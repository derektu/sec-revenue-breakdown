"""XBRL fact 快照與申報清單：沒有 SEC 原文時，以快照重跑 parse 的 `--check`。

快照（`data/snapshots/<首字母>/<TICKER>/<accession>.json`）是 FilingSet 讀到的每份申報的解析結果：申報篩選用到的
申報包欄位（申報資訊、是否完整、主文件與其 sha256、URL）、namespaces、dei，以及規格用到的 concept 的全部 fact
（不分 dimensions）。快照由原文產生，記錄產生時的規格 concept 集合與解析器 hash；快照模式先檢查這兩項，規格多了
快照沒有的 concept、或決定快照內容的程式（`PARSER_FILES`）改過時直接報錯，不以不完整的快照計算。

申報清單（同目錄的 `manifest.json`）列出正式輸出依賴的每份 10-K／10-Q（引擎不讀 8-K，所以不在清單內）的申報資訊，
與申報包內每個檔案的 sha256、bytes；download 可依清單重新下載並逐檔核對。

快照模式走與原文相同的程式路徑：`SnapshotFilingSet` 以同一個 `periodic_filing` 篩選申報，文件由
`InlineDocument.from_snapshot` 重建。沒有原文，所以 `raw()` 不可用，證據沿用已提交的表格檔（見 `engine.py`）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..common.jsonio import JsonCodec
from .filings import Filing, FilingSet, ParseError, package_record, periodic_filing
from .spec import CompanySpec, fact_variants
from .xbrl import InlineDocument

SNAPSHOT_FORMAT = 1
PACKAGE = Path(__file__).resolve().parent
# 決定快照內容的程式：fact 解析、HTML 解析與表格編號、數值規則、申報篩選，以及快照本身的產生與讀取。
PARSER_FILES = ("xbrl.py", "ixbrl.py", "filings.py", "snapshot.py")
MANIFEST = "manifest.json"


def parser_sha256() -> str:
    digest = hashlib.sha256()
    for name in PARSER_FILES:
        digest.update(name.encode() + hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def snapshot_dir(root: Path, ticker: str) -> Path:
    return Path(root) / ticker[0].upper() / ticker


def spec_concepts(spec: CompanySpec) -> list[str]:
    """規格中所有定義（含 one_of 的每種寫法、調節項與總營收）用到的 concept。"""
    items = list(spec.categories) + list(spec.reconciling) + [spec.total]
    return sorted({v.concept for item in items for d in item.definitions for a in d.addends for v in fact_variants(a.selector)})


def build(data: Path, spec: CompanySpec) -> tuple[dict[str, dict], dict]:
    """由原文產生（accession → 快照, 申報清單）；原文讀不到的申報記成錯誤，快照模式照樣重現。"""
    filings = FilingSet(data, spec.ticker)
    concepts = spec_concepts(spec)
    parser = parser_sha256()
    packages = JsonCodec.read(filings.root / "pipeline" / spec.ticker / "packages.json")["packages"]
    snapshots, listed = {}, []
    for filing in filings.filings:
        payload = {
            "format": SNAPSHOT_FORMAT,
            "parser_sha256": parser,
            "spec_concepts": concepts,
            "accession": filing.accession,
            "package": package_record(packages[filing.accession]),
        }
        try:
            payload.update(filings.document(filing).to_snapshot(concepts))
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
    return snapshots, {"ticker": spec.ticker, "filings": listed}


def write(data: Path, root: Path, spec: CompanySpec) -> dict:
    """產生該公司的快照與申報清單；不再屬於 FilingSet 的舊快照刪除。"""
    snapshots, manifest = build(data, spec)
    directory = snapshot_dir(root, spec.ticker)
    directory.mkdir(parents=True, exist_ok=True)
    for accession, payload in snapshots.items():
        JsonCodec.write(directory / f"{accession}.json", payload)
    for stale in directory.glob("*.json"):
        if stale.name != MANIFEST and stale.stem not in snapshots:
            stale.unlink()
    JsonCodec.write(directory / MANIFEST, manifest)
    return {"ticker": spec.ticker, "snapshots": len(snapshots), "errors": sorted(a for a, p in snapshots.items() if "error" in p)}


def check(data: Path, root: Path, spec: CompanySpec) -> list[str]:
    """已提交的快照與申報清單是否與原文重新產生的結果完全相同；回傳不同之處。"""
    snapshots, manifest = build(data, spec)
    directory = snapshot_dir(root, spec.ticker)
    expected = {f"{a}.json": JsonCodec.encode(p) for a, p in snapshots.items()} | {MANIFEST: JsonCodec.encode(manifest)}
    found = {p.name: p.read_bytes() for p in directory.glob("*.json")} if directory.exists() else {}
    differences = [f"{spec.ticker} {name}：缺少" for name in sorted(set(expected) - set(found))]
    differences += [f"{spec.ticker} {name}：多出" for name in sorted(set(found) - set(expected))]
    differences += [f"{spec.ticker} {name}：內容不同" for name in sorted(set(expected) & set(found)) if expected[name] != found[name]]
    return differences


class SnapshotFilingSet(FilingSet):
    """由快照建立的 FilingSet：申報、選申報、期別與原文模式相同，文件由快照重建。

    建立時檢查快照與申報清單一致、解析器 hash 相同、規格的 concept 都在快照內；不符時丟出 ValueError，
    指出要重產的公司與原因。
    """

    snapshot = True

    def __init__(self, root: Path, spec: CompanySpec):
        directory = snapshot_dir(root, spec.ticker)
        manifest_path = directory / MANIFEST
        if not manifest_path.exists():
            raise ValueError(f"{spec.ticker} 沒有快照（{manifest_path}）；請在有原文的環境執行 snapshot --tickers {spec.ticker}")
        manifest = JsonCodec.read(manifest_path)
        accessions = [f["filing"]["accessionNumber"] for f in manifest["filings"]]
        self.payloads = {}
        problems = []
        for accession in accessions:
            path = directory / f"{accession}.json"
            if not path.exists():
                problems.append(f"申報清單列出的 {accession} 沒有快照")
                continue
            self.payloads[accession] = JsonCodec.read(path)
        extra = sorted(p.stem for p in directory.glob("*.json") if p.name != MANIFEST and p.stem not in accessions)
        if extra:
            problems.append(f"快照 {'、'.join(extra)} 不在申報清單中")
        for entry in manifest["filings"]:
            accession = entry["filing"]["accessionNumber"]
            payload = self.payloads.get(accession)
            if payload is None:
                continue
            listed = payload.get("package", {}).get("filing", {})
            if payload.get("accession") != accession:
                problems.append(f"快照檔 {accession}.json 記錄的 accession 是 {payload.get('accession')}")
            elif any(listed.get(k) != entry["filing"].get(k) for k in ("form", "reportDate", "filingDate")):
                problems.append(f"{accession} 的申報資訊與申報清單不同")
        current = parser_sha256()
        stale = sorted(a for a, p in self.payloads.items() if p.get("format") != SNAPSHOT_FORMAT or p.get("parser_sha256") != current)
        if stale:
            problems.append(f"{len(stale)} 份快照由不同版本的解析器產生（例如 {stale[0]}）")
        needed = set(spec_concepts(spec))
        missing = {}
        for accession, payload in self.payloads.items():
            for concept in sorted(needed - set(payload.get("spec_concepts", []))):
                missing.setdefault(concept, []).append(accession)
        for concept, listed in sorted(missing.items()):
            problems.append(f"規格的 {concept} 不在 {len(listed)} 份快照的範圍內（例如 {listed[0]}）")
        if problems:
            raise ValueError(f"{spec.ticker} 的快照需要重產：{'；'.join(problems)}；請在有原文的環境執行 snapshot --tickers {spec.ticker}")
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
