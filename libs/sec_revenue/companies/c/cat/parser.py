"""CAT：營運分部（Construction Industries、Resource Industries、Energy & Transportation／Power & Energy、Financial Products、All Other）與公司層級項目及抵銷。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（營建機械、礦業機械、動力與能源、融資服務），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "CAT"
VIEW = "business_segment"
TOTAL = "Total sales and revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
ENERGY_TRANSPORTATION = "Energy & Transportation"
POWER_ENERGY = "Power & Energy"
# 期末 2025-09-30 的 10-Q 是最後一份列 Energy & Transportation 的申報；FY2025 10-K（期末 2025-12-31）起改名 Power & Energy。
LAST_ENERGY_TRANSPORTATION = "2025-09-30"
POWER_ENERGY_FROM = "2025-10-01"
SEGMENTS = (
    ("Construction Industries", "cat:ConstructionIndustriesMember", None, None),
    ("Resource Industries", "cat:ResourceIndustriesMember", None, None),
    (ENERGY_TRANSPORTATION, "cat:EnergyandTransportationMember", None, LAST_ENERGY_TRANSPORTATION),
    (POWER_ENERGY, "cat:PowerEnergyMember", POWER_ENERGY_FROM, None),
    ("Financial Products", "cat:FinancialProductsSegmentMember", None, None),
    ("All Other", "us-gaap:AllOtherSegmentsMember", None, None),
)
CORPORATE = "Corporate Items and Eliminations"


def _active(day, start, end):
    return (start is None or start <= day) and (end is None or day <= end)


def categories(day):
    return [name for name, _, start, end in SEGMENTS if _active(day, start, end)] + [CORPORATE]


def compose(filing, request):
    period = filing.report_date
    result = Composition()
    for name, member, start, end in SEGMENTS:
        if _active(period, start, end):
            put(result, "category", name, find(filing, request, REVENUE, {**OPERATING, SEGMENT: member}))
    # 分部表的同一列：FY2024 10-K 起用 EliminationsAndReconcilingItemsMember，更早的申報用 CorporateReconcilingItemsAndEliminationsMember。
    put(
        result,
        "category",
        CORPORATE,
        one_of(
            filing,
            request,
            (REVENUE, {CONSOLIDATION: "cat:EliminationsAndReconcilingItemsMember"}),
            (REVENUE, {CONSOLIDATION: "cat:CorporateReconcilingItemsAndEliminationsMember"}),
        ),
    )
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
