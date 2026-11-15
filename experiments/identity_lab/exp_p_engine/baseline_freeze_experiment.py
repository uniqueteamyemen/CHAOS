"""Compare rolling, fixed, and suspicion-triggered frozen baselines.

All strategies use the same Theil-Sen baseline family and first-difference MAD
scale. The experiment separates the effect of freezing the expectation from
freezing the scale, and reports historical signal density separately from
controlled persistent-shift injection response.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from experiments.identity_lab.exp_p_engine.calibration_sweep import (
    read_usgs_monthly,
    read_world_bank,
)
from experiments.identity_lab.exp_p_engine.domain_neutral import (
    detect_sign_runs,
    detect_two_sided_cusum,
    false_alerts_per_1000_entity_year,
    first_difference_mad_scale,
    first_evidence_at_or_after,
    validate_residual_contract,
)

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT / "experiments" / "identity_lab" / "exp_p_engine"
    / "results" / "domain_neutral_baseline_freeze.json"
)

MIN_HISTORY = 8
BASELINE_WINDOW = 12
SCALE_WINDOW = 12
SUSPICION_Z = 2.0
RELEASE_Z = 1.0
RELEASE_RUN = 5
SUSPICION_RUN = 2
CUSUM_SETTINGS = (
    {"k": 0.50, "h": 8.5},
    {"k": 0.50, "h": 12.0},
    {"k": 1.00, "h": 16.0},
)
P1_SETTINGS = (
    {"threshold": 3.0, "run_length": 3},
    {"threshold": 3.5, "run_length": 4},
)

POLICIES = (
    "rolling_baseline_rolling_scale",
    "fixed_initial_baseline_fixed_scale",
    "suspicion_freeze_baseline_rolling_scale",
    "suspicion_freeze_baseline_and_scale",
)


def time_position(value: Any, unit: str) -> float:
    raw = str(value).strip()
    if unit == "years" and len(raw) == 4 and raw.isdigit():
        return float(int(raw))
    if unit == "months" and len(raw) >= 7 and raw[4] == "-":
        return float(int(raw[:4]) * 12 + int(raw[5:7]) - 1)
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if unit == "years":
        start = datetime(parsed.year, 1, 1, tzinfo=timezone.utc)
        end = datetime(parsed.year + 1, 1, 1, tzinfo=timezone.utc)
        return parsed.year + (parsed - start).total_seconds() / (end - start).total_seconds()
    if unit == "months":
        start = datetime(parsed.year, parsed.month, 1, tzinfo=timezone.utc)
        if parsed.month == 12:
            end = datetime(parsed.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(parsed.year, parsed.month + 1, 1, tzinfo=timezone.utc)
        return parsed.year * 12 + parsed.month - 1 + (parsed - start).total_seconds() / (end - start).total_seconds()
    raise ValueError("unsupported_time_unit:" + unit)


def fit_theil_sen(history: Sequence[Mapping[str, Any]], unit: str) -> tuple[float, float]:
    if len(history) < 4:
        raise ValueError("insufficient_theil_sen_history")
    x = [time_position(row["event_time"], unit) for row in history]
    y = [float(row["value"]) for row in history]
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(len(x))
        for j in range(i + 1, len(x))
        if x[j] > x[i]
    ]
    if not slopes:
        raise ValueError("theil_sen_time_unidentifiable")
    slope = median(slopes)
    intercept = median(y[i] - slope * x[i] for i in range(len(x)))
    return intercept, slope


def predict(model: tuple[float, float], event_time: Any, unit: str) -> float:
    intercept, slope = model
    return intercept + slope * time_position(event_time, unit)


def scale_from(history: Sequence[Mapping[str, Any]], unit: str) -> dict[str, Any]:
    return first_difference_mad_scale(
        history,
        time_unit=unit,
        estimate_rho=False,
        min_differences=4,
    )


def _result_row(
    source: Mapping[str, Any],
    *,
    expected: float,
    scale: float | None,
    status: str,
    baseline_id: str,
    baseline_method: str,
    support: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    observed = float(source["value"])
    residual = observed - expected
    ready = status == "ready" and scale is not None and math.isfinite(scale) and scale > 0
    row = {
        "entity_id": str(source["entity_id"]),
        "metric_id": str(source["metric_id"]),
        "event_time": source["event_time"],
        "observed_value": observed,
        "expected_value": expected,
        "residual": residual,
        "scale": float(scale) if scale is not None and math.isfinite(scale) and scale > 0 else None,
        "z_score": residual / float(scale) if ready else None,
        "status": "ready" if ready else status,
        "baseline_id": baseline_id,
        "baseline_method": baseline_method,
        "support_count": int(support),
        "unit": source.get("unit"),
        **dict(metadata),
    }
    return row


def build_policy_residuals(
    observations: Sequence[Mapping[str, Any]],
    *,
    policy: str,
    time_unit: str,
    baseline_window: int = BASELINE_WINDOW,
    scale_window: int = SCALE_WINDOW,
    min_history: int = MIN_HISTORY,
    suspicion_z: float = SUSPICION_Z,
    release_z: float = RELEASE_Z,
    release_run: int = RELEASE_RUN,
    suspicion_run: int = SUSPICION_RUN,
    freeze_trigger_after_time: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if policy not in POLICIES:
        raise ValueError("baseline_freeze_policy_unsupported")
    if baseline_window < min_history or scale_window < min_history or min_history < 4:
        raise ValueError("baseline_freeze_window_invalid")
    if suspicion_run < 1 or release_run < 1 or suspicion_z <= 0 or release_z <= 0:
        raise ValueError("baseline_freeze_trigger_or_release_invalid")
    trigger_after_position = (
        time_position(freeze_trigger_after_time, time_unit)
        if freeze_trigger_after_time is not None else None
    )
    identities = {(str(row["entity_id"]), str(row["metric_id"])) for row in observations}
    if len(identities) != 1:
        raise ValueError("baseline_freeze_requires_one_entity_metric")
    series = [
        row for row in observations
        if row.get("observation_status") == "observed" and row.get("value") is not None
    ]
    series.sort(key=lambda row: time_position(row["event_time"], time_unit))
    times = [time_position(row["event_time"], time_unit) for row in series]
    if len(set(times)) != len(times):
        raise ValueError("baseline_freeze_duplicate_time")

    entity_id, metric_id = next(iter(identities))
    baseline_id = (
        f"{metric_id}:{policy}:bw{baseline_window}:sw{scale_window}"
        f":trigger{suspicion_z:g}x{suspicion_run}:release{release_z:g}x{release_run}"
    )
    output: list[dict[str, Any]] = []
    frozen_model: tuple[float, float] | None = None
    frozen_scale: float | None = None
    frozen_support = 0
    frozen_at: str | None = None
    frozen_duration = 0
    freeze_episodes: list[dict[str, Any]] = []
    calm_run = 0
    current_episode: dict[str, Any] | None = None
    pending_model: tuple[float, float] | None = None
    pending_scale: float | None = None
    pending_support = 0
    pending_start_time: str | None = None
    pending_start_index: int | None = None
    pending_sign = 0
    pending_z: float | None = None
    pending_count = 0
    previous_time: float | None = None
    fixed_model: tuple[float, float] | None = None
    fixed_scale: float | None = None
    fixed_support = 0
    prequential_triggers = 0
    freeze_active_rows = 0
    releases = 0
    unresolved_gaps = 0

    for index in range(min_history, len(series)):
        source = series[index]
        event_time = source["event_time"]
        current_time = times[index]
        observation_gap = current_time - times[index - 1] if index > 0 else 1.0
        contiguous_start = index - 1
        while (
            contiguous_start > 0
            and times[contiguous_start] - times[contiguous_start - 1] <= 1.02
        ):
            contiguous_start -= 1
        contiguous_history = list(series[contiguous_start:index])
        history = contiguous_history[-baseline_window:]
        scale_history = contiguous_history[-scale_window:]

        if observation_gap > 1.02:
            fixed_model = None
            fixed_scale = None
            fixed_support = 0
            if frozen_model is not None:
                if current_episode is not None:
                    current_episode["ended_by"] = "unresolved_time_gap"
                    current_episode["end_time"] = event_time
                    freeze_episodes.append(current_episode)
                frozen_model = None
                frozen_scale = None
                frozen_support = 0
                frozen_at = None
                current_episode = None
                calm_run = 0
            pending_model = None
            pending_scale = None
            pending_support = 0
            pending_start_time = None
            pending_start_index = None
            pending_sign = 0
            pending_z = None
            pending_count = 0
            unresolved_gaps += 1
            output.append({
                "entity_id": entity_id,
                "metric_id": metric_id,
                "event_time": event_time,
                "observed_value": float(source["value"]),
                "expected_value": None,
                "residual": None,
                "scale": None,
                "z_score": None,
                "status": "gap_unresolved",
                "baseline_id": baseline_id,
                "baseline_method": policy,
                "support_count": len(history),
                "unit": source.get("unit"),
                "observation_gap_units": observation_gap,
                "freeze_active": False,
                "freeze_trigger": False,
                "freeze_released": False,
            })
            previous_time = current_time
            continue

        if len(history) < min_history:
            output.append({
                "entity_id": entity_id,
                "metric_id": metric_id,
                "event_time": event_time,
                "observed_value": float(source["value"]),
                "expected_value": None,
                "residual": None,
                "scale": None,
                "z_score": None,
                "status": "scale_unavailable",
                "baseline_id": baseline_id,
                "baseline_method": policy,
                "support_count": len(history),
                "unit": source.get("unit"),
                "observation_gap_units": observation_gap,
                "freeze_active": False,
                "freeze_trigger": False,
                "freeze_released": False,
                "reason": "insufficient_contiguous_history_after_gap",
            })
            previous_time = current_time
            continue

        if policy == "fixed_initial_baseline_fixed_scale":
            if index < baseline_window:
                output.append({
                    "entity_id": entity_id,
                    "metric_id": metric_id,
                    "event_time": event_time,
                    "observed_value": float(source["value"]),
                    "expected_value": None,
                    "residual": None,
                    "scale": None,
                    "z_score": None,
                    "status": "scale_unavailable",
                    "baseline_id": baseline_id,
                    "baseline_method": policy,
                    "support_count": len(history),
                    "unit": source.get("unit"),
                    "observation_gap_units": observation_gap,
                    "freeze_active": True,
                    "freeze_trigger": False,
                    "freeze_released": False,
                    "reason": "fixed_baseline_requires_full_initial_window",
                })
                previous_time = current_time
                continue
            if fixed_model is None:
                anchor = list(history[:baseline_window])
                fixed_model = fit_theil_sen(anchor, time_unit)
                fixed_scale_result = scale_from(anchor, time_unit)
                fixed_scale = fixed_scale_result["value"]
                fixed_support = len(anchor)
            model = fixed_model
            scale_result = {"value": fixed_scale, "method": "fixed_initial_first_difference_mad"}
            support = fixed_support
            frozen_now = True
        elif policy.startswith("suspicion_freeze") and frozen_model is not None:
            model = frozen_model
            support = frozen_support
            if policy == "suspicion_freeze_baseline_and_scale":
                scale_result = {
                    "value": frozen_scale,
                    "method": "frozen_first_difference_mad",
                }
            else:
                scale_result = scale_from(scale_history, time_unit)
            frozen_now = True
        else:
            model = fit_theil_sen(history, time_unit)
            scale_result = scale_from(scale_history, time_unit)
            support = len(history)
            frozen_now = False

        expected = predict(model, event_time, time_unit)
        scale = scale_result.get("value")
        residual = float(source["value"]) - expected
        z = residual / float(scale) if scale is not None and float(scale) > 0 else None
        freeze_trigger = False
        freeze_released = False

        suspicion_pending = False
        if policy.startswith("suspicion_freeze") and frozen_model is None:
            trigger_enabled = (
                trigger_after_position is None
                or current_time >= trigger_after_position
            )
            if not trigger_enabled:
                pending_model = None
                pending_scale = None
                pending_support = 0
                pending_start_time = None
                pending_start_index = None
                pending_sign = 0
                pending_z = None
                pending_count = 0
            else:
                current_sign = 1 if z is not None and z >= suspicion_z else (
                    -1 if z is not None and z <= -suspicion_z else 0
                )
                if current_sign == 0:
                    pending_model = None
                    pending_scale = None
                    pending_support = 0
                    pending_start_time = None
                    pending_start_index = None
                    pending_sign = 0
                    pending_z = None
                    pending_count = 0
                elif (
                    pending_count > 0
                    and current_sign == pending_sign
                    and pending_start_index is not None
                    and index == pending_start_index + pending_count
                ):
                    pending_count += 1
                    suspicion_pending = pending_count < suspicion_run
                else:
                    pending_model = model
                    pending_scale = float(scale) if scale is not None and float(scale) > 0 else None
                    pending_support = support
                    pending_start_time = str(event_time)
                    pending_start_index = index
                    pending_sign = current_sign
                    pending_z = z
                    pending_count = 1
                    suspicion_pending = pending_count < suspicion_run

                if pending_count >= suspicion_run and pending_model is not None:
                    frozen_model = pending_model
                    frozen_scale = pending_scale
                    frozen_support = pending_support
                    frozen_at = pending_start_time
                    frozen_duration = 0
                    calm_run = 0
                    freeze_trigger = True
                    frozen_now = True
                    model = frozen_model
                    support = frozen_support
                    if policy == "suspicion_freeze_baseline_and_scale":
                        scale_result = {
                            "value": frozen_scale,
                            "method": "frozen_first_difference_mad",
                        }
                        scale = frozen_scale
                    expected = predict(model, event_time, time_unit)
                    residual = float(source["value"]) - expected
                    z = residual / float(scale) if scale is not None and float(scale) > 0 else None
                    prequential_triggers += 1
                    current_episode = {
                        "start_time": frozen_at,
                        "confirmation_time": str(event_time),
                        "start_index": pending_start_index,
                        "trigger_z": pending_z,
                        "confirmation_z": z,
                        "trigger_run": suspicion_run,
                        "frozen_scale": frozen_scale,
                        "support_count": frozen_support,
                        "policy": policy,
                    }
                    pending_model = None
                    pending_scale = None
                    pending_support = 0
                    pending_start_time = None
                    pending_start_index = None
                    pending_sign = 0
                    pending_z = None
                    pending_count = 0

        if frozen_now:
            freeze_active_rows += 1
            if current_episode is not None:
                frozen_duration += 1
                current_episode["duration_observations"] = frozen_duration
                current_episode["last_z"] = z
            if (
                policy.startswith("suspicion_freeze")
                and not freeze_trigger
                and z is not None
                and abs(z) <= release_z
            ):
                calm_run += 1
            elif z is not None and abs(z) > release_z:
                calm_run = 0
            if (
                policy.startswith("suspicion_freeze")
                and not freeze_trigger
                and calm_run >= release_run
            ):
                freeze_released = True
                releases += 1
                if current_episode is not None:
                    current_episode["ended_by"] = "confirmed_return_to_frozen_baseline"
                    current_episode["end_time"] = str(event_time)
                    freeze_episodes.append(current_episode)
                frozen_model = None
                frozen_scale = None
                frozen_support = 0
                frozen_at = None
                current_episode = None
                frozen_duration = 0
                calm_run = 0

        status = "ready" if z is not None and scale is not None and float(scale) > 0 else "scale_unavailable"
        row = _result_row(
            source,
            expected=expected,
            scale=float(scale) if scale is not None else None,
            status=status,
            baseline_id=baseline_id,
            baseline_method=policy,
            support=support,
            metadata={
                "scale_method": scale_result.get("method"),
                "observation_gap_units": observation_gap,
                "freeze_active": frozen_now,
                "freeze_trigger": freeze_trigger,
                "freeze_released": freeze_released,
                "frozen_at": frozen_at if frozen_now else None,
                "calm_run": calm_run,
                "suspicion_pending": suspicion_pending,
                "suspicion_run_required": suspicion_run,
            },
        )
        output.append(row)
        previous_time = current_time

    if current_episode is not None:
        current_episode["ended_by"] = "series_end"
        current_episode["end_time"] = str(series[-1]["event_time"])
        freeze_episodes.append(current_episode)

    validate_residual_contract(output)
    diagnostics = {
        "entity_id": entity_id,
        "policy": policy,
        "observations": len(series),
        "residual_rows": len(output),
        "ready_rows": sum(1 for row in output if row["status"] == "ready"),
        "gap_unresolved_rows": unresolved_gaps,
        "freeze_trigger_count": prequential_triggers,
        "freeze_release_count": releases,
        "suspicion_run_required": suspicion_run,
        "freeze_active_rows": freeze_active_rows,
        "freeze_active_fraction": freeze_active_rows / len(output) if output else 0.0,
        "freeze_episodes": freeze_episodes,
        "first_freeze_time": freeze_episodes[0]["start_time"] if freeze_episodes else None,
        "baseline_id": baseline_id,
    }
    return output, diagnostics


def _injection_copy(
    series: Sequence[Mapping[str, Any]],
    *,
    magnitude_sigma: float,
    direction: int,
    time_unit: str,
) -> tuple[list[dict[str, Any]] | None, str | None, float | None, int | None]:
    observed = [
        dict(row) for row in series
        if row.get("observation_status") == "observed" and row.get("value") is not None
    ]
    observed.sort(key=lambda row: time_position(row["event_time"], time_unit))
    if len(observed) < 14:
        return None, None, None, None
    target_index = min(max(MIN_HISTORY + 2, int(len(observed) * 0.65)), len(observed) - 3)
    valid_onsets = []
    for candidate in range(target_index, len(observed) - 2):
        start = candidate - 1
        while start > 0:
            gap = (
                time_position(observed[start]["event_time"], time_unit)
                - time_position(observed[start - 1]["event_time"], time_unit)
            )
            if gap > 1.02:
                break
            start -= 1
        history = observed[max(start, candidate - SCALE_WINDOW):candidate]
        if len(history) >= MIN_HISTORY:
            valid_onsets.append((candidate, history))
            break
    if not valid_onsets:
        return None, None, None, None
    onset_index, pre_onset = valid_onsets[0]
    scale = scale_from(pre_onset, time_unit).get("value")
    if scale is None or float(scale) <= 0:
        return None, None, None, None
    delta = direction * magnitude_sigma * float(scale)
    for row in observed[onset_index:]:
        row["value"] = float(row["value"]) + delta
    return observed, str(observed[onset_index]["event_time"]), float(scale), onset_index


def _detector_response(
    residuals: Sequence[Mapping[str, Any]],
    *,
    onset: str,
    unit: str,
) -> dict[str, Any]:
    # Reset at the labelled onset to isolate detector sensitivity. Historical
    # false-alarm behavior is measured separately on the uninjected series.
    post_onset = [row for row in residuals if time_position(row["event_time"], unit) >= time_position(onset, unit)]
    cusum_results = []
    for params in CUSUM_SETTINGS:
        hits = detect_two_sided_cusum(post_onset, k=params["k"], h=params["h"])
        first = first_evidence_at_or_after(hits, onset)
        delay = (
            time_position(first["event_time"], unit) - time_position(onset, unit)
            if first else None
        )
        cusum_results.append({
            **params,
            "detected": first is not None,
            "direction": first["direction"] if first else None,
            "first_evidence_time": first["event_time"] if first else None,
            "delay_time_units": delay,
        })
    p1_results = []
    for params in P1_SETTINGS:
        hits = detect_sign_runs(post_onset, threshold=params["threshold"], run_length=params["run_length"])
        first = first_evidence_at_or_after(hits, onset)
        delay = (
            time_position(first["event_time"], unit) - time_position(onset, unit)
            if first else None
        )
        p1_results.append({
            **params,
            "detected": first is not None,
            "direction": first["direction"] if first else None,
            "first_evidence_time": first["event_time"] if first else None,
            "delay_time_units": delay,
        })
    return {
        "cusum": cusum_results,
        "sign_run": p1_results,
        "post_onset_reset": True,
        "interpretation": "sensitivity from labelled onset with detector state reset; not continuous-operation alert rate",
    }


def run_experiment(
    source_name: str,
    source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    time_unit: str,
    suspicion_z: float = SUSPICION_Z,
    suspicion_run: int = 1,
    policy_filter: Sequence[str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": source_name,
        "time_unit": time_unit,
        "entity_count": len(source),
        "suspicion_z": suspicion_z,
        "suspicion_run": suspicion_run,
        "policies": {},
    }
    selected_policies = list(policy_filter) if policy_filter is not None else list(POLICIES)
    for policy in selected_policies:
        historical_profiles = []
        historical_residuals: list[dict[str, Any]] = []
        freeze_episode_count = 0
        frozen_entities = 0
        pre_injection_results: dict[str, list[dict[str, Any]]] = defaultdict(list)
        tested_series = 0
        skipped_series = 0
        for entity_id, series in source.items():
            observed = [
                row for row in series
                if row.get("observation_status") == "observed" and row.get("value") is not None
            ]
            if len(observed) < 14:
                skipped_series += 1
                continue
            residuals, diagnostics = build_policy_residuals(
                observed,
                policy=policy,
                time_unit=time_unit,
                suspicion_z=suspicion_z,
                suspicion_run=suspicion_run,
            )
            tested_series += 1
            historical_residuals.extend(residuals)
            freeze_episode_count += diagnostics["freeze_trigger_count"]
            frozen_entities += int(diagnostics["freeze_trigger_count"] > 0)
            cusum_hits = []
            p1_hits = []
            for params in CUSUM_SETTINGS:
                cusum_hits.extend(detect_two_sided_cusum(residuals, k=params["k"], h=params["h"]))
            for params in P1_SETTINGS:
                p1_hits.extend(detect_sign_runs(residuals, threshold=params["threshold"], run_length=params["run_length"]))
            historical_profiles.append({
                "entity_id": entity_id,
                "ready_rows": diagnostics["ready_rows"],
                "freeze_trigger_count": diagnostics["freeze_trigger_count"],
                "freeze_active_fraction": diagnostics["freeze_active_fraction"],
                "cusum_hits_grid_total": len(cusum_hits),
                "sign_run_hits_grid_total": len(p1_hits),
            })

            for magnitude in (3.0, 6.0):
                for direction in (-1, 1):
                    injected, onset, injection_scale, onset_index = _injection_copy(
                        observed,
                        magnitude_sigma=magnitude,
                        direction=direction,
                        time_unit=time_unit,
                    )
                    if injected is None or onset is None:
                        continue
                    injected_residuals, injected_diagnostics = build_policy_residuals(
                        injected,
                        policy=policy,
                        time_unit=time_unit,
                        suspicion_z=suspicion_z,
                        suspicion_run=suspicion_run,
                        freeze_trigger_after_time=onset,
                    )
                    response = _detector_response(
                        injected_residuals,
                        onset=onset,
                        unit=time_unit,
                    )
                    freeze_times = [
                        item["start_time"]
                        for item in injected_diagnostics["freeze_episodes"]
                    ]
                    freeze_before = [
                        value for value in freeze_times
                        if time_position(value, time_unit) < time_position(onset, time_unit)
                    ]
                    freeze_after = [
                        value for value in freeze_times
                        if time_position(value, time_unit) >= time_position(onset, time_unit)
                    ]
                    key = (
                        f"{'positive' if direction > 0 else 'negative'}_"
                        f"{magnitude:g}sigma"
                    )
                    pre_injection_results[key].append({
                        "entity_id": entity_id,
                        "onset_time": onset,
                        "injection_scale": injection_scale,
                        "freeze_before_injection": bool(freeze_before),
                        "freeze_time_before_injection": freeze_before[0] if freeze_before else None,
                        "freeze_time_after_injection": freeze_after[0] if freeze_after else None,
                        "freeze_episodes": injected_diagnostics["freeze_trigger_count"],
                        "cusum": response["cusum"],
                        "sign_run": response["sign_run"],
                    })

        # Historical hits are unlabelled; report density rather than a false-positive claim.
        cusum_summary = []
        for params in CUSUM_SETTINGS:
            total_hits = 0
            ready_exposure = 0
            entities_with_hit = 0
            for entity_id, series in source.items():
                observed = [
                    row for row in series
                    if row.get("observation_status") == "observed" and row.get("value") is not None
                ]
                if len(observed) < 14:
                    continue
                rows, _ = build_policy_residuals(
                    observed, policy=policy, time_unit=time_unit,
                    suspicion_z=suspicion_z, suspicion_run=suspicion_run,
                )
                hits = detect_two_sided_cusum(rows, k=params["k"], h=params["h"])
                total_hits += len(hits)
                ready_exposure += sum(1 for row in rows if row["status"] == "ready")
                entities_with_hit += int(bool(hits))
            cusum_summary.append({
                **params,
                "historical_raw_hits": total_hits,
                "ready_residual_exposure": ready_exposure,
                "signals_per_1000_ready_residuals": (
                    1000.0 * total_hits / ready_exposure if ready_exposure else None
                ),
                "entities_with_any_hit": entities_with_hit,
                "share_entities_with_any_hit": entities_with_hit / tested_series if tested_series else None,
            })

        injection_summary: dict[str, Any] = {}
        for scenario, rows in pre_injection_results.items():
            item_result: dict[str, Any] = {"eligible_series": len(rows)}
            for detector in ("cusum", "sign_run"):
                settings = CUSUM_SETTINGS if detector == "cusum" else P1_SETTINGS
                summaries = []
                for params in settings:
                    matches = [
                        hit
                        for row in rows
                        for hit in row[detector]
                        if all(hit.get(key) == value for key, value in params.items())
                    ]
                    detected = [hit for hit in matches if hit["detected"]]
                    delays = [hit["delay_time_units"] for hit in detected if hit["delay_time_units"] is not None]
                    direction = "positive" if scenario.startswith("positive") else "negative"
                    matching_direction = sum(1 for hit in detected if hit["direction"] == direction)
                    within_3 = sum(1 for hit in detected if hit["delay_time_units"] is not None and hit["delay_time_units"] <= 3.0)
                    summaries.append({
                        **params,
                        "tested_injections": len(rows),
                        "detected_injections": len(detected),
                        "recall": len(detected) / len(rows) if rows else None,
                        "direction_matches": matching_direction,
                        "median_detection_delay_time_units": median(delays) if delays else None,
                        "detected_within_3_time_units": within_3,
                        "recall_within_3_time_units": within_3 / len(rows) if rows else None,
                    })
                item_result[detector] = summaries
            item_result["freeze_before_injection_series"] = sum(
                1 for row in rows if row["freeze_before_injection"]
            )
            item_result["freeze_after_injection_series"] = sum(
                1 for row in rows if row["freeze_time_after_injection"] is not None
            )
            injection_summary[scenario] = item_result

        result["policies"][policy] = {
            "tested_series": tested_series,
            "skipped_series": skipped_series,
            "historical_freeze_triggered_entities": frozen_entities,
            "historical_freeze_episodes": freeze_episode_count,
            "historical_profile": historical_profiles,
            "historical_signal_density": {
                "cusum": cusum_summary,
            },
            "controlled_persistent_shift_injections": injection_summary,
            "interpretation": (
                "Historical hits are unlabelled signal density, not verified false alarms. "
                "Injection sensitivity resets detector state at the known onset to isolate "
                "post-onset response; this is not continuous-operation FPR."
            ),
        }
    return result


def main() -> None:
    world_bank_source = read_world_bank()
    freeze_policies = (
        "suspicion_freeze_baseline_rolling_scale",
        "suspicion_freeze_baseline_and_scale",
    )
    world_bank_trigger_sweep: dict[str, Any] = {}
    for trigger_z in (2.0, 3.0, 4.0, 6.0):
        trigger_key = f"z{trigger_z:g}_same_direction_run2"
        trigger_result = run_experiment(
            "World Bank domestic credit to private sector (% GDP)",
            world_bank_source,
            time_unit="years",
            suspicion_z=trigger_z,
            suspicion_run=2,
            policy_filter=freeze_policies,
        )
        world_bank_trigger_sweep[trigger_key] = trigger_result["policies"]

    report = {
        "experiment": "domain_neutral_baseline_freeze_comparison_v1",
        "policies": list(POLICIES),
        "trigger_sweep": {
            "same_direction_consecutive_evidence": True,
            "trigger_run": 2,
            "tested_z_thresholds": [2.0, 3.0, 4.0, 6.0],
            "world_bank": world_bank_trigger_sweep,
            "interpretation": "A freeze candidate is confirmed only after two contiguous same-direction residuals exceed the threshold; the frozen model is snapshotted from the first candidate.",
        },
        "parameters": {
            "baseline_window": BASELINE_WINDOW,
            "scale_window": SCALE_WINDOW,
            "min_history": MIN_HISTORY,
            "suspicion_z": SUSPICION_Z,
            "release_z": RELEASE_Z,
            "release_run": RELEASE_RUN,
            "suspicion_run": SUSPICION_RUN,
            "cusum_settings": list(CUSUM_SETTINGS),
            "p1_settings": list(P1_SETTINGS),
        },
        "world_bank": run_experiment(
            "World Bank domestic credit to private sector (% GDP)",
            world_bank_source,
            time_unit="years",
            suspicion_z=SUSPICION_Z,
            suspicion_run=SUSPICION_RUN,
        ),
        "usgs": run_experiment(
            "USGS global M6.5+ monthly event counts",
            read_usgs_monthly(),
            time_unit="months",
            suspicion_z=SUSPICION_Z,
            suspicion_run=SUSPICION_RUN,
        ),
        "promotion": "not_automatic",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {}
    for source_key in ("world_bank", "usgs"):
        compact[source_key] = {}
        for policy, block in report[source_key]["policies"].items():
            compact[source_key][policy] = {
                "tested_series": block["tested_series"],
                "historical_freeze_triggered_entities": block["historical_freeze_triggered_entities"],
                "historical_cusum_signal_density": block["historical_signal_density"]["cusum"],
                "injections": block["controlled_persistent_shift_injections"],
            }
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)),
        "summary": compact,
        "promotion": "not_automatic",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
