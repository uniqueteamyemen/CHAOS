import unittest
import numpy as np
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import SurgicalFactorEngineB61
from experiments.identity_lab.exp_sequential_break_b62_sign_flip_guard.engine_b62 import DriftConditionalSignFlipEngineB62
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import CASES, N, ONSET, generate_series

class B62SignFlipGuardTests(unittest.TestCase):
    def test_no_guard_matches_D1P1G0_event_for_event(self):
        for i,(name,dist,rho,vjump,shift) in enumerate(CASES):
            seq=generate_series(np.random.default_rng(1_400_000+i),dist=dist,rho=rho,var_jump=vjump,shift_sigma=shift,n=N,onset=ONSET)
            a=SurgicalFactorEngineB61(innovation_drain=True,persistence_floor=True,heuristic_scale_guard=False).analyze(seq)
            b=DriftConditionalSignFlipEngineB62(innovation_drain=True,persistence_floor=True,sign_flip_guard=False,sign_flip_threshold=8).analyze(seq)
            for key in ("structural_breaks","transient_anomalies","unresolved_alerts","pending_lifecycle"):
                self.assertEqual(b[key],a[key],msg=f"{name}:{key}")

    def test_monotone_window_zero_flips(self):
        self.assertEqual(DriftConditionalSignFlipEngineB62._count_sign_flips(np.arange(12)),0)

    def test_alternating_window_ten_flips(self):
        self.assertEqual(DriftConditionalSignFlipEngineB62._count_sign_flips(np.array([0,1]*6)),10)

    def test_zero_differences_are_ignored(self):
        x=np.array([0,1,1,2,2,3,3,4,4,5,5,6],dtype=float)
        self.assertEqual(DriftConditionalSignFlipEngineB62._count_sign_flips(x),0)

    def test_guard_activates_at_eight_not_seven(self):
        e=DriftConditionalSignFlipEngineB62(sign_flip_guard=True,sign_flip_threshold=8)
        seven=np.array([0,1,0,1,0,1,0,1,0,0,0,0],dtype=float)
        eight=np.array([0,1,0,1,0,1,0,1,0,1,1,1],dtype=float)
        s7,f7,a7=e._apply_sign_flip_guard(2.0,0.7,seven)
        s8,f8,a8=e._apply_sign_flip_guard(2.0,0.7,eight)
        self.assertEqual(f7,7); self.assertFalse(a7); self.assertEqual(s7,2.0)
        self.assertEqual(f8,8); self.assertTrue(a8); self.assertAlmostEqual(s8,2.35)

    def test_guard_off_identity(self):
        e=DriftConditionalSignFlipEngineB62(sign_flip_guard=False)
        s,f,a=e._apply_sign_flip_guard(2.0,0.7,np.array([0,1]*6))
        self.assertEqual(f,10); self.assertFalse(a); self.assertEqual(s,2.0)

    def test_step_jump_can_be_followed_by_noisy_sign_reversals(self):
        x=np.array([0,.02,-.01,.01,3,3.02,2.99,3.01,2.98,3.02,2.99,3.01])
        f=DriftConditionalSignFlipEngineB62._count_sign_flips(x)
        self.assertGreater(f,0); self.assertLessEqual(f,10)

    def test_threshold_validation(self):
        for x in (-1,11,8.5,True):
            with self.subTest(x=x):
                with self.assertRaises(ValueError): DriftConditionalSignFlipEngineB62(sign_flip_threshold=x)

    def test_guard_flag_type_validation(self):
        with self.assertRaises(ValueError): DriftConditionalSignFlipEngineB62(sign_flip_guard=1)

    def test_lifecycle_accounting(self):
        x=np.random.default_rng(8832).standard_t(df=3,size=140)
        r=DriftConditionalSignFlipEngineB62(innovation_drain=True,persistence_floor=True,sign_flip_guard=True).analyze(x)
        p=r["pending_lifecycle"]
        self.assertTrue(p["accounting_complete"])
        self.assertEqual(p["opened_count"],p["resolved_structural_count"]+p["resolved_transient_count"]+p["unresolved_count"])

    def test_diagnostics_report_guard_activation(self):
        x=np.random.default_rng(19).normal(size=140)
        d=DriftConditionalSignFlipEngineB62(innovation_drain=True,persistence_floor=True,sign_flip_guard=True).analyze(x)["diagnostics"]
        self.assertGreater(d["sign_flip_windows_evaluated"],0)
        self.assertIn("sign_flip_guard_activation_pct",d)
        self.assertIn("mean_sign_flip_count",d)

if __name__=="__main__": unittest.main()
