#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2024 text layer (pdftotext -layout).

All amounts in RM (exact as printed). Provenance on every row.
Output: tidy CSVs in /home/claude/pkkp/warehouse/
"""
import csv
import os
import re

YEAR = 2024
PRIOR = 2023
SRC = "2024_Penyata_Kewangan_Kerajaan_Persekutuan.pdf"
OUT = "/home/claude/pkkp/warehouse"
os.makedirs(OUT, exist_ok=True)

pages = open("/home/claude/pkkp/work/2024_full.txt", encoding="utf-8").read().split("\f")


def page(n):
    return pages[n - 1]


NUM = r"[\d,]+(?:\.\d+)?"


def parse_amount(tok):
    """'1,234,567' -> 1234567.0 ; '–'/'-' -> 0.0 (printed dash means nil); '(123)' -> -123."""
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def grab_rows(text, min_nums, max_nums=None):
    """Yield (label, [nums], raw_line) for lines ending in >=min_nums numeric tokens."""
    for line in text.split("\n"):
        s = line.rstrip()
        if not s.strip():
            continue
        toks = re.findall(rf"\(?{NUM}\)?\*?|\*?\(?[–—-]\)?", s)
        # find trailing numeric tokens
        m = re.match(rf"^(.*?)((?:\s+\*?\(?(?:{NUM}|[–—-])\)?){{{min_nums},{max_nums or 12}}})\s*$", s)
        if not m:
            continue
        label = m.group(1).strip()
        nums = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", m.group(2))
        if label and not re.match(r"^\d", label):
            yield label, nums, s


def w(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print(f"{name}: {len(rows)} rows")


PROV = ["source_file", "pdf_page", "printed_page", "statement"]

# ---------------------------------------------------------------- 1. Penyata Kedudukan Kewangan (p73)
def financial_position():
    stmt = "Penyata Kedudukan Kewangan"
    targets = {
        "WANG TUNAI": ("WANG AWAM", 3),
        "PELABURAN": ("WANG AWAM", 4),
        "AKAUN HASIL DISATUKAN": ("KUMPULAN WANG DISATUKAN", 5),
        "AKAUN PINJAMAN DISATUKAN": ("KUMPULAN WANG DISATUKAN", 6),
        "AKAUN AMANAH DISATUKAN": ("KUMPULAN WANG DISATUKAN", 7),
    }
    rows = []
    for label, nums, _ in grab_rows(page(73), 2, 3):
        lab = label.strip()
        # strip trailing nota number embedded? format: LABEL  nota  n1  n2 -> nums may include nota
        key = re.sub(r"\s+\d+$", "", lab)
        if key in targets:
            section, nota = targets[key]
            vals = [parse_amount(x) for x in nums]
            if len(vals) == 3:  # first token is the Nota number
                vals = vals[1:]
            rows.append([section, key, nota, YEAR, vals[0], SRC, 73, 59, stmt])
            rows.append([section, key, nota, PRIOR, vals[1], SRC, 73, 59, stmt])
    w("fact_financial_position.csv",
      ["section", "line_item_bm", "nota", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 2. Penyata Penerimaan dan Pembayaran Wang Tunai (p74-75)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    spec = [  # (flow, category, item)
        ("TERIMAAN", "Hasil", ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"]),
        ("TERIMAAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("TERIMAAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("TERIMAAN", "Terimaan Modal", ["Terimaan Balik Pinjaman", "Jualan Aset Modal", "Pelbagai Terimaan", "Jualan Instrumen Kewangan"]),
        ("TERIMAAN", "Terimaan Amanah", ["Akaun Amanah PFI II *", "Pelbagai"]),
        ("BAYARAN", "Perbelanjaan Mengurus", ["Emolumen", "Perkhidmatan dan Bekalan", "Aset", "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"]),
        ("BAYARAN", "Perbelanjaan Pembangunan", ["Langsung", "Pinjaman"]),
        ("BAYARAN", "Perbelanjaan Kumpulan Wang COVID-19", ["Perbelanjaan COVID-19"]),
        ("BAYARAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("BAYARAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("BAYARAN", "Perbelanjaan Modal", ["Pembelian Instrumen Kewangan"]),
        ("BAYARAN", "Perbelanjaan Amanah", ["Akaun Amanah PFI II *", "Pelbagai"]),
    ]
    totals = ["Jumlah Terimaan", "Jumlah Bayaran", "Tambahan/(Kurangan) Wang Tunai",
              "Wang Tunai Pada 1 Januari", "WANG TUNAI PADA 31 DISEMBER"]
    rows = []
    for pdfp, printed in [(74, 60), (75, 61)]:
        txt = page(pdfp)
        lines = txt.split("\n")
        flow = None
        cat = None
        for line in lines:
            s = line.strip()
            if s in ("TERIMAAN", "BAYARAN"):
                flow = s
                continue
            base = re.sub(r"\s+8$|\s+\d$", "", s)  # strip nota refs
            # category headers have no numbers
            for f, c, items in spec:
                if f == flow and (base == c or s == c):
                    cat = c
            m = re.match(rf"^(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{1,4}})$", line.rstrip())
            if not m:
                continue
            label = re.sub(r"\s+\d$", "", m.group(1).strip())
            nums = [parse_amount(x) for x in re.findall(rf"\(?(?:{NUM}|[–—-])\)?", m.group(2))]
            item_match = None
            for f, c, items in spec:
                if f != flow:
                    continue
                for it in items:
                    if label == it.replace(" *", "") or label == it:
                        item_match = (f, c, it.replace(" *", ""))
            if item_match and cat and item_match[1] == cat:
                f, c, it = item_match
                # two amount columns per year block: item col + block col; item value is first
                # rows carry 2 or 4 numbers: cur_item [cur_block] prior_item [prior_block]
                if len(nums) == 4:
                    cur, pri = nums[0], nums[2]
                elif len(nums) == 2:
                    cur, pri = nums
                elif len(nums) == 3:
                    # item + block-close for cur, item for prior OR item, item+block
                    cur, pri = nums[0], nums[-1]
                else:
                    cur, pri = nums[0], None
                rows.append([f, c, it, YEAR, cur, SRC, pdfp, printed, stmt])
                if pri is not None:
                    rows.append([f, c, it, PRIOR, pri, SRC, pdfp, printed, stmt])
            elif label in totals or label.upper() in [t.upper() for t in totals]:
                if len(nums) >= 2:
                    rows.append(["JUMLAH", label, label, YEAR, nums[0], SRC, pdfp, printed, stmt])
                    rows.append(["JUMLAH", label, label, PRIOR, nums[1], SRC, pdfp, printed, stmt])
    w("fact_cash_statement.csv",
      ["flow", "category_bm", "item_bm", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 3. Penyata Prestasi Kewangan (p76)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    txt = page(76)
    rows = []
    pat = {
        "Hasil": "revenue",
        "Belanja Mengurus": "opex",
        "LEBIHAN/(KURANGAN) HASIL": "current_balance",
        "Belanja Pembangunan": "devex",
        "Belanja Kumpulan Wang COVID-19": "covid_fund_exp",
        "KURANGAN KESELURUHAN": "overall_deficit",
        "JUMLAH PEMBIAYAAN": "total_financing",
    }
    for label, nums, _ in grab_rows(txt, 2, 4):
        lab = re.sub(r"\s+\d$", "", label.strip())
        if lab in pat:
            vals = [parse_amount(x) for x in nums]
            if len(vals) == 4 and abs(vals[0]) < 100:  # leading Nota reference digit
                vals = vals[1:]
            if len(vals) == 3:
                rows.append([lab, pat[lab], YEAR, "anggaran", vals[0], SRC, 76, 62, stmt])
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[1], SRC, 76, 62, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[2], SRC, 76, 62, stmt])
            elif len(vals) == 2:
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[0], SRC, 76, 62, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[1], SRC, 76, 62, stmt])
    # financing components under KURANGAN DIBIAYAI OLEH (labels wrap over 2-3 lines;
    # numbers are printed on the first line of each label)
    fin = [
        ("Pinjaman dan", "Pinjaman dan Bantuan Luar Negeri", "financing_net_borrowing"),
        ("Terimaan Balik Pinjaman,", "Terimaan Balik Pinjaman, Jualan Aset Modal dan Pelbagai Terimaan",
         "financing_capital_receipts"),
        ("Perubahan Tunai,", "Perubahan Tunai, Pelaburan dan Amanah", "financing_cash_inv_trust_change"),
    ]
    for first_frag, full_label, code in fin:
        for label, nums, _ in grab_rows(txt, 2, 3):
            if label.strip() == first_frag:
                vals = [parse_amount(x) for x in nums]
                vals = [v for v in vals if abs(v) >= 100]  # drop stray Nota ref
                rows.append([full_label, code, YEAR, "sebenar", vals[0], SRC, 76, 62, stmt])
                rows.append([full_label, code, PRIOR, "sebenar", vals[1], SRC, 76, 62, stmt])
    w("fact_financial_performance.csv",
      ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 4. Hasil mengikut penjenisan (p83-84)
REV_L1 = ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]
REV_L2 = ["Cukai Langsung", "Cukai Tidak Langsung"]


JUNK = re.compile(
    r"^(RM|Anggaran|Asal|Disemak|Sebenar|% ?Anggaran|\(disambung\)|\(sambungan\)|"
    r"NOTA KEPADA|PENYATA KEWANGAN|BAGI TAHUN|WJD25|\d+$)"
)


def revenue():
    stmt = "Nota 5(a) Hasil Mengikut Penjenisan"
    rows = []
    l1 = l2 = None
    started = False
    for pdfp, printed in [(83, 69), (84, 70)]:
        for line in page(pdfp).split("\n"):
            s = line.rstrip()
            st = s.strip()
            if not st:
                continue
            if re.match(r"^HASIL\s+307,600,000,000", st):
                started = True
            if not started:
                continue
            if "(b) Perbelanjaan Mengurus" in st:
                started = False
                break
            m = re.match(rf"^(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{4,6}})$", s)
            if not m:
                # continuation fragment: pure text, short, belongs to previous data row
                if (rows and not re.search(r"\d", st) and len(st) < 60
                        and not JUNK.match(st) and st != st.upper()):
                    rows[-1][3] = rows[-1][3] + " " + st
                elif rows and not re.search(r"\d", st) and len(st) < 60 and not JUNK.match(st):
                    # all-caps fragment (rare); still a wrap if very short
                    if len(st.split()) <= 3 and st not in REV_L1:
                        rows[-1][3] = rows[-1][3] + " " + st
                continue
            label = m.group(1).strip()
            if not label or JUNK.match(label):
                continue
            nums = [parse_amount(x) for x in re.findall(rf"\(?(?:{NUM}|[–—-])\)?", m.group(2))]
            pct = pct_pri = None
            if len(nums) == 6:
                a_asal, a_disemak, sebenar, pct, pri, pct_pri = nums
            elif len(nums) == 5:
                a_asal, a_disemak, sebenar, pct, pri = nums
            elif len(nums) == 4:
                a_asal, a_disemak, sebenar, pri = nums
            else:
                continue
            if label == "HASIL":
                lvl, l1_, l2_ = 0, None, None
            elif label in REV_L1:  # L1 headers are printed in ALL CAPS
                lvl, l1_, l2_ = 1, label, None
                l1 = label
                l2 = None
            elif label in REV_L2:
                lvl, l1_, l2_ = 2, l1, label
                l2 = label
            else:
                lvl, l1_, l2_ = 3, l1, l2
            rows.append([lvl, l1_, l2_, label, YEAR, a_asal, a_disemak, sebenar, pct, pri, pct_pri, SRC, pdfp, printed, stmt])
    # WP sub-items are not under Cukai Langsung/Tidak Langsung
    for r in rows:
        if r[1] == "HASIL WILAYAH PERSEKUTUAN":
            r[2] = None
    w("fact_revenue.csv",
      ["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
       "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
       "sebenar_prior_rm", "pct_anggaran_prior"] + PROV, rows)


# ---------------------------------------------------------------- 4b. Penyata Akaun Memorandum summary (p77)
def memorandum():
    stmt = "Penyata Akaun Memorandum"
    targets = {
        "Akaun Belum Terima": "MEMORANDUM ASET",
        "Pelaburan": "MEMORANDUM ASET",
        "Jumlah Aset": "MEMORANDUM ASET",
        "Hutang Persekutuan": "MEMORANDUM LIABILITI",
        "Liabiliti Inisiatif Pembiayaan Swasta": "MEMORANDUM LIABILITI",
        "Komitmen Kewangan": "MEMORANDUM LIABILITI",
        "Pelbagai Liabiliti": "MEMORANDUM LIABILITI",
        "Jumlah Liabiliti": "MEMORANDUM LIABILITI",
    }
    rows = []
    for label, nums, _ in grab_rows(page(77), 2, 2):
        lab = re.sub(r"\s+\d+$", "", label.strip())
        if lab in targets:
            vals = [parse_amount(x) for x in nums]
            rows.append([targets[lab], lab, YEAR, vals[0], SRC, 77, 63, stmt])
            rows.append([targets[lab], lab, PRIOR, vals[1], SRC, 77, 63, stmt])
    w("fact_memorandum.csv",
      ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 5. Perbelanjaan Mengurus mengikut Maksud (p85-86?)
def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    for pdfp, printed in [(85, 71), (86, 72)]:
        for line in page(pdfp).split("\n"):
            s = line.rstrip()
            m = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{3,4}})$", s)
            if not m:
                continue
            kind, code, name, numstr = m.groups()
            raw = re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", numstr)
            flagged = any("*" in x for x in raw)
            nums = [parse_amount(x) for x in raw]
            if len(nums) == 4:
                asal, dipinda, sebenar, pct = nums
            else:
                asal, dipinda, sebenar = nums
                pct = None
            rows.append([f"{kind}.{code}", "Tanggungan" if kind == "T" else "Bekalan", name.strip(),
                         YEAR, asal, dipinda, sebenar, pct, flagged, SRC, pdfp, printed, stmt])
    w("fact_opex_maksud.csv",
      ["maksud_code", "jenis_bm", "maksud_name_bm", "year",
       "anggaran_asal_rm", "anggaran_dipinda_rm", "sebenar_rm", "pct_anggaran", "has_footnote"] + PROV, rows)


# ---------------------------------------------------------------- 6. Hutang Persekutuan & Komitmen (p93-94)
def debt():
    stmt = "Nota 10 Memorandum Liabiliti"
    items = {
        "Bil Perbendaharaan": ("Pinjaman Dalam Negeri", "instrument"),
        "Terbitan Pelaburan Kerajaan": ("Pinjaman Dalam Negeri", "instrument"),
        "Sekuriti Kerajaan Malaysia": ("Pinjaman Dalam Negeri", "instrument"),
        "Sukuk": ("Pinjaman Dalam Negeri", "instrument"),
        "Pinjaman Pasaran": ("Pinjaman Luar Negeri", "instrument"),
        "Pinjaman Multilateral": ("Bantuan Luar Negeri", "instrument"),
        "Pinjaman Bilateral": ("Bantuan Luar Negeri", "instrument"),
        "PINJAMAN": ("JUMLAH", "subtotal"),
        "Dalam Negeri": ("Pinjaman Dalam Negeri", "subtotal"),
        "BANTUAN LUAR NEGERI": ("JUMLAH", "subtotal"),
        "HUTANG PERSEKUTUAN": ("JUMLAH", "total"),
        "LIABILITI INISIATIF PEMBIAYAAN SWASTA": ("Liabiliti PFI", "pfi_total"),
        "Pembinaan PFI Sdn. Bhd.": ("Liabiliti PFI", "pfi_company"),
        "MKD Aman Makmur Sdn. Bhd.": ("Liabiliti PFI", "pfi_company"),
        "KOMITMEN JAMINAN": ("Komitmen Kewangan", "commitment_total"),
        "KOMITMEN PAJAKAN KEWANGAN": ("Komitmen Kewangan", "commitment_total"),
        "KOMITMEN BAYARAN BALIK CUKAI": ("Komitmen Kewangan", "commitment_total"),
        "KOMITMEN PAMPASAN": ("Komitmen Kewangan", "commitment_total"),
        "Pampasan Konsesi Lebuhraya": ("Komitmen Pampasan", "commitment_item"),
        "Pampasan Kelewatan Bayaran Balik Cukai Pendapatan": ("Komitmen Pampasan", "commitment_item"),
        "PELBAGAI LIABILITI": ("Pelbagai Liabiliti", "misc_total"),
    }
    rows = []
    for pdfp, printed in [(93, 79), (94, 80), (95, 81)]:
        for label, nums, _ in grab_rows(page(pdfp), 2, 2):
            lab = label.strip()
            if lab in items:
                grp, kind = items[lab]
                if lab == "PELBAGAI LIABILITI" and pdfp != 95:
                    continue
                if lab in ("PINJAMAN", "Dalam Negeri", "BANTUAN LUAR NEGERI",
                           "Pinjaman Multilateral", "Pinjaman Bilateral") and pdfp != 93:
                    continue  # avoid identically-named rows in commitment tables on later pages
                vals = [parse_amount(x) for x in nums]
                rows.append([grp, lab, kind, YEAR, vals[0], SRC, pdfp, printed, stmt])
                rows.append([grp, lab, kind, PRIOR, vals[1], SRC, pdfp, printed, stmt])
    w("fact_debt.csv",
      ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 7. Akaun Amanah Disatukan (p87)
def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    groups = {
        "KUMPULAN WANG AMANAH KERAJAAN": None,
        "Kumpulan Wang Pembangunan": "KUMPULAN WANG AMANAH KERAJAAN",
        "Kumpulan Wang COVID-19": "KUMPULAN WANG AMANAH KERAJAAN",
        "Pelbagai Kumpulan Wang Amanah Kerajaan": "KUMPULAN WANG AMANAH KERAJAAN",
        "KUMPULAN WANG AMANAH AWAM": None,
        "Kumpulan Wang Amanah Am": "KUMPULAN WANG AMANAH AWAM",
        "Kumpulan Wang Amanah Khas": "KUMPULAN WANG AMANAH AWAM",
        "AKAUN DEPOSIT": None,
        "Deposit Am": "AKAUN DEPOSIT",
        "Deposit Pelarasan": "AKAUN DEPOSIT",
        "AKAUN AMANAH DISATUKAN": "JUMLAH",
    }
    rows = []
    for label, nums, _ in grab_rows(page(87), 4, 4):
        lab = label.strip()
        if lab in groups:
            vals = [parse_amount(x) for x in nums]
            parent = groups[lab] or ""
            rows.append([parent, lab, YEAR, vals[0], vals[1], vals[2], vals[3], SRC, 87, 73, stmt])
    w("fact_trust_accounts.csv",
      ["parent_group_bm", "account_bm", "year", "baki_awal_rm", "debit_rm", "kredit_rm", "baki_akhir_rm"] + PROV, rows)


financial_position()
cash_statement()
performance()
revenue()
memorandum()
opex_maksud()
debt()
trust()
