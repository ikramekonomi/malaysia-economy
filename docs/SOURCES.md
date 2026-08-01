# Source Catalog — Malaysia Public Finance Data Warehouse

Sources to ingest or connect, prioritised by value and by how directly they enable
**gap-finding**. Each source is namespaced under `sources/<name>/` with its own extraction,
provenance, and validation; comparison happens in `curated/`. Prefer machine-readable feeds
(APIs / open data) over PDF extraction wherever available.

## Status
- ✅ **pkkp** — Federal audited actuals, FY2009–FY2024 (in repo). Provenance to PDF + page.
- ✅ **anggaran** — Anggaran Perbelanjaan Persekutuan, Budget 2025 + 2026 books at maksud
  grain (sebenar 2022–2024, anggaran asal, tabled), crosswalked to PKKP, adversarially
  verified. Program/objek grain = follow-up.
- ✅ **anggaran-hasil** — Anggaran Hasil (revenue estimates by kod hasil), Budget 2025 +
  2026 editions incl. tax-measure impacts and revenue-after-measures headline.
- ✅ **mof-fiscal-outlook** — Fiscal Outlook Budget 2025 + 2026 editions, headline grain
  (official 2025–26 projections, debt, nominal GDP), adversarially verified.
- ✅ **dosm** — GDP/GNI, population, households (OpenDOSM canonical files + API
  cross-check + vintage tracking with a weekly detection routine).
- ✅ **bnm** — quarterly federal finance + debt-by-holder/maturity via the BNM
  OpenAPI (`api.bnm.gov.my/public/msb/3.1*`), 1996–1Q2026, triangulated against
  PKKP to RM1–2m per year; FY2025 measured intra-year.
- ✅ **audit-negara** — all 8 federal LKAN volumes 2024–2026 acquired via
  parlimen.gov.my Command Papers (manifest + sha256 in
  `sources/audit-negara/data/lkan_reports.csv`); extracted & adversarially
  verified: per-agency sijil registers FY2023+FY2024 (285 agencies × opinion)
  and the per-audit findings register (34 audits, 426 findings, 1,080 RM
  tokens, 405 ministry responses). Remaining targets in the source README:
  LKAN 3/2025 Bahagian II fiscal tables (pairs with PKKP FY2024).

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

## Benchmarking / independent validation
- **IMF** — Article IV, WEO, Government Finance Statistics for Malaysia (independent check on
  headline aggregates).
- **World Bank** — Malaysia public finance reviews & open data.

## Roadmap (agreed 2026-07-31)
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
