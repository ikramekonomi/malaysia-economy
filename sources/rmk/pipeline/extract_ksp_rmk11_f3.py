#!/usr/bin/env python3
"""Extract KSP RMKe-11 (the Eleventh Plan's mid-term review) Jadual F-3: federal development allocation and
spending by state, 2016-2017 (one two-year column each), as printed.

  python3 sources/rmk/pipeline/extract_ksp_rmk11_f3.py -> sources/rmk/data/ksp_rmk11/fact_ksp_rmk11_f3.csv

raw/ksp_rmk11_lampiran_f.pdf, pdf page 5, printed F-5 (sha256 in data/_documents_manifest.csv). Columns as printed:
Peruntukan (RM juta; footnote 1: the revised allocation, 'peruntukan dipinda'), % Jumlah, Perbelanjaan (RM juta),
% Peruntukan. 'Wilayah Persekutuan' is the three Federal Territories together; 'Pelbagai Negeri' (footnote 2) is
projects and programmes carried out across states. Source line: Unit Perancang Ekonomi and Unit Penyelarasan
Pelaksanaan, JPM. Nothing is corrected.
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
PDF = os.path.join(SRC, "raw", "ksp_rmk11_lampiran_f.pdf")
OUT = os.path.join(SRC, "data", "ksp_rmk11", "fact_ksp_rmk11_f3.csv")
GEO = {"Sarawak": "MY-13", "Sabah": "MY-12", "Wilayah Persekutuan": "MY-14+MY-15+MY-16", "Selangor": "MY-10",
       "Pahang": "MY-06", "Johor": "MY-01", "Perak": "MY-08", "Kelantan": "MY-03", "Kedah": "MY-02",
       "Terengganu": "MY-11", "Pulau Pinang": "MY-07", "Negeri Sembilan": "MY-05", "Melaka": "MY-04", "Perlis": "MY-09",
       "Pelbagai Negeri": "_unallocated", "Jumlah": "MY"}
COLS = [("peruntukan_dipinda_2016_2017", "RM juta"), ("peruntukan_pct_jumlah", "%"),
        ("perbelanjaan_2016_2017", "RM juta"), ("perbelanjaan_pct_peruntukan", "%")]
ROW = re.compile(r"^\s*(\d{1,2})?\s+([A-Z][A-Za-z ]+?)(2)?\s+([\d,]+)\s+([\d.]+)\s+([\d,]+)\s+([\d.]+)\s*$")


def main():
    text = subprocess.run(["pdftotext", "-f", "5", "-l", "5", "-layout", PDF, "-"], capture_output=True, text=True,
                          check=True).stdout.splitlines()
    out = []
    for ln in text:
        m = ROW.match(ln)
        if not m:
            continue
        name = m.group(2).strip()
        if name not in GEO:
            raise SystemExit(f"unknown row {name!r}")
        for (c, u), v in zip(COLS, m.groups()[3:]):
            out.append(dict(document="KSP RMKe-11", jadual="F-3", bil=m.group(1) or "", negeri_bm=name,
                            footnote=m.group(3) or "", geo_scope=GEO[name],
                            row_type="total" if name == "Jumlah" else "line", measure=c, value_printed=v,
                            value=v.replace(",", ""), unit_printed=u, source_file="ksp_rmk11_lampiran_f.pdf",
                            pdf_page="5", printed_page="F-5"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"ksp_rmk11_f3: {len(out) // 4} rows -> {os.path.relpath(OUT, SRC)}")


if __name__ == "__main__":
    main()
