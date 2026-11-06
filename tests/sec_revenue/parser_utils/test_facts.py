"""parser_utils.facts：依 concept 與 dimensions 精確找 fact、多種寫法、放進組成。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.parser_utils import Missing, find, one_of, put  # noqa: E402
from sec_revenue.revenue.contract import Composition, FilingFacts, ParserFailure, Request  # noqa: E402
from sec_revenue.revenue.source import facts_only  # noqa: E402
from sec_revenue.revenue.xbrl import InlineDocument  # noqa: E402
from tests.sec_revenue.revenue.test_revenue_parser import A, AXIS, NAMESPACES, REVENUE, build_html, item  # noqa: E402

Q1 = Request("2025-03-31", "quarter")
ALT_A = {AXIS: "x:AltAMember"}


def filing(items, namespaces=None, html=None):
    document = InlineDocument(html or build_html(2025, "Q1", items, namespaces))
    return FilingFacts("acc-1", "10-Q", "2025-03-31", facts_only(document))


class FindTest(unittest.TestCase):
    def test_exact_concept_and_dimensions(self):
        facts = filing([
            item("qa", REVENUE, A, "2025-01-01", "2025-03-31", "60"),
            item("qa2", REVENUE, {**A, "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}, "2025-01-01", "2025-03-31", "60"),
            item("ya", REVENUE, A, "2024-01-01", "2025-03-31", "200"),
            item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "100"),
        ])
        found = find(facts, Q1, REVENUE, A)
        self.assertEqual([f.fact_id for f in found.facts], ["qa"])
        self.assertEqual(found.weight, 1)
        self.assertEqual([f.fact_id for f in find(facts, Q1, REVENUE).facts], ["qt"])
        self.assertEqual(find(facts, Q1, REVENUE, A, weight=-1).weight, -1)

    def test_missing_and_undeclared_prefix(self):
        facts = filing([item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "100")])
        self.assertIsInstance(find(facts, Q1, REVENUE, A), Missing)
        missing = find(facts, Q1, REVENUE, {AXIS: "zz:AMember"})
        self.assertIn("前綴在文件中沒有宣告", missing.reason)

    def test_conflicting_prefix_fails(self):
        html = build_html(2025, "Q1", [item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "100")], {**NAMESPACES, "y": NAMESPACES["x"]})
        html = html.replace(b"<body>", b'<body><span xmlns:y="http://example.com/other"></span>', 1)
        with self.assertRaisesRegex(ParserFailure, "宣告衝突"):
            find(filing([], html=html), Q1, REVENUE, {AXIS: "y:AMember"})

    def test_one_of_merges_variants_in_document_order(self):
        facts = filing([
            item("alt", REVENUE, ALT_A, "2025-01-01", "2025-03-31", "60"),
            item("qa", REVENUE, A, "2025-01-01", "2025-03-31", "60"),
        ])
        found = one_of(facts, Q1, (REVENUE, A), (REVENUE, ALT_A), (REVENUE, {AXIS: "zz:AMember"}))
        self.assertEqual([f.fact_id for f in found.facts], ["alt", "qa"])
        self.assertIsInstance(one_of(facts, Q1, (REVENUE, {AXIS: "x:BMember"}), (REVENUE, {AXIS: "x:CMember"})), Missing)

    def test_put_records_missing_items(self):
        facts = filing([item("qa", REVENUE, A, "2025-01-01", "2025-03-31", "60")])
        result = Composition()
        put(result, "category", "A", find(facts, Q1, REVENUE, A))
        put(result, "category", "B", find(facts, Q1, REVENUE, A), find(facts, Q1, REVENUE, {AXIS: "x:BMember"}))
        put(result, "total", "Total", find(facts, Q1, REVENUE))
        self.assertEqual(list(result.categories), ["A"])
        self.assertIsNone(result.total)
        self.assertEqual(sorted(result.missing), ["B", "Total"])
        self.assertIn("x:BMember", result.missing["B"])
        with self.assertRaises(ValueError):
            put(result, "segment", "C", find(facts, Q1, REVENUE, A))

    def test_facts_only_has_no_html(self):
        facts = filing([item("qa", REVENUE, A, "2025-01-01", "2025-03-31", "60")])
        self.assertIsNone(facts.document.locator)
        self.assertFalse(hasattr(facts.document, "tables"))


if __name__ == "__main__":
    unittest.main()
