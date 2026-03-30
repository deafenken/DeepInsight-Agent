import unittest
from unittest.mock import patch
import tempfile
import sqlite3
from pathlib import Path

from deepinsight.core import retriever


class RetrieverUnitTests(unittest.TestCase):
    def test_build_chroma_filter_supports_multiple_company_names(self):
        where = retriever.build_chroma_filter(
            {
                "company_names": ["甲公司", "乙公司"],
                "report_year": 2023,
                "doc_type": "annual_report",
            }
        )

        self.assertEqual(
            where,
            {
                "$and": [
                    {"doc_type": "annual_report"},
                    {"$or": [{"company_name": "甲公司"}, {"company_name": "乙公司"}]},
                    {"report_year": 2023},
                ]
            },
        )

    def test_build_chroma_filter_ignores_inferred_industry_name(self):
        where = retriever.build_chroma_filter(
            {
                "company_name": "ST生物",
                "industry_name": "生物制品",
                "industry_name_inferred": True,
                "report_year": 2023,
            }
        )

        self.assertEqual(
            where,
            {
                "$and": [
                    {"company_name": "ST生物"},
                    {"report_year": 2023},
                ]
            },
        )

    def test_select_top_chunks_balances_multiple_companies(self):
        scored_chunks = [
            (0.99, {"text": "甲公司 chunk 1", "metadata": {"company_name": "甲公司", "document_id": 1, "chunk_index": 0, "page": 10}}),
            (0.98, {"text": "甲公司 chunk 2", "metadata": {"company_name": "甲公司", "document_id": 1, "chunk_index": 1, "page": 11}}),
            (0.80, {"text": "乙公司 chunk 1", "metadata": {"company_name": "乙公司", "document_id": 2, "chunk_index": 0, "page": 8}}),
            (0.70, {"text": "乙公司 chunk 2", "metadata": {"company_name": "乙公司", "document_id": 2, "chunk_index": 1, "page": 9}}),
        ]

        selected = retriever.select_top_chunks(scored_chunks, top_k=3, company_names=["甲公司", "乙公司"])

        self.assertEqual(len(selected), 3)
        self.assertEqual(selected[0]["metadata"]["company_name"], "甲公司")
        self.assertEqual(selected[1]["metadata"]["company_name"], "乙公司")
        self.assertEqual(selected[2]["text"], "甲公司 chunk 2")

    def test_retrieve_chunks_queries_each_company_in_comparison_mode(self):
        class FakeCollection:
            def __init__(self):
                self.calls = []

            def query(self, **kwargs):
                where = kwargs.get("where") or {}
                self.calls.append(where)
                company_name = None
                for item in where.get("$and", []):
                    if "company_name" in item:
                        company_name = item["company_name"]
                        break
                return {
                    "documents": [[f"{company_name} 经营情况与风险提示，营业收入与现金流表现。"]],
                    "metadatas": [[{"company_name": company_name, "document_id": len(self.calls), "chunk_index": 0, "page": 12 if company_name == '甲公司' else None, "source": f"{company_name}.md"}]],
                    "distances": [[0.1]],
                }

        fake_collection = FakeCollection()
        with patch.object(retriever, "get_collection", return_value=fake_collection):
            with patch.object(retriever.LocalEmbeddingClient, "embed", return_value=[[0.1, 0.2]]):
                chunks = retriever.retrieve_chunks(
                    "请比较甲公司和乙公司的经营风险",
                    filters={"company_names": ["甲公司", "乙公司"], "report_year": 2023},
                    top_k=4,
                )

        self.assertEqual(len(fake_collection.calls), 2)
        self.assertEqual(
            fake_collection.calls,
            [
                {"$and": [{"company_name": "甲公司"}, {"report_year": 2023}]},
                {"$and": [{"company_name": "乙公司"}, {"report_year": 2023}]},
            ],
        )
        self.assertEqual([chunk["metadata"]["company_name"] for chunk in chunks[:2]], ["甲公司", "乙公司"])
        self.assertIsNone(chunks[1]["metadata"]["page"])

    def test_resolve_local_query_filters_infers_industry_for_single_company(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.row_factory = sqlite3.Row
                conn.executescript(
                    """
                    CREATE TABLE dim_industry (
                        industry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        industry_name TEXT UNIQUE,
                        industry_level INTEGER
                    );
                    CREATE TABLE dim_company (
                        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_name TEXT NOT NULL,
                        primary_industry_id INTEGER
                    );
                    CREATE TABLE dim_document (
                        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL,
                        report_year INTEGER,
                        is_latest INTEGER NOT NULL DEFAULT 1
                    );
                    """
                )
                conn.execute("INSERT INTO dim_industry (industry_name, industry_level) VALUES (?, ?)", ("生物制品", 2))
                industry_id = conn.execute("SELECT industry_id FROM dim_industry WHERE industry_name = ?", ("生物制品",)).fetchone()[0]
                conn.execute("INSERT INTO dim_company (company_name, primary_industry_id) VALUES (?, ?)", ("ST生物", industry_id))
                company_id = conn.execute("SELECT company_id FROM dim_company WHERE company_name = ?", ("ST生物",)).fetchone()[0]
                conn.execute("INSERT INTO dim_document (company_id, report_year, is_latest) VALUES (?, ?, 1)", (company_id, 2023))
                conn.commit()
            finally:
                conn.close()

            resolved = retriever.resolve_local_query_filters("请分析ST生物的经营质量", {}, db_path=db_path)

        self.assertEqual(resolved["company_name"], "ST生物")
        self.assertEqual(resolved["industry_name"], "生物制品")
        self.assertEqual(resolved["report_year"], 2023)


if __name__ == "__main__":
    unittest.main()
