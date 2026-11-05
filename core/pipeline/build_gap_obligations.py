#!/usr/bin/env python3
"""gap_obligations_growth (docs/DATA_MODEL.md §10, Phase 5): are off-budget obligations growing faster than debt?

  python3 core/pipeline/build_gap_obligations.py -> core/gap_obligations_growth.csv, core/_validation_gap_obl.csv

Method (declared 2026-11-06 01:20 MYT, committed before any result of this view was computed; the levels below
were seen in curated/fact_obligations.csv while choosing the lines, no growth or ratio was computed):
* Core first: a family federal_gov.obligation.*, stocks at 31 December, basis audited, from PKKP's memorandum
  accounts, each year from its own volume (golden rule 6; the prior-year column each volume also prints is used
  only in check O3). One printed figure per instrument and year, never summed by us:
    debt                   Penyata Akaun Memorandum 'Hutang Awam' (to FY2015) / 'Hutang Persekutuan' (FY2016+)
    pfi                    memorandum 'Liabiliti Inisiatif Pembiayaan Swasta' (first printed FY2018)
    commitments            memorandum 'Komitmen Kewangan' (FY2018+; includes the committed guarantees)
    committed_guarantees   Komitmen Jaminan register, printed 'JUMLAH KOMITMEN JAMINAN' (FY2018+)
    loan_guarantees        Jaminan Berkanun register, loans: 'JUMLAH JAMINAN PINJAMAN' (FY2012+); FY2009-2011
                           print no deposit section, so their 'JUMLAH JAMINAN' / 'JUMLAH JAMINAN BERKANUN' total
                           is the loan guarantees (proved by Badan Berkanun + Syarikat = that total, check O2)
    deposit_guarantees     Jaminan Berkanun register 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT' (FY2012+)
  The Auditor-General's re-presentation (LKAN) and MOF's Fiscal Outlook (end-June positions) stay in
  curated/fact_obligations.csv for now: one publisher per series in this view.
* The view, grain instrument x year: amount, prior year's amount (own volumes), change, growth = amount / prior
  - 1, debt's growth the same year, growth_minus_debt_pp, ratio_to_debt = amount / debt, and an index (first year
  held = 100) beside debt's index on the same base. Status: grew_faster_than_debt (growth > debt's growth),
  grew_slower_than_debt (<), grew_as_debt (equal to 4 decimal places), first_year (no prior year held), and for
  debt itself 'the benchmark'. Ratios to 4 decimals, no rounding before the end. Never added across
  instruments: commitments include the committed guarantees, and deposit guarantees overlap deposit insurance.
* Checks: O1 every value equals its observation; O2 FY2009-2011 loan guarantees = Badan Berkanun + Syarikat
  subtotals as printed, and FY2012+ the same identity; O3 each volume's prior-year column against the previous
  volume's own figure (a restatement is INFO, reported, never applied); O4 every instrument and year once; O5
  growth summary per instrument over its whole span against debt's over the same span (INFO).
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from warehouse import CORE, Warehouse, fmt  # noqa: E402

INST = ["debt", "pfi", "commitments", "committed_guarantees", "loan_guarantees", "deposit_guarantees"]
LABEL = {"debt": "Federal government debt", "pfi": "PFI liabilities", "commitments": "Financial commitments",
         "committed_guarantees": "Committed guarantees", "loan_guarantees": "Statutory loan guarantees",
         "deposit_guarantees": "Statutory contributor and depositor guarantees"}
NOTE = {"commitments": "includes the committed guarantees: never add the two",
        "committed_guarantees": "part of the financial commitments: never add the two",
        "deposit_guarantees": "balances of contributors and depositors guaranteed by statute; overlaps deposit "
                              "insurance and is not borrowing: never add it to debt"}
FIELDS = ["geo_code", "instrument", "indicator_code", "instrument_label", "year", "amount_rm", "prior_year_rm",
          "change_rm", "growth", "debt_growth", "growth_minus_debt_pp", "ratio_to_debt", "index_first_year",
          "debt_index_same_base", "status", "source_obs_ids", "note", "caveats", "release_id"]
Q4 = Decimal("0.0001")


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    w = Warehouse()
    obs = {}
    for r in w.obs:
        if r["indicator_code"].startswith("federal_gov.obligation.") and r["geo_code"] == "MY":
            obs[(r["indicator_code"].rsplit(".", 1)[1], r["period_code"])] = r
    val = {k: Decimal(r["value"]) for k, r in obs.items()}
    out, checks = [], []
    for inst in INST:
        years = sorted(y for i, y in val if i == inst)
        base = years[0]
        for y in years:
            row = {k: "" for k in FIELDS}
            r = obs[(inst, y)]
            a = val[(inst, y)]
            prev = str(int(y) - 1)
            p, dbt, dprev = val.get((inst, prev)), val.get(("debt", y)), val.get(("debt", prev))
            row.update(geo_code="MY", instrument=inst, indicator_code=r["indicator_code"], instrument_label=LABEL[inst],
                       year=y, amount_rm=fmt(a), release_id=w.release_id)
            ids, notes = [r["obs_id"]], []
            if dbt is not None and inst != "debt":
                ids.append(obs[("debt", y)]["obs_id"])
                row["ratio_to_debt"] = fmt(a / dbt, 4)
            row["index_first_year"] = fmt(a / val[(inst, base)] * 100, 2)
            if inst != "debt" and ("debt", base) in val and dbt is not None:
                row["debt_index_same_base"] = fmt(dbt / val[("debt", base)] * 100, 2)
            if p is None:
                row["status"] = "first_year"
                notes.append("first year held" if y == base else "the year before is not held")
            else:
                ids.append(obs[(inst, prev)]["obs_id"])
                g = a / p - 1
                row.update(prior_year_rm=fmt(p), change_rm=fmt(a - p), growth=fmt(g, 4))
                if inst == "debt":
                    row["status"] = "the_benchmark"
                elif dbt is not None and dprev is not None:
                    dg = dbt / dprev - 1
                    row.update(debt_growth=fmt(dg, 4), growth_minus_debt_pp=fmt((g - dg) * 100, 2))
                    gq, dq = g.quantize(Q4), dg.quantize(Q4)
                    row["status"] = ("grew_as_debt" if gq == dq else "grew_faster_than_debt" if g > dg
                                     else "grew_slower_than_debt")
                    ids.append(obs[("debt", prev)]["obs_id"])
            if inst in NOTE:
                notes.append(NOTE[inst])
            if inst == "loan_guarantees" and int(y) <= 2011:
                notes.append("FY2009-2011 print no deposit section: the register total is the loan guarantees")
            row["caveats"] = ";".join(sorted(set(w.caveats_for(r)) | {"CV30"}))
            row["source_obs_ids"] = ";".join(dict.fromkeys(ids))
            row["note"] = "; ".join(notes)
            out.append(row)

    def add(c, st, dt):
        checks.append(dict(check=c, scope="core/gap_obligations_growth.csv", status=st, detail=dt))
    bad = [r for r in out if Decimal(r["amount_rm"]) != Decimal(w.by_id[r["source_obs_ids"].split(";")[0]]["value"])]
    add("O1 every value equals its observation", "PASS" if not bad else "FAIL", f"{len(out)} rows")
    # O2 and O3 read the L1 registers directly
    pk = os.path.join(REPO, "sources", "pkkp", "data")
    bad, n = [], 0
    for y in sorted({y for i, y in val if i == "loan_guarantees"}):
        sub = [Decimal(r["jumlah_rm"]) for r in rows(os.path.join(pk, y, "fact_statutory_guarantees.csv"))
               if r["year"] == y and r["row_type"] == "subtotal" and r["agensi_bm"].strip() in
               ("Jumlah Badan Berkanun", "Jumlah Syarikat")]
        n += 1
        if len(sub) != 2 or sum(sub) != val[("loan_guarantees", y)]:
            bad.append(f"{y}: {sub} vs {val[('loan_guarantees', y)]}")
    add("O2 loan guarantees = Badan Berkanun + Syarikat as printed", "PASS" if not bad else "FAIL",
        f"{n} years" + (f"; {bad}" if bad else ""))
    lab = {"fact_memorandum.csv": {"HUTANG AWAM": "debt", "HUTANG PERSEKUTUAN": "debt",
                                   "LIABILITI INISIATIF PEMBIAYAAN SWASTA": "pfi", "KOMITMEN KEWANGAN": "commitments"},
           "fact_guarantees.csv": {"JUMLAH KOMITMEN JAMINAN": "committed_guarantees"},
           "fact_statutory_guarantees.csv": {"JUMLAH JAMINAN PINJAMAN": "loan_guarantees",
                                             "JUMLAH JAMINAN PENCARUM / PENDEPOSIT": "deposit_guarantees"}}
    restated, compared = [], 0
    for y in sorted({y for _, y in val}):
        prev = str(int(y) - 1)
        for fname, m in lab.items():
            path = os.path.join(pk, y, fname)
            if not os.path.exists(path):
                continue
            for r in rows(path):
                if r["year"] != prev:
                    continue
                if fname == "fact_memorandum.csv" and "LIABILITI" not in r["section"].upper():
                    continue
                inst = m.get((r.get("line_item_bm") or r.get("agensi_bm") or "").strip().upper())
                v = r.get("amount_rm") or r.get("jumlah_rm")
                if inst and v and (inst, prev) in val:
                    compared += 1
                    d = Decimal(v) - val[(inst, prev)]
                    if abs(d) > Decimal("1"):
                        restated.append(f"{inst} FY{prev} restated in the FY{y} volume by {fmt(d)}")
                        for row in out:
                            if row["instrument"] == inst and row["year"] == y:
                                row["note"] = "; ".join(x for x in (row["note"], (
                                    f"this volume reprints FY{prev} as {fmt(Decimal(v))} ({fmt(d)} against the FY{prev} "
                                    "volume); growth here is against the FY{prev} volume's own figure (golden rule 6)"
                                ).replace("{prev}", prev)) if x)
    add("O3 each volume's prior-year figure against the previous volume (INFO)", "INFO",
        f"{compared} compared; " + ("; ".join(restated) if restated else "no restatement beyond RM1"))
    keys = [(r["instrument"], r["year"]) for r in out]
    add("O4 every instrument and year once", "PASS" if len(keys) == len(set(keys)) else "FAIL", f"{len(keys)} rows")
    summ = []
    for inst in INST:
        ys = sorted(y for i, y in val if i == inst)
        a0, a1 = val[(inst, ys[0])], val[(inst, ys[-1])]
        line = f"{inst} {ys[0]}-{ys[-1]}: x{fmt(a1 / a0, 3)}"
        if inst != "debt":
            line += f" (debt x{fmt(val[('debt', ys[-1])] / val[('debt', ys[0])], 3)})"
        summ.append(line)
    add("O5 growth over each instrument's span against debt's (INFO)", "INFO", "; ".join(summ))
    with open(os.path.join(CORE, "gap_obligations_growth.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_obl.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    print(f"gap_obligations_growth: {len(out)} rows; " + "; ".join(f"{c['check'][:2]} {c['status']}" for c in checks))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
