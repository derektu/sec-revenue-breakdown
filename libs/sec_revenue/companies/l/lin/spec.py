"""LIN：Industrial Gases（三個地區分部加總）、Engineering、Other。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact, sum_of

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}


def segment(member: str):
    return fact(REVENUE, {**OPERATING, SEGMENT: member})


SPEC = CompanySpec(
    ticker="LIN",
    view="business_segment",
    categories=(
        # 工業氣體業務依地區分成三個報告分部；觀點不做地區拆分，三者加總成一類。
        Category(
            "Industrial Gases",
            sum_of(
                segment("lin:AmericasSegmentMember"),
                segment("lin:EMEASegmentMember"),
                segment("lin:APACSegmentMember"),
            ),
        ),
        Category("Engineering", segment("lin:EngineeringSegmentMember")),
        Category("Other", segment("us-gaap:CorporateAndOtherMember")),
    ),
    total=Category("Total", fact(REVENUE)),
)
