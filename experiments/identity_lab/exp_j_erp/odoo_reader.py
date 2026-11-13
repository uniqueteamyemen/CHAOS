"""Read a movement export in Odoo's document model and turn it into edge transfers.

The field names are taken from Odoo 17's own source, not invented:
  stock.move:  picking_id, location_id, location_dest_id, product_id,
               product_uom_qty, state, reference, date
  stock.picking: name, origin, state

Only moves with state == 'done' are physical. Everything else is intent.
A transfer edge exists when two done moves describe the same picking with opposite locations.
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


def to_edges(moves: list[dict]) -> tuple[list[dict], dict]:
    """Pair the two records of one movement by picking, and keep every unmatched record visible."""
    done = [m for m in moves if str(m.get("state", "")).lower() == DONE]
    by_picking = {}
    for m in done:
        by_picking.setdefault(str(m.get("picking_id") or m.get("reference") or ""), []).append(m)

    edges, unmatched = [], []
    for picking, group in by_picking.items():
        outbound = [m for m in group if m.get("location_dest_id") and m.get("location_id")]
        if len(group) < 2:
            unmatched.append({"picking": picking, "moves": len(group), "reason": "single_record"})
            continue
        a, b = group[0], group[1]
        # the same picking seen from both ends: A->B and B->A are the two declarations
        edges.append({
            "transfer_id": picking or a.get("reference"),
            "from_entity": a.get("location_id"),
            "to_entity": a.get("location_dest_id"),
            "month_out": str(a.get("date", ""))[:7],
            "month_in": str(b.get("date", ""))[:7],
            "qty_out": float(a.get("product_uom_qty") or 0),
            "qty_in": float(b.get("product_uom_qty") or 0),
            "product": a.get("product_id"),
        })
    stats = {"moves_total": len(moves), "moves_done": len(done), "pickings": len(by_picking),
             "edges": len(edges), "unmatched": len(unmatched),
             "locations": sorted({str(m.get('location_id')) for m in done} |
                                 {str(m.get('location_dest_id')) for m in done})}
    return edges, stats


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("usage: odoo_reader.py <moves.csv|moves.json>")
        raise SystemExit(2)
    path = Path(argv[1])
    moves = load_moves(path)
    edges, stats = to_edges(moves)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "odoo_edges.json").write_text(json.dumps({"stats": stats, "edges": edges},
                                                        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)
