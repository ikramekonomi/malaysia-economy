#!/usr/bin/env python3
"""Self-validation for the 2016 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2016 volume's own pages. Reports PASS/FAIL; never adjusts data.

2016 layout notes:
 - fact_loans_receivable (Lampiran 3): FIVE value columns (Pembangunan / Hasil
   Disatukan / Amanah Lain / Baki 2016 / Baki 2015); per-row identity
   pembangunan+hasil+amanah_lain = baki 2016.
 - fact_debt_issues (Lampiran 5): DN instruments BP / TPK / SKM / Sukuk
   Perumahan Kerajaan; LN Pinjaman Pasaran carries a USD column.
 - fact_statutory_guarantees (Lampiran 6): JAMINAN PENCARUM / PENDEPOSIT +
   JAMINAN PINJAMAN with Badan Berkanun / Syarikat kategori.
 - NO Komitmen Jaminan / finance-lease / PFI / grants / compensation registers
   exist in this volume.
 - controls are printed register totals, sen precision.
"""
import pandas as pd

WH = '/home/claude/pkkp/warehouse2016'
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2016, 2015):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'hasil_disatukan_rm', 'amanah_lain_rm'] if y == 2016 else [])
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].category_bm.dropna().unique():
        for c in cols:
            det = s(dy, (dy.row_type == 'detail') & (dy.category_bm == cat) & (dy.section_bm == 'PINJAMAN'), c)
            sub = dy[(dy.row_type == 'subtotal') & (dy.category_bm == cat) & (dy.section_bm == 'PINJAMAN')][c]
            if len(sub):
                check(f'loans: {cat} detail={c} = Jumlah {cat} ({y})', det, sub.iloc[0])
    for c in cols:
        subs = s(dy, (dy.row_type == 'subtotal') & (dy.peminjam_bm.str.startswith('Jumlah')) & (dy.section_bm == 'PINJAMAN'), c)
        jp = dy[(dy.peminjam_bm == 'JUMLAH PINJAMAN')][c].iloc[0]
        check(f'loans: sum(category subtotals)={c} = JUMLAH PINJAMAN ({y})', subs, jp)
        pend_det = s(dy, (dy.row_type == 'detail') & (dy.section_bm == 'PENDAHULUAN'), c)
        jpend = dy[(dy.peminjam_bm == 'JUMLAH PENDAHULUAN')][c].iloc[0]
        check(f'loans: pendahuluan details={c} = JUMLAH PENDAHULUAN ({y})', pend_det, jpend)
        gt = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'loans: JUMLAH PINJAMAN + PENDAHULUAN = grand total ({c},{y})', jp + jpend, gt)
d16 = df[(df.year == 2016) & (df.row_type == 'detail')]
bad = d16[(d16.pembangunan_rm + d16.hasil_disatukan_rm + d16.amanah_lain_rm - d16.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+hasil+amanah_lain = baki 2016 on every detail row (violations)', len(bad), 0)
check('loans: JUMLAH PINJAMAN 2016 = printed 54,739,970,827.61',
      df[(df.peminjam_bm == 'JUMLAH PINJAMAN') & (df.year == 2016)].baki_belum_selesai_rm.iloc[0], 54739970827.61)
check('loans: JUMLAH PENDAHULUAN 2016 = printed 1,073,523,687.32',
      df[(df.peminjam_bm == 'JUMLAH PENDAHULUAN') & (df.year == 2016)].baki_belum_selesai_rm.iloc[0], 1073523687.32)
check('loans: grand total 2016 = printed 55,813,494,514.93',
      df[(df.row_type == 'total') & (df.year == 2016)].baki_belum_selesai_rm.iloc[0], 55813494514.93)
check('loans: grand total 2015 = printed 106,821,651,022.37',
      df[(df.row_type == 'total') & (df.year == 2015)].baki_belum_selesai_rm.iloc[0], 106821651022.37)
check('loans: grand total 2016 = Nota 8 PPBD (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2016)].baki_belum_selesai_rm.iloc[0]), 55813494515, tol=1)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2016, 2015):
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
check('investments: Jumlah Syarikat 2016 = printed 29,668,857,833.74',
      df[(df.entiti_bm == 'Jumlah Syarikat') & (df.year == 2016)].nilai_buku_rm.iloc[0], 29668857833.74)
check('investments: JUMLAH PELABURAN 2016 = printed 30,926,284,938.72',
      df[(df.row_type == 'total') & (df.year == 2016)].nilai_buku_rm.iloc[0], 30926284938.72)
check('investments: JUMLAH PELABURAN 2015 = printed 30,316,159,988.72',
      df[(df.row_type == 'total') & (df.year == 2015)].nilai_buku_rm.iloc[0], 30316159988.72)
check('investments: JUMLAH PELABURAN 2016 = Nota 8(b) (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2016)].nilai_buku_rm.iloc[0]), 30926284939, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl_dib, ctrl_bs in [('TERBITAN PELABURAN KERAJAAN', 234500000000, 234500000000),
                                ('SEKURITI KERAJAAN MALAYSIA', 359652726000, 357421726000),
                                ('SUKUK PERUMAHAN KERAJAAN', 28400000000, 28400000000)]:
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
check('debt: PINJAMAN PASARAN = control 17,211,340,000 (Nota 9(a))', sub, 17211340000)
detf = s(pp, pp.row_type == 'detail', 'amaun_dibenarkan_fx')
subf = pp[pp.row_type == 'subtotal'].amaun_dibenarkan_fx.iloc[0]
check('debt: PINJAMAN PASARAN USD sum = printed Jumlah (USD 3.8b)', detf, subf)
check('debt: PINJAMAN PASARAN USD control 3,800,000,000.00', subf, 3800000000.00)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = control 4.5b', bp, 4500000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM+Sukuk = Jumlah Dalam Negeri', bp + 234500000000 + 357421726000 + 28400000000, jdn)
check('debt: Jumlah Dalam Negeri = control 624,821,726,000 (Nota 9(a))', jdn, 624821726000)
check('debt: Jumlah Dalam Negeri dibenarkan = printed 630,552,726,000.00',
      dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_dibenarkan_rm.iloc[0], 630552726000.00)
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri', sub, jln)
check('debt: Dalam + Luar = JUMLAH PINJAMAN', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = control 642,033,066,000', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 642033066000)

bl = df[df.statement.str.contains('Bantuan')]
for lender in bl.lender_bm.dropna().unique():
    for c in ['amaun_dibenarkan_fx', 'terkumpul_keluaran_fx', 'terkumpul_bayaran_balik_fx',
              'amaun_belum_selesai_fx', 'amaun_belum_selesai_rm']:
        det = s(bl, (bl.row_type == 'detail') & (bl.lender_bm == lender), c)
        sub = bl[(bl.row_type == 'subtotal') & (bl.lender_bm == lender)][c].iloc[0]
        check(f'debt/BLN: {lender} details = Jumlah ({c})', det, sub)
jm = bl[bl.perihal_bm == 'JUMLAH PINJAMAN MULTILATERAL'].amaun_belum_selesai_rm.iloc[0]
jb = bl[bl.perihal_bm == 'JUMLAH PINJAMAN BILATERAL'].amaun_belum_selesai_rm.iloc[0]
mlt = s(bl, (bl.row_type == 'subtotal') & (bl.region_bm == 'PINJAMAN MULTILATERAL')
       & bl.perihal_bm.str.startswith('Jumlah '), 'amaun_belum_selesai_rm')
check('debt/BLN: multilateral lender subtotals = JUMLAH MULTILATERAL', mlt, jm, tol=0.5)
check('debt/BLN: bilateral lender subtotals = JUMLAH BILATERAL',
      s(bl, (bl.row_type == 'subtotal') & (bl.region_bm == 'PINJAMAN BILATERAL') & bl.perihal_bm.str.startswith('Jumlah '), 'amaun_belum_selesai_rm'), jb, tol=0.5)
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], tol=0.5)
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = control 6,442,238,686.34', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 6442238686.34, tol=0.5)
check('debt/BLN: JUMLAH MULTILATERAL = control 498,540,785.89', jm, 498540785.89, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = control 5,943,697,900.45', jb, 5943697900.45, tol=0.5)
check('debt: JUMLAH PINJAMAN + BLN = Nota 9 HUTANG PERSEKUTUAN 648,475,304,686 (rounded)',
      dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
      + bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 648475304686.34, tol=1.0)

# --- fact_statutory_guarantees ---------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2016, 2015):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2016 else [])
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
d16 = df[(df.year == 2016) & (df.row_type == 'detail')]
bad = d16[(d16.dalam_negeri_rm + d16.luar_negeri_rm - d16.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2016 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2016 = control 985,103,411,469.47',
      df[(df.row_type == 'total') & (df.year == 2016)].jumlah_rm.iloc[0], 985103411469.47, tol=0.5)
check('statutory: JUMLAH JAMINAN 2015 = control 920,336,791,310.19',
      df[(df.row_type == 'total') & (df.year == 2015)].jumlah_rm.iloc[0], 920336791310.19, tol=0.5)
check('statutory: pinjaman total 2016 = Nota 10(a) 187,234,195,606',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2016)].jumlah_rm.iloc[0], 187234195606.31, tol=0.5)
check('statutory: pencarum total 2016 = Nota 10(b) 797,869,215,863',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2016)].jumlah_rm.iloc[0], 797869215863.16, tol=0.5)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2016.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
