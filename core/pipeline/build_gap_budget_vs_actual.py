#!/usr/bin/env python3
"""gap_budget_vs_actual (docs/DATA_MODEL.md §10, Phase 5): was the money budgeted spent?

  python3 core/pipeline/build_gap_budget_vs_actual.py -> core/gap_budget_vs_actual.csv, core/_validation_gap_bva.csv

Method (declared 2026-11-05, committed before any result of this view was computed):
* Grain: federal body (entity, D26/D28/D31) x year x flow (opex: B and T votes' operating spending; devex: P
  votes' development spending), every year the audited accounts are held (PKKP FY2009-2024) and the Budget books'
  estimate years (Anggaran 2024-2026: 2023-2026). Spending heads (T.*, P.70) are rows of the federal government
  (E000001) with their head as breakdown, as in core. Each year from its own volume (golden rule 6).
* Columns, each one source as printed, never mixed:
    estimate_original_pkkp   opex: the original estimate the audited accounts print (Nota 5(b) anggaran_asal)
    estimate_revised_pkkp    opex: the revised estimate (anggaran_dipinda); devex: the accounts' own allocation
                             column (Lampiran 2 'Anggaran'), which is NOT the Budget book's original estimate
                             (FY2024: RM85.2b against the book's RM92.0b), so it is labelled an allocation
    estimate_original_book   the Budget book's original estimate for that year (the book of that year, or the
                             next book's 'anggaran asal' column)
    actual_audited           PKKP sebenar
    actual_book              the Budget book's reprint of that year's actual (the books two years later)
* Derived, by declared rules only (meta/derivation.csv DV1-style ratios, no rounding before the end):
    execution_rate           actual_audited / estimate_revised_pkkp (opex), / the allocation (devex)
    unspent_rm               estimate_revised_pkkp - actual_audited (negative = overspent)
    book_vs_pkkp_estimate_rm estimate_original_book - estimate_original_pkkp (opex): two printings of one
                             estimate; a difference is reported, never resolved
    book_vs_pkkp_actual_rm   actual_book - actual_audited: MOF's reprint against the audit; a difference is a
                             restatement or a different scope (the book prints under its own year's votes)
* Status words, no ranking: within_estimate (execution 0.90-1.00), underspent (< 0.90), overspent (> 1.00),
  not_held (a side missing), and for the two-printings columns agree (|difference| <= RM1, whole ringgit against
  sen) or differ. Thresholds declared here, before results.
* A body's row is only ever its own vote: a lapsed vote's successor is another body (lineage, never summed);
  growth across years is not computed in this view.
* Checks: V1 every row's audited actual equals its fact_observation; V2 each year's opex and devex rows add up to
  the PKKP vote totals (C16); V3 every value traces to an observation id; V4 every body and year present once.
"""
