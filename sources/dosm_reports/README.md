# sources/dosm_reports — DOSM survey reports, the tables as printed

DOSM publishes each survey twice: as open-data files (held in `sources/dosm`, one figure per row) and as a
report, a PDF and its Excel twin, that prints many more breakdowns. This source holds the reports' Excel twins
cell by cell, exactly as printed. It also records where a report and the open data disagree.

| publication | report | released | tables | cells |
|---|---|---|---|---|
| `household_income_2024` | Household Income Survey 2024: household income | 2025-10-08 | 125 | 15,253 |
| `poverty_2024` | HIES 2024: poverty | 2025-10-08 | 19 | 3,479 |
| `income_inequality_2024` | HIES 2024: income inequality | 2025-10-08 | 51 | 4,834 |
| `household_expenditure_2024` | Household Expenditure Survey 2024 | 2025-10-08 | 116 | 36,401 |
| `labour_annual_2025` | Labour Force Survey 2025, annual tables A1.1-A1.12 | 2026-06-26 | 14 | 1,144 |
| `salaries_wages_2025` | Salaries & Wages Survey 2025 | 2026-09-21 | 47 | 14,683 |

Each publication was found through OpenDOSM's publication pages (open.dosm.gov.my/publications/<id>), which link
the PDF and the Excel file on storage.dosm.gov.my. `data/_documents_manifest.csv` records each file's URL,
sha256, size, release date (OpenDOSM's) and PDF twin. The workbooks themselves (`raw/*.xlsx`) are not in git: they go to the
L0 archive, `meta/l0_candidates.csv`, which stores every file as `<sha256>.pdf` whatever its type.

## The files

* `data/<publication>/cells.csv`: one row per printed figure. Columns:
  * `table_no`, `title_bm`, `title_en`: the table the figure is in. A sheet can hold several tables.
  * `sheet`, `cell`: where it is, as an A1 reference. The cell is the citation.
  * `row_label`: the printed row label. A label continued on the next line is joined.
  * `section`: the last label row above it that carries no numbers.
  * `col_header`: the header texts above it, top to bottom, each carried across its merged span.
  * `value_printed`: the figure as the report shows it, which is the stored number under the cell's own number
    format, rounded half away from zero (the PDF twin prints the same).
  * `value`: the number the workbook stores, in full.
  * `number_format`: the cell's Excel number format.

  A `-` or `..` is kept as printed, with `value` empty.
  Labels printed as numbers are kept as labels: an income class's bounds (`2,000 – 2,999`) and a Tahun/Year
  column. Headings nest in `section` (`Lelaki | Penengah (RM)`).
* `data/<publication>/tables.csv`: one row per table, with its notes as printed (`1 Data merujuk kepada
  warganegara sahaja / Data refer to citizen`, `Nota / Notes: ...`). A table's notes end its body.
* `data/_extraction_coverage.csv`: every numeric cell of every sheet, either captured or the reason it was not.
  The only numbers not captured are whole years in header rows.
* `data/_source_divergences.csv`: figures the report and the open data print differently, with the proof.
* `data/_validation_report_cells.csv`: the checks, from `pipeline/validate_report_cells.py`, which runs offline
  in the suite. The checks were declared before the first run:
  * R1, coverage: every numeric cell is captured.
  * R2, display: `value_printed` equals `value` rounded to the printed decimals.
  * R3, open data: the report equals the open-data file for the same figure (poverty by state, income by
    state, the participation rate, all 2,448 wage cells of Jadual A8-A9). The method was amended once, after the
    first run, to accept the stored number or the printed figure. The audit note lists both runs.
  * R4, identity: the states' household counts add to Malaysia's.
  * R5, one report (added after the blind verifier): a figure the poverty report prints twice must be printed
    the same. Jadual 5.1, 5.3 and 5.4 are checked against chapters 2-4 and income Jadual 2.7: 203 of 204 pairs are
    equal, and the exception is SD1b.

`pipeline/extract_report_cells.py` regenerates everything above from `raw/` and checks each file's sha256 against
the manifest first. It does no mapping: which indicator, place and breakdown a cell means is declared table by
table in `core/pipeline/report_tables.py` (decision D35).

## What is in core (D35)

The report adds breakdowns the open data lack. Report figures that the open data already hold, figure for
figure, are not loaded a second time. Report figures in core: 1,059.
* `poverty.absolute.rate`, `poverty.hardcore.rate`: by state and strata (2022, 2024); by the household head's
  ethnicity and strata, and ethnicity and sex; by the head's age; by household size.
* `poverty.pli.mean` (new): the average poverty line income, by state, state and strata, the head's ethnicity
  and strata, and food / non-food (`pli_component`).
* `hh_income.disposable.*`, `hh_income.gross_per_capita.*`, `hh_income.disposable_per_capita.*` (new), and
  `hh_income.gross.*` breakdowns, all as median and mean:
  * by state;
  * by state and the head's sex;
  * by the head's ethnicity, strata and sex;
  * by the head's age.
* `lfs.participation_rate`: by age, strata and sex (2025).

A household head's attributes are their own axes, `hh_head_ethnicity`, `hh_head_sex` and `hh_head_age`, not the person axes.
`hh_size` is the household's size. Growth rates stay at L1, because they are derivable (D34). Household counts
stay at L1 too: core takes those from `hh_profile_state`.

The rest of the tables are held at L1 only, so far:
* income by source, by income class and by percentile;
* Gini, Theil and Atkinson by income type, and the district Gini tables;
* the long series from 1970;
* the expenditure tables;
* LFS A1.2-A1.12;
* the wage tables, which equal the open data already loaded.

## Caveats

* **Terengganu, absolute poverty 2024 (SD1, SD1b).** The poverty report prints two figures for one key:
  * **4.8%** in Jadual 3.1 (cell E17) and Jadual 5.3 (U24); the PDF prints it on pp. 20, 40 (Table 5 and Chart 2),
    62 and 67;
  * **5.8%** in Jadual 5.4, the district table (cell I100; PDF p. 72). The open-data file `hh_poverty_state` also
    prints 5.8.

  The report's own strata (urban 3.3, rural 7.3), weighted by Terengganu's 2024 households (64.0% urban), give 4.7
  to 4.8. The open data probably follow the district table. Core holds the chapter figure (4.8) and the open data's
  (5.8), each under its own edition, and no reader chooses between them. Which is right is for DOSM to say. The
  verifier found the 5.8 inside the report; the first write-up said only that the report and the open data
  differ.
* The poverty workbook stores hardcore incidence to more digits than it prints (0.03, printed 0.0). Core loads
  the printed figure, and cells.csv keeps the stored number. Where the open data carry the stored number
  (hardcore poverty by state, 0.08), core keeps the open data's figure and does not load the report's.
* The Salaries & Wages state tables cover citizens only (their note 1), as the open-data `wages_state` does.
* No sampling error is printed in these tables, except the Salaries & Wages E1-E3 RSE tables, which are held
  at L1. Core marks every report figure `reliability=unknown` (golden rule 9).
