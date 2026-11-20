#!/usr/bin/env python3
"""Paired injected-break power audit for raw vs Rolling-MAD Markov inputs.

This is an external diagnostic harness. It calls the frozen BreakDetectorV1
without modifying its implementation, constants, or thresholds.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from real_data_stress_pipeline import run_pipeline as p2
from scripts.audits.p2_2_3_markov_real_data_behavior import (
    rolling_mad_volatility_normalize,
    robust_mad,
    sha256_bytes,
    sha256_file,
)
from structural_engine.isolated_break_detector_v1 import (
    BreakDetectorV1,
    DEFAULT_MARKOV_THRESHOLD,
)

BLOCK_MONTHS = 12
QUIET_END = 40
SCENARIOS = ("mean_shift_2_5_initial_MAD", "volatility_jump_2x")


def stable_seed(series_id: str, sample_length: int, replicate_id: int) -> int:
    token = (
        f"CHAOS-P2.2.4-POWER|{series_id}|{sample_length}|{replicate_id}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def planned_break_index(sample_length: int) -> int:
    if sample_length < 87:
        raise ValueError("sample_length_below_full_resolution_gate")
    return max(52, int(math.floor(sample_length * 0.70)))


def inject_scenario(
    sample: np.ndarray | list[float],
    scenario: str,
    break_index: int,
) -> tuple[np.ndarray, float, str]:
    """Apply a predeclared change using only the pre-break quiet scale."""
    x = np.asarray(sample, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError("sample_must_be_finite_one_dimensional")
    if not QUIET_END <= break_index < x.size:
        raise ValueError("break_index_out_of_range")

    center = float(np.median(x[:QUIET_END]))
    initial_scale = 1.4826 * robust_mad(x[:QUIET_END])
    scale = max(initial_scale, 1e-12)
    changed = x.copy()

    if scenario == "mean_shift_2_5_initial_MAD":
        effect = 2.5 * scale
        changed[break_index:] += effect
        parameter = "additive_shift_2.5_x_initial_robust_sigma"
    elif scenario == "volatility_jump_2x":
        multiplier = 2.0
        changed[break_index:] = (
            center + multiplier * (changed[break_index:] - center)
        )
        effect = multiplier
        parameter = "post_break_deviation_multiplier_2.0_about_initial_median"
    else:
        raise ValueError(f"unsupported_injection_scenario:{scenario}")

    return changed, float(effect), parameter


def detector_power_record(
    values: np.ndarray,
    series_id: str,
    category: str,
    sample_length: int,
    replicate_id: int,
    seed: int,
    scenario: str,
    variant: str,
    break_index: int,
    parameter: str,
    effect: float,
    base_sample_sha256: str,
) -> dict[str, Any]:
    output = BreakDetectorV1(
        mode="markov_cusum",
        markov_threshold=DEFAULT_MARKOV_THRESHOLD,
    ).analyze(values)
    alarms = output.get("structural_breaks", [])
    alarm_times = sorted(
        int(event["detection_time"])
        for event in alarms
        if event.get("detection_time") is not None
    )
    pre = [index for index in alarm_times if index < break_index]
    post = [index for index in alarm_times if index >= break_index]
    first_post = post[0] if post else None
    diagnostics = output.get("diagnostics", {})

    return {
        "series_id": series_id,
        "category": category,
        "sample_length": sample_length,
        "replicate_id": replicate_id,
        "seed": seed,
        "scenario": scenario,
        "input_variant": variant,
        "threshold_h": DEFAULT_MARKOV_THRESHOLD,
        "break_index": break_index,
        "injection_parameter": parameter,
        "injection_effect": effect,
        "base_sample_sha256": base_sample_sha256,
        "injected_input_sha256": sha256_bytes(
            np.asarray(values, dtype="<f8").tobytes()
        ),
        "alarm_count": len(alarms),
        "alarm_times": alarm_times,
        "pre_break_alarm": bool(pre),
        "post_break_alarm": bool(post),
        "clean_detection": bool(post) and not bool(pre),
        "first_post_break_alarm": first_post,
        "detection_delay_steps": (
            first_post - break_index if first_post is not None else None
        ),
        "cusum_peak": diagnostics.get("cusum_peak"),
        "cusum_updates": diagnostics.get("cusum_updates"),
        **extract_markov_rho_diagnostics(diagnostics),
    }


def _run_series_power(payload: tuple[Any, ...]) -> tuple[str, list[dict[str, Any]]]:
    series_id, category, values_list, replicates = payload
    values = np.asarray(values_list, dtype=float)
    records: list[dict[str, Any]] = []

    for sample_length in (100, int(values.size)):
        break_index = planned_break_index(sample_length)
        for replicate_id in range(replicates):
            seed = stable_seed(series_id, sample_length, replicate_id)
            rng = np.random.default_rng(seed)
            base = p2.stationary_sample(values, rng, BLOCK_MONTHS)[:sample_length]
            base_hash = sha256_bytes(np.asarray(base, dtype="<f8").tobytes())

            for scenario in SCENARIOS:
                injected, effect, parameter = inject_scenario(
                    base, scenario, break_index
                )
                variants = (
                    ("raw", injected),
                    (
                        "rolling_mad_scale_only",
                        rolling_mad_volatility_normalize(injected),
                    ),
                )
                for variant, detector_input in variants:
                    records.append(
                        detector_power_record(
                            detector_input,
                            series_id,
                            category,
                            sample_length,
                            replicate_id,
                            seed,
                            scenario,
                            variant,
                            break_index,
                            parameter,
                            effect,
                            base_hash,
                        )
                    )

    return series_id, records


def run_power_jobs(
    payloads: list[tuple[Any, ...]],
    workers: int,
) -> list[tuple[str, list[dict[str, Any]]]]:
    if workers < 1:
        raise ValueError("workers_must_be_positive")
    if workers == 1 or len(payloads) <= 1:
        return [_run_series_power(payload) for payload in payloads]

    from concurrent.futures import ProcessPoolExecutor, as_completed

    completed: dict[int, tuple[str, list[dict[str, Any]]]] = {}
    with ProcessPoolExecutor(max_workers=min(workers, len(payloads))) as executor:
        futures = {
            executor.submit(_run_series_power, payload): index
            for index, payload in enumerate(payloads)
        }
        for future in as_completed(futures):
            completed[futures[future]] = future.result()
    return [completed[index] for index in range(len(payloads))]


def distribution(values: list[float | int]) -> dict[str, float | int | None]:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "q25": None, "q75": None}
    ordered = sorted(clean)

    def q(probability: float) -> float:
        position = (len(ordered) - 1) * probability
        lower, upper = math.floor(position), math.ceil(position)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "n": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "q25": q(0.25),
        "q75": q(0.75),
    }


def extract_markov_rho_diagnostics(diagnostics: dict[str, Any]) -> dict[str, float]:
    """Expose raw, clipped and structural-CUSUM rho without touching frozen V1."""
    source_fields = {
        "rho_raw": "rho_raw",
        "rho_clipped": "rho_used",
        "rho_cusum_used": "rho_cusum_used",
    }
    result: dict[str, float] = {}
    for output_name, source_name in source_fields.items():
        value = diagnostics.get(source_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ArithmeticError(
                f"markov_rho_diagnostic_missing_or_nonfinite:{source_name}"
            )
        result[output_name] = float(value)
    expected_clipped = min(0.88, max(0.0, result["rho_raw"]))
    if not math.isclose(
        result["rho_clipped"], expected_clipped, rel_tol=0.0, abs_tol=1e-6
    ):
        raise ArithmeticError("markov_rho_clipped_inconsistent_with_raw")
    return result


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    per_series_groups: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        per_series_groups[(
            row["series_id"], row["scenario"],
            int(row["sample_length"]), row["input_variant"],
        )].append(row)

    per_series: dict[str, Any] = {}
    category_groups: dict[tuple[str, int, str, str], list[dict[str, Any]]] = defaultdict(list)

    for (series_id, scenario, length, variant), rows in sorted(per_series_groups.items()):
        clean = sum(bool(row["clean_detection"]) for row in rows)
        post = sum(bool(row["post_break_alarm"]) for row in rows)
        pre = sum(bool(row["pre_break_alarm"]) for row in rows)
        delays = [
            int(row["detection_delay_steps"])
            for row in rows
            if row["clean_detection"] and row["detection_delay_steps"] is not None
        ]
        category = str(rows[0]["category"])
        key = f"{series_id}|{scenario}|n={length}|{variant}"
        value = {
            "series_id": series_id,
            "category": category,
            "scenario": scenario,
            "sample_length": length,
            "input_variant": variant,
            "replicates": len(rows),
            "clean_detection_probability": clean / len(rows) if rows else None,
            "post_break_alarm_probability": post / len(rows) if rows else None,
            "pre_break_alarm_probability": pre / len(rows) if rows else None,
            "detection_delay_steps_among_clean_detections": distribution(delays),
            "rho_raw_distribution": distribution([row.get("rho_raw") for row in rows]),
            "rho_clipped_distribution": distribution([row.get("rho_clipped") for row in rows]),
            "rho_cusum_used_distribution": distribution([row.get("rho_cusum_used") for row in rows]),
        }
        per_series[key] = value
        category_groups[(category, length, scenario, variant)].append(value)

    by_category: dict[str, Any] = {}
    for (category, length, scenario, variant), rows in sorted(category_groups.items()):
        key = f"{category}|n={length}|{scenario}|{variant}"
        by_category[key] = {
            "category": category,
            "sample_length": length,
            "scenario": scenario,
            "input_variant": variant,
            "aggregation_unit": "series",
            "series_count": len(rows),
            "clean_detection_probability_mean_across_series": statistics.fmean(
                row["clean_detection_probability"] for row in rows
            ),
            "clean_detection_probability_distribution_across_series": distribution(
                [row["clean_detection_probability"] for row in rows]
            ),
            "post_break_alarm_probability_mean_across_series": statistics.fmean(
                row["post_break_alarm_probability"] for row in rows
            ),
            "pre_break_alarm_probability_mean_across_series": statistics.fmean(
                row["pre_break_alarm_probability"] for row in rows
            ),
            "median_detection_delay_mean_across_series": statistics.fmean(
                row["detection_delay_steps_among_clean_detections"]["median"]
                for row in rows
                if row["detection_delay_steps_among_clean_detections"]["median"] is not None
            ) if any(
                row["detection_delay_steps_among_clean_detections"]["median"] is not None
                for row in rows
            ) else None,
            "rho_raw_per_series_median_distribution": distribution([
                row["rho_raw_distribution"]["median"] for row in rows
            ]),
            "rho_clipped_per_series_median_distribution": distribution([
                row["rho_clipped_distribution"]["median"] for row in rows
            ]),
            "rho_cusum_used_per_series_median_distribution": distribution([
                row["rho_cusum_used_distribution"]["median"] for row in rows
            ]),
        }

    return {
        "aggregation_note": (
            "Power and delay are summarized per series; category summaries give equal "
            "weight to each eligible series. A clean detection requires no pre-break "
            "alarm and at least one structural alarm at or after the injected change."
        ),
        "per_series": per_series,
        "by_category": by_category,
    }


def run_audit(
    replicates: int,
    max_series: int | None = None,
    workers: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if replicates < 1:
        raise ValueError("replicates_must_be_positive")
    metadata: dict[str, Any] = {"sources": [], "errors": [], "rejected": []}
    items = p2.pink(metadata)
    if not items:
        raise RuntimeError("World Bank Pink Sheet returned no eligible long monthly series")
    if max_series is not None:
        items = items[:max_series]

    eligible_payloads: list[tuple[Any, ...]] = []
    series_rows: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        values = np.asarray(item["values"], dtype=float)
        g1_result = p2.g1(values)
        series_id = str(item["id"])
        series_rows.append({
            "series_id": series_id,
            "name": item["name"],
            "category": p2.series_category(item),
            "observations": int(values.size),
            "source_sha256": item.get("sha256"),
            "g1": g1_result,
            "power_status": "PENDING" if g1_result.get("passed") else "SKIPPED_G1_SCREEN_FAILED",
        })
        if g1_result.get("passed"):
            eligible_payloads.append((
                series_id, p2.series_category(item), values.tolist(), replicates
            ))
        print(
            f"[{index}/{len(items)}] {series_id}: n={values.size}, "
            f"G1={'PASS' if g1_result.get('passed') else 'FAIL'}",
            flush=True,
        )

    worker_count = min(
        int(workers if workers is not None else (os.cpu_count() or 1)),
        max(1, len(eligible_payloads)),
    )
    started = time.monotonic()
    worker_results = run_power_jobs(eligible_payloads, worker_count)
    by_id = {series_id: rows for series_id, rows in worker_results}
    records = [row for _, rows in worker_results for row in rows]
    for item in series_rows:
        if item["power_status"] == "PENDING":
            rows = by_id.get(item["series_id"], [])
            item["power_status"] = "COMPLETED" if rows else "FAILED_NO_RECORDS"
            item["replicate_records"] = len(rows)

    engine_path = ROOT / "structural_engine/isolated_break_detector_v1/engine_markov_cusum.py"
    result = {
        "audit_id": "CHAOS-P2.2.4-MARKOV-INJECTED-BREAK-POWER",
        "status": "completed",
        "repository_commit": os.getenv("GITHUB_SHA", "local-unresolved"),
        "source": {
            "provider": "World Bank Pink Sheet",
            "retrieved_at_utc": metadata["sources"][0].get("retrieved_at_utc")
                if metadata["sources"] else None,
            "source_sha256": metadata["sources"][0].get("sha256")
                if metadata["sources"] else None,
            "eligible_series_count": len(items),
        },
        "detector": {
            "name": "BreakDetectorV1",
            "mode": "markov_cusum",
            "threshold_h": DEFAULT_MARKOV_THRESHOLD,
            "frozen": True,
            "engine_file_sha256": sha256_file(engine_path),
        },
        "design": {
            "replicates_per_series_per_length": replicates,
            "sample_lengths": [100, "full_source_length"],
            "break_position_fraction": 0.70,
            "break_index": "floor(0.70*n), bounded below by 52",
            "scenarios": {
                "mean_shift_2_5_initial_MAD": "Add 2.5 times initial quiet robust sigma from the break onward",
                "volatility_jump_2x": "Multiply post-break deviations from the initial quiet median by 2.0",
            },
            "comparison": ["raw", "rolling_mad_scale_only"],
            "seed_policy": "SHA256(series_id|sample_length|replicate_id|P2.2.4)",
            "parallel_workers": worker_count,
            "parallelism_unit": "series",
            "primary_metric": "clean_detection_probability",
            "clean_detection_definition": "At least one alarm at/after break and no alarm before break",
            "g1_gate_required_for_resampling": True,
            "rho_diagnostic_mapping": {
                "rho_raw": "detector diagnostics.rho_raw",
                "rho_clipped": (
                    "detector diagnostics.rho_used; legacy V1 value clipped from "
                    "rho_raw to [0.0, 0.88]"
                ),
                "rho_cusum_used": "detector diagnostics.rho_cusum_used",
                "detector_modified": False,
            },
            "not_operational_forecast": True,
        },
        "series": series_rows,
        "summary": summarize_records(records),
        "replicate_record_count": len(records),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "limitations": [
            "Injected changes are controlled stress cases, not claims about the frequency or size of real-world breaks.",
            "The null sample is stationary-block-resampled from each G1-screened source series.",
            "A clean detection metric is intentionally conservative and penalizes any pre-break alarm.",
            "These results assess the external input transform only; the frozen detector is unchanged.",
        ],
    }
    return result, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=100)
    parser.add_argument("--max-series", type=int, default=None)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/markov_injected_break_power"),
    )
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    try:
        result, records = run_audit(args.replicates, args.max_series, args.workers)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with gzip.open(
            args.output_dir / "replicates.jsonl.gz",
            "wt",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            for row in records:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"ELAPSED_SECONDS={result['elapsed_seconds']}", flush=True)
    except (OSError, ValueError, RuntimeError, ArithmeticError) as exc:
        parser.exit(2, f"INJECTED POWER AUDIT ERROR: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
