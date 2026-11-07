import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sec_pipeline.py"
spec = importlib.util.spec_from_file_location("sec_pipeline_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
from sec_revenue.revenue.source import ParserSource  # noqa: E402


class DataRootTest(unittest.TestCase):
    def test_defaults_to_repo_data(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.data_root(), cli.ROOT / "data")

    def test_sec_data_dir_expands_home(self):
        with mock.patch.dict(os.environ, {"SEC_DATA_DIR": "~/shared-sec"}, clear=True):
            self.assertEqual(cli.data_root(), Path.home() / "shared-sec")

    def test_blank_value_falls_back(self):
        with mock.patch.dict(os.environ, {"SEC_DATA_DIR": "  "}, clear=True):
            self.assertEqual(cli.data_root(), cli.ROOT / "data")


class ParseArgumentsTest(unittest.TestCase):
    def run_cli(self, *argv):
        with mock.patch("sys.argv", ["sec_pipeline.py", *argv]), mock.patch("sys.stderr") as stderr:
            code = cli.WorkflowCli().run()
        return code, "".join(call.args[0] for call in stderr.write.call_args_list)

    def test_start_may_be_earlier_than_default(self):
        with tempfile.TemporaryDirectory() as temp:
            data, out = Path(temp) / "data", Path(temp) / "revenue"
            (data / "pipeline" / "AAPL").mkdir(parents=True)
            (data / "pipeline" / "AAPL" / "packages.json").write_text('{"packages": {}}')
            common = ("parse", "--tickers", "AAPL", "--start", "2023-01-01", "--data", str(data), "--out", str(out))
            with mock.patch("sys.stdout"):
                self.assertEqual(self.run_cli(*common, "--check")[0], 0)
                # --republish 照一般規則：期別必須在這次處理的範圍內。
                code, message = self.run_cli(*common, "--republish", "AAPL", "Q", "2023-07-01")
            self.assertEqual(code, 1)
            self.assertIn("不在這次處理的期別中", message)

    def test_invalid_parser_stops_only_that_ticker(self):
        # BAD 的 DURATION_DAYS 不合理：BAD 記為錯誤、AAPL 照常處理，結束碼 2。
        bad = types.ModuleType("bad")
        bad.TICKER, bad.VIEW, bad.TOTAL, bad.DURATION_DAYS = "BAD", "product", "Total", {"quarter": (84, 119)}
        real = cli.companies.parser_source

        def parser_source(ticker):
            return ParserSource(bad) if ticker == "BAD" else real(ticker)

        with tempfile.TemporaryDirectory() as temp:
            data, out = Path(temp) / "data", Path(temp) / "revenue"
            (data / "pipeline" / "AAPL").mkdir(parents=True)
            (data / "pipeline" / "AAPL" / "packages.json").write_text('{"packages": {}}')
            with (
                mock.patch.object(cli.companies, "tickers", return_value=["AAPL", "BAD"]),
                mock.patch.object(cli.companies, "parser_source", parser_source),
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                code, message = self.run_cli("parse", "--tickers", "BAD", "AAPL", "--data", str(data), "--out", str(out))
            reports = {r["ticker"]: r for r in json.loads(stdout.getvalue())["companies"]}
            self.assertEqual(code, 2)
            self.assertTrue(reports["AAPL"]["complete"])
            self.assertTrue((out / "A" / "AAPL" / "status.json").exists())
            self.assertFalse(reports["BAD"]["complete"])
            self.assertIn("BAD 的 DURATION_DAYS", reports["BAD"]["error"])
            self.assertIn("BAD：BAD 的 DURATION_DAYS", message)


def aapl_data(temp: str) -> tuple[Path, Path]:
    """AAPL 沒有申報的資料根目錄與輸出目錄：AAPL 照常處理並寫出 status.json。"""
    data, out = Path(temp) / "data", Path(temp) / "revenue"
    (data / "pipeline" / "AAPL").mkdir(parents=True)
    (data / "pipeline" / "AAPL" / "packages.json").write_text('{"packages": {}}')
    return data, out


@contextlib.contextmanager
def companies_with(root: Path, sources: dict[str, str]):
    """公司目錄是 AAPL 加上 `root` 下的 `<首字母>/<目錄>/parser.py`（`sources` 是 {目錄: 內容}）。

    暫存目錄不在套件路徑內，這些 parser.py 以檔案載入；載入的錯誤照樣經過 `companies.declared` 處理。
    """
    extra = []
    for name, text in sources.items():
        directory = root / name[0] / name
        directory.mkdir(parents=True)
        (directory / "parser.py").write_text(text)
        extra.append(directory)
    real_module, real_dir = cli.companies.module, cli.companies.module_dir

    def module(directory):
        if directory not in extra:
            return real_module(directory)
        spec = importlib.util.spec_from_file_location(f"temp_parser_{directory.name}", directory / "parser.py")
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        return loaded

    def module_dir(ticker):
        found = root / ticker[0].lower() / ticker.lower()
        return found if found in extra else real_dir(ticker)

    with (
        mock.patch.object(cli.companies, "directories", return_value=[real_dir("AAPL"), *extra]),
        mock.patch.object(cli.companies, "module", module),
        mock.patch.object(cli.companies, "module_dir", module_dir),
    ):
        yield


# 三種載入失敗：語法錯誤、import 不存在的模組、缺少 TICKER。
BROKEN = {
    "zbad": 'TICKER = "ZBAD"\nVIEW = "product"\nTOTAL = "Total"\ndef compose(:\n',
    "ymiss": "import sec_revenue.no_such_module\n",
    "xnone": 'VIEW = "product"\nTOTAL = "Total"\n',
}


class ParserLoadFailureTest(unittest.TestCase):
    """parser.py 載入失敗只停那一家：其他 ticker 照常產出，結束碼 2，錯誤列出檔案。"""

    run_cli = ParseArgumentsTest.run_cli

    def parse(self, root: Path, *argv, sources=BROKEN, entries=False):
        with tempfile.TemporaryDirectory() as temp:
            data, out = aapl_data(temp)
            with companies_with(root, sources), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                code, message = self.run_cli("parse", *argv, "--data", str(data), "--out", str(out))
            reports = json.loads(stdout.getvalue())["companies"]
            self.assertTrue((out / "A" / "AAPL" / "status.json").exists())
        return code, message, reports if entries else {r["ticker"]: r for r in reports}

    def test_same_name_failures_are_all_reported(self):
        # 載入失敗的檔案宣告的 TICKER 與正常的 AAPL 相同，另有兩個檔案都宣告 DUP：每一個都報出，結束碼 2。
        sources = {"waapl": 'TICKER = "AAPL"\n', "vdup1": 'TICKER = "DUP"\n', "vdup2": 'TICKER = "DUP"\n'}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for argv in (["--all"], ["--tickers", "AAPL", "DUP"]):
                with self.subTest(argv=argv):
                    code, message, reports = self.parse(root / argv[0].strip("-"), *argv, sources=sources, entries=True)
                    self.assertEqual(code, 2)
                    failed = sorted((r["ticker"], r["error"]) for r in reports if not r["complete"])
                    base = root / argv[0].strip("-")
                    self.assertEqual(failed, [
                        ("AAPL", f"{base / 'w' / 'waapl' / 'parser.py'} 缺少 VIEW、TOTAL"),
                        ("DUP", f"{base / 'v' / 'vdup1' / 'parser.py'} 缺少 VIEW、TOTAL"),
                        ("DUP", f"{base / 'v' / 'vdup2' / 'parser.py'} 缺少 VIEW、TOTAL"),
                    ])
                    self.assertEqual([r["ticker"] for r in reports if r["complete"]], ["AAPL"])
                    self.assertIn(f"AAPL：{base / 'w' / 'waapl' / 'parser.py'} 缺少 VIEW、TOTAL", message)

    def test_all_skips_broken_parsers(self):
        # 讀不到 TICKER 時以目錄名稱轉大寫記錄。
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code, message, reports = self.parse(root, "--all")
        self.assertEqual(code, 2)
        self.assertEqual(sorted(reports), ["AAPL", "XNONE", "YMISS", "ZBAD"])
        self.assertTrue(reports["AAPL"]["complete"])
        expected = {
            "ZBAD": f"{root / 'z' / 'zbad' / 'parser.py'} 載入失敗：SyntaxError",
            "YMISS": f"{root / 'y' / 'ymiss' / 'parser.py'} 載入失敗：ModuleNotFoundError",
            "XNONE": f"{root / 'x' / 'xnone' / 'parser.py'} 缺少 TICKER",
        }
        for label, error in expected.items():
            self.assertFalse(reports[label]["complete"])
            self.assertIn(error, reports[label]["error"])
            self.assertIn(f"{label}：{error}", message)

    def test_named_broken_ticker_reports_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code, message, reports = self.parse(root, "--tickers", "ZBAD", "AAPL")
        self.assertEqual(code, 2)
        self.assertEqual(sorted(reports), ["AAPL", "ZBAD"])
        self.assertTrue(reports["AAPL"]["complete"])
        self.assertIn(f"{root / 'z' / 'zbad' / 'parser.py'} 載入失敗：SyntaxError", reports["ZBAD"]["error"])

    def test_listing_tickers_skips_broken_parsers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with companies_with(root, BROKEN), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                code, message = self.run_cli("tickers", "--json")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue()), ["AAPL"])
        self.assertIn(f"XNONE：{root / 'x' / 'xnone' / 'parser.py'} 缺少 TICKER", message)

    def test_wide_duration_days_are_processed(self):
        # 單季 70–130 天的 DURATION_DAYS 格式正確：WIDE 與 AAPL 都照常處理。
        wide = types.ModuleType("wide")
        wide.TICKER, wide.VIEW, wide.TOTAL = "WIDE", "product", "Total"
        wide.DURATION_DAYS = {"quarter": (70, 130), "six_months": (168, 189), "nine_months": (252, 280), "annual": (357, 378)}
        real = cli.companies.parser_source

        def parser_source(ticker):
            return ParserSource(wide) if ticker == "WIDE" else real(ticker)

        with tempfile.TemporaryDirectory() as temp:
            data, out = aapl_data(temp)
            (data / "pipeline" / "WIDE").mkdir(parents=True)
            (data / "pipeline" / "WIDE" / "packages.json").write_text('{"packages": {}}')
            with (
                mock.patch.object(cli.companies, "tickers", return_value=["AAPL", "WIDE"]),
                mock.patch.object(cli.companies, "parser_source", parser_source),
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                code, message = self.run_cli("parse", "--tickers", "WIDE", "AAPL", "--data", str(data), "--out", str(out))
            reports = {r["ticker"]: r for r in json.loads(stdout.getvalue())["companies"]}
            self.assertEqual(code, 0, message)
            self.assertTrue(reports["AAPL"]["complete"])
            self.assertTrue(reports["WIDE"]["complete"])
            self.assertTrue((out / "A" / "AAPL" / "status.json").exists())
            self.assertTrue((out / "W" / "WIDE" / "status.json").exists())


class SnapshotArgumentsTest(unittest.TestCase):
    run_cli = ParseArgumentsTest.run_cli

    def test_snapshots_require_check(self):
        code, message = self.run_cli("parse", "--tickers", "AAPL", "--snapshots")
        self.assertEqual(code, 1)
        self.assertIn("只能與 --check 一起使用", message)

    def test_from_manifest_excludes_date_selection_and_dry_run(self):
        for extra in (["--dry-run"], ["--start", "2024-01-01"], ["--latest"]):
            with self.subTest(extra=extra):
                code, message = self.run_cli("download", "--tickers", "AAPL", "--from-manifest", *extra)
                self.assertEqual(code, 1)
                self.assertIn("--from-manifest", message)

    def test_all_with_from_manifest_means_companies_with_a_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "snapshots"
            for ticker in ("AAPL", "BRK-B"):
                (root / ticker[0] / ticker).mkdir(parents=True)
                (root / ticker[0] / ticker / "manifest.json").write_text('{"filings": []}')
            seen = {}

            class Batch:
                def __init__(self, workflow):
                    seen["manifests"] = workflow.manifests

                def run(self, tickers, *args):
                    seen["tickers"] = tickers
                    return {"complete": True}

            with mock.patch.object(cli, "DownloadBatch", Batch), mock.patch("sys.stdout"):
                code, _ = self.run_cli("download", "--all", "--from-manifest", "--snapshots-dir", str(root), "--data", str(Path(temp) / "data"))
            self.assertEqual(code, 0)
            self.assertEqual(seen, {"manifests": root, "tickers": ["AAPL", "BRK-B"]})


if __name__ == "__main__":
    unittest.main()
