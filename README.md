# PKKP Data Warehouse — Malaysia Federal Government Financial Statements (FY2009–FY2024)

Malaysia's audited Federal Government Financial Statements (*Penyata Kewangan Kerajaan
Persekutuan*), all 16 volumes FY2009–FY2024, extracted to full detail — ~580,000 numeric
data points, down to object-level operating expenditure per ministry. Every figure carries
provenance (source PDF + page) and reconciles to the printed totals.

## Layout

```
warehouse/            <- the data (CSVs are the source of truth)
  *.csv               <- FY2024 volume's tables (root)
  2009/ .. 2023/      <- each older volume's tables (identical schemas)
  DATA_DICTIONARY.md      <- every table & column
  VALIDATION_REPORT.md    <- how each volume was verified
  README_QUICKSTART.md    <- start here to query
pipeline/             <- the extraction & build code (reproducible)
  build_duckdb.py     <- regenerates warehouse/pkkp.duckdb from the CSVs
  2009/ .. 2024/      <- per-volume extraction scripts
SOURCES.md
```

## Quick start

```bash
pip install duckdb
python3 pipeline/build_duckdb.py        # builds warehouse/pkkp.duckdb from the CSVs
duckdb warehouse/pkkp.duckdb
```
Then read `warehouse/README_QUICKSTART.md`. In short: the CSVs are canonical (the .duckdb is
a rebuildable cache); **join on codes, not names** (renames + preserved govt typos);
**sum only leaf rows** (`row_type` in `object_aktiviti`/`project`/`detail`) or you'll double
count; take each year from its own volume for clean series (governments restate — see the
`_restatements_*.csv` catalogues).

## Known caveat

FY2015 is the one image-only scan. Its statements, registers, panel and ministry-level
totals are fully verified; its object-leaf / project-leaf amounts are OCR-provisional and
not reconciled to printed subtotals (every unresolved cell is inventoried in
`warehouse/2015/_unresolved_ocr_cells_2015.csv`). See `VALIDATION_REPORT.md`.
