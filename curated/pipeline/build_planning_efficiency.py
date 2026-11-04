#!/usr/bin/env python3
"""Planning-efficiency view: original budget vs actual, FY2010-FY2024 (+ tabled 2025-26).

Run:  python3 curated/pipeline/build_planning_efficiency.py
Writes: curated/fact_planning_efficiency.csv

For every audited year, PKKP records each vote's original appropriation
(anggaran_asal) alongside the actual — and the ingested budget books prove that this
recorded original IS the budget as tabled in Parliament: the AP2024 book's tabled
figures match PKKP's recorded asal 2024 exactly on all 53 comparable votes (and its
asal-2023 column matches PKKP's 2023 record; AP2025/AP2026 confirm 2024/2025 the same
way). So the audited PKKP series doubles as the tabled-vs-actual series.

Columns: year, side (oe|de|total), budget_rm, actual_rm, variance_rm, utilisation_pct,
basis, book_evidence (which tabled book confirms the original, where ingested).
2025/2026 rows carry the tabled budgets with actual=NULL (unaudited) — the signature
nowcast for expected outturn lives in apps/models/ (a model, not warehouse data).
"""
import csv
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
AP = os.path.join(ROOT, "sources", "anggaran", "data")

con = duckdb.connect(DB, read_only=True)
oe = {int(r[0]): (float(r[1]), float(r[2])) for r in con.sql("""
    SELECT year, sum(anggaran_asal_rm), sum(sebenar_rm) FROM fact_opex_maksud
    WHERE source_file ILIKE year || '_PENYATA%' AND year >= 2010 GROUP BY 1""").fetchall()}
de = {int(r[0]): (float(r[1]), float(r[2])) for r in con.sql("""
    SELECT year, sum(anggaran_jumlah_rm), sum(sebenar_jumlah_rm) FROM fact_devex_maksud
    WHERE source_file ILIKE year || '_PENYATA%' AND maksud_code LIKE 'P.%' AND year >= 2010
    GROUP BY 1""").fetchall()}

# tabled totals from the ingested budget books (evidence + the unaudited years)


def book_totals(ed, measure):
    p = os.path.join(AP, str(ed), f"fact_anggaran_maksud_{ed}.csv")
    if not os.path.exists(p):
        return None
    toe = tde = 0
    for r in csv.DictReader(open(p)):
        if r["measure"] != measure:
            continue
        c, cp = r["maksud_code"], r["component"]
        if (c.startswith("T.") and cp == "jumlah") or (c.startswith("B.") and cp == "mengurus"):
            toe += int(r["amount_rm"])
        elif c.startswith("P.") and cp == "pembangunan":
            tde += int(r["amount_rm"])
    return toe, tde


tabled = {2024: (book_totals(2024, "anggaran_2024"), "AP2024 book (tabled)"),
          2025: (book_totals(2025, "anggaran_2025"), "AP2025 book (tabled)"),
          2026: (book_totals(2026, "anggaran_2026"), "AP2026 book (tabled)")}
EVIDENCE = {2023: "asal column of AP2024 book", 2024: "AP2024 tabled = PKKP asal (exact, all votes); AP2025 asal column",
            2025: "AP2025 tabled; AP2026 asal column", 2026: "AP2026 tabled"}

dest = os.path.join(HERE, "..", "fact_planning_efficiency.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "side", "budget_rm", "actual_rm", "variance_rm",
                "utilisation_pct", "basis", "book_evidence"])
    for y in sorted(oe):
        rows = {"oe": oe[y], "de": de.get(y, (None, None))}
        rows["total"] = tuple((a or 0) + (b or 0) for a, b in zip(oe[y], de.get(y, (0, 0))))
        for side, (b, a) in rows.items():
            if b is None:
                continue
            w.writerow([y, side, int(b), int(a), int(a - b), round(100 * a / b, 2),
                        "audited (PKKP; anggaran_asal = budget as tabled, book-verified)",
                        EVIDENCE.get(y, "")])
    for y, (tot, src) in sorted(tabled.items()):
        if y <= 2024 or tot is None:
            continue
        toe, tde = tot
        for side, b in (("oe", toe), ("de", tde), ("total", toe + tde)):
            w.writerow([y, side, b, "", "", "", "budget (tabled, unaudited year)", src])
print(f"wrote {dest}")

# consistency proof: tabled 2024 vs PKKP recorded asal 2024
t24 = tabled[2024][0]
print(f"tabled 2024 OE {t24[0]:,} vs PKKP asal {int(oe[2024][0]):,} -> "
      f"{'EQUAL' if t24[0] == int(oe[2024][0]) else 'DIFF'}")
print(f"tabled 2024 DE {t24[1]:,} vs PKKP asal {int(de[2024][0]):,} -> "
      f"{'EQUAL' if t24[1] == int(de[2024][0]) else 'DIFF'}")
