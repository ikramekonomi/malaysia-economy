#!/usr/bin/env python3
"""Extract Penyata Akaun Memorandum Pelaburan (Lampiran 4, pdf 221-224) -> fact_investments.csv.

Uses pdfplumber word coordinates (2019 frame; page x-shift calibrated on the '%'
column header at x0=448.3). Grain of output = one printed share-class line x year.
2019 notes: '*'..'****' footnote markers are glued to entity names; the separate
share-count column is prepended to the perihal text ('1,000,000,000 saham biasa
RM1.00'); off-page spread ghosts and the rotated sidebar are filtered out."""
import re
import pdfplumber
import pandas as pd

WORK = '/home/claude/pkkp/work/2019'
WH = '/home/claude/pkkp/warehouse2019'
SRC = '2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
STMT = 'Penyata Akaun Memorandum Pelaburan'
PAGES = {221: 209, 222: 210, 223: 211, 224: 212}
SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
AMT = re.compile(r'^[\d,]+\.\d{2}$')
COUNT = re.compile(r'^[\d,]+$')
CCY = re.compile(r'^[A-Z]{3}$|^Baht$')
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
    x0, x1, t = w['x0'] - dx, w['x1'] - dx, w['text']
    if x1 <= 202:
        return 'entity'
    if x1 <= 270:
        if CCY.match(t):
            return 'modal_ccy'
        if AMT.match(t):
            return 'modal_amt'
        if t == DASH:
            return 'modal_dash'
        return 'entity'
    if x1 <= 318:
        if COUNT.match(t):
            return 'count'
        return 'perihal'
    if x0 < 370:
        return 'perihal'
    if x1 <= 440:
        return 'nominal_ccy' if CCY.match(t) else 'nominal'
    if x1 <= 465:
        return 'pct'
    if x1 <= 517:
        return 'nb2020'
    return 'nb2019'

records = []
section = None
cur_entity = None

pdf = pdfplumber.open(f'{WORK}/2019.pdf')
for pno, pp in PAGES.items():
    page = pdf.pages[pno - 1]
    words = [w for w in page.extract_words(keep_blank_chars=False)
             if w['x0'] >= 0 and w['x1'] <= page.width and w.get('upright', True)]
    pct_hdr = [w for w in words if w['text'] == '%' and w['top'] < 200]
    dx = pct_hdr[0]['x0'] - 448.3
    body = [w for w in words if 185 < w["top"] < 830]
    lines = group_lines(body)
    in_nota = False
    for ln in lines:
        texts = [w['text'] for w in ln]
        joined = ' '.join(texts)
        if joined.startswith('Nota'):
            in_nota = True
        if in_nota:
            continue
        if joined.startswith('(disambung') or joined.startswith('LAMPIRAN') \
           or joined.startswith('Teks ') or re.match(r'^\d+$', joined) \
           or joined.startswith('PENYATA KEWANGAN') or joined.startswith('6. Teks'):
            continue
        if all(t in ('RM', '%') for t in texts):
            continue    # units header row
        zones = {}
        for w in ln:
            t = w['text']
            m = re.match(r'^([A-Z][A-Za-z]{2,3})([\d,]+\.\d{2})$', t)
            if m and classify(w, dx) in ('entity', 'modal_amt'):
                # ccy glued to the modal amount ('USD19,566,717,000.00', 'Baht...')
                zones.setdefault('modal_ccy', []).append(m.group(1))
                zones.setdefault('modal_amt', []).append(m.group(2))
                continue
            zones.setdefault(classify(w, dx), []).append(t)
        ent_txt = ' '.join(zones.get('entity', []))
        has_values = any(z in zones for z in ('nominal', 'pct', 'nb2020', 'nb2019'))
        norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()
        if norm in SECTIONS and not has_values and not zones.get('perihal'):
            section = norm
            cur_entity = None
            continue
        if not has_values:
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
            if zones.get('perihal') and records:
                records[-1]['perihal'] += ' ' + ' '.join(zones['perihal'])
            continue
        if ent_txt.startswith(('Jumlah', 'JUMLAH')):
            records.append(dict(section=section, kind='agg', label=ent_txt,
                                nb2020=zones.get('nb2020', [None])[0],
                                nb2019=zones.get('nb2019', [None])[0],
                                pdf_page=pno, printed_page=pp))
            cur_entity = None
            continue
        if zones.get('modal_amt') or zones.get('modal_dash'):
            cur_entity = dict(name=ent_txt, fns=[],
                              modal_ccy=zones.get('modal_ccy', ['RM'])[0],
                              modal=(zones.get('modal_amt', [None])[0]
                                     or (DASH if zones.get('modal_dash') else None)),
                              rows=[])
        else:
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
        perihal = ' '.join(zones.get('count', []) + zones.get('perihal', []))
        rec = dict(section=section, kind='detail', entity=cur_entity,
                   perihal=perihal,
                   nominal_ccy=zones.get('nominal_ccy', [None])[0],
                   nominal=zones.get('nominal', [None])[0],
                   pct=zones.get('pct', [None])[0],
                   nb2020=zones.get('nb2020', [None])[0],
                   nb2019=zones.get('nb2019', [None])[0],
                   pdf_page=pno, printed_page=pp)
        if cur_entity is None:
            print(f'skip header/orphan value line p{pno}:', joined[:90])
            records.pop() if records and records[-1] is rec else None
            continue
        records.append(rec)
        cur_entity['rows'].append(rec)

# strip footnote markers glued to entity names
seen = set()
for r in records:
    e = r.get('entity')
    if e is None or id(e) in seen:
        continue
    seen.add(id(e))
    m = re.search(r'(\*+)\s*$', e['name'])
    if m:
        e['name'] = e['name'][:m.start()].rstrip()
        e['fns'].append(m.group(1))
    else:
        m2 = re.search(r'(\*+)(\s|$)', e['name'])
        if m2:
            e['name'] = (e['name'][:m2.start()] + ' ' + e['name'][m2.end():]).strip()
            e['fns'].append(m2.group(1))

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
                    pegangan_pct=amt(r['pct']),
                    row_type='detail',
                    has_footnote=bool(e['fns']),
                    footnote_ref=','.join(e['fns']) if e['fns'] else None)
    for y, nb in ((2019, r['nb2020']), (2018, r['nb2019'])):
        rows.append(dict(base, year=y, nilai_buku_rm=amt(nb),
                         source_file=SRC, pdf_page=r['pdf_page'],
                         printed_page=r['printed_page'], statement=STMT))

df = pd.DataFrame(rows)
df['footnote_ref'] = df['footnote_ref'].astype('string')
df.to_csv(f'{WH}/fact_investments.csv', index=False)
print('investments rows:', len(df))
print('entities:', df[df.row_type == "detail"].entiti_bm.nunique())
print(df[df.row_type != 'detail'][['section_bm', 'entiti_bm', 'year', 'nilai_buku_rm']].to_string())
