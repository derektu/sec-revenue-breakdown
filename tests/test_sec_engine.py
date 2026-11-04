"""新架構行為與三十家公司重播；凍結答案只在測試讀取。"""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT / "scripts"))
from sec_revenue.engines import (
    EvidenceStore,
    JsonCodec,
    QuarterEngine,
    SelectionEngine,
    XbrlEngine,
    SecDownloadEngine,
    PrecisionAnalyzer,
)
from sec_revenue.service import ReplayService, ParserRegistry, RiskAnalyzer
from sec_revenue.parsers.base import IssuerParser
from sec_revenue.viewer import RevenueViewer
from check_engine_regression import RegressionCheck


class EngineTests(unittest.TestCase):
    def fact(self, value=100, start="2025-01-01", end="2025-12-31", **extra):
        return dict(
            concept="revenue",
            dimensions={},
            unit="iso4217:USD",
            value=value,
            startdate=start,
            enddate=end,
            decimals="-6",
            source_url="https://www.sec.gov/Archives/edgar/data/1/000000000125000001/a.htm",
            accession="0000000001-25-000001",
            **extra,
        )

    def test_q4_retains_both_operands_and_period(self):
        annual = self.fact(100)
        nine = self.fact(70, end="2025-09-30")
        rows, bad = QuarterEngine().quarter([annual], "2025-12-31", [nine])
        self.assertFalse(bad)
        self.assertEqual(rows[0]["value"], 30)
        self.assertEqual(rows[0]["startdate"], "2025-10-01")
        self.assertEqual(rows[0]["annual_evidence"], annual)
        self.assertEqual(rows[0]["nine_month_evidence"], nine)
        self.assertEqual(PrecisionAnalyzer().fact_error(rows[0]), 1000000)

    def test_q4_missing_never_zero(self):
        rows, _ = QuarterEngine().quarter([self.fact()], "2025-12-31", [])
        self.assertEqual(rows, [])

    def test_q4_scope_or_start_mismatch_refuses(self):
        for changes in [
            {"dimensions": {"axis": "member"}},
            {"startdate": "2025-01-02"},
        ]:
            nine = self.fact(70, end="2025-09-30")
            nine.update(changes)
            rows, _ = QuarterEngine().quarter([self.fact()], "2025-12-31", [nine])
            self.assertFalse(rows)

    def test_q4_ambiguous_operand_refuses(self):
        rows, bad = QuarterEngine().quarter(
            [self.fact()],
            "2025-12-31",
            [self.fact(70, end="2025-09-30"), self.fact(71, end="2025-09-30")],
        )
        self.assertFalse(rows)
        self.assertTrue(bad)

    def test_empty_expression_cannot_create_zero(self):
        output = SelectionEngine().select({"alternatives": [[]]}, [], [])
        self.assertIsNone(output["value_usd"])

    def test_alternatives_preserved_without_double_sum(self):
        fact = self.fact()
        other = dict(fact, concept="alternate")
        term = lambda f: {k: f[k] for k in ("concept", "dimensions", "unit")}
        output = SelectionEngine().select(
            {"alternatives": [[term(fact)], [term(other)]]}, [fact, other], []
        )
        self.assertEqual(output["value_usd"], 100)
        self.assertEqual(len(output["SEC_operands"]), 2)
        self.assertEqual(PrecisionAnalyzer().output_error(output), "500000")
        other["value"] = 101
        self.assertIsNone(
            SelectionEngine().select(
                {"alternatives": [[term(fact)], [term(other)]]}, [fact, other], []
            )["value_usd"]
        )

    def test_evidence_keeps_different_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            store = EvidenceStore(Path(temp))
            a = store.capture("AAPL", "2025-01-01", "acc", b"first", "web_text", {})
            b = store.capture("AAPL", "2025-01-01", "acc", b"second", "web_text", {})
            self.assertNotEqual(a["path"], b["path"])
            self.assertEqual(Path(a["path"]).read_bytes(), b"first")
            self.assertTrue(a["path"].endswith(".txt"))

    def test_cache_alteration_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "AAPL.json.gz"
            raw = (
                ROOT / "research/sec-30-baseline-2026-11-04/AAPL.json.gz"
            ).read_bytes()
            path.write_bytes(raw + b"changed")
            JsonCodec.write(
                path.parent / "verification.json",
                {"artifact_sha256": {path.name: hashlib.sha256(raw).hexdigest()}},
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                XbrlEngine().read_cache(path)

    def test_download_denial_is_single_request(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = SecDownloadEngine(
                EvidenceStore(Path(temp)), "Research operator contact@research.test"
            )
            with patch(
                "sec_revenue.engines.urlopen",
                side_effect=HTTPError("url", 403, "Forbidden", {}, None),
            ) as request:
                with self.assertRaises(HTTPError):
                    engine.download(
                        "AAPL",
                        "2025-01-01",
                        "acc",
                        "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/a.htm",
                    )
                self.assertEqual(request.call_count, 1)
            self.assertFalse(list(Path(temp).rglob("*.html")))

    def test_download_requires_contact(self):
        with self.assertRaises(ValueError):
            SecDownloadEngine(None, "")

    def test_inline_xbrl_value_and_full_scope(self):
        body = b'<html><xbrli:context id="c"><xbrli:period><xbrli:startdate>2025-01-01</xbrli:startdate><xbrli:enddate>2025-03-31</xbrli:enddate></xbrli:period><xbrldi:explicitmember dimension="axis">member</xbrldi:explicitmember></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonfraction name="us-gaap:Revenues" contextref="c" unitref="u" scale="6" decimals="-6">123</ix:nonfraction></html>'
        facts = XbrlEngine().parse_html(body, "https://www.sec.gov/a", "acc")
        self.assertEqual(facts[0]["value"], 123000000)
        self.assertEqual(facts[0]["dimensions"], {"axis": "member"})

    def test_typed_dimension_is_rejected_instead_of_dropped(self):
        with self.assertRaisesRegex(ValueError, "typed dimension"):
            XbrlEngine().parse_html(
                b'<html><xbrldi:typedmember dimension="axis">unknown</xbrldi:typedmember></html>',
                "url",
                "acc",
            )

    def test_fiscal_year_for_retail_and_non_december(self):
        registry = ParserRegistry()
        for ticker, period, year, quarter in [
            ("HD", "2026-08-02", 2026, 2),
            ("MSFT", "2026-09-30", 2027, 1),
            ("NVDA", "2026-01-25", 2026, 4),
        ]:
            records = XbrlEngine().read_cache(
                ROOT / f"research/sec-30-baseline-2026-11-04/{ticker}.json.gz"
            )
            label = registry.create(ticker).fiscal_label(period, records)
            self.assertEqual(
                (label["fiscal_year"], label["fiscal_quarter"]), (year, quarter)
            )

    def test_new_ticker_registration_is_isolated(self):
        registry = ParserRegistry()
        original = copy.deepcopy(registry.create("AAPL").rules)
        records = XbrlEngine().read_cache(
            ROOT / "research/sec-30-baseline-2026-11-04/AAPL.json.gz"
        )
        original_output = registry.create("AAPL").parse(records)
        module = types.ModuleType("sec_revenue.issuers.n.newissuer.parser")

        class NewIssuer(IssuerParser):
            ticker = "NEW"
            rules = {"reported": {}}

        module.NewIssuer = NewIssuer
        with patch.dict(
            sys.modules, {"sec_revenue.issuers.n.newissuer.parser": module}
        ):
            registry.entries["NEW"] = {"module": "newissuer", "class": "NewIssuer"}
            self.assertEqual(registry.create("NEW").ticker, "NEW")
            NewIssuer.rules = {"reported": {"new-only": {"alternatives": []}}}
            self.assertEqual(registry.create("AAPL").rules, original)
            self.assertEqual(registry.create("AAPL").parse(records), original_output)

    def test_recent_schema_change_raises_risk(self):
        def row(end, dimensions):
            return {
                "period_end": end,
                "outputs": {
                    "Revenue": {
                        "status": "observed",
                        "SEC_operands": [dict(self.fact(), dimensions=dimensions)],
                    }
                },
            }

        stable = [row("2025-03-31", {}), row("2025-06-30", {}), row("2025-09-30", {})]
        changed = copy.deepcopy(stable)
        changed[-1]["outputs"]["Revenue"]["SEC_operands"][0]["dimensions"] = {
            "axis": "new"
        }
        self.assertGreater(
            RiskAnalyzer().assess(changed)["score"],
            RiskAnalyzer().assess(stable)["score"],
        )

    def test_missing_history_and_missing_value_not_low_risk(self):
        row = {
            "period_end": "2025-03-31",
            "outputs": {"Revenue": {"status": "missing", "SEC_operands": []}},
        }
        self.assertEqual(RiskAnalyzer().assess([row])["level"], "high")

    def test_nested_actual_rules_appear_in_risk(self):
        fact = self.fact()
        fact["annual_evidence"] = dict(self.fact(), normalization_rule_id="nested-rule")
        fact["nine_month_evidence"] = self.fact()
        fact["derivation"] = "annual_minus_nine_months"
        result = RiskAnalyzer().assess(
            [
                {
                    "period_end": "2025-12-31",
                    "outputs": {"x": {"status": "observed", "SEC_operands": [fact]}},
                }
            ]
        )
        self.assertIn("nested-rule", " ".join(result["reasons"]))

    def test_runtime_has_no_legacy_imports_or_expected_reads(self):
        for path in (ROOT / "libs/sec_revenue").rglob("*.py"):
            text = path.read_text()
            self.assertNotIn("_expected", text, str(path))
            self.assertNotIn("data/vendor/local", text, str(path))
            self.assertNotIn("from scripts", text, str(path))
            self.assertNotIn("if ticker ==", text, str(path))

    def test_viewer_rejects_paths_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            viewer = RevenueViewer(Path(temp))
            for url in [
                "/api/revenue?ticker=../AAPL",
                "/api/revenue?ticker=AAPL&path=x",
                "/api/revenue?ticker=AAPL&ticker=MSFT",
            ]:
                self.assertEqual(viewer.request(url)[0], 400)
            self.assertEqual(viewer.request("/api/revenue?ticker=AAPL")[0], 404)
            self.assertEqual(viewer.request("/missing")[0], 404)


class ThirtyIssuerIntegrationTests(unittest.TestCase):
    def test_all_240_periods_operands_and_two_run_determinism(self):
        manifest = JsonCodec.read(
            ROOT / "research/refactor-baseline-sec-20261104/manifest.json"
        )
        count = 0
        with tempfile.TemporaryDirectory() as temp:
            service = ReplayService(ROOT, Path(temp))
            checker = RegressionCheck()
            for company in manifest["companies"]:
                ticker = company["ticker"]
                first = service.replay(ticker)
                second = service.replay(ticker)
                self.assertEqual(
                    JsonCodec.encode(first), JsonCodec.encode(second), ticker
                )
                if ticker == "CVX":
                    net = [row for row in first if row["basis"] == "net"]
                    self.assertEqual(len(net), 8)
                    for row in net:
                        self.assertTrue(
                            all(
                                o["status"] == "observed"
                                for o in row["outputs"].values()
                            )
                        )
                        self.assertEqual(
                            sum(
                                o["value_usd"]
                                for k, o in row["outputs"].items()
                                if k != "consolidated_sales"
                            ),
                            row["outputs"]["consolidated_sales"]["value_usd"],
                        )
                basis = service.registry.entries[ticker]["primary_basis"]
                if ticker == "CVX":
                    basis = "gross"
                rows = {
                    row["period_end"]: row for row in first if row["basis"] == basis
                }
                self.assertEqual(set(rows), set(company["periods"]), ticker)
                for period in company["periods"]:
                    target = JsonCodec.read(
                        ROOT
                        / f"research/refactor-baseline-sec-20261104/{ticker}/{period}/{ticker}_{period}_SEC_expected.json.gz"
                    )
                    for label, expected in target["outputs"].items():
                        actual = rows[period]["outputs"][label]
                        count += 1
                        self.assertEqual(
                            actual["value_usd"],
                            expected["value_usd"],
                            (ticker, period, label),
                        )
                        self.assertEqual(
                            checker.operand_signature(actual["SEC_operands"]),
                            checker.operand_signature(expected["SEC_operands"]),
                            (ticker, period, label),
                        )
            self.assertEqual(count, 1092)
