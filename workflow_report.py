import json
import os
from datetime import datetime

import streamlit as st
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


MOCK_SQL_RESULT = [
    {"company_name": "ST生物", "report_year": 2023, "indicator": "营业收入", "value_num": 1280000000},
    {"company_name": "ST生物", "report_year": 2023, "indicator": "归母净利润", "value_num": 85000000},
    {"company_name": "ST生物", "report_year": 2023, "indicator": "经营活动现金流量净额", "value_num": 112000000},
]

MOCK_RAG_CHUNKS = [
    {
        "text": "公司在 2023 年继续推进主营业务结构优化，重点产品收入占比提升，营销费用率下降。",
        "metadata": {"source": "ST生物-2023年度报告.md", "page": 28, "doc_type": "annual_report"},
    },
    {
        "text": "管理层认为未来增长动力主要来自渠道下沉、新品放量以及成本控制效率改善。",
        "metadata": {"source": "ST生物-2023年度报告.md", "page": 34, "doc_type": "annual_report"},
    },
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


def plan_outline(topic):
    messages = [
        {"role": "system", "content": "你是一名资深卖方分析师，请为深度诊断报告生成结构化大纲，使用 Markdown 列表。"},
        {"role": "user", "content": f"请为主题“{topic}”生成深度诊断报告大纲。"},
    ]
    return call_deepseek(messages)


def query_financial_sql(topic):
    sql = """
    SELECT company_name, report_year, indicator, value_num
    FROM mock_financial_result
    WHERE company_name = 'ST生物' AND report_year = 2023
    ORDER BY indicator
    """.strip()
    return sql, MOCK_SQL_RESULT


def query_chroma_chunks(topic):
    return MOCK_RAG_CHUNKS


def generate_report(topic, outline, sql_rows, rag_chunks):
    payload = {
        "topic": topic,
        "outline": outline,
        "financial_data": sql_rows,
        "rag_chunks": rag_chunks,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    messages = [
        {
            "role": "system",
            "content": "你是一名顶级企业经营诊断顾问。请基于给定大纲、财务数据和检索片段，输出一份完整的 Markdown 深度诊断报告，包含结论、风险、机会和建议。",
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    return call_deepseek(messages)


def main():
    st.set_page_config(page_title="一键自动化研报工作流", layout="wide")
    st.title("一键自动化研报工作流")
    st.caption("使用串行状态机模式生成深度诊断报告")

    topic = st.text_input("报告主题", value="请为 ST生物 生成经营质量与风险诊断报告")
    if not topic:
        st.info("请输入报告主题。")
        return

    if st.button("生成深度诊断报告", type="primary"):
        report_markdown = None
        sql_text = None
        sql_rows = None
        rag_chunks = None
        outline = None
        with st.status("正在执行自动化研报工作流...", expanded=True) as status:
            try:
                st.write("步骤一：规划报告大纲")
                outline = plan_outline(topic)

                st.write("步骤二：查询关系数据库获取财务指标")
                sql_text, sql_rows = query_financial_sql(topic)

                st.write("步骤三：查询 ChromaDB 获取研报信息")
                rag_chunks = query_chroma_chunks(topic)

                st.write("步骤四：聚合信息并生成最终研报")
                report_markdown = generate_report(topic, outline, sql_rows, rag_chunks)
                status.update(label="研报生成完成", state="complete")
            except Exception as exc:
                status.update(label=f"执行失败：{exc}", state="error")
                st.error(f"研报生成失败：{exc}")
                return

        st.markdown("## 报告大纲")
        st.markdown(outline)
        st.markdown("## 最终研报")
        st.markdown(report_markdown)

        with st.expander("查看中间结果", expanded=False):
            st.markdown("### 模拟 SQL")
            st.code(sql_text, language="sql")
            st.dataframe(sql_rows)
            st.markdown("### 模拟向量检索结果")
            for chunk in rag_chunks:
                st.markdown(f"**来源：{chunk['metadata']['source']} 第{chunk['metadata']['page']}页**")
                st.caption(chunk["text"])

        st.download_button(
            label="下载 Markdown 报告",
            data=report_markdown.encode("utf-8"),
            file_name="deep_diagnostic_report.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
