# Source: MOF Fiscal Outlook (Tinjauan Fiskal / Fiscal Outlook)

Official Ministry of Finance projections for federal revenue, expenditure, deficit and debt
— the government's own forward numbers for FY2025–FY2026. Published each October alongside
the Budget on **belanjawan.mof.gov.my** (English: "Fiscal Outlook and Federal Government
Revenue Estimates"; also mirrored on treasury.gov.my).

## Status: INGESTED (headline grain), verified 2026-07-31

`data/fiscal_outlook_headline.csv` carries the headline figures of both editions:

| document | retrieved from | pages | covers |
|---|---|---|---|
| `tinjauan_fiskal_2025.pdf` (Budget 2025 edition, Oct 2024) | https://belanjawan.mof.gov.my/pdf/belanjawan2025/hasil/tinjauan_fiskal_2025.pdf | 277 | 2024 revised estimates + 2025 budget estimates |
| `tinjauan_fiskal_2026.pdf` (Budget 2026 edition, Oct 2025) | https://belanjawan.mof.gov.my/pdf/belanjawan2026/hasil/tinjauan_fiskal_2026.pdf | 270 | 2024 outturn + 2025 revised + 2026 budget estimates |

PDFs live in `raw/` (gitignored — re-download from the URLs above; retrieved 2026-07-31).
Both are bilingual (BM section first, EN section second); BM and EN tables agree
figure-for-figure on everything extracted.

### Verification

- `pipeline/validate_headline.py` reconciles the CSV to the documents' own printed totals
  (current-balance / net-DE / overall-balance identities and every %GDP row against the
  printed nominal GDP) → `data/_validation_headline.csv`: **23/23 PASS**.
- Independent adversarial verifier pass (separate agent, blind to this extraction,
  re-derived every figure from the PDFs, cross-checking BM vs EN sections and a page
  render for cells with a defective text layer): **full agreement** on all figures.
- Source anomalies catalogued (never corrected) in `data/_source_anomalies.csv` —
  notably the 2026 edition prints the 2024 gross/net DE %GDP pair transposed, and its
  Table 1.1 bold rows are missing from the PDF text layer (font defect), so the headline
  CSV cites the Key Data spread for those figures.

## Also extracted — `data/2021_public_finance_stats/` (Jadual 1.1, 3.1, 3.2, 3.3)

The "Statistik Kewangan Awam / Public Finance Statistics" appendix of the **Tinjauan
Fiskal 2021** edition (`raw/2021/st_kewangan.pdf`, the 20-page statistical-tables appendix —
not the narrative report; first transcribed from a user-uploaded copy of the same appendix) — the same appendix
format that carries MOF's finer OPEX/DEVEX breakdowns than anything else in this
warehouse:

| table | contents | years covered | file |
|---|---|---|---|
| 1.1 | Federal Government Finance (revenue, opex, devex gross/net, overall & primary balance, financing) | 2017-2021 | `fact_headline.csv` |
| 3.1 | Operating Expenditure by Component (emoluments, retirement, debt service [dom/ext], grants to state govts [constitutional/other], supplies & services, subsidies & SA, asset acquisition, refunds & write-offs, grants to statutory bodies, others) | 2017-2021 | `fact_opex_by_component.csv` |
| 3.2 | Operating Expenditure by Sector (economic/social/security/general admin + sub-functions) | 2017-2021 | `fact_opex_by_sector.csv` |
| 3.3 | Development Expenditure by Sector (same sector structure as 3.2, no "others"-catchall since devex has no debt/retirement/transfer lines) | 2017-2021 | `fact_devex_by_sector.csv` |

**2017-2019 = `official_actual` (unlabelled in source), 2020 = `official_revised`
("Anggaran disemak"), 2021 = `official_projection` ("Anggaran belanjawan tidak termasuk
langkah Belanjawan 2021" — excludes 2021 Budget measures).** This folder covers 2017-2021; the other eight editions now sit beside it (next section).

Extracted by `pipeline/extract_2021_public_finance_stats.py` (every value embedded with
its own `pdf_page`/`printed_page`, read directly off the PDF — nothing recomputed).
Reconciled to the tables' own printed sub-item/parent/Jumlah sums and cross-table
identities (`data/2021_public_finance_stats/_validation.csv`: **80/80 PASS**), plus an
independent adversarial verifier pass (separate agent, blind to the extraction script,
re-transcribed all 4 tables from the PDF and compared cell-by-cell): **full agreement**.

## Nine editions of the statistical appendix — 2019 to 2027

Every edition MOF still publishes on **belanjawan.mof.gov.my** (the archive reaches back to
Budget 2018) has its *Statistik Kewangan Awam / Public Finance Statistics* appendix
ingested, one folder per edition: `data/<edition>_public_finance_stats/`, same four tables
and same schema as the 2021 folder above (plus an `edition` column on every row).

| step | script | output |
|---|---|---|
| fetch | `pipeline/fetch_editions.py` | `raw/<edition>/*.pdf` (gitignored); `data/_editions_manifest.csv` — URL, bytes, sha256, pages, retrieved date per file |
| Jadual 1.1 | `pipeline/extract_public_finance_stats.py` | `fact_headline.csv` per edition |
| Jadual 3.1–3.3 | `pipeline/extract_breakdowns.py` | `fact_opex_by_component.csv`, `fact_opex_by_sector.csv`, `fact_devex_by_sector.csv` |
| reconcile | `pipeline/validate_editions.py` | `_validation.csv` per edition, `data/_validation_editions_summary.csv`, `data/_restatements_editions.csv` |

**Nothing is typed in.** Every figure is read from `pdftotext -layout` output of the
official PDF on the `pdf_page` recorded in its row. Year columns and their basis come from
each page's own header and footnotes (*Anggaran disemak* → `official_revised`,
*Anggaran belanjawan* → `official_projection`, *Awalan* → `official_preliminary`, no
marker → `official_actual`). A label the parser does not recognise stops the build.

| edition | file | actual years | revised | budget |
|---|---|---|---|---|
| 2019 | `st_kewangan.pdf` | 2015–2017 | 2018 | 2019 |
| 2020 | `st_kewangan.pdf` | 2016–2018 | 2019 | 2020 |
| 2021 | `st_kewangan.pdf` | 2017–2019 | 2020 | 2021 |
| 2022 | `st_kewangan.pdf` | 2018–2020 | 2021 | 2022 |
| 2023 | `jadual_perangkaan.pdf` (re-tabled Feb 2023 budget; tables numbered 1.1 / 7.1–7.3) | 2019–2021 | 2022 *preliminary* | 2023 |
| 2024 | `st_kewangan.pdf` | 2020–2022 | 2023 | 2024 |
| 2025 | `st_kewangan.pdf` | 2021–2023 | 2024 | 2025 |
| 2026 | `st_kewangan.pdf` | 2022–2024 | 2025 | 2026 |
| 2027 | `st_kewangan.pdf` | 2023–2025 | 2026 | 2027 |

**The parser is tested against verified data, twice.** Run on the 2021 appendix it
reproduces the hand-transcribed, independently verified 2021 folder exactly — 74/74
headline cells and 75/75, 95/95, 90/90 breakdown cells, basis included
(`data/_parser_check_2021*.csv`). And on the 2025/2026 editions it matches, 20/20, the
headline figures extracted separately from the *full report* in `fiscal_outlook_headline.csv`.

**Reconciliation: 832 checks across the eight new editions, 0 FAIL** — 821 exact, 4 within
the stated rounding bound of their own printed figures, 1 `FOOTNOTED`, 2 `SOURCE_ANOMALY`
(and the 2021 folder's own 80/80). Each printed figure is rounded to the nearest RM juta, so
a sum of *n* printed figures may miss its printed total by up to 0.5 × (*n* + 1) juta; that
bound is written on every check.

### Text-layer hazards handled (each proven on the page, not assumed)

- **2023 edition, shifted font.** The last two year headers' text layer is offset by 0x1D
  (bytes `15 13 15 15` = "2022"); decoded by that offset, and confirmed by the next page,
  which prints the column readably as "2022³".
- **Glued footnote markers.** "51,9734" in the 2019 edition is 51,973 carrying footnote 4
  (a thousands group holds three digits); the cell's note quotes the footnote.
- **Stray superscripts** from the English label bleeding into a values line ("Primary
  balance¹") are ignored when they sit left of every year column.
- **2022 prints shares in parentheses** — "(4.2)", "(100.0)". Read as shares, not
  negatives: a share of spending cannot be negative and the total prints "(100.0)".
- **Unlabelled growth-rate rows** (2019, Jadual 3.3, under *Ekonomi*) are skipped: a share
  never appears without its amount.
- **Dashes in 3.1–3.3** are printed nils, stored as 0.0 (repo convention).
- **Printed page numbers** sit before or after the running title in the footer; in the
  2022/2023 appendices the title is in a font with no usable text layer but the number is
  plain digits. Only the 2019 appendix prints none in its text layer (confirmed on a
  render): `printed_page` is empty there with a note; `pdf_page` is always exact.
- **Table numbers are read from the page**: the 2023 edition numbers its federal-finance
  table **5.1** and its breakdowns **7.1–7.3**.
- **Dashes in Jadual 1.1** are printed nils (0.0) — e.g. the COVID-19 fund in years it spent
  nothing — except in the budget-year financing rows, where a dash means *not printed*.

### What the source itself gets wrong — kept as printed

- **FY2022 domestic debt service, 2024 and 2025 editions:** 40,533 + external 716 = 41,249
  under a printed total of 41,269. Confirmed on a 150-dpi page render. 40,553 is the
  intended figure: the 2023 edition printed it, the row's own 13.9% share fits it (40,533
  would round to 13.8%), and the 2026 edition restates to it. In `data/_source_anomalies.csv`.
- **2019 edition, FY2018 financing:** net domestic borrowing is footnoted *"tidak termasuk
  terbitan bersih bil Perbendaharaan sebanyak RM2 bilion"*, so the financing sources fall
  short of the deficit by exactly RM2,000 juta. `FOOTNOTED`, not an error.

### Restatements and reclassifications

Most actual years are printed by three editions. 30 of 588 line-years differ
(`data/_restatements_editions.csv`): ±RM1 juta rounding revisions, the debt-service fix
above, and reclassifications that net to zero — notably the **2024 edition moving about
RM1.1–1.2 bil a year of FY2020–21 operating expenditure from general administration to
housing**. Two labels change: **"Pertanian dan pembangunan luar bandar"** (2019–2021) becomes
**"Pertanian"** (2022 onward) — a rename, not a redefinition: FY2018–19 print identically
under both labels in three editions. The edition folders keep a separate code per printed
label (`economic_agri_rural`, `economic_agriculture`); the curated layer conforms them.
**"Pelajaran dan latihan"** (2025–2026) is a synonym of "Pendidikan dan latihan" (same
English label, same code).

Which edition the curated layer takes for each year is decided in one place:
`curated/pipeline/mof_editions.py` (each year from its own edition; see `curated/README.md`).

### Not available from here

Editions before Budget 2019 did not carry these tables — MOF published its fiscal tables in
the **Laporan Ekonomi** until then. The 2018 *Anggaran Hasil* book (`raw/2018/`) is fetched
for the record but has no Federal Government Finance table. So MOF's own figures for
FY2009–2014 still need the Laporan Ekonomi, which this site does not hold.

## Also extracted — `data/fact_contingent_liabilities.csv`

The Seksyen 5 (Risiko Fiskal dan Liabiliti) guarantee / contingent-liability tables of both
editions — Jadual 5.1 (Pendedahan Hutang dan Liabiliti), 5.2 (Jaminan Kewangan by
instrument under Akta 850), 5.3 (Penerima Utama Jaminan di bawah Akta 96) and 5.4
(Komitmen Jaminan by entity, incl. 1MDB) — one row per (edition × table × line × column
year), amounts as printed (`value_printed` + normalised `amount_rm`), with share-% and
%KDNK columns where printed. **The second column of every table is an end-June position**
(`asof`). Extracted by `pipeline/extract_contingent_liabilities.py`;
`data/_validation_contingent_liabilities.csv` reconciles every table to its own printed
totals plus cross-table identities (32/32 PASS). Feeds `curated/fact_obligations.csv`
(see `curated/OBLIGATIONS.md`).

## Entry contract — `data/fiscal_outlook_headline.csv`

One row per (edition_year × target_year × line). Template: `data/_TEMPLATE_headline.csv`.
Required provenance on every row: `source_file` (exact PDF filename), `pdf_page`,
`printed_page` (or table number), `retrieved_from` (URL), `retrieved_date`. `basis` is
`official_projection` (or `official_revised` for mid-year revisions; this ingest also uses
`official_actual` for the prior-year outturn column of each edition — as-reported, not
audited). Beyond the original contract lines, `nominal_gdp` rows carry the edition's own
printed KDNK (current prices) so the %GDP rows are reconcilable; `development_expenditure`
is the **gross** figure (net + loan recovery in the note). `deficit_pct_gdp` /
`debt_pct_gdp` rows hold percentages in `amount_rm_bil` (flagged in the note). Debt rows
labelled end-June in the source keep that caveat in the note — MOF publishes no year-end
debt projection. After entry: reconcile against the document's own printed totals, then run
the independent adversarial verifier pass — the same discipline as PKKP.

Pairs with `apps/models/` (our model projection, now only a cross-check) and with the
gap-analysis pairings in `docs/SOURCES.md` (audited vs headline-reported).
