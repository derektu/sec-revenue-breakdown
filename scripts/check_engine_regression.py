#!/usr/bin/env python3
"""只有本測試 CLI 可讀凍結答案；生產引擎不可匯入此檔。"""

import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))
from sec_revenue.service import ReplayService
from sec_revenue.engines import JsonCodec


class RegressionCheck:
    @classmethod
    def operand_signature(cls, facts):
        result = []
        for fact in facts:
            payload = {
                k: fact.get(k)
                for k in (
                    "concept",
                    "dimensions",
                    "unit",
                    "value",
                    "startdate",
                    "enddate",
                    "source_url",
                    "accession",
                )
            }
            for key in ("annual_evidence", "nine_month_evidence"):
                if key in fact:
                    payload[key] = cls.operand_signature([fact[key]])
            if fact.get("aggregation_evidence"):
                payload["aggregation_evidence"] = cls.operand_signature(
                    fact["aggregation_evidence"]
                )
            result.append(json.dumps(payload, sort_keys=True))
        return sorted(set(result))

    def run(self):
        root = Path(__file__).resolve().parents[1]
        manifest = JsonCodec.read(
            root / "research/refactor-baseline-sec-20261104/manifest.json"
        )
        import hashlib

        for entry in manifest["files"]:
            path = root / "research/refactor-baseline-sec-20261104" / entry["path"]
            if (
                hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
                or hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
                != entry["decompressed_sha256"]
            ):
                raise ValueError("凍結回歸答案 hash 不符")
        service = ReplayService(root, root / "data/engine-check")
        results = []
        for company in manifest["companies"]:
            ticker = company["ticker"]
            actual = {(r["period_end"], r["basis"]): r for r in service.replay(ticker)}
            differences = []
            count = 0
            for period in company["periods"]:
                expected = JsonCodec.read(
                    root
                    / f"research/refactor-baseline-sec-20261104/{ticker}/{period}/{ticker}_{period}_SEC_expected.json.gz"
                )
                sources = company["reference_sources_by_period"].get(period, [])
                basis = {
                    "stockanalysis": "reported",
                    "issuer_ir": "reported",
                    "futu": "segments",
                }.get(
                    company["default_reference"],
                    {
                        "LLY": "reported",
                        "BRK-B": "segments",
                        "PGR": "reported",
                        "XOM": "segments",
                        "PLD": "reported",
                    }.get(ticker),
                )
                if ticker == "CVX":
                    basis = "gross"
                row = actual.get((period, basis), {})
                for label, target in expected["outputs"].items():
                    got = row.get("outputs", {}).get(label, {})
                    count += 1
                    if got.get("value_usd") != target[
                        "value_usd"
                    ] or self.operand_signature(
                        got.get("SEC_operands", [])
                    ) != self.operand_signature(
                        target["SEC_operands"]
                    ):
                        differences.append(
                            {
                                "period": period,
                                "category": label,
                                "basis": basis,
                                "expected": target["value_usd"],
                                "actual": got.get("value_usd"),
                                "status": got.get("status", "period_missing"),
                                "operand_match": self.operand_signature(
                                    got.get("SEC_operands", [])
                                )
                                == self.operand_signature(target["SEC_operands"]),
                            }
                        )
            results.append(
                {"ticker": ticker, "count": count, "differences": differences}
            )
            print(ticker, count, len(differences))
        JsonCodec.write(root / "data/engine-check/regression.json", results)
        if any(c["differences"] for c in results):
            raise SystemExit(1)


if __name__ == "__main__":
    RegressionCheck().run()
