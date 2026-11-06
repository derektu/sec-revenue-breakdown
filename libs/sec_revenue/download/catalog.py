"""CIK 查詢與 SEC 申報清單（submissions recent 與歷史分頁，含 8-K item 代碼）。"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re

from ..common.jsonio import JsonCodec
from ..common.periods import PeriodSelection
from ..universe import load_tickers
from .http import SecHttpClient
from .plan import PERIODIC_FORMS
from .store import RawFileStore, WorkflowCache, utc_now

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_TICKERS_MAX_AGE = dt.timedelta(days=7)


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

    def history_complete(self, ticker: str) -> bool:
        """本機 catalog 是否已含全部歷史分頁。"""
        return bool((self.cache.read(ticker, "catalog") or {}).get("history_complete"))

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
