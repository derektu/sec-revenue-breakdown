"""UNH：營運分部（UnitedHealthcare、Optum Health、Optum Insight、Optum Rx）與公司層級抵銷。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact, one_of

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}


def segment(*members: str):
    variants = [fact(REVENUE, {**OPERATING, SEGMENT: m}) for m in members]
    return variants[0] if len(variants) == 1 else one_of(*variants)


SPEC = CompanySpec(
    ticker="UNH",
    view="business_segment",
    categories=(
        Category("UnitedHealthcare", segment("unh:UnitedhealthcareMember")),
        # 10-Q 與 10-K 的 Optum 分部成員只差大小寫。
        Category("Optum Health", segment("unh:OptumHealthMember", "unh:OptumhealthMember")),
        Category("Optum Insight", segment("unh:OptumInsightMember", "unh:OptuminsightMember")),
        Category("Optum Rx", segment("unh:OptumRxMember", "unh:OptumrxMember")),
        Category("Corporate and eliminations", fact(REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"})),
    ),
    reconciling=(Category("Optum eliminations", fact(REVENUE, {CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"})),),
    total=Category("Consolidated revenues", fact(REVENUE)),
)
