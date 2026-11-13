"""Exercise UoM normalisation, multi-move aggregation and counterpart matching."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "exp_j_erp"))
from reconcile import aggregate, classify, match  # noqa: E402
from uom import convert  # noqa: E402

RESULTS = ROOT / "results"

MOVES = [
    {"picking_id": "P1", "product_id": "pr-1", "quantity": 10, "product_uom": "unit", "state": "done",
     "location_id": "WH", "location_dest_id": "SHOP-1", "reference": "P1", "product_uom_qty": 10},
    {"picking_id": "P1", "product_id": "pr-1", "quantity": 1, "product_uom": "dozen", "state": "done",
     "location_id": "WH", "location_dest_id": "SHOP-1", "reference": "P1", "product_uom_qty": 12},
    {"picking_id": "P2", "product_id": "pr-2", "quantity": 5, "product_uom": "unit", "state": "done",
     "location_id": "WH", "location_dest_id": "SHOP-2", "reference": "P2", "product_uom_qty": 5},
    {"picking_id": "P2", "product_id": "pr-2", "quantity": 2, "product_uom": "kg", "state": "done",
     "location_id": "WH", "location_dest_id": "SHOP-2", "reference": "P2", "product_uom_qty": 2},
    {"picking_id": "P3", "product_id": "pr-3", "quantity": 4, "product_uom": "unit", "state": "draft",
     "location_id": "WH", "location_dest_id": "SHOP-2", "reference": "P3", "product_uom_qty": 4},
]

EDGES = [
    {"transfer_id": "P1", "product": "pr-1", "from_entity": "WH", "to_entity": "SHOP-1", "qty_out": 22.0},
    {"transfer_id": "P4", "product": "pr-4", "from_entity": "WH", "to_entity": "SHOP-1", "qty_out": 10.0},
    {"transfer_id": "P5", "product": "pr-5", "from_entity": "WH", "to_entity": "SHOP-2", "qty_out": 10.0},
    {"transfer_id": "P6", "product": "pr-6", "from_entity": "WH", "to_entity": "SHOP-2", "qty_out": 10.0},
]

RECEIPTS = [
    {"counterpart_picking_id": "P1", "product_id": "pr-1", "from_entity": "WH", "to_entity": "SHOP-1",
     "counterpart_qty": 20, "counterpart_uom": "unit", "counterpart_source": "shop-receipt-app",
     "recorded_at": "2025-09-06T10:00:00Z", "day_offset": 0},
    {"counterpart_picking_id": "EXT-4", "product_id": "pr-4", "from_entity": "WH", "to_entity": "SHOP-1",
     "counterpart_qty": 9.9, "counterpart_uom": "unit", "counterpart_source": "email-confirmation",
     "recorded_at": "2025-09-11T09:00:00Z", "day_offset": 1},
    {"counterpart_picking_id": "EXT-5a", "product_id": "pr-5", "from_entity": "WH", "to_entity": "SHOP-2",
     "counterpart_qty": 10, "counterpart_uom": "unit", "counterpart_source": "paper-receipt",
     "recorded_at": "2025-09-12T09:00:00Z", "day_offset": 0},
    {"counterpart_picking_id": "EXT-5b", "product_id": "pr-5", "from_entity": "WH", "to_entity": "SHOP-2",
     "counterpart_qty": 10, "counterpart_uom": "unit", "counterpart_source": "phone-note",
     "recorded_at": "2025-09-12T15:00:00Z", "day_offset": 1},
]


def main() -> None:
    groups, rejected = aggregate(MOVES)
    results = match(EDGES, RECEIPTS)
    summary = classify(results, EDGES)
    conversions = [{"from": "1 kg", "to": convert(1, "kg", "g")},
                   {"from": "1000 g", "to": convert(1000, "g", "kg")},
                   {"from": "2 dozen", "to": convert(2, "dozen", "unit")},
                   {"from": "5 unit", "to": convert(5, "unit", "kg")}]

    checks = {
        "P1 aggregated 10 unit + 1 dozen = 22": next(g for g in groups if g["picking_id"] == "P1")["executed"] == 22.0,
        "P1 kept one location pair": next(g for g in groups if g["picking_id"] == "P1")["locations"] == ["WH->SHOP-1"],
        "unit+kg rejected": any(r["picking"] == "P2" for r in rejected),
        "draft ignored": not any(g["picking_id"] == "P3" for g in groups),
        "exact key -> confirmed": next(r for r in results if r["edge"] == "P1")["state"] == "confirmed",
        "approximate -> candidate": next(r for r in results if r["edge"] == "P4")["state"] == "candidate",
        "two fits -> ambiguous": next(r for r in results if r["edge"] == "P5")["state"] == "ambiguous",
        "none -> unmatched": next(r for r in results if r["edge"] == "P6")["state"] == "unmatched",
        "only confirmed yields a loss": len(summary["confirmed_loss"]) == 1,
        "loss value is 2": summary["confirmed_loss"][0]["missing"] == 2.0,
    }
    failed = [k for k, v in checks.items() if not v]

    payload = {"checks": checks, "failed": failed, "groups": groups, "rejected": rejected,
               "match": results, "summary": summary}
    (RESULTS / "uom_reconcile.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Experiment K — units, aggregation, and the limits of matching",
        "",
        "## 1. Unit conversion",
        "",
        "| case | result |",
        "|---|---|",
    ]
    for c in conversions:
        value, reason = c["to"]
        lines.append(f"| {c['from']} | {value if value is not None else reason} |")
    lines += [
        "",
        "The kilogram case is refused with `uom_category_mismatch`: Units are *count*, Kilograms are",
        "*weight*. No factor can bridge that unless the product declares its own unit weight, which is",
        "a product fact, not a conversion.",
        "",
        "## 2. Aggregation across moves",
        "",
        "| picking | product | executed (ref unit) | moves | locations | note |",
        "|---|---|---|---|---|---|",
    ]
    for g in groups:
        lines.append(f"| {g['picking_id']} | {g['product_id']} | {g['executed']} | {g['moves']} | "
                     f"{', '.join(g['locations'])} | {'mixed' if g['mixed_locations'] else 'single'} |")
    lines += [
        "",
        f"Rejected rows: {len(rejected)} — " + ", ".join(f"{r['picking']}:{r['reason']}" for r in rejected),
        "",
        "The dozen is normalised to 12 units *before* summing, and the location pair is retained, not",
        "collapsed. The unit+kg document is refused rather than added.",
        "",
        "## 3. Counterpart matching",
        "",
        "| edge | state | confidence | note |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['edge']} | {r['state']} | {r['confidence']} | {r['note']} |")
    lines += [
        "",
        f"Confirmed: {summary['confirmed']}, candidates: {summary.get('candidate', 0)}, "
        f"ambiguous: {summary.get('ambiguous', 0)}, unmatched: {summary.get('unmatched', 0)}.",
        "",
        "**Only a confirmed edge may produce a loss.** A receipt matched on quantity and a three-day",
        "window is a candidate, and two receipts that both fit make the edge ambiguous — the system says",
        "so instead of picking one.",
        "",
        f"Checks: {sum(checks.values())}/{len(checks)} passed" + (f"; failed: {failed}" if failed else "."),
    ]
    (RESULTS / "uom_reconcile_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"checks": f"{sum(checks.values())}/{len(checks)}", "failed": failed,
                      "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
