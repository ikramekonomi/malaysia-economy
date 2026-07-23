import json
from collections import defaultdict
recs=json.load(open('/tmp/opex_recs.json'))
obj=defaultdict(lambda:[0,0,0]); prog={}; ocm=defaultdict(lambda:[0,0,0]); mak={}; jen={}; kesel=None
# We need object-class maksud subtotals grouped: rebuild from detail not recs (ocm not in recs). Load detail.
import csv
D=list(csv.DictReader(open('/home/claude/pkkp/warehouse2009/fact_opex_detail.csv')))
def f(x): return float(x) if x not in (None,'') else 0.0
# 1. objects sum -> program subtotal
prog_obj=defaultdict(lambda:[0.0,0.0,0.0]); prog_sub={}
mak_prog=defaultdict(lambda:[0.0,0.0,0.0]); mak_grand={}
mak_ocm=defaultdict(lambda:[0.0,0.0,0.0])
jen_mak=defaultdict(lambda:[0.0,0.0,0.0]); jen_grand={}
kesel_row=None; mengurus_pind=None
for r in D:
    rt=r['row_type']; key=(r['maksud_code'],r['program_code'])
    trip=(f(r['anggaran_asal_rm']),f(r['anggaran_jumlah_rm']),f(r['sebenar_rm']))
    if rt=='object_program':
        for i in range(3): prog_obj[key][i]+=trip[i]
    elif rt=='jumlah_program':
        prog_sub[key]=trip
        for i in range(3): mak_prog[r['maksud_code']][i]+=trip[i]
    elif rt=='jumlah_objek_maksud':
        for i in range(3): mak_ocm[r['maksud_code']][i]+=trip[i]
    elif rt=='jumlah_maksud':
        mak_grand[r['maksud_code']]=trip
        for i in range(3): jen_mak[r['jenis_bm']][i]+=trip[i]
    elif rt=='jumlah_jenis':
        jen_grand[r['jenis_bm']]=trip
    elif rt=='jumlah_besar':
        kesel_row=trip
    elif rt=='jumlah_besar_dengan_pindahan':
        mengurus_pind=f(r['sebenar_rm'])
COLS=['asal','dipinda','sebenar']; CH=[]
def cmp(name,a,b):
    ok=all(abs(a[i]-b[i])<0.05 for i in range(3))
    CH.append(("PASS" if ok else "FAIL",name,a,b))
    return ok
# program additivity
pf=0
for key,sub in prog_sub.items():
    if not all(abs(prog_obj[key][i]-sub[i])<0.05 for i in range(3)):
        pf+=1
        if pf<=8: print("PROG MISMATCH",key,"obj",prog_obj[key],"sub",sub)
print(f"[1] object->program: {len(prog_sub)-pf}/{len(prog_sub)} programs OK")
# program->maksud grand
mf=0
for mc,g in mak_grand.items():
    if not all(abs(mak_prog[mc][i]-g[i])<0.05 for i in range(3)):
        mf+=1; print("MAKSUD(prog sum) MISMATCH",mc,mak_prog[mc],g)
print(f"[2] program->maksud: {len(mak_grand)-mf}/{len(mak_grand)} maksuds OK")
# object-class maksud subtotals -> maksud grand
of=0
for mc,g in mak_grand.items():
    if not all(abs(mak_ocm[mc][i]-g[i])<0.05 for i in range(3)):
        of+=1; print("MAKSUD(objclass sum) MISMATCH",mc,mak_ocm[mc],g)
print(f"[3] objclass->maksud: {len(mak_grand)-of}/{len(mak_grand)} maksuds OK")
# maksud->jenis
for jn in jen_grand:
    ok=all(abs(jen_mak[jn][i]-jen_grand[jn][i])<0.5 for i in range(3))
    print(f"[4] maksud->jenis {jn}: {'OK' if ok else 'FAIL'} sum={jen_mak[jn]} grand={jen_grand[jn]}")
# jenis->keseluruhan
tot=[jen_grand['Tanggungan'][i]+jen_grand['Bekalan'][i] for i in range(3)]
ok=all(abs(tot[i]-kesel_row[i])<0.5 for i in range(3))
print(f"[5] jenis->keseluruhan: {'OK' if ok else 'FAIL'} sum={tot} kesel={kesel_row}")
print(f"[6] JUMLAH MENGURUS (incl pindahan) sebenar = {mengurus_pind} (expect 158639304227.70)")
print(f"    keseluruhan sebenar = {kesel_row[2]} (expect 157066959319.47)")
print(f"    pindahan = {mengurus_pind-kesel_row[2]:.2f} (expect 1572344908.23)")
json.dump({'prog_fail':pf,'mak_prog_fail':mf,'mak_ocm_fail':of,'nprog':len(prog_sub),'nmak':len(mak_grand),
 'kesel':kesel_row,'mengurus':mengurus_pind,'jen':jen_grand},open('/tmp/opex_valid.json','w'))
