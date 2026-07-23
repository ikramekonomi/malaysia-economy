#!/usr/bin/env python3
"""Programmatic validation for the 2019 warehouse: extracted line items must
reproduce printed totals. Never corrects -- only reports PASS/FAIL with amounts.
All reference figures are typed from the 2019 volume's own printed statements."""
import csv
from collections import defaultdict

WH = "/home/claude/pkkp/warehouse2019"
results = []


def check(name, got, want, tol=0.5):
    ok = abs(got - want) <= tol
    results.append((("PASS" if ok else "FAIL"), name, got, want, got - want))


def note(name, ok=True):
    results.append((("PASS" if ok else "FAIL"), name, "", "", ""))


def load(name):
    with open(f"{WH}/{name}", encoding="utf-8") as f:
        return list(csv.DictReader(f))


F = lambda r, k: float(r[k]) if r[k] not in ("", "None") else 0.0

# ---- printed reference figures (typed from the 2019 volume) ----
WANG_AWAM = {2019: 59_230_681_572, 2018: 52_910_057_045}          # pdf 53
HASIL = {2019: 264_414_755_876, 2018: 232_882_562_288}            # pdf 56
OPEX_PRESTASI = {2019: 263_342_924_643, 2018: 230_960_492_668}
DEVEX = {2019: 54_173_235_317, 2018: 56_095_455_662}
KURANGAN = {2019: -53_101_404_084, 2018: -54_173_386_042}
JUM_TERIMAAN = {2019: 408_405_103_476, 2018: 382_901_357_462}     # pdf 54-55
JUM_BAYARAN = {2019: 411_555_631_742, 2018: 377_317_886_056}
TUNAI_AKHIR = {2019: 20_497_071_598, 2018: 23_647_599_864}
TANGGUNGAN = 64_079_723_659                                       # Nota 5(b) pdf 62
BEKALAN = 200_335_032_217
OPEX_NOTA_TOTAL = 264_414_755_876   # incl. transfer to KW Pembangunan (in B.12)
N_MAKSUD = 50
HUTANG = {2019: 792_997_555_813, 2018: 741_048_714_484}           # Nota 10 pdf 69
PINJ_DN = {2019: 764_232_726_000, 2018: 719_545_169_000}
AMANAH_AKHIR = {2019: 31_090_170_157, 2018: 25_822_806_810}       # Nota 7 pdf 64
DEVEX_L2 = 54_173_235_316.97                                      # Lampiran 2 pdf 210-211
N_MINISTRIES_L2 = 28
KOMITMEN = {2019: 247_461_392_666, 2018: 242_968_745_211}         # memo pdf 57
PFI = {2019: 38_829_548_225, 2018: 36_416_442_980}                # Nota 10(b) pdf 69
PAMPASAN = {2019: 990_037_154, 2018: 2_169_792_773}               # Nota 10(c)(iv) pdf 70

# ---- 0. documented schema/format differences of the 2019 volume ----
note("schema note: Lampiran 1 prints FOUR value columns (Asal|Dipinda|Amaun|Prestasi); "
     "Dipinda stored in anggaran_jumlah_rm; anggaran_tambahan_rm/viremen_rm/varian_rm empty")
note("schema note: Lampiran 2 cumulative columns are RMKe-11 (terkumpul_rmke11_prior_rm=to 31.12.2018, "
     "terkumpul_rmke11_rm=to 31.12.2019)")
note("schema note: NO COVID-19 fund exists in 2019 (pre-COVID volume): no fact_covid_fund_detail; "
     "no COVID rows anywhere")
note("schema note: no 'Penyata Penyaluran Geran Bayaran Balik Pinjaman' is printed in the 2019 "
     "volume -> fact_guarantee_repayment_grants.csv absent (grants appear only as narrative notes: "
     "opex RM528,963,870 / devex RM3,412,608,823)")
note("schema note: Lampiran 6 PFI prints by KATEGORI (IPS(PFI)/APKPS) with '*' restructuring "
     "footnotes -> fact_pfi_liabilities gains kategori_bm and has_footnote columns; "
     "fact_debt PFI components use kind='pfi_component' (2020 volume restated to companies)")
note("schema note: Perangkaan panel spans 2010-2019 (10 years) -> fact_timeseries_2010_2019.csv")
note("format note: 2019 Lampiran 1 HAS a text layer (extracted textually, no OCR needed); "
     "the volume's two 'No font in show' pdftotext errors are on ENGLISH-section pages 362-363 "
     "(Attachment 5 BI mirror), outside all extracted BM tables")
note("PRINT ANOMALY (volume pagination): one page of Lampiran 1 content is MISSING from the "
     "official print between printed pages 77 and 78 (pdf 89->90): B.05's closing blocks "
     "(rest of program 030000, class summaries, JUMLAH maksud row) and B.06's opening blocks "
     "(header, aktiviti 010100/010200) were dropped in prepress; affected sums are reported "
     "below with diagnoses, nothing fabricated")

# ---- 1. financial position ----
fp = load("fact_financial_position.csv")
for yr in (2019, 2018):
    tunai = sum(F(r, "amount_rm") for r in fp if r["section"] == "WANG AWAM" and int(r["year"]) == yr)
    kw = sum(F(r, "amount_rm") for r in fp if r["section"] == "KUMPULAN WANG DISATUKAN" and int(r["year"]) == yr)
    check(f"pos: Wang Awam {yr} = printed total", tunai, WANG_AWAM[yr])
    check(f"pos: Kumpulan Wang Disatukan {yr} = printed total", kw, WANG_AWAM[yr])

# ---- 2. performance ----
pf = load("fact_financial_performance.csv")
g = {(r["line_code"], int(r["year"]), r["basis"]): F(r, "amount_rm") for r in pf}
for yr in (2019, 2018):
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
    cb = g[("current_balance", yr, "sebenar")]
    check(f"perf: Lebihan/(Kurangan) = hasil - opex {yr}",
          g[("revenue", yr, "sebenar")] - g[("opex", yr, "sebenar")], cb)

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
    for l2 in ["Cukai Langsung", "Cukai Tak Langsung"]:
        l2v = next(F(r, col) for r in rv if r["level"] == "2" and r["item_bm"] == l2)
        l3 = sum(F(r, col) for r in rv if r["level"] == "3" and r["category_l2_bm"] == l2)
        check(f"rev[{col}]: sum(items) = {l2}", l3, l2v)
check("rev: HASIL sebenar = perf Hasil", next(F(r, "sebenar_rm") for r in rv if r["level"] == "0"), HASIL[2019])
check("rev: GST rows (Cukai Barangan dan Perkhidmatan Import/Tempatan) print nil 2019 columns "
      "(SST era; GST repealed 01.09.2018) -- 2018 comparatives",
      sum(F(r, "sebenar_prior_rm") for r in rv if r["item_bm"].startswith("Cukai Barangan dan Perkhidmatan")),
      9_606_118_809 + 10_629_520_562)

# ---- 4. opex by maksud ----
ox = load("fact_opex_maksud.csv")
t = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("T."))
b = sum(F(r, "sebenar_rm") for r in ox if r["maksud_code"].startswith("B."))
check("opex: sum(T.*) sebenar = printed Tanggungan (whole-RM rounding of 14 rows; "
      "Lampiran 1 sen-level total is 64,079,723,658.94)", t, TANGGUNGAN, tol=3)
check("opex: sum(B.*) sebenar = printed Bekalan (whole-RM rounding of 36 rows; "
      "Lampiran 1 sen-level total is 200,335,032,217.47)", b, BEKALAN, tol=10)
check("opex: T+B = printed Perbelanjaan Mengurus (rounding as above)", t + b, OPEX_NOTA_TOTAL, tol=10)
check(f"opex: count of maksud = {N_MAKSUD}", len(ox), N_MAKSUD)

# ---- 5. devex by maksud ----
dx = load("fact_devex_maksud.csv")
SECTION_LBLS = ("PENDIDIKAN", "PENDIDIKAN TINGGI")
mins = [r for r in dx if r["maksud_code"] != "TOTAL" and r["jumlah_label_bm"] not in SECTION_LBLS]
secs = [r for r in dx if r["jumlah_label_bm"] in SECTION_LBLS]
tot = next(r for r in dx if r["maksud_code"] == "TOTAL")
for col in ["anggaran_jumlah_rm", "sebenar_jumlah_rm", "kos_keseluruhan_rm", "terkumpul_rmke11_rm"]:
    check(f"devex[{col}]: sum(ministries) = grand total", sum(F(r, col) for r in mins), F(tot, col), tol=0.05)
check("devex: grand total sebenar = printed (sen)", F(tot, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
check("devex: grand total = perf Belanja Pembangunan (rounded)", F(tot, "sebenar_jumlah_rm"), DEVEX[2019], tol=0.5)
check("devex: P.63 section subtotals (PENDIDIKAN + PENDIDIKAN TINGGI) = JUMLAH KEMENTERIAN PENDIDIKAN",
      sum(F(r, "sebenar_jumlah_rm") for r in secs),
      next(F(r, "sebenar_jumlah_rm") for r in mins if r["jumlah_label_bm"] == "KEMENTERIAN PENDIDIKAN"), tol=0.01)
for r in mins:
    lg = F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm")
    check(f"devex row: langsung+pinjaman=jumlah [{r['maksud_code']} {r['jumlah_label_bm'][:20]}]",
          lg, F(r, "sebenar_jumlah_rm"), tol=0.01)

# ---- 6. cash statement ----
cs = load("fact_cash_statement.csv")
for yr in (2019, 2018):
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
pos_tunai = next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "WANG TUNAI" and r["year"] == "2019")
check("cross: cash closing 2019 = position Wang Tunai", TUNAI_AKHIR[2019], pos_tunai)

# ---- 7. debt / memo ----
db = load("fact_debt.csv")
for yr in (2019, 2018):
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
for yr in (2019, 2018):
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
    kc = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_total" and int(r["year"]) == yr)
    check(f"debt: 4 commitment totals sum = memo Komitmen Kewangan {yr}", kc, KOMITMEN[yr])
    pfi_t = next(F(r, "amount_rm") for r in db if r["kind"] == "pfi_total" and int(r["year"]) == yr)
    pfi_c = sum(F(r, "amount_rm") for r in db if r["kind"] == "pfi_component" and int(r["year"]) == yr)
    check(f"debt: PFI components sum = PFI total {yr}", pfi_c, pfi_t)
    check(f"debt: PFI total = printed {yr}", pfi_t, PFI[yr])
    pit = sum(F(r, "amount_rm") for r in db if r["kind"] == "commitment_item" and int(r["year"]) == yr)
    check(f"debt: pampasan item = printed {yr}", pit, PAMPASAN[yr])
    ml = next(F(r, "amount_rm") for r in db if r["kind"] == "misc_total" and int(r["year"]) == yr)
    memo_ml = next(F(r, "amount_rm") for r in mm if r["line_item_bm"] == "Pelbagai Liabiliti" and int(r["year"]) == yr)
    check(f"debt: Pelbagai Liabiliti = memo {yr}", ml, memo_ml)

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
check("trust: closing = printed Nota 7 total 2019", F(grand, "baki_akhir_rm"), AMANAH_AKHIR[2019])
check("trust: opening = printed Nota 7 total 2018", F(grand, "baki_awal_rm"), AMANAH_AKHIR[2018])
check("cross: trust closing = position Akaun Amanah 2019", F(grand, "baki_akhir_rm"),
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN AMANAH DISATUKAN" and r["year"] == "2019"))
check("cross: position Akaun Pinjaman Disatukan 2019 = Nota 6 closing 16,277,384,329",
      next(F(r, "amount_rm") for r in fp if r["line_item_bm"] == "AKAUN PINJAMAN DISATUKAN" and r["year"] == "2019"),
      16_277_384_329)

# ---- 9. opex detail (Lampiran 1, text layer) ----
od = load("fact_opex_detail.csv")
# available value columns in the 2019 print: asal / jumlah(=dipinda) / sebenar
ODCOLS = ["anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"]
N5B = {"anggaran_asal_rm": "anggaran_asal_rm", "anggaran_jumlah_rm": "anggaran_dipinda_rm",
       "sebenar_rm": "sebenar_rm"}
for col in ODCOLS:
    leaf = defaultdict(float)
    for r in od:
        if r["row_type"] == "object_aktiviti":
            leaf[r["maksud_code"]] += F(r, col)
    okc = sum(1 for r in ox if abs(leaf[r["maksud_code"]] - F(r, N5B[col])) < 1)
    check(f"opex_detail[{col}]: maksud leaf sums = Nota 5(b) (48 of {N_MAKSUD}; B.05 and B.06 "
          f"fail ONLY because the print omits one page of their detail -- see PRINT ANOMALY note)",
          okc, 48)
    jm = {}
    for r in od:
        if r["row_type"] == "jumlah_maksud":
            jm[r["maksud_code"]] = F(r, col)
    okc = sum(1 for k, v in jm.items() if abs(leaf[k] - v) < 1)
    check(f"opex_detail[{col}]: maksud leaf sums = printed JUMLAH maksud rows (48 of 49 printed; "
          f"B.05's JUMLAH row is on the omitted page; B.06's printed JUMLAH includes the omitted detail)",
          okc, 48)
EXPECT_BAD_PROG = {  # documented print-side inconsistencies (crop/text verified)
    "anggaran_asal_rm": 1,      # B.06 010000 (omitted page)
    "anggaran_jumlah_rm": 4,    # B.03/B.06/B.10/B.43
    "sebenar_rm": 5,            # B.03/B.06/B.10/B.23/B.43
}
for col in ODCOLS:
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
        if r["row_type"] == "object_aktiviti":
            prog_leaf[(r["maksud_code"], r["program_code"])] += F(r, col)
    jp = defaultdict(float)
    for r in od:
        if r["row_type"] == "jumlah_program":
            jp[(r["maksud_code"], r["program_code"])] += F(r, col)
    badp = sum(1 for k, v in jp.items() if abs(prog_leaf.get(k, 0.0) - v) >= 1)
    check(f"opex_detail[{col}]: program leaf sums = printed Jumlah program "
          f"(bad groups = documented print anomalies only)", badp, EXPECT_BAD_PROG[col])
    jenis_rows = [r for r in od if r["row_type"] == "jumlah_jenis"]
    jb_rows = [r for r in od if r["row_type"] == "jumlah_besar"]
    jenis_sum = sum(F(r, col) for r in jenis_rows)
    check(f"opex_detail[{col}]: sum(jenis totals) = grand total", jenis_sum, F(jb_rows[0], col), tol=1.0)
jb = [r for r in od if r["row_type"] == "jumlah_besar"]
check("opex_detail: grand total sebenar = Nota total (JUMLAH KESELURUHAN MENGURUS 264,414,755,876.41)",
      F(jb[0], "sebenar_rm"), OPEX_NOTA_TOTAL, tol=0.5)
check("opex_detail: jenis totals sebenar = printed Tanggungan+Bekalan",
      sum(F(r, "sebenar_rm") for r in od if r["row_type"] == "jumlah_jenis"),
      TANGGUNGAN + BEKALAN, tol=1.0)
jm_all = sum(F(r, "sebenar_rm") for r in od if r["row_type"] == "jumlah_maksud")
check("opex_detail: sum(printed JUMLAH maksud rows) sebenar = grand - 37,746,646.74 "
      "(B.05's JUMLAH row is on the page omitted from the print; its Nota 5(b) value is 37,746,647)",
      jm_all, F(jb[0], "sebenar_rm") - 37_746_646.74, tol=1.0)
# documented print-side anomalies found in Lampiran 1 (kept as printed)
note("lampiran1 PRINT ANOMALY (kept as printed): B.03 program 010000 'Jumlah 010000' row "
     "(pdf 87) excludes the Perbelanjaan-perbelanjaan Lain class (dipinda -40,000 / sebenar "
     "-29,294.45 vs its own aktiviti and class rows; leaves reconcile with Nota 5(b))")
note("lampiran1 PRINT ANOMALY (kept as printed): B.10 program 040000 'Jumlah 040000' row "
     "(pdf 101) excludes the Perbelanjaan-perbelanjaan Lain class in dipinda/sebenar "
     "(sebenar -4,901,640.58); leaves reconcile with Nota 5(b)")
note("lampiran1 PRINT ANOMALY (kept as printed): B.23 program 050000 'Jumlah 050000' row "
     "(pdf 122) prints sebenar 22,207,912.22, EXCLUDING aktiviti 050500 Cukai Tanah "
     "Persekutuan 234,320,457.63 which its own class rows and the maksud JUMLAH include")
note("lampiran1 PRINT ANOMALY (kept as printed): B.43 program 030000 'Jumlah 030000' row "
     "(pdf 152) prints dipinda/sebenar 9,234,420/9,234,253.88 HIGHER than its own aktiviti "
     "and class rows (an extra copy of pendahuluan-aktiviti 030800's total); leaves "
     "reconcile with Nota 5(b)")
note("lampiran1 PRINT ANOMALY (kept as printed): pdf 169 subtotal under aktiviti 060100 "
     "prints 'Jumlah 040200' (wrong code); label kept as printed, row attributed to 060100 "
     "whose object rows it sums exactly")
note("lampiran1 print quirk repaired: pdf 114 aktiviti header '20400 Perkhidmatan Veterinar' "
     "drops its leading zero (restored to 020400; sums verified)")

# ---- 10. devex project level ----
dp = load("fact_devex_project.csv")
projsum = defaultdict(float)
for r in dp:
    if r["row_type"] == "project":
        projsum[r["maksud_code"]] += F(r, "sebenar_jumlah_rm")
okc = 0
for r in mins:
    if abs(projsum[r["maksud_code"]] - F(r, "sebenar_jumlah_rm")) < 1:
        okc += 1
check(f"devex_project: project sums = ministry totals ({N_MINISTRIES_L2} ministries)", okc, N_MINISTRIES_L2)
for col in ["kos_keseluruhan_rm", "terkumpul_rmke11_prior_rm", "anggaran_langsung_rm",
            "anggaran_pinjaman_rm", "anggaran_jumlah_rm", "sebenar_langsung_rm",
            "sebenar_pinjaman_rm", "sebenar_jumlah_rm", "terkumpul_rmke11_rm"]:
    ps = defaultdict(float)
    for r in dp:
        if r["row_type"] == "project":
            ps[r["maksud_code"]] += F(r, col)
    okc = sum(1 for r in mins if abs(ps[r["maksud_code"]] - F(r, col)) < 1)
    check(f"devex_project[{col}]: project sums = ministry totals ({N_MINISTRIES_L2})", okc, N_MINISTRIES_L2)
    mt = sum(F(r, col) for r in dp if r["row_type"] == "ministry_total")
    gt_ = next(F(r, col) for r in dp if r["row_type"] == "grand_total")
    check(f"devex_project[{col}]: ministry totals sum = grand total", mt, gt_, tol=0.05)
gt = next(r for r in dp if r["row_type"] == "grand_total")
check("devex_project: grand total = printed (sen)", F(gt, "sebenar_jumlah_rm"), DEVEX_L2, tol=0.005)
idfail = 0
for r in dp:
    if r["row_type"] == "project":
        if abs(F(r, "sebenar_langsung_rm") + F(r, "sebenar_pinjaman_rm") - F(r, "sebenar_jumlah_rm")) > 1:
            idfail += 1
        if abs(F(r, "anggaran_langsung_rm") + F(r, "anggaran_pinjaman_rm") - F(r, "anggaran_jumlah_rm")) > 1:
            idfail += 1
        if abs(F(r, "terkumpul_rmke11_prior_rm") + F(r, "sebenar_jumlah_rm") - F(r, "terkumpul_rmke11_rm")) > 1:
            idfail += 1
check("devex_project: per-project identities (0 failures)", idfail, 0)
psum = defaultdict(float)
for r in dp:
    if r["row_type"] == "project" and r["program_bm"]:
        psum[(r["maksud_code"], r["program_bm"].upper())] += F(r, "sebenar_jumlah_rm")
okp = badp = 0
for r in dp:
    if r["row_type"] == "program_subtotal" and r["program_bm"]:
        key = (r["maksud_code"], r["program_bm"].upper())
        if key in psum:
            if abs(psum[key] - F(r, "sebenar_jumlah_rm")) < 1:
                okp += 1
            else:
                badp += 1
check("devex: program subtotals matched by linked project sums (mismatches)", badp, 0)
check("devex: verified program-linkage groups >= 50", 1 if okp >= 50 else 0, 1)
p24i = [r for r in dp if r["maksud_code"] == "P.24" and r["row_type"] == "section_subtotal"]
check("devex PRINT QUIRK (kept, retyped section_subtotal): interim 'JUMLAH KEMENTERIAN "
      "PERDAGANGAN ANTARABANGSA DAN INDUSTRI' printed mid-block on pdf 188 sums the 6 "
      "MITI-core projects exactly; the full ministry total prints on pdf 190",
      F(p24i[0], "sebenar_jumlah_rm") if p24i else -1, 330_235_412.94, tol=0.005)

# ---- 11. timeseries panel 2010-2019 ----
ts = load("fact_timeseries_2010_2019.csv")
tv = {}
for r in ts:
    tv[(r["section_bm"], r["line_item_bm"], int(r["year"]))] = float(r["amount_rm_juta"])
years = sorted({int(r["year"]) for r in ts})
check("timeseries: covers 2010-2019 (10 years)", len(years), 10)
check("timeseries: min year 2010", years[0], 2010)
check("timeseries: max year 2019", years[-1], 2019)
panel19 = [
    ("Hasil", "Jumlah Hasil", HASIL[2019]),
    ("Perbelanjaan Mengurus", "Jumlah Perbelanjaan Mengurus", OPEX_PRESTASI[2019]),
    ("Wang Awam", "Wang Tunai", TUNAI_AKHIR[2019]),
    ("Kumpulan Wang Disatukan", "Akaun Amanah Disatukan", AMANAH_AKHIR[2019]),
    ("Hutang Persekutuan Luar Negeri", "Jumlah Hutang Persekutuan", HUTANG[2019]),
]
for sec, item, rm in panel19:
    got = tv.get((sec, item, 2019))
    check(f"timeseries: {item} 2019 = warehouse (RM juta)", got if got is not None else -1, round(rm / 1e6), tol=1.0)
XFOOT = [
    ("Wang Awam", ["Wang Tunai", "Pelaburan"], "Jumlah Wang Awam"),
    ("Kumpulan Wang Disatukan", ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan"],
     "Jumlah Kumpulan Wang Disatukan"),
    ("Kewangan", ["Lebihan/(Kurangan) Akaun Semasa", "Lebihan/(Kurangan) Akaun Pembangunan"],
     "Lebihan/(Kurangan) Keseluruhan"),
    ("Dibiayai oleh:", ["Pinjaman Bersih Dalam Negeri", "Pinjaman Bersih Luar Negeri", "Baki Akaun"], "Jumlah"),
    ("Punca Dana", ["Hasil", "Terimaan Kumpulan Wang Pembangunan", "Terimaan Bersih Kumpulan Wang Amanah Lain"],
     "Jumlah Punca Dana"),
    ("Penggunaan Dana", ["Perbelanjaan Mengurus (tidak termasuk pindahan ke Kumpulan Wang Pembangunan)",
                         "Perbelanjaan Pembangunan",
                         "Bayaran Bersih Kumpulan Wang Amanah Lain"], "Jumlah Penggunaan Dana"),
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
    ("Perubahan Dalam Modal Kerja", ["Tambahan/(Kurangan) Wang Tunai dan Pelaburan",
                                     "Pinjaman Bersih Dalam dan Luar Negeri"],
     "Tambahan/(Kurangan) Modal Kerja"),
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
    if titem == "Jumlah Bayaran Balik":
        check("timeseries xfoot [Jumlah Bayaran Balik = DN+LN] -- PRINT TYPO kept as printed: "
              "the 2017 column prints 88,453 (= DN total only), omitting LN 404; DN+LN = 88,857 "
              "(1 bad year expected)", len(bad_years), 1)
    else:
        check(f"timeseries xfoot [{titem} = DN+LN] all 10 years (bad years)", len(bad_years), 0)
    if bad_years:
        print(f"   xfoot detail {titem}: {bad_years}")
# roll-forwards across years within fund sections
CLOSING_SEC = {
    "Kumpulan Wang Pembangunan": "Kumpulan Wang Pembangunan / Perbelanjaan Pembangunan",
}
for sec in ["Akaun Hasil Disatukan", "Akaun Pinjaman Disatukan", "Akaun Amanah Disatukan",
            "Kumpulan Wang Pembangunan", "Kumpulan Wang Pinjaman Perumahan",
            "Pelbagai Kumpulan Wang Amanah Kerajaan",
            "Kumpulan Wang Amanah Awam", "Wang Deposit"]:
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
note("timeseries PRINT NOTE (kept as printed): the Kewangan/Dibiayai-oleh panel prints the "
     "2018-2019 columns with flipped sign convention (deficit shown positive, financing negative) "
     "relative to 2010-2017; cross-foots hold within each column as printed")

# ---- 12. Nota 5 statement table ----
ras = load("fact_revenue_account_statement.csv")
g5 = {(r["line_item_bm"], int(r["year"])): F(r, "sebenar_rm") for r in ras}
for yr in (2019, 2018):
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
check("nota5stmt: Akaun Hasil balance fixed at 11,863,127,086 since 1996 (both years)",
      g5[("BAKI PADA 31 DISEMBER", 2019)], 11_863_127_086)

# ---- 13. trust fund detail cross to Nota 7 top table ----
tfd = load("fact_trust_fund_detail.csv")
kwp_close = next(F(r, "amount_rm") for r in tfd if r["fund_bm"] == "Kumpulan Wang Pembangunan"
                 and r["row_type"] == "closing" and r["year"] == "2019")
kwp_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Kumpulan Wang Pembangunan")
check("cross: Nota7(a)(i) closing = Nota 7 table KWP closing", kwp_close, kwp_top)
pkw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "PELBAGAI KUMPULAN WANG AMANAH KERAJAAN" and r["year"] == "2019")
pkw_top = next(F(r, "baki_akhir_rm") for r in tr if r["account_bm"] == "Pelbagai Kumpulan Wang Amanah Kerajaan")
check("cross: Nota7(a)(ii) total = Nota 7 table PKWAK closing", pkw_close, pkw_top)
kaw_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "KUMPULAN WANG AMANAH AWAM" and r["year"] == "2019")
kaw_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Kumpulan Wang Amanah Am", "Kumpulan Wang Amanah Khas"))
check("cross: Nota7(b) total = Nota 7 table KWAA closing", kaw_close, kaw_top)
dep_close = next(F(r, "amount_rm") for r in tfd
                 if r["line_item_bm"] == "AKAUN DEPOSIT" and r["year"] == "2019")
dep_top = sum(F(r, "baki_akhir_rm") for r in tr
              if r["account_bm"] in ("Deposit Am", "Deposit Pelarasan"))
check("cross: Nota7(c) total = Nota 7 table Deposit closing", dep_close, dep_top)

# ---- 14. Nota 6 loan account cross-checks ----
la = load("fact_loan_account_statement.csv")
gl = {(r["group_bm"], r["sub_bm"], r["line_item_bm"], int(r["year"])): F(r, "amount_rm") for r in la}
check("nota6: DN Terimaan 2019 = cash statement DN borrowing",
      gl[("PINJAMAN", "Dalam Negeri", "Terimaan", 2019)], 131_254_933_379)
check("nota6: LN Terimaan 2019 = cash statement LN borrowing",
      gl[("PINJAMAN", "Luar Negeri", "Terimaan", 2019)], 7_170_135_617)
kwp_key = ("PINDAHAN KE", "", "Kumpulan Wang Pembangunan", 2019)
if kwp_key not in gl:
    kwp_key = ("PINDAHAN KE", None, "Kumpulan Wang Pembangunan", 2019)
check("nota6: transfer to KW Pembangunan 2019", gl[kwp_key], -54_456_031_282)
check("nota6: closing balance 2019 = position 16,277,384,329",
      next(v for (grp, sub, item, yr), v in gl.items() if grp == "BAKI" and "31" in item and yr == 2019),
      16_277_384_329)
check("cross: Nota6 KWP transfer = Nota7(a)(i) Pindahan Dari APD",
      abs(gl[kwp_key]),
      abs(next(F(r, "amount_rm") for r in tfd if r["line_item_bm"] == "Pindahan Dari Akaun Pinjaman Disatukan"
               and r["year"] == "2019")))

# ---- report ----
fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results)} checks: {len(results)-len(fails)} PASS, {len(fails)} FAIL\n")
for st, name, got, want, diff in results:
    if st == "FAIL":
        try:
            print(f"FAIL  {name}\n      got {got:,.2f}  want {want:,.2f}  diff {diff:,.2f}")
        except (ValueError, TypeError):
            print(f"FAIL  {name}")
with open(f"{WH}/_validation_checks_2019.csv", "a", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    for r in results:
        cw.writerow([r[0], "core: " + r[1], r[2], r[3], r[4]])
