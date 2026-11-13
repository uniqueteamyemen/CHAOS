"""Independent tests for unit conversion and the isolated DeepSeek scorer."""
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / "deepseek_source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(HERE))

from uom import convert
from reconcile_benchmark import classify


class UomBenchmarkTests(unittest.TestCase):
    def test_two_dozen_equals_24_units(self):
        self.assertEqual(convert(2, "dozen", "unit"), (24.0, "ok"))

    def test_one_point_five_kg_equals_1500_g(self):
        self.assertEqual(convert(1.5, "kg", "g"), (1500.0, "ok"))

    def test_1000_g_equals_one_kg(self):
        self.assertEqual(convert(1000, "g", "kg"), (1.0, "ok"))

    def test_weight_cannot_convert_to_count(self):
        value, reason = convert(1, "kg", "unit")
        self.assertIsNone(value)
        self.assertTrue(reason.startswith("uom_category_mismatch:"))

    def test_unknown_unit_is_rejected(self):
        value, reason = convert(1, "carton", "unit")
        self.assertIsNone(value)
        self.assertTrue(reason.startswith("unknown_uom:"))

    def test_product_specific_normalization_and_original_audit(self):
        edges = [
            {"transfer_id": "COUNT", "product": "p-count", "qty_out": 24.0},
            {"transfer_id": "WEIGHT", "product": "p-weight", "qty_out": 1.5},
        ]
        results = [
            {"edge": "COUNT", "state": "confirmed",
             "receipt": {"counterpart_qty": 2, "counterpart_uom": "dozen"}},
            {"edge": "WEIGHT", "state": "confirmed",
             "receipt": {"counterpart_qty": 1500, "counterpart_uom": "g"}},
        ]
        out = classify(results, edges, {"p-count": "unit", "p-weight": "kg"})
        self.assertEqual(out["confirmed"], 2)
        self.assertEqual(out["confirmed_loss"], [])
        self.assertEqual(out["uom_audit"][0]["quantity_original"], 2)
        self.assertEqual(out["uom_audit"][0]["unit_original"], "dozen")
        self.assertEqual(out["uom_audit"][0]["quantity_normalized"], 24.0)
        self.assertEqual(out["uom_audit"][1]["quantity_original"], 1500)
        self.assertEqual(out["uom_audit"][1]["unit_original"], "g")
        self.assertEqual(out["uom_audit"][1]["quantity_normalized"], 1.5)

    def test_cross_category_scorer_result_is_ambiguous(self):
        edges = [{"transfer_id": "X", "product": "count-product", "qty_out": 10}]
        results = [{"edge": "X", "state": "confirmed",
                    "receipt": {"counterpart_qty": 1, "counterpart_uom": "kg"}}]
        out = classify(results, edges, {"count-product": "unit"})
        self.assertEqual(out["ambiguous"], 1)
        self.assertEqual(out["confirmed"], 0)
        self.assertTrue(out["uom_audit"][0]["normalization"].startswith(
            "uom_category_mismatch:"))

    def test_original_half_unit_loss_threshold_is_preserved(self):
        edges = [{"transfer_id": "T", "product": "p", "qty_out": 100.0}]
        exactly_half = [{"edge": "T", "state": "confirmed",
                         "receipt": {"counterpart_qty": 99.5, "counterpart_uom": "unit"}}]
        above_half = [{"edge": "T", "state": "confirmed",
                       "receipt": {"counterpart_qty": 99.49, "counterpart_uom": "unit"}}]
        self.assertEqual(classify(exactly_half, edges, {"p": "unit"})["confirmed_loss"], [])
        self.assertEqual(len(classify(above_half, edges, {"p": "unit"})["confirmed_loss"]), 1)


if __name__ == "__main__":
    unittest.main()
