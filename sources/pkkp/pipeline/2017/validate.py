#!/usr/bin/env python3
"""Programmatic validation for the 2017 warehouse: extracted line items must
reproduce printed totals. Never corrects — only reports PASS/FAIL with amounts.
All reference figures are typed from the 2017 volume's own printed statements."""
import os
import csv
from collections import defaultdict

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2017")
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2017 volume) ----
# Penyata Kedudukan Kewangan pdf 54
WANG_AWAM = {2017: 42_184_431_834, 2016: 39_373_333_718}
# Penyata Prestasi Kewangan pdf 57
HASIL = {2017: 220_406_001_884, 2016: 212_421_098_894}
OPEX_PRESTASI = {2017: 217_695_192_668, 2016: 210_172_661_334}
DEVEX = {2017: 44_883_838_833, 2016: 41_995_037_697}
KURANGAN = {2017: -42_173_029_617, 2016: -39_746_600_137}
# Cash statement pdf 55-56 (cash-basis HASIL differs from Nota 5(a); Nota 8 explains)
JUM_TERIMAAN = {2017: 362_943_563_718, 2016: 316_011_224_041}
JUM_BAYARAN = {2017: 360_942_896_952, 2016: 322_920_310_464}
TUNAI_AKHIR = {2017: 18_064_128_458, 2016: 16_063_461_692}
# Nota 5(b) pdf 63
TANGGUNGAN = 55_633_124_354
BEKALAN = 164_772_877_530
OPEX_NOTA_TOTAL = 220_406_001_884  # includes transfer to KW Pembangunan (inside B.12)
N_MAKSUD = 50
# Nota 10 pdf 70
HUTANG = {2017: 686_836_648_477, 2016: 648_475_304_686}
PINJ_DN = {2017: 665_571_726_000, 2016: 624_821_726_000}
# Nota 7 pdf 65
AMANAH_AKHIR = {2017: -3_161_093_193, 2016: 7_186_447_384}
# Lampiran 1 grand total (sen precision, pdf 216)
OPEX_L1 = 220_406_001_883.63
# Lampiran 2 grand total (sen precision, pdf 250)
DEVEX_L2 = 44_883_838_832.01
N_MINISTRIES_L2 = 27

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2017, 2016):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2017, 2016):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex=kurangan {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")] - g[("devex", yr, "sebenar")],
          KURANGAN[yr])
    check(f"perf: pembiayaan = kurangan {yr}", g[("total_financing", yr, "sebenar")], -KURANGAN[yr])

# ---- 3. revenue (2017 layout: Cukai Langsung / Cukai Tak Langsung print as
#      BARE headers with no value columns; level-2 sums are checked against
#      the HASIL CUKAI level-1 row) ----
rv = load("fact_revenue.csv")
cols = ["anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "sebenar_prior_rm"]
for col in cols:
    total = next(F(r, col) for r in rv if r["level"] == "0")
    l1sum = sum(F(r, col) for r in rv if r["level"] == "1")
    check(f"rev[{col}]: sum(L1) = HASIL", l1sum, total)
    for l1 in ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]:
        l1v = next(F(r, col) for r in rv if r["level"] == "1" and r["item_bm"] == l1)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l1_bm"] == l1)
        check(f"rev[{col}]: sum(items) = {l1}", l3, l1v)
    l2both = sum(F(r, col) for r in rv if r["level"] == "3"
                 and r["category_l2_bm"] in ("Cukai Langsung", "Cukai Tak Langsung"))
    l1c = next(F(r, col) for r in rv if r["level"] == "1" and r["item_bm"] == "HASIL CUKAI")
    check(f"rev[{col}]: sum(Cukai Langsung + Tak Langsung items) = HASIL CUKAI", l2both, l1c)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2017])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Bekalan", b, BEKALAN)
check("opex: T+B = printed Perbelanjaan Mengurus (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)
for col, want_t, want_b in [("anggaran_asal_rm", 56_543_658_100, 158_256_341_900),
                            ("anggaran_dipinda_rm", 57_207_155_560, 159_492_492_230)]:
    check(f"opex[{col}]: sum(T.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("T.")), want_t)
    check(f"opex[{col}]: sum(B.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("B.")), want_b)

# ---- 5. devex by maksud ----
dx = load("fact_devex_maksud.csv")
mins = [r for r in dx if r["maksud_code"] != "TOTAL"]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm",
            "terkumpul_rmke11_prior_rm", "terkumpul_rmke11_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col), tol=0.02)
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded; RM0.99 print "
      "rounding inconsistency, see DIAGNOSIS)", F(tot, "sebenar_jumlah_rm"), DEVEX[2017], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm")
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)
    check(f"devex row: prior+sebenar=terkumpul RMKe-11 [{r['maksud_code']}]",
          F(r, "terkumpul_rmke11_prior_rm") + F(r, "sebenar_jumlah_rm"),
          F(r, "terkumpul_rmke11_rm"), tol=0.02)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2017, 2016):
    ter = sum(F(r, "amount_rm") for r in cs if r["flow"] == "TERIMAAN" and int(r["year"]) == yr)
    bay = sum(F(r, "amount_rm") for r in cs if r["flow"] == "BAYARAN" and int(r["year"]) == yr)
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
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2017")
check("cross: cash closing 2017 = position Wang Tunai", TUNAI_AKHIR[2017], pos_tunai)
# 2017 cash-basis Hasil differs from Nota 5(a) by the Nota 8 reconciliation items
cash_hasil = sum(F(r, "amount_rm") for r in cs if r["category_bm"] == "Hasil" and int(r["year"]) == 2017)
check("cash: Hasil (cash) + Nota 8 differences = Nota 5(a) HASIL",
      cash_hasil + 15_082_389 + 232_707_113, HASIL[2017])

# ---- 7. debt / memorandum ----
db = load("fact_debt.csv")
for yr in (2017, 2016):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed", dn, PINJ_DN[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG PERSEKUTUAN" and int(r["year"]) == yr)
    check(f"debt: Hutang Persekutuan {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+LN+BLN = Hutang {yr}", dn + ln_ + bln, HUTANG[yr])
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
mm = load("fact_memorandum.csv")
md = load("fact_memo_assets_detail.csv")
for yr in (2017, 2016):
    hm = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Hutang Persekutuan" and int(r["year"]) == yr)
    check(f"cross: memo Hutang = debt Hutang {yr}", hm, HUTANG[yr])
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)
    # the 2017 memorandum statement prints NO Jumlah rows; cross-check the two
    # asset lines against Nota 9 instead
    ppbd_m = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pinjaman dan Pendahuluan Boleh Dituntut" and int(r["year"]) == yr)
    ppbd_n = next(F(r, "amount_rm") for r in md if r["line_item_bm"] == "PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT" and int(r["year"]) == yr)
    check(f"cross: memo PPBD = Nota 9 PPBD {yr}", ppbd_m, ppbd_n)
    pel_m = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelaburan" and int(r["year"]) == yr)
    pel_n = next(F(r, "amount_rm") for r in md if r["line_item_bm"] == "PELABURAN" and int(r["year"]) == yr)
    check(f"cross: memo Pelaburan = Nota 9 Pelaburan {yr}", pel_m, pel_n)

# ---- 8. trust ----
tr = load("fact_trust_accounts.csv")
for r in tr:
    if r["parent_group_bm"] == "JUMLAH":
        continue
    flow = F(r, "baki_awal_rm") - F(r, "debit_rm") + F(r, "kredit_rm")
    check(f"trust row identity [{r['account_bm'][:30]}]", flow, F(r, "baki_akhir_rm"), tol=0.5)
grand = next(r for r in tr if r["parent_group_bm"] == "JUMLAH")
kids = [r for r in tr if r["parent_group_bm"] == ""]
for col in ["baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"]:
    check(f"trust: sum(groups).{col} = AKAUN AMANAH DISATUKAN", sum(F(r, col) for r in kids), F(grand, col))
check("trust: closing = printed Nota 7 total 2017", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2017])
check("trust: opening = printed Nota 7 total 2016", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2016])
check("cross: trust closing = position Akaun Amanah 2017", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2017"))

# ---- 9. financing ----
for yr in (2017, 2016):
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components sum = Jumlah Pembiayaan {yr}", fin, -KURANGAN[yr])

# ---- 10. Lampiran 1 detail (4 printed value columns) ----
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
    exp_akt = {"anggaran_asal_rm": 0, "anggaran_jumlah_rm": 2, "sebenar_rm": 2}[col]
    check(f"opex_detail[{col}]: aktiviti leaf sums = printed Jumlah aktiviti "
          f"(bad groups; {exp_akt} = the B.11 misprinted subtotals, see DIAGNOSIS)", bad, exp_akt)
    prog_leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = sum(1 for k, v in jp.items() if abs(prog_leaf.get(k, 0.0) - v) >= 1)
    exp_prog = {"anggaran_asal_rm": 0, "anggaran_jumlah_rm": 2, "sebenar_rm": 2}[col]
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program "
          f"(bad groups; {exp_prog} = B.11 mirror + B.27 'Jumlah 070000' code typo, see DIAGNOSIS)", badp, exp_prog)
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
# empty 7-column-era fields stay empty in the 4-column 2017 volume
for col in ("anggaran_tambahan_rm", "viremen_rm", "varian_rm"):
    nonempty = sum(1 for r in od if r[col] not in ("", "None"))
    check(f"opex_detail[{col}]: not printed in the 2017 4-column layout (populated rows)", nonempty, 0)

# ---- 11. devex project ----
dp = load("fact_devex_project.csv")
for col in ["kos_keseluruhan_rm", "terkumpul_rmke11_prior_rm", "anggaran_langsung_rm",
            "anggaran_pinjaman_rm", "anggaran_jumlah_rm", "sebenar_langsung_rm",
            "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke11_rm"]:
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
        # RMKe-11 second year: cumulative-to-31.12.2017 = cumulative-to-31.12.2016 + 2017 actual
        if abs(F(r, "terkumpul_rmke11_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke11_rm")) > 0.011:
            idfail += 1
check("devex_project: per-project identities (0 failures; RMKe-11 mid-plan: prior+sebenar==terkumpul)", idfail, 0)

# ---- 12. timeseries ----
ts = load("fact_timeseries_2008_2017.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2008-2017 (10 years)", len(years), 10)
check("timeseries: min year 2008", years[0], 2008)
check("timeseries: max year 2017", years[-1], 2017)
panel17 = [
    ("Hasil", "Jumlah Hasil", HASIL[2017]),
    ("Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", OPEX_PRESTASI[2017]),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2017]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2017]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2017]),
]
for sec, item, rm in panel17:
    got = tv.get((sec, item, 2017))
    check(f"timeseries: {item} 2017 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
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
    ("Hutang Persekutuan Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                         "Sekuriti Kerajaan Malaysia", "SUKUK", "Pinjaman Lain"],
     "Jumlah Hutang Persekutuan Dalam Negeri"),
    ("Hutang Persekutuan Luar Negeri", ["Pinjaman Pasaran", "Bantuan Luar Negeri", "Pinjaman Lain"],
     "Jumlah Hutang Persekutuan Luar Negeri"),
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
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan",
     [("Hutang Persekutuan Dalam Negeri", "Jumlah Hutang Persekutuan Dalam Negeri"),
      ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan Luar Negeri")]),
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
check("timeseries identity [Akaun Hasil roll: opening+hasil-PM-PP=closing] all 10 years (bad years)",
      len(bad_years), 0)
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
        # fund-closure boundary: a year printed as all dashes means the fund no
        # longer operates (Kumpulan Wang Pinjaman Perumahan wound up after 2015,
        # balance transferred to LPPSA) — the volume asserts no roll there
        yr_all_zero = all(tv.get((s2, it, yr), 0.0) == 0.0
                          for s2 in {sec, cl_sec}
                          for it in ("Baki pada 1 Januari", "Terimaan/(Bayaran) Bersih",
                                     "Baki pada 31 Disember"))
        if yr_all_zero and op_this == 0.0:
            continue
        if abs(op_this - cl_prev) > 1.0:
            bad_years.append((yr, op_this - cl_prev))
    check(f"timeseries roll [{sec}] opening=prior closing (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   roll detail {sec}: {bad_years}")

# ---- 13. Nota 5 statement table ----
ras = load("fact_revenue_account_statement.csv")
g5 = {(r["line_item_bm"], int(r["year"])): F(r, "sebenar_rm") for r in ras}
for yr in (2017, 2016):
    comp = sum(g5[(k, yr)] for k in ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"])
    check(f"nota5stmt: hasil components sum {yr}", comp, g5[("HASIL", yr)])
    obj = sum(g5[(k, yr)] for k in ["Emolumen", "Perkhidmatan dan Bekalan", "Aset",
                                    "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"])
    check(f"nota5stmt: opex object components sum {yr}", obj, g5[("PERBELANJAAN MENGURUS (sebelum pindahan)", yr)])
    check(f"nota5stmt: opex + transfer = jumlah selepas pindahan {yr}",
          g5[("PERBELANJAAN MENGURUS (sebelum pindahan)", yr)]
          + g5[("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", yr)],
          g5[("PERBELANJAAN MENGURUS (selepas pindahan)", yr)])
    check(f"nota5stmt: hasil = perf revenue {yr}", g5[("HASIL", yr)], HASIL[yr])
    check(f"nota5stmt: opex = perf opex (before transfer) {yr}",
          g5[("PERBELANJAAN MENGURUS (sebelum pindahan)", yr)], OPEX_PRESTASI[yr])
    check(f"nota5stmt: baki roll-forward {yr}",
          g5[("BAKI PADA 1 JANUARI", yr)] + g5[("HASIL", yr)]
          - g5[("PERBELANJAAN MENGURUS (selepas pindahan)", yr)],
          g5[("BAKI PADA 31 DISEMBER", yr)])
check("nota5stmt: Akaun Hasil balance fixed at 11,863,127,086 since 1996",
      g5[("BAKI PADA 31 DISEMBER", 2017)], 11_863_127_086)

# ---- 14. Nota 6 loan account statement ----
la = load("fact_loan_account_statement.csv")
for yr in (2017, 2016):
    closing = next(F(r, "amount_rm") for r in la if r["row_type"] == "closing" and int(r["year"]) == yr)
    pos = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN PINJAMAN DISATUKAN" and int(r["year"]) == yr)
    check(f"cross: Nota 6 closing = position Akaun Pinjaman {yr}", closing, pos)

# ---- 15. devex program linkage ----
psum = defaultdict(float)
for r in dp:
    if r["row_type"] == "project" and r["program_bm"]:
        psum[(r["maksud_code"], r["program_bm"].upper())] += F(r, "sebenar_jumlah_rm")
okp = badp = 0
for r in dp:
    if r["row_type"] == "program_subtotal":
        key = (r["maksud_code"], (r["program_bm"] or r["name_bm"]).upper())
        if key in psum:
            if abs(psum[key] - F(r, "sebenar_jumlah_rm")) < 1:
                okp += 1
            else:
                badp += 1
check("devex: program subtotals matched by linked project sums", badp, 0)
check("devex: verified program-linkage groups >= 30", 1 if okp >= 30 else 0, 1)

# ---- 16. trust fund detail cross to Nota 7 top table ----
tfd = load("fact_trust_fund_detail.csv")
kwp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
                 and r["row_type"] == "closing" and r["year"] == "2017")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2017")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(ii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2017")
kaw_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Kumpulan Wang Amanah Am", "Kumpulan Wang Amanah Khas"))
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2017")
dep_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Deposit Am", "Deposit Pelarasan"))
check("cross: Nota7(c) total = Nota 7 table Deposit closing", dep_close, dep_top)

# ---- 17. printed aktiviti-code anomaly scan (diagnosed, never corrected) ----
akt_sum = defaultdict(float)
for r in od:
    if r["row_type"] == "object_aktiviti":
        akt_sum[(r["maksud_code"], r["pdf_page"], r["aktiviti_code"])] += F(r, "sebenar_rm")
akt_sum_all = defaultdict(float)
for r in od:
    if r["row_type"] == "object_aktiviti":
        akt_sum_all[(r["maksud_code"], r["aktiviti_code"])] += F(r, "sebenar_rm")
anomalies = []
for r in od:
    if r["row_type"] != "jumlah_aktiviti":
        continue
    key = (r["maksud_code"], r["aktiviti_code"])
    if abs(akt_sum_all.get(key, 0.0) - F(r, "sebenar_rm")) < 1:
        continue
    cands = [k[2] for k, v in akt_sum.items()
             if k[0] == r["maksud_code"] and k[1] == r["pdf_page"] and abs(v - F(r, "sebenar_rm")) < 1]
    anomalies.append((r["maksud_code"], r["pdf_page"], r["label_bm"], F(r, "sebenar_rm"), cands))
check("lampiran1: jumlah_aktiviti rows not matching their own leaf sum "
      "(2 = the B.11 misprinted subtotals, diagnosed; no unexplained cases)",
      sum(1 for a in anomalies if not a[4]), 2)
for mk, pg, lbl, val, cands in anomalies:
    if cands:
        print(f"   printed-typo diagnosis: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f} "
              f"matches aktiviti {cands} leaf sum — printed code typo in the volume")
    else:
        print(f"   UNRESOLVED jumlah_aktiviti mismatch: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f}")

# ---- print-discrepancy diagnoses (proven from the volume's own pages) ----
DIAGNOSES = [
    ("lampiran2 vs prestasi devex rounding inconsistency (RM0.99)",
     "Lampiran 2 prints the grand total in sen: Langsung 42,276,425,978.38 + Pinjaman "
     "2,607,412,853.63 = 44,883,838,832.01; the Penyata Prestasi / Nota 7(a)(i) RM-level "
     "figures print Langsung 42,276,425,979 + Pinjaman 2,607,412,854 = 44,883,838,833 — the "
     "RM-level Langsung figure (…979) is NOT the rounding of the sen figure (…978.38). Both "
     "kept as printed; the perf-vs-L2 check above fails by 0.99 by construction"),
    ("lampiran1 prestasi% printed typos (3 cells, verified against page images)",
     "B.07 030400 50000 Perbelanjaan-perbelanjaan Lain prints 99.99 vs nil sebenar (dipinda 1) "
     "[pdf 103]; B.07 030600 40000 Pemberian prints 99.99 vs nil sebenar (dipinda 1) [pdf 104]; "
     "B.11 022600 40000 Pemberian prints 99.99 (arith. 6,836.43/6,900 = 99.08) [pdf 119]. "
     "All RM columns verified by group sums; % kept as printed"),
    ("lampiran1 misprinted aktiviti subtotals (B.11 020700/020800, pdf 118; image-verified)",
     "the printed 'Jumlah 020700' (723,707,340 / 723,707,264.89) and 'Jumlah 020800' "
     "(27,448,100 / 27,448,001.96) equal ONLY their 40000 object rows, EXCLUDING the "
     "20000 Perkhidmatan dan Bekalan rows printed inside the same blocks (1,023,900 and "
     "871,900/871,808.37); the program-level 'Jumlah 020000' DOES include them, so the "
     "aktiviti subtotal cells are printed arithmetic errors; all cells kept as printed"),
    ("lampiran1 printed program-code typo ('Jumlah 070000' closing block 080000, B.27 pdf 153; image-verified)",
     "the row closing program 080000 'ONE-OFF' (aktiviti 080100 One Off Aset) prints "
     "'Jumlah 070000' — its values 710,509 / 405,738.04 equal the 080100 sums exactly; "
     "kept as printed (program_code follows the label), producing a duplicate Jumlah "
     "070000 pair in B.27"),
    ("lampiran1 printed object-code typo ('020000 Perkhidmatan dan Bekalan', B.64 aktiviti 090300, pdf 216)",
     "the object row prints code 020000 (extra leading zero) instead of 20000; kept as "
     "printed and classified by its object name; the aktiviti and program sums reconcile"),
    ("lampiran1 coded program-level object row (B.23 program 160000, pdf 142; image-verified)",
     "the program-level object summary row prints WITH its object code ('20000 "
     "Perkhidmatan dan Bekalan') instead of the uncoded form; classified object_program "
     "by position (follows Jumlah 160100)"),
    ("timeseries Jumlah Bayaran Balik Luar Negeri 2017 (pdf 278)",
     "panel prints Jumlah Bayaran Balik Luar Negeri 2017 = '–' while its own component "
     "Pinjaman Projek prints 404, and Jumlah Bayaran Balik 2017 = 88,453 repeats the DN "
     "figure (LN 404 dropped from both totals; cash statement BLN bayaran 404,570,236 "
     "confirms the 404 is real) — print typo in the panel's 2017 column, kept as printed "
     "(the corresponding FAIL above is this diagnosis)"),
    ("lampiran1 omitted program header (B.06 program 530000, pdf 102-103)",
     "aktiviti 530100/530200/530300 and the closing 'Jumlah 530000' print WITHOUT a "
     "'530000 <name>' program header line; program code inferred from the aktiviti prefix "
     "and flagged (program_name_bm empty)"),
    ("lampiran2 blank terkumpul-prior cells (P.22 projek 00700 pdf 225, P.29 projek 95000 pdf 237)",
     "the Perbelanjaan Sebenar RMKe-11 Hingga 31.12.2016 cell prints BLANK (not even a dash) "
     "for P.22 00700 PPP/PFI and P.29 95000 NRW Nasional; stored 0.0 and flagged; the rows' "
     "terkumpul identities hold with nil prior (both projects started spending in 2017)"),
    ("lampiran2 duplicate vote-name JUMLAH (P.24, pdf 231)",
     "P.24 prints 'JUMLAH KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI' twice: the "
     "first (kos 2,212,420,444) closes the ministry-proper block, the second "
     "(kos 7,920,349,084) is the vote total; the first is stored as program_subtotal"),
    ("lampiran2 abbreviated vote-total label (P.25, pdf 231)",
     "the P.25 vote total prints 'JUMLAH KEM. PERDAGANGAN DALAM NEGERI, KOPERASI & "
     "KEPENGGUNAAN' (KEMENTERIAN abbreviated to KEM.); label kept as printed"),
    ("lampiran6 blank Luar Negeri cells (Sentuhan Budiman; SSER, pdf 272)",
     "two Jaminan Berkanun rows print a BLANK Luar Negeri cell (not even a dash); "
     "Dalam Negeri equals Jumlah on both rows so the omitted cell is nil; stored 0.0"),
    ("cash statement Hasil vs Nota 5(a) differences (printed, explained in Nota 8)",
     "cash-basis Hasil Bukan Cukai (39,505,138,495) and Terimaan Bukan Hasil "
     "(1,743,795,825) differ from Nota 5(a) by 15,082,389 and 232,707,113 (deposit-account "
     "adjustments); Pemberian differs by 1,339,810,349 and Perbelanjaan Lain by 25,000,000; "
     "all figures as printed, reconciliation captured in fact_other_notes"),
    ("nota 5(b) wrapped B.12 sebenar (pdf 63)",
     "B.12 Peruntukan kepada Kumpulan Wang Terkanun prints '**' at line end with the sebenar "
     "amount 4,467,209,216 wrapped to the following line; captured with has_footnote=True "
     "(the ** footnote: includes the RM2,710,809,216 caruman to Kumpulan Wang Pembangunan)"),
    ("register absences in the 2017 volume (6 lampiran only)",
     "no Komitmen Jaminan register (fact_guarantees), no Komitmen Pajakan Kewangan register "
     "(fact_finance_leases), no PFI tranche register, no Penyata Penyaluran Geran, no "
     "Komitmen Pampasan register; the 2017 volume reports NO commitments and NO PFI "
     "liability anywhere (they first appear in the 2018 volume); fact_commitment_detail "
     "carries only the Nota 10(b) Pelbagai Liabiliti split"),
    ("memorandum statement prints no Jumlah rows (pdf 58)",
     "the 2017 Penyata Akaun Memorandum prints only 4 lines (PPBD, Pelaburan, Hutang "
     "Persekutuan, Pelbagai Liabiliti) with no Akaun Belum Terima line and no Jumlah "
     "Aset/Liabiliti rows; fact_memorandum therefore has 8 rows"),
    ("glyph overprints repaired (text layer only)",
     "trailing '-' glued to amounts (Nota 6/7 pages, e.g. '27,232,066,897-'), 'Nombor' "
     "watermark word inside the DBKL row (pdf 254), doubled title glyphs "
     "('KEDUDUKANKEWANGAN'), kerned 'P . 2 7' maksud headers and split leading digits in "
     "Lampiran 2 number cells; all are text-layer artifacts repaired against the printed "
     "page, never value changes"),
]

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
with open(f"{WH}/_validation_checks_2017.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
    for name, diag in DIAGNOSES:
        cw.writerow(["DIAGNOSIS", f"core: {name}: {diag}", "", "", ""])
