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

## Extracted datasets

### Per-agency sijil registers (`data/fact_agensi_sijil_{2023,2024}.csv`)

One row per federal agency certified by the Auditor-General (Lampiran 2 of the two
Agensi volumes): 142 rows FY2023, 143 rows FY2024 — badan berkanun / kumpulan wang /
agensi lain sub-registers, ministry groups, opinion + qualifier, incorporating act for
the Lain register, per-row `pdf_page`. Pipeline `pipeline/extract_agensi_sijil.py`
(the PDFs carry duplicated offset text layers and out-of-page-box neighbour text —
see the script's layout notes), validation `pipeline/validate_agensi.py`:
**17/17 PASS** against the reports' own printed tallies (FY2023: 133 Tanpa Teguran /
8 Berteguran / 1 Bertentangan — MADA's adverse opinion; FY2024: 128 / 15).
**Adversarial verifier:** independent blind two-engine re-derivation (pdftotext
-layout + pdfplumber) — AGREE on every row of both years, all opinions/qualifiers
identical; the two artifacts it flagged (spaced-duplicate name capture on FY2023
bil 80; ministry groups dropped on continuation pages) are fixed and re-validated.
Source inconsistency (kept as printed): FY2023 prose says 129+10+3 agencies, its own
register prints 130+9+3 — `data/_source_anomalies_agensi.csv`.

### LKAN audit inventory + findings register (`data/fact_lkan_audits.csv`, `data/fact_lkan_findings.csv`)

The five Aktiviti-bearing volumes (LKAN 2/2024 ×2, 2/2025, 3/2025, 1/2026 vol 2):
`fact_lkan_audits.csv` — 34 audits (ministry, entity, topic, chapter architecture,
pdf range, each cross-checked against its chapter-head pages; incl. the two
register-style e-SelfAudit censuses, CMD.2.2026 II.3 and CMD.14.2025 VII);
`fact_lkan_findings.csv` — 426 finding units with per-unit `section_path`
(`5.x`/`5.x.y` heading numbers, or the paragraph range a margin sub-topic label
spans), verbatim heading/label, `pdf_page`, ordered `RM…` amount tokens,
`Maklum balas` responses as `entity|dates`, and `Pendapat Audit` box text.
Pipeline `pipeline/extract_lkan_findings.py` (three chapter architectures —
numbered skeleton, CMD.9-style margin-label, register; structural map with
text-layer hazards in `pipeline/STRUCTURE_NOTES.md`), validation
`pipeline/validate_lkan_findings.py`: **44/44 PASS**
(`data/_validation_lkan_findings.csv`) — per-volume response-marker recounts by
an independent scanner, section-path continuity incl. zero interior paragraph
gaps in every margin chapter, pdf-page ranges, chapter counts, RM-token
normalisation. Source wording variants kept as printed and documented in
`data/_source_anomalies_lkan.csv`. An independent adversarial verifier
re-derived the datasets from the PDFs (30-row deep sample all confirmed); the
margin-label defects it flagged are fixed and re-validated.

### Audit inventory of every held volume (`data/lkan_toc/`, `data/fact_lkan_audit_inventory.csv`, 2026-11-06)

There is one row per audit that the contents pages of a volume list, across every LKAN volume reporting audits
of activities, companies or statutory bodies: 283 volumes in the two manifests, tabled 2015-2026.

* **`pipeline/lkan_toc.py`** (`.github/workflows/lkan-extract.yml` runs it on Actions, over the L0 archive) writes
  the contents pages as page-aligned text (`data/lkan_toc/<file>.txt`). It reads the text layer, or, where the
  contents page is an image (the 2014-2016 volumes), uses OCR; OCR pages are marked `(ocr)`. A volume with no
  contents page found says why: text per page, and the lines naming the contents.
* **`pipeline/lkan_inventory.py`** (in the suite) reads every layout of the twelve years into one row per audit:
  * the part (BAHAGIAN);
  * the body as printed (ministry or department, in capitals);
  * the agency or company under it;
  * the topic;
  * the printed page;
  * `text_source` (`text` or `ocr`).

  The layouts are documented in its docstring: page number left, behind a bar or right; chapter pages `1-1`;
  marked topics `2.` / `-`. It does no matching or classification.
* **Counts (2026-11-06): 875 audits in 211 volumes (430 federal, 445 state).** Some volumes have no audit by
  design: the 2025 state volumes (3/2025) and the 2017 Siri 1 state volumes print only financial statements and
  key audit areas. Some contents pages are images (2014-2016) and await the OCR run.
* **Caveats:**
  * a combined audit lists several bodies in one entry, and they are kept joined as printed;
  * an audit's year is the volume's (`LKAN 2017 Siri 2` -> 2017; `TAHUN 2023` in the title), not the years its
    findings cover.

The findings register of the five recent federal volumes (`fact_lkan_findings.csv`, below) goes deeper. The
inventory is the breadth: what was audited, where and when, over twelve years.

### AG federal fiscal tables (`data/fact_lkan_fiscal_tables_2024.csv`)

The Auditor-General's own Analisis Kewangan Kerajaan Persekutuan tables
(LKAN 3/2025 Bahagian II pdf 30-67 JADUAL 1-33, II.a Pengurusan Hutang pdf
68-73 JADUAL 1-4, II.b Pengurusan Pelbagai ABT Hasil pdf 74-81 JADUAL 1-11):
48/48 tables, 1,567 cells in long format (verbatim values incl. parentheses
negatives/en-dash nils, row hierarchy + JUMLAH row types, per-column printed
heading and unit, `pdf_page`). Pipeline `pipeline/extract_lkan_fiscal.py`,
validation `pipeline/validate_lkan_fiscal.py` (`data/_validation_lkan_fiscal.csv`):
internal additivity of every printed JUMLAH row (183 recomputations, all pass
except one **documented sign misprint in JADUAL 21**, pdf 53), an independent
header re-read of every reconstructed column label, and the
**three-source triangulation** this dataset exists for — AG vs PKKP audited:
revenue/opex/gross DE FY2024+FY2023 all six agree to the AG's printed rounding
(incl. one documented truncation, devex FY2023 96.089 vs audited 96.0897);
AG/PKKP vs BNM MSB 3.1: five of six agree, **BNM's FY2023 gross development
expenditure (96,090.984 RM juta) diverges from the audited figure by
RM1.247 juta** — a real reported-vs-audited gap, kept as published.
Conventions/caveats: nil cells are stored as ASCII hyphen `-` (that is what
the text layer yields for the printed en-dash nil glyph — same concept as the
warehouse's en-dash = 0.0 convention); in 14 complex-header tables (stacked/
wrapped multi-row headings) the column heading could not be reconstructed
reliably, so `col_label_bm` is `lajur N (kepala tidak boleh dibina semula)` —
**in complex-header tables, column identity should be treated positionally
(col order per page)**; unit and values are verified either way.

### e-SelfAudit census registers of off-budget entities (`data/fact_eselfaudit_registers.csv`)

The Auditor-General's census of gazetted **badan lain termasuk syarikat** —
companies and other bodies outside the consolidated fund (P.U.(A) 331/2024,
1,856 entities) — the off-budget scope register. Two chapters, 31 tables,
561 cells in long format (one row per printed register cell, verbatim values,
`row_type` line/total/group, per-row `pdf_page`):
**CMD.2.2026 Bahagian II.3** (pdf 85-126; the FY2024 e-SelfAudit round over
the 852 federal entities: census + composition, mandate compliance,
tatakelola, and the Prestasi Kewangan registers — CLBS profit/loss, the 17
CLBS companies paying dividends to the Federal Government 2022-23, the 13
MKD companies profitable-but-not-paying, going-concern counts, deferred-grant
and financial-support balances, dormant-company registers) and
**CMD.14.2025 Bahagian VII** (pdf 204-207; the 2025 census announcement:
warta composition, federal + 13-state implementation status, the 1,526
responding companies by type/status). Named companies are kept verbatim
(incl. `**` note markers and `> 10` ratio cells); jadual numbering restarts
per sub-report, so `bahagian` distinguishes `II.3` / `II.3 Mandat` /
`II.3 Tatakelola` / `II.3 Prestasi` / `VII`. `unit` = `bilangan` marks
entity-count columns; column labels are declared from each table's printed
(stacked/merged) header. Pipeline `pipeline/extract_eselfaudit.py`
(pdfplumber cell-border banding — the volumes' doubled text layers put a
ghost copy of the neighbouring page at negative x and ghost lines between
baselines; see the docstring), validation `pipeline/validate_eselfaudit.py`
(`data/_validation_eselfaudit.csv`): **75 PASS / 6 INFO / 0 FAIL** — every
printed JUMLAH re-summed (column-, row- and derived-difference-wise), census
totals vs the chapters' own prose with page evidence (852 / 1,856 / 641 /
513 / 401 …), and the FY2024-vs-FY2025 cross-report reconciliation (641+1
responders identical; the 850/1,006 vs 852/1,004 federal/state split and the
34→2 non-responder / 174→208 winding-up moves are dated snapshots, INFO).
Source quirks kept as printed in `data/_source_anomalies_lkan.csv`: Prestasi
J3's JUMLAH PERUBAHAN misprint (RM3.00 juta off its own columns), the
`Jawatakuasa` typo, the cross-report census split, and Prestasi J8's
double-counted RM1.4 bilion pass-through (its own Nota explains). **Prestasi
J8 is a top-10 excerpt** (10 of 119 companies, RM9.858 of RM13.784 bilion) —
do not treat its JUMLAH as the population total.

## Planned next extraction

1. Deepen the findings register: key findings to `maksud` where the report names
   votes, joining PKKP for the "planned vs delivered vs audited-verdict" pairing
   in docs/SOURCES.md; quantify the Ringkasan/Infografik per-chapter digests as a
   cross-check on the register's RM tokens.
2. The Penyata Kewangan volumes' sijil + findings tables (CMD.18.2024 for FY2023,
   CMD.14.2025 Bahagian I/III for FY2024) to extend the audited-restatement series.

Then the standard discipline: reconcile to the report's own printed totals +
independent adversarial verifier pass before any curated or site exposure.

## Historical backfill (`data/lkan_reports_backfill.csv`, 2026-07-31)

**402 further volumes acquired and cover-verified** — 49 federal + 353 state
(all 13 states), tabling years 2015–2026, 12.35 GB in `raw/backfill/`
(gitignored; manifest carries sha256 + the live-verified source URL per file).

Route improvement: Parliament publishes a JSON catalogue of every tabled paper
2013–2026 at `/risalat.html?uweb=dr&ajx=1&arkib=yes` (and `uweb=dn`) — no URL
guessing. Pre-2018 catalogue links are dead but the files were migrated to
`/ipms/eps/<sitting-date>/CMD.<n>.<year> - <free-form name>.pdf`; those were
resolved by probing name variants using directory existence (403 vs 404) as an
oracle.

Audit-year coverage: **2017–2022 essentially complete** (federal 6/6, 8/8, 7/7,
4/4, 7/7, 5/5; state sets near-complete), 2014–2016 partial, **2009–2013
unavailable** — Parliament's online archive simply begins mid-2013 and holds no
LKAN entries before April 2014 (the 2014 tabling directories 404 under every
probed pattern; audit.gov.my remains WAF-blocked; Wayback CDX is blocked by this
environment's egress proxy). ~104 catalogued items unobtainable, each with the
attempts recorded.

**Two server-side mislabels found and excluded, not silently corrected:**
`CMD.31.2016` (catalogued as "Aktiviti … Siri 2") is byte-identical (sha256) to
the Siri 1 volume, and `CMD.42.2017` (catalogued as Sarawak Penyata Kewangan) is
byte-identical to the Selangor volume — so AY2015 Siri 2 Aktiviti (federal) and
Sarawak PK 2016 are effectively unavailable from this route.
