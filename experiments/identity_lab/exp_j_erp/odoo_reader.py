"""Read Odoo movement exports.

The legacy to_edges() helper below is retained for historical synthetic fixtures only.
Operational exports must use reconcile_export(), which aggregates one-sided stock.move
records and requires a separate counterparty receipt evidence stream.

Field names are taken from Odoo 17's own source (`stock_move.py`), not invented:
  stock.move:  picking_id, location_id, location_dest_id, product_id,
               product_uom_qty (DEMAND), quantity (EXECUTED), product_uom,
               state, reference, date

The executed quantity is `quantity`. `product_uom_qty` is the demand: using it would turn every
backorder into a phantom loss. If `quantity` is absent from the export, the reader refuses the
row instead of falling back to demand — a loud failure beats a silent misclassification.

The legacy fixture adapter uses the pre-normalized `uom_factor` column. The operational
`reconcile_export()` path derives conversion from exported `uom.uom` rows and checks the
product's stock-UoM category before aggregating.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DONE = "done"


def load_moves(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def executed(move: dict) -> tuple[float | None, str]:
    """Executed quantity only. Demand is never a substitute."""
    raw = move.get("quantity")
    if raw in (None, ""):
        raw = move.get("quantity_done")      # pre-17 exports
    if raw in (None, ""):
        return None, "missing_executed_quantity"
    factor = move.get("uom_factor")
    if factor in (None, ""):
        return None, "uom_unresolved"
    return float(raw) * float(factor), "ok"


def to_edges(moves: list[dict]) -> tuple[list[dict], dict]:
    """Legacy same-file fixture adapter; not valid evidence of independent receipts."""
    done = [m for m in moves if str(m.get("state", "")).lower() == DONE]
    by_picking: dict[str, list[dict]] = {}
    for m in done:
        by_picking.setdefault(str(m.get("picking_id") or m.get("reference") or ""), []).append(m)

    edges, rejected = [], []
    for picking, group in by_picking.items():
        if len(group) < 2:
            rejected.append({"picking": picking, "reason": "single_record"})
            continue
        sender, receiver = group[0], group[1]
        q_out, reason_out = executed(sender)
        q_in, reason_in = executed(receiver)
        if q_out is None or q_in is None:
            rejected.append({"picking": picking, "reason": reason_out if q_out is None else reason_in})
            continue
        demand = float(sender.get("product_uom_qty") or 0)
        edges.append({
            "transfer_id": picking,
            "from_entity": sender.get("location_id"),
            "to_entity": sender.get("location_dest_id"),
            "month_out": str(sender.get("date", ""))[:7],
            "month_in": str(receiver.get("date", ""))[:7],
            "qty_out": q_out,
            "qty_in": q_in,
            "product": sender.get("product_id"),
            "demand_out": demand * float(sender.get("uom_factor") or 1),
            "partial": demand > float(sender.get("quantity") or 0),
        })
    stats = {"moves_total": len(moves), "moves_done": len(done), "pickings": len(by_picking),
             "edges": len(edges), "rejected": rejected,
             "partial_executions": sum(1 for e in edges if e["partial"]),
             "locations": sorted({str(m.get("location_id")) for m in done} |
                                 {str(m.get("location_dest_id")) for m in done})}
    return edges, stats


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("usage: odoo_reader.py <moves.csv|moves.json>")
        raise SystemExit(2)
    moves = load_moves(Path(argv[1]))
    edges, stats = to_edges(moves)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "odoo_edges.json").write_text(json.dumps({"stats": stats, "edges": edges},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)



def reconcile_export(moves: list[dict], uom_rows: list[dict], receipts: list[dict]) -> dict:
    """Authoritative path for operational exports with independent receipt evidence.

    Unlike the historical fixture adapter above, this path never treats two stock.move
    rows in one picking as independent sender/receiver records.
    """
    try:
        from .reconcile import aggregate_moves, match_counterpart_receipts
        from .uom import index_uoms
    except ImportError:  # direct script execution from this directory
        from reconcile import aggregate_moves, match_counterpart_receipts
        from uom import index_uoms

    uoms = index_uoms(uom_rows)
    movements, movement_stats = aggregate_moves(moves, uoms)
    matches = match_counterpart_receipts(movements, receipts, uoms)
    states = {}
    for match in matches:
        states[match["state"]] = states.get(match["state"], 0) + 1
    confirmed = [match for match in matches if match.get("confirmed")]
    return {
        "movement_stats": movement_stats,
        "movements": movements,
        "receipt_match_stats": states,
        "receipt_matches": matches,
        "confirmed_edges": confirmed,
        "confirmed_loss_events": sum(1 for match in confirmed if "loss" in match.get("issues", [])),
        "approximate_matches_are_not_confirmed": True,
    }
