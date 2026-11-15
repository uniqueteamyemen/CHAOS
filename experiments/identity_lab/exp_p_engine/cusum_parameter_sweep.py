"""Targeted paired CUSUM k/h sweep for C/E/F transition policies."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import (
    MONTHS, ONSET, QUIET_RANGE, make_rows, scenario_spec, wilson,
)
from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates

TRIALS = 200
K_GRID = (0.5, 0.75)
H_GRID = (8.5, 12.0, 16.0, 24.0)
VARIANTS = ("C", "E", "F")
SCENARIOS = (
    "stable_null", "rising_noise_null", "elevated_noise_null",
    "positive_step_3sigma", "negative_step_3sigma",
    "transition_positive_3sigma", "transition_negative_3sigma",
)
SEED_BASE = 720_000
OUTPUT = Path(__file__).resolve().parent / "results" / "cusum_parameter_sweep.json"


def score_cusum_hits(hits, *, scenario: str, onset: int = ONSET) -> dict:
    """Score CUSUM only; P1/fused notifications are excluded."""
    selected = [
        hit for hit in hits
        if str(hit.get("detector", "")).startswith("cusum_")
    ]
    sign = -1 if "negative" in scenario else (1 if "positive" in scenario else 0)
    if sign == 0:
        false_hits = [hit for hit in selected if int(hit["time"]) > QUIET_RANGE[1]]
        return {
            "is_null": True, "false_alarm": bool(false_hits),
            "false_alarm_events": len(false_hits), "pre_onset_false_alarm": False,
            "detected": False, "wrong_direction": False, "delay": None,
        }
    pre_hits = [
        hit for hit in selected if QUIET_RANGE[1] < int(hit["time"]) < onset
    ]
    post_hits = [hit for hit in selected if int(hit["time"]) >= onset]
    correct = [hit for hit in post_hits if int(hit["sign"]) == sign]
    wrong = [hit for hit in post_hits if int(hit["sign"]) != sign]
    first = min((int(hit["time"]) for hit in correct), default=None)
    return {
        "is_null": False, "false_alarm": False, "false_alarm_events": 0,
        "pre_onset_false_alarm": bool(pre_hits), "detected": first is not None,
        "wrong_direction": bool(wrong), "delay": first - onset if first is not None else None,
    }


def run_sweep() -> dict:
    results = {}
    for scenario_index, scenario in enumerate(SCENARIOS):
        _, _, expected_sign = scenario_spec(scenario, ONSET)
        scenario_result = {"trials": TRIALS, "expected_direction": expected_sign, "parameters": {}}
        for k in K_GRID:
            for h in H_GRID:
                key = f"k={k:.2f}|h={h:.1f}"
                counts = {
                    variant: {
                        "null_false": 0, "null_false_events": 0, "pre_onset_false": 0,
                        "detected": 0, "wrong_direction": 0, "delays": [],
                    }
                    for variant in VARIANTS
                }
                for trial in range(TRIALS):
                    seed = SEED_BASE + scenario_index * 100_000 + trial
                    rows, _ = make_rows(seed, scenario)
                    candidates = run_candidates(
                        "stock", rows, quiet_range=QUIET_RANGE,
                        entity=f"cusum-sweep-{scenario_index}",
                        code_revision="p-engine-cusum-kh-sweep-v1",
                        k_cusum=k, h_cusum=h,
                    )
                    for variant in VARIANTS:
                        metrics = score_cusum_hits(candidates[variant]["raw_hits"], scenario=scenario)
                        target = counts[variant]
                        target["null_false"] += int(metrics["false_alarm"])
                        target["null_false_events"] += metrics["false_alarm_events"]
                        target["pre_onset_false"] += int(metrics["pre_onset_false_alarm"])
                        target["detected"] += int(metrics["detected"])
                        target["wrong_direction"] += int(metrics["wrong_direction"])
                        if metrics["delay"] is not None:
                            target["delays"].append(metrics["delay"])

                cell = {}
                for variant in VARIANTS:
                    c = counts[variant]
                    if expected_sign == 0:
                        cell[variant] = {
                            "false_alarm_rate": c["null_false"] / TRIALS,
                            "false_alarm_wilson95": wilson(c["null_false"], TRIALS),
                            "false_events_per_sequence": c["null_false_events"] / TRIALS,
                        }
                    else:
                        cell[variant] = {
                            "pre_onset_false_alarm_rate": c["pre_onset_false"] / TRIALS,
                            "pre_onset_false_wilson95": wilson(c["pre_onset_false"], TRIALS),
                            "sensitivity": c["detected"] / TRIALS,
                            "sensitivity_wilson95": wilson(c["detected"], TRIALS),
                            "wrong_direction_trial_rate": c["wrong_direction"] / TRIALS,
                            "mean_detection_delay": statistics.mean(c["delays"]) if c["delays"] else None,
                            "median_detection_delay": statistics.median(c["delays"]) if c["delays"] else None,
                        }
                scenario_result["parameters"][key] = cell
        results[scenario] = scenario_result

    return {
        "experiment": "p_engine_cusum_kh_sweep_v1",
        "trials_per_condition": TRIALS,
        "scenarios": list(SCENARIOS),
        "k_grid": list(K_GRID), "h_grid": list(H_GRID),
        "variants": {
            "C": "bounded/damped transition scale",
            "E": "reset transition accumulators; capped scale afterwards",
            "F": "reset transition accumulators; actual uncapped scale afterwards",
        },
        "scoring": {
            "detector": "CUSUM only; P1/fused alerts excluded",
            "null_window": [QUIET_RANGE[1] + 1, MONTHS],
            "pre_onset_window": [QUIET_RANGE[1] + 1, ONSET - 1],
            "detection_window": [ONSET, MONTHS],
            "seeds_paired_across_parameter_cells": True,
        },
        "results": results,
    }


def main() -> int:
    report = run_sweep()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        scenario: {
            key: {
                variant: result.get("false_alarm_rate", result.get("sensitivity"))
                for variant, result in cell.items()
            }
            for key, cell in item["parameters"].items()
        }
        for scenario, item in report["results"].items()
    }
    print(json.dumps({"output": str(OUTPUT), "summary": compact}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
