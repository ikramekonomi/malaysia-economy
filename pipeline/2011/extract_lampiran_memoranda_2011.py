#!/usr/bin/env python3
"""Extract Lampiran 3/4/5 memorandum registers from PKKP FY2011.

Outputs to /home/claude/pkkp/warehouse2011/:
  fact_loans_receivable.csv        Lampiran 3  pdf 251-253  printed 233-235
  fact_investments.csv             Lampiran 4  pdf 257-260  printed 239-242
  fact_statutory_guarantees.csv    Lampiran 5  pdf 263      printed 245

printed_page = pdf_page - 18.  One row per item (year=2011); 2010 comparative dropped.
Conventions: exact RM incl sen; en-dash -> 0.0; parens -> negative.
"""
import re
import csv
import pandas as pd
import pdfplumber

WORK = '/home/claude/pkkp/work/2011'
WH = '/home/claude/pkkp/warehouse2011'
SRC = '2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2011

pages = open(f'{WORK}/full.txt').read().split('\f')
_pdf = pdfplumber.open(f'{WORK}/2011.pdf')

DASH = '–'
AMT = re.compile(r'^\(?[\d,]+\.\d{2}\)?$')          # money w/ sen, opt parens
AMT_INT = re.compile(r'^\(?\d{1,3}(?:,\d{3})+\)?$')  # integer w/ thousands

LIG = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}


def deligature(s):
    for k, v in LIG.items():
        s = s.replace(k, v)
    return s


def is_val(tok):
    return tok in (DASH, '-', '—') or AMT.match(tok) or AMT_INT.match(tok)


def amt(tok):
    if tok is None or tok == '':
        return None
    if tok in (DASH, '-', '—'):
        return 0.0
    neg = tok.startswith('(') and tok.endswith(')')
    v = float(tok.strip('()').replace(',', ''))
    return -v if neg else v


def prov(row, pno, pp, stmt):
    row['source_file'] = SRC
    row['pdf_page'] = pno
    row['printed_page'] = pp
    row['statement'] = stmt
    return row


def raw_page_lines(pno):
    """Clean text lines from full.txt for a page (headers/footers stripped)."""
    out = []
    for ln in pages[pno - 1].split('\n'):
        s = deligature(ln.replace('!', '')).rstrip()
        st = s.strip()
        if not st:
            continue
        if '.indd' in st:
            continue
        if re.match(r'^Penyata Akaun Memorandum', st):
            continue
        if re.match(r'^[Pp]ada 31 Disember', st):
            continue
        if re.match(r'^\(disambung', st) or re.match(r'^\(sambungan', st):
            continue
        if re.fullmatch(r'\d{1,3}', st):
            continue
        out.append(st)
    return out


def split_label_vals(line):
    toks = line.split()
    vals = []
    while toks and is_val(toks[-1]):
        vals.insert(0, toks.pop())
    return ' '.join(toks), vals


# ===========================================================================
# 1. Lampiran 3 : Pinjaman Boleh Dituntut  (pdf 251-253)
# ===========================================================================
def extract_loans():
    stmt = 'Penyata Akaun Memorandum Pinjaman Boleh Dituntut'
    pageinfo = {251: 233, 252: 234, 253: 235}
    HDR = re.compile(r'^(Peminjam|Baki Pinjaman Mengikut|Pembangunan\b|Hasil Disatukan\b|'
                     r'Baki Belum Selesai|RM(\s+RM)*$|2011\s+2010$)')
    rows = []
    cat_no = cat = None
    for pno, pp in pageinfo.items():
        for st in raw_page_lines(pno):
            if HDR.match(st):
                continue
            m = re.match(r'^([IVX]+)\.\s+(.*)$', st)
            if m:
                cat_no = m.group(1)
                cat = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', m.group(2), flags=re.I).strip()
                continue
            label, vals = split_label_vals(st)
            if not vals:
                if rows and rows[-1]['row_type'] == 'detail':
                    rows[-1]['peminjam_bm'] += ' ' + label
                continue
            if len(vals) != 5:
                raise ValueError(f'loans p{pno} vals={len(vals)}: {st!r}')
            label = label.replace('*', '').strip()
            if label == 'JUMLAH PINJAMAN BOLEH DITUNTUT':
                rt, sec, cn, cb = 'total', None, None, None
            elif label.startswith('Jumlah '):
                rt, sec, cn, cb = 'subtotal', 'PINJAMAN', cat_no, cat
            else:
                rt, sec, cn, cb = 'detail', 'PINJAMAN', cat_no, cat
            rows.append(prov(dict(
                section_bm=sec, category_no=cn, category_bm=cb, peminjam_bm=label,
                row_type=rt, year=YEAR,
                pembangunan_rm=amt(vals[0]), hasil_disatukan_rm=amt(vals[1]),
                amanah_lain_rm=amt(vals[2]), baki_belum_selesai_rm=amt(vals[3])),
                pno, pp, stmt))
    df = pd.DataFrame(rows, columns=[
        'section_bm', 'category_no', 'category_bm', 'peminjam_bm', 'row_type', 'year',
        'pembangunan_rm', 'hasil_disatukan_rm', 'amanah_lain_rm', 'baki_belum_selesai_rm',
        'source_file', 'pdf_page', 'printed_page', 'statement'])
    df.to_csv(f'{WH}/fact_loans_receivable.csv', index=False)
    return df


# ===========================================================================
# 3. Lampiran 5 : Jaminan Berkanun  (pdf 263) -- single page, 2-up doubled
# ===========================================================================
def extract_statutory():
    stmt = 'Penyata Akaun Memorandum Jaminan Berkanun'
    pno, pp = 263, 245
    CATS = ('BADAN BERKANUN', 'SYARIKAT')
    HDR = re.compile(r'^(Penyata|Peminjam|Dalam Negeri|Luar Negeri|Jumlah$|Jaminan Berkanun$|'
                     r'Akaun Memorandum|2011\s+2010$|RM(\s+RM)*$|\d{1,3}(\s+\d{1,3})*$)')
    rows = []
    kategori = None
    prev = None
    for st in raw_page_lines(pno):
        if HDR.match(st):
            continue
        label, vals = split_label_vals(st)
        sig = (label, tuple(vals))
        if sig == prev:            # dedup the 2-up doubled line
            continue
        prev = sig
        if not vals:
            if label in CATS:
                kategori = label
            elif rows and rows[-1]['row_type'] == 'detail':
                rows[-1]['agensi_bm'] += ' ' + label
            continue
        if len(vals) != 4:
            raise ValueError(f'guar p{pno} vals={len(vals)}: {st!r}')
        if label == 'JUMLAH JAMINAN':
            rt, kat = 'total', None
        elif label.startswith('Jumlah '):
            rt, kat = 'subtotal', kategori
        else:
            rt, kat = 'detail', kategori
        rows.append(prov(dict(
            jenis_jaminan_bm=None, kategori_bm=kat, agensi_bm=label, row_type=rt, year=YEAR,
            dalam_negeri_rm=amt(vals[0]), luar_negeri_rm=amt(vals[1]),
            jumlah_rm=amt(vals[2])), pno, pp, stmt))
    df = pd.DataFrame(rows, columns=[
        'jenis_jaminan_bm', 'kategori_bm', 'agensi_bm', 'row_type', 'year',
        'dalam_negeri_rm', 'luar_negeri_rm', 'jumlah_rm',
        'source_file', 'pdf_page', 'printed_page', 'statement'])
    df.to_csv(f'{WH}/fact_statutory_guarantees.csv', index=False)
    return df


# ===========================================================================
# 2. Lampiran 4 : Pelaburan  (pdf 257-260)  -- pdfplumber x-zone parse
# ===========================================================================
def extract_investments():
    stmt = 'Penyata Akaun Memorandum Pelaburan'
    PAGES = {257: 239, 258: 240, 259: 241, 260: 242}
    SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
    IAMT = re.compile(r'^[\d,]+\.\d{2}$')
    CCY = re.compile(r'^(USD|Baht|RM)$')
    CCYAMT = re.compile(r'^(USD|Baht|RM)([\d,]+\.\d{2})$')
    FN = re.compile(r'^\((\d)\)$')

    def iamt(tok):
        if tok is None:
            return None
        if tok in (DASH, '-'):
            return 0.0
        return float(tok.replace(',', ''))

    def zone_of(w):
        x0, x1 = w['x0'], w['x1']
        if x1 <= 185:
            return 'entity'
        if x1 <= 255:
            return 'modal'
        if x0 < 361:
            return 'perihal'
        if x1 <= 430:
            return 'nominal'
        if x1 <= 452:
            return 'pct'
        if x1 <= 510:
            return 'nb2011'
        return 'nb2010'

    def group_lines(words, gap=3.0):
        words = sorted(words, key=lambda w: (w['top'], w['x0']))
        lines, cur, cur_top = [], [], None
        for w in words:
            if cur and w['top'] - cur_top > gap:
                lines.append(sorted(cur, key=lambda x: x['x0']))
                cur = []
            if not cur:
                cur_top = w['top']
            cur.append(w)
        if cur:
            lines.append(sorted(cur, key=lambda x: x['x0']))
        return lines

    records = []
    section = None
    cur_entity = None
    for pno, pp in PAGES.items():
        page = _pdf.pages[pno - 1]
        words = []
        for w in page.extract_words(keep_blank_chars=False):
            if not w.get('upright', True):
                continue
            if w['x0'] < 0 or w['x1'] > page.width + 5:
                continue
            t = deligature(w['text'].replace('!', ''))
            if t == '':
                continue
            if 165 < w['top'] < 815:
                words.append(dict(w, text=t))
        for ln in group_lines(words):
            texts = [w['text'] for w in ln]
            joined = ' '.join(texts)
            # strip bare folio-only lines
            if re.fullmatch(r'\d{1,3}', joined.strip()):
                continue
            zones = {}
            for w in ln:
                z = zone_of(w)
                t = w['text']
                if z == 'modal':
                    m = CCYAMT.match(t)
                    if m:
                        zones.setdefault('modal_ccy', []).append(m.group(1))
                        zones.setdefault('modal_amt', []).append(m.group(2))
                    elif CCY.match(t):
                        zones.setdefault('modal_ccy', []).append(t)
                    elif t == DASH:
                        zones['modal_dash'] = True
                    elif IAMT.match(t):
                        zones.setdefault('modal_amt', []).append(t)
                    else:
                        zones.setdefault('entity', []).append(t)
                elif z == 'nominal':
                    m = CCYAMT.match(t)
                    if m:
                        zones.setdefault('nominal_ccy', []).append(m.group(1))
                        zones.setdefault('nominal_amt', []).append(m.group(2))
                    elif CCY.match(t):
                        zones.setdefault('nominal_ccy', []).append(t)
                    elif t == DASH:
                        zones.setdefault('nominal_amt', []).append(DASH)
                    elif IAMT.match(t):
                        zones.setdefault('nominal_amt', []).append(t)
                    else:
                        zones.setdefault('perihal', []).append(t)
                else:
                    zones.setdefault(z, []).append(t)

            ent_words = [t for t in zones.get('entity', []) if not FN.match(t)]
            fns = [FN.match(t).group(1) for t in zones.get('entity', []) if FN.match(t)]
            ent_txt = ' '.join(ent_words)
            has_values = any(z in zones for z in ('nominal_amt', 'pct', 'nb2011', 'nb2010'))
            norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()

            if norm in SECTIONS and not has_values and not zones.get('perihal') \
               and not zones.get('modal_amt'):
                section = norm
                cur_entity = None
                continue
            if not has_values:
                if ent_txt and cur_entity is not None:
                    cur_entity['name'] += ' ' + ent_txt
                if fns and cur_entity is not None:
                    cur_entity['fns'] += fns
                if zones.get('perihal') and records and records[-1].get('kind') == 'detail':
                    records[-1]['perihal'] = (records[-1]['perihal'] + ' '
                                              + ' '.join(zones['perihal'])).strip()
                continue
            if ent_txt.startswith(('Jumlah', 'JUMLAH')):
                records.append(dict(section=section, kind='agg', label=ent_txt,
                                    nb2011=zones.get('nb2011', [None])[0],
                                    pdf_page=pno, printed_page=pp))
                cur_entity = None
                continue
            if zones.get('modal_amt') or zones.get('modal_dash'):
                cur_entity = dict(name=ent_txt, fns=fns,
                                  modal_ccy=zones.get('modal_ccy', ['RM'])[0],
                                  modal=(zones.get('modal_amt', [None])[0]
                                         or (DASH if zones.get('modal_dash') else None)))
            else:
                if ent_txt and cur_entity is not None:
                    cur_entity['name'] += ' ' + ent_txt
                if fns and cur_entity is not None:
                    cur_entity['fns'] += fns
            records.append(dict(section=section, kind='detail', entity=cur_entity,
                                perihal=' '.join(zones.get('perihal', [])),
                                nominal_ccy=zones.get('nominal_ccy', [None])[0],
                                nominal=zones.get('nominal_amt', [None])[0],
                                pct=zones.get('pct', [None])[0],
                                nb2011=zones.get('nb2011', [None])[0],
                                pdf_page=pno, printed_page=pp))

    # normalise trailing footnote markers on entity names
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
            perihal = re.sub(r'(\d)(syer|saham)', r'\1 \2', r['perihal']).strip()
            nom_ccy = r['nominal_ccy'] or ('RM' if r['nominal'] and r['nominal'] != DASH else None)
            base = dict(section_bm=r['section'],
                        entiti_bm=e['name'] if e else None,
                        perihal=perihal or None,
                        modal_saham_ccy=(e['modal_ccy'] if e and e['modal'] else None),
                        modal_saham_amt=iamt(e['modal']) if e else None,
                        nilai_nominal_ccy=nom_ccy if (r['nominal'] and r['nominal'] != DASH) else None,
                        nilai_nominal_amt=iamt(r['nominal']),
                        pegangan_pct=iamt(r['pct']) if r['pct'] not in (DASH, '-', None) else None,
                        row_type='detail',
                        has_footnote=bool(e['fns']) if e else False,
                        footnote_ref=','.join(e['fns']) if e and e['fns'] else None)
        rows.append(prov(dict(base, year=YEAR, nilai_buku_rm=iamt(r['nb2011'])),
                         r['pdf_page'], r['printed_page'], stmt))
    df = pd.DataFrame(rows, columns=[
        'section_bm', 'entiti_bm', 'perihal', 'modal_saham_ccy', 'modal_saham_amt',
        'nilai_nominal_ccy', 'nilai_nominal_amt', 'pegangan_pct', 'row_type',
        'has_footnote', 'footnote_ref', 'year', 'nilai_buku_rm',
        'source_file', 'pdf_page', 'printed_page', 'statement'])
    df['footnote_ref'] = df['footnote_ref'].astype('string')
    df.to_csv(f'{WH}/fact_investments.csv', index=False)
    return df


if __name__ == '__main__':
    dl = extract_loans();        print('loans_receivable rows:', len(dl))
    dg = extract_statutory();    print('statutory_guarantees rows:', len(dg))
    di = extract_investments();  print('investments rows:', len(di))
