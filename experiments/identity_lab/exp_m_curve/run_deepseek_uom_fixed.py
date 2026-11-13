"""Experiment M runner using the isolated, corrected DeepSeek scorer.

Matching logic and synthetic generator are imported from the unchanged baseline.
Writes every seed/window/policy row so paired comparison is possible.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "exp_m_curve"
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(BASE))
sys.path.insert(2, str(ROOT / "exp_j_erp"))

from curve import (  # noqa: E402
    TRANSFERS, SEEDS, WINDOWS, QTY_TOL, generate, match,
)
from reconcile_benchmark import classify  # noqa: E402


def evaluate(seed: int, window: int, promote: bool) -> dict:
    edges, receipts, truth, meta = generate(seed)
    ref_uom = {product: values[0] for product, values in meta["ref_uom"].items()}
    results = match(edges, receipts, date_window=window, qty_tolerance=QTY_TOL,
                    ref_uom=ref_uom, promote_unique=promote)
    summary = classify(results, edges, ref_uom)
    by_edge = {r["edge"]: r for r in results}
    truth_by_edge = {t["transfer_id"]: t for t in truth}
    detected = {x["edge"] for x in summary["confirmed_loss"]}
    actual = {t["transfer_id"] for t in truth if t["has_loss"]}
    tp, fp, fn = len(detected & actual), len(detected - actual), len(actual - detected)
    loss_precision = tp / (tp + fp) if tp + fp else 1.0
    loss_recall = tp / (tp + fn) if tp + fn else 1.0
    confirmed = summary["confirmed"] + summary["confirmed_approx"]
    confirmed_rows = [r for r in results if r["state"] in ("confirmed", "confirmed_approx")]
    strict_tp = sum(1 for r in confirmed_rows if r["state"] == "confirmed"
                    and (r.get("receipt") or {}).get("_owner") == r["edge"])
    strict_fp = sum(1 for r in confirmed_rows if r["state"] == "confirmed"
                    and (r.get("receipt") or {}).get("_owner") != r["edge"])
    strict_precision = strict_tp / (strict_tp + strict_fp) if strict_tp + strict_fp else 1.0
    candidate_truth = {t["transfer_id"] for t in truth if not t["deleted"]}
    candidate_found = {r["edge"] for r in results if r["state"] in
                       ("candidate", "confirmed_approx", "confirmed")}
    candidate_recall = len(candidate_found & candidate_truth) / len(candidate_truth) if candidate_truth else 1.0
    return {
        "seed": seed, "window": window, "policy": "promote" if promote else "strict",
        "transfers": TRANSFERS, "quantity_tolerance": QTY_TOL,
        "loss_precision": loss_precision, "loss_recall": loss_recall,
        "candidate_recall": candidate_recall, "strict_confirmation_precision": strict_precision,
        "ambiguity": summary["ambiguous"], "false_positives": fp,
        "confirmed": summary["confirmed"], "confirmed_approx": summary["confirmed_approx"],
        "candidate": summary["candidate"], "unmatched": summary["unmatched"],
        "tp": tp, "fp": fp, "fn": fn,
    }


def main() -> None:
    rows = [evaluate(seed, window, promote)
            for promote in (False, True)
            for window in WINDOWS for seed in range(SEEDS)]
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "deepseek_uom_fixed_per_seed.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    summary = {}
    for policy in ("strict", "promote"):
        summary[policy] = {}
        for window in WINDOWS:
            subset = [r for r in rows if r["policy"] == policy and r["window"] == window]
            summary[policy][str(window)] = {
                key: round(statistics.mean(r[key] for r in subset), 6)
                for key in ("loss_precision", "loss_recall", "candidate_recall",
                            "strict_confirmation_precision", "ambiguity", "false_positives")
            }
    (out / "deepseek_uom_fixed_summary.json").write_text(
        json.dumps({"seeds": SEEDS, "transfers": TRANSFERS, "summary": summary},
                   indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "seeds": SEEDS, "transfers_per_seed": TRANSFERS,
                      "output": str(out)}, indent=2))


if __name__ == "__main__":
    main()
