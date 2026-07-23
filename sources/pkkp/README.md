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

Build the query DB: `python3 ../../pipeline/build_duckdb.py` → `pkkp.duckdb` (rebuildable cache).

Caveat: FY2015 is an image-only scan — its object-leaf/project-leaf amounts are
OCR-provisional (see `VALIDATION_REPORT.md`); statement/register/ministry-level tables are
fully verified.
