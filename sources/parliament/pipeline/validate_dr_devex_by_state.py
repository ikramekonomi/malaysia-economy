#!/usr/bin/env python3
"""Validate the Dewan Rakyat answers on development allocation and spending by state.

  D1 % BELANJA = BELANJA / PERUNTUKAN (within 0.01 point plus the amounts' rounding). The RP3 misprint (7 states
     print the allocation in the BELANJA and % columns) is a registered source anomaly: WARN, kept as printed
  D2 coverage: 14 rows (13 states + Wilayah Persekutuan) x 4 rolling plans x 4 measures
  D3 (INFO) the 14 rows' BELANJA against PKKP's audited gross development spending of the same year (core,
     federal_gov.expenditure.devex, basis audited): the answer has no multi-state row and its figures come from
     the MyProjek system, so it is not expected to add up to the accounts; RP4 is as at 4 Nov 2024 (part year)
Writes sources/parliament/data/_validation_dr_devex_by_state.csv. Exit 1 on a FAIL. Nothing is corrected.
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SRC))


def main():
    rows = list(csv.DictReader(open(os.path.join(SRC, "data", "fact_dr_devex_by_state.csv"), encoding="utf-8")))
    v = {(r["rolling_plan"], r["negeri_bm"], r["measure"]): (D(r["value"]), r["value_printed"]) for r in rows}
    anomalies = {(r["location"]) for r in csv.DictReader(open(os.path.join(SRC, "data", "_source_anomalies.csv"), encoding="utf-8"))}
    out = []

    def add(c, s, st, d):
        out.append(dict(check=c, scope=s, status=st, detail=d))
    rps = sorted({r["rolling_plan"] for r in rows})
    names = sorted({r["negeri_bm"] for r in rows})
    for rp in rps:
        bad, warn = [], []
        for n in names:
            p, b, pc = v[(rp, n, "peruntukan")][0], v[(rp, n, "belanja")][0], v[(rp, n, "pct_belanja")]
            calc = b / p * 100
            if abs(calc - pc[0]) > D("0.01") + D("0.5") / p:
                (warn if f"{rp} {n}" in anomalies else bad).append(f"{n}: printed {pc[1]}, from amounts {calc:.2f}%")
        add("D1 % BELANJA = BELANJA / PERUNTUKAN", rp, "FAIL" if bad else "WARN" if warn else "PASS",
            "; ".join(bad + [w + " (registered source anomaly)" for w in warn]) or f"{len(names)} rows")
    n_ok = len(rows) == 14 * 4 * 4 and len(names) == 14 and len(rps) == 4
    add("D2 coverage 14 rows x 4 rolling plans x 4 measures", "JBL12122024 Q243", "PASS" if n_ok else "FAIL", f"{len(rows)} cells")
    pk = defaultdict(D)
    for r in csv.DictReader(open(os.path.join(REPO, "core", "fact_observation.csv"), encoding="utf-8")):
        if r["indicator_code"] == "federal_gov.expenditure.devex" and r["basis"] == "audited" and \
                r["edition_id"].startswith("pkkp:") and r["geo_code"] == "MY" and r["breakdown_key"] == "_total":
            pk[r["period_code"]] += D(r["value"])
    year = {r["rolling_plan"]: r["year"] for r in rows}
    for rp in rps:
        s = sum(v[(rp, n, "belanja")][0] for n in names)
        t = pk.get(year[rp], D(0)) / D(1000000)
        add("D3 the 14 rows' BELANJA against PKKP gross development spending (INFO)", f"{rp} ({year[rp]})", "INFO",
            f"{s:.2f} vs PKKP {t:.2f} RM juta ({s / t * 100:.1f}%)" if t else f"{s:.2f}; PKKP not held")
    with open(os.path.join(SRC, "data", "_validation_dr_devex_by_state.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("dr_devex_by_state: " + ", ".join(f"{r['check'][:2]} {r['scope'][:3]} {r['status']}" for r in out))
    sys.exit(1 if any(r["status"] == "FAIL" for r in out) else 0)


if __name__ == "__main__":
    main()
