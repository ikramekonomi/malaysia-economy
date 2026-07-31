# Source: Anggaran Perbelanjaan Persekutuan (Federal Expenditure Estimates)

Source #2 of the warehouse: the **budget as tabled in Parliament**, at the same
maksud → program → aktiviti → objek grain PKKP records as actuals. Enables the true
budget-vs-actual gap (vs the interim view in `curated/`, which uses PKKP's own recorded
`anggaran_asal`) and — via `curated/forecast/fact_utilisation_signatures.csv` — expected-
actual nowcasts for un-audited years.

## Status: Budget 2025 ingested at maksud grain (2026-07-31)

`data/2025/fact_anggaran_maksud_2025.csv` — the book's "Ringkasan Perbelanjaan Sebenar dan
Anggaran Mengurus dan Pembangunan" (printed pages 21–31), all 85 votes (14 Tanggungan,
40 Bekalan, 31 Pembangunan incl. P.70 Simpanan Luar Jangka), all four printed columns
(sebenar 2022, sebenar 2023, anggaran asal 2024, anggaran 2025), whole RM as printed,
long format with per-row `pdf_page`/`printed_page`.

- **Document:** `Anggaran_Perbelanjaan_Persekutuan_2025.pdf` (541 pp), retrieved
  2026-07-31 from
  https://belanjawan.mof.gov.my/pdf/belanjawan2025/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2025.pdf
  → `raw/` (gitignored; re-download to reproduce).
- **Pipeline:** `pipeline/2025/extract_maksud_2025.py` (extraction),
  `validate_2025.py` (reconciliation), `build_crosswalk_2025.py` (PKKP join).
- **Validation:** `data/2025/_validation_2025.csv` — 376 checks against the book's own
  per-maksud totals and printed grand totals: 368 PASS; the 8 FAILs are the source's own
  inconsistencies (RM1 sen-rounding differences and an RM8m emolumen/lain split
  disagreement in the printed roll-up), catalogued with proofs in
  `data/2025/_source_anomalies_2025.csv` — kept as printed, never corrected.
- **Adversarial verifier:** independent agent, blind to the extraction, re-derived all
  226 vote-component cells with two engines (pdftotext + pdfplumber): **full agreement**
  — same 85 votes, same values, same 8 printed-source mismatches and nothing else;
  59 other printed "Jumlah" rows (incl. the unlabelled Kementerian Kewangan roll-up and
  combined B+P ministry totals) reconcile exactly.
- **Crosswalk:** `data/2025/_crosswalk_pkkp_2025.csv` — AP vote codes ("B. 62")
  normalised to PKKP `dim_maksud` codes ("B.62"/zero-padded); all 85 matched with
  name-level evidence, none guessed.
- **Nowcast:** `curated/forecast/fact_nowcast_2025.csv` (built by
  `curated/forecast/build_nowcast_2025.py`) applies per-vote utilisation signatures to
  the anggaran_2025 figures (`basis=model_projection`).

Program/objek grain is the documented follow-up (the book's per-vote detail sections).

## Where the documents live

- **belanjawan.mof.gov.my** — Budget portal; "Estimated Federal Expenditure / Anggaran
  Perbelanjaan Persekutuan" booklets per year (recent years). One volume per Budget year;
  Budget 2025 tabled Oct 2024, Budget 2026 tabled Oct 2025 (Budget 2026 book:
  `/pdf/belanjawan2026/perbelanjaan/Anggaran_Perbelanjaan_Persekutuan_2026.pdf` — next
  ingestion candidate).
- **www.treasury.gov.my** — older editions (the portal moved over the years).
- data.gov.my hosts **no** maksud-grain budget dataset (verified Jul 2026) — PDF is the
  only machine route.

## Ingestion plan (mirrors PKKP discipline)

Pilot **Budget 2025** first (pairs with FY2025 PKKP when it lands; joins to FY2024 history
immediately): `data/<year>/` CSVs with full provenance (source_file, pdf_page,
printed_page), amounts exact as printed, en-dash = 0, parentheses = negative, Malay labels
canonical; join keys `maksud_code`/`program_code`/`aktiviti_code`/`objek_code` with an
explicit crosswalk for any code differences vs PKKP (never guessed); `measure=budget`,
never blended into actuals; reconcile to the book's own printed per-maksud and grand
totals, then an independent adversarial verifier pass before any dashboard exposure.
