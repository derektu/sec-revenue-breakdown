"""唯讀雲端 viewer；API 不執行 parser、不接受檔案路徑。

`/api/revenue` 回傳萃取輸出，並附上該期 `evidence/evidence.json` 中對應的證據；
`/evidence/<TICKER>/<period>/<file>` 只提供證據目錄內符合命名規則的表格 PNG 與 HTML。
"""

from __future__ import annotations
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from sec_revenue.engines import JsonCodec
from sec_revenue.evidence import FILE_NAME_RE, EvidenceWorkflow
from sec_revenue.service import ParserRegistry

EVIDENCE_PATH_RE = re.compile(r"/evidence/([A-Z0-9.\-]{1,10})/(\d{4}-\d{2}-\d{2})/([^/]+)")
# 證據 HTML 由 SEC 原文抽出，以 sandbox 隔離，不執行 script、不載入任何資源。
EVIDENCE_HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"


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
        if parsed.path.startswith("/evidence/"):
            return self.evidence_file(parsed.path)
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
        rows, loaded = [], {}
        for relative in manifest["paths"]:
            raw = (directory / relative).read_bytes()
            row = json.loads(raw)
            period = row["period_end"]
            if period not in loaded:
                loaded[period] = self.load_evidence(directory / period)
            row["evidence"] = self.row_evidence(
                loaded[period], relative, hashlib.sha256(raw).hexdigest()
            )
            rows.append(row)
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

    def load_evidence(self, period_dir: Path) -> dict | None:
        """讀該期 evidence.json 並核對表格檔 hash；檔案壞掉時回傳錯誤，不讓整個 API 失敗。"""
        path = period_dir / "evidence" / "evidence.json"
        if not path.exists():
            return None
        try:
            evidence = JsonCodec.read(path)
            intact = all(
                self.file_sha256(self.data / table[kind]["path"]) == table[kind]["sha256"]
                for table in evidence["tables"].values()
                for kind in ("html", "png")
            )
            return {
                "evidence": evidence,
                "intact": intact,
                "rules_current": evidence.get("rules_sha256") == EvidenceWorkflow.rules_sha256(),
            }
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"error": f"evidence.json 無法讀取：{type(error).__name__}: {error}"}

    @staticmethod
    def file_sha256(path: Path) -> str | None:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

    @staticmethod
    def row_evidence(loaded: dict | None, relative: str, output_sha256: str) -> dict | None:
        """該期證據中對應這份萃取輸出的部分。

        萃取輸出 hash、表格檔 hash 或證據程式版本與紀錄不同時標為過期（stale）並附原因。
        """
        if loaded is None:
            return None
        if "error" in loaded:
            return {"error": loaded["error"]}
        evidence = loaded["evidence"]
        name = Path(relative).name
        try:
            row = next(
                (r for r in evidence["rows"] if Path(r["output"]["path"]).name == name), None
            )
            if row is None:
                return None
            reasons = []
            if row["output"]["sha256"] != output_sha256:
                reasons.append("萃取輸出與證據紀錄的 hash 不同")
            if not loaded["intact"]:
                reasons.append("表格檔缺少或 hash 不符")
            if not loaded["rules_current"]:
                reasons.append("證據由不同版本的證據程式產生")
            return {
                "status": evidence["status"],
                "error": evidence.get("error"),
                "stale": bool(reasons),
                "stale_reasons": reasons,
                "fields": row["fields"],
                "facts": evidence["facts"],
                "tables": {
                    key: {
                        "cropped": table["cropped"],
                        "html": Path(table["html"]["path"]).name,
                        "png": Path(table["png"]["path"]).name,
                    }
                    for key, table in evidence["tables"].items()
                },
            }
        except (KeyError, TypeError) as error:
            return {"error": f"evidence.json 格式不符：{type(error).__name__}: {error}"}

    def evidence_file(self, path: str) -> tuple[int, str, bytes]:
        match = EVIDENCE_PATH_RE.fullmatch(path)
        if (
            not match
            or match.group(1) not in self.registry.entries
            or not FILE_NAME_RE.fullmatch(match.group(3))
        ):
            return 400, "application/json", b'{"error":"invalid evidence path"}'
        ticker, period, name = match.groups()
        root = (self.data / "outputs").resolve()
        file = (root / ticker / period / "evidence" / name).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            return 404, "application/json", b'{"error":"evidence not found"}'
        kind = "image/png" if name.endswith(".png") else "text/html; charset=utf-8"
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
                if self.path.startswith("/evidence/") and kind.startswith("text/html"):
                    self.send_header("Content-Security-Policy", EVIDENCE_HTML_CSP)
                self.end_headers()
                self.wfile.write(body)

        return ThreadingHTTPServer((host, port), Handler)
