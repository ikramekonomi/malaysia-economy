#!/usr/bin/env python3
"""Extract Lampiran E of the Budget books: actual federal grants to each state government, by grant.

Source table: "PEMBERIAN SEBENAR KERAJAAN PERSEKUTUAN KEPADA KERAJAAN NEGERI TAHUN <Y>" (the 2024 and 2025 books
title it "ANGGARAN PEMBERIAN ... TAHUN <Y>" but print it "SEHINGGA 31 DISEMBER <Y>" and list it as "Pemberian
Sebenar" in their contents; kept as printed, flagged in _source_anomalies_lampiran_e.csv). One table per book,
for the year two before the book: 13 states (no Federal Territory) x the grants paid under T.12 (Tanggungan,
grants and assignments to states), B.11 and B.12 (Treasury votes), with a JUMLAH column and a Jumlah row. RM,
whole ringgit as printed. 'tb' = tidak berkenaan (not applicable: the state is not eligible) -> blank amount,
`printed='tb'`; '-' = nil -> 0 (CLAUDE.md).

Books and where the table sits:
  2021 book -> FY2019  raw/lampiran_e_2021.pdf (the appendix alone, from belanjawan.mof.gov.my/pdf/2021/...)
  2022 book -> FY2020  raw/lampiran_e_2022.pdf
  2023 book -> FY2021  raw/lampiran_e_2023.pdf
  2024 book -> FY2022  raw/Anggaran_Perbelanjaan_Persekutuan_2024.pdf p514
  2025 book -> FY2023  raw/Anggaran_Perbelanjaan_Persekutuan_2025.pdf p536
  2026 book -> FY2024  raw/Anggaran_Perbelanjaan_Persekutuan_2026.pdf p578
Older books are not at the publisher's URLs (checked 2026-11-05).

The column headers are rotated or wrapped multi-line text, so each book's columns are DECLARED below (read from
the page and checked against the printed vote-code row, which the script re-reads: a mismatch stops it). The
FY2019 and FY2020 tables split the road-maintenance grant into three unlabelled sub-columns and a JUMLAH: the
sub-columns are kept as `road_maintenance_part1..3` (row_type `part`) and the grant is its printed JUMLAH.

Output: sources/anggaran/data/<book>/fact_anggaran_lampiran_e_<book>.csv, one row per state (or Jumlah) x
column. Validation: validate_lampiran_e.py.

Run: python3 sources/anggaran/pipeline/extract_lampiran_e.py
"""
import csv
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
RAW = os.path.join(SRC, "raw")

STATES = [("Johor", "MY-01"), ("Kedah", "MY-02"), ("Kelantan", "MY-03"), ("Melaka", "MY-04"),
          ("Negeri Sembilan", "MY-05"), ("Pahang", "MY-06"), ("Perak", "MY-08"), ("Perlis", "MY-09"),
          ("Pulau Pinang", "MY-07"), ("Selangor", "MY-10"), ("Terengganu", "MY-11"), ("Sabah", "MY-12"),
          ("Sarawak", "MY-13")]
LABEL = {"N. Sembilan": "Negeri Sembilan", "P. Pinang": "Pulau Pinang"}

# grant_id -> (printed label, vote)
G = {
    "capitation": ("Pemberian Mengikut Bilangan Penduduk", "T.12"),
    "road_maintenance": ("Pemberian Penyenggaraan Jalan Negeri", "T.12"),
    "road_maintenance_part1": ("Pemberian Penyenggaraan Jalan Negeri (sub-column 1, unlabelled)", "T.12"),
    "road_maintenance_part2": ("Pemberian Penyenggaraan Jalan Negeri (sub-column 2, unlabelled)", "T.12"),
    "road_maintenance_part3": ("Pemberian Penyenggaraan Jalan Negeri (sub-column 3, unlabelled)", "T.12"),
    "special_annual": ("Pemberian Khas Tahunan", "T.12"),
    "revenue_growth": ("Pemberian Pertambahan Hasil", "T.12"),
    "gtbkk": ("Geran Tahunan Kepada Pihak Berkuasa Tempatan (GTBKK)", "T.12"),
    "state_services": ("Bayaran Perkhidmatan Bagi Negeri-Negeri", "B.11"),
    "concurrent_list": ("Pemberian Di Bawah Senarai Bersama", "B.11"),
    "libraries": ("Pemberian Kepada Perpustakaan Negeri", "B.11"),
    "museums": ("Pemberian Kepada Muzium Negeri", "B.11"),
    "petroleum_duty_compensation": ("Bayaran Pemansuhan Duti Import dan Eksais Atas Barangan Petroleum Kepada "
                                    "Negeri Sabah & Sarawak", "B.11"),
    "street_lighting": ("Pemberian Bayaran Bil Lampu Jalan & Lampu Isyarat PBT", "B.11"),
    "tourism": ("Pemberian Pelancongan", "B.11"),
    "tourism_tax": ("Pemberian Cukai Pelancongan", "B.11"),
    "biodiversity_eft": ("Pemberian Insentif Kewangan bagi Konservasi Biodiversity (EFT)", "B.11"),
    "development_level": ("Pemberian Berdasarkan Tahap Pembangunan Ekonomi, Infrastruktur dan Kesejahteraan Hidup",
                          "B.12"),
    "opex_deficit": ("Pemberian Kekurangan Akaun Mengurus", "B.12"),
    "total": ("JUMLAH", ""),
}
ROAD4 = ["road_maintenance_part1", "road_maintenance_part2", "road_maintenance_part3", "road_maintenance"]
TAIL15 = ["capitation", "road_maintenance", "special_annual", "revenue_growth", "gtbkk", "state_services",
          "concurrent_list", "libraries", "museums", "petroleum_duty_compensation", "street_lighting", "tourism_tax"]
BOOKS = {
    "2021": dict(year="2019", file="lampiran_e_2021.pdf", page=None,
                 cols=["capitation"] + ROAD4 + ["special_annual", "revenue_growth", "gtbkk", "state_services",
                       "concurrent_list", "libraries", "museums", "petroleum_duty_compensation", "street_lighting",
                       "development_level", "opex_deficit", "tourism", "total"]),
    "2022": dict(year="2020", file="lampiran_e_2022.pdf", page=None,
                 cols=["capitation"] + ROAD4 + ["special_annual", "revenue_growth", "gtbkk", "state_services",
                       "concurrent_list", "libraries", "museums", "petroleum_duty_compensation", "street_lighting",
                       "tourism", "development_level", "opex_deficit", "total"]),
    "2023": dict(year="2021", file="lampiran_e_2023.pdf", page=None,
                 cols=TAIL15 + ["development_level", "opex_deficit", "total"]),
    "2024": dict(year="2022", file="Anggaran_Perbelanjaan_Persekutuan_2024.pdf", page=514,
                 cols=TAIL15 + ["development_level", "opex_deficit", "total"]),
    "2025": dict(year="2023", file="Anggaran_Perbelanjaan_Persekutuan_2025.pdf", page=536,
                 cols=TAIL15 + ["development_level", "opex_deficit", "total"]),
    "2026": dict(year="2024", file="Anggaran_Perbelanjaan_Persekutuan_2026.pdf", page=578,
                 cols=TAIL15 + ["biodiversity_eft", "development_level", "opex_deficit", "total"]),
}
TOKEN = re.compile(r"^(?:\d{1,3}(?:,\d{3})*|tb|-)$")
FIELDS = ["book", "year", "geo_code", "state", "row_type", "grant_id", "grant_name_bm", "vote_code", "amount_rm",
          "printed", "source_file", "pdf_page", "printed_page", "statement"]


def text(path, page):
    args = ["pdftotext", "-layout"] + (["-f", str(page), "-l", str(page)] if page else []) + [path, "-"]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def main():
    for book, b in BOOKS.items():
        path = os.path.join(RAW, b["file"])
        t = text(path, b["page"])
        lines = t.splitlines()
        title = next(l.strip() for l in lines if "KEPADA KERAJAAN NEGERI TAHUN" in l)
        title = re.sub(r"\s+LAMPIRAN E$", "", re.sub(r"\s+", " ", title))
        assert title.endswith(f"TAHUN {b['year']}"), (book, title)
        m = re.search(r"PERSEKUTUAN (\d{4}) \| (\d+)", t)
        printed_page = m.group(2) if m and m.group(1) == book else ""
        # the printed vote-code row must match the declared columns (every column but JUMLAH carries a code)
        codes = next(re.findall(r"\b[TB]\.?1[12]\b", l) for l in lines if len(re.findall(r"\b[TB]\.?1[12]\b", l)) > 8)
        codes = [c if "." in c else c[0] + "." + c[1:] for c in codes]
        want = [G[c][1] for c in b["cols"] if c != "total"]
        assert codes == want, (book, codes, want)
        rows, prev = {}, ""
        for l in lines:
            s = l.strip()
            name = next((n for n in [x for x, _ in STATES] + list(LABEL) + ["Jumlah"]
                         if s.startswith(n + " ") or s == n), None)
            toks = [x for x in s[len(name):].split()] if name else s.split()
            nums = [x for x in toks if TOKEN.match(x)]
            if name is None and prev == "Negeri" and len(nums) == len(b["cols"]):
                name = "Negeri Sembilan"  # the 2026 book wraps the label around the row: 'Negeri' / numbers / 'Sembilan'
            prev = s
            if not name or len(nums) != len(b["cols"]) or len(nums) != len(toks):
                continue
            rows[LABEL.get(name, name)] = nums
        missing = [n for n, _ in STATES if n not in rows] + ([] if "Jumlah" in rows else ["Jumlah"])
        assert not missing, (book, missing)
        out = []
        for name, geo in STATES + [("Jumlah", "MY")]:
            for col, raw in zip(b["cols"], rows[name]):
                amt = "" if raw == "tb" else "0" if raw == "-" else raw.replace(",", "")
                out.append(dict(book=book, year=b["year"], geo_code=geo, state=name,
                                row_type="total" if name == "Jumlah" else "state",
                                grant_id=col, grant_name_bm=G[col][0], vote_code=G[col][1], amount_rm=amt,
                                printed=raw, source_file=b["file"], pdf_page=str(b["page"] or 1),
                                printed_page=printed_page, statement=title))
        d = os.path.join(SRC, "data", book)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"fact_anggaran_lampiran_e_{book}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(out)
        print(f"book {book} (FY{b['year']}): {len(out)} cells, {len(b['cols'])} columns, printed page {printed_page}")


if __name__ == "__main__":
    main()
