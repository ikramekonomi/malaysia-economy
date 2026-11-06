#!/usr/bin/env python3
"""Extract the development (P-vote) project lists of the Anggaran Perbelanjaan Persekutuan books, as printed.

  python3 sources/anggaran/pipeline/extract_projek.py [2024 2025 2026]
      -> sources/anggaran/data/<year>/fact_anggaran_projek_<year>.csv

Each development vote (Maksud Pembangunan P.n) prints its projects in one table, over one or more pages:
  Butiran (Projek) | Tajuk | (3) Jumlah Anggaran Harga Projek | (4) Perbelanjaan Sebenar <y-2> |
  (5) Anggaran Dipinda <y-1> | Anggaran <y>: (6) Cara Langsung, (7) Pinjaman
closing with 'JUMLAH ANGGARAN PERBELANJAAN PEMBANGUNAN' and the vote's five totals. One output row per printed
project line (row_type 'project') and per vote total (row_type 'jumlah_maksud'), the five columns as printed,
whole RM. A title printed over several lines is joined. En-dash or '-' alone = 0; parentheses = negative;
'*' on a value -> has_footnote. The page's vote header gives the vote; maksud_code is normalised to the PKKP
form (P.06), maksud_code_printed keeps the book's (P.6).

Read from raw/Anggaran_Perbelanjaan_Persekutuan_<year>.pdf (sha256 checked against data/_documents_manifest.csv;
gitignored, in the L0 archive). Checked by validate_projek.py.
"""
import csv
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
NUM = r"\(?-?[\d,]+\)?\*?|[–-]"
ROW = re.compile(rf"^\s*(\d{{5}})\s+(.*?)\s+((?:(?:{NUM})\s+){{4}}(?:{NUM}))\s*$")
CODE_ONLY = re.compile(r"^\s*(\d{5})\s+(\S.*?)\s*$")
NUMS_ONLY = re.compile(rf"^\s*((?:(?:{NUM})\s+){{4}}(?:{NUM}))\s*$")
HEADER = re.compile(r"Maksud Pembangunan\s+(\d+)\s*[–-]\s*(.*?)\s{2,}(P\.\s?\d+)\s*$")
HEADER_LEFT = re.compile(r"^\s*(P\.\s?\d+)\s{2,}Maksud Pembangunan\s+(\d+)\s*[–-]\s*(.*?)\s*$")  # 2026, even pages
FIELDS = ["book_year", "maksud_code", "maksud_code_printed", "maksud_name_bm", "row_type", "program_bm", "projek_code",
          "projek_name_bm", "jumlah_anggaran_harga_projek", "sebenar_prev2", "anggaran_dipinda_prev1",
          "anggaran_langsung", "anggaran_pinjaman", "has_footnote", "source_file", "pdf_page", "printed_page"]


def amount(tok):
    t = tok.replace("*", "")
    if t in ("-", "–"):
        return 0
    neg = t.startswith("(")
    v = int(t.strip("()").replace(",", ""))
    return -v if neg else v


def norm_code(printed):
    n = int(re.sub(r"\D", "", printed))
    return f"P.{n:02d}"


def pages(pdf):
    return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True,
                          check=True).stdout.split("\f")


def printed_page(text):
    m = re.search(r"^\s*(\d+)\s*\|\s*ANGGARAN PERBELANJAAN PERSEKUTUAN", text, re.M) or \
        re.search(r"ANGGARAN PERBELANJAAN PERSEKUTUAN \d{4}\s*\|\s*(\d+)\s*$", text, re.M)
    return m.group(1) if m else ""


def extract(year):
    pdf_name = f"Anggaran_Perbelanjaan_Persekutuan_{year}.pdf"
    pdf = os.path.join(SRC, "raw", pdf_name)
    man = {r["file_name"]: r for r in csv.DictReader(open(os.path.join(SRC, "data", "_documents_manifest.csv")))}
    h = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    if h != man[pdf_name]["sha256"]:
        sys.exit(f"{pdf_name}: sha256 {h} is not the manifest's")
    out, log = [], []
    vote = None  # the vote being read: its code and parsing state carry across its pages
    for pno, text in enumerate(pages(pdf), start=1):
        if "Harga Projek" not in text or "Maksud Pembangunan" not in text:
            continue
        lines = text.splitlines()
        hdr = next((HEADER.search(ln) for ln in lines if HEADER.search(ln)), None)
        left = next((HEADER_LEFT.search(ln) for ln in lines if HEADER_LEFT.search(ln)), None)
        if hdr:
            code_p, name = hdr.group(3).replace(" ", ""), hdr.group(2).strip()
        elif left:
            code_p, name = left.group(1).replace(" ", ""), left.group(3).strip()
        else:
            log.append(f"p{pno}: project table without a vote header")
            continue
        if vote is None or vote["code"] != code_p:
            vote = {"code": code_p, "program": "", "sub": None}
        base = dict(book_year=year, maksud_code=norm_code(code_p), maksud_code_printed=code_p, maksud_name_bm=name,
                    source_file=pdf_name, pdf_page=pno, printed_page=printed_page(text))
        # the body starts after the units line ('RM RM RM ...')
        start = next((i for i, ln in enumerate(lines) if re.fullmatch(r"\s*(RM\s+){4}RM\s*", ln)), None)
        if start is None:
            log.append(f"p{pno}: no units line")
            continue
        cur, pending_total = None, False
        for ln in lines[start + 1:]:
            if not ln.strip() or re.search(r"ANGGARAN PERBELANJAAN PERSEKUTUAN \d{4}", ln):
                continue
            m = ROW.match(ln)
            if m:
                if vote["sub"] is not None:
                    vote["program"] = ""  # a project straight after a subtotal stands outside any programme
                vote["sub"] = None
                cur = dict(base, row_type="project", program_bm=vote["program"], projek_code=m.group(1),
                           projek_name_bm=m.group(2).strip())
                put(cur, m.group(3))
                out.append(cur)
                continue
            if "JUMLAH ANGGARAN" in ln:
                pending_total, cur, vote["sub"] = True, None, None
                nm = NUMS_ONLY.match(ln.split("JUMLAH ANGGARAN")[-1])
                if nm:
                    out.append(total_row(base, nm.group(1)))
                    pending_total = False
                continue
            if pending_total and "PERBELANJAAN PEMBANGUNAN" in ln:
                nm = NUMS_ONLY.match(ln.split("PERBELANJAAN PEMBANGUNAN")[-1])
                if nm and nm.group(1).strip():
                    out.append(total_row(base, nm.group(1)))
                    pending_total = False
                continue
            sub = re.match(rf"^\s*Jumlah(?:\s+([^\d\s(].*?))?(\s+(?:(?:{NUM})\s+){{4}}(?:{NUM}))?\s*$", ln)
            if sub:
                # 2024/2025 name the programme on its subtotal ('Jumlah Perikanan'); 2026 prints 'Jumlah' alone
                label = (sub.group(1) or "").strip()
                cur = dict(base, row_type="jumlah_program", program_bm=vote["program"], projek_code="",
                           projek_name_bm=f"Jumlah {label}".strip(), jumlah_anggaran_harga_projek=None)
                if sub.group(2):
                    put(cur, sub.group(2))
                out.append(cur)
                vote["sub"] = cur
                continue
            nm = NUMS_ONLY.match(ln)
            if nm:
                if pending_total:
                    out.append(total_row(base, nm.group(1)))
                    pending_total = False
                elif cur is not None and cur.get("jumlah_anggaran_harga_projek") is None:
                    put(cur, nm.group(1))
                else:
                    log.append(f"p{pno}: numbers with no row: {ln.strip()}")
                continue
            if pending_total:
                continue
            c = CODE_ONLY.match(ln)
            if c and not re.search(r"\d[\d,]{3,}", c.group(2)):
                if vote["sub"] is not None:
                    vote["program"] = ""
                vote["sub"] = None
                cur = dict(base, row_type="project", program_bm=vote["program"], projek_code=c.group(1),
                           projek_name_bm=c.group(2).strip(), jumlah_anggaran_harga_projek=None)
                out.append(cur)
                continue
            mid = re.match(rf"^\s*([^\d\s(].*?)\s+((?:(?:{NUM})\s+){{4}}(?:{NUM}))\s*$", ln)
            if mid and vote["sub"] is not None and vote["sub"].get("jumlah_anggaran_harga_projek") is None:
                # a subtotal whose name runs over three lines prints its numbers on the middle one
                vote["sub"]["projek_name_bm"] += f" {mid.group(1).strip()}"
                put(vote["sub"], mid.group(2))
                continue
            if re.search(r"\d[\d,]{4,}", ln):
                log.append(f"p{pno}: unread line: {ln.strip()[:90]}")
                continue
            t = ln.strip()
            sub = vote["sub"]
            if sub is not None:
                # a subtotal's name printed over two lines ('Jumlah Dasar, Pembangunan dan' / numbers / 'Pengurusan'):
                # the tail completes it while the open programme's name continues it
                so_far = sub["projek_name_bm"][len("Jumlah "):]
                if so_far and vote["program"] and vote["program"] != so_far and \
                        vote["program"].startswith(f"{so_far} {t}"):
                    sub["projek_name_bm"] = f"Jumlah {so_far} {t}"
                    continue
                vote["sub"], vote["program"], cur = None, t, None  # a new programme heading
                continue
            if cur is not None and cur["row_type"] == "project":
                cur["projek_name_bm"] = f"{cur['projek_name_bm']} {t}"
                continue
            if cur is None and vote["program"] and not any(r for r in out[-1:] if r.get("row_type") == "project"
                                                            and r["pdf_page"] == pno):
                # a programme heading printed over two lines, or one at the top of a page
                if out and out[-1].get("row_type") != "project" and vote.get("heading_open"):
                    vote["program"] = f"{vote['program']} {t}"
                    continue
            vote["program"], vote["heading_open"], cur = t, True, None
            continue
    bad = [r for r in out if r.get("jumlah_anggaran_harga_projek") is None]
    for r in bad:
        log.append(f"p{r['pdf_page']}: {r['maksud_code']} {r['projek_code']} has no amounts")
    return [r for r in out if r not in bad], log


def put(row, nums):
    toks = nums.split()
    vals = [amount(t) for t in toks]
    for k, v in zip(["jumlah_anggaran_harga_projek", "sebenar_prev2", "anggaran_dipinda_prev1", "anggaran_langsung",
                     "anggaran_pinjaman"], vals):
        row[k] = v
    row["has_footnote"] = any("*" in t for t in toks)


def total_row(base, nums):
    r = dict(base, row_type="jumlah_maksud", program_bm="", projek_code="",
             projek_name_bm="JUMLAH ANGGARAN PERBELANJAAN PEMBANGUNAN")
    put(r, nums)
    return r


def main():
    years = sys.argv[1:] or ["2024", "2025", "2026"]
    for y in years:
        rows, log = extract(y)
        d = os.path.join(SRC, "data", y)
        with open(os.path.join(d, f"fact_anggaran_projek_{y}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        n_v = len({r["maksud_code"] for r in rows})
        print(f"{y}: {sum(r['row_type'] == 'project' for r in rows)} projects, "
              f"{sum(r['row_type'] == 'jumlah_maksud' for r in rows)} vote totals, {n_v} votes; {len(log)} log lines")
        for ln in log[:40]:
            print("   ", ln)


if __name__ == "__main__":
    main()
