# CLAUDE.md — Malaysia Public Finance Data Warehouse

Operating manual for anyone (human or AI) working in this repo. Read this first.

## Mission
Build a consolidated, fully-verifiable data warehouse of **Malaysia's public finances** —
federal **and** state — to understand, track, analyse, and **find gaps in the country's
fiscal behaviour**. Multiple official sources are ingested (each with complete provenance),
then curated into a comparable layer so the same concept can be traced and cross-checked
across sources.

## Architecture: hub-per-domain, truth-by-reconciliation
No single source is "the truth" for the whole warehouse. Each **domain** has a hub —
the record others in that domain reconcile against when they disagree — and the
warehouse's real product is the **reconciliation layer**: where independent
institutions agree to the ringgit, and where they diverge, by how much, kept as
published.

| Domain | Hub (anchor of last resort) | Reconciled against it |
|---|---|---|
| Federal fiscal | **PKKP** (audited actuals) | budgets, BNM fiscal series, AG tables, MOF outlook |
| Agencies & GLCs | AG certifications + company accounts | e-SelfAudit censuses, findings |
| States | each state's audited statements | state budgets, state LKAN |
| Real economy | DOSM national accounts | GFS, CPI, state GDP |
| Monetary/financial | BNM | debt issuance, holdings |

Domains join only through conformed dimensions (year, jurisdiction, entity, economic
classification) in `curated/`. PKKP is the *federal fiscal* hub — never the warehouse's
identity. Three known blind spots of a PKKP-centric view, tracked as first-class work:
**(1) scope** — statutory bodies, GLCs and off-budget vehicles sit outside the
consolidated fund (guarantees/contingent-liability registers + agency accounts cover
this); **(2) accounting basis** — PKKP is modified-cash, so commitments, PFI
liabilities, guarantees and revenue arrears live in memorandum accounts and AG
analyses, not expenditure lines (the obligations layer covers this); **(3) domain** —
the economy's backbone is DOSM/BNM, not any fiscal document.

## Sources
- **pkkp** (in repo) — audited *Penyata Kewangan Kerajaan Persekutuan* (Federal Government
  Financial Statements), FY2009–FY2024, to object-level grain. The foundational source:
  audited **federal actuals**.
- **Planned** — federal budget estimates (*Anggaran Perbelanjaan / Hasil*), MOF *Fiscal
  Outlook*, DOSM statistics, data.gov.my/OpenDOSM, Auditor-General reports, **state financial
  statements & budgets**, and more. Full catalogue with priorities and gap-analysis pairings:
  **`docs/SOURCES.md`**.

## Golden rules — do not break these
1. **Raw source data (the CSVs) is the source of truth.** Consolidated/curated tables and any
   `*.duckdb` are derived, rebuildable artifacts — never hand-edit them
   (`python3 pipeline/build_duckdb.py` rebuilds the PKKP DB).
2. **Never silently correct a figure.** If a source misprints something, keep it as printed
   and document it in that source's validation CSV with a proof. Fixing an extraction bug is
   fine; altering what a source published is not.
3. **Every row keeps its source + provenance** (`source_file`, `pdf_page`, `printed_page`,
   `statement`). Traceability is the whole point — it's what lets us compare sources and
   defend a public dataset.
4. **Join on codes, never names** (`maksud_code`, `projek_code`).
5. **Sum only leaf rows** — `row_type` in `object_aktiviti` / `project` / `detail`.
6. **Take each year from its own volume/source** for clean series (restatements catalogued in
   the per-year `_restatements_*.csv`).
7. **Work on a branch and open a PR** — never push data changes straight to `main`.

## Layout
```
sources/            one folder per source, each independently verifiable
  pkkp/
    data/<year>/    the CSVs (canonical) — one folder per audited volume
    pipeline/<year>/  extraction scripts for that volume
    DATA_DICTIONARY.md  VALIDATION_REPORT.md  README_QUICKSTART.md
curated/            consolidated layer (conformed dims + gap views) — built as sources land
pipeline/
  build_duckdb.py   rebuilds sources/pkkp/pkkp.duckdb from the CSVs
docs/
  SOURCES.md        the source catalogue: what to add, priority, gap-analysis pairings
CLAUDE.md  README.md  requirements.txt
```

## Adding a new source
Keep each source **namespaced and independently verified**, then consolidate on top — never
merge raw numbers from different sources without a mapping and an audit trail. New source →
its own `sources/<name>/` (data + pipeline + provenance + validation). Conform shared
dimensions (fiscal year, ministry/`maksud`, object class, **state/jurisdiction**) in
`curated/`. **Gap-finding is a first-class use case:** compare the same concept across sources
(budgeted vs actual, estimate vs collected, federal vs state, audited vs reported) and surface
divergences — see `docs/SOURCES.md`.

## Setup (fresh clone / cloud session)
```
pip install -r requirements.txt
python3 pipeline/build_duckdb.py       # -> sources/pkkp/pkkp.duckdb
duckdb sources/pkkp/pkkp.duckdb
```
Querying needs only `duckdb`. **Extraction also needs system tools** `poppler-utils` and
`tesseract-ocr` — install via apt in a cloud setup script when re-running a pipeline.

## Extraction conventions
Amounts exact RM as printed (sen kept). En-dash `–` = 0.0 (nil). Parentheses = negative.
Asterisk on a value → `has_footnote=True`. Malay labels canonical (`*_bm`).

## Verification rule (mandatory for any new/changed source)
Reconcile to the source's own printed totals, THEN run an **independent adversarial verifier
pass** (a separate agent, blind to the extraction code, re-derives from the original and
compares). Report discrepancies; never correct silently.

## Known caveats (PKKP)
- **FY2015** is an image-only scan: statements/registers/panel/ministry totals fully verified,
  but object-leaf & project-leaf amounts are OCR-provisional (unresolved cells in
  `sources/pkkp/data/2015/_unresolved_ocr_cells_2015.csv`). Use `fact_opex_maksud` /
  `fact_devex_maksud` for 2015 ministry-level work.
- **FY2009** is the archaic cash-basis presentation (no aktiviti tier, narrative-only notes,
  no performance/commitment statements — genuine source absences).
- See `sources/pkkp/DATA_DICTIONARY.md` for all per-era format differences.

## Good next tasks
- Ingest source #2 — federal budget estimates (*Anggaran Perbelanjaan*) into `sources/anggaran/`,
  then build the first **budget-vs-actual** gap view in `curated/`.
- Begin **state** coverage — one state's financial statements into `sources/state-<name>/`.
- Add FY2008 PKKP following the `sources/pkkp/pipeline/2009/` pattern (branch → verify → PR).
