import unittest

from observation_foundation.record_identity_v1 import (
    prepare_source_record,
    prepare_source_records,
    build_vintage_chains,
    select_vintages_as_of,
)


def base_record(**changes):
    record = {
        "source_namespace": "usgs.comcat",
        "dataset_id": "catalog-west-01",
        "series_semantics": "event_stream",
        "entity_id": "belt-west",
        "metric_id": "earthquake-magnitude",
        "event_time": "2026-01-01T00:00:00Z",
        "available_at": "2026-01-01T01:00:00Z",
        "source_record_id": "us7000abcd",
        "logical_key": None,
        "source_revision": "r1",
        "value": 5.2,
        "unit": "Mw",
        "observation_status": "observed",
        "transport_metadata": {
            "retrieved_at": "2026-01-02T00:00:00Z",
            "ingest_batch_id": "batch-A",
            "row_number": 17,
        },
    }
    record.update(changes)
    return record


class SourceRecordIdentityTests(unittest.TestCase):
    def test_ingest_metadata_does_not_change_either_identity(self):
        first = prepare_source_record(base_record())
        second = prepare_source_record(base_record(transport_metadata={
            "retrieved_at": "2026-02-01T00:00:00Z",
            "ingest_batch_id": "batch-Z",
            "row_number": 999,
        }))
        self.assertEqual(first["logical_record_id"], second["logical_record_id"])
        self.assertEqual(first["canonical_record_id"], second["canonical_record_id"])

    def test_source_revision_keeps_logical_id_and_changes_canonical_id(self):
        first = prepare_source_record(base_record())
        revised = prepare_source_record(base_record(
            source_revision="r2", available_at="2026-01-03T00:00:00Z", value=5.3
        ))
        self.assertEqual(first["logical_record_id"], revised["logical_record_id"])
        self.assertNotEqual(first["canonical_record_id"], revised["canonical_record_id"])

    def test_declared_natural_key_is_order_independent(self):
        a = prepare_source_record(base_record(
            source_record_id=None,
            logical_key={"event_code": "E-7", "region": "west"},
        ))
        b = prepare_source_record(base_record(
            source_record_id=None,
            logical_key={"region": "west", "event_code": "E-7"},
            transport_metadata={"row_number": 1},
        ))
        self.assertEqual(a["logical_record_id"], b["logical_record_id"])

    def test_vintage_chain_retains_every_version_under_one_logical_id(self):
        first = prepare_source_record(base_record())
        second = prepare_source_record(base_record(
            source_revision="r2", available_at="2026-01-03T00:00:00Z", value=5.3
        ))
        chains = build_vintage_chains([second, first])
        chain = chains["chains"][first["logical_record_id"]]
        self.assertEqual(chains["logical_records"], 1)
        self.assertEqual(chains["canonical_versions"], 2)
        self.assertEqual([item["source_revision"] for item in chain], ["r1", "r2"])

    def test_canonical_order_is_independent_of_input_order(self):
        a = base_record(source_record_id="event-A", event_time="2026-01-01T00:00:00Z")
        b = base_record(source_record_id="event-B", event_time="2026-01-02T00:00:00Z")
        first = prepare_source_records([a, b])
        second = prepare_source_records([b, a])
        self.assertEqual(
            [item["canonical_record_id"] for item in first],
            [item["canonical_record_id"] for item in second],
        )

    def test_no_stable_key_is_explicitly_unresolved(self):
        record = base_record(source_record_id=None, logical_key=None)
        prepared = prepare_source_record(record)
        self.assertIsNone(prepared["logical_record_id"])
        self.assertEqual(prepared["identity_basis"], "UNRESOLVED_NO_STABLE_KEY")

    def test_same_timestamp_event_multiplicity_is_preserved(self):
        first = base_record(source_record_id="event-1")
        second = base_record(source_record_id="event-2")
        prepared = prepare_source_records([first, second])
        self.assertEqual(len(prepared), 2)
        self.assertEqual(len({x["logical_record_id"] for x in prepared}), 2)
        self.assertTrue(all(x["multiplicity_policy"] == "PRESERVE_EACH_OCCURRENCE" for x in prepared))

    def test_period_count_does_not_deduplicate_identical_occurrences(self):
        record = base_record(
            source_record_id=None,
            logical_key=None,
            series_semantics="period_count",
            metric_id="monthly-event-count",
            event_time="2026-01",
        )
        prepared = prepare_source_records([record, dict(record)])
        self.assertEqual(len(prepared), 2)
        self.assertEqual(prepared[0]["canonical_record_id"], prepared[1]["canonical_record_id"])

    def test_numeric_equivalent_values_have_same_canonical_identity(self):
        a = prepare_source_record(base_record(value=5))
        b = prepare_source_record(base_record(value=5.0))
        self.assertEqual(a["canonical_record_id"], b["canonical_record_id"])

    def test_datetime_offsets_are_canonicalized_to_utc(self):
        a = prepare_source_record(base_record(event_time="2026-01-01T03:00:00+03:00"))
        b = prepare_source_record(base_record(event_time="2026-01-01T00:00:00Z"))
        self.assertEqual(a["canonical_record_id"], b["canonical_record_id"])

    def test_naive_available_at_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            prepare_source_record(base_record(available_at="2026-01-01T01:00:00"))

    def test_non_observed_status_requires_null_value(self):
        with self.assertRaisesRegex(ValueError, "non_observed_status_requires_null_value"):
            prepare_source_record(base_record(observation_status="missing", value=0))

    def test_as_of_selects_latest_vintage_not_future_revision(self):
        first = prepare_source_record(base_record())
        second = prepare_source_record(base_record(
            source_revision="r2", available_at="2026-01-03T00:00:00Z", value=5.4
        ))
        third = prepare_source_record(base_record(
            source_revision="r3", available_at="2026-02-03T00:00:00Z", value=5.5
        ))
        result = select_vintages_as_of([first, second, third], "2026-01-10T00:00:00Z")
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(result["selected"][0]["source_revision"], "r2")
        self.assertEqual(result["ambiguous"], [])

    def test_as_of_reports_same_time_conflicting_vintages_as_ambiguous(self):
        first = prepare_source_record(base_record())
        competing = prepare_source_record(base_record(
            source_revision="r2", available_at="2026-01-01T01:00:00Z", value=5.8
        ))
        result = select_vintages_as_of([first, competing], "2026-01-10T00:00:00Z")
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["ambiguous"][0]["status"], "AMBIGUOUS_SAME_AVAILABLE_AT")

    def test_missing_available_at_is_excluded_from_point_in_time_selection(self):
        record = prepare_source_record(base_record(available_at=None))
        result = select_vintages_as_of([record], "2026-01-10T00:00:00Z")
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["missing_available_at_excluded"], 1)

    def test_records_without_logical_id_remain_standalone_as_of_records(self):
        record = prepare_source_record(base_record(source_record_id=None, logical_key=None))
        result = select_vintages_as_of([record], "2026-01-10T00:00:00Z")
        self.assertEqual(len(result["selected"]), 1)
        self.assertIsNone(result["selected"][0]["logical_record_id"])


if __name__ == "__main__":
    unittest.main()
