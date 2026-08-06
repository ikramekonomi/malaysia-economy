# fact_obligations — the obligations layer (what is OWED, beyond the cash accounts)

PKKP's core statements are cash accounts: they show money moving, not what the federal
government **owes** (debt, PFI liabilities, financial commitments, guarantees) or is **owed**
(receivables / revenue arrears). That obligations side lives in the *Penyata Akaun
Memorandum* and its notes/registers, in the Auditor-General's fiscal analysis, and in the
MOF Fiscal Outlook's fiscal-risk section. `fact_obligations.csv` unifies the figures already
extracted **and verified** in the source layer into one queryable view.

Built by `pipeline/build_obligations.py`. Validation: `_validation_obligations.csv`
(**94/94 PASS** — every register reconciles to its own printed total, plus 11 cross-source
checks). No number is created here; every row carries its source provenance
(`source_table`, `source_file`, `pdf_page`, `printed_page`, `statement`).

## Schema

| column | meaning |
|---|---|
| `source` / `basis` | `pkkp` = `audited_memorandum` (FY2009–2024, each year from its own audited volume); `audit-negara` = `ag_analysis` (LKAN 3/2025: FY2024 + FY2023 comparatives); `mof-fiscal-outlook` = `official_outlook` (FO2025 + FO2026 editions) |
| `year`, `asof` | position date. **PKKP/AG are 31 Dec positions; each FO edition's second column is an end-JUNE position** (`asof` = `…-06-30`) — never mix Jun and Dec positions silently |
| `obligation_class`, `subclass` | see the map below |
| `group_bm`, `line_bm` | printed section/category and line/entity label, verbatim |
| `row_type` | `line` (one-per-concept headline figure), `component`, `detail`, `subtotal`, `total`, `memo`. **Sum only `detail` rows, within one (`source_table`, `year`)** — subtotal/total rows are retained so every printed figure exists and reconciles |
| `amount_rm` | normalised to RM (AG bilion ×1e9, FO juta/bilion ×1e6/1e9); `unit_original`, `value_printed` keep the printed form |

## Class map (all mappings — nothing else is included)

| class | subclass | source rows |
|---|---|---|
| `hutang` | | PKKP memorandum line *Hutang Awam* (2009–2015 label) / *Hutang Persekutuan* (2016+); AG II.J28; FO J5.1 *Hutang Kerajaan Persekutuan* |
| `pfi` | | PKKP memorandum *Liabiliti Inisiatif Pembiayaan Swasta* (first disclosed FY2018); AG II.J28 *Liabiliti PFI* |
| `komitmen` | `''` | PKKP memorandum *Komitmen Kewangan* (first disclosed FY2018); AG II.J28 |
| | `jaminan`, `pajakan_kewangan`, `bayaran_balik_cukai`, `pampasan` | PKKP Nota 10 component totals (`fact_debt` kind=`commitment_total`, 2018+); AG II.J29. `row_type=component` — components sum to the class line; the `jaminan` component equals the jaminan-class register total (do **not** double count) |
| | `liabiliti_lain_ppp_pfi` | FO J5.1 *Liabiliti lain* (PPP + PFI obligations, + PBLT in FO2025) — narrower than PKKP *Komitmen Kewangan* |
| `jaminan` (committed guarantees — government services the debt) | `komitmen_jaminan` | PKKP *Komitmen Jaminan* register by entity (`fact_guarantees`, Lampiran, 2018+ — earlier volumes do not print this register); AG II.J30 by entity; FO J5.1 *Komitmen jaminan* line + J5.4 by entity (incl. 1MDB RM5.0b, TRX City, GovCo…) |
| | `memorandum_2009` | the 2009 volume's memorandum *JAMINAN* line (that era printed the whole guarantee register as one memorandum liability line) |
| `contingent` (exposure contingent on default) | `berkanun_pinjaman`, `berkanun_pencarum`, `berkanun_total` | PKKP *Jaminan Berkanun* register by entity, all 16 years (`fact_statutory_guarantees`); AG II.J33. Pre-2012 volumes have no pencarum/pendeposit section (total = loan guarantees only — noted per row) |
| | `kewangan_akta96`, `kewangan_akta61` (+`_ikatan`, `_skim`), `kewangan_total` | FO J5.2 *Jaminan Kewangan* by instrument (Akta 850 definition) and J5.3 Akta-96 top recipients. Akta 96 ≙ PKKP `berkanun_pinjaman` (cross-checked exactly for 2024) |
| `abt_hasil` (owed TO the government) | `abt_total`, `pinjaman_boleh_dituntut`, `pelbagai_abt`, `tunggakan_pelbagai_abt`, `tunggakan_faedah_pinjaman` | PKKP memorandum *Akaun Belum Terima* + Nota 9 split + arrears memo rows (2018+); pre-2018 volumes print only *Pinjaman (dan Pendahuluan) Boleh Dituntut* — **revenue arrears are not disclosed in PKKP before FY2018** |
| | `hasil`, `pelbagai_abt_component` | AG II.b.J1 *Pelbagai ABT* split — `hasil` = revenue arrears (RM44.55b at 2024), the register PKKP never breaks out; AG II.J22 totals |
| `pelbagai_liabiliti` | | PKKP memorandum line, all years; AG II.J28 |

**Do-not-sum warnings.** (1) `contingent` overlaps `jaminan`: committed guarantees are a
subset of the guarantee stock, and `berkanun_pencarum` (deposit/contributor guarantees,
RM1.42 trillion at 2024) overlaps deposit-insurance cover — never add classes together.
(2) `komitmen` `component` rows sum to the `komitmen` headline `line`; don't add both.
(3) FO Jun-30 positions are not comparable to Dec-31 rows.

## Deliberate exclusions (stay in the source layer)

- PKKP `fact_pfi_liabilities` (tranche-level PFI register, 2019+), `fact_finance_leases`,
  `fact_compensation_commitments`, `fact_guarantee_repayment_grants`, `fact_debt_issues`,
  Nota 10 komitmen split detail (`fact_commitment_detail`), borrower-level ABT detail —
  the view carries the headline + entity-level guarantee grain; the registers remain fully
  queryable in `sources/pkkp/`.
- PKKP memorandum *Pelaburan* and the 2009 *JAMINAN DEPOSIT BERKANUN* asset line
  (investments/deposits, not obligations).
- AG II.J21 (duplicate of II.J28 + II.J22), II.J31 (maturity profile), II.J32 (grant
  channelling), II.b.J2–J11 (ABT ageing/agency views) — in `sources/audit-negara/`.
- MOF FO J5.1 *Jumlah* row (mixes classes; used in validation only). PFI figures in FO
  appear only in narrative text, not tables — not extracted.

## Provenance / era caveats

- Committed guarantees (`jaminan`) have **no PKKP figure for 2010–2017**: that era's
  memorandum lists only Hutang Awam + Pelbagai Liabiliti, and no Komitmen Jaminan register
  is printed — a genuine source absence, not an extraction gap. The contingent
  (`berkanun`) register is the only PKKP guarantee series covering all 16 years.
- AG II.J30/J33 column headings could not be rebuilt by the AG extraction (kept as
  `lajur N` in the source CSV); the year mapping used here (J30: lajur1=2024, lajur2=2023;
  J33: lajur2=2024, lajur4=2023) is verified by exact agreement with PKKP and II.J29
  (see `xsource` checks).
- The AG source keeps a printed-label artifact ("Govco Holdings Berhad KOMITMEN JAMINAN" —
  a page-break header merged into the row label). Kept verbatim per golden rule 2.
- Nota 10 prints register figures rounded to whole RM (differences ≤ RM0.59 — tolerance
  1.0 in the checks); the 2009 memorandum statement prints whole RM against a register
  kept in sen (RM0.08).
- FO2026's text layer garbles some glyphs; labels were assigned positionally from the
  printed row order and all values reconcile to printed totals (see
  `sources/mof-fiscal-outlook/pipeline/extract_contingent_liabilities.py`).

## Headline picture (PKKP audited memorandum, RM billion, 31 Dec)

| FY | Hutang | PFI | Komitmen Kewangan | — of which komitmen jaminan | — bayaran balik cukai | ABT (owed to govt) | — tunggakan pelbagai ABT | Jaminan berkanun (pinjaman) | Jaminan berkanun (total, incl. pencarum) |
|---|---|---|---|---|---|---|---|---|---|
| 2009 | 362.4 | – | – | 84.3¹ | – | 73.4² | – | – | 84.3 |
| 2012 | 501.6 | – | – | – | – | 95.5² | – | 143.1 | 690.4 |
| 2015 | 630.5 | – | – | – | – | 105.7² | – | 177.7 | 920.3 |
| 2018 | 741.0 | 36.4 | 243.0 | 164.9 | 44.4 | 86.9 | 16.2 | 266.5 | 1,211.1 |
| 2020 | 879.6 | 37.0 | 269.9 | 216.8 | 14.6 | 106.4 | 20.9 | 294.7 | 1,395.1 |
| 2022 | 1,079.6 | 34.5 | 284.9 | 224.1 | 25.7 | 105.5 | 21.6 | 317.6 | 1,490.4 |
| 2023 | 1,172.5 | 33.5 | 285.6 | 227.4 | 25.5 | 98.4 | 24.7 | 328.0 | 1,614.8 |
| 2024 | 1,247.6 | 32.9 | 297.2 | 236.2 | 33.3 | 103.2 | 32.4 | 332.8 | 1,748.5 |

¹ 2009 presentation (guarantee register as memorandum line). ² pre-2018 = loans
receivable only (no revenue-arrears disclosure). Full per-year series: query the CSV.

Gap-analysis hooks this enables: PKKP total liabilities (RM1,577.8b, 81.7% of GDP at 2024)
vs the headline "federal debt" figure; unpaid tax refunds swinging RM44.4b→14.6b→33.3b
(the 2019 GST-refund clearance and renewed build-up); revenue arrears RM44.6b (AG) vs
PKKP's undisclosed pre-2018 arrears; committed guarantees at ~71% of the guarantee stock;
1MDB still RM5.0b committed at end-Jun 2025.
