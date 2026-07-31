# Forecast layer — method & assumptions (pilot)

Everything in this folder is a **derived model**, never an audited figure. Rows carry
`basis` (`derived_signature` / `model_projection`), `method`, and `data_through` so they can
never be confused with PKKP actuals. Rebuild: `python3 curated/forecast/build_forecast.py`.

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
