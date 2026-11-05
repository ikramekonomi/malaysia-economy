# Blind verifier pass: state parser re-extraction (2026-11-05)

A parser change (`sources/states/pipeline/lkan_state_parser.py`) re-extracted all 13 states' audited
volumes (143 PDFs). A separate agent with no access to `sources/states/pipeline/` checked every changed
canonical row against `pdftotext -layout` of its original page (31 pages). Verdicts, row by row:
`2026-11-05_state_parser_verdicts.csv`.

**Result: 154 changed rows checked, 0 wrong amounts, 0 wrong years.**

| Verdict | Rows | Meaning |
|---|---|---|
| CORRECT | 89 | 82 new rows and 7 changed values. All 7 old values were wrong: a `(%)` share (100.0) read as an amount, or a value shifted one year (Perlis CMD.41.2016 J4.27 2012-13, Selangor CMD.41.2019 J11 2015-16 and CMD.50.2021 J13 2017-18, Sarawak CMD.48.2023 J7 2020). |
| RELABELLED | 34 | Same value, label corrected (22: Sarawak CMD.60.2015 J4.11, Kedah CMD.50.2015 J4.13) or one polluted label swapped for another (12). |
| WRONG_LABEL | 22 | Value and year right, label not the printed one. Pre-existing label stitching (the same labels are on main for the other years of each line); recorded in `state_config.KNOWN_EXTRACTION_DEFECTS` (labels entry). |
| NOT_ON_PAGE | 5 | Nil (`-`) phantom rows made from footer words and page numbers; pre-existing, relabelled. Recorded in the same entry. |
| SUPERSEDED | 4 | Printed rows demoted to `is_canonical=no` because the same item, year and value is now canonical from the sibling table on the same page (Melaka CMD.33.2019 J16/J17, Kedah CMD.50.2015 J4.13/J4.14). Nothing deleted. |

Rows changed after the list was drawn (the Negeri Sembilan fixes: banner `JUMLAH HASIL RM...` kept under
an unconformed code, CMD.37.2018 J4.10 JUMLAH 2017 = 367.27; Kedah CMD.34.2016 J4.13 2015 = 281.84;
Pahang CMD.55.2015 J4.10 2013-14 = 541.85 / 455.57) were checked against their pages by the author.

**Effect:** state FAIL rows 29 -> 16 (every `V1_penyumbang_utama_total` and the Sarawak 2020-21 balance
checks now PASS), `qa/known_fails.csv` 39 -> 26, known extraction defects 13 -> 7. Core values: 0 changed
(only `l1_ref` row numbers moved); the gap view: only `release_id`.

**Raised and answered:** CMD.49.2023 and CMD.52.2022 pages carry a `RAHSIA` stamp. Both files are the
tabled Command Papers downloaded from parlimen.gov.my (`meta/registry_file.csv`), i.e. published documents.
