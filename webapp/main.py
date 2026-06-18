from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from deepinsight.core.agent_tools import run_advanced_analysis, tool_get_equity_penetration, tool_get_innovation_index, tool_get_risk_radar
from deepinsight.apps.app_whitebox import MOCK_ANSWER, MOCK_CHUNKS, MOCK_REASONING, MOCK_SQL
from deepinsight.core.industry_taxonomy import infer_industry_name
from deepinsight.core.retriever import DEFAULT_DB_PATH, answer_query, create_optional_client, get_connection
from deepinsight.apps.workflow_report import run_workflow

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    company_name: str | None = None
    industry_name: str | None = None
    report_year: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)
    history: list[dict[str, Any]] | None = None
    model: str | None = None


class WorkflowRequest(BaseModel):
    topic: str = Field(min_length=1)
    company_name: str | None = None
    industry_name: str | None = None
    report_year: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class AdvancedRequest(BaseModel):
    question: str = Field(min_length=1)
    company_name: str = Field(min_length=1)


class BatchWorkflowRequest(BaseModel):
    company_names: list[str] = Field(default_factory=list)
    industry_name: str | None = None
    report_year: int | None = None
    top_k: int = Field(default=5, ge=1, le=10)


TREND_INDICATORS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "经营活动产生的现金流量净额",
    "研发费用",
    "净资产收益率",
]
RANKING_INDICATORS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "研发费用",
    "净资产收益率",
]
PROFILE_INDICATORS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "经营活动产生的现金流量净额",
    "研发费用",
    "净资产收益率",
    "总资产",
]
COMPARE_INDICATORS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "经营活动产生的现金流量净额",
    "研发费用",
    "净资产收益率",
    "总资产",
]
ALERT_INDICATORS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "经营活动产生的现金流量净额",
    "研发费用",
    "净资产收益率",
]
MACRO_PRIORITY_KEYWORDS = [
    "卫生总费用-卫生总费用",
    "医疗卫生机构-医院数",
    "医疗卫生机构-医疗卫生机构数",
    "医疗卫生机构门诊服务情况-医疗卫生机构诊疗人次",
    "每万人口卫生技术人员数-每万人拥有执业(助理)医师数",
]
SEVERITY_ORDER = {"高": 0, "中": 1, "低": 2}


def build_filters(company_name: str | None, report_year: int | None, industry_name: str | None = None) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if company_name and company_name != "全部":
        filters["company_name"] = company_name
    if industry_name and industry_name != "全部":
        filters["industry_name"] = industry_name
    if report_year:
        filters["report_year"] = report_year
    return filters


def fetch_bootstrap_data() -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        industries = [
            row[0]
            for row in conn.execute(
                """
                SELECT industry_name
                FROM dim_industry
                WHERE COALESCE(industry_level, 2) >= 2
                ORDER BY industry_name
                """
            ).fetchall()
        ]
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
        "industries": industries,
        "companies": companies,
        "years": years,
        "stats": stats,
        "deepseek_enabled": bool(create_optional_client()),
    }


def _normalize_number(value: float | int | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def _format_change_ratio(current_value: float | None, previous_value: float | None) -> str:
    if current_value is None or previous_value in (None, 0):
        return "同比待补充"
    delta_ratio = (current_value - previous_value) / abs(previous_value)
    direction = "上升" if delta_ratio > 0 else ("下降" if delta_ratio < 0 else "持平")
    return f"{direction} {abs(delta_ratio) * 100:.1f}%"


def _get_default_company(conn, company_name: str | None) -> str | None:
    if company_name and company_name != "全部":
        return company_name
    row = conn.execute(
        """
        SELECT c.company_name
        FROM dim_document d
        JOIN dim_company c ON c.company_id = d.company_id
        WHERE d.is_latest = 1
        ORDER BY c.company_name
        LIMIT 1
        """
    ).fetchone()
    return row[0] if row else None


def _build_trend_anomalies(grouped: dict[str, list[dict[str, Any]]]) -> list[str]:
    anomalies: list[str] = []
    revenue_rows = grouped.get("营业收入") or []
    profit_rows = grouped.get("归属于上市公司股东的净利润") or []
    cash_rows = grouped.get("经营活动产生的现金流量净额") or []
    roe_rows = grouped.get("净资产收益率") or []
    rd_rows = grouped.get("研发费用") or []

    current_revenue = revenue_rows[-1]["value_num"] if revenue_rows else None
    previous_revenue = revenue_rows[-2]["value_num"] if len(revenue_rows) >= 2 else None
    current_profit = profit_rows[-1]["value_num"] if profit_rows else None
    previous_profit = profit_rows[-2]["value_num"] if len(profit_rows) >= 2 else None
    current_cash = cash_rows[-1]["value_num"] if cash_rows else None
    current_roe = roe_rows[-1]["value_num"] if roe_rows else None
    current_rd = rd_rows[-1]["value_num"] if rd_rows else None
    previous_rd = rd_rows[-2]["value_num"] if len(rd_rows) >= 2 else None

    if current_profit is not None and current_profit > 0 and current_cash is not None and current_cash < 0:
        anomalies.append("净利润为正但经营现金流为负，利润含金量需要重点复核。")
    if (
        current_revenue is not None and previous_revenue not in (None, 0)
        and current_profit is not None and previous_profit not in (None, 0)
        and current_revenue > previous_revenue and current_profit < previous_profit
    ):
        anomalies.append("营收增长但净利润下滑，存在增收不增利迹象。")
    if current_roe is not None and current_roe < 0:
        anomalies.append("净资产收益率为负，股东回报表现偏弱。")
    if current_rd is not None and previous_rd not in (None, 0) and current_rd < previous_rd * 0.8:
        anomalies.append("研发费用同比下降较多，需关注创新投入是否收缩。")
    return anomalies[:4]


def _get_metric_status(indicator_name: str, current_value: float | None, previous_value: float | None) -> dict[str, str]:
    if current_value is None:
        return {"level": "neutral", "label": "待补充"}
    delta = None if previous_value is None else current_value - previous_value
    if indicator_name in {"营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "研发费用"}:
        if current_value < 0 and indicator_name != "研发费用":
            return {"level": "red", "label": "承压"}
        if delta is None:
            return {"level": "neutral", "label": "观察"}
        if delta > 0:
            return {"level": "green", "label": "改善"}
        if delta < 0:
            return {"level": "amber", "label": "回落"}
        return {"level": "neutral", "label": "持平"}
    if indicator_name == "净资产收益率":
        if current_value < 0:
            return {"level": "red", "label": "偏弱"}
        if current_value >= 10:
            return {"level": "green", "label": "良好"}
        if current_value >= 5:
            return {"level": "amber", "label": "一般"}
        return {"level": "amber", "label": "偏低"}
    return {"level": "neutral", "label": "观察"}


def _build_trend_summary(company_name: str, cards: list[dict[str, Any]], anomalies: list[str]) -> str:
    if not cards:
        return f"{company_name} 当前缺少足够趋势数据，暂时无法生成自动摘要。"
    highlights = []
    for card in cards[:4]:
        status_label = card.get("status", {}).get("label")
        if status_label:
            highlights.append(f"{card['label']}{status_label}")
    if anomalies:
        return f"{company_name} 当前趋势概览为：{'、'.join(highlights[:3])}。另外需要重点关注：{anomalies[0]}"
    return f"{company_name} 当前趋势概览为：{'、'.join(highlights[:3])}。整体未发现特别突出的异常信号。"


def _resolve_report_year(conn, company_name: str | None, report_year: int | None) -> int | None:
    if report_year:
        return report_year
    if not company_name:
        return None
    row = conn.execute(
        """
        SELECT MAX(d.report_year) AS report_year
        FROM dim_document d
        JOIN dim_company c ON c.company_id = d.company_id
        WHERE c.company_name = ? AND d.is_latest = 1 AND d.report_year IS NOT NULL
        """,
        (company_name,),
    ).fetchone()
    return int(row["report_year"]) if row and row["report_year"] is not None else None


def _resolve_company_meta(conn, company_name: str | None, report_year: int | None = None) -> dict[str, Any]:
    resolved_company = _get_default_company(conn, company_name)
    if not resolved_company:
        return {"company_name": None, "industry_name": None, "report_year": report_year}
    company_row = conn.execute(
        """
        SELECT c.company_name, i.industry_name
        FROM dim_company c
        LEFT JOIN dim_industry i ON i.industry_id = c.primary_industry_id
        WHERE c.company_name = ?
        """,
        (resolved_company,),
    ).fetchone()
    resolved_year = _resolve_report_year(conn, resolved_company, report_year)
    return {
        "company_name": resolved_company,
        "industry_name": infer_industry_name(resolved_company, company_row["industry_name"] if company_row else None),
        "report_year": resolved_year,
    }


def _fetch_financial_rows(
    conn,
    company_names: list[str],
    indicators: list[str],
    report_year: int | None = None,
    include_historical: bool = True,
) -> list[dict[str, Any]]:
    if not company_names or not indicators:
        return []
    company_placeholders = ",".join("?" for _ in company_names)
    indicator_placeholders = ",".join("?" for _ in indicators)
    params: list[Any] = [*company_names, *indicators]
    year_clause = ""
    if report_year is not None:
        year_clause = " AND d.report_year = ?"
        params.append(report_year)
    role_clause = ""
    if not include_historical:
        role_clause = " AND f.value_role = 'current'"
    rows = conn.execute(
        """
        WITH dedup AS (
            SELECT
                c.company_name,
                d.report_year,
                i.indicator_name,
                f.value_num,
                COALESCE(f.unit, i.default_unit) AS unit,
                f.value_role,
                f.source_page,
                ROW_NUMBER() OVER (
                    PARTITION BY c.company_name, d.report_year, i.indicator_name, f.value_role
                    ORDER BY ABS(COALESCE(f.value_num, 0)) DESC, COALESCE(f.source_page, 999999) ASC
                ) AS rn
            FROM fact_financial_report f
            JOIN dim_document d ON d.document_id = f.document_id
            JOIN dim_company c ON c.company_id = d.company_id
            JOIN dict_financial_indicator i ON i.indicator_id = f.indicator_id
            WHERE d.is_latest = 1
              AND c.company_name IN ({company_placeholders})
              AND i.indicator_name IN ({indicator_placeholders})
              {year_clause}
              {role_clause}
        )
        SELECT company_name, report_year, indicator_name, value_num, unit, value_role, source_page
        FROM dedup
        WHERE rn = 1
        ORDER BY company_name, report_year, indicator_name, value_role
        """.format(
            company_placeholders=company_placeholders,
            indicator_placeholders=indicator_placeholders,
            year_clause=year_clause,
            role_clause=role_clause,
        ),
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _group_financial_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["company_name"], {}).setdefault(row["indicator_name"], {})[row["value_role"]] = row
    return grouped


def _format_metric_value(value: float | int | None, unit: str | None = None) -> str:
    if value is None:
        return "-"
    normalized = _normalize_number(value)
    unit_text = unit or ""
    return f"{normalized}{unit_text}"


def _build_financial_alerts(company_name: str, report_year: int | None, grouped: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    revenue = grouped.get("营业收入", {})
    profit = grouped.get("归属于上市公司股东的净利润", {})
    cash = grouped.get("经营活动产生的现金流量净额", {})
    roe = grouped.get("净资产收益率", {})
    rd = grouped.get("研发费用", {})

    current_revenue = revenue.get("current", {}).get("value_num")
    historical_revenue = revenue.get("historical", {}).get("value_num")
    current_profit = profit.get("current", {}).get("value_num")
    historical_profit = profit.get("historical", {}).get("value_num")
    current_cash = cash.get("current", {}).get("value_num")
    current_roe = roe.get("current", {}).get("value_num")
    current_rd = rd.get("current", {}).get("value_num")
    historical_rd = rd.get("historical", {}).get("value_num")

    if current_profit is not None and current_profit > 0 and current_cash is not None and current_cash < 0:
        alerts.append(
            {
                "company_name": company_name,
                "report_year": report_year,
                "severity": "高",
                "category": "财务质量",
                "signal": "净利润为正但经营现金流为负",
                "detail": "利润含金量承压，建议优先核查回款、存货和应收变化。",
            }
        )
    if current_roe is not None and current_roe < 0:
        alerts.append(
            {
                "company_name": company_name,
                "report_year": report_year,
                "severity": "高",
                "category": "回报能力",
                "signal": "净资产收益率为负",
                "detail": "股东回报表现偏弱，经营修复仍需验证。",
            }
        )
    if (
        current_revenue is not None and historical_revenue not in (None, 0)
        and current_profit is not None and historical_profit not in (None, 0)
        and current_revenue > historical_revenue and current_profit < historical_profit
    ):
        alerts.append(
            {
                "company_name": company_name,
                "report_year": report_year,
                "severity": "中",
                "category": "盈利结构",
                "signal": "营收增长但净利润下滑",
                "detail": "存在增收不增利迹象，建议复核毛利率、费用率和资产减值。",
            }
        )
    if current_rd is not None and historical_rd not in (None, 0) and current_rd < historical_rd * 0.8:
        alerts.append(
            {
                "company_name": company_name,
                "report_year": report_year,
                "severity": "中",
                "category": "创新投入",
                "signal": "研发费用同比明显下滑",
                "detail": "研发投入收缩超过 20%，需关注产品管线与中长期竞争力。",
            }
        )
    return alerts


def _fetch_company_latest_document(conn, company_name: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT d.title, d.file_name, d.file_path, d.report_year, d.updated_at
        FROM dim_document d
        JOIN dim_company c ON c.company_id = d.company_id
        WHERE c.company_name = ? AND d.is_latest = 1
        ORDER BY d.report_year DESC, d.updated_at DESC
        LIMIT 1
        """,
        (company_name,),
    ).fetchone()
    return dict(row) if row else None


def _pick_compare_peer(conn, company_name: str) -> str | None:
    meta = _resolve_company_meta(conn, company_name)
    industry_name = meta.get("industry_name")
    if industry_name:
        row = conn.execute(
            """
            SELECT c.company_name
            FROM dim_company c
            LEFT JOIN dim_industry i ON i.industry_id = c.primary_industry_id
            WHERE c.company_name <> ?
            ORDER BY CASE WHEN i.industry_name = ? THEN 0 ELSE 1 END, c.company_name
            LIMIT 1
            """,
            (company_name, industry_name),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT company_name FROM dim_company WHERE company_name <> ? ORDER BY company_name LIMIT 1",
            (company_name,),
        ).fetchone()
    return row[0] if row else None


def _safe_growth_text(current_value: float | None, previous_value: float | None) -> str:
    if current_value is None or previous_value in (None, 0):
        return "变化待补充"
    delta = current_value - previous_value
    if delta > 0:
        return "较上期改善"
    if delta < 0:
        return "较上期回落"
    return "较上期持平"


def fetch_company_profile_dashboard(company_name: str | None, report_year: int | None = None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        meta = _resolve_company_meta(conn, company_name, report_year)
        resolved_company = meta["company_name"]
        resolved_year = meta["report_year"]
        if not resolved_company:
            return {"company_name": None, "cards": []}
        financial_rows = _fetch_financial_rows(conn, [resolved_company], PROFILE_INDICATORS, resolved_year, include_historical=True)
        grouped = _group_financial_rows(financial_rows).get(resolved_company, {})
        trend = fetch_company_trend_dashboard(resolved_company)
        ranking = fetch_industry_ranking_dashboard(resolved_company, resolved_year, ranking_scope="industry")
        risk = tool_get_risk_radar(resolved_company, include_subsidiaries=True)
        innovation = tool_get_innovation_index(resolved_company)
        equity = tool_get_equity_penetration(resolved_company)
        latest_document = _fetch_company_latest_document(conn, resolved_company)
        cards = [
            {"label": "所属赛道", "value": meta["industry_name"] or "医药生物", "accent": "blue"},
            {"label": "画像年份", "value": resolved_year or "-", "accent": "teal"},
            {"label": "风险事件总数", "value": risk["dimensions"].get("风险事件总数", 0), "accent": "rose"},
            {"label": "专利总量", "value": innovation["dimensions"].get("专利总量", 0), "accent": "cyan"},
            {"label": "股权节点数", "value": equity["summary"].get("node_count", 0), "accent": "amber"},
        ]
        metric_cards = []
        for indicator_name in PROFILE_INDICATORS:
            current = grouped.get(indicator_name, {}).get("current")
            historical = grouped.get(indicator_name, {}).get("historical")
            if not current:
                continue
            metric_cards.append(
                {
                    "label": indicator_name,
                    "value": _format_metric_value(current.get("value_num"), current.get("unit")),
                    "meta": _safe_growth_text(current.get("value_num"), historical.get("value_num") if historical else None),
                }
            )
        risk_cards = [
            {"label": key, "value": value}
            for key, value in risk["dimensions"].items()
        ]
        innovation_cards = [
            {"label": key, "value": value}
            for key, value in innovation["dimensions"].items()
        ]
        equity_cards = [
            {"label": "图谱节点", "value": equity["summary"].get("node_count", 0)},
            {"label": "图谱边数", "value": equity["summary"].get("edge_count", 0)},
            {"label": "一级关系", "value": len([node for node in equity["nodes"] if node.get("level") == 1])},
        ]
        alerts = _build_financial_alerts(resolved_company, resolved_year, grouped)
        if risk["dimensions"].get("高风险事件数", 0) > 0:
            alerts.append(
                {
                    "company_name": resolved_company,
                    "report_year": resolved_year,
                    "severity": "高",
                    "category": "合规风险",
                    "signal": "近三年存在高风险司法/处罚事件",
                    "detail": f"已命中 {risk['dimensions'].get('高风险事件数', 0)} 起高风险事件，建议结合诉讼明细继续复核。",
                }
            )
        alerts = sorted(alerts, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["category"]))[:6]
        innovation_rows = innovation.get("details") or []
        profile_summary = (
            f"{resolved_company} 当前画像覆盖财务、风险、创新与股权四个维度。"
            f" 其中 {trend.get('summary') or '趋势数据有限'}"
            f" 风险侧近三年累计 {risk['dimensions'].get('风险事件总数', 0)} 起，创新侧累计专利 {innovation['dimensions'].get('专利总量', 0)} 件。"
        )
        return {
            "company_name": resolved_company,
            "industry_name": meta["industry_name"] or "医药生物",
            "report_year": resolved_year,
            "cards": cards,
            "metric_cards": metric_cards[:6],
            "risk_cards": risk_cards,
            "innovation_cards": innovation_cards,
            "equity_cards": equity_cards,
            "alerts": alerts,
            "summary": profile_summary,
            "latest_document": latest_document,
            "trend_chart": trend.get("amount_chart"),
            "ratio_chart": trend.get("ratio_chart"),
            "innovation_chart": {
                "title": f"{resolved_company} 专利活跃度趋势",
                "rows": innovation_rows,
                "chart_type": "bar",
                "x": "application_year",
                "y": "patent_count",
                "series": "patent_type",
            } if innovation_rows else None,
            "ranking_overview": ranking,
        }
    finally:
        conn.close()


def fetch_alert_center(company_name: str | None = None, report_year: int | None = None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        resolved_company = company_name if company_name and company_name != "全部" else None
        rows = _fetch_financial_rows(
            conn,
            [resolved_company] if resolved_company else [row[0] for row in conn.execute("SELECT company_name FROM dim_company").fetchall()],
            ALERT_INDICATORS,
            report_year,
            include_historical=True,
        )
        grouped = _group_financial_rows(rows)
        items: list[dict[str, Any]] = []
        for current_company, current_rows in grouped.items():
            if resolved_company and current_company != resolved_company:
                continue
            company_year = max(
                [row.get("report_year") for indicator_rows in current_rows.values() for row in indicator_rows.values() if row.get("report_year")],
                default=report_year,
            )
            items.extend(_build_financial_alerts(current_company, company_year, current_rows))
        legal_rows = conn.execute(
            """
            SELECT c.company_name, COUNT(*) AS risk_count, MAX(flr.severity_score) AS max_severity
            FROM fact_legal_risk flr
            JOIN dim_company c ON c.company_id = flr.company_id
            WHERE flr.filing_date >= date('now', '-3 years')
            GROUP BY c.company_name
            HAVING MAX(flr.severity_score) >= 80
            ORDER BY max_severity DESC, risk_count DESC
            """
        ).fetchall()
        for row in legal_rows:
            if resolved_company and row["company_name"] != resolved_company:
                continue
            items.append(
                {
                    "company_name": row["company_name"],
                    "report_year": report_year,
                    "severity": "高",
                    "category": "合规风险",
                    "signal": "近三年存在高风险司法/处罚事件",
                    "detail": f"累计 {row['risk_count']} 起，最高严重度 {row['max_severity']} 分。",
                }
            )
        empty_doc_rows = conn.execute(
            """
            SELECT c.company_name, d.report_year, d.file_name
            FROM dim_document d
            JOIN dim_company c ON c.company_id = d.company_id
            WHERE d.is_latest = 1
              AND COALESCE(json_extract(d.metadata_json, '$.has_meaningful_text'), 1) = 0
            ORDER BY d.updated_at DESC
            """
        ).fetchall()
        for row in empty_doc_rows:
            if resolved_company and row["company_name"] != resolved_company:
                continue
            items.append(
                {
                    "company_name": row["company_name"],
                    "report_year": row["report_year"],
                    "severity": "中",
                    "category": "数据质量",
                    "signal": "最新文档缺少可抽取正文",
                    "detail": f"{row['file_name']} 当前为图片占位型 Markdown，已从 RAG 中隔离。",
                }
            )
        deduped = []
        seen = set()
        for item in sorted(items, key=lambda current: (SEVERITY_ORDER.get(current["severity"], 9), current["company_name"], current["signal"])):
            key = (item["company_name"], item["signal"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        cards = [
            {"label": "高优先级预警", "value": sum(1 for item in deduped if item["severity"] == "高"), "accent": "rose"},
            {"label": "中优先级预警", "value": sum(1 for item in deduped if item["severity"] == "中"), "accent": "amber"},
            {"label": "覆盖公司数", "value": len({item['company_name'] for item in deduped}), "accent": "blue"},
        ]
        summary = "当前未发现明显预警。" if not deduped else f"当前共识别 {len(deduped)} 条重点预警，其中高优先级 {cards[0]['value']} 条。"
        return {
            "company_name": resolved_company,
            "cards": cards,
            "summary": summary,
            "items": deduped[:16],
        }
    finally:
        conn.close()


def fetch_compare_matrix_dashboard(company_name: str | None, compare_company_name: str | None = None, report_year: int | None = None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        primary_meta = _resolve_company_meta(conn, company_name, report_year)
        primary_company = primary_meta["company_name"]
        if not primary_company:
            return {"company_names": [], "rows": []}
        secondary_company = compare_company_name if compare_company_name and compare_company_name != primary_company else _pick_compare_peer(conn, primary_company)
        if not secondary_company:
            return {"company_names": [primary_company], "rows": []}
        resolved_year = primary_meta["report_year"] or _resolve_report_year(conn, secondary_company, report_year)
        rows = _fetch_financial_rows(conn, [primary_company, secondary_company], COMPARE_INDICATORS, resolved_year, include_historical=False)
        grouped = _group_financial_rows(rows)
        risk_primary = tool_get_risk_radar(primary_company)
        risk_secondary = tool_get_risk_radar(secondary_company)
        innovation_primary = tool_get_innovation_index(primary_company)
        innovation_secondary = tool_get_innovation_index(secondary_company)
        matrix_rows = []
        for metric in COMPARE_INDICATORS:
            left = grouped.get(primary_company, {}).get(metric, {}).get("current")
            right = grouped.get(secondary_company, {}).get(metric, {}).get("current")
            left_value = left.get("value_num") if left else None
            right_value = right.get("value_num") if right else None
            winner = "持平"
            if left_value is not None and right_value is not None:
                if left_value > right_value:
                    winner = primary_company
                elif right_value > left_value:
                    winner = secondary_company
            matrix_rows.append(
                {
                    "metric": metric,
                    "left_value": _format_metric_value(left_value, left.get("unit") if left else None),
                    "right_value": _format_metric_value(right_value, right.get("unit") if right else None),
                    "winner": winner,
                }
            )
        extra_rows = [
            {
                "metric": "风险事件总数",
                "left_value": str(risk_primary["dimensions"].get("风险事件总数", 0)),
                "right_value": str(risk_secondary["dimensions"].get("风险事件总数", 0)),
                "winner": primary_company if risk_primary["dimensions"].get("风险事件总数", 0) < risk_secondary["dimensions"].get("风险事件总数", 0) else (secondary_company if risk_secondary["dimensions"].get("风险事件总数", 0) < risk_primary["dimensions"].get("风险事件总数", 0) else "持平"),
            },
            {
                "metric": "专利总量",
                "left_value": str(innovation_primary["dimensions"].get("专利总量", 0)),
                "right_value": str(innovation_secondary["dimensions"].get("专利总量", 0)),
                "winner": primary_company if innovation_primary["dimensions"].get("专利总量", 0) > innovation_secondary["dimensions"].get("专利总量", 0) else (secondary_company if innovation_secondary["dimensions"].get("专利总量", 0) > innovation_primary["dimensions"].get("专利总量", 0) else "持平"),
            },
        ]
        matrix_rows.extend(extra_rows)
        win_counts = defaultdict(int)
        for row in matrix_rows:
            if row["winner"] not in {primary_company, secondary_company}:
                continue
            win_counts[row["winner"]] += 1
        summary = f"{primary_company} 领先 {win_counts[primary_company]} 项，{secondary_company} 领先 {win_counts[secondary_company]} 项。"
        chart_rows = []
        for row in matrix_rows:
            for company_value, company_label in [(row["left_value"], primary_company), (row["right_value"], secondary_company)]:
                try:
                    numeric_value = float(str(company_value).rstrip("%元"))
                except ValueError:
                    continue
                chart_rows.append({"metric": row["metric"], "company_name": company_label, "value_num": numeric_value})
        return {
            "company_names": [primary_company, secondary_company],
            "report_year": resolved_year,
            "summary": summary,
            "rows": matrix_rows,
            "chart": {
                "title": f"{primary_company} vs {secondary_company} 对比矩阵",
                "rows": chart_rows,
                "chart_type": "bar",
                "x": "metric",
                "y": "value_num",
                "series": "company_name",
            } if chart_rows else None,
        }
    finally:
        conn.close()


def fetch_company_timeline_dashboard(company_name: str | None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        meta = _resolve_company_meta(conn, company_name)
        resolved_company = meta["company_name"]
        if not resolved_company:
            return {"company_name": None, "events": []}
        events: list[dict[str, Any]] = []
        financial_rows = _fetch_financial_rows(conn, [resolved_company], ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额"], include_historical=False)
        for row in financial_rows:
            if row.get("report_year") is None:
                continue
            events.append(
                {
                    "event_date": f"{row['report_year']}-12-31",
                    "category": "财务",
                    "title": f"{row['report_year']}年 {row['indicator_name']}",
                    "detail": _format_metric_value(row.get("value_num"), row.get("unit")),
                }
            )
        legal_rows = conn.execute(
            """
            SELECT risk_type, filing_date, severity_score, detail_text
            FROM fact_legal_risk flr
            JOIN dim_company c ON c.company_id = flr.company_id
            WHERE c.company_name = ?
            ORDER BY filing_date DESC, severity_score DESC
            LIMIT 12
            """,
            (resolved_company,),
        ).fetchall()
        for row in legal_rows:
            events.append(
                {
                    "event_date": row["filing_date"],
                    "category": "风险",
                    "title": row["risk_type"],
                    "detail": f"严重度 {row['severity_score']} 分。{row['detail_text'] or ''}".strip(),
                }
            )
        patent_rows = conn.execute(
            """
            SELECT application_year, patent_type, patent_name, patent_score
            FROM fact_ip_patent p
            JOIN dim_company c ON c.company_id = p.company_id
            WHERE c.company_name = ?
            ORDER BY application_year DESC, patent_score DESC
            LIMIT 12
            """,
            (resolved_company,),
        ).fetchall()
        for row in patent_rows:
            events.append(
                {
                    "event_date": f"{row['application_year']}-06-30",
                    "category": "创新",
                    "title": row["patent_name"],
                    "detail": f"{row['patent_type']} · 评分 {row['patent_score'] or '-'}",
                }
            )
        ordered = sorted(events, key=lambda item: item["event_date"], reverse=True)
        cards = [
            {"label": "财务事件", "value": sum(1 for item in ordered if item["category"] == "财务"), "accent": "blue"},
            {"label": "风险事件", "value": sum(1 for item in ordered if item["category"] == "风险"), "accent": "rose"},
            {"label": "创新事件", "value": sum(1 for item in ordered if item["category"] == "创新"), "accent": "teal"},
        ]
        return {
            "company_name": resolved_company,
            "cards": cards,
            "events": ordered[:24],
            "summary": f"{resolved_company} 当前时间轴已整合财务、风险、创新三类事件，方便答辩时串联经营变化与关键外部事件。",
        }
    finally:
        conn.close()


def fetch_macro_linkage_dashboard(company_name: str | None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        meta = _resolve_company_meta(conn, company_name)
        resolved_company = meta["company_name"]
        if not resolved_company:
            return {"company_name": None, "cards": [], "macro_chart": None}
        company_rows = _fetch_financial_rows(conn, [resolved_company], ["营业收入", "归属于上市公司股东的净利润"], include_historical=False)
        revenue_rows = [row for row in company_rows if row["indicator_name"] == "营业收入" and row.get("report_year") is not None]
        macro_conditions = " OR ".join("d.indicator_name LIKE ?" for _ in MACRO_PRIORITY_KEYWORDS)
        macro_rows = conn.execute(
            f"""
            SELECT
                d.indicator_name,
                SUBSTR(f.period_date, 1, 4) AS period_year,
                AVG(f.value_num) AS value_num,
                COALESCE(MAX(f.unit), MAX(d.default_unit)) AS unit
            FROM fact_macro_data f
            JOIN dict_macro_indicator d ON d.macro_indicator_id = f.macro_indicator_id
            WHERE {macro_conditions}
            GROUP BY d.indicator_name, SUBSTR(f.period_date, 1, 4)
            ORDER BY d.indicator_name, period_year
            """,
            [f"%{keyword}%" for keyword in MACRO_PRIORITY_KEYWORDS],
        ).fetchall()
        grouped_macro: dict[str, list[dict[str, Any]]] = {}
        for row in macro_rows:
            grouped_macro.setdefault(row["indicator_name"], []).append(dict(row))
        selected_metrics = []
        for keyword in MACRO_PRIORITY_KEYWORDS:
            match = next((name for name in grouped_macro if keyword in name), None)
            if match and match not in selected_metrics:
                selected_metrics.append(match)
        selected_metrics = selected_metrics[:4]
        chosen_rows = [row for row in macro_rows if row["indicator_name"] in selected_metrics]
        cards = []
        macro_directions = []
        for metric in selected_metrics:
            metric_rows = grouped_macro.get(metric) or []
            if not metric_rows:
                continue
            latest = metric_rows[-1]
            previous = metric_rows[0]
            cards.append(
                {
                    "label": metric,
                    "value": _format_metric_value(latest["value_num"], latest["unit"]),
                    "accent": "cyan",
                }
            )
            if latest["value_num"] is not None and previous["value_num"] is not None:
                macro_directions.append(f"{metric}{'上行' if latest['value_num'] > previous['value_num'] else ('下行' if latest['value_num'] < previous['value_num'] else '平稳')}")
        revenue_direction = "待补充"
        if len(revenue_rows) >= 2 and revenue_rows[-1]["value_num"] is not None and revenue_rows[0]["value_num"] is not None:
            revenue_direction = "上行" if revenue_rows[-1]["value_num"] > revenue_rows[0]["value_num"] else ("下行" if revenue_rows[-1]["value_num"] < revenue_rows[0]["value_num"] else "平稳")
        summary = (
            f"{resolved_company} 的营业收入趋势整体{revenue_direction}。"
            + (f" 同期宏观信号显示：{'、'.join(macro_directions[:3])}。" if macro_directions else " 当前宏观指标样本较少，建议把它作为辅助判断。")
        )
        return {
            "company_name": resolved_company,
            "cards": cards,
            "summary": summary,
            "macro_chart": {
                "title": f"{resolved_company} 关联宏观指标",
                "rows": [dict(row) for row in chosen_rows],
                "chart_type": "line",
                "x": "period_year",
                "y": "value_num",
                "series": "indicator_name",
            } if chosen_rows else None,
            "revenue_chart": {
                "title": f"{resolved_company} 营业收入趋势",
                "rows": revenue_rows,
                "chart_type": "line",
                "x": "report_year",
                "y": "value_num",
                "series": "indicator_name",
            } if revenue_rows else None,
        }
    finally:
        conn.close()


def build_batch_workflow_markdown(items: list[dict[str, Any]]) -> str:
    sections = []
    for item in items:
        sections.append(f"# {item['company_name']}\n\n{item['report_markdown']}")
    return "\n\n---\n\n".join(sections)


def fetch_import_dashboard() -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        summary = conn.execute(
            """
            WITH latest_docs AS (
                SELECT document_id, file_path, metadata_json
                FROM dim_document
                WHERE is_latest = 1
            )
            SELECT
                (SELECT COUNT(*) FROM dim_document) AS documents_total,
                (SELECT COUNT(*) FROM latest_docs) AS latest_documents,
                (SELECT COUNT(*) FROM map_vector_chunk) AS chunk_total,
                (SELECT COUNT(*) FROM fact_financial_report) AS fact_total,
                (
                    SELECT COUNT(*)
                    FROM latest_docs d
                    WHERE COALESCE(json_extract(d.metadata_json, '$.has_meaningful_text'), 1) = 0
                ) AS empty_text_documents,
                (
                    SELECT COUNT(DISTINCT d.document_id)
                    FROM latest_docs d
                    JOIN map_vector_chunk m ON m.document_id = d.document_id
                ) AS latest_with_chunks,
                (
                    SELECT COUNT(DISTINCT d.document_id)
                    FROM latest_docs d
                    JOIN fact_financial_report f ON f.document_id = d.document_id
                ) AS latest_with_facts,
                (
                    SELECT COUNT(*)
                    FROM dim_document
                    WHERE file_path LIKE '%/Final_md/%'
                ) AS final_md_documents
            """
        ).fetchone()
        source_rows = conn.execute(
            """
            SELECT
                CASE
                    WHEN file_path LIKE '%/Final_md/%' THEN 'Final_md'
                    WHEN file_path LIKE '%/reports_md/%' THEN 'reports_md'
                    WHEN file_path LIKE '%/report_md/%' THEN 'report_md'
                    ELSE 'other'
                END AS source_group,
                COUNT(*) AS documents,
                SUM(CASE WHEN is_latest = 1 THEN 1 ELSE 0 END) AS latest_documents
            FROM dim_document
            GROUP BY source_group
            ORDER BY documents DESC, source_group
            """
        ).fetchall()
        risk_rows = conn.execute(
            """
            SELECT
                c.company_name,
                d.report_year,
                d.file_name,
                d.file_path,
                COALESCE(json_extract(d.metadata_json, '$.meaningful_line_count'), 0) AS meaningful_line_count,
                COALESCE(json_extract(d.metadata_json, '$.picture_placeholder_lines'), 0) AS picture_placeholder_lines,
                COALESCE(json_extract(d.metadata_json, '$.non_empty_line_count'), 0) AS non_empty_line_count,
                d.updated_at
            FROM dim_document d
            JOIN dim_company c ON c.company_id = d.company_id
            WHERE d.is_latest = 1
              AND COALESCE(json_extract(d.metadata_json, '$.has_meaningful_text'), 1) = 0
            ORDER BY d.updated_at DESC, c.company_name, d.report_year DESC
            LIMIT 10
            """
        ).fetchall()
        last_import_row = conn.execute("SELECT MAX(updated_at) AS last_import_at FROM dim_document").fetchone()
        latest_documents = summary["latest_documents"] or 0
        latest_with_chunks = summary["latest_with_chunks"] or 0
        latest_with_facts = summary["latest_with_facts"] or 0
        chunk_coverage = (latest_with_chunks / latest_documents * 100) if latest_documents else 0.0
        fact_coverage = (latest_with_facts / latest_documents * 100) if latest_documents else 0.0
        cards = [
            {"label": "导入文档总数", "value": summary["documents_total"], "accent": "blue"},
            {"label": "最新文档数", "value": latest_documents, "accent": "teal"},
            {"label": "向量切片数", "value": summary["chunk_total"], "accent": "cyan"},
            {"label": "财务事实数", "value": summary["fact_total"], "accent": "amber"},
            {"label": "空文本风险文档", "value": summary["empty_text_documents"], "accent": "rose"},
        ]
        health_cards = [
            {"label": "最新文档切片覆盖率", "value": f"{chunk_coverage:.1f}%", "accent": "teal"},
            {"label": "最新文档事实覆盖率", "value": f"{fact_coverage:.1f}%", "accent": "blue"},
            {"label": "Final_md 文档数", "value": summary["final_md_documents"], "accent": "cyan"},
        ]
        source_breakdown = [
            {
                "source_group": row["source_group"],
                "documents": row["documents"],
                "latest_documents": row["latest_documents"],
            }
            for row in source_rows
        ]
        risk_documents = [
            {
                "company_name": row["company_name"],
                "report_year": row["report_year"],
                "file_name": row["file_name"],
                "file_path": row["file_path"],
                "meaningful_line_count": row["meaningful_line_count"],
                "picture_placeholder_lines": row["picture_placeholder_lines"],
                "non_empty_line_count": row["non_empty_line_count"],
                "updated_at": row["updated_at"],
            }
            for row in risk_rows
        ]
        return {
            "cards": cards,
            "health_cards": health_cards,
            "source_breakdown": source_breakdown,
            "last_import_at": last_import_row["last_import_at"] if last_import_row else None,
            "risk_documents": risk_documents,
        }
    finally:
        conn.close()


def _fetch_user_tables(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def fetch_database_catalog() -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        tables = []
        for table in _fetch_user_tables(conn):
            table_name = table["name"]
            quoted_name = _quote_identifier(table_name)
            column_rows = conn.execute(f"PRAGMA table_info({quoted_name})").fetchall()
            row_count = conn.execute(f"SELECT COUNT(*) AS row_count FROM {quoted_name}").fetchone()["row_count"]
            tables.append(
                {
                    "table_name": table_name,
                    "row_count": row_count,
                    "column_count": len(column_rows),
                    "columns": [row["name"] for row in column_rows],
                    "has_create_sql": bool(table.get("sql")),
                }
            )
        return {
            "database_path": str(DEFAULT_DB_PATH),
            "table_count": len(tables),
            "table_names": [table["table_name"] for table in tables],
            "tables": tables,
        }
    finally:
        conn.close()


def fetch_database_table_preview(table_name: str, limit: int = 20) -> dict[str, Any]:
    normalized_table_name = (table_name or "").strip()
    if not normalized_table_name:
        raise ValueError("请先选择需要查看的数据表。")
    normalized_limit = max(1, min(int(limit), 100))
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        user_tables = {table["name"]: table for table in _fetch_user_tables(conn)}
        if normalized_table_name not in user_tables:
            raise ValueError(f"数据库中不存在数据表：{normalized_table_name}")
        quoted_name = _quote_identifier(normalized_table_name)
        column_rows = conn.execute(f"PRAGMA table_info({quoted_name})").fetchall()
        row_count = conn.execute(f"SELECT COUNT(*) AS row_count FROM {quoted_name}").fetchone()["row_count"]
        preview_rows = conn.execute(
            f"SELECT * FROM {quoted_name} LIMIT ?",
            (normalized_limit,),
        ).fetchall()
        return {
            "database_path": str(DEFAULT_DB_PATH),
            "table_name": normalized_table_name,
            "limit": normalized_limit,
            "row_count": row_count,
            "create_sql": user_tables[normalized_table_name].get("sql") or "",
            "columns": [
                {
                    "cid": row["cid"],
                    "name": row["name"],
                    "type": row["type"] or "TEXT",
                    "notnull": bool(row["notnull"]),
                    "default_value": row["dflt_value"],
                    "is_pk": bool(row["pk"]),
                }
                for row in column_rows
            ],
            "rows": [dict(row) for row in preview_rows],
        }
    finally:
        conn.close()


def fetch_data_room_catalog() -> dict[str, Any]:
    catalog = fetch_database_catalog()
    return {
        "table_count": catalog["table_count"],
        "table_names": catalog["table_names"],
        "tables": catalog["tables"],
    }


def fetch_data_room_preview(name: str, limit: int = 20) -> dict[str, Any]:
    preview = fetch_database_table_preview(name, limit)
    return {
        "table_name": preview["table_name"],
        "limit": preview["limit"],
        "row_count": preview["row_count"],
        "columns": preview["columns"],
        "rows": preview["rows"],
    }


def fetch_company_trend_dashboard(company_name: str | None) -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        resolved_company = _get_default_company(conn, company_name)
        if not resolved_company:
            return {"company_name": None, "cards": [], "amount_chart": None, "ratio_chart": None}
        rows = conn.execute(
            """
            WITH dedup AS (
                SELECT
                    c.company_name,
                    d.report_year,
                    i.indicator_name,
                    f.value_num,
                    i.default_unit AS unit,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.company_name, d.report_year, i.indicator_name
                        ORDER BY ABS(COALESCE(f.value_num, 0)) DESC, COALESCE(f.source_page, 999999) ASC
                    ) AS rn
                FROM fact_financial_report f
                JOIN dim_document d ON d.document_id = f.document_id
                JOIN dim_company c ON c.company_id = d.company_id
                JOIN dict_financial_indicator i ON i.indicator_id = f.indicator_id
                WHERE c.company_name = ?
                  AND d.is_latest = 1
                  AND f.value_role = 'current'
                  AND i.indicator_name IN ({placeholders})
            )
            SELECT company_name, report_year, indicator_name, value_num, unit
            FROM dedup
            WHERE rn = 1
            ORDER BY report_year ASC, indicator_name ASC
            """.format(placeholders=",".join("?" for _ in TREND_INDICATORS)),
            (resolved_company, *TREND_INDICATORS),
        ).fetchall()
        trend_rows = [dict(row) for row in rows]
        years = sorted({row["report_year"] for row in trend_rows if row["report_year"] is not None})
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in trend_rows:
            grouped.setdefault(row["indicator_name"], []).append(row)
        cards = []
        for indicator_name in ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "净资产收益率"]:
            metric_rows = grouped.get(indicator_name) or []
            if not metric_rows:
                continue
            current = metric_rows[-1]
            previous = metric_rows[-2] if len(metric_rows) >= 2 else None
            status = _get_metric_status(indicator_name, current.get("value_num"), previous.get("value_num") if previous else None)
            cards.append(
                {
                    "label": indicator_name,
                    "value": _normalize_number(current.get("value_num")),
                    "unit": current.get("unit") or "",
                    "report_year": current.get("report_year"),
                    "change_text": _format_change_ratio(current.get("value_num"), previous.get("value_num") if previous else None),
                    "status": status,
                }
            )
        amount_rows = [row for row in trend_rows if row["indicator_name"] in {"营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "研发费用"}]
        ratio_rows = [row for row in trend_rows if row["indicator_name"] in {"净资产收益率"}]
        anomalies = _build_trend_anomalies(grouped)
        return {
            "company_name": resolved_company,
            "years": years,
            "cards": cards,
            "anomalies": anomalies,
            "summary": _build_trend_summary(resolved_company, cards, anomalies),
            "amount_chart": {
                "title": f"{resolved_company} 关键金额指标趋势",
                "rows": amount_rows,
                "chart_type": "line",
                "x": "report_year",
                "y": "value_num",
                "series": "indicator_name",
            } if amount_rows else None,
            "ratio_chart": {
                "title": f"{resolved_company} 回报率趋势",
                "rows": ratio_rows,
                "chart_type": "line",
                "x": "report_year",
                "y": "value_num",
                "series": "indicator_name",
            } if ratio_rows else None,
        }
    finally:
        conn.close()


def fetch_industry_ranking_dashboard(company_name: str | None, report_year: int | None, ranking_scope: str = "industry") -> dict[str, Any]:
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        resolved_company = _get_default_company(conn, company_name)
        if not resolved_company:
            return {"company_name": None, "industry_name": None, "report_year": report_year, "boards": []}
        company_row = conn.execute(
            """
            SELECT c.company_name, i.industry_name
            FROM dim_company c
            LEFT JOIN dim_industry i ON i.industry_id = c.primary_industry_id
            WHERE c.company_name = ?
            """,
            (resolved_company,),
        ).fetchone()
        resolved_year = report_year
        if resolved_year is None:
            year_row = conn.execute(
                """
                SELECT MAX(d.report_year)
                FROM dim_document d
                JOIN dim_company c ON c.company_id = d.company_id
                WHERE c.company_name = ? AND d.is_latest = 1
                """,
                (resolved_company,),
            ).fetchone()
            resolved_year = year_row[0] if year_row else None
        if resolved_year is None:
            return {
                "company_name": resolved_company,
                "industry_name": infer_industry_name(resolved_company, company_row["industry_name"] if company_row else None),
                "scope_label": "同一级行业排名" if ranking_scope == "industry" else "全行业排名",
                "ranking_scope": ranking_scope,
                "report_year": None,
                "boards": [],
            }
        industry_name = infer_industry_name(resolved_company, company_row["industry_name"] if company_row else None)
        ranking_scope_sql = """
            WITH dedup AS (
                SELECT
                    c.company_name,
                    i.indicator_name,
                    f.value_num,
                    i.default_unit AS unit,
                    di.industry_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.company_name, d.report_year, i.indicator_name
                        ORDER BY ABS(COALESCE(f.value_num, 0)) DESC, COALESCE(f.source_page, 999999) ASC
                    ) AS rn
                FROM fact_financial_report f
                JOIN dim_document d ON d.document_id = f.document_id
                JOIN dim_company c ON c.company_id = d.company_id
                JOIN dict_financial_indicator i ON i.indicator_id = f.indicator_id
                LEFT JOIN dim_industry di ON di.industry_id = c.primary_industry_id
                WHERE d.is_latest = 1
                  AND d.report_year = ?
                  AND f.value_role = 'current'
                  AND i.indicator_name IN ({placeholders})
            )
            SELECT company_name, indicator_name, value_num, unit, industry_name
            FROM dedup
            WHERE rn = 1
        """.format(placeholders=",".join("?" for _ in RANKING_INDICATORS))
        params: list[Any] = [resolved_year, *RANKING_INDICATORS]
        ranking_scope_sql += " ORDER BY indicator_name, value_num DESC"
        raw_rows = [dict(row) for row in conn.execute(ranking_scope_sql, params).fetchall()]
        rows = []
        use_industry_scope = ranking_scope == "industry" and bool(industry_name)
        for row in raw_rows:
            row_industry_name = infer_industry_name(row["company_name"], row.get("industry_name"))
            if use_industry_scope and row_industry_name != industry_name:
                continue
            row["industry_name"] = row_industry_name
            rows.append(row)
        boards = []
        for indicator_name in RANKING_INDICATORS:
            metric_rows = [row for row in rows if row["indicator_name"] == indicator_name and row.get("value_num") is not None]
            if not metric_rows:
                continue
            ranked_rows = []
            selected_company_rank = None
            for index, row in enumerate(metric_rows, start=1):
                ranked_row = {
                    "rank": index,
                    "company_name": row["company_name"],
                    "value_num": _normalize_number(row.get("value_num")),
                    "unit": row.get("unit") or "",
                    "is_selected": row["company_name"] == resolved_company,
                }
                ranked_rows.append(ranked_row)
                if ranked_row["is_selected"] and selected_company_rank is None:
                    selected_company_rank = index
            boards.append(
                {
                    "indicator_name": indicator_name,
                    "unit": metric_rows[0].get("unit") or "",
                    "selected_company_rank": selected_company_rank,
                    "sample_size": len(metric_rows),
                    "rows": ranked_rows[:8],
                }
            )
        return {
            "company_name": resolved_company,
            "industry_name": industry_name or "全部行业",
            "scope_label": "同一级行业排名" if use_industry_scope else "全行业排名",
            "ranking_scope": ranking_scope,
            "report_year": resolved_year,
            "boards": boards,
        }
    finally:
        conn.close()


app = FastAPI(title="医药生物企业智能分析与决策支持系统")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTMLResponse(
        INDEX_HTML.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    return fetch_bootstrap_data()


@app.get("/api/dashboard")
def dashboard(company_name: str | None = None, report_year: int | None = None, ranking_scope: str = "industry") -> dict[str, Any]:
    return {
        "import_overview": fetch_import_dashboard(),
        "trend_overview": fetch_company_trend_dashboard(company_name),
        "ranking_overview": fetch_industry_ranking_dashboard(company_name, report_year, ranking_scope=ranking_scope),
        "alert_overview": fetch_alert_center(company_name, report_year),
        "macro_overview": fetch_macro_linkage_dashboard(company_name),
    }


@app.get("/api/profile")
def profile(company_name: str | None = None, report_year: int | None = None) -> dict[str, Any]:
    return fetch_company_profile_dashboard(company_name, report_year)


@app.get("/api/compare")
def compare(company_name: str | None = None, compare_company_name: str | None = None, report_year: int | None = None) -> dict[str, Any]:
    return fetch_compare_matrix_dashboard(company_name, compare_company_name, report_year)


@app.get("/api/timeline")
def timeline(company_name: str | None = None) -> dict[str, Any]:
    return fetch_company_timeline_dashboard(company_name)


@app.get("/api/database/catalog")
def database_catalog() -> dict[str, Any]:
    return fetch_database_catalog()


@app.get("/api/database/table")
def database_table(table_name: str, limit: int = 20) -> dict[str, Any]:
    try:
        return fetch_database_table_preview(table_name, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/data-room/catalog")
def data_room_catalog() -> dict[str, Any]:
    return fetch_data_room_catalog()


@app.get("/api/data-room/preview")
def data_room_preview(name: str, limit: int = 20) -> dict[str, Any]:
    try:
        return fetch_data_room_preview(name, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    client = create_optional_client()
    answer_client = client
    if client is not None and payload.model == "pro":
        answer_client = create_optional_client("deepseek-v4-pro")
    filters = build_filters(payload.company_name, payload.report_year, payload.industry_name)
    result = answer_query(payload.question, filters=filters, top_k=payload.top_k, client=client, history=payload.history, answer_client=answer_client)
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
    filters = build_filters(payload.company_name, payload.report_year, payload.industry_name)
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


@app.post("/api/batch-workflow")
def batch_workflow(payload: BatchWorkflowRequest) -> dict[str, Any]:
    client = create_optional_client()
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        normalized_companies = []
        for company_name in payload.company_names:
            name = (company_name or "").strip()
            if name and name not in normalized_companies:
                normalized_companies.append(name)
        if not normalized_companies:
            default_company = _get_default_company(conn, None)
            if default_company:
                normalized_companies.append(default_company)
        normalized_companies = normalized_companies[:5]
    finally:
        conn.close()
    items = []
    for company_name in normalized_companies:
        filters = build_filters(company_name, payload.report_year, payload.industry_name)
        topic = f"请为 {company_name} 生成经营质量与风险诊断报告"
        result = run_workflow(topic, filters=filters, top_k=payload.top_k, client=client)
        items.append(
            {
                "company_name": company_name,
                "topic": topic,
                "report_markdown": result.get("report_markdown", ""),
                "warnings": result.get("warnings") or [],
                "data_mode": result.get("data_mode"),
            }
        )
    return {
        "company_names": normalized_companies,
        "combined_markdown": build_batch_workflow_markdown(items),
        "items": items,
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
