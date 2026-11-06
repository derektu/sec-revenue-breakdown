"""SEC HTTP 用戶端：身分、URL 限制、不重試與拒絕非 identity 編碼；不連網。"""

from email.message import Message
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.download.http import SecHttpClient, SecIdentityError  # noqa: E402

IDENTITY = "Synthetic unit-test identity unit@test.invalid"
URL = "https://www.sec.gov/Archives/edgar/data/1/000000000127000001/fixture.htm"


class SecHttpClientTests(unittest.TestCase):
    def test_identity_and_sec_url_are_required_before_any_request(self):
        client = SecHttpClient("")
        with patch.object(client.opener, "open") as request:
            with self.assertRaises(SecIdentityError):
                client.get("https://data.sec.gov/submissions/CIK0000320193.json", "json")
            with self.assertRaisesRegex(ValueError, "SEC HTTPS"):
                SecHttpClient(IDENTITY).get("https://other.test/a", "html")
            request.assert_not_called()

    def test_403_is_not_retried(self):
        client = SecHttpClient(IDENTITY)
        with patch.object(client.opener, "open", side_effect=HTTPError(URL, 403, "Forbidden", {}, None)) as request:
            with self.assertRaises(HTTPError):
                client.get(URL, "html")
            self.assertEqual(request.call_count, 1)

    def test_encoded_response_is_rejected_before_reading_bytes(self):
        client = SecHttpClient(IDENTITY)
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = URL
        response.headers = Message()
        response.headers["Content-Type"] = "text/html"
        response.headers["Content-Encoding"] = "gzip"
        response.read.return_value = b"compressed fixture bytes, not HTML"
        with patch.object(client.opener, "open", return_value=response):
            with self.assertRaisesRegex(ValueError, "編碼"):
                client.get(URL, "html")
        response.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
