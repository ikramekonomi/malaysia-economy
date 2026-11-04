#!/usr/bin/env python3
"""Detail projection layer: every dashboard series estimated to FY2025-FY2026.

Run:  python3 apps/models/build_forecast2026.py
Reads : sources/pkkp/pkkp.duckdb                       (audited history)
        sources/mof-fiscal-outlook/data/fiscal_outlook_headline.csv   (official anchors)
        sources/anggaran/data/2025/fact_anggaran_maksud_2025.csv      (Budget 2025 as tabled)
        apps/models/fact_utilisation_signatures.csv              (actual/budget quantiles)
        apps/models/fact_nowcast_2025.csv                        (per-vote 2025 nowcast)
        apps/models/fact_projection_headline.csv                 (v1 trend bands)
Writes: apps/models/fact_projection_detail.csv    (year x group x series, lo/mid/hi)
        apps/models/fact_gap_projection.csv       (per-vote budget vs expected actual)
        apps/models/_validation_projection_2026.csv

MODEL DESIGN (hybrid, hierarchical; alternatives considered are in _METHOD.md #4):
  Anchor-and-share with identity constraints. Aggregates are pinned to the best
  available basis (official MOF figures where published; signature nowcast where the
  quantity is budget-driven; stock-flow identity for debt); components are modelled as
  SHARES of their anchor and re-normalised so accounting identities hold by
  construction. Bands are historical quantiles (p25/p75), never distributional claims.

  headline   rev/OE/DE/deficit: mid = official (Budget 2026 edition), band = v1
             trend-model p25/p75 band (kept as the honest uncertainty around a
             point official projection).
             debt: stock-flow identity debt_t = debt_{t-1} + |deficit_t| + eps_t,
             eps quantiles from FY2015-24 residuals (eps = observed change minus
             deficit: asset drawdowns, exchange valuation, off-budget financing).
  rev comp   tax / non-tax / non-revenue shares of official revenue: median share of
             the last 5 audited years (p25/p75 band), mids normalised to sum to 1.
             "of which investment income" modelled separately with a min/max band
             over 7 years (the known petroleum swing risk), no additivity constraint.
  objects    emoluments 2025 = Budget 2025 tabled emoluments x aggregate-OE
             utilisation quantiles; 2026 grown by its own FY2016-24 log-growth
             quantiles. Grants/supplies/assets = shares of (OE anchor - emoluments),
             5-year share quantiles, mids normalised. (FY2015 excluded everywhere:
             OCR-provisional object data.)
  rigidity   pension = T.14 tabled x T.14 signature quantiles; debt service = T.13
             tabled x T.13 signature; 2026 grown by each vote's own FY2016-24
             log-growth quantiles. Emoluments shared with `objects`.
  functions  2025 = per-vote signature nowcast aggregated to dashboard functions
             (sums of vote lo/mid/hi); 2026 = each function grown by its own
             FY2016-24 log-growth quantiles. NOT normalised to the official OE
             (the signature total deliberately preserves the historical
             overshoot-vs-budget bias; the difference is reported).
  gap        2025 = tabled budget vs signature-expected actual per vote (top |gap|).
             2026 = 2025 tabled budgets scaled uniformly by official OE growth
             (weakest layer, flagged) x signatures.
  contingent guarantees / PFI / leases: own log-growth quantiles (windows adapt to
             series start; leases FY2018-, PFI FY2019-).

Basis discipline: every row carries basis (official_projection / official_revised /
model_projection) + method + anchor. Nothing here is audited; nothing is blended into
audited tables. Supersedes nothing official - where MOF publishes a number, that
number IS the mid.
"""
import csv
import math
import os
import statistics as st

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
OFF_CSV = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data", "fiscal_outlook_headline.csv")
AP_CSV = os.path.join(ROOT, "sources", "anggaran", "data", "2025", "fact_anggaran_maksud_2025.csv")
AP26_CSV = os.path.join(ROOT, "sources", "anggaran", "data", "2026", "fact_anggaran_maksud_2026.csv")
HASIL26_CSV = os.path.join(ROOT, "sources", "anggaran-hasil", "data", "2026", "fact_hasil_ringkasan_2026.csv")
SIG_CSV = os.path.join(HERE, "fact_utilisation_signatures.csv")
NOW_CSV = os.path.join(HERE, "fact_nowcast_2025.csv")
V1_CSV = os.path.join(HERE, "fact_projection_headline.csv")

con = duckdb.connect(DB, read_only=True)
OWN = "source_file ILIKE year || '_PENYATA%'"
YEARS = [2025, 2026]


def q1(a, p):
    s = sorted(a)
    if not s:
        return None
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def gq(series):
    """log-growth quantiles of a positive series -> (p25, med, p75) growth factors"""
    g = [series[i] / series[i - 1] for i in range(1, len(series)) if series[i - 1] > 0 and series[i] > 0]
    lg = [math.log(x) for x in g]
    return tuple(math.exp(q1(lg, p)) for p in (0.25, 0.5, 0.75))


# ---------------- official anchors (latest edition per target year) ----------------
off = {}
for r in csv.DictReader(open(OFF_CSV)):
    k = (int(r["target_year"]), r["line"])
    ed = int(r["edition_year"])
    if k not in off or ed > off[k][0]:
        off[k] = (ed, float(r["amount_rm_bil"]), r["basis"])
ANCH = {y: {ln: off[(y, ln)][1] for ln in ("revenue", "operating_expenditure",
                                            "development_expenditure", "overall_deficit")}
        for y in YEARS}
OFF_BASIS = {y: off[(y, "revenue")][2] for y in YEARS}

# v1 trend bands (band around the official mid)
v1 = {}
for r in csv.DictReader(open(V1_CSV)):
    v1[(int(r["year"]), r["series"])] = (float(r["lo_rm_bil"]), float(r["hi_rm_bil"]))

# Budget 2026 tabled figures (real, from the AP2026 book - replaces growth/uniform scaling)
emol26_budget = pension26_budget = debtsvc26_budget = 0.0
vote_budget26 = {}
vote_name26 = {}
for r in csv.DictReader(open(AP26_CSV)):
    if r["measure"] != "anggaran_2026":
        continue
    c, cp, amt = r["maksud_code"], r["component"], int(r["amount_rm"]) / 1e9
    if cp == "emolumen":
        emol26_budget += amt
    if c.startswith(("T.", "B.")) and cp == "mengurus":
        vote_budget26[c] = amt
        vote_name26[c] = r["maksud_name_bm"]
    if c == "T.14" and cp == "mengurus":
        pension26_budget = amt
    if c == "T.13" and cp == "mengurus":
        debtsvc26_budget = amt

# official revenue estimates by category (anggaran-hasil, Budget 2026 edition)
hasil = {}
for r in csv.DictReader(open(HASIL26_CSV)):
    hasil.setdefault(r["measure"], {})[r["kod"]] = int(r["amount_rm"]) / 1e9


# ---------------- history ----------------
H = con.sql(f"""SELECT year,
  max(CASE WHEN line_code='revenue' THEN amount_rm END)/1e9 rev,
  max(CASE WHEN line_code='overall_deficit' THEN amount_rm END)/1e9 deficit
 FROM fact_financial_performance WHERE basis='sebenar' AND {OWN} GROUP BY year ORDER BY year""").fetchall()
DEBT = {int(y): v / 1e3 for y, v in con.sql(
    "SELECT year, amount_rm_juta FROM fact_timeseries_2010_2024 WHERE line_item_bm='Jumlah Hutang Persekutuan'").fetchall()}
DEF = {int(r[0]): float(r[2]) for r in H}

rows = []          # (year, grp, series, lo, mid, hi, basis, method, anchor, note)
checks = []


def add(year, grp, series, lo, mid, hi, basis, method, anchor="", note=""):
    rows.append([year, grp, series, round(lo, 3), round(mid, 3), round(hi, 3),
                 basis, method, anchor, note])


# ---------------- headline ----------------
for y in YEARS:
    for ln, s in (("revenue", "rev"), ("operating_expenditure", "opex"),
                  ("development_expenditure", "devex"), ("overall_deficit", "deficit")):
        lo, hi = v1[(y, s)]
        if lo > hi:
            lo, hi = hi, lo
        add(y, "headline", s, lo, ANCH[y][ln], hi, OFF_BASIS[y],
            "mid=official MOF; band=v1 trend p25/p75", "MOF Fiscal Outlook (Budget 2026 ed.)")

# debt: stock-flow with residual quantiles (FY2015-24)
eps = [DEBT[t] - DEBT[t - 1] - abs(DEF[t]) for t in range(2015, 2025)]
e25, e50, e75 = q1(eps, .25), q1(eps, .5), q1(eps, .75)
d24 = DEBT[2024]
dlo25 = d24 + abs(ANCH[2025]["overall_deficit"]) + e25
dmid25 = d24 + abs(ANCH[2025]["overall_deficit"]) + e50
dhi25 = d24 + abs(ANCH[2025]["overall_deficit"]) + e75
dlo26 = dlo25 + abs(ANCH[2026]["overall_deficit"]) + e25
dmid26 = dmid25 + abs(ANCH[2026]["overall_deficit"]) + e50
dhi26 = dhi25 + abs(ANCH[2026]["overall_deficit"]) + e75
add(2025, "headline", "debt", dlo25, dmid25, dhi25, "model_projection",
    "stock-flow: debt24 + |official deficit| + eps(p25/med/p75 of FY2015-24 residuals)",
    "PKKP debt 2024 + MOF deficit path", f"official end-Jun-2025 level {off[(2025,'federal_debt')][1]}; band is conditional on the official deficit path (deficit uncertainty not propagated - see headline deficit band)")
add(2026, "headline", "debt", dlo26, dmid26, dhi26, "model_projection",
    "stock-flow compounded from 2025 quantile paths", "PKKP debt 2024 + MOF deficit path",
    "band conditional on official deficit path (deficit uncertainty not propagated)")
ej = off[(2025, "federal_debt")][1]
checks.append(["debt_monotone", "d24<mid25<mid26", f"{d24:.1f}<{dmid25:.1f}<{dmid26:.1f}",
               "PASS" if d24 < dmid25 < dmid26 else "FAIL"])
checks.append(["debt_endjun_sanity", "end-Jun-25 official within [d24, hi25]",
               f"{d24:.1f}<={ej:.1f}<={dhi25:.1f}", "PASS" if d24 <= ej <= dhi25 else "FAIL"])

# ---------------- revenue composition ----------------
comp = con.sql(f"""SELECT year,
  max(CASE WHEN item_bm ILIKE 'HASIL CUKAI' THEN sebenar_rm END)/1e9 tax,
  max(CASE WHEN item_bm ILIKE 'HASIL BUKAN CUKAI' THEN sebenar_rm END)/1e9 nontax,
  max(CASE WHEN item_bm ILIKE 'TERIMAAN BUKAN HASIL' THEN sebenar_rm END)/1e9 nonrev,
  max(CASE WHEN item_bm ILIKE 'Faedah dan Perolehan daripada Pelaburan%' THEN sebenar_rm END)/1e9 inv,
  max(CASE WHEN level=0 THEN sebenar_rm END)/1e9 total
 FROM fact_revenue WHERE {OWN} GROUP BY year HAVING tax IS NOT NULL ORDER BY year""").fetchall()
last5 = comp[-5:]
shares = {k: [r[i] / r[5] for r in last5] for i, k in ((1, "tax"), (2, "nontax"), (3, "nonrev"))}
mids = {k: q1(v, .5) for k, v in shares.items()}
norm = sum(mids.values())
inv7 = [r[4] / r[5] for r in comp[-7:]]
HASIL_COL = {2025: "anggaran_disemak_2025", 2026: "anggaran_2026"}
for y in YEARS:
    rev = ANCH[y]["revenue"]
    hc = hasil[HASIL_COL[y]]
    # official mids straight from the revenue estimates book (kod hasil sections);
    # the book splits WP collections into 90000 - PKKP counts them under non-tax
    off_mid = {"tax": hc["60000"], "nontax": hc["70000"] + hc.get("90000", 0.0),
               "nonrev": hc["80000"]}
    for k in ("tax", "nontax", "nonrev"):
        add(y, "revenue_comp", k, q1(shares[k], .25) * rev, off_mid[k],
            q1(shares[k], .75) * rev, "official_estimate",
            "mid = Anggaran Hasil official estimate by kod section; band = 5-yr share quantiles",
            f"sources/anggaran-hasil {HASIL_COL[y]}")
    add(y, "revenue_comp", "investment", min(inv7) * rev, hc.get("75000", q1(inv7, .5) * rev),
        max(inv7) * rev, "official_estimate",
        "mid = kod 75000 Faedah dan Pulangan Pelaburan official estimate; band = 7-yr share min/max",
        f"sources/anggaran-hasil {HASIL_COL[y]}", "memo item - subset of non-tax, not additive")
    tot = sum(off_mid.values())
    checks.append([f"revcomp_additivity_{y}", "tax+nontax+nonrev == official revenue",
                   f"{tot:.3f} vs {rev:.3f}", "PASS" if abs(tot - rev) < 0.01 else "FAIL"])

# ---------------- Budget 2025 tabled aggregates ----------------
emol_budget = pension_budget = debtsvc_budget = 0.0
vote_budget = {}
vote_name = {}
for r in csv.DictReader(open(AP_CSV)):
    if r["measure"] != "anggaran_2025":
        continue
    c, cp, amt = r["maksud_code"], r["component"], int(r["amount_rm"]) / 1e9
    if cp == "emolumen":
        emol_budget += amt
    if (c.startswith("T.") and cp == "jumlah") or (c.startswith("B.") and cp == "mengurus"):
        vote_budget[c] = amt
        vote_name[c] = r["maksud_name_bm"]
    if c == "T.14" and cp == "jumlah":
        pension_budget = amt
    if c == "T.13" and cp == "jumlah":
        debtsvc_budget = amt

# aggregate-OE utilisation quantiles (FY2015-24)
oeu = [float(r[1]) for r in con.sql(f"""SELECT year, sum(sebenar_rm)/sum(anggaran_asal_rm)
  FROM fact_opex_maksud WHERE {OWN} GROUP BY year HAVING year BETWEEN 2015 AND 2024 ORDER BY year""").fetchall()]
u25, u50, u75 = q1(oeu, .25), q1(oeu, .5), q1(oeu, .75)

sig = {}
for r in csv.DictReader(open(SIG_CSV)):
    if r["util_p25"] and r["util_median"] and r["util_p75"]:
        sig[r["maksud_code"]] = (float(r["util_p25"]), float(r["util_median"]), float(r["util_p75"]))

# ---------------- objects (emol / grants / supplies / assets) ----------------
obj = con.sql(f"""SELECT year,
  sum(CASE WHEN objek_code='10000' THEN sebenar_rm END)/1e9 emol,
  sum(CASE WHEN objek_code='20000' THEN sebenar_rm END)/1e9 supplies,
  sum(CASE WHEN objek_code='30000' THEN sebenar_rm END)/1e9 assets,
  sum(CASE WHEN objek_code='40000' THEN sebenar_rm END)/1e9 grants
 FROM fact_opex_detail WHERE {OWN} AND row_type='object_aktiviti'
 GROUP BY year HAVING year BETWEEN 2016 AND 2024 ORDER BY year""").fetchall()
em = {2025: (emol_budget * u25, emol_budget * u50, emol_budget * u75),
      2026: (emol26_budget * u25, emol26_budget * u50, emol26_budget * u75)}
rest_shares = {}
for i, k in ((2, "supplies"), (3, "assets"), (4, "grants")):
    rest_shares[k] = [r[i] / (r[2] + r[3] + r[4]) for r in obj[-5:]]
rmids = {k: q1(v, .5) for k, v in rest_shares.items()}
rnorm = sum(rmids.values())
for y in YEARS:
    oe = ANCH[y]["operating_expenditure"]
    lo, mid, hi = em[y]
    add(y, "objects", "emol", lo, mid, hi, "model_projection",
        "tabled emoluments (own Budget book) x aggregate-OE utilisation quantiles",
        f"tabled emoluments {emol_budget if y==2025 else emol26_budget:.3f}; official OE {oe}")
    rest = oe - mid
    for k in ("grants", "supplies", "assets"):
        add(y, "objects", k, q1(rest_shares[k], .25) * rest, rmids[k] / rnorm * rest,
            q1(rest_shares[k], .75) * rest, "model_projection",
            "median share of non-emoluments OE (last 5 audited yrs), mids normalised to OE anchor",
            f"official OE {oe}")
    tot = mid + sum(rmids[k] / rnorm * rest for k in rmids)
    checks.append([f"objects_additivity_{y}", "emol+grants+supplies+assets == official OE",
                   f"{tot:.3f} vs {oe:.3f}", "PASS" if abs(tot - oe) < 0.01 else "FAIL"])

# ---------------- rigidity (pension / debtsvc; emol shared with objects) ----------------
rg_hist = con.sql(f"""SELECT year,
  sum(CASE WHEN maksud_code='T.13' THEN sebenar_rm END)/1e9 dsvc,
  sum(CASE WHEN maksud_code='T.14' THEN sebenar_rm END)/1e9 pens
 FROM fact_opex_maksud WHERE {OWN} GROUP BY year HAVING year BETWEEN 2016 AND 2024 ORDER BY year""").fetchall()
for series, b25, b26, code in (("pension", pension_budget, pension26_budget, "T.14"),
                               ("debtsvc", debtsvc_budget, debtsvc26_budget, "T.13")):
    s25, s50, s75 = sig[code]
    add(2025, "rigidity", series, b25 * s25, b25 * s50, b25 * s75, "model_projection",
        f"{code} tabled budget x its own utilisation signature quantiles", f"Budget 2025 {code} {b25:.3f}")
    add(2026, "rigidity", series, b26 * s25, b26 * s50, b26 * s75, "model_projection",
        f"{code} tabled Budget-2026 figure x its own utilisation signature quantiles",
        f"Budget 2026 {code} {b26:.3f}")
for y in YEARS:
    add(y, "rigidity", "emol", *em[y], "model_projection", "shared with objects.emol", "")

# ---------------- functions ----------------
def fn(n):
    n = n.lower()
    if 'perkhidmatan am perbendaharaan' in n: return 'Subsidies & refunds'
    if 'hutang' in n: return 'Debt service'
    if 'pencen' in n: return 'Pensions'
    if 'pendidikan tinggi' in n or 'pengajian tinggi' in n: return 'Education'
    if 'pendidikan' in n or 'pelajaran' in n: return 'Education'
    if 'kesihatan' in n: return 'Health'
    if 'pertahanan' in n: return 'Defence'
    if 'dalam negeri' in n and 'perdagangan' not in n: return 'Home Affairs'
    if 'terkanun' in n: return 'Transfers to funds'
    return 'Other ministries'


fh = con.sql(f"""SELECT o.year, dm.name_bm, o.sebenar_rm/1e9 v
  FROM fact_opex_maksud o JOIN dim_maksud dm ON dm.maksud_code=o.maksud_code AND dm.year=o.year
  WHERE o.{OWN.replace('year', 'o.year')} AND o.year BETWEEN 2016 AND 2024""").fetchall()
fhist = {}
for y, nm, v in fh:
    fhist.setdefault(fn(nm), {}).setdefault(int(y), 0.0)
    fhist[fn(nm)][int(y)] += v or 0.0

f25 = {}
for r in csv.DictReader(open(NOW_CSV)):
    if r["maksud_code"] == "TOTAL_OE":
        continue
    f = fn(r["name_bm"])
    cur = f25.setdefault(f, [0.0, 0.0, 0.0])
    cur[0] += float(r["expected_lo_rm"]) / 1e9
    cur[1] += float(r["expected_mid_rm"]) / 1e9
    cur[2] += float(r["expected_hi_rm"]) / 1e9
ftot25 = sum(v[1] for v in f25.values())
f26 = {}
for c, b in vote_budget26.items():
    q = sig.get(c, (1.0, 1.0, 1.0))
    cur = f26.setdefault(fn(vote_name26[c]), [0.0, 0.0, 0.0])
    cur[0] += b * q[0]
    cur[1] += b * q[1]
    cur[2] += b * q[2]
ftot26 = sum(v[1] for v in f26.values())
for f, (lo, mid, hi) in sorted(f25.items()):
    add(2025, "functions", f, lo, mid, hi, "model_projection",
        "sum of per-vote signature nowcast (budget x utilisation quantiles)",
        "Budget 2025 per vote", f"function totals sum to {ftot25:.1f}, not the official OE (signature bias kept)")
for f, (lo, mid, hi) in sorted(f26.items()):
    add(2026, "functions", f, lo, mid, hi, "model_projection",
        "sum of per-vote signature nowcast (tabled Budget-2026 x utilisation quantiles)",
        "Budget 2026 per vote", f"function totals sum to {ftot26:.1f}, not the official OE (signature bias kept)")

checks.append(["functions_vs_official_2025", "signature total vs official OE (INFO, by design)",
               f"{ftot25:.1f} vs {ANCH[2025]['operating_expenditure']:.1f}", "INFO"])

# ---------------- per-vote gap projection ----------------
SHORT = {'Perkhidmatan Am Perbendaharaan': 'Treasury general services',
         'Peruntukan Kepada Kumpulan Wang Terkanun': 'Transfers to statutory funds',
         'Peruntukan kepada Kumpulan Wang Terkanun': 'Transfers to statutory funds',
         'Perbelanjaan Kerana Hutang Negara': 'Debt service',
         'Pencen, Elaun Bersara dan Ganjaran': 'Pensions & gratuities',
         'Kementerian Pendidikan': 'Education', 'Kementerian Kesihatan': 'Health',
         'Kementerian Pendidikan Tinggi': 'Higher Education',
         'Jabatan Perkhidmatan Awam': 'Public Service Dept',
         'Kementerian Dalam Negeri': 'Home Affairs', 'Kementerian Pertahanan': 'Defence'}


def short(name):
    for k, v in SHORT.items():
        if name.strip().startswith(k[:18]):
            return v
    return (name[:26] + '…') if len(name) > 26 else name


gap_rows = []
for r in csv.DictReader(open(NOW_CSV)):
    if r["maksud_code"] == "TOTAL_OE" or r["signature"] == "fallback_no_history":
        continue
    c = r["maksud_code"]
    b25 = float(r["budget_2025_rm"]) / 1e9
    lo, mid, hi = (float(r[k]) / 1e9 for k in ("expected_lo_rm", "expected_mid_rm", "expected_hi_rm"))
    s = sig.get(c)
    gap_rows.append([2025, c, r["name_bm"], short(r["name_bm"]), b25, lo, mid, hi,
                     mid - b25, round(s[1] * 100, 1) if s else "", "model_projection",
                     "tabled Budget 2025 x own utilisation signature"])
for c, b26 in sorted(vote_budget26.items()):
    s = sig.get(c)
    if not s:
        continue
    nm = vote_name26[c]
    gap_rows.append([2026, c, nm, short(nm), b26,
                     b26 * s[0], b26 * s[1], b26 * s[2], b26 * s[1] - b26,
                     round(s[1] * 100, 1), "model_projection",
                     "tabled Budget 2026 (AP2026 book) x own utilisation signature"])

# ---------------- contingent ----------------
cont = {"guarantees": [v for _, v in sorted(
            {int(y): v / 1e3 for y, v in con.sql("SELECT year, amount_rm_juta FROM fact_timeseries_2010_2024 WHERE line_item_bm='Jumlah Jaminan'").fetchall()}.items()) if v],
        "pfi": [float(r[1]) for r in con.sql(f"SELECT year, sum(amaun_belum_selesai_rm)/1e9 FROM fact_pfi_liabilities WHERE {OWN} AND row_type='total' GROUP BY year ORDER BY year").fetchall()],
        "leases": [float(r[1]) for r in con.sql(f"SELECT year, sum(amaun_belum_selesai_rm)/1e9 FROM fact_finance_leases WHERE {OWN} AND row_type='total' GROUP BY year ORDER BY year").fetchall()]}
for k, series in cont.items():
    g25_, g50_, g75_ = gq(series)
    base = series[-1]
    v25 = (base * g25_, base * g50_, base * g75_)
    v26 = (v25[0] * g25_, v25[1] * g50_, v25[2] * g75_)
    n = len(series)
    add(2025, "contingent", k, *v25, "model_projection",
        f"FY2024 level x own log-growth quantiles (n={n} years)", f"PKKP 2024 {base:.1f}")
    add(2026, "contingent", k, *v26, "model_projection", "compounded quantile paths", f"PKKP 2024 {base:.1f}")

# ---------------- write ----------------
dest = os.path.join(HERE, "fact_projection_detail.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "grp", "series", "lo_rm_bil", "mid_rm_bil", "hi_rm_bil",
                "basis", "method", "anchor", "note"])
    w.writerows(rows)
gdest = os.path.join(HERE, "fact_gap_projection.csv")
with open(gdest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "maksud_code", "name_bm", "short", "budget_rm_bil",
                "expected_lo_rm_bil", "expected_mid_rm_bil", "expected_hi_rm_bil",
                "variance_mid_rm_bil", "util_median_pct", "basis", "method"])
    for r in gap_rows:
        w.writerow([r[0], r[1], r[2], r[3]] + [round(x, 3) if isinstance(x, float) else x for x in r[4:]])
vdest = os.path.join(HERE, "_validation_projection_2026.csv")
with open(vdest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check", "description", "values", "status"])
    w.writerows(checks)
fails = [c for c in checks if c[-1] == "FAIL"]
print(f"{dest}: {len(rows)} rows; {gdest}: {len(gap_rows)} rows; "
      f"{len(checks)} checks ({len(fails)} FAIL) -> {vdest}")
for c in fails:
    print("FAIL:", c)
