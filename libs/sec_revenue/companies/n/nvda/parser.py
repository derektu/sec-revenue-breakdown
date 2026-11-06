"""NVDA：營運分部（Compute & Networking、Graphics）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（運算與網路產品、繪圖產品），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "NVDA"
VIEW = "business_segment"
TOTAL = "Revenue"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
# 期末 2024-10-27 的 10-Q 是最後一份用舊成員的申報；FY2025 10-K（期末 2025-01-26）起成員改名為 ...SegmentMember。
OLD_MEMBERS_UNTIL = "2024-10-27"
NEW_MEMBERS_FROM = "2025-01-26"
SEGMENTS = (
    ("Compute & Networking", "nvda:ComputeAndNetworkingMember", "nvda:ComputeAndNetworkingSegmentMember"),
    ("Graphics", "nvda:GraphicsMember", "nvda:GraphicsSegmentMember"),
)


def _member(day, old, new):
    """`day` 適用的成員；兩段之間的日子沒有分部。"""
    if day <= OLD_MEMBERS_UNTIL:
        return old
    if day >= NEW_MEMBERS_FROM:
        return new
    return None


def categories(day):
    return [name for name, old, new in SEGMENTS if _member(day, old, new) is not None]


def compose(filing, request):
    result = Composition()
    for name, old, new in SEGMENTS:
        member = _member(filing.report_date, old, new)
        if member is not None:
            put(result, "category", name, find(filing, request, REVENUE, {**OPERATING, SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
