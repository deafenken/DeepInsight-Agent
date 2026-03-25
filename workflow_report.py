import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI

from retriever import build_context_bundle, build_sources, create_optional_client, execute_sql, generate_sql, retrieve_chunks
from ui_common import build_sidebar, get_project_paths_caption, render_sources

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LOCAL_OUTLINE = """
- 一、核心结论
- 二、财务指标摘要
- 三、文档检索发现
- 四、主要风险与后续关注点
""".strip()


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


def query_chroma_chunks(topic, filters=None, top_k=5, client=None):
    warnings = []
    try:
        chunks = retrieve_chunks(topic, filters=filters, top_k=top_k, client=client)
        status = "success" if chunks else "empty"
        return {"chunks": chunks, "warnings": warnings, "status": status}
    except Exception as exc:
        warnings.append(f"向量检索不可用：{exc}")
        return {"chunks": [], "warnings": warnings, "status": "unavailable"}


def build_local_report(topic, outline, sql_result, rag_result, sources, warnings, data_mode):
    sections = [f"## 工作流结果（{data_mode}）", "", f"**主题**：{topic}", "", "## 报告大纲", outline or LOCAL_OUTLINE]
    if sql_result.get("sql_rows"):
        sections.extend(["", "## 财务指标摘要"])
        for row in sql_result["sql_rows"][:10]:
            metric = row.get("indicator_name") or row.get("indicator") or "指标"
            value = row.get("value_num") if row.get("value_num") is not None else row.get("value_text")
            sections.append(f"- {metric}：{value}")
    if rag_result.get("chunks"):
        sections.extend(["", "## 文档检索发现"])
        for chunk in rag_result["chunks"][:5]:
            meta = chunk.get("metadata") or {}
            sections.append(f"- {meta.get('source', '未知来源')} 第{meta.get('page') or '?'}页：{chunk.get('text', '')[:140]}")
    if warnings:
        sections.extend(["", "## 限制与告警"])
        sections.extend([f"- {warning}" for warning in warnings])
    if sources:
        sections.extend(["", "## 参考来源"])
        sections.extend([f"- {source['label']}" for source in sources[:10]])
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
    outline = plan_outline(topic, client=client)
    sql_result = query_financial_sql(topic, filters=filters, client=client)
    rag_result = query_chroma_chunks(topic, filters=filters, top_k=top_k, client=client)
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
    st.markdown("## 报告大纲")
    st.markdown(result["outline"])
    st.markdown("## 最终研报")
    st.markdown(result["report_markdown"])
    if result.get("sources"):
        render_sources(result["sources"])
    with st.expander("查看中间结果", expanded=False):
        st.markdown("### SQL")
        if result.get("sql"):
            st.code(result["sql"], language="sql")
        else:
            st.caption("本次未生成可执行 SQL。")
        if result.get("sql_rows"):
            st.dataframe(pd.DataFrame(result["sql_rows"]))
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
                st.write("步骤一：规划报告大纲")
                st.write("步骤二：执行真实 SQL 检索")
                st.write("步骤三：执行真实向量检索")
                st.write("步骤四：聚合信息并生成最终研报")
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
