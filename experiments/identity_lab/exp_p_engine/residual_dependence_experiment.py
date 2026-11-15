"""Panel residual-dependence and prewhitening experiment.

The dependence parameter is estimated from pre-evaluation, prequential residual
streams only, frozen for the evaluation interval, and never inferred from the
injected evaluation data. Results remain experimental; prewhitening can remove
persistent-break signal and must pass matched controls before consideration.
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.identity_lab.exp_p_engine.calibration_sweep import read_world_bank
from experiments.identity_lab.exp_p_engine.domain_neutral import (
    build_univariate_residuals,
    detect_sign_runs,
    detect_two_sided_cusum,
    first_evidence_at_or_after,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_residual_dependence.json"
)

TRAINING_END = "2014"
EVALUATION_START = "2015"
BASELINE_WINDOW = 8
MIN_HISTORY = 8
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20261115
MIN_SERIES_FOR_RHO = 30
MIN_LAG_PAIRS_PER_SERIES = 4
MAX_RHO_CI_WIDTH = 0.50
INJECTION_SIGMAS = (3.0, 6.0)
INJECTION_DIRECTIONS = (-1, 1)

RAW_CUSUM_GRID = (
    {"k": 0.5, "h": 8.5},
    {"k": 1.0, "h": 16.0},
)
INNOVATION_CUSUM_GRID = (
    {"k": 0.25, "h": 2.0},
    {"k": 0.25, "h": 3.0},
    {"k": 0.25, "h": 4.0},
    {"k": 0.50, "h": 4.0},
    {"k": 0.50, "h": 6.0},
)
RAW_P1_GRID = (
    {"threshold": 3.0, "run_length": 3},
    {"threshold": 4.0, "run_length": 4},
)
INNOVATION_P1_GRID = (
    {"threshold": 3.0, "run_length": 1},
    {"threshold": 3.5, "run_length": 1},
    {"threshold": 4.0, "run_length": 1},
    {"threshold": 3.0, "run_length": 3},
)


def year_number(value: Any) -> int:
    raw = str(value).strip()
    if len(raw) < 4 or not raw[:4].isdigit():
        raise ValueError("annual_year_label_required")
    return int(raw[:4])


def median_or_none(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    mean_left = statistics.mean(left)
    mean_right = statistics.mean(right)
    dx = [value - mean_left for value in left]
    dy = [value - mean_right for value in right]
    denom = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denom <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def _series_map(
    residual_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in residual_rows:
        grouped[(str(row["entity_id"]), str(row["metric_id"]))].append(dict(row))
    for rows in grouped.values():
        rows.sort(key=lambda item: year_number(item["event_time"]))
    return dict(grouped)


def _entity_lag1(
    rows: Sequence[Mapping[str, Any]],
    *,
    training_end: str,
    min_lag_pairs: int,
) -> tuple[float | None, float | None, int]:
    cutoff = year_number(training_end)
    ready = [
        row for row in rows
        if row.get("status") == "ready"
        and row.get("z_score") is not None
        and year_number(row["event_time"]) <= cutoff
    ]
    ready.sort(key=lambda item: year_number(item["event_time"]))
    if not ready:
        return None, None, 0
    center = statistics.median(float(row["z_score"]) for row in ready)
    pairs: list[tuple[float, float]] = []
    for previous, current in zip(ready, ready[1:]):
        if year_number(current["event_time"]) != year_number(previous["event_time"]) + 1:
            continue
        pairs.append((
            float(previous["z_score"]) - center,
            float(current["z_score"]) - center,
        ))
    if len(pairs) < min_lag_pairs:
        return None, center, len(pairs)
    rho = pearson(
        [pair[0] for pair in pairs],
        [pair[1] for pair in pairs],
    )
    return rho, center, len(pairs)


def estimate_panel_residual_rho(
    residual_rows: Sequence[Mapping[str, Any]],
    *,
    training_end: str = TRAINING_END,
    min_series: int = MIN_SERIES_FOR_RHO,
    min_lag_pairs_per_series: int = MIN_LAG_PAIRS_PER_SERIES,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Estimate a common residual-stream lag-1 correlation from training only.

    The point estimate is the median of entity-specific correlations, preventing
    long or high-variance series from dominating. The CI bootstraps entities.
    """
    grouped = _series_map(residual_rows)
    estimates: dict[str, float] = {}
    centers: dict[str, float] = {}
    pair_counts: dict[str, int] = {}
    dropped: dict[str, int] = defaultdict(int)

    for (entity_id, metric_id), rows in grouped.items():
        key = entity_id + "::" + metric_id
        rho, center, pair_count = _entity_lag1(
            rows,
            training_end=training_end,
            min_lag_pairs=min_lag_pairs_per_series,
        )
        if rho is None or center is None or not math.isfinite(rho):
            dropped["insufficient_or_unidentifiable_entity_lag1"] += 1
            continue
        estimates[key] = max(-0.99, min(0.99, float(rho)))
        centers[key] = float(center)
        pair_counts[key] = pair_count

    keys = sorted(estimates)
    if len(keys) < min_series:
        return {
            "status": "insufficient_panel_residual_support",
            "rho": None,
            "training_end": training_end,
            "series_count": len(keys),
            "lag_pair_count": sum(pair_counts.values()),
            "min_series": min_series,
            "min_lag_pairs_per_series": min_lag_pairs_per_series,
            "dropped_series": dict(dropped),
        }

    point = statistics.median(estimates[key] for key in keys)
    rng = random.Random(seed)
    boot: list[float] = []
    for _ in range(bootstrap_replicates):
        sample = [estimates[keys[rng.randrange(len(keys))]] for _ in keys]
        boot.append(statistics.median(sample))
    boot.sort()

    def pct(q: float) -> float:
        index = min(len(boot) - 1, max(0, round(q * (len(boot) - 1))))
        return boot[index]

    lower, upper = pct(0.025), pct(0.975)
    width = upper - lower
    status = "ok"
    reason = None
    if not -0.95 <= point <= 0.95:
        status, reason = "rho_outside_supported_range", "rho_outside_-0.95_to_0.95"
    elif width > MAX_RHO_CI_WIDTH:
        status, reason = "unstable_panel_residual_rho", "bootstrap_ci_too_wide"

    return {
        "status": status,
        "rho": point if status == "ok" else None,
        "raw_rho": point,
        "rho_ci95": [lower, upper],
        "ci_width": width,
        "training_end": training_end,
        "series_count": len(keys),
        "lag_pair_count": sum(pair_counts.values()),
        "entity_lag1_summary": {
            "median": point,
            "p10": sorted(estimates.values())[max(0, int(0.10 * (len(keys) - 1)))],
            "p90": sorted(estimates.values())[max(0, int(0.90 * (len(keys) - 1)))],
        },
        "entity_centers": centers,
        "entity_pair_counts": pair_counts,
        "bootstrap_replicates": bootstrap_replicates,
        "seed": seed,
        "min_series": min_series,
        "min_lag_pairs_per_series": min_lag_pairs_per_series,
        "dropped_series": dict(dropped),
        "reason": reason,
        "estimator": "median_entity_lag1_correlation_of_prequential_zscores",
        "scope": "frozen from pre-evaluation residuals; not an original-observation AR(1) estimate",
    }


def prewhiten_evaluation_rows(
    residual_rows: Sequence[Mapping[str, Any]],
    calibration: Mapping[str, Any],
    *,
    evaluation_start: str = EVALUATION_START,
) -> list[dict[str, Any]]:
    """Apply a frozen panel AR(1) innovation filter only to evaluation rows.

    A gap resets state. The first ready observation after a gap is not scored.
    The first evaluation innovation may use the last contiguous training residual.
    """
    if calibration.get("status") != "ok" or calibration.get("rho") is None:
        raise ValueError("panel_residual_rho_not_approved")
    rho = float(calibration["rho"])
    if not -0.95 <= rho <= 0.95:
        raise ValueError("panel_residual_rho_outside_range")
    centers = calibration.get("entity_centers", {})
    start_year = year_number(evaluation_start)
    output: list[dict[str, Any]] = []

    for (entity_id, metric_id), rows in _series_map(residual_rows).items():
        key = entity_id + "::" + metric_id
        if key not in centers:
            continue
        center = float(centers[key])
        previous_year: int | None = None
        previous_z: float | None = None
        for row in rows:
            current_year = year_number(row["event_time"])
            is_ready = row.get("status") == "ready" and row.get("z_score") is not None
            if not is_ready:
                if current_year >= start_year:
                    item = dict(row)
                    item["raw_z_score"] = row.get("z_score")
                    item["innovation_z_score"] = None
                    item["status"] = "innovation_gap_reset"
                    item["baseline_id"] = str(row["baseline_id"]) + ":panel-residual-rho"
                    output.append(item)
                previous_year = None
                previous_z = None
                continue

            current_z = float(row["z_score"])
            if current_year < start_year:
                previous_year = current_year
                previous_z = current_z
                continue

            item = dict(row)
            item["raw_z_score"] = current_z
            item["residual_dependence_rho"] = rho
            item["innovation_method"] = "frozen_panel_ar1_residual_prewhitening"
            item["baseline_id"] = str(row["baseline_id"]) + ":panel-residual-rho"
            if previous_year is None or previous_year != current_year - 1 or previous_z is None:
                item["innovation_z_score"] = None
                item["z_score"] = None
                item["status"] = "innovation_warmup_or_gap"
            else:
                innovation = (
                    (current_z - center) - rho * (previous_z - center)
                ) / math.sqrt(1.0 - rho * rho)
                item["innovation_z_score"] = innovation
                item["z_score"] = innovation
                item["status"] = "ready"
                item["residual"] = innovation * float(row["scale"])
            output.append(item)
            previous_year = current_year
            previous_z = current_z

    output.sort(key=lambda row: (
        year_number(row["event_time"]), str(row["entity_id"]), str(row["metric_id"])
    ))
    return output


def lag1_summary(
    residual_rows: Sequence[Mapping[str, Any]],
    *,
    value_field: str = "z_score",
    min_pairs: int = 4,
) -> dict[str, Any]:
    per_entity: list[float] = []
    pair_count = 0
    for _, rows in _series_map(residual_rows).items():
        ready = [
            row for row in rows
            if row.get("status") == "ready"
            and row.get(value_field) is not None
        ]
        pairs_left: list[float] = []
        pairs_right: list[float] = []
        for previous, current in zip(ready, ready[1:]):
            if year_number(current["event_time"]) != year_number(previous["event_time"]) + 1:
                continue
            pairs_left.append(float(previous[value_field]))
            pairs_right.append(float(current[value_field]))
        if len(pairs_left) < min_pairs:
            continue
        corr = pearson(pairs_left, pairs_right)
        if corr is not None:
            per_entity.append(corr)
            pair_count += len(pairs_left)
    return {
        "series_with_metric": len(per_entity),
        "lag_pair_count": pair_count,
        "median_entity_lag1": median_or_none(per_entity),
        "p10_entity_lag1": (
            sorted(per_entity)[max(0, int(0.10 * (len(per_entity) - 1)))]
            if per_entity else None
        ),
        "p90_entity_lag1": (
            sorted(per_entity)[max(0, int(0.90 * (len(per_entity) - 1)))]
            if per_entity else None
        ),
    }


def summarize_detector_hits(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    entities = {str(row["entity_id"]) for row in rows if row.get("status") == "ready"}
    output: dict[str, Any] = {
        "ready_evaluation_periods": ready_count,
        "entity_count_with_ready_periods": len(entities),
        "cusum": [],
        "sign_run": [],
    }
    for params in RAW_CUSUM_GRID:
        hits = detect_two_sided_cusum(rows, k=params["k"], h=params["h"])
        output["cusum"].append({
            **params,
            "raw_hits": len(hits),
            "entities_with_hit": len({hit["entity_id"] for hit in hits}),
            "signals_per_1000_ready_periods": (
                1000.0 * len(hits) / ready_count if ready_count else None
            ),
        })
    for params in RAW_P1_GRID:
        hits = detect_sign_runs(
            rows, threshold=params["threshold"], run_length=params["run_length"]
        )
        output["sign_run"].append({
            **params,
            "raw_hits": len(hits),
            "entities_with_hit": len({hit["entity_id"] for hit in hits}),
            "signals_per_1000_ready_periods": (
                1000.0 * len(hits) / ready_count if ready_count else None
            ),
        })
    return output


def _time_delta(first: str, second: str) -> float:
    return float(year_number(second) - year_number(first))


def _first_hit_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    onset: str,
    detector: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    if detector == "cusum":
        hits = detect_two_sided_cusum(rows, k=float(parameters["k"]), h=float(parameters["h"]))
    elif detector == "sign_run":
        hits = detect_sign_runs(
            rows,
            threshold=float(parameters["threshold"]),
            run_length=int(parameters["run_length"]),
        )
    else:
        raise ValueError("detector_type_unsupported")
    first = first_evidence_at_or_after(hits, onset)
    return {
        "detected": first is not None,
        "direction": first["direction"] if first else None,
        "first_evidence_time": first["event_time"] if first else None,
        "delay_years": _time_delta(onset, first["event_time"]) if first else None,
    }


def _response_grid_for_stream(
    injected: Sequence[Mapping[str, Any]],
    control: Sequence[Mapping[str, Any]],
    *,
    onset: str,
    cusum_grid: Sequence[Mapping[str, Any]],
    p1_grid: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output: dict[str, Any] = {"cusum": [], "sign_run": []}
    for params in cusum_grid:
        inj = _first_hit_summary(injected, onset=onset, detector="cusum", parameters=params)
        ctl = _first_hit_summary(control, onset=onset, detector="cusum", parameters=params)
        output["cusum"].append({
            **dict(params),
            "injected_detected": inj["detected"],
            "control_detected": ctl["detected"],
            "incremental_detection": inj["detected"] and not ctl["detected"],
            "control_only_detection": ctl["detected"] and not inj["detected"],
            "injected_direction": inj["direction"],
            "control_direction": ctl["direction"],
            "injected_delay_years": inj["delay_years"],
        })
    for params in p1_grid:
        inj = _first_hit_summary(injected, onset=onset, detector="sign_run", parameters=params)
        ctl = _first_hit_summary(control, onset=onset, detector="sign_run", parameters=params)
        output["sign_run"].append({
            **dict(params),
            "injected_detected": inj["detected"],
            "control_detected": ctl["detected"],
            "incremental_detection": inj["detected"] and not ctl["detected"],
            "control_only_detection": ctl["detected"] and not inj["detected"],
            "injected_direction": inj["direction"],
            "control_direction": ctl["direction"],
            "injected_delay_years": inj["delay_years"],
        })
    return output


def run_injection_experiment(
    entity_series: Mapping[str, Sequence[Mapping[str, Any]]],
    original_residuals: Mapping[str, Sequence[Mapping[str, Any]]],
    calibration: Mapping[str, Any],
) -> dict[str, Any]:
    """Matched injection/control experiments, sharing one frozen training rho."""
    if calibration.get("status") != "ok":
        return {"status": "skipped_panel_rho_not_approved"}
    results: dict[str, Any] = defaultdict(list)
    eligible = 0
    skipped = defaultdict(int)
    for entity_id, source in entity_series.items():
        series = [dict(row) for row in source]
        base_residuals = list(original_residuals[entity_id])
        evaluation_times = sorted({
            year_number(row["event_time"])
            for row in base_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
            and row.get("status") == "ready"
        })
        if len(evaluation_times) < 6:
            skipped["insufficient_evaluation_history"] += 1
            continue
        onset_year = evaluation_times[len(evaluation_times) // 2]
        onset = str(onset_year)
        prior_scales = [
            float(row["scale"])
            for row in base_residuals
            if row.get("status") == "ready"
            and year_number(row["event_time"]) < onset_year
            and row.get("scale") is not None
            and float(row["scale"]) > 0
        ]
        sigma = median_or_none(prior_scales)
        if sigma is None or sigma <= 0:
            skipped["scale_unavailable"] += 1
            continue
        entity_key = entity_id + "::" + str(series[0]["metric_id"])
        if entity_key not in calibration.get("entity_centers", {}):
            skipped["training_dependence_unavailable"] += 1
            continue
        eligible += 1
        for magnitude in INJECTION_SIGMAS:
            for direction in INJECTION_DIRECTIONS:
                shift = direction * magnitude * sigma
                injected_series = []
                for row in series:
                    item = dict(row)
                    if year_number(item["event_time"]) >= onset_year:
                        item["value"] = float(item["value"]) + shift
                    injected_series.append(item)

                injected_residuals = build_univariate_residuals(
                    injected_series,
                    baseline_window=BASELINE_WINDOW,
                    min_history=MIN_HISTORY,
                    time_unit="years",
                    baseline_method="rolling_theil_sen",
                    scale_estimator="first_difference_mad",
                    estimate_rho=False,
                )
                injected_whitened = prewhiten_evaluation_rows(injected_residuals, calibration)
                control_whitened = prewhiten_evaluation_rows(base_residuals, calibration)
                raw_injected = [
                    row for row in injected_residuals
                    if year_number(row["event_time"]) >= year_number(EVALUATION_START)
                ]
                raw_control = [
                    row for row in base_residuals
                    if year_number(row["event_time"]) >= year_number(EVALUATION_START)
                ]
                white_injected = injected_whitened
                white_control = control_whitened

                raw_response = _response_grid_for_stream(
                    raw_injected,
                    raw_control,
                    onset=onset,
                    cusum_grid=RAW_CUSUM_GRID,
                    p1_grid=RAW_P1_GRID,
                )
                white_response = _response_grid_for_stream(
                    white_injected,
                    white_control,
                    onset=onset,
                    cusum_grid=INNOVATION_CUSUM_GRID,
                    p1_grid=INNOVATION_P1_GRID,
                )
                for stream_name, response in (
                    ("raw_residuals", raw_response),
                    ("prewhitened_innovations", white_response),
                ):
                    results[stream_name].append({
                        "entity_id": entity_id,
                        "scenario": (
                            ("positive_" if direction > 0 else "negative_")
                            + str(magnitude) + "sigma"
                        ),
                        "onset_time": onset,
                        "injection_scale": sigma,
                        "cusum": response["cusum"],
                        "sign_run": response["sign_run"],
                    })
    return {
        "status": "ok",
        "eligible_entities": eligible,
        "skipped_entities": dict(skipped),
        "responses": dict(results),
    }


def summarize_injection_response(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_scenario: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[str(row["scenario"])].append(row)
    output: dict[str, Any] = {}
    for scenario, items in by_scenario.items():
        summary: dict[str, Any] = {"series_tested": len(items), "cusum": [], "sign_run": []}
        for detector in ("cusum", "sign_run"):
            parameter_keys = (
                [dict(params) for params in (RAW_CUSUM_GRID if detector == "cusum" else RAW_P1_GRID)]
                if "raw" in str(items[0].get("stream_name", ""))
                else [dict(params) for params in (INNOVATION_CUSUM_GRID if detector == "cusum" else INNOVATION_P1_GRID)]
            )
            for params in parameter_keys:
                candidates = []
                for row in items:
                    for candidate in row[detector]:
                        if all(candidate.get(key) == val for key, val in params.items()):
                            candidates.append(candidate)
                injected_detections = sum(1 for item in candidates if item["injected_detected"])
                control_detections = sum(1 for item in candidates if item["control_detected"])
                incremental = sum(1 for item in candidates if item["incremental_detection"])
                control_only = sum(1 for item in candidates if item["control_only_detection"])
                correct_direction = sum(
                    1 for item in candidates
                    if item["injected_detected"]
                    and item["injected_direction"] ==
                    ("positive" if scenario.startswith("positive") else "negative")
                )
                delays = [
                    item["injected_delay_years"]
                    for item in candidates
                    if item["injected_delay_years"] is not None
                ]
                summary[detector].append({
                    **params,
                    "tested_series": len(candidates),
                    "injected_detection_rate": (
                        injected_detections / len(candidates) if candidates else None
                    ),
                    "matched_control_detection_rate": (
                        control_detections / len(candidates) if candidates else None
                    ),
                    "incremental_detection_rate": (
                        incremental / len(candidates) if candidates else None
                    ),
                    "control_only_detection_rate": (
                        control_only / len(candidates) if candidates else None
                    ),
                    "net_detection_rate_delta": (
                        (injected_detections - control_detections) / len(candidates)
                        if candidates else None
                    ),
                    "correct_direction_count": correct_direction,
                    "median_injected_detection_delay_years": (
                        statistics.median(delays) if delays else None
                    ),
                })
        output[scenario] = summary
    return output


def run_source() -> dict[str, Any]:
    entity_series = read_world_bank()
    residual_by_entity: dict[str, list[dict[str, Any]]] = {}
    for entity_id, observations in entity_series.items():
        if len(observations) < BASELINE_WINDOW + 8:
            continue
        residual_by_entity[entity_id] = build_univariate_residuals(
            observations,
            baseline_window=BASELINE_WINDOW,
            min_history=MIN_HISTORY,
            time_unit="years",
            baseline_method="rolling_theil_sen",
            scale_estimator="first_difference_mad",
            estimate_rho=False,
        )

    all_residuals = [row for rows in residual_by_entity.values() for row in rows]
    calibration = estimate_panel_residual_rho(
        all_residuals,
        training_end=TRAINING_END,
    )
    if calibration["status"] == "ok":
        evaluation_rows = [
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ]
        whitened = prewhiten_evaluation_rows(all_residuals, calibration)
        raw_diag = lag1_summary(evaluation_rows)
        whitened_diag = lag1_summary(whitened)
        raw_signals = summarize_detector_hits(evaluation_rows)
        whitened_signals = summarize_detector_hits(whitened)
        injections = run_injection_experiment(
            entity_series,
            residual_by_entity,
            calibration,
        )
        summarized_injections: dict[str, Any] = {}
        for stream_name, rows in injections.get("responses", {}).items():
            for row in rows:
                row["stream_name"] = stream_name
            summarized_injections[stream_name] = summarize_injection_response(rows)
        injection_status = {
            "status": injections["status"],
            "eligible_entities": injections["eligible_entities"],
            "skipped_entities": injections["skipped_entities"],
            "summaries": summarized_injections,
        }
    else:
        raw_diag = lag1_summary([
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ])
        whitened_diag = None
        raw_signals = summarize_detector_hits([
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ])
        whitened_signals = None
        injection_status = {"status": "skipped_panel_rho_not_approved"}

    return {
        "source": "World Bank FS.AST.PRVT.GD_ZS",
        "training_end": TRAINING_END,
        "evaluation_start": EVALUATION_START,
        "baseline": {
            "method": "rolling_theil_sen",
            "window": BASELINE_WINDOW,
            "scale": "first_difference_mad_iid_unit_gap_only",
        },
        "dependence_calibration": calibration,
        "evaluation_residual_dependence": {
            "raw": raw_diag,
            "prewhitened": whitened_diag,
        },
        "historical_signal_profile": {
            "raw_residuals": raw_signals,
            "prewhitened_innovations": whitened_signals,
        },
        "controlled_persistent_shift_injections": injection_status,
        "interpretation": (
            "Prewhitening is a diagnostic candidate only. The panel rho is estimated "
            "and frozen before evaluation. Matched injection/control response and "
            "held-out residual autocorrelation must both be acceptable before any use. "
            "No source-history hits are labelled true or false without ground truth."
        ),
    }


def main() -> None:
    report = {
        "experiment": "domain_neutral_residual_dependence_whitening_v1",
        "seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "min_series_for_rho": MIN_SERIES_FOR_RHO,
        "min_lag_pairs_per_series": MIN_LAG_PAIRS_PER_SERIES,
        "max_rho_ci_width": MAX_RHO_CI_WIDTH,
        "max_acceptance": "diagnostic only; no automatic promotion",
        "result": run_source(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    result = report["result"]
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "dependence_calibration": {
            key: value for key, value in result["dependence_calibration"].items()
            if key != "entity_centers" and key != "entity_pair_counts"
        },
        "raw_eval_autocorrelation": result["evaluation_residual_dependence"]["raw"],
        "whitened_eval_autocorrelation": result["evaluation_residual_dependence"]["prewhitened"],
        "raw_signal_profile": result["historical_signal_profile"]["raw_residuals"],
        "whitened_signal_profile": result["historical_signal_profile"]["prewhitened_innovations"],
        "injections": result["controlled_persistent_shift_injections"]["summaries"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
