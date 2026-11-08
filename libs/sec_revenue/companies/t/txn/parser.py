"""TXN：業務分部 Analog、Embedded Processing、Other；分部軸成員是業務別，不是地區。說明見 parser.md。"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "TXN"
VIEW = "business_segment"
TOTAL = "Total revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Analog", ("txn:AnalogMember", "txn:AnalogSegmentMember")),
    ("Embedded Processing", ("txn:EmbeddedProcessingMember", "txn:EmbeddedProcessingSegmentMember")),
    ("Other", ("us-gaap:AllOtherSegmentsMember",)),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, members in SEGMENTS:
        put(result, "category", name, one_of(
            filing, request, *((REVENUE, {SEGMENT: member}) for member in members),
        ))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
