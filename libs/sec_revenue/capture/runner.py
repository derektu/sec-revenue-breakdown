"""`setup` 與 `capture` 的流程：登入檢查、逐檔擷取、寫入證據與合併、最後整體驗證。

一個 ticker 的所有表（富途一期一張）都截圖完成後才一次寫入；中途失敗就整檔不寫，不留下部分期別。
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..universe import TICKER_RE, capture_id, validate_universe
from .evidence import PNG_WARN_BYTES, compress_png, table_html, table_text
from .merge import PendingCapture, commit_captures
from .model import CaptureError, Table
from .browser import VIEWPORT
from .sites import SITES, Site

# 兩檔之間的預設間隔（秒），讓擷取速度接近人工操作。
DEFAULT_PAUSE = 10.0
# 截圖時表格四周保留的像素。
SHOT_MARGIN = 16
# 一個畫面只顯示一期的來源（富途）每檔擷取的季度範圍：最近 12 季（三年）。
DEFAULT_PERIODS = 12

Prompt = Callable[[str], str]
Output = Callable[[str], None]

# 截圖前隱藏表格以外的 fixed／sticky 元素（例如帶有帳號頭像的頁首），
# 並讓祖先元素不裁切，使截圖只含完整的表格。原本的 inline style 記在 window 上，截圖後由 _RESTORE_JS 復原，
# 避免影響同一頁後續的操作（例如富途切換期間）。
_ISOLATE_JS = """
el => {
  const saved = window.__secCaptureSaved = [];
  const set = (n, prop, value) => {
    saved.push([n, prop, n.style.getPropertyValue(prop), n.style.getPropertyPriority(prop)]);
    n.style.setProperty(prop, value, 'important');
  };
  for (const n of document.querySelectorAll('body *')) {
    if (n.contains(el) || el.contains(n)) continue;
    const pos = getComputedStyle(n).position;
    if (pos === 'fixed' || pos === 'sticky') set(n, 'visibility', 'hidden');
  }
  for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    set(a, 'overflow', 'visible');
  }
}
"""

_RESTORE_JS = """
() => {
  for (const [n, prop, value, priority] of (window.__secCaptureSaved || []).reverse()) {
    if (value) n.style.setProperty(prop, value, priority); else n.style.removeProperty(prop);
  }
  window.__secCaptureSaved = [];
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


def check_login(context, sites: list[Site]) -> dict[str, str]:
    """逐站檢查登入狀態，不等待使用者；回傳 `{來源: logged_in | logged_out}`。"""
    states = {}
    for site in sites:
        page = context.new_page()
        try:
            page.goto(site.probe_url, wait_until="domcontentloaded", timeout=60_000)
            states[site.name] = site.login_state(page)
        finally:
            page.close()
    return states


OpenBrowser = Callable[[bool], object]


def run_capture(
    open_browser: OpenBrowser,
    source: str,
    tickers: list[str],
    universe_dir: Path,
    *,
    headless: bool = True,
    periods: int = DEFAULT_PERIODS,
    pause: float = DEFAULT_PAUSE,
    prompt: Prompt = input,
    out: Output = print,
    clock: CaptureClock | None = None,
) -> Summary:
    """擷取一個來源的多個 ticker。

    `open_browser(headless)` 開啟專用 profile 的瀏覽器。無視窗執行時先檢查登入；
    未登入就關閉無視窗瀏覽器，改開視窗走 `setup` 的登入流程，登入後再以無視窗繼續。
    """
    site = SITES[source]
    clock = clock or CaptureClock()
    summary = Summary()
    context = open_browser(headless)
    try:
        if not headless:
            ok = ensure_login(context, [site], prompt, out)
        elif check_login(context, [site])[site.name] == "logged_in":
            ok = True
        else:
            out(f"{source} 未登入，開啟瀏覽器視窗登入")
            context.close()
            context = None
            context = open_browser(False)
            ok = ensure_login(context, [site], prompt, out)
            context.close()
            context = None
            if ok:
                context = open_browser(True)
        if not ok:
            summary.failed = [(ticker, f"{source} 未登入") for ticker in tickers]
            return summary
        page = context.new_page()
        for index, ticker in enumerate(tickers):
            if index:
                time.sleep(pause)
            out(f"[{index + 1}/{len(tickers)}] {source} {ticker}")
            try:
                if not TICKER_RE.match(ticker):
                    raise CaptureError(f"ticker 格式不合法：{ticker!r}")
                pending = [_shoot(table, source, clock) for table in site.capture(page, ticker, periods)]
                if not pending:
                    raise CaptureError("沒有可擷取的表格")
                _commit(pending, source, ticker, universe_dir, out)
                summary.succeeded.append(ticker)
            except Exception as exc:  # 一檔失敗不影響其他檔
                message = str(exc).strip() or type(exc).__name__
                out(f"  失敗：{message}")
                summary.failed.append((ticker, message))
        return summary
    finally:
        if context is not None:
            context.close()


def _shoot(table: Table, source: str, clock: CaptureClock) -> PendingCapture:
    """截圖並產生證據內容，尚不寫入。"""
    captured_at = clock.next(source)
    png = compress_png(_screenshot(table.element))
    fragment = table.element.evaluate("e => e.outerHTML")
    return PendingCapture(
        url=table.url,
        captured_at=captured_at,
        periods=table.periods,
        display_unit=table.display_unit,
        png=png,
        html_text=table_html(fragment, table.rows, table.html_mode, table.caption),
        txt=table_text(table.rows, table.caption),
    )


def _commit(pending: list[PendingCapture], source: str, ticker: str, universe_dir: Path, out: Output) -> None:
    result = commit_captures(universe_dir, ticker, source, pending)
    sizes = [len(p.png) for p in pending]
    line = f"  {len(result.captures)} 次擷取、{result.periods} 期，table.png 最大 {max(sizes) // 1024} KB"
    if result.removed_captures:
        line += f"，移除未引用的擷取 {', '.join(result.removed_captures)}"
    out(line)
    for p, size in zip(pending, sizes):
        if size > PNG_WARN_BYTES:
            out(f"  警告：{capture_id(p.captured_at)} 的 table.png 超過 {PNG_WARN_BYTES // 1024} KB")


def _screenshot(element) -> bytes:
    """只截表格區塊，四周留 `SHOT_MARGIN` 像素，避免貼齊邊緣的文字被裁掉。

    表格右緣超出視窗時暫時加寬視窗；截完恢復成 `VIEWPORT`。
    """
    page = element.page
    try:
        element.evaluate(_ISOLATE_JS)
        box = _box(element)
        right = box["x"] + box["width"] + SHOT_MARGIN
        if right > page.viewport_size["width"]:
            page.set_viewport_size({"width": int(right) + 20, "height": page.viewport_size["height"]})
            page.wait_for_timeout(500)
            box = _box(element)
        clip = {
            "x": max(box["x"] - SHOT_MARGIN, 0),
            "y": max(box["y"] - SHOT_MARGIN, 0),
            "width": box["width"] + 2 * SHOT_MARGIN,
            "height": box["height"] + 2 * SHOT_MARGIN,
        }
        return page.screenshot(clip=clip, full_page=True)
    finally:
        page.evaluate(_RESTORE_JS)
        if page.viewport_size != VIEWPORT:
            page.set_viewport_size(VIEWPORT)


def _box(element) -> dict:
    return element.evaluate(
        """e => { const r = e.getBoundingClientRect();
                  return {x: r.left + window.scrollX, y: r.top + window.scrollY,
                          width: Math.max(r.width, e.scrollWidth), height: Math.max(r.height, e.scrollHeight)}; }"""
    )


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
