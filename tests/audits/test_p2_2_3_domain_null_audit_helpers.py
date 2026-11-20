import unittest
from datetime import datetime, timezone
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
import csv
from unittest.mock import patch

from real_data_stress_pipeline import run_pipeline as p2
from real_data_stress_pipeline.run_pipeline import usgs_record_rejection_reasons

from scripts.audits.p2_2_3_domain_null_and_declustering import (
    contiguous_transformed_series,
    fetch_eia,
    fetch_fred,
    homogeneous_poisson_fit_diagnostics,
    load_world_bank_gem_snapshot,
    parse_world_bank_page,
    required_source_gate,
    validate_usgs_belt_catalog,
    WB_INDICATORS,
    redact_secret_payload,
)


class DomainNullAuditHelperTests(unittest.TestCase):
    def test_world_bank_page_parser_rejects_malformed_payload(self):
        with self.assertRaises(ValueError):
            parse_world_bank_page(b'{"not":"the expected api shape"}')

    def test_world_bank_page_parser_accepts_metadata_and_records(self):
        payload = [
            {"page": 1, "pages": 2},
            [{"countryiso3code": "USA", "date": "2024M01", "value": 100.0}],
        ]
        meta, rows = parse_world_bank_page(json.dumps(payload).encode("utf-8"))
        self.assertEqual(meta["pages"], 2)
        self.assertEqual(rows[0]["countryiso3code"], "USA")

    def test_monthly_transform_does_not_fill_missing_months(self):
        mapping = {
            1990 * 12: 10.0,
            1990 * 12 + 1: 11.0,
            1990 * 12 + 3: 13.0,
            1990 * 12 + 4: 14.0,
        }
        axis, values = contiguous_transformed_series(mapping, "log_difference")
        self.assertEqual(axis, ["1990-02"])
        self.assertEqual(len(values), 1)
        self.assertAlmostEqual(values[0], np.log(1.1), places=12)

    def test_secret_redaction_preserves_source_hash_inputs_without_storing_secret(self):
        original = b'{"api_key":"sensitive-test-token","value":12}'
        stored, redacted = redact_secret_payload(original, "sensitive-test-token")
        self.assertTrue(redacted)
        self.assertNotIn(b"sensitive-test-token", stored)
        self.assertIn(b"[REDACTED]", stored)
        unchanged, unchanged_flag = redact_secret_payload(b'{"value":12}', "sensitive-test-token")
        self.assertEqual(unchanged, b'{"value":12}')
        self.assertFalse(unchanged_flag)

    def test_fred_and_eia_are_optional_without_secrets(self):
        self.assertEqual(fetch_fred(None, None)["status"], "SKIPPED_SECRET_MISSING")
        self.assertEqual(fetch_eia(None, None)["status"], "SKIPPED_SECRET_MISSING")


    def test_p2_2_1_gem_snapshot_is_loaded_only_after_manifest_and_page_hash_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_dir = root / "artifacts/real_data_stress/raw/world_bank/gem"
            raw_dir.mkdir(parents=True)
            indicators = []
            for code in sorted(WB_INDICATORS):
                payload = [
                    {"page": 1, "pages": 1, "per_page": 20000, "total": 1},
                    [{
                        "countryiso3code": "USA",
                        "country": {"id": "USA", "value": "United States"},
                        "date": "1990M01",
                        "value": 100.0,
                    }],
                ]
                raw = json.dumps(payload).encode("utf-8")
                (raw_dir / f"{code}_page_001.json").write_bytes(raw)
                indicators.append({
                    "code": code,
                    "raw_hashes": [hashlib.sha256(raw).hexdigest()],
                })

            manifest_dir = root / "real_data_stress_pipeline/results"
            manifest_dir.mkdir(parents=True)
            manifest = {
                "git_commit": "verified-source-commit",
                "run_timestamp_utc": "2026-11-18T00:00:00+00:00",
                "gem_config": {
                    "world_bank_source_id": 15,
                    "period_window": "1990M01:2023M12",
                },
                "gem_indicators": indicators,
            }
            (manifest_dir / "real_data_stress_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            pages, hashes, page_counts, source = load_world_bank_gem_snapshot(
                root, root / "audit"
            )
            self.assertEqual(set(pages), set(WB_INDICATORS))
            self.assertEqual(set(page_counts.values()), {1})
            self.assertEqual(source["source_repository_commit"], "verified-source-commit")
            self.assertEqual(source["pages_verified"], len(WB_INDICATORS))
            self.assertEqual(len(hashes), len(WB_INDICATORS))

            damaged = raw_dir / f"{sorted(WB_INDICATORS)[0]}_page_001.json"
            damaged.write_bytes(b'{"tampered":true}')
            with self.assertRaisesRegex(ValueError, "sha256_mismatch"):
                load_world_bank_gem_snapshot(root, root / "audit_retry")

    def test_usgs_seismic_ingestion_preserves_raw_and_quarantines_contamination(self):
        belt = {
            "id": "sunda_andaman_test",
            "name": "Sunda-Andaman test",
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        valid_epoch = int(datetime(2004, 5, 18, tzinfo=timezone.utc).timestamp() * 1000)
        invalid_epoch = int(datetime(2004, 5, 17, 21, 41, 12, tzinfo=timezone.utc).timestamp() * 1000)
        payload = json.dumps({
            "features": [
                {
                    "id": "valid-sunda-event",
                    "properties": {"time": valid_epoch, "mag": 5.1, "place": "Sunda test"},
                    "geometry": {"coordinates": [110.0, 0.0, 10.0]},
                },
                {
                    "id": "nc21364840",
                    "properties": {"time": invalid_epoch, "mag": 3.38, "place": "12 km NNE of Cayucos, California"},
                    "geometry": {"coordinates": [-120.8448333, 35.5446667, 8.0]},
                },
            ]
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
                patch.object(p2, "BELTS", [belt]),
                patch.object(p2, "get", return_value=payload),
            ):
                p2.seismic(metadata)

            catalog_path = derived_root / "sunda_andaman_test_events.csv"
            with catalog_path.open("r", encoding="utf-8", newline="") as handle:
                accepted = list(csv.DictReader(handle))
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0]["id"], "valid-sunda-event")

            raw_files = list(raw_root.rglob("*.geojson"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), payload)
            self.assertEqual(metadata["sources"][0]["sha256"], hashlib.sha256(payload).hexdigest())

            ingestion = metadata["belts"][0]
            self.assertEqual(ingestion["events_received"], 2)
            self.assertEqual(ingestion["events_accepted"], 1)
            self.assertEqual(ingestion["events_quarantined"], 1)
            self.assertEqual(ingestion["duplicate_features_deduplicated"], 0)
            self.assertEqual(ingestion["catalog_integrity_status"], "PASS_WITH_QUARANTINE")
            anomaly = next(row for row in metadata["rejected"] if row.get("event_id") == "nc21364840")
            self.assertIn("OUTSIDE_BELT_LONGITUDE_BOUNDS", anomaly["reasons"])
            self.assertIn("BELOW_QUERY_MINIMUM_MAGNITUDE", anomaly["reasons"])

    def test_usgs_catalog_accepts_event_inside_belt_and_source_window(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        epoch_ms = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(
            usgs_record_rejection_reasons(
                belt, 0.0, 110.0, 4.5, epoch_ms, min_magnitude=4.5
            ),
            [],
        )

    def test_usgs_catalog_quarantines_geographic_and_magnitude_contamination(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        epoch_ms = int(datetime(2004, 5, 17, tzinfo=timezone.utc).timestamp() * 1000)
        reasons = usgs_record_rejection_reasons(
            belt, 35.5446667, -120.8448333, 3.38, epoch_ms, min_magnitude=4.5
        )
        self.assertIn("OUTSIDE_BELT_LATITUDE_BOUNDS", reasons)
        self.assertIn("OUTSIDE_BELT_LONGITUDE_BOUNDS", reasons)
        self.assertIn("BELOW_QUERY_MINIMUM_MAGNITUDE", reasons)

    def test_usgs_catalog_rejects_invalid_coordinates_and_time_outside_window(self):
        belt = {
            "minlatitude": 30, "maxlatitude": 42,
            "minlongitude": 18, "maxlongitude": 35,
        }
        outside_epoch = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        reasons = usgs_record_rejection_reasons(
            belt, float("nan"), 200.0, 5.0, outside_epoch, min_magnitude=4.5
        )
        self.assertIn("INVALID_OR_MISSING_COORDINATES", reasons)
        self.assertIn("OUTSIDE_ANALYSIS_TIME_WINDOW", reasons)

    def test_usgs_catalog_rejects_fractional_epoch_milliseconds(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        reasons = usgs_record_rejection_reasons(
            belt, 0.0, 110.0, 5.0, 946684800000.5, min_magnitude=4.5
        )
        self.assertIn("INVALID_OR_MISSING_EVENT_TIME", reasons)

    def test_usgs_longitude_validation_supports_antimeridian_belts(self):
        belt = {
            "minlatitude": 50, "maxlatitude": 65,
            "minlongitude": 170, "maxlongitude": -170,
        }
        epoch_ms = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(
            usgs_record_rejection_reasons(
                belt, 55.0, 179.0, 5.0, epoch_ms, min_magnitude=4.5
            ),
            [],
        )
        self.assertIn(
            "OUTSIDE_BELT_LONGITUDE_BOUNDS",
            usgs_record_rejection_reasons(
                belt, 55.0, -130.0, 5.0, epoch_ms, min_magnitude=4.5
            ),
        )

    def test_required_source_gate_rejects_missing_gem_but_reports_valid_usgs_integrity(self):
        usgs = {"status": "COMPLETED", "errors": []}
        belts = [
            {
                "source_events": 1,
                "catalog_integrity": {
                    "status": "PASS",
                    "post_ingest_validation_status": "PASS",
                    "accounting_reconciled": True,
                },
            }
            for _ in range(5)
        ]
        gate = required_source_gate(
            {"status": "ERROR", "indicators": []},
            usgs,
            belts,
        )
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["world_bank_gem"])
        self.assertTrue(gate["usgs_comcat"])
        self.assertTrue(gate["five_seismic_belts"])
        self.assertTrue(gate["usgs_catalog_integrity"])

    def test_required_source_gate_rejects_unvalidated_usgs_catalogs(self):
        usgs = {"status": "COMPLETED", "errors": []}
        belts = [
            {
                "source_events": 1,
                "catalog_integrity": {
                    "status": "FAIL",
                    "post_ingest_validation_status": "FAIL",
                    "accounting_reconciled": False,
                },
            }
            for _ in range(5)
        ]
        gate = required_source_gate(
            {"status": "REUSED_VERIFIED_SNAPSHOT", "indicators": [
                {"indicator": code, "status": "REUSED_VERIFIED_SNAPSHOT"}
                for code in WB_INDICATORS
            ]},
            usgs,
            belts,
        )
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["usgs_catalog_integrity"])

    def test_post_ingest_catalog_validation_accepts_reconciled_clean_catalog(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        epoch_ms = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        events = [{
            "id": "event-1", "latitude": 0.0, "longitude": 110.0,
            "magnitude": 5.0, "epoch_ms": epoch_ms,
        }]
        ingestion = {
            "events_received": 1, "events_accepted": 1,
            "events_quarantined": 0, "duplicate_features_deduplicated": 0,
            "catalog_integrity_status": "PASS",
        }
        result = validate_usgs_belt_catalog(belt, events, ingestion)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["accounting_reconciled"])
        self.assertEqual(result["post_ingest_rejected_events"], [])

    def test_post_ingest_catalog_validation_fails_closed_on_outside_event(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        epoch_ms = int(datetime(2004, 5, 17, tzinfo=timezone.utc).timestamp() * 1000)
        events = [{
            "id": "nc21364840", "latitude": 35.5446667,
            "longitude": -120.8448333, "magnitude": 3.38,
            "epoch_ms": epoch_ms,
        }]
        ingestion = {
            "events_received": 1, "events_accepted": 1,
            "events_quarantined": 0, "duplicate_features_deduplicated": 0,
            "catalog_integrity_status": "PASS",
        }
        result = validate_usgs_belt_catalog(belt, events, ingestion)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["post_ingest_validation_status"], "FAIL")
        self.assertIn(
            "OUTSIDE_BELT_LONGITUDE_BOUNDS",
            result["post_ingest_rejected_events"][0]["reasons"],
        )

    def test_post_ingest_catalog_validation_fails_on_accounting_mismatch(self):
        belt = {
            "minlatitude": -15, "maxlatitude": 20,
            "minlongitude": 90, "maxlongitude": 130,
        }
        epoch_ms = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        events = [{
            "id": "event-1", "latitude": 0.0, "longitude": 110.0,
            "magnitude": 5.0, "epoch_ms": epoch_ms,
        }]
        ingestion = {
            "events_received": 4, "events_accepted": 1,
            "events_quarantined": 1, "duplicate_features_deduplicated": 1,
            "catalog_integrity_status": "PASS_WITH_QUARANTINE",
        }
        result = validate_usgs_belt_catalog(belt, events, ingestion)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["accounting_reconciled"])

    def test_poisson_diagnostics_are_explicitly_benchmark_only(self):
        counts = np.asarray([0, 1, 0, 2, 1, 0, 0, 1, 2, 0, 1, 0], dtype=np.int64)
        events = [
            {
                "epoch_ms": int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
                + index * 86400000,
            }
            for index in range(8)
        ]
        result = homogeneous_poisson_fit_diagnostics(counts, events)
        self.assertEqual(
            result["homogeneous_poisson_status"],
            "BENCHMARK_ONLY_NOT_VALIDATED",
        )
        self.assertNotIn("FPR", json.dumps(result))
        self.assertEqual(result["catalog_completeness_status"], "NOT_ASSESSED")
        self.assertFalse(result["inferential_goodness_of_fit_p_values_reported"])
        self.assertNotIn("monthly_count_dispersion_two_sided_p", result)
        if result["inter_event_exponential_ks"] is not None:
            self.assertNotIn("p_value", result["inter_event_exponential_ks"])


if __name__ == "__main__":
    unittest.main()
