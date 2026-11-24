import unittest
from datetime import datetime, timezone
import numpy as np
from io import BytesIO
from openpyxl import Workbook

from real_data_stress_pipeline.run_pipeline import (
    g0, g1, boot, parse_pink, longest_run, month, label_month, returns,
    stationary_sample, wilson, series_category, shock_eval, applicable_shock_series,
    aggregate, make_time_support, time_support_registry, TIME_SUPPORT_SCHEMA,
    P2_SOURCE_SCOPE_DECISIONS, usgs_record_rejection_reasons, make_usgs_request_time_support, BELTS, Y1,
)

class StressPipelineContractTests(unittest.TestCase):
    def test_time_support_registry_matches_schema_and_labels_windows_honestly(self):
        registry = time_support_registry()
        self.assertEqual(registry["schema_id"], TIME_SUPPORT_SCHEMA["$id"])
        self.assertEqual(registry["scope"], "source_collection")
        self.assertEqual(registry["record_identity_hash_impact"], "NONE")

        allowed = set(TIME_SUPPORT_SCHEMA["properties"])
        sources = registry["sources"]
        for source_name in ("pink_sheet", "gem"):
            support = sources[source_name]["time_support"]
            self.assertEqual(set(support), allowed)
            self.assertTrue(set(TIME_SUPPORT_SCHEMA["required"]).issubset(support))
            self.assertFalse(sources[source_name]["source_coverage_status"].startswith("ASSERTED"))

        pink = sources["pink_sheet"]["time_support"]
        self.assertEqual(pink["observation_period_start"], "1980-01")
        self.assertEqual(pink["observation_period_end"], "2024-12")
        self.assertIn("ANALYSIS_FILTER_WINDOW", pink["boundary_semantics"])

        gem = sources["gem"]["time_support"]
        self.assertEqual(gem["observation_period_start"], "1990-01")
        self.assertEqual(gem["observation_period_end"], "2023-12")
        self.assertIn("API_QUERY_WINDOW", gem["boundary_semantics"])

        belts = sources["usgs"]["by_belt"]
        self.assertEqual(len(belts), 5)
        for belt in belts.values():
            support = belt["time_support"]
            self.assertEqual(set(support), allowed)
            self.assertEqual(support["native_frequency"], "event_timestamp")
            self.assertEqual(support["observation_period_start"], "1980-01-01T00:00:00Z")
            self.assertEqual(support["observation_period_end"], "2025-01-01T00:00:00Z")
            self.assertIn("ANALYSIS_COLLECTION_WINDOW_START_INCLUSIVE_END_EXCLUSIVE", support["boundary_semantics"])
            self.assertIn(
                "SOURCE_COMCAT_QUERY_WINDOW_START_AND_END_INCLUSIVE_THEN_FILTERED_ON_INGEST",
                support["boundary_semantics"],
            )
            self.assertIn("NOT_MAGNITUDE_COMPLETENESS", support["boundary_semantics"])
            source_query_support = belt["source_query_time_support"]
            self.assertEqual(set(source_query_support), allowed)
            self.assertIn(
                "USGS_COMCAT_API_QUERY_WINDOW_START_AND_END_INCLUSIVE",
                source_query_support["boundary_semantics"],
            )
            analysis_window = belt["analysis_window"]
            self.assertTrue(analysis_window["start_inclusive"])
            self.assertFalse(analysis_window["end_inclusive"])
            self.assertEqual(
                analysis_window["boundary_semantics"],
                "CLIENT_SIDE_ANALYSIS_FILTER_START_INCLUSIVE_END_EXCLUSIVE",
            )
            self.assertFalse(belt["magnitude_completeness_status"] == "ESTABLISHED")

        usgs_analysis_support = sources["usgs"]["time_support"]
        self.assertIn(
            "ANALYSIS_COLLECTION_WINDOW_START_INCLUSIVE_END_EXCLUSIVE",
            usgs_analysis_support["boundary_semantics"],
        )
        source_query_support = sources["usgs"]["source_query_time_support"]
        self.assertIn(
            "USGS_COMCAT_API_QUERY_WINDOW_START_AND_END_INCLUSIVE",
            source_query_support["boundary_semantics"],
        )
        self.assertEqual(
            usgs_analysis_support["observation_period_start"],
            source_query_support["observation_period_start"],
        )
        self.assertEqual(
            usgs_analysis_support["observation_period_end"],
            source_query_support["observation_period_end"],
        )
        source_analysis_window = sources["usgs"]["analysis_window"]
        self.assertEqual(source_analysis_window["period_start"], "1980-01-01T00:00:00Z")
        self.assertEqual(source_analysis_window["period_end"], "2025-01-01T00:00:00Z")
        self.assertTrue(source_analysis_window["start_inclusive"])
        self.assertFalse(source_analysis_window["end_inclusive"])

    def test_usgs_api_includes_end_boundary_but_analysis_excludes_it(self):
        belt = BELTS[0]
        latitude = (float(belt["minlatitude"]) + float(belt["maxlatitude"])) / 2
        longitude = (float(belt["minlongitude"]) + float(belt["maxlongitude"])) / 2
        analysis_end_ms = int(
            datetime(Y1 + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
        )
        at_exclusive_analysis_end = usgs_record_rejection_reasons(
            belt, latitude, longitude, 5.0, analysis_end_ms
        )
        just_before_analysis_end = usgs_record_rejection_reasons(
            belt, latitude, longitude, 5.0, analysis_end_ms - 1
        )
        self.assertIn("OUTSIDE_ANALYSIS_TIME_WINDOW", at_exclusive_analysis_end)
        self.assertNotIn("OUTSIDE_ANALYSIS_TIME_WINDOW", just_before_analysis_end)

        registry = time_support_registry()["sources"]["usgs"]
        analysis_semantics = registry["time_support"]["boundary_semantics"]
        request_semantics = make_usgs_request_time_support(
            "1980-01-01T00:00:00",
            "2025-01-01T00:00:00",
        )["boundary_semantics"]
        self.assertIn(
            "ANALYSIS_COLLECTION_WINDOW_START_INCLUSIVE_END_EXCLUSIVE",
            analysis_semantics,
        )
        self.assertIn(
            "SOURCE_COMTRADE_QUERY_WINDOW_START_AND_END_INCLUSIVE_THEN_FILTERED_ON_INGEST",
            analysis_semantics,
        )
        self.assertIn(
            "USGS_COMCAT_API_REQUEST_WINDOW_START_AND_END_INCLUSIVE",
            request_semantics,
        )
        self.assertFalse(registry["analysis_window"]["end_inclusive"])

    def test_p2_source_scope_quarantines_deferred_sources_without_rewriting_engine1_lineage(self):
        decisions = P2_SOURCE_SCOPE_DECISIONS
        self.assertEqual(decisions["scope"], "P2.2")
        self.assertEqual(
            set(decisions["decisions"]),
            {"COMTRADE", "OECD_PMR", "WGI"},
        )
        for decision in decisions["decisions"].values():
            self.assertEqual(decision["status"], "QUARANTINED_OUT_OF_SCOPE")
        self.assertEqual(
            decisions["scope_effect"],
            "P2_SCOPE_ONLY; ENGINE1_GLOBAL_SOURCE_LINEAGE_UNCHANGED",
        )

    def test_time_support_rejects_empty_schema_values(self):
        with self.assertRaisesRegex(ValueError, "empty_required_value"):
            make_time_support("", "2024-12", "monthly", "TEST")

    def test_world_bank_month_encodings(self):
        self.assertEqual(month("1980M01"), 1980 * 12)
        self.assertEqual(month("1980-M1"), 1980 * 12)
        self.assertEqual(month("1980-01"), 1980 * 12)
        self.assertEqual(month("198001"), 1980 * 12)
        self.assertIsNone(month("1980"))
        self.assertIsNone(month("1980M13"))

    def test_month_label_round_trip(self):
        self.assertEqual(label_month(2024 * 12 + 11), "2024-12")

    def test_contiguous_selection_does_not_fill_gaps(self):
        xs, ys = longest_run({1: 10.0, 2: 11.0, 4: 13.0, 5: 14.0, 6: 15.0})
        self.assertEqual(xs, [4, 5, 6])
        self.assertEqual(ys, [13.0, 14.0, 15.0])

    def test_log_returns_only_use_adjacent_points(self):
        xs, ys = returns([1970*12+1, 1970*12+2, 1970*12+3], [10.0, 11.0, 12.1])
        self.assertEqual(xs, ["1970-03", "1970-04"])
        self.assertAlmostEqual(ys[0], np.log(1.1), places=12)
        self.assertAlmostEqual(ys[1], np.log(1.1), places=12)

    def test_g0_rejects_short_and_degenerate(self):
        self.assertFalse(g0(np.linspace(0.01, 0.05, 86), 87)["passed"])
        self.assertFalse(g0([0.0] * 100, 87)["passed"])

    def test_g0_accepts_non_degenerate_long_series(self):
        values = np.random.default_rng(12).normal(0, 0.01, 540)
        self.assertTrue(g0(values, 501)["passed"])

    def test_stationary_bootstrap_is_repeatable(self):
        values = np.arange(100, dtype=float)
        left = stationary_sample(values, np.random.default_rng(5), 12)
        right = stationary_sample(values, np.random.default_rng(5), 12)
        np.testing.assert_array_equal(left, right)
        self.assertEqual(left.size, values.size)

    def test_wilson_interval(self):
        low, high = wilson(5, 100)
        self.assertLess(low, 0.05)
        self.assertGreater(high, 0.05)
        self.assertIsNone(wilson(0, 0))

    def test_g1_passes_stationary_white_noise_screen(self):
        values = np.random.default_rng(12).normal(0, 0.01, 540)
        result = g1(values)
        self.assertTrue(result["passed"], result)
        self.assertLess(result["adf_p_value"], 0.05)
        self.assertGreaterEqual(result["kpss_p_value"], 0.05)

    def test_g1_rejects_trended_series(self):
        values = np.linspace(0, 10, 540) + np.random.default_rng(12).normal(0, 0.01, 540)
        result = g1(values)
        self.assertFalse(result["passed"])
        self.assertFalse(result["kpss_does_not_reject_level_stationarity"])

    def test_g1_does_not_test_short_series(self):
        result = g1(np.random.default_rng(4).normal(size=86))
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "NOT_TESTED")

    def test_stationary_bootstrap_is_skipped_when_g1_fails(self):
        result = boot(
            np.random.default_rng(4).normal(size=100),
            "test-series",
            12,
            {"passed": False, "status": "SCREEN_FAIL"},
        )
        self.assertEqual(result["status"], "SKIPPED_G1_SCREEN_FAILED")
        self.assertEqual(result["replicates"], 0)
        self.assertTrue(all(mode["runs"] == 0 for mode in result["by_mode"].values()))


    def test_series_categories_respect_domain_terms(self):
        self.assertEqual(series_category({"domain": "commodity", "name": "Crude Oil, Brent"}), "energy")
        self.assertEqual(series_category({"domain": "commodity", "name": "Copper"}), "metals")
        self.assertEqual(series_category({"domain": "commodity", "name": "Cocoa"}), "agriculture_food")
        self.assertEqual(series_category({"domain": "macro", "name": "CPI"}), "macro")

    def test_oil_anchor_excludes_non_energy_series(self):
        import json
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[1] / "shock_event_contract.json").read_text(encoding="utf-8"))
        copper = {"domain": "commodity", "name": "Copper", "axis": ["2014-06"]}
        results = shock_eval(copper, [], contract)
        oil = next(x for x in results if x["event_id"] == "OIL_2014")
        self.assertFalse(oil["eligible"])

    def test_alarm_is_not_reused_for_overlapping_anchor_windows(self):
        import json
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[1] / "shock_event_contract.json").read_text(encoding="utf-8"))
        series = {"domain": "macro", "name": "GEM CPI", "axis": ["2021-02"]}
        events = [{"detection_time": 0, "status": "CONFIRMED"}]
        matches = shock_eval(series, events, contract)
        matched = [x for x in matches if x["matched"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["event_id"], "COVID_2020")


    def test_pink_sheet_two_row_header_preserves_commodity_codes_and_units(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Monthly Prices"
        sheet.append(["World Bank Commodity Prices"])
        sheet.append(["Metadata row"])
        sheet.append(["Metadata row"])
        sheet.append(["Period", "OIL_BRENT", "iCOPPER", "iWHEAT_US_HRW"])
        sheet.append(["", "$/bbl", "$/mt", "$/mt"])
        sheet.append(["1980M01", 10.0, 20.0, 30.0])
        sheet.append(["1980M02", 11.0, 21.0, 31.0])
        payload = BytesIO()
        workbook.save(payload)
        parsed, layout = parse_pink(payload.getvalue())
        self.assertEqual(set(parsed), {"OIL_BRENT", "iCOPPER", "iWHEAT_US_HRW"})
        self.assertEqual(parsed["OIL_BRENT"][1980 * 12], 10.0)
        self.assertEqual(layout["units_by_series"]["OIL_BRENT"], "$/bbl")
        self.assertEqual(layout["units_by_series"]["iCOPPER"], "$/mt")
        workbook.close()

    def test_native_pink_sheet_codes_are_categorized(self):
        self.assertEqual(series_category({"domain": "commodity", "name": "OIL_BRENT"}), "energy")
        self.assertEqual(series_category({"domain": "commodity", "name": "iCOPPER"}), "metals")
        self.assertEqual(series_category({"domain": "commodity", "name": "iWHEAT_US_HRW"}), "agriculture_food")


    def test_unrelated_commodity_is_excluded_from_shock_alarm_burden(self):
        contract = {
            "events": [
                {"id": "GFC", "applicable_categories": ["macro", "energy"]},
                {"id": "OIL", "applicable_categories": ["energy"]},
            ]
        }
        item = {"source": "pink_sheet", "frequency": "monthly", "domain": "commodity", "name": "Rubber"}
        self.assertFalse(applicable_shock_series(item, contract))

    def test_macro_series_is_in_shock_matching_cohort(self):
        contract = {"events": [{"id": "COVID", "applicable_categories": ["macro"]}]}
        item = {"source": "gem", "frequency": "monthly", "domain": "macro", "name": "CPI"}
        self.assertTrue(applicable_shock_series(item, contract))

    def test_bootstrap_aggregation_separates_cohorts_and_representations(self):
        modes = ("fast", "markov_cusum", "consensus")

        def make_series(cohort, representation, alarms, runs=1000):
            return {
                "cohort": cohort,
                "duration_years": 10.0,
                "g1": {"passed": True},
                "detector": {
                    mode: {
                        "alarm_count": 0,
                        "unassociated_structural_alarm_count": None,
                        "shock_matches": [],
                    }
                    for mode in modes
                },
                "bootstrap": {
                    "series_representation": representation,
                    "by_mode": {
                        mode: {"alarms": alarms, "runs": runs}
                        for mode in modes
                    },
                },
            }

        result = aggregate(
            [
                make_series("strict_long_monthly", "level", 200),
                make_series("strict_long_monthly", "returns", 900),
                make_series("seismic_event_interarrival", "differences", 800),
            ],
            {"events": []},
        )

        cohorts = result["by_cohort"]
        commodity = cohorts["strict_long_monthly"]["by_representation"]
        seismic = cohorts["seismic_event_interarrival"]["by_representation"]

        self.assertAlmostEqual(
            commodity["level"]["markov_cusum"]["conditional_bootstrap_alarm_probability_mean"],
            0.20,
        )
        self.assertAlmostEqual(
            commodity["returns"]["markov_cusum"]["conditional_bootstrap_alarm_probability_mean"],
            0.90,
        )
        self.assertAlmostEqual(
            seismic["differences"]["markov_cusum"]["conditional_bootstrap_alarm_probability_mean"],
            0.80,
        )
        self.assertEqual(commodity["level"]["markov_cusum"]["bootstrap_eligible_series"], 1)
        self.assertEqual(commodity["returns"]["markov_cusum"]["bootstrap_eligible_series"], 1)
        self.assertEqual(seismic["differences"]["markov_cusum"]["bootstrap_eligible_series"], 1)
        self.assertNotIn("by_mode", result)

    def test_bootstrap_output_uses_conditional_alarm_probability_name(self):
        result = boot(
            np.random.default_rng(12).normal(size=120),
            "bootstrap-name-test",
            12,
            {"passed": True, "status": "SCREEN_PASS"},
        )
        self.assertIn("alarm_probability", result["by_mode"]["fast"])
        self.assertNotIn("fpr", result["by_mode"]["fast"])

if __name__ == "__main__":
    unittest.main()
