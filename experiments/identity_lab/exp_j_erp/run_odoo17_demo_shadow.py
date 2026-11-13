"""Run A/B/C on Odoo 17 demo movement fields with explicit test overlays.

Source movement fields are parsed from Odoo's official stock_demo2.xml.
That seed writes line quantities but does not set picked=True; Odoo 17's
stock.move._action_done therefore does not prove these rows became done.
A clearly separated test-only completion overlay enables the completed-move
path. A second synthetic overlay supplies counterpart receipts for comparison.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .shadow_mode import run_shadow, write_run

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "odoo17_demo_stock_moves.json"
COMPLETION = HERE / "odoo17_demo_test_completion_overlay.json"
RECEIPTS = HERE / "odoo17_demo_test_receipt_overlay.json"


def load_inputs() -> tuple[dict, dict, dict]:
    bundle = json.loads(SOURCE.read_text(encoding="utf-8"))
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    receipt_overlay = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    return bundle, completion, receipt_overlay


def completed_test_bundle(bundle: dict, completion: dict) -> dict:
    if completion.get("not_source_data") is not True:
        raise AssertionError("completion_overlay_must_be_labeled_test_only")
    overrides = {row["picking_id"]: row for row in completion["overrides"]}
    moves = []
    for source_move in bundle["moves"]:
        override = overrides.get(source_move["picking_id"])
        if not override:
            raise AssertionError("missing_completion_override:" + source_move["picking_id"])
        moves.append({
            **source_move,
            "state": override["state"],
            "picked": override["picked"],
        })
    if len(overrides) != len(moves):
        raise AssertionError("completion_overlay_contains_unknown_or_duplicate_picking")
    return {
        **bundle,
        "moves": moves,
        "export_metadata": {
            **bundle["export_metadata"],
            "test_completion_overlay": completion["overlay_classification"],
            "test_completion_overlay_is_source_data": False,
        },
    }


def execute(output_root: Path | None = None) -> dict:
    bundle, completion, receipt_overlay = load_inputs()
    raw_source_report = run_shadow(bundle)
    test_moves = completed_test_bundle(bundle, completion)
    baseline = run_shadow(test_moves)
    scenario_bundle = {
        **test_moves,
        "export_metadata": {
            **test_moves["export_metadata"],
            "test_receipt_overlay": receipt_overlay["overlay_classification"],
            "test_receipt_overlay_is_source_data": False,
        },
        "receipts": receipt_overlay["receipts"],
    }
    scenario = run_shadow(scenario_bundle)

    expected_losses = {"A": 2, "B": 2, "C": 2}
    for engine in ("A", "B", "C"):
        raw_summary = raw_source_report["engine_summaries"][engine]
        base_summary = baseline["engine_summaries"][engine]
        test_summary = scenario["engine_summaries"][engine]
        if raw_summary["shipments_scored"] != 0:
            raise AssertionError(f"{engine}:source_rows_must_not_be_treated_as_done")
        if base_summary["shipments_scored"] != 4 or base_summary["unmatched"] != 4:
            raise AssertionError(f"{engine}:completed_test_baseline_must_score_four_unmatched_moves")
        if base_summary["confirmed"] or base_summary["loss_claims"]:
            raise AssertionError(f"{engine}:baseline_claimed_without_receipt_rows")
        if test_summary["shipments_scored"] != 4 or test_summary["confirmed"] != 4:
            raise AssertionError(f"{engine}:controlled_overlay_must_confirm_four_exact_links")
        if test_summary["loss_claims"] != expected_losses[engine]:
            raise AssertionError(
                f"{engine}:unexpected_loss_count:{test_summary['loss_claims']}"
            )

    if scenario["pairwise_state_disagreements"] != {
        "A_vs_B": 0, "A_vs_C": 0, "B_vs_C": 0
    }:
        raise AssertionError("engines_disagree_on_semantic_confirmation_state")
    if scenario["disagreement_count"] != 0:
        raise AssertionError(
            f"expected_no_semantic_or_loss_disagreements_after_threshold_alignment:"
            f"{scenario['disagreement_count']}"
        )

    if output_root is None:
        output_root = Path(os.environ.get("RUNNER_TEMP", ".")) / "odoo17-demo-stock-shadow"
    output_root.mkdir(parents=True, exist_ok=True)
    raw_dir = write_run(raw_source_report, output_root / "raw-source")
    baseline_dir = write_run(baseline, output_root / "completed-test-baseline")
    scenario_dir = write_run(scenario, output_root / "controlled-receipts")

    summary = {
        "classification": "Odoo 17 source movement fields plus explicitly synthetic test overlays",
        "source": bundle["export_metadata"],
        "source_movement_count": len(bundle["moves"]),
        "source_state": {
            "states": sorted({m["state"] for m in bundle["moves"]}),
            "picked_flags": sorted({m["picked"] for m in bundle["moves"]}),
            "engine_scored_movements": {
                e: raw_source_report["engine_summaries"][e]["shipments_scored"]
                for e in ("A", "B", "C")
            },
        },
        "completion_overlay": {
            "classification": completion["overlay_classification"],
            "is_source_data": False,
            "movement_count": len(completion["overrides"]),
            "test_only_done_count": 4,
        },
        "baseline_without_receipts": {
            "shipments_scored": {
                e: baseline["engine_summaries"][e]["shipments_scored"] for e in ("A", "B", "C")
            },
            "confirmed": {
                e: baseline["engine_summaries"][e]["confirmed"] for e in ("A", "B", "C")
            },
            "loss_claims": {
                e: baseline["engine_summaries"][e]["loss_claims"] for e in ("A", "B", "C")
            },
            "unmatched": {
                e: baseline["engine_summaries"][e]["unmatched"] for e in ("A", "B", "C")
            },
            "partial_movement_count": baseline["movement_stats"]["partial_movements"],
        },
        "controlled_receipt_overlay": {
            "classification": receipt_overlay["overlay_classification"],
            "is_source_data": False,
            "receipt_rows": len(receipt_overlay["receipts"]),
            "confirmed": {
                e: scenario["engine_summaries"][e]["confirmed"] for e in ("A", "B", "C")
            },
            "loss_claims": {
                e: scenario["engine_summaries"][e]["loss_claims"] for e in ("A", "B", "C")
            },
            "pairwise_semantic_state_disagreements": scenario["pairwise_state_disagreements"],
            "raw_state_label_differences": scenario["pairwise_raw_state_label_differences"],
            "disagreement_count": scenario["disagreement_count"],
        },
        "threshold_observation": (
            "A, B and C use the same 0.5 reference-unit loss threshold. B retains "
            "a separate 2% per-shipment candidate tolerance."
        ),
        "raw_source_report_directory": str(raw_dir),
        "completed_test_report_directory": str(baseline_dir),
        "controlled_receipt_report_directory": str(scenario_dir),
        "writes_to_odoo": False,
        "source_records_modified": False,
        "completion_and_receipt_overlays_are_test_only": True,
    }
    (output_root / "odoo17_demo_abc_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Odoo 17 demo movement — A/B/C shadow experiment",
        "",
        "## Source movement fields",
        "",
        "- Source: Odoo 17 stock_demo2.xml.",
        "- Selected movement rows: 4 outbound records with a stock.move.line quantity write.",
        "- Source state: assigned; picked=false in the normalized source rows.",
        "- The XML invokes stock.picking._action_done, but Odoo 17 stock.move._action_done skips moves that are not picked.",
        "- Therefore the source itself does not establish these four moves as completed.",
        "",
        "## Test-only completion overlay",
        "",
        "A separate explicit overlay sets picked=true and state=done solely to exercise the matcher's completed-movement path.",
        "",
        "## Completed test baseline: no receipts",
        "",
        "| Engine | Scored | Confirmed | Loss claims | Unmatched |",
        "|---|---:|---:|---:|---:|",
    ]
    for e in ("A", "B", "C"):
        s = baseline["engine_summaries"][e]
        lines.append(f"| {e} | {s['shipments_scored']} | {s['confirmed']} | {s['loss_claims']} | {s['unmatched']} |")
    lines += [
        "",
        "All engines abstain when no receipt rows are supplied.",
        "",
        "## Controlled receipt overlay",
        "",
        "Four complete receipt rows are generated test inputs, not records contained in Odoo's source fixture.",
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
        "Loss-claim disagreements: 0 movements.",
        "",
        "## Finding",
        "",
        "A, B and C share the same 0.5 reference-unit loss threshold, while B retains "
        "its separate 2% per-shipment candidate tolerance. The overlay yields A=2, B=2, C=2 loss claims. "
        "Threshold coupling is removed for this comparison; equality on four controlled cases is not proof of equivalent accuracy.",
        "",
        "The comparator normalizes different engine-specific confirmed labels before counting semantic state disagreements.",
        "",
        "## Evidence boundary",
        "",
        "Movement attributes originate from Odoo's published demo fixture. Completion state and receiver receipts are explicit test-only overlays. "
        "The experiment validates ingestion/normalization and engine behavior under controlled cases, not actual Odoo execution or real-world receipt accuracy.",
    ]
    (output_root / "odoo17_demo_abc_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    result = execute()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
