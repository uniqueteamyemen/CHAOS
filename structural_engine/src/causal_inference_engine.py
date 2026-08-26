from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class LagMetric:
    lag: int
    train_score: float
    test_score: float
    stability_delta: float
    empirical_p_value: float
    surrogate_count: int
    train_n: int
    test_n: int
    interpretation: str = "temporal_dependence_candidate_not_causal_proof"


@dataclass(frozen=True)
class EdgeResult:
    edge_id: str
    experiment_id: str
    source_variable: str
    target_variable: str
    lag: int
    metrics: LagMetric
    fdr_q_value: float
    status: str
    rejection_reason: str | None = None


class BoundedCausalExplorationEngine:
    """Bounded exploratory engine; preserves time order and never makes causal claims."""

    def __init__(self, experiment_id: str, *, alpha: float = 0.01, random_seed: int = 42) -> None:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be between zero and one")
        self.experiment_id = experiment_id
        self.alpha = alpha
        self.random_seed = random_seed
        self.validated_registry: list[EdgeResult] = []
        self.rejected_registry: list[EdgeResult] = []

    @staticmethod
    def _corr(x: np.ndarray, y: np.ndarray) -> float:
        if len(x) < 3 or len(x) != len(y) or np.std(x) == 0 or np.std(y) == 0:
            return float("nan")
        return float(np.corrcoef(x, y)[0, 1])

    def execute_circular_permutation_test(
        self,
        x: Iterable[float],
        y: Iterable[float],
        *,
        max_lag: int,
        num_surrogates: int = 10_000,
        train_fraction: float = 0.7,
    ) -> list[LagMetric]:
        x_arr = np.asarray(list(x), dtype=float)
        y_arr = np.asarray(list(y), dtype=float)
        if x_arr.ndim != 1 or y_arr.ndim != 1 or len(x_arr) != len(y_arr):
            raise ValueError("x and y must be equal-length one-dimensional series")
        if max_lag < 0 or num_surrogates < 1 or not 0.5 <= train_fraction < 1:
            raise ValueError("invalid lag, surrogate budget, or train fraction")
        if len(x_arr) <= max_lag:
            return []
        if not np.isfinite(x_arr).all() or not np.isfinite(y_arr).all():
            raise ValueError("raw missing values must be removed by an explicit observed-only alignment before this method")

        rng = np.random.default_rng(self.random_seed)
        metrics: list[LagMetric] = []
        for lag in range(max_lag + 1):
            x_lagged = x_arr[: len(x_arr) - lag] if lag else x_arr
            y_sliced = y_arr[lag:] if lag else y_arr
            split = int(len(x_lagged) * train_fraction)
            x_train, x_test = x_lagged[:split], x_lagged[split:]
            y_train, y_test = y_sliced[:split], y_sliced[split:]
            if min(len(x_train), len(x_test)) < 3:
                continue
            observed = self._corr(x_train, y_train)
            test_score = self._corr(x_test, y_test)
            if not np.isfinite(observed):
                continue
            null_scores: list[float] = []
            for _ in range(num_surrogates):
                shift = int(rng.integers(1, len(x_train)))
                surrogate = np.roll(x_train, shift)
                score = self._corr(surrogate, y_train)
                if np.isfinite(score):
                    null_scores.append(abs(score))
            if not null_scores:
                continue
            empirical_p = (1 + sum(score >= abs(observed) for score in null_scores)) / (len(null_scores) + 1)
            metrics.append(
                LagMetric(
                    lag=lag,
                    train_score=float(observed),
                    test_score=float(test_score) if np.isfinite(test_score) else 0.0,
                    stability_delta=float(abs(observed - test_score)) if np.isfinite(test_score) else float("inf"),
                    empirical_p_value=float(empirical_p),
                    surrogate_count=len(null_scores),
                    train_n=len(x_train),
                    test_n=len(x_test),
                )
            )
        return metrics

    def apply_benjamini_hochberg_fdr(
        self,
        edges: list[dict[str, object]],
        *,
        stability_delta_max: float = 0.35,
        q_threshold: float | None = None,
    ) -> list[EdgeResult]:
        if q_threshold is None:
            q_threshold = self.alpha
        if not edges:
            return []
        p_values = [float(edge["metrics"]["empirical_p_value"]) for edge in edges]  # type: ignore[index]
        ordered = sorted(enumerate(p_values), key=lambda pair: pair[1])
        q_values = [1.0] * len(p_values)
        running = 1.0
        for rank, (index, p_value) in reversed(list(enumerate(ordered, start=1))):
            running = min(running, p_value * len(p_values) / rank)
            q_values[index] = min(1.0, running)

        outputs: list[EdgeResult] = []
        for index, edge in enumerate(edges):
            metric_dict = edge["metrics"]
            metric = LagMetric(**metric_dict)  # type: ignore[arg-type]
            passed = q_values[index] <= q_threshold and metric.stability_delta <= stability_delta_max and metric.test_n >= 3
            result = EdgeResult(
                edge_id=str(edge["edge_id"]),
                experiment_id=self.experiment_id,
                source_variable=str(edge["source_variable"]),
                target_variable=str(edge["target_variable"]),
                lag=metric.lag,
                metrics=metric,
                fdr_q_value=float(q_values[index]),
                status="validated_structural_pattern" if passed else "rejected_spurious_or_unstable",
                rejection_reason=None if passed else "Failed BH-FDR, OOS stability, or minimum test support",
            )
            outputs.append(result)
            (self.validated_registry if passed else self.rejected_registry).append(result)
        return outputs

    @staticmethod
    def write_registry(results: list[EdgeResult], path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
