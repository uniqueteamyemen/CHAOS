"""Paired, eight-case B-v3.1 vs minimal B-v3.2 calibration retest.

The case definitions, generator, seed scheme, sequence accounting, and B-v3.1
reference engine are imported unchanged from the frozen B-v3.1 audit module.
Only the candidate engine parameters vary in the development sweep.
"""
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
    AuditedSequentialBreakEngineB3,
    N,
    ONSET,
    generate_series,
)
from experiments.identity_lab.exp_sequential_break_b3_2_retest.engine_b3_2_retest import (
    CalibratedSequentialBreakEngineB32,
)

THRESHOLDS = (4.5, 5.0, 5.5, 6.0)
RHO_MODES = ("raw", "small_sample_adjusted")
DEV_SEED_BASE = 4_000_000
HOLDOUT_SEED_BASE = 5_000_000
DEFAULT_TRIALS = 500
FALSE_ALARM_BUDGET_PCT = 5.0
RESOLUTION_HORIZON = 14
RETURN_TO_BASELINE_Z = 1.5
BREAK_PERCENT_THRESH = 85.0

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

OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b3_2_minimal_retest.json"
)


def wilson_interval(successes: int, trials: int) -> list[float]:
    if trials <= 0:
        raise ValueError("trials_must_be_positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes_must_be_between_zero_and_trials")
    z = 1.959963984540054
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = z * math.sqrt(
        p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)
    ) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def rate_block(count: int, trials: int) -> dict[str, Any]:
    low, high = wilson_interval(count, trials)
    return {
        "sequences": count,
        "rate_pct": round(count / trials * 100.0, 2),
        "wilson95_pct": [round(low * 100.0, 2), round(high * 100.0, 2)],
    }


def classify_result(
    result: dict[str, Any], *, shift_sigma: float, onset: int = ONSET
) -> dict[str, Any]:
    """Use the original B-v3.1 sequence-level meanings without narrowing Combined."""
    breaks = list(result["structural_breaks"])
    transients = list(result["transient_anomalies"])
    unresolved = list(result["unresolved_alerts"])

    if shift_sigma == 0.0:
        structural_metric = bool(breaks)
        correct_structural: list[dict[str, Any]] = []
        wrong_structural: list[dict[str, Any]] = []
        pre_structural: list[dict[str, Any]] = []
        delay = None
    else:
        expected_direction = 1 if shift_sigma > 0 else -1
        pre_structural = [
            b for b in breaks if int(b["detection_time"]) < onset
        ]
        post_structural = [
            b for b in breaks if int(b["detection_time"]) >= onset
        ]
        correct_structural = [
            b for b in post_structural
            if int(b["direction"]) == expected_direction
        ]
        wrong_structural = [
            b for b in post_structural
            if int(b["direction"]) != expected_direction
        ]
        earliest = (
            min(correct_structural, key=lambda b: int(b["detection_time"]))
            if correct_structural else None
        )
        delay = (
            int(earliest["detection_time"]) - onset
            if earliest is not None else None
        )
        structural_metric = bool(correct_structural)

    pre_transient = (
        [a for a in transients if int(a["time"]) < onset]
        if shift_sigma != 0.0 else []
    )
    pre_unresolved = (
        [a for a in unresolved if int(a["time"]) < onset]
        if shift_sigma != 0.0 else []
    )

    return {
        "structural_metric": structural_metric,
        "any_structural_alert": bool(breaks),
        "transient_alert": bool(transients),
        "unresolved_alert": bool(unresolved),
        "combined_any_alert": bool(breaks or transients or unresolved),
        "correct_structural_sequence": bool(correct_structural),
        "wrong_direction_structural_sequence": bool(wrong_structural),
        "pre_onset_structural_sequence": bool(pre_structural),
        "pre_onset_transient_sequence": bool(pre_transient),
        "pre_onset_unresolved_sequence": bool(pre_unresolved),
        "pre_onset_combined_sequence": bool(
            pre_structural or pre_transient or pre_unresolved
        ),
        "detection_delay": delay,
    }


def empty_counts() -> dict[str, Any]:
    return {
        "structural": 0,
        "transient": 0,
        "unresolved": 0,
        "combined": 0,
        "wrong_direction": 0,
        "pre_structural": 0,
        "pre_transient": 0,
        "pre_unresolved": 0,
        "pre_combined": 0,
        "correct": 0,
        "delays": [],
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


def add_trial(
    counts: dict[str, Any],
    result: dict[str, Any],
    metrics: dict[str, Any],
) -> bool:
    counts["structural"] += int(metrics["structural_metric"])
    counts["transient"] += int(metrics["transient_alert"])
    counts["unresolved"] += int(metrics["unresolved_alert"])
    counts["combined"] += int(metrics["combined_any_alert"])
    counts["wrong_direction"] += int(
        metrics["wrong_direction_structural_sequence"]
    )
    counts["pre_structural"] += int(metrics["pre_onset_structural_sequence"])
    counts["pre_transient"] += int(metrics["pre_onset_transient_sequence"])
    counts["pre_unresolved"] += int(metrics["pre_onset_unresolved_sequence"])
    counts["pre_combined"] += int(metrics["pre_onset_combined_sequence"])
    counts["correct"] += int(metrics["correct_structural_sequence"])
    if metrics["detection_delay"] is not None:
        counts["delays"].append(metrics["detection_delay"])

    lifecycle = result["pending_lifecycle"]
    event_map = {
        "structural": "resolved_structural_count",
        "transient": "resolved_transient_count",
        "unresolved": "unresolved_count",
    }
    counts["events"]["structural"] += len(result["structural_breaks"])
    counts["events"]["transient"] += len(result["transient_anomalies"])
    counts["events"]["unresolved"] += len(result["unresolved_alerts"])
    counts["events"]["pending_opened"] += int(lifecycle["opened_count"])
    counts["events"]["pending_resolved_structural"] += int(
        lifecycle["resolved_structural_count"]
    )
    counts["events"]["pending_resolved_transient"] += int(
        lifecycle["resolved_transient_count"]
    )
    counts["events"]["pending_unresolved"] += int(lifecycle["unresolved_count"])

    terminal = sum(int(lifecycle[event]) for event in event_map.values())
    return (
        bool(lifecycle["accounting_complete"])
        and int(lifecycle["opened_count"]) == terminal
    )


def summarize_counts(
    counts: dict[str, Any], *, trials: int, shift_sigma: float,
    var_jump: bool = False,
) -> dict[str, Any]:
    scenario_type = (
        "level_shift" if shift_sigma != 0.0
        else "variance_jump" if var_jump
        else "pure_null"
    )
    return {
        "scenario_type": scenario_type,
        "trials": trials,
        "structural_metric_label": (
            "structural_false_alarm"
            if shift_sigma == 0.0
            else "correct_directional_structural_detection"
        ),
        "structural_rate": rate_block(counts["structural"], trials),
        "transient_alert_rate": rate_block(counts["transient"], trials),
        "unresolved_alert_rate": rate_block(counts["unresolved"], trials),
        "combined_any_alert_rate": rate_block(counts["combined"], trials),
        "wrong_direction_structural_rate": rate_block(
            counts["wrong_direction"], trials
        ),
        "pre_onset_structural_rate": rate_block(
            counts["pre_structural"], trials
        ),
        "pre_onset_transient_rate": rate_block(
            counts["pre_transient"], trials
        ),
        "pre_onset_unresolved_rate": rate_block(
            counts["pre_unresolved"], trials
        ),
        "pre_onset_combined_rate": rate_block(
            counts["pre_combined"], trials
        ),
        "median_correct_detection_delay": (
            round(float(statistics.median(counts["delays"])), 2)
            if counts["delays"] else None
        ),
        "event_totals": counts["events"],
        "pending_lifecycle_accounting_complete": (
            counts["events"]["pending_opened"]
            == counts["events"]["pending_resolved_structural"]
            + counts["events"]["pending_resolved_transient"]
            + counts["events"]["pending_unresolved"]
        ),
    }


def evaluate_config(
    *,
    anomaly_z_thresh: float,
    rho_mode: str,
    seed_base: int,
    trials: int,
    compare_b3_1: bool = False,
    print_cases: bool = False,
) -> dict[str, Any]:
    if rho_mode not in RHO_MODES:
        raise ValueError(f"unsupported_rho_mode:{rho_mode}")

    candidate = CalibratedSequentialBreakEngineB32(
        anomaly_z_thresh=anomaly_z_thresh,
        break_percent_thresh=BREAK_PERCENT_THRESH,
        resolution_horizon=RESOLUTION_HORIZON,
        rho_bias_correction=(rho_mode == "small_sample_adjusted"),
        return_to_baseline_z=RETURN_TO_BASELINE_Z,
    )
    baseline = (
        AuditedSequentialBreakEngineB3(
            anomaly_z_thresh=3.2,
            break_percent_thresh=BREAK_PERCENT_THRESH,
            resolution_horizon=6,
        )
        if compare_b3_1 else None
    )

    cases: dict[str, Any] = {}
    baseline_cases: dict[str, Any] = {}
    lifecycle_complete = True
    baseline_lifecycle_complete = True

    for case_index, (name, dist, rho, var_jump, shift) in enumerate(CASES):
        candidate_counts = empty_counts()
        baseline_counts = empty_counts() if baseline is not None else None

        for trial in range(trials):
            seed = seed_base + case_index * 10_000 + trial
            series = generate_series(
                np.random.default_rng(seed),
                dist=dist,
                rho=rho,
                var_jump=var_jump,
                shift_sigma=shift,
                n=N,
                onset=ONSET,
            )

            candidate_result = candidate.analyze(series)
            candidate_metrics = classify_result(
                candidate_result, shift_sigma=shift
            )
            lifecycle_complete = (
                add_trial(candidate_counts, candidate_result, candidate_metrics)
                and lifecycle_complete
            )

            if baseline is not None and baseline_counts is not None:
                baseline_result = baseline.analyze(series)
                baseline_metrics = classify_result(
                    baseline_result, shift_sigma=shift
                )
                baseline_lifecycle_complete = (
                    add_trial(baseline_counts, baseline_result, baseline_metrics)
                    and baseline_lifecycle_complete
                )

        cases[name] = summarize_counts(
            candidate_counts, trials=trials, shift_sigma=shift, var_jump=var_jump
        )
        if baseline_counts is not None:
            baseline_cases[name] = summarize_counts(
                baseline_counts, trials=trials, shift_sigma=shift, var_jump=var_jump
            )
        if print_cases:
            row = cases[name]
            print(
                f"{name:22s} "
                f"Struct={row['structural_rate']['rate_pct']:5.1f}% "
                f"Trans={row['transient_alert_rate']['rate_pct']:5.1f}% "
                f"Unres={row['unresolved_alert_rate']['rate_pct']:5.1f}% "
                f"Combined={row['combined_any_alert_rate']['rate_pct']:5.1f}%",
                flush=True,
            )

    # The supplied eight-case design labels structural detections in both
    # pure-null and variance-jump cases as structural false alarms. Shift cases
    # are excluded from this FPR gate and evaluated by directional sensitivity.
    structural_rows = [
        row for row in cases.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_null_rows = [
        row for row in cases.values() if row["scenario_type"] == "pure_null"
    ]
    shift_rows = [cases["pos_shift_3.0s"], cases["neg_shift_3.0s"]]

    worst_structural = max(
        row["structural_rate"]["rate_pct"] for row in structural_rows
    )
    worst_pure_null_combined = max(
        row["combined_any_alert_rate"]["rate_pct"] for row in pure_null_rows
    )
    worst_pre_onset_combined = max(
        row["pre_onset_combined_rate"]["rate_pct"] for row in shift_rows
    )
    mean_sensitivity = round(
        float(statistics.mean(
            row["structural_rate"]["rate_pct"] for row in shift_rows
        )),
        4,
    )

    result: dict[str, Any] = {
        "anomaly_z_thresh": anomaly_z_thresh,
        "rho_mode": rho_mode,
        "rho_bias_correction_enabled": rho_mode == "small_sample_adjusted",
        "resolution_horizon": RESOLUTION_HORIZON,
        "return_to_baseline_z": RETURN_TO_BASELINE_Z,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "worst_structural_fpr_all_non_level_cases_pct": round(
            worst_structural, 2
        ),
        "worst_combined_fpr_pure_null_pct": round(
            worst_pure_null_combined, 2
        ),
        "worst_pre_onset_combined_fpr_level_shift_pct": round(
            worst_pre_onset_combined, 2
        ),
        "mean_directional_sensitivity_level_shift_pct": mean_sensitivity,
        "lifecycle_accounting_complete": lifecycle_complete,
        "dev_gate": {
            "structural_fpr_all_non_level_cases_passed": (
                worst_structural <= FALSE_ALARM_BUDGET_PCT
            ),
            "combined_pure_null_fpr_passed": (
                worst_pure_null_combined <= FALSE_ALARM_BUDGET_PCT
            ),
            "pre_onset_combined_fpr_passed": (
                worst_pre_onset_combined <= FALSE_ALARM_BUDGET_PCT
            ),
            "lifecycle_accounting_passed": lifecycle_complete,
        },
        "cases": cases,
    }

    if baseline is not None:
        result["b3_1_reference"] = {
            "candidate": "AuditedSequentialBreakEngineB3",
            "anomaly_z_thresh": 3.2,
            "resolution_horizon": 6,
            "lifecycle_accounting_complete": baseline_lifecycle_complete,
            "cases": baseline_cases,
        }
        deltas = {}
        for case_name, candidate_row in cases.items():
            base_row = baseline_cases[case_name]
            deltas[case_name] = {
                metric: round(
                    candidate_row[metric]["rate_pct"]
                    - base_row[metric]["rate_pct"],
                    2,
                )
                for metric in (
                    "structural_rate",
                    "transient_alert_rate",
                    "unresolved_alert_rate",
                    "combined_any_alert_rate",
                )
            }
        result["paired_delta_vs_b3_1_percentage_points"] = deltas

    return result


def select_dev_candidate(sweep: list[dict[str, Any]]) -> dict[str, Any]:
    def rank(row: dict[str, Any]) -> tuple[Any, ...]:
        gates = list(row["dev_gate"].values())
        failed = sum(not value for value in gates)
        ratios = [
            row["worst_structural_fpr_all_non_level_cases_pct"],
            row["worst_combined_fpr_pure_null_pct"],
            row["worst_pre_onset_combined_fpr_level_shift_pct"],
        ]
        max_ratio = max(ratios) / FALSE_ALARM_BUDGET_PCT
        excess = sum(
            max(0.0, value / FALSE_ALARM_BUDGET_PCT - 1.0)
            for value in ratios
        )
        return (
            failed,
            round(max_ratio, 8),
            round(excess, 8),
            -row["mean_directional_sensitivity_level_shift_pct"],
            0 if row["rho_mode"] == "small_sample_adjusted" else 1,
            row["anomaly_z_thresh"],
        )

    return min(sweep, key=rank)


def holdout_gate(holdout: dict[str, Any]) -> dict[str, bool]:
    cases = holdout["cases"]
    non_level = [
        row for row in cases.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_null = [
        row for row in cases.values() if row["scenario_type"] == "pure_null"
    ]
    shifts = [cases["pos_shift_3.0s"], cases["neg_shift_3.0s"]]

    checks = {
        "structural_point_all_non_level": all(
            row["structural_rate"]["rate_pct"] <= FALSE_ALARM_BUDGET_PCT
            for row in non_level
        ),
        "structural_wilson_upper95_all_non_level": all(
            row["structural_rate"]["wilson95_pct"][1]
            <= FALSE_ALARM_BUDGET_PCT for row in non_level
        ),
        "combined_pure_null_point": all(
            row["combined_any_alert_rate"]["rate_pct"]
            <= FALSE_ALARM_BUDGET_PCT for row in pure_null
        ),
        "combined_pure_null_wilson_upper95": all(
            row["combined_any_alert_rate"]["wilson95_pct"][1]
            <= FALSE_ALARM_BUDGET_PCT for row in pure_null
        ),
        "pre_onset_combined_point": all(
            row["pre_onset_combined_rate"]["rate_pct"]
            <= FALSE_ALARM_BUDGET_PCT for row in shifts
        ),
        "pre_onset_combined_wilson_upper95": all(
            row["pre_onset_combined_rate"]["wilson95_pct"][1]
            <= FALSE_ALARM_BUDGET_PCT for row in shifts
        ),
        "lifecycle_accounting": bool(holdout["lifecycle_accounting_complete"]),
    }
    return checks


def run_calibration(
    *, dev_trials: int = DEFAULT_TRIALS,
    holdout_trials: int = DEFAULT_TRIALS,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    if dev_trials < 100 or holdout_trials < 100:
        raise ValueError("dev_and_holdout_trials_must_each_be_at_least_100")

    report: dict[str, Any] = {
        "experiment": "sequential_break_engine_b3_2_minimal_retest",
        "candidate": "CalibratedSequentialBreakEngineB32",
        "baseline": "sequential_break_engine_b3_1_audit_complete",
        "base_commit": "a07b29315d0af7d84e9e07e31ccdda32dac2b570",
        "configuration": {
            "quiet_end": 40,
            "window_size": 12,
            "winsor_cap": 2.5,
            "break_percent_thresh": BREAK_PERCENT_THRESH,
            "resolution_horizon": RESOLUTION_HORIZON,
            "return_to_baseline_z": RETURN_TO_BASELINE_Z,
            "onset_index_zero_based": ONSET,
            "rho_adjustment": (
                "min(0.90, rho_raw + (1 + 3*rho_raw)/quiet_end)"
            ),
            "rho_adjustment_status": (
                "experimental small-sample heuristic; not a validated Kendall correction"
            ),
            "anomaly_z_thresh_sweep": list(THRESHOLDS),
            "rho_modes": list(RHO_MODES),
        },
        "design": {
            "series_length": N,
            "case_count": len(CASES),
            "trials_per_case_dev": dev_trials,
            "trials_per_case_holdout": holdout_trials,
            "case_definitions_unchanged": True,
            "cases": [case[0] for case in CASES],
            "distribution": ["gauss", "t3"],
            "rho_levels": [0.3, 0.7],
            "variance_jump_cases": 2,
            "level_shift_cases": 2,
            "pure_null_cases": 4,
            "dev_seed_base": DEV_SEED_BASE,
            "holdout_seed_base": HOLDOUT_SEED_BASE,
            "seed_scheme": "seed_base + case_index*10000 + trial",
            "combined_definition": (
                "sequence-level union of any structural break (including wrong-direction "
                "or pre-onset), transient anomaly, or unresolved alert"
            ),
            "pending_lifecycle_invariant": (
                "opened = resolved_structural + resolved_transient + unresolved"
            ),
            "false_alarm_budget_pct": FALSE_ALARM_BUDGET_PCT,
        },
        "dev_sweep": [],
        "selected_candidate": None,
        "holdout": None,
        "holdout_status": "NOT_RUN",
        "holdout_gates": None,
        "final_gate_passed": False,
    }

    dev_start = time.perf_counter()
    for rho_mode in RHO_MODES:
        for threshold in THRESHOLDS:
            print(
                f"DEV rho_mode={rho_mode} anomaly_z_thresh={threshold:.1f}",
                flush=True,
            )
            row = evaluate_config(
                anomaly_z_thresh=threshold,
                rho_mode=rho_mode,
                seed_base=DEV_SEED_BASE,
                trials=dev_trials,
                compare_b3_1=False,
                print_cases=False,
            )
            report["dev_sweep"].append(row)
            print(
                "DEV SUMMARY "
                f"threshold={threshold:.1f} rho={rho_mode} "
                f"structural={row['worst_structural_fpr_all_non_level_cases_pct']:.2f}% "
                f"pure_null_combined={row['worst_combined_fpr_pure_null_pct']:.2f}% "
                f"pre_onset_combined={row['worst_pre_onset_combined_fpr_level_shift_pct']:.2f}% "
                f"sensitivity={row['mean_directional_sensitivity_level_shift_pct']:.2f}% "
                f"gate={all(row['dev_gate'].values())}",
                flush=True,
            )

    report["dev_elapsed_seconds"] = round(time.perf_counter() - dev_start, 2)
    selected = select_dev_candidate(report["dev_sweep"])
    report["selected_candidate"] = {
        "anomaly_z_thresh": selected["anomaly_z_thresh"],
        "rho_mode": selected["rho_mode"],
        "rho_bias_correction_enabled": selected["rho_bias_correction_enabled"],
        "resolution_horizon": RESOLUTION_HORIZON,
        "return_to_baseline_z": RETURN_TO_BASELINE_Z,
        "dev_gate_passed": all(selected["dev_gate"].values()),
        "dev_mean_directional_sensitivity_pct": (
            selected["mean_directional_sensitivity_level_shift_pct"]
        ),
    }

    print(
        "HOLDOUT "
        f"threshold={selected['anomaly_z_thresh']:.1f} "
        f"rho_mode={selected['rho_mode']}",
        flush=True,
    )
    holdout = evaluate_config(
        anomaly_z_thresh=float(selected["anomaly_z_thresh"]),
        rho_mode=str(selected["rho_mode"]),
        seed_base=HOLDOUT_SEED_BASE,
        trials=holdout_trials,
        compare_b3_1=True,
        print_cases=True,
    )
    report["holdout"] = holdout
    report["holdout_gates"] = holdout_gate(holdout)
    report["holdout_status"] = (
        "COMPLETED" if report["selected_candidate"]["dev_gate_passed"]
        else "COMPLETED_DIAGNOSTIC_ONLY_DEV_GATE_FAILED"
    )
    report["final_gate_passed"] = (
        report["selected_candidate"]["dev_gate_passed"]
        and all(report["holdout_gates"].values())
        and holdout["b3_1_reference"]["lifecycle_accounting_complete"]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\n=== B-v3.2 MINIMAL RETEST FINAL ===")
    print(f"selected_candidate={report['selected_candidate']}")
    print(f"holdout_status={report['holdout_status']}")
    print(f"holdout_gates={report['holdout_gates']}")
    print(f"final_gate_passed={report['final_gate_passed']}")
    print(f"artifact={output}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--holdout-trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run_calibration(
        dev_trials=args.dev_trials,
        holdout_trials=args.holdout_trials,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
