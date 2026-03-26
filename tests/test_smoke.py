import json
import unittest
from pathlib import Path

from deepinsight.apps.workflow_report import run_workflow
from deepinsight.core.agent_tools import run_advanced_analysis
from deepinsight.core.retriever import answer_query, create_optional_client, get_collection, get_connection


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_optional_client()

    def test_database_and_vector_store_available(self):
        conn = get_connection()
        try:
            companies = conn.execute("select count(*) from dim_company").fetchone()[0]
            documents = conn.execute("select count(*) from dim_document").fetchone()[0]
        finally:
            conn.close()
        collection = get_collection()
        self.assertGreater(companies, 0)
        self.assertGreater(documents, 0)
        self.assertGreater(collection.count(), 0)

    def test_chat_answer_query_smoke(self):
        result = answer_query(
            "请总结ST生物2023年的经营质量、风险点和关注指标",
            filters={},
            top_k=5,
            client=self.client,
        )
        self.assertTrue(result.get("answer_markdown"))
        self.assertIn(result.get("route"), {"sql", "vector", "hybrid"})
        self.assertGreater(len(result.get("sources") or []), 0)

    def test_workflow_smoke(self):
        result = run_workflow(
            "请为 ST生物 生成经营质量与风险诊断报告",
            filters={},
            top_k=5,
            client=self.client,
        )
        self.assertTrue(result.get("report_markdown"))
        self.assertIn(result.get("data_mode"), {"live", "partial", "degraded", "unavailable"})
        self.assertGreater(len(result.get("sql_rows") or []), 0)
        self.assertGreater(len(result.get("rag_chunks") or []), 0)

    def test_advanced_analysis_smoke(self):
        result = run_advanced_analysis(
            "请分析该公司的股权结构、司法风险与创新能力",
            company_name="ST生物",
            client=self.client,
        )
        self.assertGreater(len(result.get("viz_blocks") or []), 0)
        self.assertIn("equity", result.get("tool_results") or {})

    def test_demo_cache_json_valid(self):
        cache_dir = Path("/Volumes/ORICO/code1/demo_cache")
        targets = [
            "enterprise_diagnosis.json",
            "company_compare.json",
            "macro_linkage.json",
            "starter_latest_enterprise_diagnosis.json",
            "starter_recent_company_compare.json",
            "starter_regulatory_risk.json",
            "starter_traceable_investment_summary.json",
            "workflow_report.json",
            "advanced_st_bio.json",
            "whitebox_demo.json",
        ]
        for name in targets:
            path = cache_dir / name
            self.assertTrue(path.exists(), msg=f"missing cache file: {name}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("type", payload, msg=f"invalid cache payload: {name}")


if __name__ == "__main__":
    unittest.main()
