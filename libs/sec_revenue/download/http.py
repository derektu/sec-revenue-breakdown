"""SEC HTTP 用戶端：帶身分的單次 GET、請求間隔與 SEC 拒絕（403／429）判斷；不重試、不追蹤重新導向。"""

from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MIN_REQUEST_INTERVAL = 0.125
BLOCKING_HTTP_STATUSES = (403, 429)


class SecIdentityError(ValueError):
    """缺少或不合格的 SEC_USER_AGENT；所有請求都會失敗，整批停止。"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("SEC 重新導向已停止，未追蹤其他 URL")


class SecHttpClient:
    """沿用環境 proxy／CA，至多每秒八次，單次 GET，拒絕即停止。"""

    def __init__(self, user_agent: str | None = None, interval: float = MIN_REQUEST_INTERVAL):
        self.user_agent = (
            user_agent if user_agent is not None else os.environ.get("SEC_USER_AGENT", "")
        )
        self.interval, self.last_request = max(interval, MIN_REQUEST_INTERVAL), 0.0
        self.requests = 0
        self.opener = build_opener(NoRedirect())

    def get(self, url: str, kind: str) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in ("www.sec.gov", "data.sec.gov")
            or parsed.query
            or parsed.fragment
            or ".." in parsed.path.split("/")
        ):
            raise ValueError("只接受 SEC HTTPS URL")
        if (
            not self.user_agent.strip()
            or "@" not in self.user_agent
            or any(
                s in self.user_agent.lower() for s in ("example.com", "your-real-contact")
            )
        ):
            raise SecIdentityError(
                "網路下載需設定真實 SEC_USER_AGENT（組織／姓名與聯絡 email）；離線快取不需要"
            )
        remaining = self.interval - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_request = time.monotonic()
        self.requests += 1
        with self.opener.open(
            Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"}),
            timeout=45,
        ) as response:
            if response.geturl() != url:
                raise ValueError("SEC 最終 URL 不一致")
            content_type = response.headers.get_content_type()
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError(
                    "SEC 回應編碼不符 identity；停止，避免把壓縮 bytes 假存為 HTML／JSON"
                )
            body = response.read()
        if kind == "html" and content_type not in ("text/html", "application/xhtml+xml"):
            raise ValueError("非 HTML response，不儲存成 .html")
        if kind == "json":
            json.loads(body)
        return body


def is_blocking(error: BaseException) -> bool:
    return isinstance(error, SecIdentityError) or (
        isinstance(error, HTTPError) and error.code in BLOCKING_HTTP_STATUSES
    )
