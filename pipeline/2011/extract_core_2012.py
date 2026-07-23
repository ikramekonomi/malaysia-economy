#!/usr/bin/env python3
"""Core fiscal tables for PKKP 2012 (RMKe-10 era, pre-GST).
2012 anchors: printed = pdf - 22. Position pdf47, cash pdf48-49, prestasi pdf50,
memorandum pdf51. Notes pdf52-64 are GARBLED in -layout; use per-page -raw.
Nota 5(a) revenue pdf54-55, Nota 5(b) opex-maksud pdf56-57, Nota 6 pdf57,
Nota 7 summary pdf58, Nota 9 debt pdf63, Pelbagai Liabiliti pdf64.
All amounts exact RM as printed. Typed tokens verified verbatim on source page.
"""
import csv, os, re, subprocess, sys

YEAR, PRIOR = 2012, 2011
SRC = "2012_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
PDF = "/home/claude/pkkp/work/2012/2012.pdf"
OUT = "/home/claude/pkkp/warehouse2012"
os.makedirs(OUT, exist_ok=True)
PP = lambda pdf: pdf - 22
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
NUM = r"[\d,]+(?:\.\d+)?"

layout = open("/home/claude/pkkp/work/2012/full.txt", encoding="utf-8").read().split("\f")
_rawcache = {}
def raw(pdf):
    if pdf not in _rawcache:
        t = subprocess.run(["pdftotext","-f",str(pdf),"-l",str(pdf),"-raw",PDF,"-"],
                           capture_output=True, text=True).stdout
        # dedup repeated render layers
        seen=set(); out=[]
        for ln in t.split("\n"):
            if ln not in seen:
                seen.add(ln); out.append(ln)
        _rawcache[pdf] = "\n".join(out)
    return _rawcache[pdf]

def page_text(pdf):
    t = layout[pdf-1]
    if 52 <= pdf <= 64:
        t = t + "\n" + raw(pdf)
    return t

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
    v=float(tok)
    return -v if neg else v

def w(name, header, rows):
    with open(os.path.join(OUT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f); cw.writerow(header); cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")

checks=[]
def chk(label, got, want, tol=0.5):
    ok = abs(got-want) <= tol
    checks.append((ok,label,got,want))
    return ok

# ---------------- 1. Penyata Kedudukan Kewangan (pdf47) ----------------
def financial_position():
    stmt="Penyata Kedudukan Kewangan"; pg=47
    src=[
        ("WANG AWAM","WANG TUNAI",3,"29,355,825,184","24,466,775,527"),
        ("WANG AWAM","PELABURAN",4,"24,049,136,708","22,843,463,212"),
        ("WANG AWAM","JUMLAH WANG AWAM","","53,404,961,892","47,310,238,739"),
        ("KUMPULAN WANG DISATUKAN","AKAUN HASIL DISATUKAN",5,"11,863,127,086","11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN","AKAUN PINJAMAN DISATUKAN",6,"28,904,795,292","38,909,479,613"),
        ("KUMPULAN WANG DISATUKAN","AKAUN AMANAH DISATUKAN",7,"12,637,039,514","(3,462,367,960)"),
        ("KUMPULAN WANG DISATUKAN","JUMLAH KUMPULAN WANG DISATUKAN","","53,404,961,892","47,310,238,739"),
    ]
    rows=[]
    for sec,item,nota,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([sec,item,nota,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_financial_position.csv",["section","line_item_bm","nota","year","amount_rm"]+PROV,rows)

# ---------------- 2. Cash statement (pdf48 terimaan / pdf49 bayaran) ----------------
def cash_statement():
    stmt="Penyata Penerimaan dan Pembayaran Wang Tunai"
    src=[
        ("TERIMAAN","Hasil","Hasil Cukai","151,643,090,263","134,884,834,173",48),
        ("TERIMAAN","Hasil","Hasil Bukan Cukai","50,909,327,554","49,423,045,556",48),
        ("TERIMAAN","Hasil","Terimaan Bukan Hasil","872,220,870","544,133,845",48),
        ("TERIMAAN","Hasil","Hasil Wilayah Persekutuan","483,424,598","566,906,169",48),
        ("TERIMAAN","Hasil","Jumlah Hasil","203,908,063,285","185,418,919,743",48),
        ("TERIMAAN","Pinjaman","Dalam Negeri","108,145,229,672","107,091,588,179",48),
        ("TERIMAAN","Pinjaman","Luar Negeri","–","5,960,800,000",48),
        ("TERIMAAN","Pinjaman","Jumlah Pinjaman","108,145,229,672","113,052,388,179",48),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Multilateral","91,016,051","33,518,605",48),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Bilateral","592,519,054","474,214,046",48),
        ("TERIMAAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","683,535,105","507,732,651",48),
        ("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","1,058,991,393","833,191,934",48),
        ("TERIMAAN","Terimaan Modal","Terimaan Balik Pendahuluan","29,400,000","–",48),
        ("TERIMAAN","Terimaan Modal","Jualan Aset Modal","89,869","91,433",48),
        ("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","1,519,509,321","133,387",48),
        ("TERIMAAN","Terimaan Modal","Jumlah Terimaan Modal","2,607,990,583","833,416,754",48),
        ("TERIMAAN","Terimaan Amanah","Inisiatif Pembiayaan Swasta (PFI)","2,136,635,290","2,385,876,399",48),
        ("TERIMAAN","Terimaan Amanah","Aktiviti Pembangunan Khas Pembiayaan Swasta","5,000,230,450","–",48),
        ("TERIMAAN","Terimaan Amanah","Pelbagai","–","–",48),
        ("TERIMAAN","Terimaan Amanah","Jumlah Terimaan Amanah","7,136,865,740","2,385,876,399",48),
        ("JUMLAH","Jumlah Terimaan","Jumlah Terimaan","322,481,684,385","302,198,333,726",48),
        ("BAYARAN","Perbelanjaan Mengurus","Emolumen","60,015,799,383","50,148,348,527",49),
        ("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","31,962,576,293","28,948,592,637",49),
        ("BAYARAN","Perbelanjaan Mengurus","Aset","1,769,606,790","2,665,292,177",49),
        ("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","104,451,633,629","92,603,818,793",49),
        ("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan-perbelanjaan Lain","1,466,359,006","1,137,741,551",49),
        ("BAYARAN","Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus","199,665,975,101","175,503,793,685",49),
        ("BAYARAN","Perbelanjaan Pembangunan","Langsung","44,978,124,405","44,917,440,271",49),
        ("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","1,954,329,401","1,498,922,156",49),
        ("BAYARAN","Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan","46,932,453,806","46,416,362,427",49),
        ("BAYARAN","Pinjaman","Dalam Negeri","61,403,631,379","59,430,119,121",49),
        ("BAYARAN","Pinjaman","Luar Negeri","–","5,215,700,000",49),
        ("BAYARAN","Pinjaman","Jumlah Pinjaman","61,403,631,379","64,645,819,121",49),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Multilateral","95,017,283","106,210,281",49),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Bilateral","590,443,637","583,837,554",49),
        ("BAYARAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","685,460,920","690,047,835",49),
        ("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","1,205,673,496","2,061,487,565",49),
        ("BAYARAN","Perbelanjaan Modal","Jumlah Perbelanjaan Modal","1,205,673,496","2,061,487,565",49),
        ("BAYARAN","Perbelanjaan Amanah","Inisiatif Pembiayaan Swasta (PFI)","2,352,521,909","3,584,962,054",49),
        ("BAYARAN","Perbelanjaan Amanah","Aktiviti Pembangunan Khas Pembiayaan Swasta","1,718,428,784","–",49),
        ("BAYARAN","Perbelanjaan Amanah","Pelbagai","3,628,489,333","6,179,379,456",49),
        ("BAYARAN","Perbelanjaan Amanah","Jumlah Perbelanjaan Amanah","7,699,440,026","9,764,341,510",49),
        ("JUMLAH","Jumlah Bayaran","Jumlah Bayaran","317,592,634,728","299,081,852,143",49),
        ("JUMLAH","Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai","4,889,049,657","3,116,481,583",49),
        ("JUMLAH","Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari","24,466,775,527","21,350,293,944",49),
        ("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER","29,355,825,184","24,466,775,527",49),
    ]
    rows=[]
    for flow,cat,item,a,b,pg in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([flow,cat,item,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_cash_statement.csv",["flow","category_bm","item_bm","year","amount_rm"]+PROV,rows)

# ---------------- 3. Penyata Prestasi Kewangan (pdf50) ----------------
def performance():
    stmt="Penyata Prestasi Kewangan"; pg=50
    src3=[("HASIL","revenue","207,246,482,000","207,912,754,669","185,418,919,743"),
          ("Belanja Mengurus","opex","198,737,824,368","205,537,081,525","182,593,788,338"),
          ("LEBIHAN HASIL","current_balance","8,508,657,632","2,375,673,144","2,825,131,405"),
          ("Belanja Pembangunan","devex","51,107,796,358","46,932,453,806","46,416,362,427"),
          ("KURANGAN KESELURUHAN","overall_deficit","(42,599,138,726)","(44,556,780,662)","(43,591,231,022)")]
    src2=[("Pinjaman dan Bantuan Luar Negeri","financing_net_borrowing","43,327,545,911","45,611,224,372"),
          ("Terimaan Balik Pinjaman dan Pelbagai Terimaan","financing_capital_receipts","2,634,972,286","1,082,196,256"),
          ("Perubahan Tunai, Pelaburan dan Amanah","financing_cash_inv_trust_change","(1,405,737,535)","(3,102,189,606)"),
          ("JUMLAH PEMBIAYAAN","total_financing","44,556,780,662","43,591,231,022")]
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

# ---------------- 4. Penyata Akaun Memorandum (pdf51) ----------------
def memorandum():
    stmt="Penyata Akaun Memorandum"; pg=51
    src=[("MEMORANDUM ASET","Pinjaman Boleh Dituntut","95,492,612,803","88,838,070,548"),
         ("MEMORANDUM ASET","Pelaburan","27,194,316,450","28,834,528,313"),
         ("MEMORANDUM LIABILITI","Hutang Awam","501,616,849,368","456,127,663,265"),
         ("MEMORANDUM LIABILITI","Pelbagai Liabiliti","275,621,222","241,513,526")]
    rows=[]
    for sec,item,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([sec,item,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_memorandum.csv",["section","line_item_bm","year","amount_rm"]+PROV,rows)

# ---------------- 5. Nota 9 debt (pdf63 + pdf64) ----------------
def debt():
    stmt="Nota 9 Memorandum Liabiliti"
    src=[
        ("Pinjaman Dalam Negeri","Bil Perbendaharaan","instrument","4,320,000,000","4,320,000,000",63),
        ("Pinjaman Dalam Negeri","Terbitan Pelaburan Kerajaan","instrument","143,500,000,000","110,000,000,000",63),
        ("Pinjaman Dalam Negeri","Sekuriti Kerajaan Malaysia","instrument","292,150,000,000","277,713,197,000",63),
        ("Pinjaman Dalam Negeri","Sukuk","instrument","2,398,801,500","6,991,618,300",63),
        ("Pinjaman Dalam Negeri","Dalam Negeri","subtotal","442,368,801,500","399,024,815,300",63),
        ("Kumpulan Wang Pinjaman Perumahan","Pembiayaan Kumpulan Wang Pinjaman Perumahan","instrument","42,400,000,000","39,000,000,000",63),
        ("Pinjaman Luar Negeri","Pinjaman Pasaran","instrument","10,052,575,000","10,402,925,000",63),
        ("JUMLAH","Jumlah Pinjaman","subtotal","494,821,376,500","448,427,740,300",63),
        ("Bantuan Luar Negeri","Pinjaman Multilateral","instrument","712,418,688","737,856,152",63),
        ("Bantuan Luar Negeri","Pinjaman Bilateral","instrument","6,083,054,180","6,962,066,813",63),
        ("JUMLAH","Jumlah Bantuan Luar Negeri","subtotal","6,795,472,868","7,699,922,965",63),
        ("JUMLAH","JUMLAH HUTANG AWAM","total","501,616,849,368","456,127,663,265",63),
        ("Pelbagai Liabiliti","PELBAGAI LIABILITI","misc_total","275,621,222","241,513,526",64),
    ]
    rows=[]
    for grp,item,kind,a,b,pg in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([grp,item,kind,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_debt.csv",["group_bm","item_bm","kind","year","amount_rm"]+PROV,rows)

# ---------------- 6. Nota 7 summary matrix (pdf58) -> fact_trust_accounts ----------------
def trust():
    stmt="Nota 7 Akaun Amanah Disatukan"; pg=58
    src=[
        ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pembangunan","(55,235,001,113)","46,945,799,332","58,356,221,189","(43,824,579,256)"),
        ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pinjaman Perumahan","1,908,324,534","10,961,105,335","10,568,301,237","1,515,520,436"),
        ("KUMPULAN WANG AMANAH KERAJAAN","Pelbagai Kumpulan Wang Amanah Kerajaan","34,554,927,065","295,201,452,952","296,398,507,887","35,751,982,000"),
        ("","KUMPULAN WANG AMANAH KERAJAAN","(18,771,749,514)","353,108,357,619","365,323,030,313","(6,557,076,820)"),
        ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Khas","617,929,977","172,923,278","192,785,973","637,792,672"),
        ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Am","5,701,912,589","8,655,946,515","12,055,878,776","9,101,844,850"),
        ("","KUMPULAN WANG AMANAH AWAM","6,319,842,566","8,828,869,793","12,248,664,749","9,739,637,522"),
        ("AKAUN DEPOSIT","Deposit Am","8,690,055,757","2,096,191,153","2,561,346,007","9,155,210,611"),
        ("AKAUN DEPOSIT","Deposit Pelarasan","299,483,231","1,608,491,193","1,608,276,163","299,268,201"),
        ("","AKAUN DEPOSIT","8,989,538,988","3,704,682,346","4,169,622,170","9,454,478,812"),
        ("JUMLAH","AKAUN AMANAH DISATUKAN","(3,462,367,960)","365,641,909,758","381,741,317,232","12,637,039,514"),
    ]
    rows=[]
    for parent,acct,ba,dr,cr,bk in src:
        for t in (ba,dr,cr,bk): V(pg,t)
        rows.append([parent,acct,YEAR,N(ba),N(dr),N(cr),N(bk),SRC,pg,PP(pg),stmt])
    w("fact_trust_accounts.csv",["parent_group_bm","account_bm","year","baki_awal_rm","debit_rm","kredit_rm","baki_akhir_rm"]+PROV,rows)

# ---------------- 7. Nota 5(a) revenue (pdf54-55) parsed ----------------
REV_L1=["HASIL CUKAI","HASIL BUKAN CUKAI","TERIMAAN BUKAN HASIL","HASIL WILAYAH PERSEKUTUAN"]
L1J={"Jumlah Hasil Cukai":"HASIL CUKAI","Jumlah Hasil Bukan Cukai":"HASIL BUKAN CUKAI",
     "Jumlah Terimaan Bukan Hasil":"TERIMAAN BUKAN HASIL","Jumlah Hasil Wilayah Persekutuan":"HASIL WILAYAH PERSEKUTUAN"}
def revenue():
    stmt="Nota 5(a) Hasil Mengikut Penjenisan"
    rows=[]; l1=None; started=False
    numline=re.compile(rf"^(.*?)\s+((?:\*?\(?{NUM}\)?|[–—-])\s+(?:\*?\(?{NUM}\)?|[–—-])\s+(?:\*?\(?{NUM}\)?|[–—-])\s+[\d.]+\s+(?:\*?\(?{NUM}\)?|[–—-])\s+[\d.]+)\s*$")
    for pdfp in (54,55):
        for ln in raw(pdfp).split("\n"):
            s=ln.strip()
            if not s: continue
            if s=="HASIL CUKAI" and pdfp==54: started=True
            if not started: continue
            if s.startswith("(b) Perbelanjaan"): started=False; break
            if s in REV_L1: l1=s; continue
            m=numline.match(s)
            if not m:
                # wrapped continuation: short phrase, few words, appended to last row label
                if (rows and 0<len(s)<40 and len(s.split())<=4 and not s.endswith(".")
                        and not s.startswith(("Jumlah","JUMLAH")) and s not in REV_L1
                        and not re.search(r"\d",s) and s not in ("RM","Anggaran","Asal","Disemak","Sebenar","%")):
                    rows[-1][3]=rows[-1][3]+" "+s
                continue
            label=m.group(1).strip()
            toks=re.findall(rf"\*?\(?{NUM}\)?|[–—-]", m.group(2))
            if len(toks)!=6: continue
            asal,disemak,seb,pct,pri,pctp=toks
            if label=="JUMLAH HASIL":
                rows.append([0,None,None,"HASIL",YEAR,N(asal),N(disemak),N(seb),float(pct),N(pri),float(pctp),SRC,pdfp,PP(pdfp),stmt])
            elif label in L1J:
                cat=L1J[label]
                rows.append([1,cat,None,cat,YEAR,N(asal),N(disemak),N(seb),float(pct),N(pri),float(pctp),SRC,pdfp,PP(pdfp),stmt])
            else:
                rows.append([3,l1,None,label,YEAR,N(asal),N(disemak),N(seb),float(pct),N(pri),float(pctp),SRC,pdfp,PP(pdfp),stmt])
    w("fact_revenue.csv",["level","category_l1_bm","category_l2_bm","item_bm","year","anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm","pct_anggaran","sebenar_prior_rm","pct_anggaran_prior"]+PROV,rows)
    # internal additivity: items sum to L1 subtotal; L1 subtotals sum to grand
    for col in (5,6,7):  # asal,disemak,sebenar
        for cat in REV_L1:
            items=[r for r in rows if r[0]==3 and r[1]==cat]
            sub=[r for r in rows if r[0]==1 and r[1]==cat]
            if items and sub:
                chk(f"revenue {cat} sum(items)==Jumlah col{col}", sum(r[col] for r in items), sub[0][col])
        grand=[r for r in rows if r[0]==0]
        subs=[r for r in rows if r[0]==1]
        if grand and subs:
            chk(f"revenue JUMLAH HASIL==sum(L1) col{col}", sum(r[col] for r in subs), grand[0][col])
    return rows

# ---------------- 8. Nota 5(b) opex maksud (pdf56-57) parsed ----------------
def opex_maksud():
    stmt="Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows=[]
    pat=re.compile(rf"^([TB])\.\s*(\d{{2,3}})\s+(.*?)\s+({NUM})\s+({NUM})\s+(\*{{0,3}}{NUM})\s+([\d.]+)\s*$")
    stop=False
    for pdfp in (56,57):
        if stop: break
        for ln in raw(pdfp).split("\n"):
            s=ln.strip()
            if not s: continue
            # hard stop once the maksud table ends and Nota 6 (Akaun Pinjaman Disatukan) begins
            if re.match(r"^6\.\s*AKAUN", s) or "AKAUN PINJAMAN DISATUKAN" in s or s.startswith("Penyata Akaun Pinjaman"):
                stop=True; break
            m=pat.match(s)
            if not m:
                # wrapped maksud name continuation
                if (rows and 0<len(s)<50 and not re.search(r"\d",s) and s[0:1].isalpha()
                        and not s.startswith(("Jumlah","JUMLAH","PERBELANJAAN","NOTA","Anggaran","Penyata","bagi"))):
                    rows[-1][2]=rows[-1][2]+" "+s
                continue
            kind,code,name,asal,dip,seb,pct=m.groups()
            fn="*" in seb
            rows.append([f"{kind}.{code.zfill(2)}","Tanggungan" if kind=="T" else "Bekalan",name.strip(),
                         YEAR,N(asal),N(dip),N(seb),float(pct),fn,SRC,pdfp,PP(pdfp),stmt])
    w("fact_opex_maksud.csv",["maksud_code","jenis_bm","maksud_name_bm","year","anggaran_asal_rm","anggaran_dipinda_rm","sebenar_rm","pct_anggaran","has_footnote"]+PROV,rows)
    return rows

financial_position(); cash_statement(); performance(); memorandum()
debt(); trust()
rev=revenue(); om=opex_maksud()

# cross checks vs printed totals
tang=[r for r in om if r[0].startswith("T.")]; bek=[r for r in om if r[0].startswith("B.")]
chk("opex maksud count==50", len(om), 50)
chk("opex T count==14", len(tang), 14)
chk("opex B count==36", len(bek), 36)
# Nota 5(b) maksud breakdown is SELEPAS pindahan (balances Hasil) = 207,912,754,669;
# sebelum pindahan = that - 2,375,673,144 = 205,537,081,525 (Penyata Prestasi Belanja Mengurus).
chk("opex maksud sum sebenar(selepas pindahan)==207,912,754,669", sum(r[6] for r in om), 207912754669, tol=1.0)
chk("opex sebelum pindahan==205,537,081,525", sum(r[6] for r in om)-2375673144, 205537081525, tol=1.0)
chk("opex sum asal == Jumlah Tanggungan+Bekalan asal(181,584,000,000)?", sum(r[4] for r in om), 35288886200+146295113800, tol=2.0)
revgrand=[r for r in rev if r[0]==0]
if revgrand: chk("revenue grand sebenar==207,912,754,669", revgrand[0][7], 207912754669)

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
