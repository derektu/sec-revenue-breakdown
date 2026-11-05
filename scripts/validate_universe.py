#!/usr/bin/env python3
"""驗證 ticker 清單與對照資料；逐項列出所有錯誤。全部通過回傳 0，有錯誤回傳 1。"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.universe import DEFAULT_UNIVERSE_DIR, validate_universe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--universe-dir",
        type=Path,
        default=DEFAULT_UNIVERSE_DIR,
        help="含 tickers.csv 與 references/ 的目錄（預設 data/universe）",
    )
    args = parser.parse_args(argv)
    errors = validate_universe(args.universe_dir)
    for error in errors:
        print(error)
    if errors:
        print(f"共 {len(errors)} 個錯誤", file=sys.stderr)
        return 1
    print(f"{args.universe_dir}: 通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
