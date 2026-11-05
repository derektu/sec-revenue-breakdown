"""BRK-B：營運分部（保險、BNSF、BHE、製造、McLane、Pilot、服務零售）與公司層級調節。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"


def segment(member: str):
    return fact(REVENUE, {CONSOLIDATION: "us-gaap:OperatingSegmentsMember", SEGMENT: member})


SPEC = CompanySpec(
    ticker="BRK-B",
    view="business_segment",
    categories=(
        Category("Insurance", segment("brka:BerkshireHathawayInsuranceGroupMember")),
        Category("BNSF", segment("brka:BurlingtonNorthernSantaFeCorporationMember")),
        Category("BHE", segment("brka:BerkshireHathawayEnergyCompanyMember")),
        Category("Manufacturing", segment("brka:ManufacturingBusinessesMember")),
        Category("McLane", segment("brka:McLaneCompanyMember")),
        Category("Pilot", segment("brka:PilotTravelCentersLLCMember")),
        Category("Service and retailing", segment("brka:ServiceAndRetailingBusinessesMember")),
        Category(
            "Corporate, eliminations and other",
            fact(REVENUE, {CONSOLIDATION: "brka:CorporateReconcilingItemsAndEliminationsMember"}),
        ),
    ),
    total=Category("Revenues", fact(REVENUE)),
)
