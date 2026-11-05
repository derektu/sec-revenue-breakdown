#!/usr/bin/env python3
"""download → extract → viewer；各階段可獨立執行。

download 接受任何 ticker，下載完整申報包；extract 只處理 registry 有 parser 的公司。
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.dotenv import load_dotenv
from sec_revenue.download import DownloadBatch, DownloadWorkflow
from sec_revenue.tickers import DownloadTickers, SupportedTickers
from sec_revenue.workflow import PeriodSelection, ExtractionWorkflow
from sec_revenue.viewer import RevenueViewer


class WorkflowCli:
    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        commands = cli.add_subparsers(dest="command", required=True)
        listing = commands.add_parser("tickers", help="列出有 parser 的 ticker")
        listing.add_argument("--json", action="store_true")
        for command in ("download", "extract"):
            sub = commands.add_parser(command)
            sub.add_argument(
                "--tickers",
                nargs="+",
                help="AAPL MSFT 或 AAPL,MSFT；ALL 是 Allstate 的 ticker",
            )
            sub.add_argument(
                "--all",
                dest="all_tickers",
                action="store_true",
                help=(
                    "download：tickers.csv 的全部公司"
                    if command == "download"
                    else "extract：全部有 parser 的公司（省略 ticker 時同）"
                ),
            )
            sub.add_argument(
                "--ticker-file", type=Path, help="一行一個 ticker，或 JSON 字串清單"
            )
            sub.add_argument("--start", help="包含起日，實際 SEC reportDate YYYY-MM-DD")
            sub.add_argument("--end", help="包含迄日")
            sub.add_argument(
                "--latest",
                action="store_true",
                help="download：刷新 SEC 清單；沒有日期範圍時只選最新一期；extract：最新已下載目標期",
            )
            sub.add_argument(
                "--force",
                action="store_true",
                help="download 強制重抓；extract 強制重新萃取",
            )
            sub.add_argument("--data", type=Path, default=Path("data"))
            if command == "download":
                sub.add_argument(
                    "--offline",
                    action="store_true",
                    help="只允許 local cache，禁止網路",
                )
                sub.add_argument(
                    "--include-r-pages",
                    action="store_true",
                    help="一併下載 XBRL R 頁面與其呈現檔；預設略過，之後加此參數重跑可補抓",
                )
        viewer = commands.add_parser("viewer")
        viewer.add_argument("--data", type=Path, default=Path("data"))
        viewer.add_argument("--host", default="127.0.0.1")
        viewer.add_argument("--port", type=int, default=7290)
        args = cli.parse_args()
        try:
            roster = SupportedTickers()
            if args.command == "tickers":
                names = roster.select()
                print(json.dumps(names) if args.json else "\n".join(names))
                return 0
            if args.command == "viewer":
                server = RevenueViewer(args.data).server(args.host, args.port)
                print(f"Viewer http://{args.host}:{server.server_port}", flush=True)
                server.serve_forever()
                return 0
            periods = PeriodSelection(args.start, args.end, args.latest)
            repository = Path(__file__).resolve().parents[1]
            if args.command == "download":
                tickers = DownloadTickers().select(
                    args.tickers, args.ticker_file, args.all_tickers
                )
                workflow = DownloadWorkflow(
                    repository,
                    args.data,
                    progress=self.progress,
                    packages=True,
                    include_r_pages=args.include_r_pages,
                )
                result = DownloadBatch(workflow).run(
                    tickers, periods, args.force, args.offline
                )
            else:
                tickers = roster.select(args.tickers, args.ticker_file, args.all_tickers)
                result = ExtractionWorkflow(
                    repository, args.data, progress=self.progress
                ).run(tickers, periods, args.force)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("complete", True) else 2
        except (ValueError, KeyError, OSError) as error:
            print(f"{args.command} 失敗：{error}", file=sys.stderr)
            return 1

    def progress(self, event: dict):
        print(
            f"{event['ticker']} {event.get('period', '')} {event['status']}",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    raise SystemExit(WorkflowCli().run())
