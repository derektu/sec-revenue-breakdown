"""富途：個股「財務 > 主營構成」頁。目前只提供登入檢查；擷取見 #43。"""

from __future__ import annotations

from typing import Iterator

from ..model import CaptureError, Table
from .base import Site


class Futu(Site):
    name = "futu"
    probe_url = "https://www.futunn.com/hk/stock/AAPL-US/financials-revenue"
    logged_in_selector = ".hk-js-header-avatar"
    logged_out_selector = ".hk-cs-log-in-btn"

    def target_url(self, ticker: str) -> str:
        return f"https://www.futunn.com/hk/stock/{ticker}-US/financials-revenue"

    def capture(self, page, ticker: str) -> Iterator[Table]:
        raise CaptureError("富途擷取尚未實作（#43）")
