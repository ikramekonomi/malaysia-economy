# Analyst guide — how to use this warehouse without getting a wrong answer

`CLAUDE.md` is the operating manual for people *building* this warehouse. This is for
people *querying* it. Read the seven traps (§3) before you write your first `SUM()`.

## 1. The model in 60 seconds

**No single source is "the truth."** Each domain has a hub — the record others in that
domain reconcile against — and the warehouse's actual product is the **reconciliation
layer**: where independent institutions agree to the ringgit, and where they diverge, by
how much, kept exactly as published.

| Domain | Hub | Reconciled against it |
|---|---|---|
| Federal fiscal | `sources/pkkp` (audited actuals, FY2009–FY2024) | budgets, BNM, Auditor-General, MOF outlook |
| Agencies & GLCs | `sources/audit-negara` certifications | e-SelfAudit censuses, findings |
| States | `sources/states` (each state's audited statements) | state budgets, state LKAN, DOSM |
| Real economy | `sources/dosm` | GFS, CPI, state GDP |
| Monetary/financial | `sources/bnm` | debt issuance, holdings |

Sources are **namespaced and never merged**. Comparison happens only in `core/` (the gap views), with the older `curated/` layer retiring,
through conformed dimensions (year, jurisdiction, entity, economic classification).

## 2. Where to start, by question

| Your question | Start here |
|---|---|
| What did the federal government actually spend/collect? | `sources/pkkp` (`pkkp.duckdb`, rebuild with `sources/pkkp/pipeline/build_duckdb.py`) |
| What was budgeted, by ministry? | `sources/anggaran/data/<yr>/fact_anggaran_maksud_<yr>.csv` |
| …by programme, activity, object class, or headcount? | `…/fact_anggaran_detail_<yr>.csv` (26k rows, 2024–2026) |
| Budgeted vs actual, ministry level, 2009–2026 | `core/gap_budget_vs_actual.csv` (projects: `core/gap_project_budget_vs_actual.csv`) |
| What is owed but not yet paid (guarantees, PFI, arrears)? | `curated/fact_obligations.csv` + `curated/OBLIGATIONS.md` |
| What did the Auditor-General find, and did anyone answer? | `sources/audit-negara/data/fact_lkan_findings.csv` |
| Which agencies/GLCs sit outside the federal accounts? | `…/fact_eselfaudit_registers.csv`, `fact_agensi_sijil_<yr>.csv` |
| Anything about a state, or all states compared | `sources/states/data/_national/fact_state_finance_all.csv` |
| Denominators (%GDP, per capita, real terms) | `sources/dosm` |
| Intra-year / monthly / debt-holder detail | `sources/bnm` |
| 2025–27 figures | `sources/mof-fiscal-outlook/` (MOF official: FY2025 actuals, FY2026 revised, FY2027 budget). Our own models: `apps/models/` — **model output, never actuals** |

## 3. The seven traps

Each of these will silently give you a wrong number. They are the reason this file exists.

**1. Never blend bases.** Every figure carries a `basis` or `measure`. `audited` ≠
`budget` ≠ `official_projection` ≠ `official_revised` ≠ `reported` ≠ `model_projection`.
A chart mixing audited actuals with a model projection without a visual break is a lie.
2025 and 2026 are **not** actuals anywhere in this warehouse.

**2. Sum only leaf rows.** Long-format fact tables carry components *and* their printed
subtotals and totals in the same file. Filter `row_type='component'` (or `is_leaf='yes'`).
Summing a whole table double-counts, sometimes triple-counts.

**3. One row per fact — use the canonical filter.** The same figure is printed in several
tables of one volume, and reprinted as a comparative by later volumes. For the states
data the safe filter is:
```
column_role='own_year' AND is_canonical='yes' AND measure='actual'
```
`own_year` = the volume that audits that year; `comparative` = a later volume reprinting
it (useful for restatement analysis, wrong for a series).

**4. Verbatim vs conformed values.** `amount_rm` is exactly as printed — including
negatives where the source prints a deduction, e.g. FY2024 state opex as `(2,725.11)`.
`amount_rm_conformed` is the sign-normalised level. Use `amount_rm` to quote a source;
use `amount_rm_conformed` to build a series. `sign_convention` tells you which applies.

**5. Mind the identity contract.** In `sources/states`, `revenue_total` and `opex_total`
sit on **different bases printed on different pages in 99 of 137 state-years**. The
internally consistent set is the performance-statement one:
`revenue_total − opex_before_transfer − devex_total = surplus_deficit`, which closes to
the sen in 109 of 120 state-years; the 11 residuals are printed facts (Pahang prints a
third expenditure head, Johor prints an unsigned balance). Check `N2_identity_*` for your
state-year before differencing. The federal side has the same hazard: the Auditor-General
and BNM present development expenditure on different bases.

**6. Join on codes, never names.** Ministry and agency names change spelling, get
reorganised, and wrap across lines. Use `maksud_code`, `projek_code`, `line_code`,
`butiran_code`. Where a label could not be reconstructed, the row says so
(`label_quality`) rather than presenting a guess.

**7. Respect the quality flags.** `data_quality='suspect'` marks rows we know are wrong
and have not yet fixed — filter them out. Unconformed codes (`line_code_conformed='no'`)
are deliberate: a state-specific trust fund must never occupy a shared code.

## 4. How much to trust a number

Every source carries three companion files, and the distinction between the last two is
the most important thing in this repo:

- `_validation_*.csv` — every check run, with its expected/actual and provenance.
- `_source_anomalies_*.csv` — **the source's own** printed inconsistencies, each with
  arithmetic proof and a page reference. Kept exactly as printed; never corrected.
- `_known_extraction_defects_*.csv` — **our** defects, diagnosed but unfixed, with the
  reason and the impact.

Filing our bug as a source misprint would falsely accuse the publishing institution. In
the states build, 61 of 95 anomaly claims turned out to be our own bugs on inspection —
they were fixed, and 23 genuine ones remain. Assume the same discipline applies
everywhere: if a figure looks impossible, check `_known_extraction_defects` first.

Every dataset here was reconciled to its source's printed totals **and** re-derived by an
independent verifier that never saw the extraction code. Where a verifier disagreed, the
disagreement was resolved before the data was committed.

## 5. What this warehouse can answer that public sources cannot

- **Budget vs actual at programme grain**, with headcount alongside — separating "spent
  more because it hired more" from real per-head growth.
- **The obligations position beside the cash position.** FY2024 memorandum liabilities
  RM1,577.8b (81.7% of GDP) against the RM1,247.6b debt-only headline; and the dated fact
  that PKKP disclosed no committed-guarantee, PFI, or arrears detail *at all* before
  FY2018.
- **13 states on comparable line codes**, FY2014–2024 — the first machine-readable
  cross-state fiscal panel.
- **Institutional disagreement, quantified.** e.g. BNM's reported FY2023 gross
  development expenditure exceeds the audited figure by RM1.247 juta while the
  Auditor-General agrees with PKKP; DOSM's state operating-expenditure column matches
  *before-transfer* for five states and *after-transfer* for four, so it is not comparable
  across states as published.
- **Audit findings joined to the money** — 426 findings with verbatim amounts, keyed to
  the ministries that own the votes.

## 6. Known limitations, stated up front

- **2009–2013 Auditor-General reports are unobtainable** — Parliament's online archive
  begins mid-2013. The audit layer starts ~2014 while PKKP starts 2009.
- **FY2015 PKKP object/project leaves are OCR-provisional** (image-only volume); use the
  ministry-level tables for that year.
- **Kelantan FY2022** is an image-only scan — nothing extracted rather than partially
  extracted.
- **Development (P) votes** have no detail-grain extraction yet; the books print them in
  a different project-list layout.
- **DOSM's quarterly federal GFS is frozen at 2024-Q1**; BNM MSB 3.1.x is the live series.

## 7. Reproducing anything

Raw PDFs are gitignored; every source's `pipeline/` re-downloads (hash-checked against
the manifest) and re-extracts. `python3 sources/pkkp/pipeline/build_duckdb.py` rebuilds the PKKP
database. Extraction needs `poppler-utils` and `tesseract-ocr`; querying needs only
`duckdb`. Every row carries `source_file` and `pdf_page` — if you doubt a number, open
the page.
