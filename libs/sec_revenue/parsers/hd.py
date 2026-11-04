"""HD 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class HDParser(IssuerParser):
    ticker = "HD"
    # Home Depot 的年度名稱採起始年度，而非翌年一／二月結帳年份。
    fiscal_year_label_offset = -1
    rules = {
        "reported": {
            "Building Materials": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Decor": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Hardlines": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Other": {
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
                "role": "definition_pending",
            },
        }
    }
    aliases = [
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-11-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "start": "2024-07-28",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-11-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "start": "2024-07-28",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-11-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "start": "2024-07-28",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-02-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineBuildingMaterialsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
            },
            "start": "2025-02-02",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-02-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineDcorMember",
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
            },
            "start": "2025-02-02",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                "us-gaap:StatementBusinessSegmentsAxis": "hd:PrimarySegmentMember",
            },
            "end": "2025-02-02",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "hd:MajorProductLineHardlinesMember",
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember",
            },
            "start": "2025-02-02",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember"
            },
            "end": "2024-10-27",
            "id": "hd-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "hd:OtherSegmentMember"
            },
            "start": "2024-07-28",
        },
    ]
