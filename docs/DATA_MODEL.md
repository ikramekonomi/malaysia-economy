# Data model: Malaysia Economy Data Warehouse

**Status: DRAFT for review. Nothing in this document has been built yet.**
It describes the target structure and how today's tables move into it.
Companion documents: `docs/DOCUMENT_REGISTRY.md` (every document the warehouse needs) and
`docs/registry/series_seed.csv` (the first registry rows).

---

## 1. What the model is for

| Who asks | Example question | What the model must give back |
|---|---|---|
| IKRAM analyst | "Which districts in Kelantan have the highest poverty, and how much federal development money reached them?" | one number per district, its source page, its caveats |
| AI agent | `get_series("poverty.absolute.incidence", geo="MY-03/district", period="2019..2024")` | typed rows, never free text, every row cited |
| Dashboard | the same rows, through views | nothing the agent can't also get |

**Design rule:** the warehouse answers questions about the *economy*. Public finance is one
theme of eight, not the frame. PKKP was the first document, not the centre.

---

## 2. Layers

```
L0  raw files       PDF / CSV / API dumps, sha256, never edited          sources/<src>/raw (gitignored) + registry
L1  source tables   one table per printed table, AS PRINTED               sources/<src>/data/*.csv   (unchanged; golden rule 1)
L2  core            6 dimensions + 3 facts, conformed codes               core.*
L3  gap views       named, documented comparisons                         gap.*
L4  apps            agent tools · dashboard · CSV/API                     reads L2/L3 only
──
qa.*    every check, anomaly, defect, restatement (separate from data)
meta.*  tables, columns, units, code lists, caveats, releases, decisions (stored as data)
```

Rules between layers:

* L1 stays exactly as it is today: the source of truth, per source, as printed.
* L2 is rebuilt from L1 by code, never edited by hand.
* L3 reads only L2. L4 reads only L2 and L3.
* No layer silently fixes a figure. A misprint stays as printed and gets a `qa.anomaly` row.

---

## 3. The 8 themes

| # | Theme | Anchor indicators | Deepest geography | Held today |
|---|---|---|---|---|
| 1 | People & poverty | poverty incidence, median household income, Gini, population | DUN | ◑ HIES held to DUN; state/district **population not held** |
| 2 | Jobs & wages | unemployment, labour participation, median wage, productivity | DUN (LFS) | ◑ LFS held; wages survey not held |
| 3 | Prices & cost of living | CPI by state, item prices, fuel prices | state | ◑ CPI held; item prices not held |
| 4 | Output & industry | GDP, state GDP, IPI, trade, investment | state | ● mostly held |
| 5 | Public finance & money trail | revenue, spending, budget vs actual, project spending, state finances | project / state | ● deepest; project place not yet resolved |
| 6 | Health, education & services | doctors per 1,000, school outcomes, access to amenities | district | ○ amenities only |
| 7 | Accountability | audit findings, opinions, PAC actions, procurement | entity | ◑ LKAN 2024–26 extracted |
| 8 | Money, credit & financial wellbeing | OPR, lending by purpose, household debt, insolvency | national | ◑ BNM held; household debt and insolvency not held |

● held · ◑ partial · ○ thin. Every indicator belongs to exactly one theme (`dim_indicator.theme`).

---

## 4. Dimensions (L2)

Every fact joins to these through **codes**. Names are attributes, never keys (golden rule 4).

### 4.1 `dim_geo`: where

| column | example | note |
|---|---|---|
| `geo_code` PK | `MY`, `MY-10`, `MY-10/dis:<dosm>@<vintage>`, `MY-10/par:P.094@2018`, `MY-10/dun:N.01@2018` | ISO 3166-2:MY for states; DOSM/SPR codes below state, **always with the boundary vintage** |
| `geo_level` | `country` · `state` · `district` · `parlimen` · `dun` · `strata` | enum |
| `parent_geo_code` | `MY-10` | strict tree within one `boundary_vintage` |
| `local_code` | `P.094` | the code as published, without the vintage |
| `name_bm`, `name_en` | Selangor | display only |
| `boundary_vintage` | `2018` (Peninsula re-delineation), `2015` (Sarawak DUN), `2019` (Sabah DUN) | the boundary set the area belongs to |
| `valid_from`, `valid_to` | | dates the boundary set was in force |

States and the country have no vintage suffix: their ISO codes are stable.

**Boundary rule: keep every boundary set as published, and link them with a concordance.**

* Parlimen, DUN and district boundaries change (re-delineation, new districts). `P.094` in
  one boundary set is not the same area as `P.094` in another, so the vintage is part of the key.
* Data is stored against the boundary set its publisher used. It is **never re-mapped silently**.
* `bridge_geo_concordance` links old areas to new ones:

  ```
  bridge_geo_concordance (from_geo_code, to_geo_code, weight, weight_basis, source_edition_id)
    weight_basis  area · population · polling_districts · exact (unchanged area)
  ```

* A figure moved onto another boundary set through the concordance is a new observation with
  `basis = derived` and `derived_from` pointing to the original. Both stay.
* Tools default to the boundary set in force for the requested period, so a DUN figure lines up
  with the representative elected on those boundaries.
* The concordance source (SPR delimitation reports, DOSM boundary files) is a registry series
  like any other.

State codes (ISO 3166-2:MY): 01 Johor · 02 Kedah · 03 Kelantan · 04 Melaka · 05 Negeri Sembilan ·
06 Pahang · 07 Pulau Pinang · 08 Perak · 09 Perlis · 10 Selangor · 11 Terengganu · 12 Sabah ·
13 Sarawak · 14 WP Kuala Lumpur · 15 WP Labuan · 16 WP Putrajaya.

`geo_code` = `_unallocated` exists on purpose. Money that cannot be placed is shown as
unplaced, never spread across states.

### 4.2 `dim_period`: when

One time convention replaces the seven used today (`year`, `fiscal_year`, `target_year`,
`year_dt`, `date`, `period`, `edition_year`).

| column | example |
|---|---|
| `period_code` PK | `2024` · `2024-Q1` · `2024-03` · `2024-03-15` |
| `freq` | `A` · `Q` · `M` · `D` |
| `period_start`, `period_end` | `2024-01-01`, `2024-12-31` |
| `year` | 2024 |

The federal fiscal year is the calendar year, so `FY2024` = `2024`.
An edition or release date is a **vintage**, not a period (§6).

### 4.3 `dim_indicator`: what is measured

| column | example | note |
|---|---|---|
| `indicator_code` PK | `poverty.absolute.incidence` · `fiscal.opex.net` · `cpi.headline` | dotted, lowercase, stable |
| `theme` | `1` | one of the 8 |
| `name_bm`, `name_en`, `definition` | | definition quotes the publisher |
| `unit` | `RM` · `percent` · `persons` · `index` | **units live here, never in column names** |
| `index_base` | `2010=100` | for indices |
| `price_basis` | `current` · `constant_2015` | a real and a nominal series are two indicators |
| `adjustment` | `nsa` · `sa` | the same applies to seasonally adjusted series |
| `measure_type` | `flow` · `stock` · `rate` · `index` | |
| `additive` | true / false | whether summing across geo or breakdown is valid |
| `series_rule` | `latest_vintage` · `own_volume` | which vintage forms the clean series (§6) |
| `parent_indicator` | `fiscal.opex` | for drill-down |

### 4.4 `dim_breakdown`: how it is split

Any split other than place and time: sex, age band, sector (MSIC), product (COICOP, SITC),
GFS economic or functional class, PKKP object class, urban/rural strata, ethnicity, income group.

```
dim_breakdown            (breakdown_key PK, label)              e.g. 'sex=F|age=15-24'
bridge_breakdown_member  (breakdown_key, axis, member_code)     axis ∈ meta.code_list
```

`breakdown_key = '_total'` means no split. Members come from published code lists
(`meta.code_list`: msic_2008, coicop, sitc, gfs_economic, cofog, pkkp_object, …),
never from labels typed by us.

### 4.5 `dim_entity`: who

Every body that spends, receives, audits or is audited. This is the spine of the money trail.

**Rule: every entity has a permanent opaque ID, and its readable codes are attributes with dates.**
Readable codes are not keys because Malaysia's codes move: vote codes are renumbered at cabinet
restructures, so `B.45` can name different ministries in different years, and codes get reused.

```
dim_entity           (entity_id PK, entity_type, name_bm, name_en, parent_entity_id, gfs_sector, seat_geo_code)
bridge_entity_code   (entity_id, code_system, code, valid_from, valid_to, proof)
meta.entity_register  committed CSV: every entity_id ever issued, with issue date and reason; never reused, never deleted
```

| column | example | note |
|---|---|---|
| `entity_id` PK | `E000123` | issued once from `meta.entity_register`; stable across rebuilds |
| `entity_type` | `government` · `ministry` · `programme` · `activity` · `project` · `statutory_body` · `glc` · `company` · `auditor` | enum |
| `name_bm`, `name_en` | | current name; past names in `bridge_entity_code` (`code_system = name`) |
| `parent_entity_id` | project → ministry → federal government | parent changes over time are dated in a bridge, not overwritten |
| `gfs_sector` | `central_gov` · `state_gov` · `local_gov` · `public_corp` · `private` | puts off-budget bodies in scope |
| `seat_geo_code` | `MY-16` | where it sits, which is **not** where its money goes |

`bridge_entity_code` holds every readable code with its validity (illustrative: `maksud` `B.45` valid 2020–2022),
`projek_code`, `ssm_no`, `ag_agency_code`, state government `MY-03`. Its rules:

* a code points to exactly one entity on any given date (enforced by the build);
* every link that is not the first appearance of a code carries a `proof`, the way
  `dim_maksud_canonical` proves each renumbering today;
* agent tools accept a readable code plus a date (`B.45`, 2024) and resolve it to the
  `entity_id`, so agents never need to see opaque IDs unless they want to.

Issuing IDs: a build that meets a code with no entity for that date stops and lists it. An ID
is issued only when a person (or a reviewed rule) decides whether it is a new body or a
renumbered old one. This is the one place where judgement is recorded, not computed.

A state *as a place* (`dim_geo MY-03`) and a state *as a government* (an entity with code `MY-03` in `code_system = state_gov`) are
different rows. Spending by Kelantan's government is not spending in Kelantan.

### 4.6 `dim_source`: from which document

The document registry (`docs/DOCUMENT_REGISTRY.md`) **is** this dimension:
`series → edition → file`. Facts point to `edition_id` + `file_id` + page.

---

## 5. Facts (L2)

Three fact tables. Each has one job.

| Fact | One row is | Holds |
|---|---|---|
| `fact_observation` | one number for indicator × geo × period × breakdown × entity × source × vintage | statistics, aggregates, fiscal totals, targets |
| `fact_money_flow` | one amount moving from entity A to entity B at a stage | spending, transfers, project allocations: the trail |
| `fact_record` | one thing with text: a finding, a project, a contract, a guarantee, a target | accountability and registers |

### 5.1 `fact_observation`

| column | type | note |
|---|---|---|
| `indicator_code` | FK | |
| `geo_code` | FK | |
| `period_code` | FK | |
| `breakdown_key` | FK | `_total` if none |
| `entity_id` | FK | `_none` if none (e.g. CPI) |
| `edition_id` | FK | the document edition it was printed in |
| `vintage` | date | release or edition date (§6) |
| `value` | double | in the indicator's base unit (RM, not RM juta) |
| `value_printed` | text | exactly as printed, e.g. `40,533` or `–` |
| `unit_printed` | text | `RM juta` |
| `basis` | enum | §7.1 |
| `status` | enum | §7.2 |
| `file_id`, `pdf_page`, `printed_page`, `table_ref` | | provenance (golden rule 3) |
| `l1_ref` | text | the L1 table and row it came from |
| `derived_from` | text[] | for `basis = derived` only: the observation keys it was computed from |

**Primary key:** (indicator, geo, period, breakdown, entity, edition, vintage).
Plan targets are observations with `basis = target`, so "target vs outcome" is one join.

### 5.2 `fact_money_flow`

| column | note |
|---|---|
| `flow_id` | |
| `from_entity_id`, `to_entity_id` | entity IDs; e.g. a ministry (maksud code) → its project (projek_code) → a contractor (SSM number) |
| `stage` | `announced` · `budgeted` · `revised` · `spent` · `received` (§7.3) |
| `period_code` | |
| `amount` | RM (unit in `meta.column`) |
| `economic_class` | code from `pkkp_object` or `gfs_economic` |
| `purpose` | COFOG code where known |
| `geo_code` | where the money lands; `_unallocated` if unknown |
| `geo_method` | `stated` · `parsed_name` · `agency_seat` · `none`, ordered strongest to weakest |
| `geo_confidence` | `high` · `medium` · `low` |
| `is_leaf` | sum only leaf rows (golden rule 5) |
| `basis`, `status`, `edition_id`, `file_id`, `pdf_page`, `printed_page`, `l1_ref` | as in 5.1 |

Revenue and economic aggregates are **not** flows. They are observations.
`fact_money_flow` is the trail of where public money goes.

### 5.3 `fact_record` + `bridge_link`

| column | note |
|---|---|
| `record_id` | |
| `record_type` | `audit_finding` · `audit_opinion` · `project` · `pfi_contract` · `guarantee` · `procurement_award` · `pac_recommendation` · `plan_target` |
| `entity_id`, `geo_code`, `period_code` | |
| `title_bm`, `text_bm` | as printed |
| `attributes` | JSON for type-specific fields (opinion type, contract value, tender method, …) |
| provenance columns | as in 5.1 |

```
bridge_link (from_kind, from_id, to_kind, to_id, link_type, link_method, confidence, proof)
  link_type   finding_about_project · pac_on_finding · response_to · award_for_project · target_funded_by
  link_method code_exact · name_matched_reviewed · manual
```

A link made by name matching must be reviewed, carry `confidence`, and cite its `proof`.
It is never presented as code-exact.

---

## 6. Vintages: keep everything, show "latest" as a view

* Every edition and every revision is kept: `fact_observation.vintage` and `edition_id`.
* `core.v_observation_clean` applies the indicator's `series_rule`:
  * `latest_vintage` for DOSM, BNM and other statistics: the newest release wins.
  * `own_volume` for fiscal actuals (golden rule 6): each year comes from the edition in which
    it is the newest actual. Today `curated/pipeline/mof_editions.py` does this. The same
    logic becomes a declared rule, not hidden code.
* `qa.restatement` lists every value that later vintages changed, so a series break is visible.

---

## 7. Controlled vocabularies

Stored in `meta.code_list`, enforced by the build: an unknown value fails the build.

### 7.1 `basis`: what kind of figure

| value | meaning | maps from today's |
|---|---|---|
| `audited` | certified by the Auditor-General | PKKP, state statements |
| `actual` | government's own outturn, not audited | `official_actual`, BNM fiscal |
| `budget_estimate` | tabled estimate | Anggaran, `official_projection` (budget year) |
| `revised_estimate` | estimate revised in-year | `official_revised` |
| `projection` | forecast | economic projections |
| `target` | a plan target | RMK, NIMP, NETR … |
| `statistic` | official statistic (survey or administrative) | DOSM, BNM non-fiscal |
| `derived` | computed by us from other observations | identities, per-capita |

### 7.2 `status`: how settled

`final` · `preliminary` (`official_preliminary`, DOSM "p") · `estimate` (DOSM "e") ·
`revised` · `provisional_ocr` (FY2015 PKKP leaf) · `nil` (printed `–`) · `not_printed`.

### 7.3 `stage`: where in the money trail

`announced` (budget speech) → `budgeted` (Anggaran tabled) → `revised` (supplementary) →
`spent` (PKKP) → `received` (recipient's own books, e.g. a state statement).
Whether a figure is audited is its `basis`, not a stage.

### 7.4 QA statuses (unchanged from today)

identity / cross_tier: `PASS` · `PASS_ROUNDING` · `FAIL` · cross_source: `AGREE` · `DIVERGE` ·
`SOURCE_ANOMALY` · `FOOTNOTED` · `DEFINITIONAL` · `UNCAPTURED` · `KNOWN_*` defect classes.

---

## 8. Naming rules

| Rule | Example |
|---|---|
| snake_case, English column names; Malay labels in `*_bm` | `name_bm` |
| prefixes: `dim_`, `fact_`, `bridge_`, `v_`, `gap_` | `gap_budget_vs_actual` |
| `*_code` = published code; `*_id` = warehouse id | `maksud_code`, `entity_id` |
| no units or scales in names | `value`, not `amount_rm_juta` |
| no cryptic source names in L2 | BNM `cb_alr_out_loa` stays in L1; L2 uses `rates.lending.average` |
| one time column: `period_code` | |
| one value column: `value` (observation) / `amount` (flow) | |

---

## 9. QA and metadata schemas

```
qa.check        check_id, check_type, table, key, expected, observed, diff, tolerance, status, note, proof_ref
qa.anomaly      the source misprinted it; kept as printed, with proof (golden rule 2)
qa.defect       our extraction is wrong or unproven
qa.restatement  a later vintage changed a value
qa.coverage     indicator × geo_level × period: held / gap / not_published

meta.table      purpose, grain, primary key, builder script
meta.column     description, unit, enum, nullable
meta.code_list  every controlled vocabulary and published classification
meta.caveat     known limits an answer must carry (e.g. FY2015 OCR leaf, FY2009 cash basis)
meta.release    what changed in each warehouse build
meta.decision   why the model is the way it is
```

The 171 underscore-prefixed QA CSVs (`_validation*`, `_source_anomalies*`, `_known_*`, …) stay in L1, where each
source writes them. `qa.*` is their union, with one schema.

---

## 10. Gap views (L3)

Each view is named, has a one-line question, a fixed grain and a documented method.

| View | Question | Grain |
|---|---|---|
| `gap_budget_vs_actual` | Was the money budgeted spent? | entity (ministry→programme→project) × year |
| `gap_revenue_estimate_vs_collected` | Did revenue come in as estimated? | revenue code × year |
| `gap_reported_vs_audited` | Do MOF, BNM and PKKP agree? | indicator × year |
| `gap_target_vs_outcome` | Was the plan target met? | target × indicator × geo × year |
| `gap_need_vs_money` | Does money follow need? | geo (state/district) × year: poverty, income vs federal flows per capita |
| `gap_federal_vs_state` | Do federal transfers match what states record receiving? | state × year |
| `gap_audit_recurrence` | Do the same bodies keep getting the same findings? | entity × finding type × year |
| `gap_obligations_growth` | Are off-budget obligations growing faster than debt? | instrument × year |

---

## 11. Agent access: typed tools first, SQL as escape hatch

| Tool | Input | Output |
|---|---|---|
| `find_indicator` | text, theme?, geo_level? | indicator codes with definition, unit, coverage |
| `get_series` | indicator, geo, period range, breakdown?, basis?, vintage=`clean` | rows + citations + caveats |
| `compare_geos` | indicator, geo_level, period | ranked rows with the national value |
| `follow_money` | entity or geo, period, stage? | flow tree to leaves, with `_unallocated` shown |
| `get_gap_view` | view name, filters | the view's rows + its method note |
| `explain` | any returned row | document, page, checks passed, anomalies, restatements |
| `list_documents` | theme?, status? | registry rows: what exists, what is held, what is missing |
| `run_sql` | read-only SQL | row-limited; same caveats attached |

**Contract:** a tool never returns a number without its citation (`edition_id`, page) and the
`meta.caveat` rows that apply. A missing document is an answer ("not held: see registry"),
not an empty result.

---

## 12. Follow the money: both directions

```
                    Track 0 — shared spine (stable entity_id for ministry → programme → activity → project)
                                          │
          ┌───────────────────────────────┴───────────────────────────────┐
  Track A — PLACE                                               Track B — RECIPIENT
  federal → state → district → parlimen/DUN                     ministry → agency → contractor
  "how much reached Kelantan's poorest districts?"              "who received it, and was it audited?"
```

| Track | Step | Needs | Held today |
|---|---|---|---|
| 0 | Stable project identity across years | canonical maksud + `projek_code`; proof per crosswalk | 14,890 project rows, 946 codes; 1,187 projects tracked 5+ years |
| 0 | Budgeted vs spent per project | development estimates book | **not held** (Anggaran held for operating only) |
| A | Place each project | stated location → parsed name → agency seat → `_unallocated` | only 103 of 809 FY2024 project names name a state |
| A | State-level receipts | state statements, state budgets | state statements 13 states FY2014–2024; state budgets not held |
| A | Need on the same map | HIES, LFS, population at district/parlimen/DUN | HIES/LFS held; **population below national not held** |
| B | Implementing agency | entity register, AG agency codes | sijil registers FY2023–24 |
| B | Contractor | procurement awards, company register | **not held** |
| B | Audit and follow-up | LKAN findings → PAC → response | findings 2024–26 (no ministry/project code yet); PAC not held |

Every placed or linked amount carries `geo_method`/`link_method`. Unplaced money is reported
as `_unallocated` with its total, so a map never looks more complete than the data is.

---

## 13. How today's tables map in

| Today (L1 / curated) | Goes to | As |
|---|---|---|
| `sources/pkkp` statements, opex leaf | `fact_observation` (totals), `fact_money_flow` (leaf, stage `spent`, basis `audited`) | |
| `sources/pkkp` Lampiran projects | `dim_entity` (projects) + `fact_money_flow` | Track 0 |
| `sources/anggaran`, `anggaran-hasil` | `fact_money_flow` stage `budgeted` / `fact_observation` (revenue) | |
| `sources/mof-fiscal-outlook` (9 editions) | `fact_observation`, one vintage per edition, `series_rule = own_volume` | |
| `sources/bnm` msb_* | `fact_observation`; cryptic columns → indicator codes via `meta` | |
| `sources/dosm` (~110 files) | `fact_observation` at country/state/district/parlimen/DUN | |
| `sources/states` | `fact_observation` (entity = state government) + `fact_money_flow` stage `received` | |
| `sources/audit-negara` findings, sijil, e-SelfAudit | `fact_record` + `bridge_link` | Track B |
| `curated/fact_obligations` | `fact_observation` (stocks) + `fact_record` (guarantees) | |
| `curated/fact_fiscal_headline` (wide) | becomes `v_fiscal_headline`, a view, so the site keeps working | |
| `curated/dim_maksud_canonical` | absorbed into `dim_entity` + `bridge_entity_code` (its proofs move with it) | |
| `curated/forecast/` | moves to `apps/models/`, outside the warehouse (§13.1) | |
| `curated/dashboard/` | retired after a feature-by-feature decision (§13.2) | |

### 13.1 `curated/forecast/` → `apps/models/`

Model output is an application on top of the warehouse, not warehouse data. It never enters
`core.*`. Its own supersession rule has fired: MOF's official figures (Tinjauan Fiskal
2019–2027, FY2025 actuals included) are now ingested.

| Piece | Goes to |
|---|---|
| `fact_utilisation_signatures` (actual ÷ original budget per vote) | folded into `gap_budget_vs_actual`: it is a gap measure, not a forecast |
| `fact_nowcast_2025` | kept in `apps/models/` and **scored once** against MOF's FY2025 actuals; the score is published with the method |
| `fact_projection_headline`, `fact_projection_detail`, `build_forecast2026` | kept in `apps/models/` as a cross-check on official projections only |
| `official_vs_model_2025_26`, `fact_gap_projection` | kept in `apps/models/`; re-run against the 2027 edition |

References in `sources/anggaran/README.md`, `sources/mof-fiscal-outlook/README.md` and
`curated/pipeline/build_planning_efficiency.py` are updated in the same PR.

### 13.2 `curated/dashboard/` → retired

It is the earlier single-file dashboard (PKKP only, FY2010–2024), superseded by `site/`.
`site/` reads neither folder. Before retiring it, each feature it has and the site lacks gets
an explicit decision:

| Feature | Decision |
|---|---|
| Pension reform simulator | port to the site as an app (a model, so it lives with `apps/models/`) |
| Refinancing wall / debt maturity | port: becomes a view over BNM and MOF debt observations |
| Debt vs the 60/65%-of-GDP ceiling | port: a `gap_*` view (target vs outcome, the ceiling as a `target`) |
| Peer benchmarks | **not ported as is.** `external_peers.csv` is typed in by hand and compares Malaysia's federal debt against other countries' general-government debt, which is not like for like. Returns only as a registry source (IMF WEO) with matched definitions |

Other dependencies:

| File | Change |
|---|---|
| `curated/dashboard/external_denominators.csv` | retired; GDP and population come from `fact_observation` |
| `sources/dosm/pipeline/build_denominators.py` | retired with it |
| `sources/dosm/pipeline/refresh.py` | drop the dashboard rebuild step |
| `sources/dosm/README.md` | references updated |

Git history keeps both folders in full.

---

## 14. Build order (once this spec is approved)

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | registry table + `meta` + code lists; move `curated/forecast/` to `apps/models/`; retire `curated/dashboard/` (§13) | every held file has a registry row with sha256; nothing outside L1–L3 sits in `curated/` |
| 1 | `dim_geo` (with boundary vintages + concordance), `dim_period`, `dim_indicator`, `dim_breakdown` | every DOSM/BNM file maps; no name joins left |
| 2 | `fact_observation` from DOSM, BNM, MOF | reproduces today's curated tables to the ringgit |
| 3 | `meta.entity_register` + `dim_entity` + `bridge_entity_code` + `fact_money_flow` from PKKP, Anggaran, states | every code resolves to one entity per date; project spine verified across years |
| 4 | `fact_record` + links from LKAN, sijil | findings carry entity IDs |
| 5 | typed agent tools + `gap_*` views; site reads views; ported dashboard features; FY2025 nowcast scored | every tool output cited |

Each phase: branch → reconcile to today's numbers → independent adversarial verifier → PR.

---

## 15. Decisions

| # | Decision | Why | Where |
|---|---|---|---|
| D1 | Fiscal is one of 8 themes; architecture is economy-wide | PKKP was the first document, not the centre | §1, §3 |
| D2 | ISO 3166-2:MY for states; DOSM/SPR codes below state | standard, published codes | §4.1 |
| D3 | Keep every vintage; "clean" is a view | revisions are evidence | §6 |
| D4 | Typed agent tools first; read-only SQL as escape hatch | every answer cited | §11 |
| D5 | Follow the money both ways: place (Track A) and recipient (Track B) | IKRAM works at national and state level | §12 |
| D6 | Permanent opaque `entity_id` + dated readable codes in `bridge_entity_code`; tools accept readable codes | vote codes are renumbered and reused | §4.5 |
| D7 | Keep every boundary set as published, with the vintage in `geo_code`; link by `bridge_geo_concordance`; re-mapped figures are `derived` | boundaries change; DUN data must match the representatives elected on them | §4.1 |
| D8 | `curated/forecast/` → `apps/models/`; FY2025 nowcast scored once against actuals | models are apps, not warehouse data | §13.1 |
| D9 | `curated/dashboard/` retired after porting the simulator, refinancing wall and debt ceiling; peer benchmarks only via a proper IMF WEO source | superseded by `site/`; peer table was not like for like | §13.2 |
