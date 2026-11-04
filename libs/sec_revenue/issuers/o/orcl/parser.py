"""ORCL 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class ORCLParser(IssuerParser):
    ticker = "ORCL"
    rules = {
        "reported": {
            "Cloud": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:CloudRevenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "orcl:CloudRevenuesMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Cloud License and On-Premise License": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:CloudLicenseAndOnPremiseLicenseRevenue",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Cloud Services and License Support": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:CloudServicesAndLicenseSupportRevenue",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "orcl:CloudServicesAndLicenseSupportMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Hardware": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:HardwareRevenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "orcl:HardwareBusinessMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Services": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:SalesRevenueServicesNet1",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "orcl:ServicesBusinessMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Software": {
                "alternatives": [
                    [
                        {
                            "concept": "orcl:SoftwareRevenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "orcl:SoftwareRevenuesMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
        }
    }
    aliases = []

    def categories(self, period, basis):
        active = ["Services", "Hardware"] + (
            [
                "Cloud License and On-Premise License",
                "Cloud Services and License Support",
            ]
            if period <= "2025-05-31"
            else ["Cloud", "Software"]
        )
        return {k: v for k, v in self.rules[basis].items() if k in active}
