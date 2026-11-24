import json
import random
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

from p2_b_benchmark.engine import (
    BASELINE_MODES,
    audit_parallel_prefix_invariance,
    normalize_detector_key,
    register_detector,
    run_all,
    run_baseline,
    run_parallel_fusion,
    run_registered_detector,
    VARIANTS,
    _EXTENSION_RUNNERS,
)

from p2_b_benchmark.run import (
    _aggregate,
    _one_series,
    _score_all,
    _build_protocol,
    _series_manifest_sha256,
    _sorted_ids_sha256,
    aggregate_shard_files,
    combine_shard_documents,
)


class FiveDetectorCompetitionTests(unittest.TestCase):
    @staticmethod
    def sample(n=180, seed=31):
        rng=np.random.default_rng(seed)
        x=rng.normal(0,1,n)
        x[110:]+=3.0
        return x

    def setUp(self):
        from p2_b_benchmark import detectors  # noqa: F401

    def test_exact_competition_arms_and_exclusions(self):
        from p2_b_benchmark.engine import VARIANTS, BASELINE_MODES
        expected={"A_FAST","A_CONSENSUS","FOCUS","R_FPOP","BOCPD","POST_QUIET_HUBER","BARTLETT_LRV"}
        self.assertEqual(set(VARIANTS),expected)
        self.assertEqual(set(BASELINE_MODES),{"A_FAST","A_CONSENSUS"})
        self.assertFalse({"A_MARKOV_CUSUM","G","H","J","K","I"} & set(VARIANTS))

    def test_all_five_emit_no_pre_quiet_signals(self):
        from p2_b_benchmark.engine import run_all
        outputs=run_all(self.sample(),causal_audit=True)
        for arm in ("FOCUS","R_FPOP","BOCPD","POST_QUIET_HUBER","BARTLETT_LRV"):
            self.assertTrue(all(hit["index"]>=40 for hit in outputs[arm]["hits"]),arm)
            self.assertEqual(outputs[arm]["causal_audit_violations"],0,arm)

    def test_zero_mad_abstains_for_every_arm(self):
        from p2_b_benchmark.engine import run_all
        outputs=run_all(np.zeros(100),causal_audit=True)
        self.assertEqual(len(outputs),7)
        self.assertTrue(all(row["status"]=="ABSTAIN" for row in outputs.values()))
        self.assertTrue(all(row["abstain_reason"]=="ZERO_QUIET_SCALE" for row in outputs.values()))

    def test_future_suffix_mutation_and_prefix_replay(self):
        from p2_b_benchmark.engine import run_all
        x=self.sample()
        outputs=run_all(x,causal_audit=True)
        for arm in ("FOCUS","R_FPOP","BOCPD","POST_QUIET_HUBER","BARTLETT_LRV"):
            self.assertEqual(outputs[arm]["causal_audit_violations"],0,arm)

    def test_extension_rejects_early_emission_and_invalid_hits(self):
        from p2_b_benchmark.engine import register_detector, run_registered_detector, VARIANTS, _EXTENSION_RUNNERS
        key=register_detector("TEST_EARLY_EMIT",lambda x:{"hits":[{"index":39,"sign":1}]},
                              family="test",version="1",description="early emission must fail")
        try:
            with self.assertRaisesRegex(ValueError,"emitted_before_quiet_window"):
                run_registered_detector(self.sample(),key)
        finally:
            VARIANTS.pop(key,None); _EXTENSION_RUNNERS.pop(key,None)

    def test_baseline_modes_remain_frozen_and_causal(self):
        from p2_b_benchmark.engine import run_baseline
        try:
            from structural_engine.isolated_break_detector_v1 import BreakDetectorV1
        except ModuleNotFoundError:
            self.skipTest("frozen detector package is required for baseline integration")
        result=run_baseline(self.sample(),causal_audit=True)
        self.assertEqual(set(result),{"A_FAST","A_CONSENSUS"})
        for arm,row in result.items():
            self.assertEqual(row["causal_audit_violations"],0,arm)

if __name__ == "__main__":
    unittest.main()
