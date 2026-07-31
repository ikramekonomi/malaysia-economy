# Source: Bank Negara Malaysia — fiscal tables via BNM OpenAPI

Quarterly federal government finance and federal debt series, machine-read from the
**BNM OpenAPI** (no WAF, no manual downloads): `api.bnm.gov.my/public/msb/<table>`
with header `Accept: application/vnd.BNM.API.v1+json`. Catalogue discovered via
`api.bnm.gov.my/api/specification/categories` (portal: apikijangportal.bnm.gov.my).

## Status: INGESTED via API (2026-07-31); www.bnm.gov.my file downloads unnecessary

| table | content | coverage |
|---|---|---|
| `msb_3_1.csv` | Federal Government Finance (quarterly: revenue, opex, current balance, gross/net DE, financing) | 1996–1Q2026 |
| `msb_3_1_1.csv` | Federal Government Revenue (components) | 1996–2026 |
| `msb_3_1_2.csv` | Operating Expenditure by Object | 1996–2026 |
| `msb_3_1_3.csv` | Development Expenditure by Function | 1996–2025 |
| `msb_3_1_4.csv` | Federal Debt by Remaining Maturity | 2008–2026 |
| `msb_3_1_5.csv` | Federal Domestic Debt **by Holder** | 2008–2026 |
| `msb_3_1_6.csv` | Federal Debt by Currency & Remaining Maturity | 1999–2026 |

Values verbatim as served (RM million); every row carries endpoint + retrieval date +
the API's own `last_updated`. Refresh = re-run `pipeline/fetch_bnm_fiscal.py`
(explicit, provenance-updating — same discipline as sources/dosm).

## Basis discipline (why this is namespaced, never blended)

The **fiscal aggregates (3.1–3.1.3) are BNM-compiled from MOF/AGD** — a *reported*
basis, not the source of truth; PKKP (audited) and the budget books stay canonical for
annual figures. The **debt tables (3.1.4–3.1.6)** are closer to BNM's own
administrative domain (it is the government's fiscal agent). Cross-source
disagreement is a finding, not something to resolve by overwriting.

## Validation (`pipeline/validate_bnm.py` → `data/_validation_bnm.csv`, 197/197 PASS)

- Internal: quarterly balance = revenue − opex (BNM serves the balance rounded to RM1m).
- **Triangulation:** BNM annual sums equal audited PKKP revenue / opex / DE to within
  RM1–2 million for every year FY2010–FY2024. BNM's DE follows PKKP's
  performance-statement presentation (which differs from the by-vote register in
  2019–2020 — an intra-PKKP presentational difference, documented in the validator).
- **FY2025 measured** (sum of four quarters, all now published) vs the official
  revised estimates: revenue **336.07** vs 334.12; opex **330.78** vs 332.15; gross DE
  **81.92** vs 80.0; overall deficit **−75.29 vs −76.71** (RM bil) — the year landed
  slightly better than MOF's own revision, and well below the signature-nowcast OE mid
  (343.6), i.e. FY2025 broke the historical overshoot pattern. Audited PKKP 2025 will
  adjudicate finally.
