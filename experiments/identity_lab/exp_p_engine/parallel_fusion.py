"""Isolated P-engine A/B/C experiment: independent detectors, aggregation and event fusion.

A is the unchanged production engine. B and C are experimental candidates and
must not replace A until the paired benchmark supports that decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from typing import Any

from . import engine as production_engine


@dataclass(frozen=True)
class ExecutionSnapshot:
    snapshot_id: str
    code_revision: str
    input_sha256: str
    input_count: int
    first_time: Any
    last_time: Any
    quiet_range: tuple[Any, Any]
    bias_frozen: float
    sigma_quiet: float
    config_json: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_series(series: list[dict[str, Any]]) -> None:
    if not series:
        raise ValueError("series_empty")
    previous = None
    for index, row in enumerate(series):
        if "month" not in row or "residual" not in row:
            raise ValueError("series_row_missing_month_or_residual")
        current = row["month"]
        try:
            if previous is not None and current <= previous:
                if current == previous:
                    raise ValueError("series_duplicate_timestamp")
                raise ValueError("series_timestamp_order_invalid")
        except TypeError as exc:
            raise ValueError("series_timestamps_not_comparable") from exc
        try:
            value = float(row["residual"])
        except (TypeError, ValueError) as exc:
            raise ValueError("series_residual_not_numeric") from exc
        if not math.isfinite(value):
            raise ValueError("series_residual_not_finite")
        previous = current


def _snapshot(
    series: list[dict[str, Any]],
    quiet_range: tuple[Any, Any],
    bias: float,
    sigma_quiet: float,
    config: dict[str, Any],
    code_revision: str | None,
) -> ExecutionSnapshot:
    canonical_rows = [
        [str(row["month"]), float(row["residual"]).hex()]
        for row in series
    ]
    input_sha = hashlib.sha256(
        json.dumps(canonical_rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    revision = code_revision or os.getenv("GITHUB_SHA", "local-unpinned")
    payload = {
        "code_revision": revision,
        "input_sha256": input_sha,
        "quiet_range": [str(quiet_range[0]), str(quiet_range[1])],
        "bias_frozen": float(bias).hex(),
        "sigma_quiet": float(sigma_quiet).hex(),
        "config_json": config_json,
    }
    snapshot_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    return ExecutionSnapshot(
        snapshot_id=snapshot_id,
        code_revision=revision,
        input_sha256=input_sha,
        input_count=len(series),
        first_time=series[0]["month"],
        last_time=series[-1]["month"],
        quiet_range=(quiet_range[0], quiet_range[1]),
        bias_frozen=float(bias),
        sigma_quiet=float(sigma_quiet),
        config_json=config_json,
    )


def _two_sided_cusum(
    series: list[dict[str, Any]],
    bias: float,
    sigmas: list[float | None],
    transitions: list[bool],
    *,
    policy: str,
    sigma_cap: float,
    k_sigma: float,
    h_sigma: float,
    transition_damping: float,
) -> list[dict[str, Any]]:
    """Return positive and negative evidence without sharing accumulator state."""
    if policy not in {"hold_unbounded", "bounded_damped", "reset_unbounded"}:
        raise ValueError("cusum_transition_policy_invalid")
    positive = 0.0
    negative = 0.0
    hits: list[dict[str, Any]] = []
    for index, row in enumerate(series):
        raw_sigma = sigmas[index]
        if raw_sigma is None or raw_sigma <= 0:
            continue
        in_transition = transitions[index]
        if policy == "hold_unbounded" and in_transition:
            # Preserve both accumulators. A transient noise change must not erase evidence.
            continue
        if policy == "reset_unbounded" and in_transition:
            # Reset both directional tracks at the regime boundary, matching the
            # production engine's fail-closed transition behavior.
            positive = 0.0
            negative = 0.0
            continue
        scale = min(raw_sigma, sigma_cap) if policy == "bounded_damped" else raw_sigma
        gain = transition_damping if policy == "bounded_damped" and in_transition else 1.0
        z = float(row["residual"]) - bias
        positive = max(0.0, positive + gain * (z - k_sigma * scale))
        negative = max(0.0, negative + gain * (-z - k_sigma * scale))
        threshold = h_sigma * scale
        if positive > threshold:
            hits.append({
                "index": index, "time": row["month"], "detector": "cusum_positive",
                "priority": 2, "sign": 1, "magnitude": float(row["residual"]),
                "cusum_sigma": round(positive / scale, 4), "transition": in_transition,
            })
            positive = 0.0
        if negative > threshold:
            hits.append({
                "index": index, "time": row["month"], "detector": "cusum_negative",
                "priority": 2, "sign": -1, "magnitude": float(row["residual"]),
                "cusum_sigma": round(negative / scale, 4), "transition": in_transition,
            })
            negative = 0.0
    return hits


def fuse_events(
    series: list[dict[str, Any]],
    hits: list[dict[str, Any]],
    *,
    bias: float,
    calm_sigmas: list[float | None],
    sigma_quiet: float,
    entity: str,
    calm_k: float = 0.5,
    calm_periods: int = 6,
    cooldown: int = 26,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fuse same-event evidence; a reversal or a declared calm interval opens a new event.

    Cooldown is scoped to (event, detector, direction). Suppressed notifications
    remain in event evidence and are never deleted from the evidence record.
    """
    if calm_periods < 1 or cooldown < 0 or calm_k <= 0:
        raise ValueError("fusion_parameters_invalid")
    by_index: dict[int, list[dict[str, Any]]] = {}
    for hit in hits:
        by_index.setdefault(int(hit["index"]), []).append(hit)
    events: list[dict[str, Any]] = []
    cooldown_suppressed: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    calm_streak = 0
    for index, row in enumerate(series):
        sigma = calm_sigmas[index]
        scale = sigma if sigma is not None and sigma > 0 else sigma_quiet
        z = float(row["residual"]) - bias
        if abs(z) <= calm_k * scale:
            calm_streak += 1
        else:
            calm_streak = 0
        for hit in sorted(by_index.get(index, []), key=lambda item: item["priority"]):
            sign = int(hit["sign"])
            starts_new = (
                active is None
                or sign != active["sign"]
                or calm_streak >= calm_periods
            )
            if starts_new:
                active = {
                    "event_id": f"{entity}:{row['month']}:{'positive' if sign > 0 else 'negative'}",
                    "entity": entity,
                    "time": row["month"],
                    "end_time": row["month"],
                    "start_index": index,
                    "end_index": index,
                    "sign": sign,
                    "priority": int(hit["priority"]),
                    "detectors": [],
                    "max_abs_z": round(abs(z), 6),
                    "evidence": [],
                }
                events.append(active)
            key = (hit["detector"], sign)
            last_index = active.get("_last_by_detector_sign", {}).get(key)
            evidence = dict(hit)
            if last_index is not None and index - last_index < cooldown:
                evidence["notification_suppressed"] = "same_event_directional_cooldown"
                cooldown_suppressed.append({
                    "event_id": active["event_id"],
                    "index": index,
                    "detector": hit["detector"],
                    "sign": sign,
                    "reason": "same_event_directional_cooldown",
                })
            active.setdefault("_last_by_detector_sign", {})[key] = index
            active["evidence"].append(evidence)
            if hit["detector"] not in active["detectors"]:
                active["detectors"].append(hit["detector"])
            active["end_time"] = row["month"]
            active["end_index"] = index
            active["max_abs_z"] = max(active["max_abs_z"], round(abs(z), 6))
            active["priority"] = min(active["priority"], int(hit["priority"]))
            calm_streak = 0

    for event in events:
        event.pop("_last_by_detector_sign", None)
        event["evidence_count"] = len(event["evidence"])
        event["ambiguous_direction"] = any(
            other["start_index"] == event["start_index"] and other["sign"] != event["sign"]
            for other in events
        )
    return events, cooldown_suppressed


def _candidate(
    series: list[dict[str, Any]],
    *,
    bias: float,
    sigma_quiet: float,
    window: int,
    noise_gate_window: int,
    transition_ratio: float,
    sigma_ceiling_factor: float,
    k_sign: float,
    run_sign: int,
    k_cusum: float,
    h_cusum: float,
    transition_damping: float,
    p1_high_noise_handling: bool,
    p1_high_noise_factor: float,
    p1_high_noise_run: int,
    calm_k: float,
    calm_periods: int,
    cooldown: int,
    entity: str,
    policy: str,
) -> dict[str, Any]:
    ceiling = sigma_ceiling_factor * sigma_quiet
    sigmas_p1 = production_engine.rolling_sigma(series, window, ceiling=ceiling)
    sigmas_long = production_engine.rolling_sigma(series, window)
    sigmas_short = production_engine.rolling_sigma(series, noise_gate_window)
    transitions = [
        short is not None and long is not None and long > 0
        and short > transition_ratio * long
        for short, long in zip(sigmas_short, sigmas_long)
    ]

    # C keeps the experimental capped 3σ/3-run rule. D changes only P1's
    # response to a high-noise regime, reusing the production engine's
    # adaptive-scale + 13-directional-run policy. The CUSUM path is identical.
    p1_noise_threshold = p1_high_noise_factor * sigma_quiet
    if p1_high_noise_handling:
        p1_hits = production_engine.detect_sign_run(
            series, sigmas_p1, bias, k=k_sign, run_len=run_sign,
            adaptive_sigmas=sigmas_short, ceiling=p1_noise_threshold,
            high_noise_k=0.0, high_noise_run=p1_high_noise_run,
        )
    else:
        p1_hits = production_engine.detect_sign_run(
            series, sigmas_p1, bias, k=k_sign, run_len=run_sign
        )
    hits = []
    for hit in p1_hits:
        z = float(series[hit["index"]]["residual"]) - bias
        hits.append({
            "index": hit["index"], "time": hit["time"], "detector": "sign_run",
            "priority": 1, "sign": 1 if z > 0 else -1,
            "magnitude": float(hit["magnitude"]), "transition": transitions[hit["index"]],
            "noise_regime": bool(hit.get("noise_regime", False)),
        })
    hits.extend(_two_sided_cusum(
        series, bias, sigmas_long, transitions,
        policy=policy, sigma_cap=ceiling, k_sigma=k_cusum, h_sigma=h_cusum,
        transition_damping=transition_damping,
    ))
    hits.sort(key=lambda item: (item["index"], item["priority"], item["detector"]))
    events, cooldown_suppressed = fuse_events(
        series, hits, bias=bias, calm_sigmas=sigmas_long, sigma_quiet=sigma_quiet,
        entity=entity, calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
    )
    alerts = [{
        "time": event["time"], "entity": entity, "priority": event["priority"],
        "detector": "fusion", "sign": event["sign"], "event_id": event["event_id"],
        "evidence_count": event["evidence_count"], "detectors": event["detectors"],
        "ambiguous_direction": event["ambiguous_direction"],
    } for event in events]
    p1_high_noise = sum(
        1 for sigma in sigmas_short if sigma is not None and sigma > p1_noise_threshold
    )
    return {
        "policy": policy,
        "alerts": alerts,
        "events": events,
        "raw_hits": hits,
        "cooldown_suppressed": cooldown_suppressed,
        "diagnostics": {
            "transition_periods": sum(transitions),
            "p1_high_noise_periods": p1_high_noise,
            "p1_adaptive_high_noise_periods": sum(
                sigma is not None and sigma > p1_noise_threshold for sigma in sigmas_short
            ),
            "p1_mode": "production_adaptive_13_run" if p1_high_noise_handling else "capped_3sigma_3run",
            "cusum_positive_hits": sum(h["detector"] == "cusum_positive" for h in hits),
            "cusum_negative_hits": sum(h["detector"] == "cusum_negative" for h in hits),
            "p1_hits": len(p1_hits),
            "event_count": len(events),
            "sigma_cusum_policy": (
                "unbounded_hold" if policy == "hold_unbounded"
                else "unbounded_reset" if policy == "reset_unbounded"
                else "capped_damped"
            ),
        },
    }


def run_candidates(
    domain: str,
    rows: list[dict[str, Any]],
    *,
    quiet_range: tuple[Any, Any],
    entity: str = "E",
    window: int = 52,
    noise_gate_window: int = 12,
    transition_ratio: float = 1.2,
    sigma_ceiling_factor: float = 2.0,
    k_sign: float = 3.0,
    run_sign: int = 3,
    k_cusum: float = 0.5,
    h_cusum: float = 8.5,
    transition_damping: float = 0.35,
    calm_k: float = 0.5,
    calm_periods: int = 6,
    cooldown: int = 26,
    p1_high_noise_factor: float = 1.5,
    p1_high_noise_run: int = 13,
    h_cusum_f: float = 10.5,
    h_cusum_g: float = 12.5,
    h_cusum_i: float = 16.5,
    code_revision: str | None = None,
) -> dict[str, Any]:
    """Run unchanged production A plus independent B/C candidates on identical input."""
    if not isinstance(window, int) or window < 8:
        raise ValueError("window_must_be_integer_at_least_8")
    if not isinstance(noise_gate_window, int) or noise_gate_window < 8:
        raise ValueError("noise_gate_window_must_be_integer_at_least_8")
    for name, value in {
        "transition_ratio": transition_ratio,
        "sigma_ceiling_factor": sigma_ceiling_factor,
        "k_sign": k_sign,
        "k_cusum": k_cusum,
        "h_cusum": h_cusum,
        "h_cusum_f": h_cusum_f,
        "h_cusum_g": h_cusum_g,
        "h_cusum_i": h_cusum_i,
        "transition_damping": transition_damping,
        "calm_k": calm_k,
        "p1_high_noise_factor": p1_high_noise_factor,
    }.items():
        if not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError(f"{name}_must_be_finite_and_positive")
    if transition_ratio <= 1 or sigma_ceiling_factor <= 0 or transition_damping > 1:
        raise ValueError("candidate_parameter_out_of_range")
    if (run_sign < 1 or calm_periods < 1 or cooldown < 0 or p1_high_noise_run < 1
            or p1_high_noise_factor <= 1):
        raise ValueError("candidate_integer_parameter_out_of_range")

    series = production_engine.residuals(rows, domain)
    validate_series(series)
    bias = production_engine.frozen_bias(series, quiet_range)
    quiet_values = [
        row["residual"] for row in series
        if quiet_range[0] <= row["month"] <= quiet_range[1]
    ]
    sigma_quiet = production_engine.mad_sigma(quiet_values)
    if not math.isfinite(sigma_quiet) or sigma_quiet <= 0:
        raise ValueError("quiet_sigma_must_be_positive")

    config = {
        "window": window, "noise_gate_window": noise_gate_window,
        "transition_ratio": transition_ratio,
        "sigma_ceiling_factor": sigma_ceiling_factor,
        "k_sign": k_sign, "run_sign": run_sign,
        "k_cusum": k_cusum, "h_cusum": h_cusum,
        "h_cusum_f": h_cusum_f, "h_cusum_g": h_cusum_g,
        "h_cusum_i": h_cusum_i,
        "transition_damping": transition_damping,
        "calm_k": calm_k, "calm_periods": calm_periods, "cooldown": cooldown,
        "p1_high_noise_factor": p1_high_noise_factor,
        "p1_high_noise_run": p1_high_noise_run,
        "B": "two_sided_CUSUM_hold_unbounded_during_transition + capped P1",
        "C": "two_sided_CUSUM_capped_scale_with_transition_damping + capped P1",
        "D": "C CUSUM unchanged + production-style adaptive high-noise P1",
        "E": "two-sided unbounded CUSUM; reset tracks during variance transitions; adaptive P1; h=8.5",
        "F": "same as E with h=10.5",
        "G": "same as E with h=12.5",
        "H": "two-sided unbounded CUSUM; preserve accumulators during transitions; adaptive P1; h=12.5",
        "I": "same as H with h=16.5",
        "fusion": "same direction until reversal or confirmed calm",
    }
    snapshot = _snapshot(
        series, quiet_range, bias, sigma_quiet, config, code_revision
    )
    # A is the production API itself: no mirrored detector logic in the evaluator.
    baseline = production_engine.run(
        domain, rows, quiet_range=quiet_range, entity=entity
    )
    candidate_b = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="hold_unbounded",
        p1_high_noise_handling=False, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_c = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="bounded_damped",
        p1_high_noise_handling=False, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_d = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="bounded_damped",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_e = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="reset_unbounded",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_f = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum_f, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="reset_unbounded",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_g = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum_g, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="reset_unbounded",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    return {
        "snapshot": snapshot.to_dict(),
        "A": baseline,
        "B": candidate_b,
        "C": candidate_c,
        "D": candidate_d,
        "E": candidate_e,
        "F": candidate_f,
        "G": candidate_g,
    candidate_h = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum_g, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="hold_unbounded",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
    candidate_i = _candidate(
        series, bias=bias, sigma_quiet=sigma_quiet, window=window,
        noise_gate_window=noise_gate_window, transition_ratio=transition_ratio,
        sigma_ceiling_factor=sigma_ceiling_factor, k_sign=k_sign, run_sign=run_sign,
        k_cusum=k_cusum, h_cusum=h_cusum_i, transition_damping=transition_damping,
        calm_k=calm_k, calm_periods=calm_periods, cooldown=cooldown,
        entity=entity, policy="hold_unbounded",
        p1_high_noise_handling=True, p1_high_noise_factor=p1_high_noise_factor,
        p1_high_noise_run=p1_high_noise_run,
    )
        "H": candidate_h,
        "I": candidate_i,
    }
