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
