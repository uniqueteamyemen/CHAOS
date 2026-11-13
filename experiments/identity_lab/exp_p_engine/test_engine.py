"""Regression tests for the consolidated engine (exp_p_engine)."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.engine import DOMAINS, adapt, run


def generate(domain, months=200, leak=0, start=10, excess=0, noise=2.0, seed=1):
    rng = random.Random(seed)
    c = DOMAINS[domain]
    balance, rows = 2000, []
    for month in range(1, months + 1):
        opening = balance
        off = month - start
        loss = leak if off >= 0 else 0
        outflow = 400 + (excess if off >= 0 else 0)
        closing = opening + 400 - outflow - 5 - loss + rng.gauss(0, noise)
        rows.append({c["opening"]: opening, c["inflow"]: 400, c["outflow"]: outflow,
                     c["other"]: 5, c["closing"]: closing, "month": month})
        balance = closing
    return rows


class EngineTests(unittest.TestCase):
    def test_no_leak_is_silent(self):
        out = run("stock", generate("stock", leak=0), quiet_range=(1, 6))
        self.assertEqual(len(out["alerts"]), 0)

    def test_constant_leak_fires_p1(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6))
        self.assertGreaterEqual(len([a for a in out["alerts"] if a["priority"] == 1]), 1)

    def test_small_leak_only_cusum(self):
        out = run("stock", generate("stock", leak=2), quiet_range=(1, 6))
        self.assertEqual(len([a for a in out["alerts"] if a["priority"] == 1]), 0)
        self.assertGreaterEqual(len([a for a in out["alerts"] if a["priority"] == 2]), 1)

    def test_p1_suppresses_p2_for_same_entity(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6))
        self.assertGreaterEqual(
            len([s for s in out["suppressed"] if s["suppressed"] == "suppressed_by_P1"]), 1)

    def test_cooldown_reduces_duplicates(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6), cooldown=26)
        self.assertGreaterEqual(
            len([s for s in out["suppressed"] if s["suppressed"] == "cooldown"]), 1)

    def test_cashflow_same_behaviour(self):
        out = run("cashflow", generate("cashflow", leak=10), quiet_range=(1, 6))
        self.assertGreaterEqual(len([a for a in out["alerts"] if a["priority"] == 1]), 1)

    def test_frozen_bias_does_not_absorb_a_persistent_leak(self):
        # the critical regression: a rolling bias would delete this signal
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6), cooldown=12)
        p1_times = [a["time"] for a in out["alerts"] if a["priority"] == 1]
        self.assertTrue(p1_times)
        self.assertGreater(max(p1_times), 150)

    def test_counter_reports_breaks(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6))
        self.assertTrue(out["counter"]["months"])
        self.assertGreater(sum(out["counter"]["counts"]), 0)

    def test_baseline_reports_frozen_bias_and_rolling_sigma(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6))
        self.assertIsNotNone(out["baseline"]["bias_frozen"])
        self.assertIsNotNone(out["baseline"]["sigma_last"])

    def test_adapt_maps_arbitrary_columns(self):
        # the engine imposes no schema: any source is a mapping, not a rewrite
        raw = [{"date": 1, "open_qty": 2000, "in_qty": 400, "out_qty": 400,
                "close_qty": 1995}]
        mapping = {"opening": "open_qty", "inflow": "in_qty", "outflow": "out_qty",
                   "closing": "close_qty", "time": "date"}
        adapted = adapt(raw, mapping)
        self.assertEqual(adapted[0]["opening"], 2000)
        self.assertEqual(adapted[0]["other"], 0.0)   # optional term defaults
        self.assertEqual(adapted[0]["month"], 1)


if __name__ == "__main__":
    unittest.main()
