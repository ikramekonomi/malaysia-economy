# Source: Anggaran Perbelanjaan Persekutuan (Federal Expenditure Estimates) — ACQUISITION NOTES

Source #2 of the warehouse: the **budget as tabled in Parliament**, at the same
maksud → program → aktiviti → objek grain PKKP records as actuals. Enables the true
budget-vs-actual gap (vs the interim view in `curated/`, which uses PKKP's own recorded
`anggaran_asal`) and — via `curated/forecast/fact_utilisation_signatures.csv` — expected-
actual nowcasts for un-audited years.

## Where the documents live

- **belanjawan.mof.gov.my** — Budget portal; "Estimated Federal Expenditure / Anggaran
  Perbelanjaan Persekutuan" booklets per year (recent years). One volume per Budget year;
  Budget 2025 tabled Oct 2024, Budget 2026 tabled Oct 2025.
- **www.treasury.gov.my** — older editions (the portal moved over the years).
- data.gov.my hosts **no** maksud-grain budget dataset (verified Jul 2026) — PDF is the
  only machine route.

All `.gov.my` hosts are currently blocked by this environment's egress policy. Two ways in:
1. **Allow the hosts** in the environment's network policy (claude.ai/code → environment →
   network policy; docs: code.claude.com/docs/en/claude-code-on-the-web).
2. **Supply PDFs via a GitHub repo** you own (private is fine) and attach it to the session
   — GitHub is reachable under the current policy.

## Ingestion plan (mirrors PKKP discipline)

Pilot **Budget 2025** first (pairs with FY2025 PKKP when it lands; joins to FY2024 history
immediately): `data/<year>/` CSVs with full provenance (source_file, pdf_page,
printed_page), amounts exact as printed, en-dash = 0, parentheses = negative, Malay labels
canonical; join keys `maksud_code`/`program_code`/`aktiviti_code`/`objek_code` with an
explicit crosswalk for any code differences vs PKKP (never guessed); `measure=budget`,
never blended into actuals; reconcile to the book's own printed per-maksud and grand
totals, then an independent adversarial verifier pass before any dashboard exposure.
