import tempfile
import unittest
from pathlib import Path

from deepinsight.dataops import data_pipeline
from deepinsight.dataops import db_init


class DataPipelinePathTests(unittest.TestCase):
    def test_collect_files_recursively_in_nested_company_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            company_dir = root / "示例公司"
            company_dir.mkdir()
            target = company_dir / "示例公司-2023年度报告.md"
            target.write_text("# 示例", encoding="utf-8")
            ignored = root / "README.txt"
            ignored.write_text("ignore", encoding="utf-8")

            files = data_pipeline.collect_files(root)

            self.assertEqual(files, [target])

    def test_resolve_input_dir_prefers_final_md_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            final_dir = root / "Final_md"
            reports_dir = root / "reports_md"
            final_dir.mkdir()
            reports_dir.mkdir()
            original_dirs = data_pipeline.DEFAULT_INPUT_DIRS

            try:
                data_pipeline.DEFAULT_INPUT_DIRS = [final_dir, reports_dir]
                resolved = data_pipeline.resolve_input_dir()
            finally:
                data_pipeline.DEFAULT_INPUT_DIRS = original_dirs

            self.assertEqual(resolved, final_dir)

    def test_parse_pages_accepts_bold_single_page_markers(self):
        pages, total = data_pipeline.parse_pages(["封面", "", "**1**", "", "正文内容"])

        self.assertIsNone(total)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[-1].page_no, 1)
        self.assertIn("正文内容", pages[-1].text)

    def test_image_placeholder_only_markdown_does_not_create_rag_chunks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "共同药业-2021年度报告.md"
            path.write_text(
                "\n".join(
                    [
                        "**==> picture [75 x 75] intentionally omitted <==**",
                        "",
                        "**==> picture [434 x 79] intentionally omitted <==**",
                    ]
                ),
                encoding="utf-8",
            )

            parsed = data_pipeline.load_markdown_document(path)

            class DummySplitter:
                def split_text(self, text):
                    return [text]

            chunks = data_pipeline.split_document(parsed, DummySplitter())

        self.assertFalse(parsed.metadata["has_meaningful_text"])
        self.assertEqual(parsed.metadata["picture_placeholder_lines"], 2)
        self.assertEqual(parsed.pages, [])
        self.assertEqual(chunks, [])

    def test_audit_text_quality_flags_placeholder_only_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            risky = root / "共同药业-2021年度报告.md"
            healthy = root / "正常公司-2023年度报告.md"
            risky.write_text(
                "\n".join(
                    [
                        "**==> picture [75 x 75] intentionally omitted <==**",
                        "**==> picture [434 x 79] intentionally omitted <==**",
                    ]
                ),
                encoding="utf-8",
            )
            healthy.write_text(
                "\n".join(
                    [
                        "# 正常公司 2023 年度报告",
                        "主要会计数据和财务指标",
                        "营业收入 100",
                    ]
                ),
                encoding="utf-8",
            )

            rows = data_pipeline.audit_text_quality([risky, healthy], min_text_ratio=0.05)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_path"], str(risky))
        self.assertFalse(rows[0]["has_meaningful_text"])
        self.assertEqual(rows[0]["picture_placeholder_lines"], 2)

    def test_extract_financial_facts_supports_stacked_report_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = db_init.get_connection(db_path)
            try:
                db_init.create_tables(conn)
                db_init.seed_indicators(conn)
                conn.commit()
                id_to_code = {v: k for k, v in data_pipeline.find_indicator_id_map(conn).items()}
                parsed = data_pipeline.ParsedDocument(
                    metadata={"report_year": 2023},
                    pages=[],
                    raw_text="",
                    lines=[
                        "五、主要会计数据和财务指标",
                        "2023 年",
                        "2022 年",
                        "本年比上年增减",
                        "2021 年",
                        "营业收入（元）",
                        "1,337,586,673.34",
                        "1,415,288,702.33",
                        "-5.49%",
                        "1,137,447,250.97",
                        "归属于上市公司股东的净利润（元）",
                        "313,300,575.05",
                        "402,088,234.73",
                        "-22.08%",
                        "310,101,397.04",
                        "归属于上市公司股东的扣除非经常性损益的净利润（元）",
                        "291,017,312.35",
                        "392,985,160.21",
                        "-25.95%",
                        "302,741,639.68",
                        "经营活动产生的现金流量净额（元）",
                        "350,716,361.92",
                        "381,356,133.98",
                        "-8.03%",
                        "195,593,634.42",
                        "2023 年末",
                        "2022 年末",
                        "本年末比上年末增减",
                        "2021 年末",
                        "资产总额（元）",
                        "3,523,270,170.04",
                        "3,388,446,632.86",
                        "3.98%",
                        "1,901,180,254.10",
                        "归属于上市公司股东的净资产（元）",
                        "3,182,287,615.40",
                        "3,021,380,860.08",
                        "5.33%",
                        "1,391,743,044.90",
                        "主要财务指标",
                        "加权平均净资产收益率",
                        "10.10%",
                        "21.16%",
                        "-11.06%",
                        "24.58%",
                        "六、分季度主要财务指标",
                    ],
                )

                facts = data_pipeline.extract_financial_facts(parsed, conn)
            finally:
                conn.close()
        by_code = {}
        for fact in facts:
            by_code.setdefault(id_to_code[fact["indicator_id"]], []).append(fact)

        self.assertIn("revenue", by_code)
        self.assertIn("net_profit_parent", by_code)
        self.assertIn("net_profit_deducted", by_code)
        self.assertIn("operating_cash_flow", by_code)
        self.assertIn("total_assets", by_code)
        self.assertIn("net_assets_parent", by_code)
        self.assertIn("roe", by_code)
        self.assertTrue(any(f["value_role"] == "current" and f["value_num"] == 1337586673.34 for f in by_code["revenue"]))
        self.assertTrue(any(f["value_role"] == "historical" and f["value_num"] == 1415288702.33 for f in by_code["revenue"]))

    def test_backfill_company_industries_creates_medical_hierarchy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = db_init.get_connection(db_path)
            try:
                db_init.create_tables(conn)
                conn.execute(
                    "INSERT INTO dim_company (company_name) VALUES (?)",
                    ("联影医疗",),
                )
                updated = data_pipeline.backfill_company_industries(conn)
                conn.commit()

                self.assertEqual(updated, 1)
                company_row = conn.execute(
                    """
                    SELECT c.company_name, i.industry_name, i.industry_level, p.industry_name AS parent_name
                    FROM dim_company c
                    LEFT JOIN dim_industry i ON i.industry_id = c.primary_industry_id
                    LEFT JOIN dim_industry p ON p.industry_id = i.parent_industry_id
                    WHERE c.company_name = ?
                    """,
                    ("联影医疗",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(company_row["industry_name"], "医疗器械")
        self.assertEqual(company_row["industry_level"], 2)
        self.assertEqual(company_row["parent_name"], "医药生物")


if __name__ == "__main__":
    unittest.main()
