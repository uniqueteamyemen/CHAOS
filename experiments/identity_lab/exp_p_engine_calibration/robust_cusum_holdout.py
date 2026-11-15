"""Independent holdout for robust CUSUM thresholds selected in Stage J."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Mapping

from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson
from experiments.identity_lab.exp_p_engine.cusum_parameter_sweep import score_cusum_hits
from experiments.identity_lab.exp_p_engine_holdout.robust_holdout import (
    NULL_SCENARIOS,
    SHIFT_SCENARIOS,
    generate_residuals,
    residuals_to_stock_rows,
)

TRIALS = 500
SEED_BASE = 4_100_000
VARIANTS = ("C", "E", "F")
SCENARIOS = NULL_SCENARIOS + SHIFT_SCENARIOS
NULL_UPPER95_GATE = 0.05
PRE_ONSET_UPPER95_GATE = 0.05
SENSITIVITY_LOWER95_GATE = 0.75
DEFAULT_CONTROL = {"candidate_id": "C-default-control", "variant": "C", "k": 0.5, "h": 8.5}
OUTPUT = Path(__file__).resolve().parent / "results" / "robust_cusum_holdout.json"


def selected_candidates(calibration: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Use only Stage J selections; never tune after opening holdout outcomes."""
    candidates = [dict(DEFAULT_CONTROL)]
    for variant in VARIANTS:
        selected = calibration.get("selections", {}).get(variant)
        if not selected:
            continue
        candidates.append({
            "candidate_id": f"{variant}-J-selected-h{float(selected['h']):.1f}",
            "variant": variant,
            "k": float(selected["k"]),
            "h": float(selected["h"]),
            "source": "stage_j_calibration",
        })
    return candidates


def _count_metrics(target: dict[str, Any], metrics: Mapping[str, Any]) -> None:
    target["false"] += int(metrics["false_alarm"])
    target["false_events"] += int(metrics["false_alarm_events"])
    target["pre_false"] += int(metrics["pre_onset_false_alarm"])
    target["detected"] += int(metrics["detected"])
    target["wrong"] += int(metrics["wrong_direction"])
    if metrics["delay"] is not None:
        target["delays"].append(float(metrics["delay"]))


def _summarize(counts: Mapping[str, Any], scenario: str) -> dict[str, Any]:
    if scenario in NULL_SCENARIOS:
        return {
            "false_alarm_rate": counts["false"] / TRIALS,
            "false_alarm_wilson95": wilson(counts["false"], TRIALS),
            "false_events_per_sequence": counts["false_events"] / TRIALS,
        }
    return {
        "pre_onset_false_alarm_rate": counts["pre_false"] / TRIALS,
        "pre_onset_false_alarm_wilson95": wilson(counts["pre_false"], TRIALS),
        "sensitivity": counts["detected"] / TRIALS,
        "sensitivity_wilson95": wilson(counts["detected"], TRIALS),
        "wrong_direction_trial_rate": counts["wrong"] / TRIALS,
        "mean_detection_delay": statistics.mean(counts["delays"]) if counts["delays"] else None,
        "median_detection_delay": statistics.median(counts["delays"]) if counts["delays"] else None,
    }


def evaluate_holdout(calibration: Mapping[str, Any], *, trials: int = TRIALS) -> dict[str, Any]:
    if trials < 200:
        raise ValueError("holdout_trials_must_be_at_least_200")
    candidates = selected_candidates(calibration)
    candidate_results = {}

    for candidate in candidates:
        variant = candidate["variant"]
        k, h = float(candidate["k"]), float(candidate["h"])
        counts = {
            scenario: {"false": 0, "false_events": 0, "pre_false": 0,
                       "detected": 0, "wrong": 0, "delays": []}
            for scenario in SCENARIOS
        }
        for scenario_index, scenario in enumerate(SCENARIOS):
            for trial in range(trials):
                seed = SEED_BASE + scenario_index * 100_000 + trial
                values = generate_residuals(seed, scenario)
                rows = residuals_to_stock_rows(values)
                result = run_candidates(
                    "stock", rows, quiet_range=(1, 40),
                    entity=f"robust-cusum-holdout-{scenario_index}",
                    code_revision="p-engine-robust-cusum-independent-holdout-k-v1",
                    k_cusum=k, h_cusum=h,
                )
                metrics = score_cusum_hits(
                    result[variant]["raw_hits"], scenario=scenario, onset=65
                )
                _count_metrics(counts[scenario], metrics)

        scenario_reports = {
            scenario: _summarize(counts[scenario], scenario)
            for scenario in SCENARIOS
        }
        null_uppers = {
            scenario: scenario_reports[scenario]["false_alarm_wilson95"][1]
            for scenario in NULL_SCENARIOS
        }
        pre_uppers = {
            scenario: scenario_reports[scenario]["pre_onset_false_alarm_wilson95"][1]
            for scenario in SHIFT_SCENARIOS
        }
        sensitivity_lowers = {
            scenario: scenario_reports[scenario]["sensitivity_wilson95"][0]
            for scenario in SHIFT_SCENARIOS
        }
        null_pass = max(null_uppers.values()) <= NULL_UPPER95_GATE
        pre_pass = max(pre_uppers.values()) <= PRE_ONSET_UPPER95_GATE
        sensitivity_pass = min(sensitivity_lowers.values()) >= SENSITIVITY_LOWER95_GATE
        candidate_results[candidate["candidate_id"]] = {
            "candidate": candidate,
            "worst_null_upper95": max(null_uppers.values()),
            "worst_pre_onset_upper95": max(pre_uppers.values()),
            "minimum_shift_sensitivity_lower95": min(sensitivity_lowers.values()),
            "null_gate_pass": null_pass,
            "pre_onset_gate_pass": pre_pass,
            "sensitivity_gate_pass": sensitivity_pass,
            "all_gates_pass": null_pass and pre_pass and sensitivity_pass,
            "scenarios": scenario_reports,
        }

    promoted = [
        candidate_id for candidate_id, result in candidate_results.items()
        if result["all_gates_pass"] and result["candidate"]["candidate_id"] != "C-default-control"
    ]
    return {
        "experiment": "p_engine_robust_cusum_independent_holdout_k_v1",
        "trials_per_condition": trials,
        "seed_base": SEED_BASE,
        "source_calibration": "stage_j_robust_cusum_calibration_artifact",
        "scenarios": list(SCENARIOS),
        "gates": {
            "null_false_alarm_wilson_upper95": NULL_UPPER95_GATE,
            "pre_onset_false_alarm_wilson_upper95": PRE_ONSET_UPPER95_GATE,
            "minimum_shift_sensitivity_wilson_lower95": SENSITIVITY_LOWER95_GATE,
        },
        "training_selected_candidates": calibration.get("selections", {}),
        "candidates": candidate_results,
        "promoted_candidates": promoted,
        "decision": (
            "one_or_more_settings_passed_independent_holdout"
            if promoted else
            "no_setting_passed_independent_holdout; retain current engine unchanged"
        ),
        "limitations": [
            "Synthetic AR(1)/Student-t3 holdout tests declared regimes only; it does not establish all-domain field false-alarm rates.",
            "The default production path is a diagnostic control, not eligible for promotion.",
            "No holdout outcome is used to retune a threshold.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    calibration = json.loads(args.calibration_report.read_text(encoding="utf-8"))
    report = evaluate_holdout(calibration, trials=args.trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        name: {
            "candidate": item["candidate"],
            "worst_null_upper95": item["worst_null_upper95"],
            "minimum_sensitivity_lower95": item["minimum_shift_sensitivity_lower95"],
            "all_gates_pass": item["all_gates_pass"],
        }
        for name, item in report["candidates"].items()
    }
    print(json.dumps({
        "output": str(args.output),
        "candidates": compact,
        "promoted_candidates": report["promoted_candidates"],
        "decision": report["decision"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
