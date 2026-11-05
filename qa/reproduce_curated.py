#!/usr/bin/env python3
"""Phase 2 'done when': the core reproduces today's curated tables to the last printed digit.

Each curated row is rebuilt from core observations through the agent tools (get_series + derive), never
from the curated file or the L1 CSV, and compared at the curated table's own printed precision.
Writes qa/_validation_reproduce.csv (one row per curated cell; FAIL blocks the PR like any other).

    python3 qa/reproduce_curated.py

Covered so far: curated/fact_labour_indicators.csv (labour share of GDP, implied average wage), the
BNM and MOF columns of curated/fact_fiscal_headline.csv (compared to the sen), and (Phase 3) every row of
curated/fact_ministry_fiscal.csv from core's PKKP vote observations (to the sen; a documented
leaf-vs-printed-total difference is EXPLAINED, anything else FAILs). Since Phase 3.3 the headline's PKKP
columns too: core reads them from each year's own volume, independently of curated's construction.
"""
import csv
import os
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from apps.tools.warehouse_tools import Tools  # noqa: E402


def places(printed):
    return len(printed.split(".")[1]) if "." in printed else 0


def at(value, printed):
    """value rounded to the printed precision; the same answer under half-up and half-even, or flagged."""
    q = Decimal(1).scaleb(-places(printed))
    up, even = value.quantize(q, ROUND_HALF_UP), value.quantize(q, ROUND_HALF_EVEN)
    return up, up != even


def obs(t, ind, year):
    r = t.get_series(ind, "MY", year, year)
    return r["rows"][0]["obs_id"] if r.get("held") and len(r["rows"]) == 1 else None


def labour(t, out):
    path = os.path.join(REPO, "curated", "fact_labour_indicators.csv")
    for r in csv.DictReader(open(path, newline="")):
        y, ind = r["year"], r["indicator"]
        comp = obs(t, "na.compensation_of_employees", y)
        if ind == "implied_average_wage_rm_per_worker_year":
            op, other, scale = "per_employed", obs(t, "lfs.employed", y), Decimal(1)
        elif ind == "labour_share_of_gdp_pct":
            op, other, scale = "ratio", obs(t, "gdp.nominal", y), Decimal(100)
        else:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "no rule to reproduce it"])
            continue
        if not comp or not other:
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", "input not held in core"])
            continue
        d = t.derive(op, comp, other)
        if not d.get("ok"):
            out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], "", "FAIL", d.get("refused")])
            continue
        got, tie = at(Decimal(d["value"]) * scale, r["value"])
        ok = got == Decimal(r["value"])
        out.append(["fact_labour_indicators", f"{y} {ind}", r["value"], str(got), "PASS" if ok else "FAIL",
                    f"core: derive('{op}') {d['derivation_id']}" + (" (rounding tie)" if tie else "")])


FISCAL = {  # curated column -> (core indicator, publisher)
    "revenue_bnm_rm": ("federal_gov.revenue.total", "bnm"), "opex_bnm_rm": ("federal_gov.expenditure.opex", "bnm"),
    "devex_gross_bnm_rm": ("federal_gov.expenditure.devex", "bnm"),
    "devex_loan_recovery_bnm_rm": ("federal_gov.expenditure.devex_loan_recovery", "bnm"),
    "devex_net_bnm_rm": ("federal_gov.expenditure.devex_net", "bnm"),
    "revenue_mof_rm": ("federal_gov.revenue.total", "mof"), "opex_mof_rm": ("federal_gov.expenditure.opex", "mof"),
    "devex_gross_mof_rm": ("federal_gov.expenditure.devex", "mof"),
    "devex_loan_recovery_mof_rm": ("federal_gov.expenditure.devex_loan_recovery", "mof"),
    "covid_fund_mof_rm": ("federal_gov.expenditure.covid_fund", "mof"),
    "overall_balance_mof_rm": ("federal_gov.overall_balance", "mof"),
}
SEN = Decimal("0.01")


def fiscal(t, out):
    path = os.path.join(REPO, "curated", "fact_fiscal_headline.csv")
    for r in csv.DictReader(open(path, newline="")):
        y = r["year"]
        cols = dict(FISCAL)
        if "MOF" in r["devex_net_basis"]:
            cols["devex_net_rm"] = ("federal_gov.expenditure.devex_net", "mof")
        for col, (ind, pub) in cols.items():
            res = t.get_series(ind, "MY", y, y, publisher=pub)
            got = res["rows"] if res.get("held") else []
            cell = f"{y} {col}"
            if not r[col]:
                out.append(["fact_fiscal_headline", cell, "", got[0]["value"] if got else "",
                            "PASS" if not got else "FAIL", "empty in both" if not got else "core holds a value curated lacks"])
                continue
            if len(got) != 1:
                out.append(["fact_fiscal_headline", cell, r[col], "", "FAIL", f"{len(got)} core rows for {pub}"])
                continue
            a, b = Decimal(r[col]).quantize(SEN), Decimal(got[0]["value"]).quantize(SEN)
            out.append(["fact_fiscal_headline", cell, str(a), str(b), "PASS" if a == b else "FAIL",
                        f"core {got[0]['citation']['edition_id']}, to the sen"])


PKKP_HEADLINE = {"revenue_rm": "federal_gov.revenue.total", "opex_net_rm": "federal_gov.expenditure.opex",
                 "devex_gross_rm": "federal_gov.expenditure.devex", "covid_fund_rm": "federal_gov.expenditure.covid_fund",
                 "transfer_to_dev_fund_rm": "federal_gov.expenditure.transfer_development_fund"}


def headline_pkkp(t, out):
    """The PKKP columns of curated/fact_fiscal_headline.csv (Phase 3.3): core now reads each from the year's own
    volume (Penyata Prestasi Kewangan; FY2009 Akaun Hasil Disatukan), curated from other tables (sums of leaves,
    next year's comparative column), so the comparison is no longer circular. Equal within the core figure's
    printed precision (the statement prints whole ringgit) is a PASS."""
    path = os.path.join(REPO, "curated", "fact_fiscal_headline.csv")
    for r in csv.DictReader(open(path, newline="")):
        y = r["year"]
        for col, ind in PKKP_HEADLINE.items():
            cell = f"{y} {col}"
            res = t.get_series(ind, "MY", y, y, basis="audited", publisher="pkkp")
            got = res["rows"] if res.get("held") else []
            if not r[col] or Decimal(r[col]) == 0 and not got:
                out.append(["fact_fiscal_headline", cell, r[col], got[0]["value"] if got else "",
                            "PASS" if not got else "FAIL",
                            "nil or empty in curated, none in core" if not got else "core holds a value curated lacks"])
                continue
            if len(got) != 1:
                out.append(["fact_fiscal_headline", cell, r[col], "", "FAIL", f"{len(got)} core rows for pkkp"])
                continue
            a, b = Decimal(r[col]), Decimal(got[0]["value"])
            step = Decimal("1") if got[0]["unit_printed"] == "RM" and "." not in got[0]["value_printed"].rstrip("0").rstrip(".") else SEN
            ok = abs(a - b) < step if step > SEN else a.quantize(SEN) == b.quantize(SEN)
            nxt = r.get("opex_source_file", "").startswith(str(int(y) + 1))
            if not ok and nxt and col in ("opex_net_rm", "transfer_to_dev_fund_rm") and abs(a - b) < 1 and a == a.to_integral():
                out.append(["fact_fiscal_headline", cell, str(a), str(b), "EXPLAINED",
                            f"curated reads FY{y} from the FY{int(y) + 1} volume's comparative column, printed in whole "
                            f"ringgit; core reads FY{y}'s own volume, printed to the sen (golden rule 6): equal to the ringgit"])
                continue
            out.append(["fact_fiscal_headline", cell, str(a), str(b), "PASS" if ok else "FAIL",
                        f"core {got[0]['citation']['edition_id']} p.{got[0]['citation']['pdf_page']}, "
                        + ("within the printed whole ringgit" if step > SEN else "to the sen")])


def ministry(t, out):
    """curated/fact_ministry_fiscal.csv: every vote-year, audited, from core's PKKP vote observations (Phase 3).

    The curated table keys a vote by its canonical code; core keys it by entity and resolves each printed code
    in its own year, so the curated row's raw code(s) are asked for, year by year. Curated's development figure
    is the sum of the vote's project lines (FY2015: the printed vote total); core's is the printed vote total
    (its JUMLAH line). Where curated's own register (curated/_known_extraction_defects_curated.csv) documents
    that the two differ, the row is EXPLAINED with that diagnosis; any other difference is a FAIL."""
    known = {}
    for d in csv.DictReader(open(os.path.join(REPO, "curated", "_known_extraction_defects_curated.csv"), newline="")):
        if d["table"] == "fact_ministry_fiscal":
            known[d["key"].strip()] = d
    heads = {r["code"]: r for r in csv.DictReader(open(os.path.join(REPO, "meta", "spending_head.csv"), newline=""))}
    for r in csv.DictReader(open(os.path.join(REPO, "curated", "fact_ministry_fiscal.csv"), newline="")):
        y, jenis, want = r["year"], r["jenis"], Decimal(r["amount_rm"])
        ind = f"federal_gov.vote.{jenis}"
        total, why = Decimal(0), ""
        for code in r["raw_codes"].split(","):
            if code in heads:
                kind = "charged_head" if heads[code]["kind"] == "charged" else "reserve_head"
                res = t.get_series(ind, "MY", y, y, breakdown=f"{kind}={code}", basis="audited", publisher="pkkp")
            else:
                res = t.get_series(ind, "MY", y, y, basis="audited", publisher="pkkp", entity=code)
            if not res.get("held") or len(res["rows"]) != 1:
                why = f"{code}: {res.get('answer') or str(len(res.get('rows', []))) + ' rows'}"
                break
            total += Decimal(res["rows"][0]["value"])
        key = f"{r['canonical_code']} {jenis} {y}"
        if why:
            out.append(["fact_ministry_fiscal", key, r["amount_rm"], "", "FAIL", why])
            continue
        got, _ = at(total, r["amount_rm"])
        d = known.get(f"{r['raw_codes']} {jenis} {y}")
        if got == want:
            out.append(["fact_ministry_fiscal", key, r["amount_rm"], str(got), "PASS", ""])
        elif d:
            out.append(["fact_ministry_fiscal", key, r["amount_rm"], str(got), "EXPLAINED",
                        f"core = printed vote total, curated = sum of project lines; {d['classification']}: "
                        f"{d['diagnosis'][:160]}"])
        else:
            out.append(["fact_ministry_fiscal", key, r["amount_rm"], str(got), "FAIL",
                        f"core {got} vs curated {want} (diff {got - want})"])


def main():
    t = Tools()
    out = []
    labour(t, out)
    fiscal(t, out)
    headline_pkkp(t, out)
    ministry(t, out)
    with open(os.path.join(REPO, "qa", "_validation_reproduce.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "cell", "curated", "core", "status", "note"])
        w.writerows(out)
    bad = [r for r in out if r[4] == "FAIL"]
    expl = [r for r in out if r[4] == "EXPLAINED"]
    print(f"reproduce: {len(out) - len(bad) - len(expl)} of {len(out)} curated cells reproduced from core, "
          f"{len(expl)} explained by a documented difference, {len(bad)} FAIL (release {t.w.release_id})")
    for r in bad[:10]:
        print("  FAIL", r)


if __name__ == "__main__":
    main()
