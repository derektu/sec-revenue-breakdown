"""正式輸出（`data/revenue/`）的唯讀 viewer；API 不執行 parser、不接受檔案路徑。

- `/` 是頁面。
- `/api/companies` 列出公司。
- `/api/company?ticker=` 回傳一家公司的 Q、FY 兩個序列。
- `/revenue-evidence/<TICKER>/<Q|FY>/<期末日>/<file>` 只提供證據目錄內符合命名規則的表格 PNG 與 HTML。
"""

from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from .common.jsonio import JsonCodec
from .published import PublishedRevenue

REVENUE_EVIDENCE_RE = re.compile(r"/revenue-evidence/([A-Z0-9\-]{1,10})/(Q|FY)/(\d{4}-\d{2}-\d{2})/([^/]+)")
DEFAULT_REVENUE_ROOT = Path(__file__).resolve().parents[2] / "data" / "revenue"
# 證據 HTML 由 SEC 原文抽出，以 sandbox 隔離，不執行 script、不載入任何資源。
EVIDENCE_HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
# 頁面只載入自身的 inline script、樣式與同源圖片，不連外。
PAGE_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src 'self'; connect-src 'self'; frame-ancestors 'none'"
)


class RevenueViewer:
    """`revenue_root` 是正式輸出根目錄；`universe` 是 `tickers.csv` 路徑。"""

    def __init__(self, revenue_root: Path | None = None, universe: Path | None = None):
        self.published = PublishedRevenue(revenue_root or DEFAULT_REVENUE_ROOT, universe)

    def request(self, url: str) -> tuple[int, str, bytes]:
        parsed = urlsplit(url)
        if parsed.path == "/":
            return 200, "text/html; charset=utf-8", Path(__file__).with_name("viewer.html").read_bytes()
        if parsed.path == "/api/companies":
            return 200, "application/json", JsonCodec.encode(self.published.companies())
        if parsed.path == "/api/company":
            return self.company(parsed.query)
        if parsed.path.startswith("/revenue-evidence/"):
            return self.revenue_evidence_file(parsed.path)
        return 404, "application/json", b'{"error":"not found"}'

    def company(self, query_string: str) -> tuple[int, str, bytes]:
        query = parse_qs(query_string, keep_blank_values=True)
        if set(query) != {"ticker"} or len(query["ticker"]) != 1:
            return 400, "application/json", b'{"error":"invalid query"}'
        ticker = query["ticker"][0].upper()
        if not self.published.known(ticker):
            return 400, "application/json", b'{"error":"invalid ticker"}'
        company = self.published.company(ticker)
        if company is None:
            return 404, "application/json", b'{"error":"no published output"}'
        return 200, "application/json", JsonCodec.encode(company)

    def revenue_evidence_file(self, path: str) -> tuple[int, str, bytes]:
        match = REVENUE_EVIDENCE_RE.fullmatch(path)
        file = self.published.evidence_file(*match.groups()) if match else None
        if file is None:
            return 404, "application/json", b'{"error":"evidence not found"}'
        kind = "image/png" if file.suffix == ".png" else "text/html; charset=utf-8"
        return 200, kind, file.read_bytes()

    def server(self, host: str = "0.0.0.0", port: int = 7290) -> ThreadingHTTPServer:
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, kind, body = viewer.request(self.path)
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                # 與 request() 的路由一致，以 urlsplit 的路徑判斷；absolute-form 請求（GET http://host/...）也套用 CSP。
                route = urlsplit(self.path).path
                if route == "/":
                    self.send_header("Content-Security-Policy", PAGE_CSP)
                elif route.startswith("/revenue-evidence/") and kind.startswith("text/html"):
                    self.send_header("Content-Security-Policy", EVIDENCE_HTML_CSP)
                self.end_headers()
                self.wfile.write(body)

        return ThreadingHTTPServer((host, port), Handler)
