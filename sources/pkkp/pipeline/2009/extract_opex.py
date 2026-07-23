import sys, re; sys.path.insert(0,'/home/claude/pkkp/work/2009/pipeline')
import lib2009 as L, json
SRC=L.SRC; STMT="C2 Penyata Perbelanjaan Mengurus"
OBJCLASS={'10000':'Emolumen','20000':'Perkhidmatan dan Bekalan','30000':'Aset',
 '40000':'Pemberian dan Kenaan Bayaran Tetap','50000':'Perbelanjaan-perbelanjaan Lain'}
SKIP=['Penyata Perbelanjaan Mengurus','bagi tahun berakhir','Maksud Perbelanjaan',
 'Bajet Asal','Bajet Disemak','(disambung','(Sambungan)','.indd','Nota:*']
def is_skip(s):
    t=s.strip()
    if t=='' : return True
    if 'JUMLAH PERBELANJAAN' in t: return False
    for k in SKIP:
        if k in t: return True
    if t in ('RM','%','Bajet'): return True
    if re.fullmatch(r'\d{1,3}', t): return True
    if 'PERBELANJAAN TANGGUNGAN' in t or 'PERBELANJAAN BEKALAN' in t: return True
    return False
maksud_re=re.compile(r'^([TB]\.\d{2})\s+(.*)$')
prog_re=re.compile(r'^(\*?)(\d{6})\s+(.*)$')
obj_re=re.compile(r'^(\d{5})\s+(.+?)\s{2,}')
jum_prog_re=re.compile(r'^Jumlah\s+(\d{6})\b')
oc_re=re.compile(r'^Jumlah (Emolumen|Perkhidmatan dan Bekalan|Aset|Pemberian (?:dan|&) Kenaan Bayaran Tetap|Perbelanjaan-perbelanjaan Lain)\b')
def canon_oc(lbl):
    lbl=lbl.replace('&','dan')
    return lbl.replace('Jumlah ','').strip()
rows=[]; maksud_rows=[]; recs=[]
cur_jenis=cur_mcode=cur_mname=cur_prog=cur_progname=None; cur_prog_fn=False; mname_wrap=False
ocbuf=[]  # list of (canon_class, a,dp,se,pc, has_fn, pdf,pr)
def v4(s):
    toks=L.numtokens(s)
    if len(toks)<4: return None
    a=L.parse_num(toks[-4]);dp=L.parse_num(toks[-3]);se=L.parse_num(toks[-2]);pc=L.parse_num(toks[-1])
    fn=any('*' in t for t in toks)
    return (a[0],dp[0],se[0],pc[0],fn)
def emit(rt,pdf,pr,**kw):
    d=dict(jenis_bm='',maksud_code='',maksud_name_bm='',program_code='',program_name_bm='',
      aktiviti_code='',aktiviti_name_bm='',objek_code='',objek_class_bm='',row_type=rt,label_bm='',
      aa='',at='',vr='',aj='',se='',pc='',va='',fn=False)
    d.update(kw)
    rows.append([d['jenis_bm'],d['maksud_code'],d['maksud_name_bm'],d['program_code'],d['program_name_bm'],
      d['aktiviti_code'],d['aktiviti_name_bm'],d['objek_code'],d['objek_class_bm'],d['row_type'],d['label_bm'],
      2009,d['aa'],d['at'],d['vr'],d['aj'],d['se'],d['pc'],d['va'],d['fn'],SRC,pdf,pr,STMT])
def flush_oc(level, key, pdf, pr):
    for cls,a,dp,se,pc,fn,pp,ppr in ocbuf:
        if level=='maksud':
            emit('jumlah_objek_maksud',pp,ppr,jenis_bm=cur_jenis,maksud_code=key,maksud_name_bm=cur_mname,
                 objek_class_bm=cls,label_bm='Jumlah '+cls,aa=L.fmt(a),aj=L.fmt(dp),se=L.fmt(se),pc=L.fmt(pc),fn=fn)
        elif level=='jenis':
            emit('jumlah_objek_jenis',pp,ppr,jenis_bm=key,objek_class_bm=cls,label_bm='Jumlah '+cls,
                 aa=L.fmt(a),aj=L.fmt(dp),se=L.fmt(se),pc=L.fmt(pc),fn=fn)
        else:
            emit('jumlah_objek_keseluruhan',pp,ppr,objek_class_bm=cls,label_bm='Jumlah '+cls,
                 aa=L.fmt(a),aj=L.fmt(dp),se=L.fmt(se),pc=L.fmt(pc),fn=fn)
    ocbuf.clear()

for pdf in range(51,94):
    pr=L.printed_of(pdf)
    for raw in L.lines(pdf):
        if is_skip(raw): continue
        s=raw.strip()
        # object-class subtotal -> buffer
        if oc_re.match(s):
            r=v4(s)
            if r: ocbuf.append((canon_oc(oc_re.match(s).group(0)),r[0],r[1],r[2],r[3],r[4],pdf,pr))
            continue
        # keseluruhan grand
        if s.startswith('JUMLAH KESELURUHAN MENGURUS'):
            flush_oc('kesel',None,pdf,pr); r=v4(s)
            emit('jumlah_besar',pdf,pr,label_bm='JUMLAH KESELURUHAN MENGURUS',aa=L.fmt(r[0]),aj=L.fmt(r[1]),se=L.fmt(r[2]),pc=L.fmt(r[3]))
            recs.append(('kesel',r[0],r[1],r[2])); continue
        if s.startswith('JUMLAH MENGURUS'):
            toks=L.numtokens(s); se=L.parse_num(toks[-1])[0]
            emit('jumlah_besar_dengan_pindahan',pdf,pr,label_bm='JUMLAH MENGURUS',se=L.fmt(se))
            recs.append(('mengurus_pindahan',se)); continue
        # jenis grand
        if s.startswith('JUMLAH PERBELANJAAN TANGGUNGAN') or s.startswith('JUMLAH PERBELANJAAN BEKALAN'):
            jen='Tanggungan' if 'TANGGUNGAN' in s else 'Bekalan'
            flush_oc('jenis',jen,pdf,pr); r=v4(s)
            emit('jumlah_jenis',pdf,pr,jenis_bm=jen,label_bm=s.split('  ')[0].strip(),aa=L.fmt(r[0]),aj=L.fmt(r[1]),se=L.fmt(r[2]),pc=L.fmt(r[3]))
            recs.append(('jenis',jen,r[0],r[1],r[2])); continue
        # maksud header
        m=maksud_re.match(s)
        if m and 'SAMB' not in s:
            cur_mcode=m.group(1); cur_mname=m.group(2).strip(); cur_prog=None
            cur_jenis='Tanggungan' if cur_mcode[0]=='T' else 'Bekalan'; mname_wrap=True; continue
        if m and 'SAMB' in s: continue
        # program header
        pm=prog_re.match(s)
        if pm and pm.group(2) not in OBJCLASS:
            cur_prog=pm.group(2); cur_progname=pm.group(3).strip(); cur_prog_fn=(pm.group(1)=='*'); mname_wrap=False; continue
        # program subtotal
        jp=jum_prog_re.match(s)
        if jp:
            r=v4(s)
            # program_code always = current program (printed subtotal code kept in label; handles B.32 '010100' typo)
            pcode = cur_prog if cur_prog else jp.group(1)
            if r: emit('jumlah_program',pdf,pr,jenis_bm=cur_jenis,maksud_code=cur_mcode,maksud_name_bm=cur_mname,
                 program_code=pcode,program_name_bm=cur_progname,label_bm='Jumlah '+jp.group(1),
                 aa=L.fmt(r[0]),aj=L.fmt(r[1]),se=L.fmt(r[2]),pc=L.fmt(r[3]),fn=cur_prog_fn)
            if r: recs.append(('prog',cur_mcode,pcode,r[0],r[1],r[2]))
            continue
        # object row
        om=obj_re.match(s)
        if om and cur_prog is not None and om.group(1) in OBJCLASS:
            r=v4(s); code=om.group(1)
            if r: emit('object_program',pdf,pr,jenis_bm=cur_jenis,maksud_code=cur_mcode,maksud_name_bm=cur_mname,
                 program_code=cur_prog,program_name_bm=cur_progname,objek_code=code,objek_class_bm=OBJCLASS[code],
                 label_bm=code+' '+OBJCLASS[code],aa=L.fmt(r[0]),aj=L.fmt(r[1]),se=L.fmt(r[2]),pc=L.fmt(r[3]),fn=r[4])
            if r: recs.append(('obj',cur_mcode,cur_prog,code,r[0],r[1],r[2]))
            continue
        # maksud grand
        if s.startswith('JUMLAH '):
            flush_oc('maksud',cur_mcode,pdf,pr); r=v4(s)
            if r:
                emit('jumlah_maksud',pdf,pr,jenis_bm=cur_jenis,maksud_code=cur_mcode,maksud_name_bm=cur_mname,
                     label_bm=s.split('   ')[0].strip(),aa=L.fmt(r[0]),aj=L.fmt(r[1]),se=L.fmt(r[2]),pc=L.fmt(r[3]))
                maksud_rows.append([cur_mcode,cur_jenis,cur_mname,2009,L.fmt(r[0]),L.fmt(r[1]),L.fmt(r[2]),L.fmt(r[3]),False,SRC,pdf,pr,"C2 Penyata Perbelanjaan Mengurus (Jumlah Maksud)"])
                recs.append(('maksud',cur_mcode,cur_jenis,r[0],r[1],r[2]))
            continue
        if mname_wrap and s.isupper() and not L.numtokens(s):
            cur_mname=(cur_mname+' '+s).strip()
L.write_csv("fact_opex_detail.csv",
 ["jenis_bm","maksud_code","maksud_name_bm","program_code","program_name_bm","aktiviti_code","aktiviti_name_bm",
  "objek_code","objek_class_bm","row_type","label_bm","year","anggaran_asal_rm","anggaran_tambahan_rm","viremen_rm",
  "anggaran_jumlah_rm","sebenar_rm","prestasi_pct","varian_rm","has_footnote","source_file","pdf_page","printed_page","statement"],rows)
L.write_csv("fact_opex_maksud.csv",
 ["maksud_code","jenis_bm","maksud_name_bm","year","anggaran_asal_rm","anggaran_dipinda_rm","sebenar_rm","pct_anggaran","has_footnote","source_file","pdf_page","printed_page","statement"],maksud_rows)
json.dump(recs,open('/tmp/opex_recs.json','w'))
from collections import Counter
print("maksud:",len(maksud_rows),"detail:",len(rows))
print("dup maksud codes:",[k for k,v in Counter(r[0] for r in maksud_rows).items() if v>1])
print("row_types:",Counter(r[9] for r in rows))
