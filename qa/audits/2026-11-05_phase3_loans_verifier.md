# Blind verifier pass: federal loans to the states vs the states' own public debt (2026-11-05)

A separate agent with no access to the code (beyond the declared Method) re-derived every `loans` row of
`core/gap_federal_vs_state.csv` and the 195 `federal_gov.loans_receivable.state_government` observations, checked
federal values on the PKKP pages and every `differ` row on both publishers' pages.

**Result.** 0 differences in re-derivation. Federal: 91 of 91 values checked on the PKKP page match to the sen
(FY2010, 2011, 2014, 2017, 2019, 2021, 2024 x 13 states; 78 more match the next volume's prior-year column); C17
holds on the page in all 7 volumes. State: every agree/differ figure is the printed Jumlah (Hutang Awam) of the
own-year column; **no `differ` is caused by our extraction (class b: 0)**; 10 agree rows read, none by accident.

Every `differ` classified: 7 a state's other lender (Sabah bonds RM1,000m 2014-18, Pahang financial institutions),
5 a plus an unexplained residual, 15 a definition or timing difference the state report prints (Melaka 2020-21:
write-off RM10.80m + loans converted to grants RM162.72m = 173.52; Johor: interest exemption RM65.39m on the water
loan; Terengganu: Hutang Awam printed as principal and interest arrears), 36 unexplained (e.g. Kedah +89 to +93m
2018-23, Sarawak -14 to -51m, Perlis after restating its 2015 debt).

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | 5 of 6 `state_not_printed` are printed in the own volume | high | Perlis's `HUTANG KERAJAAN NEGERI` title and Kedah's lone `BAKI PADA DISEMBER` now extracted (Kedah 2024, Perlis 2023-24 in core); Kelantan 2021 (total on the continuation page) and Sarawak 2024 (text layer on ~12 of 183 pages) carry page-proved notes |
| 2 | 5 `printed_in_later_volume_only` are in the own volume | high | an unparsed own table now takes precedence (Selangor 2014, Johor 2015-16: `state_table_not_extracted`); Johor 2023, Selangor 2023, Pahang 2018: page-proved notes set `state_table_not_extracted` with the printed figure |
| 3 | 6 later-only rows have no own volume held | medium | new status `own_volume_not_held` (5 rows; Kelantan 2022 is the unparsed image-only volume) |
| 4 | the `state_table_not_extracted` rule never fired for loans | medium | the debt table (hutang_awam) is now the table kind checked for loans |
| 5 | Sabah bond years read as discrepancies | medium | where the state prints other lenders the federal part is compared: `agree_after_other_lenders` (Sabah 2014-15, 2017-18; Pahang 2015) |
| 6 | Pahang's note hid a negative federal-part residual | medium | the note now gives the federal-part difference |
| 7 | causes printed in the state reports not on the rows | medium | `meta/gap_note.csv` (year ranges): Melaka 2020-21, Johor 2019-24, Terengganu 2015-22, Perlis 2016-22 |
| 8 | Pahang 2022 lender note for a 0.00 line | low | zero lines are ignored |
| 9 | `federal_paid_rm` holds a balance for loans | low | said in the tool's how_to_read |

After: 63 agree, 5 agree_after_other_lenders, 61 differ, 8 state_table_not_extracted, 5 own_volume_not_held, 1
state_not_printed (Sarawak 2024, with its note). The 61 `differ` are differences between two audited publishers,
reported as printed.
