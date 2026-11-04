"""PLD 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class PLDParser(IssuerParser):
    ticker = "PLD"
    rules = {
        "reported": {
            "Development management and other": {
                "alternatives": [
                    [
                        {
                            "concept": "pld:OtherRealEstateRevenue",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "pld:OtherRealEstateRevenue1",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Rental": {
                "alternatives": [
                    [
                        {
                            "concept": "pld:RentalRevenue",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Strategic capital": {
                "alternatives": [
                    [
                        {
                            "concept": "pld:ManagementFeesRevenue",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "pld:ManagementFeesRevenue1",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Total revenues": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "total_not_component",
            },
        }
    }
    aliases = []
