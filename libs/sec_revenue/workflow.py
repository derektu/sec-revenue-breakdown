"""萃取工作流與共用的期間選擇、快取；只讀 local SEC cache，不讀研究答案。

下載在 `download.py`。本檔屬於萃取規則指紋，只放萃取會執行的程式。
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
from pathlib import Path
import re
from typing import Callable

from lxml.etree import LxmlError

from .engines import EvidenceStore, JsonCodec, PrecisionAnalyzer, XbrlEngine
from .service import ParserRegistry, RiskAnalyzer


@dataclass(frozen=True)
class PeriodSelection:
    """範圍以實際 SEC reportDate 為準；沒有範圍時只選最新一期。"""

    start: str | None = None
    end: str | None = None
    latest: bool = False

    def __post_init__(self):
        for value in (self.start, self.end):
            if value is not None:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("日期需使用 YYYY-MM-DD")
                dt.date.fromisoformat(value)
        if self.start and self.end and self.start > self.end:
            raise ValueError("start 不可晚於 end")

    def choose(self, filings: list[dict]) -> list[dict]:
        # 同一期多個 accession 保留所有下載版本，預設採最新申報／修訂。
        periods = {}
        for filing in filings:
            end = filing["reportDate"]
            if (self.start and end < self.start) or (self.end and end > self.end):
                continue
            existing = periods.get(end)
            if existing is None or (filing["filingDate"], filing["accessionNumber"]) > (
                existing["filingDate"],
                existing["accessionNumber"],
            ):
                periods[end] = filing
        selected = [periods[end] for end in sorted(periods)]
        return selected[-1:] if not self.start and not self.end else selected

class WorkflowCache:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.store = EvidenceStore(self.root / "sec")

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

class ExtractionWorkflow:
    """只讀下載 cache；不發網路、不讀固定研究輸出來提供數字。"""

    initial_status = "checking_extraction_cache"

    def __init__(
        self,
        repository: Path,
        data: Path,
        registry: ParserRegistry | None = None,
        progress: Callable[[dict], None] | None = None,
    ):
        self.repository = repository
        self.progress = progress
        self.registry = registry or ParserRegistry()
        self.cache = WorkflowCache(data)

    def rule_fingerprint(self, ticker: str) -> str:
        entry = self.registry.entries[ticker]
        package = Path(__file__).parent
        names = [
            "engines.py",
            "workflow.py",
            "service.py",
            "parsers/base.py",
            "parsers/table_support.py",
        ]
        # 只納入這家公司資料夾內的程式；改 AAPL 不使 MSFT 的萃取快取失效。
        names += sorted(
            path.relative_to(package).as_posix()
            for path in self.registry.issuer_dir(ticker).glob("*.py")
        )
        code = {
            name: hashlib.sha256((package / name).read_bytes()).hexdigest()
            for name in names
        }
        return hashlib.sha256(
            JsonCodec.encode({"code": code, "registry": entry})
        ).hexdigest()

    def run(
        self, tickers: list[str], selection: PeriodSelection, force: bool = False
    ) -> dict:
        report = {"stage": "extract", "companies": [], "complete": True}
        for ticker in tickers:
            parser = self.registry.create(ticker, self.repository, self.cache.root)
            if self.progress:
                self.progress({"ticker": ticker, "status": self.initial_status})
            saved = self.cache.read(ticker, "downloads")
            if not saved:
                raise ValueError(ticker + " 尚未下載；請先執行 download")
            if any(
                not entry.get("download_complete", True)
                for entry in saved["filings"].values()
            ):
                raise ValueError(
                    ticker + " 有下載未完成的文件組；先完成 download，不混用新舊附件"
                )
            candidates = [
                entry["filing"]
                for entry in saved["filings"].values()
                if entry["filing"]["reportDate"] in saved["target_periods"]
            ]
            targets = selection.choose(candidates)
            if not targets:
                raise ValueError(ticker + " 指定範圍無已下載的目標期別")
            # 完整下載集合是比較欄與 Q4 的輸入；hash／期間變動會明確使 cache 失效。
            sources = []
            for entry in saved["filings"].values():
                for role, receipt in entry["documents"].items():
                    self.cache.body(receipt)
                    sources.append(
                        {
                            "accession": entry["filing"]["accessionNumber"],
                            "role": role,
                            "sha256": receipt["sha256"],
                            "filing": entry["filing"],
                        }
                    )
            fingerprint = hashlib.sha256(
                JsonCodec.encode(
                    {
                        "sources": sorted(
                            sources, key=lambda r: (r["accession"], r["role"])
                        ),
                        "rules": self.rule_fingerprint(ticker),
                    }
                )
            ).hexdigest()
            extraction = self.cache.read(ticker, "extractions", {"periods": {}})
            company = {"ticker": ticker, "periods": []}
            pending = []
            for filing in targets:
                period = filing["reportDate"]
                previous = extraction["periods"].get(period)
                if (
                    not force
                    and previous
                    and previous["fingerprint"] == fingerprint
                    and previous["status"] == "complete"
                    and all(
                        (self.cache.root / o["path"]).exists()
                        for o in previous["outputs"]
                    )
                ):
                    for output in previous["outputs"]:
                        self.cache.body(output)
                    company["periods"].append(
                        {"period_end": period, "status": "cache_hit"}
                    )
                    if self.progress:
                        self.progress(
                            {"ticker": ticker, "period": period, "status": "cache_hit"}
                        )
                else:
                    pending.append(filing)
            if not pending:
                self.update_viewer_index(ticker, extraction)
                report["companies"].append(company)
                continue
            records, errors = [], []
            active_filings = PeriodSelection("1900-01-01", "9999-12-31").choose(
                [entry["filing"] for entry in saved["filings"].values()]
            )
            active = [saved["filings"][f["accessionNumber"]] for f in active_filings]
            for entry in sorted(active, key=lambda e: e["filing"]["filingDate"]):
                filing = entry["filing"]
                try:
                    documents = {
                        role: (self.cache.body(receipt), receipt)
                        for role, receipt in entry["documents"].items()
                    }
                    record = parser.extract_document(filing, documents)
                    records.append(record)
                except (ValueError, KeyError, ArithmeticError, LxmlError) as error:
                    errors.append(
                        {
                            "accession": filing["accessionNumber"],
                            "period_end": filing["reportDate"],
                            "error": str(error),
                        }
                    )
            periods = [f["reportDate"] for f in pending]
            try:
                rows = parser.parse_downloaded(
                    records, sorted(set(saved["target_periods"]) | set(periods))
                )
            except (ValueError, KeyError, StopIteration) as error:
                rows = []
                errors.append({"error": str(error), "stage": "issuer_rules"})
            for row in rows:
                if not row["outputs"]:
                    row["outputs"] = {
                        "Revenue": {
                            "status": "issuer_rules_empty",
                            "value_usd": None,
                            "SEC_operands": [],
                        }
                    }
            receipts = [
                receipt
                for entry in saved["filings"].values()
                for receipt in entry["documents"].values()
            ]
            risk_groups = {}
            for row in rows:
                risk_groups.setdefault(row["basis"], []).append(row)
            for basis, group in risk_groups.items():
                risk = RiskAnalyzer().assess(group, receipts)
                for row in group:
                    row["risk"] = risk
            for filing in pending:
                period = filing["reportDate"]
                chosen = [row for row in rows if row["period_end"] == period]
                if not chosen:
                    chosen = [
                        {
                            "ticker": ticker,
                            "period_end": period,
                            "period_kind": "Q",
                            "basis": self.registry.entries[ticker]["primary_basis"],
                            "outputs": {
                                "Revenue": {
                                    "status": "source_extraction_failed",
                                    "value_usd": None,
                                    "SEC_operands": [],
                                }
                            },
                        }
                    ]
                successful = bool(chosen) and all(
                    row["outputs"]
                    and all(o["status"] == "observed" for o in row["outputs"].values())
                    for row in chosen
                )
                current_errors = [
                    e
                    for e in errors
                    if e.get("period_end") == period or "period_end" not in e
                ]
                if current_errors:
                    successful = False
                output_receipts = []
                for row in chosen:
                    row.update(parser.fiscal_label(period, records))
                    direct = next(
                        (
                            r
                            for r in reversed(records)
                            if r["filing"]["reportDate"] == period
                        ),
                        {},
                    )
                    if str(direct.get("fiscal_year", "")).isdigit() and direct.get(
                        "fiscal_focus"
                    ) in ("Q1", "Q2", "Q3", "Q4", "FY"):
                        row.update(
                            fiscal_year=int(direct["fiscal_year"]),
                            fiscal_quarter=(
                                4
                                if direct["fiscal_focus"] == "FY"
                                else int(direct["fiscal_focus"][1])
                            ),
                            label_status="SEC_document_fiscal_focus",
                        )
                    row.update(
                        primary_basis=self.registry.entries[ticker]["primary_basis"],
                        reference=self.registry.entries[ticker]["reference"],
                        input_fingerprint=fingerprint,
                        extraction_mode="downloaded_SEC_bytes",
                        source_errors=errors,
                    )
                    row["source_formats"] = sorted(
                        {
                            f.get("source_format", "original_html")
                            for o in row["outputs"].values()
                            for f in o["SEC_operands"]
                        }
                    )
                    if not row.get("risk"):
                        row["risk"] = RiskAnalyzer().assess([row], receipts)
                    if current_errors:
                        row["risk"].update(
                            level="high", score=max(50, row["risk"]["score"])
                        )
                        row["risk"]["reasons"] = list(row["risk"]["reasons"]) + [
                            "SEC 原文萃取拒絕／失敗：" + str(current_errors)
                        ]
                    for output in row["outputs"].values():
                        output["reported_error_usd"] = PrecisionAnalyzer().output_error(
                            output
                        )
                    name = f"{ticker}_{period}_{row['basis']}_revenue.json"
                    relative = Path("outputs") / ticker / period / name
                    JsonCodec.write(self.cache.root / relative, row)
                    # 固定主路徑外另存版本，force 後不覆蓋不同來源／規則的舊結果。
                    version = relative.parent / "versions" / fingerprint / name
                    JsonCodec.write(self.cache.root / version, row)
                    raw = (self.cache.root / relative).read_bytes()
                    output_receipts.append(
                        {
                            "path": str(relative),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw),
                        }
                    )
                status = "complete" if successful else "partial_or_failed"
                if self.progress:
                    self.progress(
                        {"ticker": ticker, "period": period, "status": status}
                    )
                extraction["periods"][period] = {
                    "fingerprint": fingerprint,
                    "status": status,
                    "outputs": output_receipts,
                    "errors": errors,
                }
                company["periods"].append(
                    {"period_end": period, "status": status, "errors": errors}
                )
                report["complete"] &= successful
            self.cache.write(ticker, "extractions", extraction)
            self.update_viewer_index(ticker, extraction)
            report["companies"].append(company)
        return report

    def update_viewer_index(self, ticker: str, extraction: dict):
        path = self.cache.root / "outputs" / ticker / "index.json"
        old = JsonCodec.read(path) if path.exists() else {"paths": []}
        updated = {period for period in extraction["periods"]}
        paths = [p for p in old["paths"] if p.split("/")[0] not in updated]
        paths.extend(
            str(Path(o["path"]).relative_to(Path("outputs") / ticker))
            for e in extraction["periods"].values()
            for o in e["outputs"]
        )
        JsonCodec.write(
            path,
            {
                "paths": sorted(set(paths)),
                "periods": sorted(updated),
                "mode": "downloaded_SEC_bytes",
            },
        )
