# Data model: Malaysia Economy Data Warehouse

**Status: agreed design, revision 2 (2026-11-04).** Most of it is not built yet; §15 is the
order. Revision 2 folds in two independent checks: a blind-spot review of this plan, and a
check of whether the model could carry a full household-wellbeing report. §17 maps every
finding to the section that answers it.
Companion documents: `docs/DOCUMENT_REGISTRY.md`, `docs/registry/series_seed.csv`,
`docs/SOURCES.md`.

---

## 1. What the model is for

| Who asks | Example question | What the model must give back |
|---|---|---|
| IKRAM analyst | "Which districts in Kelantan have the highest poverty, and how much federal development money reached them?" | one number per district, its uncertainty, its source page, its caveats, and how much money could not be placed |
| AI agent | `get_series("poverty.absolute.incidence", geo="MY-03/district", period="2019..2024")` | typed rows, never free text, every row cited |
| Dashboard | the same rows, through views | nothing the agent can't also get |

**Design rule:** the warehouse answers questions about the *economy*. Public finance is one
theme of nine, not the frame. PKKP was the first document, not the centre.

**Design rule:** no question is built in. Every number has the same shape (indicator × place ×
period × breakdown × entity × source), so any question that combines them can be answered,
across themes, including questions nobody has asked yet. Example questions in the docs illustrate;
they never limit. A question the data cannot answer yet is logged (`meta.question_log`) and
triaged by a person (§10).

**Design rule:** a number IKRAM publishes must survive a hostile reader. So every answer carries
its uncertainty, its comparability limits and its source. A number that cannot carry them is not
returned (§11).

---

## 2. Layers

```
L0  raw files       PDF / CSV / API dumps, sha256, never edited          object store keyed by sha256 + public archive copy
L1  source tables   one table per printed table, AS PRINTED               sources/<src>/data/*.csv   (golden rule 1)
L2  core            6 dimensions + 3 facts, conformed codes               core.*
L3  gap views       named, documented comparisons                         gap.*
L4  apps            agent tools · dashboard · CSV/API · models            reads L2/L3 only
──
qa.*    every check, anomaly, defect, restatement, evaluation (separate from data)
meta.*  tables, columns, units, code lists, caveats, releases, decisions, licences (stored as data)
```

Rules between layers:

* L1 stays exactly as it is today: the source of truth, per source, as printed.
* L2 is rebuilt from L1 by code, never edited by hand.
* L3 reads only L2. L4 reads only L2 and L3. Models (`apps/models/`) are L4 and never feed L2.
* No layer silently fixes a figure. A misprint stays as printed and gets a `qa.anomaly` row.

**L0 must outlive its publisher.** Government links break. Every raw file is kept by its sha256
in object storage the project controls (gitignored locally, never only on a laptop). Where its
licence allows, it is also submitted to the Internet Archive, and the registry records the
`archive_url`. A third party can then re-derive any number even after the original page is gone.

---

## 3. The 9 themes

| # | Theme | Anchor indicators | Deepest geography | Held today |
|---|---|---|---|---|
| 1 | People & poverty | poverty, household income (mean, median, distribution), Gini, population, household composition | DUN | ◑ HIES to DUN; **population below national not held**; HIS/HES report tables not held |
| 2 | Jobs & wages | unemployment, participation, underemployment, median wage, productivity | DUN (LFS) | ◑ LFS held; wages survey not held |
| 3 | Prices & cost of living | CPI by state and household group, item prices, housing affordability | state | ◑ CPI held; item prices, house prices not held |
| 4 | Output & industry | GDP, state GDP, IPI, trade, investment, establishments | state | ● mostly held |
| 5 | Public money & money trail | revenue, spending, budget vs actual, transfers, project spending, state finances, social transfers | project / state | ● deepest; most spending not yet placed by area (§13) |
| 6 | Health, education & services | health outcomes (NHMS), doctors and beds, school outcomes, housing, water, transport, ICT | district | ○ amenities only |
| 7 | Accountability | audit findings, opinions, PAC actions, procurement, budget transparency | entity | ◑ LKAN 2024–26 extracted |
| 8 | Money, credit & financial wellbeing | OPR, lending, household debt, savings, insolvency | national | ◑ BNM held; household debt and insolvency not held |
| 9 | Environment, climate & disasters | floods and disaster spending, emissions, energy mix, climate exposure | district | ○ nothing held |

● held · ◑ partial · ○ thin.

Each indicator has **one primary theme** (`dim_indicator.theme`) and may list secondary themes
(`dim_indicator.themes_also`). The registry's `2;8` values follow the same rule: the first is
primary.

---

## 4. Dimensions (L2)

Every fact joins to these through **codes**. Names are attributes, never keys (golden rule 4).

### 4.1 `dim_geo`: where

| column | example | note |
|---|---|---|
| `geo_code` PK | `MY`, `MY-10`, `MY-10/dis:<dosm>@<vintage>`, `MY-10/par:P.094@2018`, `MY-10/dun:N.01@2018`, `ISO:SG` | ISO 3166-2:MY for states; DOSM/SPR codes below state, **always with the boundary vintage**; ISO 3166-1 for other countries |
| `geo_level` | `country` · `state` · `bahagian` · `district` · `mukim` · `pbt` · `parlimen` · `dun` · `foreign_country` | enum; urban/rural is **not** a geo level (it is a breakdown, §4.4) |
| `local_code` | `P.094` | the code as published, without the vintage |
| `name_bm`, `name_en` | Selangor | display only |
| `boundary_vintage` | `2018` (Peninsula re-delineation), `2015` (Sarawak DUN), `2019` (Sabah DUN) | the boundary set the area belongs to |
| `boundary_vintage_proof` | `stated` or the evidence used to infer it | DOSM constituency files print a label (`P.001 Padang Besar`) but not the boundary set; an inferred vintage must cite its evidence |
| `valid_from`, `valid_to` | | dates the boundary set was in force |

**Areas sit in several hierarchies, not one tree.** DUN ⊂ parlimen ⊂ state, but districts are a
separate split of the state, and parlimen do not nest in districts. Sabah and Sarawak have
*bahagian* between state and district. Local authorities (PBT) follow neither. The Federal
Territories have no DUN.

```
geo_hierarchy (hierarchy, child_geo_code, parent_geo_code)
  hierarchy  electoral (dun → parlimen → state) · administrative (mukim → district → [bahagian] → state)
             · local_government (pbt → state)
```

A rollup names its hierarchy. Nothing assumes a district can be summed into a parlimen.

**Boundary rule: keep every boundary set as published.** Parlimen, DUN and district boundaries
change (new districts are created between survey rounds). `P.094` in one boundary set is not the same area as `P.094` in another, so the vintage is
part of the key. Data is stored against the boundary set its publisher used and is **never
re-mapped silently**. Re-mapping across boundary sets (`bridge_geo_concordance`) is built only
when a concrete question needs it. Its output is `basis = derived` and the original stays.

State codes (ISO 3166-2:MY): 01 Johor · 02 Kedah · 03 Kelantan · 04 Melaka · 05 Negeri Sembilan ·
06 Pahang · 07 Pulau Pinang · 08 Perak · 09 Perlis · 10 Selangor · 11 Terengganu · 12 Sabah ·
13 Sarawak · 14 WP Kuala Lumpur · 15 WP Labuan · 16 WP Putrajaya.

`geo_code = _unallocated` exists on purpose. Money that cannot be placed is shown as unplaced,
never spread across states.

### 4.2 `dim_period`: when

One time convention replaces the seven used today (`year`, `fiscal_year`, `target_year`,
`year_dt`, `date`, `period`, `edition_year`).

| column | example |
|---|---|
| `period_code` PK | `2024` · `2024-Q1` · `2024-03` · `2024-03-15` · `FY2024-03` (a year ending March 2024) |
| `freq` | `A` · `Q` · `M` · `D` · `FY` |
| `period_start`, `period_end` | `2024-01-01`, `2024-12-31` |
| `year` | 2024 |

Federal and state governments use the calendar year, so `FY2024` = `2024`. Bodies with other
financial years (many GLCs and GLICs) use `FY<yyyy>-<mm>` with real start and end dates, so a
comparison never silently mixes year-ends. An edition or release date is a **vintage**, not a
period (§6).

### 4.3 `dim_indicator`: what is measured

| column | example | note |
|---|---|---|
| `indicator_code` PK | `hh_income.gross.median` · `fiscal.opex.net` · `cpi.headline` | dotted, lowercase, stable |
| `theme`, `themes_also` | `1`, `[8]` | primary + secondary (§3) |
| `name_bm`, `name_en`, `definition` | | definition quotes the publisher |
| `statistic` | `total` · `mean` · `median` · `share` · `rate` · `index` · `percentile_value` · `min` · `max` | what kind of number it is |
| `universe` | `households` · `persons` · `persons_15_64` · `adults_18_plus` · `children_5_15` · `establishments` | who or what it is counted over |
| `unit` | `RM` · `percent` · `persons` · `index` | **units live here, never in column names** |
| `index_base` | `2010=100` | for indices |
| `price_basis` | `current` · `constant_2015` | a real and a nominal series are two indicators |
| `adjustment` | `nsa` · `sa` | |
| `measure_type` | `flow` · `stock` · `rate` · `index` | |
| `additive_geo`, `additive_breakdown` | true / false each | summing across places and summing across groups are different questions (a median is neither) |
| `series_rule` | `latest_vintage` · `own_volume` | which vintage forms the clean series (§6) |
| `parent_indicator` | `fiscal.opex` | for drill-down |

**Composite indices** (the Malaysian Well-Being Index, a happiness index, any index IKRAM
builds) store their **components as their own indicators**. The weights and normalisation are a
row in `meta.index_definition` (components, weights, method, source). An index is never stored
without its parts, because how the parts are weighted is itself contested.

### 4.4 `dim_breakdown`: how it is split

Any split other than place and time.

```
dim_breakdown            (breakdown_key PK, label)              e.g. 'sex=F|age=15-24'
bridge_breakdown_member  (breakdown_key, axis, member_code)     axis ∈ meta.code_list
```

| Axis family | Axes |
|---|---|
| person | `sex`, `age_band`, `ethnicity`, `citizenship`, `education`, `disability_type` |
| household | `strata` (urban/rural), `hh_head_sex`, `hh_head_age`, `hh_composition` (e.g. has a member under 4, over 65), `hh_size` |
| income | `income_group` (B40/M40/T20), `decile`, `quintile`, `percentile`, `income_band` (nominal RM bands), `income_source` (employment, self-employment, property, transfers) |
| work | `employment_status`, `skill_level`, `occupation` (MASCO), `sector` (MSIC 2008) |
| product and money | `coicop`, `sitc`, `hs`, `bec`, `gfs_economic`, `cofog`, `pkkp_object` |
| trade | `partner_country` (ISO 3166-1) |

`breakdown_key = '_total'` means no split. Members come from published code lists
(`meta.code_list`), never from labels typed by us.

**Groups defined relative to a distribution** (B40, a decile, a percentile) depend on whose
distribution and which year. Each such member names its `reference_population` (national or
state) and `threshold_year` in `meta.code_list`. Otherwise national B40 and a state's bottom 40%
get confused.

### 4.5 `dim_entity`: who

Every body that spends, receives, audits or is audited. This is the spine of the money trail.

**Rule: every entity has a permanent opaque ID, and its readable codes are attributes with dates.**
Readable codes are not keys because Malaysia's codes move: vote codes are renumbered at cabinet
restructures, so `B.45` can name different ministries in different years, and codes get reused.

```
dim_entity           (entity_id PK, entity_type, name_bm, name_en, parent_entity_id, gfs_sector, seat_geo_code, fy_end_month)
bridge_entity_code   (entity_id, code_system, code, valid_from, valid_to, proof)
meta.entity_register  committed CSV: every entity_id ever issued, with issue date and reason; never reused, never deleted
```

| column | example | note |
|---|---|---|
| `entity_id` PK | `E000123` | issued once from `meta.entity_register`; stable across rebuilds |
| `entity_type` | `government` · `ministry` · `department` · `vote` · `programme` · `activity` · `project` · `statutory_body` · `glc` · `company` · `auditor` · `natural_person` | enum; `department` = a non-ministry body with its own vote (Parliament, SPR, JPA); `vote` = a vote administered by another body (B.11, B.12 under the Treasury); see the personal-data rule below |
| `parent_entity_id` | project → ministry → federal government | parent changes over time are dated in a bridge, not overwritten |
| `gfs_sector` | `central_gov` · `state_gov` · `local_gov` · `public_corp` · `private` | puts off-budget bodies in scope |
| `seat_geo_code` | `MY-16` | where it sits, which is **not** where its money goes |
| `fy_end_month` | `12`, `3` | drives `dim_period` for its accounts |

`bridge_entity_code` holds every readable code with its validity (illustrative: `maksud` `B.45`
valid 2020–2022), `projek_code`, `ssm_no`, `ag_agency_code`, state government `MY-03`. A code points
to exactly one entity on any date (the build enforces it). Every link after a code's first
appearance carries a `proof`, the way `dim_maksud_canonical` proves each renumbering today.
Agent tools accept a readable code plus a date (`B.45`, 2024) and resolve it.

Issuing IDs: a build that meets a code with no entity for that date stops and lists it. An ID is
issued only when a person decides whether it is a new body or a renumbered old one.

**Built 2026-11-05 (D26):** `meta/entity_register.csv` (59 entities: the federal government, 13
state governments, 45 federal votes), `meta/entity_code.csv` (99 dated codes with proofs),
`meta/spending_head.csv` (T.01-T.14, P.70: heads, not bodies) -> `core/dim_entity.csv`,
`core/bridge_entity_code.csv`, `core/entity_name.csv` (`core/pipeline/build_entities.py`, checks E1-E8).
Six entities (B.15, B.26 and B.33, each split at a lapse) are `proposed` until a person decides.

A state *as a place* (`dim_geo MY-03`) and a state *as a government* (an entity with code `MY-03`
in `code_system = state_gov`) are different rows. Spending by Kelantan's government is not
spending in Kelantan.

**Personal data rule.** Sole proprietors, directors, officials and other individuals named in
procurement notices, company records, hansards or audit text are `natural_person` entities.
They are held only where a public-interest purpose is recorded in `meta.decision`, are **never
returned by agent tools or published views**, and never appear in `gap_*` views (§12).

### 4.6 `dim_source`: from which document

The document registry (`docs/DOCUMENT_REGISTRY.md`) **is** this dimension:
`series → edition → file`. Facts point to `edition_id` + `file_id` + page. Each series carries
its `licence`, `redistribution` terms and whether it `contains_personal_data` (§12).

---

## 5. Facts (L2)

Three fact tables. Each has one job.

| Fact | One row is | Holds |
|---|---|---|
| `fact_observation` | one number for indicator × geo × period × breakdown × entity × basis × source × vintage | statistics, aggregates, budgets, spending by a body, targets |
| `fact_money_flow` | one amount that **moves** from entity A to entity B | transfers, grants, disbursements, contract payments |
| `fact_record` | one thing with text: a finding, a project, a contract, a guarantee, a target | accountability and registers |

### 5.1 `fact_observation`

| column | type | note |
|---|---|---|
| `indicator_code`, `geo_code`, `period_code`, `breakdown_key` | FK | `_total` breakdown if none |
| `entity_id` | FK | `_none` if none (e.g. CPI) |
| `basis` | enum | §7.1; **part of the key** |
| `edition_id`, `vintage` | FK, date | the document edition; the release or edition date (§6) |
| `value` | DECIMAL(38,6) | exact, in the indicator's base unit (RM, not RM juta); never a binary float, because reconciliation is to the sen |
| `value_printed`, `unit_printed` | text | exactly as printed, e.g. `40,533` `RM juta`, or `–` |
| `precision_printed` | DECIMAL | the rounding step of the printed figure (e.g. 1,000,000 for RM juta); a difference inside it is rounding, not divergence |
| `status` | enum | §7.2 |
| `se`, `ci_low`, `ci_high`, `ci_level` | DECIMAL | sampling uncertainty, where published |
| `cv`, `sample_n` | DECIMAL, int | coefficient of variation and sample size, where published |
| `estimate_method` | enum | `census` · `administrative` · `direct_survey` · `small_area_model` · `modelled` · `accounting` |
| `reliability` | enum | `ok` · `low` (publisher flag or our rule, e.g. CV > 25%) · `unknown` |
| `file_id`, `pdf_page`, `printed_page`, `table_ref`, `l1_ref` | | provenance (golden rule 3) |
| `derived_from`, `derivation_id` | text[], FK | for `basis = derived`: the input observations and the `meta.derivation` rule used |

**Primary key:** (indicator, geo, period, breakdown, entity, **basis**, edition, vintage). One
edition can print an actual, a revised estimate and a target for the same line, and all three
must be stored.

Where a publisher gives no uncertainty for a survey estimate, `reliability = unknown` and the
row inherits the caveat "survey estimate; sampling error not published". Small-area estimates
(district, parlimen, DUN) are never ranked as if exact (§11).

### 5.2 `fact_money_flow`: only money that moves between two bodies

| column | note |
|---|---|
| `flow_id` | |
| `from_entity_id`, `to_entity_id` | e.g. federal government → Kelantan government; ministry → statutory body; contract award → contractor |
| `flow_type` | `transfer` · `grant` · `loan` · `disbursement` · `contract_payment` · `equity` |
| `period_code`, `amount` (DECIMAL(20,2), RM) | |
| `economic_class`, `purpose` | `gfs_economic` / `pkkp_object`; COFOG |
| `geo_code`, `geo_method`, `geo_confidence` | where the money lands; `stated` · `parsed_name` · `agency_seat` · `none`; `_unallocated` if unknown |
| `is_leaf` | sum only leaf rows (golden rule 5) |
| `basis`, `status`, provenance | as in 5.1 |

**A budget or a spending total of one body is an observation, not a flow.** "Ministry X was
allocated RM Y" (basis `budget_estimate`) and "Ministry X spent RM Z" (basis `audited`) are
observations with `entity_id` = Ministry X. A flow exists only when the source shows money
moving to a named recipient. Revenue and economic aggregates are observations too.

**Consolidation:** money moving between two government bodies is counted once. The view
`v_general_government` removes flows where both ends sit inside the general-government sector
(`gfs_sector` in central/state/local government), so a federal grant to a state is not counted
again as state spending.

### 5.3 `fact_record` + `bridge_link`

| column | note |
|---|---|
| `record_id`, `record_type` | `audit_finding` · `audit_opinion` · `project` · `pfi_contract` · `guarantee` · `procurement_award` · `pac_recommendation` · `plan_target` |
| `entity_id`, `geo_code`, `period_code` | |
| `title_bm`, `text_bm` | as printed; personal names masked in anything an agent or view returns |
| `attributes` | JSON for type-specific fields |
| provenance columns | as in 5.1 |

```
bridge_link (from_kind, from_id, to_kind, to_id, link_type, link_method, confidence, proof, signed_off_by, signed_off_on)
  link_type   finding_about_project · pac_on_finding · response_to · award_for_project · target_funded_by
  link_method code_exact · name_matched_reviewed · human_signed · manual
```

**Naming a body in public needs a strong link.** A claim that names a company, agency or project
in connection with an audit finding or a contract is published only when its link is `code_exact`
or `human_signed` (a named person checked the evidence). A `name_matched_reviewed` link can guide
research but is never published as fact.

---

## 6. Vintages: keep everything, show "latest" as a view

* Every edition and every revision is kept: `fact_observation.vintage` and `edition_id`.
* **L1 keeps them too, not only L2.** For API and bulk-file sources the canonical CSV is the
  current vintage, and every vintage ever held is in an append-only log (`_vintage_log.csv`:
  dataset, data_as_of, retrieved_date, rows, sha256) with its bytes recoverable from git and
  verified by hash. **Built for DOSM on 2026-11-04** (`sources/dosm/pipeline/refresh.py`,
  `vintage_get.py`); BNM and every new API source follow the same pattern.
* `core.v_observation_clean` applies the indicator's `series_rule`:
  * `latest_vintage` for DOSM, BNM and other statistics: the newest release wins.
  * `own_volume` for fiscal actuals (golden rule 6): each year comes from the edition in which
    it is the newest actual (today `curated/pipeline/mof_editions.py`).
* `qa.restatement` lists every value that later vintages changed, so a series break is visible.
* **Keeping current:** DOSM is checked daily by a GitHub Actions workflow
  (`.github/workflows/dosm-refresh.yml`). A new vintage becomes a PR that merges itself only when
  every verifier passes and `refresh_report.py`'s gate holds: no FAIL, no new SOURCE_ANOMALY, no
  header change, no withdrawn rows (D20). BNM and other API sources follow the same pattern.

---

## 7. Controlled vocabularies

Stored in `meta.code_list`, enforced by the build: an unknown value fails the build.

### 7.1 `basis`: what kind of figure

| value | meaning | maps from today's |
|---|---|---|
| `audited` | certified by the Auditor-General | PKKP, state statements |
| `actual` | government's own outturn, not audited | `official_actual`, BNM fiscal |
| `announced` | announced (e.g. budget speech), not yet tabled | new |
| `budget_estimate` | tabled estimate | Anggaran, `official_projection` (budget year) |
| `revised_estimate` | estimate revised in-year, incl. supplementary estimates | `official_revised` |
| `projection` | forecast by the publisher | economic projections |
| `target` | a plan target | RMK, NIMP, NETR … |
| `statistic` | official statistic (survey, census or administrative) | DOSM, BNM non-fiscal |
| `third_party` | a figure printed by a non-official source from data it obtained (e.g. a research institute's table built from a data request) | new |
| `derived` | computed by us from other observations, by a `meta.derivation` rule | identities, per-capita, real terms |

The money trail is read across `basis`: announced → budget_estimate → revised_estimate → actual →
audited, with `received` as an observation on the recipient's own books.

### 7.2 `status`: how settled

`final` · `preliminary` (DOSM "p") · `estimate` (DOSM "e") · `revised` · `provisional_ocr`
(FY2015 PKKP leaf) · `nil` (printed `–`) · `not_printed` · `suppressed` (withheld by the
publisher, e.g. too few respondents) · `low_reliability` (publisher flag).

### 7.3 QA statuses (unchanged)

identity / cross_tier: `PASS` · `PASS_ROUNDING` · `FAIL` · cross_source: `AGREE` · `DIVERGE` ·
`SOURCE_ANOMALY` · `FOOTNOTED` · `DEFINITIONAL` · `UNCAPTURED` · `KNOWN_*` defect classes.

### 7.4 Verification tier (on every series and every published view)

`machine_checked` (the source's own identities and cross-checks pass) → `verifier_agent` (an
independent agent re-derived it blind) → `human_spot_checked` (a person re-checked a random sample
against the PDF, sample and result recorded) → `externally_reviewed` (a named outside reviewer).
**Anything IKRAM publishes needs at least `human_spot_checked`.** AI checking AI is not enough.

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
qa.check          check_id, check_type, table, key, expected, observed, diff, tolerance, status, note, proof_ref
qa.anomaly        the source misprinted it; kept as printed, with proof (golden rule 2)
qa.defect         our extraction is wrong or unproven
qa.restatement    a later vintage changed a value
qa.coverage       indicator × geo_level × period: held / gap / not_published
qa.spot_check     who checked which sample of which series against which page, and the result
qa.eval_question  a question, its known answer, tolerance, and the tool path expected; run in CI

meta.table        purpose, grain, primary key, builder script
meta.column       description, unit, enum, nullable
meta.code_list    every controlled vocabulary and published classification, incl. reference populations
meta.caveat       known limits an answer must carry (e.g. FY2015 OCR leaf, FY2009 cash basis, conflicts of interest)
meta.derivation   each derived measure: formula, inputs, deflator or denominator chosen, compatibility rules
meta.index_definition  composite indices: components, weights, normalisation, source
meta.release      every warehouse build: release_id, date, what changed; every answer cites one
meta.decision     why the model is the way it is, incl. the governance policies in §12
meta.question_log questions that could not be answered: anonymised, the missing series, date
```

The 171 underscore-prefixed QA CSVs stay in L1, where each source writes them. `qa.*` is their
union, with one schema. **CI runs every offline validator on every PR** and fails the PR on any
new FAIL (§15, Phase 0).

---

## 10. Gap views (L3)

Each view is named, has a one-line question, a fixed grain, a documented method, and publishes
its own coverage.

| View | Question | Grain |
|---|---|---|
| `gap_budget_vs_actual` | Was the money budgeted spent? | entity (ministry→programme→project) × year |
| `gap_revenue_estimate_vs_collected` | Did revenue come in as estimated? | revenue code × year |
| `gap_reported_vs_audited` | Do MOF, BNM and PKKP agree? | indicator × year |
| `gap_target_vs_outcome` | Was the plan target met? | target × indicator × geo × year |
| `gap_need_vs_money` | Does money follow need? | geo (state first, district later) × year |
| `gap_federal_vs_state` | Do federal transfers match what states record receiving? | state × year |
| `gap_audit_recurrence` | Do the same bodies keep getting the same findings? | entity × finding type × year |
| `gap_obligations_growth` | Are off-budget obligations growing faster than debt? | instrument × year |

**`gap_need_vs_money` guards.** Most federal money that reaches people is operating spending:
salaries in schools and clinics, subsidies, cash transfers. In FY2025 operating spending was
RM330.8b against RM81.9b gross development spending (BNM MSB 3.1, sum of four quarters). Projects
are the smallest part and the hardest to place (§13). So the view:

* places operating spending through sources that are already by area: KKM and KPM staff and
  facilities by state, STR and JKM welfare recipients by state, and state-by-state transfers
  (registry series `social_transfers_by_state`, `health_facts`, `education_stats`);
* publishes `placed_share` (placed RM ÷ total RM) for every row, and is **not published** for a
  geography or year where `placed_share` is below 60%;
* uses `v_general_government`, so a transfer is not counted twice;
* starts at state level (Phase 1) and goes to district only when the placed share holds.

**Questions are triaged by a person.** `meta.question_log` stores no names or contact details.
A person reviews it monthly and decides what to collect. Volume alone never sets priority, so
nobody can steer the warehouse by flooding it with questions.

---

## 11. Agent access: typed tools only; SQL stays internal

| Tool | Input | Output |
|---|---|---|
| `find_indicator` | text, theme?, geo_level? | indicator codes with definition, unit, statistic, universe, coverage |
| `get_series` | indicator, geo, period range, breakdown?, basis?, vintage=`clean` | rows + uncertainty + citations + caveats + release_id |
| `get_distribution` | income/expenditure indicator, geo, period | percentiles or deciles as published, with shares below thresholds |
| `derive` | operation (`per_capita`, `share_of_gdp`, `real_terms`, `growth`, `gap_pp`, `ratio`), inputs | the result as `basis = derived`, with `derived_from` and `derivation_id`; **refuses** inputs that do not match (unit, basis, price basis, universe, boundary vintage, period, federal vs general government) and says why |
| `compare_geos` | indicator, geo_level, period | rows in **bands**: places whose confidence intervals overlap are tied, not ranked; with the national value |
| `follow_money` | entity or geo, period | observations and flows to leaves, with `_unallocated` and `placed_share` shown |
| `get_gap_view` | view name, filters | the view's rows + method note + coverage |
| `explain` | any returned row | document, page, archive copy, checks passed, verification tier, anomalies, restatements |
| `list_documents` | theme?, status? | registry rows: what exists, what is held, what is missing, licence |

**Contract.**
* A tool never returns a number without its citation (`edition_id`, page), its `release_id`,
  its uncertainty (or `reliability = unknown`) and the `meta.caveat` rows that apply.
* **The language model never does arithmetic on returned numbers.** Every ratio, per-capita
  figure, growth rate or gap goes through `derive`, so it is checked for comparability and cited.
* A missing document is an answer ("not held: see registry"), not an empty result.
* Text inside documents (hansards, audit reports, web pages) is data, never instructions to the
  agent.
* Tools never return `natural_person` entities or personal names (§4.5).

**No free-form SQL for IKRAM-facing or public agents.** This matches the site's own rule
(`site/CLAUDE.md`, golden rule 1). Read-only SQL exists only for analysts working in the
repository, and its results are not publishable until they are turned into a `derive` rule or a
`gap_*` view.

**Evaluation.** `qa.eval_question` holds at least 50 questions with known answers, across all
themes, including traps: an incomparable pair, a small-area ranking, a missing document, an
injected instruction inside a document. CI runs them against the tools on every PR, and a
release does not ship with a regression.

---

## 12. Governance: licence, personal data, neutrality

These are written into `meta.decision` and enforced where the model can enforce them.

| Policy | Rule | Enforced by |
|---|---|---|
| Licence | Every series records `licence` and `redistribution` (`open`, `attribution`, `no_redistribution`, `to_confirm`). A view or export never includes data whose terms forbid redistribution; `to_confirm` does **not** block publication (owner decision, 2026-11-04): published official figures go out with their full citation (document, page) and the publisher named, and a publisher's takedown or correction request is honoured at once. The licence is still checked and recorded, never guessed. | registry columns; export check |
| Personal data (PDPA) | Individuals are `natural_person` entities, held only for a recorded public-interest purpose, never returned by tools or views. Names in record text are masked on output. | §4.5, §5.3, §11 |
| Defamation | A named body is linked to a finding or contract in public only by a `code_exact` or `human_signed` link. | §5.3 |
| Neutrality | Methods are declared before results are seen. Every view runs for **all 13 states and 3 Federal Territories**, never a chosen few. `core.*` holds no party attribute. Election results are used only as geographic context (who represents an area), not to score parties or politicians. | `meta.decision`; view definitions |
| Lawful sources only | Only documents published by their owner, released under the law, or obtained through an official data request. No leaked or OSA-classified documents. | registry rule |
| Conflicts of interest | Where IKRAM or its people helped produce a source, a `meta.caveat` discloses it on every answer that uses it. | `meta.caveat` |
| Sensitive breakdowns | Ethnicity is published only as the official source publishes it, with the source's own categories, and never inferred by us. | §4.4 code lists |

---

## 13. Follow the money: both directions

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
| A | Place operating spending (most of the money) | KKM/KPM staff and facilities by state; STR/JKM recipients by state | **not held** |
| A | Place each project | stated location → parsed name → agency seat → `_unallocated` | only 103 of 809 FY2024 project names name a state |
| A | State-level receipts | state statements, state budgets | state statements 13 states FY2014–2024; state budgets not held |
| A | Need on the same map | HIES, LFS, population at state and district | HIES/LFS held; **population below national not held** |
| B | Implementing agency | entity register, AG agency codes | sijil registers FY2023–24 |
| B | Contractor | procurement awards, company register | **not held** |
| B | Audit and follow-up | LKAN findings → PAC → response | findings 2024–26 (no ministry/project code yet); PAC not held |

Every placed or linked amount carries `geo_method`/`link_method`. Unplaced money is reported
as `_unallocated` with its total, so a map never looks more complete than the data is.

---

## 14. How today's tables map in

| Today (L1 / curated) | Goes to |
|---|---|
| `sources/pkkp` statements, opex leaf, Lampiran projects | `fact_observation` (entity = vote/programme/project, basis `audited`); `fact_money_flow` only for itemised transfers and grants; projects also `dim_entity` (Track 0) |
| `sources/anggaran`, `anggaran-hasil` | `fact_observation` (basis `budget_estimate`) |
| `sources/mof-fiscal-outlook` (9 editions) | `fact_observation`, one vintage per edition, `series_rule = own_volume` |
| `sources/bnm` msb_* | `fact_observation`; cryptic columns → indicator codes via `meta` |
| `sources/dosm` (110 files) | `fact_observation` at country/state/district/parlimen/DUN, with vintages from `_vintage_log.csv` |
| `sources/states` | `fact_observation` (entity = state government) + `fact_money_flow` for federal→state transfers |
| `sources/audit-negara` findings, sijil, e-SelfAudit | `fact_record` + `bridge_link` (Track B) |
| `curated/fact_obligations` | `fact_observation` (stocks) + `fact_record` (guarantees) |
| `curated/dim_maksud_canonical` | absorbed into `dim_entity` + `bridge_entity_code` (its proofs move with it) |
| `curated/forecast/` | **done 2026-11-04:** moved to `apps/models/` (D8) |
| `curated/dashboard/` | **done 2026-11-04:** retired; features to port: pension simulator (an app in `apps/models/`), refinancing wall (a view over debt observations), debt vs the 60/65%-of-GDP ceiling (a target-vs-outcome view). Peer benchmarks return only from a registry source with matched definitions. Last commit with the old dashboard: `67372332eb8b28c37f7313db09eb96ebcb9c2932` |

**Site migration.** Each site template moves to a view before the table it reads is retired, and
the view must return the same numbers to the ringgit:

| Site reads today (`site/api/app/templates.py`) | Becomes |
|---|---|
| `curated.fact_fiscal_headline` (14 uses, also `chatbot.py`) | `v_fiscal_headline` |
| `curated.fact_ministry_fiscal`, `curated.dim_maksud_canonical` | `v_ministry_fiscal` over observations + `dim_entity` |
| `curated.fact_opex_by_component`, `curated.fact_devex_by_sector` | `v_mof_breakdowns` |
| `curated.fact_obligations`, `curated.fact_planning_efficiency` | `v_obligations`, `gap_budget_vs_actual` |
| `pkkp.fact_revenue`, `pkkp.fact_timeseries_*`, `pkkp.fact_opex_detail`, `pkkp.fact_devex_project` | `v_pkkp_revenue`, `v_pkkp_timeseries`, `v_opex_leaf`, `v_devex_projects` |

---

## 15. Build order: something useful early, then broaden

| Phase | Deliverable | Done when |
|---|---|---|
| 0 Foundation | registry as data, with licence / redistribution / personal-data fields (done: `meta/registry_file.csv`, `meta/_validation_registry.csv`); `meta` + code lists (done); **CI** running every offline validator on PRs (done: `qa/run_offline_suite.py`, 23 scripts; 46 PKKP validators to port); L0 archive (sha256 store + public archive copies) (open); vintage logs for every API source (DOSM and BNM done); governance policies in `meta.decision` (done); daily DOSM refresh workflow (done; needs Actions write permission enabled once) | every held file has a registry row with sha256 and licence; CI blocks a PR with a new FAIL |
| 1 First useful slice: **state level, end to end** | population by state and district; HIES, LFS, CPI by state; state finances; federal→state transfers → `dim_geo` (state, district), `dim_period`, `dim_indicator`, `dim_breakdown` → `fact_observation` with uncertainty fields → `get_series`, `compare_geos` (bands), `derive`, `explain` → `gap_need_vs_money` **at state level** with `placed_share`; first 50 `qa.eval_question` | IKRAM can ask a state-level need-vs-money question and get a cited, banded, checked answer. **Built 2026-11-04** (`core/README.md`): population by state and district; 25 indicators, 62,015 observations; `gap_need_vs_money` (16 states and FTs × 5 HIES years, federal column withheld below the 60% guard); tools in `apps/tools/`; 70 eval questions in CI. Open: federal→state transfers from the federal side (Phase 3), human spot-check before publication |
| 2 Broaden the statistics | all DOSM/BNM/MOF series; DOSM survey report tables (HIS, HES, LFS annual report, Basic Amenities); NHMS; wellbeing indices; `get_distribution`; full `geo_hierarchy` | reproduces today's curated tables to the ringgit. **In progress** (`core/README.md`): health, education and services (data.gov.my, state level); small areas (166 districts, 222 parlimen, 600 DUN on GE15 boundaries; HIES income, Gini, spending, poverty, LFS, amenities), never ranked; `geo_hierarchy` (administrative and electoral); income distributions by percentile with `get_distribution` (published brackets only, rule DIST1); national accounts (GDP and income components, current prices); federal totals from BNM and MOF beside PKKP; national monthly CPI (headline and COICOP divisions, on `cpi.index` beside the states), trade (exports, imports, balance), M1–M3 and banking-system loans (BNM MSB 1.3, 1.18); `qa/reproduce_curated.py` in CI (230 of 230 cells: fact_labour_indicators and the BNM/MOF columns of fact_fiscal_headline); 63 indicators, 134,612 observations; 146 eval questions. Open: the rest of the national DOSM/BNM/MOF series, ministries' own district boundaries, reproducing the curated tables |
| 3 Money-trail spine | `meta.entity_register`, `dim_entity`, `bridge_entity_code`; PKKP and Anggaran as entity observations; transfers as flows; development estimates; social-transfer placement | every code resolves to one entity per date; `placed_share` reported per state. **In progress:** the entity spine is built (2026-11-05, D26): every vote printed in PKKP FY2009-2024 and the Anggaran 2024-2026 books resolves to one entity; core's state and federal rows carry entity IDs; `get_entity` resolves a code plus a year. Ministry spending is in core as entity observations (3,787: PKKP audited and estimates FY2009-2024, Anggaran 2024-2026), adding up to the printed totals every year (C16) and reproducing `curated/fact_ministry_fiscal` to the sen (1,261 of 1,267; 6 FY2009 rows explained). Next: federal headline totals straight from PKKP (retiring CV16), transfers as flows |
| 4 Records and links | LKAN, PAC, procurement as `fact_record` + `bridge_link`, under the personal-data and defamation rules | findings carry entity IDs; no unsigned name-match is publishable |
| 5 Complete | remaining `gap_*` views; site templates all on views; ported dashboard features; FY2025 nowcast scored; district-level need vs money where `placed_share` holds | every tool output cited; eval suite green |

Each phase: branch → reconcile to today's numbers → independent adversarial verifier → human
spot-check of a sample → PR.

---

## 16. Decisions

| # | Decision | Why | Where |
|---|---|---|---|
| D1 | Public money is one theme of nine; architecture is economy-wide | PKKP was the first document, not the centre | §1, §3 |
| D2 | ISO 3166-2:MY for states; DOSM/SPR codes below state; ISO 3166-1 for other countries | standard, published codes | §4.1 |
| D3 | Keep every vintage, in L1 (vintage log) and L2; "clean" is a view | revisions are evidence | §6 |
| D4 | Typed agent tools only for IKRAM-facing and public agents; read-only SQL internal only | every answer cited and checked; matches `site/CLAUDE.md` | §11 |
| D5 | Follow the money both ways: place (Track A) and recipient (Track B) | IKRAM works at national and state level | §13 |
| D6 | Permanent opaque `entity_id` + dated readable codes; tools accept readable codes | vote codes are renumbered and reused | §4.5 |
| D7 | Every boundary set kept as published, vintage in `geo_code`; areas sit in several hierarchies; re-mapping built only on demand | boundaries change and do not nest | §4.1 |
| D8 | `curated/forecast/` → `apps/models/` (done) | models are apps, not warehouse data | §14 |
| D9 | `curated/dashboard/` retired (done); three features to port | superseded by `site/` | §14 |
| D10 | Uncertainty stored with every survey estimate; small areas shown in bands, not ranks | the easiest IKRAM claim to discredit is a noisy ranking | §5.1, §11 |
| D11 | `basis` is part of the observation key; money and values are DECIMAL | one edition prints actual, revised and target for one line; reconciliation is to the sen | §5.1 |
| D12 | Flows only for money moving between two bodies; budgets and spending totals are observations | an appropriation is not a transfer | §5.2 |
| D13 | General-government consolidation removes intergovernmental flows | no double counting | §5.2 |
| D14 | The language model never does arithmetic; `derive` does, with comparability checks | cited numbers can still be wrongly combined | §11 |
| D15 | Governance: licence, personal data, defamation, neutrality, lawful sources, conflicts of interest | an NGO's credibility and legal exposure | §12 |
| D16 | Verification tiers; publication needs a human spot-check | AI checking AI is not enough | §7.4 |
| D17 | Raw files archived outside the publisher (sha256 store + public archive) | government links break | §2 |
| D18 | Build order delivers a state-level, end-to-end slice in Phase 1; CI in Phase 0 | value early; checks enforced | §15 |
| D19 | Ninth theme: environment, climate & disasters; housing, water, transport and ICT sit in theme 6 | the review found them missing | §3 |
| D20 | DOSM refreshed daily by a GitHub Actions workflow; a new vintage PR merges itself only when every verifier passes and the gate holds | always current, never silent | §6 |
| D21 | Low-value global series deferred until a question needs them | maintenance cost for a small team | registry |
| D22 | CI runs the offline check suite on every PR and blocks a script failure, a non-reproducing rebuild or a FAIL not in `qa/known_fails.csv` | checks must be enforced, not remembered | `qa/README.md` |
| D23 | Raw documents (L0) kept on GitHub: assets of this private repository's `l0-archive` release, named by sha256, written only by `l0-archive.yml`; index `meta/l0_archive.csv`. A file with no recorded sha256 is accepted only if its cited amounts are on its cited pages (`meta/l0_identity.py`) | 13 GB is too big for git history (files over 100 MB); release assets keep clones light and need no other service | §2, `meta/l0_archive.py` |
| D26 | A federal body is its supply vote: one ID through renames while printed every year; P vote = same body (incl. residual years); a B vote printed again after a lapse is a new body until a person links it; T heads and P.70 are spending heads, not bodies | codes are renumbered and reused; identity decided before the money is loaded | §4.5, `meta/entity_register.csv` |

---

## 17. Review findings and where they are answered

**Plan review (independent agent, 2026-11-04).**

| # | Finding | Severity | Answered in |
|---|---|---|---|
| 1 | Agent answers can be invalid even when every row is cited; `run_sql` contradicts `site/CLAUDE.md`; no eval set | critical | §11, D4, D14 |
| 2 | No uncertainty; small-area rankings | critical | §5.1, §11, D10 |
| 3 | Licence, PDPA, defamation, neutrality unaddressed | critical | §12, §4.5, §5.3, D15 |
| 4 | "Keep every vintage" not true of the pipeline; L0 not archived | critical | §6 (DOSM vintage log built), §2, D3, D17 |
| 5 | `basis` missing from the key; money as `double` | important | §5.1, D11 |
| 6 | Geography is not one tree; levels missing; inferred boundary vintages | important | §4.1, D7 |
| 7 | `gap_need_vs_money` ignores operating spending; double counting | important | §10, §5.2, D13 |
| 8 | Missing sources: supplementary estimates, Dewan Rakyat Hansard, local government, social protection, tax expenditure, LHDN, environment and disasters | important | registry, §3, D19 |
| 9 | Value comes last; no CI; site migration unplanned | important | §15, §14, D18 |
| 10 | AI verifying AI; conflicts of interest | important | §7.4, §12, D16 |
| 11 | Question log: personal data, injection, steering | minor | §10, §11 |
| 12 | One-theme rule vs the registry; `additive` too coarse; non-calendar years | minor | §3, §4.3, §4.2 |
| — | Simplify: defer global series; budgets are not flows; concordance only on demand | — | D21, D12, D7 |

**Household-wellbeing coverage check (independent agent, 2026-11-04).** The design gaps it found,
and where they are answered: household and income breakdown axes (§4.4); statistic and universe
(§4.3); uncertainty and `suppressed` / `low_reliability` (§5.1, §7.2); derivations as declared
rules (`meta.derivation`, `derive`); distributions (`get_distribution`); composite indices with
stored components (`meta.index_definition`); strata as a breakdown, not a place (§4.1); partner
countries (§4.1, §4.4); third-party figures (`basis = third_party`); district boundary changes
(§4.1). The biggest data gap it found was four public DOSM survey reports (household income,
household expenditure, the annual labour force report, basic amenities); they are in the registry.
