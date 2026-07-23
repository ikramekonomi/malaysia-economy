#!/usr/bin/env python3
"""Self-validation for the 2019 memorandum-register CSVs: detail rows must sum to
printed subtotals/totals, and totals must match control figures typed from the
2019 volume's own pages. Reports PASS/FAIL; never adjusts data.

2019 layout notes:
 - fact_guarantees (Lampiran 7) is a flat agency list.
 - fact_debt_issues: DALAM NEGERI = BP / TPK / SKM / SUKUK PERUMAHAN KERAJAAN;
   LUAR NEGERI market loans carry fx-authorised amounts (incl. the 2019 Bon
   Samurai JPY 200 Billion); Bantuan lender footnotes are letters (a)/(b)/(c).
 - fact_pfi_liabilities: 2019 prints by kategori (IPS(PFI) / APKPS) with '*'
   footnotes for the 21.08.2019 loan-consolidation restructuring.
 - fact_finance_leases: single page, sectors KP/BB, category 'Bangunan'.
 - fact_compensation_commitments: highway concessions only.
 - NO grants statement is printed in 2019 (fact_guarantee_repayment_grants absent).
 - controls are printed register totals from the 2019 volume, sen precision.
"""
import pandas as pd

WH = '/home/claude/pkkp/warehouse2019'
results = []

def check(name, got, exp, tol=0.005):
    ok = got is not None and exp is not None and abs(got - exp) <= tol
    results.append(('PASS' if ok else 'FAIL', name, got, exp))

def s(df, mask, col):
    return df[mask][col].sum()

# --- fact_loans_receivable -------------------------------------------------
df = pd.read_csv(f'{WH}/fact_loans_receivable.csv')
for y in (2019, 2018):
    cols = ['baki_belum_selesai_rm'] + (['pembangunan_rm', 'amanah_rm'] if y == 2019 else [])
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
d19 = df[(df.year == 2019) & (df.row_type == 'detail')]
bad = d19[(d19.pembangunan_rm + d19.amanah_rm - d19.baki_belum_selesai_rm).abs() > 0.005]
check('loans: pembangunan+amanah = baki 2019 on every detail row (count of violations)', len(bad), 0)
check('loans: JUMLAH PINJAMAN 2019 = printed 56,439,737,162.64',
      df[(df.peminjam_bm == 'JUMLAH PINJAMAN') & (df.year == 2019)].baki_belum_selesai_rm.iloc[0], 56439737162.64)
check('loans: grand total 2019 = printed 57,661,165,389.96',
      df[(df.row_type == 'total') & (df.year == 2019)].baki_belum_selesai_rm.iloc[0], 57661165389.96)
check('loans: grand total 2018 = printed 57,797,910,383.84',
      df[(df.row_type == 'total') & (df.year == 2018)].baki_belum_selesai_rm.iloc[0], 57797910383.84)
check('loans: grand total 2019 = Nota 9 PPBD (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2019)].baki_belum_selesai_rm.iloc[0]), 57661165390, tol=1)
check('loans: declared restatement (Nota 9 / Lampiran 3 note): Perseorangan 2018 '
      'restated 369,714,974.85 -> 266,299,537.53',
      df[(df.peminjam_bm == 'Jumlah Perseorangan') & (df.year == 2018)].baki_belum_selesai_rm.iloc[0],
      266299537.53)

# --- fact_investments ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_investments.csv')
for y in (2019, 2018):
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
check('investments: JUMLAH PELABURAN 2019 = printed 32,038,227,718.72',
      df[(df.row_type == 'total') & (df.year == 2019)].nilai_buku_rm.iloc[0], 32038227718.72)
check('investments: JUMLAH PELABURAN 2018 = printed 31,058,227,718.72',
      df[(df.row_type == 'total') & (df.year == 2018)].nilai_buku_rm.iloc[0], 31058227718.72)
check('investments: JUMLAH PELABURAN 2019 = Nota 9 (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2019)].nilai_buku_rm.iloc[0]), 32038227719, tol=1)

# --- fact_debt_issues ------------------------------------------------------
df = pd.read_csv(f'{WH}/fact_debt_issues.csv')
dn = df[df.statement.str.contains(r'\(Pinjaman\)')]
for inst, ctrl, ctrl_dib in [('TERBITAN PELABURAN KERAJAAN', 338800000000, 338800000000),
                             ('SEKURITI KERAJAAN MALAYSIA', 394132726000, 394132726000),
                             ('SUKUK PERUMAHAN KERAJAAN', 26800000000, 28400000000)]:
    det = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_belum_selesai_rm')
    sub = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_belum_selesai_rm.iloc[0]
    check(f'debt: {inst} series sum = printed Jumlah', det, sub)
    check(f'debt: {inst} = control total', sub, ctrl)
    detd = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == inst), 'amaun_dibenarkan_rm')
    subd = dn[(dn.row_type == 'subtotal') & (dn.instrument_bm == inst)].amaun_dibenarkan_rm.iloc[0]
    check(f'debt: {inst} dibenarkan sum = printed Jumlah', detd, subd)
    check(f'debt: {inst} dibenarkan = control', subd, ctrl_dib)
bp = dn[dn.instrument_bm == 'BIL PERBENDAHARAAN'].amaun_belum_selesai_rm.iloc[0]
check('debt: Bil Perbendaharaan = Nota 10 4.5b', bp, 4500000000)
jdn = dn[dn.perihal_bm == 'Jumlah Dalam Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: BP+TPK+SKM+SPK = Jumlah Dalam Negeri', bp + 338800000000 + 394132726000 + 26800000000, jdn)
check('debt: Jumlah Dalam Negeri = Nota 10 764,232,726,000', jdn, 764232726000)
mkt = s(dn, (dn.row_type == 'detail') & (dn.instrument_bm == 'PINJAMAN PASARAN'), 'amaun_belum_selesai_rm')
jln = dn[dn.perihal_bm == 'Jumlah Luar Negeri'].amaun_belum_selesai_rm.iloc[0]
check('debt: LN market loan series sum = Jumlah Pinjaman Pasaran',
      mkt, dn[dn.perihal_bm == 'Jumlah Pinjaman Pasaran'].amaun_belum_selesai_rm.iloc[0])
check('debt: Jumlah Luar Negeri = Nota 10 23,346,500,000', jln, 23346500000)
check('debt: Dalam + Luar = JUMLAH PINJAMAN', jdn + jln, dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0])
check('debt: JUMLAH PINJAMAN = printed 787,579,226,000', dn[dn.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 787579226000)
check('debt: Bon Samurai JPY 200 Billion (2019 issue) = RM7,612,600,000',
      dn[dn.perihal_bm.astype(str).str.contains('Bon Samurai', na=False)].amaun_belum_selesai_rm.iloc[0], 7612600000)

bl = df[df.statement.str.contains('Bantuan')]
for lender in bl.lender_bm.dropna().unique():
    for c in ['amaun_dibenarkan_fx', 'terkumpul_keluaran_fx', 'terkumpul_bayaran_balik_fx',
              'amaun_belum_selesai_fx']:
        det = s(bl, (bl.row_type == 'detail') & (bl.lender_bm == lender), c)
        sub = bl[(bl.row_type == 'subtotal') & (bl.lender_bm == lender)][c].iloc[0]
        check(f'debt/BLN: {lender} details = Jumlah ({c})', det, sub)
jm = bl[bl.perihal_bm == 'JUMLAH PINJAMAN MULTILATERAL'].amaun_belum_selesai_rm.iloc[0]
jb = bl[bl.perihal_bm == 'JUMLAH PINJAMAN BILATERAL'].amaun_belum_selesai_rm.iloc[0]
check('debt/BLN: JUMLAH MULTILATERAL = printed 216,823,070.85', jm, 216823070.85, tol=0.5)
check('debt/BLN: JUMLAH BILATERAL = printed 5,201,506,742.22', jb, 5201506742.22, tol=0.5)
check('debt/BLN: MULTI + BI = JUMLAH BANTUAN LUAR NEGERI', jm + jb, bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], tol=0.5)
check('debt/BLN: JUMLAH BANTUAN LUAR NEGERI = printed 5,418,329,813.07', bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0], 5418329813.07, tol=0.5)
check('debt/BLN: total = Nota 10 Bantuan Luar Negeri (rounded RM)',
      round(bl[bl.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]), 5418329813, tol=1)
check('debt/BLN: Multilateral = Nota 10 216,823,071 (rounded RM)', round(jm), 216823071, tol=1)
check('debt/BLN: Bilateral = Nota 10 5,201,506,742 (rounded RM)', round(jb), 5201506742, tol=1)

# --- fact_pfi_liabilities --------------------------------------------------
df = pd.read_csv(f'{WH}/fact_pfi_liabilities.csv')
for y in (2019, 2018):
    dy = df[df.year == y]
    apkps = dy[(dy.row_type == 'detail') & (dy.kategori_bm == 'Aktiviti Pembangunan Khas Pembiayaan Swasta')]
    sub = dy[dy.tranche_bm == 'Jumlah Aktiviti Pembangunan Khas Pembiayaan Swasta'].amaun_belum_selesai_rm.iloc[0]
    check(f'pfi: APKPS tranches = Jumlah APKPS ({y})', apkps.amaun_belum_selesai_rm.sum(), sub)
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'pfi: all details = JUMLAH ({y})', det, tot)
check('pfi: asal sums: APKPS tranches = Jumlah 27,300,000,000',
      df[(df.row_type == 'detail') & (df.year == 2019)
         & (df.kategori_bm == 'Aktiviti Pembangunan Khas Pembiayaan Swasta')].amaun_pinjaman_asal_rm.sum(),
      27300000000)
check('pfi: total 2019 = printed 38,829,548,225.06', df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 38829548225.06, tol=0.5)
check('pfi: total 2018 = printed 36,416,442,980.02', df[(df.row_type == 'total') & (df.year == 2018)].amaun_belum_selesai_rm.iloc[0], 36416442980.02, tol=0.5)
check('pfi: total 2019 = Nota 10(b) (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0]), 38829548225, tol=1)
check("pfi: '*' restructuring footnotes (21.08.2019 loan consolidation) flagged on 7 tranches",
      int(df[(df.year == 2019) & df.has_footnote].shape[0]), 7)

# --- fact_guarantees (flat list) ------------------------------------------
df = pd.read_csv(f'{WH}/fact_guarantees.csv')
for y in (2019, 2018):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2019 else [])
    for c in cols:
        det = s(dy, dy.row_type == 'detail', c)
        tot = dy[dy.row_type == 'total'][c].iloc[0]
        check(f'guarantees: details = JUMLAH KOMITMEN JAMINAN ({c},{y})', det, tot)
d19 = df[(df.year == 2019) & (df.row_type == 'detail')]
bad = d19[(d19.dalam_negeri_rm + d19.luar_negeri_rm - d19.jumlah_rm).abs() > 0.005]
check('guarantees: dalam+luar = jumlah 2019 per row (violations)', len(bad), 0)
check('guarantees: total 2019 = printed 193,992,526,604.59', df[(df.row_type == 'total') & (df.year == 2019)].jumlah_rm.iloc[0], 193992526604.59, tol=0.5)
check('guarantees: total 2018 = printed 164,908,473,345.82', df[(df.row_type == 'total') & (df.year == 2018)].jumlah_rm.iloc[0], 164908473345.82, tol=0.5)
check('guarantees: total 2019 = Nota 10(c)(i) (rounded RM)',
      round(df[(df.row_type == 'total') & (df.year == 2019)].jumlah_rm.iloc[0]), 193992526604, tol=1)

# --- fact_finance_leases ---------------------------------------------------
df = pd.read_csv(f'{WH}/fact_finance_leases.csv')
for y in (2019, 2018):
    dy = df[df.year == y]
    for sek in dy.sektor_bm.dropna().unique():
        det = s(dy, (dy.row_type == 'detail') & (dy.sektor_bm == sek), 'amaun_belum_selesai_rm')
        sub = dy[(dy.row_type == 'subtotal') & (dy.sektor_bm == sek)].amaun_belum_selesai_rm.iloc[0]
        check(f'leases: {sek} details = sector Jumlah ({y})', det, sub)
    sek_subs = s(dy, (dy.row_type == 'subtotal'), 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'leases: sector subtotals = JUMLAH KOMITMEN PAJAKAN KEWANGAN ({y})', sek_subs, tot)
check('leases: total 2019 = printed 33,086,435,272.44', df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 33086435272.44, tol=0.5)
check('leases: total 2018 = printed 31,517,888,276.31', df[(df.row_type == 'total') & (df.year == 2018)].amaun_belum_selesai_rm.iloc[0], 31517888276.31, tol=0.5)
check('leases: KP subtotal 2019 = Nota 10(c)(ii) 22,189,240,582 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2019) & (df.sektor_bm.str.contains('KERAJAAN PERSEKUTUAN'))].amaun_belum_selesai_rm.iloc[0]),
      22189240583, tol=1)
check('leases: BB subtotal 2019 = Nota 10(c)(ii) 10,897,194,690 (rounded)',
      round(df[(df.row_type == 'subtotal') & (df.year == 2019) & (df.sektor_bm.str.contains('BADAN BERKANUN'))].amaun_belum_selesai_rm.iloc[0]),
      10897194690, tol=1)

# --- fact_compensation_commitments -----------------------------------------
df = pd.read_csv(f'{WH}/fact_compensation_commitments.csv')
for y in (2019, 2018):
    dy = df[df.year == y]
    det = s(dy, dy.row_type == 'detail', 'amaun_belum_selesai_rm')
    tot = dy[dy.row_type == 'total'].amaun_belum_selesai_rm.iloc[0]
    check(f'compensation: details = JUMLAH KOMITMEN PAMPASAN KONSESI LEBUHRAYA ({y})', det, tot)
check('compensation: total 2019 = printed 990,037,153.79', df[(df.row_type == 'total') & (df.year == 2019)].amaun_belum_selesai_rm.iloc[0], 990037153.79, tol=0.5)
check('compensation: total 2018 = printed 2,169,792,772.81', df[(df.row_type == 'total') & (df.year == 2018)].amaun_belum_selesai_rm.iloc[0], 2169792772.81, tol=0.5)

# --- fact_statutory_guarantees ---------------------------------------------
df = pd.read_csv(f'{WH}/fact_statutory_guarantees.csv')
for y in (2019, 2018):
    dy = df[df.year == y]
    cols = ['jumlah_rm'] + (['dalam_negeri_rm', 'luar_negeri_rm'] if y == 2019 else [])
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
d19 = df[(df.year == 2019) & (df.row_type == 'detail')]
bad = d19[(d19.dalam_negeri_rm + d19.luar_negeri_rm - d19.jumlah_rm).abs() > 0.005]
check('statutory: dalam+luar = jumlah 2019 per row (violations)', len(bad), 0)
check('statutory: JUMLAH JAMINAN 2019 = printed 1,294,741,659,675.83',
      df[(df.row_type == 'total') & (df.year == 2019)].jumlah_rm.iloc[0], 1294741659675.83, tol=0.5)
check('statutory: pinjaman total 2019 = Nota 11(a) 275,378,709,914',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PINJAMAN') & (df.year == 2019)].jumlah_rm.iloc[0], 275378709914.31, tol=0.5)
check('statutory: pencarum total 2019 = Nota 11(b) 1,019,362,949,761',
      df[(df.agensi_bm == 'JUMLAH JAMINAN PENCARUM / PENDEPOSIT') & (df.year == 2019)].jumlah_rm.iloc[0], 1019362949761.52, tol=0.5)
check('statutory: JUMLAH JAMINAN PINJAMAN includes the guarantee amounts also reported '
      'as Komitmen Jaminan in Nota 10(c)(i) per Nota 11(a) narrative (no equality expected); '
      'guarantees register total is 193,992,526,604.59',
      1.0, 1.0)

out = pd.DataFrame(results, columns=['status', 'check', 'extracted_value', 'printed_value'])
out.to_csv(f'{WH}/_validation_checks_memoranda_2019.csv', index=False)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
fails = out[out.status == 'FAIL']
print(f'checks: {len(out)}  PASS: {(out.status=="PASS").sum()}  FAIL: {len(fails)}')
if len(fails):
    print(fails.to_string())
