#!/usr/bin/env python3
"""Programmatic validation: extracted line items must reproduce printed totals.
Never corrects — only reports PASS/FAIL with amounts."""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse"
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the PDF statements) ----
# Penyata Kedudukan Kewangan p73
WANG_AWAM = {2024: 65_943_130_080, 2023: 69_765_961_233}
# Penyata Prestasi Kewangan p76
HASIL = {2024: 324_617_649_248, 2023: 314_959_481_731}
OPEX_PRESTASI = {2024: 321_508_948_391, 2023: 311_266_917_827}
DEVEX = {2024: 84_011_595_464, 2023: 96_089_737_123}
KURANGAN = {2024: -80_902_894_607, 2023: -92_397_173_219}
# Cash statement p74-75
JUM_TERIMAAN = {2024: 527_223_260_730, 2023: 549_806_589_483}
JUM_BAYARAN = {2024: 526_633_948_837, 2023: 570_702_473_172}
TUNAI_AKHIR = {2024: 28_196_329_803, 2023: 27_607_017_910}
# Nota 5(b) p85
TANGGUNGAN = 91_843_662_273
BEKALAN = 232_773_986_975
OPEX_NOTA_TOTAL = 324_617_649_248  # includes transfer to KW Pembangunan
# Nota 10 p93
HUTANG = {2024: 1_247_613_545_373, 2023: 1_172_509_451_502}
PINJ_DN = {2024: 1_219_637_729_000, 2023: 1_142_657_729_000}
# Nota 7 p87
AMANAH_AKHIR = {2024: 54_080_002_994, 2023: 57_754_188_413}
# Lampiran 2 grand total (sen precision)
DEVEX_L2 = 84_011_595_463.78

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2024, 2023):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2024, 2023):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex=kurangan {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")] - g[("devex", yr, "sebenar")]
          - g.get(("covid_fund_exp", yr, "sebenar"), 0.0),
          KURANGAN[yr])
    check(f"perf: pembiayaan = kurangan {yr}", g[("total_financing", yr, "sebenar")], -KURANGAN[yr])

# ---- 3. revenue ----
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
    # L2 within HASIL CUKAI
    for l2 in ["Cukai Langsung", "Cukai Tidak Langsung"]:
        l2v = next(F(r, col) for r in rv if r["level"] == "2" and r["item_bm"] == l2)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l2_bm"] == l2)
        check(f"rev[{col}]: sum(items) = {l2}", l3, l2v)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2024])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Bekalan", b, BEKALAN)
check("opex: T+B = printed Perbelanjaan Mengurus (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check("opex: count of maksud = 53", len(ox), 53)

# ---- 5. devex by maksud ----
dx = load("fact_devex_maksud.csv")
mins = [r for r in dx if r["maksud_code"] != "TOTAL"]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm", "terkumpul_rmke12_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col))
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2024], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + (F(r, "sebenar_pinjaman_rm"))
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2024, 2023):
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
# closing cash = financial position Wang Tunai
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2024")
check("cross: cash closing 2024 = position Wang Tunai", TUNAI_AKHIR[2024], pos_tunai)

# ---- 7. debt ----
db = load("fact_debt.csv")
for yr in (2024, 2023):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed", dn, PINJ_DN[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG PERSEKUTUAN" and int(r["year"]) == yr)
    check(f"debt: Hutang Persekutuan {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+LN+BLN = Hutang {yr}", dn + ln_ + bln, HUTANG[yr])
# memorandum cross-check
mm = load("fact_memorandum.csv")
for yr in (2024, 2023):
    hm = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Hutang Persekutuan" and int(r["year"]) == yr)
    check(f"cross: memo Hutang = debt Hutang {yr}", hm, HUTANG[yr])
    ja = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Jumlah Aset" and int(r["year"]) == yr)
    parts = sum(F(r, "amount_rm") for r in mm if r["line_item_bm"] in ("Akaun Belum Terima", "Pelaburan") and int(r["year"]) == yr)
    check(f"memo: aset parts = Jumlah Aset {yr}", parts, ja)
    jl = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Jumlah Liabiliti" and int(r["year"]) == yr)
    lparts = sum(F(r, "amount_rm") for r in mm
                 if r["line_item_bm"] in ("Hutang Persekutuan", "Liabiliti Inisiatif Pembiayaan Swasta",
                                          "Komitmen Kewangan", "Pelbagai Liabiliti") and int(r["year"]) == yr)
    check(f"memo: liabiliti parts = Jumlah Liabiliti {yr}", lparts, jl)

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
check("cross: trust closing = position Akaun Amanah 2024", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2024"))

# ---- 9. post-verifier additions ----
# financing components must sum to JUMLAH PEMBIAYAAN
for yr in (2024, 2023):
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components sum = Jumlah Pembiayaan {yr}", fin, -KURANGAN[yr])
# commitment components must sum to memo Komitmen Kewangan
KOMITMEN = {2024: 297_164_856_524, 2023: 285_633_903_408}
for yr in (2024, 2023):
    kc = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_total" and int(r["year"]) == yr)
    check(f"debt: 4 commitment totals sum = memo Komitmen Kewangan {yr}", kc, KOMITMEN[yr])
# PFI companies sum to PFI total; PFI total = memo line
PFI = {2024: 32_905_600_585, 2023: 33_470_600_585}
for yr in (2024, 2023):
    pfi_t = next(F(r, "amount_rm") for r in db if r["kind"] == "pfi_total" and int(r["year"]) == yr)
    pfi_c = sum(F(r, "amount_rm") for r in db if r["kind"] == "pfi_company" and int(r["year"]) == yr)
    check(f"debt: PFI companies sum = PFI total {yr}", pfi_c, pfi_t)
    check(f"debt: PFI total = printed {yr}", pfi_t, PFI[yr])
# pampasan items sum to KOMITMEN PAMPASAN
PAMPASAN = {2024: 934_389_799, 2023: 1_415_747_031}
for yr in (2024, 2023):
    pit = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_item" and int(r["year"]) == yr)
    check(f"debt: pampasan items sum = printed {yr}", pit, PAMPASAN[yr])
# debt subtotals
for yr in (2024, 2023):
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
# misc liabilities matches memo
for yr in (2024, 2023):
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)

# ---- 10. detail-layer tables ----
od = load("fact_opex_detail.csv")
for col, notacol in [("sebenar_rm", "sebenar_rm"), ("anggaran_asal_rm", "anggaran_asal_rm")]:
    leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            leaf[r["maksud_code"]] += F(r, col)
    okc = 0
    for r in ox:
        if abs(leaf[r["maksud_code"]] - F(r, notacol)) < 1:
            okc += 1
    check(f"opex_detail[{col}]: maksud leaf sums = Nota 5(b) (53 maksud)", okc, 53)
jb = [r for r in od if r["row_type"] == "jumlah_besar"]
check("opex_detail: grand total sebenar = Nota total", F(jb[0], "sebenar_rm"), OPEX_NOTA_TOTAL, tol=0.5)

dp = load("fact_devex_project.csv")
projsum = defaultdict(float)
for r in dp:
    if r["row_type"] == "project":
        projsum[r["maksud_code"]] += F(r, "sebenar_jumlah_rm")
okc = 0
for r in dx:
    if r["maksud_code"] != "TOTAL" and abs(projsum[r["maksud_code"]] - F(r, "sebenar_jumlah_rm")) < 1:
        okc += 1
check("devex_project: project sums = ministry totals (31 ministries)", okc, 31)
gt = next(r for r in dp if r["row_type"] == "grand_total")
check("devex_project: grand total = printed (sen)", F(gt, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
idfail = 0
for r in dp:
    if r["row_type"] == "project":
        if abs(F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm") - F(r, "sebenar_jumlah_rm")) > 1:
            idfail += 1
        if abs(F(r, "terkumpul_rmke12_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke12_rm")) > 1:
            idfail += 1
check("devex_project: per-project identities (0 failures)", idfail, 0)

ts = load("fact_timeseries_2010_2024.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
# 2024 column must match warehouse facts (RM juta, printed panel is rounded)
panel24 = [
    ("Hasil", "Jumlah Hasil", HASIL[2024]),
    ("Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", OPEX_NOTA_TOTAL),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2024]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2024]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2024]),
]
for sec, item, rm in panel24:
    got = tv.get((sec, item, 2024))
    check(f"timeseries: {item} 2024 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2010-2024 (15 years)", len(years), 15)

# ---- 11. Nota 5 statement table ----
ras = load("fact_revenue_account_statement.csv")
g5 = {(r["line_item_bm"], int(r["year"])): F(r, "sebenar_rm") for r in ras}
for yr in (2024, 2023):
    comp = sum(g5[(k, yr)] for k in ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"])
    check(f"nota5stmt: hasil components sum {yr}", comp, g5[("HASIL", yr)])
    obj = sum(g5[(k, yr)] for k in ["Emolumen", "Perkhidmatan dan Bekalan", "Aset",
                                    "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"])
    check(f"nota5stmt: opex object components sum {yr}", obj, g5[("PERBELANJAAN MENGURUS", yr)])
    check(f"nota5stmt: opex + transfer = jumlah selepas pindahan {yr}",
          g5[("PERBELANJAAN MENGURUS", yr)] + g5[("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", yr)],
          g5[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)])
    check(f"nota5stmt: hasil = perf revenue {yr}", g5[("HASIL", yr)], HASIL[yr])
    check(f"nota5stmt: opex = perf opex (before transfer) {yr}", g5[("PERBELANJAAN MENGURUS", yr)], OPEX_PRESTASI[yr])
    check(f"nota5stmt: baki roll-forward {yr}",
          g5[("BAKI PADA 1 JANUARI", yr)] + g5[("HASIL", yr)]
          - g5[("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr)],
          g5[("BAKI PADA 31 DISEMBER", yr)])

# ---- 12. devex program linkage ----
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
check("devex: verified program-linkage groups >= 40", 1 if okp >= 40 else 0, 1)

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
with open(f"{WH}/_validation_checks.csv", "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["status", "check", "extracted_value", "printed_value", "difference"])
    cw.writerows(results)
