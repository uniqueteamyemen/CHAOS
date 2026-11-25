"""P1.4 C2 frozen-cohort generalization pilot.

Reuses the immutable v1.1.9 protocol, exact C2 selection and existing detector
implementations. This runner does not edit calibration or detection algorithms.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np

from p1_4_validation import run_evidence_pipeline as base

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_C2_COUNT = 20
EXPECTED_PROTOCOL_VERSION = "1.1.9"
EXPECTED_PROTOCOL_GIT_BLOB = "2ad0db0654bd1d9dd42c87c5cdb531f9b2aa3a2d"
EXPECTED_COHORT_MANIFEST_GIT_BLOB = "2a9ca14b501567f06840d047597d3a24398c31f2"
EXPECTED_P2C_ENGINE_GIT_BLOB = "5efcf408822551e00cb87c24e39502dcf0ed595a"
EXPECTED_PROTOCOL_SHA256 = "d4ce2b84ade5d8662e22b4cdc020f0f39a88566aced3eff1bfefd478b75645e4"
TOOLS = {
    "FOCUS": ("FOCUS", None),
    "POST_QUIET_HUBER_MAD": ("POST_QUIET_HUBER_MAD", "mad"),
    "POST_QUIET_HUBER_BARTLETT": ("POST_QUIET_HUBER_BARTLETT", "bartlett"),
}
POSITIONS = (0.30, 0.50, 0.70)


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], text=True
    ).strip()


def assert_frozen_sources() -> None:
    expected = {
        ROOT / "p1_4_validation" / "pilot_protocol.json": EXPECTED_PROTOCOL_GIT_BLOB,
        ROOT / "p1_4_validation" / "cohort_manifest.json": EXPECTED_COHORT_MANIFEST_GIT_BLOB,
        ROOT / "p2_b_benchmark" / "p2c_engine.py": EXPECTED_P2C_ENGINE_GIT_BLOB,
    }
    for path, digest in expected.items():
        actual = git_blob(path)
        if actual != digest:
            raise ValueError(f"FROZEN_SOURCE_CHANGED:{path.relative_to(ROOT)}:{actual}")


def load_context(args: argparse.Namespace) -> dict[str, Any]:
    assert_frozen_sources()
    ctx = base.load_inputs(args)
    protocol = ctx["protocol"]
    if protocol.get("protocol_version") != EXPECTED_PROTOCOL_VERSION:
        raise ValueError("C2_PROTOCOL_VERSION_MISMATCH")
    if ctx["source_sha256"]["protocol"] != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("C2_PROTOCOL_SHA256_MISMATCH")

    manifest_ids = sorted(str(x) for x in ctx["manifest"]["cohorts"]["C2"]["pilot_series_ids"])
    scope_ids = sorted(str(x) for x in ctx["c2_ids"])
    selected = ctx["selection"].get("c2", {}).get("pilot_series", [])
    selected_by_id = {str(x["series_id"]): x for x in selected}
    if len(manifest_ids) != EXPECTED_C2_COUNT or manifest_ids != scope_ids:
        raise ValueError("C2_FROZEN_MANIFEST_IDENTITY_MISMATCH")
    if len(selected_by_id) != EXPECTED_C2_COUNT or sorted(selected_by_id) != manifest_ids:
        raise ValueError("C2_SELECTION_ARTIFACT_IDENTITY_MISMATCH")
    if len(selected_by_id) != len(selected):
        raise ValueError("C2_SELECTION_DUPLICATE_SERIES")

    # C2 is the exact frozen stable/stratified 20-series Pilot subset.
    # Missing values/gaps or candidate hashes cannot be silently substituted.
    for sid in manifest_ids:
        meta = selected_by_id[sid]
        source = ctx["series"].get(sid)
        if source is None:
            raise ValueError(f"C2_SOURCE_SERIES_MISSING:{sid}")
        if int(meta.get("missing_month_count", -1)) != 0 or int(meta.get("missing_value_count", -1)) != 0:
            raise ValueError(f"C2_STABLE_SERIES_HAS_GAPS:{sid}")
        digest = base.candidate_sha256(source)
        if digest != meta.get("candidate_sha256"):
            raise ValueError(f"C2_CANDIDATE_SHA_MISMATCH:{sid}")
        if int(meta.get("observations", -1)) != len(source["values"]):
            raise ValueError(f"C2_OBSERVATION_COUNT_MISMATCH:{sid}")
        ctx["candidate_hashes"][sid] = digest
        ctx["classes"][sid] = "C2_FROZEN_STABLE_STRATIFIED_SAMPLE"

    ctx["c2_ids"] = manifest_ids
    ctx["c2_selection_by_id"] = selected_by_id
    return ctx


def calibrate_one(sid: str, ctx: dict[str, Any], out: Path, deadline: float) -> dict[str, Any]:
    if sid not in ctx["c2_ids"]:
        raise ValueError(f"SERIES_NOT_IN_FROZEN_C2_PILOT:{sid}")
    x = np.asarray(ctx["series"][sid]["values"], dtype=float)
    n = len(x)
    row: dict[str, Any] = {
        "series_id": sid, "cohort": "C2",
        "g1_failure_class": "NOT_APPLICABLE_C2_COMPLEMENT",
        "candidate_sha256": ctx["candidate_hashes"][sid],
        "series_length": n,
        "protocol_version": ctx["protocol"]["protocol_version"],
        "protocol_sha256": ctx["source_sha256"]["protocol"],
        "source_sha256": ctx["source_sha256"],
        "positions": {}, "calibration_status": "STARTED",
    }
    for pos in POSITIONS:
        if time.monotonic() >= deadline:
            row["calibration_status"] = "PARTIAL_TIME_BUDGET"
            break
        onset = int(math.floor(pos * n))
        model = base.select_ar_model(x[:onset])
        key = f"{pos:.2f}"
        position: dict[str, Any] = {
            "position_fraction": pos, "break_index": onset,
            "ar_model_status": model.get("status"),
            "ar_model_reason": model.get("reason"),
            "ar_order": model.get("order"),
            "ar_coefficients": model.get("ar_coefficients"),
            "residual_sigma": model.get("residual_sigma"),
            "residual_pool_sha256": model.get("residual_pool_sha256"),
            "arms": {},
        }
        if model.get("status") != "OK":
            position["status"] = "NOT_ELIGIBLE"
            position["reason"] = model.get("reason")
            for tool, (arm_name, _mode) in TOOLS.items():
                position["arms"][arm_name] = {
                    "status": "NOT_ELIGIBLE",
                    "reason": model.get("reason"),
                    "frozen_threshold": None,
                    "holdout": {"status": "NOT_CALIBRATED"},
                    "development_max_statistics": [],
                    "holdout_max_statistics": [],
                    "valid_development_replicates": 0,
                    "valid_holdout_replicates": 0,
                }
            row["positions"][key] = position
            base.write_json(out / f"series-{base.safe_id(sid)}.json", row)
            continue

        bank = {
            phase: {arm: [] for arm in ("FOCUS", "POST_QUIET_HUBER_MAD", "POST_QUIET_HUBER_BARTLETT")}
            for phase in ("development", "holdout")
        }
        ledgers: dict[str, str] = {}
        partial = False
        for phase in ("development", "holdout"):
            seeds = base.seed_ledger(ctx["protocol"]["protocol_version"], sid, pos, int(model["order"]), phase)
            ledgers[phase] = base.sha_bytes(base.canon(seeds))
            for seed in seeds:
                if time.monotonic() >= deadline:
                    partial = True
                    break
                trace = base.generate_ar_null_trace(model, x[:int(model["order"])], n, seed)
                for arm, score in base.detector_maxima(trace).items():
                    if score is not None:
                        bank[phase][arm].append(score)
            if partial:
                break
        if partial:
            position["status"] = "PARTIAL_TIME_BUDGET"
            position["partial_replicates"] = {
                phase: {arm: len(values) for arm, values in arms.items()}
                for phase, arms in bank.items()
            }
            row["positions"][key] = position
            row["calibration_status"] = "PARTIAL_TIME_BUDGET"
            base.write_json(out / f"series-{base.safe_id(sid)}.json", row)
            break

        grids = {
            "FOCUS": base.FOCUS_GRID,
            "POST_QUIET_HUBER_MAD": base.HUBER_GRID,
            "POST_QUIET_HUBER_BARTLETT": base.HUBER_GRID,
        }
        for arm_name, grid in grids.items():
            development = bank["development"][arm_name]
            holdout = bank["holdout"][arm_name]
            fit = base.calibrate_threshold(
                development, grid, p0_target=base.P0, minimum_valid_replicates=950
            )
            threshold = fit.get("threshold") if fit.get("status") == "CALIBRATED" else None
            status = fit.get("status", "INCONCLUSIVE")
            if arm_name == "FOCUS" and n < 150:
                status = "NOT_ELIGIBLE"
            position["arms"][arm_name] = {
                "status": status,
                "development": fit,
                "frozen_threshold": threshold,
                "holdout": base.p0_result(holdout, float(threshold)) if threshold is not None else {"status": "NOT_CALIBRATED"},
                "development_max_statistics": development,
                "holdout_max_statistics": holdout,
                "development_seed_ledger_sha256": ledgers["development"],
                "holdout_seed_ledger_sha256": ledgers["holdout"],
                "valid_development_replicates": len(development),
                "valid_holdout_replicates": len(holdout),
            }
        position["status"] = position["arms"]["FOCUS"]["status"]
        row["positions"][key] = position
        base.write_json(out / f"series-{base.safe_id(sid)}.json", row)

    if len(row["positions"]) == len(POSITIONS) and row["calibration_status"] == "STARTED":
        row["calibration_status"] = "COMPLETE"
    elif row["calibration_status"] == "STARTED":
        row["calibration_status"] = "PARTIAL"
    row["replay_command"] = (
        "python p1_4_validation/run_c2_stable_pilot.py --phase calibrate "
        f"--series-id {sid} --prepared-zip /tmp/p2-prepared.zip "
        "--manifest p1_4_validation/cohort_manifest.json "
        "--protocol p1_4_validation/pilot_protocol.json "
        "--selection-json /tmp/cohort_selection.json "
        "--g1-shards-dir /tmp/p2-g1-shards "
        f"--output artifacts/p1_4/c2/calibration/{base.safe_id(sid)}"
    )
    path = out / f"series-{base.safe_id(sid)}.json"
    base.write_json(path, row)
    artifact_sha = base.sha_file(path)
    base.write_json(out / "calibration_job_manifest.json", {
        "artifact_type": "P1_4_C2_CALIBRATION_JOB",
        "cohort": "C2", "series_id": sid,
        "candidate_sha256": row["candidate_sha256"],
        "status": row["calibration_status"],
        "artifact_sha256": artifact_sha,
        "source_commit": os.environ.get("GITHUB_SHA"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "protocol_sha256": ctx["source_sha256"]["protocol"],
        "runner_sha256": base.sha_file(Path(__file__)),
        "replay_command": row["replay_command"],
    })
    return row



def load_calibrations(folder: Path, ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    job_manifests: dict[str, dict[str, Any]] = {}
    manifest_paths = sorted(Path(folder).rglob("calibration_job_manifest.json"))
    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sid = str(manifest.get("series_id"))
        if sid in job_manifests:
            raise ValueError(f"C2_DUPLICATE_CALIBRATION_JOB_MANIFEST:{sid}")
        if manifest.get("artifact_type") != "P1_4_C2_CALIBRATION_JOB":
            raise ValueError(f"C2_CALIBRATION_JOB_MANIFEST_TYPE_MISMATCH:{sid}")
        if manifest.get("cohort") != "C2" or sid not in ctx["c2_ids"]:
            raise ValueError(f"C2_CALIBRATION_JOB_MANIFEST_SCOPE_MISMATCH:{sid}")
        if manifest.get("protocol_sha256") != ctx["source_sha256"]["protocol"]:
            raise ValueError(f"C2_CALIBRATION_JOB_PROTOCOL_MISMATCH:{sid}")
        if manifest.get("candidate_sha256") != ctx["candidate_hashes"][sid]:
            raise ValueError(f"C2_CALIBRATION_JOB_CANDIDATE_MISMATCH:{sid}")
        if manifest.get("status") != "COMPLETE":
            raise ValueError(f"C2_CALIBRATION_JOB_NOT_COMPLETE:{sid}")
        series_path = manifest_path.parent / f"series-{base.safe_id(sid)}.json"
        if not series_path.is_file():
            raise ValueError(f"C2_CALIBRATION_SERIES_FILE_MISSING:{sid}")
        actual_sha = base.sha_file(series_path)
        if actual_sha != manifest.get("artifact_sha256"):
            raise ValueError(f"C2_CALIBRATION_SERIES_SHA_MISMATCH:{sid}")
        job_manifests[sid] = manifest

    for path in sorted(Path(folder).rglob("series-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        sid = str(row.get("series_id"))
        if sid in rows:
            raise ValueError(f"C2_DUPLICATE_CALIBRATION:{sid}")
        if sid not in job_manifests:
            raise ValueError(f"C2_CALIBRATION_JOB_MANIFEST_MISSING:{sid}")
        if row.get("cohort") != "C2":
            raise ValueError(f"C2_CALIBRATION_WRONG_COHORT:{sid}")
        if sid not in ctx["c2_ids"]:
            raise ValueError(f"C2_UNEXPECTED_CALIBRATION:{sid}")
        if row.get("candidate_sha256") != ctx["candidate_hashes"][sid]:
            raise ValueError(f"C2_CALIBRATION_CANDIDATE_HASH_MISMATCH:{sid}")
        if row.get("protocol_sha256") != ctx["source_sha256"]["protocol"]:
            raise ValueError(f"C2_CALIBRATION_PROTOCOL_MISMATCH:{sid}")
        if row.get("source_sha256", {}).get("prepared_zip") != ctx["source_sha256"]["prepared_zip"]:
            raise ValueError(f"C2_CALIBRATION_SOURCE_MISMATCH:{sid}")
        if row.get("calibration_status") != "COMPLETE":
            raise ValueError(f"C2_CALIBRATION_ROW_INCOMPLETE:{sid}")
        rows[sid] = row
    missing = sorted(set(ctx["c2_ids"]) - set(rows))
    missing_manifests = sorted(set(ctx["c2_ids"]) - set(job_manifests))
    if missing or missing_manifests or len(rows) != EXPECTED_C2_COUNT or len(job_manifests) != EXPECTED_C2_COUNT:
        raise ValueError(f"C2_CALIBRATION_SET_INCOMPLETE:rows={missing}:manifests={missing_manifests}")
    return rows



def calibration_and_holdout(rows: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary: dict[str, Any] = {}
    cells: list[dict[str, Any]] = []
    for tool, (arm_name, _mode) in TOOLS.items():
        full_pass = []
        per_position = {f"{p:.2f}": 0 for p in POSITIONS}
        statuses = {"CALIBRATED": 0, "NOT_CALIBRATABLE": 0, "NOT_ELIGIBLE": 0, "INCONCLUSIVE": 0}
        for sid, row in rows.items():
            positions = row.get("positions", {})
            all_positions = True
            for pos in POSITIONS:
                key = f"{pos:.2f}"
                position = positions.get(key, {})
                arm = position.get("arms", {}).get(arm_name)
                status = str(arm.get("status")) if arm else str(position.get("status", "NOT_ELIGIBLE"))
                if status not in statuses:
                    status = "INCONCLUSIVE"
                statuses[status] += 1
                if status == "CALIBRATED":
                    per_position[key] += 1
                    threshold = arm.get("frozen_threshold")
                    raw = arm.get("holdout_max_statistics", [])
                    stored = arm.get("holdout", {})
                    if threshold is None:
                        raise ValueError(f"C2_CALIBRATED_WITHOUT_THRESHOLD:{sid}:{tool}:{key}")
                    recomputed = base.p0_result(raw, float(threshold))
                    if int(recomputed["alarm_traces"]) != int(stored.get("alarm_traces", -1)):
                        raise ValueError(f"C2_HOLDOUT_RAW_COUNT_MISMATCH:{sid}:{tool}:{key}")
                    if int(recomputed["valid_replicates"]) != int(stored.get("valid_replicates", -1)):
                        raise ValueError(f"C2_HOLDOUT_VALID_COUNT_MISMATCH:{sid}:{tool}:{key}")
                    for field in ("p0", "wilson_upper_95_one_sided"):
                        left, right = recomputed.get(field), stored.get(field)
                        if left is None or right is None or not math.isclose(float(left), float(right), rel_tol=0, abs_tol=1e-12):
                            raise ValueError(f"C2_HOLDOUT_SUMMARY_MISMATCH:{sid}:{tool}:{key}:{field}")
                    valid = int(recomputed["valid_replicates"])
                    upper = recomputed["wilson_upper_95_one_sided"]
                    gate = "INCONCLUSIVE" if valid < 950 or upper is None else ("PASS" if upper <= 0.10 else "FAIL")
                    cells.append({
                        "tool": tool, "series_id": sid, "position": key,
                        "threshold": float(threshold), "valid_replicates": valid,
                        "alarm_traces": int(recomputed["alarm_traces"]),
                        "p0": float(recomputed["p0"]),
                        "wilson_upper_95_one_sided": float(upper) if upper is not None else None,
                        "gate": gate,
                    })
                else:
                    all_positions = False
                    cells.append({
                        "tool": tool, "series_id": sid, "position": key,
                        "threshold": None, "valid_replicates": 0,
                        "alarm_traces": None, "p0": None,
                        "wilson_upper_95_one_sided": None,
                        "gate": status,
                    })
                all_positions = all_positions and status == "CALIBRATED"
            if all_positions:
                full_pass.append(sid)
        tool_cells = [x for x in cells if x["tool"] == tool]
        gates = [x["gate"] for x in tool_cells]
        summary[tool] = {
            "fully_calibrated_series": len(full_pass),
            "planned_series": EXPECTED_C2_COUNT,
            "calibration_pass_rate": len(full_pass) / EXPECTED_C2_COUNT,
            "fully_calibrated_ids": sorted(full_pass),
            "calibration_status_counts_by_position": per_position,
            "position_status_counts": statuses,
            "holdout_cells": len(tool_cells),
            "holdout_pass_cells": gates.count("PASS"),
            "holdout_fail_cells": gates.count("FAIL"),
            "holdout_inconclusive_cells": gates.count("INCONCLUSIVE"),
            "holdout_not_calibrated_or_not_eligible_cells": sum(x not in {"PASS", "FAIL", "INCONCLUSIVE"} for x in gates),
            "holdout_gate": "PASS" if gates and all(x == "PASS" for x in gates) else "PARTIAL_OR_INCONCLUSIVE",
        }
    return summary, cells


def _detect(tool: str, values: np.ndarray, sid: str, case: dict[str, Any],
            calibration: dict[str, Any]) -> dict[str, Any]:
    pos = float(case["position_fraction"])
    key = f"{pos:.2f}"
    arm_name, mode = TOOLS[tool]
    arm = calibration.get("positions", {}).get(key, {}).get("arms", {}).get(arm_name, {})
    if arm.get("status") != "CALIBRATED" or arm.get("frozen_threshold") is None:
        return {"status": "NOT_ELIGIBLE", "reason": arm.get("status", "NO_FROZEN_THRESHOLD")}
    if tool == "FOCUS":
        if len(values) < 150:
            return {"status": "NOT_ELIGIBLE", "reason": "FOCUS_MIN_N_150_REQUIRED"}
        result = base.focus_reset_rearm(values, threshold=float(arm["frozen_threshold"]))
    else:
        result = base.post_quiet_huber_detector(
            values, scale_mode=str(mode), threshold=float(arm["frozen_threshold"])
        )
    if result.get("status") != "OK":
        return {"status": "ABSTAIN", "reason": result.get("reason", result.get("status"))}
    intervals = result.get("rearm_intervals", []) if tool == "FOCUS" else []
    outcome = base.evaluate_online_hits(
        result.get("hits", []),
        true_break_index=int(case["true_break_index"]),
        true_direction=int(case["direction"]),
        rearm_intervals=intervals,
    )
    return {
        **outcome,
        "threshold": float(arm["frozen_threshold"]),
        "hit_count": len(result.get("hits", [])),
    }


def _original_alarm_count(tool: str, values: np.ndarray, calibration: dict[str, Any]) -> dict[str, Any]:
    arm_name, mode = TOOLS[tool]
    arm = calibration.get("positions", {}).get("0.30", {}).get("arms", {}).get(arm_name, {})
    if arm.get("status") != "CALIBRATED" or arm.get("frozen_threshold") is None:
        return {"status": "NOT_ELIGIBLE", "alarm_count": None}
    if tool == "FOCUS":
        if len(values) < 150:
            return {"status": "NOT_ELIGIBLE", "alarm_count": None}
        result = base.focus_reset_rearm(values, threshold=float(arm["frozen_threshold"]))
    else:
        result = base.post_quiet_huber_detector(values, scale_mode=str(mode), threshold=float(arm["frozen_threshold"]))
    return {
        "status": result.get("status"),
        "alarm_count": len(result.get("hits", [])),
        "interpretation": "DESCRIPTIVE_ORIGINAL_SERIES_BURDEN_NOT_LABELLED_FALSE_POSITIVES",
    }


def run_injection_pilot(ctx: dict[str, Any], calibrations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    series_results: dict[str, Any] = {}
    for sid in ctx["c2_ids"]:
        x = np.asarray(ctx["series"][sid]["values"], dtype=float)
        calibration = calibrations[sid]
        original = {tool: _original_alarm_count(tool, x, calibration) for tool in TOOLS}
        case_rows = []
        for index, injected in enumerate(base.injection_grid(x)):
            case = {
                "case_index": index + 1,
                "kind": "INJECTION",
                "magnitude_sigma": injected.get("magnitude_sigma", (0.5, 1.0, 2.0)[index // 6]),
                "position_fraction": injected.get("position_fraction", (0.30, 0.50, 0.70)[(index % 6) // 2]),
                "direction": injected.get("direction", (-1, 1)[index % 2]),
                "true_break_index": injected.get("true_break_index", int(math.floor((0.30, 0.50, 0.70)[(index % 6) // 2] * len(x))),
                "injection_status": injected.get("status"),
                "injection_reason": injected.get("reason"),
                "tool_outcomes": {},
            }
            for tool in TOOLS:
                if injected.get("status") != "OK":
                    outcome = {"status": "NOT_ELIGIBLE", "reason": injected.get("reason")}
                else:
                    outcome = _detect(tool, np.asarray(injected["values"], dtype=float), sid, injected, calibration)
                case["tool_outcomes"][tool] = outcome
            case_rows.append(case)
        if len(case_rows) != 18:
            raise ValueError(f"C2_INJECTION_GRID_SIZE_MISMATCH:{sid}")
        series_results[sid] = {
            "series_length": len(x),
            "candidate_sha256": ctx["candidate_hashes"][sid],
            "original_alarm_burden": original,
            "planned_injections": 18,
            "executed_injection_cases": case_rows,
        }
    return {"status": "COMPLETE", "cohort": "C2", "series_count": len(series_results), "series": series_results}


def _rate(tp: int, miss: int) -> float | None:
    denominator = tp + miss
    return tp / denominator if denominator else None


def _cluster_ci(per_series: dict[str, dict[str, Any]], metric: str, seed: int) -> list[float] | None:
    values = np.asarray([float(row[metric]) for row in per_series.values() if row.get(metric) is not None], dtype=float)
    if len(values) == 0:
        return None
    rng = np.random.default_rng(seed)
    draws = np.asarray([np.mean(rng.choice(values, size=len(values), replace=True)) for _ in range(2000)])
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def summarize_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    all_metrics: dict[str, Any] = {}
    for tool_index, tool in enumerate(TOOLS):
        totals = {
            "planned": 0, "tp": 0, "miss": 0, "invalid": 0,
            "not_eligible": 0, "abstain": 0, "evaluated": 0,
            "pre_onset_cases": 0, "pre_onset_events": 0, "wrong_direction_events": 0,
        }
        direction = {
            1: {"tp": 0, "miss": 0, "invalid": 0, "not_eligible": 0, "abstain": 0},
            -1: {"tp": 0, "miss": 0, "invalid": 0, "not_eligible": 0, "abstain": 0},
        }
        per_series: dict[str, dict[str, Any]] = {}
        for sid, series in pilot["series"].items():
            local = {
                "positive_tp": 0, "positive_miss": 0,
                "negative_tp": 0, "negative_miss": 0,
                "evaluated": 0, "pre_onset_cases": 0, "pre_onset_events": 0,
            }
            for case in series["executed_injection_cases"]:
                outcome = case["tool_outcomes"][tool]
                sign = case.get("direction")
                sign = int(sign) if sign in (-1, 1) else None
                status = outcome.get("status", "NOT_ELIGIBLE")
                totals["planned"] += 1
                if status in {"DETECTED", "MISSED", "INVALID_INJECTION"}:
                    totals["evaluated"] += 1
                    local["evaluated"] += 1
                    pre = int(outcome.get("pre_onset_alert_count", 0))
                    totals["pre_onset_events"] += pre
                    local["pre_onset_events"] += pre
                    if pre:
                        totals["pre_onset_cases"] += 1
                        local["pre_onset_cases"] += 1
                    wrong = int(outcome.get("wrong_direction_alert_count", 0))
                    totals["wrong_direction_events"] += wrong
                if status == "DETECTED":
                    totals["tp"] += 1
                    if sign is not None:
                        direction[sign]["tp"] += 1
                        local["positive_tp" if sign == 1 else "negative_tp"] += 1
                elif status == "MISSED":
                    totals["miss"] += 1
                    if sign is not None:
                        direction[sign]["miss"] += 1
                        local["positive_miss" if sign == 1 else "negative_miss"] += 1
                elif status == "INVALID_INJECTION":
                    totals["invalid"] += 1
                    if sign is not None:
                        direction[sign]["invalid"] += 1
                elif status == "ABSTAIN":
                    totals["abstain"] += 1
                    if sign is not None:
                        direction[sign]["abstain"] += 1
                else:
                    totals["not_eligible"] += 1
                    if sign is not None:
                        direction[sign]["not_eligible"] += 1
            per_series[sid] = {
                "positive_recall": _rate(local["positive_tp"], local["positive_miss"]),
                "negative_recall": _rate(local["negative_tp"], local["negative_miss"]),
                "pre_onset_cases": local["pre_onset_cases"],
                "evaluated_cases": local["evaluated"],
                "pre_onset_rate": local["pre_onset_cases"] / local["evaluated"] if local["evaluated"] else None,
            }
        positive = direction[1]
        negative = direction[-1]
        pos_recall = _rate(positive["tp"], positive["miss"])
        neg_recall = _rate(negative["tp"], negative["miss"])
        # Mean series recall is derived from the per-series positive/negative case counts below.
        recall_values = []
        for sid, series in pilot["series"].items():
            tp = miss = 0
            for case in series["executed_injection_cases"]:
                o = case["tool_outcomes"][tool]
                if o.get("status") == "DETECTED":
                    tp += 1
                elif o.get("status") == "MISSED":
                    miss += 1
            value = _rate(tp, miss)
            if value is not None:
                recall_values.append(value)
        mean_series_recall = float(np.mean(recall_values)) if recall_values else None
        per_series_recall = {sid: {"recall": _rate(
            sum(c["tool_outcomes"][tool].get("status") == "DETECTED" for c in series["executed_injection_cases"]),
            sum(c["tool_outcomes"][tool].get("status") == "MISSED" for c in series["executed_injection_cases"]),
        )} for sid, series in pilot["series"].items()}
        recall_ci = _cluster_ci(per_series_recall, "recall", 20261126 + tool_index)
        pos_ci = _cluster_ci(per_series, "positive_recall", 20261226 + tool_index)
        neg_ci = _cluster_ci(per_series, "negative_recall", 20261326 + tool_index)
        all_metrics[tool] = {
            **totals,
            "recall": _rate(totals["tp"], totals["miss"]),
            "positive_recall": pos_recall,
            "negative_recall": neg_recall,
            "positive_minus_negative_recall": (pos_recall - neg_recall) if pos_recall is not None and neg_recall is not None else None,
            "pre_onset_rate": totals["pre_onset_cases"] / totals["evaluated"] if totals["evaluated"] else None,
            "series_mean_recall": mean_series_recall,
            "series_cluster_bootstrap_95_recall": recall_ci,
            "series_cluster_bootstrap_95_positive": pos_ci,
            "series_cluster_bootstrap_95_negative": neg_ci,
            "directional_counts": {"positive": positive, "negative": negative},
            "per_series": per_series,
        }
    return all_metrics


def make_markdown(cal_summary: dict[str, Any], cells: list[dict[str, Any]],
                  metrics: dict[str, Any], pilot: dict[str, Any],
                  provenance: dict[str, Any]) -> str:
    lines = [
        "## P1.4 C2 Frozen Stable-Cohort Pilot",
        f"- Run: `{provenance['workflow_run_id']}`; commit: `{provenance['source_commit']}`",
        f"- Frozen C2 cohort: **{EXPECTED_C2_COUNT}/20 exact series**, no substitutions.",
        f"- Protocol: v{provenance['protocol_version']} / SHA-256 `{provenance['protocol_sha256']}` (unchanged).",
        "- Detector implementation unchanged; FOCuS, Huber-MAD and Huber-Bartlett use the original shared AR-null paths and frozen threshold grids.",
        "- Development nulls select thresholds; independent Holdout is evaluation only. No Holdout retuning.",
        "",
        "### Calibration Pass Rate (complete calibration at all three positions)",
        "| Detector arm | Fully calibrated series | Planned | Pass rate |",
        "|---|---:|---:|---:|",
    ]
    for tool in TOOLS:
        row = cal_summary[tool]
        lines.append(f"| {tool} | {row['fully_calibrated_series']} | 20 | {row['calibration_pass_rate']:.1%} |")
    lines.extend([
        "",
        "### Holdout P0 / one-sided Wilson U95 gate",
        "| Detector arm | Cells | Pass | Fail | Inconclusive | Not calibrated / not eligible | Overall cell gate |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])
    for tool in TOOLS:
        row = cal_summary[tool]
        lines.append(f"| {tool} | {row['holdout_cells']} | {row['holdout_pass_cells']} | {row['holdout_fail_cells']} | {row['holdout_inconclusive_cells']} | {row['holdout_not_calibrated_or_not_eligible_cells']} | {row['holdout_gate']} |")
    lines.extend([
        "",
        "### Injection detection, positive/negative balance and pre-onset alarms",
        "| Detector arm | Planned | TP | Miss | Invalid | Not eligible | Abstain | Recall | Positive recall | Negative recall | Pos−Neg | Pre-onset cases / evaluated | Pre-onset rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for tool, row in metrics.items():
        fmt = lambda v: "n/a" if v is None else f"{v:.1%}"
        lines.append(f"| {tool} | {row['planned']} | {row['tp']} | {row['miss']} | {row['invalid']} | {row['not_eligible']} | {row['abstain']} | {fmt(row['recall'])} | {fmt(row['positive_recall'])} | {fmt(row['negative_recall'])} | {fmt(row['positive_minus_negative_recall'])} | {row['pre_onset_cases']} / {row['evaluated']} | {fmt(row['pre_onset_rate'])} |")
    lines.extend([
        "",
        "### Holdout cells (all series × positions × detector arms)",
        "| Detector arm | Series ID | Position | Threshold | False alarms / valid | P0 | Wilson U95 | Gate |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ])
    for cell in cells:
        if cell["p0"] is None:
            lines.append(f"| {cell['tool']} | `{cell['series_id']}` | {cell['position']} | n/a | n/a | n/a | n/a | {cell['gate']} |")
        else:
            lines.append(f"| {cell['tool']} | `{cell['series_id']}` | {cell['position']} | {cell['threshold']:.3f} | {cell['alarm_traces']} / {cell['valid_replicates']} | {cell['p0']:.3%} | {cell['wilson_upper_95_one_sided']:.3%} | {cell['gate']} |")
    lines.extend([
        "",
        "### Per-series directional recall and pre-onset",
        "| Series ID | n | FOCuS + | FOCuS − | FOCuS pre-onset | MAD + | MAD − | MAD pre-onset | Bartlett + | Bartlett − | Bartlett pre-onset |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for sid, series in pilot["series"].items():
        row = [f"`{sid}`", str(series["series_length"])]
        for tool in TOOLS:
            m = metrics[tool]["per_series"][sid]
            fmt = lambda v: "n/a" if v is None else f"{v:.1%}"
            row.extend([fmt(m["positive_recall"]), fmt(m["negative_recall"]), fmt(m["pre_onset_rate"])])
        lines.append("| " + " | ".join(row) + " |")
    lines.extend([
        "",
        "### Interpretation boundaries",
        "- Pre-onset is measured on injected cases before their true break index; it is not adjudicated historical false-positive truth.",
        "- Original-series alarm counts are descriptive burden only and are not labelled false positives.",
        "- FOCuS n<150 is NOT_ELIGIBLE, not a miss; the frozen short C2 series is retained and not replaced.",
        "- This C2 run is a separate extension using the frozen v1.1.9 criteria; C3 historical event validation and production authorization remain pending.",
    ])
    return "\n".join(lines) + "\n"


def write_inventory(out: Path) -> None:
    inventory = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {"artifact_sha256_inventory.json", "SHA256SUMS.txt"}:
            inventory[path.relative_to(out).as_posix()] = base.sha_file(path)
    base.write_json(out / "artifact_sha256_inventory.json", inventory)
    (out / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(inventory.items())),
        encoding="utf-8",
    )


def postprocess(ctx: dict[str, Any], cal_dir: Path, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    calibrations = load_calibrations(cal_dir, ctx)
    cal_summary, cells = calibration_and_holdout(calibrations)
    pilot = run_injection_pilot(ctx, calibrations)
    metrics = summarize_pilot(pilot)
    base.write_json(out / "c2_calibration_and_holdout.json", {
        "cohort": "C2", "planned_series": 20,
        "protocol_sha256": ctx["source_sha256"]["protocol"],
        "summary": cal_summary, "holdout_cells": cells,
        "series": calibrations,
    })
    with (out / "c2_holdout_p0_cells.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "tool", "series_id", "position", "threshold", "valid_replicates",
            "alarm_traces", "p0", "wilson_upper_95_one_sided", "gate",
        ])
        writer.writeheader()
        writer.writerows(cells)
    base.write_json(out / "c2_injection_pilot.json", pilot)
    base.write_json(out / "c2_injection_metrics.json", metrics)
    provenance = {
        "artifact_type": "P1_4_C2_STABLE_PILOT_PROVENANCE",
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
        "workflow_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "source_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "protocol_version": ctx["protocol"]["protocol_version"],
        "protocol_sha256": ctx["source_sha256"]["protocol"],
        "cohort_manifest_sha256": ctx["source_sha256"]["manifest"],
        "selection_json_sha256": ctx["source_sha256"]["selection"],
        "prepared_zip_sha256": ctx["source_sha256"]["prepared_zip"],
        "c2_series_ids": ctx["c2_ids"],
        "candidate_sha256": ctx["candidate_hashes"],
        "runner_sha256": base.sha_file(Path(__file__)),
        "p2c_engine_git_blob_sha": git_blob(ROOT / "p2_b_benchmark" / "p2c_engine.py"),
        "recalibration_used_development_only": True,
        "holdout_used_for_threshold_selection": False,
        "protocol_or_detector_code_modified": False,
        "production_authorization": False,
        "replay_command": "See workflow run and artifacts; re-run with run_c2_stable_pilot.py --phase calibrate per C2 series, then --phase postprocess.",
    }
    base.write_json(out / "execution_provenance.json", provenance)
    markdown = make_markdown(cal_summary, cells, metrics, pilot, provenance)
    (out / "STEP_SUMMARY.md").write_text(markdown, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(markdown)
    print(markdown, flush=True)
    write_inventory(out)
    return {"calibration": cal_summary, "metrics": metrics, "provenance": provenance}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase", choices=("calibrate", "postprocess"), required=True)
    ap.add_argument("--series-id")
    ap.add_argument("--prepared-zip", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--selection-json", required=True)
    ap.add_argument("--g1-shards-dir", required=True)
    ap.add_argument("--calibration-dir")
    ap.add_argument("--output", required=True)
    ap.add_argument("--budget-hours", type=float, default=5.5)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    ctx = load_context(args)
    if args.phase == "calibrate":
        if not args.series_id:
            raise ValueError("C2_SERIES_ID_REQUIRED")
        result = calibrate_one(args.series_id, ctx, out, time.monotonic() + min(args.budget_hours * 3600, 330 * 60))
        if result.get("calibration_status") != "COMPLETE":
            raise RuntimeError(f"C2_CALIBRATION_INCOMPLETE:{args.series_id}:{result.get('calibration_status')}")
        return 0
    if not args.calibration_dir:
        raise ValueError("C2_CALIBRATION_DIR_REQUIRED")
    postprocess(ctx, Path(args.calibration_dir), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
