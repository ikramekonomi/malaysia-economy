# Blind verifier: wave 3 DOSM / data.gov.my datasets (2026-11-06)

A separate agent was given the ingest script's docstring, the dataset list, `meta/indicator.csv` and the READMEs.
It did not see the core builder. It checked all 84,023 wave-3 observations against their L1 cells, not a
sample:
- values, geography, period and breakdown key: **0 mismatches**;
- every non-blank L1 value is in core, or the exclusion is documented;
- no primary-key collision;
- printed inflation reconciles to the held CPI indexes within 0.1 point (7,431 of 7,431);
- units correct (ppm vs ug/m3; grammes for gold and silver; 2010 prices).

| # | finding | severity | outcome |
|---|---|---|---|
| 1 | The Salaries & Wages Survey tables are citizens only, except `wages_ethnicity` (all employees); both landed on `_total`, so `get_series` gave 9 rows of 2940 and one of 2663 | critical | fixed: citizens-only rows carry `citizenship=citizen`; `_total` is all employees (2663); the national citizen total is loaded once; definitions, README; `get_series` names the breakdowns held when `_total` is not |
| 2 | Non-citizens held under two keys (ethnicity=noncitizen, citizenship=noncitizen) | medium | fixed: one key, `citizenship=noncitizen`; the duplicate overall rows are not loaded |
| 3 | Mineral extraction is annual, but was stored as monthly | high | fixed: annual; definition corrected |
| 4 | 1,168 negative inflation rows flagged out_of_bounds (CV15) | medium | fixed: rates of change are exempt from the 0-100 rule |
| 5 | Sabah's and Sarawak's districts do not add up to the state (Supra); the CV7 text was wrong for districts | medium | CV7 reworded; gdp.real definition and README |
| 6 | KL's district GDP includes Putrajaya, unflagged | medium | the Putrajaya flag now covers KL's district rows |
| 7 | District GDP probably on pre-2020 boundaries (6 districts print none) | medium | stated in the definition and README (not proven, not assumed) |
| 8 | growth_yoy series dropped without a note | medium | documented (derivable from the levels) |
| 9 | Selangor's water likely includes KL and Putrajaya | medium | coverage notes |
| 10 | Fish landings have no state total | low-medium | definition says states are printed only by coast |
| 11 | `cpi.index`, `gdp.real` and `life_expectancy` definitions not updated | low | updated |
| 12 | Source misprints not registered | low | `verify_wave3_identities.py` (in the suite); 16 breaches registered in `_identity_breaches_wave3.csv` |
| 13 | Formal employees' national total from three files | low | loaded once (from `formal_wages`) |
| 14 | Early-childhood rate denominators missing; perinatal includes stillbirths | low | definition |
| 15 | sector p0-p5 codes unlabelled in dim_breakdown | low | open (label from DOSM's lookup later) |
| 16 | `cpi.index` mixed the annual average with monthly values | low | the annual average is its own indicator, `cpi.index_annual` |
| 17 | Life expectancy for 2026 (the current year) carries status final | low | open (DOSM publishes it as such) |
