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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.download.http import SecHttpClient, SecIdentityError, is_blocking  # noqa: E402
from sec_revenue.download.packages import FilingIndexPage, FilingPackages, is_inline_xbrl  # noqa: E402
from sec_revenue.download.plan import earnings_releases  # noqa: E402
from sec_revenue.download.workflow import DownloadBatch, DownloadWorkflow  # noqa: E402
from sec_revenue.common.jsonio import JsonCodec  # noqa: E402
from sec_revenue.common.periods import PeriodSelection  # noqa: E402
from sec_revenue.download.tickers import DownloadTickers  # noqa: E402
from sec_revenue.revenue.filings import FilingSet  # noqa: E402

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
        return DownloadWorkflow(ROOT, self.data, self.http, tickers_csv=self.csv, **options)


class AnyTickerPackageTests(SecFixture):
    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZQ": "999001"})
        self.q = self.filing("999001", "2027-03-31")
        self.submissions("999001", [self.q])
        self.base = self.package("999001", self.q)

    def test_any_ticker_downloads_full_package_with_urls(self):
        report = self.workflow().run(["ZZZQ"], PeriodSelection())
        company = report["companies"][0]
        self.assertEqual(company["cik"]["source"], "sec_company_tickers")
        self.assertIn("company_tickers_fetched_at_utc", company["cik"])

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
            ROOT, self.data, SecHttpClient(user_agent=""), tickers_csv=self.csv
        )
        report = DownloadBatch(workflow).run(["AAA", "CCC"], PeriodSelection())
        self.assertEqual(report["not_attempted"], ["CCC"])
        self.assertTrue(is_blocking(SecIdentityError("x")))

    def test_rate_limit_is_at_most_eight_per_second(self):
        self.assertEqual(SecHttpClient("Unit test unit@test.invalid", interval=0.01).interval, 0.125)


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

    def test_empty_ticker_file_is_rejected(self):
        path = Path(self.temp.name) / "empty.txt"
        path.write_text("# no tickers\n")
        with self.assertRaisesRegex(ValueError, "ticker 清單檔為空"):
            DownloadTickers(self.csv).select(file=path)


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

    def test_package_records_the_actual_form_of_an_amendment(self):
        # catalog 的 form 是表單類別；申報包記錄實際表單，parse 才分得出修正申報。
        self.company_tickers({"AMD2": "999006"})
        original = self.filing("999006", "2026-12-31", "10-K", 1, filed="2027-02-20")
        amended = dict(self.filing("999006", "2026-12-31", "10-K/A", 2, filed="2027-04-20"), primaryDocument="doc-2.htm")
        self.submissions("999006", [original, amended])
        self.package("999006", original)
        self.package("999006", amended)
        self.workflow().run(["AMD2"], PeriodSelection())
        catalog = {f["accessionNumber"]: f["form"] for f in JsonCodec.read(self.data / "pipeline/AMD2/catalog.json")["filings"]}
        self.assertEqual(catalog[amended["accessionNumber"]], "10-K")
        packages = JsonCodec.read(self.data / "pipeline/AMD2/packages.json")["packages"]
        self.assertEqual(
            {a: (p["filing"]["form"], p["filing"]["original_form"]) for a, p in packages.items()},
            {original["accessionNumber"]: ("10-K", "10-K"), amended["accessionNumber"]: ("10-K/A", "10-K/A")},
        )
        filings = FilingSet(self.data, "AMD2")
        self.assertEqual([f.form for f in filings.filings], ["10-K", "10-K/A"])
        self.assertEqual(filings.select("2026-12-31").accession, original["accessionNumber"])

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

        with patch("sec_revenue.download.http.time.monotonic", side_effect=lambda: clock["now"]), patch(
            "sec_revenue.download.http.time.sleep", side_effect=sleep
        ), patch.object(client.opener, "open", side_effect=open_request):
            for i in range(5):
                client.get(f"{ARCHIVES}/1/2/f{i}.xml", "file")
        gaps = [b - a for a, b in zip(started, started[1:])]
        self.assertEqual(len(gaps), 4)
        for gap in gaps:
            self.assertGreaterEqual(gap, 0.125 - 1e-9)
        self.assertLessEqual(len(started) / (started[-1] - started[0] + 0.125), 8 + 1e-9)


class HistoryAndDependencyTests(SecFixture):
    """歷史分頁、Q4 依賴期別與離線沿用。"""

    CIK = "999003"

    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZH": self.CIK})

    def submissions_with_history(self, recent, older):
        """recent 分頁只含 `recent`，較舊的申報放在一個歷史分頁。"""
        keys = ["accessionNumber", "reportDate", "filingDate", "form", "primaryDocument", "items"]
        page = f"CIK{int(self.CIK):010d}-submissions-001.json"
        columns = {key: [f[key] for f in recent] for key in keys}
        url = f"https://data.sec.gov/submissions/CIK{int(self.CIK):010d}.json"
        self.http.responses[url] = json.dumps({"filings": {"recent": columns, "files": [{"name": page}]}}).encode()
        self.http.responses["https://data.sec.gov/submissions/" + page] = json.dumps(
            {key: [f[key] for f in older] for key in keys}
        ).encode()
        return "https://data.sec.gov/submissions/" + page

    def fiscal_year(self):
        prior = self.filing(self.CIK, "2026-12-31", "10-K", 1, filed="2027-02-20")
        quarters = [
            self.filing(self.CIK, period, "10-Q", n, filed=filed)
            for n, (period, filed) in enumerate(
                [("2027-03-31", "2027-05-01"), ("2027-06-30", "2027-08-01"), ("2027-09-30", "2027-11-01")], start=2
            )
        ]
        annual = self.filing(self.CIK, "2027-12-31", "10-K", 5, filed="2028-02-20")
        for filing in [prior, *quarters, annual]:
            self.package(self.CIK, filing)
        return prior, quarters, annual

    def test_history_pages_are_loaded_for_older_range(self):
        recent = self.filing(self.CIK, "2027-03-31", sequence=2)
        old = self.filing(self.CIK, "2024-03-31", sequence=1)
        page = self.submissions_with_history([recent], [old])
        self.package(self.CIK, old)
        result = self.workflow().run(["ZZZH"], PeriodSelection("2024-01-01", "2024-06-30"))
        self.assertEqual(result["companies"][0]["target_periods"], ["2024-03-31"])
        self.assertIn(page, self.http.requests)

    def test_refresh_keeps_downloaded_history_for_offline_use(self):
        recent = self.filing(self.CIK, "2027-03-31", sequence=2)
        old = self.filing(self.CIK, "2024-03-31", sequence=1)
        self.submissions_with_history([recent], [old])
        self.package(self.CIK, old)
        self.package(self.CIK, recent)
        self.workflow().run(["ZZZH"], PeriodSelection("2024-01-01", "2024-06-30"))
        self.workflow().run(["ZZZH"], PeriodSelection(latest=True))
        before = len(self.http.requests)
        cached = self.workflow().run(["ZZZH"], PeriodSelection("2024-01-01", "2024-06-30"), offline=True)
        self.assertEqual(cached["companies"][0]["target_periods"], ["2024-03-31"])
        self.assertEqual(len(self.http.requests), before)

    def test_offline_and_force_conflict(self):
        with self.assertRaisesRegex(ValueError, "--force"):
            self.workflow().run(["ZZZH"], PeriodSelection(), force=True, offline=True)
        with self.assertRaisesRegex(ValueError, "--force"):
            DownloadBatch(self.workflow()).run(["ZZZH"], PeriodSelection(), force=True, offline=True)
        self.assertEqual(self.http.requests, [])

    def test_annual_target_downloads_same_year_quarters_and_prior_10k(self):
        prior, quarters, annual = self.fiscal_year()
        self.submissions(self.CIK, [prior, *quarters, annual])
        company = self.workflow().run(["ZZZH"], PeriodSelection("2027-12-01", "2027-12-31"))["companies"][0]
        self.assertEqual(company["target_periods"], ["2027-12-31"])
        self.assertEqual(company["dependency_periods"], ["2026-12-31", "2027-03-31", "2027-06-30", "2027-09-30"])
        packaged = set(JsonCodec.read(self.data / "pipeline/ZZZH/packages.json")["packages"])
        self.assertEqual(packaged, {f["accessionNumber"] for f in [prior, *quarters, annual]})

    def test_prior_10k_outside_recent_page_reloads_full_history(self):
        prior, quarters, annual = self.fiscal_year()
        page = self.submissions_with_history([*quarters, annual], [prior])
        company = self.workflow().run(["ZZZH"], PeriodSelection("2027-12-01", "2027-12-31"))["companies"][0]
        self.assertIn(page, self.http.requests)
        self.assertNotIn("dependencies_unresolved", company)
        self.assertIn("2026-12-31", company["dependency_periods"])
        self.assertIn(prior["accessionNumber"], JsonCodec.read(self.data / "pipeline/ZZZH/packages.json")["packages"])

    def test_unresolved_dependency_fails_the_company(self):
        _, quarters, annual = self.fiscal_year()
        self.submissions(self.CIK, [*quarters, annual])
        report = DownloadBatch(self.workflow()).run(["ZZZH"], PeriodSelection("2027-12-01", "2027-12-31"))
        self.assertEqual(report["succeeded"], [])
        self.assertIn("Q4 依賴期別無法確定", report["failed"][0]["error"])
        self.assertFalse(report["complete"])


class DryRunTests(SecFixture):
    """`--dry-run`：只讀本機 catalog 與 packages.json。"""

    CIK = "999004"

    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZD": self.CIK})
        self.prior = self.filing(self.CIK, "2026-12-31", "10-K", 1, filed="2027-02-20")
        self.q3 = self.filing(self.CIK, "2027-09-30", "10-Q", 2, filed="2027-11-01")
        self.annual = self.filing(self.CIK, "2027-12-31", "10-K", 3, filed="2028-02-20")
        self.submissions(self.CIK, [self.prior, self.q3, self.annual])
        for filing in (self.prior, self.q3, self.annual):
            self.package(self.CIK, filing)

    def snapshot(self):
        return {p: p.read_bytes() for p in sorted(self.data.rglob("*")) if p.is_file()}

    def dry_run(self, selection):
        offline_http = FakeHttp()
        workflow = DownloadWorkflow(ROOT, self.data, offline_http, tickers_csv=self.csv)
        before = self.snapshot()
        report = workflow.run(["ZZZD"], selection, dry_run=True)
        self.assertEqual(offline_http.requests, [])
        self.assertEqual(self.snapshot(), before)
        return report

    def test_lists_missing_dependency_without_network_or_writes(self):
        self.workflow().run(["ZZZD"], PeriodSelection("2027-12-01", "2027-12-31"))
        packages_path = self.data / "pipeline/ZZZD/packages.json"
        saved = JsonCodec.read(packages_path)
        del saved["packages"][self.q3["accessionNumber"]]
        JsonCodec.write(packages_path, saved)
        report = self.dry_run(PeriodSelection("2027-12-01", "2027-12-31"))
        company = report["companies"][0]
        self.assertEqual(company["missing_targets"], [])
        self.assertEqual(
            [(m["accession"], m["state"]) for m in company["missing_dependencies"]],
            [(self.q3["accessionNumber"], "not_downloaded")],
        )
        self.assertFalse(report["complete"])

    def test_complete_when_everything_is_downloaded(self):
        self.workflow().run(["ZZZD"], PeriodSelection("2027-12-01", "2027-12-31"))
        report = self.dry_run(PeriodSelection("2027-12-01", "2027-12-31"))
        self.assertTrue(report["complete"])
        self.assertNotIn("catalog_incomplete", report["companies"][0])

    def test_catalog_not_covering_range_is_catalog_incomplete(self):
        recent = self.filing(self.CIK, "2027-03-31", sequence=5)
        url = f"https://data.sec.gov/submissions/CIK{int(self.CIK):010d}.json"
        columns = {k: [recent[k]] for k in ["accessionNumber", "reportDate", "filingDate", "form", "primaryDocument", "items"]}
        page = f"CIK{int(self.CIK):010d}-submissions-001.json"
        self.http.responses[url] = json.dumps({"filings": {"recent": columns, "files": [{"name": page}]}}).encode()
        self.package(self.CIK, recent)
        self.workflow().run(["ZZZD"], PeriodSelection())
        report = self.dry_run(PeriodSelection("2025-01-01"))
        company = report["companies"][0]
        self.assertIn("2025-01-01", company["catalog_incomplete"][0])
        self.assertFalse(report["complete"])

    def test_missing_catalog_is_an_error(self):
        report = self.dry_run(PeriodSelection())
        self.assertIn("沒有本機 catalog", report["companies"][0]["error"])
        self.assertFalse(report["complete"])


class PriorAnnualDependencyTests(SecFixture):
    """10-Q 目標推算財年所需的上一份 10-K。"""

    CIK = "999006"

    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZP": self.CIK})
        self.prior = self.filing(self.CIK, "2026-05-31", "10-K", 1, filed="2026-06-20")
        self.q1 = self.filing(self.CIK, "2026-08-31", "10-Q", 2, filed="2026-09-10")
        self.q2 = self.filing(self.CIK, "2026-11-30", "10-Q", 3, filed="2026-12-10")

    def test_mid_year_start_downloads_prior_10k(self):
        self.submissions(self.CIK, [self.prior, self.q1, self.q2])
        for filing in (self.prior, self.q1, self.q2):
            self.package(self.CIK, filing)
        report = DownloadBatch(self.workflow()).run(["ZZZP"], PeriodSelection("2026-07-01"))
        company = report["companies"][0]
        self.assertEqual(company["target_periods"], ["2026-08-31", "2026-11-30"])
        self.assertEqual(company["dependency_periods"], ["2026-05-31"])
        self.assertIn(self.prior["accessionNumber"], JsonCodec.read(self.data / "pipeline/ZZZP/packages.json")["packages"])
        self.assertEqual(report["succeeded"], ["ZZZP"])

    def test_dry_run_lists_missing_prior_10k(self):
        self.submissions(self.CIK, [self.prior, self.q1, self.q2])
        for filing in (self.prior, self.q1, self.q2):
            self.package(self.CIK, filing)
        self.workflow().run(["ZZZP"], PeriodSelection("2026-07-01"))
        packages_path = self.data / "pipeline/ZZZP/packages.json"
        saved = JsonCodec.read(packages_path)
        del saved["packages"][self.prior["accessionNumber"]]
        JsonCodec.write(packages_path, saved)
        offline_http = FakeHttp()
        report = DownloadWorkflow(ROOT, self.data, offline_http, tickers_csv=self.csv).run(
            ["ZZZP"], PeriodSelection("2026-07-01"), dry_run=True
        )
        company = report["companies"][0]
        self.assertEqual(offline_http.requests, [])
        self.assertEqual(
            [(m["accession"], m["state"]) for m in company["missing_dependencies"]],
            [(self.prior["accessionNumber"], "not_downloaded")],
        )
        self.assertFalse(report["complete"])

    def test_prior_10k_outside_recent_page_reloads_full_history(self):
        url = f"https://data.sec.gov/submissions/CIK{int(self.CIK):010d}.json"
        keys = ["accessionNumber", "reportDate", "filingDate", "form", "primaryDocument", "items"]
        page = f"CIK{int(self.CIK):010d}-submissions-001.json"
        recent = {k: [f[k] for f in (self.q1, self.q2)] for k in keys}
        self.http.responses[url] = json.dumps({"filings": {"recent": recent, "files": [{"name": page}]}}).encode()
        self.http.responses["https://data.sec.gov/submissions/" + page] = json.dumps({k: [self.prior[k]] for k in keys}).encode()
        for filing in (self.prior, self.q1, self.q2):
            self.package(self.CIK, filing)
        company = self.workflow().run(["ZZZP"], PeriodSelection("2026-08-01"))["companies"][0]
        self.assertIn("https://data.sec.gov/submissions/" + page, self.http.requests)
        self.assertEqual(company["dependency_periods"], ["2026-05-31"])
        self.assertNotIn("prior_annual_unresolved", company)

    def recent_only(self, filings):
        """recent 分頁只含 `filings`，另有一個測試沒提供的歷史分頁：catalog 不含全部歷史。"""
        url = f"https://data.sec.gov/submissions/CIK{int(self.CIK):010d}.json"
        keys = ["accessionNumber", "reportDate", "filingDate", "form", "primaryDocument", "items"]
        page = f"CIK{int(self.CIK):010d}-submissions-001.json"
        columns = {k: [f[k] for f in filings] for k in keys}
        self.http.responses[url] = json.dumps({"filings": {"recent": columns, "files": [{"name": page}]}}).encode()
        return "https://data.sec.gov/submissions/" + page

    def test_latest_without_prior_10k_does_not_reload_history(self):
        page = self.recent_only([self.q1, self.q2])
        self.package(self.CIK, self.q2)
        company = self.workflow().run(["ZZZP"], PeriodSelection())["companies"][0]
        self.assertNotIn(page, self.http.requests)
        self.assertEqual(company["target_periods"], ["2026-11-30"])
        self.assertEqual(company["prior_annual_unresolved"], ["10-Q 2026-11-30 的上一份 10-K 不在 SEC catalog 中"])

    def test_dry_run_range_without_prior_10k_is_catalog_incomplete(self):
        self.recent_only([self.q1, self.q2])
        self.package(self.CIK, self.q2)
        self.workflow().run(["ZZZP"], PeriodSelection())
        offline_http = FakeHttp()
        report = DownloadWorkflow(ROOT, self.data, offline_http, tickers_csv=self.csv).run(
            ["ZZZP"], PeriodSelection("2026-11-01"), dry_run=True
        )
        company = report["companies"][0]
        self.assertEqual(offline_http.requests, [])
        self.assertEqual(company["catalog_incomplete"], ["10-Q 2026-11-30 的上一份 10-K 不在 SEC catalog 中"])
        self.assertEqual(company["prior_annual_unresolved"], ["10-Q 2026-11-30 的上一份 10-K 不在 SEC catalog 中"])
        self.assertFalse(report["complete"])

    def test_10q_without_any_prior_10k_is_reported_without_failing(self):
        # 例如上市後的第一批 10-Q：SEC 沒有更早的 10-K。
        self.submissions(self.CIK, [self.q1, self.q2])
        for filing in (self.q1, self.q2):
            self.package(self.CIK, filing)
        report = DownloadBatch(self.workflow()).run(["ZZZP"], PeriodSelection("2026-07-01"))
        company = report["companies"][0]
        self.assertEqual(company["dependency_periods"], [])
        self.assertEqual(
            company["prior_annual_unresolved"],
            ["10-Q 2026-08-31 的上一份 10-K 不在 SEC catalog 中", "10-Q 2026-11-30 的上一份 10-K 不在 SEC catalog 中"],
        )
        self.assertEqual(report["succeeded"], ["ZZZP"])


class ManifestRestoreTests(SecFixture):
    """依申報清單重新下載申報包並逐檔核對 sha256。"""

    CIK = "999005"

    def setUp(self):
        super().setUp()
        self.company_tickers({"ZZZM": self.CIK})
        self.q = self.filing(self.CIK, "2027-03-31")
        self.submissions(self.CIK, [self.q])
        self.base = self.package(self.CIK, self.q)
        self.workflow(include_r_pages=True).run(["ZZZM"], PeriodSelection())
        packages = JsonCodec.read(self.data / "pipeline/ZZZM/packages.json")["packages"]
        self.manifests = Path(self.temp.name) / "snapshots"
        self.entries = [
            {"filing": p["filing"], "documents": {n: {"sha256": d["sha256"], "bytes": d["bytes"]} for n, d in p["documents"].items()}}
            for p in packages.values()
        ]
        self.write_manifest()
        self.fresh = Path(self.temp.name) / "fresh"

    def write_manifest(self):
        JsonCodec.write(self.manifests / "Z/ZZZM/manifest.json", {"ticker": "ZZZM", "filings": self.entries})

    def restore(self):
        workflow = DownloadWorkflow(ROOT, self.fresh, self.http, tickers_csv=self.csv, manifests=self.manifests)
        return DownloadBatch(workflow).run(["ZZZM"], PeriodSelection())

    def saved(self):
        return JsonCodec.read(self.fresh / "pipeline/ZZZM/packages.json")["packages"][self.q["accessionNumber"]]

    def test_restores_listed_packages_without_catalog(self):
        before = len(self.http.requests)
        report = self.restore()
        self.assertEqual(report["succeeded"], ["ZZZM"])
        self.assertEqual(report["companies"][0]["manifest_mismatches"], [])
        requested = self.http.requests[before:]
        self.assertFalse(any("submissions" in url or "company_tickers" in url for url in requested), requested)
        self.assertTrue(self.saved()["complete"])

    def test_listed_r_pages_are_downloaded(self):
        self.assertIn("R1.htm", self.entries[0]["documents"])
        self.restore()
        self.assertIn("R1.htm", self.saved()["documents"])

    def test_changed_file_marks_package_incomplete_until_redownloaded(self):
        good = self.http.responses[self.base + "doc.xsd"]
        self.http.responses[self.base + "doc.xsd"] = b"<schema changed/>"
        report = self.restore()
        self.assertEqual(report["succeeded"], [])
        self.assertIn("doc.xsd：sha256 與申報清單不同", report["failed"][0]["error"])
        saved = self.saved()
        self.assertFalse(saved["complete"])
        self.assertNotIn("doc.xsd", saved["documents"])
        self.assertIn("doc.xsd", saved["failures"])
        self.http.responses[self.base + "doc.xsd"] = good
        self.assertEqual(self.restore()["succeeded"], ["ZZZM"])
        self.assertTrue(self.saved()["complete"])

    def test_listed_file_missing_from_package_fails(self):
        self.entries[0]["documents"]["gone.htm"] = {"sha256": "0" * 64, "bytes": 1}
        self.write_manifest()
        report = self.restore()
        self.assertIn("gone.htm：申報清單列出、申報包沒有這個檔案", report["failed"][0]["error"])
        self.assertFalse(self.saved()["complete"])

    def test_unlisted_file_is_reported_without_failing(self):
        del self.entries[0]["documents"]["g1.jpg"]
        self.write_manifest()
        report = self.restore()
        self.assertEqual(report["succeeded"], ["ZZZM"])
        self.assertEqual(report["companies"][0]["manifest_extra"], [f"{self.q['accessionNumber']} g1.jpg"])

if __name__ == "__main__":
    unittest.main()
