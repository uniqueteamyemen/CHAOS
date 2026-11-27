from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.causal_multiscale_adaptive import (
    CausalMultiScaleExcursionDetector,
    CausalMultiScaleFlowDetector,
)
from p2_b_benchmark.p2c_engine import bocpd_detector

PROTOCOL_PATH = Path("p1_4_validation/c3/c3_v2_4_multiscale_preregistration.json")
OUT_NAME = "C3_V2_4_MULTISCALE_EVALUATION.json"
MANIFEST_NAME = "C3_V2_4_MULTISCALE_MANIFEST.json"

MULTISCALE = "Causal MultiScale (representation-specific)"
BOCPD = "Calibrated BOCPD"
HUBER = "Post-Quiet Huber + MAD"
BASELINE_EVENT_PAIRS = {"v2_3_slope_shift": 3, "v2_3_huber_mad": 5}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        c3.clean(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8") + b"\n"


def _detector_for_series(protocol: dict, series_id: str):
    cfg = protocol["series_parameters"][series_id]
    if cfg["representation"] == "level":
        return CausalMultiScaleExcursionDetector(
            windows=tuple(cfg["windows"]),
            baseline_points=int(cfg["baseline_points"]),
            guard_points=int(cfg["guard_points"]),
            initial_quiet_points=int(cfg["initial_quiet_points"]),
            confirm_points=int(cfg["confirm_points"]),
        )
    if cfg["representation"] == "first_difference":
        return CausalMultiScaleFlowDetector(
            windows=tuple(cfg["windows"]),
            baseline_points=int(cfg["baseline_points"]),
            guard_points=int(cfg["guard_points"]),
            initial_quiet_points=int(cfg["initial_quiet_points"]),
            confirm_points=int(cfg["confirm_points"]),
            rearm_quiet_points=int(cfg["rearm_quiet_points"]),
        )
    raise ValueError(f"C3_V2_4_UNKNOWN_REPRESENTATION:{series_id}")


def _valid(scores: list[float | None]) -> list[float]:
    return [
        float(value) for value in scores
        if value is not None and np.isfinite(float(value))
    ]


def _risk_row(alarms: int, trials: int, gate: float) -> dict[str, Any]:
    row = c3.wilson_stats(int(alarms), int(trials))
    row["p0_target"] = float(gate)
    return row


def _calibrate_continuous(
    scores: list[float | None], threshold_grid: list[float],
    *, dev_gate: float, min_valid: int,
) -> dict[str, Any]:
    valid = _valid(scores)
    if len(valid) < min_valid:
        return {
            "status": "INCONCLUSIVE",
            "reason": "INSUFFICIENT_VALID_DEVELOPMENT_REPLICATES",
            "valid_replicates": len(valid), "frozen_threshold": None, "grid": [],
        }
    rows = []
    for threshold in sorted({float(v) for v in threshold_grid}):
        alarms = sum(value >= threshold for value in valid)
        stats = _risk_row(alarms, len(valid), dev_gate)
        row = {"threshold": threshold, **stats}
        rows.append(row)
        if stats["wilson_upper_95_one_sided"] is not None and (
            stats["wilson_upper_95_one_sided"] <= dev_gate
        ):
            return {
                "status": "CALIBRATED", "frozen_threshold": threshold,
                "development": row, "grid": rows,
                "selection_rule": "lowest preregistered threshold with Development Wilson U95 <= 0.085",
            }
    return {
        "status": "NOT_CALIBRATABLE",
        "reason": "NO_THRESHOLD_MET_DEVELOPMENT_WILSON_GATE",
        "valid_replicates": len(valid), "frozen_threshold": None, "grid": rows,
    }


def _calibrate_bocpd(
    scores_by_mass: dict[str, list[float | None]], mass_grid: list[float],
    *, dev_gate: float, min_valid: int,
) -> dict[str, Any]:
    rows = []
    for mass in sorted(float(v) for v in mass_grid):
        key = f"{mass:.6f}"
        valid = _valid(scores_by_mass.get(key, []))
        if len(valid) < min_valid:
            return {
                "status": "INCONCLUSIVE",
                "reason": "INSUFFICIENT_VALID_BOCPD_DEVELOPMENT_REPLICATES",
                "valid_replicates": len(valid), "frozen_threshold": None, "grid": rows,
            }
        alarms = sum(value >= 1.0 for value in valid)
        stats = _risk_row(alarms, len(valid), dev_gate)
        row = {"short_mass_threshold": mass, **stats}
        rows.append(row)
        if stats["wilson_upper_95_one_sided"] is not None and (
            stats["wilson_upper_95_one_sided"] <= dev_gate
        ):
            return {
                "status": "CALIBRATED", "frozen_threshold": mass,
                "development": row, "grid": rows,
                "selection_rule": "lowest preregistered short_mass_threshold with Development Wilson U95 <= 0.085",
                "persistence": 3,
            }
    return {
        "status": "NOT_CALIBRATABLE",
        "reason": "NO_SHORT_MASS_THRESHOLD_MET_DEVELOPMENT_WILSON_GATE",
        "valid_replicates": len(_valid(scores_by_mass.get(f"{float(mass_grid[-1]):.6f}", []))),
        "frozen_threshold": None, "grid": rows,
    }


def _evaluate_continuous_holdout(
    scores: list[float | None], frozen: float | None,
    *, holdout_gate: float, min_valid: int,
) -> dict[str, Any]:
    if frozen is None:
        return {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD", "evaluated": False,
                "holdout_retuning": False}
    valid = _valid(scores)
    alarms = sum(value >= float(frozen) for value in valid)
    stats = _risk_row(alarms, len(valid), holdout_gate)
    status = (
        "INCONCLUSIVE" if len(valid) < min_valid else
        "PASS" if stats["wilson_upper_95_one_sided"] <= holdout_gate else "FAIL"
    )
    return {"status": status, "evaluated": True, **stats,
            "frozen_threshold": float(frozen), "holdout_retuning": False}


def _evaluate_bocpd_holdout(
    scores: list[float | None] | None, frozen: float | None,
    *, holdout_gate: float, min_valid: int,
) -> dict[str, Any]:
    if frozen is None or scores is None:
        return {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD", "evaluated": False,
                "holdout_retuning": False}
    valid = _valid(scores)
    alarms = sum(value >= 1.0 for value in valid)
    stats = _risk_row(alarms, len(valid), holdout_gate)
    status = (
        "INCONCLUSIVE" if len(valid) < min_valid else
        "PASS" if stats["wilson_upper_95_one_sided"] <= holdout_gate else "FAIL"
    )
    return {"status": status, "evaluated": True, **stats,
            "frozen_short_mass_threshold": float(frozen),
            "persistence": 3, "holdout_retuning": False}


def _bocpd_alarm(trace: np.ndarray, mass: float) -> float | None:
    result = bocpd_detector(
        trace, quiet_points=c3.QUIET_POINTS,
        persistence=3, short_mass_threshold=float(mass),
    )
    if result.get("status") != "OK":
        return None
    return 1.0 if result.get("hits") else 0.0


def _generate_phase_scores(
    *,
    series_id: str,
    values: np.ndarray,
    tape_sha: str,
    model: dict,
    phase: str,
    replicates: int,
    seed_namespace: str,
    protocol: dict,
    multi_detector,
    selected_bocpd_mass: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    mass_grid = [float(v) for v in protocol["detectors"][BOCPD]["short_mass_threshold_grid"]]
    if phase == "development":
        evaluated_masses = mass_grid
    elif selected_bocpd_mass is not None:
        evaluated_masses = [float(selected_bocpd_mass)]
    else:
        evaluated_masses = []

    scores: dict[str, Any] = {
        MULTISCALE: [],
        HUBER: [],
        BOCPD: {f"{mass:.6f}": [] for mass in evaluated_masses},
    }
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

        multi = multi_detector.score_trace(trace)
        scores[MULTISCALE].append(
            multi.get("max_confirmed_score") if multi.get("status") == "OK" else None
        )
        scores[HUBER].append(c3.huber_max_statistic(trace, "mad"))
        for mass in evaluated_masses:
            key = f"{mass:.6f}"
            scores[BOCPD][key].append(_bocpd_alarm(trace, mass))

        if (replicate + 1) % 250 == 0:
            print(
                f"C3_V2_4_NULL_PROGRESS series={series_id} phase={phase} "
                f"completed={replicate + 1}/{replicates}",
                flush=True,
            )

    ledger_sha = _sha256("\n".join(seed_material).encode("utf-8"))
    ledger = {
        "replicate_count": len(seeds),
        "first_seed": seeds[0] if seeds else None,
        "last_seed": seeds[-1] if seeds else None,
        "seed_ledger_sha256": ledger_sha,
    }
    return scores, ledger, seeds


def _risk_status(dev: dict, hold: dict) -> str:
    if dev.get("status") != "CALIBRATED":
        return "NOT_CALIBRATABLE_OR_INCONCLUSIVE"
    if hold.get("status") == "PASS":
        return "VALIDATED"
    if hold.get("status") == "FAIL":
        return "NOT_VALIDATED"
    return "INCONCLUSIVE"


def _normalize_hits(hits: list[dict], detector_name: str, size: int) -> list[dict]:
    output = []
    for source in hits:
        index = source.get("index", source.get("detection_index"))
        sign = source.get("sign", source.get("direction"))
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError(f"C3_V2_4_INVALID_HIT_INDEX:{detector_name}")
        if isinstance(sign, bool) or int(sign) not in (-1, 1):
            raise ValueError(f"C3_V2_4_INVALID_HIT_SIGN:{detector_name}")
        if not 0 <= int(index) < size:
            raise ValueError(f"C3_V2_4_HIT_INDEX_OUT_OF_RANGE:{detector_name}:{index}")
        output.append({
            **source, "index": int(index), "sign": int(sign),
            "detector": detector_name,
        })
    output.sort(key=lambda row: (row["index"], row["sign"]))
    return output


def _prefix_replay_multi(detector, values: np.ndarray, hits: list[dict], threshold: float) -> int:
    for hit in hits:
        index = int(hit["index"])
        replay = detector.detect(values[:index + 1], threshold=threshold)
        if replay.get("status") != "OK" or not any(
            int(item["index"]) == index and int(item["sign"]) == int(hit["sign"])
            for item in replay.get("hits", [])
        ):
            raise ValueError(f"C3_V2_4_MULTI_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{index}")
    return len(hits)


def _prefix_replay_bocpd(
    values: np.ndarray, hits: list[dict], mass: float,
) -> int:
    for hit in hits:
        index = int(hit["index"])
        replay = bocpd_detector(
            values[:index + 1], quiet_points=c3.QUIET_POINTS,
            persistence=3, short_mass_threshold=float(mass),
        )
        if replay.get("status") != "OK" or not any(
            int(item.get("index", item.get("detection_index", -1))) == index
            and int(item["sign"]) == int(hit["sign"])
            for item in replay.get("hits", [])
        ):
            raise ValueError(f"C3_V2_4_BOCPD_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{index}")
    return len(hits)


def _historical_for_series(
    *,
    series_id: str,
    rows: list[dict],
    values: np.ndarray,
    events: list[dict],
    calibrated: dict[str, dict],
    multi_detector,
) -> tuple[list[dict], dict[str, dict]]:
    output_rows: list[dict] = []
    unmatched_summaries: dict[str, dict] = {}
    from p2_b_benchmark.p2c_engine import post_quiet_huber_detector

    for detector_name in (MULTISCALE, BOCPD, HUBER):
        arm = calibrated[detector_name]
        threshold = arm.get("frozen_threshold")
        replayed = 0
        detector_meta: dict[str, Any] = {}
        if threshold is None:
            hits: list[dict] = []
            detector_status = "ABSTAIN"
            detector_meta["reason"] = "NO_DEVELOPMENT_CALIBRATED_THRESHOLD"
        elif detector_name == MULTISCALE:
            result = multi_detector.detect(values, threshold=float(threshold))
            detector_status = str(result.get("status", "OK"))
            hits = _normalize_hits(result.get("hits", []), detector_name, len(values))
            detector_meta = {
                key: result.get(key) for key in (
                    "windows", "baseline_points", "guard_points", "confirm_points",
                    "rearm_quiet_points", "rearm_policy", "max_confirmed_score",
                    "scale_source_counts", "zero_scale_points",
                )
            }
            replayed = _prefix_replay_multi(
                multi_detector, values, hits, float(threshold)
            ) if hits else 0
        elif detector_name == BOCPD:
            result = bocpd_detector(
                values, quiet_points=c3.QUIET_POINTS,
                persistence=3, short_mass_threshold=float(threshold),
            )
            detector_status = str(result.get("status", "OK"))
            hits = _normalize_hits(result.get("hits", []), detector_name, len(values))
            detector_meta = result.get("metadata", {})
            replayed = _prefix_replay_bocpd(values, hits, float(threshold)) if hits else 0
        else:
            result = post_quiet_huber_detector(
                values, scale_mode="mad", quiet_points=c3.QUIET_POINTS,
                threshold=float(threshold), return_score_trace=False,
            )
            detector_status = str(result.get("status", "OK"))
            hits = _normalize_hits(result.get("hits", []), detector_name, len(values))
            detector_meta = result.get("metadata", {})
            if hits:
                for hit in hits:
                    prefix = post_quiet_huber_detector(
                        values[:int(hit["index"]) + 1], scale_mode="mad",
                        quiet_points=c3.QUIET_POINTS, threshold=float(threshold),
                    )
                    if prefix.get("status") != "OK" or not any(
                        int(item["index"]) == int(hit["index"])
                        and int(item["sign"]) == int(hit["sign"])
                        for item in prefix.get("hits", [])
                    ):
                        raise ValueError(
                            f"C3_V2_4_HUBER_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{hit['index']}"
                        )
                replayed = len(hits)

        detector_meta = dict(detector_meta or {})
        detector_meta["all_hits"] = [
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
        unmatched["detector_metadata"] = c3.clean(detector_meta)
        unmatched["no_lookahead_prefix_replays"] = int(replayed)
        unmatched_summaries[detector_name] = unmatched

        for row in matched_rows:
            output_rows.append({
                **row,
                "risk_validation_status": arm.get("risk_validation_status", "ABSTAINED"),
                "frozen_threshold": threshold,
                "development_wilson_u95": arm.get("development", {}).get(
                    "wilson_upper_95_one_sided"
                ),
                "holdout_wilson_u95": arm.get("holdout", {}).get(
                    "wilson_upper_95_one_sided"
                ),
                "detector_status": detector_status,
                "no_lookahead_prefix_replays": int(replayed),
                "unmatched_alarm_count_for_series_detector": unmatched["unmatched_alarm_count"],
            })
    return output_rows, unmatched_summaries


def _exposure_years(rows: list[dict]) -> float:
    if len(rows) < 2:
        return 0.0
    start = rows[0]["available_at_obj"]
    end = rows[-1]["available_at_obj"]
    return max(0.0, (end - start).days / 365.25)


def _summarize_historical(
    event_rows: list[dict],
    unmatched_all: dict[str, dict],
    by_series: dict[str, list[dict]],
    expected_episode_ids: set[str],
) -> dict[str, dict]:
    output: dict[str, dict] = {}
    total_pairs = sum(
        1 for row in event_rows
        if row["detector"] == MULTISCALE
    )
    for detector in (MULTISCALE, BOCPD, HUBER):
        rows = [row for row in event_rows if row["detector"] == detector]
        matched = [row for row in rows if row["hit_miss"] == "HIT"]
        post = [
            row for row in matched
            if row["detection_lag_days"] is not None
            and int(row["detection_lag_days"]) >= 0
        ]
        early = [
            row for row in matched
            if row["detection_lag_days"] is not None
            and int(row["detection_lag_days"]) < 0
        ]
        matched_episodes = {str(row["episode_id"]) for row in matched}
        post_episodes = {str(row["episode_id"]) for row in post}
        unmatched_count = sum(
            int(unmatched_all.get(series_id, {}).get(detector, {}).get("unmatched_alarm_count", 0))
            for series_id in by_series
        )
        exposure = sum(_exposure_years(by_series[series_id]) for series_id in by_series)
        output[detector] = {
            "total_event_series_pairs": len(rows),
            "historical_matches_within_pm_12_months": len(matched),
            "post_break_recall": {
                "matched_pairs": len(post),
                "total_pairs": len(rows),
                "recall": (len(post) / len(rows)) if rows else None,
                "matched_episode_ids": sorted(post_episodes),
                "episode_coverage": len(post_episodes),
                "total_episode_ids": len(expected_episode_ids),
            },
            "early_warning_matches": {
                "matched_pairs": len(early),
                "episode_ids": sorted({str(row["episode_id"]) for row in early}),
            },
            "all_direction_episode_coverage": {
                "matched_episode_ids": sorted(matched_episodes),
                "covered_episode_count": len(matched_episodes),
                "total_episode_count": len(expected_episode_ids),
            },
            "unmatched_alarms": unmatched_count,
            "exposure_years_sum_across_series": round(exposure, 4),
            "unmatched_alarms_per_year": (
                unmatched_count / exposure if exposure > 0 else None
            ),
            "comparison": {
                "exceeds_v2_3_slope_shift_3_of_35": len(post) > BASELINE_EVENT_PAIRS["v2_3_slope_shift"],
                "exceeds_v2_3_huber_mad_5_of_35": len(post) > BASELINE_EVENT_PAIRS["v2_3_huber_mad"],
                "v2_3_slope_shift_reference_post_break_pairs": 3,
                "v2_3_huber_mad_reference_event_pairs": 5,
            },
        }
    return output


def run(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = Path(args.protocol)
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get("status") != "PRE_REGISTERED":
        raise ValueError("C3_V2_4_PROTOCOL_NOT_PREREGISTERED")
    if protocol.get("source", {}).get("source_intake_run_id") != str(args.expected_source_run_id):
        raise ValueError("C3_V2_4_SOURCE_RUN_ID_MISMATCH")
    replicates = int(protocol["null_protocol"]["replicates_per_phase"])
    if int(args.replicates) != replicates:
        raise ValueError("C3_V2_4_BAD_REPLICATE_COUNT")
    if args.expected_source_run_id != "45757611871":
        raise ValueError("C3_V2_4_SOURCE_RUN_ID_NOT_FROZEN")
    if protocol["null_protocol"]["seed_namespace"] != "CHAOS:C3_V2_4_MULTISCALE_ADAPTIVE_2000X2_V1_PREREG_20261128":
        raise ValueError("C3_V2_4_SEED_NAMESPACE_MUTATED")

    source_zip = Path(args.source_zip)
    contract_path = Path(args.contract)
    manifest, raw_by_series, contract, archive_sha, contract_sha = c3.verify_source_bundle(
        source_zip, contract_path
    )
    if str(manifest.get("workflow_run_id")) != str(args.expected_source_run_id):
        raise ValueError("C3_V2_4_SOURCE_MANIFEST_RUN_ID_MISMATCH")
    if manifest["normalized_tape"]["sha256"] != protocol["source"]["normalized_tape_sha256"]:
        raise ValueError("C3_V2_4_NORMALIZED_TAPE_SHA256_MISMATCH")
    if contract_sha != protocol["source"]["evaluation_contract_sha256"]:
        raise ValueError("C3_V2_4_EVALUATION_CONTRACT_SHA256_MISMATCH")
    if archive_sha is None:
        raise ValueError("C3_V2_4_SOURCE_ARCHIVE_SHA_MISSING")

    by_series, transform_audit = c3.apply_causal_series_transforms(
        source_zip, manifest, raw_by_series, contract
    )
    target_series = list(protocol["analysis"]["target_series"])
    target_by_series = {sid: by_series[sid] for sid in target_series}
    analysis_tape_sha = c3.analysis_tape_sha256(target_by_series)
    min_valid = int(protocol["null_protocol"]["minimum_valid_replicates"])
    if min_valid != int(np.ceil(replicates * 0.95)):
        raise ValueError("C3_V2_4_MIN_VALID_REPLICATE_POLICY_MISMATCH")
    if float(protocol["risk_gates"]["development_wilson_u95_max"]) != 0.085:
        raise ValueError("C3_V2_4_DEV_RISK_GATE_MUTATED")
    if float(protocol["risk_gates"]["holdout_wilson_u95_max"]) != 0.10:
        raise ValueError("C3_V2_4_HOLDOUT_RISK_GATE_MUTATED")

    series_reports: dict[str, dict] = {}
    event_rows: list[dict] = []
    unmatched_all: dict[str, dict] = {}
    seed_ledgers: dict[str, dict] = {}
    event_episodes = {
        str(event["episode_id"])
        for event in contract["events"]
        if any(series_id in event.get("expected_sign_by_series", {}) for series_id in target_series)
    }
    if len(event_episodes) != 8:
        raise ValueError(f"C3_V2_4_EXPECTED_EIGHT_TARGET_EPISODES:{len(event_episodes)}")

    for series_id in target_series:
        rows = target_by_series[series_id]
        values = np.asarray([row["value_float"] for row in rows], dtype=float)
        if values.size <= c3.QUIET_POINTS:
            raise ValueError(f"C3_V2_4_SERIES_TOO_SHORT:{series_id}")
        available = [row["available_at_obj"] for row in rows]
        if any(available[i] < available[i - 1] for i in range(1, len(available))):
            raise ValueError(f"C3_V2_4_NON_MONOTONIC_AVAILABLE_AT:{series_id}")
        model = c3.select_ar_model(values[:c3.QUIET_POINTS])
        if model.get("status") != "OK":
            series_reports[series_id] = {
                "status": "ABSTAINED_AR_MODEL_NOT_ELIGIBLE",
                "ar_model_reason": model.get("reason"),
                "observation_count": int(values.size),
            }
            continue

        multi_detector = _detector_for_series(protocol, series_id)
        series_seed_ledgers: dict[str, dict] = {}
        dev_scores, dev_ledger, _ = _generate_phase_scores(
            series_id=series_id, values=values,
            tape_sha=manifest["normalized_tape"]["sha256"], model=model,
            phase="development", replicates=replicates,
            seed_namespace=protocol["null_protocol"]["seed_namespace"],
            protocol=protocol, multi_detector=multi_detector,
        )
        series_seed_ledgers["development"] = dev_ledger

        thresholds = protocol["detectors"]
        multi_dev = _calibrate_continuous(
            dev_scores[MULTISCALE],
            thresholds[MULTISCALE]["threshold_grid_by_series"][series_id],
            dev_gate=float(protocol["risk_gates"]["development_wilson_u95_max"]),
            min_valid=min_valid,
        )
        huber_dev = _calibrate_continuous(
            dev_scores[HUBER], thresholds[HUBER]["threshold_grid"],
            dev_gate=float(protocol["risk_gates"]["development_wilson_u95_max"]),
            min_valid=min_valid,
        )
        bocpd_dev = _calibrate_bocpd(
            dev_scores[BOCPD],
            thresholds[BOCPD]["short_mass_threshold_grid"],
            dev_gate=float(protocol["risk_gates"]["development_wilson_u95_max"]),
            min_valid=min_valid,
        )
        frozen_mass = bocpd_dev.get("frozen_threshold")

        # Holdout paths are generated independently. BOCPD is evaluated only
        # at the single short-mass threshold selected on Development.
        hold_scores, hold_ledger, _ = _generate_phase_scores(
            series_id=series_id, values=values,
            tape_sha=manifest["normalized_tape"]["sha256"], model=model,
            phase="holdout", replicates=replicates,
            seed_namespace=protocol["null_protocol"]["seed_namespace"],
            protocol=protocol, multi_detector=multi_detector,
            selected_bocpd_mass=float(frozen_mass) if frozen_mass is not None else None,
        )
        series_seed_ledgers["holdout"] = hold_ledger

        dev_gate = float(protocol["risk_gates"]["development_wilson_u95_max"])
        hold_gate = float(protocol["risk_gates"]["holdout_wilson_u95_max"])
        multi_hold = _evaluate_continuous_holdout(
            hold_scores[MULTISCALE], multi_dev.get("frozen_threshold"),
            holdout_gate=hold_gate, min_valid=min_valid,
        )
        huber_hold = _evaluate_continuous_holdout(
            hold_scores[HUBER], huber_dev.get("frozen_threshold"),
            holdout_gate=hold_gate, min_valid=min_valid,
        )
        bocpd_hold_scores = None
        if frozen_mass is not None:
            bocpd_hold_scores = hold_scores[BOCPD].get(f"{float(frozen_mass):.6f}")
        bocpd_hold = _evaluate_bocpd_holdout(
            bocpd_hold_scores, frozen_mass,
            holdout_gate=hold_gate, min_valid=min_valid,
        )

        calibration = {
            MULTISCALE: {
                "development": multi_dev.get("development", {}),
                "development_status": multi_dev.get("status"),
                "development_valid_replicates": len(_valid(dev_scores[MULTISCALE])),
                "development_grid": multi_dev.get("grid", []),
                "holdout": multi_hold,
                "holdout_valid_replicates": len(_valid(hold_scores[MULTISCALE])),
                "frozen_threshold": multi_dev.get("frozen_threshold"),
                "threshold_grid": thresholds[MULTISCALE]["threshold_grid_by_series"][series_id],
                "risk_validation_status": _risk_status(multi_dev, multi_hold),
                "shared_null_paths": True,
            },
            BOCPD: {
                "development": bocpd_dev.get("development", {}),
                "development_status": bocpd_dev.get("status"),
                "development_valid_replicates": len(_valid(
                    dev_scores[BOCPD].get(
                        f"{float(thresholds[BOCPD]['short_mass_threshold_grid'][-1]):.6f}", []
                    )
                )),
                "development_grid": bocpd_dev.get("grid", []),
                "holdout": bocpd_hold,
                "holdout_valid_replicates": (
                    len(_valid(bocpd_hold_scores)) if bocpd_hold_scores is not None else 0
                ),
                "frozen_threshold": frozen_mass,
                "persistence": 3,
                "short_mass_threshold_grid": thresholds[BOCPD]["short_mass_threshold_grid"],
                "risk_validation_status": _risk_status(bocpd_dev, bocpd_hold),
                "holdout_opened_only_for_development_selected_threshold": True,
                "shared_null_paths": True,
            },
            HUBER: {
                "development": huber_dev.get("development", {}),
                "development_status": huber_dev.get("status"),
                "development_valid_replicates": len(_valid(dev_scores[HUBER])),
                "development_grid": huber_dev.get("grid", []),
                "holdout": huber_hold,
                "holdout_valid_replicates": len(_valid(hold_scores[HUBER])),
                "frozen_threshold": huber_dev.get("frozen_threshold"),
                "threshold_grid": thresholds[HUBER]["threshold_grid"],
                "risk_validation_status": _risk_status(huber_dev, huber_hold),
                "shared_null_paths": True,
            },
        }

        series_events = [
            {
                **event, "series_id": series_id,
                "expected_sign": int(event["expected_sign_by_series"][series_id]),
            }
            for event in contract["events"]
            if series_id in event.get("expected_sign_by_series", {})
        ]
        historical, unmatched = _historical_for_series(
            series_id=series_id, rows=rows, values=values, events=series_events,
            calibrated=calibration, multi_detector=multi_detector,
        )
        event_rows.extend(historical)
        unmatched_all[series_id] = unmatched
        seed_ledgers[series_id] = series_seed_ledgers
        series_reports[series_id] = {
            "status": "EVALUATED",
            "observation_count": int(values.size),
            "frequency": rows[0]["frequency"],
            "series_transform": rows[0].get("series_transform", "level"),
            "analysis_units": rows[0]["units"],
            "first_observation": rows[0]["observation_date"],
            "last_observation": rows[-1]["observation_date"],
            "first_available_at": rows[0]["available_at"],
            "last_available_at": rows[-1]["available_at"],
            "ar_model": {key: c3.clean(model.get(key)) for key in (
                "order", "intercept", "ar_coefficients", "residual_sigma",
                "residual_pool_sha256", "aic", "roots_abs",
            )},
            "seed_ledgers": series_seed_ledgers,
            "calibration": calibration,
            "null_trace_protocol": {
                "development_replicates": replicates,
                "holdout_replicates": replicates,
                "holdout_seed_phase_disjoint": True,
                "same_null_trace_shared_across_arms": True,
                "holdout_threshold_selection": False,
            },
        }
        print(
            f"C3_V2_4_SERIES_COMPLETE {series_id} "
            + " ".join(
                f"{name}={calibration[name]['risk_validation_status']}"
                for name in (MULTISCALE, BOCPD, HUBER)
            ),
            flush=True,
        )

    expected_pairs = sum(
        1 for event in contract["events"]
        for series_id in target_series
        if series_id in event.get("expected_sign_by_series", {})
    )
    if expected_pairs != 35:
        raise ValueError(f"C3_V2_4_EXPECTED_35_EVENT_SERIES_PAIRS:{expected_pairs}")
    if any(series_reports.get(sid, {}).get("status") != "EVALUATED" for sid in target_series):
        status = "COMPLETED_WITH_SERIES_EXCEPTIONS"
    else:
        status = "COMPLETED_WITH_VALIDATION_RESULTS"

    detector_summary = _summarize_historical(
        event_rows, unmatched_all, target_by_series, event_episodes
    )
    total_matches = {
        name: sum(
            1 for row in event_rows
            if row["detector"] == name and row["hit_miss"] == "HIT"
        )
        for name in (MULTISCALE, BOCPD, HUBER)
    }
    return {
        "schema_version": "1.0.0",
        "experiment_id": "C3_V2_4_MULTISCALE_ADAPTIVE_2000X2_V1",
        "status": status,
        "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL_REPLAY"),
        "evaluation_commit": os.environ.get("GITHUB_SHA", "LOCAL_REPLAY"),
        "protocol_sha256": _sha256(protocol_bytes),
        "source_integrity": {
            "source_intake_run_id": manifest.get("workflow_run_id"),
            "repacked_source_archive_sha256": archive_sha,
            "source_artifact_id": protocol["source"]["source_artifact_id"],
            "source_artifact_zip_sha256": protocol["source"]["source_artifact_zip_sha256"],
            "normalized_tape_sha256": manifest["normalized_tape"]["sha256"],
            "contract_sha256": contract_sha,
            "analysis_tape_sha256": analysis_tape_sha,
            "analysis_transforms": transform_audit,
            "source_archive_mutated": False,
        },
        "protocol": protocol,
        "series": series_reports,
        "historical_results": event_rows,
        "unmatched_alarm_summary": unmatched_all,
        "historical_diagnostic_summary": detector_summary,
        "historical_pair_count": expected_pairs,
        "historical_total_matches_within_pm_12m": total_matches,
        "historical_episode_ids": sorted(event_episodes),
        "historical_matching_is_diagnostic_only": True,
        "seed_ledgers": seed_ledgers,
        "replay_command": (
            "python p1_4_validation/c3/run_c3_v2_4_multiscale.py "
            "--source-zip <repacked-frozen-source-intake.zip> "
            "--contract p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json "
            "--protocol p1_4_validation/c3/c3_v2_4_multiscale_preregistration.json "
            "--expected-source-run-id 45757611871 --replicates 2000 "
            "--output-dir artifacts/p1_4/c3/v2_4_multiscale_adaptive"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True)
    parser.add_argument(
        "--contract",
        default="p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json",
    )
    parser.add_argument("--protocol", default=str(PROTOCOL_PATH))
    parser.add_argument("--expected-source-run-id", required=True)
    parser.add_argument("--replicates", type=int, default=2000)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    report = run(args)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / OUT_NAME
    report_bytes = _canonical_json(report)
    report_path.write_bytes(report_bytes)
    report_sha = _sha256(report_bytes)

    manifest = {
        "schema_version": "1.0.0",
        "run_id": report["run_id"],
        "evaluation_commit": report["evaluation_commit"],
        "protocol_sha256": report["protocol_sha256"],
        "source_intake_run_id": report["source_integrity"]["source_intake_run_id"],
        "repacked_source_archive_sha256": report["source_integrity"]["repacked_source_archive_sha256"],
        "source_artifact_id": report["source_integrity"]["source_artifact_id"],
        "source_artifact_zip_sha256": report["source_integrity"]["source_artifact_zip_sha256"],
        "normalized_tape_sha256": report["source_integrity"]["normalized_tape_sha256"],
        "evaluation_contract_sha256": report["source_integrity"]["contract_sha256"],
        "analysis_tape_sha256": report["source_integrity"]["analysis_tape_sha256"],
        "report_path": report_path.name,
        "report_sha256": report_sha,
        "seed_namespace": report["protocol"]["null_protocol"]["seed_namespace"],
        "seed_ledgers": report["seed_ledgers"],
        "replay_command": report["replay_command"],
    }
    manifest_path = output / MANIFEST_NAME
    manifest_bytes = _canonical_json(manifest)
    manifest_path.write_bytes(manifest_bytes)
    print(json.dumps({
        "experiment_id": report["experiment_id"],
        "status": report["status"],
        "run_id": report["run_id"],
        "report": str(report_path),
        "report_sha256": report_sha,
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_bytes),
        "historical_diagnostic_summary": report["historical_diagnostic_summary"],
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
