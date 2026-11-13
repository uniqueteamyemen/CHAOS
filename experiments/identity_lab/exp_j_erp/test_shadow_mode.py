import copy
import tempfile
import unittest
from pathlib import Path

from experiments.identity_lab.exp_j_erp.shadow_mode import run_shadow, write_run

UOMS = [
    {"id":"unit","category_id":"count","factor":"1","uom_type":"reference"},
    {"id":"dozen","category_id":"count","factor":"0.0833333333333333333333333333","uom_type":"bigger"},
    {"id":"kg","category_id":"weight","factor":"1","uom_type":"reference"},
    {"id":"g","category_id":"weight","factor":"1000","uom_type":"smaller"},
]

def bundle():
    moves = [
        {"id":1,"picking_id":"OUT-1","product_id":"P1","quantity":"12","product_uom_qty":"12",
         "product_uom":"unit","product_uom_category_id":"count","state":"done",
         "location_id":"WH","location_dest_id":"SHOP","date":"2025-01-01","reference":"OUT-1"},
        {"id":2,"picking_id":"OUT-2","product_id":"P2","quantity":"1","product_uom_qty":"1",
         "product_uom":"kg","product_uom_category_id":"weight","state":"done",
         "location_id":"WH","location_dest_id":"SHOP-2","date":"2025-01-01","reference":"OUT-2"},
    ]
    receipts = [
        {"source_picking_id":"OUT-1","counterpart_picking_id":"IN-1","product_id":"P1",
         "location_id":"SHOP","from_entity":"WH","counterpart_qty":"1","counterpart_uom_id":"dozen",
         "product_uom_category_id":"count","counterpart_date":"2025-01-02",
         "counterpart_system":"receiver","counterpart_source":"signed_receipt","recorded_at":"2025-01-02T10:00:00Z"},
        {"source_picking_id":"OUT-2","counterpart_picking_id":"IN-2","product_id":"P2",
         "location_id":"SHOP-2","from_entity":"WH","counterpart_qty":"1000","counterpart_uom_id":"g",
         "product_uom_category_id":"weight","counterpart_date":"2025-01-02",
         "counterpart_system":"receiver","counterpart_source":"signed_receipt","recorded_at":"2025-01-02T10:00:00Z"},
    ]
    return {"schema_version":"1.0","export_metadata":{"source":"synthetic_test_fixture"},
            "moves":moves,"uom_rows":UOMS,"receipts":receipts}

class ShadowModeTests(unittest.TestCase):
    def test_three_engines_run_on_same_immutable_snapshot(self):
        source = bundle()
        before = copy.deepcopy(source)
        report = run_shadow(source)
        self.assertEqual(source, before)
        self.assertEqual(set(report["results"]), {"A","B","C"})
        self.assertEqual(report["snapshot"]["moves"], 2)
        self.assertEqual(report["snapshot"]["receipts"], 2)
        self.assertEqual(report["guardrails"]["writes_to_odoo"], False)
        self.assertEqual(report["guardrails"]["odoo_connection_used"], False)

    def test_count_and_weight_categories_normalize_independently(self):
        report = run_shadow(bundle())
        for engine in ("A","B","C"):
            self.assertTrue(report["results"][engine]["OUT-1"]["confirmed"], engine)
            self.assertTrue(report["results"][engine]["OUT-2"]["confirmed"], engine)
            self.assertEqual(report["results"][engine]["OUT-1"]["loss_claim"], False)
            self.assertEqual(report["results"][engine]["OUT-2"]["loss_claim"], False)

    def test_snapshot_hash_is_deterministic(self):
        one = run_shadow(bundle())
        two = run_shadow(bundle())
        self.assertEqual(one["snapshot"]["sha256"], two["snapshot"]["sha256"])

    def test_invalid_bundle_fails_closed(self):
        with self.assertRaises(ValueError):
            run_shadow({"moves":[],"uom_rows":[]})

    def test_report_writer_creates_a_new_run_directory(self):
        report = run_shadow(bundle())
        with tempfile.TemporaryDirectory() as tmp:
            folder = write_run(report, Path(tmp))
            self.assertTrue((folder/"shadow_report.json").is_file())
            self.assertTrue((folder/"comparison.md").is_file())
            self.assertTrue((folder/"manifest.json").is_file())
            manifest = (folder/"manifest.json").read_text(encoding="utf-8")
            self.assertIn('"writes_to_odoo": false', manifest)

if __name__ == "__main__":
    unittest.main()
