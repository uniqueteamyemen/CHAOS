#!/usr/bin/env python3
"""Structure-preserving magnitude permutation null for the frozen seismic Event-Path test."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "structural_engine"))
from src.event_path_engine import (  # noqa: E402
    USGSGeoJSONAdapter,
    EventPathEngine,
    build_states,
    build_transitions,
    build_windows,
    build_paths,
)

INPUT = ROOT / "data/raw/seismic_gulf_of_aden_v1/usgs_gulf_of_aden_query.geojson"
OUTPUT = ROOT / "experiments/seismic_transfer_test_v1/SEISMIC_STRUCTURE_NULL_V1.json"


def run(repetitions: int, seed: int, input_path: Path = INPUT) -> dict:
    dataset = USGSGeoJSONAdapter().load(input_path)
    engine = EventPathEngine(window_width=3, min_support=2, max_path_length=6)
    real_states = build_states(dataset.events)
    real_predictions, real_metrics = engine.rolling_oos_frozen(real_states, dataset.events, train_size=8)
    real_path = real_metrics["path_model"]["accuracy"]
    real_majority = real_metrics["majority_baseline"]["accuracy"]
    real_lift = real_path - real_majority
    rng = random.Random(seed)
    magnitudes = [event.value for event in dataset.events]
    path_scores: list[float] = []
    majority_scores: list[float] = []
    lifts: list[float] = []
    coverages: list[float] = []
    for _ in range(repetitions):
        shuffled = magnitudes.copy()
        rng.shuffle(shuffled)
        surrogate_events = [replace(event, value=value) for event, value in zip(dataset.events, shuffled)]
        states = build_states(surrogate_events)
        transitions = build_transitions(surrogate_events, states)
        windows = build_windows(surrogate_events, states, width=3)
        _ = build_paths(windows, states, transitions)
        _, metrics = engine.rolling_oos_frozen(states, surrogate_events, train_size=8)
        path = metrics["path_model"]["accuracy"]
        majority = metrics["majority_baseline"]["accuracy"]
        coverages.append(metrics["path_model"].get("coverage", 0.0))
        path_scores.append(path)
        majority_scores.append(majority)
        lifts.append(path - majority)

    def p_ge(values: list[float], observed: float) -> float:
        return (1 + sum(value >= observed for value in values)) / (len(values) + 1)

    def summary(values: list[float], observed: float) -> dict[str, float]:
        ordered = sorted(values)
        return {"observed": observed, "null_mean": statistics.fmean(values), "null_std": statistics.pstdev(values), "null_p95": ordered[int(0.95 * (len(values) - 1))], "empirical_p_value_ge_observed": p_ge(values, observed)}

    return {
        "contract": "seismic-structure-null-v1",
        "source_sha256": dataset.source_sha256,
        "repetitions": repetitions,
        "seed": seed,
        "preserved": ["event_count", "UTC_timestamps", "inter_event_intervals", "entity", "magnitude_multiset", "geographic_attributes"],
        "broken": ["magnitude-to-time/order association", "magnitude-derived state sequence", "path-to-outcome alignment"],
        "pipeline": {"window_width": 3, "train_size": 8, "min_support": 2, "same_event_path_code": True},
        "observed": {"path_accuracy": real_path, "majority_accuracy": real_majority, "lift": real_lift, "n": len(real_predictions)},
        "null": {"path_accuracy": summary(path_scores, real_path), "majority_accuracy": summary(majority_scores, real_majority), "lift": summary(lifts, real_lift), "coverage": {"observed": real_metrics["path_model"].get("coverage", 0.0), "null_mean": statistics.fmean(coverages), "null_std": statistics.pstdev(coverages), "null_min": min(coverages), "null_max": max(coverages)}},
        "primary_test": "empirical p-value for observed Event-Path lift over Majority baseline",
        "interpretation_rule": "real lift outside the null distribution supports an initial predictive signal; otherwise evidence is insufficient",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = run(args.repetitions, args.seed, args.input)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
