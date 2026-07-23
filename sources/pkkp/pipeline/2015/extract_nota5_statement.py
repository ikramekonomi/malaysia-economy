#!/usr/bin/env python3
"""Nota 5 'Penyata Akaun Hasil Disatukan' (PKKP 2015, pdf 66, printed 52).

Layout matches 2014: Anggaran | Sebenar RM | %Anggaran | prior Sebenar RM |
prior %Anggaran (the Anggaran column is the anggaran disemak; stored in
anggaran_disemak_rm for schema continuity). Pemberian dan Kenaan Bayaran
Tetap prints '**' on both years' sebenar; footnote reads 'Tidak termasuk
pindahan ke Kumpulan Wang Pembangunan'.
NO text layer -- every value EYE-READ from crops/p066_s[0-2].png (scale 2).
Identities validated below and appended to the shared validation CSV.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocrlib import SRC, YEAR, PRIOR, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015/fact_revenue_account_statement.csv"
STMT = "Nota 5 Penyata Akaun Hasil Disatukan"
PDF, PRINTED = 66, 52
checks = []


def N(s):
    s = s.strip().replace("*", "")
    if s in ("-", "–", ""):
        return None
    return parse_amount(s)


# section, label, row_type, anggaran, sebenar, pct, prior, pct_prior  (eye-read)
SPEC = [
    ("BAKI", "BAKI PADA 1 JANUARI", "opening", "", "11,863,127,086", "", "11,863,127,086", ""),
    ("HASIL", "Hasil Cukai", "detail", "170,017,285,000", "165,440,651,772", "97.31", "164,204,887,589", "95.60"),
    ("HASIL", "Hasil Bukan Cukai", "detail", "50,094,595,000", "51,466,753,565", "102.74", "53,898,784,542", "104.60"),
    ("HASIL", "Terimaan Bukan Hasil", "detail", "1,473,499,000", "1,289,802,714", "87.53", "1,666,651,362", "144.62"),
    ("HASIL", "Hasil Wilayah Persekutuan", "detail", "869,266,000", "891,552,775", "102.56", "855,349,863", "132.64"),
    ("HASIL", "Jumlah Hasil", "subtotal", "222,454,645,000", "219,088,760,826", "98.49", "220,625,673,356", "98.01"),
    ("PERBELANJAAN MENGURUS", "Emolumen", "detail", "70,119,225,634", "70,050,168,154", "99.90", "66,946,934,325", "100.71"),
    ("PERBELANJAAN MENGURUS", "Perkhidmatan dan Bekalan", "detail", "36,432,850,052", "36,372,752,985", "99.84", "34,258,880,520", "96.51"),
    ("PERBELANJAAN MENGURUS", "Aset", "detail", "1,731,531,453", "1,722,703,353", "99.49", "1,802,125,806", "95.59"),
    ("PERBELANJAAN MENGURUS", "Pemberian dan Kenaan Bayaran Tetap", "detail", "112,302,554,087", "**107,743,610,517", "95.94", "**115,096,757,716", "98.61"),
    ("PERBELANJAAN MENGURUS", "Perbelanjaan-perbelanjaan Lain", "detail", "1,140,601,072", "1,108,293,498", "97.17", "1,484,444,205", "99.07"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (sebelum pindahan)", "subtotal", "221,726,762,298", "216,997,528,507", "97.87", "219,589,142,572", "98.88"),
    ("PINDAHAN", "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", "transfer", "-", "2,091,232,319", "-", "1,036,530,784", "-"),
    ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (selepas pindahan)", "total_after_transfer", "221,726,762,298", "219,088,760,826", "98.81", "220,625,673,356", "99.34"),
    ("BAKI", "Lebihan/(Kurangan) bagi Tahun", "net", "", "-", "", "-", ""),
    ("BAKI", "BAKI PADA 31 DISEMBER", "closing", "", "11,863,127,086", "", "11,863,127,086", ""),
]

rows = []
for sec, label, rt, ag, seb, pct, pri, pct_pri in SPEC:
    foot = "*" in seb or "*" in pri
    seb_v = N(seb) if seb not in ("", "-", "–") else (0.0 if seb == "-" else None)
    pri_v = N(pri) if pri not in ("", "-", "–") else (0.0 if pri == "-" else None)
    ag_v = (0.0 if ag == "-" else (N(ag) if ag else None))
    rows.append([sec, label, rt, YEAR, ag_v, seb_v,
                 N(pct) if pct and pct != "-" else None, foot, SRC, PDF, PRINTED, STMT])
    rows.append([sec, label, rt, PRIOR, None, pri_v,
                 N(pct_pri) if pct_pri and pct_pri != "-" else None, foot, SRC, PDF, PRINTED, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["section_bm", "line_item_bm", "row_type", "year",
                 "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_revenue_account_statement.csv: {len(rows)} rows")

# ---- identities -------------------------------------------------------------
g = {(r[1], r[3]): (r[4], r[5]) for r in rows}  # (anggaran, sebenar)
hasil = ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"]
opex = ["Emolumen", "Perkhidmatan dan Bekalan", "Aset", "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"]
for yr in (YEAR, PRIOR):
    s = sum(g[(x, yr)][1] for x in hasil)
    want = g[("Jumlah Hasil", yr)][1]
    checks.append(("PASS" if abs(s - want) < 0.5 else "FAIL",
                   f"nota5 stmt: sum hasil items sebenar {yr} vs printed Jumlah Hasil", s, want, s - want))
    s = sum(g[(x, yr)][1] for x in opex)
    want = g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr)][1]
    checks.append(("PASS" if abs(s - want) < 0.5 else "FAIL",
                   f"nota5 stmt: sum opex items sebenar {yr} vs printed Jumlah (sebelum pindahan)", s, want, s - want))
    s = (g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr)][1]
         + g[("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", yr)][1])
    want = g[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)][1]
    checks.append(("PASS" if abs(s - want) < 0.5 else "FAIL",
                   f"nota5 stmt: sebelum + pindahan sebenar {yr} vs printed Jumlah (selepas pindahan)", s, want, s - want))
    net = g[("Jumlah Hasil", yr)][1] - g[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)][1]
    checks.append(("PASS" if abs(net - g[("Lebihan/(Kurangan) bagi Tahun", yr)][1]) < 0.5 else "FAIL",
                   f"nota5 stmt: Jumlah Hasil - Jumlah PM selepas pindahan {yr} vs printed Lebihan/(Kurangan) '-'",
                   net, g[("Lebihan/(Kurangan) bagi Tahun", yr)][1], net))
    for lbl, want in (("BAKI PADA 1 JANUARI", 11863127086.0), ("BAKI PADA 31 DISEMBER", 11863127086.0)):
        got = g[(lbl, yr)][1]
        checks.append(("PASS" if got == want else "FAIL",
                       f"nota5 stmt: {lbl} {yr} vs Penyata Kedudukan Kewangan Akaun Hasil 11,863,127,086", got, want, got - want))
# anggaran column sums (2015 only; prior anggaran not printed)
s = sum(g[(x, YEAR)][0] for x in hasil)
checks.append(("PASS" if abs(s - g[("Jumlah Hasil", YEAR)][0]) < 0.5 else "FAIL",
               "nota5 stmt: sum hasil items anggaran 2015 vs printed Jumlah Hasil anggaran", s, g[("Jumlah Hasil", YEAR)][0], s - g[("Jumlah Hasil", YEAR)][0]))
s = sum(g[(x, YEAR)][0] for x in opex)
checks.append(("PASS" if abs(s - g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0]) < 0.5 else "FAIL",
               "nota5 stmt: sum opex items anggaran 2015 vs printed Jumlah anggaran", s,
               g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0],
               s - g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0]))
# pindahan 2015 vs Nota 5(b) B.12 ** footnote figure
got = g[("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", YEAR)][1]
checks.append(("PASS" if got == 2091232319.0 else "FAIL",
               "nota5 stmt: Pindahan Lebihan Hasil ke KW Pembangunan 2015 vs Nota 5(b) B.12 ** footnote RM2,091,232,319 (printed digits verified on pdf 66)",
               got, 2091232319.0, got - 2091232319.0))
# ties to Nota 5(b) grand figures (already extracted; 2014 pattern: 5(b) grand = selepas pindahan)
checks.append(("PASS" if g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0] == 221726762298.0 else "FAIL",
               "nota5 stmt: anggaran 2015 vs Nota 5(b) JUMLAH PERBELANJAAN MENGURUS anggaran dipinda",
               g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0], 221726762298.0,
               g[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", YEAR)][0] - 221726762298.0))
checks.append(("PASS" if g[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", YEAR)][1] == 219088760826.0 else "FAIL",
               "nota5 stmt: sebenar selepas pindahan 2015 vs Nota 5(b) JUMLAH sebenar (5(b) grand = selepas-pindahan figure, same as 2014 pattern)",
               g[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", YEAR)][1], 219088760826.0,
               g[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", YEAR)][1] - 219088760826.0))
# 2014 comparative column vs 2014 volume (its 2014 current-year column)
prev = {}
for r in csv.DictReader(open("/home/claude/pkkp/warehouse2014/fact_revenue_account_statement.csv", encoding="utf-8")):
    if r["year"] == "2014":
        prev[r["line_item_bm"]] = (float(r["sebenar_rm"]) if r["sebenar_rm"] else None,
                                   float(r["pct_anggaran"]) if r["pct_anggaran"] else None)
bad = 0
for sec, label, rt, ag, seb, pct, pri, pct_pri in SPEC:
    if label not in prev:
        continue
    pv, ppct = prev[label]
    mine = N(pri) if pri not in ("", "-", "–") else (0.0 if pri == "-" else None)
    if (mine or 0) != (pv or 0):
        bad += 1
        checks.append(("WARN", f"nota5 stmt: 2014 comparative differs from 2014 volume for {label} (restatement candidate, kept as printed)",
                       mine, pv, (mine or 0) - (pv or 0)))
if not bad:
    checks.append(("PASS", "nota5 stmt: all 2014 comparatives match warehouse2014 fact_revenue_account_statement (2014 rows)", len(prev), len(prev), 0))
checks.append(("INFO", "nota5 stmt: 54 cells (RM+pct) eye-read from crops/p066_s*.png; all RM columns confirmed by footing/chain arithmetic; '**' footnote = Tidak termasuk pindahan ke Kumpulan Wang Pembangunan", 54, None, None))
append_checks(checks)
n = sum(1 for c in checks if c[0] == "FAIL")
print(f"nota5 stmt: {len(checks)} checks appended, {n} FAIL")
