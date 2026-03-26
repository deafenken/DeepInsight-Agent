import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from agent_tools import run_advanced_analysis
from ui_common import build_result_chips, extract_metric_cards, extract_summary_card, load_chroma_stats, load_filters, render_auto_scroll_bottom, render_chart, render_chip_row, render_echarts, render_metric_cards, render_sources, render_streamed_markdown
from app_persona import ROLE_PROMPTS
from cache_tools import SemanticCache
from demo_cache import get_advanced_cache, get_chat_cache, get_workflow_cache
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

        #MainMenu,
        header[data-testid="stHeader"],
        footer,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
          display: none !important;
          visibility: hidden !important;
          height: 0 !important;
        }

        [data-testid="collapsedControl"] {
          display: none !important;
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
          padding-top: 1.25rem;
          padding-bottom: 10rem;
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
          padding: 28px 30px 24px 30px;
          overflow: hidden;
          position: relative;
          margin-bottom: 18px;
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
          gap: 16px;
          margin: 16px 0 0;
        }

        .apple-stat {
          grid-column: span 3;
          padding: 16px 18px 14px;
          min-height: 96px;
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
          font-size: 0.88rem;
          color: var(--muted);
          margin-bottom: 8px;
        }

        .apple-stat-value {
          font-size: clamp(1.65rem, 1.9vw, 2.2rem);
          line-height: 1;
          font-weight: 700;
          letter-spacing: -0.03em;
          margin-bottom: 8px;
        }

        .apple-stat-meta {
          font-size: 0.84rem;
          color: var(--muted);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .apple-section {
          padding: 24px 24px 18px;
          margin-top: 18px;
          transition: transform .36s var(--spring), box-shadow .36s var(--spring), filter .36s var(--spring);
          animation: fadeInUp 0.82s var(--spring);
        }

        .highlight-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .highlight-card {
          padding: 14px 16px;
          min-height: 84px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 6px;
        }

        .highlight-card strong {
          font-size: 1rem;
        }

        .highlight-card span {
          color: var(--muted);
          font-size: 0.92rem;
          line-height: 1.45;
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
          margin-top: 14px;
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

        .top-path-caption {
          display: block;
          margin-bottom: 10px;
        }

        [data-testid="stChatMessage"] {
          padding: 18px 18px 10px;
          margin-bottom: 18px;
          animation: fadeInUp 0.56s var(--spring);
        }

        [data-testid="stChatInput"] {
          position: fixed;
          left: calc(50% + (var(--sidebar-width, 0px) / 2));
          transform: translateX(-50%);
          width: min(860px, calc(100vw - var(--sidebar-width, 0px) - 2rem));
          right: auto;
          bottom: 1rem;
          z-index: 100;
          background: rgba(245,245,247,0.78);
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          padding: 10px 12px 14px;
          border-radius: 28px;
          border: 1px solid rgba(255,255,255,0.62);
          box-shadow: 0 18px 42px rgba(15, 23, 42, 0.12);
        }

        .sidebar-return-button {
          position: fixed;
          top: 0.9rem;
          left: 0.9rem;
          z-index: 1000;
          width: 42px;
          height: 42px;
          display: none;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          background: rgba(255,255,255,0.92);
          border: 1px solid rgba(15, 23, 42, 0.08);
          box-shadow: 0 10px 22px rgba(15, 23, 42, 0.10);
          color: #1d1d1f;
          font-size: 1.1rem;
          cursor: pointer;
          backdrop-filter: blur(16px);
        }

        [data-testid="stChatInput"] textarea,
        [data-testid="stChatInput"] input {
          background: rgba(255,255,255,0.96) !important;
          border-radius: 18px !important;
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

        .thinking-shell {
          padding: 18px 18px 14px;
          border-radius: 22px;
          background: rgba(255,255,255,0.82);
          border: 1px solid rgba(255,255,255,0.62);
          box-shadow: 0 14px 32px rgba(15, 23, 42, 0.08);
        }

        .thinking-title {
          font-weight: 700;
          margin-bottom: 8px;
        }

        .thinking-desc {
          color: var(--muted);
          font-size: 0.93rem;
          margin-bottom: 12px;
        }

        .thinking-bar {
          position: relative;
          height: 8px;
          border-radius: 999px;
          background: rgba(15, 23, 42, 0.08);
          overflow: hidden;
        }

        .thinking-bar::after {
          content: "";
          position: absolute;
          inset: 0;
          width: 32%;
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(10,132,255,0.15), rgba(10,132,255,0.96), rgba(125,211,252,0.55));
          animation: thinkingSlide 1.25s var(--spring) infinite;
        }

        @keyframes thinkingSlide {
          0% { transform: translateX(-120%); }
          100% { transform: translateX(320%); }
        }

        @media (max-width: 1100px) {
          .apple-stat { grid-column: span 6; }
          .highlight-grid { grid-template-columns: 1fr; }
          .apple-stat-meta { white-space: normal; }
        }

        @media (max-width: 720px) {
          .apple-bento { grid-template-columns: 1fr; }
          .apple-stat { grid-column: span 1; }
          .apple-hero { padding: 24px 20px 20px; }
          h1 { font-size: 2.3rem; }
          [data-testid="stChatInput"] {
            left: 50% !important;
            width: calc(100vw - 1.5rem) !important;
            bottom: 0.75rem;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_layout_bridge():
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const root = doc.documentElement;

        const ensureButton = () => {
          let button = doc.getElementById("codex-sidebar-return");
          if (!button) {
            button = doc.createElement("button");
            button.id = "codex-sidebar-return";
            button.className = "sidebar-return-button";
            button.type = "button";
            button.setAttribute("aria-label", "展开侧边栏");
            button.textContent = "☰";
            button.addEventListener("click", () => {
              const collapsed = doc.querySelector('[data-testid="collapsedControl"]');
              const target = collapsed?.querySelector("button") || collapsed;
              if (target) target.click();
            });
            doc.body.appendChild(button);
          }
          return button;
        };

        const updateLayout = () => {
          const sidebar = doc.querySelector('[data-testid="stSidebar"]');
          const button = ensureButton();
          if (!sidebar) {
            root.style.setProperty("--sidebar-width", "0px");
            button.style.display = "none";
            return;
          }
          const expanded = sidebar.getAttribute("aria-expanded") !== "false";
          const width = expanded ? `${Math.round(sidebar.getBoundingClientRect().width)}px` : "0px";
          root.style.setProperty("--sidebar-width", width);
          button.style.display = expanded ? "none" : "flex";
        };

        updateLayout();

        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (sidebar && !sidebar.dataset.codexObserved) {
          const observer = new ResizeObserver(updateLayout);
          observer.observe(sidebar);
          sidebar.dataset.codexObserved = "true";
        }

        window.parent.addEventListener("resize", updateLayout, { passive: true });
        const timer = window.setInterval(updateLayout, 600);
        window.addEventListener("beforeunload", () => window.clearInterval(timer));
        </script>
        """,
        height=0,
    )


def render_hero_section(stats, chroma_stats):
    st.markdown(
        f"""
        <div class="apple-shell">
          <section class="apple-hero">
            <div class="apple-section-title">
              <div class="apple-icon">􀇵</div>
              <div>
                <div class="apple-muted">2026 中国大学生计算机设计大赛大数据主题赛参赛作品</div>
                <h1>医药生物企业智能分析与决策支持系统</h1>
                <div class="apple-section-desc">聚焦医药生物赛题方向，融合关系数据库、向量库、多角色问答、宏观联动分析与自动化报告生成，形成可展示、可追溯、可交互的比赛作品原型。</div>
              </div>
            </div>
            <div class="apple-bento">
              <article class="apple-stat">
                <div class="apple-stat-label">🏢 企业主体</div>
                <div class="apple-stat-value">{stats['companies']}</div>
                <div class="apple-stat-meta">覆盖公司实体与关系节点</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">📄 文档规模</div>
                <div class="apple-stat-value">{stats['documents']}</div>
                <div class="apple-stat-meta">已导入年报与研报文档</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">📊 财务事实</div>
                <div class="apple-stat-value">{stats['financial_facts']}</div>
                <div class="apple-stat-meta">支持 SQL 检索与诊断图表</div>
              </article>
              <article class="apple-stat">
                <div class="apple-stat-label">🧠 文本块</div>
                <div class="apple-stat-value">{chroma_stats['chunks']}</div>
                <div class="apple-stat-meta">Chroma 向量检索上下文规模</div>
              </article>
            </div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_competition_brief():
    st.markdown(
        """
        <div class="apple-card" style="padding:22px 24px; margin-bottom:18px;">
          <div style="font-size:1.05rem; font-weight:700; margin-bottom:8px;">作品亮点</div>
          <div class="apple-muted" style="margin-bottom:14px;">
            系统面向投资者、管理者、监管机构三类角色，支持企业问答、双公司比较、企业与宏观数据联动、白盒溯源与自动化报告生成，适合直接用于比赛答辩与视频演示。
          </div>
          <div class="highlight-grid">
            <div class="apple-card highlight-card">
              <strong>双库协同</strong>
              <span>SQLite 财务与宏观，Chroma 原文证据。</span>
            </div>
            <div class="apple-card highlight-card">
              <strong>多角色智能体</strong>
              <span>投资者、管理者、监管机构三视角切换。</span>
            </div>
            <div class="apple-card highlight-card">
              <strong>联动分析</strong>
              <span>企业财务、年报原文与卫生宏观数据联合判断。</span>
            </div>
            <div class="apple-card highlight-card">
              <strong>可追溯输出</strong>
              <span>答案、SQL、原文切片与来源标签可折叠查看。</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_demo_guide():
    st.markdown(
        """
        <div class="apple-card" style="padding:20px 22px; margin-bottom:18px;">
          <div style="font-size:1rem; font-weight:700; margin-bottom:6px;">答辩演示建议路径</div>
          <div class="apple-muted">
            推荐展示顺序：企业诊断 → 双公司比较 → 企业+宏观联动 → 白盒溯源 → 自动化报告。这样最能体现本作品的多源数据整合、智能问答、分析推理与可追溯能力。
          </div>
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
    st.session_state.setdefault("system_pending_prompt", None)
    st.session_state.setdefault("use_demo_cache", True)
    st.session_state.setdefault("pending_chat_scroll_id", None)
    st.session_state.setdefault("consumed_chat_scroll_id", None)
    st.session_state.setdefault("pending_workflow_scroll_nonce", 0)
    st.session_state.setdefault("consumed_workflow_scroll_nonce", 0)
    st.session_state.setdefault(
        "system_context",
        {"company_name": None, "report_year": None, "macro_topic": False, "last_topic": None, "compare_companies": []},
    )


def build_unified_sidebar():
    _, companies, years, stats = load_filters()
    chroma_stats = load_chroma_stats()
    st.sidebar.title("医药生物控制台")
    st.sidebar.markdown("### 系统状态")
    st.sidebar.write(f"企业数：{stats['companies']}")
    st.sidebar.write(f"文档数：{stats['documents']}")
    st.sidebar.write(f"财务事实数：{stats['financial_facts']}")
    st.sidebar.write(f"宏观事实数：{stats['macro_facts']}")
    st.sidebar.write(f"文本块数：{chroma_stats['chunks']}")

    company = st.sidebar.selectbox("企业", ["全部"] + companies, index=0)
    year = st.sidebar.selectbox("年份", ["全部"] + [str(item) for item in years], index=0)
    role = st.sidebar.radio("角色模式", list(ROLE_PROMPTS.keys()), index=list(ROLE_PROMPTS.keys()).index(st.session_state.selected_role))
    model = st.sidebar.selectbox("DeepSeek 模型", ["deepseek-chat", "deepseek-reasoner"], index=0 if st.session_state.selected_model == "deepseek-chat" else 1)
    top_k = st.sidebar.slider("向量 Top K", min_value=1, max_value=10, value=5)
    use_cache = st.sidebar.toggle("启用语义缓存", value=True)
    use_demo_cache = st.sidebar.toggle("演示极速模式", value=st.session_state.use_demo_cache, help="命中预置演示问题时优先读取本地 JSON 缓存。")

    if st.sidebar.button("清空全部会话"):
        st.session_state.system_messages = []
        st.session_state.persona_messages = []
        st.session_state.advanced_messages = []
        st.session_state.workflow_result = None

    st.session_state.selected_role = role
    st.session_state.selected_model = model
    st.session_state.use_demo_cache = use_demo_cache

    filters = {}
    if company != "全部":
        filters["company_name"] = company
    if year != "全部":
        filters["report_year"] = int(year)
    return filters, top_k, role, model, use_cache, use_demo_cache, stats, chroma_stats, companies


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


CHATGPT_STYLE_STARTERS = [
    "请总结 ST生物 最新年度的经营质量、风险点和关注指标",
    "对比 华兰生物 和 乐普医疗 近年的经营表现差异",
    "从监管机构视角梳理一家公司的潜在合规风险",
    "基于年报与研报，生成一份可追溯的投资分析摘要",
]


def queue_system_prompt(prompt):
    st.session_state.system_pending_prompt = prompt


def render_chat_empty_state():
    st.markdown(
        """
        <div class="apple-card" style="padding:22px 24px; margin-bottom:18px;">
          <div style="font-size:1.1rem; font-weight:700; margin-bottom:8px;">像 ChatGPT 一样开始提问</div>
          <div class="apple-muted" style="margin-bottom:16px;">
            直接输入企业名、年份和你的任务目标。系统会优先组合关系库与向量库，再给出可追溯回答。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for index, starter in enumerate(CHATGPT_STYLE_STARTERS):
        with cols[index % 2]:
            if st.button(starter, key=f"starter_{index}", use_container_width=True):
                queue_system_prompt(starter)
                st.rerun()


def render_demo_launchers():
    st.markdown(
        """
        <div class="apple-card" style="padding:20px 22px; margin-bottom:18px;">
          <div style="font-size:1rem; font-weight:700; margin-bottom:6px;">比赛演示快捷入口</div>
          <div class="apple-muted" style="margin-bottom:14px;">
            一键进入企业诊断、双公司对比或企业+宏观联动场景，方便展示完整作品链路。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    presets = [
        "请总结ST生物2023年的经营质量、风险点和关注指标",
        "对比华兰生物和乐普医疗2023年的经营差异",
        "结合2022到2024年医疗卫生机构变化，分析ST生物的经营环境",
    ]
    cols = st.columns(3)
    for index, preset in enumerate(presets):
        with cols[index]:
            if st.button(preset, key=f"demo_preset_{index}", use_container_width=True):
                queue_system_prompt(preset)
                st.rerun()


def render_chat_status_line(client, filters, use_cache):
    mode = "DeepSeek 增强模式" if client is not None else "本地检索模式"
    selected_company = filters.get("company_name") or "未限定企业"
    selected_year = filters.get("report_year") or "最新可用年份"
    cache_label = "开启" if use_cache else "关闭"
    st.caption(f"{mode} | 企业：{selected_company} | 年份：{selected_year} | 语义缓存：{cache_label}")


def render_thinking_state(stage="正在联合关系库、向量库和宏观数据整理答案，请稍候。"):
    st.markdown(
        f"""
        <div class="thinking-shell">
          <div class="thinking-title">正在深度思考</div>
          <div class="thinking-desc">{stage}</div>
          <div class="thinking-bar"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_answer_summary_card(summary_card):
    if not summary_card:
        return
    st.markdown(
        f"""
        <div class="apple-card" style="padding:16px 18px; margin-bottom:14px; border-radius:20px;">
          <div style="font-size:0.9rem; color:#6b7280; margin-bottom:6px;">{summary_card['title']}</div>
          <div style="font-size:1rem; font-weight:700; line-height:1.6;">{summary_card['body']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_effective_filters(filters):
    effective = dict(filters or {})
    context = st.session_state.system_context
    if not effective.get("company_name") and context.get("company_name"):
        effective["company_name"] = context["company_name"]
    if not effective.get("report_year") and context.get("report_year"):
        effective["report_year"] = context["report_year"]
    return effective


def enrich_followup_prompt(prompt, filters):
    text = (prompt or "").strip()
    if not text:
        return text
    context = st.session_state.system_context
    company = filters.get("company_name") or context.get("company_name")
    compare_companies = context.get("compare_companies") or []
    year = filters.get("report_year") or context.get("report_year")
    last_topic = context.get("last_topic")
    macro_topic = context.get("macro_topic")
    short_followup = any(text.startswith(prefix) for prefix in ["继续", "再", "那", "并且", "同时", "顺便"])
    if company and short_followup and company not in text:
        prefix = f"基于{company}"
        if year and str(year) not in text:
            prefix += f"{year}年"
        text = f"{prefix}，{text}"
    if macro_topic and company and "宏观" not in text and any(token in text for token in ["环境", "影响", "结合", "那"]):
        text = f"{text}，并结合宏观卫生数据"
    if last_topic and len(text) < 18 and company and company not in text:
        text = f"围绕{company}，{text}"
    if compare_companies and any(token in text for token in ["继续对比", "再对比", "差异", "谁更", "哪个更"]) and not any(name in text for name in compare_companies):
        text = f"对比{'、'.join(compare_companies[:2])}，{text}"
    return text


def update_system_context(prompt, result, filters):
    context = st.session_state.system_context
    context["company_name"] = filters.get("company_name") or context.get("company_name")
    context["report_year"] = filters.get("report_year") or context.get("report_year")
    context["macro_topic"] = bool(result.get("macro_rows") or ("宏观" in prompt) or ("卫生" in prompt))
    context["last_topic"] = prompt
    companies = []
    for source in result.get("sources") or []:
        label = source.get("label") or ""
        if " / " in label:
            candidate = label.split(" / ", 1)[0].strip()
            if candidate and "第" not in candidate and "年" not in candidate and "国家统计局" not in candidate:
                companies.append(candidate)
    context["compare_companies"] = [name for index, name in enumerate(companies) if name not in companies[:index]][:3]


def build_followup_prompts(question, filters, result):
    context = st.session_state.system_context
    compare_companies = context.get("compare_companies") or []
    company = filters.get("company_name") or (compare_companies[0] if compare_companies else "该公司")
    prompts = []
    if len(compare_companies) >= 2:
        prompts.append(f"继续对比{'、'.join(compare_companies[:2])}的经营差异")
    if result.get("macro_rows"):
        prompts.append(f"把这些宏观变化和{company}的经营表现结合起来分析")
    if result.get("sql_rows"):
        prompts.append(f"把{company}的关键财务指标按趋势重新总结一遍")
    if result.get("chunks"):
        prompts.append(f"从年报原文里继续追问{company}的主要风险点")
    prompts.append(f"请生成一份关于{company}的可追溯摘要")
    ordered = []
    seen = set()
    for prompt in prompts:
        if prompt not in seen:
            ordered.append(prompt)
            seen.add(prompt)
    return ordered[:3]


def render_supporting_evidence(message, prefix):
    has_support = any(
        message.get(key)
        for key in ["sources", "warnings", "sql", "sql_rows", "macro_sql", "macro_rows", "chunks"]
    )
    if not has_support:
        return
    with st.expander("查看依据", expanded=False):
        if message.get("sources"):
            render_sources(message["sources"])
        if message.get("sql"):
            st.markdown("**企业 SQL**")
            st.code(message["sql"], language="sql")
        if message.get("macro_sql"):
            st.markdown("**宏观 SQL**")
            st.code(message["macro_sql"], language="sql")
        if message.get("warnings"):
            for warning in message["warnings"]:
                st.caption(warning)
        if message.get("chunks"):
            st.markdown("**检索片段**")
            for index, chunk in enumerate(message["chunks"][:3], start=1):
                meta = chunk.get("metadata") or {}
                st.markdown(f"[{index}] {meta.get('source', '未知来源')} 第{meta.get('page') or '?'}页")
                st.caption((chunk.get("text") or "")[:220])
        followups = message.get("followups") or []
        if followups:
            st.markdown("**继续追问**")
            cols = st.columns(len(followups))
            for index, prompt in enumerate(followups):
                with cols[index]:
                    if st.button(prompt, key=f"{prefix}_followup_{index}", use_container_width=True):
                        queue_system_prompt(prompt)
                        st.rerun()


def render_basic_chat_tab(filters, top_k, use_cache, use_demo_cache):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("💬", "智能问答", "融合 SQL、向量检索与语义缓存的基础企业分析工作台。")
    cache = get_semantic_cache() if use_cache else None
    try:
        client = create_default_client()
    except Exception:
        client = None
    render_chat_status_line(client, filters, use_cache)
    if not st.session_state.system_messages:
        render_chat_empty_state()
    render_demo_guide()
    render_demo_launchers()
    for message in st.session_state.system_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("chart_spec"):
                render_chart(message["chart_spec"])
            if message.get("warnings"):
                for warning in message["warnings"]:
                    st.caption(warning)
            if message["role"] == "assistant":
                render_supporting_evidence(message, prefix=f"history_{message.get('message_id', 'msg')}")
    pending_prompt = st.session_state.pop("system_pending_prompt", None)
    live_prompt = st.chat_input("输入企业运营、财务或研报分析问题", key="system_chat_input")
    prompt = pending_prompt or live_prompt
    if prompt:
        effective_filters = build_effective_filters(filters)
        enriched_prompt = enrich_followup_prompt(prompt, effective_filters)
        st.session_state.system_messages.append({"role": "user", "content": enriched_prompt})
        with st.chat_message("user"):
            st.markdown(enriched_prompt)
        with st.chat_message("assistant"):
            try:
                thinking_placeholder = st.empty()
                with thinking_placeholder.container():
                    render_thinking_state("正在理解问题并匹配企业、年份与上下文。")
                if cache:
                    cache_result = cache.check_cache(enriched_prompt)
                    if cache_result["hit"]:
                        st.session_state.cache_metrics["hits"] += 1
                        result = {
                            "answer_markdown": cache_result["answer"],
                            "chart_spec": None,
                            "sources": [{"label": f"语义缓存命中（{cache_result['mode']}）", "snippet": f"score={cache_result['score']:.4f}"}],
                            "warnings": [],
                        }
                    else:
                        st.session_state.cache_metrics["misses"] += 1
                        with thinking_placeholder.container():
                            render_thinking_state("正在检索财务数据、年报原文和宏观指标。")
                        result = get_chat_cache(enriched_prompt) if use_demo_cache else None
                        if result is None:
                            result = answer_query(enriched_prompt, filters=effective_filters, top_k=top_k, client=client)
                        cache.update_cache(enriched_prompt, result["answer_markdown"])
                else:
                    with thinking_placeholder.container():
                        render_thinking_state("正在检索财务数据、年报原文和宏观指标。")
                    result = get_chat_cache(enriched_prompt) if use_demo_cache else None
                    if result is None:
                        result = answer_query(enriched_prompt, filters=effective_filters, top_k=top_k, client=client)
                with thinking_placeholder.container():
                    render_thinking_state("正在生成结论并整理可追溯证据。")
                thinking_placeholder.empty()
                chips = build_result_chips(
                    question=enriched_prompt,
                    sql_rows=result.get("sql_rows"),
                    macro_rows=result.get("macro_rows"),
                    sources=result.get("sources"),
                    route=result.get("route"),
                )
                summary_card = extract_summary_card(result["answer_markdown"])
                metric_cards = extract_metric_cards(result["answer_markdown"])
                render_chip_row(chips)
                render_answer_summary_card(summary_card)
                render_metric_cards(metric_cards)
                rendered_answer = render_streamed_markdown(result["answer_markdown"])
                if client is None:
                    st.caption("当前未配置 DEEPSEEK_API_KEY，已自动降级为本地检索摘要模式。")
                if result.get("warnings"):
                    for warning in result["warnings"]:
                        st.caption(warning)
                render_chart(result.get("chart_spec"))
                followups = build_followup_prompts(enriched_prompt, effective_filters, result)
                update_system_context(enriched_prompt, result, effective_filters)
                assistant_message = {
                    "role": "assistant",
                    "content": rendered_answer,
                    "chart_spec": result.get("chart_spec"),
                    "sources": result.get("sources"),
                    "warnings": result.get("warnings"),
                    "sql": result.get("sql"),
                    "sql_rows": result.get("sql_rows"),
                    "macro_sql": result.get("macro_sql"),
                    "macro_rows": result.get("macro_rows"),
                    "chunks": result.get("chunks"),
                    "followups": followups,
                    "message_id": len(st.session_state.system_messages),
                    "resolved_prompt": enriched_prompt,
                }
                render_supporting_evidence(assistant_message, prefix=f"live_{assistant_message['message_id']}")
                st.session_state.system_messages.append(
                    assistant_message
                )
                st.session_state.pending_chat_scroll_id = assistant_message["message_id"]
            except Exception as exc:
                try:
                    thinking_placeholder.empty()
                except Exception:
                    pass
                st.error(f"执行失败：{exc}")
    pending_scroll_id = st.session_state.get("pending_chat_scroll_id")
    if pending_scroll_id is not None and pending_scroll_id != st.session_state.get("consumed_chat_scroll_id"):
        render_auto_scroll_bottom(f"chat-{pending_scroll_id}")
        st.session_state.consumed_chat_scroll_id = pending_scroll_id
    st.markdown('</section>', unsafe_allow_html=True)


def render_persona_tab(role, model):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🧭", "多角色分析", "同一问题在投资者、管理者与监管机构视角下得到不同结论。")
    for message in st.session_state.persona_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.text_input("从不同角色视角分析问题", key="persona_text_input", placeholder="例如：从监管机构视角分析 ST生物 2023 年的主要风险")
    if st.button("发送角色分析问题", key="persona_submit_button", use_container_width=True) and prompt:
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
                st.session_state.persona_text_input = ""
            except Exception as exc:
                st.error(f"调用失败：{exc}")
    st.markdown('</section>', unsafe_allow_html=True)


def render_workflow_tab(filters, top_k, use_demo_cache):
    st.markdown('<section class="apple-section">', unsafe_allow_html=True)
    section_head("🪄", "自动化报告", "用串行状态机把真实检索、证据聚合与报告生成一键串起来。")
    topic = st.text_input("报告主题", value="请为 ST生物 生成经营质量与风险诊断报告", key="workflow_topic")
    if st.button("生成深度诊断报告", key="workflow_button"):
        try:
            client = create_default_client()
        except Exception:
            client = None
        try:
            with st.status("正在执行自动化研报工作流...", expanded=True) as status:
                st.write("步骤一：理解报告主题")
                st.write("步骤二：执行真实 SQL 检索")
                st.write("步骤三：执行真实向量检索")
                st.write("步骤四：聚合证据并生成最终研报")
                st.session_state.workflow_result = get_workflow_cache(topic) if use_demo_cache else None
                if st.session_state.workflow_result is None:
                    st.session_state.workflow_result = run_workflow(topic, filters=filters, top_k=top_k, client=client)
                st.session_state.pending_workflow_scroll_nonce = st.session_state.get("pending_workflow_scroll_nonce", 0) + 1
                status.update(label="研报生成完成", state="complete")
        except Exception as exc:
            st.error(f"生成失败：{exc}")

    result = st.session_state.workflow_result
    if result:
        render_workflow_result(result)
        st.download_button("下载 Markdown 报告", result["report_markdown"].encode("utf-8"), file_name="system_report.md", mime="text/markdown")
    pending_nonce = st.session_state.get("pending_workflow_scroll_nonce", 0)
    if pending_nonce and pending_nonce != st.session_state.get("consumed_workflow_scroll_nonce", 0):
        render_auto_scroll_bottom(f"workflow-{pending_nonce}")
        st.session_state.consumed_workflow_scroll_nonce = pending_nonce
    st.markdown('</section>', unsafe_allow_html=True)


def render_graph_tab(company_name, use_demo_cache):
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
        result = get_advanced_cache(company_name, "请分析该公司的股权结构、司法风险与创新能力") if use_demo_cache else None
        if result is None:
            result = run_advanced_analysis("请分析该公司的股权结构、司法风险与创新能力", company_name=company_name, client=client)
        if client is None:
            st.caption("当前未配置 DEEPSEEK_API_KEY，已降级为结构化本地分析结果。")
        tool_results = result.get("tool_results") or {}
        equity = tool_results.get("equity") or {}
        risk = tool_results.get("risk") or {}
        innovation = tool_results.get("innovation") or {}
        summary_items = []
        if equity.get("summary"):
            summary_items.append(f"股权网络包含 {equity['summary'].get('node_count', 0)} 个节点、{equity['summary'].get('edge_count', 0)} 条边。")
        if risk.get("dimensions"):
            summary_items.append(
                f"近三年风险事件 {risk['dimensions'].get('风险事件总数', 0)} 起，其中高风险 {risk['dimensions'].get('高风险事件数', 0)} 起。"
            )
        if innovation.get("dimensions"):
            summary_items.append(
                f"专利总量 {innovation['dimensions'].get('专利总量', 0)}，平均专利评分 {innovation['dimensions'].get('平均专利评分', 0)}。"
            )
        if summary_items:
            st.markdown("### 图谱摘要")
            for item in summary_items:
                st.markdown(f"- {item}")
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
    st.set_page_config(page_title="医药生物企业智能分析与决策支持系统", layout="wide")
    inject_apple_ui()
    inject_layout_bridge()
    init_state()
    filters, top_k, role, model, use_cache, use_demo_cache, stats, chroma_stats, companies = build_unified_sidebar()
    selected_company = filters.get("company_name") or (companies[0] if companies else None)
    render_hero_section(stats, chroma_stats)
    render_competition_brief()
    st.markdown('<span class="top-path-caption">&nbsp;</span>', unsafe_allow_html=True)

    tab_chat, tab_persona, tab_workflow, tab_graph, tab_whitebox, tab_status = st.tabs(
        ["💬 智能问答", "🧭 多角色分析", "🪄 自动化报告", "🕸️ 企业图谱", "🔬 白盒溯源", "🧰 调试与状态"]
    )

    with tab_chat:
        render_basic_chat_tab(filters, top_k, use_cache, use_demo_cache)
    with tab_persona:
        render_persona_tab(role, model)
    with tab_workflow:
        render_workflow_tab(filters, top_k, use_demo_cache)
    with tab_graph:
        render_graph_tab(selected_company, use_demo_cache)
    with tab_whitebox:
        render_whitebox_tab()
    with tab_status:
        render_status_tab(stats, chroma_stats)


if __name__ == "__main__":
    main()
