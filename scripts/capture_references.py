#!/usr/bin/env python3
"""擷取對照資料：開啟專用瀏覽器，確認登入後擷取指定 ticker 的 by segment 營收與證據。

    capture_references.py setup [--sources stockanalysis,futu,tradingview]
    capture_references.py capture --source stockanalysis --tickers AAPL,MSFT
    capture_references.py capture --source stockanalysis --tickers-file list.txt
    capture_references.py capture --source futu --tickers AAPL --periods 8 --headed

說明見 docs/architecture/capture.md。
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.capture.runner import DEFAULT_PAUSE, DEFAULT_PERIODS
from sec_revenue.capture.sites import SITES
from sec_revenue.universe import DEFAULT_UNIVERSE_DIR


def read_tickers(args) -> list[str]:
    tickers: list[str] = []
    if args.tickers:
        tickers += args.tickers.split(",")
    if args.tickers_file:
        for line in args.tickers_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0]
            tickers += line.replace(",", " ").split()
    seen: dict[str, None] = {}
    for ticker in tickers:
        if ticker.strip():
            seen.setdefault(ticker.strip().upper())
    return list(seen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="逐站檢查登入，未登入時等待使用者在視窗中登入")
    setup.add_argument("--sources", default=",".join(SITES), help="要檢查的來源，以逗號分隔（預設全部）")
    capture = commands.add_parser("capture", help="擷取指定 ticker 的對照資料")
    capture.add_argument("--source", required=True, choices=sorted(SITES))
    capture.add_argument("--tickers", help="以逗號分隔的 ticker")
    capture.add_argument("--tickers-file", type=Path, help="ticker 清單檔，以空白、逗號或換行分隔，# 之後為註解")
    capture.add_argument("--universe-dir", type=Path, default=DEFAULT_UNIVERSE_DIR)
    capture.add_argument("--periods", type=int, default=DEFAULT_PERIODS,
                         help=f"一個畫面只顯示一期的來源（富途）每檔擷取最近幾季範圍內的季度（預設 {DEFAULT_PERIODS}）")
    capture.add_argument("--pause", type=float, default=DEFAULT_PAUSE,
                         help=f"兩檔之間間隔的秒數（預設 {DEFAULT_PAUSE:g}）")
    capture.add_argument("--headed", action="store_true",
                         help="開視窗擷取；預設不開視窗，未登入時才開視窗登入")
    args = parser.parse_args(argv)

    if args.command == "setup":
        names = [name.strip() for name in args.sources.split(",") if name.strip()]
        unknown = [name for name in names if name not in SITES]
        if unknown:
            parser.error(f"未知的來源：{', '.join(unknown)}")
    else:
        tickers = read_tickers(args)
        if not tickers:
            parser.error("須以 --tickers 或 --tickers-file 指定至少一個 ticker")
        if args.periods < 1:
            parser.error("--periods 須為正整數")
        if args.pause < 0:
            parser.error("--pause 不可為負數")

    from playwright.sync_api import sync_playwright

    from sec_revenue.capture.browser import open_context
    from sec_revenue.capture.runner import ensure_login, report, run_capture

    with sync_playwright() as playwright:
        if args.command == "setup":
            context = open_context(playwright, headless=False)
            try:
                ok = ensure_login(context, [SITES[name] for name in names], input, print)
            finally:
                context.close()
            print("全部已登入" if ok else "仍有網站未登入")
            return 0 if ok else 1
        summary = run_capture(
            lambda headless: open_context(playwright, headless=headless),
            args.source,
            tickers,
            args.universe_dir,
            headless=not args.headed,
            periods=args.periods,
            pause=args.pause,
        )
        return report(summary, args.universe_dir)


if __name__ == "__main__":
    sys.exit(main())
