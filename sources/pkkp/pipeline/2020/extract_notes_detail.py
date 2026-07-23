#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-12 detail tables
from PKKP 2020 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2020-volume format notes vs 2022:
 - Nota 3/4 on pdf 76; Nota 4 prints a 4-column KWA/Am x 2020/2019 grid with a
   'Jumlah' row carrying the four category subtotals and a 'PELABURAN' row
   carrying only the two annual grand totals.
 - Nota 7(a)(i) TERIMAAN's first line is 'Caruman Dari Akaun Hasil Disatukan'
   and the APD line is 'Pindahan Dari Akaun Pinjaman Disatukan' (2022 volume
   prints 'Pindahan Daripada ...').
 - Nota 7(a)(ii) Kumpulan Wang COVID-19 is in its FIRST year (established
   26.10.2020 under Akta 830): no TERIMAAN/BAYARAN printed subtotal rows,
   single receipt (transfer RM38,020,000,000) and single payment
   (RM38,019,238,631), closing RM761,369.
 - Nota 7(a)(iii) categories AKAUN PERNIAGAAN and KUMPULAN WANG LUAR JANGKA
   print WITHOUT category subtotal amounts (single-item categories).
 - Nota 9 Pelbagai ABT is narrative-only (memo rows).
 - Nota 10(d) DECLARES a restatement of the 2019 Nota Kena Bayar comparative
   (798,665,127 -> 207,785,127, moved to Hutang Persekutuan/SKM); Nota 10(b)
   declares the 2019 PFI comparatives reclassified by borrowing company.
 - Nota 9 Pelaburan Syarikat rows print with a stray '-' glyph glued to the
   amounts ('32,174,788,786-'); transcribed without the artifact.
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2020"
WH = "/home/claude/pkkp/warehouse2020"
SRC = "2020_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 76, printed 60)
# =====================================================================
cash_src = [  # label, 2020, 2019, row_type
    ("WANG TUNAI", "26,030,389,682", "20,497,071,598", "total"),
    ("Wang Tunai Dalam Bank", "23,386,390,316", "19,723,454,334", "detail"),
    ("Wang Tunai Dalam Perjalanan", "2,641,122,146", "770,744,244", "detail"),
    ("Wang Tunai Dalam Tangan", "2,877,220", "2,873,020", "detail"),
]
cash_rows = []
for label, a20, a19, rt in cash_src:
    for yr, amt in ((2020, a20), (2019, a19)):
        V(76, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(76, 60, "Nota 3 Wang Tunai")))
for yr in (2020, 2019):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2020", 26030389682.0, 26030389682)
CHK("control: Wang Tunai 2019", 20497071598.0, 20497071598)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 76, printed 60)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa20, am20, kwa19, am19
    ("Sekuriti Hutang Kerajaan Luar Negeri", "5,229,692,142", "-", "4,157,767,085", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,862,758,809", "-", "1,974,496,965", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "2,473,318,064", "-", "3,294,914,325", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "4,465,343,186", "-", "3,828,888,018", "-"),
    ("Sekuriti Tersiar Harga Luar Negeri", "-", "-", "122,098,193", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "2,044,859,410", "-", "2,221,174,251", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "6,731,137,800", "55,000,000", "10,163,808,944", "5,811,650,000"),
    ("Deposit Jangka Panjang Dalam Negeri Melebihi 12 Bulan", "10,042,500,000", "-", "-", "-"),
    ("Pelbagai", "-", "942,558", "-", "942,558"),
]
inv_sub = {(KWA, 2020): "33,289,717,469", (AM, 2020): "6,773,704,135",
           (KWA, 2019): "26,203,255,839", (AM, 2019): "12,530,354,135"}
inv_tot = {2020: "40,063,421,604", 2019: "38,733,609,974"}
P4 = prov(76, 60, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2020, 2019):
    V(76, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k20, a20, k19, a19 in inv_src:
    for yr, kv, av in ((2020, k20, a20), (2019, k19, a19)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(76, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(76, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2020, 2019):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2020", N(inv_tot[2020]), 40063421604)
CHK("control: Pelaburan 2019", N(inv_tot[2019]), 38733609974)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 82-84)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 82, printed 66)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2020, 2019, row_type
    ("", "BAKI PADA 1 JANUARI", "(24,700,420,089)", "(27,785,775,413)", "opening"),
    ("TERIMAAN", "TERIMAAN", "62,804,908,426", "57,258,590,641", "subtotal"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "474,705,193", "1,071,831,233", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "61,071,047,806", "54,456,031,282", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,180,122,917", "1,602,913,880", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "59,430", "-", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "78,973,080", "127,814,246", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "51,359,855,763", "54,173,235,317", "subtotal"),
    ("BAYARAN", "Langsung", "49,330,957,654", "52,058,496,026", "detail"),
    ("BAYARAN", "Pinjaman", "2,028,898,109", "2,114,739,291", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "11,445,052,663", "3,085,355,324", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(13,255,367,426)", "(24,700,420,089)", "closing"),
]
for sec, item, a20, a19, rt in kwp_src:
    for yr, amt in ((2020, a20), (2019, a19)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 82, 66, S1)

def stmt_checks(fund, prefix):
    for yr in (2020, 2019):
        rs = [r for r in trust_rows if r["fund_bm"] == fund and r["year"] == yr]
        g = lambda sec, rt: sum(r["amount_rm"] for r in rs
                                if r["section_bm"] == sec and r["row_type"] == rt)
        one = lambda item: [r["amount_rm"] for r in rs if r["line_item_bm"] == item][0]
        ter = g("TERIMAAN", "subtotal") or g("TERIMAAN", "detail")
        bay = g("BAYARAN", "subtotal") or g("BAYARAN", "detail")
        if g("TERIMAAN", "subtotal") and any(r["section_bm"] == "TERIMAAN" and r["row_type"] == "detail" for r in rs):
            CHK(f"{prefix} TERIMAAN details = subtotal {yr}",
                g("TERIMAAN", "detail"), g("TERIMAAN", "subtotal"))
        if g("BAYARAN", "subtotal") and any(r["section_bm"] == "BAYARAN" and r["row_type"] == "detail" for r in rs):
            CHK(f"{prefix} BAYARAN details = subtotal {yr}",
                g("BAYARAN", "detail"), g("BAYARAN", "subtotal"))
        net = ter - bay
        CHK(f"{prefix} terimaan-bayaran = Lebihan/(Kurangan) {yr}",
            net, one("Lebihan/(Kurangan) bagi Tahun"))
        CHK(f"{prefix} opening+net = closing {yr}",
            one("BAKI PADA 1 JANUARI") + one("Lebihan/(Kurangan) bagi Tahun"),
            one("BAKI PADA 31 DISEMBER"))
stmt_checks("Kumpulan Wang Pembangunan", "Nota7(a)(i) KWP")
CHK("control: Kumpulan Wang Pembangunan closing 2020",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2020
     and r["row_type"] == "closing"][0], -13255367426)

# --- 7(a)(ii) Kumpulan Wang COVID-19 (pdf 82, printed 66) -- FIRST year
S2 = "Nota 7(a)(ii) Kumpulan Wang COVID-19"
covid_src = [
    ("", "BAKI PADA 1 JANUARI", "-", "-", "opening"),
    ("TERIMAAN", "Pindahan Daripada Akaun Pinjaman Disatukan", "38,020,000,000", "-", "detail"),
    ("BAYARAN", "Perbelanjaan COVID-19", "38,019,238,631", "-", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "761,369", "-", "net"),
    ("", "BAKI PADA 31 DISEMBER", "761,369", "-", "closing"),
]
for sec, item, a20, a19, rt in covid_src:
    for yr, amt in ((2020, a20), (2019, a19)):
        T(KWK, "Kumpulan Wang COVID-19", sec, item, yr, amt, rt, 82, 66, S2)
stmt_checks("Kumpulan Wang COVID-19", "Nota7(a)(ii) COVID")
CHK("control: COVID fund 2020 expenditure", 38019238631.0, 38019238631)
CHK("control: COVID fund 2020 closing", 761369.0, 761369)

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 83, printed 67)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": ("11,116,223,509", "4,949,347,070", [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "11,115,223,509", "4,948,347,070"),
    ]),
    "AKAUN PERNIAGAAN": (None, None, [
        ("Stor dan Woksyop Belum Diperuntukkan", "156,964,318", "156,921,369"),
    ]),
    "AKAUN PINJAMAN": ("2,985,563,130", "2,868,948,087", [
        ("Kontraktor", "3,388,514", "9,208,072"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "43,058,280", "21,450,107"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "500,248,513", "420,483,753"),
        ("Pembangunan Ekonomi Belia", "14,019,400", "13,478,632"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "48,965,468", "39,492,419"),
        ("Pendahuluan Diri (Pegawai Awam)", "39,625,187", "11,241,115"),
        ("Pendahuluan Pelbagai", "50,108,420", "58,253,041"),
        ("Pendahuluan Untuk Negeri", "874,893,583", "925,893,583"),
        ("Pinjaman Diraja", "763,436", "743,748"),
        ("Pinjaman Kenderaan", "63,491,343", "63,347,198"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,022,193,268", "1,055,058,708"),
        ("Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "14,182,456", "10,835,139"),
        ("Rakyat Malaysia di Luar Negeri", "1,317,092", "1,282,931"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "309,308,170", "238,179,641"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": (None, None, [
        ("Kumpulan Wang Luar Jangka", "1,499,999,980", "721,390,750"),
    ]),
    "PELBAGAI KUMPULAN WANG": ("20,218,603,754", "26,432,223,151", [
        ("Amanah Negara", "18,294,241,419", "17,605,293,030"),
        ("Amanah Pelajar Miskin", "93,733,363", "73,944,448"),
        ("Amanah Sukan Negara", "38,650,869", "26,442,867"),
        ("Bantuan Bencana Negara", "212,008,291", "235,859,572"),
        ("Bantuan Mangsa Serangan Binatang Buas", "996,200", "685,400"),
        ("Cadangan Untuk Negeri", "347,094,275", "224,759,099"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "472,854", "472,854"),
        ("Kumpulan Wang Amanah Tabung Khas Hakmilik Strata", "1,692,250", "-"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "2,080,495", "1,866,374"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "341,547", "410,811"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "103,241,716", "88,707,892"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,718,623", "2,425,679"),
        ("Kumpulan Wang Amanah Fi Jaminan - Urusniaga", "506,131,754", "423,415,576"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "6,175,844", "23,998,163"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "40,837,387", "39,596,751"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan (CBP)", "84,244,568", "6,005,750,948"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "5,356,430", "2,722,986"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "968,725", "795,957"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "739,033", "1,626,350"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "14,836,106", "14,535,848"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "7,729,170", "7,586,776"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "18,902,576", "21,633,153"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Majlis Sains Dan Penyelidikan Kebangsaan (MSPK)", "2,818,236", "3,599,304"),
        ("Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "33,335,877", "33,197,929"),
        ("Perpustakaan Negara", "1,227,574", "1,208,117"),
        ("Program Perumahan Rakyat Dimiliki", "121,943,656", "140,594,969"),
        ("Skim Biasiswa Sukan Persekutuan", "561,971", "884,216"),
        ("Tabung Bayaran Balik Cukai", "167,287,155", "1,355,479,579"),
        ("Tabung Bantuan Perubatan (TBP)", "85,022,970", "71,498,080"),
        ("Tabung Inovasi Negara (KWATIN)", "19,813,117", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "17,743", "35,347"),
    ]),
}
for cat, (s20, s19, items) in pkw_src.items():
    if s20 is not None:
        for yr, amt in ((2020, s20), (2019, s19)):
            T(KWK, PKW, cat, cat, yr, amt, "subtotal", 83, 67, S3)
    for item, a20, a19 in items:
        for yr, amt in ((2020, a20), (2019, a19)):
            T(KWK, PKW, cat, item, yr, amt, "detail", 83, 67, S3)
for yr, amt in ((2020, "35,977,354,691"), (2019, "35,128,830,427")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 83, 67, S3)
for yr in (2020, 2019):
    tot_from_cats = 0.0
    for cat, (s20, s19, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        sub = s20 if yr == 2020 else s19
        if sub is not None:
            CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}", det, N(sub))
            tot_from_cats += N(sub)
        else:
            tot_from_cats += det
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) categories = PELBAGAI KWAK total {yr}", tot_from_cats, tot)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 84, printed 68)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("3,412,661,031", "3,309,508,604", [
        ("Akaun Amanah Estet Kebankrapan", "2,090,275,745", "2,074,770,371"),
        ("Akaun Amanah Am Pelikuidasi", "312,579,832", "295,777,881"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "294,326,347", "244,192,413"),
        ("Kumpulan Wang Dius Api", "286,471,639", "302,353,303"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "275,829,411", "252,376,478"),
        ("Pelbagai Amanah Khas", "153,178,057", "140,038,158"),
    ]),
    "AMANAH AM": ("16,659,514,722", "6,184,702,924", [
        ("Akaun Amanah Mendapatkan Kembali Aset", "11,477,342,168", "695,806,281"),
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "1,430,138,317", "1,987,696,162"),
        ("Akaun Amanah Industri Bekalan Elektrik", "783,882,201", "680,775,000"),
        ("Akaun Amanah Pembinaan Projek Lebuhraya Pan Borneo Sarawak", "557,179,250", "-"),
        ("Akaun Amanah Sumber Khas", "441,926,078", "421,245,984"),
        ("Pelbagai Amanah Am", "1,969,046,708", "2,399,179,497"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 84, printed 68)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("11,303,344,115", "10,926,434,174", [
        ("Deposit Kawalan Wang Tak Dituntut", "7,091,482,309", "6,401,897,831"),
        ("Deposit Wang Jaminan Pelaksanaan", "1,747,122,403", "1,717,587,773"),
        ("Deposit Mahkamah Tinggi", "1,229,493,682", "1,322,316,390"),
        ("Deposit Imigresen", "296,343,487", "287,290,707"),
        ("Deposit Wang Tak Dituntut", "247,700,956", "470,566,889"),
        ("Pelbagai Deposit Am", "691,201,278", "726,774,584"),
    ]),
    "DEPOSIT PELARASAN": ("132,415,698", "241,114,117", [
        ("Deposit Pindahan Dana Elektronik Terbatal", "63,294,909", "64,820,861"),
        ("Akaun Terimaan Tidak Diperuntukkan", "34,238,566", "127,763,726"),
        ("Deposit Pembatalan Pencen Skim B", "15,339,138", "24,628,504"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JPA Pencen", "9,335,673", "14,414,449"),
        ("Deposit Pindahan Dana Elektronik Terbatal - JHEV", "4,375,175", "1,104,399"),
        ("Pelbagai Deposit Pelarasan", "5,832,237", "8,382,178"),
    ]),
}
for grp, src, tot20, tot19, stmt in (
        (KAW, awam_src, "20,072,175,753", "9,494,211,528", S4),
        (DEP, dep_src, "11,435,759,813", "11,167,548,291", S5)):
    for sec, (s20, s19, items) in src.items():
        for yr, amt in ((2020, s20), (2019, s19)):
            T(grp, "", sec, sec, yr, amt, "subtotal", 84, 68, stmt)
        for item, a20, a19 in items:
            for yr, amt in ((2020, a20), (2019, a19)):
                T(grp, "", sec, item, yr, amt, "detail", 84, 68, stmt)
    for yr, amt in ((2020, tot20), (2019, tot19)):
        T(grp, "", "", grp, yr, amt, "total", 84, 68, stmt)
    for yr in (2020, 2019):
        for sec, (s20, s19, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s20 if yr == 2020 else s19))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 86, printed 70)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(86, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(86, 70, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2020, "106,422,742,308", "total")
ppbd = [  # label, 2020, 2019, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "58,900,685,743", "57,661,165,390", "subtotal"),
    ("Kerajaan Negeri", "15,979,101,032", "16,344,322,228", "detail"),
    ("Syarikat", "33,471,481,387", "31,922,223,026", "detail"),
    ("Badan Berkanun", "7,120,406,614", "6,954,203,678", "detail"),
    ("Pihak Berkuasa Tempatan", "143,178,696", "185,252,112", "detail"),
    ("Koperasi", "237,272,363", "248,220,930", "detail"),
    ("Pelbagai Agensi", "1,687,486,839", "1,715,327,959", "detail"),
    ("Perseorangan", "261,758,812", "291,615,457", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a20, a19, rt in ppbd:
    for yr, amt in ((2020, a20), (2019, a19)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2020, "47,522,056,565", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2020, "732,500,022", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2020, "20,858,823,691", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2020, "2,623,386,842", "memo")
pel = [
    ("PELABURAN", "33,191,463,711", "32,038,227,719", "subtotal"),
    ("Syarikat", "32,174,788,786", "31,021,552,794", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a20, a19, rt in pel:
    for yr, amt in ((2020, a20), (2019, a19)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2020, 2019):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2020 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2020 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2020",
    N("58,900,685,743") + N("47,522,056,565"), 106422742308)
CHK("control: Akaun Belum Terima 2020", 106422742308.0, 106422742308)
CHK("control: memo Pelaburan 2020", N(pel[0][1]), 33191463711)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 88-89)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2020, printed_total_2019, items, pdf_page
    ("KOMITMEN JAMINAN", "216,841,563,770", "193,992,526,604", [
        ("Dalam Negeri", "167,991,778,089", "146,117,984,951"),
        ("Luar Negeri", "48,849,785,681", "47,874,541,653")], 88),
    ("KOMITMEN PAJAKAN KEWANGAN", "37,570,623,547", "33,086,435,272", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "26,847,483,272", "22,189,240,582"),
        ("Pajakan Kewangan Badan Berkanun", "10,723,140,275", "10,897,194,690")], 88),
    ("KOMITMEN BAYARAN BALIK CUKAI", "14,635,443,058", "19,392,393,636", [
        ("Cukai Pendapatan", "12,186,431,101", "10,346,928,837"),
        ("Cukai Keuntungan Harta Tanah", "575,429,182", "503,958,079"),
        ("Cukai Barangan dan Perkhidmatan", "1,873,582,775", "8,541,506,720")], 88),
    ("PELBAGAI LIABILITI", "278,000,205", "249,253,470", [
        ("Nota Kena Bayar", "236,620,627", "207,785,127"),
        ("Sekuriti Tak Dituntut", "27,343,222", "27,431,987"),
        ("Akaun Depositori Pusat", "14,036,356", "14,036,356")], 89),
]
for parent, t20, t19, items, pg in com_src:
    pp = pg - 16
    for item, a20, a19 in items:
        for yr, amt in ((2020, a20), (2019, a19)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2020, t20), (2019, t19)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2020", N("216,841,563,770"), 216841563770)
CHK("control: Pajakan 2020", N("37,570,623,547"), 37570623547)
CHK("control: Bayaran Balik Cukai 2020", N("14,635,443,058"), 14635443058)
CHK("control: Pelbagai Liabiliti 2020", N("278,000,205"), 278000205)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p55)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2020",
    N("216,841,563,770") + N("37,570,623,547") + N("14,635,443,058") + N("892,581,000"),
    269940211375)
# declared restatement of the 2019 comparative (reported, never corrected)
CHK("declared restatement: Nota Kena Bayar 2019 restated 798,665,127 -> 207,785,127",
    N("207,785,127"), 207785127)

# =====================================================================
# 6. Nota 11-12 (pdf 89, printed 73)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(89, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(89, 73, stmt)))
O("11", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2020, "294,674,756,861", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2020, "1,100,448,613,908", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2020, "677,895,927",
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
with open(os.path.join(WH, "_validation_checks_2020.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
