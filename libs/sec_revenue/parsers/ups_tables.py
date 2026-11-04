"""公司表格解析器；由已核對規則移植，維持表頭、期間與對帳拒絕條件。"""

import re
import hashlib
from decimal import Decimal
from datetime import date
from lxml import html
from .table_support import TableSourceReader


class RevenueTables(TableSourceReader):
    UPS_URL = "https://www.sec.gov/Archives/edgar/data/1090727/000162828026067381/exhibit991-earningspressre.htm"

    def parse_ups_sec_page(self, text):
        if text.splitlines()[0] != "www.sec.gov (" + self.UPS_URL + ")":
            raise ValueError("SEC response URL differs")
        lines = []
        for line in text.splitlines():
            match = re.match("L(\\d+): (.*)", line)
            if match:
                lines.append((int(match[1]), match[2]))
        body = "\n".join((t for _, t in lines))
        if "UPS RELEASES 3Q 2026 EARNINGS" not in body or "Exhibit 99.1" not in body:
            raise ValueError("Wrong SEC exhibit or quarter")
        sections = [
            ("Domestic Package", "U.S. Domestic Segment"),
            ("International Package", "International Segment"),
            ("Supply Chain and Freight", "Supply Chain Solutions1"),
        ]
        result = {}
        for index, (label, heading) in enumerate(sections):
            starts = [i for i, (_, line) in enumerate(lines) if line == heading]
            if len(starts) != 1:
                raise ValueError("Missing or duplicate SEC segment heading")
            start = starts[0]
            end = next(
                (
                    i
                    for i in range(start + 1, len(lines))
                    if index + 1 < len(sections)
                    and lines[i][1] == sections[index + 1][1]
                ),
                len(lines),
            )
            block = lines[start:end]
            revenues = [
                (number, line)
                for number, line in block
                if line.startswith("Revenue  |")
            ]
            if len(revenues) != 1:
                raise ValueError("Missing or duplicate SEC revenue row")
            number, line = revenues[0]
            header = "\n".join((t for n, t in block if n < number))
            if (
                not re.search("3Q 2026\\s+\\| Non-GAAP Adjusted 3Q 2026", header)
                or "3Q 2025" not in header
            ):
                raise ValueError("Wrong current/prior SEC columns")
            cells = [s.strip() for s in line.split("|")]
            if len(cells) < 5 or cells[2]:
                raise ValueError("Unreviewed revenue table layout")
            current = re.fullmatch("\\$([\\d,]+) M", cells[1])
            prior = re.fullmatch("\\$([\\d,]+) M", cells[3])
            if not current or not prior:
                raise ValueError("Revenue unit or signed value not reviewed")
            result[label] = {
                "value_usd": int(current[1].replace(",", "")) * 1000000,
                "line": number,
            }
        return result

    def parse_earnings_html(self, raw: bytes, url: str, digest: str) -> list[dict]:
        """只有已審閱的 2026Q3 exhibit；檢查 GAAP／adjusted 與本期／前期欄。"""
        if url != self.UPS_URL:
            raise ValueError("UPS 未審閱的 earnings exhibit")
        root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
        nodes = list(root.iter())
        positions = {node: i for i, node in enumerate(nodes)}
        document = " ".join(" ".join(root.itertext()).split())
        if (
            "UPS RELEASES 3Q 2026 EARNINGS" not in document
            or "Exhibit 99.1" not in document
        ):
            raise ValueError("UPS exhibit 季別／身分不符")
        sections = [
            ("Domestic Package", "U.S. Domestic Segment"),
            ("International Package", "International Segment"),
            ("Supply Chain and Freight", "Supply Chain Solutions1"),
        ]
        boundaries = []
        for label, heading in sections:
            found = [
                n
                for n in nodes
                if n.tag in ("p", "h1", "h2", "h3", "h4")
                and " ".join(n.text_content().split()) == heading
            ]
            if len(found) != 1:
                raise ValueError("UPS segment heading 缺失／歧義")
            boundaries.append(positions[found[0]])
        tables = list(root.xpath("//table"))
        facts = []
        for i, (label, heading) in enumerate(sections):
            limit = boundaries[i + 1] if i + 1 < len(sections) else len(nodes)
            matches = []
            for table_index, table in enumerate(tables):
                if not boundaries[i] < positions[table] < limit:
                    continue
                rows = [
                    [" ".join(c.text_content().split()) for c in row.xpath("./td|./th")]
                    for row in table.xpath(".//tr")
                ]
                revenue = [
                    (j, row)
                    for j, row in enumerate(rows)
                    if row and row[0] == "Revenue"
                ]
                if not revenue:
                    continue
                if len(revenue) != 1:
                    raise ValueError("UPS revenue 列歧義")
                row_index, row = revenue[0]
                caption = " ".join(
                    cell for header in rows[:row_index] for cell in header
                )
                if (
                    not re.search(r"3Q 2026\s+Non-GAAP Adjusted 3Q 2026", caption)
                    or "3Q 2025" not in caption
                ):
                    raise ValueError("UPS GAAP／adjusted 欄位異動")
                values = re.findall(r"\$\s*([\d,]+)\s*M\b", " ".join(row[1:]))
                if len(values) != 2:
                    raise ValueError("UPS 本期／前期收入或單位異動")
                matches.append(
                    {
                        "concept": "sec-table:SegmentRevenue",
                        "dimensions": {"reported_segment": label},
                        "unit": "iso4217:USD",
                        "value": int(values[0].replace(",", "")) * 1_000_000,
                        "decimals": "-6",
                        "startdate": "2026-07-01",
                        "enddate": "2026-09-30",
                        "source_url": url,
                        "accession": "0001628280-26-067381",
                        "source_format": "original_html",
                        "source_artifact_sha256": digest,
                        "source_table_index": table_index,
                        "source_row_index": row_index,
                        "source_column": "3Q 2026 GAAP",
                    }
                )
            if len(matches) != 1:
                raise ValueError("UPS 唯一收入表缺失／歧義")
            facts.extend(matches)
        return facts
