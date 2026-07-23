#!/usr/bin/env python3
"""Programmatic validation for the 2018 warehouse: extracted line items must
reproduce printed totals. Never corrects — only reports PASS/FAIL with amounts.
All reference figures are typed from the 2018 volume's own printed statements."""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse2018"
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2018 volume) ----
# Penyata Kedudukan Kewangan pdf 57
WANG_AWAM = {2018: 52_910_057_045, 2017: 42_184_431_834}
# Penyata Prestasi Kewangan pdf 60
HASIL = {2018: 232_882_562_288, 2017: 220_406_001_884}
OPEX_PRESTASI = {2018: 230_960_492_668, 2017: 217_695_192_668}
DEVEX = {2018: 56_095_455_662, 2017: 44_883_838_833}
KURANGAN = {2018: -54_173_386_042, 2017: -42_173_029_617}
# Cash statement pdf 58-59 (cash-basis HASIL differs from Nota 5(a); Nota 8 explains)
JUM_TERIMAAN = {2018: 382_901_357_462, 2017: 362_943_563_718}
JUM_BAYARAN = {2018: 377_317_886_056, 2017: 360_942_896_952}
TUNAI_AKHIR = {2018: 23_647_599_864, 2017: 18_064_128_458}
# Nota 5(b) pdf 66
TANGGUNGAN = 60_531_705_893
BEKALAN = 172_350_856_395
OPEX_NOTA_TOTAL = 232_882_562_288  # includes transfer to KW Pembangunan (inside B.12)
N_MAKSUD = 52
# Nota 10 pdf 73
HUTANG = {2018: 741_048_714_484, 2017: 686_836_648_477}
PINJ_DN = {2018: 719_545_169_000, 2017: 665_571_726_000}
# Nota 7 pdf 68
AMANAH_AKHIR = {2018: 25_822_806_810, 2017: -3_161_093_193}
# Lampiran 1 grand total (sen precision, pdf 216)
OPEX_L1 = 232_882_562_287.80
# Lampiran 2 grand total (sen precision, pdf 252-253)
DEVEX_L2 = 56_095_455_661.74
N_MINISTRIES_L2 = 29

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2018, 2017):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2018, 2017):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex=kurangan {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")] - g[("devex", yr, "sebenar")],
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
        if l1 == "HASIL CUKAI":
            sub = sum(F(r, col) for r in rv if r["level"] == "2")
            check(f"rev[{col}]: sum(L2) = HASIL CUKAI", sub, l1v)
        else:
            l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l1_bm"] == l1)
            check(f"rev[{col}]: sum(items) = {l1}", l3, l1v)
    for l2 in ["Cukai Langsung", "Cukai Tak Langsung"]:
        l2v = next(F(r, col) for r in rv if r["level"] == "2" and r["item_bm"] == l2)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l2_bm"] == l2)
        check(f"rev[{col}]: sum(items) = {l2}", l3, l2v)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2018])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Bekalan", b, BEKALAN)
check("opex: T+B = printed Perbelanjaan Mengurus (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)
for col, want_t, want_b in [("anggaran_asal_rm", 61_320_776_900, 172_929_672_100),
                            ("anggaran_dipinda_rm", 61_320_776_900, 171_120_413_380)]:
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
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2018], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm")
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)
    check(f"devex row: prior+sebenar=terkumpul RMKe-11 [{r['maksud_code']}]",
          F(r, "terkumpul_rmke11_prior_rm") + F(r, "sebenar_jumlah_rm"),
          F(r, "terkumpul_rmke11_rm"), tol=0.02)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2018, 2017):
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
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2018")
check("cross: cash closing 2018 = position Wang Tunai", TUNAI_AKHIR[2018], pos_tunai)
# 2018 cash-basis Hasil differs from Nota 5(a) by the Nota 8 reconciliation items
cash_hasil = sum(F(r, "amount_rm") for r in cs if r["category_bm"] == "Hasil" and int(r["year"]) == 2018)
check("cash: Hasil (cash) + Nota 8 differences = Nota 5(a) HASIL",
      cash_hasil + 12_178_052 + 176_047_149, HASIL[2018])

# ---- 7. debt ----
db = load("fact_debt.csv")
for yr in (2018, 2017):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed", dn, PINJ_DN[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG PERSEKUTUAN" and int(r["year"]) == yr)
    check(f"debt: Hutang Persekutuan {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+LN+BLN = Hutang {yr}", dn + ln_ + bln, HUTANG[yr])
mm = load("fact_memorandum.csv")
for yr in (2018, 2017):
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
check("trust: closing = printed Nota 7 total 2018", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2018])
check("trust: opening = printed Nota 7 total 2017", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2017])
check("cross: trust closing = position Akaun Amanah 2018", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2018"))

# ---- 9. financing / commitments / PFI / pampasan ----
for yr in (2018, 2017):
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components sum = Jumlah Pembiayaan {yr}", fin, -KURANGAN[yr])
KOMITMEN = {2018: 242_968_745_211, 2017: 214_269_652_456}  # memo pdf 61
for yr in (2018, 2017):
    kc = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_total" and int(r["year"]) == yr)
    check(f"debt: 4 commitment totals sum = memo Komitmen Kewangan {yr}", kc, KOMITMEN[yr])
PFI = {2018: 36_416_442_980, 2017: 35_462_452_983}  # Nota 10(b) pdf 73
for yr in (2018, 2017):
    pfi_t = next(F(r, "amount_rm") for r in db if r["kind"] == "pfi_total" and int(r["year"]) == yr)
    pfi_c = sum(F(r, "amount_rm") for r in db if r["kind"] == "pfi_component" and int(r["year"]) == yr)
    check(f"debt: PFI items sum = PFI total {yr}", pfi_c, pfi_t)
    check(f"debt: PFI total = printed {yr}", pfi_t, PFI[yr])
PAMPASAN = {2018: 2_169_792_773, 2017: 6_839_313_755}  # Nota 10(c)(iv) pdf 74
for yr in (2018, 2017):
    pit = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_item" and int(r["year"]) == yr)
    check(f"debt: pampasan items sum = printed {yr}", pit, PAMPASAN[yr])
for yr in (2018, 2017):
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
for yr in (2018, 2017):
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)

# ---- 10. Lampiran 1 detail (4 printed value columns) ----
od = load("fact_opex_detail.csv")
for col in ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]:
    leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            leaf[r["maksud_code"]] += F(r, col)
    if col in ("anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"):
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
    check(f"opex_detail[{col}]: aktiviti leaf sums = printed Jumlah aktiviti (bad groups)", bad, 1)
    prog_leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = sum(1 for k, v in jp.items() if abs(prog_leaf.get(k, 0.0) - v) >= 1)
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program (bad groups)", badp, 0)
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
# empty 7-column-era fields stay empty in the 4-column 2018 volume
for col in ("anggaran_tambahan_rm", "viremen_rm", "varian_rm"):
    nonempty = sum(1 for r in od if r[col] not in ("", "None"))
    check(f"opex_detail[{col}]: not printed in the 2018 4-column layout (populated rows)", nonempty, 0)

# ---- 11. devex project ----
dp = load("fact_devex_project.csv")
projsum = defaultdict(float)
for r in dp:
    if r["row_type"] == "project":
        projsum[r["maksud_code"]] += F(r, "sebenar_jumlah_rm")
okc = 0
for r in dx:
    if r["maksud_code"] != "TOTAL" and abs(projsum[r["maksud_code"]] - F(r, "sebenar_jumlah_rm")) < 1:
        okc += 1
check(f"devex_project: project sums = ministry totals ({N_MINISTRIES_L2} ministries)", okc, N_MINISTRIES_L2)
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
        # RMKe-11 mid-plan: cumulative-to-31.12.2018 = cumulative-to-31.12.2017 + 2018 actual
        if abs(F(r, "terkumpul_rmke11_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke11_rm")) > 0.011:
            idfail += 1
check("devex_project: per-project identities (0 failures; RMKe-11 mid-plan: prior+sebenar==terkumpul)", idfail, 0)

# ---- 12. timeseries ----
ts = load("fact_timeseries_2009_2018.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2009-2018 (10 years)", len(years), 10)
check("timeseries: min year 2009", years[0], 2009)
check("timeseries: max year 2018", years[-1], 2018)
panel18 = [
    ("Hasil", "Jumlah Hasil", HASIL[2018]),
    ("Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", OPEX_PRESTASI[2018]),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2018]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2018]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2018]),
]
for sec, item, rm in panel18:
    got = tv.get((sec, item, 2018))
    check(f"timeseries: {item} 2018 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
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
for yr in (2018, 2017):
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
check("nota5stmt: Akaun Hasil balance fixed at 11,863,127,086 since 1996",
      g5[("BAKI PADA 31 DISEMBER", 2018)], 11_863_127_086)

# ---- 14. Nota 6 loan account statement ----
la = load("fact_loan_account_statement.csv")
g6 = {(r["group_bm"], r["sub_bm"], r["line_item_bm"], int(r["year"])): F(r, "amount_rm") for r in la}
for yr in (2018, 2017):
    closing = next(F(r, "amount_rm") for r in la if r["row_type"] == "closing" and int(r["year"]) == yr)
    pos = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN PINJAMAN DISATUKAN" and int(r["year"]) == yr)
    check(f"cross: Nota 6 closing = position Akaun Pinjaman {yr}", closing, pos)

# ---- 15. devex program linkage ----
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

# ---- 16. trust fund detail cross to Nota 7 top table ----
tfd = load("fact_trust_fund_detail.csv")
kwp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
                 and r["row_type"] == "closing" and r["year"] == "2018")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2018")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(ii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2018")
kaw_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Kumpulan Wang Amanah Am", "Kumpulan Wang Amanah Khas"))
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2018")
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
check("lampiran1: jumlah_aktiviti rows not matching their own leaf sum (all diagnosed as printed code typos)",
      sum(1 for a in anomalies if not a[4]), 0)
for mk, pg, lbl, val, cands in anomalies:
    if cands:
        print(f"   printed-typo diagnosis: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f} "
              f"matches aktiviti {cands} leaf sum — printed code typo in the volume")
    else:
        print(f"   UNRESOLVED jumlah_aktiviti mismatch: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f}")

# ---- print-discrepancy diagnoses (proven from the volume's own pages) ----
DIAGNOSES = [
    ("lampiran1 'Jumlah 050400' printed code typo (B.06 aktiviti 060400, pdf 98)",
     "the row closing aktiviti 060400 (Jabatan Agama Islam Wilayah Persekutuan) prints "
     "'Jumlah 050400' — its values 119,001,300 / 120,955,100 / 101,188,288.50 equal the "
     "060400 object rows' sums exactly; kept as printed (aktiviti_code follows the label)"),
    ("lampiran1 prestasi% printed typos (8 cells, verified against page images)",
     "B.10 030600 Emolumen prints 95.80 (arith. 96.43) and P&B 99.90 (arith. 84.83); "
     "B.10 030700 Emolumen prints 95.80 (arith. 94.80) and P&B 99.90 (arith. 90.51) [pdf 110]; "
     "B.31 020600 Aset prints 99.99 (arith. 81.08) [pdf 164]; B.32 070200 P&B prints 99.99 "
     "(arith. 97.34) [pdf 169]; B.42 012700 Pemberian prints 99.99 vs nil sebenar [pdf 173]; "
     "B.45 'Jumlah 070100' prints 99.99 (arith. 99.11) [pdf 184]; B.63 020400 P&B prints "
     "99.99 (arith. 89.67) [pdf 208]. All RM columns verified by group sums; % kept as printed"),
    ("lampiran2 blank Kos Keseluruhan cell (P.06 projek 95000, pdf 220)",
     "the Kos Keseluruhan cell of projek *95000 Halal Industry Development Corporation is "
     "printed BLANK (not even a dash); stored 0.0 and flagged; the row's other columns "
     "reconcile (terkumpul identity holds)"),
    ("lampiran2 duplicate vote-name JUMLAH (P.24, pdf 232)",
     "P.24 prints 'JUMLAH KEMENTERIAN PERDAGANGAN ANTARABANGSA DAN INDUSTRI' twice: the "
     "first (kos 2,212,869,449) closes the ministry-proper block, the second "
     "(kos 8,040,371,189) is the vote total; the first is stored as program_subtotal"),
    ("cash statement Hasil vs Nota 5(a) difference (printed, explained in Nota 8)",
     "cash-basis Hasil Bukan Cukai (51,106,244,812) and Terimaan Bukan Hasil "
     "(6,036,758,532) differ from Nota 5(a) by 12,178,052 and 176,047,149 (deposit-account "
     "adjustments); both figures as printed, reconciliation captured in fact_other_notes"),
    ("timeseries Jumlah Bayaran Balik 2017 (pdf 289)",
     "panel prints Jumlah Bayaran Balik 2017 = 88,453 while its own components print "
     "Jumlah Bayaran Balik Dalam Negeri 88,453 + Jumlah Bayaran Balik Luar Negeri 404 "
     "= 88,857: the grand-total cell repeats the DN figure, dropping the LN 404 — a "
     "print typo in the panel's 2017 column, kept as printed (the corresponding FAIL "
     "above is this diagnosis)"),
    ("timeseries Hasil split 2018 column (pdf 289)",
     "the panel's 2018 column prints Cukai Langsung 112,426 / Cukai Tidak Langsung 61,634 "
     "(RM juta) — the CTL cell repeats the 2017 value and CL is forced to fit the total; "
     "the volume's own Nota 5(a) prints 130,035 / 44,026 (GST-to-SST transition year) and "
     "the 2019 volume's panel prints the corrected split; kept as printed"),
    ("register absences in the 2018 volume (8 lampiran only)",
     "no PFI tranche register (fact_pfi_liabilities), no Penyata Penyaluran Geran "
     "(fact_guarantee_repayment_grants), no Komitmen Pampasan register "
     "(fact_compensation_commitments); their Nota 10 summary splits are captured in "
     "fact_debt / fact_commitment_detail"),
]

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
with open(f"{WH}/_validation_checks_2018.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
    for name, diag in DIAGNOSES:
        cw.writerow(["DIAGNOSIS", f"core: {name}: {diag}", "", "", ""])
