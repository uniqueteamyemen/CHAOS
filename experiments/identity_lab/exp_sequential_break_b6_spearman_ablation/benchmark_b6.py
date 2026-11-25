"""B-v6 paired Pearson/Spearman ablation with development-only threshold selection."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    N,
    ONSET,
    generate_series,
)
from experiments.identity_lab.exp_sequential_break_b5_rho_adaptive.engine_b5 import (
    RhoAdaptiveTransientKendallEngineB5,
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import (
    PearsonSpearmanFixedGateEngineB6,
)

CASES = [
    ("gauss_r0.3_null", "gauss", 0.3, False, 0.0),
    ("gauss_r0.7_null", "gauss", 0.7, False, 0.0),
    ("gauss_r0.7_vjump", "gauss", 0.7, True, 0.0),
    ("t3_r0.3_null", "t3", 0.3, False, 0.0),
    ("t3_r0.7_null", "t3", 0.7, False, 0.0),
    ("t3_r0.7_vjump", "t3", 0.7, True, 0.0),
    ("pos_shift_3.0s", "gauss", 0.7, False, 3.0),
    ("neg_shift_3.0s", "gauss", 0.7, False, -3.0),
]
DEV_SEED_BASE = 8_000_000
HOLDOUT_SEED_BASE = 9_000_000
TRIALS_PER_CASE = 500
THRESHOLDS = (85.0, 83.5)
FPR_LIMIT = 5.0
SENSITIVITY_TARGET = 93.0
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b5_ref_b6_pearson_spearman_ablation.json"
)

DEV_CONFIG_NAMES = (
    "B-v6a_pearson@85.0",
    "B-v6a_pearson@83.5",
    "B-v6b_spearman@85.0",
    "B-v6b_spearman@83.5",
)
HOLDOUT_CONFIG_NAMES = (
    "B-v5_ref",
    "B-v6a_pearson",
    "B-v6b_spearman",
)


def wilson(successes: int, trials: int) -> list[float]:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid_binomial_counts")
    z = 1.959963984540054
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(
            p * (1.0 - p) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def rate(successes: int, trials: int) -> dict[str, Any]:
    lower, upper = wilson(successes, trials)
    return {
        "sequences": int(successes),
        "rate_pct": round(100.0 * successes / trials, 2),
        "wilson95_pct": [round(100.0 * lower, 2), round(100.0 * upper, 2)],
    }


def make_engine(config_name: str, threshold: float | None = None):
    if config_name == "B-v5_ref":
        return RhoAdaptiveTransientKendallEngineB5(
            quiet_end=40,
            window_size=12,
            anomaly_z_thresh=3.8,
            winsor_cap=1.8,
            break_percent_thresh=85.0,
            resolution_horizon=14,
            return_to_baseline_z=1.5,
            persistence_z_thresh=1.45,
        )
    if config_name.startswith("B-v6a_pearson@"):
        threshold = float(config_name.rsplit("@", 1)[1])
        method = "pearson"
    elif config_name.startswith("B-v6b_spearman@"):
        threshold = float(config_name.rsplit("@", 1)[1])
        method = "spearman"
    elif config_name == "B-v6a_pearson":
        method = "pearson"
    elif config_name == "B-v6b_spearman":
        method = "spearman"
    else:
        raise ValueError(f"unknown_b6_configuration:{config_name}")
    if threshold is None:
        raise ValueError(f"threshold_required_for:{config_name}")
    return PearsonSpearmanFixedGateEngineB6(
        quiet_end=40,
        window_size=12,
        anomaly_z_thresh=3.8,
        winsor_cap=1.8,
        break_percent_thresh=float(threshold),
        resolution_horizon=14,
        return_to_baseline_z=1.5,
        persistence_z_thresh=1.45,
        correlation_method=method,
    )


def classify(result: dict[str, Any], shift: float) -> dict[str, Any]:
    breaks = list(result["structural_breaks"])
    transients = list(result["transient_anomalies"])
    unresolved = list(result["unresolved_alerts"])

    pre_breaks: list[dict[str, Any]] = []
    pre_transients: list[dict[str, Any]] = []
    pre_unresolved: list[dict[str, Any]] = []
    wrong_direction: list[dict[str, Any]] = []
    delay = None

    if shift == 0.0:
        # For null/variance-jump cases any structural direction is a false alarm.
        structural = bool(breaks)
    else:
        expected_direction = 1 if shift > 0 else -1
        pre_breaks = [
            event for event in breaks
            if int(event["detection_time"]) < ONSET
        ]
        post_breaks = [
            event for event in breaks
            if int(event["detection_time"]) >= ONSET
        ]
        correct = [
            event for event in post_breaks
            if int(event["direction"]) == expected_direction
        ]
        wrong_direction = [
            event for event in post_breaks
            if int(event["direction"]) != expected_direction
        ]
        first_correct = (
            min(correct, key=lambda event: int(event["detection_time"]))
            if correct else None
        )
        structural = first_correct is not None
        if first_correct is not None:
            delay = int(first_correct["detection_time"]) - ONSET
        pre_transients = [
            event for event in transients if int(event["time"]) < ONSET
        ]
        pre_unresolved = [
            event for event in unresolved if int(event["time"]) < ONSET
        ]

    lifecycle = result["pending_lifecycle"]
    terminal_count = (
        int(lifecycle["resolved_structural_count"])
        + int(lifecycle["resolved_transient_count"])
        + int(lifecycle["unresolved_count"])
    )
    return {
        "structural": bool(structural),
        "any_structural": bool(breaks),
        "transient": bool(transients),
        "unresolved": bool(unresolved),
        # Combined includes correct/wrong/pre-onset structural, transient, unresolved.
        "combined": bool(breaks or transients or unresolved),
        "wrong_direction": bool(wrong_direction),
        "pre_structural": bool(pre_breaks),
        "pre_transient": bool(pre_transients),
        "pre_unresolved": bool(pre_unresolved),
        "pre_combined": bool(pre_breaks or pre_transients or pre_unresolved),
        "delay": delay,
        "events": {
            "structural": len(breaks),
            "transient": len(transients),
            "unresolved": len(unresolved),
            "pending_opened": int(lifecycle["opened_count"]),
            "pending_resolved_structural": int(lifecycle["resolved_structural_count"]),
            "pending_resolved_transient": int(lifecycle["resolved_transient_count"]),
            "pending_unresolved": int(lifecycle["unresolved_count"]),
        },
        "lifecycle_ok": (
            bool(lifecycle["accounting_complete"])
            and int(lifecycle["opened_count"]) == terminal_count
        ),
    }


def empty_counts() -> dict[str, Any]:
    return {
        "structural": 0,
        "any_structural": 0,
        "transient": 0,
        "unresolved": 0,
        "combined": 0,
        "wrong_direction": 0,
        "pre_structural": 0,
        "pre_transient": 0,
        "pre_unresolved": 0,
        "pre_combined": 0,
        "delays": [],
        "lifecycle_ok": True,
        "events": {
            "structural": 0,
            "transient": 0,
            "unresolved": 0,
            "pending_opened": 0,
            "pending_resolved_structural": 0,
            "pending_resolved_transient": 0,
            "pending_unresolved": 0,
        },
    }


def add_measurement(counts: dict[str, Any], measurement: dict[str, Any]) -> None:
    for key in (
        "structural", "any_structural", "transient", "unresolved", "combined",
        "wrong_direction", "pre_structural", "pre_transient", "pre_unresolved",
        "pre_combined",
    ):
        counts[key] += int(measurement[key])
    if measurement["delay"] is not None:
        counts["delays"].append(int(measurement["delay"]))
    counts["lifecycle_ok"] = (
        counts["lifecycle_ok"] and measurement["lifecycle_ok"]
    )
    for key, value in measurement["events"].items():
        counts["events"][key] += int(value)


def summarize_case(
    shift: float,
    variance_jump: bool,
    counts: dict[str, Any],
    trials: int,
) -> dict[str, Any]:
    scenario_type = (
        "level_shift" if shift != 0.0
        else ("variance_jump" if variance_jump else "pure_null")
    )
    return {
        "scenario_type": scenario_type,
        "trials": trials,
        "structural_metric_label": (
            "correct_directional_structural_detection"
            if shift != 0.0 else "structural_false_alarm"
        ),
        "structural_rate": rate(counts["structural"], trials),
        "any_structural_alert_rate": rate(counts["any_structural"], trials),
        "transient_alert_rate": rate(counts["transient"], trials),
        "unresolved_alert_rate": rate(counts["unresolved"], trials),
        "combined_any_alert_rate": rate(counts["combined"], trials),
        "wrong_direction_structural_rate": rate(counts["wrong_direction"], trials),
        "pre_onset_structural_rate": rate(counts["pre_structural"], trials),
        "pre_onset_transient_rate": rate(counts["pre_transient"], trials),
        "pre_onset_unresolved_rate": rate(counts["pre_unresolved"], trials),
        "pre_onset_combined_rate": rate(counts["pre_combined"], trials),
        "median_correct_detection_delay": (
            round(float(statistics.median(counts["delays"])), 2)
            if counts["delays"] else None
        ),
        "event_totals": counts["events"],
        "pending_lifecycle_accounting_complete": counts["lifecycle_ok"],
    }


def summarize_configuration(
    case_counts: dict[str, dict[str, Any]],
    trials: int,
) -> dict[str, Any]:
    rows = {
        name: summarize_case(shift, variance_jump, case_counts[name], trials)
        for name, _dist, _rho, variance_jump, shift in CASES
    }
    nonlevel = [
        row for row in rows.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_nulls = [
        row for row in rows.values() if row["scenario_type"] == "pure_null"
    ]
    shifts = [
        row for row in rows.values() if row["scenario_type"] == "level_shift"
    ]
    worst_structural = max(
        row["structural_rate"]["rate_pct"] for row in nonlevel
    )
    worst_combined = max(
        row["combined_any_alert_rate"]["rate_pct"] for row in pure_nulls
    )
    worst_pre_onset = max(
        row["pre_onset_combined_rate"]["rate_pct"] for row in shifts
    )
    sensitivity = round(
        statistics.mean(row["structural_rate"]["rate_pct"] for row in shifts), 2
    )
    lifecycle_ok = all(
        row["pending_lifecycle_accounting_complete"] for row in rows.values()
    )
    point_gates = {
        "structural_fpr_all_nonlevel_le_5": worst_structural <= FPR_LIMIT,
        "combined_fpr_all_pure_null_le_5": worst_combined <= FPR_LIMIT,
        "pre_onset_combined_all_shifts_le_5": worst_pre_onset <= FPR_LIMIT,
        "mean_directional_sensitivity_ge_93": sensitivity >= SENSITIVITY_TARGET,
        "lifecycle_accounting": lifecycle_ok,
    }
    return {
        "cases": rows,
        "worst_structural_fpr_nonlevel_pct": worst_structural,
        "worst_combined_fpr_pure_null_pct": worst_combined,
        "worst_pre_onset_combined_pct": worst_pre_onset,
        "mean_directional_sensitivity_pct": sensitivity,
        "lifecycle_accounting_complete": lifecycle_ok,
        "point_gates": point_gates,
    }


def evaluate_stage(
    seed_base: int,
    config_names: tuple[str, ...],
    trials: int,
    stage_name: str,
    selected_threshold: float | None = None,
) -> dict[str, Any]:
    engines = {
        name: make_engine(
            name,
            threshold=selected_threshold if name in ("B-v6a_pearson", "B-v6b_spearman") else None,
        )
        for name in config_names
    }
    counts = {
        config: {case[0]: empty_counts() for case in CASES}
        for config in config_names
    }
    for case_index, (case_name, distribution, rho, variance_jump, shift) in enumerate(CASES):
        for trial_index in range(trials):
            seed = seed_base + case_index * 10_000 + trial_index
            series = generate_series(
                np.random.default_rng(seed),
                dist=distribution,
                rho=rho,
                var_jump=variance_jump,
                shift_sigma=shift,
                n=N,
                onset=ONSET,
            )
            # One generated series is passed to every configuration in this stage.
            for config_name, engine in engines.items():
                result = engine.analyze(series)
                add_measurement(counts[config_name][case_name], classify(result, shift))

    summaries = {
        config_name: summarize_configuration(counts[config_name], trials)
        for config_name in config_names
    }
    return {
        "stage": stage_name,
        "seed_base": seed_base,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "generated_series_count": len(CASES) * trials,
        "configuration_evaluations": len(CASES) * trials * len(config_names),
        "same_generated_series_for_all_configurations": True,
        "models": summaries,
    }


def threshold_selection_metrics(
    pearson: dict[str, Any],
    spearman: dict[str, Any],
) -> dict[str, Any]:
    configs = {"pearson": pearson, "spearman": spearman}
    fpr_keys = (
        "structural_fpr_all_nonlevel_le_5",
        "combined_fpr_all_pure_null_le_5",
        "pre_onset_combined_all_shifts_le_5",
    )
    failures = 0
    excess = 0.0
    sensitivities = []
    by_method = {}
    for method, summary in configs.items():
        gates = summary["point_gates"]
        metric_values = (
            summary["worst_structural_fpr_nonlevel_pct"],
            summary["worst_combined_fpr_pure_null_pct"],
            summary["worst_pre_onset_combined_pct"],
        )
        failures += sum(not bool(gates[key]) for key in fpr_keys)
        excess += sum(max(0.0, value - FPR_LIMIT) for value in metric_values)
        sensitivities.append(summary["mean_directional_sensitivity_pct"])
        by_method[method] = {
            "worst_structural_fpr_nonlevel_pct": metric_values[0],
            "worst_combined_fpr_pure_null_pct": metric_values[1],
            "worst_pre_onset_combined_pct": metric_values[2],
            "mean_directional_sensitivity_pct": summary["mean_directional_sensitivity_pct"],
            "fpr_gates_passed": all(bool(gates[key]) for key in fpr_keys),
            "sensitivity_gate_passed": bool(
                gates["mean_directional_sensitivity_ge_93"]
            ),
        }
    eligible = all(
        bool(item["fpr_gates_passed"]) and bool(item["sensitivity_gate_passed"])
        for item in by_method.values()
    )
    return {
        "eligible": eligible,
        "fpr_gate_failures_across_two_methods": int(failures),
        "sum_fpr_excess_percentage_points_above_5": round(excess, 4),
        "pooled_mean_directional_sensitivity_pct": round(
            statistics.mean(sensitivities), 2
        ),
        "by_method": by_method,
    }


def select_development_threshold(
    development: dict[str, Any],
) -> dict[str, Any]:
    candidates = {}
    for threshold in THRESHOLDS:
        suffix = f"@{threshold:.1f}"
        pearson_name = f"B-v6a_pearson{suffix}"
        spearman_name = f"B-v6b_spearman{suffix}"
        candidates[threshold] = threshold_selection_metrics(
            development["models"][pearson_name],
            development["models"][spearman_name],
        )

    eligible_thresholds = [
        threshold for threshold, metrics in candidates.items()
        if metrics["eligible"]
    ]
    if eligible_thresholds:
        selected = sorted(
            eligible_thresholds,
            key=lambda threshold: (
                -candidates[threshold]["pooled_mean_directional_sensitivity_pct"],
                0 if threshold == 85.0 else 1,
            ),
        )[0]
        mode = "eligible_threshold_max_sensitivity"
        all_gates_met = True
    else:
        # Pre-registered fallback: minimize FPR failures, then FPR excess,
        # then maximize sensitivity; prefer 85.0 on a complete tie.
        selected = sorted(
            THRESHOLDS,
            key=lambda threshold: (
                candidates[threshold]["fpr_gate_failures_across_two_methods"],
                candidates[threshold]["sum_fpr_excess_percentage_points_above_5"],
                -candidates[threshold]["pooled_mean_directional_sensitivity_pct"],
                0 if threshold == 85.0 else 1,
            ),
        )[0]
        mode = "best_effort_fallback_no_threshold_met_all_development_gates"
        all_gates_met = False

    return {
        "selected_threshold": float(selected),
        "selection_mode": mode,
        "development_all_gates_met": all_gates_met,
        "eligible_thresholds": [float(value) for value in eligible_thresholds],
        "candidate_threshold_scores": {
            f"{threshold:.1f}": candidates[threshold]
            for threshold in THRESHOLDS
        },
        "rule": (
            "Both correlation methods must pass all three development FPR point-estimate "
            "ceilings and mean sensitivity >=93 to make a threshold eligible. If eligible, "
            "maximize pooled sensitivity and prefer 85.0 on a tie. If none eligible, "
            "minimize total failed FPR gates, then summed FPR excess above 5, then maximize "
            "pooled sensitivity, then prefer 85.0."
        ),
        "holdout_used_for_selection": False,
    }


def confidence_gates(summary: dict[str, Any]) -> dict[str, bool]:
    rows = summary["cases"]
    nonlevel = [
        row for row in rows.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_nulls = [
        row for row in rows.values() if row["scenario_type"] == "pure_null"
    ]
    shifts = [
        row for row in rows.values() if row["scenario_type"] == "level_shift"
    ]
    return {
        "structural_wilson_upper95_all_nonlevel_le_5": all(
            row["structural_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in nonlevel
        ),
        "combined_wilson_upper95_all_pure_null_le_5": all(
            row["combined_any_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in pure_nulls
        ),
        "pre_onset_combined_wilson_upper95_all_shifts_le_5": all(
            row["pre_onset_combined_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in shifts
        ),
        "mean_directional_sensitivity_ge_93": (
            summary["mean_directional_sensitivity_pct"] >= SENSITIVITY_TARGET
        ),
        "lifecycle_accounting": summary["lifecycle_accounting_complete"],
    }


def seed_ranges(seed_base: int, trials: int) -> dict[str, list[int]]:
    return {
        case[0]: [
            seed_base + index * 10_000,
            seed_base + index * 10_000 + trials - 1,
        ]
        for index, case in enumerate(CASES)
    }


def seed_blocks_disjoint(
    development_ranges: dict[str, list[int]],
    holdout_ranges: dict[str, list[int]],
) -> bool:
    for dev_start, dev_end in development_ranges.values():
        for hold_start, hold_end in holdout_ranges.values():
            if dev_start <= hold_end and hold_start <= dev_end:
                return False
    return True


def parameter_provenance() -> dict[str, Any]:
    return {
        "winsor_cap": {
            "value": 1.8,
            "source": "B-v4",
            "evidence": {
                "t3_r0.3_null_structural_fpr_pct": 0.6,
                "mean_directional_sensitivity_pct": 90.7,
                "stage": "historical comparative holdout replay",
                "interpretation": "Retained without retuning in B-v6.",
            },
            "source_branch": "experiment/b4-two-point-transient-winsor18",
        },
        "persistence_z_threshold": {
            "value": 1.45,
            "source": "B-v4",
            "evidence": {
                "paired_with_winsor_cap": 1.8,
                "t3_r0.3_null_structural_fpr_pct": 0.6,
                "mean_directional_sensitivity_pct": 90.7,
            },
            "source_branch": "experiment/b4-two-point-transient-winsor18",
        },
        "anomaly_z_thresh": {
            "value": 3.8,
            "source": "B-v5",
            "evidence": {
                "case": "t3_r0.7_null",
                "B_v4_transient_alert_rate_pct": 22.2,
                "B_v5_transient_alert_rate_pct": 9.0,
                "reduction_percentage_points": 13.2,
                "seed_block": "7M paired holdout",
            },
            "qualification": (
                "This is an observed B-v4/B-v5 paired-configuration difference, "
                "not an isolated estimate of the three-point gate effect because "
                "B-v5 also changed rho through its half-strength upward correction."
            ),
        },
        "three_point_pending_gate": {
            "value": "three adjacent z_point_raw values; each abs(z)>3.8; all same sign",
            "source": "B-v5 high-rho gate generalized to all rho levels",
            "qualification": (
                "The B-v5 high-rho branch required three points. B-v6 applies "
                "three points at every rho to isolate the effect from adaptive gating."
            ),
        },
        "no_kendall_inflation": {
            "value": "rho = clip(rho_raw, 0.0, 0.88); no upward correction",
            "source": "B-v5 versus B-v4 paired 7M comparison",
            "evidence": {
                "B_v4_mean_directional_sensitivity_pct": 91.6,
                "B_v5_mean_directional_sensitivity_pct": 84.1,
                "sensitivity_change_percentage_points": -7.5,
            },
            "terminology_note": (
                "B-v5 did not calculate Kendall's tau. It used Pearson lag-1 "
                "correlation plus a heuristic half-strength small-sample adjustment. "
                "B-v6 disables that adjustment; the estimator ablation is Pearson "
                "versus the specified rank-based lag-1 correlation."
            ),
        },
        "break_percent_thresh": {
            "baseline_value": 85.0,
            "calibration_hypothesis": 83.5,
            "classification": "calibration_hypothesis",
            "selection": (
                "Both values are evaluated on development seeds. 83.5 is not "
                "imposed; one shared threshold is selected by the pre-registered "
                "development-only rule and frozen before holdout evaluation."
            ),
        },
        "rho_clip": {
            "value": [0.0, 0.88],
            "source": "B-v3.1/B-v4 detector convention retained through B-v6",
        },
        "resolution_horizon": {
            "value": 14,
            "source": "B-v4/B-v5 lineage",
        },
        "return_to_baseline_z": {
            "value": 1.5,
            "source": "B-v3.2/B-v4/B-v5 observed-return rule",
        },
    }


def print_holdout_tables(holdout: dict[str, Any]) -> None:
    def fmt(metric: dict[str, Any]) -> str:
        low, high = metric["wilson95_pct"]
        return f"{metric['rate_pct']:.2f} [{low:.2f},{high:.2f}]"

    print("\\n=== B-v6 HOLDOUT CASE COMPARISON (rate_pct [Wilson95 lower,upper]) ===")
    print(
        "case | config | structural | transient | unresolved | combined | "
        "pre-onset combined | directional sensitivity"
    )
    for case_name, *_ in CASES:
        for config_name in HOLDOUT_CONFIG_NAMES:
            model = holdout["models"][config_name]
            row = model["cases"][case_name]
            sensitivity = (
                fmt(row["structural_rate"])
                if row["scenario_type"] == "level_shift" else "n/a"
            )
            print(
                f"{case_name} | {config_name} | "
                f"{fmt(row['structural_rate'])} | "
                f"{fmt(row['transient_alert_rate'])} | "
                f"{fmt(row['unresolved_alert_rate'])} | "
                f"{fmt(row['combined_any_alert_rate'])} | "
                f"{fmt(row['pre_onset_combined_rate'])} | "
                f"{sensitivity}"
            )

    print("\\n=== B-v6 HOLDOUT AGGREGATES ===")
    print(
        "config | worst structural FPR | worst pure-null Combined | "
        "worst pre-onset Combined | mean directional sensitivity | lifecycle"
    )
    for config_name in HOLDOUT_CONFIG_NAMES:
        model = holdout["models"][config_name]
        print(
            f"{config_name} | "
            f"{model['worst_structural_fpr_nonlevel_pct']:.2f} | "
            f"{model['worst_combined_fpr_pure_null_pct']:.2f} | "
            f"{model['worst_pre_onset_combined_pct']:.2f} | "
            f"{model['mean_directional_sensitivity_pct']:.2f} | "
            f"{model['lifecycle_accounting_complete']}"
        )


def run(
    dev_trials: int = TRIALS_PER_CASE,
    holdout_trials: int = TRIALS_PER_CASE,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    if dev_trials != TRIALS_PER_CASE or holdout_trials != TRIALS_PER_CASE:
        raise ValueError("B6_requires_exactly_500_trials_per_case_for_both_stages")
    if N != 140 or ONSET != 65:
        raise AssertionError(f"benchmark_generator_contract_mismatch:N={N},ONSET={ONSET}")

    started = time.perf_counter()
    development = evaluate_stage(
        DEV_SEED_BASE, DEV_CONFIG_NAMES, dev_trials, "development_sweep"
    )
    development_elapsed = round(time.perf_counter() - started, 2)
    selection = select_development_threshold(development)

    # Freeze threshold before any 9M holdout sequence is generated or evaluated.
    selected_threshold = float(selection["selected_threshold"])
    started = time.perf_counter()
    holdout = evaluate_stage(
        HOLDOUT_SEED_BASE,
        HOLDOUT_CONFIG_NAMES,
        holdout_trials,
        "pristine_unseen_holdout",
        selected_threshold=selected_threshold,
    )
    holdout_elapsed = round(time.perf_counter() - started, 2)

    dev_ranges = seed_ranges(DEV_SEED_BASE, dev_trials)
    holdout_ranges = seed_ranges(HOLDOUT_SEED_BASE, holdout_trials)
    seeds_disjoint = seed_blocks_disjoint(dev_ranges, holdout_ranges)
    if not seeds_disjoint:
        raise AssertionError("development_and_holdout_seed_blocks_overlap")

    holdout_gates = {
        config: confidence_gates(summary)
        for config, summary in holdout["models"].items()
    }
    holdout_final_gates = {
        config: all(gates.values())
        for config, gates in holdout_gates.items()
    }
    report = {
        "experiment": "B-v6 Spearman vs Pearson Ablation & Documented Calibration",
        "candidate_branch": "experiment/b6-spearman-ablation-documented",
        "parent_branch": "experiment/b5-rho-adaptive-transient-kendall",
        "parent_commit_B5": "e284df0220cee7005c24683ad08a4451517613f0",
        "parameter_provenance": parameter_provenance(),
        "fixed_specification": {
            "quiet_end": 40,
            "window_size": 12,
            "series_length": 140,
            "onset_index_zero_based": 65,
            "resolution_horizon": 14,
            "return_to_baseline_rule": (
                "0 < age <= 14 and abs((values[t]-baseline_center)/baseline_spread) < 1.5"
            ),
            "winsor_cap": 1.8,
            "persistence_z_threshold": 1.45,
            "anomaly_z_thresh": 3.8,
            "three_point_pending_gate": (
                "abs(z_point_raw[-3:]) > 3.8 for all three points, same sign"
            ),
            "rho_clip": [0.0, 0.88],
            "rho_adjustment": "none for B-v6a and B-v6b",
            "lifecycle_invariant": (
                "pending_opened == resolved_structural + resolved_transient + unresolved"
            ),
            "combined_definition": (
                "union of any structural (correct, wrong-direction, pre-onset), "
                "transient, or unresolved alert"
            ),
        },
        "design": {
            "cases": [case[0] for case in CASES],
            "case_count": len(CASES),
            "trials_per_case_development": dev_trials,
            "trials_per_case_holdout": holdout_trials,
            "dev_seed_base": DEV_SEED_BASE,
            "holdout_seed_base": HOLDOUT_SEED_BASE,
            "seed_scheme": "seed_base + case_index * 10000 + trial_index",
            "development_seed_ranges": dev_ranges,
            "holdout_seed_ranges": holdout_ranges,
            "seed_blocks_disjoint": seeds_disjoint,
            "development_generated_series": development["generated_series_count"],
            "development_configuration_evaluations": development["configuration_evaluations"],
            "holdout_generated_series": holdout["generated_series_count"],
            "holdout_configuration_evaluations": holdout["configuration_evaluations"],
            "all_configurations_receive_same_generated_series_within_each_stage": True,
            "thresholds_swept_on_development": list(THRESHOLDS),
            "holdout_threshold_selection_leakage": False,
            "false_alarm_budget_pct": FPR_LIMIT,
            "mean_directional_sensitivity_target_pct": SENSITIVITY_TARGET,
            "wilson_confidence_level_pct": 95.0,
        },
        "development_sweep": development,
        "development_elapsed_seconds": development_elapsed,
        "development_threshold_selection": selection,
        "pristine_unseen_holdout": holdout,
        "holdout_elapsed_seconds": holdout_elapsed,
        "holdout_confidence_gates": holdout_gates,
        "holdout_final_gates": holdout_final_gates,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== B-v6 DEVELOPMENT SWEEP ===", flush=True)
    print(
        "configuration | worst structural FPR | worst pure-null Combined | "
        "worst pre-onset Combined | mean sensitivity | point gates"
    )
    for config_name in DEV_CONFIG_NAMES:
        model = development["models"][config_name]
        print(
            f"{config_name} | "
            f"{model['worst_structural_fpr_nonlevel_pct']:.2f}% | "
            f"{model['worst_combined_fpr_pure_null_pct']:.2f}% | "
            f"{model['worst_pre_onset_combined_pct']:.2f}% | "
            f"{model['mean_directional_sensitivity_pct']:.2f}% | "
            f"{model['point_gates']}",
            flush=True,
        )
    print(
        f"selected_development_threshold={selected_threshold:.1f}; "
        f"selection_mode={selection['selection_mode']}; "
        f"all_development_gates_met={selection['development_all_gates_met']}",
        flush=True,
    )
    print_holdout_tables(holdout)
    print("\n=== HOLDOUT WILSON 95% GATES ===", flush=True)
    for config_name in HOLDOUT_CONFIG_NAMES:
        print(
            f"{config_name}: gates={holdout_gates[config_name]}, "
            f"final_pass={holdout_final_gates[config_name]}",
            flush=True,
        )
    print(f"artifact={output}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trials", type=int, default=TRIALS_PER_CASE)
    parser.add_argument("--holdout-trials", type=int, default=TRIALS_PER_CASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.dev_trials, args.holdout_trials, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
