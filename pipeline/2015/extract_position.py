#!/usr/bin/env python3
"""Penyata Kedudukan Kewangan (PKKP 2015, pdf 59, printed 45).

Same layout as 2014: WANG AWAM (Wang Tunai/Pelaburan) with an unlabelled
balancing subtotal, then 'DIPEGANG BAGI : KUMPULAN WANG DISATUKAN' (Akaun
Hasil/Pinjaman/Amanah Disatukan) with the same unlabelled total. Columns
2015 | 2014. Values EYE-TYPED from 400-dpi crops (p059_a/b.png); both sides
foot exactly and the 2014 comparatives equal the 2014 volume's own figures.
"""
import csv
import sys

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
from ocrlib import SRC, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015/fact_financial_position.csv"
STMT = "Penyata Kedudukan Kewangan"
PDF_PAGE, PRINTED = 59, 45

SPEC = [  # section, item, nota, v2015, v2014
    ("WANG AWAM", "WANG TUNAI", "3", "22,972,548,115", "17,426,671,072"),
    ("WANG AWAM", "PELABURAN", "4", "25,754,372,536", "23,414,668,249"),
    ("WANG AWAM", "JUMLAH WANG AWAM", "", "48,726,920,651", "40,841,339,321"),
    ("KUMPULAN WANG DISATUKAN", "AKAUN HASIL DISATUKAN", "5", "11,863,127,086", "11,863,127,086"),
    ("KUMPULAN WANG DISATUKAN", "AKAUN PINJAMAN DISATUKAN", "6", "28,385,609,134", "39,592,120,099"),
    ("KUMPULAN WANG DISATUKAN", "AKAUN AMANAH DISATUKAN", "7", "8,478,184,431", "(10,613,907,864)"),
    ("KUMPULAN WANG DISATUKAN", "JUMLAH KUMPULAN WANG DISATUKAN", "", "48,726,920,651", "40,841,339,321"),
]

rows, checks = [], []
for sec, item, nota, v15, v14 in SPEC:
    for year, v in ((2015, v15), (2014, v14)):
        rows.append([sec, item, nota, year, parse_amount(v), SRC, PDF_PAGE, PRINTED, STMT])

for year, col in ((2015, 4), (2014, 4)):
    vals = {r[1]: r[col] for r in rows if r[3] == year}
    s1 = vals["WANG TUNAI"] + vals["PELABURAN"]
    s2 = (vals["AKAUN HASIL DISATUKAN"] + vals["AKAUN PINJAMAN DISATUKAN"]
          + vals["AKAUN AMANAH DISATUKAN"])
    for nm, got in (("wang awam side", s1), ("kumpulan wang side", s2)):
        want = vals["JUMLAH WANG AWAM"] if nm.startswith("wang") else vals["JUMLAH KUMPULAN WANG DISATUKAN"]
        st = "PASS" if abs(got - want) < 0.5 else "FAIL"
        checks.append((st, f"position: {nm} {year} foots to printed total", got, want, got - want))

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["section", "line_item_bm", "nota", "year", "amount_rm",
                "source_file", "pdf_page", "printed_page", "statement"])
    w.writerows(rows)
checks.append(("INFO", "position: values eye-typed from 400-dpi crops (no text layer)", len(rows), "", ""))
append_checks(checks)
print(f"fact_financial_position.csv: {len(rows)} rows")
for c in checks:
    print(c)
