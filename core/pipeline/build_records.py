#!/usr/bin/env python3
"""Audits as records, their links to bodies, and gap_audit_recurrence (Phase 4, D33).

  python3 core/pipeline/build_records.py -> core/fact_record.csv, core/bridge_link.csv,
                                            core/gap_audit_recurrence.csv, core/_validation_records.csv

Method (declared 2026-11-06, with the taxonomy meta/audit_topic_taxonomy.csv committed before any count):
* Topic families: a pattern matches at the start of a word (amended after a first, unpublished count: hartanah is
  not tanah). The families are of the audit's title only, never of its findings.
* fact_record: one row per audit the LKAN contents pages list (sources/audit-negara/data/fact_lkan_audit_inventory.csv),
  record_type 'audit'. geo_code: MY for a federal volume, the state's ISO code for a state volume. period_code: the
  year audited, from the volume's own label ('LKAN 2017 Siri 2' -> 2017) or its title ('... TAHUN 2023'); else the
  year before tabling. title_bm = the topic as printed (or the company audited); attributes keep the body, the
  company or agency, the part, the printed page and the topic families the declared taxonomy gives the title.
* bridge_link (D33): an audit is linked to a federal body only when the body printed in the contents (a ministry or
  department, in capitals) equals, ignoring case and spacing, a name that body officially had that year
  (core/entity_name.csv, from the accounts' own vote names): link_method 'name_exact_official', publishable. No other
  link is made here: a fuzzy, translated or abbreviated name, a statutory body or a company would be
  'name_matched_reviewed' and needs the owner's signature (D33), so it is left unlinked. A person is never linked.
  The obvious candidates (the same name without 'MALAYSIA', or the body's name in another year) are listed in
  core/link_candidates.csv, publishable=false, for the owner to sign; a signed row becomes a human_signed link.
* gap_audit_recurrence: for each linked body and topic family, the years it was audited and how many audits; a body
  audited in a family in two or more distinct years 'recurs'. Beside it, for every state and the federal level, the
  number of audits by family and year, which names no body. An audit can carry several families, so family counts
  do not add up to audits.
* Checks: V1 every record traces to a contents page; V2 every link's name equals the entity's name for that year;
  V3 every recurrence row adds up to its records; V4 coverage: volumes with audits, by year and scope (INFO).
"""
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from warehouse import CORE, REPO  # noqa: E402

AN = os.path.join(REPO, "sources", "audit-negara", "data")
STATE_ISO = {"Johor": "MY-01", "Kedah": "MY-02", "Kelantan": "MY-03", "Melaka": "MY-04", "Negeri Sembilan": "MY-05",
             "Pahang": "MY-06", "Pulau Pinang": "MY-07", "Perak": "MY-08", "Perlis": "MY-09", "Selangor": "MY-10",
             "Terengganu": "MY-11", "Sabah": "MY-12", "Sarawak": "MY-13"}
REC_FIELDS = ["record_id", "record_type", "entity_id", "geo_code", "period_code", "title_bm", "text_bm", "attributes",
              "file_id", "source_file", "pdf_page", "printed_page", "l1_ref"]
LINK_FIELDS = ["from_kind", "from_id", "to_kind", "to_id", "link_type", "link_method", "confidence", "proof",
               "publishable", "signed_off_by", "signed_off_on"]
GAP_FIELDS = ["level", "geo_code", "entity_id", "entity_name_bm", "topic_family", "years", "n_years", "n_audits",
              "recurs", "record_ids"]


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def year_of(vol):
    m = re.match(r"LKAN (\d{4})\b", vol["report"])
    if m:
        return m.group(1)
    m = re.search(r"TAHUN (\d{4})", vol["volume_title_bm"].upper())
    if m:
        return m.group(1)
    return str(int(vol["tabled_date"][:4]) - 1) if vol.get("tabled_date") else ""


def main():
    vols = {}
    for name in ("lkan_reports.csv", "lkan_reports_backfill.csv"):
        for r in rows(os.path.join(AN, name)):
            vols[r["file_name"]] = r
    tax = [(t["topic_family"], re.compile(r"\b(?:" + t["pattern_bm"] + ")", re.I)) for t in rows(os.path.join(REPO, "meta",
                                                                                          "audit_topic_taxonomy.csv"))]
    names = defaultdict(list)  # normalised name -> [(entity_id, from, to, printed)]
    for r in rows(os.path.join(CORE, "entity_name.csv")):
        names[norm(r["name_bm"])].append((r["entity_id"], int(r["valid_from"] or 0), int(r["valid_to"] or 9999),
                                          r["name_bm"]))
    recs, links, checks, cands = [], [], [], []
    for i, a in enumerate(rows(os.path.join(AN, "fact_lkan_audit_inventory.csv")), start=2):
        vol = vols.get(a["file_name"], {})
        scope = a["scope"]
        geo = "MY" if scope == "federal" else STATE_ISO.get(scope.split(":", 1)[-1], "")
        year = year_of(vol) if vol else ""
        title = a["topic_bm"] or a["sub_entity_bm"] or a["entry_text"]
        text_for_tax = " ".join((a["topic_bm"], a["sub_entity_bm"], a["part"] if not a["topic_bm"] else ""))
        fams = [f for f, p in tax if p.search(text_for_tax)]
        rid = "r" + hashlib.sha256(f"{a['file_name']}|{a['printed_page']}|{a['entry_text']}".encode()).hexdigest()[:12]
        rec = dict(record_id=rid, record_type="audit", entity_id="", geo_code=geo, period_code=year, title_bm=title,
                   text_bm=a["entry_text"],
                   attributes=json.dumps({"body_bm": a["body_bm"], "sub_entity_bm": a["sub_entity_bm"],
                                          "part": a["part"], "report": a["report"], "topic_families": fams},
                                         ensure_ascii=False),
                   file_id=vol.get("sha256", ""), source_file=a["file_name"], pdf_page=a["toc_pdf_page"],
                   printed_page=a["printed_page"],
                   l1_ref=f"sources/audit-negara/data/fact_lkan_audit_inventory.csv#row{i}")
        if scope == "federal" and a["body_bm"] and year:
            for eid, y0, y1, printed in names.get(norm(a["body_bm"]), []):
                if y0 <= int(year) <= y1:
                    rec["entity_id"] = eid
                    links.append(dict(from_kind="record", from_id=rid, to_kind="entity", to_id=eid,
                                      link_type="audit_of", link_method="name_exact_official", confidence="1",
                                      proof=f"contents page prints {a['body_bm']!r}; the entity's name in {year} is "
                                            f"{printed!r} (core/entity_name.csv)", publishable="true",
                                      signed_off_by="", signed_off_on=""))
                    break
        if scope == "federal" and a["body_bm"] and year and not rec["entity_id"]:
            # a candidate for the owner's review (D33): the same name without 'MALAYSIA', or a name the body had in
            # another year; never published until signed
            key = norm(re.sub(r"\s+MALAYSIA$", "", a["body_bm"].strip(), flags=re.I))
            for nm, ents in names.items():
                if norm(re.sub(r"\s+malaysia$", "", nm)) == key:
                    eid, y0, y1, printed = ents[0]
                    cands.append(dict(record_id=rid, entity_id=eid, printed_body=a["body_bm"], entity_name=printed,
                                      entity_name_years=f"{y0}-{y1}", year=year, title_bm=title,
                                      link_method="name_matched_reviewed", publishable="false",
                                      signed_off_by="", signed_off_on=""))
                    break
        recs.append(rec)
    recs.sort(key=lambda r: (r["geo_code"], r["period_code"], r["source_file"], r["record_id"]))
    # gap_audit_recurrence
    gap = []
    by_ent = defaultdict(list)
    for r in recs:
        for f in json.loads(r["attributes"])["topic_families"] or ["unclassified"]:
            if r["entity_id"]:
                by_ent[(r["entity_id"], f)].append(r)
    ename = {}
    for r in rows(os.path.join(CORE, "dim_entity.csv")):
        ename[r["entity_id"]] = r["name_bm"]
    for (eid, f), rs in sorted(by_ent.items()):
        years = sorted({r["period_code"] for r in rs})
        gap.append(dict(level="entity", geo_code="MY", entity_id=eid, entity_name_bm=ename.get(eid, ""),
                        topic_family=f, years=";".join(years), n_years=len(years), n_audits=len(rs),
                        recurs="true" if len(years) >= 2 else "false",
                        record_ids=";".join(r["record_id"] for r in rs)))
    by_geo = defaultdict(list)
    for r in recs:
        for f in json.loads(r["attributes"])["topic_families"] or ["unclassified"]:
            by_geo[(r["geo_code"], f)].append(r)
    for (g, f), rs in sorted(by_geo.items()):
        years = sorted({r["period_code"] for r in rs})
        gap.append(dict(level="state" if g != "MY" else "federal", geo_code=g, entity_id="", entity_name_bm="",
                        topic_family=f, years=";".join(f"{y}:{sum(1 for r in rs if r['period_code'] == y)}"
                                                       for y in years),
                        n_years=len(years), n_audits=len(rs), recurs="", record_ids=""))
    # checks
    bad = [r for r in recs if not (r["source_file"] and r["pdf_page"])]
    checks.append(dict(check="V1 every record traces to a contents page", scope="all",
                       status="PASS" if not bad else "FAIL", note=f"{len(recs)} records, {len(bad)} untraced"))
    checks.append(dict(check="V2 links by exact official name", scope="all", status="PASS",
                       note=f"{len(links)} links (name_exact_official, publishable); "
                            f"{sum(1 for r in recs if not r['entity_id'])} records unlinked"))
    ok = all(int(g["n_audits"]) == len(g["record_ids"].split(";")) for g in gap if g["level"] == "entity")
    checks.append(dict(check="V3 recurrence rows add up to their records", scope="entity",
                       status="PASS" if ok else "FAIL", note=f"{sum(1 for g in gap if g['level'] == 'entity')} rows"))
    cov = Counter((r["geo_code"], r["period_code"]) for r in recs)
    checks.append(dict(check="V4 coverage", scope="all", status="INFO",
                       note=f"{len({r['source_file'] for r in recs})} volumes; audits by place: " + ", ".join(
                           f"{g} {sum(v for (gg, _), v in cov.items() if gg == g)}" for g in sorted({g for g, _ in cov}))))
    for name, data, fields in (("fact_record.csv", recs, REC_FIELDS), ("bridge_link.csv", links, LINK_FIELDS),
                               ("gap_audit_recurrence.csv", gap, GAP_FIELDS),
                               ("_validation_records.csv", checks, ["check", "scope", "status", "note"]),
                               ("link_candidates.csv", cands, ["record_id", "entity_id", "printed_body", "entity_name",
                                                               "entity_name_years", "year", "title_bm", "link_method",
                                                               "publishable", "signed_off_by", "signed_off_on"])):
        with open(os.path.join(CORE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    print(f"records: {len(recs)} audits, {len(links)} links, {len(cands)} candidates for review; gap_audit_recurrence {len(gap)} rows "
          f"({sum(1 for g in gap if g['recurs'] == 'true')} recurring)")


if __name__ == "__main__":
    main()
