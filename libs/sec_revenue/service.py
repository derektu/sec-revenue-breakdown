"""離線重播協調與近期維護風險。"""

from __future__ import annotations
import hashlib
import importlib
import json
from pathlib import Path
from sec_revenue.engines import EvidenceStore, JsonCodec, XbrlEngine, PrecisionAnalyzer


class RiskAnalyzer:
    def walk(self, fact: dict):
        yield fact
        for key in ("annual_evidence", "nine_month_evidence"):
            if fact.get(key):
                yield from self.walk(fact[key])
        for child in fact.get("aggregation_evidence", []):
            yield from self.walk(child)

    def assess(self, rows: list[dict], receipts: list[dict] | None = None) -> dict:
        schemas, rules, missing = [], set(), 0
        for row in sorted(rows, key=lambda r: r["period_end"]):
            shape = set()
            for label, output in row["outputs"].items():
                if output["status"] != "observed":
                    missing += 1
                for fact in [
                    child
                    for operand in output["SEC_operands"]
                    for child in self.walk(operand)
                ]:
                    shape.add(
                        json.dumps(
                            [
                                label,
                                fact["concept"],
                                fact["dimensions"],
                                fact.get("original_dimensions"),
                            ],
                            sort_keys=True,
                        )
                    )
                    for key in (
                        "normalization_rule_id",
                        "scope_bridge_rule_id",
                        "revision_rule_id",
                    ):
                        if fact.get(key):
                            rules.add(fact[key])
                    if fact.get("derivation"):
                        rules.add(fact["derivation"])
                if output.get("rule_id"):
                    rules.add(output["rule_id"])
            schemas.append({"period": row["period_end"], "shape": shape})
        reasons, score = [], 0
        if missing:
            score += 50
            reasons.append(f"{missing} 個分類缺值或歧義，禁止視為零")
        if len(schemas) < 2:
            score += 40
            reasons.append("可比較期間不足")
        changes = []
        for previous, current in zip(schemas, schemas[1:]):
            difference = len(current["shape"] ^ previous["shape"])
            changes.append(
                {
                    "from": previous["period"],
                    "to": current["period"],
                    "changed_fields": difference,
                }
            )
        recent = sum(c["changed_fields"] for c in changes[-2:])
        if recent:
            score += min(40, recent * 5)
            reasons.append(f"最近兩次比較有 {recent} 個 scope／分類變動")
        if rules:
            score += min(25, len(rules) * 5)
            reasons.append("實際使用特殊處理：" + ", ".join(sorted(rules)))
        original_urls = {
            r.get("source_url")
            for r in receipts or []
            if r["source_format"] == "original_html"
        }
        used_urls = {
            f.get("source_url")
            for row in rows
            for o in row["outputs"].values()
            for operand in o["SEC_operands"]
            for f in self.walk(operand)
        }
        missing_raw = len(used_urls - original_urls)
        if missing_raw or not used_urls:
            score += 15
            reasons.append(
                f"{missing_raw} 個使用的 SEC 文件缺原始 HTML bytes；以 facts／DOM／文字格式誠實重播"
            )
        return {
            "score": min(score, 100),
            "level": "high" if score >= 50 else "medium" if score >= 20 else "low",
            "reasons": reasons,
            "comparisons": changes,
            "schemas": [
                {
                    "period": r["period"],
                    "sha256": hashlib.sha256(
                        JsonCodec.encode(sorted(r["shape"]))
                    ).hexdigest(),
                }
                for r in schemas
            ],
            "meaning": "parser 維護風險，非投資風險或準確率",
        }


class ParserRegistry:
    def __init__(self):
        self.entries = JsonCodec.read(Path(__file__).with_name("registry.json"))

    def create(self, ticker: str, repository=None, output=None):
        entry = self.entries[ticker]
        return getattr(
            importlib.import_module("sec_revenue.parsers." + entry["module"]),
            entry["class"],
        )(repository, output)


class ReplayService:
    def __init__(self, repository: Path, output: Path):
        self.repository, self.output = repository, output
        self.registry = ParserRegistry()

    def replay(self, ticker: str) -> list[dict]:
        if ticker not in self.registry.entries:
            raise ValueError("未註冊 ticker")
        entry = self.registry.entries[ticker]
        source = self.repository / entry.get(
            "facts_cache_path", f"research/sec-30-baseline-2026-11-04/{ticker}.json.gz"
        )
        records = XbrlEngine().read_cache(source, entry.get("facts_cache_sha256"))
        source_manifest = JsonCodec.read(source)["manifest"]
        store = EvidenceStore(self.output / "sec")
        receipts = []
        for record in records:
            filing = record["filing"]
            original = next(
                (
                    entry
                    for entry in source_manifest
                    if entry.get("accessionNumber") == filing["accessionNumber"]
                ),
                {},
            )
            receipts.append(
                store.capture(
                    ticker,
                    filing["reportDate"],
                    filing["accessionNumber"],
                    JsonCodec.encode(record),
                    "facts_cache",
                    {
                        "upstream_cache": str(source.relative_to(self.repository)),
                        "upstream_cache_sha256": hashlib.sha256(
                            source.read_bytes()
                        ).hexdigest(),
                        "original_html_available": False,
                        "source_url": original.get("url"),
                        "original_html_recorded_sha256": original.get("sha256"),
                    },
                )
            )
        parser = self.registry.create(ticker, self.repository, self.output)
        rows = [
            row
            for row in parser.parse(records)
            if row["period_end"] in self.registry.entries[ticker]["periods"]
        ]
        reference = self.registry.entries[ticker]["reference"]
        JsonCodec.write(
            self.output / "references" / ticker / "registry.json", reference
        )
        receipts.extend(parser.source_receipts)
        receipts.extend(self.available_originals(ticker))
        receipts = list({receipt["path"]: receipt for receipt in receipts}.values())
        original_accessions = {
            Path(r["path"]).parent.name
            for r in receipts
            if r["source_format"] == "original_html"
        }
        for receipt in receipts:
            if receipt["source_format"] == "facts_cache":
                receipt["original_html_available"] = (
                    Path(receipt["path"]).parent.name in original_accessions
                )
                path = Path(receipt["path"])
                JsonCodec.write(
                    path.with_suffix(path.suffix + ".receipt.json"), receipt
                )

        JsonCodec.write(
            self.output / "sec" / ticker / "original-downloads.json",
            [
                {
                    "source_url": entry["url"],
                    "recorded_sha256": entry["sha256"],
                    "recorded_bytes": entry.get("bytes"),
                    "original_filename": entry.get("file"),
                    "period_end": entry.get("reportDate"),
                    "accession": entry.get("accessionNumber"),
                    "raw_bytes_present": any(
                        r.get("source_url") == entry["url"]
                        and r["sha256"] == entry["sha256"]
                        and r["source_format"] == "original_html"
                        for r in receipts
                    ),
                    "available_capture_formats": sorted(
                        {
                            r["source_format"]
                            for r in receipts
                            if r.get("source_url") == entry["url"]
                        }
                    ),
                }
                for entry in source_manifest
            ],
        )
        present = {r["period_end"] for r in rows}
        for period in sorted(set(self.registry.entries[ticker]["periods"]) - present):
            rows.append(
                {
                    "ticker": ticker,
                    "period_end": period,
                    "period_kind": "Q",
                    "basis": self.registry.entries[ticker]["primary_basis"],
                    "outputs": {
                        "missing_source": {
                            "status": "source_period_missing",
                            "value_usd": None,
                            "SEC_operands": [],
                        }
                    },
                }
            )
        by_basis = {}
        for row in rows:
            by_basis.setdefault(row["basis"], []).append(row)
        for basis, group in by_basis.items():
            risk = RiskAnalyzer().assess(group, receipts)
            for row in group:
                for output in row["outputs"].values():
                    output["reported_error_usd"] = PrecisionAnalyzer().output_error(
                        output
                    )
                row.update(parser.fiscal_label(row["period_end"], records))
                row["risk"] = risk
                row["source_formats"] = sorted(
                    {
                        f.get("source_format", "facts_cache")
                        for o in row["outputs"].values()
                        for f in o["SEC_operands"]
                    }
                )
                row["reference"] = reference
                row["primary_basis"] = self.registry.entries[ticker]["primary_basis"]
                row["fiscal_period"] = {
                    "startdate": min(
                        (
                            f.get("startdate", "")
                            for o in row["outputs"].values()
                            for f in o["SEC_operands"]
                        ),
                        default=None,
                    ),
                    "enddate": row["period_end"],
                    "kind": "Q",
                }
                JsonCodec.write(
                    self.output
                    / "outputs"
                    / ticker
                    / row["period_end"]
                    / f"{ticker}_{row['period_end']}_{basis}_revenue.json",
                    row,
                )
        JsonCodec.write(self.output / "sec" / ticker / "index.json", receipts)
        JsonCodec.write(
            self.output / "outputs" / ticker / "index.json",
            {
                "paths": [
                    f"{r['period_end']}/{ticker}_{r['period_end']}_{r['basis']}_revenue.json"
                    for r in rows
                ],
                "periods": self.registry.entries[ticker]["periods"],
                "parser_class": type(parser).__name__,
                "parser_sha256": hashlib.sha256(
                    (
                        Path(__file__).parent
                        / "parsers"
                        / (self.registry.entries[ticker]["module"] + ".py")
                    ).read_bytes()
                ).hexdigest(),
            },
        )
        return rows

    def available_originals(self, ticker: str) -> list[dict]:
        """已下載的真正 HTML 也納入資料索引，不冒稱每個 facts 來源皆有原文。"""
        import gzip

        entries = JsonCodec.read(
            self.repository / "research/shared-raw-semantics/manifest.json"
        )["filings"]
        receipts = []
        for entry in entries:
            if entry["ticker"] != ticker:
                continue
            packed = (self.repository / entry["path"]).read_bytes()
            raw = gzip.decompress(packed)
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError("原始 HTML hash 不符")
            receipts.append(
                EvidenceStore(self.output / "sec").capture(
                    ticker,
                    entry["reportDate"],
                    entry["accessionNumber"],
                    raw,
                    "original_html",
                    {
                        "source_url": entry["url"],
                        "upstream_container": entry["path"],
                        "upstream_container_sha256": hashlib.sha256(packed).hexdigest(),
                    },
                )
            )
        return receipts
