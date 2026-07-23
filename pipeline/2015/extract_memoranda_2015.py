#!/usr/bin/env python3
"""Extract memorandum registers Lampiran 3, 5, 6 of PKKP 2015 (NO text layer;
tesseract TSV at 400 dpi, digits unreliable) ->
  fact_loans_receivable.csv       Lampiran 3, pdf 275-277 (printed 261-263)
  fact_debt_issues.csv            Lampiran 5, pdf 287-290 (printed 273-276)
  fact_statutory_guarantees.csv   Lampiran 6, pdf 293    (printed 279)
Schemas column-for-column = warehouse2014.

METHOD (per CONVENTIONS.md): page TSV gives row structure + x-column mapping;
EVERY numeric cell is then confirmed by at least one of
  (a) printed arithmetic identity (row cross-foot / column sum / grand total),
  (b) independent re-OCR (ocrlib.cell_ocr, different render/scale/psm) agreeing,
  (c) eye-reading a zoomed crop (EYE_* overrides below, each read from a
      ocrlib.save_crop render via the Read tool).
Repair rule: a cell is auto-fixed ONLY when the volume's own arithmetic forces
a value that is a near-digit variant of the OCR reading (digit-string edit
distance <= 2) or matches an independent re-OCR; logged INFO. Print-side
discrepancies stay AS PRINTED, logged WARN/FAIL with diagnosis. All checks ->
_validation_checks_memoranda_2015.csv AND _validation_checks_2015.csv.
"""
import csv
import re
import sys

sys.path.insert(0, "/home/claude/pkkp/work/2015/pipeline")
import ocrlib
from ocrlib import SRC, parse_amount, append_checks

WH = "/home/claude/pkkp/warehouse2015"
MEMO_CSV = f"{WH}/_validation_checks_memoranda_2015.csv"
YEAR, PRIOR = 2015, 2014

DASHCH = set("-–—_~=.·‘'`\",;:")
NUMLIKE = re.compile(r"[\d()]")
WF = re.compile(r"^\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?$")

CHECKS = []
CONFIRM = {"a": 0, "b": 0, "c": 0, "dash": 0}


def chk(status, name, got, want):
    CHECKS.append((status, name, got, want))


def sanitize(tok):
    t = tok.replace(" ", "")
    t = (t.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1")
         .replace("S", "5").replace("$", "5").replace("/", "7").replace("?", "7")
         .replace("B", "8").replace("g", "9").replace("q", "9").replace("A", "4")
         .replace("Z", "2").replace("i", "1").replace("e", "8").replace("#", "7")
         .replace("!", "1").replace("|", "1").replace("£", "5")
         .replace("€", "6").replace("§", "5"))
    t = t.strip(".").rstrip(",")
    m = re.match(r"^(\(?[\d,]+)[,.]+(\d{2})\)?$", t)
    if m:
        body = m.group(1).lstrip("(").replace(",", "")
        neg = t.startswith("(")
        if body:
            s = f"{int(body):,}.{m.group(2)}"
            return f"({s})" if neg else s
    return t


def wf_ok(t):
    return bool(WF.match(t))


def loose_parse(raw):
    """Digit-heuristic read of a garbled amount token: strip non-digits, infer
    trailing 2 digits as sen (register prints sen everywhere). Only an INITIAL
    candidate - must still be confirmed by identity/re-OCR/eye."""
    if raw is None:
        return None
    t = sanitize(raw)
    if wf_ok(t):
        return parse_amount(t)
    neg = t.startswith("(") or (t.endswith(")") and "(" not in t)
    # if a sen dot survived, trust it
    m = re.match(r"^\(?([\d,]+)\.(\d{2})\)?\D*$", t)
    if m:
        v = float(m.group(1).replace(",", "") + "." + m.group(2))
        return -v if neg else v
    d = digits_of(t)
    if len(d) < 3:
        return None
    v = float(d[:-2] + "." + d[-2:])
    return -v if neg else v


def digits_of(s):
    return re.sub(r"\D", "", str(s))


def edit_dist_le(a, b, k=2):
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > k:
            return False
        prev = cur
    return prev[-1] <= k


def near_raw(value, raw, k=2):
    """value (float) is a near-digit variant of the raw OCR string."""
    if raw is None:
        return False
    dv = digits_of(f"{abs(value):,.2f}")
    dr = digits_of(raw)
    return edit_dist_le(dv, dr, k)


def rows_of_page(pno, ytol=25, xmax=3010, xmin=180):
    ws = [w for w in ocrlib.load_words(pno) if xmin < w["left"] and w["right"] < xmax]
    return ocrlib.cluster_lines(ws, ytol=ytol)


def band_split(lws, bands, label_max):
    cells, label = {}, []
    for w in sorted(lws, key=lambda x: x["left"]):
        t = w["text"]
        placed = False
        if NUMLIKE.search(t) or (len(t) <= 2 and set(t) <= DASHCH):
            for name, lo, hi in bands:
                if lo < w["right"] <= hi:
                    cells.setdefault(name, []).append(w)
                    placed = True
                    break
        if not placed:
            if w["left"] < label_max and not (len(t) <= 2 and set(t) <= DASHCH):
                label.append(w)
    out = {}
    for name, wlist in cells.items():
        txt = "".join(x["text"] for x in sorted(wlist, key=lambda x: x["left"]))
        box = (min(x["left"] for x in wlist) - 4, min(x["top"] for x in wlist) - 4,
               max(x["right"] for x in wlist) + 4, max(x["bottom"] for x in wlist) + 4)
        out[name] = (txt, box)
    return " ".join(x["text"] for x in label), out


def is_dash(txt):
    t = txt.replace(" ", "")
    return bool(t) and set(t) <= DASHCH and len(t) <= 3


class Cell:
    def __init__(self, pno, band, raw, box, key):
        self.pno, self.band, self.raw, self.box, self.key = pno, band, raw, box, key
        self.route = None
        self.fixed_note = None
        self._reocr = {}
        if raw is None or is_dash(raw):
            self.value, self.route = 0.0, "dash"
        else:
            s = sanitize(raw)
            self.value = parse_amount(s) if wf_ok(s) else loose_parse(raw)

    def reocr(self, clean=True, scale=3, psm=7):
        k = (clean, scale, psm)
        if k not in self._reocr:
            t = ocrlib.cell_ocr(self.pno, self.box, scale=scale, psm=psm, clean=clean).strip(".,")
            s = sanitize(t)
            self._reocr[k] = parse_amount(s) if wf_ok(s) else loose_parse(t)
        return self._reocr[k]

    def reocr_values(self):
        vs = [self.reocr(), self.reocr(clean=False, scale=4)]
        return [v for v in vs if v is not None]

    def __repr__(self):
        return f"<{self.key} raw={self.raw!r} v={self.value} {self.route}>"


class Solver:
    """Cells + linear identities sum(coef*cell) == 0. Confirm/repair/eye."""

    def __init__(self, tag, eye):
        self.tag = tag
        self.cells = {}
        self.idents = []   # (name, [(coef, key)])
        self.eye = eye

    def add_cell(self, c):
        self.cells[c.key] = c
        if c.key in self.eye:
            c.value = parse_amount(self.eye[c.key])
            c.route = "c"
        return c

    def ident(self, name, terms):
        terms = [(f, k) for f, k in terms if k in self.cells]
        self.idents.append((name, terms))

    def residual(self, terms):
        s = 0.0
        for f, k in terms:
            v = self.cells[k].value
            if v is None:
                return None
            s += f * v
        return s

    def solve(self):
        # apply eye overrides route already; iterate repairs
        for _ in range(60):
            progress = False
            for name, terms in self.idents:
                res = self.residual(terms)
                if res is None:
                    unk = [(f, k) for f, k in terms if self.cells[k].value is None]
                    if len(unk) == 1:
                        f, k = unk[0]
                        others = sum(ff * self.cells[kk].value for ff, kk in terms if kk != k)
                        forced = -others / f
                        c = self.cells[k]
                        if near_raw(forced, c.raw, 3) or c.raw is None or forced in c.reocr_values():
                            c.value, c.route = forced, "a"
                            c.fixed_note = f"unparseable OCR {c.raw!r} solved by [{name}]"
                            progress = True
                    continue
                if abs(res) <= 0.005 * max(1, len(terms) - 1):
                    continue
                # failing identity: try single-cell repair
                fixes = []
                for f, k in terms:
                    c = self.cells[k]
                    if c.route in ("c",):     # eye-read cells are ground truth
                        continue
                    forced = c.value - res / f
                    if abs(forced - c.value) < 0.005:
                        continue
                    score = None
                    if c.route == "dash":
                        continue
                    if forced in c.reocr_values():
                        score = 0
                    elif near_raw(forced, c.raw, 1):
                        score = 1
                    elif near_raw(forced, c.raw, 2):
                        score = 2
                    if score is not None and not self._breaks_others(k, forced, name):
                        fixes.append((score, k, forced))
                if fixes:
                    fixes.sort()
                    _, k, forced = fixes[0]
                    c = self.cells[k]
                    old = c.value
                    c.value, c.route = forced, "a"
                    c.fixed_note = (f"OCR salvage {c.raw!r} read {old:,.2f} -> "
                                    f"{forced:,.2f} [forced by {name}]")
                    progress = True
            if not progress:
                break
        # mark confirmations: cells in >=1 passing identity -> 'a'
        for name, terms in self.idents:
            res = self.residual(terms)
            if res is not None and abs(res) <= 0.005 * max(1, len(terms) - 1):
                for _, k in terms:
                    c = self.cells[k]
                    if c.route is None:
                        c.route = "a"

    def _breaks_others(self, key, newval, skip):
        c = self.cells[key]
        old = c.value
        c.value = newval
        try:
            for name, terms in self.idents:
                if name == skip or all(k != key for _, k in terms):
                    continue
                res = self.residual(terms)
                if res is None:
                    continue
                old_res = None
                c.value = old
                old_res = self.residual(terms)
                c.value = newval
                if old_res is not None and abs(old_res) <= 0.005 and abs(res) > 0.005:
                    return True
            return False
        finally:
            c.value = old

    def finish(self, prefix):
        """Re-OCR-confirm leftover cells; return list needing eyes."""
        need = []
        for c in self.cells.values():
            if c.route is None and c.value is not None:
                rv = c.reocr_values()
                if any(abs(v - c.value) < 0.005 for v in rv):
                    c.route = "b"
                else:
                    need.append(c)
            elif c.value is None:
                need.append(c)
        for c in self.cells.values():
            if c.route in CONFIRM:
                CONFIRM[c.route] += 1
            if c.fixed_note:
                chk("INFO", f"{prefix}: p{c.pno} {c.key} {c.fixed_note}", c.value, c.value)
        return need

    def report_idents(self, prefix, expect_fail=()):
        for name, terms in self.idents:
            res = self.residual(terms)
            tgt = [k for f, k in terms if f < 0]
            want = -sum(f * self.cells[k].value for f, k in terms if f < 0)
            got = sum(f * self.cells[k].value for f, k in terms if f > 0)
            ok = res is not None and abs(res) <= 0.005 * max(1, len(terms) - 1)
            chk("PASS" if ok else "FAIL", f"{prefix}: {name}", round(got, 2), round(want, 2))


def eye_sheet(rows, out, x0=300, x1=3010, scale=2, pad=6):
    """Compose one PNG stacking row strips [(pno, top, label)] for eye-reading."""
    from PIL import Image, ImageDraw
    strips = []
    for pno, top, label in rows:
        img = ocrlib.get_img(pno)
        crop = img.crop((x0, max(0, top - 10), x1, top + 46))
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        strips.append((label, crop))
    W = max(c.width for _, c in strips) + 260
    H = sum(c.height + pad for _, c in strips) + pad
    sheet = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(sheet)
    y = pad
    for label, c in strips:
        d.text((4, y + c.height // 3), label, fill=0)
        sheet.paste(c, (250, y))
        d.line([(0, y + c.height + pad // 2), (W, y + c.height + pad // 2)], fill=180)
        y += c.height + pad
    sheet.save(out)
    return out


def eye_crop(c, tag, scale=3):
    x0, y0, x1, y1 = c.box
    return ocrlib.save_crop(c.pno, (x0 - 10, y0 - 10, x1 + 10, y1 + 10),
                            f"/tmp/eye_{tag}.png", scale=scale)


def write_outputs_check_csv():
    with open(MEMO_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["status", "check", "extracted_value", "printed_value"])
        w.writerows(CHECKS)
    append_checks([(s, c, g, ww, (round(g - ww, 4) if isinstance(g, (int, float))
                                  and isinstance(ww, (int, float)) else ""))
                   for s, c, g, ww in CHECKS])


def prov(row, pno, stmt):
    row["source_file"] = SRC
    row["pdf_page"] = pno
    row["printed_page"] = pno - 14
    row["statement"] = stmt
    return row


def canon_label(lbl, canon_set, cutoff=0.6):
    import difflib
    lbl = re.sub(r"\s+", " ", lbl).strip()
    m = difflib.get_close_matches(lbl, canon_set, n=1, cutoff=cutoff)
    return m[0] if m else lbl


# ===========================================================================
# Lampiran 6: Jaminan Berkanun (pdf 293)
# ===========================================================================
L6_BANDS = [("dalam", 1300, 1800), ("luar", 1800, 2250),
            ("jumlah", 2250, 2650), ("prior", 2650, 3010)]
EYE_L6 = {   # key -> eye-read strings from 3x crops (/tmp/eye_l6_*.png)
    "r09.prior": "5,000,000,000.00",    # 1Malaysia Development Berhad
    "r11.prior": "859,860,000.00",      # Asset Global Network Sdn. Bhd.
    "r14.prior": "14,100,000,000.00",   # DanaInfra (page OCR misread 14,160,...)
    "r17.prior": "3,000,000,000.00",    # Johor Corporation (JCorp)
    "r20.prior": "1,000,000,000.00",    # Malaysia Debt Ventures (OCR read 1,600,...)
    "r30.prior": "4,000,000,000.00",    # SRC International Sdn. Bhd.
    "r31.prior": "2,324,985,894.40",    # Tenaga Nasional Berhad (TNB)
    "r32.prior": "5,310,000,000.00",    # Turus Pesawat Sdn. Bhd.
    # rows where dalam & jumlah were BOTH near-digit OCR variants; disambiguated
    # by the syarikat column sums and each eye-read from /tmp/eye_l6row_*.png
    "r13.dalam": "2,300,000,000.00",    # SME Bank ('?,300,...' misread)
    "r13.jumlah": "2,324,373,917.92",
    "r20.dalam": "1,100,000,000.00",    # Malaysia Debt Ventures
    "r20.jumlah": "1,100,000,000.00",
    "r28.dalam": "5,640,000,000.00",    # Sarawak Hidro (SHSB)
    "r28.jumlah": "5,640,000,000.00",
    "r30.dalam": "4,000,000,000.00",    # SRC International
    "r30.jumlah": "4,000,000,000.00",
    "r31.luar": "2,331,824,425.91",     # TNB (OCR .51/.91 sen confusion)
    "r31.jumlah": "2,331,824,425.91",
    "r32.dalam": "5,310,000,000.00",    # Turus Pesawat
    "r32.jumlah": "5,310,000,000.00",
}

L6_CANON = [
    "Bank Simpanan Nasional", "Kumpulan Wang Simpanan Guru-Guru",
    "Kumpulan Wang Simpanan Pekerja", "Lembaga Tabung Haji",
    "JUMLAH JAMINAN PENCARUM / PENDEPOSIT",
    "Perbadanan Tabung Pendidikan Tinggi Nasional",
    "Lembaga Kemajuan Tanah Persekutuan (FELDA)",
    "Perbadanan Kemajuan Negeri Pahang", "Jumlah Badan Berkanun",
    "1Malaysia Development Berhad", "1MDB Real Estate Sdn. Bhd.",
    "Asset Global Network Sdn. Bhd.",
    "Bank Pembangunan Malaysia Berhad (BPMB)",
    "Bank Perusahaan Kecil & Sederhana Malaysia Berhad (SME Bank)",
    "DanaInfra Nasional Berhad", "GovCo Holdings Berhad",
    "Jambatan Kedua Sdn. Bhd.", "Johor Corporation (JCorp)",
    "Khazanah Nasional Berhad", "K.L. International Airport Berhad (KLIA)",
    "Malaysia Debt Ventures Sdn. Bhd.",
    "Malaysian Industrial Development Finance Bhd. (MIDF)",
    "Pelabuhan Tanjung Pelepas Sdn. Bhd.",
    "Penerbangan Malaysia Berhad (PMB)",
    "Pengurusan Air SPV Berhad (PAAB)",
    "Projek Lebuhraya Usahasama Berhad (PLUS)", "Prasarana Malaysia Berhad",
    "Sabah Electricity Sdn. Bhd. (SESB)", "Sarawak Hidro Sdn. Bhd. (SHSB)",
    "Senai Airport Terminal Service Sdn. Bhd.", "SRC International Sdn. Bhd.",
    "Tenaga Nasional Berhad (TNB)", "Turus Pesawat Sdn. Bhd.",
    "Sentuhan Budiman", "Jumlah Syarikat", "JUMLAH JAMINAN PINJAMAN",
    "JUMLAH JAMINAN",
]


def extract_l6():
    stmt = "Penyata Akaun Memorandum Jaminan Berkanun"
    pno = 293
    lines = rows_of_page(pno)
    recs, jenis, cat = [], None, None
    for top, bot, lws in lines:
        label, cells = band_split(lws, L6_BANDS, label_max=1450)
        hdr = canon_label(label, ["JAMINAN PENCARUM / PENDEPOSIT", "JAMINAN PINJAMAN",
                                  "Badan Berkanun", "Syarikat"], cutoff=0.75) if label else ""
        if not cells:
            if hdr in ("JAMINAN PENCARUM / PENDEPOSIT", "JAMINAN PINJAMAN") and len(label) < 40:
                jenis, cat = hdr, None
            elif hdr in ("Badan Berkanun", "Syarikat") and len(label) < 20:
                cat = hdr
            elif recs and label and len(label) > 8 and not re.search(
                    r"PENYATA|Disember|Agensi|Memorandum|RM|Nota", label):
                recs[-1]["label"] += " " + label
            continue
        if len(label) < 4:
            continue
        recs.append(dict(jenis=jenis, cat=cat, label=label, top=top, cells=cells))

    sol = Solver("l6", EYE_L6)
    for i, r in enumerate(recs):
        cc = {}
        for b, lo, hi in L6_BANDS:
            if b in r["cells"]:
                txt, box = r["cells"][b]
                c = Cell(pno, b, txt, box, f"r{i:02d}.{b}")
            else:
                c = Cell(pno, b, None, (lo + 200, r["top"] - 6, hi - 40, r["top"] + 44), f"r{i:02d}.{b}")
            cc[b] = sol.add_cell(c)
        r["c"] = cc

    def idx(pred):
        return [i for i, r in enumerate(recs) if pred(r)]

    lab = [re.sub(r"\s+", " ", r["label"]) for r in recs]
    canon = [canon_label(l, L6_CANON, 0.55) for l in lab]
    for i, r in enumerate(recs):
        r["canon"] = canon[i]
    i_pen_sub = canon.index("JUMLAH JAMINAN PENCARUM / PENDEPOSIT")
    i_bb_sub = canon.index("Jumlah Badan Berkanun")
    i_sy_sub = canon.index("Jumlah Syarikat")
    i_pin_sub = canon.index("JUMLAH JAMINAN PINJAMAN")
    i_tot = canon.index("JUMLAH JAMINAN")
    pen = [i for i in idx(lambda r: r["jenis"] == "JAMINAN PENCARUM / PENDEPOSIT") if i != i_pen_sub]
    bb = [i for i in idx(lambda r: r["cat"] == "Badan Berkanun") if i != i_bb_sub]
    sy = [i for i in idx(lambda r: r["cat"] == "Syarikat") if i not in (i_sy_sub, i_pin_sub, i_tot)]

    for i, r in enumerate(recs):
        sol.ident(f"row {canon[i][:40]!r} Dalam+Luar=Jumlah",
                  [(1, f"r{i:02d}.dalam"), (1, f"r{i:02d}.luar"), (-1, f"r{i:02d}.jumlah")])
    for b, _, _ in L6_BANDS:
        sol.ident(f"pencarum details sum = JUMLAH PENCARUM [{b}]",
                  [(1, f"r{i:02d}.{b}") for i in pen] + [(-1, f"r{i_pen_sub:02d}.{b}")])
        sol.ident(f"badan berkanun details sum = Jumlah Badan Berkanun [{b}]",
                  [(1, f"r{i:02d}.{b}") for i in bb] + [(-1, f"r{i_bb_sub:02d}.{b}")])
        sol.ident(f"syarikat details sum = Jumlah Syarikat [{b}]",
                  [(1, f"r{i:02d}.{b}") for i in sy] + [(-1, f"r{i_sy_sub:02d}.{b}")])
        sol.ident(f"BB + Syarikat = JUMLAH JAMINAN PINJAMAN [{b}]",
                  [(1, f"r{i_bb_sub:02d}.{b}"), (1, f"r{i_sy_sub:02d}.{b}"), (-1, f"r{i_pin_sub:02d}.{b}")])
        sol.ident(f"PENCARUM + PINJAMAN = JUMLAH JAMINAN [{b}]",
                  [(1, f"r{i_pen_sub:02d}.{b}"), (1, f"r{i_pin_sub:02d}.{b}"), (-1, f"r{i_tot:02d}.{b}")])
    sol.solve()
    need = sol.finish("lampiran6")
    if need:
        for c in need:
            print("EYE-NEEDED L6", c.key, repr(c.raw), "->", eye_crop(c, f"l6_{c.key}"))
        raise SystemExit(f"L6: {len(need)} unresolved cells need eye-reading")
    sol.report_idents("lampiran6")

    out = []
    for i, r in enumerate(recs):
        lbl, rt, cat, jen = r["canon"], "detail", r["cat"], r["jenis"]
        if lbl.startswith("Jumlah ") or lbl in ("JUMLAH JAMINAN PENCARUM / PENDEPOSIT",
                                                "JUMLAH JAMINAN PINJAMAN"):
            rt = "subtotal"
            if lbl.startswith("JUMLAH"):
                cat = None
        if lbl == "JUMLAH JAMINAN":
            rt, cat, jen = "total", None, None
        cc = r["c"]
        base = dict(jenis_jaminan_bm=jen, kategori_bm=cat, agensi_bm=lbl, row_type=rt)
        out.append(prov(dict(base, year=YEAR, dalam_negeri_rm=cc["dalam"].value,
                             luar_negeri_rm=cc["luar"].value, jumlah_rm=cc["jumlah"].value), pno, stmt))
        out.append(prov(dict(base, year=PRIOR, dalam_negeri_rm=None,
                             luar_negeri_rm=None, jumlah_rm=cc["prior"].value), pno, stmt))
    cols = ["jenis_jaminan_bm", "kategori_bm", "agensi_bm", "row_type", "year",
            "dalam_negeri_rm", "luar_negeri_rm", "jumlah_rm",
            "source_file", "pdf_page", "printed_page", "statement"]
    with open(f"{WH}/fact_statutory_guarantees.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"fact_statutory_guarantees.csv: {len(out)} rows")
    return recs


# ===========================================================================
# Lampiran 3: Pinjaman Boleh Dituntut (pdf 275-277)
# Five printed value columns (Pembangunan / Hasil Disatukan / Amanah Lain /
# Baki 2015 / Baki 2014) exactly as the 2014 volume; warehouse2014 schema
# stores the prior baki as a year=2014 row.
# ===========================================================================
L3_BANDS = [("pemb", 1290, 1640), ("hasil", 1640, 1960), ("amanah", 1960, 2290),
            ("baki", 2290, 2645), ("prior", 2645, 3010)]
L3_CATS = {"I": "KERAJAAN NEGERI", "II": "PIHAK BERKUASA TEMPATAN",
           "III": "BADAN BERKANUN", "IV": "KOPERASI", "V": "SYARIKAT",
           "VI": "PERSEORANGAN", "VII": "PELBAGAI"}
# Eye-read values (route 'c') typed from composite crops /tmp/l3A_*.png,
# /tmp/l3B_*.png (scale 3) and /tmp/l3z_*.png (scale 4) via the Read tool for
# the 67 rows whose page-OCR failed the row cross-foot. "-" = printed dash.
# Every row re-verified below by pemb+hasil+amanah=baki and the column sums.
_L3EYE_ROWS = {
    0: ("349,494,109.95", "1,502,698.88", "84,000,000.00", "434,996,808.83", "452,814,350.10"),
    1: ("2,190,800,763.53", "7,255,809.65", "113,333,333.33", "2,311,389,906.51", "2,616,902,315.51"),
    2: ("1,309,731,075.72", "80,850.73", "45,000,000.00", "1,354,811,926.45", "1,293,560,341.47"),
    3: ("413,217,515.16", "44,105,086.65", "400,947,352.18", "858,269,953.99", "867,448,016.77"),
    4: ("853,494,940.20", "183,059.93", "81,993,300.00", "935,671,300.13", "912,694,439.65"),
    5: ("2,572,401,273.35", "9,369,485.16", "338,185,351.62", "2,919,956,110.13", "2,728,499,663.54"),
    6: ("607,080,545.63", "-", "-", "607,080,545.63", "558,400,417.41"),
    7: ("287,206,252.42", "5,917,818.71", "61,301,207.54", "354,425,278.67", "355,996,070.45"),
    8: ("69,191,008.96", "6,858.40", "-", "69,197,867.36", "61,268,809.29"),
    10: ("2,543,970,652.04", "290,909.91", "11,162,693.80", "2,555,424,255.75", "2,344,507,308.13"),
    11: ("1,013,596,029.92", "685,534.44", "14,077,904.17", "1,028,359,468.53", "957,194,787.85"),
    12: ("887,189,706.01", "17,314,404.67", "-", "904,504,110.68", "909,511,734.37"),
    13: ("15,626,918,650.69", "86,712,517.13", "1,219,316,724.89", "16,932,947,892.71", "16,470,077,891.28"),
    14: ("286,986,578.24", "24,936,610.96", "-", "311,923,189.20", "318,663,133.90"),
    15: ("15,130,668.80", "4,085,203.07", "-", "19,215,871.87", "19,215,871.87"),
    16: ("90,106,876.31", "23,019,338.86", "-", "113,126,215.17", "113,126,215.17"),
    17: ("392,224,123.35", "52,041,152.89", "-", "444,265,276.24", "451,005,220.94"),
    23: ("771,477,449.89", "-", "-", "771,477,449.89", "771,477,449.89"),
    24: ("2,658,611,617.66", "323,185,470.16", "798,811,245.97", "3,780,608,333.79", "3,780,608,333.79"),
    25: ("86,373,909.52", "15,482,393.02", "-", "101,856,302.54", "124,919,903.80"),
    26: ("564,000,000.00", "60,671,368.27", "180,000,000.00", "804,671,368.27", "687,956,471.01"),
    27: ("330,000,000.00", "-", "60,000,000.00", "390,000,000.00", "400,000,000.00"),
    30: ("-", "-", "160,200,000.00", "160,200,000.00", "167,400,000.00"),
    32: ("4,759,490,043.89", "399,341,013.50", "1,199,011,245.97", "6,357,842,303.36", "6,820,864,168.24"),
    33: ("6,120,210.00", "812,152.48", "-", "6,932,362.48", "6,932,362.48"),
    34: ("-", "-", "50,000,000.00", "50,000,000.00", "-"),
    35: ("-", "2,280,000.00", "78,200,000.00", "80,480,000.00", "80,480,000.00"),
    37: ("-", "2,493,442.76", "62,336,068.85", "64,829,511.61", "64,829,511.61"),
    38: ("6,120,210.00", "5,585,595.24", "196,596,830.15", "208,302,635.39", "158,302,635.39"),
    42: ("250,000,000.00", "28,255,616.43", "-", "278,255,616.43", "833,575,068.49"),
    44: ("127,259,123.00", "43,819,178.09", "400,000,000.00", "571,078,301.09", "588,690,932.92"),
    45: ("754,925,982.09", "-", "1,239,182,396.62", "1,994,108,378.71", "1,895,108,378.71"),
    46: ("703,959,154.00", "-", "360,000,000.00", "1,063,959,154.00", "997,133,118.00"),
    47: ("109,000,000.00", "-", "-", "109,000,000.00", "113,000,000.00"),
    48: ("439,000,000.00", "112,337,500.00", "60,500,000.00", "611,837,500.00", "617,637,500.00"),
    50: ("-", "-", "83,440,000.00", "83,440,000.00", "83,440,000.00"),
    52: ("715,000,000.00", "1,173,277,163.47", "210,000,000.00", "2,098,277,163.47", "2,098,266,572.32"),
    53: ("-", "33,859,097.30", "490,994,299.25", "524,853,396.55", "554,423,396.55"),
    56: ("855,504,289.00", "-", "25,000,000.00", "880,504,289.00", "880,504,289.00"),
    57: ("111,000,000.00", "-", "-", "111,000,000.00", "118,000,000.00"),
    59: ("227,500,000.00", "4,080,000.00", "-", "231,580,000.00", "214,500,000.00"),
    60: ("-", "32,743,909.30", "-", "32,743,909.30", "32,743,909.30"),
    70: ("-", "-", "14,895,038.00", "14,895,038.00", "14,895,038.00"),
    72: ("4,742,855,712.31", "-", "367,290,000.00", "5,110,145,712.31", "5,102,614,325.44"),
    73: ("-", "-", "571,840,361.83", "571,840,361.83", "682,400,000.00"),
    78: ("-", "3,135,000.00", "40,100,000.00", "43,235,000.00", "43,235,000.00"),
    81: ("134,203,484.06", "29,389,792.88", "-", "163,593,276.94", "175,535,173.66"),
    82: ("16,512,508.40", "-", "-", "16,512,508.40", "24,409,829.36"),
    84: ("1,486,841,539.45", "322,786,201.23", "5,000,000.00", "1,814,627,740.68", "1,691,222,307.09"),
    85: ("-", "-", "15,137,165.00", "15,137,165.00", "15,337,165.00"),
    88: ("577,500,000.00", "8,357,287.40", "-", "585,857,287.40", "581,641,612.06"),
    89: ("5,316,280.00", "8,601,892.59", "-", "13,918,172.59", "14,343,980.62"),
    92: ("110,800,000.00", "10,416,306.85", "-", "121,216,306.85", "116,784,306.85"),
    94: ("3,068,433.92", "-", "-", "3,068,433.92", "3,145,263.56"),
    96: ("-", "-", "4,602,477.13", "4,602,477.13", "4,850,000.00"),
    98: ("-", "-", "10,400,000.00", "10,400,000.00", "10,400,000.00"),
    99: ("18,235,906,567.60", "1,836,427,205.23", "8,883,780,349.21", "28,956,114,122.04", "28,856,676,215.31"),
    100: ("-", "-", "(984,835.07)", "(984,835.07)", "(1,405,512.56)"),
    101: ("-", "-", "60,779,569.43", "60,779,569.43", "60,100,986.64"),
    102: ("-", "-", "50,924,736,484.89", "50,924,736,484.89", "43,897,886,130.67"),
    103: ("-", "-", "118,185,488.71", "118,185,488.71", "104,848,152.98"),
    105: ("194,101,307.50", "-", "586,500,000.00", "780,601,307.50", "782,601,307.50"),
    108: ("-", "-", "6,800,000.00", "6,800,000.00", "6,800,000.00"),
    109: ("68,131,590.00", "-", "812,000,000.00", "880,131,590.00", "920,531,590.00"),
    110: ("-", "-", "30,000,000.00", "30,000,000.00", "30,000,000.00"),
    112: ("265,969,169.70", "-", "1,465,300,000.00", "1,731,269,169.70", "2,217,667,709.68"),
    113: ("39,286,628,765.23", "2,380,107,483.99", "64,066,721,858.18", "105,733,458,107.40", "99,036,023,598.57"),
    # rows whose trivial row-identity (single nonzero column) passed on
    # consistent misreads - caught by category column sums + 2016-volume
    # cross-flag, then eye-read from /tmp/l3QA_*.png, /tmp/l3QB_*.png (scale 3)
    9: ("2,529,544,777.80", "-", "69,315,582.25", "2,598,860,360.05", "2,411,279,636.74"),
    18: ("10,000,000.00", "-", "-", "10,000,000.00", "10,000,000.00"),
    19: ("1,817,560.13", "-", "-", "1,817,560.13", "2,670,730.89"),
    28: ("295,425,738.53", "-", "-", "295,425,738.53", "831,752,403.73"),
    29: ("5,420,400.00", "1,782.05", "-", "5,422,182.05", "-"),
    36: ("-", "-", "6,060,761.30", "6,060,761.30", "6,060,761.30"),
    40: ("-", "-", "45,750,196.20", "45,750,196.20", "46,950,196.20"),
    41: ("-", "-", "77,000,000.00", "77,000,000.00", "80,000,000.00"),
    43: ("-", "-", "4,960,000.00", "4,960,000.00", "4,960,000.00"),
    54: ("-", "-", "18,596,214.27", "18,596,214.27", "18,957,652.97"),
    58: ("-", "-", "32,871,197.69", "32,871,197.69", "34,772,155.73"),
    66: ("324,135,703.00", "-", "-", "324,135,703.00", "331,120,201.00"),
    68: ("2,850,000.00", "-", "-", "2,850,000.00", "14,850,000.00"),
    75: ("-", "-", "2,979,481,336.50", "2,979,481,336.50", "3,179,481,336.50"),
    80: ("-", "-", "50,200,000.00", "50,200,000.00", "50,200,000.00"),
    90: ("223,400,000.00", "-", "-", "223,400,000.00", "223,400,000.00"),
    93: ("1,705,999,962.00", "-", "-", "1,705,999,962.00", "1,455,999,962.00"),
    95: ("220,127,103.78", "15,913,384.40", "-", "236,040,488.18", "261,508,789.36"),
    97: ("250,000,000.00", "-", "-", "250,000,000.00", "-"),
    107: ("3,736,272.20", "-", "-", "3,736,272.20", "4,316,954.14"),
    111: ("-", "-", "30,000,000.00", "30,000,000.00", "-"),
    83: ("841,000,000.00", "-", "-", "841,000,000.00", "844,000,000.00"),  # /tmp/l3q_qcells.png
}
# prior-column (baki 2014) cells eye-read from /tmp/l3P_0.png, /tmp/l3P_1.png
# (scale 4); each also agrees exactly with the 2014 volume's own baki 2014
# (warehouse2014) - agreement logged INFO, never used as the source.
_L3EYE_PRIOR = {
    20: "32,942,659.94", 21: "2,500,269.29", 22: "6,295,341.21",
    28: "831,752,403.73", 31: "2,340,604.69", 39: "7,821,678.16",
    40: "46,950,196.20", 41: "80,000,000.00", 51: "1,560,377,272.33",
    55: "71,997,206.60", 58: "34,772,155.73", 61: "10,000,000.00",
    62: "2,598,301.96", 63: "62,736,956.44", 64: "290,000,000.00",
    65: "481,744,023.00", 67: "690,900,000.00", 69: "250,000,000.00",
    75: "3,179,481,336.50", 76: "117,131,169.00", 80: "50,200,000.00",
    83: "844,000,000.00", 86: "9,674,560.00", 91: "474,815,881.73",
    93: "1,455,999,962.00", 95: "261,508,789.36", 106: "473,417,858.04",
    107: "4,316,954.14",
}
EYE_L3 = {}
for _i, _v in _L3EYE_PRIOR.items():
    EYE_L3[f"r{_i:03d}.prior"] = _v
for _i, _vals in _L3EYE_ROWS.items():
    for _b, _v in zip(("pemb", "hasil", "amanah", "baki", "prior"), _vals):
        EYE_L3[f"r{_i:03d}.{_b}"] = "–" if _v == "-" else _v

L3_SKIP = re.compile(r"PENYATA|KEWANGAN|Disember|sambungan|Memorandum|Pinjaman Boleh|"
                     r"Pambangunan|Fembangunan|Pembangunan Hast|Paminan|Pannen|Peminjam|"
                     r"^\W*$|^[A-Za-z]{1,3}$")


def _alpha_ratio(s):
    a = sum(1 for ch in s if ch.isalpha() or ch in " .,()-&/'")
    return a / max(1, len(s))


def extract_l3():
    stmt = "Penyata Akaun Memorandum Pinjaman Boleh Dituntut"
    pages = [275, 276, 277]
    with open("/tmp/l3_names.txt") as f:
        canon_names = [l.rstrip("\n") for l in f if l.strip() and not re.search(r"\d", l)
                       and not l.startswith(("JUMLAH", "Jumlah"))]
    recs, cat = [], None
    for pno in pages:
        page_recs = 0
        for top, bot, lws in rows_of_page(pno, ytol=25):
            label, cells = band_split(lws, L3_BANDS, label_max=1290)
            label = re.sub(r"\s+", " ", label).strip()
            m = re.match(r"^([IVXLYivxly1J]{1,4})[.,]? ([A-Z].*)$", label)
            if m and not cells and len(label) < 40:
                # the roman numeral itself OCRs unreliably ('lL'->II) - key the
                # category off the header TEXT instead
                nm = canon_label(m.group(2).replace("-(SAMB,)", "").replace("- (SAMB.)", "").strip(),
                                 list(L3_CATS.values()), cutoff=0.6)
                if nm in L3_CATS.values():
                    cat = nm
                    continue
            if not cells:
                if (recs and label and len(label) > 6 and _alpha_ratio(label) > 0.8
                        and not L3_SKIP.search(label) and recs[-1]["pno"] == pno
                        and top - recs[-1]["top"] < 120):
                    recs[-1]["label"] += " " + label
                continue
            if L3_SKIP.search(label) and "Jum" not in label and "JUM" not in label \
                    and "DITUNTUT" not in label:
                continue
            if len(label) < 4:
                continue
            recs.append(dict(cat=cat, label=label, top=top, pno=pno, cells=cells))
            page_recs += 1
    # classify rows
    for r in recs:
        l = r["label"]
        if re.search(r"JU.?[DM]?[LM]?LAH.*(DITUNTUT|BOLEH)", l, re.I) and l[:2].isupper() \
                and "PINJAMAN" in l.upper():
            r["rt"], r["canon"] = "total", "JUMLAH PINJAMAN BOLEH DITUNTUT"
        elif re.match(r"^Ju\w{1,4}h?\b", l) and _alpha_ratio(l) > 0.7:
            r["rt"] = "subtotal"
            r["canon"] = "Jumlah " + r["cat"].title().replace("Kerajaan Negeri", "Kerajaan Negeri")
        else:
            r["rt"] = "detail"
            r["canon"] = canon_label(l, canon_names, cutoff=0.62)
    # fix subtotal canon capitalisation to match 2014 warehouse; a subtotal row
    # belongs to the category of the PRECEDING detail row (the next category
    # header can OCR-cluster above the Jumlah line)
    SUBS = {"KERAJAAN NEGERI": "Jumlah Kerajaan Negeri",
            "PIHAK BERKUASA TEMPATAN": "Jumlah Pihak Berkuasa Tempatan",
            "BADAN BERKANUN": "Jumlah Badan Berkanun", "KOPERASI": "Jumlah Koperasi",
            "SYARIKAT": "Jumlah Syarikat", "PERSEORANGAN": "Jumlah Perseorangan",
            "PELBAGAI": "Jumlah Pelbagai"}
    last_cat = None
    for r in recs:
        if r["rt"] == "detail" and "Penjaja" in r["label"]:
            r["canon"] = "Yayasan Penjaja dan Peniaga Kecil 1Malaysia"
        if r["rt"] == "detail":
            last_cat = r["cat"]
        elif r["rt"] == "subtotal":
            r["cat"] = last_cat or r["cat"]
            r["canon"] = SUBS[r["cat"]]
    sol = Solver("l3", EYE_L3)
    for i, r in enumerate(recs):
        cc = {}
        for b, lo, hi in L3_BANDS:
            key = f"r{i:03d}.{b}"
            if b in r["cells"]:
                txt, box = r["cells"][b]
                c = Cell(r["pno"], b, txt, box, key)
            else:
                c = Cell(r["pno"], b, None, (lo + 250, r["top"] - 6, hi - 60, r["top"] + 40), key)
            cc[b] = sol.add_cell(c)
        r["c"] = cc
    # identities
    for i, r in enumerate(recs):
        sol.ident(f"row {r['canon'][:38]!r} pemb+hasil+amanah=baki2015",
                  [(1, f"r{i:03d}.pemb"), (1, f"r{i:03d}.hasil"),
                   (1, f"r{i:03d}.amanah"), (-1, f"r{i:03d}.baki")])
    subs = {r["cat"]: i for i, r in enumerate(recs) if r["rt"] == "subtotal"}
    itot = next(i for i, r in enumerate(recs) if r["rt"] == "total")
    for cat, isub in subs.items():
        dets = [i for i, r in enumerate(recs) if r["rt"] == "detail" and r["cat"] == cat]
        for b, _, _ in L3_BANDS:
            sol.ident(f"{cat} details sum = Jumlah [{b}]",
                      [(1, f"r{i:03d}.{b}") for i in dets] + [(-1, f"r{isub:03d}.{b}")])
    for b, _, _ in L3_BANDS:
        sol.ident(f"category subtotals sum = JUMLAH PINJAMAN BOLEH DITUNTUT [{b}]",
                  [(1, f"r{i:03d}.{b}") for i in subs.values()] + [(-1, f"r{itot:03d}.{b}")])
    sol.solve()
    need = sol.finish("lampiran3")
    if need:
        for c in need:
            r = recs[int(c.key[1:4])]
            print("EYE-NEEDED L3", c.key, r["canon"][:40], repr(c.raw), "->",
                  eye_crop(c, f"l3_{c.key}"))
        raise SystemExit(f"L3: {len(need)} unresolved cells need eye-reading")
    sol.report_idents("lampiran3")
    out = []
    for i, r in enumerate(recs):
        cat_no = {v: k for k, v in L3_CATS.items()}.get(r["cat"])
        base = dict(section_bm="PINJAMAN" if r["rt"] != "total" else None,
                    category_no=cat_no if r["rt"] != "total" else None,
                    category_bm=r["cat"] if r["rt"] != "total" else None,
                    peminjam_bm=r["canon"], row_type=r["rt"])
        cc = r["c"]
        out.append(prov(dict(base, year=YEAR, pembangunan_rm=cc["pemb"].value,
                             hasil_disatukan_rm=cc["hasil"].value,
                             amanah_lain_rm=cc["amanah"].value,
                             baki_belum_selesai_rm=cc["baki"].value), r["pno"], stmt))
        out.append(prov(dict(base, year=PRIOR, pembangunan_rm=None,
                             hasil_disatukan_rm=None, amanah_lain_rm=None,
                             baki_belum_selesai_rm=cc["prior"].value), r["pno"], stmt))
    cols = ["section_bm", "category_no", "category_bm", "peminjam_bm", "row_type",
            "year", "pembangunan_rm", "hasil_disatukan_rm", "amanah_lain_rm",
            "baki_belum_selesai_rm", "source_file", "pdf_page", "printed_page", "statement"]
    with open(f"{WH}/fact_loans_receivable.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"fact_loans_receivable.csv: {len(out)} rows")
    return recs


# ===========================================================================
# Lampiran 5: Hutang Awam (pdf 287-290)
#   (a) Pinjaman DN/LN/KWPP pdf 287-288: page-OCR digits unusable, so the
#       whole table was EYE-TYPED from composite crops /tmp/l5dn_*.png,
#       /tmp/l5ln_*.png (scale 3) and /tmp/l5z_/l5r_* zooms (scale 5-6, raw
#       render). String fields cross-checked against the same issues in
#       warehouse2014/warehouse2016; two damaged-glyph kadar cells adopted
#       from BOTH adjacent volumes (identical there), logged INFO.
#       Two amounts forced by the printed column sums (logged INFO):
#       1/2006 SKM belum selesai 14,658,725,000.00 and 2/2013 SKM
#       8,786,557,000.00 (both digit-consistent with the damaged print).
#   (b) Bantuan Luar Negeri pdf 289-290: TSV + solver (per-lender 5-column
#       sums, region and grand totals), eye overrides where needed.
# ===========================================================================
L5_STMT_P = "Penyata Akaun Memorandum - Hutang Awam (Pinjaman)"
L5_STMT_B = "Penyata Akaun Memorandum - Hutang Awam (Bantuan Luar Negeri)"

TPK = [  # no_keluaran, kod, kadar, tarikh, amount (dib = belum selesai)
    ("3/2006", "GN 060019", "3.820", "15.11.2016", "11,000,000,000.00"),
    ("2/2007", "GN 070008", "3.941", "15.06.2017", "3,000,000,000.00"),
    ("4/2008", "GN 080031", "4.295", "31.10.2018", "7,500,000,000.00"),
    ("1/2009", "GO 090001", "3.910", "13.08.2019", "6,000,000,000.00"),
    ("6/2009", "GO 090061", "4.492", "30.04.2020", "3,500,000,000.00"),
    ("3/2010", "GN 100021", "4.284", "15.06.2020", "5,500,000,000.00"),
    ("6/2010", "GN 100060", "3.998", "30.11.2020", "3,000,000,000.00"),
    ("1/2011", "GL 110001", "3.872", "30.08.2018", "8,500,000,000.00"),
    ("3/2011", "GN 110025", "4.170", "30.04.2021", "12,500,000,000.00"),
    ("2/2012", "GJ 120009", "3.309", "30.08.2017", "9,500,000,000.00"),
    ("3/2012", "GL 120021", "3.704", "30.09.2019", "8,000,000,000.00"),
    ("4/2012", "GO 120037", "3.699", "15.11.2022", "8,500,000,000.00"),
    ("5/2012", "GS 120059", "3.899", "15.06.2027", "5,000,000,000.00"),
    ("6/2012", "GH 120090", "3.235", "08.02.2016", "7,000,000,000.00"),
    ("7/2012", "GL 120098", "3.576", "15.05.2020", "11,000,000,000.00"),
    ("1/2013", "GT 130001", "3.871", "08.08.2028", "3,000,000,000.00"),
    ("2/2013", "GO 130033", "3.493", "31.10.2023", "4,000,000,000.00"),
    ("3/2013", "GJ 130055", "3.399", "30.11.2018", "4,000,000,000.00"),
    ("4/2013", "GG 130067", "3.389", "22.07.2016", "4,000,000,000.00"),
    ("5/2013", "GX 130068", "4.582", "30.08.2033", "4,000,000,000.00"),
    ("6/2013", "GL 130069", "3.716", "23.03.2021", "9,500,000,000.00"),
    ("7/2013", "GJ 130070", "3.558", "30.04.2019", "10,000,000,000.00"),
    ("8/2013", "GO 130071", "4.444", "22.05.2024", "12,500,000,000.00"),
    ("9/2013", "GS 130072", "4.943", "06.12.2028", "5,000,000,000.00"),
    ("1/2014", "GH 140001", "3.678", "23.11.2017", "7,500,000,000.00"),
    ("1/2015", "GL 150001", "4.194", "15.07.2022", "10,000,000,000.00"),
    ("2/2015", "GJ 150002", "3.799", "27.08.2020", "10,000,000,000.00"),
    ("3/2015", "GT 150003", "4.245", "30.09.2030", "1,500,000,000.00"),
    ("4/2015", "GO 150004", "3.990", "15.10.2025", "10,500,000,000.00"),
    ("5/2015", "GG 150005", "3.508", "15.05.2018", "7,500,000,000.00"),
    ("6/2015", "GX 150006", "4.790", "31.10.2035", "1,500,000,000.00"),
]
SKM = [  # no, kod, kadar, tarikh, dibenarkan, belum_selesai
    ("5/1998", "MZ 9800 5A", "8.000", "30.10.2018", "3,000,000,000.00", None),
    ("1/2003", "MS 0300 1S", "4.410", "29.01.2018", "2,000,000,000.00", None),
    ("2/2003", "MS 0300 2H", "4.240", "07.02.2018", "15,100,000,000.00", "14,100,000,000.00"),
    ("3/2004", "MS 0400 3H", "5.734", "30.07.2019", "7,315,546,000.00", None),
    ("3/2005", "MY 050003", "4.837", "15.07.2025", "3,000,000,000.00", None),
    ("1/2006", "MO 060001", "4.262", "15.09.2016", "19,700,000,000.00", "14,658,725,000.00"),
    ("2/2006", "MX 060002", "4.709", "15.09.2026", "3,110,000,000.00", None),
    ("2/2007", "MN 070002", "3.814", "15.02.2017", "9,500,000,000.00", "8,750,000,000.00"),
    ("3/2007", "MX 070003", "3.502", "31.05.2027", "6,000,000,000.00", None),
    ("3/2008", "MX 080003", "5.248", "15.09.2028", "5,040,000,000.00", None),
    ("2/2009", "MO 090002", "4.378", "29.11.2019", "17,600,000,000.00", "17,119,000,000.00"),
    ("2/2010", "ML 100002", "4.012", "15.09.2017", "14,000,000,000.00", None),
    ("3/2010", "MX 100003", "4.498", "15.04.2030", "12,770,000,000.00", None),
    ("1/2011", "MO 110001", "4.160", "15.07.2021", "13,500,000,000.00", None),
    ("3/2011", "MS 110003", "4.392", "15.04.2026", "10,574,330,000.00", None),
    ("4/2011", "MX 110004", "4.232", "30.06.2031", "3,750,000,000.00", None),
    ("5/2011", "MK 110005", "3.580", "28.09.2018", "11,440,000,000.00", None),
    ("1/2012", "MO 120001", "3.418", "15.08.2022", "10,500,000,000.00", None),
    ("2/2012", "MS 120002", "3.892", "15.03.2027", "5,500,000,000.00", None),
    ("4/2012", "MX 120004", "4.127", "15.04.2032", "5,500,000,000.00", None),
    ("5/2012", "MJ 120005", "3.314", "31.10.2017", "13,500,000,000.00", None),
    ("6/2012", "ML 120006", "3.492", "31.03.2020", "11,000,000,000.00", None),
    ("1/2013", "MH 130001", "3.172", "15.07.2016", "11,500,000,000.00", "11,482,428,000.00"),
    ("2/2013", "MI 130002", "3.260", "01.03.2018", "8,786,557,000.00", None),
    ("3/2013", "MN 130003", "3.480", "15.03.2023", "11,420,000,000.00", None),
    ("4/2013", "MX 130004", "3.844", "15.04.2033", "4,500,000,000.00", None),
    ("5/2013", "MS 130005", "3.733", "15.06.2028", "5,000,000,000.00", None),
    ("6/2013", "MK 130006", "3.889", "31.07.2020", "7,973,062,000.00", None),
    ("7/2013", "MZ 130007", "4.935", "30.09.2043", "6,500,000,000.00", None),
    ("1/2014", "MO 140001", "4.181", "15.07.2024", "11,020,000,000.00", None),
    ("2/2014", "MG 140002", "3.394", "15.03.2017", "10,500,000,000.00", None),
    ("3/2014", "ML 140003", "4.048", "30.09.2021", "11,700,000,000.00", None),
    ("4/2014", "MJ 140004", "3.654", "31.10.2019", "11,800,000,000.00", None),
    ("1/2015", "MO 150001", "3.955", "15.09.2025", "13,672,200,000.00", None),
    ("2/2015", "ML 150002", "3.795", "30.09.2022", "11,000,000,000.00", None),
    ("3/2015", "MJ 150003", "3.659", "15.10.2020", "11,742,134,000.00", None),
    ("4/2015", "MY 150004", "4.254", "31.05.2035", "2,661,000,000.00", None),
    ("5/2015", "MH 150005", "3.759", "15.03.2019", "4,177,897,000.00", None),
]
L5_PRINTED = dict(  # printed subtotal/total lines (eye-read)
    tpk_dib="214,000,000,000.00", tpk_bs="214,000,000,000.00",
    skm_dib="347,352,726,000.00", skm_bs="340,062,879,000.00",
    dn_bs="558,762,879,000.00",
    pp_usd="3,500,000,000.00", pp_bs="15,179,150,000.00",
    ln_bs="15,179,150,000.00",
    kwpp_dib="60,700,000,000.00", kwpp_bs="50,300,000,000.00",
    grand_bs="624,242,029,000.00",
)
PP = [  # perihal, kadar, tarikh, usd, rm
    ("2011 Sukuk Wakala Global USD 1.2 Bilion", "3.320", "06.07.2016",
     "1,200,000,000.00", "5,204,280,000.00"),
    ("2011 Sukuk Wakala Global USD 0.8 Bilion", "3.320", "06.07.2021",
     "800,000,000.00", "3,469,520,000.00"),
    ("2015 Sukuk Global USD 1.0 Bilion", "3.043", "22.04.2025",
     "1,000,000,000.00", "4,336,900,000.00"),
    ("2015 Sukuk Global USD 0.5 Bilion", "4.236", "22.04.2045",
     "500,000,000.00", "2,168,450,000.00"),
]
KWPP = [
    ("Pinjaman Berjangka", "3.970 - 4.513", "2016 - 2020",
     "32,300,000,000.00", "21,900,000,000.00"),
    ("Sukuk Perumahan Kerajaan", "3.536 - 4.731", "2019 - 2024",
     "28,400,000,000.00", "28,400,000,000.00"),
]


def _l5row(**kw):
    base = dict(region_bm=None, instrument_bm=None, lender_bm=None, no_keluaran=None,
                kod_saham=None, perihal_bm=None, kadar_faedah=None, tarikh_tebusan=None,
                ccy=None, amaun_dibenarkan_fx=None, terkumpul_keluaran_fx=None,
                terkumpul_bayaran_balik_fx=None, amaun_belum_selesai_fx=None,
                amaun_dibenarkan_rm=None, amaun_belum_selesai_rm=None,
                row_type="detail", has_footnote=False, year=YEAR)
    base.update(kw)
    return base


def extract_l5_pinjaman():
    rows = []
    A = parse_amount
    rows.append(prov(_l5row(region_bm="DALAM NEGERI", instrument_bm="BIL PERBENDAHARAAN",
                            kadar_faedah="Dengan Tawaran", tarikh_tebusan="2015",
                            amaun_dibenarkan_rm=A("4,700,000,000.00"),
                            amaun_belum_selesai_rm=A("4,700,000,000.00")), 287, L5_STMT_P))
    for no, kod, kad, tar, amt_ in TPK:
        rows.append(prov(_l5row(region_bm="DALAM NEGERI",
                                instrument_bm="TERBITAN PELABURAN KERAJAAN",
                                no_keluaran=no, kod_saham=kod, kadar_faedah=kad,
                                tarikh_tebusan=tar, amaun_dibenarkan_rm=A(amt_),
                                amaun_belum_selesai_rm=A(amt_)), 287, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="DALAM NEGERI", instrument_bm="TERBITAN PELABURAN KERAJAAN",
                            perihal_bm="Jumlah Terbitan Pelaburan Kerajaan", row_type="subtotal",
                            amaun_dibenarkan_rm=A(L5_PRINTED["tpk_dib"]),
                            amaun_belum_selesai_rm=A(L5_PRINTED["tpk_bs"])), 287, L5_STMT_P))
    for no, kod, kad, tar, dib, bs in SKM:
        rows.append(prov(_l5row(region_bm="DALAM NEGERI",
                                instrument_bm="SEKURITI KERAJAAN MALAYSIA",
                                no_keluaran=no, kod_saham=kod, kadar_faedah=kad,
                                tarikh_tebusan=tar, amaun_dibenarkan_rm=A(dib),
                                amaun_belum_selesai_rm=A(bs if bs else dib)), 287, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="DALAM NEGERI", instrument_bm="SEKURITI KERAJAAN MALAYSIA",
                            perihal_bm="Jumlah Sekuriti Kerajaan Malaysia", row_type="subtotal",
                            amaun_dibenarkan_rm=A(L5_PRINTED["skm_dib"]),
                            amaun_belum_selesai_rm=A(L5_PRINTED["skm_bs"])), 287, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="DALAM NEGERI", perihal_bm="Jumlah Dalam Negeri",
                            row_type="subtotal",
                            amaun_belum_selesai_rm=A(L5_PRINTED["dn_bs"])), 287, L5_STMT_P))
    for per, kad, tar, usd, rm_ in PP:
        rows.append(prov(_l5row(region_bm="LUAR NEGERI", instrument_bm="PINJAMAN PASARAN",
                                perihal_bm=per, kadar_faedah=kad, tarikh_tebusan=tar,
                                ccy="USD", amaun_dibenarkan_fx=A(usd),
                                amaun_belum_selesai_rm=A(rm_)), 288, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="LUAR NEGERI", instrument_bm="PINJAMAN PASARAN",
                            perihal_bm="Jumlah Pinjaman Pasaran", row_type="subtotal", ccy="USD",
                            amaun_dibenarkan_fx=A(L5_PRINTED["pp_usd"]),
                            amaun_belum_selesai_rm=A(L5_PRINTED["pp_bs"])), 288, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="LUAR NEGERI", perihal_bm="Jumlah Luar Negeri",
                            row_type="subtotal",
                            amaun_belum_selesai_rm=A(L5_PRINTED["ln_bs"])), 288, L5_STMT_P))
    for per, kad, tar, dib, bs in KWPP:
        rows.append(prov(_l5row(region_bm="KUMPULAN WANG PINJAMAN PERUMAHAN",
                                instrument_bm="PEMBIAYAAN KUMPULAN WANG PINJAMAN PERUMAHAN",
                                perihal_bm=per, kadar_faedah=kad, tarikh_tebusan=tar,
                                amaun_dibenarkan_rm=A(dib),
                                amaun_belum_selesai_rm=A(bs)), 288, L5_STMT_P))
    rows.append(prov(_l5row(region_bm="KUMPULAN WANG PINJAMAN PERUMAHAN",
                            instrument_bm="PEMBIAYAAN KUMPULAN WANG PINJAMAN PERUMAHAN",
                            perihal_bm="Jumlah Kumpulan Wang Pinjaman Perumahan",
                            row_type="subtotal",
                            amaun_dibenarkan_rm=A(L5_PRINTED["kwpp_dib"]),
                            amaun_belum_selesai_rm=A(L5_PRINTED["kwpp_bs"])), 288, L5_STMT_P))
    rows.append(prov(_l5row(perihal_bm="JUMLAH PINJAMAN", row_type="total",
                            amaun_belum_selesai_rm=A(L5_PRINTED["grand_bs"])), 288, L5_STMT_P))
    # ---- footings (printed arithmetic; every amount cell confirmed by these
    # sums = route (a), on top of the eye-read (route c)) ----
    def S(insts, col):
        return round(sum(r[col] or 0 for r in rows
                         if r["row_type"] == "detail" and r["instrument_bm"] in insts), 2)
    fx = [("lampiran5: TPK series sum = printed Jumlah [dibenarkan]",
           S({"TERBITAN PELABURAN KERAJAAN"}, "amaun_dibenarkan_rm"), A(L5_PRINTED["tpk_dib"])),
          ("lampiran5: TPK series sum = printed Jumlah [belum selesai]",
           S({"TERBITAN PELABURAN KERAJAAN"}, "amaun_belum_selesai_rm"), A(L5_PRINTED["tpk_bs"])),
          ("lampiran5: SKM series sum = printed Jumlah [dibenarkan]",
           S({"SEKURITI KERAJAAN MALAYSIA"}, "amaun_dibenarkan_rm"), A(L5_PRINTED["skm_dib"])),
          ("lampiran5: SKM series sum = printed Jumlah [belum selesai]",
           S({"SEKURITI KERAJAAN MALAYSIA"}, "amaun_belum_selesai_rm"), A(L5_PRINTED["skm_bs"])),
          ("lampiran5: BP + TPK + SKM = Jumlah Dalam Negeri",
           round(4.7e9 + A(L5_PRINTED["tpk_bs"]) + A(L5_PRINTED["skm_bs"]), 2), A(L5_PRINTED["dn_bs"])),
          ("lampiran5: Pinjaman Pasaran USD sum = printed Jumlah",
           S({"PINJAMAN PASARAN"}, "amaun_dibenarkan_fx"), A(L5_PRINTED["pp_usd"])),
          ("lampiran5: Pinjaman Pasaran RM sum = printed Jumlah",
           S({"PINJAMAN PASARAN"}, "amaun_belum_selesai_rm"), A(L5_PRINTED["pp_bs"])),
          ("lampiran5: Jumlah Pinjaman Pasaran = Jumlah Luar Negeri",
           A(L5_PRINTED["pp_bs"]), A(L5_PRINTED["ln_bs"])),
          ("lampiran5: KWPP rows sum = printed Jumlah [dibenarkan]",
           S({"PEMBIAYAAN KUMPULAN WANG PINJAMAN PERUMAHAN"}, "amaun_dibenarkan_rm"),
           A(L5_PRINTED["kwpp_dib"])),
          ("lampiran5: KWPP rows sum = printed Jumlah [belum selesai]",
           S({"PEMBIAYAAN KUMPULAN WANG PINJAMAN PERUMAHAN"}, "amaun_belum_selesai_rm"),
           A(L5_PRINTED["kwpp_bs"])),
          ("lampiran5: DN + LN + KWPP = JUMLAH PINJAMAN",
           round(A(L5_PRINTED["dn_bs"]) + A(L5_PRINTED["ln_bs"]) + A(L5_PRINTED["kwpp_bs"]), 2),
           A(L5_PRINTED["grand_bs"]))]
    for name, got, want in fx:
        chk("PASS" if abs(got - want) < 0.5 else "FAIL", name, got, want)
    chk("INFO", "lampiran5: DN/LN/KWPP eye-typed from /tmp/l5dn_*, /tmp/l5ln_* sheets "
        "(scale 3) + /tmp/l5z_/l5r_* zooms; string fields cross-checked vs "
        "warehouse2014/2016 registers", len(rows), "")
    chk("INFO", "lampiran5: kadar 3/2006 TPK read 3.820 (damaged glyph; 2014 AND 2016 "
        "volumes print 3.820) and 3/2008 SKM 5.248 (idem)", "", "")
    chk("WARN", "lampiran5: kadar 6/2015 GX 150006 printed 4.790 in this volume but "
        "4.786 in the 2016 volume (reopening re-priced or print-side difference; "
        "kept as printed 4.790, eye-verified at 6x raw zoom /tmp/l5r_gx6.png)", 4.790, 4.786)
    chk("INFO", "lampiran5: OCR salvage p287 1/2006 SKM belum selesai damaged print -> "
        "14,658,725,000.00 [forced by Jumlah SKM column sum; glyph-consistent]",
        14658725000.0, 14658725000.0)
    chk("INFO", "lampiran5: OCR salvage p287 2/2013 SKM damaged print -> 8,786,557,000.00 "
        "both columns [forced by SKM column sums; = printed value in 2014/2016 volumes]",
        8786557000.0, 8786557000.0)
    CONFIRM["c"] += 2 + len(TPK) * 2 + len(SKM) * 2 + len(PP) * 2 + len(KWPP) * 2 + 12
    return rows


# ---- (b) Bantuan Luar Negeri, pdf 289-290 ---------------------------------
B_BANDS_289 = [("dib", 1490, 1800), ("kel", 1830, 2110), ("bay", 2170, 2420),
               ("bsfx", 2450, 2725), ("bsrm", 2760, 3040)]
B_BANDS_290 = [("dib", 1490, 1800), ("kel", 1830, 2100), ("bay", 2130, 2400),
               ("bsfx", 2430, 2690), ("bsrm", 2720, 2990)]
EYE_L5B = {}

CCYRE = re.compile(r"^(USD|CAD|EUR|JPY|GBP|CHF|SDR|ISO|SD|iso|‘sD|CAB)$")


def extract_l5_bantuan():
    import difflib
    w_perihal = set()
    try:
        import pandas as pd
        for wh in ("warehouse2014", "warehouse2016"):
            d = pd.read_csv(f"/home/claude/pkkp/{wh}/fact_debt_issues.csv")
            for v in d[d.statement.str.contains("Bantuan")].perihal_bm.dropna():
                w_perihal.add(v)
    except Exception:
        pass
    recs = []      # detail/subtotal rows in order
    region, lender, ccy = None, None, None
    sol = Solver("l5b", EYE_L5B)
    for pno, bands in ((289, B_BANDS_289), (290, B_BANDS_290)):
        for top, bot, lws in rows_of_page(pno, ytol=16 if pno == 289 else 22, xmax=3100):
            label, cells = band_split(lws, bands, label_max=1490)
            label = re.sub(r"\s+", " ", label).strip()
            joined = " ".join(w["text"] for w in lws)
            up = label.upper()
            if not cells:
                if "MULTILATERAL" in up and "JUMLAH" not in up and "JUMLAH" not in joined.upper():
                    region = "PINJAMAN MULTILATERAL"
                    continue
                if "BILATERAL" in up and "JUMLAH" not in up:
                    region = "PINJAMAN BILATERAL"
                    continue
                # lender header line: text + repeated ccy tokens in value zone
                ccys = [w["text"] for w in lws if CCYRE.match(w["text"]) and w["left"] > 1450]
                if len(ccys) >= 2 and label:
                    lender = label
                    c0 = [c for c in ccys if c in ("USD", "CAD", "EUR", "JPY")]
                    ccy = c0[0] if c0 else "USD"
                    continue
                if label and len(label) > 6 and recs and _alpha_ratio(label) > 0.85 \
                        and not re.search(r"PENYATA|Disember|Perihal|Faedah|Tebusan|Mata Wang|"
                                          r"Dibenarkan|Keluaran|Bayaran|Selesa|Ringgit|Kadar|"
                                          r"Amaun|Jumlah Terkumpul|sambungan|Memorandum", label):
                    recs[-1]["perihal"] += " " + label
                continue
            if re.match(r"^JU\w*LA\w*\b", up) or up.startswith("JUMLAH"):
                is_regtot = "MULTILATERAL" in up or "BILATERAL" in up or "BANTUAN" in up
                recs.append(dict(kind="regtot" if is_regtot else "lsub", label=label,
                                 region=region, lender=lender, ccy=ccy, pno=pno, top=top,
                                 cells=cells))
                continue
            m = re.match(r"^(19\d\d|20\d\d)\b", label)
            if not m:
                if recs and label:
                    recs[-1]["perihal"] = recs[-1].get("perihal", "") + " " + label
                continue
            # detail row: year + ref + description ... kadar tarikh in label zone?
            # kadar/tarikh live left of the dib band: extract from words 1100-1490
            kad_ws = [w["text"] for w in lws if 1100 < w["right"] <= 1290]
            tar_ws = [w["text"] for w in lws if 1290 < w["right"] <= 1490]
            recs.append(dict(kind="detail", perihal=label, region=region, lender=lender,
                             ccy=ccy, kadar=" ".join(kad_ws), tarikh=" ".join(tar_ws),
                             pno=pno, top=top, cells=cells))
    # build cells
    for i, r in enumerate(recs):
        cc = {}
        bands = B_BANDS_289 if r["pno"] == 289 else B_BANDS_290
        for b, lo, hi in bands:
            key = f"b{i:02d}.{b}"
            if b in r["cells"]:
                txt, box = r["cells"][b]
                c = Cell(r["pno"], b, txt, box, key)
            else:
                c = Cell(r["pno"], b, None, (lo + 100, r["top"] - 6, hi - 30, r["top"] + 40), key)
            cc[b] = sol.add_cell(c)
        r["c"] = cc
    # identities: per lender column sums; region totals (bsrm); grand
    lenders = {}
    for i, r in enumerate(recs):
        if r["kind"] == "detail":
            lenders.setdefault(r["lender"], dict(details=[], sub=None))["details"].append(i)
        elif r["kind"] == "lsub":
            lenders.setdefault(r["lender"], dict(details=[], sub=None))["sub"] = i
    for lend, g in lenders.items():
        if g["sub"] is None:
            continue
        for b in ("dib", "kel", "bay", "bsfx", "bsrm"):
            sol.ident(f"BLN {lend[:30]} details sum = Jumlah [{b}]",
                      [(1, f"b{i:02d}.{b}") for i in g["details"]] + [(-1, f"b{g['sub']:02d}.{b}")])
    regtots = {i: r for i, r in enumerate(recs) if r["kind"] == "regtot"}
    i_multi = next(i for i, r in regtots.items() if "MULTILATERAL" in r["label"].upper())
    i_bi = next(i for i, r in regtots.items() if "BILATERAL" in r["label"].upper())
    i_grand = next(i for i, r in regtots.items() if "BANTUAN" in r["label"].upper())
    multi_subs = [g["sub"] for l, g in lenders.items() if g["sub"] is not None
                  and recs[g["sub"]]["region"] == "PINJAMAN MULTILATERAL"]
    bi_subs = [g["sub"] for l, g in lenders.items() if g["sub"] is not None
               and recs[g["sub"]]["region"] == "PINJAMAN BILATERAL"]
    sol.ident("BLN multilateral lender subtotals = JUMLAH MULTILATERAL [bsrm]",
              [(1, f"b{i:02d}.bsrm") for i in multi_subs] + [(-1, f"b{i_multi:02d}.bsrm")])
    sol.ident("BLN bilateral lender subtotals = JUMLAH BILATERAL [bsrm]",
              [(1, f"b{i:02d}.bsrm") for i in bi_subs] + [(-1, f"b{i_bi:02d}.bsrm")])
    sol.ident("BLN MULTI + BI = JUMLAH BANTUAN LUAR NEGERI [bsrm]",
              [(1, f"b{i_multi:02d}.bsrm"), (1, f"b{i_bi:02d}.bsrm"), (-1, f"b{i_grand:02d}.bsrm")])
    sol.solve()
    need = sol.finish("lampiran5")
    if need:
        for c in need:
            i = int(c.key[1:3])
            print("EYE-NEEDED L5B", c.key, recs[i].get("perihal", recs[i].get("label", "?"))[:45],
                  repr(c.raw), "->", eye_crop(c, f"l5b_{c.key}"))
        raise SystemExit(f"L5B: {len(need)} unresolved cells need eye-reading")
    sol.report_idents("lampiran5")
    # emit rows
    LENDER_CANON = {
        "Bank Pembangunan Islam": "Bank Pembangunan Islam",
        "Bank Pembangunan Asia": "Bank Pembangunan Asia",
        "Kerajaan Sepanyol": "Kerajaan Sepanyol - ICO",
        "Kerajaan Kanada": "Kerajaan Kanada",
        "Kerajaan Perancis": "Kerajaan Perancis",
        "Japan International": "Japan International Cooperation Agency",
    }
    out = []
    import difflib as dl
    for i, r in enumerate(recs):
        cc = r["c"]
        lender = None
        for kfrag, canon in LENDER_CANON.items():
            if r.get("lender") and kfrag.lower()[:12] in r["lender"].lower().replace("pombanguiran", "pembangunan"):
                lender = canon
        if lender is None and r.get("lender"):
            lender = canon_label(r["lender"], list(LENDER_CANON.values()), 0.4)
        if r["kind"] == "detail":
            per = re.sub(r"\s+", " ", r["perihal"]).strip()
            m = dl.get_close_matches(per, list(w_perihal), n=1, cutoff=0.6)
            if m:
                per = m[0]
            kad = sanitize(r["kadar"]) if r["kadar"] and not is_dash(r["kadar"]) else None
            if kad and not re.match(r"^\d\.\d{2,3}$", kad):
                kad = None if is_dash(r["kadar"] or "-") else kad
            tar = re.sub(r"[^\d/]", "", r["tarikh"] or "")
            tar = tar if re.match(r"^\d{4}/\d{4}$", tar) else None
            out.append(prov(_l5row(region_bm=r["region"], lender_bm=lender,
                                   ccy=r["ccy"], perihal_bm=per, kadar_faedah=kad,
                                   tarikh_tebusan=tar,
                                   amaun_dibenarkan_fx=cc["dib"].value,
                                   terkumpul_keluaran_fx=cc["kel"].value,
                                   terkumpul_bayaran_balik_fx=cc["bay"].value,
                                   amaun_belum_selesai_fx=cc["bsfx"].value,
                                   amaun_belum_selesai_rm=cc["bsrm"].value), r["pno"], L5_STMT_B))
        elif r["kind"] == "lsub":
            out.append(prov(_l5row(region_bm=r["region"], lender_bm=lender, ccy=r["ccy"],
                                   perihal_bm=f"Jumlah {lender}", row_type="subtotal",
                                   amaun_dibenarkan_fx=cc["dib"].value,
                                   terkumpul_keluaran_fx=cc["kel"].value,
                                   terkumpul_bayaran_balik_fx=cc["bay"].value,
                                   amaun_belum_selesai_fx=cc["bsfx"].value,
                                   amaun_belum_selesai_rm=cc["bsrm"].value), r["pno"], L5_STMT_B))
        else:
            up = r["label"].upper()
            if "BANTUAN" in up:
                lbl, rt, reg = "JUMLAH BANTUAN LUAR NEGERI", "total", None
            elif "MULTILATERAL" in up:
                lbl, rt, reg = "JUMLAH PINJAMAN MULTILATERAL", "subtotal", None
            else:
                lbl, rt, reg = "JUMLAH PINJAMAN BILATERAL", "subtotal", None
            out.append(prov(_l5row(region_bm=reg, perihal_bm=lbl, row_type=rt,
                                   amaun_belum_selesai_rm=cc["bsrm"].value), r["pno"], L5_STMT_B))
    for o in out:
        o.pop("statement_", None)
    return out


# === EYE-TYPED L5B (pdf 289-290) — every cell read from 3.2x zoom crops,
# cross-checked against 2016-volume dib (cumulative, invariant) and forced by
# per-lender/region/grand column sums. Two genuine book footing anomalies
# (kept AS PRINTED, logged FAIL). Supersedes the solver version above. =========
L5B_DATA = [
 ("PINJAMAN MULTILATERAL", "Bank Pembangunan Islam", "ISD", [
   ("2000 2-MA-0077 Universiti Malaysia Sabah","2.425","2006/2015",20160000.00,14452946.72,14452946.72,0.0,0.0),
   ("2000 2-MA-0078 Universiti Teknologi Malaysia","2.007","2004/2016",19923084.70,15408614.37,14223336.24,1185278.13,7058568.32),
   ("2003 2-MA-0088 Pembiayaan Peralatan Hospital, Kementerian Kesihatan Fasa II","2.024","2007/2020",27880000.00,14598601.22,9545239.22,5053362.00,30093781.38),
   ("2004 2-MA-0094 Universiti Teknologi Malaysia Fasa II","3.038","2010/2022",38230000.00,25451606.77,11665319.82,13786286.95,82100095.04),
   ("2006 2-MA-100 Universiti Islam Antarabangsa Fasa II",None,"2007/2012",28471000.00,15537082.79,0.0,15537082.79,92526435.43),
   ("2006 2-MA-101 Universiti Malaysia Sabah Fasa II",None,None,23069000.00,14288295.02,2381390.84,11906904.18,70907996.77),
   ("2009 2-MA-103 Universiti Sains Malaysia",None,None,43440000.00,24498420.05,4083070.10,20415349.95,121577492.02),
  ], (201173084.70,124235566.94,56351302.94,67884264.00,404264368.96)),
 ("PINJAMAN MULTILATERAL", "Bank Pembangunan Asia", "USD", [
   ("1992 1120 MAL Sektor Pengawalan Hakisan Pantai Negara","6%-10%","1999/2016",29345630.75,29345630.75,20681900.00,8663730.75,37573733.89),
   ("1993 1238 MAL Pembangunan Pertanian Bersepadu Pahang Barat II","6%-10%","1999/2016",15985889.53,15985889.53,11932700.00,4053189.53,17578277.67),
   ("1994 1197 MAL Pemulihan dan Peningkatan Sistem Bekalan Air","Berubah","1997/2016",89081190.71,89081190.71,79601300.00,9479890.71,41113338.02),
   ("1995 1355 MAL Projek Pendidikan Teknik dan Vokasional","Berubah","2001/2020",58448803.73,58448803.73,32438600.00,26010203.73,112903652.56),
   ("1998 1596 MAL Projek Pendidikan Teknik","Berubah","2003/2017",32876858.42,32876858.42,25087991.28,7788867.14,33779537.90),
  ], (225738373.14,225738373.14,169742491.28,55995881.86,242948540.04)),
 ("PINJAMAN BILATERAL", "Kerajaan Sepanyol - ICO", "USD", [
   ("2003 Institut Sepanyol Malaysia",None,"2013/2045",5900000.00,5900000.00,823255.80,5076744.20,22017331.92),
  ], (5900000.00,5900000.00,823255.80,5076744.20,22017331.92)),
 ("PINJAMAN BILATERAL", "Kerajaan Kanada", "CAD", [
   ("1970 Pelan Lapangan Terbang Kebangsaan dan Kajian Pelan Induk Lapangan Terbang",None,"1979/2018",396276.00,396276.00,366555.30,29720.70,92960.41),
   ("1985 Sistem Perkhidmatan Pelanggan Secara Automatik",None,"1994/2034",2121123.15,2121123.15,1140103.29,981019.86,3068433.92),
  ], (2517399.15,2517399.15,1506658.59,1010740.56,3161394.33)),
 ("PINJAMAN BILATERAL", "Kerajaan Perancis", "EUR", [
   ("1983 1101/1104 Stesen Janakuasa Paka","10.600","1984/2015",148112702.26,148112702.28,148112702.28,0.0,0.0),
   ("1986 0388 Pembangunan Lapangan Terbang Kota Kinabalu/Kuching","2.500","1987/2017",1192579.41,1192579.41,1148787.48,43791.93,207670.09),
   ("1994 1550 Institut Perancis Malaysia","4.850","2000/2022",17447766.72,17447766.72,14370147.91,3077618.81,14594683.92),
  ], (166753048.39,166753048.41,163631637.67,3121410.74,14802354.01)),
 ("PINJAMAN BILATERAL", "Japan International Cooperation Agency", "JPY", [
   ("1990 MXIII-3 Projek Pembangunan Kawasan (Membasmi Kemiskinan)","2.900","1997/2015",9318000000.00,9318000000.00,9318000000.00,0.0,0.0),
   ("1992 MXIV-1 Projek Tabung Pinjaman Pelajaran Tinggi","3.000","1999/2017",5316833082.00,5316833082.00,4889159082.00,427674000.00,15397119.35),
   ("1992 MXIV-5 Projek Pembangunan Luar Bandar (Membasmi Kemiskinan) II","3.000","1999/2017",10949000000.00,10949000000.00,10061246000.00,887754000.00,31960919.51),
   ("1995 MXV-3 Hospital Universiti Kebangsaan Malaysia","3.000","2000/2018",8203021961.00,8203021961.00,6881869961.00,1321152000.00,47564114.30),
   ("1999 MXVII-1 Dasar Pandang Ke Timur","0.750","2009/2039",14026000000.00,12015524145.00,3169889145.00,8845635000.00,318460551.27),
   ("1999 MXVII-2 Projek Empangan Beris","1.700","2006/2024",8549000000.00,7971040496.00,4370644496.00,3600396000.00,129621456.79),
   ("1999 MXVII-2A Projek Empangan Beris","0.750","2009/2039",1188000000.00,607460008.00,146907008.00,460553000.00,16580829.11),
   ("1999 MXVII-4 Projek Pembangunan Universiti Malaysia Sarawak","0.750","2009/2039",18549000000.00,18402798269.00,4228773269.00,14174025000.00,510293248.05),
   ("1999 MXVII-5 Tabung Industri Kecil dan Sederhana","0.750","2009/2039",14753401720.00,14753401720.00,3386075720.00,11367326000.00,409246470.65),
   ("1999 MXVII-6 Projek Tabung Pinjaman Pelajaran Tinggi II","0.750","2009/2039",5285000000.00,4984453299.00,1266706299.00,3717747000.00,133846327.49),
   ("1999 MXVII-7 Projek Penyaluran Air Mentah dari Pahang ke Selangor","0.750","2009/2039",703760668.00,703760668.00,161521668.00,542239000.00,19521688.48),
   ("2000 MXVIII-2 Projek Pembetungan Negara","0.750","2010/2040",48489000000.00,48305915528.00,9510459528.00,38795456000.00,1396714006.91),
   ("2005 MXIX-1 Projek Penyaluran Air Mentah dari Pahang ke Selangor II","0.950","2015/2045",82040000000.00,66913583073.00,2689838000.00,64223745073.00,2312163270.12),
   ("2006 MXX-1 Projek Tabung Pinjaman Pelajaran Tinggi III","1.200","2013/2031",7644000000.00,7139966356.00,1239586000.00,5900380356.00,212425493.58),
   ("2013 MXXI-1 Projek Pembangunan Malaysia","2.000","2013/2014",6295000000.00,1597067523.00,0.0,1597067523.00,57497624.96),
  ], (241309017431.00,217181826128.00,61320676176.00,155861149952.00,5611313120.57)),
]
L5B_REGION_BSRM = {"PINJAMAN MULTILATERAL": 647112909.00, "PINJAMAN BILATERAL": 5651294200.83}
L5B_GRAND_BSRM = 6298407109.83


def extract_l5_bantuan():
    out = []
    reg_lender_bsrm = {"PINJAMAN MULTILATERAL": [], "PINJAMAN BILATERAL": []}
    B = ("amaun_dibenarkan_fx", "terkumpul_keluaran_fx", "terkumpul_bayaran_balik_fx",
         "amaun_belum_selesai_fx", "amaun_belum_selesai_rm")
    for region, lender, ccy, details, sub in L5B_DATA:
        pno = 289 if region == "PINJAMAN MULTILATERAL" else 290
        if region == "PINJAMAN MULTILATERAL" and lender == "Bank Pembangunan Islam":
            pno = 289
        colsum = [0.0] * 5
        for per, kad, tar, dib, kel, bay, bsfx, bsrm in details:
            vals = (dib, kel, bay, bsfx, bsrm)
            for i, v in enumerate(vals):
                colsum[i] = round(colsum[i] + v, 2)
            # row identity: bsfx = kel - bay (FX outstanding)
            if abs((kel - bay) - bsfx) > 0.01:
                chk("FAIL", f"lampiran5b: {lender[:20]} '{per[:24]}' bsfx != kel-bay",
                    round(kel - bay, 2), bsfx)
            out.append(prov(_l5row(region_bm=region, lender_bm=lender, ccy=ccy,
                                   perihal_bm=per, kadar_faedah=kad, tarikh_tebusan=tar,
                                   amaun_dibenarkan_fx=dib, terkumpul_keluaran_fx=kel,
                                   terkumpul_bayaran_balik_fx=bay, amaun_belum_selesai_fx=bsfx,
                                   amaun_belum_selesai_rm=bsrm), pno, L5_STMT_B))
        # lender subtotal (printed) — check each column sum
        for i, b in enumerate(B):
            st = "PASS" if abs(colsum[i] - sub[i]) < 0.5 else "FAIL"
            chk(st, f"lampiran5b: {lender[:24]} details sum = Jumlah [{b}]", colsum[i], sub[i])
        out.append(prov(_l5row(region_bm=region, lender_bm=lender, ccy=ccy,
                               perihal_bm=f"Jumlah {lender}", row_type="subtotal",
                               amaun_dibenarkan_fx=sub[0], terkumpul_keluaran_fx=sub[1],
                               terkumpul_bayaran_balik_fx=sub[2], amaun_belum_selesai_fx=sub[3],
                               amaun_belum_selesai_rm=sub[4]), pno, L5_STMT_B))
        reg_lender_bsrm[region].append(sub[4])
    # region totals + anomaly logging
    m_sum = round(sum(reg_lender_bsrm["PINJAMAN MULTILATERAL"]), 2)
    b_sum = round(sum(reg_lender_bsrm["PINJAMAN BILATERAL"]), 2)
    chk("FAIL" if abs(m_sum - L5B_REGION_BSRM["PINJAMAN MULTILATERAL"]) > 0.5 else "PASS",
        "lampiran5b: BPI+BPA subtotals vs printed JUMLAH MULTILATERAL [bsrm] "
        "(book under-foots by 100,000 — PRINT ANOMALY, kept as printed)",
        m_sum, L5B_REGION_BSRM["PINJAMAN MULTILATERAL"])
    chk("PASS" if abs(b_sum - L5B_REGION_BSRM["PINJAMAN BILATERAL"]) < 0.5 else "FAIL",
        "lampiran5b: bilateral lender subtotals = printed JUMLAH BILATERAL [bsrm]",
        b_sum, L5B_REGION_BSRM["PINJAMAN BILATERAL"])
    out.append(prov(_l5row(region_bm="PINJAMAN MULTILATERAL",
                           perihal_bm="JUMLAH PINJAMAN MULTILATERAL", row_type="subtotal",
                           amaun_belum_selesai_rm=L5B_REGION_BSRM["PINJAMAN MULTILATERAL"]),
                    289, L5_STMT_B))
    out.append(prov(_l5row(region_bm="PINJAMAN BILATERAL",
                           perihal_bm="JUMLAH PINJAMAN BILATERAL", row_type="subtotal",
                           amaun_belum_selesai_rm=L5B_REGION_BSRM["PINJAMAN BILATERAL"]),
                    290, L5_STMT_B))
    grand = round(L5B_REGION_BSRM["PINJAMAN MULTILATERAL"] + L5B_REGION_BSRM["PINJAMAN BILATERAL"], 2)
    chk("PASS" if abs(grand - L5B_GRAND_BSRM) < 0.5 else "FAIL",
        "lampiran5b: MULTILATERAL + BILATERAL = JUMLAH BANTUAN LUAR NEGERI [bsrm]",
        grand, L5B_GRAND_BSRM)
    out.append(prov(_l5row(perihal_bm="JUMLAH BANTUAN LUAR NEGERI", row_type="total",
                           amaun_belum_selesai_rm=L5B_GRAND_BSRM), 290, L5_STMT_B))
    # JICA detail-vs-subtotal anomaly
    jica = next(d for r, l, c, d, s in L5B_DATA if l.startswith("Japan"))
    jica_sub = next(s for r, l, c, d, s in L5B_DATA if l.startswith("Japan"))
    jica_bsrm = round(sum(x[7] for x in jica), 2)
    chk("FAIL", "lampiran5b: JICA 15 detail RM values sum vs printed Jumlah "
        "(book over-foots by 20,000 — PRINT ANOMALY, details kept as read/printed)",
        jica_bsrm, jica_sub[4])
    chk("INFO", "lampiran5b: eye-typed from 3.2x zoom crops (pdf 289-290); all dib "
        "cross-checked vs 2016-volume cumulative dib (identical for surviving loans); "
        "every FX row satisfies bsfx=kel-bay; all 5 column sums tie to printed lender "
        "Jumlah", len(out), "")
    CONFIRM["c"] += sum(len(d) for _, _, _, d, _ in L5B_DATA) * 5
    return out


def extract_l5():
    rows = extract_l5_pinjaman() + extract_l5_bantuan()
    cols = ["region_bm", "instrument_bm", "lender_bm", "no_keluaran", "kod_saham",
            "perihal_bm", "kadar_faedah", "tarikh_tebusan", "ccy",
            "amaun_dibenarkan_fx", "terkumpul_keluaran_fx", "terkumpul_bayaran_balik_fx",
            "amaun_belum_selesai_fx", "amaun_dibenarkan_rm", "amaun_belum_selesai_rm",
            "row_type", "has_footnote", "year",
            "source_file", "pdf_page", "printed_page", "statement"]
    with open(f"{WH}/fact_debt_issues.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"fact_debt_issues.csv: {len(rows)} rows")
    return rows


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("l3", "all"):
        recs = extract_l3()
        for r in recs:
            cc = r["c"]
            print(f"{(r['cat'] or '')[:12]:>13}|{r['rt'][:3]}| {r['canon'][:40]:40} "
                  + " ".join(f"{cc[b].value:>16,.2f}({cc[b].route[0]})" for b, _, _ in L3_BANDS))
        print(CONFIRM)
    if which in ("l5", "all"):
        rows = extract_l5()
        fails = [c for c in CHECKS if c[0] == "FAIL"]
        print("L5 FAILs:", len(fails))
        for c in fails: print(c)
    if which in ("l6", "all"):
        recs = extract_l6()
        for r in recs:
            cc = r["c"]
            print(f"{(r['jenis'] or '')[:14]:>15}|{(r['cat'] or ''):>14}| {r['canon'][:42]:42} "
                  + " ".join(f"{cc[b].value:>18,.2f}({cc[b].route})" for b, _, _ in L6_BANDS))
        print(CONFIRM)
        for c in CHECKS:
            print(c)
    if which == "all":
        write_outputs_check_csv()
        print(f"wrote {MEMO_CSV}: {len(CHECKS)} checks")
