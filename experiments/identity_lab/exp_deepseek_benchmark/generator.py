"""Deterministic Experiment M generator shared by both benchmarked algorithms."""
from __future__ import annotations
import random

TRANSFERS = 240
SEEDS = 12
LOSS_RATE = 0.18
WINDOWS = (0, 1, 2, 3, 5, 7, 10, 14, 21, 30)
QTY_TOL = 0.02
UNKEYED = 0.25


def product_catalog() -> dict[str, tuple[str, float]]:
    catalog = {}
    for i in range(40):
        catalog[f"pr-{i}"] = ("unit", 12.0) if i % 2 == 0 else ("kg", 1000.0)
    return catalog


def generate(seed: int) -> tuple[list[dict], list[dict], list[dict], dict]:
    rng = random.Random(seed)
    catalog = product_catalog()
    edges, receipts, truth = [], [], []
    used_slots: dict[tuple[str, int], list[str]] = {}
    for i in range(TRANSFERS):
        tid = f"WH/INT/{i:04d}"
        product = f"pr-{rng.randrange(40)}"
        ref_uom, pack = catalog[product]
        qty = round(rng.uniform(5, 50), 3)
        day = rng.randrange(0, 20)
        has_loss = rng.random() < LOSS_RATE
        loss = round(rng.uniform(1, 5), 3) if has_loss else 0.0
        edges.append({"transfer_id": tid, "product": product, "from_entity": "WH",
                      "to_entity": f"SHOP-{1 + i % 3}", "qty_out": qty})
        keyed = rng.random() > UNKEYED
        deleted = rng.random() < 0.10
        duplicated = keyed and rng.random() < 0.10
        shifted = (not keyed) and rng.random() < 0.30
        state = "confirmed"
        if deleted:
            state = "unmatched"
        elif duplicated:
            state = "ambiguous"
        elif shifted:
            state = "unmatched"
        elif not keyed:
            state = "candidate"
        if not deleted:
            if ref_uom == "unit":
                receipt_uom, factor = ("dozen", 1 / 12) if rng.random() < 0.3 else ("unit", 1.0)
            else:
                receipt_uom, factor = ("g", 1000.0) if rng.random() < 0.3 else ("kg", 1.0)
            base = {
                "counterpart_picking_id": tid if keyed else None,
                "product_id": product, "from_entity": "WH", "to_entity": f"SHOP-{1 + i % 3}",
                "counterpart_qty": round((qty - loss) * factor, 6),
                "counterpart_uom": receipt_uom, "counterpart_source": "erp" if keyed else "manual",
                "recorded_at": "2025-09-10T08:00:00Z",
                "day_offset": (day + 5 if shifted else day) - day,
                "_owner": tid,
            }
            receipts.append(base)
            if duplicated:
                receipts.append({**base, "counterpart_source": "duplicate"})
            used_slots.setdefault((product, day), []).append(tid)
        truth.append({"transfer_id": tid, "has_loss": has_loss, "loss": loss,
                      "expected_state": state, "unkeyed": not keyed, "deleted": deleted,
                      "duplicated": duplicated, "shifted": shifted})
    overlaps = 0
    for (product, day), tids in used_slots.items():
        if len(tids) > 1 and rng.random() < 0.5:
            overlaps += 1
    return edges, receipts, truth, {"products": len(catalog), "overlapping_slots": overlaps,
                                    "ref_uom": catalog}
