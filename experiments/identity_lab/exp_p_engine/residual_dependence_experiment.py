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
    validate_residual_contract,
)
from experiments.identity_lab.exp_p_engine.block_bootstrap_calibration import (
    BOOTSTRAP_REPLICATES as NULL_BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED as NULL_BOOTSTRAP_SEED,
    BLOCK_LENGTHS as NULL_BLOCK_LENGTHS,
    CUSUM_GRID as NULL_CUSUM_GRID,
    MAX_ACCEPTABLE_SERIES_ALERT_RATE,
    P1_GRID as NULL_P1_GRID,
    contiguous_ready_segments,
    cusum_alarm_count,
    moving_block_resample,
    percentile,
    sign_run_alarm_count,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_residual_dependence.json"
)

TRAINING_END = "2013"
EVALUATION_START = "2014"
NULL_CALIBRATION_END = "2020"
INJECTION_ONSET = "2021"
MIN_POST_INJECTION_PERIODS = 4
DETECTION_HORIZON_YEARS = 3
MIN_NULL_SEGMENT_LENGTH = 5
BASELINE_WINDOW = 8
MIN_HISTORY = 8
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20261115
MIN_SERIES_FOR_RHO = 30
MIN_LAG_PAIRS_PER_SERIES = 4
MAX_RHO_CI_WIDTH = 0.50
INJECTION_SIGMAS = (3.0, 6.0)
INJECTION_DIRECTIONS = (-1, 1)

# A broader identical grid is required because the initial empirical-null
# screen rejected every candidate. Raw residuals and innovations remain paired.
COMMON_CUSUM_GRID = tuple(
    {"k": k, "h": h}
    for k in (0.50, 1.00, 1.50)
    for h in (16.0, 24.0, 32.0, 48.0, 64.0, 96.0, 128.0, 192.0, 256.0)
)
COMMON_P1_GRID = tuple(
    {"threshold": threshold, "run_length": run_length}
    for threshold, run_lengths in (
        (3.0, (4, 5, 6)),
        (4.0, (3, 4, 5, 6)),
        (5.0, (3, 4, 5, 6)),
        (6.0, (3, 4, 5, 6)),
        (8.0, (2, 3, 4, 5)),
        (10.0, (2, 3, 4, 5)),
        (12.0, (2, 3, 4)),
        (16.0, (2, 3)),
    )
    for run_length in run_lengths
)
RAW_CUSUM_GRID = tuple(dict(item) for item in COMMON_CUSUM_GRID)
INNOVATION_CUSUM_GRID = tuple(dict(item) for item in COMMON_CUSUM_GRID)
RAW_P1_GRID = tuple(dict(item) for item in COMMON_P1_GRID)
INNOVATION_P1_GRID = tuple(dict(item) for item in COMMON_P1_GRID)
# Lower p values compensate for truncation at short, disconnected segments.
# The realised mean block length is measured and reported, not assumed to be 1/p.
STATIONARY_BOOTSTRAP_P_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35)


def year_number(value: Any) -> int:
    raw = str(value).strip()
    if len(raw) < 4 or not raw[:4].isdigit():
        raise ValueError("annual_year_label_required")
    return int(raw[:4])


def fixed_injection_onset(evaluation_times: Sequence[int]) -> int | None:
    """Return the fixed post-null onset only when both sides have usable support."""
    years = sorted({int(year) for year in evaluation_times})
    pre = [year for year in years if year <= year_number(NULL_CALIBRATION_END)]
    post = [year for year in years if year >= year_number(INJECTION_ONSET)]
    if len(pre) < 2 or len(post) < MIN_POST_INJECTION_PERIODS:
        return None
    return year_number(INJECTION_ONSET)


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
    """Build a contract-valid standardized innovation stream for evaluation.

    The original residual observation is preserved in raw_* fields. The
    transformed stream has its own explicit semantics:
      observed_value = innovation, expected_value = 0, residual = innovation,
      scale = 1, z_score = innovation.
    This keeps the shared residual arithmetic invariant valid without
    pretending that an innovation is the original metric's raw residual.

    A gap resets state. The first ready observation after a gap is unscored.
    The first evaluation innovation may use the last contiguous training row.
    """
    if calibration.get("status") != "ok" or calibration.get("rho") is None:
        raise ValueError("panel_residual_rho_not_approved")
    rho = float(calibration["rho"])
    if not -0.95 <= rho <= 0.95:
        raise ValueError("panel_residual_rho_outside_range")
    centers = calibration.get("entity_centers", {})
    start_year = year_number(evaluation_start)
    output: list[dict[str, Any]] = []

    def innovation_row(
        source: Mapping[str, Any],
        *,
        status: str,
        innovation: float | None = None,
        center: float | None = None,
    ) -> dict[str, Any]:
        item = dict(source)
        item.update({
            "raw_observed_value": source.get("observed_value"),
            "raw_expected_value": source.get("expected_value"),
            "raw_residual": source.get("residual"),
            "raw_scale": source.get("scale"),
            "raw_z_score": source.get("z_score"),
            "raw_status": source.get("status"),
            "raw_baseline_id": source.get("baseline_id"),
            "raw_baseline_method": source.get("baseline_method"),
            "residual_dependence_rho": rho,
            "innovation_method": "frozen_panel_ar1_residual_prewhitening",
            "baseline_id": str(source["baseline_id"]) + ":panel-residual-rho",
            "baseline_method": "frozen_panel_ar1_residual_prewhitening",
            "unit": "standardized_innovation",
            "status": status,
        })
        if innovation is None:
            item.update({
                "observed_value": None,
                "expected_value": None,
                "residual": None,
                "scale": None,
                "z_score": None,
                "innovation_z_score": None,
            })
        else:
            if not math.isfinite(innovation):
                raise ValueError("prewhitened_innovation_not_finite")
            # Canonical contract for the transformed stream: innovation under
            # its null expectation of zero, in standard-deviation units.
            item.update({
                "observed_value": innovation,
                "expected_value": 0.0,
                "residual": innovation,
                "scale": 1.0,
                "z_score": innovation,
                "innovation_z_score": innovation,
                "innovation_center": center,
            })
        return item

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
                    status = (
                        "innovation_gap_reset"
                        if row.get("status") == "gap_unresolved"
                        else "innovation_warmup_or_gap"
                    )
                    output.append(innovation_row(row, status=status))
                previous_year = None
                previous_z = None
                continue

            current_z = float(row["z_score"])
            if current_year < start_year:
                previous_year = current_year
                previous_z = current_z
                continue

            if (
                previous_year is None
                or previous_year != current_year - 1
                or previous_z is None
            ):
                item = innovation_row(
                    row,
                    status="innovation_warmup_or_gap",
                    center=center,
                )
            else:
                innovation = (
                    (current_z - center) - rho * (previous_z - center)
                ) / math.sqrt(1.0 - rho * rho)
                item = innovation_row(
                    row,
                    status="ready",
                    innovation=innovation,
                    center=center,
                )
            output.append(item)
            previous_year = current_year
            previous_z = current_z

    output.sort(key=lambda row: (
        year_number(row["event_time"]), str(row["entity_id"]), str(row["metric_id"])
    ))
    validate_residual_contract(output)
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
    *,
    cusum_grid: Sequence[Mapping[str, Any]] = RAW_CUSUM_GRID,
    p1_grid: Sequence[Mapping[str, Any]] = RAW_P1_GRID,
) -> dict[str, Any]:
    """Summarize one residual stream using its own detector parameter grid."""
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    entities = {str(row["entity_id"]) for row in rows if row.get("status") == "ready"}
    output: dict[str, Any] = {
        "ready_evaluation_periods": ready_count,
        "entity_count_with_ready_periods": len(entities),
        "cusum": [],
        "sign_run": [],
    }
    for params in cusum_grid:
        hits = detect_two_sided_cusum(rows, k=float(params["k"]), h=float(params["h"]))
        output["cusum"].append({
            **dict(params),
            "raw_hits": len(hits),
            "entities_with_hit": len({hit["entity_id"] for hit in hits}),
            "signals_per_1000_ready_periods": (
                1000.0 * len(hits) / ready_count if ready_count else None
            ),
        })
    for params in p1_grid:
        hits = detect_sign_runs(
            rows,
            threshold=float(params["threshold"]),
            run_length=int(params["run_length"]),
        )
        output["sign_run"].append({
            **dict(params),
            "raw_hits": len(hits),
            "entities_with_hit": len({hit["entity_id"] for hit in hits}),
            "signals_per_1000_ready_periods": (
                1000.0 * len(hits) / ready_count if ready_count else None
            ),
        })
    return output


def stationary_bootstrap_sample(
    segments: Sequence[Sequence[float]],
    *,
    target_length: int,
    restart_probability: float,
    rng: random.Random,
) -> list[list[float]]:
    """Sample stationary-bootstrap blocks without crossing source gaps.

    Block starts are uniform over all valid observations, so segment selection
    is length-weighted. A block stops on a geometric restart or at its source
    segment end. No circular wrap is allowed at any source boundary.
    """
    if target_length < 1:
        raise ValueError("stationary_bootstrap_target_length_invalid")
    if (
        not math.isfinite(restart_probability)
        or not 0.0 < restart_probability <= 1.0
    ):
        raise ValueError("stationary_bootstrap_restart_probability_invalid")

    clean_segments: list[list[float]] = []
    for segment in segments:
        values = [float(value) for value in segment]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("stationary_bootstrap_non_finite_value")
        if values:
            clean_segments.append(values)
    if not clean_segments:
        raise ValueError("stationary_bootstrap_no_valid_observations")

    # Every valid time point is one equally likely start position.
    start_positions = [
        (segment_index, offset)
        for segment_index, segment in enumerate(clean_segments)
        for offset in range(len(segment))
    ]
    blocks: list[list[float]] = []
    sampled = 0
    while sampled < target_length:
        segment_index, offset = start_positions[
            rng.randrange(len(start_positions))
        ]
        segment = clean_segments[segment_index]
        block: list[float] = []
        while sampled < target_length:
            block.append(segment[offset])
            sampled += 1
            offset += 1
            if sampled >= target_length or offset >= len(segment):
                break
            if rng.random() < restart_probability:
                break
        blocks.append(block)
    return blocks


def calibrate_prewhitened_null(
    rows: Sequence[Mapping[str, Any]],
    *,
    replicates: int = NULL_BOOTSTRAP_REPLICATES,
    seed: int = NULL_BOOTSTRAP_SEED,
    restart_probabilities: Sequence[float] = STATIONARY_BOOTSTRAP_P_GRID,
    cusum_grid: Sequence[Mapping[str, Any]] = INNOVATION_CUSUM_GRID,
    p1_grid: Sequence[Mapping[str, Any]] = INNOVATION_P1_GRID,
    min_segment_length: int = 2,
    min_series: int = 30,
) -> dict[str, Any]:
    """Stationary-bootstrap empirical-null screen on a standardized stream.

    The caller supplies only held-out rows. Missing observations and gaps split
    contiguous segments. Block restarts select uniformly among valid points;
    source segment ends truncate blocks. The 5% screen is a candidate filter,
    not a production false-alarm guarantee.
    """
    if replicates < 1 or min_segment_length < 1 or min_series < 1:
        raise ValueError("stationary_bootstrap_parameters_invalid")
    if (
        not restart_probabilities
        or any(
            not math.isfinite(float(probability))
            or not 0.0 < float(probability) <= 1.0
            for probability in restart_probabilities
        )
    ):
        raise ValueError("stationary_bootstrap_restart_probabilities_invalid")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["entity_id"]),
            str(row["metric_id"]),
            str(row["baseline_id"]),
        )
        grouped[key].append(dict(row))

    panel: dict[str, list[list[float]]] = {}
    dropped_short_segments = 0
    for key, series_rows in grouped.items():
        segments = contiguous_ready_segments(series_rows)
        retained = [
            segment for segment in segments
            if len(segment) >= min_segment_length
        ]
        dropped_short_segments += len(segments) - len(retained)
        if retained:
            panel["::".join(key)] = retained

    series_count = len(panel)
    exposure_by_series = {
        key: sum(len(segment) for segment in segments)
        for key, segments in panel.items()
    }
    exposure = sum(exposure_by_series.values())
    if series_count < min_series or exposure == 0:
        return {
            "status": "insufficient_evaluation_support",
            "series_count": series_count,
            "ready_evaluation_exposure": exposure,
            "minimum_series": min_series,
            "minimum_segment_length": min_segment_length,
            "dropped_short_segments": dropped_short_segments,
        }

    output: dict[str, Any] = {
        "status": "ok",
        "method": "stationary_bootstrap_on_contiguous_evaluation_segments",
        "restart_probabilities": [float(p) for p in restart_probabilities],
        "expected_geometric_block_lengths": {
            str(float(p)): 1.0 / float(p)
            for p in restart_probabilities
        },
        "boundary_policy": (
            "A block ends at a geometric restart or at its source contiguous "
            "segment boundary; no circular wrap or cross-gap continuation."
        ),
        "start_sampling": (
            "Uniform over every valid point in each series; segment selection "
            "is proportional to segment length."
        ),
        "series_count": series_count,
        "ready_evaluation_exposure": exposure,
        "segment_count": sum(len(segments) for segments in panel.values()),
        "minimum_segment_length": min_segment_length,
        "dropped_short_segments": dropped_short_segments,
        "bootstrap_replicates": replicates,
        "seed": seed,
        "series_alarm_screen": {
            "maximum_upper95_series_alarm_rate": MAX_ACCEPTABLE_SERIES_ALERT_RATE,
            "criterion": (
                "upper95_series_alarm_rate <= 0.05 for every tested "
                "restart probability"
            ),
            "purpose": "candidate screen only; not a production false-alarm guarantee",
        },
        "detectors": {"cusum": [], "sign_run": []},
        "sampling_diagnostics": {},
    }

    detector_settings = {
        "cusum": [
            (dict(params), lambda values, p: cusum_alarm_count(
                values, k=float(p["k"]), h=float(p["h"])
            ))
            for params in cusum_grid
        ],
        "sign_run": [
            (dict(params), lambda values, p: sign_run_alarm_count(
                values,
                threshold=float(p["threshold"]),
                run_length=int(p["run_length"]),
            ))
            for params in p1_grid
        ],
    }
    stored: dict[str, list[dict[str, Any]]] = {
        detector: [
            {
                "params": params,
                "by_probability": {},
                "passes_all_probabilities": True,
                "worst_upper95_series_alarm_rate": 0.0,
            }
            for params, _ in settings
        ]
        for detector, settings in detector_settings.items()
    }

    for probability_index, probability in enumerate(restart_probabilities):
        p = float(probability)
        rng = random.Random(
            seed + probability_index * 100_003 + int(round(p * 10_000))
        )
        event_totals = {
            detector: [[] for _ in settings]
            for detector, settings in detector_settings.items()
        }
        alarm_rates = {
            detector: [[] for _ in settings]
            for detector, settings in detector_settings.items()
        }
        sampled_block_count = 0
        sampled_point_count = 0

        for _ in range(replicates):
            replicate_events = {
                detector: [0 for _ in settings]
                for detector, settings in detector_settings.items()
            }
            replicate_alarm_series = {
                detector: [0 for _ in settings]
                for detector, settings in detector_settings.items()
            }
            for key, segments in panel.items():
                blocks = stationary_bootstrap_sample(
                    segments,
                    target_length=exposure_by_series[key],
                    restart_probability=p,
                    rng=rng,
                )
                sampled_block_count += len(blocks)
                sampled_point_count += sum(len(block) for block in blocks)
                synthetic_path = [
                    value for block in blocks for value in block
                ]
                for detector, settings in detector_settings.items():
                    for index, (params, alarm_counter) in enumerate(settings):
                        alarms = alarm_counter(synthetic_path, params)
                        replicate_events[detector][index] += alarms
                        replicate_alarm_series[detector][index] += int(alarms > 0)

            for detector, settings in detector_settings.items():
                for index in range(len(settings)):
                    event_totals[detector][index].append(
                        replicate_events[detector][index]
                    )
                    alarm_rates[detector][index].append(
                        replicate_alarm_series[detector][index] / series_count
                    )

        output["sampling_diagnostics"][str(p)] = {
            "expected_geometric_block_length": 1.0 / p,
            "observed_mean_sampled_block_length": (
                sampled_point_count / sampled_block_count
                if sampled_block_count else None
            ),
            "sampled_block_count": sampled_block_count,
            "sampled_point_count": sampled_point_count,
        }

        for detector, settings in detector_settings.items():
            for index, (params, _) in enumerate(settings):
                rates = alarm_rates[detector][index]
                upper95 = percentile(rates, 0.95)
                mean_rate = statistics.mean(rates) if rates else None
                mean_events_per_1000 = (
                    1000.0 * sum(event_totals[detector][index])
                    / (replicates * exposure)
                )
                passed = (
                    upper95 is not None
                    and upper95 <= MAX_ACCEPTABLE_SERIES_ALERT_RATE
                )
                record = stored[detector][index]
                record["by_probability"][str(p)] = {
                    "expected_block_length": 1.0 / p,
                    "mean_series_alarm_rate": mean_rate,
                    "upper95_series_alarm_rate": upper95,
                    "mean_events_per_1000_ready_periods": mean_events_per_1000,
                    "passes_5pct_series_screen": passed,
                }
                record["passes_all_probabilities"] = (
                    record["passes_all_probabilities"] and passed
                )
                record["worst_upper95_series_alarm_rate"] = max(
                    record["worst_upper95_series_alarm_rate"],
                    upper95 if upper95 is not None else 1.0,
                )

    for detector in detector_settings:
        output["detectors"][detector] = stored[detector]
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
    # The detector state must start at the labelled injection onset. Filtering
    # only the returned hit timestamp is insufficient: CUSUM can carry a
    # sub-threshold accumulator from pre-injection years into the injected run.
    onset_year = year_number(onset)
    post_onset_rows = [
        row for row in rows
        if year_number(row["event_time"]) >= onset_year
    ]
    if detector == "cusum":
        hits = detect_two_sided_cusum(
            post_onset_rows,
            k=float(parameters["k"]),
            h=float(parameters["h"]),
        )
    elif detector == "sign_run":
        hits = detect_sign_runs(
            post_onset_rows,
            threshold=float(parameters["threshold"]),
            run_length=int(parameters["run_length"]),
        )
    else:
        raise ValueError("detector_type_unsupported")
    first = first_evidence_at_or_after(hits, onset)
    delay = _time_delta(onset, first["event_time"]) if first else None
    return {
        "detected": first is not None,
        "detected_within_3_years": (
            delay is not None and delay <= DETECTION_HORIZON_YEARS
        ),
        "direction": first["direction"] if first else None,
        "first_evidence_time": first["event_time"] if first else None,
        "delay_years": delay,
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
            "injected_detected_within_3_years": inj["detected_within_3_years"],
            "control_detected_within_3_years": ctl["detected_within_3_years"],
            "incremental_detection": inj["detected"] and not ctl["detected"],
            "control_only_detection": ctl["detected"] and not inj["detected"],
            "incremental_detection_within_3_years": (
                inj["detected_within_3_years"] and not ctl["detected_within_3_years"]
            ),
            "control_only_detection_within_3_years": (
                ctl["detected_within_3_years"] and not inj["detected_within_3_years"]
            ),
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
            "injected_detected_within_3_years": inj["detected_within_3_years"],
            "control_detected_within_3_years": ctl["detected_within_3_years"],
            "incremental_detection": inj["detected"] and not ctl["detected"],
            "control_only_detection": ctl["detected"] and not inj["detected"],
            "incremental_detection_within_3_years": (
                inj["detected_within_3_years"] and not ctl["detected_within_3_years"]
            ),
            "control_only_detection_within_3_years": (
                ctl["detected_within_3_years"] and not inj["detected_within_3_years"]
            ),
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
        # Residual streams are intentionally built only for entities with
        # sufficient contiguous history. Short source series must be counted
        # and skipped, not indexed as if a residual stream had been created.
        if entity_id not in original_residuals:
            skipped["insufficient_baseline_history"] += 1
            continue
        series = [dict(row) for row in source]
        base_residuals = list(original_residuals[entity_id])
        if not base_residuals:
            skipped["empty_residual_stream"] += 1
            continue
        evaluation_times = sorted({
            year_number(row["event_time"])
            for row in base_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
            and row.get("status") == "ready"
        })
        selected_onset = fixed_injection_onset(evaluation_times)
        if selected_onset is None:
            skipped["insufficient_pre_or_post_injection_history"] += 1
            continue
        onset_year = selected_onset
        onset = INJECTION_ONSET
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
                (
                    raw_injected,
                    raw_control,
                    white_injected,
                    white_control,
                    matched_injection_series,
                    matched_injection_periods,
                ) = _matched_evaluation_streams(
                    raw_injected,
                    raw_control,
                    injected_whitened,
                    control_whitened,
                    min_segment_length=2,
                )

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
                        "matched_common_series": matched_injection_series,
                        "matched_common_ready_periods": matched_injection_periods,
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



def _matched_evaluation_streams(
    *streams: Sequence[Mapping[str, Any]],
    min_segment_length: int = 2,
) -> tuple[Any, ...]:
    """Align all streams on the exact same ready entity/metric/annual periods.

    A period is eligible only when every stream has a ready finite z-score.
    Missing, non-ready or absent years become shared reset rows, so detector
    state and bootstrap segments cannot bridge a period unavailable to a peer.
    Returns each aligned stream followed by (eligible_series, common_ready_periods).
    """
    if len(streams) < 2:
        raise ValueError("matched_streams_requires_at_least_two_paths")
    if min_segment_length < 1:
        raise ValueError("matched_stream_min_segment_length_invalid")

    grouped_streams: list[dict[tuple[str, str], dict[int, dict[str, Any]]]] = []
    for stream in streams:
        grouped: dict[tuple[str, str], dict[int, dict[str, Any]]] = defaultdict(dict)
        for row in stream:
            key = (str(row["entity_id"]), str(row["metric_id"]))
            year = year_number(row["event_time"])
            if year in grouped[key]:
                raise ValueError("matched_stream_duplicate_entity_metric_year")
            grouped[key][year] = dict(row)
        grouped_streams.append(dict(grouped))

    common_series_keys = set(grouped_streams[0])
    for grouped in grouped_streams[1:]:
        common_series_keys.intersection_update(grouped)

    aligned: list[list[dict[str, Any]]] = [[] for _ in streams]
    eligible_series = 0
    common_ready_periods = 0

    for entity_id, metric_id in sorted(common_series_keys):
        maps = [grouped[(entity_id, metric_id)] for grouped in grouped_streams]
        observed_years = sorted({year for mapping in maps for year in mapping})
        if not observed_years:
            continue

        per_stream: list[list[dict[str, Any]]] = [[] for _ in streams]
        per_series_common_ready = 0
        for year in range(observed_years[0], observed_years[-1] + 1):
            source_rows = [mapping.get(year) for mapping in maps]
            ready_for_all = all(
                row is not None
                and row.get("status") == "ready"
                and row.get("z_score") is not None
                and math.isfinite(float(row["z_score"]))
                for row in source_rows
            )
            if ready_for_all:
                for index, row in enumerate(source_rows):
                    per_stream[index].append(dict(row))
                per_series_common_ready += 1
                continue

            # Emit the same explicit reset period into every aligned path.
            for index, source in enumerate(source_rows):
                # A year absent from every input still needs to reset the
                # detector state inside the original baseline_id group.
                # Inherit identity from the nearest source row rather than
                # creating an isolated synthetic baseline for this reset.
                fallback = source
                if fallback is None and maps[index]:
                    nearest_year = min(
                        maps[index],
                        key=lambda candidate: (abs(candidate - year), candidate),
                    )
                    fallback = maps[index][nearest_year]
                placeholder = dict(source) if source is not None else {}
                placeholder.update({
                    "entity_id": entity_id,
                    "metric_id": metric_id,
                    "event_time": str(year),
                    "observed_value": None,
                    "expected_value": None,
                    "residual": None,
                    "scale": None,
                    "z_score": None,
                    "status": "gap_unresolved",
                    "baseline_id": str(
                        (fallback or {}).get(
                            "baseline_id",
                            f"{entity_id}:{metric_id}:matched-gap:{index}",
                        )
                    ),
                    "baseline_method": str(
                        (fallback or {}).get("baseline_method", "matched_support_reset")
                    ),
                    "support_count": int((fallback or {}).get("support_count", 0)),
                })
                per_stream[index].append(placeholder)

        has_usable_segment = any(
            len(segment) >= min_segment_length
            for segment in contiguous_ready_segments(per_stream[0])
        )
        if has_usable_segment:
            eligible_series += 1
            common_ready_periods += per_series_common_ready
            for index in range(len(streams)):
                aligned[index].extend(per_stream[index])

    return (*aligned, eligible_series, common_ready_periods)



def compare_screened_injection_recall(
    raw_null: Mapping[str, Any],
    innovation_null: Mapping[str, Any],
    injection_responses: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Compare identical 5%-passing settings with paired entity-level uncertainty."""
    if raw_null.get("status") != "ok" or innovation_null.get("status") != "ok":
        return {"status": "skipped_null_calibration_unavailable"}

    def passing(
        calibration: Mapping[str, Any],
        detector: str,
    ) -> set[tuple[tuple[str, Any], ...]]:
        return {
            tuple(sorted(dict(item["params"]).items()))
            for item in calibration.get("detectors", {}).get(detector, [])
            if item.get("passes_all_probabilities")
        }

    def find_candidate(
        row: Mapping[str, Any],
        detector: str,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        return next(
            (
                candidate for candidate in row.get(detector, [])
                if all(candidate.get(key) == value for key, value in params.items())
            ),
            None,
        )

    def bootstrap_ci(values: Sequence[float], *, seed: int) -> list[float] | None:
        if not values:
            return None
        rng = random.Random(seed)
        estimates = [
            statistics.mean(values[rng.randrange(len(values))] for _ in values)
            for _ in range(2000)
        ]
        estimates.sort()
        return [
            float(estimates[int(0.025 * (len(estimates) - 1))]),
            float(estimates[int(0.975 * (len(estimates) - 1))]),
        ]

    raw_by_scenario: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    white_by_scenario: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in injection_responses.get("raw_residuals", []):
        raw_by_scenario[str(row["scenario"])][str(row["entity_id"])] = row
    for row in injection_responses.get("prewhitened_innovations", []):
        white_by_scenario[str(row["scenario"])][str(row["entity_id"])] = row

    result: dict[str, Any] = {
        "status": "ok",
        "comparison_rule": (
            "A setting is eligible only if its upper-95% series-alarm rate is <=5% "
            "for every tested stationary-bootstrap restart probability in both streams. "
            "Recall is paired by entity and uses identical shift, onset, and detector "
            "parameters. Confidence intervals bootstrap matched entities."
        ),
        "common_passing_settings": {},
        "scenario_comparisons": {},
    }

    common_by_detector: dict[str, set[tuple[tuple[str, Any], ...]]] = {}
    for detector in ("cusum", "sign_run"):
        common = passing(raw_null, detector) & passing(innovation_null, detector)
        common_by_detector[detector] = common
        result["common_passing_settings"][detector] = [
            dict(params) for params in sorted(common)
        ]

    for scenario in sorted(set(raw_by_scenario) & set(white_by_scenario)):
        raw_entities = raw_by_scenario[scenario]
        white_entities = white_by_scenario[scenario]
        common_entities = sorted(set(raw_entities) & set(white_entities))
        scenario_result: dict[str, Any] = {
            "matched_series": len(common_entities),
            "detectors": {},
        }

        for detector in ("cusum", "sign_run"):
            paired_settings = []
            for setting_index, parameter_key in enumerate(sorted(common_by_detector[detector])):
                params = dict(parameter_key)
                raw_detected: list[float] = []
                white_detected: list[float] = []
                raw_detected_3yr: list[float] = []
                white_detected_3yr: list[float] = []
                raw_control: list[float] = []
                white_control: list[float] = []
                raw_control_3yr: list[float] = []
                white_control_3yr: list[float] = []
                raw_correct: list[float] = []
                white_correct: list[float] = []
                raw_delays: list[float] = []
                white_delays: list[float] = []

                for entity_id in common_entities:
                    raw_hit = find_candidate(raw_entities[entity_id], detector, params)
                    white_hit = find_candidate(white_entities[entity_id], detector, params)
                    if raw_hit is None or white_hit is None:
                        continue
                    expected_direction = "positive" if scenario.startswith("positive") else "negative"
                    raw_detected.append(float(bool(raw_hit["injected_detected"])))
                    white_detected.append(float(bool(white_hit["injected_detected"])))
                    raw_detected_3yr.append(float(bool(raw_hit["injected_detected_within_3_years"])))
                    white_detected_3yr.append(float(bool(white_hit["injected_detected_within_3_years"])))
                    raw_control.append(float(bool(raw_hit["control_detected"])))
                    white_control.append(float(bool(white_hit["control_detected"])))
                    raw_control_3yr.append(float(bool(raw_hit["control_detected_within_3_years"])))
                    white_control_3yr.append(float(bool(white_hit["control_detected_within_3_years"])))
                    raw_correct.append(float(
                        bool(raw_hit["injected_detected"])
                        and raw_hit.get("injected_direction") == expected_direction
                    ))
                    white_correct.append(float(
                        bool(white_hit["injected_detected"])
                        and white_hit.get("injected_direction") == expected_direction
                    ))
                    if raw_hit.get("injected_delay_years") is not None:
                        raw_delays.append(float(raw_hit["injected_delay_years"]))
                    if white_hit.get("injected_delay_years") is not None:
                        white_delays.append(float(white_hit["injected_delay_years"]))

                n = len(raw_detected)
                if not n:
                    continue
                recall_delta = [
                    white_detected[i] - raw_detected[i] for i in range(n)
                ]
                recall_delta_3yr = [
                    white_detected_3yr[i] - raw_detected_3yr[i] for i in range(n)
                ]
                raw_net_3yr = [
                    raw_detected_3yr[i] - raw_control_3yr[i] for i in range(n)
                ]
                white_net_3yr = [
                    white_detected_3yr[i] - white_control_3yr[i] for i in range(n)
                ]
                net_delta_3yr = [
                    white_net_3yr[i] - raw_net_3yr[i] for i in range(n)
                ]
                raw_net = [
                    raw_detected[i] - raw_control[i] for i in range(n)
                ]
                white_net = [
                    white_detected[i] - white_control[i] for i in range(n)
                ]
                net_delta = [
                    white_net[i] - raw_net[i] for i in range(n)
                ]
                stable_seed = (
                    NULL_BOOTSTRAP_SEED
                    + sum(ord(char) for char in scenario)
                    + (0 if detector == "cusum" else 20_000)
                    + setting_index
                )
                paired_settings.append({
                    "parameters": params,
                    "tested_series": n,
                    "raw_injected_detection_rate": statistics.mean(raw_detected),
                    "prewhitened_injected_detection_rate": statistics.mean(white_detected),
                    "recall_difference_innovation_minus_raw": statistics.mean(recall_delta),
                    "recall_difference_ci95": bootstrap_ci(recall_delta, seed=stable_seed),
                    "raw_injected_detection_rate_within_3_years": statistics.mean(raw_detected_3yr),
                    "prewhitened_injected_detection_rate_within_3_years": statistics.mean(white_detected_3yr),
                    "recall_difference_3yr_innovation_minus_raw": statistics.mean(recall_delta_3yr),
                    "recall_difference_3yr_ci95": bootstrap_ci(recall_delta_3yr, seed=stable_seed + 2),
                    "raw_control_detection_rate": statistics.mean(raw_control),
                    "prewhitened_control_detection_rate": statistics.mean(white_control),
                    "raw_net_detection_gain": statistics.mean(raw_net),
                    "prewhitened_net_detection_gain": statistics.mean(white_net),
                    "net_detection_gain_difference_innovation_minus_raw": statistics.mean(net_delta),
                    "net_detection_gain_difference_ci95": bootstrap_ci(net_delta, seed=stable_seed + 1),
                    "raw_net_detection_gain_within_3_years": statistics.mean(raw_net_3yr),
                    "prewhitened_net_detection_gain_within_3_years": statistics.mean(white_net_3yr),
                    "net_detection_gain_difference_3yr_innovation_minus_raw": statistics.mean(net_delta_3yr),
                    "net_detection_gain_difference_3yr_ci95": bootstrap_ci(net_delta_3yr, seed=stable_seed + 3),
                    "raw_correct_direction_rate": statistics.mean(raw_correct),
                    "prewhitened_correct_direction_rate": statistics.mean(white_correct),
                    "raw_median_detection_delay_years": statistics.median(raw_delays) if raw_delays else None,
                    "prewhitened_median_detection_delay_years": statistics.median(white_delays) if white_delays else None,
                })

            deltas = [
                item["recall_difference_innovation_minus_raw"]
                for item in paired_settings
            ]
            scenario_result["detectors"][detector] = {
                "paired_passing_setting_count": len(paired_settings),
                "paired_settings": paired_settings,
                "mean_recall_difference_across_settings": (
                    statistics.mean(deltas) if deltas else None
                ),
                "conclusion": (
                    "prewhitened_innovations_higher_recall"
                    if deltas and statistics.mean(deltas) > 0
                    else "raw_residuals_higher_recall"
                    if deltas and statistics.mean(deltas) < 0
                    else "no_common_5pct_passing_setting"
                    if not deltas
                    else "equal_recall"
                ),
            }
        result["scenario_comparisons"][scenario] = scenario_result
    return result

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

    all_residuals = [
        row for rows in residual_by_entity.values() for row in rows
    ]
    calibration = estimate_panel_residual_rho(
        all_residuals,
        training_end=TRAINING_END,
    )

    raw_null = None
    innovation_null = None
    screened_comparison: dict[str, Any] = {
        "status": "skipped_panel_rho_not_approved"
    }

    if calibration["status"] == "ok":
        evaluation_rows = [
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ]
        whitened = prewhiten_evaluation_rows(all_residuals, calibration)
        (
            matched_raw,
            matched_white,
            matched_series_count,
            matched_ready_periods,
        ) = _matched_evaluation_streams(
            evaluation_rows,
            whitened,
            min_segment_length=2,
        )

        raw_diag = lag1_summary(matched_raw)
        whitened_diag = lag1_summary(matched_white)

        # Both streams use identical detector grids, sample support, restart
        # probabilities and upper-95% per-series alarm gate.
        raw_null_candidates = [
            row for row in matched_raw
            if year_number(row["event_time"]) <= year_number(NULL_CALIBRATION_END)
        ]
        white_null_candidates = [
            row for row in matched_white
            if year_number(row["event_time"]) <= year_number(NULL_CALIBRATION_END)
        ]
        (
            matched_null_raw,
            matched_null_white,
            null_calibration_series_count,
            null_calibration_ready_periods,
        ) = _matched_evaluation_streams(
            raw_null_candidates,
            white_null_candidates,
            min_segment_length=MIN_NULL_SEGMENT_LENGTH,
        )
        raw_null = calibrate_prewhitened_null(
            matched_null_raw,
            cusum_grid=RAW_CUSUM_GRID,
            p1_grid=RAW_P1_GRID,
            min_segment_length=MIN_NULL_SEGMENT_LENGTH,
        )
        innovation_null = calibrate_prewhitened_null(
            matched_null_white,
            cusum_grid=INNOVATION_CUSUM_GRID,
            p1_grid=INNOVATION_P1_GRID,
            min_segment_length=MIN_NULL_SEGMENT_LENGTH,
        )

        raw_signals = summarize_detector_hits(
            matched_raw,
            cusum_grid=RAW_CUSUM_GRID,
            p1_grid=RAW_P1_GRID,
        )
        whitened_signals = summarize_detector_hits(
            matched_white,
            cusum_grid=INNOVATION_CUSUM_GRID,
            p1_grid=INNOVATION_P1_GRID,
        )

        injections = run_injection_experiment(
            entity_series,
            residual_by_entity,
            calibration,
        )
        summarized_injections: dict[str, Any] = {}
        for stream_name, stream_rows in injections.get("responses", {}).items():
            for row in stream_rows:
                row["stream_name"] = stream_name
            summarized_injections[stream_name] = summarize_injection_response(
                stream_rows
            )
        injection_status = {
            "status": injections["status"],
            "eligible_entities": injections["eligible_entities"],
            "skipped_entities": injections["skipped_entities"],
            "summaries": summarized_injections,
        }
        screened_comparison = compare_screened_injection_recall(
            raw_null,
            innovation_null,
            injections.get("responses", {}),
        )
    else:
        evaluation_rows = [
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ]
        matched_series_count = 0
        matched_ready_periods = 0
        raw_diag = lag1_summary(evaluation_rows)
        whitened_diag = None
        raw_signals = summarize_detector_hits(evaluation_rows)
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
        "dependence_calibration": {
            key: value
            for key, value in calibration.items()
            if key not in ("entity_centers", "entity_pair_counts")
        },
        "evaluation_residual_dependence": {
            "raw_matched": raw_diag,
            "prewhitened_matched": whitened_diag,
        },
        "matched_series_count": matched_series_count,
        "matched_ready_periods": matched_ready_periods,
        "null_calibration_matched_series_count": (
            null_calibration_series_count if calibration["status"] == "ok" else 0
        ),
        "null_calibration_matched_ready_periods": (
            null_calibration_ready_periods if calibration["status"] == "ok" else 0
        ),
        "temporal_split": {
            "dependence_training_end": TRAINING_END,
            "null_calibration_start": EVALUATION_START,
            "null_calibration_end": NULL_CALIBRATION_END,
            "controlled_injection_onset": INJECTION_ONSET,
            "minimum_post_injection_periods": MIN_POST_INJECTION_PERIODS,
            "minimum_contiguous_null_segment_length": MIN_NULL_SEGMENT_LENGTH,
            "three_year_detection_horizon_end": str(
                year_number(INJECTION_ONSET) + DETECTION_HORIZON_YEARS
            ),
            "three_year_recall_definition": (
                "A detection is within three years when first evidence is no later "
                "than onset_year + 3; the total evaluation endpoint remains 2024."
            ),
        },
        "historical_signal_profile": {
            "raw_residuals": raw_signals,
            "prewhitened_innovations": whitened_signals,
        },
        "stationary_bootstrap_null_calibration": {
            "raw_residuals": raw_null,
            "prewhitened_innovations": innovation_null,
        },
        "controlled_persistent_shift_injections": injection_status,
        "screened_injection_recall_comparison": screened_comparison,
        "interpretation": (
            "Raw residuals and prewhitened innovations are evaluated on the same "
            "entity/metric cohort with identical detector grids, stationary-bootstrap "
            "restart probabilities and upper-95% 5% series-alarm screen. Null "
            "calibration uses only series with at least five contiguous ready periods. "
            "Recall is reported both within three years and through the 2024 endpoint. "
            "This is an empirical candidate screen, not a verified production false-alarm "
            "guarantee. Persistent-shift injections are controlled simulations."
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
        "raw_eval_autocorrelation": result["evaluation_residual_dependence"]["raw_matched"],
        "whitened_eval_autocorrelation": result["evaluation_residual_dependence"]["prewhitened_matched"],
        "raw_signal_profile": result["historical_signal_profile"]["raw_residuals"],
        "whitened_signal_profile": result["historical_signal_profile"]["prewhitened_innovations"],
        "stationary_bootstrap_null": result["stationary_bootstrap_null_calibration"],
        "screened_injection_comparison": result["screened_injection_recall_comparison"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
