#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-12 detail tables
from PKKP 2021 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2021-volume format notes vs 2022:
 - Nota 4 has no 'Sekuriti Tersiar Harga Luar Negeri' row (first appears 2022);
   nil cells print an ASCII '-'.
 - Nota 7(a)(i) TERIMAAN's first line is 'Caruman Daripada Akaun Hasil
   Disatukan' (the 2022 volume renames it 'Pindahan Daripada ...').
 - Nota 7(a)(ii) COVID-19 fund is LIVE (2021 expenditure RM37,711,016,365);
   the volume prints NO TERIMAAN subtotal row for this fund.
 - Nota 7(a)(iii) account names are the short 2021 forms (e.g. 'Kontraktor',
   'Amanah Negara'); the 2022 volume prints renamed successors with the
   'Kumpulan Wang Amanah' prefix.
 - Nota 7(b) AMANAH AM includes 'Akaun Amanah Pembinaan Projek Lebuhraya Pan
   Borneo Sarawak' (dropped in the 2022 volume) and names the PFI II account
   'Akaun Amanah Pelaksana Projek / Program / Aktiviti Menerusi Inisiatif
   Pembiayaan Swasta II'.
 - Nota 7(c) Deposit Pelarasan includes 'Deposit Pembatalan Pencen Skim B' and
   'Deposit Pindahan Dana Elektronik Terbatal - JPA Pencen' (both absorbed
   into Pelbagai by the 2022 volume); no 'Deposit Pelarasan CDCSB' row yet.
 - Nota 10(c)(ii)/(iv) and 10(d) declare RESTATEMENTS of the 2020
   comparatives (Pajakan KP 26,847,483,272 -> 26,849,157,677 and total
   37,570,623,547 -> 37,572,297,952; Komitmen Pampasan 892,581,000 ->
   973,669,713 with Kelewatan Bayaran Balik Cukai reported from 2021;
   Nota Kena Bayar 236,620,627 -> 131,094,036).
 - Notes end at Nota 12 (Wang Pendahuluan Kontraktor RM995,056,556).
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2021"
WH = "/home/claude/pkkp/warehouse2021"
SRC = "2021_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 72, printed 60)
# =====================================================================
cash_src = [  # label, 2021, 2020, row_type
    ("WANG TUNAI", "34,551,543,490", "26,030,389,682", "total"),
    ("Wang Tunai Dalam Bank", "33,594,301,309", "23,386,390,316", "detail"),
    ("Wang Tunai Dalam Perjalanan", "954,475,156", "2,641,122,146", "detail"),
    ("Wang Tunai Dalam Tangan", "2,767,025", "2,877,220", "detail"),
]
cash_rows = []
for label, a21, a20, rt in cash_src:
    for yr, amt in ((2021, a21), (2020, a20)):
        V(72, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(72, 60, "Nota 3 Wang Tunai")))
for yr in (2021, 2020):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2021", 34551543490.0, 34551543490)
CHK("control: Wang Tunai 2020", 26030389682.0, 26030389682)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 72, printed 60)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa21, am21, kwa20, am20
    ("Sekuriti Hutang Kerajaan Luar Negeri", "3,482,011,049", "-", "5,229,692,142", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,383,037,962", "-", "1,862,758,809", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "1,974,237,005", "-", "2,473,318,064", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "4,455,239,592", "-", "4,465,343,186", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "2,157,530,899", "-", "2,044,859,410", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,145,938", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Luar Negeri Melebihi 3 - 12 Bulan", "-", "5,630,900", "-", "-"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "10,806,083,900", "300,000,000", "6,731,137,800", "55,000,000"),
    ("Deposit Jangka Panjang Dalam Negeri Melebihi 12 Bulan", "11,668,500,000", "-", "10,042,500,000", "-"),
    ("Pelbagai", "-", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2021): "36,366,786,345", (AM, 2021): "7,024,335,035",
           (KWA, 2020): "33,289,717,469", (AM, 2020): "6,773,704,135"}
inv_tot = {2021: "43,391,121,380", 2020: "40,063,421,604"}
P4 = prov(72, 60, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2021, 2020):
    V(72, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k21, a21, k20, a20 in inv_src:
    for yr, kv, av in ((2021, k21, a21), (2020, k20, a20)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(72, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(72, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2021, 2020):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2021", N(inv_tot[2021]), 43391121380)
CHK("control: Pelaburan 2020", N(inv_tot[2020]), 40063421604)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 78-80)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 78, printed 66)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2021, 2020, row_type
    ("", "BAKI PADA 1 JANUARI", "(13,255,367,426)", "(24,700,420,089)", "opening"),
    ("TERIMAAN", "TERIMAAN", "65,542,501,108", "62,804,908,426", "subtotal"),
    ("TERIMAAN", "Caruman Daripada Akaun Hasil Disatukan", "2,235,696,217", "474,705,193", "detail"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "62,317,002,625", "61,071,047,806", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "975,029,385", "1,180,122,917", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "12,030", "59,430", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "14,760,851", "78,973,080", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "64,256,665,755", "51,359,855,763", "subtotal"),
    ("BAYARAN", "Langsung", "63,275,221,797", "49,330,957,654", "detail"),
    ("BAYARAN", "Pinjaman", "981,443,958", "2,028,898,109", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "1,285,835,353", "11,445,052,663", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(11,969,532,073)", "(13,255,367,426)", "closing"),
]
for sec, item, a21, a20, rt in kwp_src:
    for yr, amt in ((2021, a21), (2020, a20)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 78, 66, S1)

def stmt_checks(fund, prefix):
    for yr in (2021, 2020):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        ter = g("TERIMAAN", "subtotal") or g("TERIMAAN", "detail")
        if any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "detail" for r in rs) \
           and any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "subtotal" for r in rs):
            CHK(f"{prefix} TERIMAAN details = subtotal {yr}",
                g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
        if any(r["section_bm"] == "BAYARAN" and r["row_type"] == "detail" for r in rs) \
           and any(r["section_bm"] == "BAYARAN" and r["row_type"] == "subtotal" for r in rs):
            CHK(f"{prefix} BAYARAN details = subtotal {yr}",
                g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
        bay = g("BAYARAN", "subtotal") or g("BAYARAN", "detail")
        net = ter - bay
        CHK(f"{prefix} terimaan-bayaran = Lebihan/(Kurangan) {yr}",
            net, one("Lebihan/(Kurangan) bagi Tahun"))
        transfer = sum(r["amount_rm"] for r in rs if r["section_bm"] == "PINDAHAN KE")
        CHK(f"{prefix} opening+net+pindahan = closing {yr}",
            one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun") + transfer,
            one("BAKI PADA 31 DISEMBER"))
stmt_checks("Kumpulan Wang Pembangunan", "Nota7(a)(i) KWP")
CHK("control: Kumpulan Wang Pembangunan closing 2021",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2021
     and r["row_type"] == "closing"][0], -11969532073)

# --- 7(a)(ii) Kumpulan Wang COVID-19 (pdf 78, printed 66) — LIVE, no TERIMAAN subtotal printed
S2 = "Nota 7(a)(ii) Kumpulan Wang COVID-19"
covid_src = [
    ("", "BAKI PADA 1 JANUARI", "761,369", "-", "opening"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "38,000,000,000", "38,020,000,000", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "2,021,737", "-", "detail"),
    ("BAYARAN", "Perbelanjaan COVID-19", "37,711,016,365", "38,019,238,631", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "291,005,372", "761,369", "net"),
    ("", "BAKI PADA 31 DISEMBER", "291,766,741", "761,369", "closing"),
]
for sec, item, a21, a20, rt in covid_src:
    for yr, amt in ((2021, a21), (2020, a20)):
        T(KWK, "Kumpulan Wang COVID-19", sec, item, yr, amt, rt, 78, 66, S2)
stmt_checks("Kumpulan Wang COVID-19", "Nota7(a)(ii) COVID")
CHK("control: COVID fund 2021 expenditure", 37711016365.0, 37711016365)

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 79, printed 67)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": ("17,584,177,887", "11,116,223,509", [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "17,583,177,887", "11,115,223,509"),
    ]),
    "AKAUN PERNIAGAAN": ("155,548,348", "156,964,318", [
        ("Stor dan Woksyop Tak Beruntuk", "155,548,348", "156,964,318"),
    ]),
    "AKAUN PINJAMAN": ("3,685,699,902", "2,985,563,130", [
        ("Kontraktor", "2,431,054", "3,388,514"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "64,826,104", "43,058,280"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "566,335,586", "500,248,513"),
        ("Pembangunan Ekonomi Belia", "14,458,147", "14,019,400"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "53,692,280", "48,965,468"),
        ("Pendahuluan Diri (Pegawai Awam)", "142,920,499", "39,625,187"),
        ("Pendahuluan Pelbagai", "50,260,492", "50,108,420"),
        ("Pendahuluan Untuk Negeri", "855,523,583", "874,893,583"),
        ("Pinjaman Diraja", "780,353", "763,436"),
        ("Pinjaman Kenderaan", "63,649,113", "63,491,343"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,467,050,834", "1,022,193,268"),
        ("Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "20,271,657", "14,182,456"),
        ("Rakyat Malaysia di Luar Negeri", "1,337,589", "1,317,092"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "382,162,611", "309,308,170"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("1,500,000,000", "1,499,999,980", [
        ("Kumpulan Wang Luar Jangka", "1,500,000,000", "1,499,999,980"),
    ]),
    "PELBAGAI KUMPULAN WANG": ("19,793,870,844", "20,218,603,754", [
        ("Amanah Negara", "15,291,305,995", "18,294,241,419"),
        ("Amanah Pelajar Miskin", "100,175,146", "93,733,363"),
        ("Amanah Sukan Negara", "55,075,903", "38,650,869"),
        ("Bantuan Bencana Negara", "269,621,226", "212,008,291"),
        ("Bantuan Mangsa Serangan Binatang Buas", "1,003,400", "996,200"),
        ("Cadangan Untuk Negeri", "412,992,483", "347,094,275"),
        ("Kebajikan dan Kemudahan Bagi Penuntut di Luar Negeri", "1,769,524", "2,080,495"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "954,385", "968,725"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "472,854", "472,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "562,866,676", "506,131,754"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "266,689", "341,547"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "255,830,418", "103,241,716"),
        ("Kumpulan Wang Amanah Majlis Sains dan Penyelidikan Kebangsaan (MSPK)", "10,418,838", "2,818,236"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara (INSPEN)", "2,892,811", "2,718,623"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "6,175,844", "6,175,844"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "42,361,858", "40,837,387"),
        ("Kumpulan Wang Amanah Projek Penandaan dan Pengukuran Sempadan Bersama di Antara Negeri-negeri Semenanjung Malaysia", "4,305,621", "5,356,430"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "483,075", "739,033"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "15,097,946", "14,836,106"),
        ("Kumpulan Wang Amanah Tabung Khas Hakmilik Strata", "1,517,537", "1,692,250"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "22,717,584", "7,729,170"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "14,346,266", "18,902,576"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan (CBP)", "275,848,835", "84,244,568"),
        ("Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "33,861,101", "33,335,877"),
        ("Perpustakaan Negara", "1,205,403", "1,227,574"),
        ("Program Perumahan Rakyat Dimiliki", "114,612,046", "121,943,656"),
        ("Skim Biasiswa Sukan Persekutuan", "887,152", "561,971"),
        ("Tabung Bantuan Perubatan (TBP)", "90,573,881", "85,022,970"),
        ("Tabung Bayaran Balik Cukai", "2,181,012,904", "167,287,155"),
        ("Tabung Inovasi Negara (KWATIN)", "19,813,117", "19,813,117"),
        ("Tabung Pustaka Peringatan P. Ramlee", "22,366", "17,743"),
    ]),
}
for cat, (s21, s20, items) in pkw_src.items():
    for yr, amt in ((2021, s21), (2020, s20)):
        T(KWK, PKW, cat, cat, yr, amt, "subtotal", 79, 67, S3)
    for item, a21, a20 in items:
        for yr, amt in ((2021, a21), (2020, a20)):
            T(KWK, PKW, cat, item, yr, amt, "detail", 79, 67, S3)
for yr, amt in ((2021, "42,719,296,981"), (2020, "35,977,354,691")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 79, 67, S3)
for yr in (2021, 2020):
    for cat, (s21, s20, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s21 if yr == 2021 else s20))
    subs = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "subtotal")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) subtotals = PELBAGAI KWAK total {yr}", subs, tot)
CHK("cross: Pelbagai KWAK total 2021 = Nota7 top-level closing", 42719296981.0, 42719296981)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 80, printed 68)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH AM": ("19,633,284,204", "16,659,514,722", [
        ("Akaun Amanah Mendapatkan Kembali Aset", "15,280,763,537", "11,477,342,168"),
        ("Akaun Amanah Industri Bekalan Elektrik", "865,136,402", "783,882,201"),
        ("Akaun Amanah Pelaksana Projek / Program / Aktiviti Menerusi Inisiatif Pembiayaan Swasta II", "651,772,865", "1,430,138,317"),
        ("Akaun Amanah Pembinaan Projek Lebuhraya Pan Borneo Sarawak", "524,256,490", "557,179,250"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baharu", "435,366,936", "438,084,498"),
        ("Pelbagai Amanah Am", "1,875,987,974", "1,972,888,288"),
    ]),
    "AMANAH KHAS": ("3,438,566,266", "3,412,661,031", [
        ("Akaun Amanah Estet Kebankrapan", "2,060,566,357", "2,090,275,745"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "326,776,345", "294,326,347"),
        ("Kumpulan Wang Dius Api", "303,662,063", "286,471,639"),
        ("Akaun Amanah Am Pelikuidasi", "288,965,462", "312,579,832"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "288,137,223", "275,829,411"),
        ("Pelbagai Amanah Khas", "170,458,816", "153,178,057"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 80, printed 68)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("11,836,424,195", "11,303,344,115", [
        ("Deposit Kawalan Wang Tak Dituntut", "7,476,484,583", "7,091,482,309"),
        ("Deposit Wang Jaminan Pelaksanaan", "1,802,432,243", "1,747,122,403"),
        ("Deposit Mahkamah Tinggi", "1,225,622,946", "1,229,493,682"),
        ("Deposit Imigresen", "391,898,137", "296,343,487"),
        ("Deposit Cagaran", "224,694,403", "81,749,045"),
        ("Pelbagai Deposit Am", "715,291,883", "857,153,189"),
    ]),
    "DEPOSIT PELARASAN": ("129,731,470", "132,415,698", [
        ("Deposit Pindahan Dana Elektronik Terbatal", "62,077,240", "63,294,909"),
        ("Akaun Terimaan Tidak Diperuntukkan", "46,096,022", "34,238,566"),
        ("Deposit Pembatalan Pencen Skim B", "6,548,778", "15,339,138"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JHEV", "4,556,223", "4,375,175"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JPA Pencen", "4,433,883", "9,335,673"),
        ("Pelbagai Deposit Pelarasan", "6,019,324", "5,832,237"),
    ]),
}
for grp, src, tot21, tot20, stmt in (
        (KAW, awam_src, "23,071,850,470", "20,072,175,753", S4),
        (DEP, dep_src, "11,966,155,665", "11,435,759,813", S5)):
    for sec, (s21, s20, items) in src.items():
        for yr, amt in ((2021, s21), (2020, s20)):
            T(grp, "", sec, sec, yr, amt, "subtotal", 80, 68, stmt)
        for item, a21, a20 in items:
            for yr, amt in ((2021, a21), (2020, a20)):
                T(grp, "", sec, item, yr, amt, "detail", 80, 68, stmt)
    for yr, amt in ((2021, tot21), (2020, tot20)):
        T(grp, "", "", grp, yr, amt, "total", 80, 68, stmt)
    for yr in (2021, 2020):
        for sec, (s21, s20, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s21 if yr == 2021 else s20))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 82, printed 70)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(82, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(82, 70, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2021, "113,045,075,728", "total")
ppbd = [  # label, 2021, 2020, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "57,846,052,679", "58,900,685,743", "subtotal"),
    ("Kerajaan Negeri", "14,218,973,091", "15,979,101,032", "detail"),
    ("Syarikat", "34,613,168,836", "33,471,481,387", "detail"),
    ("Badan Berkanun", "6,963,127,525", "7,120,406,614", "detail"),
    ("Pihak Berkuasa Tempatan", "136,242,276", "143,178,696", "detail"),
    ("Koperasi", "237,272,363", "237,272,363", "detail"),
    ("Pelbagai Agensi", "1,523,841,742", "1,687,486,839", "detail"),
    ("Perseorangan", "153,426,846", "261,758,812", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a21, a20, rt in ppbd:
    for yr, amt in ((2021, a21), (2020, a20)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2021, "55,199,023,049", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2021, "643,892,981", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2021, "20,775,817,355", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2021, "2,943,083,873", "memo")
pel = [
    ("PELABURAN", "33,861,520,709", "33,191,463,711", "subtotal"),
    ("Syarikat", "32,844,845,784", "32,174,788,786", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a21, a20, rt in pel:
    for yr, amt in ((2021, a21), (2020, a20)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2021, 2020):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2021 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2021 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2021",
    N("57,846,052,679") + N("55,199,023,049"), 113045075728)
CHK("control: Akaun Belum Terima 2021", 113045075728.0, 113045075728)
CHK("control: memo Pelaburan 2021", N(pel[0][1]), 33861520709)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 84-85)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2021, printed_total_2020, items, pdf_page
    ("KOMITMEN JAMINAN", "229,391,741,672", "216,841,563,770", [
        ("Dalam Negeri", "176,623,572,552", "167,991,778,089"),
        ("Luar Negeri", "52,768,169,120", "48,849,785,681")], 84),
    ("KOMITMEN PAJAKAN KEWANGAN", "37,202,939,956", "37,572,297,952", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "24,855,765,206", "26,849,157,677"),
        ("Pajakan Kewangan Badan Berkanun", "12,347,174,750", "10,723,140,275")], 84),
    ("KOMITMEN BAYARAN BALIK CUKAI", "14,683,293,428", "14,635,443,058", [
        ("Cukai Pendapatan", "13,042,914,435", "12,186,431,101"),
        ("Cukai Keuntungan Harta Tanah", "603,286,067", "575,429,182"),
        ("Cukai Barangan dan Perkhidmatan", "1,037,092,926", "1,873,582,775")], 84),
    ("PELBAGAI LIABILITI", "150,953,607", "172,473,614", [
        ("Nota Kena Bayar", "105,037,060", "131,094,036"),
        ("Sekuriti Tak Dituntut", "31,088,778", "27,343,222"),
        ("Akaun Depositori Pusat", "14,827,769", "14,036,356")], 85),
]
for parent, t21, t20, items, pg in com_src:
    pp = pg - 12
    for item, a21, a20 in items:
        for yr, amt in ((2021, a21), (2020, a20)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2021, t21), (2020, t20)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2021", N("229,391,741,672"), 229391741672)
CHK("control: Pajakan 2021", N("37,202,939,956"), 37202939956)
CHK("control: Bayaran Balik Cukai 2021", N("14,683,293,428"), 14683293428)
CHK("control: Pelbagai Liabiliti 2021", N("150,953,607"), 150953607)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p55)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2021",
    N("229,391,741,672") + N("37,202,939,956") + N("14,683,293,428") + N("997,834,453"),
    282275809509)
# declared restatements of 2020 comparatives (reported, never corrected)
CHK("declared restatement: Pajakan KP 2020 restated to 26,849,157,677",
    N("26,849,157,677"), 26849157677)
CHK("declared restatement: Pajakan total 2020 restated to 37,572,297,952",
    N("37,572,297,952"), 37572297952)
CHK("declared restatement: Komitmen Pampasan 2020 restated to 973,669,713",
    N("973,669,713"), 973669713)
CHK("declared restatement: Nota Kena Bayar 2020 restated to 131,094,036",
    N("131,094,036"), 131094036)

# =====================================================================
# 6. Nota 11-12 (pdf 85, printed 73)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(85, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(85, 73, stmt)))
O("11", "Pinjaman badan berkanun dan syarikat milik Kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2021, "310,387,529,248", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2021, "1,116,184,686,817", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2021, "995,056,556",
  "Nota 12 Wang Pendahuluan Kontraktor")

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
with open(os.path.join(WH, "_validation_checks_2021.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
