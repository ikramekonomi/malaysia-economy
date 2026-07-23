#!/usr/bin/env python3
"""Self-validation for the memorandum-register CSVs: detail rows must sum to printed
subtotals/totals, and totals must match known control figures. Reports PASS/FAIL; never
adjusts data."""
import pandas as pd

WH = '/home/claude/pkkp/warehouse'
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2024, 2023):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'amanah_rm'] if y == 2024 else [])
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
# within-row: pembangunan + amanah = baki 2024
d24 = df[(df.year == 2024) & (df.row_type == 'detail')]
bad = d24[(d24.pembangunan_rm + d24.amanah_rm - d24.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+amanah = baki 2024 on every detail row (count of violations)', len(bad), 0)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2024, 2023):
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
check('investments: JUMLAH PELABURAN 2024 (printed)', df[(df.row_type == 'total') & (df.year == 2024)].nilai_buku_rm.iloc[0], 34690492523.72)
check('investments: JUMLAH PELABURAN 2023 (printed)', df[(df.row_type == 'total') & (df.year == 2023)].nilai_buku_rm.iloc[0], 34821492524.72)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl in [('TERBITAN PELABURAN KERAJAAN', 570800000000), ('SEKURITI KERAJAAN MALAYSIA', 633837729000),
                   ('SUKUK PERUMAHAN KERAJAAN', 0), ('PINJAMAN PASARAN', 24976850000)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control total', sub, ctrl)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    if inst != 'PINJAMAN PASARAN':
        check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = control 15b', bp, 15000000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM+Sukuk = Jumlah Dalam Negeri', bp + 570800000000 + 633837729000 + 0, jdn)
check('debt: Jumlah Dalam Negeri = control 1,219,637,729,000', jdn, 1219637729000)
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri', dn[dn.perihal_bm == 'Jumlah Pinjaman Pasaran'].amaun_belum_selesai_rm.iloc[0], jln)
check('debt: Dalam + Luar = JUMLAH PINJAMAN 1,244,614,579,000', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = control', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 1244614579000)

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
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = control 2,998,966,373', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 2998966373, tol=0.5)

# --- fact_pfi_liabilities --------------------------------------------------
df = pd.read_csv(f'{WH}/fact_pfi_liabilities.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    for ag in dy[dy.row_type == 'detail'].agensi_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.agensi_bm == ag), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.agensi_bm == ag)].amaun_belum_selesai_rm.iloc[0]
        check(f'pfi: {ag} details = Jumlah ({y})', det, sub)
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'pfi: all details = JUMLAH ({y})', det, tot)
check('pfi: total 2024 = control 32,905,600,585', df[(df.row_type == 'total') & (df.year == 2024)].amaun_belum_selesai_rm.iloc[0], 32905600585, tol=0.5)

# --- fact_guarantees -------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantees.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2024 else [])
    for cat in ('Badan Berkanun', 'Syarikat'):
        for c in cols:
            det = s(dy, (dy.row_type == 'detail') & (dy.kategori_bm == cat), c)
            sub = dy[(dy.row_type == 'subtotal') & (dy.agensi_bm == f'Jumlah {cat}')][c].iloc[0]
            check(f'guarantees: {cat} details = Jumlah ({c},{y})', det, sub)
    for c in cols:
        subs = s(dy, dy.row_type == 'subtotal', c)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'guarantees: subtotals = JUMLAH KOMITMEN JAMINAN ({c},{y})', subs, tot)
d24 = df[(df.year == 2024) & (df.row_type == 'detail')]
bad = d24[(d24.dalam_negeri_rm + d24.luar_negeri_rm - d24.jumlah_rm).abs() > 0.005]
check('guarantees: dalam+luar = jumlah 2024 per row (violations)', len(bad), 0)
check('guarantees: total 2024 = control 236,229,124,709', df[(df.row_type == 'total') & (df.year == 2024)].jumlah_rm.iloc[0], 236229124709, tol=0.5)

# --- fact_guarantee_repayment_grants ----------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantee_repayment_grants.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].peruntukan_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.peruntukan_bm == cat), 'amaun_penyaluran_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.peruntukan_bm == cat)].amaun_penyaluran_rm.iloc[0]
        check(f'grants: {cat} details = Jumlah ({y})', det, sub)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_penyaluran_rm')
    tot = dy[dy.row_type == 'total'].amaun_penyaluran_rm.iloc[0]
    check(f'grants: subtotals = JUMLAH KESELURUHAN PERUNTUKAN ({y})', subs, tot)

# --- fact_finance_leases ---------------------------------------------------
df = pd.read_csv(f'{WH}/fact_finance_leases.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    for sek in dy.sektor_bm.dropna().unique():
        for cat in dy[(dy.sektor_bm == sek) & (dy.row_type == 'detail')].kategori_bm.unique():
            det = s(dy, (dy.row_type == 'detail') & (dy.sektor_bm == sek) & (dy.kategori_bm == cat), 'amaun_belum_selesai_rm')
            sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & (dy.perihal_bm == f'Jumlah Pajakan Kewangan {cat}')].amaun_belum_selesai_rm.iloc[0]
            check(f'leases: {sek}/{cat} details = Jumlah ({y})', det, sub)
        cat_subs = s(dy, (dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & dy.kategori_bm.notna(), 'amaun_belum_selesai_rm')
        sek_sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek) & dy.kategori_bm.isna()].amaun_belum_selesai_rm.iloc[0]
        check(f'leases: {sek} category subtotals = sector Jumlah ({y})', cat_subs, sek_sub)
    sek_subs = s(dy, (dy.row_type == 'subtotal') & dy.kategori_bm.isna(), 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'leases: sector subtotals = JUMLAH KOMITMEN PAJAKAN KEWANGAN ({y})', sek_subs, tot)
check('leases: total 2024 = control 26,659,661,074', df[(df.row_type == 'total') & (df.year == 2024)].amaun_belum_selesai_rm.iloc[0], 26659661074, tol=0.5)

# --- fact_compensation_commitments -------------------------------------------
df = pd.read_csv(f'{WH}/fact_compensation_commitments.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    for cat in dy[dy.row_type == 'detail'].kategori_bm.unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.kategori_bm == cat), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.kategori_bm == cat)].amaun_belum_selesai_rm.iloc[0]
        check(f'compensation: {cat} details = Jumlah ({y})', det, sub)
    subs = s(dy, dy.row_type == 'subtotal', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'compensation: subtotals = JUMLAH KOMITMEN PAMPASAN ({y})', subs, tot)
check('compensation: total 2024 = control 934,389,799', df[(df.row_type == 'total') & (df.year == 2024)].amaun_belum_selesai_rm.iloc[0], 934389799, tol=0.5)

# --- fact_statutory_guarantees -----------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2024, 2023):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2024 else [])
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
d24 = df[(df.year == 2024) & (df.row_type == 'detail')]
bad = d24[(d24.dalam_negeri_rm + d24.luar_negeri_rm - d24.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2024 per row (violations)', len(bad), 0)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
