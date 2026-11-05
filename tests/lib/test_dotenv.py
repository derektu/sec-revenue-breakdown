import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "libs"))
from sec_revenue.dotenv import load_dotenv


class LoadDotenvTest(unittest.TestCase):
    def load(self, text, environ=None):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, environ or {}, clear=True):
            path = Path(tmp) / ".env"
            path.write_text(text, encoding="utf-8")
            load_dotenv(path)
            return dict(os.environ)

    def test_parses_values_comments_quotes_and_export(self):
        env = self.load(
            '# 註解\n\nSEC_USER_AGENT="Jane Doe jane@corp.test"\nexport A=1\nB = \'two words\'\n'
        )
        self.assertEqual(env["SEC_USER_AGENT"], "Jane Doe jane@corp.test")
        self.assertEqual(env["A"], "1")
        self.assertEqual(env["B"], "two words")

    def test_existing_environment_wins(self):
        env = self.load("SEC_USER_AGENT=from-file\n", {"SEC_USER_AGENT": "from-shell"})
        self.assertEqual(env["SEC_USER_AGENT"], "from-shell")

    def test_missing_file_is_ignored(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            load_dotenv(Path("/nonexistent/.env"))
            self.assertEqual(dict(os.environ), {})

    def test_malformed_line_reports_line_number(self):
        with self.assertRaisesRegex(ValueError, r":2 "):
            self.load("A=1\nnot a pair\n")


if __name__ == "__main__":
    unittest.main()
