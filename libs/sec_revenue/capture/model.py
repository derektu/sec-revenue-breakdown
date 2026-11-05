"""adapter 與外殼之間交換的資料結構。不依賴 Playwright，可在測試中直接建構。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# `table.html` 的產生方式，見 `evidence.table_html()`。
HtmlMode = Literal["clean", "rebuild"]


class CaptureError(Exception):
    """單一 ticker 擷取失敗；訊息列入最後的失敗清單。"""


@dataclass(frozen=True)
class Period:
    """表格上的一期；`values` 鍵為分類原文，值為頁面數值原文（display）。空值不放入。"""

    label: str
    kind: Literal["Q", "FY"]
    values: dict[str, str]
    period_end: str | None = None


@dataclass
class Table:
    """adapter 定位好、可以擷取的一張表。

    `element` 是表格區塊的 Playwright Locator，外殼對它截圖並讀出 html；
    `rows` 是表格文字（含表頭列），寫成 `table.txt`，`html_mode` 為 `rebuild` 時也用來重建 html。
    """

    url: str
    element: Any
    rows: list[list[str]]
    periods: list[Period]
    html_mode: HtmlMode
    display_unit: str | None = None
