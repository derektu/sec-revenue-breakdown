"""UNH 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class UNHParser(IssuerParser):
    ticker = "UNH"
    rules = {
        "reported": {
            "Eliminations": {
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
                    ],
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember",
                                "srt:MajorCustomersAxis": "unh:IntersegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "definition_pending",
            },
            "Optum": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "unh:TotalOptumMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "UnitedHealthcare": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "unh:UnitedhealthcareMember",
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
