#!/usr/bin/env python3
"""Pilot forecast layer: utilisation signatures + trend projections for FY2025–FY2026.

Run:  python3 apps/models/build_forecast.py
Reads : sources/pkkp/pkkp.duckdb   (rebuild first: python3 pipeline/build_duckdb.py)
Writes: apps/models/fact_utilisation_signatures.csv
        apps/models/fact_projection_headline.csv
        (method & assumptions: _METHOD.md in this folder)

Basis discipline (see CLAUDE.md): everything here is a DERIVED MODEL, never an audited
figure. Every row carries `basis` ('model_projection' / 'derived_signature'),
`method`, `data_through` (the last audited year used), and lo/mid/hi bands where
applicable. These rows must never be blended into audited fact tables, and the
dashboard renders them only with explicit projection styling.

Two products:
1. UTILISATION SIGNATURES — for each operating vote (maksud), the empirical
   distribution of actual/original-budget over FY2010–FY2024 (own-volume years).
   This is the reusable mapping that converts "Budget 202X as tabled" (once the
   Anggaran/MOF sources are ingested with provenance) into expected actuals.
2. HEADLINE TREND PROJECTION — revenue / opex / devex / debt projected to 2025 &
   2026 from their own history (log-growth statistics, 2015–2024 window), with
   p25/p75 growth bands. Honest but weak on turning points — superseded by the
   official MOF Fiscal Outlook figures as soon as sources/mof-fiscal-outlook/ has
   verified data.
"""
import duckdb, os, math, statistics as st
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
con = duckdb.connect(DB, read_only=True)
DATA_THROUGH = 2024

# ---------- 1. utilisation signatures (per operating vote) ----------
u = con.sql("""
SELECT o.maksud_code, dm.name_bm, o.year,
       o.anggaran_asal_rm AS bud, o.sebenar_rm AS act
FROM fact_opex_maksud o
JOIN dim_maksud dm ON dm.maksud_code=o.maksud_code AND dm.year=o.year
WHERE o.source_file ILIKE o.year || '_PENYATA%' AND o.anggaran_asal_rm > 0
""").df()
u["util"] = u.act / u.bud
rows = []
for code, grp in u.groupby("maksud_code"):
    vals = sorted(grp.util)
    rows.append({
        "maksud_code": code,
        "name_bm": grp.name_bm.iloc[-1],
        "n_years": len(vals),
        "util_mean": round(st.mean(vals), 4),
        "util_median": round(st.median(vals), 4),
        "util_p25": round(vals[max(0, int(len(vals)*.25)-1)], 4) if len(vals) >= 4 else None,
        "util_p75": round(vals[min(len(vals)-1, int(len(vals)*.75))], 4) if len(vals) >= 4 else None,
        "util_min": round(min(vals), 4),
        "util_max": round(max(vals), 4),
        "util_std": round(st.pstdev(vals), 4) if len(vals) > 1 else None,
        "chronic_overshoot": st.median(vals) > 1.02,
        "basis": "derived_signature",
        "method": "actual/original-budget per own-volume year, FY2010-FY2024",
        "data_through": DATA_THROUGH,
    })
sig = pd.DataFrame(rows).sort_values("util_median", ascending=False)
sig.to_csv(os.path.join(HERE, "fact_utilisation_signatures.csv"), index=False)

# ---------- 2. headline trend projection 2025–2026 ----------
h = con.sql("""
SELECT year,
  max(CASE WHEN line_code='revenue' THEN amount_rm END)/1e9 rev,
  max(CASE WHEN line_code='opex' THEN amount_rm END)/1e9 opex,
  max(CASE WHEN line_code='devex' THEN amount_rm END)/1e9 devex
FROM fact_financial_performance
WHERE basis='sebenar' AND source_file ILIKE year||'_PENYATA%'
GROUP BY year ORDER BY year
""").df()
debt = con.sql("SELECT year, amount_rm_juta/1e3 debt FROM fact_timeseries_2010_2024 WHERE line_item_bm='Jumlah Hutang Persekutuan' ORDER BY year").df()
h = h.merge(debt, on="year")

proj = []
for series in ("rev", "opex", "devex", "debt"):
    s = h[h.year >= 2015][["year", series]].dropna()
    growths = [math.log(b/a) for a, b in zip(s[series], s[series][1:])]
    g_med = st.median(growths)
    g_lo = sorted(growths)[max(0, int(len(growths)*.25)-1)]
    g_hi = sorted(growths)[min(len(growths)-1, int(len(growths)*.75))]
    last = float(s[series].iloc[-1])
    for k, yr in enumerate((2025, 2026), start=1):
        proj.append({
            "year": yr, "series": series,
            "lo_rm_bil": round(last * math.exp(g_lo*k), 1),
            "mid_rm_bil": round(last * math.exp(g_med*k), 1),
            "hi_rm_bil": round(last * math.exp(g_hi*k), 1),
            "basis": "model_projection",
            "method": "log-growth median & p25/p75, FY2015-FY2024",
            "data_through": DATA_THROUGH,
            "superseded_by": "sources/mof-fiscal-outlook (official) once ingested",
        })
pj = pd.DataFrame(proj)
# derived deficit band (mid revenue vs mid spend; lo/hi crossed for widest honest band)
for k, yr in enumerate((2025, 2026), start=1):
    g = {r["series"]: r for r in proj if r["year"] == yr}
    pj = pd.concat([pj, pd.DataFrame([{
        "year": yr, "series": "deficit",
        "lo_rm_bil": round(g["rev"]["hi_rm_bil"] - g["opex"]["lo_rm_bil"] - g["devex"]["lo_rm_bil"], 1),
        "mid_rm_bil": round(g["rev"]["mid_rm_bil"] - g["opex"]["mid_rm_bil"] - g["devex"]["mid_rm_bil"], 1),
        "hi_rm_bil": round(g["rev"]["lo_rm_bil"] - g["opex"]["hi_rm_bil"] - g["devex"]["hi_rm_bil"], 1),
        "basis": "model_projection", "method": "identity from rev/opex/devex bands",
        "data_through": DATA_THROUGH,
        "superseded_by": "sources/mof-fiscal-outlook (official) once ingested",
    }])], ignore_index=True)
pj.to_csv(os.path.join(HERE, "fact_projection_headline.csv"), index=False)

print(f"signatures: {len(sig)} votes -> fact_utilisation_signatures.csv")
print("chronic overshooters (median util > 102%):")
print(sig[sig.chronic_overshoot][["maksud_code","name_bm","util_median","util_max","n_years"]].head(8).to_string(index=False))
print("\nheadline projection 2025-2026 (RM b, lo/mid/hi):")
print(pj[["year","series","lo_rm_bil","mid_rm_bil","hi_rm_bil"]].to_string(index=False))
