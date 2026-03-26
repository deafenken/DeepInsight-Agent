import json
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI

from deepinsight.core.retriever import DEFAULT_DB_PATH, build_context_bundle, build_sources, create_optional_client, execute_sql, generate_sql, resolve_local_query_filters, retrieve_chunks
from deepinsight.core.ui_common import build_result_chips, build_sidebar, extract_metric_cards, extract_summary_card, get_project_paths_caption, render_chip_row, render_interactive_table, render_metric_cards, render_sources, render_streamed_markdown

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LOCAL_OUTLINE = """
- 一、核心结论
- 二、财务指标摘要
- 三、文档检索发现
- 四、主要风险与后续关注点
""".strip()

PREFERRED_REPORT_METRICS = [
    "营业收入",
    "归属于上市公司股东的净利润",
    "经营活动产生的现金流量净额",
    "净资产收益率",
    "总资产",
    "研发费用",
]


def get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量。")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def call_deepseek(messages, model=DEFAULT_MODEL):
    client = get_client()
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.4, stream=False)
    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message or not (choice.message.content or "").strip():
        raise RuntimeError("DeepSeek 未返回有效内容。")
    return choice.message.content


def get_workflow_data_mode(sql_result, rag_result, client):
    has_sql = bool(sql_result.get("sql_rows"))
    has_rag = bool(rag_result.get("chunks"))
    if has_sql and has_rag:
        return "live" if client else "degraded"
    if has_sql or has_rag:
        return "partial" if client else "degraded"
    return "unavailable"


def render_data_mode_banner(data_mode, warnings=None, client=None):
    if data_mode == "live":
        st.success("当前工作流页已连接真实 SQLite / Chroma 检索。")
    elif data_mode == "partial":
        st.warning("当前工作流页仅部分接入真实检索，部分步骤不可用。")
    elif data_mode == "degraded":
        st.warning("当前工作流页处于降级模式：未配置 DeepSeek 或部分本地检索不可用。")
    else:
        st.error("当前工作流页未取得可用检索结果，请检查筛选条件、数据库或向量库。")
    if client is None:
        st.caption("未配置 DEEPSEEK_API_KEY 时，将优先使用本地检索与结构化降级输出。")
    for warning in warnings or []:
        st.caption(warning)


def plan_outline(topic, client=None):
    if client is None:
        return LOCAL_OUTLINE
    messages = [
        {"role": "system", "content": "你是一名资深卖方分析师，请为深度诊断报告生成结构化大纲，使用 Markdown 列表。"},
        {"role": "user", "content": f"请为主题“{topic}”生成深度诊断报告大纲。"},
    ]
    return call_deepseek(messages)


def query_financial_sql(topic, filters=None, client=None):
    warnings = []
    try:
        sql_text = generate_sql(topic, filters=filters, client=client)
        sql_rows = execute_sql(sql_text)
        status = "success" if sql_rows else "empty"
        return {"sql_text": sql_text, "sql_rows": sql_rows, "warnings": warnings, "status": status}
    except Exception as exc:
        warnings.append(f"SQL检索不可用：{exc}")
        return {"sql_text": None, "sql_rows": [], "warnings": warnings, "status": "unavailable"}


def build_workflow_retrieval_query(topic, resolved_filters):
    company_name = resolved_filters.get("company_name")
    report_year = resolved_filters.get("report_year")
    prefixes = []
    if company_name and company_name not in (topic or ""):
        prefixes.append(company_name)
    if report_year and str(report_year) not in (topic or ""):
        prefixes.append(f"{report_year}年")
    if company_name or report_year:
        prefixes.extend(["年度报告", "经营情况", "风险提示", "主营业务"])
    prefix = " ".join(prefixes).strip()
    return f"{prefix} {topic}".strip() if prefix else topic


def query_chroma_chunks(topic, filters=None, top_k=5, client=None):
    warnings = []
    try:
        resolved_filters = resolve_local_query_filters(topic, filters, db_path=DEFAULT_DB_PATH) if not client else (filters or {})
        retrieval_query = build_workflow_retrieval_query(topic, resolved_filters)
        chunks = retrieve_chunks(retrieval_query, filters=resolved_filters, top_k=top_k, client=client)
        status = "success" if chunks else "empty"
        return {"chunks": chunks, "warnings": warnings, "status": status}
    except Exception as exc:
        warnings.append(f"向量检索不可用：{exc}")
        return {"chunks": [], "warnings": warnings, "status": "unavailable"}


def build_local_report(topic, outline, sql_result, rag_result, sources, warnings, data_mode):
    sql_rows = sql_result.get("sql_rows") or []
    rag_chunks = rag_result.get("chunks") or []
    company_name = next((row.get("company_name") for row in sql_rows if row.get("company_name")), "目标企业")

    def normalize_unit(value, unit):
        if unit == "%" and isinstance(value, (int, float)) and abs(value) > 1000:
            return ""
        return unit or ""

    def format_value(value, unit=None):
        if value is None:
            return "暂无披露"
        normalized_unit = normalize_unit(value, unit)
        if isinstance(value, (int, float)):
            abs_value = abs(value)
            if normalized_unit == "%":
                rendered = f"{value:.2f}".rstrip("0").rstrip(".")
            elif abs_value >= 100000000:
                rendered = f"{value / 100000000:.2f}".rstrip("0").rstrip(".")
                normalized_unit = "亿元"
            elif abs_value >= 10000 and normalized_unit in {"元", ""}:
                rendered = f"{value / 10000:.2f}".rstrip("0").rstrip(".")
                normalized_unit = "万元" if normalized_unit == "元" else normalized_unit
            else:
                rendered = f"{value:.2f}".rstrip("0").rstrip(".")
            return f"{rendered}{normalized_unit}"
        return f"{value}{normalized_unit}"

    def pick_metric_pair(rows, indicator_name):
        metric_rows = [row for row in rows if row.get("indicator_name") == indicator_name]
        if not metric_rows:
            return None, None

        def score(row):
            value = row.get("value_num")
            unit = row.get("unit")
            unit_score = 2 if unit == "元" else (1 if unit not in {"%", None} else 0)
            magnitude_score = abs(value) if isinstance(value, (int, float)) else 0
            page_score = -(row.get("source_page") or 9999)
            return (1 if row.get("value_role") == "current" else 0, unit_score, magnitude_score, page_score)

        current_candidates = [row for row in metric_rows if row.get("value_role") == "current"] or metric_rows
        current = max(current_candidates, key=score)
        historical_candidates = [
            row for row in metric_rows
            if row is not current and row.get("value_role") == "historical" and row.get("value_num") is not None
        ]
        historical = max(historical_candidates, key=score) if historical_candidates else None
        return current, historical

    def build_metric_line(indicator_name):
        current, historical = pick_metric_pair(sql_rows, indicator_name)
        if not current:
            return None, None
        current_value = current.get("value_num") if current.get("value_num") is not None else current.get("value_text")
        unit = current.get("unit")
        line = f"- {indicator_name}：{format_value(current_value, unit)}"
        direction = None
        if historical and isinstance(current_value, (int, float)) and isinstance(historical.get("value_num"), (int, float)):
            delta = current_value - historical["value_num"]
            direction = "上升" if delta > 0 else ("下降" if delta < 0 else "基本持平")
            line += f"，较上期{direction}"
        if current.get("source_page"):
            line += f"（第{current['source_page']}页）"
        return line, direction

    summary_bits = []
    metric_lines = []
    for metric_name in PREFERRED_REPORT_METRICS:
        metric_line, direction = build_metric_line(metric_name)
        if not metric_line:
            continue
        metric_lines.append(metric_line)
        if direction and metric_name in {"营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "净资产收益率"}:
            summary_bits.append(f"{metric_name}{direction}")

    evidence_lines = []
    for chunk in rag_chunks[:3]:
        meta = chunk.get("metadata") or {}
        snippet = re.sub(r"\s+", " ", chunk.get("text", "")).strip()[:160]
        evidence_lines.append(f"- {meta.get('source', '未知来源')} 第{meta.get('page') or '?'}页：{snippet}")

    sections = [f"## 工作流结果（{data_mode}）", "", f"**主题**：{topic}"]
    sections.extend(
        [
            "",
            "### 摘要判断",
            (
                f"{company_name}当前呈现出"
                + ("、".join(summary_bits[:3]) if summary_bits else "经营表现需要结合更多样本继续判断")
                + "的特征。该报告基于本地结构化财务事实与年报原文片段生成，适合作为比赛演示和快速诊断入口。"
            ),
        ]
    )
    if metric_lines:
        sections.extend(["", "### 关键指标"])
        sections.extend(metric_lines[:5])
    if evidence_lines:
        sections.extend(["", "### 文档证据"])
        sections.extend(evidence_lines)
    sections.extend(["", "### 风险与建议"])
    if warnings:
        sections.extend([f"- {warning}" for warning in warnings[:3]])
    else:
        sections.extend(
            [
                "- 建议继续结合多期财务数据核验经营质量变化，避免单年结论失真。",
                "- 建议重点查看管理层讨论与分析、重大风险提示和现金流相关附注页。",
            ]
        )
    sections.extend(["", "### 证据边界"])
    sections.append("- 当前为本地降级研报，未调用大模型深度改写，因此正文更偏证据驱动而非完整卖方文风。")
    if sources:
        sections.extend(["", "### 参考来源"])
        sections.extend([f"- {source['label']}" for source in sources[:8]])
    return "\n".join(sections)


def generate_report(topic, outline, sql_result, rag_result, sources, warnings, data_mode, client=None):
    if client is None:
        return build_local_report(topic, outline, sql_result, rag_result, sources, warnings, data_mode)
    payload = {
        "topic": topic,
        "outline": outline,
        "sql_text": sql_result.get("sql_text"),
        "financial_data": sql_result.get("sql_rows") or [],
        "rag_chunks": rag_result.get("chunks") or [],
        "sources": sources,
        "warnings": warnings,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_mode": data_mode,
    }
    messages = [
        {
            "role": "system",
            "content": "你是一名顶级企业经营诊断顾问。请基于给定大纲、财务数据和检索片段，输出一份完整的 Markdown 深度诊断报告，包含结论、风险、机会和建议。当数据不完整时必须明确说明证据边界，不要补造。",
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return call_deepseek(messages)


def run_workflow(topic, filters=None, top_k=5, client=None):
    resolved_filters = resolve_local_query_filters(topic, filters, db_path=DEFAULT_DB_PATH) if not client else (filters or {})
    outline = plan_outline(topic, client=client)
    sql_result = query_financial_sql(topic, filters=resolved_filters, client=client)
    rag_result = query_chroma_chunks(topic, filters=resolved_filters, top_k=top_k, client=client)
    warnings = [*sql_result.get("warnings", []), *rag_result.get("warnings", [])]
    sources = build_sources(sql_result.get("sql_rows") or [], rag_result.get("chunks") or [])
    context = build_context_bundle(sql_result.get("sql_rows") or [], rag_result.get("chunks") or [])
    data_mode = get_workflow_data_mode(sql_result, rag_result, client)
    report_markdown = generate_report(topic, outline, sql_result, rag_result, sources, warnings, data_mode, client=client)
    return {
        "outline": outline,
        "sql": sql_result.get("sql_text"),
        "sql_rows": sql_result.get("sql_rows") or [],
        "rag_chunks": rag_result.get("chunks") or [],
        "sources": sources,
        "warnings": warnings,
        "context": context.get("text") or "",
        "data_mode": data_mode,
        "client": client,
        "report_markdown": report_markdown,
    }


def render_workflow_result(result):
    render_data_mode_banner(result.get("data_mode"), result.get("warnings"), result.get("client"))
    st.markdown("## 最终研报")
    chips = build_result_chips(
        sql_rows=result.get("sql_rows"),
        macro_rows=[],
        sources=result.get("sources"),
        route="hybrid" if result.get("sql_rows") and result.get("rag_chunks") else ("sql" if result.get("sql_rows") else "vector"),
    )
    summary_card = extract_summary_card(result["report_markdown"])
    metric_cards = extract_metric_cards(result["report_markdown"])
    render_chip_row(chips)
    if summary_card:
        st.markdown(
            f"""
            <div style="padding:16px 18px; margin-bottom:14px; border-radius:18px; background:#ffffff; border:1px solid rgba(15,23,42,0.08); box-shadow:0 10px 24px rgba(15,23,42,0.06);">
              <div style="font-size:0.9rem; color:#6b7280; margin-bottom:6px;">{summary_card['title']}</div>
              <div style="font-size:1rem; font-weight:700; line-height:1.6;">{summary_card['body']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    render_metric_cards(metric_cards)
    render_streamed_markdown(result["report_markdown"])
    if result.get("sources"):
        render_sources(result["sources"])
    with st.expander("查看中间结果", expanded=False):
        st.markdown("### SQL")
        if result.get("sql"):
            st.code(result["sql"], language="sql")
        else:
            st.caption("本次未生成可执行 SQL。")
        if result.get("sql_rows"):
            render_interactive_table(pd.DataFrame(result["sql_rows"]), max_rows=80, caption="悬停单元格可查看完整值。")
        else:
            st.caption("本次未取得 SQL 结果。")
        st.markdown("### 向量检索结果")
        if result.get("rag_chunks"):
            for chunk in result["rag_chunks"]:
                st.markdown(f"**来源：{chunk['metadata'].get('source', '未知来源')} 第{chunk['metadata'].get('page') or '?'}页**")
                st.caption(chunk.get("text", ""))
        else:
            st.caption("本次未取得向量检索结果。")
        if result.get("warnings"):
            st.markdown("### Warnings")
            for warning in result["warnings"]:
                st.caption(warning)


def main():
    st.set_page_config(page_title="一键自动化研报工作流", layout="wide")
    st.title("一键自动化研报工作流")
    st.caption("使用串行状态机模式生成深度诊断报告")
    st.caption(get_project_paths_caption())
    filters, top_k = build_sidebar()
    client = create_optional_client()

    topic = st.text_input("报告主题", value="请为 ST生物 生成经营质量与风险诊断报告")
    if not topic:
        st.info("请输入报告主题。")
        return

    render_data_mode_banner("degraded" if client is None else "partial", client=client)

    if st.button("生成深度诊断报告", type="primary"):
        with st.status("正在执行自动化研报工作流...", expanded=True) as status:
            try:
                st.write("步骤一：理解报告主题")
                st.write("步骤二：执行真实 SQL 检索")
                st.write("步骤三：执行真实向量检索")
                st.write("步骤四：聚合证据并生成最终研报")
                st.session_state.workflow_result = run_workflow(topic, filters=filters, top_k=top_k, client=client)
                status.update(label="研报生成完成", state="complete")
            except Exception as exc:
                status.update(label=f"执行失败：{exc}", state="error")
                st.error(f"研报生成失败：{exc}")
                return

    result = st.session_state.get("workflow_result")
    if result:
        render_workflow_result(result)
        st.download_button(
            label="下载 Markdown 报告",
            data=result["report_markdown"].encode("utf-8"),
            file_name="deep_diagnostic_report.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
