"""新版 parser 引擎：以合成的 inline XBRL 申報測試每個流程步驟與每項檢核，不連網、不啟動 Chromium。"""

import hashlib
import json
from pathlib import Path
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
from sec_revenue.revenue.spec import (  # noqa: E402
    Category,
    CompanySpec,
    define,
    effective,
    fact,
    table_cell,
)
from sec_revenue.revenue.xbrl import classify_duration  # noqa: E402

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

    def output(self, period):
        return JsonCodec.read(ticker_dir(self.out, "TEST") / period / "revenue.json")

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
        self.assertIsNone(result.replaced)

    def test_amendment_replaces_only_when_it_has_revenue_facts(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        # 只修 Part III 的修正申報：沒有該期營收 facts，不取代原申報。
        self.add("0000000001-25-000002", "10-Q/A", "2025-03-31", "2025-04-20", build_html(2025, "Q1", []))
        result = self.composer().compose("2025-03-31")
        self.assertEqual(result.primary.accession, "0000000001-25-000001")
        self.add("0000000001-25-000003", "10-Q/A", "2025-03-31", "2025-05-20", build_html(2025, "Q1", quarter_items("2025-03-31", (65, 40))))
        result = self.composer().compose("2025-03-31")
        self.assertEqual(result.primary.accession, "0000000001-25-000003")
        self.assertEqual(result.replaced.accession, "0000000001-25-000001")
        self.assertEqual(next(l.value for l in result.lines if l.name == "A"), 65_000_000)

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

    def test_effective_definitions_must_select_exactly_one(self):
        overlapping = self.spec(
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-12-31")), define(fact("us-gaap:Revenues", A), effective("2025-01-01"))),
                SPEC.categories[1],
            )
        )
        with self.assertRaisesRegex(ParseError, r"\[定義唯一\] A 在 2025-03-31 有 2 個"):
            self.composer(overlapping).compose("2025-03-31")
        uncovered = self.spec(categories=(Category("A", define(fact(REVENUE, A), effective("2026-01-01"))), SPEC.categories[1]))
        with self.assertRaisesRegex(ParseError, r"有 0 個"):
            self.composer(uncovered).compose("2025-03-31")
        switched = self.spec(
            categories=(
                Category("A", define(fact("us-gaap:Revenues", A), effective(None, "2024-12-31")), define(fact(REVENUE, A), effective("2025-01-01"))),
                SPEC.categories[1],
            )
        )
        self.assertEqual(next(l.value for l in self.composer(switched).compose("2025-03-31").lines if l.name == "A"), 60_000_000)

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
        self.assertEqual(result.fiscal_quarter, 4)
        self.assertEqual(result.nine_month_filing.report_date, "2025-09-30")
        a = next(l for l in result.lines if l.name == "A")
        self.assertEqual(a.value, 90_000_000)
        self.assertEqual([(t.weight, t.operand.role) for t in a.terms], [(1, "annual"), (-1, "nine_months")])

    def test_q4_operands_use_definition_of_their_source_filing(self):
        # 10-K 起改用新成員，同財年 Q3 10-Q 仍是舊成員：年度用新定義、九個月用舊定義。
        self.standard_year()
        self.packages.pop("0000000001-26-000001")
        annual = [
            item("ya", REVENUE, {AXIS: "x:ANewMember"}, "2025-01-01", "2025-12-31", "300"),
            item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
            item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
        ]
        self.add("0000000001-26-000001", "10-K", "2025-12-31", "2026-02-15", build_html(2025, "FY", annual))
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

    def mixed_year(self, later_nine=None):
        """10-K 起 A 改用新成員；同財年 Q3 10-Q 仍是舊成員。`later_nine` 是下一年 Q3 10-Q 以新成員標示的 2025 九個月值。"""
        self.standard_year()
        self.packages.pop("0000000001-26-000001")
        annual = [
            item("ya", REVENUE, {AXIS: "x:ANewMember"}, "2025-01-01", "2025-12-31", "300"),
            item("yb", REVENUE, B, "2025-01-01", "2025-12-31", "100"),
            item("yt", REVENUE, None, "2025-01-01", "2025-12-31", "400"),
        ]
        self.add("0000000001-26-000001", "10-K", "2025-12-31", "2026-02-15", build_html(2025, "FY", annual))
        if later_nine is not None:
            self.add(
                "0000000001-26-000009", "10-Q", "2026-09-30", "2026-10-15",
                build_html(2026, "Q3", [item("la", REVENUE, {AXIS: "x:ANewMember"}, "2025-01-01", "2025-09-30", str(later_nine))]),
            )
        return CompanySpec(
            ticker="TEST",
            view="product",
            categories=(
                Category("A", define(fact(REVENUE, A), effective(None, "2025-09-30")), define(fact(REVENUE, {AXIS: "x:ANewMember"}), effective("2025-12-31"))),
                SPEC.categories[1],
            ),
            total=SPEC.total,
        )

    def test_q4_mixed_definitions_are_annotated_with_auxiliary_evidence(self):
        spec = self.mixed_year(later_nine=210)
        self.parser(spec).run(["2025-12-31"])
        output = self.output("2025-12-31")
        record = output["checks"]["q4_definitions"]
        self.assertEqual([r["category"] for r in record], ["A"])
        self.assertEqual(record[0]["annual"]["selector"], "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax [srt:ProductOrServiceAxis=x:ANewMember]")
        self.assertEqual(record[0]["nine_months"]["effective"], {"start": None, "end": "2025-09-30"})
        self.assertEqual(record[0]["auxiliary"]["found"], True)
        self.assertEqual((record[0]["auxiliary"]["consistent"], record[0]["auxiliary"]["accession"]), (True, "0000000001-26-000009"))
        self.assertTrue(any(a["check"] == "Q4 跨定義" and a["message"].startswith("A 年度用") and a["message"].endswith("九個月值一致") for a in output["annotations"]))
        self.assertEqual(self.status()["periods"]["2025-12-31"]["status"], "published")

    def test_q4_mixed_definitions_without_auxiliary_evidence(self):
        spec = self.mixed_year()
        self.parser(spec).run(["2025-12-31"])
        record = self.output("2025-12-31")["checks"]["q4_definitions"][0]
        self.assertEqual(record["auxiliary"]["found"], False)

    def test_q4_auxiliary_evidence_reports_inconsistency(self):
        spec = self.mixed_year(later_nine=999)
        self.parser(spec).run(["2025-12-31"])
        auxiliary = self.output("2025-12-31")["checks"]["q4_definitions"][0]["auxiliary"]
        self.assertEqual((auxiliary["found"], auxiliary["consistent"], auxiliary["value"]), (True, False, 999_000_000))
        self.assertTrue(any(a["message"].endswith("九個月值不一致") for a in self.output("2025-12-31")["annotations"]))

    def test_same_definition_q4_has_no_definition_record(self):
        self.standard_year()
        self.parser().run(self.parser().periods())
        self.assertNotIn("q4_definitions", self.output("2025-12-31")["checks"])

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
        directory = ticker_dir(self.out, "TEST") / "2025-12-31" / "evidence"
        for operand in output["operands"].values():
            evidence = operand["evidence"]
            page = (directory / f"{evidence['table']}.html").read_bytes()
            png = (directory / f"{evidence['table']}.png").read_bytes()
            self.assertEqual(hashlib.sha256(page).hexdigest(), evidence["html_sha256"])
            self.assertEqual(hashlib.sha256(png).hexdigest(), evidence["png_sha256"])
        self.assertIn({"check": "Q4 期間", "result": "pass"}, output["checks"]["structural"])
        status = self.status()
        self.assertEqual({p: e["status"] for p, e in status["periods"].items()}, dict.fromkeys(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"], "published"))
        self.assertEqual(status["parser"]["spec_sha256"], "spec-sha")
        self.assertEqual([p.name for p in ticker_dir(self.out, "TEST").iterdir() if p.name.startswith(".")], [])

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
        entry = self.status()["periods"]["2025-03-31"]
        self.assertFalse(report["complete"])
        self.assertEqual((entry["status"], entry["check"]), ("failed", "證據完整"))
        self.assertFalse((ticker_dir(self.out, "TEST") / "2025-03-31").exists())

    def test_failed_rerun_keeps_published_output(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        published = (ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes()
        spec = CompanySpec(ticker="TEST", view="product", categories=(SPEC.categories[0],), total=SPEC.total)
        self.parser(spec).run(["2025-03-31"])
        entry = self.status()["periods"]["2025-03-31"]
        self.assertEqual((entry["status"], entry["check"], entry["published_output_kept"]), ("failed", "加總", True))
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), published)

    def test_browser_table_mismatch_fails(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))

        class WrongTable(FakeShooter):
            def capture(self, raw, items):
                png, cropped, _ = super().capture(raw, items)
                return png, cropped, "other"

        parser = RevenueParser(self.data, self.out, SPEC, "spec-sha", screenshotter=lambda: WrongTable(self))
        parser.run(["2025-03-31"])
        self.assertIn("文字不同", self.status()["periods"]["2025-03-31"]["reason"])

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
        committed = ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(committed)
        output["categories"]["A"]["value"] += 1
        JsonCodec.write(committed, output)
        png = next((ticker_dir(self.out, "TEST") / "2025-06-30" / "evidence").glob("*.png"))
        png.write_bytes(b"tampered")
        found = check_outputs(self.data, self.out, SPEC, "spec-sha", periods)[1]
        self.assertTrue(any(d.startswith("2025-03-31: status.differs_from_published") for d in found), found)
        self.assertTrue(any("2025-06-30" in d and "PNG" in d for d in found), found)


class CrossPeriodTest(Fixture):
    def two_years(self, second_q1=(60, 40)):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-24-000002", "10-Q", "2024-06-30", "2024-07-15", build_html(2024, "Q2", self.items("2024", (70, 30), q2=True)))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", second_q1)))

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

    def test_first_period_has_no_baseline(self):
        self.two_years()
        self.parser().run(["2024-03-31"])
        checks = self.output("2024-03-31")["checks"]["cross_period"]
        self.assertEqual(checks[0], {"check": "期別連續", "annotated": False, "note": "沒有上一期可比"})
        self.assertEqual(checks[1], {"check": "分類集合", "annotated": False, "note": "沒有上一期可比"})
        self.assertTrue(all(not c["annotated"] for c in checks))
        self.assertEqual(self.output("2024-03-31")["annotations"], [])

    def test_quarter_over_quarter_is_recorded_only(self):
        self.two_years()
        parser = self.parser()
        parser.run(parser.periods())
        q2 = self.output("2024-06-30")["checks"]["cross_period"]
        qoq = [c for c in q2 if c["check"] == "QoQ"]
        self.assertEqual({c["category"]: c["change"] for c in qoq}, {"A": 0.1667, "B": -0.25})
        self.assertTrue(all(not c["annotated"] for c in qoq))

    def test_share_and_yoy_compare_with_same_quarter_last_year(self):
        self.two_years(second_q1=(95, 5))
        parser = self.parser()
        parser.run(parser.periods())
        output = self.output("2025-03-31")
        annotated = {(c["check"], c.get("category")) for c in output["checks"]["cross_period"] if c["annotated"]}
        # 2024 Q3、Q4 沒有上線，上一個已上線期別是 2024 Q2，因此期別連續也標示。
        self.assertEqual(annotated, {("期別連續", None), ("占比變動", "A"), ("占比變動", "B"), ("YoY", "A"), ("YoY", "B")})
        self.assertEqual(next(c for c in output["checks"]["cross_period"] if c["check"] == "占比變動")["baseline_period"], "2024-03-31")
        # 2025 Q1 的申報沒有 2024 Q1 的比較期，因此另有比較期總營收的標註。
        self.assertEqual(sorted({a["check"] for a in output["annotations"]}), ["YoY", "占比變動", "期別連續", "比較期總營收"])
        share = next(a for a in output["annotations"] if a["check"] == "占比變動")
        self.assertEqual(share["detail"]["baseline_period"], "2024-03-31")
        entry = self.status()["periods"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        self.assertEqual(len(entry["annotations"]), 6)

    def test_category_set_change_is_annotated(self):
        self.two_years()
        parser = self.parser()
        parser.run(["2024-03-31"])
        spec = CompanySpec(
            ticker="TEST", view="product", categories=(Category("A", fact(REVENUE, A)), Category("Bee", fact(REVENUE, B))), total=SPEC.total
        )
        self.parser(spec).run(["2024-06-30"])
        check = next(c for c in self.output("2024-06-30")["checks"]["cross_period"] if c["check"] == "分類集合")
        self.assertEqual((check["annotated"], check["added"], check["removed"]), (True, ["Bee"], ["B"]))

    def test_restatement_marks_new_period_and_keeps_old_output(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add(
            "0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15",
            build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(62, 40))),
        )
        parser = self.parser()
        parser.run(["2024-03-31"])
        before = (ticker_dir(self.out, "TEST") / "2024-03-31" / "revenue.json").read_bytes()
        self.parser().run(["2025-03-31"])
        output = self.output("2025-03-31")
        restated = output["checks"]["restatements"]
        self.assertEqual(
            [(r["period_end"], r["published_value"], r["restated_value"]) for r in restated],
            [("2024-03-31", 60_000_000, 62_000_000), ("2024-03-31", 100_000_000, 102_000_000)],
        )
        self.assertTrue(any(a["check"] == "重編" for a in output["annotations"]))
        self.assertEqual((ticker_dir(self.out, "TEST") / "2024-03-31" / "revenue.json").read_bytes(), before)
        self.assertEqual(self.status()["periods"]["2024-03-31"]["restated_by"], ["2025-03-31"])

    def test_restatement_check_follows_spec_definition_across_rename(self):
        # 2024 Q1 用舊成員 x:AMember；2025 Q1 申報改用 x:ANewMember，且其比較期把 2024 Q1 的 A 改為 62。
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
        restated = self.output("2025-03-31")["checks"]["restatements"]
        self.assertEqual(
            [(r["period_end"], r["published_value"], r["restated_value"]) for r in restated],
            [("2024-03-31", 60_000_000, 62_000_000), ("2024-03-31", 100_000_000, 102_000_000)],
        )

    def test_comparatives_list_every_covered_operand(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44), comparative=(60, 40))))
        self.parser().run(["2024-03-31", "2025-03-31"])
        output = self.output("2025-03-31")
        self.assertEqual(
            sorted((e["category"], e["result"]) for e in output["checks"]["comparatives"]),
            [("A", "consistent"), ("B", "consistent"), ("總營收", "consistent")],
        )
        # 只缺 2024 Q2–Q4，期別連續會標示；比較期本身沒有問題。
        self.assertFalse(any(a["check"].startswith(("比較期", "重編")) for a in output["annotations"]))

    def test_missing_comparative_category_is_annotated(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        current = [f for f in self.items("2025", (66, 44), comparative=(60, 40)) if f["id"] != "pb"]
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", current))
        self.parser().run(["2024-03-31", "2025-03-31"])
        output = self.output("2025-03-31")
        missing = [e for e in output["checks"]["comparatives"] if e["result"] == "not_found"]
        self.assertEqual([(e["period_end"], e["category"]) for e in missing], [("2024-03-31", "B")])
        self.assertTrue(any(a["check"] == "比較期找不到" and a["message"].startswith("2024-03-31 B") for a in output["annotations"]))

    def test_missing_year_ago_total_is_annotated(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", self.items("2025", (66, 44))))
        self.parser().run(["2024-03-31", "2025-03-31"])
        output = self.output("2025-03-31")
        self.assertEqual(output["checks"]["comparatives"], [])
        self.assertTrue(any(a["check"] == "比較期總營收" and "去年同季 2024-03-31" in a["message"] for a in output["annotations"]))

    def test_difference_within_precision_is_not_restatement(self):
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", build_html(2024, "Q1", self.items("2024", (60, 40))))
        comparative = self.items("2025", (66, 44), comparative=(60, 40))
        for f in comparative:
            if f["id"] == "pa":
                f.update(raw="60000.4", scale="3", decimals="-3")
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", comparative))
        self.parser().run(["2024-03-31"])
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.output("2025-03-31")["checks"]["restatements"], [])


class PublishedProtectionTest(Fixture):
    def publish_q1(self, values=(60, 40)):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", values)))
        self.parser().run(["2025-03-31"])
        return (ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes()

    def amend_q1(self):
        self.add("0000000001-25-000005", "10-Q/A", "2025-03-31", "2025-06-01", build_html(2025, "Q1", quarter_items("2025-03-31", (65, 40))))

    def test_changed_values_are_not_overwritten_without_republish(self):
        published = self.publish_q1()
        self.amend_q1()
        report = self.parser().run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), published)
        entry = self.status()["periods"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        changes = entry["differs_from_published"]
        self.assertEqual(changes["reason"], "修正申報取代原申報")
        self.assertIn({"category": "A", "published": 60_000_000, "new": 65_000_000}, changes["categories"])
        self.assertTrue(any("--republish TEST 2025-03-31" in a["message"] for a in entry["new_annotations"]))
        # 修正申報造成的重編也是重算出的新標註。
        self.assertTrue(any(a["check"] == "重編" for a in entry["new_annotations"]))
        self.assertTrue(report["complete"])

    def test_republish_overwrites_and_records_previous_values(self):
        self.publish_q1()
        self.amend_q1()
        self.parser(republish={"2025-03-31"}).run(["2025-03-31"])
        output = self.output("2025-03-31")
        self.assertEqual(output["categories"]["A"]["value"], 65_000_000)
        record = output["republished"][0]
        self.assertEqual(record["reason"], "修正申報取代原申報")
        self.assertEqual(record["previous"]["categories"]["A"], 60_000_000)
        self.assertEqual(record["previous"]["accession"], "0000000001-25-000001")
        amendment = [r for r in output["checks"]["restatements"] if r["kind"] == "amendment"]
        self.assertIn(("op1", 60_000_000, 65_000_000), [(r["operand"], r["published_value"], r["restated_value"]) for r in amendment])
        self.assertTrue(any(a["check"] == "重編" for a in output["annotations"]))
        # 覆寫後的一般重跑不再有差異，也不重複累加 republished 紀錄。
        before = (ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes()
        self.parser().run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), before)
        self.assertNotIn("differs_from_published", self.status()["periods"]["2025-03-31"])

    def test_parser_version_alone_is_not_a_difference(self):
        published = self.publish_q1()
        RevenueParser(self.data, self.out, SPEC, "new-spec-sha", screenshotter=lambda: FakeShooter(self)).run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), published)
        entry = self.status()["periods"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        self.assertNotIn("stale_fields", entry)

    def test_metadata_only_change_is_recorded_as_stale_fields(self):
        published = self.publish_q1()
        path = ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(path)
        output["checks"]["structural"].append({"check": "舊版檢核", "result": "pass"})
        JsonCodec.write(path, output)
        edited = path.read_bytes()
        self.parser().run(["2025-03-31"])
        self.assertEqual(path.read_bytes(), edited)
        entry = self.status()["periods"]["2025-03-31"]
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

    def test_new_annotations_on_published_period_go_to_status(self):
        # 先上線 2025 Q1，之後才補上 2024 Q1（數字差很多），重算 2025 Q1 的跨期檢核產生新的標註。
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        published = (ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes()
        html = build_html(2024, "Q1", [
            item("a", REVENUE, A, "2024-01-01", "2024-03-31", "10"),
            item("b", REVENUE, B, "2024-01-01", "2024-03-31", "90"),
            item("t", REVENUE, None, "2024-01-01", "2024-03-31", "100"),
        ])
        self.add("0000000001-24-000001", "10-Q", "2024-03-31", "2024-04-15", html)
        self.parser().run(["2024-03-31", "2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), published)
        entry = self.status()["periods"]["2025-03-31"]
        self.assertEqual(entry["status"], "published")
        self.assertIn("checks", entry["stale_fields"])
        self.assertTrue(any(a["check"] == "占比變動" and a["message"].startswith("A 占比") for a in entry["new_annotations"]), entry)

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
        statuses = {p: e["status"] for p, e in self.status()["periods"].items()}
        self.assertEqual(statuses["2025-06-30"], "failed")
        self.assertEqual(self.status()["periods"]["2025-06-30"]["reason"], "RuntimeError: boom")
        # 下一期照常上線；上一個已上線期別變成 Q1，所以寫期別連續的標註。
        self.assertEqual(statuses["2025-09-30"], "published")
        self.assertEqual(self.status()["periods"]["2025-09-30"]["annotations"][0]["check"], "期別連續")
        self.assertFalse(report["complete"])

    def test_failed_swap_restores_previous_output(self):
        from unittest import mock

        published = self.publish_q1()
        self.amend_q1()
        parser = RevenueParser(self.data, self.out, SPEC, "spec-sha", screenshotter=lambda: FakeShooter(self), republish={"2025-03-31"})
        real_rename = Path.rename

        def rename(path, target):
            if path.name.startswith(".staging-"):
                raise OSError("disk full")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", rename):
            parser.run(["2025-03-31"])
        self.assertEqual((ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json").read_bytes(), published)
        self.assertIn("disk full", self.status()["periods"]["2025-03-31"]["reason"])
        self.assertEqual([p.name for p in ticker_dir(self.out, "TEST").iterdir() if p.name.startswith(".")], [])

    def test_leftover_directories_are_recovered_and_never_used_as_baseline(self):
        self.publish_q1()
        directory = ticker_dir(self.out, "TEST")
        (directory / "2025-03-31").rename(directory / ".retired-2025-03-31-abcd")
        (directory / ".staging-2025-06-30-x").mkdir()
        (directory / "notes").mkdir()
        self.assertEqual(RevenueParser.published(directory), {})
        report = self.parser().run([])
        self.assertTrue((directory / "2025-03-31" / "revenue.json").exists())
        self.assertFalse((directory / ".staging-2025-06-30-x").exists())
        self.assertEqual(len(report["recovered"]), 2)
        self.assertEqual(list(RevenueParser.published(directory)), ["2025-03-31"])


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
        path = ticker_dir(self.out, "TEST") / "2025-03-31" / "revenue.json"
        output = JsonCodec.read(path)
        for operand in output["operands"].values():
            operand["evidence"]["png_scale"] = 2
        JsonCodec.write(path, output)
        shots = len(self.shots)
        self.parser(republish={"2025-03-31"}).run(["2025-03-31"])
        self.assertEqual(len(self.shots), shots + 1)


class ReviewMatchingTest(Fixture):
    def baseline(self, end, year, quarter, values=(60, 40)):
        return {
            "period_end": end,
            "fiscal_year": year,
            "fiscal_quarter": quarter,
            "categories": {"A": {"value": values[0]}, "B": {"value": values[1]}},
            "total": {"value": sum(values)},
            "operands": {},
        }

    def check(self, current, baselines):
        from sec_revenue.revenue.review import cross_period

        return cross_period(current, baselines)

    def test_last_year_must_be_unique_and_one_year_apart(self):
        current = self.baseline("2025-03-31", 2025, 1)
        duplicate = {"2024-03-31": self.baseline("2024-03-31", 2024, 1), "2024-04-30": self.baseline("2024-04-30", 2024, 1)}
        notes = [c["note"] for c in self.check(current, duplicate) if c["check"] == "去年同季"]
        self.assertTrue(notes and all("有 2 期" in n for n in notes))
        shifted = {"2024-06-30": self.baseline("2024-06-30", 2024, 1)}
        checks = [c for c in self.check(current, shifted) if c["check"] == "去年同季"]
        self.assertTrue(all(c["annotated"] and "相隔不是一年" in c["note"] for c in checks))

    def test_missing_last_year_with_older_history_is_annotated(self):
        current = self.baseline("2025-03-31", 2025, 1)
        history = {"2023-12-31": self.baseline("2023-12-31", 2023, 4)}
        checks = [c for c in self.check(current, history) if c["check"] == "去年同季"]
        self.assertTrue(checks and all(c["annotated"] and "缺去年同季" in c["note"] for c in checks))

    def test_period_continuity_uses_gap_and_fiscal_labels(self):
        current = self.baseline("2025-06-30", 2025, 2)
        good = {"2025-03-31": self.baseline("2025-03-31", 2025, 1)}
        self.assertFalse(next(c for c in self.check(current, good) if c["check"] == "期別連續")["annotated"])
        mislabeled = {"2025-03-31": self.baseline("2025-03-31", 2024, 4)}
        self.assertTrue(next(c for c in self.check(current, mislabeled) if c["check"] == "期別連續")["annotated"])

    def test_zero_totals_are_annotated_not_divided(self):
        current = self.baseline("2025-03-31", 2025, 1, (0, 0))
        last = {"2024-03-31": self.baseline("2024-03-31", 2024, 1, (0, 0))}
        checks = {(c["check"], c.get("note")) for c in self.check(current, last) if c["annotated"]}
        self.assertIn(("占比變動", "總營收為 0，無法計算占比"), checks)
        self.assertIn(("YoY", "去年同季為 0"), checks)

    def test_thresholds_compare_unrounded_values(self):
        current = self.baseline("2025-03-31", 2025, 1, (1500004, 1000000))
        last = {"2024-03-31": self.baseline("2024-03-31", 2024, 1, (1000000, 1000000))}
        yoy = next(c for c in self.check(current, last) if c["check"] == "YoY" and c["category"] == "A")
        self.assertEqual(yoy["change"], 0.5)
        self.assertTrue(yoy["annotated"])

    def test_unparseable_comparative_fact_is_recorded(self):
        from sec_revenue.revenue.review import restatements
        from sec_revenue.revenue.xbrl import InlineDocument

        published = self.baseline("2024-03-31", 2024, 1)
        published["operands"] = {
            "op1": {"kind": "xbrl_fact", "accession": "old", "concept": REVENUE, "dimensions": A,
                    "period": {"start": "2024-01-01", "end": "2024-03-31"}, "value": 60_000_000, "decimals": "-6"}
        }
        items = [
            item("pa", REVENUE, A, "2024-01-01", "2024-03-31", "n/a"),
            item("pt", REVENUE, None, "2024-01-01", "2024-03-31", "100"),
        ]
        published["categories"] = {"A": {"value": 60_000_000, "expression": [{"weight": 1, "operand": "op1"}]}}
        published["total"] = {"value": 60_000_000, "expression": []}
        selector = fact(REVENUE, A)
        found = restatements(
            InlineDocument(build_html(2025, "Q1", items)), "new", {"2024-03-31": published},
            lambda name: selector if name == "A" else (fact(REVENUE) if name is None else None),
        )
        self.assertEqual(len(found), 1)
        self.assertIsNone(found[0]["restated_value"])
        self.assertIn("無法比較", found[0]["note"])


class CheckModeTest(Fixture):
    def run_check(self, periods):
        return check_outputs(self.data, self.out, SPEC, "spec-sha", periods)[1]

    def test_status_and_extra_evidence_are_compared(self):
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", quarter_items("2025-03-31", (60, 40))))
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.run_check(["2025-03-31"]), [])
        directory = ticker_dir(self.out, "TEST")
        (directory / "2025-03-31" / "evidence" / "stray.png").write_bytes(b"x")
        status = self.status()
        status["periods"]["2025-03-31"]["annotations"] = [{"check": "manual", "message": "manual"}]
        JsonCodec.write(directory / "status.json", status)
        found = self.run_check(["2025-03-31"])
        self.assertTrue(any("stray.png" in d for d in found), found)
        self.assertTrue(any("status.annotations" in d for d in found), found)

    def test_failed_periods_compare_reasons(self):
        items = quarter_items("2025-03-31", (60, 40))
        items[0]["table"] = None
        self.add("0000000001-25-000001", "10-Q", "2025-03-31", "2025-04-15", build_html(2025, "Q1", items))
        self.parser().run(["2025-03-31"])
        self.assertEqual(self.run_check(["2025-03-31"]), [])
        status = self.status()
        status["periods"]["2025-03-31"]["reason"] = "different"
        JsonCodec.write(ticker_dir(self.out, "TEST") / "status.json", status)
        self.assertTrue(any("status.reason" in d for d in self.run_check(["2025-03-31"])))


class SpecValidationTest(unittest.TestCase):
    def test_weight_is_keyword_only_and_unit(self):
        with self.assertRaisesRegex(ValueError, "第二個參數必須是 effective"):
            define(fact(REVENUE, A), -1)
        with self.assertRaisesRegex(ValueError, "只能是 1 或 -1"):
            define(fact(REVENUE, A), weight=2)
        self.assertEqual(define(fact(REVENUE, A), weight=-1).weight, -1)

    def test_spec_rules(self):
        cases = [
            (dict(view="geography"), "view 必須是"),
            (dict(total=Category("A", fact(REVENUE))), "與分類重名"),
            (dict(categories=(Category("A", fact(REVENUE, {"srt:StatementGeographicalAxis": "country:US"})), SPEC.categories[1])), "地區軸"),
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
