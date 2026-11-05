#!/usr/bin/env python3
"""Where federal spending lands, by state (Phase 3, DATA_MODEL §10 and §13 track A): what can be placed, and how much.

  python3 core/pipeline/build_federal_placement.py
    -> core/fact_placement.csv            one row per audited development project per year, with its place
    -> core/gap_federal_placement.csv     state x year: federal money placed in the state, and the year's placed_share
    -> core/_validation_placement.csv     checks P1-P6

Method (declared 2026-11-05, before any result by state was computed; committed on its own before the code. Only
the national share of development spending whose project name contains a state name, by year, was looked at
while scoping: 3-15%):

* Scope: federal spending as audited in PKKP, each year from its own volume (golden rule 6), FY2009-2024 except
  FY2015 (an image-only scan: its project leaves are OCR-provisional; CLAUDE.md). The denominator is the year's
  federal total spending as gap_need_vs_money uses it: opex + gross devex + the COVID-19 Fund (2020-2022).
* What is placed, and how (geo_method), in this order; nothing else:
  1. `stated_state`: a development project (PKKP Penyata Perbelanjaan Pembangunan, project leaf rows, its actual
     spending `sebenar_jumlah_rm`) whose printed name names exactly one state or Federal Territory.
  2. `parsed_district`: a project whose name names no state but one or more districts, all of one state (DOSM
     2020 districts in core/dim_geo.csv), matched as whole words; district names that are also common words or
     compass phrases are not used (STOP_DISTRICTS, declared below), nor a district inside a regional name
     (Lembah Klang). [Amended 2026-11-05: "exactly one district" read "districts of one state", as the code
     always did; verifier finding 7.]
  2a. `parsed_place` [added 2026-11-05 after the blind verifier, finding 1-4]: no state named, but a town,
     region, island or street, or an abbreviation of a state, listed with its proof in meta/place_gazetteer.csv
     (Iskandar, Cyberjaya, Ipoh, Kangar, P.Pinang, ...). Place names that only describe where something is NOT
     (`di luar Kuala Lumpur`, outside KL) are removed before matching.
  3. `grant_by_name`: a federal grant whose recipient is a named state government or territory administration
     (core/fact_money_flow.csv, geo_method `stated`); the class grants (all states, all local authorities)
     are never split (D27).
  A project naming two or more states (or a state and another state's district or place) is `multiple_states`
  and is not placed; a project naming the Peninsula and no state (`Semenanjung`: PKKP splits some programmes
  into Peninsula / Sabah / Sarawak lines) is `peninsula` [added 2026-11-05, finding 5] and is not placed, so the
  view reports it beside the Sabah and Sarawak lines that are; a project naming none is `none`. All stay
  `_unallocated` with their totals shown. A year with no flows held (FY2009) reports grants by name as not held,
  not zero [finding 6].
* Not used, by design: an agency's seat (it would put ministries' headquarters spending in Putrajaya), any
  allocation key (population, staff counts, need): placing money by formula makes a map look more complete than
  the accounts are (D27, DATA_MODEL §13). Operating spending (salaries in schools and clinics, subsidies, cash
  transfers: most of the money) has no place in the federal accounts and is not placed here; the sources that
  could place it (KKM/KPM by state, STR/JKM by state, registry `social_transfers_by_state`) are not held.
* A place in a project name says where the project is, not who benefits; a statewide or cross-border project is
  placed in the state it names. geo_confidence: `medium` for stated_state and grant_by_name, `low` for
  parsed_district.
* Output: every state and Federal Territory (all 16, golden rule 11) x every year, plus an `_unallocated` row and
  an `MY` row per year. placed_share = placed RM in all states / federal total RM, reported on every row; the
  per-state amounts are published only where placed_share is at least 60% (DATA_MODEL §10 guard), otherwise the
  row says why. No ranking.
* Checks: P1 project leaves add up to each volume's printed development total; P2 every project row is placed by
  exactly one method and the methods add up to the leaf total; P3 a stated or parsed place cites the words
  matched; P4 grants by name equal fact_money_flow's stated flows; P5 the 16 places + `_unallocated` = the MY
  row; P6 placed_share in [0, 1].
"""
import csv
import hashlib
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, REPO, Warehouse, fmt  # noqa: E402

META = os.path.join(REPO, "meta")
YEARS = [str(y) for y in range(2009, 2025) if y != 2015]
PLACED_MIN = Decimal("0.60")
PLACED = ("stated_state", "parsed_district", "parsed_place")
# declared with the method, before the first run: names of a place that do not say the project is there
EXCLUDE_PHRASES = ["selat melaka", "lembah klang", "antarabangsa kuala lumpur", "klia",
                   # added 2026-11-05 (verifier finding 4): "outside Kuala Lumpur" names where a project is not
                   "di luar kuala lumpur", "di luar kl"]
# district names that are also common words or compass phrases (DOSM 2020 districts)
STOP_DISTRICTS = {"pekan", "bau", "song", "sik", "yan", "pakan", "pusa", "gedong", "selama", "matu", "daro", "dalat",
                  "lingga", "betong", "bera", "barat daya", "timur laut", "kabong", "pantu", "bandar baharu"}
STATE_ALIASES = {"MY-07": ["pulau pinang", "penang"], "MY-05": ["negeri sembilan", "n. sembilan", "n.sembilan"],
                 "MY-04": ["melaka", "malacca"], "MY-14": ["kuala lumpur"], "MY-15": ["labuan"],
                 "MY-16": ["putrajaya"]}
FIELDS_FACT = ["placement_id", "period_code", "entity_id", "maksud_code", "projek_code", "name_bm", "amount",
               "geo_code", "geo_method", "geo_confidence", "geo_evidence", "basis", "edition_id", "file_id",
               "pdf_page", "printed_page", "l1_ref"]
FIELDS_GAP = ["geo_code", "name", "year", "projects_stated_rm", "projects_parsed_rm", "grants_by_name_rm",
              "placed_rm", "projects_multiple_states_rm", "projects_peninsula_rm", "projects_none_rm", "not_itemised_rm",
              "federal_total_rm", "devex_projects_total_rm", "placed_share", "publishable", "note",
              "caveats", "federal_source_obs_ids", "release_id"]


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, fields, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(data)


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def matcher(w):
    """(code, phrase, kind) for every state name and usable district name, longest phrase first."""
    out = []
    for code, g in w.geo.items():
        if g["geo_level"] == "state":
            names = {norm(re.sub(r"^W\.P\. ", "", g["name_bm"]))} | set(STATE_ALIASES.get(code, []))
            out += [(code, n, "state") for n in names]
        elif g["geo_level"] == "district" and g["parent_geo_code"].startswith("MY-"):
            n = norm(re.sub(r"^W\.P\. ", "", g["name_bm"]))
            if n not in STOP_DISTRICTS:
                out.append((g["parent_geo_code"], n, "district"))
    for r in rows(os.path.join(META, "place_gazetteer.csv")):
        out.append((r["geo_code"], norm(r["phrase"]), "state" if r["kind"] == "alias" else "place"))
    return sorted(out, key=lambda t: -len(t[1]))


def place(name, pats):
    """-> (geo_code, geo_method, evidence). A phrase is matched as whole words; a longer phrase consumes its
    words so a district inside a state's name (Kuala Terengganu) or a state inside a district's (Hilir Perak) is
    read once, as the longer phrase."""
    text = " " + re.sub(r"[^\w.]+", " ", norm(name)) + " "
    for p in EXCLUDE_PHRASES:
        text = text.replace(f" {p} ", " ")
    hits = []
    for code, ph, kind in pats:
        rx = r"(?<![\w.])" + re.escape(ph) + r"(?![\w])"
        if re.search(rx, text):
            hits.append((code, ph, kind))
            text = re.sub(rx, " ", text)
    states = {c for c, _, k in hits if k == "state"}
    dists = {c for c, _, k in hits if k == "district"}
    places = {c for c, _, k in hits if k == "place"}
    ev = "; ".join(sorted(f"{k} '{p}'={c}" for c, p, k in hits))
    if len(states | dists | places) > 1:
        return "_unallocated", "multiple_states", ev
    if states:
        return states.pop(), "stated_state", ev
    if dists:
        return dists.pop(), "parsed_district", ev
    if places:
        return places.pop(), "parsed_place", ev
    if re.search(r"(?<!\w)semenanjung(?!\w)", text):
        return "_unallocated", "peninsula", "region 'semenanjung'"
    return "_unallocated", "none", ""


def main():
    w = Warehouse()
    pats = matcher(w)
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    bridge = [c for c in rows(os.path.join(CORE, "bridge_entity_code.csv")) if c["code_system"] == "maksud_pembangunan"
              and not c.get("scope")]

    def entity(code, y):
        hit = [c["entity_id"] for c in bridge if c["code"] == code and (not c["valid_from"] or int(c["valid_from"]) <= y)
               and (not c["valid_to"] or y <= int(c["valid_to"]))]
        return hit[0] if len(hit) == 1 else ""

    fact, checks = [], []

    def add(check, scope, status, detail):
        checks.append(dict(check=check, scope=scope, status=status, detail=detail))

    printed_total, leaf_total, gap = {}, {}, []
    for y in YEARS:
        p = os.path.join(REPO, "sources", "pkkp", "data", y, "fact_devex_project.csv")
        for i, r in enumerate(rows(p), start=2):
            if r["row_type"] == "grand_total":
                printed_total[y] = Decimal(r["sebenar_jumlah_rm"] or "0")
            if r["row_type"] != "project":
                continue
            geo, method, ev = place(r["name_bm"], pats)
            ref = f"sources/pkkp/data/{y}/fact_devex_project.csv#row{i}"
            fact.append(dict(placement_id="p" + hashlib.sha1(ref.encode()).hexdigest()[:12], period_code=y,
                             entity_id=entity(r["maksud_code"], int(y)), maksud_code=r["maksud_code"],
                             projek_code=r["projek_code"], name_bm=r["name_bm"], amount=r["sebenar_jumlah_rm"] or "0",
                             geo_code=geo, geo_method=method,
                             geo_confidence={"stated_state": "medium", "parsed_district": "low",
                                             "parsed_place": "low"}.get(method, "none"),
                             geo_evidence=ev, basis="audited", edition_id=f"pkkp:{r['source_file']}",
                             file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"],
                             printed_page=r["printed_page"], l1_ref=ref))
        leaf_total[y] = sum(Decimal(f["amount"]) for f in fact if f["period_code"] == y)

    # P1 leaves add up to the printed development total (FY2009: a known shortfall, shown as not itemised)
    bad1 = {y: printed_total[y] - leaf_total[y] for y in YEARS if abs(printed_total[y] - leaf_total[y]) > Decimal("0.05")}
    add("P1 project leaves add up to each volume's printed development total", "sources/pkkp fact_devex_project",
        "PASS" if not bad1 else ("WARN" if set(bad1) == {"2009"} else "FAIL"),
        f"{len(YEARS)} years" + (f"; short: {', '.join(f'{y} {fmt(d)}' for y, d in bad1.items())} (FY2009 aligns 1266 of "
                                 "1412 project rows in its own validation; the difference is not itemised and not placed)"
                                 if bad1 else ""))
    # P2/P3
    methods = {"stated_state", "parsed_district", "parsed_place", "multiple_states", "peninsula", "none"}
    bad2 = [f["l1_ref"] for f in fact if f["geo_method"] not in methods or
            (f["geo_method"] in PLACED) != f["geo_code"].startswith("MY-")]
    add("P2 every project row is placed by exactly one method", "core/fact_placement.csv",
        "PASS" if not bad2 else "FAIL", f"{len(fact)} rows" + (f"; {bad2[:5]}" if bad2 else ""))
    bad3 = [f["l1_ref"] for f in fact if f["geo_method"] != "none" and not f["geo_evidence"]]
    add("P3 a stated or parsed place cites the words matched", "core/fact_placement.csv",
        "PASS" if not bad3 else "FAIL", "ok" if not bad3 else str(bad3[:5]))

    flows = [f for f in rows(os.path.join(CORE, "fact_money_flow.csv")) if f["is_leaf"] == "true"]
    grants = defaultdict(Decimal)
    for f in flows:
        if f["geo_method"] == "stated" and f["geo_code"].startswith("MY-") and f["period_code"] in YEARS:
            grants[(f["geo_code"], f["period_code"])] += Decimal(f["amount"])
    n_stated = sum(1 for f in flows if f["geo_method"] == "stated" and f["period_code"] in YEARS)
    flow_years = {f["period_code"] for f in flows}

    states = sorted(c for c, g in w.geo.items() if g["geo_level"] == "state")
    fed = {}
    for y in YEARS:
        parts = [w.get(i, "MY", y, basis="audited") for i in
                 ("federal_gov.expenditure.opex", "federal_gov.expenditure.devex", "federal_gov.expenditure.covid_fund")]
        if parts[0] and parts[1]:
            have = [p for p in parts if p]
            fed[y] = (sum(Decimal(p["value"]) for p in have), ";".join(p["obs_id"] for p in have))
    bad5, bad6 = [], []
    for y in YEARS:
        fy = [f for f in fact if f["period_code"] == y]
        by = defaultdict(lambda: defaultdict(Decimal))
        for f in fy:
            by[f["geo_code"]][f["geo_method"]] += Decimal(f["amount"])
        total, ids = fed.get(y, (None, ""))
        placed_all = sum(sum(by[g][m] for m in PLACED) + grants[(g, y)] for g in states)
        share = (placed_all / total) if total else None
        pub = share is not None and share >= PLACED_MIN
        note = "" if pub else (f"amounts by state are kept here for verification and withheld by the tools and from "
                               f"publication: only {float(share):.1%} of federal spending in {y} can be placed by state "
                               "(projects whose name names one place, and grants to a named state government or "
                               "territory administration), so a state's amount is a floor of what the federal accounts "
                               "place there, not what it received; salaries, subsidies, cash transfers and most projects "
                               "have no place in the federal accounts. Guard: 60%." if share is not None
                               else "federal total not held")
        if y not in flow_years:
            note += f" Grants by name: no flows held for FY{y} (not zero)."
        nonitem = printed_total[y] - leaf_total[y] if y in bad1 else Decimal(0)
        yr_rows = []
        for g in states + ["_unallocated", "MY"]:
            if g in states:
                st, pa, gr = by[g]["stated_state"], by[g]["parsed_district"] + by[g]["parsed_place"], grants[(g, y)]
                multi = pen = none = ni = Decimal(0)
            elif g == "_unallocated":
                st = pa = gr = Decimal(0)
                multi, pen, none, ni = by[g]["multiple_states"], by[g]["peninsula"], by[g]["none"], nonitem
            else:
                st = sum(by[s]["stated_state"] for s in states)
                pa = sum(by[s]["parsed_district"] + by[s]["parsed_place"] for s in states)
                gr = sum(grants[(s, y)] for s in states)
                u = by["_unallocated"]
                multi, pen, none, ni = u["multiple_states"], u["peninsula"], u["none"], nonitem
            yr_rows.append(dict(geo_code=g, name=w.geo.get(g, {}).get("name_bm", "") if g != "_unallocated" else
                                "not placed", year=y, projects_stated_rm=fmt(st), projects_parsed_rm=fmt(pa),
                                grants_by_name_rm=fmt(gr) if y in flow_years else "", placed_rm=fmt(st + pa + gr),
                                projects_multiple_states_rm=fmt(multi), projects_peninsula_rm=fmt(pen),
                                projects_none_rm=fmt(none),
                                not_itemised_rm=fmt(ni), federal_total_rm=fmt(total) if total else "",
                                devex_projects_total_rm=fmt(leaf_total[y]),
                                placed_share=fmt(share, 4) if share is not None else "", publishable=str(pub).lower(),
                                note=note, caveats="CV27", federal_source_obs_ids=ids, release_id=w.release_id))
        # P5: 16 places + not placed (projects) = the MY row's project total
        s_proj = sum(sum(by[g][m] for m in PLACED) for g in states) + sum(by["_unallocated"].values())
        if abs(s_proj - leaf_total[y]) > Decimal("0.01"):
            bad5.append(y)
        if share is not None and not (0 <= share <= 1):
            bad6.append(y)
        gap += yr_rows
    g_sum = sum(Decimal(r["grants_by_name_rm"] or "0") for r in gap if r["geo_code"] in states)
    g_ref = sum(Decimal(f["amount"]) for f in flows if f["geo_method"] == "stated" and f["period_code"] in YEARS)
    add("P4 grants by name equal fact_money_flow's stated flows", "core/fact_money_flow.csv",
        "PASS" if g_sum == g_ref else "FAIL", f"{n_stated} flows, {fmt(g_ref)}" + ("" if g_sum == g_ref else f" vs {fmt(g_sum)}"))
    add("P5 the 16 places + not placed = every project leaf, each year", "core/gap_federal_placement.csv",
        "PASS" if not bad5 else "FAIL", "ok" if not bad5 else str(bad5))
    add("P6 placed_share in [0, 1]", "core/gap_federal_placement.csv", "PASS" if not bad6 else "FAIL",
        "ok" if not bad6 else str(bad6))

    write(os.path.join(CORE, "fact_placement.csv"), FIELDS_FACT, fact)
    write(os.path.join(CORE, "gap_federal_placement.csv"), FIELDS_GAP, gap)
    write(os.path.join(CORE, "_validation_placement.csv"), ["check", "scope", "status", "detail"], checks)
    st = defaultdict(int)
    for c in checks:
        st[c["status"]] += 1
    print(f"placement: {len(fact)} project rows, {len(gap)} view rows; checks: "
          + ", ".join(f"{v} {k}" for k, v in sorted(st.items())))
    if any(c["status"] == "FAIL" for c in checks):
        sys.exit("build_federal_placement: FAIL in core/_validation_placement.csv")


if __name__ == "__main__":
    main()
