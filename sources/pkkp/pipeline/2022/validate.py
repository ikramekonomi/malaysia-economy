#!/usr/bin/env python3
"""Programmatic validation for the 2022 warehouse: extracted line items must
reproduce printed totals. Never corrects — only reports PASS/FAIL with amounts.
All reference figures are typed from the 2022 volume's own printed statements."""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse2022"
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2022 volume) ----
# Penyata Kedudukan Kewangan pdf 71
WANG_AWAM = {2022: 83_655_906_621, 2021: 77_942_664_870}
# Penyata Prestasi Kewangan pdf 74
HASIL = {2022: 294_356_760_615, 2021: 233_752_055_029}
OPEX_PRESTASI = {2022: 292_693_212_510, 2021: 231_516_358_812}
DEVEX = {2022: 71_573_961_426, 2021: 64_256_665_755}
COVID_EXP = {2022: 30_979_119_546, 2021: 37_711_016_365}
KURANGAN = {2022: -100_889_532_867, 2021: -99_731_985_903}
# Cash statement pdf 72-73
JUM_TERIMAAN = {2022: 539_547_336_039, 2021: 457_294_237_763}
JUM_BAYARAN = {2022: 525_595_977_930, 2021: 448_773_083_955}
TUNAI_AKHIR = {2022: 48_502_901_599, 2021: 34_551_543_490}
# Nota 5(b) pdf 83
TANGGUNGAN = 78_424_609_882
BEKALAN = 215_932_150_733
OPEX_NOTA_TOTAL = 294_356_760_615  # includes transfer to KW Pembangunan (inside B.12)
N_MAKSUD = 52
# Nota 10 pdf 91
HUTANG = {2022: 1_079_590_517_115, 2021: 979_814_361_318}
PINJ_DN = {2022: 1_050_077_729_000, 2021: 950_083_947_500}
# Nota 7 pdf 85
AMANAH_AKHIR = {2022: 71_792_779_535, 2021: 66_079_537_784}
# Lampiran 2 grand total (sen precision, pdf 229)
DEVEX_L2 = 71_573_961_425.79
N_MINISTRIES_L2 = 29

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2022, 2021):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2022, 2021):
    check(f"perf: Hasil sebenar {yr}", g[("revenue", yr, "sebenar")], HASIL[yr])
    check(f"perf: Belanja Mengurus sebenar {yr}", g[("opex", yr, "sebenar")], OPEX_PRESTASI[yr])
    check(f"perf: Belanja Pembangunan sebenar {yr}", g[("devex", yr, "sebenar")], DEVEX[yr])
    check(f"perf: Belanja KW COVID-19 sebenar {yr}", g[("covid_fund_exp", yr, "sebenar")], COVID_EXP[yr])
    check(f"perf: Kurangan Keseluruhan {yr}", g[("overall_deficit", yr, "sebenar")], KURANGAN[yr])
    check(f"perf: identity hasil-opex-devex-covid=kurangan {yr}",
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
    for l2 in ["Cukai Langsung", "Cukai Tidak Langsung"]:
        l2v = next(F(r, col) for r in rv if r["level"] == "2" and r["item_bm"] == l2)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l2_bm"] == l2)
        check(f"rev[{col}]: sum(items) = {l2}", l3, l2v)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2022])

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Tanggungan", t, TANGGUNGAN)
check("opex: sum(B.*) sebenar = printed Bekalan", b, BEKALAN)
check("opex: T+B = printed Perbelanjaan Mengurus (incl. transfer)", t + b, OPEX_NOTA_TOTAL)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)

# ---- 5. devex by maksud ----
dx = load("fact_devex_maksud.csv")
mins = [r for r in dx if r["maksud_code"] != "TOTAL"]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm", "terkumpul_rmke12_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col))
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2022], tol=0.5)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + (F(r, "sebenar_pinjaman_rm"))
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']}]", lg, F(r, "sebenar_jumlah_rm"), tol=0.01)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2022, 2021):
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
    # roll-forward: opening + (terimaan - bayaran) = closing
    op = next(F(r, "amount_rm") for r in cs if r["item_bm"] == "Wang Tunai Pada 1 Januari" and int(r["year"]) == yr)
    check(f"cash: roll-forward opening+net=closing {yr}", op + JUM_TERIMAAN[yr] - JUM_BAYARAN[yr], TUNAI_AKHIR[yr])
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2022")
check("cross: cash closing 2022 = position Wang Tunai", TUNAI_AKHIR[2022], pos_tunai)

# ---- 7. debt ----
db = load("fact_debt.csv")
for yr in (2022, 2021):
    dn = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Dalam Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: sum(DN instruments) {yr} = printed", dn, PINJ_DN[yr])
    hp = next(F(r, "amount_rm") for r in db if r["item_bm"] == "HUTANG PERSEKUTUAN" and int(r["year"]) == yr)
    check(f"debt: Hutang Persekutuan {yr} = printed", hp, HUTANG[yr])
    ln_ = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Pinjaman Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    bln = sum(F(r, "amount_rm") for r in db if r["group_bm"] == "Bantuan Luar Negeri" and r["kind"] == "instrument" and int(r["year"]) == yr)
    check(f"debt: DN+LN+BLN = Hutang {yr}", dn + ln_ + bln, HUTANG[yr])
mm = load("fact_memorandum.csv")
for yr in (2022, 2021):
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
check("trust: closing = printed Nota 7 total 2022", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2022])
check("trust: opening = printed Nota 7 total 2021", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2021])
check("cross: trust closing = position Akaun Amanah 2022", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2022"))

# ---- 9. financing / commitments / PFI / pampasan ----
for yr in (2022, 2021):
    fin = sum(F(r, "amount_rm") for r in pf if r["line_code"].startswith("financing_") and int(r["year"]) == yr)
    check(f"perf: financing components sum = Jumlah Pembiayaan {yr}", fin, -KURANGAN[yr])
KOMITMEN = {2022: 284_924_267_021, 2021: 289_506_312_492}  # memo pdf 75
for yr in (2022, 2021):
    kc = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_total" and int(r["year"]) == yr)
    check(f"debt: 4 commitment totals sum = memo Komitmen Kewangan {yr}", kc, KOMITMEN[yr])
PFI = {2022: 34_492_348_126, 2021: 35_574_695_050}  # Nota 10(b) pdf 91
for yr in (2022, 2021):
    pfi_t = next(F(r, "amount_rm") for r in db if r["kind"] == "pfi_total" and int(r["year"]) == yr)
    pfi_c = sum(F(r, "amount_rm") for r in db if r["kind"] == "pfi_company" and int(r["year"]) == yr)
    check(f"debt: PFI companies sum = PFI total {yr}", pfi_c, pfi_t)
    check(f"debt: PFI total = printed {yr}", pfi_t, PFI[yr])
PAMPASAN = {2022: 535_409_173, 2021: 997_834_453}  # Nota 10(c)(iv) pdf 92
for yr in (2022, 2021):
    pit = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_item" and int(r["year"]) == yr)
    check(f"debt: pampasan items sum = printed {yr}", pit, PAMPASAN[yr])
for yr in (2022, 2021):
    pj = next(F(r, "amount_rm") for r in db if r["item_bm"] == "PINJAMAN" and int(r["year"]) == yr)
    bl = next(F(r, "amount_rm") for r in db if r["item_bm"] == "BANTUAN LUAR NEGERI" and int(r["year"]) == yr)
    check(f"debt: PINJAMAN+BANTUAN = HUTANG {yr}", pj + bl, HUTANG[yr])
for yr in (2022, 2021):
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)

# ---- 10. detail-layer tables ----
od = load("fact_opex_detail.csv")
for col in ["anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm", "anggaran_jumlah_rm",
            "sebenar_rm", "varian_rm"]:
    leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            leaf[r["maksud_code"]] += F(r, col)
    okc = 0
    for r in ox:
        # Nota 5(b) carries only asal/dipinda/sebenar; other columns checked vs Lampiran 1 jumlah_maksud
        pass
    if col in ("anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"):
        # Nota 5(b) columns: Anggaran Asal / Anggaran Dipinda / Sebenar
        ncol = {"anggaran_asal_rm": "anggaran_asal_rm", "anggaran_jumlah_rm": "anggaran_dipinda_rm",
                "sebenar_rm": "sebenar_rm"}[col]
        okc = sum(1 for r in ox if abs(leaf[r["maksud_code"]] - F(r, ncol)) < 1)
        check(f"opex_detail[{col}]: maksud leaf sums = Nota 5(b) ({N_MAKSUD} maksud)", okc, N_MAKSUD)
    # leaf sums must also equal Lampiran 1's own printed jumlah_maksud rows in ALL columns
    jm = {}
    for r in od:
        if r["row_type"] == "jumlah_maksud":
            jm[r["maksud_code"]] = F(r, col)
    okc = sum(1 for k, v in jm.items() if abs(leaf[k] - v) < 1)
    check(f"opex_detail[{col}]: maksud leaf sums = printed JUMLAH maksud rows ({N_MAKSUD})", okc, N_MAKSUD)
# aktiviti and program printed subtotals (all addable value columns)
for col in ["anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm", "anggaran_jumlah_rm",
            "sebenar_rm", "varian_rm"]:
    akt_leaf = defaultdict(float)
    prog_leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            akt_leaf[(r["maksud_code"], r["program_code"], r["aktiviti_code"], r["pdf_page"])] += F(r, col)
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    bad_a = tot_a = 0
    seen = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            seen[(r["maksud_code"], r["aktiviti_code"])] += F(r, col)
    bad = tot = 0
    ja = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_aktiviti":
            ja[(r["maksud_code"], r["aktiviti_code"])] += F(r, col)
    for k, v in ja.items():
        tot += 1
        if abs(seen.get(k, 0.0) - v) >= 1:
            bad += 1
    check(f"opex_detail[{col}]: aktiviti leaf sums = printed Jumlah aktiviti (bad groups)", bad, 0)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = 0
    for k, v in jp.items():
        if abs(prog_leaf.get(k, 0.0) - v) >= 1:
            badp += 1
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program (bad groups)", badp, 0)
# jenis and grand totals in all 7 columns
for col in ["anggaran_asal_rm", "anggaran_tambahan_rm", "viremen_rm", "anggaran_jumlah_rm",
            "sebenar_rm", "varian_rm"]:
    jm_sum_t = sum(F(r, col) for r in od if r["row_type"] == "jumlah_maksud" and r["label_bm"] and any(
        x["maksud_code"].startswith("T.") and x["maksud_name_bm"] == r["label_bm"] for x in ox))
    jenis_rows = [r for r in od if r["row_type"] == "jumlah_jenis"]
    jb_rows = [r for r in od if r["row_type"] == "jumlah_besar"]
    jenis_sum = sum(F(r, col) for r in jenis_rows)
    check(f"opex_detail[{col}]: sum(jenis totals) = grand total", jenis_sum, F(jb_rows[0], col), tol=1.0)
    jm_all = sum(F(r, col) for r in od if r["row_type"] == "jumlah_maksud")
    check(f"opex_detail[{col}]: sum(maksud totals) = grand total", jm_all, F(jb_rows[0], col), tol=1.0)
jb = [r for r in od if r["row_type"] == "jumlah_besar"]
check("opex_detail: grand total sebenar = Nota total", F(jb[0], "sebenar_rm"), OPEX_NOTA_TOTAL, tol=0.5)
check("opex_detail: jenis totals sebenar = printed Tanggungan+Bekalan",
      sum(F(r, "sebenar_rm") for r in od if r["row_type"] == "jumlah_jenis"),
      TANGGUNGAN + BEKALAN, tol=1.0)

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
# in all 7 numeric columns
for col in ["kos_keseluruhan_rm", "terkumpul_rmke12_prior_rm", "anggaran_langsung_rm",
            "anggaran_pinjaman_rm", "anggaran_jumlah_rm", "sebenar_langsung_rm",
            "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke12_rm"]:
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
        if abs(F(r, "terkumpul_rmke12_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke12_rm")) > 1:
            idfail += 1
check("devex_project: per-project identities (0 failures)", idfail, 0)

# ---- 10b. COVID-19 Lampiran 3 ----
cv = load("fact_covid_fund_detail.csv")
cv_tot = next(r for r in cv if r["row_type"] == "total")
for col in ["siling_keseluruhan_rm", "terkumpul_hingga_2021_rm", "peruntukan_rm", "virement_rm",
            "peruntukan_dipinda_rm", "sebenar_rm", "varian_rm", "terkumpul_hingga_2022_rm"]:
    det = sum(F(r, col) for r in cv if r["row_type"] == "project")
    check(f"covid_l3[{col}]: details = Jumlah Keseluruhan", det, F(cv_tot, col), tol=0.02)
cvbad = sum(1 for r in cv if r["row_type"] == "project"
            and abs(F(r, "terkumpul_hingga_2021_rm") + F(r, "sebenar_rm") - F(r, "terkumpul_hingga_2022_rm")) > 1)
check("covid_l3: per-row prior+sebenar=terkumpul (0 failures)", cvbad, 0)
check("covid_l3: cumulative spend to 31.12.2021 = printed Jumlah Keseluruhan",
      F(cv_tot, "terkumpul_hingga_2021_rm"), 75_730_254_996.35, tol=0.005)
check("covid_l3: cumulative spend to 31.12.2022 = printed Jumlah Keseluruhan",
      F(cv_tot, "terkumpul_hingga_2022_rm"), 106_709_374_542.88, tol=0.005)
check("covid_l3: sebenar total = Prestasi Belanja KW COVID-19 2022 (rounded RM)",
      F(cv_tot, "sebenar_rm"), COVID_EXP[2022], tol=1.0)
check("covid_l3: total prior+sebenar=terkumpul", 
      F(cv_tot, "terkumpul_hingga_2021_rm") + F(cv_tot, "sebenar_rm"),
      F(cv_tot, "terkumpul_hingga_2022_rm"), tol=0.02)

# ---- 11. timeseries ----
ts = load("fact_timeseries_2008_2022.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2008-2022 (15 years)", len(years), 15)
check("timeseries: min year 2008", years[0], 2008)
check("timeseries: max year 2022", years[-1], 2022)
# 2022 column must match warehouse facts (RM juta, printed panel is rounded)
panel23 = [
    ("Hasil", "Jumlah Hasil", HASIL[2022]),
    ("Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", OPEX_NOTA_TOTAL),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2022]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2022]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2022]),
]
for sec, item, rm in panel23:
    got = tv.get((sec, item, 2022))
    check(f"timeseries: {item} 2022 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
# within-section cross-foots across ALL 15 years
XFOOT = [
    ("Wang Awam", ["Wang Tunai", "Pelaburan"], "Jumlah Wang Awam"),
    ("Kumpulan Wang Disatukan", ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan"],
     "Jumlah Kumpulan Wang Disatukan"),
    ("Dibiayai oleh:", ["Pinjaman Bersih Dalam Negeri", "Pinjaman Bersih Luar Negeri", "Baki Akaun"], "Jumlah"),
    ("Punca Dana", ["Hasil", "Terimaan Kumpulan Wang Pembangunan", "Terimaan Bersih Kumpulan Wang Amanah Lain"],
     "Jumlah Punca Dana"),
    ("Penggunaan Dana", ["Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)",
                         "Perbelanjaan Pembangunan", "Perbelanjaan Kumpulan Wang COVID-19",
                         "Bayaran Bersih Kumpulan Wang Amanah Lain"], "Jumlah Penggunaan Dana"),
    ("Hasil", ["Cukai Langsung", "Cukai Tidak Langsung", "Terimaan Lain"], "Jumlah Hasil"),
    ("Perbelanjaan Mengurus", ["Emolumen", "Perkhidmatan dan Bekalan", "Aset",
                               "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan Lain"],
     "Jumlah Perbelanjaan Mengurus"),
    ("Terimaan Pinjaman Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                        "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "Sukuk", "Pinjaman Lain"],
     "Jumlah Terimaan Pinjaman Dalam Negeri"),
    ("Terimaan Pinjaman Luar Negeri", ["Pinjaman Pasaran", "Pinjaman Projek", "Pinjaman Lain"],
     "Jumlah Terimaan Pinjaman Luar Negeri"),
    ("Bayaran Balik Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                    "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "Sukuk", "Pinjaman Lain"],
     "Jumlah Bayaran Balik Dalam Negeri"),
    ("Bayaran Balik Luar Negeri", ["Pinjaman Pasaran", "Pinjaman Projek", "Pinjaman Lain"],
     "Jumlah Bayaran Balik Luar Negeri"),
    ("Pinjaman Bersih Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                      "Sekuriti Kerajaan Malaysia", "Pinjaman Pasaran", "Sukuk", "Pinjaman Lain"],
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
    ("Kumpulan Wang Pembangunan / Penerimaan",
     ["Caruman daripada Akaun Hasil Disatukan", "Pindahan daripada Akaun Pinjaman Disatukan", "Lain-lain"],
     "Jumlah Penerimaan"),
    ("Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan", ["Langsung", "Pinjaman"], "Jumlah Pembayaran"),
    ("Kumpulan Wang COVID-19 / Penerimaan",
     ["Pindahan daripada Akaun Pinjaman Disatukan", "Lain-lain"], "Jumlah Penerimaan"),
    ("Kumpulan Wang COVID-19 / Pembayaran", ["Perbelanjaan COVID-19"], "Jumlah Pembayaran"),
    ("Hutang Persekutuan Dalam Negeri", ["Bil Perbendaharaan", "Terbitan Pelaburan Kerajaan",
                                         "Sekuriti Kerajaan Malaysia", "Sukuk", "Pinjaman Lain"],
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
        if abs(ssum - tv[(sec, total_item, yr)]) > 1.5:  # RM juta rounding: components each ±0.5
            bad_years.append((yr, ssum - tv[(sec, total_item, yr)]))
    check(f"timeseries xfoot [{sec} -> {total_item}] all 15 years (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   xfoot detail {sec} -> {total_item}: {bad_years}")
# cross-section grand totals (the 'Jumlah <X>' line prints inside the Luar Negeri block)
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
    check(f"timeseries xfoot [{titem} = DN+LN] all 15 years (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   xfoot detail {titem}: {bad_years}")
# within-year fund identities in the Kumpulan Wang Disatukan roll-forward panels
AH = "Akaun Hasil Disatukan"
bad_years = []
for yr in years:
    lhs = (tv.get((AH, "Baki pada 1 Januari", yr), 0.0) + tv.get((AH, "Hasil", yr), 0.0)
           - tv.get((AH, "( - ) Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)", yr), 0.0)
           - tv.get((AH, "( - ) Perbelanjaan Pembangunan", yr), 0.0)
           - tv.get((AH, "( - ) Perbelanjaan Kumpulan Wang COVID-19", yr), 0.0))
    if abs(lhs - tv.get((AH, "Baki pada 31 Disember", yr), 0.0)) > 3.0:
        bad_years.append((yr, lhs - tv.get((AH, "Baki pada 31 Disember", yr), 0.0)))
check("timeseries identity [Akaun Hasil roll: opening+hasil-PM-PP-COVID=closing] all 15 years (bad years)",
      len(bad_years), 0)
if bad_years:
    print(f"   identity detail Akaun Hasil: {bad_years}")
AP = "Akaun Pinjaman Disatukan"
bad_years = []
for yr in years:
    lhs = (tv.get((AP, "Baki pada 1 Januari", yr), 0.0) + tv.get((AP, "Pinjaman Bersih", yr), 0.0)
           + tv.get((AP, "Pelarasan ke Akaun Premium / Diskaun bagi Terbitan Pelaburan Kerajaan dan Sekuriti Kerajaan Malaysia", yr), 0.0)
           + tv.get((AP, "Pindahan", yr), 0.0))
    if abs(lhs - tv.get((AP, "Baki pada 31 Disember", yr), 0.0)) > 3.0:
        bad_years.append((yr, lhs - tv.get((AP, "Baki pada 31 Disember", yr), 0.0)))
check("timeseries identity [Akaun Pinjaman roll] all 15 years (bad years)", len(bad_years), 0)
if bad_years:
    print(f"   identity detail Akaun Pinjaman: {bad_years}")
# roll-forwards across years within fund sections
ROLL = [("Akaun Hasil Disatukan",), ("Akaun Amanah Disatukan",)]
CLOSING_SEC = {
    "Kumpulan Wang Pembangunan": "Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan",
    "Kumpulan Wang COVID-19": "Kumpulan Wang COVID-19 / Pembayaran",
}
for sec in ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan",
            "Kumpulan Wang Pembangunan", "Kumpulan Wang COVID-19",
            "Kumpulan Wang Pinjaman Perumahan", "Pelbagai Kumpulan Wang Amanah Kerajaan",
            "Kumpulan Wang Amanah Awam", "Wang Deposit"]:
    cl_sec = CLOSING_SEC.get(sec, sec)
    bad_years = []
    for yr in years[1:]:
        op_this = tv.get((sec, "Baki pada 1 Januari", yr))
        cl_prev = tv.get((cl_sec, "Baki pada 31 Disember", yr - 1))
        if op_this is None or cl_prev is None:
            continue
        # fund-closure boundary: a year printed as all dashes means the fund no
        # longer operates (e.g. Kumpulan Wang Pinjaman Perumahan wound up after
        # 2015, balance transferred to LPPSA) — the volume asserts no roll there
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
for yr in (2022, 2021):
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

# ---- 13. devex program linkage ----
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

# ---- 14. trust fund detail cross to Nota 7 top table ----
tfd = load("fact_trust_fund_detail.csv")
kwp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
                 and r["row_type"] == "closing" and r["year"] == "2022")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2022")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(iii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2022")
kaw_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Kumpulan Wang Amanah Am", "Kumpulan Wang Amanah Khas"))
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2022")
dep_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Deposit Am", "Deposit Pelarasan"))
check("cross: Nota7(c) total = Nota 7 table Deposit closing", dep_close, dep_top)
covid_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang COVID-19"
                   and r["row_type"] == "closing" and r["year"] == "2022")
covid_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang COVID-19")
check("cross: Nota7(a)(ii) COVID closing = Nota 7 table closing", covid_close, covid_top)

# ---- 15. printed aktiviti-code anomaly scan (diagnosed, never corrected) ----
# Any 'Jumlah <code>' row whose value does not equal the leaf sum of the aktiviti
# it is attributed to is diagnosed here: we search the same page for the aktiviti
# block whose leaf sum equals the printed value (i.e. a printed code typo).
akt_sum = defaultdict(float)
for r in od:
    if r["row_type"] == "object_aktiviti":
        akt_sum[(r["maksud_code"], r["pdf_page"], r["aktiviti_code"])] += F(r, "sebenar_rm")
anomalies = []
for r in od:
    if r["row_type"] != "jumlah_aktiviti":
        continue
    key = (r["maksud_code"], r["pdf_page"], r["aktiviti_code"])
    if key in akt_sum and abs(akt_sum[key] - F(r, "sebenar_rm")) < 1:
        continue
    cands = [k[2] for k, v in akt_sum.items()
             if k[0] == r["maksud_code"] and k[1] == r["pdf_page"] and abs(v - F(r, "sebenar_rm")) < 1]
    anomalies.append((r["maksud_code"], r["pdf_page"], r["label_bm"], F(r, "sebenar_rm"), cands))
check("lampiran1: jumlah_aktiviti rows not matching their own leaf sum (diagnosed below)",
      sum(1 for a in anomalies if not a[4]), 0)
for mk, pg, lbl, val, cands in anomalies:
    if cands:
        print(f"   printed-typo diagnosis: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f} "
              f"matches aktiviti {cands} leaf sum — printed code typo in the volume")
    else:
        print(f"   UNRESOLVED jumlah_aktiviti mismatch: '{lbl}' (pdf {pg}, {mk}) value {val:,.2f}")

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
with open(f"{WH}/_validation_checks_2022.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
