import random
import unittest

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

from p2_b_benchmark.run import _aggregate, _one_series, _score_all


class ParallelFusionCausalityTests(unittest.TestCase):
    @staticmethod
    def series(n=160, seed=44):
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(n)]
        for i in range(95, n):
            values[i] += 3.0
        return np.asarray(values, dtype=float)

    def test_registered_arms_and_break_detector_modes(self):
        self.assertEqual(set(BASELINE_MODES), {"A_FAST", "A_MARKOV_CUSUM", "A_CONSENSUS"})
        required_arms = set(BASELINE_MODES) | {"G", "H", "J", "K", "I"}
        self.assertTrue(required_arms.issubset(VARIANTS))
        self.assertEqual(BASELINE_MODES["A_MARKOV_CUSUM"], "markov_cusum")
        self.assertEqual(VARIANTS["G"]["transition"], "reset")
        self.assertEqual(VARIANTS["H"]["h"], 12.5)
        self.assertEqual(VARIANTS["J"]["h"], 14.5)
        self.assertEqual(VARIANTS["K"]["h"], 15.5)
        self.assertEqual(VARIANTS["I"]["h"], 16.5)
        self.assertTrue(all(VARIANTS[arm]["kind"] == "parallel_fusion" for arm in ("G", "H", "J", "K", "I")))

    def test_future_suffix_mutation_preserves_prefix_hits_and_events(self):
        values = self.series()
        for arm in ("G", "H", "J", "K", "I"):
            self.assertEqual(audit_parallel_prefix_invariance(values, arm), 0, arm)

    def test_two_sided_cusum_detects_both_directions(self):
        positive = self.series()
        negative = self.series()
        positive[95:] += 5.0
        negative[95:] -= 5.0
        self.assertTrue(any(hit["sign"] > 0 for hit in run_parallel_fusion(positive, variant="H")["hits"]))
        self.assertTrue(any(hit["sign"] < 0 for hit in run_parallel_fusion(negative, variant="H")["hits"]))

    def test_invalid_series_fails_closed(self):
        with self.assertRaises(ValueError):
            run_parallel_fusion([0.0] * 20, variant="G")
        with self.assertRaises(ValueError):
            run_parallel_fusion([0.0] * 100 + [float("nan")], variant="G")

    def test_future_detector_names_fit_extension_registry_contract(self):
        expected = {
            "FOCuS": "FOCUS",
            "R-FPOP": "R_FPOP",
            "BOCPD": "BOCPD",
            "Post-Quiet Huber": "POST_QUIET_HUBER",
            "Bartlett LRV": "BARTLETT_LRV",
        }
        for display_name, key in expected.items():
            self.assertEqual(normalize_detector_key(display_name), key)

    def test_registered_extension_runs_and_prefix_replays(self):
        def stub_runner(values):
            if values.size and values[-1] >= 3.0:
                return {"hits": [{"index": int(values.size - 1), "sign": 1, "detector": "stub"}]}
            return {"hits": []}

        key = register_detector(
            "P2B_TEST_STUB", stub_runner, family="test", version="1",
            description="test-only extension adapter",
        )
        try:
            values = np.zeros(80, dtype=float)
            values[-1] = 3.0
            result = run_registered_detector(values, key, causal_audit=True)
            self.assertEqual(result["event_count"], 1)
            self.assertEqual(result["causal_audit_violations"], 0)
            self.assertEqual(VARIANTS[key]["kind"], "extension")
        finally:
            VARIANTS.pop(key, None)
            _EXTENSION_RUNNERS.pop(key, None)

    def test_registered_extension_prefix_audit_detects_lookahead(self):
        def lookahead_runner(values):
            if values.size > 60 and values[60] > 2.0:
                return {"hits": [{"index": 50, "sign": 1, "detector": "lookahead_stub"}]}
            return {"hits": []}

        key = register_detector(
            "P2B_LOOKAHEAD_STUB", lookahead_runner, family="test", version="1",
            description="must fail prefix replay because its hit depends on the future",
        )
        try:
            values = np.zeros(80, dtype=float)
            values[60] = 3.0
            result = run_registered_detector(values, key, causal_audit=True)
            self.assertEqual(result["causal_audit_violations"], 1)
        finally:
            VARIANTS.pop(key, None)
            _EXTENSION_RUNNERS.pop(key, None)

    def test_signals_never_emit_inside_the_quiet_window(self):
        values = self.series(n=160)
        result = run_parallel_fusion(values, variant="H", quiet_points=40)
        self.assertTrue(all(hit["index"] >= 40 for hit in result["hits"]))
        self.assertTrue(all(event["start_index"] >= 40 for event in result["events"]))

    def test_zero_quiet_scale_is_explicit_abstention(self):
        values = np.zeros(100, dtype=float)
        parallel = run_parallel_fusion(values, variant="H")
        self.assertEqual(parallel["status"], "ABSTAIN")
        self.assertEqual(parallel["abstain_reason"], "ZERO_QUIET_SCALE")
        self.assertEqual(parallel["hits"], [])
        all_arms = run_all(values, causal_audit=True)
        self.assertTrue(all(payload["status"] == "ABSTAIN" for payload in all_arms.values()))
        self.assertTrue(all(payload["abstain_reason"] == "ZERO_QUIET_SCALE" for payload in all_arms.values()))

    def test_zero_quiet_scale_series_and_bootstrap_replicates_are_recorded_as_abstentions(self):
        item = {
            "id": "synthetic:flat",
            "source": "gem",
            "values": np.zeros(100, dtype=float),
            "bootstrap_eligible": True,
        }
        row = _one_series(item, null_replicates=3)
        self.assertEqual(row["observed_status"], "ABSTAIN")
        self.assertEqual(row["abstain_reason"], "ZERO_QUIET_SCALE")
        for arm in VARIANTS:
            self.assertEqual(row["null"][arm]["valid_replicates"], 0)
            self.assertEqual(row["null"][arm]["abstained_replicates"], 3)
            self.assertIsNone(row["null"][arm]["conditional_alarm_probability"])
            self.assertEqual(row["injected"][arm]["positive_3sigma"]["status"], "ABSTAIN")
        summary = _aggregate([row], null_replicates=3)
        self.assertEqual(summary["null"]["H"]["all"]["replicates_abstained_zero_quiet_scale"], 3)
        self.assertEqual(summary["injected"]["H"]["positive_3sigma"]["all"]["abstained_zero_quiet_scale_series"], 1)
        self.assertEqual(summary["observed"]["H"]["all"]["abstained_zero_quiet_scale_series"], 1)

    def test_score_all_counts_quiet_to_onset_alert_and_rejects_prestarted_event(self):
        result = {
            "A_BASELINE": {"hits": [{"time": 45, "direction": 1}, {"time": 73, "direction": 1}]},
            "H": {"hits": [
                {"index": 45, "sign": 1, "detector": "cusum_positive"},
                {"index": 73, "sign": 1, "detector": "cusum_positive"}],
                "events": [{"start_index": 45, "end_index": 73, "sign": 1, "evidence": [
                    {"index": 45, "sign": 1, "detector": "cusum_positive"},
                    {"index": 73, "sign": 1, "detector": "cusum_positive"}]}]},
            "J": {"hits": [{"index": 73, "sign": 1, "detector": "cusum_positive"}],
                "events": [{"start_index": 72, "end_index": 73, "sign": 1, "evidence": [
                    {"index": 73, "sign": 1, "detector": "cusum_positive"}]}]},
        }
        scored = _score_all(result, onset=70, sign=1, quiet_points=40)
        self.assertTrue(scored["A_BASELINE"]["pre_onset_alert"])
        self.assertTrue(scored["A_BASELINE"]["detected"])
        self.assertTrue(scored["H"]["pre_onset_alert"])
        self.assertFalse(scored["H"]["detected"], "post-onset hit cannot validate an event that started pre-onset")
        self.assertFalse(scored["J"]["pre_onset_alert"])
        self.assertTrue(scored["J"]["detected"])

    def test_frozen_break_detector_modes_replay_from_prefix(self):
        try:
            import structural_engine.isolated_break_detector_v1  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name not in {"structural_engine", "structural_engine.isolated_break_detector_v1"}:
                raise
            self.skipTest("P2-B package-only workspace: frozen BreakDetectorV1 source is not checked out")
        result = run_baseline(self.series(n=140), causal_audit=True)
        for arm in BASELINE_MODES:
            self.assertEqual(result[arm]["causal_audit_violations"], 0, arm)


if __name__ == "__main__":
    unittest.main()
