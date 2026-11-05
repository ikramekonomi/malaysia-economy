#!/usr/bin/env python3
"""Money that moves between two bodies (Phase 3, DATA_MODEL 5.2): fact_money_flow.

A budget or a spending total of one body is an observation (fact_observation); a flow exists only where the
source shows money moving to a named recipient. First slice: the federal grants and assignments to the states
(Tanggungan T.12 'Pemberian dan Serahan kepada Negeri-negeri', programme 010000), audited, one row per
activity per year, from PKKP's operating detail (sources/pkkp/data/<year>/fact_opex_detail.csv, the
activity's printed JUMLAH line).

The recipient comes from meta/flow_rule.csv, by activity code, and the printed activity name must contain
the rule's keyword (otherwise the build stops: the code moved). A grant the source pays to the state
governments or the local authorities as a class (capitation, road maintenance, revenue growth, the local
authority grant) goes to a group entity (D27) with geo _unallocated: the federal accounts do not split it by
state, and it is not split here. A grant to a named state goes to that state's government, geo stated. Second slice: the grants to governments
in supply vote B.11 programme 020000 (Bayaran Pindahan dan Pemberian), matched by printed name because
their activity codes renumber almost every year (petroleum duty compensation and the transfer-money refund to
Sabah and Sarawak jointly, the Concurrent List grants and state road slope maintenance to the state
governments, street lighting to the local authorities, grants to the Federal Territories' administrations).

Not loaded, and why:
  FY2009  the older presentation prints T.12 with no activity tier
  FY2015  the image-only scan: activity codes and names are misaligned and leaf amounts are OCR-provisional
          (sources/pkkp/data/2015/_unresolved_ocr_cells_2015.csv; CLAUDE.md: use ministry-level tables)

Checks (core/_validation_flow.csv): F1 every activity of the programme has a rule; F2 its printed name
matches the rule; F3 the year's flows equal the programme's printed JUMLAH exactly; F4 every entity is
registered; F5 the programme stays inside the T.12 head's audited total in core.

Run: python3 core/pipeline/build_flows.py   (after build_entities.py and build_core.py)
"""
import csv
import glob
import hashlib
import os
import sys
from collections import defaultdict
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(REPO, "meta")
CORE = os.path.join(REPO, "core")
PKKP = os.path.join(REPO, "sources", "pkkp", "data")
SKIP_YEARS = {"2009": "no activity tier in the FY2009 presentation",
              "2015": "image-only scan: activity codes misaligned, leaf amounts OCR-provisional"}
FIELDS = ["flow_id", "from_entity_id", "to_entity_id", "flow_type", "period_code", "amount", "amount_printed",
          "unit_printed", "economic_class", "purpose", "geo_code", "geo_method", "geo_confidence", "is_leaf",
          "basis", "status", "edition_id", "file_id", "pdf_page", "printed_page", "table_ref", "l1_ref"]


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, fieldnames, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(data)


def main():
    all_rules = rows(os.path.join(META, "flow_rule.csv"))
    rules = {(r["maksud_code"], r["program_code"], r["aktiviti_code"]): r for r in all_rules if r["aktiviti_code"]}
    name_rules = [r for r in all_rules if r["name_pattern"]]
    ents = {r["entity_id"]: r for r in rows(os.path.join(CORE, "dim_entity.csv"))}
    federal = next(c["entity_id"] for c in rows(os.path.join(CORE, "bridge_entity_code.csv"))
                   if c["code_system"] == "federal_gov")
    sha = {r["file_name"]: r["sha256"] for r in rows(os.path.join(META, "registry_file.csv"))}
    out, checks, stop = [], [], []
    printed_total, unknown, badname = {}, [], []
    leaves = defaultdict(list)

    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_opex_detail.csv"))):
        rel = os.path.relpath(path, REPO)
        for i, r in enumerate(rows(path), start=2):
            if r["maksud_code"] != "T.12" or r["program_code"] != "010000" or not r["source_file"].startswith(r["year"]):
                continue
            y = r["year"]
            if y in SKIP_YEARS:
                continue
            if r["row_type"] == "jumlah_program":
                printed_total[y] = (Decimal(r["sebenar_rm"]), f"{rel}#row{i}")
                continue
            if r["row_type"] == "object_aktiviti":
                leaves[(y, r["aktiviti_code"])].append(Decimal(r["sebenar_rm"] or "0"))
                continue
            if r["row_type"] != "jumlah_aktiviti":
                continue
            rule = rules.get((r["maksud_code"], r["program_code"], r["aktiviti_code"]))
            if not rule:
                unknown.append(f"FY{y} {r['aktiviti_code']} {r['aktiviti_name_bm']!r}")
                continue
            if rule["name_must_contain"] not in r["aktiviti_name_bm"].lower():
                badname.append(f"FY{y} {r['aktiviti_code']} {r['aktiviti_name_bm']!r} lacks {rule['name_must_contain']!r}")
                continue
            to = rule["to_entity_id"]
            key = "|".join([federal, to, y, r["maksud_code"], r["aktiviti_code"], r["source_file"]])
            out.append(dict(
                flow_id="f" + hashlib.sha1(key.encode()).hexdigest()[:12], from_entity_id=federal, to_entity_id=to,
                flow_type="grant", period_code=y, amount=str(Decimal(r["sebenar_rm"])),
                amount_printed=r["sebenar_rm"], unit_printed="RM",
                economic_class="40000 Pemberian dan Kenaan Bayaran Tetap",
                purpose=f"{r['maksud_code']} {r['aktiviti_code']}: {rule['purpose_en']}; printed: {r['aktiviti_name_bm'].strip()}",
                geo_code=rule["geo_code"] or "_unallocated", geo_method=rule["geo_method"],
                geo_confidence="high" if rule["geo_method"] == "stated" else "none", is_leaf="true",
                basis="audited", status="final", edition_id=f"pkkp:{r['source_file']}",
                file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"], printed_page=r["printed_page"],
                table_ref=f"{r['statement']} ({r['label_bm']})", l1_ref=f"{rel}#row{i}"))

    # Name-matched grants (B.11 programme 020000; B.06; B.32): activity codes renumber almost every year, so these
    # rules match the printed name (a regex), and a rule may match at most one block in a year. A block is an
    # activity, or a programme printed with no activities (B.32 FY2010-2013 prints 'PERBADANAN PUTRAJAYA' as a whole
    # programme). A rule with no programme_code matches in any programme of its vote. Only the blocks a rule names
    # are loaded: most of these votes are not money to a government.
    import re
    multi, b11_leaves, b11_years = [], defaultdict(list), defaultdict(set)
    rule_votes = {n["maksud_code"] for n in name_rules}
    b11 = []
    for path in sorted(glob.glob(os.path.join(PKKP, "*", "fact_opex_detail.csv"))):
        rel = os.path.relpath(path, REPO)
        scoped = [(i, r) for i, r in enumerate(rows(path), start=2)
                  if r["maksud_code"] in rule_votes and r["source_file"].startswith(r["year"]) and r["year"] not in SKIP_YEARS]
        with_acts = {(r["year"], r["maksud_code"], r["program_code"]) for i, r in scoped if r["aktiviti_code"].strip()}
        for i, r in scoped:
            y = r["year"]
            if r["row_type"] == "object_aktiviti":
                b11_leaves[(y, r["maksud_code"], r["program_code"], r["aktiviti_code"].strip())].append((i, r))
                continue
            if r["row_type"] == "jumlah_aktiviti":
                name = r["aktiviti_name_bm"]
            elif r["row_type"] == "jumlah_program" and (y, r["maksud_code"], r["program_code"]) not in with_acts:
                name = r["program_name_bm"]
            else:
                continue
            hit = [n for n in name_rules if n["maksud_code"] == r["maksud_code"]
                   and n["program_code"] in ("", r["program_code"]) and re.search(n["name_pattern"], name, re.I)]
            if len(hit) > 1:
                multi.append(f"FY{y} {r['maksud_code']} {r['program_code']}/{r['aktiviti_code']} {name!r} matches {len(hit)} rules")
                continue
            if hit:
                b11.append((hit[0], r, rel, i))
    # The money paid to the recipient is the activity's 40000 'Pemberian dan Kenaan Bayaran Tetap' line: a block can
    # also print a 20000 services line, which is not paid to anyone, and in FY2017 the printed activity JUMLAH of
    # 020700 and 020800 leaves that line out although the programme JUMLAH includes it (page-proved printing
    # error, sources/pkkp/data/2017/_validation_checks_2017.csv). So the flow is the 40000 line, cited to it.
    seen, b11_bad, other_lines = defaultdict(list), [], []
    resolved = []
    for rule, jr, rel, ji in b11:
        lines = b11_leaves[(jr["year"], jr["maksud_code"], jr["program_code"], jr["aktiviti_code"].strip())]
        grant = [(i, r) for i, r in lines if r["objek_code"] == "40000"]
        if len(grant) != 1:
            b11_bad.append(f"FY{jr['year']} {jr['maksud_code']} {jr['program_code']}/{jr['aktiviti_code']}: {len(grant)} 40000 lines")
            continue
        rest = [(r["objek_code"], r["sebenar_rm"]) for i, r in lines if r["objek_code"] != "40000"]
        if rest:
            other_lines.append(f"FY{jr['year']} {jr['maksud_code']} {jr['aktiviti_code']} {rest} (not paid to the recipient; not in the flow)")
        resolved.append((rule, grant[0][1], rel, grant[0][0]))
    for rule, r, rel, i in resolved:
        block = r["aktiviti_code"].strip() or r["program_code"]
        printed = r["aktiviti_name_bm"].strip() or r["program_name_bm"].strip()
        seen[(rule["name_pattern"], r["year"])].append(f"{r['maksud_code']} {block}")
        to = rule["to_entity_id"]
        key = "|".join([federal, to, r["year"], r["maksud_code"], r["program_code"], r["aktiviti_code"], r["source_file"]])
        out.append(dict(
            flow_id="f" + hashlib.sha1(key.encode()).hexdigest()[:12], from_entity_id=federal, to_entity_id=to,
            flow_type="grant", period_code=r["year"], amount=str(Decimal(r["sebenar_rm"])),
            amount_printed=r["sebenar_rm"], unit_printed="RM", economic_class=r.get("objek_class_bm") or "",
            purpose=f"{r['maksud_code']} {block}: {rule['purpose_en']}; printed: {printed}",
            geo_code=rule["geo_code"] or "_unallocated", geo_method=rule["geo_method"],
            geo_confidence="high" if rule["geo_method"] == "stated" else "none", is_leaf="true",
            basis="audited", status="final", edition_id=f"pkkp:{r['source_file']}",
            file_id=sha.get(r["source_file"], ""), pdf_page=r["pdf_page"], printed_page=r["printed_page"],
            table_ref=f"{r['statement']} ({r['label_bm']})", l1_ref=f"{rel}#row{i}"))
        b11_years[rule["name_pattern"]].add(r["year"])
    multi += [f"FY{y} rule {p!r} matches activities {c}" for (p, y), c in seen.items() if len(c) > 1]

    def add(check, scope, status, detail):
        checks.append(dict(check=check, scope=scope, status=status, detail=detail))
    jumlah_t12 = [f for f in out if f["purpose"].startswith("T.12 ")]

    add("F1 every T.12 programme 010000 activity has a recipient rule (meta/flow_rule.csv)", "fact_money_flow",
        "PASS" if not unknown else "FAIL", f"{len(jumlah_t12)} T.12 flows" + (f"; no rule: {unknown}" if unknown else ""))
    add("F2 the printed activity name matches its rule (the code has not moved)", "fact_money_flow",
        "PASS" if not badname else "FAIL", "ok" if not badname else str(badname))
    t12 = [f for f in out if f["purpose"].startswith("T.12 ")]
    by_year = defaultdict(Decimal)
    for f in t12:
        by_year[f["period_code"]] += Decimal(f["amount"])
    off = [f"FY{y}: flows {by_year[y]} vs printed {t}" for y, (t, _) in sorted(printed_total.items()) if by_year[y] != t]
    missing = sorted(set(printed_total) - set(by_year))
    add("F3 a year's flows equal T.12 programme 010000's printed JUMLAH, to the sen", "fact_money_flow",
        "PASS" if not off and not missing else "FAIL",
        f"{len(printed_total)} years" + (f"; differ: {off}" if off else "") + (f"; no flows: {missing}" if missing else ""))
    stray = sorted({f[k] for f in out for k in ("from_entity_id", "to_entity_id")} - set(ents))
    add("F4 every flow's entities are registered (core/dim_entity.csv)", "fact_money_flow",
        "PASS" if not stray else "FAIL", "ok" if not stray else str(stray))
    head = defaultdict(Decimal)
    for o in rows(os.path.join(CORE, "fact_observation.csv")):
        if o["indicator_code"] == "federal_gov.vote.opex" and o["breakdown_key"] == "charged_head=T.12" \
                and o["basis"] == "audited" and o["edition_id"].startswith("pkkp:"):
            head[o["period_code"]] += Decimal(o["value"])
    over = [f"FY{y}" for y in by_year if y in head and by_year[y] > head[y]]
    add("F5 the grants stay inside the T.12 head's audited total in core", "fact_money_flow",
        "PASS" if not over else "FAIL",
        f"{len(by_year)} years" + (f"; above the head: {over}" if over else ", grants <= T.12 head every year"))
    jumlah = {(f["period_code"], f["purpose"].split()[1].rstrip(":")): Decimal(f["amount"]) for f in t12}
    notleaf = [f"FY{y} {a}: {len(leaves[(y, a)])} leaf rows sum {sum(leaves[(y, a)])} vs JUMLAH {v}"
               for (y, a), v in sorted(jumlah.items()) if len(leaves[(y, a)]) != 1 or leaves[(y, a)][0] != v]
    add("F7 each activity prints one object line, equal to its JUMLAH (so the JUMLAH is the leaf)", "fact_money_flow",
        "PASS" if not notleaf else "FAIL", f"{len(jumlah)} activities" + (f"; {notleaf}" if notleaf else ", all single-leaf"))
    add("F8 a name rule (B.11, B.06, B.32) matches at most one block a year, and a block at most one rule", "fact_money_flow",
        "PASS" if not multi else "FAIL", f"{len(resolved)} name-matched flows" + (f"; {multi}" if multi else ""))
    add("F9 each name-matched grant prints exactly one 40000 (Pemberian dan Kenaan Bayaran Tetap) line, the flow's amount",
        "fact_money_flow", "PASS" if not b11_bad else "FAIL",
        f"{len(resolved)} activities" + (f"; {b11_bad}" if b11_bad else "")
        + (f"; other object lines left out: {other_lines}" if other_lines else ""))
    years_all = sorted({f["period_code"] for f in out})
    by_pat = defaultdict(set)
    for n in name_rules:
        by_pat[n["name_pattern"]] |= b11_years[n["name_pattern"]]
    label = {n["name_pattern"]: n["purpose_en"].split(" (")[0] for n in name_rules}
    gaps = {label[p]: [y for y in years_all if y not in ys] for p, ys in by_pat.items()}
    add("F10 years in which a name-matched grant is not found under its rules' votes (INFO: it may be printed under "
        "another vote, see F11)", "fact_money_flow",
        "INFO", "; ".join(f"{k}: {v}" for k, v in gaps.items() if v) or "every grant found every year")
    add("F11 grants to governments seen in L1 and NOT loaded (declared)", "fact_money_flow", "INFO",
        "interest subsidy on Syarikat Kemajuan Perumahan Borneo (Sabah) loans (paid on a company's loans, not to a "
        "government); the World Bank Group / IsDB offices in Kuala Lumpur (not a state); FY2018: the Federal "
        "Territories' grants are not found in B.11 or B.06 - B.32 040400 'Penyelenggaraan dan Kemudahan Awam' prints "
        "RM65,000,000.00 that year only, about their combined size, but its name does not say so (not loaded until a "
        "page or budget book proves it); the Federal Territories ministry's (B.32, later B.06) other "
        "lines for the territories (PICC upkeep, the Putrajaya bus service and infrastructure upkeep, Labuan water "
        "supply and ferry fare discount, Tasik Putrajaya desilting): services the ministry buys, recipient not stated; "
        "lines TAGGED with an administration but not a grant to it by name (FY2010 B.32 070500 ITIS-DBKL operating "
        "cost RM38m and 070600 upkeep of property not owned by DBKL RM10m; FY2014 080200 duty and licence collection "
        "(DBKL) RM2m, 080400 Bukit Tagar tipping fee (DBKL) RM18.43m, 090600 BIMP-EAGA games (PL) RM2.28m, 091000 "
        "ferry fare discount (PL) RM11m; FY2013 090400 Borneo Games (PL) RM1.5m): possibly paid through the "
        "administration, not loaded until a page says so; FY2009 programme-level grants to Perbadanan Putrajaya "
        "(B.32 050000, RM101m) and Perbadanan Labuan (040000, RM36.36m): FY2009 is not loaded (F6); B.43's 'Kerajaan "
        "Tempatan' and solid-waste lines: the recipient is not stated")
    add("F6 years not loaded (declared)", "fact_money_flow", "INFO",
        "; ".join(f"FY{y}: {why}" for y, why in SKIP_YEARS.items()))

    out.sort(key=lambda f: (f["period_code"], f["purpose"]))
    write(os.path.join(CORE, "fact_money_flow.csv"), FIELDS, out)
    write(os.path.join(CORE, "_validation_flow.csv"), ["check", "scope", "status", "detail"], checks)
    fails = [c for c in checks if c["status"] == "FAIL"]
    if fails:
        sys.exit("build_flows: FAIL in core/_validation_flow.csv: " + "; ".join(c["check"] for c in fails))
    named = sum(1 for f in out if f["geo_method"] == "stated")
    print(f"flows: {len(out)} federal->state flows ({named} to a named state, {len(out) - named} to a class of "
          f"bodies), {len(by_year)} years; checks: " + ", ".join(f"{c['status']}" for c in checks))


if __name__ == "__main__":
    main()
