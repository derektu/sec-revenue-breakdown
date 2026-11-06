"""download 的 ticker 選擇：任何格式正確的 ticker，或 `--all` 代表 `tickers.csv` 的全部公司。"""

from __future__ import annotations

from pathlib import Path

from ..universe import load_tickers, parse_tickers


class DownloadTickers:
    """下載用：任何格式正確的 ticker 都接受；`--all` 代表 `tickers.csv` 的全部公司。

    必須明確指定 ticker 或 `--all`，避免意外下載整份清單。
    """

    def __init__(self, tickers_csv: Path | None = None):
        self.tickers_csv = tickers_csv

    def select(
        self,
        tickers: list[str] | None = None,
        file: Path | None = None,
        all_tickers: bool = False,
    ) -> list[str]:
        names = parse_tickers(tickers, file)
        if all_tickers:
            listed = [entry.ticker for entry in load_tickers(self.tickers_csv)]
            names = list(dict.fromkeys(listed + names))
        if not names:
            raise ValueError("download 需指定 --tickers、--ticker-file 或 --all")
        return names
