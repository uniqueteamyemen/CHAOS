import unittest

from discovery_engine.weo_hf_mirror_v1 import (
    WeoMirrorError,
    source_records_from_rows,
)


class WeoMirrorRowTests(unittest.TestCase):
    def test_extracts_only_exact_publication_subject_and_iso3_rows(self):
        rows = [
            {
                "entity_id": "USA", "entity_name": "United States",
                "series_id": "NGDP_RPCH", "year": 2020, "value": -3.4,
                "publication_year": 2020, "publication_release": "Fall",
            },
            {
                "entity_id": "World", "entity_name": "World",
                "series_id": "NGDP_RPCH", "year": 2020, "value": -3.0,
                "publication_year": 2020, "publication_release": "Fall",
            },
            {
                "entity_id": "CAN", "entity_name": "Canada",
                "series_id": "NGDP_RPCH", "year": 2020, "value": -5.0,
                "publication_year": 2021, "publication_release": "Spring",
            },
            {
                "entity_id": "USA", "entity_name": "United States",
                "series_id": "PCPI", "year": 2020, "value": 1.2,
                "publication_year": 2020, "publication_release": "Fall",
            },
        ]
        result = source_records_from_rows(
            rows,
            publication_year=2020,
            publication_release="Fall",
            subject_code="NGDP_RPCH",
            years=[2016, 2017, 2018, 2019, 2020],
        )
        self.assertEqual(set(result), {"USA"})
        self.assertEqual(result["USA"]["values"]["2020"], -3.4)
        self.assertEqual(
            result["USA"]["event_year_data_status"],
            "UNKNOWN_MIRROR_METADATA_NOT_PRESERVED",
        )
        self.assertIsNone(result["USA"]["latest_actual_year"])

    def test_missing_values_remain_missing(self):
        rows = [{
            "entity_id": "GBR", "entity_name": "United Kingdom",
            "series_id": "NGDP_RPCH", "year": 2020, "value": None,
            "publication_year": 2020, "publication_release": "Fall",
        }]
        result = source_records_from_rows(
            rows,
            publication_year=2020,
            publication_release="Fall",
            subject_code="NGDP_RPCH",
            years=[2020],
        )
        self.assertIsNone(result["GBR"]["values"]["2020"])

    def test_duplicate_country_year_fails_closed(self):
        row = {
            "entity_id": "USA", "entity_name": "United States",
            "series_id": "NGDP_RPCH", "year": 2020, "value": -3.4,
            "publication_year": 2020, "publication_release": "Fall",
        }
        with self.assertRaisesRegex(WeoMirrorError, "mirror_duplicate_iso_year"):
            source_records_from_rows(
                [row, dict(row)],
                publication_year=2020,
                publication_release="Fall",
                subject_code="NGDP_RPCH",
                years=[2020],
            )


if __name__ == "__main__":
    unittest.main()
