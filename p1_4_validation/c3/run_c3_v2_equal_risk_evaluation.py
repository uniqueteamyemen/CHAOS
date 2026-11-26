"""C3 v2 expanded-cohort evaluation with development-Wilson calibration."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import zipfile
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p1_4_validation.injection_runner import (  # noqa: E402
    focus_rearm_points_for_frequency,
    focus_reset_rearm,
    generate_ar_null_trace,
    select_ar_model,
    wilson_upper,
)
from p2_b_benchmark.p2c_engine import (  # noqa: E402
    post_quiet_huber_detector,
)
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1  # noqa: E402

QUIET_POINTS = 40
REARM_POINTS = 20
MAX_EVENTS = 12
REPLICATES = 1000
MIN_VALID_REPLICATES = 950
P0_TARGET = 0.10  # Holdout acceptance ceiling
DEV_P0_TARGET = 0.085  # Calibration margin to reduce boundary-fragile Holdout failures
WILSON_Z = 1.6448536269514722
HYBRID_MAX_GAP = 8
FOCUS4_NAME = "FOCuS (monthly rearm 4; weekly rearm 20)"
PER_SERIES_ROUTER = "Per-Series Router"
MIN_WINNER_MATCHED_PAIRS = 3
MIN_WINNER_EPISODE_CLUSTERS = 3
FOCUS_GRID = (
    15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90, 110, 150, 175, 200,
    225, 250, 275, 300, 325, 350, 400, 450, 500, 600, 800, 1000, 1200,
)
HUBER_GRID = (
    4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 50, 60, 70,
    80, 90, 100, 110, 125, 150, 200, 250, 300,
)
CANDIDATES = (
    "FOCuS (reset-rearm)",
    FOCUS4_NAME,
    "Post-Quiet Huber + MAD",
    "Post-Quiet Huber + Bartlett LRV",
    "Hybrid: FOCuS + Huber confirmation",
)
ROUTER_MEMBER_DETECTORS = (
    "FOCuS (reset-rearm)",
    FOCUS4_NAME,
    "Post-Quiet Huber + MAD",
    "Post-Quiet Huber + Bartlett LRV",
)
READ_ONLY = ("A_FAST", "A_CONSENSUS")
BASE_DETECTORS = CANDIDATES + READ_ONLY
ALL_DETECTORS = BASE_DETECTORS + (PER_SERIES_ROUTER,)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(clean(value), ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.ndarray):
        return [clean(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def add_calendar_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + int(months)
    year, month_zero = divmod(absolute, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def ensure_causal_release_order(series_id: str, rows: list[dict]) -> None:
    previous = None
    for index, row in enumerate(rows):
        available = row["available_at_obj"]
        if previous is not None and available < previous:
            raise ValueError(f"C3_V2_NON_MONOTONIC_AVAILABLE_AT:{series_id}:{index}")
        previous = available


def validate_registered_series_tape(
    series_id: str,
    rows: list[dict],
    series_config: dict,
    events: list[dict],
) -> None:
    if len(rows) < int(series_config["minimum_observation_count"]):
        raise ValueError(f"C3_V2_INSUFFICIENT_SERIES_POINTS:{series_id}:{len(rows)}")
    observation_start = date.fromisoformat(series_config["observation_start"])
    observation_end = date.fromisoformat(series_config["observation_end"])
    for index, row in enumerate(rows):
        if row["frequency"] != series_config["frequency"]:
            raise ValueError(f"C3_V2_FREQUENCY_CONTRACT_MISMATCH:{series_id}:{index}")
        if row["units"] != series_config["units"]:
            raise ValueError(f"C3_V2_UNITS_CONTRACT_MISMATCH:{series_id}:{index}")
        if not observation_start <= row["observation_date_obj"] <= observation_end:
            raise ValueError(f"C3_V2_OBSERVATION_OUTSIDE_CONTRACT_RANGE:{series_id}:{index}")

    ensure_causal_release_order(series_id, rows)
    series_events = [
        event for event in events
        if series_id in event["expected_sign_by_series"]
    ]
    if not series_events:
        raise ValueError(f"C3_V2_SERIES_HAS_NO_REGISTERED_EVENTS:{series_id}")
    earliest_anchor = min(
        date.fromisoformat(event["anchor_date"]) for event in series_events
    )
    if len(rows) < QUIET_POINTS or rows[QUIET_POINTS - 1]["observation_date_obj"] >= earliest_anchor:
        raise ValueError(f"C3_V2_FIRST_40_NOT_PRE_EVENT:{series_id}")

    available_dates = [row["available_at_obj"] for row in rows]
    first_available, last_available = min(available_dates), max(available_dates)
    for event in series_events:
        anchor = date.fromisoformat(event["anchor_date"])
        window_start = add_calendar_months(anchor, -12)
        window_end = add_calendar_months(anchor, 12)
        if first_available > window_start:
            raise ValueError(
                f"C3_V2_EVENT_WINDOW_START_NOT_COVERED:{series_id}:{event['event_id']}:"
                f"{first_available}:{window_start}"
            )
        if last_available < window_end:
            raise ValueError(
                f"C3_V2_EVENT_WINDOW_END_NOT_COVERED:{series_id}:{event['event_id']}:"
                f"{last_available}:{window_end}"
            )


def verify_source_bundle(
    archive_path: Path, contract_path: Path,
) -> tuple[dict, dict[str, list[dict]], dict, str, str]:
    payload = archive_path.read_bytes()
    archive_sha = sha256(payload)
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    if contract.get("contract_id") != "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V2_1":
        raise ValueError("C3_V2_EXPANDED_CONTRACT_ID_MISMATCH")
    contract_sha = sha256(contract_bytes)
    frozen = contract.get("frozen_references", {})
    original_v1_path = ROOT / frozen.get(
        "original_c3_v1_contract_path",
        "p1_4_validation/c3/c3_source_intake_contract_v1.json",
    )
    if not original_v1_path.is_file() or sha256(original_v1_path.read_bytes()) != frozen.get(
        "original_c3_v1_source_contract_sha256"
    ):
        raise ValueError("C3_V2_ORIGINAL_C3_V1_CONTRACT_SHA256_MISMATCH")
    shock_contract_path = ROOT / frozen.get(
        "shock_event_contract_path", "real_data_stress_pipeline/shock_event_contract.json"
    )
    if not shock_contract_path.is_file() or sha256(shock_contract_path.read_bytes()) != frozen.get(
        "shock_event_contract_sha256"
    ):
        raise ValueError("C3_V2_SHOCK_EVENT_CONTRACT_SHA256_MISMATCH")
    series_ids = [row["series_id"] for row in contract.get("series", [])]
    event_ids = [row["event_id"] for row in contract.get("events", [])]
    expected_pairs = sum(
        len(event.get("expected_sign_by_series", {}))
        for event in contract.get("events", [])
    )
    if len(series_ids) != len(set(series_ids)) or len(series_ids) != 4:
        raise ValueError("C3_V2_UNIQUE_SERIES_CONTRACT_MISMATCH")
    if len(event_ids) != len(set(event_ids)) or len(event_ids) != 20:
        raise ValueError("C3_V2_EVENT_CONTRACT_MISMATCH")
    if len({event.get("episode_id") for event in contract["events"]}) != 10:
        raise ValueError("C3_V2_EPISODE_CLUSTER_COUNT_MISMATCH")
    if expected_pairs != 37:
        raise ValueError("C3_V2_EVENT_SERIES_PAIR_COUNT_MISMATCH")

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise ValueError("C3_V2_SOURCE_ARTIFACT_CORRUPT")
        names = {name for name in archive.namelist() if not name.endswith("/")}
        manifest_bytes = archive.read("expanded_source_intake_manifest.json")
        tape_bytes = archive.read("expanded_initial_release_tape.csv")
        manifest = json.loads(manifest_bytes)
        if manifest.get("status") != "SOURCE_TAPES_ACQUIRED_NOT_DETECTOR_EXECUTED":
            raise ValueError("C3_V2_SOURCE_INTAKE_STATUS_MISMATCH")
        manifest_contract_id = manifest.get("contract_id")
        frozen_source_sha = frozen.get("source_intake_contract_sha256")
        accepted_source_contracts = {
            (contract["contract_id"], contract_sha),
            ("CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1", frozen_source_sha),
        }
        if (manifest_contract_id, manifest.get("contract_sha256")) not in accepted_source_contracts:
            raise ValueError("C3_V2_SOURCE_CONTRACT_SNAPSHOT_MISMATCH")
        if manifest.get("shock_event_contract_git_blob") != frozen.get("shock_event_contract_git_blob"):
            raise ValueError("C3_V2_SHOCK_CONTRACT_BLOB_MISMATCH")
        if manifest.get("shock_event_contract_sha256") != frozen.get("shock_event_contract_sha256"):
            raise ValueError("C3_V2_SHOCK_CONTRACT_SHA256_MISMATCH")
        if manifest.get("detector_execution_performed") is not False:
            raise ValueError("C3_V2_INTAKE_CONTAINS_DETECTOR_EXECUTION")
        if int(manifest.get("event_count", -1)) != len(contract["events"]):
            raise ValueError("C3_V2_EVENT_COUNT_MISMATCH")
        if int(manifest.get("series_count", -1)) != len(contract["series"]):
            raise ValueError("C3_V2_SERIES_COUNT_MISMATCH")
        expected_pairs = sum(
            len(event["expected_sign_by_series"]) for event in contract["events"]
        )
        if int(manifest.get("event_series_pair_count", -1)) != expected_pairs:
            raise ValueError("C3_V2_EVENT_SERIES_PAIR_COUNT_MISMATCH")
        expected_tape_name = contract.get("intake_output", {}).get("normalized_file")
        if expected_tape_name != "expanded_initial_release_tape.csv":
            raise ValueError("C3_V2_NORMALIZED_TAPE_CONTRACT_NAME_MISMATCH")
        if manifest.get("normalized_tape", {}).get("file") != expected_tape_name:
            raise ValueError("C3_V2_MANIFEST_TAPE_NAME_MISMATCH")
        expected_manifest_guardrails = (
            contract.get("source_intake_guardrails")
            if manifest_contract_id == "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1"
            else contract.get("guardrails")
        )
        if expected_manifest_guardrails is None or manifest.get("guardrails") != expected_manifest_guardrails:
            raise ValueError("C3_V2_SOURCE_GUARDRAIL_MANIFEST_MISMATCH")
        if sha256(tape_bytes) != manifest["normalized_tape"]["sha256"]:
            raise ValueError("C3_V2_NORMALIZED_TAPE_SHA256_MISMATCH")
        if len(tape_bytes) != int(manifest["normalized_tape"]["bytes"]):
            raise ValueError("C3_V2_NORMALIZED_TAPE_SIZE_MISMATCH")

        raw_batches = manifest.get("raw_vintage_batches", [])
        raw_members = []
        for batch in raw_batches:
            member = batch["file"]
            member_path = PurePosixPath(member)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"C3_V2_RAW_BATCH_PATH_UNSAFE:{member}")
            if member in raw_members:
                raise ValueError(f"C3_V2_RAW_BATCH_DUPLICATE:{member}")
            raw_members.append(member)
            if member not in names:
                raise ValueError(f"C3_V2_RAW_BATCH_MISSING:{member}")
            raw = archive.read(member)
            if len(raw) != int(batch["bytes"]) or sha256(raw) != batch["sha256"]:
                raise ValueError(f"C3_V2_RAW_BATCH_SHA256_MISMATCH:{member}")
        expected_member_count = 2 + len(raw_batches)
        if len(names) != expected_member_count:
            raise ValueError(
                f"C3_V2_ARTIFACT_MEMBER_COUNT_MISMATCH:{len(names)}:{expected_member_count}"
            )

    rows = list(csv.DictReader(io.StringIO(tape_bytes.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("C3_V2_EMPTY_NORMALIZED_TAPE")
    if len(rows) != int(manifest.get("point_count", -1)):
        raise ValueError("C3_V2_POINT_COUNT_MISMATCH")
    expected_series = set(series_ids)
    by_series: dict[str, list[dict]] = {}
    for row in rows:
        sid = row.get("series_id")
        if sid not in expected_series:
            raise ValueError(f"C3_V2_UNEXPECTED_SERIES:{sid}")
        if row.get("value_semantics") != "FIRST_ALFRED_VINTAGE_VALUE":
            raise ValueError(f"C3_V2_NON_FIRST_RELEASE_VALUE:{sid}")
        observation = date.fromisoformat(row["observation_date"])
        available = date.fromisoformat(row["available_at"])
        value = float(row["value"])
        if not math.isfinite(value) or available < observation:
            raise ValueError(f"C3_V2_POINT_INVALID:{sid}:{observation}")
        by_series.setdefault(sid, []).append({
            **row,
            "value_float": value,
            "observation_date_obj": observation,
            "available_at_obj": available,
        })

    if set(by_series) != expected_series:
        raise ValueError("C3_V2_SERIES_SET_MISMATCH")
    configured = {row["series_id"]: row for row in contract["series"]}
    for sid, series_rows in by_series.items():
        series_rows.sort(key=lambda row: (
            row["observation_date_obj"], row["available_at_obj"]
        ))
        observations = [row["observation_date"] for row in series_rows]
        if len(observations) != len(set(observations)):
            raise ValueError(f"C3_V2_DUPLICATE_OBSERVATION_DATE:{sid}")
        validate_registered_series_tape(
            sid, series_rows, configured[sid], contract["events"]
        )

    for event in contract["events"]:
        for sid in event["expected_sign_by_series"]:
            if sid not in by_series:
                raise ValueError(f"C3_V2_EVENT_SERIES_NOT_IN_TAPE:{event['event_id']}:{sid}")
    return manifest, by_series, contract, archive_sha, contract_sha


def _raw_value_is_missing(value: str | None) -> bool:
    return value is None or value.strip() in {"", ".", "NA", "N/A", "nan", "NaN"}


def extract_first_release_level_from_archive(
    archive_path: Path,
    manifest: dict,
    series_id: str,
    observation_date: date,
) -> dict:
    """Extract one prior first-print from already-hashed raw vintage files."""
    candidates = []
    with zipfile.ZipFile(archive_path) as archive:
        batches = sorted(
            (
                batch for batch in manifest.get("raw_vintage_batches", [])
                if PurePosixPath(batch["file"]).parts[1] == series_id
            ),
            key=lambda row: int(row["batch"]),
        )
        for batch in batches:
            with archive.open(batch["file"]) as stream:
                reader = csv.DictReader(
                    (line.decode("utf-8-sig") for line in stream)
                )
                match = next(
                    (
                        row for row in reader
                        if row.get("observation_date") == observation_date.isoformat()
                    ),
                    None,
                )
            if match is None:
                continue
            for vintage_date in batch["requested_vintage_dates"]:
                field = f"{series_id}_{vintage_date.replace('-', '')}"
                value = match.get(field)
                if _raw_value_is_missing(value):
                    continue
                numeric = float(value)
                available_at = date.fromisoformat(vintage_date)
                if not math.isfinite(numeric) or available_at < observation_date:
                    raise ValueError(
                        f"C3_V2_INVALID_RAW_PREDECESSOR:{series_id}:{observation_date}"
                    )
                candidates.append({
                    "series_id": series_id,
                    "observation_date": observation_date.isoformat(),
                    "observation_date_obj": observation_date,
                    "available_at": vintage_date,
                    "available_at_obj": available_at,
                    "value_float": numeric,
                    "value": format(numeric, ".15g"),
                    "source_batch_file": batch["file"],
                    "source_batch_sha256": batch["sha256"],
                    "source_vintage": vintage_date,
                })
                break
    if not candidates:
        raise ValueError(
            f"C3_V2_RAW_PREDECESSOR_NOT_FOUND:{series_id}:{observation_date}"
        )
    return min(candidates, key=lambda row: row["available_at_obj"])


def apply_causal_series_transforms(
    archive_path: Path,
    manifest: dict,
    by_series: dict[str, list[dict]],
    contract: dict,
) -> tuple[dict[str, list[dict]], dict]:
    """Apply registered transforms without altering the source archive or release times."""
    configured = {row["series_id"]: row for row in contract["series"]}
    transformed: dict[str, list[dict]] = {}
    audit: dict[str, dict] = {}

    for series_id, source_rows in by_series.items():
        series_config = configured[series_id]
        transform = series_config.get("series_transform", "level")
        rows = sorted(
            source_rows,
            key=lambda row: (row["observation_date_obj"], row["available_at_obj"]),
        )
        analysis_units = series_config.get("analysis_units", series_config["units"])

        if transform == "level":
            transformed[series_id] = [
                {
                    **row,
                    "series_transform": "level",
                    "source_value_float": float(row["value_float"]),
                    "units": analysis_units,
                }
                for row in rows
            ]
            audit[series_id] = {
                "transform": "level",
                "source_observation_count": len(rows),
                "analysis_observation_count": len(rows),
                "analysis_units": analysis_units,
            }
            continue

        if transform != "first_difference":
            raise ValueError(f"C3_V2_UNKNOWN_SERIES_TRANSFORM:{series_id}:{transform}")
        if not rows:
            raise ValueError(f"C3_V2_EMPTY_TRANSFORM_SOURCE:{series_id}")

        first_date = rows[0]["observation_date_obj"]
        if series_config["frequency"] == "Monthly":
            predecessor_date = add_calendar_months(first_date, -1)
            next_observation = lambda value: add_calendar_months(value, 1)
        elif series_config["frequency"].startswith("Weekly"):
            predecessor_date = first_date - timedelta(days=7)
            next_observation = lambda value: value + timedelta(days=7)
        else:
            raise ValueError(f"C3_V2_TRANSFORM_FREQUENCY_UNSUPPORTED:{series_id}")

        predecessor = extract_first_release_level_from_archive(
            archive_path, manifest, series_id, predecessor_date
        )
        if predecessor["available_at_obj"] > rows[0]["available_at_obj"]:
            raise ValueError(
                f"C3_V2_PREDECESSOR_RELEASES_AFTER_CURRENT_POINT:{series_id}"
            )

        output_rows = []
        previous_date = predecessor_date
        previous_value = float(predecessor["value_float"])
        previous_available = predecessor["available_at_obj"]
        for index, row in enumerate(rows):
            current_date = row["observation_date_obj"]
            if current_date != next_observation(previous_date):
                raise ValueError(
                    f"C3_V2_FIRST_DIFFERENCE_OBSERVATION_GAP:{series_id}:{previous_date}:{current_date}"
                )
            current_available = row["available_at_obj"]
            if current_available < previous_available:
                raise ValueError(
                    f"C3_V2_FIRST_DIFFERENCE_NON_CAUSAL_RELEASE_ORDER:{series_id}:{index}"
                )
            current_value = float(row["value_float"])
            difference = current_value - previous_value
            if not math.isfinite(difference):
                raise ValueError(f"C3_V2_NON_FINITE_FIRST_DIFFERENCE:{series_id}:{index}")
            output_rows.append({
                **row,
                "value": format(difference, ".15g"),
                "value_float": difference,
                "source_value_float": current_value,
                "previous_source_value_float": previous_value,
                "series_transform": "first_difference",
                "value_semantics": "CAUSAL_FIRST_DIFFERENCE_OF_FIRST_ALFRED_RELEASES",
                "units": analysis_units,
            })
            previous_date = current_date
            previous_value = current_value
            previous_available = current_available

        transformed[series_id] = output_rows
        audit[series_id] = {
            "transform": "first_difference",
            "formula": "delta_x_t = x_t - x_t_minus_1",
            "source_observation_count": len(rows),
            "analysis_observation_count": len(output_rows),
            "first_analysis_observation": output_rows[0]["observation_date"],
            "first_analysis_available_at": output_rows[0]["available_at"],
            "analysis_units": analysis_units,
            "predecessor": {
                "observation_date": predecessor["observation_date"],
                "available_at": predecessor["available_at"],
                "value": predecessor["value"],
                "source_batch_file": predecessor["source_batch_file"],
                "source_batch_sha256": predecessor["source_batch_sha256"],
                "source_vintage": predecessor["source_vintage"],
            },
            "availability_policy": "Each transformed point retains the current observation's original first-release available_at; predecessor was first published no later than the current point.",
            "source_archive_mutated": False,
        }

    return transformed, audit

def deterministic_seed(
    tape_sha: str, series_id: str, ar_order: int, phase: str, replicate: int,
) -> int:
    if phase not in {"development", "holdout"}:
        raise ValueError("C3_V2_INVALID_SEED_PHASE")
    identity = (
        "CHAOS:C3_V2_EXPANDED:" + tape_sha + ":" + series_id + ":"
        + str(int(ar_order)) + ":" + phase + ":" + str(int(replicate))
    )
    return int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:8], "big")


def analysis_tape_sha256(by_series: dict[str, list[dict]]) -> str:
    """Hash the exact ordered values and release times consumed by the detectors."""
    identity = []
    for series_id in sorted(by_series):
        for row in sorted(
            by_series[series_id],
            key=lambda item: (item["observation_date_obj"], item["available_at_obj"]),
        ):
            identity.append({
                "series_id": series_id,
                "observation_date": row["observation_date"],
                "available_at": row["available_at"],
                "value": format(float(row["value_float"]), ".15g"),
                "series_transform": row.get("series_transform", "level"),
                "units": row["units"],
            })
    return sha256(canonical_json(identity))


def finite_positive_threshold(value: Any) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("C3_V2_INVALID_THRESHOLD")
    try:
        threshold = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("C3_V2_INVALID_THRESHOLD") from exc
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("C3_V2_INVALID_THRESHOLD")
    return threshold


def wilson_stats(alarms: int, trials: int) -> dict:
    upper = wilson_upper(int(alarms), int(trials), z=WILSON_Z)
    return {
        "alarm_traces": int(alarms),
        "valid_replicates": int(trials),
        "p0": (int(alarms) / int(trials)) if trials else None,
        "wilson_upper_95_one_sided": upper,
        "p0_target": P0_TARGET,
    }


def choose_threshold_by_dev_wilson(
    development_scores: list[float | None],
    holdout_scores: list[float | None],
    grid: tuple[int, ...],
) -> dict:
    thresholds = sorted({finite_positive_threshold(value) for value in grid})
    if not thresholds:
        raise ValueError("C3_V2_EMPTY_THRESHOLD_GRID")
    valid_dev = [float(value) for value in development_scores
                 if value is not None and math.isfinite(float(value))]
    valid_hold = [float(value) for value in holdout_scores
                  if value is not None and math.isfinite(float(value))]
    if len(valid_dev) < MIN_VALID_REPLICATES:
        return {
            "status": "ABSTAINED",
            "raw_status": "INCONCLUSIVE",
            "reason": "INSUFFICIENT_VALID_DEVELOPMENT_REPLICATES",
            "frozen_threshold": None,
            "development": wilson_stats(0, len(valid_dev)),
            "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
            "development_grid": [],
        }

    grid_rows = []
    selected = None
    for threshold in thresholds:
        alarms = sum(value >= threshold for value in valid_dev)
        stats = wilson_stats(alarms, len(valid_dev))
        point = {"threshold": threshold, **stats}
        grid_rows.append(point)
        upper = stats["wilson_upper_95_one_sided"]
        if upper is not None and upper <= DEV_P0_TARGET:
            selected = point
            break

    if selected is None:
        return {
            "status": "ABSTAINED",
            "raw_status": "NOT_CALIBRATABLE",
            "reason": "NO_THRESHOLD_MET_DEVELOPMENT_WILSON_GATE",
            "frozen_threshold": None,
            "development": grid_rows[-1] if grid_rows else {},
            "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
            "development_grid": grid_rows,
        }

    threshold = float(selected["threshold"])
    holdout_alarms = sum(value >= threshold for value in valid_hold)
    holdout_stats = wilson_stats(holdout_alarms, len(valid_hold))
    if len(valid_hold) < MIN_VALID_REPLICATES:
        holdout_status = "INCONCLUSIVE"
    elif holdout_stats["wilson_upper_95_one_sided"] <= P0_TARGET:
        holdout_status = "PASS"
    else:
        holdout_status = "FAIL"
    status = {
        "PASS": "VALIDATED",
        "FAIL": "NOT_VALIDATED",
        "INCONCLUSIVE": "ABSTAINED",
    }[holdout_status]
    return {
        "status": status,
        "raw_status": holdout_status,
        "development_status": "CALIBRATED",
        "frozen_threshold": threshold,
        "development": selected,
        "holdout": {"status": holdout_status, **holdout_stats},
        "development_grid": grid_rows,
        "holdout_retuning": False,
    }


def focus_path_alarm(
    trace: np.ndarray, threshold: float, rearm_quiet_points: int = REARM_POINTS,
) -> bool | None:
    result = focus_reset_rearm(
        trace,
        threshold=finite_positive_threshold(threshold),
        quiet_points=QUIET_POINTS,
        rearm_quiet_points=int(rearm_quiet_points),
        max_events=MAX_EVENTS,
        min_series_length=QUIET_POINTS + 1,
    )
    if result.get("status") != "OK":
        return None
    return bool(result.get("hits"))


def calibrate_focus(
    development_traces: list[np.ndarray],
    holdout_traces: list[np.ndarray],
    rearm_quiet_points: int = REARM_POINTS,
) -> dict:
    grid_rows = []
    selected = None
    for threshold in FOCUS_GRID:
        outcomes = [focus_path_alarm(trace, threshold, rearm_quiet_points) for trace in development_traces]
        valid = [value for value in outcomes if value is not None]
        if len(valid) < MIN_VALID_REPLICATES:
            return {
                "status": "ABSTAINED",
                "raw_status": "INCONCLUSIVE",
                "reason": "INSUFFICIENT_VALID_FOCUS_DEVELOPMENT_REPLICATES",
                "frozen_threshold": None,
                "development_grid": grid_rows,
                "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
                "execution_policy": f"40_initial_{int(rearm_quiet_points)}_rearm_max_12_hits",
            }
        alarms = sum(bool(value) for value in valid)
        stats = wilson_stats(alarms, len(valid))
        point = {"threshold": float(threshold), **stats}
        grid_rows.append(point)
        upper = stats["wilson_upper_95_one_sided"]
        if upper is not None and upper <= DEV_P0_TARGET:
            selected = point
            break

    if selected is None:
        return {
            "status": "ABSTAINED",
            "raw_status": "NOT_CALIBRATABLE",
            "reason": "NO_FOCUS_THRESHOLD_MET_DEVELOPMENT_WILSON_GATE",
            "frozen_threshold": None,
            "development_grid": grid_rows,
            "holdout": {"status": "NOT_RUN_NO_DEVELOPMENT_THRESHOLD"},
            "execution_policy": f"40_initial_{int(rearm_quiet_points)}_rearm_max_12_hits",
        }

    threshold = float(selected["threshold"])
    holdout_outcomes = [focus_path_alarm(trace, threshold, rearm_quiet_points) for trace in holdout_traces]
    valid_hold = [value for value in holdout_outcomes if value is not None]
    alarms = sum(bool(value) for value in valid_hold)
    stats = wilson_stats(alarms, len(valid_hold))
    if len(valid_hold) < MIN_VALID_REPLICATES:
        holdout_status = "INCONCLUSIVE"
    elif stats["wilson_upper_95_one_sided"] <= P0_TARGET:
        holdout_status = "PASS"
    else:
        holdout_status = "FAIL"
    return {
        "status": {"PASS": "VALIDATED", "FAIL": "NOT_VALIDATED",
                   "INCONCLUSIVE": "ABSTAINED"}[holdout_status],
        "raw_status": holdout_status,
        "frozen_threshold": threshold,
        "development": selected,
        "development_grid": grid_rows,
        "holdout": {"status": holdout_status, **stats},
        "holdout_retuning": False,
        "execution_policy": f"40_initial_{int(rearm_quiet_points)}_rearm_max_12_hits",
    }


def huber_max_statistic(trace: np.ndarray, scale_mode: str) -> float | None:
    result = post_quiet_huber_detector(
        trace,
        scale_mode=scale_mode,
        quiet_points=QUIET_POINTS,
        threshold=1e100,
        return_score_trace=True,
    )
    value = result.get("max_statistic") if result.get("status") == "OK" else None
    return float(value) if value is not None and math.isfinite(float(value)) else None


def extract_detector_hits(
    detector: str,
    values: np.ndarray,
    threshold: float | None = None,
    rearm_quiet_points: int = REARM_POINTS,
) -> tuple[list[dict], str, dict]:
    if detector in {"FOCuS (reset-rearm)", FOCUS4_NAME}:
        if threshold is None:
            return [], "ABSTAIN", {"reason": "NO_FROZEN_THRESHOLD"}
        result = focus_reset_rearm(
            values,
            threshold=float(threshold),
            quiet_points=QUIET_POINTS,
            rearm_quiet_points=int(rearm_quiet_points),
            max_events=MAX_EVENTS,
            min_series_length=QUIET_POINTS + 1,
        )
        hits = result.get("hits", [])
        metadata = {
            "reset_rearm": True,
            "initial_calibration_observations": result.get("initial_calibration_observations"),
            "rearm_calibration_observations": result.get("rearm_calibration_observations"),
            "rearm_intervals": result.get("rearm_intervals", []),
        }
        status = str(result.get("status", "OK"))
    elif detector in {"Post-Quiet Huber + MAD", "Post-Quiet Huber + Bartlett LRV"}:
        if threshold is None:
            return [], "ABSTAIN", {"reason": "NO_FROZEN_THRESHOLD"}
        scale_mode = "mad" if detector.endswith("+ MAD") else "bartlett"
        result = post_quiet_huber_detector(
            values, scale_mode=scale_mode, quiet_points=QUIET_POINTS,
            threshold=float(threshold), max_events=MAX_EVENTS,
            return_score_trace=False,
        )
        hits = result.get("hits", [])
        metadata = result.get("metadata", {})
        status = str(result.get("status", "OK"))
    elif detector in READ_ONLY:
        mode = "fast" if detector == "A_FAST" else "consensus"
        result = BreakDetectorV1(mode=mode).analyze(values)
        hits = []
        for event in result.get("structural_breaks", []):
            index = event.get("detection_time", event.get("time"))
            sign = event.get("direction", event.get("sign"))
            if index is None or sign is None:
                raise ValueError(f"{detector}_EVENT_SCHEMA_MISMATCH")
            hits.append({"index": int(index), "sign": int(sign)})
        metadata = result.get("metadata", {})
        status = str(result.get("status", "OK"))
    else:
        raise ValueError(f"C3_V2_UNKNOWN_DETECTOR:{detector}")

    normalized = []
    for hit in hits:
        index = hit.get("index", hit.get("detection_index"))
        sign = hit.get("sign", hit.get("direction"))
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError(f"C3_V2_INVALID_HIT_INDEX:{detector}")
        if isinstance(sign, bool) or int(sign) not in (-1, 1):
            raise ValueError(f"C3_V2_INVALID_HIT_SIGN:{detector}")
        if not 0 <= int(index) < len(values):
            raise ValueError(f"C3_V2_HIT_INDEX_OUT_OF_RANGE:{detector}:{index}")
        normalized.append({"index": int(index), "sign": int(sign)})
    normalized.sort(key=lambda row: (row["index"], row["sign"]))
    return normalized, status, metadata


def hybrid_confirmation_hits(
    values: np.ndarray,
    thresholds: dict[str, float | None],
    rearm_quiet_points: int = REARM_POINTS,
) -> tuple[list[dict], dict]:
    focus_threshold = thresholds.get("FOCuS (reset-rearm)")
    if focus_threshold is None:
        return [], {"status": "ABSTAIN", "reason": "FOCUS_THRESHOLD_UNAVAILABLE"}
    focus_hits, focus_status, focus_meta = extract_detector_hits(
        "FOCuS (reset-rearm)", values, float(focus_threshold),
        rearm_quiet_points=int(rearm_quiet_points)
    )
    huber_hits: list[tuple[str, dict]] = []
    used_huber_arms = []
    for detector in ("Post-Quiet Huber + MAD", "Post-Quiet Huber + Bartlett LRV"):
        threshold = thresholds.get(detector)
        if threshold is None:
            continue
        hits, status, _ = extract_detector_hits(
            detector, values, float(threshold),
            rearm_quiet_points=int(rearm_quiet_points),
        )
        if status == "OK":
            huber_hits.extend((detector, hit) for hit in hits)
            used_huber_arms.append(detector)
    if focus_status != "OK" or not used_huber_arms:
        return [], {
            "status": "ABSTAIN",
            "reason": "FOCUS_OR_HUBER_MEMBER_UNAVAILABLE",
            "focus_status": focus_status,
            "huber_members": used_huber_arms,
        }
    # An available Huber member that emits no alert is a valid zero outcome,
    # not an abstention. Keep it in the Bernoulli null denominator.

    # Require FOCuS plus one Huber variant; MAD and Bartlett are not counted
    # as two independent votes against one another.
    used: set[tuple[str, int, int]] = set()
    output = []
    for focus in focus_hits:
        focus_index = int(focus["index"])
        candidates = []
        for detector, huber in huber_hits:
            key = (detector, int(huber["index"]), int(huber["sign"]))
            if key in used or int(huber["sign"]) != int(focus["sign"]):
                continue
            distance = abs(int(huber["index"]) - focus_index)
            if distance <= HYBRID_MAX_GAP:
                detection_index = max(focus_index, int(huber["index"]))
                candidates.append((
                    distance, detection_index, detector, int(huber["index"]),
                    int(huber["sign"]), key,
                ))
        if not candidates:
            continue
        chosen = min(candidates, key=lambda row: row[:5])
        used.add(chosen[5])
        output.append({
            "index": int(chosen[1]),
            "sign": int(chosen[4]),
            "components": ["FOCuS (reset-rearm)", chosen[2]],
            "max_confirmation_gap_observations": HYBRID_MAX_GAP,
        })
    output.sort(key=lambda row: (row["index"], row["sign"]))
    return output, {
        "status": "OK",
        "confirmation_rule": "FOCuS plus one Holdout-eligible Huber variant; same sign; max gap 8 observations",
        "focus_metadata": focus_meta,
        "huber_members": used_huber_arms,
    }


def calibrate_ensemble(
    development_traces: list[np.ndarray],
    holdout_traces: list[np.ndarray],
    thresholds: dict[str, float | None],
    rearm_quiet_points: int = REARM_POINTS,
) -> dict:
    if thresholds.get("FOCuS (reset-rearm)") is None or not any(
        thresholds.get(name) is not None
        for name in ("Post-Quiet Huber + MAD", "Post-Quiet Huber + Bartlett LRV")
    ):
        return {
            "status": "ABSTAINED",
            "raw_status": "MEMBER_THRESHOLD_UNAVAILABLE",
            "frozen_thresholds": thresholds,
            "development": {},
            "holdout": {"status": "NOT_RUN"},
            "reason": "HYBRID_REQUIRES_FOCUS_AND_AT_LEAST_ONE_HUBER_MEMBER",
        }

    def outcomes(traces):
        result = []
        for trace in traces:
            hits, metadata = hybrid_confirmation_hits(
                trace, thresholds, rearm_quiet_points=int(rearm_quiet_points)
            )
            result.append(None if metadata.get("status") != "OK" else bool(hits))
        return result

    dev_outcomes = outcomes(development_traces)
    valid_dev = [value for value in dev_outcomes if value is not None]
    if len(valid_dev) < MIN_VALID_REPLICATES:
        return {
            "status": "ABSTAINED",
            "raw_status": "INCONCLUSIVE",
            "frozen_thresholds": thresholds,
            "development": wilson_stats(0, len(valid_dev)),
            "holdout": {"status": "NOT_RUN"},
        }
    dev_alarms = sum(bool(value) for value in valid_dev)
    dev_stats = wilson_stats(dev_alarms, len(valid_dev))
    if dev_stats["wilson_upper_95_one_sided"] > DEV_P0_TARGET:
        return {
            "status": "ABSTAINED",
            "raw_status": "DEVELOPMENT_WILSON_GATE_FAILED",
            "frozen_thresholds": thresholds,
            "development": dev_stats,
            "holdout": {"status": "NOT_RUN_DEVELOPMENT_GATE_FAILED"},
        }

    hold_outcomes = outcomes(holdout_traces)
    valid_hold = [value for value in hold_outcomes if value is not None]
    hold_alarms = sum(bool(value) for value in valid_hold)
    hold_stats = wilson_stats(hold_alarms, len(valid_hold))
    if len(valid_hold) < MIN_VALID_REPLICATES:
        hold_status = "INCONCLUSIVE"
    elif hold_stats["wilson_upper_95_one_sided"] <= P0_TARGET:
        hold_status = "PASS"
    else:
        hold_status = "FAIL"
    return {
        "status": {"PASS": "VALIDATED", "FAIL": "NOT_VALIDATED",
                   "INCONCLUSIVE": "ABSTAINED"}[hold_status],
        "raw_status": hold_status,
        "frozen_thresholds": thresholds,
        "development": dev_stats,
        "holdout": {"status": hold_status, **hold_stats},
        "holdout_retuning": False,
        "confirmation_rule": "FOCuS plus at least one Holdout-eligible Huber scale variant, same sign, gap <= 8 observations",
    }


def eligible_hybrid_member_thresholds(arms: dict[str, dict]) -> dict[str, float | None]:
    """Keep the Development-calibrated FOCuS trigger; gate Huber confirmations by Holdout."""
    focus_name = "FOCuS (reset-rearm)"
    focus_threshold = arms.get(focus_name, {}).get("frozen_threshold")
    thresholds = {focus_name: focus_threshold}
    for name in ("Post-Quiet Huber + MAD", "Post-Quiet Huber + Bartlett LRV"):
        member = arms.get(name, {})
        thresholds[name] = (
            member.get("frozen_threshold")
            if member.get("status") == "VALIDATED"
            else None
        )
    return thresholds

def calibrate_series(
    series_id: str, rows: list[dict], tape_sha: str, series_config: dict,
) -> dict:
    values = np.asarray([row["value_float"] for row in rows], dtype=float)
    rearm_quiet_points = focus_rearm_points_for_frequency(series_config["frequency"])
    if values.size <= QUIET_POINTS:
        raise ValueError(f"C3_V2_SERIES_TOO_SHORT:{series_id}")
    model = select_ar_model(values[:QUIET_POINTS])
    if model.get("status") != "OK":
        return {
            "status": "COMPLETED_WITH_CALIBRATION_EXCEPTIONS",
            "selected_ar_order": model.get("selected_order"),
            "ar_model_status": model.get("status"),
            "ar_model_reason": model.get("reason"),
            "arms": {
                name: {"status": "ABSTAINED", "reason": "AR_MODEL_NOT_ELIGIBLE"}
                for name in CANDIDATES
            },
        }

    development_traces = []
    holdout_traces = []
    seed_material = []
    for phase, target in (("development", development_traces), ("holdout", holdout_traces)):
        for replicate in range(REPLICATES):
            seed = deterministic_seed(
                tape_sha, series_id, int(model["order"]), phase, replicate
            )
            seed_material.append(f"{phase}:{replicate}:{seed}")
            target.append(generate_ar_null_trace(
                model, values[:QUIET_POINTS], int(values.size), seed
            ))
            if (replicate + 1) % 250 == 0:
                print(
                    "C3_V2_NULL_PROGRESS series=" + series_id
                    + " phase=" + phase
                    + " completed=" + str(replicate + 1) + "/" + str(REPLICATES),
                    flush=True,
                )

    arms = {}
    arms["FOCuS (reset-rearm)"] = calibrate_focus(
        development_traces, holdout_traces, rearm_quiet_points=rearm_quiet_points
    )
    arms["FOCuS (reset-rearm)"]["threshold_grid"] = list(FOCUS_GRID)
    arms["FOCuS (reset-rearm)"]["rearm_quiet_points"] = rearm_quiet_points
    focus4_rearm_points = 4 if series_config["frequency"] == "Monthly" else 20
    arms[FOCUS4_NAME] = calibrate_focus(
        development_traces, holdout_traces,
        rearm_quiet_points=focus4_rearm_points,
    )
    arms[FOCUS4_NAME]["threshold_grid"] = list(FOCUS_GRID)
    arms[FOCUS4_NAME]["rearm_quiet_points"] = focus4_rearm_points
    for detector, scale in (
        ("Post-Quiet Huber + MAD", "mad"),
        ("Post-Quiet Huber + Bartlett LRV", "bartlett"),
    ):
        dev_scores = [huber_max_statistic(trace, scale) for trace in development_traces]
        hold_scores = [huber_max_statistic(trace, scale) for trace in holdout_traces]
        arms[detector] = choose_threshold_by_dev_wilson(
            dev_scores, hold_scores, HUBER_GRID
        )
        arms[detector]["threshold_grid"] = list(HUBER_GRID)

    member_thresholds = eligible_hybrid_member_thresholds(arms)
    arms["Hybrid: FOCuS + Huber confirmation"] = calibrate_ensemble(
        development_traces, holdout_traces, member_thresholds,
        rearm_quiet_points=rearm_quiet_points,
    )
    arms["Hybrid: FOCuS + Huber confirmation"]["rearm_quiet_points"] = rearm_quiet_points
    validated = all(arms[name]["status"] == "VALIDATED" for name in CANDIDATES)
    return {
        "status": "ALL_CANDIDATES_VALIDATED" if validated
                  else "COMPLETED_WITH_CALIBRATION_EXCEPTIONS",
        "selected_ar_order": int(model["order"]),
        "ar_model": {
            key: clean(model.get(key)) for key in (
                "order", "intercept", "ar_coefficients", "residual_sigma",
                "residual_pool_sha256", "aic", "roots_abs",
            )
        },
        "seed_ledger_sha256": sha256("\n".join(seed_material).encode("utf-8")),
        "series_transform": series_config.get("series_transform", "level"),
        "analysis_units": series_config.get("analysis_units", series_config["units"]),
        "rearm_quiet_points": rearm_quiet_points,
        "valid_null_replicates_per_phase": {
            "development": REPLICATES, "holdout": REPLICATES,
        },
        "arms": arms,
    }


def extract_hits(
    detector: str, values: np.ndarray, calibration: dict,
) -> tuple[list[dict], str, dict]:
    arms = calibration.get("arms", {})
    if detector in CANDIDATES:
        arm = arms.get(detector, {})
        rearm_quiet_points = int(arm.get("rearm_quiet_points", REARM_POINTS))
        if detector == "Hybrid: FOCuS + Huber confirmation":
            hits, metadata = hybrid_confirmation_hits(
                values, arm.get("frozen_thresholds", {}),
                rearm_quiet_points=rearm_quiet_points,
            )
            return hits, metadata.get("status", "ABSTAIN"), metadata
        threshold = arm.get("frozen_threshold")
        if threshold is None:
            return [], "ABSTAIN", {"reason": "NO_FROZEN_THRESHOLD"}
        return extract_detector_hits(
            detector, values, float(threshold), rearm_quiet_points=rearm_quiet_points
        )
    return extract_detector_hits(detector, values)


def audit_prefix_replay(
    detector: str,
    values: np.ndarray,
    hits: list[dict],
    calibration: dict,
) -> int:
    for hit in hits:
        index = int(hit["index"])
        prefix_hits, status, _ = extract_hits(
            detector, values[:index + 1], calibration
        )
        if status in {"ABSTAIN", "NOT_ELIGIBLE"} or not any(
            int(candidate["index"]) == index and int(candidate["sign"]) == int(hit["sign"])
            for candidate in prefix_hits
        ):
            raise ValueError(
                f"C3_V2_NO_LOOKAHEAD_PREFIX_REPLAY_FAILED:{detector}:{index}"
            )
    return len(hits)


def match_events_one_to_one(
    rows: list[dict],
    events: list[dict],
    hits: list[dict],
    detector: str,
) -> tuple[list[dict], dict]:
    """Maximum-cardinality, minimum-total-lag one-to-one event/alert assignment."""
    by_hit = {}
    for hit_number, hit in enumerate(hits):
        index = int(hit["index"])
        if not 0 <= index < len(rows):
            raise ValueError(f"C3_V2_MATCH_HIT_INDEX_OUT_OF_RANGE:{detector}:{index}")
        available = rows[index]["available_at_obj"]
        by_hit[hit_number] = {
            **hit,
            "hit_number": hit_number,
            "available_at_obj": available,
            "available_at": available.isoformat(),
        }

    event_count = len(events)
    hit_count = len(hits)
    source = 0
    event_offset = 1
    hit_offset = event_offset + event_count
    sink = hit_offset + hit_count
    graph: list[list[dict]] = [[] for _ in range(sink + 1)]

    def add_edge(start: int, end: int, capacity: int, cost: int) -> int:
        forward = {
            "to": end,
            "reverse": len(graph[end]),
            "capacity": capacity,
            "cost": cost,
        }
        reverse = {
            "to": start,
            "reverse": len(graph[start]),
            "capacity": 0,
            "cost": -cost,
        }
        graph[start].append(forward)
        graph[end].append(reverse)
        return len(graph[start]) - 1

    event_hit_edge: dict[tuple[int, int], int] = {}
    for event_index, event in enumerate(events):
        event_node = event_offset + event_index
        add_edge(source, event_node, 1, 0)
        anchor = date.fromisoformat(event["anchor_date"])
        window_start = add_calendar_months(anchor, -12)
        window_end = add_calendar_months(anchor, 12)
        expected_sign = int(event["expected_sign"])
        eligible = []
        for hit_number, hit in by_hit.items():
            available = hit["available_at_obj"]
            if int(hit["sign"]) == expected_sign and window_start <= available <= window_end:
                distance = abs((available - anchor).days)
                eligible.append((distance, available, int(hit["index"]), hit_number))
        for distance, _available, _index, hit_number in sorted(eligible):
            event_hit_edge[(event_index, hit_number)] = add_edge(
                event_node, hit_offset + hit_number, 1, distance
            )

    for hit_number in range(hit_count):
        add_edge(hit_offset + hit_number, sink, 1, 0)

    # Successive shortest augmenting paths produce maximum cardinality first;
    # shortest residual paths then minimize total absolute calendar lag.
    node_count = len(graph)
    while True:
        distances = [math.inf] * node_count
        previous: list[tuple[int, int] | None] = [None] * node_count
        distances[source] = 0
        for _ in range(node_count - 1):
            changed = False
            for node in range(node_count):
                if math.isinf(distances[node]):
                    continue
                for edge_index, edge in enumerate(graph[node]):
                    if edge["capacity"] <= 0:
                        continue
                    target = int(edge["to"])
                    candidate = distances[node] + int(edge["cost"])
                    if candidate < distances[target]:
                        distances[target] = candidate
                        previous[target] = (node, edge_index)
                        changed = True
            if not changed:
                break
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            parent, edge_index = previous[node]
            edge = graph[parent][edge_index]
            edge["capacity"] -= 1
            graph[node][edge["reverse"]]["capacity"] += 1
            node = parent

    assigned_events: dict[str, int] = {}
    assigned_hits: set[int] = set()
    for event_index, event in enumerate(events):
        event_node = event_offset + event_index
        for hit_number in range(hit_count):
            edge_index = event_hit_edge.get((event_index, hit_number))
            if edge_index is not None and graph[event_node][edge_index]["capacity"] == 0:
                assigned_events[str(event["event_id"])] = hit_number
                assigned_hits.add(hit_number)
                break

    results = []
    frequency = rows[0]["frequency"] if rows else ""
    unit = "weeks" if "Weekly" in frequency else "months"
    for event in events:
        anchor = date.fromisoformat(event["anchor_date"])
        window_start = add_calendar_months(anchor, -12)
        window_end = add_calendar_months(anchor, 12)
        expected_sign = int(event["expected_sign"])
        event_id = str(event["event_id"])
        matched_number = assigned_events.get(event_id)
        in_window = [
            (number, hit) for number, hit in by_hit.items()
            if window_start <= hit["available_at_obj"] <= window_end
        ]
        wrong_sign = [
            hit for number, hit in in_window
            if number not in assigned_hits and int(hit["sign"]) != expected_sign
        ]
        eligible_assigned_elsewhere = [
            hit for number, hit in in_window
            if number in assigned_hits and int(hit["sign"]) == expected_sign
        ]
        correct_sign_outside_window = [
            hit for hit in by_hit.values()
            if int(hit["sign"]) == expected_sign
            and (hit["available_at_obj"] < window_start or hit["available_at_obj"] > window_end)
        ]

        if matched_number is not None:
            hit = by_hit[matched_number]
            detected_at = hit["available_at_obj"]
            lag_days = (detected_at - anchor).days
            lag = lag_days / 7.0 if unit == "weeks" else lag_days / 30.4375
            match_status, hit_miss = "MATCHED", "HIT"
            detection_index = int(hit["index"])
            detection_at = hit["available_at"]
        else:
            if wrong_sign:
                match_status = "WRONG_SIGN"
            elif eligible_assigned_elsewhere:
                match_status = "ELIGIBLE_ALERT_ASSIGNED_TO_OTHER_EVENT"
            else:
                match_status = "NO_MATCH"
            hit_miss = "MISS"
            detection_index = detection_at = lag_days = lag = None

        results.append({
            "event_id": event_id,
            "episode_id": event["episode_id"],
            "series_id": event["series_id"],
            "detector": detector,
            "anchor_date": event["anchor_date"],
            "anchor_type": event["anchor_type"],
            "expected_sign": expected_sign,
            "matching_window_start": window_start.isoformat(),
            "matching_window_end": window_end.isoformat(),
            "hit_miss": hit_miss,
            "match_status": match_status,
            "wrong_sign_within_window_alarm_count": len(wrong_sign),
            "eligible_alerts_assigned_to_other_events": len(eligible_assigned_elsewhere),
            "correct_sign_outside_window_alarm_count": len(correct_sign_outside_window),
            "detection_index": detection_index,
            "detection_available_at": detection_at,
            "detection_lag_days": lag_days,
            "detection_lag_weeks_or_months": round(lag, 3) if lag is not None else None,
            "lag_unit": unit,
        })

    unmatched = [
        hit for number, hit in by_hit.items() if number not in assigned_hits
    ]
    unmatched_summary = {
        "unmatched_alarm_count": len(unmatched),
        "unmatched_alarm_dates": [row["available_at"] for row in unmatched],
        "matched_alarm_count": len(assigned_hits),
        "matched_event_count": len(assigned_events),
        "total_alarm_count": len(hits),
        "one_to_one_assignment": True,
        "assignment_policy": "maximum-cardinality then minimum-total-absolute-calendar-lag",
    }
    return results, unmatched_summary


def summarize_detector_results(
    calibration: dict[str, dict],
    historical_results: list[dict],
    unmatched: dict[str, dict],
) -> dict:
    summary = {}
    total_series = len(calibration)
    for detector in ALL_DETECTORS:
        validated_series = (
            sum(
                calibration[sid]["arms"].get(detector, {}).get("status") == "VALIDATED"
                for sid in calibration
            ) if detector in CANDIDATES else 0
        )
        rows = [row for row in historical_results if row["detector"] == detector]
        matched = [row for row in rows if row["hit_miss"] == "HIT"]
        episode_ids = sorted({row["episode_id"] for row in matched})
        lags = [
            abs(int(row["detection_lag_days"]))
            for row in matched if row["detection_lag_days"] is not None
        ]
        unmatched_by_series = {
            sid: unmatched.get(f"{sid}|{detector}", {}).get("unmatched_alarm_count", 0)
            for sid in calibration
        }
        summary[detector] = {
            "role": "CANDIDATE" if detector in CANDIDATES else "READ_ONLY",
            "validated_series_count": int(validated_series),
            "series_count": total_series,
            "validated_all_series": validated_series == total_series,
            "matched_event_series_pairs": len(matched),
            "total_event_series_pairs": len(rows),
            "matched_episode_clusters": len(episode_ids),
            "episode_clusters_with_any_registered_pair": len({
                row["episode_id"] for row in rows
            }),
            "total_unmatched_alarm_count": int(sum(unmatched_by_series.values())),
            "unmatched_alarm_count_by_series": unmatched_by_series,
            "median_absolute_detection_lag_days": (
                float(np.median(lags)) if lags else None
            ),
        }

    eligible = [
        (name, values) for name, values in summary.items()
        if name in CANDIDATES
        and values["validated_all_series"]
        and values["matched_event_series_pairs"] >= MIN_WINNER_MATCHED_PAIRS
        and values["matched_episode_clusters"] >= MIN_WINNER_EPISODE_CLUSTERS
    ]
    ranking_rule = (
        "Eligible only after Holdout Wilson U95 <= 0.10 on every series, "
        f"at least {MIN_WINNER_MATCHED_PAIRS} matched event-series pairs, and "
        f"at least {MIN_WINNER_EPISODE_CLUSTERS} distinct episode clusters; "
        "then maximize episode coverage and pairs, minimize unmatched alarms, "
        "and minimize median absolute detection lag. The Per-Series Router is "
        "reported separately as a retrospective optimization profile."
    )
    if not eligible:
        summary["global_selection"] = {
            "status": "NO_GLOBAL_WINNER",
            "reason": "NO_DETECTOR_PASSED_RISK_AND_HISTORICAL_COVERAGE_GATES",
            "ranking_rule": ranking_rule,
        }
    else:
        ranked = sorted(
            eligible,
            key=lambda item: (
                -item[1]["matched_episode_clusters"],
                -item[1]["matched_event_series_pairs"],
                item[1]["total_unmatched_alarm_count"],
                item[1]["median_absolute_detection_lag_days"]
                if item[1]["median_absolute_detection_lag_days"] is not None else math.inf,
                item[0],
            ),
        )
        summary["global_selection"] = {
            "status": "SELECTED",
            "winner": ranked[0][0],
            "ranking_rule": ranking_rule,
            "ranked_eligible_detectors": [name for name, _ in ranked],
        }
    return summary


def markdown_report(report: dict) -> str:
    lines = [
        "# CHAOS C3 v2.1 — Operational Detector Optimization",
        "",
        "- Status: **" + report["status"] + "**",
        "- Run ID: " + str(report["run_id"]),
        "- Evaluation commit: " + str(report["evaluation_commit"]),
        "- Event anchors: **" + str(report["cohort"]["event_count"]) + "**",
        "- Episode clusters: **" + str(report["cohort"]["episode_clusters"]) + "**",
        "- Event-series pairs: **" + str(report["cohort"]["event_series_pairs"]) + "**",
        "- Unique series: **" + str(report["cohort"]["series_count"]) + "**",
        "- Source archive SHA-256: " + report["source_integrity"]["archive_sha256"],
        "- First-release tape SHA-256: " + report["source_integrity"]["tape_sha256"],
        "- Transformed analysis tape SHA-256: " + report["source_integrity"]["analysis_tape_sha256"],
        "- Development calibration margin: one-sided Wilson U95 <= 0.085",
        "- Holdout risk acceptance: one-sided Wilson U95 <= 0.10; Holdout also selects eligible Hybrid members for this optimization iteration",
        "- Replicates per series: 1000 Development + 1000 Holdout optimization traces",
        "- FOCuS policy: 40 initial observations; primary Monthly re-arm 5 observations; explicit Monthly 4-observation comparison; Weekly re-arm 20; up to 12 alerts",
        "- Hybrid policy: FOCuS plus one or more Holdout-eligible Huber members, same direction, within eight observations",
        "- PAYEMS analysis transform: causal first difference; other series remain at level",
        "",
        "## 1. Per-series calibration",
        "",
        "| Series | Detector | Frozen threshold | Dev P0 | Dev Wilson U95 | Holdout P0 | Holdout Wilson U95 | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for sid in sorted(report["calibration"]):
        for detector in CANDIDATES:
            arm = report["calibration"][sid]["arms"].get(detector, {})
            dev = arm.get("development", {})
            hold = arm.get("holdout", {})
            threshold = arm.get("frozen_threshold")
            if threshold is None and arm.get("frozen_thresholds"):
                threshold = json.dumps(arm["frozen_thresholds"], sort_keys=True)
            lines.append(
                "| " + sid + " | " + detector + " | "
                + str(threshold if threshold is not None else "—") + " | "
                + str(dev.get("p0", "—")) + " | "
                + str(dev.get("wilson_upper_95_one_sided", "—")) + " | "
                + str(hold.get("p0", "—")) + " | "
                + str(hold.get("wilson_upper_95_one_sided", "—")) + " | "
                + str(arm.get("status", "ABSTAINED")) + " |"
            )
    lines += [
        "",
        "## 2. Historical event matching",
        "",
        "| Event / Series | Detector | Expected sign | Result | Match | Wrong-sign alerts | Assigned elsewhere | Available at | Lag |",
        "|---|---|---:|---|---:|---:|---:|---|---:|",
    ]
    for row in report["historical_results"]:
        lag = (
            str(row["detection_lag_weeks_or_months"]) + " " + row["lag_unit"]
            if row["detection_lag_weeks_or_months"] is not None else "—"
        )
        lines.append(
            "| " + row["event_id"] + " / " + row["series_id"] + " | "
            + row["detector"] + " | " + str(row["expected_sign"]) + " | "
            + row["hit_miss"] + " | " + row["match_status"] + " | "
            + str(row["wrong_sign_within_window_alarm_count"]) + " | "
            + str(row["eligible_alerts_assigned_to_other_events"]) + " | "
            + str(row["detection_available_at"] or "—") + " | " + lag + " |"
        )
    lines += [
        "",
        "## 3. Risk-first detector comparison",
        "",
        "| Detector | Role | Validated series | Matched pairs | Matched episode clusters | Unmatched alarms | Median absolute lag (days) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for detector in ALL_DETECTORS:
        row = report["detector_summary"][detector]
        validated_series_label = (
            str(row["validated_series_count"]) + "/" + str(row["series_count"])
            if row["role"] == "CANDIDATE" else "—"
        )
        lines.append(
            "| " + detector + " | " + row["role"] + " | "
            + validated_series_label + " | "
            + str(row["matched_event_series_pairs"]) + "/" + str(row["total_event_series_pairs"]) + " | "
            + str(row["matched_episode_clusters"]) + "/" + str(row["episode_clusters_with_any_registered_pair"]) + " | "
            + str(row["total_unmatched_alarm_count"]) + " | "
            + str(row["median_absolute_detection_lag_days"] or "—") + " |"
        )
    selection = report["detector_summary"]["global_selection"]
    lines += [
        "",
        "- Global selection: **" + str(selection.get("status")) + "**",
        "- Winner: **" + str(selection.get("winner", "none")) + "**",
        "- Ranking: " + selection["ranking_rule"],
        "",
        "## 4. Interpretation and safeguards",
        "",
        "- Development thresholds are selected only when one-sided Wilson U95 is <= 0.10; Holdout applies the same bound once and cannot retune.",
        "- Each source series has its own AR(1–3) model, fitted on the first 40 first-release observations only.",
        "- Event anchors are external historical labels; matching is not causal attribution or proof of exact structural-break onset.",
        "- The 20 anchors are clustered into 10 episodes. Event-series pairs are not treated as independent shocks.",
        "- One alert can match at most one event per series and detector; unmatched alerts are counted once.",
        "- A_FAST and A_CONSENSUS are read-only comparators and are not claimed to be equal-risk calibrated.",
        "- A candidate that fails Holdout remains diagnostic only and cannot be named the global winner.",
        "- A global winner must also detect at least three distinct episode clusters and three event-series pairs; low false-alarm risk alone is insufficient.",
        "- The Per-Series Router is selected retrospectively against this registered event cohort and is an optimization result, not an independent validation result.",
        "",
        "## 5. Reproducibility",
        "",
        "- Replay command: " + report["replay_command"],
        "- Report JSON SHA-256: " + str(report.get("report_json_sha256", "PENDING")),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True)
    parser.add_argument(
        "--contract",
        default="p1_4_validation/c3/c3_expanded_event_cohort_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/p1_4/c3/v2_expanded_evaluation",
    )
    args = parser.parse_args()

    source_archive_path = Path(args.source_zip)
    manifest, by_series, contract, archive_sha, contract_sha = verify_source_bundle(
        source_archive_path, Path(args.contract)
    )
    by_series, transform_audit = apply_causal_series_transforms(
        source_archive_path, manifest, by_series, contract
    )
    analysis_tape_sha = analysis_tape_sha256(by_series)
    calibration = {}
    for series_id in sorted(by_series):
        series_cal = calibrate_series(
            series_id, by_series[series_id],
            manifest["normalized_tape"]["sha256"],
            {row["series_id"]: row for row in contract["series"]}[series_id],
        )
        calibration[series_id] = series_cal
        print(
            "C3_V2_SERIES_CALIBRATED series=" + series_id
            + " status=" + str(series_cal.get("status")),
            flush=True,
        )

    event_pairs_by_series = {}
    for event in contract["events"]:
        for series_id, sign in event["expected_sign_by_series"].items():
            event_pairs_by_series.setdefault(series_id, []).append({
                **event,
                "series_id": series_id,
                "expected_sign": int(sign),
            })

    historical_results = []
    unmatched_summaries = {}
    for series_id in sorted(by_series):
        rows = by_series[series_id]
        values = np.asarray([row["value_float"] for row in rows], dtype=float)
        series_cal = calibration[series_id]
        for detector in ALL_DETECTORS:
            hits, detector_status, metadata = extract_hits(
                detector, values, series_cal
            )
            replayed = audit_prefix_replay(
                detector, values, hits, series_cal
            ) if hits else 0
            matched_rows, unmatched = match_events_one_to_one(
                rows, event_pairs_by_series.get(series_id, []), hits, detector
            )
            unmatched["detector_status"] = detector_status
            unmatched["detector_metadata"] = clean(metadata)
            unmatched["no_lookahead_prefix_replays"] = replayed
            unmatched_summaries[f"{series_id}|{detector}"] = unmatched
            arm_details = (
                series_cal.get("arms", {}).get(detector, {})
                if detector in CANDIDATES else {}
            )
            arm_status = arm_details.get("status", "READ_ONLY")
            development = arm_details.get("development", {})
            holdout = arm_details.get("holdout", {})
            for row in matched_rows:
                historical_results.append({
                    **row,
                    "validation_status": arm_status or "ABSTAINED",
                    "frozen_threshold": arm_details.get("frozen_threshold"),
                    "frozen_thresholds": arm_details.get("frozen_thresholds"),
                    "development_p0": development.get("p0"),
                    "development_wilson_u95": development.get("wilson_upper_95_one_sided"),
                    "holdout_p0": holdout.get("p0"),
                    "holdout_wilson_u95": holdout.get("wilson_upper_95_one_sided"),
                    "detector_status": detector_status,
                    "no_lookahead_prefix_replays": replayed,
                    "unmatched_alarm_count_for_series_detector": unmatched["unmatched_alarm_count"],
                })

    detector_summary = summarize_detector_results(
        calibration, historical_results, unmatched_summaries
    )
    all_calibrated = all(
        calibration[sid].get("status") == "ALL_CANDIDATES_VALIDATED"
        for sid in calibration
    )
    report = {
        "schema_version": "2.1.0",
        "status": (
            "C3_V2_1_ALL_SERIES_ALL_CANDIDATES_VALIDATED"
            if all_calibrated
            else "C3_V2_1_COMPLETED_WITH_CALIBRATION_EXCEPTIONS"
        ),
        "run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL_REPLAY"),
        "evaluation_commit": os.environ.get("GITHUB_SHA", "LOCAL_REPLAY"),
        "cohort": {
            "event_count": len(contract["events"]),
            "episode_clusters": len({event["episode_id"] for event in contract["events"]}),
            "event_series_pairs": sum(
                len(event["expected_sign_by_series"]) for event in contract["events"]
            ),
            "series_count": len(by_series),
            "series_ids": sorted(by_series),
        },
        "source_integrity": {
            "archive_sha256": archive_sha,
            "tape_sha256": manifest["normalized_tape"]["sha256"],
            "analysis_tape_sha256": analysis_tape_sha,
            "contract_sha256": contract_sha,
            "source_intake_run_id": manifest.get("workflow_run_id"),
            "source_intake_commit": manifest.get("source_commit"),
            "point_count": manifest["point_count"],
            "raw_batch_count": len(manifest.get("raw_vintage_batches", [])),
            "source_contract_sha256": manifest.get("contract_sha256"),
            "source_contract_id": manifest.get("contract_id"),
            "analysis_transforms": transform_audit,
            "source_archive_mutated": False,
        },
        "calibration_protocol": {
            "p0_target": P0_TARGET,
            "development_p0_target": DEV_P0_TARGET,
            "minimum_winner_matched_event_series_pairs": MIN_WINNER_MATCHED_PAIRS,
            "minimum_winner_episode_clusters": MIN_WINNER_EPISODE_CLUSTERS,
            "confidence_bound": "one-sided Wilson 95%",
            "development_selection_rule": "lowest predeclared threshold with Dev Wilson U95 <= 0.085",
            "holdout_validation_rule": "Holdout Wilson U95 <= 0.10; current Holdout results also select eligible Hybrid members and the per-series router profile in this optimization iteration.",
            "holdout_retuning": False,
            "replicates_per_series_phase": REPLICATES,
            "minimum_valid_replicates_per_phase": MIN_VALID_REPLICATES,
            "first_observations_for_ar_fit": QUIET_POINTS,
            "ar_orders": [1, 2, 3],
            "ar_selection": "minimum AIC; unstable winner fails closed",
            "null_generator": "AR(p) residual bootstrap",
            "focus_policy": "40 initial; monthly primary rearm 5 with monthly rearm 4 comparison; weekly rearm 20; maximum 12 alerts",
            "huber_policy": "MAD or Bartlett LRV scale; two-sided Huber score",
            "hybrid_policy": "FOCuS + one or more Holdout-eligible Huber variants; same sign; gap <= 8 observations",
            "hybrid_member_gate": "Only members with status VALIDATED are passed into Hybrid for each series.",
            "per_series_router": "Chooses among members that passed the per-series Holdout risk gate, ranking them by matches to the registered historical event cohort. This is a retrospective optimization profile, not independent performance validation.",
            "independent_validation_required": True,
            "optimization_mode": "OPERATIONAL_TUNING_USING_CURRENT_DEVELOPMENT_AND_HOLDOUT_COHORTS",
            "event_matching": "one-to-one direction-constrained calendar-exact ±12 months",
            "seed_namespace": "CHAOS:C3_V2_EXPANDED",
        },
        "registered_series": [
            {
                "series_id": series["series_id"],
                "series_source": series["series_source"],
                "series_reference_url": series["series_reference_url"],
                "observation_start": series["observation_start"],
                "observation_end": series["observation_end"],
                "frequency": series["frequency"],
                "units": series["units"],
                "analysis_units": series.get("analysis_units", series["units"]),
                "series_transform": series.get("series_transform", "level"),
                "minimum_observation_count": series["minimum_observation_count"],
            }
            for series in contract["series"]
        ],
        "registered_events": [
            {
                "event_id": event["event_id"],
                "episode_id": event["episode_id"],
                "anchor_date": event["anchor_date"],
                "anchor_type": event["anchor_type"],
                "label": event["label"],
                "expected_sign_by_series": event["expected_sign_by_series"],
                "sign_rationale": event["sign_rationale"],
                "reference_urls": event["reference_urls"],
            }
            for event in contract["events"]
        ],
        "calibration": calibration,
        "historical_results": historical_results,
        "unmatched_alarm_summary": unmatched_summaries,
        "detector_summary": detector_summary,
        "replay_command": (
            "python p1_4_validation/c3/run_c3_v2_equal_risk_evaluation.py "
            "--source-zip <c3-v2-expanded-source-intake.zip> "
            "--contract p1_4_validation/c3/c3_expanded_event_cohort_v1.json "
            "--output-dir artifacts/p1_4/c3/v2_expanded_evaluation"
        ),
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "C3_V2_EXPANDED_EVALUATION.json"
    json_path.write_bytes(canonical_json(report))
    report["report_json_sha256"] = sha256(json_path.read_bytes())
    markdown_path = output / "C3_V2_EXPANDED_EVALUATION.md"
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    csv_path = output / "C3_V2_EXPANDED_EVENT_RESULTS.csv"
    fields = [
        "event_id", "episode_id", "series_id", "detector", "anchor_date",
        "anchor_type", "expected_sign", "validation_status",
        "frozen_threshold", "frozen_thresholds", "routed_member",
        "development_p0", "development_wilson_u95",
        "holdout_p0", "holdout_wilson_u95",
        "hit_miss", "match_status",
        "wrong_sign_within_window_alarm_count",
        "eligible_alerts_assigned_to_other_events",
        "correct_sign_outside_window_alarm_count",
        "detection_index", "detection_available_at",
        "detection_lag_days", "detection_lag_weeks_or_months", "lag_unit",
        "no_lookahead_prefix_replays", "unmatched_alarm_count_for_series_detector",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in historical_results:
            writer.writerow({
                key: (
                    json.dumps(row.get(key), sort_keys=True)
                    if key == "frozen_thresholds" and row.get(key) is not None
                    else row.get(key)
                )
                for key in fields
            })

    print(markdown_path.read_text(encoding="utf-8"), flush=True)
    print("C3_V2_OUTPUTS " + json.dumps({
        "json": str(json_path),
        "json_sha256": report["report_json_sha256"],
        "markdown": str(markdown_path),
        "csv": str(csv_path),
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
