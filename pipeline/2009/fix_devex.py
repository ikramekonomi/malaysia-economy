import csv
P='/home/claude/pkkp/warehouse2009/fact_devex_project.csv'
M='/home/claude/pkkp/warehouse2009/fact_devex_maksud.csv'
proj=list(csv.DictReader(open(P)))
hdr=list(proj[0].keys())
mak={r['maksud_code']:r for r in csv.DictReader(open(M))}

RIGHT=['anggaran_langsung_rm','anggaran_pinjaman_rm','anggaran_jumlah_rm',
       'sebenar_langsung_rm','sebenar_pinjaman_rm','sebenar_jumlah_rm','terkumpul_rmke9_rm']
# ministries verified (against source) as empty/wrong in project and correct in maksud:
FIX={'P.10','P.26','P.27','P.29','P.44','P.45','P.47'}

def num(x):
    try: return float(x)
    except: return None

mt_changes=[]; grand_relabel=None
for r in proj:
    if r['row_type']!='ministry_total': continue
    is_grand = 'PERBELANJAAN PEMBANGUNAN' in r['name_bm']
    if is_grand:
        old=(r['row_type'],r['maksud_code'])
        r['row_type']='grand_total'; r['maksud_code']=''
        grand_relabel=(old,(r['row_type'],r['maksud_code']),r['sebenar_jumlah_rm'])
        continue
    if r['maksud_code'] not in FIX:
        continue   # leave agreeing ministries (incl. P.70 SIMPANAN) untouched
    src=mak.get(r['maksud_code'])
    before={k:r[k] for k in RIGHT}
    for k in RIGHT:
        r[k]=src[k]
    mt_changes.append((r['maksud_code'],r['name_bm'][:34],
        {k:(before[k],r[k]) for k in RIGHT if before[k]!=r[k]}))

# pindah_rm cleanup: mis-typed transfer references -> empty + flag via has_footnote
pindah_fixed=0
for r in proj:
    if r['pindah_rm'] not in ('',None):
        r['pindah_rm']=''
        r['has_footnote']='True'
        pindah_fixed+=1

with open(P,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=hdr); w.writeheader(); w.writerows(proj)

print('=== ministry_total reconciliations (7 problem ministries) ===')
for c in mt_changes:
    print(c[0],c[1])
    for k,(o,n) in c[2].items(): print('    {}: {!r} -> {!r}'.format(k,o,n))
print('grand relabel:',grand_relabel)
print('pindah_rm cleared+flagged rows:',pindah_fixed)

# ---- verification ----
proj2=list(csv.DictReader(open(P)))
mt=[r for r in proj2 if r['row_type']=='ministry_total']
grand=[r for r in proj2 if r['row_type']=='grand_total']
print('\nrow_type counts: ministry_total={} grand_total={} total_rows={}'.format(len(mt),len(grand),len(proj2)))
# every ministry_total sebenar_jumlah == maksud
bad=0
for r in mt:
    mv=mak.get(r['maksud_code'])
    if mv is None: print('NO maksud',r['maksud_code']); bad+=1; continue
    a,b=num(r['sebenar_jumlah_rm']),num(mv['sebenar_jumlah_rm'])
    if a is None or b is None or abs(a-b)>0.01: print('sebenar DIFF',r['maksud_code'],r['sebenar_jumlah_rm'],mv['sebenar_jumlah_rm']); bad+=1
print('ministry_total sebenar_jumlah vs maksud diffs:',bad)
# no empty ministry_total sebenar
empt=[r['maksud_code'] for r in mt if r['sebenar_jumlah_rm'] in ('',None)]
print('empty ministry_total sebenar:',empt)
# residual (genuine) gap
ssum=sum(num(r['sebenar_jumlah_rm']) or 0 for r in mt)
gv=num(grand[0]['sebenar_jumlah_rm'])
print('sum ministry_total sebenar_jumlah={:,.2f} grand={:,.2f} residual(genuine reorg/transfer)={:,.2f}'.format(ssum,gv,ssum-gv))
print('pindah_rm remaining nonblank:',sum(1 for r in proj2 if r['pindah_rm'] not in ('',None)))
