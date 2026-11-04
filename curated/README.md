# Curated / consolidated layer

The comparable layer built **on top of** the per-source data in `sources/`. Sources are
never blended raw — this layer conforms shared dimensions so they can be compared and gaps
surfaced with a full audit trail back to each source.

Planned contents (build as sources land):
- **Conformed dimensions:** fiscal year; ministry/`maksud`; economic (object) classification;
  state/jurisdiction; program. A crosswalk maps each source's codes onto these.
- **Consolidated facts:** e.g. a spend fact carrying `source`, `jurisdiction` (federal/state),
  `year`, `maksud`, `measure` (budgeted / actual / reported), so budget-vs-actual and
  federal-vs-state comparisons are one query.
- **Gap views:** budgeted vs actual, estimate vs collected, audited vs headline-reported,
  planned vs delivered — see `docs/SOURCES.md` for the pairings.

## Here now

- **`fact_budget_vs_actual.csv`** — the first **budget-vs-actual gap view** (pilot **FY2024**),
  per ministry vote (`maksud`), split operating vs development, with variance and %
  utilisation. Built by `pipeline/build_gap_views.py`; reconciled to the sen
  (`_validation_gap_2024.csv`, 6/6 PASS) and independently verified. **Full schema, the
  important "what budget means" caveat, and the FY2024 findings are in
  [`GAP_VIEWS.md`](GAP_VIEWS.md) — read it before using the data.**

  Interim note: the independent *Anggaran Perbelanjaan* budget book (source #2) is not yet
  ingested (not machine-readable; its host is blocked by the current egress policy), so this
  pilot's "budget" is PKKP's own recorded appropriation. It slots an independent budget — and
  an Anggaran-vs-PKKP cross-check — in as soon as source #2 lands.

- **`fact_obligations.csv`** — the **obligations layer**: what the federal government owes
  (debt, PFI, financial commitments incl. unpaid tax refunds, committed guarantees by
  entity, statutory/contingent guarantees) and is owed (receivables / revenue arrears),
  unified across PKKP's audited Penyata Akaun Memorandum (FY2009–FY2024), the
  Auditor-General's LKAN 3/2025 fiscal tables and the MOF Fiscal Outlook fiscal-risk
  tables. Built by `pipeline/build_obligations.py`; `_validation_obligations.csv`
  (94/94 PASS) ties every register to its own printed total and cross-checks the three
  sources against each other. **Class map, do-not-sum warnings and era caveats are in
  [`OBLIGATIONS.md`](OBLIGATIONS.md) — read it before using the data.**

## Derived labour indicators (`fact_labour_indicators.csv`)

`basis='derived'` — **not** DOSM statistics. DOSM publishes no salaries-and-wages
dataset through its API (verified against all 289 data.gov.my and 182 OpenDOSM ids;
the Salaries & Wages Survey is a PDF publication on an unreachable host, and the
Labour Force Survey carries no income field). Until that survey is acquired
(docs/SOURCES.md Tier 1b), these two indicators fill the gap from sources already
held:

- `implied_average_wage_rm_per_worker_year` = compensation of employees (income-approach
  GDP, `component=i1`) ÷ employed persons (LFS `lf_employed`), 2010–2023.
- `labour_share_of_gdp_pct` = compensation of employees ÷ GDP (`i0`) × 100.

**Read the caveats before quoting either.** The denominator counts all employed
persons while the numerator counts only employees, so the wage figure *understates*
the average employee wage by roughly the self-employed share — it is a consistent
series, not a level estimate. Compensation includes employer EPF/SOCSO contributions,
so it is labour cost, not take-home pay. Both are national and nominal; no sector,
state, occupation or percentile detail is derivable, which is precisely what the
missing survey would provide. Built by `pipeline/build_labour_indicators.py`,
29 checks in `_validation_labour.csv`.

## Canonical ministry lineage + national headline

Built by `pipeline/build_ministry_fiscal.py` from `sources/pkkp/pkkp.duckdb`, with
`sources/mof-fiscal-outlook/` and `sources/bnm/` as independent references. Checks land in
`_validation_ministry_fiscal.csv` (534 checks: 488 PASS, 35 cross-source AGREE, 1
cross-source DIVERGE, 6 individually-classified known defects, 3 uncaptured-cell flags
and 1 known gap — see below), with every known defect justified one by one in
`_known_extraction_defects_curated.csv`.

- **`dim_maksud_canonical.csv`** — the ministry-vote crosswalk: 93 raw `maksud_code`s
  across FY2009–2024 mapped to a canonical code, so a ministry's series survives a
  renumbering. Joins are code-to-code throughout (golden rule 4); no name matching.

  **Caveat before plotting a canonical series.** Four codes are merged into another
  code's lineage (`B.41→B.63`, `P.41→P.63`, `B.49→B.64`, `P.49→P.64` — Education and
  Higher Education, renumbered in FY2015). No printed volume presents those as one
  continuous series; the continuity is *ours*, and `is_merged=True` marks every row where
  it applies. A step at the join year is a renumbering artefact until proven otherwise.
  Codes with a thematic echo but no evidence of continuity (e.g. `B.44` → `B.14`) are
  deliberately **not** merged; each such judgment call is written out in the `note`
  column so a reviewer can overturn it with a Cabinet reorganisation order or a Bajet
  footnote.

  A second caveat: Higher Education (`B.64`/`P.64`) has no FY2014 or FY2019 row because
  the portfolio sat inside Education those years. Those years are **missing, not zero** —
  do not read the gap as a collapse in higher-education spending.

- **`fact_ministry_fiscal.csv`** — 1,267 rows, one per (`canonical_code`, `jenis`,
  `year`). **Always gross**, always `basis='audited (PKKP)'`, and every row carries
  `source_dataset`, `source_file`, `pdf_pages`, `statement`, `n_source_rows` and the
  `raw_codes` it was aggregated from, so any figure goes straight back to the printed
  page. Opex comes from the ministry-level statement; devex sums leaf rows only
  (`row_type='project'`, golden rule 5), except FY2015 where the leaf tier is
  OCR-provisional and the ministry totals are substituted — flagged per row in `note`.

  **Check `data_quality` before summing.** Three rows are `suspect`: `P.26`, `P.44` and
  `P.45` devex FY2009, where 21 leaf cells between them have **no captured amount in the
  source CSV**. The extraction convention renders a printed en-dash as `0.0`, so a NULL is
  *our* gap, not a printed nil — those rows are understated by an unknown amount, and
  `n_source_rows_uncaptured` says by how many cells. Every other row is `ok`.

  There is **no net figure here and there will not be one.** The netting entries
  (transfer to the Development Fund; loan recovery) are whole-of-government entries with
  no per-ministry attribution in any source. A "net" ministry figure would have to be
  invented.

- **`fact_fiscal_headline.csv`** — 16 national rows, FY2009–2024. Every amount column has
  a `*_basis` column beside it.

  All three operating-expenditure figures — `opex_net_rm` (before the transfer to the
  Development Fund), `transfer_to_dev_fund_rm`, and `opex_gross_rm` (after it) — are read
  **as printed, to the sen**, off the same page of the Consolidated Revenue Account
  (*Nota 5 / Penyata Akaun Hasil Disatukan*), with `opex_source_file`, `opex_pdf_page`,
  `opex_printed_page`, `opex_source_statement` and the Malay line label used
  (`opex_net_line_bm` / `opex_gross_line_bm`, which change with the volume era). Nothing
  is derived by subtraction: the build proves `net + transfer == gross` to the sen for
  every year and stops if it does not. `devex_gross_rm` is `audited (PKKP)`.
  Net development expenditure is deliberately split across **two columns that are never
  spliced**:

  | column | source | years | basis |
  |---|---|---|---|
  | `devex_net_rm` | MOF Tinjauan Fiskal, with `devex_net_source_file` / `_pdf_page` / `_printed_page` per row | 2017–2019, 2024 | `official_actual (MOF Tinjauan Fiskal)` |
  | `devex_net_bnm_rm` | BNM Monthly Statistical Bulletin 3.1 (`sources/bnm/data/msb_3_1.csv`) | 2009–2024, complete | `reported (BNM MSB 3.1)` |

  Where both exist they agree to RM0.33 juta or better — MOF prints net DE in whole RM
  juta while BNM publishes to the sen, which accounts for the whole of the difference. **They are still two different
  publications on two different bases** — take one column or the other for a series;
  a chart that switches between them mid-way is a basis blend, which is what the
  separate columns exist to prevent. `devex_net_rm` is NULL for FY2009–2016 and
  FY2020–2023 not because MOF never published those figures but because the Tinjauan
  Fiskal editions carrying them are not ingested here yet — an open ingestion gap
  (`docs/SOURCES.md`), stated rather than papered over.

  **Revenue, the COVID-19 fund and the overall balance.** `revenue_rm` is total federal
  revenue as printed. `covid_fund_rm` is spending through the *Kumpulan Wang COVID-19*,
  which in FY2020–2022 (RM38.0b, RM37.7b, RM31.0b) sat **outside both opex and devex** —
  read to the sen from each volume's Lampiran 3 and checked against the Penyata Prestasi
  Kewangan. `covid_fund_status` says which: `printed`, `printed_nil` (FY2023–2024), or
  `not_established` (FY2009–2019, NULL — the fund did not exist, which is not the same as
  zero spending).

  `overall_balance_rm` = revenue − `opex_net_rm` − `devex_net_bnm_rm` − COVID-19 fund. This
  is **MOF's definition**, and it agrees with MOF's own published overall balance in all
  four years MOF prints one (FY2017–2019, FY2024; worst case RM0.49 juta). PKKP's 15-year
  panel prints a *different* overall balance: it nets off all of the Development Fund's
  "Lain-lain" receipts, not only loan recovery, so it can sit RM0.1–1.9b away (FY2024:
  PKKP −77,315, MOF −79,166 juta; the gap is exactly the non-loan receipts). That
  difference is reported in the validation file as `DEFINITIONAL`, never as a divergence.
  Don't compare the two as if they were the same concept.

### One finding, and one mess that is partly ours

- **FINDING — FY2023 development expenditure, BNM vs PKKP: RM1,247,043 apart.** BNM MSB
  3.1 reports RM96,090,984,165.51; the audited PKKP volume prints RM96,089,737,122.54,
  and PKKP is internally consistent that year (leaf rows = ministry totals = printed grand
  total, to the sen). BNM matches PKKP *to the sen* in every other year from FY2018, which
  is what makes FY2023 worth flagging. Recorded as `DIVERGE`; neither side is adjusted.
  This one is a genuine cross-source divergence.

- **NOT A FINDING — the FY2009 devex leaf gap (RM410,577,250).** The volume's leaf tier
  sums short of its own printed grand total. An earlier version of this file published
  that as the volume's own inconsistency. **It is not, or at least not mostly.** Broken
  down per ministry, the six mismatching votes classify as:

  | vote | gap | classification |
  |---|---|---|
  | `P.47` | −RM424,602,409 | **ours (suspected)** — the printed JUMLAH row reads 944,340,000.00 in four columns at once with `pinjaman` nil, the signature of one column being read across the row |
  | `P.26` | +RM262,323,513 | source-documented — printed JUMLAH is 0.00 above non-zero projects; the PKKP source's own validation records the FY2009 reorganisation that causes it. Its **11 uncaptured leaf cells are ours** |
  | `P.44` | +RM5,077,629 | source-documented, same reorganisation; its **9 uncaptured leaf cells are ours** |
  | `P.10` | −RM30,000,000 | unproven — an exactly-round gap in the leaf tier, JUMLAH row itself reads cleanly |
  | `P.29` | +RM3,520,173 | unproven — the only vote where the leaf tier *overshoots* |
  | `P.45` | −RM2,563,649 | **ours (proven)** — exactly one uncaptured leaf cell, projek 00616 *Pusat Latihan Khas* |

  So the single largest component, 82% of the gap, most likely belongs to our extraction,
  not to the Accountant-General. Neither `ours_suspected` nor `unproven` can be settled
  without re-reading the printed pages, which this repo does not hold (PDFs are not
  committed). Until then **none of it is published as a source-side inconsistency.** Full
  diagnosis per vote, with the evidence for each classification, is in
  **`_known_extraction_defects_curated.csv`**.

  The headline uses the printed grand total; `fact_ministry_fiscal` sums the leaf rows;
  the difference is recorded, not closed.

### Reading `_validation_ministry_fiscal.csv`

`check_type` says what kind of claim a row makes, and the status vocabulary differs on
purpose so an approximate agreement can never be mistaken for an exact one:

| `check_type` | statuses | meaning |
|---|---|---|
| `identity` | `PASS` / `FAIL` | must hold to the sen (`band_rm` = 0.01) — including the printed `net + transfer == gross` for every year, and BNM's own `net = gross − loan recovery`. A `FAIL` fails the build. |
| `cross_tier` | `PASS` / `FAIL` | two tiers of the **same** audited volume: per-maksud statement vs the account it rolls into, and each ministry's leaf rows vs its own printed JUMLAH. Band RM1.00 for opex (FY2010 and FY2020 differ by the statements' own ringgit rounding), sen-exact for devex. A `FAIL` fails the build. |
| `cross_source` | `AGREE` / `DIVERGE` | two *institutions* publishing the same concept. Band RM100,000 against BNM (sen-published), RM500,000 where MOF prints in whole juta. A `DIVERGE` is a **finding**, reported loudly, and does not fail the build. |
| `known_defect` | `KNOWN_OURS_PROVEN`, `KNOWN_OURS_SUSPECTED`, `KNOWN_UNPROVEN`, `KNOWN_SOURCE_DOCUMENTED` | an individually-justified exception from `_known_extraction_defects_curated.csv`. **Not a blanket tolerance:** any leaf-vs-JUMLAH mismatch *not* in that register fails the build. |
| `extraction_gap` | `UNCAPTURED` | a row summing leaf cells that have no captured amount; the row is understated by an unknown amount and carries `data_quality='suspect'`. |
| `known_gap` | `KNOWN_GAP` | a gap we record and do not close. |
| `definitional` | `DEFINITIONAL` | two publications printing *differently defined* versions of one concept (MOF vs PKKP overall balance). The diff is information, not error. |

A note on the bands. Until this revision `opex_net_rm` was *derived* by subtracting a
figure taken from PKKP's 15-year fiscal panel, which publishes in RM juta — so every year
carried up to RM930,380 of our own rounding, and the RM1.0 juta cross-source band was
quietly absorbing it rather than measuring a publication difference. Reading the printed
sen-exact line instead collapsed the spread against BNM from RM930,712 to RM96,529, with
four years now agreeing **to the sen**, and the band was tightened to match.

### `_known_extraction_defects_curated.csv`

Our defects, kept strictly separate from the source's. One row per known mismatch, each
with `classification` ∈ {`ours_proven`, `ours_suspected`, `source_documented`,
`unproven`}, a written diagnosis and the evidence for it. The separation is the point: a
gap that is ours must never be published as the Auditor-General's or the
Accountant-General's, and `ours_suspected`/`unproven` are not promoted to findings just
because the printed page is out of reach.

## MOF expenditure breakdowns

Built by `pipeline/build_opex_devex_breakdown.py` as a thin pass-through of MOF Tinjauan
Fiskal's own Jadual 3.1/3.2/3.3 — finer than anything derivable from PKKP or DOSM alone.
Every row carries `basis`, `source_edition`, `source_table`, `source_file`, `pdf_page`
and `printed_page`.

- **`fact_opex_by_component.csv`** (75 rows) — operating expenditure by object:
  emoluments, pensions, debt service, subsidies, supplies, grants, asset acquisition.
- **`fact_opex_by_sector.csv`** (95 rows) — operating expenditure by sector, two levels.
- **`fact_devex_by_sector.csv`** (90 rows) — development expenditure by sector
  (economic / social / security / general administration), two levels.

All three currently come from the **2021 edition only** and cover FY2017–2021. Filter on
`basis`: FY2017–2019 rows are `official_actual`, FY2020 is `official_revised` and FY2021
is `official_projection`. Mixing them produces a series that is part outturn and part
forecast. The source ingestion's own 80 identity checks
(`sources/mof-fiscal-outlook/data/2021_public_finance_stats/_validation.csv`) all PASS.
