import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from pathlib import Path

SYSTEM_PROMPT = """
你是一个顶级的企业运营分析与决策支持智能体。你不仅精通财务报表解读，还具备类似“企查查/天眼查”的商业侦察与图谱推理能力。

【你的核心分析维度】：
1. 财务基本面：基于利润表、资产负债表进行定量计算与宏观对标。
2. 资本图谱穿透：当被问及企业背景时，必须主动分析其背后的股东结构、实际控制人以及对外投资的子公司阵列。注意识别“隐蔽的关联交易”。
3. 风险传染监控：如果主公司或其核心子公司存在“失信被执行”、“重大诉讼”或“环保处罚”，必须在回答开头以【🔴 风险预警】的醒目标签予以提示！
4. 创新护城河：结合企业的专利申请类型和数量，评估其在“先进制造/电子信息”等赛道上的硬科技实力。

【执行纪律】：
- 所有的图谱关系、风险事件和定量数据必须来源于你通过工具检索到的本地 SQLite 数据库或 ChromaDB 向量库，严禁幻觉。
- 综合输出时，必须结构化清晰（使用 Markdown 表格、加粗标记），并在每个核心事实后附带数据来源溯源标签。

【当前检索到的上下文信息】：
{retrieved_context}
"""

DEFAULT_DB_PATH = Path("/Volumes/ORICO/code1/data/enterprise_analysis.db")
DEFAULT_CHROMA_PATH = Path("/Volumes/ORICO/code1/data/chroma")
DEFAULT_COLLECTION = "enterprise_documents"
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")
LLM_LOCK = threading.Lock()
LOCAL_EMBEDDING_DIMENSIONS = 256
ALLOWED_TABLES = {
    "dim_company",
    "dim_document",
    "dict_financial_indicator",
    "fact_financial_report",
    "dict_macro_indicator",
    "fact_macro_data",
    "dim_industry",
}


class DeepSeekClient:
    def __init__(self, api_key=None, chat_model=None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.chat_model = chat_model or DEEPSEEK_CHAT_MODEL
        if not self.api_key:
            raise RuntimeError("缺少 DEEPSEEK_API_KEY。")

    def _post(self, url, payload):
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("未安装 requests。") from exc
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        return response.json()

    def chat(self, messages, temperature=0.1):
        payload = {"model": self.chat_model, "messages": messages, "temperature": temperature}
        data = self._post(DEEPSEEK_BASE_URL, payload)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"DeepSeek 返回为空: {data}")
        return choices[0]["message"]["content"]


class LocalEmbeddingClient:
    def __init__(self, dimensions=LOCAL_EMBEDDING_DIMENSIONS):
        self.dimensions = dimensions

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
            if not tokens:
                vectors.append(vector)
                continue
            for token in tokens:
                index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dimensions
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


def get_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_collection(chroma_path=DEFAULT_CHROMA_PATH, collection_name=DEFAULT_COLLECTION):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("未安装 chromadb。") from exc
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(name=collection_name)


def call_llm_serial(client, task_name, messages, temperature=0.1):
    with LLM_LOCK:
        return client.chat(messages, temperature=temperature)


def get_schema_text():
    return """
可用 SQLite 表：
1. dim_company(company_id, stock_code, company_name, company_short_name, exchange, primary_industry_id, company_url)
2. dim_industry(industry_id, industry_code, industry_name, industry_level, parent_industry_id)
3. dim_document(document_id, company_id, doc_type, report_year, title, file_name, file_path, version_label, is_latest, announcement_no, publish_date, source_url, pages_total, parser_type)
4. dict_financial_indicator(indicator_id, indicator_code, indicator_name, statement_category, value_type, default_unit, aliases)
5. fact_financial_report(report_fact_id, document_id, indicator_id, period_label, statement_scope, value_role, currency_code, unit, value_num, value_text, source_page, source_row_label)
6. dict_macro_indicator(macro_indicator_id, indicator_code, indicator_name, frequency, default_unit, source_name)
7. fact_macro_data(macro_fact_id, macro_indicator_id, period_date, region_name, value_num, unit, release_date, source_file)
""".strip()


def route_question(question, filters=None, client=None):
    filters = filters or {}
    keyword_sql = ["多少", "营收", "收入", "利润", "净利润", "同比", "环比", "资产", "负债", "现金流", "宏观", "指标", "排名", "趋势"]
    keyword_vector = ["原因", "风险", "怎么看", "介绍", "主营业务", "竞争力", "战略", "研发", "管理层", "分析", "研报"]
    score_sql = sum(1 for word in keyword_sql if word in question)
    score_vector = sum(1 for word in keyword_vector if word in question)
    if client:
        prompt = [
            {"role": "system", "content": "你是问题路由器，只输出 JSON。route 只能是 sql、vector、hybrid。chart_intent 只能是 line、bar、none。"},
            {"role": "user", "content": json.dumps({"question": question, "filters": filters}, ensure_ascii=False)},
        ]
        raw = call_llm_serial(client, "router", prompt)
        try:
            payload = json.loads(extract_json(raw))
            route = payload.get("route")
            if route in {"sql", "vector", "hybrid"}:
                return {
                    "route": route,
                    "chart_intent": payload.get("chart_intent", "none"),
                    "reason": payload.get("reason", ""),
                }
        except Exception:
            pass
    if score_sql and score_vector:
        route = "hybrid"
    elif score_sql:
        route = "sql"
    elif score_vector:
        route = "vector"
    else:
        route = "hybrid"
    chart_intent = "line" if any(word in question for word in ["趋势", "变化", "历年"]) else "none"
    return {"route": route, "chart_intent": chart_intent, "reason": "rule_based"}


def build_sql_prompt(question, filters=None):
    filters = filters or {}
    return [
        {
            "role": "system",
            "content": (
                "你是 Text-to-SQL 助手。只输出单条 SELECT SQL，不要解释，不要 markdown，不要分号。"
                "只能查询给定 schema，禁止 INSERT/UPDATE/DELETE/ALTER/DROP/ATTACH/PRAGMA。"
                "字段名必须严格使用 schema 中的真实字段，尤其是 document_id，不允许使用 doc_id。"
                "优先使用 is_latest=1 的文档。"
            ),
        },
        {"role": "system", "content": get_schema_text()},
        {"role": "user", "content": json.dumps({"question": question, "filters": filters}, ensure_ascii=False)},
    ]


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text


def sanitize_sql(sql):
    cleaned = sql.strip().strip("`").replace(";", "")
    upper = cleaned.upper()
    blocked = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "ATTACH", "PRAGMA", "CREATE", "REPLACE"]
    if not upper.startswith("SELECT"):
        raise ValueError("仅允许 SELECT 查询")
    if any(token in upper for token in blocked):
        raise ValueError("SQL 包含不允许的语句")
    tokens = cleaned.replace("\n", " ").split()
    for index, token in enumerate(tokens[:-1]):
        if token.upper() in {"FROM", "JOIN"}:
            table = tokens[index + 1].strip(",")
            table = table.split(".")[-1]
            if table not in ALLOWED_TABLES:
                raise ValueError(f"不允许查询表: {table}")
    return cleaned


def quote_sql_text(value):
    return "'" + str(value).replace("'", "''") + "'"


def generate_sql(question, filters=None, client=None):
    if client:
        raw = call_llm_serial(client, "text_to_sql", build_sql_prompt(question, filters))
        return sanitize_sql(raw)
    company = (filters or {}).get("company_name")
    year = (filters or {}).get("report_year")
    if company and year:
        return sanitize_sql(
            f"""
            SELECT c.company_name, d.report_year, i.indicator_name, f.value_num, f.unit, f.source_page
            FROM fact_financial_report f
            JOIN dim_document d ON f.document_id = d.document_id
            JOIN dim_company c ON d.company_id = c.company_id
            JOIN dict_financial_indicator i ON f.indicator_id = i.indicator_id
            WHERE d.is_latest = 1 AND c.company_name = {quote_sql_text(company)} AND d.report_year = {int(year)}
            ORDER BY i.indicator_name
            """
        )
    raise ValueError("缺少 LLM 时，默认 SQL 生成仅支持传入 company_name 与 report_year 过滤。")


def execute_sql(sql, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    try:
        rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def build_chroma_filter(filters=None):
    filters = filters or {}
    conditions = []
    if filters.get("doc_type"):
        conditions.append({"doc_type": filters["doc_type"]})
    if filters.get("company_name"):
        conditions.append({"company_name": filters["company_name"]})
    if filters.get("report_year"):
        conditions.append({"report_year": int(filters["report_year"])})
    if filters.get("industry_name"):
        conditions.append({"industry_name": filters["industry_name"]})
    if len(conditions) == 1:
        return conditions[0]
    if conditions:
        return {"$and": conditions}
    return None


def retrieve_chunks(question, filters=None, top_k=5, client=None, chroma_path=DEFAULT_CHROMA_PATH, collection_name=DEFAULT_COLLECTION):
    collection = get_collection(chroma_path, collection_name)
    embedding_client = LocalEmbeddingClient()
    embedding = embedding_client.embed([question])[0]
    where = build_chroma_filter(filters)
    kwargs = {"query_embeddings": [embedding], "n_results": top_k, "include": ["documents", "metadatas", "distances"]}
    if where:
        kwargs["where"] = where
    result = collection.query(**kwargs)
    chunks = []
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for document, metadata, distance in zip(documents, metadatas, distances):
        item = {"text": document, "metadata": metadata, "distance": distance}
        chunks.append(item)
    return chunks


def build_sources(sql_rows, chunks):
    sources = []
    for row in sql_rows:
        parts = []
        if row.get("company_name"):
            parts.append(str(row["company_name"]))
        if row.get("report_year"):
            parts.append(f"{row['report_year']}年")
        if row.get("source_page"):
            parts.append(f"第{row['source_page']}页")
        if parts:
            sources.append({"type": "sql", "label": " / ".join(parts), "snippet": json.dumps(row, ensure_ascii=False)})
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        label = f"{metadata.get('source', '未知来源')} 第{metadata.get('page') or '?'}页"
        sources.append({"type": "vector", "label": label, "snippet": chunk.get("text", "")[:220]})
    return sources


def build_context_bundle(sql_rows, chunks):
    sections = []
    if sql_rows:
        rows_text = "\n".join(json.dumps(row, ensure_ascii=False) for row in sql_rows[:20])
        sections.append(f"[SQL结果]\n{rows_text}")
    if chunks:
        chunk_text = []
        for index, chunk in enumerate(chunks, start=1):
            meta = chunk.get("metadata") or {}
            chunk_text.append(
                f"[{index}] 来源：{meta.get('source', '未知')} 第{meta.get('page') or '?'}页\n{chunk.get('text', '')}"
            )
        sections.append("[向量检索]\n" + "\n\n".join(chunk_text))
    return {"text": "\n\n".join(sections)}


def infer_chart_spec(sql_rows, route_info):
    if not sql_rows:
        return None
    first = sql_rows[0]
    numeric_keys = [key for key, value in first.items() if isinstance(value, (int, float)) and key != "source_page"]
    if not numeric_keys:
        return None
    x_key = None
    for candidate in ["report_year", "period_label", "period_date", "company_name", "indicator_name"]:
        if candidate in first:
            x_key = candidate
            break
    if not x_key:
        return None
    return {
        "chart_type": "line" if route_info.get("chart_intent") == "line" else "bar",
        "x": x_key,
        "y": numeric_keys[0],
        "series": "company_name" if "company_name" in first else None,
        "rows": sql_rows,
    }


def generate_answer(question, context_bundle, sources, client=None):
    if not context_bundle["text"].strip():
        return "未检索到相关内容。当前数据库命中的公司和文档可能不足，请先导入更多年报或在问题中明确公司名与年份。"
    if not client:
        answer = [f"问题：{question}", "", context_bundle["text"] or "未检索到相关上下文。"]
        if sources:
            answer.append("")
            answer.append("参考来源：")
            answer.extend([f"- {source['label']}" for source in sources])
        return "\n".join(answer)
    system_prompt = SYSTEM_PROMPT.format(retrieved_context=context_bundle["text"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    return call_llm_serial(client, "answer", messages, temperature=0.2)


def answer_query(question, filters=None, top_k=5, db_path=DEFAULT_DB_PATH, chroma_path=DEFAULT_CHROMA_PATH, collection_name=DEFAULT_COLLECTION, client=None):
    route_info = route_question(question, filters, client)
    sql = None
    sql_rows = []
    chunks = []

    if route_info["route"] in {"sql", "hybrid"}:
        sql = generate_sql(question, filters, client)
        try:
            sql_rows = execute_sql(sql, db_path)
        except sqlite3.Error:
            sql = None
            sql_rows = []
            if route_info["route"] == "sql":
                route_info["route"] = "vector"
    if route_info["route"] in {"vector", "hybrid"}:
        chunks = retrieve_chunks(question, filters, top_k, client, chroma_path, collection_name)

    sources = build_sources(sql_rows, chunks)
    context_bundle = build_context_bundle(sql_rows, chunks)
    answer_markdown = generate_answer(question, context_bundle, sources, client)
    chart_spec = infer_chart_spec(sql_rows, route_info)

    return {
        "route": route_info["route"],
        "reason": route_info.get("reason"),
        "sql": sql,
        "sql_rows": sql_rows,
        "chunks": chunks,
        "sources": sources,
        "context": context_bundle["text"],
        "answer_markdown": answer_markdown,
        "chart_spec": chart_spec,
    }


def create_default_client():
    return DeepSeekClient()
