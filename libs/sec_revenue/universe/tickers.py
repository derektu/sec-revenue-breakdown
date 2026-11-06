"""`tickers.csv` 的讀取與驗證，以及 CLI 的 ticker 解析（`--tickers`、`--ticker-file`）。

`ALL` 是 Allstate 的 ticker，不是保留字；選擇全部公司一律用 `--all`。
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .model import (
    CIK_RE,
    COLUMNS,
    DEFAULT_UNIVERSE_DIR,
    SCORE_RANGE,
    SCORE_RE,
    SOURCES,
    STATUSES,
    TICKERS_FILE,
    TICKER_RE,
    TickerEntry,
    UniverseError,
)


@dataclass
class _TickerParse:
    entries: list[tuple[int, TickerEntry]]


def read_ticker_rows(path: Path) -> list[tuple[int, list[str]]]:
    """回傳 `(起始行號, 欄位)`；行號為檔案實際行號，空白列略過。

    非 UTF-8、CSV 語法錯誤或讀檔失敗時丟出 `UniverseError`。
    """
    label = str(path)
    try:
        text = Path(path).read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UniverseError([f"{label}: 須為 UTF-8 編碼"])
    except OSError as exc:
        raise UniverseError([f"{label}: 無法讀取（{exc.strerror or exc}）"])
    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[tuple[int, list[str]]] = []
    previous = 0
    try:
        for row in reader:
            start, previous = previous + 1, reader.line_num
            if any(cell.strip(" ") for cell in row):
                rows.append((start, row))
    except csv.Error as exc:
        raise UniverseError([f"{label}:{previous + 1}: CSV 格式錯誤（{exc}）"])
    return rows


def validate_tickers(path: Path) -> list[str]:
    errors: list[str] = []
    parse_tickers_csv(Path(path), errors)
    return errors


def load_tickers(path: Path | None = None) -> list[TickerEntry]:
    """讀取並驗證 `tickers.csv`。`status=ok` 的 `adopted_source` 是否存在於對照檔，由 `validate_universe` 檢查。"""
    path = Path(path) if path else DEFAULT_UNIVERSE_DIR / TICKERS_FILE
    errors: list[str] = []
    parsed = parse_tickers_csv(path, errors)
    if errors:
        raise UniverseError(errors)
    return [entry for _, entry in parsed.entries]


def parse_tickers_csv(path: Path, errors: list[str]) -> _TickerParse:
    result = _TickerParse([])
    label = str(path)
    if not path.exists():
        errors.append(f"{label}: 找不到檔案")
        return result
    try:
        rows = read_ticker_rows(path)
    except UniverseError as exc:
        errors.extend(exc.errors)
        return result
    if not rows:
        errors.append(f"{label}: 檔案是空的")
        return result
    header_line, header = rows[0]
    if tuple(cell.strip(" ") for cell in header) != COLUMNS:
        errors.append(f"{label}:{header_line}: 表頭須為 {','.join(COLUMNS)}，實際為 {','.join(header)}")
        return result
    seen: dict[str, int] = {}
    for line, row in rows[1:]:
        where = f"{label}:{line}"
        if len(row) != len(COLUMNS):
            errors.append(f"{where}: 欄位數須為 {len(COLUMNS)}，實際為 {len(row)}")
            continue
        cell = dict(zip(COLUMNS, (value.strip(" ") for value in row)))
        before = len(errors)
        ticker = cell["ticker"]
        if not TICKER_RE.match(ticker):
            errors.append(f"{where}: ticker {ticker!r} 不符合 {TICKER_RE.pattern}")
        elif ticker in seen:
            errors.append(f"{where}: ticker {ticker} 與第 {seen[ticker]} 行重複")
        else:
            seen[ticker] = line
        ciks = tuple(part.strip(" ") for part in cell["cik"].split(";")) if cell["cik"] else ()
        if not ciks:
            errors.append(f"{where}: cik 不可空白")
        for cik in ciks:
            if not CIK_RE.match(cik):
                errors.append(f"{where}: cik {cik!r} 須為不含前導零的數字")
        if len(set(ciks)) != len(ciks):
            errors.append(f"{where}: cik 有重複值")
        if not cell["name"]:
            errors.append(f"{where}: name 不可空白")
        status = cell["status"]
        if status not in STATUSES:
            errors.append(f"{where}: status {status!r} 須為 {'/'.join(STATUSES)}")
        adopted = cell["adopted_source"] or None
        if adopted is not None and adopted not in SOURCES:
            errors.append(f"{where}: adopted_source {adopted!r} 須為空白或 {'/'.join(SOURCES)}")
        score: int | None = None
        raw_score = cell["stability_score"]
        if raw_score:
            if SCORE_RE.match(raw_score) and int(raw_score) in SCORE_RANGE:
                score = int(raw_score)
            else:
                errors.append(f"{where}: stability_score {raw_score!r} 須為空白或 1–5 的整數")
        if status == "ok":
            if adopted is None:
                errors.append(f"{where}: status 為 ok 時 adopted_source 必填")
            if not raw_score:
                errors.append(f"{where}: status 為 ok 時 stability_score 必填")
        if len(errors) == before:
            entry = TickerEntry(
                ticker=ticker,
                ciks=ciks,
                name=cell["name"],
                status=status,
                adopted_source=adopted,
                stability_score=score,
                stability_note=cell["stability_note"],
                notes=cell["notes"],
            )
            result.entries.append((line, entry))
    return result


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
