"""Domain-neutral observation and break-detection primitives.

This module is experimental and deliberately separate from exp_p_engine.engine.
It accepts measurements, not accounting identities. Thresholds are candidate
settings; no production calibration is implied by this module.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

OBSERVATION_REQUIRED = (
    "entity_id",
    "metric_id",
    "event_time",
    "value",
    "observation_status",
)
OBSERVATION_STATUSES = {
    "observed",
    "missing",
    "not_applicable",
    "pending",
    "invalid",
}

RESIDUAL_REQUIRED_FIELDS = (
    "entity_id",
    "metric_id",
    "event_time",
    "observed_value",
    "expected_value",
    "residual",
    "status",
    "baseline_id",
    "baseline_method",
    "support_count",
)


def validate_residual_contract(rows: Sequence[Mapping[str, Any]]) -> None:
    """Validate the shared output contract emitted by every baseline builder."""
    for index, row in enumerate(rows):
        missing = [field for field in RESIDUAL_REQUIRED_FIELDS if field not in row]
        if missing:
            raise ValueError(
                "residual_contract_fields_missing_at_row_" + str(index) + ":" + ",".join(missing)
            )
        _parse_time(row["event_time"])
        if not str(row["entity_id"]).strip() or not str(row["metric_id"]).strip():
            raise ValueError("residual_contract_identity_empty")
        allowed_statuses = {
            "ready",
            "gap_unresolved",
            "scale_unavailable",
            "peer_scale_unavailable",
            "relation_scale_unavailable",
            "relation_unidentifiable",
        }
        if row["status"] not in allowed_statuses:
            raise ValueError("residual_contract_status_invalid")
        if not isinstance(row["entity_id"], str) or not row["entity_id"].strip():
            raise ValueError("residual_contract_entity_id_invalid")
        if not isinstance(row["metric_id"], str) or not row["metric_id"].strip():
            raise ValueError("residual_contract_metric_id_invalid")
        if not isinstance(row["baseline_id"], str) or not row["baseline_id"].strip():
            raise ValueError("residual_contract_baseline_id_invalid")
        if not isinstance(row["baseline_method"], str) or not row["baseline_method"].strip():
            raise ValueError("residual_contract_baseline_method_invalid")
        support = row["support_count"]
        if isinstance(support, bool) or not isinstance(support, int) or support < 0:
            raise ValueError("residual_contract_support_count_invalid")
        for field in ("observed_value", "expected_value", "residual", "scale", "z_score"):
            value = row.get(field)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(float(value))
            ):
                raise ValueError("residual_contract_numeric_value_invalid:" + field)
        if row.get("scale") is not None and float(row["scale"]) <= 0:
            raise ValueError("residual_contract_scale_not_positive")
        if row["status"] == "ready":
            for field in ("observed_value", "expected_value", "residual", "scale", "z_score"):
                if row.get(field) is None:
                    raise ValueError("residual_contract_ready_value_missing:" + field)
            if float(row["scale"]) <= 0:
                raise ValueError("residual_contract_scale_not_positive")
        if (
            row.get("observed_value") is not None
            and row.get("expected_value") is not None
            and row.get("residual") is not None
        ):
            expected_residual = float(row["observed_value"]) - float(row["expected_value"])
            if not math.isclose(
                float(row["residual"]), expected_residual,
                rel_tol=1e-9, abs_tol=1e-9,
            ):
                raise ValueError("residual_contract_observed_expected_mismatch")


def _mapped(row: Mapping[str, Any], spec: Any) -> Any:
    if isinstance(spec, Mapping) and "constant" in spec:
        return spec["constant"]
    if isinstance(spec, str):
        return row.get(spec)
    return None


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if re.fullmatch(r"\d{4}", raw):
            dt = datetime(int(raw), 1, 1)
        elif re.fullmatch(r"\d{4}-\d{2}", raw):
            dt = datetime.fromisoformat(raw + "-01")
        else:
            normalized = raw.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise ValueError("event_time_must_be_iso8601_or_year") from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _time_number(value: Any, unit: str) -> float:
    dt = _parse_time(value)
    if unit == "years":
        year_start = datetime(dt.year, 1, 1, tzinfo=timezone.utc)
        next_year = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
        return dt.year + (dt - year_start).total_seconds() / (next_year - year_start).total_seconds()
    if unit == "months":
        month_start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
        if dt.month == 12:
            next_month = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
        return dt.year * 12 + dt.month - 1 + (dt - month_start).total_seconds() / (next_month - month_start).total_seconds()
    seconds = dt.timestamp()
    if unit == "days":
        return seconds / 86400.0
    if unit == "weeks":
        return seconds / 604800.0
    if unit == "hours":
        return seconds / 3600.0
    raise ValueError("unsupported_time_unit")


def normalize_observations(
    rows: Iterable[Mapping[str, Any]],
    mapping: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Normalize source rows to the five-field minimum contract.

    Mapping values are source column names. Constants use {"constant": value}.
    Missing value cells are preserved as status=missing; no zero filling,
    forward filling, or synthetic observations are performed.
    """
    for key in ("entity_id", "metric_id", "event_time"):
        if key not in mapping:
            raise ValueError("mapping_missing_" + key)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    counts = {status: 0 for status in OBSERVATION_STATUSES}

    for row_number, row in enumerate(rows, start=1):
        entity = _mapped(row, mapping["entity_id"])
        metric = _mapped(row, mapping["metric_id"])
        event_time = _mapped(row, mapping["event_time"])
        if entity is None or not str(entity).strip():
            rejected.append({"row": row_number, "reason": "entity_id_missing"})
            continue
        if metric is None or not str(metric).strip():
            rejected.append({"row": row_number, "reason": "metric_id_missing"})
            continue
        if event_time is None or not str(event_time).strip():
            rejected.append({"row": row_number, "reason": "event_time_missing"})
            continue
        try:
            parsed_time = _parse_time(event_time)
        except ValueError:
            rejected.append({"row": row_number, "reason": "event_time_invalid"})
            continue

        raw_value = _mapped(row, mapping.get("value")) if "value" in mapping else None
        explicit_status = _mapped(row, mapping["observation_status"]) if "observation_status" in mapping else None
        status = str(explicit_status).strip().lower() if explicit_status not in (None, "") else None
        if status is None:
            status = "observed" if raw_value not in (None, "") else "missing"
        if status not in OBSERVATION_STATUSES:
            rejected.append({"row": row_number, "reason": "observation_status_invalid"})
            continue

        value: float | None = None
        quality: dict[str, Any] = {}
        if status == "observed":
            try:
                if isinstance(raw_value, bool) or raw_value in (None, ""):
                    raise ValueError
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError
            except (TypeError, ValueError):
                status = "missing" if raw_value in (None, "") else "invalid"
                quality["value_parse_failure"] = True
                value = None
        elif raw_value not in (None, ""):
            quality["value_ignored_for_non_observed_status"] = True

        entity_id, metric_id = str(entity).strip(), str(metric).strip()
        time_text = str(event_time).strip()
        key = (entity_id, metric_id, parsed_time.isoformat())
        if key in seen:
            raise ValueError("duplicate_observation_key:" + "|".join(key))
        seen.add(key)

        item: dict[str, Any] = {
            "entity_id": entity_id,
            "metric_id": metric_id,
            "event_time": time_text,
            "value": value,
            "observation_status": status,
        }
        for key_name in ("unit", "cohort_id", "source_version", "time_support", "exposure_unit"):
            mapped_value = _mapped(row, mapping[key_name]) if key_name in mapping else None
            if mapped_value not in (None, ""):
                item[key_name] = str(mapped_value)
        mapped_source = _mapped(row, mapping["source_id"]) if "source_id" in mapping else source_id
        if mapped_source not in (None, ""):
            item["source_id"] = str(mapped_source)

        if "exposure" in mapping:
            raw_exposure = _mapped(row, mapping["exposure"])
            if raw_exposure not in (None, ""):
                try:
                    exposure_value = float(raw_exposure)
                    if isinstance(raw_exposure, bool) or not math.isfinite(exposure_value) or exposure_value < 0:
                        raise ValueError
                    item["exposure"] = exposure_value
                except (TypeError, ValueError):
                    quality["exposure_invalid"] = True
        if quality:
            item["quality_metadata"] = quality
        accepted.append(item)
        counts[status] += 1

    accepted.sort(key=lambda x: (x["entity_id"], x["metric_id"], _parse_time(x["event_time"])))
    return {
        "observations": accepted,
        "rejected": rejected,
        "counts": counts,
        "accepted_rows": len(accepted),
        "rejected_rows": len(rejected),
    }


def missing_periods(
    observations: Sequence[Mapping[str, Any]],
    expected_times: Sequence[str],
) -> dict[str, Any]:
    """Report explicit missing observations and absent expected periods separately."""
    identities = {(row.get("entity_id"), row.get("metric_id")) for row in observations}
    if len(identities) != 1:
        raise ValueError("missing_periods_requires_one_entity_metric")
    observed_times = {
        _parse_time(row["event_time"]).isoformat()
        for row in observations
        if row["observation_status"] == "observed"
    }
    explicit_missing = {
        _parse_time(row["event_time"]).isoformat()
        for row in observations
        if row["observation_status"] in {"missing", "invalid"}
    }
    expected = {_parse_time(value).isoformat() for value in expected_times}
    present_any_status = observed_times | explicit_missing | {
        _parse_time(row["event_time"]).isoformat()
        for row in observations
        if row["observation_status"] in {"pending", "not_applicable"}
    }
    absent = expected - present_any_status
    return {
        "expected_periods": len(expected),
        "observed_periods": len(expected & observed_times),
        "explicit_missing_or_invalid": len(expected & explicit_missing),
        "absent_records": len(absent),
        "absent_times": sorted(absent),
    }


def detect_missingness_spikes(
    observations: Sequence[Mapping[str, Any]],
    expected_times: Sequence[str],
    *,
    window_size: int = 5,
    minimum_recent_rate: float = 0.30,
    minimum_increase: float = 0.20,
    minimum_window_coverage: float = 0.80,
) -> dict[str, Any]:
    """Detect missingness changes from an explicit expected schedule.

    An absent record is missing only because expected_times declares that a
    measurement was due. pending and not_applicable are excluded from the
    denominator. Signals describe source/collection quality, not entity behavior.
    """
    if window_size < 2:
        raise ValueError("window_size_must_be_at_least_2")
    if not 0 <= minimum_recent_rate <= 1 or not 0 <= minimum_increase <= 1:
        raise ValueError("missingness_threshold_invalid")
    if not 0 < minimum_window_coverage <= 1:
        raise ValueError("minimum_window_coverage_invalid")

    identities = {(row.get("entity_id"), row.get("metric_id")) for row in observations}
    if len(identities) != 1:
        raise ValueError("missingness_spike_requires_one_entity_metric")

    by_time: dict[str, str] = {}
    for row in observations:
        key = _parse_time(row["event_time"]).isoformat()
        if key in by_time:
            raise ValueError("duplicate_missingness_period")
        by_time[key] = str(row["observation_status"])

    expected = [_parse_time(value).isoformat() for value in expected_times]
    if len(set(expected)) != len(expected):
        raise ValueError("duplicate_expected_period")
    if expected != sorted(expected):
        raise ValueError("expected_times_must_be_ascending")

    def window_rate(window: Sequence[str]) -> tuple[float | None, int, int]:
        missing = denominator = 0
        for event_time in window:
            status = by_time.get(event_time)
            if status in {"pending", "not_applicable"}:
                continue
            denominator += 1
            if status in {None, "missing", "invalid"}:
                missing += 1
        coverage = denominator / len(window) if window else 0.0
        if coverage < minimum_window_coverage or denominator == 0:
            return None, missing, denominator
        return missing / denominator, missing, denominator

    signals: list[dict[str, Any]] = []
    checks = 0
    active = False
    for end in range(2 * window_size, len(expected) + 1):
        baseline_slice = expected[end - 2 * window_size:end - window_size]
        recent_slice = expected[end - window_size:end]
        baseline_rate, baseline_missing, baseline_count = window_rate(baseline_slice)
        recent_rate, recent_missing, recent_count = window_rate(recent_slice)
        if baseline_rate is None or recent_rate is None:
            active = False
            continue
        checks += 1
        triggered = (
            recent_rate >= minimum_recent_rate
            and recent_rate - baseline_rate >= minimum_increase
        )
        if triggered and not active:
            entity_id, metric_id = next(iter(identities))
            signals.append({
                "entity_id": entity_id,
                "metric_id": metric_id,
                "signal_type": "data_quality_missingness_spike",
                "event_time": recent_slice[-1],
                "baseline_missing_rate": baseline_rate,
                "recent_missing_rate": recent_rate,
                "baseline_missing_count": baseline_missing,
                "baseline_expected_count": baseline_count,
                "recent_missing_count": recent_missing,
                "recent_expected_count": recent_count,
                "interpretation": "source coverage or collection process changed; not an entity behavior finding",
            })
        active = triggered
    return {"signals": signals, "windows_checked": checks, "signal_count": len(signals)}


def _pearson_rho(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3 or len(x) != len(y):
        return None
    mean_x, mean_y = statistics.mean(x), statistics.mean(y)
    dx = [v - mean_x for v in x]
    dy = [v - mean_y for v in y]
    denom = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denom <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def first_difference_mad_scale(
    observations: Sequence[Mapping[str, Any]],
    *,
    time_unit: str = "years",
    rho: float | None = None,
    estimate_rho: bool = False,
    min_adjacent_pairs_for_rho: int = 1500,
    min_differences: int = 4,
) -> dict[str, Any]:
    """Estimate level-noise scale from actual first differences.

    For a stationary AR(1) level process, a gap of d base units has
    Var(X[t]-X[t-d]) = 2*sigma^2*(1-rho^d). The lag-1 autocorrelation of
    unit first differences is -(1-rho)/2, so rho = 1 + 2*acf1(diff).
    Correlation-centering removes constant linear drift without fitting the
    noisy level series. If AR(1) estimation is requested but lacks sufficient
    consecutive unit-gap differences, this function fails closed and emits no
    scale; it never silently substitutes an IID estimate. This is still a
    candidate estimator, not a universal noise model.
    """
    usable = [
        row for row in observations
        if row.get("observation_status") == "observed"
        and row.get("value") is not None
    ]
    usable.sort(key=lambda x: _parse_time(x["event_time"]))
    if len(usable) < min_differences + 1:
        return {
            "value": None,
            "status": "insufficient_history",
            "method": "first_difference_mad",
            "n_differences": 0,
            "n_unit_gaps": 0,
            "n_rho_lag_pairs": 0,
            "n_gap_adjusted": 0,
            "n_skipped_gaps": 0,
        }
    if min_adjacent_pairs_for_rho < 1 or min_differences < 1:
        raise ValueError("scale_support_parameters_invalid")

    numbers = [_time_number(row["event_time"], time_unit) for row in usable]
    unit_gap_differences: list[tuple[int, float]] = []
    pairs: list[tuple[float, float]] = []
    for i in range(1, len(usable)):
        gap = numbers[i] - numbers[i - 1]
        if gap <= 0:
            raise ValueError("event_time_not_strictly_increasing")
        difference = float(usable[i]["value"]) - float(usable[i - 1]["value"])
        pairs.append((difference, gap))
        if abs(gap - 1.0) <= 0.02:
            unit_gap_differences.append((i, difference))

    rho_was_provided = rho is not None
    rho_source = "provided" if rho_was_provided else "unavailable"
    rho_lag_pairs: list[tuple[float, float]] = []
    for index in range(1, len(unit_gap_differences)):
        previous_index, previous_difference = unit_gap_differences[index - 1]
        current_index, current_difference = unit_gap_differences[index]
        if current_index == previous_index + 1:
            rho_lag_pairs.append((previous_difference, current_difference))

    if rho is None and estimate_rho and len(rho_lag_pairs) < min_adjacent_pairs_for_rho:
        rho_source = "insufficient_consecutive_difference_pairs"

    if rho is None and estimate_rho and len(rho_lag_pairs) >= min_adjacent_pairs_for_rho:
        # For a stationary AR(1) level process, lag-1 autocorrelation of
        # first differences is -(1-rho)/2. Correlation-centering removes a
        # constant linear drift without fitting and subtracting a noisy level
        # trend, which can absorb the low-frequency AR(1) component.
        rho_difference_acf = _pearson_rho(
            [left for left, _ in rho_lag_pairs],
            [right for _, right in rho_lag_pairs],
        )
        if rho_difference_acf is not None:
            estimated_rho = 1.0 + 2.0 * rho_difference_acf
            if math.isfinite(estimated_rho) and -0.95 <= estimated_rho <= 0.95:
                rho = estimated_rho
                rho_source = "estimated_from_first_difference_acf"
            else:
                rho_source = "estimate_outside_supported_range"
        else:
            rho_source = "difference_acf_unidentifiable"

    if rho is not None:
        rho = float(rho)
        if not math.isfinite(rho) or not -0.95 <= rho <= 0.95:
            if rho_was_provided:
                raise ValueError("rho_must_be_finite_and_between_-0.95_and_0.95")
            rho = None
            rho_source = "estimate_outside_supported_range"

    if estimate_rho and rho is None:
        return {
            "value": None,
            "status": "rho_estimation_unavailable",
            "method": "first_difference_mad_ar1_unavailable",
            "rho": None,
            "rho_source": rho_source,
            "n_differences": 0,
            "n_unit_gaps": len(unit_gap_differences),
            "n_rho_lag_pairs": len(rho_lag_pairs),
            "n_gap_adjusted": 0,
            "n_skipped_gaps": len(pairs) - len(unit_gap_differences),
        }

    normalized_differences: list[float] = []
    adjusted_gaps = 0
    unit_gaps = 0
    skipped_gaps = 0
    for difference, gap in pairs:
        nearest = round(gap)
        if abs(gap - nearest) > 0.02 or nearest < 1:
            skipped_gaps += 1
            continue
        if rho is None:
            if nearest != 1:
                skipped_gaps += 1
                continue
            denominator = math.sqrt(2.0)
        else:
            term = 1.0 - (rho ** nearest)
            if term <= 1e-9:
                skipped_gaps += 1
                continue
            denominator = math.sqrt(2.0 * term)
            if nearest > 1:
                adjusted_gaps += 1
            else:
                unit_gaps += 1
        normalized_differences.append(difference / denominator)

    if len(normalized_differences) < min_differences:
        return {
            "value": None,
            "status": "insufficient_supported_differences",
            "method": "first_difference_mad",
            "rho": rho,
            "rho_source": rho_source,
            "n_differences": len(normalized_differences),
            "n_unit_gaps": unit_gaps,
            "n_rho_lag_pairs": len(rho_lag_pairs),
            "n_gap_adjusted": adjusted_gaps,
            "n_skipped_gaps": skipped_gaps,
        }

    center = statistics.median(normalized_differences)
    scale = 1.4826 * statistics.median(abs(x - center) for x in normalized_differences)
    if not math.isfinite(scale) or scale <= 0:
        status = "zero_or_invalid_scale"
        result_scale = None
    else:
        status = "ok"
        result_scale = scale

    if rho is None:
        method = "first_difference_mad_iid_unit_gap_only"
    elif adjusted_gaps:
        method = "first_difference_mad_ar1_gap_adjusted"
    else:
        method = "first_difference_mad_ar1_unit_gap"

    return {
        "value": result_scale,
        "status": status,
        "method": method,
        "rho": rho,
        "rho_source": rho_source,
        "n_differences": len(normalized_differences),
        "n_unit_gaps": unit_gaps,
        "n_rho_lag_pairs": len(rho_lag_pairs),
        "n_gap_adjusted": adjusted_gaps,
        "n_skipped_gaps": skipped_gaps,
    }


def _theil_sen_prediction(
    history: Sequence[Mapping[str, Any]],
    target_time: str,
    time_unit: str,
) -> float:
    x_values = [_time_number(row["event_time"], time_unit) for row in history]
    origin = x_values[0]
    x = [value - origin for value in x_values]
    y = [float(row["value"]) for row in history]
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(len(x))
        for j in range(i + 1, len(x))
        if x[j] > x[i]
    ]
    if not slopes:
        return statistics.median(y)
    slope = statistics.median(slopes)
    intercept = statistics.median(y[i] - slope * x[i] for i in range(len(x)))
    target_x = _time_number(target_time, time_unit) - origin
    return intercept + slope * target_x


def build_univariate_residuals(
    observations: Sequence[Mapping[str, Any]],
    *,
    baseline_window: int = 12,
    min_history: int = 8,
    time_unit: str = "years",
    baseline_method: str = "rolling_median",
    estimate_rho: bool = False,
    scale_window: int | None = None,
    min_adjacent_pairs_for_rho: int = 1500,
) -> list[dict[str, Any]]:
    """Prequential baseline; current observation never trains itself."""
    if baseline_window < min_history or min_history < 4:
        raise ValueError("baseline_window_must_be_at_least_min_history_and_min_history_ge_4")
    if baseline_method not in {"rolling_median", "rolling_theil_sen"}:
        raise ValueError("baseline_method_unsupported")
    effective_scale_window = baseline_window if scale_window is None else scale_window
    if effective_scale_window < min_history or min_adjacent_pairs_for_rho < 4:
        raise ValueError("scale_window_or_rho_support_invalid")
    identities = {(row["entity_id"], row["metric_id"]) for row in observations}
    if len(identities) > 1:
        raise ValueError("build_univariate_residuals_requires_one_entity_metric")
    series = [
        row for row in observations
        if row.get("observation_status") == "observed" and row.get("value") is not None
    ]
    series.sort(key=lambda x: _parse_time(x["event_time"]))
    residual_rows: list[dict[str, Any]] = []
    for index in range(min_history, len(series)):
        history = series[max(0, index - baseline_window):index]
        scale_history = series[max(0, index - effective_scale_window):index]
        scale = first_difference_mad_scale(
            scale_history,
            time_unit=time_unit,
            estimate_rho=estimate_rho,
            min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
        )
        if baseline_method == "rolling_theil_sen":
            expected = _theil_sen_prediction(history, series[index]["event_time"], time_unit)
        else:
            expected = statistics.median(float(row["value"]) for row in history)
        observed = float(series[index]["value"])
        ready = scale["status"] == "ok" and scale["value"] is not None
        observation_gap = (
            _time_number(series[index]["event_time"], time_unit)
            - _time_number(history[-1]["event_time"], time_unit)
        )
        gap_unresolved = observation_gap > 1.02
        residual = observed - expected
        residual_rows.append({
            "entity_id": series[index]["entity_id"],
            "metric_id": series[index]["metric_id"],
            "event_time": series[index]["event_time"],
            "observed": observed,
            "expected": expected,
            "observed_value": observed,
            "expected_value": expected,
            "residual": residual,
            "scale": scale["value"],
            "unit": series[index].get("unit"),
            "baseline_id": (
                str(series[index]["metric_id"]) + ":" + baseline_method
                + ":w" + str(baseline_window)
                + ":sw" + str(effective_scale_window)
                + ":" + scale["method"]
            ),
            "z_score": residual / scale["value"] if ready and not gap_unresolved else None,
            "status": (
                "gap_unresolved" if gap_unresolved
                else "ready" if ready
                else "scale_unavailable"
            ),
            "observation_gap_units": observation_gap,
            "baseline_method": "prequential_" + baseline_method,
            "baseline_support": len(history),
            "support_count": len(history),
            "scale_method": scale["method"],
            "scale_rho_estimation": estimate_rho,
            "scale_rho_source": scale.get("rho_source"),
            "scale_n_unit_gaps": scale.get("n_unit_gaps"),
            "scale_n_gap_adjusted": scale.get("n_gap_adjusted"),
            "scale_n_skipped_gaps": scale.get("n_skipped_gaps"),
            "scale_window": effective_scale_window,
            "min_adjacent_pairs_for_rho": min_adjacent_pairs_for_rho,
            "scale_support": scale["n_differences"],
            "rho": scale.get("rho"),
        })
    return residual_rows


def _theil_sen_relation(
    pairs: Sequence[tuple[float, float]],
) -> tuple[float, float] | None:
    """Fit y = intercept + slope*x robustly from explicitly paired history."""
    slopes = [
        (pairs[j][1] - pairs[i][1]) / (pairs[j][0] - pairs[i][0])
        for i in range(len(pairs))
        for j in range(i + 1, len(pairs))
        if pairs[j][0] != pairs[i][0]
    ]
    if not slopes:
        return None
    slope = statistics.median(slopes)
    intercept = statistics.median(y - slope * x for x, y in pairs)
    return intercept, slope


def build_partial_relation_residuals(
    observations: Sequence[Mapping[str, Any]],
    *,
    x_metric_id: str,
    y_metric_id: str,
    relationship_id: str,
    baseline_window: int = 24,
    min_pairs: int = 8,
    time_unit: str = "years",
) -> list[dict[str, Any]]:
    """Build prequential residuals for an explicitly declared two-metric relation.

    Only same-entity, same-time, actually observed pairs are used. The relation
    is descriptive, not causal or a hard conservation law. At every scored
    time, Theil-Sen is fitted only to earlier pairs. Missing counterparts are
    skipped rather than imputed. Metric units must be stable within each entity.
    """
    if not x_metric_id or not y_metric_id or x_metric_id == y_metric_id:
        raise ValueError("partial_relation_requires_two_distinct_metrics")
    if not relationship_id or not relationship_id.strip():
        raise ValueError("relationship_id_required")
    if min_pairs < 4 or baseline_window < min_pairs:
        raise ValueError("partial_relation_history_invalid")

    selected: dict[tuple[str, str], dict[str, tuple[float, str | None]]] = defaultdict(dict)
    units_seen: dict[tuple[str, str], set[str | None]] = defaultdict(set)
    seen_keys: set[tuple[str, str, str]] = set()
    for row in observations:
        metric_id = str(row.get("metric_id", ""))
        if metric_id not in {x_metric_id, y_metric_id}:
            continue
        entity_id = str(row.get("entity_id", "")).strip()
        if not entity_id:
            raise ValueError("partial_relation_entity_id_missing")
        event_time = _parse_time(row["event_time"]).isoformat()
        unique_key = (entity_id, metric_id, event_time)
        if unique_key in seen_keys:
            raise ValueError("partial_relation_duplicate_observation")
        seen_keys.add(unique_key)
        unit = str(row.get("unit")) if row.get("unit") not in (None, "") else None
        if unit is not None:
            units_seen[(entity_id, metric_id)].add(unit)
        if row.get("observation_status") != "observed" or row.get("value") is None:
            continue
        value = float(row["value"])
        if not math.isfinite(value):
            continue
        selected[(entity_id, event_time)][metric_id] = (value, unit)

    for entity_metric, units in units_seen.items():
        if len(units) > 1:
            raise ValueError("partial_relation_unit_changed_without_metric_version:" + "|".join(entity_metric))

    by_entity: dict[str, list[tuple[str, float, float, str | None, str | None]]] = defaultdict(list)
    for (entity_id, event_time), metrics in selected.items():
        if x_metric_id not in metrics or y_metric_id not in metrics:
            continue
        x_value, x_unit = metrics[x_metric_id]
        y_value, y_unit = metrics[y_metric_id]
        by_entity[entity_id].append((event_time, x_value, y_value, x_unit, y_unit))

    output: list[dict[str, Any]] = []
    for entity_id, entity_pairs in by_entity.items():
        entity_pairs.sort(key=lambda item: _parse_time(item[0]))
        for index in range(min_pairs, len(entity_pairs)):
            history = entity_pairs[max(0, index - baseline_window):index]
            event_time, x_value, y_value, x_unit, y_unit = entity_pairs[index]
            fit_pairs = [(item[1], item[2]) for item in history]
            fitted = _theil_sen_relation(fit_pairs)
            if fitted is None:
                output.append({
                    "entity_id": entity_id,
                    "metric_id": y_metric_id,
                    "relationship_id": relationship_id,
                    "event_time": event_time,
                    "observed_value": y_value,
                    "expected_value": None,
                    "residual": None,
                    "scale": None,
                    "z_score": None,
                    "status": "relation_unidentifiable",
                    "baseline_id": relationship_id,
                    "baseline_method": "prequential_theil_sen_pairwise_relation",
                    "support_count": len(history),
                    "unit": y_unit,
                    "x_metric_id": x_metric_id,
                    "x_value": x_value,
                    "relationship_semantics": "explicit_statistical_relation_not_causal_or_conservation_proof",
                })
                continue
            intercept, slope = fitted
            historical_residuals = [
                y - (intercept + slope * x)
                for x, y in fit_pairs
            ]
            residual_center = statistics.median(historical_residuals)
            scale = 1.4826 * statistics.median(
                abs(value - residual_center) for value in historical_residuals
            )
            observation_gap = (
                _time_number(event_time, time_unit)
                - _time_number(history[-1][0], time_unit)
            )
            gap_unresolved = observation_gap > 1.02
            expected = intercept + slope * x_value
            residual = y_value - expected
            ready = math.isfinite(scale) and scale > 0
            output.append({
                "entity_id": entity_id,
                "metric_id": y_metric_id,
                "relationship_id": relationship_id,
                "event_time": event_time,
                "observed_value": y_value,
                "expected_value": expected,
                "baseline_id": relationship_id,
                "baseline_method": "prequential_theil_sen_pairwise_relation",
                "unit": y_unit,
                "x_metric_id": x_metric_id,
                "y_metric_id": y_metric_id,
                "x_value": x_value,
                "y_observed": y_value,
                "y_expected": expected,
                "residual": residual,
                "observed": y_value,
                "expected": expected,
                "scale": scale if ready else None,
                "z_score": residual / scale if ready and not gap_unresolved else None,
                "status": (
                    "gap_unresolved" if gap_unresolved
                    else "ready" if ready
                    else "relation_scale_unavailable"
                ),
                "observation_gap_units": observation_gap,
                "support_count": len(history),
                "slope": slope,
                "intercept": intercept,
                "x_unit": x_unit,
                "y_unit": y_unit,
                "relationship_semantics": "explicit_statistical_relation_not_causal_or_conservation_proof",
            })
    output.sort(key=lambda row: (row["entity_id"], row["event_time"]))
    return output


def _group_residual_series(
    residual_rows: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    """Validate and split rows so detector state never leaks across entities."""
    validate_residual_contract(residual_rows)
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in residual_rows:
        key = (
            str(row["entity_id"]),
            str(row["metric_id"]),
            str(row["baseline_id"]),
        )
        grouped[key].append(row)

    output: list[list[Mapping[str, Any]]] = []
    for key, rows in grouped.items():
        rows.sort(key=lambda row: _parse_time(row["event_time"]))
        times = [_parse_time(row["event_time"]) for row in rows]
        if len(set(times)) != len(times):
            raise ValueError("residual_series_duplicate_event_time:" + "|".join(key))
        output.append(rows)
    output.sort(key=lambda rows: (
        str(rows[0]["entity_id"]),
        str(rows[0]["metric_id"]),
        str(rows[0]["baseline_id"]),
    ))
    return output


def detect_two_sided_cusum(
    residual_rows: Sequence[Mapping[str, Any]],
    *,
    k: float = 0.5,
    h: float = 8.5,
) -> list[dict[str, Any]]:
    """Candidate two-sided CUSUM; thresholds require domain calibration."""
    if k < 0 or h <= 0:
        raise ValueError("cusum_thresholds_invalid")
    hits: list[dict[str, Any]] = []
    for series in _group_residual_series(residual_rows):
        positive = negative = 0.0
        for index, row in enumerate(series):
            if row.get("status") != "ready" or row.get("z_score") is None:
                positive = negative = 0.0
                continue
            z = float(row["z_score"])
            positive = max(0.0, positive + z - k)
            negative = max(0.0, negative - z - k)
            if positive >= h:
                hits.append({
                    "detector": "cusum",
                    "direction": "positive",
                    "index": index,
                    "entity_id": row["entity_id"],
                    "metric_id": row["metric_id"],
                    "baseline_id": row["baseline_id"],
                    "event_time": row["event_time"],
                    "z_score": z,
                    "accumulator": positive,
                })
                positive = negative = 0.0
            elif negative >= h:
                hits.append({
                    "detector": "cusum",
                    "direction": "negative",
                    "index": index,
                    "entity_id": row["entity_id"],
                    "metric_id": row["metric_id"],
                    "baseline_id": row["baseline_id"],
                    "event_time": row["event_time"],
                    "z_score": z,
                    "accumulator": negative,
                })
                positive = negative = 0.0
    return sorted(hits, key=lambda hit: (
        _parse_time(hit["event_time"]), hit["entity_id"], hit["metric_id"]
    ))


def detect_sign_runs(
    residual_rows: Sequence[Mapping[str, Any]],
    *,
    threshold: float = 3.0,
    run_length: int = 3,
) -> list[dict[str, Any]]:
    """Candidate P1-style sign-run detector, kept independent from CUSUM."""
    if threshold <= 0 or run_length < 1:
        raise ValueError("sign_run_parameters_invalid")
    hits: list[dict[str, Any]] = []
    for series in _group_residual_series(residual_rows):
        sign = 0
        streak: list[tuple[int, Mapping[str, Any]]] = []
        for index, row in enumerate(series):
            if row.get("status") != "ready" or row.get("z_score") is None:
                sign, streak = 0, []
                continue
            z = float(row["z_score"])
            current_sign = 1 if z > 0 else -1 if z < 0 else 0
            if current_sign == 0 or abs(z) < threshold:
                sign, streak = 0, []
                continue
            if sign != current_sign:
                sign, streak = current_sign, []
            streak.append((index, row))
            if len(streak) >= run_length:
                hit_index, hit_row = streak[-1]
                hits.append({
                    "detector": "sign_run",
                    "direction": "positive" if sign > 0 else "negative",
                    "index": hit_index,
                    "entity_id": hit_row["entity_id"],
                    "metric_id": hit_row["metric_id"],
                    "baseline_id": hit_row["baseline_id"],
                    "event_time": hit_row["event_time"],
                    "z_score": float(hit_row["z_score"]),
                    "run_length": run_length,
                })
                sign, streak = 0, []
    return sorted(hits, key=lambda hit: (
        _parse_time(hit["event_time"]), hit["entity_id"], hit["metric_id"]
    ))


def first_evidence_at_or_after(
    hits: Sequence[Mapping[str, Any]],
    onset_time: str,
) -> dict[str, Any] | None:
    """Evaluate evidence time independently of any fused event's earlier start."""
    onset = _parse_time(onset_time)
    eligible = [hit for hit in hits if _parse_time(hit["event_time"]) >= onset]
    if not eligible:
        return None
    return min(eligible, key=lambda hit: _parse_time(hit["event_time"]))


def cohort_peer_residuals(
    observations: Sequence[Mapping[str, Any]],
    *,
    min_peers: int = 5,
    use_exposure: bool = False,
) -> list[dict[str, Any]]:
    """Same-period peer comparison using an explicit, caller-provided cohort_id.

    No cohort is inferred from country names, role names, or numeric similarity.
    Each entity is excluded from its own peer median. Complexity is O(n log n).
    """
    if min_peers < 1:
        raise ValueError("min_peers_must_be_positive")
    buckets: dict[tuple[str, str, str, str, str], list[tuple[float, str]]] = defaultdict(list)
    seen_entity_period: set[tuple[str, str, str, str]] = set()
    for row in observations:
        cohort = row.get("cohort_id")
        if cohort in (None, ""):
            continue
        canonical_time = _parse_time(row["event_time"]).isoformat()
        entity_id = str(row["entity_id"])
        unique_key = (str(row["metric_id"]), canonical_time, str(cohort), entity_id)
        if unique_key in seen_entity_period:
            raise ValueError("duplicate_entity_metric_time_in_cohort")
        seen_entity_period.add(unique_key)
        if row.get("observation_status") != "observed" or row.get("value") is None:
            continue
        raw_observed_value = float(row["value"])
        peer_value = raw_observed_value
        metric_unit = str(row.get("unit") or "")
        exposure_unit = ""
        if use_exposure:
            exposure = row.get("exposure")
            exposure_unit = str(row.get("exposure_unit") or "")
            if exposure is None or not exposure_unit or not metric_unit:
                continue
            exposure = float(exposure)
            if not math.isfinite(exposure) or exposure <= 0:
                continue
            peer_value = peer_value / exposure
        key = (str(row["metric_id"]), canonical_time, str(cohort), metric_unit, exposure_unit)
        buckets[key].append((peer_value, entity_id))

    output: list[dict[str, Any]] = []
    for (metric_id, event_time, cohort, metric_unit, exposure_unit), members in buckets.items():
        members.sort(key=lambda pair: (pair[0], pair[1]))
        values = [pair[0] for pair in members]
        cohort_center = statistics.median(values)
        cohort_mad = statistics.median(abs(value - cohort_center) for value in values)
        cohort_scale = 1.4826 * cohort_mad
        for index, (value, entity_id) in enumerate(members):
            peer_count = len(values) - 1
            if peer_count < min_peers:
                continue
            remaining_count = peer_count
            lower = (remaining_count - 1) // 2
            upper = remaining_count // 2

            def without_self(position: int) -> float:
                return values[position] if position < index else values[position + 1]

            peer_median = (without_self(lower) + without_self(upper)) / 2.0
            peer_scale = cohort_scale
            comparable_unit = (
                metric_unit + "/" + exposure_unit
                if use_exposure else metric_unit or None
            )
            baseline_id = (
                "peer:" + metric_id + ":" + cohort + ":"
                + (metric_unit or "unit-unspecified") + ":"
                + (exposure_unit or "raw")
            )
            peer_residual = value - peer_median
            scale_ready = math.isfinite(peer_scale) and peer_scale > 0
            output.append({
                "entity_id": entity_id,
                "metric_id": metric_id,
                "event_time": event_time,
                "cohort_id": cohort,
                "unit": comparable_unit,
                "exposure_unit": exposure_unit or None,
                "observed": value,
                "expected": peer_median,
                "observed_value": value,
                "expected_value": peer_median,
                "residual": peer_residual,
                "scale": peer_scale if scale_ready else None,
                "z_score": peer_residual / peer_scale if scale_ready else None,
                "status": "ready" if scale_ready else "peer_scale_unavailable",
                "baseline_id": baseline_id,
                "baseline_method": "same_period_peer_median",
                "support_count": peer_count,
                "peer_expected": peer_median,
                "peer_residual": peer_residual,
                "peer_count": peer_count,
                "raw_observed_value": raw_observed_value,
                "value_basis": "value_per_exposure" if use_exposure else "raw_value",
            })
    output.sort(key=lambda row: (row["metric_id"], row["event_time"], row["cohort_id"], row["entity_id"]))
    return output


def benjamini_hochberg(p_values: Sequence[float], *, q: float = 0.05) -> list[bool]:
    """BH step-up correction for already-valid, comparable p-values."""
    if not 0 < q < 1:
        raise ValueError("q_must_be_between_zero_and_one")
    if any(not math.isfinite(float(p)) or not 0 <= float(p) <= 1 for p in p_values):
        raise ValueError("p_values_must_be_finite_and_between_zero_and_one")
    count = len(p_values)
    if count == 0:
        return []
    ranked = sorted(enumerate(float(p) for p in p_values), key=lambda item: item[1])
    cutoff = 0
    for rank, (_, p_value) in enumerate(ranked, start=1):
        if p_value <= q * rank / count:
            cutoff = rank
    rejected = [False] * count
    for index, _ in ranked[:cutoff]:
        rejected[index] = True
    return rejected


def false_alerts_per_1000_entity_year(
    false_alerts: int,
    entity_years: float,
) -> float:
    """Temporal fleet-level false-alert rate; requires observed entity-time exposure."""
    if false_alerts < 0 or not math.isfinite(entity_years) or entity_years <= 0:
        raise ValueError("false_alert_rate_inputs_invalid")
    return 1000.0 * false_alerts / entity_years


def run_candidate_detectors(
    residual_rows: Sequence[Mapping[str, Any]],
    *,
    cusum_k: float = 0.5,
    cusum_h: float = 8.5,
    p1_threshold: float = 3.0,
    p1_run_length: int = 3,
) -> dict[str, Any]:
    """Return independent raw detector evidence; no suppression or event fusion."""
    cusum_hits = detect_two_sided_cusum(residual_rows, k=cusum_k, h=cusum_h)
    sign_hits = detect_sign_runs(residual_rows, threshold=p1_threshold, run_length=p1_run_length)
    return {
        "raw_hits": {"cusum": cusum_hits, "sign_run": sign_hits},
        "calibration_status": "candidate_thresholds_not_calibrated_for_production",
        "event_fusion": "not_applied",
        "alert_suppression": "not_applied",
    }
