"""UPS：營運分部（U.S. Domestic Package、International Package）與 Supply Chain Solutions／Other revenues。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（國內包裹、國際包裹、供應鏈），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "UPS"
VIEW = "business_segment"
TOTAL = "Consolidated revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
PACKAGES = (
    ("U.S. Domestic Package", "ups:USDomesticPackageMember", "ups:U.S.DomesticPackageSegmentMember"),
    ("International Package", "ups:InternationalPackageMember", "ups:InternationalSegmentMember"),
)
SUPPLY_CHAIN = "Supply Chain Solutions"
OTHER = "Other revenues"
SUPPLY_CHAIN_MEMBER = "ups:SupplyChainSolutionsMember"
# FY2023 10-K（期末 2023-12-31）的包裹分部 fact 另帶 OperatingSegmentsMember；更早與 2024 年的申報只帶分部軸。
FY2023_10K = ("2023-10-01", "2023-12-31")
# 期末 2025-01-01 起的申報：包裹分部改用新成員並帶 OperatingSegmentsMember；第三類只以分部表營收調節的 Other revenues 列示。
NEW_MEMBERS_FROM = "2025-01-01"
# Other revenues 與 Supply Chain Solutions 是同一塊非報告分部營收；證據見 parser.md 的「Supply Chain Solutions 與 Other revenues」。
FORMER_NAMES = {OTHER: (SUPPLY_CHAIN,)}


def categories(day):
    names = [name for name, _, _ in PACKAGES]
    return names + ([OTHER] if day >= NEW_MEMBERS_FROM else [SUPPLY_CHAIN])


def compose(filing, request):
    period = filing.report_date
    result = Composition()
    for name, old, new in PACKAGES:
        if period >= NEW_MEMBERS_FROM:
            dimensions = {**OPERATING, SEGMENT: new}
        elif FY2023_10K[0] <= period <= FY2023_10K[1]:
            dimensions = {**OPERATING, SEGMENT: old}
        else:
            dimensions = {SEGMENT: old}
        put(result, "category", name, find(filing, request, REVENUE, dimensions))
    if period >= NEW_MEMBERS_FROM:
        # 2025 年各 10-Q 以兩種寫法標示同一個數字，FY2025 10-K 起只有 CorporateNonSegmentMember。
        put(
            result,
            "category",
            OTHER,
            one_of(
                filing,
                request,
                (REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}),
                (REVENUE, {SEGMENT: SUPPLY_CHAIN_MEMBER}),
            ),
        )
    else:
        put(result, "category", SUPPLY_CHAIN, find(filing, request, REVENUE, {SEGMENT: SUPPLY_CHAIN_MEMBER}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
