"""NEE：業務分部營收（FPL、NEER、Corporate and Other）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "NEE"
VIEW = "business_segment"
TOTAL = "Total consolidated revenues"

REVENUE = "us-gaap:RegulatedAndUnregulatedOperatingRevenue"
SEGMENTS = (
    ("FPL", {"dei:LegalEntityAxis": "nee:FloridaPowerLightCompanyMember"}),
    (
        "NEER",
        {
            "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
            "us-gaap:StatementBusinessSegmentsAxis": "nee:NEERSegmentMember",
        },
    ),
    ("Corporate and Other", {"srt:ConsolidationItemsAxis": "nee:CorporateAndEliminationsMember"}),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, dimensions in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, dimensions))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
