# sources/states — all 13 Malaysian states' audited state finances (FY2014–FY2024)

In the warehouse's hub-per-domain architecture (`CLAUDE.md`), **each state's audited
financial statements are that state's hub** — the record its budgets, its LKAN activity
audits and any third-party series reconcile against. This source is that hub for all
thirteen states, produced by **one shared pipeline** from the Jabatan Audit Negara's
*Penyata Kewangan Kerajaan Negeri* volumes.

It supersedes the `sources/state-selangor` pilot, which was used as the regression
baseline during the port and then removed — it was never committed, and its output is
reproduced (and corrected) here. §9 records every row that legitimately changed.

```
pipeline/
  state_config.py        THE ONLY state-specific file: the 141-volume manifest,
                         per-state revenue heads, agency-name prefixes, era map
  table_catalog.py       what to extract (Malay title regexes) + the code dictionary
                         + row_type taxonomy + revenue classes    [no state names]
  lkan_state_parser.py   the era-independent layout parser        [no state names]
  extract_states.py      --state <Name> | --all [--national]
  validate_states.py     V1/V1b/V1c/V2/V3/V4/V5 per state, N0–N5 nationally
data/<state_slug>/
  state_reports_<slug>.csv              volume manifest (sha256, pages, cover-verified)
  fact_state_finance_<slug>.csv         headline audited accounts, long format
  fact_state_revenue_<slug>.csv         revenue by printed category / contributor
  fact_state_agency_sijil_<slug>.csv    state-agency submission & opinion registers
  _validation_<slug>.csv                every check, with provenance
  _source_anomalies_<slug>.csv          misprints & intra-volume contradictions, with proofs
                                        - ONLY inconsistencies verified on the printed page
  _known_extraction_defects_<slug>.csv  defects of OURS, diagnosed but unfixed (see 12)
  _unparsed_tables_<slug>.csv           tables matched but refused (with the reason)
  _dropped_rows_<slug>.csv              fact rows refused (label could not be defended)
  _dropped_agency_rows_<slug>.csv       register rows refused (name could not be reassembled)
data/_national/
  fact_state_finance_all.csv            the conformed cross-state panel
  _validation_national.csv              cross-state conformance checks
  _known_extraction_defects.csv         national roll-up of the above
```

Rebuild (PDFs are read in place from `sources/audit-negara/raw/backfill/`; nothing is
copied):

```
python3 pipeline/extract_states.py  --all      # ~35 s with a warm text cache
python3 pipeline/validate_states.py --all
```

---

## 1. What the volumes are, and where the numbers actually live

141 Command Papers carry a state *Penyata Kewangan* volume. Four of them
(`CMD.47.2018` Kedah, `CMD.52.2018` Perak, `CMD.53.2018` P. Pinang, `CMD.56.2018`
Selangor) only *mention* Penyata Kewangan in a combined title and are activity/company
volumes — they are declared in the manifest with `scope=state_activity_management` and
not extracted. `CMD.14.2026` (LKAN 1/2026, Selangor company management) is likewise
declared and not extracted. **137 volumes are extracted.**

**The signed statutory statements are image-only in every volume.** Lampiran III–VII
(Penyata Kedudukan Kewangan, Penyata Penerimaan dan Pembayaran Wang Tunai, Penyata
Prestasi Kewangan, Penyata Akaun Memorandum, Nota) are scans of the State Financial
Officer's signed pages and carry no text layer.

The text-layer ground truth is the **auditor's own analysis section**, whose `JADUAL`
tables restate those statements in **RM Juta** and cite `Sumber: Penyata Kewangan
Kerajaan Negeri`. That is what this source extracts, and `sumber_bm` on every row
records the citation. Amounts are therefore as-printed to two decimals in RM Juta,
**not** to the sen.

Every volume's fiscal year is read from **its own front matter** — the section heading
`PENYATA KEWANGAN KERAJAAN NEGERI <state> BAGI TAHUN BERAKHIR 31 DISEMBER <year>` and
the cover's `TAHUN <year>` — never inferred from the Command-Paper year.
`extract_states.build_manifest` re-derives it on every run and **aborts** if it
disagrees with `state_config.VOLUMES`.

## 2. Era map — identical in all 13 states

The Jabatan Audit Negara re-templated the whole series at once, verified by the JADUAL
numbering in all 137 volumes (dotted `4.x` through the 2018 tabling, serial `n` from the
2019 tabling):

| Era | Tabled | Fiscal years | Numbering | Distinguishing features |
|---|---|---|---|---|
| **e1** | 2015–2016 | FY2014–FY2015 | `Jadual 4.1` title case | Bahagian IV = ANALISIS KEWANGAN; bare-number footers; negatives printed `-x` |
| **e2** | 2017–2018 | FY2016–FY2017 | `JADUAL 4.1` ALL CAPS | footer `LKAN PENYATA KEWANGAN NEGERI <state> <year> \| <page>`; still `-x` negatives |
| **e3** | 2019–2023 | FY2018–FY2022 | `JADUAL 1` serial | InDesign slug lines carry the printed page; `JADUAL 1` becomes the Penyata Prestasi Kewangan; from FY2019 negatives switch to `(x)`; doubled footers |
| **e4** | 2024–2025 | FY2023–FY2024 | `JADUAL 1` serial, LKAN `n/YYYY` | new *Fokus Utama Audit* section; Symbol-font bullets; the `Kumpulan Wang Amanah Kerajaan` subtotal is dropped (components listed flat); `Perbelanjaan Mengurus` printed parenthesised under a `(-)` flow heading; the agency half moves to the **prior** financial year |

Era boundaries did **not** fall a year either side for any state.

## 3. Per-state coverage

| State | Volumes in manifest | Extracted | FY range | Source-absent years | Notes |
|---|---|---|---|---|---|
| Johor | 11 | 11 | 2014–2024 | — | |
| Kedah | 12 | 11 | 2014–2024 | — | CMD.47.2018 is an activity volume |
| Kelantan | 11 | 10 | 2014–2024 | **FY2022** | CMD.40.2023 is an image-only scan (see §8) |
| Melaka | 11 | 11 | 2014–2024 | — | |
| Negeri Sembilan | 10 | 10 | 2014, 2016–2024 | **FY2015** | no LKAN 2015 volume was tabled |
| Pahang | 11 | 11 | 2014–2024 | — | |
| Perak | 11 | 10 | 2014, 2016–2024 | **FY2015** | CMD.52.2018 is an activity volume; FY2017 sits in the combined federal+state CMD.39.2018 |
| Perlis | 11 | 11 | 2014–2024 | — | |
| Pulau Pinang | 11 | 10 | 2014, 2016–2024 | **FY2015** | CMD.53.2018 is an activity volume; FY2017 sits in the combined federal+state CMD.41.2018 |
| Sabah | 11 | 11 | 2014–2024 | — | |
| Sarawak | 9 | 9 | 2014–2015, 2017–2023 | **FY2016, FY2024** | no LKAN 2016 volume; no LKAN 3/2025 volume has been tabled |
| Selangor | 13 | 11 | 2014–2024 | — | CMD.56.2018 activity, CMD.14.2026 company management |
| Terengganu | 10 | 10 | 2015–2024 | **FY2014** | no LKAN 2014 volume was tabled |

Every absence above is a **source absence** (the volume was never tabled, or has no text
layer), not an extraction gap. Each is asserted by `N1_state_year_present` in
`data/_national/_validation_national.csv`.

## 4. Column contract (how to use the files without double-counting)

The same figure is printed in several jadual in one volume, so every row carries:

| column | meaning |
|---|---|
| `column_role` | `own_year` = the volume that audits this fiscal year; `comparative` = another volume reprinting it |
| `is_canonical` | exactly one row per `(source_file, fiscal_year, measure, line_code)` |
| `row_type` | `component` (leaf) / `subtotal` / `total` / `balance` / `derived` |
| `is_leaf` | `yes` **iff** `row_type='component'` — **CLAUDE.md golden rule 5: sum only leaf rows** |
| `table_role` | `current` (≤2 year columns) or `trend` (a 5-year table) |
| `measure` | `actual` or `estimate` (the *anggaran* columns **and** every `peruntukan_mengurus` approved-allocation row) |
| `label_quality` | `clean` / `partial` (a neighbour's Bil. number or a printed bullet survives in the label) |
| `amount_rm` | verbatim: parentheses ⇒ negative, `-`/`–` ⇒ 0.0 (nil) |
| `amount_rm_conformed` | same value, but codes in `table_catalog.LEVEL_CODES` are forced to their magnitude so one comparable series spans the era where the newer volumes print them parenthesised |
| `sign_convention` | `level_abs` or `as_printed` |
| `column_geometry` | `clean`, or `incomplete_row: n of m printed columns could be assigned` |
| `data_quality` | `ok`, or **`suspect`** — this row is covered by a diagnosed but unfixed defect of *ours*, listed with its diagnosis in `_known_extraction_defects_<slug>.csv` (§12). It is never a statement about the printed source. **Filter it out before using a series.** |

**The acceptance filter for one clean series:**

```sql
WHERE column_role = 'own_year' AND is_canonical = 'yes' AND measure = 'actual'
```

`V4_canonical_unique` asserts this yields exactly one row per `(fiscal_year, line_code)`
in every state (PASS 13/13). To aggregate *within* a table add `AND is_leaf = 'yes'`.

## 5. The national panel

`data/_national/fact_state_finance_all.csv` — **5,556 rows**, one per
`(state, fiscal_year, line_code, measure)`, canonical own-year rows only, conformed
codes only, `amount_rm_conformed` in ringgit. 13 states × FY2014–FY2024 × 75 conformed
line codes.

`revenue_total` is present for **136 of the 137 declared state-years**; the only gap
is Kelantan FY2022, the image-only volume (§8.2). The other absences in §3 are years for
which no volume was ever tabled, so they are not declared state-years at all.

`data/_national/_validation_national.csv` carries:

* `N0_panel_unique` — one row per (state, fiscal_year, line_code, measure). **PASS.**
* `V5_duplicate_code_in_table` (per state) — where one printed table yields two rows
  carrying one conformed code. This is an **extraction** signal, deliberately kept out of
  `_source_anomalies`: it means the dictionary cannot yet tell two printed lines apart.
  Fixing one is a dictionary change, never a figure change.
* `N1_state_year_present` / `N1_headline_codes` — every declared state-year present, and
  whether it carries `revenue_total`, `opex_before_transfer`, `devex_total`,
  `expenditure_total`, `surplus_deficit`.
* `N2_identity_surplus` / `N2_identity_expenditure` — revenue − expenditure = surplus and
  opex + devex = expenditure, computed **from the panel itself**.
* `N3_no_code_collision` — no state-specific trust fund occupies a conformed code. **PASS.**
* `N4_row_counts` — per-state rows and coverage.
* `N5_code_coverage` — how many of the 13 states carry each headline code.

### Identity contract — which codes may be combined

**Read this before computing anything from more than one code.** The volumes print
the same concept on two bases, and the panel carries both because both are printed:

* **Performance-statement basis** (Penyata Prestasi Kewangan): `revenue_total`,
  `opex_before_transfer`, `devex_total`, `expenditure_total`, `surplus_deficit`.
  This set is internally consistent: `revenue_total − opex_before_transfer −
  devex_total = surplus_deficit` closes to the sen in **109 of the 120 state-years
  that carry all four codes**. The 11 residuals are printed facts, not extraction
  error, and each is visible in `N2_identity_*`: Pahang FY2016/17/21/22 (the state
  prints a third head, `Perbelanjaan Bekalan Air`), Johor FY2018 (the volume prints
  `LEBIHAN/KURANGAN` unsigned and calls it a *kurangan* in prose), and further cases
  where a state prints an extra transfer line inside the statement (e.g. Perlis
  FY2015 `Pindahan Ke Kumpulan Wang Pembangunan`, N. Sembilan FY2020). Check `N2`
  for the state-year you are using before differencing.
* **Consolidated-revenue-account basis** (Akaun Hasil Disatukan): `cra_opening_balance`,
  `opex_total`, `cra_surplus_deficit`, `cra_closing_balance`. Here `opex_total` is
  **after** transfers out of the account.

`opex_total` and `opex_before_transfer` therefore differ by the transfer (Sabah FY2014:
4,503.91 vs 3,703.91 — exactly RM800 juta), and in **99 of 137 state-years the two
bases are printed on different pages**. Mixing them — e.g. `revenue_total −
opex_total − devex_total` — yields a surplus wrong by the transfer amount. Use one
basis throughout, and prefer the performance-statement set for cross-state
comparison, since `N2` and `N7` are computed against it.

### Conformed `line_code` dictionary

Codes are flat and semantic. A line the dictionary does not recognise keeps a
deterministic fallback `<spec_id>.<slug(label)>` with `line_code_conformed=no`, so
nothing is silently lost and **nothing state-specific ever occupies a conformed code**.

**Penyata Prestasi Kewangan** `revenue_total`, `revenue_tax`, `revenue_nontax`,
`revenue_nonrevenue_receipts`, `opex_before_transfer`, `devex_total`,
`expenditure_total`, `surplus_deficit`, `financing_external_loans`,
`financing_loan_repayment`, `financing_cash_investment_trust`, `financing_total`.

**Akaun Hasil Disatukan** `cra_opening_balance`, `revenue_total`, `opex_total`,
`cra_surplus_deficit`, `cra_closing_balance`.

**Penyata Kedudukan Kewangan** `kwd_balance`, `cra_balance`, `loan_account_balance`,
`trust_account_balance`, `govt_trust_funds`, `misc_govt_trust_funds`,
`development_fund`, `forest_development_fund`, `housing_loan_fund`,
`public_trust_funds`, `deposit_account`; `cash_total`, `cash_in_bank`,
`cash_in_transit`, `cash_in_hand`; `investment_total`, `investment_general`,
`investment_trust_funds`, `investment_shares`, `investment_domestic_deposits`.

**Akaun Pinjaman Disatukan** `loan_opening_balance`, `loan_receipts`, `loan_payments`,
`loan_closing_balance`.

**Akaun Amanah Disatukan** `devfund_*` (Kumpulan Wang Pembangunan) and **`forestfund_*`**
(Kumpulan Wang Pembangunan **Hutan** — a *separate statutory fund*, and one the pilot
conflated with the Development Fund; see §9).

**Perbelanjaan** `opex_charged`, `opex_supply`, `opex_total_by_maksud`,
`devex_total_by_department`; approved estimates `opex_estimate_*`.

**Penyata Akaun Memorandum** `debt_total`, `debt_opening_balance`,
`debt_closing_balance`, `loans_receivable_total`, `loans_receivable_bbn`,
`loans_receivable_pbt`, `receivables_total`, `financial_assets_total`,
`liabilities_total`.

**Revenue file** adds `revenue_top_contributors_total` (the *Penyumbang Utama* JUMLAH — a
top-5 subtotal, **never** total revenue) and the conformed revenue **items**
`revenue_item_land_premium`, `revenue_item_land_tax`,
`revenue_item_land_mineral_permit`, `revenue_item_federal_capitation_grant`,
`revenue_item_federal_dept_grant`, `revenue_item_forest_produce`,
`revenue_item_petroleum_royalty`, `revenue_item_state_sales_tax` — these are what make
the top-contributor block joinable **on a code, never on a name** (golden rule 4).

## 6. Per-state revenue heads

The Akta Tatacara Kewangan 1957 gives every state the same *fund* structure but **not**
the same *revenue heads*. All rules live in `state_config`
(`NATIONAL_REVENUE_CLASSES` + `STATE_REVENUE_CLASSES`), never in the parser.

| `revenue_class` | States that print it | Printed as |
|---|---|---|
| `petroleum_royalty` | **Sabah**, **Sarawak** | Sabah: `Royalti Petroleum`. Sarawak does **not** print a royalty head — the PDA 1974 payment appears as `Pampasan Gantian Hak Ke Atas Minyak` / `... Ke Atas Gas` |
| `state_sales_tax` | **Sabah**, **Sarawak** only | `Cukai Jualan Negeri` / State Sales Tax — no Peninsular state may levy one, so this class doubles as a Borneo marker |
| `forest_produce` | Kedah, Kelantan, Pahang, Perlis, Sabah, Sarawak | `Hasil Hutan`, `Royalti Hutan` (Sarawak), `Royalti Kayu Kayan` + `Premium Perhutanan` (Kelantan) |
| `federal_compensation_forest` | Selangor | `Ganti Rugi dari Pampasan (Hutan)` — a federal payment in substance, but the volumes never name the payer, so it is kept in its own class |
| `federal_transfer` | all except Negeri Sembilan and Perak (whose volumes never name a federal grant among the top contributors) | `Pemberian …`, `Geran daripada Kerajaan Persekutuan`, `Kos Pengurusan Jabatan Negeri`, `Terimaan Daripada Kerajaan Persekutuan (Dana Khas)` |

**Terengganu and Kelantan**: their share of the PDA 1974 payment is printed as
`Wang Ihsan` / `Dana Khas`, and in the years covered it never reaches the top-5
contributor table, so `petroleum_royalty` has **no rows** for those two states. `Dana
Khas` is deliberately **not** mapped to `petroleum_royalty` — the volumes never say what
the special fund is for; it is classed `federal_transfer` because the payer is named.

### State-specific trust funds (never conformed)

Only the four statutory funds (Kumpulan Wang Pembangunan / Pembangunan Hutan / Pinjaman
Perumahan / Amanah Awam) are conformed. Everything else keeps an unconformed
`<spec_id>.<slug>` code, so one state's fund can never collide with another's —
`N3_no_code_collision` **PASS**. Seen so far: Johor `Kumpulan Wang Bekalan Air`; Kedah
`Kumpulan Wang Amanah Penyelenggaraan Jalan Negeri`; Sabah `Kumpulan Wang Amanah Bencana
Alam`; Sarawak `The State Road Maintenance Fund`, `The State Disaster Relief Fund`,
`Government Contributions Towards Approved Agencies Trust Fund`, `The Ketua Masyarakat
(Ketua Kaum) Trust Fund`, `The Forest Concession Area (Rehabilitation and Development)
Trust Fund`.

**Language.** No volume is in English. Sarawak's volumes are in Malay but name several
of their trust funds in English (above); Sabah's are entirely in Malay. No
language-specific handling was needed.

## 7. State agency register

The state volumes do **not** print a full per-agency opinion register the way the federal
LKAN does — **the pilot README's claim that the submission register covers "every state
agency" is wrong and is corrected here.** They print two things:

* `penyerahan_status` — the submission / audit-status register, covering the agencies the
  volume chooses to list (Badan Berkanun Negeri, Majlis Agama Islam, Pihak Berkuasa
  Tempatan) with a submission date and/or an audit status.
* `sijil_pendapat` — **only** the agencies whose Sijil Ketua Audit Negara carried a
  modified or Emphasis-of-Matter opinion, with `opinion` and `opinion_qualifier`.

Agencies given a plain unqualified opinion are reported only as **counts in the
narrative**, so a complete opinion register at the grain of
`sources/audit-negara/data/fact_agensi_sijil_*.csv` **is not derivable from these
volumes**. That is a source absence.

The register is parsed geometrically (see the module note in `extract_states.py`):
continuation pages are followed, the running head / column strip / InDesign slug are
removed *before* row assembly, and every line is attached to its nearest `BIL.` line so
wrapped names and vertically offset status cells are recovered. Rows whose agency name
cannot be reassembled are **refused and logged** to `_dropped_agency_rows_<slug>.csv`,
never emitted scrambled. `name_quality` records `clean` / `wrapped_joined` /
`reordered`.

## 8. Known gaps

1. **Sen-level statutory statements** — Lampiran III–VII are image-only in all 137
   volumes. Everything here is the auditor's RM-Juta restatement.
2. **Kelantan FY2022 (`CMD.40.2023`) has no text layer.** All 210 pages are an
   image-only scan; `pdftotext` returns 3 characters per page and zero JADUAL headings.
   Nothing is extracted; the volume is declared in the manifest with
   `text_layer=image_only` and logged in `_unparsed_tables_kelantan.csv`. Recovering it
   needs OCR (the FY2015 PKKP pattern).
3. **136 tables refused** across the 13 states (`_unparsed_tables_*.csv`). The dominant
   reason is a 5-year trend table whose interleaved `(RM Juta)`/`(%)` columns make the
   year of a money column ambiguous; rather than risk labelling a column with the wrong
   year the whole table is dropped (those years are extracted from their own volumes).
4. **The `Akaun Amanah Disatukan` hierarchy is not the same in every state**, and the
   validator must not assume Selangor's. Selangor prints it **nested** (`Kumpulan Wang
   Amanah Kerajaan` is the roll-up of KW Pembangunan / Pinjaman Perumahan / Pelbagai KWA
   / Pembangunan Hutan); Kelantan prints it **flat** (`Akaun Amanah Disatukan terdiri
   daripada:` followed by KW Amanah Kerajaan, KW Pembangunan, KW Amanah Awam and Akaun
   Deposit as *siblings*). `V1_trust_account_composition` decides which one a volume uses
   **from the table's own arithmetic** — whichever candidate composition reconciles to
   the printed total — and records it in the check's `detail`. Only when *no* candidate
   reconciles is the table's own arithmetic inconsistent, and only then is it promoted to
   `_source_anomalies`. The same guard applies to `V1_intra_volume_contradiction`: for
   the hierarchy-sensitive codes a summary table and a detailed table of one volume
   legitimately print the same label at two aggregation levels, so a difference between
   them is only a contradiction when at least one of the two tables fails its **own**
   composition check. Worked proof, Kelantan CMD.31.2020 J2 (pdf p31), FY2018:
   `984.64 − 789.88 + 108.98 + 439.76 = 743.50`, exactly the printed `Akaun Amanah
   Disatukan`, and `−676.31 + 5.00 + 743.50 = 72.19`, exactly the printed `JUMLAH`.
5. **`expenditure_total` is not printed by every state.** 51 of 137 state-years carry no
   printed expenditure total: Kedah never prints one (its Penyata Prestasi Kewangan runs
   `Hasil Tolak → Perbelanjaan Mengurus → Perbelanjaan Pembangunan → KURANGAN` with no
   `JUMLAH PERBELANJAAN` line at all). Reported as `N1_headline_codes = PARTIAL`; never
   synthesised from opex + devex.
6. **Some states print a third expenditure head.** Pahang prints `Perbelanjaan Bekalan
   Air` beside Mengurus and Pembangunan, so `opex + devex ≠ expenditure_total` for
   Pahang FY2016/2017/2021/2022 — that is a source fact, not an error, and shows up as
   `N2_identity_expenditure = FAIL`. Read the fact file's `component` rows for the full
   composition.
7. **`hasil_penyumbang_utama` labels remain partly fragmented outside Selangor.** The
   Bil-anchored row assembly (§9) fixes the 5-year matrix wherever the table has a usable
   `BIL.` column. Terengganu and Sarawak print theirs with a different geometry, and some
   of their labels are still two adjacent printed labels concatenated (e.g. Terengganu
   `Premium Tanah Biasa Pemberian 50% Perbelanjaan`). Those rows keep an unconformed
   code; the conformed `revenue_item_*` codes are unaffected.
   The 2026-11-05 pass fixed the JUMLAH rows of these tables: a row whose figures are one space
   apart (`1,886.80 100.0`) is re-tokenised exactly, a `(RM Juta)`/`(%)` pair row takes every
   second figure, a JUMLAH set left of the grid is realigned to the item rows' columns, page
   footers no longer join the last label, and where a table prints `JUMLAH PENYUMBANG ...` the
   `JUMLAH HASIL RM...` banner (all revenue, Negeri Sembilan) keeps an unconformed code. Every
   `V1_penyumbang_utama_total` check passes; the remaining label defects are listed in
   `state_config.KNOWN_EXTRACTION_DEFECTS` (blind verifier: `qa/audits/2026-11-05_state_parser_verifier.md`).
8. **`JUSTIFIKASI PENINGKATAN/PENURUNAN HASIL YANG KETARA` is not extracted** — a
   free-text *Punca* column that `pdftotext -layout` interleaves into the row label.
9. **Spec scope.** Extraction is spec-driven: **~20 specs** matching roughly 2,900 of the
   ~8,300 printed JADUAL blocks in the 137 volumes. That is a deliberate scope choice —
   the specs cover the five statutory statements and their revenue/expenditure analysis.
   Out of scope, and *not* extracted: arrears and ageing tables (`Tunggakan Hasil`,
   `Tunggakan Cukai Tanah Mengikut Pejabat Daerah Dan Tanah`, `Kedudukan Tunggakan
   Bayaran Balik Pinjaman Boleh Dituntut`, `Pengumuran Deposit`), unspent-allocation
   tables (`Peruntukan Pembangunan Tidak Dibelanjakan`), reconciliation exception tables
   (`Akaun Penyelesaian Tidak Berbaki Sifar`), per-company investment tables (`Dividen
   Diterima`, `Kedudukan Pelaburan Melalui Pejabat Menteri Besar (Pemerbadanan)`,
   `Senarai Syarikat Yang Membayar Dividen`), RMKe-12 project-status tables, and the
   whole agency/PBT financial-performance half of each volume. They are legitimate future
   specs, not silent losses — every JADUAL the specs *do* match but the parser refuses is
   listed with its reason in `_unparsed_tables_<slug>.csv`.
10. Exact tabling URLs are not recorded here — join `command_paper` to
   `sources/audit-negara/data/lkan_reports_backfill.csv`.

## 9. Differences from the `sources/state-selangor` pilot (regression record)

Selangor is produced by exactly the same code as the other twelve. Against the frozen
pilot, restricted to the pilot's ten volumes:

* **`fact_state_finance`: 3,223 shared rows are byte-identical on every field** except
  `measure` on 60 `peruntukan_mengurus` rows, which are approved allocations and are now
  correctly tagged `estimate` rather than `actual`.
* 41 pilot-only / 65 port-only finance rows, all explained:
  * **⚠ A DEFECT IN THE PILOT THAT THE INDEPENDENT VERIFIER DID NOT CATCH.** The
    **Forest Development Fund** flow table (`KEDUDUKAN BAKI KUMPULAN WANG PEMBANGUNAN
    HUTAN`, in CMD.40.2020, CMD.50.2021, CMD.52.2022 and CMD.49.2023) was matched by the
    pilot's `kumpulan_wang_pembangunan` title regex and its rows were coded
    `devfund_opening_balance` / `devfund_receipts` / `devfund_payments` /
    `devfund_closing_balance` — **the *Development Fund*'s own codes**. The Forest
    Development Fund is a *separate statutory fund*, so for four fiscal years the pilot's
    `devfund_*` series silently contained two different funds competing for one code,
    with `is_canonical` picking one of them arbitrarily. The port gives it its own spec
    (`kumpulan_wang_pembangunan_hutan`) and its own `forestfund_*` codes, and the
    `kumpulan_wang_pembangunan` regex now carries a `(?! hutan)` guard.
    **Those 39 rows changed for a good reason — do not "restore" them to the pilot's
    values.** This is evidence the port improved on the baseline, not drift from it.
  * `KUMPULAN WANG PINJAMAN PERUMAHAN **BAGI** TAHUN 2016` (CMD.43.2017 J4.25) was missed
    by the pilot's title regex; +8 rows.
  * `PERUNTUKAN PERBELANJAAN MENGURUS PADA TAHUN 2024` (CMD.26.2025 J11) was missed;
    +16 rows.
  * 2 rows (CMD.30.2024 J17) whose *fallback slug* lost a trailing narrative connective:
    `…pelbagai_kumpulan_wang_amanah_iv_kerajaan_terdiri_daripada` →
    `…pelbagai_kumpulan_wang_amanah_iv_kerajaan`. `line_label_bm`, `amount_printed` and
    `amount_rm` are byte-identical — only the derived code is cleaner.
* **`fact_state_revenue` differs by design** — 255 pilot rows replaced by 269. The
  pilot split each printed `PENYUMBANG UTAMA HASIL` row across two line_codes and dropped
  years, because that table prints one logical row across three physical lines that *all*
  carry figures. `parse_rows_by_bil` now assembles the row from the `BIL.` column.
  Worked proof (CMD.50.2021 pdf p38 J13): `Premium Bagi Geran` now carries
  1,316.80 / 1,537.44 / 618.74 / 1,008.37 / 1,057.74 for FY2016–FY2020 under the single
  code `revenue_item_land_premium`, exactly as printed; under the pilot the 2016 figure
  sat under `geran` and 2017–2020 under `premium_bagi`.
* **`fact_state_agency_sijil` differs by design** — 335 register lines recovered from the
  ten pilot volumes against the pilot's 275 (the independent verifier counted 335 printed
  lines). Fixed: page continuations, Majlis Agama Islam (dropped from every volume by the
  pilot), four phantom rows fabricated from the running footer (two of which carried a
  fabricated `opinion='Tanpa Teguran'`), and the lost `audit_status` column on
  CMD.49.2023 pdf p105.

## 10. Adding a 14th jurisdiction

1. Add a key to `state_config.VOLUMES` with one entry per Command Paper: `file`,
   `fiscal_year` (**verify from the volume's own cover** — the extractor aborts on a
   mismatch), `agency_fiscal_year`, `report`, `command_paper`, `era`, `scope`
   (`state_financial_statements` | `state_activity_management` |
   `state_company_management`), and `text_layer="image_only"` if it is a scan.
2. If it levies a revenue head no other jurisdiction levies, add a rule to
   `STATE_REVENUE_CLASSES[<name>]`. If its agencies are named with an unusual
   institutional prefix, add it to `AGENCY_NAME_PREFIXES_EXTRA[<name>]`.
3. `python3 pipeline/extract_states.py --state <Name>` then
   `python3 pipeline/validate_states.py --state <Name> --national`.
4. Nothing in `lkan_state_parser.py` or `table_catalog.py` should need to change. If it
   does, the change must be expressible as a *title regex* or a *label regex*, never as a
   page number, a JADUAL number or a state name.

## 11. Second-pass cleanup (defect classes closed)

An independent verifier read the shipped CSVs back against the printed pages. Everything
below was found there, fixed in **code** (never by editing a figure), and is asserted by
the checks named.

### 11.1 A percent column shipped as RM juta — `build_columns` unit resolution

`(RM Juta)  (%)  (RM Juta)  (%)` strips sit so close together that the ±3-character
window used to attach a header token to a column reached *both* neighbours, and the old
rule ("any overlapping token, and money wins") gave the **percent** column a money unit.
Melaka `CMD.53.2015` J4.12 (pdf p32) therefore shipped the printed FY2013 *percentages*
as ringgit, `is_canonical=yes`, `column_geometry=clean`:

| printed row | shipped | printed `(RM Juta)` |
|---|---|---|
| Premium Tanah | 39.4 | **119.28** |
| Cukai Tanah Semasa | 20.8 | **62.96** |
| Jumlah | 73.6 | **223.05** |

A unit is now resolved **ordinally** where the strip carries as many tokens as there are
columns (exact even when the strip is typeset far tighter than the data — Selangor
`CMD.52.2022` J13 sets ten unit tokens over 100 characters above data spread over 150),
and by **nearest** token otherwise. A `(%)` printed on its own line is settled first. A
broken `(RM` / `Juta)` split over two lines is rejoined. Sweeping the class across all
13 states caught the same defect in Kedah `CMD.34.2016` J4.13 and Selangor
`CMD.52.2022` J13 (FY2017 and FY2018 both), and recovered Selangor `CMD.41.2019` J11
and Sarawak `CMD.43.2018` J4.14, which had been refused.

A money value can now only come from a money column; the year columns of a BIL-grouped
trend matrix must also be fillable in most printed rows, or the table is refused with
`row/column geometry unresolved: only n of m printed rows could be filled`.

### 11.2 Agency register

* **Nothing is dropped silently.** `Penyata kewangan belum diterima.` is a printed audit
  *status*; the old running-footer test matched the substring `penyatakewangan` inside it
  and deleted the three most audit-relevant rows of Melaka `CMD.41.2023` p91 (bils 9–11)
  without logging them. The footer test now requires the qualifier
  (`penyata kewangan KERAJAAN / AGENSI / NEGERI`), and a numbered row is never furniture.
* **`audit_status` is what the page prints**, not a whitelist match, so
  `Sijil Audit Berteguran telah dikeluarkan.` and `Dalam proses pensijilan.` survive and
  the materially different `oleh Firma Audit Swasta` / `oleh Jabatan Audit Negara` middle
  line is no longer dropped.
* **Each printed column wraps independently**, so a wrapped cell is now attached to its
  Bil. along **its own column**, and a payload fragment that opens a new sentence cannot
  join a payload cell already closed by a full stop. This is what recovers Sabah
  `CMD.43.2016` J6.1 bil 3 (`Kumpulan Wang Penanaman Semula Getah Sabah`, previously
  truncated and its tail welded onto bil 4) and Melaka `CMD.41.2023` bils 2–8.
* **The column strip is found by its printed `BIL.` stub**, so a volume that names its
  second column `BBN` or `PBT` no longer has its JADUAL title read as data
  (`Majlis Perbandaran Tawau Tahun 2015 Setakat 30 Jun 2016 Bil. PBT`).
* **Shredded running heads are removed by token**, not by substring: a line whose every
  word belongs to the running-furniture vocabulary and carries at least one
  furniture-only word (or a bare year) is refused. 30 welded names → 2.
* `Korporasi …` is a Sabah statutory-body form and is now an accepted agency prefix
  (26 previously-refused Sabah agencies recovered).

Register reconciliation, printed `n.` lines vs extracted rows, per JADUAL:

| state | register tables | printed | extracted |
|---|---|---|---|
| Melaka | 9 | 143 | 143 |
| Sabah | 18 | 541 | 539 |
| Kelantan | 17 | 263 | 262 |
| Selangor | 20 | 388 | 382 |
| Pulau Pinang | 9 | 97 | 96 |

### 11.3 Source anomalies re-adjudicated

Every promoted V1 failure was re-read against its printed page. **61 of 95 were our own
extraction or our own check, not an Auditor-General misprint**, and were fixed:

* a printed `LEBIHAN/KURANGAN` is an unsigned magnitude, so the surplus identity is
  compared on magnitudes (Johor `CMD.30.2019` J1);
* a state may print a **third expenditure head** (Pahang `Perbelanjaan Bekalan Air`:
  1,049.08 + 118.27 + 69.10 = 1,236.45 exactly), a **fourth revenue head** (Sarawak
  `Pemberian Kerajaan Persekutuan dan Bayaran Balik`: 6,390.70 + 3,976.90 + 248.34 +
  30.75 = 10,646.69 exactly), a **fifth trust sibling** (Sarawak `Akaun Kena Bayar`) or
  an extra **CRA outflow** (Perlis `Pindahan Ke Kumpulan Wang Pembangunan`: 143.82 −
  146.15 − 32.94 = −35.27 exactly) — every one of those pages reconciles, so every
  printed component line now counts;
* a leading `-` is a printed **bullet**, not a nil cell — reading it as a value emptied
  the label of every sub-fund line, welded the section caption onto the first one
  (Terengganu `CMD.46.2016` J4.2 shipped Kumpulan Wang Pembangunan's −696.94 under
  `govt_trust_funds`) and dropped `Kumpulan Wang Bekalan Air` entirely;
* a **doubled text layer** interleaved line by line parsed every printed item twice, so
  the components of Negeri Sembilan `CMD.34.2019` J11/J12 summed to exactly twice the
  printed JUMLAH; identical figures in identical columns are now folded;
* a printed **section caption** above the first figures line (`Hasil`) never reached the
  row parser, so Negeri Sembilan `CMD.54.2015` J4.25 shipped the revenue subtotal
  (354.78 / 373.09) as `expenditure_total`;
* Negeri Sembilan prints **two balance lines**; `surplus_deficit` was taking the
  intermediate `LEBIHAN` instead of `(KURANGAN)/LEBIHAN KESELURUHAN`;
* a Bil. printed alone on its line was not an anchor, so Perak `CMD.56.2015` J4.11 lost
  `Lesen, Bayaran Pendaftaran Dan Permit` and its five-year subtotal came out RM80.58
  juta short.

**23 anomalies remain**, each a genuine printed inconsistency with its own figures and
page as proof. A further **11 failures were diagnosed as defects of ours** and are
therefore NOT in `_source_anomalies` — they are in `_known_extraction_defects_<slug>.csv`
(§12) and their rows carry `data_quality=suspect`. `_source_anomalies_<slug>.csv`
contains only inconsistencies verified on the printed page; filing one of our own bugs
there would accuse the Auditor-General of misprinting a page that in fact reconciles,
which is precisely what golden rule 2 forbids.

### 11.4 `N6_spec_stable` now separates a splice from a fallback

Two statements of one volume routinely restate the same audited figure, and the volumes
do not print the same tables every year, so a code that falls back from one to the other
is not automatically spliced. The check now decides **from the data**: in every fiscal
year where both statements are printed, do they agree to 2 dp? Agreement in every
overlapping year is a benign fallback (`INFO`); disagreement, or no overlapping year to
test with, is a genuine splice (`FAIL`). **62 failures → 56 benign, 6 genuine**, and the
6 are named with the disagreeing years in the check's `proof`.

The 6 genuine splices are **kept as validation FAILs and deliberately not "fixed"**:

| state | code | evidence |
|---|---|---|
| Johor | `trust_account_balance` | FY2015 printed 1,454.59 (J4.20) vs 1,628.54 (J4.1) |
| Kelantan | `govt_trust_funds` | FY2017 231.20 vs 930.24, and FY2018–FY2020 likewise |
| Perak | `govt_trust_funds` | FY2014 138.84 vs 282.52 |
| Perlis | `misc_govt_trust_funds` | FY2022 153.39 vs 429.33; FY2023 153.77 vs 434.73 |
| Johor | `revenue_item_land_tax` | no fiscal year prints both statements |
| Pahang | `revenue_item_forest_produce` | no fiscal year prints both statements |

**Three of them share one root cause**: the summary `KEDUDUKAN KUMPULAN WANG DISATUKAN`
and the detailed `AKAUN AMANAH DISATUKAN` print `Kumpulan Wang Amanah Kerajaan` at **two
different aggregation levels** — as the roll-up of its sub-funds in one, as a single
sibling component in the other (§8.4). Deciding which level `govt_trust_funds` should
mean is an **open dictionary decision** that changes the meaning of a conformed code in
several states at once; it was deliberately **not taken unilaterally** in this pass, and
the check now names exactly which state-years are affected so it can be taken with the
evidence in hand.

## 12. Known limitations — defects of OUR OWN

`data/<slug>/_known_extraction_defects_<slug>.csv`, rolled up in
`data/_national/_known_extraction_defects.csv`, declared once in
`state_config.KNOWN_EXTRACTION_DEFECTS`. Columns: `state`, `source_file`, `pdf_page`,
`printed_page`, `jadual`, `affected_rows`, `defect`, `diagnosis`, `why_unfixed`,
`impact_on_data`.

Each entry drives three things, so a defect cannot be quietly forgotten *or* quietly
blamed on the source:

1. the row in the defects file, with its diagnosis and why it is still open;
2. **`data_quality='suspect'`** on the affected fact rows — filter it out before using a
   series;
3. **suppression of the matching V1 failure from `_source_anomalies`** — the failure
   stays in `_validation_<slug>.csv`, because it *is* a failure; only the claim "the
   source misprinted this" is withdrawn.

| where | rows flagged | defect |
|---|---|---|
| N. Sembilan `CMD.34.2019` J11 (p38) | 2 | the banner `JUMLAH HASIL RM421.24 Juta` is *total revenue* but is coded `revenue_top_contributors_total`; the five contributors correctly sum to the other printed total, 382.59. Needs a table-level rule — the label-level rule regressed 15 other tables and was reverted |
| N. Sembilan `CMD.37.2018` J4.10 (p34) | 1 | the FY2017 subtotal reads 88.8, the printed *percentage*, not 367.27; the JUMLAH row is typeset off the column grid |
| Selangor `CMD.41.2019` J11 (p38) | 4 | printed JUMLAH FY2014–18 = 1,649.60 / 1,886.80 / 1,912.34 / 2,194.80 / 1,343.67; shipped 1,649.60 (correct) / 100.0 / 1,886.80 / 1,912.34 / 100.0 — the row drifts one year right and picks up percentages. All 25 contributor values on the page were checked line by line and are correct |
| Selangor `CMD.50.2021` J13 (p38) | 4 | same; printed 1,946.54 / 2,246.29 / 1,320.32 / 1,725.82 / 1,749.01, shipped 1,946.54 (correct) / 1,320.32 / 100.0 / 1,749.01 / 100.0 |
| Perak `CMD.44.2023` p98 | 9 register rows | names weld across the three-line centred layout, and every row reads `opinion=Tanpa Teguran` because `_OPGROUPS` has no pattern for this volume's caption `PENDAPAT TANPA TEGURAN DENGAN OM` |
| P. Pinang `CMD.46.2023` p96 | 1 emitted of 2 printed | the second opinion caption wraps over two lines, so the two `1.` anchors collapse and `Majlis Agama Islam Negeri Pulau Pinang` is lost |
| (all states) | — | `_value_tokens` drops a figure printed **exactly one space** after the previous one. The root fix was implemented and **deliberately reverted**: it moved ~2,000 rows, raised the refusal count and degraded the frozen Selangor regression. It needs its own pass with the column clustering retuned alongside it. Where it hits a money column the row is already marked `column_geometry=incomplete_row`, so no figure is *wrong* — some are absent |
