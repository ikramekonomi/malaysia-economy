#!/usr/bin/env python3
"""The offline check suite: what CI runs on every pull request (docs/DATA_MODEL.md §15, Phase 0).

  python3 qa/run_offline_suite.py            # run everything, exit non-zero on any problem
  python3 qa/run_offline_suite.py --baseline # rewrite qa/known_fails.csv from the current FAIL rows

Three gates, all must hold:
  1. RUNS        every script below exits 0 in a clean checkout (no PDFs, no network).
  2. REPRODUCES  re-running them leaves every committed file byte-for-byte unchanged, so the
                 committed CSVs are exactly what the code produces from the committed inputs.
  3. NO NEW FAIL every row with status FAIL in any _validation*.csv is already listed in
                 qa/known_fails.csv. A new FAIL blocks the PR; a FAIL that disappears is reported
                 so the baseline can shrink (run --baseline and commit it).

Scripts that cannot run here are listed in qa/README.md with the reason (they need the original
PDFs, which arrive with the L0 archive, or the network, which the daily refresh workflows cover).
"""
import csv
import glob
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "qa", "known_fails.csv")

# Order matters: the PKKP database first, then source validators, then curated builders.
SUITE = [
    "pipeline/build_duckdb.py",
    "sources/pkkp/pipeline/2009/validate_2012.py",
    "sources/pkkp/pipeline/2009/validate_master_2012.py",
    "sources/pkkp/pipeline/2009/validate_memoranda.py",
    "sources/pkkp/pipeline/2010/validate_2012.py",
    "sources/pkkp/pipeline/2010/validate_devex_2010.py",
    "sources/pkkp/pipeline/2010/validate_master_2012.py",
    "sources/pkkp/pipeline/2010/validate_memoranda.py",
    "sources/pkkp/pipeline/2010/validate_notes_2010.py",
    "sources/pkkp/pipeline/2011/validate_2011.py",
    "sources/pkkp/pipeline/2011/validate_2012.py",
    "sources/pkkp/pipeline/2011/validate_master_2012.py",
    "sources/pkkp/pipeline/2011/validate_memoranda.py",
    "sources/pkkp/pipeline/2012/validate_2012.py",
    "sources/pkkp/pipeline/2012/validate_master_2012.py",
    "sources/pkkp/pipeline/2012/validate_memoranda.py",
    "sources/pkkp/pipeline/2013/validate_memoranda.py",
    "sources/pkkp/pipeline/2014/validate_memoranda.py",
    "sources/pkkp/pipeline/2016/validate_memoranda.py",
    "sources/pkkp/pipeline/2017/validate_memoranda.py",
    "sources/pkkp/pipeline/2018/validate_memoranda.py",
    "sources/pkkp/pipeline/2019/validate_memoranda.py",
    "sources/pkkp/pipeline/2020/validate_memoranda.py",
    "sources/pkkp/pipeline/2021/validate_memoranda.py",
    "sources/pkkp/pipeline/2022/validate_memoranda.py",
    "sources/pkkp/pipeline/2023/validate_memoranda.py",
    "sources/pkkp/pipeline/2024/validate_memoranda.py",
    "sources/anggaran/pipeline/2024/validate_2024.py",
    "sources/anggaran/pipeline/2024/validate_detail_2024.py",
    "sources/anggaran/pipeline/2025/validate_2025.py",
    "sources/anggaran/pipeline/2025/validate_detail_2025.py",
    "sources/anggaran/pipeline/2026/validate_2026.py",
    "sources/anggaran/pipeline/2026/validate_detail_2026.py",
    "sources/anggaran-hasil/pipeline/validate_hasil.py",
    "sources/audit-negara/pipeline/validate_agensi.py",
    "sources/audit-negara/pipeline/validate_eselfaudit.py",
    "sources/mof-fiscal-outlook/pipeline/validate_editions.py",
    "sources/mof-fiscal-outlook/pipeline/validate_headline.py",
    "sources/states/pipeline/validate_states.py",
    "sources/dosm/pipeline/series_breaks.py",
    "sources/dosm/pipeline/verify_population.py",
    "sources/dosm/pipeline/verify_services.py",
    "sources/dosm/pipeline/crosscheck_state_finance.py",
    "sources/bnm/pipeline/validate_bnm.py",
    "curated/pipeline/build_ministry_fiscal.py",
    "curated/pipeline/build_opex_devex_breakdown.py",
    "curated/pipeline/build_obligations.py",
    "curated/pipeline/build_planning_efficiency.py",
    "curated/pipeline/build_gap_views.py",
    "curated/pipeline/build_labour_indicators.py",
    "meta/build_registry.py",
    "core/pipeline/build_entities.py",
    "core/pipeline/build_core.py",
    "core/pipeline/build_flows.py",
    "sources/anggaran/pipeline/validate_lampiran_e.py",
    "core/pipeline/build_gap_need_vs_money.py",
    "core/pipeline/build_gap_federal_vs_state.py",
    "core/pipeline/build_federal_placement.py",
    "core/pipeline/build_gap_budget_vs_actual.py",
    "core/pipeline/build_gap_revenue.py",
    "core/pipeline/build_gap_reported_vs_audited.py",
    "core/pipeline/build_gap_obligations.py",
    "sources/rmk/pipeline/validate_rmk12.py",
    "core/pipeline/build_gap_target.py",
    "apps/models/score_nowcast_2025.py",
    "qa/run_eval.py",
    "qa/reproduce_curated.py",
]
STATUS_COLS = ("status", "result", "verdict", "outcome")


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True).stdout


def validation_files():
    pats = ["sources/**/_validation*.csv", "curated/**/_validation*.csv", "apps/**/_validation*.csv",
            "meta/_validation*.csv", "core/_validation*.csv", "qa/_validation*.csv"]
    return sorted({f for p in pats for f in glob.glob(os.path.join(REPO, p), recursive=True)})


def registered_anomalies(path):
    """Keys explained by the _source_anomalies*.csv registers in the same folder (qa/source_anomaly.py).
    For check files no CI script can rebuild (PKKP 2013-2024 core checks are written by the extraction
    run), the suite applies the register itself: same strict rule, whole row minus status, nothing edited."""
    sys.path.insert(0, os.path.join(REPO, "qa"))
    from source_anomaly import explained
    keys = set()
    for reg in glob.glob(os.path.join(os.path.dirname(path), "_source_anomalies*.csv")):
        keys |= explained(reg)
    return keys


def fail_rows():
    """{(file, row text)} for every FAIL row; row text = the whole row, so a changed value counts as new."""
    out = set()
    for path in validation_files():
        keys = registered_anomalies(path)
        with open(path, newline="") as f:
            r = csv.reader(f)
            head = next(r, None)
            if not head:
                continue
            idx = [i for i, c in enumerate(head) if c.strip().lower() in STATUS_COLS]
            if not idx:
                continue
            for row in r:
                if len(row) > idx[0] and row[idx[0]].strip().upper() == "FAIL":
                    if "|".join(c for i, c in enumerate(row) if i != idx[0]) in keys:
                        continue  # SOURCE_ANOMALY: the register proves it (golden rule 2)
                    out.add((os.path.relpath(path, REPO), "|".join(row)))
    return out


def load_baseline():
    if not os.path.exists(BASELINE):
        return set()
    with open(BASELINE, newline="") as f:
        return {(r["file"], r["row"]) for r in csv.DictReader(f)}


def write_baseline(rows):
    with open(BASELINE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "row"])
        for file, row in sorted(rows):
            w.writerow([file, row])


def summary(lines):
    text = "\n".join(lines) + "\n"
    print(text)
    dest = os.environ.get("GITHUB_STEP_SUMMARY")
    if dest:
        with open(dest, "a") as f:
            f.write(text)


def main():
    if "--baseline" in sys.argv:
        rows = fail_rows()
        write_baseline(rows)
        print(f"wrote {BASELINE}: {len(rows)} known FAIL rows")
        return

    problems, lines = [], ["## Offline check suite", "", "| script | exit | seconds |", "|---|---|---|"]
    before = git("status", "--porcelain", "--untracked-files=no")
    for s in SUITE:
        t0 = time.time()
        p = subprocess.run([sys.executable, os.path.join(REPO, s)], cwd=REPO, capture_output=True, text=True)
        lines.append(f"| `{s}` | {p.returncode} | {time.time() - t0:.0f} |")
        if p.returncode != 0:
            problems.append(f"RUNS: `{s}` exited {p.returncode}: {(p.stderr or p.stdout).strip().splitlines()[-1:]}")

    after = git("status", "--porcelain", "--untracked-files=no")
    if after != before:
        changed = [l[3:] for l in after.splitlines() if l not in before.splitlines()]
        problems.append(f"REPRODUCES: re-running changed {len(changed)} committed file(s): "
                        + ", ".join(f"`{c}`" for c in changed[:10]))

    cur, base = fail_rows(), load_baseline()
    new, gone = cur - base, base - cur
    if new:
        problems.append(f"NO NEW FAIL: {len(new)} FAIL row(s) not in qa/known_fails.csv")
        lines += ["", "New FAIL rows:"] + [f"- `{f}`: {r[:160]}" for f, r in sorted(new)[:20]]
    lines += ["", f"FAIL rows: {len(cur)} (baseline {len(base)}; new {len(new)}; resolved {len(gone)})"]
    if gone:
        lines.append("Some known FAIL rows are gone: run `python3 qa/run_offline_suite.py --baseline` "
                     "and commit qa/known_fails.csv to shrink the baseline.")
    lines += ["", "**Result: " + ("PASS**" if not problems else "FAIL**")] + [f"- {p}" for p in problems]
    summary(lines)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
