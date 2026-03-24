import json
import os

import streamlit as st
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
REASONER_MODEL = "deepseek-reasoner"
MOCK_SQL = """
SELECT company_name, report_year, indicator_name, value_num
FROM fact_financial_report
WHERE company_name = 'ST生物' AND report_year = 2023
ORDER BY indicator_name
""".strip()
MOCK_CHUNKS = [
    {
        "text": "2023 年公司持续推进产品结构优化，主营业务收入保持增长，管理层预计未来两年仍将以核心产品放量为主线。",
        "metadata": {"source": "ST生物-2023年度报告.md", "page": 28, "doc_type": "annual_report", "company_name": "ST生物"},
    },
    {
        "text": "公司提示未来仍需关注渠道竞争加剧、原材料价格波动和研发投入回收周期拉长等经营风险。",
        "metadata": {"source": "ST生物-2023年度报告.md", "page": 34, "doc_type": "annual_report", "company_name": "ST生物"},
    },
]
MOCK_REASONING = """
1. 先读取 SQL 结果中的关键财务指标，判断营收、利润和现金流趋势。
2. 再结合 RAG 原文切片，识别管理层提到的增长动因与潜在风险。
3. 最终输出兼顾结论、依据与风险提示，确保每一条判断都能追溯到结构化数据或原文片段。
""".strip()
MOCK_ANSWER = """
## ST生物 2023 年经营诊断

- 公司在 2023 年呈现出**经营质量稳中改善**的特征。
- 从财务指标看，营收与经营现金流表现较稳，说明主营业务仍具备一定韧性。
- 从原文切片看，管理层将增长动力归因于产品结构优化与核心产品放量，但也提示了渠道竞争和成本波动风险。

**结论**：这是一家具备一定改善趋势、但仍需持续观察风险传导的企业。
""".strip()


def get_reasoning_content(response):
    try:
        message = response.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content:
            return reasoning_content
        payload = response.model_dump()
        return payload.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "模型未返回 reasoning_content。")
    except Exception:
        return "模型未返回 reasoning_content。"


def get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量。")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def call_reasoner_example(prompt):
    client = get_client()
    response = client.chat.completions.create(
        model=REASONER_MODEL,
        messages=[
            {"role": "system", "content": "你是一个严谨的企业白盒分析助手。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        stream=False,
    )
    message = response.choices[0].message if response.choices else None
    return {
        "content": (message.content if message else "") or "",
        "reasoning_content": get_reasoning_content(response),
        "raw": response.model_dump(),
    }


def main():
    st.set_page_config(page_title="白盒溯源对话界面", layout="wide")
    st.title("极致白盒化溯源前端")
    st.caption("直接运行即可看到 SQL、RAG 和思考链三层解释面板")

    with st.chat_message("user"):
        st.markdown("请分析 ST生物 2023 年的经营质量，并告诉我依据是什么。")

    with st.chat_message("assistant"):
        st.markdown(MOCK_ANSWER)

        with st.expander("📊 执行的 SQL 语句", expanded=False):
            st.code(MOCK_SQL, language="sql")

        with st.expander("📄 RAG 原文切片", expanded=False):
            for index, chunk in enumerate(MOCK_CHUNKS, start=1):
                meta = chunk["metadata"]
                st.markdown(f"**[{index}] {meta['source']} / 第 {meta['page']} 页 / {meta['doc_type']}**")
                st.caption(json.dumps(meta, ensure_ascii=False, indent=2))
                st.markdown(chunk["text"])
                st.divider()

        with st.expander("🔍 DeepSeek 思考链", expanded=True):
            st.markdown(MOCK_REASONING)
            st.markdown("### 真实接口提取方式")
            st.code(
                """
from openai import OpenAI

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url='https://api.deepseek.com')
response = client.chat.completions.create(
    model='deepseek-reasoner',
    messages=[
        {'role': 'system', 'content': '你是一个严谨的企业白盒分析助手。'},
        {'role': 'user', 'content': '请分析 ST生物 的经营质量。'}
    ]
)

reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
if reasoning_content is None:
    reasoning_content = response.model_dump().get('choices', [{}])[0].get('message', {}).get('reasoning_content')
                """.strip(),
                language="python",
            )

    st.markdown("## 可选：真实 DeepSeek-Reasoner 调用测试")
    if st.button("调用真实 Reasoner 示例"):
        try:
            result = call_reasoner_example("请用审慎、可追溯的方式分析 ST生物 2023 年经营质量。")
            st.markdown("### 模型回复")
            st.markdown(result["content"] or "模型未返回正文内容。")
            st.markdown("### reasoning_content")
            st.markdown(result["reasoning_content"] or "模型未返回 reasoning_content。")
        except Exception as exc:
            st.error(f"调用失败：{exc}")


if __name__ == "__main__":
    main()
