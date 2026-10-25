"""Presentation only: preserve stored quantities and mapping semantics."""
import re

def quantity_unit(value):
    unit = (value or "").strip()
    return "" if unit == "原始商品单位" else unit

def quantity_text(value):
    return re.sub(r"(\d)[ \t]*原始商品单位", r"\1", value)
