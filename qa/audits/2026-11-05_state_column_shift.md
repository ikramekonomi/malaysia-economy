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

## Blind verifier (second pass, on changes 2-3) and what was done

175 of 190 relabel groups opened on the page: 169 better, 4 same, 2 worse; all 5 year moves and all 5 core
changes right; checker 2,267 ok vs 2,248 at the first fix. Findings:

| # | Finding | Done |
|---|---|---|
| 1 | Johor CMD.29.2020 J10: the JENIS HASIL column text interleaved into the name, land premium lost its conformed code | the label stops at a JENIS HASIL column printed right of BUTIRAN; `Premium Bagi Geran` conformed again |
| 2 | Pahang CMD.46.2022 J4 stray `)` | left (label only) |
| 3-5 | Real rows dropped as prose: Pahang CMD.35.2020 J7 Terimaan Bukan Hasil 366.95/213.24, Kedah CMD.40.2021 J33 JUMLAH 1,207.19, Sabah `5. a) Pendahuluan Kenderaan` in 4 volumes | amount phrases (`RM200 juta`, `sebanyak RM`, `meningkat sejumlah`) now reject only a row whose figures repeat another row or that prints fewer figures than the table's fullest row; sentence markers (`Pada tahun 2020,`, `membelanjakan`, `di Jadual`, `8.3.3.`) stay unconditional; the original prose rule is back at 8 words. All restored. |
| 6, 7, 9 | Defect-entry wording (Sarawak J4.30 FY2014, Kedah flag too wide, Melaka impact) | corrected; Kedah split into J4.8 and J4.9 entries |
| 8 | Selangor CMD.49.2023 J13 claimed fixed but was not (the guard against digits blocked `Pemberian 50% Kos`) | guard now ignores percentages: J13's Concurrent List grant labelled and conformed FY2018-2022 |
| 10 | prose rows left (NS CMD.23.2024 J12, NS CMD.34.2019 J43, Pulau Pinang CMD.49.2022 J26, Perlis CMD.39.2017 J4.19) | partly cleared by the new markers; the rest unconformed |

After the fixes: checker 2,294 tables ok (2,248 at the first fix), no table worse except where the checker
cannot match a dropped prose copy whose real row remains; the only conformed rows removed are narrative copies
that carried a figure under the wrong year or line (Kedah CMD.40.2021 J25 FY2020 135.81 for 116.65, Melaka
CMD.32.2020 J4, Pahang CMD.55.2015 J4.19 and CMD.39.2016 J4.22, Perak CMD.36.2019 J5, Sarawak CMD.29.2024
J16) or duplicates of a row still present; `core/fact_observation.csv` is unchanged by this round.
