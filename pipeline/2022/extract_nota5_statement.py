#!/usr/bin/env python3
"""Extract the Nota 5 'Penyata Akaun Hasil Disatukan' statement table (pdf 81, printed 69).

2022 volume layout matches 2023: Anggaran Disemak | Sebenar | %Anggaran | Sebenar prior | %Anggaran prior.
Differences handled: '**' footnote markers (Pemberian dan Kenaan Bayaran Tetap) normalised to '*';
wrapped labels print as label line / numbers line / 'tt '-prefixed continuation ('tt Kumpulan Wang
Pembangunan', 'tt(selepas pindahan)') — an artefact of the footnote-indent glyph in the text layer.
"""
import csv
import re

SRC = "2022_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2022/fact_revenue_account_statement.csv"
pages = open("/home/claude/pkkp/work/2022/full.txt", encoding="utf-8").read().split("\f")
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
    ("PERBELANJAAN MENGURUS", "PERBELANJAAN MENGURUS", "subtotal"),
    ("Emolumen", "PERBELANJAAN MENGURUS", "detail"),
    ("Perkhidmatan dan Bekalan", "PERBELANJAAN MENGURUS", "detail"),
    ("Aset", "PERBELANJAAN MENGURUS", "detail"),
    ("Pemberian dan Kenaan Bayaran Tetap", "PERBELANJAAN MENGURUS", "detail"),
    ("Perbelanjaan-perbelanjaan Lain", "PERBELANJAAN MENGURUS", "detail"),
    ("Pindahan Lebihan Hasil ke", "PINDAHAN", "transfer"),
    ("Jumlah Perbelanjaan Mengurus", "PERBELANJAAN MENGURUS", "total_after_transfer"),
    ("Lebihan/(Kurangan) bagi Tahun", "BAKI", "net"),
    ("BAKI PADA 31 DISEMBER", "BAKI", "closing"),
]
FULL = {
    "Pindahan Lebihan Hasil ke": "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan",
    "Jumlah Perbelanjaan Mengurus": "Jumlah Perbelanjaan Mengurus (selepas pindahan)",
}

rows = []
txt = pages[80].replace("**", "*")
start = txt.find("BAKI PADA 1 JANUARI")
end = txt.find("(a) Hasil")
region = txt[start - 2000 if start > 2000 else 0:end]

emitted = set()
prev_text = None
for line in region.split("\n"):
    s = line.rstrip()
    m = re.match(rf"^\s*(.*?)\s\s+((?:(?:{NUM})\s+){{1,5}}(?:{NUM}))\s*$", s)
    if not m:
        st = s.strip()
        if st and not re.search(r"\d", st):
            prev_text = st
        continue
    label = m.group(1).strip()
    lead_toks = []
    if label and re.fullmatch(rf"(?:{NUM})(?:\s+(?:{NUM}))*", label):
        lead_toks = re.findall(NUM, label)
        label = ""
    if not label and prev_text:
        label = prev_text
    prev_text = None
    for spec_label, section, rt in SPEC:
        if label == spec_label and spec_label not in emitted:
            toks = lead_toks + re.findall(NUM, m.group(2))
            foot = any("*" in t for t in toks)
            vals = [parse_amount(t) for t in toks]
            a_disemak = seb = pct = pri = pct_pri = None
            if len(vals) == 5:
                a_disemak, seb, pct, pri, pct_pri = vals
            elif len(vals) == 6:
                a_disemak, seb, pct, pri, pct_pri = vals[0], vals[1], vals[2], vals[3], vals[4]
            elif len(vals) == 4 and rt in ("subtotal", "detail"):
                a_disemak, seb, pri = vals[0], vals[1], vals[2]
            elif len(vals) == 2:
                seb, pri = vals
            elif len(vals) == 3 and rt in ("subtotal", "detail"):
                a_disemak, seb, pri = vals
            else:
                seb = vals[0] if vals else None
                pri = vals[1] if len(vals) > 1 else None
            full_label = FULL.get(spec_label, spec_label)
            rows.append([section, full_label, rt, 2022, a_disemak, seb, pct, foot,
                         SRC, 81, 69, "Nota 5 Penyata Akaun Hasil Disatukan"])
            rows.append([section, full_label, rt, 2021, None, pri, pct_pri, foot,
                         SRC, 81, 69, "Nota 5 Penyata Akaun Hasil Disatukan"])
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
    if r[3] == 2022:
        print(f"  [{r[2]:20s}] {r[1][:45]:45s} disemak={r[4]} sebenar={r[5]} foot={r[7]}")
