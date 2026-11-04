# Models — method & assumptions (pilot)

**This folder is an application on top of the warehouse, not warehouse data** (docs/DATA_MODEL.md
§13.1). It moved here from `curated/forecast/` on 2026-11-04. Its own supersession rule has
fired: MOF's official figures (Tinjauan Fiskal 2019–2027, FY2025 actuals included) are now in
`sources/mof-fiscal-outlook/`, so these models are cross-checks only. Nothing in `curated/`
or `site/` reads them.

Everything in this folder is a **derived model**, never an audited figure. Rows carry
`basis` (`derived_signature` / `model_projection`), `method`, and `data_through` so they can
never be confused with PKKP actuals. Rebuild: `python3 apps/models/build_forecast.py`.

## 1. `fact_utilisation_signatures.csv`
For each operating vote (`maksud`): the empirical distribution of
`actual (sebenar) / original budget (anggaran asal)` across its own-volume years,
FY2010–FY2024 (n, mean, median, p25/p75, min/max, std, and a `chronic_overshoot` flag at
median > 102%). **Purpose:** the reusable mapping that turns "Budget 202X as tabled" into
expected actuals once the Anggaran / MOF sources are ingested. Notable signatures: B.12
statutory-fund transfers median 198% of budget; B.04 Election Commission median 121% with a
474% max (election years); B.11 Treasury general services (subsidies) max 596%.

## 2. `fact_projection_headline.csv`
Revenue / operating / development / debt projected to FY2025–FY2026 from their own audited
history: median log-growth (FY2015–FY2024 window) for the central path, p25/p75 of annual
log-growths for the band; deficit derived by identity from the component bands (crossed for
the widest honest band). **Known weaknesses (by design, documented rather than hidden):**
trend models miss turning points (a 2020-style shock, a subsidy reform, a commodity swing);
the debt band ignores financing composition; bands are historical-quantile, not predictive
intervals. **Supersession rule:** the moment `sources/mof-fiscal-outlook/` (official
government projections) or `sources/anggaran/` (Budget as tabled) contains verified,
provenance-carrying figures, those become the displayed 2025–26 numbers and this model is
demoted to a cross-check ("does the official projection sit inside the historical band?").

## 3. `fact_nowcast_2025.csv` (built by `build_nowcast_2025.py`)
FY2025 expected actuals per operating vote: verified Budget 2025 as tabled
(`sources/anggaran/data/2025/`, maksud grain, crosswalked to PKKP codes) x that vote's own
utilisation quantiles from §1 (p25/median/p75 of actual vs original budget, FY2010-FY2024).
`basis=model_projection`. Votes without usable PKKP history (2 of 54: no signature or new
vote) fall back to ratio 1.0, flagged `fallback_no_history`. The TOTAL_OE row sums the
per-vote quantiles (a conservative envelope, not a joint distribution). Read: the
signatures imply expected FY2025 OE outturn ~RM343.6b (p25 RM323.4b / p75 RM369.2b)
against the RM335.0b tabled budget — history says the tabled OE budget under-states
outturn (median vote utilisation > 1) — while MOF's own Budget-2026-edition revision is
RM332.15b, inside the band but below the signature median. FY2025 audited actuals will
adjudicate.

## 4. `fact_projection_detail.csv` + `fact_gap_projection.csv` (built by `build_forecast2026.py`)
Every dashboard series estimated to FY2025-FY2026 so the whole dashboard can run to 2026.

**Model families considered (brainstorm), and why the hybrid won:**
- *Pure univariate trend (ETS/ARIMA/log-growth) per series* — rejected as the sole method:
  n=15 annual points, misses turning points, and lets components drift away from their
  own totals (violates accounting identities).
- *Pure share/compositional models* — right for components, but need an anchor.
- *Driver-based structural models* (elasticities to GDP, effective interest rate x debt
  stock) — attractive but demands assumptions we cannot source-verify; deferred.
- *Judgemental copy of official figures only* — respects sources but leaves component
  charts empty and carries no uncertainty.
- **Chosen: hierarchical anchor-and-share with identity constraints.** Aggregates are
  pinned to the best available basis in this order: official MOF projection > tabled
  budget x utilisation signature > stock-flow identity > own-history quantile growth.
  Components are modelled as shares of their anchor and re-normalised so identities
  hold by construction. Bands are historical p25/p75 quantiles — honest spread, not
  confidence intervals.

**Per group:** headline mids = official MOF (band = §2 trend band around them); debt =
stock-flow `debt_t = debt_{t-1} + |deficit_t| + ε` with ε quantiles from FY2015-24
residuals (band conditional on the official deficit path — deficit uncertainty is shown
separately, not propagated); revenue composition & OE object classes = 5-year share
quantiles normalised to official anchors (FY2015 excluded: OCR-provisional); emoluments
2025 = tabled Budget-2025 emoluments x aggregate-OE utilisation quantiles; pensions /
debt service = tabled T.14/T.13 x their own vote signatures; functions and the per-vote gap use
each year's own tabled budgets x utilisation signatures (Budget 2025 and — since the
AP2026 book was ingested — the real tabled Budget 2026 figures; the earlier
uniform-growth scaling layer is retired). Function totals are deliberately NOT
normalised to official OE, preserving the historical overshoot bias (difference
reported in `_validation_projection_2026.csv`). Revenue-composition and investment
mids are the official Anggaran Hasil estimates by kod section (`sources/anggaran-hasil`),
with share-quantile bands; contingent items = own log-growth quantiles.

**Known weaknesses (by design, documented):** quantile bands understate tail risk
(2020-style shocks); the 2026 per-vote budget scaling is uniform; investment income is
modelled only as a min/max share band; no policy reaction function. Supersession: any
newly ingested official/budget source replaces the corresponding model rows.

## Official cross-check (2026-07-31)
`official_vs_model_2025_26.csv`: 12 of 13 comparable official Fiscal Outlook figures for
2025-26 fall INSIDE the §2 model bands. The exception is federal debt 2025, where the
official number is an end-June level and the model band is year-end — not directly
comparable. Per the supersession rule the official figures are now the displayed 2025-26
numbers; §2 is demoted to the cross-check shown in that CSV.

## Dashboard rule
Projection rows may only be rendered with explicit projection styling (dashed/cone +
"model projection, unaudited" labelling), mirroring the pension-simulator treatment. They
are not yet wired into the dashboard: per the warehouse-first rule, the 2025–26 view ships
when the official `budgeted`/`projected` bases land together.
