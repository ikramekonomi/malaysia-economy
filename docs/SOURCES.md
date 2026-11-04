# Source Catalog — Malaysia Public Finance Data Warehouse

Sources to ingest or connect, prioritised by value and by how directly they enable
**gap-finding**. Each source is namespaced under `sources/<name>/` with its own extraction,
provenance, and validation; comparison happens in `curated/`. Prefer machine-readable feeds
(APIs / open data) over PDF extraction wherever available.

**Architecture (see CLAUDE.md): hub-per-domain, truth-by-reconciliation.** PKKP anchors
the federal-fiscal domain only; agencies/GLCs, states, the real economy (DOSM) and
monetary/financial (BNM) each have their own hub, joined through conformed dimensions in
`curated/`. The catalogue below is organised by how directly a source serves a domain's
reconciliation web — and by the three blind spots of any single-hub view: off-budget
scope, cash-basis accounting, and the economy beyond the fiscal accounts.

## Status
- ✅ **pkkp** — Federal audited actuals, FY2009–FY2024 (in repo). Provenance to PDF + page.
- ✅ **anggaran** — Anggaran Perbelanjaan Persekutuan, Budget 2025 + 2026 books at maksud
  grain (sebenar 2022–2024, anggaran asal, tabled), crosswalked to PKKP, adversarially
  verified. Program/objek grain = follow-up.
- ✅ **anggaran-hasil** — Anggaran Hasil (revenue estimates by kod hasil), Budget 2025 +
  2026 editions incl. tax-measure impacts and revenue-after-measures headline.
- ✅ **mof-fiscal-outlook** — Fiscal Outlook Budget 2025 + 2026 editions, headline grain
  (official 2025–26 projections, debt, nominal GDP), adversarially verified; plus the
  Seksyen 5 contingent-liability / guarantee tables (Jadual 5.1–5.4 of both editions)
  feeding `curated/fact_obligations.csv`.
- ✅ **dosm** — GDP/GNI, population, households (OpenDOSM canonical files + API
  cross-check + vintage tracking with a weekly detection routine).
- ✅ **bnm** — quarterly federal finance + debt-by-holder/maturity via the BNM
  OpenAPI (`api.bnm.gov.my/public/msb/3.1*`), 1996–1Q2026, triangulated against
  PKKP to RM1–2m per year; FY2025 measured intra-year.
- ✅ **audit-negara** — all 8 federal LKAN volumes 2024–2026 acquired via
  parlimen.gov.my Command Papers (manifest + sha256 in
  `sources/audit-negara/data/lkan_reports.csv`); extracted & adversarially
  verified: per-agency sijil registers FY2023+FY2024 (285 agencies × opinion)
  the per-audit findings register (34 audits, 426 findings, 1,080 RM
  tokens, 405 ministry responses), and the AG's own federal fiscal tables
  (48 tables / 1,569 cells, FY2024 vs FY2023) — completing the first
  three-source triangulation: AG = PKKP audited on all six headline lines;
  BNM's reported FY2023 gross DE exceeds the audited figure by RM1.247 juta.

## Tier 1 — highest value; pairs directly with PKKP
- **Anggaran Perbelanjaan Persekutuan** (Federal Expenditure Estimates) — MOF/Treasury. The
  **budgeted** counterpart to PKKP actuals, same maksud/program structure → the core
  **budget-vs-actual gap**. Annual (PDF; recent years partly on data.gov.my).
- **Anggaran Hasil Kerajaan Persekutuan** (Federal Revenue Estimates) — budgeted revenue vs
  PKKP collected.
- **MOF Fiscal Outlook & Revenue Estimates ("Buku Fiskal" / Laporan Fiskal)** — annual
  headline fiscal position, debt, tax expenditure, **commodity-level subsidies** (detail PKKP
  lacks), contingent liabilities. Cross-check vs PKKP audited.
- **data.gov.my / OpenDOSM** — Malaysia's official open-data portal; much of DOSM + some
  fiscal series already machine-readable (Parquet/CSV API). **Connect first** for anything it
  already hosts — far cheaper than PDF extraction.

## Tier 2 — denominators, gaps/wastage, revenue detail
- **DOSM (Department of Statistics)** — GDP & national accounts (federal **and state GDP**),
  Government Finance Statistics (GFS), population, CPI/deflators. Essential denominators:
  spend as % of GDP, per-capita, real terms.
- **Auditor-General's Report (Laporan Ketua Audit Negara)** — audit findings, wastage,
  non-compliance, project overruns; federal + state. Directly serves "find gaps in fiscal
  behaviour."
- **Bank Negara Malaysia (BNM)** — higher-frequency federal government finance, debt, public
  sector statistics; monthly/annual cross-check.
- **LHDN (Inland Revenue) & JKDM (Customs)** — direct tax and SST/excise collection detail
  behind PKKP revenue lines.

## Tier 3 — state & local, specialised (needed for a true multi-level warehouse)
- **State LKAN volumes** — 13 per tabling day on the SAME parlimen.gov.my Command-Paper
  route as the federal volumes (audited analysis + sijil of every state's finances,
  per year). Acquisition folded into the LKAN backfill crawl (state volumes kept and
  manifested with `scope=state:<Negeri>`). The cheapest entry into state coverage.
- **State Government Financial Statements (Penyata Kewangan Kerajaan Negeri)** — 13 states +
  Federal Territories, audited by the Auditor-General. The **state equivalent of PKKP**
  (audited state actuals). Start with the largest / most-scrutinised: Selangor, Johor,
  Sarawak, Sabah, Penang, Terengganu, Kelantan.
- **State Budgets (Belanjawan / Enakmen Perbekalan Negeri)** — state budgeted vs state
  actuals; and **federal transfers to states** (pairs state books ↔ PKKP transfer lines).
- **Petroleum / PETRONAS revenue & royalties** — federal dividends plus oil royalties to
  Terengganu / Sabah / Sarawak / Kelantan; a major fiscal channel under-detailed in PKKP.
- **Local authority (PBT) finances** — municipal / city-council budgets & accounts (deepest
  tier; fragmented publication — deliberately last).

## Tier 4 — accountability & flow detail (enabled by the audit-negara datasets)
- **PAC reports (Jawatankuasa Kira-Kira Wang Negara)** — tabled on the same
  parlimen.gov.my route (`DR.<n>.<year>` papers). Closes the loop in the data:
  audit finding → PAC hearing → government undertaking; joins to
  `fact_lkan_findings.csv`.
- **MyProcurement / ePerolehan tender awards** — procurement award registers
  (value, winner, ministry); pairs with the procurement findings in the LKAN
  registers.
- **LHDN & JKDM annual reports** — tax-type collection detail behind PKKP revenue
  lines (CIT/PIT split, SST by sector).
- **GLC / MKD company accounts** — financials of the companies the AG audits
  (joins the Syarikat audit findings to actual company statements).
- **DOSM Government Finance Statistics + state GDP** — via the existing OpenDOSM
  API pipeline; consolidated general-government series and state-ratio
  denominators. Machine-readable: do before further PDF sources.

## Tier 0 — plan targets as data (the Agenda Ekonomi Negara layer)

**The highest-value gap in the warehouse, and nothing public does it.** This warehouse's
proven competence is *plan vs outcome* — tabled budget vs audited actual. Applied to the
economy, that becomes **national targets vs realised outcomes**: the first systematic
scorecard of whether Malaysian economic plans are actually met.

Each source below is ingested as a **target register** (target, unit, baseline, target
year, owning ministry, source page), then paired with the DOSM/BNM series that measures
it, in `curated/`.

- **Rancangan Malaysia Ke-12 / Ke-13** + Mid-Term Reviews — GDP growth, investment share,
  income, employment, regional balance, poverty. The spine of the layer.
- **Ekonomi MADANI** — the 7 targets / 6 goals framework, with dates.
- **NIMP 2030** (New Industrial Master Plan) — mission-level and sector targets.
- **NETR** (National Energy Transition Roadmap) — capacity, emissions, investment.
- Sector blueprints — digital, semiconductor, logistics, agrofood, tourism.
- **Belanjawan speech commitments** — announced measures, traceable to the vote that
  funds them (joins straight to `sources/anggaran` detail grain).

Pairing pattern: `target_value` ↔ the measured series ↔ the budget line funding it.
A target with no funded vote, or a funded vote with no target, is itself the finding.

## Tier 1b — the real economy (required for any economic-agenda analysis)

Mostly machine-readable through the OpenDOSM API already wired in `sources/dosm`:

- **National accounts detail** — GDP by sector and by expenditure, quarterly, real and
  nominal; GNI; savings/investment balance.
- **Household Income & Expenditure Survey (HIES/HES)** — income by decile, **Gini**,
  poverty incidence, B40/M40/T20, by state and strata. Without this the agenda's core
  outcomes are unobservable.
- **Wages, productivity and labour** — salaries & wages survey, productivity by sector,
  labour force detail, unemployment/underemployment, foreign-worker dependence.
- **Industrial production, manufacturing sales, services indices** — the monthly pulse.
- **Trade at full depth** — commodity × partner (HS/SITC beyond the 1-digit already held).
- **Approved investments (MIDA)** — FDI/DDI by sector and state, approved vs realised
  (a gap pairing in its own right).
- **Business demography** — SSM registrations/closures, SME Corp census.

## Tier 2b — state-directed capital outside the budget

The economic analogue of the off-budget fiscal blind spot already closed:

- **GLIC accounts** — Khazanah, EPF, KWAP, PNB, LTAT, Lembaga Tabung Haji. Collectively
  they steward assets comparable to federal debt; none is in the fiscal accounts.
- **PETRONAS** — annual report, dividends and royalties. Already 92–98% of all dividends
  reaching the federal government (see `curated/GAP_VIEWS.md`): a single-point dependency.
- **Capital markets** — Bursa/SC aggregates, Islamic finance, sukuk issuance.

## Tier 3b — sector and delivery data

Energy (Suruhanjaya Tenaga, TNB), commodities (MPOB, MRB, MTIB), property (NAPIC),
transport & logistics, education/TVET outcomes, health outcomes, digital and broadband
(MCMC), **district-level GDP** for intra-state regional gaps.

## Benchmarking / independent validation
- **IMF** — Article IV, WEO, Government Finance Statistics for Malaysia (independent check on
  headline aggregates).
- **World Bank** — Malaysia public finance reviews & open data.

## Roadmap — Agenda Ekonomi Negara (agreed 2026-08-01)

Goal: the most complete, fully-verifiable warehouse of the Malaysian economy, built to
**find gaps** — between plan and outcome, budget and delivery, federal and state,
reported and audited.

Order of work:
1. **DOSM real-economy set** (Tier 1b) — national accounts detail, HIES/income and Gini,
   wages and productivity, IPI/services, trade depth. Machine-readable, extends the
   existing `sources/dosm` pipeline. **In progress.**
2. **Tier 0 plan-target registers** — RMK-12/13, Ekonomi MADANI, NIMP 2030, NETR — paired
   against the Tier 1b series in `curated/`.
3. **GLIC + PETRONAS accounts** (Tier 2b) — the largest unmeasured pool of state-directed
   capital.
4. PAC reports, MyProcurement, LHDN/JKDM (Tier 4), then sector data (Tier 3b).

**Caution carried into every economy source:** the fiscal sources are audited and
reconcilable to the ringgit; most real-economy data is survey-based, revised, and
vintaged. Restatement and vintage handling is a first-class requirement, not an
afterthought — the weekly DOSM vintage routine is the pattern to follow.

## Tinjauan Fiskal editions 2019–2027 — ingested; FY2009–2014 still open

**Closed (2026-11-04).** All nine editions MOF still publishes on `belanjawan.mof.gov.my`
(Budget 2019 to Budget 2027) have their statistical appendix ingested into
`sources/mof-fiscal-outlook/data/<edition>_public_finance_stats/` — Jadual 1.1 and the
3.1–3.3 expenditure breakdowns, parsed from the PDFs (nothing typed in), reconciled to each
edition's own printed identities (832 checks, 0 FAIL), and cross-checked against the
independently verified 2021 transcription (exact) and the full-report headline figures
(20/20). The curated layer takes each year from its own edition
(`curated/pipeline/mof_editions.py`). As a result:

- `curated/fact_fiscal_headline.devex_net_rm` (MOF's own net development expenditure) now
  covers **FY2015–2024**, against four years before; it agrees with BNM MSB 3.1 within MOF's
  own rounding every year.
- The MOF expenditure breakdowns cover **FY2015–2027** (actuals to FY2025), against
  FY2017–2021 from one edition.
- The 2027 edition adds **FY2025 actuals**, one year past the warehouse's audited (PKKP)
  horizon.

**Still open: FY2009–2014.** Before Budget 2019 MOF printed these tables in the *Laporan
Ekonomi* (Economic Report), not the Tinjauan Fiskal, and the 2018 *Anggaran Hasil* book
carries none. The Laporan Ekonomi editions 2010–2018 are the remaining source for MOF's own
figures in those years; until then BNM MSB 3.1 (`devex_net_bnm_rm`) is the complete series.

## Earlier roadmap (2026-07-31)
In flight: LKAN backfill 2009–2023 (federal + state volumes), AP + hasil book
backfill 2010–2023, Laporan Ekonomi ~2009–2018 (the pre-2019 Fiscal Outlook
equivalent) — each acquisition → manifest → era-specific extraction →
adversarial verification. Then, in order: DOSM GFS + state GDP (machine-readable)
→ pilot state financial statements (Selangor or Sarawak) → PAC reports →
remaining Tier 4 by earned priority.

## Gap-analysis pairings (why we consolidate)
| Question | Compare |
| --- | --- |
| Budgeted vs actual spend | Anggaran Perbelanjaan ↔ PKKP (per maksud/program) |
| Revenue estimate vs collected | Anggaran Hasil ↔ PKKP revenue |
| Audited vs headline-reported | PKKP ↔ MOF Fiscal Outlook |
| Federal vs state | State financial statements ↔ federal transfers |
| Spend vs capacity | PKKP / state ↔ DOSM GDP & population |
| Planned vs delivered (projects) | Devex estimates ↔ PKKP Lampiran 2 ↔ Auditor-General |
| Commodity subsidy detail | MOF Fiscal Outlook / Anggaran ↔ PKKP subsidy lines |

## Ingestion rules
1. Prefer machine-readable (data.gov.my/OpenDOSM, DOSM/BNM APIs) over PDF.
2. Each source = own `sources/<name>/` folder, own extraction + provenance + validation.
3. Conform to shared dimensions (year, maksud/ministry, object class, state) in `curated/`.
4. Never blend raw numbers across sources without a documented mapping and an audit trail —
   same discipline as PKKP's cross-volume restatement audits.
