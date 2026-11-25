"""P2-C economic cohort runner; P2-B code and published results remain frozen."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from p2_b_benchmark.engine import mad_sigma
from p2_b_benchmark.p2c_engine import P2C_VARIANTS, run_p2c_all, r_fpop_segment
from p2_b_benchmark.run import (
    NULL_BLOCK_LENGTH,
    SHIFT_SIGMA,
    _score_all,
    _series_manifest_sha256,
    _sorted_ids_sha256,
    stationary_sample,
)
from p2_b_benchmark.dataset import load_p2_economic_series

NULL_REPLICATES = 99
SHARD_COUNT = 4
EXPECTED_COUNTS = {
    "series": 509, "pink_sheet": 51, "gem": 458,
    "null_eligible": 359, "null_eligible_pink_sheet": 48,
    "null_eligible_gem": 311, "null_ineligible": 150,
}
P2C_DEV_BASE_SEED = 2026112501
P2C_HOLDOUT_BASE_SEED = 2026112502
P2C_DEV_REPLICATES = 49
P2C_HOLDOUT_REPLICATES = 50


def _p2c_seed_for(series_id: str, phase: str) -> int:
    """Independent deterministic seed stream per series and phase."""
    bases = {
        "development": P2C_DEV_BASE_SEED,
        "holdout": P2C_HOLDOUT_BASE_SEED,
    }
    if phase not in bases:
        raise ValueError(f"p2c_seed_phase_invalid:{phase}")
    payload = f"CHAOS:P2-C:{phase}:{bases[phase]}:{series_id}".encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)


def _empty_null_counts() -> dict[str, dict[str, int]]:
    return {
        arm: {"alarm_replicates": 0, "event_count": 0,
              "valid_replicates": 0, "abstained_replicates": 0}
        for arm in P2C_VARIANTS
    }


def _null_phase_summary(counts: dict[str, int], replicates: int) -> dict[str, Any]:
    valid = int(counts["valid_replicates"])
    return {
        **counts,
        "replicates_attempted": int(replicates),
        "conditional_alarm_probability": (
            counts["alarm_replicates"] / valid if valid else None
        ),
        "events_per_replicate": (
            counts["event_count"] / valid if valid else None
        ),
        "status": "OK" if valid else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
    }


def _one_series(item: dict[str, Any], null_replicates: int) -> dict[str, Any]:
    values = np.asarray(item["values"], dtype=float)
    quiet_sigma = mad_sigma(values[:40])
    zero_scale = not np.isfinite(quiet_sigma) or quiet_sigma <= 0
    observed = run_p2c_all(values, causal_audit=True)
    segmentation = r_fpop_segment(values)
    row: dict[str, Any] = {
        "id": str(item["id"]), "source": str(item["source"]),
        "n": int(values.size), "null_eligible": bool(item["bootstrap_eligible"]),
        "observed_status": "ABSTAIN" if zero_scale else "OK",
        "abstain_reason": "ZERO_QUIET_SCALE" if zero_scale else None,
        "observed": {}, "null": {}, "injected": {}, "causal": {},
        "r_fpop_segmentation": {
            "status": segmentation.get("status"),
            "abstain_reason": segmentation.get("abstain_reason"),
            "breakpoints": segmentation.get("breakpoints", []),
            "metadata": segmentation.get("metadata", {}),
        },
    }
    for arm, payload in observed.items():
        row["observed"][arm] = int(payload.get("event_count", len(payload.get("hits", []))))
        row["causal"][arm] = {
            "violations": int(payload.get("causal_audit_violations") or 0),
            "unverifiable": int(payload.get("causal_audit_unverifiable_prefixes") or 0),
            "details": list(payload.get("causal_audit_details") or []),
        }

    onset = max(52, int(values.size * 0.70))
    if onset >= values.size - 1 and not zero_scale:
        raise ValueError(f"p2c_injection_onset_out_of_range:{row['id']}:{onset}:{values.size}")
    if zero_scale:
        for arm in P2C_VARIANTS:
            for scenario in ("positive_3sigma", "negative_3sigma"):
                row["injected"].setdefault(arm, {})[scenario] = {
                    "status": "ABSTAIN", "abstain_reason": "ZERO_QUIET_SCALE",
                    "detected": None, "delay": None, "pre_onset_alert": None,
                    "wrong_direction": None, "missed": None,
                }
    else:
        for sign, scenario in ((1, "positive_3sigma"), (-1, "negative_3sigma")):
            injected = values.copy()
            injected[onset:] += sign * SHIFT_SIGMA * quiet_sigma
            results = run_p2c_all(injected, causal_audit=True)
            scored = _score_all(results, onset, sign, quiet_points=40)
            for arm, metrics in scored.items():
                row["injected"].setdefault(arm, {})[scenario] = {"status": "OK", **metrics}
                row["causal"][arm]["violations"] += int(
                    results[arm].get("causal_audit_violations") or 0
                )
                row["causal"][arm]["unverifiable"] += int(
                    results[arm].get("causal_audit_unverifiable_prefixes") or 0
                )
                row["causal"][arm]["details"].extend(
                    results[arm].get("causal_audit_details") or []
                )

    if row["null_eligible"]:
        rng = np.random.default_rng(_seed_for(row["id"]))
        counts = {
            arm: {"alarm_replicates": 0, "event_count": 0,
                  "valid_replicates": 0, "abstained_replicates": 0}
            for arm in P2C_VARIANTS
        }
        for _ in range(null_replicates):
            sample = stationary_sample(values, rng, NULL_BLOCK_LENGTH)
            null_results = run_p2c_all(sample, causal_audit=False)
            for arm, payload in null_results.items():
                if payload.get("status") == "ABSTAIN":
                    counts[arm]["abstained_replicates"] += 1
                    continue
                counts[arm]["valid_replicates"] += 1
                events = int(payload.get("event_count", len(payload.get("hits", []))))
                counts[arm]["alarm_replicates"] += int(events > 0)
                counts[arm]["event_count"] += events
        for arm, values_count in counts.items():
            valid = values_count["valid_replicates"]
            row["null"][arm] = {
                **values_count, "replicates_attempted": null_replicates,
                "conditional_alarm_probability": (
                    values_count["alarm_replicates"] / valid if valid else None
                ),
                "events_per_replicate": (
                    values_count["event_count"] / valid if valid else None
                ),
                "status": "OK" if valid else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
            }
    return row


def _aggregate(rows: list[dict[str, Any]], null_replicates: int) -> dict[str, Any]:
    output: dict[str, Any] = {
        "null": {}, "injected": {}, "observed": {}, "causal": {},
        "r_fpop_segmentation": {},
    }
    arms = list(P2C_VARIANTS)
    for arm in arms:
        for cohort in ("all", "pink_sheet", "gem"):
            selected = [r for r in rows if cohort == "all" or r["source"] == cohort]
            eligible = [r for r in selected if r["null_eligible"] and r["null"].get(arm)]
            if eligible:
                valid = sum(r["null"][arm]["valid_replicates"] for r in eligible)
                abstained = sum(r["null"][arm]["abstained_replicates"] for r in eligible)
                alarms = sum(r["null"][arm]["alarm_replicates"] for r in eligible)
                events = sum(r["null"][arm]["event_count"] for r in eligible)
                probabilities = [
                    r["null"][arm]["conditional_alarm_probability"]
                    for r in eligible
                    if r["null"][arm]["conditional_alarm_probability"] is not None
                ]
                total_valid_observations = sum(
                    int(r["n"]) * int(r["null"][arm]["valid_replicates"])
                    for r in eligible
                )
                output["null"].setdefault(arm, {})[cohort] = {
                    "series": len(eligible),
                    "replicates_attempted": len(eligible) * null_replicates,
                    "replicates_valid": valid,
                    "replicates_abstained": abstained,
                    "conditional_alarm_probability_pooled": alarms / valid if valid else None,
                    "events_per_replicate_pooled": events / valid if valid else None,
                    "events_per_1000_observations": (
                        events / total_valid_observations * 1000.0
                        if total_valid_observations else None
                    ),
                    "mean_series_alarm_probability": (
                        statistics.mean(probabilities) if probabilities else None
                    ),
                    "status": "OK" if valid else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
                    "interpretation": "conditional stationary-bootstrap diagnostic, not operational FPR",
                }
            for scenario in ("positive_3sigma", "negative_3sigma"):
                outcomes = [
                    r["injected"].get(arm, {}).get(scenario)
                    for r in selected
                    if r["injected"].get(arm, {}).get(scenario) is not None
                ]
                abstained = [o for o in outcomes if o.get("status") == "ABSTAIN"]
                valid_outcomes = [o for o in outcomes if o.get("status") != "ABSTAIN"]
                delays = [o["delay"] for o in valid_outcomes if o["delay"] is not None]
                if outcomes:
                    output["injected"].setdefault(arm, {}).setdefault(scenario, {})[cohort] = {
                        "series": len(outcomes), "eligible_series": len(valid_outcomes),
                        "abstained_zero_quiet_scale_series": len(abstained),
                        "sensitivity": (
                            sum(bool(o["detected"]) for o in valid_outcomes) / len(valid_outcomes)
                            if valid_outcomes else None
                        ),
                        "miss_rate": (
                            sum(bool(o["missed"]) for o in valid_outcomes) / len(valid_outcomes)
                            if valid_outcomes else None
                        ),
                        "pre_onset_false_alert_rate": (
                            sum(bool(o["pre_onset_alert"]) for o in valid_outcomes) / len(valid_outcomes)
                            if valid_outcomes else None
                        ),
                        "wrong_direction_rate": (
                            sum(bool(o["wrong_direction"]) for o in valid_outcomes) / len(valid_outcomes)
                            if valid_outcomes else None
                        ),
                        "median_detection_delay": statistics.median(delays) if delays else None,
                        "p90_detection_delay": (
                            float(np.quantile(delays, 0.90)) if delays else None
                        ),
                        "status": "OK" if valid_outcomes else "ABSTAIN_ALL_ZERO_QUIET_SCALE",
                    }
            observed_counts = [r["observed"].get(arm, 0) for r in selected]
            abstained_observed = sum(r["observed_status"] == "ABSTAIN" for r in selected)
            output["observed"].setdefault(arm, {})[cohort] = {
                "series": len(selected),
                "series_eligible": len(selected) - abstained_observed,
                "abstained_zero_quiet_scale_series": abstained_observed,
                "series_with_events": sum(c > 0 for c in observed_counts),
                "observed_event_count": sum(observed_counts),
                "interpretation": "descriptive only; historical labels are not adjudicated",
            }
            audits = [r["causal"].get(arm, {"violations": 0, "unverifiable": 0})
                      for r in selected]
            violations = sum(int(v["violations"]) for v in audits)
            unverifiable = sum(int(v["unverifiable"]) for v in audits)
            output["causal"].setdefault(arm, {})[cohort] = {
                "series": len(selected),
                "prefix_replay_or_mutation_violations": violations,
                "unverifiable_short_prefix_events": unverifiable,
                "status": (
                    "FAIL" if violations else
                    "PARTIAL_UNVERIFIABLE" if unverifiable else "PASS"
                ),
            }

    for cohort in ("all", "pink_sheet", "gem"):
        selected = [r for r in rows if cohort == "all" or r["source"] == cohort]
        segmentations = [r["r_fpop_segmentation"] for r in selected]
        breakpoints = [
            point for record in segmentations for point in record.get("breakpoints", [])
        ]
        lags = [
            int(p["detection_index"]) - int(p["estimated_change_index"])
            for p in breakpoints if p.get("detection_index") is not None
        ]
        output["r_fpop_segmentation"][cohort] = {
            "series": len(selected),
            "series_segmented": sum(record["status"] == "OK" for record in segmentations),
            "series_abstained": sum(record["status"] == "ABSTAIN" for record in segmentations),
            "breakpoint_count": len(breakpoints),
            "median_detection_minus_estimation": statistics.median(lags) if lags else None,
            "p90_detection_minus_estimation": (
                float(np.quantile(lags, 0.90)) if lags else None
            ),
            "interpretation": "retrospective segmentation diagnostic; not online warning performance",
        }
    return output


def _protocol(null_replicates: int) -> dict[str, Any]:
    return {
        "phase": "P2-C",
        "base_p2b_commit": "3c8eab34927640be2fb433efb77467cb9c1e31e2",
        "status_entrypoint_commit": "59a69220dce78a5ebd3eec6a6dcb8c5e54a752e5",
        "cohort": "509 economic series: 51 Pink Sheet + 458 GEM",
        "null_eligible": EXPECTED_COUNTS["null_eligible"],
        "quiet_window_observations": 40,
        "injected_break": f"persistent +/-{SHIFT_SIGMA} x quiet MAD at 70% of series",
        "null_method": f"stationary bootstrap mean block length {NULL_BLOCK_LENGTH}; conditional diagnostic only",
        "null_replicates_per_eligible_series": null_replicates,
        "online_arms": list(P2C_VARIANTS),
        "algorithm_versions": P2C_VARIANTS,
        "bartlett_role": "scale estimator within Post-Quiet Huber only; not detector",
        "r_fpop_role": "separate retrospective segmentation track",
        "no_lookahead": "online prefix replay at each hit/event plus future-suffix mutation",
        "sharding": "sorted series IDs, round-robin 4 shards; per-series seed independent of shard",
        "raw_values_in_artifacts": False,
    }


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


def _combine_shards(shards: list[dict[str, Any]], expected_series_count: int = 509) -> dict[str, Any]:
    if len(shards) != SHARD_COUNT:
        raise ValueError(f"p2c_shard_count_mismatch:{len(shards)}")
    if {int(s.get("shard_index", -1)) for s in shards} != set(range(SHARD_COUNT)):
        raise ValueError("p2c_shard_indices_missing_or_duplicate")
    first = shards[0]
    for key in ("run_id", "run_attempt", "expected_series_count",
                "null_replicates", "series_manifest_sha256", "sorted_ids_sha256",
                "sorted_ids", "protocol", "source_integrity"):
        if any(s.get(key) != first.get(key) for s in shards[1:]):
            raise ValueError(f"p2c_shard_{key}_disagreement")
    if first.get("schema") != "chaos-p2-c-shard-v1":
        raise ValueError("p2c_shard_schema_invalid")
    if int(first.get("expected_series_count", -1)) != expected_series_count:
        raise ValueError("p2c_expected_series_count_mismatch")
    sorted_ids = first.get("sorted_ids")
    if not isinstance(sorted_ids, list) or sorted_ids != sorted(set(sorted_ids)):
        raise ValueError("p2c_sorted_id_manifest_invalid")
    if _sorted_ids_sha256(sorted_ids) != first["sorted_ids_sha256"]:
        raise ValueError("p2c_sorted_ids_sha256_mismatch")

    rows: list[dict[str, Any]] = []
    ownership: dict[str, int] = {}
    for shard in shards:
        if shard.get("schema") != "chaos-p2-c-shard-v1":
            raise ValueError("p2c_shard_schema_invalid")
        index = int(shard["shard_index"])
        expected = [
            value for i, value in enumerate(sorted_ids) if i % SHARD_COUNT == index
        ]
        shard_rows = shard.get("series_results")
        if not isinstance(shard_rows, list) or len(shard_rows) != len(expected):
            raise ValueError(f"p2c_shard_rows_mismatch:{index}")
        _assert_metrics_only(shard_rows)
        ids = [str(r.get("id", "")) for r in shard_rows]
        if ids != expected:
            raise ValueError(f"p2c_shard_assignment_mismatch:{index}")
        for row in shard_rows:
            identifier = str(row["id"])
            if identifier in ownership:
                raise ValueError(f"p2c_duplicate_series:{identifier}")
            ownership[identifier] = index
            rows.append(row)
    rows.sort(key=lambda row: row["id"])
    if [r["id"] for r in rows] != sorted_ids:
        raise ValueError("p2c_series_coverage_mismatch")
    if _series_manifest_sha256(rows) != first["series_manifest_sha256"]:
        raise ValueError("p2c_series_manifest_mismatch")

    counts = {
        "series": len(rows),
        "pink_sheet": sum(r["source"] == "pink_sheet" for r in rows),
        "gem": sum(r["source"] == "gem" for r in rows),
        "null_eligible": sum(bool(r["null_eligible"]) for r in rows),
        "null_eligible_pink_sheet": sum(
            r["source"] == "pink_sheet" and bool(r["null_eligible"]) for r in rows
        ),
        "null_eligible_gem": sum(
            r["source"] == "gem" and bool(r["null_eligible"]) for r in rows
        ),
    }
    if expected_series_count == 509 and counts != EXPECTED_COUNTS:
        raise ValueError(f"p2c_cohort_counts_mismatch:{counts}")
    for key, value in counts.items():
        if first["source_integrity"].get(key) != value:
            raise ValueError(f"p2c_source_count_mismatch:{key}")
    return {
        "schema": "chaos-p2-c-competition-v1",
        "protocol": first["protocol"],
        "source_integrity": first["source_integrity"],
        "series_manifest_sha256": first["series_manifest_sha256"],
        "sorted_ids_sha256": first["sorted_ids_sha256"],
        "execution": {
            "mode": "four_matrix_shards", "run_id": first["run_id"],
            "run_attempt": first["run_attempt"],
            "shard_rows": {i: len(range(i, expected_series_count, SHARD_COUNT))
                           for i in range(SHARD_COUNT)},
        },
        "summary": _aggregate(rows, int(first["null_replicates"])),
        "series_results": rows,
        "limitations": [
            "Stationary-bootstrap probabilities are conditional diagnostics, not operational FPR.",
            "Historical Pink Sheet/GEM source vintages are unavailable; tests detector-time causality, not historic point-in-time source availability.",
            "Historical observed transitions have no adjudicated labels and are descriptive only.",
            "R-FPOP is retrospective segmentation; breakpoint estimate and earliest supported detection index are not online warning metrics.",
        ],
    }


def _write_outputs(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "P2_C_DETECTOR_COMPETITION_V1.json"
    md_path = out / "P2_C_DETECTOR_COMPETITION_V1_AR.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                         encoding="utf-8")
    lines = [
        "# P2-C — منافسة الكواشف المستقلة",
        "",
        f"- Cohort: {report['source_integrity']['series']} سلسلة "
        f"(Pink Sheet {report['source_integrity']['pink_sheet']}، GEM {report['source_integrity']['gem']}).",
        f"- Null eligible: {report['source_integrity']['null_eligible']}.",
        f"- Null replicates per eligible series: {report['protocol']['null_replicates_per_eligible_series']}.",
        "- Bartlett LRV مقياس معايرة داخل Post-Quiet Huber وليس كاشفاً.",
        "- R-FPOP يظهر في مسار segmentation رجعي مستقل ولا يدخل ترتيب online.",
        "",
        "## Conditional null diagnostics",
        "",
        "| Arm | Cohort | P(≥1 alarm) | Events/replicate | Abstained |",
        "|---|---|---:|---:|---:|",
    ]
    for arm in P2C_VARIANTS:
        for cohort in ("all", "pink_sheet", "gem"):
            r = report["summary"]["null"].get(arm, {}).get(cohort)
            if r:
                lines.append(
                    f"| {arm} | {cohort} | {r['conditional_alarm_probability_pooled']} | "
                    f"{r['events_per_replicate_pooled']} | {r['replicates_abstained']} |"
                )
    lines.extend(["", "## Injected-break performance", "",
                  "| Arm | Scenario | Cohort | Sensitivity | Miss | Pre-onset | Median delay |",
                  "|---|---|---|---:|---:|---:|---:|"])
    for arm in P2C_VARIANTS:
        for scenario in ("positive_3sigma", "negative_3sigma"):
            for cohort in ("all", "pink_sheet", "gem"):
                r = report["summary"]["injected"].get(arm, {}).get(scenario, {}).get(cohort)
                if r:
                    lines.append(
                        f"| {arm} | {scenario} | {cohort} | {r['sensitivity']} | "
                        f"{r['miss_rate']} | {r['pre_onset_false_alert_rate']} | "
                        f"{r['median_detection_delay']} |"
                    )
    lines.extend(["", "## Causal audit", "",
                  "| Arm | Prefix/mutation violations | Unverifiable |",
                  "|---|---:|---:|"])
    for arm in P2C_VARIANTS:
        r = report["summary"]["causal"][arm]["all"]
        lines.append(f"| {arm} | {r['prefix_replay_or_mutation_violations']} | "
                     f"{r['unverifiable_short_prefix_events']} |")
    lines.extend(["", "## R-FPOP — retrospective segmentation (not online ranked)", "",
                  "| Cohort | Series segmented | Abstained | Breakpoints | Median detection − estimate |",
                  "|---|---:|---:|---:|---:|"])
    for cohort, r in report["summary"]["r_fpop_segmentation"].items():
        lines.append(f"| {cohort} | {r['series_segmented']} | {r['series_abstained']} | "
                     f"{r['breakpoint_count']} | {r['median_detection_minus_estimation']} |")
    lines.extend(["", "## Interpretation limits", ""] +
                 [f"- {item}" for item in report["limitations"]])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _preflight_robseg_compile() -> None:
    """Compile the pinned C++ library in the parent before worker processes fork."""
    rng = np.random.default_rng(20261125)
    synthetic = rng.normal(0.0, 1.0, 120)
    synthetic[60:] += 3.0
    result = r_fpop_segment(synthetic)
    if result.get("status") != "OK":
        raise RuntimeError(f"R_FPOP_PREFLIGHT_FAILED:{result.get('abstain_reason')}")


def run_benchmark(prepared_zip: str, *, null_replicates: int = NULL_REPLICATES,
                  workers: int = 4, shard_index: int = 0,
                  run_id: str | None = None, run_attempt: int | None = None) -> dict[str, Any]:
    if not 1 <= null_replicates <= 999:
        raise ValueError("p2c_null_replicates_out_of_range")
    if workers < 1 or not 0 <= shard_index < SHARD_COUNT:
        raise ValueError("p2c_workers_or_shard_invalid")
    if not run_id or not isinstance(run_attempt, int) or run_attempt < 1:
        raise ValueError("p2c_shard_execution_requires_run_identity")

    # Prepare the shared .so before starting the four worker processes. This
    # avoids concurrent compiler writes to the same temporary library path.
    _preflight_robseg_compile()
    series, source_counts = load_p2_economic_series(prepared_zip)
    series = sorted(series, key=lambda item: str(item["id"]))
    ids = [str(item["id"]) for item in series]
    manifest = _series_manifest_sha256(series)
    selected = [item for i, item in enumerate(series) if i % SHARD_COUNT == shard_index]
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    actual_workers = max(1, min(workers, os.cpu_count() or 1))
    print(f"[P2-C shard {shard_index}/4] starting {len(selected)}/{len(series)} "
          f"series with {actual_workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=actual_workers) as pool:
        futures = {pool.submit(_one_series, item, null_replicates): item["id"]
                   for item in selected}
        for future in as_completed(futures):
            rows.append(future.result())
            if len(rows) % 10 == 0:
                print(f"[P2-C shard {shard_index}/4] processed {len(rows)}/{len(selected)} "
                      f"({time.perf_counter() - started:.1f}s)", flush=True)
    rows.sort(key=lambda r: r["id"])
    if len(rows) != len(selected):
        raise RuntimeError("p2c_shard_result_count_mismatch")
    print(f"[P2-C shard {shard_index}/4] complete {len(rows)} rows "
          f"({time.perf_counter() - started:.1f}s)", flush=True)

    return {
        "schema": "chaos-p2-c-shard-v1",
        "shard_index": shard_index, "shard_count": SHARD_COUNT,
        "run_id": str(run_id), "run_attempt": int(run_attempt),
        "expected_series_count": len(series), "expected_shard_rows": len(selected),
        "null_replicates": null_replicates,
        "series_manifest_sha256": manifest,
        "sorted_ids_sha256": _sorted_ids_sha256(ids), "sorted_ids": ids,
        "protocol": _protocol(null_replicates), "source_integrity": source_counts,
        "series_results": rows,
    }


def write_shard(shard: dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"p2c_shard_{shard['shard_index']}_of_4.json"
    path.write_text(json.dumps(shard, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    return path


def aggregate_shards(paths: list[str], output_dir: str | Path) -> dict[str, Any]:
    files: list[Path] = []
    for entry in paths:
        path = Path(entry)
        if path.is_dir():
            files.extend(path.glob("p2c_shard_*_of_4.json"))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"p2c_shard_path_not_found:{entry}")
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(set(files))]
    report = _combine_shards(docs)
    _write_outputs(report, output_dir)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="P2-C four-shard economic detector competition")
    parser.add_argument("--prepared-zip")
    parser.add_argument("--output-dir", default="artifacts/p2_c")
    parser.add_argument("--null-replicates", type=int, default=NULL_REPLICATES)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--run-attempt", type=int)
    parser.add_argument("--aggregate-shards", nargs="+")
    args = parser.parse_args()
    if args.aggregate_shards:
        report = aggregate_shards(args.aggregate_shards, args.output_dir)
        print(json.dumps({
            "schema": report["schema"],
            "series": report["source_integrity"]["series"],
            "summary": report["summary"],
        }, ensure_ascii=False, indent=2))
        return 0
    if not args.prepared_zip or args.shard_index is None:
        parser.error("--prepared-zip and --shard-index are required")
    shard = run_benchmark(
        args.prepared_zip, null_replicates=args.null_replicates,
        workers=args.workers, shard_index=args.shard_index,
        run_id=args.run_id, run_attempt=args.run_attempt,
    )
    path = write_shard(shard, args.output_dir)
    print(json.dumps({"shard": str(path), "rows": len(shard["series_results"]),
                      "shard_index": shard["shard_index"],
                      "manifest": shard["series_manifest_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
