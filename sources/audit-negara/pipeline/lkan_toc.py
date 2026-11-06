#!/usr/bin/env python3
"""The contents pages (KANDUNGAN) of every LKAN volume that reports audits of activities or companies, as text.

  python3 sources/audit-negara/pipeline/lkan_toc.py --list          # the volumes, one file name per line
  python3 sources/audit-negara/pipeline/lkan_toc.py [file ...]      # -> data/lkan_toc/<file>.txt for each held PDF

The first step of the audit inventory (Phase 4, D33): the contents pages list every audit of a volume with its
first page. They are kept as printed (pdftotext -layout, page by page, each page headed by its pdf page number),
so that the inventory parser can be written and checked against them without the PDFs, which live in the private
L0 archive (meta/l0_fetch.py; .github/workflows/lkan-extract.yml runs this there).

A volume is in scope when its cover-verified title (data/lkan_reports.csv, data/lkan_reports_backfill.csv) names
activities (AKTIVITI), companies (SYARIKAT) or statutory bodies (BADAN BERKANUN). Contents pages: from the first of the
first 30 with a line that is 'KANDUNGAN' (or 'CONTENTS') alone and three entries, and the pages straight after them that carry on the list
(a line ending in, or in older volumes starting with, a page number), up to 8 pages.
"""
import csv
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
OUT = os.path.join(SRC, "data", "lkan_toc")
SCOPE = re.compile(r"AKTIVITI|SYARIKAT|BADAN BERKANUN", re.I)
# an entry: a page number at the right after a gap of three spaces or more (justified prose has single spaces), or
# (older volumes) at the left; a chapter page '1-1' / '2 – 47' counts
ENTRY = re.compile(r"\S.*\s{3,}((?:[A-D]\s?-\s?)?\d{1,3}(?:\s?[–-]\s?\d{1,3})?)\s*$|^(\d{1,4}|[ivxl]+)\s{2,}\S")


def volumes():
    out = {}
    for name in ("lkan_reports.csv", "lkan_reports_backfill.csv"):
        for r in csv.DictReader(open(os.path.join(SRC, "data", name), encoding="utf-8")):
            if SCOPE.search(r["volume_title_bm"]):
                out[r["file_name"]] = r
    return out


def find(fn):
    for d in ("raw", os.path.join("raw", "backfill")):
        p = os.path.join(SRC, d, fn)
        if os.path.exists(p):
            return p
    return None


def page(pdf, n):
    return subprocess.run(["pdftotext", "-f", str(n), "-l", str(n), "-layout", pdf, "-"], capture_output=True,
                          text=True).stdout


def toc(pdf):
    pages, started = [], False
    for n in range(1, 31):
        t = page(pdf, n)
        # the contents page proper: a line that is the word alone (the cover and the imprint page mention it too)
        has = re.search(r"^\s*(KANDUNGAN|CONTENTS)\s*$", t, re.I | re.M)
        entries = sum(1 for ln in t.splitlines() if ENTRY.match(ln.strip()) and re.search(r"[A-Za-z]{3}", ln))
        if has and entries >= 3:
            started = True
        if started:
            if not has and entries < 3:
                break
            pages.append((n, t))
            if len(pages) >= 8:
                break
    return pages


def main():
    vols = volumes()
    if "--list" in sys.argv:
        print("\n".join(sorted(vols)))
        return
    os.makedirs(OUT, exist_ok=True)
    todo = sys.argv[1:] or sorted(vols)
    done = 0
    for fn in todo:
        pdf = find(fn)
        if not pdf:
            continue
        pages = toc(pdf)
        with open(os.path.join(OUT, fn.replace(".pdf", ".txt")), "w", encoding="utf-8") as f:
            f.write(f"# {vols.get(fn, {}).get('report', '')} | {vols.get(fn, {}).get('scope', '')} | "
                    f"{vols.get(fn, {}).get('volume_title_bm', '')}\n")
            for n, t in pages:
                f.write(f"=== pdf page {n} ===\n{t.rstrip()}\n")
            if not pages:
                # nothing found: say why it may be (a scan has no text; another word for the contents page)
                lens, hits = [], []
                for n in range(1, 21):
                    t = page(pdf, n)
                    lens.append(f"{n}:{len(t.strip())}")
                    hits += [f"p{n}: {ln.strip()[:100]}" for ln in t.splitlines() if re.search(r"kandungan|contents|isi\b",
                                                                                                ln, re.I)]
                f.write("# no contents page found\n# text characters by pdf page: " + " ".join(lens) + "\n")
                f.write("".join(f"# {h}\n" for h in hits[:20]))
        done += 1
        print(f"{fn}: {len(pages)} contents pages")
    print(f"{done} volumes written to {os.path.relpath(OUT, SRC)}")


if __name__ == "__main__":
    main()
