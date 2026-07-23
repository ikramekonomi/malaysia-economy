import csv
from collections import defaultdict

P = "/home/claude/pkkp/warehouse2010/fact_devex_project.csv"
M = "/home/claude/pkkp/warehouse2010/fact_devex_maksud.csv"
EXP_P = ["maksud_code","maksud_name_bm","row_type","program_bm","projek_code","name_bm","year","kos_keseluruhan_rm","anggaran_rmke9_2006_2010_rm","terkumpul_rmke9_prior_rm","anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm","sebenar_pinjaman_rm","sebenar_jumlah_rm","terkumpul_rmke9_rm","has_footnote","source_file","pdf_page","printed_page","statement"]
EXP_M = ["maksud_code","maksud_name_bm","jumlah_label_bm","year","kos_keseluruhan_rm","anggaran_rmke9_2006_2010_rm","terkumpul_rmke9_prior_rm","anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm","sebenar_pinjaman_rm","sebenar_jumlah_rm","terkumpul_rmke9_rm","has_footnote","source_file","pdf_page","printed_page","statement"]

rows = list(csv.DictReader(open(P, encoding="utf-8")))
mrows = list(csv.DictReader(open(M, encoding="utf-8")))
hp = list(csv.reader(open(P, encoding="utf-8")))[0]
hm = list(csv.reader(open(M, encoding="utf-8")))[0]
print("project header exact:", hp == EXP_P)
print("maksud  header exact:", hm == EXP_M)

def f(r, k): return float(r[k])
NUMC = ["kos_keseluruhan_rm","anggaran_rmke9_2006_2010_rm","terkumpul_rmke9_prior_rm","anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm","sebenar_pinjaman_rm","sebenar_jumlah_rm","terkumpul_rmke9_rm"]

# ---- per-project identities ----
id1 = id2 = id3 = 0
f1 = f2 = f3 = 0
fails = []
for r in rows:
    if r["row_type"] != "project":
        continue
    a = abs(f(r,"terkumpul_rmke9_rm") - (f(r,"terkumpul_rmke9_prior_rm") + f(r,"sebenar_jumlah_rm"))) <= 0.05
    b = abs(f(r,"anggaran_jumlah_rm") - (f(r,"anggaran_langsung_rm") + f(r,"anggaran_pinjaman_rm"))) <= 0.05
    c = abs(f(r,"sebenar_jumlah_rm") - (f(r,"sebenar_langsung_rm") + f(r,"sebenar_pinjaman_rm"))) <= 0.05
    id1 += a; id2 += b; id3 += c
    if not a: f1+=1; fails.append(("kumul", r["maksud_code"], r["projek_code"], r["name_bm"][:30]))
    if not b: f2+=1; fails.append(("ang", r["maksud_code"], r["projek_code"], r["name_bm"][:30]))
    if not c: f3+=1; fails.append(("seb", r["maksud_code"], r["projek_code"], r["name_bm"][:30]))
np = sum(1 for r in rows if r["row_type"]=="project")
print(f"\nper-project identities (N={np}):")
print(f"  terkumpul == prior+sebenar_jumlah : {id1} pass / {f1} fail")
print(f"  anggaran_jumlah == lgs+pinj       : {id2} pass / {f2} fail")
print(f"  sebenar_jumlah == lgs+pinj        : {id3} pass / {f3} fail")
for x in fails[:20]: print("   FAIL", x)

# ---- per-maksud reconciliation: sum of project rows == ministry_total ----
proj = defaultdict(lambda: [0.0]*10)
for r in rows:
    if r["row_type"]=="project":
        for i,k in enumerate(NUMC): proj[r["maksud_code"]][i]+=f(r,k)
mt = {}
for r in rows:
    if r["row_type"]=="ministry_total":
        mt[r["maksud_code"]] = [f(r,k) for k in NUMC]
okm = badm = 0
for mk,vals in mt.items():
    diffs=[abs(proj[mk][i]-vals[i]) for i in range(10)]
    if max(diffs)<=0.05: okm+=1
    else:
        badm+=1
        worst=max(range(10),key=lambda i:diffs[i])
        print(f"  MAKSUD MISMATCH {mk} col {NUMC[worst]}: proj={proj[mk][worst]:,.2f} vs total={vals[worst]:,.2f}")
print(f"\nper-maksud reconciliation (sum projects == ministry_total): {okm} pass / {badm} fail  (of {len(mt)} maksuds)")

# ---- sum of ministry_totals == grand_total ----
gt=[f([g for g in rows if g["row_type"]=="grand_total"][0],k) for k in NUMC]
sm=[sum(mt[mk][i] for mk in mt) for i in range(10)]
gdiff=[abs(sm[i]-gt[i]) for i in range(10)]
print(f"sum(ministry_totals)==grand_total: {'PASS' if max(gdiff)<=0.5 else 'FAIL'} (max diff {max(gdiff):.2f})")
for i,k in enumerate(NUMC):
    flag='' if gdiff[i]<=0.5 else '  <-- MISMATCH'
    print(f"    {k:32s} sum={sm[i]:,.2f}  grand={gt[i]:,.2f}{flag}")

# ---- program subtotal reconciliation (verified groups) ----
psum=defaultdict(lambda:[0.0]*10)
for r in rows:
    if r["row_type"]=="project" and r["program_bm"]:
        for i,k in enumerate(NUMC): psum[(r["maksud_code"],r["program_bm"].upper())][i]+=f(r,k)
prog_ok=prog_bad=0
for r in rows:
    if r["row_type"]=="program_subtotal":
        key=(r["maksud_code"],r["name_bm"].upper())
        if key in psum:
            d=max(abs(psum[key][i]-f(r,NUMC[i])) for i in range(10))
            if d<=0.05: prog_ok+=1
            else: prog_bad+=1
print(f"\nprogram_subtotal exact-sum (linked groups): {prog_ok} verified")
nlinked=len(set((r['maksud_code'],r['program_bm']) for r in rows if r['row_type']=='project' and r['program_bm']))
nproj_linked=sum(1 for r in rows if r['row_type']=='project' and r['program_bm'])
print(f"distinct linked programs: {nlinked}; projects with program_bm: {nproj_linked}")

# ---- ministry_total label vs maksud name ----
print("\nministry_total label != maksud name:")
mism=0
for r in rows:
    if r["row_type"]=="ministry_total" and r["name_bm"].strip().upper()!=r["maksud_name_bm"].strip().upper():
        print(f"   {r['maksud_code']}: name={r['maksud_name_bm']!r} label={r['name_bm']!r}"); mism+=1
if not mism: print("   (none - all match)")

# ---- grand total figures ----
g=[x for x in rows if x["row_type"]=="grand_total"][0]
print("\nGRAND TOTAL (JUMLAH PERBELANJAAN PEMBANGUNAN):")
for k in ["kos_keseluruhan_rm","anggaran_rmke9_2006_2010_rm","terkumpul_rmke9_prior_rm","anggaran_jumlah_rm","sebenar_jumlah_rm","terkumpul_rmke9_rm"]:
    print(f"   {k:32s} {f(g,k):,.2f}")
print("   sebenar matches 52,791,630,220 :", abs(f(g,"sebenar_jumlah_rm")-52791630220)<1)

print("\nmaksuds:", sorted(set(r["maksud_code"] for r in rows if r["row_type"]=="project")))
print("num maksuds:", len(set(r["maksud_code"] for r in rows if r["row_type"]=="project")))
print("has_footnote True count:", sum(1 for r in rows if r["has_footnote"]=="True"))
