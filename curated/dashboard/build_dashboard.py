#!/usr/bin/env python3
"""Build the Malaysia Federal Finances dashboard from the PKKP warehouse.

Run:  python3 curated/dashboard/build_dashboard.py
Reads : sources/pkkp/pkkp.duckdb  (rebuild first: python3 pipeline/build_duckdb.py)
        curated/dashboard/external_denominators.csv  (GDP/population — EXTERNAL, provisional)
Writes: curated/dashboard/data.json        (the payload)
        curated/dashboard/index.html       (self-contained artifact = template.html + data)

Source of truth = the PKKP CSVs (the .duckdb is a rebuildable cache). Each year is taken
from its OWN audited volume (source_file '<year>_...'), amounts exact Ringgit as printed.
GDP/population are namespaced external denominators (not blended into audited tables) and are
flagged provisional until the DOSM source is ingested (docs/SOURCES.md).
"""
import duckdb, json, os, csv as _csv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB   = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
EXT  = os.path.join(HERE, "external_denominators.csv")
PEERS = os.path.join(HERE, "external_peers.csv")
YEARS = list(range(2010, 2025))
con = duckdb.connect(DB, read_only=True)
def q(sql): return con.sql(sql).df()
import math
def r(v, d=2):
    if v is None: return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, d)
def sanitize(o):
    if isinstance(o, dict): return {k: sanitize(v) for k, v in o.items()}
    if isinstance(o, list): return [sanitize(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    return o

OWN = "source_file ILIKE year || '_PENYATA%'"   # each year from its own volume (case-insensitive)
d = {}

# ---- external denominators ----
ext = {}
with open(EXT) as f:
    for row in _csv.DictReader(f):
        ext[int(row["year"])] = {k: (float(row[k]) if k in ("gdp_rm_bil","population_mil","households_mil") else row[k]) for k in row}
d["external"] = {"note": "GDP & population are DOSM figures, external to the audited warehouse and provisional (see docs/SOURCES.md).",
                 "by_year": {str(y): {"gdp": ext[y]["gdp_rm_bil"], "pop": ext[y]["population_mil"], "hh": ext[y]["households_mil"]} for y in YEARS if y in ext}}
# ---- peer benchmarks (external, IMF/national, indicative) ----
peers = []
with open(PEERS) as f:
    for row in _csv.DictReader(f):
        peers.append({"country": row["country"], "debt_gdp": float(row["debt_gdp"]), "deficit_gdp": float(row["deficit_gdp"]), "is_malaysia": row["is_malaysia"] == "1"})
d["peers"] = peers

# ---- headline (validated Penyata Prestasi Kewangan) ----
fp = q(f"""SELECT year,
  max(CASE WHEN line_code='revenue' THEN amount_rm END)/1e9 rev,
  max(CASE WHEN line_code='opex' THEN amount_rm END)/1e9 opex,
  max(CASE WHEN line_code='current_balance' THEN amount_rm END)/1e9 curr_bal,
  max(CASE WHEN line_code='devex' THEN amount_rm END)/1e9 devex,
  max(CASE WHEN line_code='overall_deficit' THEN amount_rm END)/1e9 deficit,
  max(CASE WHEN line_code='financing_net_borrowing' THEN amount_rm END)/1e9 net_borrow
 FROM fact_financial_performance WHERE basis='sebenar' AND {OWN} GROUP BY year ORDER BY year""")
debt = {int(x.year): x.v for x in q("SELECT year, amount_rm_juta/1e3 v FROM fact_timeseries_2010_2024 WHERE line_item_bm='Jumlah Hutang Persekutuan'").itertuples()}
gtee = {int(x.year): x.v for x in q("SELECT year, amount_rm_juta/1e3 v FROM fact_timeseries_2010_2024 WHERE line_item_bm='Jumlah Jaminan'").itertuples()}
d["headline"] = [{"year": int(x.year), "rev": r(x.rev), "opex": r(x.opex), "curr_bal": r(x.curr_bal),
                  "devex": r(x.devex), "deficit": r(x.deficit), "net_borrow": r(x.net_borrow),
                  "debt": r(debt.get(int(x.year)))} for x in fp.itertuples()]

# ---- revenue composition + investment income (petroleum-linked) ----
comp = q(f"""SELECT year,
  max(CASE WHEN item_bm ILIKE 'HASIL CUKAI' THEN sebenar_rm END)/1e9 tax,
  max(CASE WHEN item_bm ILIKE 'HASIL BUKAN CUKAI' THEN sebenar_rm END)/1e9 nontax,
  max(CASE WHEN item_bm ILIKE 'TERIMAAN BUKAN HASIL' THEN sebenar_rm END)/1e9 nonrev,
  max(CASE WHEN item_bm ILIKE 'Faedah dan Perolehan daripada Pelaburan%' THEN sebenar_rm END)/1e9 investment,
  max(CASE WHEN level=0 THEN sebenar_rm END)/1e9 total
 FROM fact_revenue WHERE {OWN} GROUP BY year ORDER BY year""")
d["revenue_comp"] = [{"year": int(x.year), "tax": r(x.tax), "nontax": r(x.nontax), "nonrev": r(x.nonrev),
                      "investment": r(x.investment), "total": r(x.total)} for x in comp.itertuples() if x.tax is not None]

# ---- rigidity + object class (both from own-volume opex) ----
rig = q(f"""SELECT year,
  sum(CASE WHEN maksud_code='T.13' THEN sebenar_rm END)/1e9 debtsvc,
  sum(CASE WHEN maksud_code='T.14' THEN sebenar_rm END)/1e9 pension
 FROM fact_opex_maksud WHERE {OWN} GROUP BY year ORDER BY year""")
obj = q(f"""SELECT year,
  sum(CASE WHEN objek_code='10000' THEN sebenar_rm END)/1e9 emol,
  sum(CASE WHEN objek_code='20000' THEN sebenar_rm END)/1e9 supplies,
  sum(CASE WHEN objek_code='30000' THEN sebenar_rm END)/1e9 assets,
  sum(CASE WHEN objek_code='40000' THEN sebenar_rm END)/1e9 grants,
  sum(CASE WHEN objek_code='50000' THEN sebenar_rm END)/1e9 other
 FROM fact_opex_detail WHERE {OWN} AND row_type='object_aktiviti' GROUP BY year ORDER BY year""")
revby = {h["year"]: h["rev"] for h in d["headline"]}
rmap = {int(x.year): x for x in rig.itertuples()}
d["rigidity"] = []
for x in obj.itertuples():
    y = int(x.year); rr = rmap.get(y)
    d["rigidity"].append({"year": y, "emol": r(x.emol), "supplies": r(x.supplies), "assets": r(x.assets),
                          "grants": r(x.grants), "other": r(x.other),
                          "debtsvc": r(rr.debtsvc) if rr else None, "pension": r(rr.pension) if rr else None,
                          "rev": revby.get(y)})

# ---- function spend by year + trend ----
raw = q(f"""SELECT o.year, o.maksud_code, dm.name_bm, o.sebenar_rm/1e9 spend
  FROM fact_opex_maksud o JOIN dim_maksud dm ON dm.maksud_code=o.maksud_code AND dm.year=o.year
  WHERE o.source_file ILIKE o.year || '_PENYATA%'""")
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
raw["func"] = raw["name_bm"].map(fn)
fby = {}
for y in YEARS:
    g = raw[raw.year == y].groupby("func").spend.sum().sort_values(ascending=False)
    fby[str(y)] = [{"func": k, "spend": r(v)} for k, v in g.items()]
d["func_by_year"] = fby
FUNCS = ['Education','Health','Subsidies & refunds','Debt service','Pensions','Defence','Home Affairs']
d["func_trend"] = {"years": YEARS, "series": {f: [r(float(raw[(raw.year==y)&(raw.func==f)].spend.sum())) for y in YEARS] for f in FUNCS}}

# ---- budget vs actual by year (top 12 |variance|), incl revised ----
bv = q(f"""SELECT o.year, o.maksud_code, dm.name_bm, o.anggaran_asal_rm/1e9 bud,
   o.anggaran_dipinda_rm/1e9 rev_bud, o.sebenar_rm/1e9 act
  FROM fact_opex_maksud o JOIN dim_maksud dm ON dm.maksud_code=o.maksud_code AND dm.year=o.year
  WHERE o.source_file ILIKE o.year || '_PENYATA%'""")
bv["dv"] = bv.act - bv.bud
SHORT = {'Perkhidmatan Am Perbendaharaan':'Treasury general services','Peruntukan kepada Kumpulan Wang Terkanun':'Transfers to statutory funds',
 'Perbelanjaan Kerana Hutang Negara':'Debt service','Pencen, Elaun Bersara dan Ganjaran':'Pensions & gratuities',
 'Kementerian Pendidikan':'Education','Kementerian Kesihatan':'Health','Kementerian Pendidikan Tinggi':'Higher Education',
 'Jabatan Perkhidmatan Awam':'Public Service Dept','Kementerian Dalam Negeri':'Home Affairs','Kementerian Pertahanan':'Defence'}
def short(name):
    for k,v in SHORT.items():
        if name.strip().startswith(k[:18]): return v
    return (name[:26]+'…') if len(name)>26 else name
gby = {}
for y in YEARS:
    sub = bv[bv.year == y].copy(); sub["a"] = sub["dv"].abs()
    top = sub.nlargest(12, "a")
    gby[str(y)] = [{"code": t.maksud_code, "name": t.name_bm, "short": short(t.name_bm),
                    "budget": r(t.bud,3), "revised": r(t.rev_bud,3), "actual": r(t.act,3), "variance": r(t.dv,3),
                    "util": (None if t.bud==0 else r(100*t.act/t.bud,1))} for t in top.itertuples()]
d["gap_by_year"] = gby
d["gap_totals_by_year"] = {}
for y in YEARS:
    o = bv[(bv.year==y)]
    dev = q(f"SELECT sum(sebenar_jumlah_rm)/1e9 a, sum(anggaran_jumlah_rm)/1e9 b FROM fact_devex_maksud WHERE source_file ILIKE '{y}_PENYATA%' AND year={y} AND maksud_code LIKE 'P.%'")
    d["gap_totals_by_year"][str(y)] = {"op_budget": r(o.bud.sum()), "op_revised": r(o.rev_bud.sum()), "op_actual": r(o.act.sum()),
                                       "dev_budget": r(float(dev.b.iloc[0])), "dev_actual": r(float(dev.a.iloc[0]))}

# ---- contingent by year (own-volume total rows; statutory kept separate/non-additive) ----
def totrow(t, col):
    o = {}
    for y in YEARS:
        v = con.sql(f"SELECT sum({col})/1e9 v FROM {t} WHERE source_file ILIKE '{y}_PENYATA%' AND year={y} AND row_type='total'").fetchone()
        o[y] = r(v[0]) if v and v[0] else None
    return o
pfi = totrow('fact_pfi_liabilities','amaun_belum_selesai_rm'); lease = totrow('fact_finance_leases','amaun_belum_selesai_rm')
statg = {}
for y in YEARS:
    v = con.sql(f"SELECT max(jumlah_rm)/1e9 v FROM fact_statutory_guarantees WHERE source_file ILIKE '{y}_PENYATA%' AND year={y} AND row_type='total'").fetchone()
    statg[y] = r(v[0]) if v and v[0] else None
d["contingent_by_year"] = {str(y): {"debt": r(debt.get(y)), "guarantees": r(gtee.get(y)), "pfi": pfi.get(y),
                                    "leases": lease.get(y), "statutory": statg.get(y)} for y in YEARS}
# guarantees by named entity (2024)
d["guarantee_entities"] = [{"name": x.agensi_bm, "v": r(x.b)} for x in
    q("SELECT agensi_bm, jumlah_rm/1e9 b FROM fact_guarantees WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='detail' ORDER BY b DESC LIMIT 8").itertuples()]

# ---- subsidy decomposition (B.11, 2024) ----
d["subsidy_2024"] = [{"name": x.aktiviti_name_bm, "v": r(x.b)} for x in
    q("SELECT aktiviti_name_bm, sum(sebenar_rm)/1e9 b FROM fact_opex_detail WHERE source_file ILIKE '2024_%' AND year=2024 AND maksud_code='B.11' AND row_type='object_aktiviti' GROUP BY 1 ORDER BY b DESC LIMIT 7").itertuples()]

# ---- debt maturity wall + instrument mix (2024) ----
mat = q("""SELECT TRY_CAST(right(tarikh_tebusan,4) AS INT) yr, sum(amaun_belum_selesai_rm)/1e9 b
  FROM fact_debt_issues WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='detail' AND tarikh_tebusan IS NOT NULL
  GROUP BY 1 HAVING yr IS NOT NULL ORDER BY 1""")
d["debt_maturity"] = [{"year": int(x.yr), "v": r(x.b)} for x in mat.itertuples() if 2025 <= int(x.yr) <= 2060]
d["debt_instruments"] = [{"name": x.instrument_bm, "v": r(x.b)} for x in
    q("""SELECT instrument_bm, sum(amaun_belum_selesai_rm)/1e9 b FROM fact_debt_issues
      WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='detail' AND instrument_bm IS NOT NULL
      GROUP BY 1 HAVING sum(amaun_belum_selesai_rm)/1e9 > 0.1 ORDER BY b DESC LIMIT 6""").itertuples()]

# ---- development pipeline + worst-delivery projects (2024) ----
pl = q("""SELECT sum(kos_keseluruhan_rm)/1e9 approved, sum(terkumpul_rmke12_rm)/1e9 cum,
   sum(sebenar_jumlah_rm)/1e9 annual, count(*) n FROM fact_devex_project
   WHERE source_file ILIKE '2024_%' AND row_type='project'""").iloc[0]
d["pipeline"] = {"approved": r(pl.approved,1), "cum": r(pl.cum,1), "annual": r(pl.annual,1), "n": int(pl.n)}
d["top_projects"] = [{"code": x.maksud_code, "name": x.name_bm, "cost": r(x.c,1), "cum": r(x.cm,1), "pct": r(100*x.cm/x.c,0) if x.c else 0} for x in
    q("""SELECT maksud_code, name_bm, kos_keseluruhan_rm/1e9 c, terkumpul_rmke12_rm/1e9 cm FROM fact_devex_project
      WHERE source_file ILIKE '2024_%' AND row_type='project' ORDER BY kos_keseluruhan_rm DESC LIMIT 6""").itertuples()]
d["stalled_projects"] = [{"code": x.maksud_code, "name": x.name_bm, "cost": r(x.c,1), "pct": r(100*x.cm/x.c,0)} for x in
    q("""SELECT maksud_code, name_bm, kos_keseluruhan_rm/1e9 c, terkumpul_rmke12_rm/1e9 cm FROM fact_devex_project
      WHERE source_file ILIKE '2024_%' AND row_type='project' AND kos_keseluruhan_rm>5e9
      ORDER BY (terkumpul_rmke12_rm/kos_keseluruhan_rm) ASC LIMIT 6""").itertuples()]

# ---- COVID fund ----
d["covid"] = [{"year": int(x.year), "spend": r(x.v)} for x in
    q(f"SELECT year, amount_rm/1e9 v FROM fact_financial_performance WHERE line_code='covid_fund_exp' AND basis='sebenar' AND {OWN} AND amount_rm>0 ORDER BY year").itertuples()]

# ---- policy constants (Fiscal Responsibility Act guardrails; no data source needed) ----
d["fra"] = {"debt_gdp_ceiling": 60, "debt_gdp_ceiling_temp": 65, "deficit_gdp_target": 3.0, "debtsvc_rev_limit": 15}

# ---- page-level provenance (every warehouse row carries statement + printed_page) ----
def pv(sql):
    r = q(sql)
    if not len(r): return None
    row = r.iloc[0]
    pg = row.get("printed_page")
    return {"statement": (row.get("statement") or "").strip(), "page": (int(pg) if pg is not None and str(pg) != "nan" else None)}
d["prov"] = {
    "perf":       pv("SELECT statement,printed_page FROM fact_financial_performance WHERE source_file ILIKE '2024_%' LIMIT 1"),
    "revenue":    pv("SELECT statement,printed_page FROM fact_revenue WHERE source_file ILIKE '2024_%' AND year=2024 AND level=0 LIMIT 1"),
    "opex":       pv("SELECT statement,printed_page FROM fact_opex_maksud WHERE source_file ILIKE '2024_%' AND year=2024 LIMIT 1"),
    "obj":        pv("SELECT statement,printed_page FROM fact_opex_detail WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='object_aktiviti' LIMIT 1"),
    "devex":      pv("SELECT statement,printed_page FROM fact_devex_project WHERE source_file ILIKE '2024_%' AND row_type='project' LIMIT 1"),
    "debt":       pv("SELECT statement,printed_page FROM fact_debt_issues WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='detail' LIMIT 1"),
    "guarantees": pv("SELECT statement,printed_page FROM fact_guarantees WHERE source_file ILIKE '2024_%' AND year=2024 AND row_type='detail' LIMIT 1"),
}

d = sanitize(d)
out_json = os.path.join(HERE, "data.json")
json.dump(d, open(out_json, "w"), allow_nan=False)
print("data.json:", os.path.getsize(out_json), "bytes; keys:", len(d))

# ---- inject into template -> index.html ----
tpl = open(os.path.join(HERE, "template.html")).read()
html = tpl.replace("__DATA__", json.dumps(d, separators=(",", ":"), allow_nan=False))
assert "__DATA__" not in html, "placeholder not replaced"
open(os.path.join(HERE, "index.html"), "w").write(html)
print("index.html:", os.path.getsize(os.path.join(HERE, "index.html")), "bytes")
