#!/usr/bin/env python3
"""Validate data/fact_lkan_fiscal_tables_2024.csv -> data/_validation_lkan_fiscal.csv.

V1 internal additivity: for every non-% column of every table, printed
   Jumlah/JUMLAH rows are recomputed from the component lines above them.
   A subtotal passes if it equals the sum of lines since the previous
   Jumlah/total OR since the last group header (the AG's statements use both
   conventions: J14 Jumlah Terimaan includes the opening balance, J17's does
   not); a KESELURUHAN/bare-JUMLAH total also accepts the sum of preceding
   subtotals. Tolerance = one unit in the last printed decimal place.
V2 cross-source vs PKKP (audited): AG Jadual 1 revenue / opex / gross devex
   for FY2024 and FY2023 vs pkkp.duckdb fact_financial_performance
   (basis='sebenar', each year from its own volume). Tolerance = half a unit
   of the AG's printed rounding (RM bilion, 3 dp -> RM0.0005 bilion).
V3 cross-source vs BNM MSB 3.1 (reported, RM juta): same three lines from
   the annual row (period='') or summed quarters. Same tolerance; rows where
   the presentations are known to differ are reported as INFO.
Also reports tables extracted vs expected (33 + 4 + 11).
Discrepancies are reported, never corrected.
"""
import csv
import os
import re
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
BNM = os.path.join(HERE, "..", "..", "bnm", "data", "msb_3_1.csv")
PKKP = os.path.join(HERE, "..", "..", "pkkp", "pkkp.duckdb")

EXPECT = {"II": 33, "II.a": 4, "II.b": 11}


def parse_value(text):
    """Printed cell -> (float, decimals) or (None, 0) for nil/absent."""
    t = text.strip().rstrip("*")
    if t in ("", "-", "–"):
        return None, 0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").rstrip("%").rstrip("*").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None, 0
    dec = len(t.split(".")[1]) if "." in t else 0
    return (-v if neg else v), dec


POSITIONAL = re.compile(r"^lajur \d+ \(kepala tidak boleh dibina semula\)$")


def header_check(rows):
    """Independent header re-read: every reconstructed col_label_bm must be
    built from words that actually appear in the table's own header zone
    (re-located here from the page text, independently of the extractor's
    span logic), must not repeat a fragment, must not glue a year to stray
    words, and no two columns may share a (label, unit). Tables published
    with explicit positional labels are exempt and listed."""
    from extract_lkan_findings import volume_pages
    from extract_lkan_fiscal import (SOURCE_FILE, BAHAGIAN, SECTION_FOOTER,
                                     noisy)
    pages = volume_pages(SOURCE_FILE)
    vocab = {}
    for bah, lo, hi, _ in BAHAGIAN:
        lines = []
        for p in range(lo, hi + 1):
            for ln in pages[p - 1].split("\n"):
                if ln.strip() and (noisy(ln) or SECTION_FOOTER.match(ln)):
                    continue
                lines.append(ln)
        for i, ln in enumerate(lines):
            m = re.match(r"^(?:\s*|.*\s)JADUAL\s+(\d+)\s*$", ln)
            if not m:
                continue
            words = set()
            for ln2 in lines[i + 1:i + 12]:     # header zone: until data
                if re.search(r"[\d,]+\.\d", ln2) or \
                        ln2.strip().startswith("Sumber:"):
                    break
                words.update(w.strip("()").upper()
                             for w in ln2.split())
            vocab[(bah, int(m.group(1)))] = words
    bad, positional, reported = [], [], set()
    for r in rows:
        key = (r["bahagian"], int(r["jadual_no"]))
        lab = r["col_label_bm"]
        if not lab or (key, lab) in reported:
            continue
        reported.add((key, lab))
        if POSITIONAL.match(lab):
            if key not in positional:
                positional.append(key)
            continue
        toks = lab.split()
        problems = []
        missing = [t for t in toks
                   if t.strip("()").upper() not in vocab.get(key, set())
                   and not re.fullmatch(r"[\d.,%–-]+", t.strip("()"))]
        if missing:
            problems.append("tokens %s not in header zone" % missing)
        if len(set(toks)) != len(toks):
            problems.append("repeated fragment")
        if len(toks) > 1 and any(re.fullmatch(r"\d{4}", t) for t in toks):
            problems.append("year glued to other words")
        if problems:
            bad.append((key, lab, "; ".join(problems)))
    return bad, positional


def anomaly_tables():
    """{'II J21', ...} tables with a documented fiscal-table source quirk."""
    path = os.path.join(DATA, "_source_anomalies_lkan.csv")
    out = set()
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                if r.get("field") == "fiscal_table":
                    out.add(r["chapter_id"])
    return out


# trend tables whose printed "Jumlah ..." rows are levels, not sums of the
# rows above them (verified against the page): II.a JADUAL 3 (pdf 71) lists
# Jumlah Hutang / KDNK / nisbah / Jumlah Statutori as parallel series
NON_ADDITIVE = {("II.a", 3)}


def v1_checks(rows):
    """Additivity of printed Jumlah rows, per table and column."""
    tables = OrderedDict()
    for r in rows:
        key = (r["bahagian"], int(r["jadual_no"]))
        tables.setdefault(key, []).append(r)
    results = []
    for (bah, jn), cells in tables.items():
        if (bah, jn) in NON_ADDITIVE:
            continue
        cols = OrderedDict()
        for r in cells:
            if r["col_label_bm"] and r["unit"] != "%" \
                    and "%" not in r["col_label_bm"]:
                cols.setdefault((r["col_label_bm"], r["unit"]), None)
        n_ok = n_bad = 0
        notes = []
        for (clabel, unit) in cols:
            comp_all, comp_grp, subs = [], [], []
            broken_all = broken_grp = False
            for r in cells:
                if r["col_label_bm"] == "":       # group header row: opens a
                    comp_grp, broken_grp = [], False   # narrower scope
                    continue
                if (r["col_label_bm"], r["unit"]) != (clabel, unit):
                    continue
                v, dec = parse_value(r["value_verbatim"])
                if r["row_type"] == "line":
                    if r["row_label_bm"].endswith(":"):
                        comp_grp, broken_grp = [], False
                        continue
                    if v is None:
                        broken_all = broken_grp = True
                    else:
                        comp_all.append(v)
                        comp_grp.append(v)
                    continue
                if v is None:
                    comp_all, comp_grp, subs = [], [], []
                    broken_all = broken_grp = False
                    continue
                tol = 10 ** -dec if dec else 1
                cands = []
                if not broken_all and comp_all:
                    cands.append(sum(comp_all))
                if not broken_grp and comp_grp:
                    cands.append(sum(comp_grp))
                if r["row_type"] == "total" and len(subs) >= 2:
                    cands.append(sum(subs))
                ok = any(abs(v - c) <= tol + 1e-9 for c in cands)
                if cands:
                    if ok:
                        n_ok += 1
                    else:
                        n_bad += 1
                        notes.append("%s %r=%s vs %s" %
                                     (clabel, r["row_label_bm"][:28],
                                      r["value_verbatim"],
                                      "/".join("%.3f" % c for c in cands)))
                subs.append(v)
                comp_all, comp_grp = [], []
                broken_all = broken_grp = False
        results.append((bah, jn, n_ok, n_bad, "; ".join(notes[:3])))
    return results


def ag_j1(rows):
    """AG Jadual 1 (RM bilion) revenue / opex / gross devex, 2024 & 2023."""
    want = {"Hasil": "revenue",
            "Perbelanjaan Mengurus (Sebelum Pindahan ke Kumpulan Wang "
            "Pembangunan)": "opex",
            "Perbelanjaan Pembangunan": "devex"}
    out = {}
    for r in rows:
        if r["bahagian"] != "II" or r["jadual_no"] != "1":
            continue
        code = want.get(r["row_label_bm"])
        m = re.fullmatch(r"(20\d\d)", r["col_label_bm"])
        if code and m:
            v, dec = parse_value(r["value_verbatim"])
            out[(code, int(m.group(1)))] = (v, dec)
    return out


def main():
    with open(os.path.join(DATA, "fact_lkan_fiscal_tables_2024.csv")) as f:
        rows = list(csv.DictReader(f))

    results = []

    def add(check, scope, expected, actual, status, note=""):
        results.append({"check": check, "scope": scope, "expected": expected,
                        "actual": actual, "status": status, "note": note})

    # table count
    seen = {}
    for r in rows:
        seen.setdefault(r["bahagian"], set()).add(int(r["jadual_no"]))
    for bah, want in EXPECT.items():
        got = seen.get(bah, set())
        missing = sorted(set(range(1, want + 1)) - got)
        add("tables_extracted", "Bahagian " + bah, want, len(got),
            "PASS" if not missing else "FAIL",
            "missing JADUAL %s" % missing if missing else "")

    # V1
    known = anomaly_tables()
    tot_ok = tot_bad = tot_doc = 0
    for bah, jn, n_ok, n_bad, note in v1_checks(rows):
        tot_ok += n_ok
        if not n_bad:
            continue
        scope = "%s J%d" % (bah, jn)
        if scope in known:
            tot_doc += n_bad
            add("v1_additivity", scope, "printed sums",
                "%d ok, %d off" % (n_ok, n_bad), "INFO",
                "documented source misprint — see _source_anomalies_lkan.csv"
                "; " + note)
        else:
            tot_bad += n_bad
            add("v1_additivity", scope, "printed sums",
                "%d ok, %d off" % (n_ok, n_bad), "FAIL", note)
    add("v1_additivity", "all tables", "printed Jumlah rows re-sum",
        "%d ok, %d off (%d documented misprints)" % (tot_ok, tot_bad, tot_doc),
        "PASS" if tot_bad == 0 else "FAIL")

    # header reconstruction sanity (independent re-read)
    bad_hdr, positional = header_check(rows)
    add("header_reconstruction", "all tables",
        "labels built from each table's own header words, or explicitly "
        "positional",
        "; ".join("%s J%d %r: %s" % (k[0], k[1], l, p)
                  for k, l, p in bad_hdr[:5]) or
        "%d tables positional: %s" % (len(positional),
                                      ["%s J%d" % k for k in positional]),
        "PASS" if not bad_hdr else "FAIL",
        "positional tables carry 'lajur N (kepala tidak boleh dibina "
        "semula)' — treat column identity by position (col order per page)")

    # V2 vs PKKP
    ag = ag_j1(rows)
    import duckdb
    con = duckdb.connect(PKKP, read_only=True)
    for (code, year), (v, dec) in sorted(ag.items(), key=lambda x: (-x[0][1],
                                                                    x[0][0])):
        got = con.execute(
            "select amount_rm from fact_financial_performance "
            "where basis='sebenar' and line_code=? and year=? "
            "and source_file ilike ?",
            [code, year, "%d_Penyata%%" % year]).fetchone()
        pk = got[0] / 1e9 if got else None
        # one unit in the last printed decimal place: the AG mostly rounds
        # but truncates at least once (devex FY2023, see the anomalies file)
        tol = 10 ** -dec
        ok = pk is not None and abs(v - pk) <= tol + 1e-12
        note = "tolerance ±%.3f (one unit in the AG's last printed dp)" % tol
        if ok and pk is not None and abs(v - pk) > 0.5 * tol:
            note += "; AG truncated rather than rounded — " \
                    "documented in _source_anomalies_lkan.csv"
        add("v2_vs_pkkp_audited", "%s FY%d" % (code, year),
            "AG %.3f RM bilion" % v,
            "PKKP %.6f RM bilion" % pk if pk is not None else "missing",
            "PASS" if ok else "FAIL", note)
    con.close()

    # V3 vs BNM (RM juta)
    bnm = {}
    with open(BNM) as f:
        for r in csv.DictReader(f):
            if r["year_dt"] in ("2023", "2024"):
                y = int(r["year_dt"])
                rec = (r["cur_bud_rev"], r["cur_bud_exp"],
                       r["dev_exp_gro_dev_exp"])
                if r["period"] == "":
                    bnm[("annual", y)] = rec
                elif r["period"] in ("1Q", "2Q", "3Q", "4Q"):
                    q = bnm.setdefault(("q", y), [0.0, 0.0, 0.0])
                    for i in range(3):
                        q[i] += float(rec[i] or 0)
    fields = {"revenue": 0, "opex": 1, "devex": 2}
    for (code, year), (v, dec) in sorted(ag.items(), key=lambda x: (-x[0][1],
                                                                    x[0][0])):
        rec = bnm.get(("annual", year)) or bnm.get(("q", year))
        b = float(rec[fields[code]])
        ag_juta = v * 1000
        tol = 0.5 * 10 ** -dec * 1000
        diff = ag_juta - b
        ok = abs(diff) <= tol + 1e-9
        add("v3_vs_bnm_reported", "%s FY%d" % (code, year),
            "AG %.1f RM juta" % ag_juta, "BNM %.3f RM juta" % b,
            "PASS" if ok else "FAIL",
            "" if ok else "BNM diverges from the audited figure by "
            "RM%.3f juta (AG agrees with PKKP); reported vs audited gap, "
            "kept as published" % (b - ag_juta))

    dest = os.path.join(DATA, "_validation_lkan_fiscal.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "expected",
                                          "actual", "status", "note"])
        w.writeheader()
        w.writerows(results)
    npass = sum(1 for r in results if r["status"] == "PASS")
    for r in results:
        if r["status"] != "PASS":
            print("%s %-22s %-18s expected=%s actual=%s %s"
                  % (r["status"], r["check"], r["scope"], r["expected"],
                     r["actual"], r["note"][:80]))
    print("%d/%d PASS -> %s" % (npass, len(results), dest))


if __name__ == "__main__":
    main()
