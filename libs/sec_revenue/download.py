"""SEC 下載：CIK 查詢、申報清單與完整申報包。

任何 ticker 都能下載；每份文件保存 sha256、filing index、文件原址與 inline XBRL viewer URL，記錄在
`pipeline/<TICKER>/packages.json`。parser 只讀申報包，不需要另外的下載清單。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import http.client

from lxml import etree, html as lxml_html
from lxml.etree import LxmlError

from .common.jsonio import JsonCodec
from .common.periods import PeriodSelection
from .universe import load_tickers

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC 公平存取上限為每秒 10 個請求；每秒 8 個保留餘量。
MIN_REQUEST_INTERVAL = 0.125
# 這兩種回應代表身分或速率被 SEC 拒絕；繼續送請求違反 SEC 規範，整批停止。
BLOCKING_HTTP_STATUSES = (403, 429)
PERIODIC_FORMS = ("10-K", "10-Q")
EARNINGS_ITEM = "2.02"
INLINE_XBRL_NAMESPACE = "http://www.xbrl.org/2013/inlineXBRL"
DOCUMENT_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
# company_tickers.json 超過這個天數就重新抓取。
COMPANY_TICKERS_MAX_AGE = dt.timedelta(days=7)
# 單一檔案的網路／協定錯誤：記為該檔 failure，其他檔案照常下載。
FILE_ERRORS = (HTTPError, URLError, OSError, ValueError, http.client.HTTPException, LxmlError)
# XBRL 呈現檔：R 頁面與 SEC 為其產生的輔助檔，只在 include_r_pages 時下載。
RENDERING_RE = re.compile(
    r"R\d+\.(?:htm|xml)|Financial_Report\.xlsx?|report\.css|Show\.js|MetaLinks\.json",
    re.I,
)


class SecIdentityError(ValueError):
    """缺少或不合格的 SEC_USER_AGENT；所有請求都會失敗，整批停止。"""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("SEC 重新導向已停止，未追蹤其他 URL")


class SecHttpClient:
    """沿用環境 proxy／CA，至多每秒八次，單次 GET，拒絕即停止。"""

    def __init__(self, user_agent: str | None = None, interval: float = MIN_REQUEST_INTERVAL):
        self.user_agent = (
            user_agent if user_agent is not None else os.environ.get("SEC_USER_AGENT", "")
        )
        self.interval, self.last_request = max(interval, MIN_REQUEST_INTERVAL), 0.0
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
                s in self.user_agent.lower() for s in ("example.com", "your-real-contact")
            )
        ):
            raise SecIdentityError(
                "網路下載需設定真實 SEC_USER_AGENT（組織／姓名與聯絡 email）；離線快取不需要"
            )
        remaining = self.interval - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_request = time.monotonic()
        self.requests += 1
        with self.opener.open(
            Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"}),
            timeout=45,
        ) as response:
            if response.geturl() != url:
                raise ValueError("SEC 最終 URL 不一致")
            content_type = response.headers.get_content_type()
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError(
                    "SEC 回應編碼不符 identity；停止，避免把壓縮 bytes 假存為 HTML／JSON"
                )
            body = response.read()
        if kind == "html" and content_type not in ("text/html", "application/xhtml+xml"):
            raise ValueError("非 HTML response，不儲存成 .html")
        if kind == "json":
            json.loads(body)
        return body


def is_blocking(error: BaseException) -> bool:
    return isinstance(error, SecIdentityError) or (
        isinstance(error, HTTPError) and error.code in BLOCKING_HTTP_STATUSES
    )


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


class CikResolver:
    """`tickers.csv` 列出的 CIK 優先（可多個：前身與繼受實體）；沒列的查 SEC company_tickers.json。

    company_tickers.json 快取超過 7 天，或快取裡查不到該 ticker 時重新抓取（每次執行至多一次）。
    """

    def __init__(
        self,
        cache: WorkflowCache,
        http: SecHttpClient,
        tickers_csv: Path | None = None,
    ):
        self.cache, self.http = cache, http
        self.listed = {entry.ticker: list(entry.ciks) for entry in load_tickers(tickers_csv)}
        self.refreshed = False

    def resolve(self, ticker: str, offline: bool = False) -> dict:
        if ticker in self.listed:
            return {"ciks": self.listed[ticker], "source": "tickers_csv"}
        index = self.cache.read("_sec", "company_tickers")
        if not offline and not self.refreshed and (not index or self.stale(index)):
            index = self.refresh()
        cik = self.lookup(index, ticker) if index else None
        if cik is None and not offline and not self.refreshed:
            index = self.refresh()
            cik = self.lookup(index, ticker)
        if cik is None:
            if offline and not index:
                raise ValueError(ticker + " 不在 tickers.csv，且本機沒有 SEC company_tickers.json 快取")
            raise ValueError(ticker + " 不在 tickers.csv，也不在 SEC company_tickers.json")
        return {
            "ciks": [cik],
            "source": "sec_company_tickers",
            "company_tickers_fetched_at_utc": index["fetched_at_utc"],
        }

    @staticmethod
    def stale(index: dict) -> bool:
        fetched = dt.datetime.fromisoformat(index["fetched_at_utc"])
        return dt.datetime.now(dt.timezone.utc) - fetched > COMPANY_TICKERS_MAX_AGE

    def refresh(self) -> dict:
        self.refreshed = True
        raw = self.http.get(COMPANY_TICKERS_URL, "json")
        receipt = RawFileStore(self.cache).write(
            Path("sec") / "_sec" / "company_tickers", raw, "json", {"source_url": COMPANY_TICKERS_URL}
        )
        index = {"receipt": receipt, "fetched_at_utc": utc_now()}
        self.cache.write("_sec", "company_tickers", index)
        return index

    def lookup(self, index: dict, ticker: str) -> str | None:
        data = json.loads(self.cache.body(index["receipt"]))
        matches = {
            str(int(row["cik_str"]))
            for row in data.values()
            if str(row.get("ticker", "")).upper() == ticker
        }
        if len(matches) > 1:
            raise ValueError(ticker + " 在 SEC company_tickers.json 對應多個 CIK；請在 tickers.csv 明列")
        return next(iter(matches), None)


class SecFilingCatalog:
    """SEC submissions recent 與歷史分頁；另記 8-K 的 item 代碼供挑選財報新聞稿。

    catalog 記錄抓取時的 CIK 清單；與目前解析出的 CIK 清單不同時，捨棄舊 catalog 重抓。
    """

    def __init__(self, cache: WorkflowCache, http: SecHttpClient):
        self.cache, self.http = cache, http
        self.last_source = "not_loaded"

    def load(
        self,
        ticker: str,
        ciks: list[str],
        selection: PeriodSelection,
        refresh: bool = False,
        offline: bool = False,
        need_items: bool = False,
        full_history: bool = False,
    ) -> list[dict]:
        cached = self.cache.read(ticker, "catalog")
        if cached and "ciks" in cached and cached["ciks"] != ciks:
            if offline:
                raise ValueError(
                    f"{ticker} 本機 catalog 的 CIK {cached['ciks']} 與目前 {ciks} 不同；先線上 download 重抓"
                )
            cached = None
        missing_items = bool(cached) and need_items and "eight_k_items" not in cached
        if cached:
            self.verify(cached)
        if cached and (offline or (not refresh and not missing_items and not full_history)):
            # 先前只抓 recent 時，較舊範圍必須補索引，不能默默當不存在。
            oldest = min(
                (f["reportDate"] for f in cached["filings"] if f["form"] in PERIODIC_FORMS),
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
                raise ValueError("離線 catalog 尚未覆蓋指定歷史範圍；先線上 download 補索引")
        if offline:
            raise ValueError(ticker + " 尚無本機 SEC submissions cache")
        filings, receipts, items = [], [], {}
        history_complete = True
        for cik in ciks:
            url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
            body = self.http.get(url, "json")
            receipts.append(self.cache.capture(ticker, "_metadata", str(cik), body, "sec_json", url))
            data = json.loads(body)
            columns = data.get("filings", {}).get("recent", {})
            recent = self.columns(columns, str(int(cik)))
            items.update(self.eight_k_items(columns))
            filings.extend(recent)
            oldest = min(
                (f["reportDate"] for f in recent if f["form"] in PERIODIC_FORMS),
                default="9999",
            )
            need_history = (
                full_history
                or bool(selection.start and selection.start < oldest)
                or bool(selection.end and selection.end < oldest)
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
                        self.cache.capture(ticker, "_metadata", str(cik), raw, "sec_json", page_url)
                    )
                    page_columns = json.loads(raw)
                    filings.extend(self.columns(page_columns, str(int(cik))))
                    items.update(self.eight_k_items(page_columns))
        if cached:
            # 更新 recent 不丟掉已快取的歷史索引／來源收據，離線舊期仍可使用。
            filings = cached["filings"] + filings
            receipts = list(
                {receipt["path"]: receipt for receipt in cached["receipts"] + receipts}.values()
            )
            history_complete = history_complete or cached.get("history_complete", False)
            items = dict(cached.get("eight_k_items", {}), **items)
        filings = list({f["accessionNumber"]: f for f in filings}.values())
        filings.sort(key=lambda f: (f["reportDate"], f["filingDate"], f["accessionNumber"]))
        self.cache.index_catalog(ticker, filings, receipts)
        index = self.cache.read(ticker, "catalog")
        index["history_complete"] = history_complete
        index["ciks"] = list(ciks)
        index["eight_k_items"] = dict(sorted(items.items()))
        self.cache.write(ticker, "catalog", index)
        self.last_source = "SEC_catalog_fetched"
        return filings

    def verify(self, cached: dict):
        for receipt in cached["receipts"]:
            self.cache.body(receipt)
        if hashlib.sha256(JsonCodec.encode(cached["filings"])).hexdigest() != cached["filings_sha256"]:
            raise ValueError("SEC catalog index hash 不符")

    def items(self, ticker: str) -> dict:
        """accession → 8-K item 代碼；catalog 沒記錄的 accession 不在結果中。"""
        cached = self.cache.read(ticker, "catalog") or {}
        return cached.get("eight_k_items", {})

    @staticmethod
    def eight_k_items(columns: dict) -> dict:
        # 沒有 items 欄的分頁不記錄，讓這些 8-K 保持「item 不明」，不當成非 2.02。
        if "items" not in columns:
            return {}
        forms, numbers = columns.get("form", []), columns.get("accessionNumber", [])
        values = columns["items"]
        return {
            numbers[i]: values[i] or ""
            for i, form in enumerate(forms)
            if form.split("/")[0] == "8-K"
        }

    def columns(self, columns: dict, cik: str) -> list[dict]:
        forms = columns.get("form", [])
        result = []
        for i, original_form in enumerate(forms):
            if original_form not in ("10-K", "10-Q", "10-K/A", "10-Q/A", "8-K"):
                continue
            row = {
                key: columns[key][i]
                for key in ("accessionNumber", "filingDate", "reportDate", "primaryDocument")
            }
            # 沒有期間或主文件的列不收：SEC 早期純文字申報（1990 年代）沒有主文件，無法解析也無法挑選文件。
            if not row["reportDate"] or not row["primaryDocument"]:
                continue
            dt.date.fromisoformat(row["reportDate"])
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", row["accessionNumber"]) or not re.fullmatch(
                r"[A-Za-z0-9_.-]+", row["primaryDocument"]
            ):
                raise ValueError("SEC accession／主文件名不符")
            result.append(
                dict(row, cik=cik, form=original_form.split("/")[0], original_form=original_form)
            )
        return result


def release_window(filings: list[dict], targets: list[dict], selection: PeriodSelection) -> list[dict]:
    """可能是所選各期財報新聞稿的 8-K（尚未看 item 代碼）。

    申報日須晚於最早目標期的期末；有 `--end` 時不晚於最後目標期期末後 90 天。
    下一季的新聞稿必在下一季期末（約 91 天後）之後，所以 90 天內只會是範圍內各期的新聞稿。
    沒有 `--end` 時不設上限，包含最新一季尚未申報 10-Q 前的新聞稿。
    """
    if not targets:
        return []
    first = min(f["reportDate"] for f in targets)
    last = dt.date.fromisoformat(max(f["reportDate"] for f in targets))
    upper = (last + dt.timedelta(days=90)).isoformat() if selection.end else None
    return [
        f
        for f in filings
        if f["form"] == "8-K"
        and f["filingDate"] > first
        and (upper is None or f["filingDate"] <= upper)
    ]


def earnings_releases(
    filings: list[dict], items: dict, targets: list[dict], selection: PeriodSelection
) -> list[dict]:
    """申報窗口內 item 2.02（Results of Operations）的 8-K；沒有 item 資料的 8-K 不在結果中。"""
    return [
        f
        for f in release_window(filings, targets, selection)
        if EARNINGS_ITEM in [i.strip() for i in items.get(f["accessionNumber"], "").split(",")]
    ]


def package_filings(filings: list[dict], targets: list[dict], dependency_periods: list[str] = ()) -> list[dict]:
    """目標期別與依賴期別的所有 10-K／10-Q 申報，原始與修訂版都包含。"""
    periods = {f["reportDate"] for f in targets} | set(dependency_periods)
    return [f for f in filings if f["form"] in PERIODIC_FORMS and f["reportDate"] in periods]


def q4_dependencies(filings: list[dict], targets: list[dict]) -> dict:
    """目標 10-K 推算 Q4 與檢查 Q4 口徑所需、但不在目標中的期別。

    每份目標 10-K 需要同財年的 10-Q（Q1–Q3）與上一份 10-K。上一份 10-K 是期末早於目標、最晚的一期 10-K；
    同財年的 10-Q 是期末介於上一份 10-K 與目標之間的各期。catalog 中沒有上一份 10-K 時，取目標前 370 天內的 10-Q，
    並把該期列在 `unresolved`。
    """
    periodic = [f for f in filings if f["form"] in PERIODIC_FORMS]
    annual = sorted({f["reportDate"] for f in periodic if f["form"] == "10-K"})
    quarterly = sorted({f["reportDate"] for f in periodic if f["form"] == "10-Q"})
    chosen = {f["reportDate"] for f in targets}
    needed, unresolved = set(), []
    for end in sorted({f["reportDate"] for f in targets if f["form"] == "10-K"}):
        prior = [d for d in annual if d < end]
        if prior:
            start = prior[-1]
            needed.add(start)
        else:
            start = (dt.date.fromisoformat(end) - dt.timedelta(days=370)).isoformat()
            unresolved.append(f"{end} 的上一份 10-K 不在 SEC catalog 中")
        needed.update(d for d in quarterly if start < d < end)
    return {"periods": sorted(needed - chosen), "unresolved": unresolved}


class FilingIndexPage:
    """解析 SEC filing index（`ACC-index.htm`）的文件表，取每份文件的 Type 與 Description。"""

    @staticmethod
    def document_types(raw: bytes) -> dict[str, dict]:
        result = {}
        tree = lxml_html.fromstring(raw)
        for row in tree.xpath("//table[contains(@class,'tableFile')]//tr[td]"):
            cells = row.xpath("./td")
            links = row.xpath(".//a/@href")
            if len(cells) < 4 or not links:
                continue
            href = links[0]
            if href.startswith("/ix?doc="):
                href = href[len("/ix?doc=") :]
            name = href.rsplit("/", 1)[-1]
            result[name] = {
                "type": cells[3].text_content().strip(),
                "description": cells[1].text_content().strip(),
            }
        return result


def is_inline_xbrl(raw: bytes) -> bool:
    """根元素宣告 inline XBRL namespace，且文件含 `ix:header`。"""
    try:
        root = etree.fromstring(raw, etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False))
    except (LxmlError, ValueError):
        return False
    if root is None or INLINE_XBRL_NAMESPACE not in root.nsmap.values():
        return False
    return next(root.iter(f"{{{INLINE_XBRL_NAMESPACE}}}header"), None) is not None


class FilingPackages:
    """下載並保存完整申報包；一份檔案失敗只記錄在 failures，其餘照常下載。

    packages.json 在每個申報包結束或中斷時寫一次；已下載的 bytes 在檔案寫入時就已保存。
    """

    def __init__(self, cache: WorkflowCache, http: SecHttpClient):
        self.cache, self.http = cache, http
        self.files = RawFileStore(cache)

    @staticmethod
    def base_url(filing: dict) -> str:
        return f"{SEC_ARCHIVES}/{int(filing['cik'])}/{filing['accessionNumber'].replace('-', '')}/"

    @classmethod
    def filing_index_url(cls, filing: dict) -> str:
        return cls.base_url(filing) + filing["accessionNumber"] + "-index.htm"

    @staticmethod
    def ixviewer_url(filing: dict, name: str) -> str:
        return (
            "https://www.sec.gov/ix?doc=/Archives/edgar/data/"
            f"{int(filing['cik'])}/{filing['accessionNumber'].replace('-', '')}/{name}"
        )

    @staticmethod
    def classify(filing: dict, name: str, include_r_pages: bool, is_dir: bool = False) -> str | None:
        """回傳略過原因；None 表示要下載。"""
        accession = filing["accessionNumber"]
        lower = name.lower()
        if is_dir:
            return "directory"
        if name in (".", "..") or not DOCUMENT_NAME_RE.fullmatch(name):
            return "unsupported_name"
        if lower == accession + ".txt":
            return "complete_submission_text"
        if lower.startswith(accession + "-index"):
            return "filing_index_page"
        if lower.endswith(".zip"):
            return "archive_zip"
        if RENDERING_RE.fullmatch(name) and not include_r_pages:
            return "r_page_not_requested"
        return None

    @staticmethod
    def missing_r_pages(package: dict) -> list[str]:
        return sorted(n for n, reason in package["skipped"].items() if reason == "r_page_not_requested")

    def read(self, ticker: str) -> dict:
        return self.cache.read(ticker, "packages", {"packages": {}})

    def download(
        self,
        ticker: str,
        filing: dict,
        include_r_pages: bool = False,
        force: bool = False,
        offline: bool = False,
    ) -> dict:
        accession, period = filing["accessionNumber"], filing["reportDate"]
        saved = self.read(ticker)
        existing = saved["packages"].get(accession)
        if offline:
            if not existing:
                raise ValueError(ticker + " 缺申報包 cache：" + accession)
            for document in existing["documents"].values():
                self.cache.body(document)
            complete = existing["complete"] and not (include_r_pages and self.missing_r_pages(existing))
            return dict(existing, status="offline_cache" if complete else "offline_incomplete")
        base = self.base_url(filing)
        index_url = self.filing_index_url(filing)
        reuse = existing if existing and not force else None
        fetched = 0
        if reuse:
            for receipt in reuse["index_receipts"].values():
                self.cache.body(receipt)
            directory, index_receipts = reuse["directory"], reuse["index_receipts"]
            subdirectories = reuse.get("subdirectories", [])
            types = FilingIndexPage.document_types(self.cache.body(index_receipts["index_htm"]))
        else:
            listing_url = base + "index.json"
            listing = self.http.get(listing_url, "json")
            page = self.http.get(index_url, "html")
            fetched += 2
            index_receipts = {
                "index_json": self.cache.capture(
                    ticker, period, accession, listing, "sec_json", listing_url
                ),
                "index_htm": self.cache.capture(
                    ticker, period, accession, page, "original_html", index_url
                ),
            }
            items = json.loads(listing)["directory"]["item"]
            directory = [item["name"] for item in items]
            subdirectories = [item["name"] for item in items if item.get("type") == "dir"]
            types = FilingIndexPage.document_types(page)
        package = {
            "filing": filing,
            "filing_index_url": index_url,
            "index_receipts": index_receipts,
            "directory": directory,
            "subdirectories": subdirectories,
            "documents": dict(reuse["documents"]) if reuse else {},
            "skipped": {},
            "failures": {},
            "complete": False,
            "updated_at_utc": utc_now(),
        }
        try:
            for name in directory:
                if name in package["documents"]:
                    self.cache.body(package["documents"][name])
                    continue
                reason = self.classify(filing, name, include_r_pages, name in subdirectories)
                if reason:
                    package["skipped"][name] = reason
                    continue
                url = base + quote(name)
                is_html = name.lower().endswith((".htm", ".html"))
                try:
                    raw = self.http.get(url, "html" if is_html else "file")
                    fetched += 1
                    inline = is_html and is_inline_xbrl(raw)
                    metadata = {
                        "source_url": url,
                        "filing_index_url": index_url,
                        "ixviewer_url": self.ixviewer_url(filing, name) if inline else None,
                    }
                    receipt = self.files.capture(ticker, period, accession, raw, name, metadata)
                except FILE_ERRORS as error:
                    if is_blocking(error):
                        raise
                    package["failures"][name] = {"url": url, "error": f"{type(error).__name__}: {error}"}
                    continue
                package["documents"][name] = dict(
                    receipt,
                    name=name,
                    type=types.get(name, {}).get("type", ""),
                    description=types.get(name, {}).get("description", ""),
                    primary=name == filing["primaryDocument"],
                    inline_xbrl=inline,
                )
            package["complete"] = not package["failures"]
        finally:
            # 中斷（SEC 拒絕、Ctrl-C 等）時也保存已下載檔案的收據，重跑只補缺的檔案。
            package["updated_at_utc"] = utc_now()
            saved["packages"][accession] = package
            self.cache.write(ticker, "packages", saved)
        if not package["complete"]:
            status = "incomplete"
        else:
            status = "cache_hit" if fetched == 0 else "downloaded"
        return dict(package, status=status)

    @classmethod
    def summary(cls, package: dict) -> dict:
        filing = package["filing"]
        return {
            "accession": filing["accessionNumber"],
            "form": filing["original_form"],
            "period_end": filing["reportDate"],
            "filing_date": filing["filingDate"],
            "status": package["status"],
            "complete": package["status"] in ("downloaded", "cache_hit", "offline_cache"),
            "documents": len(package["documents"]),
            "r_pages_skipped": len(cls.missing_r_pages(package)),
            "failures": sorted(package["failures"]),
        }


class DownloadWorkflow:
    """下載一組 ticker 的完整申報包；任一錯誤直接拋出，批次隔離由 DownloadBatch 負責。

    每家公司下載目標期別、Q4 依賴期別與財報新聞稿 8-K 的申報包。`dry_run=True` 只讀本機 catalog 與 packages.json，
    列出還沒下載完整的申報，不發網路請求、不寫入任何檔案。
    """

    initial_status = "loading_catalog"

    def __init__(
        self,
        repository: Path,
        data: Path,
        http: SecHttpClient | None = None,
        progress: Callable[[dict], None] | None = None,
        include_r_pages: bool = False,
        tickers_csv: Path | None = None,
    ):
        self.repository = repository
        self.progress = progress
        self.cache = WorkflowCache(data)
        self.http = http or SecHttpClient()
        self.catalog = SecFilingCatalog(self.cache, self.http)
        self.ciks = CikResolver(self.cache, self.http, tickers_csv)
        self.packages = FilingPackages(self.cache, self.http)
        self.include_r_pages = include_r_pages

    def notify(self, ticker: str, status: str, period: str = ""):
        if self.progress:
            self.progress({"ticker": ticker, "period": period, "status": status})

    def run(
        self,
        tickers: list[str],
        selection: PeriodSelection,
        force: bool = False,
        offline: bool = False,
        dry_run: bool = False,
    ) -> dict:
        if force and offline:
            raise ValueError("--force 與 --offline 不可同時使用")
        report = {"stage": "download", "companies": []}
        for ticker in tickers:
            report["companies"].append(self.company(ticker, selection, force, offline, dry_run))
        return report

    def company(self, ticker: str, selection: PeriodSelection, force: bool, offline: bool, dry_run: bool = False) -> dict:
        if dry_run:
            return self.missing(ticker, selection)
        self.notify(ticker, self.initial_status)
        cik = self.ciks.resolve(ticker, offline)
        load = dict(refresh=force or selection.latest, offline=offline, need_items=True)
        filings = self.catalog.load(ticker, cik["ciks"], selection, **load)
        targets = self.targets(filings, selection)
        items = self.catalog.items(ticker)
        unknown = [f for f in release_window(filings, targets, selection) if f["accessionNumber"] not in items]
        if unknown and not offline:
            # 舊 catalog 的歷史分頁沒有 item 代碼：補抓全部歷史分頁，不把缺資料當成非 2.02。
            filings = self.catalog.load(ticker, cik["ciks"], selection, **dict(load, full_history=True))
            targets = self.targets(filings, selection)
            items = self.catalog.items(ticker)
            unknown = [f for f in release_window(filings, targets, selection) if f["accessionNumber"] not in items]
        dependencies = q4_dependencies(filings, targets)
        company = {
            "ticker": ticker,
            "cik": cik,
            "catalog_source": self.catalog.last_source,
            "target_periods": [f["reportDate"] for f in targets],
            "dependency_periods": dependencies["periods"],
        }
        if dependencies["unresolved"]:
            company["dependencies_unresolved"] = dependencies["unresolved"]
        if unknown:
            company["eight_k_items_missing"] = sorted(f["accessionNumber"] for f in unknown)
        wanted = package_filings(filings, targets, dependencies["periods"]) + earnings_releases(filings, items, targets, selection)
        packages = []
        for filing in sorted({f["accessionNumber"]: f for f in wanted}.values(), key=lambda f: (f["filingDate"], f["accessionNumber"])):
            package = self.packages.download(ticker, filing, self.include_r_pages, force, offline)
            packages.append(package)
            self.notify(ticker, "package_" + package["status"], filing["reportDate"])
        company["packages"] = [self.packages.summary(p) for p in packages]
        return company

    def missing(self, ticker: str, selection: PeriodSelection) -> dict:
        """只讀本機資料，列出目標期別與 Q4 依賴期別中沒有完整申報包的 10-K／10-Q。"""
        cached = self.cache.read(ticker, "catalog")
        if not cached:
            return {"ticker": ticker, "dry_run": True, "error": "沒有本機 catalog；先線上 download"}
        filings = cached["filings"]
        try:
            targets = self.targets(filings, selection)
        except ValueError as error:
            return {"ticker": ticker, "dry_run": True, "error": str(error)}
        dependencies = q4_dependencies(filings, targets)
        saved = self.packages.read(ticker)["packages"]
        target_periods = {f["reportDate"] for f in targets}

        def absent(periods) -> list[dict]:
            rows = []
            for filing in package_filings(filings, targets if periods is None else [], periods or []):
                package = saved.get(filing["accessionNumber"])
                if package and package["complete"]:
                    continue
                rows.append(
                    {
                        "accession": filing["accessionNumber"],
                        "form": filing.get("original_form", filing["form"]),
                        "period_end": filing["reportDate"],
                        "filing_date": filing["filingDate"],
                        "state": "incomplete" if package else "not_downloaded",
                    }
                )
            return rows

        result = {
            "ticker": ticker,
            "dry_run": True,
            "target_periods": sorted(target_periods),
            "dependency_periods": dependencies["periods"],
            "missing_targets": absent(None),
            "missing_dependencies": absent(dependencies["periods"]),
        }
        if dependencies["unresolved"]:
            result["dependencies_unresolved"] = dependencies["unresolved"]
        return result

    @staticmethod
    def targets(filings: list[dict], selection: PeriodSelection) -> list[dict]:
        """目標期別：範圍內每期一份 10-K／10-Q（修訂版優先）。"""
        targets = selection.choose([f for f in filings if f["form"] in PERIODIC_FORMS])
        if not targets:
            raise ValueError("指定期間沒有 SEC 10-K／10-Q")
        return targets


class DownloadBatch:
    """逐家下載：一家失敗不中止整批；SEC 拒絕（403／429）或缺 SEC_USER_AGENT 時整批停止。"""

    def __init__(self, workflow: DownloadWorkflow):
        self.workflow = workflow

    def run(
        self,
        tickers: list[str],
        selection: PeriodSelection,
        force: bool = False,
        offline: bool = False,
    ) -> dict:
        if force and offline:
            raise ValueError("--force 與 --offline 不可同時使用")
        report = {
            "stage": "download",
            "companies": [],
            "succeeded": [],
            "failed": [],
            "not_attempted": [],
            "stopped": None,
        }
        for position, ticker in enumerate(tickers):
            try:
                company = self.workflow.run([ticker], selection, force, offline)["companies"][0]
            except Exception as error:
                # 非預期例外也只讓這家失敗並保留原因；SEC 拒絕或缺身分時整批停止。
                report["failed"].append({"ticker": ticker, "error": f"{type(error).__name__}: {error}"})
                self.workflow.notify(ticker, "failed")
                if is_blocking(error):
                    report["stopped"] = f"{ticker}: {error}"
                    report["not_attempted"] = tickers[position + 1 :]
                    break
                continue
            report["companies"].append(company)
            problems = [
                f"{p['accession']} {p['status']}" for p in company.get("packages", []) if not p["complete"]
            ]
            if problems:
                problems = ["申報包未完成：" + ", ".join(problems)]
            if company.get("eight_k_items_missing"):
                problems.append(
                    "8-K item 代碼不明，無法判斷是否為財報新聞稿：" + ", ".join(company["eight_k_items_missing"])
                )
            if problems:
                report["failed"].append({"ticker": ticker, "error": "；".join(problems)})
            else:
                report["succeeded"].append(ticker)
        report["complete"] = not report["failed"] and not report["not_attempted"]
        return report
