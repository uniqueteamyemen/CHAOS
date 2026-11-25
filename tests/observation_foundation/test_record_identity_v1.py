import json
import unittest
from pathlib import Path

from observation_foundation.record_identity_v1 import (
    prepare_source_record,
    prepare_source_records,
    build_vintage_chains,
    select_vintages_as_of,
    build_epoch_snapshot,
    normalize_time_support,
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
        "revision_status": None,
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

    def test_revision_status_keeps_logical_id_and_changes_version_id(self):
        first = prepare_source_record(base_record(revision_status=None))
        revised = prepare_source_record(base_record(
            revision_status="corrected", source_revision="r2"
        ))
        self.assertEqual(first["logical_record_id"], revised["logical_record_id"])
        self.assertNotEqual(first["canonical_record_id"], revised["canonical_record_id"])

    def test_revision_status_is_unicode_normalized(self):
        prepared = prepare_source_record(base_record(revision_status="é"))
        self.assertEqual(prepared["revision_status"], "é")

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

    def test_periodic_measurement_has_stable_declared_series_slot_identity(self):
        base = base_record(
            series_semantics="periodic_measurement", source_record_id=None,
            logical_key=None, metric_id="monthly-output", event_time="2026-01",
        )
        first = prepare_source_record(base)
        revised = prepare_source_record(dict(base, value=99.0, source_revision="r2",
                                             available_at="2026-02-05T00:00:00Z"))
        self.assertEqual(first["logical_record_id"], revised["logical_record_id"])
        self.assertNotEqual(first["canonical_record_id"], revised["canonical_record_id"])
        self.assertEqual(first["identity_basis"], "periodic_series_key")

    def test_event_stream_without_explicit_key_remains_unlinked(self):
        prepared = prepare_source_record(base_record(source_record_id=None, logical_key=None))
        self.assertIsNone(prepared["logical_record_id"])

    def test_unicode_normalized_logical_key_collision_is_rejected(self):
        key = {"é": "first", "é": "second"}
        with self.assertRaisesRegex(ValueError, "collision_after_unicode"):
            prepare_source_record(base_record(source_record_id=None, logical_key=key))

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


    def test_as_of_orders_subsecond_vintages_by_actual_time(self):
        older = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00Z", value=5.2
        ))
        newer = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00.1Z", source_revision="r2", value=5.3
        ))
        result = select_vintages_as_of([newer, older], "2026-01-01T01:00:01Z")
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(result["selected"][0]["source_revision"], "r2")

    def test_vintage_chain_orders_subsecond_versions_by_actual_time(self):
        older = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00Z", value=5.2
        ))
        newer = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00.1Z", source_revision="r2", value=5.3
        ))
        chains = build_vintage_chains([newer, older])
        versions = chains["chains"][older["logical_record_id"]]
        self.assertEqual([item["source_revision"] for item in versions], ["r1", "r2"])

    def test_numeric_string_is_rejected_by_runtime_contract(self):
        with self.assertRaisesRegex(ValueError, "finite_number"):
            prepare_source_record(base_record(value="5.2"))

    def test_unrecognized_observation_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected_record_fields"):
            prepare_source_record(base_record(retrieved_at="2026-01-02T00:00:00Z"))

    def test_unrecognized_transport_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unexpected_transport_fields"):
            prepare_source_record(base_record(transport_metadata={"row_number": 1, "cursor": "abc"}))


    def test_epoch_snapshot_is_independent_of_input_order_and_transport_metadata(self):
        a = prepare_source_record(base_record(source_record_id="event-A"))
        b = prepare_source_record(base_record(
            source_record_id="event-B",
            event_time="2026-01-02T00:00:00Z",
            available_at="2026-01-02T01:00:00Z",
        ))
        first = build_epoch_snapshot([a, b], "2026-01-03T00:00:00Z")
        second = build_epoch_snapshot([dict(b), dict(a)], "2026-01-03T00:00:00Z")
        self.assertEqual(first["epoch_id"], second["epoch_id"])
        self.assertEqual(first["snapshot_sha256"], second["snapshot_sha256"])

    def test_epoch_snapshot_binds_source_declared_time_support(self):
        record = prepare_source_record(base_record())
        support = {
            "observation_period_start": "2026-01-01",
            "observation_period_end": "2026-12-31",
            "native_frequency": "event",
        }
        snapshot = build_epoch_snapshot([record], "2026-02-01T00:00:00Z", time_support=support)
        self.assertEqual(snapshot["manifest"]["time_support_status"], "DECLARED")
        self.assertEqual(snapshot["manifest"]["time_support"]["native_frequency"], "event")
        self.assertEqual(
            snapshot["manifest"]["time_support"]["observation_period_end"],
            "2026-12-31",
        )

    def test_epoch_snapshot_rejects_reversed_time_support(self):
        record = prepare_source_record(base_record())
        with self.assertRaisesRegex(ValueError, "time_support_start_after_end"):
            build_epoch_snapshot(
                [record],
                "2026-02-01T00:00:00Z",
                time_support={
                    "observation_period_start": "2026-12-31",
                    "observation_period_end": "2026-01-01",
                    "native_frequency": "daily",
                },
            )

    def test_epoch_snapshot_preserves_identical_event_multiplicity(self):
        record = prepare_source_record(base_record(source_record_id="event-duplicate"))
        single = build_epoch_snapshot([record], "2026-01-03T00:00:00Z")
        repeated = build_epoch_snapshot([record, dict(record)], "2026-01-03T00:00:00Z")
        self.assertEqual(single["manifest"]["selected_occurrence_count"], 1)
        self.assertEqual(repeated["manifest"]["selected_occurrence_count"], 2)
        self.assertEqual(
            repeated["manifest"]["selected_canonical_record_ids"],
            [record["canonical_record_id"], record["canonical_record_id"]],
        )
        self.assertNotEqual(single["snapshot_sha256"], repeated["snapshot_sha256"])

    def test_epoch_snapshot_records_future_and_unknown_availability_exclusions(self):
        known = prepare_source_record(base_record(source_record_id="known"))
        future = prepare_source_record(base_record(
            source_record_id="future",
            event_time="2026-01-02T00:00:00Z",
            available_at="2026-02-01T00:00:00Z",
        ))
        unknown = prepare_source_record(base_record(
            source_record_id="unknown",
            event_time="2026-01-03T00:00:00Z",
            available_at=None,
        ))
        epoch = build_epoch_snapshot([known, future, unknown], "2026-01-10T00:00:00Z")
        self.assertEqual(epoch["manifest"]["selected_occurrence_count"], 1)
        self.assertEqual(epoch["manifest"]["future_available_at_excluded"], 1)
        self.assertEqual(epoch["manifest"]["missing_available_at_excluded"], 1)

    def test_epoch_snapshot_hash_changes_with_decision_time(self):
        record = prepare_source_record(base_record())
        morning = build_epoch_snapshot([record], "2026-01-02T00:00:00Z")
        later = build_epoch_snapshot([record], "2026-01-03T00:00:00Z")
        self.assertNotEqual(morning["epoch_id"], later["epoch_id"])

    def test_epoch_snapshot_retains_same_time_vintage_ambiguity(self):
        first = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00Z", value=5.2
        ))
        competing = prepare_source_record(base_record(
            available_at="2026-01-01T01:00:00Z", source_revision="r2", value=5.8
        ))
        epoch = build_epoch_snapshot([first, competing], "2026-01-02T00:00:00Z")
        self.assertEqual(epoch["selected_records"], [])
        self.assertEqual(len(epoch["manifest"]["ambiguous"]), 1)
        self.assertEqual(
            epoch["manifest"]["ambiguous"][0]["status"],
            "AMBIGUOUS_SAME_AVAILABLE_AT",
        )


    def test_prepared_numeric_value_remains_numeric(self):
        prepared = prepare_source_record(base_record(value=5.2))
        self.assertIsInstance(prepared["value"], float)
        self.assertEqual(prepared["value"], 5.2)

    def test_epoch_snapshot_rejects_content_mutated_after_identity(self):
        prepared = prepare_source_record(base_record())
        mutated = dict(prepared, value=5.9)
        with self.assertRaisesRegex(ValueError, "canonical_record_content_mismatch"):
            build_epoch_snapshot([mutated], "2026-01-02T00:00:00Z")

    def test_epoch_snapshot_rejects_uncontracted_record_fields(self):
        prepared = prepare_source_record(base_record())
        with self.assertRaisesRegex(ValueError, "epoch_record_fields_invalid"):
            build_epoch_snapshot(
                [dict(prepared, untracked_metadata="not in source contract")],
                "2026-01-02T00:00:00Z",
            )


    def test_time_support_schema_is_series_level_not_record_level(self):
        schema_path = (
            Path(__file__).resolve().parents[2]
            / "observation_foundation"
            / "contracts"
            / "observation_time_support_v1.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {
                "observation_period_start",
                "observation_period_end",
                "native_frequency",
            },
        )
        self.assertEqual(
            set(schema["properties"]),
            {
                "observation_period_start",
                "observation_period_end",
                "native_frequency",
                "boundary_semantics",
            },
        )
        record_schema_path = (
            Path(__file__).resolve().parents[2]
            / "observation_foundation"
            / "contracts"
            / "source_record_observation_v1.schema.json"
        )
        record_schema = json.loads(
            record_schema_path.read_text(encoding="utf-8")
        )
        self.assertNotIn("observation_period_start", record_schema["properties"])
        self.assertNotIn("observation_period_end", record_schema["properties"])

    def test_time_support_accepts_native_annual_boundaries_and_default_semantics(self):
        normalized = normalize_time_support({
            "observation_period_start": "2000",
            "observation_period_end": "2024",
            "native_frequency": "annual",
        })
        self.assertEqual(normalized, {
            "observation_period_start": "2000",
            "observation_period_end": "2024",
            "native_frequency": "annual",
            "boundary_semantics": "SOURCE_DECLARED",
        })

    def test_time_support_preserves_monthly_and_timezone_aware_boundaries(self):
        monthly = normalize_time_support({
            "observation_period_start": "2000-01",
            "observation_period_end": "2024-12",
            "native_frequency": "monthly",
            "boundary_semantics": "INCLUSIVE_PERIOD_LABELS",
        })
        event = normalize_time_support({
            "observation_period_start": "2026-01-01T03:00:00+03:00",
            "observation_period_end": "2026-01-31T23:59:59Z",
            "native_frequency": "event",
        })
        self.assertEqual(monthly["observation_period_start"], "2000-01")
        self.assertEqual(monthly["observation_period_end"], "2024-12")
        self.assertEqual(monthly["boundary_semantics"], "INCLUSIVE_PERIOD_LABELS")
        self.assertEqual(event["observation_period_start"], "2026-01-01T00:00:00Z")

    def test_time_support_rejects_missing_unknown_and_empty_fields(self):
        with self.assertRaisesRegex(ValueError, "time_support_fields_missing"):
            normalize_time_support({
                "observation_period_start": "2000",
                "native_frequency": "annual",
            })
        with self.assertRaisesRegex(ValueError, "time_support_fields_invalid"):
            normalize_time_support({
                "observation_period_start": "2000",
                "observation_period_end": "2024",
                "native_frequency": "annual",
                "retrieved_at": "2026-01-01T00:00:00Z",
            })
        with self.assertRaisesRegex(ValueError, "native_frequency"):
            normalize_time_support({
                "observation_period_start": "2000",
                "observation_period_end": "2024",
                "native_frequency": " ",
            })

    def test_time_support_is_not_added_to_record_identity_payload(self):
        record = base_record()
        first = prepare_source_record(record)
        series_support = normalize_time_support({
            "observation_period_start": "2026-01-01",
            "observation_period_end": "2026-12-31",
            "native_frequency": "event",
        })
        snapshot = build_epoch_snapshot(
            [first],
            "2026-02-01T00:00:00Z",
            time_support=series_support,
        )
        self.assertNotIn("observation_period_start", first)
        self.assertNotIn("observation_period_end", first)
        self.assertEqual(snapshot["manifest"]["time_support"], series_support)


if __name__ == "__main__":
    unittest.main()
