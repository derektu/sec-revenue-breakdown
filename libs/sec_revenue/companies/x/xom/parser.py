"""XOM：Energy Products、Upstream、Chemical Products、Specialty Products 分部銷售，另列 Corporate and Financing 調節項。

us-gaap:StatementBusinessSegmentsAxis 的成員是能源、上游、化工與特種產品業務，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "XOM"
VIEW = "business_segment"
TOTAL = "Sales and other operating revenue"

REVENUE = "us-gaap:Revenues"
PRODUCT = "srt:ProductOrServiceAxis"
SALES = "xom:SalesAndOtherOperatingRevenueMember"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
GEOGRAPHY = "srt:StatementGeographicalAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
SEGMENTS = (
    ("Energy Products", "xom:EnergyProductsMember"),
    ("Upstream", "xom:UpstreamMember"),
    ("Chemical Products", "xom:ChemicalProductsMember"),
    ("Specialty Products", "xom:SpecialtyProductsMember"),
)
CORPORATE = "Corporate and Financing"


def categories(day):
    return [name for name, _ in SEGMENTS] + [CORPORATE]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        dimensions = {PRODUCT: SALES, SEGMENT: member}
        put(
            result,
            "category",
            name,
            find(filing, request, REVENUE, {**dimensions, GEOGRAPHY: "country:US"}),
            find(filing, request, REVENUE, {**dimensions, GEOGRAPHY: "us-gaap:NonUsMember"}),
        )
    corporate = one_of(
        filing,
        request,
        (REVENUE, {PRODUCT: SALES, SEGMENT: "xom:CorporateAndFinancingMember"}),
        (REVENUE, {PRODUCT: SALES, SEGMENT: "xom:CorporateAndFinancingMemberMember"}),
    )
    sales = find(filing, request, REVENUE, {PRODUCT: SALES})
    if isinstance(corporate, Missing):
        put(
            result,
            "reconciling",
            CORPORATE,
            sales,
            find(
                filing,
                request,
                REVENUE,
                {PRODUCT: SALES, CONSOLIDATION: "us-gaap:OperatingSegmentsMember"},
                weight=-1,
            ),
        )
    else:
        put(result, "reconciling", CORPORATE, corporate)
    put(result, "total", TOTAL, sales)
    return result
