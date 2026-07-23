#!/usr/bin/env python3
"""Nota 5 'Penyata Akaun Hasil Disatukan' (PKKP 2013, pdf 64, printed 40).

Columns: 2013 Anggaran | Sebenar | %Anggaran ; 2012 Sebenar | %Anggaran.
The single 2013 Anggaran column is stored in anggaran_disemak_rm for schema
continuity with the 2014/2016 outputs.  Pemberian dan Kenaan Bayaran Tetap
prints '**' on both years' sebenar (excludes transfer to KW Pembangunan).
Verbatim token verification against pdf 64.
"""
import csv
import sys

SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2013/fact_revenue_account_statement.csv"
STMT = "Nota 5 Penyata Akaun Hasil Disatukan"
PG = 64
pages = open("/home/claude/pkkp/work/2013/full.txt", encoding="utf-8").read().split("\f")


def N(s):
    s = s.strip().replace("*", "")
    if s in ("-", "–", ""):
        return None
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


verify_fail = []


def V(s):
    s = s.strip().lstrip("*")
    if s in ("-", "–", ""):
        return
    if s not in pages[PG - 1]:
        verify_fail.append(s)


# section, label, row_type, anggaran(2013), sebenar(2013), pct(2013), prior sebenar(2012), pct(2012)
SPEC = [
    ("BAKI", "BAKI PADA 1 JANUARI", "opening", "", "11,863,127,086", "", "11,863,127,086", ""),
    ("HASIL", "Hasil Cukai", "detail", "163,506,687,000", "155,952,205,546", "95.38", "151,643,090,263", "99.44"),
    ("HASIL", "Hasil Bukan Cukai", "detail", "54,428,125,000", "54,450,479,701", "100.04", "54,909,327,554", "102.85"),
    ("HASIL", "Terimaan Bukan Hasil", "detail", "1,526,031,000", "1,589,505,741", "104.16", "876,912,254", "112.62"),
    ("HASIL", "Hasil Wilayah Persekutuan", "detail", "961,584,000", "1,378,022,570", "143.31", "483,424,598", "82.22"),
    ("HASIL", "Jumlah Hasil", "subtotal", "220,422,427,000", "213,370,213,558", "96.80", "207,912,754,669", "100.32"),
    ("PERBELANJAAN MENGURUS", "Emolumen", "detail", "62,107,462,433", "61,001,190,871", "98.22", "60,015,799,383", "109.11"),
    ("PERBELANJAAN MENGURUS", "Perkhidmatan dan Bekalan", "detail", "34,352,106,169", "33,860,076,805", "98.57", "31,962,576,293", "99.11"),
    ("PERBELANJAAN MENGURUS", "Aset", "detail", "1,475,939,548", "1,414,680,060", "95.85", "1,769,606,790", "99.78"),
    ("PERBELANJAAN MENGURUS", "Pemberian dan Kenaan Bayaran Tetap", "detail", "117,462,518,567", "**113,762,343,505", "96.85", "**110,322,740,053", "101.98"),
    ("PERBELANJAAN MENGURUS", "Perbelanjaan-perbelanjaan Lain", "detail", "1,249,041,226", "1,232,045,552", "98.64", "1,466,359,006", "96.16"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (sebelum pindahan)", "subtotal", "216,647,067,943", "211,270,336,793", "97.52", "205,537,081,525", "103.42"),
    ("PINDAHAN", "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", "transfer", "-", "2,099,876,765", "-", "2,375,673,144", "-"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (selepas pindahan)", "total_after_transfer", "216,647,067,943", "213,370,213,558", "98.49", "207,912,754,669", "104.62"),
    ("BAKI", "Lebihan/(Kurangan) bagi Tahun", "net", "", "-", "", "-", ""),
    ("BAKI", "BAKI PADA 31 DISEMBER", "closing", "", "11,863,127,086", "", "11,863,127,086", ""),
]

rows = []
for sec, label, rt, ag, seb, pct, pri, pct_pri in SPEC:
    for tok in (ag, seb, pct, pri, pct_pri):
        if tok:
            V(tok)
    foot = "*" in seb or "*" in pri
    seb_v = N(seb) if seb not in ("", "-", "–") else (0.0 if seb == "-" else None)
    pri_v = N(pri) if pri not in ("", "-", "–") else (0.0 if pri == "-" else None)
    ag_v = (0.0 if ag == "-" else (N(ag) if ag else None))
    rows.append([sec, label, rt, 2013, ag_v, seb_v,
                 N(pct) if pct and pct != "-" else None, foot, SRC, PG, PG - 24, STMT])
    rows.append([sec, label, rt, 2012, None, pri_v,
                 N(pct_pri) if pct_pri and pct_pri != "-" else None, foot, SRC, PG, PG - 24, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "row_type", "year",
                 "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_revenue_account_statement.csv: {len(rows)} rows")

# identity checks
d = {(r[1], r[3]): r[5] for r in rows}
ok = True


def chk(name, a, b):
    global ok
    s = "PASS" if (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 0.5) else "FAIL"
    if s == "FAIL":
        ok = False
    print(f"{s}: {name} | {a} vs {b}")


chk("Jumlah Hasil 2013 = 213,370,213,558", d[("Jumlah Hasil", 2013)], 213370213558.0)
chk("roll-forward BAKI 1 Jan = BAKI 31 Dis (2013)",
    d[("BAKI PADA 1 JANUARI", 2013)], d[("BAKI PADA 31 DISEMBER", 2013)])
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES:", verify_fail)
    sys.exit(1)
print("nota5 stmt: all typed tokens verified verbatim on pdf 64")
sys.exit(0 if ok else 1)
