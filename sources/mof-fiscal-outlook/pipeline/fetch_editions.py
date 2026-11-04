#!/usr/bin/env python3
"""Fetch every Tinjauan Fiskal / Fiscal Outlook edition held on belanjawan.mof.gov.my.

Run:  python3 sources/mof-fiscal-outlook/pipeline/fetch_editions.py
Writes: sources/mof-fiscal-outlook/raw/<edition>/<file>.pdf     (gitignored)
        sources/mof-fiscal-outlook/data/_editions_manifest.csv  (committed)

The site's archive (/ms/arkib) reaches back to Budget 2018. Editions before that are not
held there. The document's name and packaging change across years, so each edition lists
the file(s) that carry its statistical tables:

  2018        the Anggaran Hasil (revenue estimates) book -- fetched for the record, but
              it carries NO Federal Government Finance table: before Budget 2019 MOF
              printed its fiscal tables in the Laporan Ekonomi, which this site does not
              hold. Nothing is extracted from it.
  2019-2022, 2024-2027
              st_kewangan.pdf, the Statistik Kewangan Awam appendix, published as its
              own file beside the report
  2023        the re-tabled Belanjawan 2023 (Feb 2023) "Ekonomi & Fiskal" book; its
              statistical tables are jadual_perangkaan.pdf

The manifest records url, bytes, sha256, page count and retrieval date per file, so any
extracted figure can be traced to the exact bytes it was read from.
"""
import csv
import datetime
import hashlib
import os
import subprocess
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RAW = os.path.join(ROOT, "raw")
MANIFEST = os.path.join(ROOT, "data", "_editions_manifest.csv")
BASE = "https://belanjawan.mof.gov.my"

# Per edition: the statistical appendix ("Statistik Kewangan Awam / Public Finance
# Statistics", st_kewangan.pdf) is what the extraction reads -- Jadual 1.1 and 3.1-3.3
# live there. The full report is kept alongside for the editions whose headline figures
# were already extracted from it (2025, 2026) and as context for the rest.
EDITIONS = {
    2018: ["/pdf/2018/fiscal/buku_anggaran_hasil_kerajaan_persekutuan_2018.pdf"],
    2019: ["/pdf/2019/hasil/st_kewangan.pdf",
           "/pdf/2019/hasil/Tinjauan Fiskal_Fiscal Outlook 2019.pdf"],
    2020: ["/pdf/2020/hasil/st_kewangan.pdf"],
    2021: ["/pdf/2021/hasil/st_kewangan.pdf", "/pdf/2021/hasil/tinjauan-fiskal-2021.pdf"],
    2022: ["/pdf/2022/hasil/st_kewangan.pdf", "/pdf/2022/hasil/tinjauan_fiskal_2022.pdf"],
    2023: ["/pdf/belanjawan2023/ekonomi-fiskal/jadual_perangkaan.pdf"],
    2024: ["/pdf/belanjawan2024/hasil/st_kewangan.pdf",
           "/pdf/belanjawan2024/hasil/tinjauan_fiskal_2024.pdf"],
    2025: ["/pdf/belanjawan2025/hasil/st_kewangan.pdf",
           "/pdf/belanjawan2025/hasil/tinjauan_fiskal_2025.pdf"],
    2026: ["/pdf/belanjawan2026/hasil/st_kewangan.pdf",
           "/pdf/belanjawan2026/hasil/tinjauan_fiskal_2026.pdf"],
    2027: ["/pdf/belanjawan2027/hasil/st_kewangan.pdf",
           "/pdf/belanjawan2027/hasil/tinjauan_fiskal_2027.pdf"],
}


def pdf_pages(path):
    out = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return None


def main():
    today = datetime.date.today().isoformat()
    rows = []
    for edition, paths in sorted(EDITIONS.items()):
        os.makedirs(os.path.join(RAW, str(edition)), exist_ok=True)
        for p in paths:
            url = BASE + urllib.parse.quote(p)
            name = os.path.basename(p).replace(" ", "_")
            dest = os.path.join(RAW, str(edition), name)
            if not os.path.exists(dest):
                subprocess.run(["curl", "-sSfL", "-m", "300", "-o", dest, url], check=True)
            with open(dest, "rb") as f:
                head = f.read(5)
                f.seek(0)
                digest = hashlib.sha256(f.read()).hexdigest()
            if head != b"%PDF-":
                raise SystemExit(f"{url}: not a PDF (got {head!r})")
            rows.append({
                "edition": edition, "file": name, "url": url,
                "bytes": os.path.getsize(dest), "sha256": digest,
                "pages": pdf_pages(dest), "retrieved_date": today,
            })
            print(f"{edition}: {name}  {rows[-1]['bytes']:>10,} bytes  {rows[-1]['pages']} pages")
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"-> {MANIFEST}")


if __name__ == "__main__":
    main()
