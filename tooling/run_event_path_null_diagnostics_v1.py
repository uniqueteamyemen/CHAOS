#!/usr/bin/env python3
"""Targeted Event-Path null diagnostics; no new null family is introduced."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS = ROOT / "experiments/event_path_prototype_v1/PREDICTIONS.jsonl"
DEFAULT_OUTPUT = ROOT / "experiments/event_path_prototype_v1/NULL_DIAGNOSTICS_V1.json"


def accuracy(predicted: list[str], actual: list[str]) -> float:
    return sum(p == a for p, a in zip(predicted, actual)) / len(actual) if actual else 0.0


def p_value(null_scores: list[float], observed: float) -> float:
    return (1 + sum(score >= observed for score in null_scores)) / (len(null_scores) + 1)


def run(predictions: list[dict], repetitions: int, seed: int) -> dict:
    rng = random.Random(seed)
    predicted = [row["predicted_state"] for row in predictions]
    actual = [row["actual_state"] for row in predictions]
    observed = accuracy(predicted, actual)
    by_entity: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(predictions):
        by_entity[row["entity"]].append(i)

    event_outcome_scores: list[float] = []
    temporal_order_scores: list[float] = []
    path_identity_scores: list[float] = []
    for _ in range(repetitions):
        # Null 1: break event/path -> outcome association globally.
        shuffled_actual = actual.copy()
        rng.shuffle(shuffled_actual)
        event_outcome_scores.append(accuracy(predicted, shuffled_actual))

        # Null 2: preserve each entity's outcome distribution, break temporal order.
        shifted_actual = actual.copy()
        for indices in by_entity.values():
            if len(indices) > 1:
                offset = rng.randrange(len(indices))
                values = [actual[i] for i in indices]
                values = values[offset:] + values[:offset]
                for i, value in zip(indices, values):
                    shifted_actual[i] = value
        temporal_order_scores.append(accuracy(predicted, shifted_actual))

        # Null 3: preserve the prediction label distribution within entity, break path identity.
        identity_broken = predicted.copy()
        for indices in by_entity.values():
            values = [predicted[i] for i in indices]
            rng.shuffle(values)
            for i, value in zip(indices, values):
                identity_broken[i] = value
        path_identity_scores.append(accuracy(identity_broken, actual))

    def summarize(name: str, scores: list[float], question: str) -> dict:
        return {
            "null_id": name,
            "question": question,
            "repetitions": repetitions,
            "observed_accuracy": observed,
            "null_mean": statistics.fmean(scores),
            "null_std": statistics.pstdev(scores),
            "null_p95": sorted(scores)[int(0.95 * (len(scores) - 1))],
            "empirical_p_value_ge_observed": p_value(scores, observed),
            "interpretation": "diagnostic_only",
        }

    return {
        "contract": "targeted-three-null-v1",
        "seed": seed,
        "prediction_count": len(predictions),
        "observed": {"accuracy": observed},
        "nulls": [
            summarize("break_event_outcome_association", event_outcome_scores, "هل يختفي التفوق عند كسر علاقة الحدث بالنتيجة؟"),
            summarize("break_temporal_order", temporal_order_scores, "هل يعتمد التفوق على الترتيب الزمني؟"),
            summarize("break_path_identity", path_identity_scores, "هل يعتمد التفوق على هوية الـPath؟"),
        ],
        "decision_rule": "لا نفتح عائلة Null جديدة؛ نثبت الحكم على Event-Path فقط بعد قراءة هذه التشخيصات الثلاثة.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repetitions", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260828)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = run(rows, args.repetitions, args.seed)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
