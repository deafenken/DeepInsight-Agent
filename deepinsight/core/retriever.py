import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from pathlib import Path

from deepinsight.config import CHROMA_DIR, DB_PATH

SYSTEM_PROMPT = """
你是一个顶级的企业运营分析与决策支持智能体。你不仅精通财务报表解读，还具备类似“企查查/天眼查”的商业侦察与图谱推理能力。

【你的核心分析维度】：
1. 财务基本面：基于利润表、资产负债表进行定量计算与宏观对标。
2. 资本图谱穿透：当被问及企业背景时，必须主动分析其背后的股东结构、实际控制人以及对外投资的子公司阵列。注意识别“隐蔽的关联交易”。
3. 风险传染监控：如果主公司或其核心子公司存在“失信被执行”、“重大诉讼”或“环保处罚”，必须在回答开头以【🔴 风险预警】的醒目标签予以提示！
4. 创新护城河：结合企业的专利申请类型和数量，评估其在“先进制造/电子信息”等赛道上的硬科技实力。
5. 投资研判：你同时是资深投研分析师，必须在数据分析之后给出明确的【💡 投资参考】，结合财务质量、风险敞口、创新护城河与行业地位形成观点。

【执行纪律】：
- 所有的图谱关系、风险事件和定量数据必须来源于你通过工具检索到的本地 SQLite 数据库或 ChromaDB 向量库，严禁幻觉。
- 综合输出时，必须结构化清晰（使用 Markdown 表格、加粗标记），并在每个核心事实后附带数据来源溯源标签。
- 【💡 投资参考】需包含：综合研判（明确给出“偏多/中性/偏空”的倾向及核心理由）、关键催化剂与主要风险点；并务必以一句“以上为基于已检索数据的研究性分析，仅供参考，不构成任何投资建议。”收尾。

【当前检索到的上下文信息】：
{retrieved_context}
"""

DEFAULT_DB_PATH = DB_PATH
DEFAULT_CHROMA_PATH = CHROMA_DIR
DEFAULT_COLLECTION = "enterprise_documents"
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
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
    if is_macro_question(question):
        route = "sql"
    if not client and filters.get("company_name") and any(word in question for word in ["经营", "财务", "利润", "收入", "风险", "诊断", "质量"]):
        route = "hybrid"
    chart_intent = "line" if any(word in question for word in ["趋势", "变化", "历年"]) else "none"
    return {"route": route, "chart_intent": chart_intent, "reason": "rule_based"}


_FIN_IND_HINT = {}
def get_financial_indicators_hint(db_path=DEFAULT_DB_PATH):
    key = str(db_path)
    if key in _FIN_IND_HINT:
        return _FIN_IND_HINT[key]
    hint = ''
    try:
        conn = get_connection(db_path)
        rows = conn.execute("SELECT indicator_name, COALESCE(aliases,'') AS aliases FROM dict_financial_indicator ORDER BY indicator_name").fetchall()
        conn.close()
        parts = []
        for _row in rows:
            _al = _row['aliases']
            parts.append(_row['indicator_name'] + (('（别名：' + _al + '）') if _al else ''))
        hint = '；'.join(parts)
    except Exception:
        hint = ''
    _FIN_IND_HINT[key] = hint
    return hint


def build_sql_prompt(question, filters=None, db_path=DEFAULT_DB_PATH):
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
        {"role": "system", "content": "财务指标映射：fact_financial_report.indicator_id 关联 dict_financial_indicator；用户问题里的财务指标多为简称/口语（净利润、归母净利润、营收、ROE、毛利率、研发投入等），必须映射到下列【规范 indicator_name】之一，并在 SQL 中用 i.indicator_name = 规范名：\n" + get_financial_indicators_hint(db_path)},
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


def infer_year_from_question(question):
    match = re.search(r"(20\d{2})", question or "")
    return int(match.group(1)) if match else None


def infer_years_from_question(question):
    years = re.findall(r"(20\d{2})", question or "")
    return sorted({int(year) for year in years})


def find_company_names_in_question(question, db_path=DEFAULT_DB_PATH, limit=3):
    text = question or ""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT company_name
            FROM dim_company
            WHERE company_name NOT LIKE '%模拟%'
            ORDER BY LENGTH(company_name) DESC
            """
        ).fetchall()
        matched = []
        for row in rows:
            company_name = row["company_name"]
            if company_name and company_name in text and company_name not in matched:
                matched.append(company_name)
                if len(matched) >= limit:
                    break
        return matched
    finally:
        conn.close()


def resolve_company_industry_name(company_name, db_path=DEFAULT_DB_PATH):
    if not company_name:
        return None
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT i.industry_name
            FROM dim_company c
            LEFT JOIN dim_industry i ON i.industry_id = c.primary_industry_id
            WHERE c.company_name = ?
            """,
            (company_name,),
        ).fetchone()
        return row["industry_name"] if row and row["industry_name"] else None
    finally:
        conn.close()


def resolve_local_query_filters(question, filters=None, db_path=DEFAULT_DB_PATH):
    resolved = dict(filters or {})
    question_companies = find_company_names_in_question(question, db_path=db_path)
    if question_companies:
        resolved["company_names"] = question_companies
        if not resolved.get("company_name"):
            resolved["company_name"] = question_companies[0]
    if resolved.get("company_name") and not resolved.get("industry_name") and len(resolved.get("company_names") or []) <= 1:
        industry_name = resolve_company_industry_name(resolved["company_name"], db_path=db_path)
        if industry_name:
            resolved["industry_name"] = industry_name
            resolved["industry_name_inferred"] = True
    if resolved.get("report_year") is None:
        year_from_question = infer_year_from_question(question)
        if year_from_question:
            resolved["report_year"] = year_from_question
    if resolved.get("company_name") and resolved.get("report_year") is None:
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                """
                SELECT MAX(d.report_year) AS report_year
                FROM dim_document d
                JOIN dim_company c ON d.company_id = c.company_id
                WHERE c.company_name = ? AND d.report_year IS NOT NULL AND d.is_latest = 1
                """,
                (resolved["company_name"],),
            ).fetchone()
            if row and row["report_year"] is not None:
                resolved["report_year"] = int(row["report_year"])
        finally:
            conn.close()
    return resolved


def is_macro_question(question):
    keywords = ["宏观", "统计局", "cpi", "ppi", "m2", "gdp", "卫生", "医疗卫生", "儿童健康", "病床", "住院日", "机构数"]
    text = question or ""
    lower_question = text.lower()
    return any(keyword in text for keyword in keywords if re.search(r"[\u4e00-\u9fff]", keyword)) or any(
        keyword in lower_question for keyword in keywords if not re.search(r"[\u4e00-\u9fff]", keyword)
    )


def extract_macro_query_phrases(question):
    text = re.sub(r"20\d{2}", " ", question or "")
    stop_phrases = [
        "请分析",
        "国家统计局",
        "卫生数据",
        "数据里",
        "分别是多少",
        "是多少",
        "怎么样",
        "变化趋势",
        "趋势",
        "分析",
        "请问",
    ]
    for phrase in stop_phrases:
        text = text.replace(phrase, " ")
    blocks = [block.strip() for block in re.findall(r"[\u4e00-\u9fffA-Za-z]+", text) if len(block.strip()) >= 2]
    phrases = set(blocks)
    for block in blocks:
        upper = min(len(block), 8)
        for size in range(2, upper + 1):
            for start in range(0, len(block) - size + 1):
                phrases.add(block[start : start + size])
    generic = {"数据", "卫生", "统计局", "国家", "请问", "分析"}
    return [phrase for phrase in sorted(phrases, key=len, reverse=True) if phrase not in generic]


def find_macro_indicator_names(question, db_path=DEFAULT_DB_PATH, limit=5):
    conn = get_connection(db_path)
    try:
        if "医疗卫生机构" in (question or "") and any(word in (question or "") for word in ["变化", "趋势", "数量", "机构数"]):
            preferred = [
                row["indicator_name"]
                for row in conn.execute(
                    """
                    SELECT indicator_name
                    FROM dict_macro_indicator
                    WHERE indicator_name LIKE '医疗卫生机构-%数'
                    ORDER BY CASE
                        WHEN indicator_name = '医疗卫生机构-医疗卫生机构数' THEN 0
                        WHEN indicator_name = '医疗卫生机构-医院数' THEN 1
                        WHEN indicator_name = '医疗卫生机构-专业公共卫生机构数' THEN 2
                        ELSE 9
                    END, indicator_name
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            ]
            if preferred:
                return preferred
        tokens = extract_macro_query_phrases(question)
        candidates = []
        for row in conn.execute("SELECT indicator_name FROM dict_macro_indicator"):
            indicator_name = row["indicator_name"]
            score = 0
            for token in tokens:
                if token in indicator_name:
                    score += max(1, len(token))
            if score:
                candidates.append((score, indicator_name))
        candidates.sort(key=lambda item: (-item[0], len(item[1])))
        return [name for _, name in candidates[:limit]]
    finally:
        conn.close()


def generate_local_macro_sql(question, db_path=DEFAULT_DB_PATH):
    indicator_names = find_macro_indicator_names(question, db_path=db_path, limit=3)
    if not indicator_names:
        raise ValueError("未匹配到可用宏观指标。")
    years = infer_years_from_question(question)
    year_filter = ""
    if years:
        quoted_dates = ", ".join(quote_sql_text(f"{year}-12-31") for year in years)
        year_filter = f" AND f.period_date IN ({quoted_dates})"
    indicator_filter = ", ".join(quote_sql_text(name) for name in indicator_names)
    order_sql = "ORDER BY d.indicator_name, f.period_date"
    if any(word in question for word in ["趋势", "变化", "历年"]):
        order_sql = "ORDER BY d.indicator_name, f.period_date"
    return sanitize_sql(
        f"""
        SELECT
            d.indicator_name,
            f.period_date,
            f.value_num,
            COALESCE(f.unit, d.default_unit) AS unit,
            f.region_name,
            d.source_name
        FROM fact_macro_data f
        JOIN dict_macro_indicator d ON f.macro_indicator_id = d.macro_indicator_id
        WHERE d.indicator_name IN ({indicator_filter}){year_filter}
        {order_sql}
        """
    )


def generate_sql(question, filters=None, client=None, db_path=DEFAULT_DB_PATH):
    if client:
        raw = call_llm_serial(client, "text_to_sql", build_sql_prompt(question, filters, db_path))
        return sanitize_sql(raw)
    resolved_filters = resolve_local_query_filters(question, filters, db_path=db_path)
    company = resolved_filters.get("company_name")
    company_names = resolved_filters.get("company_names") or ([company] if company else [])
    year = resolved_filters.get("report_year")
    if company_names and year:
        company_filter = ", ".join(quote_sql_text(name) for name in company_names[:2])
        return sanitize_sql(
            f"""
            SELECT c.company_name, d.report_year, i.indicator_name, f.period_label, f.value_role, f.value_num, f.unit, f.source_page
            FROM fact_financial_report f
            JOIN dim_document d ON f.document_id = d.document_id
            JOIN dim_company c ON d.company_id = c.company_id
            JOIN dict_financial_indicator i ON f.indicator_id = i.indicator_id
            WHERE d.is_latest = 1 AND c.company_name IN ({company_filter}) AND d.report_year = {int(year)}
            ORDER BY c.company_name, i.indicator_name, f.value_role DESC, f.period_label DESC
            """
        )
    if is_macro_question(question):
        return generate_local_macro_sql(question, db_path=db_path)
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
    company_names = [name for name in (filters.get("company_names") or []) if name]
    apply_industry_filter = bool(filters.get("industry_name")) and not filters.get("industry_name_inferred")
    if filters.get("doc_type"):
        conditions.append({"doc_type": filters["doc_type"]})
    if company_names:
        if len(company_names) == 1:
            conditions.append({"company_name": company_names[0]})
        else:
            conditions.append({"$or": [{"company_name": name} for name in company_names]})
    elif filters.get("company_name"):
        conditions.append({"company_name": filters["company_name"]})
    if filters.get("report_year"):
        conditions.append({"report_year": int(filters["report_year"])})
    if apply_industry_filter:
        conditions.append({"industry_name": filters["industry_name"]})
    if len(conditions) == 1:
        return conditions[0]
    if conditions:
        return {"$and": conditions}
    return None


def select_top_chunks(scored_chunks, top_k, company_names=None):
    ordered = [item for _, item in sorted(scored_chunks, key=lambda item: item[0], reverse=True)]
    if not company_names or len(company_names) < 2:
        return ordered[:top_k]

    selected = []
    seen_ids = set()
    normalized_names = [name for name in company_names if name]
    for company_name in normalized_names:
        for item in ordered:
            metadata = item.get("metadata") or {}
            chunk_key = (
                metadata.get("document_id"),
                metadata.get("chunk_index"),
                metadata.get("page"),
                item.get("text"),
            )
            if metadata.get("company_name") != company_name or chunk_key in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(chunk_key)
            break
    for item in ordered:
        metadata = item.get("metadata") or {}
        chunk_key = (
            metadata.get("document_id"),
            metadata.get("chunk_index"),
            metadata.get("page"),
            item.get("text"),
        )
        if chunk_key in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(chunk_key)
        if len(selected) >= top_k:
            break
    return selected[:top_k]


def query_collection_candidates(collection, embedding, filters, top_k):
    where = build_chroma_filter(filters)
    kwargs = {
        "query_embeddings": [embedding],
        "n_results": min(max(top_k * 3, top_k), 15),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)


def retrieve_chunks(question, filters=None, top_k=5, client=None, chroma_path=DEFAULT_CHROMA_PATH, collection_name=DEFAULT_COLLECTION):
    collection = get_collection(chroma_path, collection_name)
    embedding_client = LocalEmbeddingClient()
    embedding = embedding_client.embed([question])[0]
    chunks = []
    filters = filters or {}
    company_names = [name for name in (filters.get("company_names") or []) if name]
    if len(company_names) >= 2:
        results = []
        shared_filters = {key: value for key, value in filters.items() if key not in {"company_names", "company_name"}}
        for company_name in company_names:
            company_filters = dict(shared_filters)
            company_filters["company_name"] = company_name
            results.append(query_collection_candidates(collection, embedding, company_filters, top_k))
    else:
        results = [query_collection_candidates(collection, embedding, filters, top_k)]
    documents = []
    metadatas = []
    distances = []
    for result in results:
        documents.extend(result.get("documents", [[]])[0])
        metadatas.extend(result.get("metadatas", [[]])[0])
        distances.extend(result.get("distances", [[]])[0])
    query_terms = [term for term in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", question or "") if len(term) >= 2]
    query_focus_terms = ["经营", "风险", "环境", "主营业务", "概述", "行业", "市场", "竞争", "研发", "现金流", "收入", "利润"]
    scored_chunks = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        compact = re.sub(r"\s+", "", document or "")
        if len(compact) < 20:
            continue
        if compact.count("|") >= 8 and len(set(compact.replace("|", ""))) <= 10:
            continue
        if compact.count("|") >= 12 and len(re.findall(r"[\u4e00-\u9fffA-Za-z]", compact)) < 40:
            continue
        if compact.startswith("|---") or compact.startswith("##") and compact.count("|") >= 10:
            continue
        pipe_ratio = compact.count("|") / max(len(compact), 1)
        if pipe_ratio > 0.08:
            continue
        text = document or ""
        if any(term in text for term in ["股东与股东大会", "独立董事", "监事会", "公司治理", "释义"]):
            continue
        if any(term in question for term in ["经营", "风险", "环境", "质量"]) and not any(term in text for term in query_focus_terms):
            if compact.count("|") >= 3:
                continue
        score = -(distance or 0)
        if metadata and metadata.get("page") in {None, 1, 2, 3, 4, 5}:
            score -= 0.2 if metadata.get("page") is None else 0.35
        if "年度报告全文" in text:
            score -= 0.15
        noisy_terms = ["董事", "监事", "股东大会", "释义", "名词解释", "公司治理", "审计", "账龄", "坏账准备"]
        score -= sum(0.12 for term in noisy_terms if term in text)
        positive_terms = ["主营业务", "概述", "经营情况", "风险", "核心竞争力", "行业", "市场", "管理层", "研发", "现金流", "营业收入", "净利润"]
        score += sum(0.16 for term in positive_terms if term in text)
        score += sum(min(0.08 * text.count(term), 0.24) for term in query_terms if term in text)
        scored_chunks.append((score, {"text": document, "metadata": metadata, "distance": distance}))
    for item in select_top_chunks(scored_chunks, top_k, filters.get("company_names") if filters else None):
        chunks.append(item)
    return chunks


def build_sources(sql_rows, chunks):
    company_names = []
    for row in sql_rows:
        company_name = row.get("company_name")
        if company_name and company_name not in company_names:
            company_names.append(company_name)
    sources = []
    seen_labels = set()
    ordered_sql_rows = list(sql_rows)
    if len(company_names) >= 2:
        buckets = {name: [] for name in company_names}
        other_rows = []
        for row in sql_rows:
            if row.get("company_name") in buckets:
                buckets[row["company_name"]].append(row)
            else:
                other_rows.append(row)
        ordered_sql_rows = []
        max_len = max(len(items) for items in buckets.values()) if buckets else 0
        for index in range(max_len):
            for company_name in company_names:
                if index < len(buckets[company_name]):
                    ordered_sql_rows.append(buckets[company_name][index])
        ordered_sql_rows.extend(other_rows)
    for row in ordered_sql_rows:
        parts = []
        if row.get("company_name"):
            parts.append(str(row["company_name"]))
        if row.get("report_year"):
            parts.append(f"{row['report_year']}年")
        if row.get("indicator_name") and not row.get("company_name"):
            parts.append(str(row["indicator_name"]))
        if row.get("period_date"):
            parts.append(str(row["period_date"]))
        if row.get("source_name"):
            parts.append(str(row["source_name"]))
        if row.get("source_page"):
            parts.append(f"第{row['source_page']}页")
        if parts:
            label = " / ".join(parts)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            sources.append({"type": "sql", "label": label, "snippet": json.dumps(row, ensure_ascii=False)})
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        label = f"{metadata.get('source', '未知来源')} 第{metadata.get('page') or '?'}页"
        if label in seen_labels:
            continue
        seen_labels.add(label)
        sources.append({"type": "vector", "label": label, "snippet": chunk.get("text", "")[:220]})
    return sources[:16]


def build_local_tags(sql_rows, macro_rows):
    tags = []
    grouped = {}
    for row in sql_rows:
        metric = row.get("indicator_name")
        if metric:
            grouped.setdefault(metric, []).append(row)

    def current_row(rows):
        return next((row for row in rows if row.get("value_role") == "current"), rows[0] if rows else None)

    profit = current_row(grouped.get("归属于上市公司股东的净利润") or [])
    cash = current_row(grouped.get("经营活动产生的现金流量净额") or [])
    roe = current_row(grouped.get("净资产收益率") or [])
    if profit and isinstance(profit.get("value_num"), (int, float)):
        tags.append("盈利承压" if profit["value_num"] < 0 else "利润修复")
    if cash and isinstance(cash.get("value_num"), (int, float)):
        tags.append("现金流偏弱" if cash["value_num"] < 0 else "现金流为正")
    if roe and isinstance(roe.get("value_num"), (int, float)) and roe["value_num"] < 0:
        tags.append("回报率偏弱")
    if macro_rows:
        tags.append("宏观联动")
    ordered = []
    seen = set()
    for tag in tags:
        if tag not in seen:
            ordered.append(tag)
            seen.add(tag)
    return ordered[:4]


def normalize_unit_for_display(value, unit):
    if unit == "%" and isinstance(value, (int, float)) and abs(value) > 1000:
        return ""
    return unit or ""


def build_comparison_summary(sql_rows):
    companies = []
    grouped = {}
    for row in sql_rows:
        company_name = row.get("company_name")
        metric = row.get("indicator_name")
        if not company_name or not metric:
            continue
        if company_name not in companies:
            companies.append(company_name)
        grouped.setdefault(company_name, {}).setdefault(metric, []).append(row)
    if len(companies) < 2:
        return []
    lines = []
    for metric in ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "总资产"]:
        entries = []
        for company in companies[:2]:
            rows = grouped.get(company, {}).get(metric) or []
            current = next((row for row in rows if row.get("value_role") == "current"), rows[0] if rows else None)
            if current and current.get("value_num") is not None:
                entries.append((company, current["value_num"], current.get("unit") or ""))
        if len(entries) == 2:
            ranked = sorted(entries, key=lambda item: item[1], reverse=True)
            left_unit = normalize_unit_for_display(ranked[0][1], ranked[0][2])
            right_unit = normalize_unit_for_display(ranked[1][1], ranked[1][2])
            lines.append(f"- {metric}：{ranked[0][0]}（{ranked[0][1]}{left_unit}）高于{ranked[1][0]}（{ranked[1][1]}{right_unit}）")
    return lines[:4]


def pick_best_company_metric_rows(sql_rows, indicator_name):
    rows_by_company = {}
    for row in sql_rows:
        if row.get("indicator_name") != indicator_name or not row.get("company_name"):
            continue
        if row.get("value_role") != "current":
            continue
        rows_by_company.setdefault(row["company_name"], []).append(row)
    selected = []
    for company_name, rows in rows_by_company.items():
        def score(row):
            unit = row.get("unit")
            value = row.get("value_num")
            unit_score = 2 if unit == "元" else (1 if unit not in {"%", None} else 0)
            magnitude_score = abs(value) if isinstance(value, (int, float)) else 0
            return (unit_score, magnitude_score)
        selected.append(max(rows, key=score))
    return selected


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


def run_macro_side_query(question, db_path=DEFAULT_DB_PATH):
    if not is_macro_question(question):
        return None, []
    try:
        macro_sql = generate_local_macro_sql(question, db_path=db_path)
        macro_rows = execute_sql(macro_sql, db_path)
        return macro_sql, macro_rows
    except (ValueError, sqlite3.Error):
        return None, []


def infer_chart_spec(sql_rows, route_info):
    if not sql_rows:
        return None
    first = sql_rows[0]
    numeric_keys = [key for key, value in first.items() if isinstance(value, (int, float)) and key != "source_page"]
    if not numeric_keys:
        return None
    y_key = "value_num" if "value_num" in numeric_keys else numeric_keys[0]
    x_key = None
    for candidate in ["report_year", "period_label", "period_date", "company_name", "indicator_name"]:
        if candidate in first:
            x_key = candidate
            break
    if not x_key:
        return None
    company_names = []
    for row in sql_rows:
        if row.get("company_name") and row["company_name"] not in company_names:
            company_names.append(row["company_name"])
    if len(company_names) >= 2 and "company_name" in first and "indicator_name" in first:
        preferred_indicator = next(
            (
                indicator
                for indicator in ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "总资产"]
                if any(row.get("indicator_name") == indicator for row in sql_rows)
            ),
            None,
        )
        if preferred_indicator:
            rows = pick_best_company_metric_rows(sql_rows, preferred_indicator)
            if len(rows) >= 2:
                return {
                    "chart_type": "bar",
                    "x": "company_name",
                    "y": y_key,
                    "series": None,
                    "rows": rows,
                }
    return {
        "chart_type": "line" if route_info.get("chart_intent") == "line" else "bar",
        "x": x_key,
        "y": y_key,
        "series": "company_name" if "company_name" in first else ("indicator_name" if "indicator_name" in first and x_key == "period_date" else None),
        "rows": sql_rows,
    }


def generate_answer(question, context_bundle, sources, client=None, history=None, answer_client=None):
    if not context_bundle["text"].strip():
        return "未检索到相关内容。当前数据库命中的公司和文档可能不足，请先导入更多年报或在问题中明确公司名与年份。"
    if not client:
        sql_rows = context_bundle.get("sql_rows") or []
        macro_rows = context_bundle.get("macro_rows") or []
        chunks = context_bundle.get("chunks") or []
        answer = ["## 本地检索回答", ""]
        answer.append(f"**问题**：{question}")
        answer.append("")
        answer.append("已基于本地 SQLite + Chroma 完成检索整合；当前为无大模型降级回答，结论以证据摘录为主。")
        if sql_rows:
            is_macro_result = any(row.get("period_date") for row in sql_rows) and not any(row.get("company_name") for row in sql_rows)
            answer.extend(["", "### 结构化指标线索" if is_macro_result else "### 结构化财务线索"])
            if is_macro_result:
                grouped = {}
                for row in sql_rows:
                    metric = row.get("indicator_name") or "指标"
                    grouped.setdefault(metric, []).append(row)
                for metric, rows in list(grouped.items())[:6]:
                    ordered = sorted(rows, key=lambda item: item.get("period_date") or "")
                    parts = []
                    for row in ordered:
                        value = row.get("value_num") if row.get("value_num") is not None else row.get("value_text")
                        unit = row.get("unit") or ""
                        parts.append(f"{row.get('period_date', '?')}: {value}{unit}")
                    answer.append(f"- {metric}：{'；'.join(parts)}")
            else:
                company_name = next((row.get("company_name") for row in sql_rows if row.get("company_name")), "该公司")
                company_names = []
                for row in sql_rows:
                    if row.get("company_name") and row["company_name"] not in company_names:
                        company_names.append(row["company_name"])
                grouped = {}
                company_grouped = {}
                for row in sql_rows:
                    metric = row.get("indicator_name") or row.get("indicator") or "指标"
                    grouped.setdefault(metric, []).append(row)
                    if row.get("company_name"):
                        company_grouped.setdefault(row["company_name"], {}).setdefault(metric, []).append(row)
                insight_lines = []
                summary_bits = []
                tags = build_local_tags(sql_rows, macro_rows)
                comparison_lines = build_comparison_summary(sql_rows)
                if tags:
                    answer.extend(["", "### 经营标签", " | ".join(f"`{tag}`" for tag in tags)])
                if comparison_lines:
                    answer.extend(["", "### 对比卡片"])
                    answer.extend(comparison_lines)
                if len(company_names) > 1:
                    answer.extend(["", "### 公司要点"])
                    for company in company_names[:2]:
                        bits = []
                        for key_metric in ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额"]:
                            rows = company_grouped.get(company, {}).get(key_metric) or []
                            current = next((row for row in rows if row.get("value_role") == "current"), rows[0] if rows else None)
                            historical = next((row for row in rows if row.get("value_role") == "historical"), None)
                            if not current or current.get("value_num") is None:
                                continue
                            direction = "待观察"
                            if historical and historical.get("value_num") not in (None, 0):
                                delta = current["value_num"] - historical["value_num"]
                                direction = "上升" if delta > 0 else ("下降" if delta < 0 else "基本持平")
                            bits.append(f"{key_metric}{direction}")
                        if bits:
                            answer.append(f"- {company}：{'、'.join(bits)}")
                else:
                    for key_metric in ["营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额", "总资产", "研发费用"]:
                        if key_metric not in grouped:
                            continue
                        rows = grouped[key_metric]
                        current = next((row for row in rows if row.get("value_role") == "current"), rows[0])
                        historical = next((row for row in rows if row.get("value_role") == "historical"), None)
                        current_value = current.get("value_num")
                        historical_value = historical.get("value_num") if historical else None
                        unit = normalize_unit_for_display(current_value, current.get("unit"))
                        line = f"{key_metric}当前值为 {current_value}{unit}"
                        if historical_value not in (None, 0):
                            delta = current_value - historical_value
                            direction = "上升" if delta > 0 else ("下降" if delta < 0 else "基本持平")
                            line += f"，较上期{direction}"
                            if key_metric in {"营业收入", "归属于上市公司股东的净利润", "经营活动产生的现金流量净额"}:
                                summary_bits.append(f"{key_metric}{direction}")
                        insight_lines.append(f"- {company_name}{line}")
                    if summary_bits:
                        answer.extend(
                            [
                                "",
                                "### 摘要判断",
                                f"{company_name}当前呈现的特征是："
                                + "、".join(summary_bits[:3])
                                + "。该结论基于本地财务事实抽取，适合用作快速研判起点，详细判断仍需结合原文与多期数据继续追问。",
                            ]
                        )
                    if insight_lines:
                        answer.extend(["", "### 快速结论"])
                        answer.extend(insight_lines[:4])
                answer.extend(["", "### 关键指标"])
                seen_metrics = set()
                for row in sql_rows:
                    metric = row.get("indicator_name") or row.get("indicator") or "指标"
                    metric_key = f"{row.get('company_name','')}-{metric}" if len(company_names) > 1 else metric
                    if metric_key in seen_metrics:
                        continue
                    value = row.get("value_num") if row.get("value_num") is not None else row.get("value_text")
                    unit = normalize_unit_for_display(value, row.get("unit"))
                    page = f"（第{row['source_page']}页）" if row.get("source_page") else ""
                    prefix = f"{row.get('company_name')} / " if len(company_names) > 1 and row.get("company_name") else ""
                    answer.append(f"- {prefix}{metric}：{value}{unit}{page}")
                    seen_metrics.add(metric_key)
                    if len(seen_metrics) >= 5:
                        break
        if macro_rows:
            grouped = {}
            for row in macro_rows:
                metric = row.get("indicator_name") or "宏观指标"
                grouped.setdefault(metric, []).append(row)
            macro_summary = []
            answer.extend(["", "### 宏观指标线索"])
            for metric, rows in list(grouped.items())[:5]:
                ordered = sorted(rows, key=lambda item: item.get("period_date") or "")
                parts = []
                for row in ordered:
                    value = row.get("value_num") if row.get("value_num") is not None else row.get("value_text")
                    unit = row.get("unit") or ""
                    parts.append(f"{row.get('period_date', '?')}: {value}{unit}")
                if len(ordered) >= 2 and all(item.get("value_num") is not None for item in (ordered[0], ordered[-1])):
                    delta = ordered[-1]["value_num"] - ordered[0]["value_num"]
                    direction = "上升" if delta > 0 else ("下降" if delta < 0 else "基本持平")
                    macro_summary.append(f"{metric}{direction}")
                answer.append(f"- {metric}：{'；'.join(parts)}")
            if macro_summary:
                answer.extend(["", "### 宏观补充判断", "相关宏观指标整体表现为：" + "、".join(macro_summary[:3]) + "。"])
        if chunks:
            answer.extend(["", "### 文档证据"])
            for chunk in chunks[:3]:
                meta = chunk.get("metadata") or {}
                label = f"{meta.get('source', '未知来源')} 第{meta.get('page') or '?'}页"
                snippet = re.sub(r"\s+", " ", chunk.get("text", "")).strip()[:180]
                answer.append(f"- {label}：{snippet}")
        answer.extend(["", "### 证据边界", "- 未调用大模型推理时，系统不会自动补全结论，只展示本地已命中的结构化指标与原文证据。"])
        if sources:
            answer.append("")
            answer.append("参考来源：")
            answer.extend([f"- {source['label']}" for source in sources])
        return "\n".join(answer)
    system_prompt = SYSTEM_PROMPT.format(retrieved_context=context_bundle["text"])
    messages = [{"role": "system", "content": system_prompt}]
    for _m in (history or []):
        _r = _m.get("role"); _c = (_m.get("content") or "").strip()
        if _r in ("user", "assistant") and _c:
            messages.append({"role": _r, "content": _c[:2000]})
    messages.append({"role": "user", "content": question})
    return call_llm_serial(answer_client or client, "answer", messages, temperature=0.2)


def condense_question(question, history, client):
    if not history or not client:
        return question
    parts = []
    for _m in history[-6:]:
        _m = _m or {}
        _c = (_m.get('content') or '').strip()
        if _c:
            parts.append((_m.get('role') or 'user') + ': ' + _c[:600])
    convo = '\n'.join(parts)
    prompt = [
        {'role': 'system', 'content': '你是检索问题改写助手。结合对话历史，把用户最新的问题改写成一个独立、完整、可单独检索的问题，必须显式保留公司名、年份、指标等关键信息。只输出改写后的问题本身，不要解释。'},
        {'role': 'user', 'content': '对话历史:\n' + convo + '\n\n最新问题: ' + question + '\n\n改写后的独立问题:'},
    ]
    try:
        out = (call_llm_serial(client, 'condense', prompt, temperature=0.0) or '').strip()
        return out[:200] or question
    except Exception:
        return question


def answer_query(question, filters=None, top_k=5, db_path=DEFAULT_DB_PATH, chroma_path=DEFAULT_CHROMA_PATH, collection_name=DEFAULT_COLLECTION, client=None, history=None, answer_client=None):
    rq = condense_question(question, history, client) if (history and client) else question
    effective_filters = resolve_local_query_filters(rq, filters, db_path=db_path) if not client else (filters or {})
    route_info = route_question(rq, effective_filters, client)
    sql = None
    sql_rows = []
    macro_sql = None
    macro_rows = []
    chunks = []
    warnings = []

    if route_info["route"] in {"sql", "hybrid"}:
        try:
            sql = generate_sql(rq, effective_filters, client, db_path=db_path)
            sql_rows = execute_sql(sql, db_path)
        except (ValueError, sqlite3.Error) as exc:
            sql = None
            sql_rows = []
            warnings.append(f"SQL检索不可用：{exc}")
            if route_info["route"] == "sql":
                route_info["route"] = "vector"
    if route_info["route"] in {"vector", "hybrid"}:
        try:
            chunks = retrieve_chunks(rq, effective_filters, top_k, client, chroma_path, collection_name)
        except Exception as exc:
            chunks = []
            warnings.append(f"向量检索不可用：{exc}")
            if route_info["route"] == "vector":
                route_info["route"] = "sql"
    if effective_filters.get("company_name") and is_macro_question(rq):
        macro_sql, macro_rows = run_macro_side_query(rq, db_path=db_path)
        if not macro_rows and macro_sql is None:
            warnings.append("宏观侧检索未命中可用指标。")

    all_sql_rows = [*sql_rows, *macro_rows]
    sources = build_sources(all_sql_rows, chunks)
    context_bundle = build_context_bundle(all_sql_rows, chunks)
    context_bundle["sql_rows"] = sql_rows
    context_bundle["macro_rows"] = macro_rows
    context_bundle["chunks"] = chunks
    answer_markdown = generate_answer(question, context_bundle, sources, client, history=history, answer_client=answer_client)
    chart_spec = infer_chart_spec(sql_rows, route_info)

    return {
        "route": route_info["route"],
        "reason": route_info.get("reason"),
        "sql": sql,
        "sql_rows": sql_rows,
        "macro_sql": macro_sql,
        "macro_rows": macro_rows,
        "chunks": chunks,
        "sources": sources,
        "context": context_bundle["text"],
        "answer_markdown": answer_markdown,
        "chart_spec": chart_spec,
        "warnings": warnings,
    }


def create_default_client():
    return DeepSeekClient()


def create_optional_client(chat_model=None):
    if not os.getenv("DEEPSEEK_API_KEY"):
        return None
    return DeepSeekClient(chat_model=chat_model)
