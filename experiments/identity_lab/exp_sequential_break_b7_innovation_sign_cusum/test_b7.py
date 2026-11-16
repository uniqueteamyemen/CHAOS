import unittest
import numpy as np

from experiments.identity_lab.exp_sequential_break_b7_innovation_sign_cusum.engine_b7 import (
    InnovationSignCusumEngineB7,
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import (
    SurgicalFactorEngineB61,
)


class B7InnovationSignCusumTests(unittest.TestCase):
    def make_engine(self, threshold=6.5, corrected=True):
        return InnovationSignCusumEngineB7(
            cusum_threshold=threshold,
            structural_rho_bias_correction=corrected,
            innovation_drain=True,
            persistence_floor=False,
            heuristic_scale_guard=False,
            correlation_method="pearson",
        )

    def test_constructor_rejects_nonpositive_threshold(self):
        with self.assertRaises(ValueError):
            self.make_engine(threshold=0.0)
        with self.assertRaises(ValueError):
            self.make_engine(threshold=-1.0)

    def test_constructor_validates_rho_correction_flag(self):
        with self.assertRaises(ValueError):
            InnovationSignCusumEngineB7(structural_rho_bias_correction=1)

    def test_short_sample_ar1_correction_formula(self):
        corrected = InnovationSignCusumEngineB7._correct_short_sample_ar1_rho(0.62, 40)
        self.assertAlmostEqual(corrected, (0.62 + 1 / 40) / (1 - 3 / 40), places=12)

    def test_short_sample_ar1_correction_clips_supported_range(self):
        self.assertEqual(
            InnovationSignCusumEngineB7._correct_short_sample_ar1_rho(-0.4, 40), 0.0
        )
        self.assertEqual(
            InnovationSignCusumEngineB7._correct_short_sample_ar1_rho(0.99, 40), 0.88
        )

    def test_log_likelihood_increments_have_negative_null_and_positive_alternative_drift(self):
        q = 0.65
        target = np.log(2.0 * q)
        opposite = np.log(2.0 * (1.0 - q))
        null_drift = 0.5 * target + 0.5 * opposite
        alternative_drift = q * target + (1.0 - q) * opposite
        self.assertLess(null_drift, 0.0)
        self.assertGreater(alternative_drift, 0.0)

    def test_zero_innovation_sign_is_neutral(self):
        before = (1.25, 0.75)
        after = InnovationSignCusumEngineB7._sign_cusum_update(
            *before, innovation_sign=0, latched_direction=0
        )
        self.assertEqual(after, before)

    def test_sign_cusum_is_magnitude_blind(self):
        # Magnitude never enters the updater; only the sign is supplied.
        a = InnovationSignCusumEngineB7._sign_cusum_update(0, 0, 1, 0)
        b = InnovationSignCusumEngineB7._sign_cusum_update(0, 0, 1, 0)
        self.assertEqual(a, b)
        self.assertAlmostEqual(a[0], np.log(1.3), places=12)
        self.assertEqual(a[1], 0.0)

    def test_repeated_directional_signs_accumulate_log_likelihood(self):
        pos = neg = 0.0
        for _ in range(6):
            pos, neg = InnovationSignCusumEngineB7._sign_cusum_update(pos, neg, 1, 0)
        self.assertAlmostEqual(pos, 6 * np.log(1.3), places=12)
        self.assertEqual(neg, 0.0)

    def test_equal_positive_and_negative_log_evidence_has_negative_net_increment(self):
        q = 0.65
        self.assertLess(np.log(2*q) + np.log(2*(1-q)), 0.0)

    def test_latched_positive_direction_only_accumulates_reversal_evidence(self):
        pos, neg = 4.0, 0.0
        pos, neg = InnovationSignCusumEngineB7._sign_cusum_update(pos, neg, 1, 1)
        self.assertEqual(pos, 0.0)
        self.assertEqual(neg, 0.0)
        for _ in range(4):
            pos, neg = InnovationSignCusumEngineB7._sign_cusum_update(pos, neg, -1, 1)
        self.assertEqual(pos, 0.0)
        self.assertAlmostEqual(neg, 4 * np.log(1.3), places=12)

    def test_latched_negative_direction_only_accumulates_positive_reversal_evidence(self):
        pos, neg = 0.0, 4.0
        pos, neg = InnovationSignCusumEngineB7._sign_cusum_update(pos, neg, -1, -1)
        self.assertEqual(neg, 0.0)
        self.assertEqual(pos, 0.0)
        for _ in range(4):
            pos, neg = InnovationSignCusumEngineB7._sign_cusum_update(pos, neg, 1, -1)
        self.assertAlmostEqual(pos, 4 * np.log(1.3), places=12)
        self.assertEqual(neg, 0.0)

    def test_causal_structural_scan_starts_at_quiet_end(self):
        result = self.make_engine().analyze(np.zeros(140, dtype=float))
        self.assertEqual(result["diagnostics"]["cusum_updates"], 100)

    def test_structural_detection_uses_sign_cusum_not_break_pct_gate(self):
        values = np.zeros(140, dtype=float)
        values[65:] = 2.0
        result = self.make_engine(threshold=1.5).analyze(values)
        self.assertTrue(result["structural_breaks"])
        first = result["structural_breaks"][0]
        self.assertEqual(first["direction"], 1)
        self.assertEqual(first["evidence_kind"], "innovation_sign_cusum")
        self.assertGreaterEqual(first["structural_evidence"], 1.5)
        self.assertGreaterEqual(first["detection_time"], 51)
        # Six same-direction innovations can accumulate before the 12-point
        # median becomes a majority; unlatched CUSUM evidence must survive.
        self.assertLess(first["detection_time"], 71)

    def test_corrected_and_raw_rho_ablation_changes_only_structural_rho(self):
        rng = np.random.default_rng(709)
        values = np.empty(140, dtype=float)
        values[0] = rng.normal()
        for t in range(1, 140):
            values[t] = 0.65 * values[t-1] + np.sqrt(1-0.65**2) * rng.normal()
        raw = self.make_engine(corrected=False).analyze(values)["diagnostics"]
        corrected = self.make_engine(corrected=True).analyze(values)["diagnostics"]
        self.assertEqual(raw["rho_used"], raw["rho_raw"])
        self.assertEqual(corrected["rho_used"], corrected["rho_raw"])
        self.assertFalse(raw["rho_cusum_bias_correction_enabled"])
        self.assertTrue(corrected["rho_cusum_bias_correction_enabled"])
        self.assertNotEqual(raw["rho_cusum_used"], corrected["rho_cusum_used"])

    def test_d_channel_remains_enabled_and_context_rho_is_not_corrected(self):
        rng = np.random.default_rng(304)
        values = rng.standard_t(df=3, size=140)
        result = self.make_engine().analyze(values)
        diag = result["diagnostics"]
        self.assertTrue(diag["innovation_drain_enabled"])
        self.assertFalse(diag["heuristic_scale_guard_enabled"])
        self.assertFalse(diag["persistence_floor_enabled"])
        self.assertEqual(diag["rho_used"], diag["rho_raw"])
        self.assertEqual(diag["structural_evidence_kind"], "innovation_sign_cusum")

    def test_pending_lifecycle_equation_is_enforced(self):
        rng = np.random.default_rng(883)
        result = self.make_engine().analyze(rng.standard_t(df=3, size=140))
        life = result["pending_lifecycle"]
        self.assertEqual(
            life["opened_count"],
            life["resolved_structural_count"]
            + life["resolved_transient_count"]
            + life["unresolved_count"],
        )
        self.assertTrue(life["accounting_complete"])

    def test_b61_reference_factory_contract_remains_available(self):
        ref = SurgicalFactorEngineB61(
            innovation_drain=True, persistence_floor=True,
            heuristic_scale_guard=False, break_percent_thresh=85.0,
        )
        self.assertEqual(ref.break_percent_thresh, 85.0)
        self.assertTrue(ref.innovation_drain)
        self.assertTrue(ref.persistence_floor)
        self.assertFalse(ref.heuristic_scale_guard)


if __name__ == "__main__":
    unittest.main()
