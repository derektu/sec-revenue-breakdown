"""Stock Analysis：Revenue by Segment 頁的季度歷史表。

頁面預設顯示 TTM；擷取前切到 Quarterly 與 Latest（數值，而非成長率或占比），
並確認圖表標題為 `(Quarterly)`。表格是標準 `<table>`，`table.html` 以 `clean` 產生。
未登入時只顯示 20 期，登入後顯示完整歷史。
"""

from __future__ import annotations

import datetime as dt
from typing import Iterator

from ..model import CaptureError, Period, Table
from .base import Site

TABLE = "div.table-wrap table"
# 視為空值、不寫入的儲存格內容。
EMPTY_CELLS = {"", "-", "–", "—", "n/a", "N/A"}
LOAD_TIMEOUT_MS = 30_000


class StockAnalysis(Site):
    name = "stockanalysis"
    probe_url = "https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/"
    logged_in_selector = "header button[aria-label='Notifications']"
    logged_out_selector = "header a[href='/login/']"

    def target_url(self, ticker: str) -> str:
        # 類別股在 Stock Analysis 以 `.` 分隔，例如 BRK-B → brk.b。
        return f"https://stockanalysis.com/stocks/{ticker.lower().replace('-', '.')}/metrics/revenue-by-segment/"

    def capture(self, page, ticker: str) -> Iterator[Table]:
        url = self.target_url(ticker)
        response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if response is not None and response.status == 404:
            raise CaptureError(f"頁面不存在（404）：{url}")
        try:
            page.locator(TABLE).first.wait_for(state="visible", timeout=LOAD_TIMEOUT_MS)
        except Exception as exc:
            raise CaptureError(f"找不到營收拆分表格：{url}") from exc
        _select(page, "Quarterly")
        _select(page, "Latest")
        try:
            page.get_by_text("(Quarterly)").first.wait_for(timeout=LOAD_TIMEOUT_MS)
        except Exception as exc:
            raise CaptureError("無法確認表格已切到 Quarterly") from exc
        rows = _stable_rows(page)
        yield Table(
            url=url,
            element=page.locator(TABLE).first,
            rows=rows,
            periods=parse_rows(rows),
            html_mode="clean",
        )


def parse_rows(rows: list[list[str]]) -> list[Period]:
    """表頭第一欄為 `Date`，其餘為分類；每列一季，第一欄為期末日（例如 `Sep 30, 2026`）。"""
    if not rows or not rows[0] or rows[0][0] != "Date":
        raise CaptureError(f"表頭格式不符預期：{rows[0] if rows else '（空表格）'}")
    header = rows[0]
    periods = []
    for row in rows[1:]:
        if len(row) != len(header):
            raise CaptureError(f"欄位數與表頭不一致：{row}")
        label = row[0]
        try:
            end = dt.datetime.strptime(label, "%b %d, %Y").date().isoformat()
        except ValueError as exc:
            raise CaptureError(f"無法解析期末日：{label!r}") from exc
        values = {name: cell for name, cell in zip(header[1:], row[1:]) if cell not in EMPTY_CELLS}
        if values:
            periods.append(Period(label=label, kind="Q", values=values, period_end=end))
    if not periods:
        raise CaptureError("表格沒有任何數值")
    return periods


def _select(page, name: str) -> None:
    """點選切換按鈕並等它變成 active。"""
    button = page.get_by_role("button", name=name, exact=True).first
    try:
        button.wait_for(timeout=LOAD_TIMEOUT_MS)
    except Exception as exc:
        raise CaptureError(f"找不到 {name} 按鈕") from exc
    if "active" not in (button.get_attribute("class") or "").split():
        button.click()
    try:
        page.wait_for_function(
            "e => e.classList.contains('active')", arg=button.element_handle(), timeout=LOAD_TIMEOUT_MS
        )
    except Exception as exc:
        raise CaptureError(f"無法切換到 {name}") from exc


def _read_rows(page) -> list[list[str]]:
    return page.locator(TABLE).first.evaluate(
        """t => [...t.querySelectorAll('tr')].map(
            r => [...r.querySelectorAll('th,td')].map(c => c.innerText.trim()))"""
    )


def _stable_rows(page) -> list[list[str]]:
    """切換後數值可能分批更新；連續兩次讀到相同內容才採用。"""
    previous = None
    for _ in range(20):
        rows = _read_rows(page)
        if rows == previous:
            return rows
        previous = rows
        page.wait_for_timeout(500)
    raise CaptureError("表格內容持續變動，無法取得穩定數值")
