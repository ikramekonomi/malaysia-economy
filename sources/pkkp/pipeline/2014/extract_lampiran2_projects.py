#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level (PKKP 2016, pdf 225-256, two-page spreads).

Left page rows: [*]NNNNN project name + kos_keseluruhan + terkumpul RMKe-10
prior (name may wrap), plus 'Jumlah <Program>' subtotals and
'JUMLAH <MINISTRY>' totals. Right page rows (same y): 7 cols = anggaran
langsung/pinjaman/jumlah, sebenar langsung/pinjaman/jumlah, terkumpul RMKe-11
hingga 31.12.2016. Row types: project / program_subtotal / ministry_total /
grand_total. 2016 vote-total aliases: P.25 abbreviated 'KEM.', P.63 'JUMLAH
KEMENTERIAN PENDIDIKAN MALAYSIA' (header KEMENTERIAN PENDIDIKAN), P.64
'JUMLAH KEMENTERIAN PENGAJIAN TINGGI' (header KEMENTERIAN PENDIDIKAN TINGGI).
Watermark '!' glyphs are printed INSIDE some words ('P R !OJEK') - stripped.
program_bm is linked only where tagged project sums equal the printed program
subtotal exactly (unique-subtotal rule).
"""
import csv
import re
import pdfplumber

YEAR = 2014
SRC = "2014_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2014/fact_devex_project.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")

ALIASES = {}



def unspread(s):
    """Collapse watermark glyph-spread ('K E M ENTERIAN' -> 'KEMENTERIAN')."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\b([A-Z])\s+(?=[A-Z])", r"\1", s)
    return s


def desp(s):
    return re.sub(r"\s+", "", s or "")

def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok in {"–", "-", "—", ""}:
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").replace(",", "")
    v = float(tok)
    return -v if neg else v


def merge_split_numbers(ws):
    out = []
    for wd in ws:
        if out:
            prev = out[-1]
            gap = wd["x0"] - prev["x1"]
            if (gap < 4.0 and re.match(r"^[\d,().*]+$", prev["text"])
                    and re.match(r"^[\d,().*]+$", wd["text"])):
                prev["text"] = prev["text"] + wd["text"]
                prev["x1"] = wd["x1"]
                continue
        out.append(dict(wd))
    return out


def lines_of(page_obj):
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=2)
                    if w.get("upright", True)
                    and w["x0"] >= 0 and w["x1"] <= page_obj.width + 5
                    and 0 <= w["top"] <= page_obj.height),
                   key=lambda w: w["top"])
    cleaned = []
    for w in words:
        t = w["text"]
        if t.strip("!") == "":
            continue
        if "!" in t:
            w = dict(w)
            w["text"] = t.replace("!", "")  # watermark glyphs inside/after words
            if not w["text"]:
                continue
        cleaned.append(w)
    cleaned = [w for w in cleaned
               if not (re.fullmatch(r"\d{1,3}", w["text"])
                       and (w["x0"] < 62 or w["x0"] > 590))
               and w["text"] != "$10"]
    words = cleaned
    rows_ = []
    cur = []
    cur_top = None
    for wd in words:
        if cur and wd["top"] - cur_top > 2.5:
            rows_.append(cur)
            cur = []
        if not cur:
            cur_top = wd["top"]
        cur.append(wd)
    if cur:
        rows_.append(cur)
    out = []
    for ws in rows_:
        ws = sorted(ws, key=lambda x: x["x0"])
        out.append((ws[0]["top"], merge_split_numbers(ws)))
    return out


def solve7(nums):
    for pos in range(7):
        cand = nums[:pos] + [0.0] + nums[pos:]
        ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kum = cand
        if abs(ag_l + ag_p - ag_j) <= 2 and abs(sb_l + sb_p - sb_j) <= 2:
            return cand
    return None


rows = []
stats = {"unmatched_left": 0, "odd_cols": 0}
current_maksud = current_name = None
current_program = None
last_was_program_hdr = False

with pdfplumber.open("/home/claude/pkkp/work/2014/2014.pdf") as pdf:
    pending = []
    for pno in range(245, 273):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined
        if not is_right:
            last_entry = None
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Kos Keseluruhan|Sebenar RMKe|Hingga|RM$|Perbelanjaan$|\( ?sambungan ?\)|PENYATA KEWANGAN|6\. LAMPIRAN)", line):
                    continue
                line = re.sub(r"^(?:RM\s+)+(?=P\s?\.)", "", line)
                mh = re.match(r"^P\s?\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not any(NUMTOK.match(t) for t in texts[2:]):
                    current_maksud = f"P.{mh.group(1)}"
                    is_samb = "(SAMB" in line
                    current_name = unspread(re.sub(r"\s*(?:–\s*|-\s*)?\(SAMB\.?\)\s*$", "", mh.group(2).strip()))
                    if not is_samb:
                        current_program = None
                    last_entry = None
                    last_was_program_hdr = False
                    continue
                nums = []
                k = len(texts)
                while k > 0 and NUMTOK.match(texts[k - 1]):
                    nums.insert(0, texts[k - 1])
                    k -= 1
                head = texts[:k]
                if len(nums) == 1 and head and re.match(r"^\*?\d{5}$", head[0]):
                    xs = [w["x1"] for w in ws if NUMTOK.match(w["text"])]
                    if xs and xs[-1] > 480:
                        print(f"!! blank Kos Keseluruhan cell p{pno} {head[0]}: kept as 0.0 (print omission)")
                        nums = ["–"] + nums
                is_proj = head and re.match(r"^\*?\d{5}$", head[0])
                label = " ".join(head[1:] if is_proj else head).strip()
                if len(nums) >= 2 and (label or is_proj):
                    if is_proj:
                        rt = "project"
                        code = head[0].lstrip("*")
                        name = label
                        foot = head[0].startswith("*") or any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", label):
                        rt, code, name, foot = "grand_total", None, "JUMLAH PERBELANJAAN PEMBANGUNAN", any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH\s+[A-Z]", label):
                        name = re.sub(r"^JUMLAH\s+", "", label).strip()
                        base_name = re.sub(r"\s*(?:–\s*|-\s*)?\(SAMB\.?\)\s*$", "", current_name or "").strip()
                        base_cmp = re.sub(r"\s*\([^)]*\)\s*$", "", base_name).strip()
                        accept = {base_name, base_cmp} | ALIASES.get(current_maksud or "", set())
                        if desp(name) in {desp(a) for a in accept}:
                            rt, code = "ministry_total", None
                        else:
                            rt, code = "program_subtotal", None
                            next_program = None
                        foot = any("*" in t for t in nums)
                    elif re.match(r"^Jumlah\s+", label):
                        rt, code = "program_subtotal", None
                        name = re.sub(r"^Jumlah\s+", "", label).strip()
                        msp = re.match(r"^(.*?[a-z)0-9])\s+([A-Z][A-Z0-9 /,&().'-]{3,})$", name)
                        if msp and msp.group(2) == msp.group(2).upper():
                            name = msp.group(1).strip()
                            next_program = re.sub(r"\s*(?:–\s*)?\(SAMB\.\)\s*$", "", msp.group(2)).strip()
                        else:
                            next_program = None
                        foot = any("*" in t for t in nums)
                    else:
                        rt, code, name, foot = "other", None, label, any("*" in t for t in nums)
                    if len(nums) > 2:
                        name = (name + " " + " ".join(nums[:-2])).strip()
                    entry = {
                        "maksud": current_maksud, "mname": current_name,
                        "rt": rt, "code": code, "name": name, "foot": foot,
                        "program": current_program if rt in ("project", "program_subtotal") else None,
                        "y": top, "page": pno,
                        "kos": parse_amount(nums[-2]), "prior": parse_amount(nums[-1]),
                    }
                    if rt == "program_subtotal":
                        entry["hdr"] = current_program
                        entry["program"] = name
                        current_program = next_program
                    pending.append(entry)
                    last_entry = entry
                    last_was_program_hdr = False
                elif label and not nums and (
                        label.startswith('Nota') or '.indd' in label or label == 'ANM'
                        or re.search(r'\d{2}/\d{2}/\d{2}\s+\d', label)
                        or 'Sesi Parlimen' in label or 'dimasuk kira' in label
                        or 'dibentangkan' in label or label.endswith('pendahuluan.')
                        or label.endswith('pendahuluan..')):
                    last_entry = None  # printed Nota / page-footer line: never a name wrap
                elif label and not nums and len(label) < 90:
                    if re.match(r"^(PENYATA|LAMPIRAN|Nota\b|Nota:|\d+$)", label) or label.startswith("Nota"):
                        last_entry = None
                    elif re.fullmatch(r"(RM\s*)+", label) or re.search(r"\bP\s?\.\s?\d{2}", label):
                        pass
                    elif label == label.upper() and re.match(r"^[A-Z][A-Z0-9 /,&().'-]{3,}$", label):
                        frag = re.sub(r"\s*(?:–\s*)?\(SAMB\.\)\s*$", "", label).strip()
                        if last_was_program_hdr and current_program:
                            current_program = current_program + " " + frag
                        else:
                            current_program = frag
                        last_entry = None
                        last_was_program_hdr = True
                        continue
                    elif last_entry is not None:
                        last_entry["name"] += " " + label
        else:
            mine = [p for p in pending if p["page"] == pno - 1]
            numeric_lines = []
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                if len(texts) >= 1 and all(NUMTOK.match(t) for t in texts):
                    numeric_lines.append({"y": top, "toks": texts,
                                          "xc": [(w["x0"] + w["x1"]) / 2 for w in ws],
                                          "x1": [w["x1"] for w in ws], "used": False})
            col_x1 = None
            full7 = [nl for nl in numeric_lines if len(nl["toks"]) == 7]
            if full7:
                col_x1 = [sorted(nl["x1"][i] for nl in full7)[len(full7) // 2] for i in range(7)]
            for p in mine:
                best, bestd = None, 4.5
                for nl in numeric_lines:
                    if nl["used"]:
                        continue
                    d = abs(nl["y"] - p["y"])
                    if d < bestd:
                        best, bestd = nl, d
                if best is None:
                    stats["unmatched_left"] += 1
                    print(f"!! unmatched: {p['rt']} {p['name'][:50]} p{p['page']} y={p['y']:.0f}")
                    continue
                best["used"] = True
                nums = [parse_amount(t) for t in best["toks"]]
                foot2 = any("*" in t for t in best["toks"])
                if len(nums) == 7:
                    vals = nums
                elif 1 <= len(nums) <= 6:
                    vals = None
                    if col_x1 is not None:
                        assign = []
                        ok = True
                        for x1t in best["x1"]:
                            ci = min(range(7), key=lambda i: abs(col_x1[i] - x1t))
                            if abs(col_x1[ci] - x1t) > 15 or (assign and ci <= assign[-1]):
                                ok = False
                                break
                            assign.append(ci)
                        if ok and len(set(assign)) == len(nums):
                            cand = [0.0] * 7
                            for ci, v in zip(assign, nums):
                                cand[ci] = v
                            ag_l_, ag_p_, ag_j_, sb_l_, sb_p_, sb_j_, _k = cand
                            if abs(ag_l_ + ag_p_ - ag_j_) <= 2 and abs(sb_l_ + sb_p_ - sb_j_) <= 2:
                                vals = cand
                    if vals is None and len(nums) == 6:
                        vals = solve7(nums)
                    if vals is not None and len(nums) < 5:
                        print(f"!! sparse right-page row ({len(nums)} printed cells, blanks resolved 0.0 by column x-position): {p['name'][:50]} p{pno}")
                    if vals is None:
                        stats["odd_cols"] += 1
                        print(f"!! unsolvable {len(nums)}-col: {p['name'][:50]} p{pno}")
                        continue
                else:
                    stats["odd_cols"] += 1
                    print(f"!! {len(nums)}-col row: {p['name'][:50]} p{pno} {best['toks'][:8]}")
                    continue
                ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kum = vals
                rows.append([
                    p["maksud"], p["mname"], p["rt"], p.get("program"), p["code"], p["name"], YEAR,
                    p["kos"], p["prior"], ag_l, ag_p, ag_j, sb_l, sb_p, sb_j, kum,
                    p["foot"] or foot2,
                    SRC, p["page"], p["page"] - 25, "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
                if p["rt"] == "program_subtotal":
                    rows[-1].append(p.get("hdr"))
                else:
                    rows[-1].append(None)
            pending = [p for p in pending if p["page"] != pno - 1]

# P.62 printed Nota names butiran 03000/05000/36000 (RM10 pendahuluan rows)
# without starring the rows themselves - flag them from the printed Nota text
IDX_FOOT = 16
for r in rows:
    if r[0] == "P.62" and r[2] == "project" and r[4] in ("03000", "05000", "36000"):
        r[IDX_FOOT] = True
        print(f"!! P.62 {r[4]}: has_footnote set from the printed page Nota "
              f"(row itself prints no asterisk)")

# duplicate base-name JUMLAH handling (P.24)
_seen = {}
for i, r in enumerate(rows):
    if r[2] == "ministry_total":
        if r[0] in _seen:
            j = _seen[r[0]]
            rows[j][2] = "program_subtotal"
            rows[j][3] = rows[j][5]
            print(f"!! duplicate ministry JUMLAH in {r[0]}: row on p{rows[j][18]} demoted to program_subtotal")
        _seen[r[0]] = i

# verified-linkage filter (unique-subtotal rule)
from collections import defaultdict as _dd
IDX_PROG, IDX_SEB, IDX_HDR = 3, 14, 21
_psum = _dd(float)
for r in rows:
    if r[2] == "project" and r[IDX_PROG]:
        _psum[(r[0], r[IDX_PROG].upper())] += r[IDX_SEB]
_subcount = _dd(int)
for r in rows:
    if r[2] == "program_subtotal":
        for candu in {c.upper() for c in (r[IDX_PROG], r[IDX_HDR]) if c}:
            _subcount[(r[0], candu)] += 1
_ok = set()
for r in rows:
    if r[2] != "program_subtotal":
        continue
    linked = None
    for cand in (r[IDX_PROG], r[IDX_HDR]):
        if not cand:
            continue
        key = (r[0], cand.upper())
        if _subcount[key] == 1 and key in _psum and abs(_psum[key] - r[IDX_SEB]) < 1:
            linked = key
            break
    if linked:
        _ok.add(linked)
        r[IDX_PROG] = linked[1] if r[IDX_PROG] is None or r[IDX_PROG].upper() != linked[1] else r[IDX_PROG]
    else:
        r[IDX_PROG] = None
for key, n in _subcount.items():
    if n > 1:
        print(f"!! duplicate program-subtotal name (volume printing anomaly), attribution nulled: {key} x{n}")
nulled = 0
for r in rows:
    if r[2] == "project" and r[IDX_PROG]:
        if (r[0], r[IDX_PROG].upper()) not in _ok:
            r[IDX_PROG] = None
            nulled += 1
for r in rows:
    del r[IDX_HDR]
print(f"program linkage: {len(_ok)} verified groups; {nulled} unverifiable project attributions nulled")


with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code", "name_bm", "year",
                 "kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke10_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

from collections import Counter, defaultdict
c = Counter(r[2] for r in rows)
print(f"fact_devex_project.csv: {len(rows)} rows | {dict(c)} | stats={stats}")
leaf = defaultdict(float)
mtot = {}
for r in rows:
    if r[2] == "project":
        leaf[r[0]] += r[14]
    if r[2] == "ministry_total":
        mtot[r[0]] = r[14]
bad = 0
for mk, v in mtot.items():
    if abs(leaf.get(mk, 0) - v) > 1:
        print(f"MISMATCH {mk}: projects={leaf.get(mk,0):,.2f} vs total={v:,.2f}")
        bad += 1
print(f"ministry reconciliation: {len(mtot)-bad}/{len(mtot)} OK")
