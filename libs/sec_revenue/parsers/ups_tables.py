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
