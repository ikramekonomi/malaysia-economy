#!/usr/bin/env python3
"""Page evidence from the L0 archive: the text of chosen pages, committed next to the checks.

  python3 meta/l0_pages.py "CMD.61.2015.pdf:39,40 CMD.50.2021.pdf:29-31"
  python3 meta/l0_pages.py --fails        # every page cited by a FAIL row in qa/known_fails.csv (+-1)

For each file, finds its sha256 in meta/l0_archive.csv, downloads `<sha256>.pdf` from the private
`l0-archive` release (`gh`, so it runs on GitHub Actions: `.github/workflows/l0-pages.yml`),
and writes qa/evidence/<file>/p<NNN>.txt: `pdftotext -layout` of that page, headed by the file,
its sha256 and the page number. Evidence files let anyone check a FAIL or SOURCE_ANOMALY offline
against the archived document, and are what a human spot-check reads.
"""
import csv
import glob
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "qa", "evidence")


def parse(spec):
    want = {}
    for part in spec.split():
        name, pages = part.rsplit(":", 1)
        for p in pages.split(","):
            a, _, b = p.partition("-")
            want.setdefault(name, set()).update(range(int(a), int(b or a) + 1))
    return want


def from_fails():
    """Pages cited by the baselined FAIL rows: any cell pair (<file>.pdf, <int>) in the row."""
    want = {}
    for r in csv.DictReader(open(os.path.join(REPO, "qa", "known_fails.csv"))):
        cells = r["row"].split("|")
        for i, c in enumerate(cells[:-1]):
            if c.lower().endswith(".pdf") and re.fullmatch(r"\d+", cells[i + 1] or ""):
                p = int(cells[i + 1])
                want.setdefault(c, set()).update({p - 1, p, p + 1} - {0})
    return want


def main():
    want = from_fails() if "--fails" in sys.argv else parse(" ".join(a for a in sys.argv[1:] if not a.startswith("--")))
    index = {}
    for r in csv.DictReader(open(os.path.join(HERE, "l0_archive.csv"))):
        if r["status"] == "ARCHIVED":
            index.setdefault(r["file_name"], r["sha256"])
    missing = sorted(n for n in want if n not in index)
    with tempfile.TemporaryDirectory() as d:
        for name in sorted(want):
            if name not in index:
                continue
            sha = index[name]
            subprocess.run(["gh", "release", "download", "l0-archive", "-p", f"{sha}.pdf", "-D", d, "--clobber"],
                           check=True)
            pdf = os.path.join(d, f"{sha}.pdf")
            n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True,
                                                                text=True).stdout).group(1))
            os.makedirs(os.path.join(OUT, name), exist_ok=True)
            for p in sorted(x for x in want[name] if 1 <= x <= n):
                t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"],
                                   capture_output=True, text=True).stdout
                with open(os.path.join(OUT, name, f"p{p:03d}.txt"), "w") as f:
                    f.write(f"# {name}  sha256 {sha}  pdf_page {p} of {n}  (pdftotext -layout)\n\n{t}")
            os.remove(pdf)
            print(f"{name}: {len(want[name])} pages")
    if missing:
        print("not in the archive yet:", ", ".join(missing))


if __name__ == "__main__":
    main()
