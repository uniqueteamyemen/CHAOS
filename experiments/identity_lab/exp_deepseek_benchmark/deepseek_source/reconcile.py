"""Aggregation across moves, and counterpart matching with explicit confidence.

Two rules this file exists to enforce:
  1. normalize UoM before summing; never add heterogeneous moves;
  2. an approximate match on date and quantity is a *candidate*, never proof. Only an exact
     document key produces a confirmed edge; everything else stays explicit about its doubt.
"""
from __future__ import annotations

from uom import convert

DONE = "done"
DATE_WINDOW_DAYS = 3
QTY_TOLERANCE = 0.02


def aggregate(moves: list[dict], ref_uom: str = "unit") -> tuple[list[dict], list[dict]]:
    """Group done moves by (picking_id, product_id), normalising to one reference UoM first."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    rejected = []
    for m in moves:
        if str(m.get("state", "")).lower() != DONE:
            continue
        qty_raw = m.get("quantity")
        if qty_raw in (None, ""):
            rejected.append({"picking": m.get("picking_id"), "reason": "missing_executed_quantity"})
            continue
        qty, reason = convert(float(qty_raw), m.get("product_uom", ""), ref_uom)
        if qty is None:
            rejected.append({"picking": m.get("picking_id"), "product": m.get("product_id"),
                             "reason": reason})
            continue
        key = (str(m.get("picking_id")), str(m.get("product_id")))
        grouped.setdefault(key, []).append({**m, "_qty": qty})

    groups = []
    for (picking, product), rows in grouped.items():
        groups.append({
            "picking_id": picking,
            "product_id": product,
            "executed": round(sum(r["_qty"] for r in rows), 6),
            "moves": len(rows),
            "locations": sorted({f"{r.get('location_id')}->{r.get('location_dest_id')}" for r in rows}),
            "references": sorted({str(r.get("reference")) for r in rows}),
            "mixed_locations": len({f"{r.get('location_id')}->{r.get('location_dest_id')}" for r in rows}) > 1,
            "demand": round(sum(float(r.get("product_uom_qty") or 0) for r in rows), 6),
        })
    return groups, rejected


def match(edges: list[dict], receipts: list[dict], date_window: int = DATE_WINDOW_DAYS,
          qty_tolerance: float = QTY_TOLERANCE, ref_uom: dict | None = None,
          promote_unique: bool = False) -> list[dict]:
    """Exact key first; approximate only as a candidate with a confidence grade.

    date_window and qty_tolerance are parameters so the trade-off curve can be measured rather
    than argued. ref_uom maps product -> its reference unit; default is 'unit'.
    """
    ref_uom = ref_uom or {}
    by_key = {}
    for r in receipts:
        key = str(r.get("counterpart_picking_id") or "")
        if key:
            by_key.setdefault(key, []).append(r)

    results = []
    for edge in edges:
        key = str(edge["transfer_id"])
        exact = by_key.get(key, [])
        if len(exact) == 1:
            results.append({"edge": key, "state": "confirmed", "confidence": "exact",
                            "receipt": exact[0], "note": "shared document key"})
            continue
        if len(exact) > 1:
            results.append({"edge": key, "state": "ambiguous", "confidence": "none",
                            "candidates": len(exact), "note": "duplicate receipt rows for one key"})
            continue

        candidates = []
        for r in receipts:
            if str(r.get("product_id")) != str(edge.get("product")):
                continue
            if str(r.get("from_entity")) != str(edge.get("from_entity")):
                continue
            if str(r.get("to_entity")) != str(edge.get("to_entity")):
                continue
            target = ref_uom.get(str(edge.get("product")), "unit")
            qty, reason = convert(float(r.get("counterpart_qty") or 0), r.get("counterpart_uom", target), target)
            if qty is None:
                continue
            if edge["qty_out"] and abs(qty - edge["qty_out"]) / edge["qty_out"] > qty_tolerance:
                continue
            if abs(int(r.get("day_offset", 0))) > date_window:
                continue
            candidates.append(r)

        if len(candidates) == 1:
            state = "confirmed_approx" if promote_unique else "candidate"
            results.append({"edge": key, "state": state, "confidence": "approximate_unique",
                            "candidates": 1, "receipt": candidates[0],
                            "note": "matched on party, quantity and a date window"})
        elif len(candidates) > 1:
            results.append({"edge": key, "state": "ambiguous", "confidence": "none",
                            "candidates": len(candidates), "note": "several receipts fit"})
        else:
            results.append({"edge": key, "state": "unmatched", "confidence": "none",
                            "candidates": 0, "note": "no receipt found"})
    return results


def classify(edge_results: list[dict], edges: list[dict]) -> dict:
    """Original scorer retained verbatim; the isolated benchmark adapter replaces this function."""
    by_edge = {str(e["transfer_id"]): e for e in edges}
    out = {"confirmed": 0, "confirmed_approx": 0, "confirmed_loss": [], "candidate": 0,
           "ambiguous": 0, "unmatched": 0}
    for r in edge_results:
        out[r["state"]] = out.get(r["state"], 0) + 1
        if r["state"] not in ("confirmed", "confirmed_approx"):
            continue
        edge = by_edge[r["edge"]]
        qty_in, reason = convert(float(r["receipt"].get("counterpart_qty") or 0),
                                 r["receipt"].get("counterpart_uom", "unit"), "unit")
        if qty_in is None:
            out["ambiguous"] += 1
            continue
        gap = edge["qty_out"] - qty_in
        if gap > 0.5:
            out["confirmed_loss"].append({"edge": r["edge"], "missing": round(gap, 3),
                                          "source": r["receipt"].get("counterpart_source")})
    return out
