"""WMT：營運分部的淨銷售額（Walmart U.S.、Walmart International、Sam's Club U.S.）與會員費及其他收入。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（Walmart U.S.、Walmart International、Sam's Club U.S.），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "WMT"
VIEW = "business_segment"
TOTAL = "Total revenues"

NET_SALES = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
# 分部成員在申報之間有兩種以上名稱（`...SegmentMember` 與 `...Member`），每種寫法都找。
SEGMENTS = (
    ("Walmart U.S.", ("wmt:WalmartUSMember", "wmt:WalmartUSSegmentMember")),
    ("Walmart International", ("wmt:WalmartInternationalMember", "wmt:WalmartInternationalSegmentMember")),
    ("Sam's Club U.S.", ("wmt:SamsClubUSMember", "wmt:SamsClubSegmentMember", "wmt:SamsClubMember")),
)
MEMBERSHIP = "Membership and other income"


def categories(day):
    return [name for name, _ in SEGMENTS] + [MEMBERSHIP]


def compose(filing, request):
    result = Composition()
    for name, members in SEGMENTS:
        put(result, "category", name, one_of(filing, request, *((NET_SALES, {SEGMENT: m}) for m in members)))
    put(result, "category", MEMBERSHIP, find(filing, request, "us-gaap:OtherIncome"))
    put(result, "total", TOTAL, find(filing, request, "us-gaap:Revenues"))
    return result
