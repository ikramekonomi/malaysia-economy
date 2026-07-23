import csv, os
W9="/home/claude/pkkp/warehouse2009"; W10="/home/claude/pkkp/warehouse2010"
def rd(w,f): 
    p=os.path.join(w,f)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []
out=[]  # table,key,v9vol,v10vol,diff,note
def num(x):
    try: return float(x)
    except: return None
# financial_position: key=line_item_bm (2009)
a={r['line_item_bm']:num(r['amount_rm']) for r in rd(W9,'fact_financial_position.csv') if r['year']=='2009'}
b={r['line_item_bm']:num(r['amount_rm']) for r in rd(W10,'fact_financial_position.csv') if r['year']=='2009'}
for k in sorted(set(a)&set(b)):
    if a[k] is None or b[k] is None: continue
    d=round(a[k]-b[k],2)
    out.append(['fact_financial_position',k,a[k],b[k],d,'match' if abs(d)<1 else 'RESTATED/diff'])
# cash_statement: key=item_bm (2009)
a2={}; 
for r in rd(W9,'fact_cash_statement.csv'):
    if r['year']=='2009': a2[r['item_bm']]=num(r['amount_rm'])
b2={}
for r in rd(W10,'fact_cash_statement.csv'):
    if r['year']=='2009':
        k=r.get('item_bm') or r.get('line_item_bm')
        b2[k]=num(r['amount_rm'])
for k in sorted(set(a2)&set(b2)):
    if a2[k] is None or b2[k] is None: continue
    # compare magnitudes (2009 vol keeps BAYARAN negative; 2010 vol positive) to isolate true restatements
    d=round(abs(a2[k])-abs(b2[k]),2)
    note='match' if abs(d)<1 else 'RESTATED/reclassified'
    out.append(['fact_cash_statement',k,a2[k],b2[k],d,note])
with open(os.path.join(W9,'_restatements_2009_vs_2010volume.csv'),'w',newline='') as f:
    w=csv.writer(f); w.writerow(['table','key','value_2009_volume','value_2010_volume','difference','note']); w.writerows(out)
n=len(out); r=sum(1 for x in out if x[5]!='match')
print(f"restatement rows:{n} matches:{n-r} restated/diff:{r}")
for x in out:
    if x[5]!='match': print("  DIFF:",x[:5])
