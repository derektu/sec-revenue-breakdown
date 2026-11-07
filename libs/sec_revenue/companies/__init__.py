"""公司目錄：`<首字母>/<ticker 小寫，非英數字元改為底線>/`。

每家公司有公司 parser（`parser.py`，定義 `TICKER`、`VIEW`、`TOTAL`、`compose`、`categories`）與說明（`parser.md`）。
一家公司的 `parser.py` 載入失敗只影響那一家：列出 ticker 時跳過並記錄（`scan`），其他公司照常處理。
"""

from __future__ import annotations

import importlib
from pathlib import Path

from ..revenue.source import ParserSource

ROOT = Path(__file__).resolve().parent
# 業務分部軸常被公司用於地區分部（例如 AAPL 的 Americas、Europe），公司 parser 使用時 parser.md 必須說明為何是業務別。
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
# 公司 parser 必須定義的常數；缺少任何一個即載入失敗。
REQUIRED = ("TICKER", "VIEW", "TOTAL")


class ParserLoadError(ValueError):
    """`parser.py` 載入失敗：讀不進來（語法錯誤、import 失敗、執行時丟出例外），或缺少 `REQUIRED` 的常數。

    `ticker` 是記錄錯誤用的名稱：`parser.py` 讀得到字串 `TICKER` 時用它；讀不到時用目錄名稱轉大寫（例如 `brk_b` →
    `BRK_B`），這時它不一定是實際的 ticker，訊息中的檔案路徑才是定位依據。
    """

    def __init__(self, ticker: str, message: str):
        super().__init__(message)
        self.ticker = ticker


def module_dir(ticker: str) -> Path:
    name = "".join(c if c.isalnum() else "_" for c in ticker.lower())
    return ROOT / ticker[0].lower() / name


def directories() -> list[Path]:
    return sorted(p.parent for p in ROOT.glob("*/*/parser.py"))


def scan() -> tuple[list[str], list[ParserLoadError]]:
    """（有公司 parser 的 ticker, 每個載入失敗的 `parser.py` 的錯誤）；ticker 以各自宣告的 `TICKER` 為準。

    載入失敗依檔案各記一筆：名稱與正常的 ticker 或另一個載入失敗的檔案相同時，每一筆都保留（訊息含檔案路徑）。

    只確認每個 `parser.py` 載入得了、定義了 `REQUIRED` 的常數，不檢核 `VIEW` 的值與自訂點：一家公司宣告錯誤或載入
    失敗時，列出其他 ticker 與處理其他公司都不受影響。宣告的錯誤在處理那家公司時（`parser_source`）才報出。
    """
    found, failures = [], []
    for directory in directories():
        try:
            found.append(declared(directory).TICKER)
        except ParserLoadError as error:
            failures.append(error)
    return sorted(found), failures


def tickers() -> list[str]:
    """有公司 parser 且載入成功的 ticker（見 `scan`）。"""
    return scan()[0]


def load_failures() -> list[ParserLoadError]:
    """每個載入失敗的 `parser.py` 的錯誤，訊息含檔案路徑（見 `scan` 與 `ParserLoadError`）。"""
    return scan()[1]


def module(directory: Path):
    return importlib.import_module(f"{__name__}.{directory.parent.name}.{directory.name}.parser")


def declared(directory: Path):
    """載入 `parser.py` 並確認 `REQUIRED` 的常數都有定義、`TICKER` 是非空字串；失敗時丟出 `ParserLoadError`。"""
    source = directory / "parser.py"
    label = directory.name.upper()
    try:
        loaded = module(directory)
    except Exception as error:  # noqa: BLE001 - 公司 parser 的任何載入錯誤都只停這一家
        raise ParserLoadError(label, f"{source} 載入失敗：{type(error).__name__}: {error}") from error
    ticker = getattr(loaded, "TICKER", None)
    valid = isinstance(ticker, str) and bool(ticker)
    if valid:
        label = ticker
    missing = [name for name in REQUIRED if not hasattr(loaded, name)]
    if missing:
        raise ParserLoadError(label, f"{source} 缺少 {'、'.join(missing)}")
    if not valid:
        raise ParserLoadError(label, f"{source} 的 TICKER 必須是非空字串，收到 {ticker!r}")
    return loaded


def load(directory: Path) -> ParserSource:
    return ParserSource(declared(directory))


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
