import csv
import io

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import templates as tpl
from .chatbot import answer_question
from .ratelimit import allow

app = FastAPI(title="Fiskal Malaysia API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the deployed web origin before production launch
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ministries")
def ministries():
    return tpl.list_ministries()


@app.get("/api/fiscal/headline")
def fiscal_headline(year_from: int | None = Query(None), year_to: int | None = Query(None)):
    return tpl.national_fiscal_headline(year_from, year_to)


@app.get("/api/fiscal/ministry")
def fiscal_ministry(
    code: str = Query(...),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
):
    result = tpl.ministry_fiscal(code, year_from, year_to)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/fiscal/budget-vs-actual")
def fiscal_budget_vs_actual(
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    side: str = Query("total"),
):
    return tpl.budget_vs_actual(year_from, year_to, side)


@app.get("/api/fiscal/obligations")
def fiscal_obligations(
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
    obligation_class: str | None = Query(None),
):
    return tpl.obligations_summary(year_from, year_to, obligation_class)


@app.get("/api/fiscal/revenue")
def fiscal_revenue(year_from: int | None = Query(None), year_to: int | None = Query(None)):
    return tpl.revenue_headline(year_from, year_to)


@app.get("/api/fiscal/revenue-by-category")
def fiscal_revenue_by_category(year_from: int | None = Query(None), year_to: int | None = Query(None)):
    return tpl.revenue_by_category(year_from, year_to)


@app.get("/api/fiscal/opex-by-type")
def fiscal_opex_by_type(year: int = Query(...)):
    return tpl.opex_by_type(year)


@app.get("/api/fiscal/devex-by-sector")
def fiscal_devex_by_sector(year: int = Query(...)):
    return tpl.devex_by_sector(year)


@app.get("/api/fiscal/financing")
def fiscal_financing(year: int = Query(...)):
    return tpl.financing_breakdown(year)


@app.get("/api/fiscal/components")
def fiscal_components():
    return tpl.list_components()


@app.get("/api/fiscal/component-series")
def fiscal_component_series(
    component_key: str = Query(...),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
):
    result = tpl.component_series(component_key, year_from, year_to)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/fiscal/ministry-breakdown")
def fiscal_ministry_breakdown(
    code: str = Query(...),
    year: int = Query(...),
    jenis: str = Query("Bekalan"),
):
    result = tpl.ministry_spending_breakdown(code, year, jenis)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


def _csv_response(rows: list[dict], filename: str):
    if not rows:
        raise HTTPException(status_code=404, detail="no rows for the given filters")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/headline.csv")
def export_headline(year_from: int | None = Query(None), year_to: int | None = Query(None)):
    result = tpl.national_fiscal_headline(year_from, year_to)
    return _csv_response(result["rows"], "fiskal_malaysia_headline.csv")


@app.get("/api/export/ministry.csv")
def export_ministry(
    code: str = Query(...),
    year_from: int | None = Query(None),
    year_to: int | None = Query(None),
):
    result = tpl.ministry_fiscal(code, year_from, year_to)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return _csv_response(result["rows"], f"fiskal_malaysia_{code}.csv")


class ChatRequest(BaseModel):
    question: str


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    client_id = request.client.host if request.client else "unknown"
    if not allow(client_id):
        raise HTTPException(status_code=429, detail="terlalu banyak permintaan, cuba lagi sebentar")
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is empty")
    return answer_question(req.question)
