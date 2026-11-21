"""Conditional calendar-coincidence null for discovered candidate events.

This test conditions on the candidates already emitted by the behavioural
scanner. It preserves each candidate, metric, entity, direction, trend-state
signature, and split-support class while independently reassigning its year
within the years permitted by its native local-reference/split support.

It tests cross-entity calendar synchrony only. It is NOT a detector false-alarm
rate, a null for the existence of within-series anomalies, a causal test, or
an independent validation of a source.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from chaos_governance_kernel.core import sha256_file, validate_manifest, write_json


NULL_SUMMARY_FILE = "CONDITIONAL_CALENDAR_NULL_V1.json"
NULL_GROUPS_FILE = "CONDITIONAL_CALENDAR_GROUPS_V1.csv"
NULL_CONTRACT_ID = "CHAOS_CONDITIONAL_CALENDAR_COINCIDENCE_NULL_V1"


class CalendarNullError(ValueError):
    """Raised when the candidate set or conditional null contract is invalid."""


def _support_class(item: Mapping[str, Any]) -> str:
    candidate_type = item.get("candidate_type")
    if candidate_type == "isolated_point_anomaly":
        return "SYMMETRIC_LOCAL_REFERENCE"
    value = item.get("support_position")
    if value not in {"INTERIOR", "MINIMUM_SEGMENT_EDGE"}:
        raise CalendarNullError(f"candidate_split_support_class_invalid:{value}")
    return str(value)


def _signature(item: Mapping[str, Any]) -> tuple[str, ...]:
    candidate_type = str(item["candidate_type"])
    if candidate_type == "isolated_point_anomaly":
        direction = str(item["direction"])
        if direction not in {"ABOVE_LOCAL_REFERENCE", "BELOW_LOCAL_REFERENCE"}:
            raise CalendarNullError("point_anomaly_direction_invalid")
        pre_state = "NOT_APPLICABLE"
        post_state = "NOT_APPLICABLE"
    elif candidate_type == "level_shift":
        direction = str(item["direction"])
        if direction not in {"UP", "DOWN"}:
            raise CalendarNullError("level_shift_direction_invalid")
        pre_state = "NOT_APPLICABLE"
        post_state = "NOT_APPLICABLE"
    elif candidate_type == "slope_change":
        direction = str(item["direction"])
        if direction not in {"SLOPE_INCREASE", "SLOPE_DECREASE"}:
            raise CalendarNullError("slope_change_direction_invalid")
        pre_state = str(item.get("pre_change_trend_direction", "UNSPECIFIED"))
        post_state = str(item.get("post_change_trend_direction", "UNSPECIFIED"))
        if pre_state not in {"INCREASING", "DECREASING", "FLAT"}:
            raise CalendarNullError("pre_change_trend_direction_invalid")
        if post_state not in {"INCREASING", "DECREASING", "FLAT"}:
            raise CalendarNullError("post_change_trend_direction_invalid")
    else:
        raise CalendarNullError(f"candidate_type_invalid:{candidate_type}")

    return (
        str(item["metric_id"]),
        candidate_type,
        direction,
        pre_state,
        post_state,
        _support_class(item),
    )


def _eligible_years(
    item: Mapping[str, Any],
    *,
    start_year: int,
    end_year: int,
    minimum_segment_observations: int,
    point_reference_each_side: int,
) -> list[int]:
    candidate_type = str(item["candidate_type"])
    if candidate_type == "isolated_point_anomaly":
        years = list(range(
            start_year + point_reference_each_side,
            end_year - point_reference_each_side + 1,
        ))
    elif candidate_type in {"level_shift", "slope_change"}:
        if _support_class(item) == "MINIMUM_SEGMENT_EDGE":
            years = [
                start_year + minimum_segment_observations,
                end_year - minimum_segment_observations + 1,
            ]
        else:
            years = list(range(
                start_year + minimum_segment_observations + 1,
                end_year - minimum_segment_observations + 1,
            ))
    else:
        raise CalendarNullError(f"candidate_type_invalid:{candidate_type}")

    observed_year = item.get("candidate_year")
    if isinstance(observed_year, bool) or not isinstance(observed_year, int):
        raise CalendarNullError("candidate_year_invalid")
    if observed_year not in years:
        raise CalendarNullError(
            f"candidate_year_outside_conditional_support:{observed_year}"
        )
    return years


def _count_groups(
    candidates: Sequence[Mapping[str, Any]],
    years: Sequence[int] | None = None,
    *,
    eligibility: Sequence[Sequence[int]] | None = None,
    rng: random.Random | None = None,
) -> Counter[tuple[str, ...]]:
    counts: Counter[tuple[str, ...]] = Counter()
    for index, item in enumerate(candidates):
        signature = _signature(item)
        year = (
            int(item["candidate_year"])
            if years is None
            else int(years[index])
        )
        key = (*signature, str(year))
        counts[key] += 1
    return counts


def run_conditional_calendar_null(
    *,
    candidates: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Run a max-statistic conditional calendar-year reassignment null."""
    required = {
        "contract_id", "replicates", "seed",
        "minimum_segment_observations", "point_reference_observations_each_side",
        "minimum_entity_support", "input_year_range",
    }
    allowed = required | {"conditioning_policy", "test_family", "inference_limits"}
    missing = sorted(required - set(contract))
    unknown = sorted(set(contract) - allowed)
    if missing or unknown:
        raise CalendarNullError(
            f"calendar_null_contract_fields_invalid:missing={missing}:unknown={unknown}"
        )
    if contract["contract_id"] != NULL_CONTRACT_ID:
        raise CalendarNullError("calendar_null_contract_id_mismatch")
    replicates = contract["replicates"]
    seed = contract["seed"]
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1000:
        raise CalendarNullError("calendar_null_replicates_must_be_integer_gte_1000")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise CalendarNullError("calendar_null_seed_must_be_integer")
    minimum_segment = contract["minimum_segment_observations"]
    point_reference = contract["point_reference_observations_each_side"]
    minimum_support = contract["minimum_entity_support"]
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
           for v in (minimum_segment, point_reference, minimum_support)):
        raise CalendarNullError("calendar_null_integer_settings_invalid")
    year_range = contract["input_year_range"]
    if (
        not isinstance(year_range, list) or len(year_range) != 2
        or any(isinstance(v, bool) or not isinstance(v, int) for v in year_range)
        or year_range[0] >= year_range[1]
    ):
        raise CalendarNullError("calendar_null_input_year_range_invalid")
    start_year, end_year = year_range

    prepared: list[dict[str, Any]] = []
    seen_series_candidates: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            raise CalendarNullError(f"candidate_must_be_object:index={index}")
        for field in ("series_id", "entity_id", "metric_id", "candidate_type", "candidate_year", "direction"):
            if field not in raw:
                raise CalendarNullError(f"candidate_field_missing:index={index}:{field}")
        series_key = (
            str(raw["series_id"]),
            str(raw["candidate_type"]),
            str(raw["metric_id"]),
        )
        if series_key in seen_series_candidates:
            raise CalendarNullError(f"duplicate_candidate_per_series_type:{series_key}")
        seen_series_candidates.add(series_key)
        choices = _eligible_years(
            raw,
            start_year=start_year,
            end_year=end_year,
            minimum_segment_observations=minimum_segment,
            point_reference_each_side=point_reference,
        )
        prepared.append({
            "item": dict(raw),
            "eligible_years": choices,
            "signature": _signature(raw),
            "observed_year": int(raw["candidate_year"]),
        })

    if not prepared:
        raise CalendarNullError("candidate_set_empty")

    items = [entry["item"] for entry in prepared]
    observed_counts: Counter[tuple[str, ...]] = Counter()
    entity_sets: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for entry in prepared:
        item = entry["item"]
        key = (*entry["signature"], str(entry["observed_year"]))
        entity = str(item["entity_id"])
        if entity in entity_sets[key]:
            raise CalendarNullError(f"duplicate_entity_in_observed_candidate_group:{key}:{entity}")
        entity_sets[key].add(entity)
        observed_counts[key] += 1

    observed_max = max(observed_counts.values())
    observed_groups = [
        key for key, count in observed_counts.items()
        if count >= minimum_support
    ]
    if not observed_groups:
        raise CalendarNullError("no_candidate_group_meets_minimum_entity_support")

    rng = random.Random(seed)
    unadjusted_ge: Counter[tuple[str, ...]] = Counter()
    max_adjusted_ge: Counter[tuple[str, ...]] = Counter()
    null_maxima: list[int] = []
    replicate_count_for_global_max = 0

    for _ in range(replicates):
        simulated: Counter[tuple[str, ...]] = Counter()
        for entry in prepared:
            item = entry["item"]
            simulated_year = rng.choice(entry["eligible_years"])
            key = (*entry["signature"], str(simulated_year))
            simulated[key] += 1
        maximum = max(simulated.values(), default=0)
        null_maxima.append(maximum)
        if maximum >= observed_max:
            replicate_count_for_global_max += 1
        for key in observed_groups:
            if simulated.get(key, 0) >= observed_counts[key]:
                unadjusted_ge[key] += 1
            if maximum >= observed_counts[key]:
                max_adjusted_ge[key] += 1

    null_maxima_sorted = sorted(null_maxima)
    q95 = null_maxima_sorted[max(0, math.ceil(0.95 * replicates) - 1)]
    null_mean = sum(null_maxima) / replicates
    global_p = (replicate_count_for_global_max + 1) / (replicates + 1)

    group_rows: list[dict[str, Any]] = []
    for key in sorted(observed_groups):
        metric_id, candidate_type, direction, pre_state, post_state, support_class, year = key
        support = observed_counts[key]
        group_rows.append({
            "metric_id": metric_id,
            "candidate_type": candidate_type,
            "candidate_year": int(year),
            "direction": direction,
            "pre_change_trend_direction": pre_state,
            "post_change_trend_direction": post_state,
            "support_class": support_class,
            "entity_support": support,
            "conditional_unadjusted_p": (unadjusted_ge[key] + 1) / (replicates + 1),
            "conditional_familywise_maxT_p": (max_adjusted_ge[key] + 1) / (replicates + 1),
        })

    return {
        "contract_id": contract["contract_id"],
        "status": "CONDITIONAL_CALENDAR_COINCIDENCE_DIAGNOSTIC_ONLY",
        "method": "Independently reassign each discovered candidate year within its admissible year set while preserving metric, entity, candidate type, direction, pre/post trend state, and support class; compare maximum same-signature entity support across the entire searched family.",
        "replicates": replicates,
        "seed": seed,
        "candidate_count_conditioned_on": len(prepared),
        "observed_group_count": len(observed_counts),
        "groups_meeting_minimum_support": len(observed_groups),
        "observed_global_max_support": observed_max,
        "null_global_max_mean": null_mean,
        "null_global_max_q95": q95,
        "global_max_conditional_p": global_p,
        "null_max_ge_observed_count": replicate_count_for_global_max,
        "eligible_year_support": {
            "point_anomaly": [start_year + point_reference, end_year - point_reference],
            "split_interior": [
                start_year + minimum_segment + 1,
                end_year - minimum_segment,
            ],
            "split_boundary": [
                start_year + minimum_segment,
                end_year - minimum_segment + 1,
            ],
        },
        "interpretation_limits": [
            "This null conditions on the candidates already emitted; it does not test whether a within-series anomaly exists.",
            "It is not a detector false-alarm rate, FDR estimate, causal test, or forecast validation.",
            "The exchangeability assumption concerns calendar timing conditional on candidate existence and admissible support; nonstationary source revisions or systematic time-varying coverage can violate it.",
            "P-values are diagnostic rankings only; they do not promote candidates to validated patterns.",
        ],
        "causal_claims_permitted": False,
        "forecasting_performed": False,
        "null_is_detector_fpr": False,
        "groups": group_rows,
    }


def write_calendar_null_artifacts(
    *,
    candidates_path: Path,
    contract_path: Path,
    output_dir: Path,
    repository_root: Path,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    with candidates_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CalendarNullError(f"candidate_jsonl_invalid:line={line_number}") from exc
            candidates.append(candidate)

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    result = run_conditional_calendar_null(candidates=candidates, contract=contract)
    result["input"] = {
        "candidate_file": candidates_path.resolve().relative_to(repository_root.resolve()).as_posix(),
        "candidate_sha256": sha256_file(candidates_path),
        "contract_file": contract_path.resolve().relative_to(repository_root.resolve()).as_posix(),
        "contract_sha256": sha256_file(contract_path),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / NULL_SUMMARY_FILE
    write_json(summary_path, result)

    groups_path = output_dir / NULL_GROUPS_FILE
    fieldnames = [
        "metric_id", "candidate_type", "candidate_year", "direction",
        "pre_change_trend_direction", "post_change_trend_direction",
        "support_class", "entity_support", "conditional_unadjusted_p",
        "conditional_familywise_maxT_p",
    ]
    with groups_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result["groups"])

    manifest_path = output_dir / "BEHAVIORAL_DISCOVERY_MANIFEST_V1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing_paths = {item["path"] for item in manifest["artifacts"]}
    for path, role in (
        (summary_path, "conditional_calendar_null_summary_v1"),
        (groups_path, "conditional_calendar_null_groups_v1"),
    ):
        relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
        if relative in existing_paths:
            raise CalendarNullError(f"duplicate_manifest_artifact:{relative}")
        manifest["artifacts"].append({
            "path": relative,
            "role": role,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    write_json(manifest_path, manifest)

    validation = validate_manifest(manifest_path, repository_root)
    write_json(output_dir / "BEHAVIORAL_DISCOVERY_VALIDATION_V1.json", validation)
    if validation["status"] != "pass":
        raise RuntimeError(f"calendar_null_artifact_validation_failed:{validation['failures']}")
    return result
