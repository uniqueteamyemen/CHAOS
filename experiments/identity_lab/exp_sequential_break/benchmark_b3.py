"""Paired dev/holdout calibration for SequentialBreakEngine B-v3.

Instrumentation separates structural-break detections from transient-anomaly
detections. The combined metric counts either channel as an emitted alert.
Transient detections in pure-null cases are false alerts; in variance-jump
cases they are reported separately because the variance regime genuinely changes.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break.b3_engine import SequentialBreakEngineB3


N = 140
ONSET = 65
RHO_LEVELS = (0.3, 0.5, 0.7)
SHIFT_LEVELS = (2.0, 2.5, 3.0)
THRESHOLDS = (78.0, 82.0, 85.0, 88.0, 90.0)
DEV_SEED_BASE = 4_000_000
HOLDOUT_SEED_BASE = 5_000_000
DEFAULT_DEV_TRIALS = 300
DEFAULT_HOLDOUT_TRIALS = 500
FALSE_ALARM_BUDGET = 5.0
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b3_calibration_holdout.json"
)


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for dist in ("gauss", "t3"):
        for rho in RHO_LEVELS:
            cases.append(
                {
                    "name": f"{dist}_r{rho:.1f}_null",
                    "dist": dist,
                    "rho": rho,
                    "var_jump": False,
                    "shift_sigma": 0.0,
                }
            )
            cases.append(
                {
                    "name": f"{dist}_r{rho:.1f}_variance_jump",
                    "dist": dist,
                    "rho": rho,
                    "var_jump": True,
                    "shift_sigma": 0.0,
                }
            )

    for dist in ("gauss", "t3"):
        for rho in RHO_LEVELS:
            for magnitude in SHIFT_LEVELS:
                for sign in (1.0, -1.0):
                    shift = sign * magnitude
                    cases.append(
                        {
                            "name": f"{dist}_r{rho:.1f}_{'pos' if sign > 0 else 'neg'}_{magnitude:.1f}s",
                            "dist": dist,
                            "rho": rho,
                            "var_jump": False,
                            "shift_sigma": shift,
                        }
                    )
    return cases


CASES = build_cases()


def generate_series(
    rng: np.random.Generator,
    *,
    dist: str,
    rho: float,
    var_jump: bool,
    shift_sigma: float,
    n: int = N,
    onset: int = ONSET,
) -> np.ndarray:
    if dist == "t3":
        eps = rng.standard_t(df=3, size=n) / np.sqrt(3.0)
    elif dist == "gauss":
        eps = rng.normal(0.0, 1.0, size=n)
    else:
        raise ValueError(f"unsupported_distribution:{dist}")

    if var_jump:
        eps[onset:] *= 2.0

    x = np.zeros(n, dtype=float)
    x[0] = eps[0]
    innovation_scale = np.sqrt(1.0 - rho**2)
    for t in range(1, n):
        x[t] = rho * x[t - 1] + innovation_scale * eps[t]

    if shift_sigma != 0.0:
        x[onset:] += shift_sigma
    return x


def wilson_interval(successes: int, trials: int) -> list[float]:
    if trials <= 0:
        raise ValueError("trials_must_be_positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes_must_be_between_zero_and_trials")
    z = 1.959963984540054
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
        / denom
    )
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def summarize_trial_alerts(
    result: dict[str, Any], *, boundary: int | None = None
) -> dict[str, Any]:
    """Classify emitted detections without conflating the two alert channels."""
    breaks = list(result.get("structural_breaks", []))
    transients = list(result.get("transient_anomalies", []))
    metrics: dict[str, Any] = {
        "structural_events": len(breaks),
        "structural_sequence": bool(breaks),
        "transient_events": len(transients),
        "transient_sequence": bool(transients),
        "combined_events": len(breaks) + len(transients),
        "combined_sequence": bool(breaks or transients),
        "pre_structural_events": 0,
        "pre_structural_sequence": False,
        "pre_transient_events": 0,
        "pre_transient_sequence": False,
        "pre_combined_events": 0,
        "pre_combined_sequence": False,
        "post_transient_events": 0,
        "post_transient_sequence": False,
    }
    if boundary is not None:
        pre_breaks = [b for b in breaks if int(b["detection_time"]) < boundary]
        pre_transients = [a for a in transients if int(a["time"]) < boundary]
        post_transients = [a for a in transients if int(a["time"]) >= boundary]
        metrics.update(
            {
                "pre_structural_events": len(pre_breaks),
                "pre_structural_sequence": bool(pre_breaks),
                "pre_transient_events": len(pre_transients),
                "pre_transient_sequence": bool(pre_transients),
                "pre_combined_events": len(pre_breaks) + len(pre_transients),
                "pre_combined_sequence": bool(pre_breaks or pre_transients),
                "post_transient_events": len(post_transients),
                "post_transient_sequence": bool(post_transients),
            }
        )
    return metrics


def _new_counts() -> dict[str, Any]:
    return {
        "structural_sequences": 0,
        "structural_events": 0,
        "transient_sequences": 0,
        "transient_events": 0,
        "combined_sequences": 0,
        "combined_events": 0,
        "pre_structural_sequences": 0,
        "pre_structural_events": 0,
        "pre_transient_sequences": 0,
        "pre_transient_events": 0,
        "pre_combined_sequences": 0,
        "pre_combined_events": 0,
        "post_transient_sequences": 0,
        "post_transient_events": 0,
        "correct_sequences": 0,
        "wrong_sequences": 0,
        "wrong_events": 0,
        "delays": [],
        "onset_abs_errors": [],
        "onset_signed_errors": [],
        "rho_estimates": [],
    }


def _add_trial_metrics(counts: dict[str, Any], metrics: dict[str, Any]) -> None:
    mapping = {
        "structural_sequences": "structural_sequence",
        "structural_events": "structural_events",
        "transient_sequences": "transient_sequence",
        "transient_events": "transient_events",
        "combined_sequences": "combined_sequence",
        "combined_events": "combined_events",
        "pre_structural_sequences": "pre_structural_sequence",
        "pre_structural_events": "pre_structural_events",
        "pre_transient_sequences": "pre_transient_sequence",
        "pre_transient_events": "pre_transient_events",
        "pre_combined_sequences": "pre_combined_sequence",
        "pre_combined_events": "pre_combined_events",
        "post_transient_sequences": "post_transient_sequence",
        "post_transient_events": "post_transient_events",
    }
    for count_key, metric_key in mapping.items():
        counts[count_key] += int(metrics[metric_key])


def _rate_block(sequences: int, events: int, trials: int) -> dict[str, Any]:
    return {
        "sequences": sequences,
        "sequence_rate_pct": round(sequences / trials * 100.0, 2),
        "sequence_rate_wilson95_pct": [
            round(x * 100.0, 2) for x in wilson_interval(sequences, trials)
        ],
        "events": events,
        "events_per_sequence": round(events / trials, 4),
    }


def evaluate_suite(
    threshold: float, *, seed_base: int, trials: int
) -> dict[str, Any]:
    engine = SequentialBreakEngineB3(break_percent_thresh=threshold)
    summary: dict[str, Any] = {}

    for case_index, case in enumerate(CASES):
        counts = _new_counts()
        is_shift = case["shift_sigma"] != 0.0
        expected_direction = 1 if case["shift_sigma"] > 0 else -1

        for trial in range(trials):
            seed = seed_base + case_index * 10_000 + trial
            series = generate_series(
                np.random.default_rng(seed),
                dist=case["dist"],
                rho=case["rho"],
                var_jump=case["var_jump"],
                shift_sigma=case["shift_sigma"],
            )
            result = engine.analyze(series)
            metrics = summarize_trial_alerts(
                result, boundary=ONSET if is_shift else None
            )
            _add_trial_metrics(counts, metrics)
            counts["rho_estimates"].append(result["diagnostics"]["rho_estimate"])

            if not is_shift:
                breaks = result["structural_breaks"]
                if breaks:
                    # Structural detections are false for the level-shift target.
                    pass
                continue

            breaks = result["structural_breaks"]
            pre = [b for b in breaks if int(b["detection_time"]) < ONSET]
            post = [b for b in breaks if int(b["detection_time"]) >= ONSET]
            correct = [b for b in post if int(b["direction"]) == expected_direction]
            wrong = [b for b in post if int(b["direction"]) != expected_direction]

            if wrong:
                counts["wrong_sequences"] += 1
                counts["wrong_events"] += len(wrong)
            if correct:
                counts["correct_sequences"] += 1
                first = min(correct, key=lambda b: int(b["detection_time"]))
                delay = int(first["detection_time"]) - ONSET
                onset_error = int(first["estimated_onset"]) - ONSET
                counts["delays"].append(delay)
                counts["onset_abs_errors"].append(abs(onset_error))
                counts["onset_signed_errors"].append(onset_error)

        structural = _rate_block(
            counts["structural_sequences"], counts["structural_events"], trials
        )
        transient = _rate_block(
            counts["transient_sequences"], counts["transient_events"], trials
        )
        combined = _rate_block(
            counts["combined_sequences"], counts["combined_events"], trials
        )

        if not is_shift:
            scenario_type = "variance_jump" if case["var_jump"] else "pure_null"
            summary[case["name"]] = {
                "kind": "no_level_shift",
                "scenario_type": scenario_type,
                "trials": trials,
                # Backward-compatible names retain their original structural meaning.
                "false_alarm_sequences": counts["structural_sequences"],
                "false_alarm_rate_pct": structural["sequence_rate_pct"],
                "false_alarm_wilson95_pct": structural["sequence_rate_wilson95_pct"],
                "false_break_events_per_sequence": structural["events_per_sequence"],
                "mean_break_events_per_sequence": structural["events_per_sequence"],
                "structural_false_alarm": structural,
                "transient_alerts": transient,
                "combined_any_alerts": combined,
                "combined_false_alarm": combined if scenario_type == "pure_null" else None,
                "median_rho_estimate": round(
                    statistics.median(counts["rho_estimates"]), 4
                ),
            }
        else:
            pre_structural = _rate_block(
                counts["pre_structural_sequences"],
                counts["pre_structural_events"],
                trials,
            )
            pre_transient = _rate_block(
                counts["pre_transient_sequences"],
                counts["pre_transient_events"],
                trials,
            )
            pre_combined = _rate_block(
                counts["pre_combined_sequences"],
                counts["pre_combined_events"],
                trials,
            )
            post_transient = _rate_block(
                counts["post_transient_sequences"],
                counts["post_transient_events"],
                trials,
            )
            summary[case["name"]] = {
                "kind": "level_shift",
                "trials": trials,
                "structural_alerts": structural,
                "transient_alerts": transient,
                "combined_any_alerts": combined,
                "pre_onset_structural_false_alarm": pre_structural,
                "pre_onset_transient_alerts": pre_transient,
                "pre_onset_combined_any_alert": pre_combined,
                "pre_onset_false_alarm_sequences": counts["pre_structural_sequences"],
                "pre_onset_false_alarm_rate_pct": pre_structural["sequence_rate_pct"],
                "pre_onset_false_alarm_wilson95_pct": pre_structural[
                    "sequence_rate_wilson95_pct"
                ],
                "directionally_correct_detection_sequences": counts["correct_sequences"],
                "directional_sensitivity_pct": round(
                    counts["correct_sequences"] / trials * 100.0, 2
                ),
                "sensitivity_wilson95_pct": [
                    round(x * 100.0, 2)
                    for x in wilson_interval(counts["correct_sequences"], trials)
                ],
                "wrong_direction_sequences": counts["wrong_sequences"],
                "wrong_direction_rate_pct": round(
                    counts["wrong_sequences"] / trials * 100.0, 2
                ),
                "wrong_direction_events_per_sequence": round(
                    counts["wrong_events"] / trials, 4
                ),
                "post_onset_transient_alerts": post_transient,
                "median_detection_delay": (
                    round(float(statistics.median(counts["delays"])), 2)
                    if counts["delays"]
                    else None
                ),
                "median_onset_absolute_error": (
                    round(float(statistics.median(counts["onset_abs_errors"])), 2)
                    if counts["onset_abs_errors"]
                    else None
                ),
                "median_onset_signed_error": (
                    round(float(statistics.median(counts["onset_signed_errors"])), 2)
                    if counts["onset_signed_errors"]
                    else None
                ),
                "mean_break_events_per_sequence": structural["events_per_sequence"],
            }

    no_shift_rows = [
        (name, row)
        for name, row in summary.items()
        if row["kind"] == "no_level_shift"
    ]
    pure_null_rows = [
        (name, row)
        for name, row in no_shift_rows
        if row["scenario_type"] == "pure_null"
    ]
    worst_structural_name, worst_structural = max(
        no_shift_rows, key=lambda item: item[1]["structural_false_alarm"]["sequence_rate_pct"]
    )
    worst_null_name, worst_null = max(
        pure_null_rows, key=lambda item: item[1]["combined_false_alarm"]["sequence_rate_pct"]
    )
    return {
        "threshold": threshold,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "worst_no_level_shift_structural_false_alarm_rate_pct": (
            worst_structural["structural_false_alarm"]["sequence_rate_pct"]
        ),
        "worst_no_level_shift_structural_case": worst_structural_name,
        "worst_pure_null_combined_false_alarm_rate_pct": (
            worst_null["combined_false_alarm"]["sequence_rate_pct"]
        ),
        "worst_pure_null_combined_case": worst_null_name,
        # Legacy name remains structural-only for compatibility with previous reports.
        "worst_no_level_shift_false_alarm_rate_pct": (
            worst_structural["structural_false_alarm"]["sequence_rate_pct"]
        ),
        "cases": summary,
    }


def select_threshold(dev_sweep: list[dict[str, Any]]) -> float | None:
    """Require both structural safety and no-event combined-alert safety."""
    eligible = [
        row["threshold"]
        for row in dev_sweep
        if (
            row["worst_no_level_shift_structural_false_alarm_rate_pct"]
            <= FALSE_ALARM_BUDGET
            and row["worst_pure_null_combined_false_alarm_rate_pct"]
            <= FALSE_ALARM_BUDGET
        )
    ]
    return min(eligible) if eligible else None


def run_experiment(
    *, dev_trials: int = DEFAULT_DEV_TRIALS,
    holdout_trials: int = DEFAULT_HOLDOUT_TRIALS,
) -> dict[str, Any]:
    if dev_trials < 100 or holdout_trials < 100:
        raise ValueError("each_trial_count_must_be_at_least_100")

    dev_sweep: list[dict[str, Any]] = []
    for threshold in THRESHOLDS:
        print(
            f"DEV threshold={threshold:.1f} trials={dev_trials} "
            f"cases={len(CASES)}",
            flush=True,
        )
        row = evaluate_suite(
            threshold,
            seed_base=DEV_SEED_BASE,
            trials=dev_trials,
        )
        dev_sweep.append(row)
        print(
            "DEV RESULT "
            f"threshold={threshold:.1f} "
            f"worst_structural_no_level_shift="
            f"{row['worst_no_level_shift_structural_false_alarm_rate_pct']:.2f}% "
            f"worst_pure_null_combined="
            f"{row['worst_pure_null_combined_false_alarm_rate_pct']:.2f}% "
            f"structural_case={row['worst_no_level_shift_structural_case']} "
            f"null_case={row['worst_pure_null_combined_case']}",
            flush=True,
        )

    selected = select_threshold(dev_sweep)
    report: dict[str, Any] = {
        "experiment": "sequential_break_engine_b3_dev_holdout_v2_alert_accounting",
        "candidate": "SequentialBreakEngineB3",
        "configuration": {
            "quiet_end": 40,
            "window_size": 12,
            "anomaly_z_thresh": 3.2,
            "winsor_cap": 2.5,
            "default_break_percent_thresh": 82.0,
            "onset_lookback": 22,
            "rho_estimator": "lag-1 Pearson correlation of adjacent quiet-baseline scores",
            "threshold_selection": (
                "lowest threshold satisfying BOTH: worst structural false-alarm "
                "rate <=5% across all no-level-shift cases, AND worst combined "
                "structural-or-transient false-alert rate <=5% across pure-null cases"
            ),
            "transient_semantics": (
                "separate anomaly channel; counted in combined_any_alerts. "
                "In pure-null cases it is a false alert; in variance-jump cases "
                "it is reported but not presumed false because variance genuinely changes."
            ),
        },
        "design": {
            "series_length": N,
            "onset_index_zero_based": ONSET,
            "rho_levels": list(RHO_LEVELS),
            "shift_levels": list(SHIFT_LEVELS),
            "distributions": ["gauss", "t3"],
            "no_level_shift_cases": 12,
            "pure_null_cases": 6,
            "variance_jump_cases": 6,
            "level_shift_cases": 36,
            "total_cases": len(CASES),
            "dev_seed_base": DEV_SEED_BASE,
            "holdout_seed_base": HOLDOUT_SEED_BASE,
            "seed_scheme": "seed_base + case_index*10000 + trial",
            "false_alarm_budget_pct": FALSE_ALARM_BUDGET,
        },
        "pending_state_tracking": {
            "available": False,
            "reason": (
                "B-v3 emits transient_anomalies and structural_breaks but defines "
                "no pending/confirmed/rejected/expired lifecycle state."
            ),
        },
        "dev_sweep": dev_sweep,
        "selected_threshold": selected,
        "holdout": None,
        "holdout_structural_point_gate_passed": False,
        "holdout_structural_wilson_upper95_gate_passed": False,
        "holdout_null_combined_point_gate_passed": False,
        "holdout_null_combined_wilson_upper95_gate_passed": False,
        "holdout_point_estimate_gate_passed": False,
        "holdout_wilson_upper95_gate_passed": False,
        "final_gate_passed": False,
    }

    if selected is None:
        report["holdout_status"] = (
            "NOT_RUN: no development threshold met BOTH structural and "
            "pure-null combined false-alert budgets"
        )
        return report

    print(
        f"HOLDOUT threshold={selected:.1f} trials={holdout_trials} "
        f"cases={len(CASES)}",
        flush=True,
    )
    holdout = evaluate_suite(
        selected,
        seed_base=HOLDOUT_SEED_BASE,
        trials=holdout_trials,
    )
    report["holdout"] = holdout

    no_shift = [
        row for row in holdout["cases"].values() if row["kind"] == "no_level_shift"
    ]
    pure_null = [
        row for row in no_shift if row["scenario_type"] == "pure_null"
    ]
    structural_point = all(
        row["structural_false_alarm"]["sequence_rate_pct"] <= FALSE_ALARM_BUDGET
        for row in no_shift
    )
    structural_wilson = all(
        row["structural_false_alarm"]["sequence_rate_wilson95_pct"][1]
        <= FALSE_ALARM_BUDGET
        for row in no_shift
    )
    null_combined_point = all(
        row["combined_false_alarm"]["sequence_rate_pct"] <= FALSE_ALARM_BUDGET
        for row in pure_null
    )
    null_combined_wilson = all(
        row["combined_false_alarm"]["sequence_rate_wilson95_pct"][1]
        <= FALSE_ALARM_BUDGET
        for row in pure_null
    )

    report["holdout_structural_point_gate_passed"] = structural_point
    report["holdout_structural_wilson_upper95_gate_passed"] = structural_wilson
    report["holdout_null_combined_point_gate_passed"] = null_combined_point
    report["holdout_null_combined_wilson_upper95_gate_passed"] = null_combined_wilson
    report["holdout_point_estimate_gate_passed"] = (
        structural_point and null_combined_point
    )
    report["holdout_wilson_upper95_gate_passed"] = (
        structural_wilson and null_combined_wilson
    )
    report["final_gate_passed"] = (
        report["holdout_point_estimate_gate_passed"]
        and report["holdout_wilson_upper95_gate_passed"]
    )
    report["holdout_status"] = "COMPLETED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trials", type=int, default=DEFAULT_DEV_TRIALS)
    parser.add_argument("--holdout-trials", type=int, default=DEFAULT_HOLDOUT_TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    report = run_experiment(
        dev_trials=args.dev_trials,
        holdout_trials=args.holdout_trials,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n=== B-v3 FINAL SUMMARY ===")
    print(f"selected_threshold={report['selected_threshold']}")
    print(f"holdout_status={report['holdout_status']}")
    print(
        "holdout_structural_point_gate_passed="
        f"{report['holdout_structural_point_gate_passed']}"
    )
    print(
        "holdout_structural_wilson_upper95_gate_passed="
        f"{report['holdout_structural_wilson_upper95_gate_passed']}"
    )
    print(
        "holdout_null_combined_point_gate_passed="
        f"{report['holdout_null_combined_point_gate_passed']}"
    )
    print(
        "holdout_null_combined_wilson_upper95_gate_passed="
        f"{report['holdout_null_combined_wilson_upper95_gate_passed']}"
    )
    print(f"final_gate_passed={report['final_gate_passed']}")
    print(f"artifact={args.output}")

    if report["holdout"] is not None:
        displayed_rows = report["holdout"]["cases"].items()
        stage = "HOLDOUT"
    else:
        # When no threshold qualifies, show the complete dev summary per candidate.
        displayed_rows = (
            (str(row["threshold"]), row) for row in report["dev_sweep"]
        )
        stage = "DEV"

    for name, row in displayed_rows:
        if row.get("kind") == "no_level_shift":
            print(
                f"{stage} {name:32s} | type={row['scenario_type']:12s} "
                f"| structural={row['structural_false_alarm']['sequence_rate_pct']:5.2f}% "
                f"| transient={row['transient_alerts']['sequence_rate_pct']:5.2f}% "
                f"| combined={row['combined_any_alerts']['sequence_rate_pct']:5.2f}%"
            )
        elif row.get("kind") == "level_shift":
            print(
                f"{stage} {name:32s} | sensitivity="
                f"{row['directional_sensitivity_pct']:5.2f}% "
                f"| pre_structural={row['pre_onset_structural_false_alarm']['sequence_rate_pct']:5.2f}% "
                f"| pre_transient={row['pre_onset_transient_alerts']['sequence_rate_pct']:5.2f}% "
                f"| pre_combined={row['pre_onset_combined_any_alert']['sequence_rate_pct']:5.2f}% "
                f"| post_transient={row['post_onset_transient_alerts']['sequence_rate_pct']:5.2f}%"
            )
        elif "threshold" in row:
            print(
                f"DEV threshold={row['threshold']:4.1f} "
                f"| worst_structural="
                f"{row['worst_no_level_shift_structural_false_alarm_rate_pct']:5.2f}% "
                f"| worst_null_combined="
                f"{row['worst_pure_null_combined_false_alarm_rate_pct']:5.2f}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
