# Source: Bank Negara Malaysia — MSB tables via BNM OpenAPI

Federal government finance, federal debt, and the wider monetary / banking / markets /
external statistics, machine-read from the **BNM OpenAPI** (no WAF, no manual
downloads): `api.bnm.gov.my/public/msb/<table>[/year/<year>]` with header
`Accept: application/vnd.BNM.API.v1+json`. Catalogue discovered via
`api.bnm.gov.my/api/specification/categories`, per-table detail via
`api.bnm.gov.my/api/specification/tag?name=<tag>` (portal: apikijangportal.bnm.gov.my).

## Status: INGESTED via API (2026-07-31); www.bnm.gov.my file downloads unnecessary

**32 tables, 8,106 data rows.** Two fetchers: `pipeline/fetch_bnm_fiscal.py` owns the
fiscal 3.1.x set; `pipeline/fetch_bnm_msb_wide.py` owns everything else.

### Fiscal (3.1.x) — quarterly + annual

| table | content | coverage |
|---|---|---|
| `msb_3_1.csv` | Federal Government Finance (quarterly: revenue, opex, current balance, gross/net DE, financing) | 1996–1Q2026 |
| `msb_3_1_1.csv` | Federal Government Revenue (components) | 1996–2026 |
| `msb_3_1_2.csv` | Operating Expenditure by Object | 1996–2026 |
| `msb_3_1_3.csv` | Development Expenditure by Function | 1996–2025 |
| `msb_3_1_4.csv` | Federal Debt by Remaining Maturity | 2008–2026 |
| `msb_3_1_5.csv` | Federal Domestic Debt **by Holder** | 2008–2026 |
| `msb_3_1_6.csv` | Federal Debt by Currency & Remaining Maturity | 1999–2026 |

**Grain finding:** the 3.1.x tables serve **quarterly + annual only** — no monthly
rows exist for them at any year (`period` is `1Q`…`4Q` or null; there is no
`month_dt` field). The brief's hoped-for monthly fiscal grain is a genuine source
absence, not a fetch gap. The wider tables below *are* monthly.

### Monetary & banking (1.x) — monthly + annual

| table | content | coverage | rows |
|---|---|---|---|
| `msb_1_1.csv` | Reserve Money | 1975–2026 | 392 |
| `msb_1_2.csv` | Currency in Circulation by Denomination | 1975–2026 | 368 |
| `msb_1_3.csv` | Monetary Aggregates M1, M2, M3 | 2013–2026 | 161 |
| `msb_1_3_1.csv` | Broad Money M3 (components) | 2013–2026 | 161 |
| `msb_1_3_2.csv` | Factors Affecting M3 | 2013–2026 | 161 |
| `msb_1_4.csv` | BNM: Statement of Assets | 1975–2026 | 392 |
| `msb_1_5.csv` | BNM: Statement of Capital & Liabilities | 2013–2026 | 172 |
| `msb_1_7.csv` | Banking System: Statement of Assets (by bank type) | 2013–2026 | 644 |
| `msb_1_9.csv` | Banking System: Capital & Liabilities (by bank type) | 2013–2026 | 644 |
| `msb_1_10.csv` | Loan/Financing Applied by Purpose | 2021–2026 | 236 |
| `msb_1_12.csv` | Loan/Financing Approved | 2021–2026 | 236 |
| `msb_1_14.csv` | Loan/Financing Disbursed by Purpose | 2021–2026 | 236 |
| `msb_1_18.csv` | Loan/Financing by Type | 2021–2026 | 236 |
| `msb_1_24.csv` | Total Deposits by Type | 2007–2026 | 233 |
| `msb_1_25.csv` | Total Deposits by Holder | 2007–2026 | 233 |

### Financial & capital markets (2.x)

| table | content | coverage | rows |
|---|---|---|---|
| `msb_2_1.csv` | Interest Rates: Banking Institutions | 1980–2026 | 399 |
| `msb_2_3.csv` | Interest Rates: Interbank Money Market | 2004–2024 | 41 |
| `msb_2_4.csv` | Interest Rates: Treasury Bills & BNM Bills | 1980–2026 | 411 |
| `msb_2_5.csv` | Market Indicative Yield: MGS | 1993–2026 | 266 |
| `msb_2_6.csv` | Exchange Rates: Malaysian Ringgit (avg + end-period) | 1970–2026 | 409 |
| `msb_2_9.csv` | Funds Raised in the Capital Market (Public Sector) | 1970–2026 | 277 |
| `msb_2_10.csv` | Funds Raised in the Capital Market (Private Sector) | 1970–2026 | 277 |

### External sector (3.x)

| table | content | coverage | rows |
|---|---|---|---|
| `msb_3_2.csv` | RENTAS: Foreign Holdings in Debt Securities & Sukuk | 2011–2026 | 185 |
| `msb_3_7.csv` | External Debt (quarterly) | 2009–2026 | 86 |
| `msb_3_8.csv` | External Reserves | 1990–2026 | 377 |

### Catalogue enumeration and what did NOT land

`api.bnm.gov.my/api/specification/categories` returns **11 categories**: Rates and
Volumes (16 tags), Monetary and Banking (78 MSB tags), Financial and Capital Markets
(19), External Sector and Macroeconomic Indicators (72), Insurance and Takaful (60),
Other Indicators (2), Financial Inclusion (15), Payment Statistic (5), Government
Securities (2), IIMM (7), Bond Info Hub (44), FAST (24).

Ingested here: the fiscal set plus the monetary / banking / markets / external tables
listed above. Documented gaps:

| not ingested | reason |
|---|---|
| **`3.6.2` External Trade** | **In the catalogue and the OpenAPI spec, but serves NO data**: `/msb/3.6.2/year/<y>` returns empty for every year 2000–2026 and `/msb/3.6.2` (latest) 404s. A real dead endpoint — DOSM `trade_headline` (sources/dosm) covers the concept instead. |
| `1.*a`, `1.*b`, `2.*a`, `3.*a` (discontinued variants) | superseded presentations the catalogue itself marks "(discontinued)" |
| `1.11`, `1.13`, `1.15`, `1.16`, `1.17`, `1.19`–`1.23`, `1.27`–`1.32.x` | further banking-system cuts (by sector, impairment, capital, Islamic sub-tables); the purpose/type cuts ingested cover the credit-aggregate use case |
| `3.3`–`3.5.15` (GDP, IPI, CPI, labour, house prices) | BNM re-publishes DOSM statistics; the warehouse takes those from DOSM directly (sources/dosm) rather than second-hand |
| `3.6.x` (BoP, FDI, portfolio, IIP) | out of scope for this pass |
| Insurance & Takaful (4.x), Financial Inclusion, Payments, IIMM, Bond Info Hub, FAST | out of scope for public-finance work |

`2.3` is thin by design (41 rows, 2004–2024 — the API serves at most 2 rows/year and
nothing after 2024).

Values verbatim as served (RM million unless the table states otherwise); every row
carries endpoint + retrieval date + the API's own `last_updated`. Refresh = re-run
`pipeline/fetch_bnm_fiscal.py` and `pipeline/fetch_bnm_msb_wide.py` (explicit,
provenance-updating — same discipline as sources/dosm).

## Vintages (`data/_vintage_log.csv`, golden rule 8)

Every BNM file in `data/` is the current vintage. `data/_vintage_log.csv` lists every vintage the
warehouse has held (dataset, `api_last_updated`, retrieved date, rows, sha256, state), append-only;
it was seeded on 2026-11-04 with the 32 files then held. The fetchers write through
`pipeline/vintage.py`'s `replace_with_log`: when a refetch changes the bytes, the old file is
logged `superseded` and the new one `current`; an identical refetch logs nothing. An earlier
vintage is recovered exactly from git history by its sha256 (the DOSM method,
`sources/dosm/pipeline/vintage_get.py`).

## Basis discipline (why this is namespaced, never blended)

The **fiscal aggregates (3.1–3.1.3) are BNM-compiled from MOF/AGD** — a *reported*
basis, not the source of truth; PKKP (audited) and the budget books stay canonical for
annual figures. The **debt tables (3.1.4–3.1.6)** are closer to BNM's own
administrative domain (it is the government's fiscal agent). Cross-source
disagreement is a finding, not something to resolve by overwriting.

## Validation (`pipeline/validate_bnm.py` → `data/_validation_bnm.csv`)

**279 checks: 0 FAIL.** The original fiscal suite is unbroken —
**196/196** (192 PASS + 4 INFO; the fifth INFO, a comparison with our own model nowcast,
moved out with the model to `apps/models/` on 2026-11-04); the expansion adds 83 checks (V4–V7) covering the
wider tables, of which 34 are PASS and 49 record a **SOURCE_DIVERGENCE**.

`SOURCE_DIVERGENCE` ≠ FAIL. The CSVs are the API verbatim, so an identity that does
not close is BNM's own printed inconsistency — recorded with both figures, never
corrected (golden rule 2). `FAIL` stays reserved for pipeline defects; there are none.
Tolerance is RM2.5 million (BNM prints components rounded to RM1m, so a sum of many
components legitimately drifts a couple of million).

### V1–V3 — the original fiscal suite (196 checks)

- Internal: quarterly balance = revenue − opex (BNM serves the balance rounded to RM1m).
- **Triangulation:** BNM annual sums equal audited PKKP revenue / opex / DE to within
  RM1–2 million for every year FY2010–FY2024. BNM's DE follows PKKP's
  performance-statement presentation (which differs from the by-vote register in
  2019–2020 — an intra-PKKP presentational difference, documented in the validator).
- **FY2025 measured** (sum of four quarters, all now published) vs the official
  revised estimates: revenue **336.07** vs 334.12; opex **330.78** vs 332.15; gross DE
  **81.92** vs 80.0; overall deficit **−75.29 vs −76.71** (RM bil) — the year landed
  slightly better than MOF's own revision, and well below our model's nowcast OE mid
  (343.6, `apps/models/fact_nowcast_2025.csv`), i.e. FY2025 broke the historical overshoot pattern. Audited PKKP 2025 will
  adjudicate finally.

### V4 — component-vs-total identities inside each table (33 checks)

Every table that prints subtotals is checked row by row: revenue by tax class
(3.1.1), OE by object (3.1.2), DE by function (3.1.3), debt by maturity / holder /
currency (3.1.4–3.1.6), reserve money both ways (1.1: components **and** the
factors-affecting decomposition), the M1→M2→M3 ladder (1.3), and net international
reserves = gross reserves − external liabilities (3.8).

All identities close on all rows except these, which are BNM's own:

| identity | rows off | worst case |
|---|---|---|
| 3.1.1 revenue total vs its four blocks | 2 of 151 | 2023 1Q/2Q, ±RM11.6 mil (offsetting) |
| 3.1.3 DE total vs its four blocks | 2 of 150 | **2018 annual: printed total 62,430.6 vs components 56,360.3 — RM6.07 bil** |
| 3.1.5 MGS holders vs subtotal | 3 of 91 | ±RM40 mil |
| 3.1.5 MGII holders vs subtotal | 1 of 91 | RM150 mil |

1.1 (both decompositions, 392 rows), 1.3, 3.8, 3.1.2, 3.1.4, 3.1.6 close everywhere.

### V5 — fiscal grain consistency, quarterly vs annual (24 checks)

Every numeric column, every year: annual row = Σ quarters for the flow tables
(3.1–3.1.3), annual row = 4Q for the stock tables (3.1.4–3.1.6). 2,424 column-years
compared; 18 diverge, concentrated in **3.1.5** (13 — holder reclassifications between
the quarterly and annual vintages, e.g. 2018 MGS banks/foreign holders shift
RM3.6 bil between two lines while the total holds) and the same **2018 DE**
discrepancy above. 3.1.2 (286) and 3.1.4 (360) are clean throughout. 3.1.6 yields
**no** comparisons — the API serves it with no annual row alongside a 4Q row, so
there is nothing to reconcile (an absence, not a pass).

### V6 — monthly grain consistency for the wider tables (20 checks)

Annual row = December for stock tables, = Σ months for flow tables. 2,265
column-years: 1.1, 1.2, 2.6 (end-period columns only — the annual *average* columns
are legitimately not December), 2.9 and 3.8 are **completely clean**; 1.4/1.5
(BNM's own balance sheet) diverge on 4 columns each — 2019 total assets/liabilities
458,967 annual vs 451,600 December, a genuine year-end adjustment — and 2.10 on 4
corporate-bond columns in 2012 (RM40 mil).

### V7 — banking-system institution-type identities (6 checks)

Tables 1.7, 1.9, 1.10, 1.12, 1.14, 1.18 are served with a Commercial / Islamic /
Investment bank breakdown plus a printed Total row per month. Total = Σ the three
institution rows, checked on every numeric column: **15,805 cell-level comparisons,
100 % clean.** This is the strongest internal evidence that the wide fetch is
faithful.
