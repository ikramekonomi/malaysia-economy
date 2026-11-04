#!/usr/bin/env python3
"""Fetch archived raw documents from the private l0-archive release, by series or file name.

  python3 meta/l0_fetch.py --series state_financial_statements --dest sources/audit-negara/raw/backfill
  python3 meta/l0_fetch.py --files CMD.37.2017.pdf CMD.38.2018.pdf --dest /tmp/pdfs

Resolves each file name to its sha256 through meta/registry_file.csv, downloads `<sha256>.pdf` from the
release (`gh`, so it runs on GitHub Actions), checks the sha256 again, and saves it under its own file
name, which is what the extraction scripts expect. Prints one line per file and a summary; exits 1 when
a requested file is not archived yet, unless --allow-missing.
"""
import csv
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def arg(flag, n=1):
    if flag not in sys.argv:
        return None
    i = sys.argv.index(flag)
    vals = []
    for v in sys.argv[i + 1:]:
        if v.startswith("--"):
            break
        vals.append(v)
    return vals if n != 1 else (vals[0] if vals else None)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    dest = arg("--dest") or "."
    series = arg("--series", n=2) or []
    files = set(arg("--files", n=2) or [])
    reg = list(csv.DictReader(open(os.path.join(HERE, "registry_file.csv"), newline="")))
    want = {}
    for r in reg:
        if (r["series_id"] in series or r["file_name"] in files) and len(r["sha256"]) == 64:
            want[r["file_name"]] = r["sha256"]
    archived = {r["sha256"] for r in csv.DictReader(open(os.path.join(HERE, "l0_archive.csv"), newline=""))
                if r["status"] == "ARCHIVED"}
    os.makedirs(dest, exist_ok=True)
    got, missing = 0, []
    for name, sha in sorted(want.items()):
        out = os.path.join(dest, name)
        if os.path.exists(out) and sha256(out) == sha:
            got += 1
            continue
        if sha not in archived:
            missing.append(name)
            continue
        subprocess.run(["gh", "release", "download", "l0-archive", "-p", f"{sha}.pdf", "-D", dest, "--clobber"],
                       check=True)
        os.replace(os.path.join(dest, f"{sha}.pdf"), out)
        if sha256(out) != sha:
            sys.exit(f"sha256 mismatch for {name}: the archive copy is not the registered file")
        got += 1
    print(f"l0_fetch: {got} of {len(want)} files in {dest}; not archived yet: {len(missing)}"
          + (f" ({', '.join(missing[:12])}{' ...' if len(missing) > 12 else ''})" if missing else ""))
    if missing and "--allow-missing" not in sys.argv:
        sys.exit(1)


if __name__ == "__main__":
    main()
