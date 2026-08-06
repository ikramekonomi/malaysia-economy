#!/usr/bin/env python3
"""Build the consolidated OBLIGATIONS view — what the federal government OWES
(and is owed) beyond the cash accounts — from figures already extracted and
verified in the source layer. Writes:

    curated/fact_obligations.csv           the unified view
    curated/_validation_obligations.csv    tie-back + cross-source reconciliation

No new numbers are created here: every row is copied from a source CSV under
sources/, keyed back to it via (source, source_table, source_file, pdf_page).
Full mapping documentation: curated/OBLIGATIONS.md.

Sources drawn on
----------------
pkkp (basis=audited_memorandum, FY2009-FY2024, each year from its own volume):
    fact_memorandum              Penyata Akaun Memorandum headline lines
    fact_debt                    Nota 10 Komitmen Kewangan component totals (2018+)
    fact_guarantees              Komitmen Jaminan register by entity (2018+)
    fact_statutory_guarantees    Jaminan Berkanun register by entity (2009+)
    fact_memo_assets_detail      Nota 9 Akaun Belum Terima split + tunggakan memo rows (2018+)
audit-negara (basis=ag_analysis, LKAN 3/2025 -> FY2024 + FY2023 comparatives):
    fact_lkan_fiscal_tables_2024 Jadual II.21 is skipped (duplicate of II.28+II.22);
                                 II.22, II.28, II.29, II.30, II.33 and II.b.1 are used
mof-fiscal-outlook (basis=official_outlook, FO2025 + FO2026 editions):
    fact_contingent_liabilities  Jadual 5.1-5.4 (note: second column of each table
                                 is an end-JUNE position -- see `asof`)

obligation_class / subclass map (see OBLIGATIONS.md for the full rationale)
---------------------------------------------------------------------------
hutang               federal debt stock (memorandum liability line)
pfi                  PFI liabilities (first disclosed by PKKP in FY2018)
komitmen             financial commitments; subclass: '' (headline line),
                     jaminan / pajakan_kewangan / bayaran_balik_cukai / pampasan
                     (Nota 10 components -- the jaminan component equals the
                     jaminan-class register total: never sum class totals with
                     component rows), liabiliti_lain_ppp_pfi (FO residual)
jaminan              COMMITTED guarantees (government services the debt);
                     subclass komitmen_jaminan; 2009 volume's memorandum
                     JAMINAN line is subclass memorandum_2009 (that era printed
                     the whole guarantee register as one memorandum line)
contingent           contingent exposure: statutory-guarantee register
                     (berkanun_pencarum / berkanun_pinjaman / berkanun_total --
                     overlapping cover, do NOT sum with other classes) and the
                     MOF Jaminan Kewangan tables (kewangan_akta96,
                     kewangan_akta61 and its ikatan/skim split, kewangan_total)
abt_hasil            receivables owed TO the government; subclass abt_total /
                     pinjaman_boleh_dituntut / pelbagai_abt / hasil /
                     pelbagai_abt_component / tunggakan_* (arrears memo rows)
pelbagai_liabiliti   miscellaneous liabilities memorandum line

Summation rule: only sum row_type='detail' rows within one (source,
source_table, year); 'line' rows are one-per-concept headline figures.

Run:  python3 curated/pipeline/build_obligations.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKKP = ROOT / "sources" / "pkkp" / "data"
AG = ROOT / "sources" / "audit-negara" / "data"
MOF = ROOT / "sources" / "mof-fiscal-outlook" / "data"
OUT = ROOT / "curated"

YEARS = [str(y) for y in range(2009, 2025)]

COLS = ["source", "basis", "year", "asof", "obligation_class", "subclass",
        "group_bm", "line_bm", "row_type", "amount_rm", "unit_original",
        "value_printed", "source_table", "source_file", "pdf_page",
        "printed_page", "statement", "note"]


def read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def money(v):
    """Parse a source-layer printed value: commas, parentheses = negative,
    en-dash/hyphen = nil (repo convention)."""
    v = v.strip()
    if v in ("", "-", "–"):
        return 0.0
    neg = v.startswith("(") and v.endswith(")")
    x = float(v.strip("()").replace(",", ""))
    return -x if neg else x


def row(source, basis, year, asof, klass, subclass, group, line, row_type,
        amount, unit, printed, table, sf, pdf, pp, stmt, note=""):
    return dict(zip(COLS, [source, basis, year, asof, klass, subclass, group,
                           line, row_type, amount, unit, printed, table, sf,
                           pdf, pp, stmt, note]))


# ---------------------------------------------------------------------------
# PKKP
# ---------------------------------------------------------------------------

MEMO_LIAB_MAP = {
    # printed line (upper-cased) -> (class, subclass, note)
    "HUTANG AWAM": ("hutang", "", "pre-2016 label for Hutang Persekutuan"),
    "HUTANG PERSEKUTUAN": ("hutang", "", ""),
    "JAMINAN": ("jaminan", "memorandum_2009",
                "2009 presentation: guarantee register total printed as a "
                "memorandum liability line"),
    "LIABILITI INISIATIF PEMBIAYAAN SWASTA": ("pfi", "", ""),
    "KOMITMEN KEWANGAN": ("komitmen", "", ""),
    "PELBAGAI LIABILITI": ("pelbagai_liabiliti", "", ""),
}
MEMO_ASSET_MAP = {
    "AKAUN BELUM TERIMA": ("abt_hasil", "abt_total", ""),
    "PINJAMAN BOLEH DITUNTUT": (
        "abt_hasil", "pinjaman_boleh_dituntut",
        "pre-2018 memorandum asset line; era has no Pelbagai ABT line "
        "(revenue arrears not disclosed in PKKP before FY2018)"),
    "PINJAMAN DAN PENDAHULUAN BOLEH DITUNTUT": (
        "abt_hasil", "pinjaman_boleh_dituntut",
        "pre-2018 memorandum asset line; era has no Pelbagai ABT line "
        "(revenue arrears not disclosed in PKKP before FY2018)"),
}
COMMIT_COMPONENT_MAP = {
    "KOMITMEN JAMINAN": ("jaminan",
                         "equals the jaminan-class register total (Nota 10 "
                         "rounds the register to whole RM)"),
    "KOMITMEN PAJAKAN KEWANGAN": ("pajakan_kewangan", ""),
    "KOMITMEN BAYARAN BALIK CUKAI": ("bayaran_balik_cukai",
                                     "unpaid tax refunds incl. GST"),
    "KOMITMEN PAMPASAN": ("pampasan", "highway-concession & other compensation"),
}


def pkkp_rows():
    rows = []
    for y in YEARS:
        d = PKKP / y
        asof = f"{y}-12-31"

        for r in read(d / "fact_memorandum.csv"):
            if r["year"] != y:
                continue
            key = r["line_item_bm"].upper()
            sec = r["section"].upper()
            if key.startswith("JUMLAH"):
                continue  # printed totals -> used in validation only
            if "LIABILITI" in sec and key in MEMO_LIAB_MAP:
                klass, sub, note = MEMO_LIAB_MAP[key]
            elif "ASET" in sec and key in MEMO_ASSET_MAP:
                klass, sub, note = MEMO_ASSET_MAP[key]
            else:
                # Pelaburan / 2009 'JAMINAN DEPOSIT BERKANUN' asset line:
                # investments, not obligations -- excluded (see OBLIGATIONS.md)
                continue
            rows.append(row("pkkp", "audited_memorandum", y, asof, klass, sub,
                            r["section"], r["line_item_bm"], "line",
                            float(r["amount_rm"]), "RM", "",
                            f"pkkp:{y}:fact_memorandum", r["source_file"],
                            r["pdf_page"], r["printed_page"], r["statement"],
                            note))

        # Nota 10 Komitmen Kewangan component totals (modern presentation only)
        p = d / "fact_debt.csv"
        for r in read(p):
            if r["year"] != y or r["kind"] != "commitment_total":
                continue
            sub, note = COMMIT_COMPONENT_MAP[r["item_bm"].upper()]
            rows.append(row("pkkp", "audited_memorandum", y, asof, "komitmen",
                            sub, r["group_bm"], r["item_bm"], "component",
                            float(r["amount_rm"]), "RM", "",
                            f"pkkp:{y}:fact_debt", r["source_file"],
                            r["pdf_page"], r["printed_page"], r["statement"],
                            note))

        # Komitmen Jaminan register by entity (Lampiran, 2018+)
        p = d / "fact_guarantees.csv"
        if p.exists():
            for r in read(p):
                if r["year"] != y:
                    continue
                rows.append(row("pkkp", "audited_memorandum", y, asof,
                                "jaminan", "komitmen_jaminan",
                                r.get("kategori_bm", ""), r["agensi_bm"],
                                r["row_type"], float(r["jumlah_rm"]), "RM", "",
                                f"pkkp:{y}:fact_guarantees", r["source_file"],
                                r["pdf_page"], r["printed_page"],
                                r["statement"]))

        # Jaminan Berkanun register by entity (all years)
        for r in read(d / "fact_statutory_guarantees.csv"):
            if r["year"] != y:
                continue
            jenis = r["jenis_jaminan_bm"].upper()
            agensi = r["agensi_bm"].upper()
            if "PENCARUM" in jenis:
                sub = "berkanun_pencarum"
            elif r["row_type"] == "total":
                sub = "berkanun_total"
            else:
                sub = "berkanun_pinjaman"
            note = ""
            if sub == "berkanun_total" and int(y) <= 2011:
                note = ("register has no pencarum/pendeposit section before "
                        "the 2012 volume: total = loan guarantees only")
            rt = "detail" if r["row_type"] == "line" else r["row_type"]
            rows.append(row("pkkp", "audited_memorandum", y, asof,
                            "contingent", sub,
                            r["jenis_jaminan_bm"] or r["kategori_bm"],
                            r["agensi_bm"], rt, float(r["jumlah_rm"]), "RM",
                            "", f"pkkp:{y}:fact_statutory_guarantees",
                            r["source_file"], r["pdf_page"],
                            r["printed_page"], r["statement"], note))

        # Nota 9 ABT split + tunggakan (arrears) memo rows (2018+)
        if int(y) >= 2018:
            for r in read(d / "fact_memo_assets_detail.csv"):
                if r["year"] != y or not r["section_bm"].startswith(
                        "Akaun Belum Terima -"):
                    continue
                li = r["line_item_bm"]
                if r["row_type"] == "subtotal":
                    sub = ("pinjaman_boleh_dituntut" if "PINJAMAN" in li.upper()
                           else "pelbagai_abt")
                elif r["row_type"] == "memo" and li.startswith("Tunggakan"):
                    sub = ("tunggakan_faedah_pinjaman" if "faedah" in li
                           else "tunggakan_pelbagai_abt")
                else:
                    continue  # borrower-level detail stays in the source layer
                rows.append(row("pkkp", "audited_memorandum", y, asof,
                                "abt_hasil", sub, r["section_bm"], li,
                                r["row_type"], float(r["amount_rm"]), "RM", "",
                                f"pkkp:{y}:fact_memo_assets_detail",
                                r["source_file"], r["pdf_page"],
                                r["printed_page"], r["statement"]))
    return rows


# ---------------------------------------------------------------------------
# Auditor-General (LKAN 3/2025 fiscal analysis of FY2024, with FY2023 comparatives)
# ---------------------------------------------------------------------------

AG_UNIT = {"RM Bilion": 1e9, "RM Juta": 1e6}


def ag_rows():
    src = read(AG / "fact_lkan_fiscal_tables_2024.csv")
    rows = []

    def emit(r, year, klass, sub, group, rt, note="", amount=None):
        mult = AG_UNIT[r["unit"]]
        amt = money(r["value_verbatim"]) * mult if amount is None else amount
        rows.append(row("audit-negara", "ag_analysis", year, f"{year}-12-31",
                        klass, sub, group, r["row_label_bm"], rt, amt,
                        r["unit"], r["value_verbatim"],
                        f"audit-negara:fact_lkan_fiscal_tables_2024:"
                        f"{r['bahagian']}.J{r['jadual_no']}", r["source_file"],
                        r["pdf_page"], "", r["jadual_title_bm"], note))

    j28 = {"Hutang Persekutuan": ("hutang", ""),
           "Komitmen Kewangan": ("komitmen", ""),
           "Liabiliti PFI": ("pfi", ""),
           "Pelbagai Liabiliti": ("pelbagai_liabiliti", "")}
    j29 = {"Komitmen Jaminan": "jaminan",
           "Komitmen Bayaran Balik Cukai": "bayaran_balik_cukai",
           "Komitmen Pajakan Kewangan": "pajakan_kewangan",
           "Komitmen Pampasan": "pampasan"}
    j22 = {"Pinjaman dan Pendahuluan Boleh Dituntut": "pinjaman_boleh_dituntut",
           "Pelbagai ABT": "pelbagai_abt", "JUMLAH": "abt_total"}

    for r in src:
        bah, jad, lab, col = (r["bahagian"], r["jadual_no"],
                              r["row_label_bm"], r["col_label_bm"])
        if bah == "II" and jad == "28" and col in ("2024", "2023") \
                and lab in j28:
            klass, sub = j28[lab]
            emit(r, col, klass, sub, "MEMORANDUM LIABILITI", "line")
        elif bah == "II" and jad == "29" and col in ("2024", "2023") \
                and lab in j29:
            emit(r, col, "komitmen", j29[lab], "Komitmen Kewangan",
                 "component",
                 "equals the jaminan-class total" if lab == "Komitmen Jaminan"
                 else "")
        elif bah == "II" and jad == "22" and col in ("2024", "2023") \
                and lab in j22:
            emit(r, col, "abt_hasil", j22[lab], "MEMORANDUM ASET",
                 "total" if lab == "JUMLAH" else "line")
        elif bah == "II.b" and jad == "1" and col in ("2024", "2023"):
            sub = ("hasil" if lab == "Hasil" else
                   "abt_total" if lab == "JUMLAH" else
                   "pelbagai_abt_component")
            emit(r, col, "abt_hasil", sub, "Pelbagai ABT",
                 "total" if lab == "JUMLAH" else "detail",
                 "revenue arrears (tunggakan hasil)" if lab == "Hasil" else "")
        elif bah == "II" and jad == "30" and r["unit"] == "RM Bilion":
            # header row could not be rebuilt by the AG extraction:
            # lajur 1 = 2024, lajur 2 = 2023 (verified against II.29 & PKKP)
            year = {"lajur 1": "2024", "lajur 2": "2023"}.get(col[:7])
            if year and r["row_label_bm"] not in ("SYARIKAT",
                                                  "BADAN BERKANUN PERSEKUTUAN"):
                rt = {"line": "detail"}.get(r["row_type"], r["row_type"])
                emit(r, year, "jaminan", "komitmen_jaminan", "", rt,
                     "col heading rebuilt as " + year)
        elif bah == "II" and jad == "33" and r["unit"] == "RM Bilion":
            # lajur 2 = amount 2024, lajur 4 = amount 2023 (lajur 1/3 = counts)
            year = {"lajur 2": "2024", "lajur 4": "2023"}.get(col[:7])
            if not year:
                continue
            if "PENCARUM" in lab.upper():
                sub, rt = "berkanun_pencarum", "detail"
            elif lab == "Jumlah Jaminan Pinjaman":
                sub, rt = "berkanun_pinjaman", "subtotal"
            elif lab == "JUMLAH KESELURUHAN":
                sub, rt = "berkanun_total", "total"
            elif lab in ("Badan Berkanun", "Syarikat"):
                sub, rt = "berkanun_pinjaman", "detail"
            else:
                continue
            emit(r, year, "contingent", sub, "Jaminan Berkanun", rt,
                 "col heading rebuilt as " + year)
    return rows


# ---------------------------------------------------------------------------
# MOF Fiscal Outlook
# ---------------------------------------------------------------------------

FO_J52_SUB = {
    "Jaminan di bawah Akta 96": "kewangan_akta96",
    "Jaminan di bawah Akta 61": "kewangan_akta61",
    "Ikatan dan Sokongan": "kewangan_akta61_ikatan",
    "Skim Jaminan": "kewangan_akta61_skim",
    "Jumlah": "kewangan_total",
}


def mof_rows():
    src = read(MOF / "fact_contingent_liabilities.csv")
    rows = []
    for r in src:
        j, line = r["jadual_no"], r["line_bm"]
        if j == "5.1":
            if line == "Hutang Kerajaan Persekutuan":
                klass, sub, rt, note = "hutang", "", "line", ""
            elif line == "Komitmen jaminan":
                klass, sub, rt, note = "jaminan", "komitmen_jaminan", "line", ""
            elif line == "Liabiliti lain":
                klass, sub, rt, note = ("komitmen", "liabiliti_lain_ppp_pfi",
                                        "line", "PPP + PFI obligations (+ PBLT "
                                        "in FO2025); narrower than PKKP "
                                        "Komitmen Kewangan")
            else:
                continue  # Jumlah mixes classes -> validation only
        elif j == "5.2":
            klass, sub, rt, note = ("contingent", FO_J52_SUB[line],
                                    r["row_type"], "")
        elif j == "5.3":
            klass, sub, rt, note = ("contingent", "kewangan_akta96",
                                    r["row_type"],
                                    "recipient detail of Jaminan di bawah "
                                    "Akta 96")
        else:  # 5.4
            klass, sub, rt, note = "jaminan", "komitmen_jaminan", r["row_type"], ""
        if r["asof"].endswith("-06-30"):
            note = (note + "; " if note else "") + "mid-year (Akhir Jun) position"
        rows.append(row("mof-fiscal-outlook", "official_outlook", r["col_year"],
                        r["asof"], klass, sub,
                        f"FO{r['edition_year']} Jadual {j}", line, rt,
                        float(r["amount_rm"]), r["unit"], r["value_printed"],
                        f"mof-fiscal-outlook:fact_contingent_liabilities:"
                        f"FO{r['edition_year']}.J{j}", r["source_file"],
                        r["pdf_page"], r["printed_page"],
                        r["jadual_title_bm"], note))
    return rows


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(rows):
    checks = []

    def add(name, expected, derived, tol, kind="TIE"):
        diff = derived - expected
        checks.append({"check": name, "kind": kind,
                       "status": "PASS" if abs(diff) <= tol else "FAIL",
                       "expected_rm": expected, "derived_rm": derived,
                       "difference_rm": diff, "tolerance_rm": tol})

    def sel(**kw):
        out = rows
        for k, v in kw.items():
            out = [r for r in out if r[k] == v]
        return out

    def one(**kw):
        m = sel(**kw)
        assert len(m) == 1, (kw, len(m))
        return m[0]["amount_rm"]

    def ssum(**kw):
        return sum(r["amount_rm"] for r in sel(**kw))

    # ---- PKKP tie-backs -------------------------------------------------
    for y in YEARS:
        memo = {r["line_item_bm"].upper(): float(r["amount_rm"])
                for r in read(PKKP / y / "fact_memorandum.csv")
                if r["year"] == y}
        t = f"pkkp:{y}:fact_memorandum"
        if "JUMLAH LIABILITI" in memo:
            add(f"pkkp {y}: memorandum liability lines sum to printed "
                f"Jumlah Liabiliti", memo["JUMLAH LIABILITI"],
                sum(r["amount_rm"] for r in sel(source_table=t)
                    if r["obligation_class"] in
                    ("hutang", "pfi", "komitmen", "pelbagai_liabiliti")), 0.01)
        if int(y) >= 2018:
            add(f"pkkp {y}: Nota 10 komitmen components sum to memorandum "
                f"Komitmen Kewangan",
                one(source_table=t, obligation_class="komitmen"),
                ssum(source_table=f"pkkp:{y}:fact_debt"), 0.01)
            g = f"pkkp:{y}:fact_guarantees"
            add(f"pkkp {y}: komitmen jaminan register detail sums to its "
                f"printed total", one(source_table=g, row_type="total"),
                ssum(source_table=g, row_type="detail"), 0.01)
            add(f"pkkp {y}: komitmen jaminan register total = Nota 10 "
                f"KOMITMEN JAMINAN (Nota 10 rounds to whole RM)",
                one(source_table=f"pkkp:{y}:fact_debt", subclass="jaminan"),
                one(source_table=g, row_type="total"), 1.0)
            add(f"pkkp {y}: Nota 9 ABT split sums to memorandum Akaun Belum "
                f"Terima", one(source_table=t, subclass="abt_total"),
                ssum(source_table=f"pkkp:{y}:fact_memo_assets_detail",
                     row_type="subtotal"), 0.01)
        sg = f"pkkp:{y}:fact_statutory_guarantees"
        det = ssum(source_table=sg, row_type="detail")
        tot = one(source_table=sg, subclass="berkanun_total")
        add(f"pkkp {y}: jaminan berkanun register detail sums to its printed "
            f"JUMLAH JAMINAN", tot, det, 0.01)
        if y == "2009":
            add("pkkp 2009: memorandum JAMINAN line = guarantee register "
                "total (memorandum statement prints whole RM, register keeps "
                "sen)", one(source_table=t, obligation_class="jaminan"),
                tot, 1.0)

    # ---- AG internal tie-backs -----------------------------------------
    agsrc = read(AG / "fact_lkan_fiscal_tables_2024.csv")

    def ag_printed(bah, jad, lab, col_prefix):
        m = [r for r in agsrc if r["bahagian"] == bah and r["jadual_no"] == jad
             and r["row_label_bm"] == lab
             and r["col_label_bm"].startswith(col_prefix)
             and r["unit"] in AG_UNIT]
        assert len(m) == 1, (bah, jad, lab, col_prefix, len(m))
        return money(m[0]["value_verbatim"]) * AG_UNIT[m[0]["unit"]]

    for y, lajur in (("2024", "lajur 1"), ("2023", "lajur 2")):
        j28t = f"audit-negara:fact_lkan_fiscal_tables_2024:II.J28"
        add(f"ag {y}: J28 liability lines sum to printed JUMLAH",
            ag_printed("II", "28", "JUMLAH", y),
            ssum(source_table=j28t, year=y), 0.5e6)
        add(f"ag {y}: J29 komitmen components sum to printed JUMLAH "
            f"KESELURUHAN", ag_printed("II", "29", "JUMLAH KESELURUHAN", y),
            ssum(source_table="audit-negara:fact_lkan_fiscal_tables_2024:"
                              "II.J29", year=y), 0.5e6)
        add(f"ag {y}: J29 komitmen components = J28 Komitmen Kewangan line",
            one(source_table=j28t, year=y, obligation_class="komitmen"),
            ssum(source_table="audit-negara:fact_lkan_fiscal_tables_2024:"
                              "II.J29", year=y), 1e6)
        j30 = "audit-negara:fact_lkan_fiscal_tables_2024:II.J30"
        add(f"ag {y}: J30 entity guarantees sum to printed JUMLAH KESELURUHAN",
            one(source_table=j30, year=y, row_type="total"),
            ssum(source_table=j30, year=y, row_type="detail"), 0.5e6)
        add(f"ag {y}: J30 total = J29 Komitmen Jaminan component",
            one(source_table="audit-negara:fact_lkan_fiscal_tables_2024:"
                             "II.J29", year=y, subclass="jaminan"),
            one(source_table=j30, year=y, row_type="total"), 0.5e6)
        j22 = "audit-negara:fact_lkan_fiscal_tables_2024:II.J22"
        add(f"ag {y}: J22 ABT components sum to printed JUMLAH",
            one(source_table=j22, year=y, subclass="abt_total"),
            ssum(source_table=j22, year=y, row_type="line"), 0.5e6)
        jb1 = "audit-negara:fact_lkan_fiscal_tables_2024:II.b.J1"
        add(f"ag {y}: II.b J1 Pelbagai ABT components sum to printed JUMLAH",
            one(source_table=jb1, year=y, subclass="abt_total"),
            ssum(source_table=jb1, year=y, row_type="detail"), 0.5e6)
        add(f"ag {y}: II.b J1 JUMLAH = J22 Pelbagai ABT line",
            one(source_table=j22, year=y, subclass="pelbagai_abt"),
            one(source_table=jb1, year=y, subclass="abt_total"), 0.5e6)
        j33 = "audit-negara:fact_lkan_fiscal_tables_2024:II.J33"
        add(f"ag {y}: J33 jaminan pinjaman detail sums to its subtotal",
            one(source_table=j33, year=y, subclass="berkanun_pinjaman",
                row_type="subtotal"),
            ssum(source_table=j33, year=y, subclass="berkanun_pinjaman",
                 row_type="detail"), 0.5e6)
        add(f"ag {y}: J33 pencarum + pinjaman = JUMLAH KESELURUHAN",
            one(source_table=j33, year=y, subclass="berkanun_total"),
            one(source_table=j33, year=y, subclass="berkanun_pencarum") +
            one(source_table=j33, year=y, subclass="berkanun_pinjaman",
                row_type="subtotal"), 0.5e6)

    # ---- MOF internal tie-backs (already validated at source; re-assert) --
    for ed, cols, tol in (("2025", ("2023", "2024"), 0.05e9),
                          ("2026", ("2024", "2025"), 0.5e6)):
        for cy in cols:
            t54 = f"mof-fiscal-outlook:fact_contingent_liabilities:FO{ed}.J5.4"
            add(f"mof FO{ed} [{cy}]: J5.4 entities sum to printed Jumlah",
                one(source_table=t54, year=cy, row_type="total"),
                ssum(source_table=t54, year=cy, row_type="detail"), 0.5e6)
            t52 = f"mof-fiscal-outlook:fact_contingent_liabilities:FO{ed}.J5.2"
            add(f"mof FO{ed} [{cy}]: J5.2 Akta96 + Akta61 = printed Jumlah",
                one(source_table=t52, year=cy, subclass="kewangan_total"),
                one(source_table=t52, year=cy, subclass="kewangan_akta96") +
                one(source_table=t52, year=cy, subclass="kewangan_akta61"),
                tol)
            t53 = f"mof-fiscal-outlook:fact_contingent_liabilities:FO{ed}.J5.3"
            add(f"mof FO{ed} [{cy}]: J5.3 recipients + others = printed Jumlah",
                one(source_table=t53, year=cy, row_type="total"),
                ssum(source_table=t53, year=cy, row_type="detail") +
                0.0, 0.5e6 * 11)

    # ---- cross-source reconciliation (rounding of the coarser source) ----
    x = [("2024 hutang: PKKP exact vs AG (RM bilion, 3dp)",
          ("pkkp:2024:fact_memorandum", dict(obligation_class="hutang")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.J28",
           dict(year="2024", obligation_class="hutang")), 0.5e6),
         ("2024 hutang: PKKP exact vs FO2026 (RM juta)",
          ("pkkp:2024:fact_memorandum", dict(obligation_class="hutang")),
          ("mof-fiscal-outlook:fact_contingent_liabilities:FO2026.J5.1",
           dict(year="2024", obligation_class="hutang")), 0.5e6),
         ("2024 komitmen kewangan: PKKP exact vs AG",
          ("pkkp:2024:fact_memorandum", dict(obligation_class="komitmen")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.J28",
           dict(year="2024", obligation_class="komitmen")), 0.5e6),
         ("2024 PFI: PKKP exact vs AG (AG prints 32.905, truncation of "
          "32.9056)",
          ("pkkp:2024:fact_memorandum", dict(obligation_class="pfi")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.J28",
           dict(year="2024", obligation_class="pfi")), 1e6),
         ("2024 komitmen jaminan: PKKP register vs FO2026 J5.4",
          ("pkkp:2024:fact_guarantees", dict(row_type="total")),
          ("mof-fiscal-outlook:fact_contingent_liabilities:FO2026.J5.4",
           dict(year="2024", row_type="total")), 0.5e6),
         ("2023 komitmen jaminan: PKKP register vs FO2025 J5.4",
          ("pkkp:2023:fact_guarantees", dict(row_type="total")),
          ("mof-fiscal-outlook:fact_contingent_liabilities:FO2025.J5.4",
           dict(year="2023", row_type="total")), 0.5e6),
         ("2024 jaminan berkanun (pinjaman): PKKP register vs AG J33",
          ("pkkp:2024:fact_statutory_guarantees",
           dict(line_bm="JUMLAH JAMINAN PINJAMAN")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.J33",
           dict(year="2024", subclass="berkanun_pinjaman",
                row_type="subtotal")), 0.5e6),
         ("2024 jaminan berkanun (pinjaman): PKKP register vs FO2026 J5.2 "
          "Akta 96",
          ("pkkp:2024:fact_statutory_guarantees",
           dict(line_bm="JUMLAH JAMINAN PINJAMAN")),
          ("mof-fiscal-outlook:fact_contingent_liabilities:FO2026.J5.2",
           dict(year="2024", subclass="kewangan_akta96")), 0.5e6),
         ("2024 ABT: PKKP exact vs AG J22",
          ("pkkp:2024:fact_memorandum", dict(subclass="abt_total")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.J22",
           dict(year="2024", subclass="abt_total")), 0.5e6),
         ("2024 pelbagai ABT: PKKP Nota 9 vs AG II.b J1 JUMLAH",
          ("pkkp:2024:fact_memo_assets_detail", dict(subclass="pelbagai_abt")),
          ("audit-negara:fact_lkan_fiscal_tables_2024:II.b.J1",
           dict(year="2024", subclass="abt_total")), 5e3),
         ]
    for name, (ta, ka), (tb, kb), tol in x:
        add("xsource " + name, one(source_table=ta, **ka),
            one(source_table=tb, **kb), tol, kind="CROSS")
    return checks


def main():
    rows = pkkp_rows() + ag_rows() + mof_rows()
    checks = validate(rows)
    with open(OUT / "fact_obligations.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "_validation_obligations.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(checks[0].keys()))
        w.writeheader()
        w.writerows(checks)
    npass = sum(c["status"] == "PASS" for c in checks)
    print(f"fact_obligations.csv: {len(rows)} rows | "
          f"validation: {npass}/{len(checks)} PASS")
    for c in checks:
        if c["status"] != "PASS":
            print("FAIL:", c["check"], c["expected_rm"], c["derived_rm"])
    sys.exit(0 if npass == len(checks) else 1)


if __name__ == "__main__":
    main()
