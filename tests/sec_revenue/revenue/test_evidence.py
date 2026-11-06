"""SEC 表格證據元件：以合成 inline XBRL HTML 測試找表、表格 HTML 清理與截圖，不連網。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.revenue.evidence import TableLocator, TableScreenshotter  # noqa: E402

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

Q_ACC = "0000320193-25-000073"


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


class FactVerifyTest(unittest.TestCase):
    """`TableLocator.verify`：原文節點的 name、contextref、scale、顯示文字與數值都要與運算元相同。"""

    LEAF = {"fact_id": "f-2", "concept": CONCEPT, "context_id": "c-f-2", "scale": "6", "raw": "24,982", "value": 24982000000}

    def test_matching_fact_passes(self):
        self.assertIsNone(TableLocator(TEN_Q).verify(self.LEAF))

    def test_fact_attributes_must_match_operand(self):
        cases = {
            "contextref": dict(self.LEAF, context_id="c-other"),
            "顯示文字": dict(self.LEAF, raw="24,983"),
            "數值": dict(self.LEAF, value=24983000000),
            "name": dict(self.LEAF, concept="us-gaap:Revenues"),
            "scale": dict(self.LEAF, scale="3"),
        }
        for name, leaf in cases.items():
            with self.subTest(name):
                self.assertIn(f"{name} 不符", TableLocator(TEN_Q).verify(leaf))


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
