"""Real-artifact integration and real-series engine-output gates for C3 v2.1.

Level 1 remains the focused unit-test suite.
Level 2 validates the immutable ALFRED artifact and applies the real causal transforms.
Level 3 validates the completed detector replay over the real ALFRED series/event cohort.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p1_4_validation.c3 import run_c3_v2_equal_risk_evaluation as c3  # noqa: E402

EXPECTED_SERIES = {"UNRATE", "PAYEMS", "WCOILBRENTEU", "ICSA"}
EXPECTED_TRANSFORMS = {
    "UNRATE": "level",
    "PAYEMS": "first_difference",
    "WCOILBRENTEU": "level",
    "ICSA": "level",
}
EXPECTED_DETECTORS = (
    "FOCuS (reset-rearm)",
    c3.FOCUS4_NAME,
    "Post-Quiet Huber + MAD",
    "Post-Quiet Huber + Bartlett LRV",
    "Hybrid: FOCuS + Huber confirmation",
    "A_FAST",
    "A_CONSENSUS",
    c3.PER_SERIES_ROUTER,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(c3.canonical_json(payload))


def run_level_2_integration(
    source_zip: Path,
    contract_path: Path,
    expected_source_run_id: str,
    output_path: Path,
) -> dict:
    """Exercise real source validation and causal transformation on the archived ALFRED bundle."""
    source_zip = source_zip.resolve()
    initial_archive_sha = c3.sha256(source_zip.read_bytes())

    manifest, raw_by_series, contract, archive_sha, _contract_sha = (
        c3.verify_source_bundle(source_zip, contract_path)
    )
    actual_source_run_id = str(manifest.get("workflow_run_id", ""))
    if actual_source_run_id != str(expected_source_run_id):
        raise RuntimeError(
            "C3_V2_1_LEVEL2_SOURCE_RUN_ID_MISMATCH:"
            f"{actual_source_run_id}:{expected_source_run_id}"
        )

    if set(raw_by_series) != EXPECTED_SERIES:
        raise RuntimeError(
            "C3_V2_1_LEVEL2_SERIES_SET_MISMATCH:"
            f"{sorted(raw_by_series)}"
        )

    contract_transforms = {
        row["series_id"]: row.get("series_transform", "level")
        for row in contract["series"]
    }
    if contract_transforms != EXPECTED_TRANSFORMS:
        raise RuntimeError(
            f"C3_V2_1_LEVEL2_TRANSFORM_CONTRACT_MISMATCH:{contract_transforms}"
        )

    transformed, audit = c3.apply_causal_series_transforms(
        source_zip, manifest, raw_by_series, contract
    )
    analysis_sha = c3.analysis_tape_sha256(transformed)

    if set(transformed) != EXPECTED_SERIES:
        raise RuntimeError("C3_V2_1_LEVEL2_TRANSFORMED_SERIES_SET_MISMATCH")

    series_checks = {}
    for series_id in sorted(EXPECTED_SERIES):
        raw_rows = raw_by_series[series_id]
        analysis_rows = transformed[series_id]
        if len(raw_rows) != len(analysis_rows):
            raise RuntimeError(
                f"C3_V2_1_LEVEL2_OBSERVATION_COUNT_CHANGED:{series_id}:"
                f"{len(raw_rows)}:{len(analysis_rows)}"
            )
        for index, (raw_row, analysis_row) in enumerate(zip(raw_rows, analysis_rows)):
            if raw_row["observation_date"] != analysis_row["observation_date"]:
                raise RuntimeError(
                    f"C3_V2_1_LEVEL2_OBSERVATION_DATE_CHANGED:{series_id}:{index}"
                )
            if raw_row["available_at"] != analysis_row["available_at"]:
                raise RuntimeError(
                    f"C3_V2_1_LEVEL2_AVAILABLE_AT_CHANGED:{series_id}:{index}"
                )
            if not math.isfinite(float(analysis_row["value_float"])):
                raise RuntimeError(
                    f"C3_V2_1_LEVEL2_NON_FINITE_ANALYSIS_VALUE:{series_id}:{index}"
                )
            if series_id != "PAYEMS" and (
                float(raw_row["value_float"]) != float(analysis_row["value_float"])
            ):
                raise RuntimeError(
                    f"C3_V2_1_LEVEL2_LEVEL_SERIES_VALUE_CHANGED:{series_id}:{index}"
                )

        series_checks[series_id] = {
            "transform": audit[series_id]["transform"],
            "raw_observations": len(raw_rows),
            "analysis_observations": len(analysis_rows),
            "available_at_preserved_for_every_point": True,
            "all_analysis_values_finite": True,
            "analysis_units": audit[series_id]["analysis_units"],
        }

    payems_audit = audit["PAYEMS"]
    predecessor = payems_audit.get("predecessor", {})
    if predecessor.get("observation_date") != "1966-07-01":
        raise RuntimeError(
            "C3_V2_1_LEVEL2_PAYEMS_PREDECESSOR_DATE_MISMATCH:"
            + str(predecessor.get("observation_date"))
        )
    if predecessor.get("available_at") != "1966-08-08":
        raise RuntimeError(
            "C3_V2_1_LEVEL2_PAYEMS_PREDECESSOR_RELEASE_MISMATCH:"
            + str(predecessor.get("available_at"))
        )

    first_raw = raw_by_series["PAYEMS"][0]
    first_analysis = transformed["PAYEMS"][0]
    expected_first_difference = (
        float(first_raw["value_float"]) - float(predecessor["value"])
    )
    if not math.isclose(
        float(first_analysis["value_float"]),
        expected_first_difference,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError("C3_V2_1_LEVEL2_PAYEMS_FIRST_DIFFERENCE_MISMATCH")

    final_archive_sha = c3.sha256(source_zip.read_bytes())
    if final_archive_sha != initial_archive_sha or archive_sha != initial_archive_sha:
        raise RuntimeError("C3_V2_1_LEVEL2_SOURCE_ARCHIVE_CHANGED")

    total_points = sum(len(rows) for rows in raw_by_series.values())
    if total_points != int(manifest.get("point_count", -1)):
        raise RuntimeError("C3_V2_1_LEVEL2_POINT_COUNT_MISMATCH")

    report = {
        "schema_version": "1.0.0",
        "level": "LEVEL_2_REAL_ALFRED_INTEGRATION",
        "status": "PASS",
        "source_intake_run_id": actual_source_run_id,
        "source_contract_id": manifest.get("contract_id"),
        "source_archive_sha256": archive_sha,
        "source_tape_sha256": manifest["normalized_tape"]["sha256"],
        "analysis_tape_sha256": analysis_sha,
        "source_archive_mutated": False,
        "point_count": total_points,
        "raw_vintage_batch_count": len(manifest.get("raw_vintage_batches", [])),
        "event_count": len(contract["events"]),
        "episode_cluster_count": len({
            event["episode_id"] for event in contract["events"]
        }),
        "event_series_pair_count": sum(
            len(event["expected_sign_by_series"]) for event in contract["events"]
        ),
        "series": series_checks,
        "payems_predecessor": predecessor,
        "payems_first_difference": {
            "observation_date": first_analysis["observation_date"],
            "available_at": first_analysis["available_at"],
            "source_level": float(first_raw["value_float"]),
            "predecessor_level": float(predecessor["value"]),
            "difference": float(first_analysis["value_float"]),
            "matches_subtraction": True,
        },
        "checks": {
            "source_bundle_hashes_and_manifest_verified": True,
            "source_run_id_matches_requested_artifact": True,
            "all_four_real_series_loaded": True,
            "only_payems_transformed": True,
            "predecessor_extracted_from_archived_raw_vintages": True,
            "point_in_time_available_at_preserved": True,
            "original_source_archive_unchanged": True,
        },
    }
    _write_json(output_path, report)
    print(
        "C3_V2_1_LEVEL_2_PASS "
        + json.dumps({
            "source_run_id": actual_source_run_id,
            "point_count": total_points,
            "raw_batches": len(manifest.get("raw_vintage_batches", [])),
            "analysis_tape_sha256": analysis_sha,
            "report": str(output_path),
        }, sort_keys=True),
        flush=True,
    )
    return report


def run_level_3_engine_output_check(
    evaluation_dir: Path,
    expected_source_run_id: str,
) -> dict:
    """Check that the detector engine actually evaluated all real event-series pairs."""
    evaluation_dir = evaluation_dir.resolve()
    json_path = evaluation_dir / "C3_V2_EXPANDED_EVALUATION.json"
    markdown_path = evaluation_dir / "C3_V2_EXPANDED_EVALUATION.md"
    csv_path = evaluation_dir / "C3_V2_EXPANDED_EVENT_RESULTS.csv"
    for path in (json_path, markdown_path, csv_path):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"C3_V2_1_LEVEL3_OUTPUT_MISSING:{path.name}")

    report = json.loads(json_path.read_text(encoding="utf-8"))
    if report.get("schema_version") not in {"2.1.0", "2.2.0"}:
        raise RuntimeError("C3_V2_1_LEVEL3_REPORT_SCHEMA_MISMATCH")
    if str(report.get("source_integrity", {}).get("source_intake_run_id")) != str(
        expected_source_run_id
    ):
        raise RuntimeError("C3_V2_1_LEVEL3_SOURCE_RUN_ID_MISMATCH")

    cohort = report.get("cohort", {})
    expected_cohort = {
        "event_count": 20,
        "episode_clusters": 10,
        "event_series_pairs": 37,
        "series_count": 4,
    }
    for key, expected in expected_cohort.items():
        if int(cohort.get(key, -1)) != expected:
            raise RuntimeError(
                f"C3_V2_1_LEVEL3_COHORT_MISMATCH:{key}:"
                f"{cohort.get(key)}:{expected}"
            )
    if set(cohort.get("series_ids", [])) != EXPECTED_SERIES:
        raise RuntimeError("C3_V2_1_LEVEL3_SERIES_SET_MISMATCH")

    integrity = report.get("source_integrity", {})
    if integrity.get("source_archive_mutated") is not False:
        raise RuntimeError("C3_V2_1_LEVEL3_SOURCE_ARCHIVE_MUTATION_REPORTED")
    if len(str(integrity.get("archive_sha256", ""))) != 64:
        raise RuntimeError("C3_V2_1_LEVEL3_SOURCE_ARCHIVE_SHA_MISSING")
    if len(str(integrity.get("analysis_tape_sha256", ""))) != 64:
        raise RuntimeError("C3_V2_1_LEVEL3_ANALYSIS_TAPE_SHA_MISSING")
    transforms = integrity.get("analysis_transforms", {})
    actual_transforms = {
        series_id: transforms.get(series_id, {}).get("transform")
        for series_id in EXPECTED_SERIES
    }
    if actual_transforms != EXPECTED_TRANSFORMS:
        raise RuntimeError(
            f"C3_V2_1_LEVEL3_TRANSFORM_AUDIT_MISMATCH:{actual_transforms}"
        )

    summary = report.get("detector_summary", {})
    missing_detectors = set(EXPECTED_DETECTORS) - set(summary)
    if missing_detectors:
        raise RuntimeError(
            "C3_V2_1_LEVEL3_DETECTOR_SUMMARY_MISSING:"
            + ",".join(sorted(missing_detectors))
        )
    for detector in EXPECTED_DETECTORS:
        if int(summary[detector].get("total_event_series_pairs", -1)) != 37:
            raise RuntimeError(
                f"C3_V2_1_LEVEL3_DETECTOR_COHORT_INCOMPLETE:{detector}"
            )
    for detector in ("A_FAST", "A_CONSENSUS"):
        if summary[detector].get("role") != "READ_ONLY":
            raise RuntimeError(f"C3_V2_1_LEVEL3_BASELINE_ROLE_INVALID:{detector}")
    if summary[c3.PER_SERIES_ROUTER].get("role") != "COMPOSITE_OPTIMIZATION":
        raise RuntimeError("C3_V2_1_LEVEL3_ROUTER_ROLE_INVALID")
    router_profile = summary.get("per_series_router_profile", {})
    if router_profile.get("status") != "RETROSPECTIVE_OPTIMIZATION_ONLY":
        raise RuntimeError("C3_V2_1_LEVEL3_ROUTER_PROFILE_STATUS_INVALID")
    if router_profile.get("independent_validation_required") is not True:
        raise RuntimeError("C3_V2_1_LEVEL3_ROUTER_INDEPENDENT_VALIDATION_FLAG_MISSING")
    for series_id in EXPECTED_SERIES:
        route = report.get("calibration", {}).get(series_id, {}).get("per_series_router", {})
        selected_member = route.get("selected_detector")
        if selected_member is not None:
            if selected_member not in c3.ROUTER_MEMBER_DETECTORS:
                raise RuntimeError(f"C3_V2_1_LEVEL3_ROUTER_MEMBER_INVALID:{series_id}:{selected_member}")
            member_status = report["calibration"][series_id]["arms"][selected_member].get("status")
            if member_status != "VALIDATED":
                raise RuntimeError(f"C3_V2_1_LEVEL3_ROUTER_MEMBER_NOT_VALIDATED:{series_id}:{selected_member}")
        elif route.get("status") not in {"NO_VALIDATED_MEMBER", "NO_HISTORICAL_COVERAGE"}:
            raise RuntimeError(f"C3_V2_1_LEVEL3_ROUTER_EMPTY_ROUTE_STATUS_INVALID:{series_id}")
        elif route.get("status") == "NO_HISTORICAL_COVERAGE":
            scores = route.get("candidate_scores", [])
            if not any(row.get("validated") for row in scores):
                raise RuntimeError(f"C3_V2_1_LEVEL3_ROUTER_COVERAGE_ABSTENTION_WITHOUT_VALIDATED_MEMBER:{series_id}")
            if any(
                row.get("validated") and (
                    int(row.get("matched_event_series_pairs", 0)) > 0
                    or int(row.get("matched_episode_clusters", 0)) > 0
                )
                for row in scores
            ):
                raise RuntimeError(f"C3_V2_1_LEVEL3_ROUTER_IGNORED_HISTORICAL_COVERAGE:{series_id}")

    historical = report.get("historical_results", [])
    counts = Counter(row.get("detector") for row in historical)
    for detector in EXPECTED_DETECTORS:
        if counts[detector] != 37:
            raise RuntimeError(
                f"C3_V2_1_LEVEL3_HISTORICAL_ROWS_INCOMPLETE:"
                f"{detector}:{counts[detector]}"
            )
    if len(historical) != 37 * len(EXPECTED_DETECTORS):
        raise RuntimeError(
            f"C3_V2_1_LEVEL3_HISTORICAL_ROW_TOTAL_MISMATCH:{len(historical)}"
        )

    unmatched = report.get("unmatched_alarm_summary", {})
    if len(unmatched) != len(EXPECTED_SERIES) * len(EXPECTED_DETECTORS):
        raise RuntimeError(
            f"C3_V2_1_LEVEL3_REPLAY_AUDIT_COUNT_MISMATCH:{len(unmatched)}"
        )
    for key, item in unmatched.items():
        if "no_lookahead_prefix_replays" not in item:
            raise RuntimeError(f"C3_V2_1_LEVEL3_PREFIX_AUDIT_MISSING:{key}")

    matched_by_detector = {
        detector: int(summary[detector].get("matched_event_series_pairs", 0))
        for detector in EXPECTED_DETECTORS
    }
    unmatched_alarms_by_detector = {
        detector: int(summary[detector].get("total_unmatched_alarm_count", 0))
        for detector in EXPECTED_DETECTORS
    }
    global_selection = summary.get("global_selection", {})
    result = {
        "schema_version": "1.0.0",
        "level": "LEVEL_3_REAL_SERIES_ENGINE_REPLAY",
        "status": "PASS",
        "engine_status": report.get("status"),
        "source_intake_run_id": str(expected_source_run_id),
        "series_count": len(EXPECTED_SERIES),
        "event_count": cohort["event_count"],
        "episode_cluster_count": cohort["episode_clusters"],
        "event_series_pair_count": cohort["event_series_pairs"],
        "detector_count": len(EXPECTED_DETECTORS),
        "historical_result_rows": len(historical),
        "prefix_audit_series_detector_pairs": len(unmatched),
        "matched_event_series_pairs_by_detector": matched_by_detector,
        "unmatched_alarms_by_detector": unmatched_alarms_by_detector,
        "global_selection": global_selection,
        "per_series_router_members": router_profile.get("selected_member_by_series", {}),
        "outputs": {
            "json": json_path.name,
            "markdown": markdown_path.name,
            "csv": csv_path.name,
        },
        "checks": {
            "engine_report_present_and_parseable": True,
            "all_four_real_series_processed": True,
            "all_37_event_series_pairs_evaluated_for_eight_detectors": True,
        "per_series_router_uses_only_holdout_validated_members": True,
        "per_series_router_marked_retrospective_not_independent": True,
            "readonly_baselines_included": True,
            "no_lookahead_prefix_audit_present_for_every_series_detector": True,
            "source_and_analysis_hashes_present": True,
        },
        "performance_interpretation": (
            "Execution PASS is separate from detector performance. "
            "NO_GLOBAL_WINNER or calibration exceptions are valid measured outcomes, "
            "not workflow failures."
        ),
    }
    output_path = evaluation_dir / "C3_V2_1_LEVEL3_ENGINE_CHECK.json"
    _write_json(output_path, result)
    print(
        "C3_V2_1_LEVEL_3_PASS "
        + json.dumps({
            "historical_rows": len(historical),
            "matched_pairs": matched_by_detector,
            "unmatched_alarms": unmatched_alarms_by_detector,
            "global_selection": global_selection.get("status"),
            "per_series_router_members": router_profile.get("selected_member_by_series", {}),
            "report": str(output_path),
        }, sort_keys=True),
        flush=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("integration", "engine-output"), required=True)
    parser.add_argument("--source-zip", default="")
    parser.add_argument("--contract", default="p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json")
    parser.add_argument("--expected-source-run-id", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--evaluation-dir", default="artifacts/p1_4/c3/v2_expanded_evaluation")
    args = parser.parse_args()

    if args.mode == "integration":
        if not args.source_zip or not args.output:
            parser.error("--source-zip and --output are required for integration mode")
        run_level_2_integration(
            Path(args.source_zip),
            Path(args.contract),
            args.expected_source_run_id,
            Path(args.output),
        )
        return 0

    run_level_3_engine_output_check(
        Path(args.evaluation_dir),
        args.expected_source_run_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
