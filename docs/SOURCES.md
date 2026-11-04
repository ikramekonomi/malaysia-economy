# Source plan: documents and APIs by theme

What the warehouse needs, theme by theme: what we hold, what we must get, and how we get it
(an API to connect, or a document to collect). The **row-level detail is in
`docs/registry/series_seed.csv`** (60 series). This page is the plan; the registry is the
checklist. How the registry works: `docs/DOCUMENT_REGISTRY.md`. How the data fits together:
`docs/DATA_MODEL.md`.

**Wording:** we say **public money** (*wang awam*), not "government money". The money
belongs to the public, and the term covers federal, state, statutory bodies and GLCs. The
Financial Procedure Act 1957 uses the same term ("public moneys").

## At a glance

| # | Theme | Held | Must get first (P1) | Main way in |
|---|---|---|---|---|
| 1 | People & poverty | 1 of 5 | population by state and district | API (OpenDOSM) |
| 2 | Jobs & wages | 2 of 4 | salaries & wages survey | API (OpenDOSM) |
| 3 | Prices & cost of living | 1 of 4 | (P2: item prices, house prices) | API (data.gov.my) + PDF |
| 4 | Output & industry | 3 of 10 | (P2: investment, district GDP) | API (OpenDOSM) |
| 5 | Public money & money trail | 6 of 20 | development estimates; federal development money by state; state budget estimates | PDF |
| 6 | Health, education & services | 1 of 3 | health facts; education statistics | PDF + data.gov.my |
| 7 | Accountability | 3 of 13 | procurement awards | PDF + web |
| 8 | Money, credit & financial wellbeing | 1 of 5 | (P2: household debt, EPF/SOCSO) | API (BNM) + PDF |
| — | Plan targets (all themes) | 0 of 3 | Malaysia Plan targets (RMK-12 MTR, RMK-13) | PDF |

"Held" counts series that are held, extracted or verified. A series can serve two themes,
so the column does not add to 60.

**The pattern:** the economy themes (1–4, 8) mostly come through **APIs we already use**, so
each new series costs little. Public money and accountability (5, 7) come from **PDFs**. These
are slow, but they are where the advocacy findings are, and where nobody else has the data in
usable form.

---

## APIs: connected and to connect

| API | Publisher | Status | Gives us |
|---|---|---|---|
| `api.data.gov.my` (OpenDOSM + data catalogue) | DOSM / data.gov.my | **connected** | national accounts, HIES, LFS, CPI, trade, state GDP |
| `storage.dosm.gov.my` (bulk files) | DOSM | **connected** | the canonical CSVs behind the API |
| `api.bnm.gov.my` (OpenAPI) | BNM | **connected** | federal finance, rates, FX, money supply, credit |
| data.gov.my datasets (ids to confirm) | DOSM, KPDN, MOF, KPM | to connect | population by state/district, PriceCatcher, fuel prices, education |
| IMF DataMapper API | IMF | to connect | WEO peer benchmarks (general-government basis) |
| World Bank Indicators API | World Bank | to connect | peer benchmarks |
| IBP Open Budget Survey data | IBP | to download | the federal transparency score |

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

## Theme 1: People & poverty

**Questions:** Where are the poorest districts and DUNs? Is poverty falling everywhere, or
only on average? Does money reach the areas that need it?

| Have | Need |
|---|---|
| HIES 2019–2024: income, poverty, inequality, state to DUN | **P1** population by state and district: every per-capita figure depends on it |
| | P2 Census 2020 (small-area detail) |
| | P3 zakat collection and distribution by state |
| | restricted: PADU / eKasih (aggregates via parliamentary answers only) |

**Gap views it enables:** need vs money (`gap_need_vs_money`), poverty by DUN vs federal
spending in that DUN.

## Theme 2: Jobs & wages

**Questions:** Where is unemployment highest, for youth especially? Are wages keeping up?

| Have | Need |
|---|---|
| LFS: national monthly, state quarterly, district/parlimen/DUN annual | **P1** salaries & wages survey: median wage by state and sector |
| productivity 2015–2025 | P2 EPF and SOCSO statistics: savings adequacy, job-loss claims |

## Theme 3: Prices & cost of living

**Questions:** Is the cost of living rising faster in some states? Can households afford
a house?

| Have | Need |
|---|---|
| CPI national and state 2010–2026 | P2 PriceCatcher item-level prices by place |
| | P2 house price index by state (NAPIC) |
| | P3 retail fuel prices (pairs with subsidy spending) |

## Theme 4: Output & industry

**Questions:** Which states are growing, and from what? Is approved investment turning into
real investment?

| Have | Need |
|---|---|
| GDP quarterly and annual; state GDP 2015–2025 | P2 approved investment by state (MIDA) |
| IPI, PPI, trade, FDI | P2 district GDP (existence to confirm) |
| | P2 PETRONAS accounts (dividends; royalties to producing states) |
| | P3 energy statistics; IMF WEO and World Bank peer data |

## Theme 5: Public money & money trail

**Questions:** Was the budget spent as approved? How much reached each state and district,
and through whom? Do states publish their own budgets?

| Have | Need |
|---|---|
| PKKP audited federal accounts FY2009–2024 (down to project) | **P1** development estimates (project-level budget): the missing half of budget vs actual |
| Anggaran (operating) Budget 2024–2026; Anggaran Hasil 2025–2026 | **P1** federal development allocation by state (existence to confirm) |
| Tinjauan Fiskal 2019–2027 editions | **P1** state budget estimates (*Buku Belanjawan*): 7 of 13 states publish |
| BNM federal finance 1996–2026 | P2 state enacted budgets (Terengganu only), budget speeches (10 of 13) |
| audited state statements, 13 states FY2014–2024 | P2 Laporan Ekonomi 2010–2018 (MOF figures FY2009–2014); budget speech commitments |
| | P2 constituency development funds by parlimen/DUN; GLIC accounts; PFI/PPP register |
| | not published: state Supply Bills (0 of 13) |

**Gap views it enables:** budget vs actual, revenue estimate vs collected, reported vs
audited, federal vs state, need vs money.

## Theme 6: Health, education & services

**Questions:** Are doctors, beds and good schools where the people are?

| Have | Need |
|---|---|
| household access to amenities by district 2016–2024 | **P1** health facts by state (doctors, beds, facilities) |
| | **P1** education statistics and school data by district |

This theme is the thinnest today, and the one most directly about people's daily lives.

## Theme 7: Accountability

**Questions:** What did the Auditor-General find, and was it fixed? Who won the contracts?
How open is each state's budget?

| Have | Need |
|---|---|
| LKAN federal 2024–2026 extracted (426 findings); 402 volumes 2015–2026 held | **P1** procurement awards (project → contractor) |
| AG agency opinions FY2023–2024 | P2 federal and state PAC reports; AG action-status dashboard |
| | P2 MyOBI scores 2022/2024/2026 (2026 PDF supplied, not yet ingested) |
| | P3 DUN hansards (10 states), DUN questions (about half), IBP Open Budget Survey |
| | restricted: SSM company register (paid per lookup) |

## Theme 8: Money, credit & financial wellbeing

**Questions:** Are households over-borrowed? Who is going bankrupt, and where?

| Have | Need |
|---|---|
| BNM: OPR, rates, FX, money supply, lending by purpose | P2 household debt (BNM Financial Stability Review) |
| | P2 EPF and SOCSO statistics |
| | P3 bankruptcy statistics by state |

## Plan targets (all themes)

**Question:** Did the government hit its own targets?

| Have | Need |
|---|---|
| — | **P1** RMK-12 Mid-Term Review and RMK-13 targets |
| | P2 NIMP 2030, NETR, Ekonomi MADANI targets |
| | P2 constituency delimitation reports and boundary files (to link data across boundary changes) |

---

## Release calendar: when to expect new documents

| When | What | Source of the rule |
|---|---|---|
| October | Federal Budget: Anggaran, Anggaran Hasil, Tinjauan Fiskal, budget speech | MOF practice (Budget 2027 edition held) |
| 1 Nov – 31 Dec | State budget proposals (speech, estimates) should be public | MyOBI 2026 timeliness standard (Table 2) |
| before 1 Jan | State enacted budgets should be public | MyOBI 2026 Table 2 |
| Jan – Jun | State year-end reports (previous year) should be public | MyOBI 2026 Table 2 |
| Jan – Sep | State audit reports (year before last) should be public | MyOBI 2026 Table 2 |
| through the year | LKAN volumes, tabled in series | `lkan_reports_backfill.csv` tabling dates |
| per dataset | DOSM releases | `next_update` in `sources/dosm/data/_vintage.json`, checked by `refresh.py` |

The MyOBI dates are what *should* happen. The registry records what *did*, so a late or
missing document becomes a dated finding.

---

## What MyOBI 2026 tells us

IDEAS' Malaysia Open Budget Index (August 2026; two of its 13 state assessors were from
IKRAM) scores whether **state budget documents are published**, how strong the oversight is,
and how much the public can take part. It does not hold the numbers inside those documents.
The two efforts fit together:

| | MyOBI | This warehouse |
|---|---|---|
| Asks | Is the document public and on time? | What do the numbers say, and do they add up? |
| Covers | 13 states; transparency, oversight, participation | federal + 13 states; the whole economy |
| Output | a score per state, peer reviewed, every two years | every figure, with its source page, checked |

We use MyOBI as the **evidence for state document statuses** in the registry (for example, that
no state published its 2026 Supply Bill). We ingest its scores as an accountability series.
The one document MyOBI finds every state has, the Auditor-General's report, is the one we
already hold and have turned into data for all 13 states.

---

## Still open from earlier work

* **FY2009–2014 MOF fiscal figures:** before Budget 2019 MOF printed these in the *Laporan
  Ekonomi*. The registry row `laporan_ekonomi` tracks it. Until then BNM MSB 3.1 is the complete
  series.
* **LKAN backfill:** 402 volumes are held with sha256. Findings are extracted for 2024–2026
  only.
