"""下載快取：以 sha256 命名保存 SEC 原始檔與收據，以及 `pipeline/<TICKER>/` 下的索引。"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
import re

from ..common.jsonio import JsonCodec


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SecFileStore:
    """以 sha256 命名保存 SEC 原始檔（HTML 與 JSON），收據與檔案同目錄；同名而內容不同時拒絕寫入。"""

    def __init__(self, root: Path):
        self.root = root

    def capture(
        self,
        ticker: str,
        period: str,
        accession: str,
        body: bytes,
        kind: str,
        metadata: dict,
    ) -> dict:
        digest = hashlib.sha256(body).hexdigest()
        directory = self.root / ticker / period / accession
        path = directory / (
            digest
            + "."
            + {
                "original_html": "html",
                "sec_json": "json",
            }[kind]
        )
        directory.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != body:
            raise ValueError("Evidence collision")
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(body)
        receipt = dict(
            metadata, path=str(path), sha256=digest, source_format=kind, bytes=len(body)
        )
        # 收據與原文同目錄，只記檔名，資料目錄整個搬移後仍正確。
        JsonCodec.write(
            path.with_suffix(path.suffix + ".receipt.json"), dict(receipt, path=path.name)
        )
        return receipt


class WorkflowCache:
    """資料根目錄下的下載快取：`sec/` 保存 SEC 原始檔，`pipeline/<TICKER>/<name>.json` 保存索引。"""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.store = SecFileStore(self.root / "sec")

    def path(self, ticker: str, name: str) -> Path:
        return self.root / "pipeline" / ticker / (name + ".json")

    def read(self, ticker: str, name: str, default=None):
        path = self.path(ticker, name)
        return JsonCodec.read(path) if path.exists() else default

    def write(self, ticker: str, name: str, value: object):
        JsonCodec.write(self.path(ticker, name), value)

    def capture(
        self, ticker: str, period: str, accession: str, raw: bytes, kind: str, url: str
    ) -> dict:
        receipt = self.store.capture(
            ticker, period, accession, raw, kind, {"source_url": url}
        )
        receipt["path"] = str(Path(receipt["path"]).relative_to(self.root))
        return receipt

    def body(self, receipt: dict) -> bytes:
        path = (self.root / receipt["path"]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("快取路徑超出 data 目錄")
        raw = path.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != receipt["sha256"]
            or len(raw) != receipt["bytes"]
        ):
            raise ValueError("SEC cache hash／bytes 不符：" + receipt["path"])
        return raw

    def index_catalog(self, ticker: str, filings: list[dict], receipts: list[dict]):
        self.write(
            ticker,
            "catalog",
            {
                "filings": filings,
                "receipts": receipts,
                "filings_sha256": hashlib.sha256(JsonCodec.encode(filings)).hexdigest(),
                "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        )


class RawFileStore:
    """依原副檔名保存 SEC 檔案；HTML 與 JSON 走 SecFileStore，與既有快取同路徑去重。"""

    def __init__(self, cache: WorkflowCache):
        self.cache = cache

    def capture(
        self, ticker: str, period: str, accession: str, raw: bytes, name: str, metadata: dict
    ) -> dict:
        suffix = Path(name).suffix.lower().lstrip(".")
        if suffix in ("htm", "html"):
            kind = "original_html"
        elif suffix == "json":
            kind = "sec_json"
        else:
            return self.write(Path("sec") / ticker / period / accession, raw, suffix, metadata)
        receipt = self.cache.store.capture(ticker, period, accession, raw, kind, metadata)
        receipt["path"] = str(Path(receipt["path"]).relative_to(self.cache.root))
        return receipt

    def write(self, directory: Path, raw: bytes, suffix: str, metadata: dict) -> dict:
        if not re.fullmatch(r"[a-z0-9]{1,8}", suffix):
            suffix = "bin"
        digest = hashlib.sha256(raw).hexdigest()
        relative = directory / f"{digest}.{suffix}"
        path = self.cache.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Evidence collision")
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(raw)
        receipt = dict(
            metadata, path=str(relative), sha256=digest, source_format="sec_file", bytes=len(raw)
        )
        JsonCodec.write(
            path.with_suffix(path.suffix + ".receipt.json"), dict(receipt, path=path.name)
        )
        return receipt
