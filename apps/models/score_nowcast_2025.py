#!/usr/bin/env python3
"""Score the FY2025 model projections against FY2025 as reported (DATA_MODEL §15, Phase 5: 'FY2025 nowcast scored').

  python3 apps/models/score_nowcast_2025.py -> apps/models/_score_nowcast_2025.csv

An application, not warehouse data (§13.1). Method declared 2026-11-06 01:00 MYT and committed before any score was
computed (no FY2025 actual had been looked at for this purpose):
* What is scored: the projections already committed in this folder for FY2025, unchanged:
  fact_projection_headline.csv (rev, opex, devex, deficit; lo/mid/hi, RM billion; built from PKKP to FY2024) and
  fact_nowcast_2025.csv TOTAL_OE (sum of per-vote expected actuals, lo/mid/hi).
* Against what: FY2025 as REPORTED, because PKKP FY2025 (the audited accounts) is not yet published:
    MOF   Tinjauan Fiskal, the edition that prints FY2025 as official_actual (core: federal_gov.*, basis actual)
    BNM   MSB 3.1 annual 2025 (core, basis actual)
  Both are scored separately; neither is averaged. Every score is provisional and is re-scored when PKKP FY2025
  is loaded (the audited figure is the anchor, CLAUDE.md).
* Concepts are matched to how each projection was built: rev = federal_gov.revenue.total; opex and TOTAL_OE =
  federal_gov.expenditure.opex (before the transfer to the Development Fund); devex = federal_gov.expenditure.devex
  (gross); deficit = rev - opex - devex gross (the model's identity), computed from the same publisher's three
  lines, NOT the published overall balance (which uses net development spending and the COVID-19 Fund). debt is
  not scored: no FY2025 federal debt figure is held in core.
* Scores per series and publisher: inside_band (lo <= actual <= hi, with the deficit band's lo/hi taken as the
  min/max of the two ends), error_mid_rm_bil = actual - mid, error_mid_pct = (actual - mid) / actual, and
  band_width_pct = (hi - lo) / actual. No other metric, no re-fitting, no tuning after seeing the scores.
"""
import csv
import os
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "core", "pipeline"))
from warehouse import Warehouse, fmt  # noqa: E402

IND = {"rev": "federal_gov.revenue.total", "opex": "federal_gov.expenditure.opex",
       "devex": "federal_gov.expenditure.devex"}
B = Decimal(1000000000)


def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    w = Warehouse()
    act, ids = {}, {}
    for r in w.obs:
        if r["period_code"] == "2025" and r["geo_code"] == "MY" and r["breakdown_key"] == "_total" and \
                r["basis"] == "actual" and r["indicator_code"] in IND.values():
            pub = r["edition_id"].split(":")[0]
            if pub in ("mof", "bnm"):
                act[(r["indicator_code"], pub)] = Decimal(r["value"]) / B
                ids[(r["indicator_code"], pub)] = r["obs_id"]
    proj = {}
    for r in rows(os.path.join(HERE, "fact_projection_headline.csv")):
        if r["year"] == "2025" and r["series"] in ("rev", "opex", "devex", "deficit"):
            proj[r["series"]] = (Decimal(r["lo_rm_bil"]), Decimal(r["mid_rm_bil"]), Decimal(r["hi_rm_bil"]),
                                 "fact_projection_headline.csv", r["method"])
    t = next(r for r in rows(os.path.join(HERE, "fact_nowcast_2025.csv")) if r["maksud_code"] == "TOTAL_OE")
    proj["TOTAL_OE"] = (Decimal(t["expected_lo_rm"]) / B, Decimal(t["expected_mid_rm"]) / B,
                        Decimal(t["expected_hi_rm"]) / B, "fact_nowcast_2025.csv", t["method"])
    out = []
    for series, (lo, mid, hi, src, method) in proj.items():
        for pub in ("mof", "bnm"):
            if series == "deficit":
                need = [(IND[k], pub) for k in ("rev", "opex", "devex")]
                if not all(n in act for n in need):
                    continue
                a = act[need[0]] - act[need[1]] - act[need[2]]
                oid = ";".join(ids[n] for n in need)
                concept = "rev - opex - gross devex (the model's identity)"
            else:
                k = (IND["opex" if series == "TOTAL_OE" else series], pub)
                if k not in act:
                    continue
                a, oid, concept = act[k], ids[k], k[0]
            blo, bhi = min(lo, hi), max(lo, hi)
            out.append(dict(target_year="2025", series=series, projection_file=src, method=method,
                            model_lo=fmt(lo, 3), model_mid=fmt(mid, 3), model_hi=fmt(hi, 3), publisher=pub,
                            actual_rm_bil=fmt(a, 3), actual_concept=concept, inside_band="yes" if blo <= a <= bhi else "no",
                            error_mid_rm_bil=fmt(a - mid, 3), error_mid_pct=fmt((a - mid) / abs(a) * 100, 2),
                            band_width_pct=fmt((bhi - blo) / abs(a) * 100, 2), actual_obs_ids=oid,
                            status="provisional: FY2025 as reported; re-score when PKKP FY2025 (audited) is loaded",
                            release_id=w.release_id))
    path = os.path.join(HERE, "_score_nowcast_2025.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        wr.writeheader()
        wr.writerows(out)
    print(f"score_nowcast_2025: {len(out)} scores; inside band {sum(r['inside_band'] == 'yes' for r in out)}")


if __name__ == "__main__":
    main()
