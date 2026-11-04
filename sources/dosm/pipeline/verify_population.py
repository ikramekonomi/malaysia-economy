#!/usr/bin/env python3
"""Offline checks on the population denominators (Phase 1): do the published parts add up?

  python3 sources/dosm/pipeline/verify_population.py   -> data/_validation_population.csv

Values are thousands of persons printed to one decimal, so each published figure carries up to
0.05 thousand of rounding; a sum of n parts may differ from its printed total by n x 0.05.
  P1  sum of the 16 states and territories = Malaysia, every year (both sexes, all ages, all ethnicities)
  P2  sum of a state's districts = the state, every year the district file covers
  P3  male + female = both, every state and year
A difference inside the rounding allowance is PASS_ROUNDING; beyond it, FAIL. Nothing is corrected.
"""
import csv
import os
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
STEP = Decimal("0.05")


def read(name, keys):
    out = defaultdict(Decimal)
    with open(os.path.join(DATA, name), newline="") as f:
        for r in csv.DictReader(f):
            if r["age"] == "overall" and r["ethnicity"] == "overall":
                out[tuple(r[k] for k in keys) + (r["sex"], r["date"][:4])] += Decimal(r["population"] or 0)
    return out


def status(diff, n):
    if diff == 0:
        return "PASS"
    return "PASS_ROUNDING" if abs(diff) <= STEP * n else "FAIL"


def main():
    nat = read("population_malaysia.csv", [])
    st = read("population_state.csv", ["state"])
    di = read("population_district.csv", ["state", "district"])
    rows = []
    years = sorted({k[-1] for k in st})
    states = sorted({k[0] for k in st})
    for y in years:
        if ("both", y) not in nat:
            continue
        parts = [st[(s, "both", y)] for s in states if (s, "both", y) in st]
        d = sum(parts) - nat[("both", y)]
        rows.append(["P1_states_sum_to_national", "MY", y, nat[("both", y)], sum(parts), d, status(d, len(parts))])
    for s in states:
        for y in sorted({k[-1] for k in di}):
            parts = [v for k, v in di.items() if k[0] == s and k[2] == "both" and k[3] == y]
            if not parts or (s, "both", y) not in st:
                continue
            d = sum(parts) - st[(s, "both", y)]
            rows.append(["P2_districts_sum_to_state", s, y, st[(s, "both", y)], sum(parts), d, status(d, len(parts))])
        for y in years:
            if (s, "male", y) in st and (s, "female", y) in st:
                tot = st[(s, "male", y)] + st[(s, "female", y)]
                d = tot - st[(s, "both", y)]
                rows.append(["P3_male_plus_female", s, y, st[(s, "both", y)], tot, d, status(d, 2)])
    with open(os.path.join(DATA, "_validation_population.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "geo", "year", "printed_total", "sum_of_parts", "diff", "status"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[-1] for r in rows)
    print(f"_validation_population.csv: {len(rows)} checks, " + ", ".join(f"{v} {k}" for k, v in sorted(c.items())))
    for r in rows:
        if r[-1] == "FAIL":
            print("  FAIL", r)


if __name__ == "__main__":
    main()
