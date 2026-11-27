from __future__ import annotations
import numpy as np
from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.c3_v2_3_slope_shift_calibration import (
    DETECTORS, _detector_for_protocol, _generate_phase_scores,
    select_dev_threshold, evaluate_holdout, _valid_scores,
)
from p1_4_validation.c3.c3_v2_3_slope_shift_replay import _historical_for_series


def evaluate_series(*, series_id, rows, contract_events, manifest, protocol, replicates, min_valid):
    values = np.asarray([row["value_float"] for row in rows], dtype=float)
    if values.size <= c3.QUIET_POINTS:
        raise ValueError(f"C3_V2_3_SERIES_TOO_SHORT:{series_id}")
    available = [row["available_at_obj"] for row in rows]
    if any(available[i] < available[i - 1] for i in range(1, len(available))):
        raise ValueError(f"C3_V2_3_NON_MONOTONIC_AVAILABLE_AT:{series_id}")
    model = c3.select_ar_model(values[:c3.QUIET_POINTS])
    if model.get("status") != "OK":
        return ({"status": "ABSTAINED_AR_MODEL_NOT_ELIGIBLE",
                 "ar_model_reason": model.get("reason"),
                 "observation_count": int(values.size)}, [], {})

    phase_scores, seed_ranges = {}, {}
    detector_template = _detector_for_protocol(protocol, series_id)
    for phase in ("development", "holdout"):
        scores, ledger_sha, seeds = _generate_phase_scores(
            series_id=series_id, values=values,
            tape_sha=manifest["normalized_tape"]["sha256"], model=model,
            phase=phase, replicates=replicates,
            seed_namespace=protocol["null_protocol"]["seed_namespace"],
            detector=detector_template,
        )
        phase_scores[phase] = scores
        seed_ranges[phase] = {
            "replicate_count": len(seeds),
            "first_seed": seeds[0] if seeds else None,
            "last_seed": seeds[-1] if seeds else None,
            "seed_ledger_sha256": ledger_sha,
        }

    calibration = {}
    for detector_name in DETECTORS:
        config = protocol["detectors"][detector_name]
        dev = select_dev_threshold(
            phase_scores["development"][detector_name], config["threshold_grid"],
            target_u95=float(protocol["risk_gates"]["development_wilson_u95_max"]),
            min_valid=min_valid,
        )
        frozen = dev.get("frozen_threshold")
        hold = evaluate_holdout(
            phase_scores["holdout"][detector_name], frozen,
            target_u95=float(protocol["risk_gates"]["holdout_wilson_u95_max"]),
            min_valid=min_valid,
        )
        risk = ("NOT_CALIBRATABLE_OR_INCONCLUSIVE" if dev.get("status") != "CALIBRATED"
                else "VALIDATED" if hold.get("status") == "PASS"
                else "NOT_VALIDATED" if hold.get("status") == "FAIL" else "INCONCLUSIVE")
        calibration[detector_name] = {
            "development": dev.get("development", {}),
            "development_status": dev.get("status"),
            "development_valid_replicates": len(_valid_scores(phase_scores["development"][detector_name])),
            "holdout": hold,
            "holdout_valid_replicates": len(_valid_scores(phase_scores["holdout"][detector_name])),
            "frozen_threshold": frozen,
            "threshold_grid": config["threshold_grid"],
            "risk_validation_status": risk,
            "development_grid": dev.get("grid", []),
            "holdout_retuning": False,
            "shared_null_paths_across_detectors": True,
        }

    events = [
        {**event, "series_id": series_id,
         "expected_sign": int(event["expected_sign_by_series"][series_id])}
        for event in contract_events
        if series_id in event.get("expected_sign_by_series", {})
    ]
    historical, unmatched = _historical_for_series(
        rows=rows, values=values, events=events,
        calibrated=calibration, protocol=protocol,
    )
    report = {
        "status": "EVALUATED", "observation_count": int(values.size),
        "frequency": rows[0]["frequency"],
        "series_transform": rows[0].get("series_transform", "level"),
        "analysis_units": rows[0]["units"],
        "first_observation": rows[0]["observation_date"],
        "last_observation": rows[-1]["observation_date"],
        "first_available_at": rows[0]["available_at"],
        "last_available_at": rows[-1]["available_at"],
        "ar_model": {key: c3.clean(model.get(key)) for key in (
            "order", "intercept", "ar_coefficients", "residual_sigma",
            "residual_pool_sha256", "aic", "roots_abs")},
        "seed_ledgers": seed_ranges,
        "calibration": calibration,
        "null_trace_protocol": {
            "development_replicates": replicates,
            "holdout_replicates": replicates,
            "same_null_traces_shared_across_detectors": True,
            "holdout_is_disjoint_by_seed_phase": True,
        },
    }
    return report, historical, unmatched
