"""Synthetic plumbing fixture for the hardened Odoo reconciliation path; not real validation."""
from __future__ import annotations
import json, sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "exp_j_erp"))
from odoo_reader import reconcile_export

RESULTS = ROOT / "results"
UOM_ROWS = [
    {"id":"unit","name":"Units","category_id":"count","factor":"1","uom_type":"reference"},
    {"id":"dozen","name":"Dozen","category_id":"count","factor":"0.0833333333333333333333333333","uom_type":"bigger"},
    {"id":"kg","name":"kg","category_id":"weight","factor":"1","uom_type":"reference"},
    {"id":"g","name":"g","category_id":"weight","factor":"1000","uom_type":"smaller"},
]
MOVES = [
    {"id":1,"picking_id":"P1","product_id":"pr-1","quantity":"10","product_uom_qty":"10","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-1","reference":"P1","date":"2025-09-05"},
    {"id":2,"picking_id":"P1","product_id":"pr-1","quantity":"1","product_uom_qty":"1","product_uom":"dozen","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-1","reference":"P1","date":"2025-09-05"},
    {"id":3,"picking_id":"P2","product_id":"pr-2","quantity":"2","product_uom_qty":"2","product_uom":"kg","product_uom_category_id":"weight","state":"done","location_id":"WH","location_dest_id":"SHOP-2","reference":"P2","date":"2025-09-06"},
    {"id":4,"picking_id":"P2","product_id":"pr-2","quantity":"500","product_uom_qty":"500","product_uom":"g","product_uom_category_id":"weight","state":"done","location_id":"WH","location_dest_id":"SHOP-2","reference":"P2","date":"2025-09-06"},
    {"id":5,"picking_id":"P3","product_id":"pr-3","quantity":"5","product_uom_qty":"5","product_uom":"unit","product_uom_category_id":"weight","state":"done","location_id":"WH","location_dest_id":"SHOP-3","reference":"P3","date":"2025-09-07"},
    {"id":6,"picking_id":"P4","product_id":"pr-4","quantity":"4","product_uom_qty":"4","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-4A","reference":"P4-A","date":"2025-09-08"},
    {"id":7,"picking_id":"P4","product_id":"pr-4","quantity":"6","product_uom_qty":"6","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-4B","reference":"P4-B","date":"2025-09-08"},
    {"id":8,"picking_id":"P5","product_id":"pr-5","product_uom_qty":"99","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-5","reference":"P5","date":"2025-09-09"},
    {"id":9,"picking_id":"P6","product_id":"pr-6","quantity":"4","product_uom_qty":"4","product_uom":"unit","product_uom_category_id":"count","state":"draft","location_id":"WH","location_dest_id":"SHOP-6","reference":"P6","date":"2025-09-10"},
    {"id":10,"picking_id":"P7","product_id":"pr-7","quantity":"10","product_uom_qty":"10","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-7","reference":"P7","date":"2025-09-11"},
    {"id":11,"picking_id":"P8","product_id":"pr-8","quantity":"10","product_uom_qty":"10","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-8","reference":"P8","date":"2025-09-12"},
    {"id":12,"picking_id":"P9","product_id":"pr-9","quantity":"10","product_uom_qty":"10","product_uom":"unit","product_uom_category_id":"count","state":"done","location_id":"WH","location_dest_id":"SHOP-9","reference":"P9","date":"2025-09-13"},
]
RECEIPTS = [
    {"source_picking_id":"P1","counterpart_picking_id":"RCV-1","product_id":"pr-1","counterpart_qty":"20","counterpart_uom_id":"unit","product_uom_category_id":"count","location_id":"SHOP-1","counterpart_date":"2025-09-06","counterpart_source":"signed_receipt.pdf","recorded_at":"2025-09-06T10:00:00Z"},
    {"counterpart_picking_id":"RCV-7","product_id":"pr-7","counterpart_qty":"10","counterpart_uom_id":"unit","product_uom_category_id":"count","location_id":"SHOP-7","counterpart_date":"2025-09-12","counterpart_source":"receipt_scan","recorded_at":"2025-09-12T10:00:00Z"},
    {"counterpart_picking_id":"RCV-8A","product_id":"pr-8","counterpart_qty":"10","counterpart_uom_id":"unit","product_uom_category_id":"count","location_id":"SHOP-8","counterpart_date":"2025-09-13","counterpart_source":"receipt_scan","recorded_at":"2025-09-13T10:00:00Z"},
    {"counterpart_picking_id":"RCV-8B","product_id":"pr-8","counterpart_qty":"10","counterpart_uom_id":"unit","product_uom_category_id":"count","location_id":"SHOP-8","counterpart_date":"2025-09-13","counterpart_source":"receipt_scan","recorded_at":"2025-09-13T11:00:00Z"},
]

def main():
    result = reconcile_export(MOVES, UOM_ROWS, RECEIPTS)
    movements = result["movements"]
    stats = result["movement_stats"]
    matches = result["receipt_matches"]
    states = {s: sum(1 for x in matches if x["state"] == s) for s in ("exact","approximate_unique","ambiguous","unmatched")}
    losses = [x for x in matches if x.get("confirmed") and "loss" in x.get("issues", [])]
    p1 = next(x for x in movements if x["picking_id"] == "P1")
    p2 = next(x for x in movements if x["picking_id"] == "P2")
    p4 = [x for x in movements if x["picking_id"] == "P4"]
    p7 = next(x for x in matches if x["picking_id"] == "P7")
    p8 = next(x for x in matches if x["picking_id"] == "P8")
    p9 = next(x for x in matches if x["picking_id"] == "P9")
    checks = {
        "dozen normalized before sum": abs(float(p1["quantity"]) - 22.0) < 1e-9,
        "kg and g normalized before sum": p2["quantity"] == "2.5",
        "product category mismatch rejected": any(x["reason"] == "product_uom_category_mismatch" for x in stats["rejected"]),
        "location variants kept separate": len(p4) == 2 and all(x["heterogeneous_locations"] for x in p4),
        "missing executed quantity rejected": any(x["reason"] == "missing_executed_quantity" for x in stats["rejected"]),
        "draft move ignored": not any(x["picking_id"] == "P6" for x in movements),
        "explicit source key is exact": next(x for x in matches if x["picking_id"] == "P1")["state"] == "exact",
        "approximate unique is not confirmed": p7["state"] == "approximate_unique" and not p7["confirmed"],
        "multiple approximate receipts are ambiguous": p8["state"] == "ambiguous",
        "no candidate is unmatched": p9["state"] == "unmatched",
        "only exact receipt can create loss": len(losses) == 1 and Decimal(losses[0]["delta"]) == Decimal("2"),
    }
    failed = [k for k,v in checks.items() if not v]
    payload = {"fixture_classification":"synthetic_plumbing_only","checks":checks,"failed":failed,
               "movement_stats":stats,"movements":movements,"receipt_match_states":states,
               "receipt_matches":matches,"confirmed_loss_events":losses}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "uom_reconcile.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    lines = ["# Experiment K — Odoo UoM metadata, safe aggregation and independent receipts","",
             "**Classification:** synthetic plumbing fixture only; not operational validation.","",
             "| Check | Result |","|---|---|"]
    lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k,v in checks.items()]
    lines += ["",f"**{sum(checks.values())}/{len(checks)} checks passed.**","",
              f"Movement rows: {stats['moves_total']}; completed: {stats['moves_done']}; aggregated: {stats['aggregated_movements']}; rejected: {stats['rejected_rows']}.",
              f"Receipt states: {json.dumps(states)}. Confirmed losses: {len(losses)}.","",
              "Only an explicit source_picking_id linking the receiver record to the sender can be exact.",
              "counterpart_picking_id remains the receiver's own document ID. Approximate candidates never create loss events."]
    (RESULTS / "uom_reconcile_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"checks":f"{sum(checks.values())}/{len(checks)}","failed":failed,"states":states}))
    if failed:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
