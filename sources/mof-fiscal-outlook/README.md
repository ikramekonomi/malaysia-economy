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
