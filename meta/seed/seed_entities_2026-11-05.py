# PROVENANCE ONLY - DO NOT RE-RUN. This one-off script issued the first entity IDs on 2026-11-05.
# Re-running it would rewrite meta/entity_register.csv and meta/entity_code.csv; from that date the
# register is maintained by hand (an ID is issued only by a person, rule D26).
"""One-off seed of meta/entity_register.csv and meta/entity_code.csv (Phase 3.1, 2026-11-05).

After this run the register is maintained by hand: a new code stops core/pipeline/build_entities.py
and a person issues an ID or links it to an existing one (DATA_MODEL 4.5).
"""
import csv, glob, collections, os, sys

REPO = sys.argv[1]
os.chdir(REPO)
ISSUED = "2026-11-05"

dim = collections.defaultdict(dict)          # code -> {year: (name_bm, name_en)}
for p in sorted(glob.glob("sources/pkkp/data/*/dim_maksud.csv")):
    for r in csv.DictReader(open(p)):
        dim[r["maksud_code"]][int(r["year"])] = (r["name_bm"].strip(), r["name_en"].strip())
ang = collections.defaultdict(set)           # code -> book years
for p in sorted(glob.glob("sources/anggaran/data/*/fact_anggaran_maksud_*.csv")):
    y = int(p.split("_")[-1][:4])
    for r in csv.DictReader(open(p)):
        ang[r["maksud_code"]].add(y)

HEADS = {c for c in set(dim) | set(ang) if c.startswith("T.")} | {"P.70"}
nums = sorted({c[2:] for c in set(dim) | set(ang) if c[:2] in ("B.", "P.") and c not in HEADS}, key=int)

def years(code):
    # lineage runs come from the audited accounts only: a budget book reprints a lapsed vote with zeros
    return sorted(dim.get(code, {}))

def runs(ys):
    out = []
    for y in ys:
        if out and y == out[-1][-1] + 1:
            out[-1].append(y)
        else:
            out.append([y])
    return out

# lineages approved before this register (curated/pipeline/build_ministry_fiscal.py, analyst rule)
APPROVED = {"41": "63", "49": "64"}          # old number -> successor number
PROOF_APPROVED = ("analyst-approved renumbering (curated/pipeline/build_ministry_fiscal.py, MAPPING RULE): "
                  "continuity of function; {old} ends {end}, {new} starts {start}")

entities = []   # dict(num_list, b_runs...)
for n in nums:
    if n in APPROVED.values():
        continue
    b, p = years("B." + n), years("P." + n)
    chain = [n] + ([APPROVED[n]] if n in APPROVED else [])
    if n in APPROVED:
        # one lineage across the renumbering and the successor's own lapses (B.64 2019: folded into Education)
        entities.append(dict(nums=chain, b_runs=[sorted(set(b) | set(years("B." + APPROVED[n])))], status="confirmed"))
        continue
    br = runs(b)
    for i, r in enumerate(br):
        entities.append(dict(nums=[n], b_runs=[r], status="proposed" if len(br) > 1 else "confirmed",
                             reappears=i > 0))

def name_of(code, y):
    return dim.get(code, {}).get(y)

def best_name(e):
    # latest PKKP year in which the entity's B code is printed
    cands = []
    for n in e["nums"]:
        for y in e["b_runs"][0]:
            if name_of("B." + n, y):
                cands.append((y, "B." + n))
    if not cands:
        sys.exit(f"no PKKP name for {e}")
    y, code = max(cands)
    nm, en = name_of(code, y)
    pn = name_of("P." + code[2:], y)
    if (nm.endswith((",", " DAN", "-")) or len(nm) < 18) and pn and len(pn[0]) > len(nm):
        nm = pn[0]
    if nm.isupper():
        nm = nm.title().replace(" Dan ", " dan ")
    return nm, en, y

TYPES = {"06": "ministry", "10": "ministry", "11": "vote", "12": "vote", "03": "auditor"}

reg, codes = [], []
reg.append(dict(entity_id="E000001", entity_type="government", name_bm="Kerajaan Persekutuan",
                name_en="Federal Government of Malaysia", parent_entity_id="", gfs_sector="central_gov",
                decision_status="confirmed", issued_on=ISSUED, reason="the federal government (seed)"))
codes.append(dict(entity_id="E000001", code_system="federal_gov", code="MY", valid_from="", valid_to="",
                  proof="seed"))
STATES = [("MY-01", "Kerajaan Negeri Johor", "Johor State Government"),
          ("MY-02", "Kerajaan Negeri Kedah", "Kedah State Government"),
          ("MY-03", "Kerajaan Negeri Kelantan", "Kelantan State Government"),
          ("MY-04", "Kerajaan Negeri Melaka", "Melaka State Government"),
          ("MY-05", "Kerajaan Negeri Negeri Sembilan", "Negeri Sembilan State Government"),
          ("MY-06", "Kerajaan Negeri Pahang", "Pahang State Government"),
          ("MY-07", "Kerajaan Negeri Pulau Pinang", "Pulau Pinang State Government"),
          ("MY-08", "Kerajaan Negeri Perak", "Perak State Government"),
          ("MY-09", "Kerajaan Negeri Perlis", "Perlis State Government"),
          ("MY-10", "Kerajaan Negeri Selangor", "Selangor State Government"),
          ("MY-11", "Kerajaan Negeri Terengganu", "Terengganu State Government"),
          ("MY-12", "Kerajaan Negeri Sabah", "Sabah State Government"),
          ("MY-13", "Kerajaan Negeri Sarawak", "Sarawak State Government")]
for i, (g, bm, en) in enumerate(STATES, start=2):
    eid = f"E{i:06d}"
    reg.append(dict(entity_id=eid, entity_type="government", name_bm=bm, name_en=en, parent_entity_id="",
                    gfs_sector="state_gov", decision_status="confirmed", issued_on=ISSUED,
                    reason="a state government (seed); the government, not the place (geo " + g + ")"))
    codes.append(dict(entity_id=eid, code_system="state_gov", code=g, valid_from="", valid_to="", proof="seed"))

nxt = len(reg) + 1
treasury = None
for e in entities:
    eid = f"E{nxt:06d}"; nxt += 1
    nm, en, ly = best_name(e)
    n0 = e["nums"][0]
    et = TYPES.get(n0) or ("ministry" if nm.lower().startswith(("kementerian", "kem.")) else "department")
    if n0 == "10":
        treasury = eid
    span = e["b_runs"][0]
    reason = f"supply vote B.{n0} {span[0]}-{span[-1]} (seed from PKKP FY2009-2024 and Anggaran 2024-2026)"
    if len(e["nums"]) > 1:
        reason = (f"supply vote B.{e['nums'][0]} {min(years('B.' + e['nums'][0]))}-"
                  f"{max(years('B.' + e['nums'][0]))}, renumbered B.{e['nums'][1]} from "
                  f"{min(years('B.' + e['nums'][1]))} (lineage approved before the register; see the code proofs)")
    if e.get("reappears"):
        reason = (f"B.{n0} printed again from {span[0]} after a lapse: a NEW body by rule D26 "
                  f"unless a person links it to the earlier B.{n0}")
    elif e["status"] == "proposed":
        reason += f"; B.{n0} lapses after {span[-1]} and is printed again later: kept separate by rule D26"
    e.update(eid=eid, name=nm)
    reg.append(dict(entity_id=eid, entity_type=et, name_bm=nm, name_en=en, parent_entity_id="",
                    gfs_sector="central_gov", decision_status=e["status"], issued_on=ISSUED, reason=reason))
for r in reg:
    if r["entity_type"] == "vote":
        r["parent_entity_id"] = treasury
        r["reason"] += "; a vote administered by the Treasury (B.10), not a body of its own"
    elif r["entity_id"] != "E000001" and r["gfs_sector"] == "central_gov":
        r["parent_entity_id"] = "E000001"

# codes: B years inside the entity's run; P years: inside a run, else the latest run that ended before
for e in entities:
    for i, n in enumerate(e["nums"]):
        b = [y for y in years("B." + n) if y in e["b_runs"][0]]
        if b:
            first = (i == 0)
            proof = "first appearance" if first else PROOF_APPROVED.format(
                old="B." + e["nums"][0], end=max(years("B." + e["nums"][0])), new="B." + n, start=min(b))
            codes.append(dict(entity_id=e["eid"], code_system="maksud_bekalan", code="B." + n,
                              valid_from=str(min(b)), valid_to=str(max(b)), proof=proof))

def owner_of_p(n, y):
    cand = [e for e in entities if n in e["nums"] and any(r[0] <= y <= r[-1] for r in e["b_runs"])]
    if cand:
        return cand[0], "in_run"
    before = [e for e in entities if n in e["nums"] and e["b_runs"][0][-1] < y]
    if before:
        return max(before, key=lambda e: e["b_runs"][0][-1]), "residual"
    return None, None

for n in nums:
    if n in APPROVED.values():
        pass
    ys = years("P." + n)
    if not ys:
        continue
    groups = collections.OrderedDict()
    for y in ys:
        e, how = owner_of_p(n, y)
        if e is None:
            sys.exit(f"P.{n} {y}: no B vote run to own it")
        groups.setdefault(e["eid"], []).append((y, how))
    for eid, lst in groups.items():
        for rr in runs([y for y, _ in lst]):
            res = [y for y, how in lst if y in rr and how == "residual"]
            proof = "development vote of the same body"
            if res:
                proof += (f"; {res[0]}-{res[-1]} printed after the body's B vote ended: its residual "
                          f"development vote (projects still being paid), rule D26")
            e0 = next(e for e in entities if e["eid"] == eid)
            if n != e0["nums"][0] and rr[0] == min(years("P." + n)):
                proof += "; " + PROOF_APPROVED.format(old="P." + e0["nums"][0],
                                                      end=max(years("P." + e0["nums"][0])),
                                                      new="P." + n, start=rr[0])
            codes.append(dict(entity_id=eid, code_system="maksud_pembangunan", code="P." + n,
                              valid_from=str(rr[0]), valid_to=str(rr[-1]), proof=proof))

# a code printed in a budget book after its last PKKP year belongs to its latest holder
for code, bys in ang.items():
    if code in HEADS:
        continue
    mine = [c for c in codes if c["code"] == code]
    if not mine:
        sys.exit(f"{code}: printed in Anggaran {sorted(bys)} but never in PKKP - needs a person to issue an ID")
    last = max(mine, key=lambda c: int(c["valid_to"]))
    if max(bys) > int(last["valid_to"]):
        last["proof"] += f"; printed in Anggaran {min(y for y in bys if y > int(last['valid_to']))}-{max(bys)} budget books"
        last["valid_to"] = str(max(bys))

os.makedirs("meta", exist_ok=True)
with open("meta/entity_register.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(reg[0])); w.writeheader(); w.writerows(reg)
codes.sort(key=lambda r: (r["entity_id"], r["code_system"], r["valid_from"]))
with open("meta/entity_code.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(codes[0])); w.writeheader(); w.writerows(codes)
print(len(reg), "entities;", len(codes), "codes;", sum(r["decision_status"] == "proposed" for r in reg), "proposed")
print("heads (breakdowns, not entities):", sorted(HEADS))
