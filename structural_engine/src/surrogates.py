from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np


@dataclass(frozen=True)
class SurrogateResult:
    method: str
    observed_score: float
    null_scores: tuple[float, ...]
    empirical_p_value: float
    budget: int


def circular_shift(values: np.ndarray, shift: int) -> np.ndarray:
    if values.ndim != 1:
        raise ValueError("circular_shift expects a one-dimensional series")
    return np.roll(values, shift)


def block_permutation(values: np.ndarray, *, block_size: int, permutation: np.ndarray) -> np.ndarray:
    if values.ndim != 1:
        raise ValueError("block_permutation expects a one-dimensional series")
    if block_size < 1:
        raise ValueError("block_size must be positive")
    blocks = [values[start : start + block_size] for start in range(0, len(values), block_size)]
    if sorted(permutation.tolist()) != list(range(len(blocks))):
        raise ValueError("permutation must contain each block index exactly once")
    return np.concatenate([blocks[index] for index in permutation])[: len(values)]


def empirical_p_value(observed: float, null_scores: Iterable[float], *, greater_is_more_extreme: bool = True) -> float:
    scores = list(null_scores)
    if not scores:
        raise ValueError("null distribution cannot be empty")
    if greater_is_more_extreme:
        extreme = sum(score >= observed for score in scores)
    else:
        extreme = sum(score <= observed for score in scores)
    return (extreme + 1) / (len(scores) + 1)


def validate_with_surrogates(
    *,
    source: np.ndarray,
    target: np.ndarray,
    score_fn: Callable[[np.ndarray, np.ndarray], float],
    method: str = "circular_shift",
    budget: int = 1000,
    block_size: int = 7,
) -> SurrogateResult:
    if source.ndim != 1 or target.ndim != 1 or len(source) != len(target):
        raise ValueError("source and target must be one-dimensional arrays with equal lengths")
    if len(source) < 4:
        raise ValueError("at least four observations are required")
    if budget < 1:
        raise ValueError("budget must be positive")
    observed = float(score_fn(source, target))
    null_scores: list[float] = []
    if method == "circular_shift":
        for shift in range(1, budget + 1):
            null_scores.append(float(score_fn(circular_shift(source, shift % len(source)), target)))
    elif method == "block_permutation":
        # Deterministic cyclic block order provides a reproducible null without a hidden RNG.
        block_count = (len(source) + block_size - 1) // block_size
        base = np.arange(block_count)
        for offset in range(1, budget + 1):
            order = np.roll(base, offset % block_count)
            null_scores.append(float(score_fn(block_permutation(source, block_size=block_size, permutation=order), target)))
    else:
        raise ValueError("method must be circular_shift or block_permutation")
    return SurrogateResult(
        method=method,
        observed_score=observed,
        null_scores=tuple(null_scores),
        empirical_p_value=empirical_p_value(observed, null_scores),
        budget=budget,
    )
