# sources/rmk — Malaysia Plans (Rancangan Malaysia): the plan targets

The government's five-year plans and their mid-term reviews, as printed. They are the target side of
`gap_target_vs_outcome`.

| plan | file | held |
|---|---|---|
| RMKe-12 (2021-2025) | `raw/rmk12.pdf`; sha256 and source URL in `data/_documents_manifest.csv` (Kementerian Ekonomi, rmke12.ekonomi.gov.my) | appendix (Lampiran) Jadual 5, 10 and 14 |
| KSP RMKe-11 (the Eleventh Plan's mid-term review) | `raw/ksp_rmk11_lampiran_f.pdf` (www.ekonomi.gov.my) | Lampiran F, Jadual F-3: federal development allocation (revised) and spending by state, 2016-2017 |

* `data/rmk12/fact_rmk12_lampiran.csv`: one row per printed cell (1,070 cells). Each row has its table, section
  (the state, for Jadual 5), line, measure, the value as printed, unit, pdf page and printed page (A-6 to A-19).
  The measures are:
  * `sebenar_<year>`: actual;
  * `sasaran_2025`: the 2025 target;
  * `purata_rmk11_2016_2020`: RMKe-11's average growth, actual;
  * `sasaran_purata_rmk12_2021_2025`: RMKe-12's average growth target.

  A range (`-3.5 ~ -3.0`) keeps both ends (`value`, `value_hi`). A lone `-` is nil.
* `pipeline/extract_rmk12.py` extracts the cells (pdftotext -layout of the cited pages).
  `pipeline/validate_rmk12.py` checks the tables' own identities; results are in `data/_validation_rmk12.csv`:
  * Jadual 10's balances;
  * Jadual 14's sectors and unemployment rate;
  * Jadual 5's growth rates against its levels.

  Jadual 5's KDNK is larger than its five sectors by the import duties the table does not print. That is DOSM's
  definition of state GDP, so the check tests that the residual is positive and small. 3 growth rates of small
  sectors differ from their levels by more than rounding (WARN, kept as printed).
* Footnote kept as data: **'WP Kuala Lumpur' includes WP Putrajaya.** Core holds that row as MY-14 with
  breakdown `geo_scope=MY-14+MY-16`, never as Kuala Lumpur's own total.

Licence: `to_confirm` (an official publication, cited). Not yet in the L0 archive (registry R7 OPEN): run
`meta/l0_archive.py` with GitHub access.

KSP RMKe-11 Jadual F-3 (`data/ksp_rmk11/fact_ksp_rmk11_f3.csv`, 16 rows; series `federal_devex_by_state`):
* the 2016-2017 total spending, RM86,879 juta, equals PKKP's audited gross development spending for FY2016 +
  FY2017 within RM0.12 juta (check F3);
* 56.0% is named to a state or to the Federal Territories (one row for all three); 'Pelbagai Negeri'
  (multi-state) is 43.8%;
* the period is one two-year column, so it cannot be split by year.

Checks are in `data/_validation_ksp_rmk11_f3.csv`. Whether this split may place federal spending by state
(D29/D30) is a decision for the owner; it is not used for placement today.
