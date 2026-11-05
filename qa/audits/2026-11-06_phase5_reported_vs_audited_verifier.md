# Blind verifier: gap_reported_vs_audited (2026-11-06)

A separate agent was given only the declared method (the docstring), not the build code. It re-derived the 78 rows
from L1:
- PKKP: each year's own volume;
- BNM: the msb_3_1 annual rows;
- MOF: fact_headline, using the Y+2 edition rule.

**What matched:**
- every value, edition, signed difference and `mof_restated_in`;
- all MOF-vs-PKKP and MOF-vs-BNM statuses;
- the concepts: BNM current expenditure is PKKP opex before the transfer; revenue scopes match; the COVID-19 Fund
  is outside opex for all three.

| # | finding | severity | outcome |
|---|---|---|---|
| F1 | 12 BNM-vs-PKKP statuses were wrong under the declared rule: PKKP prints whole ringgit (FY2010-2024), not sen | high | fixed: the printed unit is read from each observation; all 12 now agree |
| F2 | BNM's msb_3_1 API keys are shifted from `ov_sur_def` onward: it holds the COVID-19 Fund, and `sou_fin_dom_bor_gro_dom_bor` holds the overall balance. BNM's Fund and overall balance were therefore missing | high | registered in `sources/bnm/data/_source_anomalies.csv` with proof; core maps both and proves it on every annual row (C20); the view gains BNM's Fund and the overall balance (89 rows) |
| F3 | PKKP's overall deficit (after gross development spending) was left out silently | medium | a note on the overall-balance rows and in the README: another concept, not compared |
| F4 | "PKKP does not print this line" was inaccurate for loan recoveries | medium | the note now says PKKP's line is broader (it adds miscellaneous receipts) |
| F5 | The README overstated two MOF exceptions that later MOF editions print in agreement | medium | README, and a note on those rows |
| F6 | Status grades print resolution, not size; BNM's unit varies by year | medium | README and tool how_to_read: read the RM gap; BNM's unit wording corrected |
| F7 | MOF's remaining exceptions are rounding so that its table adds up | low | README |
| F8 | 2 of MOF's 32 agreements are 0 = 0 | low | README |
| F9 | "Jadual 1.1" is 5.1 in the 2023 edition; the release id was stale | info | README; view re-released |

No threshold or status word was changed. Corrected BNM-vs-PKKP counts are 41 agree, 12 `differ_minor` (RM2.5 to
RM1.25m), which match the verifier's own recount.
