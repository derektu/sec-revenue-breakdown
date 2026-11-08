"""QCOM：QCT、QTL、QSI 與各期申報列出的營收調節分類。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。說明見 parser.md。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "QCOM"
VIEW = "business_segment"
TOTAL = "Total revenues"

REVENUE = "us-gaap:Revenues"
CONTRACT_REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
RECONCILING = {CONSOLIDATION: "us-gaap:MaterialReconcilingItemsMember"}
OTHER = {**RECONCILING, SEGMENT: "us-gaap:AllOtherSegmentsMember"}
UNALLOCATED = {**RECONCILING, "srt:LitigationCaseAxis": "us-gaap:LicensingAgreementsMember"}
SEGMENTS = (("QCT", "qcom:QctMember"), ("QTL", "qcom:QtlMember"), ("QSI", "qcom:QsiMember"))
# 0000804328-25-000085（期末 2025-09-28）首次主申報改列調節明細，取 Q4 起日。
SPLIT_START = "2025-06-30"
# 0000804328-26-000017（期末 2025-12-28）未列 Unallocated revenues，取 Q1 起日。
OMITTED_START = "2025-09-29"
# 0000804328-26-000061（期末 2026-03-29）恢復列示零值，取 Q2 起日。
RESTORED_START = "2025-12-29"


def categories(day):
    names = [name for name, _ in SEGMENTS]
    if day < SPLIT_START:
        return names + ["Reconciling items"]
    names.append("Nonreportable segments")
    if not OMITTED_START <= day < RESTORED_START:
        names.append("Unallocated revenues")
    return names


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, one_of(
            filing, request,
            (REVENUE, {SEGMENT: member}),
            (REVENUE, {**OPERATING, SEGMENT: member}),
            (CONTRACT_REVENUE, {**OPERATING, SEGMENT: member}),
        ))
    other = find(filing, request, REVENUE, OTHER)
    if isinstance(other, Missing):
        put(result, "category", "Reconciling items", find(filing, request, REVENUE, RECONCILING))
    else:
        put(result, "category", "Nonreportable segments", other)
        unallocated = find(filing, request, REVENUE, UNALLOCATED)
        if not isinstance(unallocated, Missing):
            put(result, "category", "Unallocated revenues", unallocated)
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
