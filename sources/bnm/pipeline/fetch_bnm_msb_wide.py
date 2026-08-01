#!/usr/bin/env python3
"""Fetch the wider BNM OpenAPI MSB tables (beyond the fiscal 3.1.x set) into CSVs.

API: https://api.bnm.gov.my/public/msb/<table>[/year/<year>]
     header  Accept: application/vnd.BNM.API.v1+json
     (catalogue: https://api.bnm.gov.my/api/specification/categories;
      tag detail: /api/specification/tag?name=...; portal: apikijangportal.bnm.gov.my)

Companion to fetch_bnm_fiscal.py (which owns 3.1-3.1.6, quarterly). This script pulls
the monetary / banking / markets / external tables in full history:

  1.1    Reserve Money                       1.2    Currency in Circulation by Denom.
  1.3    Monetary Aggregates M1/M2/M3        1.3.1  Broad Money M3 (components)
  1.3.2  Factors Affecting M3                1.4    BNM Statement of Assets
  1.5    BNM Statement of Capital & Liab.    1.7    Banking System Assets
  1.9    Banking System Capital & Liab.      1.10   Loan/Financing Applied by Purpose
  1.12   Loan/Financing Approved             1.14   Loan/Financing Disbursed by Purpose
  1.18   Loan/Financing by Type              1.24   Total Deposits by Type
  1.25   Total Deposits by Holder            2.1    Interest Rates: Banking Institutions
  2.3    Interest Rates: Interbank           2.4    Interest Rates: T-Bills & BNM Bills
  2.5    Market Indicative Yield: MGS        2.6    Exchange Rates: Malaysian Ringgit
  2.9    Funds Raised in Capital Mkt (Public) 2.10  Funds Raised in Capital Mkt (Private)
  3.2    RENTAS Foreign Holdings: Debt & Sukuk 3.7  External Debt
  3.8    External Reserves

Grain note (checked 2026-07-31): the fiscal 3.1.x tables serve QUARTERLY + annual only
(period field: 1Q..4Q / null) — no monthly rows exist for them. The tables above are
mostly MONTHLY (month_dt 1..12) with an annual row (month_dt null); 1.7/1.9/1.10/1.12/
1.14/1.18 carry multiple rows per month (banking-system breakdowns); 3.7 is quarterly.
3.6.2 (External Trade) is in the catalogue but serves no data via the API — skipped.

Writes data/msb_<slug>.csv — one row per API record, columns as served plus
provenance (endpoint, retrieved_date, api_last_updated). Values kept verbatim
(strings as served; RM million per MSB convention unless the table states otherwise).
Context series only — never blended with audited PKKP figures (see README).
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
TABLES = ["1.1", "1.2", "1.3", "1.3.1", "1.3.2", "1.4", "1.5", "1.7", "1.9", "1.10",
          "1.12", "1.14", "1.18", "1.24", "1.25", "2.1", "2.3", "2.4", "2.5", "2.6",
          "2.9", "2.10", "3.2", "3.7", "3.8"]
YEARS = range(1970, 2027)


def get(url):
    req = urllib.request.Request(url, headers=HDR)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


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
            print(f"table {t}: no data", flush=True)
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
        print(f"table {t}: {len(rows)} rows, years {yrs[0]}-{yrs[-1]} -> {dest}", flush=True)


if __name__ == "__main__":
    main()
