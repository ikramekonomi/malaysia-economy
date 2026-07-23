#!/usr/bin/env python3
"""Nota 6 'Penyata Akaun Pinjaman Disatukan' (PKKP 2015, pdf 69, printed 55;
whole statement on one page -- no spill to pdf 70).

2015 structure vs 2014: PINJAMAN Dalam Negeri (with opening = prior-year
closing BAKI of the whole account, as in 2014), Kumpulan Wang Pinjaman
Perumahan (Terimaan/Bayaran/closing only), Luar Negeri now ACTIVE (Sukuk
Global: Terimaan 5,303,204,400 / Bayaran (4,420,000,000)); BANTUAN LUAR
NEGERI Multilateral & Bilateral with openings (2015 openings print '-');
Jumlah rows; Pindahan Ke (KW Pembangunan; KW Pinjaman Perumahan); closing
BAKI 28,385,609,134 / 39,592,120,099. (Debit)/Kredit convention.
Cross-statement print differences (kept as printed, declared in the Nota
text): DN Terimaan 107,804,279,579 vs cash 115,804,279,579 and DN Bayaran
(68,488,110,445) vs cash 72,788,110,445 (KWPP financing 8.0b/4.3b routed
separately here); Bilateral Bayaran (284,889,446) vs cash 282,391,376
(urus niaga bukan tunai RM2,498,070, declared).
NO text layer -- every value EYE-READ from crops/p069_n[0-3].png (scale 3).
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocrlib import SRC, YEAR, PRIOR, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015/fact_loan_account_statement.csv"
STMT = "Nota 6 Penyata Akaun Pinjaman Disatukan"
PDF, PRINTED = 69, 55
N = parse_amount
checks = []

# group, sub, label, row_type, 2015, 2014  (eye-read)
SPEC = [
    ("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", "detail", "39,592,120,099", "26,601,885,216"),
    ("PINJAMAN", "Dalam Negeri", "Terimaan", "detail", "107,804,279,579", "97,309,141,548"),
    ("PINJAMAN", "Dalam Negeri", "Bayaran", "detail", "(68,488,110,445)", "(59,761,587,665)"),
    ("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", "detail", "78,908,289,233", "64,149,439,099"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", "detail", "8,000,000,000", "11,500,000,000"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", "detail", "(4,300,000,000)", "(6,100,000,000)"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", "detail", "3,700,000,000", "5,400,000,000"),
    ("PINJAMAN", "Luar Negeri", "Terimaan", "detail", "5,303,204,400", "-"),
    ("PINJAMAN", "Luar Negeri", "Bayaran", "detail", "(4,420,000,000)", "-"),
    ("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", "detail", "883,204,400", "-"),
    ("PINJAMAN", "", "Jumlah Pinjaman pada 31 Disember", "group_total", "83,491,493,633", "69,549,439,099"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 1 Januari", "detail", "-", "(98,238,375)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Terimaan", "detail", "-", "26,539,848"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Bayaran", "detail", "(127,773,160)", "(109,014,953)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", "detail", "(127,773,160)", "(180,713,480)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 1 Januari", "detail", "-", "(123,288,977)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Terimaan", "detail", "256,238,110", "247,564,982"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Bayaran", "detail", "(284,889,446)", "(524,557,514)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", "detail", "(28,651,336)", "(400,281,509)"),
    ("BANTUAN LUAR NEGERI", "", "Jumlah Bantuan Luar Negeri pada 31 Disember", "group_total", "(156,424,496)", "(580,994,989)"),
    ("JUMLAH", "", "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", "total", "83,335,069,137", "68,968,444,110"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", "transfer", "(49,249,460,003)", "(23,976,324,011)"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pinjaman Perumahan", "transfer", "(5,700,000,000)", "(5,400,000,000)"),
    ("BAKI", "", "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", "closing", "28,385,609,134", "39,592,120,099"),
]

rows = []
for grp, sub, label, rt, a15, a14 in SPEC:
    rows.append([grp, sub or None, label, rt, YEAR, N(a15), SRC, PDF, PRINTED, STMT])
    rows.append([grp, sub or None, label, rt, PRIOR, N(a14), SRC, PDF, PRINTED, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["group_bm", "sub_bm", "line_item_bm", "row_type", "year", "amount_rm",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_loan_account_statement.csv: {len(rows)} rows")

# ---- identities -------------------------------------------------------------
g = {}
for r in rows:
    g[(r[0], r[1], r[2], r[4])] = r[5]
for yr in (YEAR, PRIOR):
    dn = g[("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", yr)]
    roll = (g[("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", yr)]
            + g[("PINJAMAN", "Dalam Negeri", "Terimaan", yr)]
            + g[("PINJAMAN", "Dalam Negeri", "Bayaran", yr)])
    checks.append(("PASS" if abs(roll - dn) < 0.5 else "FAIL",
                   f"nota6: Dalam Negeri opening+terimaan-bayaran {yr} vs printed closing", roll, dn, roll - dn))
    kw = g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", yr)]
    roll = (g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", yr)]
            + g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", yr)])
    checks.append(("PASS" if abs(roll - kw) < 0.5 else "FAIL",
                   f"nota6: KW Pinjaman Perumahan terimaan-bayaran {yr} vs printed closing", roll, kw, roll - kw))
    ln = g[("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", yr)]
    roll = g[("PINJAMAN", "Luar Negeri", "Terimaan", yr)] + g[("PINJAMAN", "Luar Negeri", "Bayaran", yr)]
    checks.append(("PASS" if abs(roll - ln) < 0.5 else "FAIL",
                   f"nota6: Luar Negeri terimaan-bayaran {yr} vs printed closing", roll, ln, roll - ln))
    jp = g[("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember", yr)]
    checks.append(("PASS" if abs(dn + kw + ln - jp) < 0.5 else "FAIL",
                   f"nota6: DN+KWPP+LN closings {yr} vs printed Jumlah Pinjaman", dn + kw + ln, jp, dn + kw + ln - jp))
    for sub in ("Pinjaman Multilateral", "Pinjaman Bilateral"):
        cl = g[("BANTUAN LUAR NEGERI", sub, "Baki pada 31 Disember", yr)]
        roll = (g[("BANTUAN LUAR NEGERI", sub, "Baki pada 1 Januari", yr)]
                + g[("BANTUAN LUAR NEGERI", sub, "Terimaan", yr)]
                + g[("BANTUAN LUAR NEGERI", sub, "Bayaran", yr)])
        checks.append(("PASS" if abs(roll - cl) < 0.5 else "FAIL",
                       f"nota6: {sub} roll-forward {yr} vs printed closing", roll, cl, roll - cl))
    jb = g[("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember", yr)]
    bl = (g[("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", yr)]
          + g[("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", yr)])
    checks.append(("PASS" if abs(bl - jb) < 0.5 else "FAIL",
                   f"nota6: Multilateral+Bilateral closings {yr} vs printed Jumlah Bantuan Luar Negeri", bl, jb, bl - jb))
    j = g[("JUMLAH", None, "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", yr)]
    checks.append(("PASS" if abs(jp + jb - j) < 0.5 else "FAIL",
                   f"nota6: Jumlah Pinjaman + Jumlah BLN {yr} vs printed Jumlah P&BLN", jp + jb, j, jp + jb - j))
    tr = (g[("PINDAHAN KE", None, "Kumpulan Wang Pembangunan", yr)]
          + g[("PINDAHAN KE", None, "Kumpulan Wang Pinjaman Perumahan", yr)])
    cl = g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", yr)]
    checks.append(("PASS" if abs(j + tr - cl) < 0.5 else "FAIL",
                   f"nota6: Jumlah P&BLN + pindahan {yr} vs printed closing BAKI", j + tr, cl, j + tr - cl))
# closing vs position statement
pos = {int(r["year"]): float(r["amount_rm"])
       for r in csv.DictReader(open("/home/claude/pkkp/warehouse2015/fact_financial_position.csv", encoding="utf-8"))
       if r["line_item_bm"] == "AKAUN PINJAMAN DISATUKAN"}
for yr, want in ((YEAR, 28385609134.0), (PRIOR, 39592120099.0)):
    got = g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", yr)]
    checks.append(("PASS" if got == want == pos[yr] else "FAIL",
                   f"nota6: closing BAKI {yr} vs Penyata Kedudukan Kewangan Akaun Pinjaman", got, pos[yr], got - pos[yr]))
# 2015 DN opening = 2014 closing BAKI of whole account (as printed; same pattern as 2014 volume)
checks.append(("PASS" if g[("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", YEAR)] == 39592120099.0 else "FAIL",
               "nota6: 2015 DN Baki 1 Januari equals 2014 closing BAKI AKAUN PINJAMAN DISATUKAN (whole-account opening printed under Dalam Negeri, as in 2014 volume)",
               g[("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", YEAR)], 39592120099.0, 0))
# cross-statement print differences vs cash statement (kept as printed)
cash = {(r["flow"], r["category_bm"], r["item_bm"]): float(r["amount_rm"])
        for r in csv.DictReader(open("/home/claude/pkkp/warehouse2015/fact_cash_statement.csv", encoding="utf-8"))
        if r["year"] == "2015"}
checks.append(("WARN", "nota6: DN Terimaan 107,804,279,579 vs cash statement Pinjaman Dalam Negeri terimaan 115,804,279,579 -- diff 8,000,000,000 = KWPP financing routed separately in Nota 6; kept as printed",
               107804279579.0, cash[("TERIMAAN", "Pinjaman", "Dalam Negeri")], 107804279579.0 - cash[("TERIMAAN", "Pinjaman", "Dalam Negeri")]))
checks.append(("WARN", "nota6: DN Bayaran (68,488,110,445) vs cash statement Pinjaman Dalam Negeri bayaran 72,788,110,445 -- diff 4,300,000,000 = KWPP bayaran routed separately in Nota 6; kept as printed",
               68488110445.0, cash[("BAYARAN", "Pinjaman", "Dalam Negeri")], 68488110445.0 - cash[("BAYARAN", "Pinjaman", "Dalam Negeri")]))
checks.append(("WARN", "nota6: Bilateral Bayaran (284,889,446) vs cash statement Bantuan Luar Negeri Pinjaman Bilateral 282,391,376 -- diff 2,498,070 declared in Nota 6 text as urus niaga bukan tunai bayaran balik pinjaman; kept as printed",
               284889446.0, cash[("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Bilateral")], 284889446.0 - cash[("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Bilateral")]))
for lbl, mine, key in (("LN Terimaan", 5303204400.0, ("TERIMAAN", "Pinjaman", "Luar Negeri")),
                       ("LN Bayaran", 4420000000.0, ("BAYARAN", "Pinjaman", "Luar Negeri")),
                       ("Multilateral Bayaran", 127773160.0, ("BAYARAN", "Bantuan Luar Negeri", "Pinjaman Multilateral")),
                       ("Bilateral Terimaan", 256238110.0, ("TERIMAAN", "Bantuan Luar Negeri", "Pinjaman Bilateral"))):
    checks.append(("PASS" if abs(mine - abs(cash[key])) < 0.5 else "FAIL",
                   f"nota6: {lbl} 2015 vs cash statement", mine, abs(cash[key]), mine - abs(cash[key])))
# 2014 comparative column vs 2014 volume
prev = {(r["group_bm"], r["sub_bm"] or None, r["line_item_bm"]): float(r["amount_rm"])
        for r in csv.DictReader(open("/home/claude/pkkp/warehouse2014/fact_loan_account_statement.csv", encoding="utf-8"))
        if r["year"] == "2014"}
bad = 0
for grp, sub, label, rt, a15, a14 in SPEC:
    key = (grp, sub or None, label)
    if key not in prev:
        checks.append(("INFO", f"nota6: line absent from 2014 volume: {key}", N(a14), None, None))
        continue
    if abs(N(a14) - prev[key]) > 0.5:
        bad += 1
        checks.append(("WARN", f"nota6: 2014 comparative differs from 2014 volume for {label} ({sub or grp}) (restatement candidate, kept as printed)",
                       N(a14), prev[key], N(a14) - prev[key]))
if not bad:
    checks.append(("PASS", "nota6: all 2014 comparatives match warehouse2014 fact_loan_account_statement (2014 rows)", len(SPEC), len(SPEC), 0))
checks.append(("INFO", "nota6: 48 amount cells eye-read from crops/p069_n[0-3].png at 3x; all 2015/2014 columns confirmed by roll-forward identities; statement confirmed fully on pdf 69 (no spill to 70)", 48, None, None))
append_checks(checks)
n = sum(1 for c in checks if c[0] == "FAIL")
print(f"nota6: {len(checks)} checks appended, {n} FAIL")
