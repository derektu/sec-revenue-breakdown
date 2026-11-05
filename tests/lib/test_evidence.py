"""SEC 表格證據：以合成 inline XBRL HTML 測試找表、標示、運算式與快取，不連網。"""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.engines import JsonCodec  # noqa: E402
from sec_revenue.evidence import (  # noqa: E402
    EvidenceWorkflow,
    playwright_version,
    TableLocator,
    TableScreenshotter,
    duration_label,
    expression_terms,
)
from sec_revenue.viewer import RevenueViewer  # noqa: E402
from sec_revenue.workflow import PeriodSelection  # noqa: E402

CONCEPT = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


def fact(fid, value, raw, start, end):
    return (
        f'<ix:nonFraction id="{fid}" name="{CONCEPT}" contextRef="c-{fid}" '
        f'unitRef="usd" scale="6" decimals="-6">{raw}</ix:nonFraction>'
    )


TEN_Q = f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><head><title>q</title></head><body>
<table><tr><td>Cover</td></tr></table>
<table>
<tr><td>Nine Months Ended</td><td>June 28, 2025</td></tr>
<tr><td>Mac <a href="https://evil.example/" onclick="steal()">x</a></td>
<td style="background:url(https://evil.example/bg.png);color:#000">{fact("f-2", 0, "24,982", "", "")}</td></tr>
<tr><td>iPad <img src="https://evil.example/i.png"></td><td>{fact("f-4", 0, "21,071", "", "")}</td></tr>
</table>
<script>alert(1)</script>
<p>Footnote {fact("f-9", 0, "5", "", "")}</p>
</body></html>""".encode()

TEN_K = f"""<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><body>
<table><tr><td>2025</td></tr>
<tr><td>Mac</td><td>{fact("f-1", 0, "33,708", "", "")}</td></tr>
<tr><td>iPad</td><td>{fact("f-3", 0, "28,023", "", "")}</td></tr>
</table></body></html>""".encode()

Q_ACC, K_ACC = "0000320193-25-000073", "0000320193-25-000079"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def leaf(accession, fid, value, raw, start, end, table_index, source, form):
    return {
        "accession": accession,
        "concept": CONCEPT,
        "context_id": "c-" + fid,
        "decimals": "-6",
        "dimensions": {},
        "enddate": end,
        "fact_id": fid,
        "filing_date": "2025-08-01" if form == "10-Q" else "2025-10-31",
        "form": form,
        "raw": raw,
        "scale": "6",
        "source_artifact_sha256": sha(source),
        "source_format": "original_html",
        "source_url": f"https://www.sec.gov/Archives/edgar/data/320193/{accession.replace('-', '')}/doc.htm",
        "startdate": start,
        "table_index": table_index,
        "unit": "iso4217:USD",
        "value": value,
    }


def nine(fid, value, raw, table_index=1):
    return leaf(Q_ACC, fid, value, raw, "2024-09-29", "2025-06-28", table_index, TEN_Q, "10-Q")


def annual(fid, value, raw, table_index=0):
    return leaf(K_ACC, fid, value, raw, "2024-09-29", "2025-09-27", table_index, TEN_K, "10-K")


def q4(year, nine_months):
    operand = dict(
        year,
        value=year["value"] - nine_months["value"],
        startdate="2025-06-29",
        derivation="annual_minus_nine_months",
        annual_evidence=year,
        nine_month_evidence=nine_months,
    )
    return operand


def output(operands, value=None, weights=None):
    weights = weights or [1] * len(operands)
    total = sum(w * o["value"] for w, o in zip(weights, operands)) if value is None else value
    return {
        "status": "observed",
        "value_usd": total,
        "SEC_operands": operands,
        "expression_alternatives": [
            {"value_usd": total, "SEC_operands": operands, "weights": weights}
        ],
    }


def fkey(accession, fid):
    source = TEN_Q if accession == Q_ACC else TEN_K
    return f"{accession}:{sha(source)[:12]}#{fid}"


def tkey(accession, index):
    source = TEN_Q if accession == Q_ACC else TEN_K
    return f"{accession}-{sha(source)[:12]}-t{index}"


class FakeScreenshotter:
    """以 lxml 的表格文字模擬瀏覽器結果；可指定失敗的 fact 或錯誤的表格文字。"""

    calls = []
    fail_ids = set()
    wrong_text = False
    launch_error = False

    def __enter__(self):
        if FakeScreenshotter.launch_error:
            raise RuntimeError("no chromium")
        return self

    def __exit__(self, *_):
        pass

    def capture(self, raw, items):
        FakeScreenshotter.calls.append([i["id"] for i in items])
        if FakeScreenshotter.fail_ids & {i["id"] for i in items}:
            raise RuntimeError("playwright exploded")
        locator = TableLocator(raw)
        index = locator.locate(items[0]["id"])[1]
        text = "wrong" if FakeScreenshotter.wrong_text else locator.table_text(index)
        return b"\x89PNG-" + ",".join(i["id"] for i in items).encode(), False, text


class EvidenceFixture(unittest.TestCase):
    period = "2025-09-27"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        FakeScreenshotter.calls = []
        FakeScreenshotter.fail_ids = set()
        FakeScreenshotter.wrong_text = False
        FakeScreenshotter.launch_error = False
        documents = {}
        for accession, raw, name in ((Q_ACC, TEN_Q, "aapl-20250628.htm"), (K_ACC, TEN_K, "aapl-20250927.htm")):
            relative = f"sec/AAPL/x/{accession}/{sha(raw)}.html"
            (self.data / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.data / relative).write_bytes(raw)
            folder = accession.replace("-", "")
            documents[accession] = {
                "documents": {
                    name: {
                        "path": relative,
                        "sha256": sha(raw),
                        "source_url": f"https://www.sec.gov/Archives/edgar/data/320193/{folder}/{name}",
                        "ixviewer_url": f"https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/{folder}/{name}",
                        "filing_index_url": f"https://www.sec.gov/Archives/edgar/data/320193/{folder}/{accession}-index.htm",
                    }
                }
            }
        JsonCodec.write(self.data / "pipeline/AAPL/packages.json", {"packages": documents})

    def tearDown(self):
        self.temp.cleanup()

    def write_outputs(self, outputs: dict, period: str | None = None):
        period = period or self.period
        name = f"AAPL_{period}_reported_revenue.json"
        relative = Path("outputs/AAPL") / period / name
        row = {"ticker": "AAPL", "period_end": period, "basis": "reported", "outputs": outputs}
        JsonCodec.write(self.data / relative, row)
        raw = (self.data / relative).read_bytes()
        path = self.data / "pipeline/AAPL/extractions.json"
        extraction = JsonCodec.read(path) if path.exists() else {"periods": {}}
        extraction["periods"][period] = {
            "status": "complete",
            "outputs": [{"path": str(relative), "sha256": sha(raw), "bytes": len(raw)}],
        }
        JsonCodec.write(path, extraction)
        JsonCodec.write(
            self.data / "outputs/AAPL/index.json",
            {"paths": [f"{p}/AAPL_{p}_reported_revenue.json" for p in sorted(extraction["periods"])]},
        )

    def run_evidence(self, force=False, period=None):
        period = period or self.period
        return EvidenceWorkflow(self.data, screenshotter=FakeScreenshotter).run(
            ["AAPL"], PeriodSelection(period, period), force
        )

    def evidence(self, period=None):
        return JsonCodec.read(self.data / "outputs/AAPL" / (period or self.period) / "evidence/evidence.json")


class EvidenceTest(EvidenceFixture):
    def test_same_table_operands_share_one_file_and_are_all_marked(self):
        self.write_outputs(
            {"Mac": output([nine("f-2", 24982000000, "24,982")]), "iPad": output([nine("f-4", 21071000000, "21,071")])}
        )
        report = self.run_evidence()
        self.assertTrue(report["complete"])
        evidence = self.evidence()
        self.assertEqual(list(evidence["tables"]), [tkey(Q_ACC, 1)])
        self.assertEqual(FakeScreenshotter.calls, [["f-2", "f-4"]])
        table = evidence["tables"][tkey(Q_ACC, 1)]
        page = (self.data / table["html"]["path"]).read_bytes()
        self.assertEqual(sha(page), table["html"]["sha256"])
        self.assertEqual(page.count(b'class="sec-evidence-cell"'), 2)
        self.assertIn(b'data-fact-id="f-2"', page)
        self.assertEqual([evidence["facts"][k]["badge"] for k in sorted(evidence["facts"])], ["①", "②"])
        mac = evidence["facts"][fkey(Q_ACC, "f-2")]
        self.assertEqual(mac["duration"], "9M")
        self.assertTrue(mac["ixviewer_url"].startswith("https://www.sec.gov/ix?doc=/Archives/"))

    def test_q4_expression_lists_annual_and_nine_month_operands(self):
        self.write_outputs({"Mac": output([q4(annual("f-1", 33708000000, "33,708"), nine("f-2", 24982000000, "24,982"))])})
        self.assertTrue(self.run_evidence()["complete"])
        field = self.evidence()["rows"][0]["fields"]["Mac"]
        self.assertEqual(field["status"], "ok")
        self.assertEqual(
            [(t["weight"], t["role"], t["fact"]) for t in field["expressions"][0]["terms"]],
            [(1, "annual", fkey(K_ACC, "f-1")), (-1, "nine_month", fkey(Q_ACC, "f-2"))],
        )
        self.assertEqual(field["expressions"][0]["value_usd"], 8726000000)
        self.assertEqual(set(self.evidence()["tables"]), {tkey(K_ACC, 0), tkey(Q_ACC, 1)})

    def test_sum_mismatch_marks_field_failed(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")], value=1)})
        self.assertFalse(self.run_evidence()["complete"])
        evidence = self.evidence()
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["rows"][0]["fields"]["Mac"]["status"], "failed")
        self.assertIn("運算式總和", evidence["rows"][0]["fields"]["Mac"]["reasons"][0])

    def test_missing_fact_id_fails_without_evidence_files(self):
        self.write_outputs({"Mac": output([nine("f-404", 24982000000, "24,982")])})
        self.assertFalse(self.run_evidence()["complete"])
        evidence = self.evidence()
        self.assertEqual(evidence["facts"][fkey(Q_ACC, "f-404")]["status"], "fact_not_found")
        self.assertEqual(evidence["rows"][0]["fields"]["Mac"]["status"], "failed")
        self.assertEqual(evidence["tables"], {})

    def test_table_index_mismatch_is_not_accepted_as_evidence(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982", table_index=0)])})
        self.run_evidence()
        entry = self.evidence()["facts"][fkey(Q_ACC, "f-2")]
        self.assertEqual(entry["status"], "fact_mismatch")
        self.assertIn("表格 #1", entry["reason"])

    def test_fact_outside_table_is_marked_without_substitute_evidence(self):
        self.write_outputs({"Note": output([nine("f-9", 5000000, "5", table_index=None)])})
        self.assertFalse(self.run_evidence()["complete"])
        evidence = self.evidence()
        self.assertEqual(evidence["status"], "incomplete")
        self.assertEqual(evidence["facts"][fkey(Q_ACC, "f-9")]["status"], "not_in_table")
        self.assertIsNone(evidence["facts"][fkey(Q_ACC, "f-9")]["table"])
        self.assertEqual(evidence["rows"][0]["fields"]["Note"]["status"], "not_in_table")
        self.assertEqual(evidence["tables"], {})

    def test_operand_from_unknown_source_fails(self):
        operand = dict(nine("f-2", 24982000000, "24,982"), source_artifact_sha256="0" * 64)
        self.write_outputs({"Mac": output([operand])})
        self.run_evidence()
        self.assertEqual(self.evidence()["facts"][f"{Q_ACC}:{'0' * 12}#f-2"]["status"], "source_missing")
        self.assertEqual(self.evidence()["rows"][0]["fields"]["Mac"]["status"], "failed")

    def test_unobserved_output_has_no_operands_status(self):
        self.write_outputs({"Revenue": {"status": "parser_scope_missing", "value_usd": None, "SEC_operands": []}})
        self.run_evidence()
        self.assertEqual(self.evidence()["rows"][0]["fields"]["Revenue"]["status"], "no_operands")

    def test_cache_hit_and_invalidation(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        self.assertEqual(self.run_evidence()["companies"][0]["periods"][0]["status"], "cache_hit")
        self.assertEqual(len(FakeScreenshotter.calls), 1)
        png = self.data / self.evidence()["tables"][tkey(Q_ACC, 1)]["png"]["path"]
        png.write_bytes(b"tampered")
        self.assertEqual(self.run_evidence()["companies"][0]["periods"][0]["status"], "complete")
        self.assertEqual(self.run_evidence(force=True)["companies"][0]["periods"][0]["status"], "complete")
        self.assertEqual(len(FakeScreenshotter.calls), 3)
        self.write_outputs({"iPad": output([nine("f-4", 21071000000, "21,071")])})
        self.run_evidence()
        self.assertEqual(len(FakeScreenshotter.calls), 4)

    def test_rebuild_removes_table_files_no_longer_referenced(self):
        self.write_outputs({"Mac": output([q4(annual("f-1", 33708000000, "33,708"), nine("f-2", 24982000000, "24,982"))])})
        self.run_evidence()
        directory = self.data / "outputs/AAPL" / self.period / "evidence"
        self.assertTrue((directory / (tkey(K_ACC, 0) + ".png")).exists())
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        self.assertFalse((directory / (tkey(K_ACC, 0) + ".png")).exists())
        self.assertTrue((directory / (tkey(Q_ACC, 1) + ".png")).exists())

    def test_fact_attributes_must_match_operand(self):
        cases = {
            "context": dict(nine("f-2", 24982000000, "24,982"), context_id="c-other"),
            "raw": dict(nine("f-2", 24982000000, "24,982"), raw="24,983"),
            "value": dict(nine("f-2", 24982000000, "24,982"), value=24983000000),
            "concept": dict(nine("f-2", 24982000000, "24,982"), concept="us-gaap:Revenues"),
        }
        for name, operand in cases.items():
            with self.subTest(name):
                self.write_outputs({"Mac": output([operand])})
                self.run_evidence()
                entry = self.evidence()["facts"][fkey(Q_ACC, "f-2")]
                self.assertEqual(entry["status"], "fact_mismatch")
                self.assertEqual(self.evidence()["rows"][0]["fields"]["Mac"]["status"], "failed")

    def test_missing_source_format_is_not_treated_as_html(self):
        operand = nine("f-2", 24982000000, "24,982")
        del operand["source_format"]
        self.write_outputs({"Mac": output([operand])})
        self.run_evidence()
        entry = self.evidence()["facts"][fkey(Q_ACC, "f-2")]
        self.assertEqual(entry["status"], "source_missing")
        self.assertIn("None", entry["reason"])

    def test_weights_must_match_operand_count(self):
        result = output([nine("f-2", 24982000000, "24,982")])
        result["expression_alternatives"][0]["weights"] = [1, 1]
        self.write_outputs({"Mac": result})
        self.run_evidence()
        field = self.evidence()["rows"][0]["fields"]["Mac"]
        self.assertEqual(field["status"], "failed")
        self.assertIn("權重", field["reasons"][0])

    def test_null_extracted_value_fails_field_but_keeps_reference_expression(self):
        result = output([nine("f-2", 24982000000, "24,982")])
        result["value_usd"] = None
        self.write_outputs({"Mac": result})
        self.run_evidence()
        field = self.evidence()["rows"][0]["fields"]["Mac"]
        self.assertEqual(field["status"], "failed")
        self.assertIn("萃取值為空", field["reasons"][0])
        self.assertEqual(len(field["expressions"]), 1)

    def test_fact_used_by_several_fields_lists_every_label(self):
        self.write_outputs(
            {"Mac": output([nine("f-2", 24982000000, "24,982")]), "Mac again": output([nine("f-2", 24982000000, "24,982")])}
        )
        self.run_evidence()
        self.assertEqual(self.evidence()["facts"][fkey(Q_ACC, "f-2")]["labels"], ["Mac", "Mac again"])
        page = (self.data / self.evidence()["tables"][tkey(Q_ACC, 1)]["html"]["path"]).read_text()
        self.assertIn("Mac、Mac again", page)

    def test_screenshot_failure_marks_only_that_table_and_batch_continues(self):
        self.write_outputs({"Mac": output([q4(annual("f-1", 33708000000, "33,708"), nine("f-2", 24982000000, "24,982"))])})
        self.write_outputs({"iPad": output([nine("f-4", 21071000000, "21,071")])}, "2025-06-28")
        FakeScreenshotter.fail_ids = {"f-1"}
        report = EvidenceWorkflow(self.data, screenshotter=FakeScreenshotter).run(
            ["AAPL"], PeriodSelection("2025-06-01", "2025-09-30")
        )
        statuses = {p["period_end"]: p["status"] for p in report["companies"][0]["periods"]}
        self.assertEqual(statuses, {"2025-06-28": "complete", self.period: "failed"})
        evidence = self.evidence()
        self.assertEqual(evidence["facts"][fkey(K_ACC, "f-1")]["status"], "evidence_failed")
        self.assertIn("playwright exploded", evidence["facts"][fkey(K_ACC, "f-1")]["reason"])
        self.assertEqual(list(evidence["tables"]), [tkey(Q_ACC, 1)])

    def test_browser_table_must_match_parser_table(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        FakeScreenshotter.wrong_text = True
        self.run_evidence()
        entry = self.evidence()["facts"][fkey(Q_ACC, "f-2")]
        self.assertEqual(entry["status"], "evidence_failed")
        self.assertIn("文字不同", entry["reason"])
        self.assertEqual(self.evidence()["tables"], {})

    def test_chromium_launch_failure_fails_periods_without_crashing(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        FakeScreenshotter.launch_error = True
        report = self.run_evidence()
        self.assertFalse(report["complete"])
        self.assertIn("Chromium 無法啟動", self.evidence()["facts"][fkey(Q_ACC, "f-2")]["reason"])

    def test_failed_rebuild_replaces_whole_set_without_mixing_old_files(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        directory = self.data / "outputs/AAPL" / self.period / "evidence"
        old_png = directory / (tkey(Q_ACC, 1) + ".png")
        self.assertTrue(old_png.exists())
        FakeScreenshotter.fail_ids = {"f-2"}
        self.run_evidence(force=True)
        self.assertFalse(old_png.exists())
        self.assertEqual(sorted(p.name for p in directory.iterdir()), ["evidence.json"])
        self.assertEqual(self.evidence()["status"], "failed")
        self.assertEqual(
            [p.name for p in directory.parent.iterdir() if p.name.startswith(".")], []
        )

    def test_unexpected_error_writes_failed_evidence_only(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        workflow = EvidenceWorkflow(self.data, screenshotter=FakeScreenshotter)
        workflow.write_tables = lambda *args: (_ for _ in ()).throw(KeyError("boom"))
        report = workflow.run(["AAPL"], PeriodSelection(self.period, self.period), True)
        self.assertFalse(report["complete"])
        evidence = self.evidence()
        self.assertEqual(evidence["status"], "failed")
        self.assertIn("boom", evidence["error"])
        self.assertEqual(evidence["rows"][0]["fields"]["Mac"]["status"], "failed")
        directory = self.data / "outputs/AAPL" / self.period / "evidence"
        self.assertEqual(sorted(p.name for p in directory.iterdir()), ["evidence.json"])

    def test_cache_key_covers_sec_urls_and_playwright_version(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        self.assertEqual(self.evidence()["playwright"], playwright_version())
        path = self.data / "pipeline/AAPL/packages.json"
        packages = JsonCodec.read(path)
        packages["packages"][Q_ACC]["documents"]["aapl-20250628.htm"]["ixviewer_url"] = "https://www.sec.gov/ix?doc=/other.htm"
        JsonCodec.write(path, packages)
        self.assertEqual(self.run_evidence()["companies"][0]["periods"][0]["status"], "complete")
        self.assertEqual(self.evidence()["facts"][fkey(Q_ACC, "f-2")]["ixviewer_url"], "https://www.sec.gov/ix?doc=/other.htm")

    def test_period_selection_defaults_to_latest(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])}, "2025-06-28")
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        report = EvidenceWorkflow(self.data, screenshotter=FakeScreenshotter).run(["AAPL"], PeriodSelection())
        self.assertEqual([p["period_end"] for p in report["companies"][0]["periods"]], [self.period])

    def test_requires_extraction(self):
        with self.assertRaisesRegex(ValueError, "尚未萃取"):
            EvidenceWorkflow(self.data, screenshotter=FakeScreenshotter).run(["AAPL"], PeriodSelection())


class TableHtmlTest(unittest.TestCase):
    def test_extracted_table_drops_scripts_links_and_external_resources(self):
        page = TableLocator(TEN_Q).table_html(
            1,
            [{"id": "f-2", "badge": "1", "raw": "24,982", "label": "Mac"}],
            {"ticker": "AAPL", "form": "10-Q", "accession": Q_ACC, "source_url": "https://www.sec.gov/x.htm"},
        ).decode()
        for forbidden in ("<script", "evil.example", "onclick", "url(", "<img", "<a ", "ix:nonfraction"):
            self.assertNotIn(forbidden, page.lower())
        self.assertIn("Content-Security-Policy", page)
        # 含 url( 的 style 整個移除，不留下部分樣式。
        self.assertNotIn("color:#000", page)
        self.assertIn("24,982", page)
        self.assertIn('class="sec-evidence-badge">1</span>', page)

    def test_sanitize_removes_media_attributes_and_unsafe_styles(self):
        from lxml import html as lxml_html

        table = lxml_html.fromstring(
            "<table><tr><td style='color:red;background:u\\72l(x)' poster='p' formaction='f'>a</td>"
            "<td style='color:blue'><video poster='x'></video>b</td>"
            "<td style='@import \"x.css\"'>c</td></tr></table>"
        )
        TableLocator.sanitize(table)
        text = lxml_html.tostring(table, encoding="unicode")
        for forbidden in ("poster", "formaction", "@import", "\\", "<video", "color:red"):
            self.assertNotIn(forbidden, text)
        self.assertIn("color:blue", text)

    def test_locator_matches_parser_table_numbering(self):
        locator = TableLocator(TEN_Q)
        self.assertEqual(locator.locate("f-4"), ("in_table", 1))
        self.assertEqual(locator.locate("f-9"), ("not_in_table", None))
        self.assertEqual(locator.locate("missing"), ("fact_not_found", None))

    def test_expression_terms_expand_aggregation_inside_q4(self):
        parts = [nine("f-2", 10, "10"), nine("f-4", 20, "20")]
        nine_sum = dict(nine("f-2", 30, "30"), aggregation_evidence=parts)
        operand = q4(annual("f-1", 100, "100"), nine_sum)
        terms = expression_terms(operand, 1)
        self.assertEqual([(w, r, f["fact_id"]) for w, r, f in terms], [(1, "annual", "f-1"), (-1, "aggregation", "f-2"), (-1, "aggregation", "f-4")])
        self.assertEqual(sum(w * f["value"] for w, _, f in terms), operand["value"])

    def test_duration_label(self):
        self.assertEqual(duration_label({"startdate": "2025-03-30", "enddate": "2025-06-28"}), "3M")
        self.assertEqual(duration_label({"startdate": "2024-09-29", "enddate": "2025-06-28"}), "9M")
        self.assertEqual(duration_label({"startdate": "2024-09-29", "enddate": "2025-09-27"}), "年度")
        self.assertEqual(duration_label({"enddate": "2025-09-27"}), "時點")


class ViewerEvidenceTest(EvidenceFixture):
    def test_revenue_api_attaches_evidence_and_flags_stale_output(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        viewer = RevenueViewer(self.data)
        status, _, body = viewer.request("/api/revenue?ticker=AAPL")
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)[0]["evidence"])
        self.run_evidence()
        row = json.loads(viewer.request("/api/revenue?ticker=AAPL")[2])[0]
        self.assertFalse(row["evidence"]["stale"])
        self.assertEqual(row["evidence"]["fields"]["Mac"]["status"], "ok")
        self.assertEqual(row["evidence"]["tables"][tkey(Q_ACC, 1)]["png"], tkey(Q_ACC, 1) + ".png")
        path = self.data / "outputs/AAPL" / self.period / f"AAPL_{self.period}_reported_revenue.json"
        path.write_bytes(path.read_bytes().replace(b"24,982", b"24,983"))
        row = json.loads(viewer.request("/api/revenue?ticker=AAPL")[2])[0]
        self.assertTrue(row["evidence"]["stale"])

    def test_stale_when_table_file_or_rules_change(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        viewer = RevenueViewer(self.data)
        evidence_path = self.data / "outputs/AAPL" / self.period / "evidence/evidence.json"
        evidence = JsonCodec.read(evidence_path)
        png = self.data / evidence["tables"][tkey(Q_ACC, 1)]["png"]["path"]
        png.write_bytes(b"tampered")
        row = json.loads(viewer.request("/api/revenue?ticker=AAPL")[2])[0]
        self.assertTrue(row["evidence"]["stale"])
        self.assertIn("表格檔", row["evidence"]["stale_reasons"][0])
        self.run_evidence()
        evidence = JsonCodec.read(evidence_path)
        evidence["rules_sha256"] = "0" * 64
        JsonCodec.write(evidence_path, evidence)
        row = json.loads(viewer.request("/api/revenue?ticker=AAPL")[2])[0]
        self.assertEqual(row["evidence"]["stale_reasons"], ["證據由不同版本的證據程式產生"])

    def test_broken_evidence_json_reports_error_for_that_period_only(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])}, "2025-06-28")
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence(period="2025-06-28")
        self.run_evidence()
        (self.data / "outputs/AAPL" / self.period / "evidence/evidence.json").write_text("{broken")
        status, _, body = RevenueViewer(self.data).request("/api/revenue?ticker=AAPL")
        self.assertEqual(status, 200)
        rows = {r["period_end"]: r for r in json.loads(body)}
        self.assertIn("無法讀取", rows[self.period]["evidence"]["error"])
        self.assertFalse(rows["2025-06-28"]["evidence"]["stale"])

    def test_each_evidence_file_is_read_once_per_request(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        viewer = RevenueViewer(self.data)
        calls = []
        original = viewer.load_evidence
        viewer.load_evidence = lambda path: calls.append(path) or original(path)
        index = self.data / "outputs/AAPL/index.json"
        manifest = JsonCodec.read(index)
        extra = self.data / "outputs/AAPL" / self.period / f"AAPL_{self.period}_other_revenue.json"
        extra.write_bytes((self.data / "outputs/AAPL" / manifest["paths"][0]).read_bytes())
        manifest["paths"].append(f"{self.period}/{extra.name}")
        JsonCodec.write(index, manifest)
        viewer.request("/api/revenue?ticker=AAPL")
        self.assertEqual(len(calls), 1)

    def test_evidence_route_serves_only_named_evidence_files(self):
        self.write_outputs({"Mac": output([nine("f-2", 24982000000, "24,982")])})
        self.run_evidence()
        viewer = RevenueViewer(self.data)
        status, kind, body = viewer.request(f"/evidence/AAPL/{self.period}/{tkey(Q_ACC, 1)}.png")
        self.assertEqual((status, kind), (200, "image/png"))
        self.assertTrue(body.startswith(b"\x89PNG"))
        self.assertEqual(viewer.request(f"/evidence/AAPL/{self.period}/{tkey(Q_ACC, 1)}.html")[1], "text/html; charset=utf-8")
        for bad in (
            f"/evidence/AAPL/{self.period}/evidence.json",
            f"/evidence/AAPL/{self.period}/../AAPL_{self.period}_reported_revenue.json",
            f"/evidence/AAPL/../../pipeline/{tkey(Q_ACC, 1)}.png",
            f"/evidence/NOPE/{self.period}/{tkey(Q_ACC, 1)}.png",
        ):
            self.assertEqual(viewer.request(bad)[0], 400, bad)
        self.assertEqual(viewer.request(f"/evidence/AAPL/{self.period}/{tkey(Q_ACC, 9)}.png")[0], 404)


def chromium_available() -> bool:
    try:
        with TableScreenshotter():
            return True
    except Exception:
        return False


@unittest.skipUnless(chromium_available(), "需要 Playwright Chromium")
class ScreenshotSmokeTest(unittest.TestCase):
    def test_capture_marks_table_and_crops_tall_tables(self):
        rows = "".join(f"<tr><td style='height:40px'>row {i}</td><td>{i}</td></tr>" for i in range(150))
        tall = (
            "<html xmlns:ix='http://www.xbrl.org/2013/inlineXBRL'><body><table>"
            + rows
            + f"<tr><td>Mac</td><td>{fact('f-1', 0, '33,708', '', '')}</td></tr>"
            + "</table><img src='https://evil.example/x.png'></body></html>"
        ).encode()
        with TableScreenshotter() as screenshotter:
            png, cropped, text = screenshotter.capture(TEN_K, [{"id": "f-1", "badge": "1", "raw": "33,708"}])
            self.assertTrue(png.startswith(b"\x89PNG"))
            self.assertFalse(cropped)
            self.assertEqual(text, TableLocator(TEN_K).table_text(0))
            with self.assertRaisesRegex(Exception, "文字與運算元不符"):
                screenshotter.capture(TEN_K, [{"id": "f-1", "badge": "1", "raw": "99"}])
            tall_png, tall_cropped, _ = screenshotter.capture(tall, [{"id": "f-1", "badge": "1", "raw": "33,708"}])
            self.assertTrue(tall_cropped)
            # 裁切後高度遠小於 150 列 × 40px 的原表（2× 裝置像素）。
            height = int.from_bytes(tall_png[20:24], "big")
            self.assertLess(height, 2 * 3000)


if __name__ == "__main__":
    unittest.main()
