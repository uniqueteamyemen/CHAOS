import unittest
from datetime import datetime, timedelta, timezone

from real_data_stress_pipeline.diagnostics.gardner_knopoff import (
    decimal_year, gardner_knopoff_declustering, gardner_knopoff_windows, haversine_km,
)


def event(event_id, days, magnitude, lat=0.0, lon=0.0):
    stamp = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=days)
    return {"id": event_id, "time": stamp.isoformat(), "magnitude": magnitude,
            "latitude": lat, "longitude": lon}


class GardnerKnopoffTests(unittest.TestCase):
    def test_original_gk1_window_equations(self):
        distance, days = gardner_knopoff_windows(5.0)
        self.assertAlmostEqual(distance, 10 ** (0.1238 * 5.0 + 0.983), places=10)
        self.assertAlmostEqual(days, 10 ** (0.5409 * 5.0 - 0.547), places=10)

    def test_large_magnitude_uses_alternate_time_equation(self):
        _, days = gardner_knopoff_windows(6.5)
        self.assertAlmostEqual(days, 10 ** (0.032 * 6.5 + 2.7389), places=10)

    def test_haversine_handles_antimeridian(self):
        distance = haversine_km(0.0, 179.9, 0.0, -179.9)
        self.assertGreater(distance, 20.0)
        self.assertLess(distance, 23.0)

    def test_largest_event_is_retained_and_dependents_are_labeled(self):
        catalog = [event("main", 0, 6.0),
                   event("aftershock", 1, 4.8, lat=0.05),
                   event("foreshock", -1, 4.6, lat=0.02, lon=0.01),
                   event("background", 800, 4.7, lat=10, lon=10)]
        labeled, summary = gardner_knopoff_declustering(catalog)
        rows = {row["id"]: row for row in labeled}
        self.assertEqual(rows["main"]["declustering_role"], "MAINSHOCK")
        self.assertEqual(rows["aftershock"]["declustering_role"], "AFTERSHOCK")
        self.assertEqual(rows["foreshock"]["declustering_role"], "FORESHOCK")
        self.assertEqual(rows["background"]["declustering_role"], "BACKGROUND")
        self.assertEqual(summary["events_input"], 4)
        self.assertEqual(summary["retained_events"], 2)
        self.assertEqual(summary["cluster_mainshocks_retained"], 1)
        self.assertEqual(summary["dependent_events_removed"], 2)

    def test_backward_window_fraction(self):
        catalog = [event("main", 0, 6.0), event("old", -300, 4.8)]
        half, _ = gardner_knopoff_declustering(catalog, 0.5)
        full, _ = gardner_knopoff_declustering(catalog, 1.0)
        self.assertEqual({x["id"]: x["declustering_role"] for x in half}["old"], "BACKGROUND")
        self.assertEqual({x["id"]: x["declustering_role"] for x in full}["old"], "FORESHOCK")

    def test_unclustered_larger_event_can_be_captured_by_later_cluster(self):
        catalog = [
            event("larger_singleton", 0, 6.0, lat=0.0, lon=0.0),
            event("smaller_main", 1, 5.0, lat=0.0, lon=5.0),
            event("smaller_aftershock", 2, 4.0, lat=0.02, lon=5.0),
        ]
        labeled, _ = gardner_knopoff_declustering(catalog)
        rows = {row["id"]: row for row in labeled}
        self.assertEqual(rows["larger_singleton"]["declustering_role"], "BACKGROUND")
        self.assertEqual(rows["smaller_main"]["declustering_role"], "MAINSHOCK")
        self.assertEqual(rows["smaller_aftershock"]["declustering_role"], "AFTERSHOCK")

    def test_deterministic_labels_for_equal_magnitudes(self):
        catalog = [event("z", 2, 5.0, 20, 20), event("a", 1, 5.0, -20, -20)]
        one, _ = gardner_knopoff_declustering(catalog)
        two, _ = gardner_knopoff_declustering(list(reversed(catalog)))
        self.assertEqual([(x["id"], x["declustering_role"], x["cluster_id"]) for x in one],
                         [(x["id"], x["declustering_role"], x["cluster_id"]) for x in two])

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_event_id"):
            gardner_knopoff_declustering([event("same", 0, 5), event("same", 1, 4)])

    def test_naive_timestamp_rejected(self):
        invalid = event("naive", 0, 5)
        invalid["time"] = "2000-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            gardner_knopoff_declustering([invalid])

    def test_invalid_fraction_rejected(self):
        with self.assertRaises(ValueError):
            gardner_knopoff_declustering([event("one", 0, 5)], 1.5)


    def test_decimal_year_matches_hmtk_fixed_365_day_clock(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        leap_day = datetime(2020, 2, 29, 23, 59, tzinfo=timezone.utc)
        same_day = datetime(2020, 2, 29, 0, 1, tzinfo=timezone.utc)
        self.assertAlmostEqual(decimal_year(start), 2020.0)
        self.assertAlmostEqual(decimal_year(leap_day), 2020.0 + 59 / 365.0, places=10)
        # HMTK discards time-of-day; same UTC dates must share a coordinate.
        self.assertAlmostEqual(decimal_year(leap_day), decimal_year(same_day), places=12)


if __name__ == "__main__":
    unittest.main()
