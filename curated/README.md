# Curated / consolidated layer

The comparable layer built **on top of** the per-source data in `sources/`. Sources are
never blended raw — this layer conforms shared dimensions so they can be compared and gaps
surfaced with a full audit trail back to each source.

Planned contents (build as sources land):
- **Conformed dimensions:** fiscal year; ministry/`maksud`; economic (object) classification;
  state/jurisdiction; program. A crosswalk maps each source's codes onto these.
- **Consolidated facts:** e.g. a spend fact carrying `source`, `jurisdiction` (federal/state),
  `year`, `maksud`, `measure` (budgeted / actual / reported), so budget-vs-actual and
  federal-vs-state comparisons are one query.
- **Gap views:** budgeted vs actual, estimate vs collected, audited vs headline-reported,
  planned vs delivered — see `docs/SOURCES.md` for the pairings.

## Here now

- **`fact_budget_vs_actual.csv`** — the first **budget-vs-actual gap view** (pilot **FY2024**),
  per ministry vote (`maksud`), split operating vs development, with variance and %
  utilisation. Built by `pipeline/build_gap_views.py`; reconciled to the sen
  (`_validation_gap_2024.csv`, 6/6 PASS) and independently verified. **Full schema, the
  important "what budget means" caveat, and the FY2024 findings are in
  [`GAP_VIEWS.md`](GAP_VIEWS.md) — read it before using the data.**

  Interim note: the independent *Anggaran Perbelanjaan* budget book (source #2) is not yet
  ingested (not machine-readable; its host is blocked by the current egress policy), so this
  pilot's "budget" is PKKP's own recorded appropriation. It slots an independent budget — and
  an Anggaran-vs-PKKP cross-check — in as soon as source #2 lands.

- **`fact_obligations.csv`** — the **obligations layer**: what the federal government owes
  (debt, PFI, financial commitments incl. unpaid tax refunds, committed guarantees by
  entity, statutory/contingent guarantees) and is owed (receivables / revenue arrears),
  unified across PKKP's audited Penyata Akaun Memorandum (FY2009–FY2024), the
  Auditor-General's LKAN 3/2025 fiscal tables and the MOF Fiscal Outlook fiscal-risk
  tables. Built by `pipeline/build_obligations.py`; `_validation_obligations.csv`
  (94/94 PASS) ties every register to its own printed total and cross-checks the three
  sources against each other. **Class map, do-not-sum warnings and era caveats are in
  [`OBLIGATIONS.md`](OBLIGATIONS.md) — read it before using the data.**

## Derived labour indicators (`fact_labour_indicators.csv`)

`basis='derived'` — **not** DOSM statistics. DOSM publishes no salaries-and-wages
dataset through its API (verified against all 289 data.gov.my and 182 OpenDOSM ids;
the Salaries & Wages Survey is a PDF publication on an unreachable host, and the
Labour Force Survey carries no income field). Until that survey is acquired
(docs/SOURCES.md Tier 1b), these two indicators fill the gap from sources already
held:

- `implied_average_wage_rm_per_worker_year` = compensation of employees (income-approach
  GDP, `component=i1`) ÷ employed persons (LFS `lf_employed`), 2010–2023.
- `labour_share_of_gdp_pct` = compensation of employees ÷ GDP (`i0`) × 100.

**Read the caveats before quoting either.** The denominator counts all employed
persons while the numerator counts only employees, so the wage figure *understates*
the average employee wage by roughly the self-employed share — it is a consistent
series, not a level estimate. Compensation includes employer EPF/SOCSO contributions,
so it is labour cost, not take-home pay. Both are national and nominal; no sector,
state, occupation or percentile detail is derivable, which is precisely what the
missing survey would provide. Built by `pipeline/build_labour_indicators.py`,
29 checks in `_validation_labour.csv`.
