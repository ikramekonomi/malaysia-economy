#!/usr/bin/env python3
"""Programmatic validation for the 2014 warehouse: extracted line items must
reproduce printed totals. Never corrects — only reports PASS/FAIL with amounts.
All reference figures are typed from the 2014 volume's own printed statements."""
import os
import csv
from collections import defaultdict

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2014")
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2014 volume) ----
# Penyata Kedudukan Kewangan pdf 58
WANG_AWAM = {2014: 40_841_339_321, 2013: 49_083_585_341}
# Penyata Prestasi Kewangan pdf 61
HASIL = {2014: 220_625_673_356, 2013: 213_370_213_558}
OPEX_PRESTASI = {2014: 219_589_142_572, 2013: 211_270_336_793}
DEVEX = {2014: 39_503_487_396, 2013: 42_209_801_384}
KURANGAN = {2014: -38_466_956_612, 2013: -40_109_924_619}
# Cash statement pdf 59-60
JUM_TERIMAAN = {2014: 330_010_464_477, 2013: 328_282_501_320}
JUM_BAYARAN = {2014: 337_634_832_390, 2013: 332_587_287_519}
TUNAI_AKHIR = {2014: 17_426_671_072, 2013: 25_051_038_985}
# printed cash category totals (typed from pdf 59-60)
CASH_CAT = {
    ("TERIMAAN", "Hasil"): {2014: 219_075_020_760, 2013: 209_152_274_939},
    ("TERIMAAN", "Pinjaman"): {2014: 108_809_141_548, 2013: 111_357_188_482},
    ("TERIMAAN", "Bantuan Luar Negeri"): {2014: 249_284_105, 2013: 412_652_196},
    ("TERIMAAN", "Terimaan Modal"): {2014: 1_712_598_183, 2013: 2_157_029_761},
    ("TERIMAAN", "Terimaan Amanah"): {2014: 164_419_881, 2013: 5_203_355_942},
    ("BAYARAN", "Perbelanjaan Mengurus"): {2014: 216_490_532_784, 2013: 207_752_597_154},
    ("BAYARAN", "Perbelanjaan Pembangunan"): {2014: 39_468_595_127, 2013: 42_209_801_384},
    ("BAYARAN", "Pinjaman"): {2014: 65_861_587_665, 2013: 73_030_098_558},
    ("BAYARAN", "Bantuan Luar Negeri"): {2014: 625_495_418, 2013: 621_022_819},
    ("BAYARAN", "Perbelanjaan Amanah"): {2014: 15_188_621_396, 2013: 8_973_767_604},
}
# Nota 5(b) pdf 67
TANGGUNGAN = 44_335_538_291
BEKALAN = 176_290_135_065
OPEX_NOTA_TOTAL = 220_625_673_356  # incl. transfer to KWP (inside B.12)
N_MAKSUD = 49
# Nota 9 pdf 74
HUTANG = {2014: 582_828_241_281, 2013: 539_857_759_215}
PINJ_DN = {2014: 519_452_319_000, 2013: 481_895_000_000}   # excl. KWPP financing
KWPP_SUB = {2014: 46_600_000_000, 2013: 41_200_000_000}
# Nota 7 pdf 69
AMANAH_AKHIR = {2014: -10_613_907_864, 2013: 10_840_100_391}
# Lampiran 1 grand total (sen precision, pdf 243)
OPEX_L1 = 220_625_673_355.87
# Lampiran 2 grand total (sen precision, pdf 271-272)
DEVEX_L2 = 39_503_487_395.98
N_MINISTRIES_L2 = 26

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2014, 2013):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM"
                and not r["line_item_bm"].startswith("JUMLAH") and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN"
             and not r["line_item_bm"].startswith("JUMLAH") and int(r["year"]) == yr)
    check(f"pos: Wang Awam items {yr} = printed (unlabelled) total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan items {yr} = printed (unlabelled) total", kw, WANG_AWAM[yr])
    jwa = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "JUMLAH WANG AWAM" and int(r["year"]) == yr)
    jkw = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "JUMLAH KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: captured JUMLAH WANG AWAM row {yr}", jwa, WANG_AWAM[yr])
    check(f"pos: captured JUMLAH KW DISATUKAN row {yr}", jkw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2014, 2013):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex=kurangan {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")] - g[("devex", yr, "sebenar")],
          KURANGAN[yr])
    check(f"perf: pembiayaan = kurangan {yr}", g[("total_financing", yr, "sebenar")], -KURANGAN[yr])
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components = JUMLAH PEMBIAYAAN {yr}", fin, g[("total_financing", yr, "sebenar")])
check("perf: anggaran identity hasil-opex = lebihan 2014",
      g[("revenue", 2014, "anggaran")] - g[("opex", 2014, "anggaran")], g[("current_balance", 2014, "anggaran")])
check("perf: anggaran identity lebihan-devex = kurangan 2014",
      g[("current_balance", 2014, "anggaran")] - g[("devex", 2014, "anggaran")],
      g[("overall_deficit", 2014, "anggaran")])

# ---- 3. revenue (Nota 5(a)) ----
rv = load("fact_revenue.csv")
cols = ["anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "sebenar_prior_rm"]
for col in cols:
    total = next(F(r, col) for r in rv if r["level"] == "0")
    l1sum = sum(F(r, col) for r in rv if r["level"] == "1")
    check(f"rev[{col}]: sum(L1) = JUMLAH HASIL", l1sum, total)
    for l1 in ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]:
        l1v = next(F(r, col) for r in rv if r["level"] == "1" and r["item_bm"] == l1)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l1_bm"] == l1)
        check(f"rev[{col}]: sum(items) = {l1}", l3, l1v)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2014])
check("rev: HASIL sebenar prior = perf Hasil 2013",
      next(F(r, "sebenar_prior_rm") for r in rv if r["level"] == "0"), HASIL[2013])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Jumlah Perbelanjaan Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Jumlah Perbelanjaan Bekalan", b, BEKALAN)
check("opex: T+B = printed JUMLAH PERBELANJAAN MENGURUS (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)
for col, want_t, want_b in [("anggaran_asal_rm", 42_843_291_000, 174_807_709_000),
                            ("anggaran_dipinda_rm", 45_091_880_340, 176_989_391_630)]:
    check(f"opex[{col}]: sum(T.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("T.")), want_t)
    check(f"opex[{col}]: sum(B.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("B.")), want_b)
check("opex: anggaran asal grand = printed 217,651,000,000",
      sum(F(r, "anggaran_asal_rm") for r in ox), 217_651_000_000)
check("opex: anggaran dipinda grand = printed 222,081,271,970 (= prestasi anggaran)",
      sum(F(r, "anggaran_dipinda_rm") for r in ox), 222_081_271_970)

# ---- 5. devex by maksud (RMKe-10 year 4) ----
dx = load("fact_devex_maksud.csv")
mins = [r for r in dx if r["maksud_code"] != "TOTAL"]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm",
            "terkumpul_rmke10_prior_rm", "terkumpul_rmke10_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col), tol=0.02)
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2014], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm")
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)
    # RMKe-10 year 4: cumulative to 31.12.2014 = cumulative to 31.12.2013 + 2014 actual
    check(f"devex row: terkumpul RMKe-10 = prior + sebenar 2014 [{r['maksud_code']}]",
          F(r, "terkumpul_rmke10_prior_rm") + F(r, "sebenar_jumlah_rm"),
          F(r, "terkumpul_rmke10_rm"), tol=0.011)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
is_item = lambda r: not r["item_bm"].startswith("Jumlah ") and r["flow"] in ("TERIMAAN", "BAYARAN")
for yr in (2014, 2013):
    ter = sum(F(r, "amount_rm") for r in cs if r["flow"] == "TERIMAAN" and is_item(r) and int(r["year"]) == yr)
    bay = sum(F(r, "amount_rm") for r in cs if r["flow"] == "BAYARAN" and is_item(r) and int(r["year"]) == yr)
    check(f"cash: sum(terimaan items) {yr} = printed Jumlah Terimaan", ter, JUM_TERIMAAN[yr])
    check(f"cash: sum(bayaran items) {yr} = printed Jumlah Bayaran", bay, JUM_BAYARAN[yr])
    jt = next(F(r, "amount_rm") for r in cs if r["item_bm"] == "Jumlah Terimaan" and int(r["year"]) == yr)
    jb = next(F(r, "amount_rm") for r in cs if r["item_bm"] == "Jumlah Bayaran" and int(r["year"]) == yr)
    check(f"cash: captured Jumlah Terimaan row {yr}", jt, JUM_TERIMAAN[yr])
    check(f"cash: captured Jumlah Bayaran row {yr}", jb, JUM_BAYARAN[yr])
    tk = next(F(r, "amount_rm") for r in cs if "WANG TUNAI PADA 31" in r["item_bm"].upper() and int(r["year"]) == yr)
    check(f"cash: closing cash {yr} = printed", tk, TUNAI_AKHIR[yr])
    op = next(F(r, "amount_rm") for r in cs if r["item_bm"] == "Wang Tunai Pada 1 Januari" and int(r["year"]) == yr)
    check(f"cash: roll-forward opening+net=closing {yr}", op + JUM_TERIMAAN[yr] - JUM_BAYARAN[yr], TUNAI_AKHIR[yr])
    for (flow, cat), wants in CASH_CAT.items():
        got = sum(F(r, "amount_rm") for r in cs if r["flow"] == flow and r["category_bm"] == cat
                  and is_item(r) and int(r["year"]) == yr)
        check(f"cash: {flow}/{cat} items sum = printed category total {yr}", got, wants[yr])
        cap = next(F(r, "amount_rm") for r in cs if r["flow"] == flow and r["category_bm"] == cat
                   and r["item_bm"].startswith("Jumlah ") and int(r["year"]) == yr)
        check(f"cash: {flow}/{cat} captured category-total row {yr}", cap, wants[yr])
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2014")
check("cross: cash closing 2014 = position Wang Tunai", TUNAI_AKHIR[2014], pos_tunai)
# cash-basis Hasil differs from Nota 5(a) by the printed Nota 5(a) reconciliation items
cash_hasil = sum(F(r, "amount_rm") for r in cs if r["category_bm"] == "Hasil" and is_item(r) and int(r["year"]) == 2014)
check("cash: Hasil (cash) + Nota 5(a) reconciliation = Nota 5(a) JUMLAH HASIL",
      cash_hasil + 1_550_000_000 + 123_101 + 529_495, HASIL[2014])

# ---- 7. debt ----
db = load("fact_debt.csv")
mm = load("fact_memorandum.csv")
for yr in (2014, 2013):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed unlabelled DN subtotal", dn, PINJ_DN[yr])
    dn_sub = next(F(r, "amount_rm") for r in db if r["item_bm"] == "Dalam Negeri" and r["kind"] == "subtotal" and int(r["year"]) == yr)
    check(f"debt: captured DN subtotal row {yr}", dn_sub, PINJ_DN[yr])
    kwpp = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Kumpulan Wang Pinjaman Perumahan" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(KWPP instruments) {yr} = printed unlabelled KWPP subtotal", kwpp, KWPP_SUB[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG AWAM" and int(r["year"]) == yr)
    check(f"debt: Hutang Awam {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+KWPP+LN+BLN = Hutang {yr}", dn + kwpp + ln_ + bln, HUTANG[yr])
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
    check(f"debt: DN subtotal + KWPP + Pinjaman Pasaran = PINJAMAN {yr}", dn_sub + kwpp + ln_, pj)
    hm = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Hutang Awam" and int(r["year"]) == yr)
    check(f"cross: memo Hutang Awam = debt Hutang {yr}", hm, HUTANG[yr])
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)
# memorandum aset cross-checks
for yr, pbd, pel in ((2014, 99_036_023_598, 29_883_017_259), (2013, 92_444_600_374, 29_679_137_799)):
    got = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pinjaman Boleh Dituntut" and int(r["year"]) == yr)
    check(f"memo: Pinjaman Boleh Dituntut {yr} = printed", got, pbd)
    got = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelaburan" and int(r["year"]) == yr)
    check(f"memo: Pelaburan {yr} = printed", got, pel)

# ---- 8. trust ----
tr = load("fact_trust_accounts.csv")
for r in tr:
    if r["parent_group_bm"] == "JUMLAH":
        continue
    flow = F(r, "baki_awal_rm") - F(r, "debit_rm") + F(r, "kredit_rm")
    check(f"trust row identity [{r['account_bm'][:34]}]", flow, F(r, "baki_akhir_rm"), tol=0.5)
grand = next(r for r in tr if r["parent_group_bm"] == "JUMLAH")
kids = [r for r in tr if r["parent_group_bm"] == ""]
for col in ["baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"]:
    check(f"trust: sum(groups).{col} = AKAUN AMANAH DISATUKAN", sum(F(r, col) for r in kids), F(grand, col))
check("trust: closing = printed Nota 7 total 2014", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2014])
check("trust: opening = printed Nota 7 total 2013", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2013])
check("cross: trust closing = position Akaun Amanah 2014", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2014"))
for parent, members in [("KUMPULAN WANG AMANAH KERAJAAN",
                         ["Kumpulan Wang Pembangunan", "Kumpulan Wang Pinjaman Perumahan",
                          "Pelbagai Kumpulan Wang Amanah Kerajaan"]),
                        ("KUMPULAN WANG AMANAH AWAM",
                         ["Kumpulan Wang Amanah Khas", "Kumpulan Wang Amanah Am"]),
                        ("AKAUN DEPOSIT", ["Deposit Am", "Deposit Pelarasan"])]:
    for col in ["baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"]:
        det = sum(F(r, col) for r in tr if r["parent_group_bm"] == parent)
        sub = next(F(r, col) for r in tr if r["parent_group_bm"] == "" and r["account_bm"] == parent)
        check(f"trust: {parent} members.{col} = group total", det, sub)

# ---- 9. Lampiran 1 detail (4 printed value columns) ----
od = load("fact_opex_detail.csv")
for col in ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]:
    leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            leaf[r["maksud_code"]] += F(r, col)
    ncol = {"anggaran_asal_rm": "anggaran_asal_rm", "anggaran_jumlah_rm": "anggaran_dipinda_rm",
            "sebenar_rm": "sebenar_rm"}[col]
    okc = sum(1 for r in ox if abs(leaf[r["maksud_code"]] - F(r, ncol)) < 1)
    check(f"opex_detail[{col}]: maksud leaf sums = Nota 5(b) ({N_MAKSUD} maksud)", okc, N_MAKSUD)
    jm = {}
    for r in od:
        if r["row_type"] == "jumlah_maksud":
            jm[r["maksud_code"]] = F(r, col)
    okc = sum(1 for k, v in jm.items() if abs(leaf[k] - v) < 1)
    check(f"opex_detail[{col}]: maksud leaf sums = printed JUMLAH maksud rows ({N_MAKSUD})", okc, N_MAKSUD)
for col in ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]:
    seen = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            seen[(r["maksud_code"], r["aktiviti_code"])] += F(r, col)
    ja = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            ja[(r["maksud_code"], r["aktiviti_code"])] += F(r, col)
    bad = sum(1 for k, v in ja.items() if abs(seen.get(k, 0.0) - v) >= 1)
    # diagnosed printed aktiviti-code typos (verified on the pages, kept as
    # printed): B.07 pdf 111 'Jumlah 050400' should read 050500 (MyWIN
    # Academy); B.11 pdf 128 'Jumlah 023300' should read 023400 (NBOS).
    # The 050400 typo nets out in anggaran_asal (both cells 7,000,000/0).
    exp_bad_akt = {"anggaran_asal_rm": 1, "anggaran_jumlah_rm": 2, "sebenar_rm": 2}[col]
    check(f"opex_detail[{col}]: aktiviti leaf sums = printed Jumlah aktiviti "
          f"(bad groups; {exp_bad_akt} diagnosed printed code typos)", bad, exp_bad_akt)
    prog_leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
        # 2014 layout: many programs carry objects DIRECTLY (no aktiviti tier)
        if r["row_type"] == "object_aktiviti" and not r["aktiviti_code"]:
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = sum(1 for k, v in jp.items() if abs(prog_leaf.get(k, 0.0) - v) >= 1)
    # diagnosed printed program-code typo: B.31 pdf 185 prints the 'ONE-OFF'
    # (170000) program total as 'Jumlah 070000', colliding with the MUZIUM
    # 070000 program; each block's own figures foot (verified below)
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program "
          f"(bad groups; 1 diagnosed printed code typo B.31)", badp, 1)
    for k, v in jp.items():
        if abs(prog_leaf.get(k, 0.0) - v) >= 1 and k == ("B.31", "070000"):
            resid = v - prog_leaf.get(k, 0.0)
            check(f"opex_detail[{col}]: B.31 'Jumlah 070000' typo residual = 170000 aktiviti sum",
                  resid, prog_leaf.get(("B.31", "170000"), 0.0), tol=1.0)
for col in ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]:
    jenis_rows = [r for r in od if r["row_type"] == "jumlah_jenis"]
    jb_rows = [r for r in od if r["row_type"] == "jumlah_besar"]
    jenis_sum = sum(F(r, col) for r in jenis_rows)
    check(f"opex_detail[{col}]: sum(jenis totals) = grand total", jenis_sum, F(jb_rows[0], col), tol=1.0)
    jm_all = sum(F(r, col) for r in od if r["row_type"] == "jumlah_maksud")
    check(f"opex_detail[{col}]: sum(maksud totals) = grand total", jm_all, F(jb_rows[0], col), tol=1.0)
jb = [r for r in od if r["row_type"] == "jumlah_besar"]
check("opex_detail: grand total sebenar = printed Lampiran 1 (sen)", F(jb[0], "sebenar_rm"), OPEX_L1, tol=0.005)
check("opex_detail: grand total sebenar = Nota total (rounded)", F(jb[0], "sebenar_rm"), OPEX_NOTA_TOTAL, tol=0.5)
check("opex_detail: jenis totals sebenar = printed Tanggungan+Bekalan",
      sum(F(r, "sebenar_rm") for r in od if r["row_type"] == "jumlah_jenis"),
      TANGGUNGAN + BEKALAN, tol=1.0)
for col in ("anggaran_tambahan_rm", "viremen_rm", "varian_rm"):
    nonempty = sum(1 for r in od if r[col] not in ("", "None"))
    check(f"opex_detail[{col}]: not printed in the 2014 4-column layout (populated rows)", nonempty, 0)

# ---- 10. devex project ----
dp = load("fact_devex_project.csv")
for col in ["kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm", "anggaran_langsung_rm",
            "anggaran_pinjaman_rm", "anggaran_jumlah_rm", "sebenar_langsung_rm",
            "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke10_rm"]:
    ps = defaultdict(float)
    for r in dp:
        if r["row_type"] == "project":
            ps[r["maksud_code"]] += F(r, col)
    okc = sum(1 for r in dx if r["maksud_code"] != "TOTAL" and abs(ps[r["maksud_code"]] - F(r, col)) < 1)
    check(f"devex_project[{col}]: project sums = ministry totals ({N_MINISTRIES_L2})", okc, N_MINISTRIES_L2)
    mt = sum(F(r, col) for r in dp if r["row_type"] == "ministry_total")
    gt_ = next(F(r, col) for r in dp if r["row_type"] == "grand_total")
    check(f"devex_project[{col}]: ministry totals sum = grand total", mt, gt_, tol=0.02)
gt = next(r for r in dp if r["row_type"] == "grand_total")
check("devex_project: grand total = printed (sen)", F(gt, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
idfail = 0
for r in dp:
    if r["row_type"] == "project":
        if abs(F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm") - F(r, "sebenar_jumlah_rm")) > 1:
            idfail += 1
        if abs(F(r, "anggaran_langsung_rm") + F(r, "anggaran_pinjaman_rm") - F(r, "anggaran_jumlah_rm")) > 1:
            idfail += 1
        # RMKe-10 year 4: prior cumulative + 2014 actual = cumulative to 31.12.2014
        if abs(F(r, "terkumpul_rmke10_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke10_rm")) > 0.011:
            idfail += 1
check("devex_project: per-project identities (0 failures; RMKe-10: prior+sebenar=terkumpul)", idfail, 0)

# ---- 11. timeseries ----
ts = load("fact_timeseries_2005_2014.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2005-2014 (10 years)", len(years), 10)
check("timeseries: min year 2005", years[0], 2005)
check("timeseries: max year 2014", years[-1], 2014)
panel14 = [
    ("Hasil", "Jumlah Hasil", HASIL[2014]),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2014]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2014]),
    ("Hutang Awam Luar Negeri", "Jumlah Hutang Awam", HUTANG[2014]),
    ("Pinjaman Boleh Dituntut", "Jumlah Pinjaman Boleh Dituntut", 99_036_023_598),
]
for sec, item, rm in panel14:
    got = tv.get((sec, item, 2014))
    check(f"timeseries: {item} 2014 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
XFOOT = [
    ("Wang Awam", ["Wang Tunai", "Pelaburan"], "Jumlah Wang Awam"),
    ("Kumpulan Wang Disatukan", ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan"],
     "Jumlah Kumpulan Wang Disatukan"),
    ("Punca Dana", ["Hasil", "Terimaan Kumpulan Wang Pembangunan", "Terimaan Bersih Kumpulan Wang Amanah Lain"],
     "Jumlah Punca Dana"),
    ("Penggunaan Dana", ["Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)",
                         "Perbelanjaan Pembangunan", "Bayaran Bersih Kumpulan Wang Amanah Lain"],
     "Jumlah Penggunaan Dana"),
    ("Hasil", ["Cukai Langsung", "Cukai Tidak Langsung", "Terimaan Lain"], "Jumlah Hasil"),
    ("Perbelanjaan Mengurus", ["Emolumen", "Perkhidmatan dan Bekalan", "Aset",
                               "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan Lain"],
     "Jumlah Perbelanjaan Mengurus"),
    ("Terimaan Pinjaman Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                        "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "SUKUK", "Pinjaman Lain"],
     "Jumlah Terimaan Pinjaman Dalam Negeri"),
    ("Terimaan Pinjaman Luar Negeri", ["Pinjaman Pasaran", "Pinjaman Projek", "Pinjaman Lain"],
     "Jumlah Terimaan Pinjaman Luar Negeri"),
    ("Bayaran Balik Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                    "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "SUKUK", "Pinjaman Lain"],
     "Jumlah Bayaran Balik Dalam Negeri"),
    ("Bayaran Balik Luar Negeri", ["Pinjaman Pasaran", "Pinjaman Projek", "Pinjaman Lain"],
     "Jumlah Bayaran Balik Luar Negeri"),
    ("Pinjaman Bersih Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                      "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "SUKUK", "Pinjaman Lain"],
     "Jumlah Pinjaman Bersih Dalam Negeri"),
    ("Pinjaman Bersih Luar Negeri", ["Pinjaman Pasaran", "Pinjaman Projek", "Pinjaman Lain"],
     "Jumlah Pinjaman Bersih Luar Negeri"),
    ("Wang Tunai", ["Wang Tunai Dalam Bank", "Wang Tunai Dalam Tangan dan Dalam Perjalanan"], "Jumlah Wang Tunai"),
    ("Pelaburan", ["Pelaburan Kumpulan Wang Amanah", "Pelaburan Am"], "Jumlah Pelaburan"),
    ("Pinjaman Boleh Dituntut", ["Kerajaan Negeri", "Pihak Berkuasa Tempatan", "Badan Berkanun",
                                 "Koperasi", "Syarikat", "Perseorangan", "Pelbagai"],
     "Jumlah Pinjaman Boleh Dituntut"),
    ("Kewangan", ["Lebihan/(Kurangan) Akaun Semasa", "Lebihan/(Kurangan) Akaun Pembangunan"],
     "Lebihan/(Kurangan) Keseluruhan"),
    ("Perubahan Dalam Modal Kerja", ["Tambahan/(Kurangan) Wang Tunai dan Pelaburan",
                                     "Pinjaman Bersih Dalam dan Luar Negeri"],
     "Tambahan/(Kurangan) Modal Kerja"),
    ("Dibiayai oleh:", ["Pinjaman Bersih Dalam Negeri", "Pinjaman Bersih Luar Negeri", "Baki Akaun"], "Jumlah"),
    ("Kumpulan Wang Pembangunan / Penerimaan",
     ["Caruman dari Akaun Hasil Disatukan", "Pindahan dari Akaun Pinjaman Disatukan", "Lain-lain"],
     "Jumlah Penerimaan"),
    ("Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan", ["Langsung", "Pinjaman"], "Jumlah Pembayaran"),
    ("Hutang Awam Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                  "Sekuriti Kerajaan Malaysia", "SUKUK", "Pinjaman Lain"],
     "Jumlah Hutang Awam Dalam Negeri"),
    ("Hutang Awam Luar Negeri", ["Pinjaman Pasaran", "Bantuan Luar Negeri", "Pinjaman Lain"],
     "Jumlah Hutang Awam Luar Negeri"),
    ("Jaminan", ["Pinjaman Dalam Negeri", "Pinjaman Luar Negeri"], "Jumlah Jaminan"),
]
for sec, parts, total_item in XFOOT:
    bad_years = []
    for yr in years:
        if (sec, total_item, yr) not in tv:
            bad_years.append((yr, "total missing"))
            continue
        ssum = sum(tv.get((sec, p, yr), 0.0) for p in parts)
        if abs(ssum - tv[(sec, total_item, yr)]) > 1.5:
            bad_years.append((yr, ssum - tv[(sec, total_item, yr)]))
    check(f"timeseries xfoot [{sec} -> {total_item}] all 10 years (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   xfoot detail {sec} -> {total_item}: {bad_years}")
CROSSTOT = [
    ("Terimaan Pinjaman Luar Negeri", "Jumlah Terimaan Pinjaman",
     [("Terimaan Pinjaman Dalam Negeri", "Jumlah Terimaan Pinjaman Dalam Negeri"),
      ("Terimaan Pinjaman Luar Negeri", "Jumlah Terimaan Pinjaman Luar Negeri")]),
    ("Bayaran Balik Luar Negeri", "Jumlah Bayaran Balik",
     [("Bayaran Balik Dalam Negeri", "Jumlah Bayaran Balik Dalam Negeri"),
      ("Bayaran Balik Luar Negeri", "Jumlah Bayaran Balik Luar Negeri")]),
    ("Pinjaman Bersih Luar Negeri", "Jumlah Pinjaman Bersih",
     [("Pinjaman Bersih Dalam Negeri", "Jumlah Pinjaman Bersih Dalam Negeri"),
      ("Pinjaman Bersih Luar Negeri", "Jumlah Pinjaman Bersih Luar Negeri")]),
    ("Hutang Awam Luar Negeri", "Jumlah Hutang Awam",
     [("Hutang Awam Dalam Negeri", "Jumlah Hutang Awam Dalam Negeri"),
      ("Hutang Awam Luar Negeri", "Jumlah Hutang Awam Luar Negeri")]),
]
for tsec, titem, parts in CROSSTOT:
    bad_years = []
    for yr in years:
        if (tsec, titem, yr) not in tv:
            bad_years.append((yr, "total missing"))
            continue
        ssum = sum(tv.get((ps, pi, yr), 0.0) for ps, pi in parts)
        if abs(ssum - tv[(tsec, titem, yr)]) > 1.5:
            bad_years.append((yr, ssum - tv[(tsec, titem, yr)]))
    check(f"timeseries xfoot [{titem} = DN+LN] all 10 years (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   xfoot detail {titem}: {bad_years}")
AH = "Akaun Hasil Disatukan"
bad_years = []
for yr in years:
    lhs = (tv.get((AH, "Baki pada 1 Januari", yr), 0.0) + tv.get((AH, "Hasil", yr), 0.0)
           - tv.get((AH, "( - ) Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)", yr), 0.0)
           - tv.get((AH, "( - ) Perbelanjaan Pembangunan", yr), 0.0))
    if abs(lhs - tv.get((AH, "Baki pada 31 Disember", yr), 0.0)) > 3.0:
        bad_years.append((yr, lhs - tv.get((AH, "Baki pada 31 Disember", yr), 0.0)))
check("timeseries identity [Akaun Hasil roll] all 10 years (bad years)", len(bad_years), 0)
if bad_years:
    print(f"   identity detail Akaun Hasil: {bad_years}")
AP = "Akaun Pinjaman Disatukan"
bad_years = []
for yr in years:
    lhs = (tv.get((AP, "Baki pada 1 Januari", yr), 0.0) + tv.get((AP, "Pinjaman Bersih", yr), 0.0)
           + tv.get((AP, "Pindahan", yr), 0.0))
    if abs(lhs - tv.get((AP, "Baki pada 31 Disember", yr), 0.0)) > 3.0:
        bad_years.append((yr, lhs - tv.get((AP, "Baki pada 31 Disember", yr), 0.0)))
check("timeseries identity [Akaun Pinjaman roll] all 10 years (bad years)", len(bad_years), 0)
if bad_years:
    print(f"   identity detail Akaun Pinjaman: {bad_years}")
CLOSING_SEC = {
    "Kumpulan Wang Pembangunan": "Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan",
}
for sec in ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan",
            "Kumpulan Wang Pembangunan", "Kumpulan Wang Pinjaman Perumahan",
            "Pelbagai Kumpulan Wang Amanah Kerajaan", "Kumpulan Wang Amanah Awam", "Wang Deposit"]:
    cl_sec = CLOSING_SEC.get(sec, sec)
    bad_years = []
    for yr in years[1:]:
        op_this = tv.get((sec, "Baki pada 1 Januari", yr))
        cl_prev = tv.get((cl_sec, "Baki pada 31 Disember", yr - 1))
        if op_this is None or cl_prev is None:
            continue
        yr_all_zero = all(tv.get((s2, it, yr), 0.0) == 0.0
                          for s2 in {sec, cl_sec}
                          for it in ("Baki pada 1 Januari", "Terimaan/(Bayaran) Bersih",
                                     "Baki pada 31 Disember"))
        if yr_all_zero and op_this == 0.0:
            continue
        if abs(op_this - cl_prev) > 1.0:
            bad_years.append((yr, op_this - cl_prev))
    # diagnosed printed panel inconsistency: at the 2007->2008 boundary the
    # panel moves RM350 juta between Pelbagai KWAK (closing 2007 21,278 vs
    # opening 2008 20,928) and Wang Deposit (6,287 vs 6,637) - printed as such
    exp_roll = 1 if sec in ("Pelbagai Kumpulan Wang Amanah Kerajaan", "Wang Deposit") else 0
    check(f"timeseries roll [{sec}] opening=prior closing (bad years; "
          f"{exp_roll} diagnosed printed inconsistency)", len(bad_years), exp_roll)
    if bad_years:
        print(f"   roll detail {sec}: {bad_years}")

# ---- 12. Nota 5 statement table ----
ras = load("fact_revenue_account_statement.csv")
g5 = {(r["line_item_bm"], int(r["year"])): F(r, "sebenar_rm") for r in ras}
for yr in (2014, 2013):
    comp = sum(g5[(k, yr)] for k in ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"])
    check(f"nota5stmt: hasil components sum = Jumlah Hasil {yr}", comp, g5[("Jumlah Hasil", yr)])
    obj = sum(g5[(k, yr)] for k in ["Emolumen", "Perkhidmatan dan Bekalan", "Aset",
                                    "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"])
    check(f"nota5stmt: opex object components sum = Jumlah sebelum pindahan {yr}",
          obj, g5[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr)])
    check(f"nota5stmt: sebelum + pindahan = selepas pindahan {yr}",
          g5[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr)]
          + g5[("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", yr)],
          g5[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)])
    check(f"nota5stmt: hasil = perf revenue {yr}", g5[("Jumlah Hasil", yr)], HASIL[yr])
    check(f"nota5stmt: opex sebelum pindahan = perf opex {yr}",
          g5[("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr)], OPEX_PRESTASI[yr])
    check(f"nota5stmt: baki roll-forward {yr}",
          g5[("BAKI PADA 1 JANUARI", yr)] + g5[("Jumlah Hasil", yr)]
          - g5[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)],
          g5[("BAKI PADA 31 DISEMBER", yr)])
check("nota5stmt: Akaun Hasil balance fixed at 11,863,127,086 since 1996",
      g5[("BAKI PADA 31 DISEMBER", 2014)], 11_863_127_086)

# ---- 13. Nota 6 loan account statement ----
la = load("fact_loan_account_statement.csv")
for yr in (2014, 2013):
    closing = next(F(r, "amount_rm") for r in la if r["row_type"] == "closing" and int(r["year"]) == yr)
    pos = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN PINJAMAN DISATUKAN" and int(r["year"]) == yr)
    check(f"cross: Nota 6 closing = position Akaun Pinjaman {yr}", closing, pos)

# ---- 14. devex program linkage ----
dp2 = load("fact_devex_project.csv")
psum = defaultdict(float)
for r in dp2:
    if r["row_type"] == "project" and r["program_bm"]:
        psum[(r["maksud_code"], r["program_bm"].upper())] += F(r, "sebenar_jumlah_rm")
okp = badp = 0
for r in dp2:
    if r["row_type"] == "program_subtotal":
        key = (r["maksud_code"], (r["program_bm"] or r["name_bm"]).upper())
        if key in psum:
            if abs(psum[key] - F(r, "sebenar_jumlah_rm")) < 1:
                okp += 1
            else:
                badp += 1
check("devex: program subtotals matched by linked project sums", badp, 0)
check("devex: verified program-linkage groups >= 30", 1 if okp >= 30 else 0, 1)

# ---- 15. trust fund detail cross to Nota 7 top table ----
tfd = load("fact_trust_fund_detail.csv")
kwp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
                 and r["row_type"] == "closing" and r["year"] == "2014")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
kwpp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pinjaman Perumahan"
                  and r["row_type"] == "closing" and r["year"] == "2014")
kwpp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pinjaman Perumahan")
check("cross: Nota7(a)(ii) closing = Nota 7 table KWPP closing", kwpp_close, kwpp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2014")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(iii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2014")
kaw_top = next(F(r, "baki_akhir_rm") for r in tr
               if r["parent_group_bm"] == "" and r["account_bm"] == "KUMPULAN WANG AMANAH AWAM")
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2014")
dep_top = next(F(r, "baki_akhir_rm") for r in tr
               if r["parent_group_bm"] == "" and r["account_bm"] == "AKAUN DEPOSIT")
check("cross: Nota7(c) total = Nota 7 table Deposit closing", dep_close, dep_top)
# KWP statement vs prestasi devex
kwp_bay = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
               and r["line_item_bm"] == "Jumlah Bayaran" and r["year"] == "2014")
check("cross: Nota7(a)(i) Jumlah Bayaran = perf Belanja Pembangunan 2014", kwp_bay, DEVEX[2014])

# ---- 16. printed aktiviti-code anomaly scan (diagnosed, never corrected) ----
akt_sum = defaultdict(float)
for r in od:
    if r["row_type"] == "object_aktiviti":
        akt_sum[(r["maksud_code"], r["pdf_page"], r["aktiviti_code"])] += F(r, "sebenar_rm")
akt_sum_all = defaultdict(float)
for r in od:
    if r["row_type"] == "object_aktiviti":
        akt_sum_all[(r["maksud_code"], r["aktiviti_code"])] += F(r, "sebenar_rm")
ja_sum_all = defaultdict(float)
for r in od:
    if r["row_type"] == "jumlah_aktiviti":
        ja_sum_all[(r["maksud_code"], r["aktiviti_code"])] += F(r, "sebenar_rm")
anomalies = []
for r in od:
    if r["row_type"] != "jumlah_aktiviti":
        continue
    key = (r["maksud_code"], r["aktiviti_code"])
    if abs(akt_sum_all.get(key, 0.0) - F(r, "sebenar_rm")) < 1:
        continue
    if abs(akt_sum_all.get(key, 0.0) - ja_sum_all.get(key, 0.0)) < 1:
        # duplicate printed aktiviti code (e.g. B.22 pdf 149 prints both
        # 'NKRA - Education' and 'NBOS - RTC' as 120600): each block's Jumlah
        # foots against its own leaves and the code-level aggregate agrees
        print(f"   duplicate printed aktiviti code (blocks individually consistent): "
              f"'{r['label_bm']}' (pdf {r['pdf_page']}, {r['maksud_code']}) value {F(r,'sebenar_rm'):,.2f}")
        continue
    cands = [k[2] for k, v in akt_sum.items()
             if k[0] == r["maksud_code"] and k[1] == r["pdf_page"] and abs(v - F(r, "sebenar_rm")) < 1]
    anomalies.append((r["maksud_code"], r["pdf_page"], r["label_bm"], F(r, "sebenar_rm"), cands))
check("lampiran1: jumlah_aktiviti rows not matching their own leaf sum (all diagnosed)",
      sum(1 for a in anomalies if not a[4]), 0)
for mk, pg, lbl, val, cands in anomalies:
    if cands:
        print(f"   printed-typo diagnosis: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f} "
              f"matches aktiviti {cands} leaf sum — printed code typo in the volume")
    else:
        print(f"   UNRESOLVED jumlah_aktiviti mismatch: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f}")

# ---- print-discrepancy diagnoses (proven from the volume's own pages) ----
DIAGNOSES = [
    ("lampiran1 aktiviti-code printed typos (B.07 pdf 111, B.11 pdf 128)",
     "B.07: aktiviti 050500 MyWIN Academy's total prints as 'Jumlah 050400'; "
     "B.11: aktiviti 023400 (NBOS)'s total prints as 'Jumlah 023300'. Both "
     "verified against the blocks' own printed leaves; kept as printed"),
    ("lampiran1 program-code printed typo (B.31, pdf 185)",
     "the 'ONE-OFF' program 170000's total prints as 'Jumlah 070000', "
     "colliding with the MUZIUM 070000 program earlier in B.31; residual "
     "equals the 170000 aktiviti sum exactly; kept as printed"),
    ("lampiran1 duplicate printed aktiviti code (B.22, pdf 149)",
     "two consecutive activities both print code 120600 ('NKRA - Education' "
     "and 'NBOS - RTC'); each block's Jumlah 120600 foots against its own "
     "leaves and the code-level aggregate agrees; kept as printed"),
    ("lampiran1 5-digit aktiviti code (B.24, pdf 158)",
     "aktiviti header prints '80100 Perbadanan Perusahaan Kecil dan Sederhana "
     "Malaysia (SME Corp. Malaysia)' with the leading zero dropped; read as "
     "080100 (its Jumlah row prints 'Jumlah 080100'), flagged here"),
    ("timeseries 2007/2008 RM350 juta printed panel inconsistency",
     "the 10-year panel prints Pelbagai KWAK closing 2007 = 21,278 vs opening "
     "2008 = 20,928 and Wang Deposit closing 2007 = 6,287 vs opening 2008 = "
     "6,637 (RM350 juta moved between the two lines at the boundary); both "
     "kept as printed"),
    ("lampiran1 omitted program headers on continuation pages (3 blocks)",
     "aktiviti 010200 (T.12, pdf 82), 280100 (B.06, pdf 103) and 040100 "
     "(B.32, pdf 186) print without their program header on the continuation "
     "page; program inferred from the code prefix and back-filled, reported"),
    ("lampiran1 bare object code (B.62, pdf 242)",
     "an object row prints its 5-digit code '30000' with NO class name; the row's "
     "figures foot inside their aktiviti; objek_class taken from the standard "
     "chart of accounts and flagged here, figures kept as printed"),
    ("lampiran2 sparse right-page row (Rancangan Bekalan Air Negeri Terengganu, pdf 260)",
     "six of seven value cells print BLANK (not even a dash); only terkumpul "
     "RMKe-10 prints (51,476,481.00 = the prior cumulative; project complete, "
     "no 2014 activity); blanks resolved as 0.0 by column x-position and the "
     "per-row identities, flagged here"),
    ("lampiran2 blank Kos Keseluruhan cell (P.62 butiran 47000, pdf 271)",
     "the Kos Keseluruhan cell prints blank; kept as 0.0 (print omission), "
     "row otherwise foots"),
    ("lampiran2 P.62 RM10 pendahuluan rows (printed Nota)",
     "printed note: P.62 butiran 03000, 05000 dan 36000 carry RM10 token "
     "provisions to be tabled in the 2015 parliamentary session, dimasuk kira "
     "sebagai pendahuluan - rows kept exactly as printed with has_footnote"),
    ("cash statement Hasil Bukan Cukai vs Nota 5(a) (printed, explained in Nota 5(a))",
     "cash-basis Hasil Bukan Cukai 52,348,131,946 differs from Nota 5(a) "
     "53,898,784,542 by 1,550,652,596 = Akaun Premium TPK 1,550,000,000 + "
     "pelarasan pinjaman Kerajaan Negeri 123,101 + pelarasan LAD 529,495; both "
     "kept as printed, reconciliation captured in fact_other_notes"),
    ("cash statement vs Nota 6 Bilateral figures (declared non-cash transactions)",
     "Nota 6 prints Bilateral Terimaan 247,564,982 vs cash 222,744,257 (diff "
     "24,820,725 non-cash loan-drawdown adjustment) and Bayaran (524,557,514) vs "
     "cash 516,480,465 (diff 8,077,049 non-cash repayment); both kept as printed "
     "in their own tables"),
    ("cash statement devex vs prestasi/KWP devex (declared non-cash transactions)",
     "cash statement Perbelanjaan Pembangunan 39,468,595,127 vs prestasi/Nota "
     "7(a)(i) 39,503,487,396: printed difference 34,892,269 = 24,820,725 "
     "non-cash loan disbursement + 10,071,544 APKPS non-cash adjustments"),
    ("Nota 6 prestasi financing figure RM1 rounding",
     "68,968,444,110 - 26,380,357,864 - 5,400,000,000 = 37,188,086,246 vs the "
     "printed prestasi Pinjaman dan Bantuan Luar Negeri 37,188,086,245: RM1 "
     "difference consistent with the volume's declared rounding (Nota 1(i))"),
    ("Nota 8(a) declared restatement of the 2013 Pinjaman Boleh Dituntut comparative",
     "2013 Pinjaman Boleh Dituntut restated from 92,547,188,214 to 92,444,600,374 "
     "(forex revaluation of foreign-currency loans + reclassification of a "
     "borrower from Badan Berkanun to Syarikat) — declared in the volume, "
     "captured in fact_other_notes"),
    ("Nota 4 declared reclassification of investment categories (Mulai tahun 2014)",
     "Saham reclassified into Sekuriti Tersiar/Tidak Tersiar Harga Dalam Negeri; "
     "Deposit Dalam Negeri split into short/long-term; 2013 comparatives restated "
     "to the new classification (declared in the volume)"),
    ("Nota 9(a) new KWPP financing split (Mulai tahun 2014)",
     "Pembiayaan Kumpulan Wang Pinjaman Perumahan newly split into Pinjaman "
     "Berjangka and Sukuk Perumahan Kerajaan (declared in the volume)"),
    ("register absences in the 2014 volume (6 lampiran only)",
     "no Komitmen Jaminan register (fact_guarantees), no finance-lease disclosure "
     "(fact_finance_leases), no PFI tranche register, no Penyata Penyaluran Geran, "
     "no Komitmen Pampasan/Bayaran Balik Cukai disclosures; Nota 10 Liabiliti Luar "
     "Jangka gives two narrative totals only (fact_other_notes), and the Lampiran 6 "
     "Jaminan Berkanun register carries the full guarantee detail "
     "(fact_statutory_guarantees)"),
]

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
with open(f"{WH}/_validation_checks_2014.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
    for name, diag in DIAGNOSES:
        cw.writerow(["DIAGNOSIS", f"core: {name}: {diag}", "", "", ""])
