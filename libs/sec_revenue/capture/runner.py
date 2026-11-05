"""`setup` 與 `capture` 的流程：登入檢查、逐檔擷取、寫入證據與合併、最後整體驗證。"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..universe import TICKER_RE, capture_id, validate_universe
from .evidence import PNG_WARN_BYTES, compress_png, table_html, table_text
from .merge import commit_capture
from .model import CaptureError, Table
from .sites import SITES, Site

# 兩檔之間的間隔，讓擷取速度接近人工操作。
PACE_SECONDS = 3.0
# 截圖時表格四周保留的像素。
SHOT_MARGIN = 16

Prompt = Callable[[str], str]
Output = Callable[[str], None]

# 截圖前隱藏表格以外的 fixed／sticky 元素（例如帶有帳號頭像的頁首），
# 並讓祖先元素不裁切，使截圖只含完整的表格。
_ISOLATE_JS = """
el => {
  for (const n of document.querySelectorAll('body *')) {
    if (n.contains(el) || el.contains(n)) continue;
    const pos = getComputedStyle(n).position;
    if (pos === 'fixed' || pos === 'sticky') n.style.setProperty('visibility', 'hidden', 'important');
  }
  for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    a.style.setProperty('overflow', 'visible', 'important');
  }
}
"""


class CaptureClock:
    """產生 captured_at；同一來源的下一次擷取若落在同一秒，等到下一秒。"""

    def __init__(self, now: Callable[[], dt.datetime] | None = None, sleep: Callable[[float], None] = time.sleep):
        self._now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._sleep = sleep
        self._last: dict[str, str] = {}

    def next(self, source: str) -> str:
        while True:
            now = self._now()
            captured_at = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if capture_id(captured_at) != self._last.get(source):
                self._last[source] = capture_id(captured_at)
                return captured_at
            self._sleep(1 - now.microsecond / 1_000_000 + 0.01)


@dataclass
class Summary:
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def ensure_login(context, sites: list[Site], prompt: Prompt, out: Output) -> bool:
    """逐站檢查登入；有未登入的站就請使用者在視窗中登入後按 Enter 重新檢查。全部登入回傳 True。"""
    pages = {}
    for site in sites:
        page = context.new_page()
        page.goto(site.probe_url, wait_until="domcontentloaded", timeout=60_000)
        pages[site.name] = page
    while True:
        pending = []
        for site in sites:
            state = site.login_state(pages[site.name])
            out(f"{site.name:<14} {'已登入' if state == 'logged_in' else '未登入 ← 請在視窗中登入'}")
            if state != "logged_in":
                pending.append(site)
        if not pending:
            for page in pages.values():
                page.close()
            return True
        answer = prompt("登入完成後按 Enter 重新檢查（輸入 q 結束）：")
        if answer.strip().lower() == "q":
            return False
        for site in pending:
            page = pages[site.name]
            if page.is_closed():
                page = pages[site.name] = context.new_page()
            page.goto(site.probe_url, wait_until="domcontentloaded", timeout=60_000)


def run_capture(
    context,
    source: str,
    tickers: list[str],
    universe_dir: Path,
    prompt: Prompt = input,
    out: Output = print,
    clock: CaptureClock | None = None,
) -> Summary:
    site = SITES[source]
    clock = clock or CaptureClock()
    summary = Summary()
    if not ensure_login(context, [site], prompt, out):
        summary.failed = [(ticker, f"{source} 未登入") for ticker in tickers]
        return summary
    page = context.new_page()
    for index, ticker in enumerate(tickers):
        if index:
            time.sleep(PACE_SECONDS)
        out(f"[{index + 1}/{len(tickers)}] {source} {ticker}")
        try:
            if not TICKER_RE.match(ticker):
                raise CaptureError(f"ticker 格式不合法：{ticker!r}")
            count = 0
            for table in site.capture(page, ticker):
                _save(table, source, ticker, universe_dir, clock, out)
                count += 1
            if not count:
                raise CaptureError("沒有可擷取的表格")
            summary.succeeded.append(ticker)
        except Exception as exc:  # 一檔失敗不影響其他檔
            message = str(exc).strip() or type(exc).__name__
            out(f"  失敗：{message}")
            summary.failed.append((ticker, message))
    page.close()
    return summary


def _save(table: Table, source: str, ticker: str, universe_dir: Path, clock: CaptureClock, out: Output) -> None:
    captured_at = clock.next(source)
    png = compress_png(_screenshot(table.element))
    fragment = table.element.evaluate("e => e.outerHTML")
    result = commit_capture(
        universe_dir,
        ticker,
        source,
        url=table.url,
        captured_at=captured_at,
        periods=table.periods,
        display_unit=table.display_unit,
        png=png,
        html_text=table_html(fragment, table.rows, table.html_mode),
        txt=table_text(table.rows),
    )
    line = f"  {result.capture}：{result.periods} 期，table.png {len(png) // 1024} KB"
    if result.removed_captures:
        line += f"，移除未引用的擷取 {', '.join(result.removed_captures)}"
    out(line)
    if len(png) > PNG_WARN_BYTES:
        out(f"  警告：table.png 超過 {PNG_WARN_BYTES // 1024} KB")


def _screenshot(element) -> bytes:
    """只截表格區塊，四周留 `SHOT_MARGIN` 像素，避免貼齊邊緣的文字被裁掉。

    表格右緣超出視窗時暫時加寬視窗。
    """
    element.evaluate(_ISOLATE_JS)
    page = element.page
    original = page.viewport_size
    box = element.evaluate(
        """e => { const r = e.getBoundingClientRect();
                  return {x: r.left + window.scrollX, y: r.top + window.scrollY,
                          width: Math.max(r.width, e.scrollWidth), height: Math.max(r.height, e.scrollHeight)}; }"""
    )
    right = box["x"] + box["width"] + SHOT_MARGIN
    if original and right > original["width"]:
        page.set_viewport_size({"width": int(right) + 20, "height": original["height"]})
        page.wait_for_timeout(500)
    try:
        clip = {
            "x": max(box["x"] - SHOT_MARGIN, 0),
            "y": max(box["y"] - SHOT_MARGIN, 0),
            "width": box["width"] + 2 * SHOT_MARGIN,
            "height": box["height"] + 2 * SHOT_MARGIN,
        }
        return page.screenshot(clip=clip, full_page=True)
    finally:
        if original and page.viewport_size != original:
            page.set_viewport_size(original)


def report(summary: Summary, universe_dir: Path, out: Output = print) -> int:
    """列出成功與失敗清單並驗證整個 universe；全部成功且驗證通過回傳 0。"""
    out("")
    out(f"成功 {len(summary.succeeded)}：{', '.join(summary.succeeded) or '—'}")
    out(f"失敗 {len(summary.failed)}：")
    for ticker, message in summary.failed:
        out(f"  {ticker}：{message}")
    errors = validate_universe(universe_dir)
    for error in errors:
        out(error)
    out(f"驗證：{'通過' if not errors else f'{len(errors)} 個錯誤'}")
    return 0 if not summary.failed and not errors else 1
