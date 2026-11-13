"""Paired Experiment M benchmark: corrected DeepSeek scorer vs hardened matcher.

The synthetic generator and labels are shared byte-for-byte for both algorithms.
The hardened implementation is imported from the separate feat/erp-reconcile-hardening
checkout supplied by the workflow. No production matcher code is copied or modified.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import random
import statistics
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDENTITY_ROOT = HERE.parent
sys.path.insert(0, str(IDENTITY_ROOT / "exp_j_erp"))

from curve import TRANSFERS, SEEDS, WINDOWS, QTY_TOL, generate, match as deepseek_match
from reconcile_benchmark import classify as deepseek_classify
from uom import convert

HARDENED_ROOT = Path(os.environ.get(
    "HARDENED_IDENTITY_ROOT",
    str(HERE.parents[2] / "hardened" / "experiments" / "identity_lab"),
)).resolve()
if not HARDENED_ROOT.exists():
    raise RuntimeError(
        "Hardened matcher checkout not found. Set HARDENED_IDENTITY_ROOT to "
        "the feat/erp-reconcile-hardening experiments/identity_lab directory."
    )
sys.path.insert(0, str(HARDENED_ROOT))
from exp_j_erp.reconcile import match_counterpart_receipts  # noqa: E402

RESULTS = HERE / "results"
REL_TOL = float(QTY_TOL)
BASE_DATE = date(2025, 9, 1)
UOMS = {
    "unit": {"id": "unit", "category_id": "count", "factor": "1", "uom_type": "reference"},
    "dozen": {"id": "dozen", "category_id": "count", "factor": "0.083333333333333333", "uom_type": "bigger"},
    "kg": {"id": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "g": {"id": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}


def _catalog_uom(meta: dict) -> dict[str, str]:
    return {product: values[0] for product, values in meta["ref_uom"].items()}


def _receipt_id(index: int, duplicate: bool = False) -> str:
    return f"RCV-DUP-{index:04d}" if duplicate else f"RCV-{index:04d}"


def _dataset_digest(edges: list[dict], receipts: list[dict], truth: list[dict]) -> str:
    payload = json.dumps(
        {"edges": edges, "receipts": receipts, "truth": truth},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hardened_inputs(edges: list[dict], receipts: list[dict],
                     ref_uom: dict[str, str]) -> tuple[list[dict], list[dict], dict[str, str]]:
    shipments = []
    for edge in edges:
        target = ref_uom[str(edge["product"])]
        shipments.append({
            "picking_id": str(edge["transfer_id"]),
            "product_id": str(edge["product"]),
            "location_id": str(edge["from_entity"]),
            "location_dest_id": str(edge["to_entity"]),
            "reference_uom_id": target,
            "product_uom_category_id": "count" if target == "unit" else "weight",
            "quantity": str(edge["qty_out"]),
            "dates": [BASE_DATE.isoformat()],
        })

    adapted_receipts = []
    id_to_owner = {}
    for index, receipt in enumerate(receipts):
        duplicate = receipt.get("counterpart_source") == "duplicate"
        receipt_id = _receipt_id(index, duplicate)
        owner = str(receipt.get("_owner") or "")
        id_to_owner[receipt_id] = owner
        day = int(receipt.get("day_offset") or 0)
        adapted_receipts.append({
            "source_picking_id": (
                str(receipt["counterpart_picking_id"])
                if receipt.get("counterpart_picking_id") else None
            ),
            "counterpart_picking_id": receipt_id,
            "product_id": str(receipt["product_id"]),
            "location_id": str(receipt["to_entity"]),
            "counterpart_qty": str(receipt["counterpart_qty"]),
            "counterpart_uom_id": str(receipt["counterpart_uom"]),
            "product_uom_category_id": (
                "count" if ref_uom[str(receipt["product_id"])] == "unit" else "weight"
            ),
            "counterpart_date": (BASE_DATE + timedelta(days=day)).isoformat(),
            "counterpart_system": "synthetic_independent_receiving",
            "counterpart_source": str(receipt.get("counterpart_source") or "synthetic"),
            "recorded_at": (BASE_DATE + timedelta(days=day)).isoformat() + "T08:00:00",
            "_owner": owner,
        })
    return shipments, adapted_receipts, id_to_owner


def _deepseek_candidates(edge: dict, receipts: list[dict], ref_uom: dict[str, str],
                         window: int) -> list[dict]:
    key = str(edge["transfer_id"])
    exact = [r for r in receipts if str(r.get("counterpart_picking_id") or "") == key]
    if exact:
        return exact
    candidates = []
    target = ref_uom[str(edge["product"])]
    sent = float(edge["qty_out"])
    for receipt in receipts:
        if str(receipt.get("product_id")) != str(edge.get("product")):
            continue
        if str(receipt.get("from_entity")) != str(edge.get("from_entity")):
            continue
        if str(receipt.get("to_entity")) != str(edge.get("to_entity")):
            continue
        if abs(int(receipt.get("day_offset", 0))) > window:
            continue
        try:
            qty, reason = convert(
                float(receipt["counterpart_qty"]),
                str(receipt.get("counterpart_uom") or ""),
                target,
            )
        except (KeyError, TypeError, ValueError):
            continue
        if qty is None or (sent and abs(qty - sent) / abs(sent) > REL_TOL):
            continue
        candidates.append(receipt)
    return candidates


def _metric_counts(predicted_loss: set[str], truth: list[dict]) -> dict:
    actual = {str(row["transfer_id"]) for row in truth if row["has_loss"]}
    tp = len(predicted_loss & actual)
    fp = len(predicted_loss - actual)
    fn = len(actual - predicted_loss)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "loss_precision": precision, "loss_recall": recall,
    }


def _score_deepseek(edges: list[dict], receipts: list[dict], truth: list[dict],
                    ref_uom: dict[str, str], seed: int, window: int,
                    promote: bool) -> dict:
    matches = deepseek_match(
        edges, receipts, date_window=window, qty_tolerance=REL_TOL,
        ref_uom=ref_uom, promote_unique=promote,
    )
    summary = deepseek_classify(
        matches, edges, ref_uom=ref_uom,
        qty_tolerance_relative=REL_TOL,
    )
    detected = {str(row["edge"]) for row in summary["confirmed_loss"]}
    loss = _metric_counts(detected, truth)

    owners = {str(r["transfer_id"]): str(r["transfer_id"]) for r in truth}
    strict_rows = [r for r in matches if r["state"] == "confirmed"]
    strict_correct = sum(
        1 for row in strict_rows
        if str((row.get("receipt") or {}).get("_owner") or "") == str(row["edge"])
    )
    strict_precision = strict_correct / len(strict_rows) if strict_rows else 1.0
    approximate_rows = [r for r in matches if r["state"] == "confirmed_approx"]
    approximate_correct = sum(
        1 for row in approximate_rows
        if str((row.get("receipt") or {}).get("_owner") or "") == str(row["edge"])
    )
    approximate_precision = (
        approximate_correct / len(approximate_rows) if approximate_rows else None
    )

    candidate_hits = sum(
        1 for edge in edges
        if any(str(r.get("_owner") or "") == str(edge["transfer_id"])
               for r in _deepseek_candidates(edge, receipts, ref_uom, window))
    )
    return {
        "algorithm": "deepseek_corrected",
        "policy": "promote" if promote else "strict",
        "seed": seed, "window": window, **loss,
        "candidate_recall": candidate_hits / len(edges),
        "strict_confirmation_precision": strict_precision,
        "approximate_confirmation_precision": approximate_precision,
        "strict_confirmations": len(strict_rows),
        "approximate_confirmations": len(approximate_rows),
        "ambiguity": summary["ambiguous"],
        "false_positives": loss["fp"],
        "unmatched": summary["unmatched"],
        "candidate": summary["candidate"],
        "uom_conversion_errors": summary["ambiguous"] - sum(
            1 for row in matches if row["state"] == "ambiguous"
        ),
    }


def _score_hardened(edges: list[dict], receipts: list[dict], truth: list[dict],
                    ref_uom: dict[str, str], seed: int, window: int) -> dict:
    shipments, adapted, id_to_owner = _hardened_inputs(edges, receipts, ref_uom)
    rows = []
    for shipment in shipments:
        tolerance = __import__("decimal").Decimal(str(shipment["quantity"])) * __import__("decimal").Decimal("0.02")
        rows.extend(match_counterpart_receipts(
            [shipment], adapted, UOMS,
            date_window_days=window,
            quantity_tolerance=tolerance,
        ))

    detected = {
        str(row["picking_id"]) for row in rows
        if row.get("confirmed") and "loss" in (row.get("issues") or [])
    }
    loss = _metric_counts(detected, truth)
    exact_rows = [row for row in rows if row.get("state") == "exact" and row.get("confirmed")]
    exact_correct = sum(
        1 for row in exact_rows
        if any(id_to_owner.get(str(cid)) == str(row["picking_id"])
               for cid in (row.get("candidate_receipt_ids") or []))
    )
    strict_precision = exact_correct / len(exact_rows) if exact_rows else 1.0
    candidate_hits = sum(
        1 for row in rows
        if any(id_to_owner.get(str(cid)) == str(row["picking_id"])
               for cid in (row.get("candidate_receipt_ids") or []))
    )
    state_counts = {}
    for row in rows:
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
    return {
        "algorithm": "hardened_matcher",
        "policy": "strict",
        "seed": seed, "window": window, **loss,
        "candidate_recall": candidate_hits / len(rows),
        "strict_confirmation_precision": strict_precision,
        "approximate_confirmation_precision": None,
        "strict_confirmations": len(exact_rows),
        "approximate_confirmations": state_counts.get("approximate_unique", 0),
        "ambiguity": state_counts.get("ambiguous", 0),
        "false_positives": loss["fp"],
        "unmatched": state_counts.get("unmatched", 0),
        "candidate": state_counts.get("approximate_unique", 0),
        "uom_conversion_errors": 0,
    }


def _mean_sd(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def _paired_stats(differences: list[float], rng_seed: int) -> dict:
    observed = statistics.mean(differences)
    signs = itertools.product((-1.0, 1.0), repeat=len(differences))
    extreme = sum(
        1 for sign in signs
        if abs(statistics.mean(d * s for d, s in zip(differences, sign))) >= abs(observed) - 1e-15
    )
    p_value = extreme / (2 ** len(differences))
    rng = random.Random(rng_seed)
    boot = []
    n = len(differences)
    for _ in range(10000):
        sample = [differences[rng.randrange(n)] for _ in range(n)]
        boot.append(statistics.mean(sample))
    boot.sort()
    return {
        "mean_difference_deepseek_minus_hardened": observed,
        "paired_sign_flip_p_two_sided": p_value,
        "bootstrap_95_ci": [boot[int(0.025 * len(boot))], boot[min(len(boot)-1, int(0.975 * len(boot)))]],
        "n_paired_seeds": n,
    }


def _git_commit(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def run() -> dict:
    per_seed = []
    dataset_hashes = {}
    for seed in range(SEEDS):
        edges, receipts, truth, meta = generate(seed)
        digest = _dataset_digest(edges, receipts, truth)
        dataset_hashes[str(seed)] = digest
        ref_uom = _catalog_uom(meta)
        for window in WINDOWS:
            per_seed.append(_score_deepseek(
                edges, receipts, truth, ref_uom, seed, window, promote=False
            ))
            per_seed.append(_score_deepseek(
                edges, receipts, truth, ref_uom, seed, window, promote=True
            ))
            per_seed.append(_score_hardened(
                edges, receipts, truth, ref_uom, seed, window
            ))

    algorithms = ("deepseek_corrected", "hardened_matcher")
    policies = ("strict", "promote")
    metrics = (
        "loss_precision", "loss_recall", "candidate_recall",
        "strict_confirmation_precision", "ambiguity", "false_positives",
    )
    aggregate = {}
    paired = {}
    for window in WINDOWS:
        aggregate[str(window)] = {}
        for algorithm in algorithms:
            for policy in (policies if algorithm == "deepseek_corrected" else ("strict",)):
                key = f"{algorithm}:{policy}"
                subset = [r for r in per_seed if r["window"] == window
                          and r["algorithm"] == algorithm and r["policy"] == policy]
                aggregate[str(window)][key] = {}
                for metric in metrics:
                    mean, sd = _mean_sd([float(r[metric]) for r in subset])
                    aggregate[str(window)][key][metric] = {
                        "mean": round(mean, 8), "sd": round(sd, 8),
                    }

        paired[str(window)] = {}
        hardened = {r["seed"]: r for r in per_seed
                    if r["window"] == window and r["algorithm"] == "hardened_matcher"}
        for policy in policies:
            deepseek = {r["seed"]: r for r in per_seed
                        if r["window"] == window and r["algorithm"] == "deepseek_corrected"
                        and r["policy"] == policy}
            paired[str(window)][f"deepseek_{policy}_vs_hardened_strict"] = {}
            for index, metric in enumerate(metrics):
                diffs = [float(deepseek[s][metric]) - float(hardened[s][metric])
                         for s in range(SEEDS)]
                paired[str(window)][f"deepseek_{policy}_vs_hardened_strict"][metric] = _paired_stats(
                    diffs, 20261113 + window * 100 + index + (0 if policy == "strict" else 50)
                )

    payload = {
        "experiment": "paired_uom_corrected_deepseek_vs_hardened_matcher",
        "status": "completed_by_runner",
        "classification": "synthetic_controlled_benchmark_not_operational_validation",
        "parameters": {
            "transfers_per_seed": TRANSFERS, "seeds": SEEDS,
            "relative_quantity_tolerance": REL_TOL,
            "windows_days": list(WINDOWS),
            "uom_pairs": ["unit/dozen", "kg/g"],
            "policies": ["strict", "promote"],
            "cases": ["deleted", "duplicated", "delayed", "unkeyed", "loss/no_loss"],
        },
        "source_revisions": {
            "benchmark_branch": os.environ.get("GITHUB_SHA"),
            "hardened_matcher_commit": _git_commit(HARDENED_ROOT.parents[1]),
        },
        "dataset_sha256_by_seed": dataset_hashes,
        "aggregate_mean_sd_by_window": aggregate,
        "paired_statistics": paired,
        "per_seed": per_seed,
        "metric_definitions": {
            "loss_precision": "TP/(TP+FP) for confirmed loss claims; FP means a loss asserted on a no-loss shipment.",
            "loss_recall": "TP/(TP+FN) over all independently labelled true-loss shipments.",
            "candidate_recall": "fraction of all 240 shipments whose true receipt is present in the algorithm's candidate set.",
            "strict_confirmation_precision": "fraction of exact/strict confirmations whose receipt owner is the same shipment.",
            "ambiguity": "count of ambiguous shipment classifications per seed.",
            "false_positives": "count of false loss claims per seed.",
            "paired_difference": "DeepSeek metric minus hardened matcher metric on the same seed and same generated dataset.",
            "statistics": "exact two-sided paired sign-flip permutation test (4096 sign assignments) and 10,000-resample paired bootstrap 95% percentile interval.",
        },
        "limitations": [
            "Synthetic benchmark only; does not establish operational performance.",
            "The hardened matcher receives an explicit schema adapter: DeepSeek's shared transfer key is represented as source_picking_id, while receiver document IDs remain distinct.",
            "The hardened matcher is always evaluated under its native strict-confirmation policy; DeepSeek strict and promote are both measured against it.",
            "The DeepSeek matching algorithm is unchanged; only its isolated scorer normalizes units by each product's reference category and applies the shared 2% relative loss threshold.",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "paired_uom_benchmark.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Paired UoM-corrected benchmark",
        "",
        "> 240 transfers × 12 seeds; synthetic controlled benchmark, not operational validation.",
        "",
        "Both algorithms received the same generated edges, receipts, labels, seed, temporal window, and 2% relative quantity tolerance. The DeepSeek matcher was not changed. Its isolated scorer now normalizes per product category and preserves source UoM audit values.",
        "",
        "## Strict policy: DeepSeek vs hardened matcher",
        "",
        "| Window | Metric | DeepSeek mean ± SD | Hardened mean ± SD | Δ (DS−Hardened) | paired p | 95% paired CI |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOWS:
        for metric in metrics:
            ds = aggregate[str(window)]["deepseek_corrected:strict"][metric]
            hm = aggregate[str(window)]["hardened_matcher:strict"][metric]
            stat = paired[str(window)]["deepseek_strict_vs_hardened_strict"][metric]
            ci = stat["bootstrap_95_ci"]
            lines.append(
                f"| {window} | {metric} | {ds['mean']:.4f} ± {ds['sd']:.4f} | "
                f"{hm['mean']:.4f} ± {hm['sd']:.4f} | "
                f"{stat['mean_difference_deepseek_minus_hardened']:.4f} | "
                f"{stat['paired_sign_flip_p_two_sided']:.4f} | "
                f"[{ci[0]:.4f}, {ci[1]:.4f}] |"
            )
    lines += [
        "",
        "## Promote policy: DeepSeek promote vs hardened strict",
        "",
        "| Window | Metric | DeepSeek promote mean ± SD | Hardened mean ± SD | Δ (DS−Hardened) | paired p | 95% paired CI |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOWS:
        for metric in metrics:
            ds = aggregate[str(window)]["deepseek_corrected:promote"][metric]
            hm = aggregate[str(window)]["hardened_matcher:strict"][metric]
            stat = paired[str(window)]["deepseek_promote_vs_hardened_strict"][metric]
            ci = stat["bootstrap_95_ci"]
            lines.append(
                f"| {window} | {metric} | {ds['mean']:.4f} ± {ds['sd']:.4f} | "
                f"{hm['mean']:.4f} ± {hm['sd']:.4f} | "
                f"{stat['mean_difference_deepseek_minus_hardened']:.4f} | "
                f"{stat['paired_sign_flip_p_two_sided']:.4f} | "
                f"[{ci[0]:.4f}, {ci[1]:.4f}] |"
            )
    lines += [
        "",
        "## Reproducibility",
        "",
        f"- DeepSeek benchmark source: `{os.environ.get('GITHUB_SHA', 'local')}`.",
        f"- Hardened matcher commit: `{_git_commit(HARDENED_ROOT.parents[1]) or 'unknown'}`.",
        "- The JSON artifact contains all per-seed metrics and SHA-256 hashes of the common generated dataset for each seed.",
        "- Paired inference uses the 12 matched seed-level differences; confidence intervals are percentile bootstrap intervals.",
        "",
        "## Interpretation boundary",
        "",
        "- The corrected scorer fixes UoM normalization and applies the same relative 2% tolerance to loss classification.",
        "- The original DeepSeek matcher and the hardened matcher remain unchanged.",
        "- A lower ambiguity count is not automatically better if it is achieved by unsafe confirmation; read it with confirmation precision and candidate recall.",
        "- No algorithm should be declared superior from one metric or from the aggregate means alone.",
    ]
    (RESULTS / "paired_uom_benchmark_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "status": result["status"],
        "rows": len(result["per_seed"]),
        "dataset_hashes": len(result["dataset_sha256_by_seed"]),
        "windows": len(result["parameters"]["windows_days"]),
        "report": str(RESULTS / "paired_uom_benchmark_report.md"),
    }, indent=2))
