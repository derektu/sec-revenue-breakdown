"""獨立下載／萃取工作流；一般操作只讀 local SEC cache，不讀研究答案。"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

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


class SupportedTickers:
    def __init__(self, registry: ParserRegistry | None = None):
        self.registry = registry or ParserRegistry()

    def select(
        self, tickers: list[str] | None = None, file: Path | None = None
    ) -> list[str]:
        names = []
        for item in tickers or []:
            names.extend(
                part.strip().upper() for part in item.split(",") if part.strip()
            )
        if file:
            if file.suffix == ".json":
                payload = json.loads(file.read_text())
                if not isinstance(payload, list) or any(
                    not isinstance(t, str) for t in payload
                ):
                    raise ValueError("ticker JSON 必須是字串清單")
                names.extend(t.strip().upper() for t in payload if t.strip())
            else:
                for line in file.read_text().splitlines():
                    names.extend(
                        t.upper()
                        for t in re.split(r"[\s,]+", line.split("#", 1)[0].strip())
                        if t
                    )
        if not names and file is not None:
            raise ValueError("ticker 清單檔為空；不會自動下載全部公司")
        if not names or "ALL" in names:
            names = list(self.registry.entries) + [
                name for name in names if name != "ALL"
            ]
        unknown = sorted(set(names) - set(self.registry.entries))
        if unknown:
            raise ValueError("不支援 ticker：" + ", ".join(unknown))
        return list(dict.fromkeys(names))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("SEC 重新導向已停止，未追蹤其他 URL")


class SecHttpClient:
    """沿用環境 proxy／CA，至多每秒五次，單次 GET，拒絕即停止。"""

    def __init__(self, user_agent: str | None = None, interval: float = 0.2):
        self.user_agent = (
            user_agent
            if user_agent is not None
            else os.environ.get("SEC_USER_AGENT", "")
        )
        self.interval, self.last_request = max(interval, 0.2), 0.0
        self.requests = 0
        self.opener = build_opener(NoRedirect())

    def get(self, url: str, kind: str) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in ("www.sec.gov", "data.sec.gov")
            or parsed.query
            or parsed.fragment
            or ".." in parsed.path.split("/")
        ):
            raise ValueError("只接受 SEC HTTPS URL")
        if (
            not self.user_agent.strip()
            or "@" not in self.user_agent
            or any(
                s in self.user_agent.lower()
                for s in ("example.com", "your-real-contact")
            )
        ):
            raise ValueError(
                "網路下載需設定真實 SEC_USER_AGENT（組織／姓名與聯絡 email）；離線快取不需要"
            )
        remaining = self.interval - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_request = time.monotonic()
        self.requests += 1
        with self.opener.open(
            Request(
                url,
                headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"},
            ),
            timeout=45,
        ) as response:
            if response.geturl() != url:
                raise ValueError("SEC 最終 URL 不一致")
            content_type = response.headers.get_content_type()
            if (
                response.headers.get("Content-Encoding", "identity").lower()
                != "identity"
            ):
                raise ValueError(
                    "SEC 回應編碼不符 identity；停止，避免把壓縮 bytes 假存為 HTML／JSON"
                )
            body = response.read()
        if kind == "html" and content_type not in (
            "text/html",
            "application/xhtml+xml",
        ):
            raise ValueError("非 HTML response，不儲存成 .html")
        if kind == "json":
            json.loads(body)
        return body


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


class SecFilingCatalog:
    """SEC submissions recent 與歷史分頁；CIK 由支援清單明列。"""

    def __init__(
        self, cache: WorkflowCache, registry: ParserRegistry, http: SecHttpClient
    ):
        self.cache, self.registry, self.http = cache, registry, http
        self.last_source = "not_loaded"

    def load(
        self,
        ticker: str,
        selection: PeriodSelection,
        refresh: bool = False,
        offline: bool = False,
    ) -> list[dict]:
        cached = self.cache.read(ticker, "catalog")
        if cached and (offline or not refresh):
            for receipt in cached["receipts"]:
                self.cache.body(receipt)
            if (
                hashlib.sha256(JsonCodec.encode(cached["filings"])).hexdigest()
                != cached["filings_sha256"]
            ):
                raise ValueError("SEC catalog index hash 不符")
            # 先前只抓 recent 時，較舊範圍必須補索引，不能默默當不存在。
            oldest = min(
                (
                    f["reportDate"]
                    for f in cached["filings"]
                    if f["form"] in ("10-K", "10-Q")
                ),
                default="9999",
            )
            if (
                not (selection.start or selection.end)
                or (selection.start or selection.end) >= oldest
                or cached.get("history_complete")
            ):
                self.last_source = "offline_catalog" if offline else "catalog_cache_hit"
                return cached["filings"]
            if offline:
                raise ValueError(
                    "離線 catalog 尚未覆蓋指定歷史範圍；先線上 download 補索引"
                )
        if offline:
            raise ValueError(ticker + " 尚無本機 SEC submissions cache")
        filings, receipts = [], []
        history_complete = True
        for cik in self.registry.entries[ticker]["submission_ciks"]:
            url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
            body = self.http.get(url, "json")
            receipts.append(
                self.cache.capture(ticker, "_metadata", str(cik), body, "sec_json", url)
            )
            data = json.loads(body)
            recent = self.columns(
                data.get("filings", {}).get("recent", {}), str(int(cik))
            )
            filings.extend(recent)
            oldest = min(
                (f["reportDate"] for f in recent if f["form"] in ("10-K", "10-Q")),
                default="9999",
            )
            need_history = bool(selection.start and selection.start < oldest) or bool(
                selection.end and selection.end < oldest
            )
            histories = data.get("filings", {}).get("files", [])
            history_complete &= need_history or not histories
            if need_history:
                for page in histories:
                    name = page["name"]
                    if not re.fullmatch(r"CIK\d+-submissions-\d+\.json", name):
                        raise ValueError("SEC 歷史分頁檔名不符")
                    page_url = "https://data.sec.gov/submissions/" + name
                    raw = self.http.get(page_url, "json")
                    receipts.append(
                        self.cache.capture(
                            ticker, "_metadata", str(cik), raw, "sec_json", page_url
                        )
                    )
                    filings.extend(self.columns(json.loads(raw), str(int(cik))))
        if cached:
            # 更新 recent 不丟掉已快取的歷史索引／來源收據，離線舊期仍可使用。
            if (
                hashlib.sha256(JsonCodec.encode(cached["filings"])).hexdigest()
                != cached["filings_sha256"]
            ):
                raise ValueError("SEC catalog index hash 不符")
            for receipt in cached["receipts"]:
                self.cache.body(receipt)
            filings = cached["filings"] + filings
            receipts = list(
                {
                    receipt["path"]: receipt
                    for receipt in cached["receipts"] + receipts
                }.values()
            )
            history_complete = history_complete or cached.get("history_complete", False)
        filings = list({f["accessionNumber"]: f for f in filings}.values())
        filings.sort(
            key=lambda f: (f["reportDate"], f["filingDate"], f["accessionNumber"])
        )
        self.cache.index_catalog(ticker, filings, receipts)
        index = self.cache.read(ticker, "catalog")
        index["history_complete"] = history_complete
        self.cache.write(ticker, "catalog", index)
        self.last_source = "SEC_catalog_fetched"
        return filings

    def columns(self, columns: dict, cik: str) -> list[dict]:
        forms = columns.get("form", [])
        result = []
        for i, original_form in enumerate(forms):
            if original_form not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "8-K"):
                continue
            row = {
                key: columns[key][i]
                for key in (
                    "accessionNumber",
                    "filingDate",
                    "reportDate",
                    "primaryDocument",
                )
            }
            if not row["reportDate"]:
                continue
            dt.date.fromisoformat(row["reportDate"])
            if not re.fullmatch(
                r"\d{10}-\d{2}-\d{6}", row["accessionNumber"]
            ) or not re.fullmatch(r"[A-Za-z0-9_.-]+", row["primaryDocument"]):
                raise ValueError("SEC accession／主文件名不符")
            result.append(
                dict(
                    row,
                    cik=cik,
                    form=original_form.split("/")[0],
                    original_form=original_form,
                )
            )
        return result


class DownloadWorkflow:
    initial_status = "loading_catalog"

    def __init__(
        self,
        repository: Path,
        data: Path,
        http: SecHttpClient | None = None,
        registry: ParserRegistry | None = None,
        progress: Callable[[dict], None] | None = None,
    ):
        self.repository = repository
        self.progress = progress
        self.registry = registry or ParserRegistry()
        self.cache = WorkflowCache(data)
        self.http = http or SecHttpClient()
        self.catalog = SecFilingCatalog(self.cache, self.registry, self.http)

    def run(
        self,
        tickers: list[str],
        selection: PeriodSelection,
        force: bool = False,
        offline: bool = False,
    ) -> dict:
        if force and offline:
            raise ValueError("--force 與 --offline 不可同時使用")
        report = {"stage": "download", "companies": []}
        for ticker in tickers:
            parser = self.registry.create(ticker, self.repository, self.cache.root)
            if self.progress:
                self.progress({"ticker": ticker, "status": self.initial_status})
            filings = self.catalog.load(
                ticker, selection, refresh=force or selection.latest, offline=offline
            )
            filings = parser.catalog_filings(filings)
            targets = selection.choose(filings)
            if not targets:
                raise ValueError(ticker + " 指定期間沒有 SEC 10-K／10-Q")
            plan = {f["accessionNumber"]: f for f in targets}
            for filing in targets:
                for dependency in parser.download_dependencies(filing, filings):
                    plan[dependency["accessionNumber"]] = dependency
            saved = self.cache.read(
                ticker, "downloads", {"filings": {}, "target_periods": []}
            )
            company = {
                "ticker": ticker,
                "catalog_source": self.catalog.last_source,
                "target_periods": [f["reportDate"] for f in targets],
                "filings": [],
            }
            for accession, filing in sorted(
                plan.items(), key=lambda pair: pair[1]["filingDate"]
            ):
                existing = saved["filings"].get(accession)
                roles = parser.required_document_roles(filing)
                if (
                    existing
                    and not force
                    and existing.get("download_complete", True)
                    and set(roles).issubset(existing["documents"])
                ):
                    for receipt in existing["documents"].values():
                        self.cache.body(receipt)
                    status = "cache_hit"
                else:
                    if offline:
                        raise ValueError(ticker + " 缺原文 cache：" + accession)
                    base = f"https://www.sec.gov/Archives/edgar/data/{int(filing['cik'])}/{accession.replace('-', '')}/"
                    names = [filing["primaryDocument"]]
                    if parser.needs_filing_index(filing):
                        index_url = base + "index.json"
                        raw = self.http.get(index_url, "json")
                        self.cache.capture(
                            ticker,
                            filing["reportDate"],
                            accession,
                            raw,
                            "sec_json",
                            index_url,
                        )
                        names = [
                            item["name"]
                            for item in json.loads(raw)["directory"]["item"]
                        ]
                    selected = parser.document_names(filing, names)
                    documents = (
                        dict(existing["documents"]) if existing and not force else {}
                    )
                    saved["filings"][accession] = {
                        "filing": filing,
                        "documents": documents,
                        "download_complete": False,
                    }
                    self.cache.write(ticker, "downloads", saved)
                    for role, name in selected.items():
                        if not re.fullmatch(
                            r"[A-Za-z0-9_.-]+\.(?:htm|html)", name, re.I
                        ):
                            raise ValueError("附件檔名不符")
                        url = base + quote(name)
                        if role in documents and not force:
                            self.cache.body(documents[role])
                            continue
                        raw = self.http.get(url, "html")
                        documents[role] = self.cache.capture(
                            ticker,
                            filing["reportDate"],
                            accession,
                            raw,
                            "original_html",
                            url,
                        )
                        # 每個成功檔案立即存收據；下一檔失敗也不丟失已取得 bytes。
                        saved["filings"][accession] = {
                            "filing": filing,
                            "documents": documents,
                            "download_complete": False,
                        }
                        self.cache.write(ticker, "downloads", saved)
                    saved["filings"][accession]["download_complete"] = True
                    self.cache.write(ticker, "downloads", saved)
                    status = "downloaded"
                if self.progress:
                    self.progress(
                        {
                            "ticker": ticker,
                            "period": filing["reportDate"],
                            "status": status,
                        }
                    )
                company["filings"].append(
                    {
                        "accession": accession,
                        "period_end": filing["reportDate"],
                        "status": status,
                        "dependency": filing not in targets,
                    }
                )
            saved["target_periods"] = sorted(
                set(saved["target_periods"]) | {f["reportDate"] for f in targets}
            )
            self.cache.write(ticker, "downloads", saved)
            report["companies"].append(company)
        return report


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
