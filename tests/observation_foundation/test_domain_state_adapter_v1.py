import unittest

from observation_foundation.domain_state_adapter_v1 import (
    DomainStateAdapterError,
    adapt_domain_state,
    adapt_domain_states,
)


def periodic_contract():
    return {
        "adapter_id": "fixture-periodic-v1",
        "source_namespace": "fixture-provider",
        "dataset_id": "fixture-annual-series",
        "domain": "trade",
        "native_frequency": "annual",
        "series_semantics": "periodic_measurement",
        "entity_id_path": ["entity_id"],
        "event_time_path": ["timestamp"],
        "time_support": {
            "observation_period_start": "2000",
            "observation_period_end": "2024",
            "native_frequency": "annual",
        },
        "metrics": [
            {
                "metric_id": "trade.import.value",
                "value_path": ["source_observations", "imports_raw"],
                "unit": "USD",
            },
            {
                "metric_id": "trade.export.value",
                "value_path": ["source_observations", "exports_raw"],
                "unit": "USD",
            },
        ],
    }


def event_contract(*, include_source_id=True):
    contract = {
        "adapter_id": "fixture-events-v1",
        "source_namespace": "fixture-seismic",
        "dataset_id": "fixture-events",
        "domain": "environmental",
        "native_frequency": "event",
        "series_semantics": "event_stream",
        "entity_id_path": ["entity_id"],
        "event_time_path": ["timestamp"],
        "time_support": {
            "observation_period_start": "2024-01-01T00:00:00Z",
            "observation_period_end": "2024-12-31T23:59:59Z",
            "native_frequency": "event",
        },
        "metrics": [{
            "metric_id": "earthquake.magnitude",
            "value_path": ["source_observations", "magnitude"],
            "unit": "magnitude",
        }],
    }
    if include_source_id:
        contract["source_record_id_path"] = ["entity_id"]
    return contract


def state(**changes):
    value = {
        "pattern_id": "TRADE_STATE_V1",
        "domain": "trade",
        "entity_id": "124",
        "entity_name": "Reporter 124",
        "timestamp": 2020,
        "native_frequency": "annual",
        "state_label": "trade_observation",
        "state_probability": None,
        "source_observations": {
            "imports_raw": 120.0,
            "exports_raw": 150.0,
        },
        "lead_profile": {},
        "uncertainty": [],
        "failure_cases": [],
        "edge_status": "not_testable",
        "evidence_refs": ["source://fixture/2020"],
    }
    value.update(changes)
    return value


class DomainStateObservationAdapterTests(unittest.TestCase):
    def test_explicit_metric_mapping_preserves_native_time_and_units(self):
        result = adapt_domain_state(state(), periodic_contract())
        by_metric = {row["observation"]["metric_id"]: row for row in result}
        imports = by_metric["trade.import.value"]["observation"]
        exports = by_metric["trade.export.value"]["observation"]
        self.assertEqual(imports["event_time"], "2020")
        self.assertEqual(by_metric["trade.import.value"]["lineage"]["native_frequency"], "annual")
        self.assertEqual(imports["value"], 120.0)
        self.assertEqual(imports["unit"], "USD")
        self.assertEqual(exports["value"], 150.0)
        self.assertEqual(by_metric["trade.import.value"]["lineage"]["evidence_refs"], ["source://fixture/2020"])

    def test_availability_is_not_invented_and_as_of_excludes_unknown(self):
        result = adapt_domain_state(state(), periodic_contract())
        observation = result[0]["observation"]
        self.assertIsNone(observation["available_at"])
        self.assertIsNotNone(observation["logical_record_id"])
        from observation_foundation.record_identity_v1 import select_vintages_as_of
        selection = select_vintages_as_of([observation], "2021-01-01T00:00:00Z")
        self.assertEqual(selection["selected"], [])
        self.assertEqual(selection["missing_available_at_excluded"], 1)

    def test_missing_value_remains_missing_and_never_becomes_zero(self):
        missing_state = state(source_observations={
            "imports_raw": None,
            "exports_raw": 0.0,
        })
        result = adapt_domain_state(missing_state, periodic_contract())
        by_metric = {row["observation"]["metric_id"]: row["observation"] for row in result}
        self.assertIsNone(by_metric["trade.import.value"]["value"])
        self.assertEqual(by_metric["trade.import.value"]["observation_status"], "missing")
        self.assertEqual(by_metric["trade.export.value"]["value"], 0.0)
        self.assertEqual(by_metric["trade.export.value"]["observation_status"], "observed")

    def test_frequency_mismatch_fails_closed(self):
        with self.assertRaisesRegex(DomainStateAdapterError, "native_frequency_mismatch"):
            adapt_domain_state(state(native_frequency="monthly"), periodic_contract())

    def test_domain_mismatch_fails_closed(self):
        with self.assertRaisesRegex(DomainStateAdapterError, "domain_mismatch"):
            adapt_domain_state(state(domain="economy"), periodic_contract())

    def test_missing_mapped_value_fails_instead_of_silent_drop(self):
        malformed = state(source_observations={"imports_raw": 50.0})
        with self.assertRaisesRegex(DomainStateAdapterError, "source_path_missing"):
            adapt_domain_state(malformed, periodic_contract())

    def test_event_stream_uses_only_declared_source_identity(self):
        event = state(
            domain="environmental",
            entity_id="us7000abc",
            timestamp="2024-01-01T10:00:00Z",
            native_frequency="event",
            source_observations={"magnitude": 6.7},
        )
        observation = adapt_domain_state(event, event_contract())[0]["observation"]
        self.assertEqual(observation["source_record_id"], "us7000abc")
        self.assertEqual(observation["identity_basis"], "source_record_id")
        self.assertEqual(observation["event_time"], "2024-01-01T10:00:00Z")

    def test_event_stream_without_source_id_remains_unlinked(self):
        event = state(
            domain="environmental",
            entity_id="unknown",
            timestamp="2024-01-01T10:00:00Z",
            native_frequency="event",
            source_observations={"magnitude": 6.7},
        )
        observation = adapt_domain_state(
            event, event_contract(include_source_id=False)
        )[0]["observation"]
        self.assertIsNone(observation["logical_record_id"])
        self.assertEqual(observation["identity_basis"], "UNRESOLVED_NO_STABLE_KEY")

    def test_event_outside_source_declared_support_fails(self):
        event = state(
            domain="environmental",
            entity_id="us7000abc",
            timestamp="2025-01-01T10:00:00Z",
            native_frequency="event",
            source_observations={"magnitude": 6.7},
        )
        with self.assertRaisesRegex(DomainStateAdapterError, "event_time_outside"):
            adapt_domain_state(event, event_contract())

    def test_time_support_frequency_must_match_adapter(self):
        contract = periodic_contract()
        contract["time_support"]["native_frequency"] = "monthly"
        with self.assertRaisesRegex(DomainStateAdapterError, "time_support_frequency_mismatch"):
            adapt_domain_state(state(), contract)

    def test_collection_order_is_deterministic_and_multiplicity_is_preserved(self):
        first = state(entity_id="124", timestamp=2020)
        second = state(entity_id="36", timestamp=2019)
        left = adapt_domain_states([first, second, first], periodic_contract())
        right = adapt_domain_states([first, first, second], periodic_contract())
        self.assertEqual(
            [item["observation"]["canonical_record_id"] for item in left["records"]],
            [item["observation"]["canonical_record_id"] for item in right["records"]],
        )
        self.assertEqual(left["output_observation_count"], 6)
        self.assertEqual(left["input_domain_state_count"], 3)
        self.assertEqual(left["unknown_availability_count"], 6)
        self.assertEqual(left["time_support"]["observation_period_start"], "2000")

    def test_duplicate_metric_id_is_rejected(self):
        contract = periodic_contract()
        contract["metrics"].append(dict(contract["metrics"][0]))
        with self.assertRaisesRegex(DomainStateAdapterError, "metric_id_duplicate"):
            adapt_domain_state(state(), contract)

    def test_unknown_contract_fields_are_rejected(self):
        contract = periodic_contract()
        contract["guess_missing_dates"] = True
        with self.assertRaisesRegex(DomainStateAdapterError, "adapter_contract_unknown"):
            adapt_domain_state(state(), contract)


if __name__ == "__main__":
    unittest.main()
