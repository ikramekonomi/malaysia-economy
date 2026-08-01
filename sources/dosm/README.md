# Source: DOSM (Department of Statistics Malaysia) — denominators + machine-readable GFS

Two layers in one namespace:

1. **National denominators** (the original three): annual nominal GDP, population,
   households. Used by `curated/dashboard/` to express audited PKKP figures per-GDP /
   per-capita / per-household.
2. **Expansion (2026-07-31)**: the machine-readable **Government Finance Statistics**
   published on data.gov.my (federal: compiled by JANM, the Accountant General's
   Department; state: by the National Audit Department), plus **state GDP**, **CPI**
   (national + by state, by COICOP division), monthly **labour force** principal
   statistics, and monthly **trade** toplines.

All of it is *external context / reported basis* — never blended into the audited PKKP
tables. GFS-vs-PKKP disagreement is a finding, not something to resolve by overwriting.

## Datasets (CSVs in `data/` are the canonical, as-published files)

### Original denominators (byte-for-byte as downloaded)

| file | dataset (data.gov.my / OpenDOSM) | units | coverage | data vintage |
|---|---|---|---|---|
| `gdp_gni_annual_nominal.csv` | Annual Nominal GDP & GNI: 1947 to Present (`gdp_gni_annual_nominal`) | RM million (`abs` rows); `growth_yoy` rows = % | 1947–2025 | "Data as of 2025" per catalogue page |
| `population_malaysia.csv` | Population — Malaysia (`population_malaysia`) | '000 persons, by sex × age × ethnicity | 1970–2026 | "Data as of 2025" per catalogue page |
| `hh_lq.csv` | Number of Households and Living Quarters (`hh_profile`) | count | 1970–2024 (annual from 2010) | "Data as of 2024" per catalogue page |

### Expansion datasets (values verbatim + appended `retrieved_from`,`retrieved_date` columns)

Ingested by `pipeline/ingest_expansion.py`; dataset id = catalogue id = filename.

| file | title | grain | coverage (data_as_of) | rows |
|---|---|---|---|---|
| `federal_finance_year.csv` | Annual Federal Government Finance (JANM) | annual, RM mil | 1970–2023 | 594 |
| `federal_finance_year_revenue.csv` | Annual Federal Revenue detail | annual | 1970–2023 | 1,134 |
| `federal_finance_year_oe.csv` | Annual Federal OE by Object | annual | 1979–2023 | 495 |
| `federal_finance_year_de.csv` | Annual Federal DE by Function | annual | 1970–2023 | 756 |
| `federal_finance_qtr.csv` | Quarterly Federal Government Finance | quarterly | 1996–**2024-Q1** | 1,243 |
| `federal_finance_qtr_revenue.csv` | Quarterly Federal Revenue detail | quarterly | 1996–2024-Q1 | 2,373 |
| `federal_finance_qtr_oe.csv` | Quarterly Federal OE by Object | quarterly | 1996–2024-Q1 | 1,111 |
| `federal_finance_qtr_de.csv` | Quarterly Federal DE by Function | quarterly | 1996–2024-Q1 | 1,582 |
| `lookup_federal_finance.csv` | Lookup: federal finance variable labels (EN/BM) | — | — | 57 |
| `state_finance_revenue.csv` | State Government Revenue (AUDIT) | annual, by state | **2020–2022** | 52 |
| `state_finance_expenditure.csv` | State Government Expenditure (AUDIT) | annual, by state | 2020–2022 | 104 |
| `gdp_state_real_supply.csv` | Annual Real GDP by State & Sector (2015 prices) | annual | 2015–2025 | 2,163 |
| `cpi_headline.csv` | Monthly CPI by Division (overall = headline + 13 divisions) | monthly | 1980-01–2026-06 | 7,812 |
| `cpi_state.csv` | Monthly CPI by State & Division | monthly | 2010-01–2026-06 | 44,352 |
| `lfs_month.csv` | Monthly Principal Labour Force Statistics | monthly | 2010-01–2026-05 | 197 |
| `trade_headline.csv` | Headline Monthly Trade in Goods (abs + growth series) | monthly | 2000-01–2026-04 | 743 |
| `trade_sitc_1d.csv` | Monthly Trade by SITC Section (1-digit) | monthly | 2000-01–2026-05 | 3,487 |

Catalogue findings (2026-07-31, via github.com/data-gov-my/datagovmy-meta + the APIs):

- **No consolidated general-government GFS** dataset exists in the catalogue — federal
  and state are separate; consolidation would be a `curated/` task.
- **Quarterly federal GFS stops at 2024-Q1** (JANM has not updated it since
  2024-05-31); the annual files stop at 2023. BNM's MSB 3.1.x (sources/bnm) is the
  live quarterly series.
- **State finance covers 2020–2022 only** — a short, seemingly one-off publication
  (next_update "—"), which is exactly why state financial statements remain a priority
  source (docs/SOURCES.md). Units: RM million; state revenue detail by receipt-code
  category (`revenue_60000` etc.), expenditure split oe/de.
- State GDP exists in **real (2015 prices) terms only**; no nominal state GDP dataset.
- Deferred for a future decision (sizes as of retrieval): `cpi_3d` 188 KB / `cpi_4d`
  424 KB / `cpi_5d` 790 KB, `trade_enduse_bec` 597 KB, `gdp_district_real_supply`
  461 KB. Trade at full commodity detail (SITC 2d+/HS) is **not in this catalogue**
  (METS portal territory).

### What was NOT ingested, and why (documented gap, not a silent one)

Everything targeted in the brief landed. The following catalogue entries were
deliberately left out of this pass — all are reachable, none failed:

| dataset(s) | why not ingested |
|---|---|
| `cpi_3d`, `cpi_4d`, `cpi_5d` (CPI at group/class/subclass) | budget: division-level (`cpi_headline`, `cpi_state`) covers the fiscal use case; deeper tiers are 188 KB / 424 KB / 790 KB, a future decision |
| `trade_enduse_bec` (retained imports by end-use), SITC 2-digit+ | topline ingested (`trade_headline`, `trade_sitc_1d`) per the brief's "topline now, report the size" instruction; BEC file is 597 KB |
| `gdp_district_real_supply` (GDP by district) | 461 KB; state grain is what the warehouse needs today |
| `cpi_*_inflation`, `cpi_core*`, `cpi_lowincome`, `cpi_strata`, `ppi*`, `sppi*` | derived/parallel price series, not required for fiscal work |
| `lfs_qtr*`, `lfs_year*`, `lfs_district`, `lfs_dun`, `lfs_parlimen`, `employment_sector` | monthly principal indicators (`lfs_month`) are the briefed set |
| `gdp_qtr_*`, `gdp_annual_*` (24 further GDP cuts) | `gdp_gni_annual_nominal` remains the warehouse denominator; mixing vintages across GDP datasets is a known caveat (below) |

No dataset in the fiscal/GFS/state-GDP/CPI/labour/trade scope 404'd or timed out.

## Provenance

- Original three: retrieved **2026-07-31** from DOSM's own object storage (the
  catalogue pages' download links):
  - https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv
  - https://storage.dosm.gov.my/population/population_malaysia.csv
  - https://storage.dosm.gov.my/demography/hh_lq.csv
- Expansion datasets: retrieved **2026-07-31** from the same storage layer
  (storage.dosm.gov.my for DOSM datasets, storage.data.gov.my/publicadmin for the
  JANM/AUDIT government-finance datasets); the exact URL is on **every row**
  (`retrieved_from`), alongside `retrieved_date`.
- Catalogue pages: https://open.dosm.gov.my/data-catalogue/<id> (OpenDOSM datasets) and
  https://data.gov.my/data-catalogue/<id> (federal/state finance).
- License: Creative Commons Attribution 4.0 (per catalogue pages).
- The original three CSVs are byte-for-byte as downloaded; the expansion CSVs are the
  downloaded files with **only** the two provenance columns appended (source values
  verbatim). **Never edit any of them**; re-download to refresh (that is a new vintage:
  update this README's retrieval date and vintages).

## Keeping it fresh (updates are pulled, never silent)

The warehouse pins a retrieval vintage on purpose — an upstream revision changing every
%GDP ratio silently would break provenance. To detect and apply DOSM updates:

- `python3 sources/dosm/pipeline/refresh.py` — **check** (safe): compares the OpenDOSM
  static API metadata (`data_as_of`, `last_updated` via
  `api.data.gov.my/opendosm?id=…&meta=true`) and the storage ETag against the recorded
  baseline in `data/_vintage.json`; exits non-zero if a new vintage exists.
- `python3 sources/dosm/pipeline/refresh.py --apply` — pulls the new vintage with a
  row-level diff report, updates `_vintage.json`, rebuilds the derived denominators and
  re-runs the API cross-check. Then update the vintage table above, rebuild the
  dashboard, and commit the refresh as its own change.
- `python3 sources/dosm/pipeline/verify_against_api.py` — independent value-level
  cross-check of the original three CSVs against the API (same publication, second door).
- `python3 sources/dosm/pipeline/verify_expansion.py` — same second-door discipline for
  the expansion datasets: per dataset, row count vs the API total plus a field-by-field
  comparison of every row in the latest period → `data/_validation_expansion.csv`.
- `python3 sources/dosm/pipeline/crosscheck_state_finance.py` — reported vs audited
  state finances → `data/_crosscheck_state_finance_vs_audited.csv` (see the gap
  finding below).

API endpoints used: `https://api.data.gov.my/opendosm?id=<id>` for OpenDOSM datasets
and `https://api.data.gov.my/data-catalogue?id=<id>` for the federal/state finance
datasets (both accept `&meta=true` for vintage metadata and `&limit=` for bulk reads);
canonical files come from `https://storage.dosm.gov.my/<domain>/<file>.csv` and
`https://storage.data.gov.my/publicadmin/<file>.csv`. Catalogue enumeration:
`github.com/data-gov-my/datagovmy-meta` (`data-catalogue/*.json`, 291 datasets).

`refresh.py` watches **all 20 datasets** (the three originals byte-for-byte, the 17
expansion datasets through `ingest_expansion.py`'s provenance-appending writer) — so
the weekly Routine now covers the whole set.

Per the API, the next scheduled DOSM releases are recorded in `data/_vintage.json`
(`next_update` per dataset).

## Derived output

`pipeline/build_denominators.py` regenerates `curated/dashboard/external_denominators.csv`
(unit conversions only: RM mil → RM bil, '000 → mil, count → mil; GDP total = `sector p0`
equivalent headline `gdp` column, population = `both`/`overall`/`overall` rows). Households
are absent after 2024 in the source and are left blank, never interpolated.

## Gap finding: DOSM/data.gov.my state finance vs the AUDITED state accounts

The state-level analogue of the BNM-vs-PKKP federal triangulation. Two independent
publications of the same concept: data.gov.my's `state_finance_*` (RM million, one
year per state — 2022 for twelve states, 2020 for Sarawak) versus the states' own
audited accounts in `sources/states`
(`data/_national/fact_state_finance_all.csv`). Produced by
`pipeline/crosscheck_state_finance.py` →
`data/_crosscheck_state_finance_vs_audited.csv` (138 comparisons:
**102 MATCH, 4 CLOSE, 25 DIVERGENT, 7 NO_AUDITED**). Neither side is corrected.

**The reported side is internally clean.** All 39 of DOSM's own identities hold
exactly: revenue components (60000/70000/80000) = revenue total; OE objects
(10000–50000) = OE total; OE + DE = expenditure total.

**Revenue and DE agree almost everywhere** (RM million):

| state | yr | DOSM rev | audited rev | verdict | DOSM DE | audited DE | verdict |
|---|---|---|---|---|---|---|---|
| Johor | 2022 | 1,547.79 | 1,630.64 | **DIVERGENT** −5.1 % | 735.57 | 735.57 | MATCH |
| Kedah | 2022 | 597.17 | 596.17 | MATCH | 145.00 | 173.54 | **DIVERGENT** −16.5 % |
| Kelantan | 2022 | 983.42 | — | NO_AUDITED | 360.23 | — | NO_AUDITED |
| Melaka | 2022 | 452.75 | 452.74 | MATCH | 77.31 | 77.31 | MATCH |
| Negeri Sembilan | 2022 | 521.22 | 521.22 | MATCH | 114.91 | 114.91 | MATCH |
| Pahang | 2022 | 1,288.03 | 1,288.03 | MATCH | 118.27 | 118.27 | MATCH |
| Perak | 2022 | 1,093.75 | 1,093.74 | MATCH | 343.07 | 267.32 | **DIVERGENT** +28.3 % |
| Perlis | 2022 | 152.00 | 151.99 | MATCH | 58.10 | 58.10 | MATCH |
| Pulau Pinang | 2022 | 595.06 | 595.06 | MATCH | 225.72 | 225.72 | MATCH |
| Sabah | 2022 | 6,960.59 | 7,319.13 | **DIVERGENT** −4.9 % | 1,381.03 | 1,375.33 | MATCH |
| Sarawak | 2020 | 10,646.69 | 10,646.69 | MATCH | 5,446.96 | 5,446.96 | MATCH |
| Selangor | 2022 | 2,533.83 | 2,533.83 | MATCH | 1,019.54 | 1,025.61 | CLOSE |
| Terengganu | 2022 | 1,778.54 | 1,778.53 | MATCH | 1,031.46 | 1,046.84 | CLOSE |

**The real finding is operating expenditure: DOSM's `oe` is not a single concept.**
The state accounts carry several OE presentations, and DOSM's `oe` matches a
*different* one state by state — so the column is not comparable across states as
published:

| DOSM `oe` matches… | states |
|---|---|
| `opex_before_transfer` exactly | Negeri Sembilan, Perak, Sabah, Selangor, Terengganu |
| `opex_total` / `opex_total_by_maksud` exactly | Johor, Kedah, Melaka, Pahang |
| **no audited OE concept** | Perlis (−4.4 %), Pulau Pinang (−13.5 %), Sarawak |
| no audited data at all | Kelantan (FY2022 absent from the audited panel) |

Two specific anomalies, both left exactly as published:

- **Sarawak 2020** — DOSM's `oe` is **10,646.688**, byte-identical to DOSM's own
  *revenue* total for Sarawak. The audited figures are 4,430.06
  (`opex_before_transfer`) and 10,280.06 (`opex_total`). This looks like an
  upstream duplication error in the reported dataset, not a definitional
  difference.
- **Sarawak 2020 non-revenue receipts** — DOSM 279.09 vs audited 30.75. DOSM's three
  revenue components sum to its total, so the audited panel's
  `revenue_nonrevenue_receipts` is the outlier here (the 248.34 gap is exactly the
  residual): a question for `sources/states`, not for DOSM.

Read-across: at state level the *reported* statistics agree with the audited accounts
on revenue and development expenditure, but **operating expenditure cannot be
compared across states from the reported source alone** — which is precisely the
argument for the audited state financial statements being the canonical layer.

## Validation — expansion datasets (2026-07-31 ingest)

`data/_validation_expansion.csv`: 34 checks (17 datasets × row-count + latest-period /
full-content), **0 FAIL, 1 INFO**. The INFO is a genuine upstream divergence, kept as
found: the API's copy of `lookup_federal_finance` still codes the financing block as
`borrowing`/`borrowing_dom_gross`… while the storage CSV (and the actual data files)
use `financing`/`domestic_gross`… — a stale API-side lookup, documented in
`verify_expansion.py`, never corrected.

## Validation — original three (2026-07-31 ingest)

- CSV downloads match the parquet mirrors of the same datasets (date-key join: 0 mismatches).
- Internal cross-check: `gdp_capita` as printed vs `gdp ÷ population` recomputed from the
  population dataset agrees to ≤0.03 % (rounding) for 2009–2025 — the two datasets are
  mutually consistent.
- vs the retired provisional numbers (`external_denominators.csv` before this ingest):
  GDP differences ≤ 0.28 % (vintage revisions, e.g. 2023 1819.0 → 1824.0,
  2022 1791.1 → 1793.9); population ≤ 0.98 % (largest at 2013); households up to
  **5.9 %** higher across 2020–2024 (the provisional series had not applied the 2020
  Census rebase). The provisional values were replaced wholesale, not merged.

## Known caveats

- GDP & population 2025 values and population 2026 are DOSM current estimates/projections
  (vintage above), subject to revision at the next annual release.
- `gdp_annual_nominal_supply` (sectoral dataset) carries slightly different totals for the
  same years (e.g. 2024: 1,933,209.415 vs 1,932,291.49 RM mil here) — different revision
  vintages between catalogue datasets. This source uses `gdp_gni_annual_nominal` throughout;
  do not mix the two.
- Households series is census-benchmarked at 1970/1980/1991/2000/2010/2020; intervening
  years are DOSM intercensal estimates (their methodology note, not ours).
