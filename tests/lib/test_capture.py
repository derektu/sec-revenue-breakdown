"""擷取工具的離線測試：html 清理、證據檔、合併、Stock Analysis 表格解析與擷取時間。不開瀏覽器、不連網。"""

import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT / "scripts"))
from PIL import Image

from sec_revenue.capture.evidence import clean_html, compress_png, rebuild_html, table_text
from sec_revenue.capture.merge import commit_capture, merge_reference
from sec_revenue.capture.model import CaptureError, Period
from sec_revenue.capture.runner import CaptureClock
from sec_revenue.capture.sites.stockanalysis import StockAnalysis, parse_rows
from sec_revenue.universe import COLUMNS, reference_dir, validate_universe
import capture_references as cli

PNG = b"\x89PNG\r\n\x1a\nsynthetic"


def q(label, end, **values):
    return Period(label=label, kind="Q", values=values, period_end=end)


class CleanHtmlTest(unittest.TestCase):
    def test_keeps_structure_and_text_only(self):
        fragment = (
            '<table class="x" data-user="derek" style="color:red" onclick="steal()">'
            "<!-- tracking --><thead><tr><th colspan=\"2\" class=\"h\">Date</th></tr></thead>"
            '<tbody><tr><td><a href="https://x.test/?utm_source=a">iPhone</a></td>'
            '<td><span title="Signed in as derek">57.58B</span><button>Sort</button></td></tr>'
            '<script>track()</script><tr><td><img src="https://cdn.test/p.png">Mac</td>'
            "<td><svg><text>chart</text></svg>8.40B</td></tr></tbody></table>"
        )
        out = clean_html(fragment)
        self.assertEqual(
            out,
            '<table><thead><tr><th colspan="2">Date</th></tr></thead><tbody><tr><td>iPhone</td>'
            "<td><span>57.58B</span></td></tr><tr><td>Mac</td><td>8.40B</td></tr></tbody></table>\n",
        )
        for leaked in ("derek", "utm_", "https://", "track", "Sort", "chart", "tracking", "style"):
            self.assertNotIn(leaked, out)

    def test_rejects_non_numeric_span_attributes(self):
        self.assertEqual(clean_html('<table><tr><td rowspan="x">a</td></tr></table>'),
                         "<table><tr><td>a</td></tr></table>\n")


class EvidenceTest(unittest.TestCase):
    def test_rebuild_escapes_text(self):
        self.assertEqual(
            rebuild_html([["名稱", "營收"], ["A&B <x>", "1.5億"]]),
            "<table>\n<tr><th>名稱</th><th>營收</th></tr>\n<tr><td>A&amp;B &lt;x&gt;</td><td>1.5億</td></tr>\n</table>\n",
        )

    def test_table_text_is_tab_separated(self):
        self.assertEqual(table_text([["Date", "iPhone"], ["Sep 30, 2026", "57.58\tB"]]),
                         "Date\tiPhone\nSep 30, 2026\t57.58 B\n")

    def test_compress_png_uses_palette(self):
        buffer = io.BytesIO()
        Image.new("RGB", (40, 20), (255, 255, 255)).save(buffer, format="PNG")
        out = Image.open(io.BytesIO(compress_png(buffer.getvalue())))
        self.assertEqual((out.format, out.mode, out.size), ("PNG", "P", (40, 20)))


class StockAnalysisTest(unittest.TestCase):
    def test_parse_rows(self):
        rows = [
            ["Date", "iPhone", "Corporate and Other"],
            ["Sep 30, 2026", "57.58B", "-"],
            ["Jun 30, 2026", "54.25B", "1.2M"],
            ["Mar 31, 2026", "-", "-"],
        ]
        self.assertEqual(parse_rows(rows), [
            q("Sep 30, 2026", "2026-09-30", iPhone="57.58B"),
            Period("Jun 30, 2026", "Q", {"iPhone": "54.25B", "Corporate and Other": "1.2M"}, "2026-06-30"),
        ])

    def test_parse_rows_rejects_unexpected_layout(self):
        for rows in ([], [["Year", "iPhone"], ["2026", "1B"]], [["Date", "iPhone"], ["Q3 2026", "1B"]],
                     [["Date", "iPhone"], ["Sep 30, 2026"]], [["Date", "iPhone"], ["Sep 30, 2026", "-"]]):
            with self.subTest(rows=rows), self.assertRaises(CaptureError):
                parse_rows(rows)

    def test_target_url_uses_dot_for_class_shares(self):
        site = StockAnalysis()
        self.assertEqual(site.target_url("BRK-B"),
                         "https://stockanalysis.com/stocks/brk.b/metrics/revenue-by-segment/")


class MergeTest(unittest.TestCase):
    META = {"url": "https://example.test/", "captured_at": "2026-11-05T01:00:00Z", "method": "browser_dom"}

    def test_overlap_replaces_and_orphans_are_removed(self):
        first, removed = merge_reference(None, "AAPL", "futu", "20261101T000000Z", self.META, [
            q("2026/Q2", "2026-06-30", iPhone="400億"), q("2026/Q1", "2026-03-31", iPhone="500億"),
        ])
        self.assertEqual(removed, [])
        second, removed = merge_reference(first, "AAPL", "futu", "20261102T000000Z", self.META, [
            q("2026/Q3", "2026-09-30", iPhone="600億"), q("2026/Q2", "2026-06-30", iPhone="401億"),
        ])
        self.assertEqual(removed, [])
        body = second["sources"]["futu"]
        self.assertEqual([(p["label"], p["capture"], p["values"]["iPhone"]["usd"]) for p in body["periods"]], [
            ("2026/Q3", "20261102T000000Z", 60_000_000_000),
            ("2026/Q2", "20261102T000000Z", 40_100_000_000),
            ("2026/Q1", "20261101T000000Z", 50_000_000_000),
        ])
        third, removed = merge_reference(second, "AAPL", "futu", "20261103T000000Z", self.META, [
            q("2026/Q1", "2026-03-31", iPhone="500億"),
        ])
        self.assertEqual(removed, ["20261101T000000Z"])
        fourth, removed = merge_reference(third, "AAPL", "futu", "20261104T000000Z", self.META, [
            q("2026/Q3", "2026-09-30", iPhone="600億"), q("2026/Q2", "2026-06-30", iPhone="401億"),
        ])
        self.assertEqual(removed, ["20261102T000000Z"])
        self.assertEqual(sorted(fourth["sources"]["futu"]["captures"]), ["20261103T000000Z", "20261104T000000Z"])
        self.assertIn("20261101T000000Z", first["sources"]["futu"]["captures"])  # 傳入的 reference 不被修改

    def test_same_period_end_with_new_label_replaces(self):
        first, _ = merge_reference(None, "AAPL", "futu", "20261101T000000Z", self.META,
                                   [q("Q2 2026", "2026-06-30", iPhone="1B")])
        second, removed = merge_reference(first, "AAPL", "futu", "20261102T000000Z", self.META,
                                          [q("2026/Q2", "2026-06-30", iPhone="1B")])
        self.assertEqual([p["label"] for p in second["sources"]["futu"]["periods"]], ["2026/Q2"])
        self.assertEqual(removed, ["20261101T000000Z"])

    def test_refuses_duplicate_capture_id(self):
        first, _ = merge_reference(None, "AAPL", "futu", "20261101T000000Z", self.META,
                                   [q("Q2", "2026-06-30", iPhone="1B")])
        with self.assertRaises(CaptureError):
            merge_reference(first, "AAPL", "futu", "20261101T000000Z", self.META, [q("Q3", "2026-09-30", iPhone="1B")])


class CommitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.universe = Path(self.tmp.name)
        (self.universe / "tickers.csv").write_text(",".join(COLUMNS) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, captured_at, periods, **extra):
        args = dict(url="https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/",
                    captured_at=captured_at, periods=periods, display_unit=None, png=PNG,
                    html_text="<table></table>\n", txt="Date\n")
        args.update(extra)
        return commit_capture(self.universe, "AAPL", "stockanalysis", **args)

    def test_commits_accumulate_and_remove_unreferenced_evidence(self):
        folder = reference_dir("AAPL", self.universe)
        first = self.commit("2026-11-05T01:00:00.123Z", [q("Jun 30, 2026", "2026-06-30", iPhone="54.25B")])
        self.assertEqual(first.capture, "20261105T010000Z")
        self.assertEqual(validate_universe(self.universe), [])
        second = self.commit("2026-11-05T02:00:00.456Z", [q("Jun 30, 2026", "2026-06-30", iPhone="54.25B"),
                                                          q("Sep 30, 2026", "2026-09-30", iPhone="57.58B")])
        self.assertEqual(second.removed_captures, ["20261105T010000Z"])
        self.assertFalse((folder / "captures/stockanalysis/20261105T010000Z").exists())
        self.assertEqual(validate_universe(self.universe), [])
        data = json.loads((folder / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual(list(data["sources"]["stockanalysis"]["captures"]), ["20261105T020000Z"])
        self.assertEqual([p.name for p in folder.parent.iterdir()], ["AAPL"])  # 暫存目錄已清除

    def test_failure_leaves_existing_reference_untouched(self):
        self.commit("2026-11-05T01:00:00Z", [q("Jun 30, 2026", "2026-06-30", iPhone="54.25B")])
        folder = reference_dir("AAPL", self.universe)
        before = (folder / "reference.json").read_bytes()
        with self.assertRaises(ValueError):
            self.commit("2026-11-05T02:00:00Z", [q("Jun 30, 2026", "2026-06-30", iPhone="n/a B")])
        with self.assertRaises(CaptureError):  # 同一來源同一秒
            self.commit("2026-11-05T01:00:00.900Z", [q("Sep 30, 2026", "2026-09-30", iPhone="1B")])
        self.assertEqual((folder / "reference.json").read_bytes(), before)
        self.assertEqual([p.name for p in folder.parent.iterdir()], ["AAPL"])
        self.assertEqual(validate_universe(self.universe), [])


class ClockTest(unittest.TestCase):
    def test_waits_for_next_second_within_same_source(self):
        times = iter([
            dt.datetime(2026, 11, 5, 1, 0, 0, 100_000, tzinfo=dt.timezone.utc),
            dt.datetime(2026, 11, 5, 1, 0, 0, 900_000, tzinfo=dt.timezone.utc),
            dt.datetime(2026, 11, 5, 1, 0, 1, 20_000, tzinfo=dt.timezone.utc),
            dt.datetime(2026, 11, 5, 1, 0, 1, 30_000, tzinfo=dt.timezone.utc),
        ])
        sleeps = []
        clock = CaptureClock(now=lambda: next(times), sleep=sleeps.append)
        self.assertEqual(clock.next("futu"), "2026-11-05T01:00:00.100Z")
        self.assertEqual(clock.next("futu"), "2026-11-05T01:00:01.020Z")
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 0.11)
        self.assertEqual(clock.next("stockanalysis"), "2026-11-05T01:00:01.030Z")


class CliTest(unittest.TestCase):
    def test_read_tickers_merges_sources_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.txt"
            path.write_text("msft, nvda  # 註解\n\nAAPL\n", encoding="utf-8")
            args = cli.argparse.Namespace(tickers="aapl,BRK-B", tickers_file=path)
            self.assertEqual(cli.read_tickers(args), ["AAPL", "BRK-B", "MSFT", "NVDA"])


if __name__ == "__main__":
    unittest.main()
