import argparse
import csv
import errno
import hashlib
import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from deepinsight.config import ALT_REPORTS_DIR, CHROMA_DIR, DB_PATH, FINAL_REPORTS_DIR, REPORTS_DIR
from deepinsight.core.industry_taxonomy import PRIMARY_INDUSTRY_NAME, infer_industry_name, infer_industry_path

DEFAULT_DB_PATH = DB_PATH
DEFAULT_CHROMA_PATH = CHROMA_DIR
DEFAULT_COLLECTION = "enterprise_documents"
DEFAULT_INPUT_DIRS = [FINAL_REPORTS_DIR, REPORTS_DIR, ALT_REPORTS_DIR]
DEFAULT_BUSY_TIMEOUT_MS = 60000
DEFAULT_LOCKFILE_NAME = ".data_pipeline.lock"
PAGE_INLINE_RE = re.compile(r"^\**\s*(\d{1,4})\s*/\s*(\d{1,4})\s*\**$")
PAGE_SINGLE_RE = re.compile(r"^\d{1,4}$")
PICTURE_PLACEHOLDER_RE = re.compile(r"^\**\s*==>\s*picture\s*\[[^\]]+\]\s*intentionally omitted\s*<==\s*\**$", re.IGNORECASE)
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
    "total_assets": ["总资产", "资产总额", "资产总计"],
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
    conn = sqlite3.connect(db_path, timeout=DEFAULT_BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS}")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.DatabaseError:
        pass
    return conn


@contextmanager
def pipeline_lock(db_path):
    lock_path = Path(db_path).with_name(DEFAULT_LOCKFILE_NAME)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        try:
            import fcntl
        except ImportError:
            yield
            return
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise SystemExit("已有导入任务正在运行，请等待当前任务完成后再重试。") from exc
            raise
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        yield
    finally:
        try:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            lock_file.close()
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


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
    raise FileNotFoundError("未找到 Final_md、reports_md 或 report_md 目录。")


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


def normalize_page_marker(value):
    return value.strip().replace("*", "")


def is_picture_placeholder_line(line):
    return bool(PICTURE_PLACEHOLDER_RE.match((line or "").strip()))


def collect_meaningful_lines(lines):
    meaningful = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or is_picture_placeholder_line(stripped):
            continue
        meaningful.append(raw_line.rstrip())
    return meaningful


def summarize_text_quality(lines):
    non_empty_lines = [line for line in lines if line.strip()]
    meaningful_lines = collect_meaningful_lines(lines)
    return {
        "non_empty_line_count": len(non_empty_lines),
        "picture_placeholder_lines": sum(1 for line in non_empty_lines if is_picture_placeholder_line(line)),
        "meaningful_line_count": len(meaningful_lines),
        "has_meaningful_text": bool(meaningful_lines),
        "meaningful_text_ratio": (len(meaningful_lines) / len(non_empty_lines)) if non_empty_lines else 0.0,
    }


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
        marker = PAGE_INLINE_RE.match(normalize_page_marker(line))
        if marker:
            flush()
            buffer = []
            current_page = int(marker.group(1))
            total_pages = int(marker.group(2))
            continue
        if is_single_page_marker(lines, index):
            flush()
            buffer = []
            current_page = int(normalize_page_marker(line))
            continue
        if is_picture_placeholder_line(line):
            continue
        buffer.append(raw_line.rstrip())

    flush()
    if not pages:
        fallback_text = "\n".join(collect_meaningful_lines(lines)).strip()
        if fallback_text:
            pages.append(ParsedPage(page_no=1, text=fallback_text))
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
    metadata.update(summarize_text_quality(lines))
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
    lines = raw_text.splitlines()
    metadata = extract_document_metadata(path, raw_text, lines, explicit_doc_type, industry_name)
    metadata.update(summarize_text_quality(lines))
    metadata["pages_total"] = len(pdf.pages)
    fallback_pages = pages or ([ParsedPage(page_no=1, text=raw_text)] if raw_text.strip() else [])
    return ParsedDocument(metadata=metadata, pages=fallback_pages, raw_text=raw_text, lines=lines)


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
        fallback_text = "\n".join(collect_meaningful_lines(parsed_document.lines)).strip()
        if not fallback_text:
            return []
        chunks.append({"chunk_index": 0, "page_start": 1, "page_end": 1, "text": fallback_text[:500]})
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


def normalize_indicator_text(text):
    cleaned = (text or "").replace("<br>", "").replace("（", "(").replace("）", ")")
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", cleaned)
    return cleaned


def match_indicator_code(text, allowed_codes=None):
    normalized = normalize_indicator_text(text)
    if not normalized:
        return None
    candidate_codes = allowed_codes or FINANCIAL_ALIASES.keys()
    for indicator_code in candidate_codes:
        aliases = FINANCIAL_ALIASES.get(indicator_code, [])
        if any(normalize_indicator_text(alias) in normalized for alias in aliases):
            return indicator_code
    return None


def iter_document_lines(parsed_document):
    current_page = None
    for index, raw_line in enumerate(parsed_document.lines):
        line = raw_line.strip()
        marker = PAGE_INLINE_RE.match(normalize_page_marker(line))
        if marker:
            current_page = int(marker.group(1))
            continue
        if is_single_page_marker(parsed_document.lines, index):
            current_page = int(normalize_page_marker(line))
            continue
        yield current_page, raw_line.rstrip()


def is_numeric_value_line(line):
    values = NUMBER_RE.findall(line or "")
    if not values:
        return False
    residual = NUMBER_RE.sub("", line)
    residual = re.sub(r"[%％,，\.\-—–\s/()（）元股]", "", residual)
    return not residual


def is_financial_noise_line(line):
    stripped = (line or "").strip()
    if not stripped or stripped == "---":
        return True
    lowered = stripped.lower()
    if "年度报告全文" in stripped or "年年度报告" in stripped:
        return True
    if "picture intentionally omitted" in lowered:
        return True
    if PAGE_SINGLE_RE.match(normalize_page_marker(stripped)):
        return True
    return False


def append_financial_fact(results, seen, indicator_map, indicator_code, report_year, value_num, value_text, source_page, source_row_label, unit, value_role):
    if indicator_code not in indicator_map or value_num is None:
        return
    year = report_year if value_role == "current" else report_year - 1
    fact_key = (indicator_code, f"{year}FY", source_page, source_row_label, value_role)
    if fact_key in seen:
        return
    results.append(
        {
            "indicator_id": indicator_map[indicator_code],
            "period_label": f"{year}FY",
            "value_role": value_role,
            "unit": unit,
            "value_num": value_num,
            "value_text": value_text,
            "source_page": source_page,
            "source_row_label": source_row_label,
        }
    )
    seen.add(fact_key)


def infer_unit_for_indicator(indicator_code, label_text, context_lines):
    inferred = detect_unit(context_lines)
    if inferred:
        return inferred
    if indicator_code in {"gross_margin", "debt_ratio", "roe"} or "%" in (label_text or ""):
        return "%"
    return "元"


def extract_table_financial_facts(parsed_document, indicator_map, report_year, results, seen):
    current_page = None
    recent_lines = []
    for index, raw_line in enumerate(parsed_document.lines):
        line = raw_line.strip().replace("**", "")
        marker = PAGE_INLINE_RE.match(line)
        if marker:
            current_page = int(marker.group(1))
            continue
        if is_single_page_marker(parsed_document.lines, index):
            current_page = int(normalize_page_marker(line))
            continue
        recent_lines.append(raw_line)
        recent_lines = recent_lines[-5:]
        if not line.startswith("|"):
            continue
        cells = [cell.strip().replace("<br>", " ") for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        row_label = re.sub(r"\s+", "", cells[0])
        matched_code = match_indicator_code(row_label)
        if not matched_code:
            continue
        numeric_cells = []
        for cell in cells[1:]:
            match = NUMBER_RE.search(cell)
            if match:
                numeric_cells.append((cell, match.group(0)))
        if not numeric_cells:
            continue
        unit = infer_unit_for_indicator(matched_code, row_label, recent_lines)
        current_value = parse_numeric(numeric_cells[0][1])
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            current_value,
            numeric_cells[0][0],
            current_page,
            row_label,
            unit,
            "current",
        )
        previous_value = parse_numeric(numeric_cells[1][1]) if len(numeric_cells) > 1 else None
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            previous_value,
            numeric_cells[1][0] if len(numeric_cells) > 1 else None,
            current_page,
            row_label,
            unit,
            "historical",
        )


def collect_stacked_financial_blocks(parsed_document):
    section = None
    phase = "current"
    text_buffer = []
    numeric_values = []
    numeric_texts = []
    numeric_page = None
    blocks = []

    def flush():
        nonlocal text_buffer, numeric_values, numeric_texts, numeric_page
        if numeric_values:
            blocks.append(
                {
                    "section": section,
                    "phase": phase,
                    "label_text": "".join(text_buffer[-8:]),
                    "values": list(numeric_values),
                    "value_texts": list(numeric_texts),
                    "source_page": numeric_page,
                    "context_lines": list(text_buffer[-8:]),
                }
            )
        text_buffer = []
        numeric_values = []
        numeric_texts = []
        numeric_page = None

    for page_no, raw_line in iter_document_lines(parsed_document):
        line = raw_line.strip()
        if not line:
            continue
        normalized = normalize_indicator_text(line)
        if "主要会计数据和财务指标" in line or (section != "main_data" and "主要会计数据" in normalized and "分季度" not in line):
            flush()
            section = "main_data"
            phase = "current"
            continue
        if "主要财务指标" in line and "分季度" not in line and section != "main_kpi":
            flush()
            section = "main_kpi"
            phase = "current"
            continue
        if any(marker in line for marker in ["分季度主要财务指标", "分季度主要会计数据", "非经常性损益项目和金额", "非经常性损益项目及金额"]):
            flush()
            section = None
            phase = "current"
            continue
        if section is None:
            continue
        if any(token in line for token in ["年末", "本年末", "本期末"]):
            flush()
            phase = "year_end"
            text_buffer.append(line)
            continue
        if is_financial_noise_line(line):
            continue
        if is_numeric_value_line(line):
            if numeric_page is None:
                numeric_page = page_no
            values = NUMBER_RE.findall(line)
            numeric_values.extend(values)
            numeric_texts.extend([line] * len(values))
            continue
        if numeric_values:
            flush()
        text_buffer.append(line)
    flush()
    return blocks


def extract_stacked_financial_facts(parsed_document, indicator_map, report_year, results, seen):
    blocks = collect_stacked_financial_blocks(parsed_document)
    current_order = ["revenue", "net_profit_parent", "net_profit_deducted", "operating_cash_flow"]
    current_index = 0
    for block in blocks:
        values = block["values"]
        if len(values) < 2:
            continue
        matched_code = None
        if block["section"] == "main_data" and block["phase"] == "current":
            matched_code = match_indicator_code(block["label_text"], current_order)
            if not matched_code and current_index < len(current_order):
                matched_code = current_order[current_index]
            if matched_code in current_order and current_index < len(current_order):
                current_index += 1
        elif block["section"] == "main_data" and block["phase"] == "year_end":
            matched_code = match_indicator_code(block["label_text"], ["net_assets_parent", "total_assets"])
        elif block["section"] == "main_kpi":
            matched_code = match_indicator_code(block["label_text"], ["roe"])
        if not matched_code:
            continue
        unit = infer_unit_for_indicator(matched_code, block["label_text"], block["context_lines"])
        source_row_label = normalize_indicator_text(block["label_text"]) or matched_code
        current_value = parse_numeric(values[0])
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            current_value,
            block["value_texts"][0],
            block["source_page"],
            source_row_label,
            unit,
            "current",
        )
        previous_index = 2 if len(values) >= 6 else 1
        previous_value = parse_numeric(values[previous_index]) if len(values) > previous_index else None
        previous_text = block["value_texts"][previous_index] if len(block["value_texts"]) > previous_index else None
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            previous_value,
            previous_text,
            block["source_page"],
            source_row_label,
            unit,
            "historical",
        )


def extract_explicit_financial_facts(parsed_document, indicator_map, report_year, results, seen):
    target_codes = ["revenue", "net_profit_parent", "net_profit_deducted", "operating_cash_flow", "total_assets", "net_assets_parent", "roe"]
    id_to_code = {indicator_id: indicator_code for indicator_code, indicator_id in indicator_map.items()}
    existing_codes = {
        id_to_code[fact["indicator_id"]]
        for fact in results
        if fact["value_role"] == "current" and fact["indicator_id"] in id_to_code
    }
    remaining_codes = [code for code in target_codes if code not in existing_codes]
    if not remaining_codes:
        return

    entries = list(iter_document_lines(parsed_document))
    index = 0
    while index < len(entries):
        page_no, raw_line = entries[index]
        line = raw_line.strip()
        if not line or is_financial_noise_line(line):
            index += 1
            continue
        label_text = line
        matched_code = match_indicator_code(label_text, remaining_codes)
        cursor = index + 1
        while not matched_code and cursor < len(entries):
            next_line = entries[cursor][1].strip()
            if not next_line or is_financial_noise_line(next_line) or is_numeric_value_line(next_line):
                break
            label_text += next_line
            matched_code = match_indicator_code(label_text, remaining_codes)
            cursor += 1
        if not matched_code:
            index += 1
            continue

        values = []
        value_texts = []
        inline_numbers = NUMBER_RE.findall(line) if match_indicator_code(line, [matched_code]) else []
        if inline_numbers and not is_numeric_value_line(line):
            values.extend(inline_numbers)
            value_texts.extend([line] * len(inline_numbers))

        scan = cursor if cursor > index + 1 else index + 1
        while scan < len(entries) and len(values) < 6:
            next_line = entries[scan][1].strip()
            if not next_line or is_financial_noise_line(next_line):
                scan += 1
                continue
            if is_numeric_value_line(next_line):
                matches = NUMBER_RE.findall(next_line)
                values.extend(matches)
                value_texts.extend([next_line] * len(matches))
                scan += 1
                continue
            if values:
                break
            if match_indicator_code(next_line, remaining_codes):
                break
            label_text += next_line
            scan += 1
        if len(values) < 2:
            index += 1
            continue

        unit = infer_unit_for_indicator(matched_code, label_text, [label_text])
        source_row_label = FINANCIAL_ALIASES.get(matched_code, [matched_code])[0]
        current_value = parse_numeric(values[0])
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            current_value,
            value_texts[0],
            page_no,
            source_row_label,
            unit,
            "current",
        )
        previous_index = 2 if len(values) >= 6 else 1
        previous_value = parse_numeric(values[previous_index]) if len(values) > previous_index else None
        previous_text = value_texts[previous_index] if len(value_texts) > previous_index else None
        append_financial_fact(
            results,
            seen,
            indicator_map,
            matched_code,
            report_year,
            previous_value,
            previous_text,
            page_no,
            source_row_label,
            unit,
            "historical",
        )
        remaining_codes = [code for code in remaining_codes if code != matched_code]
        if not remaining_codes:
            return
        index = scan


def extract_financial_facts(parsed_document, conn):
    indicator_map = find_indicator_id_map(conn)
    report_year = parsed_document.metadata.get("report_year")
    if not report_year:
        return []

    results = []
    seen = set()
    extract_table_financial_facts(parsed_document, indicator_map, report_year, results, seen)
    extract_stacked_financial_facts(parsed_document, indicator_map, report_year, results, seen)
    extract_explicit_financial_facts(parsed_document, indicator_map, report_year, results, seen)
    return results


def upsert_industry(conn, industry_name):
    if not industry_name:
        return None
    conn.execute(
        """
        INSERT INTO dim_industry (industry_name, industry_level)
        VALUES (?, ?)
        ON CONFLICT(industry_name) DO UPDATE SET industry_level = COALESCE(dim_industry.industry_level, excluded.industry_level)
        """,
        (industry_name, 1 if industry_name == PRIMARY_INDUSTRY_NAME else 2),
    )
    row = conn.execute("SELECT industry_id FROM dim_industry WHERE industry_name = ?", (industry_name,)).fetchone()
    return row["industry_id"] if row else None


def upsert_industry_hierarchy(conn, company_name, industry_name=None):
    path = infer_industry_path(company_name, industry_name)
    if not path:
        return None
    parent_id = None
    current_id = None
    for level, name in enumerate(path, start=1):
        conn.execute(
            """
            INSERT INTO dim_industry (industry_name, industry_level, parent_industry_id)
            VALUES (?, ?, ?)
            ON CONFLICT(industry_name) DO UPDATE SET
                industry_level = COALESCE(dim_industry.industry_level, excluded.industry_level),
                parent_industry_id = COALESCE(dim_industry.parent_industry_id, excluded.parent_industry_id)
            """,
            (name, level, parent_id),
        )
        row = conn.execute("SELECT industry_id FROM dim_industry WHERE industry_name = ?", (name,)).fetchone()
        current_id = row["industry_id"] if row else None
        parent_id = current_id
    return current_id


def upsert_company(conn, metadata):
    resolved_industry_name = infer_industry_name(metadata.get("company_name"), metadata.get("industry_name"))
    metadata["industry_name"] = resolved_industry_name
    industry_id = upsert_industry_hierarchy(conn, metadata.get("company_name"), resolved_industry_name)
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


def purge_superseded_document_records(conn, collection, company_id, metadata, keep_document_id):
    rows = conn.execute(
        """
        SELECT document_id
        FROM dim_document
        WHERE company_id = ?
          AND doc_type = ?
          AND COALESCE(report_year, -1) = COALESCE(?, -1)
          AND document_id != ?
        """,
        (company_id, metadata["doc_type"], metadata.get("report_year"), keep_document_id),
    ).fetchall()
    for row in rows:
        purge_document_records(conn, collection, row["document_id"])


def persist_chunks(conn, collection, document_id, metadata, chunks, embedding_client, batch_size=64):
    if not chunks:
        return
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


def is_document_materialized(conn, document_id):
    row = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM map_vector_chunk WHERE document_id = ?) AS has_chunks",
        (document_id,),
    ).fetchone()
    return bool(row["has_chunks"]) if row else False


def has_financial_facts(conn, document_id):
    row = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM fact_financial_report WHERE document_id = ?) AS has_facts",
        (document_id,),
    ).fetchone()
    return bool(row["has_facts"]) if row else False


def ingest_document(
    path,
    conn,
    collection,
    splitter,
    embedding_client,
    explicit_doc_type=None,
    industry_name=None,
    batch_size=64,
    force=False,
):
    parsed_document = load_document(path, explicit_doc_type, industry_name)
    company_id = upsert_company(conn, parsed_document.metadata)
    existing = conn.execute(
        "SELECT document_id, file_hash FROM dim_document WHERE file_path = ?",
        (parsed_document.metadata["file_path"],),
    ).fetchone()
    document_id = upsert_document(conn, company_id, parsed_document.metadata)
    purge_superseded_document_records(conn, collection, company_id, parsed_document.metadata, document_id)
    if (
        not force
        and
        existing
        and existing["document_id"] == document_id
        and existing["file_hash"] == parsed_document.metadata.get("file_hash")
        and (is_document_materialized(conn, document_id) or not parsed_document.metadata.get("has_meaningful_text", True))
    ):
        return {
            "file_name": path.name,
            "document_id": document_id,
            "company_name": parsed_document.metadata["company_name"],
            "doc_type": parsed_document.metadata["doc_type"],
            "chunks": 0,
            "facts": 0,
            "skipped": True,
            "no_meaningful_text": not parsed_document.metadata.get("has_meaningful_text", True),
        }
    purge_document_records(conn, collection, document_id)
    chunks = split_document(parsed_document, splitter)
    persist_chunks(conn, collection, document_id, parsed_document.metadata, chunks, embedding_client, batch_size=batch_size)
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
        "skipped": False,
        "no_meaningful_text": not parsed_document.metadata.get("has_meaningful_text", True),
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
        for path in sorted(Path(input_dir).rglob(pattern)):
            if path.name.startswith("._"):
                continue
            files.append(path)
    return files


def audit_document_text_quality(path, explicit_doc_type=None, industry_name=None):
    parsed_document = load_document(path, explicit_doc_type, industry_name)
    metadata = parsed_document.metadata
    return {
        "file_name": path.name,
        "file_path": str(path),
        "company_name": metadata.get("company_name"),
        "doc_type": metadata.get("doc_type"),
        "report_year": metadata.get("report_year"),
        "parser_type": metadata.get("parser_type"),
        "non_empty_line_count": metadata.get("non_empty_line_count", 0),
        "picture_placeholder_lines": metadata.get("picture_placeholder_lines", 0),
        "meaningful_line_count": metadata.get("meaningful_line_count", 0),
        "meaningful_text_ratio": metadata.get("meaningful_text_ratio", 0.0),
        "has_meaningful_text": metadata.get("has_meaningful_text", True),
    }


def audit_text_quality(files, explicit_doc_type=None, industry_name=None, min_text_ratio=0.05):
    results = []
    for path in files:
        audit_row = audit_document_text_quality(path, explicit_doc_type, industry_name)
        if (not audit_row["has_meaningful_text"]) or audit_row["meaningful_text_ratio"] < min_text_ratio:
            results.append(audit_row)
    results.sort(key=lambda row: (row["meaningful_line_count"], row["meaningful_text_ratio"], row["file_path"]))
    return results


def write_text_quality_audit(audit_rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "company_name",
        "report_year",
        "doc_type",
        "file_name",
        "file_path",
        "parser_type",
        "non_empty_line_count",
        "picture_placeholder_lines",
        "meaningful_line_count",
        "meaningful_text_ratio",
        "has_meaningful_text",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit_rows:
            writer.writerow(row)


def backfill_company_industries(conn):
    rows = conn.execute("SELECT company_id, company_name FROM dim_company ORDER BY company_id").fetchall()
    updated = 0
    for row in rows:
        industry_id = upsert_industry_hierarchy(conn, row["company_name"])
        conn.execute(
            """
            UPDATE dim_company
            SET primary_industry_id = COALESCE(?, primary_industry_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE company_id = ?
            """,
            (industry_id, row["company_id"]),
        )
        updated += 1
    return updated


def parse_args():
    parser = argparse.ArgumentParser(description="企业文档数据处理流水线")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库文件路径")
    parser.add_argument("--chroma-path", default=str(DEFAULT_CHROMA_PATH), help="Chroma 持久化目录")
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION, help="Chroma collection 名称")
    parser.add_argument("--input-dir", help="文档目录，默认自动识别 Final_md/reports_md/report_md")
    parser.add_argument("--doc-type", choices=["annual_report", "research_report"], help="显式指定文档类型")
    parser.add_argument("--industry-name", help="显式指定行业名称")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64, help="Chroma 写入批次大小")
    parser.add_argument("--force", action="store_true", help="强制重跑文档，即使文件未变化且已入库")
    parser.add_argument("--limit", type=int, help="仅处理前 N 个文件")
    parser.add_argument("--audit-text-quality", action="store_true", help="扫描文档文本质量，找出空文本或疑似 OCR 风险文档")
    parser.add_argument("--audit-output", help="将文本质量审计结果写入 CSV")
    parser.add_argument("--min-text-ratio", type=float, default=0.05, help="文本质量审计阈值，低于该占比的文档会被标记")
    parser.add_argument("--backfill-industries", action="store_true", help="为现有公司回填医药行业与细分赛道标签")
    parser.add_argument("--macro-csv", help="导入宏观数据 CSV 文件")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = None
    try:
        if args.audit_text_quality:
            input_dir = resolve_input_dir(args.input_dir)
            files = collect_files(input_dir)
            if args.limit:
                files = files[: args.limit]
            if not files:
                raise SystemExit(f"目录中没有可处理文件: {input_dir}")
            audit_rows = audit_text_quality(files, args.doc_type, args.industry_name, args.min_text_ratio)
            print(f"文本质量审计完成 | 总文件={len(files)} | 风险文件={len(audit_rows)} | 阈值={args.min_text_ratio:.2%}")
            for row in audit_rows[:20]:
                print(
                    f"风险文档 {row['file_name']} | 公司={row['company_name']} | 年份={row['report_year']} | "
                    f"正文行={row['meaningful_line_count']} | 非空行={row['non_empty_line_count']} | "
                    f"占位图={row['picture_placeholder_lines']} | 文本占比={row['meaningful_text_ratio']:.2%}"
                )
            if args.audit_output:
                write_text_quality_audit(audit_rows, args.audit_output)
                print(f"审计结果已写入: {args.audit_output}")
            return
        with pipeline_lock(args.db_path):
            conn = get_connection(args.db_path)
            collection = get_collection(args.chroma_path, args.collection_name)
            splitter = get_splitter(args.chunk_size, args.chunk_overlap)
            embedding_client = get_embedding_client()

            if args.backfill_industries:
                updated = backfill_company_industries(conn)
                conn.commit()
                print(f"行业标签回填完成 | 公司数={updated}")
                return

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
                result = ingest_document(
                    path,
                    conn,
                    collection,
                    splitter,
                    embedding_client,
                    args.doc_type,
                    args.industry_name,
                    args.batch_size,
                    args.force,
                )
                conn.commit()
                if result.get("skipped"):
                    reason = "文件未变化且已完成入库"
                    if result.get("no_meaningful_text"):
                        reason = "文件未变化且源文档无可抽取正文"
                    print(
                        f"已跳过 {result['file_name']} | 公司={result['company_name']} | 类型={result['doc_type']} | "
                        f"原因={reason}"
                    )
                    continue
                suffix = " | 状态=源文档无可抽取正文" if result.get("no_meaningful_text") else ""
                print(
                    f"已导入 {result['file_name']} | 公司={result['company_name']} | 类型={result['doc_type']} | "
                    f"chunks={result['chunks']} | facts={result['facts']}{suffix}"
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
