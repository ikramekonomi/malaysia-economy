#!/usr/bin/env python3
"""Build the PKKP query database from the per-year CSV folders.

Run from anywhere:  python3 sources/pkkp/pipeline/build_duckdb.py
Source of truth = the CSVs under sources/pkkp/data/<year>/. This script only builds a
rebuildable DuckDB cache (sources/pkkp/pkkp.duckdb). As more sources land under
sources/<name>/, add their build here or build a consolidated DB in curated/.

Same-named CSVs across year folders are UNIONed (schemas identical by design). Each volume
contributes its own year plus prior-year comparatives, distinguished by (year, source_file);
differences between volumes are RESTATEMENTS, catalogued in the per-year _restatements_*.csv.
"""
import duckdb, glob, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PKKP = os.path.join(ROOT, "sources", "pkkp", "data")
FOLDERS = sorted(glob.glob(os.path.join(PKKP, "20*")))   # 2009 .. 2024
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")

if os.path.exists(DB):
    os.remove(DB)
con = duckdb.connect(DB)

byname = defaultdict(list)
for folder in FOLDERS:
    for path in sorted(glob.glob(f"{folder}/*.csv")):
        name = os.path.basename(path)[:-4]
        if name.startswith("_"):
            name = "meta" + name
        byname[name].append(path)

for name, paths in sorted(byname.items()):
    selects = [f"SELECT * FROM read_csv_auto('{p}', header=true, all_varchar=false)" for p in paths]
    con.execute(f"CREATE TABLE {name} AS " + " UNION ALL BY NAME ".join(selects))
    n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    print(f"{name}: {n} rows ({len(paths)} file(s))")

con.execute("CREATE VIEW v_opex_leaf AS SELECT * FROM fact_opex_detail WHERE row_type='object_aktiviti'")
con.execute("CREATE VIEW v_devex_projects AS SELECT * FROM fact_devex_project WHERE row_type='project'")
print(f"\n{DB}: {os.path.getsize(DB)/1e6:.1f} MB")
con.close()
