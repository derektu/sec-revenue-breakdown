"""UNH：營運分部（UnitedHealthcare、Optum Health、Optum Insight、Optum Rx）與公司層級抵銷。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（健康保險、醫療服務、資訊與科技服務、藥品福利管理），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "UNH"
VIEW = "business_segment"
TOTAL = "Consolidated revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
# 10-Q 與 10-K 的 Optum 分部成員只差大小寫：每個分部列出兩種寫法。
SEGMENTS = (
    ("UnitedHealthcare", ("unh:UnitedhealthcareMember",)),
    ("Optum Health", ("unh:OptumHealthMember", "unh:OptumhealthMember")),
    ("Optum Insight", ("unh:OptumInsightMember", "unh:OptuminsightMember")),
    ("Optum Rx", ("unh:OptumRxMember", "unh:OptumrxMember")),
)
CORPORATE = "Corporate and eliminations"
OPTUM_ELIMINATIONS = "Optum eliminations"


def categories(day):
    return [name for name, _ in SEGMENTS] + [CORPORATE, OPTUM_ELIMINATIONS]


def _segment(filing, request, members):
    if len(members) == 1:
        return find(filing, request, REVENUE, {**OPERATING, SEGMENT: members[0]})
    return one_of(filing, request, *((REVENUE, {**OPERATING, SEGMENT: m}) for m in members))


def compose(filing, request):
    result = Composition()
    for name, members in SEGMENTS:
        put(result, "category", name, _segment(filing, request, members))
    put(result, "category", CORPORATE, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}))
    put(result, "reconciling", OPTUM_ELIMINATIONS, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
