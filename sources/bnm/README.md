# Source: Bank Negara Malaysia — SCAFFOLD, fiscal series not machine-reachable

Higher-frequency (monthly) federal government finance, debt and public-sector
statistics — the Tier-2 cross-check for PKKP annual actuals (docs/SOURCES.md).

## Status (2026-07-31): egress open; API live but carries no fiscal series; site WAF-blocked

- **BNM OpenAPI** (`api.bnm.gov.my`, header `Accept: application/vnd.BNM.API.v1+json`)
  is reachable and serves rates/FX/kijang-emas resources — probed for fiscal
  endpoints (`msb`, `government-finance`, `public-finance`, `fiscal`, auction data):
  all 404. The Monthly Statistical Bulletin tables (federal government finance) are
  **not in the API**.
- **www.bnm.gov.my** (where the MSB XLS/CSV files live) sits behind a JS-challenge
  WAF (HTTP 202 interstitial) that non-browser clients cannot pass, and browser
  traffic cannot traverse this environment's egress proxy.

## Ways in

1. Supply the MSB "Government finance" table files (XLS/CSV, monthly) via a GitHub
   repo and attach it — smallest useful set: Table 3.x federal government revenue,
   expenditure and financing, plus federal debt outstanding.
2. Retry from an environment whose egress path carries browser traffic.

## Planned first use

Monthly revenue/expenditure profile → within-year utilisation curves (sharpening the
FY2025 nowcast), and an independent debt-outstanding series to cross-check the PKKP
debt register and the stock-flow model in `curated/forecast/`.
