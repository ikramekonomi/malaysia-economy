#!/usr/bin/env python3
"""Nota 6 'Penyata Akaun Pinjaman Disatukan' (PKKP 2014, pdf 68, printed 43).

2014 structure: PINJAMAN (Dalam Negeri WITH opening balance / Kumpulan Wang
Pinjaman Perumahan Terimaan+Bayaran+closing only / Luar Negeri nil
Terimaan+Bayaran+closing), BANTUAN LUAR NEGERI (Multilateral / Bilateral,
each WITH opening balances - 2013 openings print as unlabelled nil), 'Jumlah
Pinjaman pada 31 Disember' / 'Jumlah Bantuan Luar Negeri pada 31 Disember' /
'Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember', Pindahan Ke
(KW Pembangunan; KW Pinjaman Perumahan), closing BAKI 39,592,120,099 /
26,380,357,864. (Debit)/Kredit convention, columns 2014 | 2013.
NOTE (cross-statement print differences, kept as printed, declared in the
Nota text): Nota 6 DN Terimaan 97,309,141,548 vs cash statement
108,809,141,548 (KWPP financing routed separately here); Bilateral Terimaan
247,564,982 vs cash 222,744,257 (urus niaga bukan tunai 24,820,725);
Bilateral Bayaran (524,557,514) vs cash 516,480,465 (8,077,049).
Typed with verbatim token verification; identities checked below.
"""
import csv
import sys

SRC = "2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2014/fact_loan_account_statement.csv"
STMT = "Nota 6 Penyata Akaun Pinjaman Disatukan"
pages = open("/home/claude/pkkp/work/2014/full.txt", encoding="utf-8").read().split("\f")


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
    if s not in pages[67]:
        verify_fail.append(s)


# group, sub, label, row_type, 2014, 2013
SPEC = [
    ("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", "detail", "26,601,885,216", "28,904,795,292"),
    ("PINJAMAN", "Dalam Negeri", "Terimaan", "detail", "97,309,141,548", "106,957,188,482"),
    ("PINJAMAN", "Dalam Negeri", "Bayaran", "detail", "(59,761,587,665)", "(67,430,098,558)"),
    ("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", "detail", "64,149,439,099", "68,431,885,216"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", "detail", "11,500,000,000", "4,400,000,000"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", "detail", "(6,100,000,000)", "(5,600,000,000)"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", "detail", "5,400,000,000", "(1,200,000,000)"),
    ("PINJAMAN", "Luar Negeri", "Terimaan", "detail", "-", "-"),
    ("PINJAMAN", "Luar Negeri", "Bayaran", "detail", "-", "-"),
    ("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", "detail", "-", "-"),
    ("PINJAMAN", "", "Jumlah Pinjaman pada 31 Disember", "group_total", "69,549,439,099", "67,231,885,216"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 1 Januari", "detail", "(98,238,375)", "-"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Terimaan", "detail", "26,539,848", "325,828"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Bayaran", "detail", "(109,014,953)", "(98,564,203)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", "detail", "(180,713,480)", "(98,238,375)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 1 Januari", "detail", "(123,288,977)", "-"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Terimaan", "detail", "247,564,982", "412,326,368"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Bayaran", "detail", "(524,557,514)", "(535,615,345)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", "detail", "(400,281,509)", "(123,288,977)"),
    ("BANTUAN LUAR NEGERI", "", "Jumlah Bantuan Luar Negeri pada 31 Disember", "group_total", "(580,994,989)", "(221,527,352)"),
    ("JUMLAH", "", "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", "total", "68,968,444,110", "67,010,357,864"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", "transfer", "(23,976,324,011)", "(41,830,000,000)"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pinjaman Perumahan", "transfer", "(5,400,000,000)", "1,200,000,000"),
    ("BAKI", "", "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", "closing", "39,592,120,099", "26,380,357,864"),
]

rows = []
for grp, sub, label, rt, a14, a13 in SPEC:
    for tok in (a14, a13):
        V(tok)
    rows.append([grp, sub or None, label, rt, 2014, N(a14), SRC, 68, 43, STMT])
    rows.append([grp, sub or None, label, rt, 2013, N(a13), SRC, 68, 43, STMT])

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
for yr in (2014, 2013):
    dn = g[("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", yr)]
    kw = g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", yr)]
    ln = g[("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", yr)]
    if abs(dn + kw + ln - g[("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember", yr)]) > 1:
        print(f"FAIL {yr} PINJAMAN subtotal")
        ok = False
    bl = (g[("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", yr)]
          + g[("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", yr)])
    if abs(bl - g[("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember", yr)]) > 1:
        print(f"FAIL {yr} BANTUAN subtotal")
        ok = False
    j = g[("JUMLAH", None, "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", yr)]
    if abs(g[("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember", yr)]
           + g[("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember", yr)] - j) > 1:
        print(f"FAIL {yr} JUMLAH")
        ok = False
    tr = (g[("PINDAHAN KE", None, "Kumpulan Wang Pembangunan", yr)]
          + g[("PINDAHAN KE", None, "Kumpulan Wang Pinjaman Perumahan", yr)])
    if abs(j + tr - g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", yr)]) > 1:
        print(f"FAIL {yr} closing roll")
        ok = False
    # per-block rolls where openings print
    if abs(g[("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", yr)]
           + g[("PINJAMAN", "Dalam Negeri", "Terimaan", yr)]
           + g[("PINJAMAN", "Dalam Negeri", "Bayaran", yr)] - dn) > 1:
        print(f"FAIL {yr} DN roll")
        ok = False
print(f"nota6: identities {'PASS' if ok else 'SEE FAILURES'}; tokens verified verbatim on pdf 68")
