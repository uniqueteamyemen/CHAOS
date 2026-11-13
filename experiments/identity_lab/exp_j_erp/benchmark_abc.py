"""Paired A/B/C benchmark for legacy, hardened and hybrid ERP receipt matching.

A is a frozen compatibility port of the historical matcher at
4c9ae2614aa290c4cf19c347129467f049d09867. Its input adapter maps the historical
edge-key convention to source_picking_id; its matching/classification logic is unchanged.
B and C receive the same canonical shipment/receipt records and UoM metadata.
Synthetic ground truth is generated before any matcher runs.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .reconcile import match_counterpart_receipts
from .hybrid_reconcile import match_hybrid

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEEDS = 40
LOSS_THRESHOLD = Decimal("0.5")
UOMS = {
    "unit": {"id": "unit", "category_id": "count", "factor": "1", "uom_type": "reference"},
    "dozen": {"id": "dozen", "category_id": "count", "factor": "0.0833333333333333333333333333", "uom_type": "bigger"},
    "kg": {"id": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "g": {"id": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}


def shipment(sid, qty="10", product=None, destination=None, sender=None, day="2025-01-01", uom="unit"):
    category = "weight" if uom in ("kg", "g") else "count"
    product = product or f"P-{sid}"
    destination = destination or f"D-{sid}"
    sender = sender or f"S-{sid}"
    return {
        "picking_id": sid, "product_id": product, "location_id": sender,
        "location_dest_id": destination, "from_entity": sender,
        "reference_uom_id": "kg" if category == "weight" else "unit",
        "product_uom_category_id": category, "quantity": str(qty), "dates": [day],
    }


def receipt(rid, source=None, qty="10", uom="unit", product="AUTO", destination="AUTO",
            sender="AUTO", day="2025-01-02", complete=True):
    category = "weight" if uom in ("kg", "g") else "count"
    if product == "AUTO":
        product = f"P-{source}" if source else "P-UNLINKED"
    if destination == "AUTO":
        destination = f"D-{source}" if source else "D-UNLINKED"
    if sender == "AUTO":
        sender = f"S-{source}" if source else "S-UNLINKED"
    row = {
        "source_picking_id": source, "counterpart_picking_id": rid,
        "product_id": product, "location_id": destination, "from_entity": sender,
        "counterpart_qty": str(qty), "counterpart_uom_id": uom,
        "product_uom_category_id": category, "counterpart_date": day,
        "counterpart_system": "receiver-wms", "counterpart_source": "receipt-record",
        "recorded_at": day + "T10:00:00",
    }
    if not complete:
        row["counterpart_source"] = None
    return row


def make_cases(seed):
    rng = random.Random(seed)
    ss, rr, truth = [], [], {}
    def add(s, receipts, exact=False, received=None, candidate_id=None, note=""):
        ss.append(s)
        rr.extend(receipts)
        truth[s["picking_id"]] = {
            "exact": exact, "loss": bool(exact and received is not None and
                Decimal(s["quantity"]) - Decimal(str(received)) > LOSS_THRESHOLD),
            "received": None if received is None else str(received),
            "candidate_id": candidate_id, "candidate_ids": ([candidate_id] if candidate_id else []), "note": note,
        }

    # Exact full receipt, exact loss, and exact over-receipt.
    add(shipment(f"{seed}-E0"), [receipt(f"{seed}-R0", f"{seed}-E0")],
        True, "10", note="exact_full")
    loss_qty = Decimal("8.5") - Decimal(str(rng.randint(0, 20))) / Decimal("100")
    add(shipment(f"{seed}-E1"), [receipt(f"{seed}-R1", f"{seed}-E1", loss_qty)],
        True, loss_qty, note="exact_loss")
    add(shipment(f"{seed}-E2"), [receipt(f"{seed}-R2", f"{seed}-E2", "10.7")],
        True, "10.7", note="exact_over")

    # Two linked partial receipts: C can sum them; A/B should remain conservative.
    add(shipment(f"{seed}-PART"), [
        receipt(f"{seed}-RP1", f"{seed}-PART", "4"),
        receipt(f"{seed}-RP2", f"{seed}-PART", "6"),
    ], True, "10", note="linked_partials")

    # Provenance defect and explicit identity conflict.
    add(shipment(f"{seed}-INCOMP"), [
        receipt(f"{seed}-RI", f"{seed}-INCOMP", complete=False)
    ], False, note="incomplete_provenance")
    add(shipment(f"{seed}-CONFLICT"), [
        receipt(f"{seed}-RC", f"{seed}-CONFLICT", product="WRONG")
    ], False, note="explicit_product_conflict")

    # Approximate unique and ambiguous candidate cases.
    app_sid = f"{seed}-APP"
    app = shipment(app_sid)
    cand = receipt(f"{seed}-RA", None, "10.1", product=app["product_id"],
                   destination=app["location_dest_id"], sender=app["from_entity"])
    add(app, [cand], False, candidate_id=f"{seed}-RA",
        note="approximate_unique")
    multi = shipment(f"{seed}-MULTI")
    add(multi, [
        receipt(f"{seed}-RM1", None, "10", product=multi["product_id"],
                destination=multi["location_dest_id"], sender=multi["from_entity"]),
        receipt(f"{seed}-RM2", None, "10.05", product=multi["product_id"],
                destination=multi["location_dest_id"], sender=multi["from_entity"]),
    ], False, note="multiple_candidates")
    truth[f"{seed}-MULTI"]["candidate_ids"] = [f"{seed}-RM1", f"{seed}-RM2"]

    # Same approximate receipt fits two shipments; it must not be assigned twice.
    shared_product, shared_destination = f"P-{seed}-SHARED", f"D-{seed}-SHARED"
    sh1 = shipment(f"{seed}-SH1", product=shared_product,
                   destination=shared_destination, sender="S1")
    sh2 = shipment(f"{seed}-SH2", product=shared_product,
                   destination=shared_destination, sender="S2")
    shared = receipt(f"{seed}-SHARED", None, "10", product=shared_product,
                     destination=shared_destination, sender=None)
    add(sh1, [shared], False, candidate_id=f"{seed}-SHARED", note="shared_candidate")
    add(sh2, [], False, candidate_id=f"{seed}-SHARED", note="shared_candidate")

    # Odoo UoM conversion and out-of-window receipt.
    add(shipment(f"{seed}-DOZEN"), [
        receipt(f"{seed}-RD", f"{seed}-DOZEN", "0.75", "dozen")
    ], True, "9", note="dozen_conversion")
    late = shipment(f"{seed}-LATE")
    add(late, [
        receipt(f"{seed}-RL", None, "10", product=late["product_id"],
                destination=late["location_dest_id"], sender=late["from_entity"],
                day="2025-01-10")
    ], False, note="outside_date_window")

    # Duplicate receiver identity must never become a confirmed unique receipt.
    dup = receipt(f"{seed}-DUP", f"{seed}-DUPSHIP", "10")
    add(shipment(f"{seed}-DUPSHIP"), [dup, dict(dup)], False, note="duplicate_receipt_id")

    # A deliberately wrong product candidate and a location-conflicting explicit link.
    wrong_candidate = shipment(f"{seed}-WRONGC")
    add(wrong_candidate, [
        receipt(f"{seed}-RWC", None, "10", product="OTHER",
                destination=wrong_candidate["location_dest_id"],
                sender=wrong_candidate["from_entity"])
    ], False, note="wrong_product_candidate")
    add(shipment(f"{seed}-WRONGL"), [
        receipt(f"{seed}-RWL", f"{seed}-WRONGL", "10", destination="OTHER")
    ], False, note="explicit_location_conflict")

    # Unkeyed but valid receipt: candidate evidence only.
    unkeyed = shipment(f"{seed}-UNKEY")
    add(unkeyed, [
        receipt(f"{seed}-RUK", None, "10", product=unkeyed["product_id"],
                destination=unkeyed["location_dest_id"], sender=unkeyed["from_entity"])
    ], False, candidate_id=f"{seed}-RUK", note="unkeyed_reference")

    return ss, rr, truth


def legacy_a(shipments, receipts):
    """Frozen historical matcher logic, with a schema-only adapter."""
    edges = [{
        "transfer_id": s["picking_id"], "product": s["product_id"],
        "from_entity": s["from_entity"], "to_entity": s["location_dest_id"],
        "qty_out": float(s["quantity"]),
    } for s in shipments]
    old_receipts = []
    for r in receipts:
        old_receipts.append({
            **r,
            # Historical A compared this field to transfer_id. Map the source link
            # into that legacy key; preserve the actual receiver ID separately.
            "counterpart_picking_id": r.get("source_picking_id") or "",
            "receiver_id": r.get("counterpart_picking_id"),
            "counterpart_qty": r.get("counterpart_qty"),
            "counterpart_uom": r.get("counterpart_uom_id"),
            "from_entity": r.get("from_entity"),
            "to_entity": r.get("location_id"),
            "day_offset": 1 if r.get("counterpart_date") == "2025-01-02" else 9,
        })
    from .legacy_uom import convert
    by_key = {}
    for r in old_receipts:
        key = str(r.get("counterpart_picking_id") or "")
        if key:
            by_key.setdefault(key, []).append(r)
    results = []
    for e in edges:
        key = str(e["transfer_id"])
        exact = by_key.get(key, [])
        if len(exact) == 1:
            results.append({"edge": key, "state": "confirmed", "receipt": exact[0], "candidate_ids": []})
            continue
        if len(exact) > 1:
            results.append({"edge": key, "state": "ambiguous", "candidate_ids": []})
            continue
        candidates = []
        for r in old_receipts:
            if str(r.get("product_id")) != str(e.get("product")):
                continue
            if str(r.get("from_entity")) != str(e.get("from_entity")):
                continue
            if str(r.get("to_entity")) != str(e.get("to_entity")):
                continue
            qty, _ = convert(float(r.get("counterpart_qty") or 0),
                             r.get("counterpart_uom", "unit"), "unit")
            if qty is None or (e["qty_out"] and abs(qty-e["qty_out"])/e["qty_out"] > .02):
                continue
            if abs(int(r.get("day_offset", 0))) > 3:
                continue
            candidates.append(r)
        results.append({"edge": key, "state": "candidate" if len(candidates)==1 else
                        "ambiguous" if candidates else "unmatched",
                        "receipt": candidates[0] if len(candidates)==1 else None,
                        "candidate_ids": [str(x.get("receiver_id") or "") for x in candidates]})
    return results


def legacy_a_normalized(results):
    from .legacy_uom import convert
    normalized = {}
    for r in results:
        confirmed = r["state"] == "confirmed"
        received = None
        loss_claim = False
        if r.get("receipt"):
            received, _ = convert(
                float(r["receipt"].get("counterpart_qty") or 0),
                r["receipt"].get("counterpart_uom", "unit"), "unit"
            )
        if confirmed and received is not None:
            edge_qty = 10.0
            loss_claim = edge_qty - received > 0.5
        normalized[r["edge"]] = {
            "confirmed": confirmed,
            "candidate": r["state"] == "candidate",
            "ambiguous": r["state"] == "ambiguous",
            "received": None if received is None else str(received),
            "loss_claim": loss_claim,
            "candidate_ids": r.get("candidate_ids", []),
        }
    return normalized


def normalize_b(results, unlinked_receipt_ids):
    out = {}
    for r in results:
        out[r["picking_id"]] = {
            "confirmed": bool(r.get("confirmed")),
            "candidate": r.get("state") == "approximate_unique",
            "ambiguous": r.get("state") == "ambiguous",
            "received": r.get("qty_received"),
            "loss_claim": "loss" in r.get("issues", []),
            "candidate_ids": [rid for rid in r.get("candidate_receipt_ids", []) if rid in unlinked_receipt_ids],
        }
    return out


def normalize_c(results, unlinked_receipt_ids):
    out = {}
    for r in results:
        out[r["picking_id"]] = {
            "confirmed": bool(r.get("confirmed")),
            "candidate": r.get("state") == "candidate_approximate",
            "ambiguous": r.get("state") == "ambiguous",
            "received": r.get("qty_received"),
            "loss_claim": "loss" in r.get("issues", []),
            "candidate_ids": [rid for rid in r.get("candidate_receipt_ids", []) if rid in unlinked_receipt_ids],
        }
    return out


def score(name, predicted, truth):
    tp = fp = fn = 0
    loss_tp = loss_fp = loss_fn = 0
    candidate_tp = candidate_fp = candidate_fn = 0
    false_confirmations = []
    for sid, t in truth.items():
        p = predicted.get(sid, {})
        confirmed = bool(p.get("confirmed"))
        if confirmed and t["exact"]: tp += 1
        elif confirmed and not t["exact"]:
            fp += 1
            false_confirmations.append(sid)
        elif not confirmed and t["exact"]: fn += 1
        if p.get("loss_claim") and t["loss"]: loss_tp += 1
        elif p.get("loss_claim") and not t["loss"]: loss_fp += 1
        elif not p.get("loss_claim") and t["loss"]: loss_fn += 1
        expected_candidates = set(t.get("candidate_ids") or [])
        actual_candidates = set(p.get("candidate_ids") or [])
        candidate_tp += len(expected_candidates & actual_candidates)
        candidate_fp += len(actual_candidates - expected_candidates)
        candidate_fn += len(expected_candidates - actual_candidates)
    precision = tp/(tp+fp) if tp+fp else 1.0
    recall = tp/(tp+fn) if tp+fn else 1.0
    loss_precision = loss_tp/(loss_tp+loss_fp) if loss_tp+loss_fp else 1.0
    loss_recall = loss_tp/(loss_tp+loss_fn) if loss_tp+loss_fn else 1.0
    return {
        "engine": name, "exact_tp": tp, "false_confirmations": fp,
        "missed_exact": fn, "exact_precision": round(precision, 6),
        "exact_recall": round(recall, 6), "loss_tp": loss_tp,
        "false_loss_claims": loss_fp, "missed_losses": loss_fn,
        "loss_precision": round(loss_precision, 6),
        "loss_recall": round(loss_recall, 6),
        "candidate_tp": candidate_tp, "candidate_fp": candidate_fp,
        "candidate_fn": candidate_fn,
        "candidate_precision": round(candidate_tp/(candidate_tp+candidate_fp), 6) if candidate_tp+candidate_fp else 1.0,
        "candidate_recall": round(candidate_tp/(candidate_tp+candidate_fn), 6) if candidate_tp+candidate_fn else 1.0,
        "false_confirmation_ids": false_confirmations,
    }


def run():
    totals = Counter()
    rows = []
    timings = {"A": [], "B": [], "C": []}
    for seed in range(SEEDS):
        shipments, receipts, truth = make_cases(seed)
        start = time.perf_counter()
        a = legacy_a(shipments, receipts)
        timings["A"].append(time.perf_counter()-start)
        start = time.perf_counter()
        b = match_counterpart_receipts(
            shipments, receipts, UOMS, date_window_days=3,
            quantity_tolerance=Decimal("0.2"),
        )
        timings["B"].append(time.perf_counter()-start)
        start = time.perf_counter()
        c = match_hybrid(shipments, receipts, UOMS, date_window_days=3,
                         candidate_quantity_tolerance_relative=Decimal("0.02"),
                         reconciliation_quantity_tolerance=Decimal("0.01"),
                         loss_classification_threshold=LOSS_THRESHOLD)
        timings["C"].append(time.perf_counter()-start)
        unlinked_ids = {
            str(r.get("counterpart_picking_id") or "") for r in receipts
            if not r.get("source_picking_id") and r.get("counterpart_picking_id")
        }
        preds = {"A": legacy_a_normalized(a),
                 "B": normalize_b(b, unlinked_ids),
                 "C": normalize_c(c, unlinked_ids)}
        if seed == 0:
            print("CANDIDATE_DEBUG", json.dumps({
                label: {sid: pred[sid]["candidate_ids"] for sid in truth
                        if truth[sid].get("candidate_ids")}
                for label, pred in preds.items()
            }))
        for label, pred in preds.items():
            row = score(label, pred, truth)
            rows.append({"seed": seed, **row})
            for k, v in row.items():
                if isinstance(v, int):
                    totals[f"{label}.{k}"] += v

    summary = {}
    for label in ("A", "B", "C"):
        subset = [r for r in rows if r["engine"] == label]
        n = sum(r["exact_tp"] + r["false_confirmations"] for r in subset)
        exact_tp = sum(r["exact_tp"] for r in subset)
        exact_fp = sum(r["false_confirmations"] for r in subset)
        exact_fn = sum(r["missed_exact"] for r in subset)
        ltp = sum(r["loss_tp"] for r in subset)
        lfp = sum(r["false_loss_claims"] for r in subset)
        lfn = sum(r["missed_losses"] for r in subset)
        ctp = sum(r["candidate_tp"] for r in subset)
        cfp = sum(r["candidate_fp"] for r in subset)
        cfn = sum(r["candidate_fn"] for r in subset)
        summary[label] = {
            "exact_tp": exact_tp, "false_confirmations": exact_fp,
            "missed_exact": exact_fn,
            "exact_precision": round(exact_tp/(exact_tp+exact_fp), 6) if exact_tp+exact_fp else 1,
            "exact_recall": round(exact_tp/(exact_tp+exact_fn), 6) if exact_tp+exact_fn else 1,
            "loss_tp": ltp, "false_loss_claims": lfp, "missed_losses": lfn,
            "loss_precision": round(ltp/(ltp+lfp), 6) if ltp+lfp else 1,
            "loss_recall": round(ltp/(ltp+lfn), 6) if ltp+lfn else 1,
            "candidate_tp": ctp, "candidate_fp": cfp, "candidate_fn": cfn,
            "candidate_precision": round(ctp/(ctp+cfp), 6) if ctp+cfp else 1,
            "candidate_recall": round(ctp/(ctp+cfn), 6) if ctp+cfn else 1,
            "mean_runtime_ms": round(statistics.mean(timings[label])*1000, 4),
            "p95_runtime_ms": round(sorted(timings[label])[int(.95*(len(timings[label])-1))]*1000, 4),
        }

    payload = {
        "benchmark": "paired_erp_reconciliation_A_B_C",
        "classification": "synthetic_adversarial_benchmark_not_production_validation",
        "seeds": SEEDS, "cases_per_seed": len(make_cases(0)[0]),
        "total_shipment_cases": SEEDS*len(make_cases(0)[0]),
        "loss_threshold": str(LOSS_THRESHOLD),
        "A_reference_commit": "4c9ae2614aa290c4cf19c347129467f049d09867",
        "B": "current match_counterpart_receipts",
        "C": "current match_hybrid",
        "summary": summary,
        "per_seed": rows,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "erp_abc_benchmark.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "# ERP Reconciliation A/B/C Comparative Benchmark", "",
        "**Classification:** synthetic adversarial benchmark; not production validation.", "",
        f"- Seeds: {SEEDS}", f"- Cases per seed: {payload['cases_per_seed']}",
        f"- Total shipment cases: {payload['total_shipment_cases']}",
        f"- Shared loss threshold: {LOSS_THRESHOLD}", "",
        "| Metric | A — legacy | B — hardened | C — hybrid |",
        "|---|---:|---:|---:|",
    ]
    keys = ["exact_precision", "exact_recall", "loss_precision", "loss_recall",
            "candidate_precision", "candidate_recall", "false_confirmations",
            "false_loss_claims", "missed_exact", "missed_losses",
            "candidate_tp", "candidate_fp", "candidate_fn", "mean_runtime_ms", "p95_runtime_ms"]
    for key in keys:
        lines.append("| " + key + " | " + " | ".join(str(summary[x][key]) for x in ("A","B","C")) + " |")
    lines += ["", "## Interpretation guardrails", "",
        "- Exact-match scoring is evaluated against source_picking_id ground truth.",
        "- A is the historical algorithm with a schema-only adapter for its old transfer-key convention.",
        "- B and C receive identical canonical records and UoM metadata.",
        "- Candidate discovery and confirmed reconciliation are scored separately.",
        "- Loss classification uses the same declared 0.5-unit ground-truth threshold.",
        "- Runtime is informational and measured in a shared Python process; it is not a deployment benchmark.",
        "- Synthetic performance cannot establish production readiness or real-world accuracy.", ""]
    (RESULTS / "erp_abc_benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": summary, "total_shipment_cases": payload["total_shipment_cases"]}, indent=2))
    return payload


if __name__ == "__main__":
    run()
