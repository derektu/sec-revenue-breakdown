"""NVDA：營運分部（Compute & Networking、Graphics）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
# FY2025 10-K（期末 2025-01-26）起，分部成員改名為 ...SegmentMember；更早的申報用舊成員。
OLD_MEMBERS_UNTIL = "2024-10-27"
NEW_MEMBERS_FROM = "2025-01-26"


def segment(old: str, new: str):
    return (
        define(fact(REVENUE, {**CONSOLIDATION, SEGMENT: old}), effective(None, OLD_MEMBERS_UNTIL)),
        define(fact(REVENUE, {**CONSOLIDATION, SEGMENT: new}), effective(NEW_MEMBERS_FROM, None)),
    )


SPEC = CompanySpec(
    ticker="NVDA",
    view="business_segment",
    categories=(
        Category("Compute & Networking", *segment("nvda:ComputeAndNetworkingMember", "nvda:ComputeAndNetworkingSegmentMember")),
        Category("Graphics", *segment("nvda:GraphicsMember", "nvda:GraphicsSegmentMember")),
    ),
    total=Category("Revenue", fact(REVENUE)),
)
