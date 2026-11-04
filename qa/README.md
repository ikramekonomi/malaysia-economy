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

**101 FAIL rows** were already committed when the suite was introduced (2026-11-04):

| Source | FAIL rows |
|---|---|
| state financial statements (Selangor 18, national panel 12, Pahang 9, Johor 5, Negeri Sembilan 3, Sarawak 2, Perlis 2, Kelantan 1, Kedah 1) | 53 |
| PKKP per-year checks (2012, 2015, 2017, 2018, 2020, 2021, 2023) | 26 |
| Anggaran 2025 and 2026 books | 19 |
| Anggaran Hasil 2025 | 2 |
| LKAN fiscal tables | 1 |

Many look like a publisher's printed total that differs from the sum of its printed parts, often
by RM1. Golden rule 2 says those should be recorded as `SOURCE_ANOMALY` with a proof, not left as
`FAIL`. **Triage is open work:** each row becomes either `SOURCE_ANOMALY` (with page evidence) or a
fixed extraction defect, and the baseline shrinks. The suite reports when a known FAIL disappears.
Refresh the baseline only to remove rows, with `python3 qa/run_offline_suite.py --baseline`, and
review the diff before committing it.

## What the suite cannot run yet, and why

| Scripts | Why not | Covered by / unblocked by |
|---|---|---|
| 46 per-year PKKP validators (`sources/pkkp/pipeline/<year>/validate*.py`) | written for the original extraction machine: hard-coded `/home/claude/pkkp/...` paths | to port to repo-relative paths; their outputs are committed and checked for FAIL rows |
| `sources/audit-negara/pipeline/validate_lkan_findings.py`, `validate_lkan_fiscal.py` and every `extract_*.py` | re-read the original PDFs, which are not in the repository | the L0 archive (Phase 0) |
| `sources/dosm/pipeline/verify_*.py`, `refresh.py`; `sources/bnm/pipeline/fetch_*.py` | need the network | the daily DOSM refresh workflow (`dosm-refresh.yml`); a BNM refresh to follow |
