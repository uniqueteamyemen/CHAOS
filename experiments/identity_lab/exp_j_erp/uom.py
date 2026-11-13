"""Unit-of-measure handling with an explicit category check.

A conversion is allowed only inside one category. Units to kilograms is not a factor question:
for a product whose category is *count*, no weight conversion exists unless the product itself
declares a unit weight — and that is a product fact, not a UoM fact.
"""
from __future__ import annotations

CATEGORY = {
    "unit": "count", "dozen": "count",
    "kg": "weight", "g": "weight",
    "l": "volume", "ml": "volume",
}
TO_REF = {"unit": 1.0, "dozen": 12.0, "kg": 1.0, "g": 0.001, "l": 1.0, "ml": 0.001}


def convert(qty: float, src: str, dst: str) -> tuple[float | None, str]:
    """Direction is handled by the ratio, so kg->g and g->kg both work."""
    src, dst = (src or "").lower(), (dst or "").lower()
    if src not in CATEGORY or dst not in CATEGORY:
        return None, f"unknown_uom:{src or '?'}->{dst or '?'}"
    if CATEGORY[src] != CATEGORY[dst]:
        return None, f"uom_category_mismatch:{CATEGORY[src]}->{CATEGORY[dst]}"
    if TO_REF[dst] == 0:
        return None, "zero_factor"
    return qty * TO_REF[src] / TO_REF[dst], "ok"
