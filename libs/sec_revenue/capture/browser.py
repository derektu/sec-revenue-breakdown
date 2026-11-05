"""專用瀏覽器：Playwright 內建的 Chromium，有視窗，使用 repo 以外的 persistent profile。

使用者在這個視窗中自行登入；登入狀態由瀏覽器自己保存在 profile。程式不經手帳密，
不讀取、匯出或寫入 cookie 與 token（`AGENTS.md`）。
"""

from __future__ import annotations

import os
from pathlib import Path

PROFILE_ENV = "SEC_REVENUE_CAPTURE_PROFILE"
DEFAULT_PROFILE = Path.home() / ".sec-revenue-capture" / "profile"
# 固定視窗大小與 device scale 1，讓截圖尺寸穩定、檔案不因 Retina 放大四倍。
VIEWPORT = {"width": 1400, "height": 900}


def profile_dir() -> Path:
    return Path(os.environ.get(PROFILE_ENV) or DEFAULT_PROFILE).expanduser()


def open_context(playwright):
    """開啟有視窗的 persistent context。同一個 profile 同時只能由一個程式開啟。"""
    path = profile_dir()
    path.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(path),
        headless=False,
        viewport=VIEWPORT,
        device_scale_factor=1,
    )
