"""fact 清單納入附件（`ATTACHMENTS`）：附件 fact 共用主文件的 context、合併規則、證據指向附件、快照涵蓋附件。"""

import ast
import hashlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from lxml import etree

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.common.jsonio import JsonCodec  # noqa: E402
from sec_revenue.revenue import extract, ixds, snapshot  # noqa: E402
from sec_revenue.revenue.compose import PeriodComposer  # noqa: E402
from sec_revenue.revenue.engine import ticker_dir  # noqa: E402
from sec_revenue.revenue.filings import FilingSet, ParseError  # noqa: E402
from sec_revenue.revenue.source import ParserSource  # noqa: E402

from tests.sec_revenue.revenue import test_revenue_parser as base  # noqa: E402
from tests.sec_revenue.revenue import test_snapshot as snapshots  # noqa: E402

REVENUE, A, B, NAMESPACES, item, build_html = base.REVENUE, base.A, base.B, base.NAMESPACES, base.item, base.build_html
EXHIBIT = "test-ex13.htm"
ACCESSION = "0000000001-26-000001"


def context(f) -> str:
    members = "".join(f'<xbrldi:explicitMember dimension="{a}">{m}</xbrldi:explicitMember>' for a, m in f["dims"].items())
    segment = f"<xbrli:segment>{members}</xbrli:segment>" if members else ""
    return (
        f'<xbrli:context id="c-{f["id"]}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier>{segment}</xbrli:entity>'
        f'<xbrli:period><xbrli:startDate>{f["start"]}</xbrli:startDate><xbrli:endDate>{f["end"]}</xbrli:endDate></xbrli:period></xbrli:context>'
    )


def primary_with_contexts(items: list[dict], shared: list[dict]) -> bytes:
    """主文件：自己的 fact（`items`），另在 `ix:resources` 定義附件 fact（`shared`）用的 context。"""
    page = build_html(2025, "FY", items)
    return page.replace(b"</ix:resources>", "".join(context(f) for f in shared).encode() + b"</ix:resources>", 1)


def exhibit(items: list[dict], namespaces=None, resources: str = "") -> bytes:
    """附件：只有表格與 `ix:nonFraction`，context 與 unit 由主文件定義（`resources` 另加附件自己的定義）。"""
    rows = "".join(
        f'<tr><td>{f["id"]}</td><td><ix:nonFraction id="{f["id"]}" name="{f["concept"]}" contextRef="c-{f["id"]}" '
        f'unitRef="{f["unit"]}" scale="{f["scale"]}" format="{f["fmt"]}" decimals="{f["decimals"]}">{f["raw"]}</ix:nonFraction></td></tr>'
        for f in items
    )
    xmlns = " ".join(f'xmlns:{p}="{u}"' for p, u in (namespaces or NAMESPACES).items())
    return f"<html {xmlns}><body>{resources}<p>Exhibit 13</p><table><tr><td>x</td></tr></table><table>{rows}</table></body></html>".encode()


def annual_items(prefix="y", values=(190, 110)):
    a, b = values
    return [
        item(f"{prefix}a", REVENUE, A, "2025-01-01", "2025-12-31", str(a)),
        item(f"{prefix}b", REVENUE, B, "2025-01-01", "2025-12-31", str(b)),
        item(f"{prefix}t", REVENUE, None, "2025-01-01", "2025-12-31", str(a + b)),
    ]


def declared(**customizations):
    """與 `base.company()` 相同的合成公司 parser，另宣告附件。"""
    source = base.company(**customizations)
    module = types.ModuleType("test_parser")
    for name in ("TICKER", "VIEW", "TOTAL", "compose", "categories"):
        setattr(module, name, getattr(source.module, name))
    module.ATTACHMENTS = ("EX-13",)
    return ParserSource(module)


class AttachmentFixture(snapshots.SnapshotFixture):
    def attach(self, accession, html: bytes, name=EXHIBIT, kind="EX-13", source_format="original_html"):
        digest = hashlib.sha256(html).hexdigest()
        report = self.packages[accession]["filing"]["reportDate"]
        relative = f"sec/TEST/{report}/{accession}/{digest}.html"
        (self.data / relative).parent.mkdir(parents=True, exist_ok=True)
        (self.data / relative).write_bytes(html)
        self.packages[accession]["documents"][name] = {
            "name": name,
            "path": relative,
            "sha256": digest,
            "primary": False,
            "inline_xbrl": False,
            "type": kind,
            "source_format": source_format,
            "source_url": f"https://www.sec.gov/Archives/edgar/data/1/{accession.replace('-', '')}/{name}",
            "ixviewer_url": None,
        }
        JsonCodec.write(self.data / "pipeline" / "TEST" / "packages.json", {"packages": self.packages})
        return digest

    def annual_in_exhibit(self, primary_items=(), exhibit_items=None, **options):
        """10-K 的營收 fact 在附件 EX-13，context 定義在主文件。回傳附件的 sha256。"""
        exhibit_items = exhibit_items or annual_items()
        self.add(ACCESSION, "10-K", "2025-12-31", "2026-02-15", primary_with_contexts(list(primary_items), exhibit_items))
        return self.attach(ACCESSION, exhibit(exhibit_items, **options))


class CustomizationTest(unittest.TestCase):
    def module(self, value):
        module = types.ModuleType("test_parser")
        module.TICKER, module.VIEW, module.TOTAL = "TEST", "product", "Total"
        module.compose, module.categories = (lambda f, r: None), (lambda day: [])
        if value is not None:
            module.ATTACHMENTS = value
        return module

    def test_default_is_primary_document_only(self):
        self.assertEqual(ParserSource(self.module(None)).attachments, ())

    def test_declared_exhibit_types(self):
        self.assertEqual(ParserSource(self.module(("EX-13", "EX-99.1"))).attachments, ("EX-13", "EX-99.1"))

    def test_format_is_checked(self):
        for value in (["EX-13"], (), ("13",), ("EX-101.SCH",), ("ex-13",), ("EX-13", "EX-13"), (13,), "EX-13"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "TEST 的 ATTACHMENTS"):
                ParserSource(self.module(value))


class FactListTest(AttachmentFixture):
    def test_undeclared_company_reads_primary_document_only(self):
        self.annual_in_exhibit()
        filings = FilingSet(self.data, "TEST")
        self.assertEqual(filings.filings[0].attachments, ())
        self.assertEqual(filings.document(filings.filings[0]).facts, [])
        with self.assertRaisesRegex(ParseError, r"\[fact 存在且唯一\] 找不到"):
            PeriodComposer(base.COMPANY, filings).compose_annual("2025-12-31")

    def test_exhibit_facts_use_contexts_and_units_of_the_primary_document(self):
        self.annual_in_exhibit(primary_items=[item("p1", "us-gaap:Assets", None, "2025-01-01", "2025-12-31", "5")])
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        document = filings.document(filings.filings[0])
        facts = {f.fact_id: f for f in document.facts}
        self.assertEqual((facts["p1"].document, facts["ya"].document), (None, EXHIBIT))
        self.assertEqual((facts["ya"].start, facts["ya"].end, facts["ya"].unit, facts["ya"].value), ("2025-01-01", "2025-12-31", "iso4217:USD", 190_000_000))
        # 附件的表格各自編號：附件第一張是說明表，營收在第二張。
        self.assertEqual(facts["ya"].table_index, 1)
        # 附件的 order 接在主文件之後，整份 fact 清單的順序唯一。
        self.assertGreater(min(f.order for f in document.facts if f.document), max(f.order for f in document.facts if f.document is None))
        self.assertEqual(document.fiscal(), (2025, "FY"))

    def test_fiscal_year_comes_from_primary_dei(self):
        self.annual_in_exhibit(resources='<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="c-ya">2099</ix:nonNumeric>')
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        self.assertEqual(filings.document(filings.filings[0]).fiscal(), (2025, "FY"))

    def test_only_declared_original_html_exhibits_are_read(self):
        self.annual_in_exhibit()
        self.attach(ACCESSION, exhibit([item("z1", REVENUE, None, "2025-01-01", "2025-12-31", "1")]), name="ex99.htm", kind="EX-99")
        self.attach(ACCESSION, b"<html></html>", name="ex13.pdf", kind="EX-13", source_format="sec_file")
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        self.assertEqual([a["name"] for a in filings.filings[0].attachments], [EXHIBIT])

    def test_duplicate_fact_id_fails_the_filing(self):
        self.annual_in_exhibit(primary_items=[item("ya", "us-gaap:Assets", None, "2025-01-01", "2025-12-31", "5")])
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        with self.assertRaisesRegex(ParseError, rf"\[fact 清單合併\] {ACCESSION}：fact id ya 同時出現在主文件與附件 {EXHIBIT}"):
            filings.document(filings.filings[0])

    def test_context_defined_in_two_documents_fails_the_filing(self):
        self.annual_in_exhibit(resources=context(annual_items()[0]))
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        with self.assertRaisesRegex(ParseError, r"\[fact 清單合併\].*c-ya 同時定義在主文件與附件"):
            filings.document(filings.filings[0])

    def test_prefix_bound_to_different_uris_across_documents_is_a_conflict(self):
        self.annual_in_exhibit(namespaces={**NAMESPACES, "x": "http://example.com/other"})
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        document = filings.document(filings.filings[0])
        self.assertIn("x", document.conflicts)
        self.assertIsNone(document.resolve("x:AMember"))

    def test_changed_exhibit_bytes_fail_the_sha256_check(self):
        self.annual_in_exhibit()
        path = self.data / self.packages[ACCESSION]["documents"][EXHIBIT]["path"]
        path.write_bytes(b"tampered")
        filings = FilingSet(self.data, "TEST", ("EX-13",))
        with self.assertRaisesRegex(ParseError, rf"\[原文存在\] {ACCESSION} 附件 {EXHIBIT} sha256"):
            filings.document(filings.filings[0])


class ChooseTest(AttachmentFixture):
    def test_same_table_is_identified_by_document(self):
        # 主文件與附件都有表格 1：A 的重複 fact 一個在主文件表格 1（只有 A），一個在附件表格 1（與 B、總營收同表）。
        # 同表項目數以（申報, 文件, 表格編號）計，選附件那個；不分文件時兩張表會被當成同一張而平手、取主文件。
        filler = item("p0", "us-gaap:Assets", None, "2025-01-01", "2025-12-31", "5", 0)
        duplicate = item("pa", REVENUE, A, "2025-01-01", "2025-12-31", "190", 1)
        self.annual_in_exhibit(primary_items=[filler, duplicate])
        result = PeriodComposer(declared(), FilingSet(self.data, "TEST", ("EX-13",))).compose_annual("2025-12-31")
        operand = result.lines[0].terms[0].operand
        self.assertEqual((operand.fact.fact_id, operand.fact.document), ("ya", EXHIBIT))
        self.assertEqual([d.fact_id for d in operand.duplicates], ["pa"])


class Q4BasisTest(AttachmentFixture):
    PRIOR_10K, ANNUAL_10K = base.Q4BasisTest.PRIOR_10K, base.Q4BasisTest.ANNUAL_10K

    def test_prior_report_that_cannot_merge_fails_q4(self):
        # 上一份 10-K 的主文件與附件合不成 fact 清單：與原文不符一樣是資料不完整，Q4 失敗，不當成無法判斷。
        base.Q4BasisTest.prior_report(self)
        base.Q4BasisTest.annual_report(self, (100, 100))
        self.attach(self.PRIOR_10K, exhibit([item("ya", REVENUE, A, "2024-01-01", "2024-12-31", "100")]))
        parser = self.parser(declared(), default_start="2025-01-01")
        parser.run(parser.periods())
        q4 = self.status()["periods"]["Q"]["2025-12-31"]
        self.assertEqual((q4["status"], q4["check"]), ("failed", "fact 清單合併"))
        self.assertIn(f"上一財年 10-K {self.PRIOR_10K}", q4["reason"])


class EvidenceTest(AttachmentFixture):
    def test_output_and_evidence_point_to_the_exhibit(self):
        digest = self.annual_in_exhibit()
        parser = self.parser(declared())
        parser.run(["2025-12-31"])
        self.assertEqual(self.status()["periods"]["FY"]["2025-12-31"]["status"], "published", self.status())
        output = self.output("2025-12-31", "FY")
        self.assertEqual(output["total"]["value"], 300_000_000)
        key = f"{ACCESSION}-{digest[:12]}-t1"
        for operand in output["operands"].values():
            self.assertEqual(operand["document"]["name"], EXHIBIT)
            self.assertEqual(operand["document"]["sha256"], digest)
            self.assertTrue(operand["document"]["url"].endswith(EXHIBIT))
            self.assertEqual(operand["evidence"]["table"], key)
        evidence = ticker_dir(self.out, "TEST") / "FY" / "2025-12-31" / "evidence"
        page = (evidence / f"{key}.html").read_text()
        self.assertIn(self.packages[ACCESSION]["documents"][EXHIBIT]["source_url"], page)
        self.assertTrue((evidence / f"{key}.png").is_file())
        # 截圖讀的是附件的原文。
        self.assertEqual(self.shots, [["ya", "yb", "yt"]])

    def test_snapshot_covers_the_exhibit_and_reproduces_the_output(self):
        self.annual_in_exhibit()
        source = declared()
        self.parser(source).run(["2025-12-31"])
        snapshot.write(self.data, self.snapshots, "TEST", source.attachments)
        payload = self.load(ACCESSION)
        self.assertEqual(payload["ixds"]["types"], ["EX-13"])
        self.assertEqual(payload["ixds"]["sha256"], snapshot.ixds_sha256())
        self.assertEqual([d["name"] for d in payload["ixds"]["documents"]], [EXHIBIT])
        self.assertEqual({f.get("document") for f in payload["facts"]}, {EXHIBIT})
        self.assertEqual(snapshot.check(self.data, self.snapshots, "TEST", source.attachments), [])
        self.assertEqual(self.check_from_snapshots(source), [])

    def test_undeclared_snapshot_has_no_exhibit_fields(self):
        self.annual_in_exhibit()
        snapshot.write(self.data, self.snapshots, "TEST")
        payload = self.load(ACCESSION)
        self.assertNotIn("ixds", payload)
        self.assertNotIn("attachments", payload)
        self.assertEqual(payload["facts"], [])

    def test_snapshot_must_match_the_declaration(self):
        self.annual_in_exhibit()
        snapshot.write(self.data, self.snapshots, "TEST", ("EX-13",))
        with self.assertRaisesRegex(ValueError, "涵蓋的附件與公司 parser 宣告的（沒有附件）不同"):
            snapshot.SnapshotFilingSet(self.snapshots, "TEST")
        snapshot.write(self.data, self.snapshots, "TEST")
        with self.assertRaisesRegex(ValueError, "涵蓋的附件與公司 parser 宣告的（附件類型 EX-13）不同"):
            snapshot.SnapshotFilingSet(self.snapshots, "TEST", ("EX-13",))

    def test_merge_program_change_makes_exhibit_snapshots_stale(self):
        self.annual_in_exhibit()
        snapshot.write(self.data, self.snapshots, "TEST", ("EX-13",))
        with patch("sec_revenue.revenue.snapshot.ixds_sha256", return_value="changed"):
            with self.assertRaisesRegex(ValueError, "不同版本的附件合併程式"):
                snapshot.SnapshotFilingSet(self.snapshots, "TEST", ("EX-13",))
        # 沒有宣告附件的快照不依賴合併程式。
        snapshot.write(self.data, self.snapshots, "TEST")
        with patch("sec_revenue.revenue.snapshot.ixds_sha256", return_value="changed"):
            snapshot.SnapshotFilingSet(self.snapshots, "TEST")

    def test_merge_failure_is_recorded_in_the_snapshot(self):
        self.annual_in_exhibit(primary_items=[item("ya", "us-gaap:Assets", None, "2025-01-01", "2025-12-31", "5")])
        result = snapshot.write(self.data, self.snapshots, "TEST", ("EX-13",))
        self.assertEqual(result["errors"], [ACCESSION])
        self.assertEqual(self.load(ACCESSION)["error"]["check"], "fact 清單合併")


class MergeModuleTest(unittest.TestCase):
    def test_extraction_leaves_every_parse_tree_unchanged(self):
        # 證據元件用同一批解析樹：暫時複製進去的 context 與 unit 抽取後必須移除。
        shared = annual_items()
        primary = extract.parse_html(primary_with_contexts([item("p1", "us-gaap:Assets", None, "2025-01-01", "2025-12-31", "5")], shared))
        attachment = extract.parse_html(exhibit(shared, resources=context(item("z", REVENUE, None, "2025-01-01", "2025-12-31", "1"))))
        before = [etree.tostring(primary), etree.tostring(attachment)]
        content = ixds.extract_set(primary, [(EXHIBIT, attachment)])
        self.assertEqual([etree.tostring(primary), etree.tostring(attachment)], before)
        self.assertEqual(len(content["facts"]), 4)

    def test_ixds_imports_only_lxml_stdlib_and_extract(self):
        # 涵蓋附件的快照記錄 ixds.py 與 extract.py 的 hash：ixds.py 用到的程式都必須在這兩個檔內，或來自 lxml 與標準函式庫。
        tree = ast.parse(Path(ixds.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    self.assertEqual((node.level, node.module), (1, "extract"), ast.unparse(node))
                    continue
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                self.assertTrue(top in ("__future__", "lxml") or top in sys.stdlib_module_names, f"ixds.py 不可 import {name}")


if __name__ == "__main__":
    unittest.main()
