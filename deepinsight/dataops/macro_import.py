import argparse
import hashlib
import re
import sqlite3
from pathlib import Path

import pandas as pd

from deepinsight.config import DB_PATH

DEFAULT_DB_PATH = DB_PATH
DEFAULT_REGION = "全国"
DEFAULT_SOURCE_NAME = "国家统计局"


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def infer_frequency(column_name):
    text = str(column_name).strip()
    return "yearly" if re.fullmatch(r"20\d{2}(?:\.0+)?", text) else "unknown"


def infer_unit(metric_name):
    name = str(metric_name)
    if any(token in name for token in ["率", "比重", "占比"]):
        return "%"
    if any(token in name for token in ["人数", "人次"]):
        return "万人"
    if "机构数" in name or name.endswith("数"):
        return "个"
    if "平均住院日" in name:
        return "日"
    return ""


def make_indicator_code(category, metric_name):
    seed = f"{category}::{metric_name}".encode("utf-8")
    return f"nbs_health_{hashlib.md5(seed).hexdigest()[:12]}"


def normalize_year(value):
    text = str(value).strip()
    match = re.match(r"(20\d{2})", text)
    if not match:
        return None
    return int(match.group(1))


def load_rows(excel_path, sheet_name=None):
    effective_sheet = 0 if sheet_name is None else sheet_name
    df = pd.read_excel(excel_path, sheet_name=effective_sheet)
    df.columns = [str(col).strip() for col in df.columns]
    required = {"大分类", "细分指标"}
    if not required.issubset(df.columns):
        raise ValueError(f"缺少必要列：{required - set(df.columns)}")
    year_columns = [col for col in df.columns if normalize_year(col) is not None]
    if not year_columns:
        raise ValueError("未识别到年份列。")
    records = []
    for _, row in df.iterrows():
        category = str(row["大分类"]).strip()
        metric_name = str(row["细分指标"]).strip()
        if not category or category == "nan" or not metric_name or metric_name == "nan":
            continue
        indicator_name = f"{category}-{metric_name}"
        for year_col in year_columns:
            raw_value = row[year_col]
            if pd.isna(raw_value):
                continue
            year = normalize_year(year_col)
            value_num = float(raw_value)
            records.append(
                {
                    "category": category,
                    "metric_name": metric_name,
                    "indicator_name": indicator_name,
                    "indicator_code": make_indicator_code(category, metric_name),
                    "period_date": f"{year}-12-31",
                    "value_num": value_num,
                    "unit": infer_unit(metric_name),
                    "frequency": infer_frequency(year_col),
                }
            )
    return records


def upsert_indicator(conn, item, source_name):
    conn.execute(
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
        (
            item["indicator_code"],
            item["indicator_name"],
            item["frequency"],
            item["unit"],
            source_name,
        ),
    )
    row = conn.execute(
        "SELECT macro_indicator_id FROM dict_macro_indicator WHERE indicator_code = ?",
        (item["indicator_code"],),
    ).fetchone()
    return row["macro_indicator_id"]


def import_macro_excel(excel_path, db_path, source_name=DEFAULT_SOURCE_NAME, region_name=DEFAULT_REGION, sheet_name=None):
    records = load_rows(excel_path, sheet_name=sheet_name)
    conn = get_connection(db_path)
    try:
        inserted = 0
        for item in records:
            macro_indicator_id = upsert_indicator(conn, item, source_name)
            conn.execute(
                """
                INSERT INTO fact_macro_data (
                    macro_indicator_id, period_date, region_name, value_num, unit, release_date, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(macro_indicator_id, period_date, region_name, source_file) DO UPDATE SET
                    value_num = excluded.value_num,
                    unit = excluded.unit,
                    release_date = excluded.release_date
                """,
                (
                    macro_indicator_id,
                    item["period_date"],
                    region_name,
                    item["value_num"],
                    item["unit"],
                    item["period_date"],
                    str(Path(excel_path).resolve()),
                ),
            )
            inserted += 1
        conn.commit()
        return inserted, len({item["indicator_code"] for item in records})
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="导入国家统计局宏观/卫生类 Excel 到 fact_macro_data")
    parser.add_argument("--excel-path", required=True, help="Excel 文件路径")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME, help="数据源名称")
    parser.add_argument("--region-name", default=DEFAULT_REGION, help="区域名称")
    parser.add_argument("--sheet-name", default=None, help="指定工作表名称")
    return parser.parse_args()


def main():
    args = parse_args()
    inserted, indicators = import_macro_excel(
        excel_path=args.excel_path,
        db_path=args.db_path,
        source_name=args.source_name,
        region_name=args.region_name,
        sheet_name=args.sheet_name,
    )
    print(f"宏观数据导入完成：records={inserted}, indicators={indicators}")


if __name__ == "__main__":
    main()
