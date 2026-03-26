import pandas as pd
import streamlit as st

from deepinsight.core.retriever import answer_query, create_optional_client
from deepinsight.core.ui_common import build_sidebar, get_project_paths_caption, render_chart, render_interactive_table, render_sources

st.set_page_config(page_title="企业运营分析与决策支持系统", layout="wide")


def get_client():
    if "deepseek_client" not in st.session_state:
        st.session_state.deepseek_client = create_optional_client()
    return st.session_state.deepseek_client


def main():
    st.title("智能体赋能的企业运营分析与决策支持系统")
    st.caption(get_project_paths_caption())
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
            if message.get("warnings"):
                for warning in message["warnings"]:
                    st.caption(warning)

    prompt = st.chat_input("输入企业运营、财务或研报分析问题")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在分析..."):
            try:
                client = get_client()
                result = answer_query(prompt, filters=filters, top_k=top_k, client=client)
            except Exception as exc:
                st.error(str(exc))
                st.session_state.messages.append({"role": "assistant", "content": f"执行失败：{exc}"})
                return
        if client is None:
            st.caption("当前未配置 DEEPSEEK_API_KEY，已自动降级为本地检索摘要模式。")
        if result.get("warnings"):
            for warning in result["warnings"]:
                st.caption(warning)
        st.markdown(result["answer_markdown"])
        render_chart(result.get("chart_spec"))
        render_sources(result.get("sources"))
        with st.expander("检索细节", expanded=False):
            st.write(f"Route: {result['route']}")
            if result.get("sql"):
                st.code(result["sql"], language="sql")
            if result.get("sql_rows"):
                render_interactive_table(pd.DataFrame(result["sql_rows"]), max_rows=80, caption="悬停单元格可查看完整值。")
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
                "warnings": result.get("warnings"),
            }
        )


if __name__ == "__main__":
    main()
