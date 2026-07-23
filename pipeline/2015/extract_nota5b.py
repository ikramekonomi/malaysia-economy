#!/usr/bin/env python3
"""Nota 5(b) Perbelanjaan Mengurus mengikut Maksud (PKKP 2015, pdf 68, printed 54).

50 maksud: T.01-T.14 + 36 B votes (B.64 Kementerian Pendidikan Tinggi is NEW in
2015 -- education split B.63/B.64; B.41 Pelajaran of 2014 gone). B.12 sebenar
carries '**' (caruman ke Kumpulan Wang Pembangunan RM2,091,232,319 inside --
footnote value cross-tied to Nota 5 Pindahan row by validate.py).
Values EYE-TYPED from 400-dpi crops (p068_a/b/c.png) -- this volume has no text
layer; the page-level OCR was used only for locating the table. Column sums +
pct identities verified below; every check row appended to the validation CSV.
"""
import csv
import sys

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
from ocrlib import SRC, parse_amount, append_checks

OUT = "/home/claude/pkkp/warehouse2015/fact_opex_maksud.csv"
STMT = "Nota 5(b) Perbelanjaan Mengurus"
PDF_PAGE, PRINTED = 68, 54

# code, name, asal, dipinda, sebenar, pct   ('**' prefix -> footnote)
SPEC = [
    ("T.01", "Peruntukan Diraja Bagi S.P.B. Yang Di-Pertuan Agong", "13,533,000", "13,533,000", "13,532,940", "99.99"),
    ("T.02", "Elaun-elaun Diraja", "1,813,100", "1,813,100", "1,494,098", "82.41"),
    ("T.03", "Ketua Hakim Negara, Hakim Besar dan Hakim", "90,000,000", "84,500,000", "82,896,157", "98.10"),
    ("T.04", "Ketua Audit Negara", "1,254,000", "1,254,000", "598,674", "47.74"),
    ("T.05", "Yang Dipertua Dewan Rakyat", "1,320,000", "1,627,000", "1,582,746", "97.28"),
    ("T.06", "Yang Dipertua Dewan Negara", "1,260,000", "1,536,000", "1,532,070", "99.74"),
    ("T.07", "Suruhanjaya Pilihan Raya", "1,420,000", "1,739,000", "1,738,731", "99.98"),
    ("T.08", "Suruhanjaya Perkhidmatan Perundangan", "50,000", "40,000", "31,880", "79.70"),
    ("T.09", "Suruhanjaya Perkhidmatan Awam", "10,650,000", "5,850,000", "5,193,631", "88.78"),
    ("T.10", "Suruhanjaya Perkhidmatan Pelajaran", "3,935,800", "3,935,800", "3,596,456", "91.38"),
    ("T.11", "Suruhanjaya Pasukan Polis", "1,454,700", "1,454,700", "1,440,939", "99.05"),
    ("T.12", "Perbendaharaan", "6,302,328,400", "5,428,007,987", "5,393,219,018", "99.36"),
    ("T.13", "Perbelanjaan Kerana Hutang Negara", "24,379,250,000", "24,379,250,000", "24,283,376,224", "99.61"),
    ("T.14", "Pencen, Elaun Bersara dan Ganjaran", "15,700,000,000", "17,986,607,146", "17,986,096,719", "99.99"),
    ("JUMLAH_T", "Jumlah Perbelanjaan Tanggungan", "46,508,269,000", "47,911,147,733", "47,776,330,283", "99.72"),
    ("B.01", "Parlimen", "89,132,000", "130,132,000", "130,131,991", "99.99"),
    ("B.02", "Pejabat Penyimpan Mohor Besar Raja-Raja", "2,294,000", "1,939,631", "1,787,756", "92.17"),
    ("B.03", "Jabatan Audit Negara", "164,670,000", "157,307,742", "154,335,518", "98.11"),
    ("B.04", "Suruhanjaya Pilihan Raya", "73,852,000", "72,352,000", "71,402,636", "98.69"),
    ("B.05", "Suruhanjaya Perkhidmatan Awam", "50,622,000", "49,800,632", "49,430,001", "99.26"),
    ("B.06", "Jabatan Perdana Menteri", "6,025,239,000", "5,845,878,097", "5,841,982,204", "99.93"),
    ("B.07", "Jabatan Perkhidmatan Awam", "2,670,130,000", "2,670,130,000", "2,670,129,914", "99.99"),
    ("B.08", "Jabatan Peguam Negara", "202,200,000", "183,668,590", "179,693,758", "97.84"),
    ("B.09", "Suruhanjaya Pencegahan Rasuah Malaysia", "294,326,800", "267,068,001", "265,065,787", "99.25"),
    ("B.10", "Perbendaharaan", "3,427,324,900", "3,427,324,900", "3,373,591,021", "98.43"),
    ("B.11", "Perkhidmatan Am Perbendaharaan", "32,815,826,300", "31,942,654,980", "27,485,770,991", "86.05"),
    ("B.12", "Peruntukan kepada Kumpulan Wang Terkanun", "2,053,800,100", "2,138,100,100", "**4,226,102,854", "197.66"),
    ("B.13", "Kementerian Luar Negeri", "761,833,000", "750,635,234", "808,322,840", "107.69"),
    ("B.20", "Kementerian Perusahaan Perladangan dan Komoditi", "1,237,800,000", "1,166,200,000", "1,161,679,534", "99.61"),
    ("B.21", "Kementerian Pertanian dan Industri Asas Tani", "4,284,289,300", "3,979,176,500", "3,954,495,609", "99.38"),
    ("B.22", "Kementerian Kemajuan Luar Bandar dan Wilayah", "5,982,302,200", "5,963,002,200", "5,945,202,478", "99.70"),
    ("B.23", "Kementerian Sumber Asli dan Alam Sekitar", "1,101,875,500", "1,074,724,800", "1,074,539,035", "99.98"),
    ("B.24", "Kementerian Perdagangan Antarabangsa dan Industri", "586,658,500", "515,847,400", "507,421,780", "98.37"),
    ("B.25", "Kementerian Perdagangan Dalam Negeri, Koperasi dan Kepenggunaan", "947,029,000", "874,464,004", "871,046,601", "99.61"),
    ("B.27", "Kementerian Kerja Raya", "2,112,630,000", "1,821,614,240", "1,821,614,117", "99.99"),
    ("B.28", "Kementerian Pengangkutan", "1,256,217,900", "1,311,057,521", "1,311,057,445", "99.99"),
    ("B.29", "Kementerian Tenaga, Teknologi Hijau dan Air", "280,970,000", "246,181,514", "246,180,514", "99.99"),
    ("B.30", "Kementerian Sains, Teknologi dan Inovasi", "727,057,500", "699,602,300", "695,269,139", "99.38"),
    ("B.31", "Kementerian Pelancongan dan Kebudayaan", "1,187,592,000", "1,158,122,800", "1,149,410,251", "99.25"),
    ("B.32", "Kementerian Wilayah Persekutuan", "427,375,600", "343,888,170", "340,552,831", "99.03"),
    ("B.40", "Suruhanjaya Perkhidmatan Pelajaran", "16,629,400", "15,898,461", "15,610,235", "98.19"),
    ("B.42", "Kementerian Kesihatan", "21,714,210,000", "21,714,210,000", "21,714,209,921", "99.99"),
    ("B.43", "Kementerian Kesejahteraan Bandar, Perumahan dan Kerajaan Tempatan", "2,556,521,800", "3,131,994,850", "3,131,994,802", "99.99"),
    ("B.45", "Kementerian Belia dan Sukan", "534,835,000", "523,780,600", "523,780,573", "99.99"),
    ("B.46", "Kementerian Sumber Manusia", "801,770,000", "793,681,200", "793,582,166", "99.99"),
    ("B.47", "Kementerian Komunikasi dan Multimedia", "1,385,097,900", "1,280,831,900", "1,254,766,214", "97.96"),
    ("B.48", "Kementerian Pembangunan Wanita, Keluarga dan Masyarakat", "2,044,623,400", "1,979,550,509", "1,969,965,484", "99.52"),
    ("B.60", "Kementerian Pertahanan", "14,144,796,800", "13,397,780,828", "13,397,774,532", "99.99"),
    ("B.62", "Kementerian Dalam Negeri", "12,611,150,000", "12,604,057,000", "12,604,053,489", "99.99"),
    ("B.63", "Kementerian Pendidikan Malaysia", "39,211,432,000", "39,336,432,000", "39,336,431,952", "99.99"),
    ("B.64", "Kementerian Pendidikan Tinggi", "13,147,617,100", "12,246,523,861", "12,234,044,570", "99.99"),
    ("JUMLAH_B", "Jumlah Perbelanjaan Bekalan", "176,931,731,000", "173,815,614,565", "171,312,430,543", "98.56"),
    # grand sebenar eye-verified at 3x zoom (p068_zoom.png): 219,088,760,826
    # (page-level OCR misread the thousands '8' as '3')
    ("JUMLAH", "JUMLAH PERBELANJAAN MENGURUS", "223,440,000,000", "221,726,762,298", "219,088,760,826", "98.81"),
]

rows, checks = [], []
sums = {"T": [0.0] * 3, "B": [0.0] * 3}
printed_totals = {}
for code, name, asal, dip, seb, pct in SPEC:
    foot = "*" in seb
    a, d, s, p = parse_amount(asal), parse_amount(dip), parse_amount(seb), parse_amount(pct)
    if code.startswith("JUMLAH"):
        printed_totals[code] = (a, d, s, p)
        continue
    jenis = "Tanggungan" if code.startswith("T") else "Bekalan"
    for i, v in enumerate((a, d, s)):
        sums[code[0]][i] += v
    rows.append([code, jenis, name, 2015, a, d, s, p, foot, SRC, PDF_PAGE, PRINTED, STMT])
    # pct identity
    exp = round(s / d * 100, 2) if d else None
    if exp is not None and abs(exp - p) > 0.011:
        if code == "B.64":
            checks.append(("WARN", "nota5b: B.64 printed pct 99.99 but sebenar/dipinda*100 = 99.90 "
                           "(pct eye-verified as printed 99.99 at 3x zoom; RM columns confirmed by column sums; "
                           "PRINT-SIDE anomaly kept as printed)", exp, p, round(exp - p, 2)))
        else:
            checks.append(("FAIL", f"nota5b: {code} pct identity sebenar/dipinda*100", exp, p, round(exp - p, 2)))

for key, jl in (("T", "JUMLAH_T"), ("B", "JUMLAH_B")):
    for i, colname in enumerate(("asal", "dipinda", "sebenar")):
        got, want = sums[key][i], printed_totals[jl][i]
        st = "PASS" if abs(got - want) < 0.5 else "FAIL"
        checks.append((st, f"nota5b: sum {key}-votes {colname} vs printed Jumlah", got, want, got - want))
for i, colname in enumerate(("asal", "dipinda", "sebenar")):
    got = printed_totals["JUMLAH_T"][i] + printed_totals["JUMLAH_B"][i]
    want = printed_totals["JUMLAH"][i]
    st = "PASS" if abs(got - want) < 0.5 else "FAIL"
    checks.append((st, f"nota5b: Jumlah T + Jumlah B {colname} vs JUMLAH PERBELANJAAN MENGURUS", got, want, got - want))

# grand-total rows are stored too (as in warehouse2014: 49 rows = 14 T + 35 B... 2014
# stored ONLY the votes; keep votes-only for schema parity)
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["maksud_code", "jenis_bm", "maksud_name_bm", "year", "anggaran_asal_rm",
                "anggaran_dipinda_rm", "sebenar_rm", "pct_anggaran", "has_footnote",
                "source_file", "pdf_page", "printed_page", "statement"])
    w.writerows(rows)

checks.append(("INFO", "nota5b: values eye-typed from 400-dpi crops (no text layer); "
               "B.12 ** footnote caruman ke KW Pembangunan RM2,091,232,319", len(rows), "", ""))
append_checks(checks)
print(f"fact_opex_maksud.csv: {len(rows)} rows")
for c in checks:
    print(c)
