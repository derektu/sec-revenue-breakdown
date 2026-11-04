"""表格來源的 hash 與格式檢查；不執行網頁程式。"""

from pathlib import Path
import gzip
import hashlib
import json
import re
from urllib.parse import urlsplit
from sec_revenue.engines import JsonCodec, EvidenceStore


class TableSourceReader:
    def __init__(self, repository: Path, output: Path):
        self.repository, self.output = repository, output
        self.receipts = []

    @staticmethod
    def sec_url(url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.netloc in ("www.sec.gov", "sec.gov")
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(r"/Archives/edgar/data/\d+/\d+/[^/]+", parsed.path)
            is not None
        )

    def read(self, entry: dict, ticker: str, kind: str) -> bytes:
        path = self.repository / entry["path"]
        compressed = path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != entry["sha256"]:
            raise ValueError("來源 hash 已改變：" + str(path))
        raw = gzip.decompress(compressed) if path.suffix == ".gz" else compressed
        if (
            entry.get("raw_sha256")
            and hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]
        ):
            raise ValueError("原始 bytes hash 不一致")
        url = entry.get("source_url", entry.get("url"))
        if not self.sec_url(url):
            raise ValueError("非 SEC 表格來源")
        digits = url.split("/")[-2]
        accession = digits[:10] + "-" + digits[10:12] + "-" + digits[12:]
        period = entry.get("reportDate")
        if not period:
            match = re.search(r"(20\d{2})(\d{2})(\d{2})", url.split("/")[-1])
            if not match:
                raise ValueError("來源日期不明")
            period = "-".join(match.groups())
        self.receipts.append(
            EvidenceStore(self.output / "sec").capture(
                ticker,
                period,
                accession,
                raw,
                kind,
                {
                    "source_url": url,
                    "original_path": entry["path"],
                    "original_container_sha256": entry["sha256"],
                },
            )
        )
        return raw

    def manifest(self, relative: str) -> dict:
        return JsonCodec.read(self.repository / relative)

    def observations(
        self,
        facts: list[dict],
        ticker: str,
        basis: str,
        labels: dict,
        periods: list[str],
        original_only: bool = False,
    ) -> list[dict]:
        """每個期別選最早已存來源；Q4 由同 scope FY−YTD9，不能補零。"""
        from sec_revenue.engines import QuarterEngine

        engine = QuarterEngine()
        rows = []
        for end in periods:
            by_kind = {}
            for kind, target in [("Q", end), ("FY", end), ("YTD9", end[:4] + "-09-30")]:
                candidates = [
                    f for f in facts if f.get("kind") == kind and f["enddate"] == target
                ]
                if original_only and kind == "Q":
                    candidates = [
                        f for f in candidates if f.get("source_report_date") == end
                    ]
                selected = []
                for label in {f["label"] for f in candidates}:
                    group = [f for f in candidates if f["label"] == label]
                    earliest = min(f["source_report_date"] for f in group)
                    selected.extend(
                        f for f in group if f["source_report_date"] == earliest
                    )
                by_kind[kind] = selected
            pool, conflicts = engine.quarter(
                by_kind["Q"] + by_kind["FY"], end, by_kind["YTD9"]
            )
            outputs = {}
            for label, reported in labels.items():
                found = [f for f in pool if f["label"] == reported]
                bad = any(f["label"] == reported for g in conflicts for f in g)
                outputs[label] = {
                    "status": (
                        "observed"
                        if len(found) == 1 and not bad
                        else "missing_or_ambiguous_table_row"
                    ),
                    "value_usd": (
                        found[0]["value"] if len(found) == 1 and not bad else None
                    ),
                    "SEC_operands": found if not bad else [],
                    "weights": [1] if len(found) == 1 else [],
                }
            rows.append(
                {
                    "ticker": ticker,
                    "period_end": end,
                    "period_kind": "Q",
                    "basis": basis,
                    "outputs": outputs,
                }
            )
        return rows


class HtmlTableAdapter:
    """原始 HTML 到內部 cell 結構；來源標記仍指向原始 bytes。"""

    def nonempty(self, raw: bytes, headings: list[str]) -> list[dict]:
        from lxml import html

        root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
        tables = []
        for index, table in enumerate(root.xpath("//table")):
            text = " ".join(table.itertext())
            if not any(heading in text for heading in headings):
                continue
            rows = []
            for row in table.xpath(".//tr"):
                cells = [
                    " ".join(cell.text_content().split())
                    for cell in row.xpath("./td|./th")
                ]
                cells = [cell for cell in cells if cell and cell != "$"]
                if cells:
                    rows.append(cells)
            tables.append({"index": index, "rows": rows})
        return tables
