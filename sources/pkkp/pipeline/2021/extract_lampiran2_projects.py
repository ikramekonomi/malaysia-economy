#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level (pdf 198-229, two-page spreads).

Left page rows: [*]NNNNN project name + kos_keseluruhan + terkumpul_prior
  (name may wrap to following text-only lines), plus 'Jumlah <Program>' subtotals
  (mixed case) and 'JUMLAH <MINISTRY>' totals.
Right page rows (same y): 7 cols = anggaran langsung/pinjaman/jumlah,
  sebenar langsung/pinjaman/jumlah, terkumpul hingga 31.12.2022.
Row types: project / program_subtotal / ministry_total / grand_total.
"""
import csv
import re
import pdfplumber

YEAR = 2021
SRC = "2021_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2021/fact_devex_project.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")


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
    """Gap-based row clustering: group words whose tops are within 2.5pt of the
    row's running top (robust against bucket-boundary splits)."""
    words = sorted(page_obj.extract_words(x_tolerance=1.5, y_tolerance=2), key=lambda w: w["top"])
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
    """Return 7 values from 6 tokens using ag_l+ag_p=ag_j and sb_l+sb_p=sb_j."""
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

with pdfplumber.open("/home/claude/pkkp/work/2021/2021.pdf") as pdf:
    pending = []
    for pno in range(202, 246):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined
        if not is_right:
            last_entry = None
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Kos Keseluruhan|Sebenar RMKe|Hingga|RM$|\( ?sambungan ?\)|PENYATA KEWANGAN|WJD25)", line):
                    continue
                # the column-units line 'RM  RM' can share a baseline with the
                # P.xx header on continuation pages; strip it before matching
                line = re.sub(r"^(?:RM\s+)+(?=P\.)", "", line)
                mh = re.match(r"^P\.\s?(\d{2,3})\s+(.+)$", line)
                if mh and not any(NUMTOK.match(t) for t in texts[2:]):
                    current_maksud = f"P.{mh.group(1)}"
                    is_samb = "(SAMB.)" in line
                    current_name = re.sub(r"\s*(?:–\s*)?\(SAMB\.\)\s*$", "", mh.group(2).strip())
                    if not is_samb:
                        current_program = None
                    last_entry = None
                    last_was_program_hdr = False
                    continue
                # amounts are TRAILING numeric tokens only (project codes are leading digits)
                nums = []
                k = len(texts)
                while k > 0 and NUMTOK.match(texts[k - 1]):
                    nums.insert(0, texts[k - 1])
                    k -= 1
                head = texts[:k]
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
                        if name in (base_name, base_cmp):
                            rt, code = "ministry_total", None
                        else:
                            # ALL-CAPS sub-block subtotal inside a vote (P.63
                            # JUMLAH PENDIDIKAN / JUMLAH PENDIDIKAN TINGGI)
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
                    if len(nums) > 2:  # stray digits belong to the name, keep last 2 as amounts
                        name = (name + " " + " ".join(nums[:-2])).strip()
                    entry = {
                        "maksud": current_maksud, "mname": current_name,
                        "rt": rt, "code": code, "name": name, "foot": foot,
                        "program": current_program if rt in ("project", "program_subtotal") else None,
                        "y": top, "page": pno,
                        "kos": parse_amount(nums[-2]), "prior": parse_amount(nums[-1]),
                    }
                    if rt == "program_subtotal":
                        entry["hdr"] = current_program  # header active when the subtotal printed
                        entry["program"] = name  # a subtotal always names its own block
                        current_program = next_program  # block closed; None until a new header
                    pending.append(entry)
                    last_entry = entry
                    last_was_program_hdr = False
                elif label and not nums and len(label) < 80:
                    if re.match(r"^(PENYATA|WJD25|LAMPIRAN|\d+$)", label):
                        pass
                    elif re.fullmatch(r"(RM\s*)+", label) or re.search(r"\bP\.\s?\d{2}", label):
                        pass  # column-units furniture / merged maksud header, never a program
                    elif label == label.upper() and re.match(r"^[A-Z][A-Z0-9 /,&().'-]{3,}$", label):
                        # ALL-CAPS text line = program header (– (SAMB.) stripped); may wrap
                        frag = re.sub(r"\s*(?:–\s*)?\(SAMB\.\)\s*$", "", label).strip()
                        if last_was_program_hdr and current_program:
                            current_program = current_program + " " + frag
                        else:
                            current_program = frag
                        last_entry = None
                        last_was_program_hdr = True
                        continue
                    elif last_entry is not None:
                        # wrapped project-name continuation
                        last_entry["name"] += " " + label
        else:
            mine = [p for p in pending if p["page"] == pno - 1]
            numeric_lines = []
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                if len(texts) >= 5 and all(NUMTOK.match(t) for t in texts):
                    numeric_lines.append({"y": top, "toks": texts,
                                          "xc": [(w["x0"] + w["x1"]) / 2 for w in ws],
                                          "x1": [w["x1"] for w in ws], "used": False})
            # column x-anchors (right edges) from full 7-token rows on this page
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
                elif len(nums) in (5, 6):
                    vals = None
                    # prefer x-position assignment (columns are right-aligned): map each
                    # token to the nearest column right-edge; unmatched columns are
                    # dropped dashes. Falls back to the arithmetic solver (6-token only).
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
                    if vals is None:
                        stats["odd_cols"] += 1
                        print(f"!! unsolvable 6-col: {p['name'][:50]} p{pno}")
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
                    SRC, p["page"], p["page"] - 12, "Lampiran 2 Penyata Perbelanjaan Pembangunan",
                ])
                if p["rt"] == "program_subtotal":
                    rows[-1].append(p.get("hdr"))
                else:
                    rows[-1].append(None)
            pending = [p for p in pending if p["page"] != pno - 1]

# verified-linkage filter: link program_bm only where tagged project sums equal
# the printed program subtotal EXACTLY. The subtotal may print an abbreviated
# label ('Jumlah MARDI') for a long ALL-CAPS block header; verification is run
# against the subtotal's own name AND the header active when it printed.
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
                 "kos_keseluruhan_rm", "terkumpul_rmke12_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke12_rm", "has_footnote",
                 "source_file", "pdf_page", "printed_page", "statement"])
    cw.writerows(rows)

from collections import Counter
c = Counter(r[2] for r in rows)
print(f"fact_devex_project.csv: {len(rows)} rows | {dict(c)} | stats={stats}")
# reconcile: project rows sum to ministry totals per maksud (sebenar_jumlah)
from collections import defaultdict
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
