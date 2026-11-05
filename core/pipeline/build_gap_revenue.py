#!/usr/bin/env python3
"""gap_revenue_estimate_vs_collected (docs/DATA_MODEL.md §10, Phase 5): did revenue come in as estimated?

  python3 core/pipeline/build_gap_revenue.py -> core/gap_revenue_estimate_vs_collected.csv, core/_validation_gap_rev.csv

Method (declared 2026-11-05, committed before any result of this view was computed):
* Core first: a new indicator federal_gov.revenue.by_type, breakdown hasil_kod = the Budget revenue book's section
  code (60000 tax, 70000 non-tax, 80000 non-revenue receipts, 90000 the Federal Territories' revenue) or _total.
  Two sources, each as printed:
    PKKP fact_revenue (Nota 5(a), FY2009-2024, each year its own volume): levels 0 and 1, with the original
      estimate (budget_estimate), revised estimate (revised_estimate) and actual (audited). PKKP prints names,
      not codes: the four level-1 names (and their FY2009-2011 'JUMLAH ...' spellings) map to the book's codes by
      the declared table NAME_TO_KOD below, proved by the 2024 actuals being printed in both (equal or reported).
      FY2009's 'JUMLAH PELBAGAI TERIMAAN' (miscellaneous receipts) has no book code and is kept under its own
      key, never merged.
    Anggaran Hasil books 2025-2026 (sources/anggaran-hasil): section and total rows: the actual two years back
      (basis actual), the revised estimate of the year before (revised_estimate) and the book year's estimate
      (budget_estimate).
* The view, grain hasil_kod x year: estimate_original, estimate_revised, actual_audited (PKKP), and the book's
  revised estimate and actual beside them; collection_rate = actual / original estimate and actual / revised;
  status: on_estimate (0.97-1.03 of the original), above_estimate (> 1.03), below_estimate (< 0.97), not_held.
  Thresholds declared here, before results. Book vs PKKP: agree within RM1 (whole ringgit against sen), else
  differ, reported never resolved.
* Checks: R1 each year's PKKP level-1 categories add up to the level-0 total (each basis); R2 PKKP's level-0
  audited total equals federal_gov.revenue.total (PKKP, the performance statement) or the difference is reported;
  R3 every value traces to an observation; R4 the book's sections add up to its total.
"""
