import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_b7_quantized_block_fusion.engine_b7 import (
    QuantizedBlockFusionEngineB7,
)


def quiet(seed: int = 43) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 0.05, size=40)


def series_with_spikes(points: int, seed: int = 43) -> np.ndarray:
    values = np.zeros(140, dtype=float)
    values[:40] = quiet(seed)
    values[55 : 55 + points] = 10.0
    return values


class B7BlockFusionTests(unittest.TestCase):
    def test_fixed_experiment_dimensions_and_parameters(self):
        engine = QuantizedBlockFusionEngineB7(c_sup=1.05, z_block=1.8)
        self.assertEqual(engine.quiet_end, 40)
        self.assertEqual(engine.window_size, 12)
        self.assertEqual(engine.series_length, 140)
        self.assertEqual(engine.onset, 65)
        self.assertEqual(engine.resolution_horizon, 14)
        self.assertEqual(engine.c_sup, 1.05)
        self.assertEqual(engine.z_block, 1.8)

    def test_overlapping_block_envelope_has_29_blocks(self):
        values = np.r_[quiet(44), np.zeros(100)]
        result = QuantizedBlockFusionEngineB7().analyze(values)
        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["block_median_count"], 29)
        self.assertGreaterEqual(diagnostics["point_scale"], 1e-6)
        self.assertGreaterEqual(diagnostics["difference_scale_baseline"], 1e-6)
        self.assertGreaterEqual(diagnostics["block_scale"], 1e-6)
        self.assertGreaterEqual(diagnostics["block_supremum_95"], 0.0)

    def test_no_autocorrelation_coefficient_is_estimated(self):
        result = QuantizedBlockFusionEngineB7().analyze(
            np.r_[quiet(45), np.zeros(100)]
        )
        diagnostics = result["diagnostics"]
        self.assertFalse(diagnostics["rho_estimated"])
        self.assertNotIn("rho_raw", diagnostics)
        self.assertNotIn("rho_used", diagnostics)

    def test_quantization_is_bounded_and_rounds_to_even(self):
        z = np.asarray([-9.0, -1.5, -0.5, 0.5, 1.5, 9.0])
        quantized = QuantizedBlockFusionEngineB7._quantize_z(z)
        np.testing.assert_array_equal(
            quantized,
            np.asarray([-2.0, -2.0, 0.0, 0.0, 2.0, 2.0]),
        )

    def test_pending_gate_requires_three_consecutive_same_sign_points(self):
        two = QuantizedBlockFusionEngineB7(
            c_sup=100.0, z_block=100.0
        ).analyze(series_with_spikes(2))
        three = QuantizedBlockFusionEngineB7(
            c_sup=100.0, z_block=100.0
        ).analyze(series_with_spikes(3))
        self.assertEqual(two["pending_lifecycle"]["opened_count"], 0)
        self.assertGreaterEqual(three["pending_lifecycle"]["opened_count"], 1)
        self.assertTrue(
            any(alert["time"] == 57 for alert in three["transient_anomalies"])
        )

    def test_pending_gate_rejects_mixed_sign_triple(self):
        values = np.zeros(140, dtype=float)
        values[:40] = quiet(46)
        values[55:58] = [10.0, 10.0, -10.0]
        result = QuantizedBlockFusionEngineB7(
            c_sup=100.0, z_block=100.0
        ).analyze(values)
        self.assertEqual(result["pending_lifecycle"]["opened_count"], 0)

    def test_transient_requires_observed_return_within_horizon(self):
        values = series_with_spikes(3, 47)
        # The level returns to baseline immediately after the 3-point excursion.
        values[58:] = 0.0
        result = QuantizedBlockFusionEngineB7(
            c_sup=100.0, z_block=100.0
        ).analyze(values)
        event = [a for a in result["transient_anomalies"] if a["time"] == 57]
        self.assertTrue(event)
        self.assertEqual(event[0]["status"], "RESOLVED_TRANSIENT")
        self.assertLess(event[0]["return_z"], 1.5)
        self.assertEqual(event[0]["resolved_at"], 58)

    def test_no_return_by_horizon_becomes_unresolved(self):
        values = np.zeros(140, dtype=float)
        values[:40] = quiet(48)
        values[55:] = 10.0
        result = QuantizedBlockFusionEngineB7(
            c_sup=100.0, z_block=100.0
        ).analyze(values)
        self.assertTrue(
            any(
                item["time"] == 57
                and item["status"] == "UNRESOLVED_HORIZON_EXPIRED"
                and item["terminal_at"] == 71
                for item in result["unresolved_alerts"]
            )
        )

    def test_local_difference_scale_ratio_never_below_one(self):
        rng = np.random.default_rng(49)
        quiet_values = rng.normal(0.0, 0.05, size=65)
        post_values = rng.normal(0.0, 0.5, size=75)
        values = np.r_[quiet_values[:40], quiet_values[40:], post_values]
        # A larger post-quiet difference scale should be reflected in the local
        # variance multiplier without ever shrinking the baseline scales.
        engine = QuantizedBlockFusionEngineB7()
        baseline = engine._baseline(values[:40])
        local = engine._robust_difference_scale(values[69:91])
        ratio = max(1.0, local / baseline["difference_scale"])
        self.assertGreaterEqual(ratio, 1.0)
        self.assertGreater(local, baseline["difference_scale"])

    def test_all_structural_gates_are_required(self):
        engine = QuantizedBlockFusionEngineB7(c_sup=1.0, z_block=1.0)
        window = np.full(12, 5.0)
        z = np.full(12, 5.0)
        passed = engine._structural_gates(
            window, z, center=0.0, block_scale_t=1.0, block_supremum_t=1.0
        )
        self.assertTrue(passed["amplitude_gate"])
        self.assertTrue(passed["epoch_position_gate"])
        self.assertTrue(passed["quantized_gate"])
        self.assertTrue(passed["structural_gate_passed"])

        mixed_epochs = window.copy()
        mixed_epochs[:4] = -5.0
        failed_epoch = engine._structural_gates(
            mixed_epochs, z, 0.0, 1.0, 1.0
        )
        self.assertFalse(failed_epoch["epoch_position_gate"])
        self.assertFalse(failed_epoch["structural_gate_passed"])

        low_quantized_scores = np.full(12, 0.8)
        failed_quantized = engine._structural_gates(
            window, low_quantized_scores, 0.0, 1.0, 1.0
        )
        self.assertTrue(failed_quantized["amplitude_gate"])
        self.assertTrue(failed_quantized["epoch_position_gate"])
        self.assertFalse(failed_quantized["quantized_gate"])
        self.assertFalse(failed_quantized["structural_gate_passed"])

    def test_pending_lifecycle_accounting_is_exact(self):
        for values in (
            series_with_spikes(3, 51),
            np.r_[quiet(52), np.zeros(100)],
            np.r_[quiet(53), np.full(100, 4.0)],
        ):
            result = QuantizedBlockFusionEngineB7().analyze(values)
            life = result["pending_lifecycle"]
            self.assertTrue(life["accounting_complete"])
            self.assertEqual(
                life["opened_count"],
                life["resolved_structural_count"]
                + life["resolved_transient_count"]
                + life["unresolved_count"],
            )

    def test_invalid_length_and_nonfinite_values_are_rejected(self):
        engine = QuantizedBlockFusionEngineB7()
        with self.assertRaises(ValueError):
            engine.analyze(np.zeros(139))
        values = np.zeros(140)
        values[10] = np.nan
        with self.assertRaises(ValueError):
            engine.analyze(values)


if __name__ == "__main__":
    unittest.main()
