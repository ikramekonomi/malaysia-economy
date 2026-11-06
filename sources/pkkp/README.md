# Source: PKKP — Federal Government Financial Statements (FY2009–FY2024)

The audited *Penyata Kewangan Kerajaan Persekutuan* (JANM), all 16 volumes, extracted to
full detail — the warehouse's foundational source of **audited federal actuals** down to
object-level grain (~580k data points; 76,320 opex leaf rows). Every figure carries source
PDF + page provenance.

- `data/<year>/` — one folder per audited volume (its own year + prior-year comparatives).
  The CSVs are canonical.
- `pipeline/<year>/` — that volume's extraction scripts (reproducible).
- `DATA_DICTIONARY.md` — every table & column.
- `VALIDATION_REPORT.md` — how each volume was verified (independent adversarial passes).
- `README_QUICKSTART.md` — start here to query.

Build the query DB: `python3 pipeline/build_duckdb.py` (from this folder; or `python3 sources/pkkp/pipeline/build_duckdb.py` from the repo root) → `pkkp.duckdb` (rebuildable cache).

Caveat: FY2015 is an image-only scan — its object-leaf/project-leaf amounts are
OCR-provisional (see `VALIDATION_REPORT.md`); statement/register/ministry-level tables are
fully verified.

Archive (`meta/l0_archive.csv`, decision D24): 14 of the 16 volumes are in the private `l0-archive`
release, identified by their cited amounts on their cited pages. Not archived: **FY2020** (ANM's link
returns 404 and no other official copy has been found; its figures are kept, marked "PDF not archived",
caveat CV17) and **FY2015** (the image-only scan did not pass the identity check: 151 of 400 cited amounts
found by OCR).

**The per-year extraction scripts** (`pipeline/<year>/`) are a frozen record of how each volume was read. They
hard-code the original work paths (`/home/claude/pkkp/...`) and need the PDFs from the L0 archive, so they are kept as
provenance, not run. CI runs the validators that work on the committed CSVs (`qa/run_offline_suite.py`).
