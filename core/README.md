# core/: the conformed layer (L2) and the first gap view

Phase 1 of `docs/DATA_MODEL.md` §15 (**state level, end to end**), and Phase 2 so far: health,
education and services, the **small areas** (districts, parliamentary and state seats), national accounts,
federal totals by publisher and the **national monthly series** (CPI, trade, money and credit). Everything here is derived
from `sources/` (L1) and rebuilt by the scripts in `core/pipeline/`; never edit these CSVs by
hand (golden rule 1). CI rebuilds them on every PR and fails if the committed files differ.

```
python3 core/pipeline/build_entities.py           # dim_entity + bridge_entity_code + entity_name (Phase 3)
python3 core/pipeline/build_core.py               # dims + fact_observation + _validation_core.csv
python3 core/pipeline/build_gap_need_vs_money.py  # gap_need_vs_money.csv + _validation_gap_need.csv
python3 qa/run_eval.py                            # 159 questions against the agent tools
python3 qa/reproduce_curated.py                   # curated tables rebuilt from core, digit for digit
```

## What is in it

| File | Rows | Grain |
|---|---|---|
| `dim_geo.csv` | 1,006 | Malaysia, `_unallocated`, 16 states and FTs (ISO 3166-2:MY), 166 districts (boundary set `dosm_2020`), 222 parliamentary seats and 600 state seats (boundary set `ge15`) |
| `geo_hierarchy.csv` | 1,020 | child → parent, one row per hierarchy (`administrative`: district → state; `electoral`: DUN → parlimen → state) |
| `dim_period.csv` | 618 | years, months (monthly from 1980-01 for national CPI) |
| `dim_indicator.csv` | 63 | definitions from `meta/indicator.csv` (unit, statistic, universe, price basis, additivity, expected coverage) |
| `dim_breakdown.csv` | 181 | `_total`, `sex=…`, `coicop=…`, `bank_type=…`, `staff_type=…`, `stage=…`, `crime_category=…`, `percentile=001…100` |
| `fact_observation.csv` | 134,612 | indicator × geo × period × breakdown × entity × basis × edition × vintage (state 87,985; DUN 18,000; district 11,013; national 10,943; parlimen 6,660; unallocated 11) |
| `dim_entity.csv` | 59 | who: the federal government, 13 state governments, 45 federal votes (Phase 3) |
| `bridge_entity_code.csv` | 99 | readable code → entity, with validity years and proof |
| `entity_name.csv` | 240 | every name an entity was printed under, by code and years |
| `gap_need_vs_money.csv` | 80 | 16 states and FTs × 5 HIES years (2014, 2016, 2019, 2022, 2024) |

Indicators: population (state 1970–2026, district 2020–2026), households; median and mean household
income, Gini, household spending, absolute, hardcore and relative poverty (HIES); labour force,
employed, unemployed, participation and unemployment rates (LFS); CPI for Malaysia and by state, by COICOP
division; real GDP by state; the 13 states' audited revenue, receipts, operating and
development spending, total spending, surplus and debt; and, for Malaysia only, monthly exports,
imports and the trade balance, M1, M2, M3 and banking-system loans.

Every observation carries its value in the base unit (persons, RM) as an exact decimal, the value
and unit **as printed**, its edition and vintage, the sha256 of the file it came from, the L1 row,
and (for state accounts) the PDF page and jadual. DOSM publishes no sampling error for these state
figures, so `reliability = unknown` and answers carry caveat CV1. Nothing is invented.

## Small areas (Phase 2)

DOSM's HIES and LFS small-area files, as published:

| | districts | parliamentary and state seats |
|---|---|---|
| median and mean household income, Gini, absolute poverty | 2019, 2022, 2024 | 2019, 2022, 2024 |
| relative poverty | 2019, 2022, 2024 | not published |
| household spending | 2022, 2024 | 2019, 2022, 2024 |
| LFS labour force, employment, unemployment, rates | 2018–2024 | 2021–2023 |
| piped water, sanitation, electricity | 2016, 2019, 2022, 2024 | not published |

DOSM does not publish every district every year (2016: 148; 2018: 141; 2019–2023: 160; 2024: 166).

* **Codes, not names.** Seats are `MY-09/par:P.001@ge15` and `MY-09/dun:N.01@ge15`: the published
  seat code within its state, on the GE15 boundaries (a redelineation is a new boundary set, never
  a silent re-map, decision D7). Districts join DOSM's 166 districts; the 10 spellings that change
  between years are mapped in `meta/geo_alias.csv`, each with its proof (the two spellings never
  appear in the same year).
* **Uncertainty.** None of these files publishes a sampling error, so every row has
  `reliability = unknown` (caveat CV1). LFS seat figures are the survey's records added up below
  the domain it was designed for (the district), so they are `reliability = low` (caveat CV12).
  **`compare_geos` never bands or ranks any place below state level** (district, parlimen or DUN, whatever the
  indicator; golden rule 9); `get_series`
  answers for one place at a time.
* **Single-district places.** Perlis, Kuala Lumpur, Labuan and Putrajaya are each one district. Where
  DOSM prints no "All Districts" row for them (amenities), their figure is held under the district
  code, and the state row is declared missing in `meta/indicator.csv`, not filled.
* Ministries' own districts (education PPD, health, police) are separate boundary sets: their
  district rows are not mapped to DOSM's districts yet. Only state and national rows are loaded.

**Flags from source (2026-11-04).** Figures DOSM published in rows that fail their own arithmetic
(`sources/dosm/data/_identity_breaches_realeconomy.csv`), that are out of bounds (Telang Usan 2018:
unemployment 293%), or that repeat another area's figures exactly (35 of Kedah's 36 state seats in
2021–2022) are kept as published. They are listed in `core/obs_flag.csv` (3,704 rows), and each such
observation carries caveat CV15 and `source_flags`; `explain` lists them under `anomalies`. Check C11
reports the two district Gini cells where DOSM's `hies_district` and `hh_inequality_district` disagree
(Johor Bahru and Kulim 2022, by 0.001).

## Income distributions (Phase 2)

DOSM's HIES percentile files for Malaysia and the 16 states and territories (2019, 2022, 2024), as
published: for each percentile group p (1 to 100) the mean, median, lowest and highest household
income in it (`hh_income.gross.pctile_group.{mean,median,min,max}`, breakdown `percentile=001…100`).
The highest income in group p is the p-th percentile cut-off. DOSM warns these carry larger relative
standard errors and publishes none, so every row is `reliability = low` (caveat CV13) and
`compare_geos` refuses to rank places on them.

`get_distribution(indicator, geo, period, below=None)` returns the 100 groups and the decile cut-offs,
each with its `obs_id`. Given `below` (RM per month) it returns the share of households earning less
as the **published bracket** (rule DIST1 in `meta/derivation.csv`): k% to k+1%, where k groups lie
wholly below the threshold. Nothing is interpolated. Checks C9 (cut-offs rise with the percentile;
`get_distribution` relies on it) and C10 (the 50th cut-off against the headline median) run on every
build. C10 is INFO: of 51 place-years, 39 agree exactly, 6 differ by RM1 and 6 by RM2 to RM14 (Putrajaya 2022: -RM14); both
figures are kept as published.

## National accounts and reproducing the curated tables (Phase 2)

GDP at current prices and its income components (compensation of employees, gross operating surplus,
taxes and subsidies on production) for Malaysia, 2010 onwards, from DOSM's `gdp_annual_nominal_income`
with DOSM's own lookup codes (i0 to i3.2). GDP comes from the approach tables only. DOSM's long-run
`gdp_gni_annual_nominal` file is a different revision vintage for 2022–2025 (RM0.9–2.3 bn lower) and is
not mixed in.

`derive('per_employed')` (rule DV6) divides an amount in RM by employed persons. It refuses any other
denominator, and its answer carries caveat CV14: it understates the average employee's pay and counts
employers' EPF and SOCSO contributions.

**Phase 2's finish line** is that core reproduces today's curated tables to the last printed digit.
`qa/reproduce_curated.py` (in CI) rebuilds each curated cell through the agent tools, never from the
curated file, and writes `qa/_validation_reproduce.csv`. So far, 230 of 230 cells:
`curated/fact_labour_indicators.csv` (32) and the BNM and MOF columns of `curated/fact_fiscal_headline.csv`
(198, to the sen). The PKKP columns of that table are not claimed: core still reads them from it (Phase 3
moves them to PKKP observations), so that comparison would be circular.

**Federal totals from three publishers.** Revenue, operating spending, gross and net development
spending, loan recoveries, the COVID-19 Fund and the overall balance are held as each institution
published them: PKKP (audited), BNM MSB 3.1 (actual, as reported), MOF Tinjauan Fiskal Jadual 1.1
(actual; one edition per year by the own-volume rule in `curated/pipeline/mof_editions.py`). They are the
same indicator, told apart by `basis` and edition. `get_series` returns all of them unless asked for one
(`publisher='pkkp' | 'bnm' | 'mof'`), and `Warehouse.get` never chooses between publishers silently;
`derive('growth')` refuses to mix two publishers. FY2015–2024 operating and development spending agree to
within RM0.5 million, except 2023 development spending (BNM RM1.25 million and MOF RM1.26 million above the
audited figure, in `qa/known_fails.csv`). PKKP's figures still come through `curated/fact_fiscal_headline.csv`
and carry caveat CV16: their citation is that table, development spending has no page yet, and operating
spending FY2009–2023 is the comparative printed in the following year's volume (the same amount to the
ringgit). Phase 3 cites each year's own volume and page. MOF's COVID-19 Fund for 2018–2019 is not loaded
because the own-volume edition for those years prints no such line.

## National monthly series: CPI, trade, money and credit (Phase 2, 2026-11-05)

`build_national_series` in `core/pipeline/build_core.py`, 8,432 rows, Malaysia only, monthly, as published:

| indicator | L1 file (edition) | rows | months | printed unit |
|---|---|---|---|---|
| `cpi.index`, geo `MY`, `_total` and `coicop=01…13` | DOSM `cpi_headline` (`dosm:cpi_headline@2026-10-19`) | 6,390 | 1980-01 to 2026-09 | index 2010=100 |
| `trade.exports`, `trade.imports`, `trade.balance` | DOSM `trade_headline`, series `abs` (`dosm:trade_headline@2026-10-28`) | 441 each | 1990-01 to 2026-09 | RM |
| `money.m1`, `money.m2`, `money.m3` | BNM MSB 1.3 (`bnm:msb_1_3@2026-08-01`) | 161 each | 2013-01 to 2026-05 | RM million |
| `credit.loans.banking_system`, `_total` and `bank_type=commercial / islamic / investment` | BNM MSB 1.18, column `tot_fin` (`bnm:msb_1_18@2026-08-01`) | 236 (59 months × 4) | 2021-07 to 2026-05 | RM million |

* **National CPI is the same indicator as state CPI.** Checked before joining them: the same DOSM
  product (`cpi_2d.csv` and `cpi_2d_state.csv`), the same base (the 2010 average of the national
  headline index is 100.02; Selangor's is 99.98), the same 14 codes (`overall`, `01`…`13`), unit and
  precision. In DOSM's national file divisions 08, 10, 11 and 13 start in 2003-01 and 12 in 2010-01; the
  1,464 earlier cells are blank and have no row. The file is one series on 2010=100 from 1980; it does
  not say how earlier bases were linked.
* **New refusal.** With Malaysia's CPI in core, `derive('ratio')` would have divided a state's index by the
  national one ("is Selangor dearer than Malaysia?"). `derive` now refuses `ratio`, `difference` and
  `gap_pp` of an index across two places (rules DV2 and DV5, caveat CV8); `compare_geos` already refused.
* **Trade.** Check C12 tests balance = exports − imports on all 441 months: exact to the ringgit. (In L1,
  exports = domestic exports + re-exports, and the total = exports + imports, also hold on every row; those
  columns are not loaded.) 49 months are deficits, kept negative as published. DOSM's `growth_mom` and
  `growth_yoy` rows are its own transforms and are not loaded. Caveat CV19: DOSM says the latest two
  months may be revised, and its 2026-11-04 release revised 175 earlier rows (`sources/dosm/README.md`).
  Core holds the current vintage only, like every DOSM series; the replaced one is logged in
  `sources/dosm/data/_vintage_log.csv` and recoverable with `vintage_get.py`.
* **Money.** In MSB 1.3, M1 = currency in circulation + demand deposits, M2 = M1 + narrow quasi-money,
  M3 = M2 + deposits placed with other banking institutions, on every row (to 10⁻⁹ RM million; BNM's
  validator V4 and rechecked here). The table serves monthly rows only. Whether a level is the month's end
  or its average is not stated in the file, and is not claimed.
* **Loans.** MSB 1.18's `Jumlah/Total` row equals commercial + Islamic + investment banks every month
  (check C13). It is a level outstanding, not lending in the month: it moves by −RM3.2 bn to +RM24.2 bn a
  month while MSB 1.14 records RM145–224 bn disbursed a month. It is **not** the same aggregate as loans
  and advances in BNM's statement of assets (MSB 1.7): that is RM56.2–94.1 bn lower every month, with a
  step from RM59.0 bn to RM82.6 bn in 2022-07. Kept as published, not reconciled (caveat CV20).
* **Check C14**: the sha256 of each file read equals the current row of its vintage log.
* **Not loaded, and why.** The **OPR** (MSB 2.3): one value per year (the row served twice for 2004–2023), with
  no month or day, so the file does not say whether it is the year-end rate or an average; its interbank
  columns print 0.00 for 2004–2005; and the API serves nothing after 2024. The **average lending rate**
  (MSB 2.1): the file carries two, `cb_alr_out_loa` (a simple mean whose divisor changes with the number
  of banks) and `cb_wavg_alr_out_loa` (weighted, from 2005), which cross (2013: 4.65 vs 5.43; 2023: 5.32
  vs 5.00); the file has no labels, so which one is the ALR, what `out_loa` and the `ib_` prefix denote,
  cannot be stated from the data. **Loans and advances in MSB 1.7**: its `db_`/`fb_` column prefixes are
  not decodable from the file. To load any of these, first bring BNM's field labels
  (`api.bnm.gov.my/api/specification/tag`) into L1.
* No curated table holds these series, so `qa/reproduce_curated.py` is unchanged (230 of 230).
* Evals: 23 questions (Q124–Q146): a value from L1 for every new series, growth of national CPI and M3,
  and traps (Selangor's CPI over Malaysia's, Kuala Lumpur's minus Sabah's, growth across two places,
  a month of exports over a year of GDP, reversed months, a CPI division before DOSM prints it, the OPR).

## The entity spine (Phase 3, 2026-11-05)

Who spends, receives, audits or is audited (DATA_MODEL §4.5). The decisions are committed data in
`meta/`; `core/pipeline/build_entities.py` builds `dim_entity`, `bridge_entity_code` and
`entity_name` from them and from the votes printed in every PKKP volume (FY2009-2024) and Anggaran
book (2024-2026).

| File | What it holds |
|---|---|
| `meta/entity_register.csv` | every `entity_id` ever issued (E000001 …), with type, sector, parent, reason and `decision_status`; never reused, never deleted (check E1: IDs contiguous) |
| `meta/entity_code.csv` | every readable code of an entity (`federal_gov` MY, `state_gov` MY-01…MY-13, `maksud_bekalan` B.xx, `maksud_pembangunan` P.xx) with its years and a proof |
| `meta/spending_head.csv` | T.01-T.14 (Tanggungan) and P.70 (contingency reserve): spending heads, not bodies |

The identity rule (decision D26), declared before any spending is loaded against it:

* **A federal body is its supply vote.** A B code keeps one ID through renames and portfolio
  changes while it is printed every year (B.23 has held four portfolios since 2009; it is one vote).
* **Its P code is the same body**, including the years after the B vote ends: P.29 is printed
  2019-2021 after B.29 (Energy, Green Technology and Water) ended in 2018, paying for its projects.
* **A B vote printed again after a lapse is a new body** unless a person links it. B.15 (Economic
  Affairs 2018-2020; Economy from 2023), B.26 (2009; Entrepreneur Development from 2018) and B.33
  (Environment and Water 2020-2022; Energy Transition from 2024) are split this way and marked
  `proposed`; the tools say so on every answer about them.
* **Renumberings link only with a proof:** B.41→B.63 (Education) and B.49→B.64 (Higher Education),
  approved before the register (`curated/pipeline/build_ministry_fiscal.py`).
* **Budget books do not extend a lineage:** the 2024 and 2025 books reprint B.32 (Federal
  Territories, ended 2022) with zeros; the code resolves to the old ministry, nothing more.

A code printed in a source with no entity for that year **stops the build** and is listed: an ID is
issued only by a person. Checks E1-E8 are in `_validation_entity.csv`. Core's state and federal rows
carry entity IDs (check C15), every citation names its entity, and the tool `get_entity(code, year)`
resolves `B.45` + 2024, `MY-03` or `E000052`, refuses a spending head (`T.13`) and lists every body a
code ever named when no year is given.

## gap_need_vs_money (state level)

**Question:** does money follow need? The method was declared before results were seen and is in
the header of `core/pipeline/build_gap_need_vs_money.py`. In short:

* **Need** (DOSM, same year, never carried forward): poverty, median income, Gini, unemployment, population.
* **State-government money:** audited spending (printed total, or opex + devex where the volume
  prints no total, marked `derived`), non-revenue receipts (mostly federal grants, as recorded by
  the state), both per person.
* **Federal money placed in each state is not published yet.** Today only what state governments
  record receiving can be placed: 0.3–1.5% of federal spending, far below the 60% guard. Each row
  says so. Placing operating spending (schools, clinics, cash transfers) needs the registry series
  `social_transfers_by_state`, `health_facts` and `education_stats` (Phase 3).
* **Under check:** a state-year with an open FAIL on a headline identity (`qa/known_fails.csv`) is
  published with `under_check` naming the check: Pahang 2016/2017/2021/2022, Johor 2018/2019,
  Kelantan 2018, Sarawak 2020.
* The Federal Territories are rows like any other (golden rule 11), marked "no state government".
* Gaps are shown, not filled: e.g. Kedah and Kelantan 2022 spending is not extracted yet.

Verification tier: `machine_checked`. **Before IKRAM publishes from it, a person spot-checks a
sample against the archived pages** (`docs/DATA_MODEL.md` §7.4).

## The agent tools (`apps/tools/warehouse_tools.py`)

`find_indicator`, `get_series`, `get_distribution`, `compare_geos`, `derive`, `explain`,
`get_entity`, `list_documents`, `get_gap_view`. No SQL. Every number comes with its citation, `release_id` (a hash of
`fact_observation.csv`), uncertainty and caveats (`meta/caveat.csv`). Arithmetic only through
`derive` (rules in `meta/derivation.csv`), which refuses mismatched inputs: different years,
units or price bases, a median divided by population, growth across two places. `compare_geos`
returns **bands**, not ranks (rule BAND1: a new band starts after a step of more than 1 percentage
point, or 5% for other units; declared before results were seen), with the national value.

`qa/eval_questions.csv` (159 questions, made by `qa/make_eval_questions.py` from L1 directly)
includes traps: incomparable pairs, small-area rankings, missing documents, and document text that
must come back marked as data. `qa/run_eval.py` runs them in CI.

## Independent verification (2026-11-04)

A blind verifier agent (no access to the pipeline code) re-derived all 720 numeric cells of
`gap_need_vs_money.csv` from L1 and sampled `fact_observation.csv`: **0 mismatches in the view.**
It found, and this commit fixed, each now pinned by an eval question:

* one wrong sign: Negeri Sembilan's 2020 deficit came through as a surplus (the state panel's
  `level_abs` convention). Surpluses now keep the printed sign, and check C8 tests every row's value
  against its printed value × unit scale (62,052 rows);
* `derive('growth')` accepted reversed periods, a zero base and spans across series breaks
  (`meta/series_break.csv`: poverty line 2019, population rebase 2020, LFS 2025); `ratio` accepted two
  different rates over different universes; `compare_geos` banded CPI index levels. All now refused;
* the federal total in the view had no citation and left out the COVID-19 Fund (2020-2022); it is
  now three cited observations (`federal_source_obs_ids`);
* integer years, a state name instead of a code, and dict inputs crashed or returned silent empties.

`file_id` on a state-accounts row is the sha256 of the **PDF volume** (the document the figure is
printed in), not of the L1 CSV; the PDF is recoverable from the `l0-archive` release once archived.
