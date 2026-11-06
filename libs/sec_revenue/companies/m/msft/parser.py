"""MSFT：依申報列示三個或兩個業務分部，沒有調節項。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "MSFT"
VIEW = "business_segment"
TOTAL = "Total revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
ORIGINAL_SEGMENTS = (
    ("Intelligent Cloud", "msft:IntelligentCloudMember"),
    ("More Personal Computing", "msft:MorePersonalComputingMember"),
    ("Productivity and Business Processes", "msft:ProductivityAndBusinessProcessesMember"),
)
NEW_SEGMENTS = (
    ("Agents and Infra", "msft:AgentsAndInfraMember"),
    ("Devices and Consumer", "msft:DevicesAndConsumerMember"),
)
# 期末 2026-09-30 的 10-Q（0001193125-26-436133）列示 2026-07-01～2026-09-30 已為兩類。
# FY2027 自該期起日開始；框架逐日檢查 Q4 的分類集合，因此切換點使用起日。
FIRST_TWO_SEGMENTS = "2026-07-01"


def categories(day):
    segments = NEW_SEGMENTS if day >= FIRST_TWO_SEGMENTS else ORIGINAL_SEGMENTS
    return [name for name, _ in segments]


def compose(filing, request):
    first_new = find(filing, request, REVENUE, {SEGMENT: NEW_SEGMENTS[0][1]})
    segments = ORIGINAL_SEGMENTS if isinstance(first_new, Missing) else NEW_SEGMENTS
    result = Composition()
    for name, member in segments:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
