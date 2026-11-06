# Source: DOSM (Department of Statistics Malaysia) — denominators, GFS, and the real economy

Three layers in one namespace — **110 datasets, 230,104 rows** (CSV records, not file lines):

1. **National denominators** (the original three): annual nominal GDP, population,
   households: the denominators for expressing audited PKKP figures per-GDP /
   per-capita / per-household.
2. **Expansion (2026-07-31)**: the machine-readable **Government Finance Statistics**
   published on data.gov.my (federal: compiled by JANM, the Accountant General's
   Department; state: by the National Audit Department), plus **state GDP**, **CPI**
   (national + by state, by COICOP division), monthly **labour force** principal
   statistics, and monthly **trade** toplines.
3. **Real economy (2026-08-01)**: 90 datasets / 143,859 rows — national accounts at
   full detail, the Household Income & Expenditure Survey family (income, **Gini**,
   poverty, the percentile distribution), labour depth and productivity, the monthly
   activity indices, and trade by end-use. This is the outcome side: what an economic
   agenda is actually judged on. See **[the real-economy set](#the-real-economy-set-2026-08-01)**.

All of it is *external context / reported basis* — never blended into the audited PKKP
tables. GFS-vs-PKKP disagreement is a finding, not something to resolve by overwriting.

> **Reading the real-economy layer:** it is survey data, not audited accounts. Before
> differencing anything across time, read `data/_series_breaks_dosm.csv` — 18 registered
> discontinuities, including the 2019 poverty-line revision that moves the absolute
> poverty rate from 0.4% to 5.6% with no change in household welfare.

## Datasets (CSVs in `data/` are the canonical, as-published files)

### Original denominators (byte-for-byte as downloaded)

| file | dataset (data.gov.my / OpenDOSM) | units | coverage | data vintage |
|---|---|---|---|---|
| `gdp_gni_annual_nominal.csv` | Annual Nominal GDP & GNI: 1947 to Present (`gdp_gni_annual_nominal`) | RM million (`abs` rows); `growth_yoy` rows = % | 1947–2025 | "Data as of 2025" per catalogue page |
| `population_malaysia.csv` | Population — Malaysia (`population_malaysia`) | '000 persons, by sex × age × ethnicity | 1970–2026 | "Data as of 2025" per catalogue page |
| `population_state.csv` | Population — state (`population_state`) | '000 persons, by sex × age × ethnicity, 16 states and FTs | 1970–2026 | added 2026-11-04 (Phase 1 denominator); `pipeline/verify_population.py`: states sum to Malaysia, male + female = both |
| `population_district.csv` | Population — district (`population_district`) | '000 persons, by sex × age × ethnicity, 166 districts | 2020–2026 | added 2026-11-04; districts sum to their state every year (within 0.05 thousand rounding per part) |
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

### What the 2026-07-31 expansion pass deferred

Everything targeted in that brief landed; the entries below were deliberately left out
of it. **Most were subsequently ingested by the real-economy pass** — the still-open
ones are consolidated in [what the real-economy pass deferred](#what-the-real-economy-pass-deferred).

| dataset(s) | status |
|---|---|
| `cpi_3d`, `cpi_4d`, `cpi_5d` (CPI at group/class/subclass) | still deferred — 188 KB / 424 KB / 790 KB |
| `trade_enduse_bec` (retained imports by end-use) | **ingested 2026-08-01** (14,332 rows) |
| SITC 2-digit+ / HS / by partner country | **not in this catalogue at all** — confirmed against all 289 ids; needs a non-DOSM route |
| `gdp_district_real_supply` (GDP by district) | still deferred — 461 KB, and 2015–2020 only |
| `cpi_*_inflation`, `cpi_core*`, `cpi_lowincome`, `cpi_strata` | still deferred — derived/parallel price series |
| `ppi*`, `sppi*` | **headline + 1-digit + SPPI 2d/3d + `ppi_sitc` ingested 2026-08-01**; `ppi_2d`/`ppi_3d` still deferred |
| `lfs_qtr*`, `lfs_year*`, `lfs_district`, `lfs_dun`, `lfs_parlimen`, `employment_sector` | **all ingested 2026-08-01** |
| `gdp_qtr_*`, `gdp_annual_*` (24 further GDP cuts) | **all ingested 2026-08-01** |

No dataset in the fiscal/GFS/state-GDP/CPI/labour/trade scope 404'd or timed out.

---

## The real-economy set (2026-08-01)

The warehouse was ~92% fiscal. This is the economy side: **90 datasets, 143,859 rows**,
ingested by `pipeline/ingest_realeconomy.py` through the same provenance-appending
writer, verified by `pipeline/verify_realeconomy.py`, vintage-tracked in
`data/_vintage.json`, and — new for this layer — accompanied by a **series-break
register**, `data/_series_breaks_dosm.csv`.

Why the register exists: the fiscal sources are audited and reconcilable to the ringgit.
These are survey estimates whose definitions changed *inside* the published series. A
line drawn straight through `hh_poverty.csv` from 1970 to 2024 is not one series.

| block | datasets | rows |
|---|---|---|
| 1. National accounts detail | 26 | 39,167 |
| 2. Household income & expenditure (HIES) | 23 | 34,025 |
| 3. Wages, productivity, labour depth | 21 | 10,746 |
| 4. Industrial production, wholesale & retail, services, producer prices | 16 | 45,206 |
| 5. Trade depth + classification dictionaries | 4 | 14,715 |

### 1. National accounts detail (26 datasets, 39,167 rows)

GDP on all three approaches, annual and quarterly, real and nominal, headline and
subsector/subtype, plus seasonal adjustment and the external balance.

| file | rows | coverage | grain | data_as_of |
|---|---|---|---|---|
| `gdp_gni_annual_real` | 111 | 1970–2025 | series × {gdp, gni, per-capita} | 2025 |
| `gdp_annual_nominal_supply` / `gdp_annual_real_supply` | 147 each | 2015–2025 | sector p0–p6 | 2025 |
| `gdp_annual_nominal_demand` / `gdp_annual_real_demand` | 137 each | 2015–2025 | expenditure e0–e6 | 2025 |
| `gdp_annual_nominal_income` | 156 | 2010–2025 | income i0–i3.2 (incl. **compensation of employees**) | 2024 |
| `gdp_annual_nominal_supply_granular` / `gdp_annual_real_supply_granular` | 2,373 each | 2015–2025 | subsector (p1.1.1 …) | 2023 |
| `gdp_annual_nominal_demand_granular` / `gdp_annual_real_demand_granular` | 893 each | 2015–2025 | expenditure subtype (e1.1.01 …) | 2023 / 2025 |
| `gdp_qtr_nominal` / `gdp_qtr_real` | 130 each | 2015Q1–2026Q1 | headline | 2026-Q1 |
| `gdp_qtr_nominal_supply` / `gdp_qtr_real_supply` | 910 each | 2015Q1–2026Q1 | sector | 2026-Q1 |
| `gdp_qtr_nominal_demand` / `gdp_qtr_real_demand` | 825 each | 2015Q1–2026Q1 | expenditure | 2026-Q1 |
| `gdp_qtr_real_sa` / `_sa_supply` / `_sa_demand` | 45 / 315 / 270 | 2015Q1–2026Q1 | seasonally adjusted | 2026-Q1 |
| `gdp_qtr_nominal_supply_granular` / `gdp_qtr_real_supply_granular` | 10,010 each | 2015Q1–2026Q1 | subsector | 2026-Q1 |
| `gdp_qtr_nominal_demand_granular` / `gdp_qtr_real_demand_granular` | 3,425 each | 2015Q1–2026Q1 | expenditure subtype | 2026-Q1 |
| `gdp_lookup` | 174 | — | code → label (EN/BM) for p*, e*, i* | 2024-Q1 |
| `bop_balance` | 325 | 2010Q1–2026Q1 | current / capital / financial / NEO / reserves | 2026-Q1 |
| `fdi_flows` | 71 | 2008Q1–2025Q3 | inflow / outflow / net | 2025-Q3 |

**Savings/investment balance:** no such dataset is published. `bop_balance`'s current
account (S − I by identity) plus `gdp_annual_*_demand`'s GFCF and inventories are the
closest the catalogue gets; a true savings/investment account is a gap (below).

### 2. Household income & expenditure — HIES (23 datasets, 34,025 rows)

The highest-value gap the brief named, now closed at every published grain.

| file | rows | coverage | grain |
|---|---|---|---|
| `hh_income` | 22 | 1970–2024 | national mean + median monthly gross income |
| `hh_income_state` | 319 | 1970–2024 | × state |
| `hh_income_district` | 480 | 2019–2024 | × administrative district |
| `hh_income_parlimen` / `hh_income_dun` | 666 / 1,800 | 2019–2024 | × federal / state constituency |
| `hh_inequality` | 21 | 1970–2024 | **Gini** |
| `hh_inequality_state` | 289 | 1974–2024 | Gini × state |
| `hh_inequality_district` / `_parlimen` / `_dun` | 480 / 666 / 1,800 | 2019–2024 | Gini × district / parliament / DUN |
| `hh_poverty` | 21 | 1970–2024 | absolute / hardcore / relative headcount |
| `hh_poverty_state` | 310 | 1970–2024 | × state |
| `hh_poverty_district` / `_parlimen` / `_dun` | 480 / 666 / 1,800 | 2019–2024 | × district / parliament / DUN |
| `hies_malaysia_percentile` | 1,200 | 2019–2024 | **100 percentiles** × {mean, median, min, max} |
| `hies_state_percentile` | 19,200 | 2019–2024 | 100 percentiles × state |
| `hies_state` | 32 | 2022–2024 | income + **expenditure** + Gini + poverty, one row per state |
| `hies_district` | 322 | 2022–2024 | same, per district |
| `hh_expenditure_parlimen` / `hh_expenditure_dun` | 666 / 1,800 | 2019–2024 | mean household expenditure × constituency |
| `hh_access_amenities` | 688 | 2016–2024 | piped water / sanitation / electricity × state × district |
| `hh_profile_state` | 297 | 1970–2024 | households + living quarters × state |

Deciles/quintiles (B40/M40/T20) are **not published as such** — they are derived from
`hies_malaysia_percentile` / `hies_state_percentile` by grouping percentiles, which is a
`curated/` task. **Urban/rural strata are not published in the catalogue** at all (see
gaps). Household expenditure exists only at constituency grain plus the
`hies_state`/`hies_district` pair — there is no national or state expenditure-by-category
dataset.

### 3. Wages, productivity, labour depth (21 datasets, 10,746 rows)

| file | rows | coverage | grain |
|---|---|---|---|
| `productivity_annual` | 462 | 2015–2025 | sector × {gdp, hours, employment, output/hour, output/worker} |
| `productivity_annual_priority` | 288 | 2015–2025 | 14 priority subsectors |
| `productivity_qtr` | 1,848 | 2015Q1–2025Q4 | sector, quarterly |
| `productivity_lookup` | 36 | — | sector code → label |
| `lfs_month_sa` | 197 | 2010-01–2026-05 | seasonally adjusted principal statistics |
| `lfs_month_status` | 250 | 2016-01–2026-05 | employer / employee / own-account / unpaid family |
| `lfs_month_duration` | 125 | 2016-01–2026-05 | unemployment by search duration (incl. long-term) |
| `lfs_month_youth` | 125 | 2016-01–2026-05 | youth unemployment 15–24 and 15–30 |
| `lfs_qtr` | 63 | 2010Q1–2025Q3 | national quarterly |
| `lfs_qtr_state` | 560 | 2017Q1–2025Q3 | × state |
| `lfs_qtr_sru_age` / `lfs_qtr_sru_sex` | 350 / 210 | 2017Q1–2025Q3 | **skills-related underemployment** × age / sex |
| `lfs_qtr_tru_age` / `lfs_qtr_tru_sex` | 350 / 210 | 2017Q1–2025Q3 | **time-related underemployment** × age / sex |
| `lfs_year` | 40 | 1982–2023 | national annual (1991, 1994 absent at source) |
| `lfs_year_sex` | 120 | 1982–2023 | × sex |
| `lfs_state_sex` | 1,732 | 1982–2023 | × state × sex |
| `lfs_district` | 1,116 | 2018–2024 | × district |
| `lfs_parlimen` / `lfs_dun` | 666 / 1,800 | 2021–2023 | × constituency |
| `employment_sector` | 198 | 2001–2022 | share of employment by MSIC sector × sex |

**There is no salaries & wages dataset in the catalogue** (as of 2026-08-03; superseded: the catalogue now publishes `wages_*` and `formal_wages_*`, ingested in wave 3, 2026-11-06). DOSM publishes formal-sector
wages as a dashboard only, and the Salaries & Wages Survey has no catalogue entry. The
nearest available wage aggregate is `gdp_annual_nominal_income`'s *compensation of
employees* (component `i1`), which gives the labour share of GDP from 2010. Getting
wages by sector/state/occupation needs a non-DOSM route (see gaps).

### 4. Industrial production, wholesale & retail, services, producer prices (16 datasets, 45,206 rows)

| file | rows | coverage | grain |
|---|---|---|---|
| `ipi` | 398 | 2015-01–2026-05 | Industrial Production Index, raw + seasonally adjusted |
| `ipi_1d` / `ipi_2d` | 1,194 / 10,348 | 2015-01–2026-05 | IPI × MSIC section / division |
| `ipi_domestic` / `ipi_export` | 5,970 / 5,174 | 2015-01–2026-05 | IPI split domestic- vs export-oriented divisions |
| `iowrt` | 290 | 2018-01–2026-05 | wholesale & retail trade: sales value + volume index |
| `iowrt_2d` / `iowrt_3d` | 870 / 5,800 | 2018-01–2026-05 | × division / group |
| `sppi` / `sppi_1d` / `sppi_2d` / `sppi_3d` | 130 / 1,040 / 1,790 / 3,062 | 2015Q1–2026Q1 | Services Producer Price Index, headline → 3-digit |
| `ppi` / `ppi_1d` | 581 / 2,905 | 2010-01–2026-06 | Producer Price Index, headline + section |
| `ppi_sitc` | 5,229 | 2010-01–2026-06 | PPI on the **same SITC sections as `trade_sitc_1d`** — terms-of-trade pairing without a mapping table |
| `economic_indicators` | 425 | 1991-01–2026-05 | leading / coincident / lagging composite + diffusion indices |

**There is no manufacturing sales-value dataset and no index of services production.**
The Monthly Manufacturing Survey feeds `ipi` but its sales/employment tables are not
published as a catalogue dataset; `iowrt` (wholesale & retail) and `sppi` (services
prices) are the only services-side series available.

### 5. Trade depth + dictionaries (4 datasets, 14,715 rows)

| file | rows | coverage | grain |
|---|---|---|---|
| `trade_enduse_bec` | 14,332 | 2010-01–2026-06 | retained imports × end use × BEC (capital / intermediate / consumer) |
| `sitc` | 9 | — | SITC section dictionary |
| `bec` | 31 | — | BEC dictionary (UN BEC rev. 4) |
| `mcoicop` | 343 | — | MCOICOP dictionary (joins CPI) |

**Trade below SITC 1-digit does not exist in this catalogue** — checked against all 289
data.gov.my ids and all 182 OpenDOSM ids. There is no SITC 2-digit+, no HS chapter, and
**no trade by partner country**. Deeper trade is METS/StatsBDA territory and needs a
separate acquisition.

### What the real-economy pass deferred

All reachable, none failed; sizes as measured 2026-08-01.

| dataset(s) | size | why deferred |
|---|---|---|
| `ipi_3d` (group), `ipi_5d` (item) | 831 KB / 1,672 KB | `ipi_2d` division grain already resolves every published sector; item-level output is below any agenda-outcome question |
| `ppi_2d`, `ppi_3d` | 315 KB / 1,072 KB | headline + section + SITC cuts ingested; deeper producer-price tiers are a pricing study, not an outcome measure |
| `cpi_3d`, `cpi_4d`, `cpi_5d` | 188 / 424 / 790 KB | carried over from the 2026-07-31 decision — division level covers the deflator use case |
| `gdp_district_real_supply` | 461 KB | district GDP stops at 2020; `gdp_state_real_supply` is the live regional series |
| `msic` | 576 KB | full MSIC classification tree; `employment_sector` and the IPI files carry their own labels |
| `cpi_*_inflation`, `cpi_core*`, `cpi_lowincome`, `cpi_strata` | small | derived transforms of series already held |
| `hies_state_percentile` at DUN grain, `lfs_qtr_sru/tru` cross-tabs | n/a | not published |

### What the catalogue does NOT publish (needs a non-DOSM route)

Checked exhaustively against **all 289 data.gov.my ids and all 182 OpenDOSM ids**
(scraped 2026-08-01 from the two catalogue pages; the GitHub API for
`data-gov-my/datagovmy-meta` is not reachable from this environment, but every metadata
file is readable individually via `raw.githubusercontent.com`). These are absences, not
deferrals — nothing to ingest later from this source:

| what an agenda analysis needs | status in the catalogue | where it has to come from |
|---|---|---|
| **Salaries & wages** by sector / state / occupation | **absent.** No SWS dataset; DOSM publishes formal-sector wages as a dashboard only | DOSM dashboard scrape or the SWS publication; EPF/SOCSO administrative data |
| **Urban/rural strata** for income, Gini, poverty | **absent.** HIES is published by state, district, parliament, DUN — never by strata | HIES report PDFs |
| **B40/M40/T20 as published groups** | absent as such | derivable in `curated/` from `hies_*_percentile` |
| **Household expenditure by category** (national or state) | **absent.** Only `hies_state`/`hies_district` mean expenditure and the DUN/parliament files | HES report |
| **Manufacturing sales value / employment** | **absent.** The Monthly Manufacturing Survey feeds `ipi` but its own tables are not a dataset | DOSM monthly manufacturing release |
| **Index of services production** | **absent.** `iowrt` (wholesale & retail) and `sppi` (services prices) are the only services series | DOSM services statistics release |
| **Trade below SITC 1-digit; trade by partner country** | **absent** at every grain | METS / StatsBDA portal |
| **Nominal state GDP** | absent — state GDP is real (2015 prices) only | — |
| **Savings / investment account** | absent — `bop_balance` current account and GFCF are the proxies | DOSM national accounts publication |
| **Approved investments (MIDA)** | absent — `fdi_flows` is realised, BOP-basis FDI, not approvals | MIDA (the approved-vs-realised gap pairing in docs/SOURCES.md) |
| **Foreign-worker share of employment** | **absent.** `employment_sector` is by MSIC sector and sex only, and stops at 2022 | Immigration / MOHR administrative data |
| **Business demography** (registrations, closures, SME census) | absent | SSM, SME Corp |

The first two rows are the load-bearing ones: without wages and without urban/rural
strata, two of the questions an economic agenda is normally judged on cannot be answered
from this source at all.

### Series breaks — `data/_series_breaks_dosm.csv`

**18 registered discontinuities**, built by `pipeline/series_breaks.py`, each with the
source's own caveat text quoted (10 `source_caveat`, 7 `observed` by this pipeline, 1
combining both). The ones that change conclusions:

| series | break | what changed |
|---|---|---|
| poverty | **2019** | **PLI redefined.** Absolute poverty steps 0.4% (2016) → 5.6% (2019); hardcore 0.0% → 0.4% — while median household income *rose* 12.3% over the same interval. Pre-2019 and post-2019 poverty are not one series. |
| HIES income/Gini/poverty | 1976 | 1970 and 1974 are Peninsular Malaysia only; Sabah and Sarawak enter in 1976 |
| HIES | 1989 | published statistics cover Malaysian citizens only from 1989 |
| HIES state panel | 1976 / 2004 / 2007 | KL from 1976, Putrajaya from 2007, Labuan from **2004 per the poverty file but 2007 per the income file** — the source's two caveats disagree; both recorded, neither corrected |
| HIES sub-state | 2019 | district / parliament / DUN grain begins in 2019; nothing earlier exists to compare to |
| LFS | **2025** | population benchmark moves from the 2010 Census to the 2020 Census; the source states a trend break follows |
| LFS annual | 1991, 1994 | years absent entirely from the source |
| national accounts | 2015 | constant-price base year 2015 = 100 |
| HIES income | all | **nominal, never deflated** — comparing 1970 to 2024 without `cpi_headline` measures inflation, not welfare |
| seasonally adjusted series | all | components are adjusted independently and do **not** add to totals (median gap in `lfs_month_sa`: 4.5k) |
| GDP / productivity / IPI / BOP / trade | rolling | open revision windows: GDP 2024–2025, SA 2022–2024, productivity 3 years, IPI 1 year, BOP & FDI 8 quarters, trade 2 months |
| `hh_access_amenities` | 2024 | the 2024 wave was published **mid-ingest** and revised 2022 as well; anyone holding an earlier copy has different 2022 numbers |
| `ep_ratio` across LFS files | all | `lfs_year` reproduces employed/(lf+outside); `lfs_year_sex` and `lfs_state_sex` publish a *different* ep_ratio for identical levels |
| small-area LFS | 2020–2023 | district/parliament/DUN rows where lf ≠ employed + unemployed by far more than rounding — do not aggregate them |
| `hies_malaysia_percentile` | 2022 | the 2022 percentile distribution averages to RM 8,359.7 against a published mean of RM 8,479 (−1.4%); 2019 and 2024 reconcile to 0.03% |

## Validation — real-economy set (2026-08-01 ingest)

`data/_validation_realeconomy.csv` (as of the 2026-11-04 refresh: **429 checks, 399 PASS, 28 INFO,
2 SOURCE_ANOMALY, 0 FAIL**; the figures below describe the first ingest): **411 checks, 384 PASS, 27 INFO, 0 FAIL**, plus
`data/_identity_breaches_realeconomy.csv` listing all **1,860 individual breaching rows**.
Run `python3 sources/dosm/pipeline/verify_realeconomy.py`.

**Two independent doors, with an explicit arbiter.** Every dataset is compared against
(a) its **parquet mirror** on storage.dosm.gov.my — the same vintage of the same
publication in a different serialisation, and (b) the **static API** where it is served
(80 of 90; the rest carry `exclude_openapi: true`). A value disagreement is a FAIL only
if the *parquet arbiter* disagrees with the canonical CSV; an API-only disagreement is
INFO, because it means the API mirror is the one out of step. Three such divergences
exist in this vintage, all kept as published:

- **`lfs_district.ep_ratio`** — the API's column runs ~19pp below the CSV's for every
  row. The CSV and the parquet arbiter both reproduce `100*lf_employed/(lf+lf_outside)`
  exactly; the API does not. The canonical file is the internally consistent one.
- **`gdp_annual_*_granular`** — the API mirror is a stale *vintage*, not merely short:
  it ends 2023 and its 2023 values are pre-revision.
- **`ipi`, `ipi_1d`** — the API lags the storage file by one month.

**Internal identities** (the accounting the source implies about itself). Tolerances are
the half-unit rounding bound computed *per period* at the precision that period is
actually printed to — DOSM mixes 0, 1 and 3 decimal places inside single files — floored
at one full unit so "agrees to the last printed digit" counts as agreement.

| identity | result |
|---|---|
| GDP expenditure `e0 = e1+e2+e3+e4+e5−e6` (9 files, annual/quarterly/SA/granular) | PASS |
| GDP production `p0 = p1+…+p6` (9 files) | PASS |
| GDP income `i0 = i1+i2+i3`, `i3 = i3.1−i3.2` | PASS |
| production = expenditure = income, same year (SNA 2008) | PASS — agree to RM 0.001 mil for all 16 years |
| labour force `lf = employed + unemployed` (9 LFS grains) | PASS at national/state/quarterly; **INFO at district (16 rows), parliament (6), DUN (78)** |
| `u_rate`, `p_rate`, `ep_ratio` from their own levels | PASS except the small-area and `*_sex` cases below |
| productivity `output/worker = gdp/employment`, `output/hour = gdp/hours` | PASS (3 files) |
| 100 percentile means average to the published mean | PASS for 2019 & 2024 and 47/48 state-years; **INFO: 2022 national −1.4%** |
| hardcore ≤ absolute poverty (5 files) | PASS |
| `hies_state` vs `hh_income_state` / `hh_inequality_state` / `hh_poverty_state` | PASS — 32 state-years × 4 indicators agree exactly |
| `employment_sector` shares sum to 100 | PASS |
| BOP `ca+ka+neo−fa` | reported as a diagnostic only — the financial-account sign convention is not published with the dataset (median residual RM 18,440 mil) |

The INFO rows are source-side, not pipeline-side: every value was verified verbatim
against the parquet arbiter first, so an identity that fails is a property of the
publication. All of them are recorded row-by-row and none is corrected.

## Wave 3 (2026-11-06)

`pipeline/ingest_wave3.py` pulls 55 datasets that the catalogue added or that earlier passes deferred, with the
same writer (values verbatim plus `retrieved_from`/`retrieved_date`), `_vintage.json` and `_vintage_log.csv`
entries. `refresh.py` watches them. `pipeline/verify_wave3.py` compares every file with the parquet mirror of the
same publication, cell by cell (`data/_validation_wave3.csv`: 165 checks, all PASS).

| block | datasets |
|---|---|
| wages and productivity | `wages_state`, `wages_strata`, `wages_sector`, `wages_industry`, `wages_education`, `wages_age`, `wages_ethnicity`, `wages_occupation`, `wages_skill`, `wages_certificate`, `wages_noncitizen`, `wages_noncitizen_education`, `wages_real_state`, `wages_real_state_citizen`, `formal_wages`, `formal_wages_state`, `formal_wages_msic`, `formal_wages_band`, `formal_wages_percentile`, `formal_wages_msic_age`, `productivity_state` |
| prices, output, people, services | `cpi_core`, `cpi_core_inflation`, `cpi_lowincome`, `cpi_strata`, `cpi_state_inflation`, `cpi_headline_inflation`, `cpi_annual`, `cpi_annual_inflation`, `gdp_district_real_supply`, `life_expectancy`, `life_expectancy_state_ethnic`, `life_expectancy_district`, `births_annual_state`, `fertility_state`, `deaths_maternal_state`, `deaths_early_childhood_state`, `completion_school_state`, `completion_school_district`, `hh_access_internet` |
| environment, energy, water, agriculture | `air_pollution`, `ghg_emissions`, `water_pollution_basin`, `forest_reserve`, `forest_reserve_state`, `electricity_consumption`, `electricity_supply`, `energy_consumption_sector`, `energy_supply_commodity`, `water_consumption`, `water_production`, `mineral_extraction`, `timber_production`, `crops_state`, `fish_landings` |

Left out on purpose: `cpi_3d`/`4d`/`5d`, and `population_dun`/`parlimen` (age × ethnicity grain).

**The Salaries & Wages Survey tables cover citizens only, except `wages_ethnicity` and `wages_real_state`,
which cover all employees.** The other tables' 'overall' row equals `wages_ethnicity`'s 'citizen' row in all 48
year × sex cells. In core, the citizens-only rows carry `citizenship=citizen`, and `_total` is all employees.

The files' own identities are checked offline by `pipeline/verify_wave3_identities.py`. Breaches beyond the
printed rounding are registered in `data/_identity_breaches_wave3.csv` and kept as published. There are 16:
* timber national totals that are not the sum of the states (e.g. 2001 plywood: 4,317,193 printed against
  4,217,193 summed);
* water production in 2010;
* fish landings in two months;
* one wage-recipients year.

Other notes:
* District GDP: in Sabah and Sarawak the state's own Supra is not a district, so their districts do not add up to
  the state.
* Kuala Lumpur's district row includes Putrajaya (flagged).
* 6 districts of the 2020 set print no GDP (the file likely uses earlier boundaries).
* Selangor's water figures likely include KL and Putrajaya.
* Fish landings are printed for each state only by coast.

Held at L1 only:
* `completion_school_district`: MOE's education districts, not DOSM's administrative districts;
* the `growth_yoy` series of `productivity_state` and `gdp_district_real_supply` (derivable from the levels);
* the national 'overall' rows of the citizens-only wage tables, and the national totals of `formal_wages_state`
  and `formal_wages_msic`: each repeats a total loaded once from another file;
* the states' CPI inflation and every month-on-month rate: derivable from the indexes core holds;
* the 'Supra' rows of district GDP;
* the 'Semenanjung Malaysia' forest subtotal.

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
- Real-economy datasets: retrieved **2026-08-01** from storage.dosm.gov.my
  (`/gdp/`, `/bop/`, `/hies/`, `/demography/`, `/labour/`, `/ipi/`, `/iowrt/`, `/ppi/`,
  `/mei/`, `/trade/`, `/dictionaries/`); same per-row `retrieved_from` +
  `retrieved_date`. Note that the file name on storage is not always the catalogue id
  (`gdp_annual_nominal_supply_granular` -> `gdp_annual_nominal_supply_sub.csv`,
  `hh_profile_state` -> `hh_lq_state.csv`, `economic_indicators` -> `mei/mei.csv`,
  `productivity_annual_priority` -> `productivity_annual_p14.csv`); the mapping lives
  in `pipeline/ingest_realeconomy.py` and the resolved URL is on every row.
- Catalogue pages: https://open.dosm.gov.my/data-catalogue/<id> (OpenDOSM datasets) and
  https://data.gov.my/data-catalogue/<id> (federal/state finance).
- License: Creative Commons Attribution 4.0 (per catalogue pages).
- The original three CSVs are byte-for-byte as downloaded; the expansion CSVs are the
  downloaded files with **only** the two provenance columns appended (source values
  verbatim). **Never edit any of them**; re-download to refresh (that is a new vintage:
  update this README's retrieval date and vintages).

## Vintage refresh 2026-11-04

`refresh.py --apply` pulled **63 datasets** with a new DOSM release (47 were already current).
Row counts and coverage in the tables above are as of each dataset's first ingest; this table
is the change, and `data/_vintage.json` holds the current `data_as_of` for every dataset.
"Revised" counts rows that existed before and whose published values changed (compared as
numbers, so a `25431356829.0` → `25431356829` reformat is not a revision). The replaced
vintages are logged in `data/_vintage_log.csv` and recoverable with `pipeline/vintage_get.py`.

| dataset | rows | latest period | new rows | revised rows (years) |
|---|---|---|---|---|
| `bop_balance` | 325 → 330 | 2026-01 → 2026-04 | 5 | 8 (2024–2026) |
| `cpi_headline` | 7,812 → 7,854 | 2026-06 → 2026-09 | 42 | 0 |
| `cpi_state` | 44,352 → 45,024 | 2026-06 → 2026-09 | 672 | 0 |
| `economic_indicators` | 425 → 428 | 2026-05 → 2026-08 | 3 | 5 (2026) |
| `employment_sector` | 198 → 225 | 2022-01 → 2025-01 | 27 | 64 (2010–2022) |
| `federal_finance_qtr` | 1,243 → 1,342 | 2024-01 → 2026-04 | 99 | 8 (2021–2024) |
| `federal_finance_qtr_de` | 1,582 → 1,708 | 2024-01 → 2026-04 | 126 | 1 (2023) |
| `federal_finance_qtr_oe` | 1,111 → 1,210 | 2024-01 → 2026-04 | 99 | 4 (2023–2024) |
| `federal_finance_qtr_revenue` | 2,373 → 2,562 | 2024-01 → 2026-04 | 189 | 24 (1999–2023) |
| `federal_finance_year` | 594 → 616 | 2023-01 → 2025-01 | 22 | 5 (2021–2023) |
| `federal_finance_year_de` | 756 → 784 | 2023-01 → 2025-01 | 28 | 8 (2018–2023) |
| `federal_finance_year_oe` | 495 → 517 | 2023-01 → 2025-01 | 22 | 5 (2022–2023) |
| `federal_finance_year_revenue` | 1,134 → 1,176 | 2023-01 → 2025-01 | 42 | 8 (2000–2023) |
| `gdp_annual_nominal_income` | 156 → 156 | 2025-01 → 2025-01 | 0 | 0 |
| `gdp_qtr_nominal` | 130 → 133 | 2026-01 → 2026-04 | 3 | 1 (2026) |
| `gdp_qtr_nominal_demand` | 825 → 844 | 2026-01 → 2026-04 | 19 | 2 (2026) |
| `gdp_qtr_nominal_demand_granular` | 3,425 → 3,504 | 2026-01 → 2026-04 | 79 | 2 (2026) |
| `gdp_qtr_nominal_supply` | 910 → 931 | 2026-01 → 2026-04 | 21 | 7 (2026) |
| `gdp_qtr_nominal_supply_granular` | 10,010 → 10,241 | 2026-01 → 2026-04 | 231 | 28 (2026) |
| `gdp_qtr_real` | 130 → 133 | 2026-01 → 2026-04 | 3 | 1 (2026) |
| `gdp_qtr_real_demand` | 825 → 844 | 2026-01 → 2026-04 | 19 | 2 (2026) |
| `gdp_qtr_real_demand_granular` | 3,425 → 3,504 | 2026-01 → 2026-04 | 79 | 2 (2026) |
| `gdp_qtr_real_sa` | 45 → 46 | 2026-01 → 2026-04 | 1 | 5 (2025–2026) |
| `gdp_qtr_real_sa_demand` | 270 → 276 | 2026-01 → 2026-04 | 6 | 16 (2025–2026) |
| `gdp_qtr_real_sa_supply` | 315 → 322 | 2026-01 → 2026-04 | 7 | 34 (2025–2026) |
| `gdp_qtr_real_supply` | 910 → 931 | 2026-01 → 2026-04 | 21 | 3 (2026) |
| `gdp_qtr_real_supply_granular` | 10,010 → 10,241 | 2026-01 → 2026-04 | 231 | 24 (2026) |
| `hh_access_amenities` | 688 → 694 | 2024-01 → 2024-01 | 6 | 27 (2024) |
| `iowrt` | 290 → 299 | 2026-05 → 2026-08 | 9 | 53 (2022–2024) |
| `iowrt_2d` | 870 → 897 | 2026-05 → 2026-08 | 9 | 29 (2022–2024) |
| `iowrt_3d` | 5,800 → 5,980 | 2026-05 → 2026-08 | 9 | 0 |
| `ipi` | 398 → 407 | 2026-05 → 2026-08 | 9 | 129 (2020–2026) |
| `ipi_1d` | 1,194 → 1,221 | 2026-05 → 2026-08 | 27 | 194 (2020–2026) |
| `ipi_2d` | 10,348 → 10,582 | 2026-05 → 2026-08 | 9 | 103 (2022–2026) |
| `ipi_domestic` | 5,970 → 6,105 | 2026-05 → 2026-08 | 135 | 0 |
| `ipi_export` | 5,174 → 5,291 | 2026-05 → 2026-08 | 117 | 19 (2020–2026) |
| `lfs_month` | 197 → 200 | 2026-05 → 2026-08 | 3 | 4 (2025) |
| `lfs_month_duration` | 125 → 126 | 2026-05 → 2026-06 | 1 | 1 (2025) |
| `lfs_month_sa` | 197 → 200 | 2026-05 → 2026-08 | 3 | 4 (2025) |
| `lfs_month_status` | 250 → 256 | 2026-05 → 2026-08 | 6 | 246 (2016–2026) |
| `lfs_month_youth` | 125 → 126 | 2026-05 → 2026-06 | 1 | 125 (2016–2026) |
| `lfs_qtr` | 63 → 66 | 2025-07 → 2026-04 | 3 | 7 (2024–2025) |
| `lfs_qtr_sru_age` | 350 → 380 | 2025-07 → 2026-04 | 30 | 59 (2024–2025) |
| `lfs_qtr_sru_sex` | 210 → 228 | 2025-07 → 2026-04 | 18 | 31 (2024–2025) |
| `lfs_qtr_state` | 560 → 608 | 2025-07 → 2026-04 | 48 | 112 (2024–2025) |
| `lfs_qtr_tru_age` | 350 → 380 | 2025-07 → 2026-04 | 30 | 31 (2024–2025) |
| `lfs_qtr_tru_sex` | 210 → 228 | 2025-07 → 2026-04 | 18 | 22 (2024–2025) |
| `lfs_state_sex` | 1,732 → 1,908 | 2023-01 → 2025-01 | 176 | 1,567 (1982–2023) |
| `lfs_year` | 40 → 42 | 2023-01 → 2025-01 | 2 | 0 |
| `lfs_year_sex` | 120 → 126 | 2023-01 → 2025-01 | 6 | 109 (1982–2023) |
| `ppi` | 581 → 590 | 2026-06 → 2026-09 | 9 | 0 |
| `ppi_1d` | 2,905 → 2,950 | 2026-06 → 2026-09 | 45 | 0 |
| `ppi_sitc` | 5,229 → 5,310 | 2026-06 → 2026-09 | 9 | 0 |
| `productivity_annual` | 462 → 462 | 2025-01 → 2025-01 | 0 | 419 (2015–2025) |
| `productivity_annual_priority` | 288 → 291 | 2025-01 → 2025-01 | 3 | 119 (2017–2025) |
| `productivity_qtr` | 1,848 → 1,936 | 2025-10 → 2026-04 | 88 | 1,720 (2015–2025) |
| `sppi` | 130 → 133 | 2026-01 → 2026-04 | 3 | 0 |
| `sppi_1d` | 1,040 → 1,064 | 2026-01 → 2026-04 | 24 | 5 (2020–2021) |
| `sppi_2d` | 1,790 → 1,841 | 2026-01 → 2026-04 | 3 | 0 |
| `sppi_3d` | 3,062 → 3,149 | 2026-01 → 2026-04 | 3 | 0 |
| `trade_enduse_bec` | 14,332 → 14,697 | 2026-04 → 2026-09 | 95 | 651 (2010–2026) |
| `trade_headline` | 743 → 1,310 | 2026-04 → 2026-09 | 567 | 175 (2000–2026) |
| `trade_sitc_1d` | 3,487 → 4,851 | 2026-05 → 2026-09 | 1,364 | 247 (2024–2026) |

What moved, in short:

- **New periods everywhere**: CPI to 2026-09, LFS monthly to 2026-08 and quarterly to 2026-Q2,
  GDP to 2026-Q2, IPI/IOWRT to 2026-08, PPI and trade to 2026-09, annual LFS and
  `employment_sector` to 2025, and DOSM's federal finance files (JANM) to **FY2025 annual and
  2026-Q2 quarterly**, after two years without an update.
- **History extended**: `trade_headline` and `trade_sitc_1d` now start in **1990** (were 2000);
  `trade_headline` also gains domestic exports and re-exports.
- **Real revisions to history**, not only the newest period: `lfs_state_sex` (1,567 rows back to
  1982; levels move ≤0.4%, rates up to 9.5% relative, e.g. Selangor 1990), `lfs_year_sex`,
  `productivity_*` (most of 2015–2025, the open three-year revision window plus level changes),
  `lfs_month_status`, IPI 2020–2026 and trade 2024–2026. Anything computed from these before
  2026-11-04 should be recomputed, not assumed unchanged.
- `curated/fact_labour_indicators.csv` was rebuilt: 2024–2025 added, no historical value changed.

### Source anomalies found during this refresh (kept as printed, golden rule 2)

| dataset | vintage | what | evidence |
|---|---|---|---|
| `lfs_month_youth` | 2026-08-03 (previous) | **headers out of order**: the file was labelled `unemployed_15_24, u_rate_15_24, unemployed_15_30, u_rate_15_30` but its values were in the order unemployed 15–24, unemployed 15–30, rate 15–24, rate 15–30. Read by name, the youth unemployment rate was **402.8%** (2016-01). | DOSM's 2026-11-04 file carries the same numbers under corrected headers (`…,unemployed_15_30,u_rate_15_24,…`). Nothing in `curated/` or `site/` read the column. Anyone who used the August file by column name has wrong youth rates. |
| `lfs_district` | held since 2026-08 | Telang Usan (Sarawak), 2018: `u_rate` = 293.0 with every other field blank | a rate cannot exceed 100; `_identity_breaches_realeconomy.csv` |
| `lfs_dun` | held since 2026-08 | Kedah N.08 Pedu and N.09 Bukit Lada, 2021: `lf_employed` 24.3 > `lf` 13.0 / 12.4; `ep_ratio` 106.1 / 109.0. Both rows print identical employed / unemployed / outside figures, which suggests a copied row. | same |

**New check** (`verify_realeconomy.py`): every rate, ratio, proportion and poverty column must lie
in [0, 100]. A few cells out of range are recorded as `SOURCE_ANOMALY` (the publisher's
misprint); more than 1% of a file's rows out of range is a `FAIL` that blocks the refresh. The
youth file above would have failed (125 of 125 rows).

The refresh also needs `pyarrow` (the parquet arbiter in `verify_realeconomy.py`); without it every
GDP/BOP/FDI arbiter check FAILs with "No module named 'pyarrow'". It is now in `requirements.txt`.

## Keeping it fresh (updates are pulled, never silent)

The warehouse pins a retrieval vintage on purpose — an upstream revision changing every
%GDP ratio silently would break provenance. To detect and apply DOSM updates:

- `python3 sources/dosm/pipeline/refresh.py` — **check** (safe): compares the OpenDOSM
  static API metadata (`data_as_of`, `last_updated` via
  `api.data.gov.my/opendosm?id=…&meta=true`) and the storage ETag against the recorded
  baseline in `data/_vintage.json`; exits non-zero if a new vintage exists.
- `python3 sources/dosm/pipeline/refresh.py --apply` — pulls the new vintage with a
  row-level diff report, updates `_vintage.json` and re-runs the API cross-check. Then
  update the vintage table above and commit the refresh as its own change.
- **Every vintage is kept** (docs/DATA_MODEL.md §6, D3). `refresh.py --apply` appends to
  `data/_vintage_log.csv` (dataset, data_as_of, retrieved_date, rows, sha256): one `superseded`
  row for the file it replaces and one `current` row for the new file. Rows are never edited.
  The log was seeded on 2026-11-04 with all 110 current files and the 63 vintages replaced that
  day. `python3 sources/dosm/pipeline/vintage_get.py <dataset>` lists a dataset's vintages, and
  `vintage_get.py <dataset> <data_as_of> <out.csv>` writes any of them back out from git history,
  verified against the logged sha256.
- **Automatic daily refresh:** `.github/workflows/dosm-refresh.yml` runs at 14:17 Malaysia time
  (and on demand). On a new release it runs `refresh.py --apply`, rebuilds the labour table, and
  measures the change with `pipeline/refresh_report.py`, which writes the per-dataset table into the
  PR. The PR merges itself only when every verifier exited 0 and the gate passes: no FAIL, no new
  SOURCE_ANOMALY, no header change, no withdrawn rows. Anything else waits for a person. Replayed
  on the 2026-11-04 refresh, the gate correctly held it for review (the `lfs_month_youth` header
  change and two new anomalies).
- `python3 sources/dosm/pipeline/verify_against_api.py` — independent value-level
  cross-check of the original three CSVs against the API (same publication, second door).
- `python3 sources/dosm/pipeline/verify_expansion.py` — same second-door discipline for
  the expansion datasets: per dataset, row count vs the API total plus a field-by-field
  comparison of every row in the latest period → `data/_validation_expansion.csv`.
- `python3 sources/dosm/pipeline/verify_realeconomy.py` — the two-door + internal-identity
  pass for the real-economy set → `data/_validation_realeconomy.csv` and
  `data/_identity_breaches_realeconomy.csv`.
- `python3 sources/dosm/pipeline/series_breaks.py` — rebuilds `data/_series_breaks_dosm.csv`
  from the catalogue's own caveat text plus the discontinuities the verifier observed.
  **Re-run it after any real-economy refresh** — a survey revision can add or move a break.
- `python3 sources/dosm/pipeline/crosscheck_state_finance.py` — reported vs audited
  state finances → `data/_crosscheck_state_finance_vs_audited.csv` (see the gap
  finding below).

API endpoints used: `https://api.data.gov.my/opendosm?id=<id>` for OpenDOSM datasets
and `https://api.data.gov.my/data-catalogue?id=<id>` for the federal/state finance
datasets (both accept `&meta=true` for vintage metadata and `&limit=` for bulk reads);
canonical files come from `https://storage.dosm.gov.my/<domain>/<file>.csv` and
`https://storage.data.gov.my/publicadmin/<file>.csv`. Catalogue enumeration:
`github.com/data-gov-my/datagovmy-meta` (`data-catalogue/*.json`, 291 datasets).

`refresh.py` watches **all 110 datasets** — the three originals byte-for-byte, the 17
expansion datasets and the 90 real-economy datasets through the provenance-appending
writer. The weekly Routine therefore covers the whole namespace. Ten of the 110 carry
`exclude_openapi: true` in the catalogue and are not served by the static API
(`gdp_annual_real_demand_granular`, the four `gdp_qtr_*_granular`, `ipi_2d`,
`ipi_domestic`, `ipi_export`, `iowrt_3d`, `sppi_3d`); for those, `refresh.py` reads the
vintage fields from the catalogue repo instead and `verify_realeconomy.py` verifies the
values against the parquet mirror. Nothing in the namespace is unwatched or unverified.

**Vintage tracking is mandatory for the real-economy layer, not optional.** Survey data
is revised: `hh_access_amenities` moved from the 2022 wave to the 2024 wave *during*
this ingest and revised its 2022 values in the process, and `trade_headline` /
`trade_sitc_1d` (from the 2026-07-31 pass) are already flagged stale by `refresh.py`
at the time of writing — left for an explicit `--apply` decision rather than folded in
silently.

Per the API, the next scheduled DOSM releases are recorded in `data/_vintage.json`
(`next_update` per dataset).

## Derived output

None. `pipeline/build_denominators.py` and the `curated/dashboard/external_denominators.csv`
it wrote were retired on 2026-11-04 with the old dashboard (docs/DATA_MODEL.md §13.2). GDP
and population reach every consumer from these source CSVs directly.

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

## The wages gap — what fills it meanwhile

No salaries-and-wages dataset exists in this catalogue (see the absence list
above). `curated/fact_labour_indicators.csv` derives an implied average wage and
labour share from `gdp_annual_nominal_income.csv` (component i1/i0) and
`lfs_year.csv` (lf_employed), marked `basis='derived'` with its limits documented.
It is a stopgap, not a substitute for the Salaries & Wages Survey.
