"""公司目錄：`<首字母>/<ticker 小寫，非英數字元改為底線>/`。

每家公司有公司 parser（`parser.py`，定義 `TICKER`、`VIEW`、`TOTAL`、`compose`、`categories`）與說明（`parser.md`）。
"""

from __future__ import annotations

import importlib
from pathlib import Path

from ..revenue.source import ParserSource

ROOT = Path(__file__).resolve().parent
# 業務分部軸常被公司用於地區分部（例如 AAPL 的 Americas、Europe），公司 parser 使用時 parser.md 必須說明為何是業務別。
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"


def module_dir(ticker: str) -> Path:
    name = "".join(c if c.isalnum() else "_" for c in ticker.lower())
    return ROOT / ticker[0].lower() / name


def directories() -> list[Path]:
    return sorted(p.parent for p in ROOT.glob("*/*/parser.py"))


def tickers() -> list[str]:
    """有公司 parser 的 ticker，以各自宣告的 ticker 為準。"""
    return sorted(load(directory).ticker for directory in directories())


def load(directory: Path) -> ParserSource:
    return ParserSource(importlib.import_module(f"{__name__}.{directory.parent.name}.{directory.name}.parser"))


def parser_source(ticker: str) -> ParserSource:
    """回傳公司 parser；檢查宣告的 ticker 與 parser.md。"""
    directory = module_dir(ticker)
    source = directory / "parser.py"
    if not source.exists():
        raise ValueError(f"{ticker} 沒有公司 parser（{source}）")
    loaded = load(directory)
    if loaded.ticker != ticker:
        raise ValueError(f"{source} 宣告的 ticker 是 {loaded.ticker}，不是 {ticker}")
    notes = directory / "parser.md"
    if not notes.exists():
        raise ValueError(f"{ticker} 缺少 {notes}；每家公司都要有 parser.md")
    check_notes(ticker, SEGMENT_AXIS in source.read_text(), notes.read_text())
    return loaded


def check_notes(ticker: str, uses_segment_axis: bool, notes: str):
    """使用業務分部軸時，parser.md 必須提到這個軸並說明成員是業務別而不是地區。"""
    if uses_segment_axis and SEGMENT_AXIS not in notes:
        raise ValueError(
            f"{ticker} 使用 {SEGMENT_AXIS}；parser.md 必須寫明這個軸的成員是業務別而不是地區（並提到 {SEGMENT_AXIS}）"
        )
