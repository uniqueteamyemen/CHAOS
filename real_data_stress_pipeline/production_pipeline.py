"""Deterministic three-stage P2 production pipeline.

The frozen detector and all scientific eligibility rules remain owned by
real_data_stress_pipeline.run_pipeline. This module only partitions execution,
freezes provenance, and enforces complete-result publication.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

# Set numerical-library thread limits before importing NumPy / statsmodels.
for _name in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

import numpy as np

from real_data_stress_pipeline import run_pipeline as p2


ROOT = p2.ROOT
ARTIFACT_ROOT = ROOT / "artifacts" / "real_data_stress"
RESULTS_ROOT = p2.OUT
FROZEN_CANDIDATES = ARTIFACT_ROOT / "frozen_candidates.json"
PINK_RESULTS = ARTIFACT_ROOT / "pink_precomputed_results.json"
PREPARE_STATE = RESULTS_ROOT / "prepare_state.json"
SHARD_PAYLOAD_ROOT = ARTIFACT_ROOT / "candidate_shards"
SHARD_RESULT_ROOT = RESULTS_ROOT / "shard_results"
SHARD_COUNT = 4
EXPECTED_CANDIDATES = 519
SCHEMA_VERSION = "chaos-p2-production-v1"


class IntegrityError(RuntimeError):
    """Raised when frozen inputs or shard outputs cannot be proven complete."""


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _value_tokens(values: list[Any]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("candidate_contains_non_finite_value")
        tokens.append(number.hex())
    return tokens


def candidate_sha256(item: dict[str, Any]) -> str:
    """Hash candidate identity, source provenance, axis, representation and exact values."""
    document = {
        "id": str(item["id"]),
        "source": str(item["source"]),
        "source_sha256": item.get("sha256"),
        "cohort": str(item["cohort"]),
        "domain": str(item["domain"]),
        "frequency": str(item["frequency"]),
        "representation": item.get(
            "representation",
            "returns" if item["source"] in {"pink_sheet", "gem"} else "level",
        ),
        "axis": [str(value) for value in item["axis"]],
        "values_f64_hex": _value_tokens(item["values"]),
    }
    return hashlib.sha256(json_bytes(document)).hexdigest()


def _bootstrap_is_eligible(item: dict[str, Any]) -> bool:
    """Mirror boot()'s eligibility routing without running any bootstrap replicates."""
    if item.get("domain") == "seismic":
        return False

    values = np.asarray(item["values"], dtype=float)
    representation = item.get(
        "representation",
        "returns" if item.get("source") in {"pink_sheet", "gem"} else "level",
    )
    level_screen = p2.g1(values)
    if level_screen.get("passed"):
        return True

    if (
        item.get("domain") in p2.INTEGRATED_NULL_DOMAINS
        and representation == "level"
        and len(values) >= p2.STATIONARITY_MIN_OBSERVATIONS + 1
    ):
        difference_screen = p2.g1(
            np.diff(values),
            adf_significance=p2.INTEGRATED_ADF_SIGNIFICANCE,
            kpss_significance=p2.INTEGRATED_KPSS_SIGNIFICANCE,
        )
        return bool(difference_screen.get("passed"))

    return False


def estimate_cost(item: dict[str, Any]) -> tuple[int, bool]:
    """Conservative work estimate based on detector passes and bootstrap eligibility."""
    observations = len(item["values"])
    mode_count = max(1, len(p2.BreakDetectorV1.MODES))
    bootstrap_eligible = _bootstrap_is_eligible(item)
    expected_replicates = int(p2.REPS) if bootstrap_eligible else 0
    # Each eligible bootstrap replicate evaluates every frozen detector mode.
    weight = max(1, observations) * mode_count * (1 + expected_replicates)
    return int(weight), bootstrap_eligible


def candidate_manifest_entry(
    item: dict[str, Any],
    original_index: int,
    assigned_shard: int | None,
    execution_stage: str,
    weight: int,
    bootstrap_eligible: bool,
) -> dict[str, Any]:
    """Metadata-only registry entry. Never serialize Pink Sheet values."""
    item_metadata = {key: value for key, value in item.items() if key != "values"}
    entry = {
        "id": str(item["id"]),
        "original_index": int(original_index),
        "source": str(item["source"]),
        "source_sha256": item.get("sha256"),
        "candidate_sha256": candidate_sha256(item),
        "values_count": len(item["values"]),
        "estimated_weight": int(weight),
        "bootstrap_expected": bool(bootstrap_eligible),
        "bootstrap_replicates_expected": int(p2.REPS) if bootstrap_eligible else 0,
        "execution_stage": execution_stage,
        "shard": assigned_shard,
        "item_metadata": item_metadata,
    }
    if item["source"] == "pink_sheet" and "values" in entry["item_metadata"]:
        raise IntegrityError("pink_values_must_not_enter_candidate_registry")
    return entry


def weighted_shard_assignments(
    candidates: list[dict[str, Any]],
    shard_count: int = SHARD_COUNT,
) -> dict[str, int]:
    """Stable LPT assignment: largest estimated cost first, least-loaded shard next."""
    if shard_count < 1:
        raise ValueError("shard_count_must_be_positive")
    loads = [0] * shard_count
    assignments: dict[str, int] = {}
    ordered = sorted(
        candidates,
        key=lambda item: (
            -int(item["estimated_weight"]),
            int(item["original_index"]),
            str(item["id"]),
        ),
    )
    for candidate in ordered:
        shard = min(range(shard_count), key=lambda index: (loads[index], index))
        assignments[str(candidate["id"])] = shard
        loads[shard] += int(candidate["estimated_weight"])
    return assignments


def _evaluate_worker(payload: tuple[Any, ...]) -> dict[str, Any]:
    """Pickle-safe worker; seed identity remains inside the frozen eval_series/boot logic."""
    item, contract, bootstrap_replicates, expected_candidate_sha = payload
    previous_replicates = p2.REPS
    p2.REPS = int(bootstrap_replicates)
    try:
        result = p2.eval_series(item, contract)
    finally:
        p2.REPS = previous_replicates
    result["candidate_sha256"] = str(expected_candidate_sha)
    return result


def evaluate_items(
    items: list[dict[str, Any]],
    contract: dict[str, Any],
    workers: int,
    bootstrap_replicates: int | None = None,
) -> list[dict[str, Any]]:
    """Evaluate independent series concurrently while returning original input order."""
    if workers < 1:
        raise ValueError("workers_must_be_positive")
    replicates = int(p2.REPS if bootstrap_replicates is None else bootstrap_replicates)
    if replicates < 1:
        raise ValueError("bootstrap_replicates_must_be_positive")
    bounded_workers = min(int(workers), os.cpu_count() or 1, max(1, len(items)))
    payloads = [
        (item, contract, replicates, candidate_sha256(item))
        for item in items
    ]
    if bounded_workers <= 1 or len(payloads) <= 1:
        return [_evaluate_worker(payload) for payload in payloads]

    completed: dict[int, dict[str, Any]] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=bounded_workers) as executor:
        futures = {
            executor.submit(_evaluate_worker, payload): index
            for index, payload in enumerate(payloads)
        }
        for future in concurrent.futures.as_completed(futures):
            completed[futures[future]] = future.result()
    return [completed[index] for index in range(len(payloads))]


def _manifest_seed(contract: dict[str, Any], dependencies: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1.6",
        "pipeline_config": p2.PIPELINE_CONFIG,
        "gem_config": p2.GEM_CONFIG,
        "seismic_config": p2.SEISMIC_CONFIG,
        "run_timestamp_utc": p2.stamp(),
        "git_commit": os.getenv("GITHUB_SHA", "local-unresolved"),
        "branch": os.getenv("GITHUB_REF_NAME", "local"),
        "detector": "isolated_break_detector_v1",
        "markov_H": p2.H,
        "period": f"{p2.Y0}-01/{p2.Y1}-12",
        "stationarity_screen": {
            "method": "ADF plus KPSS preliminary screens",
            "scope": "null eligibility only; observed-series detector execution is independent",
            "minimum_observations": p2.STATIONARITY_MIN_OBSERVATIONS,
            "adf_significance": p2.STATIONARITY_ADF_SIGNIFICANCE,
            "kpss_significance": p2.STATIONARITY_KPSS_SIGNIFICANCE,
            "integrated_adf_significance": p2.INTEGRATED_ADF_SIGNIFICANCE,
            "integrated_kpss_significance": p2.INTEGRATED_KPSS_SIGNIFICANCE,
            "level_null_family": p2.LEVEL_NULL_FAMILY,
            "integrated_null_family": p2.INTEGRATED_NULL_FAMILY,
            "integrated_null_domains": sorted(p2.INTEGRATED_NULL_DOMAINS),
            "seismic_null_policy": p2.SEISMIC_NULL_POLICY,
        },
        "dependencies": dependencies,
        "bootstrap": {
            "method": "domain-routed conditional null diagnostics",
            "replicates": p2.REPS,
            "monthly_mean_block": p2.MONTH_BLOCK,
            "event_mean_block": p2.EVENT_BLOCK,
            "economic_null_routing": [
                "level_stationary_bootstrap",
                "integrated_first_difference_bootstrap",
                "no_null_when_both_screens_fail",
            ],
            "level_null_family": p2.LEVEL_NULL_FAMILY,
            "integrated_null_family": p2.INTEGRATED_NULL_FAMILY,
            "integrated_null_domains": sorted(p2.INTEGRATED_NULL_DOMAINS),
            "seismic_null_routing": "point_process_model_required",
            "seismic_generic_bootstrap_enabled": p2.BOOTSTRAP_CONFIG["seismic_generic_bootstrap_enabled"],
            "conditional_alarm_probability_only": p2.BOOTSTRAP_CONFIG["conditional_alarm_probability_only"],
            "operational_fpr_claim_permitted": p2.BOOTSTRAP_CONFIG["operational_fpr_claim_permitted"],
        },
        "shock_contract": contract,
        "sources": [],
        "gem_indicators": [],
        "belts": [],
        "errors": [],
        "rejected": [],
    }


def prepare(expected_candidates: int = EXPECTED_CANDIDATES, shard_count: int = SHARD_COUNT) -> dict[str, Any]:
    """Fetch each primary source once, privately evaluate Pink, and freeze shard inputs."""
    started = time.monotonic()
    for path in (p2.RAW, p2.DERIVED, p2.OUT, ARTIFACT_ROOT, SHARD_PAYLOAD_ROOT):
        path.mkdir(parents=True, exist_ok=True)

    contract = read_json(p2.HERE / "shock_event_contract.json")
    dependencies = p2.dependency_inventory()
    p2.DEPENDENCIES.write_text(
        json.dumps(dependencies, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_seed = _manifest_seed(contract, dependencies)

    print("PREPARE Pink Sheet", flush=True)
    pink_items = p2.pink(manifest_seed)
    print(f"PREPARE Pink accepted={len(pink_items)}", flush=True)
    print("PREPARE GEM", flush=True)
    gem_items = p2.gem(manifest_seed)
    print(f"PREPARE GEM accepted={len(gem_items)}", flush=True)
    print("PREPARE USGS", flush=True)
    seismic_items = p2.seismic(manifest_seed)
    print(f"PREPARE USGS accepted={len(seismic_items)}", flush=True)

    candidates = pink_items + gem_items + seismic_items
    if len(candidates) != int(expected_candidates):
        raise IntegrityError(
            f"candidate_count_mismatch:expected={expected_candidates}:actual={len(candidates)}"
        )
    if not pink_items or not seismic_items:
        raise IntegrityError("required_pink_or_seismic_cohort_missing")

    # Pink Sheet values remain in this job's memory. Only derived evaluations and
    # a metadata/hash registry are exported to GitHub artifacts.
    pink_started = time.monotonic()
    pink_workers = min(4, os.cpu_count() or 1, max(1, len(pink_items)))
    pink_results = evaluate_items(pink_items, contract, pink_workers)
    pink_result_by_id = {str(item["id"]): item for item in pink_results}
    pink_result_entries: list[dict[str, Any]] = []

    scored: list[tuple[int, dict[str, Any], int, bool]] = []
    for index, item in enumerate(candidates):
        weight, bootstrap_eligible = estimate_cost(item)
        scored.append((index, item, weight, bootstrap_eligible))

    matrix_scored = [
        (index, item, weight, eligible)
        for index, item, weight, eligible in scored
        if item["source"] != "pink_sheet"
    ]
    assignment_candidates = [
        {
            "id": item["id"],
            "original_index": index,
            "estimated_weight": weight,
        }
        for index, item, weight, _eligible in matrix_scored
    ]
    assignments = weighted_shard_assignments(assignment_candidates, shard_count)

    registry: list[dict[str, Any]] = []
    payloads: list[list[dict[str, Any]]] = [[] for _ in range(shard_count)]
    pink_count = 0
    for index, item, weight, eligible in scored:
        if item["source"] == "pink_sheet":
            entry = candidate_manifest_entry(
                item, index, None, "prepare_private", weight, eligible
            )
            result = pink_result_by_id.get(str(item["id"]))
            if result is None:
                raise IntegrityError(f"pink_prepare_result_missing:{item['id']}")
            pink_result_entries.append({
                "id": str(item["id"]),
                "original_index": index,
                "candidate_sha256": entry["candidate_sha256"],
                "result": result,
            })
            pink_count += 1
        else:
            shard = assignments[str(item["id"])]
            entry = candidate_manifest_entry(
                item, index, shard, "matrix", weight, eligible
            )
            payloads[shard].append({
                "original_index": index,
                "candidate_sha256": entry["candidate_sha256"],
                "item": item,
            })
        registry.append(entry)

    registry.sort(key=lambda item: item["original_index"])
    write_json(FROZEN_CANDIDATES, {
        "schema": SCHEMA_VERSION,
        "repository_commit": manifest_seed["git_commit"],
        "expected_series_count": int(expected_candidates),
        "shard_count": int(shard_count),
        "sharding_algorithm": "LPT_WEIGHTED_DETERMINISTIC",
        "weight_model": "observations * detector_modes * (1 + expected_bootstrap_replicates)",
        "pink_sheet_policy": "VALUES_MEMORY_ONLY; DERIVED_EVALUATION_AND_HASH_METADATA_ONLY",
        "candidates": registry,
    })
    for shard_index, shard_payload in enumerate(payloads):
        shard_payload.sort(key=lambda item: item["original_index"])
        write_json(SHARD_PAYLOAD_ROOT / f"shard-{shard_index}.json", {
            "schema": SCHEMA_VERSION,
            "repository_commit": manifest_seed["git_commit"],
            "shard_index": shard_index,
            "shard_count": shard_count,
            "items": shard_payload,
        })
    write_json(PINK_RESULTS, {
        "schema": SCHEMA_VERSION,
        "repository_commit": manifest_seed["git_commit"],
        "source_sha256": next(
            (source.get("sha256") for source in manifest_seed["sources"]
             if source.get("provider") == "World Bank Pink Sheet"),
            None,
        ),
        "results": pink_result_entries,
    })

    manifest_seed["pink_eligible"] = len(pink_items)
    manifest_seed["gem_eligible"] = len(gem_items)
    manifest_seed["seismic_eligible"] = len(seismic_items)
    state = {
        "schema": SCHEMA_VERSION,
        "repository_commit": manifest_seed["git_commit"],
        "expected_series_count": int(expected_candidates),
        "shard_count": int(shard_count),
        "pink_count": pink_count,
        "matrix_count": len(candidates) - pink_count,
        "pink_source_sha256": next(
            (source.get("sha256") for source in manifest_seed["sources"]
             if source.get("provider") == "World Bank Pink Sheet"),
            None,
        ),
        "manifest_seed": manifest_seed,
        "candidate_registry_sha256": file_sha256(FROZEN_CANDIDATES),
        "pink_results_sha256": file_sha256(PINK_RESULTS),
        "shard_payload_sha256": {
            str(index): file_sha256(SHARD_PAYLOAD_ROOT / f"shard-{index}.json")
            for index in range(shard_count)
        },
        "prepare_elapsed_seconds": round(time.monotonic() - started, 3),
        "pink_private_evaluation_elapsed_seconds": round(time.monotonic() - pink_started, 3),
        "pink_private_evaluation_workers": pink_workers,
        "shard_loads": [
            sum(int(item["estimated_weight"]) for item in registry if item["shard"] == index)
            for index in range(shard_count)
        ],
    }
    write_json(PREPARE_STATE, state)
    print(
        f"PREPARE_COMPLETE candidates={len(registry)} pink_private={pink_count} "
        f"matrix={len(candidates)-pink_count} elapsed={state['prepare_elapsed_seconds']}",
        flush=True,
    )
    return state


def _verify_prepare_artifacts(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("schema") != SCHEMA_VERSION:
        raise IntegrityError("prepare_schema_mismatch")
    if state.get("repository_commit") != os.getenv("GITHUB_SHA", state.get("repository_commit")):
        raise IntegrityError("prepare_commit_mismatch")
    if file_sha256(FROZEN_CANDIDATES) != state.get("candidate_registry_sha256"):
        raise IntegrityError("candidate_registry_sha256_mismatch")
    if file_sha256(PINK_RESULTS) != state.get("pink_results_sha256"):
        raise IntegrityError("pink_results_sha256_mismatch")
    return read_json(FROZEN_CANDIDATES)


def evaluate_shard(
    shard_index: int,
    shard_count: int = SHARD_COUNT,
    workers: int = 4,
    bootstrap_replicates: int | None = None,
) -> dict[str, Any]:
    """Evaluate exactly one immutable LPT shard; never writes a partial success."""
    state = read_json(PREPARE_STATE)
    registry_doc = _verify_prepare_artifacts(state)
    if int(state["shard_count"]) != int(shard_count):
        raise IntegrityError("shard_count_mismatch")
    if not 0 <= int(shard_index) < int(shard_count):
        raise ValueError("shard_index_out_of_range")

    payload_path = SHARD_PAYLOAD_ROOT / f"shard-{shard_index}.json"
    expected_payload_sha = state["shard_payload_sha256"].get(str(shard_index))
    if not payload_path.is_file() or file_sha256(payload_path) != expected_payload_sha:
        raise IntegrityError(f"shard_payload_missing_or_changed:{shard_index}")

    payload = read_json(payload_path)
    if (
        payload.get("repository_commit") != state["repository_commit"]
        or int(payload.get("shard_index", -1)) != int(shard_index)
        or int(payload.get("shard_count", -1)) != int(shard_count)
    ):
        raise IntegrityError(f"shard_payload_header_mismatch:{shard_index}")

    registry = registry_doc["candidates"]
    expected_entries = [
        item for item in registry
        if item.get("execution_stage") == "matrix"
        and int(item.get("shard", -1)) == int(shard_index)
    ]
    expected_ids = [item["id"] for item in expected_entries]
    payload_items = payload.get("items", [])
    payload_ids = [entry["item"]["id"] for entry in payload_items]
    if payload_ids != expected_ids:
        raise IntegrityError(f"shard_payload_id_order_mismatch:{shard_index}")

    expected_hashes = {entry["id"]: entry["candidate_sha256"] for entry in expected_entries}
    items: list[dict[str, Any]] = []
    for entry in payload_items:
        item = entry["item"]
        identifier = str(item["id"])
        actual_hash = candidate_sha256(item)
        if actual_hash != expected_hashes.get(identifier):
            raise IntegrityError(f"candidate_payload_hash_mismatch:{identifier}")
        if actual_hash != entry.get("candidate_sha256"):
            raise IntegrityError(f"shard_entry_hash_mismatch:{identifier}")
        items.append(item)

    contract = state["manifest_seed"]["shock_contract"]
    actual_workers = min(int(workers), os.cpu_count() or 1, 4)
    started = time.monotonic()
    results = evaluate_items(items, contract, actual_workers, bootstrap_replicates)
    envelope = {
        "schema": SCHEMA_VERSION,
        "repository_commit": state["repository_commit"],
        "shard_index": int(shard_index),
        "shard_count": int(shard_count),
        "expected_ids": expected_ids,
        "results": results,
        "worker_count": actual_workers,
        "bootstrap_replicates": int(
            p2.REPS if bootstrap_replicates is None else bootstrap_replicates
        ),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    destination = SHARD_RESULT_ROOT / f"shard-{shard_index}.json"
    write_json(destination, envelope)
    print(
        f"SHARD_COMPLETE shard={shard_index}/{shard_count} "
        f"series={len(results)} workers={actual_workers} "
        f"elapsed={envelope['elapsed_seconds']}",
        flush=True,
    )
    return envelope


def validate_result_records(
    expected_candidates: list[dict[str, Any]],
    result_records: list[dict[str, Any]],
    expected_count: int | None = None,
) -> list[dict[str, Any]]:
    """Strict exact-set, no-duplicate and source/candidate-hash gate."""
    if expected_count is not None and len(expected_candidates) != int(expected_count):
        raise IntegrityError(
            f"expected_registry_count_mismatch:{expected_count}:{len(expected_candidates)}"
        )
    expected_by_id: dict[str, dict[str, Any]] = {}
    for candidate in expected_candidates:
        identifier = str(candidate["id"])
        if identifier in expected_by_id:
            raise IntegrityError(f"duplicate_id_in_registry:{identifier}")
        expected_by_id[identifier] = candidate

    observed: dict[str, dict[str, Any]] = {}
    for result in result_records:
        identifier = str(result.get("id", ""))
        if not identifier:
            raise IntegrityError("result_missing_id")
        if identifier in observed:
            raise IntegrityError(f"duplicate_result_id:{identifier}")
        expected = expected_by_id.get(identifier)
        if expected is None:
            raise IntegrityError(f"unexpected_result_id:{identifier}")
        if result.get("candidate_sha256") != expected.get("candidate_sha256"):
            raise IntegrityError(f"candidate_sha256_mismatch:{identifier}")
        if result.get("sha256") != expected.get("source_sha256"):
            raise IntegrityError(f"source_sha256_mismatch:{identifier}")
        if int(result.get("observations", -1)) != int(expected.get("values_count", -2)):
            raise IntegrityError(f"observation_count_mismatch:{identifier}")
        observed[identifier] = result

    missing = sorted(set(expected_by_id) - set(observed))
    if missing:
        raise IntegrityError(f"missing_results:{len(missing)}:{','.join(missing[:10])}")
    if len(observed) != len(expected_by_id):
        raise IntegrityError("result_count_mismatch")

    return [observed[str(item["id"])] for item in sorted(
        expected_candidates, key=lambda value: int(value["original_index"])
    )]


def _load_all_shard_results(state: dict[str, Any], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for shard_index in range(int(state["shard_count"])):
        path = SHARD_RESULT_ROOT / f"shard-{shard_index}.json"
        if not path.is_file():
            raise IntegrityError(f"missing_shard_artifact:{shard_index}")
        envelope = read_json(path)
        if (
            envelope.get("schema") != SCHEMA_VERSION
            or envelope.get("repository_commit") != state["repository_commit"]
            or int(envelope.get("shard_index", -1)) != shard_index
            or int(envelope.get("shard_count", -1)) != int(state["shard_count"])
        ):
            raise IntegrityError(f"shard_envelope_header_mismatch:{shard_index}")
        expected_ids = [
            item["id"] for item in registry
            if item.get("execution_stage") == "matrix"
            and int(item.get("shard", -1)) == shard_index
        ]
        shard_results = envelope.get("results")
        if not isinstance(shard_results, list):
            raise IntegrityError(f"shard_results_not_list:{shard_index}")
        observed_ids = [item.get("id") for item in shard_results]
        if observed_ids != expected_ids:
            raise IntegrityError(f"shard_result_id_set_or_order_mismatch:{shard_index}")
        if envelope.get("expected_ids") != expected_ids:
            raise IntegrityError(f"shard_expected_ids_mismatch:{shard_index}")
        results.extend(shard_results)
    return results


def _restore_items_in_original_order(
    registry: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payload_by_id: dict[str, dict[str, Any]] = {}
    for shard_index in range(SHARD_COUNT):
        path = SHARD_PAYLOAD_ROOT / f"shard-{shard_index}.json"
        payload = read_json(path)
        for entry in payload.get("items", []):
            item = entry["item"]
            identifier = str(item["id"])
            if identifier in payload_by_id:
                raise IntegrityError(f"duplicate_candidate_payload:{identifier}")
            if candidate_sha256(item) != entry.get("candidate_sha256"):
                raise IntegrityError(f"candidate_payload_integrity_failure:{identifier}")
            payload_by_id[identifier] = item

    restored: list[dict[str, Any]] = []
    for entry in sorted(registry, key=lambda value: int(value["original_index"])):
        if entry["execution_stage"] == "prepare_private":
            item = dict(entry["item_metadata"])
            # Pink values are intentionally not persisted. normalized_csv() writes
            # blank values for this source and needs only an axis-length placeholder.
            item["values"] = [0.0] * int(entry["values_count"])
            restored.append(item)
            continue
        identifier = str(entry["id"])
        item = payload_by_id.get(identifier)
        if item is None:
            raise IntegrityError(f"candidate_payload_missing:{identifier}")
        if candidate_sha256(item) != entry["candidate_sha256"]:
            raise IntegrityError(f"candidate_payload_sha256_mismatch:{identifier}")
        restored.append(item)
    if len(restored) != len(registry):
        raise IntegrityError("restored_candidate_count_mismatch")
    return restored


def aggregate() -> dict[str, Any]:
    """Merge all 519 results, restore canonical order, then write auditable outputs."""
    started = time.monotonic()
    state = read_json(PREPARE_STATE)
    registry_doc = _verify_prepare_artifacts(state)
    registry = registry_doc.get("candidates", [])
    expected_count = int(state["expected_series_count"])
    if len(registry) != expected_count:
        raise IntegrityError("frozen_registry_count_mismatch")

    pink_document = read_json(PINK_RESULTS)
    if (
        pink_document.get("repository_commit") != state["repository_commit"]
        or pink_document.get("source_sha256") != state.get("pink_source_sha256")
    ):
        raise IntegrityError("pink_results_source_or_commit_mismatch")
    pink_entries = pink_document.get("results", [])
    pink_expected = [
        item for item in registry if item.get("execution_stage") == "prepare_private"
    ]
    if [entry.get("id") for entry in pink_entries] != [item["id"] for item in pink_expected]:
        raise IntegrityError("pink_private_result_set_or_order_mismatch")
    for entry, candidate in zip(pink_entries, pink_expected):
        if entry.get("candidate_sha256") != candidate.get("candidate_sha256"):
            raise IntegrityError(f"pink_candidate_sha256_mismatch:{candidate['id']}")
        if "values" in entry.get("result", {}):
            raise IntegrityError("pink_raw_values_must_not_be_published")

    matrix_results = _load_all_shard_results(state, registry)
    all_results = [entry["result"] for entry in pink_entries] + matrix_results
    canonical_results = validate_result_records(registry, all_results, expected_count)

    # Original source and candidate identity checks are completed before any
    # final report, checksum manifest, or release-ready output is written.
    items = _restore_items_in_original_order(registry)
    if [item["id"] for item in items] != [
        item["id"] for item in sorted(registry, key=lambda value: int(value["original_index"]))
    ]:
        raise IntegrityError("candidate_original_order_mismatch")

    manifest = copy.deepcopy(state["manifest_seed"])
    contract = manifest["shock_contract"]
    manifest["pink_eligible"] = int(state["pink_count"])
    manifest["gem_eligible"] = sum(
        1 for item in registry if item["source"] == "gem"
    )
    manifest["seismic_eligible"] = sum(
        1 for item in registry if item["source"] == "usgs"
    )
    manifest["series_results"] = canonical_results
    manifest["normalized"] = p2.normalized_csv(items)
    manifest["run_status"] = (
        "COMPLETED_WITH_SOURCE_WARNINGS" if manifest.get("errors") else "COMPLETED"
    )
    manifest["aggregate"] = p2.aggregate(canonical_results, contract)
    manifest["manifest_path"] = str(p2.MANIFEST.relative_to(ROOT))
    manifest["checksums_path"] = str(p2.CHECKSUMS.relative_to(ROOT))
    manifest["dependencies_path"] = str(p2.DEPENDENCIES.relative_to(ROOT))
    manifest["raw_snapshots"] = len(manifest.get("sources", []))
    manifest["distributed_evaluation"] = {
        "schema": SCHEMA_VERSION,
        "strategy": "prepare -> four weighted matrix shards -> strict aggregate",
        "expected_series": expected_count,
        "verified_series": len(canonical_results),
        "missing_series": 0,
        "duplicate_series": 0,
        "order_policy": "original_index_restored_before_aggregate",
        "shard_count": int(state["shard_count"]),
        "weight_model": registry_doc["weight_model"],
        "shard_loads": state.get("shard_loads", []),
        "pink_sheet_data_policy": "raw_values_memory_only_in_prepare; no raw values in artifacts",
        "prepare_elapsed_seconds": state.get("prepare_elapsed_seconds"),
        "aggregate_elapsed_seconds": round(time.monotonic() - started, 3),
    }

    # The normalized CSV, Manifest, checksums and report are written only after
    # all 519 result records have passed the strict integrity gate.
    sum_paths = [
        path for path in list(p2.RAW.rglob("*")) + list(p2.DERIVED.rglob("*"))
        if path.is_file()
    ]
    sum_paths += [
        p2.HERE / "run_pipeline.py",
        p2.HERE / "production_pipeline.py",
        p2.HERE / "shock_event_contract.json",
        p2.HERE / "requirements.txt",
        p2.HERE / "tests" / "test_pipeline.py",
        p2.HERE / "config" / "pipeline.json",
        p2.HERE / "config" / "gem_indicators.json",
        p2.HERE / "config" / "seismic_belts.json",
        p2.HERE / "README_AR.md",
        p2.DEPENDENCIES,
        FROZEN_CANDIDATES,
        PINK_RESULTS,
        PREPARE_STATE,
        ROOT / ".github" / "workflows" / "real-data-stress.yml",
        ROOT / "structural_engine" / "isolated_break_detector_v1" / "break_detector_v1.py",
        ROOT / "structural_engine" / "isolated_break_detector_v1" / "engine_fast_ref.py",
        ROOT / "structural_engine" / "isolated_break_detector_v1" / "engine_markov_cusum.py",
        ROOT / "tests" / "audits" / "test_p2_production_pipeline.py",
    ]
    checksums = []
    for path in sorted(set(path for path in sum_paths if path.exists())):
        checksums.append(
            f"{file_sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        )
    p2.CHECKSUMS.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    p2.MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    p2.REPORT.write_text(p2.make_report(manifest), encoding="utf-8")

    print(
        f"AGGREGATE_COMPLETE verified={len(canonical_results)}/{expected_count} "
        f"run_status={manifest['run_status']}",
        flush=True,
    )
    return {
        "status": manifest["run_status"],
        "series_count": len(canonical_results),
        "manifest_sha256": file_sha256(p2.MANIFEST),
        "checksums_sha256": file_sha256(p2.CHECKSUMS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--expected-candidates", type=int, default=EXPECTED_CANDIDATES)
    prepare_parser.add_argument("--shards", type=int, default=SHARD_COUNT)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--shard", type=int, required=True)
    evaluate_parser.add_argument("--shards", type=int, default=SHARD_COUNT)
    evaluate_parser.add_argument("--workers", type=int, default=4)

    aggregate_parser = subparsers.add_parser("aggregate")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.expected_candidates, args.shards)
        elif args.command == "evaluate":
            evaluate_shard(args.shard, args.shards, args.workers)
        elif args.command == "aggregate":
            result = aggregate()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        else:
            parser.error("unknown_command")
    except (OSError, ValueError, RuntimeError, ArithmeticError, KeyError, TypeError) as exc:
        print(f"PRODUCTION_PIPELINE_ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
