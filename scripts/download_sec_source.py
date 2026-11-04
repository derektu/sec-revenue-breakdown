#!/usr/bin/env python3
"""單次 SEC 下載並保存真實 HTML 與來源 facts；不自動修改既有研究。"""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.engines import EvidenceStore, SecDownloadEngine, XbrlEngine, JsonCodec
from sec_revenue.service import ParserRegistry


class DownloadCli:
    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument("--ticker", required=True)
        cli.add_argument("--period", required=True)
        cli.add_argument("--accession", required=True)
        cli.add_argument("--url", required=True)
        cli.add_argument("--out", type=Path, default=Path("data"))
        args = cli.parse_args()
        ticker = args.ticker.upper()
        if ticker not in ParserRegistry().entries:
            cli.error("先登記 ticker parser")
        import datetime, re

        datetime.date.fromisoformat(args.period)
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", args.accession):
            cli.error("accession 格式不符")
        receipt = SecDownloadEngine(
            EvidenceStore(args.out / "sec"), os.environ.get("SEC_USER_AGENT", "")
        ).download(ticker, args.period, args.accession, args.url)
        # 非 inline XBRL 附件仍保留真實 HTML；不得假稱已產生 facts。
        try:
            facts = XbrlEngine().parse_html(
                Path(receipt["path"]).read_bytes(), args.url, args.accession
            )
        except ValueError as error:
            print("HTML 已保存；XBRL 擷取拒絕：" + str(error))
            return
        JsonCodec.write(
            Path(receipt["path"]).with_suffix(".facts.json"),
            {
                "source_receipt": receipt,
                "facts": facts,
                "status": "source_extraction_only_not_quarter_output",
            },
        )
        print(receipt["path"])


if __name__ == "__main__":
    DownloadCli().run()
