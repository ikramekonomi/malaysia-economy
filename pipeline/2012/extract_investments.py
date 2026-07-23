#!/usr/bin/env python3
"""Extract Penyata Akaun Memorandum Pelaburan (Lampiran 4, pdf 266-269) -> fact_investments.csv.

2016 frame calibration: page 266's '%' header at x0=441.1; other pages shifted
slightly, handled by dx from each page's own '%' header. Grain = one printed
share-class line x year (2016/2015 book values).
"""
import re
import pdfplumber
import pandas as pd

WORK = '/home/claude/pkkp/work/2014'
WH = '/home/claude/pkkp/warehouse2014'
SRC = '2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
STMT = 'Penyata Akaun Memorandum Pelaburan'
PAGES = {282: 257, 283: 258, 284: 259, 285: 260}
SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
AMT = re.compile(r'^[\d,]+\.\d{2}$')
CCY = re.compile(r'^[A-Z]{3}$|^Baht$')
FN = re.compile(r'^\((\d)\)$')
DASH = '–'

def amt(tok):
    if tok is None:
        return None
    if tok in (DASH, '-'):
        return 0.0
    return float(tok.replace(',', ''))

def group_lines(words, gap=3.0):
    words = sorted(words, key=lambda w: (w['top'], w['x0']))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur and w['top'] - cur_top > gap:
            lines.append(sorted(cur, key=lambda x: x['x0']))
            cur = []
        cur.append(w)
        cur_top = w['top'] if cur_top is None or len(cur) == 1 else max(cur_top, w['top'])
    if cur:
        lines.append(sorted(cur, key=lambda x: x['x0']))
    return lines

def classify(w, dx):
    """Zone for a word given page x-shift dx (zones in the 2016 page-266 frame)."""
    x0, x1, t = w['x0'] - dx, w['x1'] - dx, w['text']
    if x1 <= 255:
        if AMT.match(t) and x1 > 195:
            return 'modal_amt'
        if CCY.match(t) and x0 > 150:
            return 'modal_ccy'
        if t == DASH and x0 > 195:
            return 'modal_dash'
        return 'entity'
    if x0 < 358:
        return 'perihal'
    if x1 <= 432:
        return 'nominal_ccy' if CCY.match(t) else 'nominal'
    if x1 <= 456:
        return 'pct'
    if x1 <= 512:
        return 'nb2014'
    return 'nb2013'

records = []
section = None
cur_entity = None

pdf = pdfplumber.open(f'{WORK}/2014.pdf')
for pno, pp in PAGES.items():
    page = pdf.pages[pno - 1]
    words = [w for w in page.extract_words(keep_blank_chars=False)
             if w.get('upright', True) and w['x0'] >= 0 and w['x1'] <= page.width + 5]
    pct_hdr = [w for w in words if w['text'].rstrip('!') == '%' and w['top'] < 260]
    dx = pct_hdr[0]['x0'] - 441.1
    body = [w for w in words if 185 < w['top'] < 825
            and not (re.fullmatch(r'\d{1,3}', w['text']) and (w['x0'] - dx > 565 or w['x0'] < 70))
            and w['text'] != '$10']
    lines = group_lines(body)
    in_nota = False
    for ln in lines:
        texts = [w['text'] for w in ln]
        joined = ' '.join(texts).replace('!', '')
        if joined.startswith('Nota'):
            in_nota = True
        if in_nota:
            continue
        if set(t.strip('!') for t in texts) <= {'RM', '%', ''}:
            continue
        if joined.startswith(('(disambung', '(sambungan', 'LAMPIRAN', 'Teks ', 'Penyata Akaun', 'pada 31')) \
           or re.match(r'^\d+\. LAMPIRAN', joined) or re.match(r'^\d+$', joined) \
           or 'PENYATA KEWANGAN KERAJAAN PERSEKUTUAN' in joined:
            continue
        zones = {}
        for w in ln:
            if w['text'].strip('!') == '':
                continue
            wt = dict(w)
            wt['text'] = w['text'].replace('!', '') or w['text']
            zones.setdefault(classify(wt, dx), []).append(wt['text'])
        ent_words = [t for t in zones.get('entity', []) if not FN.match(t)]
        fns = [FN.match(t).group(1) for t in zones.get('entity', []) if FN.match(t)]
        ent_txt = ' '.join(ent_words)
        has_values = any(z in zones for z in ('nominal', 'pct', 'nb2014', 'nb2013'))
        norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()
        if norm in SECTIONS and not has_values and not zones.get('perihal'):
            section = norm
            cur_entity = None
            continue
        if not has_values:
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
            if fns and cur_entity is not None:
                cur_entity['fns'] += fns
            if zones.get('perihal') and records and 'perihal' in records[-1]:
                records[-1]['perihal'] += ' ' + ' '.join(zones['perihal'])
            continue
        if ent_txt.startswith(('Jumlah', 'JUMLAH')):
            records.append(dict(section=section, kind='agg', label=ent_txt,
                                nb2014=zones.get('nb2014', [None])[0],
                                nb2013=zones.get('nb2013', [None])[0],
                                pdf_page=pno, printed_page=pp))
            cur_entity = None
            continue
        if zones.get('modal_amt') or zones.get('modal_dash'):
            cur_entity = dict(name=ent_txt, fns=fns,
                              modal_ccy=zones.get('modal_ccy', ['RM'])[0],
                              modal=(zones.get('modal_amt', [None])[0]
                                     or (DASH if zones.get('modal_dash') else None)),
                              rows=[])
        else:
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
            if fns and cur_entity is not None:
                cur_entity['fns'] += fns
        rec = dict(section=section, kind='detail', entity=cur_entity,
                   perihal=' '.join(zones.get('perihal', [])),
                   nominal_ccy=zones.get('nominal_ccy', [None])[0],
                   nominal=zones.get('nominal', [None])[0],
                   pct=zones.get('pct', [None])[0],
                   nb2014=zones.get('nb2014', [None])[0],
                   nb2013=zones.get('nb2013', [None])[0],
                   pdf_page=pno, printed_page=pp)
        records.append(rec)
        cur_entity['rows'].append(rec)

seen = set()
for r in records:
    e = r.get('entity')
    if e is None or id(e) in seen:
        continue
    seen.add(id(e))
    m = re.search(r'\s*\((\d)\)$', e['name'])
    if m:
        e['name'] = e['name'][:m.start()]
        e['fns'].append(m.group(1))
    m = re.search(r'(\*+)$', e['name'])
    if m:
        e['name'] = e['name'][:m.start()].rstrip()
        e['fns'].append(m.group(1))

rows = []
for r in records:
    if r['kind'] == 'agg':
        rt = 'total' if r['label'].startswith('JUMLAH') else 'subtotal'
        base = dict(section_bm=r['section'] if rt == 'subtotal' else None,
                    entiti_bm=r['label'], perihal=None, modal_saham_ccy=None,
                    modal_saham_amt=None, nilai_nominal_ccy=None, nilai_nominal_amt=None,
                    pegangan_pct=None, row_type=rt, has_footnote=False, footnote_ref=None)
    else:
        e = r['entity']
        nom_ccy = r['nominal_ccy'] or ('RM' if r['nominal'] else None)
        base = dict(section_bm=r['section'], entiti_bm=e['name'], perihal=r['perihal'],
                    modal_saham_ccy=e['modal_ccy'] if e['modal'] else None,
                    modal_saham_amt=amt(e['modal']),
                    nilai_nominal_ccy=nom_ccy if (r['nominal'] and r['nominal'] != DASH) else None,
                    nilai_nominal_amt=amt(r['nominal']),
                    pegangan_pct=amt(r['pct']) if r['pct'] not in (DASH, '-', None) else None,
                    row_type='detail',
                    has_footnote=bool(e['fns']),
                    footnote_ref=','.join(e['fns']) if e['fns'] else None)
    for y, nb in ((2014, r["nb2014"]), (2013, r["nb2013"])):
        rows.append(dict(base, year=y, nilai_buku_rm=amt(nb),
                         source_file=SRC, pdf_page=r['pdf_page'],
                         printed_page=r['printed_page'], statement=STMT))

df = pd.DataFrame(rows)
df['footnote_ref'] = df['footnote_ref'].astype('string')
df.to_csv(f'{WH}/fact_investments.csv', index=False)
print('investments rows:', len(df))
print('entities:', df[df.row_type == "detail"].entiti_bm.nunique())
print(df[df.row_type != 'detail'][['section_bm', 'entiti_bm', 'year', 'nilai_buku_rm']].to_string())
