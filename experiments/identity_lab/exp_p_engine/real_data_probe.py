"""Run the domain-neutral vertical slice on committed source data.

Outputs candidate signals and coverage diagnostics only. The repository contains
no ground-truth anomaly labels for these public series, so raw hits are not
counted as verified true/false positives.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from experiments.identity_lab.exp_p_engine.domain_neutral import (
    build_univariate_residuals,
    missing_periods,
    normalize_observations,
    run_candidate_detectors,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "raw"
OUT = ROOT / "experiments" / "identity_lab" / "exp_p_engine" / "results" / "domain_neutral_real_data_probe.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def candidate_summary(observations: list[dict], *, time_unit: str, min_history: int, window: int, baseline_method: str = "rolling_median") -> dict:
    residuals = build_univariate_residuals(
        observations,
        baseline_window=window,
        min_history=min_history,
        time_unit=time_unit,
        baseline_method=baseline_method,
    )
    detectors = run_candidate_detectors(residuals)
    scale_status = Counter(row["status"] for row in residuals)
    cusum_hits = detectors["raw_hits"]["cusum"]
    p1_hits = detectors["raw_hits"]["sign_run"]
    return {
        "baseline_method": baseline_method,
        "observations": len(observations),
        "residual_rows": len(residuals),
        "scale_ready_rows": scale_status.get("ready", 0),
        "scale_unavailable_rows": scale_status.get("scale_unavailable", 0),
        "gap_unresolved_rows": scale_status.get("gap_unresolved", 0),
        "cusum_raw_hits": len(cusum_hits),
        "sign_run_raw_hits": len(p1_hits),
        "calibration_status": detectors["calibration_status"],
    }


def probe_world_bank() -> dict:
    folder = DATA / "financial_world_bank_v1"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    path = folder / "WB_FS_AST_PRVT_GD_ZS_2000_2024.csv"
    raw_rows = read_csv(path)
    normalized = normalize_observations(
        raw_rows,
        {
            "entity_id": "entity_code",
            "metric_id": {"constant": manifest["indicator"]},
            "event_time": "year",
            "value": "value",
            "unit": {"constant": "% of GDP"},
            "source_id": {"constant": "World Bank"},
            "time_support": {"constant": "annual"},
        },
    )
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in normalized["observations"]:
        grouped[row["entity_id"]].append(row)

    years = [str(year) for year in range(2000, 2025)]
    per_series = []
    total_cusum = total_p1 = tested_entities = scale_ready = 0
    trend_cusum = trend_p1 = trend_scale_ready = 0
    median_gap_unresolved = trend_gap_unresolved = 0
    lengths = []
    for entity_id, series in grouped.items():
        coverage = missing_periods(series, years)
        lengths.append(coverage["observed_periods"])
        # Per-entity observation schedules are not present in this snapshot.
        if coverage["observed_periods"] >= 8:
            tested_entities += 1
            median_result = candidate_summary(
                series, time_unit="years", min_history=8, window=12,
                baseline_method="rolling_median",
            )
            trend_result = candidate_summary(
                series, time_unit="years", min_history=8, window=12,
                baseline_method="rolling_theil_sen",
            )
            total_cusum += median_result["cusum_raw_hits"]
            total_p1 += median_result["sign_run_raw_hits"]
            scale_ready += median_result["scale_ready_rows"]
            median_gap_unresolved += median_result["gap_unresolved_rows"]
            trend_cusum += trend_result["cusum_raw_hits"]
            trend_p1 += trend_result["sign_run_raw_hits"]
            trend_scale_ready += trend_result["scale_ready_rows"]
            trend_gap_unresolved += trend_result["gap_unresolved_rows"]
            per_series.append({
                "entity_id": entity_id,
                "coverage": coverage,
                "missingness_probe": "not_run_entity_specific_expected_schedule_absent",
                "rolling_median": median_result,
                "rolling_theil_sen": trend_result,
            })

    expected_slots = len(grouped) * len(years)
    observed_slots = sum(lengths)
    return {
        "source": "World Bank API snapshot",
        "indicator": manifest["indicator"],
        "indicator_name": manifest["indicator_name"],
        "manifest_lastupdated": manifest["lastupdated"],
        "manifest_rows": manifest["rows"],
        "csv_rows": len(raw_rows),
        "entity_count": len(grouped),
        "expected_entity_year_slots": expected_slots,
        "observed_entity_year_slots": observed_slots,
        "unobserved_entity_year_slots": expected_slots - observed_slots,
        "coverage_rate": observed_slots / expected_slots if expected_slots else None,
        "series_length_min": min(lengths) if lengths else 0,
        "series_length_median": statistics.median(lengths) if lengths else 0,
        "series_length_max": max(lengths) if lengths else 0,
        "entities_with_at_least_8_observations": tested_entities,
        "scale_ready_residual_rows_rolling_median": scale_ready,
        "gap_unresolved_rows_rolling_median": median_gap_unresolved,
        "cusum_raw_hits_rolling_median": total_cusum,
        "sign_run_raw_hits_rolling_median": total_p1,
        "scale_ready_residual_rows_rolling_theil_sen": trend_scale_ready,
        "gap_unresolved_rows_rolling_theil_sen": trend_gap_unresolved,
        "cusum_raw_hits_rolling_theil_sen": trend_cusum,
        "sign_run_raw_hits_rolling_theil_sen": trend_p1,
        "missingness_quality_signals": None,
        "missingness_execution": "not_run_entity_specific_expected_schedule_absent",
        "rejected_source_rows": normalized["rejected_rows"],
        "sample_entity_diagnostics": per_series[:10],
        "interpretation": (
            "Raw candidate signals only. Unobserved entity-years are coverage gaps, "
            "not automatically data errors. No ground-truth anomaly labels are present."
        ),
    }


def probe_usgs() -> dict:
    folder = DATA / "usgs_earthquake_m6_5_2000_2024"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    path = folder / manifest["raw_file"]
    raw_rows = read_csv(path)
    normalized = normalize_observations(
        raw_rows,
        {
            "entity_id": {"constant": "USGS:global:magnitude-ge-6.5"},
            "metric_id": {"constant": "earthquake_event_magnitude"},
            "event_time": "time",
            "value": "mag",
            "unit": {"constant": "magnitude"},
            "source_id": {"constant": "USGS FDSN event catalog"},
            "time_support": {"constant": "event"},
        },
    )

    missing_columns = {}
    for column in ("nst", "gap", "dmin", "rms", "horizontalError", "depthError", "magError", "magNst"):
        missing_columns[column] = sum(1 for row in raw_rows if row.get(column, "") == "")

    month_counts: Counter[tuple[int, int]] = Counter()
    for row in normalized["observations"]:
        year, month = row["event_time"][:7].split("-")
        month_counts[(int(year), int(month))] += 1

    monthly = []
    for year in range(2000, 2025):
        for month in range(1, 13):
            monthly.append({
                "entity_id": "USGS:global:magnitude-ge-6.5",
                "metric_id": "monthly_count_magnitude_ge_6.5",
                "event_time": f"{year:04d}-{month:02d}",
                "value": float(month_counts[(year, month)]),
                "observation_status": "observed",
                "unit": "events/month",
                "source_id": "USGS FDSN event catalog",
                "time_support": "monthly",
            })
    median_result = candidate_summary(monthly, time_unit="months", min_history=12, window=24, baseline_method="rolling_median")
    trend_result = candidate_summary(monthly, time_unit="months", min_history=12, window=24, baseline_method="rolling_theil_sen")
    return {
        "source": "USGS FDSN event catalog snapshot",
        "manifest_event_count": manifest["event_count"],
        "csv_event_rows": len(raw_rows),
        "normalized_event_rows": normalized["accepted_rows"],
        "entity_count": 1,
        "event_time_span": [
            min(row["event_time"] for row in normalized["observations"]),
            max(row["event_time"] for row in normalized["observations"]),
        ],
        "optional_column_missing_counts": missing_columns,
        "monthly_series_points": len(monthly),
        "zero_event_months": sum(1 for row in monthly if row["value"] == 0),
        "monthly_detection_candidates": {
            "rolling_median": median_result,
            "rolling_theil_sen": trend_result,
        },
        "interpretation": (
            "The monthly zeroes mean no event meeting this catalog query's magnitude "
            "threshold was returned for that month. They do not mean no earthquake occurred. "
            "The raw catalog's optional fields remain nullable; they are not input blockers."
        ),
    }


def probe_who() -> dict:
    folder = DATA / "who_covid_global_v2"
    manifest_path = folder / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_path = folder / "WHO-COVID-19-global-daily-data.csv"
    return {
        "source": "WHO global COVID-19 daily data",
        "manifest_rows": manifest.get("rows"),
        "manifest_downloaded_at": manifest.get("downloaded_at"),
        "source_file_present": expected_path.exists(),
        "execution": "not_run_raw_file_absent" if not expected_path.exists() else "available_for_next_probe",
        "source_url": manifest.get("source_url"),
        "interpretation": "Manifest metadata is not a substitute for the raw source file.",
    }


def main() -> None:
    report = {
        "engine": "domain_neutral_observation_kernel_v1",
        "branch_scope": "experimental_only",
        "production_engine_modified": False,
        "world_bank": probe_world_bank(),
        "usgs": probe_usgs(),
        "who": probe_who(),
        "global_calibration": "not_claimed",
        "ground_truth_labels": "not_available_in_committed_public_snapshots",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUT.relative_to(ROOT)),
        "world_bank": {
            "rows": report["world_bank"]["csv_rows"],
            "entities": report["world_bank"]["entity_count"],
            "coverage_rate": report["world_bank"]["coverage_rate"],
            "rolling_median_cusum_raw_hits": report["world_bank"]["cusum_raw_hits_rolling_median"],
            "rolling_median_sign_run_raw_hits": report["world_bank"]["sign_run_raw_hits_rolling_median"],
            "rolling_theil_sen_cusum_raw_hits": report["world_bank"]["cusum_raw_hits_rolling_theil_sen"],
            "rolling_theil_sen_sign_run_raw_hits": report["world_bank"]["sign_run_raw_hits_rolling_theil_sen"],
            "missingness_execution": report["world_bank"]["missingness_execution"],
        },
        "usgs": {
            "events": report["usgs"]["csv_event_rows"],
            "monthly_points": report["usgs"]["monthly_series_points"],
            "rolling_median_cusum_raw_hits": report["usgs"]["monthly_detection_candidates"]["rolling_median"]["cusum_raw_hits"],
            "rolling_theil_sen_cusum_raw_hits": report["usgs"]["monthly_detection_candidates"]["rolling_theil_sen"]["cusum_raw_hits"],
        },
        "who": {
            "manifest_rows": report["who"]["manifest_rows"],
            "source_file_present": report["who"]["source_file_present"],
            "execution": report["who"]["execution"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
