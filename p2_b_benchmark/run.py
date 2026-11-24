"""P2-B first operational detector competition on the frozen 509 economic series."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from p2_b_benchmark.engine import VARIANTS, mad_sigma, run_all

NULL_REPLICATES = 99
NULL_BLOCK_LENGTH = 12
BASE_SEED = 20261117
SHIFT_SIGMA = 3.0


def stationary_sample(values: np.ndarray, rng: np.random.Generator, mean_block: int) -> np.ndarray:
    n = int(values.size)
    if n == 0 or mean_block < 1:
        raise ValueError("stationary_sample_input_invalid")
    indices = np.empty(n, dtype=int)
    indices[0] = int(rng.integers(n))
    restart_probability = 1.0 / float(mean_block)
    for i in range(1, n):
        if rng.random() < restart_probability:
            indices[i] = int(rng.integers(n))
        else:
            indices[i] = (indices[i - 1] + 1) % n
    return values[indices]


def _seed_for(series_id: str) -> int:
    digest = hashlib.sha256(f"{BASE_SEED}:{series_id}".encode()).hexdigest()
    return int(digest[:16], 16)


def _one_series(item: dict[str, Any], null_replicates: int) -> dict[str, Any]:
    values = np.asarray(item["values"], dtype=float)
    quiet_sigma = mad_sigma(values[:40])
    zero_quiet_scale = not np.isfinite(quiet_sigma) or quiet_sigma <= 0
    result: dict[str, Any] = {
        "id": item["id"], "source": item["source"], "n": int(values.size),
        "null_eligible": bool(item["bootstrap_eligible"]),
        "observed_status": "ABSTAIN" if zero_quiet_scale else "OK",
        "abstain_reason": "ZERO_QUIET_SCALE" if zero_quiet_scale else None,
        "observed": {}, "null": {}, "injected": {}, "causal": {},
    }
    observed = run_all(values, causal_audit=True)
    for arm, payload in observed.items():
        result["observed"][arm] = int(payload.get("event_count", len(payload.get("hits", []))))
        result["causal"][arm] = {
            "violations": int(payload.get("causal_audit_violations") or 0),
            "unverifiable": int(payload.get("causal_audit_unverifiable_prefixes") or 0),
        }

    onset = max(52, int(values.size * 0.70))
    if zero_quiet_scale:
        for arm in VARIANTS:
            for label in ("positive_3sigma", "negative_3sigma"):
                result["injected"].setdefault(arm, {})[label] = {
                    "status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                    "detected": None, "delay": None, "pre_onset_alert": None,
                    "wrong_direction": None, "missed": None,
                }
    else:
        if onset >= values.size - 1:
            raise ValueError(f"injection_onset_out_of_range:{item['id']}")
        for sign, label in ((1, "positive_3sigma"), (-1, "negative_3sigma")):
            injected = values.copy()
            injected[onset:] += sign * SHIFT_SIGMA * quiet_sigma
            detected = run_all(injected, causal_audit=True)
            for arm, score in _score_all(detected, onset, sign, quiet_points=40).items():
                result["injected"].setdefault(arm, {})[label] = {"status": "OK", **score}
                result["causal"][arm]["violations"] += int(detected[arm].get("causal_audit_violations") or 0)
                result["causal"][arm]["unverifiable"] += int(detected[arm].get("causal_audit_unverifiable_prefixes") or 0)

    if result["null_eligible"]:
        rng = np.random.default_rng(_seed_for(str(item["id"])))
        counts = {arm: {"alarm_replicates": 0, "event_count": 0,
                        "valid_replicates": 0, "abstained_replicates": 0}
                  for arm in VARIANTS}
        for _ in range(null_replicates):
            sample = stationary_sample(values, rng, NULL_BLOCK_LENGTH)
            null_result = run_all(sample, causal_audit=False)
            for arm, payload in null_result.items():
                if payload.get("status") == "ABSTAIN":
                    counts[arm]["abstained_replicates"] += 1
                    continue
                counts[arm]["valid_replicates"] += 1
                events = int(payload.get("event_count", len(payload.get("hits", []))))
                counts[arm]["alarm_replicates"] += int(events > 0)
                counts[arm]["event_count"] += events
        result["null"] = {}
        for arm, payload in counts.items():
            valid = payload["valid_replicates"]
            result["null"][arm] = {
                **payload, "replicates_attempted": null_replicates,
                "conditional_alarm_probability": payload["alarm_replicates"] / valid if valid else None,
                "events_per_replicate": payload["event_count"] / valid if valid else None,
                "status": "OK" if valid else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
            }
    return result


def _hit_index(hit: dict[str, Any]) -> int:
    return int(hit.get("time", hit.get("index", -1)))


def _event_start_for_hit(payload: dict[str, Any], hit: dict[str, Any]) -> int:
    """Return the start of the event carrying a hit, not merely hit time."""
    hit_index = _hit_index(hit)
    hit_sign = int(hit.get("direction", hit.get("sign", 0)))
    for event in payload.get("events", []):
        start = int(event.get("start_index", event.get("time", hit_index)))
        evidence = event.get("evidence", [])
        if any(
            _hit_index(item) == hit_index
            and int(item.get("direction", item.get("sign", 0))) == hit_sign
            and str(item.get("detector", "")) == str(hit.get("detector", ""))
            for item in evidence
        ):
            return start
        end = int(event.get("end_index", start))
        if start <= hit_index <= end and int(event.get("sign", event.get("direction", 0))) == hit_sign:
            return start
    return hit_index


def _score_all(
    result: dict[str, Any], onset: int, sign: int, *, quiet_points: int = 40,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for arm, payload in result.items():
        if payload.get("status") == "ABSTAIN":
            output[arm] = {
                "status": "ABSTAIN",
                "abstain_reason": payload.get("abstain_reason", "ZERO_QUIET_SCALE"),
                "detected": None, "delay": None, "pre_onset_alert": None,
                "wrong_direction": None, "missed": None,
            }
            continue
        hits = payload.get("hits", [])
        correct = [
            _hit_index(hit) for hit in hits
            if _hit_index(hit) >= onset
            and int(hit.get("direction", hit.get("sign", 0))) == sign
            and _event_start_for_hit(payload, hit) >= onset
        ]
        wrong = [
            hit for hit in hits
            if _hit_index(hit) >= onset
            and int(hit.get("direction", hit.get("sign", 0))) == -sign
            and _event_start_for_hit(payload, hit) >= onset
        ]
        pre_event_starts = [
            int(event.get("start_index", event.get("time", -1)))
            for event in payload.get("events", [])
            if quiet_points <= int(event.get("start_index", event.get("time", -1))) < onset
        ]
        covered_hit_tokens = {
            (_hit_index(item), int(item.get("direction", item.get("sign", 0))),
             str(item.get("detector", "")))
            for event in payload.get("events", [])
            for item in event.get("evidence", [])
        }
        pre_hit_times = [
            _hit_index(hit) for hit in hits
            if quiet_points <= _hit_index(hit) < onset
            and (_hit_index(hit), int(hit.get("direction", hit.get("sign", 0))),
                 str(hit.get("detector", ""))) not in covered_hit_tokens
        ]
        first = min(correct) if correct else None
        output[arm] = {
            "status": "OK", "detected": first is not None,
            "delay": first - onset if first is not None else None,
            "pre_onset_alert": bool(pre_event_starts or pre_hit_times),
            "wrong_direction": bool(wrong), "missed": first is None,
        }
    return output


def _aggregate(rows: list[dict[str, Any]], null_replicates: int) -> dict[str, Any]:
    arms = list(VARIANTS)
    output: dict[str, Any] = {"null": {}, "injected": {}, "observed": {}, "causal": {}}
    for arm in arms:
        for cohort in ("all", "pink_sheet", "gem"):
            selected = [r for r in rows if cohort == "all" or r["source"] == cohort]
            eligible = [r for r in selected if r["null_eligible"] and r["null"].get(arm)]
            if eligible:
                attempted = len(eligible) * null_replicates
                valid = sum(r["null"][arm]["valid_replicates"] for r in eligible)
                abstained = sum(r["null"][arm]["abstained_replicates"] for r in eligible)
                alarm_count = sum(r["null"][arm]["alarm_replicates"] for r in eligible)
                events = sum(r["null"][arm]["event_count"] for r in eligible)
                series_probs = [r["null"][arm]["conditional_alarm_probability"]
                                for r in eligible if r["null"][arm]["conditional_alarm_probability"] is not None]
                total_observations = sum(int(r["n"]) for r in eligible)
                total_valid_observations = sum(
                    int(r["n"]) * int(r["null"][arm]["valid_replicates"])
                    for r in eligible
                )
                output["null"].setdefault(arm, {})[cohort] = {
                    "series": len(eligible), "replicates_attempted": attempted,
                    "replicates_eligible": valid, "replicates_abstained_zero_quiet_scale": abstained,
                    "total_series_observations": total_observations,
                    "total_valid_bootstrap_observations": total_valid_observations,
                    "conditional_alarm_probability_pooled": alarm_count / valid if valid else None,
                    "events_per_replicate_pooled": events / valid if valid else None,
                    "events_per_1000_observations": (events / total_valid_observations * 1000.0) if total_valid_observations else None,
                    "mean_series_alarm_probability": statistics.mean(series_probs) if series_probs else None,
                    "median_series_alarm_probability": statistics.median(series_probs) if series_probs else None,
                    "p90_series_alarm_probability": float(np.quantile(series_probs, 0.90)) if series_probs else None,
                    "status": "OK" if valid else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
                    "interpretation": "conditional stationary-bootstrap diagnostic on eligible replicates only; not operational FPR",
                }
        for cohort in ("all", "pink_sheet", "gem"):
            selected = [r for r in rows if cohort == "all" or r["source"] == cohort]
            for scenario in ("positive_3sigma", "negative_3sigma"):
                all_outcomes = [r["injected"].get(arm, {}).get(scenario) for r in selected]
                all_outcomes = [o for o in all_outcomes if o is not None]
                abstained_outcomes = [o for o in all_outcomes if o.get("status") == "ABSTAIN"]
                outcomes = [o for o in all_outcomes if o.get("status", "OK") != "ABSTAIN"]
                delays = [o["delay"] for o in outcomes if o["delay"] is not None]
                if all_outcomes:
                    output["injected"].setdefault(arm, {}).setdefault(scenario, {})[cohort] = {
                        "series": len(all_outcomes), "eligible_series": len(outcomes),
                        "abstained_zero_quiet_scale_series": len(abstained_outcomes),
                        "sensitivity": sum(bool(o["detected"]) for o in outcomes) / len(outcomes) if outcomes else None,
                        "miss_rate": sum(bool(o["missed"]) for o in outcomes) / len(outcomes) if outcomes else None,
                        "pre_onset_false_alert_rate": sum(bool(o["pre_onset_alert"]) for o in outcomes) / len(outcomes) if outcomes else None,
                        "wrong_direction_rate": sum(bool(o["wrong_direction"]) for o in outcomes) / len(outcomes) if outcomes else None,
                        "median_detection_delay": statistics.median(delays) if delays else None,
                        "p90_detection_delay": float(np.quantile(delays, 0.90)) if delays else None,
                        "missed_series": sum(bool(o["missed"]) for o in outcomes),
                        "status": "OK" if outcomes else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
                    }
            observed_counts = [r["observed"].get(arm, 0) for r in selected]
            abstained_observed = sum(r.get("observed_status") == "ABSTAIN" for r in selected)
            output["observed"].setdefault(arm, {})[cohort] = {
                "series": len(selected), "series_eligible": len(selected) - abstained_observed,
                "abstained_zero_quiet_scale_series": abstained_observed,
                "series_with_events": sum(c > 0 for c in observed_counts),
                "observed_event_count": sum(observed_counts),
                "interpretation": "descriptive only; historical labels are not adjudicated",
            }
            audit = [r["causal"].get(arm, {"violations": 0, "unverifiable": 0}) for r in selected]
            violations = sum(int(item.get("violations", 0)) for item in audit)
            unverifiable = sum(int(item.get("unverifiable", 0)) for item in audit)
            output["causal"].setdefault(arm, {})[cohort] = {
                "series": len(selected),
                "prefix_replay_or_mutation_violations": violations,
                "unverifiable_short_prefix_events": unverifiable,
                "status": (
                    "FAIL_LOOKAHEAD_OR_PREFIX_INCONSISTENCY" if violations else
                    "PARTIAL_UNVERIFIABLE_SHORT_PREFIXES" if unverifiable else "PASS"
                ),
            }
    return output


def _sorted_ids_sha256(sorted_ids: list[str]) -> str:
    """Fingerprint only the sorted public series identifiers, never observations."""
    payload = json.dumps(sorted_ids, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _series_manifest_sha256(series_or_rows: list[dict[str, Any]]) -> str:
    """Fingerprint the ordered series identity/eligibility manifest, never values."""
    manifest = []
    for item in sorted(series_or_rows, key=lambda row: str(row["id"])):
        n = int(item.get("n", len(item.get("values", []))))
        eligible = bool(item.get("null_eligible", item.get("bootstrap_eligible", False)))
        manifest.append({
            "id": str(item["id"]),
            "source": str(item["source"]),
            "n": n,
            "null_eligible": eligible,
        })
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_protocol(null_replicates: int) -> dict[str, Any]:
    return {
        "input_scope": "51 Pink Sheet + 458 GEM monthly log-return series; USGS excluded from this economic first batch",
        "source_artifact_run": 45244943216,
        "parallel_fusion_git_blob_sha1": "f294c5312bec2d21492ed829071bf948fca0e8e1",
        "break_detector_git_blob_sha1": "10426c108b9786b7a565ba1796b943b6d44ee130",
        "null_replicates_per_eligible_series": null_replicates,
        "null_method": "Politis-Romano stationary bootstrap on observed returns; mean block length 12",
        "injected_break": f"persistent +/-{SHIFT_SIGMA} x quiet MAD sigma at 70% of each series",
        "quiet_window_observations": 40,
        "no_lookahead": "past-only rolling scales for Parallel Fusion; per-hit/per-event prefix replay and future-suffix mutation audit for Parallel Fusion; per-event prefix replay for BreakDetectorV1",
        "detectors": VARIANTS,
        "series_order": "ascending item id before deterministic round-robin sharding",
        "sharding": "sorted_index modulo shard_count; per-series random seed depends only on series_id",
        "scoring": "events must start at or after injected onset to count as detections; pre-onset window is [quiet_points, onset), including event starts before onset even if later evidence follows",
        "zero_quiet_scale_policy": "ABSTAIN / ZERO_QUIET_SCALE; abstentions are recorded and excluded from conditional null/injected denominators",
    }


def _limitations() -> list[str]:
    return [
        "The 359 eligible series pass only the existing preliminary null-eligibility screen; bootstrap probabilities are conditional diagnostics, not real-world false-positive rates.",
        "Pink Sheet and GEM historical source vintages/available_at histories are not present in the pinned input artifact; this audit tests detector-time causality on the as-downloaded snapshot, not historical point-in-time source availability.",
        "The 150 null-ineligible series are still included in observed replay and injected-break sensitivity/delay measurements.",
        "Historical observed events have no adjudicated ground truth and are descriptive, not labelled false alarms.",
        "Injected breaks provide controlled sensitivity/delay and miss-rate measurements, not proof that historical events are correctly classified.",
        "Series or stationary-bootstrap replicates with zero MAD in the initial quiet window abstain as ZERO_QUIET_SCALE and are excluded from eligible metric denominators, with abstention counts reported.",
        "FOCuS, BOCPD and R-FPOP implementations were not found in the tracked main-phase2 code; no substitute implementation is silently claimed in this first PR.",
    ]


def _partition_series(series: list[dict[str, Any]], shard_index: int, shard_count: int) -> list[dict[str, Any]]:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index_or_count_invalid")
    ordered = sorted(series, key=lambda item: str(item["id"]))
    return [item for index, item in enumerate(ordered) if index % shard_count == shard_index]


def run_benchmark(
    prepared_zip: str,
    *,
    null_replicates: int = NULL_REPLICATES,
    workers: int = 4,
    shard_index: int = 0,
    shard_count: int = 1,
    emit_shard_rows: bool = False,
    run_id: str | None = None,
    run_attempt: int | None = None,
) -> dict[str, Any]:
    if not 1 <= null_replicates <= 999:
        raise ValueError("null_replicates_out_of_range")
    if workers < 1:
        raise ValueError("workers_must_be_positive")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard_index_or_count_invalid")
    if shard_count > 1 and not emit_shard_rows:
        raise ValueError("multi_shard_execution_requires_emit_shard_rows")
    if emit_shard_rows and (not run_id or not isinstance(run_attempt, int) or run_attempt < 1):
        raise ValueError("shard_execution_requires_run_id_and_positive_run_attempt")

    from p2_b_benchmark.dataset import load_p2_economic_series

    series, source_counts = load_p2_economic_series(prepared_zip)
    # Sort before modulo assignment: every matrix runner must derive the exact same partition.
    series = sorted(series, key=lambda item: str(item["id"]))
    ordered_ids = [str(item["id"]) for item in series]
    sorted_ids_sha256 = _sorted_ids_sha256(ordered_ids)
    series_manifest_sha256 = _series_manifest_sha256(series)
    selected = [item for index, item in enumerate(series) if index % shard_count == shard_index]
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    last_progress = 0
    actual_workers = max(1, min(workers, os.cpu_count() or 1))
    label = f"[shard {shard_index}/{shard_count}]" if emit_shard_rows else "[benchmark]"
    print(f"{label} starting {len(selected)}/{len(series)} series with {actual_workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=actual_workers) as pool:
        futures = {pool.submit(_one_series, item, null_replicates): item["id"] for item in selected}
        for future in as_completed(futures):
            rows.append(future.result())
            processed = len(rows)
            if processed % 25 == 0:
                elapsed = time.perf_counter() - started
                print(f"{label} processed {processed}/{len(selected)} series ({elapsed:.1f}s)", flush=True)
                last_progress = processed
    rows.sort(key=lambda row: row["id"])
    elapsed = time.perf_counter() - started
    if len(rows) != len(selected):
        raise RuntimeError(f"shard_result_count_mismatch:{len(rows)}:{len(selected)}")
    if last_progress != len(rows):
        print(f"{label} processed {len(rows)}/{len(selected)} series ({elapsed:.1f}s)", flush=True)
    print(f"{label} completed {len(rows)}/{len(selected)} series (total {elapsed:.1f}s)", flush=True)

    protocol = _build_protocol(null_replicates)
    if emit_shard_rows:
        return {
            "schema": "chaos-p2-b-shard-v2",
            "shard_index": shard_index,
            "shard_count": shard_count,
            "run_id": str(run_id),
            "run_attempt": run_attempt,
            "expected_series_count": len(series),
            "expected_shard_rows": len(selected),
            "null_replicates": null_replicates,
            "series_manifest_sha256": series_manifest_sha256,
            "sorted_ids_sha256": sorted_ids_sha256,
            "sorted_ids": ordered_ids,
            "protocol": protocol,
            "source_integrity": source_counts,
            "series_results": rows,
        }

    return {
        "schema": "chaos-p2-b-detector-competition-v1",
        "protocol": protocol,
        "source_integrity": source_counts,
        "series_manifest_sha256": series_manifest_sha256,
        "execution": {"mode": "single", "workers": actual_workers},
        "summary": _aggregate(rows, null_replicates),
        "series_results": rows,
        "limitations": _limitations(),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _assert_metrics_only(value: Any, path: str = "series_results") -> None:
    forbidden = {"values", "axis", "raw_values", "observations", "raw_observations", "levels"}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                raise ValueError(f"raw_series_field_forbidden:{path}.{key}")
            _assert_metrics_only(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_metrics_only(child, f"{path}[{index}]")


class ShardAggregationError(ValueError):
    """Validation failure with a machine-readable missing-shard/series report."""

    def __init__(self, code: str, **diagnostic: Any):
        self.diagnostic = {"code": code, **diagnostic}
        detail = {key: value for key, value in diagnostic.items() if key != "missing_series_ids"}
        if diagnostic.get("missing_series_ids") is not None:
            detail["missing_series_ids_count"] = len(diagnostic["missing_series_ids"])
            detail["missing_series_ids_sample"] = diagnostic["missing_series_ids"][:12]
        super().__init__(f"{code}:{_canonical_json(detail)}")


def combine_shard_documents(
    shards: list[dict[str, Any]], *, expected_series_count: int = 509,
) -> dict[str, Any]:
    """Validate and deterministically combine one complete, single-attempt shard set."""
    if not shards:
        raise ShardAggregationError(
            "no_shard_documents_found", missing_shard_indices=list(range(4)),
            missing_series_ids=None,
        )
    first = shards[0]
    shard_count = int(first.get("shard_count", 0))
    if shard_count < 1 or shard_count > 32:
        raise ShardAggregationError("shard_count_invalid", shard_count=shard_count)

    expected_indices = set(range(shard_count))
    actual_indices = [int(doc.get("shard_index", -1)) for doc in shards]
    actual_set = set(actual_indices)
    missing_shards = sorted(expected_indices - actual_set)
    duplicates = sorted({x for x in actual_indices if actual_indices.count(x) > 1})

    raw_sorted_ids = first.get("sorted_ids")
    if (not isinstance(raw_sorted_ids, list) or
            not all(isinstance(value, str) and value for value in raw_sorted_ids)):
        raise ShardAggregationError(
            "sorted_ids_manifest_missing", missing_shard_indices=missing_shards,
            missing_series_ids=None,
        )
    sorted_ids = list(raw_sorted_ids)
    if sorted_ids != sorted(set(sorted_ids)) or len(sorted_ids) != expected_series_count:
        raise ShardAggregationError(
            "sorted_ids_manifest_invalid", expected_series_count=expected_series_count,
            actual_series_count=len(sorted_ids), missing_shard_indices=missing_shards,
            missing_series_ids=None,
        )
    sorted_ids_sha256 = _sorted_ids_sha256(sorted_ids)
    if str(first.get("sorted_ids_sha256", "")) != sorted_ids_sha256:
        raise ShardAggregationError("sorted_ids_sha256_mismatch", missing_shard_indices=missing_shards)

    if int(first.get("expected_series_count", -1)) != expected_series_count:
        raise ShardAggregationError("expected_series_count_mismatch", missing_shard_indices=missing_shards)

    protocol_token = _canonical_json(first.get("protocol"))
    source_token = _canonical_json(first.get("source_integrity"))
    manifest_token = str(first.get("series_manifest_sha256", ""))
    replicates = int(first.get("null_replicates", 0))
    run_id = str(first.get("run_id", ""))
    run_attempt = int(first.get("run_attempt", 0))
    if not run_id or run_attempt < 1:
        raise ShardAggregationError("shard_run_identity_missing", missing_shard_indices=missing_shards)

    rows: list[dict[str, Any]] = []
    row_owner: dict[str, int] = {}
    expected_shard_rows = {index: len(range(index, expected_series_count, shard_count))
                           for index in range(shard_count)}
    for doc in shards:
        index = int(doc.get("shard_index", -1))
        if doc.get("schema") != "chaos-p2-b-shard-v2":
            raise ShardAggregationError("shard_schema_invalid", shard_index=index, missing_shard_indices=missing_shards)
        if int(doc.get("shard_count", -1)) != shard_count:
            raise ShardAggregationError("shard_count_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if str(doc.get("run_id", "")) != run_id or int(doc.get("run_attempt", 0)) != run_attempt:
            raise ShardAggregationError("mixed_run_or_attempt", shard_index=index, missing_shard_indices=missing_shards)
        if int(doc.get("expected_series_count", -1)) != expected_series_count:
            raise ShardAggregationError("expected_series_count_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if int(doc.get("null_replicates", -1)) != replicates:
            raise ShardAggregationError("null_replicates_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if _canonical_json(doc.get("protocol")) != protocol_token:
            raise ShardAggregationError("protocol_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if _canonical_json(doc.get("source_integrity")) != source_token:
            raise ShardAggregationError("source_integrity_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if str(doc.get("series_manifest_sha256", "")) != manifest_token:
            raise ShardAggregationError("series_manifest_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        if str(doc.get("sorted_ids_sha256", "")) != sorted_ids_sha256 or doc.get("sorted_ids") != sorted_ids:
            raise ShardAggregationError("sorted_ids_manifest_disagreement", shard_index=index, missing_shard_indices=missing_shards)
        shard_rows = doc.get("series_results")
        if not isinstance(shard_rows, list):
            raise ShardAggregationError("series_results_missing_or_invalid", shard_index=index, missing_shard_indices=missing_shards)
        if len(shard_rows) != expected_shard_rows[index] or int(doc.get("expected_shard_rows", -1)) != expected_shard_rows[index]:
            expected_ids_for_shard = [
                series_id for sorted_index, series_id in enumerate(sorted_ids)
                if sorted_index % shard_count == index
            ]
            actual_ids_for_shard = {str(row.get("id", "")) for row in shard_rows if isinstance(row, dict)}
            missing_ids_for_shard = sorted(set(expected_ids_for_shard) - actual_ids_for_shard)
            raise ShardAggregationError(
                "shard_row_count_mismatch", shard_index=index,
                expected_rows=expected_shard_rows[index], actual_rows=len(shard_rows),
                missing_shard_indices=missing_shards,
                missing_series_ids=missing_ids_for_shard,
                missing_ids_by_shard={str(index): missing_ids_for_shard},
            )
        _assert_metrics_only(shard_rows)
        for row in shard_rows:
            identifier = str(row.get("id", ""))
            if not identifier:
                raise ShardAggregationError("series_id_missing_in_shard", shard_index=index, missing_shard_indices=missing_shards)
            if identifier in row_owner:
                raise ShardAggregationError("duplicate_series_id", series_id=identifier, missing_shard_indices=missing_shards)
            row_owner[identifier] = index
            rows.append(row)

    actual_ids = set(row_owner)
    expected_ids = set(sorted_ids)
    missing_ids = sorted(expected_ids - actual_ids)
    unexpected_ids = sorted(actual_ids - expected_ids)
    if missing_shards or duplicates or missing_ids or unexpected_ids or len(shards) != shard_count:
        missing_by_shard = {
            str(index): [series_id for sorted_index, series_id in enumerate(sorted_ids)
                         if sorted_index % shard_count == index]
            for index in missing_shards
        }
        raise ShardAggregationError(
            "shard_coverage_incomplete_or_invalid",
            expected_shard_indices=sorted(expected_indices),
            received_shard_indices=sorted(actual_set),
            missing_shard_indices=missing_shards, duplicates=duplicates,
            missing_series_ids=missing_ids, missing_ids_by_shard=missing_by_shard,
            unexpected_series_ids=unexpected_ids,
        )

    if len(rows) != expected_series_count:
        raise ShardAggregationError(
            "series_count_mismatch", expected=expected_series_count, actual=len(rows),
            missing_shard_indices=missing_shards, missing_series_ids=missing_ids,
        )
    rows.sort(key=lambda row: str(row["id"]))
    if _series_manifest_sha256(rows) != manifest_token:
        raise ShardAggregationError("series_manifest_sha256_mismatch", missing_shard_indices=[])
    for sorted_index, row in enumerate(rows):
        expected_owner = sorted_index % shard_count
        actual_owner = row_owner[str(row["id"])]
        if actual_owner != expected_owner:
            raise ShardAggregationError(
                "series_in_wrong_shard", series_id=row["id"],
                expected_shard=expected_owner, actual_shard=actual_owner, missing_shard_indices=[],
            )

    actual_counts = {
        "series": len(rows),
        "pink_sheet": sum(row["source"] == "pink_sheet" for row in rows),
        "gem": sum(row["source"] == "gem" for row in rows),
        "null_eligible": sum(bool(row["null_eligible"]) for row in rows),
        "null_eligible_pink_sheet": sum(row["source"] == "pink_sheet" and bool(row["null_eligible"]) for row in rows),
        "null_eligible_gem": sum(row["source"] == "gem" and bool(row["null_eligible"]) for row in rows),
    }
    expected_counts = {
        "series": 509, "pink_sheet": 51, "gem": 458,
        "null_eligible": 359, "null_eligible_pink_sheet": 48, "null_eligible_gem": 311,
    }
    if expected_series_count == 509 and actual_counts != expected_counts:
        raise ShardAggregationError("series_cohort_counts_mismatch", actual_counts=actual_counts, missing_shard_indices=[])
    source_integrity = first.get("source_integrity")
    for key, value in actual_counts.items():
        if source_integrity.get(key) != value:
            raise ShardAggregationError("source_integrity_row_count_mismatch", field=key, missing_shard_indices=[])

    return {
        "schema": "chaos-p2-b-detector-competition-v1",
        "protocol": first["protocol"],
        "source_integrity": source_integrity,
        "series_manifest_sha256": manifest_token,
        "sorted_ids_sha256": sorted_ids_sha256,
        "execution": {
            "mode": "matrix_shards", "shard_count": shard_count,
            "run_id": run_id, "run_attempt": run_attempt,
            "shard_rows": expected_shard_rows,
        },
        "summary": _aggregate(rows, replicates),
        "series_results": rows,
        "limitations": _limitations(),
    }


def _resolve_shard_files(specs: list[str]) -> list[Path]:
    found: list[Path] = []
    for spec in specs:
        path = Path(spec)
        if path.is_dir():
            found.extend(sorted(path.glob("shard_*_of_*.json")))
        elif path.is_file():
            found.append(path)
        else:
            raise ShardAggregationError(
                "shard_artifact_path_not_found", path=spec,
                missing_shard_indices=[0, 1, 2, 3], missing_series_ids=None,
            )
    unique = {path.resolve(): path for path in found}
    return sorted(unique.values(), key=lambda path: path.name)


def aggregate_shard_files(specs: list[str], *, output_dir: str | Path) -> dict[str, Any]:
    paths = _resolve_shard_files(specs)
    if not paths:
        raise ShardAggregationError(
            "no_shard_documents_found", missing_shard_indices=[0, 1, 2, 3],
            missing_series_ids=None,
        )
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return combine_shard_documents(documents, expected_series_count=509)


def write_shard_rows(shard: dict[str, Any], output_dir: str | Path) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"shard_{int(shard['shard_index'])}_of_{int(shard['shard_count'])}.json"
    path.write_text(json.dumps(shard, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def write_aggregation_failure(exc: Exception, output_dir: str | Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "P2_B_SHARD_AGGREGATION_FAILURE.json"
    md_path = output / "P2_B_SHARD_AGGREGATION_FAILURE_AR.md"
    payload = {
        "schema": "chaos-p2-b-shard-aggregation-failure-v1",
        "status": "FAIL_INCOMPLETE_OR_INCONSISTENT_SHARDS",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "diagnostic": getattr(exc, "diagnostic", None),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "# P2-B — تعذر تجميع الشرائح\n\n"
        "لم تُنتج هذه المحاولة تقرير نتائج نهائياً؛ لا تُفسَّر أي نتائج جزئية على أنها نتائج المجموعة الكاملة.\n\n"
        f"- نوع الخطأ: `{type(exc).__name__}`\n- التفاصيل: `{exc}`\n"
        + (
            "\n## الشرائح المفقودة\n\n"
            + ", ".join(map(str, exc.diagnostic.get("missing_shard_indices", [])))
            + "\n\n## معرّفات السلاسل المفقودة\n\n"
            + ", ".join(exc.diagnostic.get("missing_series_ids", []) or [])
            if isinstance(exc, ShardAggregationError) else ""
        ),
        encoding="utf-8",
    )
    return json_path, md_path

def write_outputs(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "P2_B_DETECTOR_COMPETITION_V1.json"
    md_path = output / "P2_B_DETECTOR_COMPETITION_V1_AR.md"
    # Only metrics/provenance are written; neither Pink nor GEM raw values are emitted.
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    lines = [
        "# P2-B — مقارنة الكواشف على 509 سلسلة اقتصادية",
        "",
        f"- السلاسل: {report['source_integrity']['series']} (Pink Sheet: {report['source_integrity']['pink_sheet']}, GEM: {report['source_integrity']['gem']}).",
        f"- أهلية null الأولية: {report['source_integrity']['null_eligible']} (Pink: {report['source_integrity']['null_eligible_pink_sheet']}, GEM: {report['source_integrity']['null_eligible_gem']}).",
        f"- تكرارات null لكل سلسلة مؤهلة: {report['protocol']['null_replicates_per_eligible_series']}.",
        "- جميع النتائج أدناه منفصلة حسب الكاشف والفوج؛ لا يوجد رقم عالمي يخلط المجالات.",
    ]
    for cohort, label in (("all", "الإجمالي"), ("pink_sheet", "Pink Sheet"), ("gem", "GEM")):
        lines.extend(["", f"## Conditional null diagnostic — {label}", "",
                      "| Arm | P(≥1 alarm) | Events / replicate | Events / 1,000 observations | Mean series probability | Abstained replicates |",
                      "|---|---:|---:|---:|---:|---:|"])
        for arm in VARIANTS:
            row = summary["null"].get(arm, {}).get(cohort)
            if row:
                lines.append(
                    f"| {arm} | {row['conditional_alarm_probability_pooled'] if row['conditional_alarm_probability_pooled'] is not None else 'NA'} | "
                    f"{row['events_per_replicate_pooled'] if row['events_per_replicate_pooled'] is not None else 'NA'} | "
                    f"{row['events_per_1000_observations'] if row['events_per_1000_observations'] is not None else 'NA'} | "
                    f"{row['mean_series_alarm_probability'] if row['mean_series_alarm_probability'] is not None else 'NA'} | "
                    f"{row['replicates_abstained_zero_quiet_scale']} |"
                )
    for cohort, label in (("all", "الإجمالي"), ("pink_sheet", "Pink Sheet"), ("gem", "GEM")):
        lines.extend(["", f"## Injected-break results — {label}", "",
                      "| Arm | Scenario | Sensitivity | Miss rate | Pre-onset alert | Median delay |",
                      "|---|---|---:|---:|---:|---:|"])
        for arm in VARIANTS:
            for scenario in ("positive_3sigma", "negative_3sigma"):
                row = summary["injected"].get(arm, {}).get(scenario, {}).get(cohort)
                if row:
                    lines.append(
                        f"| {arm} | {scenario} | {row['sensitivity'] if row['sensitivity'] is not None else 'NA'} | "
                        f"{row['miss_rate'] if row['miss_rate'] is not None else 'NA'} | "
                        f"{row['pre_onset_false_alert_rate'] if row['pre_onset_false_alert_rate'] is not None else 'NA'} | "
                        f"{row['median_detection_delay']} |"
                    )
    lines.extend(["", "## No-lookahead audit", "",
                  "| Arm | Prefix violations | Unverifiable short prefixes | Status |",
                  "|---|---:|---:|---|"])
    for arm in VARIANTS:
        row = summary["causal"].get(arm, {}).get("all", {})
        lines.append(
            f"| {arm} | {row.get('prefix_replay_or_mutation_violations', 'NA')} | "
            f"{row.get('unverifiable_short_prefix_events', 'NA')} | {row.get('status', 'NA')} |"
        )
    lines.extend(["", "## قيود التفسير", ""] + [f"- {item}" for item in report["limitations"]])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def load_detector_plugins(module_names: list[str]) -> list[str]:
    """Import explicitly configured extension modules before sizing benchmark arms."""
    loaded: list[str] = []
    for raw_name in module_names:
        name = raw_name.strip()
        if not name:
            continue
        if name in loaded:
            continue
        importlib.import_module(name)
        loaded.append(name)
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-zip")
    parser.add_argument("--output-dir", default="artifacts/p2_b")
    parser.add_argument("--null-replicates", type=int, default=NULL_REPLICATES)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--emit-shard-rows", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--run-attempt", type=int)
    parser.add_argument(
        "--aggregate-shards", nargs="+", metavar="PATH",
        help="Directory containing shard_*/_of_*.json files, or explicit shard JSON paths; no source download is performed",
    )
    parser.add_argument(
        "--plugin-module", action="append", default=[],
        help="Python module that registers additional detector arms before the benchmark starts",
    )
    args = parser.parse_args()
    env_plugins = [x for x in os.environ.get("P2B_DETECTOR_PLUGIN_MODULES", "").split(",") if x.strip()]
    loaded_plugins = load_detector_plugins([*env_plugins, *args.plugin_module])

    if args.aggregate_shards:
        if args.prepared_zip:
            parser.error("--prepared-zip must not be supplied with --aggregate-shards")
        try:
            report = aggregate_shard_files(args.aggregate_shards, output_dir=args.output_dir)
        except Exception as exc:
            failure_json, failure_md = write_aggregation_failure(exc, args.output_dir)
            print(f"P2-B shard aggregation failed: {type(exc).__name__}: {exc}", flush=True)
            print(json.dumps({"failure_json": str(failure_json), "failure_report": str(failure_md)}, ensure_ascii=False), flush=True)
            return 2
        json_path, md_path = write_outputs(report, args.output_dir)
        print("=== P2_B_DETECTOR_COMPETITION_V1_AR.md ===", flush=True)
        print(md_path.read_text(encoding="utf-8"), flush=True)
        print("=== P2_B_DETECTOR_COMPETITION_V1 summary JSON (aggregates only) ===", flush=True)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True), flush=True)
        print(json.dumps({"json": str(json_path), "report": str(md_path),
                          "loaded_detector_plugins": loaded_plugins,
                          "registered_arms": list(VARIANTS),
                          "series": report["source_integrity"]["series"]}, ensure_ascii=False), flush=True)
        return 0

    if not args.prepared_zip:
        parser.error("--prepared-zip is required unless --aggregate-shards is used")
    report = run_benchmark(
        args.prepared_zip,
        null_replicates=args.null_replicates,
        workers=args.workers,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        emit_shard_rows=args.emit_shard_rows,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
    )
    if args.emit_shard_rows:
        shard_path = write_shard_rows(report, args.output_dir)
        print(json.dumps({
            "shard_json": str(shard_path),
            "shard_index": report["shard_index"],
            "shard_count": report["shard_count"],
            "series_processed": len(report["series_results"]),
            "series_manifest_sha256": report["series_manifest_sha256"],
            "run_id": report["run_id"], "run_attempt": report["run_attempt"],
        }, ensure_ascii=False), flush=True)
        return 0

    json_path, md_path = write_outputs(report, args.output_dir)
    print("=== P2_B_DETECTOR_COMPETITION_V1_AR.md ===", flush=True)
    print(md_path.read_text(encoding="utf-8"), flush=True)
    print("=== P2_B_DETECTOR_COMPETITION_V1 summary JSON (aggregates only) ===", flush=True)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    print(json.dumps({"json": str(json_path), "report": str(md_path),
                      "loaded_detector_plugins": loaded_plugins,
                      "registered_arms": list(VARIANTS),
                      "source_integrity": report["source_integrity"]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
