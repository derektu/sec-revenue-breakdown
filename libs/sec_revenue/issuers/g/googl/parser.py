"""GOOGL 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class GOOGLParser(IssuerParser):
    ticker = "GOOGL"
    rules = {
        "reported": {
            "Google Cloud": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleCloudMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Google Network": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "goog:GoogleNetworkMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Google Search & Other": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "goog:GoogleSearchOtherMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Google Subscriptions, Platforms & Devices": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "goog:SubscriptionsPlatformsAndDevicesRevenueMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Hedging Gains": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleCloudMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleCloudMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                    ],
                ],
                "role": "sec_reported_segment_reconciliation_hedging",
            },
            "Other Bets": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "YouTube Ads": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "goog:YouTubeAdvertisingRevenueMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "goog:GoogleServicesMember",
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
