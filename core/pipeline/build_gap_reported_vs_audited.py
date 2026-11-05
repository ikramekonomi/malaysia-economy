#!/usr/bin/env python3
"""gap_reported_vs_audited (docs/DATA_MODEL.md §10, Phase 5): do MOF, BNM and PKKP agree?

  python3 core/pipeline/build_gap_reported_vs_audited.py -> core/gap_reported_vs_audited.csv, core/_validation_gap_rva.csv

Method (declared 2026-11-06 00:55 MYT, committed before the view was built. While checking units I saw the
three printings of federal operating expenditure for 2019, 2022 and 2024, and no other result):
* Grain: federal headline indicator x year. Each publisher's figure as core holds it (built by build_core
  build_federal_reported), never mixed or corrected:
    pkkp_audited   PKKP, the Auditor-General's certified accounts, that year's own volume (basis audited)
    bnm_actual     BNM Monthly Statistical Bulletin table 3.1, the annual row (basis actual, current vintage)
    mof_actual     MOF Tinjauan Fiskal Jadual 1.1, the edition chosen by curated/pipeline/mof_editions.py (own
                   volume Y+2); what later editions print differently is kept in mof_restated_in
  Indicators: federal_gov.revenue.total, .expenditure.opex (before the transfer to the Development Fund),
  .expenditure.devex (gross), .expenditure.covid_fund, .expenditure.devex_loan_recovery, .expenditure.devex_net.
  A row exists where at least two publishers print the indicator for the year; an indicator printed by only one
  publisher (the overall balance, MOF only in core) is not a row (listed in check G4).
* Three pairs: bnm - pkkp, mof - pkkp, mof - bnm (RM, signed). Status of each pair:
    agree          |difference| <= half the printed unit of the coarser of the two printings (MOF prints whole
                   RM juta: RM500,000; BNM prints RM million to the decimals in its value; PKKP prints sen)
    differ_minor   beyond that, but |difference| <= 0.1% of the larger of the two figures
    differ         beyond 0.1%
    not_held       one side missing
  Thresholds declared here, before results. A difference is reported, never resolved: which publisher is right
  is not decided by this view (PKKP is the anchor of last resort, CLAUDE.md, but a reported figure may use another
  scope or a later revision).
* Checks: G1 every value equals its observation; G2 every row traces to observation ids; G3 every indicator and
  year present once; G4 coverage (INFO): years per publisher and the indicators left out; G5 status counts (INFO).
"""
