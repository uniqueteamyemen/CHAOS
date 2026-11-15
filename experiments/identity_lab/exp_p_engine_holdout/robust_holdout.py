"""Independent holdout for selected CUSUM transition-policy candidates.

The threshold sweep selects settings using its own synthetic training seeds.
This experiment evaluates the selected settings on disjoint seeds and new
stochastic regimes (AR(1), Student-t heavy tails, and variance transitions).
It scores CUSUM evidence only; P1 and fusion notifications are excluded.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Mapping

from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates
from experiments.identity_lab.exp_p_engine.cusum_parameter_sweep import score_cusum_hits
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson

MONTHS = 140
QUIET_RANGE = (1, 40)
ONSET = 65
AR1_PHI = 0.60
HOLDOUT_TRIALS = 500
HOLDOUT_SEED_BASE = 1_800_000

NULL_SCENARIOS = (
    "gaussian_ar1_null",
    "gaussian_ar1_variance_jump_null",
    "student_t3_ar1_null",
    "student_t3_ar1_variance_jump_null",
)
SHIFT_SCENARIOS = (
    "gaussian_ar1_positive_step3",
    "gaussian_ar1_negative_step3",
    "student_t3_ar1_positive_step3",
    "student_t3_ar1_negative_step3",
    "student_t3_ar1_transition_positive_step3",
    "student_t3_ar1_transition_negative_step3",
)
SCENARIOS = NULL_SCENARIOS + SHIFT_SCENARIOS
VARIANTS = ("C", "E", "F")
NULL_GATE = 0.05
TRAINING_SENSITIVITY_FLOOR = 0.75

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SWEEP_REPORT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "cusum_parameter_sweep.json"
)
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine_holdout"
    / "results" / "cusum_robust_holdout.json"
)


def select_training_candidates(
    sweep: Mapping[str, Any],
    *,
    null_gate: float = NULL_GATE,
    sensitivity_floor: float = TRAINING_SENSITIVITY_FLOOR,
) -> list[dict[str, Any]]:
    """Select per-variant settings from training only; never inspect holdout results."""
    results = sweep.get("results", {})
    required_nulls = ("stable_null", "rising_noise_null", "elevated_noise_null")
    required_shifts = (
        "positive_step_3sigma",
        "negative_step_3sigma",
        "transition_positive_3sigma",
        "transition_negative_3sigma",
    )
    first = results.get(required_nulls[0], {}).get("parameters", {})
    keys = sorted(first)
    selections = [{
        "candidate_id": "C-default-control",
        "variant": "C",
        "k": 0.5,
        "h": 8.5,
        "selection_status": "fixed_default_control",
        "training_worst_null_false_alarm_rate": None,
        "training_minimum_shift_sensitivity": None,
    }]

    for variant in VARIANTS:
        eligible = []
        for key in keys:
            try:
                null_rates = [
                    float(results[name]["parameters"][key][variant]["false_alarm_rate"])
                    for name in required_nulls
                ]
                sensitivities = [
                    float(results[name]["parameters"][key][variant]["sensitivity"])
                    for name in required_shifts
                ]
                delays = [
                    results[name]["parameters"][key][variant]["mean_detection_delay"]
                    for name in required_shifts
                ]
            except (KeyError, TypeError, ValueError):
                continue
            worst_null = max(null_rates)
            min_sensitivity = min(sensitivities)
            mean_sensitivity = statistics.mean(sensitivities)
            mean_delay = statistics.mean(float(v) for v in delays if v is not None)
            if worst_null <= null_gate:
                k_text, h_text = key.split("|")
                k, h = float(k_text.split("=")[1]), float(h_text.split("=")[1])
                eligible.append({
                    "candidate_id": f"{variant}-{key.replace('|', '-')}",
                    "variant": variant,
                    "k": k,
                    "h": h,
                    "selection_status": (
                        "eligible_for_holdout"
                        if min_sensitivity >= sensitivity_floor
                        else "diagnostic_only_low_training_sensitivity"
                    ),
                    "training_worst_null_false_alarm_rate": worst_null,
                    "training_minimum_shift_sensitivity": min_sensitivity,
                    "training_mean_shift_sensitivity": mean_sensitivity,
                    "training_mean_detection_delay": mean_delay,
                })
        if eligible:
            best = max(
                eligible,
                key=lambda item: (
                    item["training_minimum_shift_sensitivity"],
                    item["training_mean_shift_sensitivity"],
                    -item["training_mean_detection_delay"],
                    -item["h"],
                ),
            )
            selections.append(best)
        else:
            selections.append({
                "candidate_id": f"{variant}-no-null-passing-setting",
                "variant": variant,
                "k": None,
                "h": None,
                "selection_status": "no_training_setting_passed_null_gate",
                "training_worst_null_false_alarm_rate": None,
                "training_minimum_shift_sensitivity": None,
            })
    return selections


def _iid_noise(rng: random.Random, distribution: str) -> float:
    if distribution == "gaussian":
        return rng.gauss(0.0, 1.0)
    if distribution == "student_t3":
        chi_square_3 = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(3))
        return rng.gauss(0.0, 1.0) / math.sqrt(max(chi_square_3, 1e-12))
    raise ValueError(f"holdout_distribution_invalid:{distribution}")


def generate_residuals(seed: int, scenario: str) -> list[float]:
    """Generate unit-variance Gaussian/t3 AR(1) residuals with optional mean/scale shifts."""
    rng = random.Random(seed)
    if scenario.startswith("gaussian_"):
        distribution = "gaussian"
    elif scenario.startswith("student_t3_"):
        distribution = "student_t3"
    else:
        raise ValueError(f"holdout_scenario_invalid:{scenario}")

    has_variance_jump = "variance_jump_null" in scenario
    has_transition = "transition_" in scenario
    sign = -1 if "negative" in scenario else (1 if "positive" in scenario else 0)
    previous = 0.0
    values: list[float] = []
    innovation_scale = math.sqrt(1.0 - AR1_PHI ** 2)

    for month in range(1, MONTHS + 1):
        if has_variance_jump and month >= ONSET:
            scale = 3.0
        elif has_transition:
            scale = 1.0 + 2.0 * min(1.0, max(0.0, (month - 50) / 45.0))
        else:
            scale = 1.0

        innovation = _iid_noise(rng, distribution)
        ar_component = (
            AR1_PHI * previous
            + innovation_scale * scale * innovation
        )
        previous = ar_component

        shift = sign * 3.0 if sign and month >= ONSET else 0.0
        values.append(ar_component + shift)

    return values


def residuals_to_stock_rows(values: list[float]) -> list[dict[str, Any]]:
    """Encode residuals as ledger rows so the production residual adapter is exercised."""
    rows = []
    balance = 2_000.0
    for month, residual in enumerate(values, start=1):
        expected_closing = balance + 400.0 - 400.0 - 5.0
        closing = expected_closing - residual
        rows.append({
            "opening_balance": balance,
            "inflow": 400.0,
            "outflow": 400.0,
            "adjustments": 5.0,
            "closing_balance": closing,
            "month": month,
        })
        balance = closing
    return rows


def _score_candidate(
    hits: list[dict[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    return score_cusum_hits(hits, scenario=scenario, onset=ONSET)


def run_holdout(sweep: Mapping[str, Any], *, trials: int = HOLDOUT_TRIALS) -> dict[str, Any]:
    if trials < 100:
        raise ValueError("holdout_trials_must_be_at_least_100")
    selected = select_training_candidates(sweep)
    runnable = [item for item in selected if item.get("k") is not None and item.get("h") is not None]

    candidate_results: dict[str, dict[str, Any]] = {}
    for candidate in runnable:
        candidate_id = candidate["candidate_id"]
        variant = candidate["variant"]
        counts = {
            scenario: {
                "false": 0,
                "false_events": 0,
                "pre_onset_false": 0,
                "detected": 0,
                "wrong_direction": 0,
                "delays": [],
            }
            for scenario in SCENARIOS
        }

        for scenario_index, scenario in enumerate(SCENARIOS):
            for trial in range(trials):
                seed = HOLDOUT_SEED_BASE + scenario_index * 100_000 + trial
                values = generate_residuals(seed, scenario)
                rows = residuals_to_stock_rows(values)
                result = run_candidates(
                    "stock",
                    rows,
                    quiet_range=QUIET_RANGE,
                    entity=f"robust-holdout-{scenario_index}",
                    code_revision="p-engine-independent-robust-holdout-v1",
                    k_cusum=float(candidate["k"]),
                    h_cusum=float(candidate["h"]),
                )
                metrics = _score_candidate(result[variant]["raw_hits"], scenario)
                target = counts[scenario]
                target["false"] += int(metrics["false_alarm"])
                target["false_events"] += int(metrics["false_alarm_events"])
                target["pre_onset_false"] += int(metrics["pre_onset_false_alarm"])
                target["detected"] += int(metrics["detected"])
                target["wrong_direction"] += int(metrics["wrong_direction"])
                if metrics["delay"] is not None:
                    target["delays"].append(float(metrics["delay"]))

        summarized = {}
        for scenario, values in counts.items():
            is_null = scenario in NULL_SCENARIOS
            if is_null:
                summarized[scenario] = {
                    "false_alarm_rate": values["false"] / trials,
                    "false_alarm_wilson95": wilson(values["false"], trials),
                    "false_events_per_sequence": values["false_events"] / trials,
                }
            else:
                summarized[scenario] = {
                    "pre_onset_false_alarm_rate": values["pre_onset_false"] / trials,
                    "pre_onset_false_wilson95": wilson(values["pre_onset_false"], trials),
                    "sensitivity": values["detected"] / trials,
                    "sensitivity_wilson95": wilson(values["detected"], trials),
                    "wrong_direction_trial_rate": values["wrong_direction"] / trials,
                    "mean_detection_delay": (
                        statistics.mean(values["delays"]) if values["delays"] else None
                    ),
                    "median_detection_delay": (
                        statistics.median(values["delays"]) if values["delays"] else None
                    ),
                }
        null_rates = [summarized[name]["false_alarm_rate"] for name in NULL_SCENARIOS]
        shift_sensitivity = [summarized[name]["sensitivity"] for name in SHIFT_SCENARIOS]
        candidate_results[candidate_id] = {
            "candidate": candidate,
            "worst_holdout_null_false_alarm_rate": max(null_rates),
            "minimum_holdout_shift_sensitivity": min(shift_sensitivity),
            "mean_holdout_shift_sensitivity": statistics.mean(shift_sensitivity),
            "scenarios": summarized,
            "holdout_gate": (
                "pass"
                if max(null_rates) <= NULL_GATE and min(shift_sensitivity) >= sensitivity_floor()
                else "fail_or_not_promoted"
            ),
        }

    return {
        "experiment": "p_engine_cusum_independent_robust_holdout_v1",
        "training_source": "G threshold sweep artifact; no holdout outcomes used for selection",
        "holdout_trials_per_scenario": trials,
        "holdout_seed_base": HOLDOUT_SEED_BASE,
        "ar1_phi": AR1_PHI,
        "scenarios": list(SCENARIOS),
        "null_gate": NULL_GATE,
        "minimum_shift_sensitivity_gate": sensitivity_floor(),
        "training_selection": selected,
        "results": candidate_results,
        "decision_rule": (
            "A candidate passes only if every independent null condition has a "
            "CUSUM sequence false-alarm rate <=5% and every independent shifted "
            "condition retains >=75% directional CUSUM sensitivity."
        ),
        "limitations": [
            "Synthetic holdout tests robustness under specified AR(1) and Student-t3 regimes; it is not a substitute for unlabeled field data.",
            "The run_candidates policy also creates P1/fusion outputs, but holdout scoring intentionally uses CUSUM raw hits only.",
        ],
    }


def sensitivity_floor() -> float:
    return TRAINING_SENSITIVITY_FLOOR


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-report", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=HOLDOUT_TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    sweep = json.loads(args.sweep_report.read_text(encoding="utf-8"))
    report = run_holdout(sweep, trials=args.trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        candidate: {
            "selected": value["candidate"],
            "worst_null": value["worst_holdout_null_false_alarm_rate"],
            "minimum_shift_sensitivity": value["minimum_holdout_shift_sensitivity"],
            "holdout_gate": value["holdout_gate"],
        }
        for candidate, value in report["results"].items()
    }
    print(json.dumps({"output": str(args.output), "summary": compact}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
