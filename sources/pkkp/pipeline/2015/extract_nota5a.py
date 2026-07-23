#!/usr/bin/env python3
"""Nota 5(a) 'Hasil Mengikut Penjenisan' (PKKP 2015, pdf 66-67, printed 52-53).

GST introduction year: two new lines 'Cukai Barangan dan Perkhidmatan Import'
and 'Cukai Barangan dan Perkhidmatan Tempatan' (2014 comparative prints '-');
the pre-GST Cukai Jualan / Cukai Perkhidmatan lines still carry Jan-Mar 2015
collections. Labels typed exactly as printed (wrapped names joined).
Columns: Anggaran Asal | Anggaran Disemak | Sebenar | %Anggaran | 2014 Sebenar
| 2014 %Anggaran. Schema/level/row conventions copied from warehouse2014
fact_revenue.csv (level 3 detail / 1 category subtotal / 0 JUMLAH HASIL).
NO text layer -- every value EYE-READ from crops/p066_a[01].png and
crops/p067_a[0-3].png, p067_jh.png (scale 2). Nothing silently corrected.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocrlib import SRC, YEAR, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015/fact_revenue.csv"
STMT = "Nota 5(a) Hasil Mengikut Penjenisan"
checks = []


def N(s):
    if s in ("-", "–", ""):
        return None if s == "" else 0.0
    return parse_amount(s)


# cat, item, asal, disemak, sebenar, pct, prior, pct_prior, pdf_page
D = [
    ("HASIL CUKAI", "Cukai Pendapatan", "127,391,847,000", "108,361,781,000", "103,985,416,377", "95.96", "118,995,547,439", "95.02", 66),
    ("HASIL CUKAI", "Cukai Langsung yang Lain", "8,011,136,000", "8,397,828,000", "7,784,904,264", "92.70", "7,746,944,723", "97.89", 66),
    ("HASIL CUKAI", "Duti Kastam - Eksport", "2,230,545,000", "1,052,653,000", "1,039,192,023", "98.72", "1,892,894,533", "89.91", 66),
    ("HASIL CUKAI", "Duti Kastam - Import", "2,629,173,000", "2,727,121,000", "2,731,766,954", "100.17", "2,669,683,046", "106.71", 66),
    ("HASIL CUKAI", "Duti Eksais", "9,388,939,000", "8,030,936,000", "7,999,148,934", "99.60", "8,456,105,401", "91.90", 66),
    ("HASIL CUKAI", "Cukai Jualan atas Barang-barang Perkilangan Dalam Negeri", "1,556,001,000", "2,980,857,000", "3,207,057,042", "107.59", "6,130,394,771", "98.22", 66),
    ("HASIL CUKAI", "Cukai Jualan atas Barangan Import", "1,178,057,000", "1,803,143,000", "2,015,954,706", "111.80", "4,808,996,229", "101.37", 66),
    ("HASIL CUKAI", "Cukai Perkhidmatan", "1,874,036,000", "2,850,999,000", "3,038,230,278", "106.57", "6,277,600,117", "92.60", 66),
    ("HASIL CUKAI", "Levi", "150,000,000", "150,000,000", "164,147,955", "109.43", "216,318,553", "120.18", 66),
    ("HASIL CUKAI", "Duti Eksais Terhadap Barangan Import", "4,327,991,000", "4,137,148,000", "3,890,691,272", "94.04", "4,468,395,725", "105.35", 67),
    ("HASIL CUKAI", "Pelbagai Cukai Tidak Langsung", "2,677,000,000", "2,524,819,000", "2,571,791,852", "101.86", "2,542,007,052", "96.75", 67),
    ("HASIL CUKAI", "Cukai Barangan dan Perkhidmatan Import", "3,463,146,000", "13,155,000,000", "12,972,704,469", "98.61", "-", "-", 67),
    ("HASIL CUKAI", "Cukai Barangan dan Perkhidmatan Tempatan", "18,256,854,000", "13,845,000,000", "14,039,645,646", "101.41", "-", "-", 67),
    ("JUMLAH:HASIL CUKAI", "Jumlah Hasil Cukai", "183,134,725,000", "170,017,285,000", "165,440,651,772", "97.31", "164,204,887,589", "95.60", 67),
    ("HASIL BUKAN CUKAI", "Lesen, Bayaran Pendaftaran dan Permit", "13,142,829,000", "12,459,908,000", "12,539,757,409", "100.64", "14,253,820,028", "109.23", 67),
    ("HASIL BUKAN CUKAI", "Perkhidmatan dan Bayaran Perkhidmatan", "1,303,790,000", "1,434,718,000", "1,536,620,025", "107.10", "1,452,480,156", "117.84", 67),
    ("HASIL BUKAN CUKAI", "Perolehan daripada Jualan Barang-barang", "573,621,000", "465,343,000", "601,705,877", "129.30", "1,096,357,029", "96.24", 67),
    ("HASIL BUKAN CUKAI", "Sewaan", "249,594,000", "109,059,000", "187,461,249", "171.89", "188,097,653", "90.86", 67),
    ("HASIL BUKAN CUKAI", "Faedah dan Perolehan daripada Pelaburan", "31,193,534,000", "32,172,228,000", "32,838,054,986", "102.07", "33,755,931,743", "102.87", 67),
    ("HASIL BUKAN CUKAI", "Denda dan Hukuman", "1,136,329,000", "1,157,661,000", "1,285,033,338", "111.00", "1,117,102,950", "104.99", 67),
    ("HASIL BUKAN CUKAI", "Sumbangan dan Bayaran Ganti daripada Luar Negeri dan Sumbangan Tempatan", "3,785,000", "125,445,000", "343,443,349", "273.78", "4,363,340", "138.96", 67),
    ("HASIL BUKAN CUKAI", "Aktiviti Carigali Minyak dan Gas MTJA", "2,209,332,000", "2,170,233,000", "2,134,677,332", "98.36", "2,030,631,643", "100.72", 67),
    ("JUMLAH:HASIL BUKAN CUKAI", "Jumlah Hasil Bukan Cukai", "49,812,814,000", "50,094,595,000", "51,466,753,565", "102.74", "53,898,784,542", "104.60", 67),
    ("TERIMAAN BUKAN HASIL", "Pulangan Balik Perbelanjaan", "1,121,299,000", "1,443,734,000", "1,265,280,835", "87.64", "1,529,635,147", "148.07", 67),
    ("TERIMAAN BUKAN HASIL", "Terimaan daripada Agensi-agensi Kerajaan", "129,653,000", "29,765,000", "24,521,879", "82.38", "137,016,215", "114.71", 67),
    ("JUMLAH:TERIMAAN BUKAN HASIL", "Jumlah Terimaan Bukan Hasil", "1,250,952,000", "1,473,499,000", "1,289,802,714", "87.53", "1,666,651,362", "144.62", 67),
    ("HASIL WILAYAH PERSEKUTUAN", "Hasil Cukai Wilayah Persekutuan", "684,369,000", "787,104,000", "803,885,206", "102.13", "731,734,325", "128.90", 67),
    ("HASIL WILAYAH PERSEKUTUAN", "Hasil Bukan Cukai Wilayah Persekutuan", "93,101,000", "82,162,000", "87,667,569", "106.70", "123,615,538", "160.07", 67),
    ("JUMLAH:HASIL WILAYAH PERSEKUTUAN", "Jumlah Hasil Wilayah Persekutuan", "777,470,000", "869,266,000", "891,552,775", "102.56", "855,349,863", "132.64", 67),
    ("GRAND", "JUMLAH HASIL", "234,975,961,000", "222,454,645,000", "219,088,760,826", "98.49", "220,625,673,356", "98.01", 67),
]

rows = []
for cat, item, asal, dis, seb, pct, pri, pct_pri, pdfp in D:
    vals = [N(asal), N(dis), N(seb), N(pct), N(pri), N(pct_pri)]
    if cat == "GRAND":
        rows.append([0, None, None, "HASIL", YEAR] + vals + [SRC, pdfp, pdfp - 14, STMT])
    elif cat.startswith("JUMLAH:"):
        c = cat.split(":", 1)[1]
        rows.append([1, c, None, c, YEAR] + vals + [SRC, pdfp, pdfp - 14, STMT])
    else:
        rows.append([3, cat, None, item, YEAR] + vals + [SRC, pdfp, pdfp - 14, STMT])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
                 "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
                 "sebenar_prior_rm", "pct_anggaran_prior",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)
print(f"fact_revenue.csv: {len(rows)} rows")

# ---- identities -------------------------------------------------------------
COLS = {"asal": 5, "disemak": 6, "sebenar": 7, "sebenar_2014": 9}
cats = ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]
for cname, ci in COLS.items():
    for cat in cats:
        s = sum(r[ci] or 0 for r in rows if r[0] == 3 and r[1] == cat)
        want = next(r[ci] for r in rows if r[0] == 1 and r[1] == cat) or 0
        checks.append(("PASS" if abs(s - want) < 0.5 else "FAIL",
                       f"nota5a: {cat} item sum ({cname}) vs printed Jumlah", s, want, s - want))
    s = sum((next(r[ci] for r in rows if r[0] == 1 and r[1] == cat) or 0) for cat in cats)
    want = next(r[ci] for r in rows if r[0] == 0)
    checks.append(("PASS" if abs(s - want) < 0.5 else "FAIL",
                   f"nota5a: category totals sum ({cname}) vs printed JUMLAH HASIL", s, want, s - want))
# vs Nota 5 statement hasil lines (both years' sebenar and 2015 disemak)
n5 = {}
for r in csv.DictReader(open("/home/claude/pkkp/warehouse2015/fact_revenue_account_statement.csv", encoding="utf-8")):
    n5[(r["line_item_bm"], int(r["year"]))] = (float(r["anggaran_disemak_rm"]) if r["anggaran_disemak_rm"] else None,
                                               float(r["sebenar_rm"]) if r["sebenar_rm"] else None)
stmt_map = {"HASIL CUKAI": "Hasil Cukai", "HASIL BUKAN CUKAI": "Hasil Bukan Cukai",
            "TERIMAAN BUKAN HASIL": "Terimaan Bukan Hasil", "HASIL WILAYAH PERSEKUTUAN": "Hasil Wilayah Persekutuan"}
for cat, line in stmt_map.items():
    sub = next(r for r in rows if r[0] == 1 and r[1] == cat)
    for tag, mine, want in (("2015 sebenar", sub[7], n5[(line, 2015)][1]),
                            ("2015 anggaran disemak", sub[6], n5[(line, 2015)][0]),
                            ("2014 sebenar", sub[9], n5[(line, 2014)][1])):
        checks.append(("PASS" if abs((mine or 0) - (want or 0)) < 0.5 else "FAIL",
                       f"nota5a: Jumlah {cat} ({tag}) vs Nota 5 statement line", mine, want, (mine or 0) - (want or 0)))
grand = next(r for r in rows if r[0] == 0)
for tag, mine, want in (("2015 sebenar", grand[7], n5[("Jumlah Hasil", 2015)][1]),
                        ("2015 anggaran disemak", grand[6], n5[("Jumlah Hasil", 2015)][0]),
                        ("2014 sebenar", grand[9], n5[("Jumlah Hasil", 2014)][1])):
    checks.append(("PASS" if abs((mine or 0) - (want or 0)) < 0.5 else "FAIL",
                   f"nota5a: JUMLAH HASIL ({tag}) vs Nota 5 statement Jumlah Hasil", mine, want, (mine or 0) - (want or 0)))
# 2014 comparative columns vs 2014 volume current-year figures (label match)
prev = {}
for r in csv.DictReader(open("/home/claude/pkkp/warehouse2014/fact_revenue.csv", encoding="utf-8")):
    prev[r["item_bm"]] = (float(r["sebenar_rm"]) if r["sebenar_rm"] else None,
                          float(r["pct_anggaran"]) if r["pct_anggaran"] else None)
alias = {"Hasil Bukan Cukai Wilayah Persekutuan": "Hasil Bukan Cukai Wilayah Persekutuan",
         "Jumlah Hasil Cukai": "HASIL CUKAI", "Jumlah Hasil Bukan Cukai": "HASIL BUKAN CUKAI",
         "Jumlah Terimaan Bukan Hasil": "TERIMAAN BUKAN HASIL",
         "Jumlah Hasil Wilayah Persekutuan": "HASIL WILAYAH PERSEKUTUAN", "JUMLAH HASIL": "HASIL"}
bad = unmatched = 0
for cat, item, asal, dis, seb, pct, pri, pct_pri, pdfp in D:
    if pri in ("-", ""):
        continue
    key = alias.get(item, item)
    if key not in prev:
        unmatched += 1
        checks.append(("INFO", f"nota5a: no matching 2014-volume line for '{item}' (label changed or new)", N(pri), None, None))
        continue
    pv = prev[key][0]
    if abs(N(pri) - (pv or 0)) > 0.5:
        bad += 1
        checks.append(("WARN", f"nota5a: 2014 comparative differs from 2014 volume for {item} (restatement candidate, kept as printed)",
                       N(pri), pv, N(pri) - (pv or 0)))
if not bad:
    checks.append(("PASS", "nota5a: all printed 2014 comparatives match warehouse2014 fact_revenue (2014 sebenar)", 28 - unmatched, 28 - unmatched, 0))
checks.append(("INFO", "nota5a: GST year -- new lines 'Cukai Barangan dan Perkhidmatan Import' 12,972,704,469 / 'Cukai Barangan dan Perkhidmatan Tempatan' 14,039,645,646 (2014 comparatives '-'); labels exactly as printed", 2, None, None))
checks.append(("INFO", "nota5a: 180 cells eye-read from crops/p066_a*.png + p067_a*.png + p067_jh.png; all four RM columns confirmed by category/grand footings", 180, None, None))
append_checks(checks)
n = sum(1 for c in checks if c[0] == "FAIL")
print(f"nota5a: {len(checks)} checks appended, {n} FAIL")
