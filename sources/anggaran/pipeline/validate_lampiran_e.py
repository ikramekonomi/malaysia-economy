#!/usr/bin/env python3
"""Validate Lampiran E (actual federal grants to the states, Budget books 2021-2026, FY2019-2024).

  L1 each state's grants add up to its printed JUMLAH (the road-maintenance sub-columns, FY2019-2020, are
     counted once, through their printed JUMLAH)
  L2 each grant's 13 states add up to the printed Jumlah row
  L3 the Jumlah row's grants add up to its printed JUMLAH
  L4 the road-maintenance sub-columns add up to their printed JUMLAH (FY2019-2020)
  L5 each grant's national total against the federal audited accounts (PKKP) of the same year, own volume:
     the PKKP line(s) are the grants already loaded as flows (core/fact_money_flow.csv, matched by code and
     name each year), plus B.11 'Bayaran Perkhidmatan' for state_services. Whole ringgit against sen: equal
     within RM2. A difference is WARN with its amount, kept as printed (golden rule 2), never corrected.
     Grants PKKP does not print as a line of their own (libraries, museums, tourism, the two B.12 grants,
     which are paid out of the State Reserve Fund trust account) are INFO.
  L6 the grants PKKP pays to a named state (special annual grants to Sabah, Sarawak, Selangor and Kedah; the
     petroleum-duty compensation to Sabah and Sarawak together) against Lampiran E's figure for that state
  L7 libraries + museums + Concurrent List against PKKP's Concurrent List line (the PKKP line appears to
     include them; equal in FY2024): WARN where it is not, with the difference

Writes sources/anggaran/data/_validation_lampiran_e.csv. Exit 1 on a FAIL (L1-L4 are the table's own sums).
"""
import csv
import glob
import os
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SRC))
TOL = Decimal("2")
PARTS = ["road_maintenance_part1", "road_maintenance_part2", "road_maintenance_part3"]
# grant_id -> purpose_en prefixes of the flow rules (meta/flow_rule.csv) that carry it in PKKP
FLOWS = {
    "capitation": ["capitation grant to the state governments"],
    "road_maintenance": ["state road maintenance grant, roads at the minimum standard",
                         "state road maintenance grant, substandard roads", "state road maintenance, one-way roads"],
    "special_annual": ["special annual grant to Sabah", "special annual grant to Sarawak", "annual payment to Selangor",
                       "annual payment to Kedah"],
    "revenue_growth": ["revenue growth grant"],
    "gtbkk": ["annual grant to local authorities"],
    "concurrent_list": ["grants under the Concurrent List"],
    "petroleum_duty_compensation": ["compensation to Sabah and Sarawak for the abolition"],
    "street_lighting": ["street-lighting bill assistance"],
}
NAMED = {("special_annual", "MY-12"): ["special annual grant to Sabah"],
         ("special_annual", "MY-13"): ["special annual grant to Sarawak"],
         ("special_annual", "MY-10"): ["annual payment to Selangor"],
         ("special_annual", "MY-02"): ["annual payment to Kedah"]}


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def D(x):
    return Decimal(x) if x not in ("", None) else Decimal(0)


def main():
    out = []

    def add(check, scope, status, detail):
        out.append(dict(check=check, scope=scope, status=status, detail=detail))

    flows = rows(os.path.join(REPO, "core", "fact_money_flow.csv"))
    for p in sorted(glob.glob(os.path.join(SRC, "data", "*", "fact_anggaran_lampiran_e_*.csv"))):
        cells = rows(p)
        book, year = cells[0]["book"], cells[0]["year"]
        scope = f"book {book} (FY{year})"
        v = {(c["geo_code"], c["grant_id"]): D(c["amount_rm"]) for c in cells}
        grants = list(dict.fromkeys(c["grant_id"] for c in cells))
        leaves = [g for g in grants if g not in PARTS + ["total"]]
        geos = list(dict.fromkeys(c["geo_code"] for c in cells if c["row_type"] == "state"))
        bad = [f"{g}: {sum(v[(g, x)] for x in leaves)} vs {v[(g, 'total')]}" for g in geos + ["MY"]
               if sum(v[(g, x)] for x in leaves) != v[(g, "total")]]
        add("L1 each state's grants add up to its JUMLAH", scope, "PASS" if not bad else "FAIL",
            f"{len(geos) + 1} rows" + (f"; {bad}" if bad else ""))
        bad = [f"{x}: {sum(v[(g, x)] for g in geos)} vs {v[('MY', x)]}" for x in grants
               if sum(v[(g, x)] for g in geos) != v[("MY", x)]]
        add("L2 each grant's 13 states add up to the Jumlah row", scope, "PASS" if not bad else "FAIL",
            f"{len(grants)} columns" + (f"; {bad}" if bad else ""))
        tot = sum(v[("MY", x)] for x in leaves)
        add("L3 the Jumlah row adds up to its JUMLAH", scope, "PASS" if tot == v[("MY", "total")] else "FAIL",
            f"{tot} vs {v[('MY', 'total')]}")
        if PARTS[0] in grants:
            bad = [g for g in geos + ["MY"] if sum(v[(g, x)] for x in PARTS) != v[(g, "road_maintenance")]]
            add("L4 road-maintenance sub-columns add up to their JUMLAH", scope, "PASS" if not bad else "FAIL",
                "ok" if not bad else str(bad))
        fy = [f for f in flows if f["period_code"] == year and f["basis"] == "audited"]

        def flow_sum(prefixes, geo=None):
            hit = [f for f in fy if any(f["purpose"].split(": ", 1)[-1].startswith(pp) for pp in prefixes)]
            return sum(D(f["amount"]) for f in hit), len(hit)
        for g in leaves:
            if g == "concurrent_list":
                pk, n = flow_sum(FLOWS[g])
                add(f"L5 {g} against PKKP", scope, "INFO",
                    f"Lampiran E {v[('MY', g)]} vs PKKP {pk}: PKKP's line also carries the libraries and museums "
                    "grants, so it is tested with them in L7")
                continue
            if g in FLOWS:
                pk, n = flow_sum(FLOWS[g])
                if not n:
                    add(f"L5 {g} against PKKP", scope, "INFO", "no PKKP flow held for this grant this year")
                    continue
                diff = v[("MY", g)] - pk
                add(f"L5 {g} against PKKP", scope, "PASS" if abs(diff) <= TOL else "WARN",
                    f"Lampiran E {v[('MY', g)]} vs PKKP {pk} ({n} line(s))" + ("" if abs(diff) <= TOL else f"; difference {diff}"))
            elif g == "state_services":
                pk = sum(D(r["sebenar_rm"]) for r in rows(os.path.join(REPO, "sources", "pkkp", "data", year,
                                                                      "fact_opex_detail.csv"))
                         if r["maksud_code"] == "B.11" and r["row_type"] == "object_aktiviti"
                         and r["aktiviti_name_bm"].strip() == "Bayaran Perkhidmatan")
                diff = v[("MY", g)] - pk
                add(f"L5 {g} against PKKP", scope, "PASS" if pk and abs(diff) <= TOL else "WARN",
                    f"Lampiran E {v[('MY', g)]} vs PKKP B.11 'Bayaran Perkhidmatan' {pk}"
                    + ("" if pk and abs(diff) <= TOL else f"; difference {diff}"))
            else:
                add(f"L5 {g} against PKKP", scope, "INFO",
                    f"Lampiran E {v[('MY', g)]}; not a line of its own in PKKP"
                    + (" (B.12: paid out of the State Reserve Fund, Kumpulan Wang Rizab Negeri)" if g in
                       ("development_level", "opex_deficit") else ""))
        for (g, geo), pre in NAMED.items():
            if g in leaves:
                pk, n = flow_sum(pre)
                if n:
                    diff = v[(geo, g)] - pk
                    add(f"L6 {g} {geo} against PKKP's grant by name", scope, "PASS" if abs(diff) <= TOL else "WARN",
                        f"Lampiran E {v[(geo, g)]} vs PKKP {pk}" + ("" if abs(diff) <= TOL else f"; difference {diff}"))
        if "concurrent_list" in FLOWS and all(x in leaves for x in ("libraries", "museums", "concurrent_list")):
            pk, n = flow_sum(FLOWS["concurrent_list"])
            le = v[("MY", "concurrent_list")] + v[("MY", "libraries")] + v[("MY", "museums")]
            if n:
                diff = le - pk
                add("L7 Concurrent List + libraries + museums against PKKP's Concurrent List line", scope,
                    "PASS" if abs(diff) <= TOL else "WARN",
                    f"Lampiran E {le} vs PKKP {pk}" + ("" if abs(diff) <= TOL else f"; difference {diff}"))
    path = os.path.join(SRC, "data", "_validation_lampiran_e.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    st = defaultdict(int)
    for r in out:
        st[r["status"]] += 1
    print("lampiran_e: " + ", ".join(f"{n} {k}" for k, n in sorted(st.items())))
    sys.exit(1 if st["FAIL"] else 0)


if __name__ == "__main__":
    main()
