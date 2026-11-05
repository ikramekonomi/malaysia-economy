#!/usr/bin/env python3
"""gap_target_vs_outcome (docs/DATA_MODEL.md §10, Phase 5): was the plan target met?

  python3 core/pipeline/build_gap_target.py -> core/gap_target_vs_outcome.csv, core/_validation_gap_tvo.csv

Method (declared 2026-11-06 01:25 MYT, committed before the targets were extracted or any outcome compared; the
RMK12 appendix pages were read to find the tables):
* Targets: the Twelfth Malaysia Plan (RMKe-12, 2021-2025), Lampiran, as printed (sources/rmk/, basis target, edition
  rmk:rmk12): the 2025 target ('Sasaran 2025') and the 2021-2025 average annual growth target ('Sasaran RMKe-12')
  of three tables, the only ones whose outcome core holds today:
    Jadual 5   GDP by state at constant 2015 prices (KDNK; 'WP Kuala Lumpur' includes WP Putrajaya, as footnoted)
    Jadual 10  federal government finance (revenue, operating and gross development spending, loan recoveries, net
               development spending, overall balance, and the balance as % of GDP, a range)
    Jadual 14  labour market (employment, labour force, unemployment rate, participation rate)
  Lines whose outcome core does not hold are extracted at L1 and listed in check T5 (not compared): GDP per capita,
  sectors, the GDP by expenditure and income tables, and the rest of the appendix.
* Outcomes, each from core as published, never adjusted:
    GDP by state      gdp.real, DOSM, the current vintage, 2025 (and 2020 for growth); the KL row is WP Kuala Lumpur +
                      WP Putrajaya (the plan's own footnote), summed by declared rule; Labuan alone
    federal finance   MOF Tinjauan Fiskal FY2025 official actual (basis actual), with BNM beside it; PKKP FY2025
                      (audited) when loaded
    labour            lfs.*, DOSM, 2025 annual
* Comparison, by declared rule (no direction is assumed better):
    level targets     outcome / target and outcome - target; status at_target (within +-1% of the target),
                      above_target, below_target; for a range target (e.g. '-3.5 ~ -3.0'), within_range,
                      above_range, below_range
    growth targets    outcome = compound average growth 2020-2025 of the outcome series ((v2025 / v2020)^(1/5) - 1,
                      both from the same vintage); status the same words against the target (a point: within +-0.1
                      percentage point is at_target; a range: within_range)
    not_held          the outcome is not in core
  Status words state the position only; whether above or below is good depends on the line, and is left to the
  reader. All 13 states and the Federal Territories in the table are rows (golden rule 11).
* Checks: T1 Jadual 10's printed identities (revenue - opex = current balance; gross DE - loan recoveries = net DE;
  current balance - net DE - COVID-19 Fund = overall balance) for every printed column; T2 Jadual 14's sectors add
  up to total employment; T3 every target traces to its L1 row and page; T4 every row once; T5 coverage (INFO).
"""
import csv
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from warehouse import CORE, Warehouse, fmt  # noqa: E402

LEVEL_TOL, GROWTH_TOL = Decimal("0.01"), Decimal("0.1")
FIELDS = ["geo_code", "plan", "target_line", "indicator_code", "breakdown_key", "year", "target", "outcome",
          "outcome_source", "outcome_bnm", "difference", "ratio", "status", "source_obs_ids", "note", "caveats",
          "release_id"]


def main():
    w = Warehouse()
    tg = [r for r in w.obs if r["basis"] == "target" and r["edition_id"] == "rmk:rmk12.pdf"]
    stat = defaultdict(list)   # (ind, geo, period) -> DOSM statistic rows (all vintages)
    rep = {}
    for r in w.obs:
        if r["indicator_code"] in ("gdp.real",) or r["indicator_code"].startswith("lfs."):
            if r["basis"] == "statistic" and r["breakdown_key"] == "_total" and r["edition_id"].startswith("dosm:"):
                stat[(r["indicator_code"], r["geo_code"], r["period_code"])].append(r)
        elif r["indicator_code"].startswith("federal_gov.") and r["period_code"] == "2025" and r["basis"] == "actual" \
                and r["geo_code"] == "MY" and r["breakdown_key"] == "_total":
            rep[(r["indicator_code"], r["edition_id"].split(":")[0])] = r

    def latest(ind, geo, per):
        lst = stat.get((ind, geo, per), [])
        return max(lst, key=lambda x: x["vintage"]) if lst else None
    out, checks = [], []
    for t in sorted(tg, key=lambda x: (x["indicator_code"], x["geo_code"], x["period_code"])):
        row = {k: "" for k in FIELDS}
        l1 = t["l1_ref"]
        ind, geo, per = t["indicator_code"], t["geo_code"], t["period_code"]
        tv = Decimal(t["value"])
        row.update(geo_code=geo, plan="RMKe-12 (2021-2025)", indicator_code=ind, breakdown_key=t["breakdown_key"],
                   year=per, target=fmt(tv), release_id=w.release_id, target_line=t["table_ref"].split(":")[0])
        ids, notes, ov, used = [t["obs_id"]], [], None, []
        geos = ["MY-14", "MY-16"] if t["breakdown_key"] == "geo_scope=MY-14+MY-16" else [geo]
        if ind == "gdp.real":
            got = [latest("gdp.real", g, "2025") for g in geos]
            if all(got):
                ov, used = sum(Decimal(x["value"]) for x in got), got
                row["outcome_source"] = f"DOSM gdp.real 2025 ({got[0]['edition_id']})"
        elif ind == "gdp.real.avg_growth":
            a = [latest("gdp.real", g, "2025") for g in geos]
            b = [latest("gdp.real", g, "2020") for g in geos]
            if all(a) and all(b) and len({x["edition_id"] for x in a + b}) == 1:
                v1, v0 = sum(Decimal(x["value"]) for x in a), sum(Decimal(x["value"]) for x in b)
                ov = (Decimal(str((float(v1) / float(v0)) ** 0.2)) - 1) * 100
                used = a + b
                row["outcome_source"] = f"compound average growth 2020-2025 of DOSM gdp.real ({a[0]['edition_id']})"
        elif ind.startswith("lfs."):
            x = latest(ind, "MY", "2025")
            if x:
                ov, used = Decimal(x["value"]), [x]
                row["outcome_source"] = f"DOSM {ind} 2025 ({x['edition_id']})"
        else:
            x = rep.get((ind, "mof"))
            if x:
                ov, used = Decimal(x["value"]), [x]
                row["outcome_source"] = f"MOF FY2025 actual ({x['edition_id']}); PKKP FY2025 not yet loaded"
            b = rep.get((ind, "bnm"))
            if b:
                row["outcome_bnm"] = fmt(Decimal(b["value"]))
                ids.append(b["obs_id"])
        if t["breakdown_key"] == "geo_scope=MY-14+MY-16":
            notes.append("the plan's Kuala Lumpur row includes Putrajaya (its own footnote): the outcome is WP Kuala "
                         "Lumpur + WP Putrajaya")
        if ov is None:
            row["status"] = "not_held"
            notes.append("the outcome is not in core" if not (ind == "gdp.real.avg_growth" and geo == "MY-14") else
                         "not computed: DOSM prints WP Putrajaya separately only from 2023, so 2020 has no Putrajaya "
                         "figure to add (DOSM's KL falls from RM240.5b in 2022 to RM237.2b in 2023 while KL + "
                         "Putrajaya is RM250.2b, which suggests the earlier KL figure includes Putrajaya; not assumed)")
        else:
            ids += [x["obs_id"] for x in used]
            row["outcome"] = fmt(ov, 2 if ind == "gdp.real.avg_growth" else None)
            row["difference"] = fmt(ov - tv, 2 if ind == "gdp.real.avg_growth" else None)
            if ind == "gdp.real.avg_growth":
                d = ov - tv
                row["status"] = "at_target" if abs(d) <= GROWTH_TOL else "above_target" if d > 0 else "below_target"
            else:
                row["ratio"] = fmt(ov / tv, 4)
                d = ov - tv
                row["status"] = ("at_target" if abs(d) <= LEVEL_TOL * abs(tv) else
                                 "above_target" if d > 0 else "below_target")
            if ind == "federal_gov.overall_balance":
                notes.append("a balance is negative: below_target means a larger deficit than planned")
            if ind == "gdp.real":
                notes.append("a level target is sensitive to DOSM's revisions of past levels since 2021; the growth "
                             "row of the same state is the like-for-like comparison")
        cv = set()
        for i in ids:
            cv |= set(w.caveats_for(w.by_id[i]))
        row["caveats"] = ";".join(sorted(cv))
        row["source_obs_ids"] = ";".join(ids)
        row["note"] = "; ".join(notes)
        row["_l1"] = l1
        out.append(row)

    def add(c, st, dt):
        checks.append(dict(check=c, scope="core/gap_target_vs_outcome.csv", status=st, detail=dt))
    v = [r for r in csv.DictReader(open(os.path.join(REPO, "sources", "rmk", "data", "_validation_rmk12.csv")))]
    for k in ("V3", "V4"):
        bad = [r for r in v if r["check"].startswith(k) and r["status"] == "FAIL"]
        add(f"T{1 if k == 'V3' else 2} {'Jadual 10 printed identities' if k == 'V3' else 'Jadual 14 sectors add up'} "
            "(sources/rmk/data/_validation_rmk12.csv)", "PASS" if not bad else "FAIL",
            f"{sum(1 for r in v if r['check'].startswith(k))} checks")
    l1 = {}
    path = os.path.join(REPO, "sources", "rmk", "data", "rmk12", "fact_rmk12_lampiran.csv")
    for i, r in enumerate(csv.DictReader(open(path, encoding="utf-8")), start=2):
        l1[f"{os.path.relpath(path, REPO)}#row{i}"] = r
    bad = [r for r in out if r["_l1"] not in l1 or not l1[r["_l1"]]["pdf_page"]]
    add("T3 every target traces to its L1 row and page", "PASS" if not bad else "FAIL", f"{len(out)} targets")
    keys = [(r["indicator_code"], r["geo_code"], r["breakdown_key"], r["year"]) for r in out]
    add("T4 every row once", "PASS" if len(keys) == len(set(keys)) else "FAIL", f"{len(keys)} rows")
    used = {r["_l1"] for r in out}
    left = Counter((x["jadual"], x["line_bm"]) for k, x in l1.items() if k not in used and x["measure"] == "sasaran_2025")
    add("T5 coverage (INFO): 2025 targets extracted but not compared (outcome not in core)", "INFO",
        "; ".join(f"Jadual {j} {ln} ({n})" for (j, ln), n in sorted(left.items())))
    add("T6 status counts (INFO)", "INFO", ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(
        Counter((r["indicator_code"], r["status"]) for r in out).items())))
    for r in out:
        r.pop("_l1")
    with open(os.path.join(CORE, "gap_target_vs_outcome.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_tvo.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    print(f"gap_target_vs_outcome: {len(out)} rows; " + "; ".join(f"{c['check'][:2]} {c['status']}" for c in checks))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
