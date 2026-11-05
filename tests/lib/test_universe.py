"""ticker 清單與對照資料格式驗證；全部使用暫存目錄內的合成 fixture。"""

from decimal import Decimal
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT / "scripts"))
from sec_revenue.universe import (
    COLUMNS,
    UniverseError,
    capture_file_path,
    capture_id,
    load_reference,
    load_tickers,
    parse_display,
    reference_dir,
    validate_universe,
)
import validate_universe as cli

HEADER = ",".join(COLUMNS)
SA = "20261104T013829Z"      # stockanalysis 的瀏覽器擷取
FUTU = "20260730T080000Z"    # futu 的舊資料匯入
EVIDENCE = {
    "png": b"\x89PNG\r\n\x1a\nsynthetic",
    "html": b"<table><tr><td>iPhone</td><td>57.58B</td></tr></table>",
    "txt": b"iPhone\t57.58B\n",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ticker_line(ticker, cik="320193", status="wip", source="", score="", name="Synthetic Inc."):
    return f"{ticker},{cik},{name},{status},{source},{score},,"


def files_entry(source, cid, evidence=EVIDENCE):
    return {kind: {"path": capture_file_path(source, cid, kind), "sha256": sha(data)}
            for kind, data in evidence.items()}


def reference(ticker="AAPL"):
    return {
        "schema_version": 1,
        "ticker": ticker,
        "sources": {
            "stockanalysis": {
                "captures": {
                    SA: {
                        "url": "https://example.test/segments",
                        "captured_at": "2026-11-04T01:38:29.259Z",
                        "method": "browser_dom",
                        "files": files_entry("stockanalysis", SA),
                    }
                },
                "periods": [
                    {
                        "label": "Q3 2026",
                        "period_end": "2026-09-30",
                        "kind": "Q",
                        "capture": SA,
                        "values": {"iPhone": {"display": "57.58B", "usd": 57_580_000_000}},
                    },
                    {
                        "label": "FY 2025",
                        "period_end": "2025-09-27",
                        "kind": "FY",
                        "capture": SA,
                        "values": {"Services": {"display": "(1,234.5)M", "usd": -1_234_500_000}},
                    },
                ],
            },
            "futu": {
                "captures": {
                    FUTU: {"captured_at": "2026-07-30T08:00:00Z", "method": "legacy_import"},
                },
                "periods": [
                    {
                        "label": "2026/Q3",
                        "period_end": "2026-09-30",
                        "kind": "Q",
                        "capture": FUTU,
                        "values": {"汽車分部": {"display": "212.05億", "usd": 21_205_000_000}},
                    }
                ],
            },
        },
    }


def sa(data):
    return data["sources"]["stockanalysis"]


def futu(data):
    return data["sources"]["futu"]


class UniverseFixture:
    def __init__(self, root: Path):
        self.root = root
        self.write_csv([
            ticker_line("AAPL"),
            ticker_line("BRK-B", cik="1067983;34088", source="futu", score="5"),
        ])

    @property
    def csv_path(self):
        return self.root / "tickers.csv"

    def write_csv(self, lines):
        self.csv_path.write_text("\n".join([HEADER, *lines]) + "\n", encoding="utf-8")

    def write_evidence(self, ticker, source, cid, evidence=EVIDENCE, folder=None):
        folder = folder or reference_dir(ticker, self.root)
        for kind, data in evidence.items():
            path = folder / capture_file_path(source, cid, kind)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def write_reference(self, ticker, data, folder=None, evidence=True):
        folder = folder or reference_dir(ticker, self.root)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reference.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if evidence:
            self.write_evidence(ticker, "stockanalysis", SA, folder=folder)
        return folder


class UniverseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = UniverseFixture(Path(self.tmp.name))

    def errors(self):
        return validate_universe(self.fx.root)

    def assertReported(self, fragment, errors=None):
        errors = self.errors() if errors is None else errors
        self.assertTrue(any(fragment in e for e in errors), f"未回報 {fragment!r}：{errors}")

    def assertClean(self):
        self.assertEqual(self.errors(), [])

    def write_aapl(self, mutate, evidence=True):
        data = reference()
        mutate(data)
        return self.fx.write_reference("AAPL", data, evidence=evidence)


class ParseDisplayTests(unittest.TestCase):
    def test_units_separators_and_negative_forms(self):
        cases = {
            "57.58B": Decimal("57580000000"),
            "1.2T": Decimal("1200000000000"),
            "950K": Decimal("950000"),
            "3,456.7M": Decimal("3456700000"),
            "212.05億": Decimal("21205000000"),
            "8,500萬": Decimal("85000000"),
            "-1.5B": Decimal("-1500000000"),
            "−1.5B": Decimal("-1500000000"),
            "(1.5B)": Decimal("-1500000000"),
            "(1,234.5)M": Decimal("-1234500000"),
            "$1,234": Decimal("1234"),
            "1.5 B": Decimal("1500000000"),
            "0": Decimal("0"),
        }
        for display, usd in cases.items():
            with self.subTest(display=display):
                self.assertEqual(parse_display(display).usd, usd)

    def test_tolerance_is_half_of_last_displayed_digit(self):
        self.assertEqual(parse_display("57.58B").tolerance, Decimal("5000000"))
        self.assertEqual(parse_display("57B").tolerance, Decimal("500000000"))
        self.assertEqual(parse_display("212.05億").tolerance, Decimal("500000"))
        self.assertEqual(parse_display("1,234").tolerance, Decimal("0.5"))

    def test_default_unit_applies_only_to_unitless_display(self):
        self.assertEqual(parse_display("57,583", "M"), parse_display("57,583M"))
        self.assertEqual(parse_display("57,583", "M").tolerance, Decimal("500000"))
        self.assertEqual(parse_display("57.58B", "M").usd, Decimal("57580000000"))
        self.assertEqual(parse_display("(12.5)", "億").usd, Decimal("-1250000000"))
        with self.assertRaises(ValueError):
            parse_display("1", "T")

    def test_unparseable_display_raises(self):
        bad = ["", "-", "N/A", "1.2X", "12,34B", "1..2B",
               "５７B", "٥٧B", "57.58 B", " 57B", "1 2B"]
        for display in bad:
            with self.subTest(display=display), self.assertRaises(ValueError):
                parse_display(display)


class PathHelperTests(unittest.TestCase):
    def test_reference_dir_uses_initial_letter_and_verbatim_ticker(self):
        root = Path("/u")
        self.assertEqual(reference_dir("BRK-B", root), root / "references" / "B" / "BRK-B")
        self.assertEqual(reference_dir("AAPL", root), root / "references" / "A" / "AAPL")
        for bad in ["brk-b", "BRK.B", "A.", "A--", "A-"]:
            with self.subTest(ticker=bad), self.assertRaises(ValueError):
                reference_dir(bad, root)

    def test_capture_id_truncates_to_seconds(self):
        self.assertEqual(capture_id("2026-11-04T01:38:29.999Z"), "20261104T013829Z")
        self.assertEqual(capture_id("2026-11-04T01:38:29+00:00"), "20261104T013829Z")
        with self.assertRaises(ValueError):
            capture_id("2026-11-04T09:38:29+08:00")

    def test_capture_file_path(self):
        self.assertEqual(capture_file_path("futu", FUTU, "html"), f"captures/futu/{FUTU}/table.html")


class RepoUniverseTests(unittest.TestCase):
    def test_repo_universe_passes(self):
        self.assertEqual(validate_universe(ROOT / "data" / "universe"), [])

    def test_csv_cik_matches_registry_submission_ciks(self):
        # registry.json 移除後（T3）刪除此測試。
        registry = json.loads((ROOT / "libs" / "sec_revenue" / "registry.json").read_text(encoding="utf-8"))
        entries = {e.ticker: e for e in load_tickers(ROOT / "data" / "universe" / "tickers.csv")}
        shared = sorted(set(entries) & set(registry))
        self.assertTrue(shared)
        for ticker in shared:
            with self.subTest(ticker=ticker):
                self.assertEqual(list(entries[ticker].ciks), registry[ticker]["submission_ciks"])


class ValidUniverseTests(UniverseTestCase):
    def test_valid_csv_and_reference_pass_and_load(self):
        self.fx.write_reference("AAPL", reference("AAPL"))
        self.fx.write_reference("BRK-B", reference("BRK-B"))
        self.assertClean()
        entries = load_tickers(self.fx.csv_path)
        brk = entries[1]
        self.assertEqual((brk.ticker, brk.ciks, brk.status, brk.adopted_source, brk.stability_score),
                         ("BRK-B", ("1067983", "34088"), "wip", "futu", 5))
        self.assertIsNone(entries[0].adopted_source)
        self.assertIsNone(entries[0].stability_score)
        data = load_reference("BRK-B", self.fx.root)
        self.assertEqual(sa(data)["captures"][SA]["captured_at"], "2026-11-04T01:38:29.259Z")
        self.assertEqual(futu(data)["periods"][0]["values"]["汽車分部"]["usd"], 21_205_000_000)

    def test_reference_without_csv_entry_passes(self):
        self.fx.write_reference("MSFT", reference("MSFT"))
        self.fx.write_reference("BRK-B", reference("BRK-B"))
        self.assertClean()

    def test_accumulated_captures_each_period_points_to_its_capture(self):
        newer = "20261105T020000Z"

        def mutate(d):
            source = futu(d)
            source["captures"][newer] = {
                "url": "https://example.test/futu",
                "captured_at": "2026-11-05T02:00:00.5Z",
                "method": "browser_dom",
                "display_unit": "億",
                "files": files_entry("futu", newer),
            }
            source["periods"].append({
                "label": "2026/Q4", "kind": "Q", "capture": newer,
                "values": {"汽車分部": {"display": "230.10", "usd": 23_010_000_000}},
            })
        self.write_aapl(mutate)
        self.fx.write_evidence("AAPL", "futu", newer)
        self.assertClean()

    def test_tolerance_boundary(self):
        iphone = lambda d: sa(d)["periods"][0]["values"]["iPhone"]
        self.write_aapl(lambda d: iphone(d).update(usd=57_585_000_000))
        self.assertClean()
        self.write_aapl(lambda d: iphone(d).update(usd=57_575_000_000))
        self.assertClean()
        self.write_aapl(lambda d: iphone(d).update(usd=57_585_000_001))
        self.assertReported("換算超出誤差")

    def test_zero_display_and_unicode_minus(self):
        def mutate(d):
            values = sa(d)["periods"][0]["values"]
            values["Zero"] = {"display": "0", "usd": 0}
            values["Minus"] = {"display": "−2.5M", "usd": -2_500_000}
        self.write_aapl(mutate)
        self.assertClean()

    def test_captured_at_forms(self):
        for stamp in ["2026-07-30T08:00:00Z", "2026-07-30T08:00:00.259Z",
                      "2026-07-30T08:00:00+00:00", "2026-07-30T08:00:00.259123+00:00"]:
            with self.subTest(stamp=stamp):
                self.write_aapl(lambda d: futu(d)["captures"][FUTU].update(captured_at=stamp))
                self.assertClean()

    def test_period_without_period_end(self):
        def mutate(d):
            periods = futu(d)["periods"]
            del periods[0]["period_end"]
            periods.append({"label": "2026/Q1", "kind": "Q", "capture": FUTU,
                            "values": {"汽車分部": {"display": "200億", "usd": 20_000_000_000}}})
        self.write_aapl(mutate)
        self.assertClean()

    def test_display_unit_follows_the_period_capture(self):
        other = "20261104T020000Z"

        def mutate(d):
            source = sa(d)
            source["captures"][SA]["display_unit"] = "M"
            source["captures"][other] = {"captured_at": "2026-11-04T02:00:00Z", "method": "manual"}
            source["periods"][0]["values"] = {
                "iPhone": {"display": "57,583", "usd": 57_583_000_000},
                "Mac": {"display": "8.7B", "usd": 8_700_000_000},
                "Edge": {"display": "1.5", "usd": 1_500_500},
            }
            source["periods"][1].update(capture=other, values={"Services": {"display": "1,234", "usd": 1234}})
        self.write_aapl(mutate)
        self.assertClean()

    def test_same_period_in_different_sources_is_allowed(self):
        self.fx.write_reference("AAPL", reference())
        self.assertClean()

    def test_status_ok_with_existing_source_passes(self):
        self.fx.write_csv([ticker_line("AAPL", status="ok", source="futu", score="3")])
        self.fx.write_reference("AAPL", reference())
        self.assertClean()

    def test_blank_lines_and_dotfiles_are_skipped(self):
        self.fx.csv_path.write_text(f"{HEADER}\n\n{ticker_line('AAPL')}\n \n", encoding="utf-8")
        folder = self.fx.write_reference("AAPL", reference())
        for path in [folder / ".DS_Store", folder / "captures" / ".DS_Store",
                     folder / "captures" / "stockanalysis" / SA / ".DS_Store"]:
            path.write_text("x", encoding="utf-8")
        self.assertClean()

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--universe-dir", str(self.fx.root)]), 0)
        self.fx.write_csv([ticker_line("AAPL", status="live")])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["--universe-dir", str(self.fx.root)]), 1)
        self.assertIn("status", out.getvalue())


class CsvErrorTests(UniverseTestCase):
    def test_invalid_status(self):
        self.fx.write_csv([ticker_line("AAPL", status="live")])
        self.assertReported("status 'live'")

    def test_score_out_of_range(self):
        for score in ["0", "6", "4.5", "x", "５"]:
            with self.subTest(score=score):
                self.fx.write_csv([ticker_line("AAPL", score=score)])
                self.assertReported(f"stability_score {score!r}")

    def test_ticker_format(self):
        for ticker in ["aapl", "1ABC", "BRK B", "BRK/B", "BRK.B", "A.", "A--", "A-", "-A", "ＡＡＰＬ"]:
            with self.subTest(ticker=ticker):
                self.fx.write_csv([ticker_line(ticker)])
                self.assertReported("不符合")

    def test_other_csv_errors(self):
        self.fx.write_csv([
            ticker_line("AAPL", source="yahoo"),
            ticker_line("AAPL"),
            ticker_line("MSFT", cik="0789019"),
            ticker_line("NVDA", cik=""),
            ticker_line("META", name=""),
            ticker_line("ORCL", cik="１３４１４３９"),
            "TSLA,1318605,Tesla",
        ])
        for fragment in ["adopted_source 'yahoo'", "與第 2 行重複", "cik '0789019'", "cik 不可空白",
                         "name 不可空白", "cik '１３４１４３９'", "欄位數須為 8"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_header_must_match_column_order(self):
        self.fx.csv_path.write_text("cik,ticker\n1,AAPL\n", encoding="utf-8")
        self.assertReported("表頭須為")

    def test_non_utf8_csv_reported_not_raised(self):
        content = f"{HEADER}\nAAPL,320193,蘋果公司,wip,,,,\n"
        self.fx.csv_path.write_bytes(content.encode("cp950"))
        self.assertReported("須為 UTF-8")
        with self.assertRaises(UniverseError):
            load_tickers(self.fx.csv_path)

    def test_csv_syntax_error_reported(self):
        # 超過 csv 模組欄位長度上限（預設 131072 字元）時 csv.reader 丟出 csv.Error。
        self.fx.csv_path.write_text(f"{HEADER}\n{ticker_line('AAPL')}\nMSFT,1,{'x' * 200_000},wip,,,,\n",
                                    encoding="utf-8")
        self.assertReported(":3: CSV 格式錯誤")

    def test_errors_report_actual_file_line(self):
        self.fx.csv_path.write_text(
            "\n".join([
                HEADER,                                   # 1
                "",                                       # 2
                ticker_line("AAPL"),                      # 3
                'MSFT,789019,"Micro\nsoft",wip,,,,',      # 4–5
                "",                                       # 6
                ticker_line("NVDA", status="live"),       # 7
            ]) + "\n",
            encoding="utf-8",
        )
        errors = self.errors()
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].endswith(":7: status 'live' 須為 wip/ok/drop"), errors)

    def test_status_ok_requires_adopted_source_and_score(self):
        self.fx.write_csv([ticker_line("AAPL", status="ok")])
        self.assertReported("status 為 ok 時 adopted_source 必填")
        self.assertReported("status 為 ok 時 stability_score 必填")

    def test_status_ok_adopted_source_must_exist_in_reference(self):
        self.fx.write_csv([ticker_line("AAPL", status="ok", source="tradingview", score="4")])
        self.assertReported("不在 AAPL 對照檔的來源中（現有：無對照檔）")
        self.fx.write_reference("AAPL", reference())
        self.assertReported("不在 AAPL 對照檔的來源中（現有：futu, stockanalysis）")

    def test_wip_and_drop_skip_adoption_checks(self):
        self.fx.write_csv([ticker_line("AAPL", status="drop", source="tradingview"), ticker_line("MSFT", status="wip")])
        self.assertClean()

    def test_load_tickers_raises_with_all_errors(self):
        self.fx.write_csv([ticker_line("AAPL", status="live", score="9")])
        with self.assertRaises(UniverseError) as ctx:
            load_tickers(self.fx.csv_path)
        self.assertEqual(len(ctx.exception.errors), 2)


class ReferenceErrorTests(UniverseTestCase):
    def test_directory_mismatch(self):
        folder = self.fx.root / "references" / "X" / "AAPL"
        self.fx.write_reference("AAPL", reference("AAPL"), folder=folder)
        self.assertReported("應位於")

    def test_reference_ticker_differs_from_directory(self):
        self.fx.write_reference("AAPL", reference("BRK-B"))
        self.assertReported("與目錄 AAPL 不一致")

    def test_conversion_outside_tolerance(self):
        def mutate(d):
            sa(d)["periods"][0]["values"]["iPhone"]["usd"] = 57_585_000_001
            futu(d)["periods"][0]["values"]["汽車分部"]["usd"] = 2_120_500_000
        self.write_aapl(mutate)
        self.assertEqual(sum("換算超出誤差" in e for e in self.errors()), 2)

    def test_zero_usd_is_judged_by_tolerance(self):
        def mutate(d):
            values = sa(d)["periods"][0]["values"]
            values["Small"] = {"display": "0.4", "usd": 0}
            values["Mac"] = {"display": "8.7B", "usd": 0}
        self.write_aapl(mutate)
        self.assertEqual(sum("換算超出誤差" in e for e in self.errors()), 2)

    def test_empty_or_non_integer_values(self):
        def mutate(d):
            values = sa(d)["periods"][0]["values"]
            values["iPad"] = {"display": "", "usd": 0}
            values["Other"] = {"display": "1.0B", "usd": None}
            values["Float"] = {"display": "1.0B", "usd": 1e9}
            values["Bool"] = {"display": "1", "usd": True}
        self.write_aapl(mutate)
        self.assertReported("display 須為非空字串")
        self.assertEqual(sum("usd 須為整數" in e for e in self.errors()), 3)

    def test_unitless_decimal_display_needs_display_unit(self):
        self.write_aapl(lambda d: sa(d)["periods"][0]["values"].update(
            Cents={"display": "1,234.56", "usd": 1235}))
        self.assertReported("換算超出誤差")

    def test_display_unit_errors(self):
        self.write_aapl(lambda d: sa(d)["captures"][SA].update(display_unit="T"))
        self.assertReported("display_unit 'T'")

    def test_display_unit_tolerance(self):
        def mutate(d):
            sa(d)["captures"][SA]["display_unit"] = "M"
            sa(d)["periods"][0]["values"] = {"iPhone": {"display": "57,583", "usd": 57_583_500_001}}
        self.write_aapl(mutate)
        self.assertReported("換算超出誤差")

    def test_duplicate_period_within_source(self):
        def mutate(d):
            periods = sa(d)["periods"]
            periods.append(copy.deepcopy(periods[0]))
            periods.append(dict(copy.deepcopy(periods[1]), label="FY 2025 again"))
        self.write_aapl(mutate)
        self.assertReported("label 'Q3 2026' 與 periods[0] 重複")
        self.assertReported("kind FY 期末 2025-09-27 與 periods[1] 重複")

    def test_duplicate_label_without_period_end(self):
        def mutate(d):
            periods = futu(d)["periods"]
            del periods[0]["period_end"]
            periods.append(copy.deepcopy(periods[0]))
        self.write_aapl(mutate)
        self.assertReported("label '2026/Q3' 與 periods[0] 重複")

    def test_unhashable_period_fields_do_not_crash(self):
        def mutate(d):
            periods = sa(d)["periods"]
            periods[0]["kind"] = ["Q"]
            periods[1]["period_end"] = {"y": 2025}
            periods.append({"label": ["x"], "kind": "Q", "capture": SA,
                            "values": {"a": {"display": "1", "usd": 1}}})
            periods.append({"label": "y", "kind": "Q", "capture": [SA],
                            "values": {"a": {"display": "1", "usd": 1}}})
        self.write_aapl(mutate)
        for fragment in ["kind ['Q']", "period_end {'y': 2025}", "label 須為非空字串", "capture ['"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_empty_sources_captures_periods_values(self):
        self.write_aapl(lambda d: d.update(sources={}))
        self.assertReported("sources 至少須有一個來源")
        self.write_aapl(lambda d: futu(d).update(periods=[]))
        self.assertReported("periods 至少須有一期")
        self.write_aapl(lambda d: futu(d).update(captures={}))
        self.assertReported("captures 至少須有一次擷取")
        self.write_aapl(lambda d: futu(d)["periods"][0].update(values={}))
        self.assertReported("values 須為非空物件")

    def test_period_capture_reference(self):
        def mutate(d):
            sa(d)["periods"][0]["capture"] = "20990101T000000Z"
            del sa(d)["periods"][1]["capture"]
        self.write_aapl(mutate)
        self.assertReported("periods[0]: capture '20990101T000000Z' 須為同來源 captures 中的擷取")
        self.assertReported("periods[1]: capture None")
        self.assertReported("沒有任何期別引用此擷取")

    def test_capture_of_other_source_is_not_referenceable(self):
        self.write_aapl(lambda d: futu(d)["periods"][0].update(capture=SA))
        self.assertReported("須為同來源 captures 中的擷取")

    def test_unreferenced_capture(self):
        extra = "20260101T000000Z"
        self.write_aapl(lambda d: futu(d)["captures"].update(
            {extra: {"captured_at": "2026-01-01T00:00:00Z", "method": "manual"}}))
        self.assertReported(f"captures['{extra}']: 沒有任何期別引用此擷取")

    def test_capture_id_format_and_consistency(self):
        def mutate(d):
            captures = futu(d)["captures"]
            captures["2026-07-30"] = {"captured_at": "2026-07-30T08:00:00Z", "method": "manual"}
            captures["20260730T080001Z"] = {"captured_at": "2026-07-30T08:00:00.999Z", "method": "manual"}
            futu(d)["periods"].append({"label": "a", "kind": "Q", "capture": "2026-07-30",
                                       "values": {"x": {"display": "1", "usd": 1}}})
            futu(d)["periods"].append({"label": "b", "kind": "Q", "capture": "20260730T080001Z",
                                       "values": {"x": {"display": "1", "usd": 1}}})
        self.write_aapl(mutate)
        self.assertReported("capture_id 須為 YYYYMMDDTHHMMSSZ")
        self.assertReported("capture_id 須與 captured_at 取到秒一致（應為 20260730T080000Z）")

    def test_capture_metadata_errors(self):
        def mutate(d):
            capture = sa(d)["captures"][SA]
            capture["method"] = "scrape"
            capture["url"] = "http://insecure.test"
            capture["extra"] = 1
            del futu(d)["captures"][FUTU]["captured_at"]
        self.write_aapl(mutate)
        for fragment in ["method 'scrape'", "url 須為 https://", "未定義的欄位 'extra'", "captured_at None"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_browser_dom_requires_url_and_all_files(self):
        def mutate(d):
            capture = sa(d)["captures"][SA]
            del capture["url"]
            del capture["files"]["png"]
        self.write_aapl(mutate)
        self.assertReported("method 為 browser_dom 時須有 url")
        self.assertReported("files: 缺少 png")
        self.assertReported("table.png: 證據檔未被 reference.json 引用")
        self.write_aapl(lambda d: sa(d)["captures"][SA].pop("files"))
        self.assertReported("method 為 browser_dom 時須有 files")

    def test_non_browser_capture_must_not_have_files(self):
        def mutate(d):
            futu(d)["captures"][FUTU]["files"] = files_entry("futu", FUTU)
        self.write_aapl(mutate)
        self.assertReported("method 為 legacy_import 時不得有 files")

    def test_evidence_path_hash_and_presence(self):
        def mutate(d):
            files = sa(d)["captures"][SA]["files"]
            files["png"]["path"] = f"captures/stockanalysis/{SA}/shot.png"
            files["html"]["sha256"] = "0" * 64
            files["extra"] = {}
        self.write_aapl(mutate)
        for fragment in [f"png: path 須為 captures/stockanalysis/{SA}/table.png", "html: sha256 不符",
                         "files: 未定義的欄位 'extra'"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)
        folder = self.write_aapl(lambda d: None)
        (folder / capture_file_path("stockanalysis", SA, "txt")).unlink()
        self.assertReported("txt: 找不到")

    def test_tampered_evidence_detected(self):
        folder = self.fx.write_reference("AAPL", reference())
        (folder / capture_file_path("stockanalysis", SA, "png")).write_bytes(b"other")
        self.assertReported("png: sha256 不符")

    def test_capture_tree_whitelist_and_orphans(self):
        folder = self.fx.write_reference("AAPL", reference())
        captures = folder / "captures"
        (captures / "yahoo").mkdir()
        (captures / "notes.txt").write_text("x", encoding="utf-8")
        (captures / "futu" / "latest").mkdir(parents=True)
        (captures / "stockanalysis" / SA / "full-page.html").write_text("x", encoding="utf-8")
        self.fx.write_evidence("AAPL", "stockanalysis", "20250101T000000Z")
        (captures / "futu" / FUTU).mkdir()
        (captures / "futu" / FUTU / "table.txt").write_text("x", encoding="utf-8")
        for fragment in ["yahoo: captures/ 下只能有來源目錄", "notes.txt: captures/ 下只能有來源目錄",
                         "latest: 來源目錄下只能有 capture_id", "full-page.html: 擷取目錄只能放",
                         "20250101T000000Z: 擷取目錄未被 reference.json 引用",
                         f"{FUTU}/table.txt: 證據檔未被 reference.json 引用"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_ticker_directory_whitelist(self):
        folder = self.fx.write_reference("AAPL", reference())
        (folder / "notes.txt").write_text("x", encoding="utf-8")
        (folder / "stockanalysis.snapshot.txt").write_text("x", encoding="utf-8")
        (folder / "captures2").mkdir()
        for name in ["notes.txt", "stockanalysis.snapshot.txt", "captures2"]:
            with self.subTest(name=name):
                self.assertReported(f"{name}: ticker 目錄只能放 reference.json 與 captures/")

    def test_obsolete_fields_are_rejected(self):
        def mutate(d):
            sa(d)["url"] = "https://example.test"
            sa(d)["snapshot"] = {}
            sa(d)["periods"][0]["captured_at"] = "2026-11-04T00:00:00Z"
        self.write_aapl(mutate)
        for fragment in ["sources.stockanalysis: 未定義的欄位 'snapshot'",
                         "sources.stockanalysis: 未定義的欄位 'url'",
                         "periods[0]: 未定義的欄位 'captured_at'"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_captured_at_errors(self):
        for stamp in ["2026-11-04 00:00", "2026-11-04T01:38:29", "2026-11-04T01:38:29+08:00",
                      "2026-11-04T01:38:29-00:00", "2026-02-30T00:00:00Z", "２０２６-11-04T00:00:00Z", 0]:
            with self.subTest(stamp=stamp):
                self.write_aapl(lambda d: futu(d)["captures"][FUTU].update(captured_at=stamp))
                self.assertReported("captured_at")

    def test_schema_version_must_be_int_one(self):
        for version in [2, True, 1.0, "1", None]:
            with self.subTest(version=version):
                self.write_aapl(lambda d: d.update(schema_version=version))
                self.assertReported("schema_version")

    def test_schema_field_errors(self):
        def mutate(d):
            d["sources"]["yahoo"] = d["sources"].pop("futu")
            sa(d)["periods"][0]["kind"] = "H1"
            sa(d)["periods"][1]["period_end"] = "2025-02-30"
            sa(d)["periods"][1]["extra"] = 1
        self.write_aapl(mutate)
        for fragment in ["sources.yahoo: 來源須為", "kind 'H1'", "period_end '2025-02-30'", "未定義的欄位 'extra'"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)

    def test_duplicate_json_keys(self):
        folder = self.fx.write_reference("AAPL", reference())
        text = (folder / "reference.json").read_text(encoding="utf-8")
        text = text.replace('"iPhone": {', '"iPhone": {"display": "1B", "usd": 1000000000}, "iPhone": {', 1)
        text = text.replace('"futu": {', '"tradingview": {}, "futu": {', 1).replace('"tradingview": {}', '"futu": {}', 1)
        (folder / "reference.json").write_text(text, encoding="utf-8")
        self.assertReported("重複的鍵 'iPhone'")
        self.assertReported("重複的鍵 'futu'")

    def test_unreadable_reference_reported_not_raised(self):
        folder = reference_dir("AAPL", self.fx.root)
        (folder / "reference.json").mkdir(parents=True)
        self.assertReported("reference.json: 無法讀取")
        with self.assertRaises(UniverseError):
            load_reference("AAPL", self.fx.root)

    def test_all_errors_reported_together(self):
        self.fx.write_csv([ticker_line("AAPL", status="live")])
        folder = self.write_aapl(lambda d: sa(d)["periods"][0]["values"]["iPhone"].update(usd=1))
        (folder / capture_file_path("stockanalysis", SA, "txt")).write_bytes(b"other")
        self.fx.write_reference("M", reference("MSFT"))
        errors = self.errors()
        for fragment in ["status 'live'", "換算超出誤差", "txt: sha256 不符", "與目錄 M 不一致"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment, errors)

    def test_layout_errors(self):
        refs = self.fx.root / "references"
        # 名稱避開大小寫衝突：macOS 預設檔案系統不分大小寫。
        (refs / "xy").mkdir(parents=True)
        (refs / "A" / "A_B").mkdir(parents=True)
        (refs / "B" / "BRK-B").mkdir(parents=True)
        (refs / "stray.json").write_text("{}", encoding="utf-8")
        for fragment in ["首字母目錄須為單一大寫字母", "不符合 ticker 格式", "缺少 reference.json",
                         "只能有首字母目錄"]:
            with self.subTest(fragment=fragment):
                self.assertReported(fragment)


if __name__ == "__main__":
    unittest.main()
