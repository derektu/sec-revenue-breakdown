"""TSLA：營運分部（Automotive、Energy generation and storage）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"

SPEC = CompanySpec(
    ticker="TSLA",
    view="business_segment",
    categories=(
        Category("Automotive", fact(REVENUE, {SEGMENT: "tsla:AutomotiveSegmentMember"})),
        Category("Energy generation and storage", fact(REVENUE, {SEGMENT: "tsla:EnergyGenerationAndStorageSegmentMember"})),
    ),
    total=Category("Total revenues", fact(REVENUE)),
)
