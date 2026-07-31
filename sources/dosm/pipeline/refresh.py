#!/usr/bin/env python3
"""Detect and (explicitly) apply new DOSM vintages.

The warehouse pins a retrieval vintage on purpose — a silent upstream revision would
change every %GDP / per-capita ratio with no provenance trail. So updates are pulled,
never pushed, and always leave a record. This script makes that a one-command check:

  python3 sources/dosm/pipeline/refresh.py           # check only (safe, default)
  python3 sources/dosm/pipeline/refresh.py --apply   # download new vintage + diff report

Check mode compares the OpenDOSM static API metadata (data_as_of / last_updated —
https://developer.data.gov.my/static-api/opendosm) and the storage ETag against the
recorded baseline in data/_vintage.json.

Apply mode re-downloads the canonical CSVs, prints a row-level diff summary, updates
_vintage.json, rebuilds the derived denominators, and re-runs the API cross-check.
After applying: update the vintage table in sources/dosm/README.md and rebuild the
dashboard (python3 curated/dashboard/build_dashboard.py).
"""
import csv
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
VINTAGE = os.path.join(DATA, "_vintage.json")

DATASETS = {  # catalogue id -> (csv filename, storage url)
    "gdp_gni_annual_nominal": ("gdp_gni_annual_nominal.csv",
                               "https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv"),
    "population_malaysia": ("population_malaysia.csv",
                            "https://storage.dosm.gov.my/population/population_malaysia.csv"),
    "hh_profile": ("hh_lq.csv", "https://storage.dosm.gov.my/demography/hh_lq.csv"),
}


def api_meta(ds):
    url = f"https://api.data.gov.my/opendosm?id={ds}&meta=true&limit=1"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())["meta"]


def storage_etag(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get("ETag", "").strip('"'), r.headers.get("Last-Modified", "")


def current_state():
    out = {}
    for ds, (fname, url) in DATASETS.items():
        m = api_meta(ds)
        etag, lastmod = storage_etag(url)
        out[ds] = {"file": fname, "data_as_of": m.get("data_as_of"),
                   "last_updated": m.get("last_updated"), "next_update": m.get("next_update"),
                   "api_total_rows": m.get("total"), "storage_etag": etag,
                   "storage_last_modified": lastmod}
    return out


def diff_csv(old_path, new_path):
    old = list(csv.reader(open(old_path))) if os.path.exists(old_path) else []
    new = list(csv.reader(open(new_path)))
    oset, nset = set(map(tuple, old[1:])), set(map(tuple, new[1:]))
    return len(nset - oset), len(oset - nset), len(new) - 1


def main():
    apply = "--apply" in sys.argv
    live = current_state()
    if not os.path.exists(VINTAGE):
        json.dump(live, open(VINTAGE, "w"), indent=2)
        print(f"baseline written to {VINTAGE} (canonical CSVs previously verified "
              "against the API with 0 mismatches); re-run to check for updates")
        return
    base = json.load(open(VINTAGE))
    stale = []
    for ds, cur in live.items():
        b = base.get(ds, {})
        changed = [k for k in ("data_as_of", "last_updated", "storage_etag")
                   if cur.get(k) != b.get(k)]
        if changed:
            stale.append(ds)
            print(f"NEW VINTAGE  {ds}: " + "; ".join(
                f"{k}: {b.get(k)} -> {cur.get(k)}" for k in changed))
        else:
            print(f"up to date   {ds} (data_as_of {cur['data_as_of']}, "
                  f"next update {cur['next_update']})")
    if not stale:
        return
    if not apply:
        print("\nrun with --apply to pull the new vintage (explicit, provenance-updating)")
        sys.exit(2)
    for ds in stale:
        fname, url = DATASETS[ds]
        dest = os.path.join(DATA, fname)
        tmp = dest + ".new"
        urllib.request.urlretrieve(url, tmp)
        added, removed, total = diff_csv(dest, tmp)
        os.replace(tmp, dest)
        print(f"applied      {ds}: {fname} now {total} rows (+{added} new/changed, "
              f"-{removed} removed/changed vs previous vintage)")
    json.dump(live, open(VINTAGE, "w"), indent=2)
    print("vintage baseline updated; rebuilding derived denominators + re-running API cross-check")
    subprocess.run([sys.executable, os.path.join(HERE, "build_denominators.py")], check=True)
    subprocess.run([sys.executable, os.path.join(HERE, "verify_against_api.py")], check=True)
    print("REMEMBER: update the vintage table in sources/dosm/README.md, rebuild the "
          "dashboard, and commit the new vintage as its own change (never silently).")


if __name__ == "__main__":
    main()
