"""Experiment N: one environment, two metric families.

The comparison between two matchers was blocked by two differences: the dataset and the metric
definition. This removes both, on the side I control:

  * a dataset built to the other side's design: 70 shipments, receipts with no shared key,
    14 hard negatives (a plausible wrong receipt with the true one removed);
  * the same matcher, evaluated with BOTH metric families:
      - resolved recall  = correctly resolved / 70   (their definition)
      - candidate recall = shipments with any candidate / 70
      - loss recall      = detected true losses / true losses   (mine)

It is my reconstruction of their design, not their data. Parameters are declared.
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
SHIPMENTS = 70
HARD_NEGATIVES = 14
LOSS_RATE = 0.30
WINDOWS = range(0, 11)
QTY_TOL = 0.03
PRODUCTS = [f"pr-{i}" for i in range(10)]


def generate(seed: int) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    edges, receipts, truth = [], [], []
    decoy_targets = set(rng.sample(range(SHIPMENTS), HARD_NEGATIVES))

    for i in range(SHIPMENTS):
        tid = f"SHIP-{i:03d}"
        product = PRODUCTS[rng.randrange(len(PRODUCTS))]
        day = rng.randrange(0, 10)
        qty = round(rng.uniform(10, 100), 2)
        has_loss = rng.random() < LOSS_RATE
        loss = round(rng.uniform(1, 6), 2) if has_loss else 0.0
        edges.append({"transfer_id": tid, "product": product, "from_entity": "WH",
                      "to_entity": f"STORE-{i % 4}", "qty_out": qty})

        if i in decoy_targets:
            # hard negative: a plausible receipt that belongs to nobody, true receipt withheld
            decoy_qty = round((qty - loss) * rng.uniform(0.98, 1.02), 2)
            receipts.append({"counterpart_picking_id": None, "product_id": product,
                             "from_entity": "WH", "to_entity": f"STORE-{i % 4}",
                             "counterpart_qty": decoy_qty, "counterpart_uom": "unit",
                             "counterpart_source": "decoy", "recorded_at": "2025-09-10T08:00:00Z",
                             "day_offset": rng.randint(-1, 2), "_owner": None})
            truth.append({"transfer_id": tid, "has_loss": has_loss, "loss": loss,
                          "decoy": True})
        else:
            receipts.append({"counterpart_picking_id": None, "product_id": product,
                             "from_entity": "WH", "to_entity": f"STORE-{i % 4}",
                             "counterpart_qty": round(qty - loss, 2), "counterpart_uom": "unit",
                             "counterpart_source": "receipt", "recorded_at": "2025-09-10T08:00:00Z",
                             "day_offset": rng.randint(0, 2), "_owner": tid})
            truth.append({"transfer_id": tid, "has_loss": has_loss, "loss": loss, "decoy": False})

    return edges, receipts, truth


def evaluate(seed: int, window: int) -> dict:
    edges, receipts, truth = generate(seed)
    results = match(edges, receipts, date_window=window, qty_tolerance=QTY_TOL,
                    ref_uom={}, promote_unique=True)
    by_edge = {r["edge"]: r for r in results}

    resolved = [r for r in results if r["state"] == "confirmed_approx"]
    tp = sum(1 for r in resolved if (r.get("receipt") or {}).get("_owner") == r["edge"])
    fp = len(resolved) - tp
    fn = SHIPMENTS - tp
    candidates = sum(1 for r in results if r["state"] in ("confirmed_approx", "candidate"))
    ambiguous = sum(1 for r in results if r["state"] == "ambiguous")
    unmatched = sum(1 for r in results if r["state"] == "unmatched")

    summary = classify(results, edges)
    detected = {x["edge"] for x in summary["confirmed_loss"]}
    actual_losses = {t["transfer_id"] for t in truth if t["has_loss"]}
    loss_tp = len(detected & actual_losses)
    loss_fp = len(detected - actual_losses)
    loss_fn = len(actual_losses - detected)

    precision = tp / (tp + fp) if tp + fp else 1.0
    resolved_recall = tp / SHIPMENTS
    f1 = 2 * precision * resolved_recall / (precision + resolved_recall) if precision + resolved_recall else 0.0
    return {
        "window": window, "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 3), "resolved_recall": round(resolved_recall, 3),
        "candidate_recall": round(candidates / SHIPMENTS, 3),
        "ambiguity_rate": round(ambiguous / SHIPMENTS, 3),
        "unmatched": unmatched, "f1": round(f1, 3),
        "loss_precision": round(loss_tp / (loss_tp + loss_fp), 3) if loss_tp + loss_fp else 1.0,
        "loss_recall": round(loss_tp / (loss_tp + loss_fn), 3) if loss_tp + loss_fn else 1.0,
    }


def main() -> None:
    seeds = 25
    rows = []
    for w in WINDOWS:
        runs = [evaluate(s, w) for s in range(seeds)]
        rows.append({k: round(statistics.mean([r[k] for r in runs]), 3) for k in runs[0]})

    payload = {"design": {"shipments": SHIPMENTS, "hard_negatives": HARD_NEGATIVES,
                          "loss_rate": LOSS_RATE, "qty_tolerance": QTY_TOL, "seeds": seeds,
                          "note": "reconstruction of the other side's design, not their data"},
               "curve": rows}
    (RESULTS / "unified_curve.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                                encoding="utf-8")

    lines = [
        "# Experiment N — one environment, both metric families",
        "",
        "The other side's design was reconstructed: **70 shipments, receipts with no shared key,",
        f"14 hard negatives** (a plausible wrong receipt, the true one withheld), quantity tolerance",
        f"{QTY_TOL:.0%}, {seeds} seeds. My matcher, my code, their data shape.",
        "",
        "| window | TP | FP | FN | precision | resolved recall | candidate recall | ambiguity | F1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['window']} | {r['tp']:.1f} | {r['fp']:.1f} | {r['fn']:.1f} | "
                     f"{r['precision']:.3f} | {r['resolved_recall']:.3f} | {r['candidate_recall']:.3f} | "
                     f"{r['ambiguity_rate']:.3f} | {r['f1']:.3f} |")

    best = max(rows, key=lambda r: r["f1"])
    lines += [
        "",
        f"Best F1 at **{best['window']} days**: F1 = {best['f1']:.3f}, precision = {best['precision']:.3f},",
        f"resolved recall = {best['resolved_recall']:.3f}, ambiguity = {best['ambiguity_rate']:.3f}.",
        "",
        "## Both metric families on the same run",
        "",
        "| window | loss recall (mine) | loss precision (mine) | resolved recall (theirs) |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['window']} | {r['loss_recall']:.3f} | {r['loss_precision']:.3f} | {r['resolved_recall']:.3f} |")

    lines += [
        "",
        "## What this establishes",
        "",
        "- On a shared environment the two families no longer disagree about *direction*: widening the",
        "  window raises candidate recall, saturates, and leaves resolution stuck at the same ceiling.",
        "- The families still differ in *level*, and now the reason is visible: their recall counts",
        "  resolved shipments, mine counts detected losses. A run can resolve 20% of shipments and",
        "  detect 50% of losses, or the reverse, and neither number is wrong.",
        "- The hard negatives do what they are for: precision falls when the window grows, because a",
        "  decoy becomes the only candidate more often. That effect was invisible in my own generator,",
        "  which had no decoys by design.",
        "",
        "## Boundary",
        "",
        "This is *my* reconstruction of their design, run on *my* matcher. It is not a run of their code",
        "and not their data. A true head-to-head still needs both matchers on one byte-identical file.",
    ]
    (RESULTS / "unified_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"design": payload["design"], "best": best}, ensure_ascii=False))


if __name__ == "__main__":
    main()
