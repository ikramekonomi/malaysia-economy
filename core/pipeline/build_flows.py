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
state, and it is not split here. A grant to a named state goes to that state's government, geo stated.

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
    rules = {(r["maksud_code"], r["program_code"], r["aktiviti_code"]): r for r in rows(os.path.join(META, "flow_rule.csv"))}
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

    def add(check, scope, status, detail):
        checks.append(dict(check=check, scope=scope, status=status, detail=detail))

    add("F1 every T.12 programme 010000 activity has a recipient rule (meta/flow_rule.csv)", "fact_money_flow",
        "PASS" if not unknown else "FAIL", f"{len(out)} flows" + (f"; no rule: {unknown}" if unknown else ""))
    add("F2 the printed activity name matches its rule (the code has not moved)", "fact_money_flow",
        "PASS" if not badname else "FAIL", "ok" if not badname else str(badname))
    by_year = defaultdict(Decimal)
    for f in out:
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
    jumlah = {(f["period_code"], f["purpose"].split()[1].rstrip(":")): Decimal(f["amount"]) for f in out}
    notleaf = [f"FY{y} {a}: {len(leaves[(y, a)])} leaf rows sum {sum(leaves[(y, a)])} vs JUMLAH {v}"
               for (y, a), v in sorted(jumlah.items()) if len(leaves[(y, a)]) != 1 or leaves[(y, a)][0] != v]
    add("F7 each activity prints one object line, equal to its JUMLAH (so the JUMLAH is the leaf)", "fact_money_flow",
        "PASS" if not notleaf else "FAIL", f"{len(jumlah)} activities" + (f"; {notleaf}" if notleaf else ", all single-leaf"))
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
