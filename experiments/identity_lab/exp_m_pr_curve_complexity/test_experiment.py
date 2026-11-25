import unittest
from .experiment import build_window_dataset, score_window, build_complexity_case, UOMS
try:
 from ..exp_j_erp.reconcile import match_counterpart_receipts
except ImportError:
 from exp_j_erp.reconcile import match_counterpart_receipts

class TemporalCurveTests(unittest.TestCase):
 def test_dataset_and_determinism(self):
  d=build_window_dataset(); self.assertEqual(len(d["shipments"]),70); self.assertEqual(len(d["truth"]),70)
  self.assertEqual(score_window(d,3),score_window(d,3))
 def test_metrics_denominators_and_bounds(self):
  d=build_window_dataset()
  for w in range(11):
   r=score_window(d,w); self.assertEqual(r["tp"]+r["fn"],70)
   self.assertTrue(0<=r["precision"]<=1); self.assertTrue(0<=r["resolved_recall"]<=1)
   self.assertGreaterEqual(r["candidate_recall"],r["resolved_recall"])
 def test_approximate_never_confirms_loss(self):
  d=build_window_dataset()
  for w in range(11):
   rows=match_counterpart_receipts(d["shipments"],d["receipts"],UOMS,date_window_days=w)
   self.assertTrue(all(not x["confirmed"] for x in rows))
   self.assertTrue(all("loss" not in x.get("issues",[]) for x in rows))
class ConcurrentUomTests(unittest.TestCase):
 def test_overlapping_shipments_and_categories(self):
  r=build_complexity_case(); self.assertEqual(len(r["movements"]),5)
  self.assertEqual({x["uom_category_id"] for x in r["movements"]},{"weight","count"})
 def test_unlinked_receipts_stay_unconfirmed(self):
  r=build_complexity_case(); self.assertTrue(all(not x["confirmed"] for x in r["receipt_matches"]))
if __name__=="__main__": unittest.main()
