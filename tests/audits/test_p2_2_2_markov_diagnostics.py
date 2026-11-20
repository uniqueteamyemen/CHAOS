import unittest

from scripts.audits.p2_2_2_markov_diagnostics import (
    build_report,
    quantile,
    summarize_cohort,
)


class MarkovAuditTests(unittest.TestCase):
    def test_quantile_uses_linear_interpolation(self):
        self.assertEqual(quantile([0.0, 1.0, 2.0, 3.0], 0.25), 0.75)
        self.assertEqual(quantile([4.0, 8.0, 12.0], 0.5), 8.0)
        self.assertIsNone(quantile([], 0.5))

    def test_cohorts_are_summarized_independently(self):
        def series(cohort, alarm_probability):
            return {
                "cohort": cohort,
                "duration_years": 10.0,
                "g1": {"passed": True},
                "detector": {
                    mode: {
                        "alarm_count": 1,
                        "diagnostics": (
                            {"rho_raw": 0.1, "rho_used": 0.1,
                             "rho_cusum_used": 0.07,
                             "rho_bias_correction_enabled": False,
                             "rho_cusum_bias_correction_enabled": True}
                            if mode == "markov_cusum" else {}
                        ),
                    }
                    for mode in ("fast", "markov_cusum", "consensus")
                },
                "bootstrap": {
                    "by_mode": {
                        mode: {"alarms": int(alarm_probability * 100),
                               "runs": 100, "events": 1, "errors": 0}
                        for mode in ("fast", "markov_cusum", "consensus")
                    }
                },
            }

        report = build_report({
            "version": "1.4",
            "run_timestamp_utc": "2026-11-17T00:00:00Z",
            "git_commit": "abc",
            "series_results": [
                series("strict_long_monthly", 0.2),
                series("seismic_event_interarrival", 0.8),
            ],
        })

        commodity = report["by_cohort"]["strict_long_monthly"]["by_mode"]["markov_cusum"]
        seismic = report["by_cohort"]["seismic_event_interarrival"]["by_mode"]["markov_cusum"]
        self.assertEqual(
            commodity["conditional_bootstrap_probability_of_one_or_more_alerts"]["mean"],
            0.2,
        )
        self.assertEqual(
            seismic["conditional_bootstrap_probability_of_one_or_more_alerts"]["mean"],
            0.8,
        )
        self.assertNotIn("by_mode", report)
        self.assertEqual(
            commodity["g1_passed_series_reporting_rho_bias_correction_enabled_false"], 1
        )
        self.assertEqual(
            commodity["g1_passed_markov_series_reporting_rho_cusum_bias_correction_enabled_true"],
            1,
        )
        self.assertEqual(
            commodity["g1_passed_markov_series_reporting_rho_cusum_bias_correction_enabled_false"],
            0,
        )
        self.assertEqual(
            commodity["rho_diagnostic_completeness"]["rho_cusum_bias_correction_flag_missing_or_invalid"],
            0,
        )
        self.assertEqual(
            commodity["observed_alert_count_g1_passed_series"]["mean"], 1.0
        )
        self.assertEqual(commodity["rho_raw_g1_passed"]["median"], 0.1)
        self.assertEqual(commodity["rho_clipped_g1_passed"]["median"], 0.1)
        self.assertEqual(commodity["rho_cusum_used_g1_passed"]["median"], 0.07)
        self.assertEqual(
            commodity["rho_diagnostic_completeness"]["rho_cusum_used_available"], 1
        )
        self.assertEqual(
            report["by_cohort"]["strict_long_monthly"]["by_mode"]["fast"]
            ["rho_cusum_used_g1_passed"]["n"], 0
        )

    def test_non_g1_series_is_not_in_bootstrap_comparison_denominator(self):
        def make_series(passed, alarms, runs):
            return {
                "cohort": "strict_long_monthly",
                "duration_years": 10.0,
                "g1": {"passed": passed},
                "detector": {
                    mode: {"alarm_count": alarms, "diagnostics": {}}
                    for mode in ("fast", "markov_cusum", "consensus")
                },
                "bootstrap": {
                    "by_mode": {
                        mode: {"alarms": 20, "runs": runs, "events": 30, "errors": 0}
                        for mode in ("fast", "markov_cusum", "consensus")
                    }
                },
            }

        summary = summarize_cohort([
            make_series(True, 1, 100),
            make_series(False, 99, 0),
        ])["by_mode"]["markov_cusum"]

        self.assertEqual(summary["observed_alert_count_all_series"]["n"], 2)
        self.assertEqual(summary["observed_alert_count_g1_passed_series"]["n"], 1)
        self.assertEqual(summary["observed_alert_count_g1_passed_series"]["mean"], 1.0)
        self.assertEqual(summary["bootstrap_eligible_series"], 1)

    def test_legacy_manifest_missing_rho_cusum_used_is_reported_not_imputed(self):
        legacy_series = {
            "cohort": "strict_long_monthly",
            "g1": {"passed": True},
            "detector": {
                "markov_cusum": {
                    "alarm_count": 0,
                    "diagnostics": {"rho_raw": 0.92, "rho_used": 0.88},
                }
            },
            "bootstrap": {"by_mode": {"markov_cusum": {
                "alarms": 0, "runs": 10, "events": 0, "errors": 0,
            }}},
        }
        summary = summarize_cohort([legacy_series])["by_mode"]["markov_cusum"]
        self.assertEqual(summary["rho_raw_g1_passed"]["median"], 0.92)
        self.assertEqual(summary["rho_clipped_g1_passed"]["median"], 0.88)
        self.assertEqual(summary["rho_cusum_used_g1_passed"]["n"], 0)
        self.assertEqual(
            summary["rho_diagnostic_completeness"]["rho_cusum_used_missing_or_invalid"], 1
        )
        self.assertEqual(
            summary["rho_diagnostic_completeness"]["rho_cusum_bias_correction_flag_missing_or_invalid"],
            1,
        )

    def test_inconsistent_legacy_rho_used_is_not_reported_as_clipped(self):
        series = {
            "g1": {"passed": True},
            "detector": {"markov_cusum": {
                "diagnostics": {
                    "rho_raw": 0.92, "rho_used": 0.70, "rho_cusum_used": 0.65,
                },
            }},
        }
        summary = summarize_cohort([series])["by_mode"]["markov_cusum"]
        self.assertEqual(summary["rho_clipped_g1_passed"]["n"], 0)
        self.assertEqual(
            summary["rho_diagnostic_completeness"]["rho_clipped_inconsistent_with_raw"], 1
        )

    def test_rejects_missing_cohort(self):
        with self.assertRaises(ValueError):
            build_report({"series_results": [{"g1": {"passed": True}}]})


if __name__ == "__main__":
    unittest.main()
