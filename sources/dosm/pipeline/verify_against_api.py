#!/usr/bin/env python3
"""Cross-check the canonical DOSM CSVs in data/ against the OpenDOSM static API.

The API (https://developer.data.gov.my/static-api/opendosm) serves JSON slices of the
same datasets whose canonical full files we ingest from storage.dosm.gov.my — so it is
an independent retrieval path over the same publication, useful to detect a corrupted
download or a silent revision. It is NOT the canonical store here (full files are:
byte-stable, unpaginated, and exactly what the catalogue's download button serves).

Compares every overlapping (key, value) pair; exits non-zero on any mismatch.
Run ad hoc or after re-downloading the CSVs.
"""
import csv
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
API = "https://api.data.gov.my/opendosm"


def fetch(dataset_id, extra=""):
    url = f"{API}?id={dataset_id}&limit=100000{extra}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def check(name, api_rows, csv_rows, key, cols, tol=1e-6):
    api_map = {tuple(r[k] for k in key): r for r in api_rows}
    n = miss = bad = 0
    for r in csv_rows:
        k = tuple(r[c] for c in key)
        a = api_map.get(k)
        if a is None:
            miss += 1
            continue
        for c in cols:
            va, vc = a.get(c), r.get(c)
            va = None if va in (None, "") else float(va)
            vc = None if vc in (None, "") else float(vc)
            if (va is None) != (vc is None) or (va is not None and abs(va - vc) > tol):
                bad += 1
                print(f"  MISMATCH {name} {k} {c}: csv={vc} api={va}")
        n += 1
    print(f"{name}: {n} rows compared, {miss} not in API slice, {bad} value mismatches")
    return bad


bad = 0
gdp_csv = list(csv.DictReader(open(os.path.join(DATA, "gdp_gni_annual_nominal.csv"))))
bad += check("gdp_gni_annual_nominal", fetch("gdp_gni_annual_nominal"), gdp_csv,
             ("series", "date"), ("gdp", "gni", "gdp_capita", "gni_capita"))

pop_csv = [r for r in csv.DictReader(open(os.path.join(DATA, "population_malaysia.csv")))
           if r["sex"] == "both" and r["age"] == "overall" and r["ethnicity"] == "overall"]
bad += check("population_malaysia (both/overall/overall)",
             fetch("population_malaysia", "&filter=both@sex,overall@age,overall@ethnicity"),
             pop_csv, ("date",), ("population",))

hh_csv = list(csv.DictReader(open(os.path.join(DATA, "hh_lq.csv"))))
bad += check("hh_profile (hh_lq)", fetch("hh_profile"), hh_csv,
             ("date",), ("households", "living_quarters"))

sys.exit(1 if bad else 0)
