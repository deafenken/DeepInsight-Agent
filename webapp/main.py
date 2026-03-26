from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_tools import run_advanced_analysis
from app_whitebox import MOCK_ANSWER, MOCK_CHUNKS, MOCK_REASONING, MOCK_SQL
from retriever import DEFAULT_DB_PATH, answer_query, create_optional_client, get_connection
from workflow_report import run_workflow

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    company_name: str | None = None
    report_year: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class WorkflowRequest(BaseModel):
    topic: str = Field(min_length=1)
    company_name: str | None = None
    report_year: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class AdvancedRequest(BaseModel):
    question: str = Field(min_length=1)
    company_name: str = Field(min_length=1)


def build_filters(company_name: str | None, report_year: int | None) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if company_name and company_name != "全部":
        filters["company_name"] = company_name
    if report_year:
        filters["report_year"] = report_year
    return filters


def fetch_bootstrap_data() -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        companies = [row[0] for row in conn.execute("SELECT company_name FROM dim_company ORDER BY company_name").fetchall()]
        years = [row[0] for row in conn.execute("SELECT DISTINCT report_year FROM dim_document WHERE report_year IS NOT NULL ORDER BY report_year DESC").fetchall()]
        stats = {
            "companies": conn.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0],
            "documents": conn.execute("SELECT COUNT(*) FROM dim_document").fetchone()[0],
            "financial_facts": conn.execute("SELECT COUNT(*) FROM fact_financial_report").fetchone()[0],
            "macro_facts": conn.execute("SELECT COUNT(*) FROM fact_macro_data").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "companies": companies,
        "years": years,
        "stats": stats,
        "deepseek_enabled": bool(create_optional_client()),
    }


app = FastAPI(title="医药生物企业智能分析与决策支持系统")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    return fetch_bootstrap_data()


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    client = create_optional_client()
    filters = build_filters(payload.company_name, payload.report_year)
    result = answer_query(payload.question, filters=filters, top_k=payload.top_k, client=client)
    return {
        "question": payload.question,
        "answer_markdown": result.get("answer_markdown", ""),
        "sources": result.get("sources") or [],
        "warnings": result.get("warnings") or [],
        "route": result.get("route"),
        "sql": result.get("sql"),
        "macro_sql": result.get("macro_sql"),
        "chart_spec": result.get("chart_spec"),
        "sql_rows": result.get("sql_rows") or [],
        "macro_rows": result.get("macro_rows") or [],
        "chunks": result.get("chunks") or [],
        "deepseek_enabled": client is not None,
    }


@app.post("/api/workflow")
def workflow(payload: WorkflowRequest) -> dict[str, Any]:
    client = create_optional_client()
    filters = build_filters(payload.company_name, payload.report_year)
    result = run_workflow(payload.topic, filters=filters, top_k=payload.top_k, client=client)
    return {
        "topic": payload.topic,
        "report_markdown": result.get("report_markdown", ""),
        "sources": result.get("sources") or [],
        "warnings": result.get("warnings") or [],
        "sql": result.get("sql"),
        "sql_rows": result.get("sql_rows") or [],
        "rag_chunks": result.get("rag_chunks") or [],
        "data_mode": result.get("data_mode"),
        "deepseek_enabled": client is not None,
    }


@app.post("/api/advanced")
def advanced(payload: AdvancedRequest) -> dict[str, Any]:
    client = create_optional_client()
    result = run_advanced_analysis(payload.question, company_name=payload.company_name, client=client)
    return {
        "question": payload.question,
        "company_name": payload.company_name,
        "answer_markdown": result.get("answer_markdown", ""),
        "sources": result.get("sources") or [],
        "viz_blocks": result.get("viz_blocks") or [],
        "tool_results": result.get("tool_results") or {},
        "deepseek_enabled": client is not None,
    }


@app.get("/api/whitebox")
def whitebox() -> dict[str, Any]:
    return {
        "answer_markdown": MOCK_ANSWER,
        "sql": MOCK_SQL,
        "chunks": MOCK_CHUNKS,
        "reasoning_markdown": MOCK_REASONING,
    }
