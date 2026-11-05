#!/usr/bin/env python3
"""gap_revenue_estimate_vs_collected (docs/DATA_MODEL.md §10, Phase 5): did revenue come in as estimated?

  python3 core/pipeline/build_gap_revenue.py -> core/gap_revenue_estimate_vs_collected.csv, core/_validation_gap_rev.csv

Method (declared 2026-11-05, committed before any result of this view was computed):
* Core first: a new indicator federal_gov.revenue.by_type, breakdown hasil_kod = the Budget revenue book's section
  code (60000 tax, 70000 non-tax, 80000 non-revenue receipts, 90000 the Federal Territories' revenue) or _total.
  Two sources, each as printed:
    PKKP fact_revenue (Nota 5(a), FY2009-2024, each year its own volume): levels 0 and 1, with the original
      estimate (budget_estimate), revised estimate (revised_estimate) and actual (audited). PKKP prints names,
      not codes: the four level-1 names (and their FY2009-2011 'JUMLAH ...' spellings) map to the book's codes by
      the declared table NAME_TO_KOD below, proved by the 2024 actuals being printed in both (equal or reported).
      FY2009's 'JUMLAH PELBAGAI TERIMAAN' (miscellaneous receipts) has no book code and is kept under its own
      key, never merged.
    Anggaran Hasil books 2025-2026 (sources/anggaran-hasil): section and total rows: the actual two years back
      (basis actual), the revised estimate of the year before (revised_estimate) and the book year's estimate
      (budget_estimate).
* The view, grain hasil_kod x year: estimate_original, estimate_revised, actual_audited (PKKP), and the book's
  revised estimate and actual beside them; collection_rate = actual / original estimate and actual / revised;
  status: on_estimate (0.97-1.03 of the original), above_estimate (> 1.03), below_estimate (< 0.97), not_held.
  Thresholds declared here, before results. Book vs PKKP: agree within RM1 (whole ringgit against sen), else
  differ, reported never resolved.
* Checks: R1 each year's PKKP level-1 categories add up to the level-0 total (each basis); R2 PKKP's level-0
  audited total equals federal_gov.revenue.total (PKKP, the performance statement) or the difference is reported;
  R3 every value traces to an observation; R4 the book's sections add up to its total.
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, Warehouse, fmt  # noqa: E402

LOW, HIGH = Decimal("0.97"), Decimal("1.03")
LABEL = {"_total": "Jumlah hasil", "hasil_kod=60000": "Hasil cukai", "hasil_kod=70000": "Hasil bukan cukai",
         "hasil_kod=80000": "Terimaan bukan hasil", "hasil_kod=90000": "Hasil Wilayah Persekutuan",
         "hasil_kod=pelbagai_terimaan_2009": "Pelbagai terimaan (FY2009 only)"}
FIELDS = ["geo_code", "breakdown_key", "revenue_type", "year", "estimate_original", "estimate_revised", "actual_audited",
          "collection_rate_original", "collection_rate_revised", "status", "book_estimate_original",
          "book_estimate_revised", "book_actual", "book_vs_pkkp_revised_rm", "book_vs_pkkp_revised_status",
          "book_vs_pkkp_actual_rm", "book_vs_pkkp_actual_status", "source_obs_ids", "note", "caveats", "release_id"]


def main():
    w = Warehouse()
    cells = defaultdict(lambda: defaultdict(list))
    for r in w.obs:
        if r["indicator_code"] != "federal_gov.revenue.by_type":
            continue
        pub = r["edition_id"].split(":")[0]
        slot = {("pkkp", "budget_estimate"): "estimate_original", ("pkkp", "revised_estimate"): "estimate_revised",
                ("pkkp", "audited"): "actual_audited", ("anggaran_hasil", "budget_estimate"): "book_estimate_original",
                ("anggaran_hasil", "revised_estimate"): "book_estimate_revised",
                ("anggaran_hasil", "actual"): "book_actual"}.get((pub, r["basis"]))
        if slot:
            cells[(r["breakdown_key"], r["period_code"])][slot].append(r)
    out, checks = [], []
    for (bk, y), d in sorted(cells.items(), key=lambda x: (x[0][1], x[0][0])):
        row = {k: "" for k in FIELDS}
        row.update(geo_code="MY", breakdown_key=bk, revenue_type=LABEL.get(bk, bk), year=y, release_id=w.release_id)
        ids, val, notes = [], {}, []
        for slot, lst in d.items():
            r = min(lst, key=lambda x: x["vintage"])
            if len({x["value"] for x in lst}) > 1:
                notes.append(f"{slot}: two printings differ; the earlier is used")
            ids.append(r["obs_id"])
            val[slot] = Decimal(r["value"])
            row[slot] = fmt(val[slot])
        a, o, rv = val.get("actual_audited"), val.get("estimate_original"), val.get("estimate_revised")
        if a is not None and o:
            rate = a / o
            row["collection_rate_original"] = fmt(rate, 4)
            row["status"] = "above_estimate" if rate > HIGH else "on_estimate" if rate >= LOW else "below_estimate"
        else:
            row["status"] = "not_held"
            notes.append("no audited actual (a Budget-book year)" if a is None else "no original estimate printed")
        if a is not None and rv:
            row["collection_rate_revised"] = fmt(a / rv, 4)
        for b, p, k in (("book_estimate_revised", "estimate_revised", "book_vs_pkkp_revised"),
                        ("book_actual", "actual_audited", "book_vs_pkkp_actual")):
            if b in val and p in val:
                dd = val[b] - val[p]
                row[f"{k}_rm"] = fmt(dd)
                row[f"{k}_status"] = "agree" if abs(dd) <= 1 else "differ"
        row["caveats"] = "CV22" if any(k.startswith("book_") for k in val) else ""
        row["source_obs_ids"] = ";".join(ids)
        row["note"] = "; ".join(notes)
        out.append(row)

    def add(c, s, st, dt):
        checks.append(dict(check=c, scope=s, status=st, detail=dt))
    # R1 is C18 in core; R2: PKKP Nota 5(a) total vs the performance statement's revenue total
    tot = {r["period_code"]: Decimal(r["value"]) for r in w.obs if r["indicator_code"] == "federal_gov.revenue.total"
           and r["basis"] == "audited" and r["edition_id"].startswith("pkkp:")}
    diffs = []
    for r in out:
        if r["breakdown_key"] == "_total" and r["actual_audited"] and r["year"] in tot:
            dd = Decimal(r["actual_audited"]) - tot[r["year"]]
            if abs(dd) > 2:
                diffs.append(f"{r['year']}: {fmt(dd)}")
    add("R2 PKKP Nota 5(a) revenue total vs the performance statement's revenue (federal_gov.revenue.total)",
        "PKKP", "PASS" if not diffs else "INFO", f"{len(tot)} years" + (f"; differ: {diffs}" if diffs else ""))
    bad = [r for r in out if any(i not in w.by_id for i in r["source_obs_ids"].split(";") if i)]
    add("R3 every value traces to an observation", "core", "PASS" if not bad else "FAIL", f"{len(out)} rows")
    bsum = defaultdict(Decimal)
    btot = {}
    for r in out:
        for col in ("book_estimate_original", "book_estimate_revised", "book_actual"):
            if r[col]:
                if r["breakdown_key"] == "_total":
                    btot[(r["year"], col)] = Decimal(r[col])
                else:
                    bsum[(r["year"], col)] += Decimal(r[col])
    bad = [f"{k}: {bsum[k]} vs {v}" for k, v in btot.items() if abs(bsum[k] - v) > 2]
    add("R4 the book's sections add up to its total", "anggaran_hasil", "PASS" if not bad else "FAIL",
        f"{len(btot)} totals" + (f"; {bad}" if bad else ""))
    from collections import Counter
    add("R5 status counts (INFO)", "view", "INFO", ", ".join(f"{a}/{b} {n}" for (a, b), n in
        sorted(Counter((r["breakdown_key"], r["status"]) for r in out).items())))
    add("R6 book vs PKKP (INFO)", "view", "INFO", ", ".join(
        f"{k}: {dict(Counter(r[k] for r in out if r[k]))}" for k in ("book_vs_pkkp_revised_status", "book_vs_pkkp_actual_status")))
    with open(os.path.join(CORE, "gap_revenue_estimate_vs_collected.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_rev.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    print(f"gap_revenue_estimate_vs_collected: {len(out)} rows; " + "; ".join(f"{c['check'][:2]} {c['status']}" for c in checks))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
