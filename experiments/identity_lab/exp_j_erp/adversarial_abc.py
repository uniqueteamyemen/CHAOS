"""Adversarial cases the original A/B/C benchmark avoids.

Each case targets a known risk surface the original `make_cases` never generates:

  1. decoy_qty  — a decoy receipt (wrong product) with a DIFFERENT quantity (5 vs 10).
  2. multiline  — one picking_id with two product lines (the normal ERP shape).
  3. reuse      — two split rows of one picking (same product), one receipt linked.

Run from the repo root:
    python -m experiments.identity_lab.exp_j_erp.adversarial_abc
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal

from .benchmark_abc import UOMS, LOSS_THRESHOLD, legacy_a, receipt, shipment
from .hybrid_reconcile import match_hybrid
from .reconcile import match_counterpart_receipts

TOL = Decimal("0.02")
DATE_WINDOW = 3


def run_a(shipments, receipts):
    """A's raw legacy result, then loss computed from the shipment's own quantity."""
    raw = legacy_a(shipments, receipts)
    qty = {s["picking_id"]: Decimal(str(s["quantity"])) for s in shipments}
    out = []
    for r in raw:
        confirmed = r["state"] == "confirmed"
        loss = False
        if confirmed and r.get("receipt"):
            received = Decimal(str(r["receipt"].get("counterpart_qty") or 0))
            loss = (qty.get(r["edge"], Decimal("10")) - received) > LOSS_THRESHOLD
        out.append({"shipment": r["edge"], "state": r["state"], "confirmed": confirmed,
                    "loss_claim": loss, "reason": None})
    return out


def run_b(shipments, receipts):
    out = []
    for s in shipments:
        tol = abs(Decimal(str(s["quantity"]))) * TOL
        rows = match_counterpart_receipts(
            [s], receipts, UOMS, date_window_days=DATE_WINDOW,
            quantity_tolerance=tol, loss_classification_threshold=LOSS_THRESHOLD,
        )
        r = rows[0] if rows else {}
        out.append({"shipment": s["picking_id"], "state": r.get("state"),
                    "confirmed": bool(r.get("confirmed")),
                    "loss_claim": "loss" in (r.get("issues") or []),
                    "reason": r.get("reason")})
    return out


def run_b_full(shipments, receipts):
    """B over the full batch with a per-shipment relative tolerance."""
    rows = match_counterpart_receipts(
        shipments, receipts, UOMS, date_window_days=DATE_WINDOW,
        quantity_tolerance=Decimal("0"), quantity_tolerance_relative=TOL,
        loss_classification_threshold=LOSS_THRESHOLD,
    )
    return [{"shipment": r.get("picking_id"), "state": r.get("state"),
             "confirmed": bool(r.get("confirmed")),
             "loss_claim": "loss" in (r.get("issues") or []),
             "reason": r.get("reason")} for r in rows]


def run_c(shipments, receipts):
    rows = match_hybrid(
        shipments, receipts, UOMS, date_window_days=DATE_WINDOW,
        candidate_quantity_tolerance_relative=TOL,
        reconciliation_quantity_tolerance=Decimal("0.01"),
        loss_classification_threshold=LOSS_THRESHOLD,
    )
    return [{"shipment": r.get("picking_id"), "state": r.get("state"),
             "confirmed": bool(r.get("confirmed")),
             "loss_claim": bool(r.get("loss_claim")) or "loss" in (r.get("issues") or []),
             "reason": r.get("reason")} for r in rows]


def case_decoy_qty(seed):
    """Shipment qty=10; decoy linked to it, WRONG product, qty=5. Truth: no loss."""
    s = shipment(f"{seed}-DQ", qty="10")
    r = receipt(f"{seed}-DQR", source=f"{seed}-DQ", qty="5", product="WRONG")
    return [s], [r]


def case_multiline(seed):
    """One picking, two product lines, one receipt per line (normal ERP shape)."""
    pid = f"{seed}-ML"
    s1 = shipment(pid, qty="10", product="P1", sender="S1")
    s1["location_dest_id"] = "D-ML"
    s2 = shipment(pid, qty="7", product="P2", sender="S1")
    s2["location_dest_id"] = "D-ML"
    r1 = receipt(f"{seed}-MLR1", source=pid, qty="10", product="P1", sender="S1")
    r2 = receipt(f"{seed}-MLR2", source=pid, qty="7", product="P2", sender="S1")
    r1["location_id"] = "D-ML"
    r2["location_id"] = "D-ML"
    return [s1, s2], [r1, r2]


def case_reuse(seed):
    """Two split rows of one picking (same product), one receipt. Must not confirm both."""
    pid = f"{seed}-RU"
    s1 = shipment(pid, qty="10", product="P1", sender="S1")
    s2 = shipment(pid, qty="10", product="P1", sender="S1")
    r = receipt(f"{seed}-RUR", source=pid, qty="10", product="P1", sender="S1")
    return [s1, s2], [r]


CASES = {"decoy_qty": case_decoy_qty, "multiline": case_multiline, "reuse": case_reuse}


def run(seeds=40):
    report = {}
    for name, builder in CASES.items():
        totals = {e: {"confirmed": 0, "loss": 0} for e in ("A", "B", "C")}
        sample = None
        for seed in range(seeds):
            shipments, receipts = builder(seed)
            res = {"A": run_a(shipments, receipts),
                   "B": run_b_full(shipments, receipts),
                   "C": run_c(shipments, receipts)}
            if sample is None:
                sample = res
            for e, rows in res.items():
                totals[e]["confirmed"] += sum(1 for r in rows if r["confirmed"])
                totals[e]["loss"] += sum(1 for r in rows if r["loss_claim"])
        report[name] = {"seeds": seeds, "shipments_per_seed": len(builder(0)[0]),
                        "totals": totals, "sample_seed0": sample}
    return report


def main():
    report = run(seeds=40)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    problems = []
    seeds = 40
    # A is the frozen legacy engine and is expected to keep both defects.
    for engine in ("B", "C"):
        if report["multiline"]["totals"][engine]["confirmed"] != seeds * 2:
            problems.append(f"multiline {engine} confirmed != {seeds * 2}")
        if report["reuse"]["totals"][engine]["confirmed"] > seeds:
            problems.append(f"reuse {engine} confirmed > {seeds} (receipt reused)")
        if report["decoy_qty"]["totals"][engine]["loss"] != 0:
            problems.append(f"decoy_qty {engine} emitted a false loss")
    if problems:
        print("ADVERSARIAL INVARIANTS FAILED: " + "; ".join(problems), file=sys.stderr)
        return 1
    print("adversarial invariants passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
