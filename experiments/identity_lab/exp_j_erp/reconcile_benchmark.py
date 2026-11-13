"""Benchmark-only DeepSeek scorer adapter.

The production/original reconcile.py and matching algorithm are imported unchanged.
Only loss classification's receipt quantity normalization is corrected here.
"""
from __future__ import annotations

from reconcile import aggregate, match
from uom import convert


def classify(edge_results: list[dict], edges: list[dict],
             ref_uom: dict[str, str] | None = None) -> dict:
    """Classify confirmed edges using each product's reference UoM category.

    ref_uom maps product_id -> canonical unit (unit or kg in Experiment M).
    Original receipt quantity and UoM are retained in audit fields.
    """
    ref_uom = ref_uom or {}
    by_edge = {str(e["transfer_id"]): e for e in edges}
    out = {"confirmed": 0, "confirmed_approx": 0, "confirmed_loss": [],
           "candidate": 0, "ambiguous": 0, "unmatched": 0}
    for result in edge_results:
        state = result["state"]
        out[state] = out.get(state, 0) + 1
        if state not in ("confirmed", "confirmed_approx"):
            continue

        edge = by_edge[str(result["edge"])]
        receipt = result["receipt"]
        product = str(edge.get("product"))
        target_uom = ref_uom.get(product, "unit")
        source_uom = str(receipt.get("counterpart_uom") or target_uom)
        source_qty_raw = receipt.get("counterpart_qty")
        try:
            source_qty = float(source_qty_raw or 0)
        except (TypeError, ValueError):
            out["ambiguous"] += 1
            out["confirmed"] -= 1 if state == "confirmed" else 0
            out["confirmed_approx"] -= 1 if state == "confirmed_approx" else 0
            continue

        qty_in, reason = convert(source_qty, source_uom, target_uom)
        if qty_in is None:
            out["ambiguous"] += 1
            out["confirmed"] -= 1 if state == "confirmed" else 0
            out["confirmed_approx"] -= 1 if state == "confirmed_approx" else 0
            continue

        gap = float(edge["qty_out"]) - qty_in
        if gap > 0.5:
            out["confirmed_loss"].append({
                "edge": result["edge"],
                "missing": round(gap, 3),
                "source": receipt.get("counterpart_source"),
                "product": product,
                "qty_out": edge["qty_out"],
                "receipt_qty_original": source_qty_raw,
                "receipt_uom_original": source_uom,
                "receipt_qty_normalized": round(qty_in, 9),
                "reference_uom": target_uom,
            })
    return out
