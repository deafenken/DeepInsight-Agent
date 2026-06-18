import unittest

from webapp.main import (
    build_batch_workflow_markdown,
    fetch_alert_center,
    fetch_company_profile_dashboard,
    fetch_company_timeline_dashboard,
    fetch_company_trend_dashboard,
    fetch_data_room_catalog,
    fetch_data_room_preview,
    fetch_database_catalog,
    fetch_database_table_preview,
    fetch_import_dashboard,
    fetch_industry_ranking_dashboard,
    fetch_macro_linkage_dashboard,
    infer_industry_name,
)


class WebappDashboardTests(unittest.TestCase):
    def test_fetch_import_dashboard_returns_core_cards(self):
        payload = fetch_import_dashboard()

        self.assertIn("cards", payload)
        self.assertIn("health_cards", payload)
        self.assertIn("source_breakdown", payload)
        self.assertIn("last_import_at", payload)
        self.assertIn("risk_documents", payload)
        self.assertTrue(any(card["label"] == "导入文档总数" for card in payload["cards"]))

    def test_fetch_company_trend_dashboard_returns_chart_for_known_company(self):
        payload = fetch_company_trend_dashboard("ST生物")

        self.assertEqual(payload["company_name"], "ST生物")
        self.assertTrue(payload["cards"])
        self.assertIn("anomalies", payload)
        self.assertIn("summary", payload)
        self.assertTrue(all("status" in card for card in payload["cards"]))
        self.assertTrue(payload["amount_chart"])
        self.assertTrue(payload["amount_chart"]["rows"])

    def test_fetch_industry_ranking_dashboard_returns_boards_for_known_company(self):
        payload = fetch_industry_ranking_dashboard("ST生物", 2023, ranking_scope="industry")

        self.assertEqual(payload["company_name"], "ST生物")
        self.assertEqual(payload["report_year"], 2023)
        self.assertIn("scope_label", payload)
        self.assertEqual(payload["ranking_scope"], "industry")
        self.assertEqual(payload["scope_label"], "同一级行业排名")
        self.assertTrue(payload["boards"])
        self.assertTrue(any(board["indicator_name"] == "营业收入" for board in payload["boards"]))
        self.assertTrue(all("sample_size" in board for board in payload["boards"]))

    def test_fetch_company_profile_dashboard_returns_company_360_payload(self):
        payload = fetch_company_profile_dashboard("ST生物", 2023)

        self.assertEqual(payload["company_name"], "ST生物")
        self.assertIn("summary", payload)
        self.assertTrue(payload["cards"])
        self.assertTrue(payload["metric_cards"])
        self.assertIn("alerts", payload)

    def test_fetch_alert_center_returns_structured_items(self):
        payload = fetch_alert_center("ST生物", 2023)

        self.assertIn("cards", payload)
        self.assertIn("items", payload)
        self.assertTrue(all("signal" in item for item in payload["items"]))

    def test_fetch_company_timeline_dashboard_returns_events(self):
        payload = fetch_company_timeline_dashboard("ST生物")

        self.assertEqual(payload["company_name"], "ST生物")
        self.assertTrue(payload["events"])
        self.assertTrue(any(event["category"] in {"财务", "风险", "创新"} for event in payload["events"]))

    def test_fetch_macro_linkage_dashboard_returns_summary(self):
        payload = fetch_macro_linkage_dashboard("ST生物")

        self.assertEqual(payload["company_name"], "ST生物")
        self.assertIn("summary", payload)
        self.assertTrue(payload["cards"])

    def test_fetch_database_catalog_returns_tables(self):
        payload = fetch_database_catalog()

        self.assertIn("tables", payload)
        self.assertTrue(payload["tables"])
        self.assertIn("table_names", payload)
        self.assertIn("dim_company", payload["table_names"])

    def test_fetch_database_table_preview_returns_columns_and_rows(self):
        payload = fetch_database_table_preview("dim_company", limit=5)

        self.assertEqual(payload["table_name"], "dim_company")
        self.assertEqual(payload["limit"], 5)
        self.assertIn("columns", payload)
        self.assertTrue(payload["columns"])
        self.assertIn("rows", payload)
        self.assertLessEqual(len(payload["rows"]), 5)
        self.assertIn("row_count", payload)
        self.assertIn("create_sql", payload)

    def test_fetch_data_room_preview_omits_raw_schema_sql(self):
        catalog = fetch_data_room_catalog()
        self.assertIn("tables", catalog)
        payload = fetch_data_room_preview("dim_company", limit=5)

        self.assertEqual(payload["table_name"], "dim_company")
        self.assertIn("columns", payload)
        self.assertIn("rows", payload)
        self.assertNotIn("create_sql", payload)
        self.assertNotIn("database_path", payload)

    def test_build_batch_workflow_markdown_joins_reports(self):
        markdown = build_batch_workflow_markdown(
            [
                {"company_name": "甲公司", "report_markdown": "## 结论\n甲"},
                {"company_name": "乙公司", "report_markdown": "## 结论\n乙"},
            ]
        )

        self.assertIn("# 甲公司", markdown)
        self.assertIn("# 乙公司", markdown)
        self.assertIn("---", markdown)

    def test_infer_industry_name_supports_medical_subsectors(self):
        self.assertEqual(infer_industry_name("联影医疗"), "医疗器械")
        self.assertEqual(infer_industry_name("智飞生物"), "生物制品")
        self.assertEqual(infer_industry_name("海思科"), "医药生物")


if __name__ == "__main__":
    unittest.main()
