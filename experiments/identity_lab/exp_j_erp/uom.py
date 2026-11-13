"""Odoo UoM normalization with Odoo's factor semantics.

Odoo defines factor as: 1 reference-UoM unit = factor * this-UoM units.
Therefore quantity_in_reference = quantity / source.factor.
Cross-category conversions are forbidden; product category membership is checked separately.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping


class UomNormalizationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _decimal(value: object, code: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise UomNormalizationError(code, f"invalid numeric value: {value!r}")
    if not result.is_finite():
        raise UomNormalizationError(code, f"non-finite numeric value: {value!r}")
    return result


def _factor(uom: Mapping) -> Decimal:
    value = _decimal(uom.get("factor"), "uom_factor_invalid")
    if value <= 0:
        raise UomNormalizationError("uom_factor_invalid", "factor must be > 0")
    return value


def normalize_quantity(
    quantity: object,
    from_uom: Mapping,
    to_uom: Mapping,
) -> Decimal:
    """Convert quantity from one Odoo UoM to another without rounding.

    Odoo's own _compute_quantity formula is (qty / from.factor) * to.factor.
    Both units must belong to the same uom.category.
    """
    from_category = str(from_uom.get("category_id") or "")
    to_category = str(to_uom.get("category_id") or "")
    if not from_category or not to_category:
        raise UomNormalizationError("uom_category_unresolved")
    if from_category != to_category:
        raise UomNormalizationError(
            "uom_category_mismatch", f"{from_category} != {to_category}"
        )
    qty = _decimal(quantity, "quantity_invalid")
    return (qty / _factor(from_uom)) * _factor(to_uom)


def normalize_to_reference(
    quantity: object,
    source_uom: Mapping,
    uoms_by_id: Mapping[str, Mapping],
    product_uom_category_id: object,
) -> tuple[Decimal, str]:
    """Convert a movement quantity to its category's reference UoM.

    The product's stock-UoM category is required. This prevents a product's
    movement from being accepted merely because some unrelated UoM exists.
    """
    source_category = str(source_uom.get("category_id") or "")
    product_category = str(product_uom_category_id or "")
    if not product_category:
        raise UomNormalizationError("product_uom_category_unresolved")
    if source_category != product_category:
        raise UomNormalizationError(
            "product_uom_category_mismatch",
            f"movement={source_category}, product={product_category}",
        )

    references = [
        (str(uid), uom)
        for uid, uom in uoms_by_id.items()
        if str(uom.get("category_id") or "") == source_category
        and str(uom.get("uom_type") or "").lower() == "reference"
    ]
    if len(references) != 1:
        raise UomNormalizationError(
            "uom_reference_unresolved",
            f"expected one reference UoM for category {source_category}, found {len(references)}",
        )
    ref_id, reference_uom = references[0]
    normalized = normalize_quantity(quantity, source_uom, reference_uom)
    return normalized, ref_id


def index_uoms(rows: list[Mapping]) -> dict[str, Mapping]:
    """Index exported uom.uom rows by their Odoo database id."""
    indexed: dict[str, Mapping] = {}
    for row in rows:
        uid = row.get("id")
        if uid in (None, ""):
            raise UomNormalizationError("uom_id_missing")
        key = str(uid)
        if key in indexed:
            raise UomNormalizationError("uom_id_duplicate", key)
        indexed[key] = row
    return indexed
