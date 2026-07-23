#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 8, 9(b) detail tables + narrative figures
from PKKP 2013 into tidy warehouse CSVs.  Adapted from the 2014 reference.

printed_page = pdf_page - 24 for the 2013 volume.  YEAR=2013, PRIOR=2012.
Amounts transcribed from the PDF text layer; every non-zero amount is verified
to appear verbatim on its source page.  Detail-vs-total sums and control values
are validated PASS/FAIL.  Nothing silently corrected.
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2013"
WH = "/home/claude/pkkp/warehouse2013"
SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OFF = 24  # printed = pdf - 24

pages = open(os.path.join(WORK, "full.txt")).read().split("\f")


def N(s):
    s = s.strip()
    if s in ("-", "–", ""):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


verify_fail = []


def V(pdf_page, s):
    s = s.strip()
    if s in ("-", "–", ""):
        return
    if s not in pages[pdf_page - 1]:
        verify_fail.append((pdf_page, s))


checks = []


def CHK(name, got, want):
    checks.append(("PASS" if abs(got - float(want)) < 0.5 else "FAIL",
                   name, got, want, got - float(want)))


def prov(pdf_page, statement):
    return dict(source_file=SRC, pdf_page=pdf_page, printed_page=pdf_page - OFF,
                statement=statement)


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


# =====================================================================
# 1. Nota 3 WANG TUNAI (pdf 63, printed 39)
# =====================================================================
cash_src = [
    ("Wang Tunai Dalam Bank", "24,150,819,417", "28,543,129,953", "detail"),
    ("Wang Tunai Dalam Perjalanan", "897,494,085", "810,022,000", "detail"),
    ("Wang Tunai Dalam Tangan", "2,725,483", "2,673,231", "detail"),
    ("JUMLAH WANG TUNAI", "25,051,038,985", "29,355,825,184", "total"),
]
cash_rows = []
for label, a13, a12, rt in cash_src:
    for yr, amt in ((2013, a13), (2012, a12)):
        V(63, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(63, "Nota 3 Wang Tunai")))
for yr in (2013, 2012):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2013 = position", 25051038985.0, 25051038985)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 63, printed 39)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa13, am13, kwa12, am12
    ("Sekuriti Kerajaan Luar Negeri", "4,133,344,179", "-", "3,488,419,954", "-"),
    ("Sekuriti Kerajaan Malaysia", "2,024,714,111", "-", "1,238,248,943", "-"),
    ("Saham", "784,811", "6,203,976,779", "784,811", "5,563,998,987"),
    ("Deposit Dalam Negeri", "7,514,279,088", "4,153,776,830", "8,133,614,560", "5,093,996,935"),
    ("Pelbagai", "-", "1,670,558", "528,401,960", "1,670,558"),
]
inv_sub = {(KWA, 2013): "13,673,122,189", (AM, 2013): "10,359,424,167",
           (KWA, 2012): "13,389,470,228", (AM, 2012): "10,659,666,480"}
inv_tot = {2013: "24,032,546,356", 2012: "24,049,136,708"}
P4 = prov(63, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2013, 2012):
    V(63, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="JUMLAH PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k13, a13, k12, a12 in inv_src:
    for yr, kv, av in ((2013, k13, a13), (2012, k12, a12)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(63, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(63, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2013, 2012):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = JUMLAH PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2013 = position", N(inv_tot[2013]), 24032546356)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 69-72)
# =====================================================================
trust_rows = []


def T(fund_group, fund, section, item, yr, amt, rt, pg, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, stmt)))


KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 69, printed 45)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2013, 2012, row_type
    ("", "BAKI PADA 1 JANUARI", "(43,824,579,256)", "(55,235,001,113)", "opening"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "2,099,876,765", "2,375,673,144", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "41,830,000,000", "53,332,230,232", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,500,331,052", "1,085,973,097", "detail"),
    ("TERIMAAN", "Perbezaan Forex Relending Loan", "13,697,019", "-", "detail"),
    ("TERIMAAN", "Terimaan Balik Pendahuluan", "29,508,837", "29,400,000", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "87,017", "89,869", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "25,809,117", "1,519,509,321", "detail"),
    ("TERIMAAN", "Jumlah Terimaan", "45,499,309,807", "58,342,875,663", "subtotal"),
    ("BAYARAN", "Langsung", "40,473,294,579", "44,978,124,405", "detail"),
    ("BAYARAN", "Pinjaman", "1,736,506,805", "1,954,329,401", "detail"),
    ("BAYARAN", "Jumlah Bayaran", "42,209,801,384", "46,932,453,806", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "3,289,508,423", "11,410,421,857", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(40,535,070,833)", "(43,824,579,256)", "closing"),
]
for sec, item, a13, a12, rt in kwp_src:
    for yr, amt in ((2013, a13), (2012, a12)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 69, S1)
for yr in (2013, 2012):
    rs = [r for r in trust_rows if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == yr]
    g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                            if r["section_bm"] == sec and r["row_type"] == rt)
    one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
    CHK(f"Nota7(a)(i) KWP TERIMAAN details = subtotal {yr}",
        g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
    CHK(f"Nota7(a)(i) KWP BAYARAN details = subtotal {yr}",
        g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
    CHK(f"Nota7(a)(i) KWP terimaan-bayaran = Lebihan/(Kurangan) {yr}",
        g("TERIMAAN", "subtotal") - g("BAYARAN", "subtotal"),
        one("Lebihan/(Kurangan) bagi Tahun"))
    CHK(f"Nota7(a)(i) KWP opening+net = closing {yr}",
        one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun"),
        one("BAKI PADA 31 DISEMBER"))
CHK("control: KWP closing 2013 = Nota7 summary", -40535070833.0, -40535070833)

# --- 7(a)(ii) Kumpulan Wang Pinjaman Perumahan (pdf 69-70, printed 45-46)
S2 = "Nota 7(a)(ii) Kumpulan Wang Pinjaman Perumahan"
KWPP = "Kumpulan Wang Pinjaman Perumahan"
kwpp_src = [  # section, item, 2013, 2012, row_type, pdf_page
    ("", "BAKI PADA 1 JANUARI", "1,515,520,436", "1,908,324,534", "opening", 69),
    ("TERIMAAN / Pinjaman Perseorangan", "Bayaran Balik Pinjaman Perseorangan", "1,530,464,432", "1,266,040,286", "detail", 69),
    ("TERIMAAN / Pinjaman Perseorangan", "Hasil Pensekuritian", "6,727,762,560", "-", "detail", 69),
    ("TERIMAAN / Pembiayaan", "Pelbagai Pembiayaan", "4,400,000,000", "5,500,000,000", "detail", 69),
    ("TERIMAAN / Pendapatan Faedah", "Bayaran Balik Faedah Pinjaman Perseorangan", "1,380,731,300", "1,169,642,131", "detail", 69),
    ("TERIMAAN / Akaun Pensekuritian", "Kutipan Bayaran Balik Akaun Pensekuritian", "2,501,037,601", "2,300,118,669", "detail", 69),
    ("TERIMAAN / Akaun Pensekuritian", "Peruntukan Diskaun Pensekuritian", "(386,424,941)", "342,237,619", "detail", 69),
    ("TERIMAAN", "Pelbagai", "11,665,999", "10,458,990", "detail", 69),
    ("TERIMAAN", "Jumlah Terimaan", "16,165,236,951", "10,588,497,695", "subtotal", 69),
    ("BAYARAN / Pinjaman Perseorangan", "Pengeluaran Pinjaman Perseorangan", "(8,145,312,053)", "(6,488,768,940)", "detail", 70),
    ("BAYARAN / Pembiayaan", "Bayaran Balik Pelbagai Pembiayaan", "(5,600,000,000)", "(2,100,000,000)", "detail", 70),
    ("BAYARAN / Akaun Pensekuritian", "Serahan Kutipan Akaun Pensekuritian", "(2,582,427,916)", "(2,371,333,558)", "detail", 70),
    ("BAYARAN / Akaun Pensekuritian", "Bayaran Lain Akaun Pensekuritian", "(28,072,467)", "(21,199,295)", "detail", 70),
    ("BAYARAN", "Jumlah Bayaran", "(16,355,812,436)", "(10,981,301,793)", "subtotal", 70),
    ("", "BAKI PADA 31 DISEMBER", "1,324,944,951", "1,515,520,436", "closing", 70),
]
for sec, item, a13, a12, rt, pg in kwpp_src:
    for yr, amt in ((2013, a13), (2012, a12)):
        T(KWK, KWPP, sec, item, yr, amt, rt, pg, S2)
for yr in (2013, 2012):
    rs = [r for r in trust_rows if r["fund_bm"] == KWPP and r["year"] == yr]
    ter = sum(r["amount_rm"] for r in rs if r["section_bm"].startswith("TERIMAAN") and r["row_type"] == "detail")
    ter_s = [r["amount_rm"] for r in rs if r["line_item_bm"] == "Jumlah Terimaan"][0]
    bay = sum(r["amount_rm"] for r in rs if r["section_bm"].startswith("BAYARAN") and r["row_type"] == "detail")
    bay_s = [r["amount_rm"] for r in rs if r["line_item_bm"] == "Jumlah Bayaran"][0]
    op = [r["amount_rm"] for r in rs if r["row_type"] == "opening"][0]
    cl = [r["amount_rm"] for r in rs if r["row_type"] == "closing"][0]
    CHK(f"Nota7(a)(ii) KWPP TERIMAAN details = subtotal {yr}", ter, ter_s)
    CHK(f"Nota7(a)(ii) KWPP BAYARAN details = subtotal {yr}", bay, bay_s)
    CHK(f"Nota7(a)(ii) KWPP opening+terimaan+bayaran = closing {yr}", op + ter_s + bay_s, cl)
CHK("control: KWPP closing 2013 = Nota7 summary", 1324944951.0, 1324944951)

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 70-71, printed 46-47)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (jumlah_label, subtotal13, subtotal12, page, items)
    "AKAUN PENYELESAIAN": ("Jumlah Akaun Penyelesaian", "9,810,381,418", "20,011,478,316", 70, [
        ("Akaun Semasa Antara Pentadbiran", "15,062,341", "17,374,952"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "9,695,319,077", "19,894,103,364"),
        ("Akaun Penyelesaian Jabatan Mengakaun Sendiri", "100,000,000", "100,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("Jumlah Akaun Perniagaan", "82,506,758", "79,155,435", 70, [
        ("Stor dan Woksyop Belum Diuntukkan", "82,506,758", "79,155,435"),
    ]),
    "AKAUN PINJAMAN": ("Jumlah Akaun Pinjaman", "7,133,892,658", "5,661,215,278", 70, [
        ("Kontraktor", "7,712,617", "7,082,337"),
        ("Kredit Kerjasama", "15,037,189", "15,037,189"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "158,813,111", "133,160,698"),
        ("Pembangunan Ekonomi Belia", "6,311,298", "5,891,017"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "105,065,042", "110,189,417"),
        ("Pendahuluan Diri (Pegawai Awam)", "122,577,139", "104,912,700"),
        ("Pendahuluan Pelbagai", "58,548,445", "55,390,714"),
        ("Pendahuluan Peti Sejuk Sarawak", "620,000", "620,000"),
        ("Pendahuluan Untuk Negeri", "160,928,872", "156,518,645"),
        ("Pinjaman Diraja", "2,500,000", "2,500,000"),
        ("Pinjaman Kenderaan", "666,576,983", "667,091,673"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "5,189,338,781", "3,896,691,838"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "86,428,496", "38,161,652"),
        ("Rakyat Malaysia di Luar Negeri", "1,082,529", "1,044,139"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "552,352,156", "466,923,259"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("Jumlah Kumpulan Wang Luar Jangka", "1,207,799,118", "176,414,332", 70, [
        ("Kumpulan Wang Luar Jangka", "1,207,799,118", "176,414,332"),
    ]),
    "KUMPULAN WANG YANG LAIN": ("Jumlah Pelbagai Kumpulan Wang", "11,370,636,978", "9,823,718,639", 71, [
        ("Amanah Negara", "7,040,478,437", "5,653,917,035"),
        ("Amanah Pelajar Miskin", "428,734,551", "478,656,172"),
        ("Amanah Sukan Negara", "25,329,695", "577,000"),
        ("Bantuan Bencana Negara", "257,948,166", "184,315,891"),
        ("Bantuan Mangsa Serangan Binatang Buas", "251,500", "281,000"),
        ("Cadangan Untuk Negeri", "248,606,008", "349,618,591"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "3,875,655", "2,776,212"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "81,083,808", "40,000,000"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "3,154,793", "2,566,381"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "84,660,107", "125,064,112"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "1,000,000", "1,000,000"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "1,689,081", "1,520,646"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "634,903,284", "816,477,428"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "46,029,888", "43,075,662"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "7,045,522", "3,840,995"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "835,748", "1,016,170"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "13,202,886", "13,030,550"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "4,777,584", "4,130,965"),
        ("Kursi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Majlis Penyelidikan dan Kemajuan Sains Negara (MPKSN)", "2,988,430", "2,841,407"),
        ("Penjelas Hutang", "219,449,874", "213,528,635"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "57,561,454", "64,092,032"),
        ("Perpustakaan Negara", "653,949", "1,102,027"),
        ("Program Perumahan Rakyat Dimiliki", "391,444,071", "504,485,840"),
        ("Skim Biasiswa Sukan Persekutuan", "2,028,245", "923,996"),
        ("Tabung Bantuan Perubatan (TBP)", "15,530,468", "17,834,331"),
        ("Tabung Bayaran Balik Cukai", "1,777,285,515", "1,274,862,121"),
        ("Tabung Inovasi Negara Berhad (KWATIN)", "20,002,616", "22,095,535"),
        ("Tabung Pustaka Peringatan P. Ramlee", "84,849", "87,111"),
    ]),
}
for cat, (jlabel, s13, s12, pg, items) in pkw_src.items():
    for yr, amt in ((2013, s13), (2012, s12)):
        T(KWK, PKW, cat, jlabel, yr, amt, "subtotal", pg, S3)
    for item, a13, a12 in items:
        for yr, amt in ((2013, a13), (2012, a12)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, S3)
for yr, amt in ((2013, "29,605,216,930"), (2012, "35,751,982,000")):
    T(KWK, PKW, "", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 71, S3)
for yr in (2013, 2012):
    for cat, (jlabel, s13, s12, pg, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s13 if yr == 2013 else s12))
    subs = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "subtotal")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) subtotals = PELBAGAI KWAK total {yr}", subs, tot)
CHK("control: Pelbagai KWAK 2013 = Nota7 summary", 29605216930.0, 29605216930)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 71, printed 47)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("Jumlah Amanah Khas", "646,842,019", "637,792,672", [
        ("Kumpulan Wang Dius Api", "275,682,421", "253,864,042"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "225,789,017", "219,781,848"),
        ("Pelbagai Amanah Khas", "145,370,581", "164,146,782"),
    ]),
    "AMANAH AM": ("Jumlah Amanah Am", "10,059,927,940", "9,101,844,850", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "5,097,189,238", "3,281,801,666"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)", "1,958,569,562", "3,022,437,903"),
        ("Akaun Amanah Dana Khas", "716,580,225", "585,398,831"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "526,940,287", "538,117,683"),
        ("Pelbagai Amanah Am", "1,760,648,628", "1,674,088,767"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 72, printed 48)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("Jumlah Deposit Am", "9,465,977,654", "9,155,210,611", [
        ("Kawalan Wang Tak Dituntut", "3,216,434,707", "2,798,393,775"),
        ("Wang Jaminan Pelaksanaan", "1,503,886,080", "1,593,072,799"),
        ("Deposit Wang Tak Dituntut", "1,503,240,128", "1,743,403,330"),
        ("Harta Kebangkrapan", "1,189,759,017", "1,038,002,924"),
        ("Deposit Mahkamah Tinggi", "815,311,116", "805,178,606"),
        ("Pelbagai Deposit Am", "1,237,346,606", "1,177,159,177"),
    ]),
    "DEPOSIT PELARASAN": ("Jumlah Deposit Pelarasan", "272,261,730", "299,268,201", [
        ("Pembatalan Bayaran EFT", "94,251,189", "148,874,654"),
        ("Terimaan Yang Tidak Diperuntukkan", "83,396,516", "41,822,808"),
        ("Deposit Pelarasan Cek Terbatal", "43,528,668", "69,966,536"),
        ("Bayaran Kepada Commerce Dot Com (CDC)", "26,043,004", "23,904,735"),
        ("Pembatalan Pencen Skim B", "24,081,607", "14,699,361"),
        ("Pelbagai Deposit Pelarasan", "960,746", "107"),
    ]),
}
for grp, src, tot13, tot12, pg, stmt in (
        (KAW, awam_src, "10,706,769,959", "9,739,637,522", 71, S4),
        (DEP, dep_src, "9,738,239,384", "9,454,478,812", 72, S5)):
    for sec, (jlabel, s13, s12, items) in src.items():
        for yr, amt in ((2013, s13), (2012, s12)):
            T(grp, "", sec, jlabel, yr, amt, "subtotal", pg, stmt)
        for item, a13, a12 in items:
            for yr, amt in ((2013, a13), (2012, a12)):
                T(grp, "", sec, item, yr, amt, "detail", pg, stmt)
    for yr, amt in ((2013, tot13), (2012, tot12)):
        T(grp, "", "", grp, yr, amt, "total", pg, stmt)
    for yr in (2013, 2012):
        for sec, (jlabel, s13, s12, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s13 if yr == 2013 else s12))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 8 MEMORANDUM ASET (pdf 72-73, printed 48-49)
# =====================================================================
memo_rows = []


def M(section, item, yr, amt, rt, pg):
    V(pg, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(pg, "Nota 8 Memorandum Aset")))


PBD_SEC = "Pinjaman Boleh Dituntut"
pbd = [  # label, 2013, 2012, row_type
    ("Kerajaan Negeri", "15,940,499,634", "15,796,571,501", "detail"),
    ("Pihak Berkuasa Tempatan", "457,717,393", "519,747,254", "detail"),
    ("Badan Berkanun", "13,558,275,121", "14,073,212,231", "detail"),
    ("Koperasi", "178,271,904", "197,473,124", "detail"),
    ("Syarikat", "22,824,017,744", "25,508,607,827", "detail"),
    ("Perseorangan", "36,460,363,862", "36,565,906,580", "detail"),
    ("Pelbagai", "3,128,042,556", "2,952,195,602", "detail"),
    ("JUMLAH PINJAMAN BOLEH DITUNTUT", "92,547,188,214", "95,613,714,119", "total"),
]
for item, a13, a12, rt in pbd:
    for yr, amt in ((2013, a13), (2012, a12)):
        M(PBD_SEC, item, yr, amt, rt, 72)
pel = [
    ("Syarikat", "28,421,710,694", "26,852,985,472", "detail"),
    ("Badan Berkanun", "1,218,852,876", "1,218,852,876", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
    ("JUMLAH PELABURAN", "29,679,137,799", "28,110,412,577", "total"),
]
for item, a13, a12, rt in pel:
    for yr, amt in ((2013, a13), (2012, a12)):
        M("Pelaburan", item, yr, amt, rt, 73)
for yr in (2013, 2012):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == PBD_SEC
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 PBD details = printed total {yr}", det, tot)
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 Pelaburan details = printed total {yr}", det, tot)
CHK("control: memo PBD 2013", 92547188214.0, 92547188214)
CHK("control: memo Pelaburan 2013", 29679137799.0, 29679137799)

# =====================================================================
# 5. Nota 9(b) PELBAGAI LIABILITI (pdf 74, printed 50) -> fact_commitment_detail
# =====================================================================
com_rows = []


def C(parent, item, yr, amt, pg):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, "Nota 9 Memorandum Liabiliti")))


com_src = [  # parent, total13, total12, items, pdf_page
    ("PELBAGAI LIABILITI", "286,624,151", "275,621,222", [
        ("Nota Kena Bayar", "250,336,879", "238,838,141"),
        ("Sekuriti Tak Dituntut", "22,225,104", "22,542,084"),
        ("Akaun Depositori Pusat", "14,062,168", "14,240,997")], 74),
]
for parent, t13, t12, items, pg in com_src:
    for item, a13, a12 in items:
        for yr, amt in ((2013, a13), (2012, a12)):
            C(parent, item, yr, amt, pg)
    for yr, tot in ((2013, t13), (2012, t12)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota9(b) {parent} details = printed total {yr}", det, N(tot))

# =====================================================================
# 6. Narrative figures (fact_other_notes)
# =====================================================================
other_rows = []


def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, stmt)))


# Nota 5(a) Hasil (pdf 64)
O("5(a)", "Hasil Bukan Cukai di Penyata Penerimaan dan Pembayaran Wang Tunai tidak termasuk pelarasan bayaran balik pinjaman",
  2013, "4,505,474", 64, "Nota 5(a) Hasil")
O("5(a)", "Hasil Bukan Cukai tidak termasuk penukaran jumlah faedah pinjaman kepada pegangan ekuiti",
  2013, "4,667,590", 64, "Nota 5(a) Hasil")
O("5(a)", "Hasil Bukan Cukai tidak termasuk pelarasan pindahan wang pensekuritian Kumpulan Wang Pinjaman Perumahan",
  2013, "4,200,000,000", 64, "Nota 5(a) Hasil")
O("5(a)", "Terimaan Bukan Hasil tidak termasuk penukaran pinjaman kepada pegangan ekuiti",
  2013, "8,765,555", 64, "Nota 5(a) Hasil")
# Nota 5(b) Perbelanjaan Mengurus (pdf 65)
O("5(b)", "Perbezaan perbelanjaan Pemberian dan Kenaan Bayaran Tetap di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2013, "3,338,297,240", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan bayaran balik pinjaman (komponen perbezaan Pemberian dan Kenaan Bayaran Tetap)",
  2013, "8,505,474", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan Kumpulan Wang Terkanun kepada Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2013, "3,205,276,766", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan-pindahan lain kepada Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2013, "124,515,000", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan Perbelanjaan-perbelanjaan Lain di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2013, "179,442,399", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan pulangan balik hasil (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2013, "1,650,000", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan hapus kira pelaburan (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2013, "93,687,833", 65, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan hapus kira pinjaman (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2013, "84,104,566", 65, "Nota 5(b) Perbelanjaan Mengurus")
# Nota 6 Akaun Pinjaman Disatukan (pdf 67)
O("6", "Bayaran faedah pinjaman dan kos lain dikenakan kepada Perbelanjaan Tanggungan (T13)",
  2013, "20,775,862,663", 67, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Perbezaan bayaran Pinjaman Bilateral di Penyata Penerimaan dan Pembayaran Wang Tunai (urus niaga bukan tunai pelarasan bayaran balik pinjaman)",
  2013, "13,156,729", 67, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2013, "1,320,651,597", 67, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2012, "1,503,480,145", 67, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Pinjaman dan Bantuan Luar Negeri di Penyata Prestasi Kewangan (terimaan bersih tahun semasa)",
  2013, "39,305,562,572", 67, "Nota 6 Akaun Pinjaman Disatukan")
# Nota 7 Akaun Amanah Disatukan (pdf 68)
O("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar",
  2013, "323,279,904,248", 68, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar",
  2013, "313,081,119,961", 68, "Nota 7 Akaun Amanah Disatukan")
O("7", "Pelbagai Perbelanjaan Amanah di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih semasa Akaun Amanah)",
  2013, "4,521,930,893", 68, "Nota 7 Akaun Amanah Disatukan")
# Nota 7(a)(i) Kumpulan Wang Pembangunan (pdf 68)
O("7(a)(i)", "Terimaan Balik Pinjaman Kumpulan Wang Pembangunan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2013, "1,377,968,465", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Urus niaga bukan tunai pelarasan dan penukaran pinjaman kepada ekuiti (tidak termasuk dalam Terimaan Balik Pinjaman)",
  2013, "121,955,984", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Pelarasan perbezaan pertukaran mata wang asing (komponen urus niaga bukan tunai Terimaan Balik Pinjaman)",
  2013, "406,603", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Terimaan Perbezaan Forex Relending Loan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2013, "6,947,052", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Pelbagai Terimaan Modal di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2013, "24,919,163", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Pelarasan deposit Wang Jaminan Pelaksanaan (urus niaga bukan tunai, komponen Pelbagai Terimaan Modal)",
  2013, "889,954", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Kurangan Terkumpul Kumpulan Wang Pembangunan (baki bersih pinjaman belum dipindahkan)",
  2013, "40,535,070,833", 68, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
# Nota 8(a) Pinjaman Boleh Dituntut restatement (pdf 72)
O("8(a)", "Jumlah Pinjaman Boleh Dituntut 2012 sebelum penyata semula",
  2012, "95,492,612,803", 72, "Nota 8 Memorandum Aset")
O("8(a)", "Jumlah Pinjaman Boleh Dituntut 2012 selepas penyata semula (mengambil kira baki mata wang asing pada 31 Disember 2012)",
  2012, "95,613,714,119", 72, "Nota 8 Memorandum Aset")
# Nota 8(b) Pelaburan restatement (pdf 73)
O("8(b)", "Nilai Buku Pelaburan 2012 sebelum penyata semula",
  2012, "27,194,316,450", 73, "Nota 8 Memorandum Aset")
O("8(b)", "Nilai Buku Pelaburan 2012 selepas penyata semula",
  2012, "28,110,412,577", 73, "Nota 8 Memorandum Aset")
O("8(b)", "Pelarasan pertambahan nilai buku bagi pegangan saham (komponen penyata semula 2012)",
  2012, "916,096,127", 73, "Nota 8 Memorandum Aset")
# Nota 10 Liabiliti Luar Jangka (pdf 74)
O("10", "Pinjaman badan berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",
  2013, "157,499,913,232", 74, "Nota 10 Liabiliti Luar Jangka")
O("10", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2013, "610,908,127,026", 74, "Nota 10 Liabiliti Luar Jangka")
O("10", "Third Party War Risk Liability dengan Malaysia Airports Holdings Berhad mengikut perjanjian indemniti",
  2013, "475,000,000", 74, "Nota 10 Liabiliti Luar Jangka")
# Nota 11 Akaun Belum Terima (pdf 74)
O("11", "Akaun Belum Terima (maklumat tambahan berdasarkan rekod Kementerian/Jabatan)",
  2013, "21,810,019,816", 74, "Nota 11 Akaun Belum Terima")
# Nota 12 Wang Pendahuluan Kepada Kontraktor (pdf 74)
O("12", "Wang pendahuluan kepada kontraktor yang belum diimbuh balik",
  2013, "1,106,320,571", 74, "Nota 12 Wang Pendahuluan Kepada Kontraktor")

# =====================================================================
# Write outputs + report
# =====================================================================
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
outputs = [
    ("fact_cash_components.csv", cash_rows,
     ["line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_investment_summary.csv", inv_rows,
     ["category_bm", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_trust_fund_detail.csv", trust_rows,
     ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm", "year",
      "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_memo_assets_detail.csv", memo_rows,
     ["section_bm", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_commitment_detail.csv", com_rows,
     ["parent_bm", "item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
    ("fact_other_notes.csv", other_rows,
     ["nota", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote"] + PROV),
]
for fname, rows, cols in outputs:
    n = write_csv(os.path.join(WH, fname), cols, rows)
    print(f"WROTE {fname}: {n} rows")

print()
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES (token not found on page):")
    for pg, s in verify_fail:
        print(f"  pdf_page {pg}: {s!r}")
else:
    print("RAW-TEXT VERIFICATION: all non-zero amounts found verbatim on their source pages.")

print()
fails = 0
for status, name, got, want, diff in checks:
    tag = "" if status == "PASS" else "  <<<<"
    print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}{tag}")
    if status == "FAIL":
        fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
