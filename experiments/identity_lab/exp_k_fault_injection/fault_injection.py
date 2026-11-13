"""Deterministic fault-injection harness for ERP receipt reconciliation.

All records in this module are generated fixtures shaped like Odoo exports.
They are NOT operational ERP data and cannot establish real-world detection rates.
The clean baseline is immutable by convention and hashed before mutations.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import random
from typing import Any

try:
    from ..exp_j_erp.odoo_reader import reconcile_export
except ImportError:  # direct execution
    from exp_j_erp.odoo_reader import reconcile_export


UOMS = [
    {"id": "uom_unit", "name": "Units", "category_id": "unit",
     "factor": "1", "uom_type": "reference"},
]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_clean_export(count: int = 100) -> dict:
    """Build a clean, reproducible, Odoo-export-shaped baseline."""
    moves, receipts = [], []
    origin = date(2025, 1, 1)
    for index in range(count):
        n = index + 1
        picking = f"OUT-{n:05d}"
        product = f"PRODUCT-{n:05d}"
        destination = f"RECEIVER-{n:05d}"
        qty = Decimal(10 + (index % 7))
        shipped_on = origin + timedelta(days=index)
        received_on = shipped_on + timedelta(days=1)
        moves.append({
            "id": n, "picking_id": picking, "product_id": product,
            "product_uom": "uom_unit", "product_uom_category_id": "unit",
            "quantity": str(qty), "product_uom_qty": str(qty),
            "state": "done", "location_id": "SENDER-WH",
            "location_dest_id": destination, "reference": f"SHIP-{n:05d}",
            "date": shipped_on.isoformat(),
        })
        receipts.append({
            "source_picking_id": picking,
            "counterpart_picking_id": f"IN-{n:05d}",
            "product_id": product, "counterpart_qty": str(qty),
            "counterpart_uom_id": "uom_unit",
            "product_uom_category_id": "unit", "location_id": destination,
            "counterpart_date": received_on.isoformat(),
            "counterpart_system": "independent_receiving_system",
            "counterpart_source": f"receipt-proof-{n:05d}.json",
            "recorded_at": f"{received_on.isoformat()}T12:00:00Z",
        })
    return {"moves": moves, "uoms": deepcopy(UOMS), "receipts": receipts}


def inject_faults(
    clean_export: dict,
    *,
    missing_rate: float = 0.10,
    duplicate_rate: float = 0.10,
    delayed_rate: float = 0.10,
    seed: int = 20261113,
    date_window_days: int = 3,
) -> tuple[dict, list[dict]]:
    """Mutate a copy only; selected records are disjoint and fully logged."""
    for rate in (missing_rate, duplicate_rate, delayed_rate):
        if not 0 <= rate <= 1:
            raise ValueError("fault rates must be between 0 and 1")
    if missing_rate + duplicate_rate + delayed_rate > 1:
        raise ValueError("fault rates must sum to <= 1")

    mutated = deepcopy(clean_export)
    baseline_receipts = deepcopy(clean_export["receipts"])
    indices = list(range(len(baseline_receipts)))
    random.Random(seed).shuffle(indices)
    missing_n = int(len(indices) * missing_rate)
    duplicate_n = int(len(indices) * duplicate_rate)
    delayed_n = int(len(indices) * delayed_rate)
    missing = set(indices[:missing_n])
    duplicate = set(indices[missing_n:missing_n + duplicate_n])
    delayed = set(indices[missing_n + duplicate_n:missing_n + duplicate_n + delayed_n])

    manifest: list[dict] = []
    resulting_receipts = []
    for index, receipt in enumerate(baseline_receipts):
        receipt = deepcopy(receipt)
        if index in missing:
            manifest.append({
                "fault": "missing_receipt", "shipment_id": receipt["source_picking_id"],
                "operation": "delete_receiver_record",
            })
            continue
        if index in duplicate:
            original_id = receipt["counterpart_picking_id"]
            receipt.pop("source_picking_id", None)
            duplicate_receipt = deepcopy(receipt)
            duplicate_receipt["counterpart_picking_id"] = original_id + "-DUP"
            duplicate_receipt["counterpart_source"] = "injected-duplicate-candidate"
            duplicate_receipt["recorded_at"] = "2025-12-31T23:59:00Z"
            resulting_receipts.extend([receipt, duplicate_receipt])
            manifest.append({
                "fault": "duplicate_candidate", "shipment_id": f"OUT-{index + 1:05d}",
                "operation": "remove_explicit_link_and_duplicate_receipt",
                "receiver_ids": [original_id, duplicate_receipt["counterpart_picking_id"]],
            })
            continue
        if index in delayed:
            receipt.pop("source_picking_id", None)
            original_date = date.fromisoformat(receipt["counterpart_date"])
            receipt["counterpart_date"] = (original_date + timedelta(days=date_window_days + 1)).isoformat()
            manifest.append({
                "fault": "receipt_outside_matching_window",
                "shipment_id": f"OUT-{index + 1:05d}",
                "operation": "remove_explicit_link_and_shift_receipt_date",
                "date_shift_days": date_window_days + 1,
            })
        resulting_receipts.append(receipt)

    mutated["receipts"] = resulting_receipts
    return mutated, manifest


def run_export(export: dict, date_window_days: int = 3) -> dict:
    result = reconcile_export(export["moves"], export["uoms"], export["receipts"])
    matches = result["receipt_matches"]
    states = {state: sum(1 for row in matches if row["state"] == state)
              for state in ("exact", "approximate_unique", "ambiguous", "unmatched")}
    confirmed_losses = [
        row for row in matches
        if row.get("confirmed") and "loss" in row.get("issues", [])
    ]
    confirmed_delays = [
        row for row in matches
        if row.get("confirmed") and "delay" in row.get("issues", [])
    ]
    return {
        "states": states,
        "confirmed_losses": len(confirmed_losses),
        "confirmed_delays": len(confirmed_delays),
        "false_loss_candidates_from_unconfirmed": sum(
            1 for row in matches if not row.get("confirmed") and "loss" in row.get("issues", [])
        ),
        "matches": matches,
    }


def run_experiment(
    count: int = 100,
    missing_rate: float = 0.10,
    duplicate_rate: float = 0.10,
    delayed_rate: float = 0.10,
    seed: int = 20261113,
) -> dict:
    baseline = build_clean_export(count)
    baseline_sha256 = canonical_hash(baseline)
    baseline_result = run_export(baseline)
    mutated, manifest = inject_faults(
        baseline, missing_rate=missing_rate, duplicate_rate=duplicate_rate,
        delayed_rate=delayed_rate, seed=seed,
    )
    mutated_result = run_export(mutated)
    # Ensure the caller's clean source was not modified by the injector.
    baseline_unchanged = canonical_hash(baseline) == baseline_sha256
    return {
        "classification": "synthetic_fault_injection_stress_test_not_real_validation",
        "seed": seed,
        "baseline_rows": {"moves": len(baseline["moves"]), "receipts": len(baseline["receipts"])},
        "baseline_sha256": baseline_sha256,
        "baseline_unchanged_after_injection": baseline_unchanged,
        "injection_rates": {
            "missing": missing_rate, "duplicate": duplicate_rate, "delayed": delayed_rate,
        },
        "fault_manifest": manifest,
        "baseline_result": {k: v for k, v in baseline_result.items() if k != "matches"},
        "mutated_result": {k: v for k, v in mutated_result.items() if k != "matches"},
    }
