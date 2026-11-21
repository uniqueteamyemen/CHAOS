"""Source-neutral, retrospective behavioural candidate discovery for CHAOS.

This layer describes candidate anomalies and within-series structural changes.
It does not infer causality, produce forecasts, or assign inferential p-values.
Every candidate is explicitly unvalidated until a source-appropriate null and
independent/held-out evidence are available.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from chaos_governance_kernel.core import sha256_file, utc_now, validate_manifest, write_json
from observation_foundation.record_identity_v1 import prepare_source_record


CONTRACT_ID = "CHAOS_BEHAVIORAL_DISCOVERY_V1"
SERIES_PROFILE_FILE = "SERIES_BEHAVIOR_PROFILES_V1.csv"
CANDIDATE_FILE = "BEHAVIORAL_CANDIDATES_V1.jsonl"
SHARED_PATTERN_FILE = "SHARED_YEAR_PATTERNS_V1.csv"
SUMMARY_FILE = "BEHAVIORAL_DISCOVERY_SUMMARY_V1.json"
MANIFEST_FILE = "BEHAVIORAL_DISCOVERY_MANIFEST_V1.json"
VALIDATION_FILE = "BEHAVIORAL_DISCOVERY_VALIDATION_V1.json"

CONTRACT_FIELDS = {
    "contract_id", "status", "scope", "minimum_segment_observations",
    "point_reference_observations_each_side", "point_anomaly_threshold",
    "level_shift_effect_threshold", "slope_shift_effect_threshold",
    "shared_year_minimum_entities", "shared_year_direction_concordance",
    "candidate_status", "inference_policy", "input",
}
REQUIRED_CONTRACT_FIELDS = CONTRACT_FIELDS


class BehavioralDiscoveryError(ValueError):
    """Input or contract cannot be processed without guessing."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _series_id(source_namespace: str, dataset_id: str, entity_id: str, metric_id: str) -> str:
    payload = {
        "contract": "chaos-series-identity-v1",
        "source_namespace": source_namespace,
        "dataset_id": dataset_id,
        "entity_id": entity_id,
        "metric_id": metric_id,
        "native_frequency": "annual",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "series:v1:sha256:" + hashlib.sha256(encoded).hexdigest()


def _mad(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    center = median(values)
    return float(median([abs(value - center) for value in values]))


def _robust_scale(values: Sequence[float]) -> float:
    return 1.4826 * _mad(values)


def _theil_sen_slope(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        raise BehavioralDiscoveryError("theil_sen_requires_matching_series_with_two_points")
    slopes = [
        (y[j] - y[i]) / (x[j] - x[i])
        for i in range(len(x) - 1)
        for j in range(i + 1, len(x))
        if x[j] != x[i]
    ]
    if not slopes:
        raise BehavioralDiscoveryError("theil_sen_no_valid_pairwise_slopes")
    return float(median(slopes))


def _pearson_lag1(values: Sequence[float]) -> float | None:
    if len(values) < 3:
        return None
    left, right = list(values[:-1]), list(values[1:])
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 1e-24 or right_ss <= 1e-24:
        return None
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    return float(covariance / math.sqrt(left_ss * right_ss))


def _effect(
    left: Sequence[float], right: Sequence[float]
) -> tuple[float | None, str, float, float, float]:
    left_median, right_median = float(median(left)), float(median(right))
    delta = right_median - left_median
    scale_left, scale_right = _robust_scale(left), _robust_scale(right)
    pooled_scale = math.sqrt((scale_left * scale_left + scale_right * scale_right) / 2.0)
    if pooled_scale <= 1e-12:
        if abs(delta) <= 1e-12:
            return None, "DEGENERATE_NO_DIFFERENCE", delta, left_median, right_median
        return None, "ZERO_WITHIN_SEGMENT_VARIABILITY", delta, left_median, right_median
    return abs(delta) / pooled_scale, "ROBUST_STANDARDIZED_MEDIAN_SHIFT", delta, left_median, right_median


def _fit_robust_line(years: Sequence[int], values: Sequence[float]) -> tuple[float, float, list[float]]:
    x = [float(year - years[0]) for year in years]
    slope = _theil_sen_slope(x, values)
    intercept = float(median([value - slope * point for value, point in zip(values, x)]))
    residuals = [value - (intercept + slope * point) for value, point in zip(values, x)]
    return slope, intercept, residuals


def _candidate_base(series: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_namespace": series["source_namespace"],
        "dataset_id": series["dataset_id"],
        "domain": series["domain"],
        "entity_id": series["entity_id"],
        "entity_name": series["entity_name"],
        "metric_id": series["metric_id"],
        "metric_name": series["metric_name"],
        "unit": series["unit"],
        "native_frequency": "annual",
        "series_id": series["series_id"],
        "source_record_identity_contract": "source-record-identity-v1",
        "candidate_status": "DISCOVERY_CANDIDATE_UNVALIDATED",
        "causal_claim": False,
        "forecast_generated": False,
        "inferential_p_value": None,
    }


def analyze_series(
    series: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Produce one profile and zero or more retrospective candidates."""
    years = list(series["years"])
    values = list(series["values"])
    identities = list(series["identities"])
    if len(years) != len(values) or len(years) != len(identities):
        raise BehavioralDiscoveryError("series_year_value_identity_count_mismatch")
    if len(years) < 2 or any(years[i] >= years[i + 1] for i in range(len(years) - 1)):
        raise BehavioralDiscoveryError("series_years_must_be_strictly_increasing")
    if any(not math.isfinite(value) for value in values):
        raise BehavioralDiscoveryError("series_non_finite_numeric_value")
    if len(set(years)) != len(years):
        raise BehavioralDiscoveryError("series_duplicate_year")
    minimum_segment = int(contract["minimum_segment_observations"])
    if len(years) < 2 * minimum_segment:
        raise BehavioralDiscoveryError(
            f"series_too_short_for_declared_segment_support:min_length={2 * minimum_segment}"
        )

    slope, intercept, residuals = _fit_robust_line(years, values)
    differences = [values[i] - values[i - 1] for i in range(1, len(values))]
    residual_scale = _robust_scale(residuals)
    diff_scale = _robust_scale(differences)
    profile = {
        "series_id": series["series_id"],
        "source_namespace": series["source_namespace"],
        "dataset_id": series["dataset_id"],
        "domain": series["domain"],
        "entity_id": series["entity_id"],
        "entity_name": series["entity_name"],
        "metric_id": series["metric_id"],
        "metric_name": series["metric_name"],
        "unit": series["unit"] or "",
        "native_frequency": "annual",
        "observation_count": len(values),
        "observation_start": years[0],
        "observation_end": years[-1],
        "raw_min": min(values),
        "raw_median": float(median(values)),
        "raw_max": max(values),
        "raw_mad": _mad(values),
        "global_theil_sen_slope_per_year": slope,
        "robust_detrended_residual_mad": _mad(residuals),
        "first_difference_mad": _mad(differences),
        "lag1_pearson": _pearson_lag1(values),
        "constant_series": max(values) - min(values) <= 1e-12,
        "available_at_known_count": sum(
            identity.get("available_at") is not None for identity in identities
        ),
        "available_at_unknown_count": sum(
            identity.get("available_at") is None for identity in identities
        ),
        "point_in_time_eligible": all(
            identity.get("available_at") is not None for identity in identities
        ),
    }

    candidates: list[dict[str, Any]] = []
    n = len(values)

    # Retrospective level shift scan on robust detrended residuals.
    best_level: tuple[tuple[int, float, int], dict[str, Any]] | None = None
    if n >= 2 * minimum_segment:
        for split in range(minimum_segment, n - minimum_segment + 1):
            score, score_kind, delta, left_median, right_median = _effect(
                residuals[:split], residuals[split:]
            )
            qualifies = (
                score_kind == "ZERO_WITHIN_SEGMENT_VARIABILITY"
                or (
                    score is not None
                    and score >= float(contract["level_shift_effect_threshold"])
                )
            )
            if not qualifies:
                continue
            internal_rank = (
                1 if score_kind == "ZERO_WITHIN_SEGMENT_VARIABILITY" else 0,
                score if score is not None else 0.0,
                -years[split],
            )
            event = {
                **_candidate_base(series),
                "candidate_type": "level_shift",
                "candidate_year": years[split],
                "split_index": split,
                "left_segment_start": years[0],
                "left_segment_end": years[split - 1],
                "right_segment_start": years[split],
                "right_segment_end": years[-1],
                "left_detrended_median": left_median,
                "right_detrended_median": right_median,
                "direction": "UP" if delta > 0 else "DOWN",
                "effect_size": score,
                "effect_size_kind": score_kind,
                "selection": "maximum_robust_detrended_median_shift_over_all_eligible_splits",
                "anchor_logical_record_id": identities[split]["logical_record_id"],
                "anchor_canonical_record_id": identities[split]["canonical_record_id"],
            }
            if best_level is None or internal_rank > best_level[0]:
                best_level = (internal_rank, event)
    if best_level is not None:
        candidates.append(best_level[1])

    # Retrospective slope-change scan. This is a separate signature from level shift.
    best_slope: tuple[tuple[int, float, int], dict[str, Any]] | None = None
    if n >= 2 * minimum_segment:
        x_all = [float(year - years[0]) for year in years]
        for split in range(minimum_segment, n - minimum_segment + 1):
            left_slope = _theil_sen_slope(x_all[:split], values[:split])
            right_slope = _theil_sen_slope(x_all[split:], values[split:])
            delta_slope = right_slope - left_slope
            if abs(delta_slope) <= 1e-12:
                continue
            if diff_scale <= 1e-12:
                score = None
                score_kind = "ZERO_FIRST_DIFFERENCE_VARIABILITY"
                qualifies = True
                zero_scale = 1
            else:
                score = abs(delta_slope) / diff_scale
                score_kind = "SLOPE_DELTA_OVER_ROBUST_DIFFERENCE_SCALE"
                qualifies = score >= float(contract["slope_shift_effect_threshold"])
                zero_scale = 0
            if not qualifies:
                continue
            internal_rank = (zero_scale, score if score is not None else 0.0, -years[split])
            event = {
                **_candidate_base(series),
                "candidate_type": "slope_change",
                "candidate_year": years[split],
                "split_index": split,
                "left_segment_start": years[0],
                "left_segment_end": years[split - 1],
                "right_segment_start": years[split],
                "right_segment_end": years[-1],
                "left_theil_sen_slope_per_year": left_slope,
                "right_theil_sen_slope_per_year": right_slope,
                "slope_delta_per_year": delta_slope,
                "direction": "ACCELERATING" if delta_slope > 0 else "DECELERATING",
                "effect_size": score,
                "effect_size_kind": score_kind,
                "selection": "maximum_absolute_piecewise_theil_sen_slope_delta_over_all_eligible_splits",
                "anchor_logical_record_id": identities[split]["logical_record_id"],
                "anchor_canonical_record_id": identities[split]["canonical_record_id"],
            }
            if best_slope is None or internal_rank > best_slope[0]:
                best_slope = (internal_rank, event)
    if best_slope is not None:
        candidates.append(best_slope[1])

    # Isolated point anomaly scan on detrended residuals using symmetric local context.
    neighbour_count = int(contract["point_reference_observations_each_side"])
    best_point: tuple[tuple[int, float, int], dict[str, Any]] | None = None
    if n >= 2 * neighbour_count + 1:
        for index in range(neighbour_count, n - neighbour_count):
            reference = (
                residuals[index - neighbour_count:index]
                + residuals[index + 1:index + neighbour_count + 1]
            )
            baseline = float(median(reference))
            local_scale = _robust_scale(reference)
            delta = residuals[index] - baseline
            if local_scale <= 1e-12:
                if abs(delta) <= 1e-12:
                    continue
                score = None
                score_kind = "ZERO_LOCAL_REFERENCE_VARIABILITY"
                zero_scale = 1
                qualifies = True
            else:
                score = abs(delta) / local_scale
                score_kind = "ABSOLUTE_DETRENDED_RESIDUAL_OVER_LOCAL_ROBUST_SCALE"
                zero_scale = 0
                qualifies = score >= float(contract["point_anomaly_threshold"])
            if not qualifies:
                continue
            internal_rank = (zero_scale, score if score is not None else 0.0, -years[index])
            event = {
                **_candidate_base(series),
                "candidate_type": "isolated_point_anomaly",
                "candidate_year": years[index],
                "observed_value": values[index],
                "detrended_residual": residuals[index],
                "local_reference_median": baseline,
                "direction": "ABOVE_LOCAL_REFERENCE" if delta > 0 else "BELOW_LOCAL_REFERENCE",
                "effect_size": score,
                "effect_size_kind": score_kind,
                "reference_years": (
                    years[index - neighbour_count:index]
                    + years[index + 1:index + neighbour_count + 1]
                ),
                "anchor_logical_record_id": identities[index]["logical_record_id"],
                "anchor_canonical_record_id": identities[index]["canonical_record_id"],
            }
            if best_point is None or internal_rank > best_point[0]:
                best_point = (internal_rank, event)
    if best_point is not None:
        candidates.append(best_point[1])

    profile["candidate_count"] = len(candidates)
    profile["candidate_types"] = ",".join(sorted(item["candidate_type"] for item in candidates))
    return profile, candidates


def load_metric_provenance(path: Path) -> dict[str, dict[str, Any]]:
    required = {"dataset_id", "source", "variable_id", "unit", "selected_variable_id"}
    result: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise BehavioralDiscoveryError("selected_variable_provenance_columns_missing")
        for row in reader:
            metric_id = (row.get("selected_variable_id") or "").strip()
            if not metric_id:
                continue
            if metric_id in result:
                raise BehavioralDiscoveryError(f"duplicate_metric_provenance:{metric_id}")
            source = (row.get("source") or "").strip()
            dataset_id = (row.get("dataset_id") or "").strip()
            if not source or not dataset_id:
                raise BehavioralDiscoveryError(f"metric_provenance_source_missing:{metric_id}")
            source_namespace = (
                "world_bank_wdi" if source == "World Bank WDI"
                else "imf_weo" if source == "IMF WEO"
                else "eia" if source == "EIA"
                else ""
            )
            if not source_namespace:
                raise BehavioralDiscoveryError(f"source_namespace_unmapped:{source}")
            result[metric_id] = {
                "source_namespace": source_namespace,
                "dataset_id": dataset_id,
                "source": source,
                "variable_id": (row.get("variable_id") or "").strip(),
                "metric_name": (row.get("variable_name") or "").strip(),
                "unit": (row.get("unit") or "").strip() or None,
                "domain": "energy" if source == "EIA" else "economic",
            }
    return result


def _load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise BehavioralDiscoveryError("behavioral_discovery_contract_must_be_object")
    missing = sorted(REQUIRED_CONTRACT_FIELDS - set(contract))
    unknown = sorted(set(contract) - CONTRACT_FIELDS)
    if missing or unknown:
        raise BehavioralDiscoveryError(
            f"behavioral_discovery_contract_fields_invalid:missing={missing}:unknown={unknown}"
        )
    if contract["contract_id"] != CONTRACT_ID:
        raise BehavioralDiscoveryError("behavioral_discovery_contract_id_mismatch")
    return contract


def _load_panel(
    panel_path: Path,
    provenance_path: Path,
    input_summary_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provenance = load_metric_provenance(provenance_path)
    source_summary = json.loads(input_summary_path.read_text(encoding="utf-8"))
    expected_entities = int(source_summary["entities"])
    expected_rows = int(source_summary["rows"])
    expected_year_start, expected_year_end = [int(x) for x in source_summary["years"]]
    expected_metrics = int(source_summary["variables"])

    series_values: dict[tuple[str, str], dict[str, Any]] = {}
    entity_names: dict[str, tuple[str, str]] = {}
    seen_entity_year: set[tuple[str, int]] = set()
    row_count = 0
    with panel_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"entity_code", "year", "wdi_entity_name", "imf_entity_name"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise BehavioralDiscoveryError("panel_required_columns_missing")
        metric_columns = [
            column for column in reader.fieldnames
            if column not in required
        ]
        if set(metric_columns) != set(provenance):
            raise BehavioralDiscoveryError(
                "panel_metric_provenance_mismatch:"
                f"panel_only={sorted(set(metric_columns)-set(provenance))}:"
                f"provenance_only={sorted(set(provenance)-set(metric_columns))}"
            )
        if len(metric_columns) != expected_metrics:
            raise BehavioralDiscoveryError("panel_metric_count_mismatch")
        for row_number, row in enumerate(reader, 2):
            row_count += 1
            entity_id = (row.get("entity_code") or "").strip()
            if not entity_id:
                raise BehavioralDiscoveryError(f"panel_entity_missing:line={row_number}")
            try:
                year = int(row.get("year") or "")
            except ValueError as exc:
                raise BehavioralDiscoveryError(f"panel_year_invalid:line={row_number}") from exc
            if not expected_year_start <= year <= expected_year_end:
                raise BehavioralDiscoveryError(f"panel_year_out_of_declared_range:line={row_number}")
            entity_year = (entity_id, year)
            if entity_year in seen_entity_year:
                raise BehavioralDiscoveryError(f"panel_duplicate_entity_year:{entity_id}:{year}")
            seen_entity_year.add(entity_year)
            labels = (
                (row.get("wdi_entity_name") or "").strip(),
                (row.get("imf_entity_name") or "").strip(),
            )
            previous_labels = entity_names.get(entity_id)
            if previous_labels is not None and previous_labels != labels:
                raise BehavioralDiscoveryError(f"panel_entity_name_changed:{entity_id}")
            entity_names[entity_id] = labels

            for metric_id in metric_columns:
                raw = row.get(metric_id)
                if raw is None or raw.strip() == "":
                    raise BehavioralDiscoveryError(
                        f"panel_missing_value:line={row_number}:metric={metric_id}"
                    )
                try:
                    decimal_value = Decimal(raw.strip())
                    value = float(decimal_value)
                except (InvalidOperation, ValueError, OverflowError) as exc:
                    raise BehavioralDiscoveryError(
                        f"panel_non_numeric_value:line={row_number}:metric={metric_id}"
                    ) from exc
                if not decimal_value.is_finite() or not math.isfinite(value):
                    raise BehavioralDiscoveryError(
                        f"panel_non_finite_value:line={row_number}:metric={metric_id}"
                    )
                meta = provenance[metric_id]
                key = (entity_id, metric_id)
                if key not in series_values:
                    series_values[key] = {
                        "entity_id": entity_id,
                        "entity_name": labels[0] or labels[1] or entity_id,
                        "metric_id": metric_id,
                        "years": [],
                        "values": [],
                        "raw_values": [],
                        "identities": [],
                        **meta,
                    }
                series = series_values[key]
                observation = prepare_source_record({
                    "source_namespace": meta["source_namespace"],
                    "dataset_id": meta["dataset_id"],
                    "series_semantics": "periodic_measurement",
                    "entity_id": entity_id,
                    "metric_id": metric_id,
                    "event_time": str(year),
                    "available_at": None,
                    "source_record_id": None,
                    "source_revision": None,
                    "revision_status": None,
                    "value": decimal_value,
                    "unit": meta["unit"],
                    "observation_status": "observed",
                })
                series["years"].append(year)
                series["values"].append(value)
                series["raw_values"].append(raw)
                series["identities"].append({
                    "logical_record_id": observation["logical_record_id"],
                    "canonical_record_id": observation["canonical_record_id"],
                    "available_at": observation["available_at"],
                })

    expected_years = list(range(expected_year_start, expected_year_end + 1))
    expected_entity_years = expected_entities * len(expected_years)
    if row_count != expected_rows:
        raise BehavioralDiscoveryError(f"panel_row_count_mismatch:{expected_rows}:{row_count}")
    if len(entity_names) != expected_entities:
        raise BehavioralDiscoveryError(
            f"panel_entity_count_mismatch:{expected_entities}:{len(entity_names)}"
        )
    if len(seen_entity_year) != expected_entity_years:
        raise BehavioralDiscoveryError("panel_entity_year_coverage_mismatch")
    series_list: list[dict[str, Any]] = []
    for (entity_id, metric_id), series in sorted(series_values.items()):
        if series["years"] != expected_years:
            raise BehavioralDiscoveryError(
                f"panel_series_not_complete_or_ordered:{entity_id}:{metric_id}"
            )
        series["series_id"] = _series_id(
            series["source_namespace"], series["dataset_id"], entity_id, metric_id
        )
        series_list.append(series)
    return series_list, {
        "entity_count": len(entity_names),
        "row_count": row_count,
        "metric_count": len(metric_columns),
        "series_count": len(series_list),
        "expected_years": expected_years,
        "observation_count": sum(len(item["years"]) for item in series_list),
    }


def build_shared_year_patterns(
    candidates: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for item in candidates:
        if item["candidate_type"] in {"level_shift", "slope_change"}:
            groups[(item["metric_id"], item["candidate_type"], int(item["candidate_year"]))].append(item)

    output: list[dict[str, Any]] = []
    for (metric_id, candidate_type, year), items in sorted(groups.items()):
        entities = {str(item["entity_id"]) for item in items}
        up = sum(
            item["direction"] in {"UP", "ACCELERATING"} for item in items
        )
        down = sum(
            item["direction"] in {"DOWN", "DECELERATING"} for item in items
        )
        total = len(entities)
        concordance = max(up, down) / total if total else 0.0
        if (
            total >= int(contract["shared_year_minimum_entities"])
            and concordance >= float(contract["shared_year_direction_concordance"])
        ):
            output.append({
                "pattern_type": "shared_metric_change_year",
                "metric_id": metric_id,
                "candidate_type": candidate_type,
                "year": year,
                "entity_support": total,
                "up_or_accelerating_count": up,
                "down_or_decelerating_count": down,
                "direction_concordance": concordance,
                "status": "DISCOVERY_CANDIDATE_UNVALIDATED",
                "causal_claim": False,
                "inferential_p_value": None,
            })
    return output


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def run_behavioral_discovery(
    *,
    panel_path: Path,
    provenance_path: Path,
    input_summary_path: Path,
    contract_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    contract = _load_contract(contract_path)
    series_list, input_counts = _load_panel(panel_path, provenance_path, input_summary_path)
    profiles: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for series in series_list:
        profile, found = analyze_series(series, contract)
        profiles.append(profile)
        candidates.extend(found)

    candidates.sort(key=lambda item: (
        item["metric_id"], item["entity_id"], int(item["candidate_year"]), item["candidate_type"]
    ))
    shared = build_shared_year_patterns(candidates, contract)
    candidate_counts = Counter(item["candidate_type"] for item in candidates)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_fields = list(profiles[0].keys()) if profiles else []
    _write_csv(output_dir / SERIES_PROFILE_FILE, profiles, profile_fields)
    with (output_dir / CANDIDATE_FILE).open("w", encoding="utf-8", newline="\n") as stream:
        for item in candidates:
            stream.write(json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ) + "\n")
    shared_fields = [
        "pattern_type", "metric_id", "candidate_type", "year", "entity_support",
        "up_or_accelerating_count", "down_or_decelerating_count",
        "direction_concordance", "status", "causal_claim", "inferential_p_value",
    ]
    _write_csv(output_dir / SHARED_PATTERN_FILE, shared, shared_fields)

    summary = {
        "contract_id": contract["contract_id"],
        "status": "CANDIDATE_GENERATION_ONLY",
        "generated_at_utc": utc_now(),
        "input": {
            "panel": panel_path.as_posix(),
            "panel_sha256": sha256_file(panel_path),
            "provenance": provenance_path.as_posix(),
            "provenance_sha256": sha256_file(provenance_path),
            "input_summary": input_summary_path.as_posix(),
            "input_summary_sha256": sha256_file(input_summary_path),
            **input_counts,
        },
        "outputs": {
            "series_profiles": SERIES_PROFILE_FILE,
            "candidate_events": CANDIDATE_FILE,
            "shared_year_patterns": SHARED_PATTERN_FILE,
        },
        "series_profile_count": len(profiles),
        "candidate_count": len(candidates),
        "candidate_counts_by_type": dict(sorted(candidate_counts.items())),
        "shared_year_pattern_count": len(shared),
        "source_observation_identity": {
            "contract": "source-record-identity-v1",
            "records": input_counts["observation_count"],
            "unique_logical_slots": input_counts["observation_count"],
            "available_at_known": 0,
            "available_at_unknown": input_counts["observation_count"],
            "revision_metadata_available": 0,
            "point_in_time_eligible": False,
        },
        "method": {
            "trend": "Theil-Sen line; median residual intercept",
            "level_shift": "maximum median shift on robust detrended residuals over eligible splits",
            "slope_shift": "maximum piecewise Theil-Sen slope delta",
            "point_anomaly": "symmetric local reference on detrended residuals",
            "maximum_candidates_per_series": 3,
        },
        "inference": {
            "null_tests_performed": False,
            "p_values_computed": False,
            "candidate_status": "DISCOVERY_CANDIDATE_UNVALIDATED",
            "causal_claims_permitted": False,
            "forecasting_performed": False,
            "detector_math_modified": False,
        },
    }
    write_json(output_dir / SUMMARY_FILE, summary)

    artifact_paths = [SERIES_PROFILE_FILE, CANDIDATE_FILE, SHARED_PATTERN_FILE, SUMMARY_FILE]
    manifest = {
        "bundle_id": "CHAOS_BEHAVIORAL_DISCOVERY_V1",
        "contract_id": contract["contract_id"],
        "generated_at_utc": summary["generated_at_utc"],
        "source_commit": None,
        "artifacts": [
            {
                "path": (output_dir / name).resolve().relative_to(Path.cwd().resolve()).as_posix(),
                "role": name.removesuffix(".csv").removesuffix(".jsonl").removesuffix(".json").lower(),
                "sha256": sha256_file(output_dir / name),
                "bytes": (output_dir / name).stat().st_size,
            }
            for name in artifact_paths
        ],
        "inputs": {
            "panel_sha256": summary["input"]["panel_sha256"],
            "provenance_sha256": summary["input"]["provenance_sha256"],
            "contract_sha256": sha256_file(contract_path),
        },
        "decision": {
            "status": "CANDIDATES_REQUIRE_SOURCE_SPECIFIC_NULL_AND_INDEPENDENT_REVIEW",
            "summary": "Descriptive candidate generation only; no inferential admission or forecast.",
        },
    }
    write_json(output_dir / MANIFEST_FILE, manifest)
    validation = validate_manifest(output_dir / MANIFEST_FILE, Path.cwd())
    write_json(output_dir / VALIDATION_FILE, validation)
    if validation["status"] != "pass":
        raise RuntimeError(f"behavioral_discovery_artifact_validation_failed:{validation['failures']}")
    return summary


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[1]
    run_behavioral_discovery(
        panel_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv",
        provenance_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/SELECTED_VARIABLE_PROVENANCE.csv",
        input_summary_path=ROOT / "catalog_first/readiness_gate/macro_plus_eia_energy/NUMERIC_COMPLETE_MATRIX_V1_1_SUMMARY.json",
        contract_path=ROOT / "experimental_contracts/BEHAVIORAL_DISCOVERY_CONTRACT_V1.json",
        output_dir=ROOT / "discovery/behavioral_v1",
    )
