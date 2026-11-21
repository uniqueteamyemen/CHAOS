from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.adapters.build_wdi_trade_domain_states import build_wdi_trade_domain_states


class WdiTradeDomainStateBuilderTests(unittest.TestCase):
    def _write_inputs(self, root: Path, values=None):
        values = values or ["001.2300", "9.75"]
        source = root / "observed.csv"
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "Country Name", "Country Code", "Indicator Name",
                "Indicator Code", "year", "value_raw",
            ])
            writer.writeheader()
            writer.writerow({
                "Country Name": "Testland", "Country Code": "TST",
                "Indicator Name": "Trade (% of GDP)", "Indicator Code": "NE.TRD.GNFS.ZS",
                "year": "2000", "value_raw": values[0],
            })
            writer.writerow({
                "Country Name": "Testland", "Country Code": "TST",
                "Indicator Name": "Exports (% of GDP)", "Indicator Code": "NE.EXP.GNFS.ZS",
                "year": "2001", "value_raw": values[1],
            })

        metadata = root / "metadata.csv"
        with metadata.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["Series Code", "Indicator Name", "Unit of measure"])
            writer.writeheader()
            writer.writerow({
                "Series Code": "NE.TRD.GNFS.ZS",
                "Indicator Name": "Trade (% of GDP)",
                "Unit of measure": "%",
            })
            writer.writerow({
                "Series Code": "NE.EXP.GNFS.ZS",
                "Indicator Name": "Exports (% of GDP)",
                "Unit of measure": "%",
            })

        extract = root / "extract.json"
        extract.write_text(json.dumps({\n            "observed_rows": 2,\n            "entities": 1,\n            "indicator_codes": ["NE.TRD.GNFS.ZS", "NE.EXP.GNFS.ZS"],\n            "years": [2000, 2001],\n            "external_raw_sha256": "a" * 64,\n        }), encoding="utf-8")
        return source, metadata, extract

    def test_build_preserves_raw_value_lexemes_and_native_time(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root)
            output = root / "states.jsonl"
            summary_path = root / "summary.json"
            summary = build_wdi_trade_domain_states(source, metadata, extract, output, summary_path)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(summary["records"], 2)
        self.assertEqual(summary["entities"], 1)
        self.assertEqual(summary["native_frequency"], "annual")
        trade_record = next(
            item for item in records
            if item["source_observations"]["indicator_code"] == "NE.TRD.GNFS.ZS"
        )
        self.assertEqual(trade_record["source_observations"]["value_raw"], "001.2300")
        identity = trade_record["source_observations"]["source_record_identity"]
        self.assertTrue(identity["logical_record_id"].startswith("lrid:v1:sha256:"))
        self.assertTrue(identity["canonical_record_id"].startswith("crid:v1:sha256:"))
        self.assertEqual(identity["identity_basis"], "periodic_series_key")
        self.assertIsNone(identity["available_at"])
        self.assertEqual(identity["point_in_time_eligibility"], "UNKNOWN")
        self.assertEqual(trade_record["timestamp"], 2000)
        self.assertEqual(summary["time_support"], {
            "observation_period_start": "2000",
            "observation_period_end": "2001",
            "native_frequency": "annual",
            "boundary_semantics": "SOURCE_EXTRACT_DECLARED",
        })
        self.assertEqual(summary["source_observation_identity"]["records"], 2)
        self.assertEqual(summary["source_observation_identity"]["unknown_available_at"], 2)
        self.assertEqual(summary["source_observation_identity"]["known_available_at"], 0)
        self.assertIsNone(trade_record["state_probability"])
        self.assertEqual(trade_record["edge_status"], "not_testable")
        self.assertFalse(summary["edge_evaluation_performed"])


    def test_logical_slot_is_stable_across_value_revisions_and_numeric_lexemes(self):
        from scripts.adapters.build_wdi_trade_domain_states import canonical_record

        metadata = {
            "NE.TRD.GNFS.ZS": {
                "indicator_name": "Trade (% of GDP)",
                "unit_of_measure": "%",
            }
        }
        base = {
            "Country Name": "Testland",
            "Country Code": "TST",
            "Indicator Name": "Trade (% of GDP)",
            "Indicator Code": "NE.TRD.GNFS.ZS",
            "year": "2000",
            "value_raw": "001.2300",
        }
        first = canonical_record(dict(base), metadata)["source_observations"]["source_record_identity"]
        equivalent = canonical_record(dict(base, value_raw="1.23"), metadata)["source_observations"]["source_record_identity"]
        revised = canonical_record(dict(base, value_raw="2.5"), metadata)["source_observations"]["source_record_identity"]

        self.assertEqual(first["logical_record_id"], equivalent["logical_record_id"])
        self.assertEqual(first["logical_record_id"], revised["logical_record_id"])
        self.assertEqual(first["canonical_record_id"], equivalent["canonical_record_id"])
        self.assertNotEqual(first["canonical_record_id"], revised["canonical_record_id"])

    def test_decimal_precision_that_cannot_roundtrip_to_json_number_is_rejected(self):
        from scripts.adapters.build_wdi_trade_domain_states import canonical_record

        metadata = {
            "NE.TRD.GNFS.ZS": {
                "indicator_name": "Trade (% of GDP)",
                "unit_of_measure": "%",
            }
        }
        row = {
            "Country Name": "Testland",
            "Country Code": "TST",
            "Indicator Name": "Trade (% of GDP)",
            "Indicator Code": "NE.TRD.GNFS.ZS",
            "year": "2000",
            "value_raw": "0.1234567890123456789012345678",
        }
        with self.assertRaisesRegex(ValueError, "source_value_not_roundtrip_safe"):
            canonical_record(row, metadata)

    def test_output_is_byte_deterministic_for_same_inputs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root)
            output = root / "states.jsonl"
            summary_path = root / "summary.json"
            build_wdi_trade_domain_states(source, metadata, extract, output, summary_path)
            first = output.read_bytes()
            build_wdi_trade_domain_states(source, metadata, extract, output, summary_path)
            second = output.read_bytes()
        self.assertEqual(first, second)

    def test_invalid_non_numeric_value_fails_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root, values=["not-a-number", "9.75"])
            output = root / "states.jsonl"
            summary_path = root / "summary.json"
            with self.assertRaisesRegex(ValueError, "source_value_not_decimal"):
                build_wdi_trade_domain_states(source, metadata, extract, output, summary_path)
            self.assertFalse(output.exists())
            self.assertFalse(summary_path.exists())

    def test_source_sha256_must_match_the_prior_edge_input_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root)
            edge_integrity = root / "edge-integrity.json"
            edge_integrity.write_text(json.dumps({"source_sha256": "b" * 64}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_sha256_mismatch"):
                build_wdi_trade_domain_states(
                    source, metadata, extract, root / "states.jsonl",
                    root / "summary.json", edge_integrity,
                )

    def test_extract_row_count_mismatch_fails_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root)
            extract.write_text(json.dumps({"observed_rows": 3}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "extract_row_count_mismatch"):
                build_wdi_trade_domain_states(
                    source, metadata, extract, root / "states.jsonl", root / "summary.json"
                )

    def test_duplicate_source_slot_fails_closed_without_silent_deduplication(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, metadata, extract = self._write_inputs(root)
            with source.open("a", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["Testland", "TST", "Trade (% of GDP)", "NE.TRD.GNFS.ZS", "2000", "2.0"])
            extract.write_text(json.dumps({"observed_rows": 3}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate_source_slot"):
                build_wdi_trade_domain_states(
                    source, metadata, extract, root / "states.jsonl", root / "summary.json"
                )


if __name__ == "__main__":
    unittest.main()
