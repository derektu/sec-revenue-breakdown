"""分階段流程測試；HTTP 注入 fixture，不把 synthetic HTML 宣稱 SEC 原文。"""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from html import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT / "scripts"))
from sec_revenue.engines import JsonCodec, QuarterEngine, XbrlEngine
from sec_revenue.service import ParserRegistry
from sec_revenue.workflow import (
    SupportedTickers,
    PeriodSelection,
    WorkflowCache,
    DownloadWorkflow,
    ExtractionWorkflow,
    SecHttpClient,
    NoRedirect,
)
from sec_revenue.viewer import RevenueViewer
from check_engine_regression import RegressionCheck


class FixtureHttp:
    """明確的測試 transport；不發出真實網路請求。"""

    def __init__(self, documents):
        self.documents = documents
        self.requests = []

    def get(self, url, kind):
        self.requests.append((url, kind))
        value = self.documents[url]
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.registry = ParserRegistry()

    def tearDown(self):
        self.temp.cleanup()

    def filing(self, ticker="AAPL", period="2027-03-31", form="10-Q", sequence=1):
        cik = self.registry.entries[ticker]["submission_ciks"][0]
        accession = f"{int(cik):010d}-27-{sequence:06d}"
        return {
            "cik": cik,
            "accessionNumber": accession,
            "reportDate": period,
            "filingDate": "2027-05-01",
            "form": form,
            "original_form": form,
            "primaryDocument": "fixture-" + period.replace("-", "") + ".htm",
        }

    def catalog_url(self, ticker):
        return (
            "https://data.sec.gov/submissions/CIK"
            + self.registry.entries[ticker]["submission_ciks"][0].zfill(10)
            + ".json"
        )

    def document_url(self, filing, name=None):
        return f"https://www.sec.gov/Archives/edgar/data/{int(filing['cik'])}/{filing['accessionNumber'].replace('-','')}/{name or filing['primaryDocument']}"

    def submission(self, filings, pages=None):
        columns = {
            key: [
                f.get("original_form", f["form"]) if key == "form" else f[key]
                for f in filings
            ]
            for key in [
                "accessionNumber",
                "reportDate",
                "filingDate",
                "form",
                "primaryDocument",
            ]
        }
        return JsonCodec.encode({"filings": {"recent": columns, "files": pages or []}})

    def html(self, ticker="AAPL", start="2027-01-01", end="2027-03-31", value=100):
        """只有此測試產生 synthetic inline bytes；數值明確報告而非缺值補零。"""
        parser = self.registry.create(ticker)
        terms = {}
        for rules in parser.rules.values():
            for rule in rules.values():
                for expression in rule["alternatives"]:
                    for term in expression:
                        key = json.dumps(
                            {k: term[k] for k in ["concept", "dimensions", "unit"]},
                            sort_keys=True,
                        )
                        terms[key] = term
        if ticker == "XOM":
            dims = [
                {},
                {"srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember"},
                {"srt:ConsolidationItemsAxis": "us-gaap:IntersegmentEliminationMember"},
            ]
            dims += [
                {"srt:ProductOrServiceAxis": "xom:" + member}
                for member in [
                    "SalesAndOtherOperatingRevenueMember",
                    "IncomeFromEquityAffiliatesMember",
                    "OtherRevenueMember",
                ]
            ]
            dims += [
                {
                    "us-gaap:StatementBusinessSegmentsAxis": "xom:" + member,
                    "srt:StatementGeographicalAxis": geo,
                }
                for member in [
                    "UpstreamMember",
                    "EnergyProductsMember",
                    "ChemicalProductsMember",
                    "SpecialtyProductsMember",
                ]
                for geo in ["country:US", "us-gaap:NonUsMember"]
            ]
            for d in dims:
                terms[json.dumps(d, sort_keys=True)] = {
                    "concept": "us-gaap:Revenues",
                    "dimensions": d,
                    "unit": "iso4217:USD",
                }
        pieces = [
            '<html><body><p>Explicit synthetic test fixture, not SEC downloaded original</p><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        ]
        for i, term in enumerate(terms.values()):
            dimensions = "".join(
                f'<xbrldi:explicitMember dimension="{escape(axis)}">{escape(member)}</xbrldi:explicitMember>'
                for axis, member in term["dimensions"].items()
            )
            pieces.append(
                f'<xbrli:context id="c{i}"><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period><xbrli:scenario>{dimensions}</xbrli:scenario></xbrli:context><ix:nonFraction name="{term["concept"]}" unitRef="usd" contextRef="c{i}" decimals="0">{value}</ix:nonFraction>'
            )
        pieces.append("</body></html>")
        return "".join(pieces).encode()

    def simple(self, filings=None, body=None):
        filings = filings or [self.filing()]
        documents = {self.catalog_url("AAPL"): self.submission(filings)}
        for filing in filings:
            documents[self.document_url(filing)] = body or self.html(
                end=filing["reportDate"]
            )
        http = FixtureHttp(documents)
        return DownloadWorkflow(ROOT, self.data, http), http


class WorkflowTests(WorkflowFixture):
    def test_supported_lists_files_and_unknown_fail(self):
        roster = SupportedTickers()
        self.assertEqual(len(roster.select()), 30)
        text = self.data / "tickers.txt"
        text.write_text("AAPL,MSFT\n# supported\nAAPL\n")
        self.assertEqual(roster.select(file=text), ["AAPL", "MSFT"])
        target = self.data / "tickers.json"
        target.write_text('["aapl","MSFT"]')
        self.assertEqual(roster.select(file=target), ["AAPL", "MSFT"])
        with self.assertRaises(ValueError):
            roster.select(["../AAPL"])

    def test_date_range_inclusive_and_latest(self):
        a = self.filing(period="2026-03-31")
        b = self.filing(period="2026-06-30", sequence=2)
        self.assertEqual(PeriodSelection().choose([a, b]), [b])
        self.assertEqual(
            PeriodSelection("2026-03-31", "2026-06-30").choose([a, b]), [a, b]
        )
        self.assertEqual(
            PeriodSelection("2026-06-30", "2026-06-30").choose([a, b]), [b]
        )
        with self.assertRaises(ValueError):
            PeriodSelection("2026-06-30", "2026-03-31")

    def test_download_cache_and_force_preserve_bytes_without_extract(self):
        workflow, http = self.simple()
        first = workflow.run(["AAPL"], PeriodSelection())
        self.assertEqual(first["companies"][0]["filings"][0]["status"], "downloaded")
        self.assertFalse((self.data / "outputs").exists())
        workflow.run(["AAPL"], PeriodSelection())
        self.assertEqual(len(http.requests), 2)
        url = self.document_url(self.filing())
        http.documents[url] = self.html(value=200)
        workflow.run(["AAPL"], PeriodSelection(), force=True)
        self.assertEqual(len(http.requests), 4)
        bodies = list((self.data / "sec" / "AAPL").rglob("*.html"))
        self.assertEqual(len(bodies), 2)
        self.assertEqual(
            {p.read_bytes() for p in bodies}, {self.html(), self.html(value=200)}
        )

    def test_latest_refresh_discovers_new_period(self):
        a = self.filing(period="2027-03-31")
        b = self.filing(period="2027-06-30", sequence=2)
        workflow, http = self.simple([a])
        workflow.run(["AAPL"], PeriodSelection())
        http.documents[self.catalog_url("AAPL")] = self.submission([a, b])
        http.documents[self.document_url(b)] = self.html(
            start="2027-04-01", end="2027-06-30"
        )
        result = workflow.run(["AAPL"], PeriodSelection(latest=True))
        self.assertEqual(result["companies"][0]["target_periods"], ["2027-06-30"])
        extracted = ExtractionWorkflow(ROOT, self.data).run(
            ["AAPL"], PeriodSelection(latest=True)
        )
        self.assertTrue(extracted["complete"])
        self.assertEqual(
            extracted["companies"][0]["periods"][0]["period_end"], "2027-06-30"
        )

    def test_annual_downloads_ytd9_dependency_then_extracts_q4(self):
        annual = self.filing(period="2026-09-26", form="10-K", sequence=2)
        annual["filingDate"] = "2026-11-01"
        nine = self.filing(period="2026-06-27")
        nine["filingDate"] = "2026-08-01"
        workflow, http = self.simple([nine, annual])
        http.documents[self.document_url(annual)] = self.html(
            start="2025-09-28", end="2026-09-26", value=100
        )
        http.documents[self.document_url(nine)] = self.html(
            start="2025-09-28", end="2026-06-27", value=60
        )
        result = workflow.run(["AAPL"], PeriodSelection("2026-09-26", "2026-09-26"))
        self.assertEqual(
            sum(f["dependency"] for f in result["companies"][0]["filings"]), 1
        )
        extracted = ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())
        self.assertTrue(extracted["complete"])
        row = JsonCodec.read(
            self.data / "outputs/AAPL/2026-09-26/AAPL_2026-09-26_reported_revenue.json"
        )
        self.assertEqual({o["value_usd"] for o in row["outputs"].values()}, {40})
        self.assertEqual(
            row["outputs"]["iPhone"]["SEC_operands"][0]["nine_month_evidence"][
                "enddate"
            ],
            "2026-06-27",
        )

    def test_extract_cache_skip_force_and_changed_raw_invalidates(self):
        workflow, http = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        extraction = ExtractionWorkflow(ROOT, self.data)
        first = extraction.run(["AAPL"], PeriodSelection())
        self.assertTrue(first["complete"])
        output = (
            self.data / "outputs/AAPL/2027-03-31/AAPL_2027-03-31_reported_revenue.json"
        )
        before = output.stat().st_mtime_ns
        hit = extraction.run(["AAPL"], PeriodSelection())
        self.assertEqual(hit["companies"][0]["periods"][0]["status"], "cache_hit")
        self.assertEqual(output.stat().st_mtime_ns, before)
        forced = extraction.run(["AAPL"], PeriodSelection(), force=True)
        self.assertEqual(forced["companies"][0]["periods"][0]["status"], "complete")
        old_fingerprint = JsonCodec.read(output)["input_fingerprint"]
        http.documents[self.document_url(self.filing())] = self.html(value=200)
        workflow.run(["AAPL"], PeriodSelection(), force=True)
        updated = extraction.run(["AAPL"], PeriodSelection())
        self.assertEqual(updated["companies"][0]["periods"][0]["status"], "complete")
        row = JsonCodec.read(output)
        self.assertNotEqual(row["input_fingerprint"], old_fingerprint)
        self.assertEqual(row["outputs"]["iPhone"]["value_usd"], 200)
        self.assertEqual(len(list(output.parent.glob("versions/*/*revenue.json"))), 2)

    def test_extract_never_calls_network(self):
        workflow, _ = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        with patch(
            "sec_revenue.workflow.SecHttpClient.get",
            side_effect=AssertionError("network forbidden"),
        ):
            self.assertTrue(
                ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())[
                    "complete"
                ]
            )

    def test_missing_or_invalid_raw_cannot_fall_back_to_research(self):
        workflow, http = self.simple(body=b"<html><p>no revenue data</p></html>")
        workflow.run(["AAPL"], PeriodSelection())
        result = ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())
        self.assertFalse(result["complete"])
        row = JsonCodec.read(
            self.data / "outputs/AAPL/2027-03-31/AAPL_2027-03-31_reported_revenue.json"
        )
        self.assertIsNone(row["outputs"]["Revenue"]["value_usd"])
        self.assertEqual(row["risk"]["level"], "high")

    def test_cache_corruption_refuses_without_network(self):
        workflow, http = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        receipt = next(
            iter(workflow.cache.read("AAPL", "downloads")["filings"].values())
        )["documents"]["primary"]
        (self.data / receipt["path"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash"):
            workflow.run(["AAPL"], PeriodSelection())
        with self.assertRaisesRegex(ValueError, "hash"):
            ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())
        self.assertEqual(len(http.requests), 2)

    def test_offline_cache_and_force_conflict(self):
        workflow, http = self.simple()
        with self.assertRaises(ValueError):
            workflow.run(["AAPL"], PeriodSelection(), offline=True)
        self.assertEqual(http.requests, [])
        workflow.run(["AAPL"], PeriodSelection())
        result = workflow.run(["AAPL"], PeriodSelection(latest=True), offline=True)
        self.assertEqual(result["companies"][0]["filings"][0]["status"], "cache_hit")
        self.assertEqual(len(http.requests), 2)
        with self.assertRaises(ValueError):
            workflow.run(["AAPL"], PeriodSelection(), force=True, offline=True)

    def test_http_403_stops_without_other_tickers_or_retry(self):
        http = FixtureHttp(
            {self.catalog_url("AAPL"): HTTPError("url", 403, "Forbidden", {}, None)}
        )
        with self.assertRaises(HTTPError):
            DownloadWorkflow(ROOT, self.data, http).run(
                ["AAPL", "MSFT"], PeriodSelection()
            )
        self.assertEqual(len(http.requests), 1)

    def test_history_pages_are_loaded_for_older_range(self):
        recent = self.filing(period="2027-03-31")
        old = self.filing(period="2024-03-31", sequence=9)
        page = "CIK0000320193-submissions-001.json"
        workflow, http = self.simple([recent])
        http.documents[self.catalog_url("AAPL")] = self.submission(
            [recent], [{"name": page}]
        )
        old_columns = json.loads(self.submission([old]))["filings"]["recent"]
        http.documents["https://data.sec.gov/submissions/" + page] = JsonCodec.encode(
            old_columns
        )
        http.documents[self.document_url(old)] = self.html(
            start="2024-01-01", end="2024-03-31"
        )
        result = workflow.run(["AAPL"], PeriodSelection("2024-01-01", "2024-06-30"))
        self.assertEqual(result["companies"][0]["target_periods"], ["2024-03-31"])
        self.assertTrue(any(page in url for url, _ in http.requests))

    def test_rule_cache_invalidates_only_changed_issuer(self):
        workflow = ExtractionWorkflow(ROOT, self.data)
        a = workflow.rule_fingerprint("AAPL")
        m = workflow.rule_fingerprint("MSFT")
        original = Path.read_bytes

        def changed(path):
            raw = original(path)
            return (
                raw + b"\n# synthetic rule revision\n"
                if path.name == "aapl.py"
                else raw
            )

        with patch.object(Path, "read_bytes", changed):
            self.assertNotEqual(workflow.rule_fingerprint("AAPL"), a)
            self.assertEqual(workflow.rule_fingerprint("MSFT"), m)

    def test_amendment_latest_accession_does_not_duplicate_outputs(self):
        old = self.filing()
        new = self.filing(sequence=2, form="10-Q/A")
        new["filingDate"] = "2027-05-02"
        workflow, http = self.simple([old])
        workflow.run(["AAPL"], PeriodSelection())
        http.documents[self.catalog_url("AAPL")] = self.submission([old, new])
        http.documents[self.document_url(new)] = self.html(value=300)
        workflow.run(["AAPL"], PeriodSelection(latest=True))
        result = ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())
        self.assertTrue(result["complete"])
        index = JsonCodec.read(self.data / "outputs/AAPL/index.json")
        self.assertEqual(len(index["paths"]), 1)
        row = JsonCodec.read(self.data / "outputs/AAPL" / index["paths"][0])
        self.assertEqual(row["outputs"]["iPhone"]["value_usd"], 300)
        self.assertEqual(
            row["outputs"]["iPhone"]["SEC_operands"][0]["accession"],
            new["accessionNumber"],
        )

    def test_viewer_keeps_previous_period_after_partial_extract(self):
        a = self.filing()
        b = self.filing(period="2027-06-30", sequence=2)
        workflow, http = self.simple([a, b])
        http.documents[self.document_url(b)] = self.html(
            start="2027-04-01", end="2027-06-30"
        )
        workflow.run(["AAPL"], PeriodSelection("2027-01-01", "2027-06-30"))
        extraction = ExtractionWorkflow(ROOT, self.data)
        extraction.run(["AAPL"], PeriodSelection("2027-03-31", "2027-03-31"))
        extraction.run(["AAPL"], PeriodSelection("2027-06-30", "2027-06-30"))
        viewer = RevenueViewer(self.data)
        self.assertEqual(
            len(json.loads(viewer.request("/api/revenue?ticker=AAPL")[2])), 2
        )
        self.assertEqual(
            viewer.request("/api/revenue?ticker=AAPL&period=2027-03-31")[0], 200
        )

    def test_q4_does_not_bridge_cik(self):
        annual = {
            "concept": "us-gaap:Revenues",
            "dimensions": {},
            "unit": "iso4217:USD",
            "startdate": "2025-01-01",
            "enddate": "2025-12-31",
            "value": 100,
            "source_cik": "1",
        }
        nine = dict(annual, enddate="2025-09-30", value=70, source_cik="2")
        self.assertEqual(QuarterEngine().quarter([annual], "2025-12-31", [nine])[0], [])

    def test_sec_identity_and_url_are_required_only_on_network(self):
        with self.assertRaisesRegex(ValueError, "SEC_USER_AGENT"):
            SecHttpClient("").get(
                "https://data.sec.gov/submissions/CIK0000320193.json", "json"
            )
        with self.assertRaisesRegex(ValueError, "SEC HTTPS"):
            SecHttpClient("Research user@test.invalid").get(
                "https://other.test/a", "html"
            )

    def test_pgr_missing_consolidated_exhibit_refuses_parent_only(self):
        filing = self.filing("PGR", "2025-12-31", "10-K")
        parser = self.registry.create("PGR")
        with self.assertRaisesRegex(ValueError, "Exhibit 13"):
            parser.document_names(filing, [filing["primaryDocument"]])
        selected = parser.document_names(
            filing, [filing["primaryDocument"], "pgr-20251231_d2.htm"]
        )
        self.assertEqual(selected["consolidated"], "pgr-20251231_d2.htm")

    def test_8k_period_is_actual_quarter_not_event_date(self):
        filing = self.filing("UPS", "2026-10-27", "8-K")
        filing["accessionNumber"] = "0001628280-26-067381"
        selected = self.registry.create("UPS").catalog_filings([filing])[0]
        self.assertEqual(selected["reportDate"], "2026-09-30")
        self.assertEqual(selected["event_report_date"], "2026-10-27")

    def test_refresh_keeps_downloaded_history_for_offline_use(self):
        old = self.filing(period="2024-03-31")
        new = self.filing(period="2027-03-31", sequence=2)
        workflow, http = self.simple([old])
        http.documents[self.document_url(old)] = self.html(
            start="2024-01-01", end="2024-03-31"
        )
        workflow.run(["AAPL"], PeriodSelection("2024-01-01", "2024-06-30"))
        http.documents[self.catalog_url("AAPL")] = self.submission([new])
        http.documents[self.document_url(new)] = self.html()
        workflow.run(["AAPL"], PeriodSelection(latest=True))
        before = len(http.requests)
        cached = workflow.run(
            ["AAPL"], PeriodSelection("2024-01-01", "2024-06-30"), offline=True
        )
        self.assertEqual(cached["companies"][0]["target_periods"], ["2024-03-31"])
        self.assertEqual(len(http.requests), before)

    def test_missing_output_is_reextracted_and_index_is_repaired(self):
        workflow, _ = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        extractor = ExtractionWorkflow(ROOT, self.data)
        extractor.run(["AAPL"], PeriodSelection())
        index = self.data / "outputs/AAPL/index.json"
        output = (
            self.data / "outputs/AAPL/2027-03-31/AAPL_2027-03-31_reported_revenue.json"
        )
        index.unlink()
        extractor.run(["AAPL"], PeriodSelection())
        self.assertTrue(index.exists())
        output.unlink()
        result = extractor.run(["AAPL"], PeriodSelection())
        self.assertEqual(result["companies"][0]["periods"][0]["status"], "complete")

    def test_extraction_cannot_read_research_sources(self):
        workflow, _ = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        original = Path.read_bytes

        def guarded(path):
            if "research" in path.parts:
                raise AssertionError("research input forbidden")
            return original(path)

        with patch.object(Path, "read_bytes", guarded):
            self.assertTrue(
                ExtractionWorkflow(ROOT, self.data).run(["AAPL"], PeriodSelection())[
                    "complete"
                ]
            )

    def test_pgr_interrupted_force_never_mixes_old_consolidated_document(self):
        ticker = "PGR"
        filing = self.filing(ticker, "2025-12-31", "10-K")
        # 只測下載 bundle 一致性，兩份 HTML 明確為 synthetic，不作數值證據。
        main = self.document_url(filing)
        extra = self.document_url(filing, "pgr-20251231_d2.htm")
        index = main.rsplit("/", 1)[0] + "/index.json"
        documents = {
            self.catalog_url(ticker): self.submission([filing]),
            index: JsonCodec.encode(
                {
                    "directory": {
                        "item": [
                            {"name": filing["primaryDocument"]},
                            {"name": "pgr-20251231_d2.htm"},
                        ]
                    }
                }
            ),
            main: b"<html>old primary fixture</html>",
            extra: b"<html>old consolidated fixture</html>",
        }
        http = FixtureHttp(documents)
        workflow = DownloadWorkflow(ROOT, self.data, http)
        workflow.run([ticker], PeriodSelection())
        documents[main] = b"<html>new primary fixture</html>"
        documents[extra] = HTTPError(extra, 403, "Forbidden", {}, None)
        with self.assertRaises(HTTPError):
            workflow.run([ticker], PeriodSelection(), force=True)
        with self.assertRaisesRegex(ValueError, "下載未完成"):
            ExtractionWorkflow(ROOT, self.data).run([ticker], PeriodSelection())
        saved = workflow.cache.read(ticker, "downloads")["filings"][
            filing["accessionNumber"]
        ]
        self.assertFalse(saved["download_complete"])
        self.assertNotIn("consolidated", saved["documents"])
        documents[extra] = b"<html>new consolidated fixture</html>"
        before = sum(url == main for url, _ in http.requests)
        workflow.run([ticker], PeriodSelection())
        self.assertEqual(sum(url == main for url, _ in http.requests), before)

    def test_comcast_q1_q2_header_spans_from_explicit_dom_fixture(self):
        from sec_revenue.parsers.cmcsa_tables import RevenueTables

        reader = RevenueTables(ROOT, self.data)
        for quarter, month in [("Q1", 3), ("Q2", 6)]:
            snapshot = JsonCodec.read(
                ROOT / f"research/sec-dom-sources-20261104/CMCSA-2026{quarter}.json"
            )
            pieces = [
                "<html><p>Synthetic HTML made from saved DOM fixture; not original bytes</p>"
            ]
            for table in snapshot["tables"]:
                pieces.append("<table>")
                for _, cells in table["rows"]:
                    pieces.append("<tr>")
                    cursor = 0
                    for start, span, text in cells:
                        if start > cursor:
                            pieces.append(f'<td colspan="{start-cursor}"></td>')
                        pieces.append(f'<td colspan="{span}">{escape(text)}</td>')
                        cursor = start + span
                    pieces.append("</tr>")
                pieces.append("</table>")
            pieces.append("</html>")
            result = reader.parse_groups("".join(pieces).encode(), "10-Q", 2026, month)
            self.assertEqual(len(result), 4 if month == 3 else 8)
            expected = 19962000000 if month == 3 else 19795000000
            self.assertEqual(result["Q", 2026, "Connectivity and Platforms"], expected)

    def test_reviewed_cat_and_ups_8k_html_adapters_use_downloaded_bytes(self):
        for ticker, accession in [
            ("CAT", "0000018230-26-000052"),
            ("UPS", "0001628280-26-067381"),
        ]:
            filing = self.filing(ticker, "2026-10-27", "8-K")
            filing["accessionNumber"] = accession
            parser = self.registry.create(ticker)
            filing = parser.catalog_filings([filing])[0]
            if ticker == "CAT":
                snapshot = JsonCodec.read(
                    ROOT / "research/sec-dom-sources-20261104/CAT-2026Q3.json"
                )
                pieces = [
                    "<html><p>Synthetic layout fixture from public SEC DOM; not original HTML</p>"
                ]
                for table in snapshot["tables"]:
                    pieces.append("<table>")
                    for row in table["rows"]:
                        pieces.append(
                            "<tr>"
                            + "".join("<td>" + escape(cell) + "</td>" for cell in row)
                            + "</tr>"
                        )
                    pieces.append("</table>")
                pieces.append("</html>")
                raw = "".join(pieces).encode()
            else:
                pieces = [
                    "<html><p>Synthetic layout fixture, not original HTML. Exhibit 99.1 UPS RELEASES 3Q 2026 EARNINGS</p>"
                ]
                for label, heading in [
                    ("Domestic Package", "U.S. Domestic Segment"),
                    ("International Package", "International Segment"),
                    ("Supply Chain and Freight", "Supply Chain Solutions1"),
                ]:
                    pieces.append(
                        f"<h2>{heading}</h2><table><tr><td>3Q 2026</td><td>Non-GAAP Adjusted 3Q 2026</td><td>3Q 2025</td></tr><tr><td>Revenue</td><td>$1,000 M</td><td></td><td>$900 M</td></tr></table>"
                    )
                pieces.append("</html>")
                raw = "".join(pieces).encode()
            url = self.document_url(filing)
            receipt = {"source_url": url, "sha256": hashlib.sha256(raw).hexdigest()}
            record = parser.extract_document(filing, {"primary": (raw, receipt)})
            rows = parser.parse_downloaded([record], ["2026-09-30"])
            self.assertEqual(len(rows), 1)
            self.assertTrue(
                all(o["status"] == "observed" for o in rows[0]["outputs"].values())
            )
            self.assertTrue(
                all(
                    f["source_format"] == "original_html"
                    for o in rows[0]["outputs"].values()
                    for f in o["SEC_operands"]
                )
            )

    def test_empty_ticker_file_and_non_iso_date_are_rejected(self):
        path = self.data / "empty.txt"
        path.write_text("# no tickers\n")
        with self.assertRaises(ValueError):
            SupportedTickers().select(file=path)
        with self.assertRaises(ValueError):
            PeriodSelection("20260331")
        self.assertEqual(len(SupportedTickers().select(["ALL", "AAPL"])), 30)

    def test_empty_issuer_rules_are_not_successful_extraction(self):
        workflow, _ = self.simple()
        workflow.run(["AAPL"], PeriodSelection())
        extractor = ExtractionWorkflow(ROOT, self.data)
        parser = self.registry.create("AAPL")
        parser.rules = {"reported": {}}
        with patch.object(extractor.registry, "create", return_value=parser):
            result = extractor.run(["AAPL"], PeriodSelection())
        self.assertFalse(result["complete"])
        row = JsonCodec.read(
            self.data / "outputs/AAPL/2027-03-31/AAPL_2027-03-31_reported_revenue.json"
        )
        self.assertEqual(row["outputs"]["Revenue"]["status"], "issuer_rules_empty")
        self.assertEqual(row["risk"]["level"], "high")

    def test_xbrl_explicit_zero_is_distinct_from_missing_dash(self):
        raw = self.html(value=0).replace(b">0</ix:nonFraction>", b">-</ix:nonFraction>")
        url = self.document_url(self.filing())
        with self.assertRaises(ValueError):
            XbrlEngine().parse_html(raw, url, self.filing()["accessionNumber"])
        explicit = raw.replace(b'decimals="0"', b'decimals="0" format="ixt:fixed-zero"')
        facts = XbrlEngine().parse_html(explicit, url, self.filing()["accessionNumber"])
        self.assertTrue(facts)
        self.assertEqual({f["value"] for f in facts}, {0})
        self.assertTrue(all(f["numeric_transform"] == "fixed-zero" for f in facts))

    def test_unsupported_numeric_transform_refuses_instead_of_misreading(self):
        raw = self.html().replace(
            b'decimals="0"', b'decimals="0" format="ixt:num-comma-decimal"'
        )
        with self.assertRaisesRegex(ValueError, "transform"):
            XbrlEngine().parse_html(
                raw, self.document_url(self.filing()), self.filing()["accessionNumber"]
            )

    def test_live_cvx_net_and_xom_all_income_refuse_inconsistent_totals(self):
        from lxml import html

        for ticker, field in [
            ("CVX", "consolidated_sales"),
            ("XOM", "Total revenues and other income"),
        ]:
            filing = self.filing(ticker)
            root = html.fromstring(self.html(ticker, value=0))
            for node in root.iter():
                if not isinstance(node.tag, str) or not node.tag.endswith(
                    "nonfraction"
                ):
                    continue
                context = root.xpath(f'//*[@id="{node.get("contextref")}"]')[0]
                dims = [
                    n
                    for n in context.iter()
                    if isinstance(n.tag, str) and n.tag.endswith("explicitmember")
                ]
                if not dims:
                    node.text = "999"
            raw = html.tostring(root)
            documents = {
                self.catalog_url(ticker): self.submission([filing]),
                self.document_url(filing): raw,
            }
            for cik in self.registry.entries[ticker]["submission_ciks"][1:]:
                documents[
                    f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
                ] = self.submission([])
            DownloadWorkflow(ROOT, self.data, FixtureHttp(documents)).run(
                [ticker], PeriodSelection()
            )
            result = ExtractionWorkflow(ROOT, self.data).run(
                [ticker], PeriodSelection()
            )
            self.assertFalse(result["complete"])
            basis = self.registry.entries[ticker]["primary_basis"]
            row = JsonCodec.read(
                self.data
                / f"outputs/{ticker}/2027-03-31/{ticker}_2027-03-31_{basis}_revenue.json"
            )
            self.assertIsNone(row["outputs"][field]["value_usd"])
            self.assertEqual(row["risk"]["level"], "high")
            self.assertTrue(
                any(
                    c["status"] == "reconciliation_failed"
                    for c in row["reconciliation_checks"]
                )
            )

    def test_document_period_mismatch_refuses_comparative_as_current(self):
        raw = self.html().replace(
            b"<body>",
            b'<body><ix:nonNumeric name="dei:DocumentPeriodEndDate">2028-03-31</ix:nonNumeric>',
        )
        filing = self.filing()
        receipt = {
            "source_url": self.document_url(filing),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "DocumentPeriodEndDate"):
            self.registry.create("AAPL").extract_document(
                filing, {"primary": (raw, receipt)}
            )

    def test_actual_http_client_403_has_no_retry(self):
        client = SecHttpClient("Synthetic unit-test identity unit@test.invalid")
        url = "https://www.sec.gov/Archives/edgar/data/1/000000000127000001/fixture.htm"
        with patch.object(
            client.opener,
            "open",
            side_effect=HTTPError(url, 403, "Forbidden", {}, None),
        ) as request:
            with self.assertRaises(HTTPError):
                client.get(url, "html")
            self.assertEqual(request.call_count, 1)

    def test_actual_http_client_rejects_encoded_bytes_before_html_cache(self):
        from email.message import Message
        from unittest.mock import MagicMock

        client = SecHttpClient("Synthetic unit-test identity unit@test.invalid")
        url = "https://www.sec.gov/Archives/edgar/data/1/000000000127000001/fixture.htm"
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = url
        response.headers = Message()
        response.headers["Content-Type"] = "text/html"
        response.headers["Content-Encoding"] = "gzip"
        response.read.return_value = b"compressed fixture bytes, not HTML"
        with patch.object(client.opener, "open", return_value=response):
            with self.assertRaisesRegex(ValueError, "編碼"):
                client.get(url, "html")
        response.read.assert_not_called()


class DownloadedHtmlIntegrationTests(WorkflowFixture):
    def test_thirty_supported_issuer_workflow_contract(self):
        documents = {}
        tickers = list(self.registry.entries)
        for ticker in tickers:
            filing = self.filing(ticker)
            if ticker == "PGR":
                entry = JsonCodec.read(
                    ROOT / "research/progressive-sec-html-20261104/manifest.json"
                )["files"][1]
                url = entry["source_url"]
                digits = url.split("/")[-2]
                filing.update(
                    reportDate="2026-03-31",
                    primaryDocument=url.split("/")[-1],
                    accessionNumber=digits[:10]
                    + "-"
                    + digits[10:12]
                    + "-"
                    + digits[12:],
                )
                raw = gzip.decompress((ROOT / entry["path"]).read_bytes())
            elif ticker == "CMCSA":
                entry = next(
                    e
                    for e in JsonCodec.read(
                        ROOT / "research/shared-raw-semantics/manifest.json"
                    )["filings"]
                    if e["ticker"] == ticker and e["form"] == "10-Q"
                )
                filing.update(
                    {
                        k: entry[k]
                        for k in [
                            "reportDate",
                            "filingDate",
                            "accessionNumber",
                            "primaryDocument",
                        ]
                    }
                )
                raw = gzip.decompress((ROOT / entry["path"]).read_bytes())
            else:
                raw = self.html(ticker, value=0)
            documents[self.catalog_url(ticker)] = self.submission([filing])
            for cik in self.registry.entries[ticker]["submission_ciks"][1:]:
                documents[
                    f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
                ] = self.submission([])
            documents[self.document_url(filing)] = raw
        http = FixtureHttp(documents)
        DownloadWorkflow(ROOT, self.data, http).run(tickers, PeriodSelection())
        extraction = ExtractionWorkflow(ROOT, self.data)
        result = extraction.run(tickers, PeriodSelection())
        self.assertTrue(result["complete"], str(result))
        self.assertEqual(len(result["companies"]), 30)
        second = extraction.run(tickers, PeriodSelection())
        self.assertTrue(
            all(
                p["status"] == "cache_hit"
                for c in second["companies"]
                for p in c["periods"]
            )
        )

    def test_thirteen_existing_real_sec_html_inputs(self):
        """13 份真正已保存 HTML；PGR 年報 primary 是明標 fixture，數值只來自真實 Exhibit 13。"""
        documents = {}
        grouped = {}
        expected_count = 0
        manifest = JsonCodec.read(ROOT / "research/shared-raw-semantics/manifest.json")
        for entry in manifest["filings"]:
            ticker = entry["ticker"]
            filing = {
                k: entry[k]
                for k in [
                    "form",
                    "reportDate",
                    "filingDate",
                    "accessionNumber",
                    "primaryDocument",
                ]
            }
            filing.update(
                cik=self.registry.entries[ticker]["submission_ciks"][0],
                original_form=filing["form"],
            )
            grouped.setdefault(ticker, []).append(filing)
            documents[entry["url"]] = gzip.decompress(
                (ROOT / entry["path"]).read_bytes()
            )
        for entry in JsonCodec.read(
            ROOT / "research/progressive-sec-html-20261104/manifest.json"
        )["files"]:
            url = entry["source_url"]
            digits = url.split("/")[-2]
            date = url.split("/")[-1][4:12]
            period = date[:4] + "-" + date[4:6] + "-" + date[6:]
            filing = {
                "cik": "80661",
                "reportDate": period,
                "filingDate": period,
                "form": "10-K" if period.endswith("12-31") else "10-Q",
                "accessionNumber": digits[:10]
                + "-"
                + digits[10:12]
                + "-"
                + digits[12:],
                "primaryDocument": url.split("/")[-1].replace("_d2", ""),
            }
            filing["original_form"] = filing["form"]
            grouped.setdefault("PGR", []).append(filing)
            documents[url] = gzip.decompress((ROOT / entry["path"]).read_bytes())
            if filing["form"] == "10-K":
                documents[self.document_url(filing)] = (
                    b"<html><p>Synthetic test primary index only; no financial values</p></html>"
                )
                documents[
                    self.document_url(filing).rsplit("/", 1)[0] + "/index.json"
                ] = JsonCodec.encode(
                    {
                        "directory": {
                            "item": [
                                {"name": filing["primaryDocument"]},
                                {"name": url.split("/")[-1]},
                            ]
                        }
                    }
                )
        for ticker, filings in grouped.items():
            documents[self.catalog_url(ticker)] = self.submission(filings)
        http = FixtureHttp(documents)
        selection = PeriodSelection("2025-09-30", "2026-09-30")
        DownloadWorkflow(ROOT, self.data, http).run(list(grouped), selection)
        result = ExtractionWorkflow(ROOT, self.data).run(list(grouped), selection)
        self.assertTrue(result["complete"], str(result))
        self.assertEqual(sum(len(c["periods"]) for c in result["companies"]), 13)
        for ticker in grouped:
            for rel in JsonCodec.read(self.data / "outputs" / ticker / "index.json")[
                "paths"
            ]:
                row = JsonCodec.read(self.data / "outputs" / ticker / rel)
                baseline = JsonCodec.read(
                    ROOT
                    / f'research/refactor-baseline-sec-20261104/{ticker}/{row["period_end"]}/{ticker}_{row["period_end"]}_SEC_expected.json.gz'
                )
                for label, expected in baseline["outputs"].items():
                    if label in row["outputs"]:
                        self.assertEqual(
                            row["outputs"][label]["value_usd"],
                            expected["value_usd"],
                            (ticker, row["period_end"], label),
                        )
                        self.assertEqual(
                            RegressionCheck.operand_signature(
                                row["outputs"][label]["SEC_operands"]
                            ),
                            RegressionCheck.operand_signature(expected["SEC_operands"]),
                            (ticker, row["period_end"], label, "operands"),
                        )
                        expected_count += 1
        self.assertEqual(expected_count, 82)
