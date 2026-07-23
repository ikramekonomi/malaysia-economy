#!/usr/bin/env python3
"""Extract memorandum register tables (Lampiran 3, 5, 6) from PKKP 2017 text layer.

Adapted from the proven 2018 pipeline. The 2017 volume has only SIX lampiran;
the register set is smaller than 2018:
  fact_loans_receivable.csv           pdf 254-256  Lampiran 3 (FIVE value
                                      columns: Pembangunan | Hasil Disatukan |
                                      Amanah Lain | Baki 2017 | Baki 2016 --
                                      the Hasil Disatukan fund column exists
                                      only in this era; stored in
                                      hasil_disatukan_rm)
  fact_debt_issues.csv                pdf 266-269  Lampiran 5 (Pinjaman + Bantuan Luar Negeri)
  fact_statutory_guarantees.csv       pdf 272      Lampiran 6 (Jaminan Berkanun)
NO counterparts exist in this volume for: fact_guarantees (no Komitmen Jaminan
register -- commitments are not reported at all in the 2017 volume),
fact_finance_leases (no Komitmen Pajakan Kewangan register), fact_pfi_liabilities,
fact_guarantee_repayment_grants, fact_compensation_commitments.
fact_investments.csv (Lampiran 4, pdf 260-263) is produced by extract_investments.py.
"""
import re
import pandas as pd

WORK = '/home/claude/pkkp/work/2017'
WH = '/home/claude/pkkp/warehouse2017'
SRC = '2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2017
PRIOR = 2016

pages = open(f'{WORK}/full.txt').read().split('\f')
import pdfplumber
_pdf = pdfplumber.open(f'{WORK}/2017.pdf')
_plcache = {}

def plumber_lines(pno):
    """Reconstruct visual text lines from pdfplumber word coordinates. Rotated
    side labels, off-page bleed, watermark glyphs and margin page numbers are
    dropped."""
    if pno in _plcache:
        return _plcache[pno]
    pg = _pdf.pages[pno - 1]
    ws = [w for w in pg.extract_words(x_tolerance=1.5, y_tolerance=2)
          if w.get('upright', True) and w['x0'] >= 0 and w['x1'] <= pg.width + 5
          and 0 <= w['top'] <= pg.height]
    ws = [w for w in ws if not (re.fullmatch(r'\d{1,3}', w['text'])
                                and (w['x0'] < 70 or w['x0'] > pg.width - 60))]
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
               and re.match(r'^[\d,().*]+$', merged[-1]['text']) and re.match(r'^[\d,().]+$', w['text']):
                merged[-1] = dict(merged[-1], text=merged[-1]['text'] + w['text'], x1=w['x1'])
            else:
                merged.append(dict(w))
        out.append(' '.join(w['text'] for w in merged))
    _plcache[pno] = out
    return out

AMT = re.compile(r'^\(?[\d,]+\.\d{2}\)?$|^\(?\d{1,3}(?:,\d{3})+\)?$')
DASH = '–'

def is_val(tok):
    return tok == DASH or tok == '-' or AMT.match(tok)

def amt(tok):
    if tok is None or tok == '':
        return None
    if tok in (DASH, '-'):
        return 0.0
    neg = tok.startswith('(') and tok.endswith(')')
    v = float(tok.strip('()').replace(',', ''))
    return -v if neg else v

SKIP = [
    re.compile(r'^PENYATA KEWANGAN KERAJAAN PERSEKUTUAN'),
    re.compile(r'^\[2O1[78]\]'),
    re.compile(r'^\d+\s*\|?\s*PENYATA KEWANGAN'),
    re.compile(r'^\d+$'),
    re.compile(r'^LAMPIRAN \d+'),
    re.compile(r'^\(disambung'),
    re.compile(r'^\(s ?ambungan ?\)!?'),
    re.compile(r'^Penyata (Akaun|Penyaluran)'),
    re.compile(r'^[Pp]ada 31 Disember'),
    re.compile(r'^(%|RM)(!)?( +(%|RM)(!)?)*( \( ?\w\))?$'),
    re.compile(r'^(Jumlah\s*)+!?$'),
    re.compile(r'^\d+ WJD\d+ Teks'),
    re.compile(r'^WJD\d+ Teks'),
    re.compile(r'^\d+\s+WJD'),
    re.compile(r'^PENDAHULUAN BOLEH DITUNTUT$'),   # rotated side label
    re.compile(r'^PINJAMAN DAN$'),
    re.compile(r'^KEWANGAN$'),
    re.compile(r'^!+$'),
    re.compile(r'^Excellent Accounting'),
    re.compile(r'^\(cid:'),
    re.compile(r'^Nombor$'),                        # stray watermark word
    re.compile(r'^HUTANG PERSEKUTUAN$'),            # rotated side label (L5)
    re.compile(r'^JAMINAN BERKANUN$'),              # rotated side label (L6)
]

def page_lines(pno):
    out = []
    for ln in plumber_lines(pno):
        s = ln.replace('!', '').rstrip()
        s = re.sub(r'\s+Nombor(\s+)', r'\1', s)   # watermark word inside a data row
        st = s.strip()
        if not st:
            continue
        if any(p.match(st) for p in SKIP):
            continue
        out.append(s)
    return out

def split_label_vals(line, nvals=None):
    toks = line.split()
    vals = []
    while toks and is_val(toks[-1]):
        vals.insert(0, toks.pop())
    label = ' '.join(toks)
    return label, vals

def prov(row, pdf_page, printed_page, statement):
    row['source_file'] = SRC
    row['pdf_page'] = pdf_page
    row['printed_page'] = printed_page
    row['statement'] = statement
    return row

# ---------------------------------------------------------------------------
# 1. Lampiran 3: Pinjaman dan Pendahuluan Boleh Dituntut (pdf 254-256)
#    FIVE value columns: Pembangunan | Hasil Disatukan | Amanah Lain |
#    Baki Belum Selesai 2017 | 2016
# ---------------------------------------------------------------------------
def extract_loans():
    stmt = 'Penyata Akaun Memorandum Pinjaman dan Pendahuluan Boleh Dituntut'
    pageinfo = {254: 243, 255: 244, 256: 245}
    recs = []
    section = None
    cat_no, cat = None, None
    pending_label = None
    HDR_SKIP = re.compile(r'^(Peminjam|Baki Pinjaman Mengikut|Pembangunan\s+Hasil Disatukan|Hasil Disatukan|Amanah Lain|Baki Belum Selesai|Nota:|Nota :)')
    for pno, pp in pageinfo.items():
        prev_was_row = False
        for line in page_lines(pno):
            st = line.strip()
            if HDR_SKIP.match(st):
                continue
            m = re.match(r'^(PINJAMAN|PENDAHULUAN):$', st)
            if m:
                section = m.group(1)
                cat_no, cat = None, None
                prev_was_row = False
                continue
            m = re.match(r'^([IVX]+)\.\s+(.*)$', st)
            if m and not re.search(r'\d,\d{3}', st):
                cat_no = m.group(1)
                cat = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', m.group(2)).strip()
                prev_was_row = False
                continue
            if st == 'KERAJAAN NEGERI':
                cat_no, cat = None, st
                prev_was_row = False
                continue
            label, vals = split_label_vals(st)
            if len(vals) == 5:
                if not label and pending_label:
                    label = pending_label
                    pending_label = None
                recs.append(dict(section_bm=section, category_no=cat_no, category_bm=cat,
                                 label=label, vals=vals, pdf_page=pno, printed_page=pp))
                prev_was_row = True
                continue
            if vals:
                raise ValueError(f'unexpected val count p{pno}: {st!r}')
            if label.startswith('JUMLAH'):
                pending_label = label
                prev_was_row = False
                continue
            if pending_label is not None:
                pending_label += ' ' + label
            elif prev_was_row and recs:
                recs[-1]['label'] += ' ' + label
            else:
                raise ValueError(f'orphan label p{pno}: {st!r}')
    rows = []
    for r in recs:
        lb = r['label']
        if lb == 'DITUNTUT':
            continue
        if lb.startswith('JUMLAH PINJAMAN DAN PENDAHULUAN BOLEH'):
            lb = 'JUMLAH PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT'
        rt = 'detail'
        cat_no, cat = r['category_no'], r['category_bm']
        if lb.startswith('Jumlah '):
            rt = 'subtotal'
        elif lb in ('JUMLAH PINJAMAN', 'JUMLAH PENDAHULUAN'):
            rt, cat_no, cat = 'subtotal', None, None
        elif lb == 'JUMLAH PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT':
            rt, cat_no, cat = 'total', None, None
        sec = r['section_bm'] if rt != 'total' else None
        v = r['vals']
        base = dict(section_bm=sec, category_no=cat_no, category_bm=cat,
                    peminjam_bm=lb, row_type=rt)
        rows.append(prov(dict(base, year=YEAR, pembangunan_rm=amt(v[0]),
                              hasil_disatukan_rm=amt(v[1]), amanah_rm=amt(v[2]),
                              baki_belum_selesai_rm=amt(v[3])), r['pdf_page'], r['printed_page'], stmt))
        rows.append(prov(dict(base, year=PRIOR, pembangunan_rm=None,
                              hasil_disatukan_rm=None, amanah_rm=None,
                              baki_belum_selesai_rm=amt(v[4])), r['pdf_page'], r['printed_page'], stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_loans_receivable.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 2. Lampiran 5: Hutang Persekutuan (pdf 266-269)
# ---------------------------------------------------------------------------
def extract_debt_issues():
    rows = []
    stmt = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Pinjaman)'
    pageinfo = {266: 255, 267: 256}
    region, instrument, ln_ccy = None, None, None
    def add(pno, pp, **kw):
        base = dict(region_bm=None, instrument_bm=None, lender_bm=None, no_keluaran=None,
                    kod_saham=None, perihal_bm=None, kadar_faedah=None, tarikh_tebusan=None,
                    ccy=None, amaun_dibenarkan_fx=None, terkumpul_keluaran_fx=None,
                    terkumpul_bayaran_balik_fx=None, amaun_belum_selesai_fx=None,
                    amaun_dibenarkan_rm=None, amaun_belum_selesai_rm=None,
                    row_type='detail', has_footnote=False, year=YEAR)
        st = kw.pop('statement', stmt)
        base.update(kw)
        rows.append(prov(base, pno, pp, st))
    for pno, pp in pageinfo.items():
        for line in page_lines(pno):
            st = re.sub(r'\s+', ' ', line.strip())
            if st in ('DALAM NEGERI', 'LUAR NEGERI'):
                region = st
                continue
            st = re.sub(r'\s*\(Samb\.?\)\s*$|\s*-?\s*\(SAMB\.?\)\s*$', '', st)
            if st in ('TERBITAN PELABURAN KERAJAAN', 'SEKURITI KERAJAAN MALAYSIA',
                      'SUKUK PERUMAHAN KERAJAAN', 'PINJAMAN PASARAN'):
                instrument = st
                continue
            if st in ('SUKUK', 'USD RM', 'RM', '% RM RM') or '(disambung' in st or '(sambungan' in st \
               or re.fullmatch(r'[%\sRM]+', st) or st.startswith('No. Keluaran') or st.startswith('Kadar') \
               or st.startswith('Perihal') or st.startswith('Faedah') or st.startswith('Tebusan') \
               or st.startswith('Amaun') or st.startswith('Dibenarkan') or st.startswith('Belum Selesai') \
               or st.startswith('Tarikh') or st.startswith('Nota'):
                continue
            if st.startswith('BIL PERBENDAHARAAN'):
                m = re.match(r'^BIL PERBENDAHARAAN Dengan Tawaran (\d{4}) (\S+) (\S+)$', st)
                add(pno, pp, region_bm=region, instrument_bm='BIL PERBENDAHARAAN',
                    kadar_faedah='Dengan Tawaran', tarikh_tebusan=m.group(1),
                    amaun_dibenarkan_rm=amt(m.group(2)), amaun_belum_selesai_rm=amt(m.group(3)))
                continue
            label, vals = split_label_vals(st)
            if label.startswith('Jumlah ') or label.startswith('JUMLAH'):
                rt = 'total' if label == 'JUMLAH PINJAMAN' else 'subtotal'
                kw = dict(region_bm=region if rt != 'total' else None, row_type=rt)
                if label.startswith('Jumlah ') and label not in ('Jumlah Dalam Negeri', 'Jumlah Luar Negeri'):
                    kw['instrument_bm'] = instrument
                if len(vals) == 2:
                    if region == 'LUAR NEGERI' and rt == 'subtotal':
                        kw['amaun_dibenarkan_fx'] = amt(vals[0])   # USD column
                        kw['ccy'] = 'USD'
                    else:
                        kw['amaun_dibenarkan_rm'] = amt(vals[0])
                    kw['amaun_belum_selesai_rm'] = amt(vals[1])
                elif len(vals) == 1:
                    kw['amaun_belum_selesai_rm'] = amt(vals[0])
                else:
                    raise ValueError(f'jumlah vals p{pno}: {st!r}')
                add(pno, pp, perihal_bm=label, **kw)
                continue
            m = re.match(r'^(\d+/\d{4}) (.+?) (\d\.\d{3}) (\d{2}\.\d{2}\.\d{4}) (\S+) (\S+)$', st)
            if m:
                add(pno, pp, region_bm=region, instrument_bm=instrument,
                    no_keluaran=m.group(1), kod_saham=m.group(2), kadar_faedah=m.group(3),
                    tarikh_tebusan=m.group(4), amaun_dibenarkan_rm=amt(m.group(5)),
                    amaun_belum_selesai_rm=amt(m.group(6)))
                continue
            # LUAR NEGERI market loans: perihal + kadar + tarikh + USD amt + RM amt
            m = re.match(r'^(.+?) (\d\.\d{3}) (\d{2}\.\d{2}\.\d{4}) (\S+) (\S+)$', st)
            if m and instrument == 'PINJAMAN PASARAN':
                add(pno, pp, region_bm=region, instrument_bm=instrument, perihal_bm=m.group(1),
                    kadar_faedah=m.group(2), tarikh_tebusan=m.group(3), ccy='USD',
                    amaun_dibenarkan_fx=amt(m.group(4)), amaun_belum_selesai_rm=amt(m.group(5)))
                continue
            raise ValueError(f'unparsed p{pno}: {st!r}')
    # --- (b) Bantuan Luar Negeri, pdf 268-269 ---
    stmt_b = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Bantuan Luar Negeri)'
    section, lender, ccy = None, None, None
    pending_fn = False
    lender_fn = False
    CCYHDR = re.compile(r'^(.*?)\s*(\(\s*[a-z\d]\s*\))?\s+([A-Z]{3})( +[A-Z]{3}){3}$')
    for pno, pp in [(268, 257), (269, 258)]:
      in_nota = False
      for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if in_nota:
            continue
        if st.startswith('Nota'):
            in_nota = True
            continue
        if re.match(r'^\(\s*[a-z\d]\s*\)$', st):
            pending_fn = True
            continue
        if st in ('PINJAMAN MULTILATERAL', 'PINJAMAN BILATERAL', 'PINJAMAN BILATERAL - (SAMB.)'):
            section = st.replace(' - (SAMB.)', '')
            continue
        if st.startswith(('Perihal', 'Kadar', 'Tarikh', 'Amaun', 'Jumlah Terkumpul',
                          'Mata Wang', 'Faedah', 'Tebusan', 'Keluaran', 'Bayaran Balik',
                          'Belum Selesai', 'Ringgit Malaysia', '(c)', '(d)')):
            continue
        m = CCYHDR.match(st)
        if m and not st.startswith('Jumlah') and not re.match(r'^\d{4} ', st):
            lender = m.group(1).strip()
            lender_fn = bool(m.group(2)) or pending_fn
            pending_fn = False
            ccy = m.group(3)
            continue
        label, vals = split_label_vals(st)
        if vals in ([DASH], ['-']) and not re.match(r'^\d{4} ', st) and rows and label:
            rows[-1]['perihal_bm'] += ' ' + label
            continue
        if label.startswith('JUMLAH'):
            rt = 'total' if label == 'JUMLAH BANTUAN LUAR NEGERI' else 'subtotal'
            add(pno, pp, statement=stmt_b, region_bm=None if rt == 'total' else section,
                perihal_bm=label, row_type=rt, amaun_belum_selesai_rm=amt(vals[0]))
            continue
        if label.startswith('Jumlah '):
            assert len(vals) == 5, st
            add(pno, pp, statement=stmt_b, region_bm=section, lender_bm=lender, ccy=ccy,
                perihal_bm=label, row_type='subtotal',
                amaun_dibenarkan_fx=amt(vals[0]), terkumpul_keluaran_fx=amt(vals[1]),
                terkumpul_bayaran_balik_fx=amt(vals[2]), amaun_belum_selesai_fx=amt(vals[3]),
                amaun_belum_selesai_rm=amt(vals[4]), has_footnote=lender_fn)
            continue
        m = re.match(r'^(.+?) (\d+\.\d{2,3}(?:-\d+\.\d{2,3})?|-|–|\d+%-\d+%|Berubah) (\d{4}/\d{4})$',
                     ' '.join(st.split()[:len(st.split()) - len(vals)]))
        if m and len(vals) == 5:
            add(pno, pp, statement=stmt_b, region_bm=section, lender_bm=lender, ccy=ccy,
                perihal_bm=m.group(1), kadar_faedah=m.group(2), tarikh_tebusan=m.group(3),
                amaun_dibenarkan_fx=amt(vals[0]), terkumpul_keluaran_fx=amt(vals[1]),
                terkumpul_bayaran_balik_fx=amt(vals[2]), amaun_belum_selesai_fx=amt(vals[3]),
                amaun_belum_selesai_rm=amt(vals[4]), has_footnote=lender_fn)
            continue
        if not vals and rows:
            rows[-1]['perihal_bm'] += ' ' + label
            continue
        raise ValueError(f'unparsed bantuan p{pno}: {st!r}')
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_debt_issues.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 3. Lampiran 6: Jaminan Berkanun (pdf 272)
# ---------------------------------------------------------------------------
def extract_dn_ln_table(pno, pp, stmt, out_csv, type_headers=()):
    """Tables with columns: Dalam Negeri | Luar Negeri | Jumlah 2017 | 2016."""
    rows = []
    jenis, cat = None, None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        st = re.sub(r'( RM)+$', '', st)
        if st.startswith(('Agensi', 'Dalam Negeri', 'Luar Negeri', 'Jumlah 2017', '2017 2016')) \
           or st == 'Jumlah' or st.startswith('Nota'):
            continue
        label, vals = split_label_vals(st)
        if not vals:
            if label in type_headers:
                jenis, cat = label, None
            else:
                cat = label
            continue
        if len(vals) == 3 and abs(amt(vals[0]) - amt(vals[1])) < 0.005:
            # print omission (Sentuhan Budiman / SSER, pdf 272): ONE of the
            # Dalam/Luar Negeri cells is BLANK (not even a dash). Decide which
            # by the first amount's x-position on the page (DN column right
            # edge ~338, LN ~400-408).
            pgw = _pdf.pages[pno - 1]
            lw = [w for w in pgw.extract_words(x_tolerance=1.5, y_tolerance=2)
                  if w.get('upright', True)]
            first_word = label.split()[0]
            tops = [w['top'] for w in lw if w['text'] == first_word]
            x1 = None
            for t in tops:
                amts = sorted((w for w in lw if abs(w['top'] - t) < 3
                               and re.match(r'^[\d,]+\.\d{2}$', w['text'])),
                              key=lambda w: w['x0'])
                if amts and amts[0]['text'].replace(',', '') == vals[0].replace(',', ''):
                    x1 = amts[0]['x1']
                    break
            if x1 is not None and x1 > 370:
                print(f'!! blank Dalam Negeri cell (print omission): {st[:60]!r} -> stored 0.0')
                vals = [DASH, vals[0], vals[1], vals[2]]
            else:
                print(f'!! blank Luar Negeri cell (print omission): {st[:60]!r} -> stored 0.0')
                vals = [vals[0], DASH, vals[1], vals[2]]
        assert len(vals) == 4, st
        rt = 'detail'
        c = cat
        if label.startswith('Jumlah '):
            rt = 'subtotal'
        elif label.startswith('JUMLAH JAMINAN PENCARUM') or label == 'JUMLAH JAMINAN PINJAMAN':
            rt, c = 'subtotal', None
        elif label.startswith('JUMLAH'):
            rt, c = 'total', None
        base = dict(jenis_jaminan_bm=(None if rt == 'total' else jenis),
                    kategori_bm=c, agensi_bm=label, row_type=rt)
        if not type_headers:
            base.pop('jenis_jaminan_bm')
            base.pop('kategori_bm')
        rows.append(prov(dict(base, year=YEAR, dalam_negeri_rm=amt(vals[0]),
                              luar_negeri_rm=amt(vals[1]), jumlah_rm=amt(vals[2])), pno, pp, stmt))
        rows.append(prov(dict(base, year=PRIOR, dalam_negeri_rm=None,
                              luar_negeri_rm=None, jumlah_rm=amt(vals[3])), pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/{out_csv}', index=False)
    return df

if __name__ == '__main__':
    d1 = extract_loans()
    print('loans_receivable', len(d1))
    d2 = extract_debt_issues()
    print('debt_issues', len(d2))
    d5 = extract_dn_ln_table(272, 261, 'Penyata Akaun Memorandum Jaminan Berkanun',
                             'fact_statutory_guarantees.csv',
                             type_headers=('JAMINAN PENCARUM / PENDEPOSIT', 'JAMINAN PINJAMAN'))
    print('statutory_guarantees', len(d5))
