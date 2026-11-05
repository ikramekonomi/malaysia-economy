# Blind verifier: gap_revenue_estimate_vs_collected (2026-11-05)

A separate agent was given only the declared method (the docstring), not the build code. It re-derived the
view's 90 rows from PKKP `fact_revenue` (FY2009-2024, each year's own volume) and the Anggaran Hasil books
2025-2026 (`fact_hasil_ringkasan`).

**What matched (0 mismatches):**
- every value;
- both collection rates and all 90 statuses, including the cases near a threshold (2015 80000 at 1.03106; 2018
  total at 0.97091);
- every book-vs-PKKP difference;
- the name-to-code mapping in every year;
- completeness;
- categories adding up to the total for every year and basis;
- tracing to all 270 observations;
- PKKP's level-0 actual against federal_gov.revenue.total in all 16 years;
- no restatement between volumes.

| # | finding | severity | outcome |
|---|---|---|---|
| 1 | FY2009 'Pelbagai Terimaan' is the same line as 80000, renamed: the FY2010 volume reprints it as Terimaan Bukan Hasil, at the same amount and with the same sub-items. | medium | kept apart as declared (each year from its own volume, never merged); a note on the row and in the README gives the FY2010 reprint |
| 2 | 80000 'above_estimate' measures transfers, not collection (FY2024: 4.78x). | medium | a note on every 80000 row; README and the tool's how_to_read |
| 3 | PKKP's printed % is against the revised estimate, which is set late, so it can contradict the original-based status (FY2015 tax: 0.90 against a printed 97.3%). | low-medium | README and how_to_read |
| 4 | The anggaran-hasil validator labelled the RM144 FY2024 difference 'ROUNDING', but both sides are whole ringgit. | low | relabelled WARN in `sources/anggaran-hasil/pipeline/validate_hasil.py` (kept as printed) |
| 5 | CV22 (expenditure books) was attached to revenue rows, including an own-year estimate. | low | new CV29 (a revenue book's reprint of a past year) attached through the observations' own caveats; own-year estimates carry none |
| 6 | Labels: FY2009 is the C1 statement, not Nota 5(a); R1 lives as C18; FY2023's estimate is the re-tabled Budget 2023. | info | notes and docstring |

The verifier saw no reclassification behind any 'below_estimate'. The Federal Territories' shortfalls (2019:
0.46 of the estimate) are genuine and sit in FT tax.
