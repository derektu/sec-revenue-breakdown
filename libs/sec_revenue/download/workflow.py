"""下載一組 ticker：每家公司的目標、依賴與 8-K 申報包，以及逐家隔離的批次。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..common.jsonio import JsonCodec
from ..common.periods import PeriodSelection
from ..revenue.snapshot import MANIFEST, snapshot_dir
from .catalog import CikResolver, SecFilingCatalog
from .http import SecHttpClient, is_blocking
from .packages import RENDERING_RE, FilingPackages
from .plan import PERIODIC_FORMS, earnings_releases, package_filings, q4_dependencies, release_window
from .store import WorkflowCache


class DownloadWorkflow:
    """下載一組 ticker 的完整申報包；任一錯誤直接拋出，批次隔離由 DownloadBatch 負責。

    每家公司下載目標期別、Q4 依賴期別與財報新聞稿 8-K 的申報包。`dry_run=True` 只讀本機 catalog 與 packages.json，
    列出還沒下載完整的申報，不發網路請求、不寫入任何檔案。

    `manifests` 指定快照根目錄時改依申報清單（`<首字母>/<TICKER>/manifest.json`）下載：不查 SEC 申報清單、
    不選期別，下載清單列出的每份申報包，並逐檔核對 sha256。
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
        manifests: Path | None = None,
    ):
        self.repository = repository
        self.progress = progress
        self.cache = WorkflowCache(data)
        self.http = http or SecHttpClient()
        self.catalog = SecFilingCatalog(self.cache, self.http)
        self.ciks = CikResolver(self.cache, self.http, tickers_csv)
        self.packages = FilingPackages(self.cache, self.http)
        self.include_r_pages = include_r_pages
        self.manifests = manifests

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
        if dry_run:
            # 有任何一家需要處理（沒有 catalog、catalog 未涵蓋範圍、缺申報包）時不算完成。
            report["complete"] = not any(
                c.get("error") or c.get("catalog_incomplete") or c.get("missing_targets") or c.get("missing_dependencies")
                for c in report["companies"]
            )
        return report

    def company(self, ticker: str, selection: PeriodSelection, force: bool, offline: bool, dry_run: bool = False) -> dict:
        if dry_run:
            return self.missing(ticker, selection)
        if self.manifests is not None:
            return self.restore(ticker, force, offline)
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
        if dependencies["unresolved"] and not offline and not self.catalog.history_complete(ticker):
            # 依賴期別比目標早約 15 個月，可能在只抓 recent 的 catalog 之外：補抓全部歷史分頁再算一次。
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
        oldest = min((f["reportDate"] for f in filings if f["form"] in PERIODIC_FORMS), default="9999")
        bound = selection.start or selection.end
        uncovered = []
        if not cached.get("history_complete"):
            if bound and bound < oldest:
                uncovered.append(f"範圍起日 {bound} 早於本機 catalog 最舊的 10-K／10-Q 期別 {oldest}")
            uncovered += dependencies["unresolved"]
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
        if uncovered:
            result["catalog_incomplete"] = uncovered
        return result

    def restore(self, ticker: str, force: bool, offline: bool) -> dict:
        """依申報清單下載每份申報包，逐檔核對清單記錄的 sha256。

        缺檔或 sha256 不同的檔案列在 `manifest_mismatches`，並記成該申報包的失敗檔案：申報包標為不完整，parse 不讀它，
        之後重跑 download 會重新下載這些檔案。申報包有、清單沒列的檔案列在 `manifest_extra`，只回報不算失敗。
        """
        path = snapshot_dir(self.manifests, ticker) / MANIFEST
        if not path.exists():
            raise ValueError(f"{ticker} 沒有申報清單（{path}）")
        self.notify(ticker, "loading_manifest")
        company = {"ticker": ticker, "manifest": str(path), "packages": [], "manifest_mismatches": [], "manifest_extra": []}
        for entry in JsonCodec.read(path)["filings"]:
            filing = entry["filing"]
            accession = filing["accessionNumber"]
            # 清單列了 R 頁面時一併下載，才能逐檔核對。
            r_pages = self.include_r_pages or any(RENDERING_RE.fullmatch(name) for name in entry["documents"])
            package = self.packages.download(ticker, filing, r_pages, force, offline)
            self.notify(ticker, "package_" + package["status"], filing["reportDate"])
            bad = {}
            for name, expected in entry["documents"].items():
                found = package["documents"].get(name)
                if found is None:
                    bad[name] = "申報清單列出、申報包沒有這個檔案"
                elif found["sha256"] != expected["sha256"]:
                    bad[name] = "sha256 與申報清單不同"
            company["manifest_mismatches"] += [f"{accession} {name}：{reason}" for name, reason in bad.items()]
            company["manifest_extra"] += [f"{accession} {name}" for name in sorted(set(package["documents"]) - set(entry["documents"]))]
            if bad:
                package = self.reject(ticker, accession, bad)
            company["packages"].append(self.packages.summary(package))
        return company

    def reject(self, ticker: str, accession: str, bad: dict[str, str]) -> dict:
        """把與申報清單不符的檔案記成申報包的失敗檔案，申報包標為不完整。"""
        saved = self.packages.read(ticker)
        package = saved["packages"][accession]
        base = FilingPackages.base_url(package["filing"])
        for name, reason in bad.items():
            document = package["documents"].pop(name, None)
            package["failures"][name] = {"url": (document or {}).get("source_url", base + name), "error": reason}
        package["complete"] = False
        self.cache.write(ticker, "packages", saved)
        return dict(package, status="manifest_mismatch")

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
            if company.get("manifest_mismatches"):
                problems.append("與申報清單不符（申報包已標為不完整）：" + "；".join(company["manifest_mismatches"]))
            if company.get("dependencies_unresolved"):
                problems.append("Q4 依賴期別無法確定：" + "；".join(company["dependencies_unresolved"]))
            if problems:
                report["failed"].append({"ticker": ticker, "error": "；".join(problems)})
            else:
                report["succeeded"].append(ticker)
        report["complete"] = not report["failed"] and not report["not_attempted"]
        return report
