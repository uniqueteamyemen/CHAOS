"""Six-scenario, 500-path benchmark for ImprovedSequentialBreakEngine."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break.engine import ImprovedSequentialBreakEngine
from experiments.identity_lab.exp_p_engine_holdout.asymmetry_guarded_cusum import (
    asymmetry_guarded_bounded_cusum,
)
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson

N = 140
RHO = 0.70
ONSET = 65
TRIALS = 500
SEED_BASE = 2_000_000
SCENARIOS = (
    "gauss_ar1",
    "gauss_ar1_var_jump",
    "t3_ar1",
    "t3_ar1_var_jump",
    "pos_shift_3s",
    "neg_shift_3s",
)
OUTPUT = Path(__file__).resolve().parent / "results" / "sequential_break_engine_500_seed_benchmark.json"


def generate_series(rng: np.random.Generator, scenario: str, n: int = N,
                    rho: float = RHO, onset: int = ONSET) -> np.ndarray:
    if "t3" in scenario:
        eps = rng.standard_t(df=3, size=n) / np.sqrt(3.0)
    else:
        eps = rng.normal(0.0, 1.0, size=n)
    if "var_jump" in scenario:
        eps[onset:] *= 2.0
    x = np.zeros(n, dtype=float)
    x[0] = eps[0]
    for t in range(1, n):
        x[t] = rho * x[t - 1] + np.sqrt(1.0 - rho**2) * eps[t]
    if "pos_shift" in scenario:
        x[onset:] += 3.0
    elif "neg_shift" in scenario:
        x[onset:] -= 3.0
    return x


def score_sequential(result: dict[str, Any], *, scenario: str,
                     confirm_window: int) -> dict[str, Any]:
    breaks = result["structural_breaks"]
    if "shift" not in scenario:
        return {
            "false_alarm": len(breaks) > 0,
            "false_events": len(breaks),
            "pre_onset_false_alarm": False,
            "detected": False,
            "wrong_direction": False,
            "operational_delay": None,
            "estimated_onset": None,
            "evidence_available_at": None,
            "backdated_onset": None,
        }

    expected_direction = 1 if "pos_shift" in scenario else -1
    emitted = [
        {**event, "evidence_available_at": int(event["onset_time"]) + confirm_window - 1}
        for event in breaks
    ]
    pre = [event for event in emitted if event["evidence_available_at"] < ONSET]
    post = [event for event in emitted if event["evidence_available_at"] >= ONSET]
    correct = [event for event in post if int(event["direction"]) == expected_direction]
    wrong = [event for event in post if int(event["direction"]) != expected_direction]
    first = min(correct, key=lambda item: item["evidence_available_at"]) if correct else None
    return {
        "false_alarm": False,
        "false_events": 0,
        "pre_onset_false_alarm": len(pre) > 0,
        "pre_onset_false_events": len(pre),
        "detected": first is not None,
        "wrong_direction": len(wrong) > 0,
        "operational_delay": int(first["evidence_available_at"]) - ONSET if first else None,
        "estimated_onset": int(first["onset_time"]) if first else None,
        "evidence_available_at": int(first["evidence_available_at"]) if first else None,
        "backdated_onset": ONSET - int(first["onset_time"]) if first and first["onset_time"] < ONSET else 0,
        "reported_onset_error": int(first["onset_time"]) - ONSET if first else None,
    }


def score_ag(alerts: list[dict[str, Any]], *, scenario: str) -> dict[str, Any]:
    if "shift" not in scenario:
        false = [alert for alert in alerts if int(alert["time"]) >= 40]
        return {
            "false_alarm": len(false) > 0, "false_events": len(false),
            "pre_onset_false_alarm": False, "detected": False,
            "wrong_direction": False, "operational_delay": None,
        }
    expected_direction = 1 if "pos_shift" in scenario else -1
    pre = [alert for alert in alerts if 40 <= int(alert["time"]) < ONSET]
    post = [alert for alert in alerts if int(alert["time"]) >= ONSET]
    correct = [alert for alert in post if int(alert["direction"]) == expected_direction]
    wrong = [alert for alert in post if int(alert["direction"]) != expected_direction]
    first = min((int(alert["time"]) for alert in correct), default=None)
    return {
        "false_alarm": False, "false_events": 0,
        "pre_onset_false_alarm": len(pre) > 0,
        "pre_onset_false_events": len(pre),
        "detected": first is not None, "wrong_direction": len(wrong) > 0,
        "operational_delay": first - ONSET if first is not None else None,
    }


def _empty_counts() -> dict[str, Any]:
    return {
        "false_sequences": 0, "false_events": 0, "pre_sequences": 0,
        "pre_events": 0, "detected": 0, "wrong_sequences": 0,
        "delays": [], "onset_errors": [], "backdated": [],
        "breaks_per_sequence": [], "anomalies_per_sequence": [],
    }


def _add(counts: dict[str, Any], score: dict[str, Any], result: dict[str, Any]) -> None:
    counts["false_sequences"] += int(score["false_alarm"])
    counts["false_events"] += int(score["false_events"])
    counts["pre_sequences"] += int(score["pre_onset_false_alarm"])
    counts["pre_events"] += int(score.get("pre_onset_false_events", 0))
    counts["detected"] += int(score["detected"])
    counts["wrong_sequences"] += int(score["wrong_direction"])
    if score["operational_delay"] is not None:
        counts["delays"].append(float(score["operational_delay"]))
    if score.get("reported_onset_error") is not None:
        counts["onset_errors"].append(float(score["reported_onset_error"]))
    if score.get("backdated_onset") is not None:
        counts["backdated"].append(float(score["backdated_onset"]))
    counts["breaks_per_sequence"].append(len(result["structural_breaks"]))
    counts["anomalies_per_sequence"].append(len(result["transient_anomalies"]))


def _summarize(counts: dict[str, Any], scenario: str) -> dict[str, Any]:
    trials = len(counts["breaks_per_sequence"])
    if "shift" not in scenario:
        return {
            "false_alarm_sequences": counts["false_sequences"],
            "false_alarm_rate": counts["false_sequences"] / trials,
            "false_alarm_wilson95": wilson(counts["false_sequences"], trials),
            "false_break_events_per_sequence": counts["false_events"] / trials,
            "mean_breaks_per_sequence": statistics.mean(counts["breaks_per_sequence"]),
            "mean_transient_anomalies_per_sequence": statistics.mean(counts["anomalies_per_sequence"]),
        }
    return {
        "pre_onset_false_alarm_sequences": counts["pre_sequences"],
        "pre_onset_false_alarm_rate": counts["pre_sequences"] / trials,
        "pre_onset_false_wilson95": wilson(counts["pre_sequences"], trials),
        "directional_sensitivity": counts["detected"] / trials,
        "sensitivity_wilson95": wilson(counts["detected"], trials),
        "wrong_direction_sequence_rate": counts["wrong_sequences"] / trials,
        "mean_operational_detection_delay": statistics.mean(counts["delays"]) if counts["delays"] else None,
        "median_operational_detection_delay": statistics.median(counts["delays"]) if counts["delays"] else None,
        "mean_reported_onset_error": statistics.mean(counts["onset_errors"]) if counts["onset_errors"] else None,
        "mean_backdated_onset_steps": statistics.mean(counts["backdated"]) if counts["backdated"] else None,
        "mean_breaks_per_sequence": statistics.mean(counts["breaks_per_sequence"]),
        "mean_transient_anomalies_per_sequence": statistics.mean(counts["anomalies_per_sequence"]),
    }


def run_benchmark(trials: int = TRIALS) -> dict[str, Any]:
    if trials < 100:
        raise ValueError("trials_must_be_at_least_100")
    engine = ImprovedSequentialBreakEngine()
    methods = ("ImprovedSequentialBreakEngine", "AG-CUSUM")
    counts = {method: {scenario: _empty_counts() for scenario in SCENARIOS} for method in methods}
    rho_estimates = []

    for scenario_index, scenario in enumerate(SCENARIOS):
        for trial in range(trials):
            seed = SEED_BASE + scenario_index * 10_000 + trial
            series = generate_series(np.random.default_rng(seed), scenario)

            sequential_result = engine.analyze(series)
            seq_score = score_sequential(
                sequential_result, scenario=scenario,
                confirm_window=engine.confirm_window,
            )
            _add(counts["ImprovedSequentialBreakEngine"][scenario], seq_score, sequential_result)

            ag_alerts, ag_diag = asymmetry_guarded_bounded_cusum(series)
            ag_result = {"structural_breaks": ag_alerts, "transient_anomalies": []}
            ag_score = score_ag(ag_alerts, scenario=scenario)
            _add(counts["AG-CUSUM"][scenario], ag_score, ag_result)
            rho_estimates.append(float(ag_diag["rho_used"]))

    scenario_results = {
        method: {
            scenario: _summarize(counts[method][scenario], scenario)
            for scenario in SCENARIOS
        }
        for method in methods
    }
    aggregate = {}
    for method in methods:
        null_names = [name for name in SCENARIOS if "shift" not in name]
        shift_names = [name for name in SCENARIOS if "shift" in name]
        aggregate[method] = {
            "worst_null_false_alarm_rate": max(
                scenario_results[method][name]["false_alarm_rate"] for name in null_names
            ),
            "minimum_shift_directional_sensitivity": min(
                scenario_results[method][name]["directional_sensitivity"] for name in shift_names
            ),
            "worst_pre_onset_false_alarm_rate": max(
                scenario_results[method][name]["pre_onset_false_alarm_rate"] for name in shift_names
            ),
        }

    return {
        "experiment": "improved_sequential_break_engine_six_scenario_v1",
        "candidate": "ImprovedSequentialBreakEngine, supplied defaults unchanged",
        "comparison": "paired AG-CUSUM baseline, frozen defaults",
        "trials_per_scenario": trials,
        "total_series_per_method": trials * len(SCENARIOS),
        "seed_scheme": "2_000_000 + scenario_index*10_000 + trial",
        "generator": {
            "length": N, "ar1_rho": RHO, "onset_index_zero_based": ONSET,
            "innovation": "Gaussian N(0,1) or Student-t(3)/sqrt(3)",
            "variance_jump": "multiply innovations from onset by 2",
            "level_shift": "add +/-3 to x[onset:] after AR(1) generation",
        },
        "sequential_engine_parameters": {
            "quiet_end": engine.quiet_end, "anomaly_z_thresh": engine.anomaly_z_thresh,
            "confirm_window": engine.confirm_window,
            "break_percent_thresh": engine.break_percent_thresh,
        },
        "timing_contract": {
            "reported_onset_time": "t, beginning of the 12-point confirmation window",
            "evidence_available_time": "t + confirm_window - 1",
            "lookahead_points": engine.confirm_window - 1,
            "zero_operational_delay_claim": False,
        },
        "aggregate": aggregate,
        "scenarios": scenario_results,
        "diagnostics": {"median_AG_estimated_rho": statistics.median(rho_estimates)},
        "limitations": [
            "Break percentage is a weighted heuristic score, not a calibrated probability.",
            "The 12-point future window gives fixed-lag retrospective onset estimates; it is not an alarm available at onset_time.",
            "Only the six supplied synthetic regimes were tested; this is not a production validation.",
        ],
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run_benchmark(args.trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "aggregate": report["aggregate"],
        "scenarios": report["scenarios"],
        "timing_contract": report["timing_contract"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
