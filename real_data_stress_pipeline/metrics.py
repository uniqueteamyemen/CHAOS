"""Quality gates, event mapping, Stationary Bootstrap, and detector metrics."""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

import numpy as np
from statsmodels.tsa.stattools import adfuller, kpss

from structural_engine.isolated_break_detector_v1 import BreakDetectorV1


STRUCTURAL_STATUSES = {"CONFIRMED", "PROVISIONAL"}


def scaled_mad(values: list[float] | np.ndarray) -> float:
    data = np.asarray(values, dtype=float)
    data = data[np.isfinite(data)]
    if data.size == 0:
        return 0.0
    median = float(np.median(data))
    return float(1.4826 * np.median(np.abs(data - median)))


def g0_quality(series: dict, pipeline_config: dict) -> dict:
    values = np.asarray(series.get("values", []), dtype=float)
    n = int(values.size)
    minimum = int(pipeline_config["general_g0_min_observations_inclusive"])
    mad_floor = float(pipeline_config["mad_scaled_minimum"])
    mad = scaled_mad(values)
    finite = bool(values.size and np.all(np.isfinite(values)))
    strictly_long_monthly = (
        series.get("frequency") == "monthly"
        and series.get("source_id") == "WORLD_BANK_PINK_SHEET"
    )
    required = (
        int(pipeline_config["primary_monthly_min_observations_exclusive"]) + 1
        if strictly_long_monthly else minimum
    )
    passed = finite and n >= required and mad > mad_floor
    return {
        "gate": "G0",
        "passed": bool(passed),
        "observations": n,
        "required_observations_inclusive": required,
        "primary_long_monthly_cohort": bool(strictly_long_monthly),
        "scaled_mad": mad,
        "mad_minimum_exclusive": mad_floor,
        "finite_values": finite,
        "rejection_reasons": [
            reason for condition, reason in (
                (not finite, "non_finite_or_empty_values"),
                (n < required, f"insufficient_observations:{n}<{required}"),
                (mad <= mad_floor, f"degenerate_scaled_mad:{mad}"),
            ) if condition
        ],
    }


def g1_stationarity(values: list[float] | np.ndarray, config: dict) -> dict:
    data = np.asarray(values, dtype=float)
    adf_alpha = float(config["adf_significance"])
    kpss_alpha = float(config["kpss_significance"])
    if data.size < 87 or not np.all(np.isfinite(data)):
        return {
            "gate": "G1",
            "passed": False,
            "status": "NOT_TESTED",
            "reason": "G0_sample_not_eligible_for_stationarity_diagnostics",
            "adf_p_value": None,
            "kpss_p_value": None,
        }
    if scaled_mad(data) <= 1e-8:
        return {
            "gate": "G1",
            "passed": False,
            "status": "DEGENERATE",
            "reason": "stationarity_tests_not_run_on_degenerate_series",
            "adf_p_value": None,
            "kpss_p_value": None,
        }
    try:
        adf_result = adfuller(data, autolag="AIC")
        with np.errstate(all="ignore"):
            kpss_result = kpss(data, regression="c", nlags="auto")
        adf_p = float(adf_result[1])
        kpss_p = float(kpss_result[1])
        passed = adf_p < adf_alpha and kpss_p >= kpss_alpha
        return {
            "gate": "G1",
            "passed": bool(passed),
            "status": "SCREEN_PASS" if passed else "SCREEN_FAIL",
            "adf_statistic": float(adf_result[0]),
            "adf_p_value": adf_p,
            "adf_lags": int(adf_result[2]),
            "kpss_statistic": float(kpss_result[0]),
            "kpss_p_value": kpss_p,
            "kpss_lags": int(kpss_result[2]),
            "adf_rejects_unit_root": bool(adf_p < adf_alpha),
            "kpss_does_not_reject_level_stationarity": bool(kpss_p >= kpss_alpha),
            "interpretation": (
                "A preliminary sequence-stationarity screen only; it does not prove "
                "strict stationarity or validate a domain-specific stochastic model."
            ),
        }
    except Exception as exc:
        return {
            "gate": "G1",
            "passed": False,
            "status": "TEST_ERROR",
            "reason": f"{type(exc).__name__}:{exc}",
            "adf_p_value": None,
            "kpss_p_value": None,
        }


def stationary_bootstrap(
    values: list[float] | np.ndarray,
    replicates: int,
    mean_block_length: float,
    seed: int,
) -> np.ndarray:
    """Politis–Romano stationary bootstrap with circular continuation."""
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or data.size < 2 or not np.all(np.isfinite(data)):
        raise ValueError("stationary_bootstrap_requires_finite_1d_series_n_ge_2")
    if replicates < 1:
        raise ValueError("bootstrap_replicates_must_be_positive")
    if not math.isfinite(mean_block_length) or mean_block_length < 1:
        raise ValueError("mean_block_length_must_be_finite_and_at_least_one")

    n = data.size
    restart_probability = 1.0 / mean_block_length
    rng = np.random.default_rng(seed)
    samples = np.empty((replicates, n), dtype=float)
    for b in range(replicates):
        index = int(rng.integers(0, n))
        for t in range(n):
            if t > 0 and rng.random() < restart_probability:
                index = int(rng.integers(0, n))
            else:
                index = (index + 1) % n if t > 0 else index
            samples[b, t] = data[index]
    return samples


def stable_seed(base_seed: int, *parts: str) -> int:
    payload = "|".join((str(base_seed), *parts)).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _event_counts(result: dict) -> dict:
    counts = Counter(event.get("status", "UNKNOWN") for event in result.get("events", []))
    return {
        "PROVISIONAL": int(counts.get("PROVISIONAL", 0)),
        "CONFIRMED": int(counts.get("CONFIRMED", 0)),
        "TRANSIENT": int(counts.get("TRANSIENT", 0)),
        "UNRESOLVED": int(counts.get("UNRESOLVED", 0)),
        "STRUCTURAL_TOTAL": int(
            counts.get("PROVISIONAL", 0) + counts.get("CONFIRMED", 0)
        ),
    }


def run_all_detector_modes(values: list[float] | np.ndarray) -> dict:
    output = {}
    for mode in BreakDetectorV1.MODES:
        result = BreakDetectorV1(mode=mode).analyze(values)
        output[mode] = {
            "event_counts": _event_counts(result),
            "sample_adequacy": result.get("sample_adequacy"),
            "diagnostics": result.get("diagnostics", {}),
            "events": result.get("events", []),
        }
    return output


def bootstrap_detector_null(
    values: list[float] | np.ndarray,
    g1_result: dict,
    replicates: int,
    mean_block_length: float,
    seed: int,
) -> dict:
    if not g1_result.get("passed"):
        return {
            "status": "NOT_RUN_G1_SCREEN_FAILED",
            "replicates": 0,
            "reason": "Stationary Block-Bootstrap is restricted to G1 screen-pass series.",
        }

    samples = stationary_bootstrap(
        values=values,
        replicates=replicates,
        mean_block_length=mean_block_length,
        seed=seed,
    )
    counts: dict[str, list[int]] = {
        mode: [] for mode in BreakDetectorV1.MODES
    }
    transient_counts: dict[str, list[int]] = {
        mode: [] for mode in BreakDetectorV1.MODES
    }
    for sample in samples:
        results = run_all_detector_modes(sample)
        for mode, result in results.items():
            counts[mode].append(result["event_counts"]["STRUCTURAL_TOTAL"])
            transient_counts[mode].append(result["event_counts"]["TRANSIENT"])

    return {
        "status": "COMPLETED",
        "method": "Politis-Romano stationary bootstrap (geometric block lengths, circular continuation)",
        "replicates": int(replicates),
        "mean_block_length_observations": float(mean_block_length),
        "seed": int(seed),
        "mode_null_counts": {
            mode: {
                "mean_structural_alarms_per_replica": float(np.mean(values_)),
                "median_structural_alarms_per_replica": float(np.median(values_)),
                "p025_structural_alarms_per_replica": float(np.quantile(values_, 0.025)),
                "p975_structural_alarms_per_replica": float(np.quantile(values_, 0.975)),
                "mean_transient_alarms_per_replica": float(np.mean(transient_counts[mode])),
                "structural_alarm_count_distribution": values_,
            }
            for mode, values_ in counts.items()
        },
        "scope_note": (
            "Conditional sequence-level null. For seismic inter-event intervals this is "
            "not a complete point-process/ETAS/declustering null and cannot alone establish "
            "a seismic false-alarm probability."
        ),
    }


def parse_period(value: str) -> datetime | None:
    text = str(value)
    try:
        if re.match(r"^\d{4}-\d{2}$", text):
            return datetime.strptime(text, "%Y-%m")
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def month_distance(left: datetime, right: datetime) -> int:
    return (right.year - left.year) * 12 + (right.month - left.month)


def _applicable_shocks(category: str, contract: dict) -> list[dict]:
    applicable = []
    for event in contract.get("events", []):
        categories = event.get("applicable_categories", ["all"])
        if "all" in categories or category in categories:
            applicable.append(event)
    return applicable


def evaluate_shock_matches(
    series: dict,
    detector_runs: dict,
    shock_contract: dict,
) -> dict:
    if series.get("frequency") != "monthly":
        return {
            "status": "NOT_APPLICABLE",
            "reason": "Calendar macro-shock matching is defined for monthly market series, not event-time seismic intervals.",
            "modes": {},
        }

    anchor_window = int(shock_contract.get("matching_window_months", 12))
    category = series.get("category", "other_commodity")
    anchors = _applicable_shocks(category, shock_contract)
    periods = series.get("periods", [])
    output: dict[str, Any] = {}

    for mode, run in detector_runs.items():
        candidates = []
        for event in run.get("events", []):
            if event.get("status") not in STRUCTURAL_STATUSES:
                continue
            index = event.get("detection_time", event.get("time"))
            if index is None:
                continue
            try:
                period = periods[int(index)]
            except (IndexError, TypeError, ValueError):
                continue
            stamp = parse_period(period)
            if stamp is None:
                continue
            candidates.append({
                "event": event,
                "index": int(index),
                "period": str(period),
                "timestamp": stamp,
                "status": event.get("status"),
            })

        pairs = []
        for candidate_index, candidate in enumerate(candidates):
            for anchor_index, anchor in enumerate(anchors):
                anchor_date = datetime.fromisoformat(anchor["anchor_date"])
                delta = month_distance(candidate["timestamp"], anchor_date)
                if abs(delta) <= anchor_window:
                    pairs.append((
                        abs(delta),
                        candidate_index,
                        anchor_index,
                        delta,
                        anchor,
                    ))
        pairs.sort(key=lambda item: (item[0], item[1], item[2]))
        used_candidates: set[int] = set()
        used_anchors: set[int] = set()
        matches = []
        for _, candidate_index, anchor_index, lead_months, anchor in pairs:
            if candidate_index in used_candidates or anchor_index in used_anchors:
                continue
            used_candidates.add(candidate_index)
            used_anchors.add(anchor_index)
            candidate = candidates[candidate_index]
            matches.append({
                "anchor_id": anchor["id"],
                "anchor_date": anchor["anchor_date"],
                "anchor_label": anchor["label"],
                "detector_status": candidate["status"],
                "detection_period": candidate["period"],
                "detection_time_index": candidate["index"],
                "warning_lead_months": int(lead_months),
                "interpretation": (
                    "PRE_ANCHOR_SIGNAL" if lead_months > 0
                    else "SAME_MONTH" if lead_months == 0
                    else "POST_ANCHOR_LAG"
                ),
            })

        unmatched_anchors = [
            anchor["id"] for i, anchor in enumerate(anchors)
            if i not in used_anchors
        ]
        matched_count = len(matches)
        output[mode] = {
            "eligible_anchor_count": len(anchors),
            "matched_anchor_count": matched_count,
            "capture_rate": matched_count / len(anchors) if anchors else None,
            "pre_anchor_count": sum(item["warning_lead_months"] > 0 for item in matches),
            "same_month_count": sum(item["warning_lead_months"] == 0 for item in matches),
            "post_anchor_count": sum(item["warning_lead_months"] < 0 for item in matches),
            "matches": matches,
            "unmatched_anchor_ids": unmatched_anchors,
            "unmatched_detector_candidate_count": len(candidates) - len(used_candidates),
        }

    return {
        "status": "EVALUATED",
        "matching_window_months_before_and_after": anchor_window,
        "one_to_one_matching": True,
        "series_category": category,
        "modes": output,
    }


def alarm_burden(
    series: dict,
    detector_runs: dict,
    shock_match_result: dict,
) -> dict:
    periods = series.get("periods", [])
    if not periods:
        return {"status": "NOT_COMPUTED", "reason": "missing_period_axis"}
    first = parse_period(periods[0])
    last = parse_period(periods[-1])
    if first is None or last is None:
        return {"status": "NOT_COMPUTED", "reason": "unparseable_period_axis"}

    span_days = max(1.0, (last - first).total_seconds() / 86400.0)
    decades = span_days / (365.2425 * 10.0)
    if decades <= 0:
        decades = max(1, len(periods)) / 120.0

    output = {}
    for mode, run in detector_runs.items():
        matches = (
            shock_match_result.get("modes", {}).get(mode, {}).get("matches", [])
            if shock_match_result.get("status") == "EVALUATED" else []
        )
        matched_keys = {
            (item["anchor_id"], item["detection_time_index"])
            for item in matches
        }
        matched_indices = {item["detection_time_index"] for item in matches}
        structural_events = [
            event for event in run.get("events", [])
            if event.get("status") in STRUCTURAL_STATUSES
        ]
        alarm_indices = []
        transient = 0
        for event in run.get("events", []):
            index = event.get("detection_time", event.get("time"))
            if event.get("status") == "TRANSIENT":
                transient += 1
            elif event.get("status") in STRUCTURAL_STATUSES and index is not None:
                alarm_indices.append(int(index))

        matched = min(len(matched_indices), len(structural_events))
        false_alarm_count = max(0, len(alarm_indices) - matched)
        output[mode] = {
            "calendar_span_years": span_days / 365.2425,
            "false_alarm_structural_count": false_alarm_count,
            "false_structural_alarms_per_decade": false_alarm_count / decades,
            "all_structural_alarms_per_decade": len(alarm_indices) / decades,
            "transient_alarms_per_decade": transient / decades,
            "matched_shock_signal_count": matched,
            "structural_event_count": len(structural_events),
            "unmatched_structural_event_count": max(0, len(structural_events) - matched),
        }
    return {"status": "COMPUTED", "modes": output}


def empirical_bootstrap_p_value(observed_count: int, null_counts: list[int]) -> float | None:
    if not null_counts:
        return None
    extremes = sum(value >= observed_count for value in null_counts)
    return (extremes + 1) / (len(null_counts) + 1)


def compare_observed_to_null(
    detector_runs: dict,
    bootstrap_result: dict,
    burden: dict,
) -> dict:
    if bootstrap_result.get("status") != "COMPLETED":
        return {"status": bootstrap_result.get("status", "NOT_RUN")}
    output = {}
    for mode, run in detector_runs.items():
        null = bootstrap_result["mode_null_counts"][mode]
        observed_structural = run["event_counts"]["STRUCTURAL_TOTAL"]
        distribution = null["structural_alarm_count_distribution"]
        output[mode] = {
            "observed_structural_alarm_count": observed_structural,
            "null_mean_structural_alarms": null["mean_structural_alarms_per_replica"],
            "null_p025": null["p025_structural_alarms_per_replica"],
            "null_p975": null["p975_structural_alarms_per_replica"],
            "empirical_upper_tail_p_value": empirical_bootstrap_p_value(
                observed_structural, distribution
            ),
            "observed_false_alarms_per_decade": (
                burden.get("modes", {}).get(mode, {}).get("false_structural_alarms_per_decade")
            ),
        }
    return {"status": "COMPLETED", "modes": output}
