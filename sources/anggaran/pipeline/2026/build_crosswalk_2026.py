#!/usr/bin/env python3
"""Build the documented maksud-code crosswalk AP2026 -> PKKP dim_maksud.

The Anggaran book prints vote codes as "T.1" / "B.62" / "P.62"; PKKP's dim_maksud
uses zero-padded "T.01" / "B.62" / "P.62". The mapping is the identity on (jenis letter,
vote number) — but it is never assumed: this script joins every AP2026 maksud to
PKKP dim_maksud (latest year available per code, 2022-2024) and records the name-level
evidence, so any renumbering between sources would surface as a name mismatch.

Output: sources/anggaran/data/2025/_crosswalk_pkkp_2026.csv
Codes with no PKKP counterpart (e.g. P.70 Simpanan Luar Jangka, a budget-only
contingency reserve; votes created after FY2024) are kept with status=no_pkkp_match —
they must not be joined to actuals.
"""
import csv
import os
import re

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..", "..", "..")
DATA = os.path.join(HERE, "..", "..", "data", "2026")
DB = os.path.join(REPO, "sources", "pkkp", "pkkp.duckdb")


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


ap = {}
for r in csv.DictReader(open(os.path.join(DATA, "fact_anggaran_maksud_2026.csv"))):
    ap[r["maksud_code"]] = (r["maksud_code_printed"], r["jenis"], r["maksud_name_bm"])

con = duckdb.connect(DB, read_only=True)
pk = {}
for code, name, yr in con.sql(
        "select maksud_code, name_bm, max(year) from dim_maksud "
        "where year between 2022 and 2024 group by maksud_code, name_bm "
        "qualify row_number() over (partition by maksud_code order by max(year) desc) = 1"
).fetchall():
    pk[code] = (name, yr)

dest = os.path.join(DATA, "_crosswalk_pkkp_2026.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ap_maksud_code_printed", "maksud_code", "jenis", "ap_name_bm",
                "pkkp_name_bm", "pkkp_dim_year", "status", "note"])
    n_match = n_name = n_none = 0
    for code in sorted(ap):
        printed, jenis, name = ap[code]
        if code in pk:
            pname, pyr = pk[code]
            exact = norm(name) == norm(pname)
            # word-overlap evidence for renamed/reworded votes
            aw, pw = set(norm(name).split()), set(norm(pname).split())
            overlap = len(aw & pw) / max(1, min(len(aw), len(pw)))
            if exact or overlap >= 0.5:
                status, note = "matched", "" if exact else f"name reworded (word overlap {overlap:.0%})"
                n_match += 1
            else:
                status, note = "matched_code_name_differs", f"word overlap {overlap:.0%} — review before joining"
                n_name += 1
            w.writerow([printed, code, jenis, name, pname, pyr, status, note])
        else:
            reason = ("budget-only contingency reserve, no actuals in PKKP"
                      if code == "P.70" else "no dim_maksud entry 2022-2024")
            w.writerow([printed, code, jenis, name, "", "", "no_pkkp_match", reason])
            n_none += 1
print(f"wrote {dest}: {n_match} matched, {n_name} code-matched-name-differs, {n_none} unmatched")
