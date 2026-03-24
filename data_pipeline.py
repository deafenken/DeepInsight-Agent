import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("/Volumes/ORICO/code1/data/enterprise_analysis.db")
DEFAULT_CHROMA_PATH = Path("/Volumes/ORICO/code1/data/chroma")
DEFAULT_COLLECTION = "enterprise_documents"
DEFAULT_INPUT_DIRS = [Path("/Volumes/ORICO/code1/reports_md"), Path("/Volumes/ORICO/code1/report_md")]
PAGE_INLINE_RE = re.compile(r"^\**\s*(\d{1,4})\s*/\s*(\d{1,4})\s*\**$")
PAGE_SINGLE_RE = re.compile(r"^\d{1,4}$")
STOCK_CODE_RE = re.compile(r"(?:股票代码|公司代码)[：:\s]*([0-9]{6})")
ANNOUNCEMENT_RE = re.compile(r"公告编号[：:\s]*([A-Za-z0-9\-]+)")
DATE_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
URL_RE = re.compile(r"https?://[^\s)）]+")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

FINANCIAL_ALIASES = {
    "revenue": ["营业收入", "营业总收入", "主营业务收入"],
    "net_profit_parent": ["归属于上市公司股东的净利润", "归母净利润"],
    "net_profit_deducted": ["归属于上市公司股东的扣除非经常性损益的净利润", "扣非净利润"],
    "operating_cash_flow": ["经营活动产生的现金流量净额", "经营现金流净额"],
    "total_assets": ["总资产", "资产总额"],
    "net_assets_parent": ["归属于上市公司股东的净资产", "归母净资产"],
    "gross_margin": ["毛利率", "销售毛利率"],
    "debt_ratio": ["资产负债率"],
    "rd_expense": ["研发费用", "研发投入", "研发支出"],
    "roe": ["净资产收益率", "加权平均净资产收益率"],
}


@dataclass
class ParsedPage:
    page_no: Optional[int]
    text: str


@dataclass
class ParsedDocument:
    metadata: dict
    pages: list
    raw_text: str
    lines: list


class ZhipuEmbeddingClient:
    def __init__(self, api_key=None, model=None, base_url=None, timeout=60):
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY")
        self.model = model or os.getenv("ZHIPU_EMBEDDING_MODEL", "embedding-3")
        self.base_url = base_url or os.getenv("ZHIPU_EMBEDDING_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/embeddings")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("缺少 ZHIPU_API_KEY，无法写入 Chroma 向量数据。")

    def embed(self, texts):
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("未安装 requests，无法调用智谱 embedding 接口。") from exc

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or []
        if not data:
            raise RuntimeError(f"智谱 embedding 返回为空: {payload}")
        return [item["embedding"] for item in data]


class LocalEmbeddingClient:
    def __init__(self, dimensions=256):
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


def get_embedding_client():
    return LocalEmbeddingClient()


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_collection(chroma_path, collection_name):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("未安装 chromadb。") from exc

    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(name=collection_name)


def get_splitter(chunk_size, chunk_overlap):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
        except ImportError as exc:
            raise RuntimeError("未安装 LangChain 文本切分组件。") from exc

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n|", "\n- ", "\n\n", "。", "\n", " "],
    )


def resolve_input_dir(input_dir=None):
    if input_dir:
        path = Path(input_dir)
        if path.exists():
            return path
        raise FileNotFoundError(f"输入目录不存在: {path}")
    for path in DEFAULT_INPUT_DIRS:
        if path.exists():
            return path
    raise FileNotFoundError("未找到 reports_md 或 report_md 目录。")


def infer_doc_type(path, explicit_doc_type=None):
    if explicit_doc_type:
        return explicit_doc_type
    lower = str(path).lower()
    if "research" in lower or "研报" in path.name:
        return "research_report"
    return "annual_report"


def normalize_company_name(name):
    return re.sub(r"\s+", "", name).strip("-_（）() ")


def parse_filename_metadata(path):
    stem = path.stem
    version_label = "updated" if any(token in stem for token in ["更新版", "修订", "修正版"]) else "base"
    company_name = stem
    report_year = None
    match = re.match(r"(.+?)-(20\d{2})年?(?:年度)?(?:报告|年报|研报)?", stem)
    if match:
        company_name = match.group(1)
        report_year = int(match.group(2))
    company_name = normalize_company_name(re.sub(r"\(.*?\)|（.*?）", "", company_name))
    return {
        "company_name": company_name,
        "report_year": report_year,
        "version_label": version_label,
    }


def is_single_page_marker(lines, index):
    line = lines[index].strip().replace("*", "")
    if not PAGE_SINGLE_RE.match(line):
        return False
    prev_line = lines[index - 1].strip() if index > 0 else ""
    next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
    return not prev_line and (not next_line or "年度报告" in next_line or "picture" in next_line.lower())


def parse_pages(lines):
    pages = []
    current_page = None
    total_pages = None
    buffer = []

    def flush():
        text = "\n".join(buffer).strip()
        if text:
            pages.append(ParsedPage(page_no=current_page, text=text))

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        marker = PAGE_INLINE_RE.match(line.replace("**", ""))
        if marker:
            flush()
            buffer = []
            current_page = int(marker.group(1))
            total_pages = int(marker.group(2))
            continue
        if is_single_page_marker(lines, index):
            flush()
            buffer = []
            current_page = int(line)
            continue
        if "intentionally omitted" in line.lower() and "picture" in line.lower():
            continue
        buffer.append(raw_line.rstrip())

    flush()
    if not pages:
        pages.append(ParsedPage(page_no=1, text="\n".join(lines).strip()))
        total_pages = 1
    return pages, total_pages


def extract_document_metadata(path, raw_text, lines, explicit_doc_type=None, industry_name=None):
    file_meta = parse_filename_metadata(path)
    head_text = "\n".join(lines[:220])
    stock_code = None
    announcement_no = None
    publish_date = None
    source_url = None

    stock_match = STOCK_CODE_RE.search(head_text)
    if stock_match:
        stock_code = stock_match.group(1)

    announcement_match = ANNOUNCEMENT_RE.search(head_text)
    if announcement_match:
        announcement_no = announcement_match.group(1)

    date_match = DATE_RE.search(head_text)
    if date_match:
        publish_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"

    url_match = URL_RE.search(head_text)
    if url_match:
        source_url = url_match.group(0)

    title = None
    for line in lines[:40]:
        cleaned = line.strip().strip("#").strip()
        if "年度报告" in cleaned or "研报" in cleaned:
            title = cleaned
            break

    metadata = {
        "company_name": file_meta["company_name"],
        "stock_code": stock_code,
        "report_year": file_meta["report_year"],
        "version_label": file_meta["version_label"],
        "announcement_no": announcement_no,
        "publish_date": publish_date,
        "source_url": source_url,
        "title": title or path.stem,
        "doc_type": infer_doc_type(path, explicit_doc_type),
        "industry_name": industry_name,
        "file_name": path.name,
        "file_path": str(path),
        "parser_type": path.suffix.lower().lstrip("."),
        "file_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
    }
    return metadata


def read_text_with_fallback(path):
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def load_markdown_document(path, explicit_doc_type=None, industry_name=None):
    raw_text = read_text_with_fallback(path)
    lines = raw_text.splitlines()
    pages, total_pages = parse_pages(lines)
    metadata = extract_document_metadata(path, raw_text, lines, explicit_doc_type, industry_name)
    metadata["pages_total"] = total_pages
    return ParsedDocument(metadata=metadata, pages=pages, raw_text=raw_text, lines=lines)


def load_pdf_document(path, explicit_doc_type=None, industry_name=None):
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("未安装 pdfplumber，无法读取 PDF。") from exc

    pages = []
    texts = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(ParsedPage(page_no=index, text=text))
                texts.append(text)
    raw_text = "\n".join(texts)
    metadata = extract_document_metadata(path, raw_text, raw_text.splitlines(), explicit_doc_type, industry_name)
    metadata["pages_total"] = len(pdf.pages)
    return ParsedDocument(metadata=metadata, pages=pages or [ParsedPage(page_no=1, text=raw_text)], raw_text=raw_text, lines=raw_text.splitlines())


def load_document(path, explicit_doc_type=None, industry_name=None):
    suffix = path.suffix.lower()
    if suffix == ".md":
        return load_markdown_document(path, explicit_doc_type, industry_name)
    if suffix == ".pdf":
        return load_pdf_document(path, explicit_doc_type, industry_name)
    raise ValueError(f"不支持的文件类型: {path}")


def split_document(parsed_document, splitter):
    chunks = []
    chunk_index = 0
    for page in parsed_document.pages:
        page_chunks = splitter.split_text(page.text)
        for piece in page_chunks:
            text = piece.strip()
            if not text:
                continue
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "page_start": page.page_no,
                    "page_end": page.page_no,
                    "text": text,
                }
            )
            chunk_index += 1
    if not chunks:
        chunks.append({"chunk_index": 0, "page_start": 1, "page_end": 1, "text": parsed_document.raw_text[:500]})
    return chunks


def find_indicator_id_map(conn):
    rows = conn.execute("SELECT indicator_id, indicator_code FROM dict_financial_indicator").fetchall()
    return {row["indicator_code"]: row["indicator_id"] for row in rows}


def parse_numeric(value):
    cleaned = value.replace(",", "").replace("%", "").strip()
    if cleaned in {"", "-", "--", "不适用"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def detect_unit(context_lines):
    context = " ".join(context_lines)
    if "单位：万元" in context:
        return "万元"
    if "单位：亿元" in context:
        return "亿元"
    if "单位：元" in context:
        return "元"
    if "币种：人民币" in context:
        return "元"
    if "%" in context:
        return "%"
    return None


def extract_financial_facts(parsed_document, conn):
    indicator_map = find_indicator_id_map(conn)
    report_year = parsed_document.metadata.get("report_year")
    if not report_year:
        return []

    results = []
    current_page = None
    recent_lines = []
    seen = set()

    for index, raw_line in enumerate(parsed_document.lines):
        line = raw_line.strip().replace("**", "")
        marker = PAGE_INLINE_RE.match(line)
        if marker:
            current_page = int(marker.group(1))
            continue
        if is_single_page_marker(parsed_document.lines, index):
            current_page = int(line)
            continue
        recent_lines.append(raw_line)
        recent_lines = recent_lines[-5:]
        if not line.startswith("|"):
            continue
        cells = [cell.strip().replace("<br>", " ") for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        row_label = re.sub(r"\s+", "", cells[0])
        matched_code = None
        for indicator_code, aliases in FINANCIAL_ALIASES.items():
            if any(alias in row_label for alias in aliases):
                matched_code = indicator_code
                break
        if not matched_code or matched_code not in indicator_map:
            continue
        numeric_cells = []
        for cell in cells[1:]:
            match = NUMBER_RE.search(cell)
            if match:
                numeric_cells.append((cell, match.group(0)))
        if not numeric_cells:
            continue
        unit = detect_unit(recent_lines)
        current_value = parse_numeric(numeric_cells[0][1])
        if current_value is None:
            continue
        current_key = (matched_code, f"{report_year}FY", current_page, row_label)
        if current_key not in seen:
            results.append(
                {
                    "indicator_id": indicator_map[matched_code],
                    "period_label": f"{report_year}FY",
                    "value_role": "current",
                    "unit": unit,
                    "value_num": current_value,
                    "value_text": numeric_cells[0][0],
                    "source_page": current_page,
                    "source_row_label": row_label,
                }
            )
            seen.add(current_key)
        previous_value = parse_numeric(numeric_cells[1][1]) if len(numeric_cells) > 1 else None
        if previous_value is not None:
            previous_key = (matched_code, f"{report_year - 1}FY", current_page, row_label)
            if previous_key not in seen:
                results.append(
                    {
                        "indicator_id": indicator_map[matched_code],
                        "period_label": f"{report_year - 1}FY",
                        "value_role": "historical",
                        "unit": unit,
                        "value_num": previous_value,
                        "value_text": numeric_cells[1][0],
                        "source_page": current_page,
                        "source_row_label": row_label,
                    }
                )
                seen.add(previous_key)
    return results


def upsert_industry(conn, industry_name):
    if not industry_name:
        return None
    conn.execute(
        "INSERT INTO dim_industry (industry_name) VALUES (?) ON CONFLICT(industry_name) DO NOTHING",
        (industry_name,),
    )
    row = conn.execute("SELECT industry_id FROM dim_industry WHERE industry_name = ?", (industry_name,)).fetchone()
    return row["industry_id"] if row else None


def upsert_company(conn, metadata):
    industry_id = upsert_industry(conn, metadata.get("industry_name"))
    stock_code = metadata.get("stock_code")
    if stock_code:
        conn.execute(
            """
            INSERT INTO dim_company (stock_code, company_name, primary_industry_id, company_url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                company_name = excluded.company_name,
                primary_industry_id = COALESCE(excluded.primary_industry_id, dim_company.primary_industry_id),
                company_url = COALESCE(excluded.company_url, dim_company.company_url),
                updated_at = CURRENT_TIMESTAMP
            """,
            (stock_code, metadata["company_name"], industry_id, metadata.get("source_url")),
        )
        row = conn.execute("SELECT company_id FROM dim_company WHERE stock_code = ?", (stock_code,)).fetchone()
        return row["company_id"]

    row = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (metadata["company_name"],)).fetchone()
    if row:
        conn.execute(
            """
            UPDATE dim_company
            SET primary_industry_id = COALESCE(?, primary_industry_id),
                company_url = COALESCE(?, company_url),
                updated_at = CURRENT_TIMESTAMP
            WHERE company_id = ?
            """,
            (industry_id, metadata.get("source_url"), row["company_id"]),
        )
        return row["company_id"]

    cursor = conn.execute(
        "INSERT INTO dim_company (stock_code, company_name, primary_industry_id, company_url) VALUES (?, ?, ?, ?)",
        (None, metadata["company_name"], industry_id, metadata.get("source_url")),
    )
    return cursor.lastrowid


def upsert_document(conn, company_id, metadata):
    conn.execute(
        """
        INSERT INTO dim_document (
            company_id, doc_type, report_year, title, file_name, file_path, file_hash,
            version_label, is_latest, announcement_no, publish_date, source_url,
            pages_total, parser_type, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            company_id = excluded.company_id,
            doc_type = excluded.doc_type,
            report_year = excluded.report_year,
            title = excluded.title,
            file_hash = excluded.file_hash,
            version_label = excluded.version_label,
            is_latest = 1,
            announcement_no = excluded.announcement_no,
            publish_date = excluded.publish_date,
            source_url = excluded.source_url,
            pages_total = excluded.pages_total,
            parser_type = excluded.parser_type,
            metadata_json = excluded.metadata_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            company_id,
            metadata["doc_type"],
            metadata.get("report_year"),
            metadata.get("title"),
            metadata["file_name"],
            metadata["file_path"],
            metadata.get("file_hash"),
            metadata.get("version_label"),
            metadata.get("announcement_no"),
            metadata.get("publish_date"),
            metadata.get("source_url"),
            metadata.get("pages_total"),
            metadata.get("parser_type"),
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    row = conn.execute("SELECT document_id FROM dim_document WHERE file_path = ?", (metadata["file_path"],)).fetchone()
    document_id = row["document_id"]
    conn.execute(
        """
        UPDATE dim_document
        SET is_latest = CASE WHEN document_id = ? THEN 1 ELSE 0 END,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = ? AND doc_type = ? AND COALESCE(report_year, -1) = COALESCE(?, -1)
        """,
        (document_id, company_id, metadata["doc_type"], metadata.get("report_year")),
    )
    return document_id


def purge_document_records(conn, collection, document_id):
    rows = conn.execute("SELECT vector_id FROM map_vector_chunk WHERE document_id = ?", (document_id,)).fetchall()
    ids = [row["vector_id"] for row in rows]
    if ids:
        collection.delete(ids=ids)
    conn.execute("DELETE FROM map_vector_chunk WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM fact_financial_report WHERE document_id = ?", (document_id,))


def persist_chunks(conn, collection, document_id, metadata, chunks, embedding_client, batch_size=16):
    records = []
    for chunk in chunks:
        chunk_hash = hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
        vector_id = f"doc-{document_id}-chunk-{chunk['chunk_index']}-{chunk_hash[:12]}"
        chunk_metadata = {
            "source": metadata["file_name"],
            "page": chunk["page_start"],
            "doc_type": metadata["doc_type"],
            "company_name": metadata["company_name"],
            "stock_code": metadata.get("stock_code") or "",
            "report_year": metadata.get("report_year") or 0,
            "industry_name": metadata.get("industry_name") or "",
            "document_id": document_id,
            "file_path": metadata["file_path"],
            "chunk_index": chunk["chunk_index"],
        }
        records.append((vector_id, chunk, chunk_hash, chunk_metadata))

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        ids = [item[0] for item in batch]
        documents = [item[1]["text"] for item in batch]
        metadatas = [item[3] for item in batch]
        embeddings = embedding_client.embed(documents)
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        conn.executemany(
            """
            INSERT INTO map_vector_chunk (
                vector_id, document_id, chunk_index, page_start, page_end,
                char_start, char_end, chunk_hash, chunk_text_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item[0],
                    document_id,
                    item[1]["chunk_index"],
                    item[1]["page_start"],
                    item[1]["page_end"],
                    None,
                    None,
                    item[2],
                    item[1]["text"][:200],
                )
                for item in batch
            ],
        )


def persist_financial_facts(conn, document_id, facts):
    conn.executemany(
        """
        INSERT INTO fact_financial_report (
            document_id, indicator_id, period_label, statement_scope, value_role,
            currency_code, unit, value_num, value_text, source_page, source_table_title, source_row_label
        ) VALUES (?, ?, ?, 'consolidated', ?, 'CNY', ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                document_id,
                fact["indicator_id"],
                fact["period_label"],
                fact["value_role"],
                fact["unit"],
                fact["value_num"],
                fact["value_text"],
                fact["source_page"],
                None,
                fact["source_row_label"],
            )
            for fact in facts
        ],
    )


def ingest_document(path, conn, collection, splitter, embedding_client, explicit_doc_type=None, industry_name=None):
    parsed_document = load_document(path, explicit_doc_type, industry_name)
    company_id = upsert_company(conn, parsed_document.metadata)
    document_id = upsert_document(conn, company_id, parsed_document.metadata)
    purge_document_records(conn, collection, document_id)
    chunks = split_document(parsed_document, splitter)
    persist_chunks(conn, collection, document_id, parsed_document.metadata, chunks, embedding_client)
    facts = extract_financial_facts(parsed_document, conn)
    if facts:
        persist_financial_facts(conn, document_id, facts)
    return {
        "file_name": path.name,
        "document_id": document_id,
        "company_name": parsed_document.metadata["company_name"],
        "doc_type": parsed_document.metadata["doc_type"],
        "chunks": len(chunks),
        "facts": len(facts),
    }


def import_macro_csv(csv_path, conn):
    csv_path = Path(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"indicator_code", "period_date", "value_num"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("宏观 CSV 至少需要列: indicator_code, period_date, value_num")
        for row in reader:
            conn.execute(
                """
                INSERT INTO fact_macro_data (
                    macro_indicator_id, period_date, region_name, value_num, unit, release_date, source_file
                )
                SELECT macro_indicator_id, ?, ?, ?, ?, ?, ?
                FROM dict_macro_indicator WHERE indicator_code = ?
                """,
                (
                    row["period_date"],
                    row.get("region_name") or "全国",
                    float(row["value_num"]),
                    row.get("unit"),
                    row.get("release_date"),
                    csv_path.name,
                    row["indicator_code"],
                ),
            )


def collect_files(input_dir):
    files = []
    for pattern in ("*.md", "*.pdf"):
        for path in sorted(Path(input_dir).glob(pattern)):
            if path.name.startswith("._"):
                continue
            files.append(path)
    return files


def parse_args():
    parser = argparse.ArgumentParser(description="企业文档数据处理流水线")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库文件路径")
    parser.add_argument("--chroma-path", default=str(DEFAULT_CHROMA_PATH), help="Chroma 持久化目录")
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION, help="Chroma collection 名称")
    parser.add_argument("--input-dir", help="文档目录，默认自动识别 reports_md/report_md")
    parser.add_argument("--doc-type", choices=["annual_report", "research_report"], help="显式指定文档类型")
    parser.add_argument("--industry-name", help="显式指定行业名称")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--limit", type=int, help="仅处理前 N 个文件")
    parser.add_argument("--macro-csv", help="导入宏观数据 CSV 文件")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = None
    try:
        conn = get_connection(args.db_path)
        collection = get_collection(args.chroma_path, args.collection_name)
        splitter = get_splitter(args.chunk_size, args.chunk_overlap)
        embedding_client = get_embedding_client()

        if args.macro_csv:
            import_macro_csv(args.macro_csv, conn)
            conn.commit()
            print(f"宏观 CSV 导入完成: {args.macro_csv}")
            return

        input_dir = resolve_input_dir(args.input_dir)
        files = collect_files(input_dir)
        if args.limit:
            files = files[: args.limit]
        if not files:
            raise SystemExit(f"目录中没有可处理文件: {input_dir}")

        for path in files:
            result = ingest_document(path, conn, collection, splitter, embedding_client, args.doc_type, args.industry_name)
            conn.commit()
            print(
                f"已导入 {result['file_name']} | 公司={result['company_name']} | 类型={result['doc_type']} | "
                f"chunks={result['chunks']} | facts={result['facts']}"
            )
    except Exception as exc:
        if conn:
            conn.rollback()
        raise SystemExit(f"处理失败: {exc}") from exc
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
