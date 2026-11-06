"""完整申報包：filing index、檔案清單與每份文件的下載、收據與 URL。"""

from __future__ import annotations

import http.client
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from lxml import etree, html as lxml_html
from lxml.etree import LxmlError

from .http import SecHttpClient, is_blocking
from .store import RawFileStore, WorkflowCache, utc_now

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
INLINE_XBRL_NAMESPACE = "http://www.xbrl.org/2013/inlineXBRL"
DOCUMENT_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
FILE_ERRORS = (HTTPError, URLError, OSError, ValueError, http.client.HTTPException, LxmlError)
RENDERING_RE = re.compile(
    r"R\d+\.(?:htm|xml)|Financial_Report\.xlsx?|report\.css|Show\.js|MetaLinks\.json",
    re.I,
)


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
