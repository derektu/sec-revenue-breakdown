"""唯讀雲端 viewer；API 不執行 parser、不接受檔案路徑。"""

from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from sec_revenue.engines import JsonCodec
from sec_revenue.service import ParserRegistry


class RevenueViewer:
    def __init__(self, data: Path):
        self.data = data
        self.registry = ParserRegistry()

    def request(self, url: str) -> tuple[int, str, bytes]:
        parsed = urlsplit(url)
        if parsed.path == "/":
            return (
                200,
                "text/html; charset=utf-8",
                Path(__file__).with_name("viewer.html").read_bytes(),
            )
        if parsed.path == "/api/tickers":
            return (
                200,
                "application/json",
                JsonCodec.encode(sorted(self.registry.entries)),
            )
        if parsed.path != "/api/revenue":
            return 404, "application/json", b'{"error":"not found"}'
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"ticker", "period", "basis"} or any(
            len(v) != 1 for v in query.values()
        ):
            return 400, "application/json", b'{"error":"invalid query"}'
        ticker = query.get("ticker", [""])[0].upper()
        if ticker not in self.registry.entries:
            return 400, "application/json", b'{"error":"invalid ticker"}'
        directory = self.data / "outputs" / ticker
        index = directory / "index.json"
        if not index.exists():
            return 404, "application/json", b'{"error":"ticker has not been replayed"}'
        manifest = JsonCodec.read(index)
        files = [directory / relative for relative in manifest["paths"]]
        rows = [JsonCodec.read(path) for path in files]
        for key, field in [("period", "period_end"), ("basis", "basis")]:
            if key in query:
                rows = [r for r in rows if r[field] == query[key][0]]
        if not rows:
            return (
                404,
                "application/json",
                b'{"error":"no data for ticker / period / basis"}',
            )
        return 200, "application/json", JsonCodec.encode(rows)

    def server(self, host: str = "0.0.0.0", port: int = 8765) -> ThreadingHTTPServer:
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, kind, body = viewer.request(self.path)
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        return ThreadingHTTPServer((host, port), Handler)
