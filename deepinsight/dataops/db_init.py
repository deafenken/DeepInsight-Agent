import argparse
import sqlite3
from pathlib import Path

from deepinsight.config import CHROMA_DIR, DB_PATH

DEFAULT_DB_PATH = DB_PATH
DEFAULT_CHROMA_PATH = CHROMA_DIR
DEFAULT_COLLECTION = "enterprise_documents"

FINANCIAL_INDICATORS = [
    ("revenue", "营业收入", "income_statement", "amount", "元", "营业总收入,主营业务收入"),
    ("net_profit_parent", "归属于上市公司股东的净利润", "income_statement", "amount", "元", "归母净利润,归属于上市公司股东的净利润"),
    ("net_profit_deducted", "归属于上市公司股东的扣除非经常性损益的净利润", "income_statement", "amount", "元", "扣非净利润"),
    ("operating_cash_flow", "经营活动产生的现金流量净额", "cash_flow", "amount", "元", "经营现金流净额"),
    ("total_assets", "总资产", "balance_sheet", "amount", "元", "资产总额"),
    ("net_assets_parent", "归属于上市公司股东的净资产", "balance_sheet", "amount", "元", "归母净资产"),
    ("gross_margin", "毛利率", "kpi", "ratio", "%", "销售毛利率"),
    ("debt_ratio", "资产负债率", "kpi", "ratio", "%", "负债率"),
    ("rd_expense", "研发费用", "income_statement", "amount", "元", "研发投入,研发支出"),
    ("roe", "净资产收益率", "kpi", "ratio", "%", "ROE,加权平均净资产收益率"),
]

MACRO_INDICATORS = [
    ("gdp", "国内生产总值", "quarterly", "亿元", "国家统计局"),
    ("cpi", "居民消费价格指数", "monthly", "%", "国家统计局"),
    ("ppi", "工业生产者出厂价格指数", "monthly", "%", "国家统计局"),
    ("m2", "广义货币M2", "monthly", "%", "中国人民银行"),
]


def get_connection(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.DatabaseError:
        pass
    return conn


def create_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dim_industry (
            industry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            industry_code TEXT UNIQUE,
            industry_name TEXT NOT NULL UNIQUE,
            industry_level INTEGER,
            parent_industry_id INTEGER,
            FOREIGN KEY (parent_industry_id) REFERENCES dim_industry(industry_id)
        );

        CREATE TABLE IF NOT EXISTS dim_company (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT UNIQUE,
            company_name TEXT NOT NULL,
            company_short_name TEXT,
            exchange TEXT,
            primary_industry_id INTEGER,
            company_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_name, stock_code),
            FOREIGN KEY (primary_industry_id) REFERENCES dim_industry(industry_id)
        );

        CREATE TABLE IF NOT EXISTS dict_financial_indicator (
            indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_code TEXT NOT NULL UNIQUE,
            indicator_name TEXT NOT NULL,
            statement_category TEXT NOT NULL,
            value_type TEXT NOT NULL,
            default_unit TEXT,
            aliases TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(indicator_name, statement_category)
        );

        CREATE TABLE IF NOT EXISTS dim_document (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            report_year INTEGER,
            title TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            file_hash TEXT,
            version_label TEXT,
            is_latest INTEGER NOT NULL DEFAULT 1,
            announcement_no TEXT,
            publish_date TEXT,
            source_url TEXT,
            pages_total INTEGER,
            parser_type TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES dim_company(company_id)
        );

        CREATE TABLE IF NOT EXISTS fact_financial_report (
            report_fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            indicator_id INTEGER NOT NULL,
            period_label TEXT NOT NULL,
            statement_scope TEXT NOT NULL DEFAULT 'consolidated',
            value_role TEXT NOT NULL DEFAULT 'current',
            currency_code TEXT NOT NULL DEFAULT 'CNY',
            unit TEXT,
            value_num REAL,
            value_text TEXT,
            source_page INTEGER,
            source_table_title TEXT,
            source_row_label TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, indicator_id, period_label, statement_scope, value_role, source_page, source_row_label),
            FOREIGN KEY (document_id) REFERENCES dim_document(document_id) ON DELETE CASCADE,
            FOREIGN KEY (indicator_id) REFERENCES dict_financial_indicator(indicator_id)
        );

        CREATE TABLE IF NOT EXISTS dict_macro_indicator (
            macro_indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_code TEXT NOT NULL UNIQUE,
            indicator_name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            default_unit TEXT,
            source_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS fact_macro_data (
            macro_fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            macro_indicator_id INTEGER NOT NULL,
            period_date TEXT NOT NULL,
            region_name TEXT NOT NULL DEFAULT '全国',
            value_num REAL NOT NULL,
            unit TEXT,
            release_date TEXT,
            source_file TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(macro_indicator_id, period_date, region_name, source_file),
            FOREIGN KEY (macro_indicator_id) REFERENCES dict_macro_indicator(macro_indicator_id)
        );

        CREATE TABLE IF NOT EXISTS map_vector_chunk (
            map_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vector_id TEXT NOT NULL UNIQUE,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            char_start INTEGER,
            char_end INTEGER,
            chunk_hash TEXT NOT NULL,
            chunk_text_preview TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, chunk_index),
            FOREIGN KEY (document_id) REFERENCES dim_document(document_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_company_name ON dim_company(company_name);
        CREATE INDEX IF NOT EXISTS idx_company_industry ON dim_company(primary_industry_id);
        CREATE INDEX IF NOT EXISTS idx_document_company_year_type ON dim_document(company_id, report_year, doc_type, is_latest);
        CREATE INDEX IF NOT EXISTS idx_fact_financial_document ON fact_financial_report(document_id);
        CREATE INDEX IF NOT EXISTS idx_fact_financial_indicator_period ON fact_financial_report(indicator_id, period_label);
        CREATE INDEX IF NOT EXISTS idx_fact_macro_indicator_period ON fact_macro_data(macro_indicator_id, period_date);
        CREATE INDEX IF NOT EXISTS idx_chunk_document_page ON map_vector_chunk(document_id, page_start, page_end);
        """
    )


def seed_indicators(conn):
    conn.executemany(
        """
        INSERT INTO dict_financial_indicator (
            indicator_code, indicator_name, statement_category, value_type, default_unit, aliases
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(indicator_code) DO UPDATE SET
            indicator_name = excluded.indicator_name,
            statement_category = excluded.statement_category,
            value_type = excluded.value_type,
            default_unit = excluded.default_unit,
            aliases = excluded.aliases
        """,
        FINANCIAL_INDICATORS,
    )
    conn.executemany(
        """
        INSERT INTO dict_macro_indicator (
            indicator_code, indicator_name, frequency, default_unit, source_name
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(indicator_code) DO UPDATE SET
            indicator_name = excluded.indicator_name,
            frequency = excluded.frequency,
            default_unit = excluded.default_unit,
            source_name = excluded.source_name
        """,
        MACRO_INDICATORS,
    )


def init_chroma(chroma_path, collection_name):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("未安装 chromadb，请先安装依赖后再初始化向量库。") from exc

    chroma_path = Path(chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "企业年报与研报文本块",
            "metadata_fields": "source,page,doc_type,company_name,industry_name,report_year",
        },
    )


def parse_args():
    parser = argparse.ArgumentParser(description="初始化 SQLite 和 ChromaDB")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库文件路径")
    parser.add_argument("--chroma-path", default=str(DEFAULT_CHROMA_PATH), help="Chroma 持久化目录")
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION, help="Chroma collection 名称")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = None
    try:
        conn = get_connection(args.db_path)
        create_tables(conn)
        seed_indicators(conn)
        conn.commit()
        collection = init_chroma(args.chroma_path, args.collection_name)
        print(f"SQLite 初始化完成: {args.db_path}")
        print(f"Chroma 初始化完成: {args.chroma_path}/{collection.name}")
    except Exception as exc:
        if conn:
            conn.rollback()
        raise SystemExit(f"初始化失败: {exc}") from exc
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
