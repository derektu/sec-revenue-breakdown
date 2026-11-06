"""ticker 清單與對照資料共用的常數、格式規則與資料結構。"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


DEFAULT_UNIVERSE_DIR = ROOT / "data" / "universe"


TICKERS_FILE = "tickers.csv"


REFERENCES_DIR = "references"


REFERENCE_FILE = "reference.json"


CAPTURES_DIR = "captures"


# 每次瀏覽器擷取保存的證據檔；鍵為 reference.json 的 `files` 欄位名稱。
CAPTURE_FILES = {"png": "table.png", "html": "table.html", "txt": "table.txt"}


SCHEMA_VERSION = 1


COLUMNS = (
    "ticker",
    "cik",
    "name",
    "status",
    "adopted_source",
    "stability_score",
    "stability_note",
    "notes",
)


STATUSES = ("wip", "ok", "drop")


SOURCES = ("stockanalysis", "futu", "tradingview", "manual")


METHODS = ("browser_dom", "manual")


KINDS = ("Q", "FY")


SCORE_RANGE = range(1, 6)


# 所有 pattern 只接受 ASCII 數字與一般空格；全形數字、其他文字系統的數字與 NBSP 都不合法。
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)?$", re.ASCII)


CIK_RE = re.compile(r"^[1-9][0-9]{0,9}$", re.ASCII)


SCORE_RE = re.compile(r"^[0-9]+$", re.ASCII)


DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", re.ASCII)


TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|\+00:00)$", re.ASCII
)


CAPTURE_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$", re.ASCII)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


LETTER_RE = re.compile(r"^[A-Z]$", re.ASCII)


# display 的單位倍數；無單位代表美元原值，或套用來源的 `display_unit`。
UNIT_MULTIPLIERS = {
    "K": Decimal(10) ** 3,
    "M": Decimal(10) ** 6,
    "B": Decimal(10) ** 9,
    "T": Decimal(10) ** 12,
    "萬": Decimal(10) ** 4,
    "億": Decimal(10) ** 8,
}


DISPLAY_UNITS = ("K", "M", "B", "萬", "億")


_UNIT = "[KMBT萬億]?"


_NUMBER_RE = re.compile(
    rf"^\$?(?P<int>[0-9]{{1,3}}(?:,[0-9]{{3}})+|[0-9]+)(?:\.(?P<frac>[0-9]+))? *(?P<unit>{_UNIT})$",
    re.ASCII,
)


# 括號負數：單位可在括號內 `(1.5B)` 或括號外 `(1.5)B`。
_PAREN_RE = re.compile(rf"^\((?P<body>[^()]+)\) *(?P<unit>{_UNIT})$", re.ASCII)


_MINUS = ("-", "−")


class UniverseError(ValueError):
    """資料不合法；`errors` 保存全部錯誤訊息。"""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class TickerEntry:
    ticker: str
    ciks: tuple[str, ...]
    name: str
    status: str
    adopted_source: str | None
    stability_score: int | None
    stability_note: str
    notes: str


@dataclass(frozen=True)
class DisplayValue:
    """頁面原文解析結果；`tolerance` 為最後一位數字的半個單位（美元）。"""

    usd: Decimal
    tolerance: Decimal


def reference_dir(ticker: str, universe_dir: Path = DEFAULT_UNIVERSE_DIR) -> Path:
    """對照目錄：`references/<首字母>/<TICKER>/`，TICKER 保留原樣（例如 `B/BRK-B`）。"""
    if not TICKER_RE.match(ticker):
        raise ValueError(f"ticker 格式不合法：{ticker!r}")
    return Path(universe_dir) / REFERENCES_DIR / ticker[0] / ticker


def parse_display(display: str, default_unit: str | None = None) -> DisplayValue:
    """解析頁面數值原文，例如 `57.58B`、`(1,234.5)M`、`-3.2億`、`1,234`。

    `default_unit` 套用在不帶單位的 display（表頭寫「Millions」、儲存格只有數字的情況）；
    display 自己帶單位時以自己的單位為準。
    """
    if default_unit is not None and default_unit not in DISPLAY_UNITS:
        raise ValueError(f"display_unit {default_unit!r} 須為 {'/'.join(DISPLAY_UNITS)}")
    text = display.strip(" ")
    negative = False
    wrapped = _PAREN_RE.match(text)
    if wrapped:
        negative, text = True, wrapped["body"].strip(" ") + wrapped["unit"]
    elif text[:1] in _MINUS:
        negative, text = True, text[1:].lstrip(" ")
    match = _NUMBER_RE.match(text)
    if not match:
        raise ValueError(f"無法解析 display：{display!r}")
    frac = match["frac"] or ""
    number = Decimal(match["int"].replace(",", "") + ("." + frac if frac else ""))
    unit = match["unit"] or default_unit
    multiplier = UNIT_MULTIPLIERS[unit] if unit else Decimal(1)
    tolerance = Decimal(10) ** -len(frac) * multiplier / 2
    value = number * multiplier
    return DisplayValue(-value if negative else value, tolerance)


def capture_id(captured_at: str) -> str:
    """擷取時間（UTC ISO 8601）對應的 capture_id：取到秒的 `YYYYMMDDTHHMMSSZ`。"""
    if not valid_timestamp(captured_at):
        raise ValueError(f"captured_at 不合法：{captured_at!r}")
    return dt.datetime.fromisoformat(captured_at).strftime("%Y%m%dT%H%M%SZ")


def capture_file_path(source: str, capture: str, kind: str) -> str:
    """證據檔相對於 ticker 目錄的路徑，例如 `captures/futu/20261104T013829Z/table.png`。"""
    return f"{CAPTURES_DIR}/{source}/{capture}/{CAPTURE_FILES[kind]}"


def valid_date(text: str) -> bool:
    if not DATE_RE.match(text):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def valid_timestamp(text: str) -> bool:
    if not TIMESTAMP_RE.match(text):
        return False
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.utcoffset() == dt.timedelta(0)
