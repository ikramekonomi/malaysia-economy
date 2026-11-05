#!/usr/bin/env python3
"""gap_target_vs_outcome (docs/DATA_MODEL.md §10, Phase 5): was the plan target met?

  python3 core/pipeline/build_gap_target.py -> core/gap_target_vs_outcome.csv, core/_validation_gap_tvo.csv

Method (declared 2026-11-06 01:25 MYT, committed before the targets were extracted or any outcome compared; the
RMK12 appendix pages were read to find the tables):
* Targets: the Twelfth Malaysia Plan (RMKe-12, 2021-2025), Lampiran, as printed (sources/rmk/, basis target, edition
  rmk:rmk12): the 2025 target ('Sasaran 2025') and the 2021-2025 average annual growth target ('Sasaran RMKe-12')
  of three tables, the only ones whose outcome core holds today:
    Jadual 5   GDP by state at constant 2015 prices (KDNK; 'WP Kuala Lumpur' includes WP Putrajaya, as footnoted)
    Jadual 10  federal government finance (revenue, operating and gross development spending, loan recoveries, net
               development spending, overall balance, and the balance as % of GDP, a range)
    Jadual 14  labour market (employment, labour force, unemployment rate, participation rate)
  Lines whose outcome core does not hold are extracted at L1 and listed in check T5 (not compared): GDP per capita,
  sectors, the GDP by expenditure and income tables, and the rest of the appendix.
* Outcomes, each from core as published, never adjusted:
    GDP by state      gdp.real, DOSM, the current vintage, 2025 (and 2020 for growth); the KL row is WP Kuala Lumpur +
                      WP Putrajaya (the plan's own footnote), summed by declared rule; Labuan alone
    federal finance   MOF Tinjauan Fiskal FY2025 official actual (basis actual), with BNM beside it; PKKP FY2025
                      (audited) when loaded
    labour            lfs.*, DOSM, 2025 annual
* Comparison, by declared rule (no direction is assumed better):
    level targets     outcome / target and outcome - target; status at_target (within +-1% of the target),
                      above_target, below_target; for a range target (e.g. '-3.5 ~ -3.0'), within_range,
                      above_range, below_range
    growth targets    outcome = compound average growth 2020-2025 of the outcome series ((v2025 / v2020)^(1/5) - 1,
                      both from the same vintage); status the same words against the target (a point: within +-0.1
                      percentage point is at_target; a range: within_range)
    not_held          the outcome is not in core
  Status words state the position only; whether above or below is good depends on the line, and is left to the
  reader. All 13 states and the Federal Territories in the table are rows (golden rule 11).
* Checks: T1 Jadual 10's printed identities (revenue - opex = current balance; gross DE - loan recoveries = net DE;
  current balance - net DE - COVID-19 Fund = overall balance) for every printed column; T2 Jadual 14's sectors add
  up to total employment; T3 every target traces to its L1 row and page; T4 every row once; T5 coverage (INFO).
"""
