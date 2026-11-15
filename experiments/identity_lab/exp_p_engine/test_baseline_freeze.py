"""Tests for rolling, fixed and suspicion-triggered baseline freezing."""
import random
import unittest

from experiments.identity_lab.exp_p_engine.baseline_freeze_experiment import (
    POLICIES,
    build_policy_residuals,
)


def make_series(*, count=36, shift_from=None, shift=0.0, transient_at=None, gap_at=None):
    rows = []
    rng = random.Random(2026)
    pattern = (0.10, -0.10, 0.05, -0.05)
    years = []
    for index in range(count):
        year = 2000 + index
        if gap_at is not None and index >= gap_at:
            year += 2
        years.append(year)
        value = 20.0 + 0.2 * index + pattern[index % len(pattern)] + rng.gauss(0.0, 0.03)
        if shift_from is not None and index >= shift_from:
            value += shift
        if transient_at is not None and index == transient_at:
            value += shift
        rows.append({
            "entity_id": "entity-1",
            "metric_id": "output",
            "event_time": str(year),
            "value": value,
            "observation_status": "observed",
            "unit": "units",
        })
    return rows


class BaselineFreezeTests(unittest.TestCase):
    def test_all_policies_emit_valid_residual_rows(self):
        series = make_series()
        for policy in POLICIES:
            with self.subTest(policy=policy):
                rows, diagnostics = build_policy_residuals(
                    series, policy=policy, time_unit="years",
                )
                self.assertTrue(rows)
                self.assertEqual(diagnostics["policy"], policy)
                self.assertTrue(all("baseline_id" in row for row in rows))
                self.assertTrue(all(row["status"] in {
                    "ready", "gap_unresolved", "scale_unavailable"
                } for row in rows))

    def test_suspicion_freeze_holds_the_pre_break_baseline(self):
        onset_index = 23
        series = make_series(shift_from=onset_index, shift=2.0)
        rolling, _ = build_policy_residuals(
            series, policy="rolling_baseline_rolling_scale", time_unit="years",
        )
        frozen, diagnostics = build_policy_residuals(
            series, policy="suspicion_freeze_baseline_and_scale", time_unit="years",
        )
        target_time = str(2000 + (onset_index + 7))
        rolling_row = next(row for row in rolling if row["event_time"] == target_time)
        frozen_row = next(row for row in frozen if row["event_time"] == target_time)
        self.assertGreaterEqual(diagnostics["freeze_trigger_count"], 1)
        self.assertGreater(abs(frozen_row["z_score"]), abs(rolling_row["z_score"]))
        self.assertTrue(frozen_row["freeze_active"])

    def test_freeze_baseline_only_isolates_scale_adaptation(self):
        series = make_series(shift_from=23, shift=2.0)
        baseline_only, _ = build_policy_residuals(
            series, policy="suspicion_freeze_baseline_rolling_scale", time_unit="years",
        )
        baseline_and_scale, _ = build_policy_residuals(
            series, policy="suspicion_freeze_baseline_and_scale", time_unit="years",
        )
        time = "2030"
        left = next(row for row in baseline_only if row["event_time"] == time)
        right = next(row for row in baseline_and_scale if row["event_time"] == time)
        self.assertTrue(left["freeze_active"])
        self.assertTrue(right["freeze_active"])
        self.assertGreaterEqual(abs(right["z_score"]), abs(left["z_score"]))

    def test_transient_spike_releases_after_confirmed_return(self):
        series = make_series(transient_at=18, shift=3.0)
        rows, diagnostics = build_policy_residuals(
            series,
            policy="suspicion_freeze_baseline_and_scale",
            time_unit="years",
            suspicion_z=8.0,
            release_z=2.0,
            release_run=5,
            suspicion_run=1,
        )
        self.assertGreaterEqual(diagnostics["freeze_trigger_count"], 1)
        self.assertGreaterEqual(diagnostics["freeze_release_count"], 1)
        self.assertTrue(any(row["freeze_released"] for row in rows))

    def test_first_observation_after_gap_is_not_scored_and_history_rebuilds(self):
        series = make_series(count=18, gap_at=8)
        rows, _ = build_policy_residuals(
            series, policy="rolling_baseline_rolling_scale", time_unit="years",
        )
        gap_time = series[8]["event_time"]
        gap_row = next(row for row in rows if row["event_time"] == gap_time)
        self.assertEqual(gap_row["status"], "gap_unresolved")
        post_gap = [row for row in rows if int(row["event_time"]) >= int(gap_time)]
        self.assertEqual(post_gap[0]["status"], "gap_unresolved")
        self.assertTrue(all(row["status"] == "scale_unavailable" for row in post_gap[1:8]))
        self.assertTrue(all(row["status"] == "ready" for row in post_gap[8:]))


    def test_two_same_direction_suspicion_points_are_required_before_freeze(self):
        series = make_series(shift_from=23, shift=2.0)
        rows, diagnostics = build_policy_residuals(
            series,
            policy="suspicion_freeze_baseline_and_scale",
            time_unit="years",
            suspicion_z=2.0,
            suspicion_run=2,
        )
        triggers = [row for row in rows if row["freeze_trigger"]]
        pending = [row for row in rows if row.get("suspicion_pending")]
        self.assertGreaterEqual(diagnostics["freeze_trigger_count"], 1)
        self.assertEqual(len(triggers), diagnostics["freeze_trigger_count"])
        self.assertTrue(all(row["suspicion_run_required"] == 2 for row in rows))
        self.assertGreaterEqual(len(pending), 1)

    def test_freeze_trigger_gate_ignores_prior_suspicion_until_labelled_onset(self):
        # The pre-onset history contains a sustained same-direction excursion.
        # The explicit gate must prevent that history freezing the injected run.
        series = make_series(shift_from=18, shift=2.0)
        onset = "2024"
        rows, diagnostics = build_policy_residuals(
            series,
            policy="suspicion_freeze_baseline_and_scale",
            time_unit="years",
            suspicion_z=2.0,
            suspicion_run=2,
            freeze_trigger_after_time=onset,
        )
        pre_onset = [
            row for row in rows
            if int(row["event_time"]) < int(onset)
        ]
        self.assertTrue(pre_onset)
        self.assertFalse(any(row["freeze_trigger"] for row in pre_onset))
        self.assertFalse(any(row["freeze_active"] for row in pre_onset))
        self.assertGreaterEqual(diagnostics["freeze_trigger_count"], 1)

    def test_fixed_baseline_waits_for_full_window_and_rewarms_after_gap(self):
        series = make_series(count=36, gap_at=18)
        rows, _ = build_policy_residuals(
            series,
            policy="fixed_initial_baseline_fixed_scale",
            time_unit="years",
        )
        before_gap = [row for row in rows if int(row["event_time"]) < 2020]
        after_gap = [row for row in rows if int(row["event_time"]) >= 2020]
        self.assertTrue(before_gap)
        self.assertTrue(after_gap)
        self.assertTrue(all(
            row["reason"] == "fixed_baseline_requires_full_initial_window"
            for row in before_gap[:4]
        ))
        post_gap_rewarm = [
            row for row in after_gap
            if row.get("reason") == "fixed_baseline_requires_full_initial_window"
        ]
        self.assertGreaterEqual(len(post_gap_rewarm), 4)
        first_ready_after_gap = next(
            row for row in after_gap if row["status"] == "ready"
        )
        self.assertGreaterEqual(first_ready_after_gap["support_count"], 12)

    def test_builder_rejects_multiple_entities(self):
        rows = make_series()
        rows.append({
            "entity_id": "entity-2",
            "metric_id": "output",
            "event_time": "2040",
            "value": 22.0,
            "observation_status": "observed",
        })
        with self.assertRaisesRegex(ValueError, "one_entity_metric"):
            build_policy_residuals(
                rows,
                policy="rolling_baseline_rolling_scale",
                time_unit="years",
            )


if __name__ == "__main__":
    unittest.main()
