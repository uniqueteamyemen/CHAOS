import unittest
from datetime import datetime, timezone
import json

import numpy as np

from scripts.audits.p2_2_3_domain_null_and_declustering import (
    contiguous_transformed_series,
    fetch_eia,
    fetch_fred,
    homogeneous_poisson_fit_diagnostics,
    parse_world_bank_page,
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
