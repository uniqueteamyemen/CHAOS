from __future__ import annotations
from typing import Any
import numpy as np
from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.causal_local_slope_shift import CausalLocalSlopeShiftDetector
from p1_4_validation.c3.c3_v2_3_slope_shift_calibration import (
    SLOPE_DETECTOR, HUBER_MAD, HUBER_BARTLETT, DETECTORS,
    _detector_for_protocol,
)

def _slope_prefix_replay(
    detector: CausalLocalSlopeShiftDetector, values: np.ndarray,
    hits: list[dict], threshold: float,
) -> int:
    for hit in hits:
        index = int(hit["index"])
        prefix = detector.detect(values[:index + 1], threshold=threshold)
        if prefix.get("status") != "OK" or not any(
            int(row["index"]) == index and int(row["sign"]) == int(hit["sign"])
            for row in prefix.get("hits", [])
        ):
            raise ValueError(f"C3_V2_3_SLOPE_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{index}")
    return len(hits)


def _huber_prefix_replay(
    detector_name: str, values: np.ndarray, hits: list[dict], threshold: float,
) -> int:
    for hit in hits:
        index = int(hit["index"])
        prefix_hits, status, _meta = c3.extract_detector_hits(
            detector_name, values[:index + 1], threshold=float(threshold)
        )
        if status in {"ABSTAIN", "NOT_ELIGIBLE"} or not any(
            int(row["index"]) == index and int(row["sign"]) == int(hit["sign"])
            for row in prefix_hits
        ):
            raise ValueError(
                f"C3_V2_3_HUBER_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{detector_name}:{index}"
            )
    return len(hits)


def _historical_for_series(
    *, rows: list[dict], values: np.ndarray, events: list[dict],
    calibrated: dict[str, dict], protocol: dict,
) -> tuple[list[dict], dict[str, dict]]:
    output_rows: list[dict] = []
    unmatched_summaries: dict[str, dict] = {}
    series_id = str(rows[0]["series_id"])
    slope_detector = _detector_for_protocol(protocol, series_id)

    for detector_name in DETECTORS:
        arm = calibrated[detector_name]
        threshold = arm.get("frozen_threshold")
        if threshold is None:
            hits: list[dict] = []
            detector_status = "ABSTAIN"
            detector_metadata = {"reason": "NO_DEVELOPMENT_CALIBRATED_THRESHOLD"}
            replayed = 0
        elif detector_name == SLOPE_DETECTOR:
            result = slope_detector.detect(values, threshold=float(threshold))
            detector_status = str(result.get("status", "OK"))
            hits = [
                {"index": int(hit["index"]), "sign": int(hit["sign"]),
                 "score": float(hit["score"])}
                for hit in result.get("hits", [])
            ]
            detector_metadata = {
                key: result.get(key) for key in (
                    "window_points", "initial_quiet_points", "confirm_points", "rearm_quiet_points",
                    "rearm_ratio", "max_confirmed_score", "scale_source_counts",
                    "zero_scale_points", "score_definition", "causal_policy",
                )
            }
            replayed = _slope_prefix_replay(slope_detector, values, hits, float(threshold)) if hits else 0
        else:
            hits, detector_status, detector_metadata = c3.extract_detector_hits(
                detector_name, values, threshold=float(threshold)
            )
            replayed = _huber_prefix_replay(
                detector_name, values, hits, float(threshold)
            ) if hits else 0

        detector_metadata = dict(detector_metadata or {})
        detector_metadata["all_hits"] = [
            {
                "index": int(hit["index"]),
                "available_at": rows[int(hit["index"])]["available_at"],
                "sign": int(hit["sign"]),
                "score": hit.get("score"),
            }
            for hit in hits
        ]
        matched_rows, unmatched = c3.match_events_one_to_one(
            rows, events, hits, detector_name
        )
        unmatched["detector_status"] = detector_status
        unmatched["detector_metadata"] = c3.clean(detector_metadata)
        unmatched["no_lookahead_prefix_replays"] = int(replayed)
        unmatched_summaries[detector_name] = unmatched

        for row in matched_rows:
            output_rows.append({
                **row,
                "validation_status": arm.get("risk_validation_status", "ABSTAINED"),
                "frozen_threshold": threshold,
                "development_p0": arm.get("development", {}).get("p0"),
                "development_wilson_u95": arm.get("development", {}).get("wilson_upper_95_one_sided"),
                "holdout_p0": arm.get("holdout", {}).get("p0"),
                "holdout_wilson_u95": arm.get("holdout", {}).get("wilson_upper_95_one_sided"),
                "detector_status": detector_status,
                "no_lookahead_prefix_replays": int(replayed),
                "unmatched_alarm_count_for_series_detector": unmatched["unmatched_alarm_count"],
            })
    return output_rows, unmatched_summaries
