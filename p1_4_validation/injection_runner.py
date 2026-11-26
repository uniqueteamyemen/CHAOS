"""P1.4 deterministic injection, AR-null and detector evaluation primitives.

These helpers do not launch a cohort run. A later GitHub Actions Pilot entrypoint
will call them using the exact frozen series IDs and protocol hash. Raw values
remain in memory; output records contain metrics and provenance only.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

MIN_QUIET = 40
FOCUS_INITIAL_QUIET_POINTS = 40
FOCUS_REARM_QUIET_POINTS = 20
FOCUS_MIN_N = 150
AR_ORDERS = (1, 2, 3)
WILSON_Z_95_ONE_SIDED = 1.6448536269514722


class NotEligibleError(ValueError):
    """The series or fitted model cannot satisfy the frozen protocol."""


def deterministic_seed(
    protocol_version: str, series_id: str, position: float,
    ar_order: int, phase: str, replicate: int,
) -> int:
    """Common seed identity for paired tools; deliberately excludes tool/variant."""
    if phase not in {"development", "holdout", "shuffle", "rearm"}:
        raise ValueError("invalid_seed_phase")
    if int(ar_order) not in AR_ORDERS or int(replicate) < 0:
        raise ValueError("invalid_seed_identity")
    payload = (
        f"CHAOS:P1.4:{protocol_version}:{series_id}:{float(position):.6f}:"
        f"{int(ar_order)}:{phase}:{int(replicate)}"
    ).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _values(values: Sequence[float]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError("series_must_be_finite_1d")
    return x


def fit_ar_candidate(values: Sequence[float], order: int) -> dict[str, Any]:
    """OLS AR(p)+intercept fit on the complete supplied pre-break prefix."""
    x, p = _values(values), int(order)
    if p not in AR_ORDERS:
        raise ValueError("AR order must be 1, 2 or 3")
    if x.size < MIN_QUIET or x.size <= 2 * p + 2:
        return {"status": "NOT_ELIGIBLE", "reason": "INSUFFICIENT_PREBREAK", "order": p}
    target = x[p:]
    lag_columns = [x[p - lag - 1 : x.size - lag - 1] for lag in range(p)]
    design = np.column_stack([np.ones(target.size), *lag_columns])
    beta, _residuals, rank, _singular = np.linalg.lstsq(design, target, rcond=None)
    if rank != p + 1 or not np.all(np.isfinite(beta)):
        return {"status": "NOT_ELIGIBLE", "reason": "SINGULAR_AR_FIT", "order": p}
    residuals = target - design @ beta
    residual_df = int(residuals.size - beta.size)
    sse = float(np.dot(residuals, residuals))
    if residual_df <= 0 or not math.isfinite(sse) or sse <= 1e-20:
        return {"status": "NOT_ELIGIBLE", "reason": "INVALID_AR_RESIDUALS", "order": p}
    phi = np.asarray(beta[1:], dtype=float)
    # np.roots expects descending powers: -phi_p,...,-phi_1,1.
    roots = np.roots(np.concatenate((-phi[::-1], [1.0])))
    stable = bool(np.all(np.isfinite(roots)) and np.all(np.abs(roots) > 1.0 + 1e-8))
    r0 = float(np.median(residuals))
    sigma = float(1.4826 * np.median(np.abs(residuals - r0)))
    if not math.isfinite(sigma) or sigma <= 0:
        return {"status": "NOT_ELIGIBLE", "reason": "INVALID_RESIDUAL_SCALE", "order": p}
    aic = float(residuals.size * math.log(sse / residuals.size) + 2 * beta.size)
    return {
        "status": "OK" if stable else "NOT_ELIGIBLE",
        "reason": None if stable else "UNSTABLE_AR_ROOT",
        "order": p, "intercept": float(beta[0]), "ar_coefficients": phi.tolist(),
        "residuals": residuals.astype(float), "residual_sigma": sigma,
        "residual_pool_sha256": hashlib.sha256(np.asarray(residuals, dtype="<f8").tobytes()).hexdigest(),
        "residual_df": residual_df, "aic": aic,
        "roots_abs": [float(abs(v)) for v in roots], "stable": stable,
    }


def select_ar_model(prebreak_values: Sequence[float]) -> dict[str, Any]:
    """Minimum-AIC p=1..3 model; unstable winner fails closed (no lower-order fallback)."""
    candidates = [fit_ar_candidate(prebreak_values, p) for p in AR_ORDERS]
    fitted = [row for row in candidates if row.get("aic") is not None]
    if not fitted:
        return {"status": "NOT_ELIGIBLE", "reason": "NO_AR_ORDER_FIT"}
    winner = min(fitted, key=lambda row: (float(row["aic"]), int(row["order"])))
    if winner["status"] != "OK":
        return {"status": "NOT_ELIGIBLE", "reason": winner["reason"],
                "selected_order": winner["order"], "aic": winner["aic"]}
    return winner


def generate_ar_null_trace(
    model: Mapping[str, Any], initial_values: Sequence[float], horizon: int, seed: int,
) -> np.ndarray:
    """AR(p) residual-bootstrap null; deterministic, fixed horizon, no change injection."""
    if model.get("status") != "OK":
        raise NotEligibleError("AR model not eligible")
    initial = _values(initial_values)
    p, n = int(model["order"]), int(horizon)
    phi = np.asarray(model["ar_coefficients"], dtype=float)
    residuals = np.asarray(model["residuals"], dtype=float)
    if n < max(MIN_QUIET, p) or initial.size < p or residuals.size < 4:
        raise NotEligibleError("null trace inputs are too short")
    rng = np.random.default_rng(int(seed))
    innovations = residuals - float(np.mean(residuals))
    draws = rng.choice(innovations, size=n - p, replace=True)
    output = np.empty(n, dtype=float)
    output[:p] = initial[:p]
    intercept = float(model["intercept"])
    for t in range(p, n):
        history = np.asarray([output[t - lag - 1] for lag in range(p)])
        output[t] = intercept + float(np.dot(phi, history)) + float(draws[t - p])
    if not np.all(np.isfinite(output)):
        raise RuntimeError("null_trace_non_finite")
    return output


def build_injected_case(
    values: Sequence[float], *, magnitude_sigma: float,
    position_fraction: float, direction: int,
) -> dict[str, Any]:
    """Permanent shift; sigma comes from AR residuals fitted only before the break."""
    x = _values(values)
    magnitude, position, sign = float(magnitude_sigma), float(position_fraction), int(direction)
    if magnitude not in {0.5, 1.0, 2.0} or position not in {0.3, 0.5, 0.7} or sign not in {-1, 1}:
        raise ValueError("injection_not_in_frozen_grid")
    onset = int(math.floor(position * x.size))
    if onset < MIN_QUIET:
        return {"status": "NOT_ELIGIBLE", "reason": "PREBREAK_PREFIX_SHORTER_THAN_40",
                "planned": True, "true_break_index": onset}
    model = select_ar_model(x[:onset])
    if model.get("status") != "OK":
        return {"status": "NOT_ELIGIBLE", "reason": model.get("reason"),
                "planned": True, "true_break_index": onset}
    delta = sign * magnitude * float(model["residual_sigma"])
    shifted = x.copy()
    shifted[onset:] += delta
    return {
        "status": "OK", "planned": True, "values": shifted,
        "true_break_index": onset, "magnitude_sigma": magnitude,
        "position_fraction": position, "direction": sign,
        "delta": float(delta), "residual_sigma": float(model["residual_sigma"]),
        "ar_model": {key: model[key] for key in (
            "order", "intercept", "ar_coefficients", "residual_sigma",
            "residual_pool_sha256", "aic", "roots_abs"
        )},
    }


def injection_grid(values: Sequence[float]) -> list[dict[str, Any]]:
    """Exact 3 magnitudes × 3 positions × 2 directions; keep NOT_ELIGIBLE cases."""
    rows = [
        build_injected_case(values, magnitude_sigma=m, position_fraction=p, direction=d)
        for m in (0.5, 1.0, 2.0)
        for p in (0.3, 0.5, 0.7)
        for d in (-1, 1)
    ]
    if len(rows) != 18:
        raise AssertionError("injection_grid_size_mismatch")
    return rows


def wilson_upper(successes: int, trials: int, z: float = WILSON_Z_95_ONE_SIDED) -> float | None:
    k, n = int(successes), int(trials)
    if n <= 0 or k < 0 or k > n:
        return None
    p, z2 = k / n, float(z) ** 2
    den = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    radius = float(z) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return min(1.0, (centre + radius) / den)


def calibrate_threshold(
    max_statistics: Iterable[float], thresholds: Sequence[float],
    *, p0_target: float = 0.10, minimum_valid_replicates: int = 950,
) -> dict[str, Any]:
    """Choose the lowest predeclared threshold with one-sided Wilson upper P0 <= target."""
    scores = np.asarray(list(max_statistics), dtype=float)
    valid = scores[np.isfinite(scores)]
    if valid.size < int(minimum_valid_replicates):
        return {"status": "INCONCLUSIVE", "reason": "INSUFFICIENT_VALID_NULL_REPLICATES",
                "valid_replicates": int(valid.size)}
    grid = sorted({float(v) for v in thresholds})
    if not grid or not all(math.isfinite(v) for v in grid):
        raise ValueError("invalid_threshold_grid")
    rows = []
    for threshold in grid:
        alarms = int(np.sum(valid >= threshold))
        upper = wilson_upper(alarms, valid.size)
        row = {"threshold": threshold, "alarm_traces": alarms,
               "valid_traces": int(valid.size), "p0": alarms / valid.size,
               "p0_wilson_upper_95_one_sided": upper}
        rows.append(row)
        if upper is not None and upper <= float(p0_target):
            return {"status": "CALIBRATED", **row, "grid": rows}
    return {"status": "NOT_CALIBRATABLE",
            "reason": "NO_PREDECLARED_THRESHOLD_MET_P0_TARGET",
            "valid_replicates": int(valid.size), "grid": rows}



def focus_rearm_points_for_frequency(frequency: str) -> int:
    """Return the operational FOCuS re-arm window for the registered cadence."""
    normalized = str(frequency).strip()
    if normalized == "Monthly":
        return 10
    if normalized.startswith("Weekly"):
        return 20
    raise ValueError(f"FOCUS_UNSUPPORTED_SERIES_FREQUENCY:{normalized}")

def focus_reset_rearm(
    values: Sequence[float], *, threshold: float, quiet_points: int = FOCUS_INITIAL_QUIET_POINTS,
    rearm_quiet_points: int | None = None, max_events: int = 12,
    min_series_length: int = FOCUS_MIN_N, frequency: str | None = None,
) -> dict[str, Any]:
    """Re-arm FOCuS with an explicit cadence-aware post-alert calibration window."""
    if frequency is not None:
        cadence_points = focus_rearm_points_for_frequency(frequency)
        if rearm_quiet_points is not None and int(rearm_quiet_points) != cadence_points:
            raise ValueError("FOCUS_REARM_FREQUENCY_PARAMETER_MISMATCH")
        rearm_points = cadence_points
    else:
        rearm_points = (
            FOCUS_REARM_QUIET_POINTS
            if rearm_quiet_points is None else int(rearm_quiet_points)
        )
    x = _values(values)
    if x.size < int(min_series_length):
        return {
            "status": "NOT_ELIGIBLE",
            "reason": "FOCUS_MIN_N_150_REQUIRED",
            "observations": int(x.size),
            "minimum_observations": int(min_series_length),
            "hits": [],
            "event_count": 0,
            "rearm_intervals": [],
        }
    if int(quiet_points) < 1 or int(rearm_points) < 1:
        raise ValueError("FOCUS_CALIBRATION_WINDOWS_MUST_BE_POSITIVE")
    from p2_b_benchmark.p2c_engine import focus_detector
    hits, intervals, cursor = [], [], 0
    while x.size - cursor > (quiet_points if not hits else rearm_points) and len(hits) < max_events:
        active_quiet = quiet_points if not hits else rearm_points
        result = focus_detector(x[cursor:], quiet_points=active_quiet, threshold=float(threshold))
        if result.get("status") == "ABSTAIN" or not result.get("hits"):
            break
        local = dict(result["hits"][0])
        local_index = int(local["detection_index"])
        if local_index < active_quiet or local_index >= x.size - cursor:
            raise RuntimeError("FOCUS_REARM_INDEX_INVALID")
        global_index = cursor + local_index
        estimated = cursor + int(local.get("estimated_change_index", local_index))
        hits.append({**local, "index": global_index, "detection_index": global_index,
                     "estimated_change_index": estimated})
        next_start = global_index + 1
        next_end = min(int(x.size), next_start + int(rearm_points))
        if next_start < next_end:
            intervals.append({"start_inclusive": next_start, "end_exclusive": next_end})
        if next_end >= x.size:
            break
        # The initial 40-point calibration is retained; after a hit the next
        # 20 observations are reserved for re-calibration before monitoring.
        cursor = next_start
    return {"status": "OK", "hits": hits, "event_count": len(hits),
            "rearm_intervals": intervals,
            "initial_calibration_observations": int(quiet_points),
            "rearm_calibration_observations": int(rearm_points)}


def break_is_unmonitored(break_index: int, intervals: Sequence[Mapping[str, int]]) -> bool:
    index = int(break_index)
    return any(int(row["start_inclusive"]) <= index < int(row["end_exclusive"]) for row in intervals)


def evaluate_online_hits(
    hits: Sequence[Mapping[str, Any]], *, true_break_index: int, true_direction: int,
    rearm_intervals: Sequence[Mapping[str, int]] = (),
) -> dict[str, Any]:
    onset, direction = int(true_break_index), int(true_direction)
    pre = [row for row in hits if int(row["detection_index"]) < onset]
    post = [row for row in hits if int(row["detection_index"]) >= onset]
    correct = [row for row in post if int(row["sign"]) == direction]
    wrong = [row for row in post if int(row["sign"]) != direction]
    overlap = break_is_unmonitored(onset, rearm_intervals)
    if overlap:
        return {
            "status": "INVALID_INJECTION",
            "detected": False,
            "pre_onset_alert_count": len(pre),
            "wrong_direction_alert_count": len(wrong),
            "detection_index": None,
            "delay": None,
            "missed": False,
            "false_negative": False,
            "uncovered_by_rearm": True,
            "calibration_overlap_with_injection": True,
            "excluded_from_recall": True,
            "invalid_reason": "INJECTION_FELL_INSIDE_FOCUS_REARM_CALIBRATION_WINDOW",
        }
    selected = None if not correct else min(correct, key=lambda row: int(row["detection_index"]))
    status = "DETECTED" if selected else "MISSED"
    return {
        "status": status, "detected": selected is not None,
        "pre_onset_alert_count": len(pre), "wrong_direction_alert_count": len(wrong),
        "detection_index": int(selected["detection_index"]) if selected else None,
        "delay": int(selected["detection_index"]) - onset if selected else None,
        "missed": selected is None, "false_negative": selected is None,
        "uncovered_by_rearm": False,
        "calibration_overlap_with_injection": False,
        "excluded_from_recall": False,
    }


def match_r_fpop_boundary(
    breakpoints: Sequence[Mapping[str, Any]], *, true_break_index: int,
    series_length: int, tolerance_fraction: float = 0.03,
) -> dict[str, Any]:
    """Single injected boundary gets at most one closest estimated boundary."""
    n = int(series_length)
    if n <= 0 or not 0 < float(tolerance_fraction) < 0.5:
        raise ValueError("invalid_segmentation_tolerance")
    candidates = []
    for index, point in enumerate(breakpoints):
        estimate = int(point["estimated_change_index"])
        distance = abs(estimate - int(true_break_index))
        if distance <= tolerance_fraction * n:
            candidates.append((distance, estimate, index))
    chosen = min(candidates)[2] if candidates else None
    return {
        "matched": chosen is not None, "matched_breakpoint_index": chosen,
        "matched_distance": min(candidates)[0] if candidates else None,
        "boundary_precision": (1.0 / len(breakpoints)) if chosen is not None else 0.0,
        "boundary_recall": 1.0 if chosen is not None else 0.0,
        "false_breakpoint_count": len(breakpoints) - (1 if chosen is not None else 0),
        "estimated_breakpoint_count": len(breakpoints),
    }


def execute_case(
    values: Sequence[float], *, focus_threshold: float,
    huber_mad_threshold: float, huber_bartlett_threshold: float,
    rfpop_penalty_multiplier: float, true_break_index: int | None = None,
    true_direction: int | None = None,
) -> dict[str, Any]:
    """Run the real P2-C detectors; drop full PMF after hashing and summarizing features."""
    from p2_b_benchmark.p2c_engine import (
        bocpd_detector, post_quiet_huber_detector, r_fpop_segment,
    )
    x = _values(values)
    focus = focus_reset_rearm(x, threshold=focus_threshold)
    mad = post_quiet_huber_detector(x, scale_mode="mad", threshold=huber_mad_threshold)
    bartlett = post_quiet_huber_detector(x, scale_mode="bartlett", threshold=huber_bartlett_threshold)
    bocpd = bocpd_detector(x, diagnostics=True, export_posterior=True)
    fpop = r_fpop_segment(x, penalty_multiplier=rfpop_penalty_multiplier)
    output = {
        "series_length": int(x.size),
        "focus_reset_rearm": {
            "status": focus["status"],
            "reason": focus.get("reason"),
            "observations": int(x.size),
            "minimum_observations": int(focus.get("minimum_observations", 150)),
            "hits": focus.get("hits", []),
            "rearm_intervals": focus.get("rearm_intervals", []),
        },
        "post_quiet_huber_mad": {"hits": mad.get("hits", []), "status": mad["status"]},
        "post_quiet_huber_bartlett": {"hits": bartlett.get("hits", []), "status": bartlett["status"]},
        "bocpd_features": {
            "status": bocpd["status"],
            "posterior_pmf_sha256": bocpd.get("metadata", {}).get("posterior_pmf_trace_sha256"),
            "posterior_prefix_count": bocpd.get("metadata", {}).get("posterior_prefix_count", 0),
            "feature_trace": bocpd.get("posterior_feature_trace", []),
        },
        "r_fpop": {"status": fpop.get("status"), "breakpoints": fpop.get("breakpoints", []),
                   "penalty": fpop.get("metadata", {}).get("penalty")},
    }
    if true_break_index is not None and true_direction in {-1, 1}:
        output["outcomes"] = {
            "FOCuS": (
                {"status": "NOT_ELIGIBLE", "detected": False, "missed": False,
                 "false_negative": False, "calibration_overlap_with_injection": False,
                 "excluded_from_recall": True,
                 "invalid_reason": focus.get("reason", "FOCUS_NOT_ELIGIBLE")}
                if focus.get("status") == "NOT_ELIGIBLE"
                else evaluate_online_hits(
                    focus.get("hits", []), true_break_index=true_break_index,
                    true_direction=int(true_direction),
                    rearm_intervals=focus.get("rearm_intervals", []),
                )
            ),
            "POST_QUIET_HUBER_MAD": evaluate_online_hits(mad.get("hits", []),
                true_break_index=true_break_index, true_direction=int(true_direction)),
            "POST_QUIET_HUBER_BARTLETT": evaluate_online_hits(bartlett.get("hits", []),
                true_break_index=true_break_index, true_direction=int(true_direction)),
            "R-FPOP": match_r_fpop_boundary(fpop.get("breakpoints", []),
                true_break_index=true_break_index, series_length=int(x.size)),
        }
    return output
