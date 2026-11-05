#!/usr/bin/env python3
"""gap_budget_vs_actual (docs/DATA_MODEL.md §10, Phase 5): was the money budgeted spent?

  python3 core/pipeline/build_gap_budget_vs_actual.py -> core/gap_budget_vs_actual.csv, core/_validation_gap_bva.csv

Method (declared 2026-11-05, committed before any result of this view was computed):
* Grain: federal body (entity, D26/D28/D31) x year x flow (opex: B and T votes' operating spending; devex: P
  votes' development spending), every year the audited accounts are held (PKKP FY2009-2024) and the Budget books'
  estimate years (Anggaran 2024-2026: 2023-2026). Spending heads (T.*, P.70) are rows of the federal government
  (E000001) with their head as breakdown, as in core. Each year from its own volume (golden rule 6).
* Columns, each one source as printed, never mixed:
    estimate_original_pkkp   opex: the original estimate the audited accounts print (Nota 5(b) anggaran_asal)
    estimate_revised_pkkp    opex: the revised estimate (anggaran_dipinda); devex: the accounts' own allocation
                             column (Lampiran 2 'Anggaran'), which is NOT the Budget book's original estimate
                             (FY2024: RM85.2b against the book's RM92.0b), so it is labelled an allocation
    estimate_original_book   the Budget book's original estimate for that year (the book of that year, or the
                             next book's 'anggaran asal' column)
    actual_audited           PKKP sebenar
    actual_book              the Budget book's reprint of that year's actual (the books two years later)
* Derived, by declared rules only (meta/derivation.csv DV1-style ratios, no rounding before the end):
    execution_rate           actual_audited / estimate_revised_pkkp (opex), / the allocation (devex)
    unspent_rm               estimate_revised_pkkp - actual_audited (negative = overspent)
    book_vs_pkkp_estimate_rm estimate_original_book - estimate_original_pkkp (opex): two printings of one
                             estimate; a difference is reported, never resolved
    book_vs_pkkp_actual_rm   actual_book - actual_audited: MOF's reprint against the audit; a difference is a
                             restatement or a different scope (the book prints under its own year's votes)
* Status words, no ranking: within_estimate (execution 0.90-1.00), underspent (< 0.90), overspent (> 1.00),
  not_held (a side missing), and for the two-printings columns agree (|difference| <= RM1, whole ringgit against
  sen) or differ. Thresholds declared here, before results.
* A body's row is only ever its own vote: a lapsed vote's successor is another body (lineage, never summed);
  growth across years is not computed in this view.
* Checks: V1 every row's audited actual equals its fact_observation; V2 each year's opex and devex rows add up to
  the PKKP vote totals (C16); V3 every value traces to an observation id; V4 every body and year present once.
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, Warehouse, fmt  # noqa: E402

FLOW = {"federal_gov.vote.opex": "opex", "federal_gov.vote.devex": "devex"}
LOW, HIGH = Decimal("0.90"), Decimal("1.00")
FIELDS = ["geo_code", "entity_id", "body", "breakdown_key", "flow", "year", "estimate_original_pkkp", "estimate_revised_pkkp",
          "estimate_revised_kind", "estimate_original_book", "actual_audited", "actual_book", "execution_rate",
          "unspent_rm", "status", "book_vs_pkkp_estimate_rm", "book_vs_pkkp_estimate_status", "estimate_printings",
          "book_vs_pkkp_actual_rm", "book_vs_pkkp_actual_status", "actual_printings", "source_obs_ids", "note",
          "caveats", "release_id"]


def main():
    w = Warehouse()
    cells = defaultdict(lambda: defaultdict(list))   # (entity, bk, flow, year) -> slot -> [obs]
    for r in w.obs:
        f = FLOW.get(r["indicator_code"])
        if not f:
            continue
        pub = r["edition_id"].split(":")[0]
        slot = {("pkkp", "audited"): "actual_audited", ("pkkp", "budget_estimate"): "estimate_original_pkkp",
                ("pkkp", "revised_estimate"): "estimate_revised_pkkp", ("pkkp", "allocation"): "estimate_revised_pkkp",
                ("anggaran", "budget_estimate"): "estimate_original_book",
                ("anggaran", "actual"): "actual_book"}.get((pub, r["basis"]))
        if slot:
            cells[(r["entity_id"], r["breakdown_key"], f, r["period_code"])][slot].append(r)
    out, checks = [], []
    for (eid, bk, f, y), d in sorted(cells.items(), key=lambda x: (x[0][3], x[0][2], x[0][0], x[0][1])):
        row = {k: "" for k in FIELDS}
        e = w.entity.get(eid, {})
        row.update(geo_code="MY", entity_id=eid, body=e.get("name_bm", ""), breakdown_key=bk, flow=f, year=y, release_id=w.release_id)
        ids, notes = [], []

        def one(slot, pick=min):
            lst = d.get(slot, [])
            if not lst:
                return None
            # a book's estimate or actual can be printed by two books: the earliest printing is used, all are counted
            r = pick(lst, key=lambda x: x["vintage"])
            ids.append(r["obs_id"])
            return r
        val = {}
        for slot in ("estimate_original_pkkp", "estimate_revised_pkkp", "estimate_original_book", "actual_audited",
                     "actual_book"):
            r = one(slot)
            if r:
                val[slot] = Decimal(r["value"])
                row[slot] = fmt(val[slot])
                if slot == "estimate_revised_pkkp":
                    row["estimate_revised_kind"] = "revised estimate" if r["basis"] == "revised_estimate" else \
                        "the accounts' allocation (Lampiran 2 'Anggaran'), not the tabled estimate"
        bes = {Decimal(x["value"]) for x in d.get("estimate_original_book", [])}
        bac = {Decimal(x["value"]) for x in d.get("actual_book", [])}
        row["estimate_printings"] = str(len(d.get("estimate_original_book", []))) if bes else ""
        row["actual_printings"] = str(len(d.get("actual_book", []))) if bac else ""
        if len(bes) > 1:
            notes.append("two Budget books print different original estimates for this year; the earlier is used")
        if len(bac) > 1:
            notes.append("two Budget books print different actuals for this year; the earlier is used")
        a, rv = val.get("actual_audited"), val.get("estimate_revised_pkkp")
        if a is not None and rv:
            rate = a / rv
            row["execution_rate"] = fmt(rate, 4)
            row["unspent_rm"] = fmt(rv - a)
            row["status"] = "overspent" if rate > HIGH else "within_estimate" if rate >= LOW else "underspent"
        else:
            row["status"] = "not_held"
            notes.append("no audited actual (a Budget-book year)" if a is None else "no estimate printed in the accounts")
        if "estimate_original_book" in val and "estimate_original_pkkp" in val:
            dd = val["estimate_original_book"] - val["estimate_original_pkkp"]
            row["book_vs_pkkp_estimate_rm"] = fmt(dd)
            row["book_vs_pkkp_estimate_status"] = "agree" if abs(dd) <= 1 else "differ"
        if "actual_book" in val and a is not None:
            dd = val["actual_book"] - a
            row["book_vs_pkkp_actual_rm"] = fmt(dd)
            row["book_vs_pkkp_actual_status"] = "agree" if abs(dd) <= 1 else "differ"
        # CV23 on every vote figure (gross of what the body pays on); CV22 where a Budget book's reprint is used
        cv = {"CV23"} | ({"CV22"} if row["actual_book"] or row["estimate_original_book"] else set())
        row["caveats"] = ";".join(sorted(cv))
        if row.get("book_vs_pkkp_estimate_status") == "differ" and val.get("estimate_original_pkkp") == 0:
            notes.append("the accounts print no original estimate (the vote was created during the year); the "
                         "Budget book restates one under its own votes")
        row["source_obs_ids"] = ";".join(ids)
        row["note"] = "; ".join(notes)
        out.append(row)

    def add(c, s, st, dt):
        checks.append(dict(check=c, scope=s, status=st, detail=dt))
    # V1: every audited actual equals its observation (it is the observation)
    bad = [r for r in out if r["actual_audited"] and not any(
        w.by_id[i]["value"] and Decimal(w.by_id[i]["value"]) == Decimal(r["actual_audited"]) and w.by_id[i]["basis"] == "audited"
        for i in r["source_obs_ids"].split(";"))]
    add("V1 every audited actual is its observation", "core/gap_budget_vs_actual.csv", "PASS" if not bad else "FAIL",
        f"{sum(1 for r in out if r['actual_audited'])} rows" + (f"; {len(bad)} bad" if bad else ""))
    # V2: each year's audited rows add up to the sum of the vote observations (C16 checks those against PKKP)
    tot = defaultdict(Decimal)
    for r in w.obs:
        if FLOW.get(r["indicator_code"]) and r["basis"] == "audited" and r["edition_id"].startswith("pkkp:"):
            tot[(FLOW[r["indicator_code"]], r["period_code"])] += Decimal(r["value"])
    vt = defaultdict(Decimal)
    for r in out:
        if r["actual_audited"]:
            vt[(r["flow"], r["year"])] += Decimal(r["actual_audited"])
    bad = [k for k in tot if tot[k] != vt[k]]
    add("V2 each year's rows add up to the audited vote totals", "core/gap_budget_vs_actual.csv",
        "PASS" if not bad else "FAIL", f"{len(tot)} flow-years" + (f"; {bad[:5]}" if bad else ""))
    bad = [r for r in out if any(i not in w.by_id for i in r["source_obs_ids"].split(";") if i)]
    add("V3 every value traces to an observation", "core/gap_budget_vs_actual.csv", "PASS" if not bad else "FAIL",
        f"{len(out)} rows")
    keys = [(r["entity_id"], r["breakdown_key"], r["flow"], r["year"]) for r in out]
    add("V4 every body, flow and year present once", "core/gap_budget_vs_actual.csv",
        "PASS" if len(keys) == len(set(keys)) else "FAIL", f"{len(keys)} rows")
    from collections import Counter
    st = Counter((r["flow"], r["status"]) for r in out)
    for k in ("book_vs_pkkp_estimate_status", "book_vs_pkkp_actual_status"):
        c2 = Counter((r["flow"], r[k]) for r in out if r[k])
        add(f"V6 {k} counts (INFO)", "core/gap_budget_vs_actual.csv", "INFO",
            ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(c2.items())))
    add("V5 status counts (INFO)", "core/gap_budget_vs_actual.csv", "INFO", ", ".join(f"{a}/{b} {n}" for (a, b), n in sorted(st.items())))
    with open(os.path.join(CORE, "gap_budget_vs_actual.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_bva.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    print(f"gap_budget_vs_actual: {len(out)} rows; " + "; ".join(f"{c['check'][:3]} {c['status']}" for c in checks))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
