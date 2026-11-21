import tempfile
import unittest
from pathlib import Path

from discovery_engine.weo_vintage_audit_v1 import (
    VintageAuditError,
    read_weo_country_file,
    theil_sen_pretrend_projection,
)


HEADER = [
    "Country", "WEO Country Code", "ISO", "WEO Subject Code",
    "Subject Descriptor", "2016", "2017", "2018", "2019", "2020",
    "Estimates Start After",
]


class WeoVintageAuditTests(unittest.TestCase):
    def write_tsv(self, path, rows, preamble=True):
        lines = []
        if preamble:
            lines.extend(["World Economic Outlook Database", "Release: test"])
        lines.append("\t".join(HEADER))
        lines.extend("\t".join(row) for row in rows)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_parse_tab_delimited_weo_with_preamble(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            self.write_tsv(path, [
                ["Testland", "999", "TST", "NGDP_RPCH", "GDP growth", "2.0", "3.0", "2.0", "1.0", "-4.0", "2019"],
                ["Testland", "999", "TST", "PCPI", "Inflation", "2.0", "3.0", "2.0", "1.0", "0.0", "2019"],
            ])
            result = read_weo_country_file(path)
        self.assertEqual(set(result), {"TST"})
        self.assertEqual(result["TST"]["values"]["2020"], -4.0)
        self.assertEqual(result["TST"]["estimates_start_after_raw"], "2019")

    def test_duplicate_iso_subject_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            row = ["Testland", "999", "TST", "NGDP_RPCH", "GDP growth", "2", "3", "2", "1", "-4", "2019"]
            self.write_tsv(path, [row, row], preamble=False)
            with self.assertRaisesRegex(VintageAuditError, "duplicate_weo"):
                read_weo_country_file(path)

    def test_theil_sen_pretrend_extrapolates_linear_growth(self):
        self.assertAlmostEqual(theil_sen_pretrend_projection([1.0, 2.0, 3.0, 4.0]), 5.0)

    def test_theil_sen_pretrend_resists_one_pre_event_outlier(self):
        result = theil_sen_pretrend_projection([1.0, 2.0, 30.0, 4.0])
        self.assertTrue(-15.0 < result < 30.0)

    def test_missing_vintage_year_values_are_not_silently_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            self.write_tsv(path, [
                ["Testland", "999", "TST", "NGDP_RPCH", "GDP growth", "2", "3", "2", "1", "", "2019"]
            ], preamble=False)
            result = read_weo_country_file(path)
        self.assertIsNone(result["TST"]["values"]["2020"])


if __name__ == "__main__":
    unittest.main()
