# Source: Laporan Ketua Audit Negara (Auditor-General's Report)

Audit findings, wastage, non-compliance, project overruns and the audit opinion on the
federal accounts — the Tier-2 source that most directly serves "find gaps in fiscal
behaviour" (docs/SOURCES.md). Published by Jabatan Audit Negara on lkan.audit.gov.my.

## Status: all 8 federal volumes 2024–2026 acquired & cover-verified (2026-07-31)

`data/lkan_reports.csv` is the manifest: report id, cover-verified volume title, tabling
date, Command-Paper number, exact source URL, sha256, size, pages. PDFs live in `raw/`
(gitignored — `python3 pipeline/fetch_lkan.py` re-downloads and hash-checks them).

| Report | Volume | Pairs with |
|---|---|---|
| LKAN 3/2024 | Penyata Kewangan Kerajaan Persekutuan **2023** | PKKP FY2023 |
| LKAN 3/2025 | Penyata Kewangan Kerajaan Persekutuan **2024** + Aktiviti | PKKP FY2024 |
| LKAN 2/2024 | Aktiviti Kementerian/Jabatan + Badan Berkanun (vol 1), Pengurusan Syarikat (vol 2) | FY2022-23 programmes |
| LKAN 2/2025 | Aktiviti Kementerian/Jabatan/Badan Berkanun/Syarikat | FY2023-24 programmes |
| LKAN 1/2025 | Penyata Kewangan **Agensi** Persekutuan 2023 | statutory bodies FY2023 |
| LKAN 1/2026 | Penyata Kewangan Agensi Persekutuan **2024** (vol 1) + Aktiviti/Syarikat (vol 2) | statutory bodies FY2024 |

Both Penyata Kewangan volumes certify the federal statements with **Pendapat Tanpa
Teguran** (unmodified opinion) "dengan Perenggan Hal-hal Lain" — extraction of the sijil
details and findings tables is the next step (below).

## Acquisition route (why parlimen.gov.my, not audit.gov.my)

- **lkan.audit.gov.my / www.audit.gov.my**: F5 WAF rejects every non-browser TLS
  fingerprint ("Request Rejected") — including its direct `/documents/lkan/...` PDF
  paths — and real-browser traffic cannot traverse this environment's egress proxy.
- **www.parlimen.gov.my**: every LKAN is tabled in the Dewan Rakyat as a Command Paper
  (Kertas Perintah) and served at a stable URL
  `/ipms/eps/<tabling-date>/CMD.<n>.<year> - CMD<n>.<year>.pdf`. Per tabling day the
  federal volume(s) take the lowest CMD numbers, then the 13 states alphabetically —
  but titles in search indexes are unreliable, so every volume's identity in the
  manifest was verified from its own cover pages after download.
- TLS caveat: parlimen.gov.my omits its intermediate certificate ("Sectigo Public
  Server Authentication CA DV R36"); the fetch script bootstraps it from crt.sh and
  verifies it against the system trust store before any download (verification is
  never disabled). Network policy note: the egress proxy honours allowlist entries for
  HTTPS only (plain HTTP and HTTP-only hosts like crt.sectigo.com are blocked).

## Planned first extraction

1. `fact_audit_opinion.csv` — per audited year: opinion type, sijil date, emphasis
   paragraphs (from the two Penyata Kewangan volumes' Sijil + Lampiran sections), with
   `pdf_page` provenance. Cross-links to PKKP years as the audited-quality attestation.
2. The Penyata Kewangan volumes' own summary tables of federal finances (revenue,
   opex, DE, deficit, debt) — a third independent restatement to triangulate against
   PKKP (audited) and BNM (reported).
3. Findings registers from the Aktiviti volumes: per-ministry findings with amounts
   (kelemahan/teguran), keyed to `maksud` where the report names votes, joining PKKP
   for the "planned vs delivered vs audited-verdict" pairing in docs/SOURCES.md.

Then the standard discipline: reconcile to the report's own printed totals +
independent adversarial verifier pass before any curated/dashboard exposure.

## Not yet acquired

State LKAN volumes (13 per tabling day, same URL pattern — cover-verify before use)
and pre-2024 federal LKANs (probe earlier tabling dates the same way).
