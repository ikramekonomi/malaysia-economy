# qa/ — the checks that guard the warehouse

## The offline check suite (runs on every PR)

`python3 qa/run_offline_suite.py` is what `.github/workflows/validate.yml` runs on every pull request
and on `main`. It needs no PDFs and no network, and takes about 10 seconds. A PR is blocked when:

1. **a script fails**: any of the 23 scripts in its `SUITE` list exits non-zero;
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
| state financial statements | 53 | 53 | needs the state volumes from the L0 archive |
| PKKP per-year checks | 26 | 26 | needs the PKKP volumes (being located, `meta/l0_candidates.csv`) |
| LKAN fiscal tables | 1 | 1 | needs the LKAN volume from the L0 archive |

**How a FAIL becomes a SOURCE_ANOMALY** (`qa/source_anomaly.py`): the source's
`_source_anomalies*.csv` row gains an `explains` column naming the exact validation rows it
accounts for (all cells but the status, expected and got values included). The validator then
labels those rows `SOURCE_ANOMALY`. If the values ever change, the match breaks and the row is a
`FAIL` again. No figure is changed; only the label, with the proof in the register.

Refresh the baseline only to remove rows, with `python3 qa/run_offline_suite.py --baseline`, and
review the diff before committing it.

## What the suite cannot run yet, and why

| Scripts | Why not | Covered by / unblocked by |
|---|---|---|
| 46 per-year PKKP validators (`sources/pkkp/pipeline/<year>/validate*.py`) | written for the original extraction machine: hard-coded `/home/claude/pkkp/...` paths | to port to repo-relative paths; their outputs are committed and checked for FAIL rows |
| `sources/audit-negara/pipeline/validate_lkan_findings.py`, `validate_lkan_fiscal.py` and every `extract_*.py` | re-read the original PDFs, which are not in the repository | the L0 archive (Phase 0) |
| `sources/dosm/pipeline/verify_*.py`, `refresh.py`; `sources/bnm/pipeline/fetch_*.py` | need the network | the daily DOSM refresh workflow (`dosm-refresh.yml`); a BNM refresh to follow |
