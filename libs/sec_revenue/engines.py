"""來源與季度運算；共用程式不包含任何公司判斷。"""

from __future__ import annotations
import copy
import datetime as dt
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from decimal import Decimal


class JsonCodec:
    @staticmethod
    def encode(value: object) -> bytes:
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            + "\n"
        ).encode()

    @classmethod
    def write(cls, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=path.name + ".", delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(cls.encode(value))
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(path)

    @staticmethod
    def read(path: Path) -> dict:
        return json.loads(
            gzip.decompress(path.read_bytes())
            if path.suffix == ".gz"
            else path.read_bytes()
        )


class EvidenceStore:
    """保留實際 capture 格式；原文缺失與可重播 facts 是不同狀態。"""

    def __init__(self, root: Path):
        self.root = root

    def capture(
        self,
        ticker: str,
        period: str,
        accession: str,
        body: bytes,
        kind: str,
        metadata: dict,
    ) -> dict:
        digest = hashlib.sha256(body).hexdigest()
        directory = self.root / ticker / period / accession
        path = directory / (
            digest
            + "."
            + {
                "facts_cache": "json",
                "original_html": "html",
                "web_text": "txt",
                "dom_snapshot": "json",
            }[kind]
        )
        directory.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != body:
            raise ValueError("Evidence collision")
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(body)
        receipt = dict(
            metadata, path=str(path), sha256=digest, source_format=kind, bytes=len(body)
        )
        JsonCodec.write(path.with_suffix(path.suffix + ".receipt.json"), receipt)
        return receipt


class SecDownloadEngine:
    """單次正常 SEC GET；拒絕後不換身分、不重試。"""

    def __init__(self, store: EvidenceStore, user_agent: str):
        if not user_agent.strip() or "example.com" in user_agent:
            raise ValueError("請設定真實 SEC_USER_AGENT 聯絡資料")
        self.store, self.user_agent = store, user_agent

    def download(self, ticker: str, period: str, accession: str, url: str) -> dict:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc not in ("www.sec.gov", "data.sec.gov")
            or parsed.query
            or parsed.fragment
            or ".." in parsed.path.split("/")
        ):
            raise ValueError("只接受明確 SEC HTTPS URL")
        with urlopen(
            Request(url, headers={"User-Agent": self.user_agent}), timeout=30
        ) as response:
            if response.geturl() != url:
                raise ValueError("不接受重新導向")
            body = response.read()
            content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "application/xhtml+xml"):
            raise ValueError("預期 SEC HTML；未儲存為假 HTML")
        return self.store.capture(
            ticker, period, accession, body, "original_html", {"source_url": url}
        )


class XbrlEngine:
    """讀取來源擷取 facts；不使用舊 quarter_results 或任何完成輸出。"""

    def read_cache(self, path: Path, recorded_sha256: str | None = None) -> list[dict]:
        if recorded_sha256 is None:
            verification = JsonCodec.read(path.parent / "verification.json")
            recorded_sha256 = verification["artifact_sha256"][path.name]
        if hashlib.sha256(path.read_bytes()).hexdigest() != recorded_sha256:
            raise ValueError("SEC facts cache hash mismatch")
        data = JsonCodec.read(path)
        records = copy.deepcopy(data["raw_filings"])
        for record in records:
            for fact in record["facts"]:
                if urlsplit(fact.get("source_url", "")).hostname not in (
                    "www.sec.gov",
                    "sec.gov",
                ):
                    raise ValueError("非 SEC facts")
        return sorted(records, key=lambda row: row["filing"]["filingDate"])

    def parse_html(self, body: bytes, source_url: str, accession: str) -> list[dict]:
        from lxml import etree

        root = etree.fromstring(body, etree.HTMLParser())
        contexts, units = {}, {}
        for node in root.iter():
            name = node.tag.lower() if isinstance(node.tag, str) else ""
            if name.endswith("typedmember"):
                raise ValueError("尚未支援 typed dimension，拒絕遺失 scope")
            if name.endswith("context"):
                children = {
                    n.tag.lower().split(":")[-1]: "".join(n.itertext()).strip()
                    for n in node.iter()
                    if isinstance(n.tag, str)
                }
                dims = {
                    n.get("dimension"): "".join(n.itertext()).strip()
                    for n in node.iter()
                    if isinstance(n.tag, str)
                    and n.tag.lower().endswith("explicitmember")
                }
                contexts[node.get("id")] = {
                    "startdate": children.get("startdate"),
                    "enddate": children.get("enddate", children.get("instant")),
                    "dimensions": dims,
                }
            if name.endswith("unit"):
                units[node.get("id")] = "".join(node.itertext()).strip()
        facts = []
        for node in root.iter():
            if not isinstance(node.tag, str) or not node.tag.lower().endswith(
                "nonfraction"
            ):
                continue
            context = contexts.get(node.get("contextref"))
            if not context:
                raise ValueError("Missing XBRL context")
            raw = "".join(node.itertext()).strip().replace(",", "")
            if raw in ("", "—", "-"):
                continue
            value = Decimal(raw) * Decimal(10) ** int(node.get("scale", "0"))
            if node.get("sign") == "-":
                value = -value
            if value != value.to_integral_value():
                raise ValueError("非整數美元需明確精度處理")
            facts.append(
                dict(
                    context,
                    concept=node.get("name"),
                    unit=units.get(node.get("unitref")),
                    value=int(value),
                    decimals=node.get("decimals"),
                    source_url=source_url,
                    accession=accession,
                )
            )
        if not facts:
            raise ValueError("無 inline XBRL facts")
        return facts


class QuarterEngine:
    @staticmethod
    def days(fact: dict) -> int:
        try:
            return (
                dt.date.fromisoformat(fact["enddate"])
                - dt.date.fromisoformat(fact["startdate"])
            ).days + 1
        except (ValueError, KeyError, TypeError):
            return 0

    @staticmethod
    def scope(fact: dict) -> str:
        return json.dumps(
            [fact.get("concept"), fact.get("dimensions"), fact.get("unit")],
            sort_keys=True,
        )

    def dedupe(self, facts: list[dict]) -> tuple[list[dict], list[list[dict]]]:
        groups = {}
        for fact in facts:
            if type(fact.get("value")) is int:
                key = (self.scope(fact), fact.get("startdate"), fact.get("enddate"))
                groups.setdefault(key, []).append(fact)
        good, conflicts = [], []
        for group in groups.values():
            if len({f["value"] for f in group}) != 1:
                conflicts.append(group)
            else:
                good.append(group[0])
        return good, conflicts

    def quarter(
        self, facts: list[dict], end: str, prior: list[dict]
    ) -> tuple[list[dict], list[list[dict]]]:
        direct, conflicts = self.dedupe(
            [f for f in facts if f.get("enddate") == end and 70 <= self.days(f) <= 120]
        )
        scopes = {self.scope(f) for f in direct} | {
            self.scope(f) for g in conflicts for f in g
        }
        annual, annual_conflicts = self.dedupe(
            [f for f in facts if f.get("enddate") == end and 350 <= self.days(f) <= 380]
        )
        for group in annual_conflicts:
            conflicts.append(group)
        for year in annual:
            if self.scope(year) in scopes:
                continue
            candidates = [
                f
                for f in prior
                if self.scope(f) == self.scope(year)
                and f.get("startdate") == year["startdate"]
                and 230 <= self.days(f) <= 300
                and 70
                <= (
                    dt.date.fromisoformat(end) - dt.date.fromisoformat(f["enddate"])
                ).days
                <= 120
            ]
            nine, bad = self.dedupe(candidates)
            if bad:
                conflicts.extend(bad)
            elif len(nine) == 1:
                q = copy.deepcopy(year)
                q.update(
                    value=year["value"] - nine[0]["value"],
                    startdate=(
                        dt.date.fromisoformat(nine[0]["enddate"]) + dt.timedelta(days=1)
                    ).isoformat(),
                    derivation="annual_minus_nine_months",
                    annual_evidence=year,
                    nine_month_evidence=nine[0],
                )
                direct.append(q)
        return direct, conflicts


class SelectionEngine:
    """每個替代式必須齊備，替代式彼此不同值視為歧義。"""

    def select(
        self, rule: dict, facts: list[dict], conflicts: list[list[dict]]
    ) -> dict:
        alternatives = []
        for terms in rule["alternatives"]:
            if not terms:
                continue
            selected = []
            for term in terms:
                matches = lambda f: all(
                    f.get(k) == term[k] for k in ("concept", "dimensions", "unit")
                )
                found = [f for f in facts if matches(f) and type(f.get("value")) is int]
                if (
                    any(matches(f) for g in conflicts for f in g)
                    or len({f["value"] for f in found}) > 1
                ):
                    return {
                        "status": "ambiguous_scope",
                        "value_usd": None,
                        "SEC_operands": [],
                    }
                if not found:
                    break
                selected.append((term.get("weight", 1), found[0]))
            if len(selected) == len(terms):
                alternatives.append(
                    {
                        "value_usd": sum(w * f["value"] for w, f in selected),
                        "SEC_operands": [f for _, f in selected],
                        "weights": [w for w, _ in selected],
                    }
                )
        if not alternatives:
            return {
                "status": "parser_scope_missing",
                "value_usd": None,
                "SEC_operands": [],
            }
        if len({a["value_usd"] for a in alternatives}) > 1:
            return {
                "status": "ambiguous_alternatives",
                "value_usd": None,
                "SEC_operands": [],
            }
        return dict(
            value_usd=alternatives[0]["value_usd"],
            SEC_operands=[f for a in alternatives for f in a["SEC_operands"]],
            expression_alternatives=alternatives,
            status="observed",
            role=rule.get("role", "component"),
        )


class PrecisionAnalyzer:
    """四捨五入誤差只隨真實運算元累加，不用百分比放寬。"""

    def fact_error(self, fact: dict) -> Decimal | None:
        if fact.get("derivation") == "annual_minus_nine_months":
            children = [fact["annual_evidence"], fact["nine_month_evidence"]]
        elif fact.get("aggregation_evidence"):
            children = fact["aggregation_evidence"]
        else:
            if fact.get("decimals") == "INF":
                return Decimal(0)
            if fact.get("decimals") is None:
                return None
            return Decimal(10) ** (-int(fact["decimals"])) / 2
        errors = [self.fact_error(f) for f in children]
        return None if None in errors else sum(errors, Decimal(0))

    def output_error(self, output: dict) -> str | None:
        if output.get("expression_alternatives"):
            errors = [self.output_error(a) for a in output["expression_alternatives"]]
            return None if None in errors else str(max(Decimal(e) for e in errors))
        errors = [self.fact_error(f) for f in output["SEC_operands"]]
        if not errors or None in errors:
            return None
        weights = output.get("weights", [1] * len(errors))
        return str(sum((abs(w) * e for w, e in zip(weights, errors)), Decimal(0)))
