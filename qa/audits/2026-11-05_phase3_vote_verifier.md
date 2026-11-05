# Blind verifier pass: Phase 3 entity spine and vote spending (2026-11-05)

A separate agent with no access to `core/pipeline/`, `apps/tools/*.py` (beyond docstrings), the eval and
reproduction scripts or git history re-derived every `federal_gov.vote.*` row from L1 (PKKP
`fact_opex_maksud` / `fact_devex_maksud`, Anggaran `fact_anggaran_maksud_<year>`), checked the entity spine
against PKKP's printed names, reconciled the votes to the printed totals and attacked the tools.

**Result: 3,787 of 3,787 rows re-derived exactly** (value, value_printed, period, entity, breakdown, basis,
edition, page, L1 line, file sha256, vintage); no extra rows, no duplicate keys; P.63 FY2019-2020 blocks
loaded once. PKKP votes equal the printed totals every year except FY2009 development (source-documented).
Findings and what was done:

| # | Finding | Severity | Fixed by | Eval |
|---|---|---|---|---|
| H1 | The 2024 Anggaran book's B.33/P.33 is the lapsed KASA vote (printed `Kementerian Alam Sekitar dan Air**`, zero estimates, KASA's audited 2021-22 actuals to the ringgit) but resolved to its successor PETRA at the book's year | wrong body | `meta/entity_code.csv` gains a `scope` column: a row scoped to one source (`anggaran:2024`) wins for that source; KASA's rows scoped to the 2024 book | KASA 2021 actual from the 2024 book |
| H2 | B.64 is not printed in FY2019 but one bridge row covered 2015-2026 | identity | split 2015-2018 / 2020-2026, the second row's proof citing the analyst's lineage rule (FY2019 Higher Education folded into Education); `get_entity('B.64', 2019)` now answers not held | B.64 2019 |
| H3 | The 2024 and 2025 books print the 14 Tanggungan heads with no `mengurus` line: 112 rows missing, the books' opex short by exactly the printed Tanggungan total | missing data | a head with no mengurus line takes its JUMLAH (= emolumen + lain); every book-measure now equals its printed total | T.13 in the 2025 book |
| M1 | CV17 missing on 206 FY2015/FY2020 estimate rows from the same unarchived volumes | caveat | CV17 on every basis printed in a D24 volume | Health FY2015 estimate |
| M2 | P.47 FY2009 (our extraction of the JUMLAH suspected) served as reliability ok; CV21 said "kept as printed" | caveat | `reliability=low` for `ours_suspected`; CV21 states the three diagnoses and that a suspected figure is not to be used | P.47 reliability |
| M3 | Vote opex includes B.12's transfer to the Development Fund: opex votes + devex votes double count it | caveat | CV23 says so and names the totals to use | — |
| M4 | Growth across a change of scope under one entity passes with no warning (Education 2014-15, 2019-20) | caveat | new CV24 on every growth of one body's vote spending | Education 2014-15 |
| M5 | B.32 valid to 2025 only through zero reprints; `get_entity('B.32', 2024)` answered held | identity | unscoped B.32 ends 2022; the reprints are scoped rows | B.32 2024 |
| M6 | A body shows RM0 for years before it existed (budget-book reprints) | caveat | CV22 says a body created later can show 0 or its predecessor's amounts | — |
| L1 | `breakdown=None` crashed `get_series` | crash | defaults to `_total` | — |
| L2 | bad `basis`/`breakdown`, case variants answered "not held" with unrelated series | tool | case normalised; an unknown basis or breakdown is refused as invalid | basis in capitals |
| L3, L4, L6 | federal government as entity, `publisher='mof'` for budget books, and the silent omission of charged heads | tool | each answers with a pointer; vote rows without an entity carry a note | — |
| L5 | growth across bases refused with a publisher message | tool | separate basis message | original estimate -> audited |
| L7 | `MY-14` blamed vote coverage; `year=2020.0` garbled; `year=-1` accepted | tool | messages fixed; out-of-range years refused | — |
| L8 | `entity='B.15'` finds nothing for E000029's residual P.15 2021 row | by design | the B code names the body only while printed; the entity_id finds it (documented) | — |

Judgement calls kept as they are (the verifier agreed or flagged them as calls, not errors): B.15, B.26 and
B.33 split at their lapses (`proposed`, awaiting a person); B.11 and B.12 typed as votes under the Treasury;
the 2025 book's 2022 actuals printed under PETRA's name stay with PETRA (the book's own restatement, CV22).
