from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from real_data_stress_pipeline import production_pipeline as production
from real_data_stress_pipeline import run_pipeline as p2


def synthetic_item(identifier: str, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 1.0, 180).astype(float).tolist()
    axis = [f"{2000 + index // 12:04d}-{index % 12 + 1:02d}" for index in range(len(values))]
    return {
        "id": identifier,
        "source": "gem",
        "source_name": "Synthetic fixture",
        "name": identifier,
        "cohort": "secondary_gem_monthly_87_plus",
        "domain": "macro",
        "frequency": "monthly",
        "axis": axis,
        "values": values,
        "sha256": "source-" + identifier,
        "points": len(values) + 1,
        "quality": {"passed": True, "observations": len(values)},
        "representation": "returns",
    }


class ProductionPipelineTests(unittest.TestCase):
    def test_weighted_sharding_is_deterministic_and_balances_load(self):
        candidates = [
            {"id": f"s{i}", "original_index": i, "estimated_weight": weight}
            for i, weight in enumerate((90, 80, 70, 60, 50, 40, 30, 20, 10, 5))
        ]
        first = production.weighted_shard_assignments(candidates, 4)
        second = production.weighted_shard_assignments(candidates, 4)
        self.assertEqual(first, second)
        loads = [sum(c["estimated_weight"] for c in candidates if first[c["id"]] == shard) for shard in range(4)]
        self.assertLessEqual(max(loads) - min(loads), 10)
        self.assertEqual(set(first), {c["id"] for c in candidates})

    def test_candidate_hash_binds_exact_values_axis_and_source_provenance(self):
        item = synthetic_item("gem:test", 11)
        baseline = production.candidate_sha256(item)
        changed_value = dict(item)
        changed_value["values"] = list(item["values"])
        changed_value["values"][10] += 0.0000000001
        changed_axis = dict(item)
        changed_axis["axis"] = list(item["axis"])
        changed_axis["axis"][10] = "2099-01"
        changed_source = dict(item)
        changed_source["sha256"] = "different-source"
        self.assertNotEqual(baseline, production.candidate_sha256(changed_value))
        self.assertNotEqual(baseline, production.candidate_sha256(changed_axis))
        self.assertNotEqual(baseline, production.candidate_sha256(changed_source))

    def test_pink_candidate_registry_entry_contains_no_raw_values(self):
        item = synthetic_item("pink:private", 12)
        item["source"] = "pink_sheet"
        item["sha256"] = "pink-workbook-sha"
        entry = production.candidate_manifest_entry(
            item, 0, None, "prepare_private", 100, False
        )
        self.assertNotIn("values", entry)
        self.assertNotIn("values", entry["item_metadata"])
        serialized = json.dumps(entry, ensure_ascii=False)
        self.assertNotIn('"values":', serialized)
        self.assertEqual(entry["candidate_sha256"], production.candidate_sha256(item))

    def test_process_pool_and_four_weighted_shards_match_serial_results_bit_for_bit(self):
        # Eight equal-cost, G1-eligible fixtures give every one of four shards
        # two tasks, so each shard exercises its own two-process evaluator.
        items = [synthetic_item(f"gem:fixture-{index}", 101) for index in range(8)]
        contract = {"events": [], "matching_window_months": 6}
        self.assertTrue(all(p2.g1(item["values"]).get("passed") for item in items))
        sequential = production.evaluate_items(items, contract, workers=1, bootstrap_replicates=5)
        parallel = production.evaluate_items(items, contract, workers=4, bootstrap_replicates=5)
        self.assertEqual(
            [production.json_bytes(item) for item in sequential],
            [production.json_bytes(item) for item in parallel],
        )

        candidates = []
        for index, item in enumerate(items):
            weight, eligible = production.estimate_cost(item)
            self.assertTrue(eligible)
            candidates.append({
                "id": item["id"],
                "original_index": index,
                "estimated_weight": weight,
                "candidate_sha256": production.candidate_sha256(item),
                "source_sha256": item["sha256"],
                "values_count": len(item["values"]),
            })
        assignments = production.weighted_shard_assignments(candidates, 4)
        shard_results = []
        for shard in range(4):
            shard_items = [item for item in items if assignments[item["id"]] == shard]
            self.assertEqual(len(shard_items), 2)
            shard_results.extend(
                production.evaluate_items(
                    shard_items, contract, workers=2, bootstrap_replicates=5
                )
            )
        restored = production.validate_result_records(candidates, shard_results, expected_count=8)
        self.assertEqual(
            [production.json_bytes(item) for item in sequential],
            [production.json_bytes(item) for item in restored],
        )

    def test_aggregate_gate_rejects_missing_shard_result(self):
        candidates = [synthetic_item("gem:a", 1), synthetic_item("gem:b", 2)]
        registry = []
        results = []
        for index, item in enumerate(candidates):
            weight, eligible = production.estimate_cost(item)
            registry.append({
                "id": item["id"],
                "original_index": index,
                "source_sha256": item["sha256"],
                "candidate_sha256": production.candidate_sha256(item),
                "values_count": len(item["values"]),
            })
            result = {
                "id": item["id"],
                "sha256": item["sha256"],
                "candidate_sha256": production.candidate_sha256(item),
                "observations": len(item["values"]),
            }
            results.append(result)
        with self.assertRaisesRegex(production.IntegrityError, "missing_results"):
            production.validate_result_records(registry, results[:1], expected_count=2)

    def test_aggregate_gate_rejects_duplicate_result_and_changed_hash(self):
        item = synthetic_item("gem:a", 3)
        registry = [{
            "id": item["id"],
            "original_index": 0,
            "source_sha256": item["sha256"],
            "candidate_sha256": production.candidate_sha256(item),
            "values_count": len(item["values"]),
        }]
        result = {
            "id": item["id"],
            "sha256": item["sha256"],
            "candidate_sha256": production.candidate_sha256(item),
            "observations": len(item["values"]),
        }
        with self.assertRaisesRegex(production.IntegrityError, "duplicate_result_id"):
            production.validate_result_records(registry, [result, result], expected_count=1)
        changed = dict(result)
        changed["candidate_sha256"] = "wrong"
        with self.assertRaisesRegex(production.IntegrityError, "candidate_sha256_mismatch"):
            production.validate_result_records(registry, [changed], expected_count=1)


    def test_raw_source_snapshot_hash_is_verified_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_file = root / "raw.bin"
            source_file.write_bytes(b"immutable-source-snapshot")
            source = {
                "provider": "World Bank GEM",
                "path": "raw.bin",
                "sha256": production.file_sha256(source_file),
            }
            self.assertEqual(production.validate_source_snapshots([source], root), 1)
            source["sha256"] = "wrong"
            with self.assertRaisesRegex(production.IntegrityError, "raw_source_sha256_mismatch"):
                production.validate_source_snapshots([source], root)
            source["sha256"] = production.file_sha256(source_file)
            source["path"] = "../escape.bin"
            with self.assertRaisesRegex(production.IntegrityError, "escapes_repository"):
                production.validate_source_snapshots([source], root)

    def test_pink_source_is_memory_only_and_nested_values_are_detected(self):
        source = {
            "provider": "World Bank Pink Sheet",
            "sha256": "source-hash",
            "raw_preserved": "in-memory only; workbook-specific redistribution terms not established",
        }
        self.assertEqual(production.validate_source_snapshots([source]), 0)
        source["path"] = "raw/pink.xlsx"
        with self.assertRaisesRegex(production.IntegrityError, "pink_sheet_raw_path"):
            production.validate_source_snapshots([source])
        self.assertTrue(production.contains_key_recursive({"bootstrap": [{"values": [1, 2]}]}, "values"))
        self.assertFalse(production.contains_key_recursive({"series": {"observations": 180}}, "values"))

    def test_aggregate_gate_rejects_bootstrap_replicate_mismatch(self):
        item = synthetic_item("gem:bootstrap-mismatch", 9)
        registry = [{
            "id": item["id"],
            "original_index": 0,
            "source_sha256": item["sha256"],
            "candidate_sha256": production.candidate_sha256(item),
            "values_count": len(item["values"]),
            "bootstrap_replicates_expected": 5,
        }]
        result = {
            "id": item["id"],
            "sha256": item["sha256"],
            "candidate_sha256": production.candidate_sha256(item),
            "observations": len(item["values"]),
            "bootstrap": {"replicates": 4},
        }
        with self.assertRaisesRegex(production.IntegrityError, "bootstrap_replicate_mismatch"):
            production.validate_result_records(registry, [result], expected_count=1)

    def test_aggregate_gate_rejects_source_hash_and_observation_mismatch(self):
        item = synthetic_item("gem:a", 4)
        registry = [{
            "id": item["id"],
            "original_index": 0,
            "source_sha256": item["sha256"],
            "candidate_sha256": production.candidate_sha256(item),
            "values_count": len(item["values"]),
        }]
        result = {
            "id": item["id"],
            "sha256": "wrong-source",
            "candidate_sha256": production.candidate_sha256(item),
            "observations": len(item["values"]),
        }
        with self.assertRaisesRegex(production.IntegrityError, "source_sha256_mismatch"):
            production.validate_result_records(registry, [result], expected_count=1)
        result["sha256"] = item["sha256"]
        result["observations"] -= 1
        with self.assertRaisesRegex(production.IntegrityError, "observation_count_mismatch"):
            production.validate_result_records(registry, [result], expected_count=1)


if __name__ == "__main__":
    unittest.main()
