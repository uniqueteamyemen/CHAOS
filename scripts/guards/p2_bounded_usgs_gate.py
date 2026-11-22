#!/usr/bin/env python3
"""Bounded pre-merge live USGS integrity gate for the P2.2 ingestion path."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from real_data_stress_pipeline import run_pipeline as p2

BELT = {
    "id": "p2_pr_global_integrity_gate",
    "name": "Global bounded integrity gate",
    "minlatitude": -90.0,
    "maxlatitude": 90.0,
    "minlongitude": -180.0,
    "maxlongitude": 180.0,
}
START = "2024-01-01T00:00:00"
END = "2024-02-01T00:00:00"
MIN_MAGNITUDE = float(os.getenv("P2_GATE_MIN_MAGNITUDE", "6.0"))


def validate_payload(raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw)
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise RuntimeError("USGS bounded query returned no feature list or no events")

    accepted: dict[str, str] = {}
    quarantined = 0
    deduplicated = 0
    mag_types: dict[str, int] = {}
    for feature in features:
        if not isinstance(feature, dict):
            quarantined += 1
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            geometry = {}
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            coordinates = []
        longitude = coordinates[0] if len(coordinates) > 0 else None
        latitude = coordinates[1] if len(coordinates) > 1 else None
        reasons = p2.usgs_record_rejection_reasons(
            BELT, latitude, longitude, properties.get("mag"),
            properties.get("time"), min_magnitude=MIN_MAGNITUDE,
        )
        if reasons:
            quarantined += 1
            continue
        event_id = str(feature.get("id") or "")
        if not event_id:
            event_id = "fallback:" + ":".join(str(value) for value in (
                properties.get("time"), properties.get("mag"), longitude, latitude
            ))
        fingerprint = json.dumps(feature, sort_keys=True, separators=(",", ":"))
        if event_id in accepted:
            if accepted[event_id] == fingerprint:
                deduplicated += 1
            else:
                quarantined += 1
            continue
        accepted[event_id] = fingerprint
        mag_type = str(properties.get("magType") or "MISSING")
        mag_types[mag_type] = mag_types.get(mag_type, 0) + 1

    received = len(features)
    accounted = len(accepted) + quarantined + deduplicated
    if received != accounted:
        raise RuntimeError(
            f"USGS accounting mismatch: received={received}, accounted={accounted}"
        )
    if quarantined:
        raise RuntimeError(f"USGS bounded catalog contains {quarantined} quarantined feature(s)")
    if not accepted:
        raise RuntimeError("USGS bounded catalog has no accepted events")

    return {
        "status": "PASS",
        "query_window_utc": [START, END],
        "minimum_magnitude": MIN_MAGNITUDE,
        "raw_sha256": digest,
        "features_received": received,
        "events_accepted": len(accepted),
        "duplicate_features_deduplicated": deduplicated,
        "events_quarantined": quarantined,
        "magnitude_type_counts": dict(sorted(mag_types.items())),
        "accounting_identity": "received=accepted+quarantined+deduplicated",
    }


def main() -> int:
    params = {
        "format": "geojson", "starttime": START, "endtime": END,
        "minmagnitude": MIN_MAGNITUDE,
        "minlatitude": BELT["minlatitude"], "maxlatitude": BELT["maxlatitude"],
        "minlongitude": BELT["minlongitude"], "maxlongitude": BELT["maxlongitude"],
        "orderby": "time-asc", "limit": 500,
    }
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
    raw = p2.get(url, retries=2, timeout=25)
    result = validate_payload(raw)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
