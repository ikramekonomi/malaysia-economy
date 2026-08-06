#!/usr/bin/env python3
"""Cross-check DOSM/data.gov.my state finance against the AUDITED state accounts.

The state-level analogue of the BNM-vs-PKKP federal triangulation already in
sources/bnm: two independent publications of the same concept —

  reported  data.gov.my `state_finance_revenue` / `state_finance_expenditure`
            (data_source "AUDIT" per the catalogue; RM million, one year per state:
             2022 for 12 states, 2020 for Sarawak)
  audited   sources/states — the states' own audited financial statements as
            extracted from the LKAN volumes
            (_national/fact_state_finance_all.csv, amount_rm_conformed in RM)

Line mapping (DOSM code -> audited line_code), by the standard state chart of accounts:
  revenue_60000  Hasil Cukai              -> revenue_tax
  revenue_70000  Hasil Bukan Cukai        -> revenue_nontax
  revenue_80000  Terimaan Bukan Hasil     -> revenue_nonrevenue_receipts
  total (rev)                             -> revenue_total
  oe             Perbelanjaan Mengurus    -> opex_before_transfer (also reported vs opex_total)
  de             Perbelanjaan Pembangunan -> devex_total

Neither side is corrected. Divergences are the finding. Writes
data/_crosscheck_state_finance_vs_audited.csv with, per state-year-line, both
figures, the absolute and % difference, and a verdict:
  MATCH        within 0.5% (or RM0.5 million on small lines) — the same number
  CLOSE        within 2%   — presentational/rounding difference
  DIVERGENT    beyond 2%   — a real gap between the two publications
  DEFINITIONAL the audited components ADD UP to DOSM's figure, so the two
               publications simply group the heads differently (proven at run
               time by COMBINES, never assumed)
  NO_AUDITED   the audited panel has no such line for that state-year
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
STATES = os.path.join(HERE, "..", "..", "states", "data", "_national",
                      "fact_state_finance_all.csv")

MAP = [  # (dosm key = "<file>:<category>", audited line_code, label)
    ("revenue:revenue_60000", "revenue_tax", "tax revenue"),
    ("revenue:revenue_70000", "revenue_nontax", "non-tax revenue"),
    ("revenue:revenue_80000", "revenue_nonrevenue_receipts", "non-revenue receipts"),
    ("revenue:total", "revenue_total", "total revenue"),
    ("expenditure:oe", "opex_before_transfer", "operating expenditure"),
    ("expenditure:de", "devex_total", "development expenditure"),
]
# The state accounts present operating expenditure under several concepts, and which
# one DOSM's `oe` corresponds to is itself a question — so DOSM `oe` is compared
# against every audited opex variant present for that state-year.
OPEX_VARIANTS = ["opex_before_transfer", "opex_total", "opex_after_transfer",
                 "opex_total_by_maksud"]


def load_audited():
    a = defaultdict(dict)  # (state, year) -> line_code -> RM million
    for r in csv.DictReader(open(STATES)):
        if r["measure"] != "actual" or not r["amount_rm_conformed"]:
            continue
        a[(r["state"], int(r["fiscal_year"]))][r["line_code"]] = \
            float(r["amount_rm_conformed"]) / 1e6
    return a


def load_dosm():
    # key categories as "<file>:<category>" — both files publish a `total` row
    d = defaultdict(dict)  # (state, year) -> "file:category" -> RM million
    for kind in ("revenue", "expenditure"):
        for r in csv.DictReader(open(os.path.join(DATA, f"state_finance_{kind}.csv"))):
            d[(r["state"], int(r["date"][:4]))][f"{kind}:{r['category']}"] = float(r[kind])
    return d


# audited heads DOSM folds into another category, per state. Proven by arithmetic
# at run time (the combination must equal DOSM's figure), never assumed.
COMBINES = {
    # Sarawak prints federal grants as its own revenue head; DOSM folds it into
    # non-revenue receipts: 30.75 + 248.34 = 279.09 exactly (FY2020).
    ("revenue_nonrevenue_receipts", "Sarawak"): ["revenue_federal_grants"],
}


def verdict(dosm, aud):
    diff = dosm - aud
    pct = abs(diff) / abs(aud) * 100 if aud else float("inf")
    if pct <= 0.5 or abs(diff) <= 0.5:
        return "MATCH", diff, pct
    if pct <= 2.0:
        return "CLOSE", diff, pct
    return "DIVERGENT", diff, pct


def main():
    aud, dosm = load_audited(), load_dosm()
    out = []
    # first: DOSM's own internal identities (both files publish components + a total)
    for (state, year), c in sorted(dosm.items()):
        comp = sum(c[f"revenue:revenue_{k}0000"] for k in (6, 7, 8))
        out.append([state, year, "DOSM internal: revenue components vs total",
                    "revenue:total", "-", round(c["revenue:total"], 3), round(comp, 3),
                    round(c["revenue:total"] - comp, 3), 0.0,
                    "MATCH" if abs(c["revenue:total"] - comp) <= 0.01 else "DIVERGENT"])
        objs = sum(c[f"expenditure:oe_{k}0000"] for k in range(1, 6))
        out.append([state, year, "DOSM internal: OE objects vs OE total",
                    "expenditure:oe", "-", round(c["expenditure:oe"], 3), round(objs, 3),
                    round(c["expenditure:oe"] - objs, 3), 0.0,
                    "MATCH" if abs(c["expenditure:oe"] - objs) <= 0.01 else "DIVERGENT"])
        oede = c["expenditure:oe"] + c["expenditure:de"]
        out.append([state, year, "DOSM internal: OE+DE vs expenditure total",
                    "expenditure:total", "-", round(c["expenditure:total"], 3),
                    round(oede, 3), round(c["expenditure:total"] - oede, 3), 0.0,
                    "MATCH" if abs(c["expenditure:total"] - oede) <= 0.01 else "DIVERGENT"])

    for (state, year), cats in sorted(dosm.items()):
        for dcat, aline, label in MAP:
            if dcat not in cats:
                continue
            dv = cats[dcat]
            av = aud.get((state, year), {}).get(aline)
            if av is None:
                out.append([state, year, label, dcat, aline, round(dv, 3), "", "", "",
                            "NO_AUDITED"])
                continue
            v, diff, pct = verdict(dv, av)
            out.append([state, year, label, dcat, aline, round(dv, 3), round(av, 3),
                        round(diff, 3), round(pct, 2), v])
            # Some states print a head DOSM folds into another category. Where the
            # audited components ADD UP to DOSM's figure, the difference is
            # definitional, not a discrepancy in either source — re-adjudicate and
            # say which audited lines were combined.
            if v == "DIVERGENT":
                extra = COMBINES.get((aline, state))
                if extra:
                    parts = {a: aud.get((state, year), {}).get(a) for a in [aline] + extra}
                    if all(x is not None for x in parts.values()):
                        tot = sum(parts.values())
                        if abs(dv - tot) <= max(0.01, 0.005 * abs(dv)):
                            out[-1][-1] = "DEFINITIONAL"
                            out[-1][6] = round(tot, 3)
                            out[-1][7] = round(dv - tot, 3)
                            out[-1][8] = 0.0
                            out[-1][4] = " + ".join(parts)

        # DOSM `oe` against every audited opex concept present for this state-year
        if "expenditure:oe" in cats:
            dv = cats["expenditure:oe"]
            for aline in OPEX_VARIANTS:
                av = aud.get((state, year), {}).get(aline)
                if av is None or aline == "opex_before_transfer":
                    continue  # before_transfer already emitted by the MAP loop
                v, diff, pct = verdict(dv, av)
                out.append([state, year, f"operating expenditure (vs {aline})",
                            "expenditure:oe", aline, round(dv, 3), round(av, 3),
                            round(diff, 3), round(pct, 2), v])

    dest = os.path.join(DATA, "_crosscheck_state_finance_vs_audited.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["state", "fiscal_year", "line", "dosm_category", "audited_line_code",
                    "dosm_rm_mil", "audited_rm_mil", "diff_rm_mil", "diff_pct", "verdict"])
        w.writerows(out)
    from collections import Counter
    c = Counter(r[-1] for r in out)
    print(f"{len(out)} comparisons -> {dest}")
    print("  " + "  ".join(f"{k}={v}" for k, v in c.most_common()))
    for r in out:
        if r[-1] == "DIVERGENT":
            print(f"  DIVERGENT {r[0]} {r[1]} {r[2]}: dosm {r[5]} vs audited {r[6]} "
                  f"({r[7]:+} RM mil, {r[8]}%)")


if __name__ == "__main__":
    main()
