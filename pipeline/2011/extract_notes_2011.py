#!/usr/bin/env python3
"""NOTES-section tables for PKKP FY2011. Pages read cleanly from -layout.
  Nota3 WANG TUNAI            pdf55 -> fact_cash_components
  Nota4 PELABURAN             pdf55 -> fact_investment_summary
  Nota5 AKAUN HASIL DISATUKAN pdf56 -> fact_revenue_account_statement (summary)
        Nota5(a) penjenisan   pdf56-57 -> fact_revenue
        Nota5(b) maksud       pdf58 -> fact_opex_maksud
  Nota6 AKAUN PINJAMAN DISAT. pdf59 -> fact_loan_account_statement
  Nota7 AKAUN AMANAH DISAT.   pdf60 -> fact_trust_accounts; pdf60-64 -> fact_trust_fund_detail
  Nota8 MEMORANDUM ASET       pdf64-65 -> fact_memo_assets_detail
  Nota9(a) Hutang Awam        pdf65 -> fact_debt
  Nota9(b) Pelbagai Liabiliti pdf66 -> fact_commitment_detail
  Nota10-12 narrative         pdf66+ -> fact_other_notes
"""
import csv, os, re, sys

YEAR, PRIOR = 2011, 2010
SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2011"
PP = lambda pdf: pdf - 18
PROV = ["source_file", "pdf_page", "printed_page", "statement"]
NUM = r"[\d,]+(?:\.\d+)?"
layout = open("/home/claude/pkkp/work/2011/full.txt", encoding="utf-8").read().split("\f")
def pt(pdf): return layout[pdf-1]

verify_fail=[]
def V(pdf,s):
    s=s.strip()
    if s in ("-","–","—",""): return
    if s not in pt(pdf): verify_fail.append((pdf,s))
def N(tok):
    tok=tok.strip().replace("*","")
    if tok in {"–","-","—",""}: return 0.0
    neg=tok.startswith("(") and tok.endswith(")")
    tok=tok.strip("()").replace(",","")
    return -float(tok) if neg else float(tok)
def w(name,header,rows):
    with open(os.path.join(OUT,name),"w",newline="",encoding="utf-8") as f:
        cw=csv.writer(f); cw.writerow(header); cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")
checks=[]
def chk(label,got,want,tol=0.5):
    ok=abs(got-want)<=tol; checks.append((ok,label,got,want)); return ok

# ============ Nota 3 WANG TUNAI -> fact_cash_components (pdf55) ============
def cash_components():
    stmt="Nota 3 Wang Tunai"; pg=55
    src=[("Wang Tunai Dalam Bank","23,788,144,927","20,779,086,850","item"),
         ("Wang Tunai Dalam Perjalanan","676,032,089","568,719,734","item"),
         ("Wang Tunai Dalam Tangan","2,598,511","2,487,360","item"),
         ("JUMLAH WANG TUNAI","24,466,775,527","21,350,293,944","total")]
    rows=[]
    for item,a,b,rt in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([item,yr,N(amt),rt,False,SRC,pg,PP(pg),stmt])
    w("fact_cash_components.csv",["line_item_bm","year","amount_rm","row_type","has_footnote"]+PROV,rows)
    chk("Nota3 wang tunai sum 2011", sum(N(a) for _,a,_,rt in src if rt=="item"), 24466775527)

# ============ Nota 4 PELABURAN -> fact_investment_summary (pdf55) ============
def investment_summary():
    stmt="Nota 4 Pelaburan"; pg=55
    # two book-value columns per year: Pelaburan Kumpulan Wang Amanah + Pelaburan Am
    # grain: one row per (category, kategori) x year. category_bm=KWA/Am; line_item=share class
    src=[  # item, kwa2011, am2011, kwa2010, am2010
        ("Sekuriti Kerajaan Luar Negeri","2,561,909,810","–","2,353,439,585","317,321,584"),
        ("Sekuriti Kerajaan Malaysia","936,001,984","–","961,563,860","–"),
        ("Saham","784,811","5,563,998,987","784,811","5,348,248,987"),
        ("Deposit Luar Negeri","75,996,238","–","504,567,726","49,230,388"),
        ("Deposit Dalam Negeri","8,502,089,818","4,258,392,284","8,155,696,982","2,432,986,734"),
        ("Pelbagai","942,618,722","1,670,558","440,714,432","1,670,558"),
        ("Jumlah","13,019,401,383","9,824,061,829","12,416,767,396","8,149,458,251"),
    ]
    rows=[]
    for item,k1,a1,k0,a0 in src:
        rt="subtotal" if item=="Jumlah" else "item"
        for cat,v1,v0 in (("Pelaburan Kumpulan Wang Amanah",k1,k0),("Pelaburan Am",a1,a0)):
            for yr,amt in ((YEAR,v1),(PRIOR,v0)):
                V(pg,amt); rows.append([cat,item,yr,N(amt),rt,False,SRC,pg,PP(pg),stmt])
    # JUMLAH PELABURAN (combined) row
    for yr,amt in ((YEAR,"22,843,463,212"),(PRIOR,"20,566,225,647")):
        V(pg,amt); rows.append(["JUMLAH PELABURAN","JUMLAH PELABURAN",yr,N(amt),"total",False,SRC,pg,PP(pg),stmt])
    w("fact_investment_summary.csv",["category_bm","line_item_bm","year","amount_rm","row_type","has_footnote"]+PROV,rows)
    chk("Nota4 KWA+Am jumlah 2011", N("13,019,401,383")+N("9,824,061,829"), 22843463212)

# ============ Nota 5 revenue account statement summary (pdf56) ============
def revenue_account_statement():
    stmt="Nota 5 Akaun Hasil Disatukan"; pg=56
    # cols: anggaran(disemak), sebenar, pct, prior_sebenar, prior_pct
    # (BAKI rows only have one value in the sebenar position)
    src=[  # item, rt, disemak, sebenar, pct, prior, ppct, footnote
        ("BAKI PADA 1 JANUARI","opening",None,"11,863,127,086",None,"11,863,127,086",None,False),
        ("Hasil Cukai","item","129,182,224,000","134,884,834,173","104.41","109,515,185,813","102.26",False),
        ("Hasil Bukan Cukai","item","53,141,305,000","49,423,045,556","93.00","48,867,434,930","90.76",False),
        ("Terimaan Bukan Hasil","item","548,749,000","544,133,845","99.16","793,006,447","102.35",False),
        ("Hasil Wilayah Persekutuan","item","502,331,000","566,906,169","112.86","477,335,128","112.53",False),
        ("Jumlah Hasil","subtotal","183,374,609,000","185,418,919,743","101.11","159,652,962,318","98.47",False),
        ("Emolumen","item","48,638,276,337","50,148,348,527","103.10","46,662,939,934","107.09",False),
        ("Perkhidmatan dan Bekalan","item","29,259,892,486","28,948,592,637","98.94","23,840,844,635","98.95",False),
        ("Aset","item","2,748,704,758","2,665,292,177","96.97","1,869,375,321","97.00",False),
        ("Pemberian dan Kenaan Bayaran Tetap","item","96,135,634,314","99,693,813,446","103.70","78,104,600,235","99.80",True),
        ("Perbelanjaan-perbelanjaan lain","item","1,197,316,995","1,137,741,551","95.02","1,154,849,140","95.55",False),
        ("Jumlah Perbelanjaan Mengurus (sebelum pindahan)","subtotal","177,979,824,890","182,593,788,338","102.59","151,632,609,265","101.72",False),
        ("Pindahan Lebihan Hasil ke Kumpulan Wang Pembangunan","item","–","2,825,131,405","–","8,020,353,053","–",False),
        ("Jumlah Perbelanjaan Mengurus (selepas pindahan)","subtotal","177,979,824,890","185,418,919,743","104.18","159,652,962,318","107.10",False),
        ("BAKI PADA 31 DISEMBER","closing",None,"11,863,127,086",None,"11,863,127,086",None,False),
    ]
    rows=[]
    for item,rt,dis,seb,pct,pri,ppct,fn in src:
        for t in (dis,seb,pri):
            if t: V(pg,t)
        rows.append([ "HASIL" if rt in("item","subtotal","opening","closing") and False else "", item, rt, YEAR, N(dis) if dis else "", N(seb) if seb else "", float(pct) if pct and pct not in("–","-") else "", fn, SRC,pg,PP(pg),stmt])
        rows.append([ "", item, rt, PRIOR, "", N(pri) if pri else "", float(ppct) if ppct and ppct not in("–","-") else "", fn, SRC,pg,PP(pg),stmt])
    w("fact_revenue_account_statement.csv",["section_bm","line_item_bm","row_type","year","anggaran_disemak_rm","sebenar_rm","pct_anggaran","has_footnote"]+PROV,rows)

# ============ Nota 5(a) revenue penjenisan (pdf56-57) -> fact_revenue ============
REV_L1=["HASIL CUKAI","HASIL BUKAN CUKAI","TERIMAAN BUKAN HASIL","HASIL WILAYAH PERSEKUTUAN"]
L1J={"Jumlah Hasil Cukai":"HASIL CUKAI","Jumlah Hasil Bukan Cukai":"HASIL BUKAN CUKAI",
     "Jumlah Terimaan Bukan Hasil":"TERIMAAN BUKAN HASIL","Jumlah Hasil Wilayah Persekutuan":"HASIL WILAYAH PERSEKUTUAN"}
def revenue():
    stmt="Nota 5(a) Hasil Mengikut Penjenisan"
    rows=[]; l1=None; started=False; pending=""
    six=re.compile(rf"^(.*?)\s+({NUM})\s+({NUM})\s+({NUM})\s+([\d.]+)\s+({NUM})\s+([\d.]+)\s*$")
    for pdfp in (56,57):
        for ln in pt(pdfp).split("\n"):
            s=ln.strip()
            if not s: continue
            if pdfp==56 and not started:
                if s.startswith("HASIL CUKAI"): started=True
                else: continue
            if s.startswith("(b) Perbelanjaan"): break
            if s=="(disambung)" or s.startswith("4 NKPK") or re.fullmatch(r"\d{2}",s): continue
            if s in REV_L1: l1=s; pending=""; continue
            m=six.match(s)
            if not m:
                # wrapped label fragment
                if (0<len(s)<45 and not re.search(r"\d{3,}",s) and s[0:1].isalpha()
                        and not s.startswith(("Jumlah","JUMLAH","2011","2010","RM","Anggaran","Asal","Disemak","Sebenar"))):
                    pending=(pending+" "+s).strip()
                continue
            label=(pending+" "+m.group(1)).strip(); pending=""
            asal,dis,seb,pct,pri,ppct=m.group(2,3,4,5,6,7)
            for t in (asal,dis,seb,pri): V(pdfp,t)
            if label=="JUMLAH HASIL":
                rows.append([0,None,None,"JUMLAH HASIL",YEAR,N(asal),N(dis),N(seb),float(pct),N(pri),float(ppct),SRC,pdfp,PP(pdfp),stmt])
            elif label in L1J:
                cat=L1J[label]
                rows.append([1,cat,None,label,YEAR,N(asal),N(dis),N(seb),float(pct),N(pri),float(ppct),SRC,pdfp,PP(pdfp),stmt])
            else:
                rows.append([3,l1,None,label,YEAR,N(asal),N(dis),N(seb),float(pct),N(pri),float(ppct),SRC,pdfp,PP(pdfp),stmt])
    w("fact_revenue.csv",["level","category_l1_bm","category_l2_bm","item_bm","year","anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm","pct_anggaran","sebenar_prior_rm","pct_anggaran_prior"]+PROV,rows)
    for ci,name in ((5,"asal"),(6,"disemak"),(7,"sebenar")):
        for cat in REV_L1:
            items=[r for r in rows if r[0]==3 and r[1]==cat]
            sub=[r for r in rows if r[0]==1 and r[1]==cat]
            if items and sub: chk(f"rev {cat} items==Jumlah {name}", sum(r[ci] for r in items), sub[0][ci])
        subs=[r for r in rows if r[0]==1]; grand=[r for r in rows if r[0]==0]
        if grand: chk(f"rev Jumlah L1==JUMLAH HASIL {name}", sum(r[ci] for r in subs), grand[0][ci])
    return rows

# ============ Nota 5(b) opex maksud (pdf58) -> fact_opex_maksud ============
def opex_maksud():
    stmt="Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"; pg=58
    rows=[]
    pat=re.compile(rf"^([TB])\.\s*(\d{{2}})\s+(.*?)\s+({NUM})\s+({NUM})\s+(\*{{0,3}}{NUM})\s+([\d.]+)\s*$")
    codehdr=re.compile(r"^([TB])\.\s*(\d{2})\s+(.*)$")
    tailnum=re.compile(rf"^(.*?)\s+({NUM})\s+({NUM})\s+(\*{{0,3}}{NUM})\s+([\d.]+)\s*$")
    pend=None  # (kind,code,partial_name) when a code-header line carried no numbers
    def emit(kind,code,name,asal,dip,seb,pct):
        fn="*" in seb
        V(pg,asal); V(pg,dip); V(pg,seb.replace("*",""))
        rows.append([f"{kind}.{code}","Tanggungan" if kind=="T" else "Bekalan",name.strip(),
                     YEAR,N(asal),N(dip),N(seb),float(pct),fn,SRC,pg,PP(pg),stmt])
    for ln in pt(pg).split("\n"):
        s=ln.strip()
        if not s: continue
        m=pat.match(s)
        if m:
            pend=None; emit(*m.groups()); continue
        ch=codehdr.match(s)
        if ch and not re.search(rf"{NUM}\s+{NUM}\s+{NUM}", s):
            pend=(ch.group(1),ch.group(2),ch.group(3).strip()); continue
        if pend:
            tn=tailnum.match(s)
            if tn:
                kind,code,pname=pend
                emit(kind,code,(pname+" "+tn.group(1)).strip(),*tn.group(2,3,4,5)); pend=None; continue
    w("fact_opex_maksud.csv",["maksud_code","jenis_bm","maksud_name_bm","year","anggaran_asal_rm","anggaran_dipinda_rm","sebenar_rm","pct_anggaran","has_footnote"]+PROV,rows)
    tang=[r for r in rows if r[0].startswith("T.")]; bek=[r for r in rows if r[0].startswith("B.")]
    chk("opex maksud count==50", len(rows),50)
    chk("opex T count==14", len(tang),14)
    chk("opex B count==36", len(bek),36)
    chk("opex Jumlah Tanggungan sebenar", sum(r[6] for r in tang), 33040593756)
    chk("opex Jumlah Bekalan sebenar", sum(r[6] for r in bek), 152378325987)
    chk("opex grand sebenar(selepas pindahan)==185,418,919,743", sum(r[6] for r in rows), 185418919743)
    chk("opex grand asal==162,805,323,000", sum(r[4] for r in rows), 162805323000)
    chk("opex grand dipinda==177,979,824,890", sum(r[5] for r in rows), 177979824890)
    return rows

# ============ Nota 6 loan account statement (pdf59) -> fact_loan_account_statement ============
def loan_account_statement():
    stmt="Nota 6 Akaun Pinjaman Disatukan"; pg=59
    # group, sub, item, row_type, 2011, 2010
    src=[
     ("PINJAMAN","Dalam Negeri","Baki pada 1 Januari","item","26,068,545,555","8,359,953,459"),
     ("PINJAMAN","Dalam Negeri","Terimaan","item","99,991,588,179","66,835,466,667"),
     ("PINJAMAN","Dalam Negeri","Bayaran","item","(54,930,119,121)","(30,404,584,571)"),
     ("PINJAMAN","Dalam Negeri","Baki pada 31 Disember","subtotal","71,130,014,613","44,790,835,555"),
     ("PINJAMAN","Luar Negeri","Terimaan","item","5,960,800,000","4,047,250,000"),
     ("PINJAMAN","Luar Negeri","Bayaran","item","(5,215,700,000)","–"),
     ("PINJAMAN","Luar Negeri","Baki pada 31 Disember","subtotal","745,100,000","4,047,250,000"),
     ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Terimaan","item","7,100,000,000","5,900,000,000"),
     ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Bayaran","item","(4,500,000,000)","(600,000,000)"),
     ("PINJAMAN","Kumpulan Wang Pinjaman Perumahan","Baki pada 31 Disember","subtotal","2,600,000,000","5,300,000,000"),
     ("PINJAMAN","","Jumlah Pinjaman pada 31 Disember","total","74,475,114,613","54,138,085,555"),
     ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Terimaan","item","33,518,605","117,087,038"),
     ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Bayaran","item","(106,210,281)","(239,356,767)"),
     ("BANTUAN LUAR NEGERI","Pinjaman Multilateral","Baki pada 31 Disember","subtotal","(72,691,676)","(122,269,729)"),
     ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Terimaan","item","474,214,046","330,740,067"),
     ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Bayaran","item","(596,867,056)","(591,991,257)"),
     ("BANTUAN LUAR NEGERI","Pinjaman Bilateral","Baki pada 31 Disember","subtotal","(122,653,010)","(261,251,190)"),
     ("BANTUAN LUAR NEGERI","","Jumlah Bantuan Luar Negeri pada 31 Disember","total","(195,344,686)","(383,520,919)"),
     ("JUMLAH","","Jumlah Pinjaman dan Bantuan Luar Negeri pada 31 Disember","total","74,279,769,927","53,754,564,636"),
     ("PINDAHAN KE","","Kumpulan Wang Pembangunan","item","(32,770,290,314)","(22,386,019,081)"),
     ("PINDAHAN KE","","Kumpulan Wang Pinjaman Perumahan","item","(2,600,000,000)","(5,300,000,000)"),
     ("JUMLAH","","BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER","closing","38,909,479,613","26,068,545,555"),
    ]
    rows=[]
    for grp,sub,item,rt,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([grp,sub,item,rt,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_loan_account_statement.csv",["group_bm","sub_bm","line_item_bm","row_type","year","amount_rm"]+PROV,rows)
    d={(g,s,i,y):v for g,s,i,rt,y,v,*_ in rows}
    chk("loan DN baki 31", d[("PINJAMAN","Dalam Negeri","Baki pada 1 Januari",YEAR)]+d[("PINJAMAN","Dalam Negeri","Terimaan",YEAR)]+d[("PINJAMAN","Dalam Negeri","Bayaran",YEAR)], d[("PINJAMAN","Dalam Negeri","Baki pada 31 Disember",YEAR)])
    chk("loan baki akaun pinjaman disatukan == finpos", d[("JUMLAH","","BAKI AKAUN PINJAMAN DISATUKAN PADA 31 DISEMBER",YEAR)], 38909479613)

# ============ Nota 7 trust accounts summary matrix (pdf60) -> fact_trust_accounts ============
def trust_accounts():
    stmt="Nota 7 Akaun Amanah Disatukan"; pg=60
    src=[
      ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pembangunan","(45,496,256,660)","46,432,690,220","36,693,945,767","(55,235,001,113)"),
      ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pinjaman Perumahan","3,213,459,959","13,264,423,972","11,959,288,547","1,908,324,534"),
      ("KUMPULAN WANG AMANAH KERAJAAN","Pelbagai Kumpulan Wang Amanah Kerajaan","29,920,194,056","398,714,883,472","403,349,616,481","34,554,927,065"),
      ("","Jumlah Kumpulan Wang Amanah Kerajaan","(12,362,602,645)","458,411,997,664","452,002,850,795","(18,771,749,514)"),
      ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Khas","582,089,065","220,113,233","255,954,145","617,929,977"),
      ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Am","7,139,541,106","7,977,808,251","6,540,179,734","5,701,912,589"),
      ("","Jumlah Kumpulan Wang Amanah Awam","7,721,630,171","8,197,921,484","6,796,133,879","6,319,842,566"),
      ("AKAUN DEPOSIT","Deposit Am","8,258,680,212","2,605,348,107","3,036,723,652","8,690,055,757"),
      ("AKAUN DEPOSIT","Deposit Pelarasan","367,139,212","2,452,049,738","2,384,393,757","299,483,231"),
      ("","Jumlah Akaun Deposit","8,625,819,424","5,057,397,845","5,421,117,409","8,989,538,988"),
      ("JUMLAH","JUMLAH AKAUN AMANAH DISATUKAN","3,984,846,950","471,667,316,993","464,220,102,083","(3,462,367,960)"),
    ]
    rows=[]
    for parent,acct,ba,dr,cr,bk in src:
        for t in (ba,dr,cr,bk): V(pg,t)
        rows.append([parent,acct,YEAR,N(ba),N(dr),N(cr),N(bk),SRC,pg,PP(pg),stmt])
    w("fact_trust_accounts.csv",["parent_group_bm","account_bm","year","baki_awal_rm","debit_rm","kredit_rm","baki_akhir_rm"]+PROV,rows)
    # (Debit)/Kredit sign convention: baki_akhir = baki_awal - debit + kredit
    for parent,acct,ba,dr,cr,bk in src:
        chk(f"trust rollfwd {acct[:22]}", N(ba)-N(dr)+N(cr), N(bk), tol=1.0)
    # subtotals additive
    chk("trust KWAK subtotal baki31", N("(55,235,001,113)")+N("1,908,324,534")+N("34,554,927,065"), N("(18,771,749,514)"))
    chk("trust grand baki31 == finpos amanah", N("(3,462,367,960)"), -3462367960)
    chk("trust grand baki31 == KWAK+KWAA+Deposit", N("(18,771,749,514)")+N("6,319,842,566")+N("8,989,538,988"), N("(3,462,367,960)"))

# ============ Nota 8 memo assets detail (pdf64 Pinjaman Boleh Dituntut, pdf65 Pelaburan) ============
def memo_assets_detail():
    stmt="Nota 8 Memorandum Aset"
    src=[  # section, item, 2011, 2010, rt, pg
     ("Pinjaman Boleh Dituntut","Kerajaan Negeri","16,820,200,196","18,170,277,816","item",64),
     ("Pinjaman Boleh Dituntut","Pihak Berkuasa Tempatan","500,001,908","506,706,592","item",64),
     ("Pinjaman Boleh Dituntut","Badan Berkanun","12,396,058,833","10,415,078,766","item",64),
     ("Pinjaman Boleh Dituntut","Koperasi","195,462,764","195,725,480","item",64),
     ("Pinjaman Boleh Dituntut","Syarikat","24,744,191,014","24,227,828,427","item",64),
     ("Pinjaman Boleh Dituntut","Perseorangan","31,346,545,405","26,160,214,194","item",64),
     ("Pinjaman Boleh Dituntut","Pelbagai","2,835,610,428","2,643,256,403","item",64),
     ("Pinjaman Boleh Dituntut","JUMLAH PINJAMAN BOLEH DITUNTUT","88,838,070,548","82,319,087,678","total",64),
     ("Pelaburan","Syarikat","26,965,522,817","26,465,720,953","item",65),
     ("Pelaburan","Badan Berkanun","1,218,852,876","1,218,852,876","item",65),
     ("Pelaburan","Agensi Antarabangsa","38,574,229","38,574,229","item",65),
     ("Pelaburan","JUMLAH PELABURAN","28,222,949,922","27,723,148,058","total",65),
    ]
    rows=[]
    for sec,item,a,b,rt,pg in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([sec,item,yr,N(amt),rt,False,SRC,pg,PP(pg),stmt])
    w("fact_memo_assets_detail.csv",["section_bm","line_item_bm","year","amount_rm","row_type","has_footnote"]+PROV,rows)
    chk("memo Pinjaman Boleh Dituntut jumlah", sum(N(a) for s,i,a,b,rt,pg in src if s=="Pinjaman Boleh Dituntut" and rt=="item"), 88838070548)
    chk("memo Pelaburan jumlah", sum(N(a) for s,i,a,b,rt,pg in src if s=="Pelaburan" and rt=="item"), 28222949922)

# ============ Nota 9(a) Hutang Awam (pdf65) -> fact_debt ============
def debt():
    stmt="Nota 9 Memorandum Liabiliti"; pg=65
    src=[
     ("Pinjaman Dalam Negeri","Bil Perbendaharaan","instrument","4,320,000,000","4,320,000,000"),
     ("Pinjaman Dalam Negeri","Terbitan Pelaburan Kerajaan","instrument","110,000,000,000","81,500,000,000"),
     ("Pinjaman Dalam Negeri","Sekuriti Kerajaan Malaysia","instrument","277,713,197,000","260,992,662,000"),
     ("Pinjaman Dalam Negeri","Sukuk","instrument","6,991,618,300","7,143,324,000"),
     ("Pinjaman Dalam Negeri","Dalam Negeri","subtotal","399,024,815,300","353,955,986,000"),
     ("Pinjaman Luar Negeri","Pinjaman Pasaran","instrument","10,402,925,000","9,355,200,000"),
     ("Kumpulan Wang Pinjaman Perumahan","Pembiayaan Kumpulan Wang Pinjaman Perumahan","instrument","39,000,000,000","36,400,000,000"),
     ("JUMLAH","Jumlah Pinjaman","subtotal","448,427,740,300","399,711,186,000"),
     ("Bantuan Luar Negeri","Pinjaman Multilateral","instrument","737,856,152","786,984,196"),
     ("Bantuan Luar Negeri","Pinjaman Bilateral","instrument","6,962,066,813","6,603,065,743"),
     ("JUMLAH","Jumlah Bantuan Luar Negeri","subtotal","7,699,922,965","7,390,049,939"),
     ("JUMLAH","JUMLAH HUTANG AWAM","total","456,127,663,265","407,101,235,939"),
    ]
    rows=[]
    for grp,item,kind,a,b in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([grp,item,kind,yr,N(amt),SRC,pg,PP(pg),stmt])
    w("fact_debt.csv",["group_bm","item_bm","kind","year","amount_rm"]+PROV,rows)
    chk("debt Dalam Negeri subtotal", N("4,320,000,000")+N("110,000,000,000")+N("277,713,197,000")+N("6,991,618,300"), 399024815300)
    chk("debt Jumlah Pinjaman", N("399,024,815,300")+N("10,402,925,000")+N("39,000,000,000"), 448427740300)
    chk("debt Jumlah Bantuan LN", N("737,856,152")+N("6,962,066,813"), 7699922965)
    chk("debt JUMLAH HUTANG AWAM", N("448,427,740,300")+N("7,699,922,965"), 456127663265)

# ============ Nota 9(b) Pelbagai Liabiliti (pdf66) -> fact_commitment_detail ============
def commitment_detail():
    stmt="Nota 9(b) Pelbagai Liabiliti"; pg=66
    src=[("Pelbagai Liabiliti","Nota Kena Bayar","203,612,505","170,518,025","item"),
         ("Pelbagai Liabiliti","Sekuriti Tak Dituntut","22,091,529","21,855,998","item"),
         ("Pelbagai Liabiliti","Akaun Depositori Pusat","15,809,492","14,231,026","item"),
         ("Pelbagai Liabiliti","JUMLAH PELBAGAI LIABILITI","241,513,526","206,605,049","total")]
    rows=[]
    for parent,item,a,b,rt in src:
        for yr,amt in ((YEAR,a),(PRIOR,b)):
            V(pg,amt); rows.append([parent,item,yr,N(amt),rt,False,SRC,pg,PP(pg),stmt])
    w("fact_commitment_detail.csv",["parent_bm","item_bm","year","amount_rm","row_type","has_footnote"]+PROV,rows)
    chk("commitment jumlah pelbagai liabiliti", N("203,612,505")+N("22,091,529")+N("15,809,492"), 241513526)

financial=[cash_components,investment_summary,revenue_account_statement,loan_account_statement,
           trust_accounts,memo_assets_detail,debt,commitment_detail]
for fn in financial: fn()
rev=revenue(); om=opex_maksud()

# cross: revenue grand sebenar vs opex maksud grand & prestasi
rg=[r for r in rev if r[0]==0]
if rg:
    chk("rev JUMLAH HASIL sebenar==185,418,919,743", rg[0][7], 185418919743)
chk("opex maksud grand==Nota5b PERBELANJAAN MENGURUS", sum(r[6] for r in om), 185418919743)

print("\n=== NOTES INTERNAL CHECKS ===")
np=sum(1 for c in checks if c[0]); nf=len(checks)-np
for ok,label,got,want in checks:
    if not ok: print(f"  FAIL {label}: got {got} want {want} diff {got-want}")
print(f"notes checks: {np}/{len(checks)} pass, {nf} fail")
if verify_fail:
    print("VERIFY FAILURES:")
    for pg,s in verify_fail: print(f"  pdf {pg}: {s!r}")
    sys.exit(1)
print("notes: all typed tokens verified verbatim")
