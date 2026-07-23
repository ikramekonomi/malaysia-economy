#!/usr/bin/env python3
import csv, collections
OUT="/home/claude/pkkp/warehouse2012/fact_opex_detail.csv"
rows=list(csv.DictReader(open(OUT,encoding="utf-8")))
def f(x): return float(x) if x not in ("",None) else 0.0
COLS=["anggaran_asal_rm","anggaran_jumlah_rm","sebenar_rm"]  # Asal, Dipinda(=final), Amaun(=sebenar)
def close(a,b): return abs(a-b)<0.5
OBJC={"10000":"Emolumen","20000":"Perkhidmatan dan Bekalan","30000":"Aset",
      "40000":"Pemberian dan Kenaan Bayaran Tetap","50000":"Perbelanjaan-perbelanjaan Lain"}
def norm(s): return (s or "").replace("Perbelanjaan-Perbelanjaan","Perbelanjaan-perbelanjaan").replace("& ","dan ").strip()

# leaf = object_aktiviti rows (the only printed figures at the finest grain)
leaf=[r for r in rows if r["row_type"]=="object_aktiviti"]

# ---- [1] PROGRAM: sum(leaf) over (maksud,program) == printed jumlah_program
lp=collections.defaultdict(lambda:[0.0,0.0,0.0])
for r in leaf:
    k=(r["maksud_code"],r["program_code"])
    for i,c in enumerate(COLS): lp[k][i]+=f(r[c])
pp=pf=0; pfl=[]
for r in rows:
    if r["row_type"]=="jumlah_program":
        k=(r["maksud_code"],r["program_code"]); s=lp.get(k,[0,0,0])
        w=[f(r[c]) for c in COLS]
        if all(close(s[i],w[i]) for i in range(3)): pp+=1
        else: pf+=1; pfl.append((k,r["pdf_page"],r["label_bm"],[round(x,2) for x in s],[round(x,2) for x in w]))
print(f"[1] PROGRAM  sum(object leaves)==jumlah_program : {pp} pass / {pf} fail")
for k,pg,lab,got,want in pfl: print(f"    FAIL {k} '{lab}' p{pg}: leafsum={got} vs printed={want}")

# ---- [2a] MAKSUD: sum(leaf) over maksud == printed jumlah_maksud
lm=collections.defaultdict(lambda:[0.0,0.0,0.0])
for r in leaf:
    for i,c in enumerate(COLS): lm[r["maksud_code"]][i]+=f(r[c])
mp=mf=0; mfl=[]
for r in rows:
    if r["row_type"]=="jumlah_maksud":
        s=lm.get(r["maksud_code"],[0,0,0]); w=[f(r[c]) for c in COLS]
        if all(close(s[i],w[i]) for i in range(3)): mp+=1
        else: mf+=1; mfl.append((r["maksud_code"],r["pdf_page"],[round(x,2) for x in s],[round(x,2) for x in w]))
print(f"[2a] MAKSUD  sum(object leaves)==jumlah_maksud : {mp} pass / {mf} fail")
for k,pg,got,want in mfl: print(f"    FAIL {k} p{pg}: leafsum={got} vs printed={want}")

# ---- [2b] MAKSUD-CLASS: sum(leaf by class) over maksud == printed jumlah_objek_maksud
lmc=collections.defaultdict(lambda:[0.0,0.0,0.0])
for r in leaf:
    k=(r["maksud_code"],OBJC.get(r["objek_code"],norm(r["objek_class_bm"])))
    for i,c in enumerate(COLS): lmc[k][i]+=f(r[c])
cp=cf=0; cfl=[]
for r in rows:
    if r["row_type"]=="jumlah_objek_maksud":
        k=(r["maksud_code"],norm(r["objek_class_bm"])); s=lmc.get(k,[0,0,0]); w=[f(r[c]) for c in COLS]
        if all(close(s[i],w[i]) for i in range(3)): cp+=1
        else: cf+=1; cfl.append((k,r["pdf_page"],[round(x,2) for x in s],[round(x,2) for x in w]))
print(f"[2b] MAKSUD-CLASS sum(leaf by class)==jumlah_objek_maksud : {cp} pass / {cf} fail")
for k,pg,got,want in cfl: print(f"    FAIL {k} p{pg}: leafsum={got} vs printed={want}")

# ---- [2c] program-class: object_program == sum(leaf of that class in program), where present
opc=collections.defaultdict(lambda:[0.0,0.0,0.0])
for r in leaf:
    k=(r["maksud_code"],r["program_code"],OBJC.get(r["objek_code"]))
    for i,c in enumerate(COLS): opc[k][i]+=f(r[c])
op_p=op_f=0; opfl=[]
for r in rows:
    if r["row_type"]=="object_program":
        k=(r["maksud_code"],r["program_code"],norm(r["objek_class_bm"])); s=opc.get(k,[0,0,0]); w=[f(r[c]) for c in COLS]
        if all(close(s[i],w[i]) for i in range(3)): op_p+=1
        else: op_f+=1; opfl.append((k,r["pdf_page"],[round(x,2) for x in s],[round(x,2) for x in w]))
print(f"[2c] PROGRAM-CLASS object_program==sum(leaf class in program) : {op_p} pass / {op_f} fail")
for k,pg,got,want in opfl: print(f"    FAIL {k} p{pg}: leafsum={got} vs printed={want}")

# ---- [3] JENIS + GRAND
jbj=collections.defaultdict(lambda:[0.0,0.0,0.0])
for r in rows:
    if r["row_type"]=="jumlah_maksud":
        for i,c in enumerate(COLS): jbj[r["jenis_bm"]][i]+=f(r[c])
for r in rows:
    if r["row_type"]=="jumlah_jenis":
        printed=[f(r[c]) for c in COLS]
        best=min(jbj, key=lambda j:abs(jbj[j][2]-printed[2]))
        ok=all(close(jbj[best][i],printed[i]) for i in range(3))
        print(f"[3] JENIS p{r['pdf_page']} ~{best}: printed={[round(x,2) for x in printed]} sum(jumlah_maksud)={[round(x,2) for x in jbj[best]]} {'OK' if ok else 'FAIL'}")
for r in rows:
    if r["row_type"]=="jumlah_besar":
        gt=sum(f(x["sebenar_rm"]) for x in rows if x["row_type"]=="jumlah_jenis")
        gm=sum(f(x["sebenar_rm"]) for x in rows if x["row_type"]=="jumlah_maksud")
        print(f"[3] GRAND printed p{r['pdf_page']}: asal={r['anggaran_asal_rm']} dipinda={r['anggaran_jumlah_rm']} sebenar={r['sebenar_rm']} pct={r['prestasi_pct']} foot={r['has_footnote']}")
        print(f"    sum(jumlah_jenis sebenar)={gt:,.2f}  sum(jumlah_maksud sebenar)={gm:,.2f}")
        print(f"    grand sebenar - pindahan 2,375,673,144.13 = {f(r['sebenar_rm'])-2375673144.13:,.2f}  (Nota5b=205,537,081,525)")

# ---- [4] maksud codes
codes=sorted({r["maksud_code"] for r in rows if r["maksud_code"]}, key=lambda x:(x[0],int(x[2:])))
T=[c for c in codes if c[0]=="T"]; B=[c for c in codes if c[0]=="B"]
print(f"[4] {len(codes)} maksud codes -> {len(T)} T + {len(B)} B")
print("    T:",T); print("    B:",B)
print(f"[.] has_footnote rows: {sum(1 for r in rows if r['has_footnote']=='True')}")
