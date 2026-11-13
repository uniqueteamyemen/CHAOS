"""Unit and regression tests for the isolated UoM-corrected DeepSeek scorer."""
import sys
from pathlib import Path
import unittest

ERP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ERP_DIR))

from reconcile_benchmark import classify
from uom import convert


class UomConversionTests(unittest.TestCase):
    def test_two_dozen_to_units(self):
        self.assertEqual(convert(2, "dozen", "unit"), (24.0, "ok"))

    def test_one_and_half_kg_to_grams(self):
        self.assertEqual(convert(1.5, "kg", "g"), (1500.0, "ok"))

    def test_one_thousand_grams_to_one_kg(self):
        self.assertEqual(convert(1000, "g", "kg"), (1.0, "ok"))

    def test_weight_is_not_count(self):
        value, reason = convert(1, "kg", "unit")
        self.assertIsNone(value)
        self.assertTrue(reason.startswith("uom_category_mismatch:"))

    def test_unknown_unit_is_rejected(self):
        value, reason = convert(2, "box", "unit")
        self.assertIsNone(value)
        self.assertTrue(reason.startswith("unknown_uom:"))

    def test_each_product_uses_its_own_reference_category(self):
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
        self.assertEqual(summary["confirmed"], 2)
        self.assertEqual(summary["confirmed_loss"], [])
        self.assertEqual(summary["uom_audit"][0]["quantity_original"], 2)
        self.assertEqual(summary["uom_audit"][0]["unit_original"], "dozen")
        self.assertEqual(summary["uom_audit"][0]["quantity_normalized"], 24.0)
        self.assertEqual(summary["uom_audit"][1]["quantity_original"], 1500)
        self.assertEqual(summary["uom_audit"][1]["unit_original"], "g")
        self.assertEqual(summary["uom_audit"][1]["quantity_normalized"], 1.5)

    def test_cross_category_conversion_becomes_ambiguous(self):
        edges = [{"transfer_id": "X", "product": "count-product", "qty_out": 10}]
        results = [{"edge": "X", "state": "confirmed",
                    "receipt": {"counterpart_qty": 1, "counterpart_uom": "kg"}}]
        summary = classify(results, edges, {"count-product": "unit"})
        self.assertEqual(summary["ambiguous"], 1)
        self.assertEqual(summary["confirmed"], 0)
        self.assertTrue(summary["uom_audit"][0]["normalization"].startswith(
            "uom_category_mismatch:"))

    def test_two_percent_relative_loss_boundary(self):
        edges = [{"transfer_id": "T", "product": "p", "qty_out": 100.0}]
        exact_at_boundary = [{"edge": "T", "state": "confirmed",
                              "receipt": {"counterpart_qty": 98.0, "counterpart_uom": "unit"}}]
        above_boundary = [{"edge": "T", "state": "confirmed",
                           "receipt": {"counterpart_qty": 97.99, "counterpart_uom": "unit"}}]
        ref = {"p": "unit"}
        self.assertEqual(classify(exact_at_boundary, edges, ref)["confirmed_loss"], [])
        self.assertEqual(len(classify(above_boundary, edges, ref)["confirmed_loss"]), 1)


if __name__ == "__main__":
    unittest.main()
