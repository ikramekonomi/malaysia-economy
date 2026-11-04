#!/usr/bin/env python3
"""After `refresh.py --apply`: measure what changed against a git ref, and decide whether the
refresh may merge on its own.

  python3 sources/dosm/pipeline/refresh_report.py [--ref origin/main] [--out report.md]

Writes a markdown report (per dataset: rows, latest period, new rows, revised rows and the
years they fall in, header changes) and applies the merge gate. Exit 0 = every gate condition
holds, the refresh may merge itself; exit 3 = a person must review (the report says why).

Revised rows are compared as numbers, ignoring the retrieved_* provenance columns, so a
`25431356829.0` -> `25431356829` reformat is not a revision.

Gate (docs/DATA_MODEL.md D20): no FAIL row in any DOSM or labour validation file; no
SOURCE_ANOMALY row that the ref does not already have; no CSV header change. The verifiers'
own exit codes are checked by the workflow that calls this.
"""
import csv
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = "sources/dosm/data"
VALIDATIONS = ["sources/dosm/data/_validation_realeconomy.csv",
               "sources/dosm/data/_validation_expansion.csv",
               "curated/_validation_labour.csv"]


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True).stdout


def at_ref(ref, path):
    return git("show", f"{ref}:{path}")


def rows_of(text):
    return list(csv.DictReader(io.StringIO(text))) if text else []


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def differs(a, b):
    if a == b:
        return False
    x, y = num(a), num(b)
    if x is None or y is None:
        return True
    return abs(x - y) > 1e-9 * max(1.0, abs(x))


def compare(ref, path):
    old_text, new_text = at_ref(ref, path), open(os.path.join(REPO, path)).read()
    old, new = rows_of(old_text), rows_of(new_text)
    old_hdr = old_text.splitlines()[0].strip() if old_text else ""
    new_hdr = new_text.splitlines()[0].strip() if new_text else ""
    cols = [c for c in (new[0] if new else {}) if not c.startswith("retrieved")]
    val = [c for c in cols if c != "date" and all(num(r[c]) is not None or r[c] == "" for r in new)
           and any(r[c] != "" for r in new)]
    key = [c for c in cols if c not in val]
    k = lambda r: tuple(r.get(c, "") for c in key)
    o, n = {k(r): r for r in old}, {k(r): r for r in new}
    revised = [x for x in n if x in o and any(differs(o[x].get(c, ""), n[x].get(c, "")) for c in val)]
    years = sorted({n[x].get("date", "")[:4] for x in revised if n[x].get("date")})
    last = lambda rs: max((r.get("date", "") for r in rs), default="")
    return {"dataset": os.path.basename(path)[:-4], "rows_old": len(old), "rows_new": len(new),
            "latest_old": last(old)[:7], "latest_new": last(new)[:7],
            "new": sum(1 for x in n if x not in o), "gone": sum(1 for x in o if x not in n),
            "revised": len(revised), "years": years, "header_changed": old_hdr != new_hdr}


def status_rows(text, status):
    return {tuple(r.values()) for r in rows_of(text) if r.get("status") == status}


def main():
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else "origin/main"
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    changed = [l[3:] for l in git("status", "--porcelain", "--", DATA).splitlines()]
    changed = [p for p in changed if p.endswith(".csv") and not os.path.basename(p).startswith("_")]
    res = [compare(ref, p) for p in sorted(changed)]

    problems = []
    for r in res:
        if r["header_changed"]:
            problems.append(f"header changed in `{r['dataset']}`")
        if r["gone"]:
            problems.append(f"`{r['dataset']}`: {r['gone']} rows no longer published")
    for v in VALIDATIONS:
        cur = open(os.path.join(REPO, v)).read()
        fails = status_rows(cur, "FAIL")
        if fails:
            problems.append(f"{len(fails)} FAIL row(s) in `{v}`")
        new_anom = status_rows(cur, "SOURCE_ANOMALY") - status_rows(at_ref(ref, v), "SOURCE_ANOMALY")
        if new_anom:
            problems.append(f"{len(new_anom)} new SOURCE_ANOMALY row(s) in `{v}`")

    lines = [f"Compared with `{ref}`. {len(res)} dataset(s) changed.", "",
             "| dataset | rows | latest period | new rows | revised rows (years) | header |",
             "|---|---|---|---|---|---|"]
    for r in res:
        yrs = f" ({r['years'][0]}–{r['years'][-1]})" if r["years"] else ""
        lines.append(f"| `{r['dataset']}` | {r['rows_old']:,} → {r['rows_new']:,} | "
                     f"{r['latest_old'] or '—'} → {r['latest_new'] or '—'} | {r['new']:,} | "
                     f"{r['revised']:,}{yrs} | {'**changed**' if r['header_changed'] else 'same'} |")
    lines += ["", "**Merge gate:** " + ("PASS. Every condition holds." if not problems else
              "NEEDS REVIEW. " + "; ".join(problems) + ".")]
    report = "\n".join(lines) + "\n"
    if out:
        open(out, "w").write(report)
    print(report)
    sys.exit(0 if not problems else 3)


if __name__ == "__main__":
    main()
