"""viewer 讀取 `data/revenue/` 正式輸出與 `data/universe/`：Q／FY 序列、留空／失敗／差異標記、證據核對與路徑限制、
總覽頁、穩定度評分、對照資料的擷取紀錄與截圖，以及頁面的顯示。"""

import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))

from sec_revenue.viewer.published import PublishedRevenue
from sec_revenue.viewer.server import RevenueViewer

TABLE = "0000320193-25-000079-dceb82ec4e10-t27"
CAPTURES = ("20261104T013829Z", "20261105T020000Z")
MANUAL = "20261103T000000Z"
TICKERS_CSV = """ticker,cik,name,status,adopted_source,stability_score,stability_note,notes
AAPL,320193,Apple Inc.,ok,stockanalysis,4,產品別五類一致,
MSFT,789019,Microsoft Corporation,ok,stockanalysis,3,,
KO,21344,The Coca-Cola Company,wip,,,,
NVDA,1045810,NVIDIA Corporation,wip,,,,
TSLA,1318605,"Tesla, Inc.",drop,,,,
"""


def write_universe(directory: Path):
    """tickers.csv 五家（ok、wip、drop 各有）；AAPL 的 stockanalysis 有兩次擷取，各被一期引用，另有一次 manual 擷取。"""
    directory.mkdir(parents=True)
    (directory / "tickers.csv").write_text(TICKERS_CSV)
    base = directory / "references" / "A" / "AAPL"
    captures = {}
    for i, capture in enumerate(CAPTURES):
        files = {}
        for kind, name in (("png", "table.png"), ("html", "table.html"), ("txt", "table.txt")):
            path = base / "captures" / "stockanalysis" / capture / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"{capture}-{kind}".encode()
            path.write_bytes(content)
            files[kind] = {"path": f"captures/stockanalysis/{capture}/{name}", "sha256": hashlib.sha256(content).hexdigest()}
        stamp = capture
        captures[capture] = {
            "url": "https://stockanalysis.com/stocks/aapl/statistics/revenue-by-segment/",
            "captured_at": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}.000Z",
            "method": "browser_dom",
            "display_unit": "M",
            "files": files,
        }
    periods = [
        {"label": "Q3 2025", "period_end": "2025-06-30", "kind": "Q", "capture": CAPTURES[1], "values": {"iPhone": {"display": "44,582", "usd": 44582000000}}},
        {"label": "Q2 2025", "period_end": "2025-03-31", "kind": "Q", "capture": CAPTURES[0], "values": {"iPhone": {"display": "46,841", "usd": 46841000000}}},
    ]
    manual = {
        "captures": {MANUAL: {"captured_at": "2026-11-03T00:00:00.000Z", "method": "manual"}},
        "periods": [{"label": "FY2025", "kind": "FY", "capture": MANUAL, "values": {"iPhone": {"display": "209,586M", "usd": 209586000000}}}],
    }
    sources = {"stockanalysis": {"captures": captures, "periods": periods}, "manual": manual}
    reference = {"schema_version": 1, "ticker": "AAPL", "sources": sources}
    (base / "reference.json").write_text(json.dumps(reference))


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
    """AAPL 的 Q 序列四期涵蓋各種狀態：差異標記、重算不同（表格檔被改過）、不推算但保留已上線輸出、失敗且沒有輸出。

    KO（wip）有輸出目錄但沒有期別。
    """
    (root / "K" / "KO").mkdir(parents=True)
    (root / "K" / "KO" / "status.json").write_text(json.dumps({"ticker": "KO", "view": "product", "periods": {}}))
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
                            # 已上線是一個運算元，申報中的同一分類由兩個 fact 加權加總。
                            "category": "iPhone", "role": "quarter", "period": quarter,
                            "result": "different", "published_value": 95e6, "listed_value": 96e6,
                            "source": {"accession": "0000320193-26-000002", "form": "10-Q", "filing_date": "2026-05-01"},
                            "published_addends": [
                                {"operand": "op1", "concept": "us-gaap:Revenues", "dimensions": {"srt:ProductOrServiceAxis": "aapl:IPhoneMember"}, "weight": 1, "value": 95e6}
                            ],
                            "listed_addends": [
                                {"fact_id": "f-1a", "concept": "us-gaap:Revenues", "dimensions": {"srt:ProductOrServiceAxis": "aapl:IPhoneMember"}, "weight": 1, "value": 97e6},
                                {"fact_id": "f-1b", "concept": "us-gaap:Revenues", "dimensions": {"srt:ProductOrServiceAxis": "aapl:IPhoneCaseMember"}, "weight": -1, "value": 1e6},
                            ],
                        },
                        {
                            "category": "Eliminations", "role": "quarter", "period": quarter,
                            "result": "unparseable", "published_value": -1e6, "listed_value": None,
                            "source": {"accession": "0000320193-26-000002", "form": "10-Q", "filing_date": "2026-05-01"},
                            "published_addends": [
                                {"operand": "op2", "concept": "us-gaap:Revenues", "dimensions": {}, "weight": 1, "value": -1e6}
                            ],
                            "listed_addends": [
                                {"fact_id": "f-2", "concept": "us-gaap:Revenues", "dimensions": {}, "weight": 1, "value": None}
                            ],
                            "note": "無法比較：f-2：缺 decimals",
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
        self.root = Path(self.temp.name) / "revenue"
        self.universe = Path(self.temp.name) / "universe"
        write_universe(self.universe)
        self.viewer = RevenueViewer(self.root, self.universe / "tickers.csv")

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
        status, data = self.get("/api/companies")
        self.assertEqual((status, data["universe_errors"]), (200, []))
        companies = data["companies"]
        by_ticker = {c["ticker"]: c for c in companies}
        self.assertTrue(by_ticker["AAPL"]["listed"])
        self.assertTrue(by_ticker["AAPL"]["has_output"])
        self.assertFalse(by_ticker["MSFT"]["has_output"])

    def test_companies_carry_universe_fields(self):
        self.write_series_layout()
        by_ticker = {c["ticker"]: c for c in self.get("/api/companies")[1]["companies"]}
        aapl, ko = by_ticker["AAPL"], by_ticker["KO"]
        self.assertEqual(
            (aapl["universe_status"], aapl["adopted_source"], aapl["stability_score"], aapl["stability_note"], aapl["has_reference"]),
            ("ok", "stockanalysis", 4, "產品別五類一致", True),
        )
        self.assertEqual((ko["universe_status"], ko["stability_score"], ko["has_output"], ko["has_reference"]), ("wip", None, True, False))
        self.assertEqual(by_ticker["TSLA"]["universe_status"], "drop")

    def test_references_list_captures_by_source(self):
        self.write_series_layout()
        status, data = self.get("/api/references?ticker=AAPL")
        self.assertEqual((status, data["errors"]), (200, []))
        source, manual = data["sources"]
        self.assertEqual((source["source"], manual["source"]), ("stockanalysis", "manual"))
        self.assertEqual([(c["capture"], c["periods"], c["png"], c["url"]) for c in manual["captures"]], [(MANUAL, ["FY2025"], False, None)])
        self.assertEqual([(c["capture"], c["periods"], c["png"]) for c in source["captures"]], [(CAPTURES[0], ["Q2 2025"], True), (CAPTURES[1], ["Q3 2025"], True)])
        self.assertEqual(self.get("/api/references?ticker=KO")[1]["sources"], [])
        for url in ["/api/references?ticker=ZZZZ", "/api/references?ticker=../AAPL", "/api/references"]:
            self.assertEqual(self.viewer.request(url)[0], 400, url)

    def test_reference_capture_route_serves_only_recorded_png(self):
        self.write_series_layout()
        ok = self.viewer.request(f"/reference-capture/AAPL/stockanalysis/{CAPTURES[0]}/table.png")
        self.assertEqual(ok, (200, "image/png", f"{CAPTURES[0]}-png".encode()))
        for url in [
            f"/reference-capture/AAPL/stockanalysis/{CAPTURES[0]}/table.html",
            f"/reference-capture/AAPL/futu/{CAPTURES[0]}/table.png",
            "/reference-capture/AAPL/stockanalysis/20200101T000000Z/table.png",
            f"/reference-capture/AAPL/manual/{MANUAL}/table.png",
            f"/reference-capture/AAPL/stockanalysis/../{CAPTURES[0]}/table.png",
            f"/reference-capture/ZZZZ/stockanalysis/{CAPTURES[0]}/table.png",
        ]:
            self.assertEqual(self.viewer.request(url)[0], 404, url)

    def test_invalid_tickers_csv_is_reported(self):
        self.write_series_layout()
        (self.universe / "tickers.csv").write_text("ticker,cik\nAAPL,1\n")
        data = self.get("/api/companies")[1]
        self.assertTrue(data["universe_errors"])
        self.assertEqual(sorted(c["ticker"] for c in data["companies"]), ["AAPL", "KO"])

    def test_invalid_reference_lists_errors_and_serves_nothing(self):
        self.write_series_layout()
        png = self.universe / "references" / "A" / "AAPL" / "captures" / "stockanalysis" / CAPTURES[0] / "table.png"
        png.write_bytes(b"tampered")
        data = self.get("/api/references?ticker=AAPL")[1]
        self.assertEqual(data["sources"], [])
        self.assertTrue(any("sha256" in e for e in data["errors"]))
        self.assertEqual(self.viewer.request(f"/reference-capture/AAPL/stockanalysis/{CAPTURES[1]}/table.png")[0], 404)

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


class ViewerHeaderTests(unittest.TestCase):
    """經 HTTP server 回應的標頭：CSP 依路由路徑判斷，absolute-form 請求（GET http://host/...）同樣套用。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "revenue"
        write_fixture(root)
        write_universe(Path(self.temp.name) / "universe")
        # port 0：由系統指派一個暫用 port，測試結束即關閉。
        self.server = RevenueViewer(root, Path(self.temp.name) / "universe" / "tickers.csv").server("127.0.0.1", 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def test_csp_applies_to_absolute_form_requests(self):
        host, port = self.server.server_address[:2]
        for path, policy in [
            (f"/revenue-evidence/AAPL/FY/2025-09-27/{TABLE}.html", "sandbox"),
            ("/", "default-src 'none'"),
        ]:
            for target in (path, f"http://{host}:{port}{path}"):
                connection = http.client.HTTPConnection(host, port)
                connection.request("GET", target)
                response = connection.getresponse()
                response.read()
                connection.close()
                self.assertEqual(response.status, 200, target)
                self.assertIn(policy, response.getheader("Content-Security-Policy") or "", target)


class ViewerPage(unittest.TestCase):
    """以 Playwright 開 viewer 頁面；沒有 Playwright 或瀏覽器時略過。子類別的 `setUp` 決定開哪一頁。"""

    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest("沒有安裝 playwright")
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name) / "revenue"
        write_fixture(root)
        write_universe(Path(cls.temp.name) / "universe")
        # port 0：由系統指派一個暫用 port，測試結束即關閉。
        cls.server = RevenueViewer(root, Path(cls.temp.name) / "universe" / "tickers.csv").server("127.0.0.1", 0)
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

    def open(self, hash: str, ready: str):
        self.errors = []
        self.page = self.browser.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url + hash)
        self.page.wait_for_selector(ready)

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])


class PublishedViewerPageTests(ViewerPage):
    """公司頁：各種狀態的格子與明細、評分、搜尋框與對照資料。"""

    def setUp(self):
        self.open("#ticker=AAPL&series=Q", "#grid tbody")

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
        for text in ["調節項 Eliminations", "差異標記 1 筆", "無法解析", "f-2", "缺 decimals", "-1 百萬 ="]:
            self.assertIn(text, detail)
        self.assertNotIn("f-1a", detail)

    def test_detail_shows_records(self):
        detail = self.page.locator("#detail")
        self.cell(0, 0).click()
        for text in [
            "差異標記 1 筆", "數值不同", "申報列示值", "96 百萬", "10-Q 0000320193-26-000002",
            "已上線的加數", "申報中的加數", "f-1a", "f-1b", "aapl:IPhoneCaseMember", "op1",
        ]:
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

    def test_profile_shows_score_and_note(self):
        profile = self.page.locator("#profile").inner_text()
        for text in ["AAPL Apple Inc.", "ok", "Stock Analysis", "4 / 5", "產品別五類一致"]:
            self.assertIn(text, profile)

    def test_picker_searches_as_you_type(self):
        box = self.page.locator("#company")
        box.click()
        self.assertEqual(self.page.locator("#company-list li").all_inner_texts(), ["輸入代碼或名稱搜尋"])
        box.fill("o")
        tickers = self.page.locator("#company-list li").evaluate_all("items => items.map((li) => li.firstChild.textContent)")
        # KO 代碼含 o（第三級）排在 MSFT 名稱含 o（第四級）前面；NVDA 沒有輸出、TSLA 是 drop，不列。
        self.assertEqual(tickers, ["KO", "MSFT"])
        self.assertIn("wip", self.page.locator("#company-list li").first.inner_text())
        self.assertNotIn("wip", self.page.locator("#company-list li").nth(1).inner_text())
        box.fill("zzz")
        self.assertEqual(self.page.locator("#company-list li").all_inner_texts(), ["沒有符合的公司"])

    def test_references_section_loads_capture_on_open(self):
        section = self.page.locator("#references")
        section.locator("summary").first.wait_for()
        self.assertIn("Stock Analysis · 2 次擷取", section.inner_text())
        self.assertIn("採用", section.locator("summary").first.inner_text())
        self.assertIn("手動輸入 · 1 次擷取", section.inner_text())
        image = section.locator("img").first
        self.assertIsNone(image.get_attribute("src"))
        section.locator("summary").first.click()
        self.page.wait_for_selector("#references img[src]")
        self.assertEqual(image.get_attribute("src"), f"/reference-capture/AAPL/stockanalysis/{CAPTURES[0]}/table.png")
        section.locator("summary").nth(1).click()
        text = section.inner_text()
        for t in ["Q2 2025", "Q3 2025", "擷取頁面", "擷取時間 2026-11-04 01:38:29 UTC", "手動輸入，沒有截圖"]:
            self.assertIn(t, text)


class OverviewPageTests(ViewerPage):
    """沒有 ticker 的網址開總覽頁：列出 tickers.csv 的全部公司，可過濾、搜尋，有輸出的連到公司頁。"""

    def setUp(self):
        self.open("", "#overview tbody tr")

    def rows(self):
        return [r.split("\t") for r in self.page.locator("#overview tbody tr").all_inner_texts()]

    def test_lists_every_universe_company(self):
        self.assertFalse(self.page.locator("#overview-page").is_hidden())
        self.assertTrue(self.page.locator("#company-page").is_hidden())
        rows = {r[0]: r for r in self.rows()}
        self.assertEqual(sorted(rows), ["AAPL", "KO", "MSFT", "NVDA", "TSLA"])
        self.assertEqual(rows["AAPL"][2:], ["ok", "Stock Analysis", "4 / 5", "有"])
        self.assertEqual(rows["NVDA"][2:], ["wip", "—", "尚未評分", "尚無輸出"])
        self.assertEqual(self.page.locator("#overview tbody a").all_inner_texts(), ["AAPL", "KO"])

    def test_filter_and_search(self):
        self.page.select_option("#overview-status", "wip")
        self.assertEqual([r[0] for r in self.rows()], ["KO", "NVDA"])
        self.page.select_option("#overview-status", "")
        self.page.fill("#overview-search", "tesla")
        self.assertEqual([r[0] for r in self.rows()], ["TSLA"])

    def test_back_returns_to_previous_company(self):
        self.page.locator("#overview tbody a", has_text="AAPL").click()
        self.page.wait_for_selector("#grid tbody")
        self.page.locator("#company").fill("KO")
        self.page.keyboard.press("Enter")
        self.page.wait_for_selector("#profile strong:text-is('KO The Coca-Cola Company')")
        self.page.go_back()
        self.page.wait_for_selector("#profile strong:text-is('AAPL Apple Inc.')")
        self.page.go_back()
        self.page.wait_for_selector("#overview tbody tr")
        self.assertFalse(self.page.locator("#overview-page").is_hidden())

    def test_link_opens_company_and_nav_returns(self):
        self.page.locator("#overview tbody a", has_text="AAPL").click()
        self.page.wait_for_selector("#grid tbody")
        self.assertTrue(self.page.locator("#overview-page").is_hidden())
        self.assertIn("ticker=AAPL", self.page.url)
        self.page.locator("#nav-overview").click()
        self.page.wait_for_selector("#overview tbody tr")
        self.assertFalse(self.page.locator("#overview-page").is_hidden())


if __name__ == "__main__":
    unittest.main()
