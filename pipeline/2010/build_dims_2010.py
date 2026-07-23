#!/usr/bin/env python3
"""Build dim_maksud for 2010 from fact_opex_maksud + fact_devex_maksud.
Reuses the EN/NOTES glossaries from build_dims_2012.py (extracted via ast, not executed).
Names in 2010 opex/devex print ALL CAPS; store name_bm Title-cased to match the
established dim_maksud cross-year convention (2012 dim used Title Case)."""
import csv, ast, os
WH="/home/claude/pkkp/warehouse2010"
REF="/home/claude/pkkp/work/2012/pipeline/build_dims_2012.py"

# pull EN and NOTES dict literals without executing module-level code
tree=ast.parse(open(REF).read())
EN={}; NOTES={}
for node in tree.body:
    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
        if node.targets[0].id=="EN": EN=ast.literal_eval(node.value)
        if node.targets[0].id=="NOTES": NOTES=ast.literal_eval(node.value)

SUPP_EN={
    "elaun-elaun diraja":"Royal Allowances",
    "ketua hakim negara, hakim besar dan hakim":"Chief Justice, Chief Judges and Judges",
    "pencen, elaun bersara dan ganjaran":"Pensions, Retirement Allowances and Gratuities",
    "peruntukan kepada kumpulan wang terkanun":"Contributions to Statutory Funds",
    "kementerian penerangan, komunikasi dan kebudayaan":"Ministry of Information, Communications and Culture",
}
EN_LC={k.lower():v for k,v in EN.items()}
EN_LC.update(SUPP_EN)
def en_of(name):
    return EN_LC.get(name.lower(),"")

SMALL={"dan","atas","ke","kepada","bagi","di","yang","dari","serta","atau"}
def titlecase(s):
    if not s.isupper(): return s
    out=[]
    for i,wd in enumerate(s.split(" ")):
        lw=wd.lower()
        out.append(lw if (lw in SMALL and i>0) else wd.title())
    return " ".join(out)

rows={}
with open(f"{WH}/fact_opex_maksud.csv",encoding="utf-8") as f:
    for r in csv.DictReader(f):
        code=r["maksud_code"]
        rows[code]={"maksud_code":code,"code_num":int(code.split(".")[1]),
            "jenis":{"T":"Tanggungan","B":"Bekalan"}[code[0]],
            "name_bm":titlecase(r["maksud_name_bm"]),
            "name_en":en_of(r["maksud_name_bm"]),
            "note":NOTES.get(code,""),"year":r["year"]}
with open(f"{WH}/fact_devex_maksud.csv",encoding="utf-8") as f:
    for r in csv.DictReader(f):
        code=r["maksud_code"]
        if code in ("TOTAL",""): continue
        name=r["maksud_name_bm"]
        rows[code]={"maksud_code":code,"code_num":int(code.split(".")[1]),
            "jenis":"Pembangunan","name_bm":titlecase(name),
            "name_en":en_of(name),"note":NOTES.get(code,""),"year":r["year"]}

missing=[v["name_bm"] for v in rows.values() if not v["name_en"]]
if missing: print("MISSING EN GLOSS:",missing)
with open(f"{WH}/dim_maksud.csv","w",newline="",encoding="utf-8") as f:
    cw=csv.DictWriter(f,fieldnames=["maksud_code","code_num","jenis","name_bm","name_en","note","year"])
    cw.writeheader()
    for k in sorted(rows,key=lambda c:(c[0],int(c.split(".")[1]))):
        cw.writerow(rows[k])
print(f"dim_maksud.csv: {len(rows)} rows")
