# State parser: shifted columns, wrapped labels and prose rows (2026-11-05)

Why: the federal-vs-state reconciliation (Phase 3) reads the states' grant lines, and Selangor FY2014's
Concurrent List grant was 45.37 (2013's figure) with half its label on the `Jumlah` row. Fixing it exposed
the same defects across the state tables.

## What changed in `sources/states/pipeline/`

1. **Shifted rows** (`lkan_state_parser.parse_rows`). When a row is set at a different offset from the rest,
   right-edge clustering puts its figures in columns with no unit and the years slide. A row with a figure off
   the unit strip, printing exactly one figure per column of the widest on-strip row, is now mapped in printed
   order onto those columns. Fixed: Selangor CMD.61.2015 J4.11 (2013 figures shipped as FY2014: land tax 386.30
   for 395.37), J4.17 (2010-2014 opex shifted a year), J4.21, J4.28; Johor CMD.35.2016 J4.15, J4.20 (FY2015
   trust total 1,454.59 for 1,628.54); Melaka CMD.37.2016 J4.21, J4.43 (FY2015 public debt 861.71 for 852.84,
   reaches core), CMD.53.2015 J4.39; Pahang CMD.39.2016 J4.5; Johor CMD.51.2015 J4.4.
2. **Wrapped labels** (both parsers). A label line exactly between two rows is placed by its glyph position
   (`pdftotext -bbox-layout`, cached beside the text cache): a line inside a cell sits closer to its own row.
   Never onto a closed total/balance line, never a line that opens a numbered item, carries digits or a bullet.
   A word broken at a hyphen rejoins (`Jabatan-Jabatan`). 158 labels in 13 states moved to their own row (the
   Concurrent List grant in Kedah, Selangor, Terengganu; dozens of `<name tail> Jumlah` totals).
3. **Prose rows** (`extract_states.label_quality`). The audit's sentences under a table (`Pada tahun 2020, ...
   membelanjakan`, `... di Jadual 4.20`, `RM184 juta berbanding`) were shipped as rows, some canonical, with
   wrong-year figures; 52 more are now dropped and logged in `_dropped_rows_<state>.csv`. `sebanyak RM` is
   deliberately not a prose marker: it is welded onto real labels whose code is conformed (Perak CMD.25.2024 J7
   revenue total), and dropping those lost data. No conformed row was lost.

## Effect

* 4 baseline FAILs resolved (26 -> 22): Johor V1 trust composition and intra-volume contradiction, Selangor
  V1 loan-account flow, one national N6 splice. Two `KNOWN_EXTRACTION_DEFECTS` entries retired (fixed).
* core: Melaka public debt FY2015 corrected (852.84) and FY2014 added (861.71); Pulau Pinang debt FY2014
  (61.52) and FY2018 (57.83) and Sarawak FY2024 non-revenue receipts (165.79) newly conformed. All page-checked.
* A page-blind checker (every CSV row's amounts must sit under the header years on one printed line, all 2,913
  tables) passes 2,292 tables against 2,243 before; no table got worse.

## Blind verifier (first pass, on change 1)

80 changed rows: 50 added all confirmed, 30 removed all genuinely wrong; the 10 touched tables right in full;
0 regressions. It also found older defects, handled as follows:

| # | Finding | Done |
|---|---|---|
| 1 | Melaka CMD.37.2016 J4.43 FY2015 debt = 2014's (reached core) | fixed (change 1, per-row) |
| 2 | Sarawak CMD.44.2016 J4.30 depositor counts read as RM | known defect, rows `suspect` (unconformed) |
| 3 | Johor CMD.51.2015 J4.4 total welded to a label, years shifted | fixed (changes 1-2) |
| 4 | Melaka CMD.35.2017 J4.49 header misprinted `2015 2015` | known defect, rows `suspect` |
| 5 | Kedah CMD.34.2018 J4.8/4.9 FY2016 read from the restated column (`-` = 0) | known defect; national panel takes FY2016 from its own volume |
| 6 | Narrative sentences as canonical rows | fixed (change 3) |
| 7 | Sabah CMD.43.2016 J4.31 `Corporation Sdn. Bhd. Jumlah` typed a leaf | known defect |
| 8-9 | label-only issues; integer-printed `0`/`5` cells missing | left (labels; absent, not wrong) |

A second blind pass covers changes 2-3 (`2026-11-05_state_column_shift_verifier2.md`).
