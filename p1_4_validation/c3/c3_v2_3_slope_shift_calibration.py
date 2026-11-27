from __future__ import annotations
import hashlib
import json
from typing import Any
import numpy as np
from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.causal_local_slope_shift import CausalLocalSlopeShiftDetector

PROTOCOL_PATH = "p1_4_validation/c3/c3_v2_3_slope_shift_preregistration.json"
SLOPE_DETECTOR = "Causal Local Slope-Shift"
HUBER_MAD = "Post-Quiet Huber + MAD"
HUBER_BARTLETT = "Post-Quiet Huber + Bartlett LRV"
DETECTORS = (SLOPE_DETECTOR, HUBER_MAD, HUBER_BARTLETT)
MIN_VALID_FRACTION = 0.95

def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        c3.clean(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8") + b"\n"


def _valid_scores(values: list[float | None]) -> list[float]:
    return [float(value) for value in values
            if value is not None and np.isfinite(float(value))]


def select_dev_threshold(
    scores: list[float | None], threshold_grid: list[float],
    *, target_u95: float, min_valid: int,
) -> dict[str, Any]:
    """Select the lowest pre-registered threshold on Development only."""
    valid = _valid_scores(scores)
    if len(valid) < min_valid:
        return {
            "status": "INCONCLUSIVE",
            "reason": "INSUFFICIENT_VALID_DEVELOPMENT_REPLICATES",
            "valid_replicates": len(valid),
            "frozen_threshold": None,
            "grid": [],
        }
    rows = []
    for raw_threshold in sorted({float(v) for v in threshold_grid}):
        threshold = float(raw_threshold)
        alarms = sum(value >= threshold for value in valid)
        stats = c3.wilson_stats(alarms, len(valid))
        row = {"threshold": threshold, **stats, "p0_target": float(target_u95)}
        rows.append(row)
        upper = stats["wilson_upper_95_one_sided"]
        if upper is not None and upper <= float(target_u95):
            return {
                "status": "CALIBRATED",
                "frozen_threshold": threshold,
                "development": row,
                "grid": rows,
                "selection_rule": "lowest pre-registered threshold with Development Wilson U95 <= gate",
            }
    return {
        "status": "NOT_CALIBRATABLE",
        "reason": "NO_PREDECLARED_THRESHOLD_MET_DEVELOPMENT_WILSON_GATE",
        "valid_replicates": len(valid),
        "frozen_threshold": None,
        "development": rows[-1] if rows else {},
        "grid": rows,
    }


def evaluate_holdout(
    scores: list[float | None], frozen_threshold: float | None,
    *, target_u95: float, min_valid: int,
) -> dict[str, Any]:
    """Evaluate one frozen threshold once; never select or retune on Holdout."""
    if frozen_threshold is None:
        return {
            "status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD",
            "evaluated": False,
            "holdout_retuning": False,
        }
    valid = _valid_scores(scores)
    alarms = sum(value >= float(frozen_threshold) for value in valid)
    stats = c3.wilson_stats(alarms, len(valid))
    if len(valid) < min_valid:
        status = "INCONCLUSIVE"
    elif stats["wilson_upper_95_one_sided"] <= float(target_u95):
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "evaluated": True,
        **stats,
        "holdout_retuning": False,
        "frozen_threshold": float(frozen_threshold),
    }


def _detector_for_protocol(
    protocol: dict, series_id: str,
) -> CausalLocalSlopeShiftDetector:
    config = protocol["detectors"][SLOPE_DETECTOR]["parameters_by_series"][series_id]
    return CausalLocalSlopeShiftDetector(**config)


def _score_null_trace(
    trace: np.ndarray, detector: CausalLocalSlopeShiftDetector,
) -> dict[str, float | None]:
    local = detector.score_trace(trace)
    slope_score = local.get("max_confirmed_score") if local.get("status") == "OK" else None
    mad_score = c3.huber_max_statistic(trace, "mad")
    bartlett_score = c3.huber_max_statistic(trace, "bartlett")
    return {
        SLOPE_DETECTOR: float(slope_score) if slope_score is not None else None,
        HUBER_MAD: float(mad_score) if mad_score is not None else None,
        HUBER_BARTLETT: float(bartlett_score) if bartlett_score is not None else None,
    }


def _generate_phase_scores(
    *, series_id: str, values: np.ndarray, tape_sha: str, model: dict,
    phase: str, replicates: int, seed_namespace: str,
    detector: CausalLocalSlopeShiftDetector,
) -> tuple[dict[str, list[float | None]], str, list[int]]:
    scores = {name: [] for name in DETECTORS}
    seed_material: list[str] = []
    seeds: list[int] = []
    for replicate in range(int(replicates)):
        seed = c3.deterministic_seed(
            tape_sha, series_id, int(model["order"]), phase, replicate,
            namespace=seed_namespace,
        )
        seeds.append(int(seed))
        seed_material.append(f"{phase}:{replicate}:{seed}")
        trace = c3.generate_ar_null_trace(
            model, values[:c3.QUIET_POINTS], int(values.size), int(seed)
        )
        row_scores = _score_null_trace(trace, detector)
        for name in DETECTORS:
            scores[name].append(row_scores[name])
        if (replicate + 1) % 250 == 0:
            print(
                "C3_V2_3_NULL_PROGRESS "
                f"series={series_id} phase={phase} completed={replicate + 1}/{replicates}",
                flush=True,
            )
    return scores, _sha256("\n".join(seed_material).encode("utf-8")), seeds
