#!/usr/bin/env python3
"""Extract Lampiran 3/4/5 memoranda and Lampiran I statistics panel for PKKP 2010.

Outputs to /home/claude/pkkp/warehouse2010/:
  fact_loans_receivable.csv       (Lampiran 3, pdf 228-230, printed 218-220)
  fact_investments.csv            (Lampiran 4, pdf 232-235, printed 222-225)
  fact_statutory_guarantees.csv   (Lampiran 5, pdf 238,      printed 228)
  fact_timeseries_2001_2010.csv   (Lampiran I, pdf 294-296,  printed 2-4)

Grain: one row per record at the CURRENT year (2010) for L3/L4/L5 (matching the
2012 warehouse output which keeps only the current year; the printed prior-year
2009 column is not emitted). Timeseries emits one row per (line_item, year) for
2001..2010.
"""
import re
import csv
import pdfplumber
import pandas as pd

WORK = '/home/claude/pkkp/work/2010'
WH = '/home/claude/pkkp/warehouse2010'
SRC = '2010_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2010

pages_txt = open(f'{WORK}/full.txt', encoding='utf-8', errors='replace').read().split('\f')
_pdf = pdfplumber.open(f'{WORK}/2010.pdf')

DASH = '–'
AMT = re.compile(r'^\(?[\d,]+\.\d{2}\)?$|^\(?\d{1,3}(?:,\d{3})+\)?$')
DIAG = []  # discrepancy log


def is_val(tok):
    return tok in (DASH, '-') or bool(AMT.match(tok))


def amt(tok):
    if tok is None or tok == '':
        return None
    if tok in (DASH, '-'):
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


# ---------------------------------------------------------------------------
# pdfplumber line grouping (shared by L3, L5)
# ---------------------------------------------------------------------------
def plumber_lines(pno):
    pg = _pdf.pages[pno - 1]
    ws = [w for w in pg.extract_words(x_tolerance=1.5, y_tolerance=2)
          if w.get('upright', True) and w['x0'] >= 0 and w['x1'] <= pg.width + 5
          and 0 <= w['top'] <= pg.height]
    ws = [w for w in ws if not (re.fullmatch(r'\d{1,3}', w['text'])
                                and (w['x0'] < 60 or w['x0'] > pg.width - 60))]
    rows_, cur, cur_top = [], [], None
    for wd in sorted(ws, key=lambda w: w['top']):
        if cur and wd['top'] - cur_top > 3.0:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd['top']
        cur.append(wd)
    if cur:
        rows_.append(cur)
    out = []
    for r in rows_:
        r = sorted(r, key=lambda x: x['x0'])
        merged = []
        for w in r:
            if merged and w['x0'] - merged[-1]['x1'] < 4.0 \
               and re.match(r'^[\d,().]+$', merged[-1]['text']) and re.match(r'^[\d,().]+$', w['text']):
                merged[-1] = dict(merged[-1], text=merged[-1]['text'] + w['text'], x1=w['x1'])
            else:
                merged.append(dict(w))
        out.append((merged, ' '.join(w['text'] for w in merged)))
    return out


SKIP = [
    re.compile(r'^Penyata Akaun Memorandum'),
    re.compile(r'^pada 31 Disember'), re.compile(r'^seperti pada'),
    re.compile(r'^\(sambungan\)?$'), re.compile(r'^\(disambung'),
    re.compile(r'^PENYATA KEWANGAN KERAJAAN PERSEKUTUAN'),
    re.compile(r'^FEDERAL GOVERNMENT'),
    re.compile(r'^LAMPIRAN'), re.compile(r'^Peminjam$'),
    re.compile(r'^Baki Pinjaman Mengikut'), re.compile(r'^Baki Belum Selesai'),
    re.compile(r'^Pembangunan'), re.compile(r'^Hasil Disatukan'),
    re.compile(r'^\d{4}\s+\d{4}$'), re.compile(r'^\d{4}$'),
    re.compile(r'^(RM\s*)+$'), re.compile(r'^\d{1,3}$'),
    re.compile(r'^Dalam Negeri'), re.compile(r'^Luar Negeri'), re.compile(r'^Jumlah$'),
    re.compile(r'^Nota'),
]


def page_lines(pno, with_words=False):
    out = []
    for ws, ln in plumber_lines(pno):
        s = ln.rstrip()
        st = s.strip()
        if not st or any(p.match(st) for p in SKIP):
            continue
        out.append((ws, s) if with_words else s)
    return out


def split_label_vals(line):
    toks = line.split()
    vals = []
    while toks and is_val(toks[-1]):
        vals.insert(0, toks.pop())
    return ' '.join(toks), vals


# ===========================================================================
# LAMPIRAN 3  -- loans receivable (5 value cols: Pemb | Hasil | Amanah | 2010 | 2009)
# ===========================================================================
def extract_loans():
    stmt = 'Lampiran 3 Penyata Akaun Memorandum Pinjaman Boleh Dituntut'
    pageinfo = {228: 218, 229: 219, 230: 220}
    rows = []
    cat_no, cat = None, None
    for pno, pp in pageinfo.items():
        for st in page_lines(pno):
            st = st.strip()
            m = re.match(r'^([IVX]+)\.\s+(.*)$', st)
            if m:
                cat_no = m.group(1)
                cat = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', m.group(2)).strip()
                continue
            label, vals = split_label_vals(st)
            if not vals:
                if rows and not label.startswith('Jumlah') and not label.startswith('JUMLAH'):
                    # wrapped borrower-name continuation
                    rows[-1]['peminjam_bm'] += ' ' + label
                continue
            if len(vals) != 5:
                DIAG.append(f'L3 p{pno}: expected 5 vals got {len(vals)}: {st!r}')
                continue
            rt = 'detail'
            cn, cc, sec = cat_no, cat, 'PINJAMAN'
            if label.startswith('Jumlah '):
                rt = 'subtotal'
            elif label.startswith('JUMLAH PINJAMAN BOLEH DITUNTUT'):
                rt, cn, cc, sec = 'total', None, None, None
            rows.append(prov(dict(
                section_bm=sec, category_no=cn, category_bm=cc, peminjam_bm=label,
                row_type=rt, year=YEAR,
                pembangunan_rm=amt(vals[0]), hasil_disatukan_rm=amt(vals[1]),
                amanah_lain_rm=amt(vals[2]), baki_belum_selesai_rm=amt(vals[3])),
                pno, pp, stmt))
    cols = ['section_bm', 'category_no', 'category_bm', 'peminjam_bm', 'row_type',
            'year', 'pembangunan_rm', 'hasil_disatukan_rm', 'amanah_lain_rm',
            'baki_belum_selesai_rm', 'source_file', 'pdf_page', 'printed_page', 'statement']
    df = pd.DataFrame(rows)[cols]
    df.to_csv(f'{WH}/fact_loans_receivable.csv', index=False)
    return df


# ===========================================================================
# LAMPIRAN 4  -- investments (pdfplumber x-zones; % header calibrates dx/page)
# ===========================================================================
INV_SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
CCY = re.compile(r'^[A-Z]{3}$|^Baht$')
INV_AMT = re.compile(r'^[\d,]+\.\d{2}$')
FN = re.compile(r'^\((\d)\)$')


def _inv_amt(tok):
    if tok is None:
        return None
    if tok in (DASH, '-'):
        return 0.0
    return float(tok.replace(',', ''))


def inv_group_lines(words, gap=3.0):
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


def inv_classify(w, dx):
    x0, x1, t = w['x0'] - dx, w['x1'] - dx, w['text']
    if x1 <= 255:
        if INV_AMT.match(t) and x1 > 195:
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
        return 'nb_cur'
    return 'nb_prev'


def extract_investments():
    stmt = 'Lampiran 4 Penyata Akaun Memorandum Pelaburan'
    PAGES = {232: 222, 233: 223, 234: 224, 235: 225}
    records = []
    section = None
    cur_entity = None
    for pno, pp in PAGES.items():
        page = _pdf.pages[pno - 1]
        words = [w for w in page.extract_words(keep_blank_chars=False)
                 if w.get('upright', True) and w['x0'] >= 0 and w['x1'] <= page.width + 5]
        pct_hdr = [w for w in words if w['text'].rstrip('!') == '%' and w['top'] < 260]
        dx = pct_hdr[0]['x0'] - 441.1
        body = [w for w in words if 143 < w['top'] < 815
                and not (re.fullmatch(r'\d{1,3}', w['text']) and (w['x0'] - dx > 565 or w['x0'] < 60))]
        lines = inv_group_lines(body)
        in_nota = False
        for ln in lines:
            texts = [w['text'] for w in ln]
            joined = ' '.join(texts)
            if joined.startswith('Nota'):
                in_nota = True
            if in_nota:
                continue
            if set(texts) <= {'RM', '%', ''}:
                continue
            if joined.startswith(('(disambung', '(sambungan', 'LAMPIRAN', 'Penyata Akaun',
                                  'seperti pada', 'Modal', 'Entiti', 'Diterbitkan', 'Perihal',
                                  'Nilai', 'Pegangan', 'FEDERAL')) \
               or 'PENYATA KEWANGAN KERAJAAN PERSEKUTUAN' in joined \
               or re.fullmatch(r'\d{1,3}', joined) or re.fullmatch(r'(\d{4}\s*)+', joined):
                continue
            zones = {}
            for w in ln:
                if w['text'] == '':
                    continue
                zones.setdefault(inv_classify(w, dx), []).append(w['text'])
            ent_words = [t for t in zones.get('entity', []) if not FN.match(t)]
            fns = [FN.match(t).group(1) for t in zones.get('entity', []) if FN.match(t)]
            ent_txt = ' '.join(ent_words)
            has_values = any(z in zones for z in ('nominal', 'pct', 'nb_cur', 'nb_prev'))
            norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()
            if norm in INV_SECTIONS and not has_values and not zones.get('perihal'):
                section = norm
                cur_entity = None
                continue
            if not has_values:
                if ent_txt and cur_entity is not None:
                    cur_entity['name'] += ' ' + ent_txt
                if fns and cur_entity is not None:
                    cur_entity['fns'] += fns
                if zones.get('perihal') and records and records[-1].get('kind') == 'detail':
                    records[-1]['perihal'] += ' ' + ' '.join(zones['perihal'])
                continue
            if ent_txt.startswith(('Jumlah', 'JUMLAH')):
                records.append(dict(kind='agg', section=section, label=ent_txt,
                                    nb_cur=zones.get('nb_cur', [None])[0],
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
            if cur_entity is None:
                DIAG.append(f'L4 p{pno}: detail row without entity: {joined!r}')
                continue
            records.append(dict(kind='detail', section=section, entity=cur_entity,
                                perihal=' '.join(zones.get('perihal', [])),
                                nominal_ccy=zones.get('nominal_ccy', [None])[0],
                                nominal=zones.get('nominal', [None])[0],
                                pct=zones.get('pct', [None])[0],
                                nb_cur=zones.get('nb_cur', [None])[0],
                                pdf_page=pno, printed_page=pp))

    # strip trailing footnote/asterisk from entity names
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
                        pegangan_pct=None, row_type=rt, has_footnote=False, footnote_ref=None,
                        nilai_buku_rm=_inv_amt(r['nb_cur']))
        else:
            e = r['entity']
            nom_ccy = r['nominal_ccy'] or ('RM' if r['nominal'] and r['nominal'] != DASH else None)
            base = dict(section_bm=r['section'], entiti_bm=e['name'], perihal=r['perihal'] or None,
                        modal_saham_ccy=e['modal_ccy'] if e['modal'] else None,
                        modal_saham_amt=_inv_amt(e['modal']),
                        nilai_nominal_ccy=nom_ccy if (r['nominal'] and r['nominal'] != DASH) else None,
                        nilai_nominal_amt=_inv_amt(r['nominal']),
                        pegangan_pct=(_inv_amt(r['pct']) if r['pct'] not in (DASH, '-', None) else None),
                        row_type='detail', has_footnote=bool(e['fns']),
                        footnote_ref=(','.join(e['fns']) if e['fns'] else None),
                        nilai_buku_rm=_inv_amt(r['nb_cur']))
        rows.append(prov(dict(base, year=YEAR), r['pdf_page'], r['printed_page'], stmt))
    cols = ['section_bm', 'entiti_bm', 'perihal', 'modal_saham_ccy', 'modal_saham_amt',
            'nilai_nominal_ccy', 'nilai_nominal_amt', 'pegangan_pct', 'row_type',
            'has_footnote', 'footnote_ref', 'year', 'nilai_buku_rm', 'source_file',
            'pdf_page', 'printed_page', 'statement']
    df = pd.DataFrame(rows)[cols]
    df['footnote_ref'] = df['footnote_ref'].astype('string')
    df.to_csv(f'{WH}/fact_investments.csv', index=False)
    return df


# ===========================================================================
# LAMPIRAN 5  -- statutory guarantees (Dalam | Luar | 2010 | 2009)
# ===========================================================================
def extract_statutory():
    stmt = 'Lampiran 5 Penyata Akaun Memorandum Jaminan Berkanun'
    pno, pp = 238, 228
    rows = []
    cat = None
    for st in page_lines(pno):
        st = re.sub(r'\s+', ' ', st.strip())
        label, vals = split_label_vals(st)
        if not vals:
            if label in ('BADAN BERKANUN', 'SYARIKAT'):
                cat = label
            elif rows:
                rows[-1]['agensi_bm'] += ' ' + label
            continue
        if len(vals) != 4:
            DIAG.append(f'L5 p{pno}: expected 4 vals got {len(vals)}: {st!r}')
            continue
        rt, c = 'detail', cat
        if label.startswith('Jumlah '):
            rt = 'subtotal'
        elif label.startswith('JUMLAH JAMINAN BERKANUN'):
            rt, c = 'total', None
        rows.append(prov(dict(
            jenis_jaminan_bm=None, kategori_bm=c, agensi_bm=label, row_type=rt, year=YEAR,
            dalam_negeri_rm=amt(vals[0]), luar_negeri_rm=amt(vals[1]), jumlah_rm=amt(vals[2])),
            pno, pp, stmt))
    cols = ['jenis_jaminan_bm', 'kategori_bm', 'agensi_bm', 'row_type', 'year',
            'dalam_negeri_rm', 'luar_negeri_rm', 'jumlah_rm', 'source_file',
            'pdf_page', 'printed_page', 'statement']
    df = pd.DataFrame(rows)[cols]
    df.to_csv(f'{WH}/fact_statutory_guarantees.csv', index=False)
    return df


# ===========================================================================
# LAMPIRAN I  -- statistics panel 2001-2010 (Malay pages, text-based)
# ===========================================================================
NUMTOK = re.compile(r'^\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$')
YEARS = list(range(2010, 2000, -1))  # 10 columns, left->right = 2010..2001


def ts_amount(tok):
    if tok in (DASH, '-', '—'):
        return 0.0
    neg = tok.startswith('(') and tok.endswith(')')
    return (-1 if neg else 1) * float(tok.strip('()').replace(',', ''))


def extract_timeseries():
    stmt = 'Lampiran I Perangkaan Kewangan Kerajaan Persekutuan 2001-2010'
    pageinfo = [(294, 2), (295, 3), (296, 4)]
    SPECIAL = {'Penerimaan', 'Pembayaran', 'Perbelanjaan Pembangunan'}
    batch = []          # (section, label, vals(list len10), pno, pp)
    section = None
    for pno, pp in pageinfo:
        if pno == 295:
            # print omission: the 'Hasil' section header is not printed at the top
            # of printed page 3 (it opens directly on 'Cukai Langsung'). 2012 volume
            # prints it. Seed it; reported as a discrepancy.
            section = 'Hasil'
            DIAG.append("TS: 'Hasil' section header absent on printed p3 (pdf295) "
                        "- seeded from structure (Jumlah Hasil subtotal confirms grouping)")
        for raw in pages_txt[pno - 1].split('\n'):
            st = raw.strip()
            if not st:
                continue
            if re.match(r'^(Perangkaan Kewangan|Federal Government|\(dalam RM juta\)|'
                        r'\(in RM million\)|\(sambungan|\(continuation|Lampiran|Appendix|'
                        r'PENYATA KEWANGAN|FEDERAL GOVERNMENT|Nota\b|Note\b)', st):
                continue
            if re.match(r'^\(?\s*\d\s*\)\s*-', st):  # footnote definition lines
                continue
            toks = st.split()
            if all(re.fullmatch(r'20\d\d', t) for t in toks):  # year header row
                continue
            if re.fullmatch(r'\d{1,3}', st):  # page number footer
                continue
            vals = []
            while toks and NUMTOK.match(toks[-1]):
                vals.insert(0, toks.pop())
            label = ' '.join(toks)
            if not vals:
                # section header or wrapped-label continuation
                if not label:
                    continue
                if label[0].islower() or label[0] == '(':
                    if batch:
                        batch[-1] = (batch[-1][0], batch[-1][1] + ' ' + label,
                                     batch[-1][2], batch[-1][3], batch[-1][4])
                    continue
                # a section header
                if label in SPECIAL and (section or '').startswith('Kumpulan Wang'):
                    base = section.split(' / ')[0]
                    section = f'{base} / {label}'
                else:
                    section = label
                continue
            if len(vals) == 11 and re.fullmatch(r'\d{1,3}', vals[0]):
                # trailing footnote ref (e.g. 'Bil Perbendaharaan 4') popped as an
                # extra leading value; the 10 real year-columns are the rightmost 10
                vals = vals[1:]
            if len(vals) != 10:
                DIAG.append(f'TS p{pno}: expected 10 vals got {len(vals)}: {st!r}')
                continue
            batch.append((section, label, [ts_amount(v) for v in vals], pno, pp))

    out = []
    for section, label, vals, pno, pp in batch:
        for i, yr in enumerate(YEARS):
            out.append([section, label, yr, vals[i], 'RM juta', SRC, pno, pp, stmt])
    with open(f'{WH}/fact_timeseries_2001_2010.csv', 'w', newline='', encoding='utf-8') as f:
        cw = csv.writer(f)
        cw.writerow(['section_bm', 'line_item_bm', 'year', 'amount_rm_juta', 'unit',
                     'source_file', 'pdf_page', 'printed_page', 'statement'])
        cw.writerows(out)
    return pd.DataFrame(out, columns=['section_bm', 'line_item_bm', 'year', 'amount_rm_juta',
                                      'unit', 'source_file', 'pdf_page', 'printed_page', 'statement'])


if __name__ == '__main__':
    d3 = extract_loans()
    print('L3 loans_receivable rows:', len(d3))
    d4 = extract_investments()
    print('L4 investments rows:', len(d4))
    d5 = extract_statutory()
    print('L5 statutory_guarantees rows:', len(d5))
    dt = extract_timeseries()
    print('LI timeseries rows:', len(dt))
    print('\n--- DIAGNOSTICS ---')
    for d in DIAG:
        print(' ', d)
