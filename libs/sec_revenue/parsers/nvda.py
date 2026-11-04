"""NVDA 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class NVDAParser(IssuerParser):
    ticker = "NVDA"
    rules = {
        "reported": {
            "Compute and Networking": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nvda:ComputeAndNetworkingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Graphics": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nvda:GraphicsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        },
        "segments": {
            "繪圖": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nvda:GraphicsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "計算與網絡": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nvda:ComputeAndNetworkingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        },
    }
    aliases = [
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "nvda:ComputeAndNetworkingSegmentMember",
            },
            "evidence_urls": [
                "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20241027.htm",
                "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
            ],
            "id": "nvda-fy2025-compute",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "nvda:ComputeAndNetworkingMember",
            },
            "report_dates": ["2024-10-27"],
            "review_basis": "兩份歷史申報均列同名兩營運分部；只在指定舊申報與完整維度接合，並非通用名稱模糊匹配。",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "nvda:GraphicsSegmentMember",
            },
            "evidence_urls": [
                "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20241027.htm",
                "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
            ],
            "id": "nvda-fy2025-graphics",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "nvda:GraphicsMember",
            },
            "report_dates": ["2024-10-27"],
            "review_basis": "兩份歷史申報均列同名兩營運分部；只在指定舊申報與完整維度接合，並非通用名稱模糊匹配。",
        },
    ]
