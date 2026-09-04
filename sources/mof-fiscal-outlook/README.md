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
Fiskal 2021** edition (`tinjauan_fiskal_2021.pdf`, user-uploaded, 20 pages — not the full
~277-page narrative report, just its statistical-tables appendix) — the same appendix
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
langkah Belanjawan 2021" — excludes 2021 Budget measures).** Note this PDF's own
coverage is **2017-2021, not 2020-2024** — later years (2022-2024) need a later edition's
equivalent appendix, not yet ingested; each edition's appendix here should land as its own
`data/<edition>_public_finance_stats/` folder (same basename tables UNION BY NAME across
editions in the warehouse build automatically) rather than merged into this one.

Extracted by `pipeline/extract_2021_public_finance_stats.py` (every value embedded with
its own `pdf_page`/`printed_page`, read directly off the PDF — nothing recomputed).
Reconciled to the tables' own printed sub-item/parent/Jumlah sums and cross-table
identities (`data/2021_public_finance_stats/_validation.csv`: **80/80 PASS**), plus an
independent adversarial verifier pass (separate agent, blind to the extraction script,
re-transcribed all 4 tables from the PDF and compared cell-by-cell): **full agreement**.

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

Pairs with `curated/forecast/` (the model projection becomes a cross-check) and with the
gap-analysis pairings in `docs/SOURCES.md` (audited vs headline-reported).
