#!/usr/bin/env python3
"""Offline checks on the Phase 2 health, education and services datasets (data.gov.my; MOH, MOE, JPN, SPAN, PDRM).

  python3 sources/dosm/pipeline/verify_services.py  -> data/_validation_services.csv

Each file's own aggregates are checked against its own parts (counts are integers, so exact):
  S1 parts sum to the published total: hospital bed types -> 'all'; crime types -> 'all' in each category
  S2 districts sum to their state ('All' / 'All Districts' rows): beds, schools, enrolment, teachers, crime
  S3 states sum to Malaysia: beds, staff, schools, enrolment, teachers
  S4 male + female = both: enrolment, teachers, life expectancy is not additive (skipped)
  S5 bounds: shares in [0, 100], life expectancy in [40, 95], death rate per 1,000 in [0, 30]
A difference is FAIL with the counts; nothing is corrected. A sum where the publisher withholds a
part (blank) is INFO, not compared.
"""
import csv
import os
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = []
ALLD = {"All", "All Districts"}


def rows(name):
    with open(os.path.join(DATA, f"{name}.csv"), newline="") as f:
        return list(csv.DictReader(f))


def num(s):
    s = (s or "").strip()
    return Decimal(s) if s not in ("", "NA", "nan") else None


def add(check, dataset, scope, expected, got):
    if expected is None or got is None:
        OUT.append([check, dataset, scope, expected, got, "", "INFO"])
        return
    d = got - expected
    OUT.append([check, dataset, scope, expected, got, d, "PASS" if d == 0 else "FAIL"])


def sum_check(check, dataset, rs, key_total, key_part, val, is_total, is_part):
    """Group rows by key_total(r); compare the total row with the sum of part rows sharing that key."""
    tot, parts, missing = {}, defaultdict(Decimal), defaultdict(bool)
    for r in rs:
        v = num(r[val])
        if is_total(r):
            tot[key_total(r)] = v
        elif is_part(r):
            k = key_part(r)
            if v is None:
                missing[k] = True
            else:
                parts[k] += v
    for k in sorted(tot):
        if k in parts or k in missing:
            add(check, dataset, "|".join(k), tot[k], None if missing[k] else parts[k])


def main():
    beds = rows("hospital_beds")
    sum_check("S1_types_sum_to_all", "hospital_beds", beds, lambda r: (r["state"], r["district"], r["date"]),
              lambda r: (r["state"], r["district"], r["date"]), "beds", lambda r: r["type"] == "all",
              lambda r: r["type"] != "all")
    sum_check("S2_districts_sum_to_state", "hospital_beds", beds, lambda r: (r["state"], r["type"], r["date"]),
              lambda r: (r["state"], r["type"], r["date"]), "beds",
              lambda r: r["district"] in ALLD and r["state"] != "Malaysia",
              lambda r: r["district"] not in ALLD and r["state"] != "Malaysia")
    sum_check("S3_states_sum_to_malaysia", "hospital_beds", beds, lambda r: (r["type"], r["date"]),
              lambda r: (r["type"], r["date"]), "beds", lambda r: r["state"] == "Malaysia",
              lambda r: r["state"] != "Malaysia" and r["district"] in ALLD)
    staff = rows("healthcare_staff")
    sum_check("S3_states_sum_to_malaysia", "healthcare_staff", staff, lambda r: (r["type"], r["date"]),
              lambda r: (r["type"], r["date"]), "staff", lambda r: r["state"] == "Malaysia",
              lambda r: r["state"] != "Malaysia")
    for name, val, extra in (("schools_district", "schools", ("stage", "type")),
                             ("enrolment_school_district", "students", ("stage", "sex")),
                             ("teachers_district", "teachers", ("stage", "sex"))):
        rs = rows(name)
        k = lambda r, e=extra: tuple(r[x] for x in e) + (r["date"],)  # noqa: E731
        sum_check("S2_districts_sum_to_state", name, rs, lambda r, k=k: (r["state"],) + k(r),
                  lambda r, k=k: (r["state"],) + k(r), val,
                  lambda r: r["district"] in ALLD and r["state"] != "Malaysia",
                  lambda r: r["district"] not in ALLD and r["state"] != "Malaysia")
        sum_check("S3_states_sum_to_malaysia", name, rs, k, k, val, lambda r: r["state"] == "Malaysia",
                  lambda r: r["state"] != "Malaysia" and r["district"] in ALLD)
        if "sex" in extra:
            sum_check("S4_male_plus_female", name, rs,
                      lambda r: (r["state"], r["district"], r["stage"], r["date"]),
                      lambda r: (r["state"], r["district"], r["stage"], r["date"]), val,
                      lambda r: r["sex"] == "both", lambda r: r["sex"] in ("male", "female"))
    crime = rows("crime_district")
    sum_check("S1_types_sum_to_all", "crime_district", crime,
              lambda r: (r["state"], r["district"], r["category"], r["date"]),
              lambda r: (r["state"], r["district"], r["category"], r["date"]), "crimes",
              lambda r: r["type"] == "all", lambda r: r["type"] != "all")
    sum_check("S2_districts_sum_to_state", "crime_district", crime,
              lambda r: (r["state"], r["category"], r["type"], r["date"]),
              lambda r: (r["state"], r["category"], r["type"], r["date"]), "crimes",
              lambda r: r["district"] in ALLD and r["state"] != "Malaysia",
              lambda r: r["district"] not in ALLD and r["state"] != "Malaysia")
    for name, col, lo, hi in (("water_access", "proportion", 0, 100), ("life_expectancy_state", "life_expectancy", 40, 95),
                              ("death_state", "rate", 0, 30)):
        bad = [r for r in rows(name) if num(r[col]) is not None and not (lo <= num(r[col]) <= hi)]
        n = sum(1 for r in rows(name) if num(r[col]) is not None)
        OUT.append(["S5_bounds", name, f"{col} in [{lo}, {hi}]", n, n - len(bad), -len(bad), "PASS" if not bad else "FAIL"])
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "qa"))
    from source_anomaly import classify  # FAIL -> SOURCE_ANOMALY only where the register proves it
    OUT[:] = classify(OUT, os.path.join(DATA, "_source_anomalies_services.csv"))
    with open(os.path.join(DATA, "_validation_services.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "dataset", "scope", "expected", "got", "diff", "status"])
        w.writerows(OUT)
    from collections import Counter
    c = Counter(r[-1] for r in OUT)
    print(f"_validation_services.csv: {len(OUT)} checks, " + ", ".join(f"{v} {k}" for k, v in sorted(c.items())))
    fails = Counter((r[0], r[1]) for r in OUT if r[-1] == "FAIL")
    for k, v in fails.most_common():
        print("  FAIL", v, k)


if __name__ == "__main__":
    main()
