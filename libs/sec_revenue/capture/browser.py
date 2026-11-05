"""專用瀏覽器：Playwright 內建的 Chromium，使用 repo 以外的 persistent profile。

登入時開視窗，使用者在視窗中自行登入；擷取預設不開視窗，不干擾使用者的其他操作。
登入狀態由瀏覽器自己保存在 profile。程式不經手帳密，不讀取、匯出或寫入 cookie 與 token（`AGENTS.md`）。
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


def open_context(playwright, headless: bool = False):
    """開啟 persistent context。同一個 profile 同時只能由一個程式開啟。

    有無視窗都用完整的 Chromium（`channel="chromium"`），兩種模式共用同一個 profile。
    """
    path = profile_dir()
    path.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(path),
        channel="chromium",
        headless=headless,
        viewport=VIEWPORT,
        device_scale_factor=1,
    )
