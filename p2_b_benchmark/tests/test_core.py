import random
import unittest
import numpy as np
from p2_b_benchmark.engine import (
    BASELINE_MODES, VARIANTS, _EXTENSION_RUNNERS, audit_parallel_prefix_invariance,
    normalize_detector_key, register_detector, run_baseline, run_parallel_fusion,
    run_registered_detector,
)

class ParallelFusionCausalityTests(unittest.TestCase):
    @staticmethod
    def series(n=160,seed=44):
        rng=random.Random(seed); values=[rng.gauss(0.0,1.0) for _ in range(n)]
        for i in range(95,n): values[i]+=3.0
        return np.asarray(values,dtype=float)

    def test_registered_arms_and_break_detector_modes(self):
        self.assertEqual(set(BASELINE_MODES),{"A_FAST","A_MARKOV_CUSUM","A_CONSENSUS"})
        needed=set(BASELINE_MODES)|{"G","H","J","K","I"}
        self.assertTrue(needed.issubset(VARIANTS))
        self.assertEqual(BASELINE_MODES["A_MARKOV_CUSUM"],"markov_cusum")
        self.assertEqual(VARIANTS["G"]["transition"],"reset")
        self.assertEqual(VARIANTS["H"]["h"],12.5)
        self.assertEqual(VARIANTS["J"]["h"],14.5)
        self.assertEqual(VARIANTS["K"]["h"],15.5)
        self.assertEqual(VARIANTS["I"]["h"],16.5)

    def test_future_suffix_mutation_preserves_prefix_hits_and_events(self):
        values=self.series()
        for arm in ("G","H","J","K","I"):
            self.assertEqual(audit_parallel_prefix_invariance(values,arm),0,arm)

    def test_two_sided_cusum_detects_both_directions(self):
        pos=self.series(); neg=self.series(); pos[95:]+=5.0; neg[95:]-=5.0
        self.assertTrue(any(h["sign"]>0 for h in run_parallel_fusion(pos,variant="H")["hits"]))
        self.assertTrue(any(h["sign"]<0 for h in run_parallel_fusion(neg,variant="H")["hits"]))

    def test_invalid_series_fails_closed(self):
        with self.assertRaises(ValueError): run_parallel_fusion([0.0]*20,variant="G")
        with self.assertRaises(ValueError): run_parallel_fusion([0.0]*100+[float("nan")],variant="G")

    def test_future_detector_names_fit_extension_registry_contract(self):
        expected={"FOCuS":"FOCUS","R-FPOP":"R_FPOP","BOCPD":"BOCPD",
                  "Post-Quiet Huber":"POST_QUIET_HUBER","Bartlett LRV":"BARTLETT_LRV"}
        for name,key in expected.items(): self.assertEqual(normalize_detector_key(name),key)

    def test_registered_extension_runs_and_prefix_replays(self):
        def runner(values):
            if values.size and values[-1]>=3.0:
                return {"hits":[{"index":int(values.size-1),"sign":1,"detector":"stub"}]}
            return {"hits":[]}
        key=register_detector("P2B_TEST_STUB",runner,family="test",version="1",description="test adapter")
        try:
            values=np.zeros(80); values[-1]=3.0
            result=run_registered_detector(values,key,causal_audit=True)
            self.assertEqual(result["event_count"],1)
            self.assertEqual(result["causal_audit_violations"],0)
            self.assertEqual(VARIANTS[key]["kind"],"extension")
        finally:
            VARIANTS.pop(key,None); _EXTENSION_RUNNERS.pop(key,None)

    def test_registered_extension_prefix_audit_detects_lookahead(self):
        def runner(values):
            if values.size>60 and values[60]>2.0:
                return {"hits":[{"index":50,"sign":1,"detector":"lookahead"}]}
            return {"hits":[]}
        key=register_detector("P2B_LOOKAHEAD_STUB",runner,family="test",version="1",description="lookahead stub")
        try:
            values=np.zeros(80); values[60]=3.0
            self.assertEqual(run_registered_detector(values,key,causal_audit=True)["causal_audit_violations"],1)
        finally:
            VARIANTS.pop(key,None); _EXTENSION_RUNNERS.pop(key,None)

    def test_frozen_break_detector_modes_replay_from_prefix(self):
        try:
            import structural_engine.isolated_break_detector_v1
        except ModuleNotFoundError as exc:
            if exc.name not in {"structural_engine","structural_engine.isolated_break_detector_v1"}: raise
            self.skipTest("P2-B package-only workspace: frozen BreakDetectorV1 source is not checked out")
        result=run_baseline(self.series(n=140),causal_audit=True)
        for arm in BASELINE_MODES:
            self.assertIsInstance(result[arm]["causal_audit_violations"],int,arm)

if __name__=="__main__": unittest.main()
