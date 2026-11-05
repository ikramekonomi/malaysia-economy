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
* Added after the blind verifier (2026-11-05, before publication; no threshold changed):
    - one Budget book per year for estimate_original_book: the book of that year where it exists, else the
      earliest book printing it (a later book restates the year under its own, reorganised votes: FY2024 under
      PETRA and Digital in the 2025 book); another book's figure is named in the note, never used
    - a book's reprinted actual is shown only on a body that held the vote that year (has an audited actual);
      a reprint filed under a successor's vote (KASA's FY2022 under PETRA in the 2025 book) is not a row of
      the successor; such reprints are counted in V8
    - execution_rate_book = actual_audited / estimate_original_book, beside the accounts-based rate (for devex
      the accounts' column is an allocation, not the tabled estimate)
    - each row carries the caveats of the observations it uses (CV21 where the printed vote total and its lines
      disagree, e.g. FY2009 P.26/P.44), and notes on the contingency reserve (P.70), the contributions to
      statutory funds (B.12) and spending above the printed estimate
* Checks: V1 every row's audited actual equals its fact_observation; V2 each year's opex and devex rows add up to
  the PKKP vote totals (C16); V3 every value traces to an observation id; V4 every body and year present once;
  V7 each year's book-estimate column adds up to that one book's printed votes; V8 book reprints not shown (INFO).
"""
import csv
import os
import re
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
          "execution_rate_book",
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
    def book_year(r):
        m = re.search(r"(\d{4})\.pdf$", r["edition_id"])
        return m.group(1) if m else r["vintage"][:4]
    # one book per year for the original estimate: the book of that year, else the earliest book printing it
    books = defaultdict(set)
    for d in cells.values():
        for r in d.get("estimate_original_book", []):
            books[r["period_code"]].add(book_year(r))
    chosen = {y: (y if y in bs else min(bs)) for y, bs in books.items()}
    audited_years = {k[3] for k, d in cells.items() if d.get("actual_audited")}
    hidden = []   # book reprints not shown: filed under a body that did not hold the vote that year
    out, checks = [], []
    for (eid, bk, f, y), d in sorted(cells.items(), key=lambda x: (x[0][3], x[0][2], x[0][0], x[0][1])):
        row = {k: "" for k in FIELDS}
        e = w.entity.get(eid, {})
        row.update(geo_code="MY", entity_id=eid, body=e.get("name_bm", ""), breakdown_key=bk, flow=f, year=y, release_id=w.release_id)
        ids, notes, used = [], [], []
        other = [r for r in d.get("estimate_original_book", []) if book_year(r) != chosen[y]]
        if other:
            d["estimate_original_book"] = [r for r in d["estimate_original_book"] if book_year(r) == chosen[y]]
            for r in other:
                notes.append(f"the {book_year(r)} Budget book prints an original estimate of {fmt(Decimal(r['value']))} "
                             f"for this body under its own votes; not used (this year's estimate is from the "
                             f"{chosen[y]} book)")
        if d.get("actual_book") and not d.get("actual_audited") and y in audited_years:
            hidden.extend((eid, bk, f, y, r["edition_id"], r["value"]) for r in d["actual_book"])
            d["actual_book"] = []
        if not any(d.get(k) for k in ("estimate_original_pkkp", "estimate_revised_pkkp", "estimate_original_book",
                                      "actual_audited", "actual_book")):
            continue

        def one(slot, pick=min):
            lst = d.get(slot, [])
            if not lst:
                return None
            # a book's estimate or actual can be printed by two books: the earliest printing is used, all are counted
            r = pick(lst, key=lambda x: x["vintage"])
            ids.append(r["obs_id"])
            used.append(r)
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
        if a is not None and val.get("estimate_original_book"):
            row["execution_rate_book"] = fmt(a / val["estimate_original_book"], 4)
        if rv and a is not None and a > rv:
            notes.append("spent above the estimate printed in the accounts; whether the excess was authorised "
                         "later (supplementary supply) is not stated in this view")
        if bk == "reserve_head=P.70":
            notes.append("the contingency reserve: it is drawn by transfers to other votes, so its own spending "
                         "is not expected to match its allocation")
        if eid == "E000026" and f == "opex":
            notes.append("B.12 carries the transfer to the Development Fund (and other statutory funds); its "
                         "spending is money moved to those funds, not spent by a body")
        if f == "devex" and y == "2015":
            notes.append("FY2015 accounts are an image-only scan: the allocation column is OCR-read (the printed "
                         "grand total differs from its lines by RM60,000)")
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
        for r in used:
            cv |= set(w.caveats_for(r)) - {"CV22"}
        row["caveats"] = ";".join(sorted(cv))
        if val.get("estimate_original_pkkp") == 0 and val.get("estimate_revised_pkkp"):
            notes.append("the accounts print no original estimate (the vote was created during the year)")
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
    bt = defaultdict(Decimal)
    for r in w.obs:
        fl = FLOW.get(r["indicator_code"])
        if fl and r["edition_id"].startswith("anggaran:") and r["basis"] == "budget_estimate" \
                and chosen.get(r["period_code"]) == book_year(r):
            bt[(fl, r["period_code"])] += Decimal(r["value"])
    vb = defaultdict(Decimal)
    for r in out:
        if r["estimate_original_book"]:
            vb[(r["flow"], r["year"])] += Decimal(r["estimate_original_book"])
    bad = [f"{k}: {vb[k]} vs {bt[k]}" for k in bt if vb[k] != bt[k]]
    add("V7 each year's book-estimate column adds up to one book's votes", "core/gap_budget_vs_actual.csv",
        "PASS" if not bad else "FAIL", ", ".join(f"{y} from book {b}" for y, b in sorted(chosen.items()))
        + (f"; {bad}" if bad else ""))
    hz = Decimal(sum(Decimal(h[5]) for h in hidden))
    add("V8 book reprints filed under a body without its own vote that year, not shown (INFO)",
        "core/gap_budget_vs_actual.csv", "INFO", f"{len(hidden)} reprints, RM{fmt(hz)}: " +
        "; ".join(f"{h[0]} {h[2]} {h[3]} ({h[4].split(':')[1]}) {h[5]}" for h in hidden if Decimal(h[5])) +
        " (the rest are zeros)")
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
