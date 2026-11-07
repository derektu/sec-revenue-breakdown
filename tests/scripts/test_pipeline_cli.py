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
