"""inline XBRL 原文的共用讀取規則：HTML 解析、表格編號、文字正規化與數值換算。

fact 解析（`xbrl.py`）與證據元件（`evidence.py`）都用這裡的規則，兩者的表格編號與數值因此一致。
這些規則決定 XBRL fact 快照的內容，列入快照的解析器 hash（見 `snapshot.py`）。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from lxml import html


def parse_html(raw: bytes):
    """以 lxml HTML parser 解析原文，不載入任何外部資源。"""
    return html.fromstring(raw, parser=html.HTMLParser(no_network=True))


def numbered_tables(root) -> list:
    """依文件順序列舉 `<table>`；串列位置就是表格編號。"""
    return list(root.iter("table"))


def clean_text(text: str) -> str:
    return " ".join(text.split())



SUPPORTED_FORMATS = {"", "num-dot-decimal", "numdotdecimal", "fixed-zero", "zerodash"}
ZERO_FORMATS = {"fixed-zero", "zerodash"}
NEGATIVE_MARKS = ("-", "−", "(", ")")


def ix_number(raw: str, transform: str, scale: str, sign: str | None) -> tuple[int | None, str | None]:
    """依 iXBRL 規則由顯示文字、format、scale 與 sign 算出整數美元；不符時回傳 (None, 原因)。

    正負號只由 `sign="-"` 表示；顯示文字帶負號或括號時視為無法解析，不自行推斷。
    """
    if transform not in SUPPORTED_FORMATS:
        return None, f"不支援的數字格式 {transform}"
    if transform in ZERO_FORMATS:
        cleaned = "0"
    else:
        if any(mark in raw for mark in NEGATIVE_MARKS):
            return None, f"顯示文字 {raw!r} 帶負號；iXBRL 的正負號應由 sign 屬性表示"
        cleaned = raw.replace(",", "").replace(" ", "")
    try:
        value = Decimal(cleaned) * Decimal(10) ** int(scale)
    except (InvalidOperation, ValueError):
        return None, f"無法解析數字 {raw!r}"
    if not value.is_finite():
        return None, f"數值不是有限數：{raw!r}"
    if sign == "-":
        value = -value
    if value != value.to_integral_value():
        return None, f"不是整數美元：{raw!r}"
    return int(value), None
