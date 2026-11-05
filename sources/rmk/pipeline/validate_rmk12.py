#!/usr/bin/env python3
"""Validate the RMKe-12 appendix extraction against the tables' own printed identities.

  V1 Jadual 5: KDNK exceeds its five sectors by the import duties the table does not print (DOSM's state GDP is
     the sectors plus import duties): the residual must be positive and under 5% of KDNK in every column
  V2 Jadual 5: the printed growth rates against the printed levels: RMKe-11 2016-2020 = (2020/2015)^(1/5) - 1 and the
     RMKe-12 target = (2025 target / 2020)^(1/5) - 1, within 0.05 percentage point plus the levels' rounding
     (WARN beyond, kept as printed)
  V3 Jadual 10: Hasil - Perbelanjaan Mengurus = Baki Semasa; Kasar - Terimaan Balik Pinjaman = Bersih;
     Baki Semasa - Bersih - Kumpulan Wang COVID-19 = Baki Keseluruhan; every column, within RM2 juta
  V4 Jadual 14: the five sectors add up to Jumlah Guna Tenaga (within 0.3 thousand) and their shares to 100 (0.2);
     Penganggur / Jumlah Tenaga Buruh = Kadar Pengangguran (within 0.05 point)
  V5 coverage: 15 state sections (13 states, WP Kuala Lumpur incl. Putrajaya, WP Labuan) x 7 lines
Writes sources/rmk/data/_validation_rmk12.csv. Exit 1 on a FAIL. Nothing is corrected (golden rule 2).
"""
import csv
import os
import sys
from collections import defaultdict
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
SECT = ["Pertanian", "Perlombongan dan Pengkuarian", "Pembuatan", "Pembinaan", "Perkhidmatan"]


def main():
    rows = list(csv.DictReader(open(os.path.join(SRC, "data", "rmk12", "fact_rmk12_lampiran.csv"), encoding="utf-8")))
    v = {(r["jadual"], r["section_bm"], r["line_bm"], r["measure"]): D(r["value"]) for r in rows}
    out = []

    def add(c, s, st, d):
        out.append(dict(check=c, scope=s, status=st, detail=d))
    states = list(dict.fromkeys(r["section_bm"] for r in rows if r["jadual"] == "5"))
    cols = [m for m in dict.fromkeys(r["measure"] for r in rows if r["jadual"] == "5") if m.startswith(("sebenar", "sasaran_2025"))]
    for s in states:
        res = {c: v[("5", s, "KDNK", c)] - sum(v[("5", s, x, c)] for x in SECT) for c in cols}
        bad = [f"{c}: {r}" for c, r in res.items() if not (0 < r < D("0.05") * v[("5", s, "KDNK", c)])]
        add("V1 KDNK = sectors + unprinted import duties (residual positive, under 5%)", f"Jadual 5 {s}",
            "PASS" if not bad else "FAIL", "; ".join(bad) or "residual " + ", ".join(
                f"{c[-4:]} {r}" for c, r in res.items()))
        for line in SECT + ["KDNK"]:
            for g, a, b in (("purata_rmk11_2016_2020", "sebenar_2015", "sebenar_2020"),
                            ("sasaran_purata_rmk12_2021_2025", "sebenar_2020", "sasaran_2025")):
                x0, x1, pg = v[("5", s, line, a)], v[("5", s, line, b)], v[("5", s, line, g)]
                if x0 <= 0:
                    continue
                calc = (float(x1) / float(x0)) ** 0.2 * 100 - 100
                tol = 0.05 + 20 * (0.5 / float(min(x0, x1)))  # the printed levels' rounding, at RM1 juta
                st = "PASS" if abs(calc - float(pg)) <= tol else "WARN"
                if st != "PASS" or line == "KDNK":
                    add(f"V2 printed growth against printed levels ({g})", f"Jadual 5 {s} {line}", st,
                        f"printed {pg}, from levels {calc:.2f}")
    for c in [m for m in dict.fromkeys(r["measure"] for r in rows if r["jadual"] == "10")]:
        g = lambda line: v[("10", "", line, c)]  # noqa: E731
        ids = [("Hasil - Perbelanjaan Mengurus = Baki Semasa", g("Hasil") - g("Perbelanjaan Mengurus") - g("Baki Semasa")),
               ("Kasar - Terimaan Balik Pinjaman = Bersih", g("Perbelanjaan Pembangunan Kasar")
                - g("Tolak: Terimaan Balik Pinjaman") - g("Perbelanjaan Pembangunan Bersih")),
               ("Baki Semasa - Bersih - Kumpulan Wang COVID-19 = Baki Keseluruhan", g("Baki Semasa")
                - g("Perbelanjaan Pembangunan Bersih") - g("Kumpulan Wang COVID-19") - g("Baki Keseluruhan"))]
        for name, d in ids:
            add(f"V3 {name}", f"Jadual 10 {c}", "PASS" if abs(d) <= 2 else "FAIL", f"difference {d}")
    for c, pc in (("sebenar_2015", "pct_jumlah_2015"), ("sebenar_2020", "pct_jumlah_2020"), ("sasaran_2025", "pct_jumlah_2025")):
        s = sum(v[("14", "", x, c)] for x in SECT)
        t = v[("14", "", "Jumlah Guna Tenaga", c)]
        sp = sum(v[("14", "", x, pc)] for x in SECT)
        add("V4 sectors add up to Jumlah Guna Tenaga", f"Jadual 14 {c}", "PASS" if abs(s - t) <= D("0.3") and
            abs(sp - 100) <= D("0.2") else "FAIL", f"{s} vs {t}; shares {sp}")
        u, lf, ur = v[("14", "", "Penganggur", c)], v[("14", "", "Jumlah Tenaga Buruh", c)], v[("14", "", "Kadar Pengangguran, %", c)]
        add("V4 Penganggur / Tenaga Buruh = Kadar Pengangguran", f"Jadual 14 {c}",
            "PASS" if abs(u / lf * 100 - ur) <= D("0.05") else "WARN", f"{u / lf * 100:.2f} vs {ur}")
    n = defaultdict(set)
    for r in rows:
        if r["jadual"] == "5":
            n[r["section_bm"]].add(r["line_bm"])
    add("V5 coverage: 15 state sections x 7 lines", "Jadual 5", "PASS" if len(n) == 15 and all(len(x) == 7 for x in n.values())
        else "FAIL", f"{len(n)} sections")
    with open(os.path.join(SRC, "data", "_validation_rmk12.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "scope", "status", "detail"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    st = defaultdict(int)
    for r in out:
        st[r["status"]] += 1
    print("rmk12: " + ", ".join(f"{n} {k}" for k, n in sorted(st.items())))
    sys.exit(1 if st["FAIL"] else 0)


if __name__ == "__main__":
    main()
