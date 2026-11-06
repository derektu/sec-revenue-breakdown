"""整個 `data/universe/` 的驗證：`tickers.csv`、每個對照目錄與兩者的交叉檢查。"""

from __future__ import annotations

from pathlib import Path

from .model import (
    CAPTURES_DIR,
    DEFAULT_UNIVERSE_DIR,
    LETTER_RE,
    REFERENCES_DIR,
    REFERENCE_FILE,
    TICKERS_FILE,
    TICKER_RE,
    reference_dir,
)
from .references import check_reference, visible_entries
from .tickers import parse_tickers_csv


def validate_universe(universe_dir: Path = DEFAULT_UNIVERSE_DIR) -> list[str]:
    """驗證 `tickers.csv` 與 `references/` 下所有對照目錄，回傳全部錯誤。

    對照目錄不需要列在 `tickers.csv`：對照資料可先於 parser 大量擷取。
    """
    universe_dir = Path(universe_dir)
    errors: list[str] = []
    csv_path = universe_dir / TICKERS_FILE
    parsed = parse_tickers_csv(csv_path, errors)
    sources_by_ticker: dict[str, set[str]] = {}
    references = universe_dir / REFERENCES_DIR
    if references.exists() and not references.is_dir():
        errors.append(f"{references}: 須為目錄")
    elif references.is_dir():
        _check_layout(universe_dir, references, sources_by_ticker, errors)
    for line, entry in parsed.entries:
        if entry.status != "ok":
            continue
        available = sources_by_ticker.get(entry.ticker, set())
        if entry.adopted_source not in available:
            errors.append(
                f"{csv_path}:{line}: adopted_source {entry.adopted_source} 不在 {entry.ticker} 對照檔的來源中"
                f"（現有：{', '.join(sorted(available)) or '無對照檔'}）"
            )
    return errors


def _check_layout(
    universe_dir: Path,
    references: Path,
    sources_by_ticker: dict[str, set[str]],
    errors: list[str],
) -> None:
    for letter in visible_entries(references):
        if not letter.is_dir():
            errors.append(f"{letter}: references/ 下只能有首字母目錄")
            continue
        if not LETTER_RE.match(letter.name):
            errors.append(f"{letter}: 首字母目錄須為單一大寫字母")
            continue
        for folder in visible_entries(letter):
            if not folder.is_dir():
                errors.append(f"{folder}: 首字母目錄下只能有 ticker 目錄")
                continue
            ticker = folder.name
            if not TICKER_RE.match(ticker):
                errors.append(f"{folder}: 目錄名稱 {ticker!r} 不符合 ticker 格式")
                continue
            if ticker[0] != letter.name:
                errors.append(f"{folder}: {ticker} 應位於 {reference_dir(ticker, universe_dir)}")
            for extra in visible_entries(folder):
                if extra.name not in (REFERENCE_FILE, CAPTURES_DIR):
                    errors.append(f"{extra}: ticker 目錄只能放 {REFERENCE_FILE} 與 {CAPTURES_DIR}/")
            reference = folder / REFERENCE_FILE
            if not reference.exists():
                errors.append(f"{folder}: 缺少 {REFERENCE_FILE}")
                continue
            data = check_reference(reference, ticker, errors)
            if isinstance(data, dict) and isinstance(data.get("sources"), dict):
                sources_by_ticker[ticker] = set(data["sources"])
