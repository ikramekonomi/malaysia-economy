# Curated gap views — Budget vs Actual

The first consolidated **gap view** in the warehouse: budgeted vs actual federal spending
per ministry vote (`maksud`), the highest-value comparison in `docs/SOURCES.md`.

## Status & scope

- **Pilot year: FY2024** (built; reconciled to the sen; independently verified). Structured
  to scale to FY2009–FY2024 — the builder takes a year list.
- **Grain:** one row per `year × flow × maksud`. Two flows: **Operating** (`Mengurus`) and
  **Development** (`Pembangunan`) — mirroring PKKP's own split.
- Output: [`fact_budget_vs_actual.csv`](fact_budget_vs_actual.csv). Validation:
  [`_validation_gap_2024.csv`](_validation_gap_2024.csv).

## ⚠️ What "budget" means here (read before using)

Source #2 — the **independent *Anggaran Perbelanjaan Persekutuan* budget book** — is **not
yet ingested**. Discovery found it is **not machine-readable** anywhere (data.gov.my hosts
only aggregate *actuals* by object/function; the Anggaran is published only as a PDF on
`belanjawan.mof.gov.my`), and in the current environment **every `.gov.my` host is blocked
by the network egress policy** (only GitHub is reachable), so the PDF could not be fetched.
See the repo PR / task notes for the discovery record.

Until the Anggaran lands, the **budget side is PKKP's OWN recorded appropriation** — the sum
each ministry was actually voted, as printed in the audited statements:

| Flow | Budget column (source) | Actual column (source) |
| --- | --- | --- |
| Operating (`Mengurus`) | `anggaran_asal_rm` = original estimate (Nota 5(b)); `anggaran_dipinda_rm` = revised, also carried | `sebenar_rm` (Nota 5(b)) |
| Development (`Pembangunan`) | `anggaran_jumlah_rm` = year estimate (Lampiran 2) | `sebenar_jumlah_rm` (Lampiran 2) |

So this pilot is budget-vs-actual **entirely within the audited source** — every figure
traces to one PKKP page. This is legitimate and useful (it answers "did each vote spend what
it was appropriated?"), but it is **not independent**: the budget is what the accounts record
as appropriated, not the Anggaran book as originally tabled. When the Anggaran is ingested it
(a) provides an independent budget and (b) becomes a **cross-check** against PKKP's recorded
`anggaran_asal` — a gap-finding target in its own right. The `budget_source` column already
namespaces every figure to its origin so both can coexist.

## Schema — `fact_budget_vs_actual.csv`

| column | meaning |
| --- | --- |
| `year` | fiscal year |
| `flow_bm` / `flow_en` | `Mengurus`/`Operating` or `Pembangunan`/`Development` |
| `jenis_bm` | operating only: `Tanggungan` (charged) / `Bekalan` (supply); empty for development |
| `maksud_code` | vote code — **join key**. `B.*`/`T.*` = operating, `P.*` = development |
| `code_num` | shared ministry number (join operating↔development for one ministry) |
| `maksud_name_bm` | ministry/vote name (Malay, canonical) |
| `budget_source` / `actual_source` | exact PKKP field each figure came from (provenance) |
| `budget_original_rm` | original budget (RM, sen exact) |
| `budget_revised_rm` | revised budget (operating only; empty for development) |
| `actual_rm` | actual expenditure (RM, sen exact) |
| `variance_rm` | `actual − budget_original` (positive = overspend) |
| `utilisation_pct` | `100 × actual / budget_original` (empty where budget = 0) |
| `variance_vs_revised_rm` | `actual − budget_revised` (operating only) |
| `source_file`, `pdf_page`, `printed_page`, `statement` | provenance back to the audited PDF |

**Join discipline** (CLAUDE.md): join on `maksud_code`, never names. The file is leaf grain —
no subtotal/grand-total rows — so it is safe to `SUM`. Printed totals are reconciled
separately in `_validation_gap_<year>.csv`.

## FY2024 result

| Flow | Budget (original) | Revised | Actual | Variance | Utilisation |
| --- | ---: | ---: | ---: | ---: | ---: |
| Operating (Nota 5(b), 53 votes, incl. statutory-fund transfer) | RM303.80b | RM307.28b | RM324.62b | **+RM20.82b** | 106.9% |
| Development (Lampiran 2, 31 ministries) | RM85.15b | — | RM84.01b | −RM1.14b | 98.7% |

**Presentation nuance (documented, not corrected):** the operating actual here (RM324.62b,
sum of the 53 votes in Nota 5(b)) **includes** the RM3.1b transfer to statutory funds
(vote B.12); the *financial-performance* headline operating figure is RM321.51b, which
**excludes** it. Both are faithful to the source — B.12 is the reconciling item.

Largest operating overspends vs original budget: **B.11** Perkhidmatan Am Perbendaharaan
(+RM12.47b, 126%, carries subsidies/refunds), **B.12** Kumpulan Wang Terkanun (+RM3.11b,
288%), **B.63** Pendidikan (+RM1.76b), **T.14** Pencen/pensions (+RM1.62b). Development is
almost fully utilised except **P.70** Simpanan Luar Jangka (RM2b contingency reserve, 0
spent) and **P.10** Perbendaharaan development (+RM1.86b, 115%, the only devex overspend).

## Validation

Two layers, matching PKKP's discipline:
1. **Reconciliation** (`_validation_gap_2024.csv`): the curated sums are checked back to the
   volume's own printed totals — operating actual & budget = Nota 5(b) totals (53 votes),
   development actual & budget = Lampiran 2 grand total, plus the `variance = actual − budget`
   identity on every row. **6/6 PASS** to the sen.
2. **Independent adversarial verifier**: a separate agent, blind to the builder, re-derived
   the figures from the raw PKKP CSVs and compared — see the PR/task notes for the verdict.

## Rebuild / scale

```
python3 curated/pipeline/build_gap_views.py          # pilot FY2024 (default)
python3 curated/pipeline/build_gap_views.py 2024 2023 2022   # more years, once spot-checked
```
Source of truth = the PKKP CSVs (never the `.duckdb`). Each year is taken from its own
volume for a clean series.

## Next

- Ingest source #2 (**Anggaran Perbelanjaan**) under `sources/anggaran/` once source access
  is arranged (allow `belanjawan.mof.gov.my` in the egress policy, or supply the PDF), then
  add `budget_source='anggaran:...'` rows and an Anggaran-vs-PKKP-`anggaran_asal` cross-check.
- Extend to program / object grain (PKKP `fact_opex_detail` supports it) for finer variance.
- Scale the pilot across FY2009–FY2024.


## Planning efficiency, FY2010-FY2024 (`fact_planning_efficiency.csv`)

Original budget vs actual for every audited year (build:
`curated/pipeline/build_planning_efficiency.py`). The ingested budget books prove the
baseline: **the tabled Budget 2024 equals PKKP's recorded original OE appropriation
exactly, vote for vote** (and AP2024's asal-2023 column equals PKKP's 2023 record;
AP2025/AP2026 confirm 2024/2025) - so PKKP's `anggaran_asal` doubles as the budget as
tabled, and the audited series measures true planning accuracy.

Headlines: total utilisation ran 108-110% in 2010-2012, tightened to ~100+/-3% in
2013-2021 (COVID 2020: 94%), then blew out to **121% in 2022** (subsidy surge),
107% (2023), 105% (2024). Operating spend chronically exceeds plan; development spend
mostly underspends its appropriation.

**Documented gap - development votes:** the tabled DE 2024 (RM92.0b incl the RM2.0b
P.70 reserve) does not equal PKKP's recorded original DE appropriation (RM85.15b).
Beyond the reserve, the difference decomposes into post-tabling machinery-of-government
restructuring: P.33 (re-created Energy Transition ministry, tabled 0) records RM3.76b
and P.50 (Digital, created 2024) RM1.03b, absorbed from P.23 (-RM4.78b), P.06
(-RM1.53b), P.62/P.15/P.47 and others. OE shows no such gap. Recorded per-vote
evidence, not interpretation; cause-tracing at program grain is the follow-up.
