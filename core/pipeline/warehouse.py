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


def observation_files():
    """The fact_observation table: one CSV per indicator family under core/fact_observation/ (decision D34)."""
    import glob
    return sorted(glob.glob(os.path.join(CORE, "fact_observation", "*.csv")))


def read_observations():
    out = []
    for p in observation_files():
        out.extend(_rows(p))
    return out


class Warehouse:
    def __init__(self):
        self.obs = read_observations()
        h = hashlib.sha256()
        for fact in observation_files():  # the release id covers every shard, in name order
            h.update(os.path.basename(fact).encode())
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
        self.entity = {r["entity_id"]: r for r in _rows(os.path.join(CORE, "dim_entity.csv"))}
        self.entity_codes = _rows(os.path.join(CORE, "bridge_entity_code.csv"))
        self.entity_names = _rows(os.path.join(CORE, "entity_name.csv"))
        self.entity_lineage = _rows(os.path.join(CORE, "entity_lineage.csv"))
        self.spending_heads = {r["code"]: r for r in _rows(os.path.join(META, "spending_head.csv"))}
        fl = os.path.join(CORE, "fact_money_flow.csv")
        self.flows = _rows(fl) if os.path.exists(fl) else []
        self.group_members = defaultdict(set)
        for g in _rows(os.path.join(META, "group_member.csv")):
            self.group_members[g["group_entity_id"]].add(g["member_geo_code"])
        self.bases = {r["code"] for r in _rows(os.path.join(META, "code_list.csv")) if r["code_list"] == "basis"}
        self.breakdowns = {r["breakdown_key"] for r in _rows(os.path.join(CORE, "dim_breakdown.csv"))}
        self.caveats = {r["caveat_id"]: r for r in _rows(os.path.join(META, "caveat.csv"))}
        self.derivations = {r["derivation_id"]: r for r in _rows(os.path.join(META, "derivation.csv"))}
        self.registry = _rows(os.path.join(REPO, "docs", "registry", "series_seed.csv"))
        self.breaks = _rows(os.path.join(META, "series_break.csv"))
        self.index = defaultdict(list)
        for r in self.obs:
            self.index[(r["indicator_code"], r["geo_code"], r["period_code"], r["breakdown_key"])].append(r)
        self.flags = self._state_flags()
        self.l0_status = {}
        ap = os.path.join(META, "l0_archive.csv")
        if os.path.exists(ap):
            for a in _rows(ap):
                if self.l0_status.get(a["file_name"]) != "ARCHIVED":
                    self.l0_status[a["file_name"]] = a["status"]
        self.obs_flags = {}
        fp = os.path.join(os.path.dirname(META), "core", "obs_flag.csv")
        if os.path.exists(fp):
            for f in _rows(fp):
                self.obs_flags.setdefault(f["l1_ref"], []).append(f)

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
        else:
            rs = [r for r in rs if r["basis"] != "target"]  # a plan's target is never the outcome; ask for it by basis
        if len({r["edition_id"].split(":")[0] for r in rs}) > 1:
            return None  # two publishers for one concept: never choose between them silently
        return rs[0] if len(rs) == 1 else (sorted(rs, key=lambda r: r["vintage"])[-1] if rs else None)

    def source_flags(self, r):
        """Anomalies registered at L1 (or by a declared rule) for the L1 row this observation comes from."""
        return [{"flag": f["flag"], "note": f["note"], "register": f["register"]}
                for f in self.obs_flags.get(r["l1_ref"], [])
                if not f["indicator_code"] or f["indicator_code"] == r["indicator_code"]]

    def caveats_for(self, r):
        out = []
        ind = r["indicator_code"]
        flags = {f["flag"] for f in self.source_flags(r)}
        if flags - {"our_extraction_defect", "leaf_total_mismatch"}:
            out.append("CV15")
        if "our_extraction_defect" in flags:
            out.append("CV18")
        if r["estimate_method"] == "direct_survey" and r["reliability"] == "unknown":
            out.append("CV1")
        if r["estimate_method"] == "direct_survey" and r["reliability"] == "low" and ind.startswith("lfs."):
            out.append("CV12")
        if ind.startswith("hh_income.gross.pctile_group."):
            out.append("CV13")
        if ind in ("pop.total", "households.total"):
            out.append("CV2")
        if ind == "state_gov.revenue.nonrevenue_receipts":
            out.append("CV3")
        if ind.startswith("state_gov.revenue.federal_"):
            out.append("CV26")
        if r["basis"] == "audited" and r["geo_code"].startswith("MY-"):
            out.append("CV5")
            if self.flags.get((r["geo_code"], r["period_code"])):
                out.append("CV6")
        if ind == "gdp.real" and r["basis"] != "target":
            out.append("CV7")
        if "leaf_total_mismatch" in flags:
            out.append("CV21")
        if r["edition_id"].startswith("pkkp:") and ind.startswith("federal_gov."):
            src = r["edition_id"].split(":", 1)[1]
            if not src.lower().endswith(".pdf"):  # no volume cited: the year's own volume
                src = next((f for f in self.l0_status if f.startswith(f"{r['period_code']}_") and
                            "penyata_kewangan" in f.lower()), "")
            if src and self.l0_status.get(src, "ARCHIVED") != "ARCHIVED":
                out.append("CV17")
        if ind.startswith("federal_gov.vote."):
            out.append("CV23")
        if r["edition_id"].startswith("anggaran:") and r["period_code"][:4] < r["vintage"][:4]:
            out.append("CV22")
        if r["edition_id"].startswith("anggaran_hasil:") and r["period_code"][:4] < r["vintage"][:4]:
            out.append("CV29")
        if ind == "cpi.index":
            out.append("CV8")
        if ind.startswith("trade."):
            out.append("CV19")
        if ind == "credit.loans.banking_system":
            out.append("CV20")
        return out

    def entity_of_federal_gov(self):
        return next((c["entity_id"] for c in self.entity_codes if c["code_system"] == "federal_gov"), "")

    def cite(self, r):
        """Everything a returned number must carry (docs/DATA_MODEL.md §11 contract)."""
        cv = self.caveats_for(r)
        out = {"obs_id": r["obs_id"], "indicator_code": r["indicator_code"], "geo_code": r["geo_code"],
               "geo_name": self.geo.get(r["geo_code"], {}).get("name_bm", ""), "period_code": r["period_code"],
               "breakdown_key": r["breakdown_key"], "entity_id": r["entity_id"],
               "entity_name": self.entity.get(r["entity_id"], {}).get("name_bm", ""),
               "basis": r["basis"], "value": r["value"],
               "unit": self.all_ind[r["indicator_code"]]["unit"], "value_printed": r["value_printed"],
               "unit_printed": r["unit_printed"], "status": r["status"],
               "uncertainty": {"se": r["se"] or None, "ci_low": r["ci_low"] or None, "ci_high": r["ci_high"] or None,
                               "reliability": r["reliability"]},
               "citation": {"edition_id": r["edition_id"], "vintage": r["vintage"], "file_sha256": r["file_id"],
                            "pdf_page": r["pdf_page"] or None, "printed_page": r["printed_page"] or None,
                            "table": r["table_ref"], "l1_row": r["l1_ref"]},
               "caveats": [{"id": c, "text": self.caveats[c]["text_en"]} for c in cv]
               + ([{"id": "COVERAGE", "text": self.all_ind[r["indicator_code"]]["coverage_note"]}]
                  if self.all_ind[r["indicator_code"]].get("coverage_note") else []),
               "release_id": self.release_id}
        if "CV6" in cv:
            out["under_check"] = self.flags[(r["geo_code"], r["period_code"])]
        sf = self.source_flags(r)
        if sf:
            out["source_flags"] = sf
        return out

    # ------------------------------------------------------------ derive (the only place arithmetic happens)
    def break_between(self, indicator, p0, p1):
        """A registered series break with p0 < first period of the new basis <= p1, if any."""
        lo, hi = sorted((p0, p1))
        for b in self.breaks:
            if indicator.startswith(b["indicator_prefix"]) and lo[:4] < b["first_period_new_basis"] <= hi[:4]:
                return b
        return None

    def break_before(self, indicator, period, since):
        """A break after `since` and up to `period`: the row's years before it are not comparable."""
        return self.break_between(indicator, since, period)

    def derive(self, operation, a_id, b_id):
        if not isinstance(a_id, str) or not isinstance(b_id, str):
            raise Refused("inputs must be observation ids (obs_id) returned by get_series, not values")
        a, b = self.by_id.get(a_id), self.by_id.get(b_id)
        if not a or not b:
            raise Refused(f"unknown observation id: {a_id if not a else b_id}")
        ia, ib = self.all_ind[a["indicator_code"]], self.all_ind[b["indicator_code"]]
        va, vb = Decimal(a["value"]), Decimal(b["value"])
        if (operation in ("ratio", "difference", "gap_pp") and "index" in (ia["unit"], ib["unit"])
                and a["geo_code"] != b["geo_code"]):
            raise Refused("index levels do not compare places (caveat CV8): each place's index is set to 100 in its "
                          "own base year, so a level measures change since then, not how dear one place is against "
                          "another. Compare each place's growth over the same period instead (derive('growth'))")
        if operation == "per_capita":
            if vb == 0:
                raise Refused("population is zero")
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
        elif operation == "per_employed":
            if b["indicator_code"] != "lfs.employed" or b["breakdown_key"] != "_total":
                raise Refused("per_employed needs lfs.employed (no split) as the denominator")
            if a["indicator_code"] != "na.compensation_of_employees":
                raise Refused("per_employed is declared for na.compensation_of_employees only (rule DV6): other "
                              "amounts are not paid to employed persons, so dividing them by employment means nothing")
            if a["geo_code"] != b["geo_code"]:
                raise Refused(f"different places: {a['geo_code']} vs {b['geo_code']}")
            if a["period_code"] != b["period_code"]:
                raise Refused(f"different periods: {a['period_code']} vs {b['period_code']}")
            if vb == 0:
                raise Refused("employment is zero")
            dv, value, unit = "DV6", va / vb, "RM per employed person"
        elif operation == "ratio":
            if ia["unit"] != ib["unit"]:
                raise Refused(f"different units: {ia['unit']} vs {ib['unit']}")
            if a["period_code"] != b["period_code"]:
                raise Refused(f"different periods: {a['period_code']} vs {b['period_code']}")
            if ia["price_basis"] != ib["price_basis"]:
                raise Refused(f"different price bases: {ia['price_basis'] or 'none'} vs {ib['price_basis'] or 'none'}")
            if a["geo_code"] != b["geo_code"] and b["geo_code"] != "MY":
                raise Refused("a ratio across two different places needs the second to be the national value")
            if ia["universe"] != ib["universe"]:
                raise Refused(f"different universes: {ia['universe']} vs {ib['universe']}")
            if ia["statistic"] in ("rate", "share") and a["indicator_code"] != b["indicator_code"]:
                raise Refused("a ratio of two different rates mixes two populations; compare each rate with its "
                              "own national value instead")
            if vb == 0:
                raise Refused("the denominator is zero")
            dv, value, unit = "DV2", va / vb, "ratio"
        elif operation == "growth":
            same = all(a[k] == b[k] for k in ("indicator_code", "geo_code", "breakdown_key"))
            if not same:
                raise Refused("growth compares one series with itself: same indicator, place and breakdown")
            if a["entity_id"] != b["entity_id"]:
                raise Refused(f"growth compares one body with itself; got {b['entity_id']} -> {a['entity_id']} (a vote "
                              "code can name different bodies in different years: see get_entity)")
            if a["edition_id"].startswith("anggaran:") and a["edition_id"] != b["edition_id"]:
                raise Refused("each Anggaran book restates past years to its own votes (caveat CV22): take both years "
                              "from the same book")
            if len(a["period_code"]) != len(b["period_code"]):
                raise Refused("different frequencies")
            pa, pb = a["edition_id"].split(":")[0], b["edition_id"].split(":")[0]
            if pa != pb:
                raise Refused(f"growth compares one publisher's series with itself; got {pb} -> {pa}. Take both years "
                              "from the same publisher (get_series publisher=...)")
            if a["basis"] != b["basis"]:
                raise Refused(f"growth compares one basis with itself; got {b['basis']} -> {a['basis']}. For budget "
                              "against outcome in one year use derive('difference')")
            if a["period_code"] <= b["period_code"]:
                raise Refused(f"growth is from the earlier period (second input) to the later (first input); got "
                              f"{b['period_code']} -> {a['period_code']}")
            brk = self.break_between(a["indicator_code"], b["period_code"], a["period_code"])
            if brk:
                raise Refused(f"series break in {brk['first_period_new_basis']}: {brk['what_changed']}")
            if vb == 0:
                raise Refused("growth from a zero base is undefined")
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
        if operation == "per_employed":
            cv.append("CV14")
        if operation == "growth" and ia["price_basis"] == "current":
            unit += " (nominal)"
        if operation == "growth" and a["indicator_code"].startswith("federal_gov.vote.") \
                and a["entity_id"] != self.entity_of_federal_gov():
            cv.append("CV24")
        return {"operation": operation, "value": fmt(value, 6), "unit": unit, "basis": "derived",
                "derivation_id": dv, "formula": self.derivations[dv]["formula"], "derived_from": [a_id, b_id],
                "inputs": [self.cite(a), self.cite(b)],
                "caveats": [{"id": c, "text": self.caveats[c]["text_en"]} for c in cv],
                "release_id": self.release_id}
