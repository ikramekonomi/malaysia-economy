#!/usr/bin/env python3
"""OPEX-by-component, OPEX-by-sector, DEVEX-by-sector -- curated pass-through of MOF
Tinjauan Fiskal's own Jadual 3.1/3.2/3.3 tables (finer than anything derivable from PKKP
or DOSM alone -- see sources/mof-fiscal-outlook/README.md).

Run:  python3 curated/pipeline/build_opex_devex_breakdown.py
Reads : curated/warehouse.duckdb (rebuild first: python3 curated/pipeline/build_warehouse_duckdb.py)
Writes: curated/fact_opex_by_component.csv
        curated/fact_opex_by_sector.csv
        curated/fact_devex_by_sector.csv

Currently sourced from a single edition (Tinjauan Fiskal 2021's appendix, 2017-2021).
This script is intentionally a thin per-source union rather than a one-off copy: once a
later edition is ingested into another sources/mof-fiscal-outlook/data/<edition>/ folder
with the same fact_opex_by_component.csv/fact_opex_by_sector.csv/fact_devex_by_sector.csv
basenames, build_warehouse_duckdb.py already UNIONs them BY NAME into one
mof_fiscal_outlook table -- this script only needs a year-precedence rule added (same
"take each year from its own volume" principle as PKKP) if two editions ever cover the
same year with different figures.
"""
import csv
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
ROOT = os.path.dirname(CURATED)
DB = os.path.join(CURATED, "warehouse.duckdb")

OUT_COMPONENT = os.path.join(CURATED, "fact_opex_by_component.csv")
OUT_OPEX_SECTOR = os.path.join(CURATED, "fact_opex_by_sector.csv")
OUT_DEVEX_SECTOR = os.path.join(CURATED, "fact_devex_by_sector.csv")

FIELDS = ["year", "line", "line_bm", "line_en", "level", "parent_line", "amount_rm",
          "pct_share", "basis", "source_edition", "source_table", "source_file",
          "pdf_page", "printed_page", "note"]


def pull(con, table_no):
    rows = con.execute(f"""
        SELECT target_year, line, line_bm, line_en, level, parent_line, amount_rm_juta,
               pct_share, basis, source_file, pdf_page, printed_page, note
        FROM mof_fiscal_outlook.{'fact_opex_by_component' if table_no == '3.1' else
                                  'fact_opex_by_sector' if table_no == '3.2' else
                                  'fact_devex_by_sector'}
        ORDER BY target_year, level, line
    """).fetchall()
    out = []
    for (year, line, line_bm, line_en, level, parent_line, amt_juta, pct, basis,
         source_file, pdf_page, printed_page, note) in rows:
        out.append({
            "year": year, "line": line, "line_bm": line_bm, "line_en": line_en,
            "level": level, "parent_line": parent_line,
            "amount_rm": round(amt_juta * 1e6, 2) if amt_juta is not None else None,
            "pct_share": pct, "basis": basis,
            "source_edition": "tinjauan_fiskal_2021", "source_table": table_no,
            "source_file": source_file, "pdf_page": pdf_page, "printed_page": printed_page,
            "note": note,
        })
    return out


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{path}: {len(rows)} rows")


def main():
    con = duckdb.connect(DB, read_only=True)
    write_csv(OUT_COMPONENT, pull(con, "3.1"))
    write_csv(OUT_OPEX_SECTOR, pull(con, "3.2"))
    write_csv(OUT_DEVEX_SECTOR, pull(con, "3.3"))


if __name__ == "__main__":
    main()
