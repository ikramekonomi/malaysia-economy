#!/usr/bin/env python3
"""Nota 6 'Penyata Akaun Pinjaman Disatukan' (PKKP 2016, pdf 66, printed 55).

2016 structure: PINJAMAN (Dalam Negeri WITH opening balance / Kumpulan Wang
Pinjaman Perumahan Terimaan+Bayaran only, wound up 2016 / Luar Negeri without
opening), BANTUAN LUAR NEGERI (Multilateral / Bilateral, each WITH a printed
nil opening-balance row), Jumlah Pinjaman / Jumlah Bantuan Luar Negeri /
Jumlah Pinjaman dan Bantuan Luar Negeri all 'pada 31 Disember', Pindahan Ke
(KW Pembangunan; KW Pinjaman Perumahan nil 2016 / (5.7b) 2015), closing
BAKI 20,323,759,248 / 28,385,609,134. (Debit)/Kredit convention, columns
2016 | 2015. Typed with verbatim token verification; identities in validate.py.
NOTE (cross-statement print difference, kept as printed): Bilateral Bayaran
2015 prints (284,889,446) here vs 282,391,376 in the cash statement.
"""
import csv
import sys

SRC = "2016_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2016/fact_loan_account_statement.csv"
STMT = "Nota 6 Penyata Akaun Pinjaman Disatukan"
pages = open("/home/claude/pkkp/work/2016/full.txt", encoding="utf-8").read().split("\f")


def N(s):
    s = s.strip()
    if s in ("-", "–", ""):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


verify_fail = []


def V(s):
    s = s.strip()
    if s in ("-", "–", ""):
        return
    if s not in pages[65]:
        verify_fail.append(s)


# group, sub, label, row_type, 2016, 2015
SPEC = [
    ("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", "detail", "28,385,609,134", "39,592,120,099"),
    ("PINJAMAN", "Dalam Negeri", "Terimaan", "detail", "93,876,452,672", "107,804,279,579"),
    ("PINJAMAN", "Dalam Negeri", "Bayaran", "detail", "(56,193,846,424)", "(68,488,110,445)"),
    ("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", "detail", "66,068,215,382", "78,908,289,233"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", "detail", "–", "8,000,000,000"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", "detail", "–", "(4,300,000,000)"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", "detail", "–", "3,700,000,000"),
    ("PINJAMAN", "Luar Negeri", "Terimaan", "detail", "5,837,065,920", "5,303,204,400"),
    ("PINJAMAN", "Luar Negeri", "Bayaran", "detail", "(4,670,400,000)", "(4,420,000,000)"),
    ("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", "detail", "1,166,665,920", "883,204,400"),
    ("PINJAMAN", "", "PINJAMAN", "group_total", "67,234,881,302", "83,491,493,633"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 1 Januari", "detail", "-", "-"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Terimaan", "detail", "-", "-"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Bayaran", "detail", "(156,925,423)", "(127,773,160)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", "detail", "(156,925,423)", "(127,773,160)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 1 Januari", "detail", "-", "-"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Terimaan", "detail", "145,355,562", "256,238,110"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Bayaran", "detail", "(320,293,408)", "(284,889,446)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", "detail", "(174,937,846)", "(28,651,336)"),
    ("BANTUAN LUAR NEGERI", "", "BANTUAN LUAR NEGERI", "group_total", "(331,863,269)", "(156,424,496)"),
    ("JUMLAH", "", "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", "total", "66,903,018,033", "83,335,069,137"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", "transfer", "(46,579,258,785)", "(49,249,460,003)"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pinjaman Perumahan", "transfer", "-", "(5,700,000,000)"),
    ("BAKI", "", "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", "closing", "20,323,759,248", "28,385,609,134"),
]

rows = []
for grp, sub, label, rt, a16, a15 in SPEC:
    for tok in (a16, a15):
        V(tok)
    rows.append([grp, sub or None, label, rt, 2016, N(a16), SRC, 66, 55, STMT])
    rows.append([grp, sub or None, label, rt, 2015, N(a15), SRC, 66, 55, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["group_bm", "sub_bm", "line_item_bm", "row_type", "year", "amount_rm",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_loan_account_statement.csv: {len(rows)} rows")
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES:", verify_fail)
    sys.exit(1)

# internal identities
g = {}
for r in rows:
    g[(r[0], r[1], r[2], r[4])] = r[5]
ok = True
for yr in (2016, 2015):
    dn = g[("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", yr)]
    kw = g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", yr)]
    ln = g[("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", yr)]
    if abs(dn + kw + ln - g[("PINJAMAN", None, "PINJAMAN", yr)]) > 1:
        print(f"FAIL {yr} PINJAMAN subtotal")
        ok = False
    bl = (g[("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", yr)]
          + g[("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", yr)])
    if abs(bl - g[("BANTUAN LUAR NEGERI", None, "BANTUAN LUAR NEGERI", yr)]) > 1:
        print(f"FAIL {yr} BANTUAN subtotal")
        ok = False
    j = g[("JUMLAH", None, "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", yr)]
    if abs(g[("PINJAMAN", None, "PINJAMAN", yr)] + g[("BANTUAN LUAR NEGERI", None, "BANTUAN LUAR NEGERI", yr)] - j) > 1:
        print(f"FAIL {yr} JUMLAH")
        ok = False
    tr = (g[("PINDAHAN KE", None, "Kumpulan Wang Pembangunan", yr)]
          + g[("PINDAHAN KE", None, "Kumpulan Wang Pinjaman Perumahan", yr)])
    if abs(j + tr - g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", yr)]) > 1:
        print(f"FAIL {yr} closing roll")
        ok = False
print(f"nota6: identities {'PASS' if ok else 'SEE FAILURES'}; tokens verified verbatim on pdf 66")
