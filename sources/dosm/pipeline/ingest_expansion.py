#!/usr/bin/env python3
"""Ingest the DOSM / data.gov.my expansion datasets (GFS, state GDP, CPI, labour, trade).

Blind-spot #3 expansion beyond the three original denominator datasets: the
machine-readable Government Finance Statistics published on data.gov.my (compiled by
JANM — the Accountant General's Department — and, for state finance, the National
Audit Department), plus state GDP, CPI (national + by state, by division), monthly
labour force principal statistics, and monthly trade toplines from OpenDOSM.

Canonical retrieval path is the catalogue's own storage links
(storage.dosm.gov.my / storage.data.gov.my — the download-button files: byte-stable,
unpaginated). Each file is written to data/<dataset_id>.csv with the source values
verbatim plus two appended provenance columns: retrieved_from (the storage URL) and
retrieved_date. (The three original denominator CSVs predate this convention and stay
byte-for-byte as downloaded — see README.)

After download this script records each dataset in data/_vintage.json (same fields
refresh.py tracks: data_as_of / last_updated / next_update / storage ETag), so
`refresh.py` watches the whole set. Verification is a separate, independent pass:
`verify_expansion.py` re-fetches every dataset through the static API (a second door
onto the same publication) and writes data/_validation_expansion.csv.

Discovery notes (2026-07-31, catalogue = github.com/data-gov-my/datagovmy-meta):
- No consolidated general-government GFS dataset exists in the catalogue — federal
  and state are published separately; consolidation would be a curated/ task.
- State GDP is published in REAL (constant 2015) terms only (gdp_state_real_supply);
  no nominal state GDP dataset exists in the catalogue.
- cpi_headline's underlying file is cpi_2d.csv: headline (division=overall) and the
  13 COICOP divisions in one dataset. cpi_state likewise (cpi_2d_state.csv).
- Deeper detail exists but is deliberately NOT pulled yet (future decision):
  cpi_3d (188 KB) / cpi_4d (424 KB) / cpi_5d (790 KB), trade_enduse_bec (597 KB),
  gdp_district_real_supply (461 KB). Trade by full commodity detail (2d+) is not in
  this catalogue at all (lives in METS/Trade portal).
"""
import csv
import io
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
VINTAGE = os.path.join(DATA, "_vintage.json")
RETRIEVED_DATE = "2026-07-31"

# dataset id -> (storage csv url, api route for metadata/verification)
# route "opendosm" = api.data.gov.my/opendosm; "data-catalogue" = api.data.gov.my/data-catalogue
EXPANSION = {
    # Government Finance Statistics (federal: JANM; state: AUDIT) — all available
    "federal_finance_year": ("https://storage.data.gov.my/publicadmin/federal_finance_year.csv", "data-catalogue"),
    "federal_finance_year_revenue": ("https://storage.data.gov.my/publicadmin/federal_finance_year_revenue.csv", "data-catalogue"),
    "federal_finance_year_oe": ("https://storage.data.gov.my/publicadmin/federal_finance_year_oe.csv", "data-catalogue"),
    "federal_finance_year_de": ("https://storage.data.gov.my/publicadmin/federal_finance_year_de.csv", "data-catalogue"),
    "federal_finance_qtr": ("https://storage.data.gov.my/publicadmin/federal_finance_qtr.csv", "data-catalogue"),
    "federal_finance_qtr_revenue": ("https://storage.data.gov.my/publicadmin/federal_finance_qtr_revenue.csv", "data-catalogue"),
    "federal_finance_qtr_oe": ("https://storage.data.gov.my/publicadmin/federal_finance_qtr_oe.csv", "data-catalogue"),
    "federal_finance_qtr_de": ("https://storage.data.gov.my/publicadmin/federal_finance_qtr_de.csv", "data-catalogue"),
    "lookup_federal_finance": ("https://storage.data.gov.my/publicadmin/federal_finance_lookup.csv", "data-catalogue"),
    "state_finance_revenue": ("https://storage.data.gov.my/publicadmin/state_finance_revenue.csv", "data-catalogue"),
    "state_finance_expenditure": ("https://storage.data.gov.my/publicadmin/state_finance_expenditure.csv", "data-catalogue"),
    # State GDP (annual, by state & sector, constant 2015 prices — no nominal exists)
    "gdp_state_real_supply": ("https://storage.dosm.gov.my/gdp/gdp_state_real_supply.csv", "opendosm"),
    # CPI: national by division (incl. overall = headline) + by state & division
    "cpi_headline": ("https://storage.dosm.gov.my/cpi/cpi_2d.csv", "opendosm"),
    "cpi_state": ("https://storage.dosm.gov.my/cpi/cpi_2d_state.csv", "opendosm"),
    # Labour force principal indicators (monthly)
    "lfs_month": ("https://storage.dosm.gov.my/labour/lfs_month.csv", "opendosm"),
    # Trade toplines (monthly totals + by SITC section; full commodity detail deferred)
    "trade_headline": ("https://storage.dosm.gov.my/trade/trade_headline.csv", "opendosm"),
    "trade_sitc_1d": ("https://storage.dosm.gov.my/trade/trade_sitc_1d.csv", "opendosm"),
}


def api_meta(ds, route):
    url = f"https://api.data.gov.my/{route}?id={ds}&meta=true&limit=1"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["meta"]


def storage_etag(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get("ETag", "").strip('"'), r.headers.get("Last-Modified", "")


def download_with_provenance(url, dest, retrieved_date=RETRIEVED_DATE):
    """Download a storage CSV and append retrieved_from + retrieved_date columns."""
    with urllib.request.urlopen(url, timeout=120) as r:
        raw = r.read().decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(raw)))
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(rows[0] + ["retrieved_from", "retrieved_date"])
        for row in rows[1:]:
            if row:  # skip trailing blank lines
                w.writerow(row + [url, retrieved_date])
    return len(rows) - 1


def main():
    os.makedirs(DATA, exist_ok=True)
    vintage = json.load(open(VINTAGE)) if os.path.exists(VINTAGE) else {}
    total = 0
    for ds, (url, route) in EXPANSION.items():
        dest = os.path.join(DATA, f"{ds}.csv")
        n = download_with_provenance(url, dest)
        total += n
        m = api_meta(ds, route)
        etag, lastmod = storage_etag(url)
        vintage[ds] = {"file": f"{ds}.csv", "data_as_of": m.get("data_as_of"),
                       "last_updated": m.get("last_updated"), "next_update": m.get("next_update"),
                       "api_total_rows": m.get("total"), "storage_etag": etag,
                       "storage_last_modified": lastmod, "api_route": route,
                       "provenance_columns": True}
        print(f"{ds}: {n} rows (data_as_of {m.get('data_as_of')}) -> {dest}")
    json.dump(vintage, open(VINTAGE, "w"), indent=2)
    print(f"total {total} rows across {len(EXPANSION)} datasets; vintage recorded in {VINTAGE}")
    print("next: python3 sources/dosm/pipeline/verify_expansion.py")


if __name__ == "__main__":
    main()
