# Lapsed votes and lineage: blind verifier passes (2026-11-05)

Decision D28 (by a person, 2026-11-05): B.15, B.26 and B.33 each name two different bodies, before and after a
lapse, and all six stay separate entities (`confirmed`). Where their work was printed in the lapse years is
**lineage**: a link between two bodies, never one ID (`meta/entity_lineage.csv`, evidence in
`meta/entity_lineage_evidence.csv`, re-found in PKKP L1 on every build, checks E9 and E10).

## First pass (8 links, 43 evidence lines)

43 of 43 lines re-derived from L1 (name, code, entity, PDF and printed page); 41 checked on the printed page
(8 archived volumes, sha256 matched; the 2 FY2020 lines on L1 only, no archived PDF). The FY2018 cooperatives
split was confirmed on the page (SKM RM38.4m under B.25 p143 and under B.26 p147).

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | L01 is a mid-year move (B.06 still spent UPE RM23.17m and statistics RM80.6m in FY2018) but was flagged `no`; E9 missed it because it compared names case-sensitively | high | E9 compares names ignoring case and spacing; L01 `moved_mid_year=yes` |
| 2 | L02 began in FY2020, not 2021: B.06 prints UPE (RM50.3m) and DOSM (RM129.2m) from 2020 with nil original estimates | high | L02 first_year 2020, mid-year; E9 now also requires the new vote to spend nothing on the work the year before, which catches this |
| 3 | L04/L05 moved during FY2009: B.25 spent the Cooperatives Commission in full (RM45.6m), MARA split between B.26 (RM969.2m) and B.22 (RM947.5m) | high | L04 first_year 2009 (not mid-year: B.26 spends nothing on it); L05 2009, mid-year |
| 4 | B.15's RISDA (its largest 2020 line) and MARA went to B.22 with no link | medium | L09 (B.22 to B.15, 2018, mid-year), L10 (MARA back, 2019), L11 (RISDA back, 2020, mid-year) |
| 5 | B.64 (Higher Education) also lapses (FY2019) and B.49 ends in 2013, but they are one entity by an earlier analyst rule, with no lineage | medium | L12 (FY2013 into Education, mid-year), L13 (FY2019), L14 (back in FY2020, mid-year); the FY2015 return is not linked (OCR-provisional scan). The identity itself was not re-decided: raised with the user |
| 6 | `get_entity` for a lapse year (B.15 2021, B.33 2023) answered "no body held" with no pointer | low | a year inside a lapse returns the links out of the body before and into the body after |
| 7 | E000037's English name sits in `source_text` though not printed | low | `name_en_note` says the source prints no English name |
| 8 | A year's answer heads with the latest name | low | `printed_in_year` gives that year's printed names |
| 9 | L08 "revised to 0" wording; B.33's own 2024 original estimate is nil | low | note reworded |
| 10 | FY2018 printed_page is the volume's page number, not the Lampiran footer | low | L1-wide convention, left |

Confirmed correct: L03, L06, L07, L08 as described; environment stays under B.23 in 2024 (RM135.2m, p149);
"P.15 printed to 2021", "P.33 to 2023"; every answer about B.15, B.26 and B.33 warns that the code was also held
by a different body.

## Second pass (14 links, 63 evidence lines)

All 14 links re-derived from L1 leaf rows; 28 printed pages checked (FY2009, 2013, 2017, 2018, 2019, 2022,
2023, 2024; the 2013 and 2019 volumes fetched from the archive, sha256 matched; FY2020 on L1 only). Every
evidence line is printed under its code, year and body; every first_year and moved_mid_year matches both votes'
actual spending; every amount in the notes matches the page; each link points to the main destination. No wrong
link or wrong year.

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | `old_vote_actual_rm_in_first_year` for L06 'Pembangunan Koperasi' was 91,217,918.92, twice the printed programme total 45,608,959.46: from FY2010 a programme with activities also prints object_program rows that repeat its activities | high (derived amount) | spending sums an activity's object lines, and a programme's own object lines only where it has no activities; now 45,608,959.46 (p143-144) |
| 2 | Higher Education's FY2015 return to B.64 has no link, so Education reads as holding the universities 2013-2019; `get_entity('B.64', 2014)` gave no pointer | medium | L15 (B.41 to B.64, 2015): the new vote's side is the vote itself (`level=vote`, ministry-level table p68, RM12.23bn), because FY2015 activity names are OCR-provisional; a lapse across two codes of one body (B.49, B.64) now returns its links |
| 3 | B.26's other FY2009 lines (RM265m, mostly DASAR BARU) are not traced | low | the L04 note already says so |
| 4 | the tool's reading note said "the next year", wrong for mid-year links | medium | reworded: from first_year, the same year for a mid-year move |
| 5 | D28 stated the year-before rule with no exception, which L10 (MARA returning) breaks as written | low | the exception is written into D28 |
| 6 | D28's rationale said B.23 held "water, energy and environment" from B.33; energy was B.23's own | low | corrected |
| 7 | smaller FY2018 moves into B.15 (Malaysia-Japan programme, LADA, TERAJU, MPRC) not linked; L01 and L09 cover about 91% | low | stated in the L09 note |
| 8 | L04/L05 cannot be tested against FY2008 (not held) | low | stated in their notes |
| 9 | the brief named object_program as a leaf | medium (method) | the root of #1, fixed there |

After the fixes: 15 links, 66 evidence lines, E1-E10 PASS, 235 eval questions pass, offline suite 22 known
FAILs (no new).
