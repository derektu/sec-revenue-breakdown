"""PLD：營運分部（不動產、Strategic Capital）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}

SPEC = CompanySpec(
    ticker="PLD",
    view="business_segment",
    categories=(
        Category("Real estate segment", fact(REVENUE, {**OPERATING, SEGMENT: "pld:RealEstateOperationsSegmentMember"})),
        Category("Strategic capital segment", fact(REVENUE, {**OPERATING, SEGMENT: "pld:StrategicCapitalSegmentMember"})),
    ),
    total=Category("Total revenues", fact(REVENUE)),
)
