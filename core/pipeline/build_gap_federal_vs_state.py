#!/usr/bin/env python3
"""gap_federal_vs_state (docs/DATA_MODEL.md §10, Phase 3): do federal transfers match what states record receiving?

  python3 core/pipeline/build_gap_federal_vs_state.py -> core/gap_federal_vs_state.csv, core/_validation_gap_fed.csv

Method (declared 2026-11-05, before any result of this view was looked at):
* Two sides, each audited and each from its own publisher. Federal: core/fact_money_flow.csv (PKKP, the payer's
  accounts, D27). State: the state_gov.revenue.federal_* observations (the state's audited accounts as the Auditor
  General's state report prints them). Nothing is estimated, split or carried between years.
* Grain: transfer x place x year, FY2014-2024 (the years the state reports are held), all 13 states and the three
  Federal Territories (golden rule 11). FY2015 has no federal side (PKKP FY2015 is not loaded, F6).
* Transfers:
    capitation       federal: T.12 'capitation grant to the state governments' (paid to the states as a class,
                     E000060); state: state_gov.revenue.federal_capitation_grant
    concurrent_list  federal: B.11 'grants under the Concurrent List' (to the states as a class, E000060); state:
                     state_gov.revenue.federal_concurrent_list_grant
    named            federal: every flow paid to that state's government by name (Selangor and Kedah's annual
                     payments, Sabah and Sarawak's special grants); state: state_gov.revenue.federal_grants_total,
                     the one line where a state prints ALL its federal grants (Sabah, Sarawak)
* Comparison, by what the sources allow (never a formula split, D27):
    a class grant    the federal accounts do not say what each state got, so no state row can 'agree' or
                     'differ': the row gives the state's recorded receipt beside the federal total and its share
                     (DV2 ratio). The year's aggregate row (geo _states) tests the one thing that must hold: the
                     states that print the grant together recorded no more than the federal total.
    a named grant    the state's record of all its federal grants must be at least the grant paid to it by name:
                     consistent / inconsistent. A state that prints no total gives state_not_printed.
* Printings: a state report reprints last year's figure; every printing of the state's figure for that year (own
  volume and later volumes) is listed, and printings that disagree are flagged, both kept as printed.
* A missing state figure is 'not printed', never zero (CV26): the grants are printed only among a state's top
  revenue items. Flows are a floor (CV25). Status words, not rankings; no state is compared with another.
* Amended 2026-11-05 after the blind verifier (qa/audits/2026-11-05_phase3_gap_fed_verifier.md), before any
  conclusion was drawn from the view: a figure printed only in a LATER volume is listed but never compared
  (status printed_in_later_volume_only: two such later columns were found misaligned on the page, Kedah and Sabah
  2020); where the state's own top-revenue table for that year is registered as not parsed
  (_unparsed_tables_<state>.csv) the status is state_table_not_extracted, not state_not_printed; page-proved notes
  on single rows come from meta/gap_note.csv.
"""
import csv
import glob
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, REPO, Warehouse, fmt  # noqa: E402

YEARS = [str(y) for y in range(2014, 2025)]
STATES_DIR = os.path.join(REPO, "sources", "states", "data")
TRANSFERS = {
    "capitation": dict(fed=re.compile(r"^T\.12 \d+: capitation grant to the state governments"),
                       ind="state_gov.revenue.federal_capitation_grant",
                       code="revenue_item_federal_capitation_grant", kind="class",
                       name="federal capitation grant (Pemberian Mengikut Bilangan Penduduk)"),
    "concurrent_list": dict(fed=re.compile(r"^B\.11 \d+: grants under the Concurrent List"),
                            ind="state_gov.revenue.federal_concurrent_list_grant",
                            code="revenue_item_federal_dept_grant", kind="class",
                            name="federal grant to state departments under the Concurrent List (Senarai Bersama)"),
    "named": dict(fed=None, ind="state_gov.revenue.federal_grants_total", code="revenue_item_federal_grants_total",
                  kind="named", name="federal grants paid to the state government by name"),
}
FIELDS = ["transfer", "geo_code", "place", "year", "comparison", "status", "federal_paid_rm", "federal_recipient",
          "federal_flow_ids", "state_recorded_rm", "state_obs_id", "state_share_of_federal", "state_printings",
          "printings_agree", "states_printing", "note", "caveats", "release_id"]


def printings(code):
    """(state, year) -> every printed value of this conformed line, own volume first, from the L1 revenue tables."""
    out = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(STATES_DIR, "*", "fact_state_revenue_*.csv"))):
        with open(p, newline="", encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                if r["line_code"] != code or r["measure"] != "actual" or r["line_code_conformed"] != "yes":
                    continue
                out[(r["state"], r["fiscal_year"])].append(dict(
                    value=Decimal(r["amount_rm_conformed"]), printed=r["amount_printed"], volume=r["command_paper"],
                    jadual=r["jadual"], page=r["pdf_page"], own=r["column_role"] == "own_year",
                    ref=f"{os.path.relpath(p, REPO)}#row{i}"))
    for k in out:
        seen, uniq = set(), []
        for x in sorted(out[k], key=lambda x: (not x["own"], x["volume"], x["jadual"])):
            key = (x["volume"], x["printed"])
            if key not in seen:
                seen.add(key)
                uniq.append(x)
        out[k] = uniq
    return out


# which unparsed tables could hold a grant: the top-revenue table for a class grant; for the named comparison also
# the revenue-category table (Sabah and Sarawak print all federal grants as a category); a whole volume for any
SPECS_FOR = {"class": ("hasil_penyumbang_utama",), "named": ("hasil_penyumbang_utama", "hasil_kategori")}


def no_state_status(pr, state, y, kind, unparsed, extracted, notes):
    """Why there is no own-year state figure: printed only later, table not parsed, or not printed."""
    if pr:
        notes.append("printed only in a later volume (listed, not compared: later columns have been found "
                     "misaligned on the page)")
        return "printed_in_later_volume_only"
    whole = unparsed.get((state, y, "(whole volume)"))
    if whole:
        notes.append(f"the state's report {whole} is registered as not parsed (image-only): the grant may be "
                     "printed there")
        return "state_table_not_extracted"
    hits = [unparsed[(state, y, sp)] for sp in SPECS_FOR[kind] if (state, y, sp) in unparsed]
    # an unparsed table explains a missing figure only if no table of that kind WAS extracted for the year
    if hits and not any((state, y, sp) in extracted for sp in SPECS_FOR[kind]):
        notes.append(f"the state's table {hits[0]} is registered as not parsed: the grant may be printed there")
        return "state_table_not_extracted"
    return "state_not_printed"


def unparsed_years():
    """(state, fiscal_year, spec) -> the own-volume table that could not be parsed (registered, with the reason)."""
    out = {}
    for p in glob.glob(os.path.join(STATES_DIR, "*", "_unparsed_tables_*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ref = f"{r['source_file'][:-4]}" + (f" J{r['jadual']} p{r['pdf_page']}" if r["jadual"] else "")
                out.setdefault((r["state"], r["fiscal_year"], r["spec_id"]), ref)
    return out


def extracted_tables():
    """(state, fiscal_year, spec) for which an own-year table of that kind was extracted."""
    out = set()
    for p in glob.glob(os.path.join(STATES_DIR, "*", "fact_state_revenue_*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["column_role"] == "own_year":
                    out.add((r["state"], r["fiscal_year"], r["spec_id"]))
    return out


def gap_notes():
    with open(os.path.join(REPO, "meta", "gap_note.csv"), newline="", encoding="utf-8") as f:
        return {(r["transfer"], r["geo_code"], r["year"]): r for r in csv.DictReader(f)
                if r["view"] == "gap_federal_vs_state"}


def main():
    w = Warehouse()
    unparsed, notes_reg, extracted = unparsed_years(), gap_notes(), extracted_tables()
    places = sorted(c for c, g in w.geo.items() if g["geo_level"] == "state")
    gov = {}                                  # geo -> state government entity
    for c in w.entity_codes:
        if c["code_system"] == "state_gov":
            gov[c["code"]] = c["entity_id"]
    state_name = {c: w.geo[c]["name_bm"] for c in places}
    iso_by_name = {}
    for c in places:
        iso_by_name[w.geo[c]["name_bm"]] = c
    flows_by = defaultdict(list)              # (transfer, year) -> flows to the class
    named_by = defaultdict(list)              # (geo, year) -> flows to that government by name
    for f in w.flows:
        for t, spec in TRANSFERS.items():
            if spec["fed"] is not None and spec["fed"].match(f["purpose"]) and f["to_entity_id"] == "E000060":
                flows_by[(t, f["period_code"])].append(f)
        for g, eid in gov.items():
            if f["to_entity_id"] == eid:
                named_by[(g, f["period_code"])].append(f)
    fed_years = {f["period_code"] for f in w.flows}
    named_states = {g for g, _ in named_by}
    out, checks = [], []
    for t, spec in TRANSFERS.items():
        prints = printings(spec["code"])
        for y in YEARS:
            agg_sum, agg_n, agg_ids = Decimal(0), 0, []
            fl = flows_by.get((t, y), []) if spec["kind"] == "class" else None
            fed_class = sum(Decimal(f["amount"]) for f in fl) if fl else None
            for g in places:
                if spec["kind"] == "named" and g not in named_states:
                    continue                      # no grant to this government by name in any year
                row = {k: "" for k in FIELDS}
                row.update(transfer=t, geo_code=g, place=state_name[g], year=y, release_id=w.release_id)
                cv = {"CV25", "CV26"}
                notes = []
                if g in ("MY-14", "MY-15", "MY-16"):
                    row.update(comparison="not_applicable", status="no_state_government")
                    row["note"] = ("a Federal Territory has no state government; the territories' administrations' "
                                   "grants are in get_flows (to=MY-14/15/16), their own accounts are not held")
                    row["caveats"] = "CV4"
                    out.append(row)
                    continue
                obs = w.get(spec["ind"], g, y, basis="audited")
                pr = prints.get((state_name[g], y), [])
                if pr:
                    row["state_printings"] = "; ".join(
                        f"{x['printed']} ({x['volume']} J{x['jadual']} p{x['page']}"
                        f"{', own volume' if x['own'] else ''})" for x in pr)
                    vals = [x["value"] for x in pr]
                    spread = max(vals) - min(vals)
                    # RM juta to 2 dp: a 0.01 difference between two volumes is the last digit's rounding
                    row["printings_agree"] = ("true" if spread == 0 else
                                              "rounding" if spread <= Decimal(10000) else "false")
                    if row["printings_agree"] == "false":
                        notes.append("the state's reports print different figures for this year; both kept as "
                                     "printed, the own-year volume's figure is used")
                    elif row["printings_agree"] == "rounding":
                        notes.append("two of the state's reports differ by RM0.01 juta (rounding of the last digit)")
                if obs:
                    row["state_recorded_rm"], row["state_obs_id"] = obs["value"], obs["obs_id"]
                    cv |= set(w.caveats_for(obs))
                if spec["kind"] == "class":
                    row["comparison"] = "share_of_class_total"
                    row["federal_recipient"] = "the state governments as a class (E000060), not split by state"
                    if fl:
                        row["federal_paid_rm"] = fmt(fed_class)
                        row["federal_flow_ids"] = ";".join(f["flow_id"] for f in fl)
                    if y not in fed_years:
                        row["status"] = "federal_not_held"
                        notes.append(f"PKKP FY{y} is not loaded (the image-only scan), so the federal side is "
                                     "not held")
                        if obs:
                            agg_n += 1                # the state still printed it: counted, not compared
                    elif not obs:
                        row["status"] = no_state_status(pr, state_name[g], y, spec["kind"], unparsed, extracted, notes)
                    else:
                        row["status"] = "share"
                        row["state_share_of_federal"] = fmt(Decimal(obs["value"]) / fed_class, 4)
                        agg_sum += Decimal(obs["value"])
                        agg_n += 1
                        agg_ids.append(obs["obs_id"])
                else:
                    nf = named_by.get((g, y), [])
                    if not nf and y in fed_years:
                        continue                  # no grant to this state by name: nothing to compare
                    row["comparison"] = "state_total_at_least_named"
                    row["federal_recipient"] = f"the {state_name[g]} state government by name ({gov.get(g, '')})"
                    if nf:
                        row["federal_paid_rm"] = fmt(sum(Decimal(f["amount"]) for f in nf))
                        row["federal_flow_ids"] = ";".join(f["flow_id"] for f in nf)
                    if y not in fed_years:
                        row["status"] = "federal_not_held"
                    elif not obs:
                        row["status"] = no_state_status(pr, state_name[g], y, spec["kind"], unparsed, extracted, notes)
                        if row["status"] == "state_not_printed":
                            notes.append("the state prints no line for all its federal grants in this year")
                    else:
                        ok = Decimal(obs["value"]) >= Decimal(row["federal_paid_rm"])
                        row["status"] = "consistent" if ok else "inconsistent"
                        notes.append("the state's record of all its federal grants is "
                                     + ("at least" if ok else "LESS than") + " the grants paid to it by name"
                                     + (" (it also receives class grants, so it should be more)" if ok else ""))
                reg = notes_reg.get((t, g, y))
                if reg:
                    notes.append(f"{reg['note']} [{reg['proof']}]")
                row["note"] = "; ".join(notes)
                row["caveats"] = ";".join(sorted(cv))
                out.append(row)
            if spec["kind"] == "class":
                agg = {k: "" for k in FIELDS}
                agg.update(transfer=t, geo_code="_states", place="the states that print it", year=y,
                           comparison="sum_at_most_class_total", release_id=w.release_id, caveats="CV25;CV26",
                           federal_recipient="the state governments as a class (E000060)",
                           states_printing=str(agg_n), state_obs_id=";".join(agg_ids))
                if fl:
                    agg["federal_paid_rm"] = fmt(fed_class)
                    agg["federal_flow_ids"] = ";".join(f["flow_id"] for f in fl)
                if y not in fed_years:
                    agg["status"] = "federal_not_held"
                    agg["note"] = f"{agg_n} of 13 states print this grant; the federal side is not held for FY{y}"
                elif not agg_n:
                    agg["status"] = "state_not_printed"
                else:
                    agg["state_recorded_rm"] = fmt(agg_sum)
                    agg["state_share_of_federal"] = fmt(agg_sum / fed_class, 4)
                    agg["status"] = "consistent" if agg_sum <= fed_class else "inconsistent"
                    agg["note"] = (f"{agg_n} of 13 states print this grant; together they recorded "
                                   f"{fmt(agg_sum / fed_class * 100, 1)}% of the federal total")
                out.append(agg)
                checks.append([f"GF2 {t}: the printing states' receipts are at most the federal class total", y,
                               "INFO" if agg["status"] in ("consistent", "inconsistent", "state_not_printed",
                                                           "federal_not_held") else "FAIL",
                               f"{agg['status']}: {agg_n} states, recorded {agg.get('state_recorded_rm') or '-'} "
                               f"vs federal {agg.get('federal_paid_rm') or '-'}"])
    # checks
    for t in TRANSFERS:
        if TRANSFERS[t]["kind"] != "class":
            continue
        n = {y: len({r["geo_code"] for r in out if r["transfer"] == t and r["year"] == y and r["geo_code"] != "_states"})
             for y in YEARS}
        checks.append([f"GF1 {t}: every state and territory present", "all",
                       "PASS" if set(n.values()) == {16} else "FAIL", str(n)])
    untraced = [r for r in out if (r["state_recorded_rm"] and not r["state_obs_id"])
                or (r["federal_paid_rm"] and not r["federal_flow_ids"])]
    checks.append(["GF3 every figure traces to an observation or a flow", "all", "PASS" if not untraced else "FAIL",
                   f"{len(untraced)} untraced"])
    bad = [f"{r['transfer']} {r['geo_code']} {r['year']}" for r in out if r["status"] == "inconsistent"]
    checks.append(["GF4 rows where the two sides cannot both be right (status inconsistent)", "all", "INFO",
                   f"{len(bad)}" + (f": {bad}" if bad else "")])
    dis = [f"{r['transfer']} {r['geo_code']} {r['year']}" for r in out if r["printings_agree"] == "false"]
    checks.append(["GF5 state figures printed differently in two of the state's own reports", "all", "INFO",
                   f"{len(dis)}" + (f": {dis}" if dis else "")])
    ft = [r for r in out if r["geo_code"] in ("MY-14", "MY-15", "MY-16") and r["state_recorded_rm"]]
    checks.append(["GF6 no state-government figure for a Federal Territory", "all", "PASS" if not ft else "FAIL",
                   f"{len(ft)}"])
    with open(os.path.join(CORE, "gap_federal_vs_state.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    with open(os.path.join(CORE, "_validation_gap_fed.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["check", "scope", "status", "note"])
        wr.writerows(checks)
    from collections import Counter
    st = Counter((r["transfer"], r["status"]) for r in out)
    print(f"gap_federal_vs_state: {len(out)} rows; " + ", ".join(f"{t}/{s} {n}" for (t, s), n in sorted(st.items())))
    if any(c[2] == "FAIL" for c in checks):
        for c in checks:
            if c[2] == "FAIL":
                print(" ", c)
        sys.exit(1)


if __name__ == "__main__":
    main()
