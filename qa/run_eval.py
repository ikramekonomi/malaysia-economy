#!/usr/bin/env python3
"""Run qa/eval_questions.csv against the agent tools; write qa/_validation_eval.csv (in CI).

A FAIL means a tool answered differently from the source, or a trap was not caught. The runner
does no arithmetic of its own on tool output beyond comparing a returned value with the frozen
expected value.
"""
import csv
import json
import os
import sys
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from apps.tools.warehouse_tools import UNTRUSTED, Tools  # noqa: E402


def one(t, s):
    r = t.get_series(s["indicator"], s["geo"], s.get("start"), s.get("end"), s.get("breakdown", "_total"))
    if not r.get("held") or len(r["rows"]) != 1:
        raise LookupError(f"expected one row for {s}, got {r.get('answer') or len(r.get('rows', []))}")
    return r["rows"][0]


def run(t, q):
    a = json.loads(q["args"])
    tool, check, exp = q["tool"], q["check"], q["expected"]
    if tool == "get_series":
        res = t.get_series(a["indicator"], a["geo"], a.get("start"), a.get("end"), a.get("breakdown", "_total"))
    elif tool == "derive_chain":
        res = t.derive(a["operation"], one(t, a["a"])["obs_id"], one(t, a["b"])["obs_id"])
    elif tool == "explain_chain":
        res = t.explain(one(t, a)["obs_id"])
    elif tool == "compare_geos":
        res = t.compare_geos(a["indicator"], a["period"], a.get("geo_level", "state"),
                             a.get("breakdown", "_total"))
    else:
        res = getattr(t, tool)(**a)

    first = (res.get("rows") or [res])[0] if isinstance(res, dict) else {}
    if check == "value":
        got = Decimal(first["value"])
        return abs(got - Decimal(exp)) <= Decimal(q["tolerance"] or "0"), str(got)
    if check == "has_citation":
        c = first["citation"]
        return bool(c["file_sha256"] and c["l1_row"] and c["pdf_page"] and res["release_id"]), json.dumps(c)[:120]
    if check == "caveat":
        ids = [c["id"] for c in first.get("caveats", res.get("caveats", []))]
        return exp in ids, ",".join(ids)
    if check == "refused":
        return res.get("ok") is False and exp in res.get("refused", ""), res.get("refused", "computed: " + str(res.get("value")))
    if check == "not_ranked":
        return res.get("held") is False or res.get("refused_ranking") is True, res.get("answer", "ranked")
    if check == "share_bracket":
        sb = res.get("share_below", {})
        got = f"{sb.get('low_percent')};{sb.get('high_percent')}"
        return got == exp, got
    if check.startswith("decile:"):
        n = int(check.split(":")[1])
        got = next((d["cut_off"] for d in res.get("deciles", []) if d["percentile"] == n), None)
        return got is not None and Decimal(got) == Decimal(exp), str(got)
    if check == "refused_ranking":
        return res.get("refused_ranking") is True, res.get("answer", "ranked")
    if check == "not_held":
        return res.get("held") is False, res.get("answer", "held")
    if check == "not_held_registry":
        ids = [r["series_id"] for r in res.get("registry", [])]
        return res.get("held") is False and exp in ids, ",".join(ids)
    if check == "nonempty":
        return bool(res.get("documents")), str(len(res.get("documents", [])))
    if check == "untrusted_text":
        st = res.get("source_text", {})
        return st.get("note") == UNTRUSTED and "line_label_bm" in st, json.dumps(st)[:120]
    if check.startswith("field:"):
        f = check.split(":", 1)[1]
        src = first if f in first else first.get("uncertainty", {}) if f in first.get("uncertainty", {}) \
            else first.get("citation", {})
        return str(src.get(f)) == exp, str(src.get(f))
    if check.startswith("field_contains:"):
        f = check.split(":", 1)[1]
        return exp in str(first.get(f, "")), str(first.get(f, ""))[:100]
    if check.startswith("field_nonempty:"):
        f = check.split(":", 1)[1]
        return bool(first.get(f)), str(first.get(f, ""))[:60]
    if check == "row_count":
        return str(len(res.get("rows", []))) == exp, str(len(res.get("rows", [])))
    bands = res.get("bands", [])
    where = {p["geo_code"]: b["band"] for b in bands for p in b["places"]}
    if check == "alone_in_band":
        b = where.get(exp)
        return b is not None and sum(1 for v in where.values() if v == b) == 1, str(b)
    if check == "same_band":
        x, y = exp.split(";")
        return where.get(x) is not None and where.get(x) == where.get(y), f"{where.get(x)} {where.get(y)}"
    if check == "has_national":
        return bool(res.get("national")), str(bool(res.get("national")))
    if check == "place_count":
        return str(len(where)) == exp, str(len(where))
    if check == "method":
        return res.get("method", {}).get("derivation_id") == exp, res.get("method", {}).get("derivation_id", "")
    if check == "first_indicator":
        ids = [i["indicator_code"] for i in res.get("indicators", [])]
        return bool(ids) and ids[0] == exp, ",".join(ids[:3])
    raise ValueError(f"unknown check {check}")


def main():
    t = Tools()
    with open(os.path.join(REPO, "qa", "eval_questions.csv"), newline="") as f:
        qs = list(csv.DictReader(f))
    out = []
    for q in qs:
        try:
            ok, got = run(t, q)
        except Exception as e:  # noqa: BLE001 - an exception is a failed answer, reported
            ok, got = False, f"{type(e).__name__}: {e}"
        out.append([q["qid"], q["kind"], q["tool"], q["check"], q["expected"], got, "PASS" if ok else "FAIL"])
    with open(os.path.join(REPO, "qa", "_validation_eval.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qid", "kind", "tool", "check", "expected", "got", "status"])
        w.writerows(out)
    n = sum(1 for r in out if r[-1] == "PASS")
    print(f"eval: {n} of {len(out)} PASS (release {t.w.release_id})")
    for r in out:
        if r[-1] == "FAIL":
            print("  FAIL", r)


if __name__ == "__main__":
    main()
