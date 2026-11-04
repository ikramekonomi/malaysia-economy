#!/usr/bin/env python3
"""Phase 2 'done when': the core reproduces today's curated tables to the last printed digit.

Each curated row is rebuilt from core observations through the agent tools (get_series + derive), never
from the curated file or the L1 CSV, and compared at the curated table's own printed precision.
Writes qa/_validation_reproduce.csv (one row per curated cell; FAIL blocks the PR like any other).

    python3 qa/reproduce_curated.py

Covered so far: curated/fact_labour_indicators.csv (labour share of GDP, implied average wage).
"""
import csv
import os
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from apps.tools.warehouse_tools import Tools  # noqa: E402


def places(printed):
    return len(printed.split(".")[1]) if "." in printed else 0


def at(value, printed):
    """value rounded to the printed precision; the same answer under half-up and half-even, or flagged."""
    q = Decimal(1).scaleb(-places(printed))
    up, even = value.quantize(q, ROUND_HALF_UP), value.quantize(q, ROUND_HALF_EVEN)
    return up, up != even


def obs(t, ind, year):
    r = t.get_series(ind, "MY", year, year)
    return r["rows"][0]["obs_id"] if r.get("held") and len(r["rows"]) == 1 else None


def labour(t, out):
    path = os.path.join(REPO, "curated", "fact_labour_indicators.csv")
    for r in csv.DictReader(open(path, newline="")):
        y, ind = r["year"], r["indicator"]
        comp = obs(t, "na.compensation_of_employees", y)
        if ind == "implied_average_wage_rm_per_worker_year":
            op, other, scale = "per_employed", obs(t, "lfs.employed", y), Decimal(1)
        elif ind == "labour_share_of_gdp_pct":
            op, other, scale = "ratio", obs(t, "gdp.nominal", y), Decimal(100)
        else:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "no rule to reproduce it"])
            continue
        if not comp or not other:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "input not held in core"])
            continue
        d = t.derive(op, comp, other)
        if not d.get("ok"):
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", d.get("refused")])
            continue
        got, tie = at(Decimal(d["value"]) * scale, r["value"])
        ok = got == Decimal(r["value"])
        out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], str(got), "PASS" if ok else "FAIL",
                    f"core: derive('{op}') {d['derivation_id']}" + (" (rounding tie)" if tie else "")])


def main():
    t = Tools()
    out = []
    labour(t, out)
    with open(os.path.join(REPO, "qa", "_validation_reproduce.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "cell", "curated", "core", "status", "note"])
        w.writerows(out)
    bad = [r for r in out if r[4] != "PASS"]
    print(f"reproduce: {len(out) - len(bad)} of {len(out)} curated cells reproduced from core "
          f"(release {t.w.release_id})")
    for r in bad[:10]:
        print("  FAIL", r)


if __name__ == "__main__":
    main()
