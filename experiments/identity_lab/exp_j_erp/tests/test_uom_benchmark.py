"""Independent tests for benchmark-only UoM normalization."""
import unittest

from reconcile_benchmark import classify
from uom import convert


class UomConversionTests(unittest.TestCase):
    def test_two_dozen_to_units(self):
        self.assertEqual(convert(2, "dozen", "unit"), (24.0, "ok"))

    def test_one_and_half_kg_to_grams(self):
        self.assertEqual(convert(1.5, "kg", "g"), (1500.0, "ok"))

    def test_weight_is_not_count(self):
        value, reason = convert(1, "kg", "unit")
        self.assertIsNone(value)
        self.assertTrue(reason.startswith("uom_category_mismatch:"))

    def test_reverse_weight_conversion(self):
        self.assertEqual(convert(1000, "g", "kg"), (1.0, "ok"))

    def test_classify_uses_product_reference_category_and_audit_values(self):
        edges = [
            {"transfer_id": "COUNT-1", "product": "count-product", "qty_out": 24},
            {"transfer_id": "WEIGHT-1", "product": "weight-product", "qty_out": 1.5},
        ]
        results = [
            {"edge": "COUNT-1", "state": "confirmed",
             "receipt": {"counterpart_qty": 2, "counterpart_uom": "dozen"}},
            {"edge": "WEIGHT-1", "state": "confirmed",
             "receipt": {"counterpart_qty": 1500, "counterpart_uom": "g"}},
        ]
        summary = classify(results, edges, {
            "count-product": "unit", "weight-product": "kg"
        })
        self.assertEqual(len(summary["confirmed_loss"]), 0)
        self.assertEqual(summary["confirmed"], 2)

    def test_classify_rejects_cross_category_conversion(self):
        edges = [{"transfer_id": "X", "product": "count-product", "qty_out": 10}]
        results = [{"edge": "X", "state": "confirmed",
                    "receipt": {"counterpart_qty": 1, "counterpart_uom": "kg"}}]
        summary = classify(results, edges, {"count-product": "unit"})
        self.assertEqual(summary["ambiguous"], 1)
        self.assertEqual(summary["confirmed"], 0)


if __name__ == "__main__":
    unittest.main()
