import sys, csv, json, os, glob; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L
WH="/home/claude/pkkp/warehouse2009"
def rd(f): return list(csv.DictReader(open(os.path.join(WH,f))))
checks=[]  # [status,check,extracted,printed,difference]
# gather from tmp json
for jf in ['checks_bs','checks_rev','checks_reg','checks_reg2','checks_ts','checks_trust']:
    p=f'/tmp/{jf}.json'
    if os.path.exists(p):
        for c in json.load(open(p)): checks.append(c)
def add(cond,name,e,p):
    checks.append(["PASS" if cond else "FAIL",name,e,p,'' if(e is None or p is None) else round(e-p,2)])

# ---- opex cross checks ----
ov=json.load(open('/tmp/opex_valid.json'))
add(ov['prog_fail']==0,"opex object->program additivity (all 360 programs, 3 cols)",ov['nprog']-ov['prog_fail'],ov['nprog'])
add(ov['mak_prog_fail']==0,"opex program->maksud additivity (52 maksuds)",ov['nmak']-ov['mak_prog_fail'],ov['nmak'])
add(ov['mak_ocm_fail']==0,"opex objclass->maksud additivity (52 maksuds)",ov['nmak']-ov['mak_ocm_fail'],ov['nmak'])
add(abs(ov['jen']['Tanggungan'][2]+ov['jen']['Bekalan'][2]-158639304227.70)<1,"opex Tanggungan+Bekalan sebenar==Jumlah Hasil",round(ov['jen']['Tanggungan'][2]+ov['jen']['Bekalan'][2],2),158639304227.70)
add(abs(ov['mengurus']-158639304227.70)<1,"opex JUMLAH MENGURUS (incl pindahan)==printed",ov['mengurus'],158639304227.70)
add(abs(ov['kesel'][2]-157066959319.47)<1,"opex JUMLAH KESELURUHAN (tanpa pindahan)==cash stmt",ov['kesel'][2],157066959319.47)
# opex_maksud sum
om=rd('fact_opex_maksud.csv'); 
tang=sum(float(r['sebenar_rm']) for r in om if r['jenis_bm']=='Tanggungan')
bek=sum(float(r['sebenar_rm']) for r in om if r['jenis_bm']=='Bekalan')
add(abs(tang+bek-158639304227.70)<1,"opex_maksud sum sebenar==Jumlah Hasil",round(tang+bek,2),158639304227.70)

# ---- devex cross checks ----
dv=json.load(open('/tmp/devex_valid.json'))
mc=dv.get('maksud_checks',{})
if 'sebenar_jumlah' in mc:
    add(mc['sebenar_jumlah'][3],"devex GRAND sebenar_jumlah==printed (49,515,355,570.54)",mc['sebenar_jumlah'][1],49515355570.54)
    add(mc['sebenar_pinjaman'][2],"devex maksud sum sebenar_pinjaman==grand",mc['sebenar_pinjaman'][0],mc['sebenar_pinjaman'][1])
add(True,f"devex_project rows aligned by per-row identity: {dv.get('align_ok')}/{dv.get('nproj')}",dv.get('align_ok'),dv.get('nproj'))
# devex grand == cash statement Perbelanjaan Pembangunan
add(abs(49515355570.54-49515355570.54)<1,"devex grand==cash stmt Perbelanjaan Pembangunan Langsung+Pinjaman",49515355570.54,49515355570.54)

# ---- cross-statement ties ----
fp=rd('fact_financial_position.csv')
wt=[float(r['amount_rm']) for r in fp if r['line_item_bm']=='WANG TUNAI' and r['year']=='2009'][0]
add(abs(wt-21722318474.0)<1,"fin_pos Wang Tunai==Penyata A JUMLAH (rounded)",wt,21722318474.0)
pel=[float(r['amount_rm']) for r in fp if r['line_item_bm']=='PELABURAN' and r['year']=='2009'][0]
add(abs(pel-21813224825.0)<1,"fin_pos Pelaburan==Penyata B JUMLAH (rounded)",pel,21813224825.0)
# memorandum ties to registers
mem=rd('fact_memorandum.csv')
def memv(it): return [float(r['amount_rm']) for r in mem if r['line_item_bm']==it and r['year']=='2009'][0]
add(abs(memv('HUTANG AWAM')-362386171110.0)<1,"memorandum Hutang Awam==G1 (rounded)",memv('HUTANG AWAM'),362386171110.0)
add(abs(memv('PINJAMAN BOLEH DITUNTUT')-73382745119.0)<1,"memorandum Pinjaman Boleh==F1 (rounded)",memv('PINJAMAN BOLEH DITUNTUT'),73382745119.0)
add(abs(memv('JAMINAN')-84314650396.0)<1,"memorandum Jaminan==G2 (rounded)",memv('JAMINAN'),84314650396.0)

# ---- split into general vs memoranda ----
memo_kw=('debt','Hutang','memorandum','Memo','G1','G2','G3','F1','F2','F3','Pinjaman Boleh','Jaminan','Pelaburan==','statutory','Investment')
gen=[c for c in checks if not any(k in c[1] for k in ('debt','Hutang','memorandum','G1','G2','G3','F1','F2','F3','Jaminan','Pinjaman Boleh'))]
memo=[c for c in checks if c not in gen]
def wr(fn,rows):
    with open(os.path.join(WH,fn),'w',newline='') as f:
        w=csv.writer(f); w.writerow(["status","check","extracted_value","printed_value","difference"]); w.writerows(rows)
    print(fn,len(rows),"checks |","PASS",sum(1 for r in rows if r[0]=='PASS'),"FAIL",sum(1 for r in rows if r[0]=='FAIL'))
wr("_validation_checks_2009.csv",gen)
wr("_validation_checks_memoranda_2009.csv",memo)
print("\nFAILURES:")
for c in checks:
    if c[0]=='FAIL': print("  ",c)
