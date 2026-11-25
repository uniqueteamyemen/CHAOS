from __future__ import annotations

import argparse
import hashlib
import json
import math
import collections
from collections import defaultdict
from pathlib import Path
from typing import Any
import sys

# Direct script execution sets sys.path[0] to scripts/p1_4; add repository
# root explicitly so repository packages resolve identically in Actions.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import numpy as np

from p2_b_benchmark.dataset import load_p2_economic_series
from real_data_stress_pipeline.production_pipeline import candidate_sha256


C1_SEED = "CHAOS:P1.4:C1:PILOT:v1"
C2_FRAME_SEED = "CHAOS:P1.4:C2:FRAME:v1"
C2_PILOT_SEED = "CHAOS:P1.4:C2:PILOT:v1"
C1_FAILURE_QUOTAS = {
    # Minimum representation requested for the three G1 failure mechanisms.
    # The 12/6/2 split oversamples the two smaller diagnostic classes relative
    # to their population share; it is not a prevalence estimator.
    "ADF_PASS_KPSS_FAIL": 12,
    "ADF_FAIL_KPSS_FAIL": 6,
    "ADF_FAIL_KPSS_PASS": 2,
}
SOURCE_QUOTAS_C2 = {"pink_sheet": 7, "gem": 43}
SOURCE_QUOTAS_C2_PILOT = {"pink_sheet": 3, "gem": 17}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _hash_order(seed: str, series_id: str) -> str:
    return sha256_bytes(f"{seed}|{series_id}".encode("utf-8"))


def _length_band(n: int) -> str:
    if n < 160:
        return "lt_160"
    if n < 240:
        return "160_239"
    if n < 360:
        return "240_359"
    return "gte_360"


def _monthly_index(label: str) -> int:
    match = __import__("re").fullmatch(r"(\d{4})-(\d{2})", str(label))
    if not match:
        raise ValueError(f"unsupported_monthly_axis_label:{label}")
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"invalid_monthly_axis_label:{label}")
    return year * 12 + month


def _missingness_features(item: dict[str, Any]) -> dict[str, Any]:
    """Classify absent calendar months and non-finite aligned values."""
    axis = [str(value) for value in item.get("axis", [])]
    values = item.get("values", [])
    if not axis:
        return {
            "missing_month_count": None,
            "missing_month_rate": None,
            "max_missing_run": None,
            "missing_value_count": None,
            "missingness_pattern": "NOT_ESTIMABLE_NO_AXIS",
        }
    if str(item.get("frequency", "")).lower() != "monthly":
        return {
            "missing_month_count": None,
            "missing_month_rate": None,
            "max_missing_run": None,
            "missing_value_count": None,
            "missingness_pattern": "NOT_ESTIMABLE_NON_MONTHLY",
        }
    indices = [_monthly_index(label) for label in axis]
    if any(right <= left for left, right in zip(indices, indices[1:])):
        raise ValueError(f"monthly_axis_not_strictly_increasing:{item.get('id')}")
    gaps = [right - left - 1 for left, right in zip(indices, indices[1:])]
    missing_months = int(sum(gaps))
    expected_months = int(indices[-1] - indices[0] + 1)
    missing_values = sum(
        1 for value in values
        if value is None or not math.isfinite(float(value))
    )
    total_missing = missing_months + int(missing_values)
    rate = total_missing / max(expected_months, 1)
    max_gap = max(gaps, default=0)
    if total_missing == 0:
        pattern = "NO_GAPS"
    elif rate < 0.05 and max_gap <= 2:
        pattern = "SPARSE_GAPS"
    elif rate < 0.15 and max_gap <= 6:
        pattern = "MODERATE_GAPS"
    else:
        pattern = "CLUSTERED_OR_HIGH_MISSINGNESS"
    return {
        "missing_month_count": missing_months,
        "missing_month_rate": float(rate),
        "max_missing_run": int(max_gap),
        "missing_value_count": int(missing_values),
        "missingness_pattern": pattern,
    }


def _ar1_feature(values: list[float], prebreak_n: int) -> dict[str, Any]:
    if prebreak_n < 40:
        return {
            "ar1_coefficient": None,
            "ar1_abs_band": "NOT_ESTIMABLE_SHORT_PREBREAK",
            "prebreak_observations": int(prebreak_n),
        }
    x = np.asarray(values[:prebreak_n], dtype=float)
    if x.ndim != 1 or x.size < 40 or not np.all(np.isfinite(x)):
        return {
            "ar1_coefficient": None,
            "ar1_abs_band": "NOT_ESTIMABLE_INVALID_INPUT",
            "prebreak_observations": int(prebreak_n),
        }
    lagged = x[:-1]
    current = x[1:]
    design = np.column_stack((np.ones(lagged.size), lagged))
    try:
        coefficients, _residuals, rank, _singular = np.linalg.lstsq(design, current, rcond=None)
    except np.linalg.LinAlgError:
        return {
            "ar1_coefficient": None,
            "ar1_abs_band": "NOT_ESTIMABLE_SINGULAR",
            "prebreak_observations": int(prebreak_n),
        }
    if rank < 2 or not np.all(np.isfinite(coefficients)):
        band = "NOT_ESTIMABLE_SINGULAR"
        rho = None
    else:
        rho = float(coefficients[1])
        magnitude = abs(rho)
        if magnitude < 0.25:
            band = "LOW"
        elif magnitude < 0.70:
            band = "MODERATE"
        else:
            band = "HIGH"
    return {
        "ar1_coefficient": rho,
        "ar1_abs_band": band,
        "prebreak_observations": int(prebreak_n),
    }


def _features(item: dict[str, Any]) -> dict[str, Any]:
    values = item["values"]
    n = len(values)
    prebreak_n = int(math.floor(0.30 * n))
    ar = _ar1_feature(values, prebreak_n)
    return {
        "series_id": str(item["id"]),
        "candidate_sha256": candidate_sha256(item),
        "source": str(item["source"]),
        "source_cohort": str(item.get("cohort", "")),
        "domain": str(item.get("domain", "")),
        "frequency": str(item.get("frequency", "")),
        "observations": int(n),
        "first_observation": str(item["axis"][0]) if item.get("axis") else None,
        "last_observation": str(item["axis"][-1]) if item.get("axis") else None,
        "length_band": _length_band(n),
        **_missingness_features(item),
        **ar,
    }


def _hamilton_quotas(group_sizes: dict[tuple[str, ...], int], total: int) -> dict[tuple[str, ...], int]:
    population = sum(group_sizes.values())
    if total < 0 or total > population:
        raise ValueError(f"invalid_stratified_quota:{total}:{population}")
    if total == 0:
        return {key: 0 for key in group_sizes}
    exact = {key: total * size / population for key, size in group_sizes.items()}
    quotas = {key: int(math.floor(value)) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    order = sorted(
        group_sizes,
        key=lambda key: (-(exact[key] - quotas[key]), key),
    )
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def _stratified_select(
    records: list[dict[str, Any]],
    *,
    total: int,
    seed: str,
    strata_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = tuple(str(record.get(field, "")) for field in strata_fields)
        groups[key].append(record)
    sizes = {key: len(items) for key, items in groups.items()}
    quotas = _hamilton_quotas(sizes, total)
    selected: list[dict[str, Any]] = []
    for key in sorted(groups):
        quota = quotas[key]
        ordered = sorted(
            groups[key],
            key=lambda row: (_hash_order(seed, row["series_id"]), row["series_id"]),
        )
        selected.extend(ordered[:quota])
    if len(selected) != total or len({row["series_id"] for row in selected}) != total:
        raise ValueError("stratified_selection_count_or_uniqueness_failed")
    return sorted(selected, key=lambda row: row["series_id"])


def _select_by_source(
    records: list[dict[str, Any]],
    quotas: dict[str, int],
    seed: str,
    strata_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for source, quota in sorted(quotas.items()):
        source_rows = [row for row in records if row["source"] == source]
        if len(source_rows) < quota:
            raise ValueError(f"source_quota_unavailable:{source}:{len(source_rows)}:{quota}")
        local = _stratified_select(
            source_rows,
            total=quota,
            seed=f"{seed}:{source}",
            strata_fields=strata_fields,
        )
        selected.extend(local)
    if len(selected) != sum(quotas.values()):
        raise ValueError("source_stratified_selection_count_failed")
    if len({row["series_id"] for row in selected}) != len(selected):
        raise ValueError("source_stratified_selection_duplicate")
    return sorted(selected, key=lambda row: row["series_id"])


def _read_g1_results(directory: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    shard_paths = sorted(directory.glob("shard-*.json"))
    if len(shard_paths) != 4:
        raise ValueError(f"expected_four_g1_eval_shards:{len(shard_paths)}")
    for path in shard_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("results", []):
            if row.get("source") != "gem":
                continue
            series_id = str(row["id"])
            if series_id in result:
                raise ValueError(f"duplicate_g1_evaluation_id:{series_id}")
            g1 = row.get("g1")
            if not isinstance(g1, dict) or g1.get("status") not in {"SCREEN_PASS", "SCREEN_FAIL"}:
                raise ValueError(f"missing_or_invalid_g1_record:{series_id}")
            result[series_id] = {
                "candidate_sha256": str(row["candidate_sha256"]),
                "g1": g1,
            }
    if len(result) != 458:
        raise ValueError(f"gem_g1_evaluation_count_mismatch:{len(result)}")
    return result


def _failure_class(g1: dict[str, Any]) -> str:
    adf_pass = bool(g1["adf_rejects_unit_root"])
    kpss_pass = bool(g1["kpss_does_not_reject_level_stationarity"])
    if adf_pass and not kpss_pass:
        return "ADF_PASS_KPSS_FAIL"
    if not adf_pass and not kpss_pass:
        return "ADF_FAIL_KPSS_FAIL"
    if not adf_pass and kpss_pass:
        return "ADF_FAIL_KPSS_PASS"
    raise ValueError("C1_member_unexpectedly_passed_G1")


def _select_c1_pilot(
    c1_rows: list[dict[str, Any]],
    failure_classes: dict[str, str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for failure_class, quota in C1_FAILURE_QUOTAS.items():
        rows = [row for row in c1_rows if failure_classes[row["series_id"]] == failure_class]
        if len(rows) < quota:
            raise ValueError(f"c1_failure_class_quota_unavailable:{failure_class}")
        local = _stratified_select(
            rows,
            total=quota,
            seed=f"{C1_SEED}:{failure_class}",
            strata_fields=("length_band", "ar1_abs_band"),
        )
        selected.extend(local)
    if len(selected) != 20 or len({row["series_id"] for row in selected}) != 20:
        raise ValueError("c1_pilot_selection_count_failed")
    return sorted(selected, key=lambda row: row["series_id"])


def _assert_manifest_selection(selection: dict[str, Any], manifest: dict[str, Any]) -> None:
    """Fail closed unless every selected identity exactly matches the committed manifest."""
    c1 = manifest["cohorts"]["C1"]
    c2 = manifest["cohorts"]["C2"]
    pilot = manifest["pilot_scope"]
    actual_c1_all = sorted(c1["series_ids"])
    actual_c2_sample = sorted(c2["series_ids"])
    actual_c1_pilot = sorted(row["series_id"] for row in selection["c1"]["pilot_series"])
    actual_c2_pilot = sorted(row["series_id"] for row in selection["c2"]["pilot_series"])
    actual_c2_all = sorted(row["series_id"] for row in selection["c2"]["sample_series"])
    actual_pilot = sorted(selection["pilot_scope"]["series_ids"])

    if len(actual_c1_all) != 147 or len(set(actual_c1_all)) != 147:
        raise ValueError("manifest_C1_identity_count_invalid")
    if len(actual_c2_sample) != 50 or len(set(actual_c2_sample)) != 50:
        raise ValueError("manifest_C2_sample_identity_count_invalid")
    if actual_c1_pilot != sorted(c1["pilot_series_ids"]):
        raise ValueError("C1_pilot_identity_set_differs_from_committed_manifest")
    if actual_c2_all != actual_c2_sample:
        raise ValueError("C2_sample_identity_set_differs_from_committed_manifest")
    if actual_c2_pilot != sorted(c2["pilot_series_ids"]):
        raise ValueError("C2_pilot_identity_set_differs_from_committed_manifest")
    if actual_pilot != sorted(pilot["series_ids"]):
        raise ValueError("40_series_pilot_identity_set_differs_from_committed_manifest")
    if len(actual_pilot) != 40 or len(set(actual_pilot)) != 40:
        raise ValueError("pilot_series_must_be_40_unique_ids")
    if set(actual_c1_pilot).intersection(actual_c2_pilot):
        raise ValueError("C1_C2_pilot_identity_overlap")
    if selection["c1"]["failure_class_pilot"] != c1["pilot_failure_class_counts"]:
        raise ValueError("C1_pilot_failure_class_counts_differ_from_manifest")
    if selection["c2"]["sample_source_counts"] != c2["sample_source_counts"]:
        raise ValueError("C2_source_counts_differ_from_manifest")
    if selection["c2"]["pilot_source_counts"] != c2["pilot_source_counts"]:
        raise ValueError("C2_pilot_source_counts_differ_from_manifest")
    if selection["pilot_scope"]["run_cases"] != pilot["run_cases"]:
        raise ValueError("pilot_run_case_count_differs_from_manifest")
    expected_ids = sorted(actual_c1_pilot + actual_c2_pilot)
    if actual_pilot != expected_ids:
        raise ValueError("pilot_union_is_not_exact_C1_C2_pilot_union")


def build_selection(
    prepared_zip: Path,
    g1_shards_dir: Path,
    cohort_manifest_path: Path,
    protocol_path: Path,
    selection_commit: str | None,
) -> dict[str, Any]:
    manifest = json.loads(cohort_manifest_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN_BEFORE_EXECUTION":
        raise ValueError("pilot_protocol_not_frozen")
    c1 = manifest["cohorts"]["C1"]
    c1_ids = list(c1["series_ids"])
    if c1.get("status") != "VERIFIED" or len(c1_ids) != 147 or len(set(c1_ids)) != 147:
        raise ValueError("C1_identity_manifest_not_verified")

    series, counts = load_p2_economic_series(prepared_zip)
    by_id = {str(item["id"]): item for item in series}
    if len(by_id) != 509:
        raise ValueError("economic_series_count_mismatch")
    missing_c1 = sorted(set(c1_ids) - set(by_id))
    if missing_c1:
        raise ValueError(f"c1_ids_missing_from_pinned_source:{len(missing_c1)}")

    g1_results = _read_g1_results(g1_shards_dir)
    gem_ids = {series_id for series_id, item in by_id.items() if item["source"] == "gem"}
    if set(g1_results) != gem_ids:
        raise ValueError("g1_eval_identity_set_mismatch")
    failure_classes: dict[str, str] = {}
    for series_id in c1_ids:
        item = by_id[series_id]
        g1_record = g1_results.get(series_id)
        if item["source"] != "gem" or g1_record is None:
            raise ValueError(f"c1_non_gem_or_g1_missing:{series_id}")
        if candidate_sha256(item) != g1_record["candidate_sha256"]:
            raise ValueError(f"c1_candidate_sha_mismatch:{series_id}")
        failure_classes[series_id] = _failure_class(g1_record["g1"])
        if g1_record["g1"].get("passed") is not False:
            raise ValueError(f"c1_g1_failure_criterion_mismatch:{series_id}")

    counts_by_class = {
        name: sum(value == name for value in failure_classes.values())
        for name in C1_FAILURE_QUOTAS
    }
    if counts_by_class != {
        "ADF_PASS_KPSS_FAIL": 106,
        "ADF_FAIL_KPSS_FAIL": 32,
        "ADF_FAIL_KPSS_PASS": 9,
    }:
        raise ValueError(f"c1_failure_class_counts_changed:{counts_by_class}")

    feature_by_id = {series_id: _features(item) for series_id, item in by_id.items()}
    c1_features = [feature_by_id[series_id] for series_id in c1_ids]
    c1_pilot = _select_c1_pilot(c1_features, failure_classes)

    c2_frame = [feature_by_id[series_id] for series_id in sorted(set(by_id) - set(c1_ids))]
    source_counts = {
        "pink_sheet": sum(row["source"] == "pink_sheet" for row in c2_frame),
        "gem": sum(row["source"] == "gem" for row in c2_frame),
    }
    if len(c2_frame) != 362 or source_counts != {"pink_sheet": 51, "gem": 311}:
        raise ValueError(f"c2_sampling_frame_mismatch:{len(c2_frame)}:{source_counts}")

    strata_fields = (
        "source", "source_cohort", "domain", "length_band",
        "ar1_abs_band", "missingness_pattern",
    )
    c2_sample = _select_by_source(c2_frame, SOURCE_QUOTAS_C2, C2_FRAME_SEED, strata_fields)
    c2_pilot = _select_by_source(c2_sample, SOURCE_QUOTAS_C2_PILOT, C2_PILOT_SEED, strata_fields)

    c1_sample_ids = [row["series_id"] for row in c1_pilot]
    c2_sample_ids = [row["series_id"] for row in c2_sample]
    c2_pilot_ids = [row["series_id"] for row in c2_pilot]
    pilot_ids = sorted(c1_sample_ids + c2_pilot_ids)
    if len(pilot_ids) != 40 or len(set(pilot_ids)) != 40:
        raise ValueError("c1_c2_pilot_union_invalid")
    if set(pilot_ids).intersection(set(c1_ids) - set(c1_sample_ids)):
        raise ValueError("c1_pilot_outside_sample")
    if set(c2_pilot_ids) - set(c2_sample_ids):
        raise ValueError("c2_pilot_not_subset_of_c2_frame")

    protocol_sha = sha256_file(protocol_path)
    prepared_sha = sha256_file(prepared_zip)
    if prepared_sha != counts["prepared_artifact_sha256"]:
        raise ValueError("prepared_artifact_sha_drift")

    def distribution(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for field in fields:
            result[field] = dict(sorted(
                collections.Counter(str(row.get(field, "NOT_RECORDED")) for row in rows).items()
            ))
        for left, right in (
            ("source", "length_band"),
            ("source", "ar1_abs_band"),
            ("source", "missingness_pattern"),
        ):
            key = f"{left}__x__{right}"
            result[key] = dict(sorted(
                collections.Counter(
                    f"{row.get(left, 'NOT_RECORDED')}|{row.get(right, 'NOT_RECORDED')}"
                    for row in rows
                ).items()
            ))
        return result

    c2_stratification_report = {
        "report_id": "C2_STRATIFICATION_REPORT_V1",
        "status": "GENERATED_FROM_PINNED_SERIES_VALUES",
        "sample_count": len(c2_sample),
        "pilot_count": len(c2_pilot),
        "dimensions": [
            "source",
            "domain",
            "length_band",
            "ar1_abs_band",
            "missingness_pattern",
        ],
        "missingness_note": (
            "Monthly calendar gaps and non-finite aligned values are assessed separately. "
            "A constant NO_GAPS stratum is reported as observed; it is not presented as "
            "evidence of variation in missingness."
        ),
        "sample_distributions": distribution(
            c2_sample,
            ("source", "domain", "length_band", "ar1_abs_band", "missingness_pattern"),
        ),
        "pilot_distributions": distribution(
            c2_pilot,
            ("source", "domain", "length_band", "ar1_abs_band", "missingness_pattern"),
        ),
        "sample_ids": [row["series_id"] for row in c2_sample],
        "pilot_ids": [row["series_id"] for row in c2_pilot],
        "pilot_is_subset_of_sample": set(row["series_id"] for row in c2_pilot).issubset(
            set(row["series_id"] for row in c2_sample)
        ),
        "selection_method": "Deterministic stratified Hamilton allocation and SHA-256 rank within source/domain/length/AR1/missingness strata.",
    }
    c1_stratification_report = {
        "report_id": "C1_FAILURE_CLASS_STRATIFICATION_V1",
        "population_counts": counts_by_class,
        "pilot_minimum_quotas": {"ADF_PASS_KPSS_FAIL": 6, "ADF_FAIL_KPSS_FAIL": 6, "ADF_FAIL_KPSS_PASS": 2},
        "pilot_counts": {
            failure_class: sum(
                failure_classes[row["series_id"]] == failure_class for row in c1_pilot
            )
            for failure_class in C1_FAILURE_QUOTAS
        },
        "minimum_quotas_satisfied": all(
            sum(failure_classes[row["series_id"]] == failure_class for row in c1_pilot)
            >= minimum
            for failure_class, minimum in {
                "ADF_PASS_KPSS_FAIL": 6,
                "ADF_FAIL_KPSS_FAIL": 6,
                "ADF_FAIL_KPSS_PASS": 2,
            }.items()
        ),
        "pilot_length_distribution": dict(sorted(collections.Counter(
            row["length_band"] for row in c1_pilot
        ).items())),
        "pilot_ar1_distribution": dict(sorted(collections.Counter(
            row["ar1_abs_band"] for row in c1_pilot
        ).items())),
    }

    selection = {
        "schema_version": "chaos-p1-4-cohort-selection-v1.2",
        "C1_STRATIFICATION_REPORT": c1_stratification_report,
        "C2_STRATIFICATION_REPORT": c2_stratification_report,
        "selection_commit": selection_commit,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol_sha,
        "source_identity": {
            "p2_2_commit": counts["source_commit"],
            "prepared_artifact_sha256": prepared_sha,
            "candidate_registry_sha256": manifest["created_from"]["candidate_registry_sha256"],
            "economic_series": counts["series"],
            "pink_sheet_series": counts["pink_sheet"],
            "gem_series": counts["gem"],
        },
        "c1": {
            "verified_population_count": 147,
            "pilot_sample_count": 20,
            "pilot_seed": C1_SEED,
            "failure_class_population": counts_by_class,
            "failure_class_pilot": {
                failure_class: sum(
                    failure_classes[row["series_id"]] == failure_class
                    for row in c1_pilot
                )
                for failure_class in C1_FAILURE_QUOTAS
            },
            "pilot_series": c1_pilot,
        },
        "c2": {
            "verified_sampling_frame_count": len(c2_frame),
            "sampling_frame_source_counts": source_counts,
            "sample_count": 50,
            "sample_seed": C2_FRAME_SEED,
            "pilot_sample_count": 20,
            "pilot_seed": C2_PILOT_SEED,
            "sample_source_counts": {
                source: sum(row["source"] == source for row in c2_sample)
                for source in SOURCE_QUOTAS_C2
            },
            "pilot_source_counts": {
                source: sum(row["source"] == source for row in c2_pilot)
                for source in SOURCE_QUOTAS_C2_PILOT
            },
            "stratification_dimensions": list(strata_fields),
            "sample_series": c2_sample,
            "pilot_series": c2_pilot,
        },
        "c3": {
            "status": "PENDING_EXTERNAL_EVIDENCE",
            "pilot_sample_count": 0,
            "reason": "Historical source vintages available at event-time are not established by the current P2.2 snapshot.",
        },
        "pilot_scope": {
            "series_count": 40,
            "series_ids": pilot_ids,
            "cases_per_series": 19,
            "run_cases": 760,
            "C3_included": False,
            "raw_values_persisted": False,
        },
        "replay_command": (
            "python scripts/p1_4/build_cohort_selection.py "
            "--prepared-zip /tmp/p2-prepared.zip "
            "--g1-shards-dir /tmp/p2-g1-shards "
            "--cohort-manifest p1_4_validation/cohort_manifest.json "
            "--pilot-protocol p1_4_validation/pilot_protocol.json "
            "--output artifacts/p1_4/cohort_selection.json"
        ),
    }
    _assert_manifest_selection(selection, manifest)
    return selection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-zip", required=True, type=Path)
    parser.add_argument("--g1-shards-dir", required=True, type=Path)
    parser.add_argument("--cohort-manifest", required=True, type=Path)
    parser.add_argument("--pilot-protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selection-commit", default=None)
    parser.add_argument(
        "--stratification-report",
        type=Path,
        default=Path("artifacts/p1_4/cohort_stratification_report.json"),
    )
    args = parser.parse_args()

    selection = build_selection(
        args.prepared_zip,
        args.g1_shards_dir,
        args.cohort_manifest,
        args.pilot_protocol,
        selection_commit=args.selection_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(selection))
    report = {
        "schema_version": "chaos-p1-4-stratification-report-v1",
        "C1": selection["C1_STRATIFICATION_REPORT"],
        "C2": selection["C2_STRATIFICATION_REPORT"],
        "source_identity": selection["source_identity"],
        "protocol_sha256": selection["protocol_sha256"],
    }
    args.stratification_report.parent.mkdir(parents=True, exist_ok=True)
    args.stratification_report.write_bytes(canonical_json_bytes(report))
    print(json.dumps({
        "status": "PASS",
        "c1_pilot_count": selection["c1"]["pilot_sample_count"],
        "c2_sample_count": selection["c2"]["sample_count"],
        "c2_pilot_count": selection["c2"]["pilot_sample_count"],
        "pilot_series_count": selection["pilot_scope"]["series_count"],
        "pilot_run_cases": selection["pilot_scope"]["run_cases"],
        "output": str(args.output),
        "sha256": sha256_file(args.output),
        "stratification_report": str(args.stratification_report),
        "stratification_report_sha256": sha256_file(args.stratification_report),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
