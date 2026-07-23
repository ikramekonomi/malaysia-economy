#!/usr/bin/env python3
"""Extract core fiscal tables from PKKP 2017 text layer (pdftotext -layout).

Adapted from the proven 2018 pipeline. 2017 page anchors (printed = pdf - 11):
position pdf 54, cash 55-56, prestasi 57, memorandum 58, Nota 5 stmt/5(a) pdf
61-62, Nota 5(b) pdf 63, Nota 10 pdf 70, trust pdf 65.
2017 specifics (full-GST era, pre-GE14 ministry structure):
 - Nota 5(a) prints GST items (CBP Import/Tempatan) as the main indirect-tax
   lines PLUS residual old Cukai Jualan / Cukai Perkhidmatan collections and
   the new Cukai Pelancongan (nil anggaran).
 - Cash statement Terimaan Modal has FOUR items (Terimaan Balik Pinjaman /
   Jualan Aset Modal / Pelbagai Terimaan Modal / Jualan Instrumen Kewangan);
   Perbelanjaan Amanah HAS a 'Pelbagai' item (unlike 2018).
 - Penyata Akaun Memorandum prints only 4 lines (no Akaun Belum Terima /
   Jumlah rows / PFI / Komitmen Kewangan -- those start with the 2018 volume).
 - Nota 5(b): 50 maksud (T.01-T.14, B.01-B.64 pre-GE14 list). B.12's sebenar
   prints '**' at line end with the amount WRAPPED to the next line.
 - Nota 10: DN instruments Bil Perbendaharaan/TPK/SKM/Sukuk; LN instrument
   Pinjaman Pasaran; NO PFI liability, NO commitments sections; (b) Pelbagai
   Liabiliti only.
All amounts exact RM as printed. Provenance on every row.
"""
import csv
import os
import re

YEAR = 2017
PRIOR = 2016
SRC = "2017_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2017"
os.makedirs(OUT, exist_ok=True)

pages = open("/home/claude/pkkp/work/2017/full.txt", encoding="utf-8").read().split("\f")


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


def strip_margin(s):
    """Remove the printed page number set in the side margin (leading or
    trailing bare 1-3 digit integer separated by wide gaps)."""
    s = re.sub(r"^(\s*)\d{1,3}(\s{3,})", r"\1\2", s)
    s = re.sub(r"(\s{6,})\d{1,3}\s*$", "", s)
    return s


def grab_rows(text, min_nums, max_nums=None):
    for line in text.split("\n"):
        s = strip_margin(line.rstrip())
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

# ---------------------------------------------------------------- 1. Penyata Kedudukan Kewangan (pdf 54, printed 43)
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
    for label, nums, _ in grab_rows(page(54), 2, 3):
        lab = label.strip()
        key = re.sub(r"\s+\d+$", "", lab)
        if key in targets:
            section, nota = targets[key]
            vals = [parse_amount(x) for x in nums]
            if len(vals) == 3:  # first token is the Nota number
                vals = vals[1:]
            rows.append([section, key, nota, YEAR, vals[0], SRC, 54, 43, stmt])
            rows.append([section, key, nota, PRIOR, vals[1], SRC, 54, 43, stmt])
    w("fact_financial_position.csv",
      ["section", "line_item_bm", "nota", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 2. Penyata Penerimaan dan Pembayaran Wang Tunai (pdf 55-56)
def cash_statement():
    stmt = "Penyata Penerimaan dan Pembayaran Wang Tunai"
    spec = [
        ("TERIMAAN", "Hasil", ["Hasil Cukai", "Hasil Bukan Cukai", "Terimaan Bukan Hasil", "Hasil Wilayah Persekutuan"]),
        ("TERIMAAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("TERIMAAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("TERIMAAN", "Terimaan Modal", ["Terimaan Balik Pinjaman", "Jualan Aset Modal", "Pelbagai Terimaan Modal", "Jualan Instrumen Kewangan"]),
        ("TERIMAAN", "Terimaan Amanah", ["Inisiatif Pembiayaan Swasta", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"]),
        ("BAYARAN", "Perbelanjaan Mengurus", ["Emolumen", "Perkhidmatan dan Bekalan", "Aset", "Pemberian dan Kenaan Bayaran Tetap", "Perbelanjaan-perbelanjaan Lain"]),
        ("BAYARAN", "Perbelanjaan Pembangunan", ["Langsung", "Pinjaman"]),
        ("BAYARAN", "Pinjaman", ["Dalam Negeri", "Luar Negeri"]),
        ("BAYARAN", "Bantuan Luar Negeri", ["Pinjaman Multilateral", "Pinjaman Bilateral"]),
        ("BAYARAN", "Perbelanjaan Modal", ["Pembelian Instrumen Kewangan"]),
        ("BAYARAN", "Perbelanjaan Amanah", ["Inisiatif Pembiayaan Swasta", "Aktiviti Pembangunan Khas Pembiayaan Swasta", "Pelbagai"]),
    ]
    totals = ["Jumlah Terimaan", "Jumlah Bayaran", "Tambahan/(Kurangan) Wang Tunai",
              "Wang Tunai Pada 1 Januari", "WANG TUNAI PADA 31 DISEMBER"]
    rows = []
    for pdfp, printed in [(55, 44), (56, 45)]:
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


# ---------------------------------------------------------------- 3. Penyata Prestasi Kewangan (pdf 57, printed 46)
def performance():
    stmt = "Penyata Prestasi Kewangan"
    txt = page(57)
    rows = []
    pat = {
        "HASIL": "revenue",
        "Belanja Mengurus": "opex",
        "LEBIHAN/(KURANGAN) HASIL": "current_balance",
        "Belanja Pembangunan": "devex",
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
                rows.append([lab, pat[lab], YEAR, "anggaran", vals[0], SRC, 57, 46, stmt])
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[1], SRC, 57, 46, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[2], SRC, 57, 46, stmt])
            elif len(vals) == 2:
                rows.append([lab, pat[lab], YEAR, "sebenar", vals[0], SRC, 57, 46, stmt])
                rows.append([lab, pat[lab], PRIOR, "sebenar", vals[1], SRC, 57, 46, stmt])
    # financing rows print on a single line with a leading Nota ref (6 / 7 / none)
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
                rows.append([full_label, code, YEAR, "sebenar", vals[0], SRC, 57, 46, stmt])
                rows.append([full_label, code, PRIOR, "sebenar", vals[1], SRC, 57, 46, stmt])
    w("fact_financial_performance.csv",
      ["line_item_bm", "line_code", "year", "basis", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 4. Hasil mengikut penjenisan (pdf 61-62)
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
    for pdfp, printed in [(61, 50), (62, 51)]:
        for line in page(pdfp).split("\n"):
            s = line.rstrip()
            # rotated sidebar overprint at line end ('NOTA KEPADA PENYATA KEWANGAN')
            s = re.sub(r"(\S)\s{4,}[A-Z][A-Z ]{9,}$", r"\1", s)
            st = s.strip()
            if not st:
                continue
            # 5(a) table starts with the HASIL row carrying the Anggaran Asal column
            if re.match(r"^HASIL\s+218,975,845,000", st):
                started = True
            if not started:
                continue
            if "(b) Perbelanjaan Mengurus" in st:
                started = False
                break
            # 2017: Cukai Langsung / Cukai Tak Langsung print as BARE group
            # headers (no value columns) -- set the L2 state, never a wrap
            if st in REV_L2:
                l2 = st
                continue
            m = re.match(rf"^(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{4,6}})$", s)
            if not m:
                if (rows and not re.search(r"\d", st) and len(st) < 60
                        and not JUNK.match(st) and st not in REV_L1):
                    # wrap continuation; collapse overprint-doubled words
                    prev_words = rows[-1][3].split()
                    for wd in st.split():
                        if not prev_words or prev_words[-1] != wd:
                            prev_words.append(wd)
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
    for r in rows:
        if r[1] == "HASIL WILAYAH PERSEKUTUAN":
            r[2] = None
    w("fact_revenue.csv",
      ["level", "category_l1_bm", "category_l2_bm", "item_bm", "year",
       "anggaran_asal_rm", "anggaran_disemak_rm", "sebenar_rm", "pct_anggaran",
       "sebenar_prior_rm", "pct_anggaran_prior"] + PROV, rows)


# ---------------------------------------------------------------- 4b. Penyata Akaun Memorandum summary (pdf 58, printed 47)
def memorandum():
    stmt = "Penyata Akaun Memorandum"
    targets = {
        "Pinjaman dan Pendahuluan Boleh Dituntut": "MEMORANDUM ASET",
        "Pelaburan": "MEMORANDUM ASET",
        "Hutang Persekutuan": "MEMORANDUM LIABILITI",
        "Pelbagai Liabiliti": "MEMORANDUM LIABILITI",
    }
    rows = []
    for label, nums, _ in grab_rows(page(58), 2, 2):
        lab = re.sub(r"\s+\d+$", "", label.strip())
        if lab in targets:
            vals = [parse_amount(x) for x in nums]
            rows.append([targets[lab], lab, YEAR, vals[0], SRC, 58, 47, stmt])
            rows.append([targets[lab], lab, PRIOR, vals[1], SRC, 58, 47, stmt])
    w("fact_memorandum.csv",
      ["section", "line_item_bm", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 5. Perbelanjaan Mengurus mengikut Maksud (pdf 63, printed 52)
def opex_maksud():
    stmt = "Nota 5(b) Perbelanjaan Mengurus Mengikut Maksud"
    rows = []
    pending = None  # (kind, code, name, raw_tokens) for the wrapped B.12 '**' row
    for pdfp, printed in [(63, 52)]:
        for line in page(pdfp).split("\n"):
            s = strip_margin(line.rstrip())
            if pending is not None:
                # value continuation line: pure numbers completing the wrapped row
                mc = re.match(rf"^\s*((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{1,2}})$", s)
                if mc:
                    kind, code, name, raw = pending
                    raw = raw + re.findall(rf"\*?\(?(?:{NUM}|[–—-])\)?", mc.group(1))
                    flagged = True  # the wrap is caused by the printed '**'
                    nums = [parse_amount(x) for x in raw]
                    if len(nums) == 4:
                        asal, dipinda, sebenar, pct = nums
                    else:
                        asal, dipinda, sebenar = nums
                        pct = None
                    rows.append([f"{kind}.{code}", "Tanggungan" if kind == "T" else "Bekalan",
                                 name.strip(), YEAR, asal, dipinda, sebenar, pct, flagged,
                                 SRC, pdfp, printed, stmt])
                    pending = None
                    continue
                if s.strip():
                    pending = None  # not a continuation after all
            sn = s.replace("***", "*").replace("**", "*")  # normalise footnotes
            # wrapped maksud-name continuation ('dan Kepenggunaan' under B.25,
            # 'dan Kerajaan Tempatan' under B.43): label-only lowercase line
            if rows and re.fullmatch(r"\s*(dan|kepada|untuk)\s+[A-Za-z ,./-]+", s or ""):
                rows[-1][2] = (rows[-1][2] + " " + s.strip()).strip()
                continue
            m = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s+((?:\*?\(?(?:{NUM}|[–—-])\)?\s*){{3,4}})$", sn)
            if not m:
                # wrapped-value row: label + 2 values + trailing '**' marker
                mw = re.match(rf"^\s*([TB])\.\s?(\d{{2,3}})\s+(.*?)\s+((?:\(?(?:{NUM})\)?\s+){{2}})\*{{1,3}}\s*$",
                              s)
                if mw:
                    kind, code, name, numstr = mw.groups()
                    pending = (kind, code, name,
                               re.findall(rf"\(?(?:{NUM})\)?", numstr))
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


# ---------------------------------------------------------------- 6. Nota 10 Memorandum Liabiliti (pdf 70, printed 59)
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
        "PELBAGAI LIABILITI": ("Pelbagai Liabiliti", "misc_total"),
    }
    rows = []
    for pdfp, printed in [(70, 59)]:
        for label, nums, _ in grab_rows(page(pdfp), 2, 2):
            lab = label.strip()
            if lab in items:
                grp, kind = items[lab]
                vals = [parse_amount(x) for x in nums]
                rows.append([grp, lab, kind, YEAR, vals[0], SRC, pdfp, printed, stmt])
                rows.append([grp, lab, kind, PRIOR, vals[1], SRC, pdfp, printed, stmt])
    w("fact_debt.csv",
      ["group_bm", "item_bm", "kind", "year", "amount_rm"] + PROV, rows)


# ---------------------------------------------------------------- 7. Akaun Amanah Disatukan (pdf 65, printed 54)
def trust():
    stmt = "Nota 7 Akaun Amanah Disatukan"
    groups = {
        "KUMPULAN WANG AMANAH KERAJAAN": None,
        "Kumpulan Wang Pembangunan": "KUMPULAN WANG AMANAH KERAJAAN",
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
    txt = re.sub(r"(\d)-(\s*$)", r"\1\2", page(65), flags=re.M)
    for label, nums, _ in grab_rows(txt, 4, 4):
        lab = label.strip()
        if lab in groups:
            vals = [parse_amount(x) for x in nums]
            parent = groups[lab] or ""
            rows.append([parent, lab, YEAR, vals[0], vals[1], vals[2], vals[3], SRC, 65, 54, stmt])
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
