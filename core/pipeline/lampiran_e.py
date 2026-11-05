"""Lampiran E (sources/anggaran: MOF's actual grants to each state, FY2019-2024), as decision D30 allows it to be
used: a grant and year only where its national total equals PKKP's audited line within RM2
(sources/anggaran/data/_validation_lampiran_e.csv: L5 PASS, or L7 PASS for the Concurrent List, libraries and
museums, which PKKP prints as one line)."""
import csv
import glob
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "sources", "anggaran", "data")
L7_GROUP = ("concurrent_list", "libraries", "museums")


def _rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def reconciled():
    """year -> {grant_id: 'L5 PASS' | 'L7 PASS'} for the grants D30 lets us use."""
    out = {}
    for r in _rows(os.path.join(DATA, "_validation_lampiran_e.csv")):
        m = re.search(r"\(FY(\d{4})\)", r["scope"])
        if not m or r["status"] != "PASS":
            continue
        y = m.group(1)
        g = re.match(r"L5 (\S+) against PKKP", r["check"])
        if g:
            out.setdefault(y, {})[g.group(1)] = "L5 PASS"
        if r["check"].startswith("L7 "):
            for x in L7_GROUP:
                out.setdefault(y, {})[x] = "L7 PASS"
    return out


def cells():
    """(year, geo_code, grant_id) -> cell row (amount_rm blank where printed 'tb')."""
    out = {}
    for p in sorted(glob.glob(os.path.join(DATA, "*", "fact_anggaran_lampiran_e_*.csv"))):
        for i, r in enumerate(_rows(p), start=2):
            r["l1_ref"] = os.path.relpath(p, REPO) + f"#row{i}"
            out[(r["year"], r["geo_code"], r["grant_id"])] = r
    return out


def validation_status(year, grant_id):
    """the L5/L7 row(s) for this grant and year, for a reason when it is not used."""
    keys = [f"L5 {grant_id} against PKKP"] + (["L7 "] if grant_id in L7_GROUP else [])
    return [r for r in _rows(os.path.join(DATA, "_validation_lampiran_e.csv"))
            if f"(FY{year})" in r["scope"] and any(r["check"].startswith(k) for k in keys)]
