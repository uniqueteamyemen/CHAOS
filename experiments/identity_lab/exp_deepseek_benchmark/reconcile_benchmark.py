"""Benchmark-only DeepSeek scorer with the UoM fix isolated.

The original classify() uses a fixed 0.5-unit loss threshold. That threshold is preserved
verbatim; only the erroneous assumption that every product is measured in 'unit' is fixed.
The original matcher and its source files remain unchanged.
"""
from __future__ import annotations
import math
from uom import convert


def classify(edge_results: list[dict], edges: list[dict],
             ref_uom: dict[str, str] | None = None) -> dict:
    ref_uom = ref_uom or {}
    by_edge = {str(e["transfer_id"]): e for e in edges}
    out = {"confirmed": 0, "confirmed_approx": 0, "confirmed_loss": [],
           "candidate": 0, "ambiguous": 0, "unmatched": 0, "uom_audit": []}
    for result in edge_results:
        state = result["state"]
        out[state] = out.get(state, 0) + 1
        if state not in ("confirmed", "confirmed_approx"):
            continue
        edge = by_edge[str(result["edge"])]
        receipt = result["receipt"]
        product = str(edge.get("product"))
        target_uom = ref_uom.get(product)
        source_uom = str(receipt.get("counterpart_uom") or target_uom or "")
        source_qty_raw = receipt.get("counterpart_qty")
        audit = {"edge": str(result["edge"]), "product": product,
                 "quantity_original": source_qty_raw, "unit_original": source_uom,
                 "reference_unit": target_uom}
        try:
            if target_uom is None:
                raise ValueError("product_reference_uom_missing")
            source_qty = float(source_qty_raw)
            if not math.isfinite(source_qty) or source_qty < 0:
                raise ValueError("quantity_invalid")
        except (TypeError, ValueError):
            audit["normalization"] = "quantity_or_reference_invalid"
            out["uom_audit"].append(audit)
            out["ambiguous"] += 1
            out[state] -= 1
            continue
        normalized, reason = convert(source_qty, source_uom, target_uom)
        if normalized is None:
            audit["normalization"] = reason
            out["uom_audit"].append(audit)
            out["ambiguous"] += 1
            out[state] -= 1
            continue
        audit["quantity_normalized"] = round(normalized, 9)
        audit["normalization"] = "ok"
        out["uom_audit"].append(audit)
        gap = float(edge["qty_out"]) - normalized
        # Deliberately preserved from the original DeepSeek classify() implementation.
        if gap > 0.5:
            out["confirmed_loss"].append({
                "edge": str(result["edge"]), "missing": round(gap, 9),
                "source": receipt.get("counterpart_source"), **audit,
            })
    return out
