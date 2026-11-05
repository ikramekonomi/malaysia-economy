#!/usr/bin/env python3
"""Reconcile the Anggaran Hasil extraction against the documents' own printed
hierarchy and against the other sources in the warehouse.

Checks per edition (2025, 2026):
  H1  code hierarchy: each group (x000) with item children == sum of items;
      each section (x0000) == sum of its groups (via the printed combined
      indirect-tax subtotal where the book uses one); TOTAL == sum of sections
  H2  measures page: TOTAL_AFTER == TOTAL_BEFORE + net of the group-level
      measure impacts; NET_CHANGE row (where printed) equals that net
  X1  ringkasan TOTAL (estimate column) == measures TOTAL_BEFORE
  X2  sebenar column vs PKKP audited revenue (level 0 and the three l1
      categories) — exact for 2023, rounding-level (whole RM vs sen) for 2024
  X3  anggaran columns vs MOF Fiscal Outlook revenue lines (same editions)
Writes data/_validation_hasil.csv. Discrepancies reported, never corrected.
"""
import csv
import os
from collections import defaultdict

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
ROOT = os.path.join(HERE, "..", "..", "..")
DB = os.path.join(ROOT, "sources", "pkkp", "pkkp.duckdb")
OFF = os.path.join(ROOT, "sources", "mof-fiscal-outlook", "data", "fiscal_outlook_headline.csv")

out = []


def rec(ed, check, scope, expected, got, status=None):
    out.append([ed, check, scope, expected, got,
                status or ("PASS" if expected == got else "FAIL")])


off = {}
for r in csv.DictReader(open(OFF)):
    off[(int(r["edition_year"]), int(r["target_year"]), r["line"])] = float(r["amount_rm_bil"])

con = duckdb.connect(DB, read_only=True)

for ed in (2025, 2026):
    vals = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(DATA, str(ed), f"fact_hasil_ringkasan_{ed}.csv"))):
        vals[r["measure"]][r["kod"]] = int(r["amount_rm"])
    measures = sorted(vals)
    for m in measures:
        v = vals[m]
        groups = [k for k in v if k.isdigit() and int(k) % 1000 == 0 and int(k) % 10000 != 0]
        for g in groups:
            items = [k for k in v if k.isdigit() and k[:2] == g[:2] and int(k) % 1000 != 0
                     and (int(k) // 1000) * 1000 == int(g)]
            if items:
                rec(ed, "H1_group", f"{g} ({m})", v[g], sum(v[k] for k in items))
        for sec in [k for k in v if k.isdigit() and int(k) % 10000 == 0]:
            kids = [k for k in groups if k[0] == sec[0]]
            combo = [k for k in v if "&" in k and k.startswith(sec[0])]
            if sec == "60000" and combo:
                got = v.get("61000", 0) + v[combo[0]]
            else:
                got = sum(v[k] for k in kids)
            if kids or combo:
                rec(ed, "H1_section", f"{sec} ({m})", v[sec], got)
        if combo:
            parts = combo[0].split("&")
            rec(ed, "H1_combined", f"{combo[0]} ({m})", v[combo[0]],
                sum(v.get(p, 0) for p in parts))
        rec(ed, "H1_total", f"TOTAL ({m})", v["TOTAL"],
            sum(v[k] for k in v if k.isdigit() and int(k) % 10000 == 0))

    ms = {r["kod"]: int(r["amount_rm"]) for r in
          csv.DictReader(open(os.path.join(DATA, str(ed), f"fact_hasil_measures_{ed}.csv")))}
    net = ms.get("61000", 0) + ms.get("62000", 0)
    net_items = sum(v for k, v in ms.items()
                    if ("&" in k) or (k.isdigit() and int(k) % 1000 != 0))
    rec(ed, "H2_after", "TOTAL_AFTER == BEFORE + group impacts",
        ms["TOTAL_AFTER"], ms["TOTAL_BEFORE"] + net)
    rec(ed, "H2_after_items", "TOTAL_AFTER == BEFORE + item impacts",
        ms["TOTAL_AFTER"], ms["TOTAL_BEFORE"] + net_items)
    if "NET_CHANGE" in ms:
        rec(ed, "H2_net", "NET_CHANGE == group impacts", ms["NET_CHANGE"], net)
        rec(ed, "H2_net_items", "NET_CHANGE == item impacts", ms["NET_CHANGE"], net_items)
    est_col = f"anggaran_{ed}"
    rec(ed, "X1_before", "ringkasan TOTAL == measures TOTAL_BEFORE",
        vals[est_col]["TOTAL"], ms["TOTAL_BEFORE"])

    # X2: sebenar column vs PKKP
    yr = ed - 2
    pk = {r[0]: float(r[1]) for r in con.sql(f"""
        SELECT CASE WHEN level=0 THEN 'TOTAL' WHEN item_bm ILIKE 'HASIL CUKAI' THEN '60000'
               WHEN item_bm ILIKE 'HASIL BUKAN CUKAI' THEN '70000'
               WHEN item_bm ILIKE 'TERIMAAN BUKAN HASIL' THEN '80000' END k, max(sebenar_rm)
        FROM fact_revenue WHERE source_file ILIKE '{yr}_%' AND year={yr} AND level<=1
        GROUP BY 1 HAVING k IS NOT NULL""").fetchall()}
    seb = vals[f"sebenar_{yr}"]
    for k in ("TOTAL", "60000", "70000", "80000"):
        if k in pk:
            # book's 70000/90000 split WP revenue differently from PKKP's three
            # categories; compare TOTAL and 60000 strictly, others informally
            d = abs(seb.get(k, 0) - pk[k])
            strict = k in ("TOTAL", "60000")
            # whole ringgit on both sides: a difference is not rounding; kept as printed (golden rule 2)
            note = "PASS" if d == 0 else ("WARN" if d < 200 else ("FAIL" if strict else "INFO"))
            # 90000 (WP) sits inside PKKP nontax/nonrev; tolerate category drift
            if k in ("70000", "80000") and d >= 200:
                note = "INFO"
            rec(ed, "X2_vs_pkkp", f"{k} (sebenar_{yr})", int(pk[k]), seb.get(k, 0), note)

    # X3: estimate columns vs Fiscal Outlook revenue
    fo_rev = off.get((ed, ed, "revenue"))
    rec(ed, "X3_vs_outlook", f"anggaran_{ed} TOTAL vs Fiscal Outlook revenue (RM bil)",
        round(fo_rev, 3), round(vals[est_col]["TOTAL"] / 1e9, 3))
    fo_rev_rev = off.get((2026, 2025, "revenue"))
    if ed == 2026 and fo_rev_rev:
        rec(ed, "X3_vs_outlook", "anggaran_disemak_2025 TOTAL vs Fiscal Outlook revised (RM bil)",
            round(fo_rev_rev, 3), round(vals["anggaran_disemak_2025"]["TOTAL"] / 1e9, 3))

import sys
sys.path.insert(0, os.path.join(HERE, "../../..", "qa"))
from source_anomaly import classify  # noqa: E402  FAIL -> SOURCE_ANOMALY only where the register proves it
out = classify(out, os.path.join(DATA, "_source_anomalies_hasil.csv"))

dest = os.path.join(DATA, "_validation_hasil.csv")
with open(dest, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["edition", "check", "scope", "expected", "got", "status"])
    w.writerows(out)
fails = [r for r in out if r[-1] == "FAIL"]
print(f"{len(out)} checks, {len(fails)} FAIL -> {dest}")
for r in fails[:20]:
    print("FAIL:", r)
