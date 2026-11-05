import importlib.util
import os
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sec_pipeline.py"
spec = importlib.util.spec_from_file_location("sec_pipeline_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


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


if __name__ == "__main__":
    unittest.main()
