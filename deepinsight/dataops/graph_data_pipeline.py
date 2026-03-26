import argparse
import hashlib
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

from deepinsight.config import DB_PATH

DEFAULT_DB_PATH = DB_PATH
DEFAULT_DEPTH = 3
DEFAULT_BRANCH_FACTOR = 2

RISK_TYPES = ["失信被执行", "环保处罚", "专利侵权", "劳动争议", "买卖合同纠纷"]
PATENT_TYPES = ["发明", "实用新型", "软著"]
PATENT_STATUS = ["已公开", "已授权", "审查中"]


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_company_id(conn, company_name):
    row = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (company_name,)).fetchone()
    if not row:
        raise ValueError(f"未找到公司: {company_name}")
    return row["company_id"]


def ensure_company_party(conn, company_id):
    row = conn.execute("SELECT party_id FROM dim_party WHERE company_id = ?", (company_id,)).fetchone()
    if row:
        return row["party_id"]
    cursor = conn.execute("INSERT INTO dim_party (party_type, company_id) VALUES ('company', ?)", (company_id,))
    return cursor.lastrowid


def ensure_person_party(conn, fake, person_name=None):
    name = person_name or fake.name()
    identity_hash = hashlib.md5(name.encode("utf-8")).hexdigest()
    row = conn.execute("SELECT person_id FROM dim_person WHERE identity_hash = ?", (identity_hash,)).fetchone()
    if row:
        person_id = row["person_id"]
    else:
        cursor = conn.execute(
            "INSERT INTO dim_person (person_name, person_title, identity_hash) VALUES (?, ?, ?)",
            (name, fake.job(), identity_hash),
        )
        person_id = cursor.lastrowid
    party_row = conn.execute("SELECT party_id FROM dim_party WHERE person_id = ?", (person_id,)).fetchone()
    if party_row:
        return party_row["party_id"]
    cursor = conn.execute("INSERT INTO dim_party (party_type, person_id) VALUES ('person', ?)", (person_id,))
    return cursor.lastrowid


def create_mock_company(conn, parent_name, level, index):
    company_name = f"{parent_name}-模拟{level}级子公司{index}"
    row = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", (company_name,)).fetchone()
    if row:
        return row["company_id"], company_name
    cursor = conn.execute(
        "INSERT INTO dim_company (stock_code, company_name, company_short_name, exchange) VALUES (?, ?, ?, ?)",
        (None, company_name, company_name[:20], "模拟主体"),
    )
    return cursor.lastrowid, company_name


def build_mock_hierarchy(conn, root_company_name, depth, branch_factor, fake, batch_tag):
    root_company_id = get_company_id(conn, root_company_name)
    ensure_company_party(conn, root_company_id)
    created_company_ids = [root_company_id]
    frontier = [(root_company_id, root_company_name, 1)]

    while frontier:
        parent_id, parent_name, level = frontier.pop(0)
        if level > depth:
            continue
        investor_party_id = ensure_company_party(conn, parent_id)
        for index in range(1, branch_factor + 1):
            child_company_id, child_name = create_mock_company(conn, parent_name, level, index)
            ensure_company_party(conn, child_company_id)
            equity_ratio = round(random.uniform(35, 85), 2)
            subscribed_amount = round(random.uniform(500, 5000), 2) * 10000
            conn.execute(
                """
                INSERT OR IGNORE INTO fact_investment_relation (
                    investor_party_id, investee_company_id, equity_ratio, subscribed_amount,
                    control_type, effective_date, source_type, source_note, batch_tag
                ) VALUES (?, ?, ?, ?, 'direct', ?, 'mock', ?, ?)
                """,
                (
                    investor_party_id,
                    child_company_id,
                    equity_ratio,
                    subscribed_amount,
                    f"{2020 + level}-12-31",
                    f"{root_company_name} 模拟股权结构",
                    batch_tag,
                ),
            )
            if child_company_id not in created_company_ids:
                created_company_ids.append(child_company_id)
            if level < depth:
                frontier.append((child_company_id, child_name, level + 1))
            minority_person_party = ensure_person_party(conn, fake)
            conn.execute(
                """
                INSERT OR IGNORE INTO fact_investment_relation (
                    investor_party_id, investee_company_id, equity_ratio, subscribed_amount,
                    control_type, effective_date, source_type, source_note, batch_tag
                ) VALUES (?, ?, ?, ?, 'minority', ?, 'mock', ?, ?)
                """,
                (
                    minority_person_party,
                    child_company_id,
                    round(max(5.0, 100 - equity_ratio - random.uniform(5, 20)), 2),
                    round(random.uniform(50, 500), 2) * 10000,
                    f"{2020 + level}-12-31",
                    f"{root_company_name} 模拟少数股东",
                    batch_tag,
                ),
            )
    return created_company_ids


def insert_mock_legal_risks(conn, company_ids, fake, batch_tag):
    for company_id in company_ids:
        for _ in range(random.randint(1, 4)):
            filing = fake.date_between(start_date="-3y", end_date="today")
            hearing = filing + timedelta(days=random.randint(30, 180))
            amount = round(random.uniform(10, 5000), 2) * 10000
            risk_type = random.choice(RISK_TYPES)
            severity = random.randint(30, 95)
            case_no = f"({filing.year})模拟案字第{random.randint(1000,9999)}号"
            conn.execute(
                """
                INSERT OR IGNORE INTO fact_legal_risk (
                    company_id, case_no, risk_type, role_in_case, counterparty,
                    filing_date, hearing_date, amount_involved, status,
                    severity_score, detail_text, source_type, source_note, batch_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'mock', ?, ?)
                """,
                (
                    company_id,
                    case_no,
                    risk_type,
                    random.choice(["被告", "被执行人", "被处罚对象"]),
                    fake.company(),
                    filing.isoformat(),
                    hearing.isoformat(),
                    amount,
                    random.choice(["处理中", "已结案", "已履行"]),
                    severity,
                    f"模拟风险事件：{risk_type}，金额约 {amount:.2f} 元。",
                    "模拟司法与处罚数据",
                    batch_tag,
                ),
            )


def insert_mock_patents(conn, company_ids, fake, batch_tag):
    current_year = date.today().year
    for company_id in company_ids:
        for index in range(random.randint(3, 10)):
            application_year = random.randint(current_year - 5, current_year)
            patent_type = random.choice(PATENT_TYPES)
            status = random.choice(PATENT_STATUS)
            patent_name = f"{fake.word().upper()}-{patent_type}-技术方案-{index+1}"
            conn.execute(
                """
                INSERT OR IGNORE INTO fact_ip_patent (
                    company_id, patent_no, application_no, patent_name, patent_type,
                    legal_status, application_year, application_date, grant_date,
                    ipc_code, inventor_count, citation_count, patent_score,
                    source_type, source_note, batch_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'mock', ?, ?)
                """,
                (
                    company_id,
                    f"CN{random.randint(10000000, 99999999)}{index}",
                    f"APP{application_year}{random.randint(10000, 99999)}",
                    patent_name,
                    patent_type,
                    status,
                    application_year,
                    f"{application_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    None if status == "审查中" else f"{application_year+1}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    f"A61K{random.randint(1,99)}/{random.randint(1,99)}",
                    random.randint(1, 6),
                    random.randint(0, 50),
                    round(random.uniform(40, 95), 2),
                    "模拟知识产权数据",
                    batch_tag,
                ),
            )


def query_downstream_holdings(conn, root_company_id, max_depth=2):
    sql = """
    WITH RECURSIVE equity_tree AS (
        SELECT
            fir.investee_company_id AS company_id,
            dc.company_name,
            1 AS depth,
            fir.equity_ratio AS direct_ratio,
            fir.equity_ratio AS cumulative_ratio,
            CAST(dc.company_name AS TEXT) AS path
        FROM fact_investment_relation fir
        JOIN dim_party dp ON fir.investor_party_id = dp.party_id
        JOIN dim_company dc ON fir.investee_company_id = dc.company_id
        WHERE dp.company_id = ?

        UNION ALL

        SELECT
            fir.investee_company_id AS company_id,
            dc.company_name,
            et.depth + 1 AS depth,
            fir.equity_ratio AS direct_ratio,
            ROUND(et.cumulative_ratio * fir.equity_ratio / 100.0, 4) AS cumulative_ratio,
            et.path || ' -> ' || dc.company_name AS path
        FROM equity_tree et
        JOIN dim_party dp ON dp.company_id = et.company_id
        JOIN fact_investment_relation fir ON fir.investor_party_id = dp.party_id
        JOIN dim_company dc ON fir.investee_company_id = dc.company_id
        WHERE et.depth < ?
    )
    SELECT company_id, company_name, depth, direct_ratio, cumulative_ratio, path
    FROM equity_tree
    ORDER BY depth, cumulative_ratio DESC, company_name
    """
    return [dict(row) for row in conn.execute(sql, (root_company_id, max_depth)).fetchall()]


def parse_args():
    parser = argparse.ArgumentParser(description="生成企业图谱模拟数据")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    parser.add_argument("--root-company", required=True, help="作为模拟根节点的现有公司名称")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="股权层级深度")
    parser.add_argument("--branch-factor", type=int, default=DEFAULT_BRANCH_FACTOR, help="每层分支数")
    parser.add_argument("--seed", type=int, default=20260324, help="随机种子")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)
    fake = Faker("zh_CN")
    Faker.seed(args.seed)
    batch_tag = f"mock_{args.root_company}_{args.seed}"
    conn = None
    try:
        conn = get_connection(args.db_path)
        company_ids = build_mock_hierarchy(conn, args.root_company, args.depth, args.branch_factor, fake, batch_tag)
        insert_mock_legal_risks(conn, company_ids, fake, batch_tag)
        insert_mock_patents(conn, company_ids, fake, batch_tag)
        conn.commit()
        root_company_id = get_company_id(conn, args.root_company)
        rows = query_downstream_holdings(conn, root_company_id, max_depth=2)
        print(f"模拟数据写入完成，batch_tag={batch_tag}，涉及公司数={len(company_ids)}")
        print("递归CTE查询结果：")
        for row in rows:
            print(
                f"depth={row['depth']} | company={row['company_name']} | "
                f"direct={row['direct_ratio']} | cumulative={row['cumulative_ratio']} | path={row['path']}"
            )
    except Exception as exc:
        if conn:
            conn.rollback()
        raise SystemExit(f"模拟数据写入失败: {exc}") from exc
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
