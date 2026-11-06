#!/usr/bin/env python3
"""Build the consolidated multi-source warehouse DuckDB.

Run from anywhere:  python3 curated/pipeline/build_warehouse_duckdb.py

Source of truth = the CSVs under sources/<name>/data/ and curated/ (never the .duckdb).
This script only builds a rebuildable cache (curated/warehouse.duckdb). It does NOT
replace sources/pkkp/pkkp.duckdb (sources/pkkp/pipeline/build_duckdb.py) — that file stays the
quick, PKKP-only entry point docs/ANALYST_GUIDE.md already points to. This one is the
"query all eight sources from one file" entry point once you're past PKKP-only questions.

NAMESPACING (CLAUDE.md golden rule: sources are namespaced and never merged)
-----------------------------------------------------------------------------
Each source gets its own DuckDB SCHEMA, named after its folder (hyphens -> underscores):
    pkkp, anggaran, anggaran_hasil, mof_fiscal_outlook, audit_negara, states, bnm, dosm
plus a `curated` schema for the consolidated/gap-view layer. This mirrors the repo's own
"namespaced, consolidate only on top" rule at the database level: a table name never has
to be reused across sources because each source lives in its own schema
(e.g. `pkkp.fact_revenue` vs a same-named table in another source would never collide).
Query fully-qualified: SELECT * FROM anggaran.fact_anggaran_maksud_2024.

TABLE NAMING WITHIN A SOURCE
-----------------------------
Same rule as sources/pkkp/pipeline/build_duckdb.py: files are grouped by exact basename (no year/state
suffix stripping) and UNIONed BY NAME across folders that share it. This unions PKKP's
per-year files into one series per concept, but leaves e.g. states' per-state files
(fact_state_finance_pahang.csv, fact_state_finance_sabah.csv, ...) as separate tables,
since their basenames differ — same "own-year/own-state file first, consolidate in one
place" pattern the source already uses (states' own cross-state panel lives under
data/_national/ and becomes its own table here, e.g. states.fact_state_finance_all).
Leading-underscore files (validation, anomalies, dropped rows, crosswalks, restatements)
get a `meta_` prefix, same convention as sources/pkkp/pipeline/build_duckdb.py.

EXCLUSIONS
----------
Files with "TEMPLATE" in the name (e.g. mof-fiscal-outlook's _TEMPLATE_headline.csv) are
blank schema templates, not data, and are skipped.

A file that fails to load (inconsistent schema across a UNION, a parse error) is reported
and skipped rather than aborting the whole build — with 8 sources and ~900 files, one bad
file should not block querying the other 899.
"""
import duckdb, glob, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
ROOT = os.path.dirname(CURATED)
SOURCES_DIR = os.path.join(ROOT, "sources")
DB = os.path.join(CURATED, "warehouse.duckdb")

SOURCES = ["pkkp", "anggaran", "anggaran-hasil", "mof-fiscal-outlook",
           "audit-negara", "states", "bnm", "dosm"]


def schema_name(source):
    return source.replace("-", "_")


def group_by_basename(files):
    byname = defaultdict(list)
    for path in files:
        name = os.path.basename(path)[:-4]
        if "TEMPLATE" in name.upper():
            continue
        if name.startswith("_"):
            name = "meta" + name
        byname[name].append(path)
    return byname


def load_group(con, schema, name, paths, failures):
    def build_sql(extra_opts=""):
        selects = [f"SELECT * FROM read_csv_auto('{p}', header=true, all_varchar=false{extra_opts})"
                   for p in paths]
        return f'CREATE TABLE {schema}."{name}" AS ' + " UNION ALL BY NAME ".join(selects)

    try:
        con.execute(build_sql())
    except Exception as e1:
        # A well-formed RFC4180 file (quoted fields with embedded commas/thousand
        # separators) can still trip DuckDB's dialect sniffer on its sampled rows.
        # Retry once with strict_mode=false before giving up — this changes how the
        # file is *parsed*, never the values read from it.
        try:
            con.execute(build_sql(", strict_mode=false"))
            print(f"  [strict_mode=false fallback] {schema}.{name}")
        except Exception as e2:
            print(f"  [SKIPPED] {schema}.{name}: {e2}")
            failures.append((schema, name, paths, str(e2)))
            return 0
    n = con.execute(f'SELECT count(*) FROM {schema}."{name}"').fetchone()[0]
    print(f"  {schema}.{name}: {n} rows ({len(paths)} file(s))")
    return n


def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)

    failures = []
    total_rows = 0
    total_tables = 0

    for source in SOURCES:
        schema = schema_name(source)
        print(f"=== {source} -> schema {schema} ===")
        con.execute(f"CREATE SCHEMA {schema}")
        data_dir = os.path.join(SOURCES_DIR, source, "data")
        files = sorted(glob.glob(os.path.join(data_dir, "**", "*.csv"), recursive=True))
        byname = group_by_basename(files)
        for name, paths in sorted(byname.items()):
            total_rows += load_group(con, schema, name, paths, failures)
            total_tables += 1

    print("=== curated -> schema curated ===")
    con.execute("CREATE SCHEMA curated")
    curated_files = sorted(glob.glob(os.path.join(CURATED, "**", "*.csv"), recursive=True))
    # pipeline/ has no CSVs (code only). Model output lives in apps/models/, outside
    # the warehouse, and is deliberately not loaded.
    byname = group_by_basename(curated_files)
    for name, paths in sorted(byname.items()):
        total_rows += load_group(con, "curated", name, paths, failures)
        total_tables += 1

    # meta: the document registry, code lists and decisions, stored as data (DATA_MODEL.md §9).
    print("=== meta -> schema meta ===")
    con.execute("CREATE SCHEMA meta")
    meta_files = sorted(glob.glob(os.path.join(ROOT, "meta", "*.csv")))
    meta_files.append(os.path.join(ROOT, "docs", "registry", "series_seed.csv"))
    for path in meta_files:
        name = "registry_series" if path.endswith("series_seed.csv") else os.path.basename(path)[:-4]
        total_rows += load_group(con, "meta", name.lstrip("_"), [path], failures)
        total_tables += 1

    # core: the conformed L2 layer (DATA_MODEL.md §4-5, §10), built by core/pipeline/build_core.py.
    print("=== core -> schema core ===")
    con.execute("CREATE SCHEMA core")
    # read as text, then `value` as an exact DECIMAL(38,6) (no binary floats in L2, D11)
    for path in sorted(glob.glob(os.path.join(ROOT, "core", "*.csv"))):
        name = os.path.basename(path)[:-4].lstrip("_")
        cast = " REPLACE (CAST(value AS DECIMAL(38,6)) AS value)" if name == "fact_observation" else ""
        con.execute(f'CREATE TABLE core."{name}" AS SELECT *{cast} FROM '
                    f"read_csv('{path}', header=true, all_varchar=true, quote='\"', escape='\"')")
        n = con.execute(f'SELECT count(*) FROM core."{name}"').fetchone()[0]
        print(f"  core.{name}: {n} rows")
        total_rows += n
        total_tables += 1

    # Convenience views carried over from sources/pkkp/pipeline/build_duckdb.py (leaf rows only).
    con.execute("CREATE VIEW pkkp.v_opex_leaf AS "
                "SELECT * FROM pkkp.fact_opex_detail WHERE row_type='object_aktiviti'")
    con.execute("CREATE VIEW pkkp.v_devex_projects AS "
                "SELECT * FROM pkkp.fact_devex_project WHERE row_type='project'")

    con.close()
    print(f"\n{DB}: {os.path.getsize(DB)/1e6:.1f} MB, {total_tables} tables, {total_rows} rows total")
    if failures:
        print(f"\n{len(failures)} table(s) failed to load and were skipped:")
        for schema, name, paths, err in failures:
            print(f"  - {schema}.{name} ({len(paths)} file(s)): {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
