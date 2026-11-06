"""對照資料（`references/<首字母>/<TICKER>/reference.json` 與擷取證據檔）的讀取與驗證。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .model import (
    CAPTURES_DIR,
    CAPTURE_FILES,
    CAPTURE_ID_RE,
    DEFAULT_UNIVERSE_DIR,
    DISPLAY_UNITS,
    KINDS,
    METHODS,
    REFERENCE_FILE,
    SCHEMA_VERSION,
    SHA256_RE,
    SOURCES,
    TICKER_RE,
    UniverseError,
    capture_file_path,
    capture_id,
    parse_display,
    reference_dir,
    valid_date,
    valid_timestamp,
)


def validate_reference(path: Path, expected_ticker: str | None = None) -> list[str]:
    """驗證單一 `reference.json` 與同目錄的 `captures/`；`expected_ticker` 為目錄推得的 ticker。"""
    errors: list[str] = []
    check_reference(Path(path), expected_ticker, errors)
    return errors


def load_reference(ticker: str, universe_dir: Path = DEFAULT_UNIVERSE_DIR) -> dict:
    path = reference_dir(ticker, universe_dir) / REFERENCE_FILE
    errors: list[str] = []
    data = check_reference(path, ticker, errors)
    if errors:
        raise UniverseError(errors)
    return data


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


def check_reference(path: Path, expected_ticker: str | None, errors: list[str]) -> dict | None:
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
    for source_dir in visible_entries(root):
        if not source_dir.is_dir() or source_dir.name not in SOURCES:
            errors.append(f"{source_dir}: captures/ 下只能有來源目錄（{'/'.join(SOURCES)}）")
            continue
        for capture_dir in visible_entries(source_dir):
            if not capture_dir.is_dir() or not CAPTURE_ID_RE.match(capture_dir.name):
                errors.append(f"{capture_dir}: 來源目錄下只能有 capture_id（YYYYMMDDTHHMMSSZ）目錄")
                continue
            if (source_dir.name, capture_dir.name) not in evidence.captures:
                errors.append(f"{capture_dir}: 擷取目錄未被 reference.json 引用")
                continue
            for file in visible_entries(capture_dir):
                if not file.is_file() or file.name not in allowed_files:
                    errors.append(f"{file}: 擷取目錄只能放 {'、'.join(sorted(allowed_files))}")
                    continue
                relative = f"{CAPTURES_DIR}/{source_dir.name}/{capture_dir.name}/{file.name}"
                if relative not in evidence.files:
                    errors.append(f"{file}: 證據檔未被 reference.json 引用")


def visible_entries(folder: Path) -> list[Path]:
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
        if not isinstance(end, str) or not valid_date(end):
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
    if isinstance(value, str) and valid_timestamp(value):
        return True
    errors.append(
        f"{where}: captured_at {value!r} 須為 UTC 的 ISO 8601 時間"
        "（YYYY-MM-DDTHH:MM:SS[.fff]，結尾 Z 或 +00:00）"
    )
    return False


def _unknown_keys(where: str, data: dict, allowed: set[str], errors: list[str]) -> None:
    for key in sorted(set(data) - allowed):
        errors.append(f"{where}: 未定義的欄位 {key!r}")
