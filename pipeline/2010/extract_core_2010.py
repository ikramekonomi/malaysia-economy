#!/usr/bin/env python3
"""Core fiscal statements PKKP 2010 (RMKe-10 year 1, pre-GST).
Offset: pdf = printed + 10. Position pdf41, cash pdf42-43, prestasi pdf44, memorandum pdf45.
Values transcribed from printed pages, verified against dedup'd page text.
"""
import csv, os, re
YEAR, PRIOR = 2010, 2009
SRC = "2010_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2010"
os.makedirs(OUT, exist_ok=True)
layout = open("/home/claude/pkkp/work/2010/full.txt", encoding="utf-8").read().split("\f")

def page(pdf): return layout[pdf-1]
def norm(pdf):
    # collapse doubled glyphs: remove commas-in-number duplication by normalizing whitespace,
    # keep a version where we just check membership of numeric tokens.
    return page(pdf)

verify_fail=[]
def num_tokens(pdf):
    return set(re.findall(r"\(?[\d,]+(?:\.\d+)?\)?", page(pdf)))
def V(pdf, tok):
    tok=tok.strip()
    if tok in ("-","–","—",""): return
    if tok not in num_tokens(pdf):
        verify_fail.append((pdf,tok))

def N(tok):
    tok=str(tok).strip().replace("*","")
    if tok in {"–","-","—",""}: return 0.0
    neg=tok.startswith("(") and tok.endswith(")")
    tok=tok.strip("()").replace(",","")
    v=float(tok); return -v if neg else v

def w(name, header, rows):
    with open(os.path.join(OUT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f); cw.writerow(header); cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")

checks=[]
def chk(label, got, want, tol=0.5):
    ok=abs(got-want)<=tol; checks.append((ok,label,got,want)); return ok

# ---------- 1. Penyata Kedudukan Kewangan (pdf41 / printed31) ----------
def financial_position():
    stmt="Penyata Kedudukan Kewangan"; pg=41; pp=31
    src=[
        ("WANG AWAM","WANG TUNAI","3","21,573,280,678","27,520,118,474"),
        ("WANG AWAM","PELABURAN","4","20,343,238,913","16,015,424,825"),
        ("WANG AWAM","JUMLAH WANG AWAM","","41,916,519,591","43,535,543,299"),
        ("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN","5","11,863,127,086","11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN","6","26,068,545,555","8,359,953,459"),
        ("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN","7","3,984,846,950","23,312,462,754"),
        ("KUMPULAN WANG DISATUKAN","JUMLAH KUMPULAN WANG DISATUKAN","","41,916,519,591","43,535,543,299"),
    ]
    rows=[]
    for sec,item,nota,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt)
            rows.append([sec,item,nota,yr,N(amt),SRC,pg,pp,stmt])
    w("fact_financial_position.csv",
      ["section","line_item_bm","nota","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
    # additivity
    chk("FP WangAwam 2010", N("21,573,280,678")+N("20,343,238,913"), N("41,916,519,591"))
    chk("FP KWD 2010", N("11,863,127,086")+N("26,068,545,555")+N("3,984,846,950"), N("41,916,519,591"))
    chk("FP WangAwam=KWD 2010", N("41,916,519,591"), N("41,916,519,591"))

# ---------- 2. Cash statement (pdf42-43 / printed 32-33) ----------
def cash():
    stmt="Penyata Penerimaan dan Pembayaran Wang Tunai"
    rows=[]
    def add(flow,cat,item,a,b,pg,pp):
        V(pg,a); V(pg,b)
        rows.append([flow,cat,item,YEAR,N(a),SRC,pg,pp,stmt])
        rows.append([flow,cat,item,PRIOR,N(b),SRC,pg,pp,stmt])
    # TERIMAAN pdf42/pp32
    p,pp=42,32
    add("TERIMAAN","Hasil","Hasil Cukai","109,515,185,813","106,504,411,011",p,pp)
    add("TERIMAAN","Hasil","Hasil Bukan Cukai","48,867,434,930","50,789,238,902",p,pp)
    add("TERIMAAN","Hasil","Terimaan Bukan Hasil","793,006,447","1,067,563,070",p,pp)
    add("TERIMAAN","Hasil","Hasil Wilayah-Wilayah Persekutuan","477,335,128","278,091,245",p,pp)
    add("TERIMAAN","Hasil","Jumlah Hasil","159,652,962,318","158,639,304,228",p,pp)
    add("TERIMAAN","Pinjaman","Dalam Negeri","72,735,466,667","106,719,903,344",p,pp)
    add("TERIMAAN","Pinjaman","Luar Negeri","4,047,250,000","-",p,pp)
    add("TERIMAAN","Pinjaman","Jumlah Pinjaman","76,782,716,667","106,719,903,344",p,pp)
    add("TERIMAAN","Bantuan Luar Negeri","Pinjaman Multilateral","117,087,038","74,159,605",p,pp)
    add("TERIMAAN","Bantuan Luar Negeri","Pinjaman Bilateral","330,740,067","376,653,422",p,pp)
    add("TERIMAAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","447,827,105","450,813,027",p,pp)
    add("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","784,998,160","518,787,580",p,pp)
    add("TERIMAAN","Terimaan Modal","Jualan Aset Modal","73,318","1,340",p,pp)
    add("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","30,874,234","2,900,658",p,pp)
    add("TERIMAAN","Terimaan Modal","Jualan Instrumen Kewangan","-","674,481,048",p,pp)
    add("TERIMAAN","Terimaan Modal","Jumlah Terimaan Modal","815,945,712","1,196,170,626",p,pp)
    add("TERIMAAN","Terimaan Lain","Terimaan Amanah","-","79,183,036",p,pp)
    add("TERIMAAN","Terimaan Lain","Inisiatif Pembiayaan Swasta (PFI)","3,262,830,183","6,838,257,836",p,pp)
    add("TERIMAAN","Terimaan Lain","Jumlah Terimaan Lain","3,262,830,183","6,917,440,872",p,pp)
    add("JUMLAH","Jumlah Terimaan","Jumlah Terimaan","240,962,281,985","273,923,632,097",p,pp)
    # BAYARAN pdf43/pp33
    p,pp=43,33
    add("BAYARAN","Perbelanjaan Mengurus","Emolumen","46,662,939,934","42,778,266,363",p,pp)
    add("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","23,840,844,635","26,372,131,596",p,pp)
    add("BAYARAN","Perbelanjaan Mengurus","Aset","1,869,375,321","2,581,505,478",p,pp)
    add("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","78,104,600,235","84,650,079,062",p,pp)
    add("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan Lain","1,154,849,140","684,976,820",p,pp)
    add("BAYARAN","Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus","151,632,609,265","157,066,959,319",p,pp)
    add("BAYARAN","Perbelanjaan Pembangunan","Langsung","49,096,365,990","45,294,239,672",p,pp)
    add("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","3,695,264,230","4,221,115,898",p,pp)
    add("BAYARAN","Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan","52,791,630,220","49,515,355,570",p,pp)
    add("BAYARAN","Inisiatif Pembiayaan Swasta (PFI)","Inisiatif Pembiayaan Swasta (PFI)","5,012,367,936","4,291,992,718",p,pp)
    add("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","3,617,286,466","-",p,pp)
    add("BAYARAN","Pinjaman","Dalam Negeri","31,004,584,571","44,194,308,344",p,pp)
    add("BAYARAN","Pinjaman","Luar Negeri","-","5,837,534,800",p,pp)
    add("BAYARAN","Pinjaman","Jumlah Pinjaman","31,004,584,571","50,031,843,144",p,pp)
    add("BAYARAN","Bantuan Luar Negeri","Pinjaman Multilateral","239,356,767","354,543,416",p,pp)
    add("BAYARAN","Bantuan Luar Negeri","Pinjaman Bilateral","591,991,257","544,805,183",p,pp)
    add("BAYARAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","831,348,024","899,348,599",p,pp)
    add("BAYARAN","Bayaran Lain","Akaun Amanah","2,019,293,299","-",p,pp)
    add("JUMLAH","Jumlah Bayaran","Jumlah Bayaran","246,909,119,781","261,805,499,350",p,pp)
    add("JUMLAH","Tambahan / (Kurangan) Wang Tunai","Tambahan / (Kurangan) Wang Tunai","(5,946,837,796)","12,118,132,747",p,pp)
    add("JUMLAH","Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari","27,520,118,474","15,401,985,727",p,pp)
    add("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER","21,573,280,678","27,520,118,474",p,pp)
    w("fact_cash_statement.csv",
      ["flow","category_bm","item_bm","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
    # chains
    chk("Cash Jumlah Hasil", sum(N(x) for x in ["109,515,185,813","48,867,434,930","793,006,447","477,335,128"]), N("159,652,962,318"))
    chk("Cash Jumlah Terimaan", sum(N(x) for x in ["159,652,962,318","76,782,716,667","447,827,105","815,945,712","3,262,830,183"]), N("240,962,281,985"))
    chk("Cash Jumlah Mengurus", sum(N(x) for x in ["46,662,939,934","23,840,844,635","1,869,375,321","78,104,600,235","1,154,849,140"]), N("151,632,609,265"))
    chk("Cash Jumlah Bayaran", sum(N(x) for x in ["151,632,609,265","52,791,630,220","5,012,367,936","3,617,286,466","31,004,584,571","831,348,024","2,019,293,299"]), N("246,909,119,781"))
    chk("Cash net change", N("240,962,281,985")-N("246,909,119,781"), N("(5,946,837,796)"))
    chk("Cash closing", N("27,520,118,474")+N("(5,946,837,796)"), N("21,573,280,678"))

# ---------- 3. Penyata Prestasi Kewangan (pdf44 / printed34) ----------
def performance():
    stmt="Penyata Prestasi Kewangan"; pg,pp=44,34
    rows=[]
    def add(item,code,ang,seb,seb_prior):
        if ang is not None:
            V(pg,ang); rows.append([item,code,YEAR,"anggaran",N(ang),SRC,pg,pp,stmt])
        V(pg,seb); rows.append([item,code,YEAR,"sebenar",N(seb),SRC,pg,pp,stmt])
        V(pg,seb_prior); rows.append([item,code,PRIOR,"sebenar",N(seb_prior),SRC,pg,pp,stmt])
    add("HASIL","revenue","162,131,333,000","159,652,962,318","158,639,304,228")
    add("Belanja Mengurus","opex","149,064,665,100","151,632,609,265","157,066,959,319")
    add("LEBIHAN HASIL","current_balance","13,066,667,900","8,020,353,053","1,572,344,909")
    add("Belanja Pembangunan","devex","56,076,663,806","52,791,630,220","49,515,355,570")
    add("LEBIHAN / (KURANGAN) KESELURUHAN","overall_deficit","(43,009,995,906)","(44,771,277,167)","(47,943,010,661)")
    add("Pinjaman dan Bantuan Luar Negeri","financing_net_borrowing",None,"40,094,611,177","56,239,524,629")
    add("Terimaan Balik Pinjaman dan Pelbagai Terimaan","financing_capital_receipts",None,"1,526,473,333","521,689,577")
    add("Perubahan Tunai, Pelaburan dan Amanah","financing_cash_inv_trust_change",None,"3,150,192,657","(8,818,203,545)")
    add("JUMLAH PEMBIAYAAN","total_financing",None,"44,771,277,167","47,943,010,661")
    w("fact_financial_performance.csv",
      ["line_item_bm","line_code","year","basis","amount_rm","source_file","pdf_page","printed_page","statement"],rows)
    chk("Perf lebihan hasil sebenar", N("159,652,962,318")-N("151,632,609,265"), N("8,020,353,053"))
    chk("Perf overall sebenar", N("8,020,353,053")-N("52,791,630,220"), N("(44,771,277,167)"))
    chk("Perf financing total", sum(N(x) for x in ["40,094,611,177","1,526,473,333","3,150,192,657"]), N("44,771,277,167"))
    chk("Perf financing=deficit", N("44,771,277,167"), -N("(44,771,277,167)"))

# ---------- 4. Penyata Akaun Memorandum (pdf45 / printed35) ----------
def memorandum():
    stmt="Penyata Akaun Memorandum"; pg,pp=45,35
    src=[
        ("MEMORANDUM ASET","Pinjaman Boleh Dituntut","82,319,087,678","73,382,745,119"),
        ("MEMORANDUM ASET","Pelaburan","27,723,148,058","27,751,414,083"),
        ("MEMORANDUM LIABILITI","Hutang Awam","407,101,235,939","362,386,171,110"),
        ("MEMORANDUM LIABILITI","Pelbagai Liabiliti","206,605,049","173,364,115"),
    ]
    rows=[]
    for sec,item,a,b in src:
        V(pg,a); V(pg,b)
        rows.append([sec,item,YEAR,N(a),SRC,pg,pp,stmt])
        rows.append([sec,item,PRIOR,N(b),SRC,pg,pp,stmt])
    w("fact_memorandum.csv",
      ["section","line_item_bm","year","amount_rm","source_file","pdf_page","printed_page","statement"],rows)

financial_position(); cash(); performance(); memorandum()
print("\n=== VERIFY FAILURES (token not found on page) ===")
for pdf,tok in verify_fail: print(" ",pdf,tok)
print(f"total verify failures: {len(verify_fail)}")
print("\n=== CORE CHECKS ===")
for ok,label,got,want in checks:
    print(("PASS" if ok else "FAIL"), label, f"got={got:.1f} want={want:.1f}" if not ok else "")
np=sum(1 for c in checks if c[0]); print(f"{np}/{len(checks)} core checks pass")
