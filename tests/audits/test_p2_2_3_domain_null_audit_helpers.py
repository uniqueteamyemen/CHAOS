import unittest
from datetime import datetime, timezone
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from scripts.audits.p2_2_3_domain_null_and_declustering import (
    contiguous_transformed_series,
    fetch_eia,
    fetch_fred,
    homogeneous_poisson_fit_diagnostics,
    load_world_bank_gem_snapshot,
    parse_world_bank_page,
    required_source_gate,
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

    def test_required_source_gate_rejects_missing_gem(self):
        usgs = {"status": "COMPLETED", "errors": []}
        belts = [{"source_events": 1} for _ in range(5)]
        gate = required_source_gate(
            {"status": "ERROR", "indicators": []},
            usgs,
            belts,
        )
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["world_bank_gem"])
        self.assertTrue(gate["usgs_comcat"])
        self.assertTrue(gate["five_seismic_belts"])

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
