#!/usr/bin/env python3
"""Programmatic validation for the 2016 warehouse: extracted line items must
reproduce printed totals. Never corrects — only reports PASS/FAIL with amounts.
All reference figures are typed from the 2016 volume's own printed statements."""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse2016"
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2016 volume) ----
# Penyata Kedudukan Kewangan pdf 56
WANG_AWAM = {2016: 39_373_333_718, 2015: 48_726_920_651}
# Penyata Prestasi Kewangan pdf 59
HASIL = {2016: 212_421_098_894, 2015: 219_088_760_826}
OPEX_PRESTASI = {2016: 210_172_661_334, 2015: 216_997_528_507}
DEVEX = {2016: 41_995_037_697, 2015: 40_767_711_667}
KURANGAN = {2016: -39_746_600_137, 2015: -38_676_479_348}
# Cash statement pdf 57-58
JUM_TERIMAAN = {2016: 316_011_224_041, 2015: 342_170_005_509}
JUM_BAYARAN = {2016: 322_920_310_464, 2015: 336_624_128_466}
TUNAI_AKHIR = {2016: 16_063_461_692, 2015: 22_972_548_115}
# printed cash category totals (typed from pdf 57-58)
CASH_CAT = {
    ("TERIMAAN", "Hasil"): {2016: 212_018_590_443, 2015: 219_088_255_295},
    ("TERIMAAN", "Pinjaman"): {2016: 99_713_518_592, 2015: 121_107_483_979},
    ("TERIMAAN", "Bantuan Luar Negeri"): {2016: 145_355_562, 2015: 256_238_110},
    ("TERIMAAN", "Terimaan Modal"): {2016: 3_891_080_081, 2015: 1_029_832_780},
    ("TERIMAAN", "Terimaan Amanah"): {2016: 242_679_363, 2015: 688_195_345},
    ("BAYARAN", "Perbelanjaan Mengurus"): {2016: 208_381_449_771, 2015: 215_044_511_316},
    ("BAYARAN", "Perbelanjaan Pembangunan"): {2016: 41_995_037_697, 2015: 40_767_711_667},
    ("BAYARAN", "Pinjaman"): {2016: 60_864_246_424, 2015: 77_208_110_445},
    ("BAYARAN", "Bantuan Luar Negeri"): {2016: 477_218_831, 2015: 410_164_536},
    ("BAYARAN", "Perbelanjaan Modal"): {2016: 0, 2015: 1_864_888_405},
    ("BAYARAN", "Perbelanjaan Amanah"): {2016: 11_202_357_741, 2015: 1_328_742_097},
}
# Nota 5(b) pdf 65
TANGGUNGAN = 52_401_054_410
BEKALAN = 160_020_044_484
OPEX_NOTA_TOTAL = 212_421_098_894  # incl. transfer to KWP (inside B.12)
N_MAKSUD = 50
# Nota 9 pdf 71
HUTANG = {2016: 648_475_304_686, 2015: 630_540_436_110}
PINJ_DN = {2016: 624_821_726_000, 2015: 609_062_879_000}
# Nota 7 pdf 67
AMANAH_AKHIR = {2016: 7_186_447_384, 2015: 8_478_184_431}
# Lampiran 1 grand total (sen precision, pdf 223)
OPEX_L1 = 212_421_098_894.35
# Lampiran 2 grand total (sen precision, pdf 255-256)
DEVEX_L2 = 41_995_037_696.86
N_MINISTRIES_L2 = 27

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2016, 2015):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2016, 2015):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex=kurangan {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")] - g[("devex", yr, "sebenar")],
          KURANGAN[yr])
    check(f"perf: pembiayaan = kurangan {yr}", g[("total_financing", yr, "sebenar")], -KURANGAN[yr])
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components sum = Jumlah Pembiayaan {yr}", fin, -KURANGAN[yr])
check("perf: anggaran identity hasil-opex = lebihan 2016",
      g[("revenue", 2016, "anggaran")] - g[("opex", 2016, "anggaran")], g[("current_balance", 2016, "anggaran")])
check("perf: anggaran identity lebihan-devex = kurangan 2016",
      g[("current_balance", 2016, "anggaran")] - g[("devex", 2016, "anggaran")],
      g[("overall_deficit", 2016, "anggaran")])

# ---- 3. revenue (2016: NO Cukai Langsung/Tak Langsung L2 tier) ----
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
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2016])
check("rev: HASIL sebenar prior = perf Hasil 2015",
      next(F(r, "sebenar_prior_rm") for r in rv if r["level"] == "0"), HASIL[2015])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Jumlah Perbelanjaan Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Jumlah Perbelanjaan Bekalan", b, BEKALAN)
check("opex: T+B = printed JUMLAH PERBELANJAAN MENGURUS (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)
for col, want_t, want_b in [("anggaran_asal_rm", 51_776_244_000, 163_447_756_000),
                            ("anggaran_dipinda_rm", 53_222_698_048, 159_077_855_000)]:
    check(f"opex[{col}]: sum(T.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("T.")), want_t)
    check(f"opex[{col}]: sum(B.*) = printed jenis subtotal",
          sum(F(r, col) for r in ox if r["maksud_code"].startswith("B.")), want_b)

# ---- 5. devex by maksud (RMKe-11 year 1) ----
dx = load("fact_devex_maksud.csv")
mins = [r for r in dx if r["maksud_code"] != "TOTAL"]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm",
            "terkumpul_rmke10_prior_rm", "terkumpul_rmke11_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col), tol=0.02)
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2016], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm")
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)
    # RMKe-11 year 1: cumulative-to-31.12.2016 = the 2016 actual itself
    check(f"devex row: terkumpul RMKe-11 = sebenar 2016 (plan year 1) [{r['maksud_code']}]",
          F(r, "terkumpul_rmke11_rm"), F(r, "sebenar_jumlah_rm"), tol=0.011)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2016, 2015):
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
    for (flow, cat), wants in CASH_CAT.items():
        got = sum(F(r, "amount_rm") for r in cs if r["flow"] == flow and r["category_bm"] == cat and int(r["year"]) == yr)
        check(f"cash: {flow}/{cat} items sum = printed category total {yr}", got, wants[yr])
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2016")
check("cross: cash closing 2016 = position Wang Tunai", TUNAI_AKHIR[2016], pos_tunai)
# cash-basis Hasil differs from Nota 5(a) by the printed Nota 5 reconciliation items
cash_hasil = sum(F(r, "amount_rm") for r in cs if r["category_bm"] == "Hasil" and int(r["year"]) == 2016)
check("cash: Hasil (cash) + Nota 5(a) differences = Nota 5(a) JUMLAH HASIL",
      cash_hasil + 203_392_339 + 199_116_112, HASIL[2016])

# ---- 7. debt ----
db = load("fact_debt.csv")
mm = load("fact_memorandum.csv")
for yr in (2016, 2015):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed DN subtotal", dn, PINJ_DN[yr])
    dn_sub = next(F(r, "amount_rm") for r in db if r["item_bm"] == "Dalam Negeri" and r["kind"] == "subtotal" and int(r["year"]) == yr)
    check(f"debt: captured DN subtotal row {yr}", dn_sub, PINJ_DN[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG PERSEKUTUAN" and int(r["year"]) == yr)
    check(f"debt: Hutang Persekutuan {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+LN+BLN = Hutang {yr}", dn + ln_ + bln, HUTANG[yr])
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
    check(f"debt: DN subtotal + Pinjaman Pasaran = PINJAMAN {yr}", dn_sub + ln_, pj)
    hm = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Hutang Persekutuan" and int(r["year"]) == yr)
    check(f"cross: memo Hutang = debt Hutang {yr}", hm, HUTANG[yr])
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)
# memorandum aset cross-checks (2016 statement has no Jumlah rows)
for yr, ppbd, pel in ((2016, 55_813_494_515, 30_926_284_939), (2015, 106_821_651_022, 30_316_159_989)):
    got = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pinjaman dan Pendahuluan Boleh Dituntut" and int(r["year"]) == yr)
    check(f"memo: PPBD {yr} = printed", got, ppbd)
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
check("trust: closing = printed Nota 7 total 2016", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2016])
check("trust: opening = printed Nota 7 total 2015", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2015])
check("cross: trust closing = position Akaun Amanah 2016", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2016"))
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
    check(f"opex_detail[{col}]: aktiviti leaf sums = printed Jumlah aktiviti (bad groups)", bad, 0)
    prog_leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = sum(1 for k, v in jp.items() if abs(prog_leaf.get(k, 0.0) - v) >= 1)
    # anggaran_asal: 1 diagnosed printed typo (B.10 Jumlah 090000 asal prints
    # 288,084,900 while its own printed component rows sum to 292,184,900 —
    # the 090500 'Bayaran Balik Hasil' 4,100,000 is dropped from the total cell;
    # verified on the pdf 122 page image; kept as printed)
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program (bad groups)",
          badp, 1 if col == "anggaran_asal_rm" else 0)
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
    check(f"opex_detail[{col}]: not printed in the 2016 4-column layout (populated rows)", nonempty, 0)

# ---- 10. devex project ----
dp = load("fact_devex_project.csv")
for col in ["kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm", "anggaran_langsung_rm",
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
        # RMKe-11 year 1: cumulative-to-31.12.2016 = the 2016 actual itself
        if abs(F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke11_rm")) > 0.011:
            idfail += 1
check("devex_project: per-project identities (0 failures; RMKe-11 year 1: terkumpul==sebenar)", idfail, 0)

# ---- 11. timeseries ----
ts = load("fact_timeseries_2007_2016.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2007-2016 (10 years)", len(years), 10)
check("timeseries: min year 2007", years[0], 2007)
check("timeseries: max year 2016", years[-1], 2016)
panel16 = [
    ("Hasil", "Jumlah Hasil", HASIL[2016]),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2016]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2016]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2016]),
    ("Pinjaman Boleh Dituntut", "Jumlah Pinjaman Boleh Dituntut", 55_813_494_515),
]
for sec, item, rm in panel16:
    got = tv.get((sec, item, 2016))
    check(f"timeseries: {item} 2016 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
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
    check(f"timeseries roll [{sec}] opening=prior closing (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   roll detail {sec}: {bad_years}")

# ---- 12. Nota 5 statement table ----
ras = load("fact_revenue_account_statement.csv")
g5 = {(r["line_item_bm"], int(r["year"])): F(r, "sebenar_rm") for r in ras}
for yr in (2016, 2015):
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
      g5[("BAKI PADA 31 DISEMBER", 2016)], 11_863_127_086)

# ---- 13. Nota 6 loan account statement ----
la = load("fact_loan_account_statement.csv")
for yr in (2016, 2015):
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
                 and r["row_type"] == "closing" and r["year"] == "2016")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2016")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(ii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2016")
kaw_top = next(F(r, "baki_akhir_rm") for r in tr
               if r["parent_group_bm"] == "" and r["account_bm"] == "KUMPULAN WANG AMANAH AWAM")
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2016")
dep_top = next(F(r, "baki_akhir_rm") for r in tr
               if r["parent_group_bm"] == "" and r["account_bm"] == "AKAUN DEPOSIT")
check("cross: Nota7(c) total = Nota 7 table Deposit closing", dep_close, dep_top)
# KWP statement vs cash statement devex
kwp_bay = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
               and r["line_item_bm"] == "Jumlah Bayaran" and r["year"] == "2016")
check("cross: Nota7(a)(i) Jumlah Bayaran = perf Belanja Pembangunan 2016", kwp_bay, DEVEX[2016])

# ---- 16. printed aktiviti-code anomaly scan (diagnosed, never corrected) ----
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
    ("lampiran1 'Jumlah 090000' anggaran asal printed typo (B.10, pdf 122)",
     "the B.10 program-090000 total prints Anggaran Asal 288,084,900 while its own "
     "printed component rows sum to 292,184,900 — the 090500 'Bayaran Balik Hasil' "
     "asal of 4,100,000 is dropped from the total cell only (Dipinda/Sebenar cells "
     "foot, and the maksud total includes the 4,100,000); verified on the page "
     "image; kept as printed"),
    ("lampiran1 prestasi% printed typos (4 cells, verified against page images)",
     "B.06 160200 Pemberian prints 99.00 (arith. 100.00) [pdf 98]; B.06 180100 "
     "Perkhidmatan dan Bekalan prints 99.99 (arith. 97.75) and B.06 190100 "
     "Perkhidmatan dan Bekalan prints 99.99 (arith. 95.98) [pdf 99]; B.42 070400 "
     "Emolumen prints 99.99 (arith. 84.91) [pdf 182]. All RM columns verified by "
     "group sums; % kept as printed"),
    ("cash statement Hasil vs Nota 5(a) difference (printed, explained in Nota 5)",
     "cash-basis Hasil Bukan Cukai (39,802,803,140) and Terimaan Bukan Hasil "
     "(1,914,344,320) differ from Nota 5(a) by 203,392,339 and 199,116,112 "
     "(Akaun Premium TPK / Sukuk Global gains and deposit-account adjustments); "
     "both figures as printed, reconciliation captured in fact_other_notes"),
    ("cash statement vs Nota 6 Bilateral Bayaran 2015 (cross-statement print difference)",
     "the cash statement prints Bayaran Bantuan Luar Negeri Pinjaman Bilateral 2015 "
     "= 282,391,376 while Nota 6 prints (284,889,446) — difference 2,498,070; both "
     "kept as printed in their own tables (fact_cash_statement vs "
     "fact_loan_account_statement)"),
    ("lampiran6 blank Luar Negeri cell (Sentuhan Budiman, pdf 278)",
     "the Luar Negeri cell of the Sentuhan Budiman row is printed BLANK (not even a "
     "dash); resolved as 0.0 by the row identity Dalam+Luar=Jumlah "
     "(650,000,000.00 + 0 = 650,000,000.00) and flagged here"),
    ("Nota 8(a) declared restatement of the 2015 PPBD comparative",
     "2015 Pinjaman dan Pendahuluan Boleh Dituntut restated from 105,733,458,107 to "
     "106,821,651,022 (Pendahuluan Diri & Pelbagai Penjawat Awam and Pendahuluan "
     "kepada Kerajaan Negeri adjustments) — declared in the volume, captured in "
     "fact_other_notes"),
    ("LPPSA corporatisation runs through the 2016 volume",
     "Bahagian Pinjaman Perumahan Perbendaharaan corporatised into Lembaga "
     "Pembiayaan Perumahan Sektor Awam on 1.1.2016: Kumpulan Wang Pinjaman "
     "Perumahan wound up (Nota 6/7), RM21.9b term loans removed from Hutang "
     "Persekutuan (Nota 9(a)), RM50.92b housing loans removed from PPBD (Nota 8(a)), "
     "RM1.78b cash paid over (Nota 3)"),
    ("register absences in the 2016 volume (6 lampiran only)",
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
with open(f"{WH}/_validation_checks_2016.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
    for name, diag in DIAGNOSES:
        cw.writerow(["DIAGNOSIS", f"core: {name}: {diag}", "", "", ""])
