#!/usr/bin/env python3
"""Self-validation for the 2018 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2018 volume's own pages. Reports PASS/FAIL; never adjusts data.

2018 layout notes:
 - fact_guarantees (Lampiran 6) is a FLAT agency list (no kategori columns).
 - fact_debt_issues (Lampiran 5): DN instruments BP / TPK / SKM / Sukuk
   Perumahan Kerajaan; LN Pinjaman Pasaran carries a USD column (no per-row
   ccy token; ccy='USD' from the column header).
 - fact_finance_leases (Lampiran 7) is a single page whose sector subtotals
   print WITHOUT labels (perihal_bm empty, row_type='subtotal').
 - No PFI / grants / compensation registers exist in this volume.
 - controls are printed register totals, sen precision.
"""
import os
import pandas as pd

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2018")
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2018, 2017):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'amanah_rm'] if y == 2018 else [])
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
d18 = df[(df.year == 2018) & (df.row_type == 'detail')]
bad = d18[(d18.pembangunan_rm + d18.amanah_rm - d18.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+amanah = baki 2018 on every detail row (count of violations)', len(bad), 0)
check('loans: grand total 2018 = printed 57,901,325,821.16',
      df[(df.row_type == 'total') & (df.year == 2018)].baki_belum_selesai_rm.iloc[0], 57901325821.16)
check('loans: grand total 2017 = printed 58,443,750,297.51',
      df[(df.row_type == 'total') & (df.year == 2017)].baki_belum_selesai_rm.iloc[0], 58443750297.51)
check('loans: grand total 2018 = Nota 9 PPBD (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2018)].baki_belum_selesai_rm.iloc[0]), 57901325821, tol=1)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2018, 2017):
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
check('investments: JUMLAH PELABURAN 2018 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2018)].nilai_buku_rm.iloc[0]), 31058227719, tol=1)
check('investments: JUMLAH PELABURAN 2017 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2017)].nilai_buku_rm.iloc[0]), 30907727719, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl in [('TERBITAN PELABURAN KERAJAAN', 304300000000),
                   ('SEKURITI KERAJAAN MALAYSIA', 380345169000),
                   ('SUKUK PERUMAHAN KERAJAAN', 28400000000)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control total (Nota 10)', sub, ctrl)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
pp = dn[dn.instrument_bm == 'PINJAMAN PASARAN']
det = s(pp, pp.row_type == 'detail', 'amaun_belum_selesai_rm')
sub = pp[pp.row_type == 'subtotal'].amaun_belum_selesai_rm.iloc[0]
check('debt: PINJAMAN PASARAN series sum = printed Jumlah', det, sub)
check('debt: PINJAMAN PASARAN = control 15,906,420,000 (Nota 10)', sub, 15906420000)
detf = s(pp, pp.row_type == 'detail', 'amaun_dibenarkan_fx')
subf = pp[pp.row_type == 'subtotal'].amaun_dibenarkan_fx.iloc[0]
check('debt: PINJAMAN PASARAN USD sum = printed Jumlah (USD 3.8b)', detf, subf)
check('debt: PINJAMAN PASARAN USD control 3,800,000,000.00', subf, 3800000000.00)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = control 6.5b', bp, 6500000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM+Sukuk = Jumlah Dalam Negeri', bp + 304300000000 + 380345169000 + 28400000000, jdn)
check('debt: Jumlah Dalam Negeri = control 719,545,169,000', jdn, 719545169000)
check('debt: Jumlah Dalam Negeri dibenarkan = printed 720,026,169,000.00',
      dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_dibenarkan_rm.iloc[0], 720026169000.00)
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri', sub, jln)
check('debt: Dalam + Luar = JUMLAH PINJAMAN', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = control 735,451,589,000', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 735451589000)

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
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = control 5,597,125,484.13', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 5597125484.13, tol=0.5)
check('debt/BLN: JUMLAH MULTILATERAL = control 288,885,562.51', jm, 288885562.51, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = control 5,308,239,921.62', jb, 5308239921.62, tol=0.5)
check('debt: JUMLAH PINJAMAN + BLN = Nota 10 HUTANG PERSEKUTUAN 741,048,714,484 (rounded)',
      dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
      + bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 741048714484.13, tol=1.0)

# --- fact_guarantees (flat list) -------------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantees.csv')
for y in (2018, 2017):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2018 else [])
    for c in cols:
        det = s(dy, dy.row_type == 'detail', c)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'guarantees: details = JUMLAH KOMITMEN JAMINAN ({c},{y})', det, tot)
d18 = df[(df.year == 2018) & (df.row_type == 'detail')]
bad = d18[(d18.dalam_negeri_rm + d18.luar_negeri_rm - d18.jumlah_rm).abs() > 0.005]
check('guarantees: dalam+luar = jumlah 2018 per row (violations)', len(bad), 0)
check('guarantees: total 2018 = control 164,908,473,345.82', df[(df.row_type == 'total') & (df.year == 2018)].jumlah_rm.iloc[0], 164908473345.82, tol=0.5)
check('guarantees: total 2017 = control 139,749,167,987.30', df[(df.row_type == 'total') & (df.year == 2017)].jumlah_rm.iloc[0], 139749167987.30, tol=0.5)

# --- fact_finance_leases ---------------------------------------------------
df = pd.read_csv(f'{WH}/fact_finance_leases.csv')
for y in (2018, 2017):
    dy = df[df.year == y]
    for sek, subctrl in [('Pajakan Kewangan Kerajaan Persekutuan', {2018: 20008614752.50, 2017: 21302260692.90}),
                         ('Pajakan Kewangan Badan Berkanun', {2018: 11509273523.81, 2017: 12119680714.03})]:
        det = s(dy, (dy.row_type == 'detail') & (dy.sektor_bm == sek), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek)].amaun_belum_selesai_rm.iloc[0]
        check(f'leases: {sek} details = printed (unlabeled) subtotal ({y})', det, sub)
        check(f'leases: {sek} subtotal = control ({y})', sub, subctrl[y], tol=0.5)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'leases: sector subtotals = JUMLAH KOMITMEN PAJAKAN KEWANGAN ({y})', subs, tot)
check('leases: total 2018 = control 31,517,888,276.31', df[(df.row_type == 'total') & (df.year == 2018)].amaun_belum_selesai_rm.iloc[0], 31517888276.31, tol=0.5)
check('leases: total 2017 = control 33,421,941,406.93', df[(df.row_type == 'total') & (df.year == 2017)].amaun_belum_selesai_rm.iloc[0], 33421941406.93, tol=0.5)

# --- fact_statutory_guarantees ---------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2018, 2017):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2018 else [])
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
        check(f'statutory: PENCARUM + PINJAMAN = JUMLAH JAMINAN ({c},{y})', sub + jp, tot)
d18 = df[(df.year == 2018) & (df.row_type == 'detail')]
bad = d18[(d18.dalam_negeri_rm + d18.luar_negeri_rm - d18.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2018 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2018 = control 1,211,063,250,638.15',
      df[(df.row_type == 'total') & (df.year == 2018)].jumlah_rm.iloc[0], 1211063250638.15, tol=0.5)
check('statutory: JUMLAH JAMINAN 2017 = control 1,104,590,450,002.56',
      df[(df.row_type == 'total') & (df.year == 2017)].jumlah_rm.iloc[0], 1104590450002.56, tol=0.5)
check('statutory: pinjaman total 2018 = Nota 11(a) 266,468,479,030',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2018)].jumlah_rm.iloc[0], 266468479030.06, tol=0.5)
check('statutory: pencarum total 2018 = Nota 11(b) 944,594,771,608',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2018)].jumlah_rm.iloc[0], 944594771608.09, tol=0.5)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2018.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
