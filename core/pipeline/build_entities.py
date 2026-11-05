#!/usr/bin/env python3
"""Build the entity spine (Phase 3, DATA_MODEL 4.5): who spends, receives, audits or is audited.

Reads (never edits):
  meta/entity_register.csv   every entity_id ever issued, with the reason; never reused, never deleted
  meta/entity_code.csv       every readable code of an entity, with its years and a proof (the human decisions)
  meta/spending_head.csv     Tanggungan (T.*) and reserve (P.70) heads: spending heads, NOT bodies
  meta/entity_lineage.csv    where a body's work went when its vote ended (D28): a link between two bodies, never one ID
  meta/entity_lineage_evidence.csv  the printed programme/activity names that show each move, re-found in PKKP L1
  sources/pkkp/data/<year>/dim_maksud.csv            the votes printed in each audited volume, FY2009-2024
  sources/anggaran/data/<year>/fact_anggaran_maksud_<year>.csv   the votes printed in each budget book
Writes (derived, rebuilt every run, committed so a reviewer can diff them):
  core/dim_entity.csv          one row per entity, its latest printed names
  core/bridge_entity_code.csv  code -> entity with validity years and proof
  core/entity_name.csv         every name each entity was printed under, by code and years
  core/entity_lineage.csv      each lineage link with both bodies' names and its evidence lines summarised
  core/entity_lineage_evidence.csv  each evidence line with the PKKP file, PDF page and printed page it was found on
  core/_validation_entity.csv  checks E1-E10

A code printed in a source with no entity for that year STOPS the build and is listed: an ID is issued
only when a person decides whether it is a new body or a renumbered old one (rule D26).

Run: python3 core/pipeline/build_entities.py
"""
import csv
import glob
import os
import re
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(REPO, "meta")
CORE = os.path.join(REPO, "core")

ENTITY_TYPES = {"government", "ministry", "department", "vote", "group", "local_authority", "programme", "activity", "project",
                "statutory_body", "glc", "company", "auditor", "natural_person"}
GFS = {"central_gov", "state_gov", "local_gov", "public_corp", "private"}
SYSTEMS = {"federal_gov", "state_gov", "maksud_bekalan", "maksud_pembangunan", "group", "local_authority"}


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, fieldnames, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(data)


def yr(s, default):
    return int(s) if s.strip() else default


class Bridge:
    """Resolve (code_system, code, year) -> entity_id, the way every consumer must."""

    def __init__(self, codes):
        self.by = defaultdict(list)
        for c in codes:
            self.by[(c["code_system"], c["code"])].append(c)

    def resolve(self, system, code, year=None, scope=""):
        """A row scoped to one source (scope=anggaran:2024) wins for that source: a budget book is tabled before
        its year and can reprint a code under the body that held it then (D26, verifier H1). Unscoped rows
        answer every other question."""
        def hits(sc):
            return sorted({c["entity_id"] for c in self.by.get((system, code), []) if c.get("scope", "") == sc
                           and (year is None or yr(c["valid_from"], -10**9) <= year <= yr(c["valid_to"], 10**9))})
        return (hits(scope) if scope else []) or hits("")


def system_of(code):
    return {"B": "maksud_bekalan", "P": "maksud_pembangunan"}.get(code[:1])


def main():
    reg = rows(os.path.join(META, "entity_register.csv"))
    codes = rows(os.path.join(META, "entity_code.csv"))
    heads = {r["code"]: r for r in rows(os.path.join(META, "spending_head.csv"))}
    br = Bridge(codes)
    out, stop = [], []

    def add(check, scope, status, detail):
        out.append(dict(check=check, scope=scope, status=status, detail=detail))

    # E1 IDs: well formed, unique, contiguous from E000001 (a deleted ID leaves a hole and is caught)
    ids = [r["entity_id"] for r in reg]
    bad = [i for i in ids if not re.fullmatch(r"E\d{6}", i)]
    want = [f"E{i:06d}" for i in range(1, len(ids) + 1)]
    add("E1 entity IDs well formed, unique and contiguous (none deleted, none reused)", "meta/entity_register.csv",
        "PASS" if not bad and sorted(ids) == want else "FAIL",
        f"{len(ids)} IDs" + (f"; malformed {bad}" if bad else "") +
        ("" if sorted(ids) == want else f"; holes or duplicates: {sorted(set(want) ^ set(ids))[:10]}"))

    # E2 referential: every code row names a registered entity; every entity has a code
    known = set(ids)
    orphan = sorted({c["entity_id"] for c in codes} - known)
    codeless = sorted(known - {c["entity_id"] for c in codes})
    add("E2 every code belongs to a registered entity, every entity has a code", "meta/entity_code.csv",
        "PASS" if not orphan and not codeless else "FAIL",
        f"{len(codes)} codes" + (f"; unknown entities {orphan}" if orphan else "") +
        (f"; entities with no code {codeless}" if codeless else ""))

    # E3 a code points to exactly one entity on any date
    clash = []
    for (s, c), lst in br.by.items():
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                if a["entity_id"] != b["entity_id"] and a.get("scope", "") == b.get("scope", "") and not (
                        yr(a["valid_to"], 10**9) < yr(b["valid_from"], -10**9)
                        or yr(b["valid_to"], 10**9) < yr(a["valid_from"], -10**9)):
                    clash.append(f"{s}:{c} {a['entity_id']}/{b['entity_id']}")
    add("E3 a code points to one entity on any date", "meta/entity_code.csv",
        "PASS" if not clash else "FAIL", f"{len(br.by)} codes" + (f"; overlaps {clash}" if clash else ""))

    # E4 every vote printed in an audited volume resolves; E5 every vote printed in a budget book resolves
    names = defaultdict(lambda: defaultdict(list))      # entity -> (code, name_bm, name_en) -> years
    n4 = 0
    for p in sorted(glob.glob(os.path.join(REPO, "sources", "pkkp", "data", "*", "dim_maksud.csv"))):
        for r in rows(p):
            code, y = r["maksud_code"].strip(), int(r["year"])
            if code in heads:
                continue
            n4 += 1
            hit = br.resolve(system_of(code) or "?", code, y)
            if len(hit) != 1:
                stop.append(f"PKKP FY{y} {code} {r['name_bm']!r}: {hit or 'no entity'}")
                continue
            names[hit[0]][(code, r["name_bm"].strip(), r["name_en"].strip())].append(y)
    add("E4 every vote printed in PKKP FY2009-2024 resolves to exactly one entity", "sources/pkkp dim_maksud",
        "PASS" if not [s for s in stop if s.startswith("PKKP")] else "FAIL",
        f"{n4} code-years" + (f"; unresolved {[s for s in stop if s.startswith('PKKP')][:5]}" if stop else ""))
    n5, s5 = 0, []
    for p in sorted(glob.glob(os.path.join(REPO, "sources", "anggaran", "data", "*", "fact_anggaran_maksud_*.csv"))):
        y = int(os.path.basename(p)[-8:-4])
        seen = {}
        for r in rows(p):
            seen.setdefault(r["maksud_code"].strip(), r["maksud_name_bm"].strip())
        for code, nm in sorted(seen.items()):
            if code in heads:
                continue
            n5 += 1
            hit = br.resolve(system_of(code) or "?", code, y, scope=f"anggaran:{y}")
            if len(hit) != 1:
                s5.append(f"Anggaran {y} {code} {nm!r}: {hit or 'no entity'}")
    stop += s5
    add("E5 every vote printed in an Anggaran book resolves at the book's year", "sources/anggaran",
        "PASS" if not s5 else "FAIL", f"{n5} code-books" + (f"; unresolved {s5[:5]}" if s5 else ""))

    # E6 every code row carries a proof; a code after an entity's first carries a reason beyond 'first appearance'
    noproof = [f"{c['entity_id']} {c['code']}" for c in codes if not c["proof"].strip()]
    first = {}
    for c in sorted(codes, key=lambda c: (c["entity_id"], c["code_system"], yr(c["valid_from"], -10**9))):
        first.setdefault((c["entity_id"], c["code_system"]), c)
    later = [f"{c['entity_id']} {c['code']}" for c in codes
             if first[(c["entity_id"], c["code_system"])] is not c and c["proof"].startswith("first appearance")
             and c["code"] == first[(c["entity_id"], c["code_system"])]["code"]]
    add("E6 every code link carries a proof (a renumbering cites its evidence)", "meta/entity_code.csv",
        "PASS" if not noproof and not later else "FAIL",
        f"{len(codes)} links" + (f"; no proof {noproof}" if noproof else "") +
        (f"; later link without proof {later}" if later else ""))

    # E7 vocabularies and parents
    badv = [f"{r['entity_id']} {r['entity_type']}/{r['gfs_sector']}" for r in reg
            if r["entity_type"] not in ENTITY_TYPES or r["gfs_sector"] not in GFS]
    badp = [r["entity_id"] for r in reg if r["parent_entity_id"] and r["parent_entity_id"] not in known]
    bads = sorted({c["code_system"] for c in codes} - SYSTEMS)
    add("E7 entity_type, gfs_sector and code_system in their vocabularies; parents registered", "meta",
        "PASS" if not (badv or badp or bads) else "FAIL",
        "ok" if not (badv or badp or bads) else f"{badv} {badp} {bads}")

    # E8 decisions still open (INFO): entities issued by rule and awaiting a person
    prop = [f"{r['entity_id']} {r['name_bm']}" for r in reg if r["decision_status"] == "proposed"]
    add("E8 identity decisions awaiting a person (decision_status=proposed)", "meta/entity_register.csv",
        "INFO" if prop else "PASS", f"{len(prop)}" + (f": {prop}" if prop else ""))

    # E9 lineage (D28): every evidence line is printed in that year's PKKP volume under its code, the code names the
    # stated body that year, a moved line is no longer printed under the old vote the next year, and every link
    # joins two different registered bodies with evidence on both sides
    lin = rows(os.path.join(META, "entity_lineage.csv"))
    ev = rows(os.path.join(META, "entity_lineage_evidence.csv"))
    printed = {}

    def printed_in(y):
        if y not in printed:
            d = defaultdict(lambda: {})
            p = os.path.join(REPO, "sources", "pkkp", "data", str(y), "fact_opex_detail.csv")
            spent = defaultdict(float)
            for r in (rows(p) if os.path.exists(p) else []):
                for n in (r["program_name_bm"], r["aktiviti_name_bm"]):
                    if n.strip():
                        d[r["maksud_code"]].setdefault(n.strip(), r)
                        if r["row_type"] in ("object_aktiviti", "object_program") and r["sebenar_rm"].strip():
                            spent[(r["maksud_code"], n.strip())] += float(r["sebenar_rm"])
            printed[y] = d
            printed[(y, "spent")] = spent
        return printed[y]

    byid = {r["lineage_id"]: r for r in lin}
    e9, ev_out = [], []
    for r in lin:
        if r["from_entity_id"] not in known or r["to_entity_id"] not in known or r["from_entity_id"] == r["to_entity_id"]:
            e9.append(f"{r['lineage_id']} bodies {r['from_entity_id']}->{r['to_entity_id']}")
        sides = {e["side"] for e in ev if e["lineage_id"] == r["lineage_id"]}
        if not {"from", "to"} <= sides:
            e9.append(f"{r['lineage_id']} evidence on {sorted(sides)} only")
    for r in lin:
        if r["moved_mid_year"] not in ("yes", "no"):
            e9.append(f"{r['lineage_id']} moved_mid_year={r['moved_mid_year']!r}")
        elif r["moved_mid_year"] == "yes":
            fy = int(r["first_year"])
            printed_in(fy)
            if not any(printed[(fy, "spent")].get((e["maksud_code"], e["printed_name"]))
                       for e in ev if e["lineage_id"] == r["lineage_id"] and e["side"] == "from"):
                e9.append(f"{r['lineage_id']} declared moved_mid_year but the old vote spent nothing on it in {fy}")
    if len(byid) != len(lin):
        e9.append("duplicate lineage_id")
    for e in ev:
        L = byid.get(e["lineage_id"])
        if not L:
            e9.append(f"evidence for unknown {e['lineage_id']}")
            continue
        y, fy = int(e["year"]), int(L["first_year"])
        want_y = fy - 1 if e["side"] == "from" else fy
        want_e = L["to_entity_id"] if e["side"] == "to" else L["from_entity_id"]
        tag = f"{e['lineage_id']} {e['side']} {y} {e['maksud_code']} {e['printed_name']!r}"
        if e["side"] not in ("from", "to", "stays") or y != want_y:
            e9.append(f"{tag}: side/year (want {want_y})")
        if br.resolve("maksud_bekalan", e["maksud_code"], y) != [want_e]:
            e9.append(f"{tag}: code names {br.resolve('maksud_bekalan', e['maksud_code'], y)} not {want_e}")
        hit = printed_in(y).get(e["maksud_code"], {}).get(e["printed_name"])
        if not hit:
            e9.append(f"{tag}: not printed")
            continue
        left = ""
        if e["side"] == "from":
            # the old vote may still print the line in the move year: with no spending (the budget was moved
            # before it was spent) or, for a move made during the year, with part of it (moved_mid_year=yes)
            printed_in(fy)
            left = printed[(fy, "spent")].get((e["maksud_code"], e["printed_name"]))
            if left and L["moved_mid_year"] != "yes":
                e9.append(f"{tag}: old vote still spent {left:,.2f} on it in {fy} (not declared moved_mid_year)")
            left = "" if left is None else f"{left:.2f}"
        ev_out.append(dict(lineage_id=e["lineage_id"], side=e["side"], year=y, maksud_code=e["maksud_code"],
                           entity_id=want_e, printed_name=e["printed_name"], source_file=hit["source_file"],
                           pdf_page=hit["pdf_page"], printed_page=hit["printed_page"],
                           old_vote_actual_rm_in_first_year=left))
    add("E9 every lineage link joins two bodies, each evidence line is printed in PKKP under that body's vote that "
        "year, and the old vote spends nothing on a moved line the next year unless the move is declared mid-year", "meta/entity_lineage*.csv",
        "PASS" if not e9 else "FAIL", f"{len(lin)} links, {len(ev)} evidence lines" + (f"; {e9[:8]}" if e9 else ""))

    # E10 a vote code that named more than one body: the later body is reachable from the earlier one through
    # lineage, so nobody meets a reused code without being told where the earlier body's work went
    nxt = defaultdict(set)
    for r in lin:
        nxt[r["from_entity_id"]].add(r["to_entity_id"])

    def reach(a, b):
        seen, todo = {a}, [a]
        while todo:
            for n in nxt[todo.pop()] - seen:
                seen.add(n)
                todo.append(n)
        return b in seen
    e10, nre = [], 0
    for (s_, c), lst in br.by.items():
        runs = sorted({(yr(x["valid_from"], -10**9), x["entity_id"]) for x in lst if not x.get("scope")})
        order = []
        for _, eid in runs:
            if not order or order[-1] != eid:
                order.append(eid)
        if s_ == "maksud_bekalan" and len(order) > 1:
            nre += 1
            e10 += [f"{c} {a}->{b}" for a, b in zip(order, order[1:]) if not reach(a, b)]
    add("E10 a reused vote code: each later body is reachable from the earlier one through lineage", "meta/entity_lineage.csv",
        "PASS" if not e10 else "FAIL", f"{nre} reused B codes" + (f"; no lineage {e10}" if e10 else ""))

    os.makedirs(CORE, exist_ok=True)
    write(os.path.join(CORE, "_validation_entity.csv"), ["check", "scope", "status", "detail"], out)
    if stop:
        sys.exit("build_entities: codes with no entity - a person must issue an ID or link it (rule D26):\n  "
                 + "\n  ".join(stop))
    if any(r["status"] == "FAIL" for r in out):
        sys.exit("build_entities: FAIL in core/_validation_entity.csv")

    # dim_entity: register fields + the latest printed English name; entity_name: every printed name
    hist = []
    for eid, d in names.items():
        for (code, bm, en), ys in d.items():
            ys = sorted(ys)
            start = prev = ys[0]
            for y in ys[1:] + [None]:
                if y is not None and y == prev + 1:
                    prev = y
                    continue
                hist.append(dict(entity_id=eid, code=code, name_bm=bm, name_en=en, valid_from=start,
                                 valid_to=prev, source="PKKP dim_maksud"))
                if y is not None:
                    start = prev = y
    hist.sort(key=lambda r: (r["entity_id"], r["valid_from"], r["code"]))
    dim = []
    for r in reg:
        dim.append(dict(entity_id=r["entity_id"], entity_type=r["entity_type"], name_bm=r["name_bm"],
                        name_en=r["name_en"], parent_entity_id=r["parent_entity_id"], gfs_sector=r["gfs_sector"],
                        seat_geo_code="", fy_end_month="12", decision_status=r["decision_status"]))
    write(os.path.join(CORE, "dim_entity.csv"), list(dim[0]), dim)
    write(os.path.join(CORE, "bridge_entity_code.csv"), ["entity_id", "code_system", "code", "valid_from",
                                                         "valid_to", "scope", "proof"],
          sorted(codes, key=lambda c: (c["entity_id"], c["code_system"], yr(c["valid_from"], -10**9))))
    write(os.path.join(CORE, "entity_name.csv"), list(hist[0]), hist)
    def nm(eid, y):
        # the name the body's supply vote was printed under that year (a body is renamed; the link shows the
        # name a reader meets on that page), else its register name
        hit = [bm for (code, bm, en), ys in names[eid].items() if code.startswith("B.") and y in ys]
        return hit[0] if hit else next(r["name_bm"] for r in reg if r["entity_id"] == eid)
    lo = []
    for r in lin:
        mine = [e for e in ev_out if e["lineage_id"] == r["lineage_id"]]
        lo.append(dict(lineage_id=r["lineage_id"], from_entity_id=r["from_entity_id"], from_name_bm=nm(r["from_entity_id"], int(r["first_year"]) - 1),
                       to_entity_id=r["to_entity_id"], to_name_bm=nm(r["to_entity_id"], int(r["first_year"])), first_year=r["first_year"],
                       moved_mid_year=r["moved_mid_year"],
                       what_moved=r["what_moved"], note=r["note"],
                       evidence="; ".join(f"{e['side']} {e['year']} {e['maksud_code']} '{e['printed_name']}' p{e['pdf_page']}"
                                          for e in mine)))
    write(os.path.join(CORE, "entity_lineage.csv"), list(lo[0]), lo)
    write(os.path.join(CORE, "entity_lineage_evidence.csv"), list(ev_out[0]), ev_out)
    st = defaultdict(int)
    for r in out:
        st[r["status"]] += 1
    print(f"entities: {len(dim)} entities, {len(codes)} codes, {len(hist)} printed names; checks: "
          + ", ".join(f"{v} {k}" for k, v in sorted(st.items())))


if __name__ == "__main__":
    main()
