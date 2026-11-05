# Blind verifier pass: gap_federal_vs_state (2026-11-05)

A separate agent with no access to the view's code (beyond its declared Method header), the state pipeline, the
tool code or the eval scripts re-derived `core/gap_federal_vs_state.csv` from the declared method, checked every
state figure on the printed page, searched every state report for printings the view missed, and attacked the tool.

**Result: 418 of 418 rows re-derived exactly** (status, federal and state amounts, shares, the `_states` sums and
tests; flow ids are the right lines and years and agree with PKKP L1). **59 of 59 state figures right** on the page
(own-year column, right grant). The view followed its method; the findings were about its inputs and wording.

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | Sarawak's all-federal-grants line missed in 7 volumes (FY2014-15, 2017-19, 2021-22) | high | the revenue-category spec now reads `KUTIPAN / PUNGUTAN HASIL NEGERI ...`; a line opening with a connective (`Dan Bayaran Balik`) or after one continues the row above. All 7 now held (and Sarawak's tax, non-tax and non-revenue receipts for those years: 21 new core observations, page-checked) |
| 2-3 | Concurrent List (6) and capitation (5) printings missed | high | Melaka FY2014-15: wrapped label fixed (a line above a row is that row's only if the row also wraps below, or opens a sub-item). Terengganu FY2018-22 and Kedah FY2017: the tables are registered as not parsed (multi-tier headers): status `state_table_not_extracted` now says so instead of `state_not_printed`. Kedah FY2020 capitation (second page of the table): a page-proved note |
| 4 | CV26 said 'five largest revenue items' only | medium | reworded: also significant-change tables (not extracted), and later columns found misaligned |
| 5 | `_states` sums under-count | medium | follows from 1-3; FY2015 aggregate rows now count the states that print it |
| 6 | Kedah FY2020: the later report's 2020 column is shifted one row (31.74 is Caruman Pinjaman) | medium | page-proved note in `meta/gap_note.csv` (both pages cited); the own report's 37.51 is used |
| 7 | Sabah FY2020: the later report's 2020 column misaligned | low-med | a figure printed only in a later volume is now listed but never compared (`printed_in_later_volume_only`); note in `meta/gap_note.csv` |
| 8 | `state_not_printed` rows that list later printings | medium | the new status (11 rows) |
| 9 | Printing lists incomplete | low | partly closed by 1-3; the rest follow the extraction |
| 10 | Kelantan FY2021 includes a catch-up for MoF's 2019-20 miscalculation | low | note in `meta/gap_note.csv` |
| 11 | Relabels: 16 of 24 right; Selangor CMD.52.2022 J61 ageing-table total read as receivables | low | ageing tables (`MENGIKUT TEMPOH TUNGGAKAN`) excluded; section captions and bare caption rows (`HASIL`) never take a wrapped line |
| 12 | Tool: transfer case-sensitive; FT named message | low | normalised; message points the territories to get_flows |

While fixing 1-3 the label changes were re-checked against main: no conformed row lost except wrong ones (the
`Bekalan Aset` rows coded `opex_supply` in Pahang CMD.39.2016 J4.17 and Perak CMD.56.2015 J4.16, a prose figure in
Negeri Sembilan CMD.54.2015 J4.19, the J61 ageing bucket); one regression found and fixed before commit (Sarawak
CMD.43.2018 J4.6: a group heading attached to the row above made 91.23 `investment_trust_funds`). Page-blind
checker: 2,307 tables ok (2,294 before), none worse. Not verified: Kelantan FY2022 (CMD.40.2023, image-only).

## Second blind pass (on the fixes) and what was done

29 new core observations, all right on the page (every Sarawak year's four categories add up to its printed
Jumlah); every national-panel change right; 62 label groups judged: 50 better, 5 same, 7 worse; checker no table
worse; `_states` rows, all four `meta/gap_note.csv` notes and the tool's transfer handling right.

| # | Finding | Done |
|---|---|---|
| 1 | Kedah FY2017 Concurrent List 35.38 printed in its own volume, unconformed (label lost its first line) | the rule also reads `Membiayai Separuh Kos ... Senarai Bersama`; now a `share` row, the 2017 sum counts 2 states |
| 2 | Melaka FY2015 capitation 15.25 still welded (`Projek Persekutuan Pemberian Hitung Kepala`) | a line below a row is that row's wrap only if the next row prints its own name; now conformed |
| 3 | 21 `state_table_not_extracted` rows cited a category table that cannot print these grants; Johor 2014 has extracted top-revenue tables | a class grant counts only an unparsed top-revenue table (a named grant also the category table), and only when no table of that kind was extracted for the year |
| 4 | Kelantan FY2022 (whole volume unparsed, image-only) said `state_not_printed` | now `state_table_not_extracted` citing the volume |
| 5 | Perlis: two prose figures coded `devfund_payments` | a label ending in `RM` (an amount cut off) is prose, unless it is a printed JUMLAH; also removes a prose 21.03 that was Kelantan's FY2020 `devfund_payments` in the national panel (the table prints 198.48 under `Pembayaran`, unconformed) |
| 6-9 | label-only residue (group headings on the row above in NS CMD.43.2021 J5, Selangor CMD.41.2019 J26 / CMD.52.2022 J29, Sabah CMD.48.2021 J71; Sarawak five-year tables' three-line label; Pahang CMD.39.2016 J4.39, Sabah CMD.59.2015 J4.31) | left: unconformed codes, labels only |

After: checker 2,339 tables ok (2,307), BAD 199 (231), none worse; conformed rows lost only the three prose figures.
