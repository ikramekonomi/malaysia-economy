#!/usr/bin/env python3
"""The contents pages (KANDUNGAN) of every LKAN volume that reports audits of activities or companies, as text.

  python3 sources/audit-negara/pipeline/lkan_toc.py --list          # the volumes, one file name per line
  python3 sources/audit-negara/pipeline/lkan_toc.py [file ...]      # -> data/lkan_toc/<file>.txt for each held PDF

The first step of the audit inventory (Phase 4, D33): the contents pages list every audit of a volume with its
first page. They are kept as printed (pdftotext -layout, page by page, each page headed by its pdf page number),
so that the inventory parser can be written and checked against them without the PDFs, which live in the private
L0 archive (meta/l0_fetch.py; .github/workflows/lkan-extract.yml runs this there).

Where no page of the text layer is a contents page (the 2014-2016 volumes print it as an image), the near-empty
front-matter pages are read by OCR (tesseract, 200 dpi) and headed '=== pdf page N (ocr) ==='; an audit read from
them is OCR-provisional.

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


LENIENT = re.compile(r"\S.*\s{2,}((?:[A-D]\s?-\s?)?\d{1,3}(?:\s?[–-]\s?\d{1,3})?)\s*$|^(\d{1,4}|[ivxl]+)\s{2,}\S")


def count(t, pat):
    return sum(1 for ln in t.splitlines() if pat.match(ln.strip()) and re.search(r"[A-Za-z]{3}", ln))


def ocr(pdf, n):
    """The page as tesseract reads it (image-only contents pages of the 2014-2016 volumes); '' if OCR is absent."""
    import shutil
    import tempfile
    if not shutil.which("tesseract"):
        return ""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-f", str(n), "-l", str(n), "-r", "200", "-gray", "-png", pdf, f"{d}/p"],
                       capture_output=True)
        imgs = sorted(os.listdir(d))
        if not imgs:
            return ""
        return subprocess.run(["tesseract", os.path.join(d, imgs[0]), "-", "--psm", "4"], capture_output=True,
                              text=True).stdout


def toc(pdf):
    """[(pdf page, text, how)]: the contents pages, read from the text layer, or by OCR where the page is an image."""
    texts = {n: page(pdf, n) for n in range(1, 31)}
    has = {n: bool(re.search(r"^\s*(KANDUNGAN|CONTENTS)\s*$", t, re.I | re.M)) for n, t in texts.items()}
    for pat, need in ((ENTRY, 3), (LENIENT, 1)):
        pages, started = [], False
        for n in range(1, 31):
            t, e = texts[n], count(texts[n], pat)
            if has[n] and e >= need:
                started = True
            if started:
                if not has[n] and e < 3:
                    break
                pages.append((n, t, "text"))
                if len(pages) >= 8:
                    break
        if pages:
            return pages
    # no text contents page: OCR the near-empty pages of the front matter
    pages, started = [], False
    for n in range(2, 16):
        if len(texts[n].strip()) > 150:
            if started:
                break
            continue
        t = ocr(pdf, n)
        found = re.search(r"K\s?A\s?N\s?D\s?U\s?N\s?G\s?A\s?N|CONTENTS", t, re.I)
        if found or (started and count(t, LENIENT) >= 3):
            started = True
            pages.append((n, t, "ocr"))
        elif started:
            break
    return pages


def main():
    vols = volumes()
    if "--list" in sys.argv:
        print("\n".join(sorted(vols)))
        return
    os.makedirs(OUT, exist_ok=True)
    todo = [f for f in (sys.argv[1:] or sorted(vols)) if f in vols]  # only the volumes in scope
    done = 0
    for fn in todo:
        pdf = find(fn)
        if not pdf:
            continue
        pages = toc(pdf)
        with open(os.path.join(OUT, fn.replace(".pdf", ".txt")), "w", encoding="utf-8") as f:
            f.write(f"# {vols.get(fn, {}).get('report', '')} | {vols.get(fn, {}).get('scope', '')} | "
                    f"{vols.get(fn, {}).get('volume_title_bm', '')}\n")
            for n, t, how in pages:
                f.write(f"=== pdf page {n}{' (ocr)' if how == 'ocr' else ''} ===\n{t.rstrip()}\n")
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
