#!/usr/bin/env python3
"""Keep every BNM vintage (docs/DATA_MODEL.md §6, decision D3), the same way as DOSM.

The canonical CSV in data/ is the current vintage. data/_vintage_log.csv lists every vintage the
warehouse has held (dataset, api_last_updated, retrieved_date, rows, sha256), append-only. An earlier
vintage is recovered exactly from git history by its sha256 (same method as
sources/dosm/pipeline/vintage_get.py).

  python3 sources/bnm/pipeline/vintage.py --seed   # log every current file (first run only)

The fetchers call `replace_with_log(dest, write)`: the old file is logged as `superseded` and the
new one as `current`, but only when the bytes actually change.
"""
import csv
import hashlib
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
LOG = os.path.join(DATA, "_vintage_log.csv")
FIELDS = ["dataset", "file", "data_as_of", "retrieved_date", "rows", "sha256", "state", "logged_at"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(path):
    with open(path, newline="") as f:
        r = list(csv.DictReader(f))
    first = r[0] if r else {}
    return {"data_as_of": first.get("api_last_updated", ""), "retrieved_date": first.get("retrieved_date", ""),
            "rows": len(r)}


def log(path, state):
    new = not os.path.exists(LOG)
    d = describe(path)
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        name = os.path.basename(path)
        w.writerow({"dataset": name[:-4], "file": name, **d, "sha256": sha256(path), "state": state,
                    "logged_at": date.today().isoformat()})


def replace_with_log(dest, write):
    """write(tmp_path) writes the new file; it replaces dest, and both vintages are logged if they differ."""
    tmp = dest + ".new"
    write(tmp)
    if os.path.exists(dest) and sha256(dest) == sha256(tmp):
        os.remove(tmp)
        return False
    if os.path.exists(dest):
        log(dest, "superseded")
    os.replace(tmp, dest)
    log(dest, "current")
    return True


def seed():
    if os.path.exists(LOG):
        sys.exit(f"{LOG} already exists; the log is append-only")
    files = sorted(f for f in os.listdir(DATA) if f.startswith("msb_") and f.endswith(".csv"))
    for f in files:
        log(os.path.join(DATA, f), "current")
    print(f"seeded {LOG}: {len(files)} current vintages")


if __name__ == "__main__":
    if "--seed" in sys.argv:
        seed()
    else:
        sys.exit(__doc__)
