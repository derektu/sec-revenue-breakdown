#!/usr/bin/env python3
"""download → parse → viewer；各階段可獨立執行。

download 下載任何 ticker 的完整 SEC 申報包；parse 依 `libs/sec_revenue/companies/` 的公司 parser 產生 `data/revenue/`
的正式輸出與證據；viewer 唯讀顯示正式輸出。snapshot 由原文產生 `data/snapshots/` 的 XBRL fact 快照與申報清單，
沒有原文時以 `parse --check --snapshots` 驗證正式輸出。
"""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.common.dotenv import load_dotenv
from sec_revenue.common.periods import PeriodSelection
from sec_revenue.download.workflow import DownloadBatch, DownloadWorkflow
from sec_revenue.download.tickers import DownloadTickers
from sec_revenue.universe import parse_tickers
from sec_revenue.viewer.server import RevenueViewer
from sec_revenue import companies
from sec_revenue.revenue.engine import DEFAULT_START, SERIES, RevenueParser, check_outputs
from sec_revenue.revenue import snapshot

REVENUE_ROOT = ROOT / "data" / "revenue"
SNAPSHOT_ROOT = ROOT / "data" / "snapshots"


def data_root() -> Path:
    """SEC 原文與流程產物的根目錄：`SEC_DATA_DIR`（可放在 `.env`），未設定時為 repo 的 `data/`。"""
    configured = os.environ.get("SEC_DATA_DIR", "").strip()
    return Path(configured).expanduser() if configured else ROOT / "data"


class WorkflowCli:
    def __init__(self):
        # 這次要報出的載入失敗的 parser.py：（名稱, 含檔案路徑的錯誤訊息），由 `company_tickers` 填入。
        self.failures: list[tuple[str, str]] = []

    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        commands = cli.add_subparsers(dest="command", required=True)
        listing = commands.add_parser("tickers", help="列出有公司 parser 的 ticker")
        listing.add_argument("--json", action="store_true")
        download = commands.add_parser("download", help="下載 SEC 申報包")
        download.add_argument("--tickers", nargs="+", help="AAPL MSFT 或 AAPL,MSFT；ALL 是 Allstate 的 ticker")
        download.add_argument("--all", dest="all_tickers", action="store_true", help="tickers.csv 的全部公司；與 --from-manifest 一起用時為有申報清單的公司")
        download.add_argument("--ticker-file", type=Path, help="一行一個 ticker，或 JSON 字串清單")
        download.add_argument("--start", help="包含起日，實際 SEC reportDate YYYY-MM-DD")
        download.add_argument("--end", help="包含迄日")
        download.add_argument("--latest", action="store_true", help="刷新 SEC 清單；沒有日期範圍時只選最新一期")
        download.add_argument("--force", action="store_true", help="強制重抓")
        download.add_argument("--offline", action="store_true", help="只允許 local cache，禁止網路")
        download.add_argument(
            "--include-r-pages",
            action="store_true",
            help="一併下載 XBRL R 頁面與其呈現檔；預設略過，之後加此參數重跑可補抓",
        )
        download.add_argument(
            "--dry-run",
            action="store_true",
            help="只讀本機 catalog 與申報包，列出目標期別與 Q4 依賴期別中還沒下載完整的申報，以及 catalog 未涵蓋的範圍；不連網、不寫入，有缺漏時回傳 2",
        )
        download.add_argument(
            "--from-manifest",
            action="store_true",
            help="依 data/snapshots/ 的申報清單下載每份申報包並逐檔核對 sha256；不查 SEC 申報清單、不選期別。--all 為有申報清單的公司",
        )
        download.add_argument("--data", type=Path, default=data_root(), help="資料根目錄（預設 SEC_DATA_DIR 或 repo 的 data/）")
        download.add_argument("--snapshots-dir", type=Path, default=SNAPSHOT_ROOT, help=argparse.SUPPRESS)
        parse = commands.add_parser("parse", help="依公司 parser 產生 data/revenue/ 的正式輸出")
        parse.add_argument("--tickers", nargs="+", help="AAPL MSFT 或 AAPL,MSFT；省略或 --all 為全部有公司 parser 的公司")
        parse.add_argument("--all", dest="all_tickers", action="store_true", help="全部有公司 parser 的公司")
        parse.add_argument("--start", help=f"包含起日（期末日 YYYY-MM-DD）；省略時從預設起始日 {DEFAULT_START} 起，可以早於預設值")
        parse.add_argument("--end", help="包含迄日")
        parse.add_argument(
            "--check",
            action="store_true",
            help="在已提交輸出的副本上照一般 parse 執行並逐欄比對，不寫入、不啟動 Chromium；省略期別時比對 status.json 列出的期別",
        )
        parse.add_argument(
            "--snapshots",
            action="store_true",
            help="與 --check 一起使用：申報與 fact 讀 data/snapshots/ 的快照，不需要 SEC 原文；證據沿用已提交的表格檔",
        )
        parse.add_argument(
            "--republish",
            nargs=3,
            action="append",
            metavar=("TICKER", "SERIES", "PERIOD"),
            default=[],
            help="由人決定後覆寫已上線的期別；SERIES 是 Q 或 FY，可重複指定。未指定時已上線期別不會被改動",
        )
        parse.add_argument("--data", type=Path, default=data_root(), help="SEC 原文的資料根目錄（預設 SEC_DATA_DIR 或 repo 的 data/）")
        parse.add_argument("--out", type=Path, default=REVENUE_ROOT, help=argparse.SUPPRESS)
        parse.add_argument("--snapshots-dir", type=Path, default=SNAPSHOT_ROOT, help=argparse.SUPPRESS)
        snap = commands.add_parser("snapshot", help="由 SEC 原文產生 data/snapshots/ 的 XBRL fact 快照與申報清單")
        snap.add_argument("--tickers", nargs="+", help="AAPL MSFT 或 AAPL,MSFT；省略或 --all 為全部有公司 parser 的公司")
        snap.add_argument("--all", dest="all_tickers", action="store_true", help="全部有公司 parser 的公司")
        snap.add_argument("--check", action="store_true", help="不寫入，核對已提交的快照與申報清單是否與原文重新產生的結果相同")
        snap.add_argument("--data", type=Path, default=data_root(), help="SEC 原文的資料根目錄（預設 SEC_DATA_DIR 或 repo 的 data/）")
        snap.add_argument("--out", type=Path, default=SNAPSHOT_ROOT, help=argparse.SUPPRESS)
        viewer = commands.add_parser("viewer", help="本機唯讀 viewer")
        viewer.add_argument("--host", default="127.0.0.1")
        viewer.add_argument("--port", type=int, default=7290)
        viewer.add_argument("--revenue", type=Path, default=REVENUE_ROOT, help="正式輸出根目錄（預設 repo 的 data/revenue/）")
        args = cli.parse_args()
        try:
            if args.command == "tickers":
                names, failures = companies.scan()
                print(json.dumps(names) if args.json else "\n".join(names))
                if failures:
                    self.report_broken([f"{error.ticker}：{error}" for error in failures])
                    return 2
                return 0
            if args.command == "viewer":
                server = RevenueViewer(args.revenue).server(args.host, args.port)
                print(f"Viewer http://{args.host}:{server.server_port}", flush=True)
                server.serve_forever()
                return 0
            if args.command == "parse":
                return self.parse(args)
            if args.command == "snapshot":
                return self.snapshot(args)
            periods = PeriodSelection(args.start, args.end, args.latest)
            if args.from_manifest and args.all_tickers:
                listed = sorted(p.parent.name for p in args.snapshots_dir.glob(f"*/*/{snapshot.MANIFEST}"))
                named = DownloadTickers().select(args.tickers, args.ticker_file) if args.tickers or args.ticker_file else []
                tickers = list(dict.fromkeys(listed + named))
            else:
                tickers = DownloadTickers().select(args.tickers, args.ticker_file, args.all_tickers)
            if args.from_manifest and (args.dry_run or args.start or args.end or args.latest):
                raise ValueError("--from-manifest 依申報清單下載，不能與 --dry-run、--start、--end、--latest 同時使用")
            workflow = DownloadWorkflow(
                ROOT,
                args.data,
                progress=self.progress,
                include_r_pages=args.include_r_pages,
                manifests=args.snapshots_dir if args.from_manifest else None,
            )
            if args.dry_run:
                result = workflow.run(tickers, periods, dry_run=True)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result["complete"] else 2
            result = DownloadBatch(workflow).run(tickers, periods, args.force, args.offline)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("complete", True) else 2
        except (ValueError, KeyError, OSError) as error:
            print(f"{args.command} 失敗：{error}", file=sys.stderr)
            return 1

    def company_tickers(self, args) -> list[str]:
        """這次處理的 ticker，以及要報出的載入失敗（`self.failures`，由 `unloaded` 記為錯誤）。

        全部處理時報出每一個載入失敗的 `parser.py`；指定 ticker 時報出名稱（見 `companies.ParserLoadError`）與指定
        ticker 相同的載入失敗，名稱與正常的 ticker 相同時也報出。指定的 ticker 有 `parser.py`、但載入失敗時的名稱
        不是它（例如讀不到 `TICKER`），由 `load` 報出檔案與錯誤。
        """
        names = parse_tickers(args.tickers)
        available = companies.tickers()
        everything = args.all_tickers or not names
        if everything:
            names = list(dict.fromkeys(available + names))
        self.failures = [(e.ticker, str(e)) for e in companies.load_failures() if everything or e.ticker in names]
        failed = {label for label, _ in self.failures}
        unknown = [
            n for n in names
            if n not in available and n not in failed and not (companies.module_dir(n) / "parser.py").exists()
        ]
        if unknown:
            raise ValueError("沒有公司 parser：" + ", ".join(unknown))
        return [n for n in names if n in available or n not in failed]

    def unloaded(self, entries: list, broken: list[str], **fields):
        """把 `self.failures` 記為錯誤：每筆一個輸出條目（另加 `fields`）與一行 `broken`。"""
        for label, error in self.failures:
            self.progress({"ticker": label, "status": "parser_invalid"})
            broken.append(f"{label}：{error}")
            entries.append({"ticker": label, **fields, "error": error})

    def snapshot(self, args) -> int:
        names = self.company_tickers(args)
        results, differences, broken = [], [], []
        self.unloaded(results, broken)
        for ticker in names:
            source, error = self.load(ticker)
            if error is not None:
                broken.append(f"{ticker}：{error}")
                results.append({"ticker": ticker, "error": error})
                continue
            # 公司 parser 宣告附件（ATTACHMENTS）時，快照涵蓋這些附件。
            if args.check:
                found = snapshot.check(args.data, args.out, ticker, source.attachments)
                differences += found
                results.append({"ticker": ticker, "differences": found})
            else:
                results.append(snapshot.write(args.data, args.out, ticker, source.attachments))
            self.progress({"ticker": ticker, "status": "snapshot_checked" if args.check else "snapshot_written"})
        print(json.dumps({"stage": "snapshot", "check": args.check, "companies": results}, ensure_ascii=False, indent=2))
        if broken:
            self.report_broken(broken)
        if differences:
            print("\n".join(["快照與原文重新產生的結果不同："] + differences), file=sys.stderr)
        unreadable = [f"{r['ticker']} {a}" for r in results for a in r.get("errors", [])]
        if unreadable:
            print("\n".join(["原文讀不到，快照記錄為錯誤："] + unreadable), file=sys.stderr)
        return 2 if differences or broken or unreadable else 0

    def parse(self, args) -> int:
        PeriodSelection(args.start, args.end)
        names = self.company_tickers(args)
        if args.snapshots and not args.check:
            raise ValueError("--snapshots 沒有原文，無法產生證據，只能與 --check 一起使用")
        republish = {}
        for ticker, series, period in args.republish:
            ticker, series = ticker.upper(), series.upper()
            PeriodSelection(period, period)
            if ticker not in names:
                raise ValueError(f"--republish 的 {ticker} 不在這次處理的 ticker 中")
            if series not in SERIES:
                raise ValueError(f"--republish 的序列必須是 {'、'.join(SERIES)}，收到 {series}")
            republish.setdefault(ticker, set()).add((series, period))
        if args.check and republish:
            raise ValueError("--check 不寫入，不能與 --republish 同時使用")
        reports, differences, broken = [], [], []
        self.unloaded(reports, broken, complete=False)
        for ticker in names:
            source, error = self.load(ticker)
            if error is not None:
                broken.append(f"{ticker}：{error}")
                reports.append({"ticker": ticker, "complete": False, "error": error})
                continue
            if args.check:
                report, found = check_outputs(
                    args.data,
                    args.out,
                    source,
                    None,
                    args.start,
                    args.end,
                    progress=self.progress,
                    snapshots=args.snapshots_dir if args.snapshots else None,
                )
                report["differences"] = found
                differences += [f"{ticker} {d}" for d in found]
            else:
                parser = RevenueParser(
                    args.data, args.out, source, republish=republish.get(ticker, set()), progress=self.progress
                )
                periods = parser.periods(args.start, args.end)
                missing = sorted(p for p in republish.get(ticker, set()) if p[1] not in periods or p[0] not in parser.series_of(p[1]))
                if missing:
                    raise ValueError(f"--republish 的 {ticker} {missing} 不在這次處理的期別中")
                report = parser.run(periods)
            reports.append(report)
        print(json.dumps({"stage": "check" if args.check else "parse", "companies": reports}, ensure_ascii=False, indent=2))
        if broken:
            self.report_broken(broken)
        if differences:
            print("\n".join(["與已提交的輸出不同："] + differences), file=sys.stderr)
            return 2
        return 0 if all(r["complete"] for r in reports) else 2

    def load(self, ticker: str):
        """（公司 parser, None），或載入失敗、不合理時（None, 錯誤訊息）。載入失敗包括 `parser.py` 讀不進來與缺少
        `TICKER`、`VIEW`、`TOTAL`，訊息含檔案路徑；檢核含 VIEW 與自訂點的格式。這樣的 ticker 不處理，同一次執行的
        其他 ticker 照常處理，指令以結束碼 2 結束。"""
        try:
            return companies.parser_source(ticker), None
        except ValueError as error:
            self.progress({"ticker": ticker, "status": "parser_invalid"})
            return None, str(error)

    @staticmethod
    def report_broken(broken: list[str]):
        print("\n".join(["公司 parser 載入失敗或不合理，這些 ticker 沒有處理："] + broken), file=sys.stderr)

    def progress(self, event: dict):
        print(
            f"{event['ticker']} {event.get('period', '')} {event['status']}",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    raise SystemExit(WorkflowCli().run())
