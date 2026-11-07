"""由下載的申報包（`pipeline/<TICKER>/packages.json`）選每一期的主申報並載入 inline XBRL 主文件。

公司 parser 宣告附件類型（`ATTACHMENTS`，見 `source.py`）時，fact 清單另含同一份申報中這些附件的 inline XBRL
（`ixds.py`）；附件與主文件屬於同一份申報，申報日相同。

主申報是 reportDate 等於該期、申報日最早的 10-Q 或 10-K。修正申報（10-Q/A、10-K/A）不取代主申報：
它在原申報之後才公開，只參與比較欄比對，與已上線數字不同時寫成差異標記。

Point in time：選申報與列期別都可以指定 `as_of`（申報日），只考慮申報日當天或更早的申報。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from pathlib import Path

from ..common.jsonio import JsonCodec
from . import extract, ixds
from .xbrl import InlineDocument

ORIGINAL_FORMS = {"10-Q", "10-K"}
AMENDMENT_FORMS = {"10-Q/A", "10-K/A"}
# 主文件與附件合不成一份 fact 清單時的檢核名稱（見 `ixds.MergeError`）。
MERGE_CHECK = "fact 清單合併"


class ParseError(Exception):
    """該期無法產生正式輸出；訊息會寫進 status.json。"""

    def __init__(self, check: str, message: str):
        super().__init__(f"[{check}] {message}")
        self.check = check
        self.message = message


@dataclass(frozen=True)
class Filing:
    """一份申報：`document` 是主文件，`attachments` 是 fact 清單納入的附件（`ixds.attachment_records` 的欄位）。"""

    accession: str
    form: str
    report_date: str
    filing_date: str
    document: dict
    attachments: tuple[dict, ...] = ()

    def describe(self) -> dict:
        return {
            "accession": self.accession,
            "form": self.form,
            "report_date": self.report_date,
            "filing_date": self.filing_date,
        }

    def source(self, name: str | None = None) -> dict:
        """fact 所在的文件：`name` 為 None 是主文件，否則是同名的附件（`Fact.document`）。"""
        if name is None:
            return self.document
        found = [d for d in self.attachments if d["name"] == name]
        if len(found) != 1:
            raise ParseError("原文存在", f"{self.accession} 沒有附件 {name}")
        return found[0]

    def document_record(self, name: str | None = None) -> dict:
        document = self.source(name)
        return {
            "name": document["name"],
            "sha256": document["sha256"],
            "url": document["source_url"],
            "ixviewer_url": document.get("ixviewer_url"),
        }


def periodic_filing(accession: str, package: dict) -> Filing | None:
    """申報包是否為 parser 讀取的申報：10-Q、10-K 或其修訂版，申報包完整，且只有一份主文件、是 inline XBRL。

    快照模式以同一個函式篩選；它讀的申報包欄位由 `extract.package_record` 存進快照。
    """
    filing = package.get("filing", {})
    form = filing.get("form")
    if form not in ORIGINAL_FORMS | AMENDMENT_FORMS or not package.get("complete"):
        return None
    primary = [d for d in package["documents"].values() if d.get("primary")]
    if len(primary) != 1 or not primary[0].get("inline_xbrl"):
        return None
    return Filing(accession, form, filing["reportDate"], filing["filingDate"], primary[0])


class FilingSet:
    """一家公司已下載的 10-Q／10-K 申報與其主文件（讀取時核對 sha256）。

    `attachments` 是公司 parser 宣告的附件類型（`ParserSource.attachments`）；每份申報的 fact 清單另含這些類型的附件，
    沒有宣告時只取主文件。`snapshot` 為 False 表示文件來自原文；快照建立的子類別（`snapshot.SnapshotFilingSet`）為 True。
    """

    snapshot = False

    def __init__(self, data: Path, ticker: str, attachments: tuple[str, ...] = ()):
        self.root = data.resolve()
        self.attachment_types = tuple(attachments)
        path = self.root / "pipeline" / ticker / "packages.json"
        if not path.exists():
            raise ValueError(f"{ticker} 沒有已下載的申報包（{path}）；請先執行 download")
        self.packages = JsonCodec.read(path)["packages"]
        self.filings = sorted(
            (
                replace(f, attachments=tuple(ixds.attachment_records(package, self.attachment_types)))
                for accession, package in self.packages.items()
                if (f := periodic_filing(accession, package))
            ),
            key=lambda f: (f.filing_date, f.accession),
        )
        self.documents: dict[str, InlineDocument] = {}

    def visible(self, as_of: str | None) -> list[Filing]:
        return [f for f in self.filings if as_of is None or f.filing_date <= as_of]

    def periods(self, as_of: str | None = None) -> list[str]:
        return sorted({f.report_date for f in self.visible(as_of) if f.form in ORIGINAL_FORMS})

    def is_annual(self, period: str) -> bool:
        """該期的第一份原申報是 10-K。"""
        originals = [f for f in self.filings if f.report_date == period and f.form in ORIGINAL_FORMS]
        return bool(originals) and originals[0].form == "10-K"

    def raw(self, filing: Filing, name: str | None = None) -> bytes:
        """主文件（`name` 為 None）或附件 `name` 的原文，核對 sha256。"""
        document = filing.source(name)
        what = "主文件" if name is None else f"附件 {name}"
        relative = document["path"] if name is None else self.packages[filing.accession]["documents"][document["name"]]["path"]
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ParseError("原文存在", f"找不到 {filing.accession} 的{what} {relative}；請先執行 download")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != document["sha256"]:
            raise ParseError("原文存在", f"{filing.accession} {what} sha256 與申報包紀錄不符")
        return raw

    def extract(self, filing: Filing) -> tuple[dict, dict]:
        """（抽取內容, 文件名稱 → HTML 解析樹）；主文件的名稱是 None。

        沒有附件時是主文件的 `extract.extract`；有附件時由 `ixds.extract_set` 合併，合不成時以「fact 清單合併」結束。
        快照（`snapshot.build`）與 fact 清單（`document`）都經過這裡。
        """
        roots = {None: extract.parse_html(self.raw(filing))}
        for attachment in filing.attachments:
            roots[attachment["name"]] = extract.parse_html(self.raw(filing, attachment["name"]))
        if not filing.attachments:
            return extract.extract(roots[None]), roots
        try:
            return ixds.extract_set(roots[None], [(n, r) for n, r in roots.items() if n is not None]), roots
        except ixds.MergeError as error:
            raise ParseError(MERGE_CHECK, f"{filing.accession}：{error}") from error

    def document(self, filing: Filing) -> InlineDocument:
        if filing.accession not in self.documents:
            self.documents[filing.accession] = InlineDocument.from_extracted(*self.extract(filing))
        return self.documents[filing.accession]

    def select(self, period: str, as_of: str | None = None) -> Filing:
        """該期申報日最早的原申報；`as_of` 限定只看申報日不晚於它的申報。"""
        originals = [f for f in self.visible(as_of) if f.report_date == period and f.form in ORIGINAL_FORMS]
        if not originals:
            when = f"（申報日 {as_of} 以前）" if as_of else ""
            raise ParseError("選申報", f"沒有期末日為 {period} 的 10-Q 或 10-K{when}")
        return originals[0]
