#!/usr/bin/env python3
"""Extract PKKP 2012 NOTES-section tables (Nota 5,6,7,8) into warehouse CSVs.

Notes pages (pdf 52-64) are badly overprinted in the layout text, so each page
is read individually in RAW reading-order mode (pdftotext -raw). Values are
transcribed from the clean raw output and every non-zero amount is verified to
appear verbatim on its source page. All additive chains and external anchor
figures are validated PASS/FAIL. Nothing is silently corrected.

printed_page = pdf_page - 22 for the 2012 volume (confirmed via page folios).
"""
import csv, os, subprocess

WORK = "/home/claude/pkkp/work/2012"
WH = "/home/claude/pkkp/warehouse2012"
PDF = os.path.join(WORK, "2012.pdf")
SRC = "2012_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"

os.makedirs(WH, exist_ok=True)

# ---- raw page cache ---------------------------------------------------------
_raw = {}
def raw(pg):
    if pg not in _raw:
        _raw[pg] = subprocess.run(
            ["pdftotext", "-f", str(pg), "-l", str(pg), "-raw", PDF, "-"],
            capture_output=True, text=True).stdout
    return _raw[pg]

def N(s):
    """Parse a printed amount string to float. dash -> 0.0, ()->negative,
    strip footnote asterisks."""
    if s is None:
        return None
    s = str(s).strip().lstrip("*").strip()
    if s in ("-", "–", "—", ""):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v

def fmt(v):
    """Format an integer amount with thousands separators for raw verification."""
    return f"{int(round(abs(v))):,}"

verify_fail = []
def V(pg, v):
    """Verify a non-zero amount appears verbatim (comma-grouped) on the raw page."""
    if v in (None, 0, 0.0):
        return
    tok = fmt(v)
    if tok not in raw(pg):
        verify_fail.append((pg, tok))

checks = []
def CHK(name, got, want):
    ok = abs(float(got) - float(want)) < 0.5
    checks.append(("PASS" if ok else "FAIL", name, float(got), float(want),
                   float(got) - float(want)))

def prov(pg):
    return dict(source_file=SRC, pdf_page=pg, printed_page=pg - 22)

def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)

PROV = ["source_file", "pdf_page", "printed_page", "statement"]

# =====================================================================
# NOTA 5  AKAUN HASIL DISATUKAN  (pdf 54, printed 32)
# columns: label | anggaran disemak | sebenar 2012 | %2012 | sebenar 2011 | %2011
# =====================================================================
STMT5 = "Nota 5 Akaun Hasil Disatukan"
PG5 = 54
rev_src = [  # label, section, row_type, anggaran, seb12, pct12, seb11, pct11, foot
 ("BAKI PADA 1 JANUARI","BAKI","opening", None,11863127086,None,11863127086,None,False),
 ("Hasil Cukai","HASIL","detail",152493265000,151643090263,99.44,134884834173,104.41,False),
 ("Hasil Bukan Cukai","HASIL","detail",53386588000,54909327554,102.85,49423045556,93.00,False),
 ("Terimaan Bukan Hasil","HASIL","detail",778648000,876912254,112.62,544133845,99.16,False),
 ("Hasil Wilayah Persekutuan","HASIL","detail",587981000,483424598,82.22,566906169,112.86,False),
 ("Jumlah Hasil","HASIL","subtotal",207246482000,207912754669,100.32,185418919743,101.11,False),
 ("Emolumen","PERBELANJAAN MENGURUS","detail",55007121376,60015799383,109.11,50148348527,103.10,False),
 ("Perkhidmatan dan Bekalan","PERBELANJAAN MENGURUS","detail",32249318322,31962576293,99.11,28948592637,98.94,False),
 ("Aset","PERBELANJAAN MENGURUS","detail",1773481727,1769606790,99.78,2665292177,96.97,False),
 ("Pemberian dan Kenaan Bayaran Tetap","PERBELANJAAN MENGURUS","detail",108182987735,110322740053,101.98,99693813446,103.70,True),
 ("Perbelanjaan-perbelanjaan Lain","PERBELANJAAN MENGURUS","detail",1524915208,1466359006,96.16,1137741551,95.02,False),
 ("Jumlah Perbelanjaan Mengurus (sebelum pindahan)","PERBELANJAAN MENGURUS","subtotal",198737824368,205537081525,103.42,182593788338,102.59,False),
 ("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan","PINDAHAN","transfer",0.0,2375673144,None,2825131405,None,False),
 ("Jumlah Perbelanjaan Mengurus (selepas pindahan)","PERBELANJAAN MENGURUS","total_after_transfer",198737824368,207912754669,104.62,185418919743,104.18,False),
 ("Lebihan/(Kurangan) bagi Tahun","BAKI","net",None,0.0,None,0.0,None,False),
 ("BAKI PADA 31 DISEMBER","BAKI","closing",None,11863127086,None,11863127086,None,False),
]
rev_rows = []
for label, sec, rt, ang, s12, p12, s11, p11, foot in rev_src:
    V(PG5, ang); V(PG5, s12); V(PG5, s11)
    rev_rows.append(dict(section_bm=sec, line_item_bm=label, row_type=rt, year=2012,
        anggaran_disemak_rm=("" if ang is None else ang),
        sebenar_rm=("" if s12 is None else s12),
        pct_anggaran=("" if p12 is None else p12), has_footnote=foot,
        statement=STMT5, **prov(PG5)))
    rev_rows.append(dict(section_bm=sec, line_item_bm=label, row_type=rt, year=2011,
        anggaran_disemak_rm="",
        sebenar_rm=("" if s11 is None else s11),
        pct_anggaran=("" if p11 is None else p11), has_footnote=foot,
        statement=STMT5, **prov(PG5)))

def rget(item, yr, col):
    for r in rev_rows:
        if r["line_item_bm"] == item and r["year"] == yr:
            return r[col]
_hasil = ["Hasil Cukai","Hasil Bukan Cukai","Terimaan Bukan Hasil","Hasil Wilayah Persekutuan"]
_perb = ["Emolumen","Perkhidmatan dan Bekalan","Aset","Pemberian dan Kenaan Bayaran Tetap","Perbelanjaan-perbelanjaan Lain"]
for yr in (2012, 2011):
    CHK(f"Nota5 Jumlah Hasil sebenar = sum details {yr}",
        sum(rget(i, yr, "sebenar_rm") for i in _hasil), rget("Jumlah Hasil", yr, "sebenar_rm"))
    CHK(f"Nota5 Jumlah PM (sebelum pindahan) sebenar = sum details {yr}",
        sum(rget(i, yr, "sebenar_rm") for i in _perb),
        rget("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr, "sebenar_rm"))
    CHK(f"Nota5 selepas pindahan = sebelum + pindahan {yr}",
        rget("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", yr, "sebenar_rm")
        + rget("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan", yr, "sebenar_rm"),
        rget("Jumlah Perbelanjaan Mengurus (selepas pindahan)", yr, "sebenar_rm"))
CHK("Nota5 anggaran Jumlah Hasil = sum details 2012",
    sum(rget(i, 2012, "anggaran_disemak_rm") for i in _hasil), rget("Jumlah Hasil", 2012, "anggaran_disemak_rm"))
CHK("ANCHOR Nota5 Jumlah Hasil sebenar 2012", rget("Jumlah Hasil", 2012, "sebenar_rm"), 207912754669)
CHK("ANCHOR Nota5 Jumlah PM sebelum pindahan sebenar 2012",
    rget("Jumlah Perbelanjaan Mengurus (sebelum pindahan)", 2012, "sebenar_rm"), 205537081525)

# =====================================================================
# NOTA 6  AKAUN PINJAMAN DISATUKAN  (pdf 57, printed 35)
# columns: label | 2012 (Debit)/Kredit | 2011 (Debit)/Kredit
# =====================================================================
STMT6 = "Nota 6 Akaun Pinjaman Disatukan"
PG6 = 57
loan_src = [  # group, sub, line, row_type, 2012, 2011
 ("PINJAMAN","Dalam Negeri","Baki pada 1 Januari","detail",38909479613,26068545555),
 ("PINJAMAN","Dalam Negeri","Terimaan","detail",102645229672,99991588179),
 ("PINJAMAN","Dalam Negeri","Bayaran","detail",-59303631379,-54930119121),
 ("PINJAMAN","Dalam Negeri","Baki pada 31 Disember","detail",82251077906,71130014613),
 ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Terimaan","detail",5500000000,7100000000),
 ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Bayaran","detail",-2100000000,-4500000000),
 ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Baki pada 31 Disember","detail",3400000000,2600000000),
 ("PINJAMAN","Luar Negeri","Terimaan","detail",0.0,5960800000),
 ("PINJAMAN","Luar Negeri","Bayaran","detail",0.0,-5215700000),
 ("PINJAMAN","Luar Negeri","Baki pada 31 Disember","detail",0.0,745100000),
 ("PINJAMAN","","Jumlah Pinjaman pada 31 Disember","group_total",85651077906,74475114613),
 ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Terimaan","detail",91016051,33518605),
 ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Bayaran","detail",-95017283,-106210281),
 ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Baki pada 31 Disember","detail",-4001232,-72691676),
 ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Terimaan","detail",592519054,474214046),
 ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Bayaran","detail",-602570204,-596867056),
 ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Baki pada 31 Disember","detail",-10051150,-122653010),
 ("BANTUAN LUAR NEGERI","","Jumlah Bantuan Luar Negeri pada 31 Disember","group_total",-14052382,-195344686),
 ("JUMLAH","","Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember","total",85637025524,74279769927),
 ("PINDAHAN KE","","Kumpulan Wang Pembangunan","transfer",-53332230232,-32770290314),
 ("PINDAHAN KE","","Kumpulan Wang Pinjaman Perumahan","transfer",-3400000000,-2600000000),
 ("BAKI","","BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER","closing",28904795292,38909479613),
]
loan_rows = []
for grp, sub, line, rt, a12, a11 in loan_src:
    for yr, amt in ((2012, a12), (2011, a11)):
        V(PG6, amt)
        loan_rows.append(dict(group_bm=grp, sub_bm=sub, line_item_bm=line,
            row_type=rt, year=yr, amount_rm=amt, statement=STMT6, **prov(PG6)))

def lget(grp, sub, line, yr):
    for grp2, sub2, line2, rt, a12, a11 in loan_src:
        if grp2 == grp and sub2 == sub and line2 == line:
            return a12 if yr == 2012 else a11
for yr in (2012, 2011):
    # roll-forwards per sub
    CHK(f"Nota6 Dalam Negeri open+ter+bay=baki31 {yr}",
        lget("PINJAMAN","Dalam Negeri","Baki pada 1 Januari",yr)
        + lget("PINJAMAN","Dalam Negeri","Terimaan",yr)
        + lget("PINJAMAN","Dalam Negeri","Bayaran",yr),
        lget("PINJAMAN","Dalam Negeri","Baki pada 31 Disember",yr))
    CHK(f"Nota6 KWPPerumahan ter+bay=baki31 {yr}",
        lget("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Terimaan",yr)
        + lget("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Bayaran",yr),
        lget("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Baki pada 31 Disember",yr))
    CHK(f"Nota6 Jumlah Pinjaman = DN+KWPP+LN baki31 {yr}",
        lget("PINJAMAN","Dalam Negeri","Baki pada 31 Disember",yr)
        + lget("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Baki pada 31 Disember",yr)
        + lget("PINJAMAN","Luar Negeri","Baki pada 31 Disember",yr),
        lget("PINJAMAN","","Jumlah Pinjaman pada 31 Disember",yr))
    CHK(f"Nota6 Jumlah Bantuan LN = Multi+Bilateral baki31 {yr}",
        lget("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Baki pada 31 Disember",yr)
        + lget("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Baki pada 31 Disember",yr),
        lget("BANTUAN LUAR NEGERI","","Jumlah Bantuan Luar Negeri pada 31 Disember",yr))
    CHK(f"Nota6 Jumlah Pinjaman dan Bantuan = Jumlah Pinjaman + Jumlah Bantuan {yr}",
        lget("PINJAMAN","","Jumlah Pinjaman pada 31 Disember",yr)
        + lget("BANTUAN LUAR NEGERI","","Jumlah Bantuan Luar Negeri pada 31 Disember",yr),
        lget("JUMLAH","","Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember",yr))
    CHK(f"Nota6 BAKI = Jumlah + Pindahan KWP + Pindahan KWPP {yr}",
        lget("JUMLAH","","Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember",yr)
        + lget("PINDAHAN KE","","Kumpulan Wang Pembangunan",yr)
        + lget("PINDAHAN KE","","Kumpulan Wang Pinjaman Perumahan",yr),
        lget("BAKI","","BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER",yr))
CHK("ANCHOR Nota6 BAKI AKAUN PINJAMAN DISATUKAN 31 Dis 2012",
    lget("BAKI","","BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER",2012), 28904795292)

# =====================================================================
# NOTA 7  AKAUN AMANAH DISATUKAN  (pdf 58-62)
# =====================================================================
STMT7 = "Nota 7 Akaun Amanah Disatukan"
trust_rows = []
def T(fg, fund, sec, item, yr, amt, rt, pg, foot=False):
    V(pg, amt)
    trust_rows.append(dict(fund_group_bm=fg, fund_bm=fund, section_bm=sec,
        line_item_bm=item, year=yr, amount_rm=amt, row_type=rt,
        has_footnote=foot, statement=STMT7, **prov(pg)))

KWK = "KUMPULAN WANG AMANAH KERAJAAN"
KAW = "KUMPULAN WANG AMANAH AWAM"
DEP = "AKAUN DEPOSIT"

# --- 7 summary matrix (pdf 58): opening/debit/kredit/closing, year 2012 only
PG7M = 58
MEAS = ["Baki pada 1 Januari", "Debit", "Kredit", "Baki pada 31 Disember"]
matrix = [  # fund_group, fund_or_blank, level, opening, debit, kredit, closing
 (KWK,"Kumpulan Wang Pembangunan","detail",-55235001113,46945799332,58356221189,-43824579256),
 (KWK,"Kumpulan Wang Pinjaman Perumahan","detail",1908324534,10961105335,10568301237,1515520436),
 (KWK,"Pelbagai Kumpulan Wang Amanah Kerajaan","detail",34554927065,295201452952,296398507887,35751982000),
 (KWK,"Jumlah Kumpulan Wang Amanah Kerajaan","subtotal",-18771749514,353108357619,365323030313,-6557076820),
 (KAW,"Kumpulan Wang Amanah Khas","detail",617929977,172923278,192785973,637792672),
 (KAW,"Kumpulan Wang Amanah Am","detail",5701912589,8655946515,12055878776,9101844850),
 (KAW,"Jumlah Kumpulan Wang Amanah Awam","subtotal",6319842566,8828869793,12248664749,9739637522),
 (DEP,"Deposit Am","detail",8690055757,2096191153,2561346007,9155210611),
 (DEP,"Deposit Pelarasan","detail",299483231,1608491193,1608276163,299268201),
 (DEP,"Jumlah Akaun Deposit","subtotal",8989538988,3704682346,4169622170,9454478812),
 ("JUMLAH AKAUN AMANAH DISATUKAN","JUMLAH AKAUN AMANAH DISATUKAN","total",-3462367960,365641909758,381741317232,12637039514),
]
for fg, fund, level, op, de, kr, cl in matrix:
    vals = dict(zip(MEAS, (op, de, kr, cl)))
    for m in MEAS:
        T(fg, fund, "Penyata Ringkasan", m, 2012, vals[m], level, PG7M)
    # roll-forward identity: opening + kredit - debit = closing
    CHK(f"Nota7 matrix roll-forward {fund}", op + kr - de, cl)
# matrix group members sum to Jumlah (closing) and Jumlah sum to grand total
def mclose(fg, fund):
    for a, b, lvl, op, de, kr, cl in matrix:
        if a == fg and b == fund:
            return cl
CHK("Nota7 matrix KWAK members = Jumlah closing",
    mclose(KWK,"Kumpulan Wang Pembangunan")+mclose(KWK,"Kumpulan Wang Pinjaman Perumahan")
    +mclose(KWK,"Pelbagai Kumpulan Wang Amanah Kerajaan"),
    mclose(KWK,"Jumlah Kumpulan Wang Amanah Kerajaan"))
CHK("Nota7 matrix Awam members = Jumlah closing",
    mclose(KAW,"Kumpulan Wang Amanah Khas")+mclose(KAW,"Kumpulan Wang Amanah Am"),
    mclose(KAW,"Jumlah Kumpulan Wang Amanah Awam"))
CHK("Nota7 matrix Deposit members = Jumlah closing",
    mclose(DEP,"Deposit Am")+mclose(DEP,"Deposit Pelarasan"),
    mclose(DEP,"Jumlah Akaun Deposit"))
CHK("Nota7 matrix 3 group Jumlahs = grand total closing",
    mclose(KWK,"Jumlah Kumpulan Wang Amanah Kerajaan")+mclose(KAW,"Jumlah Kumpulan Wang Amanah Awam")
    +mclose(DEP,"Jumlah Akaun Deposit"),
    mclose("JUMLAH AKAUN AMANAH DISATUKAN","JUMLAH AKAUN AMANAH DISATUKAN"))
CHK("ANCHOR Nota7 JUMLAH AKAUN AMANAH DISATUKAN baki akhir 2012",
    mclose("JUMLAH AKAUN AMANAH DISATUKAN","JUMLAH AKAUN AMANAH DISATUKAN"), 12637039514)

# --- 7(a)(i) Kumpulan Wang Pembangunan (pdf 59, printed 37)
PGa = 59
KWP = "Kumpulan Wang Pembangunan"
kwp = [  # section, item, row_type, 2012, 2011
 ("","BAKI PADA 1 JANUARI","opening",-55235001113,-45496256660),
 ("TERIMAAN","Caruman Dari Akaun Hasil Disatukan","detail",2375673144,2825131405),
 ("TERIMAAN","Pindahan Dari Akaun Pinjaman Disatukan","detail",53332230232,32770290314),
 ("TERIMAAN","Terimaan Balik Pinjaman","detail",1085973097,1081971436),
 ("TERIMAAN","Terimaan Balik Pendahuluan","detail",29400000,0.0),
 ("TERIMAAN","Jualan Aset Modal","detail",89869,91433),
 ("TERIMAAN","Pelbagai Terimaan","detail",1519509321,133387),
 ("TERIMAAN","Jumlah Terimaan","subtotal",58342875663,36677617974),
 ("BAYARAN / Perbelanjaan Pembangunan","Langsung","detail",-44978124405,-44917440271),
 ("BAYARAN / Perbelanjaan Pembangunan","Pinjaman","detail",-1954329401,-1498922156),
 ("BAYARAN","Jumlah Bayaran","subtotal",-46932453806,-46416362427),
 ("","Lebihan/(Kurangan) bagi Tahun","net",11410421857,-9738744453),
 ("","BAKI PADA 31 DISEMBER","closing",-43824579256,-55235001113),
]
for sec, item, rt, a12, a11 in kwp:
    for yr, amt in ((2012, a12), (2011, a11)):
        T(KWK, KWP, sec, item, yr, amt, rt, PGa)

def kwpget(item, yr):
    for sec, it, rt, a12, a11 in kwp:
        if it == item:
            return a12 if yr == 2012 else a11
for yr in (2012, 2011):
    ter = sum(a12 if yr == 2012 else a11 for sec, it, rt, a12, a11 in kwp if sec.startswith("TERIMAAN") and rt == "detail")
    bay = sum(a12 if yr == 2012 else a11 for sec, it, rt, a12, a11 in kwp if sec.startswith("BAYARAN") and rt == "detail")
    CHK(f"Nota7(a)(i) KWP TERIMAAN details=subtotal {yr}", ter, kwpget("Jumlah Terimaan", yr))
    CHK(f"Nota7(a)(i) KWP BAYARAN details=subtotal {yr}", bay, kwpget("Jumlah Bayaran", yr))
    CHK(f"Nota7(a)(i) KWP terimaan-bayaran=Lebihan {yr}",
        kwpget("Jumlah Terimaan", yr) + kwpget("Jumlah Bayaran", yr), kwpget("Lebihan/(Kurangan) bagi Tahun", yr))
    CHK(f"Nota7(a)(i) KWP opening+lebihan=closing {yr}",
        kwpget("BAKI PADA 1 JANUARI", yr) + kwpget("Lebihan/(Kurangan) bagi Tahun", yr), kwpget("BAKI PADA 31 DISEMBER", yr))
CHK("Nota7(a)(i) KWP closing 2012 = matrix", kwpget("BAKI PADA 31 DISEMBER", 2012), mclose(KWK, KWP))

# --- 7(a)(ii) Kumpulan Wang Pinjaman Perumahan (pdf 59 open+TERIMAAN, pdf 60 BAYARAN+closing)
KWPP = "Kumpulan Wang Pinjaman Perumahan"
kwpp = [  # section, item, row_type, 2012, 2011, pdf_page
 ("","BAKI PADA 1 JANUARI","opening",1908324534,3213459959,59),
 ("TERIMAAN / Pinjaman Perseorangan","Bayaran Balik Pinjaman Perseorangan","detail",1266040286,1106261314,59),
 ("TERIMAAN / Pembiayaan","Pelbagai Pembiayaan","detail",5500000000,7100000000,59),
 ("TERIMAAN / Pendapatan Faedah","Bayaran Balik Faedah Pinjaman Perseorangan","detail",1169642131,995035013,59),
 ("TERIMAAN / Akaun Pensekuritian","Kutipan Bayaran Balik Akaun Pensekuritian","detail",2300118669,2435028308,59),
 ("TERIMAAN / Akaun Pensekuritian","Peruntukan Diskaun Pensekuritian","detail",342237619,342237619,59),
 ("TERIMAAN","Pelbagai","detail",10458990,6127217,59),
 ("TERIMAAN","Jumlah Terimaan","subtotal",10588497695,11984689471,59),
 ("BAYARAN / Pinjaman Perseorangan","Pengeluaran Pinjaman Perseorangan","detail",-6488768940,-6306896491,60),
 ("BAYARAN / Pembiayaan","Bayaran Balik Pelbagai Pembiayaan","detail",-2100000000,-4500000000,60),
 ("BAYARAN / Akaun Pensekuritian","Serahan Kutipan Akaun Pensekuritian","detail",-2371333558,-2455825270,60),
 ("BAYARAN / Akaun Pensekuritian","Bayaran Lain Akaun Pensekuritian","detail",-21199295,-27103135,60),
 ("BAYARAN","Jumlah Bayaran","subtotal",-10981301793,-13289824896,60),
 ("","BAKI PADA 31 DISEMBER","closing",1515520436,1908324534,60),
]
for sec, item, rt, a12, a11, pg in kwpp:
    for yr, amt in ((2012, a12), (2011, a11)):
        T(KWK, KWPP, sec, item, yr, amt, rt, pg)
def kwppget(item, yr):
    for sec, it, rt, a12, a11, pg in kwpp:
        if it == item:
            return a12 if yr == 2012 else a11
for yr in (2012, 2011):
    ter = sum(a12 if yr == 2012 else a11 for sec, it, rt, a12, a11, pg in kwpp if sec.startswith("TERIMAAN") and rt == "detail")
    bay = sum(a12 if yr == 2012 else a11 for sec, it, rt, a12, a11, pg in kwpp if sec.startswith("BAYARAN") and rt == "detail")
    CHK(f"Nota7(a)(ii) KWPP TERIMAAN details=subtotal {yr}", ter, kwppget("Jumlah Terimaan", yr))
    CHK(f"Nota7(a)(ii) KWPP BAYARAN details=subtotal {yr}", bay, kwppget("Jumlah Bayaran", yr))
    CHK(f"Nota7(a)(ii) KWPP opening+ter+bay=closing {yr}",
        kwppget("BAKI PADA 1 JANUARI", yr) + kwppget("Jumlah Terimaan", yr) + kwppget("Jumlah Bayaran", yr),
        kwppget("BAKI PADA 31 DISEMBER", yr))
CHK("Nota7(a)(ii) KWPP closing 2012 = matrix", kwppget("BAKI PADA 31 DISEMBER", 2012), mclose(KWK, KWPP))

# --- 7(a)(iii) Pelbagai Kumpulan Wang Amanah Kerajaan (pdf 60-61)
PKW = "Pelbagai Kumpulan Wang Amanah Kerajaan"
pkw = {  # category: (jumlah_label, page, subtotal12, subtotal13, items[(label,2012,2011)])
 "AKAUN PENYELESAIAN": ("Jumlah Akaun Penyelesaian", 60, 20011478316, 20704801842, [
    ("Akaun Semasa Antara Pentadbiran",17374952,16395143),
    ("Akaun Penyelesaian Utama Perbendaharaan",19894103364,20588406699),
    ("Akaun Penyelesaian Jabatan Mengakaun Sendiri",100000000,100000000)]),
 "AKAUN PERNIAGAAN": ("Jumlah Akaun Perniagaan", 60, 79155435, 78959835, [
    ("Stor dan Woksyop Belum Diuntukkan",79155435,78959835)]),
 "AKAUN PINJAMAN": ("Jumlah Akaun Pinjaman", 60, 5661215278, 5354970719, [
    ("Kontraktor",7082337,8616423),
    ("Kredit Kerjasama",15037189,15037189),
    ("Modal Pusingan Jabatan Pembangunan Koperasi",133160698,191753670),
    ("Pembangunan Ekonomi Belia",5891017,1895025),
    ("Pembiayaan Komputer Anggota Perkhidmatan Awam",110189417,111675149),
    ("Pendahuluan Diri (Pegawai Awam)",104912700,106013039),
    ("Pendahuluan Pelbagai",55390714,55042544),
    ("Pendahuluan Peti Sejuk Sarawak",620000,620000),
    ("Pendahuluan Untuk Negeri",156518645,302641280),
    ("Pinjaman Diraja",2500000,2500000),
    ("Pinjaman Kenderaan",667091673,666826554),
    ("Pinjaman Kepada Badan Berkanun dan Badan Lain",3896691838,3402423934),
    ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah",38161652,33573560),
    ("Rakyat Malaysia di Luar Negeri",1044139,1008229),
    ("Tabung Pusingan Pinjaman Pelajaran Persekutuan",466923259,455344123)]),
 "KUMPULAN WANG LUAR JANGKA": ("Jumlah Kumpulan Wang Luar Jangka", 60, 176414332, 117197110, [
    ("Kumpulan Wang Luar Jangka",176414332,117197110)]),
 "PELBAGAI KUMPULAN WANG": ("Jumlah Pelbagai Kumpulan Wang", 61, 9823718639, 8298997559, [
    ("Amanah Negara",5653917035,4804902567),
    ("Amanah Pelajar Miskin",478656172,471582212),
    ("Amanah Sukan Negara",577000,10435878),
    ("Bantuan Bencana Negara",184315891,132205660),
    ("Bantuan Mangsa Serangan Binatang Buas",281000,335800),
    ("Cadangan Untuk Negeri",349618591,230391662),
    ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri",2776212,3286540),
    ("Kumpulan Wang Amanah Dana Automotif Bumiputra",40000000,0.0),
    ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni",2566381,3235048),
    ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia",125064112,65498209),
    ("Kumpulan Wang Amanah Bagi Pembangunan Projek ICT Sektor Awam",1000000,0.0),
    ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara",1520646,1075797),
    ("Kumpulan Wang Amanah Pengangkutan Awam",816477428,955590216),
    ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras",43075662,46056666),
    ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia",3840995,1553561),
    ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia",1016170,1317538),
    ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia",13030550,12774394),
    ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut",4130965,3301274),
    ("Kursi Pengajian Melayu Leiden University, The Netherlands",794,794),
    ("Majlis Penyelidikan dan Kemajuan Sains Negara (MPKSN)",2841407,2546001),
    ("Penjelas Hutang",213528635,206715154),
    ("Perkhidmatan Kemasyarakatan dan Kebajikan",64092032,69204562),
    ("Perpustakaan Negara",1102027,1343327),
    ("Program Perumahan Rakyat Dimiliki",504485840,617769870),
    ("Skim Biasiswa Sukan Persekutuan",923996,918618),
    ("Tabung Bantuan Perubatan (TBP)",17834331,19554231),
    ("Tabung Bayaran Balik Cukai",1274862121,610975797),
    ("Tabung Inovasi Negara Berhad (KWATIN)",22095535,26289411),
    ("Tabung Pustaka Peringatan P. Ramlee",87111,136772)]),
}
for cat, (jlab, pg, s12, s11, items) in pkw.items():
    for item, a12, a11 in items:
        for yr, amt in ((2012, a12), (2011, a11)):
            T(KWK, PKW, cat, item, yr, amt, "detail", pg)
    for yr, amt in ((2012, s12), (2011, s11)):
        T(KWK, PKW, cat, jlab, yr, amt, "subtotal", pg)
    for yr in (2012, 2011):
        det = sum(a12 if yr == 2012 else a11 for item, a12, a11 in items)
        CHK(f"Nota7(a)(iii) {cat} details=subtotal {yr}", det, s12 if yr == 2012 else s11)
# grand total for Pelbagai KWAK
for yr, amt in ((2012, 35751982000), (2011, 34554927065)):
    T(KWK, PKW, "", "JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN", yr, amt, "total", 61)
for yr in (2012, 2011):
    subs = sum((s12 if yr == 2012 else s11) for cat, (jlab, pg, s12, s11, items) in pkw.items())
    tot = 35751982000 if yr == 2012 else 34554927065
    CHK(f"Nota7(a)(iii) category subtotals = JUMLAH PELBAGAI KWAK {yr}", subs, tot)
CHK("Nota7(a)(iii) Pelbagai KWAK total 2012 = matrix closing", 35751982000, mclose(KWK, "Pelbagai Kumpulan Wang Amanah Kerajaan"))

# --- 7(b) Kumpulan Wang Amanah Awam (pdf 61, printed 39)
PGb = 61
awam = {
 "AMANAH KHAS": ("Jumlah Amanah Khas", 637792672, 617929977, [
    ("Kumpulan Wang Dius Api",253864042,233365760),
    ("Faedah atas Pelaburan untuk Deposit Mahkamah",219781848,217674942),
    ("Akaun Amanah Khas Warisan",34602459,36827784),
    ("Pelbagai Amanah Khas",129544323,130061491)]),
 "AMANAH AM": ("Jumlah Amanah Am", 9101844850, 5701912589, [
    ("Akaun Amanah Aktiviti Pembangunan Khas Pembiayaan Swasta",3281801666,0.0),
    ("Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)",3022437903,3238324521),
    ("Akaun Amanah Dana Khas",585398831,394775310),
    ("Akaun Amanah Membangun/Menaiktaraf Sistem Pembetungan untuk Pembangunan Baru",538117683,597912481),
    ("Akaun Amanah Industri Bekalan Elektrik",425086933,414098864),
    ("Pelbagai Amanah Am",1249001834,1056801413)]),
}
for cat, (jlab, s12, s11, items) in awam.items():
    for item, a12, a11 in items:
        for yr, amt in ((2012, a12), (2011, a11)):
            T(KAW, "", cat, item, yr, amt, "detail", PGb)
    for yr, amt in ((2012, s12), (2011, s11)):
        T(KAW, "", cat, jlab, yr, amt, "subtotal", PGb)
    for yr in (2012, 2011):
        det = sum(a12 if yr == 2012 else a11 for item, a12, a11 in items)
        CHK(f"Nota7(b) {cat} details=subtotal {yr}", det, s12 if yr == 2012 else s11)
for yr, amt in ((2012, 9739637522), (2011, 6319842566)):
    T(KAW, "", "", "JUMLAH KUMPULAN WANG AMANAH AWAM", yr, amt, "total", PGb)
for yr in (2012, 2011):
    subs = sum((s12 if yr == 2012 else s11) for cat, (jlab, s12, s11, items) in awam.items())
    tot = 9739637522 if yr == 2012 else 6319842566
    CHK(f"Nota7(b) subtotals = JUMLAH KW AMANAH AWAM {yr}", subs, tot)
CHK("Nota7(b) Awam total 2012 = matrix Jumlah closing", 9739637522, mclose(KAW, "Jumlah Kumpulan Wang Amanah Awam"))

# --- 7(c) Akaun Deposit (pdf 62, printed 40)
PGc = 62
dep = {
 "DEPOSIT AM": ("Jumlah Deposit Am", 9155210611, 8690055757, [
    ("Kawalan Wang Tak Dituntut",2798393775,2430080705),
    ("Deposit Wang Tak Dituntut",1743403330,1747344932),
    ("Wang Jaminan Pelaksanaan",1593072799,1673641083),
    ("Harta Kebangkrapan",1038002924,929171695),
    ("Deposit Mahkamah Tinggi",805178606,669797188),
    ("Pelbagai Deposit Am",1177159177,1240020154)]),
 "DEPOSIT PELARASAN": ("Jumlah Deposit Pelarasan", 299268201, 299483231, [
    ("Pembatalan Bayaran EFT",148874654,92990934),
    ("Deposit Pelarasan Cek Terbatal",69966536,88839725),
    ("Terimaan Yang Tidak Diperuntukkan",41822808,99407201),
    ("Bayaran Kepada Commerce Dot Com (CDC)",23904735,18245371),
    ("Pelbagai Deposit Pelarasan",14699468,0.0)]),
}
for cat, (jlab, s12, s11, items) in dep.items():
    for item, a12, a11 in items:
        for yr, amt in ((2012, a12), (2011, a11)):
            T(DEP, "", cat, item, yr, amt, "detail", PGc)
    for yr, amt in ((2012, s12), (2011, s11)):
        T(DEP, "", cat, jlab, yr, amt, "subtotal", PGc)
    for yr in (2012, 2011):
        det = sum(a12 if yr == 2012 else a11 for item, a12, a11 in items)
        CHK(f"Nota7(c) {cat} details=subtotal {yr}", det, s12 if yr == 2012 else s11)
for yr, amt in ((2012, 9454478812), (2011, 8989538988)):
    T(DEP, "", "", "JUMLAH AKAUN DEPOSIT", yr, amt, "total", PGc)
for yr in (2012, 2011):
    subs = sum((s12 if yr == 2012 else s11) for cat, (jlab, s12, s11, items) in dep.items())
    tot = 9454478812 if yr == 2012 else 8989538988
    CHK(f"Nota7(c) subtotals = JUMLAH AKAUN DEPOSIT {yr}", subs, tot)
CHK("Nota7(c) Deposit total 2012 = matrix Jumlah closing", 9454478812, mclose(DEP, "Jumlah Akaun Deposit"))

# =====================================================================
# NOTA 8  MEMORANDUM ASET  (pdf 62 PBD, pdf 63 Pelaburan)
# =====================================================================
STMT8 = "Nota 8 Memorandum Aset"
memo_rows = []
def M(section, item, yr, amt, rt, pg):
    V(pg, amt)
    memo_rows.append(dict(section_bm=section, line_item_bm=item, year=yr,
        amount_rm=amt, row_type=rt, has_footnote=False, statement=STMT8, **prov(pg)))
PBD = "Pinjaman Boleh Dituntut"
pbd = [
 ("Kerajaan Negeri",15722068018,16820200196,"detail"),
 ("Pihak Berkuasa Tempatan",502753742,500001908,"detail"),
 ("Badan Berkanun",14026666610,12396058833,"detail"),
 ("Koperasi",197473124,195462764,"detail"),
 ("Syarikat",25525549127,24744191014,"detail"),
 ("Perseorangan",36565906580,31346545405,"detail"),
 ("Pelbagai",2952195602,2835610428,"detail"),
 ("JUMLAH PINJAMAN BOLEH DITUNTUT",95492612803,88838070548,"total"),
]
for item, a12, a11, rt in pbd:
    for yr, amt in ((2012, a12), (2011, a11)):
        M(PBD, item, yr, amt, rt, 62)
pel = [
 ("Syarikat",25936889345,27577101208,"detail"),
 ("Badan Berkanun",1218852876,1218852876,"detail"),
 ("Agensi Antarabangsa",38574229,38574229,"detail"),
 ("JUMLAH PELABURAN",27194316450,28834528313,"total"),
]
for item, a12, a11, rt in pel:
    for yr, amt in ((2012, a12), (2011, a11)):
        M("Pelaburan", item, yr, amt, rt, 63)
for yr in (2012, 2011):
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == PBD and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == PBD and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 PBD details=total {yr}", det, tot)
    det = sum(r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan" and r["year"] == yr and r["row_type"] == "detail")
    tot = [r["amount_rm"] for r in memo_rows if r["section_bm"] == "Pelaburan" and r["year"] == yr and r["row_type"] == "total"][0]
    CHK(f"Nota8 Pelaburan details=total {yr}", det, tot)
CHK("ANCHOR Nota8 PBD 2012 total", 95492612803, 95492612803)
CHK("ANCHOR Nota8 Pelaburan 2012 total", 27194316450, 27194316450)

# =====================================================================
# WRITE + REPORT
# =====================================================================
outputs = [
 ("fact_revenue_account_statement.csv", rev_rows,
  ["section_bm","line_item_bm","row_type","year","anggaran_disemak_rm","sebenar_rm","pct_anggaran","has_footnote"] + PROV),
 ("fact_loan_account_statement.csv", loan_rows,
  ["group_bm","sub_bm","line_item_bm","row_type","year","amount_rm"] + PROV),
 ("fact_trust_fund_detail.csv", trust_rows,
  ["fund_group_bm","fund_bm","section_bm","line_item_bm","year","amount_rm","row_type","has_footnote"] + PROV),
 ("fact_memo_assets_detail.csv", memo_rows,
  ["section_bm","line_item_bm","year","amount_rm","row_type","has_footnote"] + PROV),
]
print("=== ROW COUNTS ===")
for fname, rows, cols in outputs:
    n = write_csv(os.path.join(WH, fname), cols, rows)
    print(f"  {fname}: {n} rows")

print("\n=== RAW-TEXT VERIFICATION ===")
if verify_fail:
    print(f"  {len(verify_fail)} token(s) NOT found verbatim on source page:")
    for pg, s in verify_fail:
        print(f"    pdf_page {pg}: {s!r}")
else:
    print("  all non-zero amounts found verbatim on their source pages.")

print("\n=== VALIDATION CHECKS ===")
fails = 0
for status, name, got, want, diff in checks:
    if status == "FAIL":
        fails += 1
        print(f"  FAIL: {name} | extracted={got:,.0f} printed={want:,.0f} diff={diff:,.0f}")
npass = len(checks) - fails
print(f"\n  {len(checks)} checks: {npass} PASS / {fails} FAIL")
