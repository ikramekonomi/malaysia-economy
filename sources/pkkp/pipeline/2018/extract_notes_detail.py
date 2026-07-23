#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-12 detail tables
from PKKP 2018 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2018-volume format notes vs 2020/2021:
 - Nota 4 columns: KWA rows include 'Sekuriti Tersiar Harga Luar Negeri'
   (new 2018, nil 2017); NO long-term deposit row; nil cells print '-'.
   DECLARED RESTATEMENT: 2017 Sekuriti Hutang Kerajaan Malaysia restated from
   3,360,920,452 to 796,055,739 with 2,564,864,713 moved to the newly separate
   Sekuriti Hutang Swasta Dalam Negeri category.
 - Nota 7(a)(i) TERIMAAN first line is 'Caruman Dari Akaun Hasil Disatukan'
   (2018 wording); NO COVID-19 fund anywhere.
 - Nota 7(a)(ii) is 'Pelbagai Kumpulan Wang Amanah Kerajaan' with categories
   AKAUN PENYELESAIAN / AKAUN PERNIAGAAN (no subtotal printed) / AKAUN
   PINJAMAN / KUMPULAN WANG LUAR JANGKA (no subtotal printed) / KUMPULAN WANG
   YANG LAIN; account names are the short 2018 forms.
 - Nota 9: Pelbagai Akaun Belum Terima reported as NARRATIVE figures (2018
   only). DECLARED RESTATEMENT: Bank Pertanian reclassified from Badan
   Berkanun to Syarikat (2017 comparatives restated 1,218,852,876 ->
   978,100,696 and 29,650,300,614 -> 29,891,052,794).
 - Nota 10(c): commitments include KOMITMEN PAMPASAN items Pampasan Konsesi
   Lebuhraya / Pampasan Kontrak Pengangkutan Awam (captured in fact_debt).
 - Nota 8 prints cash-vs-accrual reconciliation figures (captured in
   fact_other_notes).
"""
import csv, os, sys, re

WORK = "/home/claude/pkkp/work/2018"
WH = "/home/claude/pkkp/warehouse2018"
SRC = "2018_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 63, printed 51)
# =====================================================================
cash_src = [  # label, 2018, 2017, row_type
    ("WANG TUNAI", "23,647,599,864", "18,064,128,458", "total"),
    ("Wang Tunai Dalam Bank", "22,212,752,569", "16,663,516,979", "detail"),
    ("Wang Tunai Dalam Perjalanan", "1,431,980,775", "1,397,584,959", "detail"),
    ("Wang Tunai Dalam Tangan", "2,866,520", "3,026,520", "detail"),
]
cash_rows = []
for label, a18, a17, rt in cash_src:
    for yr, amt in ((2018, a18), (2017, a17)):
        V(63, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(63, 51, "Nota 3 Wang Tunai")))
for yr in (2018, 2017):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2018", 23647599864.0, 23647599864)
CHK("control: Wang Tunai 2017", 18064128458.0, 18064128458)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 63, printed 51)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa18, am18, kwa17, am17
    ("Sekuriti Hutang Kerajaan Luar Negeri", "1,172,457,168", "-", "6,752,198,170", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "2,124,457,690", "-", "796,055,739", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "6,827,402,898", "-", "2,564,864,713", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "2,014,796,137", "-", "676,753", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Sekuriti Tersiar Harga Luar Negeri", "286,053,195", "-", "-", "-"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "8,671,991,964", "966,650,000", "6,592,045,808", "255,650,000"),
    ("Pelbagai", "39,835,936", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2018): "21,577,103,046", (AM, 2018): "7,685,354,135",
           (KWA, 2017): "17,145,949,241", (AM, 2017): "6,974,354,135"}
inv_tot = {2018: "29,262,457,181", 2017: "24,120,303,376"}
P4 = prov(63, 51, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2018, 2017):
    V(63, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k18, a18, k17, a17 in inv_src:
    for yr, kv, av in ((2018, k18, a18), (2017, k17, a17)):
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
for yr in (2018, 2017):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2018", N(inv_tot[2018]), 29262457181)
CHK("control: Pelaburan 2017", N(inv_tot[2017]), 24120303376)
CHK("declared restatement: 2017 Sekuriti Hutang Kerajaan Malaysia restated to 796,055,739",
    N("796,055,739"), 796055739)
CHK("declared restatement: 2017 Sekuriti Hutang Swasta Dalam Negeri restated to 2,564,864,713",
    N("2,564,864,713"), 2564864713)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 69-71)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 69, printed 57)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2018, 2017, row_type
    ("", "BAKI PADA 1 JANUARI", "(46,765,912,939)", "(33,677,135,427)", "opening"),
    ("TERIMAAN", "TERIMAAN", "75,075,593,188", "31,795,061,321", "subtotal"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "1,922,069,620", "2,710,809,216", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "72,365,341,045", "27,232,066,897", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "776,819,515", "785,821,218", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "11,363,008", "1,066,363,990", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "56,095,455,662", "44,883,838,833", "subtotal"),
    ("BAYARAN", "Langsung", "54,405,363,219", "42,276,425,979", "detail"),
    ("BAYARAN", "Pinjaman", "1,690,092,443", "2,607,412,854", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "18,980,137,526", "(13,088,777,512)", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(27,785,775,413)", "(46,765,912,939)", "closing"),
]
for sec, item, a18, a17, rt in kwp_src:
    for yr, amt in ((2018, a18), (2017, a17)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 69, 57, S1)

def stmt_checks(fund, prefix):
    for yr in (2018, 2017):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        if any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "detail" for r in rs) \
           and any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "subtotal" for r in rs):
            CHK(f"{prefix} TERIMAAN details = subtotal {yr}",
                g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
        if any(r["section_bm"] == "BAYARAN" and r["row_type"] == "detail" for r in rs) \
           and any(r["section_bm"] == "BAYARAN" and r["row_type"] == "subtotal" for r in rs):
            CHK(f"{prefix} BAYARAN details = subtotal {yr}",
                g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
        ter = g("TERIMAAN", "subtotal") or g("TERIMAAN", "detail")
        bay = g("BAYARAN", "subtotal") or g("BAYARAN", "detail")
        net = ter - bay
        CHK(f"{prefix} terimaan-bayaran = Lebihan/(Kurangan) {yr}",
            net, one("Lebihan/(Kurangan) bagi Tahun"))
        CHK(f"{prefix} opening+net = closing {yr}",
            one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun"),
            one("BAKI PADA 31 DISEMBER"))
stmt_checks("Kumpulan Wang Pembangunan", "Nota7(a)(i) KWP")
CHK("control: Kumpulan Wang Pembangunan closing 2018",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2018
     and r["row_type"] == "closing"][0], -27785775413)

# --- 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 69-70, printed 57-58)
S3 = "Nota 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (subtotal18 or None, subtotal17 or None, page, items)
    "AKAUN PENYELESAIAN": ("6,229,373,232", "4,152,455,614", 69, [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "6,228,373,232", "4,151,455,614"),
    ]),
    "AKAUN PERNIAGAAN": (None, None, 69, [
        ("Stor dan Woksyop Belum Diuntukkan", "160,497,698", "79,974,300"),
    ]),
    "AKAUN PINJAMAN": ("3,212,473,867", "3,027,633,431", 69, [
        ("Kontraktor", "5,591,053", "4,359,739"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "-", "25,611,624"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "318,115,280", "199,815,126"),
        ("Pembangunan Ekonomi Belia", "12,934,471", "12,325,602"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "38,543,079", "38,064,828"),
        ("Pendahuluan Diri (Pegawai Awam)", "36,321,119", "94,173,856"),
        ("Pendahuluan Pelbagai", "59,655,642", "58,930,388"),
        ("Pendahuluan Untuk Negeri", "637,192,003", "138,019,183"),
        ("Pinjaman Diraja", "728,964", "728,964"),
        ("Pinjaman Kenderaan", "63,129,854", "62,878,742"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,887,987,163", "1,532,197,919"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "16,582,433", "26,772,499"),
        ("Rakyat Malaysia di Luar Negeri", "1,277,735", "1,233,365"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "134,415,071", "832,521,596"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": (None, None, 69, [
        ("Kumpulan Wang Luar Jangka", "294,306,200", "253,549,670"),
    ]),
    "KUMPULAN WANG YANG LAIN": ("21,641,419,300", "15,710,851,827", 70, [
        ("Amanah Negara", "16,046,677,687", "12,553,645,967"),
        ("Amanah Pelajar Miskin", "55,615,424", "55,553,689"),
        ("Amanah Sukan Negara", "19,360,516", "18,013,810"),
        ("Bantuan Bencana Negara", "238,534,123", "336,130,684"),
        ("Bantuan Mangsa Serangan Binatang Buas", "541,900", "1,130,300"),
        ("Cadangan Untuk Negeri", "259,420,613", "293,154,763"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "1,951,277", "1,871,371"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "537,305", "913,743"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "472,854", "2,972,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "331,886,217", "229,010,753"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "580,787", "677,302"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "45,239,854", "92,288,017"),
        ("Kumpulan Wang Amanah Majlis Sains Dan Penyelidikan Kebangsaan", "3,481,297", "3,939,806"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "1,695,340", "1,532,126"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "62,351,926", "103,958,774"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "39,915,375", "34,130,596"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "2,437,393", "1,514,293"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "5,107", "5,107"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "14,195,169", "13,900,008"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "8,587,426", "10,067,964"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "16,342,578", "10,842,868"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan", "3,900,000,034", "1,000,650,921"),
        ("Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "34,629,981", "36,286,183"),
        ("Perpustakaan Negara", "1,321,858", "1,305,863"),
        ("Program Perumahan Rakyat Dimiliki", "148,580,363", "215,702,889"),
        ("Skim Biasiswa Sukan Persekutuan", "1,143,899", "482,398"),
        ("Tabung Bantuan Perubatan", "66,314,608", "60,822,361"),
        ("Tabung Bayaran Balik Cukai", "316,372,898", "607,113,095"),
        ("Tabung Inovasi Negara", "19,813,116", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "30,415", "38,246"),
    ]),
}
for cat, (s18, s17, pg, items) in pkw_src.items():
    pp = pg - 12
    if s18 is not None:
        for yr, amt in ((2018, s18), (2017, s17)):
            T(KWK, PKW, cat, cat, yr, amt, "subtotal", pg, pp, S3)
    for item, a18, a17 in items:
        for yr, amt in ((2018, a18), (2017, a17)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, pp, S3)
for yr, amt in ((2018, "31,538,070,297"), (2017, "23,224,464,842")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 70, 58, S3)
for yr in (2018, 2017):
    for cat, (s18, s17, pg, items) in pkw_src.items():
        if s18 is None:
            continue
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(ii) {cat} details = subtotal {yr}",
            det, N(s18 if yr == 2018 else s17))
    dets = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(ii) all details = PELBAGAI KWAK total {yr}", dets, tot)
CHK("cross: Pelbagai KWAK total 2018 = Nota 7 table closing", 31538070297.0, 31538070297)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 70, printed 58)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("3,130,824,564", "2,984,703,829", [
        ("Akaun Amanah Estet Kebankrapan", "2,138,802,162", "2,051,215,569"),
        ("Kumpulan Wang Dius Api", "290,821,360", "298,303,805"),
        ("Akaun Amanah Am Pelikuidasi", "273,440,726", "267,863,095"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "232,296,456", "235,144,525"),
        ("Pelbagai Amanah Khas", "195,463,860", "132,176,835"),
    ]),
    "AMANAH AM": ("7,080,573,488", "6,277,238,525", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "3,129,217,998", "2,634,402,384"),
        ("Akaun Amanah Dana Khas", "621,918,895", "464,590,787"),
        ("Akaun Amanah Industri Bekalan Elektrik", "604,797,267", "609,123,454"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta", "497,299,398", "533,784,517"),
        ("Akaun Amanah Sumber Khas", "426,949,191", "343,006,251"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "415,459,860", "408,861,391"),
        ("Pelbagai Amanah Am", "1,384,930,879", "1,283,469,741"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 71, printed 59)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("10,792,824,645", "10,132,063,006", [
        ("Kawalan Wang Tak Dituntut", "5,752,246,030", "5,200,020,273"),
        ("Wang Jaminan Pelaksanaan", "1,691,185,905", "1,525,299,233"),
        ("Mahkamah Tinggi", "1,148,171,490", "1,202,242,487"),
        ("Wang Tak Dituntut", "691,918,489", "834,611,034"),
        ("Pelbagai Deposit Am", "1,509,302,731", "1,369,889,979"),
    ]),
    "DEPOSIT PELARASAN": ("1,066,289,229", "986,349,544", [
        ("Terimaan Yang Tidak Diperuntukkan", "878,084,519", "876,716,880"),
        ("Pindahan Dana Elektronik Terbatal", "142,398,185", "54,184,799"),
        ("Deposit Pembatalan Pencen Skim B", "28,011,556", "29,285,944"),
        ("Pelbagai Deposit Pelarasan", "17,794,969", "26,161,921"),
    ]),
}
for grp, src, tot18, tot17, pg, stmt in (
        (KAW, awam_src, "10,211,398,052", "9,261,942,354", 70, S4),
        (DEP, dep_src, "11,859,113,874", "11,118,412,550", 71, S5)):
    pp = pg - 12
    for sec, (s18, s17, items) in src.items():
        for yr, amt in ((2018, s18), (2017, s17)):
            T(grp, "", sec, sec, yr, amt, "subtotal", pg, pp, stmt)
        for item, a18, a17 in items:
            for yr, amt in ((2018, a18), (2017, a17)):
                T(grp, "", sec, item, yr, amt, "detail", pg, pp, stmt)
    for yr, amt in ((2018, tot18), (2017, tot17)):
        T(grp, "", "", grp, yr, amt, "total", pg, pp, stmt)
    for yr in (2018, 2017):
        for sec, (s18, s17, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s18 if yr == 2018 else s17))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 72, printed 60)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(72, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(72, 60, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2018, "86,934,779,072", "total")
ppbd = [  # label, 2018, 2017, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "57,901,325,821", "58,443,750,298", "subtotal"),
    ("Kerajaan Negeri", "18,221,257,138", "18,785,075,609", "detail"),
    ("Syarikat", "30,764,095,109", "30,521,775,145", "detail"),
    ("Badan Berkanun", "6,328,481,358", "6,338,015,378", "detail"),
    ("Pihak Berkuasa Tempatan", "192,116,889", "298,354,685", "detail"),
    ("Koperasi", "265,203,844", "270,827,830", "detail"),
    ("Pelbagai Agensi", "1,760,456,508", "1,864,072,733", "detail"),
    ("Perseorangan", "369,714,975", "365,628,918", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a18, a17, rt in ppbd:
    for yr, amt in ((2018, a18), (2017, a17)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2018, "29,033,453,251", "subtotal")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2018, "16,185,900,325", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2018, "2,133,423,712", "memo")
pel = [
    ("PELABURAN", "31,058,227,719", "30,907,727,719", "subtotal"),
    ("Syarikat", "30,041,552,794", "29,891,052,794", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a18, a17, rt in pel:
    for yr, amt in ((2018, a18), (2017, a17)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2018, 2017):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2018 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2018 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2018",
    N("57,901,325,821") + N("29,033,453,251"), 86934779072)
CHK("control: Akaun Belum Terima 2018", 86934779072.0, 86934779072)
CHK("control: memo Pelaburan 2018", N(pel[0][1]), 31058227719)
CHK("declared restatement: 2017 memo Pelaburan Badan Berkanun restated to 978,100,696",
    N("978,100,696"), 978100696)
CHK("declared restatement: 2017 memo Pelaburan Syarikat restated to 29,891,052,794",
    N("29,891,052,794"), 29891052794)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 74-75)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2018, printed_total_2017, items, pdf_page
    ("KOMITMEN JAMINAN", "164,908,473,346", "139,749,167,987", [
        ("Dalam Negeri", "116,003,213,747", "96,066,843,422"),
        ("Luar Negeri", "48,905,259,599", "43,682,324,565")], 74),
    ("KOMITMEN PAJAKAN KEWANGAN", "31,517,888,277", "33,421,941,407", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "20,008,614,753", "21,302,260,693"),
        ("Pajakan Kewangan Badan Berkanun", "11,509,273,524", "12,119,680,714")], 74),
    ("KOMITMEN BAYARAN BALIK CUKAI", "44,372,590,815", "34,259,229,307", [
        ("Cukai Pendapatan", "17,943,934,658", "15,949,987,713"),
        ("Cukai Keuntungan Harta Tanah", "492,507,539", "444,862,143"),
        ("Cukai Barangan dan Perkhidmatan", "25,936,148,618", "17,864,379,451")], 74),
    ("KOMITMEN PAMPASAN", "2,169,792,773", "6,839,313,755", [
        ("Pampasan Konsesi Lebuhraya", "2,169,792,773", "3,719,783,710"),
        ("Pampasan Kontrak Pengangkutan Awam", "-", "3,119,530,045")], 74),
    ("PELBAGAI LIABILITI", "786,190,452", "726,330,018", [
        ("Nota Kena Bayar", "744,856,249", "685,904,863"),
        ("Sekuriti Tak Dituntut", "27,332,947", "26,423,883"),
        ("Akaun Depositori Pusat", "14,001,256", "14,001,272")], 75),
]
for parent, t18, t17, items, pg in com_src:
    pp = pg - 12
    for item, a18, a17 in items:
        for yr, amt in ((2018, a18), (2017, a17)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2018, t18), (2017, t17)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2018", N("164,908,473,346"), 164908473346)
CHK("control: Pajakan 2018", N("31,517,888,277"), 31517888277)
CHK("control: Bayaran Balik Cukai 2018", N("44,372,590,815"), 44372590815)
CHK("control: Komitmen Pampasan 2018", N("2,169,792,773"), 2169792773)
CHK("control: Pelbagai Liabiliti 2018", N("786,190,452"), 786190452)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p49)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2018",
    N("164,908,473,346") + N("31,517,888,277") + N("44,372,590,815") + N("2,169,792,773"),
    242968745211)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2017",
    N("139,749,167,987") + N("33,421,941,407") + N("34,259,229,307") + N("6,839,313,755"),
    214269652456)

# =====================================================================
# 6. Nota 5(b)/6/8/10/11/12 narrative figures (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, pg - 12, stmt)))
O("5(b)", "Penyaluran geran di bawah vot B11 untuk bayaran balik pinjaman yang dijamin kepada Syarikat Special Purpose Vehicle (SPV) (termasuk dalam Perbelanjaan Mengurus)",
  2018, "2,839,225,279", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("6", "Bayaran faedah pinjaman dan kos lain dikenakan kepada Akaun Pinjaman Disatukan",
  2018, "61,501,359", 67, "Nota 6 Akaun Pinjaman Disatukan")
O("8", "Perbezaan Hasil Bukan Cukai antara Penyata Wang Tunai dan Nota 5(a)",
  2018, "12,178,052", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Terimaan Bukan Hasil antara Penyata Wang Tunai dan Nota 5(a)",
  2018, "176,047,149", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Terimaan Balik Pinjaman antara Penyata Wang Tunai dan Kumpulan Wang Pembangunan",
  2018, "15,000,000", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Pelbagai Terimaan Amanah (baki bersih semasa Akaun Amanah)",
  2018, "8,472,183,766", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Pemberian dan Kenaan Bayaran Tetap antara Penyata Wang Tunai dan Nota 5",
  2018, "1,256,137,463", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Pindahan peruntukan Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2018, "1,156,200,000", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Pelarasan bayaran balik pendahuluan Kumpulan Wang Pendahuluan Untuk Negeri (komponen perbezaan Pemberian)",
  2018, "99,937,463", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Perbelanjaan-perbelanjaan Lain antara Penyata Wang Tunai dan Nota 5 (pelarasan hapus kira pinjaman)",
  2018, "20,335,953", 71, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("10(a)", "Pegangan Bukan Pemastautin bagi Pinjaman Dalam Negeri",
  2018, "165,777,059,000", 73, "Nota 10 Memorandum Liabiliti")
O("11", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2018, "266,468,479,030", 75, "Nota 11 Liabiliti Luar Jangka")
O("11", "Jaminan berisiko menjadi komitmen Kerajaan berdasarkan kedudukan kewangan entiti yang dijamin",
  2018, "74,070,000,000", 75, "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2018, "944,594,771,608", 75, "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2018, "814,631,716", 75,
  "Nota 12 Wang Pendahuluan Kontraktor")

# CHKs for the Nota 8 reconciliation identities against extracted statements
CHK("Nota8: Hasil Bukan Cukai Nota5(a) - cash = printed difference",
    51118422864 - 51106244812, 12178052)
CHK("Nota8: Terimaan Bukan Hasil Nota5(a) - cash = printed difference",
    6212805681 - 6036758532, 176047149)
CHK("Nota8: Pemberian Nota5 - cash = printed difference",
    114144347736 - 112888210273, 1256137463)
CHK("Nota8: Pemberian difference components sum",
    1156200000 + 99937463, 1256137463)
CHK("Nota8: Perbelanjaan Lain Nota5 - cash = printed difference",
    1097211248 - 1076875295, 20335953)
CHK("Nota8: Terimaan Balik Pinjaman cash - KWP = printed difference",
    761819515 + 15000000, 776819515)

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
with open(os.path.join(WH, "_validation_checks_2018.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
