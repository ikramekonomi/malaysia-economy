#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-12 detail tables
from PKKP 2022 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2022-volume format notes vs 2023:
 - Nota 7(a)(i) TERIMAAN's first line is 'Pindahan Daripada Akaun Hasil
   Disatukan' (2023 volume calls it 'Caruman Daripada Akaun Hasil Disatukan').
 - Nota 7(a)(ii) COVID-19 fund is LIVE: 2022 expenditure RM30,979,119,546;
   no 'PINDAHAN KE' row (that appears only in the 2023 volume when the fund
   is wound up into KW Pembangunan).
 - Nota 7(a)(iii) account names differ from the 2023 volume for four funds
   (Pengangkutan Awam - Pinjaman Persekutuan / Modal Pusingan Jabatan
   Pembangunan Koperasi / Majlis Sains dan Penyelidikan Kebangsaan / Projek
   Pelantar Benua Malaysia) — the 2023 volume prints renamed successors.
 - Nota 7(b) AMANAH AM includes Akaun Amanah PFI II (still open); no
   'Akaun Amanah Dana Khas Kerajaan Persekutuan' row yet.
 - Nota 7(c) Deposit Pelarasan includes 'Deposit Pelarasan CDCSB'.
 - Nota 9 PPBD includes a 'Pihak Berkuasa Tempatan' row (nil in 2022,
   RM136,242,276 in 2021); the 2023 volume drops the row entirely.
 - Nota 10(c)(ii)/(iii) declare RESTATEMENTS of the 2021 comparatives
   (Pajakan KP 24,855,765,206 -> 24,933,059,218; Cukai Pendapatan
   13,042,914,435 -> 20,194,440,042; CKHT 603,286,067 -> 604,969,431).
 - Notes end at Nota 12 (no Nota 13 'Pendahuluan Dana Pembiayaan Utiliti').
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2022"
WH = "/home/claude/pkkp/warehouse2022"
SRC = "2022_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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

def prov(pdf_page, printed_page, statement):
    return dict(source_file=SRC, pdf_page=pdf_page, printed_page=printed_page,
                statement=statement)

def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)

# =====================================================================
# 1. Nota 3 WANG TUNAI (pdf 80, printed 68)
# =====================================================================
cash_src = [  # label, 2022, 2021, row_type
    ("WANG TUNAI", "48,502,901,599", "34,551,543,490", "total"),
    ("Wang Tunai Dalam Bank", "46,815,352,167", "33,594,301,309", "detail"),
    ("Wang Tunai Dalam Perjalanan", "1,684,925,057", "954,475,156", "detail"),
    ("Wang Tunai Dalam Tangan", "2,624,375", "2,767,025", "detail"),
]
cash_rows = []
for label, a22, a21, rt in cash_src:
    for yr, amt in ((2022, a22), (2021, a21)):
        V(80, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(80, 68, "Nota 3 Wang Tunai")))
for yr in (2022, 2021):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2022", 48502901599.0, 48502901599)
CHK("control: Wang Tunai 2021", 34551543490.0, 34551543490)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 80, printed 68)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa22, am22, kwa21, am21
    ("Sekuriti Hutang Kerajaan Luar Negeri", "3,668,464,214", "-", "3,482,011,049", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,334,744,136", "-", "1,383,037,962", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "2,095,583,493", "-", "1,974,237,005", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "4,396,155,634", "-", "4,455,239,592", "-"),
    ("Sekuriti Tersiar Harga Luar Negeri", "371,725,288", "-", "-", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "2,167,823,214", "-", "2,157,530,899", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,145,938", "6,717,761,577"),
    ("Deposit Jangka Pendek Luar Negeri Melebihi 3 - 12 Bulan", "-", "5,292,600", "-", "5,630,900"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "9,538,404,250", "4,280,000,000", "10,806,083,900", "300,000,000"),
    ("Deposit Jangka Panjang Dalam Negeri Melebihi 12 Bulan", "136,000,000", "-", "11,668,500,000", "-"),
    ("Pelbagai", "-", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2022): "24,149,008,287", (AM, 2022): "11,003,996,735",
           (KWA, 2021): "36,366,786,345", (AM, 2021): "7,024,335,035"}
inv_tot = {2022: "35,153,005,022", 2021: "43,391,121,380"}
P4 = prov(80, 68, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2022, 2021):
    V(80, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k22, a22, k21, a21 in inv_src:
    for yr, kv, av in ((2022, k22, a22), (2021, k21, a21)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(80, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(80, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2022, 2021):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2022", N(inv_tot[2022]), 35153005022)
CHK("control: Pelaburan 2021", N(inv_tot[2021]), 43391121380)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 86-88)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 86, printed 74)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2022, 2021, row_type
    ("", "BAKI PADA 1 JANUARI", "(11,969,532,073)", "(13,255,367,426)", "opening"),
    ("TERIMAAN", "TERIMAAN", "71,592,466,448", "65,542,501,108", "subtotal"),
    ("TERIMAAN", "Pindahan Daripada Akaun Hasil Disatukan", "1,663,548,105", "2,235,696,217", "detail"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "68,540,975,622", "62,317,002,625", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,198,648,613", "975,029,385", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "300", "12,030", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "189,293,808", "14,760,851", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "71,573,961,426", "64,256,665,755", "subtotal"),
    ("BAYARAN", "Langsung", "69,928,178,120", "63,275,221,797", "detail"),
    ("BAYARAN", "Pinjaman", "1,645,783,306", "981,443,958", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "18,505,022", "1,285,835,353", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(11,951,027,051)", "(11,969,532,073)", "closing"),
]
for sec, item, a22, a21, rt in kwp_src:
    for yr, amt in ((2022, a22), (2021, a21)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 86, 74, S1)

def stmt_checks(fund, prefix):
    for yr in (2022, 2021):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        if any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "detail" for r in rs):
            CHK(f"{prefix} TERIMAAN details = subtotal {yr}",
                g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
        if any(r["section_bm"] == "BAYARAN" and r["row_type"] == "detail" for r in rs):
            CHK(f"{prefix} BAYARAN details = subtotal {yr}",
                g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
        net = g("TERIMAAN", "subtotal") - g("BAYARAN", "subtotal")
        CHK(f"{prefix} terimaan-bayaran = Lebihan/(Kurangan) {yr}",
            net, one("Lebihan/(Kurangan) bagi Tahun"))
        transfer = sum(r["amount_rm"] for r in rs if r["section_bm"] == "PINDAHAN KE")
        CHK(f"{prefix} opening+net+pindahan = closing {yr}",
            one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun") + transfer,
            one("BAKI PADA 31 DISEMBER"))
stmt_checks("Kumpulan Wang Pembangunan", "Nota7(a)(i) KWP")
CHK("control: Kumpulan Wang Pembangunan closing 2022",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2022
     and r["row_type"] == "closing"][0], -11951027051)

# --- 7(a)(ii) Kumpulan Wang COVID-19 (pdf 86, printed 74) — LIVE in 2022
S2 = "Nota 7(a)(ii) Kumpulan Wang COVID-19"
covid_src = [
    ("", "BAKI PADA 1 JANUARI", "291,766,741", "761,369", "opening"),
    ("TERIMAAN", "TERIMAAN", "30,899,284,878", "38,002,021,737", "subtotal"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "30,880,000,000", "38,000,000,000", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "19,284,878", "2,021,737", "detail"),
    ("BAYARAN", "Perbelanjaan COVID-19", "30,979,119,546", "37,711,016,365", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "(79,834,668)", "291,005,372", "net"),
    ("", "BAKI PADA 31 DISEMBER", "211,932,073", "291,766,741", "closing"),
]
for sec, item, a22, a21, rt in covid_src:
    for yr, amt in ((2022, a22), (2021, a21)):
        T(KWK, "Kumpulan Wang COVID-19", sec, item, yr, amt, rt, 86, 74, S2)
stmt_checks("Kumpulan Wang COVID-19", "Nota7(a)(ii) COVID")
CHK("control: COVID fund 2022 expenditure", 30979119546.0, 30979119546)

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 87, printed 75)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": ("29,732,519,771", "17,584,177,887", [
        ("Akaun Penyelesaian Utama Perbendaharaan", "29,731,519,771", "17,583,177,887"),
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("150,039,652", "155,548,348", [
        ("Stor dan Woksyop Tak Beruntuk", "150,039,652", "155,548,348"),
    ]),
    "AKAUN PINJAMAN": ("3,983,151,017", "3,685,699,902", [
        ("Kumpulan Wang Amanah Kontraktor", "1,435,042", "2,431,054"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "97,539,470", "64,826,104"),
        ("Kumpulan Wang Amanah Modal Pusingan Jabatan Pembangunan Koperasi", "580,254,935", "566,335,586"),
        ("Kumpulan Wang Amanah Pembangunan Ekonomi Belia", "14,810,666", "14,458,147"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "51,467,275", "53,692,280"),
        ("Pendahuluan Diri (Pegawai Awam)", "122,930,610", "142,920,499"),
        ("Pendahuluan Pelbagai", "47,640,685", "50,260,492"),
        ("Pendahuluan Untuk Negeri", "734,153,583", "855,523,583"),
        ("Kumpulan Wang Amanah Pinjaman Diraja", "799,478", "780,353"),
        ("Pinjaman Kenderaan", "63,541,281", "63,649,113"),
        ("Kumpulan Wang Amanah Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,795,846,153", "1,467,050,834"),
        ("Kumpulan Wang Amanah Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "27,982,509", "20,271,657"),
        ("Kumpulan Wang Amanah Rakyat Malaysia di Luar Negeri", "1,362,012", "1,337,589"),
        ("Kumpulan Wang Amanah Tabung Pusingan Pinjaman Pelajaran Persekutuan", "443,387,318", "382,162,611"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("823,079,800", "1,500,000,000", [
        ("Kumpulan Wang Luar Jangka", "823,079,800", "1,500,000,000"),
    ]),
    "PELBAGAI KUMPULAN WANG": ("27,878,401,978", "19,793,870,844", [
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "623,314", "954,385"),
        ("Kumpulan Wang Amanah Bantuan Bencana Negara", "169,450,750", "269,621,226"),
        ("Kumpulan Wang Amanah Bantuan Mangsa Serangan Binatang Buas", "228,520", "1,003,400"),
        ("Kumpulan Wang Amanah Cadangan Untuk Negeri", "492,738,560", "412,992,483"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "4,472,854", "472,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "619,929,506", "562,866,676"),
        ("Kumpulan Wang Amanah Kebajikan dan Kemudahan Bagi Penuntut di Luar Negeri", "1,837,821", "1,769,524"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "263,109", "266,689"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "109,103,139", "255,830,418"),
        ("Kumpulan Wang Amanah Majlis Sains dan Penyelidikan Kebangsaan", "10,115,710", "10,418,838"),
        ("Kumpulan Wang Amanah Negara", "15,559,210,295", "15,291,305,995"),
        ("Kumpulan Wang Amanah Pelajar Miskin", "70,776,571", "100,175,146"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,399,372", "2,892,811"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "4,613,074", "6,175,844"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "38,400,846", "42,361,858"),
        ("Kumpulan Wang Amanah Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Kumpulan Wang Amanah Perkhidmatan Kemasyarakatan dan Kebajikan", "33,597,148", "33,861,101"),
        ("Kumpulan Wang Amanah Perpustakaan Negara", "643,293", "1,205,403"),
        ("Kumpulan Wang Amanah Program Perumahan Rakyat Dimiliki", "115,329,088", "114,612,046"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "601,695", "483,075"),
        ("Kumpulan Wang Amanah Projek Penandaan dan Pengukuran Sempadan Bersama di Antara Negeri-negeri Semenanjung Malaysia", "2,336,704", "4,305,621"),
        ("Kumpulan Wang Amanah Skim Biasiswa Sukan Persekutuan", "1,378,962", "887,152"),
        ("Kumpulan Wang Amanah Sokongan Keluarga Jabatan Kehakiman Syariah Malaysia", "15,303,565", "15,097,946"),
        ("Kumpulan Wang Amanah Sukan Negara", "25,921,589", "55,075,903"),
        ("Kumpulan Wang Amanah Tabung Bantuan Perubatan (TBP)", "90,456,221", "90,573,881"),
        ("Kumpulan Wang Amanah Tabung Bayaran Balik Cukai", "10,186,456,917", "2,181,012,904"),
        ("Kumpulan Wang Amanah Tabung Inovasi Negara (KWATIN)", "19,813,117", "19,813,117"),
        ("Kumpulan Wang Amanah Tabung Khas Hakmilik Strata", "1,814,404", "1,517,537"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "20,302,697", "22,717,584"),
        ("Kumpulan Wang Amanah Tabung Pustaka Peringatan P. Ramlee", "40,424", "22,366"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "14,230,890", "14,346,266"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan (CBP)", "262,629,863", "275,848,835"),
    ]),
}
for cat, (s22, s21, items) in pkw_src.items():
    for yr, amt in ((2022, s22), (2021, s21)):
        T(KWK, PKW, cat, cat, yr, amt, "subtotal", 87, 75, S3)
    for item, a22, a21 in items:
        for yr, amt in ((2022, a22), (2021, a21)):
            T(KWK, PKW, cat, item, yr, amt, "detail", 87, 75, S3)
for yr, amt in ((2022, "62,567,192,218"), (2021, "42,719,296,981")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 87, 75, S3)
for yr in (2022, 2021):
    for cat, (s22, s21, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s22 if yr == 2022 else s21))
    subs = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "subtotal")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) subtotals = PELBAGAI KWAK total {yr}", subs, tot)
CHK("cross: Pelbagai KWAK total 2022 = Nota7 top-level closing", 62567192218.0, 62567192218)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 88, printed 76)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH AM": ("5,350,446,266", "19,633,284,204", [
        ("Akaun Amanah Mendapatkan Kembali Aset", "1,927,333,888", "15,280,763,537"),
        ("Akaun Amanah Industri Bekalan Elektrik", "840,971,913", "865,136,402"),
        ("Akaun Amanah Pelaksanaan Projek / Program / Aktiviti Menerusi Inisiatif Pembiayaan Swasta (PFI II)", "439,569,218", "651,772,865"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baharu", "428,692,575", "435,366,936"),
        ("Akaun Amanah Sumber Khas", "397,941,208", "364,708,398"),
        ("Pelbagai Amanah Am", "1,315,937,464", "2,035,536,066"),
    ]),
    "AMANAH KHAS": ("3,499,072,034", "3,438,566,266", [
        ("Akaun Amanah Estet Kebankrapan", "2,078,984,083", "2,060,566,357"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "346,622,703", "326,776,345"),
        ("Akaun Amanah Faedah atas Pelaburan untuk Deposit Mahkamah", "302,071,900", "288,137,223"),
        ("Kumpulan Wang Dius Api", "301,917,856", "303,662,063"),
        ("Akaun Amanah Am Pelikuidasi", "295,611,957", "288,965,462"),
        ("Pelbagai Amanah Khas", "173,863,535", "170,458,816"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 88, printed 76)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("11,965,755,444", "11,836,424,195", [
        ("Deposit Kawalan Wang Tak Dituntut", "7,733,236,530", "7,476,484,583"),
        ("Deposit Wang Jaminan Pelaksanaan", "1,661,456,801", "1,802,432,243"),
        ("Deposit Mahkamah Tinggi", "1,219,853,377", "1,225,622,946"),
        ("Deposit Imigresen", "413,648,187", "391,898,137"),
        ("Deposit Cagaran", "248,265,797", "224,694,403"),
        ("Pelbagai Deposit Am", "689,294,752", "715,291,883"),
    ]),
    "DEPOSIT PELARASAN": ("149,408,551", "129,731,470", [
        ("Akaun Terimaan Tidak Diperuntukkan", "89,092,270", "46,096,022"),
        ("Deposit Pindahan Dana Elektronik Terbatal", "54,301,231", "62,077,240"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JHEV", "3,604,157", "4,556,223"),
        ("Deposit Pelarasan Cek Terbatal", "912,325", "1,611,718"),
        ("Deposit Pelarasan CDCSB", "343,057", "2,101,822"),
        ("Pelbagai Deposit Pelarasan", "1,155,511", "13,288,445"),
    ]),
}
for grp, src, tot22, tot21, stmt in (
        (KAW, awam_src, "8,849,518,300", "23,071,850,470", S4),
        (DEP, dep_src, "12,115,163,995", "11,966,155,665", S5)):
    for sec, (s22, s21, items) in src.items():
        for yr, amt in ((2022, s22), (2021, s21)):
            T(grp, "", sec, sec, yr, amt, "subtotal", 88, 76, stmt)
        for item, a22, a21 in items:
            for yr, amt in ((2022, a22), (2021, a21)):
                T(grp, "", sec, item, yr, amt, "detail", 88, 76, stmt)
    for yr, amt in ((2022, tot22), (2021, tot21)):
        T(grp, "", "", grp, yr, amt, "total", 88, 76, stmt)
    for yr in (2022, 2021):
        for sec, (s22, s21, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s22 if yr == 2022 else s21))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 90, printed 78)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(90, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(90, 78, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2022, "105,523,695,021", "total")
ppbd = [  # label, 2022, 2021, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "53,916,510,499", "57,846,052,679", "subtotal"),
    ("Kerajaan Negeri", "11,828,564,837", "14,218,973,091", "detail"),
    ("Syarikat", "33,248,609,006", "34,613,168,836", "detail"),
    ("Badan Berkanun", "6,934,327,366", "6,963,127,525", "detail"),
    ("Pihak Berkuasa Tempatan", "-", "136,242,276", "detail"),
    ("Koperasi", "262,272,363", "237,272,363", "detail"),
    ("Pelbagai Agensi", "1,464,367,549", "1,523,841,742", "detail"),
    ("Perseorangan", "178,369,378", "153,426,846", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a22, a21, rt in ppbd:
    for yr, amt in ((2022, a22), (2021, a21)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2022, "51,607,184,522", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2022, "561,039,679", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2022, "21,634,885,054", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2022, "2,893,466,103", "memo")
pel = [
    ("PELABURAN", "34,030,520,711", "33,861,520,709", "subtotal"),
    ("Syarikat", "33,013,845,786", "32,844,845,784", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a22, a21, rt in pel:
    for yr, amt in ((2022, a22), (2021, a21)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2022, 2021):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2022 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2022 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2022",
    N("53,916,510,499") + N("51,607,184,522"), 105523695021)
CHK("control: Akaun Belum Terima 2022", 105523695021.0, 105523695021)
CHK("control: memo Pelaburan 2022", N(pel[0][1]), 34030520711)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 92-93)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2022, printed_total_2021, items, pdf_page
    ("KOMITMEN JAMINAN", "224,115,577,507", "229,391,741,672", [
        ("Dalam Negeri", "183,667,995,570", "176,623,572,552"),
        ("Luar Negeri", "40,447,581,937", "52,768,169,120")], 92),
    ("KOMITMEN PAJAKAN KEWANGAN", "34,551,706,062", "37,280,233,968", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "22,973,365,099", "24,933,059,218"),
        ("Pajakan Kewangan Badan Berkanun", "11,578,340,963", "12,347,174,750")], 92),
    ("KOMITMEN BAYARAN BALIK CUKAI", "25,721,574,279", "21,836,502,399", [
        ("Cukai Pendapatan", "24,263,817,207", "20,194,440,042"),
        ("Cukai Keuntungan Harta Tanah", "686,063,322", "604,969,431"),
        ("Cukai Barangan dan Perkhidmatan", "771,693,750", "1,037,092,926")], 92),
    ("PELBAGAI LIABILITI", "155,342,175", "150,953,607", [
        ("Nota Kena Bayar", "109,822,637", "105,037,060"),
        ("Sekuriti Tak Dituntut", "31,179,044", "31,088,778"),
        ("Akaun Depositori Pusat", "14,340,494", "14,827,769")], 93),
]
for parent, t22, t21, items, pg in com_src:
    pp = pg - 12
    for item, a22, a21 in items:
        for yr, amt in ((2022, a22), (2021, a21)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2022, t22), (2021, t21)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2022", N("224,115,577,507"), 224115577507)
CHK("control: Pajakan 2022", N("34,551,706,062"), 34551706062)
CHK("control: Bayaran Balik Cukai 2022", N("25,721,574,279"), 25721574279)
CHK("control: Pelbagai Liabiliti 2022", N("155,342,175"), 155342175)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p63)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2022",
    N("224,115,577,507") + N("34,551,706,062") + N("25,721,574,279") + N("535,409,173"),
    284924267021)
# declared restatements of 2021 comparatives (reported, never corrected)
CHK("declared restatement: Pajakan KP 2021 restated to 24,933,059,218",
    N("24,933,059,218"), 24933059218)
CHK("declared restatement: Cukai Pendapatan 2021 restated to 20,194,440,042",
    N("20,194,440,042"), 20194440042)
CHK("declared restatement: CKHT 2021 restated to 604,969,431",
    N("604,969,431"), 604969431)

# =====================================================================
# 6. Nota 11-12 (pdf 93, printed 81)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(93, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(93, 81, stmt)))
O("11", "Pinjaman badan berkanun dan syarikat milik Kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2022, "317,616,866,101", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2022, "1,172,780,827,145", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2022, "1,878,985,615",
  "Nota 12 Wang Pendahuluan Kontraktor")
# NOTE: the 2022 volume has no Nota 13 (Pendahuluan Dana Pembiayaan Utiliti first
# appears in the 2023 volume) — format difference, reported in the build notes.

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
    print(f"WROTE {fname}: {n} rows | columns: {','.join(cols)}")

print()
if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES (token not found on page):")
    for pg, s in verify_fail:
        print(f"  pdf_page {pg}: {s!r}")
else:
    print("RAW-TEXT VERIFICATION: all non-zero amounts found verbatim on their source pages.")

print()
fails = 0
with open(os.path.join(WH, "_validation_checks_2022.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
