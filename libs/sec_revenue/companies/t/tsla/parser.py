"""TSLA：營運分部（Automotive、Energy generation and storage）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（汽車、能源發電與儲能），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "TSLA"
VIEW = "business_segment"
TOTAL = "Total revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Automotive", "tsla:AutomotiveSegmentMember"),
    ("Energy generation and storage", "tsla:EnergyGenerationAndStorageSegmentMember"),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
