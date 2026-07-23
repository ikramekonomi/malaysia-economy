#!/usr/bin/env python3
import csv, os

SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
STMT7 = "Nota 7 Akaun Amanah Disatukan"
OUT = "/home/claude/pkkp/warehouse2011"
os.makedirs(OUT, exist_ok=True)

# ---- amount formatting: en-dash -> "0.0"; else integer string (preserve sign) ----
DASH = "__DASH__"
def fmt(v):
    if v == DASH:
        return "0.0"
    return str(int(v))

rows = []  # each: dict
def add(fg, fund, sec, item, year, amt, rtype, page, printed, foot=False):
    rows.append({
        "fund_group_bm": fg, "fund_bm": fund, "section_bm": sec,
        "line_item_bm": item, "year": year, "amount_rm": fmt(amt),
        "row_type": rtype, "has_footnote": foot, "source_file": SRC,
        "pdf_page": page, "printed_page": printed, "statement": STMT7,
    })

# =========================================================
# 1) PENYATA RINGKASAN (summary matrix) -- year 2011 only, pdf60/printed42
# each fund: 4 line items (Baki pada 1 Januari, Debit, Kredit, Baki pada 31 Disember)
# =========================================================
LI = ["Baki pada 1 Januari", "Debit", "Kredit", "Baki pada 31 Disember"]
ringkasan = [
    ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pembangunan","detail",[-45496256660,46432690220,36693945767,-55235001113]),
    ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pinjaman Perumahan","detail",[3213459959,13264423972,11959288547,1908324534]),
    ("KUMPULAN WANG AMANAH KERAJAAN","Pelbagai Kumpulan Wang Amanah Kerajaan","detail",[29920194056,398714883472,403349616481,34554927065]),
    ("KUMPULAN WANG AMANAH KERAJAAN","Jumlah Kumpulan Wang Amanah Kerajaan","subtotal",[-12362602645,458411997664,452002850795,-18771749514]),
    ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Khas","detail",[582089065,220113233,255954145,617929977]),
    ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Am","detail",[7139541106,7977808251,6540179734,5701912589]),
    ("KUMPULAN WANG AMANAH AWAM","Jumlah Kumpulan Wang Amanah Awam","subtotal",[7721630171,8197921484,6796133879,6319842566]),
    ("AKAUN DEPOSIT","Deposit Am","detail",[8258680212,2605348107,3036723652,8690055757]),
    ("AKAUN DEPOSIT","Deposit Pelarasan","detail",[367139212,2452049738,2384393757,299483231]),
    ("AKAUN DEPOSIT","Jumlah Akaun Deposit","subtotal",[8625819424,5057397845,5421117409,8989538988]),
    ("JUMLAH AKAUN AMANAH DISATUKAN","JUMLAH AKAUN AMANAH DISATUKAN","total",[3984846950,471667316993,464220102083,-3462367960]),
]
for fg, fund, rtype, vals in ringkasan:
    for li, v in zip(LI, vals):
        add(fg, fund, "Penyata Ringkasan", li, 2011, v, rtype, 60, 42)

# =========================================================
# helper for two-year rows (2011 then 2010)
# =========================================================
def add2(fg, fund, sec, item, v2011, v2010, rtype, page, printed):
    add(fg, fund, sec, item, 2011, v2011, rtype, page, printed)
    add(fg, fund, sec, item, 2010, v2010, rtype, page, printed)

# =========================================================
# 2) KUMPULAN WANG PEMBANGUNAN roll-forward -- pdf61/printed43
# =========================================================
FG = "KUMPULAN WANG AMANAH KERAJAAN"; F = "Kumpulan Wang Pembangunan"
add2(FG,F,"","BAKI PADA 1 JANUARI",-45496256660,-24382711582,"opening",61,43)
add2(FG,F,"TERIMAAN","Caruman Dari Akaun Hasil Disatukan",2825131405,8020353053,"detail",61,43)
add2(FG,F,"TERIMAAN","Pindahan Dari Akaun Pinjaman Disatukan",32770290314,22386019081,"detail",61,43)
add2(FG,F,"TERIMAAN","Terimaan Balik Pinjaman",1081971436,1495525781,"detail",61,43)
add2(FG,F,"TERIMAAN","Jualan Aset Modal",91433,73318,"detail",61,43)
add2(FG,F,"TERIMAAN","Pelbagai Terimaan",133387,30874234,"detail",61,43)
add2(FG,F,"TERIMAAN","Pelarasan",DASH,-254760325,"detail",61,43)
add2(FG,F,"TERIMAAN","Jumlah Terimaan",36677617974,31678085142,"subtotal",61,43)
add2(FG,F,"BAYARAN / Perbelanjaan Pembangunan","Langsung",-44917440271,-49096365990,"detail",61,43)
add2(FG,F,"BAYARAN / Perbelanjaan Pembangunan","Pinjaman",-1498922156,-3695264230,"detail",61,43)
add2(FG,F,"BAYARAN","Jumlah Bayaran",-46416362427,-52791630220,"subtotal",61,43)
add2(FG,F,"","Lebihan/(Kurangan) bagi Tahun",-9738744453,-21113545078,"net",61,43)
add2(FG,F,"","BAKI PADA 31 DISEMBER",-55235001113,-45496256660,"closing",61,43)

# =========================================================
# 3) KUMPULAN WANG PINJAMAN PERUMAHAN roll-forward
#    opening + TERIMAAN on pdf61/printed43 ; BAYARAN..closing on pdf62/printed44
# =========================================================
F = "Kumpulan Wang Pinjaman Perumahan"
add2(FG,F,"","BAKI PADA 1 JANUARI",3213459959,1757692388,"opening",61,43)
add2(FG,F,"TERIMAAN / Pinjaman Perseorangan","Bayaran Balik Pinjaman Perseorangan",1106261314,910251578,"detail",61,43)
add2(FG,F,"TERIMAAN / Pinjaman Perseorangan","Hasil Pensekuritian",DASH,7104,"detail",61,43)
add2(FG,F,"TERIMAAN / Pembiayaan","Pelbagai Pembiayaan",7100000000,5900000000,"detail",61,43)
add2(FG,F,"TERIMAAN / Pendapatan Faedah","Bayaran Balik Faedah Pinjaman Perseorangan",995035013,794010397,"detail",61,43)
add2(FG,F,"TERIMAAN / Akaun Pensekuritian","Kutipan Bayaran Balik Akaun Pensekuritian",2435028308,2538563052,"detail",61,43)
add2(FG,F,"TERIMAAN / Akaun Pensekuritian","Peruntukan Diskaun Pensekuritian",342237619,348309662,"detail",61,43)
add2(FG,F,"TERIMAAN","Pelbagai",6127217,11252845,"detail",61,43)
add2(FG,F,"TERIMAAN","Jumlah Terimaan",11984689471,10502394638,"subtotal",61,43)
add2(FG,F,"BAYARAN / Pinjaman Perseorangan","Pengeluaran Pinjaman Perseorangan",-6306896491,-5925636830,"detail",62,44)
add2(FG,F,"BAYARAN / Pembiayaan","Bayaran Balik Pelbagai Pembiayaan",-4500000000,-600000000,"detail",62,44)
add2(FG,F,"BAYARAN / Akaun Pensekuritian","Serahan Kutipan Akaun Pensekuritian",-2455825270,-2493063000,"detail",62,44)
add2(FG,F,"BAYARAN / Akaun Pensekuritian","Bayaran Lain Akaun Pensekuritian",-27103135,-27927237,"detail",62,44)
add2(FG,F,"BAYARAN","Jumlah Bayaran",-13289824896,-9046627067,"subtotal",62,44)
add2(FG,F,"PINDAHAN DARI / (KE)","Akaun Amanah Pensekuritian",DASH,DASH,"detail",62,44)
add2(FG,F,"","BAKI PADA 31 DISEMBER",1908324534,3213459959,"closing",62,44)

# =========================================================
# 4) PELBAGAI KUMPULAN WANG AMANAH KERAJAAN roll-forward
#    AKAUN PENYELESAIAN/PERNIAGAAN/PINJAMAN/LUAR JANGKA on pdf62/printed44
#    PELBAGAI KUMPULAN WANG list on pdf63/printed45
# =========================================================
F = "Pelbagai Kumpulan Wang Amanah Kerajaan"
# AKAUN PENYELESAIAN
add2(FG,F,"AKAUN PENYELESAIAN","Akaun Semasa Antara Pentadbiran",16395143,17601444,"detail",62,44)
add2(FG,F,"AKAUN PENYELESAIAN","Akaun Penyelesaian Utama Perbendaharaan",20588406699,17133244231,"detail",62,44)
add2(FG,F,"AKAUN PENYELESAIAN","Akaun Penyelesaian Jabatan Mengakaun Sendiri",100000000,100000000,"detail",62,44)
add2(FG,F,"AKAUN PENYELESAIAN","Jumlah Akaun Penyelesaian",20704801842,17250845675,"subtotal",62,44)
# AKAUN PERNIAGAAN
add2(FG,F,"AKAUN PERNIAGAAN","Stor dan Woksyop Belum Diuntukkan",78959835,81310524,"detail",62,44)
add2(FG,F,"AKAUN PERNIAGAAN","Jumlah Akaun Perniagaan",78959835,81310524,"subtotal",62,44)
# AKAUN PINJAMAN
akaun_pinjaman = [
    ("Kontraktor",8616423,8517709),
    ("Kredit Kerjasama",15037189,15037189),
    ("Modal Pusingan Jabatan Pembangunan Koperasi",191753670,163492167),
    ("Pembangunan Ekonomi Belia",1895025,1416913),
    ("Pembiayaan Komputer Anggota Perkhidmatan Awam",111675149,101659694),
    ("Pendahuluan Diri (Pegawai Awam)",106013039,88197090),
    ("Pendahuluan Pelbagai",55042544,55839349),
    ("Pendahuluan Peti Sejuk Sarawak",620000,616613),
    ("Pendahuluan Untuk Negeri",302641280,197941807),
    ("Pinjaman Diraja",2500000,2500000),
    ("Pinjaman Kenderaan",666826554,664323196),
    ("Pinjaman Kepada Badan Berkanun dan Badan Lain",3402423934,3150036049),
    ("Pinjaman Perumahan kepada Golongan Pendapatan Rendah",33573560,31788407),
    ("Rakyat Malaysia di Luar Negeri",1008229,993089),
    ("Tabung Pusingan Pinjaman Pelajaran Persekutuan",455344123,356457902),
]
for it,a,b in akaun_pinjaman:
    add2(FG,F,"AKAUN PINJAMAN",it,a,b,"detail",62,44)
add2(FG,F,"AKAUN PINJAMAN","Jumlah Akaun Pinjaman",5354970719,4838817174,"subtotal",62,44)
# KUMPULAN WANG LUAR JANGKA
add2(FG,F,"KUMPULAN WANG LUAR JANGKA","Kumpulan Wang Luar Jangka",117197110,79147700,"detail",62,44)
add2(FG,F,"KUMPULAN WANG LUAR JANGKA","Jumlah Kumpulan Wang Luar Jangka",117197110,79147700,"subtotal",62,44)
# PELBAGAI KUMPULAN WANG (pdf63/printed45)
pelbagai = [
    ("Amanah Negara",4804902567,4362655239),
    ("Amanah Pelajar Miskin",471582212,443757048),
    ("Amanah Sukan Negara",10435878,11766764),
    ("Bantuan Bencana Negara",132205660,143179718),
    ("Bantuan Mangsa Serangan Binatang Buas",335800,587800),
    ("Cadangan Untuk Negeri",230391662,226624324),
    ("Kebajikan dan Kemudahan bagi Penuntut di Luar Negeri",3286540,3781106),
    ("Kumpulan Wang Amanah Kebudayaan dan Kebajikan Penggiat Seni (U)",3235048,DASH),
    ("Kumpulan Wang Amanah Lembaga Peperiksaan Malaysia",65498209,56359475),
    ("Kumpulan Wang Amanah Pendidikan, Perundingan dan Penyelidikan, Institut Penilaian Negara",1075797,414329),
    ("Kumpulan Wang Amanah Pengangkutan Awam",955590216,753645090),
    ("Kumpulan Wang Amanah Pengurusan Perolehan Setem Cukai (Banderol) untuk Rokok dan Minuman Keras",46056666,43876236),
    ("Kumpulan Wang Amanah Projek dan Pengukuran Sempadan Bersama Di antara Negeri-negeri Semenanjung Malaysia",1553561,1773671),
    ("Kumpulan Wang Amanah Projek Pelantar Benua Malaysia",1317538,1398810),
    ("Kumpulan Wang Amanah Sokongan Jabatan Kehakiman Syariah Malaysia",12774394,14880792),
    ("Kumpulan Wang Amanah Taman Laut dan Rizab Laut",3301274,2741782),
    ("Kursi Pengajian Melayu Leiden University, The Netherlands",794,794),
    ("Majlis Penyelidikan dan Kemajuan Sains Negara (MPKSN)",2546001,3089995),
    ("Penjelas Hutang",206715154,200000000),
    ("Perkhidmatan Kemasyarakatan dan Kebajikan",69204562,75395808),
    ("Perpustakaan Negara",1343327,1306444),
    ("Program Perumahan Rakyat Dimiliki",617769870,658582359),
    ("Skim Biasiswa Sukan Persekutuan",918618,1265001),
    ("Tabung Bayaran Balik Cukai",610975797,595253542),
    ("Tabung Bantuan Perubatan (TBP)",19554231,24498178),
    ("Tabung Inovasi Negara Berhad (KWATIN)",26289411,43040000),
    ("Tabung Pustaka Peringatan P. Ramlee",136772,198681),
]
for it,a,b in pelbagai:
    add2(FG,F,"PELBAGAI KUMPULAN WANG",it,a,b,"detail",63,45)
add2(FG,F,"PELBAGAI KUMPULAN WANG","Jumlah Pelbagai Kumpulan Wang",8298997559,7670072984,"subtotal",63,45)
add2(FG,F,"","JUMLAH PELBAGAI KUMPULAN WANG AMANAH KERAJAAN",34554927065,29920194056,"total",63,45)

# =========================================================
# 5) KUMPULAN WANG AMANAH AWAM  (fund_bm blank) pdf63/printed45
# =========================================================
FG = "KUMPULAN WANG AMANAH AWAM"; F = ""
add2(FG,F,"AMANAH KHAS","Kumpulan Wang Dius Api",233365760,198346701,"detail",63,45)
add2(FG,F,"AMANAH KHAS","Faedah atas pelaburan Untuk Deposit Mahkamah",217674942,214516134,"detail",63,45)
add2(FG,F,"AMANAH KHAS","Akaun Amanah Khas Warisan",36827784,43776082,"detail",63,45)
add2(FG,F,"AMANAH KHAS","Pelbagai Amanah Khas",130061491,125450148,"detail",63,45)
add2(FG,F,"AMANAH KHAS","Jumlah Amanah Khas",617929977,582089065,"subtotal",63,45)
add2(FG,F,"AMANAH AM","Akaun Amanah Inisiatif Pembiayaan Swasta (PFI)",3238324521,4437410176,"detail",63,45)
add2(FG,F,"AMANAH AM","Akaun Amanah Membangun/Menaiktaraf Sistem Pembentungan untuk Pembangunan Baru",597912481,725063371,"detail",63,45)
add2(FG,F,"AMANAH AM","Akaun Amanah Industri Bekalan Elektrik",414098864,442029026,"detail",63,45)
add2(FG,F,"AMANAH AM","Akaun Amanah Dana Khas",394775310,452213814,"detail",63,45)
add2(FG,F,"AMANAH AM","Pelbagai Amanah Am",1056801413,1082824719,"detail",63,45)
add2(FG,F,"AMANAH AM","Jumlah Amanah Am",5701912589,7139541106,"subtotal",63,45)
add2(FG,F,"","JUMLAH KUMPULAN WANG AMANAH AWAM",6319842566,7721630171,"total",63,45)

# =========================================================
# 6) AKAUN DEPOSIT (fund_bm blank) pdf64/printed46
# =========================================================
FG = "AKAUN DEPOSIT"; F = ""
add2(FG,F,"DEPOSIT AM","Kawalan Wang Tak Dituntut",2430080705,2131449146,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Deposit Wang Tak Dituntut",1747344932,1751022061,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Wang Jaminan Perlaksanaan",1673641083,1711333693,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Harta Kebangkrapan",929171695,848872213,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Deposit Mahkamah Tinggi",669797188,750171139,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Pelbagai Deposit Am",1240020154,1065831960,"detail",64,46)
add2(FG,F,"DEPOSIT AM","Jumlah Deposit Am",8690055757,8258680212,"subtotal",64,46)
add2(FG,F,"DEPOSIT PELARASAN","Terimaan Yang Tidak Diperuntukkan",99407201,101101437,"detail",64,46)
add2(FG,F,"DEPOSIT PELARASAN","Pembatalan Bayaran EFT",92990934,119830425,"detail",64,46)
add2(FG,F,"DEPOSIT PELARASAN","Deposit Pelarasan Cek Terbatal",88839725,127593518,"detail",64,46)
add2(FG,F,"DEPOSIT PELARASAN","Pelbagai Deposit Pelarasan",18245371,18613832,"detail",64,46)
add2(FG,F,"DEPOSIT PELARASAN","Jumlah Deposit Pelarasan",299483231,367139212,"subtotal",64,46)
add2(FG,F,"","JUMLAH AKAUN DEPOSIT",8989538988,8625819424,"total",64,46)

# ---- write trust_fund_detail ----
hdr = ["fund_group_bm","fund_bm","section_bm","line_item_bm","year","amount_rm",
       "row_type","has_footnote","source_file","pdf_page","printed_page","statement"]
p1 = os.path.join(OUT,"fact_trust_fund_detail.csv")
with open(p1,"w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=hdr)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("wrote", p1, len(rows), "rows")

# =========================================================
# fact_other_notes  (Nota 8-12 narrative RM figures)
# =========================================================
onh = ["nota","line_item_bm","year","amount_rm","row_type","has_footnote",
       "source_file","pdf_page","printed_page","statement"]
def onr(nota,item,year,amt,page,printed,stmt):
    return {"nota":nota,"line_item_bm":item,"year":year,"amount_rm":str(float(amt)),
            "row_type":"narrative","has_footnote":False,"source_file":SRC,
            "pdf_page":page,"printed_page":printed,"statement":stmt}

onrows = [
    onr("8(b)","Pengambilalihan ekuiti UDA Holdings Berhad (176,577,186 unit) oleh Menteri Kewangan Diperbadankan melalui set off pembayaran dividen Khazanah Nasional Berhad",2011,529731558,65,47,"Nota 8 Memorandum Aset"),
    onr("10(a)","Pinjaman badan berkanun dan syarikat milik kerajaan yang dijamin oleh Kerajaan Persekutuan [Akta 96]",2011,116757672552,66,48,"Nota 10 Liabiliti Luar Jangka"),
    onr("10(b)","Simpanan pendeposit di Bank Simpanan Nasional, Kumpulan Wang Simpanan Guru-Guru, Kumpulan Wang Simpanan Pekerja dan Lembaga Tabung Haji",2011,471085369744,66,48,"Nota 10 Liabiliti Luar Jangka"),
    onr("10(c)","Third Party War Risk Liability dengan Malaysia Airports Holdings Berhad mengikut perjanjian indemniti",2011,475000000,66,48,"Nota 10 Liabiliti Luar Jangka"),
    onr("11","Akaun Belum Terima berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)",2011,21478375650,66,48,"Nota 11 Akaun Belum Terima"),
    onr("12","Wang pendahuluan kepada kontraktor yang belum diimbuh balik berdasarkan rekod Kementerian/Jabatan (maklumat tambahan)",2011,1535759271,66,48,"Nota 12 Wang Pendahuluan Kepada Kontraktor"),
]
p2 = os.path.join(OUT,"fact_other_notes.csv")
with open(p2,"w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=onh)
    w.writeheader()
    for r in onrows:
        w.writerow(r)
print("wrote", p2, len(onrows), "rows")
