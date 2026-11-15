"""Real-series threshold sweep for the domain-neutral break detectors.

This tool reports observed historical signal density separately from controlled
injection response. Historical hits are NOT labelled false positives because
the committed public sources have no trusted anomaly ground truth.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from experiments.identity_lab.exp_p_engine.domain_neutral import (
    build_univariate_residuals,
    detect_sign_runs,
    detect_two_sided_cusum,
    first_difference_mad_scale,
    estimate_panel_ar1_rho,
    first_evidence_at_or_after,
    normalize_observations,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "raw"
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_threshold_sweep.json"
)

BASELINE_CONFIGS = (
    {
        "label": "rolling_median_iid_scale",
        "baseline_method": "rolling_median",
        "estimate_rho": False,
        "scale_window": 12,
        "min_adjacent_pairs_for_rho": 16,
    },
    {
        "label": "rolling_theil_sen_iid_scale",
        "baseline_method": "rolling_theil_sen",
        "estimate_rho": False,
        "scale_window": 12,
        "min_adjacent_pairs_for_rho": 16,
    },
    {
        "label": "rolling_theil_sen_first_difference_acf_ar1_scale",
        "baseline_method": "rolling_theil_sen",
        "estimate_rho": True,
        "scale_window": 2048,
        "min_adjacent_pairs_for_rho": 1500,
    },
)
MAX_ACCEPTABLE_DELAY_TIME_UNITS = 3.0
CUSUM_GRID = (
    {"k": 0.25, "h": 8.5},
    {"k": 0.25, "h": 12.0},
    {"k": 0.50, "h": 8.5},
    {"k": 0.50, "h": 12.0},
    {"k": 0.50, "h": 16.0},
    {"k": 0.75, "h": 12.0},
    {"k": 1.00, "h": 16.0},
)
P1_GRID = (
    {"threshold": 3.0, "run_length": 3},
    {"threshold": 3.0, "run_length": 4},
    {"threshold": 3.5, "run_length": 3},
    {"threshold": 3.5, "run_length": 4},
    {"threshold": 4.0, "run_length": 3},
    {"threshold": 4.0, "run_length": 4},
)
INJECTION_MAGNITUDES = (3.0, 6.0)
INJECTION_DIRECTIONS = (-1, 1)


def _time_position(value: str, time_unit: str) -> float:
    raw = str(value).strip()
    if time_unit == "years":
        if len(raw) >= 4 and raw[:4].isdigit():
            return float(int(raw[:4]))
    if time_unit == "months":
        if len(raw) >= 7 and raw[4] == "-" and raw[:4].isdigit():
            year, month = int(raw[:4]), int(raw[5:7])
            return float(year * 12 + month - 1)
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if time_unit == "years":
        year_start = datetime(parsed.year, 1, 1, tzinfo=timezone.utc)
        next_year = datetime(parsed.year + 1, 1, 1, tzinfo=timezone.utc)
        return parsed.year + (parsed - year_start).total_seconds() / (next_year - year_start).total_seconds()
    if time_unit == "months":
        month_start = datetime(parsed.year, parsed.month, 1, tzinfo=timezone.utc)
        if parsed.month == 12:
            next_month = datetime(parsed.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(parsed.year, parsed.month + 1, 1, tzinfo=timezone.utc)
        return parsed.year * 12 + parsed.month - 1 + (
            parsed - month_start
        ).total_seconds() / (next_month - month_start).total_seconds()
    raise ValueError("unsupported_delay_time_unit:" + time_unit)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_world_bank() -> dict[str, list[dict[str, Any]]]:
    folder = DATA / "financial_world_bank_v1"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    rows = read_csv(folder / "WB_FS_AST_PRVT_GD_ZS_2000_2024.csv")
    normalized = normalize_observations(
        rows,
        {
            "entity_id": "entity_code",
            "metric_id": {"constant": manifest["indicator"]},
            "event_time": "year",
            "value": "value",
            "unit": {"constant": "% of GDP"},
            "source_id": {"constant": "World Bank"},
            "time_support": {"constant": "annual"},
        },
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized["observations"]:
        grouped[row["entity_id"]].append(row)
    return dict(grouped)


def read_usgs_monthly() -> dict[str, list[dict[str, Any]]]:
    folder = DATA / "usgs_earthquake_m6_5_2000_2024"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    raw_rows = read_csv(folder / manifest["raw_file"])
    normalized = normalize_observations(
        raw_rows,
        {
            "entity_id": {"constant": "USGS:global:magnitude-ge-6.5"},
            "metric_id": {"constant": "earthquake_event_magnitude"},
            "event_time": "time",
            "value": "mag",
            "unit": {"constant": "magnitude"},
            "source_id": {"constant": "USGS FDSN event catalog"},
            "time_support": {"constant": "event"},
        },
    )
    counts: Counter[str] = Counter()
    for row in normalized["observations"]:
        counts[row["event_time"][:7]] += 1
    monthly: list[dict[str, Any]] = []
    for year in range(2000, 2025):
        for month in range(1, 13):
            period = f"{year:04d}-{month:02d}"
            monthly.append({
                "entity_id": "USGS:global:magnitude-ge-6.5",
                "metric_id": "monthly_count_magnitude_ge_6_5",
                "event_time": period,
                "value": float(counts[period]),
                "observation_status": "observed",
                "unit": "events/month",
                "source_id": "USGS FDSN event catalog",
                "time_support": "monthly",
            })
    return {"USGS:global:magnitude-ge-6.5": monthly}


def ready_period_count(residuals: list[dict[str, Any]]) -> int:
    return sum(1 for row in residuals if row["status"] == "ready")


def historical_detector_profile(
    residuals: list[dict[str, Any]],
) -> dict[str, Any]:
    ready = ready_period_count(residuals)
    cusum: list[dict[str, Any]] = []
    p1: list[dict[str, Any]] = []
    for params in CUSUM_GRID:
        hits = detect_two_sided_cusum(residuals, k=params["k"], h=params["h"])
        cusum.append({
            **params,
            "raw_hits": len(hits),
            "positive_hits": sum(1 for hit in hits if hit["direction"] == "positive"),
            "negative_hits": sum(1 for hit in hits if hit["direction"] == "negative"),
            "observed_signal_rate_per_1000_ready_periods": (
                1000.0 * len(hits) / ready if ready else None
            ),
        })
    for params in P1_GRID:
        hits = detect_sign_runs(
            residuals,
            threshold=params["threshold"],
            run_length=params["run_length"],
        )
        p1.append({
            **params,
            "raw_hits": len(hits),
            "positive_hits": sum(1 for hit in hits if hit["direction"] == "positive"),
            "negative_hits": sum(1 for hit in hits if hit["direction"] == "negative"),
            "observed_signal_rate_per_1000_ready_periods": (
                1000.0 * len(hits) / ready if ready else None
            ),
        })
    return {
        "ready_periods": ready,
        "cusum_p1_disabled": cusum,
        "sign_run_cusum_disabled": p1,
        "interpretation": (
            "Rates are observed signal density on the historical source. They are not "
            "false-positive rates because source periods have no trusted anomaly labels."
        ),
    }


def inject_persistent_level_shift(
    series: list[dict[str, Any]],
    *,
    magnitude_sigma: float,
    direction: int,
    time_unit: str,
    estimate_rho: bool,
    min_adjacent_pairs_for_rho: int,
    scale_rho: float | None = None,
) -> tuple[list[dict[str, Any]] | None, str | None, int | None, float | None]:
    observed = [
        row for row in series
        if row.get("observation_status") == "observed" and row.get("value") is not None
    ]
    observed.sort(key=lambda row: row["event_time"])
    if len(observed) < 12:
        return None, None, None, None
    onset_index = min(max(8, int(len(observed) * 0.65)), len(observed) - 3)
    pre_onset = observed[:onset_index]
    scale = first_difference_mad_scale(
        pre_onset,
        time_unit=time_unit,
        estimate_rho=estimate_rho,
        rho=scale_rho,
        min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
    )
    if scale["status"] != "ok" or scale["value"] is None:
        return None, None, None, None
    if estimate_rho and scale.get("rho") is None:
        return None, None, None, None
    shift = direction * magnitude_sigma * float(scale["value"])
    injected = [dict(row) for row in observed]
    for index in range(onset_index, len(injected)):
        injected[index]["value"] = float(injected[index]["value"]) + shift
    return injected, injected[onset_index]["event_time"], onset_index, float(scale["value"])


def injection_response_for_series(
    series: list[dict[str, Any]],
    *,
    baseline_method: str,
    time_unit: str,
    estimate_rho: bool,
    min_adjacent_pairs_for_rho: int,
    scale_rho: float | None = None,
) -> dict[str, Any]:
    responses: dict[str, dict[str, Any]] = {}
    for magnitude in INJECTION_MAGNITUDES:
        for direction in INJECTION_DIRECTIONS:
            key = f"{'positive' if direction > 0 else 'negative'}_{magnitude:g}sigma"
            injected, onset, onset_index, sigma = inject_persistent_level_shift(
                series,
                magnitude_sigma=magnitude,
                direction=direction,
                time_unit=time_unit,
                estimate_rho=estimate_rho,
                min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
                scale_rho=scale_rho,
            )
            if injected is None or onset is None or onset_index is None or sigma is None:
                responses[key] = {
                    "tested": False,
                    "skip_reason": "insufficient_pre_onset_ar1_support" if estimate_rho else "insufficient_scale_support",
                }
                continue
            residuals = build_univariate_residuals(
                injected,
                baseline_window=12,
                min_history=8,
                time_unit=time_unit,
                baseline_method=baseline_method,
                estimate_rho=estimate_rho,
                scale_window=12,
                min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
                scale_rho=scale_rho,
            )
            # The detector starts at the injection onset; pre-onset residuals
            # cannot carry a partially accumulated CUSUM state into the test.
            scored_residuals = [
                row for row in residuals
                if _time_position(row["event_time"], time_unit)
                >= _time_position(onset, time_unit)
            ]
            cusum_params_result: list[dict[str, Any]] = []
            for params in CUSUM_GRID:
                hits = detect_two_sided_cusum(
                    scored_residuals, k=params["k"], h=params["h"]
                )
                first = first_evidence_at_or_after(hits, onset)
                delay = None
                delay_time_units = None
                if first is not None:
                    detected_index = next(
                        index for index, row in enumerate(scored_residuals)
                        if row["event_time"] == first["event_time"]
                    )
                    onset_residual_index = next(
                        (
                            index for index, row in enumerate(scored_residuals)
                            if row["event_time"] == onset
                        ),
                        None,
                    )
                    if onset_residual_index is not None:
                        delay = detected_index - onset_residual_index
                    delay_time_units = (
                        _time_position(first["event_time"], time_unit)
                        - _time_position(onset, time_unit)
                    )
                cusum_params_result.append({
                    **params,
                    "detected": first is not None,
                    "direction_detected": first["direction"] if first else None,
                    "first_evidence_time": first["event_time"] if first else None,
                    "delay_observations": delay,
                    "delay_time_units": delay_time_units,
                })

            p1_params_result: list[dict[str, Any]] = []
            for params in P1_GRID:
                hits = detect_sign_runs(
                    scored_residuals,
                    threshold=params["threshold"],
                    run_length=params["run_length"],
                )
                first = first_evidence_at_or_after(hits, onset)
                delay = None
                delay_time_units = None
                if first is not None:
                    detected_index = next(
                        index for index, row in enumerate(scored_residuals)
                        if row["event_time"] == first["event_time"]
                    )
                    onset_residual_index = next(
                        (
                            index for index, row in enumerate(scored_residuals)
                            if row["event_time"] == onset
                        ),
                        None,
                    )
                    if onset_residual_index is not None:
                        delay = detected_index - onset_residual_index
                    delay_time_units = (
                        _time_position(first["event_time"], time_unit)
                        - _time_position(onset, time_unit)
                    )
                p1_params_result.append({
                    **params,
                    "detected": first is not None,
                    "direction_detected": first["direction"] if first else None,
                    "first_evidence_time": first["event_time"] if first else None,
                    "delay_observations": delay,
                    "delay_time_units": delay_time_units,
                })
            responses[key] = {
                "tested": True,
                "onset_time": onset,
                "injection_scale": sigma,
                "cusum": cusum_params_result,
                "sign_run": p1_params_result,
            }
    return responses


def wilson_interval(successes: int, total: int, *, z: float = 1.96) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    denominator = 1.0 + (z * z / total)
    center = (p + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * (
            p * (1.0 - p) / total
            + z * z / (4.0 * total * total)
        ) ** 0.5
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def summarize_injection_responses(
    all_responses: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for detector in ("cusum", "sign_run"):
        if detector == "cusum":
            grid = CUSUM_GRID
            get_key = lambda p: (p["k"], p["h"])
        else:
            grid = P1_GRID
            get_key = lambda p: (p["threshold"], p["run_length"])
        by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
        skipped_by_scenario: Counter[str] = Counter()
        for response in all_responses:
            for scenario, result in response.items():
                if not result.get("tested", True):
                    skipped_by_scenario[scenario] += 1
                    continue
                for candidate in result[detector]:
                    by_scenario[scenario].append(candidate)
        scenario_names = sorted(set(by_scenario) | set(skipped_by_scenario))
        scenario_summary: dict[str, Any] = {}
        for scenario in scenario_names:
            results = by_scenario.get(scenario, [])
            candidate_rows = []
            for params in grid:
                key = get_key(params)
                matching = [
                    row for row in results
                    if (
                        get_key(row) == key
                    )
                ]
                detected = [row for row in matching if row["detected"]]
                delays = [
                    row["delay_time_units"]
                    for row in detected
                    if row.get("delay_time_units") is not None
                ]
                fast_detected = [
                    row for row in detected
                    if row.get("delay_time_units") is not None
                    and row["delay_time_units"] <= MAX_ACCEPTABLE_DELAY_TIME_UNITS
                ]
                ci_low, ci_high = wilson_interval(len(detected), len(matching))
                fast_ci_low, fast_ci_high = wilson_interval(len(fast_detected), len(matching))
                candidate_rows.append({
                    **params,
                    "tested_injections": len(matching),
                    "detected_injections": len(detected),
                    "injection_recall": (
                        len(detected) / len(matching) if matching else None
                    ),
                    "injection_recall_wilson95": [ci_low, ci_high],
                    "detected_within_delay_budget": len(fast_detected),
                    "recall_within_delay_budget": (
                        len(fast_detected) / len(matching) if matching else None
                    ),
                    "recall_within_delay_budget_wilson95": [fast_ci_low, fast_ci_high],
                    "median_detection_delay_time_units": (
                        median(delays) if delays else None
                    ),
                    "direction_matches_injection": sum(
                        1 for row in detected
                        if row["direction_detected"] ==
                        ("positive" if "positive" in scenario else "negative")
                    ),
                })
            scenario_summary[scenario] = {
                "eligible_series": len(results) // len(grid) if grid else 0,
                "skipped_series": skipped_by_scenario[scenario],
                "skip_reason": (
                    "insufficient_pre_onset_ar1_support"
                    if skipped_by_scenario[scenario] else None
                ),
                "candidates": candidate_rows,
            }
        summary[detector] = scenario_summary
    return summary



def monte_carlo_ar1_scale_validation(
    *,
    repetitions: int = 100,
    sample_lengths: tuple[int, ...] = (12, 16, 24, 40, 64, 100, 200, 500, 1000, 2000),
    rho_values: tuple[float, ...] = (0.30, 0.60, 0.85),
    drift_profiles: tuple[str, ...] = ("linear", "quadratic"),
    target_sigma: float = 2.0,
) -> dict[str, Any]:
    """Measure AR1 scale-estimator support, bias and coverage on controlled series."""
    seed = 20261115
    rng = random.Random(seed)
    min_support = 1500
    results: dict[str, Any] = {}
    for drift_profile in drift_profiles:
        for length in sample_lengths:
            for true_rho in rho_values:
                rho_estimates: list[float] = []
                scale_estimates: list[float] = []
                method_counts: Counter[str] = Counter()
                for _ in range(repetitions):
                    innovation_sigma = target_sigma * (1.0 - true_rho * true_rho) ** 0.5
                    state = rng.gauss(0.0, target_sigma)
                    series = []
                    for index in range(length):
                        state = true_rho * state + rng.gauss(0.0, innovation_sigma)
                        linear_drift = 20.0 + 0.15 * index
                        if drift_profile == "quadratic":
                            deterministic_level = linear_drift + 0.0003 * index * index
                        else:
                            deterministic_level = linear_drift
                        series.append({
                            "entity_id": "ar1-sim",
                            "metric_id": "metric",
                            "event_time": str(2000 + index),
                            "value": deterministic_level + state,
                            "observation_status": "observed",
                        })
                    estimate = first_difference_mad_scale(
                        series,
                        time_unit="years",
                        estimate_rho=True,
                        min_adjacent_pairs_for_rho=min_support,
                    )
                    method_counts[estimate["method"]] += 1
                    if estimate.get("rho") is not None:
                        rho_estimates.append(float(estimate["rho"]))
                    if estimate.get("value") is not None:
                        scale_estimates.append(float(estimate["value"]))
                rho_errors = [abs(value - true_rho) for value in rho_estimates]
                scale_relative_errors = [
                    abs(value / target_sigma - 1.0) for value in scale_estimates
                ]
                key = f"{drift_profile}_n{length}_rho{true_rho:.2f}"
                results[key] = {
                    "drift_profile": drift_profile,
                    "series_length": length,
                    "true_rho": true_rho,
                    "target_level_sigma": target_sigma,
                    "repetitions": repetitions,
                    "rho_estimates_available": len(rho_estimates),
                    "rho_estimate_coverage": len(rho_estimates) / repetitions,
                    "median_estimated_rho": median(rho_estimates) if rho_estimates else None,
                    "median_absolute_rho_error": median(rho_errors) if rho_errors else None,
                    "p90_absolute_rho_error": (
                        sorted(rho_errors)[int(0.9 * (len(rho_errors) - 1))]
                        if rho_errors else None
                    ),
                    "scale_estimates_available": len(scale_estimates),
                    "median_estimated_level_sigma": median(scale_estimates) if scale_estimates else None,
                    "median_absolute_relative_scale_error": (
                        median(scale_relative_errors) if scale_relative_errors else None
                    ),
                    "scale_method_counts": dict(method_counts),
                    "interpretation": (
                        "Monte Carlo estimator stability only; no production threshold or source anomaly labels"
                    ),
                }
    return {
        "seed": seed,
        "repetitions_per_cell": repetitions,
        "sample_lengths": list(sample_lengths),
        "rho_values": list(rho_values),
        "drift_profiles": list(drift_profiles),
        "target_level_sigma": target_sigma,
        "min_adjacent_difference_pairs_for_rho": min_support,
        "rho_estimator": "rho = 1 + 2 * lag1_acf(first_differences)",
        "linear_drift_handling": "first-difference autocorrelation is centered; no level-series trend fit",
        "quadratic_drift_control": "included as a negative-control stress condition",
        "ar1_mode_fails_closed_without_supported_lagged_differences": True,
        "results": results,
    }


def run_source(
    name: str,
    entity_series: dict[str, list[dict[str, Any]]],
    *,
    time_unit: str,
    scale_rho: float | None = None,
    evaluation_start: str | None = None,
) -> dict[str, Any]:
    source_result: dict[str, Any] = {
        "source": name,
        "time_unit": time_unit,
        "entity_count": len(entity_series),
        "baseline_methods": {},
    }
    baseline_configs = list(BASELINE_CONFIGS)
    if scale_rho is not None:
        baseline_configs.append({
            "label": "rolling_theil_sen_frozen_panel_rho",
            "baseline_method": "rolling_theil_sen",
            "estimate_rho": False,
            "scale_window": 12,
            "min_adjacent_pairs_for_rho": 14,
            "scale_rho": scale_rho,
        })
    for baseline_config in baseline_configs:
        baseline_method = baseline_config["baseline_method"]
        estimate_rho = baseline_config["estimate_rho"]
        scale_window = baseline_config["scale_window"]
        min_adjacent_pairs_for_rho = baseline_config["min_adjacent_pairs_for_rho"]
        config_rho = baseline_config.get("scale_rho")
        baseline_label = baseline_config["label"]
        historical_rows: list[dict[str, Any]] = []
        injections: list[dict[str, Any]] = []
        series_count = ready_count = 0
        per_entity_signal: dict[str, Any] = {}
        for entity_id, series in entity_series.items():
            observed = [
                row for row in series
                if row.get("observation_status") == "observed" and row.get("value") is not None
            ]
            if len(observed) < 12:
                continue
            residuals = build_univariate_residuals(
                observed,
                baseline_window=12,
                min_history=8,
                time_unit=time_unit,
                baseline_method=baseline_method,
                estimate_rho=estimate_rho,
                scale_window=scale_window,
                min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
                scale_rho=config_rho,
            )
            evaluation_rows = [
                row for row in residuals
                if evaluation_start is None
                or _time_position(row["event_time"], time_unit)
                >= _time_position(evaluation_start, time_unit)
            ]
            series_count += 1
            ready_count += ready_period_count(evaluation_rows)
            historical_rows.extend(evaluation_rows)
            per_entity_signal[entity_id] = {
                "observation_count": len(observed),
                "residual_count": len(evaluation_rows),
                "ready_periods": ready_period_count(evaluation_rows),
                "gap_unresolved": sum(1 for row in evaluation_rows if row["status"] == "gap_unresolved"),
                "scale_unavailable": sum(1 for row in evaluation_rows if row["status"] == "scale_unavailable"),
                "rho_estimated_rows": sum(1 for row in evaluation_rows if row.get("rho") is not None),
                "rho_values": [float(row["rho"]) for row in evaluation_rows if row.get("rho") is not None],
                "scale_method_counts": dict(Counter(row.get("scale_method") for row in evaluation_rows)),
            }
            injection = injection_response_for_series(
                observed,
                baseline_method=baseline_method,
                time_unit=time_unit,
                estimate_rho=estimate_rho,
                min_adjacent_pairs_for_rho=min_adjacent_pairs_for_rho,
                scale_rho=config_rho,
            )
            if injection:
                injections.append(injection)

        source_result["baseline_methods"][baseline_label] = {
            "baseline_method": baseline_method,
            "estimate_rho": estimate_rho,
            "scale_rho": config_rho,
            "scale_window": scale_window,
            "evaluation_start": evaluation_start,
            "min_adjacent_pairs_for_rho": min_adjacent_pairs_for_rho,
            "series_tested": series_count,
            "ready_periods": ready_count,
            "historical_signal_profile": historical_detector_profile(historical_rows),
            "injection_response": summarize_injection_responses(injections),
            "per_entity_coverage": per_entity_signal,
            "maximum_acceptable_detection_delay_time_units": MAX_ACCEPTABLE_DELAY_TIME_UNITS,
            "delay_time_unit": time_unit,
            "labeling": (
                "Observed source signals are unlabelled. Injection recall is measured "
                "against controlled persistent shifts added to copies of the real series."
            ),
        }
    return source_result


def main() -> None:
    report = {
        "experiment": "domain_neutral_real_series_threshold_sweep_v1",
        "source_data": {
            "world_bank_indicator": "FS.AST.PRVT.GD.ZS",
            "usgs_query": "magnitude >= 6.5, monthly count series",
        },
        "threshold_grid": {
            "cusum": list(CUSUM_GRID),
            "sign_run": list(P1_GRID),
            "max_acceptable_detection_delay_time_units": MAX_ACCEPTABLE_DELAY_TIME_UNITS,
        },
        "scale_estimators": [
            {
                "label": item["label"],
                "baseline_method": item["baseline_method"],
                "estimate_rho": item["estimate_rho"],
                "scale_window": item["scale_window"],
                "min_adjacent_pairs_for_rho": item["min_adjacent_pairs_for_rho"],
            }
            for item in BASELINE_CONFIGS
        ],
        "scale_estimator_validation": monte_carlo_ar1_scale_validation(),
        "sources": {
            "world_bank": run_source(
                "World Bank domestic credit to private sector (% GDP)",
                read_world_bank(),
                time_unit="years",
            ),
            "usgs": run_source(
                "USGS global M6.5+ monthly event counts",
                read_usgs_monthly(),
                time_unit="months",
            ),
        },
        "decision_rule": (
            "No threshold is auto-promoted to production. Compare observed historical "
            "signal density against persistent +/-3sigma and +/-6sigma injection recall "
            "and detection delay, separately for each source and baseline strategy."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {}
    for source, source_data in report["sources"].items():
        compact[source] = {}
        for baseline, result in source_data["baseline_methods"].items():
            compact[source][baseline] = {
                "series_tested": result["series_tested"],
                "ready_periods": result["ready_periods"],
                "cusum_signal_rates": result["historical_signal_profile"]["cusum_p1_disabled"],
                "sign_run_signal_rates": result["historical_signal_profile"]["sign_run_cusum_disabled"],
                "injection_scenarios": {
                    key: {
                        "eligible_series": value["eligible_series"],
                        "skipped_series": value["skipped_series"],
                        "skip_reason": value["skip_reason"],
                    }
                    for key, value in result["injection_response"]["cusum"].items()
                },
            }
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "summary": compact,
        "promotion": "not_automatic",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
