#!/usr/bin/env python3
"""gap_need_vs_money, state level (docs/DATA_MODEL.md §10, Phase 1): does money follow need?

  python3 core/pipeline/build_gap_need_vs_money.py  -> core/gap_need_vs_money.csv, core/_validation_gap_need.csv

Method (declared before results were seen, 2026-11-04):
* Grain: every state and Federal Territory (all 16, golden rule 11) x every HIES year in 2014-2024
  (2014, 2016, 2019, 2022, 2024). Need and money are taken from the same year; nothing is carried
  forward from another year.
* Need: absolute poverty rate, median household income, Gini, unemployment rate (DOSM), population.
* Money, scope `state_government`: the state government's own audited spending, as printed
  (`state_gov.expenditure.total`) or, where the volume prints no total, opex + devex (basis derived,
  rule DV5-sum, flagged); and its non-revenue receipts (mostly federal grants, as the state records
  them). Per capita through derive DV1. Placed share 1.0 by construction: a state's own accounts
  are about that state.
* Money, scope `federal`: federal spending placed in the state. Phase 1 can place only what states
  record receiving (non-revenue receipts), so federal_placed_share = sum of the 13 states' receipts /
  federal total spending (PKKP audited: opex before transfers + gross devex). Below 60% the federal
  column is NOT published for any state (DATA_MODEL §10 guard), and the row says why.
* A state-year with an open FAIL on a headline identity (qa/known_fails.csv) is published with
  under_check = the check names, never silently.
* No ranking. compare_geos bands states (meta/derivation.csv BAND1); this view lists them by code.
"""
import csv
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, REPO, Warehouse, fmt  # noqa: E402

YEARS = ["2014", "2016", "2019", "2022", "2024"]
PLACED_MIN = Decimal("0.60")
NEED = {"poverty_absolute_rate": "poverty.absolute.rate", "income_median_rm": "hh_income.gross.median",
        "gini": "hh_income.gini", "unemployment_rate": "lfs.unemployment_rate"}
FIELDS = ["geo_code", "state", "year", "population"] + list(NEED) + [
    "state_gov_expenditure_rm", "state_gov_expenditure_basis", "state_gov_expenditure_per_capita_rm",
    "state_gov_receipts_rm", "state_gov_receipts_per_capita_rm", "state_gov_placed_share",
    "federal_total_expenditure_rm", "federal_placed_share", "federal_publishable", "federal_note",
    "under_check", "coverage_note", "verification_tier", "caveats", "source_obs_ids", "release_id"]


def federal_totals():
    out = {}
    with open(os.path.join(REPO, "curated", "fact_fiscal_headline.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["opex_net_rm"] and r["devex_gross_rm"]:
                out[r["year"]] = (Decimal(r["opex_net_rm"]) + Decimal(r["devex_gross_rm"]),
                                  f"{r['opex_source_file']} p{r['opex_pdf_page']} + devex gross ({r['devex_gross_basis']})")
    return out


def main():
    w = Warehouse()
    fed = federal_totals()
    states = sorted(c for c, g in w.geo.items() if g["geo_level"] == "state")
    out, checks = [], []
    receipts_sum = {y: Decimal(0) for y in YEARS}
    receipts_n = {y: 0 for y in YEARS}
    for y in YEARS:
        for g in states:
            r = w.get("state_gov.revenue.nonrevenue_receipts", g, y, basis="audited")
            if r:
                receipts_sum[y] += Decimal(r["value"])
                receipts_n[y] += 1
    for y in YEARS:
        fed_total = fed.get(y, (None, None))[0]
        placed = (receipts_sum[y] / fed_total) if fed_total else None
        for g in states:
            row = {k: "" for k in FIELDS}
            ids, cv, notes = [], set(), []
            row.update(geo_code=g, state=w.geo[g]["name_bm"], year=y, release_id=w.release_id,
                       verification_tier="machine_checked")
            pop = w.get("pop.total", g, y)
            if pop:
                row["population"] = pop["value"]
                ids.append(pop["obs_id"])
            for col, ind in NEED.items():
                r = w.get(ind, g, y)
                if r:
                    row[col] = r["value"]
                    ids.append(r["obs_id"])
                    cv |= set(w.caveats_for(r))
                else:
                    notes.append(f"{ind} not published for {y}")
            is_ft = g in ("MY-14", "MY-15", "MY-16")
            if is_ft:
                notes.append("no state government (Federal Territory)")
                cv.add("CV4")
            else:
                exp = w.get("state_gov.expenditure.total", g, y, basis="audited")
                if exp:
                    row["state_gov_expenditure_rm"], row["state_gov_expenditure_basis"] = exp["value"], "audited"
                    ids.append(exp["obs_id"])
                else:
                    op = w.get("state_gov.expenditure.opex", g, y, basis="audited")
                    dv = w.get("state_gov.expenditure.devex", g, y, basis="audited")
                    if op and dv:
                        row["state_gov_expenditure_rm"] = fmt(Decimal(op["value"]) + Decimal(dv["value"]))
                        row["state_gov_expenditure_basis"] = "derived: opex + devex (no printed total)"
                        ids += [op["obs_id"], dv["obs_id"]]
                    else:
                        notes.append("state spending not extracted for this year")
                rec = w.get("state_gov.revenue.nonrevenue_receipts", g, y, basis="audited")
                if rec:
                    row["state_gov_receipts_rm"] = rec["value"]
                    ids.append(rec["obs_id"])
                    cv.add("CV3")
                if pop and row["state_gov_expenditure_rm"]:
                    row["state_gov_expenditure_per_capita_rm"] = fmt(
                        Decimal(row["state_gov_expenditure_rm"]) / Decimal(pop["value"]), 2)
                if pop and rec:
                    row["state_gov_receipts_per_capita_rm"] = w.derive("per_capita", rec["obs_id"],
                                                                       pop["obs_id"])["value"]
                    row["state_gov_receipts_per_capita_rm"] = fmt(Decimal(row["state_gov_receipts_per_capita_rm"]), 2)
                if row["state_gov_expenditure_rm"]:
                    row["state_gov_placed_share"] = "1"
                    cv |= {"CV5", "CV9"}
                flag = w.headline_flag(g, y)
                if flag:
                    row["under_check"] = ";".join(flag)
                    cv.add("CV6")
            row["federal_total_expenditure_rm"] = fmt(fed_total) if fed_total else ""
            row["federal_placed_share"] = fmt(placed, 4) if placed is not None else ""
            ok = placed is not None and placed >= PLACED_MIN
            row["federal_publishable"] = "true" if ok else "false"
            row["federal_note"] = ("" if ok else
                                   f"not published: only {fmt(placed * 100, 1) if placed is not None else '?'}% of "
                                   f"federal spending in {y} can be placed by state (what the {receipts_n[y]} state "
                                   "governments record receiving); the rest (schools, clinics, subsidies, cash "
                                   "transfers) is not yet placed. Guard: 60%.")
            row["coverage_note"] = "; ".join(notes)
            row["caveats"] = ";".join(sorted(cv))
            row["source_obs_ids"] = ";".join(ids)
            out.append(row)
        checks.append(["G1 federal placed share", y, "INFO",
                       f"{fmt(placed * 100, 2) if placed is not None else 'n/a'}% "
                       f"({receipts_n[y]} states' receipts / federal total); publishable: "
                       f"{'yes' if placed is not None and placed >= PLACED_MIN else 'no'}"])
    n_geo = {y: len({r['geo_code'] for r in out if r['year'] == y}) for y in YEARS}
    checks.append(["G2 every state and territory present", "all", "PASS" if set(n_geo.values()) == {16} else "FAIL",
                   str(n_geo)])
    leak = [r for r in out if r["federal_publishable"] == "false" and r.get("federal_value")]
    checks.append(["G3 no federal value below the placed-share guard", "all", "PASS" if not leak else "FAIL",
                   f"{len(leak)} rows"])
    unflagged = [r for r in out if w.headline_flag(r["geo_code"], r["year"]) and not r["under_check"]]
    checks.append(["G4 every state-year with an open headline FAIL is flagged", "all",
                   "PASS" if not unflagged else "FAIL", f"{sum(1 for r in out if r['under_check'])} flagged"])
    for r in out:
        if r["state_gov_expenditure_rm"] and r["state_gov_expenditure_basis"] == "audited":
            op = w.get("state_gov.expenditure.opex", r["geo_code"], r["year"], basis="audited")
            dv = w.get("state_gov.expenditure.devex", r["geo_code"], r["year"], basis="audited")
            if op and dv:
                d = Decimal(r["state_gov_expenditure_rm"]) - Decimal(op["value"]) - Decimal(dv["value"])
                status = "PASS" if abs(d) <= Decimal(20000) else ("FLAGGED" if r["under_check"] else "FAIL")
                checks.append(["G5 printed total = opex + devex", f"{r['geo_code']} {r['year']}", status,
                               f"diff RM{fmt(d)}" + (f" (under check: {r['under_check']})" if r["under_check"] else "")])
    with open(os.path.join(CORE, "gap_need_vs_money.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_need.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["check", "scope", "status", "note"])
        wr.writerows(checks)
    from collections import Counter
    t = Counter(c[2] for c in checks)
    print(f"gap_need_vs_money: {len(out)} rows; checks " + ", ".join(f"{v} {k}" for k, v in sorted(t.items())))
    for c in checks:
        if c[2] in ("FAIL", "INFO"):
            print(" ", c)


if __name__ == "__main__":
    main()
