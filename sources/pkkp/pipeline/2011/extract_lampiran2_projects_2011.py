#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level for FY2011 (two-page spreads).

2011 anchors: LEFT pages = even pdf 204..246, RIGHT (sambungan) = odd 205..247.
printed_page = pdf_page - 18. Each physical pdf page carries crop-bleed from its
facing page (right-half data bleeds into a left page at x>width; left-half bleeds
into a right page at negative x); the 0<=x<=width filter separates the pair.

LEFT page prints THREE numeric columns:
  [Jumlah Anggaran Harga Projek]  = kos_keseluruhan_rm            (stored, first)
  [Anggaran RMKe-10 2011-2012]    = EXTRA, no schema slot         (NOT stored)
  [Perbelanjaan Sebenar RMKe-9 Hingga 31.12.2010] = prior cumul   (stored, last ->
                                                     terkumpul_rmke10_prior_rm)
RIGHT page prints SEVEN numeric columns:
  anggaran langsung/pinjaman/jumlah, sebenar langsung/pinjaman/jumlah,
  terkumpul RMKe-10 hingga 31.12.2011.
2011 = RMKe-10 year 1: terkumpul_rmke10_rm == sebenar_jumlah_rm on every project.
"""
import csv
import re
import pdfplumber

YEAR = 2011
SRC = "2011_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
PDF = "/home/claude/pkkp/work/2011/2011.pdf"
OUT = "/home/claude/pkkp/warehouse2011/fact_devex_project.csv"
STMT = "Penyata Perbelanjaan Pembangunan"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")

ALIASES = {}
MID_GRAND = {"val": None}  # extra 'Anggaran RMKe-10 2011-2012' grand total, reporting only


def unspread(s):
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
    return -float(tok) if neg else float(tok)


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
    words = [w for w in words
             if not (re.fullmatch(r"\d{1,3}", w["text"]) and (w["x0"] < 70 or w["x0"] > 590))]
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

with pdfplumber.open(PDF) as pdf:
    pending = []
    for pno in range(204, 248):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        is_right = (pno % 2 == 1)
        if not is_right:
            last_entry = None
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|"
                            r"Jumlah Anggaran|Harga Projek|Anggaran$|Anggaran RMKe|"
                            r"Perbelanjaan$|Perbelanjaan Sebenar|Sebenar|Cara|Pinjaman|"
                            r"Hingga|RMKe|2011|31\.|RM( RM)*$|\( ?sambungan ?\)|"
                            r"PENYATA KEWANGAN|LAMPIRAN)", line):
                    continue
                mh = re.match(r"^P\s?\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not any(NUMTOK.match(t) for t in texts[2:]):
                    current_maksud = f"P.{mh.group(1)}"
                    is_samb = "(SAMB" in line.upper()
                    current_name = unspread(re.sub(r"\s*(?:[-–]\s*)?\(SAMB\.?\)\s*$", "",
                                                   mh.group(2).strip()))
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
                is_proj = bool(head) and re.match(r"^\*?\d{5}$", head[0])
                if is_proj and 0 < len(nums) < 3:
                    print(f"!! project {head[0]} p{pno}: only {len(nums)} numeric cell(s) "
                          f"{nums} - padding leading blanks 0.0 (print omission)")
                    nums = ["–"] * (3 - len(nums)) + nums
                label = " ".join(head[1:] if is_proj else head).strip()
                if len(nums) >= 3 and (label or is_proj):
                    if is_proj:
                        rt = "project"
                        code = head[0].lstrip("*")
                        name = label
                        foot = head[0].startswith("*") or any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", label):
                        rt, code, name = "grand_total", None, "JUMLAH PERBELANJAAN PEMBANGUNAN"
                        foot = any("*" in t for t in nums)
                        MID_GRAND["val"] = parse_amount(nums[-2])
                    elif re.match(r"^JUMLAH\s+[A-Z]", label):
                        name = re.sub(r"^JUMLAH\s+", "", label).strip()
                        base_name = re.sub(r"\s*(?:[-–]\s*)?\(SAMB\.?\)\s*$", "", current_name or "").strip()
                        base_cmp = re.sub(r"\s*\([^)]*\)\s*$", "", base_name).strip()
                        accept = {base_name, base_cmp} | ALIASES.get(current_maksud or "", set())
                        if desp(name) in {desp(a) for a in accept}:
                            rt, code = "ministry_total", None
                        else:
                            rt, code = "program_subtotal", None
                        foot = any("*" in t for t in nums)
                    elif re.match(r"^Jumlah\s+", label):
                        rt, code = "program_subtotal", None
                        name = re.sub(r"^Jumlah\s+", "", label).strip()
                        foot = any("*" in t for t in nums)
                    else:
                        rt, code, name = "other", None, label
                        foot = any("*" in t for t in nums)
                    if len(nums) > 3:
                        name = (name + " " + " ".join(nums[:-3])).strip()
                    entry = {
                        "maksud": current_maksud, "mname": current_name,
                        "rt": rt, "code": code, "name": name, "foot": bool(foot),
                        "program": current_program if rt in ("project", "program_subtotal") else None,
                        "y": top, "page": pno,
                        "kos": parse_amount(nums[-3]),
                        "mid": parse_amount(nums[-2]),   # Anggaran RMKe-10 2011-2012 (extra, unstored)
                        "prior": parse_amount(nums[-1]),
                    }
                    if rt == "program_subtotal":
                        entry["hdr"] = current_program
                        entry["program"] = name
                    pending.append(entry)
                    last_entry = entry
                    last_was_program_hdr = False
                elif label and not nums and (
                        label.startswith('Nota') or '.indd' in label or label == 'ANM'
                        or re.search(r'\d{2}/\d{2}/\d{2}\s+\d', label)
                        or 'Sesi Parlimen' in label or 'dimasuk kira' in label
                        or 'dibentangkan' in label or 'pendahuluan' in label):
                    last_entry = None
                elif label and not nums and len(label) < 90:
                    if re.match(r"^(PENYATA|LAMPIRAN|Nota\b|Nota:|\d+$)", label):
                        last_entry = None
                    elif re.fullmatch(r"(RM\s*)+", label) or re.search(r"\bP\s?\.\s?\d{2}", label):
                        pass
                    elif label == label.upper() and re.match(r"^[A-Z][A-Z0-9 /,&().'-]{3,}$", label):
                        frag = re.sub(r"\s*(?:[-–]\s*)?\(SAMB\.?\)\s*$", "", label).strip()
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
                    # An all-blank left row (kos=mid=prior=0) prints no right-page line;
                    # emit it with all-zero right columns rather than dropping it.
                    if abs(p["kos"]) < 1e-9 and abs(p["mid"]) < 1e-9 and abs(p["prior"]) < 1e-9:
                        print(f"!! all-blank row (no right-page line printed), emitted as 0.0: "
                              f"{p['rt']} {p['code'] or ''} {p['name'][:40]} p{p['page']}")
                        rows.append([
                            p["maksud"], p["mname"], p["rt"], p.get("program"), p["code"],
                            p["name"], YEAR, p["kos"], p["prior"],
                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, p["foot"],
                            SRC, p["page"], p["page"] - 18, STMT,
                        ])
                        rows[-1].append(p.get("hdr") if p["rt"] == "program_subtotal" else None)
                        continue
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
                        assign, ok = [], True
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
                        print(f"!! sparse right-page row ({len(nums)} cells, blanks->0.0 by x-pos): "
                              f"{p['name'][:50]} p{pno}")
                    if vals is None:
                        stats["odd_cols"] += 1
                        print(f"!! unsolvable {len(nums)}-col: {p['name'][:50]} p{pno} {best['toks']}")
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
                    SRC, p["page"], p["page"] - 18, STMT,
                ])
                rows[-1].append(p.get("hdr") if p["rt"] == "program_subtotal" else None)
            pending = [p for p in pending if p["page"] != pno - 1]

# P.62 RM10-pendahuluan Nota butiran (codes already carry * -> already footnoted;
# ensure any listed butiran with no printed asterisk is still flagged)
IDX_FOOT = 16
NOTA_P62 = {"21000", "22000", "24000", "45000", "55000", "67000", "76000", "78000"}
for r in rows:
    if r[0] == "P.62" and r[2] == "project" and r[4] in NOTA_P62 and not r[IDX_FOOT]:
        r[IDX_FOOT] = True
        print(f"!! P.62 {r[4]}: has_footnote set from printed Nota (row printed no asterisk)")

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
    else:
        r[IDX_PROG] = None
for key, n in _subcount.items():
    if n > 1:
        print(f"!! duplicate program-subtotal name, attribution nulled: {key} x{n}")
nulled = 0
for r in rows:
    if r[2] == "project" and r[IDX_PROG]:
        if (r[0], r[IDX_PROG].upper()) not in _ok:
            r[IDX_PROG] = None
            nulled += 1
for r in rows:
    del r[IDX_HDR]
print(f"program linkage: {len(_ok)} verified groups; {nulled} project attributions nulled")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code",
                 "name_bm", "year", "kos_keseluruhan_rm", "terkumpul_rmke10_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke10_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

from collections import Counter
c = Counter(r[2] for r in rows)
print(f"fact_devex_project.csv: {len(rows)} rows | {dict(c)} | stats={stats}")
print(f"extra 'Anggaran RMKe-10 2011-2012' column grand total (NOT stored): {MID_GRAND['val']:,.2f}"
      if MID_GRAND['val'] is not None else "extra-column grand total not captured")
