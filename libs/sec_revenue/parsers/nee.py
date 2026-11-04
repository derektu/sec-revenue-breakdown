"""NEE 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class NEEParser(IssuerParser):
    ticker = "NEE"
    rules = {
        "segments": {
            "Florida Power & Light Company (FPL)": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nee:FloridaPowerLightCompanyMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
                            "dimensions": {
                                "dei:LegalEntityAxis": "nee:FloridaPowerLightCompanyMember",
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nee:FloridaPowerLightCompanyMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "NextEra Energy Resources (NEER)": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "nee:NEERSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "公司和其他": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "nee:CorporateAndEliminationsMember"
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
        """僅 2024 FPL 年度分部與單一 legal entity 九月表的已審閱橋接。"""
        facts, conflicts = super().pool(records, index, engine)
        if records[index]["filing"]["reportDate"] != "2024-12-31":
            return facts, conflicts
        concept = "us-gaap:RegulatedAndUnregulatedOperatingRevenue"
        entity = {"dei:LegalEntityAxis": "nee:FloridaPowerLightCompanyMember"}
        scope = {
            **entity,
            "us-gaap:StatementBusinessSegmentsAxis": "nee:FloridaPowerLightCompanyMember",
            "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
        }
        annual = [
            f
            for f in records[index]["facts"]
            if f["concept"] == concept
            and f["dimensions"] == scope
            and f.get("startdate") == "2024-01-01"
            and f.get("enddate") == "2024-12-31"
        ]
        nine = [
            f
            for r in records
            for f in r["facts"]
            if r["filing"]["reportDate"] == "2024-09-30"
            and f["concept"] == concept
            and f["dimensions"] == entity
            and f.get("startdate") == "2024-01-01"
            and f.get("enddate") == "2024-09-30"
        ]
        a, bad = engine.dedupe(annual)
        n, other = engine.dedupe(nine)
        if len(a) == len(n) == 1 and not bad and not other:
            facts.append(
                dict(
                    a[0],
                    value=a[0]["value"] - n[0]["value"],
                    startdate="2024-10-01",
                    derivation="annual_minus_nine_months",
                    annual_evidence=a[0],
                    nine_month_evidence=n[0],
                    scope_bridge_rule_id="nee-fpl-2024-reported-segment-to-entity-reviewed",
                )
            )
        return facts, conflicts
