#!/usr/bin/env python3
"""Extract Penyata Akaun Memorandum Pelaburan (Lampiran 4, pdf 248-251) -> fact_investments.csv.

Uses pdfplumber word coordinates: the table has wrapped entity names, wrapped share-class
descriptions (Perihal), currency prefixes (USD/THB) and superscript footnote markers, so the
text layer alone is ambiguous. Grain of output = one printed share-class line x year.
"""
import re
import pdfplumber
import pandas as pd

WORK = '/home/claude/pkkp/work'
WH = '/home/claude/pkkp/warehouse'
SRC = '2024_Penyata_Kewangan_Kerajaan_Persekutuan.pdf'
STMT = 'Penyata Akaun Memorandum Pelaburan'
PAGES = {248: 234, 249: 235, 250: 236, 251: 237}
SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
AMT = re.compile(r'^[\d,]+\.\d{2}$')
CCY = re.compile(r'^[A-Z]{3}$')
FN = re.compile(r'^\((\d)\)$')
DASH = '–'

def amt(tok):
    if tok is None:
        return None
    if tok == DASH:
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
    """Zone for a word given page x-shift dx (zones in page-248 frame)."""
    x0, x1, t = w['x0'] - dx, w['x1'] - dx, w['text']
    if x1 <= 262:
        if AMT.match(t) and x1 > 210:
            return 'modal_amt'
        if CCY.match(t) and x0 > 185:
            return 'modal_ccy'
        if t == DASH and x0 > 185:
            return 'modal_dash'
        return 'entity'
    if x0 < 366:
        return 'perihal'
    if x1 <= 435:
        return 'nominal_ccy' if CCY.match(t) else 'nominal'
    if x1 <= 462:
        return 'pct'
    if x1 <= 522:
        return 'nb2024'
    return 'nb2023'

records = []   # each: dict per printed share-class line
section = None
entities = []  # (entity_index) records grouped: track current entity dict
cur_entity = None

pdf = pdfplumber.open(f'{WORK}/2024.pdf')
for pno, pp in PAGES.items():
    page = pdf.pages[pno - 1]
    words = page.extract_words(keep_blank_chars=False)
    # page x-shift from '%' header position (443.0 on page 248)
    pct_hdr = [w for w in words if w['text'] == '%' and w['top'] < 200]
    dx = pct_hdr[0]['x0'] - 443.0
    # drop header/footer words
    body = [w for w in words if 160 < w['top'] < 830]
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
           or joined.startswith('WJD25') or re.match(r'^\d+$', joined):
            continue
        zones = {}
        for w in ln:
            zones.setdefault(classify(w, dx), []).append(w['text'])
        ent_words = [t for t in zones.get('entity', []) if not FN.match(t)]
        fns = [FN.match(t).group(1) for t in zones.get('entity', []) if FN.match(t)]
        ent_txt = ' '.join(ent_words)
        has_values = any(z in zones for z in ('nominal', 'pct', 'nb2024', 'nb2023'))
        # section headers
        norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()
        if norm in SECTIONS and not has_values and not zones.get('perihal'):
            section = norm
            cur_entity = None
            continue
        if not has_values:
            # continuation line: entity words extend entity name, perihal words extend perihal
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
            if fns and cur_entity is not None:
                cur_entity['fns'] += fns
            if zones.get('perihal') and records:
                records[-1]['perihal'] += ' ' + ' '.join(zones['perihal'])
            continue
        # value-bearing line
        if ent_txt.startswith(('Jumlah', 'JUMLAH')):
            records.append(dict(section=section, kind='agg', label=ent_txt,
                                nb2024=zones.get('nb2024', [None])[0],
                                nb2023=zones.get('nb2023', [None])[0],
                                pdf_page=pno, printed_page=pp))
            cur_entity = None
            continue
        if zones.get('modal_amt') or zones.get('modal_dash'):
            # first share-class line of a new entity (every entity prints Modal Saham or a dash)
            cur_entity = dict(name=ent_txt, fns=fns,
                              modal_ccy=zones.get('modal_ccy', ['RM'])[0],
                              modal=(zones.get('modal_amt', [None])[0]
                                     or (DASH if zones.get('modal_dash') else None)),
                              rows=[])
        else:
            # further share class of current entity; entity-zone text is a name continuation
            if ent_txt and cur_entity is not None:
                cur_entity['name'] += ' ' + ent_txt
            if fns and cur_entity is not None:
                cur_entity['fns'] += fns
        rec = dict(section=section, kind='detail', entity=cur_entity,
                   perihal=' '.join(zones.get('perihal', [])),
                   nominal_ccy=zones.get('nominal_ccy', [None])[0],
                   nominal=zones.get('nominal', [None])[0],
                   pct=zones.get('pct', [None])[0],
                   nb2024=zones.get('nb2024', [None])[0],
                   nb2023=zones.get('nb2023', [None])[0],
                   pdf_page=pno, printed_page=pp)
        records.append(rec)
        cur_entity['rows'].append(rec)

# strip footnote markers that pdfplumber merged into the last word of an entity name
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
    for y, nb in ((2024, r['nb2024']), (2023, r['nb2023'])):
        rows.append(dict(base, year=y, nilai_buku_rm=amt(nb),
                         source_file=SRC, pdf_page=r['pdf_page'],
                         printed_page=r['printed_page'], statement=STMT))

df = pd.DataFrame(rows)
df['footnote_ref'] = df['footnote_ref'].astype('string')
df.to_csv(f'{WH}/fact_investments.csv', index=False)
print('investments rows:', len(df))
print('entities:', df[df.row_type == "detail"].entiti_bm.nunique())
print(df[df.row_type != 'detail'][['section_bm', 'entiti_bm', 'year', 'nilai_buku_rm']].to_string())
