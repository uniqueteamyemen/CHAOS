"""Apply Experiment M's 240-transfer/12-seed generator to the hardened receipt matcher.

This is an isolated benchmark adapter. It does not modify production reconciliation code.
"""
from __future__ import annotations

import json
import random
import statistics
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from exp_j_erp.reconcile import match_counterpart_receipts

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TRANSFERS = 240
SEEDS = 12
LOSS_RATE = 0.18
WINDOWS = (0, 1, 2, 3, 5, 7, 10, 14, 21, 30)
QTY_TOL = Decimal("0.02")

UOMS = {
    "unit": {"id": "unit", "category_id": "count", "factor": "1", "uom_type": "reference"},
    "dozen": {"id": "dozen", "category_id": "count", "factor": "0.083333333333333333", "uom_type": "bigger"},
    "kg": {"id": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "g": {"id": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}


def generate(seed: int):
    rng = random.Random(seed)
    catalog = {f"pr-{i}": ("unit", "count") if i % 2 == 0 else ("kg", "weight") for i in range(40)}
    shipments, receipts, truth = [], [], []
    for i in range(TRANSFERS):
        tid = f"WH/INT/{i:04d}"
        product = f"pr-{rng.randrange(40)}"
        ref_uom, category = catalog[product]
        qty = round(rng.uniform(5, 50), 3)
        day_offset = rng.randrange(0, 20)
        ship_date = date(2025, 9, 1) + timedelta(days=day_offset)
        has_loss = rng.random() < LOSS_RATE
        loss = round(rng.uniform(1, 5), 3) if has_loss else 0.0
        keyed = rng.random() > 0.25
        deleted = rng.random() < 0.10
        duplicated = keyed and rng.random() < 0.10
        shifted = (not keyed) and rng.random() < 0.30

        expected_state = "confirmed"
        if deleted:
            expected_state = "unmatched"
        elif duplicated:
            expected_state = "ambiguous"
        elif shifted:
            expected_state = "unmatched"
        elif not keyed:
            expected_state = "candidate"

        shipments.append({
            "picking_id": tid, "product_id": product,
            "location_id": "WH", "location_dest_id": f"SHOP-{1 + i % 3}",
            "reference_uom_id": ref_uom, "product_uom_category_id": category,
            "quantity": str(qty), "dates": [ship_date.isoformat()],
        })

        if not deleted:
            if ref_uom == "unit":
                receipt_uom = "dozen" if rng.random() < 0.3 else "unit"
                received_base = qty - loss
                receipt_qty = received_base / 12 if receipt_uom == "dozen" else received_base
            else:
                receipt_uom = "g" if rng.random() < 0.3 else "kg"
                receipt_qty = (qty - loss) * 1000 if receipt_uom == "g" else qty - loss
            receipt_date = ship_date + timedelta(days=5 if shifted else 0)
            receipt = {
                "source_picking_id": tid if keyed else None,
                "counterpart_picking_id": f"RCV-{i:04d}",
                "product_id": product, "location_id": f"SHOP-{1 + i % 3}",
                "counterpart_qty": str(round(receipt_qty, 8)),
                "counterpart_uom_id": receipt_uom,
                "product_uom_category_id": category,
                "counterpart_date": receipt_date.isoformat(),
                "counterpart_system": "independent_receiving_wms",
                "counterpart_source": "erp" if keyed else "manual",
                "recorded_at": receipt_date.isoformat() + "T08:00:00",
                "_owner": tid,
            }
            receipts.append(receipt)
            if duplicated:
                duplicate = dict(receipt)
                duplicate["counterpart_picking_id"] = f"RCV-DUP-{i:04d}"
                duplicate["counterpart_source"] = "duplicate"
                receipts.append(duplicate)

        truth.append({
            "picking_id": tid, "receipt_id": f"RCV-{i:04d}",
            "has_loss": has_loss, "loss": loss, "expected_state": expected_state,
            "keyed": keyed, "deleted": deleted, "duplicated": duplicated, "shifted": shifted,
        })
    return shipments, receipts, truth


def evaluate(seed: int, window: int):
    shipments, receipts, truth = generate(seed)
    rows = match_counterpart_receipts(
        shipments, receipts, UOMS, date_window_days=window, quantity_tolerance=QTY_TOL
    )
    truth_by_id = {row["picking_id"]: row for row in truth}
    tp = fp = fn = 0
    candidate_hits = 0
    ambiguous = unmatched = confirmed = approximate = 0
    state_correct = 0
    for row in rows:
        expected = truth_by_id[row["picking_id"]]
        state = row["state"]
        if state == expected["expected_state"]:
            state_correct += 1
        if state == "exact":
            confirmed += 1
        elif state == "approximate_unique":
            approximate += 1
        elif state == "ambiguous":
            ambiguous += 1
        elif state == "unmatched":
            unmatched += 1

        candidate_ids = set(row.get("candidate_receipt_ids") or [])
        if expected["receipt_id"] in candidate_ids:
            candidate_hits += 1

        predicted_loss = row.get("confirmed", False) and "loss" in row.get("issues", [])
        if predicted_loss and expected["has_loss"]:
            tp += 1
        elif predicted_loss and not expected["has_loss"]:
            fp += 1
        elif expected["has_loss"]:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    n = len(truth)
    return {
        "seed": seed, "window_days": window, "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "candidate_recall": candidate_hits / n,
        "state_accuracy": state_correct / n,
        "confirmed_coverage": confirmed / n,
        "approximate_unique_rate": approximate / n,
        "ambiguity_rate": ambiguous / n, "unmatched_rate": unmatched / n,
        "false_loss_rate": fp / n,
        "n": n,
    }


def run():
    per_seed = [evaluate(seed, window) for seed in range(SEEDS) for window in WINDOWS]
    curve = []
    for window in WINDOWS:
        subset = [row for row in per_seed if row["window_days"] == window]
        fields = (
            "precision", "recall", "f1", "candidate_recall", "state_accuracy",
            "confirmed_coverage", "approximate_unique_rate", "ambiguity_rate",
            "unmatched_rate", "false_loss_rate",
        )
        aggregate = {"window_days": window}
        for field in fields:
            values = [row[field] for row in subset]
            aggregate[field] = round(statistics.mean(values), 6)
            aggregate[field + "_sd"] = round(statistics.stdev(values), 6) if len(values) > 1 else 0.0
        aggregate.update({key: sum(row[key] for row in subset) for key in ("tp", "fp", "fn")})
        curve.append(aggregate)

    payload = {
        "experiment": "DeepSeek_240x12_method_on_hardened_matcher",
        "classification": "synthetic_controlled_benchmark_not_operational_validation",
        "algorithm": "feat/erp-reconcile-hardening: match_counterpart_receipts",
        "dataset_protocol": {
            "transfers_per_seed": TRANSFERS, "seeds": SEEDS, "quantity_tolerance": str(QTY_TOL),
            "loss_rate": LOSS_RATE, "unkeyed_rate": 0.25, "windows_days": list(WINDOWS),
            "uom_pairs": ["unit/dozen", "kg/g"],
        },
        "curve": curve,
        "per_seed": per_seed,
        "metric_definitions": {
            "loss_precision": "TP/(TP+FP) for confirmed loss claims",
            "loss_recall": "TP/(TP+FN) over labelled true-loss shipments",
            "candidate_recall": "true receipt ID appears in candidate_receipt_ids / all shipments",
            "state_accuracy": "matcher state equals generator's expected state",
            "confirmed_coverage": "exact confirmed shipments / all shipments",
        },
        "limitations": [
            "Synthetic labels measure controlled behavior, not operational accuracy or prevalence.",
            "The hardened matcher requires explicit source_picking_id for confirmation; approximate matches remain unconfirmed.",
            "The DeepSeek generator's expected state is used only for state accuracy; loss metrics use independent has_loss labels.",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "deepseek_method_on_hardened_matcher.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    lines = [
        "# DeepSeek 240×12 protocol on the hardened matcher",
        "",
        "> Synthetic controlled benchmark; not operational validation.",
        "",
        "The DeepSeek 240-transfer generator and 12-seed protocol are retained. Only the matcher under test is replaced by the hardened independent-receipt matcher.",
        "",
        "| Window | Loss P | Loss R | F1 | Candidate R | State accuracy | Exact coverage | Ambiguous | Unmatched | FP loss |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in curve:
        lines.append(
            f"| {row['window_days']} | {row['precision']:.3f} | {row['recall']:.3f} | "
            f"{row['f1']:.3f} | {row['candidate_recall']:.3f} | {row['state_accuracy']:.3f} | "
            f"{row['confirmed_coverage']:.3f} | {row['ambiguity_rate']:.3f} | "
            f"{row['unmatched_rate']:.3f} | {row['false_loss_rate']:.4f} |"
        )
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "- Loss precision/recall evaluate loss detection, not receipt identity resolution.",
        "- Candidate recall evaluates retrieval before resolution.",
        "- Exact coverage is limited to receipts carrying explicit source-picking provenance.",
        "- Approximate matches are intentionally never promoted or allowed to create loss claims.",
        "- Per-seed results and standard deviations are in the JSON artifact.",
    ]
    (RESULTS / "deepseek_method_on_hardened_matcher.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["curve"], indent=2))
