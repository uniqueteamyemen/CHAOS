from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

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
    def _frozen_prepare_state(self):
        commit = "fixture-commit"
        with patch.dict(os.environ, {"GITHUB_SHA": commit}, clear=False):
            contract_path = p2.HERE / "shock_event_contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            manifest_seed = production._manifest_seed(
                contract, p2.dependency_inventory()
            )
        return {
            "schema": production.SCHEMA_VERSION,
            "repository_commit": commit,
            "manifest_seed": manifest_seed,
        }

    def test_manifest_seed_freezes_time_support_contract(self):
        state = self._frozen_prepare_state()
        manifest_seed = state["manifest_seed"]
        self.assertEqual(
            manifest_seed["observation_time_support"],
            p2.time_support_registry(),
        )
        self.assertEqual(
            manifest_seed["p2_source_scope_decisions"],
            p2.P2_SOURCE_SCOPE_DECISIONS,
        )
        production._verify_manifest_configuration(manifest_seed)

        drifted = copy.deepcopy(p2.time_support_registry())
        drifted["sources"]["pink_sheet"]["time_support"]["observation_period_start"] = "1970-01"
        with patch.object(p2, "time_support_registry", return_value=drifted):
            with self.assertRaisesRegex(
                production.IntegrityError, "observation_time_support_mismatch"
            ):
                production._verify_manifest_configuration(manifest_seed)

        changed_scope = copy.deepcopy(p2.P2_SOURCE_SCOPE_DECISIONS)
        changed_scope["decisions"]["WGI"]["status"] = "IN_SCOPE"
        with patch.object(p2, "P2_SOURCE_SCOPE_DECISIONS", changed_scope):
            with self.assertRaisesRegex(
                production.IntegrityError, "p2_source_scope_decisions_mismatch"
            ):
                production._verify_manifest_configuration(manifest_seed)

    def _assert_runtime_entrypoints_reject(
        self, state, expected_error, environ, patcher_factories=()
    ):
        entrypoints = (
            ("evaluate_shard", lambda: production.evaluate_shard(shard_index=0)),
            ("aggregate", production.aggregate),
        )
        for name, invoke in entrypoints:
            with self.subTest(entrypoint=name, expected_error=expected_error):
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, environ, clear=True))
                    stack.enter_context(
                        patch.object(production, "read_json", return_value=state)
                    )
                    for factory in patcher_factories:
                        stack.enter_context(factory())
                    with self.assertRaisesRegex(production.IntegrityError, expected_error):
                        invoke()

    def test_shard_and_aggregate_reject_missing_or_mismatched_github_sha(self):
        state = self._frozen_prepare_state()
        self._assert_runtime_entrypoints_reject(
            state, "github_sha_missing", {}
        )
        self._assert_runtime_entrypoints_reject(
            state,
            "prepare_commit_mismatch",
            {"GITHUB_SHA": "different-commit"},
        )

    def test_shard_and_aggregate_reject_all_frozen_config_drift(self):
        state = self._frozen_prepare_state()
        for attribute, label in (
            ("PIPELINE_CONFIG", "PIPELINE_CONFIG"),
            ("GEM_CONFIG", "GEM_CONFIG"),
            ("SEISMIC_CONFIG", "SEISMIC_CONFIG"),
        ):
            changed = copy.deepcopy(getattr(p2, attribute))
            changed["_test_drift"] = True
            with self.subTest(config=label):
                self._assert_runtime_entrypoints_reject(
                    state,
                    f"execution_config_mismatch:{label}",
                    {"GITHUB_SHA": "fixture-commit"},
                    (lambda attribute=attribute, changed=changed:
                        patch.object(p2, attribute, changed),),
                )

    def test_shard_and_aggregate_reject_shock_contract_drift(self):
        state = self._frozen_prepare_state()
        with tempfile.TemporaryDirectory() as directory:
            changed_root = Path(directory)
            changed_contract = json.loads(
                (p2.HERE / "shock_event_contract.json").read_text(encoding="utf-8")
            )
            changed_contract["matching_window_months"] = (
                int(changed_contract.get("matching_window_months", 0)) + 1
            )
            (changed_root / "shock_event_contract.json").write_text(
                json.dumps(changed_contract), encoding="utf-8"
            )
            self._assert_runtime_entrypoints_reject(
                state,
                "shock_contract_mismatch",
                {"GITHUB_SHA": "fixture-commit"},
                (lambda: patch.object(p2, "HERE", changed_root),),
            )

    def test_shard_and_aggregate_reject_each_frozen_execution_parameter_drift(self):
        state = self._frozen_prepare_state()
        parameter_changes = {
            "REPS": p2.REPS + 1,
            "PINK_MIN": p2.PINK_MIN + 1,
            "GEM_MIN": p2.GEM_MIN + 1,
            "SEISMIC_MIN": p2.SEISMIC_MIN + 1,
            "MONTH_BLOCK": p2.MONTH_BLOCK + 1,
            "EVENT_BLOCK": p2.EVENT_BLOCK + 1,
            "MAG": p2.MAG + 0.1,
        }
        for name, value in parameter_changes.items():
            with self.subTest(parameter=name):
                self._assert_runtime_entrypoints_reject(
                    state,
                    "execution_parameters_mismatch",
                    {"GITHUB_SHA": "fixture-commit"},
                    (lambda name=name, value=value: patch.object(p2, name, value),),
                )

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

    def test_public_release_is_created_as_draft_and_published_after_asset_upload(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "real-data-stress.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        preflight = workflow.index("Preflight every public release asset")
        publish = workflow.index("Publish P2 phase-close audited release")
        draft_create = workflow.index("--draft", publish)
        upload = workflow.index('gh release upload "${TAG_NAME}"', publish)
        verify_remote = workflow.index("verify_remote_assets", upload)
        publish_release = workflow.index('gh release edit "${TAG_NAME}" --repo "${GH_REPO}" --draft=false', publish)
        self.assertLess(preflight, publish)
        self.assertLess(draft_create, upload)
        self.assertLess(upload, verify_remote)
        self.assertLess(verify_remote, publish_release)
        self.assertIn("release_asset_missing_remote", workflow)
        self.assertIn("REMOTE_RELEASE_ASSETS_VERIFIED", workflow)
        self.assertIn("release_asset_digest_mismatch", workflow)
        self.assertIn("release_asset_size_mismatch", workflow)
        self.assertIn("release_target=", workflow)
        self.assertIn("--json targetCommitish", workflow)
        self.assertIn('if [[ "${release_target}" != "${SOURCE_SHA}" ]]; then', workflow)
        self.assertIn('if [[ "${release_target}" != "${SOURCE_SHA}" ]]; then', workflow)
        self.assertIn("P2 phase-close release targets a different commit", workflow)
        for release_name in (
            "markov-real-data-summary.json",
            "markov-real-data-replicates.jsonl.gz",
            "markov-injected-break-summary.json",
            "markov-injected-break-replicates.jsonl.gz",
            "domain-null-declustering-summary.json",
        ):
            self.assertIn(f"release_assets/{release_name}", workflow)
        self.assertIn("release_asset_local_names_not_unique", workflow)
        publish_block = workflow.split("Publish P2 phase-close audited release", 1)[1]
        asset_block = publish_block.split("          assets=(\n", 1)[1].split(
            "          )", 1
        )[0]
        asset_paths = [
            line.strip() for line in asset_block.splitlines() if line.strip()
        ]
        asset_names = [Path(asset_path).name for asset_path in asset_paths]
        self.assertEqual(len(asset_names), len(set(asset_names)))
        self.assertIn(
            "sha256sum --strict -c real_data_stress_pipeline/results/SHA256SUMS.txt",
            workflow,
        )

    def test_workflow_limits_secrets_to_domain_audit_step_and_uses_four_markov_workers(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "real-data-stress.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        domain_job = workflow.split("  audit-domain-null:", 1)[1].split(
            "  publish-phase-close:", 1
        )[0]
        job_environment = domain_job.split("    steps:", 1)[0]
        self.assertNotIn("FRED_API_KEY:", job_environment)
        self.assertNotIn("EIA_API_KEY:", job_environment)
        domain_step = domain_job.split(
            "- name: Run seismic integrity, declustering and domain-null audit", 1
        )[1].split("- name: Upload domain-null audit", 1)[0]
        self.assertIn("FRED_API_KEY: ${{ github.ref == 'refs/heads/main-phase2'", domain_step)
        self.assertIn("EIA_API_KEY: ${{ github.ref == 'refs/heads/main-phase2'", domain_step)
        self.assertEqual(workflow.count("--replicates 999 --workers 4"), 2)

    def test_runtime_dependency_manifest_rejects_version_drift(self):
        expected = p2.dependency_inventory()
        self.assertTrue(production.verify_runtime_dependencies(expected))
        changed = json.loads(json.dumps(expected))
        changed["packages"]["numpy"]["version"] = "0.0.0-not-the-prepare-version"
        with self.assertRaisesRegex(production.IntegrityError, "runtime_package_version_mismatch"):
            production.verify_runtime_dependencies(changed)

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


    def test_prepare_four_shards_and_aggregate_complete_fixture_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact_root = root / "artifacts" / "real_data_stress"
            raw_root = artifact_root / "raw"
            derived_root = artifact_root / "derived"
            here = root / "real_data_stress_pipeline"
            output_root = here / "results"
            here.mkdir(parents=True, exist_ok=True)
            output_root.mkdir(parents=True, exist_ok=True)
            (here / "shock_event_contract.json").write_text(
                json.dumps({"events": [], "matching_window_months": 6}),
                encoding="utf-8",
            )

            pink_source_sha = __import__("hashlib").sha256(b"pink-source-fixture").hexdigest()
            gem_raw = raw_root / "world_bank" / "gem" / "fixture.json"
            usgs_raw = raw_root / "usgs" / "fixture" / "events.geojson"
            gem_raw.parent.mkdir(parents=True, exist_ok=True)
            usgs_raw.parent.mkdir(parents=True, exist_ok=True)
            gem_raw.write_bytes(b'{"fixture":"gem"}')
            usgs_raw.write_bytes(b'{"fixture":"usgs"}')
            gem_sha = production.file_sha256(gem_raw)
            usgs_sha = production.file_sha256(usgs_raw)

            pink_item = synthetic_item("pink:fixture", 101)
            pink_item.update({
                "source": "pink_sheet",
                "source_name": "World Bank Pink Sheet",
                "name": "Pink fixture",
                "cohort": "strict_long_monthly",
                "domain": "commodity",
                "sha256": pink_source_sha,
                "representation": "returns",
            })
            gem_items = []
            for index in range(3):
                item = synthetic_item(f"gem:fixture-{index}", 202 + index)
                item.update({"sha256": gem_sha, "source_name": "World Bank GEM"})
                gem_items.append(item)

            seismic_item = synthetic_item("usgs:fixture", 404)
            seismic_item.update({
                "source": "usgs",
                "source_name": "USGS ComCat",
                "cohort": "seismic_event_interarrival",
                "domain": "seismic",
                "frequency": "event_interarrival",
                "axis": [
                    (datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=2 * index)).isoformat()
                    for index in range(180)
                ],
                "values": np.random.default_rng(505).uniform(0.1, 5.0, 180).tolist(),
                "sha256": usgs_sha,
                "representation": "level",
            })

            def fake_pink(metadata):
                metadata["sources"].append({
                    "provider": "World Bank Pink Sheet",
                    "sha256": pink_source_sha,
                    "raw_preserved": "in-memory only; workbook-specific redistribution terms not established",
                    "retrieved_at_utc": "2000-01-01T00:00:00+00:00",
                })
                return [pink_item]

            def fake_gem(metadata):
                metadata["sources"].append({
                    "provider": "World Bank GEM",
                    "path": gem_raw.relative_to(root).as_posix(),
                    "sha256": gem_sha,
                    "bytes": gem_raw.stat().st_size,
                })
                return gem_items

            def fake_seismic(metadata):
                metadata["sources"].append({
                    "provider": "USGS ComCat",
                    "path": usgs_raw.relative_to(root).as_posix(),
                    "sha256": usgs_sha,
                    "bytes": usgs_raw.stat().st_size,
                })
                return [seismic_item]

            patch_targets = {
                production: {
                    "ROOT": root,
                    "ARTIFACT_ROOT": artifact_root,
                    "FROZEN_CANDIDATES": artifact_root / "frozen_candidates.json",
                    "PINK_RESULTS": artifact_root / "pink_precomputed_results.json",
                    "PREPARE_STATE": output_root / "prepare_state.json",
                    "SHARD_PAYLOAD_ROOT": artifact_root / "candidate_shards",
                    "SHARD_RESULT_ROOT": output_root / "shard_results",
                    "RESULTS_ROOT": output_root,
                },
                p2: {
                    "ROOT": root,
                    "HERE": here,
                    "RAW": raw_root,
                    "DERIVED": derived_root,
                    "OUT": output_root,
                    "REPORT": root / "REAL_DATA_STRESS_REPORT_AR.md",
                    "MANIFEST": output_root / "real_data_stress_manifest.json",
                    "CHECKSUMS": output_root / "SHA256SUMS.txt",
                    "DEPENDENCIES": output_root / "dependency_manifest.json",
                    "REPS": 3,
                    "pink": fake_pink,
                    "gem": fake_gem,
                    "seismic": fake_seismic,
                },
            }
            with patch.dict(os.environ, {
                "GITHUB_SHA": "fixture-commit",
                "GITHUB_REF_NAME": "fixture-branch",
            }):
                with patch.multiple(production, **patch_targets[production]):
                    with patch.multiple(p2, **patch_targets[p2]):
                        prepared = production.prepare(expected_candidates=5, shard_count=4)
                        self.assertEqual(prepared["expected_series_count"], 5)
                        self.assertEqual(prepared["pink_count"], 1)
                        self.assertEqual(prepared["matrix_count"], 4)

                        for shard_index in range(4):
                            envelope = production.evaluate_shard(
                                shard_index=shard_index,
                                shard_count=4,
                                workers=2,
                            )
                            self.assertEqual(len(envelope["results"]), 1)

                        aggregate = production.aggregate()
                        self.assertEqual(aggregate["status"], "COMPLETED")
                        self.assertEqual(aggregate["series_count"], 5)

                        manifest = json.loads(
                            (output_root / "real_data_stress_manifest.json").read_text(encoding="utf-8")
                        )
                        self.assertEqual(manifest["distributed_evaluation"]["verified_series"], 5)
                        self.assertEqual(manifest["distributed_evaluation"]["missing_series"], 0)
                        self.assertEqual(manifest["distributed_evaluation"]["duplicate_series"], 0)
                        self.assertEqual(
                            manifest["observation_time_support"],
                            p2.time_support_registry(),
                        )
                        self.assertEqual(
                            manifest["p2_source_scope_decisions"],
                            p2.P2_SOURCE_SCOPE_DECISIONS,
                        )
                        frozen = json.loads(
                            (artifact_root / "frozen_candidates.json").read_text(encoding="utf-8")
                        )
                        self.assertEqual(len(frozen["candidates"]), 5)
                        pink_entry = next(x for x in frozen["candidates"] if x["source"] == "pink_sheet")
                        self.assertNotIn("values", pink_entry["item_metadata"])
                        pink_results = json.loads(
                            (artifact_root / "pink_precomputed_results.json").read_text(encoding="utf-8")
                        )
                        self.assertFalse(production.contains_key_recursive(pink_results, "values"))
                        for shard_index in range(4):
                            self.assertTrue(
                                (output_root / "shard_results" / f"shard-{shard_index}.json").is_file()
                            )


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


    def test_write_publish_jobs_have_no_checkout_and_consume_read_only_artifacts(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "real-data-stress.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        prepare_job = workflow.split("  prepare:", 1)[1].split("\n  evaluate:", 1)[0]
        prepare_header = prepare_job.split("    steps:", 1)[0]
        self.assertIn("contents: read", prepare_header)
        self.assertNotIn("contents: write", prepare_header)
        self.assertIn("Stage immutable Phase 1 release assets", prepare_job)
        self.assertIn("Upload immutable Phase 1 release assets", prepare_job)
        self.assertIn("actions/upload-artifact@v7", prepare_job)
        self.assertNotIn("needs: publish-phase1-archive", prepare_job)

        phase1_job = workflow.split("  publish-phase1-archive:", 1)[1].split("\n  prepare:", 1)[0]
        self.assertIn("needs: prepare", phase1_job)
        self.assertIn("contents: write", phase1_job)
        self.assertNotIn("actions/checkout@", phase1_job)
        self.assertNotIn("git ", phase1_job)
        self.assertIn("actions/download-artifact@v8", phase1_job)
        self.assertIn("digest-mismatch: error", phase1_job)
        self.assertIn("gh release create", phase1_job)
        self.assertIn("gh release upload", phase1_job)

        evaluate_job = workflow.split("  evaluate:", 1)[1].split("\n  aggregate-and-audit:", 1)[0]
        self.assertIn("needs: [prepare, publish-phase1-archive]", evaluate_job)

        stage_job = workflow.split("  stage-phase-close-release:", 1)[1].split("\n  publish-phase-close:", 1)[0]
        stage_header = stage_job.split("    steps:", 1)[0]
        self.assertIn("contents: read", stage_header)
        self.assertNotIn("contents: write", stage_header)
        self.assertIn("Preflight every public release asset", stage_job)
        self.assertIn("Upload preflighted P2 phase-close release bundle", stage_job)
        self.assertIn("actions/upload-artifact@v7", stage_job)
        self.assertNotIn("GH_TOKEN", stage_job)

        phase_close_job = workflow.split("  publish-phase-close:", 1)[1].split("\n  pr-gate:", 1)[0]
        self.assertIn("needs: stage-phase-close-release", phase_close_job)
        self.assertIn("contents: write", phase_close_job)
        self.assertNotIn("actions/checkout@", phase_close_job)
        self.assertNotIn("git ", phase_close_job)
        self.assertIn("actions/download-artifact@v8", phase_close_job)
        self.assertIn("digest-mismatch: error", phase_close_job)
        self.assertIn("gh release create", phase_close_job)
        self.assertIn("gh release upload", phase_close_job)
        self.assertIn("gh release edit", phase_close_job)

    def test_all_artifact_downloads_fail_closed_on_digest_mismatch(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "real-data-stress.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        download_count = workflow.count("uses: actions/download-artifact@v8")
        self.assertGreater(download_count, 0)
        self.assertNotIn("uses: actions/download-artifact@v4", workflow)
        self.assertEqual(download_count, workflow.count("digest-mismatch: error"))
        upload_count = workflow.count("uses: actions/upload-artifact@v7")
        self.assertGreater(upload_count, 0)
        self.assertNotIn("uses: actions/upload-artifact@v4", workflow)


if __name__ == "__main__":
    unittest.main()
