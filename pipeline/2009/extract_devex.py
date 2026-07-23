import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; STMT="E1ai Penyata Perbelanjaan Pembangunan"
maksud_re=re.compile(r'^([P]\.\d{2})\s+(.*)$')
proj_re=re.compile(r'^(\d{5})\s+(.+)$')
# ---- parse LEFT pages -> ordered value rows tagged with maksud/program ----
left=[]   # dict rows
cur_m=cur_mname=None; cur_prog=None
for pdf in range(98,149,2):
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if s=='' or '.indd' in l: continue
        if any(k in s for k in ['Penyata Perbelanjaan Pembangunan','bagi tahun berakhir','Maksud Perbelanjaan',
             'Jumlah Anggaran','Harga Projek','2006 – 2010','Hingga 31.12','(disambung','(sambungan)','Nota:']): continue
        if s in ('RM','RM RM RM'): continue
        m=maksud_re.match(s)
        if m and 'SAMB' not in s:
            cur_m=m.group(1); cur_mname=m.group(2).strip(); cur_prog=None; continue
        if m and 'SAMB' in s: 
            cur_m=m.group(1); cur_mname=re.sub(r'\s*-?\s*\(SAMB\.\)','',m.group(2)).strip(); cur_prog=None; continue
        pj=proj_re.match(s)
        if pj and len(toks)>=4:
            money=[L.parse_num(t)[0] for t in toks[-3:]]
            fn = s.startswith('*') or '*' in toks[0]
            name=re.sub(r'\s{2,}.*$','', pj.group(2)).strip()
            left.append(dict(kind='project',maksud=cur_m,mname=cur_mname,prog=cur_prog or '',code=pj.group(1),
                 name=name,kos=money[0],ang=money[1],prior=money[2],fn=fn,pdf=pdf,pr=pr)); continue
        if re.match(r'^JUMLAH [A-Z]', s) and len(toks)>=3:
            money=[L.parse_num(t)[0] for t in toks[-3:]]
            left.append(dict(kind='ministry_total',maksud=cur_m,mname=cur_mname,prog='',code='',
                 name=re.sub(r'\s{2,}.*$','',s).strip(),kos=money[0],ang=money[1],prior=money[2],fn=False,pdf=pdf,pr=pr)); continue
        if re.match(r'^Jumlah\b', s) and len(toks)>=3:
            money=[L.parse_num(t)[0] for t in toks[-3:]]
            left.append(dict(kind='program_subtotal',maksud=cur_m,mname=cur_mname,prog=cur_prog or '',code='',
                 name=re.sub(r'\s{2,}.*$','',s).strip(),kos=money[0],ang=money[1],prior=money[2],fn=False,pdf=pdf,pr=pr)); continue
        # program header: allcaps, no numbers
        if not toks and s.isupper() and len(s)>3 and 'PENYATA' not in s:
            cur_prog=s.strip(); continue
        # else wrapped project name -> append to last project name
        if left and left[-1]['kind']=='project' and not toks:
            left[-1]['name']=(left[-1]['name']+' '+s).strip()
# ---- parse RIGHT pages -> ordered numeric rows ----
right=[]
for pdf in range(99,150,2):
    pr=L.printed_of(pdf)
    for l in L.lines(pdf):
        if '.indd' in l or ' PM' in l or ' AM' in l: continue
        toks=L.numtokens(l)
        if len(toks) in (7,8):
            vals=[L.parse_num(t) for t in toks]
            v=[x[0] for x in vals]; fn=any(x[1] for x in vals)
            pindah = v[7] if len(v)==8 else None
            right.append(dict(bL=v[0],bP=v[1],bJ=v[2],sL=v[3],sP=v[4],sJ=v[5],terk=v[6],pindah=pindah,fn=fn,pdf=pdf,pr=pr))
print("left value rows:",len(left),"right rows:",len(right))
# ---- align with identity: prior + sJ (+pindah) == terk ----
def ident_ok(lr,rr):
    if lr['prior'] is None or rr['sJ'] is None or rr['terk'] is None: return False
    return abs(lr['prior']+rr['sJ']-rr['terk'])<0.05
# group left into per-maksud blocks (contiguous in doc order)
blocks=[]
for lr in left:
    if not blocks or blocks[-1][0]!=lr['maksud']:
        blocks.append((lr['maksud'],[lr]))
    else:
        blocks[-1][1].append(lr)
pairs=[]; j=0; unmatched=0; block_adj=[]
def block_zip(L_m, R_s):
    """two-pointer identity zip within a bounded block. Always emits exactly len(L_m) pairs."""
    res=[]; a=0; b=0
    while a<len(L_m):
        lr=L_m[a]
        if b<len(R_s) and ident_ok(lr,R_s[b]): res.append((lr,R_s[b])); a+=1; b+=1; continue
        # right[b] extra (no left partner): skip it, retry same lr
        if b+1<len(R_s) and ident_ok(lr,R_s[b+1]) and not (a+1<len(L_m) and ident_ok(L_m[a+1],R_s[b])):
            b+=1; continue
        # left[a] extra (no right partner): emit None
        if a+1<len(L_m) and b<len(R_s) and ident_ok(L_m[a+1],R_s[b]):
            res.append((lr,None)); a+=1; continue
        res.append((lr, R_s[b] if b<len(R_s) else None))
        if b<len(R_s): b+=1
        a+=1
    return res
for mc, L_m in blocks:
    k=len(L_m); last=L_m[-1]; best_e=None
    for e in range(max(0,j+k-3), j+k+4):
        if 0<=e<len(right) and ident_ok(last,right[e]): best_e=e; break
    if best_e is None: best_e=min(j+k-1,len(right)-1)
    z=block_zip(L_m,right[j:best_e+1]); pairs.extend(z); j=best_e+1
    unmatched+=sum(1 for lr,rr in z if rr is None or not ident_ok(lr,rr))
print(f"pairs:{len(pairs)} maksud_blocks:{len(blocks)} unmatched:{unmatched}")
if block_adj: print("blocks needing adjustment (maksud,leftk,rights,badrows):",block_adj)
json.dump({'nleft':len(left),'nright':len(right),'unmatched':unmatched,'leftover':len(right)-j},open('/tmp/devex_align.json','w'))
# ---- write fact_devex_project ----
def g(x): return L.fmt(x) if x is not None else ''
rows=[]; mak_rows=[]
for lr,rr in pairs:
    rt=lr['kind']
    if rr:
        aok = (lr['prior'] is not None and rr['sJ'] is not None and rr['terk'] is not None and abs(lr['prior']+rr['sJ']-rr['terk'])<0.05)
        # langsung+pinjaman=jumlah check
        lpj = (rr['bL'] is not None and abs((rr['bL']or 0)+(rr['bP']or 0)-(rr['bJ']or 0))<0.05 and abs((rr['sL']or 0)+(rr['sP']or 0)-(rr['sJ']or 0))<0.05)
        rows.append([lr['maksud'],lr['mname'],rt,lr['prog'],lr['code'],lr['name'],2009,
            g(lr['kos']),g(lr['prior']),g(rr['bL']),g(rr['bP']),g(rr['bJ']),g(rr['sL']),g(rr['sP']),g(rr['sJ']),
            g(rr['terk']),g(rr['pindah']),g(lr['ang']),(lr['fn'] or rr['fn']),(aok and lpj),SRC,lr['pdf'],lr['pr'],STMT])
        if rt=='ministry_total':
            mak_rows.append([lr['maksud'],lr['mname'],lr['name'],2009,g(lr['kos']),g(lr['prior']),
                g(rr['bL']),g(rr['bP']),g(rr['bJ']),g(rr['sL']),g(rr['sP']),g(rr['sJ']),g(rr['terk']),g(lr['ang']),g(rr['pindah']),
                lr['fn'],SRC,lr['pdf'],lr['pr'],"E1ai Penyata Perbelanjaan Pembangunan (Jumlah Maksud)"])
    else:
        rows.append([lr['maksud'],lr['mname'],rt,lr['prog'],lr['code'],lr['name'],2009,
            g(lr['kos']),g(lr['prior']),'','','','','','','','',g(lr['ang']),lr['fn'],False,SRC,lr['pdf'],lr['pr'],STMT])
L.write_csv("fact_devex_project.csv",
 ["maksud_code","maksud_name_bm","row_type","program_bm","projek_code","name_bm","year","kos_keseluruhan_rm",
  "terkumpul_rmke9_prior_rm","anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm",
  "sebenar_pinjaman_rm","sebenar_jumlah_rm","terkumpul_rmke9_rm","pindah_rm","anggaran_rmke9_2006_2010_rm",
  "has_footnote","align_ok","source_file","pdf_page","printed_page","statement"],rows)
L.write_csv("fact_devex_maksud.csv",
 ["maksud_code","maksud_name_bm","jumlah_label_bm","year","kos_keseluruhan_rm","terkumpul_rmke9_prior_rm",
  "anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm","sebenar_pinjaman_rm",
  "sebenar_jumlah_rm","terkumpul_rmke9_rm","anggaran_rmke9_2006_2010_rm","pindah_rm","has_footnote",
  "source_file","pdf_page","printed_page","statement"],mak_rows)
aok_n=sum(1 for r in rows if r[19] is True)
print(f"wrote devex_project rows:{len(rows)} align_ok:{aok_n} ({100*aok_n//len(rows)}%) | devex_maksud:{len(mak_rows)}")
# validation: maksud sebenar_jumlah sum == grand
gr=[m for m in mak_rows if 'PERBELANJAAN PEMBANGUNAN' in m[2]]
mk=[m for m in mak_rows if 'PERBELANJAAN PEMBANGUNAN' not in m[2]]
def fnum(x): return float(x) if x not in ('',None) else 0.0
sum_sJ=sum(fnum(m[11]) for m in mk); grand_sJ=fnum(gr[0][11]) if gr else None
print(f"devex maksud sum sebenar_jumlah={sum_sJ:.2f} grand={grand_sJ} diff={sum_sJ-(grand_sJ or 0):.2f}")
json.dump({'nproj':len(rows),'align_ok':aok_n,'nmaksud':len(mak_rows),'sum_sJ':sum_sJ,'grand_sJ':grand_sJ},open('/tmp/devex_valid.json','w'))


# ===== FINAL fact_devex_maksud builder =====
import re as _re
codes=[b[0] for b in blocks]; ci=0; out=[]
for pdf in range(98,149,2):
    prp=L.printed_of(pdf)
    rr=[]
    for l in L.lines(pdf+1):
        if '.indd' in l or ' PM' in l or ' AM' in l: continue
        t=L.numtokens(l)
        if len(t) in (7,8): rr.append([L.parse_num(x)[0] for x in t]+([None] if len(t)==7 else []))
    for l in L.lines(pdf):
        s=l.strip(); toks=L.numtokens(l)
        if _re.match(r'^JUMLAH [A-Z]', s) and len(toks)>=3:
            kos,ang,prior=[L.parse_num(t)[0] for t in toks[-3:]]
            label=_re.sub(r'\s{2,}.*$','',s).strip(); is_grand=('PERBELANJAAN PEMBANGUNAN' in label)
            best=None
            if prior and abs(prior)>0.01:
                exact=[v for v in rr if v[6] is not None and v[5] is not None and abs(prior+v[5]-v[6])<0.05]
                if len(exact)==1: best=exact[0]
                elif len(exact)>1: best=max(exact,key=lambda v:v[6] or 0)
                else:
                    cand=[v for v in rr if v[6] is not None]
                    best=max(cand,key=lambda v:v[6] or 0) if cand else [0.0]*8
            else:
                best=[0.0]*8   # dormant maksud (printed --- ---)
            pindah=best[7] if len(best)>=8 else None
            code='TOTAL' if is_grand else (codes[ci] if ci<len(codes) else ''); 
            if not is_grand: ci+=1
            nm='JUMLAH PERBELANJAAN PEMBANGUNAN' if is_grand else label.replace('JUMLAH ','').strip()
            out.append([code,nm,label,2009,L.fmt(kos),L.fmt(prior),L.fmt(best[0]),L.fmt(best[1]),L.fmt(best[2]),
                L.fmt(best[3]),L.fmt(best[4]),L.fmt(best[5]),L.fmt(best[6]),L.fmt(ang),L.fmt(pindah),False,
                SRC,pdf,prp,"E1ai Penyata Perbelanjaan Pembangunan (Jumlah Maksud)"])
L.write_csv("fact_devex_maksud.csv",
 ["maksud_code","maksud_name_bm","jumlah_label_bm","year","kos_keseluruhan_rm","terkumpul_rmke9_prior_rm",
  "anggaran_langsung_rm","anggaran_pinjaman_rm","anggaran_jumlah_rm","sebenar_langsung_rm","sebenar_pinjaman_rm",
  "sebenar_jumlah_rm","terkumpul_rmke9_rm","anggaran_rmke9_2006_2010_rm","pindah_rm","has_footnote",
  "source_file","pdf_page","printed_page","statement"],out)
mk=[m for m in out if m[0] not in ("TOTAL","")]; gr=[m for m in out if m[0]=="TOTAL"]
def fn(x): return float(x) if x not in ("",None) else 0.0
import json
DV={}
for col,idx,exp in [("sebenar_langsung",9,45294239672.54),("sebenar_pinjaman",10,4221115898.00),
   ("sebenar_jumlah",11,49515355570.54),("anggaran_jumlah",8,55840144382.0)]:
    ssum=sum(fn(m[idx]) for m in mk); g=fn(gr[0][idx])
    DV[col]=[round(ssum,2),round(g,2),abs(ssum-g)<2,abs(g-exp)<1]
    print(f"devex_maksud {col}: maksud_sum={ssum:.2f} grand={g:.2f} sum==grand:{abs(ssum-g)<2} grand==printed:{abs(g-exp)<1}")
print("devex_maksud rows:",len(out))
dj=json.load(open("/tmp/devex_valid.json")) if __import__("os").path.exists("/tmp/devex_valid.json") else {}
dj.update({"devex_maksud_rows":len(out),"maksud_checks":DV,"nproj":len(rows),"align_ok":aok_n})
json.dump(dj,open("/tmp/devex_valid.json","w"))
