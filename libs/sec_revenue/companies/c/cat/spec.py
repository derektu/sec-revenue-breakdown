"""CAT：營運分部（Construction Industries、Resource Industries、Energy & Transportation／Power & Energy、Financial Products、All Other）與公司層級項目及抵銷。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact, one_of

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
# Energy & Transportation 在 FY2025 10-K（期末 2025-12-31）起改名 Power & Energy；名稱照各期申報，定義以申報期末日切換，
# 相鄰的生效期間首尾相接。
ENERGY_TRANSPORTATION = (None, "2025-09-30")
POWER_ENERGY_FROM = "2025-10-01"


def segment(*members: str):
    variants = [fact(REVENUE, {**OPERATING, SEGMENT: m}) for m in members]
    return variants[0] if len(variants) == 1 else one_of(*variants)


SPEC = CompanySpec(
    ticker="CAT",
    view="business_segment",
    categories=(
        Category("Construction Industries", segment("cat:ConstructionIndustriesMember")),
        Category("Resource Industries", segment("cat:ResourceIndustriesMember")),
        Category("Energy & Transportation", define(segment("cat:EnergyandTransportationMember"), effective(*ENERGY_TRANSPORTATION))),
        Category("Power & Energy", define(segment("cat:PowerEnergyMember"), effective(POWER_ENERGY_FROM, None))),
        Category("Financial Products", segment("cat:FinancialProductsSegmentMember")),
        Category("All Other", segment("us-gaap:AllOtherSegmentsMember")),
        # FY2023 10-K 至 2024 年 Q3 10-Q 用 cat:CorporateReconcilingItemsAndEliminationsMember；FY2024 10-K 起用
        # cat:EliminationsAndReconcilingItemsMember。兩者是分部表的同一列；2024 年 Q4 的年度與九個月累計分別在兩種寫法的申報中。
        Category(
            "Corporate Items and Eliminations",
            one_of(
                fact(REVENUE, {CONSOLIDATION: "cat:EliminationsAndReconcilingItemsMember"}),
                fact(REVENUE, {CONSOLIDATION: "cat:CorporateReconcilingItemsAndEliminationsMember"}),
            ),
        ),
    ),
    total=Category("Total sales and revenues", fact(REVENUE)),
)
