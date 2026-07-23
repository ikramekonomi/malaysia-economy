import sys; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L
SRC=L.SRC
CHECKS=[]
def chk(status,name,ext,pr):
    diff = (None if (ext is None or pr is None) else round(ext-pr,2))
    CHECKS.append([status,name,ext,pr,'' if diff is None else diff])

# ---------- fact_financial_position (Lembaran Imbangan, pdf38 printed31) ----------
rows=[]
STMT="Lembaran Imbangan"
pdf=38; pr=L.printed_of(pdf)
defs=[
 ("WANG AWAM","WANG TUNAI","6"),
 ("WANG AWAM","PELABURAN","7"),
 ("WANG AWAM","JUMLAH WANG AWAM",""),
 ("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN","8"),
 ("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN","9"),
 ("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN","10"),
 ("KUMPULAN WANG DISATUKAN","JUMLAH DIPEGANG BAGI",""),
]
lines=L.lines(pdf)
def find_nums(sub):
    for l in lines:
        if sub in l:
            return [L.parse_num(t) for t in L.numtokens(l)]
    return None
# WANG TUNAI line: "A WANG TUNAI 6 21,722,318,474 15,401,985,728"
def bs_row(label):
    for l in lines:
        if label in l and ('WANG' in l or 'AKAUN' in l or 'PELABURAN' in l):
            nums=[t for t in L.numtokens(l)]
            return nums
    return None
recs=[
 ("WANG AWAM","WANG TUNAI","6","A    WANG TUNAI"),
 ("WANG AWAM","PELABURAN","7","B    PELABURAN"),
 ("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN","8","C    AKAUN HASIL"),
 ("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN","9","D    AKAUN PINJAMAN"),
 ("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN","10","E    AKAUN AMANAH"),
]
for sec,item,nota,key in recs:
    nums=bs_row(key)
    v9=L.parse_num(nums[-2])[0]; v8=L.parse_num(nums[-1])[0]
    rows.append([sec,item,nota,2009,L.fmt(v9),SRC,pdf,pr,STMT])
    rows.append([sec,item,nota,2008,L.fmt(v8),SRC,pdf,pr,STMT])
# subtotals: two lines with only 43,535,543,299 32,091,891,601
sub9,sub8=43535543299.0,32091891601.0
for lbl in ["JUMLAH WANG AWAM","JUMLAH DIPEGANG BAGI"]:
    rows.append([("WANG AWAM" if 'WANG AWAM' in lbl else "KUMPULAN WANG DISATUKAN"),lbl,"",2009,L.fmt(sub9),SRC,pdf,pr,STMT])
    rows.append([("WANG AWAM" if 'WANG AWAM' in lbl else "KUMPULAN WANG DISATUKAN"),lbl,"",2008,L.fmt(sub8),SRC,pdf,pr,STMT])
L.write_csv("fact_financial_position.csv",
 ["section","line_item_bm","nota","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
# validation: A+B=subtotal ; C+D+E=subtotal ; both subtotals equal
d={ (r[1],r[3]):float(r[4]) for r in rows }
chk("PASS" if abs((d[("WANG TUNAI",2009)]+d[("PELABURAN",2009)])-sub9)<1 else "FAIL","fin_pos WangAwam A+B=Jumlah 2009",d[("WANG TUNAI",2009)]+d[("PELABURAN",2009)],sub9)
chk("PASS" if abs((d[("AKAUN HASIL DISATUKAN",2009)]+d[("AKAUN PINJAMAN DISATUKAN",2009)]+d[("AKAUN AMANAH DISATUKAN",2009)])-sub9)<1 else "FAIL","fin_pos C+D+E=Jumlah 2009",d[("AKAUN HASIL DISATUKAN",2009)]+d[("AKAUN PINJAMAN DISATUKAN",2009)]+d[("AKAUN AMANAH DISATUKAN",2009)],sub9)

import json
json.dump(CHECKS, open('/tmp/checks_bs.json','w'))
print("CHECKS so far:", len(CHECKS))
for c in CHECKS: print(c)
