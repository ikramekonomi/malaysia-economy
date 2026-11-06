#!/usr/bin/env python3
"""gap_project_budget_vs_actual (docs/DATA_MODEL.md §10): was each development project's money spent?

  python3 core/pipeline/build_gap_project_budget.py -> core/gap_project_budget_vs_actual.csv,
                                                        core/_validation_gap_pbva.csv

Method (declared 2026-11-06, before any result of this view was computed):
* Grain: federal development project (vote, project code: maksud_code, projek_code; golden rule 4) x year, FY2023-
  FY2025: the years where a Budget book held (2024-2026) and the audited accounts (PKKP FY2023-2024) meet.
* Columns, each one source as printed, never mixed:
    tabled_rm            the Budget book of that year, columns (6) cara langsung + (7) pinjaman: the allocation as
                         tabled in Parliament (sources/anggaran fact_anggaran_projek_<year>; no book for FY2023 held)
    revised_book_rm      the next year's book, column (5) Anggaran Dipinda: the allocation as revised during the year
    total_cost_book_rm   the project's total estimated cost (column 3) in the year's book, else the next one
    allocation_pkkp_rm   the audited accounts' allocation for the project (PKKP Lampiran 2 'Anggaran', jumlah)
    actual_pkkp_rm       the audited actual (PKKP 'Sebenar', jumlah)
  The book's own column (4) 'Perbelanjaan Sebenar' is not used: it counts only the parts of a project carried into
  the budget year (sources/anggaran/data/_validation_projek.csv J5), so it is not the project's spending.
* Joining: on (maksud_code, projek_code) within a year's sources. Codes are reused (P.15 00700 is GREEN FUND in the
  2024 book and a different programme in the 2025 book), so every join carries a name check on the printed names
  (lowercase, letters and digits only): same (equal), similar (one contains the other, or at least half of the
  words of the shorter name are in the longer), different. A 'different' pair is not joined: each side is its
  own row, with a note.
* Derived, by declared rules only, no rounding before the end:
    execution_rate          actual_pkkp_rm / allocation_pkkp_rm
    execution_rate_tabled   actual_pkkp_rm / tabled_rm
    unspent_rm              allocation_pkkp_rm - actual_pkkp_rm (negative = overspent)
    allocation_change_rm    allocation_pkkp_rm - tabled_rm (money moved into or out of the project during the year)
* Status words, no ranking, the thresholds of gap_budget_vs_actual: within_allocation (execution 0.90-1.00),
  underspent (< 0.90), overspent (> 1.00), not_held (a side missing), no_allocation (allocation 0 and actual 0).
* Checks: V1 each vote-year's tabled_rm adds up to that book's printed vote total (columns 6+7); V2 each vote-year's
  actual_pkkp_rm adds up to the vote's audited development spending in core (federal_gov.vote.devex, basis
  audited), within the sen rounding of its project rows; V3 every value traces to a file, page and row; V4 every
  project-year once; V5 name-check counts (INFO).
"""
import csv
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, REPO, Warehouse, fmt  # noqa: E402

YEARS = ["2023", "2024", "2025"]
LOW, HIGH = Decimal("0.90"), Decimal("1.00")
FIELDS = ["maksud_code", "projek_code", "year", "name_book", "name_pkkp", "name_check", "total_cost_book_rm",
          "tabled_rm", "revised_book_rm", "allocation_pkkp_rm", "actual_pkkp_rm", "execution_rate",
          "execution_rate_tabled", "unspent_rm", "allocation_change_rm", "status", "tabled_ref", "revised_ref",
          "pkkp_ref", "note", "release_id"]


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def name_check(a, b):
    if not a or not b:
        return ""
    na, nb = norm(a), norm(b)
    if na == nb:
        return "same"
    if na in nb or nb in na:
        return "similar"
    wa, wb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return "similar" if short and len(short & long_) * 2 >= len(short) else "different"


def book(y):
    p = os.path.join(REPO, "sources", "anggaran", "data", y, f"fact_anggaran_projek_{y}.csv")
    if not os.path.exists(p):
        return {}, {}
    proj, tot = {}, {}
    for i, r in enumerate(rows(p), start=2):
        r["_ref"] = f"sources/anggaran/data/{y}/fact_anggaran_projek_{y}.csv#row{i} (pdf p{r['pdf_page']})"
        if r["row_type"] == "project":
            proj[(r["maksud_code"], r["projek_code"])] = r
        elif r["row_type"] == "jumlah_maksud":
            tot[r["maksud_code"]] = r
    return proj, tot


def pkkp(y):
    p = os.path.join(REPO, "sources", "pkkp", "data", y, "fact_devex_project.csv")
    if not os.path.exists(p):
        return {}
    out = {}
    for i, r in enumerate(rows(p), start=2):
        if r["row_type"] == "project":
            r["_ref"] = f"sources/pkkp/data/{y}/fact_devex_project.csv#row{i} (pdf p{r['pdf_page']})"
            out[(r["maksud_code"], r["projek_code"])] = r
    return out


def dec(s):
    return None if s in (None, "") else Decimal(str(s))


def main():
    w = Warehouse()
    out, checks = [], []

    def check(name, scope, ok, note, status=None):
        checks.append({"check": name, "scope": scope, "status": status or ("PASS" if ok else "FAIL"), "note": note})

    names = defaultdict(int)
    for y in YEARS:
        tab, tab_tot = book(y)
        rev, _ = book(str(int(y) + 1))
        acc = pkkp(y)
        keys = sorted(set(tab) | set(rev) | set(acc))
        for k in keys:
            t, rv, a = tab.get(k), rev.get(k), acc.get(k)
            bname = (t or rv or {}).get("projek_name_bm", "")
            notes = []
            # the revised figure is the next book's: it must name the same project as the tabled one
            if t and rv and name_check(t["projek_name_bm"], rv["projek_name_bm"]) == "different":
                notes.append(f"the {int(y) + 1} book prints code {k[1]} for another project "
                             f"({rv['projek_name_bm']!r}): its revised figure is not used")
                rv = None
            nc = name_check(bname, a["name_bm"]) if a and (t or rv) else ""
            if nc:
                names[nc] += 1
            if nc == "different":
                # two projects under one code: one row each, never joined
                for side in ("book", "pkkp"):
                    out.append(row(y, k, t if side == "book" else None, rv if side == "book" else None,
                                   a if side == "pkkp" else None, "different", w,
                                   notes + [f"the book and the accounts print code {k[1]} for different projects "
                                            f"({bname!r} / {a['name_bm']!r}): not joined"]))
                continue
            out.append(row(y, k, t, rv, a, nc, w, notes))
        # V1
        sums = defaultdict(Decimal)
        for r in out:
            if r["year"] == y and r["tabled_rm"] != "":
                sums[r["maksud_code"]] += Decimal(r["tabled_rm"])
        for v, tr in sorted(tab_tot.items()):
            printed = Decimal(tr["anggaran_langsung"]) + Decimal(tr["anggaran_pinjaman"])
            check("V1 tabled adds up to the book's vote total", f"{v} {y}", sums[v] == printed,
                  f"rows {fmt(sums[v])}, printed {fmt(printed)}")
        # V2: against core's audited (and allocation) vote observations, read back to their PKKP vote row
        vrow = {f"sources/pkkp/data/{y}/fact_devex_maksud.csv#row{i}": r["maksud_code"] for i, r in
                enumerate(rows(os.path.join(REPO, "sources", "pkkp", "data", y, "fact_devex_maksud.csv")), start=2)} \
            if os.path.exists(os.path.join(REPO, "sources", "pkkp", "data", y, "fact_devex_maksud.csv")) else {}
        for col, basis in (("actual_pkkp_rm", "audited"), ("allocation_pkkp_rm", "allocation")):
            got, n = defaultdict(Decimal), defaultdict(int)
            for r in out:
                if r["year"] == y and r[col] != "":
                    got[r["maksud_code"]] += Decimal(r[col])
                    n[r["maksud_code"]] += 1
            vobs = defaultdict(Decimal)
            for o in w.obs:
                if o["indicator_code"] == "federal_gov.vote.devex" and o["period_code"] == y and \
                        o["basis"] == basis and o["l1_ref"] in vrow:
                    vobs[vrow[o["l1_ref"]]] += Decimal(o["value"])
            for v in sorted(got):
                if v not in vobs:
                    check(f"V2 {col} adds up to the vote's {basis} devex", f"{v} {y}", True,
                          "no vote observation in core to compare with", "INFO")
                    continue
                ok = abs(got[v] - vobs[v]) <= Decimal("0.01") * n[v]
                check(f"V2 {col} adds up to the vote's {basis} devex", f"{v} {y}", ok,
                      f"projects {fmt(got[v])}, vote {fmt(vobs[v])}", None if ok else "WARN")
    # V3, V4
    seen = defaultdict(int)
    for r in out:
        seen[(r["maksud_code"], r["projek_code"], r["year"], r["name_book"], r["name_pkkp"])] += 1
    dup = [k for k, c in seen.items() if c > 1]
    check("V4 every project-year once", "all", not dup, f"{len(dup)} duplicates")
    untraced = [r for r in out if not (r["tabled_ref"] or r["revised_ref"] or r["pkkp_ref"])]
    check("V3 every row traces to a file, page and row", "all", not untraced, f"{len(untraced)} untraced")
    check("V5 name checks (book vs accounts)", "all", True, ", ".join(f"{k} {v}" for k, v in sorted(names.items())),
          "INFO")
    for r in out:
        r["release_id"] = w.release_id
    with open(os.path.join(CORE, "gap_project_budget_vs_actual.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_pbva.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["check", "scope", "status", "note"], lineterminator="\n")
        wr.writeheader()
        wr.writerows(checks)
    from collections import Counter
    print(f"gap_project_budget_vs_actual: {len(out)} rows;", dict(Counter(r["status"] for r in out)))
    print("checks:", dict(Counter(c["status"] for c in checks)))
    for c in checks:
        if c["status"] in ("FAIL", "WARN"):
            print("  ", c)


def row(y, k, t, rv, a, nc, w, notes):
    r = {f: "" for f in FIELDS}
    r.update(maksud_code=k[0], projek_code=k[1], year=y, name_check=nc, note="; ".join(notes))
    if t:
        r.update(name_book=t["projek_name_bm"], total_cost_book_rm=t["jumlah_anggaran_harga_projek"],
                 tabled_rm=str(int(t["anggaran_langsung"]) + int(t["anggaran_pinjaman"])), tabled_ref=t["_ref"])
    if rv:
        r.update(name_book=r["name_book"] or rv["projek_name_bm"], revised_book_rm=rv["anggaran_dipinda_prev1"],
                 revised_ref=rv["_ref"])
        if not r["total_cost_book_rm"]:
            r["total_cost_book_rm"] = rv["jumlah_anggaran_harga_projek"]
    if a:
        r.update(name_pkkp=a["name_bm"], allocation_pkkp_rm=fmt(Decimal(a["anggaran_jumlah_rm"] or "0")),
                 actual_pkkp_rm=fmt(Decimal(a["sebenar_jumlah_rm"] or "0")), pkkp_ref=a["_ref"])
    al, ac, tb = dec(r["allocation_pkkp_rm"]), dec(r["actual_pkkp_rm"]), dec(r["tabled_rm"])
    if al is not None and ac is not None:
        r["unspent_rm"] = fmt(al - ac)
        if al == 0 and ac == 0:
            r["status"] = "no_allocation"
        elif al == 0:
            r["status"] = "overspent"
            r["note"] = "; ".join(x for x in (r["note"], "spent with no allocation recorded") if x)
        else:
            e = ac / al
            r["execution_rate"] = fmt(e.quantize(Decimal("0.0001")))
            r["status"] = "within_allocation" if LOW <= e <= HIGH else "underspent" if e < LOW else "overspent"
    else:
        r["status"] = "not_held"
    if tb is not None and ac is not None and tb != 0:
        r["execution_rate_tabled"] = fmt((ac / tb).quantize(Decimal("0.0001")))
    if tb is not None and al is not None:
        r["allocation_change_rm"] = fmt(al - tb)
    return r


if __name__ == "__main__":
    main()
