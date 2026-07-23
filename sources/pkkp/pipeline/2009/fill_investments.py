import csv, json, re
DASH={'–','-','—','−'}
def amtf(t):
    if t is None: return None
    if t in DASH: return 0.0
    neg=t.startswith('(') and t.endswith(')')
    v=float(t.strip('()').replace(',',''))
    return -v if neg else v
def fmt(v):
    if v is None: return ''
    if v==int(v): return str(float(v))
    return repr(v)

coords=json.load(open('/tmp/inv_coords.json'))
det=[c for c in coords if (c['nb2009'] is not None or c['nominal_amt'] is not None)
     and not c['entity'].strip().startswith(('Jumlah','JUMLAH'))
     and not re.match(r'^\d+ \d+$', c['raw'].strip())]

wh=list(csv.DictReader(open('/home/claude/pkkp/warehouse2009/fact_investments.csv')))
LEAK=lambda r: r['entiti_bm'] in ('174','176','Dibayar') or r['nilai_buku_rm'] in ('2009.0','2008.0','174.0','176.0')
kept=[r for r in wh if not LEAK(r)]
removed=[r for r in wh if LEAK(r)]

whd=[r for r in kept if r['row_type']=='line' and r['year']=='2009']
assert len(whd)==len(det), (len(whd),len(det))

# strict document-order 1:1 alignment (verified: nb2009 matches for all 132)
for r,c in zip(whd,det):
    assert abs((amtf(r['nilai_buku_rm']) or 0)-(amtf(c['nb2009']) if c['nb2009'] is not None else 0))<0.01
    r['modal_saham_amt']=fmt(amtf(c['modal_amt'])) if c['modal_amt'] is not None else ''
    r['modal_saham_ccy']=c['modal_ccy'] or ''
    r['nilai_nominal_amt']=fmt(amtf(c['nominal_amt'])) if c['nominal_amt'] is not None else ''
    r['nilai_nominal_ccy']=c['nominal_ccy'] or ''

# reconciliation: grand total tie + detail populated
def val(pred):
    return [r for r in kept if pred(r)]
grand=[r for r in kept if r['row_type']=='total' and r['year']=='2009']
subt=[r for r in kept if r['row_type']=='subtotal' and r['year']=='2009']
pop_modal=sum(1 for r in whd if r['modal_saham_amt']!='')
pop_nom=sum(1 for r in whd if r['nilai_nominal_amt']!='')

hdr=list(wh[0].keys())
with open('/tmp/investments_fixed.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=hdr); w.writeheader(); w.writerows(kept)

print('removed leak rows:',len(removed),'-> kept:',len(kept))
print('2009 detail rows:',len(whd),'| modal populated:',pop_modal,'| nominal populated:',pop_nom)
print('GRAND JUMLAH PELABURAN 2009:',grand[0]['nilai_buku_rm'],'(expect 27751414083.29)')
for r in subt: print('  subtotal',r['entiti_bm'],r['nilai_buku_rm'])
print('WROTE /tmp/investments_fixed.csv rows',len(kept))
