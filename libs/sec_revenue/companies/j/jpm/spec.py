"""JPM：營運分部（Consumer & Community Banking、Commercial & Investment Bank、Asset & Wealth Management）與 Corporate。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact, one_of

REVENUE = "us-gaap:RevenuesNetOfInterestExpense"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
# 2024 年 Q2 起，原 Corporate & Investment Bank 與 Commercial Banking 合併為 Commercial & Investment Bank。
# 定義以申報期末日切換，相鄰的生效期間首尾相接。
OLD_SEGMENTS = (None, "2024-03-31")
NEW_SEGMENTS_FROM = "2024-04-01"


def segment(member: str):
    return fact(REVENUE, {**OPERATING, SEGMENT: member})


SPEC = CompanySpec(
    ticker="JPM",
    view="business_segment",
    categories=(
        Category("Consumer & Community Banking", segment("jpm:ConsumerCommunityBankingMember")),
        # 2024 年 Q2、Q3 10-Q 沿用 jpm:CorporateAndInvestmentBankMember 標示合併後的分部；FY2024 10-K 起用 jpm:CommercialAndInvestmentBankMember。
        Category(
            "Commercial & Investment Bank",
            define(
                one_of(segment("jpm:CommercialAndInvestmentBankMember"), segment("jpm:CorporateAndInvestmentBankMember")),
                effective(NEW_SEGMENTS_FROM, None),
            ),
        ),
        Category("Corporate & Investment Bank", define(segment("jpm:CorporateAndInvestmentBankMember"), effective(*OLD_SEGMENTS))),
        Category("Commercial Banking", define(segment("jpm:CommercialBankingMember"), effective(*OLD_SEGMENTS))),
        Category("Asset & Wealth Management", segment("jpm:AssetandWealthManagementSegmentMember")),
        Category("Corporate", fact(REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"})),
    ),
    # 分部營收是 managed basis（含稅負等價調整）；調節項把它調回報告的總營收。
    reconciling=(Category("Reconciling items", fact(REVENUE, {CONSOLIDATION: "us-gaap:MaterialReconcilingItemsMember"})),),
    total=Category("Total net revenue", fact(REVENUE)),
)
