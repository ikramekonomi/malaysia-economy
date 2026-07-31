# Task briefing: 2025–26 pilot ingestion (network egress now open)

**Context.** This branch (`claude/anggaran-budget-source-f55o9x`, PR #1) carries the curated
budget-vs-actual gap view, the dashboard (`curated/dashboard/`), and the forecast pilot
(`curated/forecast/`). The environment's network policy now allows `*.mof.gov.my`,
`*.treasury.gov.my`, `data.gov.my`/`*.data.gov.my`, and `dosm.gov.my`/`*.dosm.gov.my`.
Everything below follows `CLAUDE.md` — read it first. Golden rules apply throughout:
figures only from documents/datasets in hand (never memory), exact as printed, full
provenance, reconcile to printed totals, then an independent adversarial verifier pass.
Delete this file in the final commit when the tasks are done.

## 0. Setup
- `git fetch origin claude/anggaran-budget-source-f55o9x && git checkout claude/anggaran-budget-source-f55o9x`
- `pip install -r requirements.txt && python3 pipeline/build_duckdb.py`
- Verify egress: `curl -sS -o /dev/null -w "%{http_code}\n"` against
  `https://belanjawan.mof.gov.my`, `https://data.gov.my`, `https://open.dosm.gov.my`,
  `https://storage.data.gov.my`. Report which are reachable before proceeding.

## 1. DOSM denominators (smallest, do first)
Replace the provisional GDP/population numbers with a real ingested source:
- Fetch annual **nominal GDP** and **population** (data.gov.my / OpenDOSM parquet or CSV,
  e.g. the GDP annual and population datasets; household counts if available).
- Create `sources/dosm/` (data + tiny pipeline + README) with provenance = dataset URL +
  retrieval date + data vintage. CSVs canonical.
- Update `curated/dashboard/build_dashboard.py` to read from `sources/dosm/` and
  regenerate `curated/dashboard/external_denominators.csv`; drop the PROVISIONAL flag in
  the dashboard footer copy only after values are verified against the published series.

## 2. MOF Fiscal Outlook headline (the official 2025–26 numbers)
- Download the **Fiscal Outlook / Laporan Ekonomi & Fiskal** PDFs: Budget 2025 edition and
  Budget 2026 edition, from belanjawan.mof.gov.my (store under
  `sources/mof-fiscal-outlook/raw/` — gitignored; commit only extracted CSVs).
- Fill `sources/mof-fiscal-outlook/data/fiscal_outlook_headline.csv` per the entry contract
  in that folder's README (every row: source_file, pdf_page, printed_page, retrieved_from,
  retrieved_date; basis=official_projection).
- Reconcile to the document's own printed totals; then run an **independent adversarial
  verifier** (separate agent, blind to the extraction) exactly as PKKP was verified.
  Report discrepancies; never correct silently.
- Cross-check: do the official 2025–26 figures sit inside the model bands in
  `curated/forecast/fact_projection_headline.csv`? Note the comparison in the PR.

## 3. Anggaran Perbelanjaan 2025 (source #2 proper — pilot one year)
- Download the Budget 2025 **Anggaran Perbelanjaan Persekutuan** expenditure book(s).
- Extract to `sources/anggaran/data/2025/` at maksud grain first (program/objek grain as a
  follow-up), per `sources/anggaran/README.md`: exact amounts, en-dash = 0, parentheses =
  negative, Malay labels canonical, join on codes with an explicit documented crosswalk to
  PKKP `dim_maksud` (never guessed), `measure=budget`.
- Validate against the book's own per-maksud and grand totals + adversarial verifier.
- Then combine with `curated/forecast/fact_utilisation_signatures.csv` to produce
  expected-actual nowcasts for FY2025 (basis=model_projection, method documented).

## 4. Dashboard: the 2025–26 outlook (only after 1–3 are verified)
- Extend `curated/dashboard/` with a clearly-styled outlook segment: solid = audited
  (≤2024), distinct dashed/hatched = `budgeted` / `official_projection`, cone =
  `model_projection`, each labelled unaudited. Never blend bases.
- Rebuild (`python3 curated/dashboard/build_dashboard.py`), then verify in headless
  Chromium: light + dark + mobile + ultrawide, zero JS errors, and the NaN-geometry sweep
  over every chart (pattern in the session history / reproduce: assert every rect, circle,
  line, path and text geometry attribute is finite).
- Update the existing artifact IN PLACE by passing
  `url: https://claude.ai/code/artifact/582fcee9-1ae6-4fd3-893c-455c30d26979` to the
  Artifact tool (otherwise a new URL is minted).

## 5. Housekeeping
- Commit incrementally with clear messages; push to **this same branch** (feeds PR #1).
  Do not push to main. Update the PR description with what landed and validation results.
- Add `sources/*/raw/` to `.gitignore` if not already present.
- Report back: what was downloaded (URLs), extraction coverage, validation PASS/FAIL with
  diagnoses, the official-vs-model comparison, and dashboard changes.
