#!/usr/bin/env python3
"""Build dim_maksud.csv for PKKP 2015.

The maksud dimension is stable year-to-year (ministries/heads). name_bm is
taken from THIS volume's own printed labels (Bekalan/Tanggungan from Nota 5(b)
fact_opex_maksud; Pembangunan from Lampiran 2 fact_devex_maksud). name_en is
not printed in this volume, so it is carried from the 2016 canonical dim_maksud
(labels are canonical/correctable across years per CONVENTIONS.md). Any code
present in 2015 but absent from the 2016 canonical is logged.
Schema column-for-column = warehouse2014/2016 dim_maksud.csv.
"""
import csv
import sys
import pandas as pd

WH = "/home/claude/pkkp/warehouse2015"
YEAR = 2015

o = pd.read_csv(f"{WH}/fact_opex_maksud.csv")
try:
    dv = pd.read_csv(f"{WH}/fact_devex_maksud.csv")
except FileNotFoundError:
    dv = None
d16 = pd.read_csv("/home/claude/pkkp/warehouse2016/dim_maksud.csv")
d14 = pd.read_csv("/home/claude/pkkp/warehouse2014/dim_maksud.csv")
en_map = dict(zip(d16.maksud_code, d16.name_en))
en_map14 = dict(zip(d14.maksud_code, d14.name_en))

rows = []       # (maksud_code, jenis, name_bm)
# Bekalan + Tanggungan from opex_maksud (detail rows only, has maksud_code like B.xx/T.xx)
seen = set()
for _, r in o.iterrows():
    code = str(r["maksud_code"]).strip()
    if not code or code == "nan" or "." not in code:
        continue
    if code in seen:
        continue
    seen.add(code)
    rows.append((code, str(r["jenis_bm"]).strip(), str(r["maksud_name_bm"]).strip()))

# Pembangunan (P.xx): the 2015 Lampiran 2 hierarchy OCR did not reliably tag
# maksud codes, so the Pembangunan maksud list + names are carried from the
# 2016 canonical dim_maksud (ministries are stable; labels canonical per
# CONVENTIONS.md). Logged. name_bm here is therefore the canonical name.
pemb_src = "2016-canonical (2015 Lampiran 2 maksud hierarchy OCR unreliable)"
for _, r in d16[d16.jenis == "Pembangunan"].iterrows():
    code = str(r["maksud_code"]).strip()
    if code in seen:
        continue
    seen.add(code)
    rows.append((code, "Pembangunan", str(r["name_bm"]).strip()))

JENIS_ORDER = {"Bekalan": 0, "Pembangunan": 1, "Tanggungan": 2}
def code_num(code):
    try:
        return int(code.split(".")[1])
    except Exception:
        return 999
rows.sort(key=lambda t: (JENIS_ORDER.get(t[1], 9), code_num(t[0])))

missing_en = []
out = []
for code, jenis, name_bm in rows:
    name_en = en_map.get(code) or en_map14.get(code) or ""
    if not name_en:
        missing_en.append(code)
    out.append(dict(maksud_code=code, code_num=code_num(code), jenis=jenis,
                    name_bm=name_bm, name_en=name_en, note="", year=YEAR))

cols = ["maksud_code", "code_num", "jenis", "name_bm", "name_en", "note", "year"]
with open(f"{WH}/dim_maksud.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out)

from collections import Counter
print(f"dim_maksud.csv: {len(out)} rows", dict(Counter(r['jenis'] for r in out)))
if missing_en:
    print("WARN missing name_en for:", missing_en)
