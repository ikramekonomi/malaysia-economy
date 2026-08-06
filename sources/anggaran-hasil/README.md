# Source: Anggaran Hasil Kerajaan Persekutuan (Federal Revenue Estimates)

The **budgeted revenue** counterpart to PKKP's collected revenue — unlocks the
"revenue estimate vs collected" gap pairing (docs/SOURCES.md) at *kod hasil* grain.
Published with each Budget on belanjawan.mof.gov.my alongside the Fiscal Outlook.

## Status: Budget 2025 + 2026 editions ingested (2026-07-31)

| document | grain | columns |
|---|---|---|
| `ringkasan_2025.pdf` (7 pp) → `data/2025/fact_hasil_ringkasan_2025.csv` | kod hasil (sections 60000/70000/80000/90000 → groups → items) | Pendapatan 2023 · Anggaran Disemak 2024 · Anggaran 2025 |
| `ringkasan_2026.pdf` (7 pp) → `data/2026/fact_hasil_ringkasan_2026.csv` | same | Pendapatan 2024 · Anggaran Disemak 2025 · Anggaran 2026 |
| `hasil_2025.pdf` / `hasil_2026.pdf` → `fact_hasil_measures_<ed>.csv` | Budget tax-measure impacts by kod | total before measures · per-code impacts (parentheses = negative) · net change · **total after measures** |

Retrieved 2026-07-31 from `https://belanjawan.mof.gov.my/pdf/belanjawan<ed>/hasil/{ringkasan,hasil}.pdf`
(PDFs in `raw/`, gitignored). Whole RM as printed; `-` (nil) recorded as 0 with
`has_nil=True`; the combined indirect-tax subtotal keeps its printed span code
(`62000&64000`). `label_bm` is the first printed label line and `label_context` the
wrapped/translated continuation — **join on kod, never labels**.

## Verification (`pipeline/validate_hasil.py` → `data/_validation_hasil.csv`)

132 checks, 130 PASS. Highlights:
- Code hierarchy reconciles exactly in every column of both editions (groups = items,
  sections = groups, TOTAL = sections).
- **Cross-source:** Pendapatan 2023 equals audited PKKP revenue **to the ringgit**
  (314,959,481,731); Pendapatan 2024 matches PKKP to whole-RM rounding; the estimate
  totals equal the MOF Fiscal Outlook revenue lines exactly (322.050 / 339.706 /
  334.115 / 343.124 RM bil).
- The measures pages give a headline the Fiscal Outlook does not: revenue **after**
  Budget measures — 2025: 344,093,198,000; 2026: 342,332,278,000.
- **Adversarial verifier** (blind, two engines + a third rendering for the disputed
  cell): identical row sets and values on all four documents, zero disagreements;
  independently isolated the same misprinted cell.
- The 2 FAILs are one printed source misprint in the 2025 measures list (the 61000
  group impact, off RM500k vs its own items; net + total agree with the items) —
  catalogued in `data/_source_anomalies_hasil.csv`, kept as printed.

## Crosswalk to PKKP

PKKP `fact_revenue` is label-based (no kod hasil). Mapped at category level:
60000 ↔ HASIL CUKAI, 70000+90000 ↔ HASIL BUKAN CUKAI (the book splits WP collections
into 90000), 80000 ↔ TERIMAAN BUKAN HASIL — exercised by the X2 checks. An item-level
label crosswalk (61100 ↔ Cukai Pendapatan, …) is the documented follow-up.
