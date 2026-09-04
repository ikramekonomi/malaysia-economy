"""The constrained query-template library Tanya Fiskal dispatches to.

Every function here is a fixed, parameterized query against curated/warehouse.duckdb.
The chatbot (chatbot.py) never generates SQL -- it only picks one of these functions
and extracts (year_from, year_to, ministry, ...) parameters from the user's question.
This is the guardrail against the basis-blending / leaf-row / canonical-ministry traps
documented in docs/ANALYST_GUIDE.md.

Every function returns {"rows": [...], "citations": [...]} -- citations always name the
underlying table and basis so the frontend/chatbot can show "lihat sumber."
"""
from .db import get_connection

MIN_YEAR, MAX_YEAR = 2009, 2024


def _clamp_years(year_from, year_to):
    yf = max(MIN_YEAR, int(year_from) if year_from else MIN_YEAR)
    yt = min(MAX_YEAR, int(year_to) if year_to else MAX_YEAR)
    if yf > yt:
        yf, yt = yt, yf
    return yf, yt


def national_fiscal_headline(year_from=None, year_to=None):
    """Opex/devex, gross and net, per year. The default headline series."""
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    rows = con.execute(
        "SELECT year, opex_gross_rm, opex_net_rm, devex_gross_rm, devex_net_rm, note "
        "FROM curated.fact_fiscal_headline WHERE year BETWEEN ? AND ? ORDER BY year",
        [yf, yt],
    ).fetchall()
    cols = ["year", "opex_gross_rm", "opex_net_rm", "devex_gross_rm", "devex_net_rm", "note"]
    return {
        "rows": [dict(zip(cols, r)) for r in rows],
        "citations": [{
            "table": "curated.fact_fiscal_headline",
            "basis": "opex_net follows MOF Tinjauan Fiskal (gross minus transfer to Development "
                     "Fund); devex_net follows MOF Tinjauan Fiskal (gross minus loan recovery) "
                     "where available (FY2020+); gross figures are PKKP's own audited actuals",
        }],
    }


def list_ministries():
    """Canonical ministries for the dashboard filter and chatbot lookup."""
    con = get_connection()
    rows = con.execute(
        "SELECT canonical_code, canonical_name_bm, jenis "
        "FROM curated.dim_maksud_canonical WHERE is_merged = false "
        "ORDER BY canonical_name_bm"
    ).fetchall()
    return {
        "rows": [{"code": r[0], "name_bm": r[1], "jenis": r[2]} for r in rows],
        "citations": [{"table": "curated.dim_maksud_canonical"}],
    }


def ministry_fiscal(canonical_code, year_from=None, year_to=None):
    """Gross opex/devex for one canonical ministry across a year range.

    canonical_code should be resolved via list_ministries() / dim_maksud_canonical --
    never a raw maksud_code -- so renumbered ministries (e.g. Education's pre-2015 B.41)
    read as one continuous series.
    """
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    name_row = con.execute(
        "SELECT canonical_name_bm FROM curated.dim_maksud_canonical "
        "WHERE canonical_code = ? AND is_merged = false LIMIT 1",
        [canonical_code],
    ).fetchone()
    if name_row is None:
        return {"rows": [], "citations": [], "error": f"unknown canonical_code {canonical_code!r}"}
    rows = con.execute(
        "SELECT year, jenis, amount_rm, note FROM curated.fact_ministry_fiscal "
        "WHERE canonical_code = ? AND year BETWEEN ? AND ? ORDER BY year, jenis",
        [canonical_code, yf, yt],
    ).fetchall()
    return {
        "ministry_name_bm": name_row[0],
        "rows": [{"year": r[0], "jenis": r[1], "amount_rm": r[2], "note": r[3]} for r in rows],
        "citations": [{
            "table": "curated.fact_ministry_fiscal",
            "basis": "gross ministry spend (audited actual) -- no net-of-transfer concept exists "
                     "at ministry level, see curated/pipeline/build_ministry_fiscal.py",
        }],
    }


def budget_vs_actual(year_from=None, year_to=None, side="total"):
    """Tabled budget vs audited actual, whole-of-government (side: oe|de|total)."""
    if side not in ("oe", "de", "total"):
        side = "total"
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    rows = con.execute(
        "SELECT year, budget_rm, actual_rm, variance_rm, utilisation_pct, basis "
        "FROM curated.fact_planning_efficiency "
        "WHERE side = ? AND year BETWEEN ? AND ? ORDER BY year",
        [side, yf, yt],
    ).fetchall()
    cols = ["year", "budget_rm", "actual_rm", "variance_rm", "utilisation_pct", "basis"]
    return {
        "rows": [dict(zip(cols, r)) for r in rows],
        "citations": [{"table": "curated.fact_planning_efficiency", "side": side}],
    }


def obligations_summary(year_from=None, year_to=None, obligation_class=None):
    """Debt, PFI, guarantees, commitments, arrears -- unified across 3 publishers."""
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    if obligation_class:
        rows = con.execute(
            "SELECT year, obligation_class, subclass, sum(amount_rm) AS amount_rm, source "
            "FROM curated.fact_obligations "
            "WHERE year BETWEEN ? AND ? AND obligation_class = ? "
            "GROUP BY year, obligation_class, subclass, source ORDER BY year",
            [yf, yt, obligation_class],
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT year, obligation_class, sum(amount_rm) AS amount_rm "
            "FROM curated.fact_obligations WHERE year BETWEEN ? AND ? "
            "GROUP BY year, obligation_class ORDER BY year, obligation_class",
            [yf, yt],
        ).fetchall()
    cols = (["year", "obligation_class", "subclass", "amount_rm", "source"] if obligation_class
            else ["year", "obligation_class", "amount_rm"])
    return {
        "rows": [dict(zip(cols, r)) for r in rows],
        "citations": [{"table": "curated.fact_obligations", "doc": "curated/OBLIGATIONS.md"}],
    }


def revenue_headline(year_from=None, year_to=None):
    """Federal revenue grand total per year (PKKP audited, Nota 5(a))."""
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    rows = con.execute(
        "SELECT year, sebenar_rm FROM pkkp.fact_revenue "
        "WHERE level = 0 AND year BETWEEN ? AND ? ORDER BY year",
        [yf, yt],
    ).fetchall()
    return {
        "rows": [{"year": r[0], "revenue_rm": r[1]} for r in rows],
        "citations": [{"table": "pkkp.fact_revenue", "basis": "audited actual (Nota 5(a) Hasil Mengikut Penjenisan)"}],
    }


def revenue_by_category(year_from=None, year_to=None):
    """Federal revenue's 4-category split (Hasil Cukai/Bukan Cukai/Wilayah Persekutuan/
    Terimaan Bukan Hasil), PKKP audited actual. Used by Papan Pemuka's "where revenue
    came from" section."""
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    rows = con.execute(
        "SELECT year, category_l1_bm, sebenar_rm FROM pkkp.fact_revenue "
        "WHERE level = 1 AND year BETWEEN ? AND ? ORDER BY year, category_l1_bm",
        [yf, yt],
    ).fetchall()
    return {
        "rows": [{"year": r[0], "category_bm": r[1], "amount_rm": r[2]} for r in rows],
        "citations": [{"table": "pkkp.fact_revenue", "basis": "audited actual (Nota 5(a) Hasil Mengikut Penjenisan)"}],
    }


# Years the ingested Tinjauan Fiskal appendix (Jadual 3.1/3.2/3.3) actually covers --
# see sources/mof-fiscal-outlook/README.md. A later edition widens this without any
# code change here (it's read from the data, not hardcoded as a second source of truth).
def _mof_stats_year_range(con, table):
    row = con.execute(f"SELECT min(year), max(year) FROM curated.{table}").fetchone()
    return row[0], row[1]


def opex_by_type(year):
    """OPEX by economic component (Jadual 3.1: Emolumen, Bayaran persaraan, Bayaran
    khidmat hutang, ... ) for one year. Finer than PKKP's own 5-bucket object
    classification and DOSM's coarser proxy -- see sources/mof-fiscal-outlook/README.md.
    Returns not_available=True with the coverage range in the note if the year isn't
    covered by any ingested Tinjauan Fiskal edition yet."""
    con = get_connection()
    lo, hi = _mof_stats_year_range(con, "fact_opex_by_component")
    year = int(year)
    if year < lo or year > hi:
        return {"rows": [], "not_available": True,
                "note": f"OPEX-by-component not yet ingested for {year}; "
                        f"currently covers {lo}-{hi} (Tinjauan Fiskal 2021 edition's own appendix)",
                "citations": [{"table": "curated.fact_opex_by_component"}]}
    rows = con.execute(
        "SELECT line, line_bm, line_en, level, parent_line, amount_rm, pct_share, basis, note "
        "FROM curated.fact_opex_by_component WHERE year = ? ORDER BY level, line",
        [year],
    ).fetchall()
    cols = ["line", "line_bm", "line_en", "level", "parent_line", "amount_rm", "pct_share", "basis", "note"]
    return {
        "rows": [dict(zip(cols, r)) for r in rows], "not_available": False,
        "citations": [{"table": "curated.fact_opex_by_component",
                        "basis": "MOF Tinjauan Fiskal, Jadual 3.1 (own printed classification)"}],
    }


def devex_by_sector(year):
    """DEVEX by sector (Jadual 3.3: Ekonomi/Sosial/Keselamatan/Pentadbiran Am + sub-
    functions) for one year. PKKP carries no sector classification for devex at any
    year, so this table is the only source -- see sources/mof-fiscal-outlook/README.md."""
    con = get_connection()
    lo, hi = _mof_stats_year_range(con, "fact_devex_by_sector")
    year = int(year)
    if year < lo or year > hi:
        return {"rows": [], "not_available": True,
                "note": f"DEVEX-by-sector not yet ingested for {year}; "
                        f"currently covers {lo}-{hi} (Tinjauan Fiskal 2021 edition's own appendix)",
                "citations": [{"table": "curated.fact_devex_by_sector"}]}
    rows = con.execute(
        "SELECT line, line_bm, line_en, level, parent_line, amount_rm, pct_share, basis, note "
        "FROM curated.fact_devex_by_sector WHERE year = ? ORDER BY level, line",
        [year],
    ).fetchall()
    cols = ["line", "line_bm", "line_en", "level", "parent_line", "amount_rm", "pct_share", "basis", "note"]
    return {
        "rows": [dict(zip(cols, r)) for r in rows], "not_available": False,
        "citations": [{"table": "curated.fact_devex_by_sector",
                        "basis": "MOF Tinjauan Fiskal, Jadual 3.3 (own printed classification)"}],
    }


def financing_breakdown(year):
    """How the deficit was financed (PKKP's own 'Dibiayai oleh:' panel): Baki Akaun,
    Pinjaman Bersih Dalam/Luar Negeri. Values can be negative (asset accumulation /
    net repayment)."""
    con = get_connection()
    year = int(year)
    rows = con.execute(
        "SELECT line_item_bm, amount_rm_juta * 1e6 FROM pkkp.fact_timeseries_2010_2024 "
        "WHERE section_bm = 'Dibiayai oleh:' AND year = ? AND line_item_bm <> 'Jumlah' "
        "ORDER BY line_item_bm",
        [year],
    ).fetchall()
    if not rows:
        return {"rows": [], "not_available": True,
                "note": f"financing breakdown not available for {year} (fact_timeseries_2010_2024 covers 2010-2024)",
                "citations": [{"table": "pkkp.fact_timeseries_2010_2024"}]}
    return {
        "rows": [{"component_bm": r[0], "amount_rm": r[1]} for r in rows],
        "not_available": False,
        "citations": [{"table": "pkkp.fact_timeseries_2010_2024", "section": "Dibiayai oleh:"}],
    }


# Whitelist for component_series -- each entry names its own table/column so a new
# component means adding a row here, never accepting an arbitrary column from a caller.
_COMPONENT_SERIES = {
    "revenue_total": ("pkkp.fact_revenue", "level = 0", "sebenar_rm", None),
    "opex_net": ("curated.fact_fiscal_headline", None, "opex_net_rm", None),
    "opex_gross": ("curated.fact_fiscal_headline", None, "opex_gross_rm", None),
    "devex_net": ("curated.fact_fiscal_headline", None, "devex_net_rm", None),
    "devex_gross": ("curated.fact_fiscal_headline", None, "devex_gross_rm", None),
    "income_tax": ("pkkp.fact_revenue", "level = 3 AND item_bm = 'Cukai Pendapatan'", "sebenar_rm", None),
}
for _key in ["emoluments", "retirement_charges", "debt_service", "supplies_services",
             "subsidies_social_assistance", "asset_acquisition", "refunds_writeoffs",
             "grants_statutory_bodies"]:
    _COMPONENT_SERIES[f"opex_component_{_key}"] = (
        "curated.fact_opex_by_component", f"line = '{_key}'", "amount_rm", None)
for _key in ["economic", "social", "security", "general_admin"]:
    _COMPONENT_SERIES[f"devex_sector_{_key}"] = (
        "curated.fact_devex_by_sector", f"line = '{_key}'", "amount_rm", None)


def component_series(component_key, year_from=None, year_to=None):
    """One named component's value over time, for the "how did X evolve" page. Only
    keys in _COMPONENT_SERIES are queryable -- never a caller-supplied column/table."""
    if component_key not in _COMPONENT_SERIES:
        return {"rows": [], "citations": [],
                "error": f"unknown component_key {component_key!r}; see list_components()"}
    table, extra_where, value_col, _ = _COMPONENT_SERIES[component_key]
    yf, yt = _clamp_years(year_from, year_to)
    con = get_connection()
    where = "year BETWEEN ? AND ?"
    if extra_where:
        where += f" AND {extra_where}"
    rows = con.execute(
        f"SELECT year, {value_col} FROM {table} WHERE {where} ORDER BY year", [yf, yt]
    ).fetchall()
    return {
        "rows": [{"year": r[0], "amount_rm": r[1]} for r in rows],
        "citations": [{"table": table, "component_key": component_key}],
    }


def list_components():
    """The fixed whitelist component_series() accepts -- for the frontend's picker."""
    return {"rows": [{"component_key": k} for k in _COMPONENT_SERIES], "citations": []}


def ministry_spending_breakdown(canonical_code, year, jenis="Bekalan"):
    """Where one ministry's opex ('Bekalan') or devex ('Pembangunan') went in one year:
    top-10 programmes/activities plus a "Lain-lain" remainder, and (opex only) the
    5-bucket object-class split. Resolves canonical_code -> that year's raw maksud_code
    via curated.dim_maksud_canonical -- never a raw code passed straight through."""
    if jenis not in ("Bekalan", "Pembangunan"):
        return {"rows": [], "citations": [], "error": "jenis must be 'Bekalan' or 'Pembangunan'"}
    year = int(year)
    con = get_connection()
    raw = con.execute(
        "SELECT raw_code, canonical_name_bm FROM curated.dim_maksud_canonical "
        "WHERE canonical_code = ? AND jenis = ? AND ? BETWEEN first_year AND last_year",
        [canonical_code, jenis, year],
    ).fetchone()
    if raw is None:
        return {"rows": [], "citations": [],
                "error": f"no {jenis} ministry {canonical_code!r} active in {year}"}
    raw_code, ministry_name = raw
    caveat = "FY2015 leaf-tier detail is OCR-provisional" if year == 2015 else None

    if jenis == "Bekalan":
        leaf = con.execute(
            "SELECT aktiviti_name_bm, sum(sebenar_rm) AS amt FROM pkkp.fact_opex_detail "
            "WHERE maksud_code = ? AND year = ? AND row_type = 'object_aktiviti' "
            "GROUP BY aktiviti_name_bm ORDER BY amt DESC",
            [raw_code, year],
        ).fetchall()
        objclass = con.execute(
            "SELECT objek_class_bm, sum(sebenar_rm) FROM pkkp.fact_opex_detail "
            "WHERE maksud_code = ? AND year = ? AND row_type = 'object_aktiviti' "
            "GROUP BY objek_class_bm ORDER BY 2 DESC",
            [raw_code, year],
        ).fetchall()
    else:
        leaf = con.execute(
            "SELECT name_bm, sum(sebenar_jumlah_rm) AS amt FROM pkkp.fact_devex_project "
            "WHERE maksud_code = ? AND year = ? AND row_type = 'project' "
            "GROUP BY name_bm ORDER BY amt DESC",
            [raw_code, year],
        ).fetchall()
        objclass = []

    top = leaf[:10]
    other_total = sum(r[1] for r in leaf[10:])
    ranked = [{"label": r[0], "amount_rm": r[1]} for r in top]
    if other_total:
        ranked.append({"label": "Lain-lain", "amount_rm": other_total})

    return {
        "ministry_name_bm": ministry_name,
        "raw_code": raw_code,
        "rows": ranked,
        "object_class_rows": [{"label": r[0], "amount_rm": r[1]} for r in objclass],
        "citations": [{
            "table": "pkkp.fact_opex_detail" if jenis == "Bekalan" else "pkkp.fact_devex_project",
            "basis": "audited actual", "note": caveat,
        }],
    }


TEMPLATES = {
    "national_fiscal_headline": national_fiscal_headline,
    "list_ministries": list_ministries,
    "ministry_fiscal": ministry_fiscal,
    "budget_vs_actual": budget_vs_actual,
    "obligations_summary": obligations_summary,
    "revenue_headline": revenue_headline,
    "revenue_by_category": revenue_by_category,
    "opex_by_type": opex_by_type,
    "devex_by_sector": devex_by_sector,
    "financing_breakdown": financing_breakdown,
    "component_series": component_series,
    "list_components": list_components,
    "ministry_spending_breakdown": ministry_spending_breakdown,
}
