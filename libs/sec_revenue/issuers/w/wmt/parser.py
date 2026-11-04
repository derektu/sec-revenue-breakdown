"""WMT 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class WMTParser(IssuerParser):
    ticker = "WMT"
    rules = {
        "segments": {
            "Sam's Club United States (U.S.)": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:SamsClubUSMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Walmart United States (U.S.)": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:WalmartUSMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "企業和支持": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:WalmartUSMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:WalmartInternationalMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:SamsClubUSMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": -1,
                        },
                    ]
                ],
                "role": "named_corporate_membership_and_other_income_residual",
            },
            "沃爾瑪國際": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "wmt:WalmartInternationalMember",
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

    def pool(self, records, index, engine):
        """歷史季取研究截止日前最新可用比較欄，拒絕依金額挑版本。"""
        target = records[index]["filing"]["reportDate"]
        latest = records[-1]["filing"]["reportDate"]
        if target == latest:
            return super().pool(records, index, engine)
        chosen = None
        for i, record in enumerate(records):
            if record["filing"]["reportDate"] == latest:
                continue
            candidate = engine.quarter(
                record["facts"], target, [f for r in records[:i] for f in r["facts"]]
            )
            if candidate[0]:
                chosen = candidate
        return chosen or ([], [])
