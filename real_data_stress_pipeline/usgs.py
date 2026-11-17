"""USGS ComCat fetcher for five predeclared spatial seismic-belt windows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from .fetch import SourceFetcher


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _event_timestamp(feature: dict) -> datetime | None:
    raw = (feature.get("properties") or {}).get("time")
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(float(raw) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _query_chunk(
    fetcher: SourceFetcher,
    belt: dict,
    start: datetime,
    end: datetime,
    min_magnitude: float,
    limit: int,
    depth: int = 0,
) -> tuple[list[dict], list[dict]]:
    params = {
        "format": "geojson",
        "starttime": _iso_utc(start),
        "endtime": _iso_utc(end),
        "minmagnitude": min_magnitude,
        "minlatitude": belt["minlatitude"],
        "maxlatitude": belt["maxlatitude"],
        "minlongitude": belt["minlongitude"],
        "maxlongitude": belt["maxlongitude"],
        "orderby": "time-asc",
        "limit": limit,
    }
    source_id = (
        f"usgs_{belt['id']}_m{min_magnitude:g}_"
        f"{start.strftime('%Y%m%dT%H%M%S')}_{end.strftime('%Y%m%dT%H%M%S')}"
    )
    payload, snapshot = fetcher.get_json(
        source_id=source_id,
        url="https://earthquake.usgs.gov/fdsnws/event/1/query",
        params=params,
        subdirectory=f"usgs/{belt['id']}",
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise ValueError(f"usgs_geojson_shape_invalid:{source_id}")

    features = payload["features"]
    metadata = payload.get("metadata") or {}
    reported_count = int(metadata.get("count") or len(features))
    if reported_count > len(features) or len(features) >= limit:
        if depth >= 16 or (end - start).total_seconds() <= 1:
            raise RuntimeError(
                f"usgs_query_still_truncated_after_subdivision:{source_id}:"
                f"reported={reported_count}:returned={len(features)}"
            )
        midpoint = start + (end - start) / 2
        left_end = midpoint
        right_start = midpoint + timedelta(seconds=1)
        left_features, left_meta = _query_chunk(
            fetcher, belt, start, left_end, min_magnitude, limit, depth + 1
        )
        right_features, right_meta = _query_chunk(
            fetcher, belt, right_start, end, min_magnitude, limit, depth + 1
        )
        return left_features + right_features, [snapshot.__dict__, *left_meta, *right_meta]

    return features, [snapshot.__dict__]


def fetch_belt_events(
    fetcher: SourceFetcher,
    belt: dict,
    start_year: int = 1980,
    end_year: int = 2024,
    min_magnitude: float = 4.5,
    limit: int = 20000,
) -> tuple[list[dict], dict]:
    all_features: list[dict] = []
    snapshots: list[dict] = []

    for year in range(start_year, end_year + 1):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            if year < end_year
            else datetime(end_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        )
        features, chunk_snapshots = _query_chunk(
            fetcher, belt, start, end, min_magnitude, limit
        )
        all_features.extend(features)
        snapshots.extend(chunk_snapshots)

    deduplicated: dict[str, dict] = {}
    without_id = 0
    for feature in all_features:
        event_id = feature.get("id")
        if event_id:
            deduplicated[str(event_id)] = feature
        else:
            without_id += 1

    events: list[dict] = []
    invalid = 0
    for event_id, feature in deduplicated.items():
        stamp = _event_timestamp(feature)
        props = feature.get("properties") or {}
        try:
            magnitude = float(props.get("mag"))
        except (TypeError, ValueError):
            invalid += 1
            continue
        if stamp is None or not np.isfinite(magnitude):
            invalid += 1
            continue
        events.append({
            "event_id": event_id,
            "time_utc": stamp,
            "magnitude": magnitude,
            "place": props.get("place"),
            "event_type": props.get("type"),
            "net": props.get("net"),
            "code": props.get("code"),
            "status": props.get("status"),
        })
    events.sort(key=lambda item: item["time_utc"])

    summary = {
        "belt_id": belt["id"],
        "belt_label": belt["label"],
        "query_bounds": {
            key: belt[key]
            for key in ("minlatitude", "maxlatitude", "minlongitude", "maxlongitude")
        },
        "query_window_utc": [f"{start_year}-01-01", f"{end_year}-12-31"],
        "minimum_magnitude_requested": min_magnitude,
        "query_chunk_count": len(snapshots),
        "raw_feature_count": len(all_features),
        "deduplicated_event_count": len(events),
        "features_without_event_id": without_id,
        "invalid_event_records": invalid,
        "first_event_utc": events[0]["time_utc"].isoformat() if events else None,
        "last_event_utc": events[-1]["time_utc"].isoformat() if events else None,
        "raw_snapshots": snapshots,
    }
    return events, summary


def build_inter_event_series(
    belt_id: str,
    belt_label: str,
    events: list[dict],
    magnitude_threshold: float,
    minimum_intervals: int = 87,
) -> dict:
    selected = [
        item for item in events
        if item["magnitude"] >= magnitude_threshold
    ]
    selected.sort(key=lambda item: item["time_utc"])
    if len(selected) < minimum_intervals + 1:
        return {
            "source_id": f"USGS_COMCAT::{belt_id}",
            "series_id": f"USGS::{belt_id}::M{magnitude_threshold:g}",
            "series_name": f"{belt_label} — M{magnitude_threshold:g}+ inter-event intervals",
            "frequency": "event_time_interarrival",
            "category": "seismic",
            "magnitude_threshold": magnitude_threshold,
            "event_count": len(selected),
            "observation_count": max(0, len(selected) - 1),
            "eligible_g0": False,
            "rejection_reason": (
                f"insufficient_events_for_{minimum_intervals}_intervals:"
                f"events={len(selected)}"
            ),
        }

    intervals_days: list[float] = []
    periods: list[str] = []
    for previous, current in zip(selected, selected[1:]):
        days = (current["time_utc"] - previous["time_utc"]).total_seconds() / 86400.0
        if days <= 0:
            continue
        intervals_days.append(days)
        periods.append(current["time_utc"].isoformat())

    values = np.log1p(np.asarray(intervals_days, dtype=float))
    return {
        "source_id": f"USGS_COMCAT::{belt_id}",
        "series_id": f"USGS::{belt_id}::M{magnitude_threshold:g}",
        "series_name": f"{belt_label} — M{magnitude_threshold:g}+ inter-event intervals",
        "frequency": "event_time_interarrival",
        "category": "seismic",
        "transform": "log1p(days_between_consecutive_events)",
        "magnitude_threshold": magnitude_threshold,
        "event_count": len(selected),
        "observation_count": len(values),
        "periods": periods,
        "values": values.tolist(),
        "first_event_utc": selected[0]["time_utc"].isoformat(),
        "last_event_utc": selected[-1]["time_utc"].isoformat(),
        "eligible_g0": len(values) >= minimum_intervals,
        "rejection_reason": None,
    }


def build_all_belt_series(
    fetcher: SourceFetcher,
    belts: list[dict],
    magnitude_levels: list[float],
    start_year: int = 1980,
    end_year: int = 2024,
    query_min_magnitude: float = 4.5,
) -> tuple[list[dict], list[dict]]:
    series: list[dict] = []
    belt_summaries: list[dict] = []
    for belt in belts:
        events, summary = fetch_belt_events(
            fetcher=fetcher,
            belt=belt,
            start_year=start_year,
            end_year=end_year,
            min_magnitude=query_min_magnitude,
        )
        belt_summaries.append(summary)
        for threshold in magnitude_levels:
            item = build_inter_event_series(
                belt_id=belt["id"],
                belt_label=belt["label"],
                events=events,
                magnitude_threshold=float(threshold),
            )
            series.append(item)
    return series, belt_summaries
