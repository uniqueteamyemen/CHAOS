"""C3 per-series equal-risk calibration using a first-40-only AR null model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

from p1_4_validation.c3.run_historical_break_evaluation import (
    PINNED, audit_prefix_replay, extract_hits, score_events, sha256, verify_bundle,
)
from p1_4_validation.injection_runner import (
    generate_ar_null_trace, select_ar_model, wilson_upper,
)
from p2_b_benchmark.p2c_engine import focus_detector, post_quiet_huber_detector

QUIET_POINTS = 40
REPLICATES = 1000
MIN_VALID_REPLICATES = 950
P0_TARGET = 0.10
FOCUS_GRID = (15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90, 110, 150, 200, 250, 300, 350, 400, 500, 600, 800, 1000, 1200)
HUBER_GRID = (4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 50, 60, 70, 80, 90, 100, 110, 125, 150, 200)
CANDIDATES = (
    "Post-Quiet Huber + MAD",
    "Post-Quiet Huber + Bartlett LRV",
    "FOCuS",
)
ALL_ARMS = CANDIDATES + ("A_FAST", "A_CONSENSUS")


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return [clean(v) for v in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(clean(value), ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))


def deterministic_seed(series_id: str, ar_order: int, phase: str, replicate: int) -> int:
    if phase not in {"development", "holdout"}:
        raise ValueError("C3_INVALID_SEED_PHASE")
    identity = (
        "CHAOS:P1.4:C3_EQUAL_RISK:v2:"
        + PINNED["tape_sha256"] + ":" + series_id + ":"
        + str(int(ar_order)) + ":" + phase + ":" + str(int(replicate))
    )
    return int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:8], "big")


def max_statistics(trace: np.ndarray) -> dict[str, float | None]:
    focus = focus_detector(
        trace, quiet_points=QUIET_POINTS, threshold=1e100,
        return_score_trace=True,
    )
    mad = post_quiet_huber_detector(
        trace, scale_mode="mad", quiet_points=QUIET_POINTS,
        threshold=1e100, return_score_trace=True,
    )
    bartlett = post_quiet_huber_detector(
        trace, scale_mode="bartlett", quiet_points=QUIET_POINTS,
        threshold=1e100, return_score_trace=True,
    )
    return {
        "FOCuS": focus.get("max_statistic") if focus.get("status") == "OK" else None,
        "Post-Quiet Huber + MAD": mad.get("max_statistic") if mad.get("status") == "OK" else None,
        "Post-Quiet Huber + Bartlett LRV": (
            bartlett.get("max_statistic") if bartlett.get("status") == "OK" else None
        ),
    }


def validate_holdout(scores: list[float | None], threshold: float) -> dict:
    valid = [float(x) for x in scores if x is not None and math.isfinite(float(x))]
    alarms = sum(x >= float(threshold) for x in valid)
    upper = wilson_upper(alarms, len(valid))
    status = (
        "INCONCLUSIVE" if len(valid) < MIN_VALID_REPLICATES
        else "PASS" if upper is not None and upper <= P0_TARGET
        else "FAIL"
    )
    return {
        "status": status,
        "valid_replicates": len(valid),
        "invalid_replicates": len(scores) - len(valid),
        "alarm_traces": alarms,
        "p0": alarms / len(valid) if valid else None,
        "wilson_upper_95_one_sided": upper,
        "p0_target": P0_TARGET,
    }


def calibrate_arm(
    development_scores: list[float | None],
    holdout_scores: list[float | None],
    grid: tuple[int, ...],
) -> dict:
    valid_dev = [float(x) for x in development_scores if x is not None and math.isfinite(float(x))]
    valid_hold = [float(x) for x in holdout_scores if x is not None and math.isfinite(float(x))]
    if len(valid_dev) < MIN_VALID_REPLICATES:
        return {
            "status": "INCONCLUSIVE",
            "reason": "INSUFFICIENT_VALID_DEVELOPMENT_NULL_REPLICATES",
            "valid_development_replicates": len(valid_dev),
            "valid_holdout_replicates": len(valid_hold),
            "frozen_threshold": None,
            "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
        }

    grid_rows = []
    selected = None
    for threshold in sorted(float(x) for x in grid):
        alarms = sum(x >= threshold for x in valid_dev)
        upper = wilson_upper(alarms, len(valid_dev))
        point = {
            "threshold": threshold,
            "alarm_traces": alarms,
            "valid_traces": len(valid_dev),
            "p0": alarms / len(valid_dev),
            "wilson_upper_95_one_sided": upper,
        }
        grid_rows.append(point)
        if upper is not None and upper <= P0_TARGET:
            selected = point
            break

    if selected is None:
        return {
            "status": "NOT_CALIBRATABLE",
            "reason": "NO_PREDECLARED_THRESHOLD_MET_DEVELOPMENT_P0",
            "development_grid": grid_rows,
            "valid_development_replicates": len(valid_dev),
            "valid_holdout_replicates": len(valid_hold),
            "frozen_threshold": None,
            "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
        }

    threshold = float(selected["threshold"])
    holdout = validate_holdout(holdout_scores, threshold)
    return {
        "status": holdout["status"],
        "development_status": "CALIBRATED",
        "development": selected,
        "development_grid": grid_rows,
        "frozen_threshold": threshold,
        "holdout": holdout,
        "valid_development_replicates": len(valid_dev),
        "valid_holdout_replicates": len(valid_hold),
        "holdout_retuning": False,
    }


def summarize_model(model: dict, rows: list[dict]) -> dict:
    result = {
        key: model.get(key)
        for key in (
            "order", "intercept", "ar_coefficients", "residual_sigma",
            "residual_pool_sha256", "residual_df", "aic", "roots_abs", "stable",
        )
    }
    result.update({
        "status": model.get("status"),
        "reason": model.get("reason"),
        "training_observations": QUIET_POINTS,
        "training_first_observation_date": rows[0]["observation_date"],
        "training_last_observation_date": rows[QUIET_POINTS - 1]["observation_date"],
        "training_last_available_at": rows[QUIET_POINTS - 1]["available_at"],
        "training_values_sha256": hashlib.sha256(
            np.asarray([r["value_float"] for r in rows[:QUIET_POINTS]], dtype="<f8").tobytes()
        ).hexdigest(),
        "no_post_quiet_observations_used_for_model_fit": True,
    })
    return result


def calibrate_series(series_id: str, rows: list[dict]) -> dict:
    values = np.asarray([row["value_float"] for row in rows], dtype=float)
    if len(values) <= QUIET_POINTS:
        raise ValueError("C3_EQUAL_RISK_SERIES_TOO_SHORT:" + series_id)

    # AR model fitting is restricted to the first 40 first-release observations.
    model = select_ar_model(values[:QUIET_POINTS])
    result = {
        "series_id": series_id,
        "series_length": len(values),
        "quiet_points": QUIET_POINTS,
        "p0_target": P0_TARGET,
        "replicates_per_phase": REPLICATES,
        "minimum_valid_replicates": MIN_VALID_REPLICATES,
        "model": summarize_model(model, rows),
        "arms": {},
    }
    if model.get("status") != "OK":
        for arm in CANDIDATES:
            result["arms"][arm] = {
                "status": "NOT_CALIBRATABLE",
                "reason": model.get("reason", "AR_NULL_MODEL_NOT_ELIGIBLE"),
                "frozen_threshold": None,
            }
        result["calibration_status"] = "NOT_CALIBRATABLE"
        return result

    order = int(model["order"])
    maxima = {
        phase: {arm: [] for arm in CANDIDATES}
        for phase in ("development", "holdout")
    }
    seed_hashes = {}
    for phase in ("development", "holdout"):
        seeds = [deterministic_seed(series_id, order, phase, i) for i in range(REPLICATES)]
        seed_hashes[phase] = hashlib.sha256(canonical_json(seeds)).hexdigest()
        for index, seed in enumerate(seeds):
            trace = generate_ar_null_trace(model, values[:order], len(values), seed)
            scores = max_statistics(trace)
            for arm in CANDIDATES:
                maxima[phase][arm].append(scores[arm])
            if (index + 1) % 250 == 0:
                print(
                    "C3_EQUAL_RISK_PROGRESS series=" + series_id
                    + " phase=" + phase
                    + " completed=" + str(index + 1) + "/" + str(REPLICATES),
                    flush=True,
                )

    result["seed_ledger_sha256"] = seed_hashes
    result["null_max_statistics"] = maxima
    grids = {
        "FOCuS": FOCUS_GRID,
        "Post-Quiet Huber + MAD": HUBER_GRID,
        "Post-Quiet Huber + Bartlett LRV": HUBER_GRID,
    }
    for arm in CANDIDATES:
        result["arms"][arm] = calibrate_arm(
            maxima["development"][arm], maxima["holdout"][arm], grids[arm]
        )
        result["arms"][arm]["threshold_grid"] = list(grids[arm])

    states = [result["arms"][arm]["status"] for arm in CANDIDATES]
    result["calibration_status"] = (
        "ALL_CANDIDATES_PASS_HOLDOUT_P0"
        if all(state == "PASS" for state in states)
        else "COMPLETED_WITH_CALIBRATION_EXCEPTIONS"
    )
    return result


def evaluate_series(
    series_id: str, rows: list[dict], event: dict, calibration: dict
) -> list[dict]:
    values = np.asarray([row["value_float"] for row in rows], dtype=float)
    output = []
    for detector in ALL_ARMS:
        if detector in CANDIDATES:
            arm = calibration["arms"][detector]
            if arm.get("status") != "PASS":
                output.append({
                    "event_id": event["event_id"],
                    "series_id": series_id,
                    "detector": detector,
                    "evaluation_status": "NOT_EVALUATED_EQUAL_RISK_NOT_VALIDATED",
                    "calibration_status": arm.get("status"),
                    "threshold": arm.get("frozen_threshold"),
                    "metrics": None,
                })
                continue
            threshold = float(arm["frozen_threshold"])
            hits, detector_status, metadata = extract_hits(
                detector, values, threshold=threshold
            )
            replayed = (
                audit_prefix_replay(detector, values, hits, threshold=threshold)
                if hits else 0
            )
            metrics = score_events(rows, event["anchor_date"], hits)
            output.append({
                "event_id": event["event_id"],
                "series_id": series_id,
                "detector": detector,
                "evaluation_status": "EQUAL_RISK_HOLDOUT_VALIDATED",
                "calibration_status": "PASS",
                "threshold": threshold,
                "detector_status": detector_status,
                "no_lookahead_prefix_replays": replayed,
                "detector_metadata": metadata,
                "metrics": metrics,
            })
        else:
            # Frozen A_FAST / A_CONSENSUS controls are read-only and not recalibrated.
            hits, detector_status, metadata = extract_hits(detector, values)
            replayed = audit_prefix_replay(detector, values, hits) if hits else 0
            metrics = score_events(rows, event["anchor_date"], hits)
            output.append({
                "event_id": event["event_id"],
                "series_id": series_id,
                "detector": detector,
                "evaluation_status": "FROZEN_REFERENCE_NOT_EQUAL_RISK_CALIBRATED",
                "calibration_status": "NOT_APPLICABLE_READ_ONLY",
                "threshold": None,
                "detector_status": detector_status,
                "no_lookahead_prefix_replays": replayed,
                "detector_metadata": metadata,
                "metrics": metrics,
            })
    return output


def markdown_report(report: dict) -> str:
    lines = [
        "# C3 — Equal-Risk Calibration v1",
        "",
        "- Status: " + report["status"],
        "- Run ID: " + str(report["run_id"]),
        "- Evaluation commit: " + str(report["evaluation_commit"]),
        "- Source archive SHA-256: " + PINNED["artifact_sha256"],
        "- Normalized first-release tape SHA-256: " + PINNED["tape_sha256"],
        "- P0 target: 0.10; one-sided Wilson upper 95% must be at or below target",
        "- Null design: AR(1–3), AIC selection from first 40 observations only; residual bootstrap",
        "- Replicates per series and phase: 1000 development + 1000 independent holdout",
        "- Minimum valid replicates per phase and arm: 950",
        "- Threshold selected on development only. Holdout is validation only; never retuned.",
        "- Grid v2 expands the predeclared C3 threshold search range after v1 development-only shortfalls; a new seed namespace supplies fresh development and holdout simulations.",
        "- P0 is conditional on the fitted AR model and residual-bootstrap assumptions.",
        "",
        "## 1. Per-series calibration",
        "",
        "| Series | AR order | Detector | Threshold | Dev P0 | Dev Wilson U95 | Holdout P0 | Holdout Wilson U95 | Status |",
        "|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for series_id, series in report["calibration"].items():
        order = series["model"].get("order", "—")
        for arm_name in CANDIDATES:
            arm = series["arms"][arm_name]
            dev = arm.get("development", {})
            hold = arm.get("holdout", {})
            def fmt(value):
                return "—" if value is None else str(round(float(value), 4))
            lines.append(
                "| " + series_id + " | " + str(order) + " | " + arm_name + " | "
                + fmt(arm.get("frozen_threshold")) + " | "
                + fmt(dev.get("p0")) + " | "
                + fmt(dev.get("wilson_upper_95_one_sided")) + " | "
                + fmt(hold.get("p0")) + " | "
                + fmt(hold.get("wilson_upper_95_one_sided")) + " | "
                + str(arm.get("status")) + " |"
            )

    lines += [
        "",
        "## 2. Historical head-to-head at frozen equal-risk thresholds",
        "",
        "| Series / event | Detector | Evaluation status | Hit / Miss | Available at | Lag | Baseline false alarms | Baseline n |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in report["historical_results"]:
        metrics = row.get("metrics")
        if metrics is None:
            lines.append(
                "| " + row["series_id"] + " / " + row["event_id"] + " | "
                + row["detector"] + " | " + row["evaluation_status"]
                + " | — | — | — | — | — |"
            )
            continue
        lag = (
            str(metrics["detection_lag_weeks_or_months"]) + " " + metrics["lag_unit"]
            if metrics.get("detection_lag_weeks_or_months") is not None else "—"
        )
        lines.append(
            "| " + row["series_id"] + " / " + row["event_id"] + " | "
            + row["detector"] + " | " + row["evaluation_status"] + " | "
            + metrics["hit_miss"] + " | "
            + str(metrics.get("detection_available_at") or "—") + " | "
            + lag + " | " + str(metrics["false_alarms_before_anchor"])
            + " | " + str(metrics["baseline_observations_after_quiet"]) + " |"
        )

    lines += [
        "",
        "## 3. Interpretation limits",
        "",
        "- Only the initial 40 first-release observations fit the AR null model. Event anchors and later observations are excluded from threshold selection.",
        "- P0 is estimated as the fraction of simulated no-change traces with at least one alarm over the same post-quiet monitoring horizon.",
        "- A candidate is historically scored only after independent holdout passes the frozen P0 gate. Failed or inconclusive arms remain unscored; no global-threshold fallback.",
        "- Bartlett is a Huber scale-estimator variant, not an independent alarm detector.",
        "- The current FOCuS primitive is single-hit with no reset/rearm; repeated-change performance is not validated.",
        "- A_FAST and A_CONSENSUS remain unchanged read-only references; no equal-risk claim is made for them.",
        "- UNRATE has only 9 post-quiet pre-anchor observations; its observed baseline count has limited resolution.",
        "- Passing this fitted-null test is not a distribution-free real-world false-alarm guarantee.",
        "",
        "## 4. Reproducibility",
        "",
        "- Source intake run: " + PINNED["source_run_id"],
        "- Run ID: " + str(report["run_id"]),
        "- Evaluation commit: " + str(report["evaluation_commit"]),
        "- Report JSON SHA-256: " + str(report.get("report_json_sha256", "PENDING")),
        "- Replay: python p1_4_validation/c3/run_equal_risk_calibration.py --artifact-zip <pinned-source.zip> --contract p1_4_validation/c3/c3_source_contract_v1.json --output-dir artifacts/p1_4/c3/equal_risk_calibration",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--contract", default="p1_4_validation/c3/c3_source_contract_v1.json")
    parser.add_argument("--output-dir", default="artifacts/p1_4/c3/equal_risk_calibration")
    args = parser.parse_args()

    _manifest, series_rows, events = verify_bundle(
        Path(args.artifact_zip), Path(args.contract)
    )
    calibration = {}
    historical_results = []
    for series_id in ("UNRATE", "WCOILBRENTEU", "ICSA"):
        series_cal = calibrate_series(series_id, series_rows[series_id])
        calibration[series_id] = series_cal
        historical_results.extend(
            evaluate_series(series_id, series_rows[series_id], events[series_id], series_cal)
        )
        print(
            "C3_EQUAL_RISK_SERIES_COMPLETE series=" + series_id
            + " calibration_status=" + series_cal["calibration_status"],
            flush=True,
        )

    all_states = [
        calibration[sid]["arms"][arm]["status"]
        for sid in calibration for arm in CANDIDATES
    ]
    report_status = (
        "EQUAL_RISK_ALL_SERIES_ALL_CANDIDATES_HOLDOUT_PASS"
        if all(state == "PASS" for state in all_states)
        else "EQUAL_RISK_COMPLETED_WITH_CALIBRATION_EXCEPTIONS"
    )
    report = {
        "schema_version": "1.0.0",
        "status": report_status,
        "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL_REPLAY"),
        "evaluation_commit": os.environ.get("GITHUB_SHA", "LOCAL_REPLAY"),
        "source_integrity": {
            "artifact_sha256": PINNED["artifact_sha256"],
            "manifest_sha256": PINNED["manifest_sha256"],
            "tape_sha256": PINNED["tape_sha256"],
            "contract_sha256": PINNED["contract_sha256"],
            "source_run_id": PINNED["source_run_id"],
            "source_commit": PINNED["source_commit"],
            "point_count": 840,
            "series_count": 3,
            "raw_batch_count": 87,
        },
        "calibration_protocol": {
            "p0_target": P0_TARGET,
            "confidence_bound": "one-sided Wilson 95%",
            "quiet_points": QUIET_POINTS,
            "ar_orders": [1, 2, 3],
            "ar_selection": "minimum AIC; unstable winner fails closed",
            "model_fit_scope": "first 40 first-release observations only",
            "null_generator": "AR(p) residual bootstrap using fitted pre-quiet residual pool",
            "development_replicates_per_series": REPLICATES,
            "holdout_replicates_per_series": REPLICATES,
            "minimum_valid_replicates_per_phase_and_arm": MIN_VALID_REPLICATES,
            "threshold_grids": {
                "FOCuS": list(FOCUS_GRID),
                "Post-Quiet Huber + MAD": list(HUBER_GRID),
                "Post-Quiet Huber + Bartlett LRV": list(HUBER_GRID),
            },
            "threshold_selected_on": "development only",
            "holdout_retuning": False,
            "historical_evaluation_requires_holdout_pass": True,
            "null_seed_namespace": "CHAOS:P1.4:C3_EQUAL_RISK:v2",
            "threshold_grid_revision": "v2_extended_after_development_only_search_range_shortfall",
            "independent_seed_set_from_prior_calibration_attempt": True,
        },
        "calibration": calibration,
        "historical_results": historical_results,
        "replay_command": (
            "python p1_4_validation/c3/run_equal_risk_calibration.py "
            "--artifact-zip <pinned-source.zip> "
            "--contract p1_4_validation/c3/c3_source_contract_v1.json "
            "--output-dir artifacts/p1_4/c3/equal_risk_calibration"
        ),
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "C3_EQUAL_RISK_CALIBRATION_V1.json"
    json_path.write_bytes(canonical_json(report))
    report["report_json_sha256"] = sha256(json_path.read_bytes())
    markdown_path = output / "C3_EQUAL_RISK_CALIBRATION_V1.md"
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    csv_path = output / "C3_EQUAL_RISK_CALIBRATION_V1.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "series_id", "event_id", "detector", "calibration_status",
            "frozen_threshold", "development_p0", "development_wilson_upper_95",
            "holdout_p0", "holdout_wilson_upper_95", "evaluation_status",
            "hit_miss", "detection_available_at", "detection_lag_days",
            "detection_lag_weeks_or_months", "lag_unit",
            "false_alarms_before_anchor", "baseline_observations_after_quiet",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        indexed = {(row["series_id"], row["detector"]): row for row in historical_results}
        for sid in ("UNRATE", "WCOILBRENTEU", "ICSA"):
            for detector in ALL_ARMS:
                row = indexed[(sid, detector)]
                metrics = row.get("metrics") or {}
                arm = calibration[sid]["arms"].get(detector, {})
                dev = arm.get("development", {})
                hold = arm.get("holdout", {})
                writer.writerow({
                    "series_id": sid,
                    "event_id": row["event_id"],
                    "detector": detector,
                    "calibration_status": row["calibration_status"],
                    "frozen_threshold": row.get("threshold"),
                    "development_p0": dev.get("p0"),
                    "development_wilson_upper_95": dev.get("wilson_upper_95_one_sided"),
                    "holdout_p0": hold.get("p0"),
                    "holdout_wilson_upper_95": hold.get("wilson_upper_95_one_sided"),
                    "evaluation_status": row["evaluation_status"],
                    "hit_miss": metrics.get("hit_miss"),
                    "detection_available_at": metrics.get("detection_available_at"),
                    "detection_lag_days": metrics.get("detection_lag_days"),
                    "detection_lag_weeks_or_months": metrics.get("detection_lag_weeks_or_months"),
                    "lag_unit": metrics.get("lag_unit"),
                    "false_alarms_before_anchor": metrics.get("false_alarms_before_anchor"),
                    "baseline_observations_after_quiet": metrics.get("baseline_observations_after_quiet"),
                })

    print(markdown_path.read_text(encoding="utf-8"), flush=True)
    print(
        "C3_EQUAL_RISK_OUTPUTS " + json.dumps({
            "json": str(json_path),
            "json_sha256": report["report_json_sha256"],
            "markdown": str(markdown_path),
            "csv": str(csv_path),
        }, sort_keys=True),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
