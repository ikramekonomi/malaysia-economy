# core/: the conformed layer (L2) and the first gap view

Phase 1 of `docs/DATA_MODEL.md` §15 (**state level, end to end**), and Phase 2 so far: health,
education and services, the **small areas** (districts, parliamentary and state seats), national accounts,
federal totals by publisher and the **national monthly series** (CPI, trade, money and credit). Everything here is derived
from `sources/` (L1) and rebuilt by the scripts in `core/pipeline/`; never edit these CSVs by
hand (golden rule 1). CI rebuilds them on every PR and fails if the committed files differ.

```
python3 core/pipeline/build_entities.py           # dim_entity + bridge_entity_code + entity_name (Phase 3)
python3 core/pipeline/build_core.py               # dims + fact_observation + _validation_core.csv
python3 core/pipeline/build_flows.py              # fact_money_flow.csv + _validation_flow.csv (Phase 3)
python3 core/pipeline/build_gap_need_vs_money.py  # gap_need_vs_money.csv + _validation_gap_need.csv
python3 qa/run_eval.py                            # 209 questions against the agent tools
python3 qa/reproduce_curated.py                   # curated tables rebuilt from core, digit for digit
```

## What is in it

| File | Rows | Grain |
|---|---|---|
| `dim_geo.csv` | 1,006 | Malaysia, `_unallocated`, 16 states and FTs (ISO 3166-2:MY), 166 districts (boundary set `dosm_2020`), 222 parliamentary seats and 600 state seats (boundary set `ge15`) |
| `geo_hierarchy.csv` | 1,020 | child → parent, one row per hierarchy (`administrative`: district → state; `electoral`: DUN → parlimen → state) |
| `dim_period.csv` | 618 | years, months (monthly from 1980-01 for national CPI) |
| `dim_indicator.csv` | 65 | definitions from `meta/indicator.csv` (unit, statistic, universe, price basis, additivity, expected coverage) |
| `dim_breakdown.csv` | 181 | `_total`, `sex=…`, `coicop=…`, `bank_type=…`, `staff_type=…`, `stage=…`, `crime_category=…`, `percentile=001…100` |
| `fact_observation.csv` | 138,511 | indicator × geo × period × breakdown × entity × basis × edition × vintage (state 87,985; DUN 18,000; district 11,013; national 10,943; parlimen 6,660; unallocated 11) |
| `dim_entity.csv` | 68 | who: the federal government, 13 state governments, 47 federal votes, 4 group recipients, 3 territory administrations (Phase 3) |
| `fact_money_flow.csv` | 276 | money moving from one body to another: federal grants to governments (PKKP T.12, B.11, and B.32/B.06 by name to the territories' administrations), FY2010-2024 except FY2015 |
| `bridge_entity_code.csv` | 112 | readable code → entity, with validity years, scope and proof |
| `entity_name.csv` | 240 | every name an entity was printed under, by code and years |
| `entity_lineage.csv` | 15 | where a body's work went when its vote lapsed (D28): a link between two bodies, with printed evidence (`entity_lineage_evidence.csv`, 66 lines with PDF pages and both votes' spending in the move year) |
| `gap_need_vs_money.csv` | 80 | 16 states and FTs × 5 HIES years (2014, 2016, 2019, 2022, 2024) |
| `fact_placement.csv` | 14,112 | every audited development project × year (PKKP FY2009-2024 except FY2015) with the place its name names: `stated_state`, `parsed_district`, `parsed_place`, `multiple_states`, `peninsula` or `none` (D29) |
| `gap_federal_placement.csv` | 270 | federal money placed by state from the federal accounts (projects by name + grants by name) × 15 years, with each year's `placed_share`; amounts by state withheld below 60% |
| `gap_budget_vs_actual.csv` | 1,440 | federal body × year × flow (opex, devex): the accounts' estimates (or devex allocation), the Budget book's original estimate, the audited actual and the book's reprint; execution rate and status (Phase 5) |
| `gap_reported_vs_audited.csv` | 89 | federal headline × year: PKKP audited, BNM MSB 3.1 and MOF Tinjauan Fiskal side by side, each pair's signed difference and status (Phase 5) |
| `gap_obligations_growth.csv` | 68 | federal obligation × year: debt, PFI, commitments, guarantees at 31 December (PKKP memorandum), growth against debt's (Phase 5) |
| `gap_target_vs_outcome.csv` | 41 | plan target × place: RMKe-12's 2025 targets (GDP by state, federal finance, labour) beside the outcome (Phase 5) |
| `gap_revenue_estimate_vs_collected.csv` | 90 | federal revenue by type (tax, non-tax, non-revenue receipts, Federal Territories, total) × year: the accounts' original and revised estimates and actual beside the Budget revenue books'; collection rate and status (Phase 5) |
| `gap_federal_vs_state.csv` | 594 | federal paid (PKKP flows) vs state recorded (state accounts): capitation and Concurrent List grants × 16 places × FY2014-2024, plus each year's all-states row; named grants for Kedah, Selangor, Sabah, Sarawak; federal loans vs state debt × 16 × FY2014-2024 |

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
curated file, and writes `qa/_validation_reproduce.csv`. Now 1,574 cells reproduced and 8
explained, 0 FAIL: `curated/fact_labour_indicators.csv` (32), the BNM and MOF columns of
`curated/fact_fiscal_headline.csv` (198, to the sen), its PKKP columns (80; since Phase 3.3 core reads them
from each year's own volume, independently of curated: equal within the printed whole ringgit, FY2009 opex
and transfer equal to the ringgit because curated reads them from the FY2010 volume's whole-ringgit
comparative column, EXPLAINED) and `curated/fact_ministry_fiscal.csv` (1,267; 6 FY2009 rows EXPLAINED).

**Federal totals from three publishers.** Revenue, operating spending, gross and net development
spending, loan recoveries, the COVID-19 Fund and the overall balance are held as each institution
published them: PKKP (audited), BNM MSB 3.1 (actual, as reported), MOF Tinjauan Fiskal Jadual 1.1
(actual; one edition per year by the own-volume rule in `curated/pipeline/mof_editions.py`). They are the
same indicator, told apart by `basis` and edition. `get_series` returns all of them unless asked for one
(`publisher='pkkp' | 'bnm' | 'mof'`), and `Warehouse.get` never chooses between publishers silently;
`derive('growth')` refuses to mix two publishers. FY2015–2024 operating and development spending agree to
within RM0.5 million, except 2023 development spending (BNM RM1.25 million and MOF RM1.26 million above the
audited figure, in `qa/known_fails.csv`). Since Phase 3.3 (2026-11-05) PKKP's figures are read from each
year's own volume: Penyata Prestasi Kewangan (`fact_financial_performance`, FY2010-2024, whole ringgit) and,
for FY2009, Akaun Hasil Disatukan and the development grand total, each cited to its page; caveat CV16 is
retired. The transfer to the Development Fund is its own indicator
(`federal_gov.expenditure.transfer_development_fund`), so operating votes = opex + transfer (check C16). MOF's COVID-19 Fund for 2018–2019 is not loaded
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
| `meta/entity_lineage.csv`, `meta/entity_lineage_evidence.csv` | where a body's work went at a vote lapse, and the printed lines on both sides that show it (D28) |

The identity rule (decision D26), declared before any spending is loaded against it:

* **A federal body is its supply vote.** A B code keeps one ID through renames and portfolio
  changes while it is printed every year (B.23 has held four portfolios since 2009; it is one vote).
* **Its P code is the same body**, including the years after the B vote ends: P.29 is printed
  2019-2021 after B.29 (Energy, Green Technology and Water) ended in 2018, paying for its projects.
* **A B vote printed again after a lapse is a new body** unless a person links it. B.15 (Economic
  Affairs 2018-2020; Economy from 2023), B.26 (2009; Entrepreneur Development from 2018) and B.33
  (Environment and Water 2020-2022; Energy Transition from 2024) are split this way, and a person confirmed
  all six as separate bodies (D28). The tools warn on every answer about them that the code was also held by
  a different body.
* **Where the work went is lineage, not identity (D28).** In each gap the work was paid from another vote,
  so `meta/entity_lineage.csv` links the bodies with the printed lines that show the move
  (`meta/entity_lineage_evidence.csv`, re-found in PKKP L1 on every build):

  | Link | From → to | First year | Mid-year | What moved |
  |---|---|---|---|---|
  | L01 | B.06 Prime Minister's Dept → B.15 Economic Affairs | 2018 | yes | economic planning (EPU), statistics |
  | L09 | B.22 Rural Development → B.15 Economic Affairs | 2018 | yes | MARA, RISDA |
  | L10 | B.15 → B.22 | 2019 | no | MARA |
  | L02 | B.15 → B.06 | 2020 | yes | economic planning, statistics |
  | L11 | B.15 → B.22 | 2020 | yes | RISDA |
  | L03 | B.06 → B.15 Economy | 2023 | no | economic planning, statistics, corridor authorities |
  | L04 | B.26 (2009) → B.25 Domestic Trade, Co-operatives | 2009 | no | Cooperatives Commission (B.25 spends all of FY2009) |
  | L05 | B.26 (2009) → B.22 Rural Development | 2009 | yes | MARA |
  | L06 | B.25 → B.26 Entrepreneur Development | 2018 | yes | cooperatives |
  | L07 | B.33 Environment and Water → B.23 Natural Resources | 2023 | no | water, sewerage, environment |
  | L08 | B.23 → B.33 Energy Transition | 2024 | no | water, sewerage, energy (environment stays in B.23) |
  | L12 | B.49 Higher Education → B.41 Education | 2013 | yes | universities, polytechnics |
  | L13 | B.64 Higher Education → B.63 Education | 2019 | no | universities, qualifications agency |
  | L14 | B.63 → B.64 | 2020 | yes | universities, qualifications agency |
  | L15 | B.41 Education → B.64 Higher Education | 2015 | no | universities, qualifications agency (new vote's side evidenced at vote level: FY2015 activity names are OCR-provisional) |

  `first_year` is the first year the new body's vote prints the work; a mid-year move splits that year's
  spending between both votes. The build tests both votes' actual spending (leaf rows) in the move year and
  the year before (E9). A year inside a lapse (`get_entity('B.15', 2021)`, `('B.64', 2014)`) returns the
  links out of the body before and into the body after.
  A series joined across a link changes scope: compare the named activities, not the vote totals. Links are
  recorded at the lapses and the moves that led to them, not for every move between ministries.
* **Renumberings link only with a proof:** B.41→B.63 (Education, printed every year), approved before the
  register (`curated/pipeline/build_ministry_fiscal.py`).
* **Higher Education is three bodies (D31, decided by a person 2026-11-05):** B.49 (2009-2013, E000056), B.64
  2015-2018 (E000067) and B.64 from 2020 (E000068). Each time its vote lapsed, its work was printed under
  Education's vote (FY2013-2014, FY2019), so like B.15, B.26 and B.33 the runs are separate bodies joined by
  lineage (L12-L15). The earlier analyst rule, and `curated/fact_ministry_fiscal`, still treat it as one
  ministry; core no longer does.
* **Budget books do not extend a lineage, and can name an older holder:** a book is tabled before its year,
  so it can reprint a lapsed vote. The 2024 book prints B.33 as the lapsed KASA (`Kementerian Alam Sekitar
  dan Air**`, zero estimates), not its successor; the 2024 and 2025 books reprint B.32 (Federal
  Territories, ended 2022) with zeros. Such reprints are `scope`d rows of `meta/entity_code.csv`
  (`anggaran:2024`): a scoped row wins for that source only, so `get_entity('B.32', 2024)` is not held.

A code printed in a source with no entity for that year **stops the build** and is listed: an ID is
issued only by a person. Checks E1-E10 are in `_validation_entity.csv`. Core's state and federal rows
carry entity IDs (check C15), every citation names its entity, and the tool `get_entity(code, year)`
resolves `B.45` + 2024, `MY-03` or `E000052`, refuses a spending head (`T.13`) and lists every body a
code ever named when no year is given.

## Federal spending by who spends it (Phase 3, 2026-11-05)

`federal_gov.vote.opex` and `federal_gov.vote.devex`: 3,899 observations, one per vote, year, basis and
edition, with `entity_id` = the vote's body (46 bodies). The T heads (Tanggungan) and P.70 sit under the
federal government with breakdown `charged_head=T.xx` / `reserve_head=P.70`. Each figure is the vote's
printed total, cited to its volume and page:

| Source (L1) | Basis | Rows |
|---|---|---|
| PKKP `fact_opex_maksud`, FY2009-2024 | audited (sebenar); budget_estimate (anggaran asal); revised_estimate (anggaran dipinda), all printed in the audited volume | 814 each |
| PKKP `fact_devex_maksud` (Lampiran 2, the vote's JUMLAH line), FY2009-2024 | audited | 453 |
| Anggaran Perbelanjaan books 2024-2026 (B/T: mengurus, or a head's JUMLAH where no mengurus line is printed; P: pembangunan) | budget_estimate (the book's year and the year before); actual (MOF, the two years before) | 1,004 |

* **They add up** (check C16): every year's audited votes plus heads equal the printed operating total
  after the transfer to the Development Fund, and the development votes the printed grand total, within RM1,
  FY2009-2024. The one exception is FY2009 development (RM224 million short of the printed total), where
  five printed vote totals disagree with their own project lines; those five carry flag
  `leaf_total_mismatch` and caveat CV21 with curated's diagnosis.
* **Blocks are not double counted:** P.63 is printed in two blocks in FY2019-2020 (Pendidikan,
  Pendidikan Tinggi); only the vote total is loaded, and the build checks it is the sum of the blocks.
* **A budget book restates the past** (caveat CV22): the 2025 book's 2024 estimates differ from the 2024
  estimates as tabled on the 11 votes reorganised in December 2023; both are kept, each with its edition.
* **Caveats:** CV23 on every vote figure (gross, not placed; B.12 carries the transfer to the Development
  Fund, so operating plus development votes double count it); CV24 on growth of one body (scope changes
  without a change of name); CV21 for the FY2009 mismatches (`ours_suspected` also `reliability=low`).
  Blind verifier: `qa/audits/2026-11-05_phase3_vote_verifier.md`.
* **Reproduces curated:** `qa/reproduce_curated.py` rebuilds every row of `curated/fact_ministry_fiscal.csv`
  (1,267) through the tools: 1,261 to the sen; 6 FY2009 development rows differ because curated sums the
  project lines and core takes the printed total, each EXPLAINED by curated's own register.
* **Tools:** `get_series(..., entity=...)` takes a vote code (resolved year by year: `B.63` before 2015 is
  nobody, because Education printed as B.41 then), a state or an entity_id; `derive('growth')` refuses two
  different bodies or two budget books (rule DV3); `derive('difference')` of audited and budget_estimate is
  the budget-vs-outcome gap.

## Money flows: federal grants to the states (Phase 3, 2026-11-05)

`fact_money_flow.csv` holds money moving between two bodies (DATA_MODEL §5.2), only where the payer's accounts
show it (D27). First slice: the federal grants and assignments to the states, Tanggungan T.12
(programme 010000), one row per printed activity per year, audited, from PKKP's operating detail.

* **Recipient by code, with a name guard** (`meta/flow_rule.csv`): the special annual grants to Sabah and
  Sarawak and the annual payments to Selangor and Kedah go to that state's government (geo stated); the
  capitation grant, the state road maintenance grants and the revenue growth grant go to the state
  governments as a class (E000060), and the local authority grant to the local authorities as a class
  (E000061), geo `_unallocated`: the federal accounts do not split them by state and they are not split here.
* **Checks** (`_validation_flow.csv`): every activity has a rule (F1), its printed name matches (F2), a
  year's flows equal the programme's printed JUMLAH to the sen (F3), entities registered (F4), the grants stay
  inside the T.12 head (F5). FY2009 (no activity tier) and FY2015 (the image-only scan, OCR-provisional) are
  not loaded (F6).
* **Tool** `get_flows(to, frm, start, end)`: `to='MY-12'` returns Sabah's named grants and, beside them, the
  class grants of those years (`not_split_by_state`); a state with no named grant gets the class grants and
  an answer saying so. Caveat CV25.
* **A floor, not the whole:** development grants and federal projects in a state are not loaded; every
  `get_flows` answer says so (`coverage`),
  lists the years in range that are not held, and tells the agent not to add up a state's named grants as what
  it received. Blind verifier: `qa/audits/2026-11-05_phase3_flows_verifier.md` (140 of 140 re-derived).
* **B.11 grants to governments** (second slice): supply vote B.11 programme 020000, matched by printed name
  because the activity codes renumber almost every year (check F8: a rule matches at most one activity a
  year). The flow is the activity's 40000 'Pemberian dan Kenaan Bayaran Tetap' line (F9): a block can also
  print a services line not paid to anyone, and in FY2017 two printed activity totals leave that line out
  (page-proved in PKKP's own validation). Petroleum duty compensation (RM240 million a year) and the
  transfer-money refund go to Sabah and Sarawak together (E000062); the Concurrent List grants and state road
  slope maintenance to the state governments; street lighting to the local authorities; the special and road
  grants to the Federal Territories' administrations (E000063; under B.06 from FY2024; not found in FY2018,
  where B.32 prints a RM65 million line of about their size whose name does not say so: F10, F11).
  `meta/group_member.csv` says which places each group covers, so Johor is not shown the Sabah-Sarawak grants
  and Kuala Lumpur sees the Federal Territories' grants (not the local-authority grants: nothing shows the
  territories receiving them). Declared and not loaded (F11): the interest subsidy on
  a Sabah housing company's loans, the World Bank/IsDB offices in Kuala Lumpur, the territories ministry's
  service lines (PICC, buses, water), and the local-government ministry's lines (recipient not stated). Blind
  verifier: `qa/audits/2026-11-05_phase3_b11_verifier.md` (94 of 94 re-derived).
* **Grants by name to the territories' administrations** (third slice): Perbadanan Putrajaya (RM60-157 million
  a year), Perbadanan Labuan (RM35-52 million) and Dewan Bandaraya Kuala Lumpur (RM55-76 million to 2014, small
  since; none by name in FY2010 and FY2019), paid under the Federal Territories ministry's vote B.32 and from
  FY2023 under B.06; FY2010-2013 print each as a whole programme with no activity tier, which the name rules
  match. They are local-authority entities (E000064-E000066), geo stated, members of the class E000063; a
  territory's `get_flows` answer lists its administration's grants by name and the class grants beside them.
  Declared and not loaded (F11): lines only tagged `(DBKL)`/`(PL)` or naming a territory (ITIS-DBKL, the Bukit
  Tagar tipping fee, ferry fare discounts, PICC, Putrajaya buses) and FY2009's programme-level grants. Blind
  verifier: `qa/audits/2026-11-05_phase3_territories_verifier.md` (40 of 40 re-derived, 19 page-checked).
* **Not yet:** what each state records receiving (state accounts) matched to these flows; development grants
  and federal projects in a state.

## gap_budget_vs_actual (Phase 5, 2026-11-05)

Was the money budgeted spent? One row per federal body (entity), year and flow (opex: B and T votes; devex: P
votes), PKKP FY2009-2024 plus the Budget books' estimate years (2023-2026). Method declared and committed before
any result (`core/pipeline/build_gap_budget_vs_actual.py`). Each column is one source as printed:

* `estimate_original_pkkp`, `estimate_revised_pkkp`: the audited accounts' original and revised operating
  estimates; for devex the accounts print one column, 'Anggaran' in Lampiran 2, loaded as basis `allocation`
  because it is not the tabled estimate (FY2024: RM85.2b against the Budget book's RM92.0b).
* `estimate_original_book`, `actual_book`: the Budget books' original estimate for the year and their reprint of
  the actual, beside the audit (`book_vs_pkkp_*`: all 102 operating estimates the accounts and the book both
  print agree, and so does every reprinted actual; PETRA and Digital, created during FY2024, have no original
  estimate in the accounts).
* `execution_rate` = audited actual / revised estimate (or allocation): `within_estimate` 0.90-1.00,
  `underspent` below 0.90, `overspent` above 1.00, `not_held` where a side is missing. No ranking. For devex the
  rate is against the accounts' allocation; `execution_rate_book` = audited actual / the Budget book's original
  estimate is beside it (devex FY2023: allocation RM93.4b against the book's RM99.0b).
* One Budget book per year for `estimate_original_book` (the book of that year; V7 proves the column adds up to
  that book). A later book restates a year under its own, reorganised votes (the 2025 book prints FY2024 under
  PETRA and Digital, money the 2024 book held under the old ministries); that figure is named in the row's note,
  never added. A book's reprinted actual is shown only on the body that held the vote that year: the 2025 book
  files KASA's FY2022 spending (RM3.43b) under PETRA's vote B.33, which is not PETRA's (V8 lists them).

How to read the status words: `P.70` (the contingency reserve) is always underspent because it is drawn by
transfers to other votes; B.12 (contributions to statutory funds, incl. the Development Fund) is always overspent
because it is money moved to those funds; spending above the printed estimate may have been authorised later
(supplementary supply), which this view does not show. FY2009 devex: the rows add up to the vote observations
but not the printed grand total (P.26 and P.44 were transferred out during the year, RM224.3m, documented at L1;
those rows carry CV21). FY2015 devex allocations are OCR-read from a scan (grand total off its lines by RM60,000).

A body is its vote (D26, D28, D31): a lapsed vote's successor is another body, so rows are never joined across
bodies. Tool: `get_gap_view('gap_budget_vs_actual', year=..., entity='B.45')`. Checks V1-V8 in
`_validation_gap_bva.csv`; blind verifier: `qa/audits/2026-11-05_phase5_budget_vs_actual_verifier.md`.

## gap_revenue_estimate_vs_collected (Phase 5, 2026-11-05)

Did revenue come in as estimated? Core gains `federal_gov.revenue.by_type` (breakdown `hasil_kod`: the Budget
revenue book's section codes 60000 tax, 70000 non-tax, 80000 non-revenue receipts, 90000 the Federal
Territories, and `_total`), from PKKP Nota 5(a) (FY2009-2024: original and revised estimates, actual; PKKP prints
names, mapped to the codes by a declared table, `REV_NAME_TO_KOD` in build_core) and the Anggaran Hasil books
2025-2026. Check C18: the types add up to the printed total, every year and basis (48 PASS).

The view (method declared before results, `core/pipeline/build_gap_revenue.py`): one row per type and year;
`collection_rate_original` = actual / original estimate, status `on_estimate` (0.97-1.03), `above_estimate`,
`below_estimate`, `not_held`; the book's revised estimate and actual beside the audit (agree within RM1: 5 of 5
revised estimates and 8 of 10 actuals; FY2024's total and non-revenue receipts are RM144 below the audit in the
book, kept as printed; whole ringgit on both sides, so not rounding). FY2009 (the C1 revenue statement) prints
a fifth type, miscellaneous receipts, kept apart; the FY2010 volume reprints the same figure as non-revenue
receipts, so read 80000 over time with that row (each row's note says so). Checks R2-R6 in
`_validation_gap_rev.csv` (R1 is C18 in core); blind verifier:
`qa/audits/2026-11-05_phase5_revenue_verifier.md`.

How to read it: 80000 (refunds of expenditure and receipts from government agencies) is set by transfers, not
collection, and is `above_estimate` in 13 of 15 years (FY2024: 4.78x the estimate); it is not revenue
performance. PKKP's own printed percentage is against the revised estimate, which is set late in the year, so it
reads closer to 100% than `collection_rate_original` (FY2015 tax: 0.90 of the original, 97.3% printed). The
FY2023 estimate is Budget 2023 as re-tabled in February 2023. Book reprints carry CV29.

## gap_reported_vs_audited (Phase 5, 2026-11-06)

Do MOF, BNM and PKKP agree? One row per federal headline and year, where at least two of them print it:
* revenue;
* operating spending (before the transfer to the Development Fund);
* gross development spending;
* the COVID-19 Fund;
* loan recoveries, net development spending and the overall balance (BNM and MOF only).

The method was declared before the view was built (`core/pipeline/build_gap_reported_vs_audited.py`):
* each publisher's figure is taken as core holds it: PKKP from that year's own volume; BNM's annual row (MSB
  3.1); MOF's edition of year+2 (Jadual 1.1, 5.1 in the 2023 edition), with what later editions print
  differently in `mof_restated_in`;
* each pair (bnm-pkkp, mof-pkkp, mof-bnm) is signed and graded:
  * `agree` within half the coarser printed unit (MOF: whole RM juta; PKKP: whole ringgit, sen in FY2009; BNM:
    the decimals it serves, which vary by year from RM1m to the sen);
  * `differ_minor` within 0.1%;
  * `differ` beyond 0.1%.

**The status grades print resolution, not size: always read the RM gap.** A finer printing can be
`differ_minor` where a coarser one, further off in ringgit, is `agree`. For example, revenue 2019: BNM +RM41,124
is `differ_minor`, while MOF +RM244,124 is `agree`.

Result, 89 rows: no pair differs by more than 0.1% in any year.
* **MOF against PKKP:** 32 of 35 pairs agree to the RM juta; 2 of them are 0 = 0 (the COVID-19 Fund after it
  closed). Two of the three exceptions agree in MOF's later editions:
  * revenue 2020 (+RM1.05m; the 2023 and 2024 editions print 225,075, which agrees);
  * gross development spending 2023 (+RM1.26m; the 2027 edition prints 96,090, which agrees).
  * The third, revenue 2018 (-RM0.56m), is MOF rounding its lines so that its table adds up.
* **BNM against PKKP:** 41 of 53 pairs agree. The rest are RM2.5 to RM1.25m.
* **MOF against BNM:** the 5 exceptions are RM0.53m to RM0.97m, rounding.

Not compared:
* PKKP's overall deficit is struck after gross development spending (MOF's and BNM's after net), so it is
  another concept.
* PKKP's 'Terimaan Balik Pinjaman dan Pelbagai Terimaan' is broader than the loan recoveries.

BNM's API labels its COVID-19 Fund and overall balance under shifted keys. The proof is in
`sources/bnm/data/_source_anomalies.csv` and core check C20.

Which publisher is right is not decided here (a reported figure can be a later revision or another scope). Checks
G1-G5 are in `_validation_gap_rva.csv`. Blind verifier: `qa/audits/2026-11-06_phase5_reported_vs_audited_verifier.md`.

## gap_obligations_growth (Phase 5, 2026-11-06)

Are off-budget obligations growing faster than debt? Core gains `federal_gov.obligation.*` (six stocks at 31
December from PKKP's memorandum accounts and guarantee registers, each year from its own volume; check C19):
* debt, FY2009-2024;
* PFI liabilities, financial commitments and committed guarantees, FY2018+ (first printed then);
* statutory loan guarantees, FY2009-2024 (FY2009-2011 print no deposit section, so the register total is the
  loans; O2 proves it);
* contributor and depositor guarantees, FY2010+ (FY2010-2011 from Nota 10(b); the FY2012 note equals the
  register, C21).

The view (method declared before results, `core/pipeline/build_gap_obligations.py`) gives each instrument's
year-on-year growth against debt's, its ratio to debt, and an index (first year = 100) beside debt's.

Over each instrument's span (check O5), debt grew 3.44x (2009-2024) and 1.68x over 2018-2024:
* PFI liabilities: 0.90x (falling every year since 2020: repayment by the two vehicles PKKP's line covers;
  MOF's PPP and PFI obligations, RM148.6b at 2024, are several times larger and not in this line);
* commitments: 1.22x;
* committed guarantees: 1.43x;
* statutory loan guarantees: 3.95x, against debt's 3.44x over the same years;
* deposit guarantees: 3.29x, against debt's 3.07x since 2010 (mostly EPF members' savings: not borrowing).

So only the statutory guarantees outgrew debt over their span.

Restatements are kept in the note and never applied (O3). Financial commitments are restated by every later
volume, by up to RM7.2b (FY2021, in the FY2022 volume).

Never add instruments (CV30):
* commitments include the committed guarantees;
* most committed guarantees (RM210.9b of RM236.2b in 2024) are loans also in the statutory loan-guarantee
  register;
* deposit guarantees are savings.

The FY2018 volume's 2017 comparatives for PFI, commitments and committed guarantees are not used (each year from
its own volume), so those series start in 2018. A blind verifier re-derived every number:
`qa/audits/2026-11-06_phase5_obligations_verifier.md`. The Auditor-General's and MOF's figures stay in `curated/fact_obligations.csv`. Checks O1-O5 are
in `_validation_gap_obl.csv`.

## gap_target_vs_outcome (Phase 5, 2026-11-06)

Was the plan target met? The targets come from a new source, `sources/rmk/`: the Twelfth Malaysia Plan
(RMKe-12, 2021-2025) appendix as printed, 1,070 cells checked against the tables' own identities. Core holds them
as basis `target` (41 observations, check C22):
* real GDP by state, the 2025 level and the 2021/2025 average growth (a new multi-year period code);
* federal finance, 2025;
* the labour market, 2025.

The view sets each target beside its outcome from core:
* DOSM GDP by state (constant 2015 prices), and its 2020-2025 compound growth from the same vintage;
* MOF's FY2025 actuals, with BNM beside them, until PKKP FY2025 is loaded;
* the DOSM labour force survey, 2025.

The method was declared before the targets were extracted (`core/pipeline/build_gap_target.py`). Status states
the position only: `at_target` is within 1% of a level target or 0.1 point of a growth target; otherwise
`above_target` or `below_target`. Whether above is good depends on the line.

Results:
* **GDP growth:** 14 places are computed (13 states and Labuan). 3 grew faster than their target: Selangor
  (7.1% a year against 4.3%), Pulau Pinang (7.1% against 5.4%) and Johor (6.0% against 5.1%). The other 11 grew
  slower. The largest shortfalls are Sabah (2.7% against 6.5%), Kelantan (3.4% against 6.7%) and Terengganu (3.6%
  against 6.6%).
* **Kuala Lumpur:** not computed. The plan's KL row includes Putrajaya, and DOSM prints Putrajaya separately only
  from 2023. The note gives the evidence that DOSM's earlier KL figure includes it, but this is not assumed.
* **Federal finance**, in nominal ringgit:
  * revenue: 1.24x the target;
  * operating spending: 1.25x;
  * gross development spending: 1.08x;
  * overall deficit: RM75.3b against a planned RM68.5b.
* **Labour:** unemployment came in at 3.0% against a 4.0% target.

Extracted but not compared, because core holds no outcome (check T5): GDP per capita, sectors, and Jadual 10's
current balance and %-of-GDP range. Checks T1-T6 are in `_validation_gap_tvo.csv`.

## gap_federal_placement (Phase 3, 2026-11-05)

How much federal spending can be placed in a state from the federal accounts themselves (DATA_MODEL §10, §13
track A; D29). The method, declared and committed before any result by state, is in the header of
`core/pipeline/build_federal_placement.py`:

* **Projects** (`core/fact_placement.csv`, one row per PKKP development project leaf, its actual spending): placed
  in a state when the printed name names exactly one state or Federal Territory (`stated_state`, 2,205 rows), or
  no state but districts of one state (`parsed_district`, 263; DOSM 2020 districts, whole words, common-word names
  excluded; a state named only inside a district's name, as in Kuala Terengganu, counts as that district), or a
  town, region, island or facility listed with its proof in `meta/place_gazetteer.csv` (`parsed_place`, 127:
  Iskandar Malaysia, Cyberjaya, Ipoh, IADA Pekan, IADA Kalaka Saribas, Angkasapuri, ...). A name naming two or more places is `multiple_states` (104); one
  naming only the Peninsula is `peninsula` (136, RM4.24b: PKKP's Peninsula / Sabah / Sarawak split lines, of which
  only the Sabah and Sarawak ones can be placed); 11,277 name none. None of these is placed. The words matched are
  kept (`geo_evidence`); `pdf_page` is the page printing the name, the amounts sit on the facing page.
* **Grants by name** to a state government or territory administration (`fact_money_flow`, `stated`); class
  grants are never split by formula (D27).
* **Class grants at the payer's own split** (FY2019-2024, D30): the Budget books' Lampiran E prints what each state
  was actually paid of each grant (`sources/anggaran`). A grant is placed this way only in a year its national
  total equals PKKP's audited line within RM2 (capitation, road maintenance, revenue growth, petroleum-duty
  compensation, street lighting, state services every year; GTBKK FY2019-2022; the tourism grants, which PKKP
  prints as B.11 'Lain-lain Bayaran Balik', FY2020-2024; the Concurrent List with libraries and museums
  FY2023-2024): RM6.3-7.8b a year (`grants_split_by_payer_rm`). The national test cannot check how MOF split a
  total between states: several states' figures are round hundreds or repeat the previous year's (CV28).
* **Not used:** an agency's seat, or any allocation key (population, staff, need).

| | FY2009 | FY2014 | FY2019 | FY2024 |
|---|---|---|---|---|
| placed (projects by name + grants by name + grants at the payer's split) | RM6.59b (no FY2009 grants held) | RM3.79b | RM9.32b | RM10.90b |
| of which grants at the payer's split (from FY2019) | | | RM6.32b | RM7.76b |
| federal total spending | RM207b | RM259b | RM318b | RM406b |
| `placed_share` | 3.2% | 1.5% | 2.9% | 2.7% |

`placed_share` is under 4% in every year (highest 3.9%, FY2010; 2.5-2.9% from FY2019 with the payer's split), so the amounts by state are withheld by
`get_gap_view('gap_federal_placement', geo, year)` under the 60% guard; the national row and what could not be
placed are returned (the CSV keeps them for verification, marked `publishable=false`). Sabah and Sarawak hold
about 54% of the placed project money over the years held (42-65% by year), partly because the accounts print their lines separately while the
Peninsula's cannot be placed (CV27). Some placed lines are loans, equity or regional agencies. Most federal money (salaries, subsidies, cash transfers, and most projects, whose names name
no place) has no location in the federal accounts. Placing it needs sources by area that are not held (KKM/KPM
by state, STR/JKM recipients by state). A place in a project name is where the project is, not who benefits
(CV27). Checks P1-P6 in `_validation_placement.csv` (P1 WARN: FY2009's project rows are RM410.6m short of its
printed development total, known in that volume's own validation and shown as not itemised).

## gap_federal_vs_state (Phase 3, 2026-11-05)

**Question:** do federal transfers match what states record receiving? Method declared before results were seen,
in the header of `core/pipeline/build_gap_federal_vs_state.py`. Two audited sides, each from its own publisher:
`fact_money_flow` (PKKP) and the new `state_gov.revenue.federal_*` observations (the state's accounts as the
Auditor General's state report prints them; capitation, Concurrent List, and Sabah/Sarawak's all-federal-grants line).

* **Class grants** (capitation, Concurrent List) are paid to the states as a class and not split by state in the
  federal accounts (D27), so from those accounts alone a state row cannot agree or differ: it gives the state's
  receipt and its share of the federal total (from FY2019 the payer's own split adds a per-state side, below). The year's `_states` row tests what must hold: the states that print the grant together recorded no
  more than the federal total (every year consistent; 1-4 of 13 states print it).
* **Named grants**: a state's record of ALL its federal grants must be at least what it was paid by name (Sabah,
  Sarawak: consistent every year printed; Selangor and Kedah print no such line).
* **Loans** (added 2026-11-05, declared before the result): what PKKP says each state government owes the
  federal government at 31 December (`federal_gov.loans_receivable.state_government`, new; the states add up
  to the printed Jumlah Kerajaan Negeri every year, check C17) against the state's own printed public debt.
  Equal expected: `agree` within RM10,000 (the state prints RM juta to 2 dp), else `differ` with the
  difference; where the state's debt table prints another lender (bonds, financial institutions) the federal
  part is compared (`agree_after_other_lenders`). Blind verifier (`qa/audits/2026-11-05_phase3_loans_verifier.md`):
  every federal value right on the page, and no `differ` caused by our extraction; causes the state reports print
  (write-offs, loans turned into grants, interest arrears) are on the rows.
* **Printings**: every printing of a state's figure is listed; Kedah FY2020's Concurrent List grant is 37.51 in its
  own report (CMD.40.2021 J10) and 31.74 in the next (CMD.42.2022 J10), kept as printed (check GF5).
* A state figure exists only where the grant is among the state's top revenue items: `state_not_printed` is not
  zero (CV26); where the state's table could not be parsed the status says `state_table_not_extracted`, and a
  figure printed only in a later volume is listed but not compared (`printed_in_later_volume_only`: two later
  columns were found misaligned on the page). Page-proved notes on single rows: `meta/gap_note.csv`. Blind
  verifier: `qa/audits/2026-11-05_phase3_gap_fed_verifier.md` (418 of 418 re-derived; 59 of 59 state figures
  right on the page). Tool: `get_gap_view('gap_federal_vs_state', geo, year, transfer)`.
* **A third side for the class grants (FY2019-2024, D30):** the Budget books' Lampiran E prints what MOF paid each
  state of each grant. Where its national total equals PKKP's audited line, `federal_by_state_rm` gives the
  state's figure and `by_state_status` compares it with the state's own record (agree within RM10,000): the
  capitation grant agrees in all 14 state-years where the state prints it, the Concurrent List in all 4
  (FY2023-2024). For the Concurrent List in FY2019-2022 it is `lampiran_e_unreconciled`: MOF prints the
  Concurrent List, libraries and museums grants as three columns, the audited accounts as one line, and the three
  together do not equal it (RM54k-2.5m apart), so none is used; which of the three differs cannot be told. MOF's
  figure is not the audited accounts (CV28).

## gap_need_vs_money (state level)

**Question:** does money follow need? The method was declared before results were seen and is in
the header of `core/pipeline/build_gap_need_vs_money.py`. In short:

* **Need** (DOSM, same year, never carried forward): poverty, median income, Gini, unemployment, population.
* **State-government money:** audited spending (printed total, or opex + devex where the volume
  prints no total, marked `derived`), non-revenue receipts (mostly federal grants, as recorded by
  the state), both per person.
* **Federal money placed in each state is not published yet.** This view's federal column counts
  only what state governments record receiving (0.3–1.5% of federal spending); `gap_federal_placement`
  places federal money from the federal accounts themselves (0.6–3.9%). Both are far below the 60%
  guard, and each row says so. Placing operating spending (schools, clinics, cash transfers) needs the registry series
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
