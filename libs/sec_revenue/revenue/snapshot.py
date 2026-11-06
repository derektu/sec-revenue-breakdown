"""XBRL fact 快照與申報清單：沒有 SEC 原文時，以快照重跑 parse 的 `--check`。

快照（`data/snapshots/<首字母>/<TICKER>/<accession>.jsonl`）只保存一定要有原文才拿得到的資料，也就是 `extract.py`
從每份申報抽出的內容，與公司 parser 無關。JSON Lines 格式：第一行是表頭（格式版本、抽取程式 hash、accession、
申報篩選用到的申報包欄位、namespaces、衝突的前綴、dei；原文讀不到時是錯誤原因），之後一行一個主文件的數值 fact
（`ix:nonFraction`）的原始欄位與 HTML 位置，依文件順序。數值、QName 解析、期間分類與申報篩選由讀快照時的程式
重算，不存在快照中。

一份申報公開後內容不會變，所以快照只由申報與抽取程式的行為決定。抽取程式 hash（`extract_sha256`）依
`extract.py` 的語法樹計算，不含註解、docstring 與排版；快照模式先檢查 hash，不同時直接報錯，不以過期的快照計算。
快照檔的編排（`encode`）改變時，`SNAPSHOT_FORMAT` 隨之改變。

申報清單（同目錄的 `manifest.json`）列出正式輸出依賴的每份 10-K／10-Q（框架不讀 8-K，所以不在清單內）的申報資訊，
與申報包內每個檔案的 sha256、bytes；download 可依清單重新下載並逐檔核對。

快照模式走與原文相同的程式路徑：`SnapshotFilingSet` 以同一個 `periodic_filing` 篩選申報，文件由
`InlineDocument.from_snapshot` 以與原文相同的 `InlineDocument.load` 重建。沒有原文，所以 `raw()` 不可用，證據沿用
已提交的表格檔（見 `engine.py`）。
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from ..common.jsonio import JsonCodec
from . import extract
from .filings import Filing, FilingSet, ParseError, periodic_filing
from .xbrl import InlineDocument

SNAPSHOT_FORMAT = 3
MANIFEST = "manifest.json"
SUFFIX = ".jsonl"
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def source_sha256(source: str) -> str:
    """原始碼語法樹的 sha256：去掉 docstring 後以 `ast.unparse` 正規化，註解與排版不影響結果。"""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, DOCSTRING_OWNERS) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return hashlib.sha256(ast.unparse(tree).encode()).hexdigest()


def extract_sha256() -> str:
    """決定快照內容的抽取程式（`extract.py`）的 hash。"""
    return source_sha256(Path(extract.__file__).read_text(encoding="utf-8"))


def snapshot_dir(root: Path, ticker: str) -> Path:
    return Path(root) / ticker[0].upper() / ticker


def encode(payload: dict) -> bytes:
    """快照的 JSON Lines：表頭一行，之後一行一個 fact。"""
    header = {k: v for k, v in payload.items() if k != "facts"}
    rows = [header] + list(payload.get("facts", []))
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode()


def decode(data: bytes) -> dict:
    """`encode` 的反向：表頭的欄位加上 `facts`（原文讀不到的申報沒有 fact）。"""
    # 只以 \n 分行：JSON 字串中的其他 Unicode 換行字元（例如 U+2028）不是行界。
    lines = [line for line in data.decode().split("\n") if line]
    if not lines:
        raise ValueError("快照是空檔")
    payload = json.loads(lines[0])
    if "error" in payload:
        if len(lines) > 1:
            raise ValueError("記錄錯誤的快照只有表頭一行")
    else:
        payload["facts"] = [json.loads(line) for line in lines[1:]]
    return payload


def snapshot_files(directory: Path) -> list[Path]:
    """目錄中申報清單以外的快照檔，包括格式不對的 `.json`。"""
    if not directory.exists():
        return []
    return sorted(p for p in directory.iterdir() if p.name != MANIFEST and p.suffix in (SUFFIX, ".json"))


def build(data: Path, ticker: str) -> tuple[dict[str, dict], dict]:
    """由原文產生（accession → 快照, 申報清單）；原文讀不到的申報記成錯誤，快照模式照樣重現。"""
    filings = FilingSet(data, ticker)
    extractor = extract_sha256()
    packages = JsonCodec.read(filings.root / "pipeline" / ticker / "packages.json")["packages"]
    snapshots, listed = {}, []
    for filing in filings.filings:
        payload = {
            "format": SNAPSHOT_FORMAT,
            "extract_sha256": extractor,
            "accession": filing.accession,
            "package": extract.package_record(packages[filing.accession]),
        }
        try:
            payload.update(extract.extract(extract.parse_html(filings.raw(filing))))
        except ParseError as error:
            payload["error"] = {"check": error.check, "message": error.message}
        snapshots[filing.accession] = payload
        package = packages[filing.accession]
        listed.append(
            {
                "filing": package["filing"],
                "documents": {
                    name: {"sha256": d["sha256"], "bytes": d.get("bytes")} for name, d in sorted(package["documents"].items())
                },
            }
        )
    return snapshots, {"ticker": ticker, "filings": listed}


def write(data: Path, root: Path, ticker: str) -> dict:
    """產生該公司的快照與申報清單；不屬於 FilingSet 的快照檔刪除。"""
    snapshots, manifest = build(data, ticker)
    directory = snapshot_dir(root, ticker)
    directory.mkdir(parents=True, exist_ok=True)
    for accession, payload in snapshots.items():
        JsonCodec.write_bytes(directory / f"{accession}{SUFFIX}", encode(payload))
    for stale in snapshot_files(directory):
        if stale.suffix != SUFFIX or stale.stem not in snapshots:
            stale.unlink()
    JsonCodec.write(directory / MANIFEST, manifest)
    return {"ticker": ticker, "snapshots": len(snapshots), "errors": sorted(a for a, p in snapshots.items() if "error" in p)}


def check(data: Path, root: Path, ticker: str) -> list[str]:
    """已提交的快照與申報清單是否與原文重新產生的結果完全相同；回傳不同之處。"""
    snapshots, manifest = build(data, ticker)
    directory = snapshot_dir(root, ticker)
    expected = {f"{a}{SUFFIX}": encode(p) for a, p in snapshots.items()} | {MANIFEST: JsonCodec.encode(manifest)}
    found = {p.name: p.read_bytes() for p in snapshot_files(directory)}
    if (directory / MANIFEST).exists():
        found[MANIFEST] = (directory / MANIFEST).read_bytes()
    differences = [f"{ticker} {name}：缺少" for name in sorted(set(expected) - set(found))]
    differences += [f"{ticker} {name}：多出" for name in sorted(set(found) - set(expected))]
    differences += [f"{ticker} {name}：內容不同" for name in sorted(set(expected) & set(found)) if expected[name] != found[name]]
    return differences


class SnapshotFilingSet(FilingSet):
    """由快照建立的 FilingSet：申報、選申報、期別與原文模式相同，文件由快照重建。

    建立時檢查快照與申報清單一致、抽取程式 hash 相同；不符時丟出 ValueError，指出要重產的公司與原因。
    """

    snapshot = True

    def __init__(self, root: Path, ticker: str):
        directory = snapshot_dir(root, ticker)
        manifest_path = directory / MANIFEST
        if not manifest_path.exists():
            raise ValueError(f"{ticker} 沒有快照（{manifest_path}）；請在有原文的環境執行 snapshot --tickers {ticker}")
        manifest = JsonCodec.read(manifest_path)
        accessions = [f["filing"]["accessionNumber"] for f in manifest["filings"]]
        self.payloads = {}
        problems = []
        for accession in accessions:
            path = directory / f"{accession}{SUFFIX}"
            if not path.exists():
                problems.append(f"申報清單列出的 {accession} 沒有快照")
                continue
            try:
                self.payloads[accession] = decode(path.read_bytes())
            except ValueError as error:
                problems.append(f"{path.name} 無法讀取（{error}）")
        extra = [p.name for p in snapshot_files(directory) if p.suffix != SUFFIX or p.stem not in accessions]
        if extra:
            problems.append(f"快照 {'、'.join(extra)} 不在申報清單中")
        for entry in manifest["filings"]:
            accession = entry["filing"]["accessionNumber"]
            payload = self.payloads.get(accession)
            if payload is None:
                continue
            listed = payload.get("package", {}).get("filing", {})
            if payload.get("accession") != accession:
                problems.append(f"快照檔 {accession}{SUFFIX} 記錄的 accession 是 {payload.get('accession')}")
            elif any(listed.get(k) != entry["filing"].get(k) for k in ("form", "reportDate", "filingDate")):
                problems.append(f"{accession} 的申報資訊與申報清單不同")
        current = extract_sha256()
        stale = sorted(a for a, p in self.payloads.items() if p.get("format") != SNAPSHOT_FORMAT or p.get("extract_sha256") != current)
        if stale:
            problems.append(f"{len(stale)} 份快照由不同版本的抽取程式產生（例如 {stale[0]}）")
        if problems:
            raise ValueError(f"{ticker} 的快照需要重產：{'；'.join(problems)}；請在有原文的環境執行 snapshot --tickers {ticker}")
        self.root = None
        # 與原文模式相同的申報篩選；快照保存的是篩選用到的申報包欄位。
        self.filings = sorted(
            (f for accession, p in self.payloads.items() if (f := periodic_filing(accession, p["package"]))),
            key=lambda f: (f.filing_date, f.accession),
        )
        self.documents: dict[str, InlineDocument] = {}

    def raw(self, filing: Filing) -> bytes:
        raise ParseError("原文存在", f"快照模式沒有 {filing.accession} 的原文")

    def document(self, filing: Filing) -> InlineDocument:
        if filing.accession not in self.documents:
            payload = self.payloads[filing.accession]
            if "error" in payload:
                raise ParseError(payload["error"]["check"], payload["error"]["message"])
            self.documents[filing.accession] = InlineDocument.from_snapshot(payload)
        return self.documents[filing.accession]
