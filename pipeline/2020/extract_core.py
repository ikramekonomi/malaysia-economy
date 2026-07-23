#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2020 text layer (pdftotext -layout).

Adapted from the proven 2022 pipeline. 2020 page anchors (printed = pdf - 16):
position pdf 67, cash 68-69, prestasi 70, memorandum 71, Nota 5 pdf 77-79,
Nota 10 spans pdf 87-89 (PFI shares pdf 87 with the debt table), trust pdf 81.
2020 specifics:
 - COVID-19 fund ESTABLISHED this year (Akta 830, gazetted 26.10.2020);
   Belanja KW COVID-19 sebenar RM38,019,238,631 (cash outflow 37,869,238,631 --
   RM150,000,000 adjustment to KWA Tabung Bantuan Bencana Negara per Nota 8(b)).
 - Prestasi table prints a single 'Anggaran' column (the revised estimate).
 - Financing rows print on ONE line each with a leading Nota ref.
 - Nota 5(a) L2 category prints 'Cukai Tak Langsung' (not 'Tidak').
 - Nota 5(b) rows are 'T. 01' style with '**'/'***' footnotes.
 - Cash statement Terimaan/Perbelanjaan Amanah items are Inisiatif Pembiayaan
   Swasta / Aktiviti Pembangunan Khas Pembiayaan Swasta / Pelbagai.
 - Trust table: KWAA prints Khas before Am; COVID-19 fund row first appears.
All amounts in RM (exact as printed). Provenance on every row.
"""
import csv
import os
import re

YEAR = 2020
PRIOR = 2019
SRC = "2020_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2020"
os.makedirs(OUT, exist_ok=True)

pages = open("/home/claude/pkkp/work/2020/full.txt", encoding="utf-8").read().split("\f")


def page(n):
    return pages[n - 1]


NUM = r"[\d,]+(?:\.\d+)?"


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def grab_rows(text, min_nums, max_nums=None):
    for line in text.split("\n"):
        s = line.rstrip()
        if not s.strip():
            continue
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

# ---------------------------------------------------------------- 1. Penyata Kedudukan Kewangan (pdf 67, printed 51)
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
    for label, nums, _ in grab_rows(page(67), 2, 3):
        lab = label.strip()
        key = re.sub(r"\s+\d+$", "", lab)
        if key in targets:
            section, nota = targets[key]
            vals = [parse_amount(x) for x in nums]
            if len(vals) == 3:  # first token is the Nota number
                vals = vals[1:]
            rows.append([section, key, nota, YEAR, vals[0], SRC, 67, 51, stmt])
            rows.append([section, key, nota, PRIOR, vals[1], SRC, 67, 51, stmt])
    w("fact_financial_position.csv",
      ["section", "line_item_bm", "nota", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 2. Penyata Penerimaan dan Pembayaran Wang Tunai (pdf 68-69)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    spec = [
        ("TERIMAAN", "Hasil", ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"]),
        ("TERIMAAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("TERIMAAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("TERIMAAN", "Terimaan Modal", ["Terimaan Balik Pinjaman", "Jualan Aset Modal", "Pelbagai Terimaan", "Jualan Instrumen Kewangan"]),
        ("TERIMAAN", "Terimaan Amanah", ["Inisiatif Pembiayaan Swasta", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"]),
        ("BAYARAN", "Perbelanjaan Mengurus", ["Emolumen", "Perkhidmatan dan Bekalan", "Aset", "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"]),
        ("BAYARAN", "Perbelanjaan Pembangunan", ["Langsung", "Pinjaman"]),
        ("BAYARAN", "Perbelanjaan Kumpulan Wang COVID-19", ["Perbelanjaan COVID-19"]),
        ("BAYARAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("BAYARAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("BAYARAN", "Perbelanjaan Modal", ["Pembelian Instrumen Kewangan"]),
        ("BAYARAN", "Perbelanjaan Amanah", ["Inisiatif Pembiayaan Swasta", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"]),
    ]
    totals = ["Jumlah Terimaan", "Jumlah Bayaran", "Tambahan/(Kurangan) Wang Tunai",
              "Wang Tunai Pada 1 Januari", "WANG TUNAI PADA 31 DISEMBER"]
    rows = []
    for pdfp, printed in [(68, 52), (69, 53)]:
        txt = page(pdfp)
        lines = txt.split("\n")
        flow = None
        cat = None
        for line in lines:
            s = line.strip()
            if s in ("TERIMAAN", "BAYARAN"):
                flow = s
                continue
            if s.startswith("Nota:") or s.startswith("Nota :") or s.startswith("--- "):
                continue
            base = re.sub(r"\s+8$|\s+\d$", "", s)  # strip nota refs
            for f, c, items in spec:
                if f == flow and (base == c or s == c):
                    cat = c
            m = re.match(rf"^(.*?)\s+((?:\*{{0,2}}\(?(?:{NUM}|[–—-])\)?\s*){{1,4}})$", line.rstrip())
            if not m:
                continue
            label = re.sub(r"\s+\d$", "", m.group(1).strip())
            nums = [parse_amount(x) for x in re.findall(rf"\(?(?:{NUM}|[–—-])\)?", m.group(2))]
            item_match = None
            for f, c, items in spec:
                if f != flow:
                    continue
                for it in items:
                    if label == it:
                        item_match = (f, c, it)
            if item_match and cat and item_match[1] == cat:
                f, c, it = item_match
                if len(nums) == 4:
                    cur, pri = nums[0], nums[2]
                elif len(nums) == 2:
                    cur, pri = nums
                elif len(nums) == 3:
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


# ---------------------------------------------------------------- 3. Penyata Prestasi Kewangan (pdf 70, printed 54)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    txt = page(70)
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
                rows.append([lab, pat[lab], YEAR, "anggaran", vals[0], SRC, 70, 54, stmt])
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[1], SRC, 70, 54, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[2], SRC, 70, 54, stmt])
            elif len(vals) == 2:
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[0], SRC, 70, 54, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[1], SRC, 70, 54, stmt])
    # 2020 volume prints each financing row on a single line with a leading Nota ref
    fin = [
        ("Pinjaman dan Bantuan Luar Negeri", "financing_net_borrowing"),
        ("Terimaan Balik Pinjaman dan Pelbagai Terimaan", "financing_capital_receipts"),
        ("Perubahan Tunai, Pelaburan dan Amanah", "financing_cash_inv_trust_change"),
    ]
    for full_label, code in fin:
        for label, nums, _ in grab_rows(txt, 2, 3):
            if label.strip() == full_label:
                vals = [parse_amount(x) for x in nums]
                vals = [v for v in vals if abs(v) >= 100]  # drop stray Nota ref
                rows.append([full_label, code, YEAR, "sebenar", vals[0], SRC, 70, 54, stmt])
                rows.append([full_label, code, PRIOR, "sebenar", vals[1], SRC, 70, 54, stmt])
    w("fact_financial_performance.csv",
      ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 4. Hasil mengikut penjenisan (pdf 77-78)
REV_L1 = ["HASIL CUKAI", "HASIL BUKAN CUKAI", "TERIMAAN BUKAN HASIL", "HASIL WILAYAH PERSEKUTUAN"]
REV_L2 = ["Cukai Langsung", "Cukai Tak Langsung"]


JUNK = re.compile(
    r"^(RM|Anggaran|Asal|Disemak|Sebenar|% ?Anggaran|\(disambung\)|\(sambungan\)|"
    r"NOTA\s+KEPADA|PENYATA\s+KEWANGAN|BAGI\s+TAHUN|KEWANGAN|NOT A|B AG I|\d+$|[ivxl]+$)"
)


def revenue():
    stmt = "Nota 5(a) Hasil Mengikut Penjenisan"
    rows = []
    l1 = l2 = None
    started = False
    for pdfp, printed in [(77, 61), (78, 62)]:
        for line in page(pdfp).split("\n"):
            s = line.rstrip()
            st = s.strip()
            if not st:
                continue
            # 5(a) table starts with the HASIL row carrying the Anggaran Asal column
            if re.match(r"^HASIL\s+244,530,029,000", st):
                started = True
            if not started:
                continue
            if "(b) Perbelanjaan Mengurus" in st:
                started = False
                break
            m = re.match(rf"^(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{4,6}})$", s)
            if not m:
                if (rows and not re.search(r"\d", st) and len(st) < 60
                        and not JUNK.match(st) and st not in REV_L1):
                    # wrap continuation; collapse overprint-doubled words
                    # (e.g. 'Wilayah / Wilayah Persekutuan / Persekutuan')
                    prev_words = rows[-1][3].split()
                    for wd in st.split():
                        if not prev_words or prev_words[-1] != wd:
                            prev_words.append(wd)
                        # drop exact immediate duplicate (overprint)
                    rows[-1][3] = " ".join(prev_words)
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
            elif label in REV_L1:
                lvl, l1_, l2_ = 1, label, None
                l1 = label
                l2 = None
            elif label in REV_L2:
                lvl, l1_, l2_ = 2, l1, label
                l2 = label
            else:
                lvl, l1_, l2_ = 3, l1, l2
            rows.append([lvl, l1_, l2_, label, YEAR, a_asal, a_disemak, sebenar, pct, pri, pct_pri, SRC, pdfp, printed, stmt])
    # targeted repair of the split-label pair on pdf 78 (verified against the print):
    # 'Terimaan daripada Agensi-agensi' wraps 'Kerajaan' AND the next item's label
    # 'Terimaan / Kerajaan Lain' wraps its FIRST word onto a line of its own before
    # the numbers line, so the naive wrap-joiner glues 'Terimaan' to the previous item.
    for i, r in enumerate(rows):
        if r[3].startswith("Terimaan daripada Agensi-agensi") and r[3].endswith(" Terimaan"):
            r[3] = r[3][: -len(" Terimaan")]
            if i + 1 < len(rows) and rows[i + 1][3] == "Kerajaan Lain":
                rows[i + 1][3] = "Terimaan Kerajaan Lain"
    for r in rows:
        if r[1] == "HASIL WILAYAH PERSEKUTUAN":
            r[2] = None
    w("fact_revenue.csv",
      ["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
       "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
       "sebenar_prior_rm", "pct_anggaran_prior"] + PROV, rows)


# ---------------------------------------------------------------- 4b. Penyata Akaun Memorandum summary (pdf 71, printed 55)
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
    for label, nums, _ in grab_rows(page(71), 2, 2):
        lab = re.sub(r"\s+\d+$", "", label.strip())
        if lab in targets:
            vals = [parse_amount(x) for x in nums]
            rows.append([targets[lab], lab, YEAR, vals[0], SRC, 71, 55, stmt])
            rows.append([targets[lab], lab, PRIOR, vals[1], SRC, 71, 55, stmt])
    w("fact_memorandum.csv",
      ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 5. Perbelanjaan Mengurus mengikut Maksud (pdf 79, printed 63)
def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    for pdfp, printed in [(79, 63)]:
        for line in page(pdfp).split("\n"):
            s = line.rstrip().replace("***", "*").replace("**", "*")  # normalise footnotes
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


# ---------------------------------------------------------------- 6. Nota 10 Memorandum Liabiliti (pdf 87-89)
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
        "PELBAGAI LIABILITI": ("Pelbagai Liabiliti", "misc_total"),
    }
    rows = []
    for pdfp, printed in [(87, 71), (88, 72), (89, 73)]:
        for label, nums, _ in grab_rows(page(pdfp), 2, 2):
            lab = label.strip()
            if lab in items:
                grp, kind = items[lab]
                if lab == "PELBAGAI LIABILITI" and pdfp != 89:
                    continue
                if lab in ("PINJAMAN", "Dalam Negeri", "BANTUAN LUAR NEGERI",
                           "Pinjaman Multilateral", "Pinjaman Bilateral") and pdfp != 87:
                    continue  # avoid identically-named rows in other tables
                if kind in ("commitment_total", "commitment_item") and pdfp != 88:
                    continue
                vals = [parse_amount(x) for x in nums]
                rows.append([grp, lab, kind, YEAR, vals[0], SRC, pdfp, printed, stmt])
                rows.append([grp, lab, kind, PRIOR, vals[1], SRC, pdfp, printed, stmt])
    w("fact_debt.csv",
      ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 7. Akaun Amanah Disatukan (pdf 81, printed 65)
def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    groups = {
        "KUMPULAN WANG AMANAH KERAJAAN": None,
        "Kumpulan Wang Pembangunan": "KUMPULAN WANG AMANAH KERAJAAN",
        "Kumpulan Wang COVID-19": "KUMPULAN WANG AMANAH KERAJAAN",
        "Pelbagai Kumpulan Wang Amanah Kerajaan": "KUMPULAN WANG AMANAH KERAJAAN",
        "KUMPULAN WANG AMANAH AWAM": None,
        "Kumpulan Wang Amanah Khas": "KUMPULAN WANG AMANAH AWAM",
        "Kumpulan Wang Amanah Am": "KUMPULAN WANG AMANAH AWAM",
        "AKAUN DEPOSIT": None,
        "Deposit Am": "AKAUN DEPOSIT",
        "Deposit Pelarasan": "AKAUN DEPOSIT",
        "AKAUN AMANAH DISATUKAN": "JUMLAH",
    }
    rows = []
    # glyph repair: strip a stray '-' glued to a trailing amount if present
    txt = re.sub(r"(\d)-(\s*$)", r"\1\2", page(81), flags=re.M)
    for label, nums, _ in grab_rows(txt, 4, 4):
        lab = label.strip()
        if lab in groups:
            vals = [parse_amount(x) for x in nums]
            parent = groups[lab] or ""
            rows.append([parent, lab, YEAR, vals[0], vals[1], vals[2], vals[3], SRC, 81, 65, stmt])
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
