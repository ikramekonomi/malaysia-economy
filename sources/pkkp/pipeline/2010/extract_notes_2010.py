#!/usr/bin/env python3
# Extract Nota 3-12 tables from 2010 Federal Government Financial Statements.
# Output CSVs to /home/claude/pkkp/warehouse2010/ matching 2012 schemas.
import csv, os

OUT = "/home/claude/pkkp/warehouse2010"
SRC = "2010_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
os.makedirs(OUT, exist_ok=True)


def ff(x):
    """float-style formatting: 123 -> '123.0'; None/'' -> ''"""
    if x is None or x == "":
        return ""
    return repr(float(x))


def fi(x):
    """int-style formatting: 123 -> '123'; None/'' -> ''"""
    if x is None or x == "":
        return ""
    return str(int(x))


def pp(pdf):
    return pdf, pdf - 10


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"WROTE {name}: {len(rows)} rows")


# ============================================================
# NOTA 3 WANG TUNAI  -> fact_cash_components.csv   (pdf47)
# ============================================================
def build_cash():
    st = "Nota 3 Wang Tunai"
    pdf, pr = pp(47)
    data = [  # line_item, 2010, 2009
        ("Wang Tunai Dalam Bank", 21002073584, 26867892348),
        ("Wang Tunai Dalam Perjalanan", 568719734, 650154731),
        ("Wang Tunai Dalam Tangan", 2487360, 2071395),
        ("JUMLAH WANG TUNAI", 21573280678, 27520118474),
    ]
    rows = []
    for item, v10, v09 in data:
        rt = "total" if item.startswith("JUMLAH") else "detail"
        for yr, v in ((2010, v10), (2009, v09)):
            rows.append([item, yr, ff(v), rt, "False", SRC, pdf, pr, st])
    write_csv("fact_cash_components.csv",
              ["line_item_bm", "year", "amount_rm", "row_type", "has_footnote",
               "source_file", "pdf_page", "printed_page", "statement"], rows)


# ============================================================
# NOTA 4 PELABURAN  -> fact_investment_summary.csv  (pdf47)
# ============================================================
def build_investment():
    st = "Nota 4 Pelaburan"
    pdf, pr = pp(47)
    KWA = "Pelaburan Kumpulan Wang Amanah"
    AM = "Pelaburan Am"
    # item : (KWA10, AM10, KWA09, AM09)
    items = [
        ("Sekuriti Kerajaan Luar Negeri", 2353439585, 317321584, 2886603406, 360950154),
        ("Sekuriti Kerajaan Malaysia", 961563860, 0, 772602056, 0),
        ("Saham", 784811, 5348248987, 784811, 4582540117),
        ("Deposit Luar Negeri", 504567726, 49230388, 207758837, 33499075),
        ("Deposit Dalam Negeri", 8155696982, 2210000000, 7169015811, 0),
        ("Pelbagai", 440714432, 1670558, 0, 1670558),
    ]
    rows = []
    header = ["category_bm", "line_item_bm", "year", "amount_rm", "row_type",
              "has_footnote", "source_file", "pdf_page", "printed_page", "statement"]
    # JUMLAH PELABURAN total first (mirrors 2012 ordering)
    rows.append(["", "JUMLAH PELABURAN", 2010, ff(20343238913), "total", "False", SRC, pdf, pr, st])
    rows.append(["", "JUMLAH PELABURAN", 2009, ff(16015424825), "total", "False", SRC, pdf, pr, st])
    for item, k10, a10, k09, a09 in items:
        rows.append([KWA, item, 2010, ff(k10), "detail", "False", SRC, pdf, pr, st])
        rows.append([AM, item, 2010, ff(a10), "detail", "False", SRC, pdf, pr, st])
        rows.append([KWA, item, 2009, ff(k09), "detail", "False", SRC, pdf, pr, st])
        rows.append([AM, item, 2009, ff(a09), "detail", "False", SRC, pdf, pr, st])
    # Jumlah subtotals per category
    rows.append([KWA, "Jumlah", 2010, ff(12416767396), "subtotal", "False", SRC, pdf, pr, st])
    rows.append([AM, "Jumlah", 2010, ff(7926471517), "subtotal", "False", SRC, pdf, pr, st])
    rows.append([KWA, "Jumlah", 2009, ff(11036764921), "subtotal", "False", SRC, pdf, pr, st])
    rows.append([AM, "Jumlah", 2009, ff(4978659904), "subtotal", "False", SRC, pdf, pr, st])
    write_csv("fact_investment_summary.csv", header, rows)


# ============================================================
# NOTA 5 AKAUN HASIL DISATUKAN lead table
#   -> fact_revenue_account_statement.csv  (pdf48)
# ============================================================
def build_revenue_account_statement():
    st = "Nota 5 Akaun Hasil Disatukan"
    pdf, pr = pp(48)
    header = ["section_bm", "line_item_bm", "row_type", "year", "anggaran_disemak_rm",
              "sebenar_rm", "pct_anggaran", "has_footnote", "source_file",
              "pdf_page", "printed_page", "statement"]
    # (section, item, row_type, hf, ad2010, seb2010, pct2010, seb2009, pct2009)
    rows_def = [
        ("BAKI", "BAKI PADA 1 JANUARI", "opening", False, None, 11863127086, "", 11863127086, ""),
        ("HASIL", "Hasil Cukai", "detail", False, 107092070000, 109515185813, "102.26", 106504411011, "100.00"),
        ("HASIL", "Hasil Bukan Cukai", "detail", False, 53840291000, 48867434930, "90.76", 50789238902, "92.69"),
        ("HASIL", "Terimaan Bukan Hasil", "detail", False, 774792000, 793006447, "102.35", 1067563070, "214.87"),
        ("HASIL", "Hasil Wilayah-Wilayah Persekutuan", "detail", False, 424180000, 477335128, "112.53", 278091245, "92.21"),
        ("HASIL", "Jumlah Hasil", "subtotal", False, 162131333000, 159652962318, "98.47", 158639304228, "97.87"),
        ("PERBELANJAAN MENGURUS", "Emolumen", "detail", False, 43571884582, 46662939934, "107.09", 42778266363, "109.22"),
        ("PERBELANJAAN MENGURUS", "Perkhidmatan dan Bekalan", "detail", False, 24092865236, 23840844635, "98.95", 26372131596, "99.02"),
        ("PERBELANJAAN MENGURUS", "Aset", "detail", False, 1927281252, 1869375321, "97.00", 2581505478, "97.52"),
        ("PERBELANJAAN MENGURUS", "Pemberian dan Kenaan Bayaran Tetap", "detail", True, 78264039277, 78104600235, "99.80", 84650079062, "95.70"),
        ("PERBELANJAAN MENGURUS", "Perbelanjaan-perbelanjaan lain", "detail", False, 1208594753, 1154849140, "95.55", 684976820, "89.91"),
        ("PERBELANJAAN MENGURUS", "Perbelanjaan Mengurus (sebelum pindahan)", "subtotal", False, 149064665100, 151632609265, "101.72", 157066959319, "99.62"),
        ("PINDAHAN", "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", "transfer", False, "0.0", 8020353053, "", 1572344909, ""),
        ("PERBELANJAAN MENGURUS", "Jumlah Perbelanjaan Mengurus (selepas pindahan)", "total_after_transfer", False, 149064665100, 159652962318, "107.10", 158639304228, "100.62"),
        ("BAKI", "Lebihan/(Kurangan) bagi Tahun", "net", False, None, "0.0", "", "0.0", ""),
        ("BAKI", "BAKI PADA 31 DISEMBER", "closing", False, None, 11863127086, "", 11863127086, ""),
    ]
    rows = []
    for sec, item, rt, hf, ad, s10, p10, s09, p09 in rows_def:
        ad_s = ad if isinstance(ad, str) else fi(ad)
        s10_s = s10 if isinstance(s10, str) else fi(s10)
        s09_s = s09 if isinstance(s09, str) else fi(s09)
        rows.append([sec, item, rt, 2010, ad_s, s10_s, p10, str(hf), SRC, pdf, pr, st])
        rows.append([sec, item, rt, 2009, "", s09_s, p09, str(hf), SRC, pdf, pr, st])
    write_csv("fact_revenue_account_statement.csv", header, rows)


# ============================================================
# NOTA 5(a) HASIL detailed  -> fact_revenue.csv  (pdf48-49)
# ============================================================
def build_revenue():
    st = "Nota 5(a) Hasil Mengikut Penjenisan"
    header = ["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
              "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
              "sebenar_prior_rm", "pct_anggaran_prior", "source_file", "pdf_page",
              "printed_page", "statement"]
    # (level, cat1, item, pdf, aa, ad, seb, pct, sebprior, pctprior)
    d = [
        (3, "HASIL CUKAI", "Cukai Pendapatan", 48, 77639195000, 72024389000, 74450947406, "103.37", 74917451186, "98.99"),
        (3, "HASIL CUKAI", "Cukai Langsung yang Lain", 48, 3620728000, 4131659000, 4557623181, "110.31", 3457934046, "113.37"),
        (3, "HASIL CUKAI", "Duti Kastam - Eksport", 48, 1460124000, 2041477000, 1810153989, "88.67", 1152144382, "91.05"),
        (3, "HASIL CUKAI", "Duti Kastam - Import", 48, 1725478000, 2099179000, 1966286242, "93.67", 2114273126, "106.12"),
        (3, "HASIL CUKAI", "Duti Eksais", 48, 8770230000, 9420997000, 9349845826, "99.24", 8473710247, "101.93"),
        (3, "HASIL CUKAI", "Cukai Jualan atas Barang-barang Perkilangan Dalam Negeri", 48, 4891668000, 4852533000, 4886329398, "100.70", 5348019540, "100.56"),
        (3, "HASIL CUKAI", "Cukai Jualan atas Import", 48, 2886731000, 3388573000, 3284997419, "96.94", 3255198738, "103.72"),
        (3, "HASIL CUKAI", "Cukai Perkhidmatan", 48, 3960854000, 3964984000, 3925825907, "99.01", 3344125618, "100.31"),
        (3, "HASIL CUKAI", "Levi", 48, 156635000, 275000000, 440135686, "160.05", 437751883, "94.79"),
        (3, "HASIL CUKAI", "Duti Eksais Terhadap Barangan Import", 49, 1521236000, 2414025000, 2420388694, "100.26", 1594774130, "110.59"),
        (3, "HASIL CUKAI", "Pelbagai Cukai Tidak Langsung", 49, 2728933000, 2479254000, 2422652064, "97.72", 2409028115, "96.04"),
        (1, "HASIL CUKAI", "Jumlah Hasil Cukai", 49, 109361812000, 107092070000, 109515185813, "102.26", 106504411011, "100.00"),
        (3, "HASIL BUKAN CUKAI", "Lesen, Bayaran Pendaftaran dan Permit", 49, 9305236000, 10238632000, 10330656302, "100.90", 10686110292, "109.09"),
        (3, "HASIL BUKAN CUKAI", "Perkhidmatan dan Bayaran Perkhidmatan", 49, 916166000, 1196508000, 1121609498, "93.74", 949129664, "108.52"),
        (3, "HASIL BUKAN CUKAI", "Perolehan daripada Jualan Barang-barang", 49, 68817000, 602269000, 92307707, "15.33", 67799310, "104.71"),
        (3, "HASIL BUKAN CUKAI", "Sewaan", 49, 191716000, 196328000, 197308450, "100.50", 181179399, "98.43"),
        (3, "HASIL BUKAN CUKAI", "Faedah dan Perolehan daripada Pelaburan", 49, 32322084000, 39457691000, 34575536231, "87.63", 37393786263, "88.22"),
        (3, "HASIL BUKAN CUKAI", "Denda dan Hukuman", 49, 667162000, 898001000, 1100140888, "122.51", 689556855, "108.22"),
        (3, "HASIL BUKAN CUKAI", "Sumbangan dan Bayaran Ganti dari Luar Negeri dan Sumbangan Tempatan", 49, 2000000, 226002000, 317959382, "140.69", 3026565, "157.72"),
        (3, "HASIL BUKAN CUKAI", "Aktiviti Mencari Gali Minyak dan Gas", 49, 889245000, 1024860000, 1131916472, "110.45", 818650554, "96.39"),
        (1, "HASIL BUKAN CUKAI", "Jumlah Hasil Bukan Cukai", 49, 44362426000, 53840291000, 48867434930, "90.76", 50789238902, "92.69"),
        (3, "TERIMAAN BUKAN HASIL", "Pulangan Balik Perbelanjaan", 49, 508309000, 739313000, 763682026, "103.30", 542176617, "111.68"),
        (3, "TERIMAAN BUKAN HASIL", "Terimaan daripada Agensi-agensi Kerajaan", 49, 11906000, 35479000, 29324421, "82.65", 525386453, "4,620.41"),
        (1, "TERIMAAN BUKAN HASIL", "Jumlah Terimaan Bukan Hasil", 49, 520215000, 774792000, 793006447, "102.35", 1067563070, "214.87"),
        (3, "HASIL WILAYAH-WILAYAH PERSEKUTUAN", "Hasil Cukai Wilayah-Wilayah Persekutuan", 49, 249861000, 356036000, 398675390, "111.98", 210698612, "88.29"),
        (3, "HASIL WILAYAH-WILAYAH PERSEKUTUAN", "Hasil Bukan Cukai Wilayah-Wilayah Persekutuan", 49, 65926000, 68144000, 78659738, "115.43", 67392633, "107.03"),
        (1, "HASIL WILAYAH-WILAYAH PERSEKUTUAN", "Jumlah Hasil Wilayah-Wilayah Persekutuan", 49, 315787000, 424180000, 477335128, "112.53", 278091245, "92.21"),
        (0, "", "JUMLAH HASIL", 49, 154560240000, 162131333000, 159652962318, "98.47", 158639304228, "97.87"),
    ]
    rows = []
    for lvl, c1, item, pdf, aa, ad, seb, pct, sp, pp2 in d:
        _, pr = pp(pdf)
        rows.append([lvl, c1, "", item, 2010, ff(aa), ff(ad), ff(seb), pct, ff(sp), pp2,
                     SRC, pdf, pr, st])
    write_csv("fact_revenue.csv", header, rows)


# ============================================================
# NOTA 6 AKAUN PINJAMAN DISATUKAN -> fact_loan_account_statement.csv (pdf51)
# ============================================================
def build_loan():
    st = "Nota 6 Akaun Pinjaman Disatukan"
    pdf, pr = pp(51)
    header = ["group_bm", "sub_bm", "line_item_bm", "row_type", "year", "amount_rm",
              "source_file", "pdf_page", "printed_page", "statement"]
    # (group, sub, item, row_type, v2010, v2009)
    d = [
        ("PINJAMAN", "Dalam Negeri", "Baki pada 1 Januari", "detail", 8359953459, 43903430459),
        ("PINJAMAN", "Dalam Negeri", "Terimaan", "detail", 66835466667, 100119903344),
        ("PINJAMAN", "Dalam Negeri", "Bayaran", "detail", -30404584571, -43194308344),
        ("PINJAMAN", "Dalam Negeri", "Baki pada 31 Disember", "detail", 44790835555, 100829025459),
        ("PINJAMAN", "Luar Negeri", "Terimaan", "detail", 4047250000, 0),
        ("PINJAMAN", "Luar Negeri", "Bayaran", "detail", 0, -5837534800),
        ("PINJAMAN", "Luar Negeri", "Baki pada 31 Disember", "detail", 4047250000, -5837534800),
        ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Terimaan", "detail", 5900000000, 6600000000),
        ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Bayaran", "detail", -600000000, -1000000000),
        ("PINJAMAN", "Kumpulan Wang Pinjaman Perumahan", "Baki pada 31 Disember", "detail", 5300000000, 5600000000),
        ("PINJAMAN", "", "Jumlah Pinjaman pada 31 Disember", "group_total", 54138085555, 100591490659),
        ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Terimaan", "detail", 117087038, 74159605),
        ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Bayaran", "detail", -239356767, -354543416),
        ("BANTUAN LUAR NEGERI", "Pinjaman Multilateral", "Baki pada 31 Disember", "detail", -122269729, -280383811),
        ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Terimaan", "detail", 330740067, 376653422),
        ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Bayaran", "detail", -591991257, -544805182),
        ("BANTUAN LUAR NEGERI", "Pinjaman Bilateral", "Baki pada 31 Disember", "detail", -261251190, -168151760),
        ("BANTUAN LUAR NEGERI", "", "Jumlah Bantuan Luar Negeri pada 31 Disember", "group_total", -383520919, -448535571),
        ("JUMLAH", "", "JUMLAH PINJAMAN DAN BANTUAN LUAR NEGERI PADA 31 DISEMBER", "total", 53754564636, 100142955088),
        ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", "transfer", -22386019081, -86183001629),
        ("PINDAHAN KE", "", "Kumpulan Wang Pinjaman Perumahan", "transfer", -5300000000, -5600000000),
        ("BAKI", "", "BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER", "closing", 26068545555, 8359953459),
    ]
    rows = []
    for g, s, item, rt, v10, v09 in d:
        rows.append([g, s, item, rt, 2010, fi(v10), SRC, pdf, pr, st])
        rows.append([g, s, item, rt, 2009, fi(v09), SRC, pdf, pr, st])
    write_csv("fact_loan_account_statement.csv", header, rows)


# ============================================================
# NOTA 7 AKAUN AMANAH - top roll-forward -> fact_trust_accounts.csv (pdf52)
# ============================================================
# top table: (baki_awal, debit, kredit, baki_akhir) for 2010
TRUST_TOP = [
    # parent_group, account, ba, dr, kr, bk
    ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pembangunan", -24382711582, 53833730847, 32720185769, -45496256660),
    ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pinjaman Perumahan", 1757692388, 9021640246, 10477407817, 3213459959),
    ("KUMPULAN WANG AMANAH KERAJAAN", "Pelbagai Kumpulan Wang Amanah Kerajaan", 28541135720, 264260456727, 265639515063, 29920194056),
    ("", "KUMPULAN WANG AMANAH KERAJAAN", 5916116526, 327115827820, 308837108649, -12362602645),  # subtotal
    ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Khas", 546890042, 508385388, 543584411, 582089065),
    ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Am", 8856261454, 8226694597, 6509974249, 7139541106),
    ("", "KUMPULAN WANG AMANAH AWAM", 9403151496, 8735079985, 7053558660, 7721630171),  # subtotal
    ("AKAUN DEPOSIT", "Deposit Am", 7477117221, 1842399872, 2623962863, 8258680212),
    ("AKAUN DEPOSIT", "Deposit Pelarasan", 516077511, 2535502226, 2386563927, 367139212),
    ("", "AKAUN DEPOSIT", 7993194732, 4377902098, 5010526790, 8625819424),  # subtotal
    ("JUMLAH", "AKAUN AMANAH DISATUKAN", 23312462754, 340228809903, 320901194099, 3984846950),  # total
]


def build_trust_accounts():
    st = "Nota 7 Akaun Amanah Disatukan"
    pdf, pr = pp(52)
    header = ["parent_group_bm", "account_bm", "year", "baki_awal_rm", "debit_rm",
              "kredit_rm", "baki_akhir_rm", "source_file", "pdf_page", "printed_page", "statement"]
    rows = []
    for pg, acc, ba, dr, kr, bk in TRUST_TOP:
        rows.append([pg, acc, 2010, ff(ba), ff(dr), ff(kr), ff(bk), SRC, pdf, pr, st])
    write_csv("fact_trust_accounts.csv", header, rows)


# ============================================================
# NOTA 7 - per-fund detail -> fact_trust_fund_detail.csv (pdf52-56)
# ============================================================
def build_trust_fund_detail():
    st = "Nota 7 Akaun Amanah Disatukan"
    header = ["fund_group_bm", "fund_bm", "section_bm", "line_item_bm", "year",
              "amount_rm", "row_type", "has_footnote", "source_file", "pdf_page",
              "printed_page", "statement"]
    rows = []

    def add(fg, fund, sec, item, yr, amt, rt, pdf):
        _, pr = pp(pdf)
        rows.append([fg, fund, sec, item, yr, fi(amt), rt, "False", SRC, pdf, pr, st])

    # --- PART A: Penyata Ringkasan (year 2010 only) from top table, pdf52 ---
    ring = [
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pembangunan", "detail"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Kumpulan Wang Pinjaman Perumahan", "detail"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Pelbagai Kumpulan Wang Amanah Kerajaan", "detail"),
        ("KUMPULAN WANG AMANAH KERAJAAN", "Jumlah Kumpulan Wang Amanah Kerajaan", "subtotal"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Khas", "detail"),
        ("KUMPULAN WANG AMANAH AWAM", "Kumpulan Wang Amanah Am", "detail"),
        ("KUMPULAN WANG AMANAH AWAM", "Jumlah Kumpulan Wang Amanah Awam", "subtotal"),
        ("AKAUN DEPOSIT", "Deposit Am", "detail"),
        ("AKAUN DEPOSIT", "Deposit Pelarasan", "detail"),
        ("AKAUN DEPOSIT", "Jumlah Akaun Deposit", "subtotal"),
        ("JUMLAH AKAUN AMANAH DISATUKAN", "JUMLAH AKAUN AMANAH DISATUKAN", "total"),
    ]
    for (fg, fund, rt), (_, _, ba, dr, kr, bk) in zip(ring, TRUST_TOP):
        add(fg, fund, "Penyata Ringkasan", "Baki pada 1 Januari", 2010, ba, rt, 52)
        add(fg, fund, "Penyata Ringkasan", "Debit", 2010, dr, rt, 52)
        add(fg, fund, "Penyata Ringkasan", "Kredit", 2010, kr, rt, 52)
        add(fg, fund, "Penyata Ringkasan", "Baki pada 31 Disember", 2010, bk, rt, 52)

    KG = "KUMPULAN WANG AMANAH KERAJAAN"
    # --- PART B1: Kumpulan Wang Pembangunan roll-forward (pdf53), both years ---
    KP = "Kumpulan Wang Pembangunan"
    b1 = [
        ("", "BAKI PADA 1 JANUARI", "opening", -24382711582, -63144392127),
        ("TERIMAAN", "Pindahan Dari Akaun Hasil Disatukan", "detail", 8020353053, 1572344908),
        ("TERIMAAN", "Pindahan Dari Akaun Pinjaman Disatukan", "detail", 22386019081, 86183001629),
        ("TERIMAAN", "Terimaan Balik Pinjaman", "detail", 1495525781, 518787580),
        ("TERIMAAN", "Jualan Aset Modal", "detail", 73318, 1340),
        ("TERIMAAN", "Pelbagai Terimaan", "detail", 30874234, 2900658),
        ("TERIMAAN", "Pelarasan", "detail", -254760325, 0),
        ("TERIMAAN", "Jumlah Terimaan", "subtotal", 31678085142, 88277036115),
        ("BAYARAN / Perbelanjaan Pembangunan", "Langsung", "detail", -49096365990, -45294239672),
        ("BAYARAN / Perbelanjaan Pembangunan", "Pinjaman", "detail", -3695264230, -4221115898),
        ("BAYARAN", "Jumlah Bayaran", "subtotal", -52791630220, -49515355570),
        ("", "Lebihan/(Kurangan) Bagi Tahun", "net", -21113545078, 38761680545),
        ("", "BAKI KUMPULAN WANG PEMBANGUNAN PADA 31 DISEMBER", "closing", -45496256660, -24382711582),
    ]
    for sec, item, rt, v10, v09 in b1:
        add(KG, KP, sec, item, 2010, v10, rt, 53)
        add(KG, KP, sec, item, 2009, v09, rt, 53)

    # --- PART B2: Kumpulan Wang Pinjaman Perumahan roll-forward (pdf53-54) ---
    KR = "Kumpulan Wang Pinjaman Perumahan"
    # (section, item, row_type, v2010, v2009, pdf)
    b2 = [
        ("", "BAKI PADA 1 JANUARI", "opening", 1757692388, 2455881266, 53),
        ("TERIMAAN / Pinjaman Perseorangan", "Bayaran Balik Pinjaman Perseorangan", "detail", 910251578, 678442055, 53),
        ("TERIMAAN / Pinjaman Perseorangan", "Hasil Pensekuritian", "detail", 7104, 4235741322, 53),
        ("TERIMAAN / Pembiayaan", "Pelbagai Pembiayaan", "detail", 5900000000, 6600000000, 53),
        ("TERIMAAN / Pendapatan Faedah", "Bayaran Balik Faedah Pinjaman Perseorangan", "detail", 794010397, 646796364, 53),
        ("TERIMAAN / Akaun Pensekuritian", "Kutipan Bayaran Balik Akaun Pensekuritian", "detail", 2538563052, 2463873810, 53),
        ("TERIMAAN / Akaun Pensekuritian", "Peruntukan Diskaun Pensekuritian", "detail", 348309662, 311525941, 53),
        ("TERIMAAN", "Pelbagai", "detail", 11252845, 13342477, 53),
        ("TERIMAAN", "Jumlah Terimaan", "subtotal", 10502394638, 14949721969, 53),
        ("BAYARAN / Pinjaman Perseorangan", "Pengeluaran Pinjaman Perseorangan", "detail", -5925636830, -6592873669, 54),
        ("BAYARAN / Pembiayaan", "Bayaran Balik Pelbagai Pembiayaan", "detail", -600000000, -1000000000, 54),
        ("BAYARAN / Akaun Pensekuritian", "Serahan Kutipan Akaun Pensekuritian", "detail", -2493063000, -2280548836, 54),
        ("BAYARAN / Akaun Pensekuritian", "Bayaran Lain Akaun Pensekuritian", "detail", -27927237, -24488342, 54),
        ("BAYARAN", "Jumlah Bayaran", "subtotal", -9046627067, -9897910847, 54),
        ("PINDAHAN DARI / (KE)", "Akaun Amanah Pensekuritian", "transfer", 0, -5750000000, 54),
        ("", "BAKI KUMPULAN WANG PINJAMAN PERUMAHAN PADA 31 DISEMBER", "closing", 3213459959, 1757692388, 54),
    ]
    for sec, item, rt, v10, v09, pdf in b2:
        add(KG, KR, sec, item, 2010, v10, rt, pdf)
        add(KG, KR, sec, item, 2009, v09, rt, pdf)

    # --- PART C: Pelbagai Kumpulan Wang Amanah Kerajaan balance detail (pdf54-55) ---
    PK = "Pelbagai Kumpulan Wang Amanah Kerajaan"
    # (section, item, row_type, v2010, v2009, pdf)
    c = [
        ("AKAUN PENYELESAIAN", "Akaun Semasa Antara Pentadbiran", "detail", 17601444, 17413469, 54),
        ("AKAUN PENYELESAIAN", "Akaun Penyelesaian Utama Perbendaharaan", "detail", 17133244231, 13386481328, 54),
        ("AKAUN PENYELESAIAN", "Akaun Penyelesaian Jabatan Mengakaun Sendiri", "detail", 100000000, 100000000, 54),
        ("AKAUN PENYELESAIAN", "Jumlah Akaun Penyelesaian", "subtotal", 17250845675, 13503894797, 54),
        ("AKAUN PERNIAGAAN", "Stor dan Woksyop Belum Diuntukkan", "detail", 81310524, 88249960, 54),
        ("AKAUN PERNIAGAAN", "Jumlah Akaun Perniagaan", "subtotal", 81310524, 88249960, 54),
        ("AKAUN PINJAMAN", "Kontraktor", "detail", 8517709, 5490211, 54),
        ("AKAUN PINJAMAN", "Kredit Kerjasama", "detail", 15037189, 15037189, 54),
        ("AKAUN PINJAMAN", "Modal Pusingan Jabatan Pembangunan Koperasi", "detail", 163492167, 123390051, 54),
        ("AKAUN PINJAMAN", "Pembangunan Ekonomi Belia", "detail", 1416913, 5365873, 54),
        ("AKAUN PINJAMAN", "Pembiayaan Komputer Anggota Perkhidmatan Awam", "detail", 101659694, 95126007, 54),
        ("AKAUN PINJAMAN", "Pendahuluan Diri (Pegawai Awam)", "detail", 88197090, 41699402, 54),
        ("AKAUN PINJAMAN", "Pendahuluan Pelbagai", "detail", 55839349, 56249941, 54),
        ("AKAUN PINJAMAN", "Pendahuluan Peti Sejuk Sarawak", "detail", 616613, 527748, 54),
        ("AKAUN PINJAMAN", "Pendahuluan Untuk Negeri", "detail", 197941807, 166772028, 54),
        ("AKAUN PINJAMAN", "Pinjaman Diraja", "detail", 2500000, 2500000, 54),
        ("AKAUN PINJAMAN", "Pinjaman Kenderaan", "detail", 664323196, 657069479, 54),
        ("AKAUN PINJAMAN", "Pinjaman Kepada Badan Berkanun dan Badan Lain", "detail", 3150036049, 2938816429, 54),
        ("AKAUN PINJAMAN", "Pinjaman Perumahan kepada Golongan Pendapatan Rendah", "detail", 31788407, 26886967, 54),
        ("AKAUN PINJAMAN", "Rakyat Malaysia di Luar Negeri", "detail", 993089, 966796, 54),
        ("AKAUN PINJAMAN", "Tabung Pusingan Pinjaman Pelajaran Persekutuan", "detail", 356457902, 305792982, 54),
        ("AKAUN PINJAMAN", "Jumlah Akaun Pinjaman", "subtotal", 4838817174, 4441691103, 54),
        ("KUMPULAN WANG LUAR JANGKA", "Kumpulan Wang Luar Jangka", "detail", 79147700, 1500000000, 54),
        ("KUMPULAN WANG LUAR JANGKA", "Jumlah Kumpulan Wang Luar Jangka", "subtotal", 79147700, 1500000000, 54),
        ("PELBAGAI KUMPULAN WANG", "Amanah Negara", "detail", 4362655239, 4076555913, 55),
        ("PELBAGAI KUMPULAN WANG", "Amanah Pelajar Miskin", "detail", 443757048, 120254403, 55),
        ("PELBAGAI KUMPULAN WANG", "Amanah Sukan Negara", "detail", 11766764, 13592175, 55),
        ("PELBAGAI KUMPULAN WANG", "Bantuan Bencana Negara", "detail", 143179718, 151554720, 55),
        ("PELBAGAI KUMPULAN WANG", "Bantuan Mangsa Serangan Binatang Buas", "detail", 587800, 716200, 55),
        ("PELBAGAI KUMPULAN WANG", "Cadangan Untuk Negeri", "detail", 226624324, 239158461, 55),
        ("PELBAGAI KUMPULAN WANG", "Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri", "detail", 3781106, 3730976, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia", "detail", 56359475, 13749475, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara", "detail", 414329, 557713, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Pengangkutan Awam", "detail", 753645090, 653531006, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras", "detail", 43876236, 6051092, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia", "detail", 1773671, 1777571, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Projek Pelantar Benua Malaysia", "detail", 1398810, 0, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia", "detail", 14880792, 0, 55),
        ("PELBAGAI KUMPULAN WANG", "Kumpulan Wang Amanah Taman Laut dan Rizab Laut", "detail", 2741782, 3651065, 55),
        ("PELBAGAI KUMPULAN WANG", "Kursi Pengajian Melayu Leiden University, The Netherlands", "detail", 794, 1206, 55),
        ("PELBAGAI KUMPULAN WANG", "Majlis Penyelidikan dan Kemajuan Sains Negara (MPKSN)", "detail", 3089995, 3219956, 55),
        ("PELBAGAI KUMPULAN WANG", "Pelarasan Industri", "detail", 0, 216837310, 55),
        ("PELBAGAI KUMPULAN WANG", "Penjelas Hutang", "detail", 200000000, 200000000, 55),
        ("PELBAGAI KUMPULAN WANG", "Perkhidmatan Kemasyarakatan dan Kebajikan", "detail", 75395808, 80338119, 55),
        ("PELBAGAI KUMPULAN WANG", "Perpustakaan Negara", "detail", 1306444, 1374559, 55),
        ("PELBAGAI KUMPULAN WANG", "Program Perumahan Rakyat Dimiliki", "detail", 658582359, 486327183, 55),
        ("PELBAGAI KUMPULAN WANG", "Skim Biasiswa Sukan Persekutuan", "detail", 1265001, 121625, 55),
        ("PELBAGAI KUMPULAN WANG", "Tabung Bayaran Balik Cukai", "detail", 595253542, 2699447357, 55),
        ("PELBAGAI KUMPULAN WANG", "Tabung Bantuan Perubatan (TBP)", "detail", 24498178, 34464665, 55),
        ("PELBAGAI KUMPULAN WANG", "Tabung Inovasi Negara Berhad (KWATIN)", "detail", 43040000, 0, 55),
        ("PELBAGAI KUMPULAN WANG", "Tabung Pustaka Peringatan P. Ramlee", "detail", 198681, 287110, 55),
        ("PELBAGAI KUMPULAN WANG", "Jumlah Pelbagai Kumpulan Wang", "subtotal", 7670072984, 9007299860, 55),
        ("", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", "total", 29920194056, 28541135720, 55),
    ]
    for sec, item, rt, v10, v09, pdf in c:
        add(KG, PK, sec, item, 2010, v10, rt, pdf)
        add(KG, PK, sec, item, 2009, v09, rt, pdf)

    # --- PART D: Kumpulan Wang Amanah Awam (pdf55) ---
    AW = "KUMPULAN WANG AMANAH AWAM"
    dd = [
        ("AMANAH KHAS", "Faedah atas pelaburan Untuk Deposit Mahkamah", "detail", 214516134, 201110761),
        ("AMANAH KHAS", "Kumpulan Wang Dius Api", "detail", 198346701, 168306031),
        ("AMANAH KHAS", "Akaun Amanah Khas Warisan", "detail", 43776082, 56935239),
        ("AMANAH KHAS", "Pelbagai Amanah Khas", "detail", 125450148, 120538011),
        ("AMANAH KHAS", "Jumlah Amanah Khas", "subtotal", 582089065, 546890042),
        ("AMANAH AM", "Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)", "detail", 4437410176, 6186947928),
        ("AMANAH AM", "Akaun Amanah Membangun/Menaiktaraf Sistem Pembentungan untuk Pembangunan Baru", "detail", 725063371, 668266185),
        ("AMANAH AM", "Akaun Amanah Dana Khas", "detail", 452213814, 369445339),
        ("AMANAH AM", "Akaun Amanah Industri Bekalan Elektrik", "detail", 442029026, 416032487),
        ("AMANAH AM", "Pelbagai Amanah Am", "detail", 1082824719, 1215569515),
        ("AMANAH AM", "Jumlah Amanah Am", "subtotal", 7139541106, 8856261454),
        ("", "JUMLAH KUMPULAN WANG AMANAH AWAM", "total", 7721630171, 9403151496),
    ]
    for sec, item, rt, v10, v09 in dd:
        add(AW, "", sec, item, 2010, v10, rt, 55)
        add(AW, "", sec, item, 2009, v09, rt, 55)

    # --- PART E: Akaun Deposit (pdf56) ---
    AD = "AKAUN DEPOSIT"
    e = [
        ("DEPOSIT AM", "Kawalan Wang Tak Dituntut", "detail", 2131449146, 1787873585),
        ("DEPOSIT AM", "Deposit Wang Tak Dituntut", "detail", 1751022061, 1805011713),
        ("DEPOSIT AM", "Wang Jaminan Perlaksanaan", "detail", 1711333693, 1504352517),
        ("DEPOSIT AM", "Harta Kebangkrapan", "detail", 848872213, 727947381),
        ("DEPOSIT AM", "Deposit Mahkamah Tinggi", "detail", 750171139, 700890997),
        ("DEPOSIT AM", "Pelbagai Deposit Am", "detail", 1065831960, 951041028),
        ("DEPOSIT AM", "Jumlah Deposit Am", "subtotal", 8258680212, 7477117221),
        ("DEPOSIT PELARASAN", "Deposit Pelarasan Cek Terbatal", "detail", 127593518, 126934123),
        ("DEPOSIT PELARASAN", "Terimaan Yang Tidak Diperuntukkan", "detail", 101101437, 135162881),
        ("DEPOSIT PELARASAN", "Pembatalan Bayaran EFT", "detail", 119830425, 240057919),
        ("DEPOSIT PELARASAN", "Pelbagai Deposit Pelarasan", "detail", 18613832, 13922588),
        ("DEPOSIT PELARASAN", "Jumlah Deposit Pelarasan", "subtotal", 367139212, 516077511),
        ("", "JUMLAH AKAUN DEPOSIT", "total", 8625819424, 7993194732),
    ]
    for sec, item, rt, v10, v09 in e:
        add(AD, "", sec, item, 2010, v10, rt, 56)
        add(AD, "", sec, item, 2009, v09, rt, 56)

    write_csv("fact_trust_fund_detail.csv", header, rows)


# ============================================================
# NOTA 8 MEMORANDUM ASET -> fact_memo_assets_detail.csv (pdf56-57)
# ============================================================
def build_memo_assets():
    st = "Nota 8 Memorandum Aset"
    header = ["section_bm", "line_item_bm", "year", "amount_rm", "row_type",
              "has_footnote", "source_file", "pdf_page", "printed_page", "statement"]
    # (section, item, row_type, v2010, v2009, pdf)
    d = [
        ("Pinjaman Boleh Dituntut", "Kerajaan Negeri", "detail", 18170277816, 18482439461, 56),
        ("Pinjaman Boleh Dituntut", "Pihak Berkuasa Tempatan", "detail", 506706592, 513384889, 56),
        ("Pinjaman Boleh Dituntut", "Badan Berkanun", "detail", 10415078766, 7787066246, 56),
        ("Pinjaman Boleh Dituntut", "Koperasi", "detail", 195725480, 193033922, 56),
        ("Pinjaman Boleh Dituntut", "Syarikat", "detail", 24227828427, 22880161118, 56),
        ("Pinjaman Boleh Dituntut", "Perseorangan", "detail", 26160214194, 21151026643, 56),
        ("Pinjaman Boleh Dituntut", "Pelbagai", "detail", 2643256403, 2375632840, 56),
        ("Pinjaman Boleh Dituntut", "JUMLAH PINJAMAN BOLEH DITUNTUT", "total", 82319087678, 73382745119, 56),
        ("Pelaburan", "Syarikat", "detail", 26465720953, 26493986978, 57),
        ("Pelaburan", "Badan Berkanun", "detail", 1218852876, 1218852876, 57),
        ("Pelaburan", "Agensi Antarabangsa", "detail", 38574229, 38574229, 57),
        ("Pelaburan", "JUMLAH PELABURAN", "total", 27723148058, 27751414083, 57),
    ]
    rows = []
    for sec, item, rt, v10, v09, pdf in d:
        _, pr = pp(pdf)
        rows.append([sec, item, 2010, fi(v10), rt, "False", SRC, pdf, pr, st])
        rows.append([sec, item, 2009, fi(v09), rt, "False", SRC, pdf, pr, st])
    write_csv("fact_memo_assets_detail.csv", header, rows)


# ============================================================
# NOTA 9(a) HUTANG AWAM -> fact_debt.csv (pdf57-58)
# ============================================================
def build_debt():
    st = "Nota 9 Memorandum Liabiliti"
    header = ["group_bm", "item_bm", "kind", "year", "amount_rm", "source_file",
              "pdf_page", "printed_page", "statement"]
    # (group, item, kind, v2010, v2009, pdf)
    d = [
        ("Pinjaman Dalam Negeri", "Bil Perbendaharaan", "instrument", 4320000000, 4320000000, 57),
        ("Pinjaman Dalam Negeri", "Terbitan Pelaburan Kerajaan", "instrument", 81500000000, 66000000000, 57),
        ("Pinjaman Dalam Negeri", "Sekuriti Kerajaan Malaysia", "instrument", 260992662000, 242270372000, 57),
        ("Pinjaman Dalam Negeri", "Sukuk", "instrument", 7143324000, 4909588300, 57),
        ("Pinjaman Dalam Negeri", "Dalam Negeri", "subtotal", 353955986000, 317499960300, 57),
        ("Pinjaman Luar Negeri", "Pinjaman Pasaran", "instrument", 9355200000, 6049225000, 57),
        ("Kumpulan Wang Pinjaman Perumahan", "Pembiayaan Kumpulan Wang Pinjaman Perumahan", "instrument", 36400000000, 31100000000, 57),
        ("JUMLAH", "Jumlah Pinjaman", "subtotal", 399711186000, 354649185300, 57),
        ("Bantuan Luar Negeri", "Pinjaman Multilateral", "instrument", 786984196, 1008988053, 57),
        ("Bantuan Luar Negeri", "Pinjaman Bilateral", "instrument", 6603065743, 6727997757, 57),
        ("JUMLAH", "Jumlah Bantuan Luar Negeri", "subtotal", 7390049939, 7736985810, 57),
        ("JUMLAH", "JUMLAH HUTANG AWAM", "total", 407101235939, 362386171110, 57),
        ("Pelbagai Liabiliti", "PELBAGAI LIABILITI", "misc_total", 206605049, 173364115, 58),
    ]
    rows = []
    for g, item, kind, v10, v09, pdf in d:
        _, pr = pp(pdf)
        rows.append([g, item, kind, 2010, ff(v10), SRC, pdf, pr, st])
        rows.append([g, item, kind, 2009, ff(v09), SRC, pdf, pr, st])
    write_csv("fact_debt.csv", header, rows)


# ============================================================
# NOTA 9(b) PELBAGAI LIABILITI -> fact_commitment_detail.csv (pdf58)
# ============================================================
def build_commitment():
    st = "Nota 9 Memorandum Liabiliti"
    pdf, pr = pp(58)
    header = ["parent_bm", "item_bm", "year", "amount_rm", "row_type", "has_footnote",
              "source_file", "pdf_page", "printed_page", "statement"]
    P = "PELBAGAI LIABILITI"
    d = [
        ("Nota Kena Bayar", "detail", 170518025, 133768024),
        ("Sekuriti Tak Dituntut", "detail", 21855998, 21843596),
        ("Akaun Depositori Pusat", "detail", 14231026, 17752495),
        ("JUMLAH PELBAGAI LIABILITI", "total", 206605049, 173364115),
    ]
    rows = []
    for item, rt, v10, v09 in d:
        rows.append([P, item, 2010, ff(v10), rt, "False", SRC, pdf, pr, st])
        rows.append([P, item, 2009, ff(v09), rt, "False", SRC, pdf, pr, st])
    write_csv("fact_commitment_detail.csv", header, rows)


# ============================================================
# fact_other_notes.csv  - narrative quantified facts (various pages)
# ============================================================
def build_other_notes():
    header = ["nota", "line_item_bm", "year", "amount_rm", "row_type", "has_footnote",
              "source_file", "pdf_page", "printed_page", "statement"]
    # (nota, line_item, year, amount, pdf, statement)
    d = [
        ("5", "Baki terkumpul Akaun Hasil Disatukan sebelum tahun 1996 (tidak dipindah ke Kumpulan Wang Pembangunan)", 2010, 11863127086, 48, "Nota 5 Akaun Hasil Disatukan"),
        ("6", "Baki Pinjaman dan Bantuan Luar Negeri yang tidak dipindah ke Kumpulan Wang Pembangunan/Perumahan pada 31 Disember", 2010, 26068545555, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Komponen baki tidak dipindah: Bil Perbendaharaan", 2010, 3425221555, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Komponen baki tidak dipindah: Terbitan Pelaburan Kerajaan", 2010, 15500000000, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Komponen baki tidak dipindah: Sukuk", 2010, 7143324000, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Bantuan Luar Negeri Yang Belum Diterima pada 31 Disember", 2010, 2906782557, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Bantuan Luar Negeri Yang Belum Diterima pada 31 Disember", 2009, 3158389235, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Pinjaman dan Bantuan Luar Negeri di Penyata Prestasi Kewangan (terimaan bersih tahun semasa)", 2010, 40094611177, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("6", "Bayaran faedah hutang negara dikenakan kepada Perbelanjaan bagi Maksud Tanggungan T13", 2010, 15621082609, 51, "Nota 6 Akaun Pinjaman Disatukan"),
        ("7", "Akaun Penyelesaian Utama Perbendaharaan: debit tidak melibatkan terimaan atau bayaran sebenar", 2010, 243676282038, 52, "Nota 7 Akaun Amanah Disatukan"),
        ("7", "Akaun Penyelesaian Utama Perbendaharaan: kredit tidak melibatkan terimaan atau bayaran sebenar", 2010, 247423044940, 52, "Nota 7 Akaun Amanah Disatukan"),
        ("7", "Bayaran lain di Penyata Penerimaan dan Pembayaran Wang Tunai (baki bersih Akaun Amanah)", 2010, 2019293299, 52, "Nota 7 Akaun Amanah Disatukan"),
        ("7", "Kurangan pembiayaan di Penyata Prestasi Kewangan dibiayai oleh perubahan dalam Tunai, Pelaburan dan Amanah", 2010, 3150192657, 52, "Nota 7 Akaun Amanah Disatukan"),
        ("7(a)(i)", "Perbezaan Terimaan Balik Pinjaman Kumpulan Wang Pembangunan disebabkan urus niaga bukan tunai (penukaran pinjaman kepada ekuiti)", 2010, 710527621, 52, "Nota 7(a)(i) Kumpulan Wang Pembangunan"),
        ("7(a)(i)", "Pelarasan urus niaga tahun-tahun lepas (komponen perbezaan Terimaan Balik Pinjaman KWP)", 2010, 254760325, 52, "Nota 7(a)(i) Kumpulan Wang Pembangunan"),
        ("7(b)", "Terimaan Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)", 2010, 3262830183, 55, "Nota 7(b) Kumpulan Wang Amanah Awam"),
        ("7(b)", "Bayaran Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)", 2010, 5012367936, 55, "Nota 7(b) Kumpulan Wang Amanah Awam"),
        ("10(a)", "Pinjaman badan berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]", 2010, 96906893915, 58, "Nota 10 Liabiliti Luar Jangka"),
        ("10(b)", "Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji", 2010, 430984840697, 58, "Nota 10 Liabiliti Luar Jangka"),
        ("10(c)", "Third Party War Risk Liability dengan Malaysia Airports Holdings Berhad mengikut perjanjian indemniti", 2010, 475000000, 58, "Nota 10 Liabiliti Luar Jangka"),
        ("11", "Akaun Belum Terima berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)", 2010, 20373610990, 58, "Nota 11 Akaun Belum Terima"),
        ("12", "Wang pendahuluan kepada kontraktor yang belum diimbuh balik berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)", 2010, 1283921861, 58, "Nota 12 Wang Pendahuluan Kepada Kontraktor"),
    ]
    rows = []
    for nota, item, yr, amt, pdf, stt in d:
        _, pr = pp(pdf)
        rows.append([nota, item, yr, ff(amt), "narrative", "False", SRC, pdf, pr, stt])
    write_csv("fact_other_notes.csv", header, rows)


if __name__ == "__main__":
    build_cash()
    build_investment()
    build_revenue_account_statement()
    build_revenue()
    build_loan()
    build_trust_accounts()
    build_trust_fund_detail()
    build_memo_assets()
    build_debt()
    build_commitment()
    build_other_notes()
    print("DONE")
