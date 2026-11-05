"""富途：個股「財務 > 主營構成」頁的「業務」區塊。

業務區一次只顯示一期，由期間選單切換；選單混有季度（`2026/Q3`）與年度（`2026/FY`），
標籤為富途顯示的財年標籤。以選單中最新的一季為準，擷取往回 `periods` 季範圍內選單有的季度，
每一期一張表、一次擷取。

- 切換後期間標籤先更新、數值較晚才更新，且「暫無內容」可能只是還在載入。開頁時先等列表非空且穩定；
  切換時記下點選前實際顯示的列表，等到標籤相符、列表與點選前不同、且連續兩次讀取相同，才採用。
  兩期數值完全相同時無法確認已刷新，明確失敗而不猜。頁面預設已選取目標期間時不切換，只等數值穩定。
- 連續切換時偶爾整區變成「暫無內容」且期間選單消失，但同一期重新載入後有資料；
  因此每次切換前停頓 2 秒，失敗時重新載入頁面再選同一期，重試 2 次仍失敗才列為失敗。
- 選單中的季度不一定連續（例如缺 2025/Q3，或只有每年 Q1、Q2），以時間範圍取季度。
- 頁面沒有期末日，不寫 `period_end`。
- 數值帶 `億`、`萬` 單位；幣別須為美元。
- 列表以 div 排版，`table.html` 以 `rebuild` 產生。截圖涵蓋整個業務區塊，含目前選取的期間與幣別；
  `table.txt` 第一行與 `table.html` 的 `<caption>` 也寫入「業務 <期間> <幣別>」。
"""

from __future__ import annotations

import re
from typing import Iterator

from ..model import CaptureError, Period, Table
from .base import Site

SECTION = "div.product-data-item:has(h3#business)"
QUARTER_RE = re.compile(r"^[0-9]{4}/Q[1-4]$")
LOAD_TIMEOUT_MS = 30_000
SWITCH_TIMEOUT_MS = 30_000
# 每次切換前停頓，速度接近人工操作。
SWITCH_PAUSE_MS = 2_000
# 切換失敗時重新載入頁面重試的次數與等待時間（逐次加倍）。
RETRIES = 2
RETRY_WAIT_MS = 5_000

_READ_JS = """
s => ({
  period: (s.querySelector('.current-period')?.textContent || '').trim(),
  options: [...s.querySelectorAll('.period-list .period-item')].map(e => e.textContent.trim()),
  unit: (s.querySelector('.unit')?.textContent || '').trim(),
  head: [...s.querySelectorAll('.list-head span')].map(e => e.textContent.trim()).filter(t => t),
  rows: [...s.querySelectorAll('.list-main .list-item')].map(r => [
    (r.querySelector('.item-name')?.textContent || '').trim(),
    (r.querySelector('.item-price')?.textContent || '').trim(),
    (r.querySelector('.item-radio')?.textContent || '').trim(),
  ]),
  empty: s.textContent.includes('暫無內容'),
})
"""


class Futu(Site):
    name = "futu"
    probe_url = "https://www.futunn.com/hk/stock/AAPL-US/financials-revenue"
    logged_in_selector = ".hk-js-header-avatar"
    logged_out_selector = ".hk-cs-log-in-btn"

    def target_url(self, ticker: str) -> str:
        # 類別股在富途以 `.` 分隔，例如 BRK-B → BRK.B-US。
        return f"https://www.futunn.com/hk/stock/{ticker.replace('-', '.')}-US/financials-revenue"

    def capture(self, page, ticker: str, periods: int) -> Iterator[Table]:
        url = self.target_url(ticker)
        section, state = _load(page, url)
        quarters = recent_quarters(state["options"], periods)
        if not quarters:
            raise CaptureError(f"期間選單沒有季度：{state['options']}")
        for label in quarters:
            for attempt in range(RETRIES + 1):
                page.wait_for_timeout(SWITCH_PAUSE_MS)
                try:
                    state = _switch(page, section, label)
                    break
                except CaptureError:
                    if attempt == RETRIES:
                        raise
                # 連續切換時偶爾整區變成「暫無內容」且期間選單消失；稍候重新載入再選同一期。
                page.wait_for_timeout(RETRY_WAIT_MS * (attempt + 1))
                section, _ = _load(page, url)
            yield Table(
                url=url,
                element=section,
                rows=[state["head"], *state["rows"]],
                periods=[parse_state(state, label)],
                html_mode="rebuild",
                caption=f"業務 {state['period']} {state['unit']}",
            )


def recent_quarters(options: list[str], periods: int) -> list[str]:
    """選單中最新一季往回 `periods` 季範圍內的季度，依新到舊。

    季度不一定連續（例如只有每年 Q1、Q2），因此以時間範圍而非個數取，避免回推到很久以前。
    """
    def index(label: str) -> int:
        year, quarter = label.split("/Q")
        return int(year) * 4 + int(quarter)

    quarters = sorted({label for label in options if QUARTER_RE.match(label)}, key=index, reverse=True)
    if not quarters:
        return []
    newest = index(quarters[0])
    return [label for label in quarters if newest - index(label) < periods]


def _load(page, url: str):
    """開啟目標頁，等業務區塊與期間選單載入；回傳區塊與目前內容。"""
    response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    if response is not None and response.status == 404:
        raise CaptureError(f"頁面不存在（404）：{url}")
    section = page.locator(SECTION).first
    try:
        section.wait_for(state="visible", timeout=LOAD_TIMEOUT_MS)
    except Exception as exc:
        raise CaptureError(f"找不到業務區塊：{url}") from exc
    try:
        page.wait_for_function(
            "s => s.querySelectorAll('.period-list .period-item').length > 0",
            arg=section.element_handle(), timeout=LOAD_TIMEOUT_MS,
        )
    except Exception as exc:
        raise CaptureError(f"業務區塊沒有期間選單（可能沒有資料）：{url}") from exc
    return section, _settle(page, section, lambda state: True, "開頁時")


def _settle(page, section, accept, what: str) -> dict:
    """等列表非空、不是「暫無內容」、符合 `accept`，且連續兩次讀取相同，回傳區塊內容。"""
    deadline = SWITCH_TIMEOUT_MS
    last = state = None
    while deadline > 0:
        state = section.evaluate(_READ_JS)
        ready = bool(state["rows"]) and not state["empty"] and accept(state)
        if ready and state == last:
            return state
        last = state if ready else None
        page.wait_for_timeout(700)
        deadline -= 700
    shown = state["period"] if state else "?"
    raise CaptureError(f"{what}數值沒有載入或不穩定（頁面期間 {shown!r}）")


def parse_state(state: dict, label: str) -> Period:
    """把業務區的一期轉成 Period；表頭須為「名稱、營收、比例」，幣別須為美元。"""
    if state["period"] != label:
        raise CaptureError(f"期間標籤為 {state['period']!r}，預期 {label!r}")
    if state["unit"] != "貨幣單位:美元":
        raise CaptureError(f"幣別不是美元：{state['unit']!r}")
    if state["head"] != ["名稱", "營收", "比例"]:
        raise CaptureError(f"表頭格式不符預期：{state['head']}")
    values: dict[str, str] = {}
    for name, price, _ratio in state["rows"]:
        if not name:
            raise CaptureError(f"{label} 有分類名稱為空的列")
        if name in values:
            raise CaptureError(f"{label} 分類名稱重複：{name}")
        if price in ("", "--", "-"):
            continue
        values[name] = price
    if not values:
        raise CaptureError(f"{label} 沒有任何數值")
    return Period(label=label, kind="Q", values=values)


def _switch(page, section, label: str) -> dict:
    """切到指定期間，等數值更新並穩定後回傳區塊內容。

    以點選前實際顯示的列表為基準：標籤先變、列表仍是舊值時不採用。目前已選取該期間時不切換。
    """
    before = _settle(page, section, lambda state: True, "切換前")
    if before["period"] == label:
        page.mouse.move(0, 0)
        return before
    section.locator(".current-period").click()
    option = section.locator(".period-list .period-item", has_text=label).first
    try:
        option.wait_for(state="visible", timeout=SWITCH_TIMEOUT_MS)
        option.click()
    except Exception as exc:
        raise CaptureError(f"無法選取期間 {label}") from exc
    page.mouse.move(0, 0)  # 移開滑鼠，避免圖表 tooltip 出現在截圖中
    try:
        return _settle(
            page, section,
            lambda state: state["period"] == label and state["rows"] != before["rows"],
            f"{label} 的",
        )
    except CaptureError:
        now = section.evaluate(_READ_JS)
        if now["period"] == label and now["rows"] == before["rows"]:
            raise CaptureError(
                f"{label} 的列表與切換前（{before['period']}）完全相同，無法確認數值已更新"
            ) from None
        raise
