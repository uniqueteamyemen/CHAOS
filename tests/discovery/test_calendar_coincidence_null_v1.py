import unittest

from discovery_engine.calendar_coincidence_null_v1 import (
    CalendarNullError,
    run_conditional_calendar_null,
)


def contract(replicates=1000):
    return {
        "contract_id": "CHAOS_CONDITIONAL_CALENDAR_COINCIDENCE_NULL_V1",
        "replicates": replicates,
        "seed": 20261121,
        "minimum_segment_observations": 5,
        "point_reference_observations_each_side": 4,
        "minimum_entity_support": 5,
        "input_year_range": [2000, 2024],
    }


def point(entity, year=2020, direction="BELOW_LOCAL_REFERENCE"):
    return {
        "series_id": f"series:{entity}:wdi_gdp",
        "entity_id": entity,
        "metric_id": "wdi__NY.GDP.MKTP.KD.ZG",
        "candidate_type": "isolated_point_anomaly",
        "candidate_year": year,
        "direction": direction,
    }


def split(entity, year, support_position):
    return {
        "series_id": f"series:{entity}:eia",
        "entity_id": entity,
        "metric_id": "eia__energy_consumption_per_capita",
        "candidate_type": "level_shift",
        "candidate_year": year,
        "direction": "DOWN",
        "support_position": support_position,
    }


class ConditionalCalendarNullTests(unittest.TestCase):
    def test_null_is_deterministic_and_not_detector_fpr(self):
        candidates = [point(f"E{i}") for i in range(10)]
        first = run_conditional_calendar_null(candidates=candidates, contract=contract())
        second = run_conditional_calendar_null(candidates=candidates, contract=contract())
        self.assertEqual(first, second)
        self.assertFalse(first["null_is_detector_fpr"])
        self.assertFalse(first["causal_claims_permitted"])
        self.assertFalse(first["forecasting_performed"])
        self.assertEqual(first["candidate_count_conditioned_on"], 10)
        self.assertGreaterEqual(first["global_max_conditional_p"], 0.0)
        self.assertLessEqual(first["global_max_conditional_p"], 1.0)

    def test_point_candidates_use_only_symmetric_reference_years(self):
        result = run_conditional_calendar_null(
            candidates=[point("A", 2004), point("B", 2020)],
            contract=contract(),
        )
        self.assertEqual(result["eligible_year_support"]["point_anomaly"], [2004, 2020])

    def test_split_boundary_candidates_keep_boundary_year_support(self):
        result = run_conditional_calendar_null(
            candidates=[split("A", 2005, "MINIMUM_SEGMENT_EDGE"),
                        split("B", 2020, "MINIMUM_SEGMENT_EDGE")],
            contract=contract(),
        )
        self.assertEqual(result["eligible_year_support"]["split_boundary"], [2005, 2020])

    def test_split_interior_candidates_keep_interior_year_support(self):
        result = run_conditional_calendar_null(
            candidates=[split("A", 2006, "INTERIOR"), split("B", 2019, "INTERIOR")],
            contract=contract(),
        )
        self.assertEqual(result["eligible_year_support"]["split_interior"], [2006, 2019])

    def test_duplicate_series_candidate_fails_closed(self):
        item = point("A")
        with self.assertRaisesRegex(CalendarNullError, "duplicate_candidate_per_series_type"):
            run_conditional_calendar_null(candidates=[item, dict(item)], contract=contract())


if __name__ == "__main__":
    unittest.main()
