#!/usr/bin/env python3
"""Extract the Anggaran Hasil Kerajaan Persekutuan (Federal Revenue Estimates).

Documents (raw/, gitignored; belanjawan.mof.gov.my):
  ringkasan_<ed>.pdf  "Ringkasan Anggaran Hasil" — revenue by kod hasil, 3 columns
      Budget 2025 edition: Pendapatan 2023 | Anggaran Disemak 2024 | Anggaran 2025
      Budget 2026 edition: Pendapatan 2024 | Anggaran Disemak 2025 | Anggaran 2026
  hasil_<ed>.pdf      one-/two-page "revenue after Budget measures" summary
      (total before measures, per-code measure impacts, net change, total after)

Outputs (data/<edition>/):
  fact_hasil_ringkasan_<ed>.csv  one row per (kod x measure), whole RM as printed;
      "-" (nil) recorded as 0 per the warehouse en-dash convention, has_nil flag set.
      level: section (x0000) / group (x000) / item; the combined indirect-tax subtotal
      keeps its printed span code (e.g. 62000&64000); TOTAL = grand total row.
      label_bm is the first printed label line; label_context keeps the following
      wrapped/translated lines as match evidence (codes, not labels, are the join key).
  fact_hasil_measures_<ed>.csv   the Budget-measures page: revenue before measures,
      per-code impacts (parentheses = negative), net change, revenue after measures.
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "raw")
DATA = os.path.join(HERE, "..", "data")
BASE = "https://belanjawan.mof.gov.my/pdf/belanjawan{ed}/hasil/{f}.pdf"
RETRIEVED_DATE = "2026-07-31"
EDITIONS = {
    2025: ["sebenar_2023", "anggaran_disemak_2024", "anggaran_2025"],
    2026: ["sebenar_2024", "anggaran_disemak_2025", "anggaran_2026"],
}

NUM = re.compile(r"\(?\d{1,3}(?:,\d{3})+\)?|\(?\b\d{1,3}\b\)?")
CODE_ROW = re.compile(r"^\s*(\d{5})\s*([-&])?\s+(.*)$")


def tokens(line):
    """TRAILING value tokens only, collected from the end of the line: numbers
    (parentheses = negative) and '-' nils. A hyphen inside a label ("Cukai
    Jualan - Tempatan") never parses as a value because collection stops at the
    first non-value word from the right."""
    out = []
    for t in reversed(line.split()):
        if t == "-":
            out.append(("nil", 0))
        elif re.fullmatch(r"\(?\d{1,3}(?:,\d{3})*\)?", t):
            v = int(t.strip("()").replace(",", ""))
            out.append(("num", -v if t.startswith("(") else v))
        else:
            break
    return list(reversed(out))


def level_of(code):
    if "&" in code or code == "TOTAL":
        return "subtotal" if code != "TOTAL" else "total"
    n = int(code)
    if n % 10000 == 0:
        return "section"
    if n % 1000 == 0:
        return "group"
    return "item"


def pages_of(pdf):
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True,
                         text=True, check=True).stdout
    return txt.split("\f")


def printed_page(page):
    m = re.search(r"^\s*(\d+)\s+tinjauan fiskal", page, re.M) or \
        re.search(r"tinjauan fiskal\s+fiscal outlook\s+\d{4}\s+(\d+)\s*$", page, re.M)
    return m.group(1) if m else ""


def extract_ringkasan(ed, measures):
    src = os.path.join(RAW, f"ringkasan_{ed}.pdf")
    rows, cur = [], None
    for pnum, page in enumerate(pages_of(src), 1):
        pp = printed_page(page)
        plines = [l.strip() for l in page.splitlines()]
        for pli, s in enumerate(plines):
            if not s or s.startswith(("ANGGARAN HASIL", "FEDERAL GOVERNMENT", "KOD HASIL",
                                      "(Revenue Code)", "RM")) or "tinjauan fiskal" in s \
               or re.match(r"^\(\d{4}", s) or s.startswith("Anggaran Hasil"):
                continue
            if s.startswith("JUMLAH HASIL KERAJAAN PERSEKUTUAN"):
                vals = tokens(s)
                if len(vals) == 3:
                    rows.append(("TOTAL", "JUMLAH HASIL KERAJAAN PERSEKUTUAN", "",
                                 vals, pnum, pp))
                cur = None
                continue
            cm = CODE_ROW.match(s)
            vals = tokens(s)
            if cm and cm.group(1):
                code = cm.group(1)
                if cm.group(2):  # span subtotal printed "62000-" / "62000 &" with the
                    nxt = next((l for l in plines[pli + 1:pli + 3] if l), "")
                    m2 = re.match(r"^(\d{5})\b", nxt)  # second code on the next line
                    if m2:
                        code = f"{code}&{m2.group(1)}"
                rest = cm.group(3)
                # value tokens exclude the code itself
                vals = tokens(rest)
                label = re.sub(r"\(?[\d,]+\)?|-\s*$", "", rest)
                label = re.sub(r"\s+", " ", label).strip(" -")
                if len(vals) == 3:
                    rows.append((code, label, "", vals, pnum, pp))
                    cur = len(rows) - 1
                elif not vals and cm.group(2) is None and re.match(r"^\d{5}\s*[-&]?\s*$", s):
                    continue  # dangling half of a wrapped span code
                elif not vals:
                    # code row whose amounts wrapped? treat as context for previous
                    if cur is not None:
                        rows[cur] = rows[cur][:2] + (
                            (rows[cur][2] + " | " + s).strip(" |"),) + rows[cur][3:]
                continue
            if not vals and cur is not None:
                rows[cur] = rows[cur][:2] + ((rows[cur][2] + " | " + s).strip(" |"),) + rows[cur][3:]

    dest_dir = os.path.join(DATA, str(ed))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"fact_hasil_ringkasan_{ed}.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kod", "level", "label_bm", "label_context", "measure", "amount_rm",
                    "has_nil", "source_file", "pdf_page", "printed_page",
                    "retrieved_from", "retrieved_date"])
        n = 0
        for code, label, ctx, vals, pnum, pp in rows:
            for m, (kind, v) in zip(measures, vals):
                w.writerow([code, level_of(code), label, ctx, m, v,
                            kind == "nil", f"ringkasan_{ed}.pdf", pnum, pp,
                            BASE.format(ed=ed, f="ringkasan"), RETRIEVED_DATE])
                n += 1
    print(f"wrote {dest}: {n} rows, {len(rows)} lines")
    return rows


def extract_measures(ed):
    src = os.path.join(RAW, f"hasil_{ed}.pdf")
    rows = []
    state_lines = [("JUMLAH HASIL KERAJAAN PERSEKUTUAN", None)]
    seen_total = 0
    for pnum, page in enumerate(pages_of(src), 1):
        pp = printed_page(page)
        lines = [l.strip() for l in page.splitlines()]
        for li, s in enumerate(lines):
            vals = tokens(s)
            if s.startswith("JUMLAH HASIL KERAJAAN PERSEKUTUAN") and len(vals) == 1:
                seen_total += 1
                rows.append(("TOTAL_BEFORE" if seen_total == 1 else "TOTAL_AFTER",
                             s.split("  ")[0], vals[0][1], pnum, pp))
                continue
            m = re.match(r"^(\d{5})(-)?\s+(.*)$", s)
            if m and len(vals) == 1 and m.group(3):
                code = m.group(1)
                if m.group(2):  # span code printed as "62400-" with "62500 ..." on the next line
                    nxt = next((l for l in lines[li + 1:li + 3] if l), "")
                    m2 = re.match(r"^(\d{5})\b", nxt)
                    if m2:
                        code = f"{code}&{m2.group(1)}"
                label = re.sub(r"\(?[\d,]+\)?$", "", m.group(3)).strip()
                rows.append((code, label, vals[0][1], pnum, pp))
            elif "Hasil Bersih" in s and len(vals) == 1:
                rows.append(("NET_CHANGE", s.split("  ")[0].strip(), vals[0][1], pnum, pp))

    dest = os.path.join(DATA, str(ed), f"fact_hasil_measures_{ed}.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kod", "label_bm", "amount_rm", "source_file", "pdf_page",
                    "printed_page", "retrieved_from", "retrieved_date"])
        for code, label, v, pnum, pp in rows:
            w.writerow([code, label, v, f"hasil_{ed}.pdf", pnum, pp,
                        BASE.format(ed=ed, f="hasil"), RETRIEVED_DATE])
    print(f"wrote {dest}: {len(rows)} rows")


if __name__ == "__main__":
    for ed, measures in EDITIONS.items():
        extract_ringkasan(ed, measures)
        extract_measures(ed)
