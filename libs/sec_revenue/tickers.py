"""CLI 的 ticker 選擇：`--tickers`、`--ticker-file` 與 `--all`。

`ALL` 是 Allstate 的 ticker，不是保留字；選擇全部公司一律用 `--all`。
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from .universe import TICKER_RE, load_tickers


def parse_tickers(tickers: list[str] | None = None, file: Path | None = None) -> list[str]:
    """合併 `--tickers` 與 `--ticker-file`，去重並保留順序；格式不符的 ticker 立即拒絕。"""
    names = []
    for item in tickers or []:
        names.extend(part.strip().upper() for part in item.split(",") if part.strip())
    if file:
        if file.suffix == ".json":
            payload = json.loads(file.read_text())
            if not isinstance(payload, list) or any(not isinstance(t, str) for t in payload):
                raise ValueError("ticker JSON 必須是字串清單")
            names.extend(t.strip().upper() for t in payload if t.strip())
        else:
            for line in file.read_text().splitlines():
                names.extend(
                    t.upper()
                    for t in re.split(r"[\s,]+", line.split("#", 1)[0].strip())
                    if t
                )
        if not names:
            raise ValueError("ticker 清單檔為空；不會自動選擇全部公司")
    invalid = [name for name in names if not TICKER_RE.fullmatch(name)]
    if invalid:
        raise ValueError("ticker 格式不符：" + ", ".join(invalid))
    return list(dict.fromkeys(names))


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
