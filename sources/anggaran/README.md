# Source: Anggaran Perbelanjaan Persekutuan (Federal Expenditure Estimates)

Source #2 of the warehouse: the **budget as tabled in Parliament**, at the same
maksud → program → aktiviti → objek grain PKKP records as actuals. Enables the true
budget-vs-actual gap (vs the interim view in `curated/`, which uses PKKP's own recorded
`anggaran_asal`) and — via `curated/forecast/fact_utilisation_signatures.csv` — expected-
actual nowcasts for un-audited years.

## Status: Budget 2024, 2025 AND 2026 ingested at maksud grain (2026-07-31)

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

### Budget 2026 book (`data/2026/`)

`fact_anggaran_maksud_2026.csv` — the AP2026 book's Ringkasan (printed pp. 5–33; layout
differs from 2025: vote code inline on the first component row), all **83 votes**
(B/P.32 Wilayah Persekutuan has left the book), four columns (sebenar 2023, sebenar
2024, anggaran asal 2025, anggaran 2026). Pipeline: `pipeline/2026/`.
- **Validation** (`_validation_2026.csv`): 456 checks — the only FAILs are the book's
  own ±RM1 sen-rounding rows (catalogued in `_source_anomalies_2026.csv`).
- **Cross-book:** every tabled-2025 value identical to the 2025 book; exactly one 2023
  restatement (P.15, RM1 — the 2026 book *corrects* the inconsistency catalogued in the
  2025 book); the 2026 book's 2025 emoluments roll-up sides with the per-vote rows on
  the 2025 book's RM8m roll-up discrepancy.
- **Cross-source:** sebenar 2024 reconciles with audited PKKP FY2024 to whole-RM
  rounding (OE within RM4 of 324.6b; DE within RM2 of 84.0b).
- **Adversarial verifier:** blind two-engine re-derivation — zero disagreements on all
  300 rows; independently confirmed the same printed ±RM1 set and the JUMLAH BESAR 2024
  self-inconsistency (printed 408,629,244,715 vs its own component lines' 417).
- **Crosswalk:** `_crosswalk_pkkp_2026.csv` — all 83 codes matched with name evidence.

### Budget 2024 book (`data/2024/`)

`fact_anggaran_maksud_2024.csv` — 83 votes (B/P.50 Digital not yet created; B/P.32
still listed), columns sebenar 2021/2022, anggaran asal 2023, anggaran 2024
(2025-style layout; pipeline `pipeline/2024/`). Validation: **368/368 PASS** — the
2024 book is fully arithmetically consistent as printed. Crosswalk: all 83 matched.
**Adversarial verifier:** blind two-engine re-derivation — zero disagreements
(288/288 cells engine-to-engine; 242 row-quadruples diffed cell-by-cell against this
extraction, zero mismatches); confirms the book is internally consistent to the
ringgit everywhere.
**Key evidence:** the tabled 2024 OE equals PKKP's recorded `anggaran_asal` 2024
exactly on every comparable vote, and the book's asal-2023 column equals PKKP's 2023
record — the audited PKKP appropriation series IS the budget as tabled (see
`curated/GAP_VIEWS.md` for the DE-side exception and its decomposition).

### Program/objek grain — scoped next step

The books' per-vote detail sections are regular: `Butiran | Program/Aktiviti | Kod
(Objek Am) | Anggaran <yr-1> | Anggaran <yr> | Bil. Jawatan` — program (xx0000) and
aktiviti (xx0100) rows with objek-am (10000–50000) breakdowns and per-vote `JUMLAH
ANGGARAN PERBELANJAAN MENGURUS` totals. Extraction plan: parse per-vote sections
(85/83 votes × 2–3 books), reconcile every vote's detail total against the
already-verified summary figures (built-in anchor), then the standard adversarial
verifier pass. This joins to PKKP's program/aktiviti/objek actuals for the full-depth
budget-vs-actual gap. Headcount (Bil. Jawatan) comes free — a new analytical axis.


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
