from __future__ import annotations

import unittest

from scripts.p1_4.build_cohort_selection import _assert_manifest_selection


def fixture():
    c1_ids=["c1-a","c1-b"]
    c2_ids=["c2-a","c2-b"]
    c1_pilot=["c1-a"]
    c2_pilot=["c2-b"]
    manifest={
        "cohorts":{
            "C1":{"series_ids":c1_ids,"pilot_series_ids":c1_pilot,
                  "pilot_failure_class_counts":{"A":1,"B":0}},
            "C2":{"series_ids":c2_ids,"pilot_series_ids":c2_pilot,
                  "sample_source_counts":{"gem":2,"pink_sheet":0},
                  "pilot_source_counts":{"gem":1,"pink_sheet":0}},
        },
        "pilot_scope":{"series_ids":["c1-a","c2-b"],"run_cases":38},
    }
    selection={
        "c1":{"pilot_series":[{"series_id":"c1-a"}],
              "failure_class_pilot":{"A":1,"B":0}},
        "c2":{"sample_series":[{"series_id":"c2-a"},{"series_id":"c2-b"}],
              "pilot_series":[{"series_id":"c2-b"}],
              "sample_source_counts":{"gem":2,"pink_sheet":0},
              "pilot_source_counts":{"gem":1,"pink_sheet":0}},
        "pilot_scope":{"series_ids":["c1-a","c2-b"],"run_cases":38},
    }
    # The helper also enforces production cardinalities; this test replaces
    # those checks only through a complete-size fixture below in the integration gate.


class CohortSelectionManifestBindingTests(unittest.TestCase):
    def test_exact_id_set_guard_rejects_any_replacement(self):
        # The production-size contract is covered by the selection workflow;
        # here verify the guard's set comparisons through targeted code review
        # is not sufficient, so exercise the C1/C2/pilot exact equality path.
        # Use a temporary patch of the expected manifest counts by constructing
        # a production-shaped minimal mapping with repeated distinct tokens.
        c1 = [f"c1-{i}" for i in range(147)]
        c2 = [f"c2-{i}" for i in range(50)]
        c1_pilot = c1[:20]
        c2_pilot = c2[:20]
        pilot = sorted(c1_pilot + c2_pilot)
        manifest = {
            "cohorts": {
                "C1": {"series_ids": c1, "pilot_series_ids": c1_pilot,
                       "pilot_failure_class_counts":{"ADF_PASS_KPSS_FAIL":12,
                         "ADF_FAIL_KPSS_FAIL":6,"ADF_FAIL_KPSS_PASS":2}},
                "C2": {"series_ids": c2, "pilot_series_ids": c2_pilot,
                       "sample_source_counts":{"pink_sheet":7,"gem":43},
                       "pilot_source_counts":{"pink_sheet":3,"gem":17}},
            },
            "pilot_scope":{"series_ids":pilot,"run_cases":760},
        }
        selection = {
            "c1":{"pilot_series":[{"series_id":x} for x in c1_pilot],
                  "failure_class_pilot":manifest["cohorts"]["C1"]["pilot_failure_class_counts"]},
            "c2":{"sample_series":[{"series_id":x} for x in c2],
                  "pilot_series":[{"series_id":x} for x in c2_pilot],
                  "sample_source_counts":{"pink_sheet":7,"gem":43},
                  "pilot_source_counts":{"pink_sheet":3,"gem":17}},
            "C2_STRATIFICATION_REPORT":{
                "dimensions":["source","domain","length_band","ar1_abs_band","missingness_pattern"],
                "pilot_is_subset_of_sample":True,
            },
            "pilot_scope":{"series_ids":pilot,"run_cases":760},
        }
        _assert_manifest_selection(selection,manifest)
        selection["pilot_scope"]["series_ids"][-1]="c2-substitute"
        with self.assertRaisesRegex(ValueError,"40_series_pilot_identity_set_differs"):
            _assert_manifest_selection(selection,manifest)


if __name__ == "__main__":
    unittest.main()
