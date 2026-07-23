import re, csv, os
SRC="2009_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
WH="/home/claude/pkkp/warehouse2009"
FULL="/home/claude/pkkp/work/2009/full.txt"

_pages=None
def pages():
    global _pages
    if _pages is None:
        _pages=open(FULL,encoding='utf-8',errors='replace').read().split('\f')
    return _pages

def page(pdf):  # 1-based pdf page -> text
    return pages()[pdf-1]

def lines(pdf):
    return [l for l in page(pdf).split('\n')]

_indd=re.compile(r'\.indd\s+(\d+)')
def printed_of(pdf):
    m=_indd.search(page(pdf))
    return int(m.group(1)) if m else None

NUM=re.compile(r'^\(?\*{0,2}-?[\d,]+(?:\.\d+)?\)?\*{0,2}$')
def parse_num(tok):
    """Return (value_float_or_None, has_footnote). '–' -> 0.0. () -> negative. * -> footnote."""
    if tok is None: return (None,False)
    t=tok.strip()
    if t in ('','\t'): return (None,False)
    if t in ('–','-','—','−'): return (0.0,False)
    fn = '*' in t
    t=t.replace('*','').strip()
    neg = t.startswith('(') and t.endswith(')')
    t=t.strip('()').strip()
    if t in ('–','-','—','−',''): return (0.0,fn)
    t=t.replace(',','')
    try:
        v=float(t)
    except ValueError:
        return (None,fn)
    if neg: v=-v
    return (v,fn)

def fmt(v):
    if v is None: return ''
    if v==int(v): return str(float(v))  # e.g. 123.0
    return repr(v)

def write_csv(name, header, rows):
    path=os.path.join(WH,name)
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(header)
        for r in rows: w.writerow(r)
    print(f"WROTE {name}: {len(rows)} rows")
    return path

# find all number tokens (with commas, parens, asterisks) in a line, in order
TOKS=re.compile(r'\(?\*{0,2}-?[\d][\d,]*(?:\.\d+)?\)?\*{0,2}|–')
def numtokens(line):
    return TOKS.findall(line)
