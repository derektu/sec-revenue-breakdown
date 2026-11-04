#!/usr/bin/env python3
"""離線重播單一或全部公司；完全不讀回歸期望值或 vendor。"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.service import ReplayService


class ReplayCli:
    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument("ticker", help="ticker 或 ALL")
        cli.add_argument("--out", type=Path, default=Path("data"))
        args = cli.parse_args()
        service = ReplayService(Path(__file__).resolve().parents[1], args.out)
        for ticker in (
            service.registry.entries if args.ticker == "ALL" else [args.ticker.upper()]
        ):
            rows = service.replay(ticker)
            observed = sum(
                o["status"] == "observed" for r in rows for o in r["outputs"].values()
            )
            print(ticker, len(rows), observed)


if __name__ == "__main__":
    ReplayCli().run()
