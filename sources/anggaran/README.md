# Source: Anggaran Perbelanjaan Persekutuan (Federal Expenditure Estimates)

Source #2 of the warehouse: the **budget as tabled in Parliament**, at the same
maksud → program → aktiviti → objek grain PKKP records as actuals. Enables the true
budget-vs-actual gap (vs the interim view in `curated/`, which uses PKKP's own recorded
`anggaran_asal`) and — via `apps/models/fact_utilisation_signatures.csv`, a model outside
the warehouse — expected-actual nowcasts for un-audited years.

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
- **Nowcast:** `apps/models/fact_nowcast_2025.csv` (built by
  `apps/models/build_nowcast_2025.py`) applies per-vote utilisation signatures to
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

### Program/objek grain — extracted (all three books, 2026-08-01)

`data/<year>/fact_anggaran_detail_<year>.csv` — the books' per-vote DETAIL sections:
`Butiran | Program/Aktiviti | Kod (Objek Am) | Anggaran <yr-1> | Anggaran <yr> |
Bil. Jawatan <yr-1>/<yr>` — program (xx0000) and aktiviti (xx0100…) rows with their
objek-am (10000–50000) breakdowns, closing per vote with `JUMLAH ANGGARAN
PERBELANJAAN MENGURUS`. Long format, one row per printed line per measure
(`anggaran_<yr-1>`/`anggaran_<yr>`), `row_kind` in
program|aktiviti|objek_am|jumlah_maksud (`jumlah_butiran` reserved — no book prints
per-butiran subtotal lines), headcount columns `bil_jawatan_<yr-1>/<yr>` where
printed (the 10000 objek rows and the JUMLAH row), full per-row provenance.
**Mengurus (T/B votes) only** — the books present P votes as a project list
(`Butiran (Projek)` layout, five columns incl. total project cost), a different
grain left for a later pass.

- **Pipeline:** shared parser `pipeline/detail_common.py` (the three books are one
  layout family; per-era quirks are config + documented in the module docstring)
  driven by thin per-year `pipeline/<year>/extract_detail_<year>.py` /
  `validate_detail_<year>.py`.
- **Coverage:** 2024 book 51 votes (1,284 butiran, 2,764 objek lines, 8,198 rows);
  2025 book 53 votes (1,408 / 3,022 / 8,966); 2026 book 53 votes (1,408 / 3,030 /
  8,982).
- **Validation** (`data/<year>/_validation_detail_<year>.csv`): V1 internal sums
  (every butiran total = its objek-am lines; every program = its aktiviti; every
  vote JUMLAH = its programs), V2 anchor (vote total == the adversarially verified
  `fact_anggaran_maksud_<year>.csv` figure — detail `anggaran_<yr-1>` against the
  summary's `anggaran_asal_<yr-1>`, `anggaran_<yr>` against `anggaran_<yr>`),
  V3 coverage, V4 Bil. Jawatan (vote JUMLAH headcount = sum of program-level
  headcounts). **2024: 3,369 PASS / 0 FAIL; 2025: 3,733 PASS / 0 FAIL; 2026:
  3,729 PASS / 0 FAIL** — the detail sections are arithmetically consistent as
  printed in all three books, and every vote reconciles exactly to the verified
  maksud-grain anchor. No new source anomalies at this grain.
- **Documented absences (V3):** B.32 Wilayah Persekutuan (2024 & 2025 books) and
  B.33 Alam Sekitar dan Air (2024 book) — ministries dissolved in 2023, kept in
  the summary for historical actuals with zero budget-year allocation; the books
  print no detail section for them. The 2026 book covers all 53 T/B votes.
- **Era differences found:** 2024/2025 print `…  …` dot leaders in the Kod column
  on butiran rows, 2026 drops them; every vote opens with a per-objek-am
  RINGKASAN block — its own pages (without the Bil. Jawatan header) in 2026,
  sharing the first detail page of small votes in 2024/2025, with the total line
  worded differently per era (never extracted — pages are gated on the full
  detail header and objek/jumlah rows are only accepted once a butiran is open);
  the 2026 book can print a post-table footnote starting with a butiran code
  ("022400 - Peruntukan Skim Pinjaman Rumah Panjang (SPRP).", pdf p.197 —
  logged, not data); butiran names embed bare numbers ("Kepengerusian ASEAN
  2025") and wrap across lines, sometimes sharing a line with an objek row; the
  2024 book prints year-on-year headcount changes (13 rows, e.g. B.15 010000
  `3 → 7`, B.43 JUMLAH `18,477 → 18,497`), while the 2025 and 2026 books print
  identical Bil. Jawatan pairs throughout. En-dash nils, parenthesised negatives
  and footnote asterisks never occur in the detail tables of any of the three
  books (support kept per repo convention).
- **Next:** the standard independent adversarial verifier pass, then join to
  PKKP's program/aktiviti/objek actuals in `curated/` for the full-depth
  budget-vs-actual gap; P-vote (pembangunan) project lists as a separate grain.


## Lampiran E: actual federal grants to each state government (FY2019-2024, 2026-11-05)

Each Budget book prints, as Lampiran E, the federal grants actually paid to each of the 13 state governments in
the year two before the book, by grant, with its vote (T.12, B.11, B.12): one table, 13 states x 14-18 columns.
Held for the 2021-2026 books (FY2019-2024): the 2021-2023 appendices alone (`raw/lampiran_e_<book>.pdf`, from
`belanjawan.mof.gov.my/pdf/<book>/perbelanjaan/lampiran_e.pdf`, in `data/_documents_manifest.csv`), the 2024-2026
tables inside the full books (p514, p536, p578). Earlier books are not at the publisher's URLs.

* `pipeline/extract_lampiran_e.py` -> `data/<book>/fact_anggaran_lampiran_e_<book>.csv` (one row per state or
  Jumlah x column; `tb` = not applicable kept as printed with a blank amount; `-` = 0; `column_type` leaf /
  part / row_total: sum only `leaf`). The columns of each
  book are declared in the script (the headers are rotated multi-line text) and checked against the printed
  vote-code row. FY2019-2020 split road maintenance into three unlabelled sub-columns and a JUMLAH; each
  sub-column equals one of PKKP's three road-maintenance lines to the ringgit (L8), which names it.
* `pipeline/validate_lampiran_e.py` -> `data/_validation_lampiran_e.csv`: every row and column adds up (L1-L4,
  all PASS); each grant's national total against PKKP's audited line the same year (L5: capitation, road
  maintenance, special annual, revenue growth, petroleum-duty compensation, street lighting and state services
  equal within RM2 every year; the tourism grants equal B.11 'Lain-lain Bayaran Balik' in FY2020-2024 (RM8.0m apart
  in FY2019); GTBKK differs by RM1.4m in FY2023 and RM1.2m in FY2024); the grants PKKP pays to a
  named state (L6, all equal); PKKP's Concurrent List line carries the libraries and museums grants too (L7:
  equal in FY2023-2024, RM54k-2.5m apart in FY2019-2022). Differences are kept as printed.
* `data/_source_anomalies_lampiran_e.csv`: the 2024 and 2025 books title the table "Anggaran" (estimate) though it
  is dated to 31 December and equals the audited actuals; the unlabelled road sub-columns.

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
