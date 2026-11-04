# qa/ — the checks that guard the warehouse

## The offline check suite (runs on every PR)

`python3 qa/run_offline_suite.py` is what `.github/workflows/validate.yml` runs on every pull request
and on `main`. It needs no PDFs and no network, and takes about 20 seconds. A PR is blocked when:

1. **a script fails**: any of the 53 scripts in its `SUITE` list exits non-zero;
2. **outputs don't reproduce**: re-running the pipeline changes any committed file, so the committed
   CSVs are not exactly what the code produces from the committed inputs;
3. **a new FAIL appears**: a row with status `FAIL` in any `_validation*.csv` that is not listed in
   `qa/known_fails.csv`.

Tested on a clean checkout of `main` (PASS), with an injected FAIL row (blocked) and with a tampered
`curated/fact_fiscal_headline.csv` (blocked).

## The known-FAIL baseline (`known_fails.csv`)

**101 FAIL rows** were already committed when the suite was introduced (2026-11-04). Triage turns
each into either a `SOURCE_ANOMALY` (the publisher's printed total differs from its printed parts,
proved on the page) or a fixed extraction defect:

| Source | FAIL rows at start | Now | How |
|---|---|---|---|
| Anggaran 2025 and 2026 books | 19 | 0 | every total and part re-read on the page of the re-downloaded PDF; publisher rounding (RM1-2) and one RM8 mil roll-up misprint |
| Anggaran Hasil 2025 | 2 | 0 | same; a group impact printed RM500,000 off its own items |
| state financial statements | 53 | 29 | all volumes archived; the re-extraction reproduces every state fact file (`states-extract.yml`). Fixed in the extractor: Johor prior-year adjustment, Pahang water-supply head, public-debt subtotals and movement tables (Pahang, Selangor). Page-proved (`state_config.PAGE_PROVED_ANOMALIES`): Selangor FY2019 trust subtotal, Johor FY2019 revenue total, Kelantan FY2018 footnoted rounding, Kedah FY2016 restated column, Perlis FY2024 restatement. Our defects still open (`KNOWN_EXTRACTION_DEFECTS`): column pairing (Selangor, Negeri Sembilan), Selangor loan-account columns, Sarawak split label, Johor FY2015 column order |
| PKKP per-year checks | 26 | 9 | 15 proved on the archived pages (`qa/evidence/`) and registered in `sources/pkkp/data/<year>/_source_anomalies_<year>.csv`: mislabelled or short subtotals (2012, 2021, 2023), a foreign-repayment total left out and later corrected by the publisher (2017, 2018), stale comparatives (2021), a RM0.99 rounding clash between two statements (2017). Left: 2015 (image-only scan, not identified), 2020 (ANM 404): the Sinar Project mirrors failed the identity check (2020 compressed copy 133/400, 2015 copy 1/400), so both stay 'PDF not archived' (D24). Also proved: 2021 lease 1-sen print rounding |
| LKAN fiscal tables | 1 | 1 | needs the LKAN volume from the L0 archive |

**How a FAIL becomes a SOURCE_ANOMALY** (`qa/source_anomaly.py`): the source's
`_source_anomalies*.csv` row gains an `explains` column naming the exact validation rows it
accounts for (all cells but the status, expected and got values included). The validator then
labels those rows `SOURCE_ANOMALY`. If the values ever change, the match breaks and the row is a
`FAIL` again. No figure is changed; only the label, with the proof in the register. For check files no
CI script can rebuild (the PKKP 2013–2024 core checks, written by the extraction run), the suite
applies the registers in the same folder itself, with the same whole-row rule.

Refresh the baseline only to remove rows, with `python3 qa/run_offline_suite.py --baseline`, and
review the diff before committing it.

## What the suite cannot run yet, and why

| Scripts | Why not | Covered by / unblocked by |
|---|---|---|
| 20 of the 46 per-year PKKP validators (`sources/pkkp/pipeline/<year>/validate*.py`; the other 26 are in the suite, now on repo-relative paths) | 3 read text caches that are not in the repository: `2011/validate_lampiran1_2011.py` and `2011/validate_timeseries_2011.py` (`work/2011/full.txt`, the PDF text) and `2009/validate_opex.py` (`/tmp/opex_recs.json`, an extraction intermediate). 17 run but do not reproduce their committed output, because each writes only part of a file that the extraction pipeline (`run_all.sh`) assembles: `validate.py` for 2009-2014 and 2016-2023 appends its block to `_validation_checks_<year>.csv`, `2024/validate.py` rewrites `_validation_checks.csv` without the notes rows `extract_notes_detail.py` adds, and the committed files of two others hold rows a verifier changed after the run: `2010/validate_master_2010.py` omits a verifier DIAGNOSIS row, `2013/validate_2013.py` writes PASS for 4 cash-statement rows the verifier relabelled INFO (not a printed total). Two also differ in content: 2017 (a verifier-corrected DIAGNOSIS text) and 2021 (devex program linkage for P.28 now comes out FAIL, committed PASS: P.28 has two programmes whose names differ only in case, `PROJEK PENGANGKUTAN JALAN` RM70.67 mil and `Projek Pengangkutan Jalan` RM698.93 mil, each matching its own projects exactly; the check keys programmes by name and merges them. A checker defect, not a data error: to key by position or code) | the L0 archive for the PDFs; making each validator own its output file; their committed outputs are checked for FAIL rows |
| `sources/audit-negara/pipeline/validate_lkan_findings.py`, `validate_lkan_fiscal.py` and every `extract_*.py` | re-read the original PDFs, which are not in the repository | the L0 archive (Phase 0) |
| `sources/dosm/pipeline/verify_*.py`, `refresh.py`; `sources/bnm/pipeline/fetch_*.py` | need the network | the daily DOSM refresh workflow (`dosm-refresh.yml`); a BNM refresh to follow |
