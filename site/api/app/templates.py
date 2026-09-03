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


TEMPLATES = {
    "national_fiscal_headline": national_fiscal_headline,
    "list_ministries": list_ministries,
    "ministry_fiscal": ministry_fiscal,
    "budget_vs_actual": budget_vs_actual,
    "obligations_summary": obligations_summary,
    "revenue_headline": revenue_headline,
}
