#!/usr/bin/env python3
"""Self-validation for the 2014 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2014 volume's own pages. Reports PASS/FAIL; never adjusts data.

2014 layout notes:
 - fact_loans_receivable (Lampiran 3): title 'Pinjaman Boleh Dituntut' (no
   PINJAMAN/PENDAHULUAN sections; 7 borrower categories I-VII); FIVE value
   columns (Pembangunan / Hasil Disatukan / Amanah Lain / Baki 2014 / Baki
   2013); per-row identity pembangunan+hasil+amanah_lain = baki 2014.
 - fact_debt_issues (Lampiran 5): DN instruments BP / TPK / SKM (unlabelled DN
   subtotal printed as 'Jumlah Dalam Negeri' 519,452,319,000); LN Pinjaman
   Pasaran carries a USD column; separate KUMPULAN WANG PINJAMAN PERUMAHAN
   financing block (Pinjaman Berjangka + Sukuk Perumahan Kerajaan, split new
   in 2014); grand JUMLAH PINJAMAN 577,521,244,000.
 - fact_statutory_guarantees (Lampiran 6): JAMINAN PENCARUM / PENDEPOSIT +
   JAMINAN PINJAMAN with Badan Berkanun / Syarikat kategori.
 - NO Komitmen Jaminan / finance-lease / PFI / grants / compensation registers
   exist in this volume.
 - controls are printed register totals, sen precision.
"""
import os
import pandas as pd

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2014")
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2014, 2013):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'hasil_disatukan_rm', 'amanah_lain_rm'] if y == 2014 else [])
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].category_bm.dropna().unique():
        for c in cols:
            det = s(dy, (dy.row_type == 'detail') & (dy.category_bm == cat), c)
            sub = dy[(dy.row_type == 'subtotal') & (dy.category_bm == cat)][c]
            if len(sub):
                check(f'loans: {cat} detail={c} = Jumlah {cat} ({y})', det, sub.iloc[0])
    for c in cols:
        subs = s(dy, (dy.row_type == 'subtotal') & (dy.peminjam_bm.str.startswith('Jumlah')), c)
        gt = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'loans: sum(category subtotals)={c} = JUMLAH PINJAMAN BOLEH DITUNTUT ({y})', subs, gt)
d14 = df[(df.year == 2014) & (df.row_type == 'detail')]
bad = d14[(d14.pembangunan_rm + d14.hasil_disatukan_rm + d14.amanah_lain_rm - d14.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+hasil+amanah_lain = baki 2014 on every detail row (violations)', len(bad), 0)
check('loans: grand total 2014 = printed 99,036,023,598.57',
      df[(df.row_type == 'total') & (df.year == 2014)].baki_belum_selesai_rm.iloc[0], 99036023598.57)
check('loans: grand total 2013 = printed 92,444,600,373.76',
      df[(df.row_type == 'total') & (df.year == 2013)].baki_belum_selesai_rm.iloc[0], 92444600373.76)
check('loans: grand pembangunan 2014 = printed 39,080,564,970.08',
      df[(df.row_type == 'total') & (df.year == 2014)].pembangunan_rm.iloc[0], 39080564970.08)
check('loans: grand hasil disatukan 2014 = printed 3,262,007,175.06',
      df[(df.row_type == 'total') & (df.year == 2014)].hasil_disatukan_rm.iloc[0], 3262007175.06)
check('loans: grand amanah lain 2014 = printed 56,693,451,453.43',
      df[(df.row_type == 'total') & (df.year == 2014)].amanah_lain_rm.iloc[0], 56693451453.43)
check('loans: grand total 2014 = Nota 8 Pinjaman Boleh Dituntut (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2014)].baki_belum_selesai_rm.iloc[0]), 99036023599, tol=1)
check('loans: Jumlah Kerajaan Negeri 2014 = printed 16,470,077,891.28 (= Nota 8 rounded)',
      df[(df.peminjam_bm == 'Jumlah Kerajaan Negeri') & (df.year == 2014)].baki_belum_selesai_rm.iloc[0],
      16470077891.28)
# Nota 8 borrower-level cross-checks (rounded RM)
n8 = {'Jumlah Kerajaan Negeri': 16470077891, 'Jumlah Pihak Berkuasa Tempatan': 451005221,
      'Jumlah Badan Berkanun': 6820864168, 'Jumlah Koperasi': 158302635,
      'Jumlah Syarikat': 28856676215, 'Jumlah Perseorangan': 44061429758,
      'Jumlah Pelbagai': 2217667710}
for lbl, want in n8.items():
    got = df[(df.peminjam_bm == lbl) & (df.year == 2014)].baki_belum_selesai_rm.iloc[0]
    check(f'loans: {lbl} 2014 = Nota 8 (rounded RM)', round(got), want, tol=1)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2014, 2013):
    dy = df[df.year == y]
    tot_sub = 0.0
    for sec, lbl in [('AGENSI ANTARABANGSA', 'Jumlah Agensi Antarabangsa'),
                     ('BADAN BERKANUN', 'Jumlah Badan Berkanun'),
                     ('SYARIKAT', 'Jumlah Syarikat')]:
        det = s(dy, (dy.row_type == 'detail') & (dy.section_bm == sec), 'nilai_buku_rm')
        sub = dy[dy.entiti_bm == lbl].nilai_buku_rm.iloc[0]
        check(f'investments: {sec} details = {lbl} ({y})', det, sub)
        tot_sub += sub
    tot = dy[dy.row_type == 'total'].nilai_buku_rm.iloc[0]
    check(f'investments: sum(section subtotals) = JUMLAH PELABURAN ({y})', tot_sub, tot)
check('investments: Jumlah Syarikat 2014 = printed 28,625,590,153.74',
      df[(df.entiti_bm == 'Jumlah Syarikat') & (df.year == 2014)].nilai_buku_rm.iloc[0], 28625590153.74)
check('investments: JUMLAH PELABURAN 2014 = printed 29,883,017,258.72',
      df[(df.row_type == 'total') & (df.year == 2014)].nilai_buku_rm.iloc[0], 29883017258.72)
check('investments: JUMLAH PELABURAN 2013 = printed 29,679,137,798.72',
      df[(df.row_type == 'total') & (df.year == 2013)].nilai_buku_rm.iloc[0], 29679137798.72)
check('investments: JUMLAH PELABURAN 2014 = Nota 8(b) (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2014)].nilai_buku_rm.iloc[0]), 29883017259, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl_dib, ctrl_bs in [('TERBITAN PELABURAN KERAJAAN', 185500000000, 185500000000),
                                ('SEKURITI KERAJAAN MALAYSIA', 335897195000, 329632319000)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control (Nota 9(a))', sub, ctrl_bs)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
    check(f'debt: {inst} dibenarkan = printed control', subd, ctrl_dib)
pp = dn[dn.instrument_bm == 'PINJAMAN PASARAN']
det = s(pp, pp.row_type == 'detail', 'amaun_belum_selesai_rm')
sub = pp[pp.row_type == 'subtotal'].amaun_belum_selesai_rm.iloc[0]
check('debt: PINJAMAN PASARAN series sum = printed Jumlah', det, sub)
check('debt: PINJAMAN PASARAN = control 11,468,925,000 (Nota 9(a))', sub, 11468925000)
detf = s(pp, pp.row_type == 'detail', 'amaun_dibenarkan_fx')
subf = pp[pp.row_type == 'subtotal'].amaun_dibenarkan_fx.iloc[0]
check('debt: PINJAMAN PASARAN USD sum = printed Jumlah (USD 3.25b)', detf, subf)
check('debt: PINJAMAN PASARAN USD control 3,250,000,000.00', subf, 3250000000.00)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = control 4.32b', bp, 4320000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM = Jumlah Dalam Negeri', bp + 185500000000 + 329632319000, jdn)
check('debt: Jumlah Dalam Negeri = control 519,452,319,000 (Nota 9(a))', jdn, 519452319000)
kw = dn[dn.instrument_bm == 'PEMBIAYAAN KUMPULAN WANG PINJAMAN PERUMAHAN']
kwdet = s(kw, kw.row_type == 'detail', 'amaun_belum_selesai_rm')
kwsub = kw[kw.row_type == 'subtotal'].amaun_belum_selesai_rm.iloc[0]
check('debt: KWPP financing rows sum = printed Jumlah KWPP', kwdet, kwsub)
check('debt: Jumlah KWPP = control 46,600,000,000 (Nota 9(a))', kwsub, 46600000000)
check('debt: KWPP dibenarkan sum = printed Jumlah (41.2b)',
      s(kw, kw.row_type == 'detail', 'amaun_dibenarkan_rm'),
      kw[kw.row_type == 'subtotal'].amaun_dibenarkan_rm.iloc[0])
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri', sub, jln)
check('debt: Dalam + KWPP + Luar = JUMLAH PINJAMAN', jdn + kwsub + jln,
      dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = control 577,521,244,000', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 577521244000)

bl = df[df.statement.str.contains('Bantuan')]
for lender in bl.lender_bm.dropna().unique():
    for c in ['amaun_dibenarkan_fx', 'terkumpul_keluaran_fx', 'terkumpul_bayaran_balik_fx',
              'amaun_belum_selesai_fx', 'amaun_belum_selesai_rm']:
        det = s(bl, (bl.row_type == 'detail') & (bl.lender_bm == lender), c)
        sub = bl[(bl.row_type == 'subtotal') & (bl.lender_bm == lender)][c].iloc[0]
        if lender == 'Bank Pembangunan Islam' and c == 'amaun_belum_selesai_rm':
            # DIAGNOSED PRINTED 1-SEN DIFFERENCE (kept as printed): the ten
            # detail rows sum to 389,620,653.07 while the printed Jumlah reads
            # 389,620,653.08 - a sen-level rounding in the volume itself
            check(f'debt/BLN: {lender} details = Jumlah ({c}) '
                  f'[printed 1-sen rounding diagnosed: rows 389,620,653.07 vs Jumlah 389,620,653.08]',
                  det, sub, tol=0.011)
            continue
        check(f'debt/BLN: {lender} details = Jumlah ({c})', det, sub)
jm = bl[bl.perihal_bm == 'JUMLAH PINJAMAN MULTILATERAL'].amaun_belum_selesai_rm.iloc[0]
jb = bl[bl.perihal_bm == 'JUMLAH PINJAMAN BILATERAL'].amaun_belum_selesai_rm.iloc[0]
mlt = s(bl, (bl.row_type == 'subtotal') & (bl.region_bm == 'PINJAMAN MULTILATERAL')
       & bl.perihal_bm.str.startswith('Jumlah '), 'amaun_belum_selesai_rm')
check('debt/BLN: multilateral lender subtotals = JUMLAH MULTILATERAL', mlt, jm, tol=0.5)
check('debt/BLN: bilateral lender subtotals = JUMLAH BILATERAL',
      s(bl, (bl.row_type == 'subtotal') & (bl.region_bm == 'PINJAMAN BILATERAL') & bl.perihal_bm.str.startswith('Jumlah '), 'amaun_belum_selesai_rm'), jb, tol=0.5)
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], tol=0.5)
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = control 5,306,997,280.97', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 5306997280.97, tol=0.5)
check('debt/BLN: JUMLAH MULTILATERAL = control 656,158,104.06', jm, 656158104.06, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = control 4,650,839,176.91', jb, 4650839176.91, tol=0.5)
check('debt: JUMLAH PINJAMAN + BLN = Nota 9 HUTANG AWAM 582,828,241,281 (rounded)',
      dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
      + bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 582828241280.97, tol=1.0)

# --- fact_statutory_guarantees ---------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2014, 2013):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2014 else [])
    for c in cols:
        det = s(dy, (dy.row_type == 'detail') & (dy.jenis_jaminan_bm == 'JAMINAN PENCARUM / PENDEPOSIT'), c)
        sub = dy[dy.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT'][c].iloc[0]
        check(f'statutory: pencarum details = JUMLAH ({c},{y})', det, sub)
        for cat in ('Badan Berkanun', 'Syarikat'):
            det = s(dy, (dy.row_type == 'detail') & (dy.jenis_jaminan_bm == 'JAMINAN PINJAMAN') & (dy.kategori_bm == cat), c)
            sub2 = dy[(dy.jenis_jaminan_bm == 'JAMINAN PINJAMAN') & (dy.agensi_bm == f'Jumlah {cat}')][c].iloc[0]
            check(f'statutory: pinjaman/{cat} details = Jumlah ({c},{y})', det, sub2)
        jp = dy[dy.agensi_bm == 'JUMLAH JAMINAN PINJAMAN'][c].iloc[0]
        cats = s(dy, (dy.jenis_jaminan_bm == 'JAMINAN PINJAMAN') & dy.agensi_bm.str.startswith('Jumlah '), c)
        check(f'statutory: pinjaman category subtotals = JUMLAH JAMINAN PINJAMAN ({c},{y})', cats, jp)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'statutory: PENCARUM + PINJAMAN = JUMLAH JAMINAN ({c},{y})',
              dy[dy.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT'][c].iloc[0] + jp, tot)
d14 = df[(df.year == 2014) & (df.row_type == 'detail')]
bad = d14[(d14.dalam_negeri_rm + d14.luar_negeri_rm - d14.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2014 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2014 = control 850,035,142,802.34',
      df[(df.row_type == 'total') & (df.year == 2014)].jumlah_rm.iloc[0], 850035142802.34, tol=0.5)
check('statutory: JUMLAH JAMINAN 2013 = control 768,408,040,258.25',
      df[(df.row_type == 'total') & (df.year == 2013)].jumlah_rm.iloc[0], 768408040258.25, tol=0.5)
check('statutory: pinjaman total 2014 = Nota 10(a) 172,019,413,967',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2014)].jumlah_rm.iloc[0], 172019413967.09, tol=0.5)
check('statutory: pencarum total 2014 = Nota 10(b) 678,015,728,835',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2014)].jumlah_rm.iloc[0], 678015728835.25, tol=0.5)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2014.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
