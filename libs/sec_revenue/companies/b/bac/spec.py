"""BAC：營運分部（Consumer Banking、GWIM、Global Banking、Global Markets）與 All Other，FTE 口徑。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"


def segment(member: str):
    return fact(REVENUE, {CONSOLIDATION: "us-gaap:OperatingSegmentsMember", SEGMENT: member})


SPEC = CompanySpec(
    ticker="BAC",
    view="business_segment",
    categories=(
        Category("Consumer Banking", segment("bac:ConsumerBankingSegmentMember")),
        Category("Global Wealth & Investment Management", segment("bac:GlobalWealthAndInvestmentManagementSegmentMember")),
        Category("Global Banking", segment("bac:GlobalBankingSegmentMember")),
        Category("Global Markets", segment("bac:GlobalMarketsSegmentMember")),
        Category("All Other", fact(REVENUE, {CONSOLIDATION: "bac:CorporateReconcilingItemsAndEliminationsMember"})),
    ),
    total=Category("Total revenue, net of interest expense", fact(REVENUE)),
)
