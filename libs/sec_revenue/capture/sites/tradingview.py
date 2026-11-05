"""TradingView：個股 Financials > Segments 頁。目前只提供登入檢查；擷取見 #43。

頁面 URL 含交易所前綴（例如 `NASDAQ-AAPL`），擷取時需要 ticker 到交易所的對應。
"""

from __future__ import annotations

from typing import Iterator

from ..model import CaptureError, Table
from .base import Site


class TradingView(Site):
    name = "tradingview"
    probe_url = "https://www.tradingview.com/symbols/NASDAQ-AAPL/financials-segments/"
    # 登入狀態反映在 <html> 的 class 上。
    logged_in_selector = "html.is-authenticated"
    logged_out_selector = "html.is-not-authenticated"

    def target_url(self, ticker: str) -> str:
        raise CaptureError("TradingView 需要 ticker 到交易所的對應，尚未實作（#43）")

    def capture(self, page, ticker: str) -> Iterator[Table]:
        raise CaptureError("TradingView 擷取尚未實作（#43）")
