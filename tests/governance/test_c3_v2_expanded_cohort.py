"""Pre-registration checks for C3 v2's expanded historical cohort."""
import json
import unittest
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "p1_4_validation/c3/c3_expanded_event_cohort_v1.json"


def add_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(absolute, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


class C3V2ExpandedCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_frozen_cohort_size_and_episode_clustering(self):
        self.assertEqual(self.contract["contract_id"], "CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1")
        self.assertEqual(len(self.contract["events"]), 20)
        self.assertEqual(len(self.contract["series"]), 4)
        self.assertEqual(self.contract["cohort_design"]["episode_clusters"], 10)
        pairs = sum(len(event["expected_sign_by_series"]) for event in self.contract["events"])
        self.assertEqual(pairs, 37)
        self.assertEqual(self.contract["cohort_design"]["event_series_pairs"], 37)
        self.assertEqual(
            {series["series_id"] for series in self.contract["series"]},
            {"UNRATE", "PAYEMS", "WCOILBRENTEU", "ICSA"},
        )

    def test_registered_anchors_cover_the_preregistered_event_types(self):
        anchor_types = {event["anchor_type"] for event in self.contract["events"]}
        self.assertTrue({
            "NBER_CYCLE_PEAK",
            "NBER_CYCLE_TROUGH",
            "FINANCIAL_CRISIS_MILESTONE",
            "PUBLIC_HEALTH_AND_UNEMPLOYMENT_SHOCK",
            "ENERGY_PRICE_SHOCK",
            "GEOPOLITICAL_SUPPLY_SHOCK",
        }.issubset(anchor_types))

    def test_each_event_pair_has_a_direction_and_series(self):
        series_ids = {row["series_id"] for row in self.contract["series"]}
        event_ids = [row["event_id"] for row in self.contract["events"]]
        self.assertEqual(len(event_ids), len(set(event_ids)))
        for event in self.contract["events"]:
            self.assertTrue(event["episode_id"])
            self.assertTrue(event["reference_urls"])
            self.assertTrue(event["expected_sign_by_series"])
            for series_id, sign in event["expected_sign_by_series"].items():
                self.assertIn(series_id, series_ids)
                self.assertIn(sign, (-1, 1))

    def test_first_forty_observations_precede_every_series_first_anchor(self):
        for series in self.contract["series"]:
            sid = series["series_id"]
            anchors = [
                date.fromisoformat(event["anchor_date"])
                for event in self.contract["events"]
                if sid in event["expected_sign_by_series"]
            ]
            self.assertTrue(anchors, sid)
            start = date.fromisoformat(series["observation_start"])
            if "Monthly" in series["frequency"]:
                prefix_end = add_months(start, 39)
            else:
                prefix_end = start + timedelta(days=39 * 7)
            self.assertLess(prefix_end, min(anchors), sid)

    def test_risk_gate_is_wilson_upper_on_both_development_and_holdout(self):
        rules = self.contract["guardrails"]
        self.assertEqual(rules["development_threshold_rule"],
                         "one-sided Wilson 95% upper bound <= 0.10")
        self.assertEqual(rules["holdout_validation_rule"],
                         "one-sided Wilson 95% upper bound <= 0.10")
        self.assertTrue(rules["holdout_never_used_for_threshold_selection"])

    def test_monthly_and_weekly_sources_are_both_registered(self):
        frequencies = {row["frequency"] for row in self.contract["series"]}
        self.assertTrue(any(value == "Monthly" for value in frequencies))
        self.assertTrue(any(value.startswith("Weekly") for value in frequencies))


if __name__ == "__main__":
    unittest.main()
