"""iXBRL 數字規則：由 fact 的顯示文字、format、scale 與 sign 算出整數美元，以及 `format` 屬性的正規化。

fact 索引（`xbrl.py`）與證據元件（`evidence.py`）都用這個規則，兩者的數值因此一致。讀快照時也以這個規則
重算數值，快照不保存換算結果，改規則不需要重產快照。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

SUPPORTED_FORMATS = {"", "num-dot-decimal", "numdotdecimal", "fixed-zero", "zerodash"}
ZERO_FORMATS = {"fixed-zero", "zerodash"}
NEGATIVE_MARKS = ("-", "−", "(", ")")


def transform_name(attribute: str | None) -> str:
    """`format` 屬性的 transform 本地名稱，小寫；沒有 format 屬性時為空字串。"""
    return (attribute or "").split(":")[-1].lower()


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
