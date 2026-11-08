"""分類改名的對應（`FORMER_NAMES`）：格式檢查、比較欄比對與 Q4 口徑一致以對應把新名稱接上已上線的舊名稱。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.parser_utils import find, put  # noqa: E402
from sec_revenue.revenue.contract import Composition, FilingFacts  # noqa: E402
from sec_revenue.revenue.review import comparatives, renamings  # noqa: E402
from sec_revenue.revenue.xbrl import InlineDocument  # noqa: E402
from tests.sec_revenue.revenue.test_revenue_parser import (  # noqa: E402
    A, B, COMPANY, REVENUE, Fixture, build_html, company, fact, item, operands, since, until,
)

RENAMED_FROM = "2025-01-01"


def renamed(**customizations):
    """2024 年以前第一類叫 A，2025 年起叫 A2（同一個成員 x:AMember），B 不變。"""
    return company(
        categories=(
            ("A", fact(REVENUE, A), until("2024-12-31")),
            ("A2", fact(REVENUE, A), since(RENAMED_FROM)),
            ("B", fact(REVENUE, B)),
        ),
        **customizations,
    )


MAPPED = renamed(FORMER_NAMES={"A2": ("A",)})
UNMAPPED = renamed()


def recorded(parser):
    """讓 `parser.comparatives` 的每一筆比對結果另外記到回傳的清單。"""
    record, original = [], parser.comparatives

    def wrapped(*args):
        found = original(*args)
        record.extend(found)
        return found

    parser.comparatives = wrapped
    return record


class FormerNamesFormatTest(unittest.TestCase):
    """框架只檢查格式；改名是否只是改名由公司 parser 以證據判斷。"""

    def test_default_without_declaration(self):
        self.assertEqual(dict(COMPANY.successors), {})

    def test_declaration_maps_old_names_to_new_name(self):
        source = company(FORMER_NAMES={"C": ("B", "A")})
        self.assertEqual(dict(source.successors), {"B": "C", "A": "C"})
        # 連續改名可以分段宣告。
        self.assertEqual(dict(company(FORMER_NAMES={"B": ("A",), "C": ("B",)}).successors), {"A": "B", "B": "C"})

    def test_malformed_declarations_fail(self):
        cases = {
            "不是 dict": ([("A2", ("A",))], "必須是非空的 dict"),
            "空的 dict": ({}, "必須是非空的 dict"),
            "新名稱不是字串": ({1: ("A",)}, "新名稱必須是非空字串"),
            "新名稱是空字串": ({"": ("A",)}, "新名稱必須是非空字串"),
            "舊名稱不是 tuple": ({"A2": "A"}, "舊名稱必須是非空的 tuple"),
            "舊名稱是空的 tuple": ({"A2": ()}, "舊名稱必須是非空的 tuple"),
            "舊名稱不是字串": ({"A2": (None,)}, "舊名稱必須是非空字串"),
            "舊名稱是空字串": ({"A2": ("",)}, "舊名稱必須是非空字串"),
            "對應到自己": ({"A2": ("A2",)}, "不能對應到自己"),
            "一個舊名稱在兩個新名稱之下": ({"A2": ("A",), "A3": ("A",)}, "一個舊名稱只能對應一個新名稱"),
            "同一個舊名稱列兩次": ({"A2": ("A", "A")}, "一個舊名稱只能對應一個新名稱"),
            "循環": ({"A2": ("A",), "A": ("A2",)}, "形成循環"),
            "新名稱是 TOTAL": ({"Total": ("A",)}, "新名稱 'Total' 是總營收的名稱"),
            "新名稱是總營收": ({"總營收": ("A",)}, "新名稱 '總營收' 是總營收的名稱"),
            "舊名稱是 TOTAL": ({"A2": ("Total",)}, "舊名稱 'Total' 是總營收的名稱"),
            "舊名稱是總營收": ({"A2": ("總營收",)}, "舊名稱 '總營收' 是總營收的名稱"),
        }
        for label, (declared, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(ValueError, "TEST 的 FORMER_NAMES.*" + message):
                company(FORMER_NAMES=declared)


class RenamingsTest(unittest.TestCase):
    def test_chain_follows_successors_in_order(self):
        self.assertEqual(renamings("A", {"A": "B", "B": "C"}), ["A", "B", "C"])
        self.assertEqual(renamings("B", {"A": "B", "B": "C"}), ["B", "C"])

    def test_name_without_successor(self):
        self.assertEqual(renamings("A", {}), ["A"])
        self.assertEqual(renamings("C", {"A": "B"}), ["C"])

    def test_cycle_stops_before_repeating(self):
        self.assertEqual(renamings("A", {"A": "B", "B": "A"}), ["A", "B"])


class RenamedComparativeTest(Fixture):
    """較晚申報以新名稱列示改名前的期別：依對應與已上線的舊名稱比對，標記掛在舊名稱上。"""

    def quarters(self, listed_a):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", [
            item("a", REVENUE, A, "2024-01-01", "2024-03-31", "60"),
            item("b", REVENUE, B, "2024-01-01", "2024-03-31", "40"),
            item("t", REVENUE, None, "2024-01-01", "2024-03-31", "100"),
        ]))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", [
            item("a", REVENUE, A, "2025-01-01", "2025-03-31", "66"),
            item("b", REVENUE, B, "2025-01-01", "2025-03-31", "44"),
            item("t", REVENUE, None, "2025-01-01", "2025-03-31", "110"),
            item("pa", REVENUE, A, "2024-01-01", "2024-03-31", str(listed_a), 1),
            item("pb", REVENUE, B, "2024-01-01", "2024-03-31", "40", 1),
            item("pt", REVENUE, None, "2024-01-01", "2024-03-31", str(listed_a + 40), 1),
        ]))

    def run_both(self, source):
        """（2024 Q1 的差異標記, 這次執行的全部比對結果）。"""
        parser = self.parser(source)
        record = recorded(parser)
        parser.run(["2024-03-31", "2025-03-31"])
        return self.status()["periods"]["Q"]["2024-03-31"].get("differences", []), record

    def first_category(self, record):
        return [(c.get("listed_category"), c["result"]) for c in record if c["category"] == "A" and c["period_end"] == "2024-03-31"]

    def test_consistent_through_mapping(self):
        self.quarters(60)
        markers, record = self.run_both(MAPPED)
        self.assertEqual(markers, [])
        self.assertEqual(self.first_category(record), [("A2", "consistent")])

    def test_different_through_mapping_is_marked_on_old_name(self):
        self.quarters(62)
        markers, _ = self.run_both(MAPPED)
        self.assertEqual(
            [(m["category"], m.get("listed_category"), m["published_value"], m["listed_value"]) for m in markers],
            [("A", "A2", 60_000_000, 62_000_000), ("總營收", None, 100_000_000, 102_000_000)],
        )
        self.assertEqual([a["fact_id"] for a in markers[0]["listed_addends"]], ["pa"])

    def test_without_mapping_renamed_category_is_not_compared(self):
        self.quarters(62)
        markers, record = self.run_both(UNMAPPED)
        self.assertEqual([m["category"] for m in markers], ["總營收"])
        self.assertEqual(self.first_category(record), [(None, "not_found")])

    def test_successive_renames_reach_latest_name(self):
        # A → A2 → A3 分段宣告；較晚的申報只有 A3。
        source = company(
            categories=(("A", fact(REVENUE, A), until("2024-12-31")), ("A3", fact(REVENUE, A), since(RENAMED_FROM)), ("B", fact(REVENUE, B))),
            FORMER_NAMES={"A2": ("A",), "A3": ("A2",)},
        )
        self.quarters(62)
        markers, _ = self.run_both(source)
        self.assertEqual([(m["category"], m.get("listed_category")) for m in markers], [("A", "A3"), ("總營收", None)])


def published(categories, reconciling=None):
    """合成的已上線 2024 Q1 revenue.json：`categories`、`reconciling` 是 名稱 → (值（百萬）, dimensions)。"""
    operands, lines = {}, {"categories": {}, "reconciling": {}}
    for group, entries in (("categories", categories), ("reconciling", reconciling or {})):
        for name, (value, dims) in entries.items():
            op = f"op{len(operands) + 1}"
            operands[op] = {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": dims,
                            "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": value * 1_000_000, "raw": str(value),
                            "scale": "6", "decimals": "-6"}
            lines[group][name] = {"value": value * 1_000_000, "expression": [{"weight": 1, "operand": op}]}
    output = {"categories": lines["categories"], "total": {"value": 0, "expression": []}, "operands": operands}
    if lines["reconciling"]:
        output["reconciling"] = lines["reconciling"]
    return output


DOCUMENT = InlineDocument(build_html(2025, "Q1", [
    item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "60"),
    item("pb", REVENUE, B, "2024-01-01", "2024-03-31", "40"),
    item("pt", REVENUE, None, "2024-01-01", "2024-03-31", "100"),
]))


def review(baseline, layout, successors, unparseable=()):
    """以 `layout`（(組別, 名稱, 運算元) 的清單）從 DOCUMENT 組出 2024 Q1 的組成，與 `baseline` 比對；`unparseable` 的
    名稱記為無法確定。回傳 名稱 → 比對結果。"""
    filing = FilingFacts("new", "10-Q", "2025-03-31", DOCUMENT)

    def compose_for(request):
        result = Composition()
        for group, name, get in layout:
            put(result, group, name, *operands(filing, request, get))
        for name in unparseable:
            result.unparseable[name] = "前綴宣告衝突"
        put(result, "total", "Total", find(filing, request, REVENUE))
        return result

    found = comparatives(DOCUMENT, "new", [("Q", "2024-03-31", baseline)], compose_for, "Total", successors=successors)
    return {c["category"]: c for c in found}


class RenamedReviewTest(unittest.TestCase):
    """比較欄比對在組成上的名稱對應：同名優先、無法確定、調節項，以及兩個已上線分類對到同一個名稱。"""

    def test_same_name_takes_priority_over_mapping(self):
        found = review(published({"A": (60, A)}), [("category", "A", fact(REVENUE, A)), ("category", "A2", fact(REVENUE, B))], {"A": "A2"})
        self.assertNotIn("listed_category", found["A"])
        self.assertEqual(found["A"]["result"], "consistent")

    def test_renamed_category_unparseable_in_filing(self):
        found = review(published({"A": (60, A)}), [("category", "B", fact(REVENUE, B))], {"A": "A2"}, unparseable=("A2",))
        self.assertEqual((found["A"]["listed_category"], found["A"]["result"]), ("A2", "unparseable"))
        self.assertIn("前綴宣告衝突", found["A"]["note"])

    def test_listed_name_found_later_in_chain_beats_missing_name(self):
        # 鏈上 A2 記為找不到，A3 有列出：取 A3。
        def compose_missing_a2(filing, request):
            return find(filing, request, REVENUE, {"srt:ProductOrServiceAxis": "x:NoSuchMember"})

        found = review(
            published({"A": (60, A)}),
            [("category", "A2", compose_missing_a2), ("category", "A3", fact(REVENUE, A))],
            {"A": "A2", "A2": "A3"},
        )
        self.assertEqual((found["A"]["listed_category"], found["A"]["result"]), ("A3", "consistent"))

    def test_reconciling_item_follows_mapping(self):
        found = review(published({"A": (60, A)}, {"R": (40, B)}), [("category", "A", fact(REVENUE, A)), ("reconciling", "R2", fact(REVENUE, B))], {"R": "R2"})
        self.assertEqual((found["R"]["listed_category"], found["R"]["result"]), ("R2", "consistent"))

    def test_two_old_names_on_one_new_name_are_unparseable(self):
        # {"C": ("A", "B")}：期別同時有 A 與 B，都對到 C；無法判斷 C 的列示值屬於哪一個。
        found = review(published({"A": (60, A), "B": (40, B)}), [("category", "C", fact(REVENUE, A))], {"A": "C", "B": "C"})
        for name in ("A", "B"):
            self.assertEqual((found[name]["listed_category"], found[name]["result"]), ("C", "unparseable"))
            self.assertIn("A、B 在新申報都對到 C", found[name]["note"])

    def test_old_and_new_name_in_same_period_are_unparseable(self):
        # 期別同時有 A 與 A2，A 改名為 A2：申報的 A2 對到兩個已上線分類。
        found = review(published({"A": (60, A), "A2": (40, B)}), [("category", "A2", fact(REVENUE, A))], {"A": "A2"})
        self.assertEqual((found["A"]["result"], found["A2"]["result"]), ("unparseable", "unparseable"))
        self.assertNotIn("listed_category", found["A2"])


class RenamedQ4BasisTest(Fixture):
    """Q4 口徑一致：年報以新名稱列示上一財年時，依對應與上一財年的舊名稱比對。"""

    PRIOR_10K = "0000000001-25-000000"
    ANNUAL_10K = "0000000001-26-000001"

    def year(self, listed, omit=()):
        """上一財年 10-K（A、B 各 100），與 standard_year 的財年；年報另列示上一財年的 A2（同一個成員）、B 與總營收。"""
        self.add(self.PRIOR_10K, "10-K", "2024-12-31", "2025-02-10", build_html(2024, "FY", [
            item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "100"),
            item("yb", REVENUE, B, "2024-01-01", "2024-12-31", "100"),
            item("yt", REVENUE, None, "2024-01-01", "2024-12-31", "200"),
        ]))
        self.standard_year()
        a, b = listed
        prior = [
            item("pa", REVENUE, A, "2024-01-01", "2024-12-31", str(a), 1),
            item("pb", REVENUE, B, "2024-01-01", "2024-12-31", str(b), 1),
            item("pt", REVENUE, None, "2024-01-01", "2024-12-31", str(a + b), 1),
        ]
        self.add(self.ANNUAL_10K, "10-K", "2025-12-31", "2026-02-15", build_html(2025, "FY", [
            item("ya", REVENUE, A, "2025-01-01", "2025-12-31", "300"),
            item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
            item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
        ] + [i for i in prior if i["id"] not in omit]))

    def q4(self, source):
        """執行全部期別，回傳 2025 Q4 的紀錄；這次執行的全部比對結果留在 `self.record`。"""
        parser = self.parser(source)
        self.record = recorded(parser)
        parser.run(parser.periods())
        return self.status()["periods"]["Q"]["2025-12-31"]

    def test_same_basis_through_mapping_derives_q4(self):
        self.year((100, 100))
        q4 = self.q4(MAPPED)
        record = self.record
        self.assertEqual(q4["status"], "published")
        self.assertNotIn("q4_basis", q4)
        # 年報對上一財年 FY 的比對：A 以年報的 A2 比對且一致。
        basis = [(c.get("listed_category"), c["result"]) for c in record
                 if c["series"] == "FY" and c["period_end"] == "2024-12-31" and c["role"] == "annual" and c["category"] == "A"]
        self.assertIn(("A2", "consistent"), basis)

    def test_renamed_category_takes_part_in_basis(self):
        self.year((110, 90))
        q4 = self.q4(MAPPED)
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual(
            [(c["category"], c.get("listed_category"), c["previous_value"], c["listed_value"]) for c in q4["basis_changes"]],
            [("A", "A2", 100_000_000, 110_000_000), ("B", None, 100_000_000, 90_000_000)],
        )
        self.assertIn("A（年報稱 A2） 已上線 FY 100000000、年報 110000000", q4["reason"])

    def test_without_mapping_renamed_category_is_left_out_of_basis(self):
        self.year((110, 90))
        q4 = self.q4(UNMAPPED)
        self.assertEqual(q4["status"], "not_derived")
        self.assertEqual([c["category"] for c in q4["basis_changes"]], ["B"])

    def test_renamed_category_not_listed_is_undetermined(self):
        # 年報沒有列示上一財年的 A2：對應的分類無法比較，口徑無法判斷，Q4 照常推算並註記。
        self.year((100, 100), omit=("pa",))
        q4 = self.q4(MAPPED)
        self.assertEqual(q4["status"], "published")
        self.assertEqual(q4["q4_basis"]["result"], "undetermined")
        self.assertIn("A（年報稱 A2）：not_found", q4["q4_basis"]["reason"])

    def test_two_old_names_on_one_new_name_is_undetermined(self):
        # 2025 年起 A、B 只列一類 C（兩個成員相加），宣告 {"C": ("A", "B")}：上一財年的 A、B 都對到年報的 C，
        # 無法判斷口徑，Q4 照常推算並註記，而不是因 C 與 A 不同而不推算。
        source = company(
            categories=(
                ("A", fact(REVENUE, A), until("2024-12-31")),
                ("B", fact(REVENUE, B), until("2024-12-31")),
                ("C", (fact(REVENUE, A), fact(REVENUE, B)), since(RENAMED_FROM)),
            ),
            FORMER_NAMES={"C": ("A", "B")},
        )
        self.year((100, 100))
        q4 = self.q4(source)
        self.assertEqual(q4["status"], "published")
        self.assertEqual(q4["q4_basis"]["result"], "undetermined")
        self.assertIn("A（年報稱 C）：unparseable", q4["q4_basis"]["reason"])
        self.assertIn("都對到 C", q4["q4_basis"]["reason"])


if __name__ == "__main__":
    unittest.main()
