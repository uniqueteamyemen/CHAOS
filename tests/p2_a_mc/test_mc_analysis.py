import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from p2_a_mc import mc_analysis as mc

class McEstimatorTests(unittest.TestCase):
 def test_insufficient_sample_returns_no_mc(self):
  r=mc.estimate_mc([4.5,4.6,4.7,4.8]*5)
  self.assertEqual(r["status"],"INSUFFICIENT_EVENTS"); self.assertIsNone(r["mc_estimate"])
 def test_gft_rejects_candidate_with_fewer_than_four_magnitude_bins(self):
  values=[4.5]*5+[4.6]*5+[5.7]*100+[5.8]*20+[5.9]*10
  result=mc.estimate_mc(values)
  self.assertEqual(result["max_curvature_mc"],5.7)
  self.assertEqual(result["status"],"GFT_NOT_PASSED")
  self.assertIsNone(result["gft_mc"])
 def test_magnitude_rounding_uses_decimal_half_up(self):
  self.assertEqual(mc.round_magnitude(4.45),4.5)
  self.assertEqual(mc.round_magnitude(4.55),4.6)
  self.assertEqual(mc.round_magnitude(4.65),4.7)
 def test_synthetic_gr_curve_returns_point_estimate(self):
  values=[]
  for m,n in [(4.5,250),(4.6,180),(4.7,130),(4.8,95),(4.9,70),(5.0,52),(5.1,38),(5.2,27),(5.3,20),(5.4,14),(5.5,10),(5.6,7),(5.7,5),(5.8,4),(5.9,3),(6.0,2)]:
   values.extend([m]*n)
  r=mc.estimate_mc(values)
  self.assertIsNotNone(r["mc_estimate"]); self.assertGreaterEqual(r["mc_estimate"],4.5)
  self.assertGreaterEqual(r["gft_fit_percent_at_mc"],90.0)
 def test_query_floor_is_not_asserted_complete(self):
  r={"mc_estimate":4.5,"boundary_censored_at_query_floor":True}
  gates=mc.sensitivity([{"magnitude":4.5},{"magnitude":5.0}],r)
  self.assertEqual(gates[0]["threshold_gate"],"UNRESOLVED_LEFT_TRUNCATED_AT_QUERY_FLOOR")
  self.assertEqual(gates[1]["threshold_gate"],"CANDIDATE_ABOVE_CATALOG_FLOOR_NOT_CERTIFIED")
 def test_thresholds_are_count_sensitivity_not_reestimated_mc(self):
  r={"mc_estimate":5.0,"boundary_censored_at_query_floor":False}
  gates=mc.sensitivity([{"magnitude":4.5},{"magnitude":5.0},{"magnitude":5.5},{"magnitude":6.0}],r)
  self.assertEqual([x["events_retained"] for x in gates],[4,3,2,1])
  self.assertTrue(all(x["threshold_is_not_an_mc_estimate"] for x in gates))
  self.assertEqual(gates[0]["threshold_gate"],"NOT_SUPPORTED_BELOW_ESTIMATED_MC")
 def test_five_year_windows_cover_1980_to_2024(self):
  w=mc.windows(1980,2024)
  self.assertEqual(len(w),9); self.assertEqual(w[0],{"start_year":1980,"end_year_exclusive":1985})
  self.assertEqual(w[-1],{"start_year":2020,"end_year_exclusive":2025})
  for a,b in zip(w,w[1:]): self.assertEqual(a["end_year_exclusive"],b["start_year"])
 def test_event_weighted_rollups_reconcile_and_report_real_event_counts(self):
  strata=[
   {"event_count":10,"mc":{"status":"ESTIMATED_PENDING_REVIEW"},"threshold_sensitivity":[{"events_retained":10,"threshold_gate":"CANDIDATE"}]*4},
   {"event_count":20,"mc":{"status":"GFT_NOT_PASSED"},"threshold_sensitivity":[{"events_retained":12,"threshold_gate":"UNRESOLVED"}]*4},
   {"event_count":5,"mc":{"status":"INSUFFICIENT_EVENTS"},"threshold_sensitivity":[{"events_retained":5,"threshold_gate":"UNRESOLVED"}]*4},
  ]
  statuses=mc.event_weighted_mc_status_rollup(strata,35)
  self.assertEqual(statuses["events_accounted_for"],35)
  event_counts={x["mc_status"]:x["events"] for x in statuses["statuses"]}
  self.assertEqual(event_counts["ESTIMATED_PENDING_REVIEW"],10)
  self.assertEqual(event_counts["GFT_NOT_PASSED"],20)
  self.assertEqual(event_counts["INSUFFICIENT_EVENTS"],5)
  threshold=mc.threshold_event_gate_rollup(strata,35)[0]
  gates={x["threshold_gate"]:x for x in threshold["gate_event_distribution"]}
  self.assertEqual(gates["CANDIDATE"]["events_retained"],10)
  self.assertEqual(gates["UNRESOLVED"]["events_retained"],17)
  self.assertAlmostEqual(sum(x["event_share_of_population"] for x in threshold["gate_event_distribution"]),27/35)
 def test_known_exclusion_is_explicitly_documented(self):
  self.assertEqual(mc.KNOWN_EXCLUSION["event_id"],"nc21364840")
  self.assertEqual(mc.KNOWN_EXCLUSION["associated_merged_event_id"],"nc40157006")
  self.assertIn("do not re-fetch",mc.KNOWN_EXCLUSION["handling"].lower())

class McContractTests(unittest.TestCase):
 def test_contract_is_strict_and_scoped(self):
  c=json.loads((ROOT/"p2_a_mc/mc_assessment_contract_v1.json").read_text())
  self.assertEqual(c["scope"]["stratification"],["belt","mag_source","mag_type","five_year_utc_window"])
  self.assertEqual(c["query_truncation"]["threshold_sensitivity"],[4.5,5.0,5.5,6.0])
  self.assertFalse(c["query_truncation"]["mc_below_4_5_estimable"])
  self.assertIn("N1_inhomogeneous_Poisson_fit",c["explicit_non_goals"])
  self.assertIn("N2_Hawkes_ETAS_fit",c["explicit_non_goals"])
  self.assertEqual(c["known_exclusions"][0]["event_id"],"nc21364840")
  self.assertFalse(c["known_exclusions"][0]["re_fetch"])

if __name__=="__main__": unittest.main()
