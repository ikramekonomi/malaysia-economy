#!/usr/bin/env python3
"""Nota 5 'Penyata Akaun Hasil Disatukan' (PKKP 2014, pdf 65, printed 40).

2014 layout matches 2016: Anggaran | Sebenar RM | %Anggaran | prior Sebenar RM
| prior %Anggaran (the single Anggaran column is the anggaran disemak - it
equals Nota 5(a)'s Anggaran Disemak total; stored in anggaran_disemak_rm for
schema continuity). Pemberian dan Kenaan Bayaran Tetap prints '**' on both
years' sebenar (excludes the transfer to Kumpulan Wang Pembangunan).
Typed from the page with verbatim token verification; identities validated in
validate.py.
"""
import csv
import sys

SRC = "2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2014/fact_revenue_account_statement.csv"
STMT = "Nota 5 Penyata Akaun Hasil Disatukan"
pages = open("/home/claude/pkkp/work/2014/full.txt", encoding="utf-8").read().split("\f")


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
    if s not in pages[64]:
        verify_fail.append(s)


# section, label, row_type, anggaran, sebenar, pct, prior, pct_prior
SPEC = [
    ("BAKI", "BAKI PADA 1 JANUARI", "opening", "", "11,863,127,086", "", "11,863,127,086", ""),
    ("HASIL", "Hasil Cukai", "detail", "171,770,377,000", "164,204,887,589", "95.60", "155,952,205,546", "95.38"),
    ("HASIL", "Hasil Bukan Cukai", "detail", "51,526,705,000", "53,898,784,542", "104.60", "54,450,479,701", "100.04"),
    ("HASIL", "Terimaan Bukan Hasil", "detail", "1,152,467,000", "1,666,651,362", "144.62", "1,589,505,741", "104.16"),
    ("HASIL", "Hasil Wilayah Persekutuan", "detail", "644,880,000", "855,349,863", "132.64", "1,378,022,570", "143.31"),
    ("HASIL", "Jumlah Hasil", "subtotal", "225,094,429,000", "220,625,673,356", "98.01", "213,370,213,558", "96.80"),
    ("PERBELANJAAN MENGURUS", "Emolumen", "detail", "66,476,153,030", "66,946,934,325", "100.71", "61,001,190,871", "98.22"),
    ("PERBELANJAAN MENGURUS", "Perkhidmatan dan Bekalan", "detail", "35,499,389,766", "34,258,880,520", "96.51", "33,860,076,805", "98.57"),
    ("PERBELANJAAN MENGURUS", "Aset", "detail", "1,885,255,875", "1,802,125,806", "95.59", "1,414,680,060", "95.85"),
    ("PERBELANJAAN MENGURUS", "Pemberian dan Kenaan Bayaran Tetap", "detail", "116,722,105,786", "**115,096,757,716", "98.61", "**113,762,343,505", "96.85"),
    ("PERBELANJAAN MENGURUS", "Perbelanjaan-perbelanjaan Lain", "detail", "1,498,367,513", "1,484,444,205", "99.07", "1,232,045,552", "98.64"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (sebelum pindahan)", "subtotal", "222,081,271,970", "219,589,142,572", "98.88", "211,270,336,793", "97.52"),
    ("PINDAHAN", "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", "transfer", "-", "1,036,530,784", "-", "2,099,876,765", "-"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (selepas pindahan)", "total_after_transfer", "222,081,271,970", "220,625,673,356", "99.34", "213,370,213,558", "98.49"),
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
    rows.append([sec, label, rt, 2014, ag_v, seb_v,
                 N(pct) if pct and pct != "-" else None, foot, SRC, 65, 40, STMT])
    rows.append([sec, label, rt, 2013, None, pri_v,
                 N(pct_pri) if pct_pri and pct_pri != "-" else None, foot, SRC, 65, 40, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "row_type", "year",
                 "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_revenue_account_statement.csv: {len(rows)} rows")
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES:", verify_fail)
    sys.exit(1)
print("nota5 stmt: all typed tokens verified verbatim on pdf 65")
