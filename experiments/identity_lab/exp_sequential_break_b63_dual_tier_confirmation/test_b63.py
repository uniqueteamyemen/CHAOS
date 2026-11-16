# The confirmed event preserves its start timestamp after clearing live counter state.
import unittest

import numpy as np

from experiments.identity_lab.exp_sequential_break_b63_dual_tier_confirmation.engine_b63 import (
    DualTierStructuralConfirmationEngineB63,
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import (
    SurgicalFactorEngineB61,
)


class B63DualTierConfirmationTests(unittest.TestCase):
    def make_engine(self, fast=88.0, hold=2):
        return DualTierStructuralConfirmationEngineB63(
            fast_thresh=fast,
            hold_steps=hold,
            innovation_drain=True,
            persistence_floor=True,
            heuristic_scale_guard=False,
        )

    def test_configuration_validation(self):
        with self.assertRaises(ValueError):
            self.make_engine(fast=83.0)
        with self.assertRaises(ValueError):
            self.make_engine(fast=101.0)
        with self.assertRaises(ValueError):
            self.make_engine(hold=0)

    def test_base_factors_are_exact_d1_p1_g0(self):
        engine = self.make_engine()
        self.assertEqual(engine.correlation_method, "pearson")
        self.assertTrue(engine.innovation_drain)
        self.assertTrue(engine.persistence_floor)
        self.assertFalse(engine.heuristic_scale_guard)
        self.assertEqual(engine.fast_thresh, 88.0)
        self.assertEqual(engine.hold_steps, 2)
        self.assertEqual(engine.borderline_floor, 83.0)

    def test_fast_path_announces_at_current_t(self):
        engine = self.make_engine(fast=88.0, hold=3)
        step = engine._advance_dual_tier_confirmation(
            break_pct=88.0, dominant_persistence=0.75, direction=1,
            latched_direction=0, window_shift_z=1.2,
            hold_direction=0, hold_counter=0, hold_started_at=None, time_index=71,
        )
        self.assertEqual(step["path"], "fast")

    def test_initial_borderline_sample_is_not_counted_as_hold_step(self):
        engine = self.make_engine(fast=88.0, hold=2)
        first = engine._advance_dual_tier_confirmation(
            break_pct=85.0, dominant_persistence=0.80, direction=1,
            latched_direction=0, window_shift_z=1.1,
            hold_direction=0, hold_counter=0, hold_started_at=None, time_index=70,
        )
        self.assertIsNone(first["path"])
        self.assertEqual(first["hold_counter"], 0)
        self.assertEqual(first["hold_started_at"], 70)

    def test_borderline_requires_two_additional_consecutive_steps(self):
        engine = self.make_engine(fast=88.0, hold=2)
        state = {"hold_direction": 0, "hold_counter": 0, "hold_started_at": None}
        def advance(t):
            result = engine._advance_dual_tier_confirmation(
                break_pct=85.0, dominant_persistence=0.80, direction=1,
                latched_direction=0, window_shift_z=1.1,
                **state, time_index=t,
            )
            state.update({
                "hold_direction": result["hold_direction"],
                "hold_counter": result["hold_counter"],
                "hold_started_at": result["hold_started_at"],
            })
            return result
        one = advance(70)
        two = advance(71)
        three = advance(72)
        self.assertIsNone(one["path"])
        self.assertIsNone(two["path"])
        self.assertEqual(two["hold_counter"], 1)
        self.assertEqual(three["path"], "confirmed")
        self.assertEqual(three["confirmation_started_at"], 70)

    def test_score_below_83_resets_without_alert(self):
        engine = self.make_engine()
        result = engine._advance_dual_tier_confirmation(
            break_pct=82.9, dominant_persistence=0.90, direction=1,
            latched_direction=0, window_shift_z=0.8,
            hold_direction=1, hold_counter=1, hold_started_at=70, time_index=72,
        )
        self.assertIsNone(result["path"])
        self.assertEqual(result["hold_counter"], 0)
        self.assertTrue(result["counter_reset"])

    def test_persistence_drop_resets_without_alert(self):
        engine = self.make_engine()
        result = engine._advance_dual_tier_confirmation(
            break_pct=85.0, dominant_persistence=0.749, direction=1,
            latched_direction=0, window_shift_z=0.8,
            hold_direction=1, hold_counter=1, hold_started_at=70, time_index=72,
        )
        self.assertIsNone(result["path"])
        self.assertEqual(result["hold_counter"], 0)
        self.assertTrue(result["persistence_rejected"])

    def test_direction_flip_rejects_candidate_on_flip_sample(self):
        engine = self.make_engine()
        result = engine._advance_dual_tier_confirmation(
            break_pct=89.0, dominant_persistence=0.90, direction=-1,
            latched_direction=0, window_shift_z=-1.1,
            hold_direction=1, hold_counter=1, hold_started_at=70, time_index=72,
        )
        self.assertIsNone(result["path"])
        self.assertEqual(result["hold_direction"], 0)
        self.assertEqual(result["hold_counter"], 0)
        self.assertTrue(result["direction_flipped"])

    def test_direction_can_start_new_candidate_only_on_later_step(self):
        engine = self.make_engine()
        flipped = engine._advance_dual_tier_confirmation(
            break_pct=85.0, dominant_persistence=0.90, direction=-1,
            latched_direction=0, window_shift_z=-1.0,
            hold_direction=1, hold_counter=1, hold_started_at=70, time_index=72,
        )
        restarted = engine._advance_dual_tier_confirmation(
            break_pct=85.0, dominant_persistence=0.90, direction=-1,
            latched_direction=0, window_shift_z=-1.0,
            hold_direction=flipped["hold_direction"],
            hold_counter=flipped["hold_counter"],
            hold_started_at=flipped["hold_started_at"],
            time_index=73,
        )
        self.assertIsNone(flipped["path"])
        self.assertEqual(restarted["hold_direction"], -1)
        self.assertEqual(restarted["hold_counter"], 0)

    def test_latch_reset_matches_b61_threshold(self):
        engine = self.make_engine()
        result = engine._advance_dual_tier_confirmation(
            break_pct=70.0, dominant_persistence=0.90, direction=1,
            latched_direction=1, window_shift_z=0.399,
            hold_direction=0, hold_counter=0, hold_started_at=None, time_index=90,
        )
        self.assertTrue(result["latch_reset"])

    def test_persistence_floor_is_strict_independent_gate(self):
        engine = self.make_engine()
        accepted = engine._advance_dual_tier_confirmation(
            break_pct=83.0, dominant_persistence=0.75, direction=1,
            latched_direction=0, window_shift_z=1.0,
            hold_direction=0, hold_counter=0, hold_started_at=None, time_index=70,
        )
        rejected = engine._advance_dual_tier_confirmation(
            break_pct=87.9, dominant_persistence=0.749999, direction=1,
            latched_direction=0, window_shift_z=1.0,
            hold_direction=0, hold_counter=0, hold_started_at=None, time_index=70,
        )
        self.assertIsNone(accepted["path"])
        self.assertEqual(accepted["hold_direction"], 1)
        self.assertTrue(rejected["persistence_rejected"])
        self.assertIsNone(rejected["path"])

    def test_d1_p1_g0_scaling_and_pendings_remain_active(self):
        rng = np.random.default_rng(304)
        values = rng.normal(0, 0.1, size=140)
        values[65:] += 0.30
        result = self.make_engine().analyze(values)
        diag = result["diagnostics"]
        self.assertEqual(diag["rho_method"], "pearson")
        self.assertFalse(diag["heuristic_scale_guard_enabled"])
        self.assertTrue(diag["innovation_drain_enabled"])
        self.assertTrue(diag["persistence_floor_enabled"])
        self.assertEqual(diag["dual_tier_borderline_floor"], 83.0)
        self.assertTrue(result["pending_lifecycle"]["accounting_complete"])

    def test_lifecycle_identity_is_enforced(self):
        rng = np.random.default_rng(882)
        values = rng.standard_t(df=3, size=140)
        result = self.make_engine().analyze(values)
        life = result["pending_lifecycle"]
        self.assertEqual(
            life["opened_count"],
            life["resolved_structural_count"]
            + life["resolved_transient_count"]
            + life["unresolved_count"],
        )

    def test_reference_base_configuration_is_exact(self):
        reference = SurgicalFactorEngineB61(
            innovation_drain=True,
            persistence_floor=True,
            heuristic_scale_guard=False,
            break_percent_thresh=85.0,
        )
        self.assertEqual(reference.break_percent_thresh, 85.0)
        self.assertTrue(reference.innovation_drain)
        self.assertTrue(reference.persistence_floor)
        self.assertFalse(reference.heuristic_scale_guard)


if __name__ == "__main__":
    unittest.main()
