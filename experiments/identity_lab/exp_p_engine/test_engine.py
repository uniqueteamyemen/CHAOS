"""Regression tests for the consolidated engine (exp_p_engine)."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.engine import DOMAINS, adapt, mad_sigma, residuals, rolling_sigma, run


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


def generate_rising_noise(domain, months=200, leak=10, start=10, seed=1):
    """A constant leak under noise that grows 2 -> 8: the rolling sigma must not
    grow enough to swallow the signal."""
    rng = random.Random(seed)
    c = DOMAINS[domain]
    balance, rows = 2000, []
    for month in range(1, months + 1):
        opening = balance
        off = month - start
        loss = leak if off >= 0 else 0
        noise = 2.0 + 6.0 * (month / months)
        closing = opening + 400 - 400 - 5 - loss + rng.gauss(0, noise)
        rows.append({c["opening"]: opening, c["inflow"]: 400, c["outflow"]: 400,
                     c["other"]: 5, c["closing"]: closing, "month": month})
        balance = closing
    return rows


def generate_gradual_leak(domain, months=200, slope=0.15, start=10, seed=1):
    rng = random.Random(seed)
    c = DOMAINS[domain]
    balance, rows = 2000, []
    for month in range(1, months + 1):
        opening = balance
        off = max(0, month - start)
        loss = slope * off
        closing = opening + 400 - 400 - 5 - loss + rng.gauss(0, 2.0)
        rows.append({c["opening"]: opening, c["inflow"]: 400, c["outflow"]: 400,
                     c["other"]: 5, c["closing"]: closing, "month": month})
        balance = closing
    return rows


def generate_zero_noise(domain, months=200):
    c = DOMAINS[domain]
    balance, rows = 2000, []
    for month in range(1, months + 1):
        opening = balance
        closing = opening + 400 - 400 - 5
        rows.append({c["opening"]: opening, c["inflow"]: 400, c["outflow"]: 400,
                     c["other"]: 5, c["closing"]: closing, "month": month})
        balance = closing
    return rows


class EngineTests(unittest.TestCase):
    def test_no_leak_is_silent(self):
        out = run("stock", generate("stock", leak=0), quiet_range=(1, 6))
        self.assertEqual(len(out["alerts"]), 0, f"unexpected alerts={out['alerts']}")

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

    def test_sign_run_break_counter_reports_breaks(self):
        out = run("stock", generate("stock", leak=10), quiet_range=(1, 6))
        self.assertTrue(out["sign_run_break_counter"]["months"])
        self.assertGreater(sum(out["sign_run_break_counter"]["counts"]), 0)

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

    def test_quiet_range_is_mandatory(self):
        with self.assertRaises(TypeError):
            run("stock", generate("stock", leak=10))

    def test_insufficient_quiet_window_is_rejected(self):
        with self.assertRaises(ValueError):
            run("stock", generate("stock", leak=10), quiet_range=(1, 1))

    def test_rising_noise_does_not_erase_a_constant_leak(self):
        # with the ceiling, a leak above 3*ceiling_sigma stays visible near the end
        rows = generate_rising_noise("stock", leak=20)
        out = run("stock", rows, quiet_range=(1, 6), cooldown=12)
        p1 = [a["time"] for a in out["alerts"] if a["priority"] == 1]
        self.assertTrue(p1, "a constant leak must still alert under rising noise")
        self.assertGreater(max(p1), 160)

    def test_zero_quiet_sigma_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "quiet_sigma_must_be_positive"):
            run("stock", generate_zero_noise("stock"), quiet_range=(1, 6))

    def test_three_quiet_sigma_leak_can_be_seen_in_high_noise(self):
        out = run("stock", generate_rising_noise("stock", leak=6, seed=27),
                  quiet_range=(1, 6), cooldown=12)
        self.assertEqual(out["diagnostics"]["noise_regime"], "degraded")
        p1 = [a for a in out["alerts"] if a["detector"] == "sign_run"]
        self.assertTrue(p1, "high-noise directional P1 should retain sensitivity to a persistent shift")

    def test_rising_noise_without_leak_measures_false_alert_rate(self):
        trials = 40
        false_alerts = 0
        degraded_trials = 0
        detector_counts = {"sign_run": 0, "cusum": 0}
        for seed in range(trials):
            out = run("stock", generate_rising_noise("stock", leak=0, seed=seed + 100),
                      quiet_range=(1, 6), cooldown=12)
            if out["alerts"]:
                false_alerts += 1
            degraded_trials += int(out["diagnostics"]["noise_regime"] == "degraded")
            for detector in detector_counts:
                detector_counts[detector] += int(any(a["detector"] == detector for a in out["alerts"]))
        false_alert_rate = false_alerts / trials
        detector_rates = {k: v / trials for k, v in detector_counts.items()}
        self.assertGreaterEqual(degraded_trials / trials, 0.5,
                                "variance change must be exposed as degraded, not hidden")
        self.assertLessEqual(false_alert_rate, 0.10,
                             f"rising-noise false alert rate={false_alert_rate:.3f}; by_detector={detector_rates}")

    def test_gradual_leak_remains_detectable(self):
        out = run("stock", generate_gradual_leak("stock", slope=0.15),
                  quiet_range=(1, 6), cooldown=12)
        cusum = [a for a in out["alerts"] if a["detector"] == "cusum"]
        self.assertTrue(cusum, "CUSUM must accumulate a gradual persistent drift")

    def test_unbounded_rolling_sigma_tracks_noise_inflation(self):
        rows = generate_rising_noise("stock", leak=20)
        series = residuals(rows, "stock")
        quiet = [r["residual"] for r in series if 1 <= r["month"] <= 6]
        quiet_sigma = mad_sigma(quiet)
        unbounded = rolling_sigma(series, window=52)
        self.assertGreater(unbounded[-1], 2.5 * quiet_sigma)


if __name__ == "__main__":
    unittest.main()
