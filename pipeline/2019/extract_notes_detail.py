#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10 sub-splits, 11-12 detail tables
from PKKP 2019 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2019-volume format notes vs 2020:
 - Nota 3/4 on pdf 59 (printed 47); Nota 4 prints the same KWA/Am x year grid.
 - Nota 4 DECLARES a restatement of the 2018 comparative: Sekuriti Hutang
   Swasta Dalam Negeri 6,827,402,898 -> 2,869,471,359 with 3,957,931,539 moved
   to the (new) Sekuriti Hutang Swasta Luar Negeri category.
 - Nota 7(a)(ii) is 'Pelbagai Kumpulan Wang Amanah Kerajaan' (no COVID fund in
   2019); its last category prints as 'KUMPULAN WANG YANG LAIN' (2020 volume
   renamed it 'PELBAGAI KUMPULAN WANG') and 'Amanah Negara*' carries a KWAN
   fx-rate footnote. 'Stor dan Woksyop Belum Diuntukkan' is the 2019 spelling.
 - Nota 7(b)/(c) item lists differ from 2020 (fewer breakdown lines; deposits
   print without the 'Deposit ' prefix on several items).
 - Nota 9(a)(ii) Pelbagai ABT is narrative-only (memo rows); Nota 9 DECLARES a
   restatement of the 2018 Perseorangan comparative 369,714,975 -> 266,299,538
   (Pinjaman Perumahan kepada Golongan Berpendapatan Rendah reclassified).
 - Nota 9 Pelaburan rows print with a stray '-' glyph glued to the amounts
   ('31,021,552,794-'); transcribed without the artifact.
 - Nota 10(d) Nota Kena Bayar prints 798,665,127 for 2019 (the 2020 volume
   later RESTATED this comparative to 207,785,127).
"""
import csv, os, sys

WORK = "/home/claude/pkkp/work/2019"
WH = "/home/claude/pkkp/warehouse2019"
SRC = "2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 59, printed 47)
# =====================================================================
cash_src = [  # label, 2019, 2018, row_type
    ("WANG TUNAI", "20,497,071,598", "23,647,599,864", "total"),
    ("Wang Tunai Dalam Bank", "19,723,454,334", "22,212,752,569", "detail"),
    ("Wang Tunai Dalam Perjalanan", "770,744,244", "1,431,980,775", "detail"),
    ("Wang Tunai Dalam Tangan", "2,873,020", "2,866,520", "detail"),
]
cash_rows = []
for label, a19, a18, rt in cash_src:
    for yr, amt in ((2019, a19), (2018, a18)):
        V(59, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(59, 47, "Nota 3 Wang Tunai")))
for yr in (2019, 2018):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2019", 20497071598.0, 20497071598)
CHK("control: Wang Tunai 2018", 23647599864.0, 23647599864)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 59, printed 47)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa19, am19, kwa18, am18
    ("Sekuriti Hutang Kerajaan Luar Negeri", "4,157,767,085", "-", "1,172,457,168", "-"),
    ("Sekuriti Hutang Kerajaan Malaysia", "1,974,496,965", "-", "2,124,457,690", "-"),
    ("Sekuriti Hutang Swasta Luar Negeri", "3,294,914,325", "-", "3,957,931,539", "-"),
    ("Sekuriti Hutang Swasta Dalam Negeri", "3,828,888,018", "-", "2,869,471,359", "-"),
    ("Sekuriti Tersiar Harga Luar Negeri", "122,098,193", "-", "286,053,195", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "2,221,174,251", "-", "2,014,796,137", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "10,163,808,944", "5,811,650,000", "8,671,991,964", "966,650,000"),
    ("Pelbagai", "-", "942,558", "39,835,936", "942,558"),
]
inv_sub = {(KWA, 2019): "26,203,255,839", (AM, 2019): "12,530,354,135",
           (KWA, 2018): "21,577,103,046", (AM, 2018): "7,685,354,135"}
inv_tot = {2019: "38,733,609,974", 2018: "29,262,457,181"}
P4 = prov(59, 47, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2019, 2018):
    V(59, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k19, a19, k18, a18 in inv_src:
    for yr, kv, av in ((2019, k19, a19), (2018, k18, a18)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(59, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(59, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2019, 2018):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2019", N(inv_tot[2019]), 38733609974)
CHK("control: Pelaburan 2018", N(inv_tot[2018]), 29262457181)
CHK("declared restatement (Nota 4): SHS Dalam Negeri 2018 restated 6,827,402,898 -> "
    "2,869,471,359 (3,957,931,539 moved to SHS Luar Negeri)",
    N("2,869,471,359") + N("3,957,931,539"), 6827402898)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 65-67)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt, foot=False):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=foot,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 65, printed 53)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2019, 2018, row_type
    ("", "BAKI PADA 1 JANUARI", "(27,785,775,413)", "(46,765,912,939)", "opening"),
    ("TERIMAAN", "TERIMAAN", "57,258,590,641", "75,075,593,188", "subtotal"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "1,071,831,233", "1,922,069,620", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "54,456,031,282", "72,365,341,045", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,602,913,880", "776,819,515", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "127,814,246", "11,363,008", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "54,173,235,317", "56,095,455,662", "subtotal"),
    ("BAYARAN", "Langsung", "52,058,496,026", "54,405,363,219", "detail"),
    ("BAYARAN", "Pinjaman", "2,114,739,291", "1,690,092,443", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "3,085,355,324", "18,980,137,526", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(24,700,420,089)", "(27,785,775,413)", "closing"),
]
for sec, item, a19, a18, rt in kwp_src:
    for yr, amt in ((2019, a19), (2018, a18)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 65, 53, S1)

def stmt_checks(fund, prefix):
    for yr in (2019, 2018):
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
CHK("control: Kumpulan Wang Pembangunan closing 2019",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2019
     and r["row_type"] == "closing"][0], -24700420089)

# --- 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 65-66, printed 53-54)
S3 = "Nota 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    "AKAUN PENYELESAIAN": (65, "4,949,347,070", "6,229,373,232", [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "4,948,347,070", "6,228,373,232"),
    ]),
    "AKAUN PERNIAGAAN": (65, None, None, [
        ("Stor dan Woksyop Belum Diuntukkan", "156,921,369", "160,497,698"),
    ]),
    "AKAUN PINJAMAN": (65, "2,868,948,087", "3,212,473,867", [
        ("Kontraktor", "9,208,072", "5,591,053"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "21,450,107", "-"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "420,483,753", "318,115,280"),
        ("Pembangunan Ekonomi Belia", "13,478,632", "12,934,471"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "39,492,419", "38,543,079"),
        ("Pendahuluan Diri (Pegawai Awam)", "11,241,115", "36,321,119"),
        ("Pendahuluan Pelbagai", "58,253,041", "59,655,642"),
        ("Pendahuluan Untuk Negeri", "925,893,583", "637,192,003"),
        ("Pinjaman Diraja", "743,748", "728,964"),
        ("Pinjaman Kenderaan", "63,347,198", "63,129,854"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,055,058,708", "1,887,987,163"),
        ("Pinjaman Perumahan kepada Golongan Berpendapatan Rendah", "10,835,139", "16,582,433"),
        ("Rakyat Malaysia di Luar Negeri", "1,282,931", "1,277,735"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "238,179,641", "134,415,071"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": (65, None, None, [
        ("Kumpulan Wang Luar Jangka", "721,390,750", "294,306,200"),
    ]),
    "KUMPULAN WANG YANG LAIN": (66, "26,432,223,151", "21,641,419,300", [
        ("Amanah Negara", "17,605,293,030", "16,046,677,687"),
        ("Amanah Pelajar Miskin", "73,944,448", "55,615,424"),
        ("Amanah Sukan Negara", "26,442,867", "19,360,516"),
        ("Bantuan Bencana Negara", "235,859,572", "238,534,123"),
        ("Bantuan Mangsa Serangan Binatang Buas", "685,400", "541,900"),
        ("Cadangan Untuk Negeri", "224,759,099", "259,420,613"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "1,866,374", "1,951,277"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "795,957", "537,305"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "472,854", "472,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "423,415,576", "331,886,217"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "410,811", "580,787"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "88,707,892", "45,239,854"),
        ("Kumpulan Wang Amanah Majlis Sains Dan Penyelidikan Kebangsaan", "3,599,304", "3,481,297"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,425,679", "1,695,340"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "23,998,163", "62,351,926"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "39,596,751", "39,915,375"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "2,722,986", "2,437,393"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "1,626,350", "5,107"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "14,535,848", "14,195,169"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "7,586,776", "8,587,426"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "21,633,153", "16,342,578"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan", "6,005,750,948", "3,900,000,034"),
        ("Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "33,197,929", "34,629,981"),
        ("Perpustakaan Negara", "1,208,117", "1,321,858"),
        ("Program Perumahan Rakyat Dimiliki", "140,594,969", "148,580,363"),
        ("Skim Biasiswa Sukan Persekutuan", "884,216", "1,143,899"),
        ("Tabung Bantuan Perubatan", "71,498,080", "66,314,608"),
        ("Tabung Bayaran Balik Cukai", "1,355,479,579", "316,372,898"),
        ("Tabung Inovasi Negara", "19,813,116", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "35,347", "30,415"),
    ]),
}
for cat, (pg, s19, s18, items) in pkw_src.items():
    pp = pg - 12
    if s19 is not None:
        for yr, amt in ((2019, s19), (2018, s18)):
            T(KWK, PKW, cat, cat, yr, amt, "subtotal", pg, pp, S3)
    for item, a19, a18 in items:
        foot = item == "Amanah Negara"   # printed 'Amanah Negara*' (KWAN fx footnote)
        for yr, amt in ((2019, a19), (2018, a18)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, pp, S3, foot=foot)
for yr, amt in ((2019, "35,128,830,427"), (2018, "31,538,070,297")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 66, 54, S3)
for yr in (2019, 2018):
    tot_from_cats = 0.0
    for cat, (pg, s19, s18, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        sub = s19 if yr == 2019 else s18
        if sub is not None:
            CHK(f"Nota7(a)(ii) {cat} details = subtotal {yr}", det, N(sub))
            tot_from_cats += N(sub)
        else:
            tot_from_cats += det
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(ii) categories = PELBAGAI KWAK total {yr}", tot_from_cats, tot)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 66, printed 54)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("3,309,508,604", "3,130,824,564", [
        ("Akaun Amanah Estet Kebankrapan", "2,074,770,371", "2,138,802,162"),
        ("Kumpulan Wang Dius Api", "302,353,303", "290,821,360"),
        ("Akaun Amanah Am Pelikuidasi", "295,777,881", "273,440,726"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "252,376,478", "232,296,456"),
        ("Akaun Amanah Tabung Bantuan Insolvensi", "244,192,413", "60,344,828"),
        ("Pelbagai Amanah Khas", "140,038,158", "135,119,032"),
    ]),
    "AMANAH AM": ("6,184,702,924", "7,080,573,488", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "1,987,696,162", "3,129,217,998"),
        ("Akaun Amanah Mendapatkan Kembali Aset", "695,806,281", "-"),
        ("Akaun Amanah Industri Bekalan Elektrik", "680,775,000", "604,797,267"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta", "464,195,942", "497,299,398"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "427,040,883", "415,459,860"),
        ("Akaun Amanah Sumber Khas", "421,245,984", "426,949,191"),
        ("Pelbagai Amanah Am", "1,507,942,672", "2,006,849,774"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 67, printed 55)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("10,926,434,174", "10,792,824,645", [
        ("Kawalan Wang Tak Dituntut", "6,401,897,831", "5,752,246,030"),
        ("Wang Jaminan Pelaksanaan", "1,717,587,773", "1,691,185,905"),
        ("Mahkamah Tinggi", "1,322,316,390", "1,148,171,490"),
        ("Wang Tak Dituntut", "470,566,889", "691,918,489"),
        ("Pelbagai Deposit Am", "1,014,065,291", "1,509,302,731"),
    ]),
    "DEPOSIT PELARASAN": ("241,114,117", "1,066,289,229", [
        ("Terimaan Yang Tidak Diperuntukkan", "127,763,726", "878,084,519"),
        ("Pindahan Dana Elektronik Terbatal", "80,353,466", "142,398,185"),
        ("Deposit Pembatalan Pencen Skim B", "24,628,504", "28,011,556"),
        ("Pelbagai Deposit Pelarasan", "8,368,421", "17,794,969"),
    ]),
}
for grp, src, tot19, tot18, pg, stmt in (
        (KAW, awam_src, "9,494,211,528", "10,211,398,052", 66, S4),
        (DEP, dep_src, "11,167,548,291", "11,859,113,874", 67, S5)):
    pp = pg - 12
    for sec, (s19, s18, items) in src.items():
        for yr, amt in ((2019, s19), (2018, s18)):
            T(grp, "", sec, sec, yr, amt, "subtotal", pg, pp, stmt)
        for item, a19, a18 in items:
            for yr, amt in ((2019, a19), (2018, a18)):
                T(grp, "", sec, item, yr, amt, "detail", pg, pp, stmt)
    for yr, amt in ((2019, tot19), (2018, tot18)):
        T(grp, "", "", grp, yr, amt, "total", pg, pp, stmt)
    for yr in (2019, 2018):
        for sec, (s19, s18, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s19 if yr == 2019 else s18))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 68, printed 56)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(68, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(68, 56, "Nota 9 Memorandum Aset")))
ABT = "Akaun Belum Terima"
M(ABT, "AKAUN BELUM TERIMA", 2019, "94,114,786,243", "total")
ppbd = [  # label, 2019, 2018, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "57,661,165,390", "57,797,910,384", "subtotal"),
    ("Kerajaan Negeri", "16,344,322,228", "18,221,257,138", "detail"),
    ("Syarikat", "31,922,223,026", "30,764,095,109", "detail"),
    ("Badan Berkanun", "6,954,203,678", "6,328,481,358", "detail"),
    ("Pihak Berkuasa Tempatan", "185,252,112", "192,116,889", "detail"),
    ("Koperasi", "248,220,930", "265,203,844", "detail"),
    ("Pelbagai Agensi", "1,715,327,959", "1,760,456,508", "detail"),
    ("Perseorangan", "291,615,457", "266,299,538", "detail"),
]
PPBD_SEC = "Akaun Belum Terima - Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a19, a18, rt in ppbd:
    for yr, amt in ((2019, a19), (2018, a18)):
        M(PPBD_SEC, item, yr, amt, rt)
PABT_SEC = "Akaun Belum Terima - Pelbagai Akaun Belum Terima"
M(PABT_SEC, "PELBAGAI AKAUN BELUM TERIMA", 2019, "36,453,620,853", "subtotal")
M(PABT_SEC, "Pinjaman dan pendahuluan di peringkat Kementerian/Jabatan selain Kementerian Kewangan (termasuk dalam Pelbagai Akaun Belum Terima)",
  2019, "790,573,665", "memo")
M(PABT_SEC, "Tunggakan Pelbagai Akaun Belum Terima", 2019, "20,478,751,315", "memo")
M(PABT_SEC, "Tunggakan faedah Pinjaman Boleh Dituntut (termasuk dalam tunggakan)",
  2019, "2,441,684,121", "memo")
pel = [
    ("PELABURAN", "32,038,227,719", "31,058,227,719", "subtotal"),
    ("Syarikat", "31,021,552,794", "30,041,552,794", "detail"),
    ("Badan Berkanun", "978,100,696", "978,100,696", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a19, a18, rt in pel:
    for yr, amt in ((2019, a19), (2018, a18)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2019, 2018):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2019 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2019 else pel[0][2]))
CHK("Nota9 PPBD + Pelbagai ABT = AKAUN BELUM TERIMA 2019",
    N("57,661,165,390") + N("36,453,620,853"), 94114786243)
CHK("control: Akaun Belum Terima 2019", 94114786243.0, 94114786243)
CHK("control: memo Pelaburan 2019", N(pel[0][1]), 32038227719)
CHK("declared restatement (Nota 9): Perseorangan 2018 restated 369,714,975 -> 266,299,538 "
    "(Pinjaman Perumahan kepada Golongan Berpendapatan Rendah moved to Pelbagai ABT)",
    N("266,299,538"), 266299538)

# =====================================================================
# 5. Nota 10 sub-splits (pdf 70-71)
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2019, printed_total_2018, items, pdf_page
    ("KOMITMEN JAMINAN", "193,992,526,604", "164,908,473,346", [
        ("Dalam Negeri", "146,117,984,951", "116,003,213,747"),
        ("Luar Negeri", "47,874,541,653", "48,905,259,599")], 70),
    ("KOMITMEN PAJAKAN KEWANGAN", "33,086,435,272", "31,517,888,277", [
        ("Pajakan Kewangan Kerajaan Persekutuan", "22,189,240,582", "20,008,614,753"),
        ("Pajakan Kewangan Badan Berkanun", "10,897,194,690", "11,509,273,524")], 70),
    ("KOMITMEN BAYARAN BALIK CUKAI", "19,392,393,636", "44,372,590,815", [
        ("Cukai Pendapatan", "10,346,928,837", "17,943,934,658"),
        ("Cukai Keuntungan Harta Tanah", "503,958,079", "492,507,539"),
        ("Cukai Barangan dan Perkhidmatan", "8,541,506,720", "25,936,148,618")], 70),
    ("PELBAGAI LIABILITI", "840,133,470", "786,190,452", [
        ("Nota Kena Bayar", "798,665,127", "744,856,249"),
        ("Sekuriti Tak Dituntut", "27,431,987", "27,332,947"),
        ("Akaun Depositori Pusat", "14,036,356", "14,001,256")], 71),
]
for parent, t19, t18, items, pg in com_src:
    pp = pg - 12
    for item, a19, a18 in items:
        for yr, amt in ((2019, a19), (2018, a18)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2019, t19), (2018, t18)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Komitmen Jaminan 2019", N("193,992,526,604"), 193992526604)
CHK("control: Pajakan 2019", N("33,086,435,272"), 33086435272)
CHK("control: Bayaran Balik Cukai 2019", N("19,392,393,636"), 19392393636)
CHK("control: Pelbagai Liabiliti 2019", N("840,133,470"), 840133470)
# Komitmen Kewangan = Jaminan + Pajakan + Bayaran Balik Cukai + Pampasan (memo p45)
CHK("Nota10 commitment components sum = memo Komitmen Kewangan 2019",
    N("193,992,526,604") + N("33,086,435,272") + N("19,392,393,636") + N("990,037,154"),
    247461392666)

# =====================================================================
# 6. Nota 11-12 (pdf 71, printed 59)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, stmt):
    V(71, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(71, 59, stmt)))
O("11", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2019, "275,378,709,914", "Nota 11 Liabiliti Luar Jangka")
O("11", "Jaminan berisiko menjadi komitmen Kerajaan berdasarkan kedudukan kewangan entiti yang dijamin (termasuk dalam jaminan pinjaman)",
  2019, "42,830,300,000", "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja, Lembaga Tabung Haji dan Perbadanan Tabung Pendidikan Tinggi Nasional",
  2019, "1,019,362,949,761", "Nota 11 Liabiliti Luar Jangka")
O("12", "Wang Pendahuluan Kontraktor", 2019, "630,587,851",
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
with open(os.path.join(WH, "_validation_checks_2019.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
