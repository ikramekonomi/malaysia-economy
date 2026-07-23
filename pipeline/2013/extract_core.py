#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2013 (RMKe-10 era, pre-GST). Adjacent to 2014.

2013 page anchors (printed = pdf - 24): position pdf 57, cash 58-59, prestasi 60,
memorandum 61, Nota 5 stmt/5(a) pdf 64-65, Nota 5(b) opex maksud pdf 66,
Nota 6 loan stmt pdf 67, Nota 7 trust pdf 68, Nota 9 debt pdf 73-74.

Format deltas vs 2014 volume:
 - Penyata Kedudukan (pdf57): 2013/2012 cols; unlabelled balancing subtotal
   49,083,585,341 both sides + 'DIPEGANG BAGI :' caption. Captured as JUMLAH rows.
 - Cash statement (pdf58-59): 2013/2012, each year item-RM + category-total-RM.
   HAS a 'Perbelanjaan Modal / Pembelian Instrumen Kewangan' line (Nota 4), 0 in
   2013 / 1,205,673,496 in 2012 (absent from 2014 volume).
 - Prestasi (pdf60): 3 cols (2013 Anggaran, 2013 Sebenar, 2012 Sebenar). Labels
   'LEBIHAN HASIL', 'KURANGAN KESELURUHAN' (no /(Kurangan) suffix).
 - Memorandum (pdf61): Pinjaman Boleh Dituntut 92,547,188,214 (pre-restatement;
   2014 vol restates 2013 to 92,444,600,374). Kept as printed. Hutang Awam label.
 - Nota 5(b) maksud rounded to whole RM (Lampiran-1 keeps sen). B.12 carries '**'.
 - Nota 9 debt: Dalam Negeri has a 'Sukuk' line (0/2,398,801,500); KWPP is a single
   'Pembiayaan Kumpulan Wang Pinjaman Perumahan' line (Berjangka/Sukuk split only
   'Mulai 2014'). Unlabelled DN subtotal 481,895,000,000.
All amounts exact RM as printed (sen kept where printed). Tokens verified verbatim.
"""
import csv, os, re, sys

YEAR = 2013
PRIOR = 2012
SRC = "2013_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2013"
os.makedirs(OUT, exist_ok=True)
pages = open("/home/claude/pkkp/work/2013/full.txt", encoding="utf-8").read().split("\f")
def page(n): return pages[n - 1]
NUM = r"[\d,]+(?:\.\d+)?"

def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}: return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v

verify_fail = []
def V(pdf_page, s):
    s = s.strip()
    if s in ("-", "–", ""): return
    if s not in page(pdf_page): verify_fail.append((pdf_page, s))
def N(s): return parse_amount(s)

def w(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f); cw.writerow(header); cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")

PROV = ["source_file", "pdf_page", "printed_page", "statement"]

def financial_position():
    stmt = "Penyata Kedudukan Kewangan"
    src = [
        ("WANG AWAM", "WANG TUNAI", 3, "25,051,038,985", "29,355,825,184"),
        ("WANG AWAM", "PELABURAN", 4, "24,032,546,356", "24,049,136,708"),
        ("WANG AWAM", "JUMLAH WANG AWAM", "", "49,083,585,341", "53,404,961,892"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN HASIL DISATUKAN", 5, "11,863,127,086", "11,863,127,086"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN PINJAMAN DISATUKAN", 6, "26,380,357,864", "28,904,795,292"),
        ("KUMPULAN WANG DISATUKAN", "AKAUN AMANAH DISATUKAN", 7, "10,840,100,391", "12,637,039,514"),
        ("KUMPULAN WANG DISATUKAN", "JUMLAH KUMPULAN WANG DISATUKAN", "", "49,083,585,341", "53,404,961,892"),
    ]
    rows = []
    for sec, item, nota, a1, a0 in src:
        for yr, amt in ((YEAR, a1), (PRIOR, a0)):
            V(57, amt); rows.append([sec, item, nota, yr, N(amt), SRC, 57, 33, stmt])
    w("fact_financial_position.csv", ["section","line_item_bm","nota","year","amount_rm"]+PROV, rows)

def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    src = [
        ("TERIMAAN","Hasil","Hasil Cukai","155,952,205,546","151,643,090,263",58),
        ("TERIMAAN","Hasil","Hasil Bukan Cukai","50,241,306,637","50,909,327,554",58),
        ("TERIMAAN","Hasil","Terimaan Bukan Hasil","1,580,740,186","872,220,870",58),
        ("TERIMAAN","Hasil","Hasil Wilayah Persekutuan","1,378,022,570","483,424,598",58),
        ("TERIMAAN","Hasil","Jumlah Hasil","209,152,274,939","203,908,063,285",58),
        ("TERIMAAN","Pinjaman","Dalam Negeri","111,357,188,482","108,145,229,672",58),
        ("TERIMAAN","Pinjaman","Luar Negeri","–","–",58),
        ("TERIMAAN","Pinjaman","Jumlah Pinjaman","111,357,188,482","108,145,229,672",58),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Multilateral","325,828","91,016,051",58),
        ("TERIMAAN","Bantuan Luar Negeri","Pinjaman Bilateral","412,326,368","592,519,054",58),
        ("TERIMAAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","412,652,196","683,535,105",58),
        ("TERIMAAN","Terimaan Modal","Terimaan Balik Pinjaman","1,377,968,465","1,058,991,393",58),
        ("TERIMAAN","Terimaan Modal","Perbezaan Forex Relending Loan","6,947,052","–",58),
        ("TERIMAAN","Terimaan Modal","Terimaan Balik Pendahuluan","29,508,837","29,400,000",58),
        ("TERIMAAN","Terimaan Modal","Jualan Aset Modal","87,017","89,869",58),
        ("TERIMAAN","Terimaan Modal","Pelbagai Terimaan Modal","24,919,163","1,519,509,321",58),
        ("TERIMAAN","Terimaan Modal","Jualan Instrumen Kewangan","717,599,227","–",58),
        ("TERIMAAN","Terimaan Modal","Jumlah Terimaan Modal","2,157,029,761","2,607,990,583",58),
        ("TERIMAAN","Terimaan Amanah","Inisiatif Pembiayaan Swasta (PFI)","148,775,232","2,136,635,290",58),
        ("TERIMAAN","Terimaan Amanah","Aktiviti Pembangunan Khas Pembiayaan Swasta","5,054,580,710","5,000,230,450",58),
        ("TERIMAAN","Terimaan Amanah","Pelbagai","–","–",58),
        ("TERIMAAN","Terimaan Amanah","Jumlah Terimaan Amanah","5,203,355,942","7,136,865,740",58),
        ("JUMLAH","Jumlah Terimaan","Jumlah Terimaan","328,282,501,320","322,481,684,385",58),
        ("BAYARAN","Perbelanjaan Mengurus","Emolumen","61,001,190,871","60,015,799,383",59),
        ("BAYARAN","Perbelanjaan Mengurus","Perkhidmatan dan Bekalan","33,860,076,805","31,962,576,293",59),
        ("BAYARAN","Perbelanjaan Mengurus","Aset","1,414,680,060","1,769,606,790",59),
        ("BAYARAN","Perbelanjaan Mengurus","Pemberian dan Kenaan Bayaran Tetap","110,424,046,265","104,451,633,629",59),
        ("BAYARAN","Perbelanjaan Mengurus","Perbelanjaan-perbelanjaan Lain","1,052,603,153","1,466,359,006",59),
        ("BAYARAN","Perbelanjaan Mengurus","Jumlah Perbelanjaan Mengurus","207,752,597,154","199,665,975,101",59),
        ("BAYARAN","Perbelanjaan Pembangunan","Langsung","40,473,294,579","44,978,124,405",59),
        ("BAYARAN","Perbelanjaan Pembangunan","Pinjaman","1,736,506,805","1,954,329,401",59),
        ("BAYARAN","Perbelanjaan Pembangunan","Jumlah Perbelanjaan Pembangunan","42,209,801,384","46,932,453,806",59),
        ("BAYARAN","Pinjaman","Dalam Negeri","73,030,098,558","61,403,631,379",59),
        ("BAYARAN","Pinjaman","Luar Negeri","–","–",59),
        ("BAYARAN","Pinjaman","Jumlah Pinjaman","73,030,098,558","61,403,631,379",59),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Multilateral","98,564,203","95,017,283",59),
        ("BAYARAN","Bantuan Luar Negeri","Pinjaman Bilateral","522,458,616","590,443,637",59),
        ("BAYARAN","Bantuan Luar Negeri","Jumlah Bantuan Luar Negeri","621,022,819","685,460,920",59),
        ("BAYARAN","Perbelanjaan Modal","Pembelian Instrumen Kewangan","–","1,205,673,496",59),
        ("BAYARAN","Perbelanjaan Modal","Jumlah Perbelanjaan Modal","–","1,205,673,496",59),
        ("BAYARAN","Perbelanjaan Amanah","Inisiatif Pembiayaan Swasta (PFI)","1,212,643,573","2,352,521,909",59),
        ("BAYARAN","Perbelanjaan Amanah","Aktiviti Pembangunan Khas Pembiayaan Swasta","3,239,193,138","1,718,428,784",59),
        ("BAYARAN","Perbelanjaan Amanah","Pelbagai","4,521,930,893","3,628,489,333",59),
        ("BAYARAN","Perbelanjaan Amanah","Jumlah Perbelanjaan Amanah","8,973,767,604","7,699,440,026",59),
        ("JUMLAH","Jumlah Bayaran","Jumlah Bayaran","332,587,287,519","317,592,634,728",59),
        ("JUMLAH","Tambahan/(Kurangan) Wang Tunai","Tambahan/(Kurangan) Wang Tunai","(4,304,786,199)","4,889,049,657",59),
        ("JUMLAH","Wang Tunai Pada 1 Januari","Wang Tunai Pada 1 Januari","29,355,825,184","24,466,775,527",59),
        ("JUMLAH","WANG TUNAI PADA 31 DISEMBER","WANG TUNAI PADA 31 DISEMBER","25,051,038,985","29,355,825,184",59),
    ]
    rows = []
    for flow, cat, item, a1, a0, pg in src:
        for yr, amt in ((YEAR, a1), (PRIOR, a0)):
            V(pg, amt); rows.append([flow, cat, item, yr, N(amt), SRC, pg, pg-24, stmt])
    w("fact_cash_statement.csv", ["flow","category_bm","item_bm","year","amount_rm"]+PROV, rows)

def performance():
    stmt = "Penyata Prestasi Kewangan"
    src3 = [
        ("HASIL","revenue","220,422,427,000","213,370,213,558","207,912,754,669"),
        ("Belanja Mengurus","opex","216,647,067,943","211,270,336,793","205,537,081,525"),
        ("LEBIHAN HASIL","current_balance","3,775,359,057","2,099,876,765","2,375,673,144"),
        ("Belanja Pembangunan","devex","46,463,747,739","42,209,801,384","46,932,453,806"),
        ("KURANGAN KESELURUHAN","overall_deficit","(42,688,388,682)","(40,109,924,619)","(44,556,780,662)"),
    ]
    src2 = [
        ("Pinjaman dan Bantuan Luar Negeri","financing_net_borrowing","39,305,562,572","43,327,545,911"),
        ("Terimaan Balik Pinjaman dan Pelbagai Terimaan","financing_capital_receipts","1,569,433,042","2,634,972,286"),
        ("Perubahan Tunai, Pelaburan dan Amanah","financing_cash_inv_trust_change","(765,070,995)","(1,405,737,535)"),
        ("JUMLAH PEMBIAYAAN","total_financing","40,109,924,619","44,556,780,662"),
    ]
    rows = []
    for label, code, ag, seb, pri in src3:
        for tok in (ag, seb, pri): V(60, tok)
        rows.append([label, code, YEAR, "anggaran", N(ag), SRC, 60, 36, stmt])
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 60, 36, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 60, 36, stmt])
    for label, code, seb, pri in src2:
        for tok in (seb, pri): V(60, tok)
        rows.append([label, code, YEAR, "sebenar", N(seb), SRC, 60, 36, stmt])
        rows.append([label, code, PRIOR, "sebenar", N(pri), SRC, 60, 36, stmt])
    w("fact_financial_performance.csv", ["line_item_bm","line_code","year","basis","amount_rm"]+PROV, rows)

def memorandum():
    stmt = "Penyata Akaun Memorandum"
    src = [
        ("MEMORANDUM ASET","Pinjaman Boleh Dituntut","92,547,188,214","95,613,714,119"),
        ("MEMORANDUM ASET","Pelaburan","29,679,137,799","28,110,412,577"),
        ("MEMORANDUM LIABILITI","Hutang Awam","539,857,759,215","501,616,849,368"),
        ("MEMORANDUM LIABILITI","Pelbagai Liabiliti","286,624,151","275,621,222"),
    ]
    rows = []
    for sec, item, a1, a0 in src:
        for yr, amt in ((YEAR, a1), (PRIOR, a0)):
            V(61, amt); rows.append([sec, item, yr, N(amt), SRC, 61, 37, stmt])
    w("fact_memorandum.csv", ["section","line_item_bm","year","amount_rm"]+PROV, rows)

REV_L1 = ["HASIL CUKAI","HASIL BUKAN CUKAI","TERIMAAN BUKAN HASIL","HASIL WILAYAH PERSEKUTUAN"]
L1_JUMLAH = {"Jumlah Hasil Cukai":"HASIL CUKAI","Jumlah Hasil Bukan Cukai":"HASIL BUKAN CUKAI",
             "Jumlah Terimaan Bukan Hasil":"TERIMAAN BUKAN HASIL","Jumlah Hasil Wilayah Persekutuan":"HASIL WILAYAH PERSEKUTUAN"}
JUNK = re.compile(r"^(RM|Anggaran|Asal|Disemak|Sebenar|% ?Anggaran|%$|\(disambung|\(sambungan|NOTA\s+KEPADA|PENYATA\s+KEWANGAN|BAGI\s+TAHUN|KEWANGAN|6\.\s|\d+$|[ivxl]+$|ANM$|nota kepada|penyata kewangan|Penyata Kewangan|Hasil mengikut|Perbezaan ketara|Laporan Akauntan|Terimaan Bukan Hasil yang|Hasil Bukan Cukai yang|pegangan ekuiti|wang pensekuritian|pinjaman berjumlah)")

def revenue():
    stmt = "Nota 5(a) Hasil Mengikut Penjenisan"
    rows = []
    l1 = None; started = False
    for pdfp, printed in [(64,40),(65,41)]:
        for line in page(pdfp).split("\n"):
            s = re.sub(r"^(\s*)\d{1,3}(\s{3,})", r"\1\2", line.rstrip())
            st = s.strip()
            if not st: continue
            if st == "HASIL CUKAI" and pdfp == 64: started = True
            if not started: continue
            if "(b) Perbelanjaan Mengurus" in st: started = False; break
            if st in REV_L1: l1 = st; continue
            m = re.match(rf"^(.*?\S)\s{{2,}}((?:\*?\(?(?:{NUM}|[–—-])\)?)(?:\s+\*?\(?(?:{NUM}|[–—-])\)?)*)\s*$", s)
            if not m:
                if (rows and not re.search(r"[\d%]", st) and len(st) < 60 and not JUNK.match(st) and st not in REV_L1):
                    rows[-1][3] = rows[-1][3] + " " + st
                continue
            label = m.group(1).strip()
            if not label or JUNK.match(label): continue
            toks = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", m.group(2))
            nums = [parse_amount(x) for x in toks]
            if len(nums) == 6: a_asal, a_disemak, sebenar, pct, sebenar_pri, pct_pri = nums
            elif len(nums) == 4: a_asal, a_disemak, sebenar, pct = nums; sebenar_pri = pct_pri = None
            else: continue
            if label == "JUMLAH HASIL":
                rows.append([0, None, None, "HASIL", YEAR, a_asal, a_disemak, sebenar, pct, sebenar_pri, pct_pri, SRC, pdfp, printed, stmt])
            elif label in L1_JUMLAH:
                cat = L1_JUMLAH[label]
                rows.append([1, cat, None, cat, YEAR, a_asal, a_disemak, sebenar, pct, sebenar_pri, pct_pri, SRC, pdfp, printed, stmt])
            else:
                rows.append([3, l1, None, label, YEAR, a_asal, a_disemak, sebenar, pct, sebenar_pri, pct_pri, SRC, pdfp, printed, stmt])
    w("fact_revenue.csv", ["level","category_l1_bm","category_l2_bm","item_bm","year",
        "anggaran_asal_rm","anggaran_disemak_rm","sebenar_rm","pct_anggaran","sebenar_prior_rm","pct_anggaran_prior"]+PROV, rows)

def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    pdfp, printed = 66, 42
    for line in page(pdfp).split("\n"):
        s = re.sub(r"\*{2,3}\s*", "*", line.rstrip())
        m = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{3,4}})$", s)
        if not m:
            st = line.strip()
            if (rows and st and not re.search(r"\d", st) and len(st) < 45 and st[0].islower()
                    and not re.match(r"^(nota kepada|penyata kewangan)", st)):
                rows[-1][2] = rows[-1][2] + " " + st
            continue
        kind, code, name, numstr = m.groups()
        raw = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", numstr)
        flagged = any("*" in x for x in raw)
        nums = [parse_amount(x) for x in raw]
        if len(nums) == 4: asal, dipinda, sebenar, pct = nums
        else: continue
        rows.append([f"{kind}.{code}", "Tanggungan" if kind=="T" else "Bekalan", name.strip(),
                     YEAR, asal, dipinda, sebenar, pct, flagged, SRC, pdfp, printed, stmt])
    w("fact_opex_maksud.csv", ["maksud_code","jenis_bm","maksud_name_bm","year",
        "anggaran_asal_rm","anggaran_dipinda_rm","sebenar_rm","pct_anggaran","has_footnote"]+PROV, rows)

def debt():
    stmt = "Nota 9 Memorandum Liabiliti"
    src = [
        ("Pinjaman Dalam Negeri","Bil Perbendaharaan","instrument","4,320,000,000","4,320,000,000",73),
        ("Pinjaman Dalam Negeri","Terbitan Pelaburan Kerajaan","instrument","172,500,000,000","143,500,000,000",73),
        ("Pinjaman Dalam Negeri","Sekuriti Kerajaan Malaysia","instrument","305,075,000,000","292,150,000,000",73),
        ("Pinjaman Dalam Negeri","Sukuk","instrument","–","2,398,801,500",73),
        ("Pinjaman Dalam Negeri","Dalam Negeri","subtotal","481,895,000,000","442,368,801,500",73),
        ("Kumpulan Wang Pinjaman Perumahan","Pembiayaan Kumpulan Wang Pinjaman Perumahan","instrument","41,200,000,000","42,400,000,000",73),
        ("Pinjaman Luar Negeri","Pinjaman Pasaran","instrument","10,791,300,000","10,052,575,000",73),
        ("JUMLAH","PINJAMAN","subtotal","533,886,300,000","494,821,376,500",73),
        ("Bantuan Luar Negeri","Pinjaman Multilateral","instrument","721,664,278","712,418,688",73),
        ("Bantuan Luar Negeri","Pinjaman Bilateral","instrument","5,249,794,937","6,083,054,180",73),
        ("JUMLAH","BANTUAN LUAR NEGERI","subtotal","5,971,459,215","6,795,472,868",73),
        ("JUMLAH","HUTANG AWAM","total","539,857,759,215","501,616,849,368",73),
        ("Pelbagai Liabiliti","PELBAGAI LIABILITI","misc_total","286,624,151","275,621,222",74),
    ]
    rows = []
    for grp, item, kind, a1, a0, pg in src:
        for yr, amt in ((YEAR, a1), (PRIOR, a0)):
            V(pg, amt); rows.append([grp, item, kind, yr, N(amt), SRC, pg, pg-24, stmt])
    w("fact_debt.csv", ["group_bm","item_bm","kind","year","amount_rm"]+PROV, rows)

def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    src = [
        ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pembangunan","(43,824,579,256)","84,071,032,017","87,360,540,440","(40,535,070,833)"),
        ("KUMPULAN WANG AMANAH KERAJAAN","Kumpulan Wang Pinjaman Perumahan","1,515,520,436","17,057,292,886","16,866,717,401","1,324,944,951"),
        ("KUMPULAN WANG AMANAH KERAJAAN","Pelbagai Kumpulan Wang Amanah Kerajaan","35,751,982,000","352,524,794,935","346,378,029,865","29,605,216,930"),
        ("","KUMPULAN WANG AMANAH KERAJAAN","(6,557,076,820)","453,653,119,838","450,605,287,706","(9,604,908,952)"),
        ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Khas","637,792,672","200,779,646","209,828,993","646,842,019"),
        ("KUMPULAN WANG AMANAH AWAM","Kumpulan Wang Amanah Am","9,101,844,850","7,776,065,739","8,734,148,829","10,059,927,940"),
        ("","KUMPULAN WANG AMANAH AWAM","9,739,637,522","7,976,845,385","8,943,977,822","10,706,769,959"),
        ("AKAUN DEPOSIT","Deposit Am","9,155,210,611","2,110,884,237","2,421,651,280","9,465,977,654"),
        ("AKAUN DEPOSIT","Deposit Pelarasan","299,268,201","4,036,100,414","4,009,093,943","272,261,730"),
        ("","AKAUN DEPOSIT","9,454,478,812","6,146,984,651","6,430,745,223","9,738,239,384"),
        ("JUMLAH","AKAUN AMANAH DISATUKAN","12,637,039,514","467,776,949,874","465,980,010,751","10,840,100,391"),
    ]
    rows = []
    for parent, acct, ba, dr, cr, bk in src:
        for tok in (ba, dr, cr, bk): V(68, tok)
        rows.append([parent, acct, YEAR, N(ba), N(dr), N(cr), N(bk), SRC, 68, 44, stmt])
    w("fact_trust_accounts.csv", ["parent_group_bm","account_bm","year","baki_awal_rm","debit_rm","kredit_rm","baki_akhir_rm"]+PROV, rows)

financial_position(); cash_statement(); performance(); memorandum()
revenue(); opex_maksud(); debt(); trust()

if verify_fail:
    print("RAW-TEXT VERIFICATION FAILURES:")
    for pg, s in verify_fail: print(f"  pdf_page {pg}: {s!r}")
    sys.exit(1)
print("core: all typed tokens verified verbatim on their source pages")
