"""Gardner–Knopoff Type-I space-time window declustering."""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

EARTH_RADIUS_KM = 6371.0088
GK_DECIMAL_YEAR_DAYS = 364.75
DEFAULT_FORESHOCK_TIME_FRACTION = 0.5


def _as_utc_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("event_time_must_be_iso8601_or_datetime")
    if parsed.tzinfo is None:
        raise ValueError("event_time_must_include_timezone")
    return parsed.astimezone(timezone.utc)


def _as_utc_epoch(value: Any) -> float:
    return _as_utc_datetime(value).timestamp()


def decimal_year(value: Any) -> float:
    """Match the decimal-year clock used by OpenQuake HMTK."""
    parsed = _as_utc_datetime(value)
    year_start = datetime(parsed.year, 1, 1, tzinfo=timezone.utc)
    next_year = datetime(parsed.year + 1, 1, 1, tzinfo=timezone.utc)
    elapsed = (parsed - year_start).total_seconds()
    year_seconds = (next_year - year_start).total_seconds()
    return parsed.year + elapsed / year_seconds


def gardner_knopoff_windows(magnitude: float) -> tuple[float, float]:
    """Return original GK1 spatial radius (km) and temporal window (days)."""
    m = float(magnitude)
    if not math.isfinite(m):
        raise ValueError("magnitude_must_be_finite")
    space_km = 10.0 ** (0.1238 * m + 0.983)
    if m >= 6.5:
        time_days = 10.0 ** (0.032 * m + 2.7389)
    else:
        time_days = 10.0 ** (0.5409 * m - 0.547)
    if not (math.isfinite(space_km) and math.isfinite(time_days)):
        raise ValueError("invalid_declustering_window")
    return space_km, time_days


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not all(math.isfinite(float(v)) for v in (lat1, lon1, lat2, lon2)):
        raise ValueError("coordinates_must_be_finite")
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("latitude_out_of_range")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("longitude_out_of_range")
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _unit_sphere(lat: float, lon: float) -> tuple[float, float, float]:
    phi, lam = math.radians(lat), math.radians(lon)
    return (math.cos(phi) * math.cos(lam),
            math.cos(phi) * math.sin(lam), math.sin(phi))


def gardner_knopoff_declustering(
    events: list[dict[str, Any]],
    foreshock_time_fraction: float = DEFAULT_FORESHOCK_TIME_FRACTION,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply magnitude-priority GK1 windows and retain every event with a role.

    Mirrors HMTK Type-I semantics: descending-magnitude priority, backward
    window scaled by foreshock_time_fraction, and full forward window.
    """
    fraction = float(foreshock_time_fraction)
    if not math.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        raise ValueError("foreshock_time_fraction_must_be_in_[0,1]")

    prepared: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in events:
        event_id = str(raw.get("id", raw.get("event_id", ""))).strip()
        if not event_id:
            raise ValueError("event_missing_id")
        if event_id in seen_ids:
            raise ValueError(f"duplicate_event_id:{event_id}")
        seen_ids.add(event_id)
        try:
            epoch = _as_utc_epoch(raw.get("time", raw.get("time_utc")))
            magnitude = float(raw["magnitude"])
            latitude = float(raw["latitude"])
            longitude = float(raw["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid_event:{event_id}:{exc}") from exc
        if not all(math.isfinite(v) for v in (magnitude, latitude, longitude)):
            raise ValueError(f"nonfinite_event_field:{event_id}")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(f"invalid_coordinates:{event_id}")
        space_km, time_days = gardner_knopoff_windows(magnitude)
        prepared.append({
            "original": dict(raw), "id": event_id, "epoch": epoch,
            "decimal_year": decimal_year(raw.get("time", raw.get("time_utc"))),
            "magnitude": magnitude, "latitude": latitude, "longitude": longitude,
            "space_km": space_km, "time_days": time_days,
        })

    prepared.sort(key=lambda item: (-item["magnitude"], item["epoch"], item["id"]))
    if not prepared:
        return [], {
            "method": "Gardner-Knopoff Type-I",
            "foreshock_time_fraction": fraction,
            "events_input": 0, "mainshocks_retained": 0,
            "dependent_events_removed": 0, "clustered_events": 0,
            "cluster_count": 0, "regional_calibration_status": "NOT_ESTABLISHED",
        }

    xyz = np.asarray([_unit_sphere(item["latitude"], item["longitude"])
                      for item in prepared], dtype=float)
    tree = cKDTree(xyz)
    assigned: dict[int, dict[str, Any]] = {}
    cluster_id = 0

    for main_index, main in enumerate(prepared):
        if main_index in assigned:
            continue
        angular_radius = min(math.pi, main["space_km"] / EARTH_RADIUS_KM)
        chord_radius = 2.0 * math.sin(angular_radius / 2.0)
        candidates = tree.query_ball_point(xyz[main_index], chord_radius)
        # OpenQuake HMTK represents these empirical windows in decimal years
        # using the fixed 364.75-day conversion in GardnerKnopoffWindow.
        time_window_years = main["time_days"] / GK_DECIMAL_YEAR_DAYS
        backward_years = fraction * time_window_years
        members: list[int] = []

        for candidate_index in candidates:
            if candidate_index in assigned:
                continue
            candidate = prepared[candidate_index]
            delta_years = candidate["decimal_year"] - main["decimal_year"]
            if delta_years < -backward_years or delta_years > time_window_years:
                continue
            delta_days = (candidate["epoch"] - main["epoch"]) / 86400.0
            distance = haversine_km(
                main["latitude"], main["longitude"],
                candidate["latitude"], candidate["longitude"],
            )
            if distance <= main["space_km"]:
                members.append(candidate_index)

        if len(members) == 1:
            assigned[main_index] = {
                "cluster_id": 0, "cluster_mainshock_id": main["id"],
                "declustering_role": "BACKGROUND",
                "time_delta_days_from_mainshock": 0.0,
                "space_window_km": round(main["space_km"], 6),
                "time_window_days": round(main["time_days"], 6),
                "time_window_decimal_years": round(time_window_years, 9),
            }
            continue

        cluster_id += 1
        for member_index in members:
            member = prepared[member_index]
            delta_days = (member["epoch"] - main["epoch"]) / 86400.0
            role = ("MAINSHOCK" if member_index == main_index else
                    ("FORESHOCK" if delta_days < 0 else "AFTERSHOCK"))
            assigned[member_index] = {
                "cluster_id": cluster_id, "cluster_mainshock_id": main["id"],
                "declustering_role": role,
                "time_delta_days_from_mainshock": round(delta_days, 8),
                "space_window_km": round(main["space_km"], 6),
                "time_window_days": round(main["time_days"], 6),
                "time_window_decimal_years": round(time_window_years, 9),
            }

    output: list[dict[str, Any]] = []
    for index, item in enumerate(prepared):
        labels = assigned.get(index)
        if labels is None:
            raise AssertionError(f"event_not_classified:{item['id']}")
        output.append({**item["original"], **labels})
    output.sort(key=lambda row: (
        _as_utc_epoch(row.get("time", row.get("time_utc"))),
        str(row.get("id", row.get("event_id"))),
    ))
    dependent = [row for row in output
                 if row["declustering_role"] in {"FORESHOCK", "AFTERSHOCK"}]
    retained = [row for row in output
                if row["declustering_role"] in {"MAINSHOCK", "BACKGROUND"}]
    backgrounds = sum(row["declustering_role"] == "BACKGROUND" for row in output)
    return output, {
        "method": "Gardner-Knopoff Type-I magnitude-ordered space-time windows",
        "foreshock_time_fraction": fraction,
        "events_input": len(output), "retained_events": len(retained),
        "cluster_mainshocks_retained": sum(
            row["declustering_role"] == "MAINSHOCK" for row in output
        ),
        "dependent_events_removed": len(dependent),
        "clustered_events": len(output) - backgrounds,
        "background_singletons": backgrounds,
        "cluster_count": cluster_id,
        "retained_fraction": len(retained) / len(output) if output else None,
        "regional_calibration_status": "NOT_ESTABLISHED",
    }
