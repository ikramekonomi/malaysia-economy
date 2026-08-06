#!/usr/bin/env python3
"""Fetch the BNM OpenAPI fiscal tables (MSB section 3.1.x) into canonical CSVs.

API: https://api.bnm.gov.my/public/msb/<table>[/year/<year>]
     header  Accept: application/vnd.BNM.API.v1+json
     (catalogue: https://api.bnm.gov.my/api/specification/categories;
      portal: https://apikijangportal.bnm.gov.my)

Tables (MSB = Monthly Highlights & Statistics numbering):
  3.1    Federal Government Finance (quarterly: revenue, opex, DE, financing)
  3.1.1  Federal Government Revenue
  3.1.2  Federal Government Operating Expenditure by Object
  3.1.3  Federal Government Development Expenditure: Functional Classification
  3.1.4  Federal Government Debt by Remaining Maturity
  3.1.5  Federal Government Domestic Debt by Holder
  3.1.6  Federal Government Debt by Currency and Remaining Maturity

Writes data/msb_<slug>.csv — one row per API record, columns as served plus
provenance (endpoint, retrieved_date, api_last_updated). Values kept verbatim
(strings as served; RM million per MSB convention). Basis: BNM-compiled
("reported"), never blended with audited PKKP figures — see README.
"""
import csv
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
API = "https://api.bnm.gov.my/public/msb"
HDR = {"Accept": "application/vnd.BNM.API.v1+json"}
RETRIEVED_DATE = "2026-07-31"
TABLES = ["3.1", "3.1.1", "3.1.2", "3.1.3", "3.1.4", "3.1.5", "3.1.6"]
YEARS = range(1996, 2027)


def get(url):
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    os.makedirs(DATA, exist_ok=True)
    for t in TABLES:
        rows, last_updated = [], ""
        for y in YEARS:
            d = get(f"{API}/{t}/year/{y}")
            if not d or not d.get("data"):
                continue
            recs = d["data"] if isinstance(d["data"], list) else [d["data"]]
            last_updated = (d.get("meta") or {}).get("last_updated", last_updated)
            for r in recs:
                r["_year_requested"] = y
                rows.append(r)
            time.sleep(0.15)
        if not rows:
            print(f"table {t}: no data")
            continue
        cols = sorted({k for r in rows for k in r}, key=lambda c: (c.startswith("_"), c))
        slug = t.replace(".", "_")
        dest = os.path.join(DATA, f"msb_{slug}.csv")
        with open(dest, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols + ["endpoint", "retrieved_date", "api_last_updated"])
            for r in rows:
                w.writerow([r.get(c, "") for c in cols] +
                           [f"{API}/{t}/year/{r['_year_requested']}", RETRIEVED_DATE, last_updated])
        yrs = sorted({r["_year_requested"] for r in rows})
        print(f"table {t}: {len(rows)} rows, years {yrs[0]}-{yrs[-1]} -> {dest}")


if __name__ == "__main__":
    main()
