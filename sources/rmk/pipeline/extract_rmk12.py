#!/usr/bin/env python3
"""Extract the RMKe-12 (Twelfth Malaysia Plan, 2021-2025) appendix tables that carry the plan's 2025 targets.

  python3 sources/rmk/pipeline/extract_rmk12.py -> sources/rmk/data/rmk12/fact_rmk12_lampiran.csv

Tables (as printed; pdftotext -layout of the cited pages of raw/rmk12.pdf, sha256 in data/_documents_manifest.csv):
  Jadual 5   GDP by state and economic activity, 2015-2025, constant 2015 prices (pdf 486-490, printed A-6 to A-10)
  Jadual 10  federal government financial position, 2015-2025 (pdf 495, A-15)
  Jadual 14  labour force, employment and job creation, 2015-2025 (pdf 499, A-19)
Values exactly as printed: '-' alone = nil (0); a range 'a ~ b' keeps both ends (value = a, value_hi = b). A label
printed over two lines around its numbers ('Perlombongan dan' / numbers / 'Pengkuarian') is joined. Nothing is
corrected; the printed identities are checked by validate_rmk12.py.
"""
import csv
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
PDF = os.path.join(SRC, "raw", "rmk12.pdf")
OUT = os.path.join(SRC, "data", "rmk12", "fact_rmk12_lampiran.csv")
NUM = re.compile(r"(?<![\w.\-])(-?\d[\d,]*(?:\.\d+)?(?:\s*~\s*-?\d[\d,]*(?:\.\d+)?)?|-)(?![\w.])")
STATES = ["Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Pulau Pinang", "Perak", "Perlis",
          "Selangor", "Terengganu", "Sabah", "Sarawak", "WP Kuala Lumpur", "WP Labuan"]
PRINTED = {486: "A-6", 487: "A-7", 488: "A-8", 489: "A-9", 490: "A-10", 495: "A-15", 499: "A-19"}
J5_COLS = ["sebenar_2015", "sebenar_2016", "sebenar_2017", "sebenar_2018", "sebenar_2019", "sebenar_2020",
           "sasaran_2025", "purata_rmk11_2016_2020", "sasaran_purata_rmk12_2021_2025"]
J14_EMP = ["sebenar_2015", "pct_jumlah_2015", "sebenar_2020", "pct_jumlah_2020", "sasaran_2025", "pct_jumlah_2025",
           "purata_rmk11_2016_2020", "sasaran_purata_rmk12_2021_2025", "pewujudan_rmk11_2016_2020",
           "pewujudan_rmk11_pct_jumlah", "sasaran_pewujudan_rmk12_2021_2025", "sasaran_pewujudan_rmk12_pct_jumlah"]
J14_LF = ["sebenar_2015", "sebenar_2020", "sasaran_2025", "purata_rmk11_2016_2020", "sasaran_purata_rmk12_2021_2025"]
J14_3 = ["sebenar_2015", "sebenar_2020", "sasaran_2025"]
FIELDS = ["plan", "jadual", "table_title_bm", "section_bm", "line_bm", "row_type", "measure", "value_printed",
          "value", "value_hi", "unit_printed", "footnote", "source_file", "pdf_page", "printed_page"]
# footnotes as printed, kept as data on the rows they mark (found by the blind verifier, 2026-11-06)
FOOT = {("5", "WP Kuala Lumpur"): "1: Termasuk WP Putrajaya.",
        ("5", "KDNK Per Kapita"): "KDNK per kapita merujuk kepada nilai harga semasa (p. A-10)",
        ("14", "Jumlah Guna Tenaga"): "1: Penerbitan Produktiviti Buruh menggunakan pendekatan pertubuhan dan isi rumah."}


def page(p):
    return subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", PDF, "-"], capture_output=True,
                          text=True, check=True).stdout.splitlines()


def split(line):
    """(label, [number tokens]) of one printed line."""
    toks = [m for m in NUM.finditer(line)]
    if not toks:
        return line.strip(), []
    label = line[:toks[0].start()].strip()
    return label, [t.group(1) for t in toks]


def value(tok):
    if tok == "-":
        return "0", ""
    if "~" in tok:
        a, b = [x.strip().replace(",", "") for x in tok.split("~")]
        return a, b
    return tok.replace(",", ""), ""


def rows_of(lines, start_pat, stop_pat):
    """Yield (label, numbers) for the table body: joins a label printed around its number line."""
    body, on = [], False
    for ln in lines:
        if not on and re.search(start_pat, ln):
            on = True
            continue
        if on and re.search(stop_pat, ln):
            break
        if on and ln.strip():
            body.append(ln)
    out, pending = [], ""
    i = 0
    while i < len(body):
        label, nums = split(body[i])
        if nums and not label:
            nxt = body[i + 1].strip() if i + 1 < len(body) else ""
            tail = nxt if nxt and not split(body[i + 1])[1] else ""
            out.append(((pending + " " + tail).strip(), nums))
            pending = ""
            i += 2 if tail else 1
            continue
        if nums:
            out.append(((pending + " " + label).strip(), nums))
            pending = ""
        else:
            pending = (pending + " " + label).strip()
        i += 1
    return out, pending


def emit(out, jadual, title, section, label, cols, nums, unit, p, row_type):
    foot = "; ".join(x for x in (FOOT.get((jadual, section)), FOOT.get((jadual, label))) if x)
    if (jadual, label) == ("5", "KDNK Per Kapita"):
        unit = "RM (harga semasa)"
    if len(nums) != len(cols):
        sys.exit(f"Jadual {jadual} p{p} {section}/{label}: {len(nums)} numbers for {len(cols)} columns: {nums}")
    for c, t in zip(cols, nums):
        v, hi = value(t)
        u = "%" if c.startswith(("purata", "sasaran_purata", "pct", "pewujudan_rmk11_pct", "sasaran_pewujudan_rmk12_pct")) else unit
        out.append(dict(plan="RMKe-12", jadual=jadual, table_title_bm=title, section_bm=section, line_bm=label,
                        row_type=row_type, measure=c, value_printed=t, value=v, value_hi=hi, unit_printed=u, footnote=foot,
                        source_file="rmk12.pdf", pdf_page=p, printed_page=PRINTED[p]))


def main():
    out = []
    t5 = "Keluaran Dalam Negeri Kasar mengikut Negeri dan Jenis Aktiviti Ekonomi, 2015-2025 (pada harga malar 2015)"
    for p in range(486, 491):
        body, _ = rows_of(page(p), r"^\s*2015\s+2016", r"^\s*(Nota|Sumber)|Rancangan Malaysia Kedua Belas")
        section = None
        for label, nums in body:
            label = label.replace("WP Kuala Lumpur1", "WP Kuala Lumpur")  # footnote marker 1
            if label in STATES and not nums:
                section = label
                continue
            if not nums:
                continue
            # a state name can arrive as the pending label of its first line
            for s in STATES:
                if label.startswith(s + " "):
                    section, label = s, label[len(s) + 1:]
            if section is None:
                sys.exit(f"Jadual 5 p{p}: a row before any state: {label}")
            if label == "KDNK Per Kapita":
                emit(out, "5", t5, section, label, J5_COLS[:7], nums, "RM", p, "total")
            else:
                emit(out, "5", t5, section, label, J5_COLS, nums, "RM juta", p, "total" if label == "KDNK" else "detail")
    t10 = "Kedudukan Kewangan Kerajaan Persekutuan, 2015-2025"
    body, _ = rows_of(page(495), r"^\s*2015\s+2016", r"^\s*Sumber")
    for label, nums in body:
        emit(out, "10", t10, "", label, J5_COLS[:7], nums, "% KDNK" if label.startswith("%") else "RM juta", 495, "line")
    t14 = "Tenaga Buruh, Guna Tenaga dan Pewujudan Pekerjaan, 2015-2025"
    body, _ = rows_of(page(499), r"^\s*orang\s+Jumlah", r"^\s*Nota")
    for label, nums in body:
        cols = J14_EMP if len(nums) == 12 else J14_LF if len(nums) == 5 else J14_3
        unit = "%" if label.endswith("%") or label in ("Lelaki", "Perempuan") else "'000 orang"
        emit(out, "14", t14, "", label.rstrip("1").strip(), cols, nums, unit, 499,
             "total" if label.startswith("Jumlah") else "line")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"rmk12: {len(out)} cells -> {os.path.relpath(OUT, SRC)}")


if __name__ == "__main__":
    main()
