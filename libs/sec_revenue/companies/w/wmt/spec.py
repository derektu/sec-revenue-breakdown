"""WMT：營運分部的淨銷售額（Walmart U.S.、Walmart International、Sam's Club U.S.）與會員費及其他收入。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact, one_of

NET_SALES = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"


# 分部成員在申報之間有兩種名稱（`...SegmentMember` 與 `...Member`），以 one_of 列出。
def segment(*members: str):
    return one_of(*(fact(NET_SALES, {SEGMENT: m}) for m in members))


SPEC = CompanySpec(
    ticker="WMT",
    view="business_segment",
    categories=(
        Category("Walmart U.S.", segment("wmt:WalmartUSMember", "wmt:WalmartUSSegmentMember")),
        Category("Walmart International", segment("wmt:WalmartInternationalMember", "wmt:WalmartInternationalSegmentMember")),
        Category("Sam's Club U.S.", segment("wmt:SamsClubUSMember", "wmt:SamsClubSegmentMember", "wmt:SamsClubMember")),
        Category("Membership and other income", fact("us-gaap:OtherIncome")),
    ),
    total=Category("Total revenues", fact("us-gaap:Revenues")),
)
