# Blind verifier: gap_budget_vs_actual (2026-11-05)

A separate agent was given the declared method (the docstring only), not the build code. It re-derived every row
from L1 (PKKP FY2009-2024: Nota 5(b), Lampiran 2; Anggaran Perbelanjaan books 2024-2026).

**Agreement.** It matched 1,439 of 1,452 rows on entity, breakdown, flow and year. On every matched row these
agreed: both PKKP estimates, the audited actual, the book estimate, execution_rate, status and the agree/differ
flags. Lapsed votes land on the right body (B.15, B.26, B.33, B.49, B.64); T heads and P.70 sit on E000001; no
vote-year is missing or duplicated. The devex 'allocation' label was confirmed: it equals the book's estimate for
only 6 of 30 votes (2023) and 4 of 31 (2024).

| # | finding | severity | outcome |
|---|---|---|---|
| 1 | 2024 `estimate_original_book` mixed two books: PETRA and Digital came from the 2025 book, which restates FY2024 under reorganised votes, while the 2024 book holds that money under the old ministries. The double count was RM5.69b devex and RM0.52b opex. | high | fixed: one book per year (that year's own book); the other book's figure is named in the note; new check V7 proves the column adds up to one book |
| 2 | A book reprint under a successor's vote landed on the successor: the 2025 book prints KASA's FY2022 actuals (RM3.43b) under B.33, which the view put on PETRA, so the money appeared twice in 2022. Smaller zero cases also existed. | high | fixed: a reprinted actual is shown only on the body that held the vote that year; 19 reprints (RM3.43b, the rest zeros) are listed in V8; 12 rows that existed only through them are gone (1,440 rows) |
| 3 | FY2009 devex rows do not add up to the printed grand total (P.26/P.44 transferred out, -RM224.3m; documented at L1). This was not disclosed. | medium | disclosed in the README; those rows now carry the observations' own caveats (CV21) |
| 4 | Misleading status words: P.70 is always underspent, B.12 always overspent, B.11 2022 is 5.96x, and supplementary supply is not mentioned. | medium | notes on those rows and on every row spent above its estimate; README and tool how_to_read |
| 5 | Devex "within_estimate" is measured against an allocation, not the tabled estimate. | medium | new column execution_rate_book (actual / the book's original estimate) beside it; README and tool |
| 6 | FY2015 devex allocations carry OCR residue (grand total off by RM60,000; P.27, P.29). | low | note on FY2015 devex rows |
| 7 | B.48 2012 is overspent at a displayed 1.0000 (RM1,390 over; unspent_rm shows it); two "different actuals" notes are RM1; the release id was stale. | low | kept (the rate is exact before rounding, and unspent_rm shows the amount); the view was re-released against the current core |

No threshold or status rule was changed. The verifier's script was
`scratchpad/bva_verify/derive.py` (session scratch, not committed).
