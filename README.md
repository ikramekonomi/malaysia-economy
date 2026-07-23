# Malaysia Public Finance Data Warehouse

A consolidated, fully-verifiable data warehouse of **Malaysia's public finances** — federal
**and** state — built to understand, track, analyse, and **find gaps in the country's fiscal
behaviour**. Multiple official sources are ingested with complete provenance, then curated
into a comparable layer so the same concept can be traced and cross-checked across sources.

Start with **`CLAUDE.md`** (mission + rules) and **`docs/SOURCES.md`** (what to add next and
why).

## Layout
```
sources/            one folder per source (each independently verifiable)
  pkkp/             Federal Government Financial Statements FY2009–2024 (audited actuals)
    data/<year>/        the CSVs (source of truth), one folder per volume
    pipeline/<year>/    extraction scripts
    DATA_DICTIONARY.md · VALIDATION_REPORT.md · README_QUICKSTART.md
curated/            consolidated layer (conformed dims + gap views) — built as sources land
pipeline/build_duckdb.py   rebuilds sources/pkkp/pkkp.duckdb from the CSVs
docs/SOURCES.md     source catalogue: federal, state, statistics — priority + gap pairings
```

## Sources
**pkkp** is the first and foundational source: the audited *Penyata Kewangan Kerajaan
Persekutuan*, FY2009–2024, extracted to full detail (~580,000 data points; 76,320
object-level opex rows), every figure traceable to its source PDF and page. Planned additions
(budget estimates, MOF fiscal reports, DOSM, state statements, …) are catalogued in
`docs/SOURCES.md`.

## Quick start
```bash
pip install -r requirements.txt
python3 pipeline/build_duckdb.py          # builds sources/pkkp/pkkp.duckdb from the CSVs
duckdb sources/pkkp/pkkp.duckdb
```
Then read `sources/pkkp/README_QUICKSTART.md`. Core rules: CSVs are canonical (the .duckdb is
a rebuildable cache); **join on codes, not names**; **sum only leaf rows**; take each year
from its own volume; **never silently correct a published figure**.

## Known caveat
FY2015 is the one image-only scan — its object-leaf/project-leaf amounts are OCR-provisional
(fully-verified everywhere else). See `sources/pkkp/VALIDATION_REPORT.md`.
