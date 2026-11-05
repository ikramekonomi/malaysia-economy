#!/usr/bin/env python3
"""Score the FY2025 model projections against FY2025 as reported (DATA_MODEL §15, Phase 5: 'FY2025 nowcast scored').

  python3 apps/models/score_nowcast_2025.py -> apps/models/_score_nowcast_2025.csv

An application, not warehouse data (§13.1). Method declared 2026-11-06 01:00 MYT and committed before any score was
computed (no FY2025 actual had been looked at for this purpose):
* What is scored: the projections already committed in this folder for FY2025, unchanged:
  fact_projection_headline.csv (rev, opex, devex, deficit; lo/mid/hi, RM billion; built from PKKP to FY2024) and
  fact_nowcast_2025.csv TOTAL_OE (sum of per-vote expected actuals, lo/mid/hi).
* Against what: FY2025 as REPORTED, because PKKP FY2025 (the audited accounts) is not yet published:
    MOF   Tinjauan Fiskal, the edition that prints FY2025 as official_actual (core: federal_gov.*, basis actual)
    BNM   MSB 3.1 annual 2025 (core, basis actual)
  Both are scored separately; neither is averaged. Every score is provisional and is re-scored when PKKP FY2025
  is loaded (the audited figure is the anchor, CLAUDE.md).
* Concepts are matched to how each projection was built: rev = federal_gov.revenue.total; opex and TOTAL_OE =
  federal_gov.expenditure.opex (before the transfer to the Development Fund); devex = federal_gov.expenditure.devex
  (gross); deficit = rev - opex - devex gross (the model's identity), computed from the same publisher's three
  lines, NOT the published overall balance (which uses net development spending and the COVID-19 Fund). debt is
  not scored: no FY2025 federal debt figure is held in core.
* Scores per series and publisher: inside_band (lo <= actual <= hi, with the deficit band's lo/hi taken as the
  min/max of the two ends), error_mid_rm_bil = actual - mid, error_mid_pct = (actual - mid) / actual, and
  band_width_pct = (hi - lo) / actual. No other metric, no re-fitting, no tuning after seeing the scores.
"""
