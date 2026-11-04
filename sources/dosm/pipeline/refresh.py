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
_vintage.json, and re-runs the API cross-check.
After applying: update the vintage table in sources/dosm/README.md.
"""
import csv
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date

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
# Expansion datasets (GFS / state GDP / CPI / labour / trade): defined once in
# ingest_expansion.py; their canonical CSVs carry appended provenance columns and are
# re-ingested through that script's writer, and verified by verify_expansion.py.
from ingest_expansion import EXPANSION, download_with_provenance  # noqa: E402
# Real-economy datasets (national accounts, HIES, labour/productivity, activity indices,
# trade depth): same writer, verified by verify_realeconomy.py. Vintage tracking is
# mandatory here, not optional — these are survey estimates that get revised, and the
# series-break register (data/_series_breaks_dosm.csv) depends on knowing which vintage
# a number came from.
from ingest_realeconomy import REALECONOMY  # noqa: E402

for _ds, (_url, _route) in list(EXPANSION.items()) + list(REALECONOMY.items()):
    DATASETS[_ds] = (f"{_ds}.csv", _url)

CATALOGUE_META = ("https://raw.githubusercontent.com/data-gov-my/datagovmy-meta/main/"
                  "data-catalogue/{}.json")


def api_meta(ds):
    route = (EXPANSION.get(ds) or REALECONOMY.get(ds) or (None, "opendosm"))[1]
    if route == "meta":
        # exclude_openapi in the catalogue: the static API does not serve this dataset,
        # so its vintage fields come from the catalogue repo instead. The storage ETag
        # (checked alongside) is what actually detects a new file either way.
        with urllib.request.urlopen(CATALOGUE_META.format(ds), timeout=60) as r:
            m = json.loads(r.read())
        return {k: m.get(k) for k in ("data_as_of", "last_updated", "next_update")}
    url = f"https://api.data.gov.my/{route}?id={ds}&meta=true&limit=1"
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
        if ds in EXPANSION:
            out[ds]["api_route"] = EXPANSION[ds][1]
            out[ds]["provenance_columns"] = True
        elif ds in REALECONOMY:
            out[ds]["api_route"] = REALECONOMY[ds][1]
            out[ds]["provenance_columns"] = True
            out[ds]["block"] = "realeconomy"
    return out


# Every vintage the warehouse has held, append-only (docs/DATA_MODEL.md §6, decision D3).
# The canonical CSV holds the current vintage; an earlier one is recovered exactly with
#   git log --format=%H -S <sha256> -- sources/dosm/data/_vintage_log.csv   (the commit)
#   git show <commit>:sources/dosm/data/<file>                              (the file)
# and verified against the sha256 recorded here.
VINTAGE_LOG = os.path.join(DATA, "_vintage_log.csv")
LOG_FIELDS = ["dataset", "file", "data_as_of", "last_updated", "storage_etag",
              "retrieved_date", "rows", "sha256", "state", "logged_at"]


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def retrieved_date_of(path):
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        first = next(r, None)
    return (first or {}).get("retrieved_date", "")


def log_vintage(ds, fname, meta, path, state):
    """Append one row: `superseded` for the vintage being replaced, `current` for the new
    one. Rows are never edited or removed."""
    new_file = not os.path.exists(VINTAGE_LOG)
    with open(path, newline="") as f:
        rows = sum(1 for _ in f) - 1
    with open(VINTAGE_LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({"dataset": ds, "file": fname, "data_as_of": meta.get("data_as_of"),
                    "last_updated": meta.get("last_updated"),
                    "storage_etag": meta.get("storage_etag"),
                    "retrieved_date": retrieved_date_of(path), "rows": rows,
                    "sha256": file_sha256(path), "state": state,
                    "logged_at": date.today().isoformat()})


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
        if ds in EXPANSION or ds in REALECONOMY:  # appended provenance columns
            download_with_provenance(url, tmp, retrieved_date=date.today().isoformat())
        else:  # original denominator files stay byte-for-byte as downloaded
            urllib.request.urlretrieve(url, tmp)
        added, removed, total = diff_csv(dest, tmp)
        if os.path.exists(dest):  # the outgoing vintage is logged before it is replaced
            log_vintage(ds, fname, base.get(ds, {}), dest, "superseded")
        os.replace(tmp, dest)
        log_vintage(ds, fname, live[ds], dest, "current")
        print(f"applied      {ds}: {fname} now {total} rows (+{added} new/changed, "
              f"-{removed} removed/changed vs previous vintage)")
    json.dump(live, open(VINTAGE, "w"), indent=2)
    print("vintage baseline updated; re-running API cross-checks")
    subprocess.run([sys.executable, os.path.join(HERE, "verify_against_api.py")], check=True)
    if any(ds in EXPANSION for ds in stale):
        subprocess.run([sys.executable, os.path.join(HERE, "verify_expansion.py")], check=True)
    if any(ds in REALECONOMY for ds in stale):
        subprocess.run([sys.executable, os.path.join(HERE, "verify_realeconomy.py")], check=True)
        subprocess.run([sys.executable, os.path.join(HERE, "series_breaks.py")], check=True)
    print("REMEMBER: update the vintage table in sources/dosm/README.md and commit the "
          "new vintage as its own change (never silently).")
    if any(ds in REALECONOMY for ds in stale):
        print("REMEMBER (real economy): a survey revision can move a whole series. Check "
              "data/_series_breaks_dosm.csv still describes the new vintage, and diff the "
              "revised years rather than assuming only the newest period changed.")


if __name__ == "__main__":
    main()
