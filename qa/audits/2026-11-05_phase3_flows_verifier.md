# Blind verifier pass: Phase 3.4 money flows (2026-11-05)

A separate agent with no access to `core/pipeline/build_flows.py`, `core/pipeline/warehouse.py`,
`apps/tools/*.py` (beyond the `get_flows` docstring), the eval generator or git history re-derived every flow
from PKKP's operating detail (`sources/pkkp/data/<year>/fact_opex_detail.csv`, T.12 programme 010000) and
attacked `get_flows`.

**Result: 140 of 140 flows re-derived exactly** (amount, recipient argued from each year's printed name, geo,
L1 line, page, own-volume edition); each year equals the printed programme total to the sen; no activity
missing or double counted; every activity has exactly one object line equal to its JUMLAH. The FY2009 skip
(only the programme tier is printed) and the FY2015 skip (OCR-shifted codes, a local-authority JUMLAH of
RM22,070.22 against a leaf of RM302 million, activity JUMLAHs RM1.16 billion short of the programme line)
are justified: FY2015 cannot be loaded without re-reading the pages. T.12's other programmes hold no money
to the states.

| # | Finding | Severity | Fixed by | Eval |
|---|---|---|---|---|
| D1 | A state's `flows` held only its named grants, with no answer text: summing them understates what it received; nothing said the B.11 grants (RM240m a year of petroleum duty payments to Sabah and Sarawak, Concurrent List grants RM349-859m) are not loaded | medium-high | every state answer says not to add up `flows`; `coverage` names what is held and what is not (B.11, development grants); CV25 says the flows are a floor | 3 evals |
| D2 | periods compared as text: `2020Q1`, `2020-01-01`, reversed ranges returned wrong or empty answers | medium | whole years only; a reversed range is refused | `2020Q1` |
| D3 | `frm` ignored for the class grants and a false "no grant by name" when `frm` excluded them | medium | `frm` filters both lists; the answer is built from what is returned | — |
| D4 | a range spanning FY2015 hid the gap | medium | `years_not_held` in every answer | Sabah 2014-16 |
| D5 | the Federal Territories got "unknown recipient" | medium-low | they get an answer: no state government, no T.12 grant, their grants are under B.11 (not loaded) | Kuala Lumpur 2024 |
| D6 | the local-authority grant was missing from a state's class grants | medium-low | `not_split_by_state` includes both class recipients | Johor 2020 (6) |
| D7 | FY2020 flows have no file sha256 (the volume is not archived, D24) | low-medium | each flow carries CV17 where its volume is not archived | — |
| D8 | odd error messages for non-string recipients | low | explicit message listing the valid codes | — |
| C | Kedah's purpose dated the RM10.01m payment to FY2020 (it is FY2019); "(printed: ...)" was the rule's normalised name | low | purpose corrected; each flow quotes the year's own printed name | — |

Kept as is: 010400 (one-way roads on tourist islands) stays a class grant (the name gives no state; noted in its
purpose). The B.11 grants to states and the Federal Territories (activity codes renumber from year to year, so a
rule must be year-aware) are the next slice.
