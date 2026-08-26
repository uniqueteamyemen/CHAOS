from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiment_grid import deterministic_experiment_id
from src.surrogates import empirical_p_value

MATRIX = ROOT / "derived" / "annual_observed_matrix.csv"
REPORTS = ROOT / "reports"
PATTERNS = ROOT / "patterns"
REPORTS.mkdir(exist_ok=True)
for status in ("candidate", "rejected", "golden"):
    (PATTERNS / status).mkdir(parents=True, exist_ok=True)


def load_matrix() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with MATRIX.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    years = np.array([int(row["year"]) for row in rows])
    columns = [key for key in rows[0] if key != "year"]
    series = {key: np.array([float(row[key]) for row in rows if row.get(key, "") != ""], dtype=float) for key in columns}
    return years, series


def transform(name: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    if name.endswith("gdp_constant_usd") or name.endswith("energy_use_per_capita") or name.endswith("population"):
        if np.any(values <= 0):
            raise ValueError(f"cannot log-transform non-positive values for {name}")
        return np.diff(np.log(values)), "log_difference"
    if name.endswith("inflation_cpi"):
        return values.copy(), "level_rate"
    return values.copy(), "observed_level"


def lag_score(source: np.ndarray, target: np.ndarray, lag: int) -> tuple[float, int]:
    if lag == 0:
        left, right = source, target
    else:
        left, right = source[:-lag], target[lag:]
    mask = np.isfinite(left) & np.isfinite(right)
    left, right = left[mask], right[mask]
    if len(left) < 4 or np.std(left) == 0 or np.std(right) == 0:
        return float("nan"), len(left)
    return float(np.corrcoef(left, right)[0, 1]), len(left)


def circular_null(source: np.ndarray, target: np.ndarray, lag: int) -> list[float]:
    # Enumerate all non-zero shifts exactly for the short annual sample; no RNG is used.
    scores: list[float] = []
    for shift in range(1, len(source)):
        score, _ = lag_score(np.roll(source, shift), target, lag)
        if math.isfinite(score):
            scores.append(score)
    return scores


def bh_fdr(p_values: list[float]) -> list[float]:
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * len(p_values)
    running = 1.0
    n = len(p_values)
    for rank_from_one, (index, p_value) in reversed(list(enumerate(indexed, start=1))):
        running = min(running, p_value * n / rank_from_one)
        adjusted[index] = min(1.0, running)
    return adjusted


years, raw_series = load_matrix()
transformed: dict[str, np.ndarray] = {}
transformation_log: dict[str, str] = {}
for name, values in raw_series.items():
    transformed[name], transformation_log[name] = transform(name, values)

# Derived transformations remove the first year for differenced variables; align by common derived years only.
common_length = min(len(values) for values in transformed.values())
transformed = {name: values[-common_length:] for name, values in transformed.items()}
aligned_years = years[-common_length:]
train_mask = aligned_years <= 2017
test_mask = aligned_years >= 2018
variables = sorted(transformed)
config = {
    "variables": variables,
    "native_frequency": "annual",
    "alignment": "inner_join_common_observed_years_only",
    "transformations": transformation_log,
    "lags": {"min": 0, "max": 5, "unit": "years"},
    "surrogate": {"method": "exact_nonzero_circular_shifts", "budget": common_length - 1},
    "multiple_testing": "Benjamini-Hochberg-FDR",
    "train_test": {"train": "2000-2017", "test": "2018-2025"},
}
experiment_id = deterministic_experiment_id("annual_lag_grid_observed", config)
results: list[dict[str, object]] = []
for source_name in variables:
    for target_name in variables:
        if source_name == target_name:
            continue
        for lag in range(0, 6):
            score, n = lag_score(transformed[source_name], transformed[target_name], lag)
            if not math.isfinite(score) or n < 4:
                continue
            null_scores = circular_null(transformed[source_name], transformed[target_name], lag)
            p_value = empirical_p_value(abs(score), [abs(value) for value in null_scores])
            train_score, train_n = lag_score(transformed[source_name][train_mask], transformed[target_name][train_mask], lag)
            test_score, test_n = lag_score(transformed[source_name][test_mask], transformed[target_name][test_mask], lag)
            results.append({
                "experiment_id": experiment_id,
                "source": source_name,
                "target": target_name,
                "lag": lag,
                "lag_unit": "years",
                "score": score,
                "absolute_score": abs(score),
                "empirical_p_value": p_value,
                "surrogate_method": "exact_nonzero_circular_shifts",
                "surrogate_count": len(null_scores),
                "full_n": n,
                "train_score": train_score if math.isfinite(train_score) else None,
                "train_n": train_n,
                "test_score": test_score if math.isfinite(test_score) else None,
                "test_n": test_n,
                "interpretation": "temporal_dependence_candidate_not_causal_proof",
            })

q_values = bh_fdr([float(row["empirical_p_value"]) for row in results]) if results else []
for row, q_value in zip(results, q_values):
    row["fdr_q_value"] = q_value
    row["validation_status"] = "candidate" if q_value < 0.05 and row["test_n"] >= 4 else "rejected"

out_path = REPORTS / "lag_grid_results.json"
out_path.write_text(json.dumps({"experiment_id": experiment_id, "config": config, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for status, selected in (("candidate", [r for r in results if r["validation_status"] == "candidate"]), ("rejected", [r for r in results if r["validation_status"] == "rejected"])):
    path = PATTERNS / status / "patterns.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in selected:
            record = {
                "pattern_id": f"{experiment_id}:{row['source']}->{row['target']}@{row['lag']}y",
                "pattern_version": "1",
                "status": status,
                "path_nodes": [row["source"], row["target"]],
                "edge": row,
                "experiment_id": experiment_id,
                "provenance": {
                    "matrix": str(MATRIX),
                    "transformations": transformation_log,
                    "raw_mutation": False,
                },
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

(PATTERNS / "golden" / "patterns.jsonl").write_text("", encoding="utf-8")
(REPORTS / "lag_grid_summary.json").write_text(
    json.dumps(
        {
            "experiment_id": experiment_id,
            "candidate_count": sum(row["validation_status"] == "candidate" for row in results),
            "rejected_count": sum(row["validation_status"] == "rejected" for row in results),
            "golden_count": 0,
            "reason_golden_empty": "No edge is promoted by this bounded exploratory grid; validation is descriptive and annual sample is short.",
            "raw_mutation": False,
            "imputation": False,
            "fdr": "Benjamini-Hochberg-FDR",
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"experiment_id={experiment_id} results={len(results)} candidates={sum(row['validation_status'] == 'candidate' for row in results)} rejected={sum(row['validation_status'] == 'rejected' for row in results)}")
