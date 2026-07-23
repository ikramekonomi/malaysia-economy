#!/usr/bin/env python3
"""Extract memorandum register tables (Lampiran 4, 6-11) from PKKP 2020 text layer.

Adapted from the proven 2022 pipeline (printed = pdf - 16).

Outputs (to ../warehouse2020/):
  fact_loans_receivable.csv           pdf 255-257  Lampiran 4
  fact_debt_issues.csv                pdf 266-267  Lampiran 6 (Pinjaman) -- 2020: SUKUK
                                                   PERUMAHAN KERAJAAN includes the Sukuk
                                                   Prihatin issue (1/2020 ISPM2001);
                                                   LUAR NEGERI market loans carry a ccy
                                                   'USD/JPY nnn' authorised column
                                      pdf 268-269  Lampiran 6 (Bantuan Luar Negeri) --
                                                   lender footnotes are (a)/(b)/(c),
                                                   ISD (Islamic Dinar) currency appears
  fact_pfi_liabilities.csv            pdf 273      Lampiran 7
  fact_guarantees.csv                 pdf 276      Lampiran 8 (flat agency list)
  fact_guarantee_repayment_grants.csv pdf 277      Lampiran 8 ('Penyata Penyaluran Geran
                                                   Bayaran Balik Pinjaman' in 2020)
  fact_finance_leases.csv             pdf 281      Lampiran 9 (single page; sectors with
                                                   'Bangunan' category; '*' footnotes on
                                                   ministries affected by the 2020 MDM
                                                   machinery-of-government restructure)
  fact_compensation_commitments.csv   pdf 285      Lampiran 10 (highway concessions only)
  fact_statutory_guarantees.csv       pdf 289      Lampiran 11

fact_investments.csv (pdf 260-263) is produced by extract_investments.py (needs coordinates).
"""
import re
import pandas as pd

WORK = '/home/claude/pkkp/work/2020'
WH = '/home/claude/pkkp/warehouse2020'
SRC = '2020_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2020
PRIOR = 2019

pages = open(f'{WORK}/full.txt').read().split('\f')

AMT = re.compile(r'^\(?[\d,]+\.\d{2}\)?$')
AMTX = re.compile(r'^\(?[\d,]+(?:\.\d{2})?\)?$')   # fx columns may omit decimals
DASH = '–'

def is_val(tok):
    return tok == DASH or AMT.match(tok)

def is_valx(tok):
    return tok == DASH or AMTX.match(tok)

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
    re.compile(r'^\d+\s+PENYATA KEWANGAN'),
    re.compile(r'^\d+$'),
    re.compile(r'^LAMPIRAN \d+'),
    re.compile(r'^\(disambung'),
    re.compile(r'^\(sambungan\s*\)'),
    re.compile(r'^\(sambun'),
    re.compile(r'^Penyata (Akaun|Penyaluran)'),
    re.compile(r'^pada 31 Disember'),
    re.compile(r'^(%|RM)( +(%|RM))*( \( ?\d\))?$'),
    re.compile(r'^(Jumlah\s*)+$'),
    re.compile(r'^\d+\. Teks Lampiran'),
    re.compile(r'^14/10/2021'),
]

def page_lines(pno):
    raw = pages[pno - 1].split('\n')
    out = []
    for ln in raw:
        s = ln.rstrip()
        st = s.strip()
        if not st:
            continue
        if any(p.match(st) for p in SKIP):
            continue
        out.append(s)
    return out

def split_label_vals(line, valfn=is_val):
    toks = line.split()
    vals = []
    while toks and valfn(toks[-1]):
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
# 1. Lampiran 4: Pinjaman dan Pendahuluan Boleh Dituntut (pdf 255-257)
# ---------------------------------------------------------------------------
def extract_loans():
    stmt = 'Penyata Akaun Memorandum Pinjaman dan Pendahuluan Boleh Dituntut'
    pageinfo = {255: 239, 256: 240, 257: 241}
    recs = []
    section = None
    cat_no, cat = None, None
    pending_label = None
    HDR_SKIP = re.compile(r'^(Peminjam|Baki Pinjaman Mengikut|Pembangunan\s+Amanah|Baki Belum Selesai)')
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
            if m:
                cat_no = m.group(1)
                cat = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', m.group(2)).strip()
                prev_was_row = False
                continue
            if st == 'KERAJAAN NEGERI':
                cat_no, cat = None, st
                prev_was_row = False
                continue
            label, vals = split_label_vals(st)
            if len(vals) == 4:
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
            if prev_was_row and recs:
                recs[-1]['label'] += ' ' + label
            elif pending_label is not None:
                pending_label += ' ' + label
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
        rows.append(prov(dict(base, year=YEAR, pembangunan_rm=amt(v[0]), amanah_rm=amt(v[1]),
                              baki_belum_selesai_rm=amt(v[2])), r['pdf_page'], r['printed_page'], stmt))
        rows.append(prov(dict(base, year=PRIOR, pembangunan_rm=None, amanah_rm=None,
                              baki_belum_selesai_rm=amt(v[3])), r['pdf_page'], r['printed_page'], stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_loans_receivable.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 3. Lampiran 6: Hutang Persekutuan (Pinjaman pdf 266-267; Bantuan 268-269)
# ---------------------------------------------------------------------------
def extract_debt_issues():
    rows = []
    stmt = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Pinjaman)'
    pageinfo = {266: 250, 267: 251}
    region, instrument = None, None
    def add(pno, pp, **kw):
        base = dict(region_bm=None, instrument_bm=None, lender_bm=None, no_keluaran=None,
                    kod_saham=None, perihal_bm=None, kadar_faedah=None, tarikh_tebusan=None,
                    ccy=None, amaun_dibenarkan_fx=None, terkumpul_keluaran_fx=None,
                    terkumpul_bayaran_balik_fx=None, amaun_belum_selesai_fx=None,
                    amaun_dibenarkan_rm=None, amaun_belum_selesai_rm=None,
                    row_type='detail', has_footnote=False, year=YEAR)
        statement = kw.pop('statement', stmt)
        base.update(kw)
        rows.append(prov(base, pno, pp, statement))
    for pno, pp in pageinfo.items():
        for line in page_lines(pno):
            st = re.sub(r'\s+', ' ', line.strip())
            if st in ('DALAM NEGERI', 'LUAR NEGERI', 'LUAR NEGERI RM'):
                region = st.split()[0] + (' NEGERI' if 'NEGERI' in st else '')
                region = 'DALAM NEGERI' if st.startswith('DALAM') else 'LUAR NEGERI'
                continue
            st = re.sub(r'\s*\(Samb\.?\)\s*$', '', st)
            if st in ('TERBITAN PELABURAN KERAJAAN', 'SEKURITI KERAJAAN MALAYSIA',
                      'SUKUK PERUMAHAN KERAJAAN', 'PINJAMAN PASARAN'):
                instrument = st
                continue
            if st.startswith('No. Keluaran') or st.startswith('Kadar') \
               or st.startswith('Perihal') or st.startswith('Faedah') or st.startswith('Tebusan') \
               or st.startswith('Amaun') or st.startswith('Dibenarkan') or st.startswith('Belum Selesai') \
               or st.startswith('Tarikh'):
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
                    kw['amaun_dibenarkan_rm'] = amt(vals[0]) if vals[0] != DASH else None
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
            # LUAR NEGERI market loans: '2011 Sukuk Wakala Global USD 0.8 Bilion 4.646
            # 06.07.2021 USD 800,000,000 3,213,600,000.00'
            m = re.match(r'^(\d{4}) (.+?) (\d\.\d{3}) (\d{2}\.\d{2}\.\d{4}) ([A-Z]{3}) ([\d,]+(?:\.\d{2})?) ([\d,]+\.\d{2})$', st)
            if m and instrument == 'PINJAMAN PASARAN':
                add(pno, pp, region_bm=region, instrument_bm=instrument,
                    perihal_bm=m.group(1) + ' ' + m.group(2),
                    kadar_faedah=m.group(3), tarikh_tebusan=m.group(4), ccy=m.group(5),
                    amaun_dibenarkan_fx=amt(m.group(6)), amaun_belum_selesai_rm=amt(m.group(7)))
                continue
            raise ValueError(f'unparsed p{pno}: {st!r}')
    # --- (b) Bantuan Luar Negeri, pdf 268-269 ---
    stmt_b = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Bantuan Luar Negeri)'
    section, lender, ccy = None, None, None
    lender_fn = False
    CCYHDR = re.compile(r'^(.*?)\s*(\(\s*[a-z]\s*\))?\s+([A-Z]{3})( +[A-Z]{3}){3}$')
    pending = None
    for pno, pp in ((268, 252), (269, 253)):
        in_nota = False
        for line in page_lines(pno):
            st = re.sub(r'\s+', ' ', line.strip())
            if in_nota:
                continue
            if st.startswith('Nota'):
                in_nota = True
                continue
            if st in ('PINJAMAN MULTILATERAL', 'PINJAMAN BILATERAL', 'PINJAMAN BILATERAL - (SAMB.)'):
                section = st.replace(' - (SAMB.)', '')
                continue
            if st.startswith(('Perihal', 'Kadar', 'Tarikh', 'Amaun', 'Jumlah Terkumpul',
                              'Mata Wang', 'Faedah', 'Tebusan', 'Keluaran', 'Bayaran Balik',
                              'Belum Selesai', 'Ringgit Malaysia')):
                continue
            m = CCYHDR.match(st)
            if m and not st.startswith('Jumlah') and not re.match(r'^\d{4} ', st):
                lender = m.group(1).strip()
                lender_fn = bool(m.group(2))
                ccy = m.group(3)
                continue
            label, vals = split_label_vals(st, is_valx)
            if label.startswith('JUMLAH'):
                rt = 'total' if label == 'JUMLAH BANTUAN LUAR NEGERI' else 'subtotal'
                add(pno, pp, statement=stmt_b, region_bm=None if rt == 'total' else section,
                    perihal_bm=label, row_type=rt, amaun_belum_selesai_rm=amt(vals[-1]))
                continue
            if label.startswith('Jumlah '):
                assert len(vals) == 5, st
                add(pno, pp, statement=stmt_b, region_bm=section, lender_bm=lender, ccy=ccy,
                    perihal_bm=label, row_type='subtotal',
                    amaun_dibenarkan_fx=amt(vals[0]), terkumpul_keluaran_fx=amt(vals[1]),
                    terkumpul_bayaran_balik_fx=amt(vals[2]), amaun_belum_selesai_fx=amt(vals[3]),
                    amaun_belum_selesai_rm=amt(vals[4]), has_footnote=lender_fn)
                continue
            head = ' '.join(st.split()[:len(st.split()) - len(vals)])
            m = re.match(r'^(.+?) (\d\.\d{2,3}|-|Berubah|\d+\.\d{2}-\d+\.\d{2}) (\d{4}/\d{4})$', head)
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
# 4. Lampiran 7: PFI (pdf 273)
# ---------------------------------------------------------------------------
def extract_pfi():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Inisiatif Pembiayaan Swasta'
    pno, pp = 273, 257
    rows = []
    agensi = None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if st.startswith(('Agensi / Tranche', 'Kadar', 'Faedah', 'Keluaran', 'Matang',
                          'Amaun', 'Asal', '2020 2019')):
            continue
        label, vals = split_label_vals(st)
        if not vals:
            if not label.startswith('Jumlah') and not label.startswith('JUMLAH'):
                agensi = label
            continue
        def emit(base, vy, vp):
            for y, v in ((YEAR, vy), (PRIOR, vp)):
                rows.append(prov(dict(base, year=y, amaun_belum_selesai_rm=amt(v)), pno, pp, stmt))
        if label.startswith('- '):
            m = re.match(r'^- (.+?) (\d\.\d{3}) (\d{4}) (\d{4})$', label)
            assert m and len(vals) == 3, st
            emit(dict(agensi_bm=agensi, tranche_bm=m.group(1), kadar_faedah_pct=m.group(2),
                      tahun_keluaran=m.group(3), tahun_matang=m.group(4),
                      amaun_pinjaman_asal_rm=amt(vals[0]), row_type='detail'),
                 vals[1], vals[2])
        elif label.startswith('Jumlah '):
            assert len(vals) == 3, st
            emit(dict(agensi_bm=agensi, tranche_bm=label, kadar_faedah_pct=None,
                      tahun_keluaran=None, tahun_matang=None,
                      amaun_pinjaman_asal_rm=amt(vals[0]), row_type='subtotal'),
                 vals[1], vals[2])
        elif label.startswith('JUMLAH'):
            assert len(vals) == 3, st
            emit(dict(agensi_bm=None, tranche_bm=label, kadar_faedah_pct=None,
                      tahun_keluaran=None, tahun_matang=None,
                      amaun_pinjaman_asal_rm=amt(vals[0]), row_type='total'),
                 vals[1], vals[2])
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_pfi_liabilities.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 5a. Lampiran 8: Komitmen Jaminan (pdf 276) / Lampiran 11 (pdf 289) share shape
# ---------------------------------------------------------------------------
def extract_dn_ln_table(pno, pp, stmt, out_csv, type_headers=()):
    rows = []
    jenis, cat = None, None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        st = re.sub(r'( RM)+$', '', st)
        if st.startswith(('Agensi', 'Dalam Negeri', 'Luar Negeri', f'Jumlah {YEAR}', f'{YEAR} {PRIOR}')) \
           or st == 'Jumlah':
            continue
        label, vals = split_label_vals(st)
        if not vals:
            if label in type_headers:
                jenis, cat = label, None
            else:
                cat = label
            continue
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
        rows.append(prov(dict(base, year=YEAR, dalam_negeri_rm=amt(vals[0]),
                              luar_negeri_rm=amt(vals[1]), jumlah_rm=amt(vals[2])), pno, pp, stmt))
        rows.append(prov(dict(base, year=PRIOR, dalam_negeri_rm=None,
                              luar_negeri_rm=None, jumlah_rm=amt(vals[3])), pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/{out_csv}', index=False)
    return df

# ---------------------------------------------------------------------------
# 5b. Penyaluran Geran Bayaran Balik Pinjaman (pdf 277)
# ---------------------------------------------------------------------------
def extract_grants():
    stmt = 'Penyata Penyaluran Geran Bayaran Balik Pinjaman'
    pno, pp = 277, 261
    rows = []
    cat = None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if st.startswith(('Agensi', 'Amaun Penyaluran', '2020 2019', 'Nota')) or re.match(r'^\(\s*\d\s*\)', st):
            continue
        label, vals = split_label_vals(st)
        if not vals:
            cat = label
            continue
        assert len(vals) == 2, st
        rt = 'detail'
        c = cat
        if label.startswith('Jumlah '):
            rt = 'subtotal'
        elif label.startswith('JUMLAH'):
            rt, c = 'total', None
        base = dict(peruntukan_bm=c, agensi_bm=label, row_type=rt)
        rows.append(prov(dict(base, year=YEAR, amaun_penyaluran_rm=amt(vals[0])), pno, pp, stmt))
        rows.append(prov(dict(base, year=PRIOR, amaun_penyaluran_rm=amt(vals[1])), pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_guarantee_repayment_grants.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 6. Lampiran 9: Komitmen Pajakan Kewangan (pdf 281, single page)
# ---------------------------------------------------------------------------
def extract_leases():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Komitmen Pajakan Kewangan'
    pageinfo = {281: 265}
    rows = []
    sector, cat_no, cat = None, None, None
    pending = None
    def emit(label, vals, fn, rt, c_no, c, pno, pp):
        base = dict(sektor_bm=sector if rt != 'total' else None, category_no=c_no,
                    kategori_bm=c, perihal_bm=label, row_type=rt, has_footnote=fn)
        rows.append(prov(dict(base, year=YEAR, amaun_belum_selesai_rm=amt(vals[0])), pno, pp, stmt))
        rows.append(prov(dict(base, year=PRIOR, amaun_belum_selesai_rm=amt(vals[1])), pno, pp, stmt))
    for pno, pp in pageinfo.items():
        in_nota = False
        for line in page_lines(pno):
            st = re.sub(r'\s+', ' ', line.strip())
            if in_nota:
                continue
            if st.startswith('Nota'):
                in_nota = True
                continue
            if st.startswith(('Perihal', 'Amaun Belum Selesai', '2020 2019')):
                continue
            if st.startswith('PAJAKAN KEWANGAN'):
                sector = re.sub(r'( RM)+$', '', st)
                cat_no, cat = None, None
                continue
            label, vals = split_label_vals(st)
            fn = False
            m = re.match(r'^(.*?)\s*\*$', label)
            if m and m.group(1):
                label, fn = m.group(1), True
            if not vals:
                if label and not label.startswith(('Jumlah', 'JUMLAH')):
                    if len(label.split()) <= 3 and label == label.title():
                        cat = label     # e.g. 'Bangunan'
                    else:
                        pending = (label, fn)
                continue
            assert len(vals) == 2, st
            if not label and pending:
                label, fn = pending[0], pending[1] or fn
            pending = None
            rt, c_no, c = 'detail', cat_no, cat
            if label.startswith('Jumlah Pajakan Kewangan'):
                rt, c_no, c = 'subtotal', None, None
            elif label.startswith('Jumlah '):
                rt = 'subtotal'
            elif label.startswith('JUMLAH'):
                rt, c_no, c = 'total', None, None
            emit(label, vals, fn, rt, c_no, c, pno, pp)
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_finance_leases.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 7. Lampiran 10: Komitmen Pampasan (pdf 285) -- highway concessions only in 2020
# ---------------------------------------------------------------------------
def extract_compensation():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Komitmen Pampasan'
    pno, pp = 285, 269
    rows = []
    cat = None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if st.startswith(('Perihal', 'Amaun Belum Selesai', '2020 2019', 'Nota')):
            continue
        label, vals = split_label_vals(st)
        if not vals:
            cat = label
            continue
        assert len(vals) == 2, st
        rt, c = 'detail', cat
        if label.startswith('Jumlah '):
            rt = 'subtotal'
        elif label.startswith('JUMLAH'):
            rt, c = 'total', None
        base = dict(kategori_bm=c, perihal_bm=label, row_type=rt, has_footnote=False)
        rows.append(prov(dict(base, year=YEAR, amaun_belum_selesai_rm=amt(vals[0])), pno, pp, stmt))
        rows.append(prov(dict(base, year=PRIOR, amaun_belum_selesai_rm=amt(vals[1])), pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_compensation_commitments.csv', index=False)
    return df

if __name__ == '__main__':
    d1 = extract_loans()
    print('loans_receivable', len(d1))
    d3 = extract_debt_issues()
    print('debt_issues', len(d3))
    d4 = extract_pfi()
    print('pfi', len(d4))
    d5a = extract_dn_ln_table(276, 260, 'Penyata Akaun Memorandum Liabiliti - Komitmen Jaminan',
                              'fact_guarantees.csv')
    print('guarantees', len(d5a))
    d5b = extract_grants()
    print('grants', len(d5b))
    d6 = extract_leases()
    print('leases', len(d6))
    d7 = extract_compensation()
    print('compensation', len(d7))
    d8 = extract_dn_ln_table(289, 273, 'Penyata Akaun Memorandum Jaminan Berkanun',
                             'fact_statutory_guarantees.csv',
                             type_headers=('JAMINAN PENCARUM / PENDEPOSIT', 'JAMINAN PINJAMAN'))
    print('statutory_guarantees', len(d8))
