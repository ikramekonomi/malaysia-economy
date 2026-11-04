#!/usr/bin/env python3
"""Prove a downloaded PDF is the document a source was extracted from (L0 archive, Phase 0).

For PDFs whose sha256 was never recorded (PKKP, Anggaran, Anggaran Hasil), a fresh download is
only accepted into the archive if the figures our rows cite are printed on the pages they cite.

  python3 meta/l0_identity.py <pdf> <source_dir> [--name FILE_NAME] [--sample 400]

Reads every CSV under <source_dir>/data whose rows carry `source_file` and `pdf_page`, keeps the
rows citing FILE_NAME (default: the pdf's basename), and checks a deterministic sample: the
row's amount, formatted as printed (thousands separators; negatives in parentheses), must occur
in the text of that page. Prints one JSON line; exits 0 when every cited page exists and at
least 98% of the sampled amounts are found (90% when the pages had to be OCR'd), else 1.
Needs poppler-utils (pdftotext, pdfinfo); tesseract-ocr for image-only pages.
"""
import csv
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation

AMOUNT_COLS = ("amount_rm", "amount", "value_rm", "value", "jumlah_rm")


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pages(pdf):
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def page_text(pdf, p, cache={}):
    """The page's text layer; for an image-only page (e.g. PKKP FY2015), OCR it with tesseract."""
    if (pdf, p) not in cache:
        t = subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"],
                           capture_output=True, text=True).stdout
        if len(t.strip()) < 20 and shutil.which("tesseract"):
            with tempfile.TemporaryDirectory() as d:
                subprocess.run(["pdftoppm", "-r", "300", "-gray", "-f", str(p), "-l", str(p), "-png", pdf,
                                os.path.join(d, "pg")], capture_output=True)
                png = sorted(glob.glob(os.path.join(d, "pg*.png")))
                if png:
                    t = subprocess.run(["tesseract", png[0], "-", "--psm", "6"], capture_output=True, text=True).stdout
        cache[(pdf, p)] = t
    return cache[(pdf, p)]


def printed_forms(v):
    """Ways the amount can be printed: 1,234,567 / 1 234 567 / (1,234,567) / 1,234,567.00 ..."""
    neg = v < 0
    a = abs(v)
    whole = int(a)
    cents = a - whole
    s = f"{whole:,}"
    forms = {s, s.replace(",", " "), s.replace(",", ".")}
    if cents:
        frac = f"{a:,.2f}"
        forms |= {frac, frac.rstrip("0").rstrip(".")}
    if neg:
        forms |= {f"({x})" for x in list(forms)} | {f"-{x}" for x in list(forms)}
    return forms


def main():
    pdf, src = sys.argv[1], sys.argv[2]
    name = arg("--name", os.path.basename(pdf))
    sample = int(arg("--sample", "400"))
    rows = []
    for p in sorted(glob.glob(os.path.join(src, "data", "**", "*.csv"), recursive=True)):
        if os.path.basename(p).startswith("_"):
            continue
        with open(p, newline="") as f:
            r = csv.DictReader(f)
            cols = r.fieldnames or []
            amt = next((c for c in AMOUNT_COLS if c in cols), None) or next((c for c in cols if c.endswith("_rm")), None)
            if "source_file" not in cols or "pdf_page" not in cols:
                continue
            for row in r:
                if (row["source_file"] or "").split("/")[-1] != name:
                    continue
                rows.append((p, row.get("pdf_page"), row.get(amt) if amt else None))
    n_pages = pages(pdf)
    cited = sorted({int(float(pg)) for _, pg, _ in rows if pg not in (None, "")})
    bad_pages = [pg for pg in cited if pg < 1 or pg > n_pages]
    vals = []
    for p, pg, a in rows:
        try:
            v = Decimal(a)
        except (InvalidOperation, TypeError):
            continue
        if v != 0 and abs(v) >= 1000 and pg not in (None, ""):
            vals.append((int(float(pg)), v))
    step = max(1, len(vals) // sample)
    checked = vals[::step][:sample]
    found = 0
    misses = []
    for pg, v in checked:
        if pg in bad_pages:
            misses.append((pg, str(v)))
            continue
        t = page_text(pdf, pg)
        if any(f in t for f in printed_forms(v)):
            found += 1
        else:
            misses.append((pg, str(v)))
    rate = found / len(checked) if checked else 0.0
    ocr = any(len(subprocess.run(["pdftotext", "-f", str(pg), "-l", str(pg), pdf, "-"], capture_output=True,
                                 text=True).stdout.strip()) < 20 for pg in sorted({pg for pg, _ in checked})[:5])
    ok = bool(rows) and not bad_pages and bool(checked) and rate >= (0.90 if ocr else 0.98)
    print(json.dumps({"file": name, "sha256": sha256(pdf), "size_bytes": os.path.getsize(pdf), "pages": n_pages,
                      "rows_citing": len(rows), "pages_cited": len(cited), "pages_out_of_range": bad_pages[:10],
                      "amounts_checked": len(checked), "amounts_found": found, "match_rate": round(rate, 4), "ocr": ocr,
                      "misses": misses[:10], "identity": "PASS" if ok else "FAIL"}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
