from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from agent_tools import run_advanced_analysis, tool_get_equity_penetration, tool_get_innovation_index, tool_get_risk_radar
from app import build_sidebar, get_client, load_chroma_stats, load_filters, render_sources
from retriever import DEFAULT_CHROMA_PATH, DEFAULT_DB_PATH

st.set_page_config(page_title="企业全景画像与高级分析", layout="wide")


def render_viz_blocks(viz_blocks):
    for block in viz_blocks or []:
        st.markdown(f"### {block['title']}")
        st_echarts(options=block["option"], height="480px")


def render_debug_details(tool_results):
    equity = tool_results.get("equity", {})
    risk = tool_results.get("risk", {})
    innovation = tool_results.get("innovation", {})
    with st.expander("股权穿透明细", expanded=False):
        st.json(equity)
    with st.expander("风险雷达明细", expanded=False):
        st.json(risk)
    with st.expander("创新指数明细", expanded=False):
        st.json(innovation)


def render_radar_summary(company_name):
    risk_data = tool_get_risk_radar(company_name, include_subsidiaries=True)
    innovation_data = tool_get_innovation_index(company_name)
    dimensions = {
        "财务健康度": 70,
        "创新能力": min(100, int(innovation_data["dimensions"].get("平均专利评分", 0) or 0)),
        "市场占有率": 60,
        "合规风险": max(10, 100 - risk_data["dimensions"].get("高风险事件数", 0) * 15 - risk_data["dimensions"].get("风险事件总数", 0) * 3),
        "供应链稳定性": 65,
    }
    option = {
        "tooltip": {},
        "radar": {"indicator": [{"name": key, "max": 100} for key in dimensions.keys()]},
        "series": [{"type": "radar", "data": [{"name": company_name, "value": list(dimensions.values())}]}],
    }
    st_echarts(options=option, height="420px")
    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(pd.DataFrame(risk_data.get("details") or []))
    with col2:
        st.dataframe(pd.DataFrame(innovation_data.get("details") or []))


def render_equity_tab(default_company):
    if not default_company:
        st.info("请先在侧边栏选择企业。")
        return
    equity_data = tool_get_equity_penetration(default_company, max_depth=2)
    nodes = []
    category_map = {"root": 0, "company": 1, "person": 2}
    for node in equity_data["nodes"]:
        nodes.append(
            {
                "name": node["name"],
                "value": node["level"],
                "category": category_map.get(node["type"], 1),
                "symbolSize": 42 if node["type"] == "root" else 26,
            }
        )
    links = []
    id_to_name = {node["id"]: node["name"] for node in equity_data["nodes"]}
    for edge in equity_data["edges"]:
        links.append(
            {
                "source": id_to_name[edge["source"]],
                "target": id_to_name[edge["target"]],
                "value": edge["ratio"],
                "label": {"show": True, "formatter": f"{edge['ratio']}%"},
            }
        )
    option = {
        "tooltip": {},
        "legend": [{"data": ["核心公司", "公司", "个人"]}],
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "roam": True,
                "label": {"show": True},
                "categories": [{"name": "核心公司"}, {"name": "公司"}, {"name": "个人"}],
                "data": nodes,
                "links": links,
                "force": {"repulsion": 300, "edgeLength": [90, 200]},
                "lineStyle": {"curveness": 0.15},
            }
        ],
    }
    st_echarts(options=option, height="620px")
    st.dataframe(pd.DataFrame(equity_data["edges"]))


def main():
    st.title("企业全景画像与高级分析面板")
    st.caption(f"SQLite: {Path(DEFAULT_DB_PATH)} | Chroma: {Path(DEFAULT_CHROMA_PATH)}")
    filters, top_k = build_sidebar()
    _, companies, _, stats = load_filters()
    chroma_stats = load_chroma_stats()
    selected_company = filters.get("company_name") or (companies[0] if companies else None)

    st.markdown(
        f"**数据库概览**：企业数 {stats['companies']}，文档数 {stats['documents']}，财务事实数 {stats['financial_facts']}，"
        f"宏观事实数 {stats['macro_facts']}，文本块数 {chroma_stats['chunks']}"
    )

    if "advanced_messages" not in st.session_state:
        st.session_state.advanced_messages = []

    tab_chat, tab_graph, tab_radar, tab_debug = st.tabs(["智能问答", "企业关系图谱", "风险与创新雷达", "调试明细"])

    with tab_chat:
        for message in st.session_state.advanced_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("viz_blocks"):
                    render_viz_blocks(message["viz_blocks"])
                if message.get("sources"):
                    render_sources(message["sources"])
        prompt = st.chat_input("输入高级图谱、风险或创新分析问题")
        if prompt:
            st.session_state.advanced_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("正在执行高级分析..."):
                    company_name = selected_company
                    if not company_name:
                        st.error("当前没有可用企业，请先导入数据。")
                        return
                    result = run_advanced_analysis(prompt, company_name=company_name, client=get_client())
                st.markdown(result["answer_markdown"])
                render_viz_blocks(result.get("viz_blocks"))
                render_sources(result.get("sources"))
                st.session_state.advanced_messages.append(
                    {
                        "role": "assistant",
                        "content": result["answer_markdown"],
                        "viz_blocks": result.get("viz_blocks"),
                        "sources": result.get("sources"),
                        "tool_results": result.get("tool_results"),
                    }
                )

    with tab_graph:
        render_equity_tab(selected_company)

    with tab_radar:
        if selected_company:
            render_radar_summary(selected_company)
        else:
            st.info("请先在侧边栏选择企业。")

    with tab_debug:
        if st.session_state.advanced_messages:
            last_assistant = next((msg for msg in reversed(st.session_state.advanced_messages) if msg["role"] == "assistant"), None)
            if last_assistant and last_assistant.get("tool_results"):
                render_debug_details(last_assistant["tool_results"])
            else:
                st.info("先在智能问答中触发一次高级工具查询。")
        else:
            st.info("先在智能问答中触发一次高级工具查询。")


if __name__ == "__main__":
    main()
