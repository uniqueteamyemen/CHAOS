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


def month_for_step(value: object, axis: list[str]) -> str | None:
    if value is None:
        return None
    index = int(value)
    return axis[index] if 0 <= index < len(axis) else None


def ledger_record(event: dict, axis: list[str]) -> dict:
    record = dict(event)
    step = event.get("detection_time", event.get("time"))
    record["series_step"] = step
    record["event_period_utc"] = month_for_step(step, axis)
    for key, output_key in (
        ("estimated_onset", "estimated_onset_period_utc"),
        ("provisional_detection_time", "provisional_period_utc"),
        ("confirmation_time", "confirmation_period_utc"),
        ("resolved_at", "resolved_period_utc"),
    ):
        if key in event:
            record[output_key] = month_for_step(event[key], axis)
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
        "report_version": "1.1",
        "detector": "isolated_break_detector_v1",
        "markov_threshold": DEFAULT_MARKOV_THRESHOLD,
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
        ],
        "excluded_sources": [summarize_world_bank(wb_path)],
        "limits": [
            "The detector is transferred unchanged from synthetic validation to real data.",
            "Monthly and quarterly event counts are declared event-activity proxies, not physical magnitude or seismic energy.",
            "Consensus matching retains its original 35-step rule; this has not been recalibrated to monthly time.",
            "A detected historical transition is not evidence of causal influence or a forecast of an event.",
            "A degenerate quiet-period scale invalidates interpretation even if the detector returns events.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "report": str(OUT.relative_to(ROOT)),
                "sources": [
                    {
                        "source_id": item["source_id"],
                        "rows": item["source_rows"],
                        "events": item["event_count"],
                        "frequency": item["series_frequency"],
                        "periods": item["series_length"],
                        "zero_period_fraction": item["zero_event_period_fraction"],
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
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
