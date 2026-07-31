#!/usr/bin/env python3
"""Validate fact_agensi_sijil_{2023,2024}.csv against the reports' own printed totals.

Printed anchors (per volume's Pengesahan chapter, cited by pdf_page):
  CMD.4.2025 (FY2023) pdf p.22-24: 142 sijil = 129 Badan Berkanun + 10 Kumpulan Wang
    + 3 Lain (prose); Jadual 1.8: Tanpa Teguran 133, Pendapat Diubahsuai 9
    (Berteguran 8 + Bertentangan 1); TT split: plain 65, EOM 8, OM 60.
  CMD.1.2026 (FY2024) pdf p.21-22: 143 sijil = 131 Badan Berkanun + ... (prose);
    Jadual 1.8: Tanpa Teguran 128, Diubahsuai 15; TT split incl. plain 47, OM 63.

The FY2023 prose split (129/10/3) disagrees with the register itself, which prints
130 numbered Badan Berkanun rows and 9 Kumpulan Wang rows — a source-side
inconsistency, catalogued in data/_source_anomalies_agensi.csv, never corrected.

Writes data/_validation_agensi.csv.
"""
import csv
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# printed expectations: (year, check, expected, evidence)
PRINTED = [
    (2023, "total_sijil", 142, "CMD.4.2025 pdf p.23 'kesemua 142 Penyata Kewangan'"),
    (2023, "opinion:Tanpa Teguran", 133, "CMD.4.2025 pdf p.23 Jadual 1.8"),
    (2023, "opinion:Berteguran", 8, "CMD.4.2025 pdf p.24 Jadual 1.8"),
    (2023, "opinion:Bertentangan", 1, "CMD.4.2025 pdf p.24 Jadual 1.8 (Diubahsuai 9 = 8+1)"),
    (2023, "tt_qualifier:", 65, "CMD.4.2025 pdf p.23 'Tanpa Teguran 65'"),
    # the printed Jadual buckets combined "Penegasan Perkara dan Hal-hal Lain"
    # qualifiers under EOM, so EOM(printed) = PP + PP&HhL in the register
    (2023, "tt_qualifier_eom_combined", 8, "CMD.4.2025 pdf p.23 'Penegasan Perkara (EOM) 8'"),
    (2023, "tt_qualifier:Hal-hal Lain", 60, "CMD.4.2025 pdf p.24 'Hal-hal Lain (OM) 60'"),
    (2024, "total_sijil", 143, "CMD.1.2026 pdf p.22 '143 Penyata Kewangan ... Sijil'"),
    (2024, "register:badan_berkanun", 131, "CMD.1.2026 pdf p.21 '131 Badan Berkanun'"),
    (2024, "opinion:Tanpa Teguran", 128, "CMD.1.2026 pdf p.22 'Tanpa Teguran ... 128 sijil'"),
    (2024, "opinion:Berteguran", 15, "CMD.1.2026 pdf p.22 '15 penyata ... Diubahsuai'"),
    (2024, "tt_qualifier:", 47, "CMD.1.2026 pdf p.22 Jadual 1.8 'Tanpa Teguran 47'"),
    (2024, "tt_qualifier:Hal-hal Lain", 63, "CMD.1.2026 pdf p.22 Jadual 1.8 'OM 63'"),
]

out = []
for year in (2023, 2024):
    rows = list(csv.DictReader(open(os.path.join(DATA, f"fact_agensi_sijil_{year}.csv"))))
    got = {"total_sijil": len(rows)}
    for k, v in Counter(r["register"] for r in rows).items():
        got[f"register:{k}"] = v
    for k, v in Counter(r["opinion"] for r in rows).items():
        got[f"opinion:{k}"] = v
    for k, v in Counter(r["opinion_qualifier"] for r in rows
                        if r["opinion"] == "Tanpa Teguran").items():
        got[f"tt_qualifier:{k}"] = v
    got["tt_qualifier_eom_combined"] = (got.get("tt_qualifier:Penegasan Perkara", 0) +
                                        got.get("tt_qualifier:Penegasan Perkara dan Hal-hal Lain", 0))
    # structural checks
    bils = sorted(int(r["bil"]) for r in rows)
    out.append([year, "bil_continuous_1..n", "yes",
                "yes" if bils == list(range(1, len(rows) + 1)) else "NO",
                "PASS" if bils == list(range(1, len(rows) + 1)) else "FAIL", "register numbering"])
    dup = [k for k, v in Counter(r["agency_name_bm"] for r in rows).items() if v > 1]
    out.append([year, "no_duplicate_agency_names", "yes", "yes" if not dup else str(dup)[:60],
                "PASS" if not dup else "FAIL", "register uniqueness"])
    for y, check, exp, ev in PRINTED:
        if y != year:
            continue
        g = got.get(check, 0)
        out.append([year, check, exp, g, "PASS" if g == exp else "FAIL", ev])

dest = os.path.join(DATA, "_validation_agensi.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "check", "expected_printed", "got", "status", "evidence"])
    w.writerows(out)
fails = [r for r in out if r[4] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails:
    print("FAIL:", r)

# source anomaly register (kept as printed, never corrected)
anom = os.path.join(DATA, "_source_anomalies_agensi.csv")
with open(anom, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["source_file", "pdf_page", "anomaly", "proof"])
    w.writerow(["CMD.4.2025.pdf", "22",
                "Prose says the 142 FY2023 sijil comprise 129 Badan Berkanun + 10 Kumpulan "
                "Wang + 3 Agensi Lain, but the Lampiran 2 register prints 130 numbered Badan "
                "Berkanun rows (bil 1-130) and 9 Kumpulan Wang rows (bil 131-139)",
                "register rows extracted verbatim (fact_agensi_sijil_2023.csv) sum to "
                "130+9+3=142; prose split 129+10+3=142 disagrees at section level only"])
print(f"anomaly register -> {anom}")
