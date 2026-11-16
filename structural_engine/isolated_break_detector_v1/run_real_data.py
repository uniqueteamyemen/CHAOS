"""Run the frozen detector on versioned, real historical event datasets.

Event rows are binned into UTC calendar months over the source contracts'
declared complete query windows. The sole transformation is log1p(monthly
event count); no interpolation or forward filling is performed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from structural_engine.isolated_break_detector_v1.break_detector_v1 import (\n    BreakDetectorV1,\n    DEFAULT_MARKOV_THRESHOLD,\n)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent / "results" / "real_data_transition_scan.json"
START_YEAR, START_MONTH = 2000, 1
END_YEAR, END_MONTH = 2024, 12


def month_index(year: int, month: int) -> int:
    return (year - START_YEAR) * 12 + (month - START_MONTH)


def monthly_counts(timestamps: list[datetime]) -> list[int]:
    total = (END_YEAR - START_YEAR) * 12 + END_MONTH
    counts = [0] * total
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_gulf_geojson(path: Path) -> tuple[list[datetime], int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    stamps = []
    for feature in features:
        props = feature.get("properties") or {}
        raw_time = props.get("time")
        if raw_time is None or props.get("mag") is None:
            raise ValueError("gulf_geojson_missing_required_time_or_magnitude")
        stamps.append(datetime.fromtimestamp(float(raw_time) / 1000, tz=timezone.utc))
    return stamps, len(features)


def parse_global_usgs_csv(path: Path) -> tuple[list[datetime], int]:
    stamps = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            raw_time = row.get("time")
            if not raw_time:
                raise ValueError("global_usgs_csv_missing_time")
            stamps.append(datetime.fromisoformat(raw_time.replace("Z", "+00:00")))
    return stamps, len(stamps)


def summarize_dataset(source_id: str, path: Path, timestamps: list[datetime], row_count: int) -> dict:
    counts = monthly_counts(timestamps)
    values = np.log1p(np.asarray(counts, dtype=float))
    modes = {}
    for mode in BreakDetectorV1.MODES:
        result = BreakDetectorV1(
            mode=mode, markov_threshold=DEFAULT_MARKOV_THRESHOLD
        ).analyze(values)
        diag = result.get("diagnostics", {})
        modes[mode] = {
            "provisional_count": len(result["provisional_events"]),
            "confirmed_count": len(result["confirmed_events"]),
            "transient_count": len(result["transient_anomalies"]),
            "unresolved_count": len(result["unresolved_alerts"]),
            "pending_lifecycle": result["pending_lifecycle"],
            "diagnostics": diag,
            "event_status_counts": dict(
                Counter(event["status"] for event in result["events"])
            ),
        }

    quiet = values[:40]
    quiet_diff_mad = float(np.median(np.abs(np.diff(quiet) - np.median(np.diff(quiet)))))
    zero_months = sum(value == 0 for value in counts)
    return {
        "source_id": source_id,
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": sha256(path),
        "source_rows": row_count,
        "query_window_utc": "2000-01-01/2024-12-31",
        "series_frequency": "monthly",
        "series_length": len(counts),
        "event_count": sum(counts),
        "zero_event_months": zero_months,
        "zero_event_month_fraction": round(zero_months / len(counts), 6),
        "distinct_monthly_count_values": sorted(set(counts)),
        "transform": "log1p(monthly_event_count)",
        "quiet_first_40_months_median_absolute_deviation_of_differences": quiet_diff_mad,
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

    gulf_times, gulf_rows = parse_gulf_geojson(gulf_path)
    global_times, global_rows = parse_global_usgs_csv(global_path)
    report = {
        "report_version": "1.0",
        "detector": "isolated_break_detector_v1",
        "markov_threshold": DEFAULT_MARKOV_THRESHOLD,
        "sources": [
            summarize_dataset("USGS_GULF_OF_ADEN_M45_PLUS", gulf_path, gulf_times, gulf_rows),
            summarize_dataset("USGS_GLOBAL_M65_PLUS", global_path, global_times, global_rows),
        ],
        "excluded_sources": [summarize_world_bank(wb_path)],
        "limits": [
            "The detector is being transferred unchanged from synthetic validation to real data.",
            "Monthly event counts are a declared event-activity proxy, not physical magnitude or seismic energy.",
            "Consensus matching retains its original 35-step rule; this has not been recalibrated to monthly time.",
            "A detected historical transition is not evidence of causal influence or a forecast of an event.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(OUT.relative_to(ROOT)),
        "sources": [
            {
                "source_id": item["source_id"],
                "rows": item["source_rows"],
                "events": item["event_count"],
                "months": item["series_length"],
                "zero_month_fraction": item["zero_event_month_fraction"],
                "mode_counts": {
                    mode: {
                        "provisional": result["provisional_count"],
                        "confirmed": result["confirmed_count"],
                        "transient": result["transient_count"],
                        "unresolved": result["unresolved_count"],
                    }
                    for mode, result in item["detector_runs"].items()
                },
            }
            for item in report["sources"]
        ],
        "world_bank": report["excluded_sources"][0],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
