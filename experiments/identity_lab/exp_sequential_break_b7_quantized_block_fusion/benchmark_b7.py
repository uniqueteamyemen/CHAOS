"""B-v7 development calibration and pristine 11M holdout comparison."""
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
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import (
    PearsonSpearmanFixedGateEngineB6,
)
from experiments.identity_lab.exp_sequential_break_b7_quantized_block_fusion.engine_b7 import (
    QuantizedBlockFusionEngineB7,
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
DEV_SEED_BASE = 10_000_000
HOLDOUT_SEED_BASE = 11_000_000
TRIALS_PER_CASE = 500
C_SUP_GRID = (1.05, 1.15, 1.25)
Z_BLOCK_GRID = (1.8, 2.0, 2.2)
FPR_LIMIT = 5.0
SENSITIVITY_TARGET = 93.0
B6A_REFERENCE_THRESHOLD = 85.0
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b7_quantized_block_fusion_comparison.json"
)
DEV_CONFIGS = tuple(
    (f"c_sup={c_sup:.2f}|z_block={z_block:.1f}", c_sup, z_block)
    for c_sup in C_SUP_GRID
    for z_block in Z_BLOCK_GRID
)
HOLDOUT_CONFIGS = ("B-v7_selected", "B-v6a_pearson")


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
    return [
        max(0.0, center - half),
        min(1.0, center + half),
    ]


def rate(successes: int, trials: int) -> dict[str, Any]:
    lower, upper = wilson(successes, trials)
    return {
        "sequences": int(successes),
        "rate_pct": round(100.0 * successes / trials, 2),
        "wilson95_pct": [
            round(100.0 * lower, 2),
            round(100.0 * upper, 2),
        ],
    }


def make_engine(config_name: str, c_sup: float | None = None, z_block: float | None = None):
    if config_name == "B-v6a_pearson":
        return PearsonSpearmanFixedGateEngineB6(
            quiet_end=40,
            window_size=12,
            anomaly_z_thresh=3.8,
            winsor_cap=1.8,
            break_percent_thresh=B6A_REFERENCE_THRESHOLD,
            resolution_horizon=14,
            return_to_baseline_z=1.5,
            persistence_z_thresh=1.45,
            correlation_method="pearson",
        )
    if config_name == "B-v7_selected":
        if c_sup is None or z_block is None:
            raise ValueError("selected_B7_parameters_required")
    return QuantizedBlockFusionEngineB7(
        quiet_end=40,
        window_size=12,
        series_length=140,
        onset=65,
        resolution_horizon=14,
        anomaly_z_thresh=3.8,
        c_sup=float(c_sup),
        z_block=float(z_block),
        epoch_z_threshold=1.25,
        quantized_mean_min=1.15,
        return_to_baseline_z=1.5,
    )


def classify(result: dict[str, Any], shift: float) -> dict[str, Any]:
    breaks = list(result["structural_breaks"])
    transients = list(result["transient_anomalies"])
    unresolved = list(result["unresolved_alerts"])

    pre_structural: list[dict[str, Any]] = []
    pre_transient: list[dict[str, Any]] = []
    pre_unresolved: list[dict[str, Any]] = []
    wrong_direction: list[dict[str, Any]] = []
    delay = None

    if shift == 0.0:
        # For null and variance-jump cases, any structural break is false.
        structural_metric = bool(breaks)
    else:
        expected_direction = 1 if shift > 0 else -1
        pre_structural = [
            event for event in breaks
            if int(event["detection_time"]) < ONSET
        ]
        post = [
            event for event in breaks
            if int(event["detection_time"]) >= ONSET
        ]
        correct = [
            event for event in post
            if int(event["direction"]) == expected_direction
        ]
        wrong_direction = [
            event for event in post
            if int(event["direction"]) != expected_direction
        ]
        first_correct = (
            min(correct, key=lambda event: int(event["detection_time"]))
            if correct else None
        )
        structural_metric = first_correct is not None
        if first_correct is not None:
            delay = int(first_correct["detection_time"]) - ONSET
        pre_transient = [
            event for event in transients if int(event["time"]) < ONSET
        ]
        pre_unresolved = [
            event for event in unresolved if int(event["time"]) < ONSET
        ]

    life = result["pending_lifecycle"]
    terminal = (
        int(life["resolved_structural_count"])
        + int(life["resolved_transient_count"])
        + int(life["unresolved_count"])
    )
    return {
        "structural": bool(structural_metric),
        "any_structural": bool(breaks),
        "transient": bool(transients),
        "unresolved": bool(unresolved),
        "combined": bool(breaks or transients or unresolved),
        "wrong_direction": bool(wrong_direction),
        "pre_structural": bool(pre_structural),
        "pre_transient": bool(pre_transient),
        "pre_unresolved": bool(pre_unresolved),
        "pre_combined": bool(pre_structural or pre_transient or pre_unresolved),
        "delay": delay,
        "event_totals": {
            "structural": len(breaks),
            "transient": len(transients),
            "unresolved": len(unresolved),
            "pending_opened": int(life["opened_count"]),
            "pending_resolved_structural": int(life["resolved_structural_count"]),
            "pending_resolved_transient": int(life["resolved_transient_count"]),
            "pending_unresolved": int(life["unresolved_count"]),
        },
        "lifecycle_ok": bool(life["accounting_complete"]) and int(
            life["opened_count"]
        ) == terminal,
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
        "event_totals": {
            "structural": 0,
            "transient": 0,
            "unresolved": 0,
            "pending_opened": 0,
            "pending_resolved_structural": 0,
            "pending_resolved_transient": 0,
            "pending_unresolved": 0,
        },
    }


def accumulate(counts: dict[str, Any], measurement: dict[str, Any]) -> None:
    for key in (
        "structural",
        "any_structural",
        "transient",
        "unresolved",
        "combined",
        "wrong_direction",
        "pre_structural",
        "pre_transient",
        "pre_unresolved",
        "pre_combined",
    ):
        counts[key] += int(measurement[key])
    if measurement["delay"] is not None:
        counts["delays"].append(int(measurement["delay"]))
    counts["lifecycle_ok"] = (
        counts["lifecycle_ok"] and bool(measurement["lifecycle_ok"])
    )
    for key, value in measurement["event_totals"].items():
        counts["event_totals"][key] += int(value)


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
        "event_totals": counts["event_totals"],
        "pending_lifecycle_accounting_complete": counts["lifecycle_ok"],
    }


def summarize_configuration(
    case_counts: dict[str, dict[str, Any]],
    trials: int,
) -> dict[str, Any]:
    rows = {
        name: summarize_case(shift, variance_jump, case_counts[name], trials)
        for name, _distribution, _rho, variance_jump, shift in CASES
    }
    nonlevel = [
        row for row in rows.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_null = [
        row for row in rows.values() if row["scenario_type"] == "pure_null"
    ]
    shifts = [
        row for row in rows.values() if row["scenario_type"] == "level_shift"
    ]
    worst_structural = max(
        row["structural_rate"]["rate_pct"] for row in nonlevel
    )
    worst_combined = max(
        row["combined_any_alert_rate"]["rate_pct"] for row in pure_null
    )
    worst_pre_onset = max(
        row["pre_onset_combined_rate"]["rate_pct"] for row in shifts
    )
    sensitivity = round(
        statistics.mean(
            row["structural_rate"]["rate_pct"] for row in shifts
        ),
        2,
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
    configurations: list[tuple[str, Any]],
    trials: int,
    stage_name: str,
) -> dict[str, Any]:
    engines = {name: factory() for name, factory in configurations}
    counters = {
        config_name: {case[0]: empty_counts() for case in CASES}
        for config_name in engines
    }
    for case_index, (case_name, distribution, serial_rho, var_jump, shift) in enumerate(CASES):
        for trial_index in range(trials):
            seed = seed_base + case_index * 10_000 + trial_index
            series = generate_series(
                np.random.default_rng(seed),
                dist=distribution,
                rho=serial_rho,
                var_jump=var_jump,
                shift_sigma=shift,
                n=N,
                onset=ONSET,
            )
            # Exactly the same generated sequence is evaluated by each engine.
            for config_name, engine in engines.items():
                result = engine.analyze(series)
                accumulate(
                    counters[config_name][case_name],
                    classify(result, shift),
                )
    summaries = {
        config_name: summarize_configuration(counters[config_name], trials)
        for config_name in engines
    }
    return {
        "stage": stage_name,
        "seed_base": seed_base,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "generated_series_count": len(CASES) * trials,
        "configuration_evaluations": len(CASES) * trials * len(engines),
        "same_generated_series_for_all_configurations": True,
        "models": summaries,
    }


def calibration_score(summary: dict[str, Any]) -> dict[str, Any]:
    structural = float(summary["worst_structural_fpr_nonlevel_pct"])
    combined = float(summary["worst_combined_fpr_pure_null_pct"])
    pre_onset = float(summary["worst_pre_onset_combined_pct"])
    values = (structural, combined, pre_onset)
    failures = sum(value > FPR_LIMIT for value in values)
    excess = sum(max(0.0, value - FPR_LIMIT) for value in values)
    return {
        "fpr_gate_failures": int(failures),
        "fpr_excess_percentage_points": round(excess, 4),
        "worst_structural_fpr_nonlevel_pct": structural,
        "worst_combined_fpr_pure_null_pct": combined,
        "worst_pre_onset_combined_pct": pre_onset,
        "mean_directional_sensitivity_pct": float(
            summary["mean_directional_sensitivity_pct"]
        ),
        "all_fpr_point_gates_passed": failures == 0,
    }


def select_parameters(
    development: dict[str, Any],
) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    for config_name, c_sup, z_block in DEV_CONFIGS:
        score = calibration_score(development["models"][config_name])
        scored.append(
            {
                "configuration": config_name,
                "c_sup": c_sup,
                "z_block": z_block,
                **score,
            }
        )
    # Pre-registered lexicographic objective:
    # 1) minimize failed FPR ceilings, 2) minimize total FPR excess,
    # 3) maximize sensitivity, 4) prefer stricter/higher thresholds on a tie.
    ranked = sorted(
        scored,
        key=lambda item: (
            item["fpr_gate_failures"],
            item["fpr_excess_percentage_points"],
            -item["mean_directional_sensitivity_pct"],
            -item["c_sup"],
            -item["z_block"],
        ),
    )
    selected = ranked[0]
    return {
        "selected_c_sup": float(selected["c_sup"]),
        "selected_z_block": float(selected["z_block"]),
        "selected_configuration": selected["configuration"],
        "selected_score": selected,
        "all_candidates": scored,
        "selection_order": [
            "minimize_number_of_FPR_gates_exceeding_5_percent",
            "minimize_sum_of_FPR_percentage_point_excess_above_5",
            "maximize_mean_directional_sensitivity",
            "prefer_higher_c_sup_then_higher_z_block_on_exact_tie",
        ],
        "development_all_fpr_gates_passed": bool(
            selected["all_fpr_point_gates_passed"]
        ),
        "holdout_used_for_parameter_selection": False,
    }


def confidence_gates(summary: dict[str, Any]) -> dict[str, bool]:
    rows = summary["cases"]
    nonlevel = [
        row for row in rows.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_null = [
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
            for row in pure_null
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


def ranges_for_seed(seed_base: int, trials: int) -> dict[str, list[int]]:
    return {
        case[0]: [
            seed_base + index * 10_000,
            seed_base + index * 10_000 + trials - 1,
        ]
        for index, case in enumerate(CASES)
    }


def ranges_are_disjoint(
    development: dict[str, list[int]],
    holdout: dict[str, list[int]],
) -> bool:
    return all(
        dev_end < hold_start or hold_end < dev_start
        for dev_start, dev_end in development.values()
        for hold_start, hold_end in holdout.values()
    )


def print_summary_table(
    title: str,
    summaries: dict[str, dict[str, Any]],
) -> None:
    print(f"\\n=== {title} ===", flush=True)
    print(
        "configuration | worst structural FPR | worst pure-null Combined | "
        "worst pre-onset Combined | mean sensitivity | lifecycle",
        flush=True,
    )
    for name, summary in summaries.items():
        print(
            f"{name} | {summary['worst_structural_fpr_nonlevel_pct']:.2f}% | "
            f"{summary['worst_combined_fpr_pure_null_pct']:.2f}% | "
            f"{summary['worst_pre_onset_combined_pct']:.2f}% | "
            f"{summary['mean_directional_sensitivity_pct']:.2f}% | "
            f"{summary['lifecycle_accounting_complete']}",
            flush=True,
        )


def print_holdout_detail(holdout: dict[str, Any]) -> None:
    def fmt(metric: dict[str, Any]) -> str:
        low, high = metric["wilson95_pct"]
        return f"{metric['rate_pct']:.2f} [{low:.2f},{high:.2f}]"

    print(
        "\\n=== 11M HOLDOUT CASE DETAIL: rate_pct [Wilson 95% lower, upper] ===",
        flush=True,
    )
    print(
        "case | configuration | structural | transient | unresolved | "
        "combined | pre-onset combined | directional sensitivity",
        flush=True,
    )
    for case_name, *_ in CASES:
        for config_name, model in holdout["models"].items():
            row = model["cases"][case_name]
            directional = (
                fmt(row["structural_rate"])
                if row["scenario_type"] == "level_shift"
                else "n/a"
            )
            print(
                f"{case_name} | {config_name} | "
                f"{fmt(row['structural_rate'])} | "
                f"{fmt(row['transient_alert_rate'])} | "
                f"{fmt(row['unresolved_alert_rate'])} | "
                f"{fmt(row['combined_any_alert_rate'])} | "
                f"{fmt(row['pre_onset_combined_rate'])} | {directional}",
                flush=True,
            )


def run(
    dev_trials: int = TRIALS_PER_CASE,
    holdout_trials: int = TRIALS_PER_CASE,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    if dev_trials != TRIALS_PER_CASE or holdout_trials != TRIALS_PER_CASE:
        raise ValueError("B7_requires_exactly_500_trials_per_case")
    if N != 140 or ONSET != 65:
        raise AssertionError("scenario_generator_dimensions_do_not_match_B7_spec")

    dev_configurations = [
        (
            config_name,
            lambda c=c_sup, z=z_block: QuantizedBlockFusionEngineB7(
                quiet_end=40,
                window_size=12,
                series_length=140,
                onset=65,
                resolution_horizon=14,
                anomaly_z_thresh=3.8,
                c_sup=c,
                z_block=z,
                epoch_z_threshold=1.25,
                quantized_mean_min=1.15,
                return_to_baseline_z=1.5,
            ),
        )
        for config_name, c_sup, z_block in DEV_CONFIGS
    ]

    started = time.perf_counter()
    development = evaluate_stage(
        DEV_SEED_BASE,
        dev_configurations,
        dev_trials,
        "development_calibration_sweep",
    )
    development_elapsed = round(time.perf_counter() - started, 2)

    # Parameter selection is completed and frozen before 11M data are generated.
    selection = select_parameters(development)
    selected_c_sup = float(selection["selected_c_sup"])
    selected_z_block = float(selection["selected_z_block"])

    holdout_configurations = [
        (
            "B-v7_selected",
            lambda c=selected_c_sup, z=selected_z_block: QuantizedBlockFusionEngineB7(
                quiet_end=40,
                window_size=12,
                series_length=140,
                onset=65,
                resolution_horizon=14,
                anomaly_z_thresh=3.8,
                c_sup=c,
                z_block=z,
                epoch_z_threshold=1.25,
                quantized_mean_min=1.15,
                return_to_baseline_z=1.5,
            ),
        ),
        (
            "B-v6a_pearson",
            lambda: PearsonSpearmanFixedGateEngineB6(
                quiet_end=40,
                window_size=12,
                anomaly_z_thresh=3.8,
                winsor_cap=1.8,
                break_percent_thresh=B6A_REFERENCE_THRESHOLD,
                resolution_horizon=14,
                return_to_baseline_z=1.5,
                persistence_z_thresh=1.45,
                correlation_method="pearson",
            ),
        ),
    ]

    started = time.perf_counter()
    holdout = evaluate_stage(
        HOLDOUT_SEED_BASE,
        holdout_configurations,
        holdout_trials,
        "pristine_unseen_holdout",
    )
    holdout_elapsed = round(time.perf_counter() - started, 2)

    development_ranges = ranges_for_seed(DEV_SEED_BASE, dev_trials)
    holdout_ranges = ranges_for_seed(HOLDOUT_SEED_BASE, holdout_trials)
    disjoint = ranges_are_disjoint(development_ranges, holdout_ranges)
    if not disjoint:
        raise AssertionError("B7_development_and_holdout_seed_ranges_overlap")

    gates = {
        name: confidence_gates(summary)
        for name, summary in holdout["models"].items()
    }
    final_gates = {
        name: all(values.values()) for name, values in gates.items()
    }

    report = {
        "experiment": "B-v7 Quantized Block Fusion Engine",
        "branch": "experiment/b7-quantized-block-fusion",
        "parent_branch": "experiment/b6-spearman-ablation-documented",
        "parent_commit_B6": "97220248dea1f359c366540a58d245461556c21e",
        "parameter_provenance": {
            "quiet_reference": {
                "quiet_end": 40,
                "source": "fixed experimental contract",
            },
            "point_scale": {
                "formula": "max(1.4826 * median(abs(quiet - median(quiet))), 1e-6)",
                "source": "robust MAD scale specified for B-v7",
            },
            "difference_scale_baseline": {
                "formula": "max(1.4826 * median(abs(diff(quiet))) / sqrt(2), 1e-6)",
                "interpretation": (
                    "robust first-difference scale; despite the source label "
                    "Local Variance Ratio, this is not a classical variance estimator"
                ),
            },
            "block_envelope": {
                "window_size": 12,
                "overlapping_block_count": 29,
                "block_scale_formula": "max(1.4826 * median(abs(block_median - baseline_center)), 1e-6)",
                "block_supremum_formula": "percentile_95(abs(block_median - baseline_center))",
                "percentile_method": "NumPy default linear percentile",
                "source": "B-v7 empirical block envelope hypothesis",
                "caveat": (
                    "29 overlapping medians are dependent and do not constitute "
                    "29 independent observations; the envelope is a short-sample "
                    "empirical guard, not a population-level 95% tolerance bound"
                ),
            },
            "variance_adaptation": {
                "formula": "max(1.0, local_robust_difference_scale / baseline_robust_difference_scale)",
                "scaling": "point_scale, block_scale, and block_supremum are multiplied by this factor",
                "name_correction": "Robust Difference-Scale Ratio",
            },
            "pending_gate": {
                "value": "three adjacent point z-scores, all abs(z)>3.8 and same sign",
                "source": "B-v6 fixed three-point pending gate",
                "duplicate_suppression": "no new pending if any prior pending is aged 0..2 steps",
            },
            "structural_gates": {
                "amplitude": {
                    "c_sup_grid": list(C_SUP_GRID),
                    "z_block_grid": list(Z_BLOCK_GRID),
                    "rule": "abs(window_median - baseline_center) > c_sup * block_supremum_t AND abs(displacement) / block_scale_t > z_block",
                    "algebraic_note": (
                        "Because both block thresholds share the same variance_ratio "
                        "multiplier, this pair of inequalities reduces to a single "
                        "effective amplitude threshold using max(c_sup*B_sup, z_block*sigma_block)."
                    ),
                },
                "three_sub_epochs": {
                    "partition": "window[0:4], window[4:8], window[8:12]",
                    "rule": "all three medians have the same sign as direction and abs(deviation)/block_scale_t > 1.25",
                },
                "quantized_consistency": {
                    "rule": "q=clip(rint(z), -2, +2); direction * mean(q) >= 1.15",
                    "rounding": "NumPy rint: nearest, ties-to-even",
                },
                "combination": "strict AND across amplitude_gate, epoch_position_gate, and quantized_gate",
            },
            "structural_direction": "sign(median(window) - baseline_center)",
            "latch_reset": (
                "release direction latch when abs(window_median - baseline_center) / block_scale_t < 0.40"
            ),
            "transient_resolution": {
                "rule": (
                    "resolve transient as soon as an observed point within age 1..14 "
                    "returns with abs(value-baseline_center)/point_scale < 1.5"
                ),
                "expiry_without_return": (
                    "terminal UNRESOLVED_HORIZON_EXPIRED at age 14; no inferred transient"
                ),
            },
        },
        "fixed_specification": {
            "quiet_end": 40,
            "window_size": 12,
            "series_length": 140,
            "onset_index_zero_based": 65,
            "resolution_horizon": 14,
            "anomaly_z_thresh": 3.8,
            "epoch_z_threshold": 1.25,
            "quantized_mean_min": 1.15,
            "return_to_baseline_z": 1.5,
            "lifecycle_invariant": (
                "pending_opened == resolved_structural + resolved_transient + unresolved"
            ),
            "combined_definition": (
                "union of any structural alert (including correct/wrong/pre-onset), "
                "any resolved transient, or any unresolved alert"
            ),
        },
        "development_calibration": {
            "seed_base": DEV_SEED_BASE,
            "seed_ranges": development_ranges,
            "trials_per_case": dev_trials,
            "generated_series_count": development["generated_series_count"],
            "configuration_evaluations": development["configuration_evaluations"],
            "c_sup_grid": list(C_SUP_GRID),
            "z_block_grid": list(Z_BLOCK_GRID),
            "selection_rule": (
                "minimize FPR gate failures; then sum of FPR excess above 5%; "
                "then maximize sensitivity; exact tie prefers higher c_sup, then z_block"
            ),
            "selection": selection,
            "elapsed_seconds": development_elapsed,
        },
        "development_results": development,
        "holdout_verification": {
            "seed_base": HOLDOUT_SEED_BASE,
            "seed_ranges": holdout_ranges,
            "trials_per_case": holdout_trials,
            "generated_series_count": holdout["generated_series_count"],
            "configuration_evaluations": holdout["configuration_evaluations"],
            "seed_blocks_disjoint": disjoint,
            "selected_c_sup": selected_c_sup,
            "selected_z_block": selected_z_block,
            "B6a_pearson_reference_threshold": B6A_REFERENCE_THRESHOLD,
            "threshold_frozen_before_holdout": True,
            "elapsed_seconds": holdout_elapsed,
            "models": holdout["models"],
            "confidence_gates": gates,
            "final_gates": final_gates,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print_summary_table("B-v7 DEVELOPMENT CALIBRATION", development["models"])
    print(
        "\\nSelected B-v7 parameters: "
        f"c_sup={selected_c_sup:.2f}, z_block={selected_z_block:.1f}; "
        f"all development FPR gates passed="
        f"{selection['development_all_fpr_gates_passed']}",
        flush=True,
    )
    print_holdout_detail(holdout)
    print_summary_table("11M HOLDOUT AGGREGATES", holdout["models"])
    print("\\n=== 11M HOLDOUT WILSON 95% GATES ===", flush=True)
    for name in HOLDOUT_CONFIGS:
        print(
            f"{name}: gates={gates[name]}, final_pass={final_gates[name]}",
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
