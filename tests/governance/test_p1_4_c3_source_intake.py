from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "p1_4_validation"
    / "c3"
    / "alfred_first_release_intake.py"
)
SPEC = importlib.util.spec_from_file_location("c3_alfred_intake", MODULE_PATH)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


class C3SourceIntakeTests(unittest.TestCase):
    def test_extracts_only_real_vintage_dates_inside_capture_window(self):
        html = """
        <select name="vintage_dates" multiple>
          <option value="">Select</option>
          <option value="2004-07-30">Jul 30, 2004</option>
          <option value="2004-09-03">Sep 3, 2004</option>
          <option value="2004-10-07">Oct 7, 2004</option>
        </select>
        """
        self.assertEqual(
            runner.extract_vintage_dates(html, "2004-08-01", "2004-10-01"),
            ["2004-09-03"],
        )

    def test_first_non_missing_vintage_is_the_initial_value(self):
        csv_text = (
            "observation_date,UNRATE_20040903,UNRATE_20041007\n"
            "2004-08-01,5.4,5.3\n"
            "2004-09-01,.,5.4\n"
        )
        result = runner.parse_vintage_batch(
            csv_text, "UNRATE", ["2004-09-03", "2004-10-07"]
        )
        self.assertEqual(result["2004-08-01"], {
            "value": "5.4", "available_at": "2004-09-03"
        })
        self.assertEqual(result["2004-09-01"], {
            "value": "5.4", "available_at": "2004-10-07"
        })

    def test_rejects_unexpected_snapshot_headers(self):
        csv_text = "observation_date,UNRATE_20040904\n2004-08-01,5.4\n"
        with self.assertRaisesRegex(ValueError, "ALFRED_HEADER_MISMATCH"):
            runner.parse_vintage_batch(csv_text, "UNRATE", ["2004-09-03"])

    def test_contract_keeps_detector_execution_out_of_intake(self):
        contract = json.loads(
            (MODULE_PATH.parent / "c3_source_contract_v1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(contract["guardrails"]["no_detector_execution_in_intake_phase"])
        self.assertEqual(len(contract["events"]), 3)
        self.assertEqual(
            {x["series_id"] for x in contract["events"]},
            {"UNRATE", "ICSA", "WCOILBRENTEU"},
        )

    def test_first_release_order_is_not_reversed(self):
        ordered = ["2004-09-03", "2004-10-07", "2004-11-05"]
        self.assertEqual(ordered, sorted(ordered))


if __name__ == "__main__":
    unittest.main()
