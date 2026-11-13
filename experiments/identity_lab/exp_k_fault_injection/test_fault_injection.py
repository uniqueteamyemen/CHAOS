from copy import deepcopy
from datetime import date, timedelta
import unittest

from .fault_injection import (
    build_clean_export, canonical_hash, inject_faults, run_export, run_experiment,
)


class FaultInjectionTests(unittest.TestCase):
    def test_clean_baseline_is_all_exact(self):
        export = build_clean_export(100)
        result = run_export(export)
        self.assertEqual(result["states"]["exact"], 100)
        self.assertEqual(result["confirmed_losses"], 0)
        self.assertEqual(result["confirmed_delays"], 0)

    def test_ten_percent_fault_buckets_are_detected_as_states_not_false_losses(self):
        result = run_experiment(100, 0.10, 0.10, 0.10, 20261113)
        self.assertTrue(result["baseline_unchanged_after_injection"])
        self.assertEqual(result["baseline_result"]["states"]["exact"], 100)
        self.assertEqual(result["mutated_result"]["states"]["exact"], 70)
        self.assertEqual(result["mutated_result"]["states"]["ambiguous"], 10)
        self.assertEqual(result["mutated_result"]["states"]["unmatched"], 20)
        self.assertEqual(result["mutated_result"]["confirmed_losses"], 0)
        self.assertEqual(result["mutated_result"]["false_loss_candidates_from_unconfirmed"], 0)

    def test_unique_approximate_candidate_is_not_confirmed(self):
        export = build_clean_export(1)
        export["receipts"][0].pop("source_picking_id")
        result = run_export(export)
        self.assertEqual(result["states"]["approximate_unique"], 1)
        self.assertEqual(result["confirmed_losses"], 0)

    def test_exact_late_receipt_is_delay_not_unmatched(self):
        export = build_clean_export(1)
        shipment_date = date.fromisoformat(export["moves"][0]["date"])
        export["receipts"][0]["counterpart_date"] = (shipment_date + timedelta(days=8)).isoformat()
        result = run_export(export)
        self.assertEqual(result["states"]["exact"], 1)
        self.assertEqual(result["confirmed_delays"], 1)

    def test_exact_quantity_difference_can_create_loss(self):
        export = build_clean_export(1)
        export["receipts"][0]["counterpart_qty"] = "8"
        result = run_export(export)
        self.assertEqual(result["confirmed_losses"], 1)

    def test_injection_is_reproducible_and_does_not_mutate_baseline(self):
        source = build_clean_export(100)
        before = canonical_hash(source)
        first, manifest_a = inject_faults(source, seed=42)
        second, manifest_b = inject_faults(source, seed=42)
        self.assertEqual(canonical_hash(first), canonical_hash(second))
        self.assertEqual(manifest_a, manifest_b)
        self.assertEqual(canonical_hash(source), before)

    def test_invalid_fault_rates_are_rejected(self):
        with self.assertRaises(ValueError):
            inject_faults(build_clean_export(10), missing_rate=0.8, duplicate_rate=0.2, delayed_rate=0.1)


if __name__ == "__main__":
    unittest.main()
