"""框架與公司 parser 的介面：框架只交 fact 清單、依交回的 fact 計算數值，並核對組成與 `categories`。"""

import dataclasses
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.parser_utils import find, put  # noqa: E402
from sec_revenue.revenue.contract import Composition, ParserFailure, Term  # noqa: E402
from sec_revenue.revenue.review import comparatives  # noqa: E402
from sec_revenue.revenue.filings import ParseError  # noqa: E402
from sec_revenue.revenue.source import ParserSource  # noqa: E402
from sec_revenue.revenue.xbrl import InlineDocument  # noqa: E402
from tests.sec_revenue.revenue.test_revenue_parser import A, B, NAMESPACES, REVENUE, Fixture, build_html, item, quarter_items  # noqa: E402


def module(compose=None, categories=None, view="product"):
    """合成的公司 parser：A、B 兩類與總營收。"""
    parser = types.ModuleType("test_parser")
    parser.TICKER, parser.VIEW, parser.TOTAL = "TEST", view, "Total"

    def default_compose(filing, request):
        result = Composition()
        put(result, "category", "A", find(filing, request, REVENUE, A))
        put(result, "category", "B", find(filing, request, REVENUE, B))
        put(result, "total", "Total", find(filing, request, REVENUE))
        return result

    parser.compose = compose or default_compose
    parser.categories = categories or (lambda day: ["A", "B"])
    return parser


class ParserSourceTest(Fixture):
    def quarter(self, extra=()):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40)) + list(extra)))

    def test_parser_composition_becomes_lines(self):
        self.quarter()
        result = self.composer(ParserSource(module())).compose("2025-03-31")
        self.assertEqual([(l.name, l.group, l.value) for l in result.lines], [("A", "category", 60_000_000), ("B", "category", 40_000_000), ("Total", "total", 100_000_000)])

    def test_parser_gets_facts_without_html(self):
        seen = []

        def compose(filing, request):
            seen.append((filing.document.locator, filing.report_date, request))
            return module().compose(filing, request)

        self.quarter()
        self.composer(ParserSource(module(compose))).compose("2025-03-31")
        locator, report_date, request = seen[0]
        self.assertIsNone(locator)
        self.assertEqual((report_date, request.end, request.duration), ("2025-03-31", "2025-03-31", "quarter"))

    def test_duplicates_are_added_by_framework(self):
        self.quarter([item("qa-dup", REVENUE, A, "2025-01-01", "2025-03-31", "60", 1)])
        result = self.composer(ParserSource(module())).compose("2025-03-31")
        operand = result.lines[0].terms[0].operand
        self.assertEqual((operand.fact.fact_id, [d.fact_id for d in operand.duplicates]), ("qa", ["qa-dup"]))

    def test_category_missing_from_composition_fails(self):
        self.quarter()

        def compose(filing, request):
            result = module().compose(filing, request)
            del result.categories["B"]
            return result

        with self.assertRaisesRegex(ParseError, r"\[定義唯一\].*B"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_missing_reason_is_reported(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))[::2]))
        with self.assertRaisesRegex(ParseError, r"\[fact 存在且唯一\] 找不到 B：.*x:BMember"):
            self.composer(ParserSource(module())).compose("2025-03-31")

    def test_extra_category_fails(self):
        self.quarter()
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\].*B"):
            self.composer(ParserSource(module(categories=lambda day: ["A"]))).compose("2025-03-31")

    def test_fact_from_another_filing_fails(self):
        other = InlineDocument(build_html(2025, "Q1", quarter_items("2025-03-31", (61, 39))))

        def compose(filing, request):
            result = module().compose(filing, request)
            result.categories["A"] = [Term((other.facts[0],))]
            return result

        self.quarter()
        with self.assertRaisesRegex(ParseError, "不在這份申報的 fact 清單中"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_fact_outside_requested_period_fails(self):
        self.quarter([item("ya", REVENUE, A, "2024-04-01", "2025-03-31", "250")])

        def compose(filing, request):
            result = module().compose(filing, request)
            result.categories["A"] = [Term(tuple(f for f in filing.facts if f.fact_id == "ya"))]
            return result

        with self.assertRaisesRegex(ParseError, "不是要求的期間"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_weight_must_be_one_or_minus_one(self):
        def compose(filing, request):
            result = module().compose(filing, request)
            result.categories["A"] = [Term(result.categories["A"][0].facts, 2)]
            return result

        self.quarter()
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\].*權重"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_compose_must_return_composition(self):
        self.quarter()
        with self.assertRaisesRegex(ParseError, "Composition"):
            self.composer(ParserSource(module(lambda filing, request: {}))).compose("2025-03-31")

    def test_fabricated_fact_fails(self):
        def compose(filing, request):
            result = module().compose(filing, request)
            real = result.categories["A"][0].facts[0]
            result.categories["A"] = [Term((dataclasses.replace(real, value=real.value + 1),))]
            return result

        self.quarter()
        with self.assertRaisesRegex(ParseError, "不在這份申報的 fact 清單中"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_fact_list_is_read_only(self):
        def compose(filing, request):
            filing.facts.append(filing.facts[0])
            return module().compose(filing, request)

        self.quarter()
        with self.assertRaises(AttributeError):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_composition_order_must_follow_categories(self):
        def compose(filing, request):
            result = module().compose(filing, request)
            result.categories = {"B": result.categories["B"], "A": result.categories["A"]}
            return result

        self.quarter()
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\].*順序"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_empty_terms_fail(self):
        def compose(filing, request):
            result = module().compose(filing, request)
            result.categories["A"] = []
            return result

        self.quarter()
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\].*沒有任何運算元"):
            self.composer(ParserSource(module(compose))).compose("2025-03-31")

    def test_comparative_failure_is_unparseable(self):
        published = {
            "categories": {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}]}},
            "total": {"value": 60_000_000, "expression": []},
            "operands": {"op1": {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": A,
                                 "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": 60_000_000, "raw": "60", "scale": "6", "decimals": "-6"}},
        }
        document = InlineDocument(build_html(2025, "Q1", [item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "60")]))

        def fail(request):
            raise ParserFailure("fact 存在且唯一", "前綴宣告衝突")

        found = comparatives(document, "new", [("Q", "2024-03-31", published)], fail, "Total")
        self.assertEqual((found[0]["result"], found[0]["listed_value"]), ("unparseable", None))
        self.assertIn("前綴宣告衝突", found[0]["note"])
        # 申報沒有列示這段期間時，組不出來不算無法比較，不產生標記。
        other = InlineDocument(build_html(2025, "Q1", [item("qa", REVENUE, A, "2025-01-01", "2025-03-31", "60")]))
        self.assertEqual(comparatives(other, "new", [("Q", "2024-03-31", published)], fail, "Total"), [])

    def test_geography_is_recognized_by_namespace_uri(self):
        # 文件以別的前綴指向 srt 的 namespace；只列美國成員時，非美國成員沒有列出，地區成員完整不通過。
        geo = "geo:StatementGeographicalAxis"
        items = [
            item("us", REVENUE, {geo: "x:USMember"}, "2025-01-01", "2025-03-31", "60"),
            item("nonus", REVENUE, {geo: "x:NonUSMember"}, "2025-01-01", "2025-03-31", "40"),
            item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "100"),
        ]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items, {**NAMESPACES, "geo": NAMESPACES["srt"]}))

        def compose(filing, request):
            result = Composition()
            put(result, "category", "A", find(filing, request, REVENUE, {geo: "x:USMember"}))
            put(result, "total", "Total", find(filing, request, REVENUE))
            return result

        with self.assertRaisesRegex(ParseError, r"\[地區成員完整\].*NonUSMember"):
            self.composer(ParserSource(module(compose, categories=lambda day: ["A"]))).compose("2025-03-31")

    def test_view_is_validated(self):
        with self.assertRaisesRegex(ValueError, "VIEW"):
            ParserSource(module(view="geography"))

    def test_q4_uses_categories_for_derivation_condition(self):
        self.standard_year()
        # 分類集合在財年初的一段期間不同：各期期末日的組成都一致，判斷依 categories 的每一天。
        changed = lambda day: ["A"] if day <= "2025-01-15" else ["A", "B"]  # noqa: E731
        parser = ParserSource(module(categories=changed))
        with self.assertRaisesRegex(ParseError, "Q4 推算條件"):
            self.composer(parser).compose("2025-12-31")

    def test_q4_derives_with_parser(self):
        self.standard_year()
        result = self.composer(ParserSource(module())).compose("2025-12-31")
        self.assertEqual([l.value for l in result.lines], [90_000_000, 10_000_000, 100_000_000])

    def test_engine_writes_output_with_parser(self):
        self.standard_year()
        report = self.parser(ParserSource(module())).run(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"])
        self.assertTrue(report["complete"])
        self.assertEqual(self.output("2025-12-31")["categories"]["A"]["value"], 90_000_000)
        self.assertNotIn("reconciling", self.output("2025-12-31"))


if __name__ == "__main__":
    unittest.main()
