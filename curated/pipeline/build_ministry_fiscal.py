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
    "B.29": "Kementerian Tenaga, Teknologi Hijau dan Air (2009-2018). Thematically close "
            "to B.33 Kementerian Alam Sekitar dan Air (2020-2024) and the gap looks like a "
            "renumbering -- but NOT merged, and here the evidence is positive rather than "
            "merely absent: on the development side P.29 and P.33 both appear in FY2020 "
            "and FY2021, so the two votes demonstrably coexist and cannot be one lineage.",
    "P.29": "See B.29 -- P.29 and P.33 coexist in FY2020-2021, which is what disproves the "
            "merge.",
    "B.33": "Kementerian Alam Sekitar dan Air (2020+). See B.29 -- not merged.",
    "P.33": "See B.29 -- development-vote counterpart.",
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
        "  string_agg(DISTINCT statement, '|'), count(sebenar_rm) "
        "FROM fact_opex_maksud GROUP BY maksud_code, year"
    ).fetchall()

    devex_leaf = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm), "
        "  string_agg(DISTINCT source_file, '|'), min(pdf_page), max(pdf_page), "
        "  string_agg(DISTINCT statement, '|'), count(sebenar_jumlah_rm) "
        "FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 GROUP BY maksud_code, year"
    ).fetchall()
    # Leaf rows whose amount cell was never captured. The extraction convention is that a
    # printed en-dash becomes 0.0, so a NULL is OUR gap, not a printed nil -- it must not
    # be summed as zero in silence. FY2009 only (P.26 x11, P.44 x9, P.45 x1).
    devex_leaf_uncaptured = dict(((c, y), n) for c, y, n in con.execute(
        "SELECT maksud_code, year, count(*) FROM fact_devex_project "
        "WHERE row_type='project' AND sebenar_jumlah_rm IS NULL GROUP BY 1, 2"
    ).fetchall())
    devex_2015 = con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm), "
        "  string_agg(DISTINCT source_file, '|'), min(pdf_page), max(pdf_page), "
        "  string_agg(DISTINCT statement, '|'), count(sebenar_jumlah_rm) "
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
                "stmts": set(), "n": 0, "uncaptured": 0,
                "dataset": DATASET[(jenis, is_2015_substitute)]})
            if jenis == "devex" and not is_2015_substitute:
                a["uncaptured"] += devex_leaf_uncaptured.get((code, year), 0)
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
        if a["uncaptured"]:
            note = (note + "; " if note else "") + (
                f"UNDERSTATED: {a['uncaptured']} leaf row(s) have no captured amount in the "
                "source CSV and contribute nothing to this total -- an extraction gap on our "
                "side, not a printed nil (see _known_extraction_defects_curated.csv)")
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
            "n_source_rows_uncaptured": a["uncaptured"],
            "data_quality": "suspect" if a["uncaptured"] else "ok",
            "raw_codes": ",".join(sorted(a["raw"])),
            "note": note,
        })

    cols = ["canonical_code", "jenis", "year", "amount_rm", "basis", "measure",
            "data_quality", "source_dataset", "source_file", "pdf_pages", "statement",
            "n_source_rows", "n_source_rows_uncaptured", "raw_codes", "note"]
    with open(OUT_MINISTRY, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    multi = sum(1 for r in out if ";" in r["source_file"])
    suspect = [r for r in out if r["data_quality"] == "suspect"]
    print(f"{OUT_MINISTRY}: {len(out)} (canonical_code, jenis, year) rows"
          + (f" -- {multi} span more than one source volume" if multi else ""))
    for r in suspect:
        print(f"  data_quality=suspect: {r['canonical_code']} {r['jenis']} {r['year']} "
              f"({r['n_source_rows_uncaptured']} uncaptured leaf row(s))")
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


# The Consolidated Revenue Account (Nota 5 / Penyata Akaun Hasil Disatukan) prints, on one
# page and to the sen, all three national operating-expenditure figures: the total before
# the transfer to the Development Fund, the transfer itself, and the total after it. They
# are read straight off that statement -- NOT derived by subtracting a figure from the
# 15-year fiscal panel, which publishes in RM juta and whose rounding was silently
# entering opex_net at up to RM930,380 a year.
#
# The printed labels change with the volume era, so each year's three rows are resolved by
# label and then proved: net + transfer must equal gross to the sen, or the build stops.
RACCT_TRANSFER = "Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan"
RACCT_NET = ("sebelum pindahan", "tanpa pindahan")     # 2011-2024 / 2009
RACCT_GROSS = ("selepas pindahan",)                    # 2010-2024
RACCT_GROSS_2009 = "Jumlah Perbelanjaan Mengurus"      # the FY2009 volume prints no suffix


def _load_revenue_account(con):
    """Per year: the printed before-transfer, transfer and after-transfer figures."""
    rows = con.execute(
        "SELECT year, line_item_bm, row_type, sebenar_rm, source_file, pdf_page, "
        "       printed_page, statement "
        "FROM fact_revenue_account_statement WHERE sebenar_rm IS NOT NULL"
    ).fetchall()
    out = {}
    for year, label, row_type, amt, sfile, pdfp, prp, stmt in rows:
        low = label.lower()
        prov = {"source_file": sfile, "pdf_page": pdfp, "printed_page": prp,
                "statement": stmt}
        y = out.setdefault(year, {})
        if label == RACCT_TRANSFER:
            y["transfer"] = (amt, dict(prov, line=label))
        elif "mengurus" in low and any(k in low for k in RACCT_NET):
            y["net"] = (amt, dict(prov, line=label))
        elif "mengurus" in low and any(k in low for k in RACCT_GROSS):
            y["gross"] = (amt, dict(prov, line=label))
        elif year == 2009 and label == RACCT_GROSS_2009 and row_type == "subtotal":
            y["gross"] = (amt, dict(prov, line=label))
        elif year == 2018 and label == "PERBELANJAAN MENGURUS" and row_type == "subtotal":
            y["net"] = (amt, dict(prov, line=label))

    for year in sorted(out):
        y = out[year]
        # FY2017-2024 volumes label the before-transfer subtotal plainly "PERBELANJAAN
        # MENGURUS" with no suffix; pick it up where the suffixed form is absent.
        if "net" not in y:
            hit = [r for r in rows if r[0] == year and r[2] == "subtotal"
                   and r[1].upper() == "PERBELANJAAN MENGURUS"]
            if hit:
                y["net"] = (hit[0][3], {"source_file": hit[0][4], "pdf_page": hit[0][5],
                                        "printed_page": hit[0][6], "statement": hit[0][7],
                                        "line": hit[0][1]})
        missing = [k for k in ("net", "transfer", "gross") if k not in y]
        if missing:
            raise SystemExit(f"FY{year} revenue account statement: no printed "
                             f"{'/'.join(missing)} row found -- label convention changed?")
        # prove the three rows resolved are really the three rows of one identity
        diff = (y["net"][0] + y["transfer"][0]) - y["gross"][0]
        if abs(diff) > 0.01:
            raise SystemExit(f"FY{year}: printed net {y['net'][0]:,.2f} + transfer "
                             f"{y['transfer'][0]:,.2f} != printed gross "
                             f"{y['gross'][0]:,.2f} (off {diff:,.2f}) -- wrong rows picked")
    return out


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

    racct = _load_revenue_account(con)

    out = []
    for year in range(2009, 2025):
        ra = racct[year]
        og, og_prov = ra["gross"]
        on, on_prov = ra["net"]
        tr, tr_prov = ra["transfer"]
        dg = devex_gross.get(year)
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
            "opex_gross_rm": round(og, 2),
            "opex_gross_basis": "audited (PKKP), as printed",
            "opex_gross_line_bm": og_prov["line"],
            "opex_net_rm": round(on, 2),
            "opex_net_basis": "audited (PKKP), as printed",
            "opex_net_line_bm": on_prov["line"],
            "transfer_to_dev_fund_rm": round(tr, 2),
            "transfer_basis": "audited (PKKP), as printed",
            "opex_source_file": og_prov["source_file"],
            "opex_source_statement": og_prov["statement"],
            "opex_pdf_page": og_prov["pdf_page"],
            "opex_printed_page": og_prov["printed_page"],
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


OUT_DEFECTS = os.path.join(CURATED, "_known_extraction_defects_curated.csv")

# FY2009 per-ministry devex: the leaf tier does not foot to the printed ministry JUMLAH
# for six votes. Each is diagnosed and classified INDIVIDUALLY below, because the four
# possible answers have very different consequences and lumping them together would let
# our own extraction gaps be published as the Accountant-General's inconsistencies:
#
#   ours_proven        we can show the defect is in our extraction
#   ours_suspected     the signature points at our extraction; not provable without the
#                      printed page, which is not in this repo -- so NOT published as a
#                      source finding
#   source_documented  the source itself documents it
#   unproven           neither side established; recorded as open
#
# A leaf-vs-JUMLAH mismatch NOT listed here fails the build. This registry is a list of
# individually-justified exceptions, not a blanket tolerance.
FY2009_DEVEX_LEAF_DEFECTS = {
    "P.45": ("ours_proven",
             "Leaf sum is RM2,563,648.69 under the printed JUMLAH 601,292,384.75. P.45 has "
             "exactly one leaf row with no captured amount -- projek 00616 'Pusat Latihan "
             "Khas', whose anggaran_jumlah_rm is also NULL. A NULL is an uncaptured cell, "
             "not a printed nil (the convention renders a printed en-dash as 0.0), so the "
             "row contributes nothing and the shortfall is consistent with it to the "
             "ringgit. Fix: re-read projek 00616 from the printed page.",
             "sources/pkkp/data/2009/fact_devex_project.csv, P.45 projek 00616"),
    "P.47": ("ours_suspected",
             "Leaf sum is RM424,602,408.94 under the printed JUMLAH -- 82% of the FY2009 "
             "national gap on its own. The JUMLAH row prints 944,340,000.00 in FOUR "
             "columns at once (anggaran_langsung, anggaran_jumlah, sebenar_langsung, "
             "sebenar_jumlah) with pinjaman nil, an exactly-round figure. Four identical "
             "round columns is the signature of one column being read across the row, not "
             "of an audited outturn; 15 of P.47's project rows also carry align_ok=False. "
             "NOT publishable as a source-side inconsistency without re-reading pdf p.144 "
             "(printed p.140), which this repo does not hold.",
             "sources/pkkp/data/2009/fact_devex_maksud.csv, P.47 (pdf p.144)"),
    "P.10": ("unproven",
             "Leaf sum is RM30,000,000.00 -- exactly round -- under the printed JUMLAH. "
             "Unlike P.47 the JUMLAH row itself reads cleanly (anggaran and sebenar "
             "differ, langsung and pinjaman both populated), so the gap sits in the leaf "
             "tier; P.10 has 3 project rows with align_ok=False. An exactly-round RM30 "
             "juta gap is more consistent with a missed or misread leaf row than with an "
             "audited difference, but neither is established without the printed page.",
             "sources/pkkp/data/2009/fact_devex_project.csv, P.10 (pdf p.102)"),
    "P.29": ("unproven",
             "Leaf sum EXCEEDS the printed JUMLAH by RM3,520,172.81 -- the only ministry "
             "where the leaf tier overshoots. 5 project rows carry align_ok=False. Cause "
             "not established; needs pdf p.128 (printed p.124).",
             "sources/pkkp/data/2009/fact_devex_project.csv, P.29 (pdf p.128)"),
    "P.26": ("source_documented",
             "The printed JUMLAH is 0.00 in all six amount columns above 64 project rows "
             "summing RM262,323,513.41. The PKKP source's own validation file records this "
             "as a genuine FY2009 reorganisation (the ministry was transferred out), and "
             "the same file accounts for the resulting RM224,332,507.85 grand-total gap. "
             "Kept as printed. SEPARATELY, 11 of P.26's leaf rows have no captured amount "
             "-- that part is our extraction gap, flagged data_quality='suspect'.",
             "sources/pkkp/data/2009/_validation_checks_2009.csv row 49 (status DOC)"),
    "P.44": ("source_documented",
             "As P.26: printed JUMLAH 0.00 above project rows summing RM5,077,629.38, "
             "documented by the source as the same FY2009 reorganisation. 9 of P.44's leaf "
             "rows have no captured amount -- our gap, flagged data_quality='suspect'.",
             "sources/pkkp/data/2009/_validation_checks_2009.csv row 49 (status DOC)"),
}


def build_defects_register(rows):
    """One row per known, individually-justified exception. Written every build so it
    cannot drift from the checks that produce it."""
    with open(OUT_DEFECTS, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "key", "computed_rm", "printed_rm", "diff_rm",
                    "classification", "diagnosis", "evidence"])
        w.writerows(rows)
    from collections import Counter
    tally = Counter(r[5] for r in rows)
    print(f"{OUT_DEFECTS}: {len(rows)} known defects -- "
          + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))


# Exact identities must hold to the sen. Cross-source comparisons are a different kind of
# check and are reported as a different kind of result: two institutions publishing the
# same concept are allowed to differ, and the size of the difference is the finding --
# so they never carry the word PASS, and a divergence never silently reads as agreement.
IDENTITY_TOL_RM = 0.01
# BNM MSB 3.1 vs PKKP. Once the headline reads the sen-exact printed figures rather than
# a juta-rounded panel line, BNM's operating-expenditure series agrees with the audited
# accounts to within a few hundred ringgit in most years, so the band is set where a real
# difference would show rather than where our own rounding used to hide.
BNM_AGREEMENT_BAND_RM = 100.0e3
# The printed Consolidated Revenue Account and the printed per-maksud statement are two
# tiers of the same audited volume. They tie to the sen in 14 of 16 years; FY2010 (RM0.09)
# and FY2020 (RM1.00) differ by the statements' own ringgit rounding.
CROSS_TIER_BAND_RM = 1.0
# MOF's Tinjauan Fiskal prints net DE in RM juta, so a MOF figure can sit up to half a
# juta from a sen-exact BNM one on nothing but the printing convention. Comparing the two
# at the sen-level band would manufacture five divergences out of MOF's rounding.
MOF_PRINTING_BAND_RM = 0.5e6


def build_validation(con, headline, ministry_rows):
    checks = []   # [check_type, status, check, computed, reference, diff, band, ref_source]

    def add(kind, ok_status, bad_status, name, computed, reference, band, ref_source):
        diff = computed - reference
        checks.append([kind, ok_status if abs(diff) <= band else bad_status,
                       name, computed, reference, diff, band, ref_source])

    def identity(name, computed, reference, ref_source):
        add("identity", "PASS", "FAIL", name, computed, reference, IDENTITY_TOL_RM, ref_source)

    by_year = {r["year"]: r for r in headline}
    racct = _load_revenue_account(con)

    # ---- A. the printed statement's own identity, tier by tier ----------------------
    for year in sorted(by_year):
        row, ra = by_year[year], racct[year]
        src = (f"PKKP {row['opex_source_file']} pdf p.{row['opex_pdf_page']} "
               f"(printed p.{row['opex_printed_page']}), {row['opex_source_statement']}")
        identity(f"opex {year}: printed net + printed transfer == printed gross",
                 row["opex_net_rm"] + row["transfer_to_dev_fund_rm"], row["opex_gross_rm"], src)

    # ---- B. cross-tier: the per-maksud statement against the account it rolls into ---
    for jenis, hcol in (("opex", "opex_gross_rm"), ("devex", "devex_gross_rm")):
        for year in sorted(by_year):
            got = sum(r["amount_rm"] for r in ministry_rows
                      if r["jenis"] == jenis and r["year"] == year)
            ref = by_year[year][hcol]
            if ref is None:
                continue
            if jenis == "devex" and year == 2009:
                # the FY2009 volume's leaf tier does not foot to its own printed grand
                # total. Part of that gap is ours (21 uncaptured leaf cells) and part is
                # the volume's; the decomposition is in _known_extraction_defects_curated
                # .csv and is NOT published as a source-side finding. Recorded, not closed.
                checks.append(["known_gap", "KNOWN_GAP",
                               f"devex ministry sum {year} vs headline printed grand total",
                               got, ref, got - ref, "",
                               "PKKP FY2009 volume: mixed cause, see "
                               "_known_extraction_defects_curated.csv"])
                continue
            add("cross_tier", "PASS", "FAIL",
                f"{jenis} ministry sum {year} vs printed {hcol}", got, ref,
                CROSS_TIER_BAND_RM if jenis == "opex" else IDENTITY_TOL_RM,
                f"PKKP {year} volume, printed statement total")

    # ---- C. per-ministry devex leaf sum vs that ministry's own printed JUMLAH --------
    # The check that isolates an individual ministry's leaf gap instead of lumping every
    # ministry's into one national aggregate.
    # A ministry can print more than one JUMLAH row: FY2019/2020 P.63 prints a JUMLAH for
    # each of its two portfolios (PENDIDIKAN, PENDIDIKAN TINGGI) and then a roll-up
    # (KEMENTERIAN PENDIDIKAN). Summing all of them double-counts. Which row is the
    # roll-up is derived from the table's OWN arithmetic -- the row that equals the sum of
    # the others -- rather than assumed from its label.
    printed_rows = {}
    for code, year, label, amt in con.execute(
            "SELECT maksud_code, year, jumlah_label_bm, sebenar_jumlah_rm "
            "FROM fact_devex_maksud "
            f"WHERE jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}' "
            "AND sebenar_jumlah_rm IS NOT NULL").fetchall():
        printed_rows.setdefault((code, year), []).append((label, amt))
    printed_maksud = {}
    for key, rows_ in printed_rows.items():
        if len(rows_) == 1:
            printed_maksud[key] = rows_[0][1]
            continue
        total = sum(a for _, a in rows_)
        rollup = [a for _, a in rows_ if abs(a - (total - a)) <= IDENTITY_TOL_RM]
        printed_maksud[key] = rollup[0] if len(rollup) == 1 else total
    leaf_by_raw = {(c, y): v for c, y, v in con.execute(
        "SELECT maksud_code, year, sum(sebenar_jumlah_rm) FROM fact_devex_project "
        "WHERE row_type='project' AND year <> 2015 GROUP BY 1, 2").fetchall()}
    defects = []
    for (code, year), leaf in sorted(leaf_by_raw.items()):
        ref = printed_maksud.get((code, year))
        if ref is None:
            continue
        name = f"devex leaf sum {code} {year} vs printed ministry JUMLAH"
        src = f"PKKP {year} fact_devex_maksud (printed JUMLAH row)"
        known = FY2009_DEVEX_LEAF_DEFECTS.get(code) if year == 2009 else None
        if known and abs(leaf - ref) > IDENTITY_TOL_RM:
            cls, diagnosis, evidence = known
            checks.append(["known_defect", f"KNOWN_{cls.upper()}", name, leaf, ref,
                           leaf - ref, "", evidence])
            defects.append(["fact_ministry_fiscal", f"{code} devex 2009", f"{leaf:.2f}",
                            f"{ref:.2f}", f"{leaf - ref:.2f}", cls, diagnosis, evidence])
            continue
        add("cross_tier", "PASS", "FAIL", name, leaf, ref, IDENTITY_TOL_RM, src)

    # ---- D. nothing was summed as zero for want of an extracted cell -----------------
    for r in ministry_rows:
        if r["n_source_rows_uncaptured"]:
            checks.append(["extraction_gap", "UNCAPTURED",
                           f"{r['jenis']} {r['canonical_code']} {r['year']}: "
                           f"{r['n_source_rows_uncaptured']} leaf row(s) with no captured amount",
                           r["amount_rm"], "", "", "",
                           "our extraction gap, not a printed nil -- "
                           "see _known_extraction_defects_curated.csv"])

    # ---- E. FY2015's substituted tier against the printed grand total ---------------
    fy2015 = con.execute(
        "SELECT sum(sebenar_jumlah_rm) FROM fact_devex_maksud "
        f"WHERE year=2015 AND jumlah_label_bm <> '{FY2015_GRAND_TOTAL_LABEL}'").fetchone()[0]
    identity("FY2015 substituted ministry totals == printed 15-year panel total",
             fy2015, 40767711666.67, "PKKP FY2015 volume printed grand total")

    # ---- F. the crosswalk's merges must not join two votes that coexist --------------
    for raw, canon in LINEAGE_MERGES.items():
        both = con.execute(
            "SELECT count(*) FROM (SELECT year FROM dim_maksud WHERE maksud_code=? "
            "INTERSECT SELECT year FROM dim_maksud WHERE maksud_code=?)", [raw, canon]
        ).fetchone()[0]
        checks.append(["identity", "PASS" if both == 0 else "FAIL",
                       f"merge {raw}->{canon}: the two codes never coexist in a year",
                       both, 0, both, 0, "sources/pkkp dim_maksud (all 16 volumes)"])

    # ---- G. cross-source: BNM MSB 3.1, an independent institution --------------------
    for year in sorted(by_year):
        row, b = by_year[year], BNM.get(year)
        if not b:
            continue
        src = f"BNM MSB 3.1 ({b['source_file']}, annual row, retrieved {b['retrieved_date']})"
        if None not in (b["devex_gross_rm"], b["devex_loan_recovery_rm"], b["devex_net_rm"]):
            identity(f"BNM MSB 3.1 {year}: net DE == gross - loan recovery",
                     b["devex_gross_rm"] - b["devex_loan_recovery_rm"], b["devex_net_rm"], src)
        for name, ours, theirs in (
                (f"opex_net {year} (PKKP audited) vs BNM operating expenditure",
                 row["opex_net_rm"], b["opex_rm"]),
                (f"devex_gross {year} (PKKP audited) vs BNM gross DE",
                 row["devex_gross_rm"], b["devex_gross_rm"]),
                (f"devex_net {year} (MOF official_actual, printed in RM juta) vs BNM net DE",
                 row["devex_net_rm"], b["devex_net_rm"])):
            if ours is not None and theirs is not None:
                band = (MOF_PRINTING_BAND_RM if "MOF official_actual" in name
                        else BNM_AGREEMENT_BAND_RM)
                add("cross_source", "AGREE", "DIVERGE", name, ours, theirs, band, src)

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
    build_defects_register(defects)
    n_fail = sum(1 for c in checks if c[1] == "FAIL")
    from collections import Counter
    tally = Counter(c[1] for c in checks)
    print(f"{OUT_VALIDATION}: {len(checks)} checks -- "
          + ", ".join(f"{v} {k}" for k, v in sorted(tally.items())))
    for c in checks:
        if c[1] in ("FAIL", "DIVERGE") or c[1].startswith("KNOWN_OURS"):
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
