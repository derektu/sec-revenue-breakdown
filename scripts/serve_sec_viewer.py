#!/usr/bin/env python3
"""啟動唯讀 SEC viewer（雲端埠 8765）。"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.viewer import RevenueViewer


class ViewerCli:
    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument("--data", type=Path, default=Path("data"))
        cli.add_argument("--host", default="0.0.0.0")
        cli.add_argument("--port", type=int, default=8765)
        args = cli.parse_args()
        server = RevenueViewer(args.data).server(args.host, args.port)
        print(f"SEC viewer http://{args.host}:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    ViewerCli().run()
