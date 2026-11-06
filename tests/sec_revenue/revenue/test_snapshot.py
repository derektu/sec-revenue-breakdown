"""XBRL fact 快照：往返等價、快照模式不讀原文、涵蓋性與解析器版本檢查、申報清單與反向測試。"""

import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.common.jsonio import JsonCodec  # noqa: E402
from sec_revenue.revenue import snapshot  # noqa: E402
from sec_revenue.revenue.compose import PeriodComposer  # noqa: E402
from sec_revenue.revenue.engine import check_outputs, ticker_dir  # noqa: E402
from sec_revenue.revenue.filings import FilingSet, ParseError  # noqa: E402
from sec_revenue.revenue.spec import Category, CompanySpec, fact, sum_of  # noqa: E402
from sec_revenue.revenue.xbrl import InlineDocument  # noqa: E402

# 匯入模組而不是 TestCase 類別，避免同一批測試在這裡再跑一次。
from tests.sec_revenue.revenue import test_revenue_parser as base  # noqa: E402

REVENUE, SPEC, build_html, item, quarter_items = base.REVENUE, base.SPEC, base.build_html, base.item, base.quarter_items


class SnapshotFixture(base.Fixture):
    def setUp(self):
        super().setUp()
        self.snapshots = Path(self.temp.name) / "snapshots"

    def directory(self):
        return snapshot.snapshot_dir(self.snapshots, "TEST")

    def publish(self):
        """以原文跑一次 parse 並產生快照。"""
        parser = self.parser()
        parser.run(parser.periods())
        snapshot.write(self.data, self.snapshots, SPEC)

    def check_from_snapshots(self, spec=SPEC):
        return check_outputs(Path(self.temp.name) / "no-sec-data", self.out, spec, "spec-sha", None, snapshots=self.snapshots)[1]


class RoundTripTest(SnapshotFixture):
    def test_snapshot_rebuilds_the_same_document(self):
        self.standard_year()
        filings = FilingSet(self.data, "TEST")
        concepts = snapshot.spec_concepts(SPEC)
        for filing in filings.filings:
            with self.subTest(filing.accession):
                original = filings.document(filing)
                # 經過 JSON 編碼再讀回，與快照檔的內容相同。
                payload = json.loads(JsonCodec.encode(original.to_snapshot(concepts)))
                rebuilt = InlineDocument.from_snapshot(payload)
                self.assertEqual(rebuilt.facts, original.facts)
                self.assertEqual(rebuilt.fiscal(), original.fiscal())
                self.assertEqual(rebuilt.namespaces, original.namespaces)
                self.assertEqual(rebuilt.resolve(REVENUE), original.resolve(REVENUE))
                self.assertIsNone(rebuilt.locator)

    def test_only_spec_concepts_are_kept(self):
        items = quarter_items("2025-03-31", (60, 40)) + [item("other", "us-gaap:CostOfRevenue", None, "2025-01-01", "2025-03-31", "5")]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        filings = FilingSet(self.data, "TEST")
        payload = filings.document(filings.filings[0]).to_snapshot(snapshot.spec_concepts(SPEC))
        self.assertEqual(sorted(f["fact_id"] for f in payload["facts"]), ["qa", "qb", "qt"])
        self.assertIn("dei:DocumentFiscalPeriodFocus", payload["dei"])


class SnapshotModeTest(SnapshotFixture):
    def test_check_runs_without_any_sec_original(self):
        self.standard_year()
        self.publish()
        shutil.rmtree(self.data)
        self.assertEqual(self.check_from_snapshots(), [])

    def test_changed_fact_value_is_caught(self):
        self.standard_year()
        self.publish()
        path = self.directory() / "0000000001-25-000001.json"
        payload = JsonCodec.read(path)
        changed = next(f for f in payload["facts"] if f["fact_id"] == "qa")
        changed["value"] += 1_000_000
        JsonCodec.write(path, payload)
        found = self.check_from_snapshots()
        self.assertTrue(any(d.startswith("Q 2025-03-31") for d in found), found)

    def test_raw_is_unavailable(self):
        self.standard_year()
        self.publish()
        filings = snapshot.SnapshotFilingSet(self.snapshots, SPEC)
        with self.assertRaisesRegex(Exception, "快照模式沒有"):
            filings.raw(filings.filings[0])

    def test_unreadable_original_is_reproduced_as_comparison_error(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", base.ComparativeTest.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", base.ComparativeTest.items("2025", (66, 44))))
        self.parser().run(["2024-03-31"])
        path = self.data / self.packages["0000000001-25-000001"]["documents"]["test-2025-03-31.htm"]["path"]
        path.write_bytes(b"tampered")
        self.parser().run([])
        result = snapshot.write(self.data, self.snapshots, SPEC)
        self.assertEqual(result["errors"], ["0000000001-25-000001"])
        self.assertEqual(self.check_from_snapshots(), [])


class SnapshotPathTest(SnapshotFixture):
    """快照模式與原文模式走同一段程式：申報篩選、新申報與證據、地區成員檢查。"""

    def test_new_published_period_without_snapshot_is_caught(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        snapshot.write(self.data, self.snapshots, SPEC)
        # 下載並上線新一期，但沒有重產快照。
        self.add("0000000001-25-000002", "10-Q", "2025-06-30", "2025-07-15", build_html(2025, "Q2", quarter_items("2025-06-30", (70, 30))))
        self.parser().run(["2025-06-30"])
        found = self.check_from_snapshots()
        self.assertTrue(any("2025-06-30" in d for d in found), found)

    def test_missing_committed_evidence_fails_the_period(self):
        self.standard_year()
        self.publish()
        evidence = ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "evidence"
        for path in evidence.glob("*.html"):
            path.unlink()
        found = self.check_from_snapshots()
        self.assertTrue(any(d.startswith("Q 2025-03-31") for d in found), found)

    def test_filing_selection_is_applied_to_snapshots(self):
        self.standard_year()
        self.publish()
        path = self.directory() / "0000000001-25-000001.json"
        payload = JsonCodec.read(path)
        payload["package"]["complete"] = False
        JsonCodec.write(path, payload)
        filings = snapshot.SnapshotFilingSet(self.snapshots, SPEC)
        self.assertNotIn("0000000001-25-000001", [f.accession for f in filings.filings])

    def test_geographic_member_check_runs_on_snapshot(self):
        geo, us, non_us = base.GEO, base.US, base.NON_US
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(Category("A", sum_of(fact(REVENUE, us), fact(REVENUE, non_us))),),
            total=Category("Total", fact(REVENUE)),
        )
        items = [
            item("q1", REVENUE, us, "2025-01-01", "2025-03-31", "60"),
            item("q2", REVENUE, non_us, "2025-01-01", "2025-03-31", "40"),
            item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "105"),
            item("geo", REVENUE, {geo: "x:OtherMember"}, "2025-01-01", "2025-03-31", "5"),
        ]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        snapshot.write(self.data, self.snapshots, spec)
        for filings in (FilingSet(self.data, "TEST"), snapshot.SnapshotFilingSet(self.snapshots, spec)):
            with self.subTest(snapshot=filings.snapshot):
                with self.assertRaisesRegex(ParseError, r"地區成員完整.*x:OtherMember"):
                    PeriodComposer(spec, filings).compose("2025-03-31")


class CoverageTest(SnapshotFixture):
    def test_concept_added_to_spec_requires_regeneration(self):
        self.standard_year()
        self.publish()
        wider = CompanySpec(
            ticker="TEST",
            view="product",
            categories=SPEC.categories + (Category("C", fact("us-gaap:OtherIncome")),),
            total=SPEC.total,
        )
        with self.assertRaisesRegex(ValueError, "us-gaap:OtherIncome.*snapshot --tickers TEST"):
            snapshot.SnapshotFilingSet(self.snapshots, wider)

    def test_parser_change_makes_snapshots_stale(self):
        self.standard_year()
        self.publish()
        with patch("sec_revenue.revenue.snapshot.parser_sha256", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "不同版本的解析器"):
                snapshot.SnapshotFilingSet(self.snapshots, SPEC)

    def test_snapshot_files_must_match_manifest(self):
        self.standard_year()
        self.publish()
        (self.directory() / "0000000001-25-000001.json").unlink()
        with self.assertRaisesRegex(ValueError, "0000000001-25-000001 沒有快照"):
            snapshot.SnapshotFilingSet(self.snapshots, SPEC)

    def test_snapshot_must_match_manifest_filing(self):
        self.standard_year()
        self.publish()
        path = self.directory() / "0000000001-25-000001.json"
        payload = JsonCodec.read(path)
        payload["package"]["filing"]["filingDate"] = "2025-12-31"
        JsonCodec.write(path, payload)
        with self.assertRaisesRegex(ValueError, "0000000001-25-000001 的申報資訊與申報清單不同"):
            snapshot.SnapshotFilingSet(self.snapshots, SPEC)
        payload["package"]["filing"]["filingDate"] = "2025-04-15"
        payload["accession"] = "0000000001-25-000009"
        JsonCodec.write(path, payload)
        with self.assertRaisesRegex(ValueError, "記錄的 accession 是 0000000001-25-000009"):
            snapshot.SnapshotFilingSet(self.snapshots, SPEC)

    def test_evidence_component_cannot_change_parsed_facts(self):
        # evidence.py 不在解析器 hash 內：它的解析入口與交給它的解析樹都不能影響 fact。
        self.standard_year()
        filings = FilingSet(self.data, "TEST")
        raw = filings.raw(filings.filings[-1])
        expected = InlineDocument(raw).facts

        def drop_first_table(locator, root):
            first = next(root.iter("table"))
            first.getparent().remove(first)
            locator.root, locator.tables, locator.index = root, [], {}

        with patch("sec_revenue.revenue.evidence.parse_html", side_effect=AssertionError("xbrl 不可經由 evidence 解析")), \
                patch("sec_revenue.revenue.evidence.TableLocator.attach", drop_first_table):
            self.assertEqual(InlineDocument(raw).facts, expected)

    def test_missing_snapshots_point_to_the_command(self):
        with self.assertRaisesRegex(ValueError, "沒有快照"):
            snapshot.SnapshotFilingSet(self.snapshots, SPEC)


class ManifestTest(SnapshotFixture):
    def test_manifest_lists_every_file_with_sha256(self):
        self.standard_year()
        snapshot.write(self.data, self.snapshots, SPEC)
        manifest = JsonCodec.read(self.directory() / snapshot.MANIFEST)
        self.assertEqual(
            [f["filing"]["accessionNumber"] for f in manifest["filings"]],
            [f.accession for f in FilingSet(self.data, "TEST").filings],
        )
        first = manifest["filings"][0]
        package = self.packages[first["filing"]["accessionNumber"]]
        self.assertEqual({n: d["sha256"] for n, d in first["documents"].items()}, {n: d["sha256"] for n, d in package["documents"].items()})

    def test_check_detects_changed_snapshot_and_stale_files(self):
        self.standard_year()
        snapshot.write(self.data, self.snapshots, SPEC)
        self.assertEqual(snapshot.check(self.data, self.snapshots, SPEC), [])
        path = self.directory() / "0000000001-25-000001.json"
        payload = JsonCodec.read(path)
        payload["dei"]["dei:DocumentFiscalYearFocus"] = "2024"
        JsonCodec.write(path, payload)
        (self.directory() / "0000000009-25-000009.json").write_text("{}")
        found = snapshot.check(self.data, self.snapshots, SPEC)
        self.assertIn("TEST 0000000001-25-000001.json：內容不同", found)
        self.assertIn("TEST 0000000009-25-000009.json：多出", found)

    def test_write_removes_snapshots_of_filings_no_longer_downloaded(self):
        self.standard_year()
        (self.directory()).mkdir(parents=True)
        (self.directory() / "0000000009-25-000009.json").write_text("{}")
        snapshot.write(self.data, self.snapshots, SPEC)
        self.assertFalse((self.directory() / "0000000009-25-000009.json").exists())


if __name__ == "__main__":
    unittest.main()
