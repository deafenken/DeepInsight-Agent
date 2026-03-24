from pathlib import Path

import pandas as pd
import streamlit as st

from retriever import DEFAULT_CHROMA_PATH, DEFAULT_COLLECTION, DEFAULT_DB_PATH, answer_query, create_default_client, get_collection, get_connection

st.set_page_config(page_title="企业运营分析与决策支持系统", layout="wide")


def load_filters():
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        industries = [row[0] for row in conn.execute("SELECT industry_name FROM dim_industry ORDER BY industry_name").fetchall()]
        companies = [row[0] for row in conn.execute("SELECT company_name FROM dim_company ORDER BY company_name").fetchall()]
        years = [row[0] for row in conn.execute("SELECT DISTINCT report_year FROM dim_document WHERE report_year IS NOT NULL ORDER BY report_year DESC").fetchall()]
        stats = {
            "companies": conn.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0],
            "documents": conn.execute("SELECT COUNT(*) FROM dim_document").fetchone()[0],
            "financial_facts": conn.execute("SELECT COUNT(*) FROM fact_financial_report").fetchone()[0],
            "macro_facts": conn.execute("SELECT COUNT(*) FROM fact_macro_data").fetchone()[0],
        }
        return industries, companies, years, stats
    finally:
        conn.close()


def load_chroma_stats():
    try:
        collection = get_collection(DEFAULT_CHROMA_PATH, DEFAULT_COLLECTION)
        return {"collection_name": collection.name, "chunks": collection.count()}
    except Exception as exc:
        return {"collection_name": DEFAULT_COLLECTION, "chunks": 0, "error": str(exc)}


def render_chart(chart_spec):
    if not chart_spec:
        return
    rows = chart_spec.get("rows") or []
    if not rows:
        return
    df = pd.DataFrame(rows)
    x_key = chart_spec.get("x")
    y_key = chart_spec.get("y")
    if not x_key or not y_key or x_key not in df.columns or y_key not in df.columns:
        return
    chart_df = df[[col for col in [x_key, y_key, chart_spec.get("series")] if col and col in df.columns]].copy()
    if chart_spec.get("series") and chart_spec["series"] in chart_df.columns:
        pivot = chart_df.pivot_table(index=x_key, columns=chart_spec["series"], values=y_key, aggfunc="first")
        if chart_spec.get("chart_type") == "line":
            st.line_chart(pivot)
        else:
            st.bar_chart(pivot)
        return
    chart_df = chart_df.set_index(x_key)
    if chart_spec.get("chart_type") == "line":
        st.line_chart(chart_df[y_key])
    else:
        st.bar_chart(chart_df[y_key])


def render_sources(sources):
    if not sources:
        return
    st.markdown("**参考来源与归因追溯**")
    for index, source in enumerate(sources, start=1):
        with st.container(border=True):
            st.markdown(f"**[{index}] {source['label']}**")
            if source.get("snippet"):
                st.caption(source["snippet"])


def build_sidebar():
    industries, companies, years, stats = load_filters()
    chroma_stats = load_chroma_stats()
    st.sidebar.title("控制面板")
    st.sidebar.markdown("### 数据库状态")
    st.sidebar.write(f"企业数：{stats['companies']}")
    st.sidebar.write(f"文档数：{stats['documents']}")
    st.sidebar.write(f"财务事实数：{stats['financial_facts']}")
    st.sidebar.write(f"宏观事实数：{stats['macro_facts']}")
    st.sidebar.write(f"向量集合：{chroma_stats['collection_name']}")
    st.sidebar.write(f"文本块数：{chroma_stats['chunks']}")
    if chroma_stats.get("error"):
        st.sidebar.caption(chroma_stats["error"])
    st.sidebar.markdown("### 检索筛选")
    industry = st.sidebar.selectbox("行业", ["全部"] + industries, index=0)
    company = st.sidebar.selectbox("企业", ["全部"] + companies, index=0)
    year = st.sidebar.selectbox("年份", ["全部"] + [str(item) for item in years], index=0)
    doc_type = st.sidebar.selectbox("文档类型", ["全部", "annual_report", "research_report"], index=0)
    top_k = st.sidebar.slider("向量 Top K", min_value=1, max_value=10, value=5)
    if st.sidebar.button("清空会话"):
        st.session_state.messages = []
        st.session_state.debug_items = []
    filters = {}
    if industry != "全部":
        filters["industry_name"] = industry
    if company != "全部":
        filters["company_name"] = company
    if year != "全部":
        filters["report_year"] = int(year)
    if doc_type != "全部":
        filters["doc_type"] = doc_type
    return filters, top_k


def get_client():
    if "zhipu_client" not in st.session_state:
        st.session_state.zhipu_client = create_default_client()
    return st.session_state.zhipu_client


def main():
    st.title("智能体赋能的企业运营分析与决策支持系统")
    st.caption(f"SQLite: {Path(DEFAULT_DB_PATH)} | Chroma: {Path(DEFAULT_CHROMA_PATH)}")
    filters, top_k = build_sidebar()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "debug_items" not in st.session_state:
        st.session_state.debug_items = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("chart_spec"):
                render_chart(message["chart_spec"])
            if message.get("sources"):
                render_sources(message["sources"])

    prompt = st.chat_input("输入企业运营、财务或研报分析问题")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在分析..."):
            try:
                result = answer_query(prompt, filters=filters, top_k=top_k, client=get_client())
            except Exception as exc:
                st.error(str(exc))
                st.session_state.messages.append({"role": "assistant", "content": f"执行失败：{exc}"})
                return
        st.markdown(result["answer_markdown"])
        render_chart(result.get("chart_spec"))
        render_sources(result.get("sources"))
        with st.expander("检索细节", expanded=False):
            st.write(f"Route: {result['route']}")
            if result.get("sql"):
                st.code(result["sql"], language="sql")
            if result.get("sql_rows"):
                st.dataframe(pd.DataFrame(result["sql_rows"]))
            if result.get("chunks"):
                for item in result["chunks"]:
                    meta = item.get("metadata") or {}
                    st.markdown(f"**{meta.get('source', '未知来源')} / 第{meta.get('page') or '?'}页**")
                    st.caption(item.get("text", "")[:500])
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["answer_markdown"],
                "chart_spec": result.get("chart_spec"),
                "sources": result.get("sources"),
            }
        )


if __name__ == "__main__":
    main()
