# core/: the conformed layer (L2) and the first gap view

Phase 1 of `docs/DATA_MODEL.md` §15 (**state level, end to end**), and Phase 2 so far: health,
education and services, and the **small areas** (districts, parliamentary and state seats). Everything here is derived
from `sources/` (L1) and rebuilt by the scripts in `core/pipeline/`; never edit these CSVs by
hand (golden rule 1). CI rebuilds them on every PR and fails if the committed files differ.

```
python3 core/pipeline/build_core.py               # dims + fact_observation + _validation_core.csv
python3 core/pipeline/build_gap_need_vs_money.py  # gap_need_vs_money.csv + _validation_gap_need.csv
python3 qa/run_eval.py                            # 97 questions against the agent tools
```

## What is in it

| File | Rows | Grain |
|---|---|---|
| `dim_geo.csv` | 1,006 | Malaysia, `_unallocated`, 16 states and FTs (ISO 3166-2:MY), 166 districts (boundary set `dosm_2020`), 222 parliamentary seats and 600 state seats (boundary set `ge15`) |
| `geo_hierarchy.csv` | 1,020 | child → parent, one row per hierarchy (`administrative`: district → state; `electoral`: DUN → parlimen → state) |
| `dim_period.csv` | 258 | years, months |
| `dim_indicator.csv` | 45 | definitions from `meta/indicator.csv` (unit, statistic, universe, price basis, additivity, expected coverage) |
| `dim_breakdown.csv` | 178 | `_total`, `sex=…`, `coicop=…`, `staff_type=…`, `stage=…`, `crime_category=…`, `percentile=001…100` |
| `fact_observation.csv` | 125,850 | indicator × geo × period × breakdown × entity × basis × edition × vintage (state 87,978; DUN 18,000; district 11,013; parlimen 6,660; national 2,188) |
| `gap_need_vs_money.csv` | 80 | 16 states and FTs × 5 HIES years (2014, 2016, 2019, 2022, 2024) |

Indicators: population (state 1970–2026, district 2020–2026), households; median and mean household
income, Gini, household spending, absolute, hardcore and relative poverty (HIES); labour force,
employed, unemployed, participation and unemployment rates (LFS); CPI by state and COICOP
division; real GDP by state; and the 13 states' audited revenue, receipts, operating and
development spending, total spending, surplus and debt.

Every observation carries its value in the base unit (persons, RM) as an exact decimal, the value
and unit **as printed**, its edition and vintage, the sha256 of the file it came from, the L1 row,
and (for state accounts) the PDF page and jadual. DOSM publishes no sampling error for these state
figures, so `reliability = unknown` and answers carry caveat CV1. Nothing is invented.

## Small areas (Phase 2)

DOSM's HIES and LFS small-area files, as published: median and mean household income, Gini, household
spending and absolute poverty for every district (2019–2024), parliamentary seat and state seat
(2019–2024); relative poverty for districts; LFS labour force, employment, unemployment and rates
for districts and seats (2021–2023); and access to piped water, sanitation and electricity by
district (HIES 2016–2024).

* **Codes, not names.** Seats are `MY-09/par:P.001@ge15` and `MY-09/dun:N.01@ge15`: the published
  seat code within its state, on the GE15 boundaries (a redelineation is a new boundary set, never
  a silent re-map, decision D7). Districts join DOSM's 166 districts; the 10 spellings that change
  between years are mapped in `meta/geo_alias.csv`, each with its proof (the two spellings never
  appear in the same year).
* **Uncertainty.** None of these files publishes a sampling error, so every row has
  `reliability = unknown` (caveat CV1). LFS seat figures are the survey's records added up below
  the domain it was designed for (the district), so they are `reliability = low` (caveat CV12).
  **`compare_geos` never bands or ranks a district, parlimen or DUN** (golden rule 9); `get_series`
  answers for one place at a time.
* **Single-district places.** Perlis, Kuala Lumpur, Labuan and Putrajaya are each one district. Where
  DOSM prints no "All Districts" row for them (amenities), their figure is held under the district
  code, and the state row is declared missing in `meta/indicator.csv`, not filled.
* Ministries' own districts (education PPD, health, police) are separate boundary sets: their
  district rows are not mapped to DOSM's districts yet. Only state and national rows are loaded.

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
build. C10 is INFO: six place-years differ by RM2 to RM14 (Putrajaya 2022: -RM14), and both
figures are kept as published.

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
`list_documents`, `get_gap_view`. No SQL. Every number comes with its citation, `release_id` (a hash of
`fact_observation.csv`), uncertainty and caveats (`meta/caveat.csv`). Arithmetic only through
`derive` (rules in `meta/derivation.csv`), which refuses mismatched inputs: different years,
units or price bases, a median divided by population, growth across two places. `compare_geos`
returns **bands**, not ranks (rule BAND1: a new band starts after a step of more than 1 percentage
point, or 5% for other units; declared before results were seen), with the national value.

`qa/eval_questions.csv` (97 questions, made by `qa/make_eval_questions.py` from L1 directly)
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
