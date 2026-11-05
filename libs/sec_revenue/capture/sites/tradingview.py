"""TradingView：個股 Financials > Segments 頁的「By source」表（年度 by segment）。

- 頁面 URL 含交易所前綴（例如 `NASDAQ-AAPL`）。不帶前綴時部分交易所會自動導向，其餘不會，
  因此依序嘗試不帶前綴、`NASDAQ-`、`NYSE-`、`AMEX-`。實際開啟的 URL 須為這三個美國交易所之一，
  且頁面標題含相同的 `<交易所>:<代號>`，否則不採用。類別股以 `.` 分隔（`BRK-B` → `BRK.B`）。
- 表格欄為 TradingView 顯示的年度標籤（例如 `2026`），每欄一期 `kind=FY`，不寫 `period_end`。
  年度標籤不一定是公司財年：多數為財年結束的年份，部分公司（例如 NVDA、ORCL、WMT、HD）為結束年份減一。
  標籤原樣保存，與 SEC 財年的對齊由比對工具處理。
- 只取「By source」區塊；區塊內若同時出現「By country」標題則明確失敗。
- 表格以 div 排版並可水平捲動，預設顯示最近的年度。只取畫面上完整顯示的年度欄，
  讓每個數值都在截圖中；`table.html` 以 `rebuild` 產生。
- 數值原文含 bidi 控制字元與窄空白（`\\u202a123.00\\u202fM\\u202c`），寫入 display 前移除；
  `—` 為空值。`table.txt` 與 `table.html` 保存頁面文字原樣，仍含這些字元。
  幣別須為 USD。截圖涵蓋整個 By source 區塊（標題、圖表與表格）。
"""

from __future__ import annotations

import re
from typing import Iterator

from ..model import CaptureError, Period, Table
from .base import Site

EXCHANGES = ("", "NASDAQ-", "NYSE-", "AMEX-")
US_EXCHANGES = ("NASDAQ", "NYSE", "AMEX")
YEAR_RE = re.compile(r"^[0-9]{4}$")
EMPTY_CELLS = {"", "—", "-", "–"}
# bidi 控制字元與各種不換行空白。
_INVISIBLE_RE = re.compile("[‎‏‪-‮⁦-⁩   ]")
LOAD_TIMEOUT_MS = 30_000

_READ_JS = """
s => {
  const header = s.querySelector('div[class*="firstColumn-"]')?.closest('div[class*="container-"]');
  if (!header) return {currency: '', years: [], rows: []};
  const limit = s.getBoundingClientRect().right + 1;
  const start = header.querySelector('div[class*="firstColumn-"]').getBoundingClientRect().right - 1;
  const cellsOf = row => [...(row.querySelector(':scope > div[class*="values-"]')?.children || [])];
  // 只取完整顯示的欄：被固定首欄遮住或超出區塊右緣的欄不取。
  const shown = cellsOf(header).map(c => {
    const r = c.getBoundingClientRect();
    return r.width > 0 && r.left >= start && r.right <= limit;
  });
  const pick = row => cellsOf(row).map(c => c.innerText.trim()).filter((_, i) => shown[i]);
  return {
    currency: (header.querySelector('span[class*="description-"]')?.innerText || '').trim(),
    years: pick(header),
    rows: [...s.querySelectorAll('div[data-name]')]
      .filter(r => r.querySelector(':scope > div[class*="values-"]'))
      .map(r => [(r.querySelector('span[class*="titleText-"]')?.innerText || '').trim(), ...pick(r)]),
  };
}
"""


class TradingView(Site):
    name = "tradingview"
    probe_url = "https://www.tradingview.com/symbols/NASDAQ-AAPL/financials-segments/"
    # 登入狀態反映在 <html> 的 class 上。
    logged_in_selector = "html.is-authenticated"
    logged_out_selector = "html.is-not-authenticated"

    def target_url(self, ticker: str) -> str:
        return f"https://www.tradingview.com/symbols/{ticker.replace('-', '.')}/financials-segments/"

    def capture(self, page, ticker: str, periods: int) -> Iterator[Table]:
        url = _open(page, ticker.replace("-", "."))
        title = page.locator('div[class*="title-"]', has_text=re.compile(r"^By source$")).first
        try:
            title.wait_for(timeout=LOAD_TIMEOUT_MS)
        except Exception as exc:
            raise CaptureError(f"找不到 By source 表：{url}") from exc
        section = title.locator("xpath=..")
        titles = section.evaluate(
            """s => [...s.querySelectorAll('div[class*="title-"]')].map(e => e.innerText.trim())"""
        )
        if "By country" in titles:
            raise CaptureError("By source 區塊內出現 By country 標題，無法確定表格範圍")
        state = _stable(page, section)
        rows = [["Metrics", *state["years"]], *state["rows"]]
        yield Table(
            url=url,
            element=section,
            rows=rows,
            periods=parse_state(state),
            html_mode="rebuild",
        )


def normalize(display: str) -> str:
    """移除 bidi 控制字元與不換行空白，例如 `\\u202a123.00\\u202fM\\u202c` → `123.00M`。"""
    return _INVISIBLE_RE.sub("", display).strip()


def parse_state(state: dict) -> list[Period]:
    """每個年度欄轉成一期 FY；整列皆為空值的分類不寫入。"""
    if state["currency"] != "Currency: USD":
        raise CaptureError(f"幣別不是 USD：{state['currency']!r}")
    years = state["years"]
    if not years or not all(YEAR_RE.match(year) for year in years):
        raise CaptureError(f"表頭年度格式不符預期：{years}")
    if len(set(years)) != len(years):
        raise CaptureError(f"表頭年度重複：{years}")
    values: dict[str, dict[str, str]] = {year: {} for year in years}
    seen = set()
    for row in state["rows"]:
        name, cells = row[0], row[1:]
        if not name:
            raise CaptureError("有分類名稱為空的列")
        if name in seen:
            raise CaptureError(f"分類名稱重複：{name}")
        seen.add(name)
        if len(cells) != len(years):
            raise CaptureError(f"{name} 的欄位數與表頭不一致")
        for year, cell in zip(years, cells):
            display = normalize(cell)
            if display not in EMPTY_CELLS:
                values[year][name] = display
    periods = [Period(label=year, kind="FY", values=values[year]) for year in reversed(years) if values[year]]
    if not periods:
        raise CaptureError("表格沒有任何數值")
    return periods


def _open(page, symbol: str) -> str:
    """依序嘗試交易所前綴，回傳實際開啟的頁面 URL。

    只接受美國交易所、且頁面標題含相同 `<交易所>:<代號>` 的頁面；不帶前綴導向其他交易所時，
    不採用並繼續嘗試明確的美國交易所前綴。
    """
    rejected = []
    for prefix in EXCHANGES:
        url = f"https://www.tradingview.com/symbols/{prefix}{symbol}/financials-segments/"
        response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if response is None or response.status != 200:
            continue
        exchange = exchange_of(page.url, symbol)
        if exchange is None:
            continue
        if exchange not in US_EXCHANGES:
            rejected.append(f"{exchange}（非美國交易所）")
            continue
        if f"{exchange}:{symbol} " not in page.title() + " ":
            rejected.append(f"{exchange}（標題不符：{page.title()!r}）")
            continue
        return page.url
    tried = ", ".join(p.rstrip("-") or "不帶前綴" for p in EXCHANGES)
    detail = f"；不採用：{'、'.join(rejected)}" if rejected else ""
    raise CaptureError(f"找不到 {symbol} 的美國交易所頁面（已嘗試 {tried}{detail}）")


def exchange_of(url: str, symbol: str) -> str | None:
    """從 `/symbols/<交易所>-<代號>/` 取出交易所；代號不符或沒有前綴時回傳 None。"""
    match = re.search(r"/symbols/([A-Z]+)-([^/]+)/", url)
    if not match or match.group(2) != symbol:
        return None
    return match.group(1)


def _stable(page, section) -> dict:
    previous = None
    for _ in range(20):
        state = section.evaluate(_READ_JS)
        if state == previous and state["rows"]:
            return state
        previous = state
        page.wait_for_timeout(500)
    raise CaptureError("表格內容持續變動，無法取得穩定數值")
