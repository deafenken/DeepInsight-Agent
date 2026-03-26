from pathlib import Path

import copy
import html
import json
import re
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from retriever import DEFAULT_CHROMA_PATH, DEFAULT_COLLECTION, DEFAULT_DB_PATH, get_collection, get_connection


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
    st.markdown(
        """
        <div style="padding:12px 14px; margin:12px 0 10px; border-radius:18px; background:rgba(255,255,255,0.82); border:1px solid rgba(15,23,42,0.08);">
          <div style="font-size:0.9rem; color:#6b7280; margin-bottom:8px;">图表洞察</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
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
        label = html.escape(source["label"])
        snippet = html.escape((source.get("snippet") or "").strip())
        st.markdown(
            f"""
            <details style="padding:12px 14px; margin-bottom:10px; border-radius:16px; background:rgba(255,255,255,0.78); border:1px solid rgba(15,23,42,0.08);">
              <summary style="display:flex; align-items:center; gap:8px; cursor:pointer; list-style:none;">
                <span style="display:inline-flex; min-width:24px; height:24px; align-items:center; justify-content:center; border-radius:999px; background:#eff6ff; color:#2563eb; font-size:12px; font-weight:700;">{index}</span>
                <span style="font-weight:700; color:#111827;">{label}</span>
                <span style="margin-left:auto; color:#6b7280; font-size:0.83rem;">点击展开</span>
              </summary>
              {f'<div style="margin-top:10px; color:#6b7280; font-size:0.88rem; line-height:1.6;">{snippet}</div>' if snippet else '<div style="margin-top:10px; color:#9ca3af; font-size:0.88rem;">暂无原文片段</div>'}
            </details>
            """,
            unsafe_allow_html=True,
        )


def sanitize_echarts_options(options):
    sanitized = copy.deepcopy(options or {})
    sanitized.setdefault("color", ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444"])
    sanitized.setdefault("textStyle", {"color": "#0f172a", "fontFamily": "SF Pro Text, PingFang SC, sans-serif"})
    data_zoom = sanitized.get("dataZoom") or []
    if isinstance(data_zoom, dict):
        data_zoom = [data_zoom]
    for item in data_zoom:
        if not isinstance(item, dict):
            continue
        item["zoomLock"] = True
        item["moveOnMouseWheel"] = False
        item["zoomOnMouseWheel"] = False
        item["moveOnMouseMove"] = False
        item["preventDefaultMouseMove"] = True
    if data_zoom:
        sanitized["dataZoom"] = data_zoom

    for axis_key in ["xAxis", "yAxis", "angleAxis", "radiusAxis"]:
        axis = sanitized.get(axis_key)
        if isinstance(axis, dict):
            axis.setdefault("scale", False)
        elif isinstance(axis, list):
            for item in axis:
                if isinstance(item, dict):
                    item.setdefault("scale", False)

    for series in sanitized.get("series") or []:
        if not isinstance(series, dict):
            continue
        if series.get("type") == "graph":
            series["roam"] = False
            if isinstance(series.get("force"), dict):
                series["force"]["layoutAnimation"] = False

    tooltip = sanitized.get("tooltip")
    if isinstance(tooltip, dict):
        tooltip.setdefault("confine", True)
    return sanitized


def render_echarts(options, height="480px"):
    try:
        from streamlit_echarts import st_echarts as _st_echarts
    except Exception as exc:
        st.caption(f"ECharts 组件不可用，已降级为配置展示：{exc}")
        st.code(json.dumps(options, ensure_ascii=False, indent=2), language="json")
        return
    try:
        st.markdown(
            """
            <div style="padding:12px 14px; margin:12px 0 10px; border-radius:18px; background:rgba(255,255,255,0.82); border:1px solid rgba(15,23,42,0.08);">
              <div style="font-size:0.9rem; color:#6b7280; margin-bottom:8px;">分析图表</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _st_echarts(options=sanitize_echarts_options(options), height=height)
    except Exception as exc:
        st.caption(f"ECharts 渲染失败，已降级为配置展示：{exc}")
        st.code(json.dumps(options, ensure_ascii=False, indent=2), language="json")


def render_interactive_table(df, *, max_rows=100, height_px=420, caption=None):
    if df is None or df.empty:
        st.caption(caption or "暂无表格数据。")
        return

    visible_df = df.head(max_rows).fillna("")
    columns = [str(col) for col in visible_df.columns]
    rows_html = []
    for _, row in visible_df.iterrows():
        cell_html = []
        for col in columns:
            raw_value = row[col]
            display_value = str(raw_value)
            escaped_value = html.escape(display_value)
            cell_html.append(
                f'<td title="{escaped_value}"><span>{escaped_value}</span></td>'
            )
        rows_html.append(f"<tr>{''.join(cell_html)}</tr>")

    notice = caption or ""
    if len(df) > max_rows:
        suffix = f"当前展示前 {max_rows} 行，共 {len(df)} 行。"
        notice = f"{notice} {suffix}".strip()

    table_html = f"""
    <style>
    .codex-table-wrap {{
        border: 1px solid rgba(15, 23, 42, 0.10);
        border-radius: 18px;
        overflow: auto;
        max-height: {height_px}px;
        background: #ffffff;
        box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
    }}
    .codex-table {{
        width: max-content;
        min-width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        table-layout: auto;
        font-size: 0.93rem;
    }}
    .codex-table thead th {{
        position: sticky;
        top: 0;
        z-index: 1;
        background: #f8fafc;
        color: #0f172a;
        text-align: left;
        font-weight: 700;
        border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    }}
    .codex-table th,
    .codex-table td {{
        padding: 0.8rem 0.9rem;
        white-space: nowrap;
        border-bottom: 1px solid rgba(15, 23, 42, 0.06);
        vertical-align: top;
    }}
    .codex-table tbody tr:hover td {{
        background: #fffef7;
    }}
    .codex-table td span {{
        display: inline-block;
        max-width: 24rem;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .codex-table-caption {{
        margin-top: 0.45rem;
        color: #64748b;
        font-size: 0.84rem;
    }}
    </style>
    <div class="codex-table-wrap">
      <table class="codex-table">
        <thead>
          <tr>{''.join(f"<th>{html.escape(col)}</th>" for col in columns)}</tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)
    if notice:
        st.caption(notice)


def render_auto_scroll_bottom(key_suffix="default"):
    components.html(
        f"""
        <script>
        const frameId = "codex-scroll-{key_suffix}";
        if (!window.frameElement || window.frameElement.dataset.scrollId === frameId) {{
          const parentDoc = window.parent.document;
          const app = parentDoc.querySelector('[data-testid="stAppViewContainer"]');
          if (app) {{
            app.scrollTo({{ top: app.scrollHeight, behavior: "smooth" }});
          }}
          window.parent.scrollTo({{ top: parentDoc.body.scrollHeight, behavior: "smooth" }});
          if (window.frameElement) {{
            window.frameElement.dataset.scrollId = frameId;
          }}
        }}
        </script>
        """,
        height=0,
    )


def _chunk_markdown_for_stream(text):
    content = (text or "").strip()
    if not content:
        return []
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    chunks = []
    for block in blocks:
        if len(block) <= 220:
            chunks.append(block + "\n\n")
            continue
        lines = block.splitlines()
        buffer = []
        buffer_len = 0
        for line in lines:
            candidate_len = buffer_len + len(line) + 1
            if buffer and candidate_len > 220:
                chunks.append("\n".join(buffer) + "\n\n")
                buffer = [line]
                buffer_len = len(line)
            else:
                buffer.append(line)
                buffer_len = candidate_len
        if buffer:
            chunks.append("\n".join(buffer) + "\n\n")
    return chunks


def render_streamed_markdown(text):
    chunks = _chunk_markdown_for_stream(text)
    if not chunks:
        st.markdown(text or "")
        return text or ""

    def _generator():
        for chunk in chunks:
            yield chunk

    try:
        rendered = st.write_stream(_generator())
        return rendered if isinstance(rendered, str) else text
    except Exception:
        st.markdown(text)
        return text


def extract_summary_card(markdown_text):
    text = (markdown_text or "").strip()
    if not text:
        return None
    match = re.search(r"### (摘要判断|快速结论)\n(.+?)(?:\n### |\Z)", text, re.S)
    if match:
        title = match.group(1)
        body = match.group(2).strip()
        body_lines = [line.strip("- ").strip() for line in body.splitlines() if line.strip()]
        summary = "；".join(body_lines[:3]).strip()
        if summary:
            return {"title": title, "body": summary}
    plain_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("### ")]
    if plain_lines:
        return {"title": "核心判断", "body": "；".join(plain_lines[:2])[:220]}
    return None


def extract_metric_cards(markdown_text, limit=4):
    text = (markdown_text or "").strip()
    if not text:
        return []
    match = re.search(r"### 关键指标\n(.+?)(?:\n### |\Z)", text, re.S)
    if not match:
        return []
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip().startswith("- ")]
    cards = []
    for line in lines[:limit]:
        payload = line[2:].strip()
        if "：" in payload:
            label, value = payload.split("：", 1)
        else:
            label, value = payload, ""
        value = re.sub(r"（第\d+页）", "", value).strip()
        cards.append({"label": label.strip(), "value": value})
    return cards


def render_metric_cards(cards):
    if not cards:
        return
    cols = st.columns(len(cards))
    for index, card in enumerate(cards):
        with cols[index]:
            st.markdown(
                f"""
                <div style="padding:14px 16px; min-height:116px; border-radius:18px; background:rgba(255,255,255,0.82); border:1px solid rgba(15,23,42,0.08); box-shadow:0 10px 24px rgba(15,23,42,0.05);">
                  <div style="font-size:0.86rem; color:#6b7280; margin-bottom:8px;">{html.escape(card['label'])}</div>
                  <div style="font-size:1rem; font-weight:700; line-height:1.55; color:#111827;">{html.escape(card['value'] or '已命中指标')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def build_result_chips(question="", sql_rows=None, macro_rows=None, sources=None, route=None):
    chips = []
    seen = set()

    def push(value):
        normalized = (value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            chips.append(normalized)

    for row in sql_rows or []:
        push(row.get("company_name"))
    year_matches = re.findall(r"\b(20\d{2})\b", question or "")
    for year in year_matches[:2]:
        push(f"{year}年")
    for row in sql_rows or []:
        report_year = row.get("report_year")
        if report_year:
            push(f"{report_year}年")
    if macro_rows:
        push("宏观联动")
    if route == "hybrid":
        push("双库协同")
    elif route == "sql":
        push("结构化检索")
    elif route == "vector":
        push("向量检索")
    if sources:
        source_names = []
        for source in sources[:4]:
            label = source.get("label") or ""
            if " / " in label:
                source_name = label.split(" / ", 1)[0].strip()
                if source_name and "国家统计局" not in source_name:
                    source_names.append(source_name)
        for name in source_names[:2]:
            push(name)
    return chips[:6]


def render_chip_row(chips):
    if not chips:
        return
    chip_html = "".join(
        f'<span style="display:inline-flex; align-items:center; padding:6px 10px; border-radius:999px; background:rgba(37,99,235,0.08); color:#1d4ed8; font-size:0.84rem; font-weight:600; border:1px solid rgba(37,99,235,0.12);">{html.escape(chip)}</span>'
        for chip in chips
    )
    st.markdown(
        f'<div style="display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 14px;">{chip_html}</div>',
        unsafe_allow_html=True,
    )


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


def get_project_paths_caption():
    return f"SQLite: {Path(DEFAULT_DB_PATH)} | Chroma: {Path(DEFAULT_CHROMA_PATH)}"
