import tempfile
import unittest
from pathlib import Path

from discovery_engine.weo_vintage_audit_v1 import (
    VintageAuditError,
    event_year_status,
    parse_latest_actual_year,
    read_weo_country_file,
    theil_sen_pretrend_reference,
)


HEADER = [
    "Country", "WEO Country Code", "ISO", "WEO Subject Code",
    "Subject Descriptor", "Subject Notes", "Units", "Scale",
    "Country/Series-specific Notes", "Estimates Start After",
    "2016", "2017", "2018", "2019", "2020",
]


class WeoVintageAuditTests(unittest.TestCase):
    def write_tsv(self, path, rows):
        path.write_text(
            "WEO test file\nRelease: test\n"
            + "\t".join(HEADER) + "\n"
            + "\n".join("\t".join(row) for row in rows) + "\n",
            encoding="utf-8",
        )

    def row(self, iso, latest_actual, event_value="-4.0"):
        return [
            "Testland", "999", iso, "NGDP_RPCH", "GDP growth", "",
            "Percent change", "Units", "", str(latest_actual),
            "2.0", "3.0", "2.0", "1.0", event_value,
        ]

    def test_parse_tab_delimited_weo_and_preserve_estimate_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            self.write_tsv(path, [self.row("TST", 2019)])
            result = read_weo_country_file(
                path, subject_code="NGDP_RPCH", years=[2016, 2017, 2018, 2019, 2020]
            )
        self.assertEqual(set(result), {"TST"})
        self.assertEqual(result["TST"]["values"]["2020"], -4.0)
        self.assertEqual(result["TST"]["latest_actual_year"], 2019)
        self.assertEqual(result["TST"]["event_year_data_status"], "ESTIMATE_OR_PROJECTION")
        self.assertTrue(result["TST"]["pretrend_all_actual"])

    def test_2020_is_actual_only_when_latest_actual_year_reaches_2020(self):
        self.assertEqual(parse_latest_actual_year("2020"), 2020)
        self.assertEqual(event_year_status(2020, 2020), "ACTUAL")
        self.assertEqual(event_year_status(2020, 2019), "ESTIMATE_OR_PROJECTION")
        self.assertEqual(event_year_status(2020, 0), "ESTIMATE_OR_PROJECTION")
        self.assertEqual(event_year_status(2020, None), "UNKNOWN")

    def test_duplicate_iso_subject_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            self.write_tsv(path, [self.row("TST", 2019), self.row("TST", 2020)])
            with self.assertRaisesRegex(VintageAuditError, "duplicate_weo_iso_subject_row"):
                read_weo_country_file(
                    path, subject_code="NGDP_RPCH", years=[2016, 2017, 2018, 2019, 2020]
                )

    def test_theil_sen_pretrend_extrapolates_linear_growth(self):
        self.assertAlmostEqual(
            theil_sen_pretrend_reference([1.0, 2.0, 3.0, 4.0]), 5.0
        )

    def test_theil_sen_pretrend_resists_one_pre_event_outlier(self):
        result = theil_sen_pretrend_reference([1.0, 2.0, 30.0, 4.0])
        self.assertTrue(-15.0 < result < 30.0)

    def test_missing_vintage_year_values_are_not_silently_filled(self):
        row = self.row("TST", 2019)
        row[-1] = ""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            self.write_tsv(path, [row])
            result = read_weo_country_file(
                path, subject_code="NGDP_RPCH", years=[2016, 2017, 2018, 2019, 2020]
            )
        self.assertIsNone(result["TST"]["values"]["2020"])

    def test_estimates_start_after_invalid_value_fails_closed(self):
        with self.assertRaisesRegex(VintageAuditError, "estimates_start_after_invalid"):
            parse_latest_actual_year("unknown")


if __name__ == "__main__":
    unittest.main()

