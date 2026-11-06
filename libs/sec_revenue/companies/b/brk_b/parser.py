"""BRK-B：營運分部（保險、BNSF、BHE、製造、McLane、Pilot、服務零售）與公司層級調節。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（保險、鐵路、能源、製造、經銷、零售等子公司群），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "BRK-B"
VIEW = "business_segment"
TOTAL = "Revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
SEGMENTS = (
    ("Insurance", "brka:BerkshireHathawayInsuranceGroupMember"),
    ("BNSF", "brka:BurlingtonNorthernSantaFeCorporationMember"),
    ("BHE", "brka:BerkshireHathawayEnergyCompanyMember"),
    ("Manufacturing", "brka:ManufacturingBusinessesMember"),
    ("McLane", "brka:McLaneCompanyMember"),
    ("Pilot", "brka:PilotTravelCentersLLCMember"),
    ("Service and retailing", "brka:ServiceAndRetailingBusinessesMember"),
)
CORPORATE = "Corporate, eliminations and other"


def categories(day):
    return [name for name, _ in SEGMENTS] + [CORPORATE]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {**OPERATING, SEGMENT: member}))
    put(result, "category", CORPORATE, find(filing, request, REVENUE, {CONSOLIDATION: "brka:CorporateReconcilingItemsAndEliminationsMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
