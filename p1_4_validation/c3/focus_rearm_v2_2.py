"""Isolated C3 v2.2 FOCuS re-arm calibration helper."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from p1_4_validation.injection_runner import focus_reset_rearm as legacy_focus_reset_rearm


def _numeric_values(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("FOCUS_SERIES_MUST_BE_NONEMPTY_1D")
    if not np.all(np.isfinite(array)):
        raise ValueError("FOCUS_SERIES_MUST_BE_FINITE")
    return array


def focus_reset_rearm_v2_2(
    values: Sequence[float],
    *,
    threshold: float,
    quiet_points: int = 40,
    rearm_quiet_points: int | None = None,
    rearm_scale_points: int | None = None,
    max_events: int = 12,
    min_series_length: int = 41,
    frequency: str | None = None,
) -> dict[str, Any]:
    """Separate short re-arm wait/location estimation from causal scale estimation.

    The dispersion window ends immediately before monitoring resumes. It is
    translated to the center estimated from the re-arm wait points, preserving
    its MAD while avoiding the noisy 4/5-observation scale estimate.
    """
    if rearm_scale_points is None:
        return legacy_focus_reset_rearm(
            values,
            threshold=threshold,
            quiet_points=quiet_points,
            rearm_quiet_points=rearm_quiet_points,
            max_events=max_events,
            min_series_length=min_series_length,
            frequency=frequency,
        )

    if frequency is not None:
        from p1_4_validation.injection_runner import focus_rearm_points_for_frequency
        cadence_points = focus_rearm_points_for_frequency(frequency)
        if rearm_quiet_points is not None and int(rearm_quiet_points) != cadence_points:
            raise ValueError("FOCUS_REARM_FREQUENCY_PARAMETER_MISMATCH")
        rearm_points = cadence_points
    else:
        rearm_points = 20 if rearm_quiet_points is None else int(rearm_quiet_points)

    x = _numeric_values(values)
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
    scale_points = int(rearm_scale_points)
    if scale_points < int(rearm_points) or scale_points < 3:
        raise ValueError("FOCUS_REARM_SCALE_WINDOW_TOO_SHORT")

    from p2_b_benchmark.p2c_engine import focus_detector

    hits = []
    intervals = []
    cursor = 0
    while len(hits) < int(max_events):
        if not hits:
            detector_values = x[cursor:]
            detector_quiet = int(quiet_points)
            map_global = lambda local_index: cursor + int(local_index)
        else:
            rearm_start = int(cursor)
            monitor_start = rearm_start + int(rearm_points)
            if monitor_start >= x.size:
                break
            scale_start = monitor_start - scale_points
            if scale_start < 0:
                raise ValueError("FOCUS_REARM_SCALE_HISTORY_UNAVAILABLE")

            rearm_values = x[rearm_start:monitor_start]
            scale_values = x[scale_start:monitor_start]
            if rearm_values.size != int(rearm_points):
                raise RuntimeError("FOCUS_REARM_WINDOW_INVALID")
            if scale_values.size != scale_points:
                raise RuntimeError("FOCUS_REARM_SCALE_WINDOW_INVALID")

            new_center = float(np.median(rearm_values))
            historical_center = float(np.median(scale_values))
            shifted_scale_reference = scale_values - historical_center + new_center
            detector_values = np.concatenate((
                shifted_scale_reference,
                x[monitor_start:],
            ))
            detector_quiet = scale_points
            intervals.append({
                "start_inclusive": rearm_start,
                "end_exclusive": monitor_start,
            })
            map_global = lambda local_index: monitor_start + (
                int(local_index) - scale_points
            )

        if detector_values.size <= detector_quiet:
            break
        result = focus_detector(
            detector_values,
            quiet_points=detector_quiet,
            threshold=float(threshold),
        )
        if result.get("status") == "ABSTAIN" or not result.get("hits"):
            break

        local = dict(result["hits"][0])
        local_index = int(local["detection_index"])
        if local_index < detector_quiet or local_index >= detector_values.size:
            raise RuntimeError("FOCUS_REARM_INDEX_INVALID")
        global_index = map_global(local_index)
        estimated_local = int(local.get("estimated_change_index", local_index))
        estimated_global = map_global(estimated_local)
        if not 0 <= global_index < x.size:
            raise RuntimeError("FOCUS_REARM_GLOBAL_INDEX_INVALID")

        hits.append({
            **local,
            "index": global_index,
            "detection_index": global_index,
            "estimated_change_index": estimated_global,
        })
        cursor = global_index + 1

    return {
        "status": "OK",
        "hits": hits,
        "event_count": len(hits),
        "rearm_intervals": intervals,
        "initial_calibration_observations": int(quiet_points),
        "rearm_calibration_observations": int(rearm_points),
        "rearm_scale_observations": scale_points,
        "rearm_scale_policy": "TRAILING_CAUSAL_SCALE_WINDOW_TRANSLATED_TO_REARM_CENTER",
    }
