# Source: MOF Fiscal Outlook (Laporan Ekonomi & Fiskal) — SCAFFOLD, awaiting documents

Official Ministry of Finance projections for federal revenue, expenditure, deficit and debt
— the government's own forward numbers for FY2025–FY2026. Published each October alongside
the Budget on **belanjawan.mof.gov.my** (English: "Fiscal Outlook and Federal Government
Revenue Estimates"; also mirrored on treasury.gov.my).

## Status: no data yet — deliberately

The publishing host is blocked by this environment's egress policy, and **figures are never
entered from memory** (CLAUDE.md golden rules: every number needs verifiable provenance).
This folder ships the structure and the entry contract so ingestion is a fill-in exercise
the moment the PDFs are available.

## How to get the documents to the pipeline (either works)

1. **Open the egress** for this environment: claude.ai/code → your environment → network
   policy → allow `belanjawan.mof.gov.my` (and ideally `www.treasury.gov.my`,
   `data.gov.my`, `api.data.gov.my`, `storage.data.gov.my`, `open.dosm.gov.my`,
   `storage.dosm.gov.my`). Docs: code.claude.com/docs/en/claude-code-on-the-web.
2. **Supply the PDFs via GitHub** (works under the current policy): download the Fiscal
   Outlook PDFs (2025 and 2026 editions) from belanjawan.mof.gov.my → put them in any
   GitHub repo you own (private is fine) → tell the session to attach it (`add_repo`).

## Entry contract — `data/fiscal_outlook_headline.csv`

One row per (edition_year × target_year × line). Template: `data/_TEMPLATE_headline.csv`.
Required provenance on every row: `source_file` (exact PDF filename), `pdf_page`,
`printed_page` (or table number), `retrieved_from` (URL), `retrieved_date`. `basis` is
`official_projection` (or `official_revised` for mid-year revisions). After entry:
reconcile against the document's own printed totals, then run the independent adversarial
verifier pass — the same discipline as PKKP.

Pairs with `curated/forecast/` (the model projection becomes a cross-check) and with the
gap-analysis pairings in `docs/SOURCES.md` (audited vs headline-reported).
