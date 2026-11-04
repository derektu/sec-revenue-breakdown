"""PG 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class PGParser(IssuerParser):
    ticker = "PG"
    rules = {
        "reported": {
            "Baby, Feminine, and Familycare": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pg:BabyFeminineFamilyCareSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Beauty": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pg:BeautySegmentMember",
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
            "Fabric and Homecare": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pg:FabricHomeCareSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Grooming": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pg:GroomingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Healthcare": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pg:HealthCareSegmentMember",
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
    aliases = []
