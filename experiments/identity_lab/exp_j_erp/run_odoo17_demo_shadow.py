"""Run A/B/C against resolved Odoo 17 demo stock moves.

The movement rows are extracted from Odoo's official stock_demo2.xml seed.
Counterpart receipts are a separate, explicitly synthetic test overlay.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .shadow_mode import run_shadow, write_run

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "odoo17_demo_stock_moves.json"
OVERLAY = HERE / "odoo17_demo_test_receipt_overlay.json"


def load_inputs() -> tuple[dict, dict]:
    bundle = json.loads(SOURCE.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    return bundle, overlay


def execute(output_root: Path | None = None) -> dict:
    bundle, overlay = load_inputs()
    baseline = run_shadow(bundle)
    scenario_bundle = {
        **bundle,
        "export_metadata": {
            **bundle["export_metadata"],
            "test_overlay": overlay["overlay_classification"],
            "test_overlay_is_source_data": False,
        },
        "receipts": overlay["receipts"],
    }
    scenario = run_shadow(scenario_bundle)

    expected = {"A": 3, "B": 1, "C": 3}
    for engine in ("A", "B", "C"):
        base_summary = baseline["engine_summaries"][engine]
        test_summary = scenario["engine_summaries"][engine]
        if base_summary["shipments_scored"] != 6 or base_summary["unmatched"] != 6:
            raise AssertionError(f"{engine}:baseline_must_score_six_unmatched_moves")
        if base_summary["confirmed"] or base_summary["loss_claims"]:
            raise AssertionError(f"{engine}:baseline_claimed_without_receipt_rows")
        if test_summary["shipments_scored"] != 6 or test_summary["confirmed"] != 6:
            raise AssertionError(f"{engine}:controlled_overlay_must_confirm_six_exact_links")
        if test_summary["loss_claims"] != expected[engine]:
            raise AssertionError(
                f"{engine}:unexpected_loss_count:{test_summary['loss_claims']}"
            )

    if scenario["pairwise_state_disagreements"] != {
        "A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0
    }:
        raise AssertionError("engines_disagree_on_semantic_confirmation_state")
    if scenario["disagreement_count"] != 2:
        raise AssertionError(
            f"expected_two_loss_threshold_disagreements:{scenario['disagreement_count']}"
        )

    if output_root is None:
        output_root = Path(os.environ.get("RUNNER_TEMP", ".")) / "odoo17-demo-stock-shadow"
    output_root.mkdir(parents=True, exist_ok=True)
    baseline_dir = write_run(baseline, output_root / "baseline")
    scenario_dir = write_run(scenario, output_root / "controlled-overlay")

    summary = {
        "classification": "Odoo 17 demo-movement integration run; not operational production data",
        "source": bundle["export_metadata"],
        "movement_count": len(bundle["moves"]),
        "partial_movement_count": baseline["movement_stats"]["partial_movements"],
        "baseline_without_receipts": {
            "confirmed": {e: baseline["engine_summaries"][e]["confirmed"] for e in ("A", "B", "C")},
            "loss_claims": {e: baseline["engine_summaries"][e]["loss_claims"] for e in ("A", "B", "C")},
            "unmatched": {e: baseline["engine_summaries"][e]["unmatched"] for e in ("A", "B", "C")},
        },
        "controlled_overlay": {
            "classification": overlay["overlay_classification"],
            "receipt_rows": len(overlay["receipts"]),
            "confirmed": {e: scenario["engine_summaries"][e]["confirmed"] for e in ("A", "B", "C")},
            "loss_claims": {e: scenario["engine_summaries"][e]["loss_claims"] for e in ("A", "B", "C")},
            "pairwise_semantic_state_disagreements": scenario["pairwise_state_disagreements"],
            "raw_state_label_differences": scenario["pairwise_raw_state_label_differences"],
            "disagreement_count": scenario["disagreement_count"],
        },
        "threshold_observation": (
            "B produces fewer loss claims because its 2% candidate tolerance is also used "
            "as the loss threshold; A and C use 0.5 reference units."
        ),
        "baseline_report_directory": str(baseline_dir),
        "overlay_report_directory": str(scenario_dir),
        "writes_to_odoo": False,
        "source_records_modified": False,
        "synthetic_receipts_used_only_in_controlled_overlay": True,
    }
    (output_root / "odoo17_demo_abc_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Odoo 17 demo movement — A/B/C shadow experiment",
        "",
        "## Dataset",
        "",
        "- Source: Odoo 17 official stock demo fixture `stock_demo2.xml`.",
        "- Completed movement rows resolved: 6.",
        "- Partial executions: 4.",
        "- Date expressions frozen at 2026-11-14 for deterministic replay.",
        "- No Odoo server/database connection or writes.",
        "",
        "## Baseline: source movement rows without receipt overlay",
        "",
        "| Engine | Scored | Confirmed | Loss claims | Unmatched |",
        "|---|---:|---:|---:|---:|",
    ]
    for e in ("A", "B", "C"):
        s = baseline["engine_summaries"][e]
        lines.append(f"| {e} | {s['shipments_scored']} | {s['confirmed']} | {s['loss_claims']} | {s['unmatched']} |")
    lines += [
        "",
        "All engines abstain from confirmation and loss classification when no receipt rows are supplied.",
        "",
        "## Controlled comparison: synthetic counterpart overlay",
        "",
        "The six receipt rows below are generated test inputs, not records contained in the Odoo source fixture.",
        "",
        "| Engine | Confirmed | Loss claims |",
        "|---|---:|---:|",
    ]
    for e in ("A", "B", "C"):
        s = scenario["engine_summaries"][e]
        lines.append(f"| {e} | {s['confirmed']} | {s['loss_claims']} |")
    lines += [
        "",
        "Semantic confirmation-state disagreements: 0.",
        "Loss-claim disagreements: 2 shipments.",
        "",
        "## Finding",
        "",
        "B uses the same 2% per-shipment quantity tolerance for candidate matching and loss classification. "
        "A and C use a 0.5 reference-unit loss threshold. The overlay therefore yields A=3, B=1, C=3 loss claims. "
        "This is a concrete configuration/implementation difference, not proof that A or C is more accurate.",
        "",
        "The raw state labels differ by engine (for example `confirmed`, `exact`, `confirmed_exact`). "
        "The comparison now canonicalizes these to the same semantic state before counting state disagreements.",
        "",
        "## Evidence boundary",
        "",
        "The Odoo movement rows are parsed from Odoo's published demo seed. The controlled receipt overlay is synthetic. "
        "This run validates field ingestion, aggregation, exact-link handling, threshold behavior, and delay handling; "
        "it does not validate real-world receiving accuracy.",
    ]
    (output_root / "odoo17_demo_abc_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return summary


def main() -> None:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
