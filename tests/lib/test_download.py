"""SEC 下載：任何 ticker、完整申報包與 SEC URL。HTTP 以合成回應注入，不連網。"""

import csv
import datetime as dt
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.download import (  # noqa: E402
    DownloadBatch,
    DownloadWorkflow,
    FilingIndexPage,
    FilingPackages,
    SecHttpClient,
    SecIdentityError,
    earnings_releases,
    is_blocking,
    is_inline_xbrl,
)
from sec_revenue.engines import JsonCodec  # noqa: E402
from sec_revenue.service import ParserRegistry  # noqa: E402
from sec_revenue.tickers import DownloadTickers, SupportedTickers  # noqa: E402
from sec_revenue.universe import load_tickers  # noqa: E402
from sec_revenue.workflow import PeriodSelection  # noqa: E402

ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
INLINE = (
    b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
    b'<body><div style="display:none"><ix:header/></div>inline</body></html>'
)


class FakeHttp:
    """合成 SEC 回應；記錄所有請求，缺少的 URL 視為測試錯誤。"""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.requests = []

    def get(self, url, kind):
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def http_error(url, code):
    return HTTPError(url, code, "synthetic", {}, None)


class SecFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "data"
        self.csv = Path(self.temp.name) / "tickers.csv"
        self.write_csv([])
        self.http = FakeHttp()

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self, rows):
        with self.csv.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                ["ticker", "cik", "name", "status", "adopted_source", "stability_score", "stability_note", "notes"]
            )
            for ticker, cik in rows:
                writer.writerow([ticker, cik, ticker + " Inc.", "wip", "", "", "", ""])

    def company_tickers(self, mapping):
        payload = {
            str(i): {"cik_str": int(cik), "ticker": ticker, "title": ticker}
            for i, (ticker, cik) in enumerate(mapping.items())
        }
        self.http.responses["https://www.sec.gov/files/company_tickers.json"] = json.dumps(payload).encode()

    @staticmethod
    def filing(cik, period, form="10-Q", sequence=1, filed=None, items=""):
        return {
            "accessionNumber": f"{int(cik):010d}-27-{sequence:06d}",
            "reportDate": period,
            "filingDate": filed or period[:8] + "28",
            "form": form,
            "primaryDocument": f"doc-{sequence}.htm",
            "items": items,
        }

    def submissions(self, cik, filings, with_items=True):
        keys = ["accessionNumber", "reportDate", "filingDate", "form", "primaryDocument"]
        keys += ["items"] if with_items else []
        columns = {key: [f[key] for f in filings] for key in keys}
        url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
        self.http.responses[url] = json.dumps({"filings": {"recent": columns, "files": []}}).encode()

    def package(self, cik, filing, extra=None, inline=True):
        """一份合成申報包：主文件、exhibit、XBRL instance、FilingSummary、R 頁面與排除檔。"""
        accession = filing["accessionNumber"]
        base = f"{ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/"
        primary = filing["primaryDocument"]
        files = {
            primary: INLINE if inline else b"<html><body>plain</body></html>",
            "ex99-1.htm": b"<html><body>press release</body></html>",
            "doc_htm.xml": b"<xbrl>instance</xbrl>",
            "doc.xsd": b"<schema/>",
            "g1.jpg": b"\xff\xd8synthetic-jpeg",
            "FilingSummary.xml": b"<FilingSummary/>",
            "R1.htm": b"<html>R1</html>",
            "R2.htm": b"<html>R2</html>",
            "Financial_Report.xlsx": b"PK-synthetic",
        }
        files.update(extra or {})
        excluded = [accession + ".txt", accession + "-index.htm", accession + "-index-headers.html", "0001-xbrl.zip"]
        entries = [{"name": n, "type": "text.gif"} for n in list(files) + excluded]
        entries.append({"name": "xslF345X05", "type": "dir"})
        listing = {"directory": {"item": entries}}
        self.http.responses[base + "index.json"] = json.dumps(listing).encode()
        rows = "".join(
            f'<tr><td>{i}</td><td>{desc}</td><td><a href="{href}">{name}</a></td><td>{kind}</td><td>1</td></tr>'
            for i, (desc, name, kind, href) in enumerate(
                [
                    ("10-Q", primary, "10-Q", f"/ix?doc=/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary}"),
                    ("Press release", "ex99-1.htm", "EX-99.1", f"/Archives/edgar/data/{int(cik)}/x/ex99-1.htm"),
                    ("Instance", "doc_htm.xml", "XML", f"/Archives/edgar/data/{int(cik)}/x/doc_htm.xml"),
                ],
                start=1,
            )
        )
        self.http.responses[base + accession + "-index.htm"] = (
            f'<html><body><table class="tableFile" summary="Document Format Files">'
            f"<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>{rows}</table></body></html>"
        ).encode()
        for name, body in files.items():
            self.http.responses[base + name] = body
        return base

    def workflow(self, **options):
        options.setdefault("packages", True)
        return DownloadWorkflow(ROOT, self.data, self.http, tickers_csv=self.csv, **options)


class AnyTickerPackageTests(SecFixture):
    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZQ": "999001"})
        self.q = self.filing("999001", "2027-03-31")
        self.submissions("999001", [self.q])
        self.base = self.package("999001", self.q)

    def test_unregistered_ticker_downloads_full_package_with_urls(self):
        self.assertNotIn("ZZZQ", ParserRegistry().entries)
        report = self.workflow().run(["ZZZQ"], PeriodSelection())
        company = report["companies"][0]
        self.assertEqual(company["cik"]["source"], "sec_company_tickers")
        self.assertIn("company_tickers_fetched_at_utc", company["cik"])
        self.assertNotIn("filings", company)
        self.assertFalse((self.data / "pipeline/ZZZQ/downloads.json").exists())

        package = JsonCodec.read(self.data / "pipeline/ZZZQ/packages.json")["packages"][self.q["accessionNumber"]]
        self.assertTrue(package["complete"])
        self.assertEqual(
            set(package["documents"]),
            {"doc-1.htm", "ex99-1.htm", "doc_htm.xml", "doc.xsd", "g1.jpg", "FilingSummary.xml"},
        )
        index_url = self.base + self.q["accessionNumber"] + "-index.htm"
        self.assertEqual(package["filing_index_url"], index_url)
        for name, document in package["documents"].items():
            raw = (self.data / document["path"]).read_bytes()
            self.assertEqual(document["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(document["source_url"], self.base + name)
            self.assertEqual(document["filing_index_url"], index_url)
        primary = package["documents"]["doc-1.htm"]
        self.assertTrue(primary["primary"] and primary["inline_xbrl"])
        self.assertEqual(
            primary["ixviewer_url"],
            "https://www.sec.gov/ix?doc=/Archives/edgar/data/999001/000099900127000001/doc-1.htm",
        )
        self.assertEqual(primary["type"], "10-Q")
        self.assertEqual(package["documents"]["ex99-1.htm"]["type"], "EX-99.1")
        self.assertIsNone(package["documents"]["ex99-1.htm"]["ixviewer_url"])
        self.assertTrue(package["documents"]["doc_htm.xml"]["path"].endswith(".xml"))
        self.assertTrue(package["documents"]["g1.jpg"]["path"].endswith(".jpg"))
        self.assertEqual(
            package["skipped"],
            {
                "R1.htm": "r_page_not_requested",
                "R2.htm": "r_page_not_requested",
                "Financial_Report.xlsx": "r_page_not_requested",
                self.q["accessionNumber"] + ".txt": "complete_submission_text",
                self.q["accessionNumber"] + "-index.htm": "filing_index_page",
                self.q["accessionNumber"] + "-index-headers.html": "filing_index_page",
                "0001-xbrl.zip": "archive_zip",
                "xslF345X05": "directory",
            },
        )
        self.assertEqual(package["failures"], {})
        self.assertNotIn(self.base + "R1.htm", self.http.requests)

    def test_rerun_is_cache_hit_and_r_pages_are_added_on_request(self):
        self.workflow().run(["ZZZQ"], PeriodSelection())
        before = len(self.http.requests)
        again = self.workflow().run(["ZZZQ"], PeriodSelection())
        self.assertEqual(again["companies"][0]["packages"][0]["status"], "cache_hit")
        self.assertEqual(len(self.http.requests), before)

        with_r = self.workflow(include_r_pages=True).run(["ZZZQ"], PeriodSelection())
        self.assertEqual(
            self.http.requests[before:],
            [self.base + "R1.htm", self.base + "R2.htm", self.base + "Financial_Report.xlsx"],
        )
        summary = with_r["companies"][0]["packages"][0]
        self.assertEqual((summary["status"], summary["r_pages_skipped"]), ("downloaded", 0))
        package = JsonCodec.read(self.data / "pipeline/ZZZQ/packages.json")["packages"][self.q["accessionNumber"]]
        self.assertIn("R1.htm", package["documents"])

    def test_single_file_failure_is_recorded_and_retried(self):
        self.http.responses[self.base + "ex99-1.htm"] = http_error(self.base + "ex99-1.htm", 404)
        report = DownloadBatch(self.workflow()).run(["ZZZQ"], PeriodSelection())
        self.assertFalse(report["complete"])
        self.assertEqual(report["succeeded"], [])
        self.assertEqual(report["failed"][0]["ticker"], "ZZZQ")
        package = JsonCodec.read(self.data / "pipeline/ZZZQ/packages.json")["packages"][self.q["accessionNumber"]]
        self.assertFalse(package["complete"])
        self.assertEqual(list(package["failures"]), ["ex99-1.htm"])
        self.assertIn("doc_htm.xml", package["documents"])

        self.http.responses[self.base + "ex99-1.htm"] = b"<html>ok</html>"
        before = len(self.http.requests)
        retry = DownloadBatch(self.workflow()).run(["ZZZQ"], PeriodSelection())
        self.assertTrue(retry["complete"])
        self.assertEqual(self.http.requests[before:], [self.base + "ex99-1.htm"])

    def test_offline_reads_package_cache_without_network(self):
        self.workflow().run(["ZZZQ"], PeriodSelection())
        before = len(self.http.requests)
        report = self.workflow().run(["ZZZQ"], PeriodSelection(), offline=True)
        self.assertEqual(report["companies"][0]["packages"][0]["status"], "offline_cache")
        self.assertEqual(len(self.http.requests), before)

    def test_corrupted_package_file_is_refused(self):
        self.workflow().run(["ZZZQ"], PeriodSelection())
        package = JsonCodec.read(self.data / "pipeline/ZZZQ/packages.json")["packages"][self.q["accessionNumber"]]
        (self.data / package["documents"]["doc.xsd"]["path"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash"):
            self.workflow().run(["ZZZQ"], PeriodSelection(), offline=True)


class CikResolutionTests(SecFixture):
    def test_tickers_csv_multi_cik_wins_over_company_tickers(self):
        self.write_csv([("XYZ", "200;100")])
        self.company_tickers({"XYZ": "300"})
        old = self.filing("100", "2026-03-31", sequence=1)
        new = self.filing("200", "2026-06-30", sequence=2)
        self.submissions("100", [old])
        self.submissions("200", [new])
        self.package("200", new)
        report = self.workflow().run(["XYZ"], PeriodSelection())
        self.assertEqual(report["companies"][0]["cik"], {"ciks": ["200", "100"], "source": "tickers_csv"})
        self.assertIn("https://data.sec.gov/submissions/CIK0000000100.json", self.http.requests)
        self.assertNotIn("https://www.sec.gov/files/company_tickers.json", self.http.requests)

    def test_company_tickers_cache_is_reused_and_refreshed_only_for_unknown(self):
        self.company_tickers({"AAA": "11", "BBB": "22"})
        for cik in ("11", "22"):
            filing = self.filing(cik, "2027-03-31")
            self.submissions(cik, [filing])
            self.package(cik, filing)
        self.workflow().run(["AAA"], PeriodSelection())
        self.workflow().run(["BBB"], PeriodSelection())
        self.assertEqual(self.http.requests.count("https://www.sec.gov/files/company_tickers.json"), 1)
        index = JsonCodec.read(self.data / "pipeline/_sec/company_tickers.json")
        self.assertIn("fetched_at_utc", index)
        self.assertTrue(index["receipt"]["path"].startswith("sec/_sec/company_tickers/"))

        with self.assertRaisesRegex(ValueError, "company_tickers"):
            self.workflow().run(["NOPE"], PeriodSelection())
        self.assertEqual(self.http.requests.count("https://www.sec.gov/files/company_tickers.json"), 2)

    def test_registry_ciks_match_tickers_csv(self):
        listed = {entry.ticker: list(entry.ciks) for entry in load_tickers()}
        for ticker, entry in ParserRegistry().entries.items():
            self.assertEqual(listed[ticker], [str(int(c)) for c in entry["submission_ciks"]], ticker)


class EarningsReleaseTests(SecFixture):
    def test_only_item_202_within_target_window(self):
        q1 = self.filing("5", "2027-03-31", sequence=1, filed="2027-05-01")
        q2 = self.filing("5", "2027-06-30", sequence=2, filed="2027-08-01")
        rows = [
            self.filing("5", "2027-01-20", "8-K", 3, filed="2027-01-20"),  # 上一季新聞稿，早於範圍
            self.filing("5", "2027-04-25", "8-K", 4, filed="2027-04-25"),  # Q1 新聞稿
            self.filing("5", "2027-05-10", "8-K", 5, filed="2027-05-10"),  # 非 2.02
            self.filing("5", "2027-07-25", "8-K", 6, filed="2027-07-25"),  # Q2 新聞稿
            self.filing("5", "2027-10-25", "8-K", 7, filed="2027-10-25"),  # Q3 新聞稿，超出 end+90
        ]
        items = {r["accessionNumber"]: "2.02,9.01" for r in rows}
        items[rows[2]["accessionNumber"]] = "5.02"
        chosen = earnings_releases(rows, items, [q1, q2], PeriodSelection("2027-01-01", "2027-06-30"))
        self.assertEqual([r["filingDate"] for r in chosen], ["2027-04-25", "2027-07-25"])
        latest = earnings_releases(rows, items, [q2], PeriodSelection(latest=True))
        self.assertEqual([r["filingDate"] for r in latest], ["2027-07-25", "2027-10-25"])

    def test_earnings_8k_package_is_downloaded(self):
        self.company_tickers({"EEE": "77"})
        q = self.filing("77", "2027-03-31", sequence=1, filed="2027-05-01")
        release = self.filing("77", "2027-04-25", "8-K", 2, filed="2027-04-25", items="2.02,9.01")
        other = self.filing("77", "2027-05-05", "8-K", 3, filed="2027-05-05", items="7.01")
        self.submissions("77", [q, release, other])
        self.package("77", q)
        self.package("77", release, inline=False)
        report = self.workflow().run(["EEE"], PeriodSelection())
        forms = {p["accession"]: p["form"] for p in report["companies"][0]["packages"]}
        self.assertEqual(forms, {q["accessionNumber"]: "10-Q", release["accessionNumber"]: "8-K"})
        catalog = JsonCodec.read(self.data / "pipeline/EEE/catalog.json")
        self.assertEqual(catalog["eight_k_items"][other["accessionNumber"]], "7.01")


class BatchTests(SecFixture):
    def setUp(self):
        super().setUp()
        self.company_tickers({"AAA": "11", "CCC": "33", "DDD": "44"})
        for cik in ("11", "33", "44"):
            filing = self.filing(cik, "2027-03-31")
            self.submissions(cik, [filing])
            self.package(cik, filing)

    def test_one_ticker_failure_does_not_stop_batch(self):
        report = DownloadBatch(self.workflow()).run(["AAA", "NOPE", "CCC"], PeriodSelection())
        self.assertEqual(report["succeeded"], ["AAA", "CCC"])
        self.assertEqual([f["ticker"] for f in report["failed"]], ["NOPE"])
        self.assertEqual(report["not_attempted"], [])
        self.assertIsNone(report["stopped"])
        self.assertFalse(report["complete"])

    def test_403_and_429_stop_the_whole_batch(self):
        for code in (403, 429):
            with self.subTest(code=code):
                url = "https://data.sec.gov/submissions/CIK0000000033.json"
                saved = self.http.responses[url]
                self.http.responses[url] = http_error(url, code)
                report = DownloadBatch(self.workflow()).run(["AAA", "CCC", "DDD"], PeriodSelection(), force=True)
                self.assertEqual(report["succeeded"], ["AAA"])
                self.assertEqual([f["ticker"] for f in report["failed"]], ["CCC"])
                self.assertEqual(report["not_attempted"], ["DDD"])
                self.assertIn("CCC", report["stopped"])
                self.http.responses[url] = saved

    def test_403_during_package_file_stops_batch_and_keeps_progress(self):
        base = f"{ARCHIVES}/11/000000001127000001/"
        self.http.responses[base + "doc.xsd"] = http_error(base + "doc.xsd", 403)
        report = DownloadBatch(self.workflow()).run(["AAA", "CCC"], PeriodSelection())
        self.assertEqual(report["not_attempted"], ["CCC"])
        package = JsonCodec.read(self.data / "pipeline/AAA/packages.json")["packages"]["0000000011-27-000001"]
        self.assertFalse(package["complete"])
        self.assertIn("doc-1.htm", package["documents"])

    def test_missing_identity_stops_batch(self):
        workflow = DownloadWorkflow(
            ROOT, self.data, SecHttpClient(user_agent=""), packages=True, tickers_csv=self.csv
        )
        report = DownloadBatch(workflow).run(["AAA", "CCC"], PeriodSelection())
        self.assertEqual(report["not_attempted"], ["CCC"])
        self.assertTrue(is_blocking(SecIdentityError("x")))

    def test_rate_limit_is_at_most_eight_per_second(self):
        self.assertEqual(SecHttpClient("Unit test unit@test.invalid", interval=0.01).interval, 0.125)


class RegisteredTickerTests(SecFixture):
    """有 parser 的公司：parser 文件取自申報包，downloads.json 與單獨下載時相同。"""

    def setUp(self):
        super().setUp()
        self.write_csv([("AAPL", "320193")])
        self.q = dict(self.filing("320193", "2027-03-31"), primaryDocument="aapl-20270331.htm")
        self.submissions("320193", [self.q])
        self.base = self.package("320193", self.q)

    def downloads(self, data):
        saved = JsonCodec.read(data / "pipeline/AAPL/downloads.json")
        return {
            accession: (entry["filing"], {role: r["sha256"] for role, r in entry["documents"].items()})
            for accession, entry in saved["filings"].items()
        }

    def test_parser_documents_reuse_package_and_match_parser_only_download(self):
        self.workflow().run(["AAPL"], PeriodSelection())
        primary = self.base + "aapl-20270331.htm"
        self.assertEqual(self.http.requests.count(primary), 1)
        with_packages = self.downloads(self.data)

        parser_only = Path(self.temp.name) / "parser-only"
        DownloadWorkflow(ROOT, parser_only, self.http, tickers_csv=self.csv).run(["AAPL"], PeriodSelection())
        self.assertEqual(self.downloads(parser_only), with_packages)
        saved = JsonCodec.read(self.data / "pipeline/AAPL/downloads.json")
        receipt = saved["filings"][self.q["accessionNumber"]]["documents"]["primary"]
        self.assertEqual(set(receipt), {"source_url", "path", "sha256", "source_format", "bytes"})
        self.assertEqual(receipt["source_url"], primary)


class FilingIndexPageTests(unittest.TestCase):
    def test_types_from_ix_and_plain_links(self):
        raw = (
            b'<table class="tableFile"><tr><th>Seq</th></tr>'
            b'<tr><td>1</td><td>Annual report</td><td><a href="/ix?doc=/Archives/edgar/data/1/2/a.htm">a.htm</a></td><td>10-K</td><td>9</td></tr>'
            b'<tr><td>2</td><td></td><td><a href="/Archives/edgar/data/1/2/ex21.htm">ex21.htm</a></td><td>EX-21</td><td>9</td></tr>'
            b"</table>"
        )
        self.assertEqual(
            FilingIndexPage.document_types(raw),
            {
                "a.htm": {"type": "10-K", "description": "Annual report"},
                "ex21.htm": {"type": "EX-21", "description": ""},
            },
        )


class TickerSelectionTests(SecFixture):
    def test_all_is_allstate_and_all_flag_reads_tickers_csv(self):
        self.write_csv([("AAPL", "320193"), ("ALL", "899051")])
        selection = DownloadTickers(self.csv)
        self.assertEqual(selection.select(["ALL"]), ["ALL"])
        self.assertEqual(selection.select(all_tickers=True), ["AAPL", "ALL"])
        self.assertEqual(selection.select(["msft"], all_tickers=True), ["AAPL", "ALL", "MSFT"])
        with self.assertRaisesRegex(ValueError, "--all"):
            selection.select()
        with self.assertRaises(ValueError):
            selection.select(["../AAPL"])
        with self.assertRaises(ValueError):
            SupportedTickers().select(["ALL"])


class ReviewFixTests(SecFixture):
    """中斷、離線、修訂版、CIK 變更、8-K item、命名規則與 inline XBRL 判定。"""

    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZQ": "999001", "OK": "999002"})
        self.q = self.filing("999001", "2027-03-31")
        self.submissions("999001", [self.q])
        self.base = self.package("999001", self.q)
        ok = self.filing("999002", "2027-03-31")
        self.submissions("999002", [ok])
        self.package("999002", ok)

    def package_record(self, ticker="ZZZQ", accession=None):
        return JsonCodec.read(self.data / f"pipeline/{ticker}/packages.json")["packages"][
            accession or self.q["accessionNumber"]
        ]

    def test_403_interrupted_package_is_not_offline_success(self):
        self.http.responses[self.base + "doc.xsd"] = http_error(self.base + "doc.xsd", 403)
        stopped = DownloadBatch(self.workflow()).run(["ZZZQ"], PeriodSelection())
        self.assertIsNotNone(stopped["stopped"])
        package = self.package_record()
        self.assertFalse(package["complete"])
        self.assertEqual(package["failures"], {})
        self.assertIn("doc-1.htm", package["documents"])

        offline = DownloadBatch(self.workflow()).run(["ZZZQ"], PeriodSelection(), offline=True)
        self.assertEqual(offline["succeeded"], [])
        self.assertIn("offline_incomplete", offline["failed"][0]["error"])

        self.http.responses[self.base + "doc.xsd"] = b"<schema/>"
        before = len(self.http.requests)
        resumed = DownloadBatch(self.workflow()).run(["ZZZQ"], PeriodSelection())
        self.assertEqual(resumed["succeeded"], ["ZZZQ"])
        # 只補中斷時尚未取得的檔案；已下載的主文件等不重抓。
        self.assertEqual(
            self.http.requests[before:],
            [self.base + "doc.xsd", self.base + "g1.jpg", self.base + "FilingSummary.xml"],
        )

    def test_offline_r_pages_requested_but_missing_is_reported(self):
        self.workflow().run(["ZZZQ"], PeriodSelection())
        offline = DownloadBatch(self.workflow(include_r_pages=True)).run(
            ["ZZZQ"], PeriodSelection(), offline=True
        )
        self.assertEqual(offline["succeeded"], [])
        self.assertIn("offline_incomplete", offline["failed"][0]["error"])

    def test_protocol_error_on_one_file_is_a_file_failure(self):
        self.http.responses[self.base + "doc.xsd"] = http.client.IncompleteRead(b"partial")
        report = DownloadBatch(self.workflow()).run(["ZZZQ", "OK"], PeriodSelection())
        self.assertEqual(report["succeeded"], ["OK"])
        self.assertIn("IncompleteRead", self.package_record()["failures"]["doc.xsd"]["error"])
        self.assertIn("doc_htm.xml", self.package_record()["documents"])

    def test_unexpected_ticker_error_fails_only_that_ticker(self):
        url = "https://data.sec.gov/submissions/CIK0000999001.json"
        self.http.responses[url] = RuntimeError("synthetic bug")
        report = DownloadBatch(self.workflow()).run(["ZZZQ", "OK"], PeriodSelection())
        self.assertEqual(report["succeeded"], ["OK"])
        self.assertEqual(report["failed"], [{"ticker": "ZZZQ", "error": "RuntimeError: synthetic bug"}])
        self.assertIsNone(report["stopped"])

    def test_company_tickers_403_stops_batch(self):
        url = "https://www.sec.gov/files/company_tickers.json"
        self.http.responses[url] = http_error(url, 403)
        report = DownloadBatch(self.workflow()).run(["ZZZQ", "OK"], PeriodSelection())
        self.assertEqual(report["not_attempted"], ["OK"])
        self.assertIn("ZZZQ", report["stopped"])

    def test_company_tickers_older_than_seven_days_is_refetched(self):
        url = "https://www.sec.gov/files/company_tickers.json"
        self.workflow().run(["ZZZQ"], PeriodSelection())
        index_path = self.data / "pipeline/_sec/company_tickers.json"
        for days, expected in ((6, 1), (8, 2)):
            with self.subTest(days=days):
                index = JsonCodec.read(index_path)
                index["fetched_at_utc"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
                JsonCodec.write(index_path, index)
                self.workflow().run(["ZZZQ"], PeriodSelection())
                self.assertEqual(self.http.requests.count(url), expected)

    def test_amended_and_original_10k_are_both_packaged(self):
        self.company_tickers({"AMD1": "999003"})
        original = self.filing("999003", "2026-12-31", "10-K", 1, filed="2027-02-20")
        amended = dict(
            self.filing("999003", "2026-12-31", "10-K/A", 2, filed="2027-04-20"), primaryDocument="doc-2.htm"
        )
        self.submissions("999003", [original, amended])
        self.package("999003", original)
        self.package("999003", amended)
        report = self.workflow().run(["AMD1"], PeriodSelection())
        forms = sorted(p["form"] for p in report["companies"][0]["packages"])
        self.assertEqual(forms, ["10-K", "10-K/A"])

    def test_changed_cik_list_refetches_catalog(self):
        self.write_csv([("XYZ", "100")])
        old = self.filing("100", "2026-03-31", sequence=1)
        new = self.filing("200", "2026-06-30", sequence=2)
        self.submissions("100", [old])
        self.submissions("200", [new])
        self.package("100", old)
        self.package("200", new)
        self.workflow().run(["XYZ"], PeriodSelection())
        self.assertEqual(JsonCodec.read(self.data / "pipeline/XYZ/catalog.json")["ciks"], ["100"])

        self.write_csv([("XYZ", "200;100")])
        with self.assertRaisesRegex(ValueError, "CIK"):
            self.workflow().run(["XYZ"], PeriodSelection(), offline=True)
        report = self.workflow().run(["XYZ"], PeriodSelection())
        self.assertIn("https://data.sec.gov/submissions/CIK0000000200.json", self.http.requests)
        self.assertEqual(report["companies"][0]["target_periods"], ["2026-06-30"])
        self.assertEqual(JsonCodec.read(self.data / "pipeline/XYZ/catalog.json")["ciks"], ["200", "100"])

    def test_missing_8k_items_are_refetched_or_reported(self):
        self.company_tickers({"EEE": "77"})
        q = self.filing("77", "2027-03-31", sequence=1, filed="2027-05-01")
        release = self.filing("77", "2027-04-25", "8-K", 2, filed="2027-04-25", items="2.02,9.01")
        self.submissions("77", [q, release])
        self.package("77", q)
        self.package("77", release, inline=False)
        self.workflow().run(["EEE"], PeriodSelection())
        # 模擬舊 catalog：這份 8-K 沒有 item 資料。
        path = self.data / "pipeline/EEE/catalog.json"
        catalog = JsonCodec.read(path)
        del catalog["eight_k_items"][release["accessionNumber"]]
        JsonCodec.write(path, catalog)
        submissions = "https://data.sec.gov/submissions/CIK0000000077.json"
        before = self.http.requests.count(submissions)
        report = DownloadBatch(self.workflow()).run(["EEE"], PeriodSelection())
        self.assertEqual(self.http.requests.count(submissions), before + 1)
        self.assertEqual(report["succeeded"], ["EEE"])

        # SEC 回應本身沒有 items 欄：明確列為未知並讓這家失敗，不當成非 2.02。
        catalog = JsonCodec.read(path)
        del catalog["eight_k_items"][release["accessionNumber"]]
        JsonCodec.write(path, catalog)
        self.submissions("77", [q, release], with_items=False)
        report = DownloadBatch(self.workflow()).run(["EEE"], PeriodSelection())
        self.assertEqual(report["companies"][0]["eight_k_items_missing"], [release["accessionNumber"]])
        self.assertIn("8-K item", report["failed"][0]["error"])

    def test_catalog_skips_rows_without_primary_document(self):
        """歷史分頁的 1990 年代純文字申報沒有主文件；略過該列，不讓整家失敗。"""
        self.company_tickers({"OLD": "55"})
        q = self.filing("55", "2027-03-31")
        legacy = dict(self.filing("55", "1997-03-31", sequence=9), primaryDocument="")
        self.submissions("55", [q, legacy])
        self.package("55", q)
        report = self.workflow().run(["OLD"], PeriodSelection())
        self.assertEqual(report["companies"][0]["target_periods"], ["2027-03-31"])
        catalog = JsonCodec.read(self.data / "pipeline/OLD/catalog.json")
        self.assertNotIn(legacy["accessionNumber"], {f["accessionNumber"] for f in catalog["filings"]})
        bad = dict(self.filing("55", "2027-06-30", sequence=10), primaryDocument="bad name.htm")
        self.submissions("55", [q, bad])
        with self.assertRaisesRegex(ValueError, "主文件名"):
            self.workflow().run(["OLD"], PeriodSelection(), force=True)

    def test_name_rules(self):
        filing = self.q
        self.assertEqual(FilingPackages.classify(filing, "..", False), "unsupported_name")
        self.assertEqual(FilingPackages.classify(filing, ".", False), "unsupported_name")
        self.assertEqual(FilingPackages.classify(filing, "Financial_Report.xls", False), "r_page_not_requested")
        self.assertEqual(FilingPackages.classify(filing, "R12.xml", False), "r_page_not_requested")
        self.assertIsNone(FilingPackages.classify(filing, "R12.htm", True))
        self.assertEqual(FilingPackages.classify(filing, "sub", False, is_dir=True), "directory")

    def test_inline_xbrl_requires_header_in_declared_namespace(self):
        self.assertTrue(is_inline_xbrl(INLINE))
        mention = b"<html><body>See http://www.xbrl.org/2013/inlineXBRL for details</body></html>"
        self.assertFalse(is_inline_xbrl(mention))
        no_header = b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>x</body></html>'
        self.assertFalse(is_inline_xbrl(no_header))
        self.assertFalse(is_inline_xbrl(b"not markup at all"))


class RateLimitTests(unittest.TestCase):
    def test_requests_are_spaced_at_least_125ms(self):
        clock = {"now": 1000.0}
        started = []
        client = SecHttpClient("Unit test unit@test.invalid")
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_type.return_value = "application/octet-stream"
        response.headers.get.return_value = "identity"
        response.read.return_value = b"x"

        def open_request(request, timeout):
            started.append(clock["now"])
            response.geturl.return_value = request.full_url
            clock["now"] += 0.01  # 回應本身花 10ms
            return response

        def sleep(seconds):
            clock["now"] += seconds

        with patch("sec_revenue.download.time.monotonic", side_effect=lambda: clock["now"]), patch(
            "sec_revenue.download.time.sleep", side_effect=sleep
        ), patch.object(client.opener, "open", side_effect=open_request):
            for i in range(5):
                client.get(f"{ARCHIVES}/1/2/f{i}.xml", "file")
        gaps = [b - a for a, b in zip(started, started[1:])]
        self.assertEqual(len(gaps), 4)
        for gap in gaps:
            self.assertGreaterEqual(gap, 0.125 - 1e-9)
        self.assertLessEqual(len(started) / (started[-1] - started[0] + 0.125), 8 + 1e-9)


class ParserPackageParityTests(SecFixture):
    """PGR 經 filing index 取 Exhibit 13、CAT／UPS 財報 8-K exhibit：申報包模式與只下載 parser 文件一致。"""

    def downloads(self, data, ticker):
        saved = JsonCodec.read(data / f"pipeline/{ticker}/downloads.json")
        return {
            accession: (entry["filing"], {role: r["sha256"] for role, r in entry["documents"].items()})
            for accession, entry in saved["filings"].items()
        }

    def assert_parity(self, ticker):
        self.workflow().run([ticker], PeriodSelection())
        with_packages = self.downloads(self.data, ticker)
        parser_only = Path(self.temp.name) / "parser-only"
        DownloadWorkflow(ROOT, parser_only, self.http, tickers_csv=self.csv).run([ticker], PeriodSelection())
        self.assertEqual(self.downloads(parser_only, ticker), with_packages)
        return with_packages

    def test_pgr_exhibit_13_from_filing_index(self):
        self.write_csv([("PGR", "80661")])
        annual = dict(self.filing("80661", "2026-12-31", "10-K", 1, filed="2027-02-25"), primaryDocument="pgr-20261231.htm")
        self.submissions("80661", [annual])
        exhibit = "pgr-20261231_d2.htm"
        base = self.package("80661", annual, extra={exhibit: b"<html>consolidated exhibit 13</html>"})
        result = self.assert_parity("PGR")
        roles = result[annual["accessionNumber"]][1]
        self.assertEqual(set(roles), {"primary", "consolidated"})
        self.assertEqual(roles["consolidated"], hashlib.sha256(b"<html>consolidated exhibit 13</html>").hexdigest())
        self.assertEqual(self.http.requests.count(base + exhibit), 2)  # 兩個模式各抓一次，申報包模式不重複

    def test_amendment_packages_both_but_parser_keeps_its_single_choice(self):
        self.write_csv([("AAPL", "320193")])
        original = dict(self.filing("320193", "2026-12-31", "10-K", 1, filed="2027-02-20"), primaryDocument="a.htm")
        amended = dict(self.filing("320193", "2026-12-31", "10-K/A", 2, filed="2027-04-20"), primaryDocument="b.htm")
        self.submissions("320193", [original, amended])
        self.package("320193", original)
        self.package("320193", amended)
        result = self.assert_parity("AAPL")
        self.assertEqual(list(result), [amended["accessionNumber"]])
        packages = JsonCodec.read(self.data / "pipeline/AAPL/packages.json")["packages"]
        self.assertEqual(set(packages), {original["accessionNumber"], amended["accessionNumber"]})

    def test_cat_and_ups_earnings_exhibit_from_package(self):
        cases = {
            "CAT": ("18230", "0000018230-26-000052", "ex991toformcat3q2026earnin.htm"),
            "UPS": ("1090727", "0001628280-26-067381", "exhibit991-earningspressre.htm"),
        }
        for ticker, (cik, accession, exhibit) in cases.items():
            with self.subTest(ticker=ticker):
                self.data = Path(self.temp.name) / ("data-" + ticker)
                self.write_csv([(ticker, cik)])
                event = {
                    "accessionNumber": accession,
                    "reportDate": "2026-10-28",
                    "filingDate": "2026-10-28",
                    "form": "8-K",
                    "primaryDocument": "form8k.htm",
                    "items": "2.02,9.01",
                }
                self.submissions(cik, [event])
                base = self.package(cik, event, extra={exhibit: f"<html>{ticker} release</html>".encode()}, inline=False)
                result = self.assert_parity(ticker)
                filing, roles = result[accession]
                self.assertEqual((filing["reportDate"], filing["primaryDocument"]), ("2026-09-30", exhibit))
                self.assertEqual(roles["primary"], hashlib.sha256(f"<html>{ticker} release</html>".encode()).hexdigest())
                package = JsonCodec.read(self.data / f"pipeline/{ticker}/packages.json")["packages"][accession]
                self.assertEqual(package["filing"]["primaryDocument"], "form8k.htm")
                self.assertTrue(package["documents"]["form8k.htm"]["primary"])
                self.assertEqual(self.http.requests.count(base + exhibit), 2)
                import shutil

                shutil.rmtree(Path(self.temp.name) / "parser-only")


if __name__ == "__main__":
    unittest.main()
