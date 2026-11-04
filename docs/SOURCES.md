# Source plan: documents and APIs by theme

What the warehouse needs, theme by theme: what we hold, what we must get, and how we get it
(an API to connect, or a document to collect). The **row-level detail is in
`docs/registry/series_seed.csv`** (104 series, revision 2). This page is the plan; the registry is the
checklist. How the registry works: `docs/DOCUMENT_REGISTRY.md`. How the data fits together:
`docs/DATA_MODEL.md`.

**Wording:** we say **public money** (*wang awam*), not "government money". The money
belongs to the public, and the term covers federal, state, statutory bodies and GLCs. The
Financial Procedure Act 1957 uses the same term ("public moneys").

## At a glance

| # | Theme | Held | Must get first (P1) | Main way in |
|---|---|---|---|---|
| 1 | People & poverty | 3 of 14 | population by state and district; HIS report tables; HES report tables; cash-transfer recipients by state | API (OpenDOSM) + DOSM reports |
| 2 | Jobs & wages | 2 of 8 | salaries & wages survey; LFS annual report | API (OpenDOSM) + DOSM reports |
| 3 | Prices & cost of living | 1 of 6 | HES report tables (P2: CPI detail, item prices, house prices) | API (data.gov.my) + PDF |
| 4 | Output & industry | 3 of 15 | (P2: investment, Economic Census, district GDP) | API (OpenDOSM) |
| 5 | Public money & money trail | 7 of 30 | development estimates; federal development money by state; state budget estimates; cash-transfer recipients by state | PDF |
| 6 | Health, education & services | 1 of 9 | NHMS; health facts; education statistics | PDF + data.gov.my |
| 7 | Accountability | 3 of 17 | procurement awards | PDF + web |
| 8 | Money, credit & financial wellbeing | 1 of 7 | (P2: household debt, EPF/SOCSO) | API (BNM) + PDF |
| 9 | Environment, climate & disasters | 0 of 6 | (P2: NADMA disaster data) | PDF + web |
| — | Plan targets and cross-cutting | 0 of 7 | Malaysia Plan targets (RMK-12 MTR, RMK-13) | PDF |

"Held" counts series that are held, extracted or verified. A series can serve two themes,
so the column does not add to 104.

**The pattern:** the economy themes (1–4, 8) mostly come through **APIs we already use**, so
each new series costs little. Public money and accountability (5, 7) come from **PDFs**. These
are slow, but they are where the advocacy findings are, and where nobody else has the data in
usable form.

---

## APIs: connected and to connect

| API | Publisher | Status | Gives us |
|---|---|---|---|
| `api.data.gov.my` (OpenDOSM + data catalogue) | DOSM / data.gov.my | **connected, checked daily** (D20) | national accounts, HIES, LFS, CPI, trade, state GDP |
| `storage.dosm.gov.my` (bulk files) | DOSM | **connected** | the canonical CSVs behind the API |
| `api.bnm.gov.my` (OpenAPI) | BNM | **connected** | federal finance, rates, FX, money supply, credit |
| data.gov.my datasets (ids to confirm) | DOSM, KPDN, MOF, KPM, SPR | to connect | population by state/district, Kawasanku constituency profiles, election results, PriceCatcher, fuel prices, education, CPI detail |
| DOSM data request service | DOSM | to request | custom HIES and Basic Amenities tabulations not in any publication |

**Global**, for peer comparison and independent cross-checks. Every one needs its
definitions matched before a comparison is shown (federal vs general government, for one).

| API | Publisher | Theme | Gives us |
|---|---|---|---|
| IMF DataMapper + SDMX API | IMF | 4, 5, 8 | WEO, IFS, GFS, Fiscal Monitor |
| World Bank Indicators API | World Bank | 4, 7 | WDI; Worldwide Governance Indicators |
| BIS data portal API | BIS | 8 | household credit and debt service ratios vs peers |
| OECD SDMX API | OECD | 5 | Revenue Statistics in Asia and the Pacific (tax mix, tax-to-GDP) |
| UN Comtrade API (free key) | UN | 4 | trade by partner and HS code; mirror checks on DOSM trade |
| ILOSTAT SDMX API | ILO | 2 | labour and wages vs peers |
| WHO GHO OData API | WHO | 6 | health outcomes and spending vs peers |
| UNESCO UIS API | UNESCO | 6 | education outcomes vs peers |
| UN SDG API | UN | targets | the SDG indicators Malaysia reports against |
| UNDP HDR API (key) | UNDP | 1 | Human Development Index |
| IBP Open Budget Survey (download) | IBP | 7 | the federal transparency score |
| TI Corruption Perceptions Index (download) | Transparency International | 7 | perceived corruption vs peers |

Endpoint details are confirmed when each is connected; none is assumed. **Deferred until a
concrete question needs them** (D21, to keep maintenance small): IMF SDMX, World Bank WDI and
WGI, OECD, ILOSTAT, UNESCO, UN SDG, UNDP, TI, FAOSTAT, WITS, ND-GAIN. Kept: IMF WEO (peer debt),
BIS (household debt), UN Comtrade (import dependence), WHO GHO (health outcomes), IBP.

No API exists for most fiscal and accountability documents. Those come by **document
collection**:

| Route | Status | Gives us |
|---|---|---|
| parlimen.gov.my Command Papers | **crawler built** | PKKP, LKAN federal and state (402 volumes held) |
| belanjawan.mof.gov.my | **fetcher built** | Tinjauan Fiskal, Anggaran, Anggaran Hasil |
| 13 state government and assembly websites | to build | state budgets, budget speeches, enacted budgets, year-end reports, hansards |
| audit.gov.my | to check | AG action-status dashboard |
| ministry and agency websites | to collect | health facts, plans, MIDA, NAPIC, GLIC reports |

---

## Questions are examples, not a limit

The questions under each theme below show what a theme is for. They are **not** the list of
what the warehouse can answer. Nothing in the data model is built around a fixed question:
every number is stored the same way (what, where, when, split by what, who, from which
document), so any question that combines those can be asked, including ones nobody has
thought of yet.

**Patterns that work for every indicator, in every theme:**

| Pattern | Example |
|---|---|
| Level | What is the youth unemployment rate in Sabah? |
| Trend | How has it moved since 2015? |
| Rank and compare places | Which DUNs are worst, and how far from the national rate? |
| Compare groups | Women vs men, urban vs rural, B40 vs T20, by age or ethnicity, where the source splits it |
| Relative to people or the economy | Per person, per household, % of GDP, in real terms |
| Gap between sources | Does BNM agree with the audited accounts? |
| Gap between stages | Announced → budgeted → spent → audited: where does the money drop? |
| Target vs outcome | Did the plan hit its own target? |
| Who and where | Which agency, which contractor, which district? |
| Against other countries | How does Malaysia compare with its peers? |
| What is missing | Which states do not publish this, since when? |

**Questions across themes** are the point of one warehouse, not nine separate ones:

* Do the districts with the highest poverty (theme 1) receive more development money per
  person (theme 5)?
* Is household debt (theme 8) rising faster where wages (theme 2) are flat and prices
  (theme 3) are rising?
* Do states with weak budget transparency (theme 7) also show bigger gaps between budget and
  actual spending (theme 5)?
* Do clinics and schools (theme 6) follow population growth (theme 1)?
* Did fuel subsidy spending (theme 5) move with fuel prices (theme 3), and who benefited?
* When an audit finding names a project (theme 7), what happened to that place's outcomes
  (themes 1, 2, 6)?

**When a question cannot be answered yet**, the answer says why: the document is
`expected`, `restricted` or `not_published` in the registry. The question is logged
(`meta.question_log`), and logged questions decide which documents are collected next. The
plan grows from the questions people actually ask.

---

## Theme 1: People & poverty

**Example questions (not a limit):** Where are the poorest districts and DUNs? Is poverty falling everywhere, or
only on average? Which groups are left behind (women-headed households, rural, elderly)? Is
inequality within a state widening? Does money reach the areas that need it?

| Have | Need |
|---|---|
| HIES 2019–2024: income, poverty, inequality, state to DUN | **P1** population by state and district: every per-capita figure depends on it |
| | **P1** DOSM Household Income Survey report tables: strata, ethnicity, income source, disposable income, household head |
| | **P1** cash-transfer and welfare recipients by state (places operating spending, theme 5) |
| | P2 Census 2020; Kawasanku constituency profiles; MyWI and happiness indices (components stored separately) |
| | P2 DOSM data requests for tabulations not published |
| | P3 zakat collection and distribution by state |
| | restricted: PADU / eKasih (aggregates via parliamentary answers only) |

**Gap views it enables:** need vs money (`gap_need_vs_money`), poverty by DUN vs federal
spending in that DUN.

## Theme 2: Jobs & wages

**Example questions (not a limit):** Where is unemployment highest, for youth especially? Are wages keeping up
with prices? How many people are underemployed or in informal work? Which sectors create jobs,
and where? Is retirement saving enough?

| Have | Need |
|---|---|
| LFS: national monthly, state quarterly, district/parlimen/DUN annual | **P1** salaries & wages survey: median wage by state and sector |
| productivity 2015–2025 | **P1** LFS annual report tables: strata, age × sex, education, skill |
| | P2 EPF and SOCSO statistics; PERKESO job vacancies; P3 DOSM employment statistics |

## Theme 3: Prices & cost of living

**Example questions (not a limit):** Is the cost of living rising faster in some states? Which essential items
rise fastest? Can households afford a house? What happens to prices when a subsidy changes?

| Have | Need |
|---|---|
| CPI national and state 2010–2026 | **P1** Household Expenditure Survey report: median spending, COICOP by decile and state |
| | P2 CPI detail (3–5 digit, low-income, urban/rural) |
| | P2 PriceCatcher item-level prices by place |
| | P2 house price index by state (NAPIC) |
| | P3 retail fuel prices (pairs with subsidy spending) |

## Theme 4: Output & industry

**Example questions (not a limit):** Which states are growing, and from what? Is approved investment turning into
real investment, and jobs? How dependent is the economy on oil and gas, or on a few exports?
Is productivity rising?

| Have | Need |
|---|---|
| GDP quarterly and annual; state GDP 2015–2025 | P2 approved investment by state (MIDA) |
| IPI, PPI, trade, FDI | P2 Economic Census 2023 (establishments by place); district GDP (existence to confirm) |
| | P2 PETRONAS accounts (dividends; royalties to producing states) |
| | P3 energy statistics; IMF WEO and World Bank peer data |

## Theme 5: Public money & money trail

**Example questions (not a limit):** Was the budget spent as approved? How much reached each state and district,
and through whom? How much is owed but not yet on the books (guarantees, PFI)? How dependent
are states on federal transfers? Do states publish their own budgets?

| Have | Need |
|---|---|
| PKKP audited federal accounts FY2009–2024 (down to project) | **P1** development estimates (project-level budget): the missing half of budget vs actual |
| Anggaran (operating) Budget 2024–2026; Anggaran Hasil 2025–2026 | **P1** federal development allocation by state (existence to confirm) |
| Tinjauan Fiskal 2019–2027 editions | **P1** state budget estimates (*Buku Belanjawan*), all 13 states |
| BNM federal finance 1996–2026 | P2 state enacted budgets, budget speeches |
| audited state statements, 13 states FY2014–2024 | P2 Laporan Ekonomi 2010–2018 (MOF figures FY2009–2014); budget speech commitments |
| | **P1** cash-transfer and welfare recipients and amounts by state (STR, JKM) |
| | P2 supplementary estimates; LHDN reports; constituency development funds by parlimen/DUN; GLIC accounts; PFI/PPP register |
| | P3 tax expenditure; local authority (PBT) finances |
| | P3 state Supply Bills |

**Gap views it enables:** budget vs actual, revenue estimate vs collected, reported vs
audited, federal vs state, need vs money.

## Theme 6: Health, education & services

**Example questions (not a limit):** Are doctors, beds and good schools where the people are? Are outcomes
(life expectancy, exam results, dropouts) improving everywhere? Does spending per pupil or
patient differ by state?

| Have | Need |
|---|---|
| household access to amenities by district 2016–2024 | **P1** National Health and Morbidity Survey (health outcomes) |
| | **P1** health facts by state (doctors, beds, facilities) |
| | **P1** education statistics and school data by district |
| | P2 Basic Amenities Survey report (ICT, distance to services, tenure); causes of death; KPM data requests |

This theme is the thinnest today, and the one most directly about people's daily lives.

## Theme 7: Accountability

**Example questions (not a limit):** What did the Auditor-General find, and was it fixed? Do the same bodies get
the same findings every year? Who won the contracts, and how? How open is each state's budget,
and is it getting better?

| Have | Need |
|---|---|
| LKAN federal 2024–2026 extracted (426 findings); 402 volumes 2015–2026 held | **P1** procurement awards (project → contractor) |
| AG agency opinions FY2023–2024 | P2 federal and state PAC reports; AG action-status dashboard; Dewan Rakyat Hansard and written answers |
| | P2 Pantau Projek and Pantau Laksana (IDEAS); state PAC reports |
| | P3 DUN hansards, DUN questions, IBP Open Budget Survey |
| | restricted: SSM company register (paid per lookup) |

## Theme 8: Money, credit & financial wellbeing

**Example questions (not a limit):** Are households over-borrowed? Who is going bankrupt, and where? How do
interest-rate changes reach borrowers? Is credit going to productive uses?

| Have | Need |
|---|---|
| BNM: OPR, rates, FX, money supply, lending by purpose | P2 household debt (BNM Financial Stability Review) |
| | P2 EPF and SOCSO statistics |
| | P3 bankruptcy statistics by state |

## Theme 9: Environment, climate & disasters

**Example questions (not a limit):** Which districts flood most often, and how much relief reached
them? Is the energy transition on track? Which places are most exposed to climate risk?

| Have | Need |
|---|---|
| — | P2 NADMA disaster events, victims and relief spending by district |
| | P3 JPS flood events; greenhouse-gas inventory (UNFCCC reports); energy statistics |
| | deferred: ND-GAIN climate vulnerability, FAOSTAT food dependence |

Housing, water, transport and ICT sit in theme 6 (services).

## Plan targets (all themes)

**Example questions (not a limit):** Did the government hit its own targets? Which targets have no funded budget
line, and which budget lines have no target?

| Have | Need |
|---|---|
| — | **P1** RMK-12 Mid-Term Review and RMK-13 targets |
| | P2 NIMP 2030, NETR, Ekonomi MADANI targets |
| | P2 constituency delimitation reports and boundary files; district list and boundary changes (144 districts in 2016 → 166 in 2024) |
| | P2 DOSM SDG Indicators Malaysia (national SDG reporting) |

---

## Release calendar: when to expect new documents

| When | What | Source of the rule |
|---|---|---|
| October | Federal Budget: Anggaran, Anggaran Hasil, Tinjauan Fiskal, budget speech | MOF practice (Budget 2027 edition held) |
| November – December | State budgets tabled in each DUN (dates to record per state) | each state assembly's calendar |
| through the year | LKAN volumes, tabled in series | `lkan_reports_backfill.csv` tabling dates |
| per dataset | DOSM releases | `next_update` in `sources/dosm/data/_vintage.json`, checked by `refresh.py` |

The registry records when each document actually appeared, so a late or missing document
becomes a dated finding.

---

## Still open from earlier work

* **FY2009–2014 MOF fiscal figures:** before Budget 2019 MOF printed these in the *Laporan
  Ekonomi*. The registry row `laporan_ekonomi` tracks it. Until then BNM MSB 3.1 is the complete
  series.
* **LKAN backfill:** 402 volumes are held with sha256. Findings are extracted for 2024–2026
  only.
