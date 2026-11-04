# CLAUDE.md — Malaysia Economy Data Warehouse

Operating manual for anyone (human or AI) working in this repo. Read this first.
(The GitHub repo is `ammarroslizar/malaysia-economy`; the old name `malaysiafinance` redirects.)

## Mission
Build a consolidated, fully verifiable data warehouse of **the Malaysian economy**, national and
state (down to district, parlimen and DUN where the data exists). Its first user is **IKRAM**,
an NGO, looking for gaps worth advocating on: plan vs outcome, budget vs spending, need vs money,
federal vs state, reported vs audited. It is queried by people and by AI agents; the dashboard
(`site/`) is one application on top of it, not the warehouse itself.

Every number must survive a hostile reader: traceable to its page, checked, carrying its
uncertainty and its caveats.

## The design, in one paragraph
Nine themes: people & poverty · jobs & wages · prices & cost of living · output & industry ·
public money & money trail · health, education & services · accountability · money, credit &
financial wellbeing · environment, climate & disasters. Raw files (L0) → source tables as printed
(L1, `sources/`) → a conformed core of 6 dimensions (geo, period, indicator, breakdown, entity,
source) and 3 facts (observation, money flow, record) (L2) → named gap views (L3) → apps (L4:
agent tools, dashboard, models). **The full specification is `docs/DATA_MODEL.md`**: read it
before changing anything structural. Decisions D1–D23 are its §16 (and `meta/decision.csv`).

## Truth by reconciliation
No single source is "the truth". Each domain has a hub that others reconcile against, and the
real product is the **reconciliation layer**: where independent institutions agree to the
ringgit, and where they diverge, by how much, kept as published.

| Domain | Hub (anchor of last resort) | Reconciled against it |
|---|---|---|
| Real economy, people, prices | DOSM (national accounts, HIES, LFS, CPI) | BNM, secondary research sources, IMF |
| Federal public money | **PKKP** (audited actuals) | budgets, BNM fiscal series, AG tables, MOF outlook, DOSM GFS |
| States | each state's audited statements | state budgets, state LKAN, DOSM state finance |
| Agencies & GLCs | AG certifications + company accounts | e-SelfAudit censuses, findings |
| Monetary/financial | BNM | debt issuance, holdings |

Known blind spots of any single-hub view, tracked as first-class work: **scope** (statutory
bodies, GLCs and off-budget vehicles), **accounting basis** (modified cash; commitments, PFI and
guarantees sit in memorandum accounts), and **place** (most federal spending has no location
in the accounts; see `docs/DATA_MODEL.md` §10 and §13).

## Sources
What we hold and what we need is one checklist: **`docs/registry/series_seed.csv`** (104 series:
status, route, access, licence, priority). The plan behind it, theme by theme:
**`docs/SOURCES.md`**. How the registry works: `docs/DOCUMENT_REGISTRY.md`. Held today (each in
`sources/<name>/`): pkkp (FY2009–2024), anggaran, anggaran-hasil, mof-fiscal-outlook (9
editions), bnm, dosm (112 datasets, refreshed daily), audit-negara, states (13 states).

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
4. **Join on codes, never names** (`maksud_code`, `projek_code`; ISO/DOSM geo codes).
5. **Sum only leaf rows** — `row_type` in `object_aktiviti` / `project` / `detail`.
6. **Take each year from its own volume/source** for clean series (restatements catalogued in
   the per-year `_restatements_*.csv`).
7. **Work on a branch and open a PR** — never push data changes straight to `main`. (The daily
   DOSM refresh also goes through a PR; it merges itself only when every verifier is clean.)
8. **Keep every vintage.** A refresh never destroys the previous release: log it (sha256, as-of
   date) so it can be recovered exactly (`sources/dosm/pipeline/vintage_get.py`). Raw PDFs live in
   the private `l0-archive` release, by sha256 (`meta/l0_archive.py`; index `meta/l0_archive.csv`).
9. **A survey estimate carries its uncertainty**, or says it is unknown. Never rank small areas
   as if their estimates were exact.
10. **Licence and personal data are checked before anything leaves the warehouse.** Every series
    has `licence`, `redistribution` and `contains_personal_data` in the registry; never guess a
    licence. `to_confirm` does not block publishing official figures with their citation;
    `no_redistribution` never leaves the warehouse; a publisher's takedown request is honoured. Individuals are never returned by tools or views. Only lawfully published or
    officially requested documents; no leaked or OSA-classified material.
11. **Neutral by construction.** Methods are declared before results are seen; every view runs
    for all 13 states and the Federal Territories; no party attribute in the core; disclose any
    conflict of interest as a caveat.

## Layout
```
sources/            one folder per source, each independently verifiable (L1)
  <name>/data/      the CSVs (canonical, as printed)  + _validation*, _source_anomalies*, _vintage_log
  <name>/pipeline/  extraction, refresh and verification scripts
core/               the conformed layer (L2: dims + fact_observation) and gap views (L3); see core/README.md
curated/            the older consolidated layer, moving into core/ view by view
apps/tools/         typed agent tools over core/ (no SQL; every number cited; arithmetic only via derive)
apps/models/        model projections: an application, never warehouse data
site/               the public site + chatbot (reads curated views; its own CLAUDE.md)
pipeline/           build_duckdb.py (PKKP DB)
docs/               DATA_MODEL.md · SOURCES.md · DOCUMENT_REGISTRY.md · registry/ · ANALYST_GUIDE.md
meta/               code lists, decisions, the file registry (build_registry.py) -> warehouse meta.*
qa/                 the offline check suite CI runs on every PR, and its known-FAIL baseline
```

**CI:** `python3 qa/run_offline_suite.py` runs on every PR (`.github/workflows/validate.yml`). It
blocks a script that fails, a rebuild that changes a committed file, and any `FAIL` row not in
`qa/known_fails.csv`. Run it before you push. If you add a validator that runs offline, add it to
the suite's `SUITE` list.

## Adding a new source
Register it first (a row in `docs/registry/series_seed.csv`, with licence and personal-data
fields). Keep each source **namespaced and independently verified** in its own
`sources/<name>/` (data + pipeline + provenance + validation), then conform it to the shared
dimensions. Never merge raw numbers from different sources without a mapping and an audit trail.
**Gap-finding is a first-class use case:** compare the same concept across sources and surface
divergences.

## Setup (fresh clone / cloud session)
```
pip install -r requirements.txt
python3 pipeline/build_duckdb.py                  # -> sources/pkkp/pkkp.duckdb
python3 curated/pipeline/build_warehouse_duckdb.py  # -> curated/warehouse.duckdb (all sources)
```
Querying needs only `duckdb`. Refresh/verification needs `pyarrow` and `pandas` (in
requirements). **Extraction also needs system tools** `poppler-utils` and `tesseract-ocr`.

## Extraction conventions
Amounts exact RM as printed (sen kept). En-dash `–` = 0.0 (nil). Parentheses = negative.
Asterisk on a value → `has_footnote=True`. Malay labels canonical (`*_bm`).

## Verification rule (mandatory for any new/changed source)
Reconcile to the source's own printed totals, THEN run an **independent adversarial verifier
pass** (a separate agent, blind to the extraction code, re-derives from the original and
compares). Anything IKRAM publishes also needs a **human spot-check** of a sample against the
original (`docs/DATA_MODEL.md` §7.4). Report discrepancies; never correct silently.

## Known caveats
- **PKKP FY2015** is an image-only scan: object-leaf & project-leaf amounts are OCR-provisional
  (`sources/pkkp/data/2015/_unresolved_ocr_cells_2015.csv`); use ministry-level tables for 2015.
- **PKKP FY2009** is the archaic cash-basis presentation (genuine source absences).
- **DOSM small-area estimates** (district, parlimen, DUN) carry no published sampling error and
  some rows do not add up; see `sources/dosm/README.md` before ranking or aggregating them.
- See each source's README for its own caveats and anomaly registers.

## Next work
Follow the build order in `docs/DATA_MODEL.md` §15. Phase 0 (foundation: registry as data, CI,
archive, governance) then Phase 1 (a state-level, end-to-end slice: population, HIES, LFS, state
finances → `gap_need_vs_money` with agent tools).
