"""The core warehouse in memory: observations, dimensions, caveats, derivations, QA flags.

Shared by the gap-view builders (core/pipeline/build_gap_*.py) and the agent tools
(apps/tools/warehouse_tools.py), so a number the view publishes and a number a tool returns are
computed by the same code. Read-only over core/*.csv and meta/*.csv.
"""
import csv
import hashlib
import os
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CORE = os.path.join(REPO, "core")
META = os.path.join(REPO, "meta")
PK = ("indicator_code", "geo_code", "period_code", "breakdown_key", "entity_id", "basis", "edition_id", "vintage")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fmt(d, places=None):
    if d is None:
        return None
    if places is not None:
        d = d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
    s = format(d.normalize(), "f")
    return s if "." not in s else s.rstrip("0").rstrip(".")


class Refused(Exception):
    """A derivation whose inputs do not match. The message says why; nothing is computed."""


class Warehouse:
    def __init__(self):
        fact = os.path.join(CORE, "fact_observation.csv")
        self.obs = _rows(fact)
        h = hashlib.sha256()
        with open(fact, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        self.release_id = "core-" + h.hexdigest()[:12]
        for r in self.obs:
            r["obs_id"] = "o" + hashlib.sha1("|".join(r[k] for k in PK).encode()).hexdigest()[:12]
        self.by_id = {r["obs_id"]: r for r in self.obs}
        self.ind = {r["indicator_code"]: r for r in _rows(os.path.join(CORE, "dim_indicator.csv"))}
        self.all_ind = {r["indicator_code"]: r for r in _rows(os.path.join(META, "indicator.csv"))}
        self.geo = {r["geo_code"]: r for r in _rows(os.path.join(CORE, "dim_geo.csv"))}
        self.caveats = {r["caveat_id"]: r for r in _rows(os.path.join(META, "caveat.csv"))}
        self.derivations = {r["derivation_id"]: r for r in _rows(os.path.join(META, "derivation.csv"))}
        self.registry = _rows(os.path.join(REPO, "docs", "registry", "series_seed.csv"))
        self.index = defaultdict(list)
        for r in self.obs:
            self.index[(r["indicator_code"], r["geo_code"], r["period_code"], r["breakdown_key"])].append(r)
        self.flags = self._state_flags()

    # ------------------------------------------------------------ QA flags ("under check")
    def _state_flags(self):
        """(geo_code, year) -> [check names] for every baselined FAIL in the state accounts."""
        from_name = {g["name_bm"]: c for c, g in self.geo.items() if g["geo_level"] == "state"}
        by_folder = {re.sub(r"[^a-z]", "", g["name_bm"].lower()): c for c, g in self.geo.items()
                     if g["geo_level"] == "state"}
        out = defaultdict(list)
        p = os.path.join(REPO, "qa", "known_fails.csv")
        if not os.path.exists(p):
            return out
        for r in _rows(p):
            if not r["file"].startswith("sources/states/"):
                continue
            cells = r["row"].split("|")
            check, year = cells[0], cells[2] if len(cells) > 2 else ""
            if not re.fullmatch(r"\d{4}", year or ""):
                continue
            folder = r["file"].split("/")[3]
            geo = by_folder.get(folder.replace("_", ""))
            if folder == "_national":
                m = re.match(r"([A-Za-z .]+):", cells[3] if len(cells) > 3 else "")
                geo = from_name.get(m.group(1).strip()) if m else None
            if geo:
                out[(geo, year)].append(check)
        return out

    def headline_flag(self, geo, year):
        """Checks that touch the headline totals the gap view uses (identities), not detail tables."""
        return sorted({c for c in self.flags.get((geo, year), []) if c.startswith(("N2_", "V1_cra"))})

    # ------------------------------------------------------------ lookups
    def get(self, indicator, geo, period, breakdown="_total", basis=None):
        rs = self.index.get((indicator, geo, period, breakdown), [])
        if basis:
            rs = [r for r in rs if r["basis"] == basis]
        return rs[0] if len(rs) == 1 else (sorted(rs, key=lambda r: r["vintage"])[-1] if rs else None)

    def caveats_for(self, r):
        out = []
        ind = r["indicator_code"]
        if r["estimate_method"] == "direct_survey" and r["reliability"] == "unknown":
            out.append("CV1")
        if ind in ("pop.total", "households.total"):
            out.append("CV2")
        if ind == "state_gov.revenue.nonrevenue_receipts":
            out.append("CV3")
        if r["basis"] == "audited" and r["geo_code"].startswith("MY-"):
            out.append("CV5")
            if self.flags.get((r["geo_code"], r["period_code"])):
                out.append("CV6")
        if ind == "gdp.real":
            out.append("CV7")
        if ind == "cpi.index":
            out.append("CV8")
        return out

    def cite(self, r):
        """Everything a returned number must carry (docs/DATA_MODEL.md §11 contract)."""
        cv = self.caveats_for(r)
        out = {"obs_id": r["obs_id"], "indicator_code": r["indicator_code"], "geo_code": r["geo_code"],
               "geo_name": self.geo.get(r["geo_code"], {}).get("name_bm", ""), "period_code": r["period_code"],
               "breakdown_key": r["breakdown_key"], "basis": r["basis"], "value": r["value"],
               "unit": self.all_ind[r["indicator_code"]]["unit"], "value_printed": r["value_printed"],
               "unit_printed": r["unit_printed"], "status": r["status"],
               "uncertainty": {"se": r["se"] or None, "ci_low": r["ci_low"] or None, "ci_high": r["ci_high"] or None,
                               "reliability": r["reliability"]},
               "citation": {"edition_id": r["edition_id"], "vintage": r["vintage"], "file_sha256": r["file_id"],
                            "pdf_page": r["pdf_page"] or None, "printed_page": r["printed_page"] or None,
                            "table": r["table_ref"], "l1_row": r["l1_ref"]},
               "caveats": [{"id": c, "text": self.caveats[c]["text_en"]} for c in cv],
               "release_id": self.release_id}
        if "CV6" in cv:
            out["under_check"] = self.flags[(r["geo_code"], r["period_code"])]
        return out

    # ------------------------------------------------------------ derive (the only place arithmetic happens)
    def derive(self, operation, a_id, b_id):
        a, b = self.by_id.get(a_id), self.by_id.get(b_id)
        if not a or not b:
            raise Refused(f"unknown observation id: {a_id if not a else b_id}")
        ia, ib = self.all_ind[a["indicator_code"]], self.all_ind[b["indicator_code"]]
        va, vb = Decimal(a["value"]), Decimal(b["value"])
        if operation == "per_capita":
            if b["indicator_code"] != "pop.total" or b["breakdown_key"] != "_total":
                raise Refused("per_capita needs pop.total (no split) as the denominator")
            if ia["additive_geo"] != "true":
                raise Refused(f"{a['indicator_code']} is a {ia['statistic']} and cannot be divided by population")
            if a["geo_code"] != b["geo_code"]:
                raise Refused(f"different places: {a['geo_code']} vs {b['geo_code']}")
            if a["period_code"] != b["period_code"]:
                raise Refused(f"different periods: {a['period_code']} vs {b['period_code']}; use the population "
                              "of the same year")
            dv, value, unit = "DV1", va / vb, ia["unit"] + " per person"
        elif operation == "ratio":
            if ia["unit"] != ib["unit"]:
                raise Refused(f"different units: {ia['unit']} vs {ib['unit']}")
            if a["period_code"] != b["period_code"]:
                raise Refused(f"different periods: {a['period_code']} vs {b['period_code']}")
            if ia["price_basis"] != ib["price_basis"]:
                raise Refused(f"different price bases: {ia['price_basis'] or 'none'} vs {ib['price_basis'] or 'none'}")
            if a["geo_code"] != b["geo_code"] and b["geo_code"] != "MY":
                raise Refused("a ratio across two different places needs the second to be the national value")
            dv, value, unit = "DV2", va / vb, "ratio"
        elif operation == "growth":
            same = all(a[k] == b[k] for k in ("indicator_code", "geo_code", "breakdown_key"))
            if not same:
                raise Refused("growth compares one series with itself: same indicator, place and breakdown")
            if len(a["period_code"]) != len(b["period_code"]):
                raise Refused("different frequencies")
            dv, value, unit = "DV3", va / vb - 1, "ratio"
        elif operation in ("gap_pp", "difference"):
            if operation == "gap_pp" and not (ia["unit"] == ib["unit"] == "percent"):
                raise Refused(f"gap_pp needs two percentages; got {ia['unit']} and {ib['unit']}")
            if a["indicator_code"] != b["indicator_code"]:
                raise Refused(f"different indicators: {a['indicator_code']} vs {b['indicator_code']}")
            if a["period_code"] != b["period_code"]:
                raise Refused(f"different periods: {a['period_code']} vs {b['period_code']}")
            dv, value = ("DV4", va - vb) if operation == "gap_pp" else ("DV5", va - vb)
            unit = "percentage points" if operation == "gap_pp" else ia["unit"]
        else:
            raise Refused(f"unknown operation {operation}")
        cv = sorted(set(self.caveats_for(a)) | set(self.caveats_for(b)))
        if operation == "per_capita" and a["indicator_code"].startswith("state_gov."):
            cv.append("CV9")
        if operation == "growth" and ia["price_basis"] == "current":
            unit += " (nominal)"
        return {"operation": operation, "value": fmt(value, 6), "unit": unit, "basis": "derived",
                "derivation_id": dv, "formula": self.derivations[dv]["formula"], "derived_from": [a_id, b_id],
                "inputs": [self.cite(a), self.cite(b)],
                "caveats": [{"id": c, "text": self.caveats[c]["text_en"]} for c in cv],
                "release_id": self.release_id}
