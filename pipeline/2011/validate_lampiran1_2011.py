#!/usr/bin/env python3
"""Validate fact_opex_detail.csv (2011) against its OWN printed subtotals
and the Nota 5(b) per-maksud / grand controls."""
import csv
from collections import defaultdict, OrderedDict

CSV = "/home/claude/pkkp/warehouse2011/fact_opex_detail.csv"
MAKSUD = "/home/claude/pkkp/warehouse2011/fact_opex_maksud.csv"
FULL = "/home/claude/pkkp/work/2011/full.txt"
TOL = 0.01

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
for r in rows:
    for k in ("anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm"):
        r[k] = float(r[k]) if r[k] not in ("", None) else 0.0

VAL = ("anggaran_asal_rm", "anggaran_jumlah_rm", "sebenar_rm")
passes = fails = 0
fail_msgs = []


def close(a, b):
    return abs(a - b) <= TOL


def check(desc, got, want):
    global passes, fails
    ok = all(close(got[k], want[k]) for k in VAL)
    if ok:
        passes += 1
    else:
        fails += 1
        diffs = {k: round(got[k] - want[k], 2) for k in VAL if not close(got[k], want[k])}
        fail_msgs.append(f"{desc}: diff(got-printed) {diffs}")
    return ok


# index by row position to keep document order per group
# ---- Check A: object_aktiviti sum -> jumlah_aktiviti (per maksud,program,akt)
grp = defaultdict(lambda: defaultdict(float))
jrows = {}
for r in rows:
    key = (r["maksud_code"], r["program_code"], r["aktiviti_code"])
    if r["row_type"] == "object_aktiviti" and r["aktiviti_code"]:
        for k in VAL:
            grp[key][k] += r[k]
    if r["row_type"] == "jumlah_aktiviti" and r["aktiviti_code"]:
        jrows.setdefault(key, []).append(r)
nA = 0
for key, jl in jrows.items():
    if key in grp and len(jl) == 1:
        nA += 1
        check(f"[A akt {key[0]}/{key[1]}/{key[2]}]", grp[key], jl[0])

# ---- Check B: object_aktiviti sum -> jumlah_program (per maksud,program)
grpB = defaultdict(lambda: defaultdict(float))
jprog = {}
for r in rows:
    key = (r["maksud_code"], r["program_code"])
    if r["row_type"] == "object_aktiviti":
        for k in VAL:
            grpB[key][k] += r[k]
    if r["row_type"] == "jumlah_program":
        jprog.setdefault(key, []).append(r)
nB = 0
for key, jl in jprog.items():
    if key in grpB and len(jl) == 1:
        nB += 1
        check(f"[B prog {key[0]}/{key[1]}]", grpB[key], jl[0])

# ---- Check C: object_program sum -> jumlah_program (only programs that have them)
grpC = defaultdict(lambda: defaultdict(float))
haveC = set()
for r in rows:
    key = (r["maksud_code"], r["program_code"])
    if r["row_type"] == "object_program":
        haveC.add(key)
        for k in VAL:
            grpC[key][k] += r[k]
nC = 0
for key in haveC:
    if key in jprog and len(jprog[key]) == 1:
        nC += 1
        check(f"[C objprog {key[0]}/{key[1]}]", grpC[key], jprog[key][0])

# ---- Check D: jumlah_program sum -> jumlah_maksud (per maksud)
grpD = defaultdict(lambda: defaultdict(float))
jmak = {}
for r in rows:
    if r["row_type"] == "jumlah_program":
        for k in VAL:
            grpD[r["maksud_code"]][k] += r[k]
    if r["row_type"] == "jumlah_maksud":
        jmak.setdefault(r["maksud_code"], []).append(r)
nD = 0
for mk, jl in jmak.items():
    if mk in grpD and len(jl) == 1:
        nD += 1
        check(f"[D maksud {mk} program-sum]", grpD[mk], jl[0])

# ---- Check E: jumlah_objek_maksud sum -> jumlah_maksud (per maksud)
grpE = defaultdict(lambda: defaultdict(float))
for r in rows:
    if r["row_type"] == "jumlah_objek_maksud":
        for k in VAL:
            grpE[r["maksud_code"]][k] += r[k]
nE = 0
for mk, jl in jmak.items():
    if mk in grpE and len(jl) == 1:
        nE += 1
        check(f"[E maksud {mk} objek-sum]", grpE[mk], jl[0])

# ---- Check F: jumlah_maksud sum -> jumlah_jenis (per jenis)
grpF = defaultdict(lambda: defaultdict(float))
jjenis = {}
for r in rows:
    if r["row_type"] == "jumlah_maksud":
        for k in VAL:
            grpF[r["jenis_bm"]][k] += r[k]
    if r["row_type"] == "jumlah_jenis":
        jjenis[r["jenis_bm"]] = r
nF = 0
for jn, jr in jjenis.items():
    if jn in grpF:
        nF += 1
        check(f"[F jenis {jn}]", grpF[jn], jr)

# ---- Check G: jumlah_jenis sum -> jumlah_besar
grpG = defaultdict(float)
for jr in jjenis.values():
    for k in VAL:
        grpG[k] += jr[k]
besar = [r for r in rows if r["row_type"] == "jumlah_besar"][0]
nG = 1
check("[G grand: jenis-sum vs JUMLAH]", grpG, besar)

# ---- Check H: jumlah_objek_jenis / keseluruhan sums
grpH1 = defaultdict(lambda: defaultdict(float))
for r in rows:
    if r["row_type"] == "jumlah_objek_jenis":
        for k in VAL:
            grpH1[r["jenis_bm"]][k] += r[k]
nH = 0
for jn, jr in jjenis.items():
    if jn in grpH1:
        nH += 1
        check(f"[H objek_jenis {jn}]", grpH1[jn], jr)
grpH2 = defaultdict(float)
for r in rows:
    if r["row_type"] == "jumlah_objek_keseluruhan":
        for k in VAL:
            grpH2[k] += r[k]
if grpH2:
    nH += 1
    check("[H objek_keseluruhan vs JUMLAH]", grpH2, besar)

# ---- Check I: per-maksud sebenar vs Nota 5(b) ----
nota = {}
for r in csv.DictReader(open(MAKSUD, encoding="utf-8")):
    nota[r["maksud_code"]] = float(r["sebenar_rm"])
nI = nIfail = 0
Ifails = []
for mk, jl in jmak.items():
    if mk in nota:
        nI += 1
        got = round(jl[0]["sebenar_rm"])
        if abs(got - nota[mk]) > 1.0:   # Nota5b rounded to whole RM
            nIfail += 1
            Ifails.append(f"  maksud {mk}: L1 sebenar {jl[0]['sebenar_rm']:,.2f} vs Nota5b {nota[mk]:,.0f}")

# ---- grand sebenar control ----
grand_sebenar = besar["sebenar_rm"]
NOTA_GRAND = 185418919743.0

# ---- verbatim: every non-zero sebenar appears on its source page ----
pages = open(FULL, encoding="utf-8").read().split("\f")
missing_verbatim = 0
vb_examples = []
for r in rows:
    v = r["sebenar_rm"]
    if v == 0:
        continue
    txt = pages[int(r["pdf_page"]) - 1]
    s2 = f"{abs(v):,.2f}"
    s0 = f"{abs(v):,.0f}"           # some rows print whole RM w/o sen
    if s2 not in txt and s0 not in txt:
        missing_verbatim += 1
        if len(vb_examples) < 12:
            vb_examples.append(f"  p{r['pdf_page']} {r['row_type']} {r['label_bm'][:32]!r} {s2}")

print("=" * 70)
print(f"CHECK COUNTS: A(akt)={nA} B(prog)={nB} C(objprog)={nC} D(prog->maksud)={nD}")
print(f"              E(objek->maksud)={nE} F(maksud->jenis)={nF} G(grand)={nG}")
print(f"              H(objek jenis/grand)={nH} I(Nota5b maksud)={nI}")
print(f"ADDITIVITY: {passes} pass / {fails} fail")
for m in fail_msgs:
    print("  FAIL", m)
print(f"\nNOTA5b per-maksud sebenar: {nI - nIfail} pass / {nIfail} fail")
for m in Ifails:
    print("  FAIL", m)
print(f"\nGRAND sebenar (Amaun) printed = {grand_sebenar:,.2f}")
print(f"  Nota5b grand = {NOTA_GRAND:,.2f}  diff = {grand_sebenar - NOTA_GRAND:+.2f}")
print(f"\nVERBATIM: {len(rows)-missing_verbatim} non-zero sebenar found on source page; "
      f"{missing_verbatim} missing")
for e in vb_examples:
    print("  MISS", e)

# ---- confirm every failing subtotal ROW is itself faithful to print ----
print("\nFAITHFULNESS of failing subtotals (printed values present verbatim on page):")
fail_codes = {"B.31", "B.32", "B.07", "B.12", "B.45", "B.48", "B.41", "B.06"}
for r in rows:
    if r["row_type"] in ("jumlah_program", "jumlah_aktiviti", "object_program") and \
            r["maksud_code"] in fail_codes:
        txt = pages[int(r["pdf_page"]) - 1]
        ok = all((f"{abs(r[k]):,.2f}" in txt or f"{abs(r[k]):,.0f}" in txt or r[k] == 0)
                 for k in VAL)
        if not ok:
            print(f"  NOT-FAITHFUL {r['maksud_code']} {r['label_bm']} p{r['pdf_page']}")
print("  (no lines above = every failing-maksud subtotal matches its printed figures)")
