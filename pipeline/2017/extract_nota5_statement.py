#!/usr/bin/env python3
"""Extract the Nota 5 'Penyata Akaun Hasil Disatukan' statement table (pdf 61, printed 50).

2017 layout: Anggaran | Sebenar | %Anggaran | Sebenar prior | %Anggaran prior
(the current-year Anggaran column is the revised estimate; stored in
anggaran_disemak_rm to match the warehouse2018 schema).
'**' footnote (Pemberian dan Kenaan Bayaran Tetap: excludes transfer to
Kumpulan Wang Pembangunan) normalised to '*'.
Wrapped labels print label line / values-on-continuation-line:
  'PERBELANJAAN MENGURUS' + '(sebelum pindahan)  <values>'
  'PERBELANJAAN MENGURUS' + '(selepas pindahan)  <values>'
  'Pindahan Lebihan Hasil ke' + 'Kumpulan Wang Pembangunan  <values>'
Lebihan/(Kurangan) bagi Tahun prints '-' both years (surplus transferred to
Kumpulan Wang Pembangunan; Akaun Hasil balance fixed at RM11,863,127,086
since 1996)."""
import csv
import re

SRC = "2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2017/fact_revenue_account_statement.csv"
pages = open("/home/claude/pkkp/work/2017/full.txt", encoding="utf-8").read().split("\f")
NUM = r"\*?\(?[\d,]+(?:\.\d+)?\)?|\*?[–—-]"


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


SPEC = [
    ("BAKI PADA 1 JANUARI", "BAKI", "opening"),
    ("HASIL", "HASIL", "subtotal"),
    ("Hasil Cukai", "HASIL", "detail"),
    ("Hasil Bukan Cukai", "HASIL", "detail"),
    ("Terimaan Bukan Hasil", "HASIL", "detail"),
    ("Hasil Wilayah Persekutuan", "HASIL", "detail"),
    ("(sebelum pindahan)", "PERBELANJAAN MENGURUS", "subtotal"),
    ("Emolumen", "PERBELANJAAN MENGURUS", "detail"),
    ("Perkhidmatan dan Bekalan", "PERBELANJAAN MENGURUS", "detail"),
    ("Aset", "PERBELANJAAN MENGURUS", "detail"),
    ("Pemberian dan Kenaan Bayaran Tetap", "PERBELANJAAN MENGURUS", "detail"),
    ("Perbelanjaan-perbelanjaan Lain", "PERBELANJAAN MENGURUS", "detail"),
    ("Kumpulan Wang Pembangunan", "PINDAHAN", "transfer"),
    ("(selepas pindahan)", "PERBELANJAAN MENGURUS", "total_after_transfer"),
    ("Lebihan/(Kurangan) bagi Tahun", "BAKI", "net"),
    ("BAKI PADA 31 DISEMBER", "BAKI", "closing"),
]
FULL = {
    "(sebelum pindahan)": "PERBELANJAAN MENGURUS (sebelum pindahan)",
    "(selepas pindahan)": "PERBELANJAAN MENGURUS (selepas pindahan)",
    "Kumpulan Wang Pembangunan": "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan",
}

rows = []
txt = pages[60].replace("**", "*")
start = txt.find("BAKI PADA 1 JANUARI")
end = txt.find("(a) Hasil")
region = txt[start - 2000 if start > 2000 else 0:end]

emitted = set()
for line in region.split("\n"):
    s = line.rstrip()
    s = re.sub(r"^(\s*)\d{1,3}(\s{3,})", r"\1\2", s)  # strip margin page number
    s = re.sub(r"(\s{6,})\d{1,3}\s*$", "", s)
    s = re.sub(r"(\S)\s{4,}[A-Z][A-Z ]{9,}$", r"\1", s)  # rotated sidebar overprint
    m = re.match(rf"^\s*(.*?)\s\s+((?:(?:{NUM})\s+){{0,5}}(?:{NUM}))\s*$", s)
    if not m:
        continue
    label = m.group(1).strip()
    for spec_label, section, rt in SPEC:
        if label == spec_label and spec_label not in emitted:
            toks = re.findall(NUM, m.group(2))
            foot = any("*" in t for t in toks)
            vals = [parse_amount(t) for t in toks]
            a_ang = seb = pct = pri = pct_pri = None
            if len(vals) == 5:
                a_ang, seb, pct, pri, pct_pri = vals
            elif len(vals) == 4:
                a_ang, seb, pri, pct_pri = vals[0], vals[1], vals[2], vals[3]
            elif len(vals) == 2:
                seb, pri = vals
            elif len(vals) == 1:
                seb = vals[0]
            else:
                continue
            full_label = FULL.get(spec_label, spec_label)
            rows.append([section, full_label, rt, 2017, a_ang, seb, pct, foot,
                         SRC, 61, 50, "Nota 5 Penyata Akaun Hasil Disatukan"])
            rows.append([section, full_label, rt, 2016, None, pri, pct_pri, foot,
                         SRC, 61, 50, "Nota 5 Penyata Akaun Hasil Disatukan"])
            emitted.add(spec_label)
            break

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "row_type", "year",
                 "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_revenue_account_statement.csv: {len(rows)} rows ({len(emitted)}/{len(SPEC)} line items)")
missing = [sl for sl, _, _ in SPEC if sl not in emitted]
if missing:
    print("MISSING:", missing)
for r in rows:
    if r[3] == 2017:
        print(f"  [{r[2]:20s}] {r[1][:48]:48s} anggaran={r[4]} sebenar={r[5]} pct={r[6]} foot={r[7]}")
