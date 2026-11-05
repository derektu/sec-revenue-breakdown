"""由下載的申報包（`pipeline/<TICKER>/packages.json`）選每一期的主申報並載入 inline XBRL 主文件。

主申報是 reportDate 等於該期的第一份 10-Q 或 10-K。10-K/A、10-Q/A 只有含該期營收 facts
（規格宣告的任一 concept、期末日等於該期）時才取代原申報；有多份時取最晚的一份。
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from ..engines import JsonCodec
from .xbrl import InlineDocument

ORIGINAL_FORMS = {"10-Q", "10-K"}
AMENDMENT_FORMS = {"10-Q/A", "10-K/A"}


class ParseError(Exception):
    """該期無法產生正式輸出；訊息會寫進 status.json。"""

    def __init__(self, check: str, message: str):
        super().__init__(f"[{check}] {message}")
        self.check = check
        self.message = message


@dataclass(frozen=True)
class Filing:
    accession: str
    form: str
    report_date: str
    filing_date: str
    document: dict

    def describe(self) -> dict:
        return {
            "accession": self.accession,
            "form": self.form,
            "report_date": self.report_date,
            "filing_date": self.filing_date,
        }

    def document_record(self) -> dict:
        return {
            "name": self.document["name"],
            "sha256": self.document["sha256"],
            "url": self.document["source_url"],
            "ixviewer_url": self.document.get("ixviewer_url"),
        }


@dataclass(frozen=True)
class Selection:
    filing: Filing
    replaced: Filing | None = None


class FilingSet:
    """一家公司已下載的 10-Q／10-K 申報與其主文件（讀取時核對 sha256）。"""

    def __init__(self, data: Path, ticker: str):
        self.root = data.resolve()
        path = self.root / "pipeline" / ticker / "packages.json"
        if not path.exists():
            raise ValueError(f"{ticker} 沒有已下載的申報包（{path}）；請先執行 download")
        self.filings = []
        for accession, package in JsonCodec.read(path)["packages"].items():
            filing = package.get("filing", {})
            form = filing.get("form")
            if form not in ORIGINAL_FORMS | AMENDMENT_FORMS or not package.get("complete"):
                continue
            primary = [d for d in package["documents"].values() if d.get("primary")]
            if len(primary) != 1 or not primary[0].get("inline_xbrl"):
                continue
            self.filings.append(
                Filing(accession, form, filing["reportDate"], filing["filingDate"], primary[0])
            )
        self.filings.sort(key=lambda f: (f.filing_date, f.accession))
        self.documents: dict[str, InlineDocument] = {}
        self.selections: dict[tuple[str, frozenset], Selection] = {}

    def periods(self) -> list[str]:
        return sorted({f.report_date for f in self.filings if f.form in ORIGINAL_FORMS})

    def raw(self, filing: Filing) -> bytes:
        path = (self.root / filing.document["path"]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ParseError("原文存在", f"找不到 {filing.accession} 的主文件 {filing.document['path']}；請先執行 download")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != filing.document["sha256"]:
            raise ParseError("原文存在", f"{filing.accession} 主文件 sha256 與申報包紀錄不符")
        return raw

    def document(self, filing: Filing) -> InlineDocument:
        if filing.accession not in self.documents:
            self.documents[filing.accession] = InlineDocument(self.raw(filing))
        return self.documents[filing.accession]

    def select(self, period: str, concepts: set[str]) -> Selection:
        key = (period, frozenset(concepts))
        if key not in self.selections:
            self.selections[key] = self.choose(period, concepts)
        return self.selections[key]

    def choose(self, period: str, concepts: set[str]) -> Selection:
        """修正申報只要含該期任一營收 fact 就取代原申報；修正申報缺少的拆分會讓該期在組合時失敗，不回頭混用原申報。"""
        originals = [f for f in self.filings if f.report_date == period and f.form in ORIGINAL_FORMS]
        if not originals:
            raise ParseError("選申報", f"沒有期末日為 {period} 的 10-Q 或 10-K")
        original = originals[0]
        amendments = [
            f
            for f in self.filings
            if f.report_date == period
            and f.form in AMENDMENT_FORMS
            and any(fact.concept in concepts and fact.end == period for fact in self.document(f).facts)
        ]
        if amendments:
            return Selection(amendments[-1], original)
        return Selection(original)
