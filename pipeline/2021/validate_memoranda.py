#!/usr/bin/env python3
"""Self-validation for the 2021 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2023 volume's own pages. Reports PASS/FAIL; never adjusts data.

2022 layout notes:
 - fact_guarantees (Lampiran 8) is a FLAT agency list (like 2023).
 - fact_debt_issues: 2022 adds SUKUK PRIHATIN and a two-level Sukuk aggregate
   ('Jumlah Sukuk Perumahan Kerajaan' + 'Jumlah Sukuk Prihatin' -> 'Jumlah Sukuk').
 - fact_finance_leases category subtotal names as in 2023; matched by kategori_bm.
 - fact_compensation_commitments 2022 has NO 'listing' rows (highway names carry
   amounts as details); the filter is retained harmlessly.
 - controls are printed register totals from the 2021 volume, sen precision.
"""
import pandas as pd

WH = '/home/claude/pkkp/warehouse2021'
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2021, 2020):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'amanah_rm'] if y == 2021 else [])
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
d23 = df[(df.year == 2021) & (df.row_type == 'detail')]
bad = d23[(d23.pembangunan_rm + d23.amanah_rm - d23.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+amanah = baki 2021 on every detail row (count of violations)', len(bad), 0)
check('loans: grand total 2021 = printed 57,846,052,679.50',
      df[(df.row_type == 'total') & (df.year == 2021)].baki_belum_selesai_rm.iloc[0], 57846052679.50)
check('loans: grand total 2020 = printed 58,900,685,742.51',
      df[(df.row_type == 'total') & (df.year == 2020)].baki_belum_selesai_rm.iloc[0], 58900685742.51)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2021, 2020):
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
check('investments: JUMLAH PELABURAN 2021 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2021)].nilai_buku_rm.iloc[0]), 33861520709, tol=1)
check('investments: JUMLAH PELABURAN 2020 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2020)].nilai_buku_rm.iloc[0]), 33191463711, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl in [('TERBITAN PELABURAN KERAJAAN', 422600000000), ('SEKURITI KERAJAAN MALAYSIA', 480717530000),
                   ('SUKUK PERUMAHAN KERAJAAN', 18100000000), ('SUKUK PRIHATIN', 666417500), ('PINJAMAN PASARAN', 25147100000)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control total', sub, ctrl)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    if inst != 'PINJAMAN PASARAN':
        check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = control 28.0b', bp, 28000000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
suk_agg = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == 'SUKUK')].amaun_belum_selesai_rm.iloc[0]
check('debt: Sukuk Perumahan + Prihatin = Jumlah Sukuk aggregate', 18100000000 + 666417500, suk_agg)
check('debt: BP+TPK+SKM+Sukuk = Jumlah Dalam Negeri', bp + 422600000000 + 480717530000 + suk_agg, jdn)
check('debt: Jumlah Dalam Negeri = control 950,083,947,500', jdn, 950083947500)
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri', dn[dn.perihal_bm == 'Jumlah Pinjaman Pasaran'].amaun_belum_selesai_rm.iloc[0], jln)
check('debt: Dalam + Luar = JUMLAH PINJAMAN', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = control 975,231,047,500', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 975231047500)

bl = df[df.statement.str.contains('Bantuan')]
for lender in bl.lender_bm.dropna().unique():
    for c in ['amaun_dibenarkan_fx', 'terkumpul_keluaran_fx', 'terkumpul_bayaran_balik_fx',
              'amaun_belum_selesai_fx', 'amaun_belum_selesai_rm']:
        det = s(bl, (bl.row_type == 'detail') & (bl.lender_bm == lender), c)
        sub = bl[(bl.row_type == 'subtotal') & (bl.lender_bm == lender)][c].iloc[0]
        check(f'debt/BLN: {lender} details = Jumlah ({c})', det, sub)
jm = bl[bl.perihal_bm == 'JUMLAH PINJAMAN MULTILATERAL'].amaun_belum_selesai_rm.iloc[0]
jb = bl[bl.perihal_bm == 'JUMLAH PINJAMAN BILATERAL'].amaun_belum_selesai_rm.iloc[0]
check('debt/BLN: multilateral lender subtotal = JUMLAH MULTILATERAL',
      bl[bl.perihal_bm == 'Jumlah Bank Pembangunan Islam'].amaun_belum_selesai_rm.iloc[0], jm)
check('debt/BLN: bilateral lender subtotals = JUMLAH BILATERAL',
      s(bl, (bl.row_type == 'subtotal') & (bl.region_bm == 'PINJAMAN BILATERAL') & bl.perihal_bm.str.startswith('Jumlah '), 'amaun_belum_selesai_rm'), jb)
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], tol=0.5)
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = control 4,583,313,817.65', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 4583313817.65, tol=0.5)
check('debt/BLN: JUMLAH MULTILATERAL = control 115,512,191.40', jm, 115512191.40, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = control 4,467,801,626.25', jb, 4467801626.25, tol=0.5)

# --- fact_pfi_liabilities --------------------------------------------------
df = pd.read_csv(f'{WH}/fact_pfi_liabilities.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    for ag in dy[dy.row_type == 'detail'].agensi_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.agensi_bm == ag), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.agensi_bm == ag)].amaun_belum_selesai_rm.iloc[0]
        check(f'pfi: {ag} details = Jumlah ({y})', det, sub)
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'pfi: all details = JUMLAH ({y})', det, tot)
check('pfi: total 2021 = control 35,574,695,049.80', df[(df.row_type == 'total') & (df.year == 2021)].amaun_belum_selesai_rm.iloc[0], 35574695049.80, tol=0.5)
check('pfi: total 2020 = control 37,034,467,015.18', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 37034467015.18, tol=0.5)

# --- fact_guarantees (flat list in 2022) ------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantees.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2021 else [])
    for c in cols:
        det = s(dy, dy.row_type == 'detail', c)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'guarantees: details = JUMLAH KOMITMEN JAMINAN ({c},{y})', det, tot)
d23 = df[(df.year == 2021) & (df.row_type == 'detail')]
bad = d23[(d23.dalam_negeri_rm + d23.luar_negeri_rm - d23.jumlah_rm).abs() > 0.005]
check('guarantees: dalam+luar = jumlah 2021 per row (violations)', len(bad), 0)
check('guarantees: total 2021 = control 229,391,741,671.56', df[(df.row_type == 'total') & (df.year == 2021)].jumlah_rm.iloc[0], 229391741671.56, tol=0.5)
check('guarantees: total 2020 = control 216,841,563,770.31', df[(df.row_type == 'total') & (df.year == 2020)].jumlah_rm.iloc[0], 216841563770.31, tol=0.5)

# --- fact_guarantee_repayment_grants ----------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantee_repayment_grants.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].peruntukan_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.peruntukan_bm == cat), 'amaun_penyaluran_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.peruntukan_bm == cat)].amaun_penyaluran_rm.iloc[0]
        check(f'grants: {cat} details = Jumlah ({y})', det, sub)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_penyaluran_rm')
    tot = dy[dy.row_type == 'total'].amaun_penyaluran_rm.iloc[0]
    check(f'grants: subtotals = JUMLAH KESELURUHAN PERUNTUKAN ({y})', subs, tot)
check('grants: total 2021 = control 10,096,793,667.83', df[(df.row_type == 'total') & (df.year == 2021)].amaun_penyaluran_rm.iloc[0], 10096793667.83, tol=0.5)
check('grants: total 2020 = control 5,662,566,811.99', df[(df.row_type == 'total') & (df.year == 2020)].amaun_penyaluran_rm.iloc[0], 5662566811.99, tol=0.5)

# --- fact_finance_leases ---------------------------------------------------
df = pd.read_csv(f'{WH}/fact_finance_leases.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    for sek in dy.sektor_bm.dropna().unique():
        for cat in dy[(dy.sektor_bm == sek) & (dy.row_type == 'detail')].kategori_bm.unique():
            det = s(dy, (dy.row_type == 'detail') & (dy.sektor_bm == sek) & (dy.kategori_bm == cat), 'amaun_belum_selesai_rm')
            sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & (dy.kategori_bm == cat)].amaun_belum_selesai_rm.iloc[0]
            check(f'leases: {sek}/{cat} details = category Jumlah ({y})', det, sub)
        cat_subs = s(dy, (dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & dy.kategori_bm.notna(), 'amaun_belum_selesai_rm')
        sek_sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & dy.kategori_bm.isna()].amaun_belum_selesai_rm.iloc[0]
        check(f'leases: {sek} category subtotals = sector Jumlah ({y})', cat_subs, sek_sub)
    sek_subs = s(dy, (dy.row_type == 'subtotal') & dy.kategori_bm.isna(), 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'leases: sector subtotals = JUMLAH KOMITMEN PAJAKAN KEWANGAN ({y})', sek_subs, tot)
check('leases: total 2021 = control 37,202,939,955.46', df[(df.row_type == 'total') & (df.year == 2021)].amaun_belum_selesai_rm.iloc[0], 37202939955.46, tol=0.5)
check('leases: total 2020 = control 37,572,297,951.66 (2020 comparative as restated in this volume)', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 37572297951.66, tol=0.5)

# --- fact_compensation_commitments -------------------------------------------
df = pd.read_csv(f'{WH}/fact_compensation_commitments.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].kategori_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.kategori_bm == cat), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.kategori_bm == cat)].amaun_belum_selesai_rm.iloc[0]
        check(f'compensation: {cat} details = Jumlah ({y})', det, sub)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'compensation: subtotals = JUMLAH KOMITMEN PAMPASAN ({y})', subs, tot)
check('compensation: total 2021 = control 997,834,453.46', df[(df.row_type == 'total') & (df.year == 2021)].amaun_belum_selesai_rm.iloc[0], 997834453.46, tol=0.5)
check('compensation: total 2020 = control 973,669,713.49 (restated in this volume)', df[(df.row_type == 'total') & (df.year == 2020)].amaun_belum_selesai_rm.iloc[0], 973669713.49, tol=0.5)

# --- fact_statutory_guarantees -----------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2021, 2020):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2021 else [])
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
d23 = df[(df.year == 2021) & (df.row_type == 'detail')]
bad = d23[(d23.dalam_negeri_rm + d23.luar_negeri_rm - d23.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2021 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2021 = control 1,426,572,216,064.53',
      df[(df.row_type == 'total') & (df.year == 2021)].jumlah_rm.iloc[0], 1426572216064.53, tol=0.5)
check('statutory: pinjaman total 2021 = Nota 11(a) 310,387,529,248',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2021)].jumlah_rm.iloc[0], 310387529247.75, tol=0.5)
check('statutory: pencarum total 2021 = Nota 11(b) 1,116,184,686,817',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2021)].jumlah_rm.iloc[0], 1116184686816.78, tol=0.5)

# print-discrepancy diagnosis (proven from the volume's own page): Lampiran 9
# pdf 279, PAJAKAN KEWANGAN KERAJAAN PERSEKUTUAN / I. Bangunan, 2020 column —
# the 24 printed detail cells sum to 26,000,942,834.42 but the printed
# 'Jumlah Pajakan Kewangan Bangunan' shows 26,000,942,834.41: a 1-sen rounding
# discrepancy in the print, kept as printed.
results.append(('DIAGNOSIS',
                'leases: KP/Bangunan 2020 1-sen gap is a print rounding discrepancy '
                '(printed details sum 26,000,942,834.42 vs printed subtotal 26,000,942,834.41; pdf 279)',
                None, None))
out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2021.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
