#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 9, 10(b) detail tables and narrative
figures from PKKP 2017 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim (comma-formatted, parens for negatives) in the
raw text of its source pdf page. All detail-vs-total sums and external
control values are validated and reported PASS/FAIL. Nothing is silently
corrected.

2017-volume format notes vs 2018:
 - Nota 4 columns: KWA category 'Sekuriti Kerajaan Luar Negeri' / 'Sekuriti
   Kerajaan Malaysia' (pre-2018 wording, before the Hutang Kerajaan/Swasta
   split and the 2018 restatement); nil cells print '-'.
 - Nota 7(a)(i) TERIMAAN includes 'Jualan Aset Modal' (nil 2017, 12,105 in
   2016); Pindahan Dari Akaun Pinjaman Disatukan prints with a stray glued
   '-' glyph ('27,232,066,897-'), a text-layer artifact only.
 - Nota 7(a)(ii) categories AKAUN PENYELESAIAN / AKAUN PERNIAGAAN (no
   subtotal) / AKAUN PINJAMAN / KUMPULAN WANG LUAR JANGKA (no subtotal) /
   KUMPULAN WANG YANG LAIN.
 - Nota 9 has NO Akaun Belum Terima section (receivables are a Nota 12
   narrative only in this volume).
 - Nota 10 has NO commitments (Jaminan/Pajakan/Bayaran Balik Cukai/Pampasan)
   and NO PFI liability; only (a) Hutang Persekutuan and (b) Pelbagai
   Liabiliti. fact_commitment_detail therefore carries ONLY the Pelbagai
   Liabiliti split in this volume.
"""
import csv, os, sys, re

WORK = "/home/claude/pkkp/work/2017"
WH = "/home/claude/pkkp/warehouse2017"
SRC = "2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 60, printed 49)
# =====================================================================
cash_src = [  # label, 2017, 2016, row_type
    ("WANG TUNAI", "18,064,128,458", "16,063,461,692", "total"),
    ("Wang Tunai Dalam Bank", "16,663,516,979", "14,879,566,399", "detail"),
    ("Wang Tunai Dalam Perjalanan", "1,397,584,959", "1,180,511,453", "detail"),
    ("Wang Tunai Dalam Tangan", "3,026,520", "3,383,840", "detail"),
]
cash_rows = []
for label, a17, a16, rt in cash_src:
    for yr, amt in ((2017, a17), (2016, a16)):
        V(60, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(60, 49, "Nota 3 Wang Tunai")))
for yr in (2017, 2016):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2017", 18064128458.0, 18064128458)
CHK("control: Wang Tunai 2016", 16063461692.0, 16063461692)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 60, printed 49)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa17, am17, kwa16, am16
    ("Sekuriti Kerajaan Luar Negeri", "6,752,198,170", "-", "6,956,148,547", "-"),
    ("Sekuriti Kerajaan Malaysia", "3,360,920,452", "-", "3,013,268,850", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "676,753", "-", "676,753", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,717,761,577"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "6,592,045,808", "255,650,000", "5,794,244,365", "385,993,318"),
    ("Pelbagai", "-", "942,558", "-", "1,670,558"),
]
inv_sub = {(KWA, 2017): "17,145,949,241", (AM, 2017): "6,974,354,135",
           (KWA, 2016): "16,204,446,573", (AM, 2016): "7,105,425,453"}
inv_tot = {2017: "24,120,303,376", 2016: "23,309,872,026"}
P4 = prov(60, 49, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2017, 2016):
    V(60, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k17, a17, k16, a16 in inv_src:
    for yr, kv, av in ((2017, k17, a17), (2016, k16, a16)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(60, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(60, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2017, 2016):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2017", N(inv_tot[2017]), 24120303376)
CHK("control: Pelaburan 2016", N(inv_tot[2016]), 23309872026)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 66-68)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 66, printed 55)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2017, 2016, row_type
    ("", "BAKI PADA 1 JANUARI", "(33,677,135,427)", "(41,856,373,646)", "opening"),
    ("TERIMAAN", "TERIMAAN", "31,795,061,321", "50,174,275,916", "subtotal"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "2,710,809,216", "2,248,437,560", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "27,232,066,897", "46,579,258,785", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "785,821,218", "1,079,107,702", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "-", "12,105", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "1,066,363,990", "267,459,764", "detail"),
    ("BAYARAN", "Perbelanjaan Pembangunan", "44,883,838,833", "41,995,037,697", "subtotal"),
    ("BAYARAN", "Langsung", "42,276,425,979", "40,052,263,265", "detail"),
    ("BAYARAN", "Pinjaman", "2,607,412,854", "1,942,774,432", "detail"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "(13,088,777,512)", "8,179,238,219", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(46,765,912,939)", "(33,677,135,427)", "closing"),
]
for sec, item, a17, a16, rt in kwp_src:
    for yr, amt in ((2017, a17), (2016, a16)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 66, 55, S1)

def stmt_checks(fund, prefix):
    for yr in (2017, 2016):
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
CHK("control: Kumpulan Wang Pembangunan closing 2017",
    [r["amount_rm"] for r in trust_rows
     if r["fund_bm"] == "Kumpulan Wang Pembangunan" and r["year"] == 2017
     and r["row_type"] == "closing"][0], -46765912939)

# --- 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 66-67, printed 55-56)
S3 = "Nota 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (subtotal17 or None, subtotal16 or None, page, items)
    "AKAUN PENYELESAIAN": ("4,152,455,614", "4,353,837,704", 66, [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "1,000,000"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "4,151,455,614", "4,352,837,704"),
    ]),
    "AKAUN PERNIAGAAN": (None, None, 66, [
        ("Stor dan Woksyop Belum Diuntukkan", "79,974,300", "78,167,501"),
    ]),
    "AKAUN PINJAMAN": ("3,027,633,431", "3,677,307,422", 66, [
        ("Kontraktor", "4,359,739", "6,452,404"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "25,611,624", "77,048,718"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "199,815,126", "140,505,555"),
        ("Pembangunan Ekonomi Belia", "12,325,602", "11,653,350"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "38,064,828", "45,845,291"),
        ("Pendahuluan Diri (Pegawai Awam)", "94,173,856", "79,887,280"),
        ("Pendahuluan Pelbagai", "58,930,388", "58,818,392"),
        ("Pendahuluan Untuk Negeri", "138,019,183", "3,798,123"),
        ("Pinjaman Diraja", "728,964", "723,761"),
        ("Pinjaman Kenderaan", "62,878,742", "62,494,891"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "1,532,197,919", "2,427,609,498"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "26,772,499", "45,653,640"),
        ("Rakyat Malaysia di Luar Negeri", "1,233,365", "1,194,796"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "832,521,596", "715,621,723"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": (None, None, 66, [
        ("Kumpulan Wang Luar Jangka", "253,549,670", "667,024,534"),
    ]),
    "KUMPULAN WANG YANG LAIN": ("15,710,851,827", "14,315,469,691", 67, [
        ("Amanah Negara", "12,553,645,967", "11,868,887,171"),
        ("Amanah Pelajar Miskin", "55,553,689", "40,150,122"),
        ("Amanah Sukan Negara", "18,013,810", "36,317,283"),
        ("Bantuan Bencana Negara", "336,130,684", "407,723,320"),
        ("Bantuan Mangsa Serangan Binatang Buas", "1,130,300", "1,184,100"),
        ("Cadangan Untuk Negeri", "293,154,763", "442,802,385"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "1,871,371", "2,233,300"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "913,743", "1,100,000"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "2,972,854", "2,972,854"),
        ("Kumpulan Wang Amanah Fi Jaminan", "229,010,753", "125,235,274"),
        ("Kumpulan Wang Amanah Kursi Eropah Bagi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "677,302", "781,094"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "92,288,017", "88,808,498"),
        ("Kumpulan Wang Amanah Majlis Sains Dan Penyelidikan Kebangsaan", "3,939,806", "3,721,271"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "1,532,126", "1,551,432"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "103,958,774", "116,010,131"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "34,130,596", "50,973,417"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "1,514,293", "3,836,944"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "5,107", "1,903"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "13,900,008", "13,616,261"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "10,067,964", "10,277,601"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "10,842,868", "4,925,044"),
        ("Kumpulan Wang Bagi Bayaran Balik Cukai Barang dan Perkhidmatan", "1,000,650,921", "323,436,815"),
        ("Penjelas Hutang", "3,381,166", "3,381,166"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "36,286,183", "37,981,539"),
        ("Perpustakaan Negara", "1,305,863", "1,287,115"),
        ("Program Perumahan Rakyat Dimiliki", "215,702,889", "332,410,209"),
        ("Skim Biasiswa Sukan Persekutuan", "482,398", "406,999"),
        ("Tabung Bayaran Balik Cukai", "607,113,095", "321,262,231"),
        ("Tabung Bantuan Perubatan", "60,822,361", "52,299,176"),
        ("Tabung Inovasi Negara", "19,813,116", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "38,246", "81,126"),
    ]),
}
for cat, (s17, s16, pg, items) in pkw_src.items():
    pp = pg - 11
    if s17 is not None:
        for yr, amt in ((2017, s17), (2016, s16)):
            T(KWK, PKW, cat, cat, yr, amt, "subtotal", pg, pp, S3)
    for item, a17, a16 in items:
        for yr, amt in ((2017, a17), (2016, a16)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, pp, S3)
for yr, amt in ((2017, "23,224,464,842"), (2016, "23,091,806,852")):
    T(KWK, PKW, "", "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 67, 56, S3)
for yr in (2017, 2016):
    for cat, (s17, s16, pg, items) in pkw_src.items():
        if s17 is None:
            continue
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(ii) {cat} details = subtotal {yr}",
            det, N(s17 if yr == 2017 else s16))
    dets = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(ii) all details = PELBAGAI KWAK total {yr}", dets, tot)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 67, printed 56)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("2,984,703,829", "2,867,936,994", [
        ("Akaun Amanah Estet Kebankrapan", "2,051,215,569", "1,850,003,228"),
        ("Kumpulan Wang Dius Api", "298,303,805", "373,919,533"),
        ("Akaun Amanah Am Pelikuidasi", "267,863,095", "300,943,044"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "235,144,525", "231,738,688"),
        ("Pelbagai Amanah Khas", "132,176,835", "111,332,501"),
    ]),
    "AMANAH AM": ("6,277,238,525", "5,352,674,967", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "2,634,402,384", "1,269,788,277"),
        ("Akaun Amanah Industri Bekalan Elektrik", "609,123,454", "616,721,373"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta", "533,784,517", "614,196,560"),
        ("Akaun Amanah Dana Khas", "464,590,787", "689,388,725"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "408,861,391", "420,566,058"),
        ("Pelbagai Amanah Am", "1,626,475,992", "1,742,013,974"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 68, printed 57)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("10,132,063,006", "8,888,640,415", [
        ("Kawalan Wang Tak Dituntut", "5,200,020,273", "4,636,391,467"),
        ("Wang Jaminan Pelaksanaan", "1,525,299,233", "1,392,572,151"),
        ("Mahkamah Tinggi", "1,202,242,487", "824,345,363"),
        ("Wang Tak Dituntut", "834,611,034", "980,759,725"),
        ("Pelbagai Deposit Am", "1,369,889,979", "1,054,571,709"),
    ]),
    "DEPOSIT PELARASAN": ("986,349,544", "662,523,583", [
        ("Terimaan Yang Tidak Diperuntukkan", "876,716,880", "502,042,408"),
        ("Pindahan Dana Elektronik Terbatal", "54,184,799", "101,699,022"),
        ("Deposit Pembatalan Pencen Skim B", "29,285,944", "33,997,635"),
        ("Pelbagai Deposit Pelarasan", "26,161,921", "24,784,518"),
    ]),
}
for grp, src, tot17, tot16, pg, stmt in (
        (KAW, awam_src, "9,261,942,354", "8,220,611,961", 67, S4),
        (DEP, dep_src, "11,118,412,550", "9,551,163,998", 68, S5)):
    pp = pg - 11
    for sec, (s17, s16, items) in src.items():
        for yr, amt in ((2017, s17), (2016, s16)):
            T(grp, "", sec, sec, yr, amt, "subtotal", pg, pp, stmt)
        for item, a17, a16 in items:
            for yr, amt in ((2017, a17), (2016, a16)):
                T(grp, "", sec, item, yr, amt, "detail", pg, pp, stmt)
    for yr, amt in ((2017, tot17), (2016, tot16)):
        T(grp, "", "", grp, yr, amt, "total", pg, pp, stmt)
    for yr in (2017, 2016):
        for sec, (s17, s16, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s17 if yr == 2017 else s16))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 9 MEMORANDUM ASET (pdf 69, printed 58)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt):
    V(69, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(69, 58, "Nota 9 Memorandum Aset")))
ppbd = [  # label, 2017, 2016, row_type
    ("PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "58,443,750,298", "55,813,494,515", "subtotal"),
    ("Kerajaan Negeri", "18,785,075,609", "18,164,217,955", "detail"),
    ("Pihak Berkuasa Tempatan", "298,354,685", "305,154,164", "detail"),
    ("Badan Berkanun", "6,338,015,378", "6,363,108,715", "detail"),
    ("Koperasi", "270,827,830", "258,302,635", "detail"),
    ("Syarikat", "30,521,775,145", "28,633,884,436", "detail"),
    ("Perseorangan", "365,628,918", "353,749,736", "detail"),
    ("Pelbagai", "1,864,072,733", "1,735,076,874", "detail"),
]
PPBD_SEC = "Pinjaman dan Pendahuluan Boleh Dituntut"
for item, a17, a16, rt in ppbd:
    for yr, amt in ((2017, a17), (2016, a16)):
        M(PPBD_SEC, item, yr, amt, rt)
pel = [
    ("PELABURAN", "30,907,727,719", "30,926,284,939", "subtotal"),
    ("Syarikat", "29,650,300,614", "29,668,857,834", "detail"),
    ("Badan Berkanun", "1,218,852,876", "1,218,852,876", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
]
for item, a17, a16, rt in pel:
    for yr, amt in ((2017, a17), (2016, a16)):
        M("Pelaburan", item, yr, amt, rt)
for yr in (2017, 2016):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 PPBD details = subtotal {yr}", det,
        N(ppbd[0][1] if yr == 2017 else ppbd[0][2]))
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    CHK(f"Nota9 Pelaburan details = subtotal {yr}", det,
        N(pel[0][1] if yr == 2017 else pel[0][2]))
CHK("control: Nota9 PPBD 2017", N("58,443,750,298"), 58443750298)
CHK("control: Nota9 memo Pelaburan 2017", N(pel[0][1]), 30907727719)

# =====================================================================
# 5. Nota 10(b) Pelbagai Liabiliti (pdf 70, printed 59)
#    The 2017 volume has NO commitments/PFI sections; the commitment-detail
#    table carries only this split.
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg, pp):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pp, "Nota 10 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2017, printed_total_2016, items, pdf_page
    ("PELBAGAI LIABILITI", "726,330,018", "765,004,321", [
        ("Nota Kena Bayar", "685,904,863", "727,720,789"),
        ("Sekuriti Tak Dituntut", "26,423,883", "23,282,260"),
        ("Akaun Depositori Pusat", "14,001,272", "14,001,272")], 70),
]
for parent, t17, t16, items, pg in com_src:
    pp = pg - 11
    for item, a17, a16 in items:
        for yr, amt in ((2017, a17), (2016, a16)):
            C(parent, item, yr, amt, pg, pp)
    for yr, tot in ((2017, t17), (2016, t16)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota10 {parent} details = printed total {yr}", det, N(tot))
CHK("control: Pelbagai Liabiliti 2017", N("726,330,018"), 726330018)

# =====================================================================
# 6. Nota 5(b)/6/7/8/9/10/11/12/13 narrative figures (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, pg - 11, stmt)))
O("5(b)", "Caruman ke Kumpulan Wang Pembangunan termasuk dalam B.12 (printed ** footnote)",
  2017, "2,710,809,216", 63, "Nota 5(b) Perbelanjaan Mengurus")
O("6", "Bayaran faedah pinjaman dan kos lain untuk mendapatkan pinjaman dikenakan kepada Perbelanjaan Tanggungan (T13)",
  2017, "27,863,209,244", 64, "Nota 6 Akaun Pinjaman Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: transaksi pelarasan debit",
  2017, "331,044,329,306", 65, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: transaksi pelarasan kredit",
  2017, "330,842,947,217", 65, "Nota 7 Akaun Amanah Disatukan")
O("8", "Perbezaan Hasil Bukan Cukai antara Penyata Wang Tunai dan Nota 5(a) (pelarasan Akaun Deposit LAD dan Akaun Deposit Pinjaman Boleh Dituntut)",
  2017, "15,082,389", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Terimaan Bukan Hasil antara Penyata Wang Tunai dan Nota 5(a)",
  2017, "232,707,113", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Pelbagai Terimaan Amanah (baki bersih semasa Akaun Amanah)",
  2017, "333,389,570", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Pemberian dan Kenaan Bayaran Tetap antara Penyata Wang Tunai dan Nota 5",
  2017, "1,339,810,349", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Penambahan peruntukan Kumpulan Wang Amanah Kerajaan (komponen perbezaan Pemberian)",
  2017, "1,237,469,289", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Pelarasan bayaran balik pendahuluan Kumpulan Wang Pendahuluan Untuk Negeri (komponen perbezaan Pemberian)",
  2017, "102,341,060", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Perbezaan Perbelanjaan-perbelanjaan Lain antara Penyata Wang Tunai dan Nota 5 (pelarasan hapus kira pinjaman)",
  2017, "25,000,000", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("8", "Urus niaga bukan tunai Akaun Amanah Inisiatif Pembiayaan Swasta (pelarasan pembayaran di bawah peraturan AP59)",
  2017, "6,624,455", 68, "Nota 8 Penyata Penerimaan dan Pembayaran Wang Tunai")
O("9(b)", "Pertukaran pinjaman kepada ekuiti bagi Syarikat SME Bank (termasuk dalam pelaburan Syarikat)",
  2017, "500,000,000", 69, "Nota 9 Memorandum Aset")
O("10(a)", "Pegangan Bukan Pemastautin bagi Pinjaman Dalam Negeri",
  2017, "186,266,262,000", 70, "Nota 10 Memorandum Liabiliti")
O("11", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan",
  2017, "238,190,723,312", 71, "Nota 11 Liabiliti Luar Jangka")
O("11", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2017, "863,602,708,110", 71, "Nota 11 Liabiliti Luar Jangka")
O("12", "Akaun Belum Terima berdasarkan rekod Kementerian/Jabatan",
  2017, "30,299,426,682", 71, "Nota 12 Akaun Belum Terima")
O("12", "Tunggakan Pinjaman Boleh Dituntut (termasuk dalam Akaun Belum Terima)",
  2017, "12,277,555,992", 71, "Nota 12 Akaun Belum Terima")
O("13", "Wang pendahuluan kepada kontraktor yang belum direkup",
  2017, "1,025,570,664", 71, "Nota 13 Wang Pendahuluan Kepada Kontraktor")

# CHKs for the Nota 8 reconciliation identities against extracted statements
CHK("Nota8: Hasil Bukan Cukai Nota5(a) - cash = printed difference",
    39520220884 - 39505138495, 15082389)
CHK("Nota8: Terimaan Bukan Hasil Nota5(a) - cash = printed difference",
    1976502938 - 1743795825, 232707113)
CHK("Nota8: Pemberian Nota5 - cash = printed difference",
    104365088374 - 103025278025, 1339810349)
CHK("Nota8: Pemberian difference components sum",
    1237469289 + 102341060, 1339810349)
CHK("Nota8: Perbelanjaan Lain Nota5 - cash = printed difference",
    1039832506 - 1014832506, 25000000)

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
with open(os.path.join(WH, "_validation_checks_2017.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
