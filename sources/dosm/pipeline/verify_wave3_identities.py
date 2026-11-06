#!/usr/bin/env python3
"""The wave 3 files' own identities, offline (registered, never corrected; golden rule 2).

  python3 sources/dosm/pipeline/verify_wave3_identities.py -> sources/dosm/data/_identity_breaches_wave3.csv,
                                                              sources/dosm/data/_validation_wave3_identities.csv
  I1 national row = sum of the states, where a file prints both: timber (by product), water consumption (by
     sector), water production, crops (by crop, area and production), forest reserves, formal wages employees by
     state, Salaries & Wages recipients by state (citizens)
  I2 parts = total: formal wage bands = formal employees; fish landings coasts = Malaysia; electricity
     local_commercial + local_domestic <= local
Tolerances are the printed rounding (whole units: 0.5 a part; formal employees: 50 a part, printed to the nearest
100). A breach beyond the printed rounding is SOURCE_DIVERGENCE (kept as published, listed in the breaches file); a
checker failure is FAIL. Exit 1 only on FAIL.
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
NAT = {"Malaysia", "All States"}


def rows(ds):
    return list(csv.DictReader(open(os.path.join(DATA, f"{ds}.csv"), encoding="utf-8")))


def sums(ds, val, keys, tol, skip=()):
    nat, parts, n = {}, defaultdict(D), defaultdict(int)
    for r in rows(ds):
        if not r[val] or r["state"] in skip:
            continue
        k = tuple(r[x] for x in keys)
        if r["state"] in NAT:
            nat[k] = D(r[val])
        else:
            parts[k] += D(r[val])
            n[k] += 1
    out = []
    for k, v in nat.items():
        d = parts[k] - v
        if abs(d) > tol * max(1, n[k]):
            out.append((ds, val, "|".join(k), str(v), str(parts[k]), str(d)))
    return len(nat), out


def main():
    checks, breaches = [], []
    for ds, val, keys, tol, skip in (("timber_production", "production", ("date", "product"), D("0.5"), ()),
                                     ("water_consumption", "value", ("date", "sector"), D("0.5"), ()),
                                     ("water_production", "value", ("date",), D("0.5"), ()),
                                     ("crops_state", "planted_area", ("date", "crop_type"), D("0.5"), ()),
                                     ("crops_state", "production", ("date", "crop_type"), D("0.5"), ()),
                                     ("forest_reserve_state", "area", ("date",), D("0.5"), ("Semenanjung Malaysia",)),
                                     ("formal_wages_state", "employees", ("date",), D("50"), ()),  # rounded to 100
                                     ("wages_state", "recipients", ("date", "sex"), D("0.05"), ())):
        n, b = sums(ds, val, keys, tol, skip)
        breaches += b
        checks.append(dict(check="I1 national = sum of states", dataset=f"{ds}.{val}",
                           status="PASS" if not b else "SOURCE_DIVERGENCE", detail=f"{n} national rows; {len(b)} differ"))
    fw = {r["date"]: D(r["employees"]) for r in rows("formal_wages") if r["sex"] == "both" and r["ethnicity"] == "overall"
          and r["age"] == "overall"}
    bands = defaultdict(D)
    for r in rows("formal_wages_band"):
        bands[r["date"]] += D(r["employees"])
    b = [("formal_wages_band", "employees", d, str(fw[d]), str(v), str(v - fw[d])) for d, v in bands.items()
         if d in fw and abs(v - fw[d]) > 50 * 15]  # 15 bands, each rounded to 100
    breaches += b
    checks.append(dict(check="I2 wage bands = formal employees", dataset="formal_wages_band",
                       status="PASS" if not b else "SOURCE_DIVERGENCE", detail=f"{len(bands)} months; {len(b)} differ"))
    fish = defaultdict(dict)
    for r in rows("fish_landings"):
        if r["state"] in NAT:
            fish[r["date"]][r["coast"]] = D(r["landings"])
    b = [("fish_landings", "landings", d, str(v["all"]), str(v["west"] + v["east"] + v["borneo"]),
          str(v["west"] + v["east"] + v["borneo"] - v["all"])) for d, v in fish.items()
         if {"all", "west", "east", "borneo"} <= set(v) and abs(v["west"] + v["east"] + v["borneo"] - v["all"]) > D("1.5")]
    breaches += b
    checks.append(dict(check="I2 coasts = Malaysia", dataset="fish_landings", status="PASS" if not b else "SOURCE_DIVERGENCE",
                       detail=f"{len(fish)} months; {len(b)} differ"))
    with open(os.path.join(DATA, "_identity_breaches_wave3.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["dataset", "column", "key", "published_total", "sum_of_parts", "difference"])
        w.writerows(sorted(breaches))
    with open(os.path.join(DATA, "_validation_wave3_identities.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "dataset", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(checks)
    print(f"wave3 identities: {len(checks)} checks, {len(breaches)} source divergences registered")
    sys.exit(0)


if __name__ == "__main__":
    main()
