#!/usr/bin/env python3
"""Build the consolidated pkkp.duckdb from the per-year CSV folders in ../warehouse.

Run from anywhere:  python3 pipeline/build_duckdb.py
Same-named CSVs across year folders are UNIONed (schemas are identical by design).
Each volume contributes its own year plus prior-year comparatives, distinguished by
(year, source_file); differences between volumes are RESTATEMENTS, catalogued in the
per-year _restatements_*.csv files.  The .duckdb is a rebuildable cache — the CSVs are
the source of truth.
"""
import duckdb, glob, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
WH = os.path.normpath(os.path.join(HERE, "..", "warehouse"))
# root folder = 2024 volume; subfolders 2009..2023 = their volumes
FOLDERS = [WH] + [os.path.join(WH, str(y)) for y in range(2009, 2024)]
DB = os.path.join(WH, "pkkp.duckdb")
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

con.execute("""CREATE VIEW v_opex_leaf AS
  SELECT * FROM fact_opex_detail WHERE row_type = 'object_aktiviti'""")
con.execute("""CREATE VIEW v_devex_projects AS
  SELECT * FROM fact_devex_project WHERE row_type = 'project'""")
print(f"\n{DB}: {os.path.getsize(DB)/1e6:.1f} MB")
con.close()
