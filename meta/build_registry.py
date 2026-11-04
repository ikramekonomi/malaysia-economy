#!/usr/bin/env python3
"""Build the document registry as data, and check it (docs/DOCUMENT_REGISTRY.md, Phase 0).

  python3 meta/build_registry.py

Reads (hand-maintained):
  docs/registry/series_seed.csv     one row per series: status, route, licence, priority ...
  meta/code_list.csv                every controlled vocabulary
Reads (the manifests each source already writes):
  sources/audit-negara/data/lkan_reports_backfill.csv, lkan_reports.csv
  sources/states/data/<state>/state_reports_<state>.csv
  sources/mof-fiscal-outlook/data/_editions_manifest.csv
  sources/dosm/data/_vintage_log.csv            (state = current)
  sources/bnm/data/_vintage_log.csv             (if present)
  sources/{pkkp,anggaran,anggaran-hasil}/data/_documents_manifest.csv  (re-downloaded, identity-checked)
  provenance columns of those sources' data, for any file no manifest covers (no sha256)
Writes (derived, rebuilt every run):
  meta/registry_file.csv          one row per file a held series is built from
  meta/_validation_registry.csv   the checks below

Checks: vocabulary values are in meta/code_list.csv; series ids are unique; every held, extracted
or verified series has at least one file; every file has a sha256 (OPEN until the L0 archive
holds it); every file is archived (OPEN until meta/l0_archive.csv lists it, or git history holds it,
as for API vintages); every held series has its licence recorded (OPEN while `to_confirm`; since G1 was revised on
2026-11-04 this no longer blocks publication). OPEN marks work not yet done; it does not block CI.
FAIL does.
"""
import csv
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SERIES = os.path.join(REPO, "docs", "registry", "series_seed.csv")
CODES = os.path.join(HERE, "code_list.csv")
OUT_FILES = os.path.join(HERE, "registry_file.csv")
OUT_CHECKS = os.path.join(HERE, "_validation_registry.csv")
L0_INDEX = os.path.join(HERE, "l0_archive.csv")
L0_TAG = "l0-archive"
HELD = {"held", "extracted", "verified"}
FIELDS = ["series_id", "edition", "file_name", "source_url", "sha256", "size_bytes", "pages",
          "retrieved_date", "manifest"]

# DOSM dataset id -> registry series (first matching prefix wins)
DOSM_SERIES = [
    ("hospital_beds", "health_facts"), ("healthcare_staff", "health_facts"), ("schools_district", "education_stats"),
    ("enrolment_school_district", "education_stats"), ("teachers_district", "education_stats"),
    ("death_state", "vital_statistics"), ("deaths_state", "vital_statistics"), ("life_expectancy_state", "vital_statistics"),
    ("water_access", "water_access"), ("crime_district", "crime_stats"),
    ("hh_access_amenities", "amenities_access"), ("hh_profile", "dosm_population"),
    ("population_malaysia", "dosm_population"), ("population_state", "population_subnational"),
    ("population_district", "population_subnational"), ("hh_", "hies"), ("hies_", "hies"),
    ("lfs_", "lfs"), ("employment_sector", "lfs"), ("cpi_", "cpi"), ("mcoicop", "cpi"),
    ("gdp_state_", "state_gdp"), ("federal_finance", "dosm_gfs"), ("lookup_federal_finance", "dosm_gfs"),
    ("state_finance", "dosm_gfs"), ("productivity", "productivity"), ("economic_indicators", "national_accounts"),
    ("gdp_", "national_accounts"), ("bop_", "industry_trade"), ("fdi_", "industry_trade"),
    ("ipi", "industry_trade"), ("ppi", "industry_trade"), ("sppi", "industry_trade"),
    ("iowrt", "industry_trade"), ("trade_", "industry_trade"), ("sitc", "industry_trade"), ("bec", "industry_trade"),
]
SHA = re.compile(r"^[0-9a-f]{64}$")


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def rel(path):
    return os.path.relpath(path, REPO)


def manifest_files():
    out = []
    for name in ("lkan_reports_backfill.csv", "lkan_reports.csv"):
        p = os.path.join(REPO, "sources", "audit-negara", "data", name)
        for r in rows(p):
            out.append({"series_id": "lkan_federal" if r["scope"] == "federal" else "lkan_state",
                        "edition": r["report"], "file_name": r["file_name"], "source_url": r["source_url"],
                        "sha256": r["sha256"], "size_bytes": r["size_bytes"], "pages": r["pages"],
                        "retrieved_date": r["retrieved_date"], "manifest": rel(p)})
    for p in sorted(glob.glob(os.path.join(REPO, "sources", "states", "data", "*", "state_reports_*.csv"))):
        for r in rows(p):
            out.append({"series_id": "state_financial_statements", "edition": r["report"],
                        "file_name": r["file_name"], "source_url": r.get("source_url_note", ""),
                        "sha256": r["sha256"], "size_bytes": r["size_bytes"], "pages": r["pages"],
                        "retrieved_date": "", "manifest": rel(p)})
    p = os.path.join(REPO, "sources", "mof-fiscal-outlook", "data", "_editions_manifest.csv")
    for r in rows(p):
        sid = "anggaran_hasil" if r["file"].startswith("buku_anggaran_hasil") else "tinjauan_fiskal"
        out.append({"series_id": sid, "edition": r["edition"], "file_name": r["file"], "source_url": r["url"],
                    "sha256": r["sha256"], "size_bytes": r["bytes"], "pages": r["pages"],
                    "retrieved_date": r["retrieved_date"], "manifest": rel(p)})
    for src, default in (("dosm", None), ("bnm", "bnm_msb")):
        p = os.path.join(REPO, "sources", src, "data", "_vintage_log.csv")
        if not os.path.exists(p):
            continue
        for r in rows(p):
            if r["state"] != "current":
                continue
            sid = default or next((s for pre, s in DOSM_SERIES if r["dataset"].startswith(pre)), "")
            out.append({"series_id": sid, "edition": r["data_as_of"], "file_name": r["file"],
                        "source_url": "", "sha256": r["sha256"], "size_bytes": "", "pages": "",
                        "retrieved_date": r["retrieved_date"], "manifest": rel(p)})
    # series built from volumes another series already holds: link by file name to that manifest
    lkan = {f["file_name"]: f for f in out if f["series_id"] in ("lkan_federal", "lkan_state")}
    used = set()
    for name in ("fact_agensi_sijil_2023.csv", "fact_agensi_sijil_2024.csv", "fact_eselfaudit_registers.csv"):
        p = os.path.join(REPO, "sources", "audit-negara", "data", name)
        used |= {r["source_file"] for r in rows(p) if r.get("source_file")}
    for fn in sorted(used):
        m = lkan.get(fn, {})
        out.append({"series_id": "ag_sijil_eselfaudit", "edition": m.get("edition", ""), "file_name": fn,
                    "source_url": m.get("source_url", ""), "sha256": m.get("sha256", ""),
                    "size_bytes": m.get("size_bytes", ""), "pages": m.get("pages", ""),
                    "retrieved_date": m.get("retrieved_date", ""),
                    "manifest": m.get("manifest", "") + " (via source_file of the AG registers)"})
    # sources whose PDFs were re-downloaded and proved by meta/l0_identity.py
    manifested = {}
    for src, sid in (("pkkp", "pkkp"), ("anggaran", "anggaran_perbelanjaan"), ("anggaran-hasil", "anggaran_hasil")):
        p = os.path.join(REPO, "sources", src, "data", "_documents_manifest.csv")
        if not os.path.exists(p):
            continue
        for r in rows(p):
            manifested.setdefault(src, set()).add(r["file_name"])
            out.append({"series_id": sid, "edition": r["edition"], "file_name": r["file_name"],
                        "source_url": r["source_url"], "sha256": r["sha256"], "size_bytes": r["size_bytes"],
                        "pages": r["pages"], "retrieved_date": r["retrieved_date"], "manifest": rel(p)})
    # the documents their rows cite that no manifest covers yet, without a sha256
    for src, sid in (("pkkp", "pkkp"), ("anggaran", "anggaran_perbelanjaan"), ("anggaran-hasil", "anggaran_hasil")):
        seen = set()
        for p in sorted(glob.glob(os.path.join(REPO, "sources", src, "data", "**", "*.csv"), recursive=True)):
            if os.path.basename(p).startswith("_"):
                continue
            with open(p, newline="") as f:
                r = csv.DictReader(f)
                if not r.fieldnames or "source_file" not in r.fieldnames:
                    continue
                for row in r:
                    name = (row["source_file"] or "").split("/")[-1]
                    if name.lower().endswith(".pdf"):
                        seen.add(name)
        for name in sorted(seen - manifested.get(src, set())):
            out.append({"series_id": sid, "edition": "", "file_name": name, "source_url": "", "sha256": "",
                        "size_bytes": "", "pages": "", "retrieved_date": "",
                        "manifest": f"cited in sources/{src}/data (no manifest yet)"})
    return out


def main():
    series = rows(SERIES)
    codes = {}
    for c in rows(CODES):
        codes.setdefault(c["code_list"], set()).add(c["code"])
    files = manifest_files()
    archived = {r["sha256"] for r in rows(L0_INDEX) if r["status"] == "ARCHIVED"} if os.path.exists(L0_INDEX) else set()
    checks = []

    def check(name, scope, ok, note="", open_=False):
        checks.append([name, scope, "PASS" if ok else ("OPEN" if open_ else "FAIL"), note])

    ids = [s["series_id"] for s in series]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    check("R1 series_id unique", "all", not dup, ", ".join(dup))
    vocab = {"status": "registry_status", "access": "access", "redistribution": "redistribution",
             "contains_personal_data": "contains_personal_data", "priority": "priority", "track": "track"}
    for s in series:
        bad = [f"{col}={s[col]!r}" for col, lst in vocab.items() if s[col] not in codes[lst]]
        bad += [f"theme={t!r}" for t in s["theme"].split(";") if t not in codes["theme"]]
        missing = [c for c in ("title_bm", "title_en", "publisher", "route", "licence") if not s[c].strip()]
        check("R2 vocabulary and required fields", s["series_id"], not bad and not missing,
              "; ".join(bad + [f"missing {m}" for m in missing]))
    known = set(ids)
    orphans = sorted({f["series_id"] or f"(unmapped) {f['file_name']}" for f in files if f["series_id"] not in known})
    check("R3 every file belongs to a registered series", "all", not orphans, ", ".join(orphans[:10]))
    by = {}
    for f in files:
        by.setdefault(f["series_id"], []).append(f)
    for s in series:
        if s["status"] not in HELD:
            continue
        fs = by.get(s["series_id"], [])
        check("R4 held series has files", s["series_id"], bool(fs), f"{len(fs)} file(s)")
        if fs:
            no_sha = [f["file_name"] for f in fs if not SHA.match(f["sha256"] or "")]
            check("R5 every file has a sha256", s["series_id"], not no_sha,
                  f"{len(no_sha)} of {len(fs)} without sha256 (needs the L0 archive)" if no_sha else f"{len(fs)} files",
                  open_=True)
            arch = [f for f in fs if f["sha256"] in archived or "_vintage_log" in f["manifest"]]
            check("R7 every file is in the L0 archive", s["series_id"], len(arch) == len(fs),
                  f"{len(arch)} of {len(fs)} archived (release {L0_TAG} or git history)", open_=True)
        check("R6 licence recorded", s["series_id"], s["licence"] != "to_confirm",
              "licence to_confirm" if s["licence"] == "to_confirm" else s["licence"], open_=True)

    with open(OUT_FILES, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(files, key=lambda r: (r["series_id"], r["edition"], r["file_name"])))
    with open(OUT_CHECKS, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "scope", "status", "note"])
        w.writerows(checks)
    from collections import Counter
    tally = Counter(c[2] for c in checks)
    print(f"{rel(OUT_FILES)}: {len(files)} files; {rel(OUT_CHECKS)}: {len(checks)} checks, "
          + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    for c in checks:
        if c[2] != "PASS":
            print(f"  {c[2]:<5} {c[0]} [{c[1]}] {c[3]}")


if __name__ == "__main__":
    main()
