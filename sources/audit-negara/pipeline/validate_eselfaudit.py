#!/usr/bin/env python3
"""Validate data/fact_eselfaudit_registers.csv -> data/_validation_eselfaudit.csv.

V1 internal additivity: every printed JUMLAH row is recomputed from the line
   rows of its table, per column (column additivity); tables whose JUMLAH
   column is a row-sum (II.3 J4, VII J3, VII J5, Prestasi J9/J11/J12) are
   also recomputed row-wise; Prestasi J3's PERUBAHAN/% columns are re-derived
   from its own TAHUN columns (difference and ratio, at printed rounding).
   The bullet sub-counts embedded in II.3 J3 row 4 are re-added to the cell.
V2 census totals vs the chapters' own prose: every entity count and RM total
   the running text states (with its pdf_page as evidence) is compared to the
   extracted register cells, including the cross-table identities inside
   CMD.2.2026 II.3 (e.g. 460 CLBS aktif of Prestasi J1 = 111+349 of II.3 J4).
V3 FY2024 register (CMD.2.2026 II.3, e-SelfAudit round as at 31 Dec 2025)
   vs the FY2025 census announcement (CMD.14.2025 VII, as at 31 Jul 2025)
   where the same categories recur: identical-by-construction rows must
   match (PASS/FAIL); categories that legitimately moved between the two
   snapshot dates are reported as INFO with both readings.
Discrepancies are reported, never corrected; failures already documented in
_source_anomalies_lkan.csv (field=eselfaudit_register) downgrade to INFO.
"""
import csv
import os
import re
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

EXPECT_TABLES = {"II.3": 4, "II.3 Mandat": 6, "II.3 Tatakelola": 4,
                 "II.3 Prestasi": 12, "VII": 5}
# tables whose JUMLAH column is the row-sum of these columns
ROWSUM = {
    ("II.3", 4): ["AKTIF SPV", "AKTIF BUKAN SPV", "DORMAN"],
    ("VII", 3): ["MAKLUM BALAS (Sistem e-SelfAudit) KEMUKA",
                 "MAKLUM BALAS (Sistem e-SelfAudit) TIDAK KEMUKA",
                 "STATUS (Winding Up/Dissolved/Tidak Lagi Berkaitan "
                 "Dengan Kerajaan)"],
    ("VII", 5): ["AKTIF CLBS", "AKTIF CLBG", "SPV CLBS", "SPV CLBG",
                 "DORMAN CLBS", "DORMAN CLBG",
                 "SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBS",
                 "SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBG"],
    ("II.3 Prestasi", 9): ["TAHUN 2022", "TAHUN 2023"],
    ("II.3 Prestasi", 11): ["2022", "2023"],
    ("II.3 Prestasi", 12): ["2022", "2023"],
}
# expected line-row counts of the named-entity registers
ROWCOUNTS = {
    ("II.3 Mandat", 2): 4, ("II.3 Mandat", 6): 2,
    ("II.3 Prestasi", 3): 17, ("II.3 Prestasi", 4): 13,
    ("II.3 Prestasi", 7): 9, ("II.3 Prestasi", 8): 10,
    ("VII", 3): 13, ("VII", 4): 2, ("VII", 5): 14,
}


def parse_value(text):
    """Printed cell -> (float, decimals) or (None, 0) for nil/non-numeric."""
    t = text.strip()
    if t in ("", "-", "–") or t.startswith(">"):
        return None, 0
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").rstrip("%").rstrip("*").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None, 0
    dec = len(t.split(".")[1]) if "." in t else 0
    return (-v if neg else v), dec


def known_anomalies():
    path = os.path.join(DATA, "_source_anomalies_lkan.csv")
    out = set()
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                if r.get("field") == "eselfaudit_register":
                    out.add(r["chapter_id"])
    return out


def main():
    with open(os.path.join(DATA, "fact_eselfaudit_registers.csv")) as f:
        rows = list(csv.DictReader(f))
    known = known_anomalies()
    results = []

    def add(check, scope, expected, actual, status, note=""):
        results.append({"check": check, "scope": scope, "expected": expected,
                        "actual": actual, "status": status, "note": note})

    def cell(bah, jn, row_prefix, col, rtype=None):
        for r in rows:
            if r["bahagian"] == bah and int(r["jadual_no"]) == jn \
                    and r["row_label_bm"].startswith(row_prefix) \
                    and r["col_label_bm"] == col \
                    and (rtype is None or r["row_type"] == rtype):
                return r["value_verbatim"]
        return None

    def num(bah, jn, row_prefix, col, rtype=None):
        v, _ = parse_value(cell(bah, jn, row_prefix, col, rtype) or "")
        return v

    # ---- tables extracted ----
    tables = OrderedDict()
    for r in rows:
        tables.setdefault((r["bahagian"], int(r["jadual_no"])),
                          []).append(r)
    seen = {}
    for bah, jn in tables:
        seen.setdefault(bah, set()).add(jn)
    for bah, want in EXPECT_TABLES.items():
        got = seen.get(bah, set())
        missing = sorted(set(range(1, want + 1)) - got)
        add("tables_extracted", bah, want, len(got),
            "PASS" if not missing else "FAIL",
            "missing JADUAL %s" % missing if missing else "")

    # ---- V1a column additivity of printed JUMLAH rows ----
    n_ok = n_bad = n_doc = 0
    for (bah, jn), cells in tables.items():
        cols = OrderedDict()
        for r in cells:
            if r["col_label_bm"] and r["unit"] != "%":
                cols.setdefault((r["col_label_bm"], r["unit"]), None)
        for clabel, unit in cols:
            comp, total = [], None
            for r in cells:
                if (r["col_label_bm"], r["unit"]) != (clabel, unit):
                    continue
                v, dec = parse_value(r["value_verbatim"])
                if v is None:
                    continue
                if r["row_type"] == "line":
                    comp.append((v, dec))
                elif r["row_type"] == "total":
                    total = (v, dec, r["value_verbatim"])
            if total is None or not comp:
                continue
            v, dec, verbatim = total
            tol = 10 ** -max([dec] + [d for _, d in comp])
            s = sum(c for c, _ in comp)
            scope = "%s J%d" % (bah, jn)
            if abs(v - s) <= tol + 1e-9:
                n_ok += 1
            elif scope in known:
                n_doc += 1
                add("v1_column_additivity", scope, "printed sums",
                    "%s JUMLAH=%s vs %.2f" % (clabel, verbatim, s), "INFO",
                    "documented source misprint — see "
                    "_source_anomalies_lkan.csv")
            else:
                n_bad += 1
                add("v1_column_additivity", scope, "printed sums",
                    "%s JUMLAH=%s vs %.2f" % (clabel, v, s), "FAIL")
    add("v1_column_additivity", "all tables", "printed JUMLAH rows re-sum",
        "%d ok, %d off (%d documented misprints)" % (n_ok, n_bad, n_doc),
        "PASS" if n_bad == 0 else "FAIL")

    # ---- V1b row additivity (JUMLAH column = sum of category columns) ----
    n_ok = n_bad = 0
    notes = []
    for (bah, jn), addcols in ROWSUM.items():
        for r in tables[(bah, jn)]:
            if r["col_label_bm"] != "JUMLAH" or r["row_type"] == "group":
                continue
            v, dec = parse_value(r["value_verbatim"])
            comp = [parse_value(cell(bah, jn, r["row_label_bm"], c,
                                     r["row_type"]) or "")[0] or 0
                    for c in addcols]
            if v is not None and abs(v - sum(comp)) <= 10 ** -dec + 1e-9:
                n_ok += 1
            else:
                n_bad += 1
                notes.append("%s J%d %r %s vs %.2f"
                             % (bah, jn, r["row_label_bm"][:24],
                                r["value_verbatim"], sum(comp)))
    add("v1_row_additivity", "II.3 J4; VII J3/J5; Prestasi J9/J11/J12",
        "JUMLAH column = sum of category columns",
        "%d ok, %d off" % (n_ok, n_bad),
        "PASS" if n_bad == 0 else "FAIL", "; ".join(notes[:3]))

    # ---- V1c Prestasi J3 derived PERUBAHAN and % columns ----
    n_ok = n_bad = n_doc = 0
    notes = []
    labels = OrderedDict()
    for r in tables[("II.3 Prestasi", 3)]:
        labels.setdefault((r["row_label_bm"], r["row_type"]), None)
    for label, rtype in labels:
        y23, _ = parse_value(cell("II.3 Prestasi", 3, label,
                                  "TAHUN 2023", rtype) or "")
        y22, _ = parse_value(cell("II.3 Prestasi", 3, label,
                                  "TAHUN 2022", rtype) or "")
        chg = cell("II.3 Prestasi", 3, label, "PERUBAHAN RM Juta", rtype)
        pct = cell("II.3 Prestasi", 3, label, "PERUBAHAN %", rtype)
        chg_v, chg_d = parse_value(chg or "")
        want = (y23 or 0) - (y22 or 0)
        if chg_v is None and abs(want) < 1e-9:
            n_ok += 1                              # nil change printed '-'
        elif chg_v is not None and abs(chg_v - want) <= 10 ** -chg_d + 1e-9:
            n_ok += 1
        elif rtype == "total" and "II.3 Prestasi J3" in known:
            n_doc += 1
            notes.append("JUMLAH PERUBAHAN %s vs %.2f (documented misprint)"
                         % (chg, want))
        else:
            n_bad += 1
            notes.append("%r PERUBAHAN %s vs %.2f" % (label[:20], chg, want))
        pct_v, pct_d = parse_value(pct or "")
        if y22 and pct_v is not None:
            want_pct = ((y23 or 0) - y22) / y22 * 100
            if abs(pct_v - want_pct) <= 0.5 * 10 ** -pct_d + 0.06:
                n_ok += 1
            else:
                n_bad += 1
                notes.append("%r %%=%s vs %.1f" % (label[:20], pct, want_pct))
    add("v1_derived_perubahan", "II.3 Prestasi J3",
        "PERUBAHAN = 2023-2022; % = PERUBAHAN/2022",
        "%d ok, %d off, %d documented" % (n_ok, n_bad, n_doc),
        "PASS" if n_bad == 0 else "FAIL", "; ".join(notes[:3]))

    # ---- V1d bullet sub-counts inside II.3 J3 row 4 ----
    lab = [r["row_label_bm"] for r in tables[("II.3", 3)]
           if r["row_label_bm"].startswith("Status Winding")][0]
    subs = [int(m) for m in re.findall(r"– (\d+) (?:syarikat|badan lain)",
                                       lab)]
    v208 = num("II.3", 3, "Status Winding", "JUMLAH")
    add("v1_bullet_subcounts", "II.3 J3 row 4",
        "15+153+40 = printed 208", "%s = %s" % ("+".join(map(str, subs)),
                                                v208),
        "PASS" if sum(subs) == v208 and len(subs) == 3 else "FAIL")

    # ---- expected register row counts ----
    bad = []
    for (bah, jn), want in ROWCOUNTS.items():
        got = len({r["row_label_bm"] for r in tables[(bah, jn)]
                   if r["row_type"] == "line"})
        if got != want:
            bad.append("%s J%d: %d vs %d" % (bah, jn, got, want))
    add("register_row_counts", "named-entity registers",
        "17 dividend payers; 13 MKD non-payers; 9 grant; 10 support; "
        "13 states; 14 census rows; 4+2 named; 2 jenis",
        "; ".join(bad) or "all match", "PASS" if not bad else "FAIL")

    # ---- V2 census totals & prose claims (pdf_page evidence in note) ----
    def prose(scope, expected_desc, want, got, page_note):
        ok = got is not None and abs(got - want) < 1e-6
        add("v2_vs_prose", scope, "%s = %s" % (expected_desc, fmt(want)),
            fmt(got), "PASS" if ok else "FAIL", page_note)

    def fmt(v):
        if v is None:
            return "missing"
        return ("{:,.2f}" if v % 1 else "{:,.0f}").format(v)

    J = num
    prose("warta 2024", "II.3 J1 JUMLAH", 1856,
          J("II.3", 1, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 85 para 1.3: 1,856 entiti diwartakan")
    prose("warta split", "852 Persekutuan + 1,004 Negeri", 1856, 852 + 1004,
          "prose pdf 85 para 1.4 (constants restated)")
    prose("warta rollout", "206 rintis + 1,650 baki", 1856, 206 + 1650,
          "prose pdf 86 para 2.1")
    prose("federal census 2024", "II.3 J3 JUMLAH", 852,
          J("II.3", 3, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 87 para 3.1: 852 entiti Persekutuan diwarta")
    for want, pref in [(641, "Syarikat Kerajaan Persekutuan yang kemuka"),
                       (1, "Badan Lain yang kemuka"),
                       (2, "Tidak kemuka"), (208, "Status Winding")]:
        prose("federal census 2024 status", "II.3 J3 %r" % pref[:28], want,
              J("II.3", 3, pref, "JUMLAH"),
              "prose pdf 87 para 3.1 bullets: 641/1/2/208")
    prose("responders by type", "II.3 J4 JUMLAH JUMLAH", 641,
          J("II.3", 4, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 89 para 5.1: 641 syarikat maklum balas")
    for want, row, col in [(575, "CLBS", "JUMLAH"), (66, "CLBG", "JUMLAH"),
                           (114, "JUMLAH", "AKTIF SPV"),
                           (411, "JUMLAH", "AKTIF BUKAN SPV"),
                           (116, "JUMLAH", "DORMAN")]:
        prose("responders by type", "II.3 J4 %s/%s" % (row, col), want,
              J("II.3", 4, row, col),
              "prose pdf 89 para 5.1: 575 CLBS/66 CLBG; 114 SPV/411/116")
    prose("mandat scope", "II.3 Mandat J1 JUMLAH (525 aktif - 12)", 513,
          J("II.3 Mandat", 1, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 93 para 1.2: 525-12 = 513 syarikat dinilai")
    for jn in (3, 4):
        prose("mandat scope", "II.3 Mandat J%d JUMLAH" % jn, 513,
              J("II.3 Mandat", jn, "JUMLAH", "JUMLAH", "total"),
              "prose pdf 95/96: analisis terhadap 513 syarikat")
    prose("KPI providers", "II.3 Mandat J5 JUMLAH (437+14)", 451,
          J("II.3 Mandat", 5, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 97 para 2.3.5: 451 syarikat menyediakan KPI")
    for jn in (1, 2, 3):
        prose("tatakelola scope", "II.3 Tatakelola J%d JUMLAH" % jn, 401,
              J("II.3 Tatakelola", jn, "JUMLAH", "JUMLAH", "total"),
              "prose pdf 102 para 2.1.3: 401 daripada 411 syarikat aktif "
              "bukan SPV")
    prose("JKA reporting", "II.3 Tatakelola J4 JUMLAH (= J3 row 1)", 202,
          J("II.3 Tatakelola", 4, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 106 para 3.2.2: daripada 202 syarikat dengan JKA")
    # Prestasi cross-table identities
    clbs_aktif = (J("II.3", 4, "CLBS", "AKTIF SPV") +
                  J("II.3", 4, "CLBS", "AKTIF BUKAN SPV"))
    for yr in ("2022", "2023"):
        got = (J("II.3 Prestasi", 1, yr, "SYARIKAT UNTUNG BILANGAN") +
               J("II.3 Prestasi", 1, yr, "SYARIKAT RUGI BILANGAN"))
        prose("CLBS aktif %s" % yr,
              "Prestasi J1 untung+rugi = II.3 J4 CLBS aktif (111+349)",
              clbs_aktif, got,
              "prose pdf 111 para 1.1: 460 syarikat CLBS aktif")
    clbg_aktif = (J("II.3", 4, "CLBG", "AKTIF SPV") +
                  J("II.3", 4, "CLBG", "AKTIF BUKAN SPV"))
    for yr in ("2022", "2023"):
        got = sum(J("II.3 Prestasi", 2, pref, yr) or 0
                  for pref in ("Syarikat Mencatatkan Lebihan",
                               "Syarikat Mencatatkan Kurangan",
                               "Syarikat Tiada"))
        # bilangan sub-rows only: RM cells share labels, so re-read strictly
        got = 0
        for r in tables[("II.3 Prestasi", 2)]:
            if r["col_label_bm"] == yr and r["unit"] == "bilangan":
                got += parse_value(r["value_verbatim"])[0]
        prose("CLBG aktif %s" % yr,
              "Prestasi J2 bilangan = II.3 J4 CLBG aktif (3+62)",
              clbg_aktif, got,
              "prose pdf 112 para 1.2: 65 syarikat CLBG aktif")
    prose("dividen kepada Kerajaan 2023", "Prestasi J3 JUMLAH TAHUN 2023",
          43278.88, J("II.3 Prestasi", 3, "JUMLAH", "TAHUN 2023", "total"),
          "prose pdf 114 para b / rumusan pdf 116: RM43.279 bilion")
    prose("dividen kepada Kerajaan 2022", "Prestasi J3 JUMLAH TAHUN 2022",
          50777.44, J("II.3 Prestasi", 3, "JUMLAH", "TAHUN 2022", "total"),
          "prose pdf 114 para b / rumusan pdf 116: RM50.777 bilion")
    payers = {"2022": 0, "2023": 0}
    for r in tables[("II.3 Prestasi", 3)]:
        if r["row_type"] == "line" and r["col_label_bm"].startswith("TAHUN"):
            if parse_value(r["value_verbatim"])[0] is not None:
                payers[r["col_label_bm"][-4:]] += 1
    prose("payers 2022", "Prestasi J3 non-nil TAHUN 2022 cells", 15,
          payers["2022"],
          "prose pdf 114 para b: 15 syarikat bayar dividen kpd Kerajaan 2022")
    prose("payers 2023", "Prestasi J3 non-nil TAHUN 2023 cells", 16,
          payers["2023"],
          "prose pdf 114 para b: 16 syarikat bayar dividen kpd Kerajaan 2023")
    prose("going concern sijil", "Prestasi J5 JUMLAH", 64,
          J("II.3 Prestasi", 5, "JUMLAH", "BIL. SYARIKAT", "total"),
          "prose pdf 118 para a: 64 syarikat Penegasan Perkara")
    prose("going concern nota", "Prestasi J6 JUMLAH", 77,
          J("II.3 Prestasi", 6, "JUMLAH", "BIL. SYARIKAT", "total"),
          "prose pdf 119 para a: 77 syarikat pendedahan Nota")
    prose("going concern all", "J5 + J6 JUMLAH", 141,
          (J("II.3 Prestasi", 5, "JUMLAH", "BIL. SYARIKAT", "total") +
           J("II.3 Prestasi", 6, "JUMLAH", "BIL. SYARIKAT", "total")),
          "prose pdf 119 para b: 141 syarikat isu usaha berterusan")
    prose("geran tertunda", "Prestasi J7 JUMLAH", 1996.88,
          J("II.3 Prestasi", 7, "JUMLAH",
            "BAKI GERAN TERTUNDA BAGI TAHUN BERAKHIR 2023", "total"),
          "prose pdf 119 para b / rumusan pdf 122: RM1.997 bilion, "
          "9 syarikat")
    prose("sokongan kewangan top-10", "Prestasi J8 JUMLAH", 9857.81,
          J("II.3 Prestasi", 8, "JUMLAH",
            "BAKI SOKONGAN KEWANGAN* BAGI TAHUN BERAKHIR 2023", "total"),
          "prose pdf 121 para d: RM9.858 bilion baki tertinggi 10 syarikat "
          "(EXCERPT of 119 syarikat / RM13.784 bilion)")
    prose("dorman", "II.3 J4 JUMLAH DORMAN", 116,
          J("II.3", 4, "JUMLAH", "DORMAN", "total"),
          "prose pdf 123 para 4.2.1: 116 (18.1%) daripada 641 dorman")
    prose("dorman analysed", "Prestasi J9 JUMLAH BILANGAN (62+17)", 79,
          J("II.3 Prestasi", 9, "JUMLAH", "BILANGAN SYARIKAT", "total"),
          "prose pdf 123 para 4.2.1-4.2.2: 79 dianalisis, 62 >=5 tahun, 17 "
          "kurang")
    prose("dorman fi audit", "Prestasi J9 JUMLAH JUMLAH", 0.55,
          J("II.3 Prestasi", 9, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 123 para 4.2.2: RM0.55 juta (0.29 + 0.26)")
    prose("dorman >=5y obligasi", "Prestasi J10 obligasi rows (4+36)", 40,
          (J("II.3 Prestasi", 10, "Aset Bersih", "BILANGAN SYARIKAT") +
           J("II.3 Prestasi", 10, "Liabiliti Bersih", "BILANGAN SYARIKAT")),
          "prose pdf 123 para a: 40 syarikat masih mempunyai obligasi; "
          "pdf 124 para b: 4 aset bersih / 36 liabiliti bersih")
    prose("dorman liabiliti bersih RM", "Prestasi J10 Liabiliti Bersih RM",
          1248.47, J("II.3 Prestasi", 10, "Liabiliti Bersih", "RM Juta"),
          "prose pdf 124 para b: RM1.248 bilion")
    prose("dorman perbelanjaan 36 syk", "Prestasi J11 JUMLAH JUMLAH", 87.74,
          J("II.3 Prestasi", 11, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 124 para d: RM34.74 juta (2022) + RM53.00 juta (2023)")
    prose("dorman perbelanjaan 4 syk", "Prestasi J12 JUMLAH JUMLAH", 3.29,
          J("II.3 Prestasi", 12, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 125 para e: RM3.29 juta keseluruhan (2022 printed 0.02 "
          "RM juta = prose RM19,810)")
    # CMD.14 VII
    prose("warta 2025 census", "VII J1 JUMLAH", 1856,
          J("VII", 1, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 204 para 3: 1,856 diwartakan (925 pada 2022)")
    prose("warta split 2025", "850 Persekutuan + 1,006 Negeri", 1856,
          850 + 1006, "prose pdf 204 para 4 (constants restated)")
    prose("federal census 2025", "VII J2 JUMLAH", 850,
          J("VII", 2, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 204 para 4 / pdf 205 para 10: 850 badan lain termasuk "
          "syarikat Persekutuan")
    for want, pref in [(641, "Syarikat yang kemuka"),
                       (1, "Badan lain yang kemuka"), (34, "Tidak kemuka"),
                       (174, "Status Winding")]:
        prose("federal census 2025 status", "VII J2 %r" % pref[:24], want,
              J("VII", 2, pref, "JUMLAH"),
              "prose pdf 205 para 10 bullets: 641/1/34/174")
    kemuka = "MAKLUM BALAS (Sistem e-SelfAudit) KEMUKA"
    tidak = "MAKLUM BALAS (Sistem e-SelfAudit) TIDAK KEMUKA"
    status = ("STATUS (Winding Up/Dissolved/Tidak Lagi Berkaitan Dengan "
              "Kerajaan)")
    for want, col, desc in [(887, kemuka, "2 badan lain + 885 syarikat"),
                            (19, tidak, "19 tidak kemuka"),
                            (100, status, "100 winding up"),
                            (1006, "JUMLAH", "1,006 Negeri")]:
        prose("state census 2025", "VII J3 JUMLAH %s" % col[:22], want,
              J("VII", 3, "JUMLAH", col, "total"),
              "prose pdf 206 para 11: %s" % desc)
    prose("responders 2025", "VII J5 JUMLAH JUMLAH", 1526,
          J("VII", 5, "JUMLAH", "JUMLAH", "total"),
          "prose pdf 205 para 9: 3 badan lain + 1,526 syarikat (82.4% of "
          "1,856); pdf 207 para 14: 1,526 tidak termasuk 3 badan lain")
    prose("responders 2025 federal", "VII J5 Persekutuan JUMLAH", 641,
          J("VII", 5, "Persekutuan", "JUMLAH"),
          "prose pdf 208 para 15: 641 syarikat Persekutuan")
    for want, cols, desc in [
            (397, ("AKTIF CLBS", "AKTIF CLBG"), "397 aktif"),
            (116, ("SPV CLBS", "SPV CLBG"), "116 SPV"),
            (109, ("DORMAN CLBS", "DORMAN CLBG"), "109 dorman"),
            (19, ("SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBS",
                  "SEDANG DALAM PROSES WINDING UP/DISSOLVED CLBG"),
             "19 winding up/dissolved")]:
        got = sum(J("VII", 5, "Persekutuan", c) or 0 for c in cols)
        prose("responders 2025 federal", "VII J5 Persekutuan %s" % desc,
              want, got, "prose pdf 208 para 15: %s" % desc)

    # ---- V3 FY2024 register vs FY2025 census (same categories) ----
    def xr(scope, a_desc, a, b_desc, b, must_equal, note):
        if must_equal:
            add("v3_cross_report", scope, "%s = %s" % (a_desc, fmt(a)),
                "%s = %s" % (b_desc, fmt(b)),
                "PASS" if a == b else "FAIL", note)
        else:
            add("v3_cross_report", scope, "%s = %s" % (a_desc, fmt(a)),
                "%s = %s" % (b_desc, fmt(b)), "INFO", note)

    snap = ("snapshots differ: CMD.14 VII as at 31 Jul 2025, CMD.2 II.3 "
            "as at 31 Dec 2025 (both over the same P.U.(A) 331/2024 warta)")
    for pref, desc in [("Syarikat yang ditubuhkan", "syarikat Akta 777"),
                       ("Badan lain yang didaftarkan di bawah Jabatan",
                        "badan lain ROS"),
                       ("Badan lain yang didaftarkan di bawah Bahagian",
                        "badan lain BHEUU"),
                       ("JUMLAH", "jumlah warta")]:
        xr("warta komposisi: %s" % desc,
           "CMD.2 II.3 J1", J("II.3", 1, pref, "JUMLAH"),
           "CMD.14 VII J1", J("VII", 1, pref, "JUMLAH"),
           True, "identical warta register printed in both reports")
    xr("federal total", "CMD.2 II.3 J3 JUMLAH",
       J("II.3", 3, "JUMLAH", "JUMLAH", "total"),
       "CMD.14 VII J2 JUMLAH", J("VII", 2, "JUMLAH", "JUMLAH", "total"),
       False, snap + "; CMD.2 pdf 85 says 852/1,004 federal/state, CMD.14 "
       "pdf 204 says 850/1,006 — two entities re-attributed between levels")
    xr("federal syarikat responders", "CMD.2 II.3 J3",
       J("II.3", 3, "Syarikat Kerajaan Persekutuan yang kemuka", "JUMLAH"),
       "CMD.14 VII J2", J("VII", 2, "Syarikat yang kemuka", "JUMLAH"),
       True, "641 in both reports")
    xr("federal badan lain responders", "CMD.2 II.3 J3",
       J("II.3", 3, "Badan Lain yang kemuka", "JUMLAH"),
       "CMD.14 VII J2", J("VII", 2, "Badan lain yang kemuka", "JUMLAH"),
       True, "1 in both reports")
    xr("federal non-responders", "CMD.2 II.3 J3 tidak kemuka",
       J("II.3", 3, "Tidak kemuka", "JUMLAH"),
       "CMD.14 VII J2 tidak kemuka", J("VII", 2, "Tidak kemuka", "JUMLAH"),
       False, snap + "; 32 of CMD.14's 34 non-responders were resolved/"
       "reclassified by Dec 2025 (CMD.2 pdf 88 para 3.3 names the last two)")
    xr("federal winding up/dissolved", "CMD.2 II.3 J3",
       J("II.3", 3, "Status Winding", "JUMLAH"),
       "CMD.14 VII J2", J("VII", 2, "Status Winding", "JUMLAH"),
       False, snap)
    xr("federal dorman", "CMD.2 II.3 J4 DORMAN",
       J("II.3", 4, "JUMLAH", "DORMAN", "total"),
       "CMD.14 VII J5 Persekutuan DORMAN",
       (J("VII", 5, "Persekutuan", "DORMAN CLBS") +
        J("VII", 5, "Persekutuan", "DORMAN CLBG")),
       False, snap + "; CMD.14's snapshot still carried 19 winding-up "
       "companies inside the 641")
    xr("federal SPV", "CMD.2 II.3 J4 AKTIF SPV",
       J("II.3", 4, "JUMLAH", "AKTIF SPV", "total"),
       "CMD.14 VII J5 Persekutuan SPV",
       (J("VII", 5, "Persekutuan", "SPV CLBS") +
        J("VII", 5, "Persekutuan", "SPV CLBG")),
       False, snap)

    dest = os.path.join(DATA, "_validation_eselfaudit.csv")
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "expected",
                                          "actual", "status", "note"])
        w.writeheader()
        w.writerows(results)
    npass = sum(1 for r in results if r["status"] == "PASS")
    ninfo = sum(1 for r in results if r["status"] == "INFO")
    for r in results:
        if r["status"] == "FAIL":
            print("FAIL %-24s %-30s expected=%s actual=%s %s"
                  % (r["check"], r["scope"][:30], r["expected"][:40],
                     r["actual"][:40], r["note"][:60]))
    print("%d PASS, %d INFO, %d FAIL -> %s"
          % (npass, ninfo, len(results) - npass - ninfo, dest))


if __name__ == "__main__":
    main()
