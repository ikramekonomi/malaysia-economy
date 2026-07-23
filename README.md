# Malaysia Public Finance Data Warehouse

A consolidated, fully-verifiable data warehouse of **Malaysia's public finances** — built to
understand, track, analyse, and **find gaps in the country's fiscal behaviour**. Multiple
official sources are ingested with complete provenance, then curated into a comparable layer
so the same concept can be traced and cross-checked across sources.

## Sources

**PKKP — Federal Government Financial Statements (FY2009–FY2024)** — the first and
foundational source: the audited *Penyata Kewangan Kerajaan Persekutuan*, extracted to full
detail (~580,000 numeric data points; 76,320 object-level operating-expenditure rows). Audited
**actuals**, down to per-ministry object-level grain, every figure traceable to its source PDF
and page. More sources (budget estimates, MOF fiscal reports, …) will be added in their own
namespaces alongside this one.

## Layout (current)

```
warehouse/            <- PKKP data (CSVs are the source of truth)
  *.csv               <- FY2024 volume's tables (root)
  2009/ .. 2023/      <- each older volume's tables (identical schemas)
  DATA_DICTIONARY.md      <- every table & column
  VALIDATION_REPORT.md    <- how each volume was verified
  README_QUICKSTART.md    <- start here to query
pipeline/             <- extraction & build code (reproducible)
  build_duckdb.py     <- regenerates warehouse/pkkp.duckdb from the CSVs
  2009/ .. 2024/      <- per-volume extraction scripts
CLAUDE.md             <- operating manual & mission (read this first)
SOURCES.md
```
As the second source lands, expect a move to a `sources/<name>/` layout with a `curated/`
consolidation layer above. See `CLAUDE.md` for the architecture direction.

## Quick start

```bash
pip install -r requirements.txt
python3 pipeline/build_duckdb.py        # builds warehouse/pkkp.duckdb from the CSVs
duckdb warehouse/pkkp.duckdb
```
Then read `warehouse/README_QUICKSTART.md`. Core rules: the CSVs are canonical (the .duckdb is
a rebuildable cache); **join on codes, not names**; **sum only leaf rows** (`row_type` in
`object_aktiviti`/`project`/`detail`) or you'll double count; take each year from its own
volume for clean series (see the `_restatements_*.csv` catalogues); **never silently correct a
published figure**.

## Known caveat

FY2015 is the one image-only scan. Its statements, registers, panel and ministry-level totals
are fully verified; its object-leaf / project-leaf amounts are OCR-provisional and not
reconciled to printed subtotals (unresolved cells inventoried in
`warehouse/2015/_unresolved_ocr_cells_2015.csv`). See `VALIDATION_REPORT.md`.
