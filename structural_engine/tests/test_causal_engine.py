from __future__ import annotations

import numpy as np

from src.causal_inference_engine import BoundedCausalExplorationEngine


def test_synthetic_engine_executes_full_surrogate_budget() -> None:
    rng = np.random.default_rng(123)
    x = rng.normal(size=80)
    y = 0.6 * np.roll(x, 2) + rng.normal(scale=1.2, size=80)
    engine = BoundedCausalExplorationEngine("synthetic-engine-smoke", random_seed=7)
    metrics = engine.execute_circular_permutation_test(x, y, max_lag=5, num_surrogates=10_000)
    assert len(metrics) == 6
    assert all(metric.surrogate_count == 10_000 for metric in metrics)
    assert all(metric.test_n >= 3 for metric in metrics)


def test_synthetic_edges_are_segregated_after_fdr() -> None:
    rng = np.random.default_rng(9)
    x = rng.normal(size=60)
    y = np.roll(x, 1) + rng.normal(scale=0.5, size=60)
    engine = BoundedCausalExplorationEngine("synthetic-fdr-smoke", random_seed=11)
    metrics = engine.execute_circular_permutation_test(x, y, max_lag=2, num_surrogates=1_000)
    edges = [
        {
            "edge_id": f"e-{metric.lag}",
            "source_variable": "x",
            "target_variable": "y",
            "metrics": metric.__dict__,
        }
        for metric in metrics
    ]
    results = engine.apply_benjamini_hochberg_fdr(edges)
    assert len(results) == len(metrics)
    assert len(engine.validated_registry) + len(engine.rejected_registry) == len(results)
    assert all(result.fdr_q_value >= 0 for result in results)
