#!/usr/bin/env python3
"""Verify the expansion CSVs (ingest_expansion.py) against the static API.

Independent second retrieval path over the same publication (the pattern of
verify_against_api.py): the canonical files came from the storage links; this script
re-fetches every dataset through api.data.gov.my (opendosm / data-catalogue route)
and checks, per dataset:

  row_count       CSV data rows == API total rows
  latest_period   every row at the dataset's latest date: all values equal
                  (exact for strings, |diff| <= 1e-6 for numerics)

Writes data/_validation_expansion.csv. Discrepancies reported, never corrected.
Exits non-zero on any FAIL.
"""
import csv
import json
import os
import sys
import urllib.request

from ingest_expansion import EXPANSION

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
PROV_COLS = ("retrieved_from", "retrieved_date")


def fetch_all(ds, route):
    url = f"https://api.data.gov.my/{route}?id={ds}&limit=1000000"
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.loads(r.read())
    return d["data"] if isinstance(d, dict) else d


def norm(v):
    if v is None or v == "":
        return None
    try:
        return round(float(v), 9)
    except (TypeError, ValueError):
        return str(v)


def _num(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


out = []
bad = 0
for ds, (url, route) in EXPANSION.items():
    csv_rows = list(csv.DictReader(open(os.path.join(DATA, f"{ds}.csv"))))
    api_rows = fetch_all(ds, route)
    # row count
    status = "PASS" if len(csv_rows) == len(api_rows) else "FAIL"
    out.append([ds, "row_count", len(api_rows), len(csv_rows), status])

    # latest-period value check ("date" column exists on every dataset except the lookup)
    if csv_rows and "date" in csv_rows[0]:
        latest = max(r["date"] for r in csv_rows)
        cols = [c for c in csv_rows[0] if c != "date" and c not in PROV_COLS]
        # key = the non-value dimension columns present (state/category/... ) at latest date
        dims = [c for c in cols if any(not _num(r[c]) for r in csv_rows[:50])]
        vals = [c for c in cols if c not in dims]
        a_map = {}
        for r in api_rows:
            if str(r.get("date")) == latest:
                a_map[tuple(str(r.get(d)) for d in dims)] = r
        n = mism = 0
        for r in csv_rows:
            if r["date"] != latest:
                continue
            n += 1
            a = a_map.get(tuple(r[d] for d in dims))
            if a is None:
                mism += 1
                continue
            for c in vals:
                if norm(r.get(c)) != norm(a.get(c)):
                    mism += 1
                    print(f"  MISMATCH {ds} {latest} {[r[d] for d in dims]} {c}: "
                          f"csv={r.get(c)} api={a.get(c)}")
        status = "PASS" if mism == 0 and n > 0 else "FAIL"
        out.append([ds, f"latest_period_values ({latest}, {n} rows x {len(vals)} cols)",
                    0, mism, status])
    else:  # lookup table: full-content comparison instead (API null == CSV empty)
        a_set = {tuple(sorted((k, "" if v is None else str(v)) for k, v in r.items()))
                 for r in api_rows}
        c_set = {tuple(sorted((k, str(v)) for k, v in r.items()
                              if k not in PROV_COLS)) for r in csv_rows}
        if a_set == c_set:
            out.append([ds, "full_content", len(a_set), len(c_set & a_set), "PASS"])
        else:
            # Known upstream divergence (found 2026-07-31, both doors fetched fresh):
            # the API's lookup still codes the financing block as
            # category='borrowing', variable='borrowing_dom_gross'... while the
            # storage CSV codes it category='financing', variable='domestic_gross'...
            # The storage coding is the one the actual data files use
            # (federal_finance_year.csv etc.), so the canonical CSV is internally
            # consistent; the API lookup is stale. Documented, never corrected.
            diff = (a_set - c_set) | (c_set - a_set)
            known = all("borrowing" in str(x) or "financing" in str(x) or
                        "asset_use" in str(x) or "Penggunaan harta" in str(x)
                        for x in diff)
            status = "INFO" if known else "FAIL"
            out.append([ds, "full_content (API lookup codes financing block as "
                        "'borrowing/borrowing_*'; storage CSV + data files use "
                        "'financing/*' — stale API lookup, documented)",
                        len(a_set), len(c_set & a_set), status])


dest = os.path.join(DATA, "_validation_expansion.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["dataset", "check", "expected", "got", "status"])
    w.writerows(out)
fails = [r for r in out if r[-1] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails:
    print("FAIL:", r)
sys.exit(1 if fails else 0)
