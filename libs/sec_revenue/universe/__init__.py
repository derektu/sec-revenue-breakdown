"""ticker 清單與對照資料的讀取與驗證。

格式定義見 `docs/architecture/universe.md`。驗證函式逐項收集錯誤、不在第一個錯誤中止，
讓人工維護者一次看到所有問題；`load_*` 函式只在資料全部合法時回傳結構化結果。
"""

from __future__ import annotations

from .model import (
    capture_file_path,
    CAPTURE_FILES,
    capture_id,
    CAPTURE_ID_RE,
    CAPTURES_DIR,
    CIK_RE,
    COLUMNS,
    DATE_RE,
    DEFAULT_UNIVERSE_DIR,
    DISPLAY_UNITS,
    DisplayValue,
    KINDS,
    LETTER_RE,
    METHODS,
    parse_display,
    reference_dir,
    REFERENCE_FILE,
    REFERENCES_DIR,
    ROOT,
    SCHEMA_VERSION,
    SCORE_RANGE,
    SCORE_RE,
    SHA256_RE,
    SOURCES,
    STATUSES,
    TICKER_RE,
    TickerEntry,
    TICKERS_FILE,
    TIMESTAMP_RE,
    UNIT_MULTIPLIERS,
    UniverseError,
)
from .tickers import (
    parse_tickers,
    load_tickers,
    read_ticker_rows,
    validate_tickers,
)
from .references import (
    load_reference,
    validate_reference,
)
from .validate import (
    validate_universe,
)

__all__ = [
    "parse_tickers",
    "capture_file_path",
    "CAPTURE_FILES",
    "capture_id",
    "CAPTURE_ID_RE",
    "CAPTURES_DIR",
    "CIK_RE",
    "COLUMNS",
    "DATE_RE",
    "DEFAULT_UNIVERSE_DIR",
    "DISPLAY_UNITS",
    "DisplayValue",
    "KINDS",
    "LETTER_RE",
    "METHODS",
    "parse_display",
    "reference_dir",
    "REFERENCE_FILE",
    "REFERENCES_DIR",
    "ROOT",
    "SCHEMA_VERSION",
    "SCORE_RANGE",
    "SCORE_RE",
    "SHA256_RE",
    "SOURCES",
    "STATUSES",
    "TICKER_RE",
    "TickerEntry",
    "TICKERS_FILE",
    "TIMESTAMP_RE",
    "UNIT_MULTIPLIERS",
    "UniverseError",
    "load_tickers",
    "read_ticker_rows",
    "validate_tickers",
    "load_reference",
    "validate_reference",
    "validate_universe",
]
