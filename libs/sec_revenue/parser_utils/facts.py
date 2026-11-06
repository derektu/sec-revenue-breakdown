"""依 concept 與 dimensions 在一份申報中找 fact，組成 `Composition` 的項目。

比對是精確的：concept 與 dimensions 依文件宣告的 namespace 解析成 URI 後完全相同，fact 多一個或少一個維度都不算；
期間由 `Request` 決定。找不到時回傳 `Missing`，由 `put` 記為組成中沒有這一項。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..revenue.contract import Composition, FilingFacts, ParserFailure, Request, Term

Variant = tuple[str, dict[str, str] | None]


@dataclass(frozen=True)
class Missing:
    """一項在申報中找不到：`reason` 描述找的是什麼、在哪個期間與申報。"""

    reason: str


def describe(concept: str, dimensions: dict[str, str] | None = None) -> str:
    """一種寫法的文字描述，例如 `us-gaap:Revenues [srt:ProductOrServiceAxis=x:AMember]`。"""
    dims = ", ".join(f"{a}={m}" for a, m in sorted((dimensions or {}).items())) or "無維度"
    return f"{concept} [{dims}]"


def _matches(filing: FilingFacts, request: Request, concept: str, dimensions: dict[str, str] | None) -> list | None:
    """一種寫法在申報中期間相符的 fact；前綴在文件中沒有宣告時回傳 None，宣告衝突時以 `ParserFailure` 結束。"""
    document = filing.document
    pairs = tuple(sorted((dimensions or {}).items()))
    conflicts = document.conflicting_prefixes(concept, pairs)
    if conflicts:
        raise ParserFailure("fact 存在且唯一", f"{describe(concept, dimensions)} 的前綴 {conflicts} 在 {filing.accession} 中宣告衝突")
    keys = (document.resolve(concept), document.resolve_dimensions(pairs))
    if None in keys:
        return None
    return [f for f in document.facts if (f.concept_key, f.dimension_keys) == keys and request.matches(f)]


def _where(filing: FilingFacts, request: Request) -> str:
    return f"{request.duration} 期末 {request.end}（{filing.accession}）"


def find(filing: FilingFacts, request: Request, concept: str, dimensions: dict[str, str] | None = None, weight: int = 1) -> Term | Missing:
    """一種寫法的 fact，回傳權重為 `weight` 的一項；找不到或前綴沒有宣告時回傳 `Missing`。"""
    label = describe(concept, dimensions)
    found = _matches(filing, request, concept, dimensions)
    if found is None:
        return Missing(f"{label} {_where(filing, request)}：前綴在文件中沒有宣告")
    if not found:
        return Missing(f"{label} {_where(filing, request)}")
    return Term(tuple(found), weight, label)


def one_of(filing: FilingFacts, request: Request, *variants: Variant, weight: int = 1) -> Term | Missing:
    """同一個數字在不同申報用不同寫法時，找每一種寫法；所有找到的 fact 合成一項，數值是否一致由框架檢查。

    `variants` 是（concept, dimensions）的序列。前綴沒有宣告的寫法視為不存在。
    """
    label = "one_of(" + "；".join(describe(c, d) for c, d in variants) + ")"
    found, declared = [], False
    for concept, dimensions in variants:
        matches = _matches(filing, request, concept, dimensions)
        if matches is not None:
            declared = True
            found += matches
    if not found:
        suffix = "" if declared else "：前綴在文件中沒有宣告"
        return Missing(f"{label} {_where(filing, request)}{suffix}")
    ordered = tuple(sorted(set(found), key=lambda f: f.order))
    return Term(ordered, weight, label)


def put(composition: Composition, group: str, name: str, *terms: Term | Missing):
    """把一項放進組成：`group` 是 `category`、`reconciling` 或 `total`。任一項是 `Missing` 時不列出，原因記在 `missing`。"""
    missing = [t.reason for t in terms if isinstance(t, Missing)]
    if missing:
        composition.missing[name] = f"{name}：{'；'.join(missing)}"
        return
    if group == "total":
        composition.total = list(terms)
    elif group == "category":
        composition.categories[name] = list(terms)
    elif group == "reconciling":
        composition.reconciling[name] = list(terms)
    else:
        raise ValueError(f"group 必須是 category、reconciling 或 total，收到 {group!r}")
