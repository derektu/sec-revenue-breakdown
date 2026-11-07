"""ORCL：業務分部營收，三類為 Cloud and license／Cloud and software、Services、Hardware。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（雲端與軟體、服務、硬體），不是地區。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "ORCL"
VIEW = "business_segment"
TOTAL = "Total revenues"
# 2026-08-31 的 10-Q（0001193125-26-389274）宣告財年 2026，實為 2027；10-Q 的財年由前一份 10-K 推算，理由見 parser.md 的「期別與推算」。
FISCAL_YEAR = "prior_annual"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = "us-gaap:OperatingSegmentsMember"
# FY2026 Q1 10-Q（0001193125-25-200095，期末 2025-08-31）起，Cloud and license 改名 Cloud and software。
RENAMED_FROM = "2025-06-01"
CLOUD_NEW = ("Cloud and software", "orcl:CloudAndSoftwareBusinessMember")
CLOUD_OLD = ("Cloud and license", "orcl:CloudAndLicenseBusinessMember")
OTHER_SEGMENTS = (
    ("Services", "orcl:ServicesBusinessMember"),
    ("Hardware", "orcl:HardwareBusinessMember"),
)


def categories(day):
    first = CLOUD_OLD[0] if day < RENAMED_FROM else CLOUD_NEW[0]
    return [first] + [name for name, _ in OTHER_SEGMENTS]


def _segment(filing, request, member):
    return find(filing, request, REVENUE, {SEGMENT: member, CONSOLIDATION: OPERATING})


def compose(filing, request):
    result = Composition()
    name, member = CLOUD_NEW
    cloud = _segment(filing, request, member)
    if isinstance(cloud, Missing):
        name, member = CLOUD_OLD
        cloud = _segment(filing, request, member)
    put(result, "category", name, cloud)
    for name, member in OTHER_SEGMENTS:
        put(result, "category", name, _segment(filing, request, member))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
