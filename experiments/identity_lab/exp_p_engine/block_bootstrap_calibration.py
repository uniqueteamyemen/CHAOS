"""Block-bootstrap null calibration for CUSUM and P1 on real residual streams.

This experiment preserves within-block temporal dependence. It does not claim
that historical source periods are known anomaly-free; its null is the empirical
source-history distribution with block order randomized.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from experiments.identity_lab.exp_p_engine.calibration_sweep import read_world_bank
from experiments.identity_lab.exp_p_engine.domain_neutral import build_univariate_residuals

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_block_bootstrap_calibration.json"
)
BOOTSTRAP_REPLICATES = 300
BOOTSTRAP_SEED = 20261115
BLOCK_LENGTHS = (2, 3, 4, 6)
MAX_ACCEPTABLE_SERIES_ALERT_RATE = 0.05

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


def contiguous_ready_segments(rows: Sequence[dict[str, Any]]) -> list[list[float]]:
    """Split ready residuals at unresolved periods or nonconsecutive annual gaps."""
    segments: list[list[float]] = []
    current: list[float] = []
    previous_year: int | None = None
    for row in sorted(rows, key=lambda item: str(item["event_time"])):
        if row.get("status") != "ready" or row.get("z_score") is None:
            if current:
                segments.append(current)
                current = []
            previous_year = None
            continue
        raw_time = str(row["event_time"])
        try:
            year = int(raw_time[:4])
        except ValueError:
            raise ValueError("block_bootstrap_requires_annual_year_labels")
        if previous_year is not None and year != previous_year + 1:
            if current:
                segments.append(current)
            current = []
        current.append(float(row["z_score"]))
        previous_year = year
    if current:
        segments.append(current)
    return segments


def moving_block_resample(
    values: Sequence[float],
    *,
    block_length: int,
    rng: random.Random,
) -> list[float]:
    """Circular moving-block bootstrap, returning exactly the source length."""
    if not values or block_length < 1:
        raise ValueError("bootstrap_series_or_block_invalid")
    n = len(values)
    width = min(block_length, n)
    output: list[float] = []
    while len(output) < n:
        start = rng.randrange(n)
        for offset in range(width):
            output.append(float(values[(start + offset) % n]))
            if len(output) == n:
                break
    return output


def cusum_alarm_count(values: Sequence[float], *, k: float, h: float) -> int:
    positive = negative = 0.0
    alarms = 0
    for z in values:
        positive = max(0.0, positive + z - k)
        negative = max(0.0, negative - z - k)
        if positive >= h or negative >= h:
            alarms += 1
            positive = negative = 0.0
    return alarms


def sign_run_alarm_count(
    values: Sequence[float],
    *,
    threshold: float,
    run_length: int,
) -> int:
    sign = 0
    streak = 0
    alarms = 0
    for z in values:
        current_sign = 1 if z > 0 else -1 if z < 0 else 0
        if current_sign == 0 or abs(z) < threshold:
            sign, streak = 0, 0
            continue
        if current_sign != sign:
            sign, streak = current_sign, 0
        streak += 1
        if streak >= run_length:
            alarms += 1
            sign, streak = 0, 0
    return alarms


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(q * (len(ordered) - 1))))
    return float(ordered[index])


def lag1_correlation(values: Sequence[float]) -> float | None:
    if len(values) < 4:
        return None
    left = list(values[:-1])
    right = list(values[1:])
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    centered_left = [value - mean_left for value in left]
    centered_right = [value - mean_right for value in right]
    denominator = (
        sum(value * value for value in centered_left)
        * sum(value * value for value in centered_right)
    ) ** 0.5
    if denominator <= 0:
        return None
    return sum(a * b for a, b in zip(centered_left, centered_right)) / denominator


def residual_distribution_diagnostics() -> dict[str, Any]:
    """Compare baseline and scale-estimator distributions before detector tuning."""
    panel = read_world_bank()
    output: dict[str, Any] = {}
    for scale_estimator in ("first_difference_mad", "second_difference_mad"):
        output[scale_estimator] = {}
        for baseline_method in ("rolling_median", "rolling_theil_sen"):
            per_series: list[dict[str, Any]] = []
            pooled_z: list[float] = []
            scale_methods: dict[str, int] = defaultdict(int)
            for entity_id, observations in panel.items():
                if len(observations) < 12:
                    continue
                residuals = build_univariate_residuals(
                    observations,
                    baseline_window=12,
                    min_history=8,
                    time_unit="years",
                    baseline_method=baseline_method,
                    estimate_rho=False,
                    scale_window=16 if scale_estimator == "second_difference_mad" else 12,
                    scale_estimator=scale_estimator,
                )
                ready = [
                    row for row in residuals
                    if row.get("status") == "ready" and row.get("z_score") is not None
                ]
                if not ready:
                    continue
                z_values = [float(row["z_score"]) for row in ready]
                scales = [
                    float(row["scale"])
                    for row in ready
                    if row.get("scale") is not None and float(row["scale"]) > 0
                ]
                for row in ready:
                    scale_methods[str(row.get("scale_method"))] += 1
                pooled_z.extend(z_values)
                per_series.append({
                    "entity_id": entity_id,
                    "ready_periods": len(z_values),
                    "mean_z": sum(z_values) / len(z_values),
                    "median_z": percentile(z_values, 0.5),
                    "median_abs_z": percentile([abs(value) for value in z_values], 0.5),
                    "p95_abs_z": percentile([abs(value) for value in z_values], 0.95),
                    "share_abs_z_ge_2": sum(abs(value) >= 2.0 for value in z_values) / len(z_values),
                    "share_abs_z_ge_3": sum(abs(value) >= 3.0 for value in z_values) / len(z_values),
                    "share_abs_z_ge_4": sum(abs(value) >= 4.0 for value in z_values) / len(z_values),
                    "share_positive_z_ge_3": sum(value >= 3.0 for value in z_values) / len(z_values),
                    "share_negative_z_le_minus_3": sum(value <= -3.0 for value in z_values) / len(z_values),
                    "lag1_z_correlation": lag1_correlation(z_values),
                    "median_scale": percentile(scales, 0.5) if scales else None,
                    "min_scale": min(scales) if scales else None,
                })

            def metric_summary(metric: str) -> dict[str, Any]:
                values = [
                    float(row[metric])
                    for row in per_series
                    if row.get(metric) is not None
                ]
                return {
                    "series_with_metric": len(values),
                    "median_across_series": percentile(values, 0.5),
                    "p90_across_series": percentile(values, 0.9),
                    "max_across_series": max(values) if values else None,
                }

            output[scale_estimator][baseline_method] = {
                "series_tested": len(per_series),
                "ready_residuals": len(pooled_z),
                "pooled_z": {
                    "mean": sum(pooled_z) / len(pooled_z) if pooled_z else None,
                    "median": percentile(pooled_z, 0.5),
                    "median_absolute_z": percentile([abs(value) for value in pooled_z], 0.5),
                    "p95_absolute_z": percentile([abs(value) for value in pooled_z], 0.95),
                    "share_abs_z_ge_2": sum(abs(value) >= 2.0 for value in pooled_z) / len(pooled_z) if pooled_z else None,
                    "share_abs_z_ge_3": sum(abs(value) >= 3.0 for value in pooled_z) / len(pooled_z) if pooled_z else None,
                    "share_abs_z_ge_4": sum(abs(value) >= 4.0 for value in pooled_z) / len(pooled_z) if pooled_z else None,
                    "positive_share_z_ge_3": sum(value >= 3.0 for value in pooled_z) / len(pooled_z) if pooled_z else None,
                    "negative_share_z_le_minus_3": sum(value <= -3.0 for value in pooled_z) / len(pooled_z) if pooled_z else None,
                },
                "per_series": {
                    "median_abs_z": metric_summary("median_abs_z"),
                    "p95_abs_z": metric_summary("p95_abs_z"),
                    "share_abs_z_ge_3": metric_summary("share_abs_z_ge_3"),
                    "lag1_z_correlation": metric_summary("lag1_z_correlation"),
                    "median_scale": metric_summary("median_scale"),
                },
                "scale_method_counts": dict(scale_methods),
            }

    return {
        "source": "World Bank FS.AST.PRVT.GD.ZS",
        "purpose": "compare scale estimator and baseline behavior; not a labelled anomaly test",
        "estimators": output,
    }


def prepare_panel_from_series(
    entity_series: dict[str, list[dict[str, Any]]],
    *,
    scale_estimator: str,
) -> dict[str, list[list[float]]]:
    """Build identical source panels with one explicitly selected scale estimator."""
    if scale_estimator not in {"first_difference_mad", "second_difference_mad"}:
        raise ValueError("block_bootstrap_scale_estimator_unsupported")
    panel: dict[str, list[list[float]]] = {}
    for entity_id, observations in entity_series.items():
        if len(observations) < 12:
            continue
        residuals = build_univariate_residuals(
            observations,
            baseline_window=12,
            min_history=8,
            time_unit="years",
            baseline_method="rolling_theil_sen",
            estimate_rho=False,
            scale_window=16 if scale_estimator == "second_difference_mad" else 12,
            scale_estimator=scale_estimator,
        )
        segments = [
            segment for segment in contiguous_ready_segments(residuals)
            if len(segment) >= 8
        ]
        if segments:
            panel[entity_id] = segments
    return panel


def prepare_panel(
    *,
    scale_estimator: str = "first_difference_mad",
) -> dict[str, list[list[float]]]:
    return prepare_panel_from_series(
        read_world_bank(),
        scale_estimator=scale_estimator,
    )


def run_bootstrap(
    panel: dict[str, list[list[float]]],
    *,
    block_length: int,
    replicates: int,
) -> dict[str, Any]:
    rng = random.Random(BOOTSTRAP_SEED + block_length)
    entity_count = len(panel)
    series_exposure = sum(
        sum(len(segment) for segment in segments)
        for segments in panel.values()
    )
    replicate_results = {
        "cusum": {
            (item["k"], item["h"]): {
                "event_counts": [],
                "entities_with_any_alarm": [],
            }
            for item in CUSUM_GRID
        },
        "sign_run": {
            (item["threshold"], item["run_length"]): {
                "event_counts": [],
                "entities_with_any_alarm": [],
            }
            for item in P1_GRID
        },
    }

    for _ in range(replicates):
        per_rep_events = {
            "cusum": {key: 0 for key in replicate_results["cusum"]},
            "sign_run": {key: 0 for key in replicate_results["sign_run"]},
        }
        per_rep_entities = {
            "cusum": {key: 0 for key in replicate_results["cusum"]},
            "sign_run": {key: 0 for key in replicate_results["sign_run"]},
        }
        for segments in panel.values():
            boot_segments = [
                moving_block_resample(
                    segment, block_length=block_length, rng=rng
                )
                for segment in segments
            ]
            for key in replicate_results["cusum"]:
                k, h = key
                count = sum(
                    cusum_alarm_count(segment, k=k, h=h)
                    for segment in boot_segments
                )
                per_rep_events["cusum"][key] += count
                per_rep_entities["cusum"][key] += int(count > 0)
            for key in replicate_results["sign_run"]:
                threshold, run_length = key
                count = sum(
                    sign_run_alarm_count(
                        segment, threshold=threshold, run_length=run_length
                    )
                    for segment in boot_segments
                )
                per_rep_events["sign_run"][key] += count
                per_rep_entities["sign_run"][key] += int(count > 0)

        for detector in ("cusum", "sign_run"):
            for key in replicate_results[detector]:
                replicate_results[detector][key]["event_counts"].append(
                    per_rep_events[detector][key]
                )
                replicate_results[detector][key]["entities_with_any_alarm"].append(
                    per_rep_entities[detector][key] / entity_count if entity_count else 0.0
                )

    output: dict[str, Any] = {
        "block_length": block_length,
        "bootstrap_replicates": replicates,
        "entity_count": entity_count,
        "ready_residual_exposure": series_exposure,
        "detectors": {},
    }
    for detector, grid in (("cusum", CUSUM_GRID), ("sign_run", P1_GRID)):
        rows = []
        store = replicate_results[detector]
        for item in grid:
            key = (
                (item["k"], item["h"])
                if detector == "cusum"
                else (item["threshold"], item["run_length"])
            )
            counts = store[key]["event_counts"]
            rates = store[key]["entities_with_any_alarm"]
            total_events = sum(counts)
            mean_events = mean(counts) if counts else 0.0
            mean_rate = mean(rates) if rates else 0.0
            upper_rate = percentile(rates, 0.95)
            rows.append({
                **item,
                "mean_bootstrap_events_per_1000_ready_periods": (
                    1000.0 * total_events / (replicates * series_exposure)
                    if series_exposure else None
                ),
                "mean_series_with_any_alarm_rate": mean_rate,
                "upper95_bootstrap_series_alarm_rate": upper_rate,
                "passes_5pct_series_alarm_screen": (
                    upper_rate is not None
                    and upper_rate <= MAX_ACCEPTABLE_SERIES_ALERT_RATE
                ),
                "mean_events_per_bootstrap_panel": mean_events,
            })
        output["detectors"][detector] = rows
    return output


def main() -> None:
    scale_estimators = ("first_difference_mad", "second_difference_mad")
    estimator_results: dict[str, Any] = {}
    compact: dict[str, Any] = {}
    diagnostics = residual_distribution_diagnostics()

    for estimator_index, scale_estimator in enumerate(scale_estimators):
        panel = prepare_panel(scale_estimator=scale_estimator)
        segment_lengths = [
            len(segment)
            for segments in panel.values()
            for segment in segments
        ]
        block_results: dict[str, Any] = {}
        for block_length in BLOCK_LENGTHS:
            block_results[str(block_length)] = run_bootstrap(
                panel,
                block_length=block_length,
                replicates=BOOTSTRAP_REPLICATES,
            )
        estimator_results[scale_estimator] = {
            "scale_estimator": scale_estimator,
            "baseline": "prequential_rolling_theil_sen",
            "entity_count": len(panel),
            "segment_count": len(segment_lengths),
            "ready_residual_exposure": sum(segment_lengths),
            "segment_length_summary": {
                "min": min(segment_lengths) if segment_lengths else None,
                "median": (
                    percentile(segment_lengths, 0.5) if segment_lengths else None
                ),
                "max": max(segment_lengths) if segment_lengths else None,
            },
            "block_lengths": block_results,
        }
        compact[scale_estimator] = {}
        for length, block in block_results.items():
            compact[scale_estimator][length] = {
                "cusum": [
                    {
                        "k": item["k"], "h": item["h"],
                        "mean_series_alarm_rate": round(item["mean_series_with_any_alarm_rate"], 4),
                        "upper95_series_alarm_rate": round(item["upper95_bootstrap_series_alarm_rate"], 4),
                        "pass_5pct_screen": item["passes_5pct_series_alarm_screen"],
                    }
                    for item in block["detectors"]["cusum"]
                ],
                "sign_run": [
                    {
                        "threshold": item["threshold"], "run_length": item["run_length"],
                        "mean_series_alarm_rate": round(item["mean_series_with_any_alarm_rate"], 4),
                        "upper95_series_alarm_rate": round(item["upper95_bootstrap_series_alarm_rate"], 4),
                        "pass_5pct_screen": item["passes_5pct_series_alarm_screen"],
                    }
                    for item in block["detectors"]["sign_run"]
                ],
            }

    report = {
        "experiment": "domain_neutral_block_bootstrap_null_calibration_v2",
        "source": "World Bank FS.AST.PRVT.GD.ZS",
        "synthetic_data": False,
        "estimators": estimator_results,
        "residual_distribution_diagnostics": diagnostics,
        "null_definition": (
            "Circular moving-block resampling of historical ready residual z-scores. "
            "Both scale estimators use the same source panel definition, detector grid, "
            "block lengths, replicate count and bootstrap seeds. Temporal order is "
            "randomized only between blocks; within-block dependence is preserved. "
            "The historical source is unlabelled and may contain real breaks, so this "
            "is an empirical reference distribution, not verified no-break ground truth."
        ),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "block_lengths": list(BLOCK_LENGTHS),
        "5pct_series_alarm_screen": (
            "A candidate passes only when the 95th percentile across bootstrap panels "
            "of the proportion of entities with at least one alarm is <= 5%. "
            "This screen is not a production FPR guarantee."
        ),
        "threshold_promotion": "not_automatic",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "estimators": {
            key: {
                "entities": value["entity_count"],
                "segments": value["segment_count"],
                "ready_residual_exposure": value["ready_residual_exposure"],
            }
            for key, value in estimator_results.items()
        },
        "block_results": compact,
        "promotion": "not_automatic",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
