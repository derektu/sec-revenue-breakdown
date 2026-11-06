"""KO：營運類型（Concentrate operations、Finished product operations）。說明見 parser.md。"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "KO"
VIEW = "product"
TOTAL = "Net operating revenues"

REVENUE = "us-gaap:Revenues"
PRODUCT = "srt:ProductOrServiceAxis"
OPERATIONS = (
    ("Concentrate operations", "ko:ConcentrateOperationsMember", "ko:Netoperatingrevenuesrelatedtoconcentrateoperations"),
    ("Finished product operations", "ko:FinishedProductOperationsMember", "ko:Netoperatingrevenuesrelatedtofinishedproductoperations"),
)
# FY2023 10-K（期末 2023-12-31）以公司自訂 concept 標示兩類營收；前後的申報都用 us-gaap:Revenues × ProductOrServiceAxis。
# 切換點放在前一份申報（2023 年 Q3 10-Q，期末 2023-09-29）與下一份申報之間。
CUSTOM_FROM, CUSTOM_TO = "2023-09-30", "2023-12-31"


def categories(day):
    return [name for name, _, _ in OPERATIONS]


def compose(filing, request):
    custom = CUSTOM_FROM <= filing.report_date <= CUSTOM_TO
    result = Composition()
    for name, member, concept in OPERATIONS:
        term = find(filing, request, concept) if custom else find(filing, request, REVENUE, {PRODUCT: member})
        put(result, "category", name, term)
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
