"""META：營運分部（Family of Apps、Reality Labs）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"

SPEC = CompanySpec(
    ticker="META",
    view="business_segment",
    categories=(
        Category("Family of Apps", fact(REVENUE, {SEGMENT: "meta:FamilyOfAppsMember"})),
        Category("Reality Labs", fact(REVENUE, {SEGMENT: "meta:RealityLabsMember"})),
    ),
    total=Category("Revenue", fact(REVENUE)),
)
