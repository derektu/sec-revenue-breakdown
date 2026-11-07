"""CVX：Downstream、Upstream、All Other 的抵銷後分部營收，沒有調節項。

us-gaap:StatementBusinessSegmentsAxis 的成員是上下游業務與其他業務，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "CVX"
VIEW = "business_segment"
TOTAL = "Sales and Other Operating Revenues"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
OIL_AND_GAS = "us-gaap:OilAndGasMember"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
GEOGRAPHY = "srt:StatementGeographicalAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
SEGMENTS = (
    ("Downstream", "cvx:DownstreamMember", "cvx:DownstreamSegmentMember"),
    ("Upstream", "cvx:UpstreamMember", "cvx:UpstreamSegmentMember"),
)
OTHER = "All Other"


def categories(day):
    return [name for name, _, _ in SEGMENTS] + [OTHER]


def compose(filing, request):
    result = Composition()
    for name, member, segment_member in SEGMENTS:
        subtotal = one_of(
            filing,
            request,
            (REVENUE, {PRODUCT: OIL_AND_GAS, SEGMENT: member}),
            (REVENUE, {PRODUCT: OIL_AND_GAS, SEGMENT: segment_member}),
        )
        if isinstance(subtotal, Missing):
            put(
                result,
                "category",
                name,
                find(filing, request, REVENUE, {SEGMENT: segment_member, GEOGRAPHY: "country:US"}),
                find(filing, request, REVENUE, {SEGMENT: segment_member, GEOGRAPHY: "us-gaap:NonUsMember"}),
            )
        else:
            put(result, "category", name, subtotal)
    put(
        result,
        "category",
        OTHER,
        one_of(
            filing,
            request,
            (REVENUE, {PRODUCT: OIL_AND_GAS, CONSOLIDATION: "cvx:CorporateAndEliminationsMember"}),
            (REVENUE, {SEGMENT: "us-gaap:AllOtherSegmentsMember"}),
        ),
    )
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
