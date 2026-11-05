# Blind verifier: gap_target_vs_outcome and sources/rmk (2026-11-06)

A separate agent was given the declared method (the docstring) and `sources/rmk/README.md`, not the extraction or
build code. It re-extracted the cited RMKe-12 pages (text and page images) and re-derived core and the view.

**What matched:**
- all 1,070 L1 cells (all 15 Jadual 5 sections parsed in full, Jadual 10 and 14 against the rendered pages);
- all 41 core targets, including scaling, pages and file sha;
- all 41 view rows.

**Concepts:**
- the plan's opex is opex before the transfer to the Development Fund;
- the overall balance is MOF's identity;
- state GDP is the same basis as DOSM's (import duties included, Supra excluded);
- the labour force, unemployment and participation rate are the same age 15-64 universe.

| # | finding | severity | outcome |
|---|---|---|---|
| 1 | The labour rows cross DOSM's 2025 LFS re-benchmarking (a registered break) with no caveat | high | CV10 on every labour row; the plan's 2020 base is beside DOSM's revised 2020 |
| 2 | The plan footnotes its employment total as from the labour productivity publication, not the LFS | medium | footnote kept as data at L1; a note says it is read as a different concept |
| 3 | Jadual 14's printed growth rates do not reconcile with its levels | medium | new check V6 (11 WARN, kept as printed) |
| 4 | The scale-free fiscal target (-3.5 to -3.0% of GDP) and the current balance were not compared | medium | MOF's pct-of-GDP and current balance loaded into core; the range is held as two bounds; outcome -3.7%, below the range |
| 5 | KL's growth was left uncomputed, but DOSM's MY-14 for 2015-2018 equals the plan's "KL including Putrajaya" | medium | computed on that proof, which is re-checked every run (T7): 5.15% a year against 4.2%. That DOSM's MY-14 before 2023 includes Putrajaya is noted for core (not yet flagged on DOSM's rows) |
| 6 | The federal nominal rows lacked the %-of-GDP context | low-medium | a note on each row; the %-of-GDP row added |
| 7 | The 2023 mid-term review targets are not mentioned | low-medium | a note on every row |
| 8 | precision_printed was in printed units | low | base units (RM juta 1000000, '000 100) |
| 9 | The per-capita "current prices" note was dropped | low | kept as a footnote, unit "RM (harga semasa)" |
| 10 | The footnote marker was left in "WP Kuala Lumpur1" | low | stripped; the footnote text is held in the `footnote` column |
| 11 | CV7 (DOSM's Supra caveat) was on the plan's targets | low | CV7 now only on DOSM's own rows |
| 12 | T5 omitted the growth targets that are not compared | low | T5 lists them |

Noticed outside this piece: DOSM's `gdp.real` MY-14 rows for 2015-2022 include Putrajaya while those from 2023 do
not. This is a scope change inside one series and should become a flag on the DOSM rows (open).
