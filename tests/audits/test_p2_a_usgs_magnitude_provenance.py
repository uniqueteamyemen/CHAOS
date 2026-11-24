import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audits import p2_a_usgs_magnitude_provenance as audit


class P2AMagnitudeProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.belt = {
            "id": "test",
            "minlatitude": -10,
            "maxlatitude": 10,
            "minlongitude": 100,
            "maxlongitude": 120,
        }
        self.accepted = {
            "us123": {
                "time": "2020-01-01T00:00:00Z",
                "mag": 5.0,
                "type": "mb",
            }
        }

    def test_csv_requires_mag_source(self):
        good = (
            b"time,latitude,longitude,depth,mag,magType,net,id,magSource\n"
            b"2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
        )
        self.assertEqual(audit.parse_csv(good)[0]["magSource"], "us")
        with self.assertRaisesRegex(ValueError, "USGS_CSV_MAG_SOURCE_FIELD_MISSING"):
            audit.parse_csv(b"time,mag,magType,id\n2020-01-01,5,mb,us123\n")

    def test_fetch_window_records_inclusive_api_bounds(self):
        data = (
            b"time,latitude,longitude,depth,mag,magType,net,id,magSource\n"
            b"2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest = []
            with patch.object(audit.p2, "get", return_value=data):
                rows = audit.fetch_window(
                    self.belt,
                    "2020-01-01T00:00:00",
                    "2021-01-01T00:00:00",
                    Path(directory) / "raw",
                    manifest,
                )
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                manifest[0]["api_boundary_semantics"], "START_AND_END_INCLUSIVE"
            )

    def test_saturated_query_splits(self):
        header = "time,latitude,longitude,depth,mag,magType,net,id,magSource\n"
        first = (
            header
            + "2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
            + "2020-01-02T00:00:00Z,1,2,3,5,mb,us,us124,us\n"
        ).encode()
        left = (
            header + "2020-01-01T00:00:00Z,1,2,3,5,mb,us,us123,us\n"
        ).encode()
        right = (
            header + "2020-01-02T00:00:00Z,1,2,3,5,mb,us,us124,us\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            manifest = []
            with patch.object(audit, "SATURATION", 2), patch.object(
                audit.p2, "get", side_effect=[first, left, right]
            ):
                rows = audit.fetch_window(
                    self.belt,
                    "2020-01-01T00:00:00",
                    "2022-01-01T00:00:00",
                    Path(directory) / "raw",
                    manifest,
                )
            self.assertEqual(len(manifest), 3)
            self.assertEqual(len(rows), 2)

    def test_missing_source_is_unresolved(self):
        rows = [{
            "id": "us123",
            "time": "2020-01-01T00:00:00Z",
            "mag": "5",
            "magType": "mb",
            "magSource": "",
            "net": "us",
        }]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", self.accepted, rows, Path(directory)
            )
        self.assertEqual(
            result["status"], "PARTIAL_MAG_SOURCE_MISSING_REQUIRES_REVIEW"
        )
        self.assertEqual(result["magnitude_source_missing_events"], 1)

    def test_magnitude_type_missing_is_normalized_and_blocked(self):
        accepted = {
            "us123": {
                "time": "2020-01-01T00:00:00Z",
                "mag": 5.0,
                "type": "missing",
            }
        }
        rows = [{
            "id": "us123",
            "time": "2020-01-01T00:00:00Z",
            "mag": "5",
            "magType": "",
            "magSource": "us",
            "net": "us",
        }]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", accepted, rows, Path(directory)
            )
        self.assertEqual(
            result["status"], "MAGNITUDE_TYPE_MISSING_REQUIRES_REVIEW"
        )
        self.assertEqual(result["magnitude_type_missing_events"], 1)
        self.assertEqual(result["magnitude_type_counts"], {"missing": 1})

    def test_mixed_sources_require_stratification(self):
        accepted = {
            "us123": {"time": "2020-01-01T00:00:00Z", "mag": 5.0, "type": "mb"},
            "us124": {"time": "2020-01-02T00:00:00Z", "mag": 5.1, "type": "mb"},
        }
        rows = [
            {"id": "us123", "time": "2020-01-01T00:00:00Z", "mag": "5.0",
             "magType": "mb", "magSource": "us", "net": "us"},
            {"id": "us124", "time": "2020-01-02T00:00:00Z", "mag": "5.1",
             "magType": "mb", "magSource": "ak", "net": "us"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", accepted, rows, Path(directory)
            )
        self.assertEqual(
            result["status"],
            "SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION",
        )

    def test_magnitude_type_mixture_requires_stratification(self):
        accepted = {
            "us123": {"time": "2020-01-01T00:00:00Z", "mag": 5.0, "type": "mb"},
            "us124": {"time": "2020-01-02T00:00:00Z", "mag": 5.1, "type": "mw"},
        }
        rows = [
            {"id": "us123", "time": "2020-01-01T00:00:00Z", "mag": "5.0",
             "magType": "mb", "magSource": "us", "net": "us"},
            {"id": "us124", "time": "2020-01-02T00:00:00Z", "mag": "5.1",
             "magType": "mw", "magSource": "us", "net": "us"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", accepted, rows, Path(directory)
            )
        self.assertEqual(
            result["status"],
            "SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION",
        )

    def test_mismatch_rows_are_not_counted_as_matched_or_written(self):
        rows = [{
            "id": "us123",
            "time": "2020-01-01T00:00:02Z",
            "mag": "5.2",
            "magType": "mw",
            "magSource": "us",
            "net": "us",
        }]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", self.accepted, rows, Path(directory)
            )
            output = Path(directory) / result["output_path"]
            with output.open(encoding="utf-8", newline="") as handle:
                persisted = list(csv.DictReader(handle))
        self.assertEqual(result["status"], "FAIL_RECONCILIATION")
        self.assertEqual(result["matched_events"], 0)
        self.assertEqual(result["rejected_mismatch_event_count"], 1)
        self.assertEqual(persisted, [])
        self.assertEqual(
            {item["reason"] for item in result["mismatches"]},
            {"MAGNITUDE_MISMATCH", "MAG_TYPE_MISMATCH", "ORIGIN_TIME_MISMATCH"},
        )

    def test_extra_query_rows_are_detailed_and_excluded(self):
        rows = [
            {"id": "us123", "time": "2020-01-01T00:00:00Z", "mag": "5.0",
             "magType": "mb", "magSource": "us", "net": "us"},
            {"id": "extra-1", "time": "2020-02-01T00:00:00Z", "mag": "4.9",
             "magType": "mb", "magSource": "ak", "net": "us"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = audit.reconcile(
                "test", self.accepted, rows, Path(directory)
            )
        self.assertEqual(result["matched_events"], 1)
        self.assertEqual(result["extra_query_row_count"], 1)
        self.assertEqual(
            result["extra_query_rows"],
            [{
                "event_id": "extra-1",
                "time": "2020-02-01T00:00:00Z",
                "mag": "4.9",
                "reason": "EVENT_NOT_PRESENT_IN_ACCEPTED_CATALOG",
            }],
        )

    def test_load_inputs_verifies_five_catalogs_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            belts = []
            for index in range(5):
                belt_id = f"belt-{index}"
                path = root / "source_snapshots" / "derived" / f"{belt_id}_events.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "id,time,magnitude,mag_type\n"
                    f"event-{index},2020-01-01T00:00:00Z,5.0,mb\n",
                    encoding="utf-8",
                )
                belts.append({
                    "id": belt_id,
                    "events_accepted": 1,
                    "csv_sha256": audit.digest(path),
                })
            (root / "summary.json").write_text(json.dumps({
                "audit_id": "CHAOS-P2.2.3-DOMAIN-NULL-DECLUSTERING",
                "status": "completed",
                "required_source_gate": {"passed": True},
                "usgs_source_ingestion": {"belts": belts},
            }), encoding="utf-8")
            summary, catalogs, hashes = audit.load_inputs(root)
        self.assertEqual(len(catalogs), 5)
        self.assertEqual(len(hashes), 5)
        self.assertEqual(catalogs["belt-0"]["event-0"]["type"], "mb")
        self.assertEqual(summary["status"], "completed")

    def test_run_appends_six_ledger_records_and_writes_final_summary_once(self):
        fake_belts = [{
            "id": f"belt-{index}",
            "minlatitude": -10,
            "maxlatitude": 10,
            "minlongitude": 100,
            "maxlongitude": 120,
        } for index in range(5)]
        catalogs = {
            belt["id"]: {
                f"event-{index}": {
                    "time": "2020-01-01T00:00:00Z",
                    "mag": 5.0,
                    "type": "mb",
                }
            }
            for index, belt in enumerate(fake_belts)
        }
        rows = [[{
            "id": f"event-{index}",
            "time": "2020-01-01T00:00:00Z",
            "mag": "5.0",
            "magType": "mb",
            "magSource": "us",
            "net": "us",
        }] for index in range(5)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            output_root = root / "out"
            ledger_path = root / "governance" / "RESEARCH_LEDGER_V1.jsonl"
            summary_path = output_root / "P2_A_MAGNITUDE_PROVENANCE_SUMMARY.json"
            original_write_text = Path.write_text
            summary_writes = []

            def tracked_write_text(path, *args, **kwargs):
                if path == summary_path:
                    summary_writes.append(str(path))
                return original_write_text(path, *args, **kwargs)

            with patch.object(audit, "load_inputs", return_value=(
                {"audit_id": "CHAOS-P2.2.3-DOMAIN-NULL-DECLUSTERING",
                 "repository_commit": "source-sha"},
                catalogs,
                {f"belt-{index}": f"hash-{index}" for index in range(5)},
            )), patch.object(audit, "fetch_window", side_effect=rows), patch.object(
                audit.p2, "BELTS", fake_belts
            ), patch.object(Path, "write_text", new=tracked_write_text):
                result = audit.run(
                    source_root, output_root, ledger_path, "run-123", "1"
                )

            records = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
            ]
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(len(records), 6)
        self.assertEqual([record["record_type"] for record in records].count("run"), 1)
        self.assertEqual(
            [record["record_type"] for record in records].count("pattern_decision"),
            5,
        )
        self.assertEqual(result["research_ledger"]["records_in_this_run"], 6)
        self.assertEqual(len(result["research_ledger"]["record_ids"]), 6)
        self.assertEqual(summary["p2_a_mc_gate"], "READY_FOR_Mc_CANDIDATE_ANALYSIS")
        self.assertEqual(len(summary_writes), 1)
        self.assertIn(
            "P2_A_MAGNITUDE_PROVENANCE_SUMMARY.json", records[0]["output_refs"]
        )
        self.assertEqual(summary["research_ledger"]["bytes_after"], ledger_path.stat().st_size)

    def test_contract_decision_states_match_all_reconcile_states(self):
        contract_path = (
            audit.ROOT
            / "real_data_stress_pipeline/contracts/p2_a_magnitude_provenance_recovery_v1.json"
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        expected = {
            "FAIL_RECONCILIATION",
            "PARTIAL_MAG_SOURCE_MISSING_REQUIRES_REVIEW",
            "MAGNITUDE_TYPE_MISSING_REQUIRES_REVIEW",
            "SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION",
            "SOURCE_HOMOGENEOUS_CANDIDATE_PENDING_CALIBRATION",
        }
        self.assertEqual(set(contract["decision_states"]), expected)


if __name__ == "__main__":
    unittest.main()
