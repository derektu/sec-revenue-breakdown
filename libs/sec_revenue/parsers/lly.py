"""LLY 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class LLYParser(IssuerParser):
    ticker = "LLY"
    rules = {
        "reported": {
            "Cardiometabolic": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "lly:CardiometabolicHealthMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Immunology": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "lly:ImmunologyMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Neuroscience": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "lly:NeuroscienceMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Oncology": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "lly:OncologyMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Other": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "us-gaap:ProductAndServiceOtherMember"
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
                "srt:ProductOrServiceAxis": "us-gaap:ProductAndServiceOtherMember",
                "srt:StatementGeographicalAxis": "country:US",
            },
            "end": "2025-12-31",
            "id": "lly-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "lly:OtherProductTotalMember",
                "srt:StatementGeographicalAxis": "country:US",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ProductOrServiceAxis": "us-gaap:ProductAndServiceOtherMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
            },
            "end": "2025-12-31",
            "id": "lly-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "lly:OtherProductTotalMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ProductOrServiceAxis": "us-gaap:ProductAndServiceOtherMember"
            },
            "end": "2025-09-30",
            "id": "lly-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ProductOrServiceAxis": "lly:OtherProductTotalMember"
            },
            "start": "2024-09-30",
        },
    ]

    def normalize(self, record: dict) -> dict:
        """年度只有 US/non-US 時才合計全球；不得覆蓋直接全球列。"""
        record = super().normalize(record)
        from sec_revenue.engines import QuarterEngine

        engine = QuarterEngine()
        additions = []
        for terms in self.rules["reported"].values():
            term = terms["alternatives"][0][0]
            groups = {}
            for fact in record["facts"]:
                dims = fact["dimensions"]
                geo = dims.get("srt:StatementGeographicalAxis")
                if (
                    fact["concept"] == term["concept"]
                    and dims
                    == {**term["dimensions"], "srt:StatementGeographicalAxis": geo}
                    and geo in ("country:US", "us-gaap:NonUsMember")
                ):
                    groups.setdefault((fact["startdate"], fact["enddate"]), []).append(
                        fact
                    )
            for (start, end), found in groups.items():
                if any(
                    f["concept"] == term["concept"]
                    and f["dimensions"] == term["dimensions"]
                    and f.get("startdate") == start
                    and f.get("enddate") == end
                    for f in record["facts"]
                ):
                    continue
                unique, bad = engine.dedupe(found)
                if len(unique) == 2 and not bad:
                    additions.append(
                        dict(
                            unique[0],
                            dimensions=term["dimensions"],
                            value=sum(f["value"] for f in unique),
                            aggregation_evidence=unique,
                            normalization_rule_id="lly-us-plus-non-us-product",
                        )
                    )
        record["facts"].extend(additions)
        return record
