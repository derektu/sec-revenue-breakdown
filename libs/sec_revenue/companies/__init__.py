"""公司目錄：`<首字母>/<ticker 小寫，非英數字元改為底線>/`。

公司 parser（`parser.py`，定義 `TICKER`、`VIEW`、`TOTAL`、`compose`、`categories`）或宣告式規格（`spec.py`，定義
`SPEC`）；有 `parser.py` 時用 parser。每家公司都要有 `parser.md`。
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

from ..revenue.source import ParserSource
from ..revenue.spec import SEGMENT_AXIS, CompanySpec

ROOT = Path(__file__).resolve().parent


def module_dir(ticker: str) -> Path:
    name = "".join(c if c.isalnum() else "_" for c in ticker.lower())
    return ROOT / ticker[0].lower() / name


def directories() -> list[Path]:
    return sorted({p.parent for pattern in ("*/*/parser.py", "*/*/spec.py") for p in ROOT.glob(pattern)})


def tickers() -> list[str]:
    """有公司 parser 或規格的 ticker，以各自宣告的 ticker 為準。"""
    return sorted(load(directory.name, directory).ticker for directory in directories())


def load(name: str, directory: Path) -> ParserSource | CompanySpec:
    if (directory / "parser.py").exists():
        return ParserSource(importlib.import_module(f"{__name__}.{directory.parent.name}.{name}.parser"))
    module = importlib.import_module(f"{__name__}.{directory.parent.name}.{name}.spec")
    return module.SPEC


def spec(ticker: str) -> tuple[ParserSource | CompanySpec, str]:
    """回傳公司 parser（或規格）與該檔（parser.py 或 spec.py）的 sha256。"""
    directory = module_dir(ticker)
    source = next((directory / name for name in ("parser.py", "spec.py") if (directory / name).exists()), None)
    if source is None:
        raise ValueError(f"{ticker} 沒有公司 parser（{directory / 'parser.py'}）")
    loaded = load(directory.name, directory)
    if loaded.ticker != ticker:
        raise ValueError(f"{source} 宣告的 ticker 是 {loaded.ticker}，不是 {ticker}")
    notes = directory / "parser.md"
    if not notes.exists():
        raise ValueError(f"{ticker} 缺少 {notes}；每家公司都要有 parser.md")
    uses_segment_axis = loaded.uses_axis(SEGMENT_AXIS) if isinstance(loaded, CompanySpec) else SEGMENT_AXIS in source.read_text()
    check_notes(ticker, uses_segment_axis, notes.read_text())
    digest = hashlib.sha256(source.name.encode() + source.read_bytes())
    if source.name == "parser.py":
        # 公司 parser 的結果也取決於它呼叫的 utility。
        for path in sorted((ROOT.parent / "parser_utils").glob("*.py")):
            digest.update(path.name.encode() + path.read_bytes())
    return loaded, digest.hexdigest()


def check_notes(ticker: str, uses_segment_axis: bool, notes: str):
    """使用業務分部軸時，parser.md 必須提到這個軸並說明成員是業務別而不是地區。"""
    if uses_segment_axis and SEGMENT_AXIS not in notes:
        raise ValueError(
            f"{ticker} 使用 {SEGMENT_AXIS}；parser.md 必須寫明這個軸的成員是業務別而不是地區（並提到 {SEGMENT_AXIS}）"
        )
