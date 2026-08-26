from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.causal_inference_engine import BoundedCausalExplorationEngine

MATRIX = ROOT / "derived" / "annual_observed_matrix.csv"
REPORTS = ROOT / "reports"
PATTERNS = ROOT / "patterns"


def load_matrix() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with MATRIX.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    years = np.array([int(row["year"]) for row in rows])
    columns = [key for key in rows[0] if key != "year"]
    series: dict[str, np.ndarray] = {}
    for key in columns:
        observed = [row[key] for row in rows if row.get(key, "") != ""]
        if len(observed) == len(rows):
            series[key] = np.array([float(row[key]) for row in rows], dtype=float)
    return years, series


def transform(name: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    if name.endswith(("gdp_constant_usd", "energy_use_per_capita", "population")):
        if np.any(values <= 0):
            raise ValueError(f"non-positive values cannot receive log differences: {name}")
        return np.diff(np.log(values)), "log_difference"
    return values.copy(), "observed_level"


years, raw = load_matrix()
series: dict[str, np.ndarray] = {}
transformations: dict[str, str] = {}
for name, values in raw.items():
    series[name], transformations[name] = transform(name, values)
common = min(len(values) for values in series.values())
series = {name: values[-common:] for name, values in series.items()}
years = years[-common:]
variables = sorted(series)

experiment_id = "real-annual-10000-surrogate-grid-20260825"
engine = BoundedCausalExplorationEngine(experiment_id, alpha=0.01, random_seed=20260825)
raw_edges: list[dict[str, object]] = []
for source in variables:
    for target in variables:
        if source == target:
            continue
        metrics = engine.execute_circular_permutation_test(series[source], series[target], max_lag=5, num_surrogates=10_000)
        for metric in metrics:
            raw_edges.append({
                "edge_id": f"{source}->{target}@{metric.lag}y",
                "source_variable": source,
                "target_variable": target,
                "metrics": asdict(metric),
            })
results = engine.apply_benjamini_hochberg_fdr(raw_edges, stability_delta_max=0.35, q_threshold=0.01)

REPORTS.mkdir(exist_ok=True)
for status, values in (("validated", engine.validated_registry), ("rejected", engine.rejected_registry)):
    path = PATTERNS / ("candidate" if status == "validated" else "rejected") / "real_10000_patterns.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for result in values:
            handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")

(PATTERNS / "golden" / "real_10000_patterns.jsonl").write_text("", encoding="utf-8")
(REPORTS / "real_10000_grid_results.json").write_text(
    json.dumps(
        {
            "experiment_id": experiment_id,
            "years": [int(years.min()), int(years.max())],
            "variables": variables,
            "transformations": transformations,
            "candidate_lag_range": {"min": 0, "max": 5, "unit": "years"},
            "surrogate": {"method": "circular_shift_train_only", "count_per_lag": 10_000, "seed": 20260825},
            "fdr": "Benjamini-Hochberg q<=0.01",
            "oos": {"train_end": 2017, "test_start": 2018},
            "results": [asdict(result) for result in results],
            "raw_mutation": False,
            "imputation": False,
            "interpretation": "validated_structural_pattern is not definitive physical causality",
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
(REPORTS / "real_10000_grid_summary.json").write_text(
    json.dumps(
        {
            "experiment_id": experiment_id,
            "tested_edges": len(results),
            "validated_structural_patterns": len(engine.validated_registry),
            "rejected_or_unstable_patterns": len(engine.rejected_registry),
            "golden_patterns": 0,
            "surrogates_per_lag": 10_000,
            "all_results_have_real_matrix_provenance": True,
            "note": "Annual observed sample is bounded; result is a controlled grid outcome, not a claim of global causal truth.",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"experiment_id={experiment_id} tested={len(results)} validated={len(engine.validated_registry)} rejected={len(engine.rejected_registry)}")
