"""Paired dev/holdout calibration for SequentialBreakEngine B-v3."""
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

    # Direction, shift magnitude, distribution, and serial dependence are
    # crossed rather than testing weaker shifts at rho=0.7 only.
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


def _new_counts() -> dict[str, Any]:
    return {
        "false_sequences": 0,
        "false_events": 0,
        "pre_sequences": 0,
        "pre_events": 0,
        "correct_sequences": 0,
        "wrong_sequences": 0,
        "wrong_events": 0,
        "delays": [],
        "onset_abs_errors": [],
        "onset_signed_errors": [],
        "all_alerts": 0,
        "rho_estimates": [],
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
            breaks = result["structural_breaks"]
            counts["all_alerts"] += len(breaks)
            counts["rho_estimates"].append(result["diagnostics"]["rho_estimate"])

            if not is_shift:
                if breaks:
                    counts["false_sequences"] += 1
                    counts["false_events"] += len(breaks)
                continue

            pre = [b for b in breaks if b["detection_time"] < ONSET]
            post = [b for b in breaks if b["detection_time"] >= ONSET]
            correct = [b for b in post if b["direction"] == expected_direction]
            wrong = [b for b in post if b["direction"] != expected_direction]

            if pre:
                counts["pre_sequences"] += 1
                counts["pre_events"] += len(pre)
            if wrong:
                counts["wrong_sequences"] += 1
                counts["wrong_events"] += len(wrong)
            if correct:
                counts["correct_sequences"] += 1
                first = min(correct, key=lambda b: b["detection_time"])
                delay = int(first["detection_time"]) - ONSET
                onset_error = int(first["estimated_onset"]) - ONSET
                counts["delays"].append(delay)
                counts["onset_abs_errors"].append(abs(onset_error))
                counts["onset_signed_errors"].append(onset_error)

        if not is_shift:
            rate = counts["false_sequences"] / trials
            summary[case["name"]] = {
                "kind": "no_level_shift",
                "trials": trials,
                "false_alarm_sequences": counts["false_sequences"],
                "false_alarm_rate_pct": round(rate * 100.0, 2),
                "false_alarm_wilson95_pct": [
                    round(x * 100.0, 2)
                    for x in wilson_interval(counts["false_sequences"], trials)
                ],
                "false_break_events_per_sequence": round(
                    counts["false_events"] / trials, 4
                ),
                "mean_break_events_per_sequence": round(
                    counts["all_alerts"] / trials, 4
                ),
                "median_rho_estimate": round(
                    statistics.median(counts["rho_estimates"]), 4
                ),
            }
        else:
            summary[case["name"]] = {
                "kind": "level_shift",
                "trials": trials,
                "pre_onset_false_alarm_sequences": counts["pre_sequences"],
                "pre_onset_false_alarm_rate_pct": round(
                    counts["pre_sequences"] / trials * 100.0, 2
                ),
                "pre_onset_false_alarm_wilson95_pct": [
                    round(x * 100.0, 2)
                    for x in wilson_interval(counts["pre_sequences"], trials)
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
                "mean_break_events_per_sequence": round(
                    counts["all_alerts"] / trials, 4
                ),
            }

    no_shift_rates = [
        v["false_alarm_rate_pct"]
        for v in summary.values()
        if v["kind"] == "no_level_shift"
    ]
    return {
        "threshold": threshold,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "worst_no_level_shift_false_alarm_rate_pct": max(no_shift_rates),
        "cases": summary,
    }


def select_threshold(dev_sweep: list[dict[str, Any]]) -> float | None:
    eligible = [
        row["threshold"]
        for row in dev_sweep
        if row["worst_no_level_shift_false_alarm_rate_pct"] <= FALSE_ALARM_BUDGET
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
        dev_sweep.append(
            evaluate_suite(
                threshold,
                seed_base=DEV_SEED_BASE,
                trials=dev_trials,
            )
        )

    selected = select_threshold(dev_sweep)
    report: dict[str, Any] = {
        "experiment": "sequential_break_engine_b3_dev_holdout_v1",
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
                "lowest threshold whose worst no-level-shift false-alarm "
                "sequence rate across all null and variance-jump cases is <=5%"
            ),
        },
        "design": {
            "series_length": N,
            "onset_index_zero_based": ONSET,
            "rho_levels": list(RHO_LEVELS),
            "shift_levels": list(SHIFT_LEVELS),
            "distributions": ["gauss", "t3"],
            "no_level_shift_cases": 12,
            "level_shift_cases": 36,
            "total_cases": len(CASES),
            "dev_seed_base": DEV_SEED_BASE,
            "holdout_seed_base": HOLDOUT_SEED_BASE,
            "seed_scheme": "seed_base + case_index*10000 + trial",
            "false_alarm_budget_pct": FALSE_ALARM_BUDGET,
        },
        "dev_sweep": dev_sweep,
        "selected_threshold": selected,
        "holdout": None,
        "holdout_point_estimate_gate_passed": False,
        "holdout_wilson_upper95_gate_passed": False,
        "final_gate_passed": False,
    }

    if selected is None:
        report["holdout_status"] = (
            "NOT_RUN: no development threshold met the <=5% false-alarm budget"
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
        v for v in holdout["cases"].values() if v["kind"] == "no_level_shift"
    ]
    point_gate = all(
        v["false_alarm_rate_pct"] <= FALSE_ALARM_BUDGET for v in no_shift
    )
    upper_gate = all(
        v["false_alarm_wilson95_pct"][1] <= FALSE_ALARM_BUDGET
        for v in no_shift
    )
    report["holdout_point_estimate_gate_passed"] = point_gate
    report["holdout_wilson_upper95_gate_passed"] = upper_gate
    report["final_gate_passed"] = point_gate and upper_gate
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
        "holdout_point_estimate_gate_passed="
        f"{report['holdout_point_estimate_gate_passed']}"
    )
    print(
        "holdout_wilson_upper95_gate_passed="
        f"{report['holdout_wilson_upper95_gate_passed']}"
    )
    print(f"final_gate_passed={report['final_gate_passed']}")
    print(f"artifact={args.output}")
    if report["holdout"] is not None:
        for name, row in report["holdout"]["cases"].items():
            if row["kind"] == "no_level_shift":
                print(
                    f"{name:32s} | false_alarm="
                    f"{row['false_alarm_rate_pct']:5.2f}% "
                    f"| Wilson95={row['false_alarm_wilson95_pct']}"
                )
            else:
                print(
                    f"{name:32s} | sensitivity="
                    f"{row['directional_sensitivity_pct']:5.2f}% "
                    f"| pre={row['pre_onset_false_alarm_rate_pct']:5.2f}% "
                    f"| wrong={row['wrong_direction_rate_pct']:5.2f}% "
                    f"| delay={row['median_detection_delay']} "
                    f"| onset_MAE={row['median_onset_absolute_error']}"
                )
    else:
        for row in report["dev_sweep"]:
            print(
                f"DEV threshold={row['threshold']:4.1f} "
                f"| worst_no_shift_FPR="
                f"{row['worst_no_level_shift_false_alarm_rate_pct']:5.2f}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
