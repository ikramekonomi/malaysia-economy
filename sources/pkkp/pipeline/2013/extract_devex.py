#!/usr/bin/env python3
"""Extract development expenditure per Maksud (JUMLAH <MINISTRY> rows) from
Lampiran 2 (PKKP 2013, pdf 226-253).

Same 2013 single-page full-spread layout as extract_lampiran2_projects.py: each
even PDF page is a complete 9-column table; consecutive pages come in identical
content pairs so we read the even page of each pair with the CropBox width
filter removed.  This script emits one row per Maksud vote total (the
'JUMLAH <MINISTRY>' subtotal line) with all 9 numeric columns, matching the
warehouse fact_devex_maksud schema.  It shares the parsing core with the
project-level extractor and is validated against it (per-maksud reconciliation).

RMKe-10 era: terkumpul_rmke10_prior_rm = cumulative RMKe-10 to 31.12.2012,
terkumpul_rmke10_rm = cumulative RMKe-10 to 31.12.2013 = prior + sebenar 2013.
"""
import csv
import re
import pdfplumber

YEAR = 2013
SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
PDF = "/home/claude/pkkp/work/2013/2013.pdf"
OUT = "/home/claude/pkkp/warehouse2013/fact_devex_maksud.csv"
STMT = "Lampiran 2 Penyata Perbelanjaan Pembangunan"
PAGES = range(226, 254, 2)
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")
ANCH = [465.0, 530.8, 752.4, 805.7, 886.5, 952.4, 1001.8, 1079.3, 1155.8]

ALIASES = {}


def unspread(s):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\b([A-Z])\s+(?=[A-Z])", r"\1", s)
    return s


def desp(s):
    return re.sub(r"\s+", "", s or "")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    return -float(tok) if neg else float(tok)


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            if (gap < 4.0 and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+$", wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
                    if w.get("upright", True) and 0 <= w["top"] <= page_obj.height),
                   key=lambda w: w["top"])
    cleaned = []
    for w in words:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if "!" in t:
            w = dict(w)
            w["text"] = t.replace("!", "")
            if not w["text"]:
                continue
        cleaned.append(w)
    rows_, cur, cur_top = [], [], None
    for wd in cleaned:
        if cur and wd["top"] - cur_top > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    out = []
    for ws in rows_:
        ws = sorted(ws, key=lambda x: x["x0"])
        out.append((ws[0]["top"], merge_split_numbers(ws)))
    return out


def assign9(cells):
    vals = [None] * 9
    prev = -1
    for w in cells:
        best, bd = None, 1e9
        for i in range(9):
            d = abs(ANCH[i] - w["x1"])
            if d < bd:
                bd, best = d, i
        if bd > 22 or best <= prev:
            return None
        vals[best] = parse_amount(w["text"])
        prev = best
    return [0.0 if v is None else v for v in vals]


BOILER = re.compile(
    r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Kos Keseluruhan|"
    r"Sebenar RMKe|Hingga |Anggaran Tahun|Cara Langsung|Pinjaman|Perbelanjaan\b|"
    r"RM( RM)*$|\( ?sambungan ?\)|PENYATA KEWANGAN|\d+\. lampiran)")


def is_footer(line):
    return bool(re.search(r"\.indd|9/27/14|10:24|8\. lampiran", line)
                or re.fullmatch(r"(\d{1,3}\s*)+", line))


rows = []
current_maksud = current_name = None

with pdfplumber.open(PDF) as pdf:
    for pno in PAGES:
        pg = pdf.pages[pno - 1]
        for top, ws in lines_of(pg):
            texts = [w["text"] for w in ws]
            line = " ".join(texts)
            if BOILER.match(line) or is_footer(line):
                continue
            if (re.search(r"[–-]\s*Butiran\s+.*[–-]\s*Peruntukan|Peruntukan sebanyak RM"
                          r"|dibentangkan dalam Sesi Parlimen", line)
                    or re.match(r"^Nota\b", line) or line.strip().startswith("pendahuluan")):
                continue

            datacols = [w for w in ws if NUMTOK.match(w["text"]) and w["x0"] > 400]
            mh = re.match(r"^P\s?\.\s?(\d{2,3})\s+(.+)$", line)
            if mh and not datacols:
                current_maksud = f"P.{mh.group(1)}"
                nm = re.sub(r"\s*[–-]\s*\(SAMB\.?\)\s*$", "", mh.group(2).strip())
                current_name = unspread(nm)
                continue

            head = [w["text"] for w in ws if not (NUMTOK.match(w["text"]) and w["x0"] > 400)]
            if not datacols or not head:
                continue

            hline = " ".join(head)
            if re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", hline):
                continue  # grand total lives in the project file, not the maksud file
            if re.match(r"^JUMLAH\s+[A-Z]", hline):
                name = re.sub(r"^JUMLAH\s+", "", hline).strip()
                base = re.sub(r"\s*[–-]\s*\(SAMB\.?\)\s*$", "", current_name or "").strip()
                base_cmp = re.sub(r"\s*\([^)]*\)\s*$", "", base).strip()
                accept = {base, base_cmp} | ALIASES.get(current_maksud or "", set())
                if desp(name) not in {desp(a) for a in accept}:
                    continue  # a program subtotal, not the vote total
                vals = assign9(datacols)
                if vals is None:
                    print(f"!! JUMLAH column solve failed {current_maksud} p{pno}: {texts}")
                    continue
                foot = any("*" in w["text"] for w in datacols)
                # dedupe: keep the last JUMLAH per maksud (the vote total)
                rows[:] = [r for r in rows if r["maksud"] != current_maksud]
                rows.append({
                    "maksud": current_maksud, "name": current_name, "label": name,
                    "vals": vals, "foot": foot, "page": pno,
                })

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "jumlah_label_bm", "year",
                 "kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke10_rm", "has_footnote", "source_file", "pdf_page",
                 "printed_page", "statement"])
    for r in rows:
        kos, prior, agl, agp, agj, sbl, sbp, sbj, kum = r["vals"]
        cw.writerow([r["maksud"], r["name"], r["label"], YEAR,
                     kos, prior, agl, agp, agj, sbl, sbp, sbj, kum, r["foot"],
                     SRC, r["page"], r["page"] - 24, STMT])

print(f"fact_devex_maksud.csv: {len(rows)} rows")
for r in rows:
    print(r["maksud"], "|", r["label"][:48], "| sebenar_jumlah:", f"{r['vals'][7]:,.2f}")
