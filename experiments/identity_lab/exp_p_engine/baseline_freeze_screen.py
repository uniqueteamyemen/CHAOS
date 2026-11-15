"""Stationary-null screening of CUSUM-confirmed baseline freezing.

The CUSUM alarm is the detection event. Freezing is a post-confirmation
baseline-control action evaluated for evidence persistence and release; it is
not counted as a second detector or as an independent recall improvement.
"""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.identity_lab.exp_p_engine.calibration_sweep import read_world_bank
from experiments.identity_lab.exp_p_engine.baseline_freeze_experiment import (
    build_policy_residuals,
    time_position,
)
from experiments.identity_lab.exp_p_engine.domain_neutral import (
    detect_two_sided_cusum,
    first_evidence_at_or_after,
)
from experiments.identity_lab.exp_p_engine.residual_dependence_experiment import (
    calibrate_prewhitened_null,
    year_number,
    STATIONARY_BOOTSTRAP_P_GRID,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_confirmation_freeze_screen.json"
)

NULL_START = 2014
NULL_END = 2020
INJECTION_ONSET = "2021"
DETECTION_END = 2024
MIN_NULL_SEGMENT_LENGTH = 5
MIN_POST_INJECTION_PERIODS = 4
MIN_SERIES_FOR_NULL = 30
BOOTSTRAP_REPLICATES = 500
BOOTSTRAP_SEED = 20261115
CUSUM_K = 0.5
CONFIRMATION_H_GRID = (8.5, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 96.0, 128.0)
CUSUM_GRID = tuple({"k": CUSUM_K, "h": h} for h in CONFIRMATION_H_GRID)
INJECTION_SIGMAS = (3.0, 6.0)
INJECTION_DIRECTIONS = (-1, 1)


def _observed_series(
    source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for entity_id, rows in source.items():
        observed = [
            dict(row) for row in rows
            if row.get("observation_status") == "observed"
            and row.get("value") is not None
        ]
        observed.sort(key=lambda row: time_position(row["event_time"], "years"))
        if len(observed) >= 14:
            output[str(entity_id)] = observed
    return output


def _slice_years(
    rows: Sequence[Mapping[str, Any]],
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    return [
        dict(row) for row in rows
        if start_year <= year_number(row["event_time"]) <= end_year
    ]


def _first_cusum_alarm(
    rows: Sequence[Mapping[str, Any]],
    *,
    onset: str,
    h: float,
) -> dict[str, Any] | None:
    onset_year = year_number(onset)
    post_onset = [
        dict(row) for row in rows
        if year_number(row["event_time"]) >= onset_year
    ]
    hits = detect_two_sided_cusum(post_onset, k=CUSUM_K, h=h)
    return first_evidence_at_or_after(hits, onset)


def _first_freeze_trigger(
    rows: Sequence[Mapping[str, Any]],
    *,
    onset: str,
) -> str | None:
    onset_year = year_number(onset)
    triggers = [
        str(row["event_time"])
        for row in rows
        if row.get("freeze_trigger")
        and year_number(row["event_time"]) >= onset_year
    ]
    return min(triggers, key=year_number) if triggers else None


def _bootstrap_mean_ci(
    values: Sequence[float],
    *,
    seed: int,
    replicates: int = 2000,
) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    means = [
        statistics.mean(values[rng.randrange(len(values))] for _ in values)
        for _ in range(replicates)
    ]
    means.sort()
    return [
        float(means[int(0.025 * (len(means) - 1))]),
        float(means[int(0.975 * (len(means) - 1))]),
    ]


def _paired_post_trigger_metrics(
    rolling_rows: Sequence[Mapping[str, Any]],
    frozen_rows: Sequence[Mapping[str, Any]],
    *,
    trigger_time: str | None,
    direction: int,
) -> dict[str, Any]:
    if trigger_time is None:
        return {
            "post_trigger_periods": 0,
            "rolling_mean_abs_z": None,
            "frozen_mean_abs_z": None,
            "mean_abs_z_gain_frozen_minus_rolling": None,
            "mean_directional_z_gain_frozen_minus_rolling": None,
            "freeze_active_fraction": None,
            "freeze_active_periods": 0,
            "freeze_released": False,
            "freeze_release_time": None,
        }

    trigger_year = year_number(trigger_time)
    rolling_by_year = {year_number(row["event_time"]): row for row in rolling_rows}
    frozen_by_year = {year_number(row["event_time"]): row for row in frozen_rows}
    common_years = sorted(
        year for year in set(rolling_by_year) & set(frozen_by_year)
        if trigger_year < year <= DETECTION_END
        and rolling_by_year[year].get("status") == "ready"
        and frozen_by_year[year].get("status") == "ready"
        and rolling_by_year[year].get("z_score") is not None
        and frozen_by_year[year].get("z_score") is not None
    )
    abs_gain: list[float] = []
    directional_gain: list[float] = []
    rolling_abs: list[float] = []
    frozen_abs: list[float] = []
    active_flags: list[float] = []
    for year in common_years:
        rolling_z = float(rolling_by_year[year]["z_score"])
        frozen_z = float(frozen_by_year[year]["z_score"])
        rolling_abs.append(abs(rolling_z))
        frozen_abs.append(abs(frozen_z))
        abs_gain.append(abs(frozen_z) - abs(rolling_z))
        directional_gain.append(direction * (frozen_z - rolling_z))
        active_flags.append(float(bool(frozen_by_year[year].get("freeze_active"))))

    release_rows = [
        row for row in frozen_rows
        if row.get("freeze_released")
        and year_number(row["event_time"]) > trigger_year
    ]
    return {
        "post_trigger_periods": len(common_years),
        "rolling_mean_abs_z": statistics.mean(rolling_abs) if rolling_abs else None,
        "frozen_mean_abs_z": statistics.mean(frozen_abs) if frozen_abs else None,
        "mean_abs_z_gain_frozen_minus_rolling": statistics.mean(abs_gain) if abs_gain else None,
        "mean_directional_z_gain_frozen_minus_rolling": (
            statistics.mean(directional_gain) if directional_gain else None
        ),
        "freeze_active_fraction": statistics.mean(active_flags) if active_flags else None,
        "freeze_active_periods": sum(active_flags),
        "freeze_released": bool(release_rows),
        "freeze_release_time": str(release_rows[0]["event_time"]) if release_rows else None,
    }


def _summarize_scenario(
    records: Sequence[Mapping[str, Any]],
    *,
    h: float,
    scenario: str,
) -> dict[str, Any]:
    n = len(records)
    raw_injected = [float(row["raw_injected_alarm"]) for row in records]
    freeze_injected = [float(row["freeze_injected_trigger"]) for row in records]
    raw_control = [float(row["raw_control_alarm"]) for row in records]
    freeze_control = [float(row["freeze_control_trigger"]) for row in records]
    trigger_matches = [
        float(row["injected_trigger_time_matches"])
        for row in records
        if row.get("injected_trigger_time_matches") is not None
    ]
    control_trigger_matches = [
        float(row["control_trigger_time_matches"])
        for row in records
        if row.get("control_trigger_time_matches") is not None
    ]

    persistence = [
        float(row["injected_persistence"]["mean_abs_z_gain_frozen_minus_rolling"])
        for row in records
        if row["injected_persistence"]["mean_abs_z_gain_frozen_minus_rolling"] is not None
    ]
    control_persistence = [
        float(row["control_persistence"]["mean_abs_z_gain_frozen_minus_rolling"])
        for row in records
        if row["control_persistence"]["mean_abs_z_gain_frozen_minus_rolling"] is not None
    ]
    direction_gain = [
        float(row["injected_persistence"]["mean_directional_z_gain_frozen_minus_rolling"])
        for row in records
        if row["injected_persistence"]["mean_directional_z_gain_frozen_minus_rolling"] is not None
    ]
    freeze_releases = [
        float(row["injected_persistence"]["freeze_released"])
        for row in records
        if row["injected_alarm_time"] is not None
    ]
    return {
        "scenario": scenario,
        "confirmation_h": h,
        "matched_series": n,
        "raw_injected_alarm_rate": statistics.mean(raw_injected) if n else None,
        "confirmation_freeze_injected_trigger_rate": statistics.mean(freeze_injected) if n else None,
        "raw_control_alarm_rate": statistics.mean(raw_control) if n else None,
        "confirmation_freeze_control_trigger_rate": statistics.mean(freeze_control) if n else None,
        "injected_trigger_time_match_rate": (
            statistics.mean(trigger_matches) if trigger_matches else None
        ),
        "control_trigger_time_match_rate": (
            statistics.mean(control_trigger_matches) if control_trigger_matches else None
        ),
        "injected_mean_abs_z_gain_frozen_minus_rolling": (
            statistics.mean(persistence) if persistence else None
        ),
        "injected_mean_abs_z_gain_ci95": _bootstrap_mean_ci(
            persistence,
            seed=BOOTSTRAP_SEED + int(h * 100) + sum(ord(ch) for ch in scenario),
        ),
        "injected_mean_directional_z_gain_frozen_minus_rolling": (
            statistics.mean(direction_gain) if direction_gain else None
        ),
        "control_mean_abs_z_gain_frozen_minus_rolling": (
            statistics.mean(control_persistence) if control_persistence else None
        ),
        "control_mean_abs_z_gain_ci95": _bootstrap_mean_ci(
            control_persistence,
            seed=BOOTSTRAP_SEED + 1 + int(h * 100) + sum(ord(ch) for ch in scenario),
        ),
        "release_rate_among_triggered_injections": (
            statistics.mean(freeze_releases) if freeze_releases else None
        ),
        "interpretation": (
            "CUSUM trigger is the alarm. Freeze begins on the next observation; "
            "post-trigger z persistence is an operational-state metric, not extra recall."
        ),
    }


def _run_one_candidate(
    entity_series: Mapping[str, Sequence[Mapping[str, Any]]],
    rolling_by_entity: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    confirmation_h: float,
) -> dict[str, Any]:
    historical_confirmation: dict[str, list[dict[str, Any]]] = {}
    history_diagnostics: dict[str, dict[str, Any]] = {}
    for entity_id, observations in entity_series.items():
        rows, diagnostics = build_policy_residuals(
            observations,
            policy="confirmation_freeze_baseline_rolling_scale",
            time_unit="years",
            confirmation_k=CUSUM_K,
            confirmation_h=confirmation_h,
        )
        historical_confirmation[entity_id] = rows
        history_diagnostics[entity_id] = diagnostics

    null_rows = [
        row
        for rows in rolling_by_entity.values()
        for row in _slice_years(rows, NULL_START, NULL_END)
    ]
    null_screen = calibrate_prewhitened_null(
        null_rows,
        replicates=BOOTSTRAP_REPLICATES,
        seed=BOOTSTRAP_SEED,
        cusum_grid=({"k": CUSUM_K, "h": confirmation_h},),
        p1_grid=(),
        min_segment_length=MIN_NULL_SEGMENT_LENGTH,
        min_series=MIN_SERIES_FOR_NULL,
    )
    gate_rows = null_screen.get("detectors", {}).get("cusum", [])
    setting_gate = next(
        (
            item for item in gate_rows
            if item.get("k") == CUSUM_K and item.get("h") == confirmation_h
        ),
        None,
    )
    passes = bool(setting_gate and setting_gate.get("passes_all_probabilities"))

    null_trigger_entities = 0
    null_active_entities = 0
    null_episode_count = 0
    for entity_id, rows in historical_confirmation.items():
        null_rows_entity = _slice_years(rows, NULL_START, NULL_END)
        if any(row.get("freeze_trigger") for row in null_rows_entity):
            null_trigger_entities += 1
        if any(row.get("freeze_active") for row in null_rows_entity):
            null_active_entities += 1
        null_episode_count += sum(
            1 for episode in history_diagnostics[entity_id].get("freeze_episodes", [])
            if NULL_START <= year_number(episode.get("confirmation_time", episode["start_time"])) <= NULL_END
        )

    injections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = defaultdict(int)
    raw_injection_rows: dict[str, list[dict[str, Any]]] = {}
    for entity_id, observations in entity_series.items():
        rolling = list(rolling_by_entity[entity_id])
        pre_scales = [
            float(row["scale"])
            for row in rolling
            if NULL_START <= year_number(row["event_time"]) <= NULL_END
            and row.get("status") == "ready"
            and row.get("scale") is not None
            and float(row["scale"]) > 0
        ]
        if not pre_scales:
            skipped["pre_injection_scale_unavailable"] += 1
            continue
        sigma = statistics.median(pre_scales)
        post_observed = [
            row for row in observations
            if year_number(row["event_time"]) >= year_number(INJECTION_ONSET)
        ]
        if len(post_observed) < MIN_POST_INJECTION_PERIODS:
            skipped["insufficient_post_injection_history"] += 1
            continue
        raw_injection_rows[entity_id] = rolling

        control_freeze, control_diag = build_policy_residuals(
            observations,
            policy="confirmation_freeze_baseline_rolling_scale",
            time_unit="years",
            freeze_trigger_after_time=INJECTION_ONSET,
            confirmation_k=CUSUM_K,
            confirmation_h=confirmation_h,
        )
        for magnitude in INJECTION_SIGMAS:
            for direction in INJECTION_DIRECTIONS:
                injected = [dict(row) for row in observations]
                delta = direction * magnitude * sigma
                for row in injected:
                    if year_number(row["event_time"]) >= year_number(INJECTION_ONSET):
                        row["value"] = float(row["value"]) + delta

                raw_injected, _ = build_policy_residuals(
                    injected,
                    policy="rolling_baseline_rolling_scale",
                    time_unit="years",
                )
                freeze_injected, injected_diag = build_policy_residuals(
                    injected,
                    policy="confirmation_freeze_baseline_rolling_scale",
                    time_unit="years",
                    freeze_trigger_after_time=INJECTION_ONSET,
                    confirmation_k=CUSUM_K,
                    confirmation_h=confirmation_h,
                )

                raw_control = rolling
                raw_injected_post = [
                    row for row in raw_injected
                    if year_number(row["event_time"]) >= year_number(INJECTION_ONSET)
                ]
                raw_control_post = [
                    row for row in raw_control
                    if year_number(row["event_time"]) >= year_number(INJECTION_ONSET)
                ]
                freeze_injected_post = [
                    row for row in freeze_injected
                    if year_number(row["event_time"]) >= year_number(INJECTION_ONSET)
                ]
                freeze_control_post = [
                    row for row in control_freeze
                    if year_number(row["event_time"]) >= year_number(INJECTION_ONSET)
                ]

                raw_injected_alarm = _first_cusum_alarm(
                    raw_injected_post, onset=INJECTION_ONSET, h=confirmation_h
                )
                raw_control_alarm = _first_cusum_alarm(
                    raw_control_post, onset=INJECTION_ONSET, h=confirmation_h
                )
                freeze_injected_time = _first_freeze_trigger(
                    freeze_injected_post, onset=INJECTION_ONSET
                )
                freeze_control_time = _first_freeze_trigger(
                    freeze_control_post, onset=INJECTION_ONSET
                )

                if injected_diag["freeze_trigger_count"] and any(
                    year_number(row["event_time"]) < year_number(INJECTION_ONSET)
                    and row.get("freeze_trigger")
                    for row in freeze_injected
                ):
                    raise RuntimeError("confirmation_freeze_triggered_before_injection_onset")

                scenario = (
                    ("positive_" if direction > 0 else "negative_")
                    + str(magnitude) + "sigma"
                )
                injected_persistence = _paired_post_trigger_metrics(
                    raw_injected,
                    freeze_injected,
                    trigger_time=freeze_injected_time,
                    direction=direction,
                )
                control_persistence = _paired_post_trigger_metrics(
                    raw_control,
                    control_freeze,
                    trigger_time=freeze_control_time,
                    direction=direction,
                )
                injections[scenario].append({
                    "entity_id": entity_id,
                    "onset_time": INJECTION_ONSET,
                    "injection_scale": sigma,
                    "raw_injected_alarm": raw_injected_alarm is not None,
                    "raw_control_alarm": raw_control_alarm is not None,
                    "freeze_injected_trigger": freeze_injected_time is not None,
                    "freeze_control_trigger": freeze_control_time is not None,
                    "injected_alarm_time": (
                        raw_injected_alarm["event_time"] if raw_injected_alarm else None
                    ),
                    "injected_freeze_trigger_time": freeze_injected_time,
                    "control_alarm_time": (
                        raw_control_alarm["event_time"] if raw_control_alarm else None
                    ),
                    "control_freeze_trigger_time": freeze_control_time,
                    "injected_trigger_time_matches": (
                        None if raw_injected_alarm is None and freeze_injected_time is None
                        else bool(raw_injected_alarm and freeze_injected_time
                                  and raw_injected_alarm["event_time"] == freeze_injected_time)
                    ),
                    "control_trigger_time_matches": (
                        None if raw_control_alarm is None and freeze_control_time is None
                        else bool(raw_control_alarm and freeze_control_time
                                  and raw_control_alarm["event_time"] == freeze_control_time)
                    ),
                    "injected_persistence": injected_persistence,
                    "control_persistence": control_persistence,
                    "injected_freeze_release_count": injected_diag["freeze_release_count"],
                    "control_freeze_release_count": control_diag["freeze_release_count"],
                    "injected_freeze_active_fraction": injected_diag["freeze_active_fraction"],
                    "control_freeze_active_fraction": control_diag["freeze_active_fraction"],
                })

    scenario_summaries = {
        scenario: _summarize_scenario(rows, h=confirmation_h, scenario=scenario)
        for scenario, rows in injections.items()
    }
    return {
        "confirmation_h": confirmation_h,
        "cusum_k": CUSUM_K,
        "null_screen": null_screen,
        "passes_5pct_series_alarm_screen": passes,
        "null_screen_setting": setting_gate,
        "null_freeze_trigger_series_rate": (
            null_trigger_entities / len(historical_confirmation)
            if historical_confirmation else None
        ),
        "null_freeze_active_series_rate": (
            null_active_entities / len(historical_confirmation)
            if historical_confirmation else None
        ),
        "null_freeze_triggered_series": null_trigger_entities,
        "null_freeze_active_series": null_active_entities,
        "null_freeze_episodes": null_episode_count,
        "injection_eligible_series": len(raw_injection_rows),
        "injection_skipped": dict(skipped),
        "injections": scenario_summaries,
        "injection_records": {
            scenario: records for scenario, records in injections.items()
        },
        "decision": "candidate_requires_screen_and_positive_persistence_evidence" if passes else "rejected_by_5pct_series_alarm_screen",
    }


def _first_cusum_alarm(
    rows: Sequence[Mapping[str, Any]],
    *,
    onset: str,
    h: float,
) -> dict[str, Any] | None:
    hits = detect_two_sided_cusum(rows, k=CUSUM_K, h=h)
    return first_evidence_at_or_after(hits, onset)


def run_screen() -> dict[str, Any]:
    entity_series = _observed_series(read_world_bank())
    rolling_by_entity: dict[str, list[dict[str, Any]]] = {}
    for entity_id, observations in entity_series.items():
        rows, _ = build_policy_residuals(
            observations,
            policy="rolling_baseline_rolling_scale",
            time_unit="years",
        )
        rolling_by_entity[entity_id] = rows

    null_rows = [
        row
        for rows in rolling_by_entity.values()
        for row in _slice_years(rows, NULL_START, NULL_END)
    ]
    null_calibration = calibrate_prewhitened_null(
        null_rows,
        replicates=BOOTSTRAP_REPLICATES,
        seed=BOOTSTRAP_SEED,
        cusum_grid=CUSUM_GRID,
        p1_grid=(),
        min_segment_length=MIN_NULL_SEGMENT_LENGTH,
        min_series=MIN_SERIES_FOR_NULL,
    )
    passing_thresholds = {
        float(item["h"])
        for item in null_calibration.get("detectors", {}).get("cusum", [])
        if item.get("k") == CUSUM_K and item.get("passes_all_probabilities")
    }
    candidates = [
        _run_one_candidate(
            entity_series,
            rolling_by_entity,
            confirmation_h=h,
        )
        for h in sorted(passing_thresholds)
    ]

    decisions = []
    for item in candidates:
        scenario_deltas = [
            scenario.get("injected_mean_abs_z_gain_frozen_minus_rolling")
            for scenario in item["injections"].values()
            if scenario.get("injected_mean_abs_z_gain_frozen_minus_rolling") is not None
        ]
        ci_lowers = [
            scenario["injected_mean_abs_z_gain_ci95"][0]
            for scenario in item["injections"].values()
            if scenario.get("injected_mean_abs_z_gain_ci95") is not None
        ]
        positive_persistence = (
            bool(scenario_deltas)
            and statistics.mean(scenario_deltas) > 0
            and bool(ci_lowers)
            and statistics.mean(ci_lowers) > 0
        )
        item["positive_persistence_evidence"] = positive_persistence
        item["decision"] = (
            "eligible_for_further_operational_validation"
            if item["passes_5pct_series_alarm_screen"] and positive_persistence
            else "not_promoted"
        )
        decisions.append({
            "confirmation_h": item["confirmation_h"],
            "passes_5pct_series_alarm_screen": item["passes_5pct_series_alarm_screen"],
            "positive_persistence_evidence": positive_persistence,
            "decision": item["decision"],
        })

    return {
        "experiment": "domain_neutral_cusum_confirmation_freeze_screen_v1",
        "source": "World Bank FS.AST.PRVT.GD_ZS",
        "source_series": len(entity_series),
        "temporal_split": {
            "null_start": NULL_START,
            "null_end": NULL_END,
            "controlled_injection_onset": INJECTION_ONSET,
            "evaluation_end": DETECTION_END,
            "minimum_null_segment_length": MIN_NULL_SEGMENT_LENGTH,
            "detection_horizon_years": DETECTION_END - year_number(INJECTION_ONSET),
        },
        "baseline": {
            "rolling": "rolling_theil_sen_first_difference_mad",
            "confirmation": "same_rolling_reference_until_two_sided_cusum_alarm_then_freeze_baseline_keep_rolling_scale",
            "freeze_activation": "following_observation_after_confirmation_alarm",
            "release": "five consecutive observations with abs(z) <= 1.0",
        },
        "threshold_screen": {
            "cusum_k": CUSUM_K,
            "candidate_h": list(CONFIRMATION_H_GRID),
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "restart_probabilities": list(STATIONARY_BOOTSTRAP_P_GRID),
            "series_alarm_gate": "upper95 per-series alarm rate <= 5% at every restart probability",
            "null_interpretation": (
                "The World Bank window is unlabelled empirical history. The screen is "
                "a conservative candidate gate, not verified ground-truth false-alarm data."
            ),
            "calibration": null_calibration,
        },
        "candidates": candidates,
        "decisions": decisions,
        "promotion": "not_automatic",
        "final_interpretation": (
            "CUSUM confirmation is the alarm; baseline freezing is only the post-alarm "
            "control action. A candidate requires a 5% empirical series-level screen "
            "and positive paired post-trigger persistence evidence before any further "
            "operational validation. Detection recall is not attributed to freezing "
            "because the trigger alarm precedes the freeze."
        ),
    }


def main() -> None:
    report = run_screen()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "source_series": report["source_series"],
        "null_status": report["threshold_screen"]["calibration"].get("status"),
        "passing_confirmation_thresholds": [
            item["confirmation_h"] for item in report["candidates"]
        ],
        "decisions": report["decisions"],
        "promotion": report["promotion"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
