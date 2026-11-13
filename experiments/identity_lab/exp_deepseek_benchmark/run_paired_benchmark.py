"""Paired benchmark of the unchanged DeepSeek matcher and unchanged hardened matcher."""
from __future__ import annotations
import hashlib
import itertools
import json
import os
import random
import statistics
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDENTITY_ROOT = HERE.parent
DEEPSEEK_SOURCE = HERE / "deepseek_source"
sys.path.insert(0, str(DEEPSEEK_SOURCE))
sys.path.insert(0, str(HERE))
from generator import TRANSFERS, SEEDS, WINDOWS, QTY_TOL, generate
from reconcile import match as deepseek_match
from reconcile_benchmark import classify as deepseek_classify

HARDENED_ROOT = Path(os.environ["HARDENED_IDENTITY_ROOT"]).resolve()
sys.path.insert(0, str(HARDENED_ROOT))
from exp_j_erp.reconcile import match_counterpart_receipts

RESULTS = HERE / "results"
BASE_DATE = date(2025, 9, 1)
REL_TOL = float(QTY_TOL)
UOMS = {
    "unit": {"id": "unit", "category_id": "count", "factor": "1", "uom_type": "reference"},
    "dozen": {"id": "dozen", "category_id": "count", "factor": "0.083333333333333333", "uom_type": "bigger"},
    "kg": {"id": "kg", "category_id": "weight", "factor": "1", "uom_type": "reference"},
    "g": {"id": "g", "category_id": "weight", "factor": "1000", "uom_type": "smaller"},
}


def digest_dataset(edges, receipts, truth):
    raw = json.dumps({"edges": edges, "receipts": receipts, "truth": truth},
                     sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def reference_units(meta):
    return {product: value[0] for product, value in meta["ref_uom"].items()}


def hard_inputs(edges, receipts, ref_uom):
    shipments, hard_receipts, id_owner = [], [], {}
    for edge in edges:
        ref = ref_uom[str(edge["product"])]
        shipments.append({
            "picking_id": str(edge["transfer_id"]), "product_id": str(edge["product"]),
            "location_id": str(edge["from_entity"]), "location_dest_id": str(edge["to_entity"]),
            "reference_uom_id": ref,
            "product_uom_category_id": "count" if ref == "unit" else "weight",
            "quantity": str(edge["qty_out"]), "dates": [BASE_DATE.isoformat()],
        })
    for i, receipt in enumerate(receipts):
        duplicate = receipt.get("counterpart_source") == "duplicate"
        receipt_id = f"RCV-DUP-{i:04d}" if duplicate else f"RCV-{i:04d}"
        owner = str(receipt.get("_owner") or "")
        id_owner[receipt_id] = owner
        day = int(receipt.get("day_offset") or 0)
        hard_receipts.append({
            "source_picking_id": str(receipt["counterpart_picking_id"])
                if receipt.get("counterpart_picking_id") else None,
            "counterpart_picking_id": receipt_id,
            "product_id": str(receipt["product_id"]), "location_id": str(receipt["to_entity"]),
            "counterpart_qty": str(receipt["counterpart_qty"]),
            "counterpart_uom_id": str(receipt["counterpart_uom"]),
            "product_uom_category_id": "count" if ref_uom[str(receipt["product_id"])] == "unit" else "weight",
            "counterpart_date": (BASE_DATE + timedelta(days=day)).isoformat(),
            "counterpart_system": "synthetic_independent_receiving",
            "counterpart_source": str(receipt.get("counterpart_source") or "synthetic"),
            "recorded_at": (BASE_DATE + timedelta(days=day)).isoformat() + "T08:00:00",
            "_owner": owner,
        })
    return shipments, hard_receipts, id_owner


def deepseek_candidate_receipts(edge, receipts, ref_uom, window):
    key = str(edge["transfer_id"])
    exact = [r for r in receipts if str(r.get("counterpart_picking_id") or "") == key]
    if exact:
        return exact
    target = ref_uom[str(edge["product"])]
    sent = float(edge["qty_out"])
    found = []
    for receipt in receipts:
        if str(receipt.get("product_id")) != str(edge.get("product")):
            continue
        if str(receipt.get("from_entity")) != str(edge.get("from_entity")):
            continue
        if str(receipt.get("to_entity")) != str(edge.get("to_entity")):
            continue
        if abs(int(receipt.get("day_offset", 0))) > window:
            continue
        qty, _ = __import__("uom").convert(
            float(receipt["counterpart_qty"]), str(receipt["counterpart_uom"]), target
        )
        if qty is not None and sent and abs(qty - sent) / abs(sent) <= REL_TOL:
            found.append(receipt)
    return found


def loss_counts(predicted, truth):
    actual = {str(t["transfer_id"]) for t in truth if t["has_loss"]}
    tp, fp, fn = len(predicted & actual), len(predicted - actual), len(actual - predicted)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "loss_precision": tp / (tp + fp) if tp + fp else 1.0,
        "loss_recall": tp / (tp + fn) if tp + fn else 1.0,
    }


def _deepseek_common_metrics(matches, edges, receipts, ref_uom, window):
    strict = [r for r in matches if r["state"] == "confirmed"]
    strict_correct = sum(
        1 for r in strict
        if str((r.get("receipt") or {}).get("_owner") or "") == str(r["edge"])
    )
    approximate = [r for r in matches if r["state"] == "confirmed_approx"]
    approximate_correct = sum(
        1 for r in approximate
        if str((r.get("receipt") or {}).get("_owner") or "") == str(r["edge"])
    )
    candidate_hits = sum(
        1 for edge in edges
        if any(str(r.get("_owner") or "") == str(edge["transfer_id"])
               for r in deepseek_candidate_receipts(edge, receipts, ref_uom, window))
    )
    return {
        "candidate_recall": candidate_hits / len(edges),
        "strict_confirmation_precision": strict_correct / len(strict) if strict else 1.0,
        "approximate_confirmation_precision": approximate_correct / len(approximate) if approximate else None,
        "strict_confirmations": len(strict),
        "approximate_confirmations": len(approximate),
    }


def score_deepseek(edges, receipts, truth, ref_uom, seed, window, promote):
    matches = deepseek_match(edges, receipts, date_window=window, qty_tolerance=REL_TOL,
                             ref_uom=ref_uom, promote_unique=promote)
    summary = deepseek_classify(matches, edges, ref_uom=ref_uom)
    detected = {str(x["edge"]) for x in summary["confirmed_loss"]}
    loss = loss_counts(detected, truth)
    exact = [r for r in matches if r["state"] == "confirmed"]
    exact_ok = sum(1 for r in exact
                   if str((r.get("receipt") or {}).get("_owner") or "") == str(r["edge"]))
    approximate = [r for r in matches if r["state"] == "confirmed_approx"]
    approximate_ok = sum(1 for r in approximate
                         if str((r.get("receipt") or {}).get("_owner") or "") == str(r["edge"]))
    candidate_hits = sum(
        1 for edge in edges
        if any(str(r.get("_owner") or "") == str(edge["transfer_id"])
               for r in deepseek_candidate_receipts(edge, receipts, ref_uom, window))
    )
    return {
        "algorithm": "deepseek_corrected", "policy": "promote" if promote else "strict",
        "seed": seed, "window": window, **loss,
        "candidate_recall": candidate_hits / len(edges),
        "strict_confirmation_precision": exact_ok / len(exact) if exact else 1.0,
        "approximate_confirmation_precision": approximate_ok / len(approximate) if approximate else None,
        "strict_confirmations": len(exact), "approximate_confirmations": len(approximate),
        "ambiguity": summary["ambiguous"], "false_positives": loss["fp"],
        "unmatched": summary["unmatched"], "candidate": summary["candidate"],
        "uom_audit_rows": len(summary["uom_audit"]),
    }


def legacy_uom_classify(edge_results, edges):
    """Counterfactual reproducing the old scorer's hardcoded unit reference."""
    from uom import convert
    by_edge = {str(e["transfer_id"]): e for e in edges}
    out = {"confirmed_loss": [], "uom_rejections": 0}
    for result in edge_results:
        if result["state"] not in ("confirmed", "confirmed_approx"):
            continue
        edge = by_edge[str(result["edge"])]
        receipt = result["receipt"]
        try:
            qty, reason = convert(
                float(receipt.get("counterpart_qty")),
                str(receipt.get("counterpart_uom") or "unit"), "unit"
            )
        except (TypeError, ValueError):
            qty, reason = None, "quantity_invalid"
        if qty is None:
            out["uom_rejections"] += 1
            continue
        gap = float(edge["qty_out"]) - qty
        if gap > 0.5:
            out["confirmed_loss"].append({"edge": str(result["edge"]), "missing": gap})
    return out


def score_deepseek_legacy_uom(edges, receipts, truth, ref_uom, seed, window, promote):
    matches = deepseek_match(edges, receipts, date_window=window, qty_tolerance=REL_TOL,
                             ref_uom=ref_uom, promote_unique=promote)
    summary = legacy_uom_classify(matches, edges)
    detected = {str(x["edge"]) for x in summary["confirmed_loss"]}
    common = _deepseek_common_metrics(matches, edges, receipts, ref_uom, window)
    loss = loss_counts(detected, truth)
    return {
        "algorithm": "deepseek_legacy_uom_control",
        "policy": "promote" if promote else "strict",
        "seed": seed, "window": window, **loss, **common,
        "ambiguity": summary["uom_rejections"] + sum(1 for r in matches if r["state"] == "ambiguous"),
        "false_positives": loss["fp"],
        "unmatched": sum(1 for r in matches if r["state"] == "unmatched"),
        "candidate": sum(1 for r in matches if r["state"] == "candidate"),
        "uom_audit_rows": summary["uom_rejections"],
    }


def score_hardened(edges, receipts, truth, ref_uom, seed, window):
    shipments, hard_receipts, id_owner = hard_inputs(edges, receipts, ref_uom)
    rows = []
    for shipment in shipments:
        tolerance = Decimal(str(shipment["quantity"])) * Decimal("0.02")
        rows.extend(match_counterpart_receipts(
            [shipment], hard_receipts, UOMS,
            date_window_days=window, quantity_tolerance=tolerance,
        ))
    detected = {
        str(r["picking_id"]) for r in rows
        if r.get("confirmed") and Decimal(str(r.get("delta", "0"))) > Decimal("0.5")
    }
    loss = loss_counts(detected, truth)
    exact = [r for r in rows if r.get("state") == "exact" and r.get("confirmed")]
    exact_ok = sum(
        1 for r in exact
        if any(id_owner.get(str(cid)) == str(r["picking_id"])
               for cid in (r.get("candidate_receipt_ids") or []))
    )
    candidate_hits = sum(
        1 for r in rows
        if any(id_owner.get(str(cid)) == str(r["picking_id"])
               for cid in (r.get("candidate_receipt_ids") or []))
    )
    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {
        "algorithm": "hardened_matcher", "policy": "strict",
        "seed": seed, "window": window, **loss,
        "candidate_recall": candidate_hits / len(rows),
        "strict_confirmation_precision": exact_ok / len(exact) if exact else 1.0,
        "approximate_confirmation_precision": None,
        "strict_confirmations": len(exact),
        "approximate_confirmations": counts.get("approximate_unique", 0),
        "ambiguity": counts.get("ambiguous", 0), "false_positives": loss["fp"],
        "unmatched": counts.get("unmatched", 0),
        "candidate": counts.get("approximate_unique", 0),
        "uom_audit_rows": 0,
    }


def mean_sd(values):
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def paired_stats(differences, seed):
    observed = statistics.mean(differences)
    extreme = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        null_mean = statistics.mean(d * sign for d, sign in zip(differences, signs))
        if abs(null_mean) >= abs(observed) - 1e-15:
            extreme += 1
    rng = random.Random(seed)
    boot = sorted(
        statistics.mean(differences[rng.randrange(len(differences))]
                        for _ in range(len(differences)))
        for _ in range(10000)
    )
    return {
        "mean_difference_first_minus_second": observed,
        "paired_sign_flip_p_two_sided": extreme / (2 ** len(differences)),
        "bootstrap_95_ci": [boot[250], boot[9749]],
        "n_paired_seeds": len(differences),
    }


def source_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    per_seed, hashes = [], {}
    for seed in range(SEEDS):
        edges, receipts, truth, meta = generate(seed)
        hashes[str(seed)] = digest_dataset(edges, receipts, truth)
        ref_uom = reference_units(meta)
        for window in WINDOWS:
            per_seed.append(score_deepseek(edges, receipts, truth, ref_uom, seed, window, False))
            per_seed.append(score_deepseek(edges, receipts, truth, ref_uom, seed, window, True))
            per_seed.append(score_deepseek_legacy_uom(edges, receipts, truth, ref_uom, seed, window, False))
            per_seed.append(score_deepseek_legacy_uom(edges, receipts, truth, ref_uom, seed, window, True))
            per_seed.append(score_hardened(edges, receipts, truth, ref_uom, seed, window))

    metrics = ("loss_precision", "loss_recall", "candidate_recall",
               "strict_confirmation_precision", "ambiguity", "false_positives")
    aggregate, paired = {}, {}
    for window in WINDOWS:
        aggregate[str(window)] = {}
        for alg, policies in (("deepseek_corrected", ("strict", "promote")),
                              ("deepseek_legacy_uom_control", ("strict", "promote")),
                              ("hardened_matcher", ("strict",))):
            for policy in policies:
                key = f"{alg}:{policy}"
                rows = [r for r in per_seed if r["window"] == window
                        and r["algorithm"] == alg and r["policy"] == policy]
                aggregate[str(window)][key] = {}
                for metric in metrics:
                    avg, sd = mean_sd([float(r[metric]) for r in rows])
                    aggregate[str(window)][key][metric] = {"mean": avg, "sd": sd}
        paired[str(window)] = {}
        hardened = {r["seed"]: r for r in per_seed if r["window"] == window
                    and r["algorithm"] == "hardened_matcher"}
        for policy in ("strict", "promote"):
            deepseek = {r["seed"]: r for r in per_seed if r["window"] == window
                        and r["algorithm"] == "deepseek_corrected" and r["policy"] == policy}
            pair_key = f"deepseek_{policy}_vs_hardened_strict"
            paired[str(window)][pair_key] = {}
            for index, metric in enumerate(metrics):
                differences = [float(deepseek[s][metric]) - float(hardened[s][metric])
                               for s in range(SEEDS)]
                paired[str(window)][pair_key][metric] = paired_stats(
                    differences, 20261113 + window * 100 + index + (0 if policy == "strict" else 50)
                )
        corrected_strict = {r["seed"]: r for r in per_seed if r["window"] == window
                            and r["algorithm"] == "deepseek_corrected" and r["policy"] == "strict"}
        legacy = {r["seed"]: r for r in per_seed if r["window"] == window
                  and r["algorithm"] == "deepseek_legacy_uom_control" and r["policy"] == "strict"}
        paired[str(window)]["uom_fix_vs_legacy_uom"] = {}
        for index, metric in enumerate(metrics):
            differences = [float(corrected_strict[s][metric]) - float(legacy[s][metric])
                           for s in range(SEEDS)]
            paired[str(window)]["uom_fix_vs_legacy_uom"][metric] = paired_stats(
                differences, 20261113 + window * 100 + index + 50
            )

    hard_commit = subprocess.check_output(
        ["git", "-C", str(HARDENED_ROOT.parents[1]), "rev-parse", "HEAD"], text=True
    ).strip()
    payload = {
        "experiment": "paired_uom_corrected_deepseek_vs_hardened_matcher",
        "classification": "synthetic_controlled_benchmark_not_operational_validation",
        "parameters": {
            "transfers_per_seed": TRANSFERS, "seeds": SEEDS, "relative_quantity_tolerance_for_candidate_matching": REL_TOL,
            "loss_gap_threshold_reference_units": 0.5,
            "windows_days": list(WINDOWS), "uom_pairs": ["unit/dozen", "kg/g"],
            "policies": ["strict", "promote"],
            "faults": ["deleted", "duplicated", "delayed", "unkeyed", "loss", "no_loss"],
        },
        "source_revisions": {
            "benchmark_commit": os.environ.get("GITHUB_SHA"),
            "deepseek_reconcile_sha256": source_sha(DEEPSEEK_SOURCE / "reconcile.py"),
            "deepseek_uom_sha256": source_sha(DEEPSEEK_SOURCE / "uom.py"),
            "hardened_matcher_commit": hard_commit,
        },
        "dataset_sha256_by_seed": hashes,
        "aggregate_mean_sd_by_window": aggregate,
        "paired_statistics": paired,
        "per_seed": per_seed,
        "metric_definitions": {
            "loss_precision": "TP/(TP+FP) for confirmed loss claims.",
            "loss_recall": "TP/(TP+FN) over independently labelled true-loss shipments.",
            "candidate_recall": "fraction of all 240 shipments whose true receipt is present in its candidate set.",
            "strict_confirmation_precision": "fraction of exact confirmations whose receipt owner is the same shipment.",
            "ambiguity": "number of ambiguous classifications per seed.",
            "false_positives": "number of false loss claims per seed.",
            "paired_difference": "first named scoring/matcher variant minus second on the same seed and byte-identical generated dataset.",
            "statistics": "exact two-sided paired sign-flip permutation test (4096 assignments) and 10,000-resample paired bootstrap 95% percentile CI.",
            "uom_fix_control": "legacy scorer keeps the original fixed unit reference; corrected scorer changes only the product-specific UoM normalization. Both use the original >0.5 loss threshold.",
        },
        "limitations": [
            "Synthetic benchmark only; it does not establish operational accuracy or prevalence.",
            "The hardened matcher receives an explicit schema adapter: the shared transfer key becomes source_picking_id while receiver document IDs remain distinct.",
            "The hardened matcher is evaluated only under its native strict-confirmation policy; DeepSeek strict and promote are each compared against it.",
            "DeepSeek matching code is byte-for-byte copied from the baseline branch; only the isolated scorer's UoM normalization is corrected. Its original >0.5 loss threshold is preserved. The legacy-UoM control retains the old fixed unit target.",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "paired_uom_benchmark.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Paired UoM-corrected benchmark",
        "",
        "> 240 transfers × 12 seeds. Synthetic controlled benchmark; not operational validation.",
        "",
        "Both matchers receive identical generated records, labels, seeds, windows and 2% relative candidate-matching tolerance. The DeepSeek matcher is unchanged. Its isolated scorer changes only product-specific UoM normalization; the original >0.5 reference-unit loss threshold is retained. The hardened output is evaluated with that same loss threshold. The legacy-UoM control replays the old fixed-unit scorer on identical matcher outputs.",
        "",
        "## UoM correction effect: corrected scorer vs legacy fixed-unit scorer",
        "",
        "| Window | Legacy loss recall | Corrected loss recall | Improvement | paired p | 95% paired CI |",
        "|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {window} | "
            f"{aggregate[str(window)]['deepseek_legacy_uom_control:strict']['loss_recall']['mean']:.4f} | "
            f"{aggregate[str(window)]['deepseek_corrected:strict']['loss_recall']['mean']:.4f} | "
            f"{paired[str(window)]['uom_fix_vs_legacy_uom']['loss_recall']['mean_difference_first_minus_second']:.4f} | "
            f"{paired[str(window)]['uom_fix_vs_legacy_uom']['loss_recall']['paired_sign_flip_p_two_sided']:.4f} | "
            f"[{paired[str(window)]['uom_fix_vs_legacy_uom']['loss_recall']['bootstrap_95_ci'][0]:.4f}, "
            f"{paired[str(window)]['uom_fix_vs_legacy_uom']['loss_recall']['bootstrap_95_ci'][1]:.4f}] |"
            for window in WINDOWS
        ],
        "",
        "## DeepSeek strict vs hardened strict",
        "",
        "| Window | Metric | DeepSeek mean ± SD | Hardened mean ± SD | Δ DS−Hardened | paired p | 95% paired CI |",
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
                f"{stat['mean_difference_first_minus_second']:.4f} | "
                f"{stat['paired_sign_flip_p_two_sided']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] |"
            )
    lines += [
        "",
        "## DeepSeek promote vs hardened strict",
        "",
        "| Window | Metric | DeepSeek promote mean ± SD | Hardened mean ± SD | Δ DS−Hardened | paired p | 95% paired CI |",
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
                f"{stat['mean_difference_first_minus_second']:.4f} | "
                f"{stat['paired_sign_flip_p_two_sided']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] |"
            )
    lines += [
        "",
        "## DeepSeek promotion diagnostics",
        "",
        "| Window | Unique promotions mean ± SD | Approximate confirmation precision | False loss claims mean |",
        "|---:|---:|---:|---:|",
        *[
            (
                lambda rows, window: (
                    f"| {window} | "
                    f"{statistics.mean(r['approximate_confirmations'] for r in rows):.3f} ± "
                    f"{(statistics.stdev(r['approximate_confirmations'] for r in rows) if len(rows)>1 else 0.0):.3f} | "
                    f"{statistics.mean(r['approximate_confirmation_precision'] for r in rows if r['approximate_confirmation_precision'] is not None):.4f} | "
                    f"{statistics.mean(r['false_positives'] for r in rows):.3f} |"
                )
            )(
                [r for r in per_seed if r["algorithm"] == "deepseek_corrected"
                 and r["policy"] == "promote" and r["window"] == window],
                window
            )
            for window in WINDOWS
        ],
        "",
        "## Reproducibility",
        "",
        f"- Benchmark commit: `{os.environ.get('GITHUB_SHA', 'local')}`.",
        f"- Hardened matcher commit: `{hard_commit}`.",
        "- JSON includes all per-seed results, the exact data SHA-256 for each seed, and source-code hashes.",
        "- Lower ambiguity is not automatically better; interpret it with candidate recall and strict confirmation precision.",
    ]
    (RESULTS / "paired_uom_benchmark_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "status": "completed", "per_seed_rows": len(result["per_seed"]),
        "seed_dataset_hashes": len(result["dataset_sha256_by_seed"]),
        "windows": len(result["parameters"]["windows_days"]),
        "report": str(RESULTS / "paired_uom_benchmark_report.md"),
    }, indent=2))
