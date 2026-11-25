from __future__ import annotations

import math
import time
import unittest

import numpy as np

from p2_b_benchmark.p2c_engine import (
    ONLINE_ARMS,
    P2C_VARIANTS,
    bartlett_lrv_scale,
    bocpd_detector,
    focus_detector,
    post_quiet_huber_detector,
    r_fpop_runtime_probe,
    r_fpop_segment,
    run_p2c_all,
)
from p2_b_benchmark.run import stationary_sample


def fixture(n: int = 240, seed: int = 771) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 1.0, n)


def assert_online_contract(test: unittest.TestCase, result: dict, n: int) -> None:
    test.assertIn(result.get("status"), {"OK", "ABSTAIN"})
    test.assertIsInstance(result.get("hits", []), list)
    test.assertIsInstance(result.get("events", []), list)
    for hit in result.get("hits", []):
        test.assertGreaterEqual(int(hit["index"]), 40)
        test.assertLess(int(hit["index"]), n)
        test.assertIn(int(hit["sign"]), {-1, 1})
        test.assertEqual(int(hit["detection_index"]), int(hit["index"]))


class P2CStressSuite(unittest.TestCase):
    """Eight P2-C stress gates; independent of the 509-series source artifact."""

    def test_01_null_and_symmetric_positive_negative_shifts(self):
        null = fixture(260, 1001)
        self.assertEqual(focus_detector(null)["hits"], [])
        self.assertEqual(post_quiet_huber_detector(null, scale_mode="mad")["hits"], [])

        base = fixture(260, 1002)
        sigma = 1.4826 * np.median(np.abs(base[:40] - np.median(base[:40])))
        onset = 182
        positive = base.copy()
        negative = base.copy()
        positive[onset:] += 3.0 * sigma
        negative[onset:] -= 3.0 * sigma

        for runner in (focus_detector,
                       lambda z: post_quiet_huber_detector(z, scale_mode="mad")):
            pos = runner(positive)
            neg = runner(negative)
            assert_online_contract(self, pos, positive.size)
            assert_online_contract(self, neg, negative.size)
            self.assertTrue(pos["hits"], "positive shift was not detected")
            self.assertTrue(neg["hits"], "negative shift was not detected")
            self.assertEqual(int(pos["hits"][0]["sign"]), 1)
            self.assertEqual(int(neg["hits"][0]["sign"]), -1)

    def test_02_isolated_extreme_spike_is_not_robust_regime_change(self):
        x = fixture(240, 2002)
        x[105] += 30.0
        robust = post_quiet_huber_detector(x, scale_mode="mad")
        self.assertEqual(robust["hits"], [])

        persistent = fixture(240, 2003)
        sigma = 1.4826 * np.median(np.abs(persistent[:40] - np.median(persistent[:40])))
        persistent[120:] += 3.0 * sigma
        step = post_quiet_huber_detector(persistent, scale_mode="mad")
        self.assertTrue(step["hits"])
        self.assertEqual(step["hits"][0]["sign"], 1)

    def test_03a_bocpd_direction_uses_active_prior_regime_not_quiet_centre(self):
        x = fixture(360, 3033)
        quiet_scale = 1.4826 * np.median(np.abs(x[:40] - np.median(x[:40])))
        x[120:240] += 5.0 * quiet_scale
        x[240:] += 2.0 * quiet_scale
        result = bocpd_detector(x)
        assert_online_contract(self, result, x.size)
        negative = [hit for hit in result["hits"] if int(hit["index"]) >= 240]
        self.assertTrue(negative, "BOCPD missed the downward transition from +5σ to +2σ")
        self.assertEqual(int(negative[0]["sign"]), -1)
        self.assertGreater(
            float(negative[0]["prior_regime_mean"]),
            float(np.median(x[:40]) / quiet_scale) - 1.0,
        )

    def test_03_student_t_heavy_tails_and_variance_jump(self):
        rng = np.random.default_rng(3003)
        x = rng.standard_t(df=3, size=320)
        x[:40] *= 1.0
        x[180:] *= 2.5  # variance changes, while the generating mean remains zero
        for runner in (
            focus_detector,
            bocpd_detector,
            lambda z: post_quiet_huber_detector(z, scale_mode="mad"),
            lambda z: post_quiet_huber_detector(z, scale_mode="bartlett"),
        ):
            result = runner(x)
            assert_online_contract(self, result, x.size)
        self.assertEqual(post_quiet_huber_detector(x, scale_mode="mad")["hits"], [])
        self.assertEqual(post_quiet_huber_detector(x, scale_mode="bartlett")["hits"], [])
        lrv = bartlett_lrv_scale(x[:40])
        self.assertEqual(lrv["status"], "OK")
        self.assertTrue(math.isfinite(lrv["scale"]))
        self.assertGreater(lrv["scale"], 0.0)

    def test_04_bartlett_lrv_responds_to_serial_dependence(self):
        rng = np.random.default_rng(4004)
        innovations = rng.normal(size=40)
        ar = np.empty(40)
        ar[0] = innovations[0]
        for i in range(1, 40):
            ar[i] = 0.72 * ar[i - 1] + innovations[i]
        mad = 1.4826 * np.median(np.abs(ar - np.median(ar)))
        bartlett = bartlett_lrv_scale(ar)
        self.assertEqual(bartlett["status"], "OK")
        self.assertGreater(bartlett["scale"], mad)
        self.assertNotIn("hits", bartlett, "Bartlett LRV must never be an event detector")

    def test_05_multiple_changes_reversal_and_gradual_shift(self):
        x = fixture(300, 5005)
        sigma = 1.4826 * np.median(np.abs(x[:40] - np.median(x[:40])))
        x[100:205] += 3.5 * sigma
        multi = post_quiet_huber_detector(x, scale_mode="mad")
        signs = [int(hit["sign"]) for hit in multi["hits"]]
        self.assertIn(1, signs)
        self.assertIn(-1, signs)

        gradual = fixture(300, 5006)
        gradual[120:] += np.linspace(0.0, 4.0 * sigma, gradual.size - 120)
        result = focus_detector(gradual)
        self.assertTrue(result["hits"], "functional-pruning FOCuS missed a gradual mean shift")

    def test_06_short_window_and_zero_scale_abstain_explicitly(self):
        flat = np.zeros(120)
        all_flat = run_p2c_all(flat)
        self.assertEqual(set(all_flat), set(P2C_VARIANTS))
        self.assertTrue(all(x["status"] == "ABSTAIN" for x in all_flat.values()))
        self.assertTrue(all(x["abstain_reason"] == "ZERO_QUIET_SCALE"
                            for x in all_flat.values()))

        short = np.arange(40, dtype=float)
        all_short = run_p2c_all(short)
        self.assertTrue(all(x["status"] == "ABSTAIN" for x in all_short.values()))
        self.assertTrue(all(x["abstain_reason"] == "INSUFFICIENT_QUIET_WINDOW"
                            for x in all_short.values()))
        for runner in (focus_detector, bocpd_detector,
                       lambda z: post_quiet_huber_detector(z, scale_mode="mad"),
                       lambda z: post_quiet_huber_detector(z, scale_mode="bartlett")):
            self.assertEqual(runner(short)["abstain_reason"], "INSUFFICIENT_QUIET_WINDOW")

    def test_07_prefix_replay_and_future_suffix_mutation(self):
        x = fixture(260, 7007)
        sigma = 1.4826 * np.median(np.abs(x[:40] - np.median(x[:40])))
        x[170:] += 3.0 * sigma
        outputs = run_p2c_all(x, causal_audit=True)
        for arm in ONLINE_ARMS:
            self.assertEqual(outputs[arm]["causal_audit_violations"], 0, arm)
            assert_online_contract(self, outputs[arm], x.size)
            for hit in outputs[arm]["hits"]:
                prefix = x[:int(hit["index"]) + 1]
                if arm == "FOCUS":
                    replay = focus_detector(prefix)
                elif arm == "BOCPD":
                    replay = bocpd_detector(prefix)
                elif arm == "POST_QUIET_HUBER_MAD":
                    replay = post_quiet_huber_detector(prefix, scale_mode="mad")
                else:
                    replay = post_quiet_huber_detector(prefix, scale_mode="bartlett")
                self.assertTrue(any(
                    int(candidate["index"]) == int(hit["index"])
                    and int(candidate["sign"]) == int(hit["sign"])
                    for candidate in replay["hits"]
                ), arm)

    def test_08_runtime_539_and_99_bootstrap_replicates(self):
        x = fixture(539, 8008)
        started = time.perf_counter()
        for _ in range(99):
            sample = stationary_sample(x, np.random.default_rng(80_000 + _), 12)
            focus_detector(sample)
            bocpd_detector(sample)
            post_quiet_huber_detector(sample, scale_mode="mad")
            post_quiet_huber_detector(sample, scale_mode="bartlett")
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 45.0, f"online suite exceeded 45s: {elapsed:.3f}s")

        segmentation = r_fpop_segment(x)
        self.assertEqual(segmentation["status"], "OK")
        self.assertIn("upstream_commit", segmentation["metadata"])
        self.assertLessEqual(len(segmentation["metadata"]["origin_trace_sha256"]), 64)
        self.assertTrue(all(
            point["detection_index"] is None
            or point["detection_index"] >= point["estimated_change_index"]
            for point in segmentation["breakpoints"]
        ))
        self.assertNotIn("origin_trace", segmentation["metadata"])
        self.assertLessEqual(r_fpop_runtime_probe(539)["elapsed_seconds"], 10.0)


class AlgorithmReferenceTests(unittest.TestCase):
    def test_focus_matches_independent_bruteforce_scan_on_small_series(self):
        x = fixture(90, 9109)
        x[66:] += 4.0
        quiet = x[:40]
        scale = 1.4826 * np.median(np.abs(quiet - np.median(quiet)))
        centre = float(np.median(quiet))
        z = (x - centre) / scale
        expected = None
        for t in range(40, x.size):
            best = 0.0
            best_start = None
            for start in range(40, t + 1):
                segment = z[start:t + 1]
                total = float(segment.sum())
                length = int(segment.size)
                delta = total / length
                score = delta * total - 0.5 * length * delta * delta
                if score > best:
                    best, best_start = score, start
            if best >= 45.0:
                expected = (t, best_start)
                break
        actual = focus_detector(x)
        self.assertTrue(actual["hits"])
        self.assertIsNotNone(expected)
        self.assertEqual(int(actual["hits"][0]["index"]), expected[0])
        self.assertEqual(int(actual["hits"][0]["estimated_change_index"]), expected[1])

    def test_r_fpop_huber_reports_distinct_estimate_and_detection_times(self):
        x = fixture(140, 9210)
        x[70:] += 4.0
        result = r_fpop_segment(x)
        self.assertEqual(result["status"], "OK")
        self.assertTrue(result["breakpoints"])
        closest = min(result["breakpoints"],
                      key=lambda item: abs(item["estimated_change_index"] - 70))
        self.assertLessEqual(abs(closest["estimated_change_index"] - 70), 3)
        self.assertIsNotNone(closest["detection_index"])
        self.assertGreaterEqual(closest["detection_index"],
                                closest["estimated_change_index"])
        self.assertTrue(closest["first_supported_in_prefix"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
