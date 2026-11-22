import json
import unittest
from datetime import datetime, timezone

from scripts.guards.p2_bounded_usgs_gate import validate_payload


class BoundedUSGSGateTests(unittest.TestCase):
    @staticmethod
    def event(event_id="usgs-test", mag=6.2):
        epoch = int(datetime(2024, 1, 10, tzinfo=timezone.utc).timestamp() * 1000)
        return {
            "type": "Feature",
            "id": event_id,
            "properties": {"time": epoch, "mag": mag, "magType": "mww"},
            "geometry": {"type": "Point", "coordinates": [120.0, 10.0, 20.0]},
        }

    def test_valid_real_shape_catalog_is_accepted_and_hashed(self):
        result = validate_payload(json.dumps({"features": [self.event()]}).encode())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["events_accepted"], 1)
        self.assertEqual(len(result["raw_sha256"]), 64)

    def test_identical_duplicate_is_accounted_without_double_counting(self):
        event = self.event()
        result = validate_payload(json.dumps({"features": [event, event]}).encode())
        self.assertEqual(result["features_received"], 2)
        self.assertEqual(result["events_accepted"], 1)
        self.assertEqual(result["duplicate_features_deduplicated"], 1)

    def test_out_of_range_feature_fails_closed(self):
        event = self.event()
        event["geometry"]["coordinates"] = [250.0, 10.0, 20.0]
        with self.assertRaisesRegex(RuntimeError, "quarantined"):
            validate_payload(json.dumps({"features": [event]}).encode())

    def test_empty_catalog_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "no feature list"):
            validate_payload(b'{"features": []}')


if __name__ == "__main__":
    unittest.main()
