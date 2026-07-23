# CLAUDE.md — PKKP Data Warehouse

Operating manual for anyone (human or AI) working in this repo. Read this first.

## What this is
Malaysia's audited Federal Government Financial Statements (*Penyata Kewangan
Kerajaan Persekutuan*), all 16 volumes **FY2009–FY2024**, extracted to full detail
(~580k data points; 76,320 object-level operating-expenditure rows). Every figure
traces to a source PDF + page.

## Golden rules — do not break these
1. **The CSVs are the source of truth.** `warehouse/pkkp.duckdb` is a rebuildable
   cache — never hand-edit it. Rebuild: `python3 pipeline/build_duckdb.py`.
2. **Never silently correct a figure.** If the source misprints something, keep it
   as printed and document it in that year's `_validation_checks_*.csv` with a proof.
   Fixing extraction bugs is fine; altering what the government printed is not.
3. **Join on codes, never names** (`maksud_code`, `projek_code`) — there are renames
   and preserved government typos.
4. **Sum only leaf rows** — `row_type` in `object_aktiviti` (opex) / `project` (devex)
   / `detail`. Subtotal rows are kept on purpose; summing them double-counts.
5. **Take each year from its own volume** for clean time series (governments restate
   prior years; restatements are catalogued in the per-year `_restatements_*.csv`).
6. **Work on a branch and open a PR** — never push data changes straight to `main`.
   Data-engineering PRs get reviewed before merge; that review is what keeps a public
   fiscal dataset trustworthy.

## Layout
- `warehouse/` — the data. FY2024 CSVs at the root; `2009/`..`2023/` per-year subfolders.
  Docs: `README_QUICKSTART.md`, `DATA_DICTIONARY.md`, `VALIDATION_REPORT.md`.
- `pipeline/build_duckdb.py` — rebuilds the DuckDB from the CSVs.
- `pipeline/<year>/` — that volume's extraction scripts.

## Setup (fresh clone / cloud session)
```
pip install -r requirements.txt
python3 pipeline/build_duckdb.py      # -> warehouse/pkkp.duckdb
```
Querying needs only `duckdb`. **Extraction (adding older years) also needs system
tools** `poppler-utils` (pdftotext/pdftoppm) and `tesseract-ocr` — install via apt in
a cloud setup script if you're re-running a pipeline.

## Extraction conventions
Amounts are exact RM as printed (sen kept). En-dash `–` = 0.0 (nil). Parentheses =
negative. Asterisk on a value → `has_footnote=True`. Every row carries `source_file`,
`pdf_page`, `printed_page`, `statement`. Malay labels are canonical (`*_bm`); English
glosses only in `dim_maksud.name_en`.

## Verification rule (mandatory for any new/changed volume)
Reconcile to the volume's own printed totals (revenue chains; Lampiran-1 additivity at
every level; devex identities; registers; panel cross-footing; Nota roll-forwards),
THEN run an **independent adversarial verifier pass** (a separate agent, blind to the
extraction code, re-derives from the PDF and compares). Report discrepancies; never
correct silently. This is how all 16 volumes were validated.

## Known caveats
- **FY2015** is an image-only scan: statements/registers/panel/ministry totals are
  fully verified, but object-leaf & project-leaf *amounts* are OCR-provisional and not
  reconciled to printed subtotals. Unresolved cells listed in
  `warehouse/2015/_unresolved_ocr_cells_2015.csv`. Use `fact_opex_maksud` /
  `fact_devex_maksud` for 2015 ministry-level work.
- **FY2009** is the archaic cash-basis presentation (statements A–G/C1/C2/E1ai, no
  aktiviti tier, narrative-only notes, no performance/commitment statements — genuine
  source absences, not gaps).
- 2016–2020 volumes print 4 opex value columns (Asal/Dipinda/Amaun/%); 2009–2012 have
  no per-issue debt register. See `DATA_DICTIONARY.md` for all per-era differences.

## Good first tasks
- Add FY2008 following the `pipeline/2009/` pattern (branch → verify → PR).
- Tighten 2015 object-leaf OCR using each maksud's Nota 5(b) total as the oracle.
- Build analysis views / charts for Agenda Ekonomi (query DuckDB; don't mutate CSVs).
