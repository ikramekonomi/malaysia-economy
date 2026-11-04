# Blind verifier pass: Phase 2 core (2026-11-04)

A separate agent with no access to `core/pipeline/`, `apps/tools/*.py`, the eval and reproduction scripts,
`curated/pipeline/` or git history re-derived core from L1 and attacked the tools as a black box.

**Scope:** small areas (districts, parlimen, DUN), income distributions (HIES percentile groups), national
accounts (GDP income approach), federal totals by publisher (PKKP, BNM MSB 3.1, MOF Tinjauan Fiskal).

**Result: 55,327 rows re-derived from L1 (every row in scope, not a sample): 0 wrong numbers.**
446 tool round-trips: 0 mismatches. 6,156 `get_distribution` thresholds against an independent DIST1
implementation: 0 wrong answers, 87 crashes.

| # | Finding | Severity | Fixed by | Eval |
|---|---|---|---|---|
| G1 | DOSM rows registered at L1 as broken (Kedah seats copied, Johor DUN 2023, Telang Usan 293%) served with no flag | guard bypass (most important) | `core/obs_flag.csv` + caveat CV15 + `source_flags`; `explain` lists `anomalies` | Kedah N.03, Telang Usan ×2 |
| G2 | `get_distribution` crashed above the 99th cut-off | tool failure | group 100 has no published maximum: bracket [99, 100] | MY 2022 RM37,583; Perlis RM10m |
| G3 | `derive('growth')` mixed publishers | guard bypass | refused unless same publisher and basis (DV3) | BNM 2021 → PKKP 2022 |
| G4 | `compare_geos` banded districts (population) | guard bypass | refuses every level below state | districts by population |
| G5 | negative thresholds accepted | tool failure | refused (not a positive amount) | RM -5 |
| G6 | list and dict inputs crashed | tool failure | every tool refuses non-code inputs | list geo |
| M1 | PKKP development spending cites no volume or page | citation | caveat CV16 states it; Phase 3 cites the volume | PKKP opex CV16 |
| M2 | PKKP operating spending FY2009–2023 cited to the next year's volume | citation | checked: same amount as the own volume to the ringgit (FY2009 own volume prints .47 sen); stated in CV16; Phase 3 | — |
| M3 | `per_employed` accepted any RM numerator with the CV14 wage caveat | wrong caveat | numerator restricted to compensation of employees (DV6) | GDP per employed |
| C1 | PKKP revenue not in core | coverage | loaded | 3 publishers for 2022 revenue |
| C2 | district Gini differs between two DOSM files (2 cells) | coverage | check C11 (INFO) | — |
| C3 | MOF COVID-19 Fund 2018–2019, BNM `ov_sur_def` not loaded | coverage | by rule (own-volume edition has no line); stated in core/README | — |
| D1–D5 | README years, "never bands a district", PKKP revenue, C10 count; GE14 seat count in the boundary proof | doc claims | corrected | — |

Cosmetic, also fixed: CV1 wording ("two places or two years"); `geo_level` and `publisher` case-insensitive;
`percentile=50` padded to `percentile=050`; `get_distribution` accepts only `hh_income` / `hh_income.gross`.
Not changed: BNM `value_printed` kept as the API's string (it is what was published); DOSM edition date
from the storage timestamp (documented in `core/pipeline/build_core.py:dosm_editions`).

Evals after the fixes: 120 of 120. Suite: PASS (65 known FAIL rows, none new).
