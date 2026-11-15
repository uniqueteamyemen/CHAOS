import unittest
from experiments.identity_lab.exp_p_engine_holdout.asymmetry_guarded_cusum import (
    asymmetry_guarded_bounded_cusum, _score_alerts,
)
class AsymmetryGuardedCusumTests(unittest.TestCase):
    def test_defaults_and_determinism(self):
        values=[0.1 if i%2==0 else -0.1 for i in range(40)]+[3.0]*40
        a,d1=asymmetry_guarded_bounded_cusum(values); b,d2=asymmetry_guarded_bounded_cusum(values)
        self.assertEqual(a,b)
        self.assertEqual(d1["effective_parameters"],{"psi_bound":1.8,"gamma":0.9,"k":0.5,"h":9.5,
          "dwell_required":4,"asymmetry_ratio":3.5,"cooldown_steps":6})
        self.assertEqual(d1["rho_raw"],d2["rho_raw"])
    def test_first_difference_scale_not_absorbing_permanent_level_shift(self):
        quiet=[0.1 if i%2==0 else -0.1 for i in range(40)]
        values=quiet+[3.0+(0.1 if i%2==0 else -0.1) for i in range(40)]
        _,diag=asymmetry_guarded_bounded_cusum(values)
        self.assertAlmostEqual(diag["scale_path"][5],diag["scale_path"][30],places=12)
    def test_zero_based_alert_time_and_direction_scoring(self):
        alerts=[{"time":49,"direction":1},{"time":67,"direction":-1},{"time":69,"direction":1}]
        score=_score_alerts(alerts,"positive_step_3sigma")
        self.assertTrue(score["pre_onset_false_alarm"]); self.assertTrue(score["detected"])
        self.assertTrue(score["wrong_direction"]); self.assertEqual(score["delay"],5)
    def test_rejects_invalid_series(self):
        with self.assertRaisesRegex(ValueError,"quiet_window_invalid"):
            asymmetry_guarded_bounded_cusum([1.0,2.0])
        with self.assertRaisesRegex(ValueError,"series_nonfinite"):
            asymmetry_guarded_bounded_cusum([0.1,-0.1,0.2,float("nan"),0.1]*10)
if __name__=="__main__": unittest.main()
