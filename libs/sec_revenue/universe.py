"""ticker 清單與對照資料的讀取與驗證。

格式定義見 `docs/architecture/universe.md`。驗證函式逐項收集錯誤、不在第一個錯誤中止，
讓人工維護者一次看到所有問題；`load_*` 函式只在資料全部合法時回傳結構化結果。
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


# ---------------------------------------------------------------- tickers.csv


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
    _parse_tickers(Path(path), errors)
    return errors


def load_tickers(path: Path | None = None) -> list[TickerEntry]:
    """讀取並驗證 `tickers.csv`。`status=ok` 的 `adopted_source` 是否存在於對照檔，由 `validate_universe` 檢查。"""
    path = Path(path) if path else DEFAULT_UNIVERSE_DIR / TICKERS_FILE
    errors: list[str] = []
    parsed = _parse_tickers(path, errors)
    if errors:
        raise UniverseError(errors)
    return [entry for _, entry in parsed.entries]


def _parse_tickers(path: Path, errors: list[str]) -> _TickerParse:
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


# ------------------------------------------------------------ reference.json


def validate_reference(path: Path, expected_ticker: str | None = None) -> list[str]:
    """驗證單一 `reference.json` 與同目錄的 `captures/`；`expected_ticker` 為目錄推得的 ticker。"""
    errors: list[str] = []
    _check_reference(Path(path), expected_ticker, errors)
    return errors


def load_reference(ticker: str, universe_dir: Path = DEFAULT_UNIVERSE_DIR) -> dict:
    path = reference_dir(ticker, universe_dir) / REFERENCE_FILE
    errors: list[str] = []
    data = _check_reference(path, ticker, errors)
    if errors:
        raise UniverseError(errors)
    return data


def capture_id(captured_at: str) -> str:
    """擷取時間（UTC ISO 8601）對應的 capture_id：取到秒的 `YYYYMMDDTHHMMSSZ`。"""
    if not _valid_timestamp(captured_at):
        raise ValueError(f"captured_at 不合法：{captured_at!r}")
    return dt.datetime.fromisoformat(captured_at).strftime("%Y%m%dT%H%M%SZ")


def capture_file_path(source: str, capture: str, kind: str) -> str:
    """證據檔相對於 ticker 目錄的路徑，例如 `captures/futu/20261104T013829Z/table.png`。"""
    return f"{CAPTURES_DIR}/{source}/{capture}/{CAPTURE_FILES[kind]}"


def _load_json(path: Path, errors: list[str]):
    """讀取 JSON；同一物件內的重複鍵列為錯誤。"""
    label = str(path)
    duplicates: list[str] = []

    def unique_pairs(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    try:
        data = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=unique_pairs)
    except FileNotFoundError:
        errors.append(f"{label}: 找不到檔案")
        return None
    except OSError as exc:
        errors.append(f"{label}: 無法讀取（{exc.strerror or exc}）")
        return None
    except UnicodeDecodeError:
        errors.append(f"{label}: 須為 UTF-8 編碼")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: 不是合法的 JSON（{exc}）")
        return None
    for key in duplicates:
        errors.append(f"{label}: 同一物件內有重複的鍵 {key!r}")
    return data


@dataclass
class _Evidence:
    """reference.json 宣告的 capture 與證據檔，用來找出 `captures/` 下未被引用的項目。"""

    captures: set[tuple[str, str]]
    files: set[str]


def _check_reference(path: Path, expected_ticker: str | None, errors: list[str]) -> dict | None:
    label = str(path)
    data = _load_json(path, errors)
    if data is None:
        return None
    if not isinstance(data, dict):
        errors.append(f"{label}: 頂層須為物件")
        return None
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version 須為整數 {SCHEMA_VERSION}，實際為 {version!r}")
    ticker = data.get("ticker")
    if not isinstance(ticker, str) or not TICKER_RE.match(ticker):
        errors.append(f"{label}: ticker {ticker!r} 不符合 {TICKER_RE.pattern}")
    elif expected_ticker is not None and ticker != expected_ticker:
        errors.append(f"{label}: ticker {ticker} 與目錄 {expected_ticker} 不一致")
    _unknown_keys(label, data, {"schema_version", "ticker", "sources"}, errors)
    evidence = _Evidence(set(), set())
    sources = data.get("sources")
    if not isinstance(sources, dict):
        errors.append(f"{label}: sources 須為物件")
    else:
        if not sources:
            errors.append(f"{label}: sources 至少須有一個來源；沒有資料就不建立對照檔")
        for source, body in sources.items():
            where = f"{label}: sources.{source}"
            if source not in SOURCES:
                errors.append(f"{where}: 來源須為 {'/'.join(SOURCES)}")
            if not isinstance(body, dict):
                errors.append(f"{where}: 須為物件")
                continue
            _check_source(path.parent, source, where, body, evidence, errors)
    _check_capture_tree(path.parent, evidence, errors)
    return data


def _check_source(
    folder: Path, source: str, where: str, body: dict, evidence: _Evidence, errors: list[str]
) -> None:
    _unknown_keys(where, body, {"captures", "periods"}, errors)
    captures = body.get("captures")
    units: dict[str, str | None] = {}
    if not isinstance(captures, dict):
        errors.append(f"{where}: captures 須為物件")
        captures = {}
    elif not captures:
        errors.append(f"{where}: captures 至少須有一次擷取")
    for cid, capture in captures.items():
        at = f"{where}.captures[{cid!r}]"
        evidence.captures.add((source, cid))
        units[cid] = _check_capture(folder, source, cid, at, capture, evidence, errors)
    periods = body.get("periods")
    if not isinstance(periods, list):
        errors.append(f"{where}: periods 須為陣列")
        return
    if not periods:
        errors.append(f"{where}: periods 至少須有一期")
    used: set[str] = set()
    seen_end: dict[tuple[str, str], int] = {}
    seen_label: dict[str, int] = {}
    for index, period in enumerate(periods):
        at = f"{where}.periods[{index}]"
        if not isinstance(period, dict):
            errors.append(f"{at}: 須為物件")
            continue
        before = len(errors)
        ref = period.get("capture")
        if not isinstance(ref, str) or ref not in captures:
            errors.append(f"{at}: capture {ref!r} 須為同來源 captures 中的擷取")
            unit = None
        else:
            used.add(ref)
            unit = units[ref]
        _check_period(at, period, unit, errors)
        if len(errors) != before:
            # 欄位本身不合法時不比對重複，避免以不可 hash 或錯誤型別的值當鍵。
            continue
        label = period["label"]
        if label in seen_label:
            errors.append(f"{at}: label {label!r} 與 periods[{seen_label[label]}] 重複")
        else:
            seen_label[label] = index
        if "period_end" in period:
            key = (period["kind"], period["period_end"])
            if key in seen_end:
                errors.append(f"{at}: kind {key[0]} 期末 {key[1]} 與 periods[{seen_end[key]}] 重複")
            else:
                seen_end[key] = index
    for cid in captures:
        if cid not in used:
            errors.append(f"{where}.captures[{cid!r}]: 沒有任何期別引用此擷取")


def _check_capture(
    folder: Path, source: str, cid: str, at: str, capture, evidence: _Evidence, errors: list[str]
) -> str | None:
    """檢查一次擷取的中繼資料與證據檔；回傳合法的 display_unit。"""
    if not CAPTURE_ID_RE.match(cid):
        errors.append(f"{at}: capture_id 須為 YYYYMMDDTHHMMSSZ")
    if not isinstance(capture, dict):
        errors.append(f"{at}: 須為物件")
        return None
    _unknown_keys(at, capture, {"url", "captured_at", "method", "display_unit", "files"}, errors)
    method = capture.get("method")
    if method not in METHODS:
        errors.append(f"{at}: method {method!r} 須為 {'/'.join(METHODS)}")
    url = capture.get("url")
    if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
        errors.append(f"{at}: url 須為 https:// 開頭的字串")
    if method == "browser_dom" and url is None:
        errors.append(f"{at}: method 為 browser_dom 時須有 url")
    captured_at = capture.get("captured_at")
    if _check_timestamp(at, captured_at, errors) and CAPTURE_ID_RE.match(cid):
        if capture_id(captured_at) != cid:
            errors.append(f"{at}: capture_id 須與 captured_at 取到秒一致（應為 {capture_id(captured_at)}）")
    unit = capture.get("display_unit")
    if "display_unit" in capture and unit not in DISPLAY_UNITS:
        errors.append(f"{at}: display_unit {unit!r} 須為 {'/'.join(DISPLAY_UNITS)}")
        unit = None
    if "files" in capture:
        if method == "manual":
            errors.append(f"{at}: method 為 {method} 時不得有 files")
        else:
            _check_files(folder, source, cid, at, capture["files"], evidence, errors)
    elif method == "browser_dom":
        errors.append(f"{at}: method 為 browser_dom 時須有 files（png、html、txt）")
    return unit


def _check_files(
    folder: Path, source: str, cid: str, at: str, files, evidence: _Evidence, errors: list[str]
) -> None:
    where = f"{at}.files"
    if not isinstance(files, dict):
        errors.append(f"{where}: 須為物件")
        return
    _unknown_keys(where, files, set(CAPTURE_FILES), errors)
    for kind in CAPTURE_FILES:
        entry = files.get(kind)
        if entry is None:
            errors.append(f"{where}: 缺少 {kind}")
            continue
        here = f"{where}.{kind}"
        if not isinstance(entry, dict):
            errors.append(f"{here}: 須為 {{path, sha256}} 物件")
            continue
        _unknown_keys(here, entry, {"path", "sha256"}, errors)
        expected = capture_file_path(source, cid, kind)
        if entry.get("path") != expected:
            errors.append(f"{here}: path 須為 {expected}，實際為 {entry.get('path')!r}")
            continue
        evidence.files.add(expected)
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not SHA256_RE.match(sha):
            errors.append(f"{here}: sha256 須為 64 位小寫十六進位")
            continue
        file = folder / expected
        if not file.is_file():
            errors.append(f"{here}: 找不到 {file}")
            continue
        try:
            actual = hashlib.sha256(file.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"{here}: 無法讀取 {file}（{exc.strerror or exc}）")
            continue
        if actual != sha:
            errors.append(f"{here}: sha256 不符，記錄 {sha}，檔案實際 {actual}")


def _check_capture_tree(folder: Path, evidence: _Evidence, errors: list[str]) -> None:
    """`captures/<source>/<capture_id>/table.*` 的白名單，以及未被 reference.json 引用的項目。"""
    root = folder / CAPTURES_DIR
    if not root.exists():
        return
    if not root.is_dir():
        errors.append(f"{root}: 須為目錄")
        return
    allowed_files = set(CAPTURE_FILES.values())
    for source_dir in _visible(root):
        if not source_dir.is_dir() or source_dir.name not in SOURCES:
            errors.append(f"{source_dir}: captures/ 下只能有來源目錄（{'/'.join(SOURCES)}）")
            continue
        for capture_dir in _visible(source_dir):
            if not capture_dir.is_dir() or not CAPTURE_ID_RE.match(capture_dir.name):
                errors.append(f"{capture_dir}: 來源目錄下只能有 capture_id（YYYYMMDDTHHMMSSZ）目錄")
                continue
            if (source_dir.name, capture_dir.name) not in evidence.captures:
                errors.append(f"{capture_dir}: 擷取目錄未被 reference.json 引用")
                continue
            for file in _visible(capture_dir):
                if not file.is_file() or file.name not in allowed_files:
                    errors.append(f"{file}: 擷取目錄只能放 {'、'.join(sorted(allowed_files))}")
                    continue
                relative = f"{CAPTURES_DIR}/{source_dir.name}/{capture_dir.name}/{file.name}"
                if relative not in evidence.files:
                    errors.append(f"{file}: 證據檔未被 reference.json 引用")


def _visible(folder: Path) -> list[Path]:
    """目錄內容，略過 `.` 開頭的項目（例如 `.gitkeep`、`.DS_Store`）。"""
    try:
        return sorted(p for p in folder.iterdir() if not p.name.startswith("."))
    except OSError:
        return []


def _check_period(at: str, period: dict, unit: str | None, errors: list[str]) -> None:
    _unknown_keys(at, period, {"label", "period_end", "kind", "capture", "values"}, errors)
    label = period.get("label")
    if not isinstance(label, str) or not label.strip(" "):
        errors.append(f"{at}: label 須為非空字串")
    if "period_end" in period:
        end = period["period_end"]
        if not isinstance(end, str) or not _valid_date(end):
            errors.append(f"{at}: period_end {end!r} 須為 YYYY-MM-DD")
    kind = period.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        errors.append(f"{at}: kind {kind!r} 須為 {'/'.join(KINDS)}")
    values = period.get("values")
    if not isinstance(values, dict) or not values:
        errors.append(f"{at}: values 須為非空物件")
        return
    for category, value in values.items():
        _check_value(f"{at}.values[{category!r}]", category, value, unit, errors)


def _check_value(at: str, category: str, value, unit: str | None, errors: list[str]) -> None:
    if not category.strip(" "):
        errors.append(f"{at}: 分類名稱不可空白")
    if not isinstance(value, dict):
        errors.append(f"{at}: 須為 {{display, usd}} 物件")
        return
    _unknown_keys(at, value, {"display", "usd"}, errors)
    display, usd = value.get("display"), value.get("usd")
    if not isinstance(display, str) or not display.strip(" "):
        errors.append(f"{at}: display 須為非空字串；空值不寫入")
        return
    if type(usd) is not int:
        errors.append(f"{at}: usd 須為整數，實際為 {usd!r}")
        return
    try:
        parsed = parse_display(display, unit)
    except ValueError as exc:
        errors.append(f"{at}: {exc}")
        return
    diff = abs(Decimal(usd) - parsed.usd)
    if diff > parsed.tolerance:
        errors.append(
            f"{at}: usd {usd} 與 display {display!r} 換算超出誤差"
            f"（差 {diff:f}，容許 ±{parsed.tolerance:f}）"
        )


def _check_timestamp(where: str, value, errors: list[str]) -> bool:
    if isinstance(value, str) and _valid_timestamp(value):
        return True
    errors.append(
        f"{where}: captured_at {value!r} 須為 UTC 的 ISO 8601 時間"
        "（YYYY-MM-DDTHH:MM:SS[.fff]，結尾 Z 或 +00:00）"
    )
    return False


def _unknown_keys(where: str, data: dict, allowed: set[str], errors: list[str]) -> None:
    for key in sorted(set(data) - allowed):
        errors.append(f"{where}: 未定義的欄位 {key!r}")


def _valid_date(text: str) -> bool:
    if not DATE_RE.match(text):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _valid_timestamp(text: str) -> bool:
    if not TIMESTAMP_RE.match(text):
        return False
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.utcoffset() == dt.timedelta(0)


# ------------------------------------------------------------------ 整體驗證


def validate_universe(universe_dir: Path = DEFAULT_UNIVERSE_DIR) -> list[str]:
    """驗證 `tickers.csv` 與 `references/` 下所有對照目錄，回傳全部錯誤。

    對照目錄不需要列在 `tickers.csv`：對照資料可先於 parser 大量擷取。
    """
    universe_dir = Path(universe_dir)
    errors: list[str] = []
    csv_path = universe_dir / TICKERS_FILE
    parsed = _parse_tickers(csv_path, errors)
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
    for letter in _visible(references):
        if not letter.is_dir():
            errors.append(f"{letter}: references/ 下只能有首字母目錄")
            continue
        if not LETTER_RE.match(letter.name):
            errors.append(f"{letter}: 首字母目錄須為單一大寫字母")
            continue
        for folder in _visible(letter):
            if not folder.is_dir():
                errors.append(f"{folder}: 首字母目錄下只能有 ticker 目錄")
                continue
            ticker = folder.name
            if not TICKER_RE.match(ticker):
                errors.append(f"{folder}: 目錄名稱 {ticker!r} 不符合 ticker 格式")
                continue
            if ticker[0] != letter.name:
                errors.append(f"{folder}: {ticker} 應位於 {reference_dir(ticker, universe_dir)}")
            for extra in _visible(folder):
                if extra.name not in (REFERENCE_FILE, CAPTURES_DIR):
                    errors.append(f"{extra}: ticker 目錄只能放 {REFERENCE_FILE} 與 {CAPTURES_DIR}/")
            reference = folder / REFERENCE_FILE
            if not reference.exists():
                errors.append(f"{folder}: 缺少 {REFERENCE_FILE}")
                continue
            data = _check_reference(reference, ticker, errors)
            if isinstance(data, dict) and isinstance(data.get("sources"), dict):
                sources_by_ticker[ticker] = set(data["sources"])
