"""讀取 `data/revenue/` 的正式輸出，整理成 viewer 使用的格式；唯讀，不執行 parser。

正式輸出的目錄配置是 `<首字母>/<TICKER>/Q/<期末日>/`、`FY/<期末日>/`，`status.json` 的 `periods` 分成 `Q` 與 `FY`
（格式見 `docs/architecture/parser.md`）。每期合併 `status.json` 的紀錄與該期的 `revenue.json`；失敗或不推算而保留先前
上線輸出的期別，兩者都有。

每個運算元的證據表格檔以 `revenue.json` 記錄的 sha256 核對，缺檔或 hash 不符時附原因，不當作正常證據。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .evidence import FILE_NAME_RE
from .universe import TICKER_RE, UniverseError, load_tickers

SERIES = ("Q", "FY")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class PublishedRevenue:
    """`root` 是正式輸出根目錄（`data/revenue/`）；`universe` 是 `tickers.csv` 路徑，省略時用預設位置。"""

    def __init__(self, root: Path, universe: Path | None = None):
        self.root = Path(root)
        self.universe = universe

    def companies(self) -> list[dict]:
        """`tickers.csv` 的公司加上有輸出目錄的公司；`listed` 為 `status=ok`，`has_output` 為有輸出目錄。"""
        try:
            entries = {e.ticker: e for e in load_tickers(self.universe)}
        except UniverseError:
            entries = {}
        outputs = set(self.output_tickers())
        names = sorted(set(entries) | outputs)
        return [
            {
                "ticker": name,
                "name": entries[name].name if name in entries else "",
                "universe_status": entries[name].status if name in entries else None,
                "listed": name in entries and entries[name].status == "ok",
                "has_output": name in outputs,
            }
            for name in names
        ]

    def output_tickers(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return [
            d.name
            for letter in self.root.iterdir()
            if letter.is_dir() and len(letter.name) == 1
            for d in letter.iterdir()
            if d.is_dir() and TICKER_RE.fullmatch(d.name) and d.name[0] == letter.name
        ]

    def known(self, ticker: str) -> bool:
        return bool(TICKER_RE.fullmatch(ticker)) and any(
            c["ticker"] == ticker for c in self.companies()
        )

    def ticker_dir(self, ticker: str) -> Path:
        return self.root / ticker[0].upper() / ticker

    def period_dir(self, ticker: str, series: str, period: str) -> Path | None:
        """該期有 `revenue.json` 時的輸出目錄。"""
        directory = self.ticker_dir(ticker) / series / period
        return directory if (directory / "revenue.json").is_file() else None

    def company(self, ticker: str) -> dict | None:
        """一家公司的兩個序列與無法做比較欄比對的申報（`comparison_errors`）。沒有輸出目錄時回傳 None。"""
        base = self.ticker_dir(ticker)
        if not base.is_dir():
            return None
        status = self.read_json(base / "status.json") or {}
        periods = status.get("periods") or {}
        records = {
            s: {k: v for k, v in (periods.get(s) or {}).items() if DATE_RE.fullmatch(k)} for s in SERIES
        }
        series = {}
        for name in SERIES:
            found = set(records[name])
            if (base / name).is_dir():
                found |= {
                    d.name
                    for d in (base / name).iterdir()
                    if DATE_RE.fullmatch(d.name) and (d / "revenue.json").is_file()
                }
            series[name] = [
                self.period(ticker, name, period, records[name].get(period))
                for period in sorted(found)
            ]
        view = status.get("view") or next(
            (p["revenue"]["view"] for s in series.values() for p in s if p["revenue"]), None
        )
        return {
            "ticker": ticker,
            "view": view,
            "parser": status.get("parser"),
            "comparison_errors": status.get("comparison_errors") or [],
            "series": series,
        }

    def period(self, ticker: str, series: str, period: str, record: dict | None) -> dict:
        record = dict(record or {})
        directory = self.period_dir(ticker, series, period)
        revenue = self.read_json(directory / "revenue.json") if directory else None
        if revenue is not None:
            revenue["evidence_files"] = self.evidence_files(revenue, directory)
        status = record.get("status") or ("published" if revenue else "unknown")
        return {
            "period_end": period,
            "status": status,
            "fiscal_year": record.get("fiscal_year", (revenue or {}).get("fiscal_year")),
            "fiscal_quarter": record.get("fiscal_quarter", (revenue or {}).get("fiscal_quarter")),
            "record": record,
            "revenue": revenue,
        }

    @staticmethod
    def evidence_files(revenue: dict, directory: Path) -> dict:
        """每張證據表格的檔名與核對結果，以表格鍵（`<accession>-<sha12>-t<N>`）為鍵。

        同一張表由多個運算元引用時，每個運算元記錄的 sha256 都要與檔案相符。
        """
        recorded: dict[str, list[tuple[str, dict]]] = {}
        for operand_id, operand in (revenue.get("operands") or {}).items():
            evidence = operand.get("evidence") or {}
            if evidence.get("table"):
                recorded.setdefault(evidence["table"], []).append((operand_id, evidence))
        tables = {}
        for key, members in recorded.items():
            problems = []
            for kind in ("png", "html"):
                name = f"{key}.{kind}"
                path = directory / "evidence" / name
                if not FILE_NAME_RE.fullmatch(name) or not path.is_file():
                    problems.append(f"缺少 {name}")
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                mismatched = [op for op, evidence in members if evidence.get(f"{kind}_sha256") != digest]
                if mismatched:
                    problems.append(f"{name} 的 hash 與 revenue.json 中 {'、'.join(mismatched)} 的紀錄不同")
            tables[key] = {"png": f"{key}.png", "html": f"{key}.html", "problems": problems}
        return tables

    def evidence_file(self, ticker: str, series: str, period: str, name: str) -> Path | None:
        """證據目錄內符合命名規則的表格檔；其他路徑一律回傳 None。"""
        if (
            not self.known(ticker)
            or series not in SERIES
            or not DATE_RE.fullmatch(period)
            or not FILE_NAME_RE.fullmatch(name)
        ):
            return None
        directory = self.period_dir(ticker, series, period)
        if directory is None:
            return None
        root = self.root.resolve()
        file = (directory / "evidence" / name).resolve()
        return file if file.is_relative_to(root) and file.is_file() else None

    @staticmethod
    def read_json(path: Path) -> dict | None:
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None
