"""Independent AR(1)/heavy-tail threshold calibration for P-engine CUSUM.

This phase uses new seeds, expands h while holding k=0.5, and measures CUSUM
raw alarms separately for C/E/F. It selects only thresholds whose Wilson
confidence bounds satisfy the declared null and sensitivity gates.
"""
from __future__ import annotations

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
K_FIXED = 0.5
H_GRID = (24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 80.0, 96.0)
VARIANTS = ("C", "E", "F")
SCENARIOS = NULL_SCENARIOS + SHIFT_SCENARIOS
SEED_BASE = 3_100_000
NULL_UPPER95_GATE = 0.05
PRE_ONSET_UPPER95_GATE = 0.05
SENSITIVITY_LOWER95_GATE = 0.75

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "experiments" / "identity_lab" / "exp_p_engine_calibration" / "results" / "robust_cusum_calibration.json"


def _record_score(target: dict[str, Any], metrics: Mapping[str, Any]) -> None:
    target["null_false"] += int(metrics["false_alarm"])
    target["null_events"] += int(metrics["false_alarm_events"])
    target["pre_onset_false"] += int(metrics["pre_onset_false_alarm"])
    target["detected"] += int(metrics["detected"])
    target["wrong_direction"] += int(metrics["wrong_direction"])
    if metrics["delay"] is not None:
        target["delays"].append(float(metrics["delay"]))


def _summarize_counts(counts: Mapping[str, Any], scenario: str, trials: int) -> dict[str, Any]:
    null = scenario in NULL_SCENARIOS
    if null:
        return {
            "false_alarm_count": counts["null_false"],
            "false_alarm_rate": counts["null_false"] / trials,
            "false_alarm_wilson95": wilson(counts["null_false"], trials),
            "false_events_per_sequence": counts["null_events"] / trials,
        }
    return {
        "pre_onset_false_alarm_count": counts["pre_onset_false"],
        "pre_onset_false_alarm_rate": counts["pre_onset_false"] / trials,
        "pre_onset_false_alarm_wilson95": wilson(counts["pre_onset_false"], trials),
        "detected_count": counts["detected"],
        "sensitivity": counts["detected"] / trials,
        "sensitivity_wilson95": wilson(counts["detected"], trials),
        "wrong_direction_count": counts["wrong_direction"],
        "wrong_direction_trial_rate": counts["wrong_direction"] / trials,
        "mean_detection_delay": statistics.mean(counts["delays"]) if counts["delays"] else None,
        "median_detection_delay": statistics.median(counts["delays"]) if counts["delays"] else None,
    }


def _upper(ci: Any) -> float:
    return float(ci[1])


def _lower(ci: Any) -> float:
    return float(ci[0])


def evaluate_gates(parameter_results: Mapping[str, Any], variant: str) -> dict[str, Any]:
    null_upper = {
        scenario: _upper(parameter_results[scenario][variant]["false_alarm_wilson95"])
        for scenario in NULL_SCENARIOS
    }
    pre_upper = {
        scenario: _upper(parameter_results[scenario][variant]["pre_onset_false_alarm_wilson95"])
        for scenario in SHIFT_SCENARIOS
    }
    shift_lower = {
        scenario: _lower(parameter_results[scenario][variant]["sensitivity_wilson95"])
        for scenario in SHIFT_SCENARIOS
    }
    null_pass = max(null_upper.values()) <= NULL_UPPER95_GATE
    pre_pass = max(pre_upper.values()) <= PRE_ONSET_UPPER95_GATE
    shift_pass = min(shift_lower.values()) >= SENSITIVITY_LOWER95_GATE
    return {
        "null_upper95_by_scenario": null_upper,
        "worst_null_upper95": max(null_upper.values()),
        "pre_onset_upper95_by_scenario": pre_upper,
        "worst_pre_onset_upper95": max(pre_upper.values()),
        "sensitivity_lower95_by_scenario": shift_lower,
        "minimum_sensitivity_lower95": min(shift_lower.values()),
        "null_gate_pass": null_pass,
        "pre_onset_gate_pass": pre_pass,
        "sensitivity_gate_pass": shift_pass,
        "all_gates_pass": null_pass and pre_pass and shift_pass,
    }


def select_thresholds(calibration: Mapping[str, Any]) -> dict[str, Any]:
    selections = {}
    for variant in VARIANTS:
        eligible = []
        for key, cell in calibration["parameter_results"].items():
            gate = evaluate_gates(cell, variant)
            if gate["all_gates_pass"]:
                eligible.append({
                    "k": K_FIXED,
                    "h": float(key),
                    "gate": gate,
                    "worst_null_upper95": gate["worst_null_upper95"],
                    "minimum_sensitivity_lower95": gate["minimum_sensitivity_lower95"],
                    "worst_pre_onset_upper95": gate["worst_pre_onset_upper95"],
                })
        selections[variant] = (
            min(eligible, key=lambda x: x["h"])
            if eligible else None
        )
    return selections


def run_calibration(*, trials: int = TRIALS) -> dict[str, Any]:
    if trials < 200:
        raise ValueError("calibration_trials_must_be_at_least_200")
    parameter_results: dict[str, Any] = {}
    for h in H_GRID:
        per_scenario = {
            scenario: {
                variant: {
                    "null_false": 0,
                    "null_events": 0,
                    "pre_onset_false": 0,
                    "detected": 0,
                    "wrong_direction": 0,
                    "delays": [],
                }
                for variant in VARIANTS
            }
            for scenario in SCENARIOS
        }
        for scenario_index, scenario in enumerate(SCENARIOS):
            for trial in range(trials):
                seed = SEED_BASE + scenario_index * 100_000 + trial
                residuals = generate_residuals(seed, scenario)
                rows = residuals_to_stock_rows(residuals)
                result = run_candidates(
                    "stock", rows, quiet_range=(1, 40),
                    entity=f"robust-cusum-calibration-{scenario_index}",
                    code_revision="p-engine-robust-cusum-calibration-j-v1",
                    k_cusum=K_FIXED, h_cusum=h,
                )
                for variant in VARIANTS:
                    metrics = score_cusum_hits(
                        result[variant]["raw_hits"], scenario=scenario, onset=65
                    )
                    _record_score(per_scenario[scenario][variant], metrics)

        parameter_results[f"{h:.1f}"] = {
            scenario: {
                variant: _summarize_counts(
                    per_scenario[scenario][variant], scenario, trials
                )
                for variant in VARIANTS
            }
            for scenario in SCENARIOS
        }

    partial = {
        "experiment": "p_engine_robust_cusum_calibration_j_v1",
        "trials_per_condition": trials,
        "seed_base": SEED_BASE,
        "k_fixed": K_FIXED,
        "h_grid": list(H_GRID),
        "variants": {
            "C": "bounded and damped transition scale",
            "E": "reset both CUSUM accumulators during transition; cap scale afterwards",
            "F": "reset both accumulators during transition; observed uncapped scale afterwards",
        },
        "scenarios": list(SCENARIOS),
        "gates": {
            "null_false_alarm_wilson_upper95": NULL_UPPER95_GATE,
            "pre_onset_false_alarm_wilson_upper95": PRE_ONSET_UPPER95_GATE,
            "minimum_directional_sensitivity_wilson_lower95": SENSITIVITY_LOWER95_GATE,
        },
        "parameter_results": parameter_results,
    }
    partial["selections"] = select_thresholds(partial)
    partial["decision"] = (
        "candidate_settings_selected_for_independent_holdout_only"
        if any(partial["selections"].values())
        else "no_setting_passed_all_robust_calibration_gates"
    )
    partial["limitations"] = [
        "This calibration uses synthetic AR(1) and Student-t3 nulls; it does not prove field false-alarm rates.",
        "Threshold selection uses calibration seeds only. Independent holdout must use a disjoint seed range.",
        "CUSUM raw evidence is scored separately from P1 and fused events.",
    ]
    return partial


def main() -> int:
    report = run_calibration()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        variant: (
            None if selected is None else {
                "h": selected["h"],
                "worst_null_upper95": selected["worst_null_upper95"],
                "minimum_sensitivity_lower95": selected["minimum_sensitivity_lower95"],
                "worst_pre_onset_upper95": selected["worst_pre_onset_upper95"],
            }
        )
        for variant, selected in report["selections"].items()
    }
    print(json.dumps({
        "output": str(OUTPUT),
        "experiment": report["experiment"],
        "trials_per_condition": report["trials_per_condition"],
        "selections": compact,
        "decision": report["decision"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
