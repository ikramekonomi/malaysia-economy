#!/usr/bin/env python3
"""Extract Lampiran 3/4/5/I memorandum registers from PKKP FY2012.

Outputs to /home/claude/pkkp/warehouse2012/:
  fact_loans_receivable.csv        Lampiran 3  pdf 243-245  printed 221-223
  fact_investments.csv             Lampiran 4  pdf 249-252  printed 227-230
  fact_statutory_guarantees.csv    Lampiran 5  pdf 255      printed 233
  fact_timeseries_2003_2012.csv    Lampiran I  pdf 260-262  printed 238-240

Conventions: exact RM incl sen; dash -> 0.0; parens -> negative; '*' -> footnote.
printed_page = pdf_page - 22.  One row per item (year=2012), 2011 column dropped
for the memoranda tables.  Timeseries: 10 rows per line item.
"""
import re
import csv
import pandas as pd
import pdfplumber

WORK = '/home/claude/pkkp/work/2012'
WH = '/home/claude/pkkp/warehouse2012'
SRC = '2012_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf'
YEAR = 2012

pages = open(f'{WORK}/full.txt').read().split('\f')
_pdf = pdfplumber.open(f'{WORK}/2012.pdf')

DASH = '–'
AMT = re.compile(r'^\(?[\d,]+\.\d{2}\)?$')          # money w/ sen, opt parens
AMT_INT = re.compile(r'^\(?\d{1,3}(?:,\d{3})+\)?$')  # integer w/ thousands


def is_val(tok):
    return tok in (DASH, '-', '—') or AMT.match(tok) or AMT_INT.match(tok)


def amt(tok):
    if tok is None or tok == '':
        return None
    if tok in (DASH, '-', '—'):
        return 0.0
    neg = tok.startswith('(') and tok.endswith(')')
    v = float(tok.strip('()').replace(',', ''))
    return -v if neg else v


def prov(row, pno, pp, stmt):
    row['source_file'] = SRC
    row['pdf_page'] = pno
    row['printed_page'] = pp
    row['statement'] = stmt
    return row


def raw_page_lines(pno):
    """Clean text lines from full.txt for a page (headers/footers stripped)."""
    out = []
    for ln in pages[pno - 1].split('\n'):
        s = ln.replace('!', '').rstrip()
        st = s.strip()
        if not st:
            continue
        if '.indd' in st:
            continue
        if re.match(r'^Penyata Akaun Memorandum', st):
            continue
        if re.match(r'^[Pp]ada 31 Disember', st):
            continue
        if re.match(r'^\(disambung', st) or re.match(r'^\(sambungan', st):
            continue
        if re.fullmatch(r'\d{1,3}', st):
            continue
        out.append(st)
    return out


def split_label_vals(line):
    toks = line.split()
    vals = []
    while toks and is_val(toks[-1]):
        vals.insert(0, toks.pop())
    return ' '.join(toks), vals


# ===========================================================================
# 1. Lampiran 3 : Pinjaman Boleh Dituntut  (pdf 243-245)
# ===========================================================================
def extract_loans():
    stmt = 'Lampiran 3 Penyata Akaun Memorandum Pinjaman Boleh Dituntut'
    pageinfo = {243: 221, 244: 222, 245: 223}
    HDR = re.compile(r'^(Peminjam|Baki Pinjaman Mengikut|Pembangunan\b|Hasil Disatukan\b|'
                     r'Baki Belum Selesai|RM(\s+RM)*$|2012\s+2011$)')
    rows = []
    cat_no = cat = None
    for pno, pp in pageinfo.items():
        for st in raw_page_lines(pno):
            if HDR.match(st):
                continue
            m = re.match(r'^([IVX]+)\.\s+(.*)$', st)
            if m:
                cat_no = m.group(1)
                cat = re.sub(r'\s*-?\s*\(SAMB\.?\)\s*$', '', m.group(2), flags=re.I).strip()
                continue
            label, vals = split_label_vals(st)
            if not vals:
                # wrapped borrower-name continuation
                if rows and rows[-1]['row_type'] == 'detail':
                    rows[-1]['peminjam_bm'] += ' ' + label
                continue
            if len(vals) != 5:
                raise ValueError(f'loans p{pno} vals={len(vals)}: {st!r}')
            label = label.replace('*', '').strip()
            if label == 'JUMLAH PINJAMAN BOLEH DITUNTUT':
                rt, sec, cn, cb = 'total', None, None, None
            elif label.startswith('Jumlah '):
                rt, sec, cn, cb = 'subtotal', 'PINJAMAN', cat_no, cat
            else:
                rt, sec, cn, cb = 'detail', 'PINJAMAN', cat_no, cat
            rows.append(prov(dict(
                section_bm=sec, category_no=cn, category_bm=cb, peminjam_bm=label,
                row_type=rt, year=YEAR,
                pembangunan_rm=amt(vals[0]), hasil_disatukan_rm=amt(vals[1]),
                amanah_lain_rm=amt(vals[2]), baki_belum_selesai_rm=amt(vals[3])),
                pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_loans_receivable.csv', index=False)
    return df


# ===========================================================================
# 3. Lampiran 5 : Jaminan Berkanun  (pdf 255)
# ===========================================================================
def extract_statutory():
    stmt = 'Lampiran 5 Penyata Akaun Memorandum Jaminan Berkanun'
    pno, pp = 255, 233
    type_headers = ('JAMINAN PENCARUM / PENDEPOSIT', 'JAMINAN PINJAMAN')
    rows = []
    jenis = cat = None
    HDR = re.compile(r'^(Agensi|Dalam Negeri|Luar Negeri|Jumlah$|2012\s+2011$|RM(\s+RM)*$)')
    for st in raw_page_lines(pno):
        if HDR.match(st):
            continue
        label, vals = split_label_vals(st)
        if not vals:
            if label in type_headers:
                jenis, cat = label, None
            elif label in ('Badan Berkanun', 'Syarikat'):
                cat = label
            elif rows and rows[-1]['row_type'] == 'detail':
                rows[-1]['agensi_bm'] += ' ' + label
            continue
        if len(vals) != 4:
            raise ValueError(f'guar p{pno} vals={len(vals)}: {st!r}')
        label = label.replace('*', '').strip()
        if label.startswith('Jumlah '):
            rt, c, j = 'subtotal', cat, jenis
        elif label.startswith('JUMLAH JAMINAN PENCARUM') or label == 'JUMLAH JAMINAN PINJAMAN':
            rt, c, j = 'subtotal', None, jenis
        elif label == 'JUMLAH JAMINAN':
            rt, c, j = 'total', None, None
        else:
            rt, c, j = 'detail', cat, jenis
        rows.append(prov(dict(
            jenis_jaminan_bm=j, kategori_bm=c, agensi_bm=label, row_type=rt, year=YEAR,
            dalam_negeri_rm=amt(vals[0]), luar_negeri_rm=amt(vals[1]),
            jumlah_rm=amt(vals[2])), pno, pp, stmt))
    df = pd.DataFrame(rows)
    df.to_csv(f'{WH}/fact_statutory_guarantees.csv', index=False)
    return df


# ===========================================================================
# 2. Lampiran 4 : Pelaburan  (pdf 249-252)  -- pdfplumber x-zone parse
# ===========================================================================
def extract_investments():
    stmt = 'Lampiran 4 Penyata Akaun Memorandum Pelaburan'
    PAGES = {249: 227, 250: 228, 251: 229, 252: 230}
    SECTIONS = {'AGENSI ANTARABANGSA', 'BADAN BERKANUN', 'SYARIKAT'}
    IAMT = re.compile(r'^[\d,]+\.\d{2}$')
    CCY = re.compile(r'^[A-Z]{3}$|^Baht$')
    FN = re.compile(r'^\((\d)\)$')

    def iamt(tok):
        if tok is None:
            return None
        if tok in (DASH, '-'):
            return 0.0
        return float(tok.replace(',', ''))

    def group_lines(words, gap=3.0):
        words = sorted(words, key=lambda w: (w['top'], w['x0']))
        lines, cur, cur_top = [], [], None
        for w in words:
            if cur and w['top'] - cur_top > gap:
                lines.append(sorted(cur, key=lambda x: x['x0']))
                cur = []
            cur.append(w)
            cur_top = w['top'] if cur_top is None or len(cur) == 1 else max(cur_top, w['top'])
        if cur:
            lines.append(sorted(cur, key=lambda x: x['x0']))
        return lines

    def classify(w, dx):
        x0, x1, t = w['x0'] - dx, w['x1'] - dx, w['text']
        if x1 <= 255:
            if IAMT.match(t) and x1 > 195:
                return 'modal_amt'
            if CCY.match(t) and x0 > 150:
                return 'modal_ccy'
            if t == DASH and x0 > 195:
                return 'modal_dash'
            return 'entity'
        if x0 < 358:
            return 'perihal'
        if x1 <= 432:
            return 'nominal_ccy' if CCY.match(t) else 'nominal'
        if x1 <= 456:
            return 'pct'
        if x1 <= 512:
            return 'nb2012'
        return 'nb2011'

    records = []
    section = None
    cur_entity = None
    for pno, pp in PAGES.items():
        page = _pdf.pages[pno - 1]
        words = [w for w in page.extract_words(keep_blank_chars=False)
                 if w.get('upright', True) and w['x0'] >= 0 and w['x1'] <= page.width + 5]
        pct_hdr = [w for w in words if w['text'].rstrip('!') == '%' and w['top'] < 260]
        dx = pct_hdr[0]['x0'] - 441.1
        body = [w for w in words if 163 < w['top'] < 825
                and not (re.fullmatch(r'\d{1,3}', w['text']) and (w['x0'] - dx > 565 or w['x0'] < 70))]
        in_nota = False
        for ln in group_lines(body):
            texts = [w['text'] for w in ln]
            joined = ' '.join(texts).replace('!', '')
            if joined.startswith('Nota'):
                in_nota = True
            if in_nota:
                continue
            if set(t.strip('!') for t in texts) <= {'RM', '%', ''}:
                continue
            if joined.startswith(('(disambung', '(sambungan', 'Penyata Akaun', 'pada 31')) \
               or re.match(r'^\d+$', joined):
                continue
            zones = {}
            for w in ln:
                if w['text'].strip('!') == '':
                    continue
                zones.setdefault(classify(dict(w, text=w['text'].replace('!', '') or w['text']), dx),
                                 []).append(w['text'].replace('!', ''))
            ent_words = [t for t in zones.get('entity', []) if not FN.match(t)]
            fns = [FN.match(t).group(1) for t in zones.get('entity', []) if FN.match(t)]
            ent_txt = ' '.join(ent_words)
            has_values = any(z in zones for z in ('nominal', 'pct', 'nb2012', 'nb2011'))
            norm = re.sub(r'\s*[–-]\s*\(SAMB\.?\)\s*$', '', joined).strip()
            if norm in SECTIONS and not has_values and not zones.get('perihal'):
                section = norm
                cur_entity = None
                continue
            if not has_values:
                if ent_txt and cur_entity is not None:
                    cur_entity['name'] += ' ' + ent_txt
                if fns and cur_entity is not None:
                    cur_entity['fns'] += fns
                if zones.get('perihal') and records and 'perihal' in records[-1]:
                    records[-1]['perihal'] += ' ' + ' '.join(zones['perihal'])
                continue
            if ent_txt.startswith(('Jumlah', 'JUMLAH')):
                records.append(dict(section=section, kind='agg', label=ent_txt,
                                    nb2012=zones.get('nb2012', [None])[0],
                                    pdf_page=pno, printed_page=pp))
                cur_entity = None
                continue
            if zones.get('modal_amt') or zones.get('modal_dash'):
                cur_entity = dict(name=ent_txt, fns=fns,
                                  modal_ccy=zones.get('modal_ccy', ['RM'])[0],
                                  modal=(zones.get('modal_amt', [None])[0]
                                         or (DASH if zones.get('modal_dash') else None)))
            else:
                if ent_txt and cur_entity is not None:
                    cur_entity['name'] += ' ' + ent_txt
                if fns and cur_entity is not None:
                    cur_entity['fns'] += fns
            records.append(dict(section=section, kind='detail', entity=cur_entity,
                                perihal=' '.join(zones.get('perihal', [])),
                                nominal_ccy=zones.get('nominal_ccy', [None])[0],
                                nominal=zones.get('nominal', [None])[0],
                                pct=zones.get('pct', [None])[0],
                                nb2012=zones.get('nb2012', [None])[0],
                                pdf_page=pno, printed_page=pp))

    # normalise trailing footnote markers on entity names
    seen = set()
    for r in records:
        e = r.get('entity')
        if e is None or id(e) in seen:
            continue
        seen.add(id(e))
        m = re.search(r'\s*\((\d)\)$', e['name'])
        if m:
            e['name'] = e['name'][:m.start()]
            e['fns'].append(m.group(1))
        m = re.search(r'(\*+)$', e['name'])
        if m:
            e['name'] = e['name'][:m.start()].rstrip()
            e['fns'].append(m.group(1))

    rows = []
    for r in records:
        if r['kind'] == 'agg':
            rt = 'total' if r['label'].startswith('JUMLAH') else 'subtotal'
            base = dict(section_bm=r['section'] if rt == 'subtotal' else None,
                        entiti_bm=r['label'], perihal=None, modal_saham_ccy=None,
                        modal_saham_amt=None, nilai_nominal_ccy=None, nilai_nominal_amt=None,
                        pegangan_pct=None, row_type=rt, has_footnote=False, footnote_ref=None)
        else:
            e = r['entity']
            nom_ccy = r['nominal_ccy'] or ('RM' if r['nominal'] else None)
            base = dict(section_bm=r['section'], entiti_bm=e['name'], perihal=r['perihal'],
                        modal_saham_ccy=e['modal_ccy'] if e['modal'] else None,
                        modal_saham_amt=iamt(e['modal']),
                        nilai_nominal_ccy=nom_ccy if (r['nominal'] and r['nominal'] != DASH) else None,
                        nilai_nominal_amt=iamt(r['nominal']),
                        pegangan_pct=iamt(r['pct']) if r['pct'] not in (DASH, '-', None) else None,
                        row_type='detail',
                        has_footnote=bool(e['fns']),
                        footnote_ref=','.join(e['fns']) if e['fns'] else None)
        rows.append(prov(dict(base, year=YEAR, nilai_buku_rm=iamt(r['nb2012'])),
                         r['pdf_page'], r['printed_page'], stmt))
    df = pd.DataFrame(rows)
    df['footnote_ref'] = df['footnote_ref'].astype('string')
    df.to_csv(f'{WH}/fact_investments.csv', index=False)
    return df


# ===========================================================================
# 4. Lampiran I : Perangkaan Kewangan 2003-2012 (pdf 260-262) timeseries
# ===========================================================================
def extract_timeseries():
    stmt = 'Lampiran I Perangkaan Kewangan Kerajaan Persekutuan'
    NUMTOK = re.compile(r"^\(?[\d,]+(?:\.\d+)?\)?$|^[–—-]$")
    JUNK = re.compile(r"^(Perangkaan Kewangan|\(dalam RM juta\)|\( ?s ?ambungan|LAMPIRAN|\d{1,3}$|\($)")

    def parse_amount(tok):
        tok = tok.strip()
        if tok in {"–", "-", "—"}:
            return 0.0
        neg = tok.startswith("(") and tok.endswith(")")
        v = float(tok.strip("()").replace(",", ""))
        return -v if neg else v

    def merge_split_numbers(ws):
        out = []
        for wd in ws:
            if out:
                prev = out[-1]
                gap_limit = 10.0 if prev["text"] == "(" else 4.0
                if (wd["x0"] - prev["x1"] < gap_limit and re.match(r"^[\d,().]+$", prev["text"])
                        and re.match(r"^[\d,().]+$", wd["text"])
                        and not prev["text"].endswith(")") and not wd["text"].startswith("(")):
                    prev["text"] += wd["text"]
                    prev["x1"] = wd["x1"]
                    continue
            out.append(dict(wd))
        return out

    def lines_of(page_obj):
        raw = [w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
               if w.get("upright", True) and w["x0"] >= 0 and w["x1"] <= page_obj.width + 5]
        cleaned = []
        for w in raw:
            t = w["text"]
            if t.strip("!") == "":
                continue
            if t.endswith("!"):
                w = dict(w); w["text"] = t.rstrip("!")
            cleaned.append(w)
        words = sorted(cleaned, key=lambda w: w["top"])
        rows_, cur, cur_top = [], [], None
        for wd in words:
            if cur and wd["top"] - cur_top > 2.5:
                rows_.append(cur); cur = []
            if not cur:
                cur_top = wd["top"]
            cur.append(wd)
        if cur:
            rows_.append(cur)
        return [(sorted(ws, key=lambda x: x["x0"])[0]["top"],
                 merge_split_numbers(sorted(ws, key=lambda x: x["x0"]))) for ws in rows_]

    def year_columns(lns):
        for top, ws in lns:
            texts = [w["text"] for w in ws]
            yrs = [t for t in texts if re.match(r"^20\d\d$", t)]
            if len(yrs) >= 4 and len(yrs) == len(texts):
                return {int(w["text"]): (w["x0"] + w["x1"]) / 2 for w in ws}
        return None

    def items_from_page(lns, ycols):
        col_min_x = min(ycols.values()) - 55
        for top, ws in lns:
            texts = [w["text"] for w in ws]
            line = " ".join(texts).strip()
            if JUNK.match(line) or (len(texts) >= 4 and all(re.match(r"^20\d\d$", t) for t in texts)):
                continue
            if re.match(r"^\(?\s*(Nota|Tidak termasuk|Termasuk)", line) or re.match(r"^\(\s*\d\s*\)", line):
                continue
            fixed = []
            for w in ws:
                t = w["text"]
                if not NUMTOK.match(t) and re.match(r"^[\d,().]+$", t):
                    c = re.sub(r"(.)\1", r"\1", t)
                    if NUMTOK.match(c):
                        w = dict(w); w["text"] = c
                fixed.append(w)
            ws2 = []
            for i, w in enumerate(fixed):
                if (w["text"] == "(" and i + 1 < len(fixed)
                        and fixed[i + 1]["x0"] <= w["x0"] + 1.5
                        and fixed[i + 1]["text"].startswith("(")):
                    continue
                if ws2:
                    prev = ws2[-1]
                    if (w["x0"] < prev["x1"] - 1.5
                            and (w["text"] in prev["text"] or prev["text"] in w["text"])):
                        if len(w["text"]) > len(prev["text"]):
                            ws2[-1] = w
                        continue
                ws2.append(w)
            valws, labws = [], []
            for w in ws2:
                xc = (w["x0"] + w["x1"]) / 2
                if NUMTOK.match(w["text"]) and xc > col_min_x and min(abs(c - xc) for c in ycols.values()) <= 40:
                    valws.append(w)
                else:
                    labws.append(w)
            label = " ".join(w["text"] for w in sorted(labws, key=lambda x: x["x0"])).strip()
            label = re.sub(r"\s*\(disambung[.…]*\)\s*$", "", label)
            label = re.sub(r"\s*\(\s*$", "", label)
            label = re.sub(r"\s+\d$", "", label)
            label = re.sub(r"\s+\d{2,3}$", "", label)
            toks = label.split()
            half = len(toks) // 2
            if half >= 2 and toks[:half] == toks[half:]:
                label = " ".join(toks[:half])
            x0 = min((w["x0"] for w in labws), default=0)
            if not label and len(valws) == 1 and valws[0]["text"] == "2012":
                continue
            if not valws:
                if label:
                    yield top, "text", (label, x0)
                continue
            vals = {}
            for w in valws:
                xc = (w["x0"] + w["x1"]) / 2
                yr = min(ycols, key=lambda y: abs(ycols[y] - xc))
                vals[yr] = parse_amount(w["text"])
            yield top, "item", (label, vals, x0)

    out_rows = []
    section = None
    batch = []
    for pno, pp in [(260, 238), (261, 239), (262, 240)]:
        pg = _pdf.pages[pno - 1]
        lns = lines_of(pg)
        ycols = year_columns(lns)
        assert ycols, f'year header not found on {pno}'
        pending_item = None
        for top, kind, payload in items_from_page(lns, ycols):
            if kind == "text":
                lbl, x0 = payload
                lbl = re.sub(r"\s*-\s*\(Samb\.\)\s*$", "", lbl)
                lbl = re.sub(r"\s*–?\s*\(SAMB\.?\)\s*$", "", lbl).strip()
                if not lbl:
                    continue
                if pending_item and top - pending_item[1] < 14:
                    batch.append((section, lbl, pending_item[0], pending_item[1], x0, pno, pp))
                    pending_item = None
                    continue
                if batch and batch[-1][5] == pno and top - batch[-1][3] < 16 and \
                   (x0 > batch[-1][4] + 4 or lbl[0].islower() or lbl[0] == "("):
                    b = batch[-1]
                    batch[-1] = (b[0], b[1] + " " + lbl, b[2], b[3], b[4], b[5], b[6])
                else:
                    base = section.split(" / ")[0] if section else ""
                    if lbl in ("Penerimaan", "Pembayaran", "Perbelanjaan Pembangunan") and base.startswith("Kumpulan Wang"):
                        section = f"{base} / {lbl}"
                    else:
                        section = lbl
                continue
            label, vals, x0 = payload
            if re.fullmatch(r"\d{1,2}", label or ""):
                pending_item = (vals, top)
                continue
            if not label and batch:
                batch[-1][2].update(vals)
                continue
            SUBHDRS = ("Penerimaan", "Pembayaran", "Perbelanjaan Pembangunan")
            KNOWN = ("Baki pada 1 Januari", "Jumlah Penerimaan", "Jumlah Pembayaran")
            for sh in SUBHDRS:
                if label.endswith(" " + sh) and label[: -len(sh) - 1].strip() in KNOWN:
                    label = label[: -len(sh) - 1].strip()
                    batch.append((section, label, vals, top, x0, pno, pp))
                    base = (section or "").split(" / ")[0]
                    section = f"{base} / {sh}" if base else sh
                    break
            else:
                batch.append((section, label, vals, top, x0, pno, pp))

    for i, b in enumerate(batch):
        if b[1].startswith("Pemberian dan Kenaan Bayaran Tetap") and b[1] != "Pemberian dan Kenaan Bayaran Tetap":
            batch[i] = (b[0], "Pemberian dan Kenaan Bayaran Tetap", b[2], b[3], b[4], b[5], b[6])

    for section, label, vals, top, _x0, pno, pp in batch:
        for yr in sorted(vals, reverse=True):
            out_rows.append([section, label, yr, vals[yr], "juta",
                             SRC, pno, pp, stmt])
    with open(f'{WH}/fact_timeseries_2003_2012.csv', 'w', newline='', encoding='utf-8') as f:
        cw = csv.writer(f)
        cw.writerow(["section_bm", "line_item_bm", "year", "amount_rm_juta", "unit",
                     "source_file", "pdf_page", "printed_page", "statement"])
        cw.writerows(out_rows)
    return out_rows


if __name__ == '__main__':
    dl = extract_loans();        print('loans_receivable rows:', len(dl))
    dg = extract_statutory();    print('statutory_guarantees rows:', len(dg))
    di = extract_investments();  print('investments rows:', len(di))
    ts = extract_timeseries();   print('timeseries rows:', len(ts))
