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

RAW_CUSUM_GRID = tuple(dict(item) for item in NULL_CUSUM_GRID)
# Use the established empirical-null grid for transformed standardized
# innovations. Each candidate is screened on the held-out innovation stream.
INNOVATION_CUSUM_GRID = tuple(dict(item) for item in NULL_CUSUM_GRID)
RAW_P1_GRID = tuple(dict(item) for item in NULL_P1_GRID)
STATIONARY_BOOTSTRAP_P_GRID = (0.25, 0.30, 0.35)
INNOVATION_P1_GRID = tuple(dict(item) for item in NULL_P1_GRID)


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



def _matched_evaluation_streams(
    raw_rows: Sequence[Mapping[str, Any]],
    innovation_rows: Sequence[Mapping[str, Any]],
    *,
    min_segment_length: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Restrict raw and innovation streams to exactly the same series cohort."""
    def group(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        result: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[(str(row["entity_id"]), str(row["metric_id"]))].append(dict(row))
        return result

    raw_grouped = group(raw_rows)
    innovation_grouped = group(innovation_rows)

    def eligible(grouped: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]) -> set[tuple[str, str]]:
        return {
            key for key, series_rows in grouped.items()
            if any(
                len(segment) >= min_segment_length
                for segment in contiguous_ready_segments(series_rows)
            )
        }

    common = eligible(raw_grouped) & eligible(innovation_grouped)
    raw_matched = [
        row for key in sorted(common) for row in raw_grouped[key]
    ]
    innovation_matched = [
        row for key in sorted(common) for row in innovation_grouped[key]
    ]
    return raw_matched, innovation_matched, len(common)


def compare_screened_injection_recall(
    raw_null: Mapping[str, Any],
    innovation_null: Mapping[str, Any],
    injection_summaries: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare recall only for identical detector settings passing both gates."""
    if raw_null.get("status") != "ok" or innovation_null.get("status") != "ok":
        return {"status": "skipped_null_calibration_unavailable"}

    def passing(calibration: Mapping[str, Any], detector: str) -> dict[tuple[tuple[str, Any], ...], dict[str, Any]]:
        allowed: dict[tuple[tuple[str, Any], ...], dict[str, Any]] = {}
        for item in calibration.get("detectors", {}).get(detector, []):
            if item.get("passes_all_probabilities"):
                params = dict(item["params"])
                allowed[tuple(sorted(params.items()))] = params
        return allowed

    raw_summary = injection_summaries.get("raw_residuals", {})
    white_summary = injection_summaries.get("prewhitened_innovations", {})
    scenarios = sorted(set(raw_summary) & set(white_summary))
    result: dict[str, Any] = {
        "status": "ok",
        "comparison_rule": (
            "Paired comparison only: a detector setting is eligible if it passes "
            "the 5% upper-95% series-alarm screen for every stationary-bootstrap "
            "restart probability in both streams."
        ),
        "common_passing_settings": {},
        "scenario_comparisons": {},
    }

    for detector in ("cusum", "sign_run"):
        common = set(passing(raw_null, detector)) & set(passing(innovation_null, detector))
        result["common_passing_settings"][detector] = [
            dict(params) for params in sorted(common)
        ]

    for scenario in scenarios:
        result["scenario_comparisons"][scenario] = {}
        for detector in ("cusum", "sign_run"):
            common = set(passing(raw_null, detector)) & set(passing(innovation_null, detector))
            raw_rows = raw_summary[scenario].get(detector, [])
            white_rows = white_summary[scenario].get(detector, [])
            paired = []
            for key in sorted(common):
                params = dict(key)
                raw_hit = next(
                    (row for row in raw_rows if all(row.get(k) == v for k, v in params.items())),
                    None,
                )
                white_hit = next(
                    (row for row in white_rows if all(row.get(k) == v for k, v in params.items())),
                    None,
                )
                if raw_hit is None or white_hit is None:
                    continue
                raw_recall = raw_hit.get("injected_detection_rate")
                white_recall = white_hit.get("injected_detection_rate")
                paired.append({
                    "parameters": params,
                    "raw": dict(raw_hit),
                    "prewhitened": dict(white_hit),
                    "recall_difference_innovation_minus_raw": (
                        float(white_recall) - float(raw_recall)
                        if white_recall is not None and raw_recall is not None
                        else None
                    ),
                    "net_detection_gain_difference_innovation_minus_raw": (
                        float(white_hit["net_detection_rate_delta"])
                        - float(raw_hit["net_detection_rate_delta"])
                        if white_hit.get("net_detection_rate_delta") is not None
                        and raw_hit.get("net_detection_rate_delta") is not None
                        else None
                    ),
                })
            result["scenario_comparisons"][scenario][detector] = {
                "paired_passing_setting_count": len(paired),
                "paired_settings": paired,
                "conclusion": (
                    "prewhitened_innovations_higher_recall"
                    if paired and statistics.mean(
                        item["recall_difference_innovation_minus_raw"]
                        for item in paired
                        if item["recall_difference_innovation_minus_raw"] is not None
                    ) > 0
                    else "raw_residuals_higher_recall"
                    if paired and statistics.mean(
                        item["recall_difference_innovation_minus_raw"]
                        for item in paired
                        if item["recall_difference_innovation_minus_raw"] is not None
                    ) < 0
                    else "tie_or_no_complete_paired_recall"
                ),
            }
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
        matched_raw, matched_white, matched_series_count = _matched_evaluation_streams(
            evaluation_rows,
            whitened,
            min_segment_length=2,
        )

        raw_diag = lag1_summary(matched_raw)
        whitened_diag = lag1_summary(matched_white)

        # Both streams use identical detector grids, sample support, restart
        # probabilities and upper-95% per-series alarm gate.
        raw_null = calibrate_prewhitened_null(
            matched_raw,
            cusum_grid=RAW_CUSUM_GRID,
            p1_grid=RAW_P1_GRID,
            min_segment_length=2,
        )
        innovation_null = calibrate_prewhitened_null(
            matched_white,
            cusum_grid=INNOVATION_CUSUM_GRID,
            p1_grid=INNOVATION_P1_GRID,
            min_segment_length=2,
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
            summarized_injections,
        )
    else:
        evaluation_rows = [
            row for row in all_residuals
            if year_number(row["event_time"]) >= year_number(EVALUATION_START)
        ]
        matched_series_count = 0
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
            "restart probabilities and upper-95% 5% series-alarm screen. This is an "
            "empirical candidate screen, not a verified production false-alarm "
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
        "raw_eval_autocorrelation": result["evaluation_residual_dependence"]["raw"],
        "whitened_eval_autocorrelation": result["evaluation_residual_dependence"]["prewhitened"],
        "raw_signal_profile": result["historical_signal_profile"]["raw_residuals"],
        "whitened_signal_profile": result["historical_signal_profile"]["prewhitened_innovations"],
        "stationary_bootstrap_null": result["stationary_bootstrap_null_calibration"],
        "screened_injection_comparison": result["screened_injection_recall_comparison"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
