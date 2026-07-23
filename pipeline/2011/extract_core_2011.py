#!/usr/bin/env python3
"""Core fiscal statements for PKKP FY2011 (RMKe-10 era, pre-GST).

2011 anchors: printed = pdf - 18 (pdf49 -> printed 31, confirmed via folios).
Statement pages read CLEANLY from pdftotext -layout (unlike the 2012 volume
which needed per-page -raw for the Notes overprint).
  Penyata Kedudukan Kewangan      pdf49  printed31
  Penyata Penerimaan & Pembayaran pdf50-51 printed32-33
  Penyata Prestasi Kewangan       pdf52  printed34
  Penyata Akaun Memorandum        pdf53  printed35
Every typed token is verified verbatim against its page's -layout text.
Amounts exact RM as printed (sen kept); en-dash=0.0; parens=negative.
"""
import csv, os, sys

YEAR, PRIOR = 2011, 2010
SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2011"
os.makedirs(OUT, exist_ok=True)
PP = lambda pdf: pdf - 18
PROV = ["source_file", "pdf_page", "printed_page", "statement"]

layout = open("/home/claude/pkkp/work/2011/full.txt", encoding="utf-8").read().split("\f")
def page_text(pdf): return layout[pdf-1]

verify_fail=[]
def V(pdf, s):
    s=s.strip()
    if s in ("-","–","—",""): return
    if s not in page_text(pdf):
        verify_fail.append((pdf, s))

def N(tok):
    tok=tok.strip().replace("*","")
    if tok in {"–","-","—",""}: return 0.0
    neg=tok.startswith("(") and tok.endswith(")")
    tok=tok.strip("()").replace(",","")
    return -float(tok) if neg else float(tok)

def w(name, header, rows):
    with open(os.path.join(OUT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f); cw.writerow(header); cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")

checks=[]
def chk(label, got, want, tol=0.5):
    ok = abs(got-want) <= tol
    checks.append((ok,label,got,want)); return ok

# ---------------- 1. Penyata Kedudukan Kewangan (pdf49) ----------------
def financial_position():
    stmt="Penyata Kedudukan Kewangan"; pg=49
    src=[
        ("WANG AWAM","WANG TUNAI","3","24,466,775,527","21,350,293,944"),
        ("WANG AWAM","PELABURAN","4","22,843,463,212","20,566,225,647"),
        ("WANG AWAM","JUMLAH WANG AWAM","","47,310,238,739","41,916,519,591"),
        ("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN","5","11,863,127,086","11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN","6","38,909,479,613","26,068,545,555"),
        ("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN","7","(3,462,367,960)","3,984,846,950"),
        ("KUMPULAN WANG DISATUKAN","JUMLAH KUMPULAN WANG DISATUKAN","","47,310,238,739","41,916,519,591"),
    ]
    rows=[]
    for sec,item,nota,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([sec,item,nota,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_financial_position.csv",["section","line_item_bm","nota","year","amount_rm"]+PROV,rows)
    # additivity
    d={ (r[0],r[1],r[3]):r[4] for r in rows }
    chk("finpos WANG AWAM subtotal 2011", d[("WANG AWAM","WANG TUNAI",YEAR)]+d[("WANG AWAM","PELABURAN",YEAR)], d[("WANG AWAM","JUMLAH WANG AWAM",YEAR)])
    chk("finpos KWD subtotal 2011", d[("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN",YEAR)]+d[("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN",YEAR)]+d[("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN",YEAR)], d[("KUMPULAN WANG DISATUKAN","JUMLAH KUMPULAN WANG DISATUKAN",YEAR)])
    chk("finpos WANG AWAM == KWD 2011", d[("WANG AWAM","JUMLAH WANG AWAM",YEAR)], d[("KUMPULAN WANG DISATUKAN","JUMLAH KUMPULAN WANG DISATUKAN",YEAR)])

# ---------------- 2. Cash statement (pdf50 terimaan / pdf51 bayaran) ----------------
def cash_statement():
    stmt="Penyata Penerimaan dan Pembayaran Wang Tunai"
    src=[
        ("TERIMAAN","Hasil","Hasil Cukai","134,884,834,173","109,515,185,813",50),
        ("TERIMAAN","Hasil","Hasil Bukan Cukai","49,423,045,556","48,867,434,930",50),
        ("TERIMAAN","Hasil","Terimaan Bukan Hasil","544,133,845","793,006,447",50),
        ("TERIMAAN","Hasil","Hasil Wilayah Persekutuan","566,906,169","477,335,128",50),
        ("TERIMAAN","Hasil","Jumlah Hasil","185,418,919,743","159,652,962,318",50),
        ("TERIMAAN","Pinjaman","Dalam Negeri","107,091,588,179","72,735,466,667",50),
        ("TERIMAAN","Pinjaman","Luar Negeri","5,960,800,000","4,047,250,000",50),
        ("TERIMAAN","Pinjaman","Jumlah Pinjaman","113,052,388,179","76,782,716,667",50),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Multilateral","33,518,605","117,087,038",50),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Bilateral","474,214,046","330,740,067",50),
        ("TERIMAAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","507,732,651","447,827,105",50),
        ("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","866,221,436","784,998,160",50),
        ("TERIMAAN","Terimaan Modal","Jualan Aset Modal","91,433","73,318",50),
        ("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","133,387","30,874,234",50),
        ("TERIMAAN","Terimaan Modal","Jualan Instrumen Kewangan","–","–",50),
        ("TERIMAAN","Terimaan Modal","Jumlah Terimaan Modal","866,446,256","815,945,712",50),
        ("TERIMAAN","Terimaan Lain","Terimaan Amanah","890,615,197","–",50),
        ("TERIMAAN","Terimaan Lain","Inisiatif Pembiayaan Swasta (PFI)","2,385,876,399","3,262,830,183",50),
        ("TERIMAAN","Terimaan Lain","Jumlah Terimaan Lain","3,276,491,596","3,262,830,183",50),
        ("JUMLAH","Jumlah Terimaan","Jumlah Terimaan","303,121,978,425","240,962,281,985",50),
        ("BAYARAN","Perbelanjaan Mengurus","Emolumen","50,148,348,527","46,662,939,934",51),
        ("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","28,948,592,637","23,840,844,635",51),
        ("BAYARAN","Perbelanjaan Mengurus","Aset","2,665,292,177","1,869,375,321",51),
        ("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","99,693,813,446","78,104,600,235",51),
        ("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan Lain","1,137,741,551","1,154,849,140",51),
        ("BAYARAN","Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus","182,593,788,338","151,632,609,265",51),
        ("BAYARAN","Perbelanjaan Pembangunan","Langsung","44,917,440,271","49,096,365,990",51),
        ("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","1,498,922,156","3,695,264,230",51),
        ("BAYARAN","Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan","46,416,362,427","52,791,630,220",51),
        ("BAYARAN","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)","3,584,962,054","5,012,367,936",51),
        ("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","2,061,487,565","3,840,273,200",51),
        ("BAYARAN","Pinjaman","Dalam Negeri","59,430,119,121","31,004,584,571",51),
        ("BAYARAN","Pinjaman","Luar Negeri","5,215,700,000","–",51),
        ("BAYARAN","Pinjaman","Jumlah Pinjaman","64,645,819,121","31,004,584,571",51),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Multilateral","106,210,281","239,356,767",51),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Bilateral","596,867,056","591,991,257",51),
        ("BAYARAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","703,077,337","831,348,024",51),
        ("BAYARAN","Bayaran Lain","Akaun Amanah","–","2,019,293,299",51),
        ("JUMLAH","Jumlah Bayaran","Jumlah Bayaran","300,005,496,842","247,132,106,515",51),
        ("JUMLAH","Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai","3,116,481,583","(6,169,824,530)",51),
        ("JUMLAH","Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari","21,350,293,944","27,520,118,474",51),
        ("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER","24,466,775,527","21,350,293,944",51),
    ]
    rows=[]
    for flow,cat,item,a,b,pg in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([flow,cat,item,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_cash_statement.csv",["flow","category_bm","item_bm","year","amount_rm"]+PROV,rows)
    d={}
    for flow,cat,item,yr,amt,*_ in rows: d[(cat,item,yr)]=amt
    dt={}  # terimaan-only, avoids Jumlah Pinjaman/Bantuan collision with bayaran
    for flow,cat,item,yr,amt,*_ in rows:
        if flow in ("TERIMAAN","JUMLAH"): dt[(cat,item,yr)]=amt
    # subtotal additivity 2011
    chk("cash Jumlah Hasil", d[("Hasil","Hasil Cukai",YEAR)]+d[("Hasil","Hasil Bukan Cukai",YEAR)]+d[("Hasil","Terimaan Bukan Hasil",YEAR)]+d[("Hasil","Hasil Wilayah Persekutuan",YEAR)], d[("Hasil","Jumlah Hasil",YEAR)])
    chk("cash Jumlah Pinjaman T", d[("Pinjaman","Dalam Negeri",YEAR)]+d[("Pinjaman","Luar Negeri",YEAR)], d[("Pinjaman","Jumlah Pinjaman",YEAR)])
    chk("cash Jumlah Terimaan Modal", d[("Terimaan Modal","Terimaan Balik Pinjaman",YEAR)]+d[("Terimaan Modal","Jualan Aset Modal",YEAR)]+d[("Terimaan Modal","Pelbagai Terimaan Modal",YEAR)]+d[("Terimaan Modal","Jualan Instrumen Kewangan",YEAR)], d[("Terimaan Modal","Jumlah Terimaan Modal",YEAR)])
    chk("cash Jumlah Terimaan Lain", d[("Terimaan Lain","Terimaan Amanah",YEAR)]+d[("Terimaan Lain","Inisiatif Pembiayaan Swasta (PFI)",YEAR)], d[("Terimaan Lain","Jumlah Terimaan Lain",YEAR)])
    tot_ter = dt[("Hasil","Jumlah Hasil",YEAR)]+dt[("Pinjaman","Jumlah Pinjaman",YEAR)]+dt[("Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri",YEAR)]+dt[("Terimaan Modal","Jumlah Terimaan Modal",YEAR)]+dt[("Terimaan Lain","Jumlah Terimaan Lain",YEAR)]
    chk("cash Jumlah Terimaan", tot_ter, dt[("Jumlah Terimaan","Jumlah Terimaan",YEAR)])
    chk("cash Jumlah PM", d[("Perbelanjaan Mengurus","Emolumen",YEAR)]+d[("Perbelanjaan Mengurus","Perkhidmatan dan Bekalan",YEAR)]+d[("Perbelanjaan Mengurus","Aset",YEAR)]+d[("Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap",YEAR)]+d[("Perbelanjaan Mengurus","Perbelanjaan Lain",YEAR)], d[("Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus",YEAR)])
    tot_bay = (d[("Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus",YEAR)]+d[("Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan",YEAR)]
               +d[("Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)",YEAR)]+d[("Perbelanjaan Modal","Pembelian Instrumen Kewangan",YEAR)]
               +d[("Pinjaman","Jumlah Pinjaman",YEAR)]+d[("Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri",YEAR)]+d[("Bayaran Lain","Akaun Amanah",YEAR)])
    chk("cash Jumlah Bayaran", tot_bay, d[("Jumlah Bayaran","Jumlah Bayaran",YEAR)])
    chk("cash Tambahan tunai == Ter-Bay", d[("Jumlah Terimaan","Jumlah Terimaan",YEAR)]-d[("Jumlah Bayaran","Jumlah Bayaran",YEAR)], d[("Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai",YEAR)])
    chk("cash 31 Dis == 1 Jan + Tambahan", d[("Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari",YEAR)]+d[("Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai",YEAR)], d[("WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER",YEAR)])

# ---------------- 3. Penyata Prestasi Kewangan (pdf52) ----------------
def performance():
    stmt="Penyata Prestasi Kewangan"; pg=52
    src3=[("HASIL","revenue","183,374,609,000","185,418,919,743","159,652,962,318"),
          ("Belanja Mengurus","opex","177,979,824,890","182,593,788,338","151,632,609,265"),
          ("LEBIHAN HASIL","current_balance","5,394,784,110","2,825,131,405","8,020,353,053"),
          ("Belanja Pembangunan","devex","51,424,046,381","46,416,362,427","52,791,630,220"),
          ("LEBIHAN / (KURANGAN) KESELURUHAN","overall_deficit","(46,029,262,271)","(43,591,231,022)","(44,771,277,167)")]
    src2=[("Pinjaman dan Bantuan Luar Negeri","financing_net_borrowing","45,611,224,372","40,094,611,177"),
          ("Terimaan Balik Pinjaman dan Pelbagai Terimaan","financing_capital_receipts","1,082,196,256","1,526,473,333"),
          ("Perubahan Tunai, Pelaburan dan Amanah","financing_cash_inv_trust_change","(3,102,189,606)","3,150,192,657"),
          ("JUMLAH PEMBIAYAAN","total_financing","43,591,231,022","44,771,277,167")]
    rows=[]
    for label,code,ag,seb,pri in src3:
        for t in (ag,seb,pri): V(pg,t)
        rows.append([label,code,YEAR,"anggaran",N(ag),SRC,pg,PP(pg),stmt])
        rows.append([label,code,YEAR,"sebenar",N(seb),SRC,pg,PP(pg),stmt])
        rows.append([label,code,PRIOR,"sebenar",N(pri),SRC,pg,PP(pg),stmt])
    for label,code,seb,pri in src2:
        for t in (seb,pri): V(pg,t)
        rows.append([label,code,YEAR,"sebenar",N(seb),SRC,pg,PP(pg),stmt])
        rows.append([label,code,PRIOR,"sebenar",N(pri),SRC,pg,PP(pg),stmt])
    w("fact_financial_performance.csv",["line_item_bm","line_code","year","basis","amount_rm"]+PROV,rows)
    d={(r[1],r[3]):r[4] for r in rows}
    chk("prestasi lebihan hasil 2011 sebenar", d[("revenue","sebenar")]-d[("opex","sebenar")], d[("current_balance","sebenar")])
    chk("prestasi kurangan keseluruhan 2011 sebenar", d[("current_balance","sebenar")]-d[("devex","sebenar")], d[("overall_deficit","sebenar")])
    chk("prestasi jumlah pembiayaan 2011", d[("financing_net_borrowing","sebenar")]+d[("financing_capital_receipts","sebenar")]+d[("financing_cash_inv_trust_change","sebenar")], d[("total_financing","sebenar")])
    chk("prestasi pembiayaan == -kurangan 2011", d[("total_financing","sebenar")], -d[("overall_deficit","sebenar")])

# ---------------- 4. Penyata Akaun Memorandum (pdf53) ----------------
def memorandum():
    stmt="Penyata Akaun Memorandum"; pg=53
    src=[("MEMORANDUM ASET","Pinjaman Boleh Dituntut","8","88,838,070,548","82,319,087,678"),
         ("MEMORANDUM ASET","Pelaburan","8","28,222,949,922","27,723,148,058"),
         ("MEMORANDUM LIABILITI","Hutang Awam","9","456,127,663,265","407,101,235,939"),
         ("MEMORANDUM LIABILITI","Pelbagai Liabiliti","9","241,513,526","206,605,049")]
    rows=[]
    for sec,item,nota,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([sec,item,yr,N(amt),SRC,pg,PP(pg),stmt])
    # schema fact_memorandum: section,line_item_bm,year,amount_rm
    w("fact_memorandum.csv",["section","line_item_bm","year","amount_rm"]+PROV,[[r[0],r[1],r[2],r[3]]+r[4:] for r in rows])

financial_position(); cash_statement(); performance(); memorandum()

print("\n=== CORE INTERNAL CHECKS ===")
np=sum(1 for c in checks if c[0]); nf=len(checks)-np
for ok,label,got,want in checks:
    if not ok: print(f"  FAIL {label}: got {got} want {want} diff {got-want}")
print(f"core checks: {np}/{len(checks)} pass, {nf} fail")
if verify_fail:
    print("VERIFY FAILURES:")
    for pg,s in verify_fail: print(f"  pdf {pg}: {s!r}")
    sys.exit(1)
print("core: all typed tokens verified verbatim")
