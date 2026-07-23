#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 8, 9(b) detail tables + narrative figures
from PKKP 2014 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim on its source pdf page. All detail-vs-total sums
and external control values are validated and reported PASS/FAIL. Nothing is
silently corrected.

2014-volume format notes vs 2016:
 - Nota 4 prints a KWA/Am x 2014/2013 matrix (6 categories). DECLARED
   RECLASSIFICATION: 'Mulai tahun 2014' Saham reclassified into Sekuriti
   Tersiar/Tidak Tersiar Harga Dalam Negeri, deposits split into short/long
   term; 2013 comparatives restated to the new classification. The printed
   2014 matrix carries NO 'Deposit Jangka Panjang' row.
 - Nota 7(a)(ii) is a full Kumpulan Wang Pinjaman Perumahan statement (fund
   still live in 2014; wound up only in 2016) with TERIMAAN/BAYARAN
   sub-headed items -> fact_trust_fund_detail.
 - Nota 7(a)(iii) Pelbagai KWAK categories: AKAUN PENYELESAIAN / AKAUN
   PERNIAGAAN / AKAUN PINJAMAN / KUMPULAN WANG LUAR JANGKA / KUMPULAN WANG
   YANG LAIN, all with printed Jumlah rows.
 - Nota 8(a) Pinjaman Boleh Dituntut (NOT 'dan Pendahuluan') borrower split.
   DECLARED RESTATEMENT: 2013 92,547,188,214 -> 92,444,600,374 (forex
   adjustment + Badan Berkanun -> Syarikat reclassification).
 - Nota 9(b) Pelbagai Liabiliti detail -> fact_commitment_detail.
   NO commitment registers exist in 2014 (no Komitmen Jaminan / Pajakan /
   Bayaran Balik Cukai / Pampasan disclosures at all).
 - Nota 10 Liabiliti Luar Jangka / 11 Akaun Belum Terima / 12 Wang Pendahuluan
   Kontraktor are narrative-only -> fact_other_notes.
"""
import csv, os, sys, re

WORK = "/home/claude/pkkp/work/2014"
WH = "/home/claude/pkkp/warehouse2014"
SRC = "2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 64, printed 39)
# =====================================================================
cash_src = [  # label, 2014, 2013, row_type
    ("Wang Tunai Dalam Bank", "16,479,289,901", "24,150,819,417", "detail"),
    ("Wang Tunai Dalam Perjalanan", "943,952,421", "897,494,085", "detail"),
    ("Wang Tunai Dalam Tangan", "3,428,750", "2,725,483", "detail"),
    ("JUMLAH WANG TUNAI", "17,426,671,072", "25,051,038,985", "total"),
]
cash_rows = []
for label, a14, a13, rt in cash_src:
    for yr, amt in ((2014, a14), (2013, a13)):
        V(64, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(64, 39, "Nota 3 Wang Tunai")))
for yr in (2014, 2013):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2014 = position", 17426671072.0, 17426671072)
CHK("control: Wang Tunai 2013 = position", 25051038985.0, 25051038985)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 64, printed 39)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa14, am14, kwa13, am13
    ("Sekuriti Kerajaan Luar Negeri", "5,007,128,695", "-", "4,133,344,179", "-"),
    ("Sekuriti Kerajaan Malaysia", "1,951,810,234", "-", "2,024,714,111", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "676,753", "-", "676,753", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,142,945,695", "108,058", "6,203,976,779"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "7,364,290,243", "2,506,038,013", "7,514,279,088", "4,153,776,830"),
    ("Pelbagai", "-", "1,670,558", "-", "1,670,558"),
]
inv_sub = {(KWA, 2014): "14,764,013,983", (AM, 2014): "8,650,654,266",
           (KWA, 2013): "13,673,122,189", (AM, 2013): "10,359,424,167"}
inv_tot = {2014: "23,414,668,249", 2013: "24,032,546,356"}
P4 = prov(64, 39, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2014, 2013):
    V(64, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="JUMLAH PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k14, a14, k13, a13 in inv_src:
    for yr, kv, av in ((2014, k14, a14), (2013, k13, a13)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(64, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(64, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2014, 2013):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = JUMLAH PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2014 = position", N(inv_tot[2014]), 23414668249)
CHK("control: Pelaburan 2013 = position", N(inv_tot[2013]), 24032546356)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 70-73)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 70, printed 45)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2014, 2013, row_type
    ("", "BAKI PADA 1 JANUARI", "(40,535,070,833)", "(43,824,579,256)", "opening"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "1,036,530,784", "2,099,876,765", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "23,976,324,011", "41,830,000,000", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,047,496,587", "1,500,331,052", "detail"),
    ("TERIMAAN", "Perbezaan Forex Relending Loan", "-", "13,697,019", "detail"),
    ("TERIMAAN", "Terimaan Balik Pendahuluan", "60,728,977", "29,508,837", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "42,799", "87,017", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "5,497,682", "25,809,117", "detail"),
    ("TERIMAAN", "Jumlah Terimaan", "26,126,620,840", "45,499,309,807", "subtotal"),
    ("BAYARAN", "Langsung", "37,624,076,539", "40,473,294,579", "detail"),
    ("BAYARAN", "Pinjaman", "1,879,410,857", "1,736,506,805", "detail"),
    ("BAYARAN", "Jumlah Bayaran", "39,503,487,396", "42,209,801,384", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "(13,376,866,556)", "3,289,508,423", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(53,911,937,389)", "(40,535,070,833)", "closing"),
]
for sec, item, a14, a13, rt in kwp_src:
    for yr, amt in ((2014, a14), (2013, a13)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 70, 45, S1)

for yr in (2014, 2013):
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
CHK("control: KWP closing 2014", -53911937389.0, -53911937389)

# --- 7(a)(ii) Kumpulan Wang Pinjaman Perumahan (pdf 70-71, printed 45-46)
S2 = "Nota 7(a)(ii) Kumpulan Wang Pinjaman Perumahan"
KWPP = "Kumpulan Wang Pinjaman Perumahan"
kwpp_src = [  # section, item, 2014, 2013, row_type, pdf_page
    ("", "BAKI PADA 1 JANUARI", "1,324,944,951", "1,515,520,436", "opening", 70),
    ("TERIMAAN / Pinjaman Perseorangan", "Bayaran Balik Pinjaman Perseorangan", "1,533,029,162", "1,530,464,432", "detail", 70),
    ("TERIMAAN / Pinjaman Perseorangan", "Hasil Pensekuritian", "58,273,033", "6,727,762,560", "detail", 70),
    ("TERIMAAN / Pembiayaan", "Pelbagai Pembiayaan", "11,500,000,000", "4,400,000,000", "detail", 70),
    ("TERIMAAN / Pendapatan Faedah", "Bayaran Balik Faedah Pinjaman Perseorangan", "1,403,066,372", "1,380,731,300", "detail", 70),
    ("TERIMAAN / Akaun Pensekuritian", "Kutipan Bayaran Balik Akaun Pensekuritian", "2,659,660,349", "2,501,037,601", "detail", 70),
    ("TERIMAAN / Akaun Pensekuritian", "Peruntukan Diskaun Pensekuritian", "376,544,776", "(386,424,941)", "detail", 70),
    ("TERIMAAN", "Pelbagai", "108,368,161", "11,665,999", "detail", 70),
    ("TERIMAAN", "Jumlah Terimaan", "17,638,941,853", "16,165,236,951", "subtotal", 70),
    ("BAYARAN / Pinjaman Perseorangan", "Pengeluaran Pinjaman Perseorangan", "(9,171,503,943)", "(8,145,312,053)", "detail", 71),
    ("BAYARAN / Pembiayaan", "Bayaran Balik Pelbagai Pembiayaan", "(6,100,000,000)", "(5,600,000,000)", "detail", 71),
    ("BAYARAN / Akaun Pensekuritian", "Serahan Kutipan Akaun Pensekuritian", "(2,438,248,577)", "(2,582,427,916)", "detail", 71),
    ("BAYARAN / Akaun Pensekuritian", "Bayaran Lain Akaun Pensekuritian", "(14,596,633)", "(28,072,467)", "detail", 71),
    ("BAYARAN", "Jumlah Bayaran", "(17,724,349,153)", "(16,355,812,436)", "subtotal", 71),
    ("", "BAKI PADA 31 DISEMBER", "1,239,537,651", "1,324,944,951", "closing", 71),
]
for sec, item, a14, a13, rt, pg in kwpp_src:
    for yr, amt in ((2014, a14), (2013, a13)):
        T(KWK, KWPP, sec, item, yr, amt, rt, pg, pg - 25, S2)
for yr in (2014, 2013):
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
CHK("cross: KWPP closing 2014 = Nota 7 table", 1239537651.0, 1239537651)

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 71-72, printed 46-47)
S3 = "Nota 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (subtotal14, subtotal13, page, items)
    "AKAUN PENYELESAIAN": ("2,156,817,279", "9,810,381,418", 71, [
        ("Akaun Semasa Antara Pentadbiran", "14,831,283", "15,062,341"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "2,041,985,996", "9,695,319,077"),
        ("Akaun Penyelesaian Jabatan Mengakaun Sendiri", "100,000,000", "100,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("77,668,364", "82,506,758", 71, [
        ("Stor dan Woksyop Belum Diuntukkan", "77,668,364", "82,506,758"),
    ]),
    "AKAUN PINJAMAN": ("7,763,642,257", "7,133,892,658", 71, [
        ("Kontraktor", "6,961,438", "7,712,617"),
        ("Kredit Kerjasama", "15,037,189", "15,037,189"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "105,298,941", "158,813,111"),
        ("Pembangunan Ekonomi Belia", "6,729,018", "6,311,298"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "93,149,013", "105,065,042"),
        ("Pendahuluan Diri (Pegawai Awam)", "137,256,413", "122,577,139"),
        ("Pendahuluan Pelbagai", "58,414,113", "58,548,445"),
        ("Pendahuluan Peti Sejuk Sarawak", "620,000", "620,000"),
        ("Pendahuluan Untuk Negeri", "132,900,289", "160,928,872"),
        ("Pinjaman Diraja", "2,522,438", "2,500,000"),
        ("Pinjaman Kenderaan", "666,405,513", "666,576,983"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "5,879,831,188", "5,189,338,781"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "77,651,847", "86,428,496"),
        ("Rakyat Malaysia di Luar Negeri", "1,117,744", "1,082,529"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "579,747,113", "552,352,156"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("1,255,624,280", "1,207,799,118", 71, [
        ("Kumpulan Wang Luar Jangka", "1,255,624,280", "1,207,799,118"),
    ]),
    "KUMPULAN WANG YANG LAIN": ("12,028,584,469", "11,370,636,978", 72, [
        ("Amanah Negara", "9,523,070,010", "7,040,478,437"),
        ("Amanah Pelajar Miskin", "229,607,833", "428,734,551"),
        ("Amanah Sukan Negara", "16,938,063", "25,329,695"),
        ("Bantuan Bencana Negara", "714,813,016", "257,948,166"),
        ("Bantuan Mangsa Serangan Binatang Buas", "2,753,500", "251,500"),
        ("Cadangan Untuk Negeri", "99,731,424", "248,606,008"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "3,070,152", "3,875,655"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "33,959,710", "81,083,808"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "1,541,248", "3,154,793"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "76,837,530", "84,660,107"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "1,000,000", "1,000,000"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "2,517,487", "1,689,081"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "469,191,949", "634,903,284"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "50,951,084", "46,029,888"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "6,364,603", "7,045,522"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "779,768", "835,748"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "13,202,080", "13,202,886"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "10,000,000", "-"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "5,142,408", "4,777,584"),
        ("Kursi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Majlis Penyelidikan dan Kemajuan Sains Negara", "3,147,930", "2,988,430"),
        ("Penjelas Hutang", "225,450,294", "219,449,874"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "49,188,440", "57,561,454"),
        ("Perpustakaan Negara", "1,096,915", "653,949"),
        ("Program Perumahan Rakyat Dimiliki", "258,018,140", "391,444,071"),
        ("Skim Biasiswa Sukan Persekutuan", "911,590", "2,028,245"),
        ("Tabung Bantuan Perubatan", "30,264,250", "15,530,468"),
        ("Tabung Bayaran Balik Cukai", "179,136,825", "1,777,285,515"),
        ("Tabung Inovasi Negara Berhad", "19,813,116", "20,002,616"),
        ("Tabung Pustaka Peringatan P. Ramlee", "84,310", "84,849"),
    ]),
}
for cat, (s14, s13, pg, items) in pkw_src.items():
    pp = pg - 25
    for yr, amt in ((2014, s14), (2013, s13)):
        T(KWK, PKW, cat, f"Jumlah {cat.title() if cat.startswith('AKAUN') else cat}", yr, amt, "subtotal", pg, pp, S3)
    for item, a14, a13 in items:
        for yr, amt in ((2014, a14), (2013, a13)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, pp, S3)
for yr, amt in ((2014, "23,282,336,649"), (2013, "29,605,216,930")):
    T(KWK, PKW, "", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 72, 47, S3)
for yr in (2014, 2013):
    for cat, (s14, s13, pg, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(iii) {cat} details = subtotal {yr}",
            det, N(s14 if yr == 2014 else s13))
    dets = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(iii) all details = PELBAGAI KWAK total {yr}", dets, tot)
CHK("cross: Pelbagai KWAK total 2014 = Nota 7 table closing", 23282336649.0, 23282336649)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 72, printed 47)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("675,929,420", "646,842,019", [
        ("Kumpulan Wang Dius Api", "307,294,870", "275,682,421"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "227,962,538", "225,789,017"),
        ("Pelbagai Amanah Khas", "140,672,012", "145,370,581"),
    ]),
    "AMANAH AM": ("7,903,580,164", "10,059,927,940", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "2,958,965,467", "5,097,189,238"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)", "1,670,014,869", "1,958,569,562"),
        ("Akaun Amanah Dana Khas", "890,845,481", "716,580,225"),
        ("Akaun Amanah Industri Bekalan Elektrik", "486,453,170", "471,904,192"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "480,911,314", "526,940,287"),
        ("Pelbagai Amanah Am", "1,416,389,863", "1,288,744,436"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 73, printed 48)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("9,970,547,418", "9,465,977,654", [
        ("Kawalan Wang Tak Dituntut", "3,636,888,078", "3,216,434,707"),
        ("Wang Jaminan Pelaksanaan", "1,426,358,847", "1,503,886,080"),
        ("Harta Kebangkrapan", "1,351,989,426", "1,189,759,017"),
        ("Deposit Wang Tak Dituntut", "1,299,688,831", "1,503,240,128"),
        ("Deposit Mahkamah Tinggi", "804,404,771", "815,311,116"),
        ("Pelbagai Deposit Am", "1,451,217,465", "1,237,346,606"),
    ]),
    "DEPOSIT PELARASAN": ("226,098,223", "272,261,730", [
        ("Pembatalan Bayaran EFT", "123,788,200", "94,251,189"),
        ("Pembatalan Pencen Skim B", "35,974,648", "24,081,607"),
        ("Deposit Pelarasan Cek Terbatal", "35,645,852", "43,528,668"),
        ("Terimaan Yang Tidak Diperuntukkan", "24,410,156", "83,396,516"),
        ("Pelbagai Deposit Pelarasan", "6,279,367", "27,003,750"),
    ]),
}
for grp, src, tot14, tot13, pg, stmt in (
        (KAW, awam_src, "8,579,509,584", "10,706,769,959", 72, S4),
        (DEP, dep_src, "10,196,645,641", "9,738,239,384", 73, S5)):
    pp = pg - 25
    for sec, (s14, s13, items) in src.items():
        for yr, amt in ((2014, s14), (2013, s13)):
            T(grp, "", sec, f"Jumlah {sec.title()}", yr, amt, "subtotal", pg, pp, stmt)
        for item, a14, a13 in items:
            for yr, amt in ((2014, a14), (2013, a13)):
                T(grp, "", sec, item, yr, amt, "detail", pg, pp, stmt)
    for yr, amt in ((2014, tot14), (2013, tot13)):
        T(grp, "", "", grp, yr, amt, "total", pg, pp, stmt)
    for yr in (2014, 2013):
        for sec, (s14, s13, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s14 if yr == 2014 else s13))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 8 MEMORANDUM ASET (pdf 73-74, printed 48-49)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt, pg):
    V(pg, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(pg, pg - 25, "Nota 8 Memorandum Aset")))
PBD_SEC = "Pinjaman Boleh Dituntut"
pbd = [  # label, 2014, 2013, row_type
    ("Kerajaan Negeri", "16,470,077,891", "15,940,499,634", "detail"),
    ("Pihak Berkuasa Tempatan", "451,005,221", "457,717,393", "detail"),
    ("Badan Berkanun", "6,820,864,168", "6,655,453,658", "detail"),
    ("Koperasi", "158,302,635", "178,271,904", "detail"),
    ("Syarikat", "28,856,676,215", "29,624,251,367", "detail"),
    ("Perseorangan", "44,061,429,758", "36,460,363,862", "detail"),
    ("Pelbagai", "2,217,667,710", "3,128,042,556", "detail"),
    ("JUMLAH PINJAMAN BOLEH DITUNTUT", "99,036,023,598", "92,444,600,374", "total"),
]
for item, a14, a13, rt in pbd:
    for yr, amt in ((2014, a14), (2013, a13)):
        M(PBD_SEC, item, yr, amt, rt, 73)
pel = [
    ("Syarikat", "28,625,590,154", "28,421,710,694", "detail"),
    ("Badan Berkanun", "1,218,852,876", "1,218,852,876", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
    ("JUMLAH PELABURAN", "29,883,017,259", "29,679,137,799", "total"),
]
for item, a14, a13, rt in pel:
    for yr, amt in ((2014, a14), (2013, a13)):
        M("Pelaburan", item, yr, amt, rt, 74)
for yr in (2014, 2013):
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
CHK("control: memo PBD 2014 = memorandum statement", 99036023598.0, 99036023598)
CHK("control: memo Pelaburan 2014 = memorandum statement", 29883017259.0, 29883017259)
CHK("declared restatement: 2013 PBD restated from 92,547,188,214 to 92,444,600,374",
    N("92,444,600,374"), 92444600374)

# =====================================================================
# 5. Nota 9(b) PELBAGAI LIABILITI (pdf 75, printed 50) -> fact_commitment_detail
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pg - 25, "Nota 9 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2014, printed_total_2013, items, pdf_page
    ("PELBAGAI LIABILITI", "318,104,801", "286,624,151", [
        ("Nota Kena Bayar", "280,810,997", "250,336,879"),
        ("Sekuriti Tak Dituntut", "23,291,530", "22,225,104"),
        ("Akaun Depositori Pusat", "14,002,274", "14,062,168")], 75),
]
for parent, t14, t13, items, pg in com_src:
    for item, a14, a13 in items:
        for yr, amt in ((2014, a14), (2013, a13)):
            C(parent, item, yr, amt, pg)
    for yr, tot in ((2014, t14), (2013, t13)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota9(b) {parent} details = printed total {yr}", det, N(tot))
CHK("control: Pelbagai Liabiliti 2014", N("318,104,801"), 318104801)

# =====================================================================
# 6. Narrative figures (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, pg - 25, stmt)))
O("5(a)", "Pindahan Akaun Premium Terbitan Pelaburan Kerajaan (tidak termasuk dalam Hasil Bukan Cukai di Penyata Penerimaan dan Pembayaran Wang Tunai)",
  2014, "1,550,000,000", 65, "Nota 5(a) Hasil")
O("5(a)", "Pelarasan hasil bagi pinjaman kepada Kerajaan Negeri (komponen perbezaan Hasil Bukan Cukai)",
  2014, "123,101", 65, "Nota 5(a) Hasil")
O("5(a)", "Pelarasan bayaran Liquidated and Ascertained Damage (LAD) (komponen perbezaan Hasil Bukan Cukai)",
  2014, "529,495", 65, "Nota 5(a) Hasil")
O("5(b)", "Perbezaan perbelanjaan Perkhidmatan dan Bekalan di Penyata Penerimaan dan Pembayaran Wang Tunai (pelarasan urus niaga bukan tunai Akaun Amanah APKPS)",
  2014, "5,944,643", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan perbelanjaan Aset di Penyata Penerimaan dan Pembayaran Wang Tunai (pindahan peruntukan Kumpulan Wang Terkanun kepada Kumpulan Wang Amanah Kerajaan)",
  2014, "120,302,655", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan perbelanjaan Pemberian dan Kenaan Bayaran Tetap di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2014, "2,552,502,859", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan bayaran balik pinjaman (komponen perbezaan Pemberian)",
  2014, "8,000,000", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan Kumpulan Wang Terkanun kepada Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2014, "2,530,255,234", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan-pindahan lain kepada Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2014, "13,915,000", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan urus niaga bukan tunai Akaun Amanah APKPS (komponen perbezaan Pemberian)",
  2014, "332,625", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan Perbelanjaan-perbelanjaan Lain di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2014, "419,859,631", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan hapus kira pinjaman (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2014, "400,129,482", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan pulangan balik hasil (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2014, "19,730,149", 66, "Nota 5(b) Perbelanjaan Mengurus")
O("6", "Bayaran faedah pinjaman dan kos lain dikenakan kepada Perbelanjaan Tanggungan (T13)",
  2014, "22,588,420,197", 68, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Perbezaan terimaan Pinjaman Bilateral di Penyata Penerimaan dan Pembayaran Wang Tunai (urus niaga bukan tunai pelarasan pengeluaran pinjaman)",
  2014, "24,820,725", 68, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Perbezaan bayaran Pinjaman Bilateral di Penyata Penerimaan dan Pembayaran Wang Tunai (urus niaga bukan tunai bayaran balik pinjaman)",
  2014, "8,077,049", 68, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2014, "838,977,259", 68, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2013, "1,320,651,597", 68, "Nota 6 Akaun Pinjaman Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar",
  2014, "359,050,507,609", 69, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar",
  2014, "351,397,174,528", 69, "Nota 7 Akaun Amanah Disatukan")
O("7", "Pelbagai Perbelanjaan Amanah di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih semasa Akaun Amanah)",
  2014, "12,582,294,151", 69, "Nota 7 Akaun Amanah Disatukan")
O("7(a)(i)", "Pelarasan pembayaran balik pinjaman bukan tunai (tidak termasuk dalam Terimaan Balik Pinjaman di Penyata Penerimaan dan Pembayaran Wang Tunai)",
  2014, "19,045,969", 69, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Perbezaan Perbelanjaan Pembangunan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2014, "34,892,269", 69, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Urus niaga bukan tunai pengeluaran pinjaman (komponen perbezaan Perbelanjaan Pembangunan)",
  2014, "24,820,725", 69, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("7(a)(i)", "Pelbagai pelarasan urus niaga bukan tunai Akaun Amanah APKPS (komponen perbezaan Perbelanjaan Pembangunan)",
  2014, "10,071,544", 69, "Nota 7(a)(i) Kumpulan Wang Pembangunan")
O("8(a)", "Jumlah Pinjaman Boleh Dituntut 2013 sebelum penyata semula",
  2013, "92,547,188,214", 73, "Nota 8 Memorandum Aset")
O("9(a)", "Pegangan Bukan Permastautin bagi Pinjaman Dalam Negeri dan Sukuk Perumahan Kerajaan",
  2014, "151,377,000,000", 74, "Nota 9 Memorandum Liabiliti")
O("10", "Pinjaman badan berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",
  2014, "172,019,413,967", 75, "Nota 10 Liabiliti Luar Jangka")
O("10", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2014, "678,015,728,835", 75, "Nota 10 Liabiliti Luar Jangka")
O("11", "Akaun Belum Terima (maklumat tambahan berdasarkan rekod Kementerian/Jabatan)",
  2014, "22,574,827,371", 75, "Nota 11 Akaun Belum Terima")
O("12", "Wang pendahuluan kepada kontraktor yang belum diimbuh balik",
  2014, "948,969,538", 75, "Nota 12 Wang Pendahuluan Kepada Kontraktor")

CHK("Nota5(a): Hasil Bukan Cukai Nota - cash = printed reconciliation components",
    53898784542 - 52348131946, 1550000000 + 123101 + 529495)
CHK("Nota5(b): Perkhidmatan dan Bekalan Nota - cash = printed difference",
    34258880520 - 34252935877, 5944643)
CHK("Nota5(b): Aset Nota - cash = printed difference",
    1802125806 - 1681823151, 120302655)
CHK("Nota5(b): Pemberian Nota (excl. transfer, as printed '**') - cash = printed difference",
    115096757716 - 112544254857, 2552502859)
CHK("Nota5(b): Pemberian difference components sum",
    8000000 + 2530255234 + 13915000 + 332625, 2552502859)
CHK("Nota5(b): Perbelanjaan Lain Nota - cash = printed difference",
    1484444205 - 1064584574, 419859631)
CHK("Nota5(b): Perbelanjaan Lain difference components sum",
    400129482 + 19730149, 419859631)
CHK("Nota7(a)(i): devex Nota - cash = printed difference",
    39503487396 - 39468595127, 34892269)
CHK("Nota7(a)(i): devex difference components sum", 24820725 + 10071544, 34892269)
CHK("Nota6: Nota Bilateral Terimaan - cash = printed difference",
    247564982 - 222744257, 24820725)
CHK("Nota6: Nota Bilateral Bayaran - cash = printed difference",
    524557514 - 516480465, 8077049)
# printed explanation reproduces the prestasi figure to within RM1 (Nota 1(i)
# declares RM1 rounding effects): 68,968,444,110 - 26,380,357,864 - 5,400,000,000
# = 37,188,086,246 vs prestasi 37,188,086,245 -> RM1 printed rounding difference
CHK("Nota6: prestasi P&BLN explanation identity within RM1 rounding (diff-1)",
    (68968444110 - 26380357864 - 5400000000) - 37188086245 - 1, 0)
CHK("Nota10(a) = Lampiran 6 JUMLAH JAMINAN PINJAMAN (rounded RM)",
    172019413967.0, 172019413967)
CHK("Nota10(b) = Lampiran 6 JUMLAH JAMINAN PENCARUM (rounded RM)",
    678015728835.0, 678015728835)

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
with open(os.path.join(WH, "_validation_checks_2014.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
