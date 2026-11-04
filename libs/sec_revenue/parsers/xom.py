"""XOM 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class XOMParser(IssuerParser):
    ticker = "XOM"
    rules = {
        "segments": {
            "上游": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:UpstreamMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:UpstreamMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "gross_sales_scope_candidate",
            },
            "分部間收入": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:IntersegmentEliminationMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "definition_pending",
            },
            "化工產品": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:ChemicalProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:ChemicalProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "gross_sales_scope_candidate",
            },
            "特種產品": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:SpecialtyProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:SpecialtyProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "gross_sales_scope_candidate",
            },
            "能源產品": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:EnergyProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "xom:EnergyProductsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "gross_sales_scope_candidate",
            },
        }
    }
    aliases = []

    def parse(self, records):
        """分部 all-income 與 gross sales 使用不同 basis，歷史 Q2 明列選用口徑。"""
        from .xom_tables import RevenueTables
        import json

        reader = RevenueTables(self.repository, self.output)
        manifest = reader.manifest("research/xom-sec-dom-20261104/manifest.json")
        facts = []
        gross = []
        for entry in manifest["files"]:
            raw = reader.read(entry, self.ticker, "dom_snapshot")
            facts.extend(reader.parse_snapshot(json.loads(raw), entry["sha256"]))
        for entry in manifest["supplemental_page_text"]:
            raw = reader.read(entry, self.ticker, "web_text")
            gross.extend(reader.parse_sales_page(raw.decode(), entry["sha256"]))
        labels = {
            **reader.LABELS,
            "Other revenues": "Other revenues",
            "分部間收入": "分部間收入",
            "其他收入": "其他收入",
            "Income from equity affiliates": "Income from equity affiliates",
        }
        periods = [
            "2024-12-31",
            "2025-03-31",
            "2025-06-30",
            "2025-09-30",
            "2025-12-31",
            "2026-03-31",
            "2026-06-30",
        ]
        rows = reader.observations(facts, self.ticker, "segments", labels, periods)
        for row in rows:
            if row["period_end"] in ("2025-06-30", "2026-06-30"):
                row["outputs"] = {
                    k: v
                    for k, v in row["outputs"].items()
                    if k in reader.LABELS or k == "分部間收入"
                }
                for label, reported in reader.LABELS.items():
                    found = [
                        f
                        for f in gross
                        if f["label"] == reported
                        and f["enddate"] == row["period_end"]
                        and f["kind"] == "Q"
                    ]
                    if len(found) != 1:
                        raise ValueError("XOM gross sales 運算元缺漏")
                    row["outputs"][label] = {
                        "status": "observed",
                        "value_usd": found[0]["value"],
                        "SEC_operands": found,
                        "weights": [1],
                        "rule_id": "xom-reviewed-q2-gross-sales-basis",
                    }
        # 新 CIK 的最新季仍從原始 facts cache 重算；與舊 CIK 表格不混接。
        from sec_revenue.engines import SelectionEngine

        latest = [
            r
            for r in super().parse(records)
            if r["period_end"] == "2026-09-30" and r["basis"] == "segments"
        ]
        for row in latest:
            record = next(
                r for r in records if r["filing"]["reportDate"] == "2026-09-30"
            )
            from sec_revenue.engines import QuarterEngine

            pool, bad = QuarterEngine().quarter(record["facts"], "2026-09-30", [])
            selector = SelectionEngine()

            # 最新申報完整 all-income 分部與扣回合併投資收入，保留真實對帳口徑。
            def term(dimensions, weight=1):
                return {
                    "concept": "us-gaap:Revenues",
                    "dimensions": dimensions,
                    "unit": "iso4217:USD",
                    "weight": weight,
                }

            for label, member in {
                "上游": "UpstreamMember",
                "能源產品": "EnergyProductsMember",
                "化工產品": "ChemicalProductsMember",
                "特種產品": "SpecialtyProductsMember",
            }.items():
                terms = [
                    term(
                        {
                            "us-gaap:StatementBusinessSegmentsAxis": "xom:" + member,
                            "srt:StatementGeographicalAxis": geo,
                        }
                    )
                    for geo in ("country:US", "us-gaap:NonUsMember")
                ]
                row["outputs"][label] = selector.select(
                    {"alternatives": [terms]}, pool, bad
                )
            for label, dimensions, weight in [
                (
                    "Other revenues",
                    {"srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember"},
                    1,
                ),
                (
                    "Income from equity affiliates",
                    {
                        "srt:ProductOrServiceAxis": "xom:IncomeFromEquityAffiliatesMember"
                    },
                    -1,
                ),
                (
                    "其他收入",
                    {"srt:ProductOrServiceAxis": "xom:OtherRevenueMember"},
                    -1,
                ),
                (
                    "Sales and other operating revenue",
                    {
                        "srt:ProductOrServiceAxis": "xom:SalesAndOtherOperatingRevenueMember"
                    },
                    1,
                ),
                ("Total revenues and other income", {}, 1),
            ]:
                row["outputs"][label] = selector.select(
                    {"alternatives": [[term(dimensions, weight)]]}, pool, bad
                )
        rows.extend(latest)
        self.source_receipts = reader.receipts
        return rows
