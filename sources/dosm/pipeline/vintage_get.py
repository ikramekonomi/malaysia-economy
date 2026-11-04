#!/usr/bin/env python3
"""Recover any DOSM vintage the warehouse has ever held, byte for byte.

The canonical CSV in data/ is the current vintage. Every earlier one is listed in
data/_vintage_log.csv (dataset, data_as_of, sha256, ...) and its bytes live in git history.
This finds the commit holding the logged bytes and writes them out, verified by sha256.

  python3 sources/dosm/pipeline/vintage_get.py <dataset>                 # list its vintages
  python3 sources/dosm/pipeline/vintage_get.py <dataset> <data_as_of> <out.csv>
"""
import csv
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOG = os.path.join(REPO, "sources", "dosm", "data", "_vintage_log.csv")


def git(*args, binary=False):
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ds = sys.argv[1]
    rows = [r for r in csv.DictReader(open(LOG)) if r["dataset"] == ds]
    if not rows:
        sys.exit(f"{ds}: not in {LOG}")
    if len(sys.argv) == 2:
        for r in rows:
            print(f"{r['data_as_of']:>10}  {r['state']:<10} retrieved {r['retrieved_date']:<10} "
                  f"{r['rows']:>7} rows  sha256 {r['sha256'][:12]}…")
        return
    as_of, out = sys.argv[2], sys.argv[3]
    want = [r for r in rows if r["data_as_of"] == as_of]
    if not want:
        sys.exit(f"{ds}: no vintage with data_as_of {as_of}")
    sha, path = want[-1]["sha256"], f"sources/dosm/data/{want[-1]['file']}"
    for commit in git("log", "--format=%H", "--", path).split():
        try:
            blob = git("show", f"{commit}:{path}", binary=True)
        except subprocess.CalledProcessError:
            continue
        if hashlib.sha256(blob).hexdigest() == sha:
            open(out, "wb").write(blob)
            print(f"{ds} {as_of}: wrote {out} from commit {commit[:10]} (sha256 verified)")
            return
    sys.exit(f"{ds} {as_of}: sha256 {sha[:12]}… not found in git history")


if __name__ == "__main__":
    main()
