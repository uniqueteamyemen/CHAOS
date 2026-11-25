"""C1 arm-isolated Post-Quiet Huber Pilot reusing frozen calibration artifacts.

This runner deliberately does not import or call calibration generators. It consumes
only the SHA-pinned per-series artifacts from workflow run 45707752707.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p1_4_validation import run_evidence_pipeline as base  # noqa: E402
from p1_4_validation.injection_runner import evaluate_online_hits, injection_grid  # noqa: E402
from p2_b_benchmark.p2c_engine import post_quiet_huber_detector  # noqa: E402

POSITIONS = (0.30, 0.50, 0.70)
SCALE_CONFIG = {
    "MAD": {
        "calibration_arm": "POST_QUIET_HUBER_MAD",
        "scale_mode": "mad",
        "display_name": "Post-Quiet Huber / MAD",
        "output_name": "arm_isolated_pilot_mad.json",
    },
    "BARTLETT_LRV": {
        "calibration_arm": "POST_QUIET_HUBER_BARTLETT",
        "scale_mode": "bartlett",
        "display_name": "Post-Quiet Huber / Bartlett LRV",
        "output_name": "arm_isolated_pilot_bartlett_lrv.json",
    },
}
TOOLS = ("POST_QUIET_HUBER", "A_FAST", "A_CONSENSUS")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(canonical(value))
    temp.replace(path)


def read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON:{label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{label}")
    return value


def api_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError(f"GITHUB_API_OBJECT_REQUIRED:{url}")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Expose the signed artifact URL without forwarding the GitHub token."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact_bytes(url: str, token: str) -> bytes:
    """Authenticate only to api.github.com; fetch the signed redirect without credentials."""
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}",
                      "Accept": "application/vnd.github+json"},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as response:
        if response.code not in {301, 302, 303, 307, 308}:
            raise
        location = response.headers.get("Location")
        if not location or not location.startswith("https://"):
            raise ValueError("ARTIFACT_REDIRECT_URL_INVALID")
    # The URL is a short-lived signed URL. No GitHub Authorization header is sent.
    redirected = urllib.request.Request(location, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(redirected, timeout=120) as response:
        return response.read()


def download_pinned_calibrations(manifest_path: Path, output_dir: Path,
                                 token: str, repository: str) -> dict[str, Any]:
    """Download exactly the pinned 20 artifacts and verify GitHub + local SHA-256."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    run_id = int(manifest["source_workflow_run_id"])
    expected_sha = str(manifest["source_commit"])
    run = api_json(f"https://api.github.com/repos/{repository}/actions/runs/{run_id}", token)
    if run.get("head_sha") != expected_sha:
        raise ValueError("SOURCE_RUN_COMMIT_MISMATCH")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("SOURCE_RUN_NOT_SUCCESSFUL")
    if run.get("head_branch") != manifest["source_branch"]:
        raise ValueError("SOURCE_RUN_BRANCH_MISMATCH")

    api = api_json(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        token,
    )
    actual = {int(row["id"]): row for row in api.get("artifacts", [])
              if str(row.get("name", "")).startswith("p1-4-calibration-")}
    pins = manifest["calibration_artifacts"]
    if len(pins) != 20 or len(actual) != 20:
        raise ValueError(f"CALIBRATION_ARTIFACT_COUNT_MISMATCH:pinned={len(pins)}:actual={len(actual)}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    verified = []
    for pin in pins:
        artifact_id = int(pin["artifact_id"])
        row = actual.get(artifact_id)
        if row is None:
            raise ValueError(f"PINNED_ARTIFACT_MISSING:{artifact_id}")
        expected_digest = "sha256:" + str(pin["sha256"])
        if row.get("name") != pin["artifact_name"] or row.get("digest") != expected_digest:
            raise ValueError(f"GITHUB_ARTIFACT_METADATA_MISMATCH:{artifact_id}")
        if row.get("expired"):
            raise ValueError(f"PINNED_ARTIFACT_EXPIRED:{artifact_id}")
        if int(row.get("workflow_run", {}).get("id", -1)) != run_id:
            raise ValueError(f"ARTIFACT_RUN_BINDING_MISMATCH:{artifact_id}")
        if row.get("workflow_run", {}).get("head_sha") != expected_sha:
            raise ValueError(f"ARTIFACT_COMMIT_BINDING_MISMATCH:{artifact_id}")

        destination = output_dir / f"{pin['artifact_name']}.zip"
        if destination.exists() and sha256_file(destination) == pin["sha256"]:
            data_digest = pin["sha256"]
        else:
            url = f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip"
            data = download_artifact_bytes(url, token)
            data_digest = sha256_bytes(data)
            if data_digest != pin["sha256"]:
                raise ValueError(f"ARTIFACT_ZIP_SHA256_MISMATCH:{artifact_id}")
            temporary = destination.with_suffix(".zip.tmp")
            temporary.write_bytes(data)
            temporary.replace(destination)
        if data_digest != pin["sha256"]:
            raise ValueError(f"ARTIFACT_LOCAL_SHA256_MISMATCH:{artifact_id}")
        with zipfile.ZipFile(destination, "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"CORRUPT_ARTIFACT_MEMBER:{artifact_id}:{bad_member}")
        verified.append({"artifact_id": artifact_id,
                         "artifact_name": pin["artifact_name"],
                         "series_id": pin["series_id"],
                         "sha256": data_digest,
                         "size_bytes": destination.stat().st_size})
    return {"status": "PASS", "source_workflow_run_id": run_id,
            "source_commit": expected_sha, "verified_artifact_count": len(verified),
            "artifacts": verified}


def read_pinned_calibration_rows(artifact_dir: Path, manifest: dict[str, Any],
                                 ctx: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load series JSON only after ZIP digest, job manifest, commit and input checks."""
    rows: dict[str, Any] = {}
    evidence = []
    for pin in manifest["calibration_artifacts"]:
        path = Path(artifact_dir) / f"{pin['artifact_name']}.zip"
        if not path.is_file():
            raise ValueError(f"CALIBRATION_ARTIFACT_FILE_MISSING:{pin['artifact_id']}")
        actual_digest = sha256_file(path)
        if actual_digest != pin["sha256"]:
            raise ValueError(f"CALIBRATION_ARTIFACT_SHA256_MISMATCH:{pin['artifact_id']}")
        with zipfile.ZipFile(path, "r") as archive:
            names = [n for n in archive.namelist() if not n.endswith("/")]
            manifests = [n for n in names if Path(n).name == "calibration_job_manifest.json"]
            series_files = [n for n in names if Path(n).name.startswith("series-") and n.endswith(".json")]
            if len(manifests) != 1 or len(series_files) != 1 or len(names) != 2:
                raise ValueError(f"CALIBRATION_ARTIFACT_LAYOUT_INVALID:{pin['artifact_id']}")
            job = read_json_bytes(archive.read(manifests[0]), "calibration_job_manifest")
            row = read_json_bytes(archive.read(series_files[0]), "series_calibration")
        sid = str(pin["series_id"])
        if job.get("series_id") != sid or row.get("series_id") != sid:
            raise ValueError(f"CALIBRATION_SERIES_ID_MISMATCH:{sid}")
        if int(job.get("workflow_run_id", -1)) != int(manifest["source_workflow_run_id"]):
            raise ValueError(f"CALIBRATION_WORKFLOW_RUN_MISMATCH:{sid}")
        if job.get("source_commit") != manifest["source_commit"]:
            raise ValueError(f"CALIBRATION_COMMIT_MISMATCH:{sid}")
        if job.get("status") != "COMPLETE":
            raise ValueError(f"CALIBRATION_JOB_NOT_COMPLETE:{sid}")
        if job.get("protocol_sha256") != ctx["source_sha256"]["protocol"]:
            raise ValueError(f"CALIBRATION_PROTOCOL_SHA_MISMATCH:{sid}")
        if row.get("protocol_sha256") != ctx["source_sha256"]["protocol"]:
            raise ValueError(f"SERIES_PROTOCOL_SHA_MISMATCH:{sid}")
        if row.get("protocol_version") != manifest.get("protocol_version"):
            raise ValueError(f"SERIES_PROTOCOL_VERSION_MISMATCH:{sid}")
        if row.get("source_sha256") != ctx["source_sha256"]:
            raise ValueError(f"CALIBRATION_INPUT_SOURCE_HASHES_MISMATCH:{sid}")
        if row.get("candidate_sha256") != ctx["candidate_hashes"].get(sid):
            raise ValueError(f"CALIBRATION_CANDIDATE_HASH_MISMATCH:{sid}")
        if row.get("calibration_status") != "COMPLETE":
            raise ValueError(f"CALIBRATION_NOT_COMPLETE:{sid}")
        if sid in rows:
            raise ValueError(f"DUPLICATE_CALIBRATION_SERIES:{sid}")
        rows[sid] = row
        evidence.append({"series_id": sid, "artifact_id": int(pin["artifact_id"]),
                         "artifact_name": pin["artifact_name"], "artifact_zip_sha256": actual_digest,
                         "series_length": int(row["series_length"]),
                         "calibration_status": row["calibration_status"]})

    expected_ids = sorted(str(x) for x in ctx["c1_ids"])
    if sorted(rows) != expected_ids:
        raise ValueError("CALIBRATION_C1_IDENTITY_SET_MISMATCH")
    return {"artifact_type": "P1_4_FROZEN_C1_CALIBRATION_INPUTS",
            "status": "COMPLETE", "source_workflow_run_id": manifest["source_workflow_run_id"],
            "source_commit": manifest["source_commit"],
            "protocol_sha256": ctx["source_sha256"]["protocol"],
            "planned_series": 20, "verified_series": len(rows),
            "recalibration_executed": False, "new_null_traces_generated": 0,
            "series": evidence}, rows


def arm_eligibility(calibrations: dict[str, Any], candidate_ids: list[str], arm_key: str) -> tuple[list[str], dict[str, str]]:
    eligible, rejected = [], {}
    for sid in candidate_ids:
        row = calibrations.get(sid)
        if row is None:
            rejected[sid] = "MISSING_CALIBRATION_ARTIFACT"
            continue
        if int(row.get("series_length", 0)) <= 40:
            rejected[sid] = "SERIES_LENGTH_NOT_ABOVE_40"
            continue
        issues = []
        for pos in POSITIONS:
            key = f"{pos:.2f}"
            position = row.get("positions", {}).get(key, {})
            arm = position.get("arms", {}).get(arm_key, {})
            if arm.get("status") != "CALIBRATED" or arm.get("frozen_threshold") is None:
                issues.append(f"{key}:{arm.get('status', 'MISSING')}")
        if issues:
            rejected[sid] = "NOT_CALIBRATED_ALL_POSITIONS:" + ",".join(issues)
        else:
            eligible.append(sid)
    return sorted(eligible), rejected


def holdout_p0_table(calibrations: dict[str, Any], eligible_ids: list[str],
                     arm_key: str) -> dict[str, Any]:
    cells = []
    for sid in eligible_ids:
        row = calibrations[sid]
        for pos in POSITIONS:
            key = f"{pos:.2f}"
            arm = row["positions"][key]["arms"][arm_key]
            holdout = arm.get("holdout", {})
            threshold = float(arm["frozen_threshold"])
            valid = int(holdout.get("valid_replicates", 0))
            alarms = int(holdout.get("alarm_traces", -1))
            raw_statistics = arm.get("holdout_max_statistics")
            if not isinstance(raw_statistics, list):
                raise ValueError(f"HOLDOUT_RAW_STATISTICS_MISSING:{sid}:{key}")
            scores = []
            for value in raw_statistics:
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(score):
                    scores.append(score)
            if holdout.get("status") != "ESTIMABLE" or valid != 1000 or len(scores) != valid or not 0 <= alarms <= valid:
                raise ValueError(f"HOLDOUT_P0_INVALID_OR_INCOMPLETE:{sid}:{key}")
            recomputed_alarms = sum(score >= threshold for score in scores)
            if recomputed_alarms != alarms:
                raise ValueError(f"HOLDOUT_P0_RAW_SCORE_COUNT_MISMATCH:{sid}:{key}")
            point = recomputed_alarms / len(scores)
            upper = base.wilson_upper(alarms, valid)
            if abs(float(holdout.get("p0", -1)) - point) > 1e-12:
                raise ValueError(f"HOLDOUT_P0_POINT_ESTIMATE_MISMATCH:{sid}:{key}")
            if abs(float(holdout.get("wilson_upper_95_one_sided", -1)) - float(upper)) > 1e-10:
                raise ValueError(f"HOLDOUT_P0_WILSON_MISMATCH:{sid}:{key}")
            cells.append({"series_id": sid, "position": key, "threshold": threshold,
                          "alarm_traces": alarms, "valid_replicates": valid,
                          "p0": point, "wilson_upper_95_one_sided": float(upper),
                          "upper_bound_pass": bool(upper <= 0.10)})
    total_alarms = sum(x["alarm_traces"] for x in cells)
    total_valid = sum(x["valid_replicates"] for x in cells)
    return {"target_p0": 0.10, "cells": cells,
            "cell_count": len(cells), "total_alarm_traces": total_alarms,
            "total_valid_replicates": total_valid,
            "pooled_p0_descriptive_only": total_alarms / total_valid if total_valid else None,
            "max_cell_p0": max((x["p0"] for x in cells), default=None),
            "max_cell_wilson_upper_95_one_sided": max((x["wilson_upper_95_one_sided"] for x in cells), default=None),
            "cells_upper_bound_pass": sum(bool(x["upper_bound_pass"]) for x in cells),
            "cells_upper_bound_fail": sum(not bool(x["upper_bound_pass"]) for x in cells),
            "status": "PASS" if cells and all(x["upper_bound_pass"] for x in cells) else "PARTIAL_HOLDOUT_GATE"}


def evaluate_outcome(hits: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    return evaluate_online_hits(
        hits,
        true_break_index=int(case["true_break_index"]),
        true_direction=int(case["direction"]),
    )


def empty_counts() -> dict[str, Any]:
    return {"tp": 0, "miss": 0, "invalid": 0, "not_eligible": 0,
            "wrong_direction": 0, "pre_onset": 0, "delay": []}


def add_outcome(counts: dict[str, Any], outcome: dict[str, Any]) -> None:
    status = outcome.get("status")
    if status == "DETECTED":
        counts["tp"] += 1
        if outcome.get("delay") is not None:
            counts["delay"].append(int(outcome["delay"]))
    elif status == "MISSED":
        counts["miss"] += 1
    elif status == "INVALID_INJECTION":
        counts["invalid"] += 1
    elif status in {"NOT_ELIGIBLE", "ABSTAIN"}:
        counts["not_eligible"] += 1
    else:
        raise ValueError(f"UNKNOWN_OUTCOME_STATUS:{status}")
    counts["wrong_direction"] += int(outcome.get("wrong_direction_alert_count", 0))
    counts["pre_onset"] += int(outcome.get("pre_onset_alert_count", 0))


def summarize_counts(counts: dict[str, Any]) -> dict[str, Any]:
    delay = counts.pop("delay")
    denominator = int(counts["tp"] + counts["miss"])
    counts.update({
        "valid_injection_denominator": denominator,
        "recall": counts["tp"] / denominator if denominator else None,
        "median_delay": float(np.median(delay)) if delay else None,
        "p90_delay": float(np.percentile(delay, 90)) if delay else None,
    })
    return counts


def series_cluster_summary(per_series: dict[str, dict[str, Any]], seed: int) -> dict[str, Any]:
    usable = {sid: row for sid, row in per_series.items() if row.get("recall") is not None}
    values = np.asarray([row["recall"] for row in usable.values()], dtype=float)
    if len(values) == 0:
        return {"status": "NOT_ESTIMABLE", "series_count": 0,
                "independent_unit": "series"}
    rng = np.random.default_rng(seed)
    boot = np.asarray([np.mean(rng.choice(values, size=len(values), replace=True))
                       for _ in range(4000)], dtype=float)
    return {"status": "ESTIMATED", "series_count": len(values),
            "independent_unit": "series", "mean_recall": float(np.mean(values)),
            "median_recall": float(np.median(values)),
            "series_cluster_bootstrap_95": [float(np.percentile(boot, 2.5)),
                                             float(np.percentile(boot, 97.5))],
            "bootstrap_replicates": 4000,
            "per_series": usable}


def run_scale_pilot(ctx: dict[str, Any], calibrations: dict[str, Any],
                    scale_label: str, eligible_ids: list[str], out_dir: Path) -> dict[str, Any]:
    config = SCALE_CONFIG[scale_label]
    arm_key, mode = config["calibration_arm"], config["scale_mode"]
    series_results: dict[str, Any] = {}
    counts_by_tool = {tool: {} for tool in TOOLS}
    planned_cases = len(eligible_ids) * int(ctx["selection_frame"]["run_cases_per_series"])
    processed_cases = 0

    for sid in eligible_ids:
        values = np.asarray(ctx["series"][sid]["values"], dtype=float)
        cases: list[dict[str, Any]] = [{
            "kind": "ORIGINAL", "status": "PLANNED", "values": values,
            "true_break_index": None, "position_fraction": None,
            "magnitude_sigma": None, "direction": None,
        }]
        for injected in injection_grid(values):
            if injected.get("status") != "OK":
                cases.append({"kind": "INJECTION", "status": "NOT_ELIGIBLE",
                              "reason": injected.get("reason"),
                              "true_break_index": injected.get("true_break_index"),
                              "position_fraction": injected.get("position_fraction"),
                              "magnitude_sigma": injected.get("magnitude_sigma"),
                              "direction": injected.get("direction")})
            else:
                cases.append({"kind": "INJECTION", "status": "PLANNED",
                              "values": injected["values"],
                              "true_break_index": injected["true_break_index"],
                              "position_fraction": injected["position_fraction"],
                              "magnitude_sigma": injected["magnitude_sigma"],
                              "direction": injected["direction"]})
        expected_case_count = int(ctx["selection_frame"]["run_cases_per_series"])
        if len(cases) != expected_case_count or expected_case_count != 19:
            raise ValueError(f"FROZEN_CASE_COUNT_MISMATCH:{sid}")

        per_tool = {tool: empty_counts() for tool in TOOLS}
        case_rows = []
        original_alarm_counts = {tool: 0 for tool in TOOLS}
        for index, case in enumerate(cases):
            if case["status"] == "NOT_ELIGIBLE":
                for tool in TOOLS:
                    per_tool[tool]["not_eligible"] += 1
                case_rows.append({"case_index": index, "kind": "INJECTION",
                                  "status": "NOT_ELIGIBLE", "reason": case["reason"],
                                  "true_break_index": case.get("true_break_index")})
                processed_cases += 1
                continue

            x = np.asarray(case["values"], dtype=float)
            position = 0.30 if case.get("position_fraction") is None else float(case["position_fraction"])
            key = f"{position:.2f}"
            calibrated_arm = calibrations[sid]["positions"][key]["arms"][arm_key]
            threshold = float(calibrated_arm["frozen_threshold"])
            huber = post_quiet_huber_detector(x, scale_mode=mode, threshold=threshold)
            huber_hits = huber.get("hits", []) if huber.get("status") == "OK" else []
            huber_output = {
                "status": huber.get("status"), "abstain_reason": huber.get("abstain_reason"),
                "hits": huber_hits, "threshold": threshold,
                "scale_mode": mode,
                "detector_id": "POST_QUIET_HUBER",
                "scale_role": "ALTERNATIVE_SCALE_ESTIMATOR_WITHIN_POST_QUIET_HUBER",
            }
            outputs: dict[str, Any] = {"POST_QUIET_HUBER": huber_output}

            for ref_tool, ref_mode in (("A_FAST", "fast"), ("A_CONSENSUS", "consensus")):
                reference = base.reference_hits(x, ref_mode)
                outputs[ref_tool] = reference
                if case["kind"] == "ORIGINAL":
                    original_alarm_counts[ref_tool] = int(reference.get("hit_count", len(reference.get("hits", []))))

            if case["kind"] == "ORIGINAL":
                original_alarm_counts["POST_QUIET_HUBER"] = len(huber_hits)
            else:
                if huber.get("status") != "OK":
                    outcomes = {
                        "POST_QUIET_HUBER": {"status": "NOT_ELIGIBLE", "reason": huber.get("abstain_reason") or huber.get("status")},
                    }
                else:
                    outcomes = {"POST_QUIET_HUBER": evaluate_outcome(huber_hits, case)}
                for ref_tool in ("A_FAST", "A_CONSENSUS"):
                    outcomes[ref_tool] = evaluate_outcome(outputs[ref_tool].get("hits", []), case)
                for tool, outcome in outcomes.items():
                    add_outcome(per_tool[tool], outcome)
                outputs["outcomes"] = outcomes

            case_rows.append({
                "case_index": index, "kind": case["kind"], "status": "EXECUTED",
                "true_break_index": case.get("true_break_index"),
                "position_fraction": case.get("position_fraction"),
                "magnitude_sigma": case.get("magnitude_sigma"),
                "direction": case.get("direction"), "tool_outputs": outputs,
            })
            processed_cases += 1

        summarized = {tool: summarize_counts(per_tool[tool]) for tool in TOOLS}
        for tool in TOOLS:
            counts_by_tool[tool][sid] = summarized[tool]
        series_results[sid] = {
            "series_length": int(values.size),
            "candidate_sha256": ctx["candidate_hashes"][sid],
            "g1_failure_class": ctx["classes"][sid],
            "case_count": len(case_rows), "cases": case_rows,
            "original_alarm_counts": original_alarm_counts,
            "metric_counts": summarized,
        }

    metrics = {tool: series_cluster_summary(counts_by_tool[tool],
                                             20261126 + (0 if scale_label == "MAD" else 1) + i)
               for i, tool in enumerate(TOOLS)}
    status = "COMPLETE" if len(series_results) == len(eligible_ids) and processed_cases == planned_cases else "PILOT_PARTIAL"
    return {
        "artifact_type": "P1_4_C1_ARM_ISOLATED_PILOT",
        "status": status, "cohort": "C1", "detector_id": "POST_QUIET_HUBER",
        "scale_variant": scale_label, "scale_mode": mode,
        "scale_role": "ALTERNATIVE_SCALE_ESTIMATOR_WITHIN_POST_QUIET_HUBER",
        "calibration_arm_key": arm_key,
        "eligible_series_ids": eligible_ids,
        "eligible_series_count": len(eligible_ids),
        "candidate_series_count": len(ctx["c1_ids"]),
        "planned_cases_per_series": 19, "planned_cases": planned_cases,
        "processed_cases": processed_cases,
        "recalibration_executed": False, "new_null_traces_generated": 0,
        "excluded_detectors": ["FOCuS_PLUS_BOCPD", "FOCuS", "BOCPD", "R-FPOP"],
        "baseline_comparators": ["A_FAST", "A_CONSENSUS"],
        "baseline_mutated": False,
        "metrics": metrics, "series": series_results,
    }


def exact_sign_flip_p(differences: list[float]) -> float | None:
    if not differences:
        return None
    observed = abs(float(np.mean(differences)))
    if len(differences) > 20:
        raise ValueError("EXACT_SIGN_FLIP_LIMIT_EXCEEDED")
    extreme = 0
    total = 1 << len(differences)
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        value = abs(float(np.mean(np.asarray(differences) * np.asarray(signs))))
        if value >= observed - 1e-15:
            extreme += 1
    return extreme / total


def compare_scale_variants(mad: dict[str, Any], bartlett: dict[str, Any]) -> dict[str, Any]:
    mad_rows = mad["metrics"]["POST_QUIET_HUBER"].get("per_series", {})
    bart_rows = bartlett["metrics"]["POST_QUIET_HUBER"].get("per_series", {})
    common = sorted(set(mad_rows) & set(bart_rows))
    differences = [float(bart_rows[s]["recall"]) - float(mad_rows[s]["recall"]) for s in common]
    return {
        "artifact_type": "P1_4_C1_POST_QUIET_HUBER_SCALE_VARIANT_COMPARISON",
        "detector_id": "POST_QUIET_HUBER",
        "comparison": "Bartlett_LRV_minus_MAD",
        "common_series_ids": common, "paired_series_count": len(common),
        "independent_unit": "series",
        "per_series_recall_difference": {s: d for s, d in zip(common, differences)},
        "mean_paired_recall_difference": float(np.mean(differences)) if differences else None,
        "two_sided_exact_series_sign_flip_p": exact_sign_flip_p(differences),
        "inference_note": "Injections are nested within series; paired inference uses series as the independent unit.",
    }


def make_markdown(integrity: dict[str, Any], holdout: dict[str, Any],
                  outputs: dict[str, dict[str, Any]], comparison: dict[str, Any],
                  run_id: str, source_run_id: int, commit: str) -> str:
    lines = [
        "## P1.4 C1 Arm-Isolated Pilot — reused calibration",
        f"- Execution run: `{run_id}`; execution commit: `{commit}`",
        f"- Frozen calibration source: run `{source_run_id}` at `{integrity['source_commit']}`",
        f"- Calibration artifacts SHA-256 verified: **{integrity['verified_series']}/20**",
        "- Recalibration: **NO**; newly generated AR null traces: **0**",
        "- Bartlett LRV is reported only as an alternative scale estimator within Post-Quiet Huber.",
        "- FOCuS + BOCPD excluded; A_FAST and A_CONSENSUS are read-only comparators.",
        "",
        "### Frozen calibration artifact integrity",
        "| Series ID | Artifact ID | Artifact ZIP SHA-256 | Calibration status |",
        "|---|---:|---|---|",
    ]
    for item in integrity["series"]:
        lines.append(
            f"| `{item['series_id']}` | {item['artifact_id']} | `{item['artifact_zip_sha256']}` | {item['calibration_status']} |"
        )
    lines.extend([
        "",
        "### Holdout P0 (1,000 independent holdout traces per series-position cell)",
        "| Post-Quiet Huber scale | Eligible series | Cells | Alarm traces / valid | P0 pooled (descriptive) | Max cell P0 | Max one-sided Wilson U95 | Cells U95 ≤ 0.10 | Cells failing U95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for label in ("MAD", "BARTLETT_LRV"):
        h = holdout[label]
        lines.append(
            f"| {label} | {outputs[label]['eligible_series_count']} | {h['cell_count']} | "
            f"{h['total_alarm_traces']:,} / {h['total_valid_replicates']:,} | "
            f"{h['pooled_p0_descriptive_only']:.3%} | {h['max_cell_p0']:.3%} | "
            f"{h['max_cell_wilson_upper_95_one_sided']:.3%} | {h['cells_upper_bound_pass']} | {h['cells_upper_bound_fail']} |"
        )
    lines.extend([
        "",
        "#### Holdout P0 by series and injection position",
        "| Scale variant | Series ID | Position | Frozen threshold | False alarms / 1,000 | P0 | One-sided Wilson U95 | Gate |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ])
    for label in ("MAD", "BARTLETT_LRV"):
        for cell in holdout[label]["cells"]:
            lines.append(
                f"| {label} | `{cell['series_id']}` | {cell['position']} | {cell['threshold']:.3f} | "
                f"{cell['alarm_traces']} / {cell['valid_replicates']} | {cell['p0']:.3%} | "
                f"{cell['wilson_upper_95_one_sided']:.3%} | {'PASS' if cell['upper_bound_pass'] else 'FAIL'} |"
            )
    lines.extend([
        "",
        "### Arm-isolated injection Pilot",
        "| Scale variant | Eligible series | Cases processed / planned | Mean series recall | Median series recall | Series-cluster bootstrap 95% CI |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for label in ("MAD", "BARTLETT_LRV"):
        output = outputs[label]
        metric = output["metrics"]["POST_QUIET_HUBER"]
        ci = metric.get("series_cluster_bootstrap_95")
        ci_text = f"{ci[0]:.3f}–{ci[1]:.3f}" if ci else "n/a"
        mean = metric.get("mean_recall")
        median = metric.get("median_recall")
        mean_text = f"{mean:.3%}" if mean is not None else "n/a"
        median_text = f"{median:.3%}" if median is not None else "n/a"
        lines.append(
            f"| {label} | {output['eligible_series_count']} | "
            f"{output['processed_cases']:,} / {output['planned_cases']:,} | "
            f"{mean_text} | {median_text} | {ci_text} |"
        )
    lines.extend([
        "",
        "### Read-only baseline comparison",
        "| Scale cohort | Comparator | Series | Mean series recall | Median recall | Series-cluster bootstrap 95% CI |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for label in ("MAD", "BARTLETT_LRV"):
        for comparator in ("A_FAST", "A_CONSENSUS"):
            metric = outputs[label]["metrics"][comparator]
            ci = metric.get("series_cluster_bootstrap_95")
            ci_text = f"{ci[0]:.3f}–{ci[1]:.3f}" if ci else "n/a"
            mean = metric.get("mean_recall")
            median = metric.get("median_recall")
            mean_text = f"{mean:.3%}" if mean is not None else "n/a"
            median_text = f"{median:.3%}" if median is not None else "n/a"
            lines.append(
                f"| {label} | {comparator} | {metric.get('series_count', 0)} | "
                f"{mean_text} | {median_text} | {ci_text} |"
            )
    lines.extend([
        "",
        "### Paired scale comparison on common eligible series",
        f"- Common series: **{comparison['paired_series_count']}**",
        f"- Mean Bartlett − MAD recall: **{comparison['mean_paired_recall_difference']:.3%}**" if comparison["mean_paired_recall_difference"] is not None else "- Mean paired recall difference: n/a",
        f"- Exact two-sided series sign-flip p: **{comparison['two_sided_exact_series_sign_flip_p']:.4f}**" if comparison["two_sided_exact_series_sign_flip_p"] is not None else "- Exact paired p: n/a",
        "",
        "### Per-series results",
        "| Scale | Series ID | n | TP | Miss | Invalid | Not eligible | Recall |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for label in ("MAD", "BARTLETT_LRV"):
        output = outputs[label]
        rows = output["metrics"]["POST_QUIET_HUBER"].get("per_series", {})
        for sid in output["eligible_series_ids"]:
            item = rows.get(sid, {})
            recall = item.get("recall")
            counts = output["series"][sid]["metric_counts"]["POST_QUIET_HUBER"]
            lines.append(
                f"| {label} | `{sid}` | {output['series'][sid]['series_length']} | "
                f"{counts['tp']} | {counts['miss']} | {counts['invalid']} | "
                f"{counts['not_eligible']} | {recall:.3%} |" if recall is not None else
                f"| {label} | `{sid}` | {output['series'][sid]['series_length']} | {counts['tp']} | {counts['miss']} | {counts['invalid']} | {counts['not_eligible']} | n/a |"
            )
    lines.extend([
        "",
        "> This is C1 synthetic-injection validation, not C3 validation against independently documented historical break events. No production authorization is granted.",
    ])
    return "\n".join(lines) + "\n"


def write_inventory(out_dir: Path) -> None:
    inventory = {}
    for path in sorted(Path(out_dir).rglob("*")):
        if path.is_file() and path.name not in {"artifact_sha256_inventory.json", "SHA256SUMS.txt"}:
            inventory[path.relative_to(out_dir).as_posix()] = sha256_file(path)
    write_json(Path(out_dir) / "artifact_sha256_inventory.json", inventory)
    lines = [f"{digest}  {name}" for name, digest in sorted(inventory.items())]
    (Path(out_dir) / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    ctx = base.load_inputs(args)
    manifest = json.loads(Path(args.artifact_manifest).read_text(encoding="utf-8"))
    if int(manifest.get("source_workflow_run_id", -1)) != 45707752707:
        raise ValueError("FROZEN_CALIBRATION_SOURCE_RUN_MISMATCH")
    if manifest.get("source_commit") != "952fa3f2dc724dbeeaaeabfa6d5df620595e9178":
        raise ValueError("FROZEN_CALIBRATION_SOURCE_COMMIT_MISMATCH")
    if manifest.get("protocol_sha256") != ctx["source_sha256"]["protocol"]:
        raise ValueError("CALIBRATION_MANIFEST_PROTOCOL_SHA_MISMATCH")
    if int(manifest.get("expected_c1_series_count", -1)) != len(ctx["c1_ids"]):
        raise ValueError("CALIBRATION_MANIFEST_C1_COUNT_MISMATCH")
    integrity, calibrations = read_pinned_calibration_rows(Path(args.artifact_dir), manifest, ctx)

    expected = manifest["expected_arm_eligibility"]
    outputs: dict[str, dict[str, Any]] = {}
    holdout: dict[str, dict[str, Any]] = {}
    rejected: dict[str, dict[str, str]] = {}
    for label, config in SCALE_CONFIG.items():
        arm_key = config["calibration_arm"]
        eligible, rejected_rows = arm_eligibility(calibrations, ctx["c1_ids"], arm_key)
        if eligible != sorted(expected[label]):
            raise ValueError(f"FROZEN_ELIGIBLE_COHORT_MISMATCH:{label}:actual={eligible}")
        rejected[label] = rejected_rows
        holdout[label] = holdout_p0_table(calibrations, eligible, arm_key)
        outputs[label] = run_scale_pilot(ctx, calibrations, label, eligible, Path(args.output))
        if outputs[label]["status"] != "COMPLETE":
            raise ValueError(f"ARM_ISOLATED_PILOT_INCOMPLETE:{label}")
        write_json(Path(args.output) / config["output_name"], outputs[label])

    comparison = compare_scale_variants(outputs["MAD"], outputs["BARTLETT_LRV"])
    write_json(Path(args.output) / "arm_isolated_scale_comparison.json", comparison)
    write_json(Path(args.output) / "calibration_artifact_integrity.json", integrity)
    write_json(Path(args.output) / "holdout_p0_summary.json", holdout)
    write_json(Path(args.output) / "arm_eligibility_rejections.json", rejected)
    import csv
    with (Path(args.output) / "holdout_p0_by_series.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scale_variant", "series_id", "position", "threshold",
            "alarm_traces", "valid_replicates", "p0", "wilson_upper_95_one_sided", "upper_bound_pass"])
        writer.writeheader()
        for label in ("MAD", "BARTLETT_LRV"):
            for cell in holdout[label]["cells"]:
                writer.writerow({"scale_variant": label, **cell})

    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    commit = os.environ.get("GITHUB_SHA", "LOCAL")
    provenance = {
        "artifact_type": "P1_4_C1_ARM_ISOLATED_EXECUTION_PROVENANCE",
        "workflow_run_id": run_id, "workflow_attempt": attempt,
        "execution_commit": commit,
        "source_calibration_run_id": 45707752707,
        "source_calibration_commit": manifest["source_commit"],
        "protocol_sha256": ctx["source_sha256"]["protocol"],
        "runner_sha256": sha256_file(Path(__file__)),
        "p2c_engine_sha256": sha256_file(ROOT / "p2_b_benchmark" / "p2c_engine.py"),
        "recalibration_executed": False, "new_null_traces_generated": 0,
        "production_authorization": False,
        "replay_command": "python p1_4_validation/run_arm_isolated_pilot.py --prepared-zip /tmp/p2-prepared.zip --manifest p1_4_validation/cohort_manifest.json --protocol p1_4_validation/pilot_protocol.json --selection-json /tmp/cohort_selection.json --g1-shards-dir /tmp/p2-g1-shards --artifact-manifest p1_4_validation/c1_calibration_artifacts_run_45707752707.json --artifact-dir /tmp/p1-4-calibration-source --output artifacts/p1_4/arm_isolated_c1",
    }
    write_json(Path(args.output) / "execution_provenance.json", provenance)
    summary = make_markdown(integrity, holdout, outputs, comparison,
                            run_id, 45707752707, commit)
    (Path(args.output) / "STEP_SUMMARY.md").write_text(summary, encoding="utf-8")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
    print(summary, flush=True)
    write_inventory(Path(args.output))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-calibration-artifacts", action="store_true")
    parser.add_argument("--artifact-manifest", default="p1_4_validation/c1_calibration_artifacts_run_45707752707.json")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--prepared-zip")
    parser.add_argument("--manifest", default="p1_4_validation/cohort_manifest.json")
    parser.add_argument("--protocol", default="p1_4_validation/pilot_protocol.json")
    parser.add_argument("--selection-json")
    parser.add_argument("--g1-shards-dir")
    parser.add_argument("--output", default="artifacts/p1_4/arm_isolated_c1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.download_calibration_artifacts:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        repository = os.environ.get("GITHUB_REPOSITORY")
        if not token or not repository:
            raise SystemExit("GH_TOKEN and GITHUB_REPOSITORY are required for artifact download")
        result = download_pinned_calibrations(Path(args.artifact_manifest),
                                              Path(args.artifact_dir), token, repository)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    required = (args.prepared_zip, args.selection_json, args.g1_shards_dir)
    if not all(required):
        raise SystemExit("--prepared-zip, --selection-json and --g1-shards-dir are required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())