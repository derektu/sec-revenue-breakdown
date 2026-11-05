"""把一次擷取累積合併進 `reference.json`，並寫入證據檔。

合併規則（`docs/architecture/universe.md`「保存模型」）：

- 新擷取涵蓋的期別以新值取代，`capture` 指向新擷取；未涵蓋的期別保留原值與原擷取。
  同一來源內 `label` 相同，或 `(kind, period_end)` 相同，即視為同一期。
- 不再被任何期別引用的擷取，連同證據目錄一併刪除。

寫入先在 ticker 目錄旁的暫存目錄（`.` 開頭，驗證程式不檢查）完成並通過 `validate_reference()`，
再整個換上；驗證失敗時原目錄不變。
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from decimal import ROUND_HALF_UP
from pathlib import Path

from ..universe import (
    CAPTURES_DIR,
    REFERENCE_FILE,
    SCHEMA_VERSION,
    capture_id,
    parse_display,
    reference_dir,
    validate_reference,
)
from .evidence import write_evidence
from .model import CaptureError, Period


@dataclass(frozen=True)
class CommitResult:
    capture: str
    periods: int
    removed_captures: list[str]
    reference_path: Path


def display_usd(display: str, display_unit: str | None) -> int:
    """display 換算成美元整數（四捨五入）。"""
    return int(parse_display(display, display_unit).usd.to_integral_value(rounding=ROUND_HALF_UP))


def period_entry(period: Period, capture: str, display_unit: str | None) -> dict:
    entry: dict = {"label": period.label}
    if period.period_end is not None:
        entry["period_end"] = period.period_end
    entry["kind"] = period.kind
    entry["capture"] = capture
    entry["values"] = {
        name: {"display": display, "usd": display_usd(display, display_unit)}
        for name, display in period.values.items()
    }
    return entry


def merge_reference(
    reference: dict | None,
    ticker: str,
    source: str,
    capture: str,
    capture_meta: dict,
    periods: list[Period],
) -> tuple[dict, list[str]]:
    """回傳合併後的 reference 與被移除的 capture_id；不修改傳入的 reference。"""
    if not periods:
        raise CaptureError("擷取沒有任何期別")
    merged = copy.deepcopy(reference) if reference else {
        "schema_version": SCHEMA_VERSION, "ticker": ticker, "sources": {}
    }
    body = merged["sources"].setdefault(source, {"captures": {}, "periods": []})
    if capture in body["captures"]:
        raise CaptureError(f"{source} 已有擷取 {capture}；同一來源同一秒只能擷取一次")
    unit = capture_meta.get("display_unit")
    fresh = [period_entry(p, capture, unit) for p in periods]
    labels = {p["label"] for p in fresh}
    ends = {(p["kind"], p["period_end"]) for p in fresh if "period_end" in p}
    kept = [
        p for p in body["periods"]
        if p["label"] not in labels and (p["kind"], p.get("period_end")) not in ends
    ]
    body["periods"] = _ordered(fresh + kept)
    body["captures"][capture] = capture_meta
    used = {p["capture"] for p in body["periods"]}
    removed = sorted(cid for cid in body["captures"] if cid not in used)
    for cid in removed:
        del body["captures"][cid]
    body["captures"] = dict(sorted(body["captures"].items()))
    return merged, removed


def _ordered(periods: list[dict]) -> list[dict]:
    """有期末日的期別依期末日新到舊（同日 FY 在 Q 前）；沒有期末日的依原順序排在後面。"""
    dated = [p for p in periods if "period_end" in p]
    undated = [p for p in periods if "period_end" not in p]
    dated.sort(key=lambda p: (p["period_end"], p["kind"] == "FY"), reverse=True)
    return dated + undated


def commit_capture(
    universe_dir: Path,
    ticker: str,
    source: str,
    *,
    url: str,
    captured_at: str,
    periods: list[Period],
    display_unit: str | None,
    png: bytes,
    html_text: str,
    txt: str,
) -> CommitResult:
    """寫入一次 `browser_dom` 擷取：證據檔、合併後的 reference.json、刪除未引用的擷取。"""
    target = reference_dir(ticker, universe_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    cid = capture_id(captured_at)
    staging = Path(tempfile.mkdtemp(prefix=f".capture-{ticker}-", dir=target.parent))
    try:
        reference = None
        if target.exists():
            shutil.copytree(target, staging, dirs_exist_ok=True)
            reference = json.loads((staging / REFERENCE_FILE).read_text(encoding="utf-8"))
        meta: dict = {"url": url, "captured_at": captured_at, "method": "browser_dom"}
        if display_unit is not None:
            meta["display_unit"] = display_unit
        merged, removed = merge_reference(reference, ticker, source, cid, meta, periods)
        meta["files"] = write_evidence(staging, source, cid, png, html_text, txt)
        for old in removed:
            shutil.rmtree(staging / CAPTURES_DIR / source / old, ignore_errors=True)
        text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
        (staging / REFERENCE_FILE).write_text(text, encoding="utf-8")
        errors = validate_reference(staging / REFERENCE_FILE, ticker)
        if errors:
            raise CaptureError("合併結果未通過驗證：\n" + "\n".join(errors))
        _swap(staging, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return CommitResult(cid, len(periods), removed, target / REFERENCE_FILE)


def _swap(staging: Path, target: Path) -> None:
    if not target.exists():
        os.rename(staging, target)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".capture-old-{target.name}-", dir=target.parent))
    backup.rmdir()
    os.rename(target, backup)
    try:
        os.rename(staging, target)
    except OSError:
        os.rename(backup, target)
        raise
    shutil.rmtree(backup, ignore_errors=True)
