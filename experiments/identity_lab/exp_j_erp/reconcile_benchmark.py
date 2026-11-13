"""Benchmark-only DeepSeek scorer adapter.

The original reconcile.py and its matching algorithm remain untouched.
Only loss classification's receipt quantity normalization is corrected here.
"""
from __future__ import annotations

from reconcile import aggregate, match
from uom import convert


def classify(edge_results: list[dict], edges: list[dict],
             ref_uom: dict[str, str] | None = None) -> dict:
    """Classify confirmed edges using each product's canonical UoM category.

    ref_uom maps product_id -> canonical unit (unit or kg in Experiment M).
    Original quantity and unit are retained for every confirmed record.
    """
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
        target_uom = ref_uom.get(product, "unit")
        source_uom = str(receipt.get("counterpart_uom") or target_uom)
        source_qty_raw = receipt.get("counterpart_qty")
        audit = {
            "edge": str(result["edge"]), "product": product,
            "quantity_original": source_qty_raw, "unit_original": source_uom,
            "reference_unit": target_uom,
        }
        try:
            source_qty = float(source_qty_raw or 0)
        except (TypeError, ValueError):
            audit["normalization"] = "quantity_invalid"
            out["uom_audit"].append(audit)
            out["ambiguous"] += 1
            out[state] -= 1
            continue

        qty_in, reason = convert(source_qty, source_uom, target_uom)
        if qty_in is None:
            audit["normalization"] = reason
            out["uom_audit"].append(audit)
            out["ambiguous"] += 1
            out[state] -= 1
            continue

        audit["quantity_normalized"] = round(qty_in, 9)
        audit["normalization"] = "ok"
        out["uom_audit"].append(audit)
        gap = float(edge["qty_out"]) - qty_in
        if gap > 0.5:
            out["confirmed_loss"].append({
                "edge": result["edge"], "missing": round(gap, 3),
                "source": receipt.get("counterpart_source"),
                **audit,
            })
    return out
