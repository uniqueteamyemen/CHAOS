from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from real_data_stress_pipeline import run_pipeline as p2


class USGSCatalogIntegrityTests(unittest.TestCase):
    BELT = {
        "id": "sunda_andaman_test",
        "name": "Sunda-Andaman test",
        "minlatitude": -15,
        "maxlatitude": 20,
        "minlongitude": 90,
        "maxlongitude": 130,
    }

    @staticmethod
    def epoch(year=2020, month=1, day=1):
        return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)

    def test_accepts_event_within_spatial_magnitude_and_time_bounds(self):
        self.assertEqual(
            p2.usgs_record_rejection_reasons(
                self.BELT, 0.0, 110.0, 5.0, self.epoch(), min_magnitude=4.5
            ),
            [],
        )

    def test_quarantines_out_of_belt_and_below_query_magnitude(self):
        reasons = p2.usgs_record_rejection_reasons(
            self.BELT, 35.5446667, -120.8448333, 3.38, self.epoch(), min_magnitude=4.5
        )
        self.assertIn("OUTSIDE_BELT_LATITUDE_BOUNDS", reasons)
        self.assertIn("OUTSIDE_BELT_LONGITUDE_BOUNDS", reasons)
        self.assertIn("BELOW_QUERY_MINIMUM_MAGNITUDE", reasons)

    def test_rejects_non_finite_coordinates_and_fractional_epoch(self):
        reasons = p2.usgs_record_rejection_reasons(
            self.BELT, float("nan"), 110.0, 5.0, self.epoch() + 0.5, min_magnitude=4.5
        )
        self.assertIn("INVALID_OR_MISSING_COORDINATES", reasons)
        self.assertIn("INVALID_OR_MISSING_EVENT_TIME", reasons)

    def test_rejects_boolean_values_and_out_of_window_event_time(self):
        boolean_time = p2.usgs_record_rejection_reasons(
            self.BELT, 0.0, 110.0, 5.0, True, min_magnitude=4.5
        )
        self.assertIn("INVALID_OR_MISSING_EVENT_TIME", boolean_time)
        outside = p2.usgs_record_rejection_reasons(
            self.BELT, 0.0, 110.0, 5.0, self.epoch(2025), min_magnitude=4.5
        )
        self.assertIn("OUTSIDE_ANALYSIS_TIME_WINDOW", outside)

    def test_longitude_validation_handles_antimeridian_belts(self):
        belt = {
            "minlatitude": 50,
            "maxlatitude": 65,
            "minlongitude": 170,
            "maxlongitude": -170,
        }
        self.assertEqual(
            p2.usgs_record_rejection_reasons(
                belt, 55.0, 179.0, 5.0, self.epoch(), min_magnitude=4.5
            ),
            [],
        )
        self.assertIn(
            "OUTSIDE_BELT_LONGITUDE_BOUNDS",
            p2.usgs_record_rejection_reasons(
                belt, 55.0, 0.0, 5.0, self.epoch(), min_magnitude=4.5
            ),
        )

    def test_ingestion_preserves_raw_payload_and_accounts_for_every_feature(self):
        event_time = self.epoch()
        valid_mb = {
            "type": "Feature",
            "id": "valid-mb",
            "properties": {
                "time": event_time,
                "mag": 5.1,
                "magType": "mb",
                "magSource": "us",
                "place": "Sunda test",
            },
            "geometry": {"type": "Point", "coordinates": [110.0, 0.0, 10.0]},
        }
        valid_mww = {
            "type": "Feature",
            "id": "valid-mww",
            "properties": {
                "time": event_time + 86_400_000,
                "mag": 5.2,
                "magType": "mww",
                "magSource": "ak",
                "place": "Sunda second test",
            },
            "geometry": {"type": "Point", "coordinates": [111.0, 1.0, 12.0]},
        }
        identical_duplicate = json.loads(json.dumps(valid_mb))
        conflicting_duplicate = json.loads(json.dumps(valid_mb))
        conflicting_duplicate["properties"]["mag"] = 5.3
        conflicting_duplicate["properties"]["time"] = event_time + 2 * 86_400_000
        contaminated = {
            "type": "Feature",
            "id": "california-contamination",
            "properties": {
                "time": event_time,
                "mag": 3.38,
                "magType": "mb",
                "magSource": "ci",
                "place": "California, outside the test belt",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-120.8448333, 35.5446667, 8.0],
            },
        }
        payload = json.dumps({
            "type": "FeatureCollection",
            "features": [
                valid_mb,
                valid_mww,
                identical_duplicate,
                conflicting_duplicate,
                contaminated,
            ],
        }).encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            derived_root = root / "derived"
            metadata = {"belts": [], "sources": [], "rejected": [], "errors": []}
            with (
                patch.object(p2, "ROOT", root),
                patch.object(p2, "RAW", raw_root),
                patch.object(p2, "DERIVED", derived_root),
                patch.object(p2, "BELTS", [self.BELT]),
                patch.object(p2, "get", return_value=payload),
            ):
                p2.seismic(metadata)

            catalog_path = derived_root / "sunda_andaman_test_events.csv"
            with catalog_path.open("r", encoding="utf-8", newline="") as handle:
                accepted = list(csv.DictReader(handle))

            raw_files = list(raw_root.rglob("*.geojson"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), payload)
            self.assertEqual(
                metadata["sources"][0]["sha256"],
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertEqual({row["id"] for row in accepted}, {"valid-mb", "valid-mww"})
            self.assertEqual({row["mag_type"] for row in accepted}, {"mb", "mww"})
            self.assertEqual({row["mag_source"] for row in accepted}, {"us", "ak"})

            ingestion = metadata["belts"][0]
            self.assertEqual(ingestion["events_received"], 5)
            self.assertEqual(ingestion["events_accepted"], 2)
            self.assertEqual(ingestion["events_quarantined"], 2)
            self.assertEqual(ingestion["duplicate_features_deduplicated"], 1)
            self.assertEqual(
                ingestion["events_received"],
                ingestion["events_accepted"]
                + ingestion["events_quarantined"]
                + ingestion["duplicate_features_deduplicated"],
            )
            self.assertEqual(ingestion["catalog_integrity_status"], "PASS_WITH_QUARANTINE")
            self.assertEqual(ingestion["magnitude_type_counts"], {"mb": 1, "mww": 1})
            self.assertFalse(ingestion["magnitude_type_homogeneous"])
            self.assertTrue(ingestion["magnitude_source_mixture_requires_calibration_review"])

            reasons = {
                reason
                for record in metadata["rejected"]
                for reason in record.get("reasons", [])
            }
            self.assertIn("DUPLICATE_EVENT_ID_CONFLICT", reasons)
            self.assertIn("OUTSIDE_BELT_LONGITUDE_BOUNDS", reasons)
            self.assertIn("BELOW_QUERY_MINIMUM_MAGNITUDE", reasons)

    def test_conflicting_event_id_is_not_silently_overwritten(self):
        event_time = self.epoch()
        first = {
            "id": "same-id",
            "properties": {"time": event_time, "mag": 5.0},
            "geometry": {"coordinates": [110.0, 0.0, 5.0]},
        }
        conflicting = {
            "id": "same-id",
            "properties": {"time": event_time + 1000, "mag": 5.1},
            "geometry": {"coordinates": [111.0, 1.0, 6.0]},
        }
        payload = json.dumps({"features": [first, conflicting]}).encode("utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata = {"belts": [], "sources": [], "rejected": [], "errors": []}
            with (
                patch.object(p2, "ROOT", root),
                patch.object(p2, "RAW", root / "raw"),
                patch.object(p2, "DERIVED", root / "derived"),
                patch.object(p2, "BELTS", [self.BELT]),
                patch.object(p2, "get", return_value=payload),
            ):
                p2.seismic(metadata)
        self.assertEqual(metadata["belts"][0]["events_accepted"], 1)
        self.assertEqual(metadata["belts"][0]["events_quarantined"], 1)
        self.assertEqual(
            metadata["rejected"][0]["reasons"],
            ["DUPLICATE_EVENT_ID_CONFLICT"],
        )


if __name__ == "__main__":
    unittest.main()
