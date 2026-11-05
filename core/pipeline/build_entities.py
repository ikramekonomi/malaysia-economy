#!/usr/bin/env python3
"""Build the entity spine (Phase 3, DATA_MODEL 4.5): who spends, receives, audits or is audited.

Reads (never edits):
  meta/entity_register.csv   every entity_id ever issued, with the reason; never reused, never deleted
  meta/entity_code.csv       every readable code of an entity, with its years and a proof (the human decisions)
  meta/spending_head.csv     Tanggungan (T.*) and reserve (P.70) heads: spending heads, NOT bodies
  sources/pkkp/data/<year>/dim_maksud.csv            the votes printed in each audited volume, FY2009-2024
  sources/anggaran/data/<year>/fact_anggaran_maksud_<year>.csv   the votes printed in each budget book
Writes (derived, rebuilt every run, committed so a reviewer can diff them):
  core/dim_entity.csv          one row per entity, its latest printed names
  core/bridge_entity_code.csv  code -> entity with validity years and proof
  core/entity_name.csv         every name each entity was printed under, by code and years
  core/_validation_entity.csv  checks E1-E8

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

ENTITY_TYPES = {"government", "ministry", "department", "vote", "programme", "activity", "project",
                "statutory_body", "glc", "company", "auditor", "natural_person"}
GFS = {"central_gov", "state_gov", "local_gov", "public_corp", "private"}
SYSTEMS = {"federal_gov", "state_gov", "maksud_bekalan", "maksud_pembangunan"}


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

    def resolve(self, system, code, year=None):
        hits = [c for c in self.by.get((system, code), [])
                if year is None or yr(c["valid_from"], -10**9) <= year <= yr(c["valid_to"], 10**9)]
        ids = sorted({c["entity_id"] for c in hits})
        return ids


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
                if a["entity_id"] != b["entity_id"] and not (
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
            hit = br.resolve(system_of(code) or "?", code, y)
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
                                                         "valid_to", "proof"],
          sorted(codes, key=lambda c: (c["entity_id"], c["code_system"], yr(c["valid_from"], -10**9))))
    write(os.path.join(CORE, "entity_name.csv"), list(hist[0]), hist)
    st = defaultdict(int)
    for r in out:
        st[r["status"]] += 1
    print(f"entities: {len(dim)} entities, {len(codes)} codes, {len(hist)} printed names; checks: "
          + ", ".join(f"{v} {k}" for k, v in sorted(st.items())))


if __name__ == "__main__":
    main()
