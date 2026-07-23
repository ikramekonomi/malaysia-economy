#!/usr/bin/env python3
"""Iterative template training for the Lampiran 2 reader.

Round-trips: read cells with current templates -> harvest high-confidence
labels (row identities; unique near-matches against the 2014/2016 warehouse
value pools -- POOLS ARE USED FOR TRAINING LABELS ONLY, never to force an
output value) -> retrain -> repeat.  Prints identity pass-rate per round.
"""
import csv
import json
import re
import sys
import itertools
from collections import defaultdict

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import lamp2_tm

TOL = 0.011


def digstr(v):
    return re.sub(r"\D", "", f"{v:,.2f}")


def lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > cap:
            return cap + 1
    return prev[-1]


def load_rows():
    rows = json.load(open("/tmp/l2_rows.json"))
    return [r for r in rows if r.get("cells")]


def pools_2014():
    pk, pp = defaultdict(set), defaultdict(set)
    for wf, yr in (("/home/claude/pkkp/warehouse2014/fact_devex_project.csv", 2014),
                   ("/home/claude/pkkp/warehouse2016/fact_devex_project.csv", 2016)):
        try:
            rd = csv.DictReader(open(wf))
        except OSError:
            continue
        for r in rd:
            mk = r["maksud_code"]
            for col, pool in (("kos_keseluruhan_rm", pk),):
                v = float(r[col] or 0)
                if v > 0:
                    pool[mk].add(round(v, 2))
            if yr == 2014:
                v = float(r["terkumpul_rmke10_rm"] or 0)
                if v > 0:
                    pp[mk].add(round(v, 2))
            else:
                v = float(r["terkumpul_rmke10_prior_rm"] or 0)
                if v > 0:
                    pp[mk].add(round(v, 2))
    return pk, pp


def read_row(r, cache):
    """Template-read all 9 cells of a row. Joint decode for ag/sb pairs when
    pinjaman is nil. Returns cn -> reading dict or None (zero cells -> 0)."""
    out = {}
    c = r["cells"]
    zero = {k for k in c if c[k]["route"] in ("dash", "blank")}
    rp = r["page"] + 1

    def rd(key, instances):
        ck = json.dumps(instances)
        if ck in cache:
            return cache[ck]
        res = lamp2_tm.read_amount_multi(instances)
        cache[ck] = res
        return res

    for pair, l, j, p in (("ag", "ag_l", "ag_j", "ag_p"), ("sb", "sb_l", "sb_j", "sb_p")):
        if p in zero and l not in zero and j not in zero:
            res = rd(pair, [(rp, c[l]["box"]), (rp, c[j]["box"])])
            out[l] = res
            out[j] = res
        else:
            for k in (l, j):
                out[k] = None if k in zero else rd(k, [(rp, c[k]["box"])])
        out[p] = None if p in zero else rd(p, [(rp, c[p]["box"])])
    for k, pg in (("kos", r["page"]), ("prior", r["page"]), ("kum", rp)):
        out[k] = None if k in zero else rd(k, [(pg, c[k]["box"])])
    for k in list(out):
        if k in zero:
            out[k] = dict(value=0.0, alts=[], text="0.00", mean=2.0, weak=[], zero=True)
        elif out[k] is None:
            out[k] = dict(value=0.0, alts=[], text=None, mean=0.0, weak=[])
    return out


def identity_ok(v):
    return (abs(v["ag_l"] + v["ag_p"] - v["ag_j"]) < TOL
            and abs(v["sb_l"] + v["sb_p"] - v["sb_j"]) < TOL
            and abs(v["prior"] + v["sb_j"] - v["kum"]) < TOL)


def solve_row(reads, extra_cands=None):
    """Try to satisfy identities using alts (and extra candidates)."""
    keys = list(reads)
    cands = {}
    for k in keys:
        cl = [reads[k]["value"]] + reads[k]["alts"][:3]
        for e in (extra_cands or {}).get(k, []):
            if not any(abs(e - x) < TOL for x in cl):
                cl.append(e)
        cands[k] = cl
    base = {k: cands[k][0] for k in keys}
    if identity_ok(base):
        return base, 0
    # derived candidates
    der = {
        "ag_j": [base["ag_l"] + base["ag_p"]],
        "ag_l": [base["ag_j"] - base["ag_p"]],
        "sb_j": [base["sb_l"] + base["sb_p"], base["kum"] - base["prior"]],
        "sb_l": [base["sb_j"] - base["sb_p"]],
        "kum": [base["prior"] + base["sb_j"]],
        "prior": [base["kum"] - base["sb_j"]],
    }
    for k, vs in der.items():
        for v in vs:
            if v >= 0 and not any(abs(v - x) < TOL for x in cands[k]):
                cands[k].append(v)
    varying = [k for k in keys if len(cands[k]) > 1]
    for nvar in (1, 2, 3):
        for ck in itertools.combinations(varying, nvar):
            for choice in itertools.product(*[cands[k][1:] for k in ck]):
                v = dict(base)
                for k, val in zip(ck, choice):
                    v[k] = val
                if identity_ok(v):
                    return v, nvar
    return None, None


def harvest_and_eval(rows, cache, poolk, poolp):
    samples = []
    stats = dict(ok0=0, solved=0, fail=0, pool_kos=0, pool_prior=0)
    for r in rows:
        reads = read_row(r, cache)
        r["_reads"] = reads
        extra = {}
        mk = r.get("maksud")
        # pool label candidates (TRAINING/CANDIDATES only)
        for k, pool in (("kos", poolk), ("prior", poolp)):
            rd = reads[k]
            if rd.get("zero") or rd["text"] is None or not mk:
                continue
            ds = re.sub(r"\D", "", rd["text"])
            hits = [pv for pv in pool.get(mk, ()) if lev(digstr(pv), ds, 2) <= 2]
            if len(hits) == 1:
                extra[k] = [hits[0]]
        v, nvar = solve_row(reads, extra)
        r["_solved"] = v
        r["_nvar"] = nvar
        if v is None:
            stats["fail"] += 1
            continue
        stats["ok0" if nvar == 0 else "solved"] += 1
        # harvest training labels from identity-passing rows
        c = r["cells"]
        rp = r["page"] + 1
        for k in v:
            if reads[k].get("zero") or v[k] <= 0:
                continue
            pg = r["page"] if k in ("kos", "prior") else rp
            samples.append((pg, c[k]["box"], True, f"{v[k]:,.2f}"))
    return samples, stats


def main():
    rows = load_rows()
    poolk, poolp = pools_2014()
    for rnd in range(3):
        cache = {}
        samples, stats = harvest_and_eval(rows, cache, poolk, poolp)
        print(f"round {rnd}: {stats} | harvest {len(samples)} labelled cells")
        counts, used, skipped = lamp2_tm.train(samples)
        print(f"  retrained: used {used} skipped {skipped} counts { {k: counts[k] for k in sorted(counts)} }")
    json.dump({k: None for k in ()}, open("/tmp/dummy.json", "w"))


if __name__ == "__main__":
    main()
