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
              panel for every year 2009-2024. Basis: audited (PKKP), derived.
  devex_net = gross minus loan recovery. NO figure in this column is hardcoded; each
              one is read from a CSV in this repo and carries its own source_file and
              pdf_page. Two independent publications supply it, kept in SEPARATE columns
              so the two bases are never blended into one series:
                devex_net_rm ...... MOF's own official_actual net-DE, basis
                                    "official_actual (MOF Tinjauan Fiskal)":
                                      FY2017-2019 from the 2021 edition's Jadual 1.1
                                        (sources/mof-fiscal-outlook/data/
                                         2021_public_finance_stats/fact_headline.csv,
                                         line=development_expenditure_net)
                                      FY2024 from the 2026 edition's Jadual 1.1
                                        (sources/mof-fiscal-outlook/data/
                                         fiscal_outlook_headline.csv -- the printed net
                                         and loan-recovery figures live in that row's
                                         note, read with the SAME regex that source's
                                         own validate_headline.py check B uses)
                                    Other years are left NULL: MOF has published them,
                                    but those editions are not yet ingested here.
                devex_net_bnm_rm .. BNM Monthly Statistical Bulletin table 3.1
                                    (sources/bnm/data/msb_3_1.csv, annual rows),
                                    basis "reported (BNM MSB 3.1)" -- a complete
                                    FY2009-2024 series from an independent institution.

  The two agree to RM0.3 juta or better in all four overlap years, so the BNM column is
  a usable stand-in where MOF is missing -- but it is a DIFFERENT publication on a
  DIFFERENT basis and is therefore never merged into devex_net_rm. Take one column or
  the other; do not splice them.

WHAT WAS HARDCODED HERE BEFORE, AND WHY IT IS GONE
----------------------------------------------------
An earlier revision carried FY2020-2023 net devex and FY2020-2024 opex_net as Python
dicts of figures "supplied by the analyst" from Tinjauan Fiskal editions not ingested as
CSVs, and FY2009 gross devex as a literal. All five figures were correct -- each has
since been confirmed against BNM MSB 3.1 to within RM2.2 juta -- but none of them could
be checked from this repository, which is what golden rules 1 (raw CSVs are the source
of truth) and 3 (every row keeps its provenance) exist to prevent. They are replaced by:
  - devex_net: the two CSV-backed columns above;
  - opex_net validation: BNM MSB 3.1 `cur_bud_exp`, a citable independent reference for
    all 16 years rather than 5 unciteable ones;
  - devex_gross FY2009: fact_devex_project's own row_type='grand_total' row, which is
    where that literal came from (49,515,355,570.54 -- confirmed identical).
"""
import csv
import csv as csv_module
import os
import re

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.dirname(HERE)
ROOT = os.path.dirname(CURATED)
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
MOF_STATS_2021 = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data",
                               "2021_public_finance_stats", "fact_headline.csv")
MOF_OUTLOOK_HEADLINE = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data",
                                    "fiscal_outlook_headline.csv")
BNM_MSB_3_1 = os.path.join(ROOT, "sources", "bnm", "data", "msb_3_1.csv")

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
    """Per-ministry gross opex/devex, one row per (canonical_code, jenis, year).

    Every row carries the provenance golden rule 3 requires. Because a row is an
    aggregate over many source rows, `source_file` is the distinct set of volumes those
    rows came from (normally one -- rule 6: each year from its own volume) and
    `pdf_pages` is the page span within it, so any figure here can be taken straight back
    to the printed page it was read from.
    """
    opex_rows = con.execute(
        "SELECT maksud_code, year, sum(sebenar_rm), "
        "  string_agg(DISTINCT source_file, '|'), min(pdf_page), max(pdf_page), "
        "  string_agg(DISTINCT statement, '|'), count(*) "
        "FROM fact_opex_maksud GROUP BY maksud_code, year"
    ).fetchall()

    devex_leaf = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm), "
        "  string_agg(DISTINCT source_file, '|'), min(pdf_page), max(pdf_page), "
        "  string_agg(DISTINCT statement, '|'), count(*) "
        "FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 GROUP BY maksud_code, year"
    ).fetchall()
    devex_2015 = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm), "
        "  string_agg(DISTINCT source_file, '|'), min(pdf_page), max(pdf_page), "
        "  string_agg(DISTINCT statement, '|'), count(*) "
        "FROM fact_devex_maksud "
        f"WHERE year=2015 AND jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}' "
        "GROUP BY maksud_code, year"
    ).fetchall()

    DATASET = {("opex", False): "pkkp.fact_opex_maksud",
               ("devex", False): "pkkp.fact_devex_project (row_type='project')",
               ("devex", True): "pkkp.fact_devex_maksud (FY2015 ministry totals)"}

    agg = {}  # (canonical_code, jenis, year) -> dict
    def absorb(jenis, rows, is_2015_substitute=False):
        for code, year, amt, files, p0, p1, stmts, n in rows:
            canon = code_to_canonical.get(code, code)
            a = agg.setdefault((canon, jenis, year), {
                "amount": 0.0, "raw": set(), "files": set(), "p0": None, "p1": None,
                "stmts": set(), "n": 0,
                "dataset": DATASET[(jenis, is_2015_substitute)]})
            a["amount"] += amt
            a["raw"].add(code)
            a["files"].update(f for f in (files or "").split("|") if f)
            a["stmts"].update(s for s in (stmts or "").split("|") if s)
            a["n"] += n
            a["p0"] = p0 if a["p0"] is None else min(a["p0"], p0)
            a["p1"] = p1 if a["p1"] is None else max(a["p1"], p1)

    absorb("opex", opex_rows)
    absorb("devex", devex_leaf)
    absorb("devex", devex_2015, is_2015_substitute=True)

    out = []
    for (canon, jenis, year), a in sorted(agg.items()):
        note = ""
        if len(a["raw"]) > 1 or sorted(a["raw"])[0] != canon:
            note = f"raw code(s) this year: {','.join(sorted(a['raw']))}"
        if year == 2015 and jenis == "devex":
            note = (note + "; " if note else "") + \
                "FY2015 leaf tier is OCR-provisional; using fact_devex_maksud ministry total"
        out.append({
            "canonical_code": canon, "jenis": jenis, "year": year,
            "amount_rm": round(a["amount"], 2),
            "basis": "audited (PKKP)",
            "measure": "gross",
            "source_dataset": a["dataset"],
            "source_file": ";".join(sorted(a["files"])),
            "pdf_pages": f"{a['p0']}-{a['p1']}" if a["p0"] != a["p1"] else str(a["p0"]),
            "statement": ";".join(sorted(a["stmts"])),
            "n_source_rows": a["n"],
            "raw_codes": ",".join(sorted(a["raw"])),
            "note": note,
        })

    cols = ["canonical_code", "jenis", "year", "amount_rm", "basis", "measure",
            "source_dataset", "source_file", "pdf_pages", "statement", "n_source_rows",
            "raw_codes", "note"]
    with open(OUT_MINISTRY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    multi = sum(1 for r in out if ";" in r["source_file"])
    print(f"{OUT_MINISTRY}: {len(out)} (canonical_code, jenis, year) rows"
          + (f" -- {multi} span more than one source volume" if multi else ""))
    return out


# ---------------------------------------------------------------------------
# Reference series, all loaded from CSVs in this repo. Nothing below is a literal.
# ---------------------------------------------------------------------------

# Tinjauan Fiskal 2021 edition's own Jadual 1.1 (sources/mof-fiscal-outlook/data/
# 2021_public_finance_stats/) -- only rows the edition itself labels official_actual are
# used; its 2020/2021 rows are revised-estimate/budget-estimate and are deliberately NOT
# applied here, because mixing an estimate into an actual-basis series is exactly the
# blending golden rule 2 forbids.
def _load_devex_net_2021_edition():
    out = {}
    if not os.path.exists(MOF_STATS_2021):
        return out
    with open(MOF_STATS_2021, newline="") as f:
        for row in csv_module.DictReader(f):
            if row["line"] == "development_expenditure_net" and row["basis"] == "official_actual":
                out[int(row["target_year"])] = {
                    "amount_rm": float(row["amount_rm_juta"]) * 1e6,
                    "basis": "official_actual (MOF Tinjauan Fiskal)",
                    "source_file": row["source_file"],
                    "pdf_page": row["pdf_page"],
                    "printed_page": row["printed_page"],
                    "source_table": f"Jadual {row['table_no']}",
                }
    return out


# Later Tinjauan Fiskal editions (sources/mof-fiscal-outlook/data/fiscal_outlook_headline.csv)
# publish gross DE as the row value and the printed NET and loan-recovery figures in the
# row's note. That is the source CSV's own convention: its validate_headline.py check B
# parses the note with this exact pattern to prove net = gross - loan recovery against
# the printed page. We read it the same way rather than re-typing the number.
NET_DE_IN_NOTE = re.compile(r"net printed ([\d.]+) after loan recovery ([\d.]+)")


def _load_devex_net_outlook_editions():
    out = {}
    if not os.path.exists(MOF_OUTLOOK_HEADLINE):
        return out
    with open(MOF_OUTLOOK_HEADLINE, newline="") as f:
        for row in csv_module.DictReader(f):
            if row["line"] != "development_expenditure" or row["basis"] != "official_actual":
                continue
            m = NET_DE_IN_NOTE.search(row["note"])
            if not m:
                continue
            year = int(row["target_year"])
            gross, net = float(row["amount_rm_bil"]), float(m.group(1))
            rec = float(m.group(2))
            if abs((gross - rec) - net) > 5e-4:      # the source's own identity must hold
                raise SystemExit(f"fiscal_outlook_headline {year}: printed net {net} != "
                                 f"gross {gross} - loan recovery {rec}")
            out[year] = {
                "amount_rm": net * 1e9,
                "basis": "official_actual (MOF Tinjauan Fiskal)",
                "source_file": row["source_file"],
                "pdf_page": row["pdf_page"],
                "printed_page": row["printed_page"],
                "source_table": "Jadual 1.1 (net in row note)",
            }
    return out


# BNM Monthly Statistical Bulletin table 3.1 "Federal Government Finance" -- annual rows
# only (the `period` column is blank on the annual row and 1Q..4Q on the quarterly ones).
# An independent institution publishing the same concepts as PKKP/MOF, which is what
# makes it usable as a reference rather than a second copy of the same number.
def _load_bnm_msb_3_1():
    out = {}
    if not os.path.exists(BNM_MSB_3_1):
        return out
    with open(BNM_MSB_3_1, newline="") as f:
        for row in csv_module.DictReader(f):
            if row["period"].strip():
                continue                              # quarterly row
            year = int(row["year_dt"])

            def juta(col):
                v = row[col].strip()
                return float(v) * 1e6 if v else None

            out[year] = {
                "opex_rm": juta("cur_bud_exp"),
                "revenue_rm": juta("cur_bud_rev"),
                "devex_gross_rm": juta("dev_exp_gro_dev_exp"),
                "devex_loan_recovery_rm": juta("dev_exp_les_loa_rec"),
                "devex_net_rm": juta("dev_exp_net_dev_exp"),
                "source_file": os.path.relpath(BNM_MSB_3_1, ROOT),
                "endpoint": row["endpoint"],
                "retrieved_date": row["retrieved_date"],
            }
    return out


DEVEX_NET_MOF = {**_load_devex_net_2021_edition(), **_load_devex_net_outlook_editions()}
BNM = _load_bnm_msb_3_1()


def build_headline(con):
    opex_gross = dict(con.execute(
        "SELECT year, sum(sebenar_rm) FROM fact_opex_maksud GROUP BY year"
    ).fetchall())

    devex_gross_leaf = dict(con.execute(
        "SELECT year, sum(sebenar_jumlah_rm) FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 AND year <> 2009 GROUP BY year"
    ).fetchall())
    devex_gross_2015 = con.execute(
        "SELECT sum(sebenar_jumlah_rm) FROM fact_devex_maksud "
        f"WHERE year=2015 AND jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}'"
    ).fetchone()[0]
    # FY2009's leaf tier does not foot to the printed grand total (RM410.6 juta short:
    # several ministries' printed JUMLAH lines exceed their listed projects, and P.26 /
    # P.44 print a zero JUMLAH above non-zero projects -- source-side, kept as printed).
    # The volume's own printed grand-total row is therefore the FY2009 gross figure.
    devex_gross_2009 = con.execute(
        "SELECT sebenar_jumlah_rm FROM fact_devex_project "
        "WHERE year=2009 AND row_type='grand_total'"
    ).fetchone()[0]
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
        mof = DEVEX_NET_MOF.get(year)
        bnm = BNM.get(year, {})

        note_parts = []
        if year == 2015:
            note_parts.append("opex/devex gross use ministry-level totals (FY2015 leaf tier is OCR-provisional)")
        if year == 2009:
            note_parts.append("no aktiviti tier that year; opex_gross from fact_opex_maksud; "
                              "devex_gross from the volume's printed grand-total row "
                              "(the FY2009 leaf tier is RM410.6 juta short of it)")
        if mof is None:
            note_parts.append("devex_net_rm NULL: MOF has published this year's net DE, but the "
                              "Tinjauan Fiskal edition carrying it is not yet ingested here -- "
                              "use devex_net_bnm_rm (a different publication, different basis)")

        out.append({
            "year": year,
            "opex_gross_rm": round(og, 2) if og is not None else None,
            "opex_gross_basis": "audited (PKKP)" if og is not None else None,
            "opex_net_rm": round(on, 2) if on is not None else None,
            "opex_net_basis": "audited (PKKP), derived: gross - transfer to Development Fund"
                              if on is not None else None,
            "transfer_to_dev_fund_rm": round(tr, 2) if tr is not None else None,
            "devex_gross_rm": round(dg, 2) if dg is not None else None,
            "devex_gross_basis": "audited (PKKP)" if dg is not None else None,
            "devex_net_rm": mof["amount_rm"] if mof else None,
            "devex_net_basis": mof["basis"] if mof else None,
            "devex_net_source_file": mof["source_file"] if mof else None,
            "devex_net_source_table": mof["source_table"] if mof else None,
            "devex_net_pdf_page": mof["pdf_page"] if mof else None,
            "devex_net_printed_page": mof["printed_page"] if mof else None,
            "devex_net_bnm_rm": bnm.get("devex_net_rm"),
            "devex_net_bnm_basis": "reported (BNM MSB 3.1)" if bnm else None,
            "devex_net_bnm_source_file": bnm.get("source_file"),
            "devex_loan_recovery_bnm_rm": bnm.get("devex_loan_recovery_rm"),
            "note": "; ".join(note_parts),
        })

    with open(OUT_HEADLINE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    n_mof = sum(1 for r in out if r["devex_net_rm"] is not None)
    print(f"{OUT_HEADLINE}: {len(out)} years "
          f"(devex_net_rm from MOF for {n_mof}, BNM reported series for "
          f"{sum(1 for r in out if r['devex_net_bnm_rm'] is not None)})")
    return out


# Exact identities must hold to the sen. Cross-source comparisons are a different kind of
# check and are reported as a different kind of result: two institutions publishing the
# same concept are allowed to differ, and the size of the difference is the finding --
# so they never carry the word PASS, and a divergence never silently reads as agreement.
IDENTITY_TOL_RM = 0.01
# BNM MSB 3.1 vs PKKP: BNM's federal-government-finance compilation is published to
# RM0.001 juta in the early years and to the sen from FY2018, and its operating-
# expenditure line is a slightly different presentation of the same account. Observed
# spread across FY2009-2024 is under RM1.0 juta on a RM150-320 bil base (<0.0005%).
# The band declares what "the same number" means here; it does NOT excuse a difference.
BNM_AGREEMENT_BAND_RM = 1.0e6


def build_validation(con, headline, ministry_rows):
    checks = []   # [check_type, status, check, computed, reference, diff, band, ref_source]

    def identity(name, computed, reference, ref_source):
        diff = computed - reference
        checks.append(["identity", "PASS" if abs(diff) <= IDENTITY_TOL_RM else "FAIL",
                       name, computed, reference, diff, IDENTITY_TOL_RM, ref_source])

    def agreement(name, computed, reference, ref_source):
        diff = computed - reference
        ok = abs(diff) <= BNM_AGREEMENT_BAND_RM
        checks.append(["cross_source", "AGREE" if ok else "DIVERGE",
                       name, computed, reference, diff, BNM_AGREEMENT_BAND_RM, ref_source])

    by_year = {r["year"]: r for r in headline}

    # A. internal identities: the ministry table must foot to the headline it was built from
    for jenis, hcol in (("opex", "opex_gross_rm"), ("devex", "devex_gross_rm")):
        for year in sorted(by_year):
            got = sum(r["amount_rm"] for r in ministry_rows
                      if r["jenis"] == jenis and r["year"] == year)
            ref = by_year[year][hcol]
            if ref is None:
                continue
            if jenis == "devex" and year == 2009:
                # headline FY2009 uses the volume's printed grand total; the ministry
                # table sums that year's leaf rows, which the volume itself prints short
                # of the grand total. A source-side gap, reported, never closed by us.
                diff = got - ref
                checks.append(["known_gap", "KNOWN_GAP",
                               f"devex ministry sum {year} vs headline printed grand total",
                               got, ref, diff, "",
                               "PKKP FY2009 volume: leaf tier short of its own printed "
                               "grand total (see build_headline note)"])
                continue
            identity(f"{jenis} ministry sum {year} == headline {hcol}", got, ref,
                     "fact_ministry_fiscal.csv (this build)")

    # B. cross-source: BNM MSB 3.1, an independent institution publishing the same lines
    for year in sorted(by_year):
        row, b = by_year[year], BNM.get(year)
        if not b:
            continue
        src = f"BNM MSB 3.1 ({b['source_file']}, annual row, retrieved {b['retrieved_date']})"
        # the BNM row's own identity, to prove we are reading its columns correctly
        if None not in (b["devex_gross_rm"], b["devex_loan_recovery_rm"], b["devex_net_rm"]):
            identity(f"BNM MSB 3.1 {year}: net DE == gross - loan recovery",
                     b["devex_gross_rm"] - b["devex_loan_recovery_rm"], b["devex_net_rm"], src)
        if row["opex_net_rm"] is not None and b["opex_rm"] is not None:
            agreement(f"opex_net {year} (PKKP audited) vs BNM operating expenditure",
                      row["opex_net_rm"], b["opex_rm"], src)
        if row["devex_gross_rm"] is not None and b["devex_gross_rm"] is not None:
            agreement(f"devex_gross {year} (PKKP audited) vs BNM gross DE",
                      row["devex_gross_rm"], b["devex_gross_rm"], src)
        if row["devex_net_rm"] is not None and b["devex_net_rm"] is not None:
            agreement(f"devex_net {year} (MOF official_actual) vs BNM net DE",
                      row["devex_net_rm"], b["devex_net_rm"], src)

    with open(OUT_VALIDATION, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check_type", "status", "check", "computed_rm", "reference_rm",
                    "diff_rm", "band_rm", "reference_source"])
        for c in checks:
            w.writerow([c[0], c[1], c[2],
                        f"{c[3]:.2f}" if isinstance(c[3], float) else c[3],
                        f"{c[4]:.2f}" if isinstance(c[4], float) else c[4],
                        f"{c[5]:.2f}" if isinstance(c[5], float) else c[5],
                        c[6], c[7]])
    n_fail = sum(1 for c in checks if c[1] == "FAIL")
    n_div = sum(1 for c in checks if c[1] == "DIVERGE")
    print(f"{OUT_VALIDATION}: {len(checks)} checks, {n_fail} FAIL, {n_div} DIVERGE")
    for c in checks:
        if c[1] in ("FAIL", "DIVERGE"):
            print(f"  {c[1]}: {c[2]} -> {c[3]:,.2f} vs {c[4]:,.2f} ({c[5]:+,.2f})")
    return n_fail


def main():
    con = duckdb.connect(DB, read_only=True)
    code_to_canonical, _ = build_crosswalk(con)
    ministry_rows = build_ministry_fiscal(con, code_to_canonical)
    headline = build_headline(con)
    n_fail = build_validation(con, headline, ministry_rows)
    con.close()
    if n_fail:
        raise SystemExit(f"{n_fail} validation check(s) FAILED -- see {OUT_VALIDATION}")


if __name__ == "__main__":
    main()
