from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np

from src.coverage_model import CoverageEntry, SourceConflict, write_conflicts, write_coverage
from src.pattern_registry import PatternRecord, PatternRegistry
from src.raw_ingest import ImmutableRawStore, verify_record
from src.surrogates import validate_with_surrogates
from src.transformations import real_value_from_cpi


def test_raw_store_preserves_bytes_and_provenance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = b'{"source":"real","value":82}\n'
        store = ImmutableRawStore(tmp)
        record = store.persist(source_id="test", url="https://example.invalid/data", payload=payload, http_status=200, suffix=".json")
        assert verify_record(record)
        assert Path(record.raw_path).read_bytes() == payload
        assert record.sha256 == hashlib.sha256(payload).hexdigest()


def test_real_value_is_derived_without_replacing_nominal() -> None:
    derived = real_value_from_cpi(
        nominal_value=100.0,
        cpi_at_observation=200.0,
        cpi_at_base=100.0,
        variable_id="x",
        timestamp="2020-01-01",
        nominal_ref="nominal:1",
        cpi_ref="cpi:1",
    )
    assert derived.value == 50.0
    assert derived.transformation.startswith("real_value")
    assert derived.source_observation_refs == ("nominal:1", "cpi:1")


def test_surrogate_validation_returns_a_null_distribution() -> None:
    source = np.arange(1.0, 21.0)
    target = np.roll(source, 2)
    result = validate_with_surrogates(
        source=source,
        target=target,
        score_fn=lambda a, b: float(np.corrcoef(a, b)[0, 1]),
        method="circular_shift",
        budget=20,
    )
    assert result.budget == 20
    assert len(result.null_scores) == 20
    assert 0.0 <= result.empirical_p_value <= 1.0


def test_coverage_and_conflicts_are_written_separately() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        coverage_path = Path(tmp) / "coverage.csv"
        conflict_path = Path(tmp) / "conflicts.jsonl"
        write_coverage(
            [CoverageEntry("v1", "source-a", "continuous", "2000", "2025", "annual", status="observed")],
            coverage_path,
        )
        write_conflicts(
            [SourceConflict("v1", "2020", [{"source": "a", "value": 82}, {"source": "b", "value": 91}], "value_disagreement")],
            conflict_path,
        )
        assert "v1" in coverage_path.read_text(encoding="utf-8")
        assert "unresolved_at_ingestion" in conflict_path.read_text(encoding="utf-8")


def test_registry_preserves_rejected_pattern() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = PatternRegistry(tmp)
        record = PatternRecord(
            pattern_id="p1",
            pattern_version="1",
            status="candidate",
            path_nodes=["a", "b"],
            edges=[{"source": "a", "target": "b", "lag": 2}],
            evidence_refs=["raw:1"],
            training_window={"start": "2000", "end": "2015"},
            validation_window={"start": "2016", "end": "2020"},
            algorithm_metadata={"algorithm": "test"},
            validation_metadata={"p_value": 0.5},
        )
        path = registry.reject(record, "failed_structure_preserving_surrogate_test")
        data = json.loads(path.read_text(encoding="utf-8").strip())
        assert data["status"] == "rejected"
        assert data["rejection_reason"].startswith("failed_")
