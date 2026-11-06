#!/usr/bin/env python3
"""Verify the wave 3 datasets through a second door: the parquet mirror of the same publication
(the catalogue's link_parquet), not the CSV we stored.

  python3 sources/dosm/pipeline/verify_wave3.py -> data/_validation_wave3.csv

  W1 same row count as the parquet
  W2 every cell equal (numbers within 1e-9 relative; text exactly; empty = NaN), column by column, after
     dropping our two appended provenance columns and sorting both sides the same way
  W3 the stored file's sha256 is the one logged as current in _vintage_log.csv
FAIL on any mismatch. Needs network (not in the offline suite; run after ingest_wave3.py or refresh.py --apply).
"""
import csv
import hashlib
import io
import json
import math
import os
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ingest_wave3 import WAVE3, META_REPO  # noqa: E402

DATA = os.path.join(HERE, "..", "data")


def norm(v):
    if v is None or v is pd.NA or v is pd.NaT or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str) and (v == "" or v.lower() == "nan"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def main():
    cur = {}
    for r in csv.DictReader(open(os.path.join(DATA, "_vintage_log.csv"))):
        if r["state"] == "current":
            cur[r["dataset"]] = r["sha256"]
    out = []
    for ds in WAVE3:
        path = os.path.join(DATA, f"{ds}.csv")
        with urllib.request.urlopen(META_REPO.format(ds), timeout=60) as r:
            pq = json.loads(r.read())["link_parquet"]
        with urllib.request.urlopen(pq, timeout=120) as r:
            p = pd.read_parquet(io.BytesIO(r.read()))
        c = pd.read_csv(path, dtype=str, keep_default_na=False).drop(columns=["retrieved_from", "retrieved_date"])
        cols = list(c.columns)
        out.append(dict(check="W1 row count equals the parquet", dataset=ds, status="PASS" if len(c) == len(p) else "FAIL",
                        detail=f"csv {len(c)} vs parquet {len(p)}"))
        missing = [x for x in cols if x not in p.columns]
        if missing:
            out.append(dict(check="W2 every cell equals the parquet", dataset=ds, status="FAIL", detail=f"columns not in parquet: {missing}"))
            continue
        p = p[cols].copy()
        for x in cols:
            if str(p[x].dtype).startswith("datetime"):
                p[x] = p[x].dt.strftime("%Y-%m-%d")
        key = lambda df: [tuple("" if norm(v) is None else str(norm(v)) for v in row) for row in df.itertuples(index=False)]  # noqa: E731
        a, b = sorted(key(c)), sorted(key(p))
        bad = 0
        for ra, rb in zip(a, b):
            for va, vb in zip(ra, rb):
                if va == vb:
                    continue
                try:
                    fa, fb = float(va), float(vb)
                    if abs(fa - fb) <= 1e-9 * max(1.0, abs(fb)):
                        continue
                except ValueError:
                    pass
                bad += 1
        out.append(dict(check="W2 every cell equals the parquet", dataset=ds, status="PASS" if not bad and len(a) == len(b) else "FAIL",
                        detail=f"{len(a) * len(cols)} cells" + (f"; {bad} differ" if bad else "")))
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        out.append(dict(check="W3 stored file is the logged current vintage", dataset=ds,
                        status="PASS" if cur.get(ds) == h else "FAIL", detail=h[:16]))
    with open(os.path.join(DATA, "_validation_wave3.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "dataset", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    bad = [r for r in out if r["status"] != "PASS"]
    print(f"wave3: {len(out)} checks, {len(bad)} not PASS")
    for r in bad:
        print(" ", r)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
