"""公司規格：`<首字母>/<ticker 小寫，非英數字元改為底線>/spec.py` 定義 `SPEC`。"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

from ..revenue.spec import SEGMENT_AXIS, CompanySpec

ROOT = Path(__file__).resolve().parent


def module_dir(ticker: str) -> Path:
    name = "".join(c if c.isalnum() else "_" for c in ticker.lower())
    return ROOT / ticker[0].lower() / name


def tickers() -> list[str]:
    """有規格的 ticker，以各規格的 `SPEC.ticker` 為準。"""
    return sorted(load(path.parent.name, path.parent).ticker for path in ROOT.glob("*/*/spec.py"))


def load(name: str, directory: Path) -> CompanySpec:
    module = importlib.import_module(f"{__name__}.{directory.parent.name}.{name}.spec")
    return module.SPEC


def spec(ticker: str) -> tuple[CompanySpec, str]:
    """回傳規格與規格檔（spec.py，以及選用的 hooks.py）的 sha256。"""
    directory = module_dir(ticker)
    if not (directory / "spec.py").exists():
        raise ValueError(f"{ticker} 沒有 parser 規格（{directory / 'spec.py'}）")
    loaded = load(directory.name, directory)
    if loaded.ticker != ticker:
        raise ValueError(f"{directory / 'spec.py'} 的 SPEC.ticker 是 {loaded.ticker}，不是 {ticker}")
    notes = directory / "parser.md"
    if not notes.exists():
        raise ValueError(f"{ticker} 缺少 {notes}；每家公司都要有 parser.md")
    check_notes(loaded, notes.read_text())
    digest = hashlib.sha256()
    for name in ("spec.py", "hooks.py"):
        if (directory / name).exists():
            digest.update(name.encode() + (directory / name).read_bytes())
    return loaded, digest.hexdigest()


def check_notes(spec: CompanySpec, notes: str):
    """規格使用業務分部軸時，parser.md 必須提到這個軸並說明成員是業務別而不是地區。"""
    if spec.uses_axis(SEGMENT_AXIS) and SEGMENT_AXIS not in notes:
        raise ValueError(
            f"{spec.ticker} 規格使用 {SEGMENT_AXIS}；parser.md 必須寫明這個軸的成員是業務別而不是地區（並提到 {SEGMENT_AXIS}）"
        )
