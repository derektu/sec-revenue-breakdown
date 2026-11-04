"""KO 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class KOParser(IssuerParser):
    ticker = "KO"
    rules = {
        "reported": {
            "Asia Pacific": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:A.PacificMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Bottling Investments": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:BottlingInvestmentsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Corporate": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Eliminations": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "srt:ConsolidationEliminationsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Europe, Middle East, and Africa": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:EuropeMiddleEastAfricaMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Global Ventures": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:GlobalVenturesMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Latin America": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:LatinAmericaSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "North America": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ko:NorthAmericaSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        }
    }
    aliases = [
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:EuropeMiddleEastAfricaMember",
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:EuropeMiddleEastAfricaMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:LatinAmericaSegmentMember",
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:LatinAmericaSegmentMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:NorthAmericaSegmentMember",
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:NorthAmericaSegmentMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:A.PacificMember",
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:PacificMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:BottlingInvestmentsMember",
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:BottlingInvestmentsMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember"
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:CorporateMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "srt:ConsolidationEliminationsMember"
            },
            "end": "2025-09-26",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:EliminationsMember"
            },
            "start": "2024-09-27",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:A.PacificMember",
            },
            "end": "2024-12-31",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:A.PacificMember"
            },
            "start": "2024-12-31",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ko:GlobalVenturesMember",
            },
            "end": "2024-12-31",
            "id": "ko-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "ko:GlobalVenturesMember"
            },
            "start": "2024-09-27",
        },
    ]

    def categories(self, period, basis):
        rules = dict(self.rules[basis])
        if period > "2024-12-31":
            rules.pop("Global Ventures", None)
        return rules
