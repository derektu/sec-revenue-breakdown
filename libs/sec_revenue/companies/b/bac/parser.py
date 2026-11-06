"""BAC：營運分部（Consumer Banking、GWIM、Global Banking、Global Markets）與 All Other，FTE 口徑。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（消費金融、財富管理、企業金融、市場交易），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "BAC"
VIEW = "business_segment"
TOTAL = "Total revenue, net of interest expense"

REVENUE = "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
SEGMENTS = (
    ("Consumer Banking", "bac:ConsumerBankingSegmentMember"),
    ("Global Wealth & Investment Management", "bac:GlobalWealthAndInvestmentManagementSegmentMember"),
    ("Global Banking", "bac:GlobalBankingSegmentMember"),
    ("Global Markets", "bac:GlobalMarketsSegmentMember"),
)
ALL_OTHER = "All Other"


def categories(day):
    return [name for name, _ in SEGMENTS] + [ALL_OTHER]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:OperatingSegmentsMember", SEGMENT: member}))
    put(result, "category", ALL_OTHER, find(filing, request, REVENUE, {CONSOLIDATION: "bac:CorporateReconcilingItemsAndEliminationsMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
