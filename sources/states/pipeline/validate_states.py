#!/usr/bin/env python3
"""Validate every state's extracted finances against that state's OWN printed
totals, across its volumes, against independent external series, and - across
states - against the national conformance contract.

    python3 pipeline/validate_states.py --all            # per state
    python3 pipeline/validate_states.py --state Sabah
    python3 pipeline/validate_states.py --all --national # + the national file

Per state  ->  data/<slug>/_validation_<slug>.csv
                data/<slug>/_source_anomalies_<slug>.csv
                data/<slug>/_known_extraction_defects_<slug>.csv
National   ->  data/_national/_validation_national.csv
                data/_national/_known_extraction_defects.csv

`_source_anomalies_<slug>.csv` asserts that the AUDITOR-GENERAL's own printed
figures do not add up, and contains ONLY inconsistencies verified on the
printed page.  A failure this pipeline has diagnosed as ITS OWN defect is
diverted to `_known_extraction_defects_<slug>.csv` (declared in
`state_config.KNOWN_EXTRACTION_DEFECTS`) and its rows are marked
`data_quality=suspect` in the fact files - it stays a FAIL in
`_validation_<slug>.csv`, but the claim "the source misprinted this" is
withdrawn.  Mis-filing our own bug as a source misprint is the one thing this
file must never do (golden rule 2).

V1  internal   - each statement's printed total equals the sum of its printed
                 components; revenue categories sum to the revenue total;
                 opening balance = prior year's closing balance where both are
                 printed in the same table.
V1b continuity - closing balance FY-1 = opening balance FY across volumes.
V2  cross-vol  - a figure restated in a later volume's comparative column must
                 equal the earlier volume's own figure.  Divergences are
                 RESTATEMENTs: catalogued, never corrected.
V3  external   - magnitudes vs DOSM's independent state public-finance series
                 and vs DOSM state GDP.
V4  contract   - the canonical own-year filter is unique.
N1-N5 national - coverage, the accounting identity, code-space collision,
                 row counts, and the panel's own uniqueness.

Nothing here is state-specific: --state only selects the files.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state_config as SC                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REPO = os.path.dirname(os.path.dirname(ROOT))
DOSM = os.path.join(REPO, "sources", "dosm", "data")

TOL = 0.011           # RM juta - the volumes print 2 dp in RM Juta
M = 1_000_000.0

CHECKS: list[dict] = []


def add(check, status, fiscal_year, detail, expected="", actual="", diff="",
        source_file="", pdf_page="", printed_page="", jadual="", proof=""):
    CHECKS.append(dict(
        check=check, status=status, fiscal_year=fiscal_year, detail=detail,
        expected=expected, actual=actual, diff=diff, source_file=source_file,
        pdf_page=pdf_page, printed_page=printed_page, jadual=jadual, proof=proof))


def show(rows, code):
    """`<printed label> <printed amount>` for the proof string."""
    c = cell(rows, code)
    return f'{c["line_label_bm"]} {c["amount_printed"]}' if c else f"{code} (absent)"


def load(state, name):
    p = os.path.join(DATA, SC.slug(state), name)
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding="utf-8")))


def juta(r):
    return float(r["amount_rm"]) / M


def key_of(r):
    """One printed table instance."""
    return (r["source_file"], r["pdf_page"], r["jadual"])


def cell(tab, code, year=None):
    for r in tab:
        if r["line_code"] == code and (year is None or r["fiscal_year"] == year):
            return r
    return None


# ---------------------------------------------------------------------------
# V1
# ---------------------------------------------------------------------------

# fund-flow triples printed in their own table: closing = opening + in - out
FUND_FLOWS = [
    ("akaun_pinjaman_disatukan", "loan_opening_balance", "loan_receipts",
     "loan_payments", "loan_closing_balance", "Akaun Pinjaman Disatukan"),
    ("kumpulan_wang_pembangunan", "devfund_opening_balance", "devfund_receipts",
     "devfund_payments", "devfund_closing_balance", "Kumpulan Wang Pembangunan"),
    ("kumpulan_wang_pembangunan_hutan", "forestfund_opening_balance",
     "forestfund_receipts", "forestfund_payments", "forestfund_closing_balance",
     "Kumpulan Wang Pembangunan Hutan"),
]


def _components(sub, exclude):
    """Every printed row of this table/year that is a leaf component."""
    out = []
    for r in sub:
        if r["line_code"] in exclude:
            continue
        if r.get("row_type") in ("total", "subtotal"):
            continue
        if not r["unit_printed"].startswith("(RM"):
            continue
        out.append(r)
    return out


def closed_form(tot, sub, exclude, named=None):
    """-> (ok, label, value).

    A printed subtotal is only inconsistent when NO exhaustive reading of the
    table's OWN printed components reaches it.  Checking a single hard-coded
    identity instead files every state whose statement carries an extra printed
    line - Sarawak's `Bayaran Lain` RM8.00 bilion transfer to the sovereign
    wealth fund, Pahang's `Perbelanjaan Bekalan Air`, Kelantan's flat trust
    hierarchy - as an Auditor-General misprint, which is exactly the accusation
    golden rule 2 forbids.
    """
    cands = []
    if named is not None:
        cands.append(("the named identity", named))
    comp = _components(sub, exclude)
    if comp:
        cands.append(("the sum of every printed component line",
                      sum(juta(r) for r in comp)))
        cands.append(("the sum of the magnitudes of every printed component line",
                      sum(abs(juta(r)) for r in comp)))
    # and the FLAT reading: every printed line except the total itself, so a
    # subtotal that is really a sibling counts once (Sarawak's Akaun Amanah
    # Disatukan prints a fifth sibling, `Akaun Kena Bayar`:
    # 2,541.52 + 253.95 + 271.98 + 154.46 + 203.95 = 3,425.86 exactly)
    flat = [r for r in sub
            if r["line_code"] not in exclude
            and r.get("row_type") != "total"
            and r["unit_printed"].startswith("(RM")]
    if flat:
        cands.append(("the sum of every printed line except the total itself",
                      sum(juta(r) for r in flat)))
    for lab, v in cands:
        if v is not None and abs(v - tot) <= TOL:
            return True, lab, v
    if not cands:
        return None, "", None
    lab, v = min((c for c in cands if c[1] is not None),
                 key=lambda c: abs(c[1] - tot), default=("", None))
    return False, lab, v


def v1(fin, rev):
    tables = defaultdict(list)
    for r in fin + rev:
        tables[key_of(r)].append(r)

    for k, rows in sorted(tables.items()):
        spec = rows[0]["spec_id"]
        src, page, jad = k
        pp = rows[0]["printed_page"]
        years = sorted({r["fiscal_year"] for r in rows if r["measure"] == "actual"})
        for y in years:
            sub = [r for r in rows if r["fiscal_year"] == y and r["measure"] == "actual"]

            def g(code):
                c = cell(sub, code)
                return juta(c) if c else None

            if spec == "prestasi_kewangan":
                opex, dev, tot = g("opex_before_transfer"), g("devex_total"), g("expenditure_total")
                if None not in (opex, dev, tot):
                    # A state may print a THIRD expenditure head beside Mengurus
                    # and Pembangunan (Pahang's `Perbelanjaan Bekalan Air`,
                    # 69.10 in FY2022: 1,049.08 + 118.27 + 69.10 = 1,236.45,
                    # exactly the printed JUMLAH PERBELANJAAN).  Checking only
                    # the two named heads calls that page a misprint when the
                    # page reconciles exactly - so every printed expenditure
                    # component line counts.
                    extra = [abs(juta(r)) for r in sub
                             if r.get("row_type") == "component"
                             and r["line_code"] not in (
                                 "opex_before_transfer", "devex_total")
                             and re.search(r"perbelanjaan", r["line_label_bm"], re.I)
                             and not re.search(r"jumlah", r["line_label_bm"], re.I)
                             and r["unit_printed"].startswith("(RM")]
                    cands = [("opex + devex", abs(opex) + abs(dev))]
                    if extra:
                        cands.append(("opex + devex + every other printed "
                                      "expenditure head", abs(opex) + abs(dev) + sum(extra)))
                    ok = [c for c in cands if abs(c[1] - abs(tot)) <= TOL]
                    win = ok[0] if ok else min(cands, key=lambda c: abs(c[1] - abs(tot)))
                    add("V1_prestasi_expenditure_total", "PASS" if ok else "FAIL",
                        y, "%s = expenditure_total" % win[0],
                        f"{abs(tot):.2f}", f"{win[1]:.2f}", f"{win[1]-abs(tot):.2f}",
                        src, page, pp, jad)
                revn, sd = g("revenue_total"), g("surplus_deficit")
                if None not in (revn, tot, sd):
                    # Several volumes print the balance line as an UNSIGNED
                    # magnitude under a `LEBIHAN/KURANGAN` caption and leave
                    # the direction to the narrative (Johor CMD.30.2019 J1:
                    # `LEBIHAN/KURANGAN 19.62  105.23`, and the prose calls
                    # both a `kurangan`).  Comparing a signed identity against
                    # that magnitude accused the volume of a 2x misprint, so
                    # compare magnitudes - the same convention the financing
                    # check already uses.
                    d = abs(revn - abs(tot)) - abs(sd)
                    add("V1_prestasi_surplus", "PASS" if abs(d) <= TOL else "FAIL",
                        y, "|revenue_total - expenditure_total| = |surplus_deficit|",
                        f"{abs(sd):.2f}", f"{abs(revn-abs(tot)):.2f}", f"{d:.2f}",
                        src, page, pp, jad)
                ft = g("financing_total")
                parts = [g("financing_external_loans"), g("financing_loan_repayment"),
                         g("financing_cash_investment_trust")]
                dom = g("financing_domestic_loans")
                if dom is not None:
                    parts.append(dom)
                if ft is not None and all(p is not None for p in parts):
                    # era <= FY2018 prints financing lines with the surplus's
                    # own sign, era >= FY2019 flips it: compare magnitudes
                    d = abs(sum(parts)) - abs(ft)
                    add("V1_prestasi_financing", "PASS" if abs(d) <= TOL else "FAIL",
                        y, "financing components = financing_total (absolute)",
                        f"{abs(ft):.2f}", f"{sum(parts):.2f}", f"{d:.2f}",
                        src, page, pp, jad)
                if ft is not None and sd is not None:
                    d = abs(abs(ft) - abs(sd))
                    add("V1_prestasi_financing_vs_surplus",
                        "PASS" if d <= TOL else "FAIL", y,
                        "|financing_total| = |surplus_deficit|",
                        f"{abs(sd):.2f}", f"{abs(ft):.2f}", f"{d:.2f}",
                        src, page, pp, jad)

            if spec == "akaun_hasil_disatukan":
                ob, revn = g("cra_opening_balance"), g("revenue_total")
                op, sd, cb = g("opex_total"), g("cra_surplus_deficit"), g("cra_closing_balance")
                if None not in (revn, op, sd):
                    # The statement may print further OUTFLOW lines between
                    # revenue and the balance - Perlis prints `Pindahan Ke
                    # Kumpulan Wang Pembangunan` (FY2013: 143.82 - 146.15 -
                    # 32.94 = -35.27, exactly the printed Defisit).  Checking
                    # only revenue less operating expenditure called five of
                    # those pages a misprint.
                    other = [abs(juta(r)) for r in sub
                             if r["line_code"] not in (
                                 "cra_opening_balance", "cra_closing_balance",
                                 "revenue_total", "opex_total",
                                 "cra_surplus_deficit")
                             and r.get("row_type") == "component"
                             and r["unit_printed"].startswith("(RM")]
                    cands = [("revenue - opex", revn - abs(op))]
                    if other:
                        cands.append(("revenue - opex - every other printed "
                                      "outflow line", revn - abs(op) - sum(other)))
                    ok = [c for c in cands if abs(c[1] - sd) <= TOL]
                    win = ok[0] if ok else min(cands, key=lambda c: abs(c[1] - sd))
                    add("V1_cra_surplus", "PASS" if ok else "FAIL", y,
                        f"{win[0]} = surplus/deficit (Akaun Hasil Disatukan)",
                        f"{sd:.2f}", f"{win[1]:.2f}", f"{win[1]-sd:.2f}",
                        src, page, pp, jad)
                if None not in (ob, sd, cb):
                    # `opening + surplus = closing` unless the volume prints
                    # further flow lines (Sarawak FY2024 prints `Bayaran Lain`
                    # 8,000.00, the transfer to the state sovereign wealth
                    # fund, between the surplus and the closing balance).
                    flows = [r for r in sub
                             if r["line_code"] not in (
                                 "cra_opening_balance", "cra_closing_balance",
                                 "revenue_total", "opex_total")
                             and r["unit_printed"].startswith("(RM")]
                    cands = [("opening + surplus", ob + sd)]
                    # Johor prints `(-) Pelarasan Tahun Sebelum` (a prior-year adjustment, always subtracted;
                    # printed 1.65 in FY2018 and (1.09) in FY2019) and `Baki Selepas Pelarasan` between the
                    # opening balance and the surplus (CMD.30.2019.pdf p33, CMD.39.2021.pdf p35)
                    adj = [r for r in sub if r["line_code"] == "akaun_hasil_disatukan.pelarasan_tahun_sebelum"]
                    after = [r for r in sub if r["line_code"] == "akaun_hasil_disatukan.baki_selepas_pelarasan"]
                    if adj:
                        cands.append(("opening - printed prior-year adjustment + surplus",
                                      ob - abs(juta(adj[0])) + sd))
                    if after:
                        cands.append(("printed balance after adjustment + surplus", juta(after[0]) + sd))
                    if flows:
                        alt = ob + sum(juta(r) for r in flows)
                        cands.append(("opening + every printed flow line", alt))
                        cands.append(("opening + surplus - other printed flows",
                                      ob + sd - sum(abs(juta(r)) for r in flows
                                                    if r["line_code"] != "cra_surplus_deficit")))
                    ok = [c for c in cands if abs(c[1] - cb) <= TOL]
                    win = ok[0] if ok else min(cands, key=lambda c: abs(c[1] - cb))
                    add("V1_cra_closing", "PASS" if ok else "FAIL", y,
                        f"{win[0]} = closing (Akaun Hasil Disatukan)",
                        f"{cb:.2f}", f"{win[1]:.2f}", f"{win[1]-cb:.2f}",
                        src, page, pp, jad)

            if spec == "kumpulan_wang_disatukan":
                parts = [g("cra_balance"), g("loan_account_balance"),
                         g("trust_account_balance")]
                tot = g("kwd_balance")
                if tot is not None and all(p is not None for p in parts):
                    d = sum(parts) - tot
                    add("V1_kwd_total", "PASS" if abs(d) <= TOL else "FAIL", y,
                        "hasil + pinjaman + amanah = Kumpulan Wang Disatukan",
                        f"{tot:.2f}", f"{sum(parts):.2f}", f"{d:.2f}", src, page, pp, jad)

            for fspec, ob_c, in_c, out_c, cb_c, label in FUND_FLOWS:
                if spec != fspec:
                    continue
                ob, ic, oc, cb = g(ob_c), g(in_c), g(out_c), g(cb_c)
                # the identity only holds when the table prints exactly the
                # four flow lines; several states add memo lines (a transfer
                # in, a `Pelarasan`), and then a mismatch says nothing about
                # the source
                extra = [r for r in sub
                         if r["line_code"] not in (ob_c, in_c, out_c, cb_c)
                         and r["row_type"] == "component"]
                if None not in (ob, ic, oc, cb):
                    d = (ob + abs(ic) - abs(oc)) - cb
                    add("V1_fund_flow",
                        "PASS" if abs(d) <= TOL else
                        ("INCONCLUSIVE" if extra else "FAIL"), y,
                        f"opening + receipts - payments = closing ({label})",
                        f"{cb:.2f}", f"{ob+abs(ic)-abs(oc):.2f}", f"{d:.2f}",
                        src, page, pp, jad,
                        f'{show(sub, ob_c)} + {show(sub, in_c)} - {show(sub, out_c)} '
                        f'vs printed closing {show(sub, cb_c)} for FY{y} (RM juta)')

            if spec in ("kumpulan_wang_disatukan", "akaun_amanah_disatukan"):
                # The states do NOT all print the same hierarchy under `Akaun
                # Amanah Disatukan`, and the difference is a presentation
                # choice, not a misprint:
                #
                #   NESTED (Selangor)  Akaun Amanah Disatukan
                #                        Kumpulan Wang Amanah Kerajaan   <- roll-up
                #                          KW Pembangunan / Pinjaman Perumahan /
                #                          Pelbagai KWA / Pembangunan Hutan
                #                        Kumpulan Wang Amanah Awam
                #                        Akaun Deposit
                #
                #   FLAT (Kelantan)    Akaun Amanah Disatukan terdiri daripada:
                #                        Kumpulan Wang Amanah Kerajaan   <- sibling
                #                        Kumpulan Wang Pembangunan       <- sibling
                #                        Kumpulan Wang Amanah Awam
                #                        Akaun Deposit
                #
                # Which one a volume uses is decided FROM THE TABLE'S OWN
                # ARITHMETIC, never assumed: whichever candidate composition
                # reconciles to the printed `Akaun Amanah Disatukan` is the
                # hierarchy that volume prints.  Only when NO candidate
                # reconciles is the table's own arithmetic inconsistent, and
                # only then is it a source anomaly.
                SUBFUNDS = ("development_fund", "housing_loan_fund",
                            "misc_govt_trust_funds", "forest_development_fund")
                subv = {c: g(c) for c in SUBFUNDS if g(c) is not None}
                gtf, tot = g("govt_trust_funds"), g("trust_account_balance")
                pub, dep = g("public_trust_funds"), g("deposit_account")
                cands: list[tuple[str, float, str]] = []
                if tot is not None and pub is not None and dep is not None:
                    if gtf is not None:
                        cands.append((
                            "nested", gtf + pub + dep,
                            "KW Amanah Kerajaan + KW Amanah Awam + Akaun Deposit"))
                        if subv:
                            cands.append((
                                "flat", gtf + sum(subv.values()) + pub + dep,
                                "KW Amanah Kerajaan + " +
                                " + ".join(sorted(subv)) +
                                " + KW Amanah Awam + Akaun Deposit"))
                    elif len(subv) == len(SUBFUNDS):
                        # era 4 drops the KW Amanah Kerajaan subtotal line
                        cands.append((
                            "era4_no_subtotal", sum(subv.values()) + pub + dep,
                            "the four sub-funds + KW Amanah Awam + Akaun Deposit"))
                if cands:
                    ok = [c for c in cands if abs(c[1] - tot) <= TOL]
                    if not ok:
                        # a state may print further SIBLING funds inside the
                        # trust block that no conformed code covers (Sarawak
                        # prints `Akaun Kena Bayar`: 4,442.91 + 2,381.63 +
                        # 231.33 + 144.01 + 279.69 = 7,479.57, exactly the
                        # printed Akaun Amanah Disatukan for FY2017).  Those
                        # keep an unconformed `<spec>.<slug>` code, so add them
                        # to each candidate before calling the page a misprint.
                        named = {"govt_trust_funds", "public_trust_funds",
                                 "deposit_account", "trust_account_balance",
                                 "cra_balance", "loan_account_balance",
                                 "kwd_balance", "cra_opening_balance",
                                 "cra_closing_balance"} | set(SUBFUNDS)
                        extras = [juta(r) for r in sub
                                  if r["line_code_conformed"] == "no"
                                  and r.get("row_type") == "component"
                                  and r["line_code"] not in named
                                  and r["unit_printed"].startswith("(RM")]
                        if extras:
                            cands += [(f"{c[0]}+siblings", c[1] + sum(extras),
                                       c[2] + " + every other printed sibling fund")
                                      for c in list(cands)]
                            ok = [c for c in cands if abs(c[1] - tot) <= TOL]
                    if not ok:
                        # states with extra sibling funds (Sarawak prints
                        # several of its own) are read closed-form
                        cf_ok, cf_lab, cf_v = closed_form(
                            tot, sub, {"trust_account_balance"})
                        if cf_ok:
                            cands.append((f"closed-form: {cf_lab}", cf_v, cf_lab))
                            ok = [cands[-1]]
                    win = ok[0] if ok else min(cands, key=lambda c: abs(c[1] - tot))
                    pr = (f'{win[2]} = {win[1]:.2f}, and '
                          f'{show(sub, "trust_account_balance")} is printed for '
                          f'FY{y} (RM juta); printed hierarchy = {win[0]}')
                    add("V1_trust_account_composition",
                        "PASS" if ok else "FAIL", y,
                        f"{win[2]} = Akaun Amanah Disatukan "
                        f"[{win[0]} presentation]",
                        f"{tot:.2f}", f"{win[1]:.2f}", f"{win[1]-tot:.2f}",
                        src, page, pp, jad, pr)
                    presentation = win[0] if ok else ""
                else:
                    presentation = ""

                # KW Amanah Kerajaan = its four sub-funds - only meaningful in
                # the NESTED presentation; in a flat table the sub-funds are
                # siblings and the identity does not hold by construction.
                sub_parts = [g(c) for c in SUBFUNDS]
                if (presentation != "flat" and gtf is not None
                        and all(p is not None for p in sub_parts)):
                    d = sum(sub_parts) - gtf
                    pr = (f'{show(sub, "development_fund")} + '
                          f'{show(sub, "housing_loan_fund")} + '
                          f'{show(sub, "misc_govt_trust_funds")} + '
                          f'{show(sub, "forest_development_fund")} = '
                          f'{sum(sub_parts):.2f}, but '
                          f'{show(sub, "govt_trust_funds")} is printed for FY{y} '
                          f'(RM juta)')
                    add("V1_govt_trust_fund_composition",
                        "PASS" if abs(d) <= TOL else "FAIL", y,
                        "KW Pembangunan + KW Pinjaman Perumahan + Pelbagai KWA "
                        "+ KW Pembangunan Hutan = KW Amanah Kerajaan",
                        f"{gtf:.2f}", f"{sum(sub_parts):.2f}", f"{d:.2f}",
                        src, page, pp, jad, pr)

            if spec in ("hasil_kategori", "prestasi_kewangan"):
                parts = [g("revenue_tax"), g("revenue_nontax"),
                         g("revenue_nonrevenue_receipts")]
                tot = g("revenue_total")
                if tot is not None and all(p is not None for p in parts):
                    # Sarawak prints a FOURTH revenue head, `Pemberian
                    # Kerajaan Persekutuan dan Bayaran Balik` (FY2020:
                    # 6,390.70 + 3,976.90 + 248.34 + 30.75 = 10,646.69, the
                    # printed JUMLAH exactly), so the three named categories
                    # are not the whole of every state's revenue.
                    named = {"revenue_tax", "revenue_nontax",
                             "revenue_nonrevenue_receipts", "revenue_total"}
                    extra = [juta(r) for r in sub
                             if r["line_code"] not in named
                             and r.get("row_type") == "component"
                             and r["line_code_conformed"] == "no"
                             and r["unit_printed"].startswith("(RM")]
                    cands = [("the three printed categories", sum(parts))]
                    if extra:
                        cands.append(("every printed revenue head",
                                      sum(parts) + sum(extra)))
                    ok = [c for c in cands if abs(c[1] - tot) <= TOL]
                    win = ok[0] if ok else min(cands, key=lambda c: abs(c[1] - tot))
                    add("V1_revenue_categories", "PASS" if ok else "FAIL",
                        y, f"{win[0]} = jumlah hasil",
                        f"{tot:.2f}", f"{win[1]:.2f}", f"{win[1]-tot:.2f}",
                        src, page, pp, jad)

            if spec == "hasil_penyumbang_utama":
                money = [r for r in sub if r["unit_printed"].startswith("(RM")]
                tot_r = [r for r in money
                         if r["line_code"] == "revenue_top_contributors_total"]
                # contributor lines only: a printed banner total (`JUMLAH HASIL RM421.24 Juta`, all revenue,
                # Negeri Sembilan) is a total row, not a sixth contributor
                comp = [r for r in money if r not in tot_r and r["row_type"] != "total"]
                if tot_r and len(comp) >= 2:
                    s = sum(juta(r) for r in comp)
                    d = s - juta(tot_r[0])
                    add("V1_penyumbang_utama_total", "PASS" if abs(d) <= TOL else "FAIL",
                        y, "top-contributor lines = printed JUMLAH",
                        f"{juta(tot_r[0]):.2f}", f"{s:.2f}", f"{d:.2f}", src, page, pp, jad)

        # in-table continuity: this table prints two consecutive years
        if spec == "akaun_hasil_disatukan" and len(years) >= 2:
            for a, b in zip(years, years[1:]):
                ca = cell([r for r in rows if r["fiscal_year"] == a], "cra_closing_balance")
                ob = cell([r for r in rows if r["fiscal_year"] == b], "cra_opening_balance")
                if ca and ob:
                    d = juta(ca) - juta(ob)
                    add("V1_continuity_in_table", "PASS" if abs(d) <= TOL else "FAIL",
                        b, f"closing {a} = opening {b} (same printed table)",
                        f"{juta(ca):.2f}", f"{juta(ob):.2f}", f"{d:.2f}", src, page, pp, jad)


# ---------------------------------------------------------------------------
# V1b year-on-year continuity across volumes
# ---------------------------------------------------------------------------

def v1b(fin):
    own = defaultdict(dict)
    for r in fin:
        if r["column_role"] == "own_year" and r["measure"] == "actual":
            own[r["fiscal_year"]].setdefault(r["line_code"], r)
    years = sorted(own)
    for a, b in zip(years, years[1:]):
        if int(b) - int(a) != 1:
            continue
        ca, ob = own[a].get("cra_closing_balance"), own[b].get("cra_opening_balance")
        if ca and ob:
            d = juta(ca) - juta(ob)
            add("V1_continuity_cross_volume", "PASS" if abs(d) <= TOL else "FAIL",
                b, f"CRA closing FY{a} ({ca['source_file']}) = opening FY{b} ({ob['source_file']})",
                f"{juta(ca):.2f}", f"{juta(ob):.2f}", f"{d:.2f}",
                ob["source_file"], ob["pdf_page"], ob["printed_page"], ob["jadual"])


# ---------------------------------------------------------------------------
# V1c intra-volume contradiction
# ---------------------------------------------------------------------------

# Statements that describe the SAME underlying quantity.  A figure printed
# twice inside one volume is only a contradiction when both printings belong to
# the same family; a Penyata Prestasi Kewangan `Hasil` and an Akaun Hasil
# Disatukan `Hasil` are different concepts (the fund-flow statement includes
# receipts the revenue account does not), and their difference is reported as
# an informative cross-statement divergence, not as a misprint.
STATEMENT_FAMILY = {
    "penyata_kedudukan_kewangan": "fund_balances",
    "akaun_amanah_disatukan": "fund_balances",
    "akaun_pinjaman_disatukan": "fund_balances",
    "akaun_hasil_disatukan": "revenue_account",
    "penyata_prestasi_kewangan": "fund_flow",
    "akaun_memorandum": "memorandum",
    "perbelanjaan_mengurus": "expenditure",
    "perbelanjaan_pembangunan": "expenditure",
}


# Codes whose value depends on WHICH aggregation level a table prints them at.
HIERARCHY_SENSITIVE = {
    "govt_trust_funds", "misc_govt_trust_funds", "trust_account_balance",
    "cra_balance", "loan_account_balance", "development_fund",
    "forest_development_fund", "housing_loan_fund", "public_trust_funds",
    "deposit_account",
}


def v1c(fin, rev):
    """The SAME volume printing two different figures for the same line/year.

    Three distinct situations, kept apart because only one of them is a
    misprint:

    * CONTRADICTION - two different JADUAL of the SAME statement family print
      different values.  Selangor CMD.50.2021 is the worked example: JADUAL 2
      and JADUAL 3 print the FY2019 Kumpulan Wang Amanah Kerajaan as 1,114.60
      while JADUAL 24 in the same volume prints 1,070.87 - and only 1,070.87
      reconciles with that volume's own Akaun Amanah Disatukan total.  Both are
      kept exactly as printed; the contradiction is catalogued (golden rule 2).
      These are the rows promoted to `_source_anomalies_<slug>.csv`.
    * DIVERGENCE - two different statements print the same conformed code with
      different values.  Informative (it is exactly the kind of gap this
      warehouse exists to surface), never an anomaly.
    * V5_duplicate_code_in_table - the SAME printed table yields two rows with
      one conformed code.  That is an EXTRACTION signal, not a source fact:
      the volume printed two lines that the dictionary cannot tell apart
      (typically a `LEBIHAN/KURANGAN` row and a `Kurangan Dibiayai Oleh: ...`
      row).  `is_canonical` already picks one; the collision is reported so it
      can be fixed rather than hidden.
    """
    seen = defaultdict(list)
    for r in fin + rev:
        if r["measure"] != "actual" or r["line_code"] not in CORE:
            continue
        seen[(r["source_file"], r["fiscal_year"], r["line_code"])].append(r)

    for (src, y, code), rows in sorted(seen.items()):
        by_table = defaultdict(list)
        for r in rows:
            by_table[(r["pdf_page"], r["jadual"])].append(r)
        # (a) same printed table, two values
        for (pg, jad), rs in sorted(by_table.items()):
            vals = {round(juta(r), 2) for r in rs}
            if len(vals) > 1:
                a, b = min(vals), max(vals)
                add("V5_duplicate_code_in_table", "FAIL", y,
                    f"{code} is produced twice by the same printed table "
                    f"{src} J{jad} with different values",
                    f"{a:.2f}", f"{b:.2f}", f"{b - a:.2f}", src, pg,
                    rs[0]["printed_page"], jad,
                    " | ".join(f'{r["line_label_bm"]} {r["amount_printed"]}'
                               for r in rs[:4]))
        # (b) across tables
        best: dict[tuple, dict] = {}
        for r in rows:
            k = (r["pdf_page"], r["jadual"])
            best.setdefault(k, r)
        vals: dict[float, dict] = {}
        for r in best.values():
            vals.setdefault(round(juta(r), 2), r)
        if len(vals) < 2:
            continue
        items = sorted(vals.items())
        lo, hi = items[0], items[-1]
        if abs(hi[0] - lo[0]) <= TOL:
            continue
        fam_lo = STATEMENT_FAMILY.get(lo[1].get("statement") or lo[1]["spec_id"], lo[1]["spec_id"])
        fam_hi = STATEMENT_FAMILY.get(hi[1].get("statement") or hi[1]["spec_id"], hi[1]["spec_id"])
        same_family = fam_lo == fam_hi
        # A HIERARCHY-SENSITIVE code legitimately denotes different aggregation
        # levels in a summary table and in the detailed table of the same
        # volume.  Kelantan CMD.31.2020 FY2018 is the worked example: JADUAL 2
        # prints `Kumpulan Wang Amanah Kerajaan` 984.64 (= Pelbagai 1,072.41 -
        # KW Bekalan Air 87.77, with KW Pembangunan shown as a sibling) while
        # JADUAL 23 prints 194.76 (= 1,072.41 - 789.88 - 87.77, with KW
        # Pembangunan folded in).  BOTH reconcile against their own table, so
        # neither is a misprint.  Such a difference is only a contradiction
        # when at least one of the two tables fails its OWN composition check.
        if same_family and lo[1]["line_code"] in HIERARCHY_SENSITIVE:
            bad_tables = {(c["source_file"], c["jadual"], c["fiscal_year"])
                          for c in CHECKS
                          if c["status"] == "FAIL" and "composition" in c["check"]}
            if not ({(src, lo[1]["jadual"], y), (src, hi[1]["jadual"], y)}
                    & bad_tables):
                same_family = False
        add("V1_intra_volume_contradiction" if same_family
            else "V3_cross_statement_divergence",
            "FAIL" if same_family else "DIVERGENCE", y,
            f"{code} for FY{y} is printed with two different values inside "
            f"{src}: J{lo[1]['jadual']} ({lo[1]['spec_id']}) vs "
            f"J{hi[1]['jadual']} ({hi[1]['spec_id']})",
            f"{lo[0]:.2f}", f"{hi[0]:.2f}", f"{hi[0]-lo[0]:.2f}",
            src, hi[1]["pdf_page"], hi[1]["printed_page"], hi[1]["jadual"],
            f'{lo[1]["line_label_bm"]} {lo[1]["amount_printed"]} on pdf p'
            f'{lo[1]["pdf_page"]} (J{lo[1]["jadual"]}) vs '
            f'{hi[1]["line_label_bm"]} {hi[1]["amount_printed"]} on pdf p'
            f'{hi[1]["pdf_page"]} (J{hi[1]["jadual"]}) - same volume, same '
            f'fiscal year; both kept as printed')


# ---------------------------------------------------------------------------
# V2 restatements
# ---------------------------------------------------------------------------

CORE = {"revenue_total", "opex_before_transfer", "devex_total", "expenditure_total",
        "surplus_deficit", "cra_opening_balance", "cra_closing_balance",
        "cra_surplus_deficit", "opex_total", "kwd_balance", "cra_balance",
        "trust_account_balance", "loan_account_balance", "revenue_tax",
        "revenue_nontax", "revenue_nonrevenue_receipts", "debt_total",
        "cash_total", "investment_total", "deposit_account",
        "public_trust_funds", "govt_trust_funds", "development_fund",
        "forest_development_fund", "housing_loan_fund", "misc_govt_trust_funds"}

# A code is only anchored from the statement that DEFINES it, so that a
# same-named line in a supporting table cannot masquerade as the anchor.
PRIMARY_SPEC = {
    "revenue_total": {"prestasi_kewangan", "akaun_hasil_disatukan", "hasil_kategori"},
    "opex_before_transfer": {"prestasi_kewangan"},
    "devex_total": {"prestasi_kewangan"},
    "expenditure_total": {"prestasi_kewangan"},
    "surplus_deficit": {"prestasi_kewangan"},
    "opex_total": {"akaun_hasil_disatukan"},
    "cra_opening_balance": {"akaun_hasil_disatukan"},
    "cra_closing_balance": {"akaun_hasil_disatukan"},
    "cra_surplus_deficit": {"akaun_hasil_disatukan"},
    "kwd_balance": {"kumpulan_wang_disatukan"},
    "cra_balance": {"kumpulan_wang_disatukan"},
    "trust_account_balance": {"kumpulan_wang_disatukan", "akaun_amanah_disatukan"},
    "loan_account_balance": {"kumpulan_wang_disatukan"},
    "cash_total": {"wang_tunai"},
    "investment_total": {"pelaburan", "wang_tunai"},
    "revenue_tax": {"hasil_kategori", "prestasi_kewangan"},
    "revenue_nontax": {"hasil_kategori", "prestasi_kewangan"},
    "revenue_nonrevenue_receipts": {"hasil_kategori", "prestasi_kewangan"},
}


def v2(fin, rev):
    anchor: dict[tuple[str, str], dict] = {}
    for r in fin + rev:
        ok = PRIMARY_SPEC.get(r["line_code"])
        if (r["column_role"] == "own_year" and r["measure"] == "actual"
                and r["line_code"] in CORE and (ok is None or r["spec_id"] in ok)):
            anchor.setdefault((r["line_code"], r["fiscal_year"]), r)

    seen: set[tuple] = set()
    for r in fin + rev:
        if r["column_role"] != "comparative" or r["measure"] != "actual":
            continue
        if r["line_code"] not in CORE:
            continue
        ok = PRIMARY_SPEC.get(r["line_code"])
        if ok is not None and r["spec_id"] not in ok:
            continue
        a = anchor.get((r["line_code"], r["fiscal_year"]))
        if not a:
            continue
        k = (r["line_code"], r["fiscal_year"], r["source_file"], r["spec_id"])
        if k in seen:
            continue
        seen.add(k)
        d = juta(r) - juta(a)
        if abs(d) <= TOL:
            status = "PASS"
        elif abs(abs(juta(r)) - abs(juta(a))) <= TOL:
            status = "SIGN_CONVENTION"     # same magnitude, era flipped the sign
        else:
            status = "RESTATEMENT"
        add("V2_restatement", status, r["fiscal_year"],
            f'{r["line_code"]} for FY{r["fiscal_year"]}: own volume '
            f'{a["source_file"]} J{a["jadual"]} vs later volume '
            f'{r["source_file"]} J{r["jadual"]} ({r["spec_id"]})',
            f"{juta(a):.2f}", f"{juta(r):.2f}", f"{d:.2f}",
            r["source_file"], r["pdf_page"], r["printed_page"], r["jadual"])


# ---------------------------------------------------------------------------
# V3 external
# ---------------------------------------------------------------------------

DOSM_REV = {"revenue_60000": "revenue_tax", "revenue_70000": "revenue_nontax",
            "revenue_80000": "revenue_nonrevenue_receipts", "total": "revenue_total"}
DOSM_EXP = {"oe": "opex_before_transfer", "de": "devex_total"}


def v3(fin, rev, state):
    own = defaultdict(dict)
    for r in fin + rev:
        if r["column_role"] == "own_year" and r["measure"] == "actual":
            own[r["fiscal_year"]].setdefault(r["line_code"], r)

    for fname, mapping, col in (("state_finance_revenue.csv", DOSM_REV, "revenue"),
                                ("state_finance_expenditure.csv", DOSM_EXP, "expenditure")):
        p = os.path.join(DOSM, fname)
        if not os.path.exists(p):
            add("V3_dosm_state_finance", "INFO", "", f"{fname} not present", "", "", "")
            continue
        for row in csv.DictReader(open(p, encoding="utf-8")):
            if row["state"].strip().lower() != state.lower():
                continue
            code = mapping.get(row["category"])
            if not code:
                continue
            y = row["date"][:4]
            ours = own.get(y, {}).get(code)
            if not ours:
                continue
            theirs = float(row[col])
            d = juta(ours) - theirs
            add("V3_vs_dosm_state_finance",
                "MATCH" if abs(d) <= 0.02 else "DIVERGENCE", y,
                f"{code}: LKAN (audited) vs DOSM/data.gov.my {row['category']}",
                f"{theirs:.2f}", f"{juta(ours):.2f}", f"{d:.2f}",
                ours["source_file"], ours["pdf_page"], ours["printed_page"],
                ours["jadual"])

    gdp = os.path.join(DOSM, "gdp_state_real_supply.csv")
    if os.path.exists(gdp):
        g = {}
        for row in csv.DictReader(open(gdp, encoding="utf-8")):
            if (row["state"].strip().lower() == state.lower()
                    and row["sector"] == "p0" and row["series"] == "abs"):
                g[row["date"][:4]] = float(row["value"])
        for y in sorted(own):
            r = own[y].get("revenue_total")
            if r and y in g:
                ratio = juta(r) / g[y] * 100
                add("V3_revenue_to_state_gdp",
                    "INFO" if 0.2 <= ratio <= 12 else "OUT_OF_RANGE", y,
                    f"state revenue as % of DOSM state GDP (real, RM juta {g[y]:.0f})",
                    "", f"{ratio:.2f}%", "", r["source_file"], r["pdf_page"],
                    r["printed_page"], r["jadual"])


# ---------------------------------------------------------------------------
# V4 - the aggregation contract
# ---------------------------------------------------------------------------

def v4(fin, rev):
    """`column_role=own_year AND is_canonical=yes AND measure=actual` must give
    exactly one row per (fiscal_year, line_code); otherwise a consumer summing
    the file would double-count."""
    for name, rows in (("fact_state_finance", fin), ("fact_state_revenue", rev)):
        seen = defaultdict(list)
        for r in rows:
            if (r["column_role"] == "own_year" and r["is_canonical"] == "yes"
                    and r["measure"] == "actual"):
                seen[(r["fiscal_year"], r["line_code"])].append(r)
        dups = {k: v for k, v in seen.items() if len(v) > 1}
        add("V4_canonical_unique", "PASS" if not dups else "FAIL", "",
            f"{name}: canonical own-year filter yields one row per "
            f"(fiscal_year, line_code)",
            "0 duplicates", f"{len(dups)} duplicates", str(len(dups)))
        for (y, code), v in list(dups.items())[:20]:
            add("V4_canonical_unique", "FAIL", y,
                f"{name}: {code} appears {len(v)}x",
                "1", str(len(v)), str(len(v) - 1),
                v[0]["source_file"], v[0]["pdf_page"], v[0]["printed_page"],
                v[0]["jadual"])


# ---------------------------------------------------------------------------
# per state
# ---------------------------------------------------------------------------

def validate_state(state: str) -> dict:
    global CHECKS
    CHECKS = []
    key = SC.slug(state)
    fin = load(state, f"fact_state_finance_{key}.csv")
    rev = load(state, f"fact_state_revenue_{key}.csv")
    if not fin:
        print(f"[{state}] no facts - run extract first")
        return dict(state=state, checks=0, fails=0, anomalies=0)

    v1(fin, rev)
    v4(fin, rev)
    v1b(fin)
    v1c(fin, rev)
    v2(fin, rev)
    v3(fin, rev, state)

    for c in CHECKS:  # FAIL -> SOURCE_ANOMALY only when proved on the archived page (state_config)
        d = SC.page_proved(state, c) if c["status"] == "FAIL" and c["check"].startswith("V1_") else None
        if d:
            c["status"] = "SOURCE_ANOMALY"
            c["proof"] = (c["proof"] + " | " if c["proof"] else "") + f"page-proved: {d['proof']} ({d['evidence']})"
    out = os.path.join(DATA, key, f"_validation_{key}.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CHECKS[0].keys()))
        w.writeheader()
        w.writerows(CHECKS)

    # Source anomalies: an internal-consistency FAIL means the VOLUME's own
    # printed figures do not add up.  Kept exactly as printed (golden rule 2)
    # with the arithmetic proof.
    # A V1 failure this pipeline has already DIAGNOSED as its own defect is
    # not a source anomaly: filing it here would accuse the Auditor-General of
    # misprinting a page that in fact reconciles.  Those failures stay in
    # `_validation_<slug>.csv` (they are failures) and are reported, with their
    # diagnosis, in `_known_extraction_defects_<slug>.csv`.
    anomalies = []
    diverted = 0
    for c in CHECKS:
        if c["check"].startswith("V1_") and c["status"] in ("FAIL", "SOURCE_ANOMALY"):
            if SC.is_known_defect_check(state, c):
                diverted += 1
                continue
            anomalies.append(dict(
                state=state, fiscal_year=c["fiscal_year"],
                source_file=c["source_file"], pdf_page=c["pdf_page"],
                printed_page=c["printed_page"], jadual=c["jadual"],
                anomaly=("the same volume prints two different values for the "
                         "same line and year"
                         if c["check"] == "V1_intra_volume_contradiction"
                         else "printed subtotal does not equal the sum of its "
                              "own printed components"),
                rule=c["detail"],
                printed_total=c["expected"], sum_of_components=c["actual"],
                difference_rm_juta=c["diff"],
                proof=c["proof"] or
                      f'printed {c["expected"]} vs components summing to '
                      f'{c["actual"]} (difference {c["diff"]} RM juta)',
                page_proved="yes" if c["status"] == "SOURCE_ANOMALY" else "no (arithmetic only; stays a FAIL until proved on the archived page)",
                treatment="kept as printed; no figure altered. This file "
                          "contains ONLY inconsistencies verified on the "
                          "printed page; defects of our own extraction are "
                          "tracked in _known_extraction_defects_<slug>.csv, "
                          "never here.",
            ))
    fields = ["state", "fiscal_year", "source_file", "pdf_page", "printed_page",
              "jadual", "anomaly", "rule", "printed_total", "sum_of_components",
              "difference_rm_juta", "proof", "page_proved", "treatment"]
    with open(os.path.join(DATA, key, f"_source_anomalies_{key}.csv"),
              "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(anomalies)

    tally = defaultdict(int)
    for c in CHECKS:
        tally[(c["check"].split("_")[0], c["status"])] += 1
    v1n = sum(n for (chk, st), n in tally.items() if chk == "V1")
    v1f = sum(n for (chk, st), n in tally.items() if chk == "V1" and st == "FAIL")
    v4f = sum(n for (chk, st), n in tally.items() if chk == "V4" and st == "FAIL")
    rest = sum(n for (chk, st), n in tally.items() if st == "RESTATEMENT")
    print(f"{state:18s} checks={len(CHECKS):5d}  V1={v1n:4d} (FAIL {v1f:2d})  "
          f"V4_FAIL={v4f}  restatements={rest}  anomalies={len(anomalies)}"
          + (f"  known_defects={diverted}" if diverted else ""))
    return dict(state=state, checks=len(CHECKS), v1=v1n, v1_fail=v1f,
                v4_fail=v4f, restatements=rest, anomalies=len(anomalies),
                known_defects=diverted)


# ---------------------------------------------------------------------------
# national
# ---------------------------------------------------------------------------

REQUIRED = ["revenue_total", "opex_before_transfer", "devex_total",
            "expenditure_total", "surplus_deficit"]

# codes that are conformed by construction - a state-specific fund must NEVER
# acquire one of these
CONFORMED_UNIVERSE_NOTE = ("only the four statutory funds (Kumpulan Wang "
                           "Pembangunan / Pembangunan Hutan / Pinjaman "
                           "Perumahan / Amanah Awam) are conformed; every other "
                           "state fund keeps an unconformed <spec_id>.<slug> code")


def national() -> None:
    global CHECKS
    CHECKS = []
    panel = os.path.join(DATA, "_national", "fact_state_finance_all.csv")
    rows = list(csv.DictReader(open(panel, encoding="utf-8")))
    by = defaultdict(dict)
    for r in rows:
        by[(r["state"], r["fiscal_year"])][(r["line_code"], r["measure"])] = r

    # N0 panel uniqueness
    seen = defaultdict(int)
    for r in rows:
        seen[(r["state"], r["fiscal_year"], r["line_code"], r["measure"])] += 1
    dups = {k: v for k, v in seen.items() if v > 1}
    add("N0_panel_unique", "PASS" if not dups else "FAIL", "",
        "one row per (state, fiscal_year, line_code, measure)",
        "0 duplicates", f"{len(dups)} duplicates", str(len(dups)))

    # N1 coverage: every state-year carries the headline codes
    for state in SC.STATES:
        cfg_years = sorted({str(v["fiscal_year"]) for v in SC.VOLUMES[state]
                            if v["fiscal_year"]})
        got_years = sorted({y for (s, y) in by if s == state})
        for y in cfg_years:
            if y not in got_years:
                vol = [v for v in SC.VOLUMES[state] if str(v["fiscal_year"]) == y][0]
                add("N1_state_year_present", "ABSENT", y,
                    f"{state}: volume {vol['file']} declared for FY{y} yields no "
                    f"canonical own-year row",
                    "rows", "0", "", vol["file"], "", "", "",
                    "image-only volume" if vol.get("text_layer") == "image_only"
                    else "see _unparsed_tables for the reason")
                continue
            cells = by[(state, y)]
            missing = [c for c in REQUIRED if (c, "actual") not in cells]
            add("N1_headline_codes", "PASS" if not missing else "PARTIAL", y,
                f"{state}: headline codes present",
                ",".join(REQUIRED), f"missing {','.join(missing)}" if missing else "all",
                str(len(missing)))

    # N2 accounting identity per state-year, from the panel itself
    for (state, y), cells in sorted(by.items()):
        def g(c):
            r = cells.get((c, "actual"))
            return float(r["amount_rm_conformed"]) / M if r else None
        rev, exp, sd = g("revenue_total"), g("expenditure_total"), g("surplus_deficit")
        if None not in (rev, exp, sd):
            d = (rev - exp) - sd
            r = cells[("surplus_deficit", "actual")]
            add("N2_identity_surplus", "PASS" if abs(d) <= TOL else "FAIL", y,
                f"{state}: revenue - expenditure = surplus (conformed panel)",
                f"{sd:.2f}", f"{rev-exp:.2f}", f"{d:.2f}",
                r["source_file"], r["pdf_page"], r["printed_page"], r["jadual"])
        opex, dev = g("opex_before_transfer"), g("devex_total")
        water = g("expenditure_water_supply") or 0.0  # Pahang prints a third head, Perbelanjaan Bekalan Air
        if None not in (opex, dev, exp):
            d = (opex + dev + water) - exp
            r = cells[("expenditure_total", "actual")]
            add("N2_identity_expenditure", "PASS" if abs(d) <= TOL else "FAIL", y,
                f"{state}: opex + devex" + (" + water supply" if water else "") + " = expenditure_total (conformed panel)",
                f"{exp:.2f}", f"{opex+dev+water:.2f}", f"{d:.2f}",
                r["source_file"], r["pdf_page"], r["printed_page"], r["jadual"])

    # N3 code-space: no conformed code carries a state-specific fund
    codes_by_state = defaultdict(set)
    for r in rows:
        codes_by_state[r["state"]].add(r["line_code"])
    labels = defaultdict(set)
    for r in rows:
        labels[(r["line_code"], r["state"])].add(
            " ".join(r["line_label_bm"].lower().split()))
    collisions = 0
    for state, funds in SC.STATE_SPECIFIC_TRUST_FUNDS.items():
        for f in funds:
            # the fund's DISTINCTIVE tail, not the generic `Kumpulan Wang
            # Amanah ...` stem every state shares
            tail = re.sub(r"^(the |kumpulan wang (amanah )?)", "", f.lower()).strip()
            for (code, st), labs in labels.items():
                if st != state or "." in code:
                    continue
                if any(tail and tail in l for l in labs):
                    collisions += 1
                    add("N3_no_code_collision", "FAIL", "",
                        f"{state}: state-specific fund '{f}' occupies conformed "
                        f"code {code}", "unconformed", code, "")
    add("N3_no_code_collision", "PASS" if not collisions else "FAIL", "",
        f"state-specific trust funds stay unconformed ({CONFORMED_UNIVERSE_NOTE})",
        "0 collisions", f"{collisions} collisions", str(collisions))

    # N6 a code's canonical source spec must not change mid-series
    spec_of = defaultdict(dict)
    for r in rows:
        if r["measure"] == "actual":
            spec_of[(r["state"], r["line_code"])][r["fiscal_year"]] = r["spec_id"]
    # Two statements of one volume routinely RESTATE the same audited figure -
    # `KEDUDUKAN KUMPULAN WANG DISATUKAN` and `AKAUN AMANAH DISATUKAN` both
    # print the trust-fund balances, `PRESTASI KEWANGAN`, `KUTIPAN HASIL
    # MENGIKUT KATEGORI` and `KUTIPAN HASIL BERBANDING ANGGARAN` all print the
    # three revenue categories - and the volumes do not print the same set of
    # tables every year.  A code that falls back from one to the other is
    # therefore NOT automatically spliced; it is spliced only when the two
    # statements do not agree.  So the check is decided from the data: in every
    # fiscal year where BOTH statements are printed, do they carry the same
    # figure?  Agreement in every overlapping year = a benign fallback (INFO);
    # any disagreement, or no overlapping year at all to test with, = a genuine
    # splice (FAIL).
    allrows = defaultdict(list)
    for state in SC.STATES:
        for nm in ("fact_state_finance", "fact_state_revenue"):
            for r in load(state, f"{nm}_{SC.slug(state)}.csv"):
                if (r["measure"] == "actual" and r["column_role"] == "own_year"
                        and r["line_code_conformed"] == "yes"):
                    allrows[(state, r["line_code"])].append(r)
    n_benign = n_spliced = 0
    for (st, code), byy in sorted(spec_of.items()):
        specs = set(byy.values())
        if len(specs) < 2:
            continue
        seq = [f"{y}:{byy[y]}" for y in sorted(byy)]
        # every printed value of this code, by (spec, year)
        vals = defaultdict(dict)
        for r in allrows.get((st, code), []):
            vals[r["spec_id"]].setdefault(r["fiscal_year"], juta(r))
        overlaps, clashes = 0, []
        for y in sorted(byy):
            present = {s: v[y] for s, v in vals.items() if y in v and s in specs}
            if len(present) < 2:
                continue
            overlaps += 1
            lo, hi = min(present.values()), max(present.values())
            if abs(hi - lo) > TOL:
                clashes.append("%s:%s" % (y, "/".join(
                    f"{s}={present[s]:.2f}" for s in sorted(present))))
        if overlaps and not clashes:
            n_benign += 1
            add("N6_spec_stable", "INFO", "",
                f"{st}: {code} falls back between statements that RESTATE each "
                f"other - benign, not a splice: the preferred statement is "
                f"simply absent in some years",
                "one spec, or agreeing restatements",
                ",".join(sorted(specs)), str(len(specs)),
                proof=f"{overlaps} fiscal year(s) print both statements and "
                      f"every one agrees to 2 dp | " + " ".join(seq))
            continue
        n_spliced += 1
        add("N6_spec_stable", "FAIL", "",
            f"{st}: {code} is taken from more than one statement across the "
            f"series - the series is SPLICED and its year-on-year changes are "
            f"not comparable",
            "one spec", ",".join(sorted(specs)), str(len(specs)),
            proof=(("disagreeing years: " + "; ".join(clashes) + " | ")
                   if clashes else
                   "no fiscal year prints both statements, so the two cannot "
                   "be shown to restate each other | ") + " ".join(seq))
    add("N6_spec_stable", "PASS" if not n_spliced else "FAIL", "",
        "every conformed code is sourced from ONE statement across each "
        "state's whole series, or from statements proved to restate each other",
        "0 spliced", f"{n_spliced} spliced, {n_benign} benign fallback",
        str(n_spliced))

    # N7 a top-contributors subtotal can never exceed that state-year's revenue
    rev_of = {}
    for r in rows:
        if r["line_code"] == "revenue_total" and r["measure"] == "actual":
            rev_of[(r["state"], r["fiscal_year"])] = float(r["amount_rm_conformed"])
    for r in rows:
        if r["line_code"] != "revenue_top_contributors_total" or r["measure"] != "actual":
            continue
        tot = rev_of.get((r["state"], r["fiscal_year"]))
        if tot is None:
            continue
        v = abs(float(r["amount_rm_conformed"]))
        add("N7_top_contributors_le_revenue",
            "PASS" if v <= tot + TOL * M else "FAIL", r["fiscal_year"],
            f"{r['state']}: the top-5 contributor subtotal cannot exceed total "
            f"revenue", f"<= {tot/M:.2f}", f"{v/M:.2f}", f"{(v-tot)/M:.2f}",
            r["source_file"], r["pdf_page"], r["printed_page"], r["jadual"])

    # N4 per-state row counts
    for state in SC.STATES:
        key = SC.slug(state)
        counts = {}
        for name in ("fact_state_finance", "fact_state_revenue",
                     "fact_state_agency_sijil"):
            p = os.path.join(DATA, key, f"{name}_{key}.csv")
            counts[name] = sum(1 for _ in open(p, encoding="utf-8")) - 1 if os.path.exists(p) else 0
        yrs = sorted({y for (s, y) in by if s == state})
        add("N4_row_counts", "INFO", "", f"{state}: rows and coverage",
            f"FY{yrs[0]}-FY{yrs[-1]} ({len(yrs)} years)" if yrs else "no years",
            f"finance={counts['fact_state_finance']} "
            f"revenue={counts['fact_state_revenue']} "
            f"agency={counts['fact_state_agency_sijil']} "
            f"panel_rows={sum(1 for r in rows if r['state']==state)}", "")

    # N5 cross-state comparability of the conformed codes
    core = defaultdict(set)
    for r in rows:
        core[r["line_code"]].add(r["state"])
    for c in REQUIRED:
        add("N5_code_coverage", "PASS" if len(core[c]) == 13 else "PARTIAL", "",
            f"{c}: states carrying the code", "13", str(len(core[c])),
            str(13 - len(core[c])),
            proof=",".join(sorted(set(SC.STATES) - core[c])))

    out = os.path.join(DATA, "_national", "_validation_national.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CHECKS[0].keys()))
        w.writeheader()
        w.writerows(CHECKS)
    tal = defaultdict(int)
    for c in CHECKS:
        tal[(c["check"], c["status"])] += 1
    print(f"\nnational: {len(CHECKS)} checks -> {os.path.relpath(out, ROOT)}")
    for (chk, st), n in sorted(tal.items()):
        print(f"  {chk:24s} {st:10s} {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--national", action="store_true")
    args = ap.parse_args()
    states = SC.STATES if (args.all or not args.state) else [args.state]
    for s in states:
        validate_state(s)
    if args.national or args.all:
        national()


if __name__ == "__main__":
    main()
