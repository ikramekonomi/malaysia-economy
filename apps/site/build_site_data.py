#!/usr/bin/env python3
"""The public site's data: core/ (L2 + L3) exported as static JSON for site/ (no server, no SQL).

  python3 apps/site/build_site_data.py -> site/data/*.json

Every number the site shows comes from these files, and every observation carries its citation (edition, vintage,
table, page, file sha256, L1 row). What is not publishable is not exported:
  * the draft audit records and gap_audit_recurrence (failed blind verification, 2026-11-06);
  * any series whose registry row says no_redistribution (golden rule 10);
  * federal amounts by state where a gap view marks them unpublishable (its own publishable column): blanked.
Survey estimates keep reliability and confidence intervals; places below state are flagged so the site never bands
or ranks them (decision D10).
"""
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "core", "pipeline"))
from warehouse import Warehouse  # noqa: E402

OUT = os.path.join(REPO, "site", "data")
GAPS = {  # file -> (title, the question it answers)
    "gap_need_vs_money": ("Need vs money", "Does money follow need, state by state?"),
    "gap_budget_vs_actual": ("Budget vs actual", "Was the money budgeted spent, ministry by ministry?"),
    "gap_project_budget_vs_actual": ("Projects: tabled vs spent", "Was each development project's money spent?"),
    "gap_revenue_estimate_vs_collected": ("Revenue: estimate vs collected", "Was revenue collected as estimated?"),
    "gap_reported_vs_audited": ("Reported vs audited", "Do MOF, BNM and the audited accounts agree?"),
    "gap_obligations_growth": ("Hidden obligations", "Are guarantees, PFI and commitments growing faster than debt?"),
    "gap_target_vs_outcome": ("Plan target vs outcome", "Did the Twelfth Malaysia Plan hit its 2025 targets?"),
    "gap_federal_vs_state": ("Federal paid vs state received", "Does what the federal government paid match what each state recorded?"),
    "gap_federal_placement": ("Where federal money lands", "How much federal spending can be placed in a state at all?"),
}
# columns that hold a federal amount by state, blanked wherever the view's own `publishable` says false
WITHHELD = {"gap_federal_placement": ("projects_stated_rm", "projects_parsed_rm", "grants_by_name_rm",
                                      "grants_split_by_payer_rm", "placed_rm", "projects_multiple_states_rm",
                                      "projects_peninsula_rm", "projects_none_rm", "not_itemised_rm")}
DROP_COLS = {"release_id", "source_obs_ids", "federal_source_obs_ids", "federal_flow_ids", "record_ids", "state_obs_id"}


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    if v in (None, ""):
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 1e15 else f
    except ValueError:
        return v


def write(name, data):
    p = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def warehouse_scale(cat, w):
    """The size of the warehouse, counted from the repository itself (for the About page)."""
    import glob

    def n(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            return max(0, sum(1 for _ in f) - 1)
    g = lambda pat: sorted(glob.glob(os.path.join(REPO, pat), recursive=True))
    src = [p for p in g("sources/*/data/**/*.csv") if not os.path.basename(p).startswith("_")]
    checks = g("sources/*/data/**/_validation*.csv") + g("core/**/_validation*.csv") + g("curated/**/_validation*.csv")
    anomalies = g("sources/*/data/**/_source_anomal*.csv")
    l0 = [r for r in rows(os.path.join(REPO, "meta", "l0_archive.csv")) if r["status"] == "ARCHIVED"]
    held = [r for r in w.registry if r["status"] in ("verified", "extracted", "held")]
    years = [int(c[k][:4]) for c in cat for k in ("first", "last") if c[k][:4].isdigit()]
    suite = open(os.path.join(REPO, "qa", "run_offline_suite.py"), encoding="utf-8").read()
    suite = suite[suite.index("SUITE = ["):]
    return {"source_tables": len(src), "source_rows": sum(map(n, src)), "checks": sum(map(n, checks)),
            "anomalies": sum(map(n, anomalies)), "l0_files": len(l0),
            "l0_gb": round(sum(int(r["size_bytes"] or 0) for r in l0) / 1e9, 1),
            "series_held": len(held), "publishers": len({r["publisher"] for r in held}),
            "eval_questions": len(rows(os.path.join(REPO, "qa", "eval_questions.csv"))),
            "ci_scripts": suite[:suite.index("]")].count('"') // 2,
            "first_year": min(years), "last_year": max(years)}


def main():
    w = Warehouse()
    themes = {r["code"]: r["label_en"] for r in rows(os.path.join(REPO, "meta", "code_list.csv"))
              if r["code_list"] == "theme"}
    caveats = {k: v.get("text_en") or v.get("note") or v.get("caveat_en") or "" for k, v in w.caveats.items()}
    blocked = {r["series_id"] for r in w.registry if r["redistribution"] == "no_redistribution"}
    by_ind = defaultdict(list)
    for r in w.obs:
        by_ind[r["indicator_code"]].append(r)
    cat = []
    for code, rs in sorted(by_ind.items()):
        meta = w.ind.get(code) or w.all_ind.get(code, {})
        if meta.get("source_dataset", "").split(":")[-1] in blocked:
            continue
        eds, cites, out = {}, {}, []
        for r in rs:
            e = eds.setdefault(r["edition_id"], len(eds))
            ck = (r["table_ref"], r["pdf_page"], r["printed_page"], r["file_id"])
            c = cites.setdefault(ck, len(cites))
            caps = w.caveats_for(r)
            out.append([r["geo_code"], r["period_code"], r["breakdown_key"], num(r["value"]), e, r["basis"],
                        r["status"], num(r["ci_low"]), num(r["ci_high"]), r["reliability"], c, r["l1_ref"],
                        ";".join(caps)])
        geos = sorted({r["geo_code"] for r in rs})
        levels = sorted({w.geo.get(g, {}).get("geo_level", "") for g in geos})
        periods = sorted({r["period_code"] for r in rs})
        brk = sorted({r["breakdown_key"] for r in rs})
        write(f"ind/{code}.json", {
            "code": code, "cols": ["geo", "period", "breakdown", "value", "edition", "basis", "status", "ci_low",
                                   "ci_high", "reliability", "cite", "l1_ref", "caveats"],
            "rows": out,
            "editions": [{"id": k, "publisher": k.split(":")[0], "vintage": k.split("@")[-1] if "@" in k else ""}
                         for k in eds],
            "cites": [{"table": t, "pdf_page": pp, "printed_page": pr, "sha256": sh} for (t, pp, pr, sh) in cites]})
        cat.append({"code": code, "name": meta.get("name_en", code), "name_bm": meta.get("name_bm", ""),
                    "theme": (meta.get("theme") or "").split(";")[0], "definition": meta.get("definition", ""),
                    "unit": meta.get("unit", ""), "statistic": meta.get("statistic", ""),
                    "universe": meta.get("universe", ""), "price_basis": meta.get("price_basis", ""),
                    "additive_geo": meta.get("additive_geo", ""), "coverage_note": meta.get("coverage_note", ""),
                    "source": meta.get("source_dataset", ""), "n": len(out), "levels": levels,
                    "first": periods[0] if periods else "", "last": periods[-1] if periods else "",
                    "n_geo": len(geos), "breakdowns": brk[:400], "n_breakdowns": len(brk),
                    "publishers": sorted({k.split(":")[0] for k in eds})})
    write("catalogue.json", cat)
    write("geo.json", [{"code": g, "level": v["geo_level"], "name": v["name_en"] or v["name_bm"], "name_bm": v["name_bm"],
                        "parent": v["parent_geo_code"]} for g, v in w.geo.items()])
    write("themes.json", themes)
    write("caveats.json", caveats)
    breaks = [{k: b[k] for k in b} for b in w.breaks]
    write("breaks.json", breaks)
    reg = [{k: r[k] for k in ("series_id", "theme", "publisher", "title_en", "status", "geo_depth", "frequency",
                              "held_coverage", "missing_coverage", "licence", "redistribution", "priority")}
           for r in w.registry]
    write("registry.json", reg)
    gaps = []
    for name, (title, q) in GAPS.items():
        p = os.path.join(REPO, "core", f"{name}.csv")
        if not os.path.exists(p):
            continue
        rs = rows(p)
        cols = [c for c in rs[0].keys() if c not in DROP_COLS] if rs else []
        data = []
        for r in rs:
            if r.get("publishable") == "false" and r.get("geo_code") != "MY":
                # a federal amount by state the view marks unpublishable: withheld (the share placed is kept)
                for c in WITHHELD.get(name, ()):
                    r[c] = ""
            data.append([num(r[c]) if c not in ("geo_code", "year", "status", "note", "caveats") else r[c]
                         for c in cols])
        write(f"gap/{name}.json", {"name": name, "title": title, "question": q, "cols": cols, "rows": data})
        gaps.append({"name": name, "title": title, "question": q, "n": len(data)})
    write("gaps.json", gaps)
    # development votes (P.xx) -> the body that holds them, by its latest name (for the projects comparison)
    names = defaultdict(list)
    for r in rows(os.path.join(REPO, "core", "entity_name.csv")):
        names[r["entity_id"]].append(r)
    votes = {}
    for r in rows(os.path.join(REPO, "core", "bridge_entity_code.csv")):
        if r["code_system"] == "maksud_pembangunan":
            ns = sorted(names.get(r["entity_id"], []), key=lambda x: x["valid_to"] or "9999")
            votes[r["code"]] = {"entity_id": r["entity_id"], "name": (ns[-1]["name_en"] or ns[-1]["name_bm"]) if ns else ""}
    write("votes.json", votes)
    scale = warehouse_scale(cat, w)
    lv = defaultdict(int)
    for r in w.obs:
        lv[w.geo.get(r["geo_code"], {}).get("geo_level", "")] += 1
    write("meta.json", {"release_id": w.release_id, "observations": len(w.obs), "indicators": len(cat),
                        "places": len(w.geo), "by_level": lv, "series_registered": len(w.registry),
                        "series_held": sum(1 for r in w.registry if r["status"] in ("verified", "extracted", "held")),
                        "gap_views": len(gaps), "built_from": "core/ at " + w.release_id, "scale": scale})
    print(f"site data: {len(cat)} indicators, {len(gaps)} gap views -> {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
