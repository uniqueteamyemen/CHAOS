"""Stable adapter for the frozen B-v7.1 structural break detectors.

The underlying Fast and Markov implementations are copied verbatim from the
B-v6.1 and B-v7.1 experiment sources. This adapter only normalizes lifecycle
semantics; it does not change detector mathematics.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .engine_fast_ref import SurgicalFactorEngineB61
from .engine_markov_cusum import InnovationSignCusumEngineB7

DEFAULT_MARKOV_THRESHOLD = 8.5
CONSENSUS_MATCH_WINDOW = 35


def _fast_engine() -> SurgicalFactorEngineB61:
    return SurgicalFactorEngineB61(
        quiet_end=40,
        window_size=12,
        anomaly_z_thresh=3.8,
        winsor_cap=1.8,
        break_percent_thresh=85.0,
        resolution_horizon=14,
        return_to_baseline_z=1.5,
        persistence_z_thresh=1.45,
        correlation_method="pearson",
        innovation_drain=True,
        persistence_floor=False,
        heuristic_scale_guard=False,
    )


def _markov_engine(threshold: float) -> InnovationSignCusumEngineB7:
    return InnovationSignCusumEngineB7(
        quiet_end=40,
        window_size=12,
        anomaly_z_thresh=3.8,
        winsor_cap=1.8,
        cusum_threshold=threshold,
        structural_rho_bias_correction=True,
        resolution_horizon=14,
        return_to_baseline_z=1.5,
        persistence_z_thresh=1.45,
        correlation_method="pearson",
        innovation_drain=True,
        persistence_floor=False,
        heuristic_scale_guard=False,
    )


def _pair_consensus_events(
    provisional_events: list[dict[str, Any]],
    markov_events: list[dict[str, Any]],
    match_window: int = CONSENSUS_MATCH_WINDOW,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One-to-one, same-direction, forward-only event matching."""
    ordered_markov = sorted(
        enumerate(markov_events), key=lambda pair: int(pair[1]["detection_time"])
    )
    consumed: set[int] = set()
    confirmed: list[dict[str, Any]] = []
    unconfirmed: list[dict[str, Any]] = []

    for provisional in sorted(
        provisional_events, key=lambda event: int(event["detection_time"])
    ):
        onset_time = int(provisional["detection_time"])
        direction = int(provisional["direction"])
        partner = next(
            (
                (index, event)
                for index, event in ordered_markov
                if index not in consumed
                and int(event["direction"]) == direction
                and 0 <= int(event["detection_time"]) - onset_time <= match_window
            ),
            None,
        )
        if partner is None:
            unconfirmed.append({**provisional, "status": "PROVISIONAL"})
            continue

        index, event = partner
        consumed.add(index)
        confirmation_time = int(event["detection_time"])
        confirmed.append(
            {
                **provisional,
                "status": "CONFIRMED",
                "provisional_detection_time": onset_time,
                "detection_time": confirmation_time,
                "confirmation_time": confirmation_time,
                "confirmation_delay": confirmation_time - onset_time,
            }
        )
    return confirmed, unconfirmed


def _consensus_result(
    fast_result: dict[str, Any], markov_result: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    confirmed, provisional = _pair_consensus_events(
        fast_result["structural_breaks"], markov_result["structural_breaks"]
    )

    unconfirmed_pending: list[dict[str, Any]] = []
    for event in provisional:
        for pending in event.get("resolved_pending_alerts", []):
            unconfirmed_pending.append(
                {
                    **pending,
                    "status": "UNRESOLVED_UNCONFIRMED_PROVISIONAL",
                    "provisional_break_time": int(event["detection_time"]),
                    "provisional_direction": int(event["direction"]),
                }
            )

    result = dict(fast_result)
    result["structural_breaks"] = confirmed
    result["unresolved_alerts"] = [
        *fast_result["unresolved_alerts"],
        *unconfirmed_pending,
    ]

    lifecycle = dict(fast_result["pending_lifecycle"])
    lifecycle["resolved_structural_count"] = sum(
        len(event.get("resolved_pending_alerts", [])) for event in confirmed
    )
    lifecycle["unresolved_count"] = (
        int(lifecycle["unresolved_count"]) + len(unconfirmed_pending)
    )
    terminal = (
        int(lifecycle["resolved_structural_count"])
        + int(lifecycle["resolved_transient_count"])
        + int(lifecycle["unresolved_count"])
    )
    lifecycle["accounting_complete"] = int(lifecycle["opened_count"]) == terminal
    if not lifecycle["accounting_complete"]:
        raise AssertionError(
            "consensus_pending_lifecycle_accounting_mismatch:"
            f"opened={lifecycle['opened_count']},terminal={terminal}"
        )

    result["pending_lifecycle"] = lifecycle
    result["diagnostics"] = {
        **fast_result.get("diagnostics", {}),
        "provisional_count": len(fast_result["structural_breaks"]),
        "confirmed_count": len(confirmed),
        "unconfirmed_provisional_count": len(provisional),
        "unconfirmed_pending_reclassified": len(unconfirmed_pending),
        "markov_confirmation_matching": "one_to_one",
        "consensus_match_window_steps": CONSENSUS_MATCH_WINDOW,
        "promotion_rate_pct": round(
            100 * len(confirmed) / len(fast_result["structural_breaks"]), 2
        )
        if fast_result["structural_breaks"]
        else 0.0,
    }
    return result, provisional


class BreakDetectorV1:
    """Unified entry point: fast, markov_cusum, or consensus."""

    MODES = ("fast", "markov_cusum", "consensus")

    def __init__(
        self, mode: str = "markov_cusum", markov_threshold: float = DEFAULT_MARKOV_THRESHOLD
    ) -> None:
        if mode not in self.MODES:
            raise ValueError(f"unsupported_mode:{mode}; expected_one_of:{self.MODES}")
        if not np.isfinite(markov_threshold) or markov_threshold <= 0:
            raise ValueError("markov_threshold_must_be_finite_and_positive")
        self.mode = mode
        self.markov_threshold = float(markov_threshold)

    def analyze(self, series: np.ndarray | list[float]) -> dict[str, Any]:
        values = np.asarray(series, dtype=float)
        if values.ndim != 1:
            raise ValueError("series_must_be_one_dimensional")
        if not np.all(np.isfinite(values)):
            raise ValueError("series_contains_nonfinite_values")
        if values.size < 52:
            raise ValueError("series_too_short_for_quiet_and_window:min_length=52")

        provisional: list[dict[str, Any]] = []
        if self.mode == "fast":
            result = _fast_engine().analyze(values)
            result["structural_breaks"] = [
                {**event, "status": "PROVISIONAL"}
                for event in result["structural_breaks"]
            ]
            provisional = list(result["structural_breaks"])
        elif self.mode == "markov_cusum":
            result = _markov_engine(self.markov_threshold).analyze(values)
            result["structural_breaks"] = [
                {**event, "status": "CONFIRMED"}
                for event in result["structural_breaks"]
            ]
        else:
            fast_result = _fast_engine().analyze(values)
            markov_result = _markov_engine(self.markov_threshold).analyze(values)
            result, provisional = _consensus_result(fast_result, markov_result)

        transient = [
            {**event, "status": "TRANSIENT"}
            for event in result["transient_anomalies"]
        ]
        unresolved = [
            {**event, "status": "UNRESOLVED"}
            for event in result["unresolved_alerts"]
        ]
        result["transient_anomalies"] = transient
        result["unresolved_alerts"] = unresolved
        result["provisional_events"] = provisional
        result["confirmed_events"] = [
            event
            for event in result["structural_breaks"]
            if event.get("status") == "CONFIRMED"
        ]
        result["events"] = sorted(
            [
                *provisional,
                *result["confirmed_events"],
                *transient,
                *unresolved,
            ],
            key=lambda event: int(
                event.get(
                    "detection_time",
                    event.get("time", event.get("provisional_detection_time", 0)),
                )
            ),
        )
        result["schema_version"] = "1.0"
        result["detector_version"] = "isolated_break_detector_v1"
        result["mode"] = self.mode
        result["markov_threshold"] = self.markov_threshold
        return result
