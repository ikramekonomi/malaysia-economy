#!/usr/bin/env python3
"""gap_obligations_growth (docs/DATA_MODEL.md §10, Phase 5): are off-budget obligations growing faster than debt?

  python3 core/pipeline/build_gap_obligations.py -> core/gap_obligations_growth.csv, core/_validation_gap_obl.csv

Method (declared 2026-11-06 01:20 MYT, committed before any result of this view was computed; the levels below
were seen in curated/fact_obligations.csv while choosing the lines, no growth or ratio was computed):
* Core first: a family federal_gov.obligation.*, stocks at 31 December, basis audited, from PKKP's memorandum
  accounts, each year from its own volume (golden rule 6; the prior-year column each volume also prints is used
  only in check O3). One printed figure per instrument and year, never summed by us:
    debt                   Penyata Akaun Memorandum 'Hutang Awam' (to FY2015) / 'Hutang Persekutuan' (FY2016+)
    pfi                    memorandum 'Liabiliti Inisiatif Pembiayaan Swasta' (first printed FY2018)
    commitments            memorandum 'Komitmen Kewangan' (FY2018+; includes the committed guarantees)
    committed_guarantees   Komitmen Jaminan register, printed 'JUMLAH KOMITMEN JAMINAN' (FY2018+)
    loan_guarantees        Jaminan Berkanun register, loans: 'JUMLAH JAMINAN PINJAMAN' (FY2012+); FY2009-2011
                           print no deposit section, so their 'JUMLAH JAMINAN' / 'JUMLAH JAMINAN BERKANUN' total
                           is the loan guarantees (proved by Badan Berkanun + Syarikat = that total, check O2)
    deposit_guarantees     Jaminan Berkanun register 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT' (FY2012+)
  The Auditor-General's re-presentation (LKAN) and MOF's Fiscal Outlook (end-June positions) stay in
  curated/fact_obligations.csv for now: one publisher per series in this view.
* The view, grain instrument x year: amount, prior year's amount (own volumes), change, growth = amount / prior
  - 1, debt's growth the same year, growth_minus_debt_pp, ratio_to_debt = amount / debt, and an index (first year
  held = 100) beside debt's index on the same base. Status: grew_faster_than_debt (growth > debt's growth),
  grew_slower_than_debt (<), grew_as_debt (equal to 4 decimal places), first_year (no prior year held), and for
  debt itself 'the benchmark'. Ratios to 4 decimals, no rounding before the end. Never added across
  instruments: commitments include the committed guarantees, and deposit guarantees overlap deposit insurance.
* Checks: O1 every value equals its observation; O2 FY2009-2011 loan guarantees = Badan Berkanun + Syarikat
  subtotals as printed, and FY2012+ the same identity; O3 each volume's prior-year column against the previous
  volume's own figure (a restatement is INFO, reported, never applied); O4 every instrument and year once; O5
  growth summary per instrument over its whole span against debt's over the same span (INFO).
"""
