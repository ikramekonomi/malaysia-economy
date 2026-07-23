# CLAUDE.md — Malaysia Public Finance Data Warehouse

Operating manual for anyone (human or AI) working in this repo. Read this first.

## Mission
Build a consolidated, fully-verifiable data warehouse of **Malaysia's public finances** —
to understand, track, analyse, and **find gaps in the country's fiscal behaviour**.
Multiple official sources are ingested (each with complete provenance), then curated and
consolidated into a comparable layer so the same concept can be traced and cross-checked
across sources.

## Sources (growing)
- **PKKP** — the audited *Penyata Kewangan Kerajaan Persekutuan* (Federal Government
  Financial Statements), **FY2009–FY2024**, extracted to full detail (~580k data points;
  76,320 object-level opex rows). This is the first and foundational source: audited
  **actuals** down to object-level grain. Currently the whole repo; see layout below.
- **Planned** — budget estimates (*Anggaran Perbelanjaan Persekutuan*), MOF *Fiscal
  Outlook / Laporan Ekonomi*, and other official series. Each new source gets its own
  namespace and its own provenance; nothing is blended without an audit trail.

## Golden rules — do not break these
1. **Raw source data (the CSVs) is the source of truth.** Any consolidated/curated table
   is derived and rebuildable; never hand-edit a build artifact (e.g. `pkkp.duckdb` —
   rebuild with `python3 pipeline/build_duckdb.py`).
2. **Never silently correct a figure.** If a source misprints something, keep it as
   printed and document it in that source's validation CSV with a proof. Fixing an
   extraction bug is fine; altering what the source published is not.
3. **Every row keeps its source + provenance** (`source_file`, `pdf_page`,
   `printed_page`, `statement`). Traceability is the whole point — it's what lets us
   compare sources and defend a public dataset.
4. **Join on codes, never names** (`maksud_code`, `projek_code`) — renames and preserved
   government typos exist.
5. **Sum only leaf rows** — `row_type` in `object_aktiviti` / `project` / `detail`.
   Subtotal rows are kept deliberately; summing them double-counts.
6. **Take each year from its own volume/source** for clean series (governments restate;
   restatements are catalogued in the per-year `_restatements_*.csv`).
7. **Work on a branch and open a PR** — never push data changes straight to `main`.
   Review before merge is what keeps a public fiscal dataset trustworthy.

## Adding a new source (the architecture direction)
As sources beyond PKKP arrive, keep them **namespaced and independently verifiable**,
then consolidate on top — do not merge raw numbers from different sources into one table
without a mapping and an audit trail:
- Each source gets its own folder + extraction pipeline + provenance (PKKP currently
  lives at `warehouse/`; expect a move to a `sources/<name>/` layout as the second source
  lands, with a `curated/` layer above).
- A **curated/consolidated layer** conforms shared dimensions — fiscal year, ministry
  (`maksud`), economic classification (object class) — so sources join cleanly.
- **Gap-finding is a first-class use case:** compare the same concept across sources
  (e.g. budgeted vs actual vs reported) and surface divergences, using the same
  discipline as the cross-volume restatement audits already in this repo.

## Layout (current — PKKP)
- `warehouse/` — the data. FY2024 CSVs at the root; `2009/`..`2023/` per-year subfolders.
  Docs: `README_QUICKSTART.md`, `DATA_DICTIONARY.md`, `VALIDATION_REPORT.md`.
- `pipeline/build_duckdb.py` — rebuilds the query DB from the CSVs.
- `pipeline/<year>/` — that volume's extraction scripts.

## Setup (fresh clone / cloud session)
```
pip install -r requirements.txt
python3 pipeline/build_duckdb.py      # -> warehouse/pkkp.duckdb
```
Querying needs only `duckdb`. **Extraction also needs system tools** `poppler-utils`
(pdftotext/pdftoppm) and `tesseract-ocr` — install via apt in a cloud setup script when
re-running a pipeline.

## Extraction conventions
Amounts exact RM as printed (sen kept). En-dash `–` = 0.0 (nil). Parentheses = negative.
Asterisk on a value → `has_footnote=True`. Malay labels canonical (`*_bm`); English
glosses only in `dim_maksud.name_en`.

## Verification rule (mandatory for any new/changed source)
Reconcile to the source's own printed totals, THEN run an **independent adversarial
verifier pass** (a separate agent, blind to the extraction code, re-derives from the
original and compares). Report discrepancies; never correct silently. This is how all 16
PKKP volumes were validated.

## Known caveats (PKKP)
- **FY2015** is an image-only scan: statements/registers/panel/ministry totals are fully
  verified, but object-leaf & project-leaf amounts are OCR-provisional (unresolved cells
  in `warehouse/2015/_unresolved_ocr_cells_2015.csv`). Use `fact_opex_maksud` /
  `fact_devex_maksud` for 2015 ministry-level work.
- **FY2009** is the archaic cash-basis presentation (no aktiviti tier, narrative-only
  notes, no performance/commitment statements — genuine source absences).
- See `DATA_DICTIONARY.md` for all per-era format differences.

## Good next tasks
- Ingest the second source (budget estimates / *Anggaran*) into its own namespace, then
  build the first budget-vs-actual gap view against PKKP.
- Add FY2008 PKKP following the `pipeline/2009/` pattern (branch → verify → PR).
- Tighten 2015 object-leaf OCR using each maksud's Nota 5(b) total as the oracle.
