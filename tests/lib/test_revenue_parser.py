"""新版 parser 引擎：以合成的 inline XBRL 申報測試每個流程步驟與每項檢核，不連網、不啟動 Chromium。"""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue import companies  # noqa: E402
from sec_revenue.engines import JsonCodec  # noqa: E402
from sec_revenue.evidence import TableLocator  # noqa: E402
from sec_revenue.revenue.compose import PeriodComposer  # noqa: E402
from sec_revenue.revenue.engine import RevenueParser, check_outputs, ticker_dir  # noqa: E402
from sec_revenue.revenue.filings import FilingSet, ParseError  # noqa: E402
from sec_revenue.revenue.review import comparatives  # noqa: E402
from sec_revenue.revenue.spec import (  # noqa: E402
    Category,
    CompanySpec,
    define,
    effective,
    fact,
    Addend,
    minus,
    one_of,
    sum_of,
    table_cell,
)
from sec_revenue.revenue.xbrl import InlineDocument, classify_duration  # noqa: E402

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
AXIS = "srt:ProductOrServiceAxis"
A = {AXIS: "x:AMember"}
B = {AXIS: "x:BMember"}
SPEC = CompanySpec(
    ticker="TEST",
    view="product",
    categories=(Category("A", fact(REVENUE, A)), Category("B", fact(REVENUE, B))),
    total=Category("Total", fact(REVENUE)),
)

# 一個財年：Q1–Q3 是 10-Q，FY 是 10-K；值以百萬美元表示。
QUARTERS = {
    "2025-03-31": ("Q1", "2025-01-01"),
    "2025-06-30": ("Q2", "2025-04-01"),
    "2025-09-30": ("Q3", "2025-07-01"),
}


def item(fid, concept, dims, start, end, raw, table=0, unit="usd", decimals="-6", scale="6", fmt="ixt:num-dot-decimal", sign=None):
    return dict(
        id=fid, concept=concept, dims=dims or {}, start=start, end=end, raw=raw, table=table,
        unit=unit, decimals=decimals, scale=scale, fmt=fmt, sign=sign,
    )


NAMESPACES = {
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
    "iso4217": "http://www.xbrl.org/2003/iso4217",
    "dei": "http://xbrl.sec.gov/dei/2025",
    "us-gaap": "http://fasb.org/us-gaap/2025",
    "srt": "http://fasb.org/srt/2025",
    "x": "http://example.com/20251231",
}


def build_html(fiscal_year, focus, items: list[dict], namespaces=None) -> bytes:
    contexts, units, tables, loose = [], [], {}, []
    for f in items:
        members = "".join(
            f'<xbrldi:explicitMember dimension="{axis}">{member}</xbrldi:explicitMember>'
            for axis, member in f["dims"].items()
        )
        segment = f"<xbrli:segment>{members}</xbrli:segment>" if members else ""
        contexts.append(
            f'<xbrli:context id="c-{f["id"]}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier>{segment}</xbrli:entity>'
            f'<xbrli:period><xbrli:startDate>{f["start"]}</xbrli:startDate><xbrli:endDate>{f["end"]}</xbrli:endDate></xbrli:period></xbrli:context>'
        )
        attrs = f' sign="{f["sign"]}"' if f["sign"] else ""
        decimals = f' decimals="{f["decimals"]}"' if f["decimals"] is not None else ""
        tag = (
            f'<ix:nonFraction id="{f["id"]}" name="{f["concept"]}" contextRef="c-{f["id"]}" unitRef="{f["unit"]}" '
            f'scale="{f["scale"]}" format="{f["fmt"]}"{decimals}{attrs}>{f["raw"]}</ix:nonFraction>'
        )
        label = f"{f['concept'].split(':')[-1]} {' '.join(f['dims'].values())} {f['start']}~{f['end']}"
        if f["table"] is None:
            loose.append(f"<p>{label} {tag}</p>")
        else:
            tables.setdefault(f["table"], []).append(f"<tr><td>{label}</td><td>{tag}</td></tr>")
    units = (
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        '<xbrli:unit id="eur"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>'
    )
    dei = "".join(
        f'<ix:nonNumeric name="{name}" contextRef="c-dei">{value}</ix:nonNumeric>'
        for name, value in (("dei:DocumentFiscalYearFocus", fiscal_year), ("dei:DocumentFiscalPeriodFocus", focus))
        if value is not None
    )
    body = "".join(f"<table>{''.join(rows)}</table>" for _, rows in sorted(tables.items()))
    return (
        f"<html {' '.join(f'xmlns:{p}=\"{u}\"' for p, u in (namespaces or NAMESPACES).items())}><head><title>t</title></head><body>"
        f'<div style="display:none"><ix:header><ix:resources>{"".join(contexts)}{units}</ix:resources></ix:header></div>'
        f"<div>{dei}</div>{body}{''.join(loose)}</body></html>"
    ).encode()


def quarter_items(end, values, prefix="q", table=0, start=None):
    focus, quarter_start = QUARTERS[end]
    start = start or quarter_start
    a, b = values
    items = [
        item(f"{prefix}a", REVENUE, A, start, end, str(a), table),
        item(f"{prefix}b", REVENUE, B, start, end, str(b), table),
        item(f"{prefix}t", REVENUE, None, start, end, str(a + b), table),
    ]
    return items


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / "sec-data"
        self.out = Path(self.temp.name) / "revenue"
        self.packages = {}
        self.shots = []

    def tearDown(self):
        self.temp.cleanup()

    def add(self, accession, form, report, filed, html: bytes, ticker="TEST"):
        digest = hashlib.sha256(html).hexdigest()
        relative = f"sec/{ticker}/{report}/{accession}/{digest}.html"
        (self.data / relative).parent.mkdir(parents=True, exist_ok=True)
        (self.data / relative).write_bytes(html)
        name = f"test-{report}.htm"
        self.packages[accession] = {
            "complete": True,
            "filing": {"accessionNumber": accession, "form": form, "reportDate": report, "filingDate": filed},
            "documents": {
                name: {
                    "name": name,
                    "path": relative,
                    "sha256": digest,
                    "primary": True,
                    "inline_xbrl": True,
                    "source_url": f"https://www.sec.gov/Archives/edgar/data/1/{accession.replace('-', '')}/{name}",
                    "ixviewer_url": f"https://www.sec.gov/ix?doc=/Archives/edgar/data/1/{accession.replace('-', '')}/{name}",
                }
            },
        }
        JsonCodec.write(self.data / "pipeline" / ticker / "packages.json", {"packages": self.packages})

    def standard_year(self, values=None):
        """Q1–Q3 10-Q 與 FY 10-K；FY 年度 = Q1+Q2+Q3+Q4。"""
        values = values or {"2025-03-31": (60, 40), "2025-06-30": (70, 30), "2025-09-30": (80, 20)}
        nine = [sum(v[i] for v in values.values()) for i in (0, 1)]
        for n, (end, pair) in enumerate(values.items(), 1):
            focus = QUARTERS[end][0]
            items = quarter_items(end, pair)
            if focus == "Q3":
                items += [
                    item("na", REVENUE, A, "2025-01-01", end, str(nine[0]), 1),
                    item("nb", REVENUE, B, "2025-01-01", end, str(nine[1]), 1),
                    item("nt", REVENUE, None, "2025-01-01", end, str(sum(nine)), 1),
                ]
            self.add(f"0000000001-25-00000{n}", "10-Q", end, f"2025-{int(end[5:7]) + 1:02d}-15", build_html(2025, focus, items))
        annual = [nine[0] + 90, nine[1] + 10]
        self.add(
            "0000000001-26-000001",
            "10-K",
            "2025-12-31",
            "2026-02-15",
            build_html(
                2025,
                "FY",
                [
                    item("ya", REVENUE, A, "2025-01-01", "2025-12-31", str(annual[0])),
                    item("yb", REVENUE, B, "2025-01-01", "2025-12-31", str(annual[1])),
                    item("yt", REVENUE, None, "2025-01-01", "2025-12-31", str(sum(annual))),
                ],
            ),
        )

    def composer(self, spec=SPEC):
        return PeriodComposer(spec, FilingSet(self.data, "TEST"))

    def parser(self, spec=SPEC, **options):
        return RevenueParser(self.data, self.out, spec, "spec-sha", screenshotter=lambda: FakeShooter(self), **options)

    def output(self, period, series="Q"):
        return JsonCodec.read(ticker_dir(self.out, "TEST") / series / period / "revenue.json")

    def status(self):
        return JsonCodec.read(ticker_dir(self.out, "TEST") / "status.json")


class FakeShooter:
    """以 lxml 的表格文字模擬瀏覽器，記錄截圖次數。"""

    def __init__(self, fixture):
        self.fixture = fixture

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def capture(self, raw, items):
        self.fixture.shots.append([i["id"] for i in items])
        locator = TableLocator(raw)
        index = locator.locate(items[0]["id"])[1]
        return b"\x89PNG" + json.dumps([i["id"] for i in items]).encode(), False, locator.table_text(index)


class FilingSelectionTest(Fixture):
    def test_first_original_filing_is_primary(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.add("0000000001-25-000009", "10-Q", "2025-03-31", "2025-05-01", build_html(2025, "Q1", quarter_items("2025-03-31", (61, 40))))
        result = self.composer().compose("2025-03-31")
        self.assertEqual(result.primary.accession, "0000000001-25-000001")

    def test_amendment_never_replaces_primary(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.add("0000000001-25-000003", "10-Q/A", "2025-03-31", "2025-05-20", build_html(2025, "Q1", quarter_items("2025-03-31", (65, 40))))
        result = self.composer().compose("2025-03-31")
        self.assertEqual(result.primary.accession, "0000000001-25-000001")
        self.assertEqual(next(l.value for l in result.lines if l.name == "A"), 60_000_000)
        # 修正申報的本期欄與已上線數字不同：寫成差異標記，已上線數字不改。
        self.parser().run(["2025-03-31"])
        markers = self.status()["periods"]["Q"]["2025-03-31"]["differences"]
        self.assertEqual(
            [(m["category"], m["published_value"], m["listed_value"], m["source"]["form"]) for m in markers],
            [("A", 60_000_000, 65_000_000, "10-Q/A"), ("總營收", 100_000_000, 105_000_000, "10-Q/A")],
        )
        self.assertEqual(self.output("2025-03-31")["categories"]["A"]["value"], 60_000_000)

    def test_missing_filing_and_source(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        with self.assertRaisesRegex(ParseError, r"\[選申報\]"):
            self.composer().compose("2025-06-30")
        path = next((self.data / "sec").rglob("*.html"))
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ParseError, r"\[原文存在\].*sha256"):
            self.composer().compose("2025-03-31")

    def test_missing_packages_asks_for_download(self):
        with self.assertRaisesRegex(ValueError, "請先執行 download"):
            FilingSet(self.data, "TEST")


class FactTest(Fixture):
    def compose_q1(self, items, focus="Q1", year=2025):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(year, focus, items))
        return self.composer().compose("2025-03-31")

    def test_duration_classification(self):
        self.assertEqual(classify_duration("2025-01-01", "2025-03-31"), "quarter")
        self.assertEqual(classify_duration("2025-01-01", "2025-06-30"), "six_months")
        self.assertEqual(classify_duration("2025-01-01", "2025-09-30"), "nine_months")
        self.assertEqual(classify_duration("2025-01-01", "2025-12-31"), "annual")
        self.assertIsNone(classify_duration("2025-01-01", "2025-02-28"))
        self.assertIsNone(classify_duration(None, "2025-02-28"))

    def test_quarter_uses_three_month_fact_and_ignores_cumulative(self):
        items = quarter_items("2025-06-30", (70, 30)) + [
            item("ha", REVENUE, A, "2025-01-01", "2025-06-30", "130", 1),
            item("hb", REVENUE, B, "2025-01-01", "2025-06-30", "70", 1),
            item("ht", REVENUE, None, "2025-01-01", "2025-06-30", "200", 1),
        ]
        self.add("0000000001-25-000002", "10-Q", "2025-06-30", "2025-07-15", build_html(2025, "Q2", items))
        result = self.composer().compose("2025-06-30")
        self.assertEqual({l.name: l.value for l in result.lines}, {"A": 70_000_000, "B": 30_000_000, "Total": 100_000_000})
        self.assertEqual((result.fiscal_year, result.fiscal_quarter), (2025, 2))

    def test_dimensions_must_match_exactly(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0]["dims"] = {**A, "srt:StatementGeographicalAxis": "country:US"}
        with self.assertRaisesRegex(ParseError, r"\[fact 存在且唯一\] 找不到 A"):
            self.compose_q1(items)

    def test_duplicates_must_agree_and_prefer_shared_table(self):
        items = quarter_items("2025-03-31", (60, 40), table=1) + [item("dup-t", REVENUE, None, "2025-01-01", "2025-03-31", "100", 0)]
        result = self.compose_q1(items)
        total = next(l for l in result.lines if l.name == "Total").terms[0].operand
        # 損益表（表 0）的總營收在文件中較早出現，但表 1 含其他分類，因此選表 1。
        self.assertEqual(total.fact.fact_id, "qt")
        self.assertEqual([d.fact_id for d in total.duplicates], ["dup-t"])

    def test_inconsistent_duplicates_fail(self):
        items = quarter_items("2025-03-31", (60, 40)) + [item("dup-a", REVENUE, A, "2025-01-01", "2025-03-31", "61", 1)]
        with self.assertRaisesRegex(ParseError, "重複 fact 的數值不一致"):
            self.compose_q1(items)

    def test_unit_decimals_and_format_checks(self):
        cases = [
            (dict(unit="eur"), r"\[單位與精度\].*不是 USD"),
            (dict(decimals=None), r"\[單位與精度\].*沒有 decimals"),
            (dict(fmt="ixt:num-comma-decimal"), r"不支援的數字格式"),
        ]
        for change, pattern in cases:
            with self.subTest(change):
                items = quarter_items("2025-03-31", (60, 40))
                items[0].update(change)
                with self.assertRaisesRegex(ParseError, pattern):
                    self.compose_q1(items)

    def test_sign_and_scale_produce_value(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[1].update(raw="5", scale="3", sign="-", decimals="-3")
        items[2].update(raw="59.995", decimals="-3")
        result = self.compose_q1(items)
        self.assertEqual(next(l.value for l in result.lines if l.name == "B"), -5000)

    def test_fiscal_declaration_required_and_must_match_form(self):
        with self.assertRaisesRegex(ParseError, r"\[財年與季別\]"):
            self.compose_q1(quarter_items("2025-03-31", (60, 40)), focus=None)
        with self.assertRaisesRegex(ParseError, r"\[財年與季別\].*FY"):
            self.compose_q1(quarter_items("2025-03-31", (60, 40)), focus="FY")


class DefinitionAndSumTest(Fixture):
    def setUp(self):
        super().setUp()
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))

    def spec(self, **changes):
        base = dict(ticker="TEST", view="product", categories=SPEC.categories, total=SPEC.total)
        base.update(changes)
        return CompanySpec(**base)

    def test_effective_definitions_select_at_most_one(self):
        overlapping = self.spec(
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-12-31")), define(fact("us-gaap:Revenues", A), effective("2025-01-01"))),
                SPEC.categories[1],
            )
        )
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\] A 在 2025-03-31 有 2 個"):
            self.composer(overlapping).compose("2025-03-31")
        switched = self.spec(
            categories=(
                Category("A", define(fact("us-gaap:Revenues", A), effective(None, "2024-12-31")), define(fact(REVENUE, A), effective("2025-01-01"))),
                SPEC.categories[1],
            )
        )
        self.assertEqual(next(l.value for l in self.composer(switched).compose("2025-03-31").lines if l.name == "A"), 60_000_000)

    def test_category_without_definition_is_not_listed(self):
        later = Category("C", define(fact(REVENUE, {AXIS: "x:CMember"}), effective("2026-01-01")))
        result = self.composer(self.spec(categories=SPEC.categories + (later,))).compose("2025-03-31")
        self.assertEqual([l.name for l in result.lines], ["A", "B", "Total"])

    def test_missing_effective_fails_sum_instead_of_dropping_category(self):
        # 規格漏寫 B 在 Q1 的適用期間：該期沒有 B，加總對不上而失敗，不會無聲少一個分類。
        omitted = Category("B", define(fact(REVENUE, B), effective("2025-04-01")))
        with self.assertRaisesRegex(ParseError, r"\[加總\] 分類加總 60000000 與總營收 100000000"):
            self.composer(self.spec(categories=(SPEC.categories[0], omitted))).compose("2025-03-31")
        # 調節項是指定的 fact，不會吸收漏掉的分類。
        items = quarter_items("2025-03-31", (60, 45))
        items[2]["raw"] = "100"
        items.append(item("qe", REVENUE, {AXIS: "x:EliminationMember"}, "2025-01-01", "2025-03-31", "5", sign="-"))
        self.packages.pop("0000000001-25-000001")
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        eliminations = (Category("Eliminations", fact(REVENUE, {AXIS: "x:EliminationMember"})),)
        self.assertEqual(self.composer(self.spec(reconciling=eliminations)).compose("2025-03-31").sum_check["difference"], 0)
        with self.assertRaisesRegex(ParseError, r"\[加總\] 分類加總 55000000 與總營收 100000000"):
            self.composer(self.spec(categories=(SPEC.categories[0], omitted), reconciling=eliminations)).compose("2025-03-31")

    def test_total_must_have_definition(self):
        spec = self.spec(total=Category("Total", define(fact(REVENUE), effective("2026-01-01"))))
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\] 總營收 Total 在 2025-03-31 沒有生效的定義"):
            self.composer(spec).compose("2025-03-31")

    def test_table_cell_is_declared_but_not_supported(self):
        spec = self.spec(categories=(Category("A", table_cell("ex99.htm", "Net sales", "A", "Q1")), SPEC.categories[1]))
        with self.assertRaisesRegex(ParseError, "table_cell 運算元尚未支援"):
            self.composer(spec).compose("2025-03-31")

    def test_sum_must_match_total_within_precision(self):
        result = self.composer().compose("2025-03-31")
        self.assertEqual(result.sum_check, {"categories": 100_000_000, "total": 100_000_000, "difference": 0, "tolerance": "1500000"})
        only_a = self.spec(categories=(SPEC.categories[0],))
        with self.assertRaisesRegex(ParseError, r"\[加總\] 分類加總 60000000 與總營收 100000000"):
            self.composer(only_a).compose("2025-03-31")

    def test_reconciling_items_take_part_in_sum(self):
        spec = self.spec(categories=(SPEC.categories[0],), reconciling=(Category("Other", fact(REVENUE, B)),))
        result = self.composer(spec).compose("2025-03-31")
        self.assertEqual(result.sum_check["difference"], 0)

    def test_duplicate_category_names_rejected(self):
        with self.assertRaisesRegex(ValueError, "重複"):
            self.spec(categories=(SPEC.categories[0], SPEC.categories[0]))


class FourthQuarterTest(Fixture):
    def test_q4_is_annual_minus_nine_months(self):
        self.standard_year()
        result = self.composer().compose("2025-12-31")
        self.assertEqual((result.series, result.fiscal_quarter), ("Q", 4))
        self.assertEqual(result.nine_month_filing.report_date, "2025-09-30")
        a = next(l for l in result.lines if l.name == "A")
        self.assertEqual(a.value, 90_000_000)
        self.assertEqual([(t.weight, t.operand.role) for t in a.terms], [(1, "annual"), (-1, "nine_months")])

    def test_fy_uses_annual_facts(self):
        self.standard_year()
        result = self.composer().compose_annual("2025-12-31")
        self.assertEqual((result.series, result.fiscal_year, result.fiscal_quarter), ("FY", 2025, None))
        self.assertEqual({l.name: [(t.weight, t.operand.role) for t in l.terms] for l in result.lines}, dict.fromkeys(["A", "B", "Total"], [(1, "annual")]))
        self.assertEqual({l.name: l.value for l in result.lines}, {"A": 300_000_000, "B": 100_000_000, "Total": 400_000_000})
        with self.assertRaisesRegex(ParseError, r"\[財年與季別\].*FY 序列只取 10-K"):
            self.composer().compose_annual("2025-09-30")

    def renamed_annual(self, member):
        self.standard_year()
        self.packages.pop("0000000001-26-000001")
        annual = [
            item("ya", REVENUE, {AXIS: member}, "2025-01-01", "2025-12-31", "300"),
            item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
            item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
        ]
        self.add("0000000001-26-000001", "10-K", "2025-12-31", "2026-02-15", build_html(2025, "FY", annual))

    def test_q4_operands_use_definition_of_their_source_filing(self):
        # 10-K 起改用新成員，同財年 Q3 10-Q 仍是舊成員：同一個分類，Q4 照常推算，年度用新定義、九個月用舊定義。
        self.renamed_annual("x:ANewMember")
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-09-30")), define(fact(REVENUE, {AXIS: "x:ANewMember"}), effective("2025-12-31"))),
                SPEC.categories[1],
            ),
            total=SPEC.total,
        )
        a = next(l for l in self.composer(spec).compose("2025-12-31").lines if l.name == "A")
        self.assertEqual([(t.weight, t.operand.fact.fact_id) for t in a.terms], [(1, "ya"), (-1, "na")])
        self.assertEqual(a.value, 90_000_000)

    def test_q4_not_derived_when_annual_categories_differ(self):
        # 10-K 把 A 換成另一個分類 A2：FY 照列 A2，Q4 不推算，status.json 記錄原因與兩邊的分類。
        self.renamed_annual("x:A2Member")
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-09-30"))),
                SPEC.categories[1],
                Category("A2", define(fact(REVENUE, {AXIS: "x:A2Member"}), effective("2025-12-31"))),
            ),
            total=SPEC.total,
        )
        parser = self.parser(spec)
        report = parser.run(parser.periods())
        self.assertTrue(report["complete"])
        status = self.status()["periods"]
        entry = status["Q"]["2025-12-31"]
        self.assertEqual((entry["status"], entry["check"], entry["published_output_kept"]), ("not_derived", "Q4 推算條件", False))
        self.assertEqual((entry["fiscal_year"], entry["fiscal_quarter"]), (2025, 4))
        self.assertEqual(entry["fy_categories"], ["B", "A2"])
        self.assertEqual(entry["quarter_categories"], [{"start": "2025-01-01", "end": "2025-09-30", "categories": ["A", "B"]}])
        self.assertFalse((ticker_dir(self.out, "TEST") / "Q" / "2025-12-31").exists())
        self.assertEqual(status["FY"]["2025-12-31"]["status"], "published")
        self.assertEqual(sorted(self.output("2025-12-31", "FY")["categories"]), ["A2", "B"])
        self.assertEqual(sorted(self.output("2025-09-30")["categories"]), ["A", "B"])

    def test_q4_nine_months_come_from_original_third_quarter(self):
        self.standard_year()
        nine = quarter_items("2025-09-30", (80, 20)) + [
            item("na", REVENUE, A, "2025-01-01", "2025-09-30", "200", 1),
            item("nb", REVENUE, B, "2025-01-01", "2025-09-30", "100", 1),
            item("nt", REVENUE, None, "2025-01-01", "2025-09-30", "300", 1),
        ]
        # Q3 的修正申報不論在 10-K 之前或之後申報，都不取代原 Q3。
        for accession, filed in (("0000000001-26-000004", "2026-01-10"), ("0000000001-26-000005", "2026-03-01")):
            self.add(accession, "10-Q/A", "2025-09-30", filed, build_html(2025, "Q3", nine))
            result = self.composer().compose("2025-12-31")
            self.assertEqual(result.nine_month_filing.accession, "0000000001-25-000003")
            self.assertEqual(next(l.value for l in result.lines if l.name == "A"), 90_000_000)
            self.packages.pop(accession)

    def test_q4_fails_when_fy_or_a_quarter_fails(self):
        # 規格漏寫 B 在 FY 的適用期間：FY 加總失敗，Q4 也失敗並指向 FY，不是 not_derived。
        self.standard_year()
        omitted = Category("B", define(fact(REVENUE, B), effective(None, "2025-09-30")))
        spec = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0], omitted), total=SPEC.total)
        parser = self.parser(spec)
        parser.run(parser.periods())
        status = self.status()["periods"]
        self.assertEqual((status["FY"]["2025-12-31"]["status"], status["FY"]["2025-12-31"]["check"]), ("failed", "加總"))
        q4 = status["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("failed", "加總"))
        self.assertTrue(q4["reason"].startswith("Q4 依據的 FY 2025-12-31 不通過：分類加總"), q4["reason"])
        # Q2 失敗時，Q4 指向 Q2。
        late = Category("B", define(fact(REVENUE, B), effective(None, "2025-03-31")), define(fact(REVENUE, B), effective("2025-07-01")))
        spec = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0], late), total=SPEC.total)
        with self.assertRaisesRegex(ParseError, r"\[加總\] Q4 依據的 Q 2025-06-30 不通過"):
            self.composer(spec).compose("2025-12-31")

    def test_not_derived_keeps_published_q4_and_says_so(self):
        self.renamed_annual("x:AMember")
        parser = self.parser()
        parser.run(parser.periods())
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-09-30"))),
                SPEC.categories[1],
                Category("A2", define(fact(REVENUE, A), effective("2025-12-31"))),
            ),
            total=SPEC.total,
        )
        self.parser(spec).run(["2025-12-31"])
        entry = self.status()["periods"]["Q"]["2025-12-31"]
        self.assertEqual((entry["status"], entry["published_output_kept"]), ("not_derived", True))
        self.assertEqual(entry["published_output"]["categories"], {"A": 90_000_000, "B": 10_000_000})
        self.assertIn("已上線輸出保留不動", entry["published_output"]["note"])
        self.assertTrue((ticker_dir(self.out, "TEST") / "Q" / "2025-12-31" / "revenue.json").exists())

    def test_q4_requires_contiguous_periods(self):
        self.standard_year()
        html = build_html(
            2025,
            "Q3",
            quarter_items("2025-09-30", (80, 20))
            + [
                item("na", REVENUE, A, "2025-01-02", "2025-09-30", "210", 1),
                item("nb", REVENUE, B, "2025-01-02", "2025-09-30", "90", 1),
                item("nt", REVENUE, None, "2025-01-02", "2025-09-30", "300", 1),
            ],
        )
        self.packages.pop("0000000001-25-000003")
        self.add("0000000001-25-000003", "10-Q", "2025-09-30", "2025-10-15", html)
        with self.assertRaisesRegex(ParseError, r"找不到 A.*nine_months"):
            self.composer().compose("2025-12-31")

    def test_q4_requires_third_quarter_of_same_fiscal_year(self):
        self.standard_year()
        self.packages.pop("0000000001-25-000003")
        JsonCodec.write(self.data / "pipeline/TEST/packages.json", {"packages": self.packages})
        with self.assertRaisesRegex(ParseError, r"\[Q4 期間\] 2025-12-31 前一季應剛好有一個 10-Q 期別"):
            self.composer().compose("2025-12-31")


class ComparisonBoundTest(unittest.TestCase):
    def test_bound_is_coarser_of_declared_and_displayed_precision(self):
        from sec_revenue.revenue.xbrl import comparison_bound
        from decimal import Decimal

        self.assertEqual(comparison_bound("-5", "15,437", "6"), Decimal(500_000))
        self.assertEqual(comparison_bound("-5", "15,436.5", "6"), Decimal(50_000))
        self.assertEqual(comparison_bound("-6", "15,436.5", "6"), Decimal(500_000))
        self.assertEqual(comparison_bound("-3", "1,234", "3"), Decimal(500))
        self.assertEqual(comparison_bound("INF", "12", "0"), Decimal("0.5"))
        self.assertEqual(comparison_bound("-6", "—", "6"), Decimal(500_000))
        self.assertIsNone(comparison_bound(None, "15", "6"))


class Q4BasisTest(Fixture):
    """Q4 口徑一致：年報列示的上一財年數字與上一財年先前申報的值比對。"""

    PRIOR_10K = "0000000001-25-000000"
    ANNUAL_10K = "0000000001-26-000001"

    def prior_report(self, values=(100, 100)):
        a, b = values
        self.add(
            self.PRIOR_10K, "10-K", "2024-12-31", "2025-02-10",
            build_html(2024, "FY", [
                item("ya", REVENUE, A, "2024-01-01", "2024-12-31", str(a)),
                item("yb", REVENUE, B, "2024-01-01", "2024-12-31", str(b)),
                item("yt", REVENUE, None, "2024-01-01", "2024-12-31", str(a + b)),
            ]),
        )

    def annual_report(self, listed, total=None, omit=()):
        """standard_year 的 10-K（年度 A 300、B 100），另列示上一財年的 A、B 與總營收（預設為 A + B）；`omit` 的分類不列示。"""
        self.standard_year()
        a, b = listed
        prior = [
            item("pa", REVENUE, A, "2024-01-01", "2024-12-31", str(a), 1),
            item("pb", REVENUE, B, "2024-01-01", "2024-12-31", str(b), 1),
            item("pt", REVENUE, None, "2024-01-01", "2024-12-31", str(total if total is not None else a + b), 1),
        ]
        self.add(
            self.ANNUAL_10K, "10-K", "2025-12-31", "2026-02-15",
            build_html(2025, "FY", [
                item("ya", REVENUE, A, "2025-01-01", "2025-12-31", "300"),
                item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
                item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
            ] + [i for i in prior if i["id"][1:].upper() not in omit]),
        )

    def run_all(self, **options):
        parser = self.parser(**options)
        parser.run(parser.periods())
        return self.status()["periods"]

    def test_same_basis_derives_q4(self):
        self.prior_report()
        self.annual_report((100, 100))
        status = self.run_all()
        self.assertEqual(status["FY"]["2024-12-31"]["status"], "published")
        q4 = status["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertNotIn("q4_basis", q4)

    def test_reclassified_prior_year_leaves_q4_blank(self):
        # 年報把上一財年 A、B 之間重分類（總營收相同）：Q4 不推算，FY 照常上線。
        self.prior_report()
        self.annual_report((110, 90))
        status = self.run_all()
        q4 = status["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"], q4["published_output_kept"]), ("not_derived", "Q4 口徑一致", False))
        self.assertEqual((q4["fiscal_year"], q4["fiscal_quarter"]), (2025, 4))
        self.assertEqual(
            [(c["category"], c["previous_value"], c["listed_value"]) for c in q4["basis_changes"]],
            [("A", 100_000_000, 110_000_000), ("B", 100_000_000, 90_000_000)],
        )
        change = q4["basis_changes"][0]
        self.assertEqual(change["previous"], {"basis": "published", "accession": self.PRIOR_10K})
        self.assertEqual(change["listed"], {"accession": self.ANNUAL_10K})
        self.assertEqual(change["period"], {"start": "2024-01-01", "end": "2024-12-31"})
        self.assertEqual([a["fact_id"] for a in change["listed_addends"]], ["pa"])
        self.assertEqual([a["operand"] for a in change["previous_addends"]], ["op1"])
        for text in ("A 已上線 FY 100000000、年報 110000000", self.PRIOR_10K, self.ANNUAL_10K):
            self.assertIn(text, q4["reason"])
        self.assertFalse((ticker_dir(self.out, "TEST") / "Q" / "2025-12-31").exists())
        self.assertEqual(status["FY"]["2025-12-31"]["status"], "published")
        # 上一財年的已上線 FY 也照比較欄規則得到差異標記。
        self.assertEqual([m["category"] for m in status["FY"]["2024-12-31"]["differences"]], ["A", "B"])

    def test_prior_year_before_start_uses_its_own_annual_report(self):
        # 上一財年在起始日之前、沒有上線：以上一份 10-K 本身依規格組出的值比對。
        self.prior_report()
        self.annual_report((110, 90))
        status = self.run_all(default_start="2025-01-01")
        self.assertNotIn("2024-12-31", status["FY"])
        q4 = status["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual(q4["basis_changes"][0]["previous"], {"basis": "filing", "accession": self.PRIOR_10K})
        # 上一份 10-K 依據沒有 revenue.json 可對應，previous_addends 列 fact_id。
        self.assertEqual(
            q4["basis_changes"][0]["previous_addends"],
            [{"fact_id": "ya", "concept": REVENUE, "dimensions": A, "weight": 1, "value": 100_000_000}],
        )
        self.assertIn("A 上一份年報 100000000、年報 110000000", q4["reason"])

    def test_prior_year_before_start_with_same_basis(self):
        self.prior_report()
        self.annual_report((100, 100))
        q4 = self.run_all(default_start="2025-01-01")["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertNotIn("q4_basis", q4)

    def test_undetermined_basis_derives_q4_with_note(self):
        # 沒有上一份 10-K：無法判斷，Q4 照常推算並註記。
        self.annual_report((110, 90))
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertEqual(q4["q4_basis"]["result"], "undetermined")
        self.assertIn("沒有已上線的 FY", q4["q4_basis"]["reason"])
        # 年報沒有列示上一財年：同樣無法判斷。
        self.prior_report()
        self.standard_year()
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertIn("沒有列示上一財年", q4["q4_basis"]["reason"])

    def test_prior_year_that_cannot_be_composed_is_undetermined(self):
        # 上一份 10-K 加總不通過（組不出年度值）：無法判斷，Q4 照常推算。
        self.add(
            self.PRIOR_10K, "10-K", "2024-12-31", "2025-02-10",
            build_html(2024, "FY", [
                item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "100"),
                item("yb", REVENUE, B, "2024-01-01", "2024-12-31", "100"),
                item("yt", REVENUE, None, "2024-01-01", "2024-12-31", "250"),
            ]),
        )
        self.annual_report((110, 90))
        q4 = self.run_all(default_start="2025-01-01")["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertIn("[加總]", q4["q4_basis"]["reason"])

    def test_unparseable_category_is_undetermined(self):
        self.prior_report()
        self.annual_report((100, 100))
        html = build_html(2025, "FY", [
            item("ya", REVENUE, A, "2025-01-01", "2025-12-31", "300"),
            item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
            item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
            item("pa", REVENUE, A, "2024-01-01", "2024-12-31", "100", 1),
            item("pa2", REVENUE, A, "2024-01-01", "2024-12-31", "120", 2),
            item("pb", REVENUE, B, "2024-01-01", "2024-12-31", "100", 1),
            item("pt", REVENUE, None, "2024-01-01", "2024-12-31", "200", 1),
        ])
        self.add(self.ANNUAL_10K, "10-K", "2025-12-31", "2026-02-15", html)
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual(q4["status"], "published")
        self.assertEqual(q4["q4_basis"]["result"], "undetermined")
        self.assertIn("A：unparseable", q4["q4_basis"]["reason"])

    def test_declared_precision_finer_than_display_is_not_a_change(self):
        # MCD 的形狀：上一份 10-K 顯示 15,436.5（百萬、decimals -5）；年報列示上一財年 15,437（百萬），卻宣告 decimals -5。
        # 年報的數字實際只到百萬位，差 50 萬在誤差內，不是口徑變更。
        self.add(
            self.PRIOR_10K, "10-K", "2024-12-31", "2025-02-10",
            build_html(2024, "FY", [
                item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "100.5", decimals="-5"),
                item("yb", REVENUE, B, "2024-01-01", "2024-12-31", "99.5", decimals="-5"),
                item("yt", REVENUE, None, "2024-01-01", "2024-12-31", "200"),
            ]),
        )
        self.standard_year()
        self.add(
            self.ANNUAL_10K, "10-K", "2025-12-31", "2026-02-15",
            build_html(2025, "FY", [
                item("ya", REVENUE, A, "2025-01-01", "2025-12-31", "300"),
                item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
                item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
                item("pa", REVENUE, A, "2024-01-01", "2024-12-31", "101", 1, decimals="-5"),
                item("pb", REVENUE, B, "2024-01-01", "2024-12-31", "99.5", 1, decimals="-5"),
                item("pt", REVENUE, None, "2024-01-01", "2024-12-31", "200", 1),
            ]),
        )
        for start in ("2025-01-01", None):
            options = {"default_start": start} if start else {}
            q4 = self.run_all(**options)["Q"]["2025-12-31"]
            self.assertEqual(q4["status"], "published", start)
            self.assertNotIn("q4_basis", q4)
        # 顯示精度與宣告相符（101.2，十萬位）而差 70 萬時才是不同。
        self.add(
            self.ANNUAL_10K, "10-K", "2025-12-31", "2026-02-15",
            build_html(2025, "FY", [
                item("ya", REVENUE, A, "2025-01-01", "2025-12-31", "300"),
                item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
                item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
                item("pa", REVENUE, A, "2024-01-01", "2024-12-31", "101.2", 1, decimals="-5"),
                item("pb", REVENUE, B, "2024-01-01", "2024-12-31", "98.8", 1, decimals="-5"),
                item("pt", REVENUE, None, "2024-01-01", "2024-12-31", "200", 1),
            ]),
        )
        shutil.rmtree(self.out)
        q4 = self.run_all(default_start="2025-01-01")["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], [c["category"] for c in q4["basis_changes"]]), ("not_derived", ["A", "B"]))

    def test_prior_report_filed_after_annual_report_is_not_used(self):
        # Point in time：上一財年的 10-K 晚於本年報才申報。它的 FY 照常上線，但本年報判斷時看不到，也不讀那份 10-K。
        self.add(
            self.PRIOR_10K, "10-K", "2024-12-31", "2026-03-01",
            build_html(2024, "FY", [
                item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "100"),
                item("yb", REVENUE, B, "2024-01-01", "2024-12-31", "100"),
                item("yt", REVENUE, None, "2024-01-01", "2024-12-31", "200"),
            ]),
        )
        self.annual_report((110, 90))
        status = self.run_all()
        self.assertEqual(status["FY"]["2024-12-31"]["status"], "published")
        q4 = status["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["q4_basis"]["result"]), ("published", "undetermined"))
        self.assertIn("已下載的申報中也沒有申報日不晚於 2026-02-15 的上一財年 10-K", q4["q4_basis"]["reason"])

    def test_only_total_differs(self):
        self.prior_report()
        self.annual_report((100, 100), total=210)
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual([(c["category"], c["previous_value"], c["listed_value"]) for c in q4["basis_changes"]], [("總營收", 200_000_000, 210_000_000)])

    def test_only_reconciling_item_differs(self):
        spec = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0],), reconciling=(SPEC.categories[1],), total=SPEC.total)
        self.prior_report()
        self.annual_report((100, 90), total=200)
        q4 = self.run_all(spec=spec)["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual([c["category"] for c in q4["basis_changes"]], ["B"])

    def test_difference_with_missing_category_is_not_derived(self):
        # A 不同、B 在年報沒有列示上一財年：有分類可判定不同，Q4 不推算，不因 B 找不到而降為無法判斷。
        self.prior_report()
        self.annual_report((110, 90), total=200, omit=("B",))
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual([c["category"] for c in q4["basis_changes"]], ["A"])

    def test_corrupted_prior_report_fails_q4(self):
        # 上一份 10-K 原文與申報包紀錄不符：資料不完整，Q4 失敗並指出那份 10-K，不照常推算。
        self.prior_report()
        self.annual_report((100, 100))
        (self.data / self.packages[self.PRIOR_10K]["documents"]["test-2024-12-31.htm"]["path"]).write_bytes(b"tampered")
        q4 = self.run_all(default_start="2025-01-01")["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("failed", "原文存在"))
        self.assertIn(f"上一財年 10-K {self.PRIOR_10K}", q4["reason"])

    def test_prior_year_of_52_53_week_fiscal_year(self):
        # 財年結束於 9 月最後一個週六：上一財年期末是本財年年度 fact 起日的前一天（2024-09-28），不是曆年。
        def year_items(prefix, start, end, values, table=0):
            a, b = values
            return [
                item(f"{prefix}a", REVENUE, A, start, end, str(a), table),
                item(f"{prefix}b", REVENUE, B, start, end, str(b), table),
                item(f"{prefix}t", REVENUE, None, start, end, str(a + b), table),
            ]

        self.add("0000000001-24-000009", "10-K", "2024-09-28", "2024-11-01", build_html(2024, "FY", year_items("y", "2023-10-01", "2024-09-28", (100, 100))))
        self.add("0000000001-25-000001", "10-Q", "2024-12-28", "2025-01-31", build_html(2025, "Q1", year_items("q", "2024-09-29", "2024-12-28", (60, 40))))
        self.add("0000000001-25-000002", "10-Q", "2025-03-29", "2025-05-01", build_html(2025, "Q2", year_items("q", "2024-12-29", "2025-03-29", (70, 30))))
        self.add(
            "0000000001-25-000003", "10-Q", "2025-06-28", "2025-08-01",
            build_html(2025, "Q3", year_items("q", "2025-03-30", "2025-06-28", (80, 20)) + year_items("n", "2024-09-29", "2025-06-28", (210, 90), 1)),
        )
        self.add(
            "0000000001-25-000004", "10-K", "2025-09-27", "2025-10-31",
            build_html(2025, "FY", year_items("y", "2024-09-29", "2025-09-27", (300, 100)) + year_items("p", "2023-10-01", "2024-09-28", (110, 90), 1)),
        )
        q4 = self.run_all(default_start="2024-12-01")["Q"]["2025-09-27"]
        self.assertEqual((q4["status"], q4["check"]), ("not_derived", "Q4 口徑一致"))
        self.assertEqual(q4["basis_changes"][0]["period"], {"start": "2023-10-01", "end": "2024-09-28"})
        self.assertEqual(q4["basis_changes"][0]["previous"], {"basis": "filing", "accession": "0000000001-24-000009"})

    def test_published_q4_is_kept_when_basis_change_is_found_later(self):
        # 先在沒有上一份 10-K 時上線 Q4；之後補下載上一份 10-K，發現口徑變更：已上線 Q4 保留不動。
        self.annual_report((110, 90))
        self.run_all()
        self.prior_report()
        q4 = self.run_all()["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"], q4["published_output_kept"]), ("not_derived", "Q4 口徑一致", True))
        self.assertEqual(q4["published_output"]["categories"], {"A": 90_000_000, "B": 10_000_000})
        self.assertTrue((ticker_dir(self.out, "TEST") / "Q" / "2025-12-31" / "revenue.json").exists())

class ParserOutputTest(Fixture):
    def test_publishes_outputs_with_evidence_and_status(self):
        self.standard_year()
        parser = self.parser()
        report = parser.run(parser.periods())
        self.assertTrue(report["complete"])
        output = self.output("2025-12-31")
        self.assertEqual(output["categories"]["A"]["value"], 90_000_000)
        self.assertEqual(output["categories"]["A"]["expression"], [{"operand": "op1", "weight": 1}, {"operand": "op2", "weight": -1}])
        op = output["operands"]["op1"]
        self.assertEqual((op["kind"], op["role"], op["form"], op["fact_id"]), ("xbrl_fact", "annual", "10-K", "ya"))
        self.assertTrue(op["document"]["ixviewer_url"].startswith("https://www.sec.gov/ix?doc="))
        self.assertEqual((output["series"], output["fiscal_quarter"]), ("Q", 4))
        annual = self.output("2025-12-31", "FY")
        self.assertEqual((annual["series"], annual["fiscal_year"], "fiscal_quarter" in annual), ("FY", 2025, False))
        self.assertEqual(annual["categories"]["A"], {"value": 300_000_000, "expression": [{"operand": "op1", "weight": 1}]})
        self.assertEqual(list(annual["filings"]), ["primary"])
        for series, result in (("Q", output), ("FY", annual)):
            directory = ticker_dir(self.out, "TEST") / series / "2025-12-31" / "evidence"
            for operand in result["operands"].values():
                evidence = operand["evidence"]
                page = (directory / f"{evidence['table']}.html").read_bytes()
                png = (directory / f"{evidence['table']}.png").read_bytes()
                self.assertEqual(hashlib.sha256(page).hexdigest(), evidence["html_sha256"])
                self.assertEqual(hashlib.sha256(png).hexdigest(), evidence["png_sha256"])
        self.assertIn({"check": "Q4 期間", "result": "pass"}, output["checks"]["structural"])
        self.assertNotIn({"check": "Q4 期間", "result": "pass"}, annual["checks"]["structural"])
        status = self.status()
        self.assertEqual({p: e["status"] for p, e in status["periods"]["Q"].items()}, dict.fromkeys(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"], "published"))
        self.assertEqual(status["periods"]["FY"], {"2025-12-31": {"status": "published", "fiscal_year": 2025, "accession": "0000000001-26-000001"}})
        self.assertEqual(status["parser"]["spec_sha256"], "spec-sha")
        for series in ("Q", "FY"):
            self.assertEqual([p.name for p in (ticker_dir(self.out, "TEST") / series).iterdir() if p.name.startswith(".")], [])

    def test_rerun_reuses_screenshots_and_is_byte_identical(self):
        self.standard_year()
        parser = self.parser()
        parser.run(parser.periods())
        before = {p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        shots = len(self.shots)
        parser = self.parser()
        parser.run(parser.periods())
        self.assertEqual(len(self.shots), shots)
        self.assertEqual({p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}, before)

    def test_operand_outside_table_fails_evidence_check(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0]["table"] = None
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        report = self.parser().run(["2025-03-31"])
        entry = self.status()["periods"]["Q"]["2025-03-31"]
        self.assertFalse(report["complete"])
        self.assertEqual((entry["status"], entry["check"]), ("failed", "證據完整"))
        self.assertFalse((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31").exists())

    def test_failed_rerun_keeps_published_output(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        published = (ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes()
        spec = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0],), total=SPEC.total)
        self.parser(spec).run(["2025-03-31"])
        entry = self.status()["periods"]["Q"]["2025-03-31"]
        self.assertEqual((entry["status"], entry["check"], entry["published_output_kept"]), ("failed", "加總", True))
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes(), published)

    def test_browser_table_mismatch_fails(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))

        class WrongTable(FakeShooter):
            def capture(self, raw, items):
                png, cropped, _ = super().capture(raw, items)
                return png, cropped, "other"

        parser = RevenueParser(self.data, self.out, SPEC, "spec-sha", screenshotter=lambda: WrongTable(self))
        parser.run(["2025-03-31"])
        self.assertIn("文字不同", self.status()["periods"]["Q"]["2025-03-31"]["reason"])

    def test_check_mode_compares_without_screenshots(self):
        self.standard_year()
        parser = self.parser()
        periods = parser.periods()
        parser.run(periods)
        shots = len(self.shots)
        self.assertEqual(check_outputs(self.data, self.out, SPEC, "spec-sha", periods)[1], [])
        self.assertEqual(len(self.shots), shots)
        # 規格或引擎 hash 不同而內容相同：一般 parse 不改動任何東西，--check 一致。
        self.assertEqual(check_outputs(self.data, self.out, SPEC, "other-spec-sha", periods)[1], [])
        committed = ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(committed)
        output["categories"]["A"]["value"] += 1
        JsonCodec.write(committed, output)
        png = next((ticker_dir(self.out, "TEST") / "Q" / "2025-06-30" / "evidence").glob("*.png"))
        png.write_bytes(b"tampered")
        found = check_outputs(self.data, self.out, SPEC, "spec-sha", periods)[1]
        self.assertTrue(any(d.startswith("Q 2025-03-31: status.differs_from_published") for d in found), found)
        self.assertTrue(any("2025-06-30" in d and "PNG" in d for d in found), found)


class ComparativeTest(Fixture):
    @staticmethod
    def items(year, values, q2=False, comparative=None):
        start, end = (f"{year}-04-01", f"{year}-06-30") if q2 else (f"{year}-01-01", f"{year}-03-31")
        a, b = values
        found = [
            item("a", REVENUE, A, start, end, str(a)),
            item("b", REVENUE, B, start, end, str(b)),
            item("t", REVENUE, None, start, end, str(a + b)),
        ]
        if comparative:
            prior = str(int(year) - 1)
            ca, cb = comparative
            found += [
                item("pa", REVENUE, A, f"{prior}-01-01", f"{prior}-03-31", str(ca), 1),
                item("pb", REVENUE, B, f"{prior}-01-01", f"{prior}-03-31", str(cb), 1),
                item("pt", REVENUE, None, f"{prior}-01-01", f"{prior}-03-31", str(ca + cb), 1),
            ]
        return found

    def test_difference_is_marked_on_old_period_and_output_kept(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add(
            "0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15",
            build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(62, 40))),
        )
        self.parser().run(["2024-03-31"])
        before = (ticker_dir(self.out, "TEST") / "Q" / "2024-03-31" / "revenue.json").read_bytes()
        self.parser().run(["2025-03-31"])
        self.assertNotIn("comparatives", self.output("2025-03-31")["checks"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2024-03-31" / "revenue.json").read_bytes(), before)
        markers = self.status()["periods"]["Q"]["2024-03-31"]["differences"]
        self.assertEqual(
            [(m["category"], m["published_value"], m["listed_value"], m["source"]["accession"]) for m in markers],
            [("A", 60_000_000, 62_000_000, "0000000001-25-000001"), ("總營收", 100_000_000, 102_000_000, "0000000001-25-000001")],
        )
        self.assertEqual([a["fact_id"] for a in markers[0]["listed_addends"]], ["pa"])
        self.assertEqual([(a["operand"], a["value"]) for a in markers[0]["published_addends"]], [("op1", 60_000_000)])
        self.assertNotIn("differences", self.status()["periods"]["Q"]["2025-03-31"])

    def test_comparison_follows_spec_definition_across_rename(self):
        # 2024 Q1 用舊成員 x:AMember；2025 Q1 申報改用 x:ANewMember，且其比較欄把 2024 Q1 的 A 列為 62。
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2024-12-31")), define(fact(REVENUE, {AXIS: "x:ANewMember"}), effective("2025-01-01"))),
                SPEC.categories[1],
            ),
            total=SPEC.total,
        )
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        current = self.items("2025", (66, 44), comparative=(62, 40))
        for f in current:
            if f["dims"] == A:
                f["dims"] = {AXIS: "x:ANewMember"}
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", current))
        self.parser(spec).run(["2024-03-31", "2025-03-31"])
        markers = self.status()["periods"]["Q"]["2024-03-31"]["differences"]
        self.assertEqual([(m["category"], m["published_value"], m["listed_value"]) for m in markers], [("A", 60_000_000, 62_000_000), ("總營收", 100_000_000, 102_000_000)])

    def test_comparatives_list_every_covered_operand(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(60, 40))))
        self.parser().run(["2024-03-31", "2025-03-31"])
        self.assertNotIn("differences", self.status()["periods"]["Q"]["2024-03-31"])

    def test_missing_comparative_category_is_recorded_without_marker(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        current = [f for f in self.items("2025", (66, 44), comparative=(60, 40)) if f["id"] != "pb"]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", current))
        self.parser().run(["2024-03-31", "2025-03-31"])
        self.assertNotIn("differences", self.status()["periods"]["Q"]["2024-03-31"])

    def test_difference_within_precision_is_consistent(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        comparative = self.items("2025", (66, 44), comparative=(60, 40))
        for f in comparative:
            if f["id"] == "pa":
                f.update(raw="60000.4", scale="3", decimals="-3")
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", comparative))
        self.parser().run(["2024-03-31"])
        self.parser().run(["2025-03-31"])
        self.assertNotIn("differences", self.status()["periods"]["Q"]["2024-03-31"])

    def test_six_month_columns_are_not_compared(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-24-000002", "10-Q", "2024-06-30", "2024-07-15", build_html(2024, "Q2", self.items("2024", (70, 30), q2=True)))
        current = self.items("2025", (75, 25), q2=True) + [
            item("ha", REVENUE, A, "2024-01-01", "2024-06-30", "999", 1),
            item("hb", REVENUE, B, "2024-01-01", "2024-06-30", "1", 1),
            item("ht", REVENUE, None, "2024-01-01", "2024-06-30", "1000", 1),
        ]
        self.add("0000000001-25-000002", "10-Q", "2025-06-30", "2025-07-15", build_html(2025, "Q2", current))
        self.parser().run(["2024-03-31", "2024-06-30", "2025-06-30"])
        self.assertFalse(any("differences" in e for e in self.status()["periods"]["Q"].values()))

    def test_outputs_from_later_filings_are_not_compared(self):
        # 2025 Q1 先上線（2025-04-15 申報）；它的 10-Q/A（2025-03-01 以前不存在）在 2025-06-01 申報，列出 2025 Q1 本期欄 70。
        # 2024 Q4 的 10-K（2025-02-15 申報）早於 2025 Q1，看不到 2025 Q1 的輸出，不會與它比對。
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44))))
        annual = [
            item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "300"),
            item("yb", REVENUE, B, "2024-01-01", "2024-12-31", "100"),
            item("yt", REVENUE, None, "2024-01-01", "2024-12-31", "400"),
            item("xa", REVENUE, A, "2025-01-01", "2025-03-31", "1", 1),
            item("xb", REVENUE, B, "2025-01-01", "2025-03-31", "1", 1),
            item("xt", REVENUE, None, "2025-01-01", "2025-03-31", "2", 1),
        ]
        self.add("0000000001-25-000000", "10-K", "2024-12-31", "2025-02-15", build_html(2024, "FY", annual))
        self.parser().run(["2025-03-31"])
        self.assertNotIn("differences", self.status()["periods"]["Q"]["2025-03-31"])

    def test_markers_are_recomputed_from_current_published_values(self):
        # 2024 Q1 起初因規格錯誤失敗、2025 Q1 先上線；修正規格重跑後 2024 Q1 上線，標記照樣出現。
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(62, 40))))
        broken = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0],), total=SPEC.total)
        self.parser(broken).run(["2024-03-31"])
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.status()["periods"]["Q"]["2024-03-31"]["status"], "failed")
        self.parser().run(["2024-03-31", "2025-03-31"])
        markers = self.status()["periods"]["Q"]["2024-03-31"]["differences"]
        self.assertEqual([(m["category"], m["published_value"], m["listed_value"]) for m in markers], [("A", 60_000_000, 62_000_000), ("總營收", 100_000_000, 102_000_000)])
        # 覆寫 2024 Q1 後，標記的已上線值跟著改。下載補上較早申報的原申報（列 A 為 58），覆寫後主申報是它。
        self.add("0000000001-24-000000", "10-Q", "2024-03-31", "2024-04-10", build_html(2024, "Q1", self.items("2024", (58, 40))))
        self.parser(republish={("Q", "2024-03-31")}).run(["2024-03-31"])
        # 原本的 10-Q 現在也是較晚的申報，它列的 60 同樣寫成標記。
        markers = self.status()["periods"]["Q"]["2024-03-31"]["differences"]
        self.assertEqual(
            [(m["category"], m["published_value"], m["listed_value"], m["source"]["accession"]) for m in markers],
            [
                ("A", 58_000_000, 60_000_000, "0000000001-24-000001"),
                ("總營收", 98_000_000, 100_000_000, "0000000001-24-000001"),
                ("A", 58_000_000, 62_000_000, "0000000001-25-000001"),
                ("總營收", 98_000_000, 102_000_000, "0000000001-25-000001"),
            ],
        )

    def test_markers_for_published_outputs_without_status_entry(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(62, 40))))
        self.parser().run(["2024-03-31", "2025-03-31"])
        status = self.status()
        del status["periods"]["Q"]["2024-03-31"]
        JsonCodec.write(ticker_dir(self.out, "TEST") / "status.json", status)
        self.parser().run(["2025-03-31"])
        entry = self.status()["periods"]["Q"]["2024-03-31"]
        self.assertEqual((entry["status"], entry["accession"], len(entry["differences"])), ("published", "0000000001-24-000001", 2))

    def test_amendment_after_annual_report_only_marks(self):
        # Q1 的修正申報在 10-K 之後才申報：Q1 與 Q4 不變，Q1+Q2+Q3+Q4 等於 FY，Q1 有差異標記。
        self.standard_year()
        amended = quarter_items("2025-03-31", (64, 40))
        self.add("0000000001-26-000009", "10-Q/A", "2025-03-31", "2026-05-01", build_html(2025, "Q1", amended))
        parser = self.parser()
        parser.run(parser.periods())
        quarters = [self.output(p)["categories"]["A"]["value"] for p in ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31")]
        self.assertEqual(sum(quarters), self.output("2025-12-31", "FY")["categories"]["A"]["value"])
        self.assertEqual(self.output("2025-03-31")["filings"]["primary"]["accession"], "0000000001-25-000001")
        markers = self.status()["periods"]["Q"]["2025-03-31"]["differences"]
        self.assertEqual([(m["category"], m["listed_value"], m["source"]["accession"]) for m in markers], [("A", 64_000_000, "0000000001-26-000009"), ("總營收", 104_000_000, "0000000001-26-000009")])

    def test_nine_month_column_marks_derived_q4(self):
        self.standard_year()
        later = [
            item("ca", REVENUE, A, "2026-07-01", "2026-09-30", "85"),
            item("cb", REVENUE, B, "2026-07-01", "2026-09-30", "15"),
            item("ct", REVENUE, None, "2026-07-01", "2026-09-30", "100"),
            item("pa", REVENUE, A, "2025-01-01", "2025-09-30", "200", 1),
            item("pb", REVENUE, B, "2025-01-01", "2025-09-30", "100", 1),
            item("pt", REVENUE, None, "2025-01-01", "2025-09-30", "300", 1),
        ]
        self.add("0000000001-26-000009", "10-Q", "2026-09-30", "2026-10-15", build_html(2026, "Q3", later))
        parser = self.parser()
        parser.run(parser.periods())
        status = self.status()["periods"]
        markers = status["Q"]["2025-12-31"]["differences"]
        self.assertEqual(
            [(m["category"], m["role"], m["published_value"], m["listed_value"]) for m in markers],
            [("A", "nine_months", 210_000_000, 200_000_000), ("B", "nine_months", 90_000_000, 100_000_000)],
        )
        self.assertNotIn("differences", status["FY"]["2025-12-31"])
        self.assertEqual(self.output("2025-12-31")["categories"]["A"]["value"], 90_000_000)

    def test_annual_column_marks_fy_and_q4_once_per_filing(self):
        self.standard_year()
        later = [
            item("ya", REVENUE, A, "2026-01-01", "2026-12-31", "300"),
            item("yb", REVENUE, B, "2026-01-01", "2026-12-31", "100"),
            item("yt", REVENUE, None, "2026-01-01", "2026-12-31", "400"),
            item("pa", REVENUE, A, "2025-01-01", "2025-12-31", "310", 1),
            item("pb", REVENUE, B, "2025-01-01", "2025-12-31", "100", 1),
            item("pt", REVENUE, None, "2025-01-01", "2025-12-31", "410", 1),
        ]
        self.add("0000000001-27-000001", "10-K", "2026-12-31", "2027-02-15", build_html(2026, "FY", later))
        parser = self.parser()
        parser.run(parser.periods())
        status = self.status()["periods"]
        for series in ("FY", "Q"):
            markers = status[series]["2025-12-31"]["differences"]
            self.assertEqual(
                [(m["category"], m["role"], m["listed_value"], m["source"]["accession"]) for m in markers],
                [("A", "annual", 310_000_000, "0000000001-27-000001"), ("總營收", "annual", 410_000_000, "0000000001-27-000001")],
            )
        # 2026 年的 Q4 沒有同財年的 Q3，失敗；FY 照常上線。
        self.assertEqual((status["FY"]["2026-12-31"]["status"], status["Q"]["2026-12-31"]["status"]), ("published", "failed"))

    def test_unparseable_comparative_fact_is_listed(self):
        from sec_revenue.revenue.review import comparatives
        from sec_revenue.revenue.xbrl import InlineDocument

        published = {
            "categories": {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}]}},
            "total": {"value": 60_000_000, "expression": []},
            "operands": {
                "op1": {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": A,
                        "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": 60_000_000, "raw": "60", "scale": "6", "decimals": "-6"}
            },
        }
        items = [
            item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "n/a"),
            item("pt", REVENUE, None, "2024-01-01", "2024-03-31", "100"),
        ]
        found = comparatives(
            InlineDocument(build_html(2025, "Q1", items)), "new", [("Q", "2024-03-31", published)],
            lambda name: [Addend(fact(REVENUE, A))] if name == "A" else ([Addend(fact(REVENUE))] if name is None else None),
        )
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["result"], found[0]["listed_value"]), ("unparseable", None))
        self.assertIn("無法比較", found[0]["note"])


A1 = {AXIS: "x:A1Member"}
A2 = {AXIS: "x:A2Member"}
GEO = "srt:StatementGeographicalAxis"
US = {GEO: "x:USMember"}
NON_US = {GEO: "x:NonUSMember"}
SUM_SPEC = CompanySpec(
    ticker="TEST",
    view="product",
    categories=(Category("A", sum_of(fact(REVENUE, A1), fact(REVENUE, A2))), Category("B", fact(REVENUE, B))),
    total=Category("Total", fact(REVENUE)),
)


class MultiFactSumTest(Fixture):
    """一個分類由多個 fact 加權相加：每個加數各是一個運算元，Q4 每個加數各自年度減九個月累計。"""

    QUARTER_VALUES = {"2025-03-31": (35, 25, 40), "2025-06-30": (40, 30, 30), "2025-09-30": (45, 35, 20)}

    def members(self, prefix, start, end, values, dims=(A1, A2, B), table=0):
        items = [item(f"{prefix}{n}", REVENUE, d, start, end, str(v), table) for n, (d, v) in enumerate(zip(dims, values))]
        return items + [item(f"{prefix}t", REVENUE, None, start, end, str(sum(values)), table)]

    def year(self, values=None, dims=(A1, A2, B), drop=None, extra=()):
        """Q1–Q3 10-Q 與 FY 10-K；`drop` 為 (期末日, 加數序號) 時該申報少一個加數；`extra` 附加到每份申報。"""
        values = values or self.QUARTER_VALUES
        nine = [sum(v[i] for v in values.values()) for i in range(len(dims))]
        for n, (end, triple) in enumerate(values.items(), 1):
            focus, start = QUARTERS[end]
            items = self.members("q", start, end, triple, dims)
            if focus == "Q3":
                items += self.members("n", "2025-01-01", end, nine, dims, table=1)
            if drop and drop[0] == end:
                items = [i for i in items if i["id"] not in (f"q{drop[1]}", f"n{drop[1]}")]
            items += [dict(i, id=f"{i['id']}{n}", end=end, start=start) for i in extra]
            self.add(f"0000000001-25-00000{n}", "10-Q", end, f"2025-{int(end[5:7]) + 1:02d}-15", build_html(2025, focus, items))
        annual = [v + 10 * (i + 1) for i, v in enumerate(nine)]
        items = self.members("y", "2025-01-01", "2025-12-31", annual, dims)
        self.add("0000000001-26-000001", "10-K", "2025-12-31", "2026-02-15", build_html(2025, "FY", items))

    def test_quarter_annual_and_q4_use_every_addend(self):
        self.year()
        parser = self.parser(SUM_SPEC)
        self.assertTrue(parser.run(parser.periods())["complete"])
        q1 = self.output("2025-03-31")
        self.assertEqual(q1["categories"]["A"]["value"], 60_000_000)
        self.assertEqual(q1["categories"]["A"]["expression"], [{"operand": "op1", "weight": 1}, {"operand": "op2", "weight": 1}])
        self.assertEqual([q1["operands"][o]["fact_id"] for o in ("op1", "op2")], ["q0", "q1"])
        self.assertEqual(q1["checks"]["sum"]["difference"], 0)
        annual = self.output("2025-12-31", "FY")
        self.assertEqual(annual["categories"]["A"]["value"], (120 + 10 + 90 + 20) * 1_000_000)
        q4 = self.output("2025-12-31")
        expression = q4["categories"]["A"]["expression"]
        self.assertEqual([(e["weight"], q4["operands"][e["operand"]]["fact_id"]) for e in expression], [(1, "y0"), (-1, "n0"), (1, "y1"), (-1, "n1")])
        self.assertEqual([q4["operands"][e["operand"]]["role"] for e in expression], ["annual", "nine_months", "annual", "nine_months"])
        self.assertEqual(q4["categories"]["A"]["value"], 30_000_000)
        for operand in q4["operands"].values():
            self.assertTrue(operand["evidence"]["table"])

    def test_negative_addend_and_define_weight(self):
        with self.assertRaisesRegex(ValueError, "同一個運算元"):
            CompanySpec(
                ticker="TEST",
                view="product",
                categories=(Category("A", sum_of(fact(REVENUE, A1), minus(fact(REVENUE, B)))), Category("B", fact(REVENUE, B))),
                total=Category("Total", fact(REVENUE)),
            )
        C = {AXIS: "x:CMember"}
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(Category("A", sum_of(fact(REVENUE, A1), fact(REVENUE, A2), minus(fact(REVENUE, C)))),),
            reconciling=(Category("Eliminations", define(sum_of(fact(REVENUE, B), minus(fact(REVENUE, {AXIS: "x:DMember"}))), weight=-1)),),
            total=Category("Total", fact(REVENUE)),
        )
        # A = 35 + 25 − 10 = 50；Eliminations = −(40 − 15) = −25；總營收 25。
        dims = (A1, A2, C, B, {AXIS: "x:DMember"})
        items = [item(f"q{n}", REVENUE, d, "2025-01-01", "2025-03-31", str(v)) for n, (d, v) in enumerate(zip(dims, (35, 25, 10, 40, 15)))]
        items.append(item("qt", REVENUE, None, "2025-01-01", "2025-03-31", "25"))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        result = self.composer(spec).compose("2025-03-31")
        lines = {l.name: l for l in result.lines}
        self.assertEqual([t.weight for t in lines["A"].terms], [1, 1, -1])
        self.assertEqual(lines["A"].value, 50_000_000)
        self.assertEqual([t.weight for t in lines["Eliminations"].terms], [-1, 1])
        self.assertEqual(lines["Eliminations"].value, -25_000_000)
        self.assertEqual(result.sum_check["difference"], 0)

    def test_missing_addend_fails_period_and_q4(self):
        self.year(drop=("2025-06-30", 1))
        parser = self.parser(SUM_SPEC)
        parser.run(parser.periods())
        entries = self.status()["periods"]["Q"]
        self.assertEqual((entries["2025-06-30"]["status"], entries["2025-06-30"]["check"]), ("failed", "fact 存在且唯一"))
        self.assertIn("x:A2Member", entries["2025-06-30"]["reason"])
        self.assertEqual(entries["2025-12-31"]["status"], "failed")
        self.assertIn("Q4 依據的 Q 2025-06-30 不通過", entries["2025-12-31"]["reason"])
        self.assertEqual(entries["2025-03-31"]["status"], "published")

    def test_missing_nine_month_addend_fails_q4(self):
        self.year(drop=("2025-09-30", 1))
        with self.assertRaisesRegex(ParseError, "fact 存在且唯一"):
            self.composer(SUM_SPEC).compose("2025-12-31")

    def test_addends_with_different_start_fail(self):
        items = self.members("q", "2025-01-01", "2025-03-31", (35, 25, 40))
        items[1]["start"] = "2024-12-29"
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        with self.assertRaisesRegex(ParseError, "各加數的 quarter 起日不同"):
            self.composer(SUM_SPEC).compose("2025-03-31")

    def geographic_spec(self):
        return CompanySpec(
            ticker="TEST",
            view="product",
            categories=(Category("A", sum_of(fact(REVENUE, US), fact(REVENUE, NON_US))),),
            total=Category("Total", fact(REVENUE)),
        )

    def test_geographic_sum_of_all_members(self):
        self.year(values={"2025-03-31": (60, 40)}, dims=(US, NON_US))
        result = self.composer(self.geographic_spec()).compose("2025-03-31")
        self.assertEqual(result.lines[0].value, 100_000_000)
        self.assertIn({"check": "地區成員完整", "result": "pass"}, result.structural)

    def test_geographic_sum_missing_member_fails(self):
        other = item("geo", REVENUE, {GEO: "x:OtherMember"}, "2025-01-01", "2025-03-31", "5")
        items = self.members("q", "2025-01-01", "2025-03-31", (60, 40), (US, NON_US)) + [other]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        with self.assertRaisesRegex(ParseError, r"地區成員完整.*x:OtherMember"):
            self.composer(self.geographic_spec()).compose("2025-03-31")

    def test_geographic_check_uses_namespace_not_prefix(self):
        namespaces = {**NAMESPACES, "geo": NAMESPACES["srt"], "y": NAMESPACES["x"]}
        items = self.members("q", "2025-01-01", "2025-03-31", (60, 40), (US, NON_US)) + [
            item("geo", REVENUE, {"geo:StatementGeographicalAxis": "y:OtherMember"}, "2025-01-01", "2025-03-31", "5")
        ]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items, namespaces))
        with self.assertRaisesRegex(ParseError, r"地區成員完整.*y:OtherMember"):
            self.composer(self.geographic_spec()).compose("2025-03-31")

    def test_geographic_check_fails_on_unresolvable_dimensions(self):
        items = self.members("q", "2025-01-01", "2025-03-31", (60, 40), (US, NON_US)) + [
            item("geo", REVENUE, {GEO: "zz:OtherMember"}, "2025-01-01", "2025-03-31", "5")
        ]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        with self.assertRaisesRegex(ParseError, r"地區成員完整.*無法解析"):
            self.composer(self.geographic_spec()).compose("2025-03-31")

    def test_geographic_member_of_other_period_or_dimension_is_ignored(self):
        items = self.members("q", "2025-01-01", "2025-03-31", (60, 40), (US, NON_US)) + [
            item("g1", REVENUE, {GEO: "x:OtherMember"}, "2024-01-01", "2024-03-31", "5"),
            item("g2", REVENUE, {**A, GEO: "x:OtherMember"}, "2025-01-01", "2025-03-31", "5"),
        ]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        self.assertEqual(self.composer(self.geographic_spec()).compose("2025-03-31").lines[0].value, 100_000_000)

    def published_sum(self):
        return {
            "categories": {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}, {"weight": 1, "operand": "op2"}]}},
            "total": {"value": 60_000_000, "expression": []},
            "operands": {
                f"op{n}": {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": d,
                           "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": v, "raw": str(v // 1_000_000), "scale": "6", "decimals": "-6"}
                for n, d, v in ((1, A1, 35_000_000), (2, A2, 25_000_000))
            },
        }

    def compare(self, values, dims, addends):
        document = InlineDocument(build_html(2025, "Q1", self.members("p", "2024-01-01", "2024-03-31", values, dims)))
        lookup = {"A": [Addend(fact(REVENUE, d), w) for d, w in addends], None: [Addend(fact(REVENUE))]}
        found = comparatives(document, "new", [("Q", "2024-03-31", self.published_sum())], lookup.get)
        self.assertEqual(len(found), 1)
        return found[0]

    def test_comparative_compares_category_value_not_addends(self):
        A3 = {AXIS: "x:A3Member"}
        # 加數順序相反：分類值相同。
        found = self.compare((35, 25), (A1, A2), [(A2, 1), (A1, 1)])
        self.assertEqual((found["result"], found["published_value"], found["listed_value"]), ("consistent", 60_000_000, 60_000_000))
        # 換了一個成員、個數也不同，但和相同（例如公司把兩個項目併成一個重新列示）。
        found = self.compare((60,), (A3,), [(A3, 1)])
        self.assertEqual(found["result"], "consistent")
        self.assertEqual([a["fact_id"] for a in found["listed_addends"]], ["p0"])
        self.assertEqual([a["operand"] for a in found["published_addends"]], ["op1", "op2"])
        # 和不同。
        found = self.compare((35, 29), (A1, A3), [(A1, 1), (A3, 1)])
        self.assertEqual((found["result"], found["listed_value"]), ("different", 64_000_000))
        # 負號加數。
        found = self.compare((70, 10), (A1, A3), [(A1, 1), (A3, -1)])
        self.assertEqual((found["result"], found["listed_value"]), ("consistent", 60_000_000))

    def test_comparative_missing_addend_is_not_found(self):
        found = self.compare((35,), (A1,), [(A1, 1), (A2, 1)])
        self.assertEqual(found["result"], "not_found")
        self.assertIn("x:A2Member", found["note"])
        self.assertNotIn("listed_value", found)

    def test_comparative_follows_addends_through_parser(self):
        self.year()
        parser = self.parser(SUM_SPEC)
        parser.run(["2025-03-31"])
        later = self.members("q", "2026-01-01", "2026-03-31", (1, 1, 1)) + self.members("c", "2025-01-01", "2025-03-31", (35, 29, 40), table=1)
        self.add("0000000001-26-000002", "10-Q", "2026-03-31", "2026-04-15", build_html(2026, "Q1", later))
        self.parser(SUM_SPEC).run([])
        marks = self.status()["periods"]["Q"]["2025-03-31"]["differences"]
        self.assertEqual([(m["category"], m["published_value"], m["listed_value"]) for m in marks], [("A", 60_000_000, 64_000_000), ("總營收", 100_000_000, 104_000_000)])
        self.assertEqual([(a["operand"], a["value"]) for a in marks[0]["published_addends"]], [("op1", 35_000_000), ("op2", 25_000_000)])
        self.assertEqual([(a["fact_id"], a["value"]) for a in marks[0]["listed_addends"]], [("c0", 35_000_000), ("c1", 29_000_000)])


ALT_A = {AXIS: "x:AltAMember"}
VARIANT_SPEC = CompanySpec(
    ticker="TEST",
    view="product",
    categories=(Category("A", one_of(fact(REVENUE, A), fact(REVENUE, ALT_A))), Category("B", fact(REVENUE, B))),
    total=Category("Total", fact(REVENUE)),
)


class TagVariantTest(Fixture):
    """同一個分類在不同申報使用不同寫法：規格以 one_of 明列每種寫法，一份申報中找得到哪種就用哪種。"""

    def filing(self, n, end, focus, rows, form="10-Q", filed=None, start=None):
        """rows：[(id, concept, dims, start, end, value, table)]；B 與總營收由呼叫端列出。"""
        items = [item(fid, concept, dims, s, e, str(v), table) for fid, concept, dims, s, e, v, table in rows]
        accession = f"0000000001-25-00000{n}" if form == "10-Q" else "0000000001-26-000001"
        self.add(accession, form, end, filed or f"2025-{int(end[5:7]) + 1:02d}-15", build_html(2025, focus, items))

    def quarter(self, n, end, a_dims, a_value, b_value=40, extra=()):
        focus, start = QUARTERS[end]
        rows = [("qa", REVENUE, a_dims, start, end, a_value, 0), ("qb", REVENUE, B, start, end, b_value, 0),
                ("qt", REVENUE, None, start, end, a_value + b_value, 0)] + list(extra)
        return rows

    def test_variants_alternate_between_filings_and_q4(self):
        # Q1、Q3 用 x:AMember，Q2 與 10-K 用 x:AltAMember；Q4 年度與九個月累計各用各的寫法。
        self.filing(1, "2025-03-31", "Q1", self.quarter(1, "2025-03-31", A, 60))
        self.filing(2, "2025-06-30", "Q2", self.quarter(2, "2025-06-30", ALT_A, 70))
        nine = [("na", REVENUE, A, "2025-01-01", "2025-09-30", 210, 1), ("nb", REVENUE, B, "2025-01-01", "2025-09-30", 120, 1),
                ("nt", REVENUE, None, "2025-01-01", "2025-09-30", 330, 1)]
        self.filing(3, "2025-09-30", "Q3", self.quarter(3, "2025-09-30", A, 80, extra=nine))
        annual = [("ya", REVENUE, ALT_A, "2025-01-01", "2025-12-31", 300, 0), ("yb", REVENUE, B, "2025-01-01", "2025-12-31", 160, 0),
                  ("yt", REVENUE, None, "2025-01-01", "2025-12-31", 460, 0)]
        self.filing(4, "2025-12-31", "FY", annual, form="10-K", filed="2026-02-15")
        parser = self.parser(VARIANT_SPEC)
        self.assertTrue(parser.run(parser.periods())["complete"])
        q2 = self.output("2025-06-30")
        self.assertEqual(q2["operands"]["op1"]["dimensions"], ALT_A)
        self.assertEqual(q2["categories"]["A"]["value"], 70_000_000)
        q4 = self.output("2025-12-31")
        operands = [q4["operands"][e["operand"]] for e in q4["categories"]["A"]["expression"]]
        self.assertEqual([(o["role"], o["dimensions"]) for o in operands], [("annual", ALT_A), ("nine_months", A)])
        self.assertEqual(q4["categories"]["A"]["value"], 90_000_000)
        self.assertEqual(self.output("2025-12-31", "FY")["categories"]["A"]["value"], 300_000_000)

    def test_concept_and_extra_dimension_variants(self):
        consolidated = {**A, "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", one_of(fact(REVENUE, A), fact(REVENUE, consolidated))),
                Category("B", one_of(fact(REVENUE, B), fact("us-gaap:Revenues", B))),
            ),
            total=Category("Total", fact(REVENUE)),
        )
        rows = [("qa", REVENUE, consolidated, "2025-01-01", "2025-03-31", 60, 0), ("qb", "us-gaap:Revenues", B, "2025-01-01", "2025-03-31", 40, 0),
                ("qt", REVENUE, None, "2025-01-01", "2025-03-31", 100, 0)]
        self.filing(1, "2025-03-31", "Q1", rows)
        result = self.composer(spec).compose("2025-03-31")
        facts = {l.name: l.terms[0].operand.fact for l in result.lines}
        self.assertEqual((facts["A"].fact_id, facts["B"].fact_id, facts["B"].concept), ("qa", "qb", "us-gaap:Revenues"))
        self.assertEqual(result.sum_check["difference"], 0)

    def test_both_variants_with_same_value_are_accepted(self):
        rows = self.quarter(1, "2025-03-31", A, 60, extra=[("alt", REVENUE, ALT_A, "2025-01-01", "2025-03-31", 60, 1)])
        self.filing(1, "2025-03-31", "Q1", rows)
        operand = next(l for l in self.composer(VARIANT_SPEC).compose("2025-03-31").lines if l.name == "A").terms[0].operand
        # 同精度時選所在表格含最多其他項目者：qa 與 B、總營收同表。
        self.assertEqual((operand.fact.fact_id, [d.fact_id for d in operand.duplicates]), ("qa", ["alt"]))

    def test_both_variants_with_different_values_fail(self):
        rows = self.quarter(1, "2025-03-31", A, 60, extra=[("alt", REVENUE, ALT_A, "2025-01-01", "2025-03-31", 61, 1)])
        self.filing(1, "2025-03-31", "Q1", rows)
        with self.assertRaisesRegex(ParseError, r"fact 存在且唯一.*多種寫法同時出現且數值不一致"):
            self.composer(VARIANT_SPEC).compose("2025-03-31")

    def test_no_variant_found_fails_and_case_is_not_ignored(self):
        self.filing(1, "2025-03-31", "Q1", self.quarter(1, "2025-03-31", {AXIS: "x:AltAmember"}, 60))
        with self.assertRaisesRegex(ParseError, r"找不到 A：one_of\(.*x:AMember.*x:AltAMember"):
            self.composer(VARIANT_SPEC).compose("2025-03-31")

    def test_variant_inside_sum(self):
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(Category("A", sum_of(one_of(fact(REVENUE, A1), fact(REVENUE, {AXIS: "x:AltA1Member"})), fact(REVENUE, A2))),),
            total=Category("Total", fact(REVENUE)),
        )
        rows = [("q1", REVENUE, {AXIS: "x:AltA1Member"}, "2025-01-01", "2025-03-31", 35, 0), ("q2", REVENUE, A2, "2025-01-01", "2025-03-31", 25, 0),
                ("qt", REVENUE, None, "2025-01-01", "2025-03-31", 60, 0)]
        self.filing(1, "2025-03-31", "Q1", rows)
        line = self.composer(spec).compose("2025-03-31").lines[0]
        self.assertEqual(([t.operand.fact.fact_id for t in line.terms], line.value), (["q1", "q2"], 60_000_000))

    def test_comparative_recognises_every_variant(self):
        self.filing(1, "2025-03-31", "Q1", self.quarter(1, "2025-03-31", A, 60))
        self.parser(VARIANT_SPEC).run(["2025-03-31"])
        # 一年後的 10-Q 以另一種寫法列示去年同季：62 與已上線 60 不同；寫法不同不影響比對。
        later = [("ca", REVENUE, ALT_A, "2025-01-01", "2025-03-31", 62, 1), ("cb", REVENUE, B, "2025-01-01", "2025-03-31", 40, 1),
                 ("ct", REVENUE, None, "2025-01-01", "2025-03-31", 102, 1),
                 ("qa", REVENUE, ALT_A, "2026-01-01", "2026-03-31", 1, 0), ("qb", REVENUE, B, "2026-01-01", "2026-03-31", 1, 0),
                 ("qt", REVENUE, None, "2026-01-01", "2026-03-31", 2, 0)]
        items = [item(fid, c, d, st, e, str(v), t) for fid, c, d, st, e, v, t in later]
        self.add("0000000001-26-000002", "10-Q", "2026-03-31", "2026-04-15", build_html(2026, "Q1", items))
        self.parser(VARIANT_SPEC).run([])
        marks = self.status()["periods"]["Q"]["2025-03-31"]["differences"]
        self.assertEqual([(m["category"], m["published_value"], m["listed_value"]) for m in marks], [("A", 60_000_000, 62_000_000), ("總營收", 100_000_000, 102_000_000)])
        self.assertEqual(marks[0]["listed_addends"][0]["dimensions"], ALT_A)
        self.assertEqual(marks[0]["published_addends"][0]["dimensions"], A)

    def test_comparative_with_conflicting_variants_is_unparseable(self):
        published = {
            "categories": {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}]}},
            "total": {"value": 60_000_000, "expression": []},
            "operands": {"op1": {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": A,
                                 "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": 60_000_000, "raw": "60", "scale": "6", "decimals": "-6"}},
        }
        items = [item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "60"), item("palt", REVENUE, ALT_A, "2024-01-01", "2024-03-31", "64"),
                 item("pt", REVENUE, None, "2024-01-01", "2024-03-31", "100")]
        lookup = {"A": [Addend(VARIANT_SPEC.categories[0].definitions[0].addends[0].selector)], None: [Addend(fact(REVENUE))]}
        found = comparatives(InlineDocument(build_html(2025, "Q1", items)), "new", [("Q", "2024-03-31", published)], lookup.get)
        self.assertEqual((found[0]["result"], found[0]["listed_value"]), ("unparseable", None))
        self.assertIn("數值不一致", found[0]["note"])
        self.assertEqual(
            [(a["fact_id"], a["dimensions"], a["value"]) for a in found[0]["listed_addends"]],
            [("pa", A, 60_000_000), ("palt", ALT_A, 64_000_000)],
        )

    def conflicted_html(self, items):
        """`y` 前綴在文件中對應兩個 namespace：根元素宣告為 x 的 URI，內文另宣告為別的 URI。"""
        html = build_html(2025, "Q1", items, {**NAMESPACES, "y": NAMESPACES["x"]})
        return html.replace(b"<body>", b'<body><span xmlns:y="http://example.com/other"></span>', 1)

    def test_variant_with_conflicting_prefix_fails(self):
        spec = CompanySpec(
            ticker="TEST",
            view="product",
            categories=(Category("A", one_of(fact(REVENUE, A), fact(REVENUE, {AXIS: "y:AltAMember"}))), Category("B", fact(REVENUE, B))),
            total=Category("Total", fact(REVENUE)),
        )
        items = [item(fid, REVENUE, d, "2025-01-01", "2025-03-31", str(v)) for fid, d, v in (("qa", A, 60), ("qb", B, 40), ("qt", None, 100))]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", self.conflicted_html(items))
        with self.assertRaisesRegex(ParseError, r"fact 存在且唯一.*y:AltAMember.*\['y'\] 在文件中宣告衝突"):
            self.composer(spec).compose("2025-03-31")

    def test_comparative_with_conflicting_prefix_is_unparseable(self):
        published = {
            "categories": {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}]}},
            "total": {"value": 60_000_000, "expression": []},
            "operands": {"op1": {"kind": "xbrl_fact", "role": "quarter", "accession": "old", "concept": REVENUE, "dimensions": A,
                                 "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": 60_000_000, "raw": "60", "scale": "6", "decimals": "-6"}},
        }
        items = [item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "60"), item("pt", REVENUE, None, "2024-01-01", "2024-03-31", "100")]
        lookup = {"A": [Addend(one_of(fact(REVENUE, A), fact(REVENUE, {AXIS: "y:AltAMember"})))], None: [Addend(fact(REVENUE))]}
        found = comparatives(InlineDocument(self.conflicted_html(items)), "new", [("Q", "2024-03-31", published)], lookup.get)
        self.assertEqual((found[0]["result"], found[0]["listed_value"]), ("unparseable", None))
        self.assertIn("宣告衝突", found[0]["note"])


class DefaultStartTest(Fixture):
    START = "2025-10-01"

    def test_default_start_skips_earlier_periods_but_reads_their_filings(self):
        # 預設起始日在 Q3 之後：不帶起日時 Q1–Q3 不處理，Q3 10-Q 仍是 Q4 的九個月運算元；FY 照常發布。
        self.standard_year()
        parser = self.parser(default_start=self.START)
        self.assertEqual(parser.periods(), ["2025-12-31"])
        report = parser.run(parser.periods())
        self.assertTrue(report["complete"])
        status = self.status()["periods"]
        self.assertEqual((sorted(status["Q"]), sorted(status["FY"])), (["2025-12-31"], ["2025-12-31"]))
        q4 = self.output("2025-12-31")
        self.assertEqual(q4["filings"]["nine_months"]["accession"], "0000000001-25-000003")
        self.assertEqual(q4["categories"]["A"]["value"], 90_000_000)
        self.assertEqual(sorted(p.name for p in (ticker_dir(self.out, "TEST") / "Q").iterdir()), ["2025-12-31"])
        self.assertEqual(check_outputs(self.data, self.out, SPEC, "spec-sha", None, default_start=self.START)[1], [])

    def test_start_before_default_publishes_earlier_periods(self):
        self.standard_year()
        parser = self.parser(default_start=self.START)
        self.assertEqual(parser.periods(start="2025-04-01"), ["2025-06-30", "2025-09-30", "2025-12-31"])
        parser.run(parser.periods(start="2025-04-01"))
        status = self.status()["periods"]["Q"]
        self.assertEqual({p: e["status"] for p, e in status.items()}, dict.fromkeys(["2025-06-30", "2025-09-30", "2025-12-31"], "published"))
        earlier = {p: (ticker_dir(self.out, "TEST") / "Q" / p / "revenue.json").read_bytes() for p in ("2025-06-30", "2025-09-30")}
        # 之後不帶起日的一般 parse：不報錯，較早的已上線輸出與紀錄保留不動。
        parser = self.parser(default_start=self.START)
        report = parser.run(parser.periods())
        self.assertTrue(report["complete"])
        self.assertEqual([(p["series"], p["period_end"]) for p in report["periods"]], [("FY", "2025-12-31"), ("Q", "2025-12-31")])
        self.assertEqual(sorted(self.status()["periods"]["Q"]), ["2025-06-30", "2025-09-30", "2025-12-31"])
        for period, raw in earlier.items():
            self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / period / "revenue.json").read_bytes(), raw)
        # --check 從 status.json 取期別，含較早的期別，照常比對。
        report, found = check_outputs(self.data, self.out, SPEC, "spec-sha", None, default_start=self.START)
        self.assertEqual(found, [])
        self.assertIn(("Q", "2025-06-30"), [(p["series"], p["period_end"]) for p in report["periods"]])

    def test_earlier_published_outputs_are_comparison_baselines(self):
        # 較早期別以起日發布後，較晚申報的比較欄照常與它比對並寫差異標記。
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", ComparativeTest.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", ComparativeTest.items("2025", (66, 44), comparative=(62, 40))))
        self.parser(default_start=self.START).run(["2024-03-31", "2025-03-31"])
        self.parser(default_start=self.START).run([])
        self.assertEqual(len(self.status()["periods"]["Q"]["2024-03-31"]["differences"]), 2)

    def test_default_start_is_global_constant(self):
        from sec_revenue.revenue.engine import DEFAULT_START

        self.standard_year()
        self.assertEqual(self.parser().default_start, DEFAULT_START)
        self.assertEqual(self.parser().periods(), ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"])


class PublishedProtectionTest(Fixture):
    def publish_q1(self, values=(60, 40)):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", values)))
        self.parser().run(["2025-03-31"])
        return (ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes()

    def earlier_original_q1(self):
        """下載補上一份申報日更早的原申報：主申報改變，數值不同。"""
        self.add("0000000001-25-000000", "10-Q", "2025-03-31", "2025-04-10", build_html(2025, "Q1", quarter_items("2025-03-31", (65, 40))))

    def test_changed_values_are_not_overwritten_without_republish(self):
        published = self.publish_q1()
        self.earlier_original_q1()
        report = self.parser().run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes(), published)
        entry = self.status()["periods"]["Q"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        changes = entry["differs_from_published"]
        self.assertEqual(changes["reason"], "選用的申報由 0000000001-25-000001 改為 0000000001-25-000000")
        self.assertIn({"category": "A", "published": 60_000_000, "new": 65_000_000}, changes["categories"])
        self.assertTrue(report["complete"])

    def test_republish_overwrites_and_records_previous_values(self):
        self.publish_q1()
        self.earlier_original_q1()
        self.parser(republish={("Q", "2025-03-31")}).run(["2025-03-31"])
        output = self.output("2025-03-31")
        self.assertEqual(output["categories"]["A"]["value"], 65_000_000)
        record = output["republished"][0]
        self.assertEqual(record["reason"], "選用的申報由 0000000001-25-000001 改為 0000000001-25-000000")
        self.assertEqual(record["previous"]["categories"]["A"], 60_000_000)
        self.assertEqual(record["previous"]["accession"], "0000000001-25-000001")
        # 覆寫後的一般重跑不再有差異，也不重複累加 republished 紀錄。
        before = (ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes()
        self.parser().run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes(), before)
        self.assertNotIn("differs_from_published", self.status()["periods"]["Q"]["2025-03-31"])

    def test_parser_version_alone_is_not_a_difference(self):
        published = self.publish_q1()
        RevenueParser(self.data, self.out, SPEC, "new-spec-sha", screenshotter=lambda: FakeShooter(self)).run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes(), published)
        entry = self.status()["periods"]["Q"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        self.assertNotIn("stale_fields", entry)

    def test_metadata_only_change_is_recorded_as_stale_fields(self):
        published = self.publish_q1()
        path = ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(path)
        output["checks"]["structural"].append({"check": "舊版檢核", "result": "pass"})
        JsonCodec.write(path, output)
        edited = path.read_bytes()
        self.parser().run(["2025-03-31"])
        self.assertEqual(path.read_bytes(), edited)
        entry = self.status()["periods"]["Q"]["2025-03-31"]
        self.assertEqual((entry["status"], entry["stale_fields"]), ("published", ["checks"]))

    def test_evidence_only_change_is_not_a_value_change(self):
        from sec_revenue.revenue.engine import published_differences

        self.publish_q1()
        existing = self.output("2025-03-31")
        changed = json.loads(json.dumps(existing))
        changed["operands"]["op1"]["evidence"]["png_sha256"] = "0" * 64
        result = published_differences(existing, changed)
        self.assertEqual((result["fields"], result["value_changed"]), (["operands.evidence"], False))
        self.assertEqual(result["reason"], "只有中繼資料更新：operands.evidence")
        changed["operands"]["op1"]["fact_id"] = "other"
        self.assertTrue(published_differences(existing, changed)["value_changed"])

    def test_exception_in_one_period_does_not_stop_run(self):
        self.standard_year()
        parser = self.parser()
        original = parser.composer.compose

        def compose(period):
            if period == "2025-06-30":
                raise RuntimeError("boom")
            return original(period)

        parser.composer.compose = compose
        report = parser.run(parser.periods())
        statuses = {p: e["status"] for p, e in self.status()["periods"]["Q"].items()}
        self.assertEqual(statuses["2025-06-30"], "failed")
        self.assertEqual(self.status()["periods"]["Q"]["2025-06-30"]["reason"], "RuntimeError: boom")
        self.assertEqual(statuses["2025-09-30"], "published")
        self.assertFalse(report["complete"])

    def test_failed_swap_restores_previous_output(self):
        from unittest import mock

        published = self.publish_q1()
        self.earlier_original_q1()
        parser = RevenueParser(self.data, self.out, SPEC, "spec-sha", screenshotter=lambda: FakeShooter(self), republish={("Q", "2025-03-31")})
        real_rename = Path.rename

        def rename(path, target):
            if path.name.startswith(".staging-"):
                raise OSError("disk full")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", rename):
            parser.run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json").read_bytes(), published)
        self.assertIn("disk full", self.status()["periods"]["Q"]["2025-03-31"]["reason"])
        self.assertEqual([p.name for p in (ticker_dir(self.out, "TEST") / "Q").iterdir() if p.name.startswith(".")], [])

    def test_leftover_directories_are_recovered_and_never_used_as_baseline(self):
        self.publish_q1()
        root = ticker_dir(self.out, "TEST")
        directory = root / "Q"
        (directory / "2025-03-31").rename(directory / ".retired-2025-03-31-abcd")
        (directory / ".staging-2025-06-30-x").mkdir()
        (directory / "notes").mkdir()
        self.assertEqual(RevenueParser.published(root), {})
        report = self.parser().run([])
        self.assertTrue((directory / "2025-03-31" / "revenue.json").exists())
        self.assertFalse((directory / ".staging-2025-06-30-x").exists())
        self.assertEqual(len(report["recovered"]), 2)
        self.assertEqual(list(RevenueParser.published(root)), [("Q", "2025-03-31")])


class StrictnessTest(Fixture):
    def compose_q1(self, items, namespaces=None):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items, namespaces))
        return self.composer().compose("2025-03-31")

    def test_non_finite_and_signed_display_text_fail(self):
        for raw in ("Infinity", "NaN", "-60", "(60)", "−60"):
            with self.subTest(raw):
                items = quarter_items("2025-03-31", (60, 40))
                items[0]["raw"] = raw
                with self.assertRaisesRegex(ParseError, r"\[fact 存在且唯一\]"):
                    self.compose_q1(items)

    def test_evidence_and_reader_share_number_rule(self):
        from sec_revenue.evidence import ix_number

        self.assertEqual(ix_number("1,234", "num-dot-decimal", "3", "-"), (-1234000, None))
        self.assertIsNone(ix_number("-1,234", "num-dot-decimal", "3", None)[0])
        self.assertEqual(ix_number("—", "fixed-zero", "6", None), (0, None))
        self.assertIsNone(ix_number("Infinity", "", "0", None)[0])

    def test_coarse_precision_fails(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0].update(raw="0.6", scale="8", decimals="-8")
        with self.assertRaisesRegex(ParseError, r"\[單位與精度\].*decimals=-8"):
            self.compose_q1(items)

    def test_duplicates_with_different_precision_use_most_precise(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0].update(raw="60,000.3", scale="3", decimals="-3")
        items[2].update(raw="100,000.3", scale="3", decimals="-3")
        items.append(item("coarse-a", REVENUE, A, "2025-01-01", "2025-03-31", "60", 1))
        result = self.compose_q1(items)
        a = next(l for l in result.lines if l.name == "A").terms[0].operand
        self.assertEqual((a.fact.fact_id, a.fact.value), ("qa", 60_000_300))
        self.assertEqual([d.fact_id for d in a.duplicates], ["coarse-a"])

    def test_less_precise_duplicate_outside_its_precision_fails(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0].update(raw="60,000.3", scale="3", decimals="-3")
        items[2].update(raw="100,000.3", scale="3", decimals="-3")
        items.append(item("coarse-a", REVENUE, A, "2025-01-01", "2025-03-31", "61", 1))
        with self.assertRaisesRegex(ParseError, "重複 fact 的數值不一致"):
            self.compose_q1(items)

    def test_matching_uses_namespace_uri(self):
        aliased = dict(NAMESPACES, gaap="http://fasb.org/us-gaap/2025")
        items = quarter_items("2025-03-31", (60, 40))
        items[0]["concept"] = "gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        result = self.compose_q1(items, aliased)
        self.assertEqual(next(l.value for l in result.lines if l.name == "A"), 60_000_000)

    def test_undeclared_prefix_fails_clearly(self):
        missing = {k: v for k, v in NAMESPACES.items() if k != "x"}
        with self.assertRaisesRegex(ParseError, "前綴在文件中沒有宣告"):
            self.compose_q1(quarter_items("2025-03-31", (60, 40)), missing)

    def test_third_quarter_errors_keep_real_cause(self):
        self.standard_year()
        self.packages.pop("0000000001-25-000003")
        self.add("0000000001-25-000003", "10-Q", "2025-09-30", "2025-10-15", build_html(2025, "Q2", quarter_items("2025-09-30", (80, 20))))
        with self.assertRaisesRegex(ParseError, r"\[Q4 期間\] 0000000001-25-000003（2025-09-30）宣告 \(2025, 'Q2'\)"):
            self.composer().compose("2025-12-31")

    def test_png_is_recaptured_when_scale_differs(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        path = ticker_dir(self.out, "TEST") / "Q" / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(path)
        for operand in output["operands"].values():
            operand["evidence"]["png_scale"] = 2
        JsonCodec.write(path, output)
        shots = len(self.shots)
        self.parser(republish={("Q", "2025-03-31")}).run(["2025-03-31"])
        self.assertEqual(len(self.shots), shots + 1)


class CheckModeTest(Fixture):
    def run_check(self, periods):
        return check_outputs(self.data, self.out, SPEC, "spec-sha", periods)[1]

    def test_status_and_extra_evidence_are_compared(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.run_check(["2025-03-31"]), [])
        directory = ticker_dir(self.out, "TEST")
        (directory / "Q" / "2025-03-31" / "evidence" / "stray.png").write_bytes(b"x")
        status = self.status()
        status["periods"]["Q"]["2025-03-31"]["differences"] = [{"category": "A"}]
        JsonCodec.write(directory / "status.json", status)
        found = self.run_check(["2025-03-31"])
        self.assertTrue(any("stray.png" in d for d in found), found)
        self.assertTrue(any(d.startswith("Q 2025-03-31: status.differences") for d in found), found)

    def test_failed_periods_compare_reasons(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0]["table"] = None
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.run_check(["2025-03-31"]), [])
        status = self.status()
        status["periods"]["Q"]["2025-03-31"]["reason"] = "different"
        JsonCodec.write(ticker_dir(self.out, "TEST") / "status.json", status)
        self.assertTrue(any("status.reason" in d for d in self.run_check(["2025-03-31"])))

    def test_comparison_errors_are_compared(self):
        # 一份申報的原文被竄改：比較欄比對讀不到，記在 comparison_errors；--check 比對這個頂層欄位。
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", ComparativeTest.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", ComparativeTest.items("2025", (66, 44))))
        self.parser().run(["2024-03-31"])
        path = self.data / self.packages["0000000001-25-000001"]["documents"]["test-2025-03-31.htm"]["path"]
        path.write_bytes(b"tampered")
        self.parser().run([])
        errors = self.status()["comparison_errors"]
        self.assertEqual([(e["accession"], e["check"]) for e in errors], [("0000000001-25-000001", "原文存在")])
        self.assertEqual(self.run_check(["2024-03-31"]), [])
        status = self.status()
        del status["comparison_errors"]
        JsonCodec.write(ticker_dir(self.out, "TEST") / "status.json", status)
        found = self.run_check(["2024-03-31"])
        self.assertTrue(any(d.startswith("status.comparison_errors") for d in found), found)

    def test_both_series_are_compared(self):
        self.standard_year()
        parser = self.parser()
        parser.run(parser.periods())
        self.assertEqual(self.run_check(None), [])
        path = ticker_dir(self.out, "TEST") / "FY" / "2025-12-31" / "revenue.json"
        output = JsonCodec.read(path)
        output["categories"]["A"]["value"] += 1
        JsonCodec.write(path, output)
        found = self.run_check(None)
        self.assertTrue(any(d.startswith("FY 2025-12-31: status.differs_from_published") for d in found), found)


class SpecValidationTest(unittest.TestCase):
    def test_weight_is_keyword_only_and_unit(self):
        with self.assertRaisesRegex(ValueError, "第二個參數必須是 effective"):
            define(fact(REVENUE, A), -1)
        with self.assertRaisesRegex(ValueError, "只能是 1 或 -1"):
            define(fact(REVENUE, A), weight=2)
        self.assertEqual([a.weight for a in define(fact(REVENUE, A), weight=-1).addends], [-1])
        self.assertEqual([a.weight for a in define(sum_of(fact(REVENUE, A), minus(fact(REVENUE, B))), weight=-1).addends], [-1, 1])
        with self.assertRaisesRegex(ValueError, "至少要有兩個加數"):
            sum_of(fact(REVENUE, A))
        with self.assertRaisesRegex(ValueError, "加數重複"):
            sum_of(fact(REVENUE, A), fact(REVENUE, A))

    def test_one_of_rules(self):
        with self.assertRaisesRegex(ValueError, "至少要有兩種寫法"):
            one_of(fact(REVENUE, A))
        with self.assertRaisesRegex(ValueError, "寫法重複"):
            one_of(fact(REVENUE, A), fact(REVENUE, A))
        with self.assertRaisesRegex(ValueError, "必須是 fact"):
            one_of(fact(REVENUE, A), table_cell("ex99", "h", "r", "c"))
        with self.assertRaisesRegex(ValueError, "加數重複"):
            sum_of(one_of(fact(REVENUE, A), fact(REVENUE, B)), fact(REVENUE, B))

    def test_spec_rules(self):
        cases = [
            (dict(categories=(Category("A", one_of(fact(REVENUE, A), fact(REVENUE, {AXIS: "x:AltMember"}))), Category("B", one_of(fact(REVENUE, B), fact(REVENUE, {AXIS: "x:AltMember"}))))), "同一個運算元 .*x:AltMember"),
            (dict(categories=(Category("A", sum_of(one_of(fact(REVENUE, {GEO: "x:USMember"}), fact(REVENUE, {GEO: "x:UsMember"})), fact(REVENUE, {GEO: "x:NonUSMember"}))), SPEC.categories[1])), "地區軸的加數不可使用 one_of"),
            (dict(view="geography"), "view 必須是"),
            (dict(total=Category("A", fact(REVENUE))), "與分類重名"),
            (dict(categories=(Category("A", fact(REVENUE, {GEO: "x:USMember"})), SPEC.categories[1])), "地區軸只能以 sum_of"),
            (dict(categories=(Category("A", sum_of(fact(REVENUE, {GEO: "x:USMember"}), fact(REVENUE, A))), SPEC.categories[1])), "每個加數都必須是帶地區軸"),
            (dict(categories=(Category("A", sum_of(fact(REVENUE, {GEO: "x:USMember"}), minus(fact(REVENUE, {GEO: "x:NonUSMember"})))), SPEC.categories[1])), "權重 1"),
            (dict(categories=(Category("A", sum_of(fact(REVENUE, {GEO: "x:USMember"}), fact("us-gaap:Revenues", {GEO: "x:NonUSMember"}))), SPEC.categories[1])), "concept 與地區軸以外"),
            (dict(categories=(Category("A", sum_of(fact(REVENUE, {**A, GEO: "x:USMember"}), fact(REVENUE, {**B, GEO: "x:NonUSMember"}))), SPEC.categories[1])), "concept 與地區軸以外"),
            (dict(categories=(Category("A", sum_of(fact(REVENUE, {AXIS: "x:CMember"}), fact(REVENUE, B))), SPEC.categories[1])), "同一個運算元"),
            (dict(categories=(SPEC.categories[0], Category("B", fact(REVENUE, A)))), "同一個運算元"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern):
                base = dict(ticker="TEST", view="product", categories=SPEC.categories, total=SPEC.total)
                base.update(change)
                with self.assertRaisesRegex(ValueError, pattern):
                    CompanySpec(**base)

    def test_segment_axis_requires_note(self):
        spec = CompanySpec(
            ticker="TEST",
            view="business_segment",
            categories=(Category("A", fact(REVENUE, {"us-gaap:StatementBusinessSegmentsAxis": "x:AMember"})),),
            total=SPEC.total,
        )
        with self.assertRaisesRegex(ValueError, "業務別而不是地區"):
            companies.check_notes(spec, "# notes")
        companies.check_notes(spec, "us-gaap:StatementBusinessSegmentsAxis 的成員是業務群")


class CompanySpecTest(unittest.TestCase):
    def test_aapl_spec_loads_with_product_view(self):
        self.assertIn("AAPL", companies.tickers())
        spec, digest = companies.spec("AAPL")
        self.assertEqual(spec.view, "product")
        self.assertEqual([c.name for c in spec.categories], ["iPhone", "Mac", "iPad", "Wearables, Home and Accessories", "Services"])
        self.assertEqual(len(digest), 64)

    def test_unknown_ticker(self):
        with self.assertRaisesRegex(ValueError, "沒有 parser 規格"):
            companies.spec("ZZZZ")


if __name__ == "__main__":
    unittest.main()
