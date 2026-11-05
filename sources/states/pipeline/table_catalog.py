"""What to extract from a state LKAN volume, expressed only as *title regexes*.

Nothing here is state-specific: the Jabatan Audit Negara prints the same
analysis tables, with the same Malay titles, in every state's volume.  Adding a
state means adding an entry to `state_config.VOLUMES`, not editing this file.

Titles drift between eras (`Jadual 4.5 Kedudukan ... Tahun 2015 Berbanding 2014`
-> `JADUAL 7 KEDUDUKAN ... PADA TAHUN 2020 BERBANDING 2019` -> `JADUAL 5
KEDUDUKAN ... PADA TAHUN 2024 BERBANDING 2023`), so every regex is matched
case-insensitively against the whitespace-collapsed title.

They also drift BETWEEN STATES, because each state audit office writes its own
titles from the same template: `KEDUDUKAN AKAUN DEPOSIT PADA TAHUN` (Selangor)
vs `KEDUDUKAN AKAUN DEPOSIT BAGI TAHUN` (Sarawak); `KEDUDUKAN AKAUN HASIL
DISATUKAN` vs `PRESTASI AKAUN HASIL DISATUKAN` vs `PRESTASI KEWANGAN AKAUN
HASIL DISATUKAN`.  Every spec therefore allows the same closed set of leading
qualifiers (`_PRE`) and the same closed set of period phrases (`_PER`); the
qualifier set is deliberately closed so that `TUNGGAKAN ...`, `JUSTIFIKASI ...`,
`PENGUMURAN ...` and `PULANGAN ...` tables can never be mistaken for the
statement they qualify.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# table specs
# ---------------------------------------------------------------------------
# (spec_id, target csv, statement, title regex)
#   target: 'finance' -> fact_state_finance, 'revenue' -> fact_state_revenue

# leading qualifiers a state audit office may print before the statement name
_PRE = (r"^(?:(?:kedudukan|prestasi|trend|analisis|perbandingan|pergerakan|"
        r"penyata|kewangan|baki|jumlah|ringkasan)\s+){0,4}")
# The period phrase that closes a table title.  It is REQUIRED: it is what
# separates the statement table (`PERBELANJAAN PEMBANGUNAN PADA TAHUN ...`)
# from the many narrative tables built on the same noun phrase
# (`PERBELANJAAN PEMBANGUNAN KURANG DARIPADA 50% BERBANDING PERUNTUKAN`,
# `AKAUN DEPOSIT BERBAKI DEBIT`, `AKAUN BELUM TERIMA MELEBIHI ENAM TAHUN`).
_PER = r"(?:pada|bagi|tahun|dan|berbanding|sehingga|setakat)\b"
# ... except where a state prints the title bare (`KEDUDUKAN BAKI PINJAMAN
# BOLEH DITUNTUT`, Selangor FY2023).
_PERO = r"(?:(?:pada|bagi|tahun|dan|berbanding|sehingga|setakat)\b)?"

SPECS: list[tuple[str, str, str, str]] = [
    # ---- Penyata Prestasi Kewangan (the headline fund-flow statement) -------
    # `(?!... akaun hasil)`: `PRESTASI KEWANGAN AKAUN HASIL DISATUKAN` is the
    # Consolidated Revenue Account table, not the fund-flow statement.
    # Not anchored at the start: the Pulau Pinang FY2021 volume's text layer
    # emits the title interleaved with the stub column (`Pinjaman KEDUDUKAN
    # PRESTASI KEWANGAN Tolak: Hasil PADA AKHIR TAHUN 2021 ...`).  The agency
    # and local-authority variants are already blocked by `_EXCLUDE` and by the
    # negative lookahead.
    ("prestasi_kewangan", "finance", "penyata_prestasi_kewangan",
     r"(?:^|\b)(?:kedudukan |penyata |trend )?prestasi kewangan\b"
     r"(?!\s+(akaun|badan|pihak|agensi|pbt|bbn))"
     r"[^|]{0,40}?(kerajaan negeri|negeri|pada tahun|bagi tahun|"
     r"pada akhir tahun|tahun \d)"),

    # ---- Penyata Kedudukan Kewangan ----------------------------------------
    ("kumpulan_wang_disatukan", "finance", "penyata_kedudukan_kewangan",
     _PRE + r"kumpulan wang disatukan"),
    ("wang_tunai", "finance", "penyata_kedudukan_kewangan",
     _PRE + r"wang tunai( dan pelaburan)?( kerajaan negeri)? " + _PER),
    ("pelaburan", "finance", "penyata_kedudukan_kewangan",
     _PRE + r"pelaburan( kerajaan negeri| am| saham(?: syarikat)?| mengikut nilai buku)? " + _PER),

    # ---- Akaun Hasil / Pinjaman / Amanah Disatukan --------------------------
    ("akaun_hasil_disatukan", "finance", "akaun_hasil_disatukan",
     _PRE + r"akaun hasil disatukan"),
    ("akaun_pinjaman_disatukan", "finance", "akaun_pinjaman_disatukan",
     _PRE + r"akaun pinjaman disatukan"),
    ("akaun_amanah_disatukan", "finance", "akaun_amanah_disatukan",
     _PRE + r"akaun amanah disatukan"),
    ("kumpulan_wang_pembangunan", "finance", "akaun_amanah_disatukan",
     _PRE + r"kumpulan wang pembangunan(?! hutan)"),
    # The Forest Development Fund is a SEPARATE statutory fund from the
    # Development Fund and its own flow table must not be coded as the
    # Development Fund's (the states that levy Hasil Hutan print both).
    ("kumpulan_wang_pembangunan_hutan", "finance", "akaun_amanah_disatukan",
     _PRE + r"(akaun amanah )?kumpulan wang (amanah )?pembangunan hutan"),
    ("kumpulan_wang_amanah_kerajaan", "finance", "akaun_amanah_disatukan",
     _PRE + r"(pelbagai )?kumpulan wang amanah kerajaan"),
    ("kumpulan_wang_amanah_awam", "finance", "akaun_amanah_disatukan",
     _PRE + r"kumpulan wang amanah awam"),
    ("kumpulan_wang_pinjaman_perumahan", "finance", "akaun_amanah_disatukan",
     r"kumpulan wang (amanah )?pinjaman perumahan " + _PER),
    ("akaun_deposit", "finance", "akaun_amanah_disatukan",
     _PRE + r"(akaun )?deposit " + _PER),

    # ---- expenditure --------------------------------------------------------
    ("perbelanjaan_mengurus", "finance", "perbelanjaan_mengurus",
     _PRE + r"perbelanjaan mengurus( sebenar)?( kerajaan negeri)? "
     r"(sebenar berbanding|berbanding|" + _PER + r")"),
    ("peruntukan_mengurus", "finance", "perbelanjaan_mengurus",
     _PRE + r"peruntukan (diluluskan |muktamad |dan perbelanjaan (sebenar )?)?"
     r"(bagi )?perbelanjaan mengurus"),
    ("perbelanjaan_pembangunan", "finance", "perbelanjaan_pembangunan",
     _PRE + r"(peruntukan dan (prestasi )?)?perbelanjaan pembangunan " + _PER),

    # ---- Penyata Akaun Memorandum ------------------------------------------
    ("hutang_awam", "finance", "akaun_memorandum",
     _PRE + r"hutang awam( kerajaan negeri)? " + _PER),
    ("pinjaman_boleh_dituntut", "finance", "akaun_memorandum",
     _PRE + r"pinjaman boleh dituntut( kerajaan negeri)?(?:\s+" + _PER + r"|\s*$)"),
    # `... MENGIKUT TEMPOH TUNGGAKAN` is the ageing table, a different grain.
    ("akaun_belum_terima", "finance", "akaun_memorandum",
     _PRE + r"(akaun belum terima|abt) (?!mengikut)" + _PER),
    ("aset_liabiliti", "finance", "akaun_memorandum",
     _PRE + r"aset kewangan dan liabiliti"),

    # ---- revenue ------------------------------------------------------------
    # Perlis prints `Kutipan Hasil Berbanding Anggaran` with no `Sebenar`;
    # without this the table falls through to `hasil_kategori` and its
    # ANGGARAN column is tagged `actual`, shipping the estimate as revenue.
    ("hasil_anggaran", "revenue", "akaun_hasil_disatukan",
     r"(kutipan |terimaan )?hasil( sebenar)?( kerajaan negeri)?"
     r"( pada tahun \d{4})? berbanding anggaran"),
    ("hasil_kategori", "revenue", "akaun_hasil_disatukan",
     _PRE + r"(kutipan|terimaan) hasil( sebenar)?( kerajaan(?: negeri)?)? "
     r"(berbanding|" + _PER + r")"),
    ("hasil_penyumbang_utama", "revenue", "akaun_hasil_disatukan",
     r"penyumbang utama hasil|" + _PRE + r"hasil utama kerajaan negeri"),
    # NOT extracted: `JUSTIFIKASI PENINGKATAN/PENURUNAN HASIL YANG KETARA`
    # carries a free-text PUNCA column that the -layout dump interleaves with
    # the row label, so the labels would be unusable.  See README "known gaps".
]

_COMPILED = [(sid, tgt, stmt, re.compile(rx, re.I)) for sid, tgt, stmt, rx in SPECS]

# Specs whose printed rows span several physical lines that ALL carry figures,
# so the row must be assembled from the BIL. column rather than line by line
# (see `lkan_state_parser.parse_rows_by_bil`).
BIL_GROUPED_SPECS = {"hasil_penyumbang_utama"}

# Specs printed as a strict tiered ladder with its own section captions
# (`HASIL:` / `TOLAK:` / `PERBELANJAAN` / `DIBIAYAI OLEH:`).  Their labels must
# be joined by INDENT, not by distance, or a caption gets welded onto the row
# above it and a wrapped cell onto the row below it.
SECTIONED_SPECS = {"prestasi_kewangan"}

# Titles that must never be treated as state-government finance: the agency /
# local-authority halves of the volume reuse similar wording.
_EXCLUDE = re.compile(
    r"\b(agensi|badan berkanun|pihak berkuasa tempatan|pbt|bbn|syarikat|"
    r"subsidiari|majlis agama|msns|mbsj|mdsb|ppas)\b", re.I)


def classify(heading: str, in_state_section: bool) -> tuple[str, str, str] | None:
    """-> (spec_id, target, statement) or None.

    `heading` must be the printed JADUAL title with the column-header block
    stripped (`lkan_state_parser.heading_of`); otherwise header words such as
    AGENSI trip the agency-section filter.
    """
    t = re.sub(r"\s+", " ", heading).strip()
    if not in_state_section or _EXCLUDE.search(t):
        return None
    for sid, tgt, stmt, rx in _COMPILED:
        if rx.search(t):
            return sid, tgt, stmt
    return None


# ---------------------------------------------------------------------------
# conformed line codes
# ---------------------------------------------------------------------------
# (spec_id regex | '*', label regex, line_code).  First match wins; labels are
# matched against the normalised (ASCII-folded, lower-cased) printed label.

LINE_CODES: list[tuple[str, str, str]] = [
    # --- Penyata Prestasi Kewangan -----------------------------------------
    ("prestasi_kewangan", r"^hasil cukai$", "revenue_tax"),
    ("prestasi_kewangan", r"^hasil bukan cukai$", "revenue_nontax"),
    # `Teriman Bukan Hasil` is a printer's typo in the Kelantan volumes; the
    # label is kept verbatim in `line_label_bm`, only the CODE is tolerant.
    ("prestasi_kewangan", r"^teri?maan bukan hasil$", "revenue_nonrevenue_receipts"),
    # `Hasil Tolak` (Kedah) is `Hasil` with the following `Tolak:` (less)
    # caption typeset on the same line.
    ("prestasi_kewangan", r"^(jumlah )?hasil( tolak)?$", "revenue_total"),
    # `Perbelanjaan Mengurus (Selepas Pindahan)` is the AFTER-transfer figure
    # and is not the same quantity as `opex_before_transfer`; Kelantan's own
    # series would otherwise mix the two bases silently.
    ("prestasi_kewangan", r"belanja(an)? mengurus\s*\(?\s*(selepas|termasuk) pindahan",
     "opex_after_transfer"),
    # Pahang's third expenditure head (CMD.37.2017 p51 J4.31: 629.27 + 91.66 + 89.95 = 810.88)
    ("prestasi_kewangan", r"belanja(an)? bekalan air", "expenditure_water_supply"),
    ("prestasi_kewangan", r"belanja(an)? mengurus", "opex_before_transfer"),
    ("prestasi_kewangan", r"belanja(an)? pembangunan", "devex_total"),
    ("prestasi_kewangan", r"^jumlah perbelanjaan", "expenditure_total"),
    # A bare `PERBELANJAAN` / `PEMBIAYAAN` row that carries figures IS the
    # section total (Sabah, Sarawak, Melaka print it that way; Selangor and
    # Johor print `JUMLAH PERBELANJAAN`).
    ("prestasi_kewangan", r"^perbelanjaan$", "expenditure_total"),
    ("prestasi_kewangan", r"^pembiayaan$", "financing_total"),
    # The financing lines are tested BEFORE the surplus line: several states
    # print the surplus caption and the first financing line on one physical
    # line (`Kurangan dibiayai oleh: Terimaan Balik Pinjaman ...`), and the row
    # is the financing line, not the surplus.
    ("prestasi_kewangan", r"pinjaman dan bantuan luar negeri", "financing_external_loans"),
    # domestic borrowing, printed under the same `Dibiayai Oleh:` caption
    ("prestasi_kewangan", r"^pinjaman dalam negeri|^pinjaman$", "financing_domestic_loans"),
    ("prestasi_kewangan", r"terimaan balik pinjaman", "financing_loan_repayment"),
    ("prestasi_kewangan", r"perubahan tunai", "financing_cash_investment_trust"),
    ("prestasi_kewangan", r"^jumlah pembiayaan", "financing_total"),
    ("prestasi_kewangan", r"^(lebihan|defisit|surplus|kurangan)", "surplus_deficit"),
    # A bare `JUMLAH` inside the Penyata Prestasi Kewangan is resolved from the
    # printed section heading it sits under (see `section_group`).
    ("prestasi_kewangan", r"^jumlah @hasil$", "revenue_total"),
    ("prestasi_kewangan", r"^jumlah @perbelanjaan$", "expenditure_total"),
    ("prestasi_kewangan", r"^jumlah @pembiayaan$", "financing_total"),

    # --- Akaun Hasil Disatukan ---------------------------------------------
    ("akaun_hasil_disatukan", r"baki pada 1 januari", "cra_opening_balance"),
    ("akaun_hasil_disatukan", r"^\(?\+?\)? ?hasil$", "revenue_total"),
    ("akaun_hasil_disatukan", r"perbelanjaan mengurus", "opex_total"),
    # Kedah and Pulau Pinang print TWO current-surplus lines: the revenue
    # surplus BEFORE the transfers out of the Consolidated Revenue Account
    # (`Lebihan Hasil Semasa`) and the surplus after them (`Lebihan/(Kurangan)
    # Semasa`).  They are different quantities and must not share a code.
    ("akaun_hasil_disatukan", r"^(lebihan|kurangan|surplus|defisit)[^ ]* hasil semasa",
     "cra_revenue_surplus"),
    ("akaun_hasil_disatukan", r"^(surplus|defisit|lebihan|kurangan)", "cra_surplus_deficit"),
    ("akaun_hasil_disatukan", r"baki pada 31 disember", "cra_closing_balance"),

    # --- Kumpulan Wang Disatukan -------------------------------------------
    ("kumpulan_wang_disatukan", r"^akaun hasil disatukan", "cra_balance"),
    ("kumpulan_wang_disatukan", r"^akaun pinjaman disatukan", "loan_account_balance"),
    ("kumpulan_wang_disatukan", r"^akaun amanah disatukan", "trust_account_balance"),
    # NOTE: `Pelbagai Kumpulan Wang Amanah Kerajaan` is a COMPONENT of
    # `Kumpulan Wang Amanah Kerajaan` - it must be tested first.
    ("kumpulan_wang_disatukan", r"^pelbagai kumpulan wang amanah", "misc_govt_trust_funds"),
    ("kumpulan_wang_disatukan", r"^kumpulan wang amanah kerajaan$", "govt_trust_funds"),
    ("kumpulan_wang_disatukan", r"kumpulan wang pembangunan hutan", "forest_development_fund"),
    ("kumpulan_wang_disatukan", r"kumpulan wang pembangunan", "development_fund"),
    ("kumpulan_wang_disatukan", r"kumpulan wang pinjaman perumahan", "housing_loan_fund"),
    ("kumpulan_wang_disatukan", r"kumpulan wang amanah awam", "public_trust_funds"),
    # Sabah, Sarawak and Negeri Sembilan print `Deposit`, not `Akaun Deposit`
    ("kumpulan_wang_disatukan", r"^(akaun )?(wang )?deposit$|^akaun (wang )?deposit", "deposit_account"),
    ("kumpulan_wang_disatukan", r"^(baki pada 31 disember|jumlah)", "kwd_balance"),

    # --- cash & investments -------------------------------------------------
    ("wang_tunai", r"wang tunai dalam bank", "cash_in_bank"),
    ("wang_tunai", r"wang tunai dalam perjalanan", "cash_in_transit"),
    ("wang_tunai", r"wang tunai dalam tangan", "cash_in_hand"),
    ("wang_tunai", r"^wang tunai pada 31 disember", "cash_total"),
    ("wang_tunai", r"pelaburan pada 31 disember", "investment_total"),
    ("pelaburan", r"pelaburan kumpulan wang amanah", "investment_trust_funds"),
    ("pelaburan", r"^pelaburan am", "investment_general"),
    ("pelaburan", r"^saham", "investment_shares"),
    ("pelaburan", r"deposit dalam negeri", "investment_domestic_deposits"),
    ("pelaburan", r"^pelaburan pada 31 disember|^baki pada 31 disember",
     "investment_total"),

    # --- consolidated loan account -----------------------------------------
    ("akaun_pinjaman_disatukan", r"baki pada 1 januari", "loan_opening_balance"),
    ("akaun_pinjaman_disatukan", r"^terimaan", "loan_receipts"),
    ("akaun_pinjaman_disatukan", r"^bayaran", "loan_payments"),
    ("akaun_pinjaman_disatukan", r"baki pada 31 disember", "loan_closing_balance"),

    # --- consolidated trust account ----------------------------------------
    ("akaun_amanah_disatukan", r"^pelbagai kumpulan wang amanah", "misc_govt_trust_funds"),
    ("akaun_amanah_disatukan", r"kumpulan wang pembangunan hutan", "forest_development_fund"),
    ("akaun_amanah_disatukan", r"^kumpulan wang pembangunan$", "development_fund"),
    ("akaun_amanah_disatukan", r"kumpulan wang pinjaman perumahan", "housing_loan_fund"),
    ("akaun_amanah_disatukan", r"^kumpulan wang amanah kerajaan$", "govt_trust_funds"),
    ("akaun_amanah_disatukan", r"kumpulan wang amanah awam", "public_trust_funds"),
    ("akaun_amanah_disatukan", r"^(akaun )?(wang )?deposit$|^akaun (wang )?deposit", "deposit_account"),
    ("akaun_amanah_disatukan", r"^(jumlah|baki pada 31 disember)", "trust_account_balance"),
    # NB: the FOREST fund spec is tested first - `kumpulan_wang_pembangunan`
    # is a prefix of `kumpulan_wang_pembangunan_hutan`.
    ("kumpulan_wang_pembangunan_hutan", r"baki pada 1 januari", "forestfund_opening_balance"),
    ("kumpulan_wang_pembangunan_hutan", r"^(caruman|terimaan|sumber|pindahan)", "forestfund_receipts"),
    ("kumpulan_wang_pembangunan_hutan", r"^(perbelanjaan|bayaran)", "forestfund_payments"),
    ("kumpulan_wang_pembangunan_hutan", r"baki pada 31 disember", "forestfund_closing_balance"),
    ("kumpulan_wang_pembangunan$", r"baki pada 1 januari", "devfund_opening_balance"),
    ("kumpulan_wang_pembangunan$", r"^(caruman|terimaan|sumber)", "devfund_receipts"),
    ("kumpulan_wang_pembangunan$", r"^(perbelanjaan|bayaran)", "devfund_payments"),
    ("kumpulan_wang_pembangunan$", r"baki pada 31 disember", "devfund_closing_balance"),

    # --- expenditure --------------------------------------------------------
    ("perbelanjaan_mengurus", r"^(maksud )?tanggungan", "opex_charged"),
    ("perbelanjaan_mengurus", r"^(maksud )?bekalan", "opex_supply"),
    ("perbelanjaan_mengurus", r"^jumlah", "opex_total_by_maksud"),
    ("peruntukan_mengurus", r"^emolumen", "opex_estimate_emoluments"),
    ("peruntukan_mengurus", r"perkhidmatan dan bekalan", "opex_estimate_services_supplies"),
    ("peruntukan_mengurus", r"^aset", "opex_estimate_assets"),
    ("peruntukan_mengurus", r"pemberian dan kenaan bayaran tetap", "opex_estimate_grants_fixed"),
    ("peruntukan_mengurus", r"perbelanjaan lain", "opex_estimate_other"),
    ("peruntukan_mengurus", r"^jumlah", "opex_estimate_total"),
    ("perbelanjaan_pembangunan", r"^jumlah", "devex_total_by_department"),

    # --- memorandum accounts -------------------------------------------------
    ("hutang_awam", r"^jumlah", "debt_total"),
    ("hutang_awam", r"baki pada 1 januari", "debt_opening_balance"),
    ("hutang_awam", r"baki pada 31 disember", "debt_closing_balance"),
    ("pinjaman_boleh_dituntut", r"^jumlah", "loans_receivable_total"),
    ("pinjaman_boleh_dituntut", r"badan berkanun negeri", "loans_receivable_bbn"),
    ("pinjaman_boleh_dituntut", r"pihak berkuasa tempatan", "loans_receivable_pbt"),
    ("akaun_belum_terima", r"^jumlah", "receivables_total"),
    ("aset_liabiliti", r"^jumlah aset", "financial_assets_total"),
    ("aset_liabiliti", r"^jumlah liabiliti", "liabilities_total"),

    # --- revenue -------------------------------------------------------------
    # the top-contributor table's JUMLAH is the sum of the top 5 lines only,
    # NOT total revenue - it must never share revenue_total's code
    ("hasil_penyumbang_utama", r"^jumlah\b", "revenue_top_contributors_total"),
    ("hasil_", r"^hasil cukai$", "revenue_tax"),
    ("hasil_", r"^hasil bukan cukai$", "revenue_nontax"),
    ("hasil_", r"^teri?maan bukan hasil$", "revenue_nonrevenue_receipts"),
    # `^jumlah$` only, EXCEPT in the estimate-vs-actual table where the
    # `Sumber: Penyata Kewangan ...` caption is sometimes typeset inside the
    # JUMLAH row and survives as `JUMLAH Penyata Kewangan` (Selangor FY2018).
    ("hasil_anggaran", r"^jumlah\b", "revenue_total"),
    ("hasil_", r"^jumlah$", "revenue_total"),

    # --- revenue ITEMS -------------------------------------------------------
    # The named revenue heads that recur across states.  Conforming them is
    # what makes the top-contributor block joinable on a code rather than on a
    # printed name (CLAUDE.md golden rule 4).  Anything else keeps its
    # deterministic `<spec_id>.<slug>` fallback.
    ("hasil_", r"^premium (bagi )?(geran|tanah)|^premium$|premium geran tanah",
     "revenue_item_land_premium"),
    ("hasil_", r"^cukai tanah", "revenue_item_land_tax"),
    ("hasil_", r"^permit tanah( dan galian)?", "revenue_item_land_mineral_permit"),
    ("hasil_", r"^pemberian .{0,10}(mengikut )?(bilangan |ramai )?penduduk|"
     r"pemberian mengikut ramai penduduk|pemberian kepala",
     "revenue_item_federal_capitation_grant"),
    ("hasil_", r"kos pengurusan jabatan negeri", "revenue_item_federal_dept_grant"),
    ("hasil_", r"^hasil hutan|^royalti (kayu|balak|hutan)", "revenue_item_forest_produce"),
    ("hasil_", r"royalti petroleum|^wang ihsan|petroleum", "revenue_item_petroleum_royalty"),
    ("hasil_", r"cukai jualan negeri|^cukai jualan", "revenue_item_state_sales_tax"),
]

_LC = [(re.compile(s), re.compile(l, re.I), c) for s, l, c in LINE_CODES]


def normalise_label(label: str) -> str:
    s = unicodedata.normalize("NFKD", label)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"^[\u2022\u25cf\u25aa\u25a0\u00b7\ue000-\uf8ff]+\s*", "", s)
    s = re.sub(r"^\((\+|-)\)\s*", "", s)
    s = re.sub(r"^(dibiayai oleh|dibiayai olehp|perbelanjaan)\s*:\s*", "", s, flags=re.I)
    # `Kurangan Dibiayai Oleh: Pinjaman Dalam Negeri` is the FINANCING line, not
    # the deficit: the `... Dibiayai Oleh:` caption is typeset on the same
    # physical line as the first financing item.  The caption is stripped ONLY
    # when something follows the colon - a bare `Defisit Kurangan Dibiayai
    # Oleh` (Melaka) carries the deficit figure itself and must keep its label.
    # `Kurangan Dibiayai Oleh: Pinjaman Dalam Negeri` (Kedah), `LEBIHAN BAGI
    # MEMBIAYAI: Pinjaman` (Perak), `DEFISIT DIBIAYAI OLEH Pinjaman` (Pahang,
    # no colon) are all the FINANCING line, not the surplus: the caption is
    # typeset on the same physical line as the first financing item.  The
    # colon is optional but CONTENT after the caption is required - a bare
    # `Defisit Kurangan Dibiayai Oleh` (Melaka) carries the deficit figure
    # itself and must keep its label.
    s = re.sub(r"^(lebihan|kurangan|defisit|surplus)[^:]{0,40}?"
               r"(dibiayai oleh|diperoleh daripada|bagi membiayai)\s*:?\s+(?=\S)",
               "", s, flags=re.I)
    # A narrative connective typeset into the row label by `pdftotext -layout`
    # (`Akaun Amanah Disatukan terdiri daripada:`).  Stripped for CODE
    # assignment only - `line_label_bm` keeps the printed text verbatim and no
    # amount is touched.
    s = re.sub(r"[\s,]+(terdiri daripada|adalah seperti berikut|"
               r"adalah seperti di bawah|seperti di bawah|seperti berikut|iaitu)"
               r"\s*:?\s*$", "", s, flags=re.I)
    s = re.sub(r"\*+$", "", s)
    s = re.sub(r"\d$", "", s)                 # footnote marker glued to label
    s = re.sub(r"\s+", " ", s).strip(" .:")
    return s.lower()


def slug(label: str) -> str:
    s = normalise_label(label)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:60]


# Section headings printed INSIDE the Penyata Prestasi Kewangan.  A row whose
# only label is `JUMLAH` is the total of the section it sits under.
_SECTION_RE = [
    (re.compile(r"^hasil$", re.I), "hasil"),
    (re.compile(r"^perbelanjaan$", re.I), "perbelanjaan"),
    (re.compile(r"^(jumlah )?pembiayaan$", re.I), "pembiayaan"),
    (re.compile(r"^dibiayai oleh$", re.I), "pembiayaan"),
]


def section_group(label: str) -> str:
    """The section a bare `JUMLAH` belongs to, if this label IS a heading."""
    n = normalise_label(label)
    for rx, g in _SECTION_RE:
        if rx.match(n):
            return g
    return ""


def line_code(spec_id: str, label: str, section: str = "") -> tuple[str, bool]:
    """-> (line_code, is_conformed).

    `section` is the last printed section heading inside the table; it only
    disambiguates a bare `JUMLAH`, which several states print instead of
    `JUMLAH PERBELANJAAN` / `JUMLAH HASIL` / `JUMLAH PEMBIAYAAN`.
    """
    n = normalise_label(label)
    if section and n == "jumlah":
        n = f"jumlah @{section}"
    for srx, lrx, code in _LC:
        if srx.match(spec_id) and lrx.search(n):
            return code, True
    return f"{spec_id}.{slug(label)}", False


# ---------------------------------------------------------------------------
# revenue classification (federal transfers must be identifiable)
# ---------------------------------------------------------------------------

REVENUE_CLASSES: list[tuple[str, str]] = [
    # Federal -> state transfers.  These are the constitutionally/statutorily
    # named federal grants (Art. 109-112 Perlembagaan Persekutuan) plus named
    # federal payments; the pattern is deliberately narrow so that state land
    # revenue such as `Premium Bagi Geran` can never fall into it.
    (r"^pemberian\b", "federal_transfer"),
    (r"^geran (daripada|kerajaan persekutuan|persekutuan)\b", "federal_transfer"),
    (r"(terimaan|caruman|bantuan|sumbangan|pemberian).{0,40}kerajaan persekutuan",
     "federal_transfer"),
    (r"kos pengurusan jabatan negeri", "federal_transfer"),
    # Federal compensation for forest conservation: a federal payment in
    # substance, but the volumes never name the payer - kept in its own class
    # so a consumer decides (see README).
    (r"ganti ?rugi.{0,20}pampasan|pampasan \(hutan\)|pampasan hutan",
     "federal_compensation_forest"),
    # printed category totals
    (r"^hasil cukai$", "tax_total"),
    (r"^hasil bukan cukai$", "nontax_total"),
    (r"^terimaan bukan hasil$", "nonrevenue_receipts_total"),
    (r"^jumlah( hasil)?$", "revenue_total"),
    # state's own sources
    (r"cukai tanah|premium|permit tanah|hasil tanah|cukai petak|tanah dan galian|"
     r"cukai parit|cukai hiburan|royalti|hasil hutan|hasil galian|hasil bijih",
     "land_forest_mineral"),
    (r"faedah|dividen|pelaburan|sewa|bunga", "investment_income"),
    (r"lesen|permit|bayaran perkhidmatan|denda|kompaun", "licences_fees_fines"),
]

_RC = [(re.compile(r, re.I), c) for r, c in REVENUE_CLASSES]

# The revenue tables print their own group headings; when one is in force it
# beats keyword matching for the printed-category classes.
_GROUP_RE = [
    (re.compile(r"^hasil cukai$", re.I), "Hasil Cukai"),
    (re.compile(r"^hasil bukan cukai$", re.I), "Hasil Bukan Cukai"),
    (re.compile(r"^terimaan bukan hasil$", re.I), "Terimaan Bukan Hasil"),
]
_GROUP_CLASS = {"Hasil Cukai": "tax_own_source",
                "Hasil Bukan Cukai": "nontax_own_source",
                "Terimaan Bukan Hasil": "nonrevenue_receipt"}


def revenue_group(label: str) -> str:
    """The printed group heading a row belongs to, if the label IS one."""
    n = normalise_label(label)
    for rx, g in _GROUP_RE:
        if rx.match(n):
            return g
    return ""


# Classes that describe WHAT the row is, and therefore beat the table's printed
# group heading (a petroleum royalty is a petroleum royalty whether the state
# prints it under Hasil Cukai or Hasil Bukan Cukai).
_DECISIVE = {"federal_transfer", "federal_compensation_forest",
             "tax_total", "nontax_total", "nonrevenue_receipts_total",
             "revenue_total", "petroleum_royalty", "forest_produce",
             "state_sales_tax", "mineral_royalty"}


def compile_rules(rules) -> list[tuple[re.Pattern, str]]:
    """Compile extra (regex, class) rules supplied by `state_config`."""
    return [(re.compile(r, re.I), c) for r, c in rules]


def revenue_class(label: str, printed_group: str = "", line_code: str = "",
                  extra: list[tuple[re.Pattern, str]] | None = None) -> str:
    """Federal transfers, the printed category totals and the distinctive
    state revenue heads (petroleum / timber / state sales tax) are decided by
    the label; everything else defers to the printed group heading when the
    table prints one, and only falls back to keywords when it does not.

    `extra` are the state's own rules from `state_config`; they are tested
    FIRST so a state-specific head can never be swallowed by a national one.
    """
    if line_code == "revenue_top_contributors_total":
        return "top_contributors_subtotal"
    n = normalise_label(label)
    rules = list(extra or []) + _RC
    for rx, c in rules:
        if rx.search(n):
            if c in _DECISIVE:
                return c
            break
    if printed_group and not revenue_group(label):
        return _GROUP_CLASS[printed_group]
    for rx, c in rules:
        if rx.search(n):
            return c
    return "other"


# ---------------------------------------------------------------------------
# row_type  (CLAUDE.md golden rule 5: sum only leaf rows)
# ---------------------------------------------------------------------------
# A printed JADUAL mixes components with their own totals at the same grain, so
# `SUM(amount)` over a spec_id double-counts unless the totals are excluded.
#
#   component  a leaf line - the ONLY row_type that may be summed
#   subtotal   a total of some rows in the table AND a component of another
#   total      the table's own printed total
#   balance    an opening/closing balance or other stock (a level: never a
#              component of anything in the same table, never summable)
#   derived    a computed line (surplus/deficit, change, financing) - the
#              arithmetic result of other rows

TOTAL_CODES = {
    "revenue_total", "expenditure_total", "financing_total",
    "revenue_top_contributors_total", "opex_total", "opex_total_by_maksud",
    "opex_estimate_total", "devex_total_by_department", "debt_total",
    "loans_receivable_total", "receivables_total", "financial_assets_total",
    "liabilities_total", "cash_total", "investment_total", "kwd_balance",
}
SUBTOTAL_CODES = {
    "trust_account_balance", "govt_trust_funds", "cra_balance",
    "loan_account_balance",
}
BALANCE_CODES = {
    "cra_opening_balance", "cra_closing_balance", "loan_opening_balance",
    "loan_closing_balance", "devfund_opening_balance", "devfund_closing_balance",
    "forestfund_opening_balance", "forestfund_closing_balance",
    "debt_opening_balance", "debt_closing_balance",
}
DERIVED_CODES = {
    "surplus_deficit", "surplus_before_devex", "surplus_deficit_intermediate",
    "cra_surplus_deficit", "cra_revenue_surplus",
    "financing_external_loans",
    "financing_domestic_loans", "financing_loan_repayment",
    "financing_cash_investment_trust",
}

_TOTAL_LABEL = re.compile(r"^(jumlah|total|jumlah besar)\b", re.I)


def row_type(line_code: str, label: str) -> str:
    n = normalise_label(label)
    if line_code in BALANCE_CODES or n.startswith("baki pada"):
        return "balance"
    if line_code in DERIVED_CODES:
        return "derived"
    if line_code in TOTAL_CODES or _TOTAL_LABEL.match(n):
        return "total"
    if line_code in SUBTOTAL_CODES:
        return "subtotal"
    return "component"


# ---------------------------------------------------------------------------
# sign conformance
# ---------------------------------------------------------------------------
# Codes that are LEVELS (never negative in substance).  The newer volumes print
# some of them parenthesised because they sit under a `(-)` flow heading, so
# `amount_rm` keeps the printed sign and `amount_rm_conformed` carries the
# comparable level.  Genuinely signed codes (surpluses, financing, changes) are
# left exactly as printed in both columns.

LEVEL_CODES = {
    "revenue_total", "revenue_tax", "revenue_nontax", "revenue_nonrevenue_receipts",
    "revenue_top_contributors_total",
    "opex_total", "opex_before_transfer", "opex_after_transfer",
    "opex_charged", "opex_supply",
    "opex_total_by_maksud", "opex_estimate_total", "opex_estimate_emoluments",
    "opex_estimate_services_supplies", "opex_estimate_assets",
    "opex_estimate_grants_fixed", "opex_estimate_other",
    "devex_total", "devex_total_by_department", "expenditure_total",
    "cash_total", "cash_in_bank", "cash_in_transit", "cash_in_hand",
    "investment_total", "investment_general", "investment_shares",
    "investment_trust_funds", "investment_domestic_deposits",
    "debt_total", "debt_subtotal", "debt_movement_total", "debt_opening_balance", "debt_closing_balance",
    "loans_receivable_total", "loans_receivable_bbn", "loans_receivable_pbt",
    "receivables_total", "financial_assets_total", "liabilities_total",
    "loan_receipts", "loan_payments", "devfund_receipts", "devfund_payments",
    "forestfund_receipts", "forestfund_payments",
}

# The statement that DEFINES each conformed code - used to pick the canonical
# row when several tables in one volume print the same figure.
#
# The value is an ORDERED tuple: earlier = preferred.  Order, not page order,
# must decide, because the auditor moved the Penyata Prestasi Kewangan to the
# front of the analysis section in era 3.  With a page-order tie-break a state
# whose two statements disagree (Sabah: the fund-flow `HASIL*` includes
# Kumpulan Wang Pembangunan receipts, the Akaun Hasil Disatukan `Hasil` does
# not) gets a SPLICED series - CRA basis to FY2017, PPK basis from FY2018, and
# a fabricated jump at the join.  `N6_spec_stable` asserts this can't recur.
PRIMARY_SPEC_OF: dict[str, tuple[str, ...]] = {
    "revenue_total": ("prestasi_kewangan", "akaun_hasil_disatukan", "hasil_kategori"),
    "revenue_tax": ("hasil_kategori", "prestasi_kewangan"),
    "revenue_nontax": ("hasil_kategori", "prestasi_kewangan"),
    "revenue_nonrevenue_receipts": ("hasil_kategori", "prestasi_kewangan"),
    "opex_before_transfer": ("prestasi_kewangan",),
    "opex_after_transfer": ("prestasi_kewangan",),
    "devex_total": ("prestasi_kewangan",),
    "expenditure_water_supply": ("prestasi_kewangan",),
    "expenditure_total": ("prestasi_kewangan",),
    "surplus_deficit": ("prestasi_kewangan",),
    "financing_external_loans": ("prestasi_kewangan",),
    "financing_loan_repayment": ("prestasi_kewangan",),
    "financing_cash_investment_trust": ("prestasi_kewangan",),
    "financing_total": ("prestasi_kewangan",),
    "opex_total": ("akaun_hasil_disatukan",),
    "cra_opening_balance": ("akaun_hasil_disatukan",),
    "cra_closing_balance": ("akaun_hasil_disatukan",),
    "cra_surplus_deficit": ("akaun_hasil_disatukan",),
    "kwd_balance": ("kumpulan_wang_disatukan",),
    "cra_balance": ("kumpulan_wang_disatukan",),
    "loan_account_balance": ("kumpulan_wang_disatukan",),
    "trust_account_balance": ("kumpulan_wang_disatukan",),
    "govt_trust_funds": ("kumpulan_wang_disatukan",),
    "public_trust_funds": ("kumpulan_wang_disatukan",),
    "deposit_account": ("kumpulan_wang_disatukan",),
    "development_fund": ("kumpulan_wang_disatukan",),
    "forest_development_fund": ("kumpulan_wang_disatukan",),
    "housing_loan_fund": ("kumpulan_wang_disatukan",),
    "misc_govt_trust_funds": ("kumpulan_wang_disatukan",),
    "cash_total": ("wang_tunai",),
    "investment_total": ("pelaburan", "wang_tunai"),
    "debt_total": ("hutang_awam",),
    "loans_receivable_total": ("pinjaman_boleh_dituntut",),
    "receivables_total": ("akaun_belum_terima",),
    "devfund_opening_balance": ("kumpulan_wang_pembangunan",),
    "devfund_closing_balance": ("kumpulan_wang_pembangunan",),
    "devfund_receipts": ("kumpulan_wang_pembangunan",),
    "devfund_payments": ("kumpulan_wang_pembangunan",),
    "forestfund_opening_balance": ("kumpulan_wang_pembangunan_hutan",),
    "forestfund_closing_balance": ("kumpulan_wang_pembangunan_hutan",),
    "forestfund_receipts": ("kumpulan_wang_pembangunan_hutan",),
    "forestfund_payments": ("kumpulan_wang_pembangunan_hutan",),
}
