# Malaysia Public Finance Data Warehouse

A consolidated, fully-verifiable data warehouse of **Malaysia's public finances** — federal
**and** state — built to understand, track, analyse, and **find gaps in the country's fiscal
behaviour**. Multiple official sources are ingested with complete provenance, then curated
into a comparable layer so the same concept can be traced and cross-checked across sources.

**Using the data?** Read **`docs/ANALYST_GUIDE.md`** first — the query traps
(basis blending, leaf rows, canonical rows, sign conventions, the identity contract)
will each silently give you a wrong number.


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
  pipeline/build_warehouse_duckdb.py  rebuilds curated/warehouse.duckdb (all 8 sources + curated/)
pipeline/build_duckdb.py   rebuilds sources/pkkp/pkkp.duckdb from the CSVs (PKKP only)
docs/SOURCES.md     source catalogue: federal, state, statistics — priority + gap pairings
```

## Sources

Eight sources, each namespaced under `sources/<name>/` with its own extraction, provenance
and validation. Sources are never merged — comparison happens only in `curated/`.

| # | Source | What it is | Publisher | Coverage | Rows | Checks | Route |
|---|---|---|---|---|---|---|---|
| 1 | **pkkp** | *Penyata Kewangan Kerajaan Persekutuan* — audited federal accounts to object/project level. **Hub of the federal-fiscal domain** | Akauntan Negara, audited by AG | FY2009–FY2024 | 141,951 | 7,329 | PDF |
| 2 | **anggaran** | *Anggaran Perbelanjaan Persekutuan* — the budget as tabled, at ministry **and** programme/activity/object grain, **plus headcount** | MOF | Budgets 2024–2026 | 29,202 | 12,037 | PDF |
| 3 | **anggaran-hasil** | *Anggaran Hasil* — revenue estimates by kod hasil, incl. tax-measure impacts | MOF | Budgets 2025–2026 | 496 | 132 | PDF |
| 4 | **mof-fiscal-outlook** | *Tinjauan Fiskal* — official projections, debt, **contingent liabilities and guarantee registers** | MOF | Editions 2025–2026 | 184 | 55 | PDF |
| 5 | **audit-negara** | Auditor-General's reports: audit inventory, 426 findings with amounts and ministry responses, per-agency certifications, e-SelfAudit censuses, the AG's own fiscal tables | Jabatan Audit Negara | LKAN 2024–2026 (+402-volume manifest 2015–2026) | 3,285 | 160 | Parliament Command Papers |
| 6 | **states** | **All 13 states'** audited financial statements — finance, revenue, agency registers, plus a conformed national panel | State treasuries, audited by AG | FY2014–FY2024 | 50,053 | 10,224 | Parliament Command Papers |
| 7 | **bnm** | Monthly Highlights & Statistics — federal finance quarterly, debt by holder/maturity, monetary, banking, external | Bank Negara Malaysia | 1996–2026 | 8,106 | 280 | **OpenAPI** |
| 8 | **dosm** | GDP/GNI, population, state GDP, CPI (national + state), labour force, trade, federal and state GFS | DOSM / data.gov.my | 1947–2026 | 86,245 | 34 | **OpenAPI** |

Plus the **curated layer** (1,491 rows): `fact_planning_efficiency` (tabled budget vs audited
actual 2010–2024), `fact_budget_vs_actual`, `fact_obligations` (debt, PFI, commitments,
guarantees, arrears and contingent liabilities unified across three publishers),
`forecast/` (2025–26 projections with bands — **model output, never actuals**), and the
published `dashboard/`.

**Totals: 319,522 rows · 30,251 validation checks · 47 catalogued source anomalies** (the
publishers' own misprints, kept exactly as printed with arithmetic proof). Every source is
reconciled to its own printed totals *and* re-derived by an independent verifier blind to
the extraction code.

What is not yet in — state budgets, PAC reports, procurement awards, tax-authority detail,
GLC/GLIC accounts, local-authority finances, and the wider real-economy sources — is
catalogued with priorities in `docs/SOURCES.md`.

## Quick start
```bash
pip install -r requirements.txt
python3 pipeline/build_duckdb.py          # builds sources/pkkp/pkkp.duckdb from the CSVs (PKKP only)
duckdb sources/pkkp/pkkp.duckdb
```
Then read `sources/pkkp/README_QUICKSTART.md`. Core rules: CSVs are canonical (the .duckdb is
a rebuildable cache); **join on codes, not names**; **sum only leaf rows**; take each year
from its own volume; **never silently correct a published figure**.

**Querying across all eight sources?**
```bash
python3 curated/pipeline/build_warehouse_duckdb.py    # builds curated/warehouse.duckdb (all sources + curated/)
duckdb curated/warehouse.duckdb
```
Each source gets its own DuckDB **schema** (`pkkp`, `anggaran`, `anggaran_hasil`,
`mof_fiscal_outlook`, `audit_negara`, `states`, `bnm`, `dosm`, plus `curated`) — sources are
namespaced, never merged, per the golden rule above; query fully-qualified, e.g.
`SELECT * FROM anggaran.fact_anggaran_maksud_2024`. Read `docs/ANALYST_GUIDE.md` before your
first cross-source query — it covers the seven traps (basis blending, leaf rows, canonical
rows) this consolidated file makes it easy to hit by accident.

## Known caveat
FY2015 is the one image-only scan — its object-leaf/project-leaf amounts are OCR-provisional
(fully-verified everywhere else). See `sources/pkkp/VALIDATION_REPORT.md`.
