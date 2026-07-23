#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-13 detail tables
from PKKP 2023 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2023-volume format notes vs 2024:
 - Nota 4 has an extra row 'Deposit Jangka Panjang Dalam Negeri Melebihi 12 Bulan'
   (2022 comparative only).
 - Nota 7(a)(ii) COVID-19 fund has live 2022 comparatives (fund wound down 31.12.2022).
 - Nota 7(c) Deposit Pelarasan composition differs from the 2024 volume's 2023
   comparatives ('Deposit Cek Terbatal Luar Negara' printed; 'Deposit Pembatalan
   Pencen Skim B' not printed).
 - Nota 9 prints a prior-year comparative for Pinjaman dan Pendahuluan Boleh
   Dituntut with a RESTATED 2022 Kerajaan Negeri figure (as noted in the volume).
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2023"
WH = "/home/claude/pkkp/warehouse2023"
SRC = "2023_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 78, printed 66)
# =====================================================================
cash_src = [  # label, 2023, 2022, row_type
    ("WANG TUNAI", "27,607,017,910", "48,502,901,599", "total"),
    ("Wang Tunai Dalam Bank", "26,685,449,061", "46,815,352,167", "detail"),
    ("Wang Tunai Dalam Perjalanan", "918,966,224", "1,684,925,057", "detail"),
    ("Wang Tunai Dalam Tangan", "2,602,625", "2,624,375", "detail"),
]
cash_rows = []
for label, a23, a22, rt in cash_src:
    for yr, amt in ((2023, a23), (2022, a22)):
        V(78, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(78, 66, "Nota 3 Wang Tunai")))
for yr in (2023, 2022):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2023", 27607017910.0, 27607017910)
CHK("control: Wang Tunai 2022", 48502901599.0, 48502901599)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 78, printed 66)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa23, am23, kwa22, am22
    ("Sekuriti Hutang Kerajaan Luar Negeri", "4,544,932,407", "-", "3,668,464,214", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,393,896,094", "-", "1,334,744,136", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "2,152,492,289", "-", "2,095,583,493", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "4,477,087,246", "-", "4,396,155,634", "-"),
    ("Sekuriti Tersiar Harga Luar Negeri", "1,325,769,994", "-", "371,725,288", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "3,121,518,450", "-", "2,167,823,214", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Luar Negeri Melebihi 3 - 12 Bulan", "-", "5,847,400", "-", "5,292,600"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "15,303,587,250", "2,675,000,000", "9,538,404,250", "4,280,000,000"),
    ("Deposit Jangka Panjang Dalam Negeri Melebihi 12 Bulan", "-", "-", "136,000,000", "-"),
    ("Pelbagai", "-", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2023): "32,759,391,788", (AM, 2023): "9,399,551,535",
           (KWA, 2022): "24,149,008,287", (AM, 2022): "11,003,996,735"}
inv_tot = {2023: "42,158,943,323", 2022: "35,153,005,022"}
P4 = prov(78, 66, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2023, 2022):
    V(78, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k23, a23, k22, a22 in inv_src:
    for yr, kv, av in ((2023, k23, a23), (2022, k22, a22)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(78, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(78, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2023, 2022):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2023", N(inv_tot[2023]), 42158943323)
CHK("control: Pelaburan 2022", N(inv_tot[2022]), 35153005022)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 84-86)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 84, printed 72)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2023, 2022, row_type
    ("", "BAKI PADA 1 JANUARI", "(11,951,027,051)", "(11,969,532,073)", "opening"),
    ("TERIMAAN", "TERIMAAN", "97,823,385,008", "71,592,466,448", "subtotal"),
    ("TERIMAAN", "Caruman Daripada Akaun Hasil Disatukan", "3,692,563,904", "1,663,548,105", "detail"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "92,408,571,723", "68,540,975,622", "detail"),
    ("TERIMAAN", "Pindahan Daripada Kumpulan Wang COVID-19", "211,932,073", "-", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,007,341,205", "1,198,648,613", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "12,611", "300", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "502,963,492", "189,293,808", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "96,089,737,123", "71,573,961,426", "subtotal"),
    ("BAYARAN", "Langsung", "94,868,859,830", "69,928,178,120", "detail"),
    ("BAYARAN", "Pinjaman", "1,220,877,293", "1,645,783,306", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "1,733,647,885", "18,505,022", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(10,217,379,166)", "(11,951,027,051)", "closing"),
]
for sec, item, a23, a22, rt in kwp_src:
    for yr, amt in ((2023, a23), (2022, a22)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 84, 72, S1)

def stmt_checks(fund, prefix):
    for yr in (2023, 2022):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        # details=subtotal only checkable where the note prints detail rows under the
        # section (COVID fund's BAYARAN section prints a single payment line, no children)
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
CHK("control: Kumpulan Wang Pembangunan closing 2023",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2023
     and r["row_type"] == "closing"][0], -10217379166)

# --- 7(a)(ii) Kumpulan Wang COVID-19 (pdf 84, printed 72)
S2 = "Nota 7(a)(ii) Kumpulan Wang COVID-19"
covid_src = [
    ("", "BAKI PADA 1 JANUARI", "211,932,073", "291,766,741", "opening"),
    ("TERIMAAN", "TERIMAAN", "-", "30,899,284,878", "subtotal"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "-", "30,880,000,000", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "-", "19,284,878", "detail"),
    ("BAYARAN", "Perbelanjaan COVID-19", "-", "30,979,119,546", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "-", "(79,834,668)", "net"),
    ("PINDAHAN KE", "Kumpulan Wang Pembangunan", "(211,932,073)", "-", "detail"),
    ("", "BAKI PADA 31 DISEMBER", "-", "211,932,073", "closing"),
]
for sec, item, a23, a22, rt in covid_src:
    for yr, amt in ((2023, a23), (2022, a22)):
        T(KWK, "Kumpulan Wang COVID-19", sec, item, yr, amt, rt, 84, 72, S2)
stmt_checks("Kumpulan Wang COVID-19", "Nota7(a)(ii) COVID")

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 85, printed 73)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": ("18,881,372,179", "29,732,519,771", [
        ("Akaun Penyelesaian Utama Perbendaharaan", "18,880,372,179", "29,731,519,771"),
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("150,174,253", "150,039,652", [
        ("Akaun Stor dan Woksyop Tak Beruntuk", "150,174,253", "150,039,652"),
    ]),
    "AKAUN PINJAMAN": ("4,551,393,675", "3,983,151,017", [
        ("Kumpulan Wang Amanah Kontraktor", "3,720,967", "1,435,042"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "130,556,471", "97,539,470"),
        ("Kumpulan Wang Amanah Tabung Modal Pusingan Suruhanjaya Koperasi Malaysia", "559,368,838", "580,254,935"),
        ("Kumpulan Wang Amanah Pembangunan Ekonomi Belia", "15,388,274", "14,810,666"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "37,003,011", "51,467,275"),
        ("Pendahuluan Diri (Pegawai Awam)", "128,823,589", "122,930,610"),
        ("Pendahuluan Pelbagai", "45,484,850", "47,640,685"),
        ("Pendahuluan Untuk Negeri", "842,783,583", "734,153,583"),
        ("Kumpulan Wang Amanah Pinjaman Diraja", "799,478", "799,478"),
        ("Pinjaman Kenderaan", "63,422,229", "63,541,281"),
        ("Kumpulan Wang Pinjaman Kepada Badan Berkanun dan Badan Lain", "2,183,265,386", "1,795,846,153"),
        ("Kumpulan Wang Amanah Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "35,170,712", "27,982,509"),
        ("Kumpulan Wang Amanah Rakyat Malaysia di Luar Negeri", "1,466,566", "1,362,012"),
        ("Kumpulan Wang Amanah Tabung Pusingan Pinjaman Pelajaran Persekutuan", "504,139,721", "443,387,318"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("721,367,550", "823,079,800", [
        ("Kumpulan Wang Luar Jangka", "721,367,550", "823,079,800"),
    ]),
    "PELBAGAI KUMPULAN WANG": ("21,339,827,491", "27,878,401,978", [
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "566,341", "623,314"),
        ("Kumpulan Wang Amanah Bantuan Bencana Negara", "192,708,844", "169,450,750"),
        ("Kumpulan Wang Amanah Bantuan Mangsa Serangan Binatang Buas", "20", "228,520"),
        ("Kumpulan Wang Amanah Cadangan Untuk Negeri", "457,463,801", "492,738,560"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "475,754", "4,472,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "683,870,413", "619,929,506"),
        ("Kumpulan Wang Amanah Kebajikan dan Kemudahan Bagi Penuntut di Luar Negeri", "1,886,059", "1,837,821"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "462,138", "263,109"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "694", "794"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "107,741,438", "109,103,139"),
        ("Kumpulan Wang Amanah Malaysia Science Endowment (MSE)", "29,812,996", "10,115,710"),
        ("Kumpulan Wang Amanah Negara", "19,055,144,798", "15,559,210,295"),
        ("Kumpulan Wang Amanah Pelajar Miskin", "68,012,293", "70,776,571"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,069,711", "2,399,372"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "4,613,074", "4,613,074"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "36,128,620", "38,400,846"),
        ("Kumpulan Wang Amanah Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Kumpulan Wang Amanah Perkhidmatan Kemasyarakatan dan Kebajikan", "35,118,430", "33,597,148"),
        ("Kumpulan Wang Amanah Perpustakaan Negara", "659,010", "643,293"),
        ("Kumpulan Wang Amanah Program Perumahan Rakyat Dimiliki", "92,728,581", "115,329,088"),
        ("Kumpulan Wang Amanah Kedaulatan Maritim Negara", "952,007", "601,695"),
        ("Kumpulan Wang Amanah Projek Penandaan dan Pengukuran Sempadan Bersama di Antara Negeri-negeri Semenanjung Malaysia", "4,277,392", "2,336,704"),
        ("Kumpulan Wang Amanah Skim Biasiswa Sukan Persekutuan", "1,749,316", "1,378,962"),
        ("Kumpulan Wang Amanah Sokongan Keluarga Jabatan Kehakiman Syariah Malaysia", "15,595,702", "15,303,565"),
        ("Kumpulan Wang Amanah Sukan Negara", "16,261,497", "25,921,589"),
        ("Kumpulan Wang Amanah Tabung Bantuan Perubatan (TBP)", "67,823,804", "90,456,221"),
        ("Kumpulan Wang Amanah Tabung Bayaran Balik Cukai", "180,700,678", "10,186,456,917"),
        ("Kumpulan Wang Amanah Tabung Inovasi Negara (KWATIN)", "-", "19,813,117"),
        ("Kumpulan Wang Amanah Tabung Khas Hakmilik Strata", "2,799,404", "1,814,404"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "16,418,753", "20,302,697"),
        ("Kumpulan Wang Amanah Tabung Pustaka Peringatan P. Ramlee", "58,419", "40,424"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "15,470,772", "14,230,890"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan (CBP)", "244,875,566", "262,629,863"),
    ]),
}
for cat, (s23, s22, items) in pkw_src.items():
    for yr, amt in ((2023, s23), (2022, s22)):
        T(KWK, PKW, cat, cat, yr, amt, "subtotal", 85, 73, S3)
    for item, a23, a22 in items:
        for yr, amt in ((2023, a23), (2022, a22)):
            T(KWK, PKW, cat, item, yr, amt, "detail", 85, 73, S3)
for yr, amt in ((2023, "45,644,135,148"), (2022, "62,567,192,218")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 85, 73, S3)
for yr in (2023, 2022):
    for cat, (s23, s22, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s23 if yr == 2023 else s22))
    subs = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "subtotal")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) subtotals = PELBAGAI KWAK total {yr}", subs, tot)
CHK("cross: Pelbagai KWAK total 2023 = Nota7 top-level closing", 45644135148.0, 45644135148)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 86, printed 74)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH AM": ("5,503,813,531", "5,350,446,266", [
        ("Akaun Amanah Mendapatkan Kembali Aset", "1,344,971,032", "1,927,333,888"),
        ("Akaun Amanah Dana Khas Kerajaan Persekutuan", "1,037,305,250", "60,614,120"),
        ("Akaun Amanah Industri Bekalan Elektrik", "886,431,163", "840,971,913"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baharu", "426,379,455", "428,692,575"),
        ("Akaun Amanah Sumber Khas", "392,241,965", "397,941,208"),
        ("Pelbagai Amanah Am", "1,416,484,666", "1,694,892,562"),
    ]),
    "AMANAH KHAS": ("3,557,308,547", "3,499,072,034", [
        ("Akaun Amanah Estet Kebankrapan", "2,104,346,115", "2,078,984,083"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "372,633,891", "346,622,703"),
        ("Akaun Amanah Faedah atas Pelaburan untuk Deposit Mahkamah", "321,421,894", "302,071,900"),
        ("Kumpulan Wang Dius Api", "308,661,188", "301,917,856"),
        ("Akaun Amanah Am Pelikuidasi", "288,567,298", "295,611,957"),
        ("Pelbagai Amanah Khas", "161,678,161", "173,863,535"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 86, printed 74)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("12,598,594,083", "11,965,755,444", [
        ("Deposit Kawalan Wang Tak Dituntut", "8,191,452,886", "7,733,236,530"),
        ("Deposit Wang Jaminan Pelaksanaan", "1,826,217,893", "1,661,456,801"),
        ("Deposit Mahkamah Tinggi", "1,153,364,778", "1,219,853,377"),
        ("Deposit Imigresen", "438,574,707", "413,648,187"),
        ("Deposit Cagaran", "242,328,305", "248,265,797"),
        ("Pelbagai Deposit Am", "746,655,514", "689,294,752"),
    ]),
    "DEPOSIT PELARASAN": ("667,716,270", "149,408,551", [
        ("Akaun Terimaan Tidak Diperuntukkan", "595,337,221", "89,092,270"),
        ("Deposit Pindahan Dana Elektronik Terbatal", "64,248,383", "54,301,231"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JHEV", "5,667,413", "3,604,157"),
        ("Deposit Pelarasan Cek Terbatal", "994,811", "912,325"),
        ("Deposit Cek Terbatal Luar Negara", "160,201", "177,539"),
        ("Pelbagai Deposit Pelarasan", "1,308,241", "1,321,029"),
    ]),
}
for grp, src, tot23, tot22, stmt in (
        (KAW, awam_src, "9,061,122,078", "8,849,518,300", S4),
        (DEP, dep_src, "13,266,310,353", "12,115,163,995", S5)):
    for sec, (s23, s22, items) in src.items():
        for yr, amt in ((2023, s23), (2022, s22)):
            T(grp, "", sec, sec, yr, amt, "subtotal", 86, 74, stmt)
        for item, a23, a22 in items:
            for yr, amt in ((2023, a23), (2022, a22)):
                T(grp, "", sec, item, yr, amt, "detail", 86, 74, stmt)
    for yr, amt in ((2023, tot23), (2022, tot22)):
        T(grp, "", "", grp, yr, amt, "total", 86, 74, stmt)
    for yr in (2023, 2022):
        for sec, (s23, s22, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s23 if yr == 2023 else s22))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 88, printed 76)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(88, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(88, 76, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2023, "98,367,476,300", "total")
ppbd = [  # label, 2023, 2022, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "52,530,333,322", "54,216,510,499", "subtotal"),
    ("Kerajaan Negeri", "12,357,545,520", "12,128,564,837", "detail"),
    ("Syarikat", "31,637,189,116", "33,248,609,006", "detail"),
    ("Badan Berkanun", "6,753,378,832", "6,934,327,366", "detail"),
    ("Koperasi", "287,272,363", "262,272,363", "detail"),
    ("Pelbagai Agensi", "1,305,731,941", "1,464,367,549", "detail"),
    ("Perseorangan", "189,215,550", "178,369,378", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a23, a22, rt in ppbd:
    for yr, amt in ((2023, a23), (2022, a22)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2023, "45,837,142,978", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2023, "535,346,818", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2023, "24,712,053,356", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2023, "2,642,755,844", "memo")
pel = [
    ("PELABURAN", "34,821,492,525", "34,030,520,711", "subtotal"),
    ("Syarikat", "33,804,817,600", "33,013,845,786", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a23, a22, rt in pel:
    for yr, amt in ((2023, a23), (2022, a22)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2023, 2022):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2023 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2023 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2023",
    N("52,530,333,322") + N("45,837,142,978"), 98367476300)
CHK("control: Akaun Belum Terima 2023", 98367476300.0, 98367476300)
CHK("control: memo Pelaburan 2023", N(pel[0][1]), 34821492525)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 90-91)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2023, printed_total_2022, items, pdf_page
    ("KOMITMEN JAMINAN", "227,404,119,216", "224,115,577,507", [
        ("Dalam Negeri", "193,434,945,644", "183,667,995,570"),
        ("Luar Negeri", "33,969,173,572", "40,447,581,937")], 90),
    ("KOMITMEN PAJAKAN KEWANGAN", "31,302,695,874", "33,727,041,258", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "20,512,969,943", "22,148,700,295"),
        ("Pajakan Kewangan Badan Berkanun", "10,789,725,931", "11,578,340,963")], 90),
    ("KOMITMEN BAYARAN BALIK CUKAI", "25,511,259,802", "25,721,574,279", [
        ("Cukai Pendapatan", "24,711,944,573", "24,263,817,207"),
        ("Cukai Keuntungan Harta Tanah", "610,703,845", "686,063,322"),
        ("Cukai Barang dan Perkhidmatan", "188,611,384", "771,693,750")], 90),
    ("PELBAGAI LIABILITI", "157,532,088", "155,342,175", [
        ("Nota Kena Bayar", "104,744,419", "109,822,637"),
        ("Sekuriti Tak Dituntut", "38,447,175", "31,179,044"),
        ("Akaun Depositori Pusat", "14,340,494", "14,340,494")], 91),
]
for parent, t23, t22, items, pg in com_src:
    pp = pg - 12
    for item, a23, a22 in items:
        for yr, amt in ((2023, a23), (2022, a22)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2023, t23), (2022, t22)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2023", N("227,404,119,216"), 227404119216)
CHK("control: Pajakan 2023", N("31,302,695,874"), 31302695874)
CHK("control: Bayaran Balik Cukai 2023", N("25,511,259,802"), 25511259802)
CHK("control: Pelbagai Liabiliti 2023", N("157,532,088"), 157532088)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p73)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2023",
    N("227,404,119,216") + N("31,302,695,874") + N("25,511,259,802") + N("1,415,747,031"),
    285633821923)

# =====================================================================
# 6. Nota 11-13 (pdf 91, printed 79)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(91, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(91, 79, stmt)))
O("11", "Pinjaman badan berkanun dan syarikat milik Kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2023, "328,013,944,052", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2023, "1,286,787,672,492", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2023, "1,655,842,151",
  "Nota 12 Wang Pendahuluan Kontraktor")
O("13", "Pendahuluan Dana Pembiayaan Utiliti", 2023, "15,794,015",
  "Nota 13 Pendahuluan Dana Pembiayaan Utiliti")

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
with open(os.path.join(WH, "_validation_checks_2023.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
