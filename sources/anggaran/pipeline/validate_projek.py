#!/usr/bin/env python3
"""Check the development project lists (fact_anggaran_projek_<year>.csv) against themselves, the book's summary
and the audited accounts.

  python3 sources/anggaran/pipeline/validate_projek.py -> sources/anggaran/data/_validation_projek.csv

Declared before the results were looked at (2026-11-06). Runs offline on the committed CSVs.
  J1 programme  the projects under a programme heading add up to its printed subtotal ('Jumlah ...'), every column
  J2 vote       the projects of a vote add up to its printed JUMLAH ANGGARAN PERBELANJAAN PEMBANGUNAN, every column
                Both are exact. A difference no larger than the sen rounding of the rows summed (RM0.50 per printed
                row: each row and the total are rounded to the ringgit from sen) is the book's own rounding: it is
                registered in data/_source_anomalies_projek.csv and the row reads SOURCE_ANOMALY, kept as printed.
                Any other difference is a FAIL. (Amended after the first run, which allowed RM1 only: P.43 in the
                2025 book is RM2 off the sum of its 33 rows, inside their rounding of RM16.50.)
  J3 anchor     each vote's JUMLAH, columns (6) cara langsung and (7) pinjaman, equals the book's own summary
                (fact_anggaran_maksud_<year>.csv, anggaran_<year>, components cara_langsung and pinjaman), exact
  J4 coverage   every development vote the summary gives an allocation for the year has a project table; a vote
                without one (P.70, the contingency reserve) is named
  J5 accounts   INFO, never a pass or fail: the book's column (4), actual spending two years before, for each project
                beside the audited PKKP figure for that project and year (sources/pkkp/data/<year>/
                fact_devex_project.csv, sebenar_jumlah_rm), joined on vote and project code. Counts of equal / within
                RM1 / different / not in PKKP; the book lists only projects carried into the budget year, so its
                column (4) is not the vote's whole spending (also compared, against the summary's sebenar).
  J6 tabled     INFO: book y's allocation for y (columns 6 + 7) beside PKKP FY y's recorded allocation, per project
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SRC))
OUT = os.path.join(SRC, "data", "_validation_projek.csv")
ANOM = os.path.join(SRC, "data", "_source_anomalies_projek.csv")
COLS = ["jumlah_anggaran_harga_projek", "sebenar_prev2", "anggaran_dipinda_prev1", "anggaran_langsung",
        "anggaran_pinjaman"]
FIELDS = ["check", "book_year", "scope", "column", "printed", "computed", "difference", "status", "note"]
ANOM_FIELDS = ["anomaly_id", "book_year", "maksud_code", "scope", "column", "printed", "sum_of_rows", "difference",
               "pdf_page", "printed_page", "explanation"]
YEARS = ["2024", "2025", "2026"]


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    out, anoms = [], []

    def add(check, y, scope, col, printed, computed, ok, note="", anomaly=None):
        diff = None if printed is None or computed is None else int(printed) - int(computed)
        st = "PASS" if ok else ("SOURCE_ANOMALY" if anomaly else "FAIL")
        if anomaly:
            aid = f"PJ{len(anoms) + 1}"
            anoms.append(dict(anomaly_id=aid, book_year=y, difference=diff, printed=printed, sum_of_rows=computed,
                              column=col, **anomaly))
            note = f"{aid}: {note}".strip(": ")
        out.append(dict(check=check, book_year=y, scope=scope, column=col, printed="" if printed is None else printed,
                        computed="" if computed is None else computed, difference="" if diff is None else diff,
                        status=st, note=note))

    for y in YEARS:
        pr = rows(os.path.join(SRC, "data", y, f"fact_anggaran_projek_{y}.csv"))
        # J1, J2
        acc, prog, vacc = [0] * 5, None, defaultdict(lambda: [0] * 5)
        pacc = defaultdict(lambda: [0] * 5)  # printed subtotals + projects outside any programme, per vote
        nrows, run = defaultdict(int), 0  # (check, scope) -> number of project rows the total sums
        for r in pr:
            if r["row_type"] == "project":
                nrows[("J2", r["maksud_code"])] += 1
                run += 1
            elif r["row_type"] == "jumlah_program":
                nrows[("J1", f"{r['maksud_code']} {r['projek_name_bm']}")] = run
                run = 0
            else:
                run = 0
        for r in pr:
            if r["row_type"] == "jumlah_program" or (r["row_type"] == "project" and not r["program_bm"]):
                for i, c in enumerate(COLS):
                    pacc[r["maksud_code"]][i] += int(r[c])
        n1 = n2 = 0
        for r in pr:
            if r["row_type"] == "project":
                if r["program_bm"] != prog:
                    acc, prog = [0] * 5, r["program_bm"]
                for i, c in enumerate(COLS):
                    acc[i] += int(r[c])
                    vacc[r["maksud_code"]][i] += int(r[c])
                continue
            check, scope, got = ("J1", f"{r['maksud_code']} {r['projek_name_bm']}", acc) if \
                r["row_type"] == "jumlah_program" else ("J2", r["maksud_code"], vacc[r["maksud_code"]])
            for i, c in enumerate(COLS):
                p, s = int(r[c]), got[i]
                if p == s:
                    continue
                anomaly = None
                if check == "J2" and p == pacc[r["maksud_code"]][i] and p != s:
                    anomaly = dict(maksud_code=r["maksud_code"], scope=scope, pdf_page=r["pdf_page"],
                                   printed_page=r["printed_page"],
                                   explanation="the vote total adds the printed programme subtotals (each rounded "
                                               "to the ringgit), which differ from their rows by RM1 each (listed "
                                               "above); the total equals those subtotals plus the projects outside "
                                               "any programme exactly")
                elif abs(p - s) * 2 <= nrows[(check, scope)]:
                    anomaly = dict(maksud_code=r["maksud_code"], scope=scope, pdf_page=r["pdf_page"],
                                   printed_page=r["printed_page"],
                                   explanation=f"the printed total differs from the sum of its {nrows[(check, scope)]} "
                                               f"printed rows by RM{abs(p - s)}, within their sen rounding (RM0.50 a "
                                               "row): the rows and the total are each rounded to the ringgit from sen")
                add(check, y, scope, c, p, s, False, "printed total vs sum of its rows", anomaly)
            if r["row_type"] == "jumlah_program":
                n1 += 1
                acc, prog = [0] * 5, None
            else:
                n2 += 1
        bad1 = sum(1 for o in out if o["book_year"] == y and o["check"] == "J1")
        bad2 = sum(1 for o in out if o["book_year"] == y and o["check"] == "J2")
        add("J1", y, f"{n1} programme subtotals", "all", None, None, True,
            f"{n1 * 5 - bad1} of {n1 * 5} subtotal cells equal the sum of their rows; the rest are listed above")
        add("J2", y, f"{n2} vote totals", "all", None, None, True,
            f"{n2 * 5 - bad2} of {n2 * 5} vote-total cells equal the sum of their rows; the rest are listed above")
        # J3, J4
        summ = defaultdict(dict)
        for r in rows(os.path.join(SRC, "data", y, f"fact_anggaran_maksud_{y}.csv")):
            if r["maksud_code"].startswith("P."):
                summ[r["maksud_code"]][(r["component"], r["measure"])] = int(r["amount_rm"])
        tot = {r["maksud_code"]: r for r in pr if r["row_type"] == "jumlah_maksud"}
        for v in sorted(summ):
            alloc = summ[v].get(("pembangunan", f"anggaran_{y}"), 0)
            if v not in tot:
                add("J4", y, v, "", None, None, alloc == 0 or v == "P.70",
                    f"no project table; the summary allocates RM{alloc:,}"
                    + (" (the contingency reserve, Simpanan Luar Jangka: no projects)" if v == "P.70" else ""))
                continue
            for comp, col in (("cara_langsung", "anggaran_langsung"), ("pinjaman", "anggaran_pinjaman")):
                s = summ[v].get((comp, f"anggaran_{y}"))
                note = f"summary {comp} anggaran_{y}"
                if s is None and comp == "pinjaman":
                    s, note = 0, "the summary prints no pinjaman line for this vote: nil"
                if s is None and comp == "cara_langsung" and ("pembangunan", f"anggaran_{y}") in summ[v]:
                    s, note = summ[v][("pembangunan", f"anggaran_{y}")], "the summary prints one line for this vote"
                add("J3", y, v, col, int(tot[v][col]), s, s is not None and int(tot[v][col]) == s, note)
            s = summ[v].get(("pembangunan", f"sebenar_{int(y) - 2}"))
            if s is not None:
                out.append(dict(check="J5", book_year=y, scope=v, column="sebenar_prev2", printed=tot[v]["sebenar_prev2"],
                                computed=s, difference=int(tot[v]["sebenar_prev2"]) - s, status="INFO",
                                note=f"project list's column (4) total vs the summary's sebenar_{int(y) - 2} (the "
                                     "vote's whole spending, incl. projects not carried into the budget year)"))
        for v in sorted(set(tot) - set(summ)):
            add("J4", y, v, "", None, None, False, "a project table for a vote the summary does not print")
        # J5 against PKKP, project by project
        py = str(int(y) - 2)
        pk = os.path.join(REPO, "sources", "pkkp", "data", py, "fact_devex_project.csv")
        if os.path.exists(pk):
            acc = {(r["maksud_code"], r["projek_code"]): r for r in rows(pk) if r["row_type"] == "project"}
            n = defaultdict(int)
            for r in pr:
                if r["row_type"] != "project":
                    continue
                a = acc.get((r["maksud_code"], r["projek_code"]))
                if a is None:
                    n["not_in_pkkp"] += 1
                    continue
                d = int(r["sebenar_prev2"]) - round(float(a["sebenar_jumlah_rm"] or 0))
                n["equal" if d == 0 else "within_rm1" if abs(d) <= 1 else "different"] += 1
            out.append(dict(check="J5", book_year=y, scope=f"{sum(n.values())} projects", column="sebenar_prev2",
                            printed="", computed="", difference="", status="INFO",
                            note=f"vs PKKP FY{py} fact_devex_project sebenar_jumlah_rm, joined on vote and project "
                                 f"code: {n['equal']} equal, {n['within_rm1']} within RM1, {n['different']} different, "
                                 f"{n['not_in_pkkp']} not in PKKP"))
    # J6 (INFO): the allocation as tabled (book y, columns 6+7) beside PKKP FY y's own allocation and actual
    for y in YEARS:
        pk = os.path.join(REPO, "sources", "pkkp", "data", y, "fact_devex_project.csv")
        if not os.path.exists(pk):
            continue
        acc = {(r["maksud_code"], r["projek_code"]): r for r in rows(pk) if r["row_type"] == "project"}
        n = defaultdict(int)
        for r in rows(os.path.join(SRC, "data", y, f"fact_anggaran_projek_{y}.csv")):
            if r["row_type"] != "project":
                continue
            a = acc.get((r["maksud_code"], r["projek_code"]))
            if a is None:
                n["not_in_pkkp"] += 1
                continue
            tabled = int(r["anggaran_langsung"]) + int(r["anggaran_pinjaman"])
            n["allocation_equal" if abs(tabled - round(float(a["anggaran_jumlah_rm"] or 0))) <= 1 else
              "allocation_changed"] += 1
        out.append(dict(check="J6", book_year=y, scope=f"{sum(n.values())} projects", column="anggaran",
                        printed="", computed="", difference="", status="INFO",
                        note=f"tabled allocation (columns 6+7) vs PKKP FY{y} fact_devex_project anggaran_jumlah_rm "
                             f"(the allocation the accounts record): {n['allocation_equal']} equal, "
                             f"{n['allocation_changed']} changed during the year, {n['not_in_pkkp']} not in PKKP"))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    with open(ANOM, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANOM_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(anoms)
    from collections import Counter
    print("projek:", dict(Counter((o["check"], o["status"]) for o in out)))


if __name__ == "__main__":
    main()
