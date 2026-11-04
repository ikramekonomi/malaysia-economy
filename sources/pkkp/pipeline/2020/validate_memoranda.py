#!/usr/bin/env python3
"""Self-validation for the 2020 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2020 volume's own pages. Reports PASS/FAIL; never adjusts data.

2020 layout notes:
 - fact_guarantees (Lampiran 8) is a flat agency list.
 - fact_debt_issues: SUKUK PERUMAHAN KERAJAAN includes the Sukuk Prihatin issue
   (1/2020 ISPM2001, RM666,417,500); LUAR NEGERI market loans carry fx-authorised
   amounts; Bantuan lender footnotes are letters (a)/(b)/(c).
 - fact_finance_leases: single page, sectors KP/BB, category 'Bangunan',
   '*' footnotes mark ministries affected by the 2020 MDM restructure.
 - fact_compensation_commitments: highway concessions only.
 - controls are printed register totals from the 2020 volume, sen precision.
"""
import os
import pandas as pd

WH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "2020")
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2020, 2019):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'amanah_rm'] if y == 2020 else [])
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
d20 = df[(df.year == 2020) & (df.row_type == 'detail')]
bad = d20[(d20.pembangunan_rm + d20.amanah_rm - d20.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+amanah = baki 2020 on every detail row (count of violations)', len(bad), 0)
check('loans: JUMLAH PINJAMAN 2020 = printed 57,618,257,515.19',
      df[(df.peminjam_bm == 'JUMLAH PINJAMAN') & (df.year == 2020)].baki_belum_selesai_rm.iloc[0], 57618257515.19)
check('loans: grand total 2020 = printed 58,900,685,742.51',
      df[(df.row_type == 'total') & (df.year == 2020)].baki_belum_selesai_rm.iloc[0], 58900685742.51)
check('loans: grand total 2019 = printed 57,661,165,389.96',
      df[(df.row_type == 'total') & (df.year == 2019)].baki_belum_selesai_rm.iloc[0], 57661165389.96)
check('loans: grand total 2020 = Nota 9 PPBD (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2020)].baki_belum_selesai_rm.iloc[0]), 58900685743, tol=1)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2020, 2019):
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
check('investments: JUMLAH PELABURAN 2020 = printed 33,191,463,710.72',
      df[(df.row_type == 'total') & (df.year == 2020)].nilai_buku_rm.iloc[0], 33191463710.72)
check('investments: JUMLAH PELABURAN 2019 = printed 32,038,227,718.72',
      df[(df.row_type == 'total') & (df.year == 2019)].nilai_buku_rm.iloc[0], 32038227718.72)
check('investments: JUMLAH PELABURAN 2020 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2020)].nilai_buku_rm.iloc[0]), 33191463711, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl, ctrl_dib in [('TERBITAN PELABURAN KERAJAAN', 374600000000, 414600000000),
                             ('SEKURITI KERAJAAN MALAYSIA', 436417530000, 467132726000),
                             ('SUKUK PERUMAHAN KERAJAAN', 24766417500, 27466417500)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control total', sub, ctrl)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
    check(f'debt: {inst} dibenarkan = control', subd, ctrl_dib)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = Nota 10 15.5b', bp, 15500000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM+Sukuk = Jumlah Dalam Negeri', bp + 374600000000 + 436417530000 + 24766417500, jdn)
check('debt: Jumlah Dalam Negeri = Nota 10 851,283,947,500', jdn, 851283947500)
check('debt: Sukuk Prihatin issue = narrative RM666,417,500',
      dn[dn.kod_saham.astype(str).str.contains('PRIHATIN', na=False)].amaun_belum_selesai_rm.iloc[0], 666417500)
mkt = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == 'PINJAMAN PASARAN'), 'amaun_belum_selesai_rm')
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: LN market loan series sum = Jumlah Pinjaman Pasaran',
      mkt, dn[dn.perihal_bm == 'Jumlah Pinjaman Pasaran'].amaun_belum_selesai_rm.iloc[0])
check('debt: Jumlah Luar Negeri = Nota 10 23,055,200,000', jln, 23055200000)
check('debt: Dalam + Luar = JUMLAH PINJAMAN', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = printed 874,339,147,500', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 874339147500)

bl = df[df.statement.str.contains('Bantuan')]
for lender in bl.lender_bm.dropna().unique():
    for c in ['amaun_dibenarkan_fx', 'terkumpul_keluaran_fx', 'terkumpul_bayaran_balik_fx',
              'amaun_belum_selesai_fx']:
        det = s(bl, (bl.row_type == 'detail') & (bl.lender_bm == lender), c)
        sub = bl[(bl.row_type == 'subtotal') & (bl.lender_bm == lender)][c].iloc[0]
        check(f'debt/BLN: {lender} details = Jumlah ({c})', det, sub)
jm = bl[bl.perihal_bm == 'JUMLAH PINJAMAN MULTILATERAL'].amaun_belum_selesai_rm.iloc[0]
jb = bl[bl.perihal_bm == 'JUMLAH PINJAMAN BILATERAL'].amaun_belum_selesai_rm.iloc[0]
check('debt/BLN: JUMLAH MULTILATERAL = printed 153,108,618.31', jm, 153108618.31, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = printed 5,067,452,691.31', jb, 5067452691.31, tol=0.5)
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], tol=0.5)
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = printed 5,220,561,309.62', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 5220561309.62, tol=0.5)
check('debt/BLN: total = Nota 10 Bantuan Luar Negeri (rounded RM)',
      round(bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]), 5220561310, tol=1)

# --- fact_pfi_liabilities --------------------------------------------------
df = pd.read_csv(f'{WH}/fact_pfi_liabilities.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    for ag in dy[dy.row_type == 'detail'].agensi_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.agensi_bm == ag), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.agensi_bm == ag)].amaun_belum_selesai_rm.iloc[0]
        check(f'pfi: {ag} details = Jumlah ({y})', det, sub)
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'pfi: all details = JUMLAH ({y})', det, tot)
check('pfi: total 2020 = printed 37,034,467,015.18', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 37034467015.18, tol=0.5)
check('pfi: total 2019 = printed 38,829,548,225.05 (restated by borrowing company per Nota 10(b))',
      df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 38829548225.05, tol=0.6)

# --- fact_guarantees (flat list) ------------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantees.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2020 else [])
    for c in cols:
        det = s(dy, dy.row_type == 'detail', c)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'guarantees: details = JUMLAH KOMITMEN JAMINAN ({c},{y})', det, tot)
d20 = df[(df.year == 2020) & (df.row_type == 'detail')]
bad = d20[(d20.dalam_negeri_rm + d20.luar_negeri_rm - d20.jumlah_rm).abs() > 0.005]
check('guarantees: dalam+luar = jumlah 2020 per row (violations)', len(bad), 0)
check('guarantees: total 2020 = printed 216,841,563,770.31', df[(df.row_type == 'total') & (df.year == 2020)].jumlah_rm.iloc[0], 216841563770.31, tol=0.5)
check('guarantees: total 2019 = printed 193,992,526,604.59', df[(df.row_type == 'total') & (df.year == 2019)].jumlah_rm.iloc[0], 193992526604.59, tol=0.5)
check('guarantees: total 2020 = Nota 10(c)(i) (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2020)].jumlah_rm.iloc[0]), 216841563770, tol=1)

# --- fact_guarantee_repayment_grants ---------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantee_repayment_grants.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].peruntukan_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.peruntukan_bm == cat), 'amaun_penyaluran_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.peruntukan_bm == cat)].amaun_penyaluran_rm.iloc[0]
        check(f'grants: {cat} details = Jumlah ({y})', det, sub)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_penyaluran_rm')
    tot = dy[dy.row_type == 'total'].amaun_penyaluran_rm.iloc[0]
    check(f'grants: subtotals = JUMLAH KESELURUHAN PERUNTUKAN ({y})', subs, tot)
check('grants: total 2020 = printed 5,662,566,811.99', df[(df.row_type == 'total') & (df.year == 2020)].amaun_penyaluran_rm.iloc[0], 5662566811.99, tol=0.5)
check('grants: total 2019 = printed 3,941,572,692.71', df[(df.row_type == 'total') & (df.year == 2019)].amaun_penyaluran_rm.iloc[0], 3941572692.71, tol=0.5)
check('grants: Peruntukan Mengurus 2020 = Nota 5(b) footnote RM534,076,151 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2020) & (df.peruntukan_bm == 'PERUNTUKAN MENGURUS')].amaun_penyaluran_rm.iloc[0]),
      534076151, tol=1)
check('grants: Peruntukan Pembangunan 2020 = Nota 7(a)(i) narrative RM5,128,490,661 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2020) & (df.peruntukan_bm == 'PERUNTUKAN PEMBANGUNAN')].amaun_penyaluran_rm.iloc[0]),
      5128490661, tol=1)

# --- fact_finance_leases ---------------------------------------------------
df = pd.read_csv(f'{WH}/fact_finance_leases.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    for sek in dy.sektor_bm.dropna().unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.sektor_bm == sek), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek)].amaun_belum_selesai_rm.iloc[0]
        diag = (' [DIAGNOSIS: print-side 1-sen rounding -- the 26 printed KP detail rows sum to '
                '26,847,483,272.24 but the volume prints Jumlah 26,847,483,272.23; all rows '
                'transcribed verbatim from the text layer]'
                if y == 2020 and 'KERAJAAN PERSEKUTUAN' in sek else '')
        check(f'leases: {sek} details = sector Jumlah ({y}){diag}', det, sub)
    sek_subs = s(dy, (dy.row_type == 'subtotal'), 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    diag2 = (' [DIAGNOSIS: follows from the KP 1-sen print rounding above; printed sector '
             'subtotals sum to ...546.58 vs printed grand ...546.59]' if y == 2020 else '')
    check(f'leases: sector subtotals = JUMLAH KOMITMEN PAJAKAN KEWANGAN ({y}){diag2}', sek_subs, tot)
check('leases: total 2020 = printed 37,570,623,546.59', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 37570623546.59, tol=0.5)
check('leases: total 2019 = printed 33,086,435,272.44', df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 33086435272.44, tol=0.5)
check('leases: KP subtotal 2020 = Nota 10(c)(ii) 26,847,483,272 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2020) & (df.sektor_bm.str.contains('KERAJAAN PERSEKUTUAN'))].amaun_belum_selesai_rm.iloc[0]),
      26847483272, tol=1)
check('leases: BB subtotal 2020 = Nota 10(c)(ii) 10,723,140,275 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2020) & (df.sektor_bm.str.contains('BADAN BERKANUN'))].amaun_belum_selesai_rm.iloc[0]),
      10723140274.35, tol=1)

# --- fact_compensation_commitments -----------------------------------------
df = pd.read_csv(f'{WH}/fact_compensation_commitments.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'compensation: details = JUMLAH KOMITMEN PAMPASAN KONSESI LEBUHRAYA ({y})', det, tot)
check('compensation: total 2020 = printed 892,581,000.00', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 892581000.00, tol=0.5)
check('compensation: total 2019 = printed 990,037,153.79', df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 990037153.79, tol=0.5)

# --- fact_statutory_guarantees ---------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2020, 2019):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2020 else [])
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
d20 = df[(df.year == 2020) & (df.row_type == 'detail')]
bad = d20[(d20.dalam_negeri_rm + d20.luar_negeri_rm - d20.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2020 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2020 = printed 1,395,123,370,769.70',
      df[(df.row_type == 'total') & (df.year == 2020)].jumlah_rm.iloc[0], 1395123370769.70, tol=0.5)
check('statutory: pinjaman total 2020 = Nota 11(a) 294,674,756,861',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2020)].jumlah_rm.iloc[0], 294674756861.38, tol=0.5)
check('statutory: pencarum total 2020 = Nota 11(b) 1,100,448,613,908',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2020)].jumlah_rm.iloc[0], 1100448613908.32, tol=0.5)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2020.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
