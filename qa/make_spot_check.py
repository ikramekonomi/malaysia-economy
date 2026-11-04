#!/usr/bin/env python3
"""Draw the human spot-check sample for a published view (docs/DATA_MODEL.md §7.4).

  python3 qa/make_spot_check.py   -> qa/spot_check/gap_need_vs_money_<release>.csv

A fixed-seed random sample of the observations the view is built from: 30 from the state accounts
(checked against the PDF page) and 10 from DOSM (checked against the OpenDOSM catalogue page).
A person fills in checked_by, checked_on, result (match / differs / cannot_find) and note. The view
moves to verification tier human_spot_checked only when every row is filled and none differs.
"""
import csv
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "core", "pipeline"))
from warehouse import Warehouse  # noqa: E402

w = Warehouse()
ids = []
with open(os.path.join(REPO, "core", "gap_need_vs_money.csv"), newline="") as f:
    for r in csv.DictReader(f):
        ids += [i for i in r["source_obs_ids"].split(";") if i]
ids = sorted(set(ids))
acct = [i for i in ids if w.by_id[i]["basis"] == "audited"]
dosm = [i for i in ids if w.by_id[i]["basis"] == "statistic"]
rng = random.Random(20261104)
sample = sorted(rng.sample(acct, min(30, len(acct)))) + sorted(rng.sample(dosm, min(10, len(dosm))))
out = os.path.join(REPO, "qa", "spot_check", f"gap_need_vs_money_{w.release_id}.csv")
with open(out, "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["obs_id", "state", "year", "indicator", "value_printed", "unit_printed", "document", "pdf_page",
                 "printed_page", "table", "where_to_look", "checked_by", "checked_on", "result", "note"])
    for i in sample:
        r = w.by_id[i]
        doc = r["edition_id"].split(":", 1)[1]
        look = (f"archived PDF sha256 {r['file_id'][:12]}..., page {r['pdf_page']}" if r["basis"] == "audited"
                else f"https://open.dosm.gov.my/data-catalogue/{r['table_ref']} ({r['period_code']})")
        wr.writerow([i, w.geo[r["geo_code"]]["name_bm"], r["period_code"], w.all_ind[r["indicator_code"]]["name_en"],
                     r["value_printed"], r["unit_printed"], doc, r["pdf_page"], r["printed_page"], r["table_ref"],
                     look, "", "", "", ""])
print(f"{os.path.relpath(out, REPO)}: {len(sample)} rows ({len(acct)} account and {len(dosm)} DOSM observations to draw from)")
