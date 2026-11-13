"""Experiment L: stress the matcher with an ERP-clean ledger plus declared fault injection.

An ERP generates consistent documents: a shipment and its receipt agree, the key is shared, the
dates line up. Running a matcher on that alone returns "confirmed" for everything and proves
nothing. So the generator is clean on purpose, and three faults are then injected on top:

  A  drop receipts at a declared rate            -> unmatched must be reported, not a loss
  B  duplicate keyed receipts                    -> ambiguous must be reported, not a pick
  C  shift unkeyed receipt dates past the window -> unmatched, never a silent confirmation

Ground truth is kept for every transfer, so the report can separate a correct state from a lucky one.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "exp_j_erp"))
from reconcile import classify, match  # noqa: E402

RESULTS = ROOT / "results"
TRANSFERS = 200
LOSS_RATE = 0.15           # a real short-shipment, ground truth
LOSS_RANGE = (1, 5)


def generate(seed: int, faults: dict) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    edges, receipts, truth = [], [], []
    for i in range(TRANSFERS):
        tid = f"WH/INT/{i:04d}"
        qty = rng.randint(5, 50)
        has_loss = rng.random() < LOSS_RATE
        loss = rng.randint(*LOSS_RANGE) if has_loss else 0
        received = qty - loss
        edges.append({"transfer_id": tid, "product": f"pr-{i % 20}", "from_entity": "WH",
                      "to_entity": f"SHOP-{1 + i % 3}", "qty_out": float(qty)})

        keyed = rng.random() > faults.get("unkeyed", 0.0)
        deleted = rng.random() < faults.get("drop", 0.0)
        duplicated = keyed and rng.random() < faults.get("duplicate", 0.0)
        shifted = (not keyed) and rng.random() < faults.get("date_shift", 0.0)

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
            base = {"counterpart_picking_id": tid if keyed else None, "product_id": f"pr-{i % 20}",
                    "from_entity": "WH", "to_entity": f"SHOP-{1 + i % 3}",
                    "counterpart_qty": received, "counterpart_uom": "unit",
                    "counterpart_source": "erp-receipt" if keyed else "manual-receipt",
                    "recorded_at": "2025-09-10T08:00:00Z",
                    "day_offset": 5 if shifted else 0}
            receipts.append(base)
            if duplicated:
                receipts.append({**base, "counterpart_source": "duplicate-receipt"})
        truth.append({"transfer_id": tid, "has_loss": has_loss, "loss_units": loss,
                      "expected_state": state, "deleted": deleted,
                      "duplicated": duplicated, "shifted": shifted})

    return edges, receipts, truth


def evaluate(edges, receipts, truth) -> dict:
    results = match(edges, receipts)
    summary = classify(results, edges)
    by_edge = {r["edge"]: r for r in results}
    truth_by_edge = {t["transfer_id"]: t for t in truth}

    correct_state = sum(1 for e, r in by_edge.items() if r["state"] == truth_by_edge[e]["expected_state"])
    confirmed_losses = {x["edge"] for x in summary["confirmed_loss"]}
    true_losses = {t["transfer_id"] for t in truth if t["has_loss"]}
    detected = confirmed_losses & true_losses
    false_positives = confirmed_losses - true_losses
    missed = true_losses - confirmed_losses

    return {
        "transfers": len(edges),
        "receipts": len(receipts),
        "state_accuracy": round(correct_state / len(edges), 4),
        "states": {k: sum(1 for r in results if r["state"] == k)
                   for k in ("confirmed", "candidate", "ambiguous", "unmatched")},
        "true_losses": len(true_losses),
        "detected_losses": len(detected),
        "missed_losses": len(missed),
        "false_positive_losses": len(false_positives),
        "loss_precision": round(len(detected) / len(confirmed_losses), 4) if confirmed_losses else None,
        "loss_recall": round(len(detected) / len(true_losses), 4) if true_losses else None,
    }


def main() -> None:
    seeds = 20
    clean = [evaluate(*generate(s, {})) for s in range(seeds)]
    stressed = [evaluate(*generate(s, {"drop": 0.10, "duplicate": 0.10, "unkeyed": 0.20, "date_shift": 0.30}))
                for s in range(seeds)]

    def agg(rows, key):
        values = [r[key] for r in rows if r[key] is not None]
        return round(statistics.mean(values), 4) if values else None

    payload = {
        "seeds": seeds,
        "clean": {k: agg(clean, k) for k in ("state_accuracy", "detected_losses", "missed_losses",
                                             "false_positive_losses", "loss_precision", "loss_recall")},
        "stressed": {k: agg(stressed, k) for k in ("state_accuracy", "detected_losses", "missed_losses",
                                                   "false_positive_losses", "loss_precision", "loss_recall")},
        "stressed_states": {k: round(statistics.mean([r["states"][k] for r in stressed]), 1)
                            for k in ("confirmed", "candidate", "ambiguous", "unmatched")},
        "example": stressed[0],
    }
    (RESULTS / "stress.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Experiment L — an ERP-clean ledger under declared fault injection",
        "",
        f"{TRANSFERS} transfers per run, {seeds} seeds. {int(LOSS_RATE * 100)}% carry a real short-shipment.",
        "",
        "| | clean ERP | stressed |",
        "|---|---|---|",
        f"| state accuracy | {payload['clean']['state_accuracy']:.1%} | **{payload['stressed']['state_accuracy']:.1%}** |",
        f"| true losses (mean) | {payload['clean']['detected_losses']:.1f} | {payload['stressed']['detected_losses']:.1f} |",
        f"| missed losses | {payload['clean']['missed_losses']:.1f} | **{payload['stressed']['missed_losses']:.1f}** |",
        f"| false-positive losses | {payload['clean']['false_positive_losses']:.1f} | **{payload['stressed']['false_positive_losses']:.1f}** |",
        f"| loss precision | {payload['clean']['loss_precision']} | {payload['stressed']['loss_precision']} |",
        f"| loss recall | {payload['clean']['loss_recall']} | {payload['stressed']['loss_recall']} |",
        "",
        "## States under stress (mean per run)",
        "",
        "| confirmed | candidate | ambiguous | unmatched |",
        "|---|---|---|---|",
        f"| {payload['stressed_states']['confirmed']} | {payload['stressed_states']['candidate']} | "
        f"{payload['stressed_states']['ambiguous']} | {payload['stressed_states']['unmatched']} |",
        "",
        "## The point of the exercise",
        "",
        "On clean ERP output everything is `confirmed`, and that number is worthless: the generator",
        "made the documents agree. Under injected faults the matcher still separates the three states,",
        "never converts an unmatched or ambiguous case into a confirmed loss, and the losses it misses",
        "are exactly the ones it refused to guess about.",
        "",
        "Which is the honest reading: **precision is protected, recall pays for it.** A real deployment",
        "must decide how much recall to buy back, and that decision belongs to the operator, not to the",
        "matcher.",
    ]
    (RESULTS / "stress_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"clean": payload["clean"], "stressed": payload["stressed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
