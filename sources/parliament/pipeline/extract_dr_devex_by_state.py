#!/usr/bin/env python3
"""Extract Dewan Rakyat written answers that print federal development allocation and spending by state.

  python3 sources/parliament/pipeline/extract_dr_devex_by_state.py -> sources/parliament/data/fact_dr_devex_by_state.csv

Held (sha256 in data/_documents_manifest.csv):
  JBL12122024.pdf  written answers of 12 Dec 2024, question 243 (Mesyuarat Ketiga, Penggal Ketiga, Parlimen ke-15),
                   answered for the Prime Minister by the Minister in the PM's Department (Federal Territories):
                   allocation (PERUNTUKAN), spending (BELANJA), % spent and number of projects by state, for each
                   Rolling Plan RP1-RP4 of RMKe-12; source line 'Sistem MyProjek sehingga 4 November 2024'
                   (pdf pages 701-704). Rolling plans: RP1 = 2021, RP2 = 2022, RP3 = 2023, RP4 = 2024 (RMKe-12's
                   annual rolling plans; the answer prints the RP label, not the year).
Values exactly as printed. RP3 prints, for 7 states, the allocation amount in the BELANJA and % BELANJA columns
(a misprint in the source, kept as printed and registered in data/_source_anomalies.csv). No personal names are
kept: the question is identified by its date and number.
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
PDF = os.path.join(SRC, "raw", "JBL12122024.pdf")
OUT = os.path.join(SRC, "data", "fact_dr_devex_by_state.csv")
GEO = {"Johor": "MY-01", "Kedah": "MY-02", "Kelantan": "MY-03", "Melaka": "MY-04", "Negeri Sembilan": "MY-05",
       "Pahang": "MY-06", "Pulau Pinang": "MY-07", "Perak": "MY-08", "Perlis": "MY-09", "Selangor": "MY-10",
       "Terengganu": "MY-11", "Sabah": "MY-12", "Sarawak": "MY-13", "Wilayah Persekutuan": "MY-14+MY-15+MY-16"}
RP_YEAR = {"RP1": "2021", "RP2": "2022", "RP3": "2023", "RP4": "2024"}
NUM = r"([\d,]+\.\d{2}%?)"
LINE = re.compile(rf"^\s*([A-Za-z][A-Za-z ]*?)?\s+{NUM}\s+{NUM}\s+{NUM}\s+([\d,]+)\s*$")
MEAS = [("peruntukan", "RM juta"), ("belanja", "RM juta"), ("pct_belanja", "%"), ("bilangan_projek", "projects")]


def main():
    out = []
    for p, rp in zip(range(701, 705), ("RP1", "RP2", "RP3", "RP4")):
        lines = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", PDF, "-"], capture_output=True,
                               text=True, check=True).stdout.splitlines()
        if not any(ln.strip() == rp for ln in lines):
            raise SystemExit(f"p{p}: {rp} heading not found")
        pending = ""
        names = []
        for i, ln in enumerate(lines):
            m = LINE.match(ln)
            if not m:
                t = ln.strip()
                if t and not re.search(r"\d", t) and t not in (rp,) and len(t) < 20:
                    pending = (pending + " " + t).strip()
                continue
            label = (m.group(1) or "").strip()
            if not label or label not in GEO:
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                label = " ".join(x for x in (pending if not label else label, nxt) if x).strip()
                if label not in GEO:
                    label = (label.split(" ", 1)[-1] if label.split(" ", 1)[-1] in GEO else label)
            if label not in GEO:
                raise SystemExit(f"p{p} {rp}: unknown row {label!r}: {ln}")
            names.append(label)
            pending = ""
            for (meas, unit), v in zip(MEAS, m.groups()[1:]):
                out.append(dict(document="Jawapan bertulis Dewan Rakyat, 12 Dis 2024", question_no="243",
                                answered_by="Menteri di Jabatan Perdana Menteri (Wilayah Persekutuan)",
                                rolling_plan=rp, year=RP_YEAR[rp], negeri_bm=label, geo_scope=GEO[label], measure=meas,
                                value_printed=v, value=v.replace(",", "").rstrip("%"), unit_printed="%" if v.endswith("%")
                                else unit, data_source_printed="Sistem MyProjek sehingga 4 November 2024",
                                source_file="JBL12122024.pdf", pdf_page=p))
        if sorted(names) != sorted(GEO):
            raise SystemExit(f"p{p} {rp}: rows {names}")
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"dr_devex_by_state: {len(out)} cells -> {os.path.relpath(OUT, SRC)}")


if __name__ == "__main__":
    main()
