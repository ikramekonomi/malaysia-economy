#!/usr/bin/env python3
"""Nota 5 'Penyata Akaun Hasil Disatukan' (PKKP 2016, pdf 63, printed 52).

2016 layout: Anggaran | Sebenar RM | %Anggaran | prior Sebenar RM | prior
%Anggaran. Differences vs 2018:
 - the HASIL / PERBELANJAAN MENGURUS headers are label-only; their totals print
   as 'Jumlah Hasil' and 'Jumlah Perbelanjaan Mengurus (sebelum pindahan)';
 - an explicit before-transfer subtotal row exists (2018 printed only the
   PERBELANJAAN MENGURUS row before transfer);
 - Pemberian dan Kenaan Bayaran Tetap prints '**' on both years' sebenar
   (excludes the transfer to Kumpulan Wang Pembangunan).
Typed from the page with verbatim token verification; identities validated in
validate.py.
"""
import csv
import sys

SRC = "2016_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2016/fact_revenue_account_statement.csv"
STMT = "Nota 5 Penyata Akaun Hasil Disatukan"
pages = open("/home/claude/pkkp/work/2016/full.txt", encoding="utf-8").read().split("\f")


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
    if s not in pages[62]:
        verify_fail.append(s)


# section, label, row_type, anggaran, sebenar, pct, prior, pct_prior
SPEC = [
    ("BAKI", "BAKI PADA 1 JANUARI", "opening", "", "11,863,127,086", "", "11,863,127,086", ""),
    ("HASIL", "Hasil Cukai", "detail", "167,101,197,000", "169,343,339,135", "101.34", "165,440,651,772", "97.31"),
    ("HASIL", "Hasil Bukan Cukai", "detail", "42,694,178,000", "40,006,195,479", "93.70", "51,466,753,565", "102.74"),
    ("HASIL", "Terimaan Bukan Hasil", "detail", "1,887,000,000", "2,113,460,432", "112.00", "1,289,802,714", "87.53"),
    ("HASIL", "Hasil Wilayah Persekutuan", "detail", "913,000,000", "958,103,848", "104.94", "891,552,775", "102.56"),
    ("HASIL", "Jumlah Hasil", "subtotal", "212,595,375,000", "212,421,098,894", "99.92", "219,088,760,826", "98.49"),
    ("PERBELANJAAN MENGURUS", "Emolumen", "detail", "73,445,677,043", "73,108,357,069", "99.54", "70,050,168,154", "99.90"),
    ("PERBELANJAAN MENGURUS", "Perkhidmatan dan Bekalan", "detail", "30,610,047,075", "30,070,477,311", "98.24", "36,372,752,985", "99.84"),
    ("PERBELANJAAN MENGURUS", "Aset", "detail", "735,550,393", "675,652,714", "91.86", "1,722,703,353", "99.49"),
    ("PERBELANJAAN MENGURUS", "Pemberian dan Kenaan Bayaran Tetap", "detail", "106,527,016,187", "**105,404,742,507", "98.95", "**107,743,610,517", "95.94"),
    ("PERBELANJAAN MENGURUS", "Perbelanjaan-perbelanjaan Lain", "detail", "982,262,350", "913,431,733", "92.99", "1,108,293,498", "97.17"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (sebelum pindahan)", "subtotal", "212,300,553,048", "210,172,661,334", "99.00", "216,997,528,507", "97.87"),
    ("PINDAHAN", "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", "transfer", "-", "2,248,437,560", "-", "2,091,232,319", "-"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (selepas pindahan)", "total_after_transfer", "212,300,553,048", "212,421,098,894", "100.06", "219,088,760,826", "98.81"),
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
    rows.append([sec, label, rt, 2016, ag_v, seb_v,
                 N(pct) if pct and pct != "-" else None, foot, SRC, 63, 52, STMT])
    rows.append([sec, label, rt, 2015, None, pri_v,
                 N(pct_pri) if pct_pri and pct_pri != "-" else None, foot, SRC, 63, 52, STMT])

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
print("nota5 stmt: all typed tokens verified verbatim on pdf 63")
