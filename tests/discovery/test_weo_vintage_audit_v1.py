import tempfile
import unittest
from pathlib import Path

from discovery_engine.weo_vintage_audit_v1 import (
    VintageAuditError,
    read_weo_country_file,
    theil_sen_pretrend_projection,
)


class WeoVintageAuditTests(unittest.TestCase):
    def test_parse_tab_delimited_weo_with_preamble(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            path.write_text(
                "World Economic Outlook Database\\n"
                "Release: test\\n"
                "Country\\tWEO Country Code\\tISO\\tWEO Subject Code\\tSubject Descriptor\\t2016\\t2017\\t2018\\t2019\\t2020\\tEstimates Start After\\n"
                "Testland\\t999\\tTST\\tNGDP_RPCH\\tGDP growth\\t2.0\\t3.0\\t2.0\\t1.0\\t-4.0\\t2019\\n"
                "Testland\\t999\\tTST\\tPCPI\\tInflation\\t2.0\\t3.0\\t2.0\\t1.0\\t0.0\\t2019\\n",
                encoding="utf-8",
            )
            result = read_weo_country_file(path)
        self.assertEqual(set(result), {"TST"})
        self.assertEqual(result["TST"]["values"]["2020"], -4.0)
        self.assertEqual(result["TST"]["estimates_start_after_raw"], "2019")

    def test_duplicate_iso_subject_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weo.xls"
            row = "Testland\\t999\\tTST\\tNGDP_RPCH\\tGDP growth\\t2\\t3\\t2\\t1\\t-4\\t2019\\n"
            path.write_text(
                "Country\\tWEO Country Code\\tISO\\tWEO Subject Code\\tSubject Descriptor\\t2016\\t2017\\t2018\\t2019\\t2020\\tEstimates Start After\\n"
                + row + row,
                encoding="utf-8",
            )
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
            path.write_text(
                "Country\\tWEO Country Code\\tISO\\tWEO Subject Code\\tSubject Descriptor\\t2016\\t2017\\t2018\\t2019\\t2020\\tEstimates Start After\\n"
                "Testland\\t999\\tTST\\tNGDP_RPCH\\tGDP growth\\t2\\t3\\t2\\t1\\t\\t2019\\n",
                encoding="utf-8",
            )
            result = read_weo_country_file(path)
        self.assertIsNone(result["TST"]["values"]["2020"])


if __name__ == "__main__":
    unittest.main()
