"""CMCSA：五個營運分部與 Corporate and Other，另有 Eliminations 調節項。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact, sum_of

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
REVENUES = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
BUSINESS_UNIT = "cmcsa:BusinessUnitAxis"
CONNECTIVITY = {BUSINESS_UNIT: "cmcsa:ConnectivityAndPlatformsMember"}
CONTENT = {BUSINESS_UNIT: "cmcsa:ContentAndExperiencesMember"}
# 定義以申報期末日切換，相鄰的生效期間首尾相接：
# - FY2023 10-K（期末 2023-12-31）的分部 fact 是 us-gaap:Revenues，並多帶事業群軸。
# - 期末 2024-03-31 以前，Corporate and Other 與 Eliminations 依事業群分成兩個 fact，相加成一類；之後各為一個 fact。
FY2023_10K = ("2023-12-31", "2023-12-31")
SPLIT_UNTIL = "2024-03-31"


def segment(name: str, member: str, unit: dict):
    return Category(
        name,
        define(fact(REVENUE, {**OPERATING, SEGMENT: member}), effective(None, "2023-12-30")),
        define(fact(REVENUES, {**unit, **OPERATING, SEGMENT: member}), effective(*FY2023_10K)),
        define(fact(REVENUE, {**OPERATING, SEGMENT: member}), effective("2024-01-01", None)),
    )


def corporate(concept: str):
    return sum_of(
        fact(concept, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}),
        fact(concept, {**CONTENT, CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}),
    )


def eliminations(concept: str):
    return sum_of(
        fact(concept, {**CONTENT, CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}),
        fact(concept, {BUSINESS_UNIT: "cmcsa:InterBusinessUnitEliminationsMember", CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}),
    )


def split_then(split, single):
    return (
        define(split(REVENUE), effective(None, "2023-12-30")),
        define(split(REVENUES), effective(*FY2023_10K)),
        define(split(REVENUE), effective("2024-01-01", SPLIT_UNTIL)),
        define(single, effective("2024-04-01", None)),
    )


SPEC = CompanySpec(
    ticker="CMCSA",
    view="business_segment",
    categories=(
        segment("Residential Connectivity & Platforms", "cmcsa:ResidentialConnectivityAndPlatformsSegmentMember", CONNECTIVITY),
        segment("Business Services Connectivity", "cmcsa:BusinessServicesConnectivitySegmentMember", CONNECTIVITY),
        segment("Media", "cmcsa:MediaSegmentMember", CONTENT),
        segment("Studios", "cmcsa:StudiosSegmentMember", CONTENT),
        segment("Theme Parks", "cmcsa:ThemeParksSegmentMember", CONTENT),
        Category(
            "Corporate and Other",
            *split_then(corporate, fact(REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"})),
        ),
    ),
    reconciling=(
        Category(
            "Eliminations",
            *split_then(eliminations, fact(REVENUE, {CONSOLIDATION: "srt:ConsolidationEliminationsMember"})),
        ),
    ),
    total=Category(
        "Total",
        define(fact(REVENUE), effective(None, "2023-12-30")),
        define(fact(REVENUES), effective(*FY2023_10K)),
        define(fact(REVENUE), effective("2024-01-01", None)),
    ),
)
