# Lampiran E and decision D30: blind verifier pass (2026-11-05)

New source: the Budget books' Lampiran E, actual federal grants to each state government by grant, FY2019-2024
(`sources/anggaran`, books 2021-2026). Decision D30: a class grant is split by state only where the payer
publishes the split, for a grant and year whose national total equals PKKP's audited line within RM2; used in
`gap_federal_placement` (grants_split_by_payer_rm) and `gap_federal_vs_state` (federal_by_state_rm). Method
declared and committed before any result from it (commit 416416f).

**Result.** The verifier re-extracted all six tables itself and compared all 1,358 cells: 0 disagreements
(amount, printed text, grant, vote code, tb/-/0, state). It viewed three pages as images for the column order;
re-derived every L5/L7 reconciliation, all 84 state-year splits of the placement view, placed_share every year
and all 156 by-state rows of gap_federal_vs_state (capitation 14 of 14 agree, largest difference RM7,520; the
Concurrent List 4 of 4). Every quoted figure checked. The 'Anggaran'-titled FY2022-2023 tables are actuals.

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | the tourism grants are printed in PKKP, as B.11 'Lain-lain Bayaran Balik' (objek 40000), FY2020-2024 within RM2 (FY2019 RM8.0m apart); they were excluded as having no PKKP line | high | reconciled in L5 and placed where they reconcile (dated amendment to the placement method and D30) |
| 2 | road sub-columns carried row_type 'state', so summing state rows would count road maintenance twice (RM4.58b FY2019, RM4.69b FY2020) | high | new `column_type` leaf / part / row_total; sum only `leaf` |
| 3 | 'MOF's split does not add up' overstated what was tested: only Concurrent List + libraries + museums against PKKP's one line | medium | wording says the three together do not equal the line and which one differs cannot be told |
| 4 | the tool said a class-grant state row 'cannot agree' while showing by_state_status agree; no caveat covered Lampiran E | medium | the note says 'from the audited accounts alone'; new CV28 on every row that uses Lampiran E |
| 5 | pre-D30 wording ('class grants are never split') | low | 'never split by formula'; the placement docstring points to method 4 |
| 6 | the road sub-columns equal PKKP's three road lines to the ringgit | low | L8 checks it and the labels say which line each equals |
| 7 | the national test cannot check MOF's split between states (round hundreds, repeated amounts) | low | stated in CV28 and the README |

After the fixes: L1-L4 and L8 PASS every year, 7 WARN kept as printed (Concurrent List group FY2019-2022, GTBKK
FY2023-2024, tourism FY2019); placed_share 2.5-2.9% from FY2019; the offline suite and evals green.
