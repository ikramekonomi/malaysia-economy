#!/usr/bin/env python3
"""Validate KSP RMKe-11 Jadual F-3 (federal development allocation and spending by state, 2016-2017).

  F1 the 15 lines add up to the printed Jumlah, both amounts (printed rounding: within RM8 juta, 15 x 0.5)
  F2 each '% Jumlah' = Peruntukan / Jumlah, and each '% Peruntukan' = Perbelanjaan / Peruntukan (within 0.05 point
     plus the rounding of the amounts)
  F3 the Jumlah of Perbelanjaan against PKKP's audited gross development spending, FY2016 + FY2017, each from its own
     volume (core/fact_observation/, federal_gov.expenditure.devex, basis audited): within RM1 juta
  F4 (INFO) the share named to one state or the Federal Territories: the 13 states + 'Wilayah Persekutuan' over the
     Jumlah ('Pelbagai Negeri' is not placed)
Writes sources/rmk/data/_validation_ksp_rmk11_f3.csv. Exit 1 on a FAIL. Nothing is corrected.
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
    rows = list(csv.DictReader(open(os.path.join(SRC, "data", "ksp_rmk11", "fact_ksp_rmk11_f3.csv"), encoding="utf-8")))
    v = {(r["negeri_bm"], r["measure"]): D(r["value"]) for r in rows}
    names = [n for n in dict.fromkeys(r["negeri_bm"] for r in rows) if n != "Jumlah"]
    out = []

    def add(c, s, st, d):
        out.append(dict(check=c, scope=s, status=st, detail=d))
    for m in ("peruntukan_dipinda_2016_2017", "perbelanjaan_2016_2017"):
        s = sum(v[(n, m)] for n in names)
        add("F1 lines add up to Jumlah", m, "PASS" if abs(s - v[("Jumlah", m)]) <= 8 else "FAIL",
            f"{s} vs {v[('Jumlah', m)]} ({len(names)} lines)")
    bad = []
    for n in names + ["Jumlah"]:
        p, b, t = v[(n, "peruntukan_dipinda_2016_2017")], v[(n, "perbelanjaan_2016_2017")], v[("Jumlah", "peruntukan_dipinda_2016_2017")]
        for name, calc, pr, tol in (("% Jumlah", p / t * 100, v[(n, "peruntukan_pct_jumlah")], D("0.05") + D("50") / t),
                                    ("% Peruntukan", b / p * 100, v[(n, "perbelanjaan_pct_peruntukan")], D("0.05") + D("100") / p)):
            if abs(calc - pr) > tol:
                bad.append(f"{n} {name}: printed {pr}, from amounts {calc:.2f}")
    add("F2 printed percentages against the amounts", "Jadual F-3", "PASS" if not bad else "WARN", "; ".join(bad) or "32 percentages")
    pk = defaultdict(D)
    sys.path.insert(0, os.path.join(REPO, "core", "pipeline"))
    from warehouse import read_observations
    for r in read_observations():
        if r["indicator_code"] == "federal_gov.expenditure.devex" and r["basis"] == "audited" and \
                r["edition_id"].startswith("pkkp:") and r["period_code"] in ("2016", "2017") and r["geo_code"] == "MY":
            pk[r["period_code"]] += D(r["value"])
    tot = (pk["2016"] + pk["2017"]) / D(1000000)
    d = v[("Jumlah", "perbelanjaan_2016_2017")] - tot
    add("F3 Jumlah Perbelanjaan against PKKP gross development spending FY2016 + FY2017", "PKKP",
        "PASS" if len(pk) == 2 and abs(d) <= 1 else "WARN", f"F-3 {v[('Jumlah', 'perbelanjaan_2016_2017')]} vs PKKP "
        f"{tot:.2f} (RM juta); difference {d:.2f}")
    placed = sum(v[(n, "perbelanjaan_2016_2017")] for n in names if n != "Pelbagai Negeri")
    add("F4 share named to one state or the Federal Territories (INFO)", "Jadual F-3", "INFO",
        f"{placed} of {v[('Jumlah', 'perbelanjaan_2016_2017')]} RM juta = "
        f"{placed / v[('Jumlah', 'perbelanjaan_2016_2017')] * 100:.1f}%; Pelbagai Negeri {v[('Pelbagai Negeri', 'perbelanjaan_2016_2017')]}")
    with open(os.path.join(SRC, "data", "_validation_ksp_rmk11_f3.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("ksp_rmk11_f3: " + ", ".join(f"{r['check'][:2]} {r['status']}" for r in out))
    sys.exit(1 if any(r["status"] == "FAIL" for r in out) else 0)


if __name__ == "__main__":
    main()
