from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


class DiscoveryInputError(ValueError):
    """Raised when source records cannot be aligned without guessing."""


def _finite_float(value: str, *, context: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DiscoveryInputError(f"non_numeric_source_value:{context}") from exc
    if not math.isfinite(number):
        raise DiscoveryInputError(f"non_finite_source_value:{context}")
    return number


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiscoveryInputError(f"json_object_required:{path}")
    return value


def load_active_annual_series(
    *,
    macro_panel_path: Path,
    macro_summary_path: Path,
    macro_provenance_path: Path,
    macro_manifest_path: Path,
    trade_csv_path: Path,
    trade_extract_summary_path: Path,
    trade_adapter_run_path: Path,
    trade_metadata_path: Path,
) -> tuple[dict[str, dict[str, dict[int, float]]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Load the active Macro-EIA and WDI Trade observations without filling or averaging."""
    macro_summary = _read_json(macro_summary_path)
    macro_manifest = _read_json(macro_manifest_path)
    trade_summary = _read_json(trade_extract_summary_path)
    trade_adapter = _read_json(trade_adapter_run_path)

    macro_hash = _sha256(macro_panel_path)
    declared_macro_hash = (macro_manifest.get("inputs") or {}).get("panel_sha256")
    if not declared_macro_hash or macro_hash != declared_macro_hash:
        raise DiscoveryInputError(
            f"macro_panel_sha256_mismatch:expected={declared_macro_hash}:actual={macro_hash}"
        )
    macro_provenance_hash = _sha256(macro_provenance_path)
    provenance_by_metric: dict[str, dict[str, str]] = {}
    with macro_provenance_path.open("r", encoding="utf-8-sig", newline="") as stream:
        provenance_reader = csv.DictReader(stream)
        required_provenance = {"selected_variable_id", "dataset_id", "source", "variable_id", "unit"}
        if not required_provenance.issubset(set(provenance_reader.fieldnames or [])):
            raise DiscoveryInputError("macro_provenance_required_columns_missing")
        for provenance_row in provenance_reader:
            selected_id = (provenance_row.get("selected_variable_id") or "").strip()
            if selected_id:
                if selected_id in provenance_by_metric:
                    raise DiscoveryInputError(f"macro_provenance_duplicate_metric:{selected_id}")
                provenance_by_metric[selected_id] = {
                    "dataset_id": (provenance_row.get("dataset_id") or "").strip(),
                    "source": (provenance_row.get("source") or "").strip(),
                    "source_metric_id": (provenance_row.get("variable_id") or "").strip(),
                    "unit": (provenance_row.get("unit") or "").strip(),
                }

    trade_hash = _sha256(trade_csv_path)
    declared_trade_hash = trade_adapter.get("input_sha256")
    if not declared_trade_hash or trade_hash != declared_trade_hash:
        raise DiscoveryInputError(
            f"wdi_trade_sha256_mismatch:expected={declared_trade_hash}:actual={trade_hash}"
        )

    series: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    metric_meta: dict[str, dict[str, Any]] = {}
    macro_rows = 0
    macro_entities: set[str] = set()
    macro_years: set[int] = set()
    macro_slots: set[tuple[str, int]] = set()
    macro_metrics: list[str] = []

    with macro_panel_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        required = {"entity_code", "year"}
        if not required.issubset(fields):
            raise DiscoveryInputError("macro_panel_identity_columns_missing")
        macro_metrics = [
            name for name in fields
            if name.startswith(("wdi__", "imf__", "eia__"))
        ]
        if not macro_metrics:
            raise DiscoveryInputError("macro_panel_numeric_metric_columns_missing")
        if len(macro_metrics) != len(set(macro_metrics)):
            raise DiscoveryInputError("macro_panel_duplicate_metric_columns")
        if set(macro_metrics) != set(provenance_by_metric):
            raise DiscoveryInputError(
                "macro_provenance_metric_set_mismatch:"
                f"missing={sorted(set(macro_metrics) - set(provenance_by_metric))}:"
                f"unexpected={sorted(set(provenance_by_metric) - set(macro_metrics))}"
            )
        for metric in macro_metrics:
            provenance = provenance_by_metric[metric]
            if not provenance["dataset_id"] or not provenance["source_metric_id"]:
                raise DiscoveryInputError(f"macro_provenance_identity_incomplete:{metric}")
            source_namespace = (
                "world_bank_wdi" if metric.startswith("wdi__")
                else "imf_weo" if metric.startswith("imf__")
                else "eia"
            )
            metric_meta[f"macro_eia::{metric}"] = {
                "source_namespace": source_namespace,
                "dataset_id": provenance["dataset_id"],
                "source": provenance["source"],
                "source_metric_id": provenance["source_metric_id"],
                "unit": provenance["unit"] or None,
            }
        for line_number, row in enumerate(reader, 2):
            entity = (row.get("entity_code") or "").strip()
            year_text = (row.get("year") or "").strip()
            if not entity:
                raise DiscoveryInputError(f"macro_entity_empty:line={line_number}")
            try:
                year = int(year_text)
            except ValueError as exc:
                raise DiscoveryInputError(
                    f"macro_year_invalid:line={line_number}:value={year_text}"
                ) from exc
            slot = (entity, year)
            if slot in macro_slots:
                raise DiscoveryInputError(f"macro_duplicate_entity_year:{entity}:{year}")
            macro_slots.add(slot)
            macro_entities.add(entity)
            macro_years.add(year)
            macro_rows += 1
            for column in macro_metrics:
                value = _finite_float(
                    row.get(column), context=f"macro:{entity}:{year}:{column}"
                )
                series[f"macro_eia::{column}"][entity][year] = value

    expected_macro_rows = macro_summary.get("rows")
    if isinstance(expected_macro_rows, int) and macro_rows != expected_macro_rows:
        raise DiscoveryInputError(
            f"macro_row_count_mismatch:expected={expected_macro_rows}:actual={macro_rows}"
        )
    expected_macro_entities = macro_summary.get("entities")
    if isinstance(expected_macro_entities, int) and len(macro_entities) != expected_macro_entities:
        raise DiscoveryInputError(
            "macro_entity_count_mismatch:"
            f"expected={expected_macro_entities}:actual={len(macro_entities)}"
        )
    expected_macro_metrics = macro_summary.get("variables")
    if isinstance(expected_macro_metrics, int) and len(macro_metrics) != expected_macro_metrics:
        raise DiscoveryInputError(
            "macro_metric_count_mismatch:"
            f"expected={expected_macro_metrics}:actual={len(macro_metrics)}"
        )
    if macro_summary.get("missing_cells") != 0:
        raise DiscoveryInputError("macro_panel_declared_missing_cells_nonzero")

    trade_metadata: dict[str, dict[str, str]] = {}
    with trade_metadata_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "Series Code" not in reader.fieldnames:
            raise DiscoveryInputError("wdi_trade_metadata_series_code_missing")
        for row in reader:
            code = (row.get("Series Code") or "").strip()
            if code:
                if code in trade_metadata:
                    raise DiscoveryInputError(f"wdi_trade_duplicate_metadata:{code}")
                trade_metadata[code] = {
                    "indicator_name": (row.get("Indicator Name") or "").strip(),
                    "unit": (row.get("Unit of measure") or "").strip(),
                }

    trade_rows = 0
    trade_entities: set[str] = set()
    trade_years: set[int] = set()
    trade_indicators: set[str] = set()
    trade_slots: set[tuple[str, str, int]] = set()
    expected_trade_years = set(trade_summary.get("years") or [])
    expected_trade_indicators = set(trade_summary.get("indicator_codes") or [])

    with trade_csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "Country Name", "Country Code", "Indicator Name",
            "Indicator Code", "year", "value_raw",
        }
        if not required.issubset(set(reader.fieldnames or [])):
            raise DiscoveryInputError("wdi_trade_required_columns_missing")
        for line_number, row in enumerate(reader, 2):
            entity = (row.get("Country Code") or "").strip()
            indicator = (row.get("Indicator Code") or "").strip()
            year_text = (row.get("year") or "").strip()
            if not entity or not indicator:
                raise DiscoveryInputError(f"wdi_trade_identity_empty:line={line_number}")
            if indicator not in trade_metadata:
                raise DiscoveryInputError(f"wdi_trade_metadata_missing:{indicator}")
            if (row.get("Indicator Name") or "").strip() != trade_metadata[indicator]["indicator_name"]:
                raise DiscoveryInputError(f"wdi_trade_indicator_name_mismatch:{indicator}")
            try:
                year = int(year_text)
            except ValueError as exc:
                raise DiscoveryInputError(
                    f"wdi_trade_year_invalid:line={line_number}:value={year_text}"
                ) from exc
            if expected_trade_years and year not in expected_trade_years:
                raise DiscoveryInputError(f"wdi_trade_year_outside_extract:{year}")
            key = (entity, indicator, year)
            if key in trade_slots:
                raise DiscoveryInputError(
                    f"wdi_trade_duplicate_entity_indicator_year:{entity}:{indicator}:{year}"
                )
            trade_slots.add(key)
            value = _finite_float(
                row.get("value_raw"), context=f"wdi_trade:{entity}:{indicator}:{year}"
            )
            metric = f"wdi_trade::{indicator}"
            series[metric][entity][year] = value
            metric_meta[metric] = {
                "source_namespace": "world_bank_wdi_trade",
                "dataset_id": "wdi_country_annual_indicators_2000_2024",
                "source_metric_id": indicator,
                "indicator_name": trade_metadata[indicator]["indicator_name"],
                "unit": trade_metadata[indicator]["unit"] or None,
            }
            trade_entities.add(entity)
            trade_years.add(year)
            trade_indicators.add(indicator)
            trade_rows += 1

    expected_trade_rows = trade_summary.get("observed_rows")
    if isinstance(expected_trade_rows, int) and trade_rows != expected_trade_rows:
        raise DiscoveryInputError(
            f"wdi_trade_row_count_mismatch:expected={expected_trade_rows}:actual={trade_rows}"
        )
    expected_trade_entities = trade_summary.get("entities")
    if isinstance(expected_trade_entities, int) and len(trade_entities) != expected_trade_entities:
        raise DiscoveryInputError(
            "wdi_trade_entity_count_mismatch:"
            f"expected={expected_trade_entities}:actual={len(trade_entities)}"
        )
    if expected_trade_indicators and trade_indicators != expected_trade_indicators:
        raise DiscoveryInputError(
            "wdi_trade_indicator_set_mismatch:"
            f"missing={sorted(expected_trade_indicators - trade_indicators)}:"
            f"unexpected={sorted(trade_indicators - expected_trade_indicators)}"
        )
    if expected_trade_years and trade_years != expected_trade_years:
        raise DiscoveryInputError(
            "wdi_trade_year_set_mismatch:"
            f"missing={sorted(expected_trade_years - trade_years)}:"
            f"unexpected={sorted(trade_years - expected_trade_years)}"
        )

    expected_years = set(range(2000, 2025))
    if macro_years != expected_years:
        raise DiscoveryInputError(
            f"macro_year_support_mismatch:missing={sorted(expected_years - macro_years)}:"
            f"unexpected={sorted(macro_years - expected_years)}"
        )
    if expected_trade_years and expected_trade_years != expected_years:
        raise DiscoveryInputError("wdi_trade_declared_year_support_not_2000_2024")

    all_metrics = sorted(series)
    if set(all_metrics) != set(metric_meta):
        raise DiscoveryInputError("metric_metadata_and_series_registry_mismatch")

    report = {
        "macro_eia": {
            "rows": macro_rows,
            "entities": len(macro_entities),
            "metrics": len(macro_metrics),
            "years": sorted(macro_years),
            "sha256": macro_hash,
            "provenance_sha256": macro_provenance_hash,
            "behavioral_manifest_sha256": _sha256(macro_manifest_path),
        },
        "wdi_trade": {
            "rows": trade_rows,
            "entities": len(trade_entities),
            "metrics": len(trade_indicators),
            "years": sorted(trade_years),
            "sha256": trade_hash,
        },
        "exact_entity_code_intersection": len(macro_entities & trade_entities),
        "exact_entity_code_overlap": sorted(macro_entities & trade_entities),
        "metric_count_total": len(all_metrics),
        "series_count_total": sum(len(series[metric]) for metric in all_metrics),
        "native_frequency": "annual",
        "missing_values_filled": False,
        "frequency_conversion": False,
        "source_averaging": False,
        "available_at_known": False,
        "point_in_time_eligible": False,
    }
    return {key: {entity: dict(values) for entity, values in entities.items()}
            for key, entities in series.items()}, metric_meta, report


def _median_absolute_deviation(values: Sequence[float]) -> float:
    center = median(values)
    return median([abs(value - center) for value in values])


def _robust_scale(values: Sequence[float]) -> float:
    """Robust Qn/MAD/IQR envelope for short annual-change samples.

    Qn is the first quartile of pairwise absolute differences (with the
    asymptotic consistency factor); MAD and IQR protect against discrete
    ties/degeneracy. A single isolated extreme has limited influence.
    """
    if len(values) < 2:
        return 0.0
    distances = sorted(
        abs(values[right] - values[left])
        for left in range(len(values) - 1)
        for right in range(left + 1, len(values))
    )
    h = len(values) // 2 + 1
    qn_index = max(0, min(len(distances) - 1, math.comb(h, 2) - 1))
    qn_scale = 2.2219 * distances[qn_index] if distances else 0.0
    center = median(values)
    mad_scale = 1.4826 * median([abs(value - center) for value in values])
    q25 = _quantile(values, 0.25)
    q75 = _quantile(values, 0.75)
    iqr_scale = ((q75 - q25) / 1.349) if q25 is not None and q75 is not None else 0.0
    return max(qn_scale, mad_scale, iqr_scale)


def _pearson(x_values: Sequence[float], y_values: Sequence[float]) -> float | None:
    if len(x_values) != len(y_values) or len(x_values) < 3:
        return None
    x_center = sum(x_values) / len(x_values)
    y_center = sum(y_values) / len(y_values)
    x_dev = [value - x_center for value in x_values]
    y_dev = [value - y_center for value in y_values]
    x_ss = sum(value * value for value in x_dev)
    y_ss = sum(value * value for value in y_dev)
    if x_ss <= 1e-24 or y_ss <= 1e-24:
        return None
    covariance = sum(a * b for a, b in zip(x_dev, y_dev))
    return max(-1.0, min(1.0, covariance / math.sqrt(x_ss * y_ss)))


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)


def _metric_change_mode(metadata: Mapping[str, Any] | None) -> str:
    """Choose a source-semantic transform; never infer log changes for rates."""
    metadata = metadata or {}
    metric_id = str(metadata.get("source_metric_id") or "")
    unit = str(metadata.get("unit") or "").strip().lower()
    name = str(metadata.get("indicator_name") or "").strip().lower()

    rate_codes = {
        "FP.CPI.TOTL.ZG", "NY.GDP.MKTP.KD.ZG", "NGDP_RPCH", "BCA_NGDPD",
        "NE.TRD.GNFS.ZS", "NE.EXP.GNFS.ZS", "NE.IMP.GNFS.ZS",
    }
    if metric_id in rate_codes or unit in {"%", "percent", "percentage"} or "percent" in unit:
        return "ABSOLUTE_DIFFERENCE"
    if metric_id in {"NY.GDP.PCAP.KD", "PA.NUS.PPP", "SP.POP.TOTL", "PCPI", "PPPEX",
                     "energy_consumption_per_capita", "energy_consumption_per_gdp",
                     "TX.VAL.MRCH.CD.WT", "TM.VAL.MRCH.CD.WT"}:
        return "LOG_DIFFERENCE"
    if "index" in unit or "constant 2015 us$" in unit or "current us$" in unit:
        return "LOG_DIFFERENCE"
    if "btu" in unit or "per person" in unit or "per international dollar" in unit:
        return "LOG_DIFFERENCE"
    if "price index" in name or "population" in name or "conversion factor" in name:
        return "LOG_DIFFERENCE"
    return "ABSOLUTE_DIFFERENCE"


def _first_differences(
    series: Mapping[str, Mapping[int, float]],
    *,
    change_mode: str = "ABSOLUTE_DIFFERENCE",
    return_excluded: bool = False,
) -> dict[str, dict[int, float]] | tuple[dict[str, dict[int, float]], list[str]]:
    if change_mode not in {"ABSOLUTE_DIFFERENCE", "LOG_DIFFERENCE"}:
        raise ValueError(f"unsupported_change_mode:{change_mode}")
    result: dict[str, dict[int, float]] = {}
    excluded_nonpositive: list[str] = []
    for entity, observations in series.items():
        years = sorted(observations)
        if change_mode == "LOG_DIFFERENCE" and any(observations[year] <= 0 for year in years):
            # Do not silently switch to absolute changes: the source-defined
            # transform is not valid for this entity's observed level series.
            result[entity] = {}
            excluded_nonpositive.append(entity)
            continue
        changes: dict[int, float] = {}
        for previous, current in zip(years, years[1:]):
            if current != previous + 1:
                continue
            left, right = observations[previous], observations[current]
            change = (math.log(right) - math.log(left)) if change_mode == "LOG_DIFFERENCE" else (right - left)
            if not math.isfinite(change):
                raise DiscoveryInputError(f"non_finite_transformed_change:{entity}:{current}")
            changes[current] = change
        result[entity] = changes
    if return_excluded:
        return result, excluded_nonpositive
    return result


def _year_effect_adjust(
    changes: Mapping[str, Mapping[int, float]],
) -> dict[str, dict[int, float]]:
    by_year: dict[int, list[float]] = defaultdict(list)
    for observations in changes.values():
        for year, value in observations.items():
            by_year[year].append(value)
    year_medians = {year: median(values) for year, values in by_year.items()}
    return {
        entity: {year: value - year_medians[year] for year, value in observations.items()}
        for entity, observations in changes.items()
    }


def _measure_pair(
    source: Mapping[str, Mapping[int, float]],
    target: Mapping[str, Mapping[int, float]],
    *,
    lag: int,
    min_pairs_per_entity: int,
    year_window: tuple[int, int] | None = None,
) -> dict[str, Any]:
    entity_correlations: list[float] = []
    entity_pair_counts: list[int] = []
    total_pairs = 0
    all_years: set[int] = set()
    entities_with_overlap = 0

    for entity in sorted(set(source) & set(target)):
        source_values = source[entity]
        target_values = target[entity]
        x_values: list[float] = []
        y_values: list[float] = []
        for source_year in sorted(source_values):
            target_year = source_year + lag
            if year_window is not None:
                start, end = year_window
                if source_year < start or source_year > end or target_year < start or target_year > end:
                    continue
            if target_year not in target_values:
                continue
            x_values.append(source_values[source_year])
            y_values.append(target_values[target_year])
            all_years.add(source_year)
        if x_values:
            entities_with_overlap += 1
        if len(x_values) < min_pairs_per_entity:
            continue
        correlation = _pearson(x_values, y_values)
        if correlation is None:
            continue
        entity_correlations.append(correlation)
        entity_pair_counts.append(len(x_values))
        total_pairs += len(x_values)

    if not entity_correlations:
        return {
            "supporting_entity_count": 0,
            "entities_with_any_overlap": entities_with_overlap,
            "paired_observation_count": 0,
            "median_pairs_per_entity": None,
            "median_entity_correlation": None,
            "q25_entity_correlation": None,
            "q75_entity_correlation": None,
            "direction_concordance": None,
            "source_year_start": min(all_years) if all_years else None,
            "source_year_end": max(all_years) if all_years else None,
        }

    center = float(median(entity_correlations))
    concordance = (
        sum(value >= 0 for value in entity_correlations) / len(entity_correlations)
        if center >= 0 else
        sum(value <= 0 for value in entity_correlations) / len(entity_correlations)
    )
    return {
        "supporting_entity_count": len(entity_correlations),
        "entities_with_any_overlap": entities_with_overlap,
        "paired_observation_count": total_pairs,
        "median_pairs_per_entity": float(median(entity_pair_counts)),
        "median_entity_correlation": center,
        "q25_entity_correlation": _quantile(entity_correlations, 0.25),
        "q75_entity_correlation": _quantile(entity_correlations, 0.75),
        "direction_concordance": concordance,
        "source_year_start": min(all_years) if all_years else None,
        "source_year_end": max(all_years) if all_years else None,
    }


def discover_cross_series_relationships(
    series: Mapping[str, Mapping[str, Mapping[int, float]]],
    *,
    metric_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    minimum_entities: int = 20,
    minimum_pairs_per_entity: int = 8,
    minimum_median_abs_correlation: float = 0.35,
    minimum_direction_concordance: float = 0.65,
    maximum_lag_years: int = 3,
    early_window: tuple[int, int] = (2001, 2012),
    late_window: tuple[int, int] = (2013, 2024),
    temporal_minimum_entities: int = 15,
    temporal_minimum_pairs_per_entity: int = 6,
) -> list[dict[str, Any]]:
    """Search pairwise relationships in exact annual first differences.

    A positive lag means source change at year t is paired with target change
    at t + lag. All results are retrospective, descriptive candidates only.
    """
    if minimum_entities < 2 or minimum_pairs_per_entity < 3 or maximum_lag_years < 0:
        raise ValueError("relationship_contract_minima_invalid")
    metrics = sorted(series)
    if len(metrics) < 2:
        return []

    metric_metadata = metric_metadata or {}
    change_modes = {
        metric: _metric_change_mode(metric_metadata.get(metric))
        for metric in metrics
    }
    differences: dict[str, dict[str, dict[int, float]]] = {}
    excluded_nonpositive: dict[str, list[str]] = {}
    for metric in metrics:
        metric_differences, excluded = _first_differences(
            series[metric], change_mode=change_modes[metric], return_excluded=True
        )
        differences[metric] = metric_differences
        excluded_nonpositive[metric] = excluded
    year_adjusted = {
        metric: _year_effect_adjust(differences[metric])
        for metric in metrics
    }
    result: list[dict[str, Any]] = []

    comparisons: list[tuple[str, str, int, str]] = []
    for index, metric_a in enumerate(metrics):
        for metric_b in metrics[index + 1:]:
            comparisons.append((metric_a, metric_b, 0, "CONTEMPORANEOUS_UNDIRECTED"))
            for lag in range(1, maximum_lag_years + 1):
                comparisons.append((metric_a, metric_b, lag, "SOURCE_LEADS_TARGET"))
                comparisons.append((metric_b, metric_a, lag, "SOURCE_LEADS_TARGET"))

    for source_metric, target_metric, lag, relation_kind in comparisons:
        for adjustment, store in (
            ("ENTITY_DEMEANED", differences),
            ("ENTITY_AND_YEAR_EFFECT_ADJUSTED", year_adjusted),
        ):
            full = _measure_pair(
                store[source_metric], store[target_metric],
                lag=lag, min_pairs_per_entity=minimum_pairs_per_entity,
            )
            early = _measure_pair(
                store[source_metric], store[target_metric],
                lag=lag, min_pairs_per_entity=temporal_minimum_pairs_per_entity,
                year_window=early_window,
            )
            late = _measure_pair(
                store[source_metric], store[target_metric],
                lag=lag, min_pairs_per_entity=temporal_minimum_pairs_per_entity,
                year_window=late_window,
            )
            median_corr = full["median_entity_correlation"]
            concordance = full["direction_concordance"]
            passes_screen = (
                full["supporting_entity_count"] >= minimum_entities
                and median_corr is not None
                and abs(median_corr) >= minimum_median_abs_correlation
                and concordance is not None
                and concordance >= minimum_direction_concordance
            )
            early_corr = early["median_entity_correlation"]
            late_corr = late["median_entity_correlation"]
            early_ok = early["supporting_entity_count"] >= temporal_minimum_entities
            late_ok = late["supporting_entity_count"] >= temporal_minimum_entities
            if not early_ok or not late_ok or early_corr is None or late_corr is None:
                stability = "NOT_TESTABLE_IN_BOTH_TIME_WINDOWS"
            elif early_corr == 0 or late_corr == 0:
                stability = "NO_DIRECTION_IN_ONE_TIME_WINDOW"
            elif (early_corr > 0) == (late_corr > 0):
                stability = "SAME_SIGN_ACROSS_TIME_WINDOWS"
            else:
                stability = "SIGN_REVERSAL_ACROSS_TIME_WINDOWS"

            record = {
                "record_type": "relationship_scan",
                "source_metric": source_metric,
                "target_metric": target_metric,
                "relation_kind": relation_kind,
                "lag_years": lag,
                "analysis_mode": adjustment,
                "source_change_transform": change_modes[source_metric],
                "target_change_transform": change_modes[target_metric],
                "source_nonpositive_transform_excluded_entities": excluded_nonpositive[source_metric],
                "target_nonpositive_transform_excluded_entities": excluded_nonpositive[target_metric],
                "lag_semantics": (
                    "source_change_at_t_paired_with_target_change_at_t_plus_lag"
                    if lag else "same_year_first_difference_association"
                ),
                **full,
                "candidate_screen_passed": bool(passes_screen),
                "candidate_status": (
                    "DISCOVERY_CANDIDATE_UNVALIDATED" if passes_screen
                    else "REJECTED_BY_DESCRIPTIVE_SCREEN"
                ),
                "early_window": {
                    "years": list(early_window),
                    **early,
                },
                "late_window": {
                    "years": list(late_window),
                    **late,
                },
                "temporal_stability": stability,
                "candidate_thresholds": {
                    "minimum_entities": minimum_entities,
                    "minimum_pairs_per_entity": minimum_pairs_per_entity,
                    "minimum_abs_median_entity_correlation": minimum_median_abs_correlation,
                    "minimum_direction_concordance": minimum_direction_concordance,
                },
                "inferential_p_value": None,
                "null_test_performed": False,
                "causal_claim": False,
                "forecast_generated": False,
                "point_in_time_eligible": False,
            }
            result.append(record)

    return result


def _volatility_split(
    values: Sequence[float],
    *,
    minimum_segment_changes: int,
) -> dict[str, Any] | None:
    if len(values) < 2 * minimum_segment_changes:
        return None
    best: tuple[tuple[int, float, int], int, dict[str, Any]] | None = None
    epsilon = 1e-12
    for split in range(minimum_segment_changes, len(values) - minimum_segment_changes + 1):
        left = values[:split]
        right = values[split:]
        left_scale = _robust_scale(left)
        right_scale = _robust_scale(right)
        left_variance = left_scale * left_scale
        right_variance = right_scale * right_scale

        if left_variance <= epsilon and right_variance <= epsilon:
            factor = 1.0
            ratio: float | None = 1.0
            ratio_kind = "FINITE"
            direction = "NO_CHANGE"
        elif left_variance <= epsilon:
            factor = math.inf
            ratio = None
            ratio_kind = "EMERGED_FROM_ZERO_BASELINE"
            direction = "VOLATILITY_EXPANSION"
        elif right_variance <= epsilon:
            factor = math.inf
            ratio = 0.0
            ratio_kind = "COLLAPSED_TO_ZERO"
            direction = "VOLATILITY_CONTRACTION"
        else:
            ratio = right_variance / left_variance
            factor = max(ratio, 1.0 / ratio)
            ratio_kind = "FINITE"
            direction = (
                "VOLATILITY_EXPANSION" if ratio > 1
                else "VOLATILITY_CONTRACTION" if ratio < 1
                else "NO_CHANGE"
            )
        candidate = {
            "split_index": split,
            "left_change_count": len(left),
            "right_change_count": len(right),
            "left_robust_scale": left_scale,
            "right_robust_scale": right_scale,
            "left_robust_variance_proxy": left_variance,
            "right_robust_variance_proxy": right_variance,
            "variance_ratio_post_over_pre": ratio,
            "variance_ratio_kind": ratio_kind,
            "variance_change_factor": None if math.isinf(factor) else factor,
            "direction": direction,
        }
        # For zero-baseline transitions the ratio is unbounded at every
        # split that leaves a zero-dispersion side. Rank by the non-zero
        # side's dispersion so the selected boundary is not arbitrarily
        # pinned to the minimum-segment edge.
        if ratio_kind == "EMERGED_FROM_ZERO_BASELINE":
            rank = (1, right_variance, -split)
        elif ratio_kind == "COLLAPSED_TO_ZERO":
            rank = (1, left_variance, -split)
        else:
            rank = (0, factor, -split)
        if best is None or rank > best[0]:
            best = (rank, split, candidate)

    if best is None:
        return None
    return best[2]


def scan_variance_shifts(
    series: Mapping[str, Mapping[str, Mapping[int, float]]],
    *,
    metric_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    minimum_segment_changes: int = 8,
    minimum_variance_change_factor: float = 3.0,
) -> list[dict[str, Any]]:
    """Detect retrospective shifts in robust variance of exact annual changes."""
    if minimum_segment_changes < 3 or minimum_variance_change_factor <= 1:
        raise ValueError("volatility_contract_minima_invalid")
    rows: list[dict[str, Any]] = []
    metric_metadata = metric_metadata or {}
    for metric in sorted(series):
        change_mode = _metric_change_mode(metric_metadata.get(metric))
        transformed, excluded_nonpositive = _first_differences(
            series[metric], change_mode=change_mode, return_excluded=True
        )
        for entity in sorted(series[metric]):
            observations = series[metric][entity]
            years = sorted(observations)
            if entity in excluded_nonpositive:
                rows.append({
                    "record_type": "variance_shift_scan",
                    "metric": metric,
                    "entity": entity,
                    "observation_count": len(observations),
                    "consecutive_first_difference_count": 0,
                    "candidate_status": "NOT_TESTABLE_NONPOSITIVE_FOR_LOG_TRANSFORM",
                    "change_transform": change_mode,
                    "candidate": False,
                    "causal_claim": False,
                    "inferential_p_value": None,
                })
                continue
            changes = [transformed[entity][year] for year in sorted(transformed[entity])]
            change_years = sorted(transformed[entity])

            split = _volatility_split(
                changes, minimum_segment_changes=minimum_segment_changes
            )
            if split is None:
                rows.append({
                    "record_type": "variance_shift_scan",
                    "metric": metric,
                    "entity": entity,
                    "observation_count": len(observations),
                    "consecutive_first_difference_count": len(changes),
                    "candidate_status": "NOT_TESTABLE_MINIMUM_SUPPORT",
                    "change_transform": change_mode,
                    "candidate": False,
                    "causal_claim": False,
                    "inferential_p_value": None,
                })
                continue

            split_index = split["split_index"]
            direction = split["direction"]
            factor = split["variance_change_factor"]
            passes = (
                direction in {"VOLATILITY_EXPANSION", "VOLATILITY_CONTRACTION"}
                and (factor is None or factor >= minimum_variance_change_factor)
            )
            rows.append({
                "record_type": "variance_shift_scan",
                "metric": metric,
                "entity": entity,
                "change_transform": change_mode,
                "observation_count": len(observations),
                "consecutive_first_difference_count": len(changes),
                "first_difference_year_start": change_years[0] if change_years else None,
                "first_difference_year_end": change_years[-1] if change_years else None,
                "candidate_year": change_years[split_index] if split_index < len(change_years) else None,
                "left_change_end_year": change_years[split_index - 1],
                "right_change_start_year": change_years[split_index],
                **split,
                "candidate": bool(passes),
                "candidate_status": (
                    "DISCOVERY_CANDIDATE_UNVALIDATED" if passes
                    else "REJECTED_BY_DESCRIPTIVE_SCREEN"
                ),
                "minimum_variance_change_factor": minimum_variance_change_factor,
                "variance_measure": "squared_max_of_qn_mad_iqr_scales_of_transformed_exact_annual_changes",
                "inferential_p_value": None,
                "null_test_performed": False,
                "causal_claim": False,
                "forecast_generated": False,
                "point_in_time_eligible": False,
            })
    return rows


def jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        for row in rows
    )
