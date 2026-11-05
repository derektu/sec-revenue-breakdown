"""viewer 讀取 `data/revenue/` 正式輸出：Q／FY 序列、留空／失敗／差異標記、證據核對與路徑限制，以及頁面的顯示。"""

import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))

from sec_revenue.published import PublishedRevenue
from sec_revenue.viewer import RevenueViewer

TABLE = "0000320193-25-000079-dceb82ec4e10-t27"


def revenue(series: str, value: int, png: bytes, html: bytes, quarter: int | None = None) -> dict:
    """iPhone 一個分類加上調節項 Eliminations（−1 百萬）；兩個運算元引用同一張表。"""
    evidence = {
        "table": TABLE,
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "html_sha256": hashlib.sha256(html).hexdigest(),
    }
    operand = {"accession": "0000320193-25-000079", "form": "10-K", "role": "annual"}
    output = {
        "ticker": "AAPL",
        "series": series,
        "view": "product",
        "fiscal_year": 2025,
        "period_end": "2025-09-27",
        "categories": {"iPhone": {"expression": [{"operand": "op1", "weight": 1}], "value": value}},
        "reconciling": {"Eliminations": {"expression": [{"operand": "op2", "weight": 1}], "value": -1e6}},
        "total": {
            "expression": [{"operand": "op1", "weight": 1}, {"operand": "op2", "weight": 1}],
            "value": value - 1e6,
        },
        "operands": {
            "op1": {**operand, "value": value, "evidence": dict(evidence)},
            "op2": {**operand, "value": -1e6, "evidence": dict(evidence)},
        },
    }
    if quarter:
        output["fiscal_quarter"] = quarter
    return output


def write_period(directory: Path, output: dict, png: bytes = b"png", html: bytes = b"<p>t</p>"):
    (directory / "evidence").mkdir(parents=True)
    (directory / "revenue.json").write_text(json.dumps(output))
    (directory / "evidence" / f"{TABLE}.png").write_bytes(png)
    (directory / "evidence" / f"{TABLE}.html").write_bytes(html)


def write_fixture(root: Path):
    """AAPL 的 Q 序列四期涵蓋各種狀態：差異標記、重算不同（表格檔被改過）、不推算但保留已上線輸出、失敗且沒有輸出。"""
    base = root / "A" / "AAPL"
    write_period(base / "FY" / "2025-09-27", revenue("FY", 416e6, b"png", b"<p>t</p>"))
    write_period(base / "Q" / "2025-03-29", revenue("Q", 95e6, b"png", b"<p>t</p>", 2))
    write_period(base / "Q" / "2025-06-28", revenue("Q", 94e6, b"png", b"<p>t</p>", 3), html=b"tampered")
    write_period(base / "Q" / "2025-09-27", revenue("Q", 37e6, b"png", b"<p>t</p>", 4))
    quarter = {"start": "2024-12-29", "end": "2025-03-29"}
    status = {
        "ticker": "AAPL",
        "view": "product",
        "periods": {
            "Q": {
                "2025-03-29": {
                    "status": "published", "fiscal_year": 2025, "fiscal_quarter": 2,
                    "accession": "0000320193-25-000057",
                    "differences": [
                        {
                            "category": "iPhone", "operand": "op1", "role": "quarter", "period": quarter,
                            "result": "different", "published_value": 95e6, "listed_value": 96e6,
                            "source": {
                                "accession": "0000320193-26-000002", "form": "10-Q",
                                "filing_date": "2026-05-01", "fact_id": "f-1",
                            },
                        },
                        {
                            "category": "Eliminations", "operand": "op2", "role": "quarter", "period": quarter,
                            "result": "unparseable", "published_value": -1e6, "listed_value": None,
                            "source": {
                                "accession": "0000320193-26-000002", "form": "10-Q",
                                "filing_date": "2026-05-01", "fact_id": "f-2",
                            },
                        },
                    ],
                },
                "../../x": {"status": "published"},
                "2025-06-28": {
                    "status": "published", "fiscal_year": 2025, "fiscal_quarter": 3,
                    "accession": "0000320193-25-000073",
                    "differs_from_published": {
                        "reason": "規則或原文變更",
                        "categories": [{"category": "iPhone", "published": 94e6, "new": 95e6}],
                        "fields": ["categories"], "value_changed": True,
                    },
                },
                "2025-09-27": {
                    "status": "not_derived", "fiscal_year": 2025, "fiscal_quarter": 4,
                    "check": "Q4 推算條件", "reason": "年度與 Q1–Q3 的分類集合不同",
                    "fy_categories": ["iPhone"],
                    "quarter_categories": [{"start": "2024-09-29", "end": "2025-06-28", "categories": ["iPhone", "Mac"]}],
                    "published_output_kept": True,
                    "published_output": {"accession": "0000320193-25-000079", "categories": {"iPhone": 37e6}, "total": 37e6},
                },
                "2025-12-27": {
                    "status": "failed", "fiscal_year": 2026, "fiscal_quarter": 1,
                    "check": "加總", "reason": "分類合計與總營收不符", "published_output_kept": False,
                },
            },
            "FY": {"2025-09-27": {"status": "published", "fiscal_year": 2025, "accession": "0000320193-25-000079"}},
        },
        "comparison_errors": [{"accession": "0000320193-26-000001", "check": "原文", "reason": "讀不到主文件"}],
    }
    (base / "status.json").write_text(json.dumps(status, ensure_ascii=False))


class PublishedViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.viewer = RevenueViewer(self.root / "legacy", self.root)

    def tearDown(self):
        self.temp.cleanup()

    def get(self, url: str) -> tuple[int, object]:
        status, _, body = self.viewer.request(url)
        return status, json.loads(body) if body.startswith((b"{", b"[")) else body

    def write_series_layout(self):
        write_fixture(self.root)

    def test_series_lists_status_records_and_outputs(self):
        self.write_series_layout()
        status, company = self.get("/api/company?ticker=AAPL")
        self.assertEqual(status, 200)
        self.assertEqual(company["comparison_errors"][0]["accession"], "0000320193-26-000001")
        q = {p["period_end"]: p for p in company["series"]["Q"]}
        # status.json 中不是日期的期別鍵不列出。
        self.assertEqual(list(q), ["2025-03-29", "2025-06-28", "2025-09-27", "2025-12-27"])
        self.assertEqual(q["2025-03-29"]["record"]["differences"][0]["source"]["form"], "10-Q")
        self.assertEqual(q["2025-03-29"]["revenue"]["reconciling"]["Eliminations"]["value"], -1e6)
        self.assertEqual(q["2025-06-28"]["record"]["differs_from_published"]["categories"][0]["new"], 95e6)
        # 不推算但保留先前上線的輸出：紀錄與 revenue.json 都有。
        kept = q["2025-09-27"]
        self.assertEqual((kept["status"], kept["record"]["published_output_kept"]), ("not_derived", True))
        self.assertEqual(kept["revenue"]["categories"]["iPhone"]["value"], 37e6)
        # 失敗且沒有輸出：只有紀錄。
        self.assertEqual((q["2025-12-27"]["status"], q["2025-12-27"]["revenue"]), ("failed", None))
        [fy] = company["series"]["FY"]
        self.assertEqual(fy["revenue"]["categories"]["iPhone"]["value"], 416e6)
        self.assertEqual(fy["revenue"]["evidence_files"][TABLE]["problems"], [])
        problems = q["2025-06-28"]["revenue"]["evidence_files"][TABLE]["problems"]
        self.assertEqual(len(problems), 1)
        self.assertIn("hash", problems[0])
        self.assertEqual(
            self.viewer.request(f"/revenue-evidence/AAPL/Q/2025-03-29/{TABLE}.png")[:2], (200, "image/png")
        )

    def test_every_operand_hash_is_checked(self):
        self.write_series_layout()
        directory = self.root / "A" / "AAPL" / "FY" / "2025-09-27"
        output = json.loads((directory / "revenue.json").read_text())
        output["operands"]["op2"]["evidence"]["png_sha256"] = "0" * 64
        problems = PublishedRevenue.evidence_files(output, directory)[TABLE]["problems"]
        self.assertEqual(len(problems), 1)
        self.assertIn("op2", problems[0])
        self.assertNotIn("op1", problems[0])

    def test_companies_mark_listed_and_output(self):
        self.write_series_layout()
        status, companies = self.get("/api/companies")
        self.assertEqual(status, 200)
        by_ticker = {c["ticker"]: c for c in companies}
        self.assertTrue(by_ticker["AAPL"]["listed"])
        self.assertTrue(by_ticker["AAPL"]["has_output"])
        self.assertFalse(by_ticker["MSFT"]["has_output"])

    def test_evidence_route_serves_only_named_table_files(self):
        self.write_series_layout()
        ok = self.viewer.request(f"/revenue-evidence/AAPL/FY/2025-09-27/{TABLE}.html")
        self.assertEqual(ok[:2], (200, "text/html; charset=utf-8"))
        for url in [
            "/revenue-evidence/AAPL/FY/2025-09-27/../../status.json",
            "/revenue-evidence/AAPL/FY/2025-09-27/revenue.json",
            f"/revenue-evidence/AAPL/H1/2025-09-27/{TABLE}.png",
            f"/revenue-evidence/AAPL/Q/2025-12-27/{TABLE}.png",
            f"/revenue-evidence/ZZZZ/FY/2025-09-27/{TABLE}.png",
        ]:
            self.assertEqual(self.viewer.request(url)[0], 404, url)

    def test_company_query_validation(self):
        self.write_series_layout()
        for url in [
            "/api/company?ticker=../AAPL",
            "/api/company?ticker=AAPL&path=x",
            "/api/company?ticker=AAPL&ticker=MSFT",
            "/api/company",
            "/api/company?ticker=ZZZZ",
        ]:
            self.assertEqual(self.viewer.request(url)[0], 400, url)
        self.assertEqual(self.viewer.request("/api/company?ticker=MSFT")[0], 404)
        self.assertEqual(self.viewer.request("/")[0], 200)
        self.assertEqual(self.viewer.request("/legacy")[0], 200)


class ViewerHeaderTests(unittest.TestCase):
    """經 HTTP server 回應的標頭：CSP 依路由路徑判斷，absolute-form 請求（GET http://host/...）同樣套用。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        write_fixture(root)
        legacy = root / "legacy" / "outputs" / "AAPL" / "2025-06-28" / "evidence"
        legacy.mkdir(parents=True)
        (legacy / f"{TABLE}.html").write_bytes(b"<p>t</p>")
        # port 0：由系統指派一個暫用 port，測試結束即關閉。
        self.server = RevenueViewer(root / "legacy", root).server("127.0.0.1", 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def test_csp_applies_to_absolute_form_requests(self):
        host, port = self.server.server_address[:2]
        for path, policy in [
            (f"/revenue-evidence/AAPL/FY/2025-09-27/{TABLE}.html", "sandbox"),
            (f"/evidence/AAPL/2025-06-28/{TABLE}.html", "sandbox"),
            ("/", "default-src 'none'"),
            ("/legacy", "default-src 'none'"),
        ]:
            for target in (path, f"http://{host}:{port}{path}"):
                connection = http.client.HTTPConnection(host, port)
                connection.request("GET", target)
                response = connection.getresponse()
                response.read()
                connection.close()
                self.assertEqual(response.status, 200, target)
                self.assertIn(policy, response.getheader("Content-Security-Policy") or "", target)


class PublishedViewerPageTests(unittest.TestCase):
    """以 Playwright 開正式輸出頁面，確認各種狀態的格子與明細；沒有 Playwright 或瀏覽器時略過。"""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("沒有安裝 playwright")
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        write_fixture(root)
        # port 0：由系統指派一個暫用 port，測試結束即關閉。
        cls.server = RevenueViewer(root / "legacy", root).server("127.0.0.1", 0)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception as error:
            cls.tearDownClass()
            raise unittest.SkipTest(f"無法啟動 Chromium：{error}")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "browser", None):
            cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def setUp(self):
        self.errors = []
        self.page = self.browser.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url + "#ticker=AAPL&series=Q")
        self.page.wait_for_selector("#grid tbody")

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def cell(self, row: int, column: int):
        return self.page.locator("#grid tbody tr").nth(row).locator("td").nth(column)

    def test_cells_mark_each_status(self):
        headers = self.page.locator("#grid thead th").all_inner_texts()
        self.assertIn("重算不同", headers[2])
        self.assertIn("留空（保留已上線值）", headers[3])
        self.assertIn("失敗", headers[4])
        self.assertIn("1 份申報讀不到原文", self.page.locator("#notes").inner_text())
        diff, kept, failed = self.cell(0, 0), self.cell(0, 2), self.cell(0, 3)
        self.assertIn("diff", diff.get_attribute("class"))
        self.assertIn("△", diff.inner_text())
        self.assertNotIn("diff", self.cell(2, 0).get_attribute("class") or "")  # 總營收列沒有差異標記
        self.assertEqual((kept.inner_text(), kept.get_attribute("class")), ("37", "blank kept"))
        self.assertEqual((failed.inner_text(), failed.get_attribute("class")), ("失敗", "failed"))

    def test_reconciling_row(self):
        row = self.page.locator("#grid tbody tr").nth(1)
        self.assertEqual(row.get_attribute("class"), "reconciling first")
        self.assertEqual(row.locator("th").inner_text(), "調節Eliminations")
        self.assertIn("diff", self.cell(1, 0).get_attribute("class"))
        self.assertNotIn("diff", self.cell(1, 1).get_attribute("class") or "")
        self.cell(1, 0).click()
        detail = self.page.locator("#detail").inner_text()
        for text in ["調節項 Eliminations", "差異標記 1 筆", "無法解析", "f-2", "-1 百萬 ="]:
            self.assertIn(text, detail)
        self.assertNotIn("f-1", detail)

    def test_detail_shows_records(self):
        detail = self.page.locator("#detail")
        self.cell(0, 0).click()
        for text in ["差異標記 1 筆", "數值不同", "申報列示值", "96 百萬", "10-Q 0000320193-26-000002", "f-1"]:
            self.assertIn(text, detail.inner_text())
        self.cell(0, 1).click()
        for text in ["規則或原文變更", "已上線 94 百萬", "重算 95 百萬", "hash"]:
            self.assertIn(text, detail.inner_text())
        self.cell(0, 2).click()
        for text in ["留空：Q4 推算條件：年度與 Q1–Q3 的分類集合不同", "年度分類", "iPhone、Mac", "保留先前上線的輸出", "37 百萬 ="]:
            self.assertIn(text, detail.inner_text())
        self.cell(0, 3).click()
        for text in ["失敗：加總：分類合計與總營收不符", "沒有先前上線的輸出"]:
            self.assertIn(text, detail.inner_text())


if __name__ == "__main__":
    unittest.main()
