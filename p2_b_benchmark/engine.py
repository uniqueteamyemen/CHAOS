"""P2-B isolated, causal detector candidates. Does not modify/import experiments/*."""
from __future__ import annotations

import json
import math
import re
import statistics
from typing import Any, Callable

import numpy as np

BASELINE_MODES = {
    "A_FAST": "fast",
    "A_MARKOV_CUSUM": "markov_cusum",
    "A_CONSENSUS": "consensus",
}

PARALLEL_FUSION_ARMS = ("G", "H", "J", "K", "I")
VARIANTS = {
    **{arm: {"kind": "break_detector_v1", "mode": mode}
       for arm, mode in BASELINE_MODES.items()},
    "G": {"kind": "parallel_fusion", "h": 12.5, "transition": "reset"},
    "H": {"kind": "parallel_fusion", "h": 12.5, "transition": "hold"},
    "J": {"kind": "parallel_fusion", "h": 14.5, "transition": "hold"},
    "K": {"kind": "parallel_fusion", "h": 15.5, "transition": "hold"},
    "I": {"kind": "parallel_fusion", "h": 16.5, "transition": "hold"},
}

# Extension algorithms are registered through this adapter contract. The
# metadata remains JSON-serializable; callables are kept out of VARIANTS.
_EXTENSION_RUNNERS: dict[str, Callable[[np.ndarray], dict[str, Any]]] = {}


def normalize_detector_key(name: str) -> str:
    """Normalize a display name into a stable, collision-checked arm key."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("detector_name_must_be_nonempty_string")
    key = re.sub(r"[^A-Z0-9]+", "_", name.strip().upper()).strip("_")
    if not key or not key[0].isalpha():
        raise ValueError("detector_name_must_start_with_letter")
    return key


def register_detector(
    name: str,
    runner: Callable[[np.ndarray], dict[str, Any]],
    *,
    family: str,
    version: str,
    description: str,
    parameters: dict[str, Any] | None = None,
) -> str:
    """Register a future detector using normalized ``index``/``sign`` hits.

    ``runner`` receives a one-dimensional float array and returns
    ``{"hits": [{"index": int, "sign": -1|1, "detector": str}, ...]}``.
    A caller can register FOCuS, R-FPOP, BOCPD, Post-Quiet Huber, Bartlett
    LRV, or any other candidate without changing the benchmark/scoring code.
    """
    key = normalize_detector_key(name)
    if key in VARIANTS or key in _EXTENSION_RUNNERS:
        raise ValueError(f"detector_arm_already_registered:{key}")
    if not callable(runner):
        raise TypeError("detector_runner_must_be_callable")
    if not all(isinstance(value, str) and value.strip()
               for value in (family, version, description)):
        raise ValueError("detector_family_version_description_required")
    metadata = {
        "kind": "extension",
        "display_name": name.strip(),
        "family": family.strip(),
        "version": version.strip(),
        "description": description.strip(),
        "parameters": parameters or {},
    }
    # Fail at registration rather than halfway through writing benchmark JSON.
    json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    VARIANTS[key] = metadata
    _EXTENSION_RUNNERS[key] = runner
    return key


def _normalize_extension_result(raw: dict[str, Any], size: int, arm: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("hits"), list):
        raise TypeError(f"{arm}_runner_must_return_dict_with_hits_list")
    hits: list[dict[str, Any]] = []
    for source_hit in raw["hits"]:
        if not isinstance(source_hit, dict):
            raise TypeError(f"{arm}_hit_must_be_dict")
        index = source_hit.get("index", source_hit.get("time"))
        sign = source_hit.get("sign", source_hit.get("direction"))
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError(f"{arm}_hit_index_must_be_integer")
        if int(index) < 0 or int(index) >= size:
            raise ValueError(f"{arm}_hit_index_out_of_range:{index}")
        if isinstance(sign, bool) or int(sign) not in (-1, 1):
            raise ValueError(f"{arm}_hit_sign_must_be_minus_or_plus_one")
        hit = dict(source_hit)
        hit.update({"index": int(index), "sign": int(sign),
                    "detector": str(source_hit.get("detector", arm))})
        hits.append(hit)
    hits.sort(key=lambda item: (item["index"], item["sign"], item["detector"]))
    raw_events = raw.get("events", [])
    if not isinstance(raw_events, list):
        raise TypeError(f"{arm}_events_must_be_list")
    events: list[dict[str, Any]] = []
    for source_event in raw_events:
        if not isinstance(source_event, dict):
            raise TypeError(f"{arm}_event_must_be_dict")
        start = source_event.get("start_index", source_event.get("index"))
        sign = source_event.get("sign", source_event.get("direction"))
        if isinstance(start, bool) or not isinstance(start, (int, np.integer)):
            raise ValueError(f"{arm}_event_start_index_must_be_integer")
        if int(start) < 0 or int(start) >= size:
            raise ValueError(f"{arm}_event_start_index_out_of_range:{start}")
        try:
            event_sign = int(sign)
        except (TypeError, ValueError):
            raise ValueError(f"{arm}_event_sign_must_be_minus_or_plus_one") from None
        if isinstance(sign, bool) or event_sign not in (-1, 1):
            raise ValueError(f"{arm}_event_sign_must_be_minus_or_plus_one")
        event = dict(source_event)
        event.update({"start_index": int(start), "sign": event_sign})
        events.append(event)
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise TypeError(f"{arm}_metadata_must_be_dict")
    json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    return {"hits": hits, "events": events, "metadata": metadata}


def run_registered_detector(
    values: list[float] | np.ndarray,
    arm: str,
    *,
    causal_audit: bool = False,
) -> dict[str, Any]:
    """Run a registered extension and optionally prefix-replay every hit."""
    if arm not in _EXTENSION_RUNNERS:
        raise ValueError(f"unknown_extension_detector:{arm}")
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or x.size < 1 or not np.all(np.isfinite(x)):
        raise ValueError("extension_input_must_be_finite_1d")
    runner = _EXTENSION_RUNNERS[arm]
    normalized = _normalize_extension_result(runner(x.copy()), x.size, arm)
    violations = 0
    if causal_audit:
        for hit in normalized["hits"]:
            t = int(hit["index"])
            prefix_raw = runner(x[:t + 1].copy())
            prefix = _normalize_extension_result(prefix_raw, t + 1, arm)
            if not any(candidate["index"] == t and candidate["sign"] == hit["sign"]
                       and candidate["detector"] == hit["detector"]
                       for candidate in prefix["hits"]):
                violations += 1
        for event in normalized["events"]:
            t = int(event["start_index"])
            prefix_raw = runner(x[:t + 1].copy())
            prefix = _normalize_extension_result(prefix_raw, t + 1, arm)
            if not any(candidate["start_index"] == t and candidate["sign"] == event["sign"]
                       for candidate in prefix["events"]):
                violations += 1
    return {
        "hits": normalized["hits"],
        "events": normalized["events"],
        "event_count": len(normalized["events"]) or len(normalized["hits"]),
        "causal_audit_violations": violations if causal_audit else None,
        "causal_audit_unverifiable_prefixes": 0 if causal_audit else None,
        "transition_periods": 0,
        "metadata": normalized["metadata"],
    }


def mad_sigma(values: list[float] | np.ndarray) -> float:
    a = np.asarray(values, dtype=float)
    if a.size == 0 or not np.all(np.isfinite(a)):
        return 0.0
    centre = float(np.median(a))
    return float(1.4826 * np.median(np.abs(a - centre)))


def _rolling_sigma(values: np.ndarray, window: int, min_points: int = 8) -> list[float | None]:
    output: list[float | None] = []
    for i in range(values.size):
        # Strictly prior observations: current and future values never enter scale.
        prior = values[max(0, i - window):i]
        if prior.size < min_points:
            output.append(None)
        else:
            scale = mad_sigma(prior)
            output.append(scale if scale > 0 and math.isfinite(scale) else None)
    return output


def run_parallel_fusion(
    values: list[float] | np.ndarray,
    *,
    variant: str,
    quiet_points: int = 40,
) -> dict[str, Any]:
    """Run frozen G/H/J/K/I logic on a single scalar stream, using only past data."""
    if variant not in {"G", "H", "J", "K", "I"}:
        raise ValueError(f"unknown_parallel_fusion_variant:{variant}")
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError("series_must_be_finite_1d")
    if quiet_points < 8 or quiet_points >= x.size:
        raise ValueError("quiet_window_invalid")

    quiet = x[:quiet_points]
    bias = float(np.median(quiet))
    sigma_quiet = mad_sigma(quiet)
    if not math.isfinite(sigma_quiet) or sigma_quiet <= 0:
        return {
            "variant": variant,
            "status": "ABSTAIN",
            "abstain_reason": "ZERO_QUIET_SCALE",
            "hits": [],
            "events": [],
            "quiet_bias": bias,
            "quiet_sigma": sigma_quiet,
            "transition_periods": 0,
        }

    short = _rolling_sigma(x, 12)
    long = _rolling_sigma(x, 52)
    cap = 2.0 * sigma_quiet
    high_noise_gate = 1.5 * sigma_quiet
    transitions = [
        s is not None and l is not None and l > 0 and s > 1.2 * l
        for s, l in zip(short, long)
    ]

    hits: list[dict[str, Any]] = []
    streak: list[int] = []
    streak_sign: int | None = None
    # P1: 3 sigma / 3-run nominal; production-style adaptive 13-run in high noise.
    for i, value in enumerate(x):
        # The first quiet_points observations calibrate bias/scale only.
        # They must never be eligible to emit a detector hit.
        if i < quiet_points:
            continue
        scale_short = short[i]
        high_noise = scale_short is not None and scale_short > high_noise_gate
        scale = (scale_short if high_noise else long[i])
        if scale is None or scale <= 0:
            streak, streak_sign = [], None
            continue
        z = float(value - bias)
        threshold = 0.0 if high_noise else 3.0 * min(scale, cap)
        required = 13 if high_noise else 3
        sign = 1 if z > 0 else -1 if z < 0 else 0
        if sign and abs(z) >= threshold:
            if streak_sign is not None and sign != streak_sign:
                streak = []
            streak.append(i)
            streak_sign = sign
        else:
            streak, streak_sign = [], None
        if len(streak) >= required:
            hits.append({"index": i, "sign": sign, "detector": "sign_run", "priority": 1})
            streak, streak_sign = [], None

    # Two independent directional CUSUM tracks. G resets during a variance
    # transition; H/J/K/I preserve evidence and do not update during that span.
    positive = 0.0
    negative = 0.0
    h = float(VARIANTS[variant]["h"])
    for i, value in enumerate(x):
        if i < quiet_points:
            continue
        scale = long[i]
        if scale is None or scale <= 0:
            continue
        if transitions[i]:
            if VARIANTS[variant]["transition"] == "reset":
                positive = 0.0
                negative = 0.0
            continue
        z = float(value - bias)
        positive = max(0.0, positive + z - 0.5 * scale)
        negative = max(0.0, negative - z - 0.5 * scale)
        threshold = h * scale
        if positive > threshold:
            hits.append({"index": i, "sign": 1, "detector": "cusum_positive", "priority": 2})
            positive = 0.0
        if negative > threshold:
            hits.append({"index": i, "sign": -1, "detector": "cusum_negative", "priority": 2})
            negative = 0.0

    hits.sort(key=lambda item: (item["index"], item["priority"], item["detector"]))
    events: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    calm_streak = 0
    last_by_detector_sign: dict[tuple[str, int], int] = {}
    hits_by_index: dict[int, list[dict[str, Any]]] = {}
    for hit in hits:
        hits_by_index.setdefault(int(hit["index"]), []).append(hit)
    for i, value in enumerate(x):
        if i < quiet_points:
            continue
        scale = long[i] if long[i] is not None else sigma_quiet
        z = float(value - bias)
        calm_streak = calm_streak + 1 if abs(z) <= 0.5 * scale else 0
        for hit in hits_by_index.get(i, []):
            sign = int(hit["sign"])
            if active is None or sign != active["sign"] or calm_streak >= 6:
                last_by_detector_sign = {}
                active = {
                    "start_index": i,
                    "end_index": i,
                    "sign": sign,
                    "detectors": [],
                    "evidence": [],
                }
                events.append(active)
            key = (str(hit["detector"]), sign)
            hit_copy = dict(hit)
            previous = last_by_detector_sign.get(key)
            if previous is not None and i - previous < 26:
                hit_copy["notification_suppressed"] = "same_event_directional_cooldown"
            last_by_detector_sign[key] = i
            active["evidence"].append(hit_copy)
            if hit["detector"] not in active["detectors"]:
                active["detectors"].append(hit["detector"])
            active["end_index"] = i
            calm_streak = 0

    for event in events:
        event["evidence_count"] = len(event["evidence"])
    return {
        "variant": variant,
        "hits": hits,
        "events": events,
        "quiet_bias": bias,
        "quiet_sigma": sigma_quiet,
        "transition_periods": sum(transitions),
    }


def audit_parallel_prefix_invariance(
    values: list[float] | np.ndarray,
    variant: str,
    *,
    quiet_points: int = 40,
) -> int:
    """Count mutation and exact prefix-replay violations for every hit/event."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)) or x.size <= quiet_points:
        raise ValueError("causal_audit_input_invalid")
    full = run_parallel_fusion(x, variant=variant, quiet_points=quiet_points)
    if full.get("status") == "ABSTAIN":
        return 0

    violations = 0

    # Future-suffix mutation check: outputs emitted strictly before cutoff must
    # remain exactly identical after only the future suffix is altered.
    cut = max(quiet_points + 1, int(x.size * 0.65))
    if cut < x.size:
        altered = x.copy()
        altered[cut:] = altered[cut:][::-1] * -1.7 + 0.31
        mutated = run_parallel_fusion(altered, variant=variant, quiet_points=quiet_points)

        def hit_tokens(rows: list[dict[str, Any]], before: int | None = None):
            return [
                (int(hit["index"]), int(hit["sign"]), str(hit["detector"]))
                for hit in rows if before is None or int(hit["index"]) < before
            ]

        if hit_tokens(full["hits"], cut) != hit_tokens(mutated["hits"], cut):
            violations += 1

        def event_tokens(rows: list[dict[str, Any]], before: int):
            tokens = []
            for event in rows:
                evidence = [item for item in event["evidence"] if int(item["index"]) < before]
                if evidence:
                    tokens.append((
                        int(event["start_index"]), int(event["sign"]),
                        tuple((int(item["index"]), int(item["sign"]), str(item["detector"]),
                               item.get("notification_suppressed")) for item in evidence),
                    ))
            return tokens

        if event_tokens(full["events"], cut) != event_tokens(mutated["events"], cut):
            violations += 1

    # Prefix replay for every emitted detector hit.
    for hit in full["hits"]:
        t = int(hit["index"])
        prefix = run_parallel_fusion(x[:t + 1], variant=variant, quiet_points=quiet_points)
        replayed = any(
            int(candidate["index"]) == t
            and int(candidate["sign"]) == int(hit["sign"])
            and str(candidate["detector"]) == str(hit["detector"])
            for candidate in prefix["hits"]
        )
        if not replayed:
            violations += 1

    # Prefix replay each fused event at its last evidence timestamp, requiring
    # its start and all evidence accumulated up to that point to be identical.
    for event in full["events"]:
        evidence = event.get("evidence", [])
        if not evidence:
            violations += 1
            continue
        t = max(int(item["index"]) for item in evidence)
        prefix = run_parallel_fusion(x[:t + 1], variant=variant, quiet_points=quiet_points)
        matching = [candidate for candidate in prefix["events"]
                    if int(candidate["start_index"]) == int(event["start_index"])
                    and int(candidate["sign"]) == int(event["sign"])]
        expected_evidence = [
            (int(item["index"]), int(item["sign"]), str(item["detector"]),
             item.get("notification_suppressed"))
            for item in evidence if int(item["index"]) <= t
        ]
        replayed = False
        for candidate in matching:
            actual_evidence = [
                (int(item["index"]), int(item["sign"]), str(item["detector"]),
                 item.get("notification_suppressed"))
                for item in candidate.get("evidence", []) if int(item["index"]) <= t
            ]
            if actual_evidence == expected_evidence:
                replayed = True
                break
        if not replayed:
            violations += 1

    return violations


def run_baseline(values: list[float] | np.ndarray, *, causal_audit: bool = False) -> dict[str, Any]:
    """Run all frozen BreakDetectorV1 modes; the detector implementation stays read-only."""
    x = np.asarray(values, dtype=float)
    from structural_engine.isolated_break_detector_v1 import BreakDetectorV1

    output: dict[str, Any] = {}
    for arm, mode in BASELINE_MODES.items():
        result = BreakDetectorV1(mode=mode).analyze(x)
        events = []
        violations = 0
        unverifiable_prefixes = 0
        short_prefix_checks = []
        for event in result.get("structural_breaks", []):
            detection_time = event.get("detection_time")
            if detection_time is None:
                continue
            t = int(detection_time)
            direction = int(event.get("direction", 0))
            events.append({"time": t, "direction": direction})
            if causal_audit:
                if t < 0 or t >= x.size:
                    violations += 1
                    continue
                # Use the detector's actual input contract. MIN_FULL_CONSENSUS_LENGTH
                # describes availability of a full matching window, not a minimum
                # length accepted by analyze() for prefix replay.
                minimum_prefix = int(BreakDetectorV1.MIN_SERIES_LENGTH)
                prefix_length = t + 1
                is_short_consensus_prefix = (
                    mode == "consensus"
                    and prefix_length < int(BreakDetectorV1.MIN_FULL_CONSENSUS_LENGTH)
                )
                check = None
                if is_short_consensus_prefix:
                    check = {
                        "time": t,
                        "direction": direction,
                        "prefix_length": prefix_length,
                        "minimum_supported_prefix": minimum_prefix,
                    }
                if prefix_length < minimum_prefix:
                    unverifiable_prefixes += 1
                    if check is not None:
                        check["status"] = "UNVERIFIABLE_BELOW_MIN_SERIES_LENGTH"
                        short_prefix_checks.append(check)
                    continue
                prefix_result = BreakDetectorV1(mode=mode).analyze(x[:prefix_length])
                found = any(
                    int(candidate.get("detection_time", -1)) == t
                    and int(candidate.get("direction", 0)) == direction
                    for candidate in prefix_result.get("structural_breaks", [])
                )
                if not found:
                    violations += 1
                if check is not None:
                    check["status"] = "MATCH" if found else "MISMATCH"
                    short_prefix_checks.append(check)
        output[arm] = {
            "hits": events,
            "event_count": len(events),
            "causal_audit_violations": violations if causal_audit else None,
            "causal_audit_unverifiable_prefixes": unverifiable_prefixes if causal_audit else None,
            "causal_audit_details": short_prefix_checks if causal_audit and mode == "consensus" else None,
        }
    return output


def run_all(
    values: list[float] | np.ndarray,
    *,
    causal_audit: bool = False,
    quiet_points: int = 40,
) -> dict[str, Any]:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)) or x.size <= quiet_points:
        raise ValueError("series_must_be_finite_1d_and_longer_than_quiet_window")
    quiet_scale = mad_sigma(x[:quiet_points])
    if not math.isfinite(quiet_scale) or quiet_scale <= 0:
        return {
            arm: {
                "status": "ABSTAIN",
                "abstain_reason": "ZERO_QUIET_SCALE",
                "hits": [],
                "events": [],
                "event_count": 0,
                "transition_periods": 0,
                "causal_audit_violations": 0 if causal_audit else None,
                "causal_audit_unverifiable_prefixes": 0 if causal_audit else None,
            }
            for arm in VARIANTS
        }

    output = run_baseline(x, causal_audit=causal_audit)
    for variant in PARALLEL_FUSION_ARMS:
        result = run_parallel_fusion(x, variant=variant, quiet_points=quiet_points)
        output[variant] = {
            "status": result.get("status", "OK"),
            "abstain_reason": result.get("abstain_reason"),
            "hits": result["hits"],
            "events": result["events"],
            "event_count": len(result["events"]),
            "transition_periods": result["transition_periods"],
            "causal_audit_violations": (
                audit_parallel_prefix_invariance(x, variant, quiet_points=quiet_points)
                if causal_audit else None
            ),
            "causal_audit_unverifiable_prefixes": 0 if causal_audit else None,
        }
    for arm in tuple(_EXTENSION_RUNNERS):
        output[arm] = run_registered_detector(x, arm, causal_audit=causal_audit)
    return output


