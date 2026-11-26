"""Unit tests for unique-series, point-in-time C3 v2 source intake."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from p1_4_validation.c3 import alfred_first_release_intake as intake


class C3V2SourceIntakeTests(unittest.TestCase):
    def test_expanded_intake_extracts_first_non_missing_release_without_event_duplication(self):
        series = {
            "series_id": "TEST",
            "observation_start": "2020-01-01",
            "observation_end": "2020-02-01",
            "vintage_search_start": "2019-11-01",
            "vintage_search_end": "2020-04-01",
            "expected_alfred_release_start": "2019-01-01",
            "frequency": "Monthly",
            "units": "units",
            "minimum_observation_count": 2,
        }
        payload = (
            "observation_date,TEST_20200102,TEST_20200203\n"
            "2020-01-01,1.0,1.1\n"
            "2020-02-01,.,2.0\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(intake, "fetch_vintage_dates",
                           return_value=["2020-01-02", "2020-02-03"]), \
             patch.object(intake, "_http_get", return_value=payload), \
             patch.object(intake.time, "sleep"):
            records, batches = intake.fetch_series_initial_releases(series, Path(directory))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["available_at"], "2020-01-02")
        self.assertEqual(records[1]["available_at"], "2020-02-03")
        self.assertEqual(records[1]["value"], "2")
        self.assertTrue(all("event_id" not in row for row in records))
        self.assertEqual(len(batches), 1)

    def test_write_intake_accepts_one_series_mapped_to_multiple_events(self):
        contract = {
            "contract_id": "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1",
            "contract_version": "1.0.0",
            "events": [
                {"event_id": "EV_A", "expected_sign_by_series": {"TEST": 1}},
                {"event_id": "EV_B", "expected_sign_by_series": {"TEST": -1}},
            ],
            "series": [{
                "series_id": "TEST",
                "observation_start": "2020-01-01",
                "observation_end": "2020-02-01",
            }],
            "frozen_references": {"shock_event_contract_git_blob": "frozen-test-blob"},
            "guardrails": {"initial_release_values_only": True},
            "intake_output": {
                "normalized_file": "expanded_initial_release_tape.csv",
                "manifest_file": "expanded_source_intake_manifest.json",
            },
        }
        records = [
            {
                "series_id": "TEST", "observation_date": "2020-01-01",
                "available_at": "2020-01-02", "value": "1",
                "frequency": "Monthly", "units": "units",
                "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
            },
            {
                "series_id": "TEST", "observation_date": "2020-02-01",
                "available_at": "2020-02-03", "value": "2",
                "frequency": "Monthly", "units": "units",
                "value_semantics": "FIRST_ALFRED_VINTAGE_VALUE",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = root / "contract.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with patch.object(intake, "fetch_series_initial_releases",
                              return_value=(records, [])):
                manifest = intake.write_intake(contract_path, root / "output")
            self.assertEqual(manifest["event_count"], 2)
            self.assertEqual(manifest["series_count"], 1)
            self.assertEqual(manifest["event_series_pair_count"], 2)
            self.assertEqual(manifest["point_count"], 2)
            tape = (root / "output/expanded_initial_release_tape.csv").read_text()
            self.assertNotIn("event_id", tape.splitlines()[0])
            self.assertEqual(tape.count("TEST,"), 2)


if __name__ == "__main__":
    unittest.main()
