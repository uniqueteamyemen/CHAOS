"""Run the frozen detector on versioned, real historical event datasets.

Event rows are binned into UTC calendar months or quarters over the source contracts'
declared complete query windows. The sole transformation is log1p(monthly
event count); no interpolation or forward filling is performed.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from structural_engine.isolated_break_detector_v1.break_detector_v1 import (
    BreakDetectorV1,
    DEFAULT_MARKOV_THRESHOLD,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent / "results" / "real_data_transition_scan.json"
START_YEAR, START_MONTH = 2000, 1
END_YEAR, END_MONTH = 2024, 12


def month_index(year: int, month: int) -> int:
    return (year - START_YEAR) * 12 + (month - START_MONTH)


def month_axis() -> list[str]:
    total = (END_YEAR - START_YEAR) * 12 + END_MONTH
    return [
        f"{START_YEAR + i // 12:04d}-{i % 12 + 1:02d}"
        for i in range(total)
    ]



def monthly_counts(timestamps: list[datetime]) -> list[int]:
    counts = [0] * ((END_YEAR - START_YEAR) * 12 + END_MONTH)
    for stamp in timestamps:
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        stamp = stamp.astimezone(timezone.utc)
        if (stamp.year, stamp.month) < (START_YEAR, START_MONTH) or (
            stamp.year, stamp.month
        ) > (END_YEAR, END_MONTH):
            raise ValueError(f"event_outside_frozen_query_window:{stamp.isoformat()}")
        counts[month_index(stamp.year, stamp.month)] += 1
    return counts

def quarterly_axis() -> list[str]:
    return [
        f"{year:04d}-Q{quarter}"
        for year in range(START_YEAR, END_YEAR + 1)
        for quarter in range(1, 5)
    ]


def quarterly_counts(timestamps: list[datetime]) -> list[int]:
    counts = [0] * (4 * (END_YEAR - START_YEAR + 1))
    for stamp in timestamps:
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        stamp = stamp.astimezone(timezone.utc)
        if (stamp.year, stamp.month) < (START_YEAR, START_MONTH) or (
            stamp.year, stamp.month
        ) > (END_YEAR, END_MONTH):
            raise ValueError(f"event_outside_frozen_query_window:{stamp.isoformat()}")
        index = (stamp.year - START_YEAR) * 4 + (stamp.month - 1) // 3
        counts[index] += 1
    return counts


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_gulf_geojson(path: Path) -> tuple[list[datetime], list[float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    timestamps, magnitudes = [], []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        raw_time, raw_mag = props.get("time"), props.get("mag")
        if raw_time is None or raw_mag is None:
            raise ValueError("gulf_geojson_missing_required_time_or_magnitude")
        timestamps.append(
            datetime.fromtimestamp(float(raw_time) / 1000, tz=timezone.utc)
        )
        magnitudes.append(float(raw_mag))
    return timestamps, magnitudes


def parse_global_usgs_csv(path: Path) -> tuple[list[datetime], list[float]]:
    timestamps, magnitudes = [], []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            raw_time, raw_mag = row.get("time"), row.get("mag")
            if not raw_time or raw_mag in (None, ""):
                raise ValueError("global_usgs_csv_missing_time_or_magnitude")
            timestamps.append(
                datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            )
            magnitudes.append(float(raw_mag))
    return timestamps, magnitudes


def axis_value_for_step(value: object, axis: list[str]) -> str | None:
    if value is None:
        return None
    index = int(value)
    return axis[index] if 0 <= index < len(axis) else None


def ledger_record(event: dict, axis: list[str]) -> dict:
    record = dict(event)
    step = event.get("detection_time", event.get("time"))
    record["series_step"] = step
    record["event_axis_value"] = axis_value_for_step(step, axis)
    for key, output_key in (
        ("estimated_onset", "estimated_onset_axis_value"),
        ("provisional_detection_time", "provisional_axis_value"),
        ("confirmation_time", "confirmation_axis_value"),
        ("resolved_at", "resolved_axis_value"),
    ):
        if key in event:
            record[output_key] = axis_value_for_step(event[key], axis)
    if event.get("resolved_pending_alerts"):
        record["resolved_pending_alerts"] = [
            ledger_record(item, axis)
            for item in event["resolved_pending_alerts"]
        ]
    return record


def summarize_dataset(
    source_id: str, path: Path, timestamps: list[datetime], magnitudes: list[float],
    frequency: str,
) -> dict:
    if frequency == "monthly":
        axis = month_axis()
        counts = monthly_counts(timestamps)
    elif frequency == "quarterly":
        axis = quarterly_axis()
        counts = quarterly_counts(timestamps)
    else:
        raise ValueError(f"unsupported_frequency:{frequency}")
    values = np.log1p(np.asarray(counts, dtype=float))
    modes = {}

    for mode in BreakDetectorV1.MODES:
        result = BreakDetectorV1(
            mode=mode, markov_threshold=DEFAULT_MARKOV_THRESHOLD
        ).analyze(values)
        diag = result.get("diagnostics", {})
        base_scale = float(diag.get("base_diff_scale", 0.0))
        level_scale = float(diag.get("baseline_level_scale", 0.0))
        modes[mode] = {
            "provisional_count": len(result["provisional_events"]),
            "confirmed_count": len(result["confirmed_events"]),
            "transient_count": len(result["transient_anomalies"]),
            "unresolved_count": len(result["unresolved_alerts"]),
            "pending_lifecycle": result["pending_lifecycle"],
            "sample_adequacy": result["sample_adequacy"],
            "diagnostics": diag,
            "baseline_scale_status": (
                "DEGENERATE" if base_scale <= 1e-6 or level_scale <= 1e-6 else "NONDEGENERATE"
            ),
            "event_status_counts": dict(
                Counter(event["status"] for event in result["events"])
            ),
            "transition_ledger": [
                ledger_record(event, axis) for event in result["events"]
            ],
        }

    quiet_differences = np.diff(values[:40])
    quiet_diff_mad = float(
        np.median(np.abs(quiet_differences - np.median(quiet_differences)))
    )
    zero_months = sum(value == 0 for value in counts)
    return {
        "source_id": source_id,
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
        "source_rows": len(timestamps),
        "query_window_utc": "2000-01-01/2024-12-31",
        "observed_first_event_utc": min(timestamps).isoformat(),
        "observed_last_event_utc": max(timestamps).isoformat(),
        "magnitude_min": min(magnitudes),
        "magnitude_max": max(magnitudes),
        "series_frequency": frequency,
        "series_length": len(counts),
        "event_count": sum(counts),
        "zero_event_periods": zero_months,
        "zero_event_period_fraction": round(zero_months / len(counts), 6),
        "distinct_monthly_count_values": sorted(set(counts)),
        "period_axis_utc": axis,
        "period_event_counts": counts,
        "transform": "log1p(period_event_count)",
        "quiet_first_40_periods_diff_mad": quiet_diff_mad,
        "detector_runs": modes,
        "interpretation_guard": (
            "Historical structural-signal scan only; not an earthquake prediction "
            "or a calibrated probability of a future event."
        ),
    }



def inter_event_interval_series(
    timestamps: list[datetime],
) -> tuple[list[float], list[str]]:
    ordered = sorted(
        stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
        for stamp in timestamps
    )
    if len(ordered) < 2:
        raise ValueError("at_least_two_events_required_for_inter_event_intervals")
    intervals_days = [
        (ordered[i + 1] - ordered[i]).total_seconds() / 86400.0
        for i in range(len(ordered) - 1)
    ]
    axis = [ordered[i + 1].isoformat() for i in range(len(ordered) - 1)]
    return intervals_days, axis


def summarize_inter_event_series(
    source_id: str,
    path: Path,
    timestamps: list[datetime],
    magnitudes: list[float],
) -> dict:
    intervals_days, axis = inter_event_interval_series(timestamps)
    values = np.log1p(np.asarray(intervals_days, dtype=float))
    modes = {}
    for mode in BreakDetectorV1.MODES:
        result = BreakDetectorV1(
            mode=mode, markov_threshold=DEFAULT_MARKOV_THRESHOLD
        ).analyze(values)
        diag = result.get("diagnostics", {})
        base_scale = float(diag.get("base_diff_scale", 0.0))
        level_scale = float(diag.get("baseline_level_scale", 0.0))
        modes[mode] = {
            "provisional_count": len(result["provisional_events"]),
            "confirmed_count": len(result["confirmed_events"]),
            "transient_count": len(result["transient_anomalies"]),
            "unresolved_count": len(result["unresolved_alerts"]),
            "pending_lifecycle": result["pending_lifecycle"],
            "sample_adequacy": result["sample_adequacy"],
            "diagnostics": diag,
            "baseline_scale_status": (
                "DEGENERATE" if base_scale <= 1e-6 or level_scale <= 1e-6 else "NONDEGENERATE"
            ),
            "event_status_counts": dict(
                Counter(event["status"] for event in result["events"])
            ),
            "transition_ledger": [
                ledger_record(event, axis) for event in result["events"]
            ],
        }
    quiet_differences = np.diff(values[:40])
    quiet_diff_mad = float(
        np.median(np.abs(quiet_differences - np.median(quiet_differences)))
    )
    return {
        "source_id": source_id,
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
        "source_rows": len(timestamps),
        "event_count": len(timestamps),
        "observed_first_event_utc": min(timestamps).isoformat(),
        "observed_last_event_utc": max(timestamps).isoformat(),
        "magnitude_min": min(magnitudes),
        "magnitude_max": max(magnitudes),
        "series_frequency": "event_time_interarrival",
        "series_length": len(intervals_days),
        "event_axis_utc": axis,
        "inter_event_interval_days": intervals_days,
        "transform": "log1p(inter_event_interval_days)",
        "quiet_first_40_intervals_diff_mad": quiet_diff_mad,
        "detector_runs": modes,
        "interpretation_guard": (
            "The detector operates in event order; all horizons are counts of "
            "inter-event intervals, not fixed calendar durations."
        ),
    }



def summarize_un_ama_gdp_panel(path: Path) -> dict:
    grouped: dict[str, dict] = {}
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            row_count += 1
            if (
                row.get("IndicatorName") != "Gross Domestic Product (GDP)"
                or not row.get("ama_gdp_growth_pct", "").strip()
            ):
                continue
            country_id = row["CountryID"]
            value = float(row["ama_gdp_growth_pct"])
            if not np.isfinite(value):
                continue
            grouped.setdefault(
                country_id,
                {"country": row["Country"], "points": []},
            )["points"].append((int(row["year"]), value))

    screened = []
    for country_id, entry in sorted(grouped.items(), key=lambda item: int(item[0])):
        points = sorted(entry["points"])
        years = [year for year, _ in points]
        contiguous = all(years[i] == years[i - 1] + 1 for i in range(1, len(years)))
        if len(points) < BreakDetectorV1.MIN_SERIES_LENGTH or not contiguous:
            continue

        values = np.asarray([value for _, value in points], dtype=float)
        axis = [str(year) for year in years]
        mode_results = {}
        for mode in BreakDetectorV1.MODES:
            result = BreakDetectorV1(
                mode=mode, markov_threshold=DEFAULT_MARKOV_THRESHOLD
            ).analyze(values)
            mode_results[mode] = {
                "event_status_counts": dict(
                    Counter(event["status"] for event in result["events"])
                ),
                "sample_adequacy": result["sample_adequacy"],
                "pending_lifecycle": result["pending_lifecycle"],
                "diagnostics": result.get("diagnostics", {}),
                "transition_ledger": [
                    ledger_record(event, axis) for event in result["events"]
                ],
            }
        screened.append(
            {
                "country_id": country_id,
                "country": entry["country"],
                "observations": len(points),
                "first_year": years[0],
                "last_year": years[-1],
                "mode_results": mode_results,
            }
        )

    full_resolution = sum(
        item["observations"] >= BreakDetectorV1.MIN_FULL_RESOLUTION_LENGTH
        for item in screened
    )
    full_consensus = sum(
        item["observations"] >= BreakDetectorV1.MIN_FULL_CONSENSUS_LENGTH
        for item in screened
    )
    return {
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
        "row_count": row_count,
        "country_series_in_source": len(grouped),
        "eligible_contiguous_gdp_growth_series": len(screened),
        "screened_year_range": (
            [min(item["first_year"] for item in screened),
             max(item["last_year"] for item in screened)]
            if screened else None
        ),
        "minimum_observations_for_first_evaluation": BreakDetectorV1.MIN_SERIES_LENGTH,
        "minimum_for_full_resolution": BreakDetectorV1.MIN_FULL_RESOLUTION_LENGTH,
        "minimum_for_full_consensus": BreakDetectorV1.MIN_FULL_CONSENSUS_LENGTH,
        "full_resolution_eligible_series": full_resolution,
        "full_consensus_eligible_series": full_consensus,
        "decision": "SCREENED_ONLY_INSUFFICIENT_POST_WARMUP_HORIZON",
        "reason": (
            "The eligible GDP-growth histories contain 54 contiguous annual observations. "
            "That passes the 52-point start gate but does not provide the 66 points needed "
            "for the 14-step resolution horizon or the 87 points needed for the 35-step "
            "consensus window."
        ),
        "series_results": screened,
    }


def summarize_catalog_first_readiness() -> dict:
    macro_path = (
        ROOT / "catalog_first" / "readiness_gate" / "macro_plus_eia_energy"
        / "MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv"
    )
    eia_path = (
        ROOT / "catalog_first" / "gap_assets"
        / "EIA_SELECTED_ANNUAL_2000_2024_LONG.csv"
    )
    un_ama_path = (
        ROOT / "catalog_first" / "readiness_gate" / "independent_sources"
        / "un_ama_2026" / "staged"
        / "UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv"
    )

    macro_years: dict[str, set[int]] = {}
    macro_rows = 0
    with macro_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            macro_rows += 1
            macro_years.setdefault(row["entity_code"], set()).add(int(row["year"]))

    eia_years: dict[tuple[str, str], set[int]] = {}
    eia_rows = 0
    with eia_path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            eia_rows += 1
            key = (row["entity_code"], row["variable_id"])
            eia_years.setdefault(key, set()).add(int(row["year"]))

    ucdp_manifest = (
        ROOT / "catalog_first" / "readiness_gate" / "independent_sources"
        / "ucdp_ged_26_1" / "UCDP_GED_26_1_RAW_MANIFEST.json"
    )
    ucdp_raw = (
        ROOT / "catalog_first" / "readiness_gate" / "independent_sources"
        / "ucdp_ged_26_1" / "raw" / "UCDP_GED_26_1_RAW.zip"
    )
    noaa_profile = ROOT / "catalog_first" / "gsom_monthly_profile.json"
    noaa_raw_dir = ROOT / "catalog_first" / "raw" / "noaa" / "gsom_monthly" / "stations"
    who_manifest = RAW / "who_covid_global_v2" / "MANIFEST.json"
    who_raw_v2 = (
        RAW / "who_covid_global_v2" / "WHO-COVID-19-global-daily-data.csv"
    )
    who_raw_catalog = (
        ROOT / "catalog_first" / "readiness_gate" / "independent_sources"
        / "who_covid_2026" / "raw" / "WHO_COVID_GLOBAL_DAILY_RAW.csv"
    )
    return {
        "macro_plus_eia_annual_panel": {
            "source_file": str(macro_path.relative_to(ROOT)),
            "source_sha256": sha256(macro_path),
            "row_count": macro_rows,
            "entity_count": len(macro_years),
            "min_years_per_entity": min(map(len, macro_years.values())),
            "max_years_per_entity": max(map(len, macro_years.values())),
            "decision": "NOT_RUN_ANNUAL_HISTORY_TOO_SHORT",
        },
        "eia_selected_annual_long": {
            "source_file": str(eia_path.relative_to(ROOT)),
            "source_sha256": sha256(eia_path),
            "row_count": eia_rows,
            "country_series_count": len(eia_years),
            "min_years_per_series": min(map(len, eia_years.values())),
            "max_years_per_series": max(map(len, eia_years.values())),
            "decision": "NOT_RUN_ANNUAL_HISTORY_TOO_SHORT",
        },
        "un_ama_gdp_growth": summarize_un_ama_gdp_panel(un_ama_path),
        "raw_payload_availability": {
            "ucdp_ged_event_csv": {
                "manifest_present": ucdp_manifest.exists(),
                "manifest_sha256": sha256(ucdp_manifest),
                "raw_payload_present": ucdp_raw.exists(),
                "decision": "NOT_RUN_RAW_PAYLOAD_NOT_COMMITTED",
            },
            "noaa_gsom_monthly_station_csvs": {
                "profile_present": noaa_profile.exists(),
                "profile_sha256": sha256(noaa_profile),
                "raw_directory_present": noaa_raw_dir.exists(),
                "decision": "NOT_RUN_RAW_PAYLOAD_NOT_COMMITTED",
            },
            "who_covid_daily_csv": {
                "manifest_present": who_manifest.exists(),
                "manifest_sha256": sha256(who_manifest),
                "raw_payload_v2_present": who_raw_v2.exists(),
                "catalog_first_raw_payload_present": who_raw_catalog.exists(),
                "decision": "NOT_RUN_RAW_PAYLOAD_NOT_COMMITTED",
            },
        },
    }


def summarize_world_bank(path: Path) -> dict:
    by_entity: dict[str, list[int]] = {}
    row_count = 0
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            row_count += 1
            by_entity.setdefault(row["entity_code"], []).append(int(row["year"]))
    lengths = [len(set(years)) for years in by_entity.values()]
    return {
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
        "indicator": "FS.AST.PRVT.GD.ZS",
        "row_count": row_count,
        "entity_count": len(by_entity),
        "max_annual_observations_per_entity": max(lengths, default=0),
        "detector_minimum_observations": 52,
        "eligible_entity_count": sum(length >= 52 for length in lengths),
        "decision": "NOT_RUN_INSUFFICIENT_HISTORY",
        "reason": (
            "The committed 2000-2024 annual extract provides at most 25 points "
            "per entity; the frozen detector requires at least 52."
        ),
    }


def main() -> None:
    gulf_path = RAW / "seismic_gulf_of_aden_v1" / "usgs_gulf_of_aden_query.geojson"
    global_path = (
        RAW / "usgs_earthquake_m6_5_2000_2024"
        / "USGS_EARTHQUAKE_M6_5_2000_2024_RAW.csv"
    )
    wb_path = RAW / "financial_world_bank_v1" / "WB_FS_AST_PRVT_GD_ZS_2000_2024.csv"

    gulf_times, gulf_magnitudes = parse_gulf_geojson(gulf_path)
    global_times, global_magnitudes = parse_global_usgs_csv(global_path)
    report = {
        "report_version": "1.3",
        "detector": "isolated_break_detector_v1",
        "markov_threshold": DEFAULT_MARKOV_THRESHOLD,
        "catalog_first_readiness": summarize_catalog_first_readiness(),
        "contracts": {
            "seismic_transfer_contract_sha256": sha256(
                ROOT / "experimental_contracts" / "EVENT_PATH_SEISMIC_TRANSFER_CONTRACT_V1.json"
            )
        },
        "sources": [
            summarize_dataset(
                "USGS_GULF_OF_ADEN_M45_PLUS",
                gulf_path,
                gulf_times,
                gulf_magnitudes,
                frequency,
            )
            for frequency in ("monthly", "quarterly")
        ] + [
            summarize_dataset(
                "USGS_GLOBAL_M65_PLUS",
                global_path,
                global_times,
                global_magnitudes,
                frequency,
            )
            for frequency in ("monthly", "quarterly")
        ] + [
            summarize_inter_event_series(
                "USGS_GULF_OF_ADEN_M45_PLUS",
                gulf_path,
                gulf_times,
                gulf_magnitudes,
            ),
            summarize_inter_event_series(
                "USGS_GLOBAL_M65_PLUS",
                global_path,
                global_times,
                global_magnitudes,
            ),
        ],
        "excluded_sources": [summarize_world_bank(wb_path)],
        "limits": [
            "The detector is transferred unchanged from synthetic validation to real data.",
            "Monthly and quarterly event counts are declared event-activity proxies, not physical magnitude or seismic energy.",
            "Consensus matching retains its original 35-step rule; its calendar interpretation changes with the input representation.",
            "Event-time inter-arrival scans use event order; their horizons are intervals, not calendar months.",
            "A detected historical transition is not evidence of causal influence or a forecast of an event.",
            "A degenerate quiet-period scale invalidates interpretation even if the detector returns events.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    safe_report = json_safe(report)
    OUT.write_text(
        json.dumps(safe_report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            json_safe({
                "report": str(OUT.relative_to(ROOT)),
                "sources": [
                    {
                        "source_id": item["source_id"],
                        "rows": item["source_rows"],
                        "events": item["event_count"],
                        "frequency": item["series_frequency"],
                        "periods": item["series_length"],
                        "zero_period_fraction": item.get("zero_event_period_fraction"),
                        "mode_counts": {
                            mode: {
                                "provisional": result["provisional_count"],
                                "confirmed": result["confirmed_count"],
                                "transient": result["transient_count"],
                                "unresolved": result["unresolved_count"],
                                "baseline_scale_status": result["baseline_scale_status"],
                            }
                            for mode, result in item["detector_runs"].items()
                        },
                    }
                    for item in report["sources"]
                ],
                "world_bank": report["excluded_sources"][0],
                "catalog_first": {
                    "un_ama_eligible_gdp_series": report["catalog_first_readiness"]["un_ama_gdp_growth"]["eligible_contiguous_gdp_growth_series"],
                    "un_ama_full_resolution_eligible": report["catalog_first_readiness"]["un_ama_gdp_growth"]["full_resolution_eligible_series"],
                    "un_ama_full_consensus_eligible": report["catalog_first_readiness"]["un_ama_gdp_growth"]["full_consensus_eligible_series"],
                    "macro_panel_max_years": report["catalog_first_readiness"]["macro_plus_eia_annual_panel"]["max_years_per_entity"],
                    "eia_series_max_years": report["catalog_first_readiness"]["eia_selected_annual_long"]["max_years_per_series"],
                    "raw_payload_availability": report["catalog_first_readiness"]["raw_payload_availability"],
                },
            }),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
