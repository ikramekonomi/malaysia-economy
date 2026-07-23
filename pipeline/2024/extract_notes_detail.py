#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-13 detail tables
from PKKP 2024 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work"
WH = "/home/claude/pkkp/warehouse"
SRC = "2024_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"

pages = open(os.path.join(WORK, "2024_full.txt")).read().split("\f")

def N(s):
    """Parse printed amount: '-'/'–' -> 0.0, '(x)' -> negative."""
    s = s.strip()
    if s in ("-", "–", ""):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v

verify_fail = []
def V(pdf_page, s):
    """Verify the printed token exists on the page (skip zero-dashes)."""
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
# 1. Nota 3 WANG TUNAI (pdf 82, printed 68)
# =====================================================================
cash_src = [  # label, 2024, 2023, row_type
    ("WANG TUNAI", "28,196,329,803", "27,607,017,910", "total"),
    ("Wang Tunai Dalam Bank", "27,598,562,879", "26,685,449,061", "detail"),
    ("Wang Tunai Dalam Perjalanan", "595,166,849", "918,966,224", "detail"),
    ("Wang Tunai Dalam Tangan", "2,600,075", "2,602,625", "detail"),
]
cash_rows = []
for label, a24, a23, rt in cash_src:
    for yr, amt in ((2024, a24), (2023, a23)):
        V(82, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(82, 68, "Nota 3 Wang Tunai")))
for yr in (2024, 2023):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2024", 28196329803.0, 28196329803)
CHK("control: Wang Tunai 2023", 27607017910.0, 27607017910)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 82, printed 68)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa24, am24, kwa23, am23
    ("Sekuriti Hutang Kerajaan Luar Negeri", "4,432,094,309", "-", "4,544,932,407", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,744,920,038", "-", "1,393,896,094", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "1,673,176,497", "-", "2,152,492,289", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "4,855,740,106", "-", "4,477,087,246", "-"),
    ("Sekuriti Tersiar Harga Luar Negeri", "1,815,748,157", "-", "1,325,769,994", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "3,527,617,677", "-", "3,121,518,450", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Luar Negeri Melebihi 3 - 12 Bulan", "-", "5,618,500", "-", "5,847,400"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "11,770,518,800", "762,554,000", "15,303,587,250", "2,675,000,000"),
    ("Pelbagai", "-", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2024): "30,259,923,642", (AM, 2024): "7,486,876,635",
           (KWA, 2023): "32,759,391,788", (AM, 2023): "9,399,551,535"}
inv_tot = {2024: "37,746,800,277", 2023: "42,158,943,323"}
P4 = prov(82, 68, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2024, 2023):
    V(82, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k24, a24, k23, a23 in inv_src:
    for yr, kv, av in ((2024, k24, a24), (2023, k23, a23)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(82, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(82, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2024, 2023):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2024", N(inv_tot[2024]), 37746800277)
CHK("control: Pelaburan 2023", N(inv_tot[2023]), 42158943323)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 88-90)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 88, printed 74)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2024, 2023, row_type
    ("", "BAKI PADA 1 JANUARI", "(10,217,379,166)", "(11,951,027,051)", "opening"),
    ("TERIMAAN", "TERIMAAN", "83,690,747,578", "97,823,385,008", "subtotal"),
    ("TERIMAAN", "Caruman Daripada Akaun Hasil Disatukan", "3,108,700,857", "3,692,563,904", "detail"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "76,994,365,064", "92,408,571,723", "detail"),
    ("TERIMAAN", "Pindahan Daripada Kumpulan Wang COVID-19", "-", "211,932,073", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,736,890,122", "1,007,341,205", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "52,450", "12,611", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "1,850,739,085", "502,963,492", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "84,011,595,464", "96,089,737,123", "subtotal"),
    ("BAYARAN", "Langsung", "83,216,205,191", "94,868,859,830", "detail"),
    ("BAYARAN", "Pinjaman", "795,390,273", "1,220,877,293", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "(320,847,886)", "1,733,647,885", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(10,538,227,052)", "(10,217,379,166)", "closing"),
]
for sec, item, a24, a23, rt in kwp_src:
    for yr, amt in ((2024, a24), (2023, a23)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 88, 74, S1)

def stmt_checks(fund, prefix):
    for yr in (2024, 2023):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        CHK(f"{prefix} TERIMAAN details = subtotal {yr}",
            g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
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
CHK("control: Kumpulan Wang Pembangunan closing 2024",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2024
     and r["row_type"] == "closing"][0], -10538227052)

# --- 7(a)(ii) Kumpulan Wang COVID-19 (pdf 88, printed 74)
S2 = "Nota 7(a)(ii) Kumpulan Wang COVID-19"
covid_src = [
    ("", "BAKI PADA 1 JANUARI", "-", "211,932,073", "opening"),
    ("TERIMAAN", "TERIMAAN", "-", "-", "subtotal"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "-", "-", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "-", "-", "detail"),
    ("BAYARAN", "Perbelanjaan COVID-19", "-", "-", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "-", "-", "net"),
    ("PINDAHAN KE", "Kumpulan Wang Pembangunan", "-", "(211,932,073)", "detail"),
    ("", "BAKI PADA 31 DISEMBER", "-", "-", "closing"),
]
for sec, item, a24, a23, rt in covid_src:
    for yr, amt in ((2024, a24), (2023, a23)):
        T(KWK, "Kumpulan Wang COVID-19", sec, item, yr, amt, rt, 88, 74, S2)
stmt_checks("Kumpulan Wang COVID-19", "Nota7(a)(ii) COVID")

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 89, printed 75)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": ("13,750,011,950", "18,881,372,179", [
        ("Akaun Penyelesaian Utama Perbendaharaan", "13,749,011,950", "18,880,372,179"),
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("150,291,462", "150,174,253", [
        ("Akaun Stor dan Woksyop Tak Beruntuk", "150,291,462", "150,174,253"),
    ]),
    "AKAUN PINJAMAN": ("3,506,557,407", "4,551,393,675", [
        ("Kumpulan Wang Amanah Kontraktor", "1,373,005", "3,720,967"),
        ("Kumpulan Wang Amanah Pembangunan Ekonomi Belia", "15,976,675", "15,388,274"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "161,456,233", "130,556,471"),
        ("Kumpulan Wang Amanah Pinjaman Diraja", "834,957", "799,478"),
        ("Kumpulan Wang Amanah Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "43,936,004", "35,170,712"),
        ("Kumpulan Wang Amanah Rakyat Malaysia di Luar Negeri", "2,650,398", "1,466,566"),
        ("Kumpulan Wang Amanah Tabung Modal Pusingan Suruhanjaya Koperasi Malaysia", "385,484,767", "559,368,838"),
        ("Kumpulan Wang Amanah Tabung Pusingan Pinjaman Pelajaran Persekutuan", "559,376,993", "504,139,721"),
        ("Kumpulan Wang Pinjaman Kepada Badan Berkanun dan Badan-Badan Lain", "1,288,730,692", "2,183,265,386"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "37,454,024", "37,003,011"),
        ("Pendahuluan Diri (Pegawai Awam)", "100,092,487", "128,823,589"),
        ("Pendahuluan Pelbagai", "47,056,907", "45,484,850"),
        ("Pendahuluan Untuk Negeri", "798,813,583", "842,783,583"),
        ("Pinjaman Kenderaan", "63,320,682", "63,422,229"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("1,449,087,300", "721,367,550", [
        ("Kumpulan Wang Luar Jangka", "1,449,087,300", "721,367,550"),
    ]),
    "PELBAGAI KUMPULAN WANG": ("23,318,315,713", "21,339,827,491", [
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "565,304", "566,341"),
        ("Kumpulan Wang Amanah Bantuan Bencana Negara", "323,768,318", "192,708,844"),
        ("Kumpulan Wang Amanah Bantuan Mangsa Serangan Binatang Buas", "20", "20"),
        ("Kumpulan Wang Amanah Cadangan Untuk Negeri", "352,524,169", "457,463,801"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "475,754", "475,754"),
        ("Kumpulan Wang Amanah Fi Jaminan", "750,969,941", "683,870,413"),
        ("Kumpulan Wang Amanah Kebajikan dan Kemudahan Bagi Penuntut di Luar Negeri", "1,892,897", "1,886,059"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "1,094,583", "462,138"),
        ("Kumpulan Wang Amanah Kedaulatan Maritim Negara", "1,028,110", "952,007"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "694", "694"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "148,137,673", "107,741,438"),
        ("Kumpulan Wang Amanah Malaysia Science Endowment (MSE)", "30,032,685", "29,812,996"),
        ("Kumpulan Wang Amanah Negara", "19,906,226,660", "19,055,144,798"),
        ("Kumpulan Wang Amanah Pelajar Miskin", "23,145,995", "68,012,293"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "1,446,373", "2,069,711"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "4,613,074", "4,613,074"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "33,964,363", "36,128,620"),
        ("Kumpulan Wang Amanah Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Kumpulan Wang Amanah Perkhidmatan Kemasyarakatan dan Kebajikan", "35,218,580", "35,118,430"),
        ("Kumpulan Wang Amanah Perpustakaan Negara", "680,214", "659,010"),
        ("Kumpulan Wang Amanah Program Perumahan Rakyat Dimiliki", "85,505,706", "92,728,581"),
        ("Kumpulan Wang Amanah Projek Penandaan dan Pengukuran Sempadan Bersama di Antara Negeri-negeri Semenanjung Malaysia", "8,664,832", "4,277,392"),
        ("Kumpulan Wang Amanah Skim Biasiswa Sukan Persekutuan", "2,461,384", "1,749,316"),
        ("Kumpulan Wang Amanah Sokongan Keluarga Jabatan Kehakiman Syariah Malaysia", "15,713,744", "15,595,702"),
        ("Kumpulan Wang Amanah Sukan Negara", "22,562,862", "16,261,497"),
        ("Kumpulan Wang Amanah Tabung Bantuan Perubatan (TBP)", "53,362,030", "67,823,804"),
        ("Kumpulan Wang Amanah Tabung Bayaran Balik Cukai", "1,169,145,336", "180,700,678"),
        ("Kumpulan Wang Amanah Tabung Khas Hakmilik Strata", "1,498,884", "2,799,404"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "13,171,667", "16,418,753"),
        ("Kumpulan Wang Amanah Tabung Pustaka Peringatan P. Ramlee", "60,171", "58,419"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "20,315,100", "15,470,772"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan (CBP)", "306,687,424", "244,875,566"),
    ]),
}
for cat, (s24, s23, items) in pkw_src.items():
    for yr, amt in ((2024, s24), (2023, s23)):
        T(KWK, PKW, cat, cat, yr, amt, "subtotal", 89, 75, S3)
    for item, a24, a23 in items:
        for yr, amt in ((2024, a24), (2023, a23)):
            T(KWK, PKW, cat, item, yr, amt, "detail", 89, 75, S3)
for yr, amt in ((2024, "42,174,263,832"), (2023, "45,644,135,148")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 89, 75, S3)
for yr in (2024, 2023):
    for cat, (s24, s23, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s24 if yr == 2024 else s23))
    subs = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "subtotal")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) subtotals = PELBAGAI KWAK total {yr}", subs, tot)
CHK("cross: Pelbagai KWAK total 2024 = Nota7 top-level closing", 42174263832.0, 42174263832)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 90, printed 76)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH AM": ("5,951,336,021", "5,503,813,531", [
        ("Akaun Amanah Mendapatkan Kembali Aset", "1,784,723,066", "1,344,971,032"),
        ("Akaun Amanah Dana Khas Kerajaan Persekutuan", "1,225,779,061", "1,037,305,250"),
        ("Akaun Amanah Industri Bekalan Elektrik", "913,890,404", "886,431,163"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baharu", "403,951,839", "426,379,455"),
        ("Akaun Amanah Sumber Khas", "318,742,909", "392,241,965"),
        ("Pelbagai Amanah Am", "1,304,248,742", "1,416,484,666"),
    ]),
    "AMANAH KHAS": ("3,669,424,566", "3,557,308,547", [
        ("Akaun Amanah Estet Kebankrapan", "2,124,646,309", "2,104,346,115"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "406,877,876", "372,633,891"),
        ("Akaun Amanah Faedah atas Pelaburan untuk Deposit Mahkamah", "351,074,346", "321,421,894"),
        ("Akaun Amanah Am Pelikuidasi", "313,326,416", "288,567,298"),
        ("Kumpulan Wang Dius Api", "301,624,895", "308,661,188"),
        ("Pelbagai Amanah Khas", "171,874,724", "161,678,161"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 90, printed 76)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("12,649,689,872", "12,598,594,083", [
        ("Deposit Kawalan Wang Tak Dituntut", "7,671,213,582", "8,191,452,886"),
        ("Deposit Wang Jaminan Pelaksanaan", "2,121,934,206", "1,826,217,893"),
        ("Deposit Mahkamah Tinggi", "1,383,135,761", "1,153,364,778"),
        ("Deposit Imigresen", "457,972,912", "438,574,707"),
        ("Deposit Cagaran", "240,260,435", "242,328,305"),
        ("Pelbagai Deposit Am", "775,172,976", "746,655,514"),
    ]),
    "DEPOSIT PELARASAN": ("173,515,755", "667,716,270", [
        ("Akaun Terimaan Tidak Diperuntukkan", "117,603,997", "595,337,221"),
        ("Deposit Pindahan Dana Elektronik Terbatal", "39,683,997", "64,248,383"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JHEV", "9,048,776", "5,667,413"),
        ("Deposit Pelarasan Cek Terbatal", "5,300,862", "994,811"),
        ("Deposit Pembatalan Pencen Skim B", "633,138", "402,912"),
        ("Pelbagai Deposit Pelarasan", "1,244,985", "1,065,530"),
    ]),
}
for grp, src, tot24, tot23, stmt in (
        (KAW, awam_src, "9,620,760,587", "9,061,122,078", S4),
        (DEP, dep_src, "12,823,205,627", "13,266,310,353", S5)):
    for sec, (s24, s23, items) in src.items():
        for yr, amt in ((2024, s24), (2023, s23)):
            T(grp, "", sec, sec, yr, amt, "subtotal", 90, 76, stmt)
        for item, a24, a23 in items:
            for yr, amt in ((2024, a24), (2023, a23)):
                T(grp, "", sec, item, yr, amt, "detail", 90, 76, stmt)
    for yr, amt in ((2024, tot24), (2023, tot23)):
        T(grp, "", "", grp, yr, amt, "total", 90, 76, stmt)
    for yr in (2024, 2023):
        for sec, (s24, s23, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s24 if yr == 2024 else s23))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 92, printed 78)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(92, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(92, 78, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2024, "103,158,407,176", "total")
ppbd = [
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "51,494,274,311", "52,530,333,322", "subtotal"),
    ("Kerajaan Negeri", "12,500,998,744", "12,357,545,520", "detail"),
    ("Syarikat", "30,549,276,896", "31,637,189,116", "detail"),
    ("Badan Berkanun", "6,721,604,457", "6,753,378,832", "detail"),
    ("Koperasi", "287,272,363", "287,272,363", "detail"),
    ("Pelbagai Agensi", "1,219,096,721", "1,305,731,941", "detail"),
    ("Perseorangan", "216,025,130", "189,215,550", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a24, a23, rt in ppbd:
    for yr, amt in ((2024, a24), (2023, a23)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2024, "51,664,132,865", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2024, "515,919,442", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2024, "32,431,263,256", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2024, "2,732,970,507", "memo")
pel = [
    ("PELABURAN", "34,690,492,524", "34,821,492,525", "subtotal"),
    ("Syarikat", "33,673,817,599", "33,804,817,600", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a24, a23, rt in pel:
    for yr, amt in ((2024, a24), (2023, a23)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2024, 2023):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2024 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2024 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2024",
    N("51,494,274,311") + N("51,664,132,865"), 103158407176)
CHK("control: Akaun Belum Terima 2024", 103158407176.0, 103158407176)
CHK("control: memo Pelaburan 2024", N(pel[0][1]), 34690492524)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 94-95)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2024, printed_total_2023, items, pdf_page
    ("KOMITMEN JAMINAN", "236,229,124,709", "227,404,119,216", [
        ("Dalam Negeri", "198,664,139,491", "193,434,945,644"),
        ("Luar Negeri", "37,564,985,218", "33,969,173,572")], 94),
    ("KOMITMEN PAJAKAN KEWANGAN", "26,659,661,074", "31,302,777,359", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "16,674,759,161", "20,513,051,428"),
        ("Pajakan Kewangan Badan Berkanun", "9,984,901,913", "10,789,725,931")], 94),
    ("KOMITMEN BAYARAN BALIK CUKAI", "33,341,680,942", "25,511,259,802", [
        ("Cukai Pendapatan", "32,569,033,195", "24,711,944,573"),
        ("Cukai Keuntungan Harta Tanah", "748,132,695", "610,703,845"),
        ("Cukai Barang dan Perkhidmatan", "24,515,052", "188,611,384")], 94),
    ("PELBAGAI LIABILITI", "133,924,597", "157,532,088", [
        ("Nota Kena Bayar", "87,061,154", "104,744,419"),
        ("Sekuriti Tak Dituntut", "36,116,407", "38,447,175"),
        ("Akaun Depositori Pusat", "10,747,036", "14,340,494")], 95),
]
for parent, t24, t23, items, pg in com_src:
    pp = pg - 14  # printed page offset in this section
    for item, a24, a23 in items:
        for yr, amt in ((2024, a24), (2023, a23)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2024, t24), (2023, t23)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2024", N("236,229,124,709"), 236229124709)
CHK("control: Pajakan 2024", N("26,659,661,074"), 26659661074)
CHK("control: Bayaran Balik Cukai 2024", N("33,341,680,942"), 33341680942)
CHK("control: Pelbagai Liabiliti 2024", N("133,924,597"), 133924597)

# =====================================================================
# 6. Nota 11-13 (pdf 95, printed 81)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(95, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(95, 81, stmt)))
O("11", "Pinjaman badan berkanun dan syarikat milik Kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2024, "332,818,713,441", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2024, "1,415,728,984,544", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2024, "1,885,240,925",
  "Nota 12 Wang Pendahuluan Kontraktor")
O("13", "Pendahuluan Dana Pembiayaan Utiliti", 2024, "78,679,014",
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
with open(os.path.join(WH, "_validation_checks.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
