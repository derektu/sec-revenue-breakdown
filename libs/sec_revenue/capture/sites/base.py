"""網站 adapter 介面與共用的登入判斷。"""

from __future__ import annotations

import time
from typing import Iterator, Literal

from ..model import Table

LoginState = Literal["logged_in", "logged_out"]
# 等待登入標記出現的時間；逾時或判斷不出來一律視為未登入。
LOGIN_TIMEOUT_S = 15.0


class Site:
    """一個對照來源網站。

    - `name`：`reference.json` 的來源名稱。
    - `probe_url`：`setup` 檢查登入時開啟的頁面（AAPL 的目標頁）。
    - `logged_in_selector`：只有登入後才出現的元素。
    - `logged_out_selector`：未登入時才出現的元素，例如登入按鈕。
    """

    name: str
    probe_url: str
    logged_in_selector: str
    logged_out_selector: str

    def target_url(self, ticker: str) -> str:
        raise NotImplementedError

    def login_state(self, page) -> LoginState:
        """看得到已登入標記、且沒有未登入標記，才算已登入。"""
        deadline = time.monotonic() + LOGIN_TIMEOUT_S
        while time.monotonic() < deadline:
            signed_in = _present(page, self.logged_in_selector)
            signed_out = _present(page, self.logged_out_selector)
            if signed_in and not signed_out:
                return "logged_in"
            if signed_out:
                return "logged_out"
            page.wait_for_timeout(500)
        return "logged_out"

    def capture(self, page, ticker: str) -> Iterator[Table]:
        """開到 ticker 的目標頁並逐一產生要擷取的表。失敗時丟出 `CaptureError`。"""
        raise NotImplementedError


def _present(page, selector: str) -> bool:
    locator = page.locator(selector)
    for index in range(locator.count()):
        item = locator.nth(index)
        try:
            if item.is_visible():
                return True
        except Exception:
            continue
    return False
