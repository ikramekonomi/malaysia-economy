#!/usr/bin/env python3
"""Extract Lampiran 2 at PROJECT level (pdf 176-211, two-page spreads).

Left page rows: [*]NNNNN project name + kos_keseluruhan + terkumpul_prior
  (name may wrap to following text-only lines), plus 'Jumlah <Program>' subtotals
  (mixed case) and 'JUMLAH <MINISTRY>' totals.
Right page rows (same y): 7 cols = anggaran langsung/pinjaman/jumlah,
  sebenar langsung/pinjaman/jumlah, terkumpul hingga 31.12.2019.
Row types: project / program_subtotal / ministry_total / grand_total.
"""
import csv
import re
import pdfplumber

YEAR = 2019
SRC = "2019_PENYATA_KEWANGAN_KERAJAAN_PERSEKUTUAN.pdf"
OUT = "/home/claude/pkkp/warehouse2019/fact_devex_project.csv"
NUMTOK = re.compile(r"^\*?\(?[\d,]+(?:\.\d+)?\)?$|^\*?[–—-]$")


def parse_amount(tok):
    tok = tok.strip().replace("*", "")
    if tok == "":
        return None     # blank printed cell (distinct from en-dash nil)
    if tok in {"–", "-", "—"}:
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
    """Gap-based row clustering. The 2020 volume squeezes some Lampiran 2 pages
    (e.g. pdf 238-239, P.47) to a ~7.5pt row pitch where two DIFFERENT rows sit
    only 1.2pt apart; extracting at y_tolerance=2 interleaves their glyphs into
    corrupt tokens. Words are therefore extracted at y_tolerance=0.5 and rows
    clustered with a 0.9pt gap."""
    words = sorted((w for w in page_obj.extract_words(x_tolerance=1.5, y_tolerance=0.12)
                    if w["x0"] >= 0 and w["x1"] <= page_obj.width and w.get("upright", True)),  # drop off-page spread ghosts + rotated sidebar
                   key=lambda w: w["top"])
    rows_ = []
    cur = []
    cur_top = None
    for wd in words:
        if cur and wd["top"] - cur_top > 0.25:
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

with pdfplumber.open("/home/claude/pkkp/work/2019/2019.pdf") as pdf:
    pending = []
    for pno in range(176, 212):
        pg = pdf.pages[pno - 1]
        lns = lines_of(pg)
        joined = " ".join(w["text"] for _, ws in lns for w in ws)
        is_right = "Anggaran Tahun" in joined and "Maksud Perbelanjaan" not in joined
        if not is_right:
            last_entry = None
            # column anchors of the left page's two value columns (kos, prior)
            _kx, _px = [], []
            for _top, _ws in lns:
                _t = [w["text"] for w in _ws]
                _nums = []
                k = len(_t)
                while k > 0 and NUMTOK.match(_t[k - 1]):
                    _nums.insert(0, _ws[k - 1])
                    k -= 1
                if len(_nums) == 2:
                    _kx.append(_nums[0]["x1"])
                    _px.append(_nums[1]["x1"])
            kos_x1 = sorted(_kx)[len(_kx) // 2] if _kx else None
            pri_x1 = sorted(_px)[len(_px) // 2] if _px else None
            for top, ws in lns:
                texts = [w["text"] for w in ws]
                line = " ".join(texts)
                if re.match(r"^(Penyata Perbelanjaan|bagi tahun|Maksud Perbelanjaan|Kos Keseluruhan|Sebenar RMKe|Hingga|RM$|\( ?sambungan ?\)|PENYATA KEWANGAN|WJD25)", line):
                    continue
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
                # ghost-overprint repair (seen pdf 210, P.06 '93600 Projek Mesra
                # Rakyat'): a shifted duplicate of the project name interleaves
                # with the 5-digit code, yielding tokens like 'Mesr9a3 6R0a0kyat'
                # followed by the clean copy. Recover the code from the embedded
                # digits and collapse the doubled name. Reported, not silent.
                if head and not re.match(r"^\*?\d{5}$", head[0]):
                    digs = "".join(re.findall(r"\d", " ".join(head)))
                    if len(digs) == 5 and any(re.search(r"\d", t) and re.search(r"[A-Za-z]", t) for t in head):
                        stripped = " ".join(re.sub(r"\d", "", t) for t in head).split()
                        s2 = " ".join(stripped)
                        halves = s2.split()
                        if len(halves) % 2 == 0 and halves[:len(halves)//2] == halves[len(halves)//2:]:
                            print(f"!! ghost-overprint repaired p{pno}: code {digs} name '{' '.join(halves[:len(halves)//2])}'")
                            head = [digs] + halves[:len(halves)//2]
                is_proj = head and re.match(r"^\*?\d{5}$", head[0])
                # print quirk (P.29 80004, pdf 196): a project row prints ONLY its
                # cumulative-prior value (kos cell blank). Duplicate the single
                # token into the right column by x-position; kos stays empty.
                if is_proj and len(nums) == 1 and kos_x1 is not None:
                    _vw = [w for w in ws if NUMTOK.match(w["text"])][-1]
                    if abs(_vw["x1"] - pri_x1) < abs(_vw["x1"] - kos_x1):
                        nums = ["", nums[0]]
                        print(f"!! single-value project row p{pno}: kos blank, value in prior column: {' '.join(head)[:60]}")
                label = " ".join(head[1:] if is_proj else head).strip()
                # scrub the printer's slug line that merges into page-bottom rows
                label = re.sub(r"\s*\d+ Teks Lampiran.*$", "", label)
                label = re.sub(r"\s*\d{2}/\d{2}/\d{4}.*$", "", label).strip()
                if len(nums) >= 2 and (label or is_proj):
                    if is_proj:
                        rt = "project"
                        code = head[0].lstrip("*")
                        name = label
                        foot = head[0].startswith("*") or any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH PERBELANJAAN PEMBANGUNAN", label):
                        rt, code, name, foot = "grand_total", None, "JUMLAH PERBELANJAAN PEMBANGUNAN", any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH\s+(PENDIDIKAN TINGGI|PENDIDIKAN)\s*$", label):
                        # P.63 prints two ALL-CAPS section blocks (PENDIDIKAN /
                        # PENDIDIKAN TINGGI) inside one maksud, each with its own
                        # JUMLAH row, before JUMLAH KEMENTERIAN PENDIDIKAN.
                        rt, code = "section_subtotal", None
                        name = re.sub(r"^JUMLAH\s+", "", label).strip()
                        foot = any("*" in t for t in nums)
                    elif re.match(r"^JUMLAH\s+[A-Z]", label):
                        rt, code = "ministry_total", None
                        name = re.sub(r"^JUMLAH\s+", "", label).strip()
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
                        entry["program"] = name  # a subtotal always names its own block
                        current_program = next_program  # block closed; None until a new header
                    pending.append(entry)
                    last_entry = entry
                    last_was_program_hdr = False
                elif label and not nums and len(label) < 80:
                    if re.match(r"^(PENYATA|WJD25|LAMPIRAN|\d+$)", label):
                        pass
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
            pending = [p for p in pending if p["page"] != pno - 1]

# 2019 print quirk (P.24, pdf 188): an INTERIM 'JUMLAH KEMENTERIAN ...' row
# prints mid-ministry (closing the MITI-proper block before the agency blocks);
# the true ministry total prints at the block end (pdf 190). Retype all but the
# LAST ministry_total per maksud as section_subtotal (label kept as printed).
from collections import defaultdict as _dd0
_mt = _dd0(list)
for _i, _r in enumerate(rows):
    if _r[2] == "ministry_total":
        _mt[_r[0]].append(_i)
for _mk, _idxs in _mt.items():
    for _j in _idxs[:-1]:
        rows[_j][2] = "section_subtotal"
        print(f"!! interim ministry total retyped section_subtotal: {_mk} p{rows[_j][18]} "
              f"sebenar={rows[_j][14]:,.2f} (print quirk; full total follows)")

# verified-linkage (positional): a printed 'Jumlah <Program>' row closes the
# block of consecutive project rows above it. program_bm is assigned to a block
# ONLY where the block's projects sum EXACTLY (tol RM1) to the printed program
# subtotal in sebenar_jumlah_rm; ambiguous or non-reconciling blocks stay empty.
# If two program subtotals in one maksud share a name, both blocks are nulled
# (the tag would be ambiguous for consumers grouping by maksud+program).
from collections import defaultdict as _dd
IDX_RT, IDX_PROG, IDX_SEB = 2, 3, 14
run = []          # indices of consecutive project rows
verified = []     # (block name, project row indices, subtotal idx)
for i, r in enumerate(rows):
    if r[IDX_RT] == "project":
        run.append(i)
        r[IDX_PROG] = None
    elif r[IDX_RT] == "program_subtotal":
        name = r[5]
        r[IDX_PROG] = name  # a subtotal always names its own block
        ssum = sum(rows[j][IDX_SEB] for j in run)
        if run and abs(ssum - r[IDX_SEB]) < 1:
            verified.append((r[0], name, list(run), i))
        elif run:
            # the run may begin with tail projects of a preceding block that has
            # no printed subtotal of its own; link the unique SUFFIX of the run
            # that sums exactly to the printed subtotal, if one exists
            matches = []
            acc2 = 0.0
            for k in range(1, len(run) + 1):
                acc2 += rows[run[-k]][IDX_SEB]
                if abs(acc2 - r[IDX_SEB]) < 1:
                    matches.append(k)
            if len(matches) == 1:
                sfx = run[-matches[0]:]
                print(f".. suffix-linked: {r[0]} '{name[:45]}' last {matches[0]} of {len(run)} projects")
                verified.append((r[0], name, list(sfx), i))
            else:
                print(f"!! program block not linkable: {r[0]} '{name[:45]}' "
                      f"projects={ssum:,.2f} vs subtotal={r[IDX_SEB]:,.2f} "
                      f"({len(matches)} suffix matches; tags left empty)")
        run = []
    else:
        run = []
# null duplicate-name blocks within a maksud
_names = _dd(int)
for mk, name, idxs, si in verified:
    _names[(mk, name.upper())] += 1
kept = 0
for mk, name, idxs, si in verified:
    if _names[(mk, name.upper())] > 1:
        print(f"!! duplicate program-subtotal name (volume printing anomaly), attribution nulled: {(mk, name.upper())}")
        continue
    for j in idxs:
        rows[j][IDX_PROG] = name
    kept += 1
print(f"program linkage: {kept} verified groups of {len(verified)} reconciling blocks; "
      f"{sum(1 for r in rows if r[IDX_RT]=='project' and not r[IDX_PROG])} projects untagged")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    cw = csv.writer(f)
    cw.writerow(["maksud_code", "maksud_name_bm", "row_type", "program_bm", "projek_code", "name_bm", "year",
                 "kos_keseluruhan_rm", "terkumpul_rmke11_prior_rm",
                 "anggaran_langsung_rm", "anggaran_pinjaman_rm", "anggaran_jumlah_rm",
                 "sebenar_langsung_rm", "sebenar_pinjaman_rm", "sebenar_jumlah_rm",
                 "terkumpul_rmke11_rm", "has_footnote",
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
