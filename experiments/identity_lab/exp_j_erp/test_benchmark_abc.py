import unittest
from experiments.identity_lab.exp_j_erp.benchmark_abc import make_cases, legacy_a, legacy_a_normalized, score
from experiments.identity_lab.exp_j_erp.reconcile import match_counterpart_receipts
from experiments.identity_lab.exp_j_erp.hybrid_reconcile import match_hybrid
from experiments.identity_lab.exp_j_erp.benchmark_abc import UOMS, normalize_b, normalize_c, LOSS_THRESHOLD
from decimal import Decimal

class ComparativeBenchmarkTests(unittest.TestCase):
    def test_deterministic_seeded_ground_truth(self):
        a = make_cases(7)
        b = make_cases(7)
        self.assertEqual(a, b)
        self.assertEqual(len(a[0]), 18)

    def test_all_three_engines_receive_same_seeded_input(self):
        shipments, receipts, truth = make_cases(3)
        a = legacy_a(shipments, receipts)
        b = match_counterpart_receipts(shipments, receipts, UOMS,
            date_window_days=3, quantity_tolerance=Decimal("0.2"))
        c = match_hybrid(shipments, receipts, UOMS, date_window_days=3,
            candidate_quantity_tolerance_relative=Decimal("0.02"),
            reconciliation_quantity_tolerance=Decimal("0.01"),
            loss_classification_threshold=LOSS_THRESHOLD)
        self.assertEqual(len(a), len(shipments))
        self.assertEqual(len(b), len(shipments))
        self.assertEqual(len(c), len(shipments))
        self.assertEqual(set(legacy_a_normalized(a)), set(truth))
        unlinked = {str(r["counterpart_picking_id"]) for r in receipts
                    if not r.get("source_picking_id") and r.get("counterpart_picking_id")}
        self.assertEqual(set(normalize_b(b, unlinked)), set(truth))
        self.assertEqual(set(normalize_c(c, unlinked)), set(truth))

    def test_hybrid_never_claims_loss_for_approximate_candidate(self):
        shipments, receipts, truth = make_cases(11)
        unlinked = {str(r["counterpart_picking_id"]) for r in receipts
                    if not r.get("source_picking_id") and r.get("counterpart_picking_id")}
        out = normalize_c(match_hybrid(shipments, receipts, UOMS), unlinked)
        for sid, expected in truth.items():
            if not expected["exact"]:
                self.assertFalse(out[sid]["loss_claim"], sid)

    def test_report_generation(self):
        from experiments.identity_lab.exp_j_erp.benchmark_abc import run
        result = run()
        self.assertEqual(result["total_shipment_cases"], 720)
        self.assertIn("A", result["summary"])
        self.assertIn("B", result["summary"])
        self.assertIn("C", result["summary"])

if __name__ == "__main__":
    unittest.main()
