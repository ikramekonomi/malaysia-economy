#!/usr/bin/env python3
"""Extract memorandum register tables (Lampiran 3, 5-10) from PKKP 2019 text layer.

Adapted from the proven 2020 pipeline (printed = pdf - 12).

Outputs (to ../warehouse2019/):
  fact_loans_receivable.csv           pdf 215-217  Lampiran 3 -- categories I-VII
                                                   (VII PERSEORANGAN new in 2019);
                                                   p216 prints one row split across
                                                   a '(disambung...)' wrap (repaired)
  fact_debt_issues.csv                pdf 227-228  Lampiran 5 (Pinjaman) -- DALAM
                                                   NEGERI: BP / TPK / SKM / SUKUK
                                                   PERUMAHAN KERAJAAN; LUAR NEGERI
                                                   market loans incl. 2019 Bon
                                                   Samurai JPY 200 Billion
                                      pdf 229-230  Lampiran 5 (Bantuan Luar Negeri)
  fact_pfi_liabilities.csv            pdf 233      Lampiran 6 -- 2019 format prints
                                                   by KATEGORI (Inisiatif Pembiayaan
                                                   Swasta (PFI) / Aktiviti Pembangunan
                                                   Khas Pembiayaan Swasta) with agensi
                                                   sub-headers and '*' restructuring
                                                   footnotes -> kategori_bm +
                                                   has_footnote columns added
  fact_guarantees.csv                 pdf 237      Lampiran 7 (flat agency list)
  fact_finance_leases.csv             pdf 241      Lampiran 8 (single page)
  fact_compensation_commitments.csv   pdf 245      Lampiran 9 (highway concessions)
  fact_statutory_guarantees.csv       pdf 249      Lampiran 10

NO 'Penyata Penyaluran Geran Bayaran Balik Pinjaman' is printed in the 2019
volume (grants exist only as narrative notes) -> no
fact_guarantee_repayment_grants.csv this year (absence reported).

fact_investments.csv (pdf 221-224) is produced by extract_investments.py.
"""
import re
import pandas as pd

WORK = '/home/claude/pkkp/work/2019'
WH = '/home/claude/pkkp/warehouse2019'
SRC = '2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2019
PRIOR = 2018

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
    re.compile(r'^\d+ Teks Lampiran'),
    re.compile(r'^20/10/2020'),
    re.compile(r'^\W+$'),
]

def page_lines(pno):
    raw = pages[pno - 1].split('\n')
    out = []
    for ln in raw:
        s = ln.replace('!', ' ').rstrip()   # 2019 header glyph noise ('Perihal!', '2019!', trailing '... !')
        s = re.sub(r'\s+PENYAT\s*A?\s+KEWANGAN.*$', '', s)   # page-edge sidebar caption glued to rows
        s = re.sub(r'\s+PENYAT\s*$', '', s)
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
# 1. Lampiran 3: Pinjaman dan Pendahuluan Boleh Dituntut (pdf 215-217)
# ---------------------------------------------------------------------------
def extract_loans():
    stmt = 'Penyata Akaun Memorandum Pinjaman dan Pendahuluan Boleh Dituntut'
    pageinfo = {215: 203, 216: 204, 217: 205}
    recs = []
    section = None
    cat_no, cat = None, None
    pending_label = None
    HDR_SKIP = re.compile(r'^(Peminjam|Baki Pinjaman Mengikut|Pembangunan\s+Amanah|Baki Belum Selesai)')
    for pno, pp in pageinfo.items():
        prev_was_row = False
        in_nota = False
        lines = page_lines(pno)
        # p216 print wrap: 'Syarikat Bekalan Air Selangor Sdn. Bhd.' prints 3 values,
        # '(disambung...)', then the 2018 value alone on the NEXT line. Rejoin.
        fixed = []
        for ln in lines:
            st = ln.strip()
            st = re.sub(r'\s*\(disambung\.{0,3}\)\s*$', '', st)
            if not st or re.fullmatch(r'\d{1,4}', st):
                continue    # page footer number sharing a line with '(disambung...)'
            if fixed and re.fullmatch(r'\(?[\d,]+\.\d{2}\)?', st):
                plabel, pvals = split_label_vals(fixed[-1].strip())
                if plabel and len(pvals) == 3:
                    print(f'.. rejoined wrapped 2018 value on p{pno}: {plabel[:45]!r} + {st}')
                    fixed[-1] = fixed[-1] + ' ' + st
                    continue
            fixed.append(ln if st == ln.strip() else ' ' * 10 + st)
        for line in fixed:
            st = line.strip()
            if in_nota:
                continue
            if st.startswith('Nota'):
                in_nota = True
                continue
            if HDR_SKIP.match(st):
                continue
            if st == 'DITUNTUT' and pending_label is None and not prev_was_row:
                continue    # wrap of the page-top 'LAMPIRAN 3 - ... BOLEH / DITUNTUT' title
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
            m = re.match(r'^([A-Z][A-Z ]+?)\s*-?\s*\(SAMB\.?\)$', st)
            if m:   # category continuation header, e.g. 'SYARIKAT- (SAMB.)'
                if cat is None or m.group(1).strip() != cat:
                    cat = m.group(1).strip()
                prev_was_row = False
                continue
            label, vals = split_label_vals(st)
            label = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', label).strip()
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
# 2. Lampiran 5: Hutang Persekutuan (Pinjaman pdf 227-228; Bantuan 229-230)
# ---------------------------------------------------------------------------
def extract_debt_issues():
    rows = []
    stmt = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Pinjaman)'
    pageinfo = {227: 215, 228: 216}
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
            # LUAR NEGERI market loans: '2019 Bon Samurai JPY 200 Billion 0.530
            # 15.03.2029 JPY 200,000,000,000 7,612,600,000.00'
            m = re.match(r'^(\d{4}) (.+?) (\d\.\d{3}) (\d{2}\.\d{2}\.\d{4}) ([A-Z]{3}) ([\d,]+(?:\.\d{2})?) ([\d,]+\.\d{2})$', st)
            if m and instrument == 'PINJAMAN PASARAN':
                add(pno, pp, region_bm=region, instrument_bm=instrument,
                    perihal_bm=m.group(1) + ' ' + m.group(2),
                    kadar_faedah=m.group(3), tarikh_tebusan=m.group(4), ccy=m.group(5),
                    amaun_dibenarkan_fx=amt(m.group(6)), amaun_belum_selesai_rm=amt(m.group(7)))
                continue
            raise ValueError(f'unparsed p{pno}: {st!r}')
    # --- (b) Bantuan Luar Negeri, pdf 229-230 ---
    stmt_b = 'Penyata Akaun Memorandum Liabiliti - Hutang Persekutuan (Bantuan Luar Negeri)'
    section, lender, ccy = None, None, None
    lender_fn = False
    CCYHDR = re.compile(r'^(.*?)\s*(\(\s*[a-z]\s*\))?\s+([A-Z]{3})( +[A-Z]{3}){3}$')
    for pno, pp in ((229, 217), (230, 218)):
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
                              'Belum Selesai', 'Ringgit Malaysia', '( d )', '(d)')):
                continue
            # glued kadar repair ('...Institut Teknologi0.01-2.00 2021/2042 ...')
            st = re.sub(r'([a-z])(\d+\.\d{2}-\d+\.\d{2}) ', r'\1 \2 ', st)
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
# 3. Lampiran 6: PFI (pdf 233) -- 2019 category format
# ---------------------------------------------------------------------------
def extract_pfi():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Inisiatif Pembiayaan Swasta'
    pno, pp = 233, 221
    rows = []
    kategori, agensi = None, None
    KATS = ('Inisiatif Pembiayaan Swasta (PFI)', 'Aktiviti Pembangunan Khas Pembiayaan Swasta')
    in_nota = False
    def emit(base, vy, vp, fn):
        for y, v in ((YEAR, vy), (PRIOR, vp)):
            rows.append(prov(dict(base, year=y, amaun_belum_selesai_rm=amt(v),
                                  has_footnote=fn), pno, pp, stmt))
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if in_nota:
            continue
        if st.startswith('Nota'):
            in_nota = True
            continue
        if st.startswith(('Agensi / Tranche', 'Kadar', 'Faedah', 'Keluaran', 'Matang',
                          'Amaun', 'Asal', '2019 2018', 'Tahun')):
            continue
        if st in KATS:
            kategori = st
            agensi = None
            continue
        fn = ' * ' in f' {st} ' or st.endswith('*')
        st_clean = st.replace(' * ', ' ').rstrip('*').strip()
        if st_clean.startswith('- '):
            # tranche row: label | kadar | tahun keluaran | tahun matang | asal | 2019 | 2018
            m = re.match(rf'^- (.+?) (\d\.\d{{3}}) (\d{{4}}|{DASH}) (\d{{4}}|{DASH}) '
                         rf'([\d,.]+|{DASH}) ([\d,.]+|{DASH}) ([\d,.]+|{DASH})$', st_clean)
            assert m, st
            emit(dict(kategori_bm=kategori, agensi_bm=agensi, tranche_bm=m.group(1),
                      kadar_faedah_pct=m.group(2),
                      tahun_keluaran=None if m.group(3) == DASH else m.group(3),
                      tahun_matang=None if m.group(4) == DASH else m.group(4),
                      amaun_pinjaman_asal_rm=amt(m.group(5)), row_type='detail'),
                 m.group(6), m.group(7), fn)
            continue
        toks = st_clean.split()
        vals = []
        while toks and (toks[-1] == DASH or AMT.match(toks[-1])):
            vals.insert(0, toks.pop())
        label = ' '.join(toks)
        if not vals:
            if not label.startswith(('Jumlah', 'JUMLAH')):
                agensi = label
            continue
        elif label.startswith('Jumlah '):
            assert len(vals) == 3, st
            emit(dict(kategori_bm=kategori, agensi_bm=None, tranche_bm=label,
                      kadar_faedah_pct=None, tahun_keluaran=None, tahun_matang=None,
                      amaun_pinjaman_asal_rm=amt(vals[0]), row_type='subtotal'),
                 vals[1], vals[2], fn)
        elif label.startswith('JUMLAH'):
            assert len(vals) == 3, st
            emit(dict(kategori_bm=None, agensi_bm=None, tranche_bm=label,
                      kadar_faedah_pct=None, tahun_keluaran=None, tahun_matang=None,
                      amaun_pinjaman_asal_rm=amt(vals[0]), row_type='total'),
                 vals[1], vals[2], fn)
        else:
            raise ValueError(f'unparsed pfi p{pno}: {st!r}')
    df = pd.DataFrame(rows, columns=['kategori_bm', 'agensi_bm', 'tranche_bm', 'kadar_faedah_pct',
                                     'tahun_keluaran', 'tahun_matang', 'amaun_pinjaman_asal_rm',
                                     'row_type', 'year', 'amaun_belum_selesai_rm', 'has_footnote',
                                     'source_file', 'pdf_page', 'printed_page', 'statement'])
    df.to_csv(f'{WH}/fact_pfi_liabilities.csv', index=False)
    return df

# ---------------------------------------------------------------------------
# 4. Lampiran 7: Komitmen Jaminan (pdf 237) / Lampiran 10 (pdf 249) share shape
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
# 5. Lampiran 8: Komitmen Pajakan Kewangan (pdf 241, single page)
# ---------------------------------------------------------------------------
def extract_leases():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Komitmen Pajakan Kewangan'
    pageinfo = {241: 229}
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
            if st.startswith(('Perihal', 'Amaun Belum Selesai', '2019 2018', '2019', '2018')):
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
# 6. Lampiran 9: Komitmen Pampasan (pdf 245) -- highway concessions only
# ---------------------------------------------------------------------------
def extract_compensation():
    stmt = 'Penyata Akaun Memorandum Liabiliti - Komitmen Pampasan'
    pno, pp = 245, 233
    rows = []
    cat = None
    for line in page_lines(pno):
        st = re.sub(r'\s+', ' ', line.strip())
        if st.startswith(('Perihal', 'Amaun Belum Selesai', '2019 2018', '2019', '2018', 'Nota')):
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
    d5a = extract_dn_ln_table(237, 225, 'Penyata Akaun Memorandum Liabiliti - Komitmen Jaminan',
                              'fact_guarantees.csv')
    print('guarantees', len(d5a))
    d6 = extract_leases()
    print('leases', len(d6))
    d7 = extract_compensation()
    print('compensation', len(d7))
    d8 = extract_dn_ln_table(249, 237, 'Penyata Akaun Memorandum Jaminan Berkanun',
                             'fact_statutory_guarantees.csv',
                             type_headers=('JAMINAN PENCARUM / PENDEPOSIT', 'JAMINAN PINJAMAN'))
    print('statutory_guarantees', len(d8))
    print("NOTE: no 'Penyata Penyaluran Geran Bayaran Balik Pinjaman' printed in the 2019 volume "
          "-> fact_guarantee_repayment_grants.csv not produced (absence, not an omission)")
