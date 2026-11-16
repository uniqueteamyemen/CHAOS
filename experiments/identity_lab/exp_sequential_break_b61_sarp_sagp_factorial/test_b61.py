import unittest
from unittest.mock import patch

import numpy as np

from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import (
    PearsonSpearmanFixedGateEngineB6,
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import (
    SurgicalFactorEngineB61,
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES,
    N,
    ONSET,
    generate_series,
)


class B61FactorialEngineTests(unittest.TestCase):
    def test_all_factors_off_matches_frozen_b6a_event_for_event(self):
        for index, (name, dist, rho, variance_jump, shift) in enumerate(CASES):
            series = generate_series(
                np.random.default_rng(1_200_000 + index),
                dist=dist,
                rho=rho,
                var_jump=variance_jump,
                shift_sigma=shift,
                n=N,
                onset=ONSET,
            )
            old = PearsonSpearmanFixedGateEngineB6(
                correlation_method="pearson"
            ).analyze(series)
            new = SurgicalFactorEngineB61(
                correlation_method="pearson",
                innovation_drain=False,
                persistence_floor=False,
                heuristic_scale_guard=False,
            ).analyze(series)
            for key in ("structural_breaks", "transient_anomalies", "unresolved_alerts", "pending_lifecycle"):
                self.assertEqual(new[key], old[key], msg=f"parity failed for {name}:{key}")
            for key in ("rho_raw", "rho_used", "rho_method", "base_diff_scale"):
                self.assertEqual(new["diagnostics"][key], old["diagnostics"][key])

    def test_innovation_drain_rejects_ar_memory_tail(self):
        engine = SurgicalFactorEngineB61(innovation_drain=True)
        recent = np.array([8.0, 5.6, 3.92], dtype=float)
        raw, rejected, innovations = engine._pending_gate_decision(recent, 0.7)
        self.assertTrue(raw)
        self.assertTrue(rejected)
        self.assertEqual(len(innovations), 2)
        self.assertLess(abs(innovations[0]), 2.8)
        self.assertLess(abs(innovations[1]), 2.8)

    def test_innovation_drain_accepts_three_new_same_direction_impulses(self):
        engine = SurgicalFactorEngineB61(innovation_drain=True)
        recent = np.array([4.2, 5.2, 6.0], dtype=float)
        raw, rejected, innovations = engine._pending_gate_decision(recent, 0.7)
        self.assertTrue(raw)
        self.assertFalse(rejected)
        self.assertTrue(all(abs(value) > 2.8 for value in innovations))
        self.assertTrue(all(value > 0 for value in innovations))

    def test_innovation_drain_preserves_negative_same_direction_impulses(self):
        engine = SurgicalFactorEngineB61(innovation_drain=True)
        recent = np.array([-4.2, -5.2, -6.0], dtype=float)
        raw, rejected, innovations = engine._pending_gate_decision(recent, 0.7)
        self.assertTrue(raw)
        self.assertFalse(rejected)
        self.assertTrue(all(value < 0 for value in innovations))

    def test_persistence_floor_is_an_independent_and_gate(self):
        engine = SurgicalFactorEngineB61(persistence_floor=True)
        self.assertTrue(engine._passes_persistence_floor(0.75))
        self.assertTrue(engine._passes_persistence_floor(0.90))
        self.assertFalse(engine._passes_persistence_floor(0.749999))

    def test_persistence_floor_off_preserves_original_score_eligibility(self):
        engine = SurgicalFactorEngineB61(persistence_floor=False)
        self.assertTrue(engine._passes_persistence_floor(0.0))
        self.assertTrue(engine._passes_persistence_floor(0.749999))

    def test_scale_guard_is_exact_heuristic_multiplier(self):
        engine = SurgicalFactorEngineB61(heuristic_scale_guard=True)
        self.assertAlmostEqual(engine._apply_heuristic_scale_guard(2.0, 0.7), 2.35)
        self.assertAlmostEqual(engine._apply_heuristic_scale_guard(2.0, 0.3), 2.15)

    def test_scale_guard_off_is_exact_identity(self):
        engine = SurgicalFactorEngineB61(heuristic_scale_guard=False)
        self.assertEqual(engine._apply_heuristic_scale_guard(2.0, 0.7), 2.0)

    def test_structural_path_runs_when_transient_pending_gate_is_rejected(self):
        rng = np.random.default_rng(441)
        values = rng.normal(0.0, 0.10, size=140)
        values[65:] += 0.28
        engine = SurgicalFactorEngineB61(innovation_drain=True)
        with patch.object(engine, "_pending_gate_decision", return_value=(False, False, [])):
            result = engine.analyze(values)
        self.assertTrue(result["structural_breaks"])

    def test_exact_lifecycle_accounting_for_all_factor_combinations(self):
        rng = np.random.default_rng(771)
        values = rng.standard_t(df=3, size=140)
        for drain in (False, True):
            for persist in (False, True):
                for guard in (False, True):
                    result = SurgicalFactorEngineB61(
                        innovation_drain=drain,
                        persistence_floor=persist,
                        heuristic_scale_guard=guard,
                    ).analyze(values)
                    life = result["pending_lifecycle"]
                    self.assertTrue(life["accounting_complete"])
                    self.assertEqual(
                        life["opened_count"],
                        life["resolved_structural_count"]
                        + life["resolved_transient_count"]
                        + life["unresolved_count"],
                    )

    def test_diagnostics_expose_suppressed_pending_and_structural_opportunities(self):
        values = np.zeros(140, dtype=float)
        rng = np.random.default_rng(88)
        values[:40] = rng.normal(0, 0.1, size=40)
        values[65:] = 0.5
        result = SurgicalFactorEngineB61(
            innovation_drain=True,
            persistence_floor=True,
            heuristic_scale_guard=True,
        ).analyze(values)
        diag = result["diagnostics"]
        self.assertIn("pending_gate_opportunities", diag)
        self.assertIn("innovation_gate_rejections", diag)
        self.assertIn("structural_threshold_candidates", diag)
        self.assertIn("persistence_floor_rejections", diag)

    def test_boolean_factor_types_are_validated(self):
        with self.assertRaises(ValueError):
            SurgicalFactorEngineB61(innovation_drain=1)

    def test_invalid_rho_method_is_rejected(self):
        with self.assertRaises(ValueError):
            SurgicalFactorEngineB61(correlation_method="kendall")


if __name__ == "__main__":
    unittest.main()
