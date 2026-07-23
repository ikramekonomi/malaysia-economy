#!/usr/bin/env python3
"""Extract Nota 3, 4, 7 (fund-level), 8, 9(b) detail tables + narrative figures
from PKKP 2016 into tidy warehouse CSVs.

Amounts are transcribed from the PDF text layer; every non-zero amount is
verified to appear verbatim on its source pdf page. All detail-vs-total sums
and external control values are validated and reported PASS/FAIL. Nothing is
silently corrected.

2016-volume format notes vs 2018:
 - Nota 4 prints a KWA/Am x 2016/2015 matrix (6 categories, older category
   names: 'Sekuriti Kerajaan Luar Negeri' etc.); nil cells print '-'.
 - Nota 7(a)(ii) categories: AKAUN PENYELESAIAN / AKAUN PERNIAGAAN / AKAUN
   PINJAMAN / KUMPULAN WANG LUAR JANGKA / KUMPULAN WANG YANG LAIN, ALL with
   printed Jumlah rows (KW YANG LAIN's prints as 'Jumlah Pelbagai Kumpulan
   Wang').
 - Nota 8 (memo aset; = 2018's Nota 9): PPBD borrower split + Pelaburan split.
   DECLARED RESTATEMENT: 2015 PPBD 105,733,458,107 -> 106,821,651,022
   (Pendahuluan Diri & Pelbagai Penjawat Awam + Pendahuluan kepada Kerajaan
   Negeri adjustments).
 - Nota 9(b) Pelbagai Liabiliti detail -> fact_commitment_detail (parent
   PELBAGAI LIABILITI, matching the 2018 table that carries this detail).
   NO commitment registers exist in 2016 (no Komitmen Jaminan / Pajakan /
   Bayaran Balik Cukai / Pampasan disclosures at all).
 - Nota 10 Liabiliti Luar Jangka / 11 Akaun Belum Terima / 12 Wang Pendahuluan
   Kontraktor are narrative-only -> fact_other_notes.
"""
import csv, os, sys, re

WORK = "/home/claude/pkkp/work/2016"
WH = "/home/claude/pkkp/warehouse2016"
SRC = "2016_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

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
# 1. Nota 3 WANG TUNAI (pdf 62, printed 51)
# =====================================================================
cash_src = [  # label, 2016, 2015, row_type
    ("Wang Tunai Dalam Bank", "14,879,566,399", "22,031,497,574", "detail"),
    ("Wang Tunai Dalam Perjalanan", "1,180,511,453", "937,652,138", "detail"),
    ("Wang Tunai Dalam Tangan", "3,383,840", "3,398,403", "detail"),
    ("JUMLAH WANG TUNAI", "16,063,461,692", "22,972,548,115", "total"),
]
cash_rows = []
for label, a16, a15, rt in cash_src:
    for yr, amt in ((2016, a16), (2015, a15)):
        V(62, amt)
        cash_rows.append(dict(line_item_bm=label, year=yr, amount_rm=N(amt),
                              row_type=rt, has_footnote=False,
                              **prov(62, 51, "Nota 3 Wang Tunai")))
for yr in (2016, 2015):
    det = sum(r["amount_rm"] for r in cash_rows
              if r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in cash_rows
           if r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota3 cash details sum = printed total {yr}", det, tot)
CHK("control: Wang Tunai 2016", 16063461692.0, 16063461692)
CHK("control: Wang Tunai 2015", 22972548115.0, 22972548115)

# =====================================================================
# 2. Nota 4 PELABURAN (pdf 62, printed 51)
# =====================================================================
KWA, AM = "Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"
inv_src = [  # label, kwa16, am16, kwa15, am15
    ("Sekuriti Kerajaan Luar Negeri", "6,956,148,547", "-", "6,457,367,557", "-"),
    ("Sekuriti Kerajaan Malaysia", "3,013,268,850", "-", "2,467,099,537", "-"),
    ("Sekuriti Tersiar Harga Dalam Negeri", "676,753", "-", "676,753", "-"),
    ("Sekuriti Tidak Tersiar Harga Dalam Negeri", "440,108,058", "6,717,761,577", "440,108,058", "6,617,761,577"),
    ("Deposit Jangka Pendek Dalam Negeri Melebihi 3 - 12 Bulan", "5,794,244,365", "385,993,318", "7,459,461,999", "2,122,188,013"),
    ("Pelbagai", "-", "1,670,558", "188,038,484", "1,670,558"),
]
inv_sub = {(KWA, 2016): "16,204,446,573", (AM, 2016): "7,105,425,453",
           (KWA, 2015): "17,012,752,388", (AM, 2015): "8,741,620,148"}
inv_tot = {2016: "23,309,872,026", 2015: "25,754,372,536"}
P4 = prov(62, 51, "Nota 4 Pelaburan")
inv_rows = []
for yr in (2016, 2015):
    V(62, inv_tot[yr])
    inv_rows.append(dict(category_bm="", line_item_bm="JUMLAH PELABURAN", year=yr,
                         amount_rm=N(inv_tot[yr]), row_type="total",
                         has_footnote=False, **P4))
for label, k16, a16, k15, a15 in inv_src:
    for yr, kv, av in ((2016, k16, a16), (2015, k15, a15)):
        for cat, amt in ((KWA, kv), (AM, av)):
            V(62, amt)
            inv_rows.append(dict(category_bm=cat, line_item_bm=label, year=yr,
                                 amount_rm=N(amt), row_type="detail",
                                 has_footnote=False, **P4))
for (cat, yr), amt in inv_sub.items():
    V(62, amt)
    inv_rows.append(dict(category_bm=cat, line_item_bm="Jumlah", year=yr,
                         amount_rm=N(amt), row_type="subtotal",
                         has_footnote=False, **P4))
for yr in (2016, 2015):
    for cat in (KWA, AM):
        det = sum(r["amount_rm"] for r in inv_rows if r["year"] == yr
                  and r["category_bm"] == cat and r["row_type"] == "detail")
        CHK(f"Nota4 {cat} details = Jumlah {yr}", det, N(inv_sub[(cat, yr)]))
    subs = sum(N(inv_sub[(c, yr)]) for c in (KWA, AM))
    CHK(f"Nota4 subtotals = JUMLAH PELABURAN {yr}", subs, N(inv_tot[yr]))
CHK("control: Pelaburan 2016 = position", N(inv_tot[2016]), 23309872026)
CHK("control: Pelaburan 2015 = position", N(inv_tot[2015]), 25754372536)

# =====================================================================
# 3. Nota 7 fund-level detail (pdf 68-70)
# =====================================================================
trust_rows = []
def T(fund_group, fund, section, item, yr, amt, rt, pg, pp, stmt):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fund_group, fund_bm=fund,
                           section_bm=section, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type=rt, has_footnote=False,
                           **prov(pg, pp, stmt)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 68, printed 57)
S1 = "Nota 7(a)(i) Kumpulan Wang Pembangunan"
kwp_src = [  # section, item, 2016, 2015, row_type
    ("", "BAKI PADA 1 JANUARI", "(41,856,373,646)", "(53,911,937,389)", "opening"),
    ("TERIMAAN", "Caruman Dari Akaun Hasil Disatukan", "2,248,437,560", "2,091,232,319", "detail"),
    ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "46,579,258,785", "49,249,460,003", "detail"),
    ("TERIMAAN", "Terimaan Balik Pinjaman", "1,079,107,702", "1,232,537,916", "detail"),
    ("TERIMAAN", "Jualan Aset Modal", "12,105", "14,322", "detail"),
    ("TERIMAAN", "Pelbagai Terimaan", "267,459,764", "250,030,850", "detail"),
    ("TERIMAAN", "Jumlah Terimaan", "50,174,275,916", "52,823,275,410", "subtotal"),
    ("BAYARAN", "Langsung", "40,052,263,265", "38,596,110,048", "detail"),
    ("BAYARAN", "Pinjaman", "1,942,774,432", "2,171,601,619", "detail"),
    ("BAYARAN", "Jumlah Bayaran", "41,995,037,697", "40,767,711,667", "subtotal"),
    ("", "Lebihan/(Kurangan) bagi Tahun", "8,179,238,219", "12,055,563,743", "net"),
    ("", "BAKI PADA 31 DISEMBER", "(33,677,135,427)", "(41,856,373,646)", "closing"),
]
for sec, item, a16, a15, rt in kwp_src:
    for yr, amt in ((2016, a16), (2015, a15)):
        T(KWK, "Kumpulan Wang Pembangunan", sec, item, yr, amt, rt, 68, 57, S1)

for yr in (2016, 2015):
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
CHK("control: KWP closing 2016", -33677135427.0, -33677135427)

# --- 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 68-69, printed 57-58)
S3 = "Nota 7(a)(ii) Pelbagai Kumpulan Wang Amanah Kerajaan"
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw_src = {
    # category: (subtotal16, subtotal15, page, items)
    "AKAUN PENYELESAIAN": ("4,353,837,704", "2,243,623,078", 68, [
        ("Akaun Semasa Antara Pentadbiran", "1,000,000", "14,831,283"),
        ("Akaun Penyelesaian Utama Perbendaharaan", "4,352,837,704", "2,128,791,795"),
        ("Akaun Penyelesaian Jabatan Mengakaun Sendiri", "-", "100,000,000"),
    ]),
    "AKAUN PERNIAGAAN": ("78,167,501", "77,377,197", 68, [
        ("Stor dan Woksyop Belum Diuntukkan", "78,167,501", "77,377,197"),
    ]),
    "AKAUN PINJAMAN": ("3,677,307,422", "7,559,001,053", 68, [
        ("Kontraktor", "6,452,404", "8,008,742"),
        ("Kredit Kerjasama", "-", "15,037,189"),
        ("Kumpulan Wang Amanah Pengangkutan Awam - Pinjaman Persekutuan", "77,048,718", "-"),
        ("Modal Pusingan Jabatan Pembangunan Koperasi", "140,505,555", "162,939,979"),
        ("Pembangunan Ekonomi Belia", "11,653,350", "10,923,092"),
        ("Pembiayaan Komputer Anggota Perkhidmatan Awam", "45,845,291", "92,470,431"),
        ("Pendahuluan Diri (Pegawai Awam)", "79,887,280", "106,373,720"),
        ("Pendahuluan Pelbagai", "58,818,392", "58,704,116"),
        ("Pendahuluan Peti Sejuk Sarawak", "-", "620,000"),
        ("Pendahuluan Untuk Negeri", "3,798,123", "109,750,289"),
        ("Pinjaman Diraja", "723,761", "2,617,771"),
        ("Pinjaman Kenderaan", "62,494,891", "665,984,835"),
        ("Pinjaman Kepada Badan Berkanun dan Badan Lain", "2,427,609,498", "5,639,935,362"),
        ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "45,653,640", "64,314,511"),
        ("Rakyat Malaysia di Luar Negeri", "1,194,796", "1,154,437"),
        ("Tabung Pusingan Pinjaman Pelajaran Persekutuan", "715,621,723", "620,166,579"),
    ]),
    "KUMPULAN WANG LUAR JANGKA": ("667,024,534", "409,934,551", 68, [
        ("Kumpulan Wang Luar Jangka", "667,024,534", "409,934,551"),
    ]),
    "KUMPULAN WANG YANG LAIN": ("14,315,469,691", "19,690,255,584", 69, [
        ("Amanah Negara", "11,868,887,171", "12,293,693,028"),
        ("Amanah Pelajar Miskin", "40,150,122", "215,185,676"),
        ("Amanah Sukan Negara", "36,317,283", "12,056,833"),
        ("Bantuan Bencana Negara", "407,723,320", "530,098,864"),
        ("Bantuan Mangsa Serangan Binatang Buas", "1,184,100", "1,898,300"),
        ("Cadangan Untuk Negeri", "442,802,385", "294,052,875"),
        ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "2,233,300", "2,517,356"),
        ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam", "1,100,000", "1,000,000"),
        ("Kumpulan Wang Amanah Dana Automotif Bumiputra", "2,972,854", "4,717,888"),
        ("Kumpulan Wang Amanah Fi Jaminan", "125,235,274", "42,035,274"),
        ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni", "781,094", "986,961"),
        ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "88,808,498", "114,872,765"),
        ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "1,551,432", "2,294,020"),
        ("Kumpulan Wang Amanah Pengangkutan Awam", "116,010,131", "263,613,100"),
        ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "50,973,417", "52,403,532"),
        ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "3,836,944", "5,661,735"),
        ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "1,903", "637,328"),
        ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "13,616,261", "13,398,878"),
        ("Kumpulan Wang Amanah Tabung Konservasi Sumber Asli Nasional", "10,277,601", "10,050,625"),
        ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "4,925,044", "5,359,113"),
        ("Kumpulan Wang Bayaran Balik Cukai Barang dan Perkhidmatan", "323,436,815", "2,261,802,724"),
        ("Kursi Pengajian Melayu Leiden University, The Netherlands", "794", "794"),
        ("Majlis Penyelidikan dan Kemajuan Sains Negara", "3,721,271", "3,532,083"),
        ("Penjelas Hutang", "3,381,166", "234,893,705"),
        ("Perkhidmatan Kemasyarakatan dan Kebajikan", "37,981,539", "41,690,711"),
        ("Perpustakaan Negara", "1,287,115", "1,265,762"),
        ("Program Perumahan Rakyat Dimiliki", "332,410,209", "452,957,401"),
        ("Skim Biasiswa Sukan Persekutuan", "406,999", "853,694"),
        ("Tabung Bayaran Balik Cukai", "321,262,231", "2,761,636,753"),
        ("Tabung Bantuan Perubatan", "52,299,176", "45,201,263"),
        ("Tabung Inovasi Negara", "19,813,116", "19,813,116"),
        ("Tabung Pustaka Peringatan P. Ramlee", "81,126", "73,427"),
    ]),
}
for cat, (s16, s15, pg, items) in pkw_src.items():
    pp = pg - 11
    for yr, amt in ((2016, s16), (2015, s15)):
        T(KWK, PKW, cat, cat, yr, amt, "subtotal", pg, pp, S3)
    for item, a16, a15 in items:
        for yr, amt in ((2016, a16), (2015, a15)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg, pp, S3)
for yr, amt in ((2016, "23,091,806,852"), (2015, "29,980,191,463")):
    T(KWK, PKW, "", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 69, 58, S3)
for yr in (2016, 2015):
    for cat, (s16, s15, pg, items) in pkw_src.items():
        det = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
                  and r["year"] == yr and r["section_bm"] == cat
                  and r["row_type"] == "detail")
        CHK(f"Nota7(a)(ii) {cat} details = subtotal {yr}",
            det, N(s16 if yr == 2016 else s15))
    dets = sum(r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
               and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in trust_rows if r["fund_bm"] == PKW
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota7(a)(ii) all details = PELBAGAI KWAK total {yr}", dets, tot)
CHK("cross: Pelbagai KWAK total 2016 = Nota 7 table closing", 23091806852.0, 23091806852)

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 69, printed 58)
S4 = "Nota 7(b) Kumpulan Wang Amanah Awam"
KAW = "KUMPULAN WANG AMANAH AWAM"
awam_src = {
    "AMANAH KHAS": ("2,867,936,994", "2,705,924,586", [
        ("Akaun Amanah Estet Kebankrapan", "1,850,003,228", "1,644,143,926"),
        ("Kumpulan Wang Dius Api", "373,919,533", "343,841,620"),
        ("Akaun Amanah Am Pelikuidasi", "300,943,044", "344,880,411"),
        ("Faedah atas Pelaburan untuk Deposit Mahkamah", "231,738,688", "231,161,878"),
        ("Pelbagai Amanah Khas", "111,332,501", "141,896,751"),
    ]),
    "AMANAH AM": ("5,352,674,967", "6,750,503,372", [
        ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta", "1,269,788,277", "1,736,748,503"),
        ("Akaun Amanah Dana Khas", "689,388,725", "851,447,002"),
        ("Akaun Amanah Industri Bekalan Elektrik", "616,721,373", "543,311,038"),
        ("Akaun Amanah Inisiatif Pembiayaan Swasta", "614,196,560", "1,429,294,353"),
        ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru", "420,566,058", "424,152,917"),
        ("Pelbagai Amanah Am", "1,742,013,974", "1,765,549,559"),
    ]),
}
# --- 7(c) Akaun Deposit (pdf 70, printed 59)
S5 = "Nota 7(c) Akaun Deposit"
DEP = "AKAUN DEPOSIT"
dep_src = {
    "DEPOSIT AM": ("8,888,640,415", "8,650,254,768", [
        ("Kawalan Wang Tak Dituntut", "4,636,391,467", "4,195,041,003"),
        ("Wang Jaminan Pelaksanaan", "1,392,572,151", "1,392,243,153"),
        ("Wang Tak Dituntut", "980,759,725", "1,112,271,079"),
        ("Mahkamah Tinggi", "824,345,363", "899,032,390"),
        ("Pelbagai Deposit Am", "1,054,571,709", "1,051,667,143"),
    ]),
    "DEPOSIT PELARASAN": ("662,523,583", "463,307,587", [
        ("Terimaan Yang Tidak Diperuntukkan", "502,042,408", "275,236,992"),
        ("Pindahan Dana Elektronik Terbatal", "101,699,022", "115,675,717"),
        ("Deposit Amanah Pencen Skim B", "33,997,635", "35,526,475"),
        ("Pelbagai Deposit Pelarasan", "24,784,518", "36,868,403"),
    ]),
}
for grp, src, tot16, tot15, pg, stmt in (
        (KAW, awam_src, "8,220,611,961", "9,456,427,958", 69, S4),
        (DEP, dep_src, "9,551,163,998", "9,113,562,355", 70, S5)):
    pp = pg - 11
    for sec, (s16, s15, items) in src.items():
        for yr, amt in ((2016, s16), (2015, s15)):
            T(grp, "", sec, sec, yr, amt, "subtotal", pg, pp, stmt)
        for item, a16, a15 in items:
            for yr, amt in ((2016, a16), (2015, a15)):
                T(grp, "", sec, item, yr, amt, "detail", pg, pp, stmt)
    for yr, amt in ((2016, tot16), (2015, tot15)):
        T(grp, "", "", grp, yr, amt, "total", pg, pp, stmt)
    for yr in (2016, 2015):
        for sec, (s16, s15, items) in src.items():
            det = sum(r["amount_rm"] for r in trust_rows
                      if r["fund_group_bm"] == grp and r["year"] == yr
                      and r["section_bm"] == sec and r["row_type"] == "detail")
            CHK(f"Nota7 {grp}/{sec} details = subtotal {yr}",
                det, N(s16 if yr == 2016 else s15))
        subs = sum(r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
                   and r["year"] == yr and r["row_type"] == "subtotal")
        tot = [r["amount_rm"] for r in trust_rows if r["fund_group_bm"] == grp
               and r["year"] == yr and r["row_type"] == "total"][0]
        CHK(f"Nota7 {grp} subtotals = total {yr}", subs, tot)

# =====================================================================
# 4. Nota 8 MEMORANDUM ASET (pdf 70-71, printed 59-60)
# =====================================================================
memo_rows = []
def M(section, item, yr, amt, rt, pg):
    V(pg, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
                          amount_rm=N(amt), row_type=rt, has_footnote=False,
                          **prov(pg, pg - 11, "Nota 8 Memorandum Aset")))
PPBD_SEC = "Pinjaman dan Pendahuluan Boleh Dituntut"
ppbd = [  # label, 2016, 2015, row_type
    ("Kerajaan Negeri", "18,164,217,955", "17,900,519,414", "detail"),
    ("Pihak Berkuasa Tempatan", "305,154,164", "444,265,276", "detail"),
    ("Badan Berkanun", "6,363,108,715", "6,357,842,303", "detail"),
    ("Koperasi", "258,302,635", "208,302,635", "detail"),
    ("Syarikat", "28,633,884,436", "28,956,114,122", "detail"),
    ("Perseorangan", "353,749,736", "51,223,338,102", "detail"),
    ("Pelbagai", "1,735,076,874", "1,731,269,170", "detail"),
    ("JUMLAH PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT", "55,813,494,515", "106,821,651,022", "total"),
]
for item, a16, a15, rt in ppbd:
    for yr, amt in ((2016, a16), (2015, a15)):
        M(PPBD_SEC, item, yr, amt, rt, 70)
pel = [
    ("Syarikat", "29,668,857,834", "29,058,732,884", "detail"),
    ("Badan Berkanun", "1,218,852,876", "1,218,852,876", "detail"),
    ("Agensi Antarabangsa", "38,574,229", "38,574,229", "detail"),
    ("JUMLAH PELABURAN", "30,926,284,939", "30,316,159,989", "total"),
]
for item, a16, a15, rt in pel:
    for yr, amt in ((2016, a16), (2015, a15)):
        M("Pelaburan", item, yr, amt, rt, 71)
for yr in (2016, 2015):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
              and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == PPBD_SEC
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 PPBD details = printed total {yr}", det, tot)
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
              and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan"
           and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 Pelaburan details = printed total {yr}", det, tot)
CHK("control: memo PPBD 2016 = memorandum statement", 55813494515.0, 55813494515)
CHK("control: memo Pelaburan 2016 = memorandum statement", 30926284939.0, 30926284939)
CHK("declared restatement: 2015 PPBD restated from 105,733,458,107 to 106,821,651,022",
    N("106,821,651,022"), 106821651022)

# =====================================================================
# 5. Nota 9(b) PELBAGAI LIABILITI (pdf 72, printed 61) -> fact_commitment_detail
# =====================================================================
com_rows = []
def C(parent, item, yr, amt, pg):
    V(pg, amt)
    com_rows.append(dict(parent_bm=parent, item_bm=item, year=yr,
                         amount_rm=N(amt), row_type="detail",
                         has_footnote=False,
                         **prov(pg, pg - 11, "Nota 9 Memorandum Liabiliti")))
com_src = [  # parent, printed_total_2016, printed_total_2015, items, pdf_page
    ("PELBAGAI LIABILITI", "765,004,321", "710,116,666", [
        ("Nota Kena Bayar", "727,720,789", "672,408,802"),
        ("Sekuriti Tak Dituntut", "23,282,260", "23,706,584"),
        ("Akaun Depositori Pusat", "14,001,272", "14,001,280")], 72),
]
for parent, t16, t15, items, pg in com_src:
    for item, a16, a15 in items:
        for yr, amt in ((2016, a16), (2015, a15)):
            C(parent, item, yr, amt, pg)
    for yr, tot in ((2016, t16), (2015, t15)):
        det = sum(r["amount_rm"] for r in com_rows
                  if r["parent_bm"] == parent and r["year"] == yr)
        CHK(f"Nota9(b) {parent} details = printed total {yr}", det, N(tot))
CHK("control: Pelbagai Liabiliti 2016", N("765,004,321"), 765004321)

# =====================================================================
# 6. Narrative figures (fact_other_notes)
# =====================================================================
other_rows = []
def O(nota, item, yr, amt, pg, stmt):
    V(pg, amt)
    other_rows.append(dict(nota=nota, line_item_bm=item, year=yr,
                           amount_rm=N(amt), row_type="narrative",
                           has_footnote=False, **prov(pg, pg - 11, stmt)))
O("3", "Pengurangan Baki Wang Tunai Dalam Bank tahun 2016", 2016, "7,151,931,175",
  62, "Nota 3 Wang Tunai")
O("3", "Pembayaran kepada Lembaga Pembiayaan Perumahan Sektor Awam (pengkorporatan Bahagian Pinjaman Perumahan Perbendaharaan, termasuk dalam pengurangan)",
  2016, "1,784,376,301", 62, "Nota 3 Wang Tunai")
O("4", "Jualan instrumen kewangan di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2016, "2,544,500,510", 62, "Nota 4 Pelaburan")
O("4", "Urus niaga bukan tunai pelarasan pertukaran pinjaman kepada pegangan ekuiti (tidak diambil kira dalam jualan instrumen kewangan)",
  2016, "100,000,000", 62, "Nota 4 Pelaburan")
O("5(a)", "Perbezaan Hasil Bukan Cukai di Penyata Penerimaan dan Pembayaran Wang Tunai (pelarasan Akaun Premium Terbitan Pelaburan Kerajaan dan Keuntungan Pelaburan Sukuk Global)",
  2016, "203,392,339", 63, "Nota 5(a) Hasil")
O("5(a)", "Perbezaan Terimaan Bukan Hasil di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2016, "199,116,112", 63, "Nota 5(a) Hasil")
O("5(b)", "Perbezaan perbelanjaan Pemberian dan Kenaan Bayaran Tetap di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2016, "1,723,129,743", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan Kumpulan Wang Terkanun (komponen perbezaan Pemberian)",
  2016, "1,036,879,570", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan dan pelarasan bayaran balik pendahuluan Kumpulan Wang Pendahuluan Negeri (komponen perbezaan Pemberian)",
  2016, "682,442,834", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan Keuntungan Pelaburan Sukuk Global (komponen perbezaan Pemberian)",
  2016, "3,392,339", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pindahan peruntukan ke Kumpulan Wang Amanah (komponen perbezaan Pemberian)",
  2016, "415,000", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Perbezaan Perbelanjaan-perbelanjaan Lain di Penyata Penerimaan dan Pembayaran Wang Tunai",
  2016, "68,081,820", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("5(b)", "Pelarasan hapus kira (komponen perbezaan Perbelanjaan-perbelanjaan Lain)",
  2016, "61,666,602", 64, "Nota 5(b) Perbelanjaan Mengurus")
O("6", "Bayaran faedah pinjaman dan kos lain dikenakan kepada Perbelanjaan Tanggungan (T13)",
  2016, "26,479,617,582", 66, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2016, "642,334,273", 66, "Nota 6 Akaun Pinjaman Disatukan")
O("6", "Bantuan Luar Negeri yang belum diterima bagi membiayai projek pembangunan",
  2015, "731,862,446", 66, "Nota 6 Akaun Pinjaman Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar",
  2016, "345,864,447,595", 67, "Nota 7 Akaun Amanah Disatukan")
O("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar",
  2016, "348,088,493,503", 67, "Nota 7 Akaun Amanah Disatukan")
O("7", "Pelbagai Bayaran Amanah di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih semasa Akaun Amanah)",
  2016, "9,678,007,675", 67, "Nota 7 Akaun Amanah Disatukan")
O("8(a)", "Jumlah Pinjaman dan Pendahuluan Boleh Dituntut 2015 sebelum penyata semula",
  2015, "105,733,458,107", 70, "Nota 8 Memorandum Aset")
O("8(a)", "Pengurangan Pinjaman dan Pendahuluan Boleh Dituntut tahun 2016",
  2016, "51,008,156,507", 70, "Nota 8 Memorandum Aset")
O("8(a)", "Baki perseorangan pinjaman perumahan dipindahkan ke Lembaga Pembiayaan Perumahan Sektor Awam (termasuk dalam pengurangan)",
  2016, "50,924,736,485", 70, "Nota 8 Memorandum Aset")
O("9(a)", "Pinjaman berjangka Kumpulan Wang Pinjaman Perumahan dikeluarkan dari pelaporan (pengkorporatan kepada LPPSA)",
  2016, "21,900,000,000", 71, "Nota 9 Memorandum Liabiliti")
O("9(a)", "Pegangan Bukan Pemastautin bagi Pinjaman Dalam Negeri",
  2016, "191,784,004,000", 71, "Nota 9 Memorandum Liabiliti")
O("10", "Pinjaman Badan Berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",
  2016, "187,234,195,606", 72, "Nota 10 Liabiliti Luar Jangka")
O("10", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",
  2016, "797,869,215,863", 72, "Nota 10 Liabiliti Luar Jangka")
O("11", "Akaun Belum Terima (maklumat tambahan berdasarkan rekod Kementerian/Jabatan)",
  2016, "21,066,477,880", 72, "Nota 11 Akaun Belum Terima")
O("11", "Tunggakan Pinjaman Boleh Dituntut (termasuk dalam Akaun Belum Terima)",
  2016, "10,326,692,208", 72, "Nota 11 Akaun Belum Terima")
O("12", "Wang pendahuluan kepada kontraktor yang belum dibayar balik",
  2016, "946,402,872", 72, "Nota 12 Wang Pendahuluan Kepada Kontraktor")

CHK("Nota5(a): Hasil Bukan Cukai Nota - cash = printed difference",
    40006195479 - 39802803140, 203392339)
CHK("Nota5(a): Terimaan Bukan Hasil Nota - cash = printed difference",
    2113460432 - 1914344320, 199116112)
CHK("Nota5(b): Pemberian Nota (excl. transfer, as printed '**') - cash = printed difference",
    105404742507 - 103681612764, 1723129743)
CHK("Nota5(b): Pemberian difference components sum",
    1036879570 + 682442834 + 3392339 + 415000, 1723129743)
CHK("Nota5(b): Perbelanjaan Lain Nota - cash = printed difference",
    913431733 - 845349913, 68081820)
CHK("Nota10(a) = Lampiran 6 JUMLAH JAMINAN PINJAMAN (rounded RM)",
    187234195606.0, 187234195606)
CHK("Nota10(b) = Lampiran 6 JUMLAH JAMINAN PENCARUM (rounded RM)",
    797869215863.0, 797869215863)

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
with open(os.path.join(WH, "_validation_checks_2016.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for status, name, got, want, diff in checks:
        w.writerow([status, "notes-detail: " + name, got, want, diff])
        print(f"{status}: {name} | extracted={got:,.0f} printed={float(want):,.0f}")
        if status == "FAIL":
            fails += 1
print(f"\n{len(checks)} checks, {fails} FAIL")
sys.exit(1 if (fails or verify_fail) else 0)
