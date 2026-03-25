import os
from pathlib import Path

import pandas as pd
import streamlit as st
from openai import OpenAI

from agent_tools import run_advanced_analysis
from ui_common import load_chroma_stats, load_filters, render_chart, render_echarts, render_sources
from app_persona import ROLE_PROMPTS
from cache_tools import SemanticCache
from retriever import DEFAULT_CHROMA_PATH, DEFAULT_DB_PATH, answer_query, create_default_client
from workflow_report import render_workflow_result, run_workflow
from app_whitebox import MOCK_ANSWER, MOCK_CHUNKS, MOCK_REASONING, MOCK_SQL, get_reasoning_content

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
REASONER_MODEL = "deepseek-reasoner"


@st.cache_resource(show_spinner=False)
def get_openai_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量。")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


@st.cache_resource(show_spinner=False)
def get_semantic_cache():
    try:
        return SemanticCache()
    except Exception:
        return None


def inject_apple_ui():
    st.markdown(
        """
        <style>
        :root {
          --bg: #F5F5F7;
          --card: rgba(255,255,255,0.78);
          --card-strong: rgba(255,255,255,0.88);
          --text: #1d1d1f;
          --muted: #86868b;
          --line: rgba(255,255,255,0.58);
          --line-dark: rgba(0,0,0,0.08);
          --blue: #0071e3;
          --blue-glow: rgba(0,113,227,0.24);
          --secondary: rgba(0,0,0,0.055);
          --radius: 24px;
          --shadow: 0 10px 40px rgba(15, 23, 42, 0.08);
          --spring: cubic-bezier(0.25, 1, 0.5, 1);
        }

        html, body, [data-testid="stAppViewContainer"] {
          background: var(--bg);
          color: var(--text);
          font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "PingFang SC", "Helvetica Neue", sans-serif;
        }

        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at 12% 18%, rgba(162,210,255,0.38), transparent 34%),
            radial-gradient(circle at 88% 10%, rgba(200,180,255,0.30), transparent 32%),
            radial-gradient(circle at 76% 82%, rgba(162,210,255,0.20), transparent 28%),
            #F5F5F7;
        }

        [data-testid="stAppViewContainer"]::before,
        [data-testid="stAppViewContainer"]::after {
          content: "";
          position: fixed;
          width: 56vw;
          height: 56vw;
          border-radius: 999px;
          filter: blur(88px);
          z-index: 0;
          pointer-events: none;
          opacity: 0.85;
          animation: auroraFloat 18s var(--spring) infinite alternate;
        }

        [data-testid="stAppViewContainer"]::before {
          top: -14vw;
          left: -10vw;
          background: radial-gradient(circle, rgba(162,210,255,0.40) 0%, rgba(162,210,255,0.12) 45%, transparent 72%);
        }

        [data-testid="stAppViewContainer"]::after {
          right: -12vw;
          top: 18vh;
          background: radial-gradient(circle, rgba(200,180,255,0.32) 0%, rgba(200,180,255,0.10) 48%, transparent 74%);
          animation-delay: 2s;
        }

        @keyframes auroraFloat {
          0% { transform: translate3d(0, 0, 0) scale(1); }
          100% { transform: translate3d(2vw, 3vh, 0) scale(1.06); }
        }

        @keyframes fadeInUp {
          0% { opacity: 0; transform: translate3d(0, 18px, 0); }
          100% { opacity: 1; transform: translate3d(0, 0, 0); }
        }

        .block-container {
          max-width: 1120px;
          padding-top: 2rem;
          padding-bottom: 3rem;
          position: relative;
          z-index: 2;
          animation: fadeInUp 0.7s var(--spring);
        }

        [data-testid="stSidebar"] {
          background: rgba(255,255,255,0.74);
          backdrop-filter: blur(24px);
          border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] > div:first-child {
          background: transparent;
        }

        h1, h2, h3 {
          color: var(--text);
          letter-spacing: -0.02em;
        }

        h1 {
          font-weight: 700;
          font-size: clamp(2.4rem, 4vw, 4.2rem);
          line-height: 1.02;
          margin-bottom: 0.3rem;
        }

        h2 {
          font-weight: 700;
          font-size: 1.35rem;
        }

        p, li, label, span, .stMarkdown {
          color: var(--text);
        }

        [data-testid="stCaptionContainer"] p,
        .apple-muted,
        .st-emotion-cache-10trblm,
        .st-emotion-cache-1wivap2 {
          color: var(--muted) !important;
        }

        .apple-shell {
          display: grid;
          gap: 28px;
        }

        .apple-hero,
        .apple-card,
        [data-testid="stChatMessage"],
        [data-testid="stExpander"],
        .stCodeBlock,
        .stDataFrame,
        div[data-testid="stMetric"] {
          background: var(--card);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid var(--line);
          border-radius: var(--radius);
          box-shadow: var(--shadow);
        }

        .apple-hero {
          padding: 34px 34px 30px 34px;
          overflow: hidden;
          position: relative;
        }

        .apple-hero::after {
          content: "";
          position: absolute;
          inset: auto -20% -56% auto;
          width: 380px;
          height: 380px;
          border-radius: 999px;
          background: radial-gradient(circle, rgba(162,210,255,0.34), transparent 68%);
          filter: blur(22px);
          pointer-events: none;
        }

        .apple-bento {
          display: grid;
          grid-template-columns: repeat(12, minmax(0, 1fr));
          gap: 24px;
          margin: 20px 0 10px;
        }

        .apple-stat {
          grid-column: span 3;
          padding: 22px 22px 18px;
          min-height: 126px;
          transition: transform .36s var(--spring), box-shadow .36s var(--spring), filter .36s var(--spring);
          animation: fadeInUp 0.72s var(--spring);
        }

        .apple-stat:hover,
        .apple-section:hover,
        [data-testid="stChatMessage"]:hover,
        [data-testid="stExpander"]:hover {
          transform: scale(1.02);
          filter: brightness(1.02);
        }

        .apple-stat-label {
          font-size: 0.92rem;
          color: var(--muted);
          margin-bottom: 10px;
        }

        .apple-stat-value {
          font-size: clamp(1.8rem, 2vw, 2.4rem);
          line-height: 1;
          font-weight: 700;
          letter-spacing: -0.03em;
          margin-bottom: 12px;
        }

        .apple-stat-meta {
          font-size: 0.9rem;
          color: var(--muted);
        }

        .apple-section {
          padding: 24px 24px 18px;
          margin-top: 12px;
          transition: transform .36s var(--spring), box-shadow .36s var(--spring), filter .36s var(--spring);
          animation: fadeInUp 0.82s var(--spring);
        }

        .apple-section-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
          margin-bottom: 14px;
        }

        .apple-section-title {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .apple-icon {
          width: 42px;
          height: 42px;
          border-radius: 16px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(242,242,247,0.94));
          border: 1px solid rgba(255,255,255,0.65);
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
          font-size: 1.15rem;
        }

        .apple-section-desc {
          color: var(--muted);
          font-size: 0.96rem;
          margin-top: 2px;
        }

        button[kind="primary"], .stButton > button {
          border-radius: 999px !important;
          min-height: 2.85rem;
          padding: 0.68rem 1.15rem;
          font-weight: 600;
          border: 1px solid rgba(255,255,255,0.65) !important;
          transition: transform .28s var(--spring), filter .28s var(--spring), box-shadow .28s var(--spring) !important;
        }

        button[kind="primary"] {
          background: linear-gradient(180deg, #0a84ff, #0071e3) !important;
          color: white !important;
          box-shadow: 0 10px 24px rgba(0,113,227,0.22);
        }

        button[kind="secondary"], .stDownloadButton > button {
          background: #E5E5EA !important;
          color: #1d1d1f !important;
          box-shadow: none !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
          transform: scale(1.02);
          filter: brightness(1.03);
        }

        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea,
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
          background: #F2F2F7 !important;
          border: 1px solid rgba(255,255,255,0.48) !important;
          color: var(--text) !important;
          border-radius: 18px !important;
          box-shadow: none !important;
        }

        .stTextInput input:focus,
        .stNumberInput input:focus,
        .stTextArea textarea:focus {
          background: rgba(255,255,255,0.96) !important;
          border-color: rgba(0,113,227,0.36) !important;
          box-shadow: 0 0 0 4px rgba(0,113,227,0.12) !important;
        }

        [data-baseweb="tab-list"] {
          gap: 12px;
          padding: 8px;
          background: rgba(255,255,255,0.62);
          border-radius: 999px;
          border: 1px solid var(--line);
          backdrop-filter: blur(18px);
        }

        button[data-baseweb="tab"] {
          border-radius: 999px !important;
          padding: 10px 18px !important;
          background: transparent !important;
          transition: all .28s var(--spring);
        }

        button[data-baseweb="tab"][aria-selected="true"] {
          background: rgba(255,255,255,0.92) !important;
          box-shadow: 0 8px 18px rgba(15,23,42,0.08);
        }

        [data-testid="stChatMessage"] {
          padding: 18px 18px 10px;
          margin-bottom: 18px;
          animation: fadeInUp 0.56s var(--spring);
        }

        [data-testid="stExpander"] {
          overflow: hidden;
          margin-top: 14px;
          animation: fadeInUp 0.62s var(--spring);
        }

        [data-testid="stExpander"] details summary {
          padding: 4px 8px;
        }

        .stCodeBlock, .stDataFrame {
          padding: 4px;
        }

        .st-emotion-cache-1r6slb0, .st-emotion-cache-1v0mbdj, .st-emotion-cache-13ln4jf {
          border-radius: var(--radius) !important;
        }

        @media (max-width: 1100px) {
          .apple-stat { grid-column: span 6; }
        }

        @media (max-width: 720px) {
          .apple-bento { grid-template-columns: 1fr; }
          .apple-stat { grid-column: span 1; }
          .apple-hero { padding: 26px 22px 22px; }
          h1 { font-size: 2.3rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_section(stats, chroma_stats):
    st.markdown(
        f"""
        <div class="apple-shell">
          <section class="apple-hero">
            <div class="apple-section-title">
              <div class="apple-icon">􀇵</div>
              <div>
                <div class="apple-muted">Enterprise Intelligence OS</div>
                <h1>智能体赋能的企业运营分析与决策支持统一系统</h1>
                <div class="apple-section-desc">以 Bento Grid 组织问答、图谱、工作流、白盒溯源与调试视图，在一个统一系统中完成比赛级展示。</div>
              </div>
            </div>
            <div class="apple-bento">
              <article class="apple-stat">
                <div class="apple-stat-label">🏢 企业主体</div>
                <div class="apple-stat-value">{stats['companies']}</div>
                <div class="apple-stat-meta">覆盖结构化公司实体与关系节点</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">📄 文档规模</div>
                <div class="apple-stat-value">{stats['documents']}</div>
                <div class="apple-stat-meta">已导入的年报 / 研报文档数</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">📊 财务事实</div>
                <div class="apple-stat-value">{stats['financial_facts']}</div>
                <div class="apple-stat-meta">支持精确 SQL 与诊断图表</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">🧠 文本块</div>
                <div class="apple-stat-value">{chroma_stats['chunks']}</div>
                <div class="apple-stat-meta">向量库 Chroma 检索上下文规模</div>
              </article>
            </div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_head(icon, title, desc):
    st.markdown(
        f"""
        <div class="apple-section-head">
          <div class="apple-section-title">
            <div class="apple-icon">{icon}</div>
            <div>
              <h2>{title}</h2>
              <div class="apple-section-desc">{desc}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def get_openai_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY 环境变量。")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


@st.cache_resource(show_spinner=False)
def get_semantic_cache():
    try:
        return SemanticCache()
    except Exception:
        return None


def init_state():
    st.session_state.setdefault("system_messages", [])
    st.session_state.setdefault("persona_messages", [])
    st.session_state.setdefault("advanced_messages", [])
    st.session_state.setdefault("workflow_result", None)
    st.session_state.setdefault("cache_metrics", {"hits": 0, "misses": 0})
    st.session_state.setdefault("selected_role", "投资者模式")
    st.session_state.setdefault("selected_model", DEFAULT_MODEL)


def build_unified_sidebar():
    industries, companies, years, stats = load_filters()
    chroma_stats = load_chroma_stats()
    st.sidebar.title("Apple 风格控制台")
    st.sidebar.markdown("### 系统状态")
    st.sidebar.write(f"企业数：{stats['companies']}")
    st.sidebar.write(f"文档数：{stats['documents']}")
    st.sidebar.write(f"财务事实数：{stats['financial_facts']}")
    st.sidebar.write(f"宏观事实数：{stats['macro_facts']}")
    st.sidebar.write(f"文本块数：{chroma_stats['chunks']}")

    industry = st.sidebar.selectbox("行业", ["全部"] + industries, index=0)
    company = st.sidebar.selectbox("企业", ["全部"] + companies, index=0)
    year = st.sidebar.selectbox("年份", ["全部"] + [str(item) for item in years], index=0)
    role = st.sidebar.radio("角色模式", list(ROLE_PROMPTS.keys()), index=list(ROLE_PROMPTS.keys()).index(st.session_state.selected_role))
    model = st.sidebar.selectbox("DeepSeek 模型", ["deepseek-chat", "deepseek-reasoner"], index=0 if st.session_state.selected_model == "deepseek-chat" else 1)
    top_k = st.sidebar.slider("向量 Top K", min_value=1, max_value=10, value=5)
    use_cache = st.sidebar.toggle("启用语义缓存", value=True)

    if st.sidebar.button("清空全部会话"):
        st.session_state.system_messages = []
        st.session_state.persona_messages = []
        st.session_state.advanced_messages = []
        st.session_state.workflow_result = None

    st.session_state.selected_role = role
    st.session_state.selected_model = model

    filters = {}
    if industry != "全部":
        filters["industry_name"] = industry
    if company != "全部":
        filters["company_name"] = company
    if year != "全部":
        filters["report_year"] = int(year)
    return filters, top_k, role, model, use_cache, stats, chroma_stats, companies


def call_openai_deepseek(messages, model):
    client = get_openai_client()
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.5, stream=False)
    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message:
        raise RuntimeError("DeepSeek 未返回有效消息。")
    content = choice.message.content or ""
    if not content.strip():
        raise RuntimeError("DeepSeek 返回内容为空。")
    reasoning_content = get_reasoning_content(response)
    return content, reasoning_content


def build_persona_prompt(role_name):
    base_prompt = (
        "你是一个顶级的企业运营分析与决策支持智能体。"
        "请使用专业、清晰、结构化的 Markdown 输出。"
        "当信息不足时，必须明确说明信息不足，不要编造。"
    )
    return f"{base_prompt}\n\n当前角色：{role_name}\n{ROLE_PROMPTS[role_name]}"


def render_basic_chat_tab(filters, top_k, use_cache):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("💬", "智能问答", "融合 SQL、向量检索与语义缓存的基础企业分析工作台。")
    cache = get_semantic_cache() if use_cache else None
    try:
        client = create_default_client()
    except Exception:
        client = None
    for message in st.session_state.system_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("chart_spec"):
                render_chart(message["chart_spec"])
            if message.get("sources"):
                render_sources(message["sources"])
            if message.get("warnings"):
                for warning in message["warnings"]:
                    st.caption(warning)
    prompt = st.chat_input("输入企业运营、财务或研报分析问题", key="system_chat_input")
    if prompt:
        st.session_state.system_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                if cache:
                    cache_result = cache.check_cache(prompt)
                    if cache_result["hit"]:
                        st.session_state.cache_metrics["hits"] += 1
                        result = {"answer_markdown": cache_result["answer"], "chart_spec": None, "sources": [{"label": f"语义缓存命中（{cache_result['mode']}）", "snippet": f"score={cache_result['score']:.4f}"}]}
                    else:
                        st.session_state.cache_metrics["misses"] += 1
                        result = answer_query(prompt, filters=filters, top_k=top_k, client=client)
                        cache.update_cache(prompt, result["answer_markdown"])
                else:
                    result = answer_query(prompt, filters=filters, top_k=top_k, client=client)
                st.markdown(result["answer_markdown"])
                if client is None:
                    st.caption("当前未配置 DEEPSEEK_API_KEY，已自动降级为本地检索摘要模式。")
                if result.get("warnings"):
                    for warning in result["warnings"]:
                        st.caption(warning)
                render_chart(result.get("chart_spec"))
                render_sources(result.get("sources"))
                st.session_state.system_messages.append(
                    {
                        "role": "assistant",
                        "content": result["answer_markdown"],
                        "chart_spec": result.get("chart_spec"),
                        "sources": result.get("sources"),
                        "warnings": result.get("warnings"),
                    }
                )
            except Exception as exc:
                st.error(f"执行失败：{exc}")
    st.markdown('</section>', unsafe_allow_html=True)


def render_persona_tab(role, model):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🧭", "多角色分析", "同一问题在投资者、管理者与监管机构视角下得到不同结论。")
    for message in st.session_state.persona_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("从不同角色视角分析问题", key="persona_chat_input")
    if prompt:
        st.session_state.persona_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                answer, _ = call_openai_deepseek(
                    [{"role": "system", "content": build_persona_prompt(role)}] + st.session_state.persona_messages,
                    model,
                )
                st.markdown(answer)
                st.session_state.persona_messages.append({"role": "assistant", "content": answer})
            except Exception as exc:
                st.error(f"调用失败：{exc}")
    st.markdown('</section>', unsafe_allow_html=True)


def render_workflow_tab(filters, top_k):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🪄", "自动化报告", "用串行状态机把大纲规划、SQL、RAG 与研报生成一键串起来。")
    topic = st.text_input("报告主题", value="请为 ST生物 生成经营质量与风险诊断报告", key="workflow_topic")
    if st.button("生成深度诊断报告", key="workflow_button"):
        try:
            client = create_default_client()
        except Exception:
            client = None
        try:
            with st.status("正在执行自动化研报工作流...", expanded=True) as status:
                st.write("步骤一：规划报告大纲")
                st.write("步骤二：执行真实 SQL 检索")
                st.write("步骤三：执行真实向量检索")
                st.write("步骤四：聚合信息并生成最终研报")
                st.session_state.workflow_result = run_workflow(topic, filters=filters, top_k=top_k, client=client)
                status.update(label="研报生成完成", state="complete")
        except Exception as exc:
            st.error(f"生成失败：{exc}")

    result = st.session_state.workflow_result
    if result:
        render_workflow_result(result)
        st.download_button("下载 Markdown 报告", result["report_markdown"].encode("utf-8"), file_name="system_report.md", mime="text/markdown")
    st.markdown('</section>', unsafe_allow_html=True)


def render_graph_tab(company_name):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🕸️", "企业图谱", "股权穿透、风险雷达与创新指数在一个玻璃化工作台中联动展示。")
    if not company_name:
        st.info("请先在侧边栏选择企业。")
        st.markdown('</section>', unsafe_allow_html=True)
        return
    try:
        client = create_default_client()
    except Exception:
        client = None
    try:
        result = run_advanced_analysis("请分析该公司的股权结构、司法风险与创新能力", company_name=company_name, client=client)
        if client is None:
            st.caption("当前未配置 DEEPSEEK_API_KEY，已降级为结构化本地分析结果。")
        st.markdown(result["answer_markdown"])
        for block in result.get("viz_blocks") or []:
            st.markdown(f"### {block['title']}")
            render_echarts(options=block["option"], height="460px")
        render_sources(result.get("sources"))
        with st.expander("高级工具明细", expanded=False):
            st.json(result.get("tool_results"))
    except Exception as exc:
        st.error(f"高级分析失败：{exc}")
    st.markdown('</section>', unsafe_allow_html=True)


def render_whitebox_tab():
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🔬", "白盒溯源", "把 SQL、RAG 切片与 reasoning_content 显式摊开，形成极具透明度的解释界面。")
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
                st.caption(meta)
                st.markdown(chunk["text"])
                st.divider()
        with st.expander("🔍 DeepSeek 思考链", expanded=True):
            st.markdown(MOCK_REASONING)
            if st.button("调用真实 Reasoner 示例", key="reasoner_demo_button"):
                try:
                    content, reasoning = call_openai_deepseek(
                        [
                            {"role": "system", "content": "你是一个严谨的企业白盒分析助手。"},
                            {"role": "user", "content": "请分析 ST生物 2023 年经营质量，并展示思考链。"},
                        ],
                        REASONER_MODEL,
                    )
                    st.markdown("### 模型回复")
                    st.markdown(content)
                    st.markdown("### reasoning_content")
                    st.markdown(reasoning or "模型未返回 reasoning_content。")
                except Exception as exc:
                    st.error(f"调用失败：{exc}")
    st.markdown('</section>', unsafe_allow_html=True)


def render_status_tab(stats, chroma_stats):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🧰", "调试与状态", "查看 SQLite、Chroma、缓存命中率与当前角色/模型选择。")
    st.json(
        {
            "sqlite": stats,
            "chroma": chroma_stats,
            "cache_metrics": st.session_state.cache_metrics,
            "selected_role": st.session_state.selected_role,
            "selected_model": st.session_state.selected_model,
        }
    )
    st.markdown('</section>', unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="企业运营分析与决策支持统一系统", layout="wide")
    inject_apple_ui()
    init_state()
    filters, top_k, role, model, use_cache, stats, chroma_stats, companies = build_unified_sidebar()
    selected_company = filters.get("company_name") or (companies[0] if companies else None)
    render_hero_section(stats, chroma_stats)
    st.caption(f"SQLite: {Path(DEFAULT_DB_PATH)} | Chroma: {Path(DEFAULT_CHROMA_PATH)} | DeepSeek: {DEEPSEEK_BASE_URL}")

    tab_chat, tab_persona, tab_workflow, tab_graph, tab_whitebox, tab_status = st.tabs(
        ["智能问答", "多角色分析", "自动化报告", "企业图谱", "白盒溯源", "调试与状态"]
    )

    with tab_chat:
        render_basic_chat_tab(filters, top_k, use_cache)
    with tab_persona:
        render_persona_tab(role, model)
    with tab_workflow:
        render_workflow_tab(filters, top_k)
    with tab_graph:
        render_graph_tab(selected_company)
    with tab_whitebox:
        render_whitebox_tab()
    with tab_status:
        render_status_tab(stats, chroma_stats)


if __name__ == "__main__":
    main()
