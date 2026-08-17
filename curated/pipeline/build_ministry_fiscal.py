#!/usr/bin/env python3
"""Ministry lineage crosswalk + canonical ministry/headline fiscal facts.

Run:  python3 curated/pipeline/build_ministry_fiscal.py
Reads : sources/pkkp/pkkp.duckdb   (rebuild first: python3 pipeline/build_duckdb.py)
Writes: curated/dim_maksud_canonical.csv
        curated/fact_ministry_fiscal.csv
        curated/fact_fiscal_headline.csv
        curated/_validation_ministry_fiscal.csv

THE PROBLEM THIS SOLVES
------------------------
dim_maksud carries 93 distinct maksud_code values across FY2009-2024. 70 are present
every year; of those, 29 keep the same code through a genuine ministry rename (portfolios
merged/split under cabinet reshuffles). The other 23 have gaps. Two of those gaps are a
straight ministry renumbering, not a discontinuity:
    B.41/P.41 (Kementerian Pelajaran/Pendidikan) 2009-2014 -> B.63/P.63 2015-2024
    B.49/P.49 (Kementerian Pengajian Tinggi)     2009-2013 -> B.64/P.64 2015-2024
verified by continuity of function (Education / Higher Education) even though the code,
and code_num, change completely (code_num is just the numeric half of maksud_code -- it
is NOT an independent identifier and does not survive a renumbering).

MAPPING RULE (as specified by the analyst, not inferred)
----------------------------------------------------------
1. Codes present all 16 years: canonical code/name = the 2024 code/name.
2. Codes with gaps: canonical code/name = the 2024 code/name where the SAME lineage
   reaches 2024 (the two renumbering pairs above); otherwise = that code's own latest
   available year (it is its own, terminated lineage -- no other code is assumed to be
   its successor without evidence). Missing years are left missing, not interpolated,
   not estimated, not zero-filled.
3. B.64/P.64 (Higher Education) is missing not one but TWO years: 2019 (as expected --
   Higher Ed was folded into the Education ministry under the Pakatan Harapan
   government) AND 2014, which the analyst didn't flag but the data shows plainly:
   B.41 (Education, pre-renumbering)'s FY2014 opex spikes to RM51.6bil against
   RM42.8bil (2013) and RM39.3bil (2015 as B.63) -- and its FY2014 programme list
   includes IPTA (public higher-ed institutions), MQA (Malaysian Qualifications
   Agency), teaching hospitals and KTAR, none of which appear in 2013 or 2015. Higher
   Education was under the Education portfolio for FY2014 too, not just FY2019. Both
   years are assumed folded into Education per the same instruction, flagged in the
   crosswalk note, NOT fabricated as a number anywhere.

Everything else among the 23 gapped codes (B.14, B.15, B.26, B.29, B.32, B.33, B.44, B.50
and their P. pairs) is kept SELF-mapped -- e.g. B.44 (Unity/Culture, 2009 only) is not
merged into B.14 (National Unity, 2020+) despite the thematic echo: an 11-year gap and a
different code_num is not evidence of continuity, and the analyst's rule only pre-approved
the two Education pairs. Flagged in the crosswalk note as a judgment call, open to
override if better evidence turns up (Cabinet reorganisation orders, Bajet footnotes).

MINISTRY-LEVEL FIGURES: gross only
------------------------------------
Per-ministry opex/devex here is always GROSS (each ministry's own recorded spend). The
"net" adjustments below (transfer to the Development Fund; loan recovery) are
whole-of-government netting entries in the Consolidated Revenue Account / Development
Fund -- they have no natural per-ministry attribution in the source, so "net" is a
national-headline-only concept, not a ministry-level one.

  opex:  fact_opex_maksud.sebenar_rm, per (maksud_code, year) -- already ministry-level
         and audited-complete for every year (including FY2015's OCR-provisional leaf
         tier and FY2019's B.05/B.06 print-anomaly leaf gap: both are leaf-tier problems
         that fact_opex_maksud, sourced from the ministry-level statement, does not have).
  devex: fact_devex_project leaf rows (row_type='project'), EXCEPT FY2015 where the leaf
         tier is OCR-provisional -- substituted with fact_devex_maksud excluding the
         literal grand-total label 'JUMLAH PERBELANJAAN PEMBANGUNAN' (verified to
         reconcile to the printed 15-year panel total for FY2015: RM40,767.7m).

NATIONAL HEADLINE: net per MOF Tinjauan Fiskal convention
------------------------------------------------------------
  opex_net  = opex_gross - "Caruman/Pindahan daripada Akaun Hasil Disatukan" (the
              transfer INTO the Development Fund), pulled from PKKP's own 15-year fiscal
              panel for every year 2009-2024. Verified against MOF Tinjauan Fiskal 2026
              (FY2024 official_actual, RM321.509bil) and the user's supplied reference
              figures for FY2020-2024, exact to the ringgit-million.
  devex_net = MOF's own published gross-minus-loan-recovery figure. Verified exact for
              FY2024 against mof_fiscal_outlook.fiscal_outlook_headline (RM82.275bil,
              "net printed 82.275 after loan recovery 1.737"). FY2020-2023 values are
              taken as supplied (sourced by the analyst directly from Tinjauan Fiskal
              dan Anggaran Hasil Kerajaan Persekutuan editions not yet ingested as CSVs).
              FY2009-2019: loan-recovery is NOT available anywhere in this warehouse
              (PKKP's own panel has no "loan recovery" line; older Tinjauan Fiskal
              editions aren't ingested) -- devex_net is left NULL for those years rather
              than silently equated to gross. This is a real, open data gap, not an
              oversight: see the note column and docs/SOURCES.md.
"""
import csv
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
ROOT = os.path.dirname(CURATED)
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")

OUT_CROSSWALK = os.path.join(CURATED, "dim_maksud_canonical.csv")
OUT_MINISTRY = os.path.join(CURATED, "fact_ministry_fiscal.csv")
OUT_HEADLINE = os.path.join(CURATED, "fact_fiscal_headline.csv")
OUT_VALIDATION = os.path.join(CURATED, "_validation_ministry_fiscal.csv")

# Hand-verified lineage merges: raw_code -> canonical_code. Everything not listed here
# is self-mapped (canonical_code = raw_code).
LINEAGE_MERGES = {
    "B.41": "B.63", "P.41": "P.63",   # Kementerian Pelajaran/Pendidikan -> Ministry of Education
    "B.49": "B.64", "P.49": "P.64",   # Kementerian Pengajian Tinggi -> Ministry of Higher Education
}

# Judgment calls made explicit (NOT merged, despite a thematic echo) -- documented so a
# reviewer can override with better evidence.
NOT_MERGED_NOTES = {
    "B.44": "Kementerian Perpaduan, Kebudayaan... (2009 only). Thematically close to "
            "B.14 Kementerian Perpaduan Negara (2020+), but an 11-year gap and a "
            "different code_num is not evidence of continuity -- kept as its own, "
            "terminated lineage (canonical = itself, name as of 2009).",
    "P.44": "See B.44 -- development-vote counterpart.",
    "B.14": "Kementerian Perpaduan Negara (2020+). Possible thematic successor to B.44 "
            "(2009 only) -- not merged, see B.44's note.",
    "P.14": "See B.14 -- development-vote counterpart.",
    "B.64": "No FY2014 or FY2019 row (not just FY2019): both years are Higher Ed "
            "folded into Education (B.41/B.63) -- FY2014 confirmed by B.41's programme "
            "list that year (IPTA, MQA, teaching hospitals, KTAR appear only in 2014). "
            "Left missing, not estimated -- see B.63's figure for those years.",
    "P.64": "See B.64 -- development-vote counterpart.",
}

FY2015_GRAND_TOTAL_LABEL = "JUMLAH PERBELANJAAN PEMBANGUNAN"


def build_crosswalk(con):
    rows = con.execute(
        "SELECT maksud_code, jenis, name_bm, year FROM dim_maksud ORDER BY maksud_code, year"
    ).fetchall()
    by_code = {}
    for code, jenis, name_bm, year in rows:
        by_code.setdefault(code, {"jenis": jenis, "years": {}})
        by_code[code]["years"][year] = name_bm

    out = []
    for code, info in sorted(by_code.items()):
        years = sorted(info["years"])
        latest_year = max(years)
        latest_name = info["years"][latest_year]
        canonical_code = LINEAGE_MERGES.get(code, code)
        if canonical_code != code:
            # pull the canonical code's own latest name/year instead
            c_years = sorted(by_code[canonical_code]["years"])
            canonical_name = by_code[canonical_code]["years"][max(c_years)]
            note = f"merged into {canonical_code} lineage (same ministry, renumbered)"
        else:
            canonical_name = latest_name
            note = NOT_MERGED_NOTES.get(code, "")
        out.append({
            "raw_code": code,
            "jenis": info["jenis"],
            "canonical_code": canonical_code,
            "canonical_name_bm": canonical_name,
            "first_year": min(years),
            "last_year": max(years),
            "n_years": len(years),
            "is_merged": canonical_code != code,
            "note": note,
        })

    with open(OUT_CROSSWALK, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"{OUT_CROSSWALK}: {len(out)} raw codes "
          f"({sum(1 for r in out if r['is_merged'])} merged into a different canonical code)")
    return {r["raw_code"]: r["canonical_code"] for r in out}, \
           {r["raw_code"]: r["canonical_name_bm"] for r in out if not r["is_merged"]}


def build_ministry_fiscal(con, code_to_canonical):
    opex_rows = con.execute(
        "SELECT maksud_code, year, sum(sebenar_rm) FROM fact_opex_maksud "
        "GROUP BY maksud_code, year"
    ).fetchall()

    devex_leaf = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm) FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 GROUP BY maksud_code, year"
    ).fetchall()
    devex_2015 = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm) FROM fact_devex_maksud "
        f"WHERE year=2015 AND jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}' "
        "GROUP BY maksud_code, year"
    ).fetchall()
    devex_rows = devex_leaf + devex_2015

    agg = {}  # (canonical_code, jenis, year) -> [amount, raw_codes_used]
    for code, year, amt in opex_rows:
        canon = code_to_canonical.get(code, code)
        key = (canon, "opex", year)
        a = agg.setdefault(key, [0.0, set()])
        a[0] += amt
        a[1].add(code)
    for code, year, amt in devex_rows:
        canon = code_to_canonical.get(code, code)
        key = (canon, "devex", year)
        a = agg.setdefault(key, [0.0, set()])
        a[0] += amt
        a[1].add(code)

    out = []
    for (canon, jenis, year), (amt, raw_codes) in sorted(agg.items()):
        note = ""
        if len(raw_codes) > 1 or list(raw_codes)[0] != canon:
            note = f"raw code(s) this year: {','.join(sorted(raw_codes))}"
        if year == 2015 and jenis == "devex":
            note = (note + "; " if note else "") + \
                "FY2015 leaf tier is OCR-provisional; using fact_devex_maksud ministry total"
        out.append({
            "canonical_code": canon, "jenis": jenis, "year": year,
            "amount_rm": round(amt, 2), "note": note,
        })

    with open(OUT_MINISTRY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["canonical_code", "jenis", "year", "amount_rm", "note"])
        w.writeheader()
        w.writerows(out)
    print(f"{OUT_MINISTRY}: {len(out)} (canonical_code, jenis, year) rows")


# MOF Tinjauan Fiskal net devex, as supplied by the analyst (sourced directly from
# Tinjauan Fiskal dan Anggaran Hasil Kerajaan Persekutuan editions not yet ingested as
# CSVs in sources/mof-fiscal-outlook/). FY2024 independently verified against
# mof_fiscal_outlook.fiscal_outlook_headline (2026 edition, official_actual).
DEVEX_NET_MOF = {
    2020: 50101.0e6, 2021: 63267.0e6, 2022: 70167.0e6, 2023: 95084.0e6, 2024: 82275.0e6,
}


def build_headline(con):
    opex_gross = dict(con.execute(
        "SELECT year, sum(sebenar_rm) FROM fact_opex_maksud GROUP BY year"
    ).fetchall())

    devex_gross_leaf = dict(con.execute(
        "SELECT year, sum(sebenar_jumlah_rm) FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 GROUP BY year"
    ).fetchall())
    devex_gross_2015 = con.execute(
        "SELECT sum(sebenar_jumlah_rm) FROM fact_devex_maksud "
        f"WHERE year=2015 AND jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}'"
    ).fetchone()[0]
    devex_gross_2009 = 49515355570.54  # PKKP's own validated grand total (source CSV, all checks PASS)
    devex_gross = dict(devex_gross_leaf)
    devex_gross[2015] = devex_gross_2015
    devex_gross[2009] = devex_gross_2009

    # opex net: gross minus transfer to Development Fund, per PKKP's own 15-year panel.
    transfer = dict(con.execute(
        "SELECT year, amount_rm_juta*1e6 FROM fact_timeseries_2010_2024 "
        "WHERE line_item_bm='Caruman daripada Akaun Hasil Disatukan'"
    ).fetchall())
    transfer[2009] = con.execute(
        "SELECT amount_rm_juta*1e6 FROM fact_timeseries_2000_2009 "
        "WHERE section_bm='Penerimaan' AND line_item_bm='Pindahan dari Akaun Hasil Disatukan' "
        "AND year=2009"
    ).fetchone()[0]

    out = []
    for year in range(2009, 2025):
        og = opex_gross.get(year)
        dg = devex_gross.get(year)
        tr = transfer.get(year)
        on = (og - tr) if (og is not None and tr is not None) else None
        dn = DEVEX_NET_MOF.get(year)
        note_parts = []
        if year == 2015:
            note_parts.append("opex/devex gross use ministry-level totals (FY2015 leaf tier is OCR-provisional)")
        if year == 2009:
            note_parts.append("no aktiviti tier that year; opex_gross from fact_opex_maksud")
        if dn is None:
            note_parts.append("devex_net unavailable: no loan-recovery figure in this warehouse for this year "
                               "(pre-2020 Tinjauan Fiskal editions not yet ingested)")
        out.append({
            "year": year,
            "opex_gross_rm": round(og, 2) if og is not None else None,
            "opex_net_rm": round(on, 2) if on is not None else None,
            "transfer_to_dev_fund_rm": round(tr, 2) if tr is not None else None,
            "devex_gross_rm": round(dg, 2) if dg is not None else None,
            "devex_net_rm": dn,
            "devex_net_basis": "official_actual (MOF Tinjauan Fiskal)" if dn is not None else None,
            "note": "; ".join(note_parts),
        })

    with open(OUT_HEADLINE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"{OUT_HEADLINE}: {len(out)} years")
    return out


def build_validation(con, headline):
    checks = []
    # opex_net must exact-match the analyst's supplied reference for 2020-2024
    ref_opex = {2020: 224600.0e6, 2021: 231516.0e6, 2022: 292693.0e6, 2023: 311267.0e6, 2024: 321509.0e6}
    for row in headline:
        y = row["year"]
        if y in ref_opex and row["opex_net_rm"] is not None:
            diff = row["opex_net_rm"] - ref_opex[y]
            checks.append(("PASS" if abs(diff) < 1.5e6 else "FAIL",
                            f"opex_net {y} == supplied reference", row["opex_net_rm"], ref_opex[y], diff))
        if y in DEVEX_NET_MOF:
            checks.append(("PASS", f"devex_net {y} == supplied reference (by construction)",
                            row["devex_net_rm"], DEVEX_NET_MOF[y], 0.0))

    with open(OUT_VALIDATION, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["status", "check", "computed", "reference", "diff"])
        w.writerows(checks)
    n_fail = sum(1 for c in checks if c[0] == "FAIL")
    print(f"{OUT_VALIDATION}: {len(checks)} checks, {n_fail} FAIL")
    return n_fail


def main():
    con = duckdb.connect(DB, read_only=True)
    code_to_canonical, _ = build_crosswalk(con)
    build_ministry_fiscal(con, code_to_canonical)
    headline = build_headline(con)
    n_fail = build_validation(con, headline)
    con.close()
    if n_fail:
        raise SystemExit(f"{n_fail} validation check(s) FAILED -- see {OUT_VALIDATION}")


if __name__ == "__main__":
    main()
