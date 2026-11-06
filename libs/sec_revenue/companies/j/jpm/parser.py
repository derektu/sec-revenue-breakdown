"""JPM：營運分部（Consumer & Community Banking、Commercial & Investment Bank、Asset & Wealth Management）與 Corporate。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（消費金融、企業與投資銀行、資產與財富管理），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "JPM"
VIEW = "business_segment"
TOTAL = "Total net revenue"

REVENUE = "us-gaap:RevenuesNetOfInterestExpense"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
CONSUMER = "Consumer & Community Banking"
COMMERCIAL_INVESTMENT = "Commercial & Investment Bank"
CORPORATE_INVESTMENT = "Corporate & Investment Bank"
COMMERCIAL = "Commercial Banking"
ASSET_WEALTH = "Asset & Wealth Management"
CORPORATE = "Corporate"
RECONCILING = "Reconciling items"
# 期末 2024-04-01 起的申報：Corporate & Investment Bank 與 Commercial Banking 合併為 Commercial & Investment Bank。
NEW_SEGMENTS_FROM = "2024-04-01"


def segment(member):
    return (REVENUE, {**OPERATING, SEGMENT: member})


def categories(day):
    if day >= NEW_SEGMENTS_FROM:
        segments = [CONSUMER, COMMERCIAL_INVESTMENT, ASSET_WEALTH]
    else:
        segments = [CONSUMER, CORPORATE_INVESTMENT, COMMERCIAL, ASSET_WEALTH]
    return segments + [CORPORATE, RECONCILING]


def compose(filing, request):
    period = filing.report_date
    result = Composition()
    put(result, "category", CONSUMER, find(filing, request, *segment("jpm:ConsumerCommunityBankingMember")))
    if period >= NEW_SEGMENTS_FROM:
        # 2024 年 Q2、Q3 10-Q 沿用 jpm:CorporateAndInvestmentBankMember 標示合併後的分部；FY2024 10-K 起用 jpm:CommercialAndInvestmentBankMember。
        put(
            result,
            "category",
            COMMERCIAL_INVESTMENT,
            one_of(filing, request, segment("jpm:CommercialAndInvestmentBankMember"), segment("jpm:CorporateAndInvestmentBankMember")),
        )
    else:
        put(result, "category", CORPORATE_INVESTMENT, find(filing, request, *segment("jpm:CorporateAndInvestmentBankMember")))
        put(result, "category", COMMERCIAL, find(filing, request, *segment("jpm:CommercialBankingMember")))
    put(result, "category", ASSET_WEALTH, find(filing, request, *segment("jpm:AssetandWealthManagementSegmentMember")))
    put(result, "category", CORPORATE, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}))
    # 分部營收是 managed basis（含稅負等價調整）；調節項把它調回報告的總營收。
    put(result, "reconciling", RECONCILING, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:MaterialReconcilingItemsMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
