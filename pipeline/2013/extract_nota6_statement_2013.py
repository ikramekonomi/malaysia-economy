#!/usr/bin/env python3
"""Nota 6 'Penyata Akaun Pinjaman Disatukan' (PKKP 2013, pdf 67, printed 43).

2013 structure: PINJAMAN (Dalam Negeri WITH opening / KW Pinjaman Perumahan
Terimaan+Bayaran+closing / Luar Negeri nil), BANTUAN LUAR NEGERI (Multilateral
/ Bilateral Terimaan+Bayaran+closing, no printed openings), group totals,
Pindahan Ke (KW Pembangunan; KW Pinjaman Perumahan), closing BAKI
26,380,357,864 / 28,904,795,292.  (Debit)/Kredit convention, columns 2013|2012.
Verbatim token verification against pdf 67; identities checked below.
"""
import csv
import sys

SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2013/fact_loan_account_statement.csv"
STMT = "Nota 6 Penyata Akaun Pinjaman Disatukan"
PG = 67
pages = open("/home/claude/pkkp/work/2013/full.txt", encoding="utf-8").read().split("\f")


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
    if s not in pages[PG - 1]:
        verify_fail.append(s)


# group, sub, label, row_type, 2013, 2012
SPEC = [
    ("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", "detail", "28,904,795,292", "38,909,479,613"),
    ("PINJAMAN", "Dalam Negeri", "Terimaan", "detail", "106,957,188,482", "102,645,229,672"),
    ("PINJAMAN", "Dalam Negeri", "Bayaran", "detail", "(67,430,098,558)", "(59,303,631,379)"),
    ("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", "detail", "68,431,885,216", "82,251,077,906"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", "detail", "4,400,000,000", "5,500,000,000"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", "detail", "(5,600,000,000)", "(2,100,000,000)"),
    ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", "detail", "(1,200,000,000)", "3,400,000,000"),
    ("PINJAMAN", "Luar Negeri", "Terimaan", "detail", "-", "-"),
    ("PINJAMAN", "Luar Negeri", "Bayaran", "detail", "-", "-"),
    ("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", "detail", "-", "-"),
    ("PINJAMAN", "", "Jumlah Pinjaman pada 31 Disember", "group_total", "67,231,885,216", "85,651,077,906"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Terimaan", "detail", "325,828", "91,016,051"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Bayaran", "detail", "(98,564,203)", "(95,017,283)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", "detail", "(98,238,375)", "(4,001,232)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Terimaan", "detail", "412,326,368", "592,519,054"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Bayaran", "detail", "(535,615,345)", "(602,570,204)"),
    ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", "detail", "(123,288,977)", "(10,051,150)"),
    ("BANTUAN LUAR NEGERI", "", "Jumlah Bantuan Luar Negeri pada 31 Disember", "group_total", "(221,527,352)", "(14,052,382)"),
    ("JUMLAH", "", "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", "total", "67,010,357,864", "85,637,025,524"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", "transfer", "(41,830,000,000)", "(53,332,230,232)"),
    ("PINDAHAN KE", "", "Kumpulan Wang Pinjaman Perumahan", "transfer", "1,200,000,000", "(3,400,000,000)"),
    ("BAKI", "", "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", "closing", "26,380,357,864", "28,904,795,292"),
]

rows = []
for grp, sub, label, rt, a13, a12 in SPEC:
    for tok in (a13, a12):
        V(tok)
    rows.append([grp, sub or None, label, rt, 2013, N(a13), SRC, PG, PG - 24, STMT])
    rows.append([grp, sub or None, label, rt, 2012, N(a12), SRC, PG, PG - 24, STMT])

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
for yr in (2013, 2012):
    dn = g[("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", yr)]
    kw = g[("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", yr)]
    ln = g[("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", yr)]
    if abs(dn + kw + ln - g[("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember", yr)]) > 1:
        print(f"FAIL {yr} PINJAMAN subtotal"); ok = False
    bl = (g[("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", yr)]
          + g[("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", yr)])
    if abs(bl - g[("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember", yr)]) > 1:
        print(f"FAIL {yr} BANTUAN subtotal"); ok = False
    j = g[("JUMLAH", None, "Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember", yr)]
    if abs(g[("PINJAMAN", None, "Jumlah Pinjaman pada 31 Disember", yr)]
           + g[("BANTUAN LUAR NEGERI", None, "Jumlah Bantuan Luar Negeri pada 31 Disember", yr)] - j) > 1:
        print(f"FAIL {yr} JUMLAH"); ok = False
    tr = (g[("PINDAHAN KE", None, "Kumpulan Wang Pembangunan", yr)]
          + g[("PINDAHAN KE", None, "Kumpulan Wang Pinjaman Perumahan", yr)])
    if abs(j + tr - g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", yr)]) > 1:
        print(f"FAIL {yr} closing roll"); ok = False
    if abs(g[("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", yr)]
           + g[("PINJAMAN", "Dalam Negeri", "Terimaan", yr)]
           + g[("PINJAMAN", "Dalam Negeri", "Bayaran", yr)] - dn) > 1:
        print(f"FAIL {yr} DN roll"); ok = False
c = g[("BAKI", None, "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", 2013)]
print(f"closing 2013 = {c:,.0f} (expect 26,380,357,864) -> {'PASS' if abs(c-26380357864)<1 else 'FAIL'}")
print(f"nota6: identities {'PASS' if ok else 'SEE FAILURES'}; tokens verified verbatim on pdf 67")
sys.exit(0 if ok else 1)
