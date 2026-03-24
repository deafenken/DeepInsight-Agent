import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("/Volumes/ORICO/code1/data/enterprise_analysis.db")


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_extended_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dim_person (
            person_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            person_title TEXT,
            identity_hash TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(person_name, person_title)
        );

        CREATE TABLE IF NOT EXISTS dim_party (
            party_id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_type TEXT NOT NULL CHECK (party_type IN ('company', 'person')),
            company_id INTEGER UNIQUE,
            person_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (
                (party_type = 'company' AND company_id IS NOT NULL AND person_id IS NULL) OR
                (party_type = 'person' AND person_id IS NOT NULL AND company_id IS NULL)
            ),
            FOREIGN KEY (company_id) REFERENCES dim_company(company_id) ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES dim_person(person_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fact_investment_relation (
            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_party_id INTEGER NOT NULL,
            investee_company_id INTEGER NOT NULL,
            equity_ratio REAL NOT NULL CHECK (equity_ratio >= 0 AND equity_ratio <= 100),
            subscribed_amount REAL,
            control_type TEXT NOT NULL DEFAULT 'direct',
            effective_date TEXT,
            source_type TEXT NOT NULL DEFAULT 'mock',
            source_note TEXT,
            batch_tag TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(investor_party_id, investee_company_id, effective_date, source_type, batch_tag),
            FOREIGN KEY (investor_party_id) REFERENCES dim_party(party_id) ON DELETE CASCADE,
            FOREIGN KEY (investee_company_id) REFERENCES dim_company(company_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fact_legal_risk (
            risk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            case_no TEXT,
            risk_type TEXT NOT NULL,
            role_in_case TEXT,
            counterparty TEXT,
            filing_date TEXT NOT NULL,
            hearing_date TEXT,
            amount_involved REAL,
            status TEXT,
            severity_score INTEGER NOT NULL DEFAULT 50 CHECK (severity_score BETWEEN 0 AND 100),
            detail_text TEXT,
            source_type TEXT NOT NULL DEFAULT 'mock',
            source_note TEXT,
            batch_tag TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, case_no, filing_date),
            FOREIGN KEY (company_id) REFERENCES dim_company(company_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fact_ip_patent (
            patent_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            patent_no TEXT,
            application_no TEXT,
            patent_name TEXT NOT NULL,
            patent_type TEXT NOT NULL,
            legal_status TEXT NOT NULL,
            application_year INTEGER NOT NULL,
            application_date TEXT,
            grant_date TEXT,
            ipc_code TEXT,
            inventor_count INTEGER,
            citation_count INTEGER,
            patent_score REAL,
            source_type TEXT NOT NULL DEFAULT 'mock',
            source_note TEXT,
            batch_tag TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, patent_name, application_year, patent_type, batch_tag),
            FOREIGN KEY (company_id) REFERENCES dim_company(company_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_party_company ON dim_party(company_id);
        CREATE INDEX IF NOT EXISTS idx_party_person ON dim_party(person_id);
        CREATE INDEX IF NOT EXISTS idx_investment_investor ON fact_investment_relation(investor_party_id);
        CREATE INDEX IF NOT EXISTS idx_investment_company ON fact_investment_relation(investee_company_id);
        CREATE INDEX IF NOT EXISTS idx_investment_company_date ON fact_investment_relation(investee_company_id, effective_date);
        CREATE INDEX IF NOT EXISTS idx_legal_company ON fact_legal_risk(company_id);
        CREATE INDEX IF NOT EXISTS idx_legal_company_date ON fact_legal_risk(company_id, filing_date);
        CREATE INDEX IF NOT EXISTS idx_legal_company_severity ON fact_legal_risk(company_id, severity_score);
        CREATE INDEX IF NOT EXISTS idx_patent_company ON fact_ip_patent(company_id);
        CREATE INDEX IF NOT EXISTS idx_patent_company_year ON fact_ip_patent(company_id, application_year);
        CREATE INDEX IF NOT EXISTS idx_patent_company_type ON fact_ip_patent(company_id, patent_type);
        """
    )


def seed_company_parties(conn):
    conn.execute(
        """
        INSERT INTO dim_party (party_type, company_id)
        SELECT 'company', company_id
        FROM dim_company
        WHERE company_id NOT IN (
            SELECT company_id FROM dim_party WHERE company_id IS NOT NULL
        )
        """
    )


def parse_args():
    parser = argparse.ArgumentParser(description="扩展企业图谱与风险分析数据库")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite 数据库路径")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = None
    try:
        conn = get_connection(args.db_path)
        create_extended_tables(conn)
        seed_company_parties(conn)
        conn.commit()
        print(f"数据库扩展完成: {args.db_path}")
    except Exception as exc:
        if conn:
            conn.rollback()
        raise SystemExit(f"扩展失败: {exc}") from exc
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
