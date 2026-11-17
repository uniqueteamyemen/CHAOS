#!/usr/bin/env python3
"""Isolated Markov behavior audit on World Bank Pink Sheet monthly returns."""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, os, statistics, sys, time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from real_data_stress_pipeline import run_pipeline as p2
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1, DEFAULT_MARKOV_THRESHOLD

SHORT_LENGTH = 100
BLOCK_MONTHS = 12
ROLLING_WINDOW = 40


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_mad(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    if x.size == 0 or not np.all(np.isfinite(x)):
        return 0.0
    return float(np.median(np.abs(x - np.median(x))))


def rolling_mad_volatility_normalize(values, quiet_end=40, window=ROLLING_WINDOW,
                                     scale_floor_ratio=1e-4):
    """Vectorized, causal, scale-only Rolling MAD; never removes local level."""
    from numpy.lib.stride_tricks import sliding_window_view

    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not np.all(np.isfinite(x)):
        raise ValueError("values_must_be_finite_one_dimensional")
    if quiet_end < 2 or window < 2 or x.size < quiet_end:
        raise ValueError("insufficient_values_for_rolling_mad_calibration")
    quiet_scale = 1.4826 * robust_mad(x[:quiet_end])
    floor = max(abs(quiet_scale) * scale_floor_ratio, 1e-12)

    # For t >= quiet_end, the legacy loop used x[t-window:t].
    # sliding_window_view aligns row 0 with exactly x[0:window], so row
    # (t-window) is the historical scale used for observation t.
    windows = sliding_window_view(x, window_shape=window)
    centers = np.median(windows, axis=1)
    rolling_scales = 1.4826 * np.median(
        np.abs(windows - centers[:, None]), axis=1
    )
    rolling_scales = np.maximum(rolling_scales, floor)

    result = np.empty_like(x)
    result[:quiet_end] = x[:quiet_end] / max(quiet_scale, floor)
    result[quiet_end:] = x[quiet_end:] / rolling_scales[:x.size - quiet_end]

    if not np.all(np.isfinite(result)):
        raise ArithmeticError("rolling_mad_produced_nonfinite_values")
    return result


def distribution(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "q25": None, "q75": None, "max": None}
    ordered = sorted(clean)
    def q(p):
        pos = (len(ordered)-1)*p
        lo, hi = math.floor(pos), math.ceil(pos)
        return ordered[lo] + (ordered[hi]-ordered[lo])*(pos-lo)
    return {"n": len(clean), "mean": statistics.fmean(clean),
            "median": statistics.median(clean), "q25": q(.25),
            "q75": q(.75), "max": max(clean)}


def summarize_records(records):
    grouped = defaultdict(list)
    for row in records:
        grouped[(row["category"], int(row["sample_length"]), row["input_variant"])].append(row)
    result = {}
    for (category, length, variant), rows in sorted(grouped.items()):
        alarm_runs = sum(bool(row["has_any_alarm"]) for row in rows)
        key = f"{category}|n={length}|{variant}"
        result[key] = {
            "category": category, "sample_length": length, "input_variant": variant,
            "replicates": len(rows), "replicates_with_one_or_more_alarms": alarm_runs,
            "conditional_null_alarm_probability": alarm_runs/len(rows) if rows else None,
            "alarm_count_distribution": distribution([r["alarm_count"] for r in rows]),
            "cusum_peak_distribution": distribution([r["cusum_peak"] for r in rows]),
            "cusum_updates_distribution": distribution([r["cusum_updates"] for r in rows]),
            "rho_cusum_used_distribution": distribution([r["rho_cusum_used"] for r in rows]),
        }
    return result


def analyze_one(sample, sample_length, replicate_id, series_id, category,
                variant, seed, raw_sample_sha256):
    output = BreakDetectorV1(mode="markov_cusum",
                             markov_threshold=DEFAULT_MARKOV_THRESHOLD).analyze(sample)
    events = output.get("structural_breaks", [])
    times = [int(e["detection_time"]) for e in events if e.get("detection_time") is not None]
    d = output.get("diagnostics", {})
    return {
        "series_id": series_id, "category": category, "sample_length": sample_length,
        "replicate_id": replicate_id, "seed": seed, "input_variant": variant,
        "threshold_h": DEFAULT_MARKOV_THRESHOLD,
        "raw_sample_sha256": raw_sample_sha256,
        "input_sha256": sha256_bytes(np.asarray(sample, dtype="<f8").tobytes()),
        "has_any_alarm": bool(events), "alarm_count": len(events),
        "first_alarm_index": min(times) if times else None,
        "cusum_peak": d.get("cusum_peak"), "cusum_updates": d.get("cusum_updates"),
        "cusum_directional_resets": d.get("cusum_directional_resets"),
        "rho_raw": d.get("rho_raw"), "rho_cusum_used": d.get("rho_cusum_used"),
        "rho_cusum_bias_correction_enabled": d.get("rho_cusum_bias_correction_enabled"),
    }


def _series_seed(series_id, sample_length, replicate_id):
    """Stable series-keyed seed; independent of task scheduling and worker ID."""
    token = f"CHAOS-P2.2.3|{series_id}|{sample_length}|{replicate_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big", signed=False)


def _run_series_bootstrap(payload):
    """Process one eligible series; all random streams are local and repeatable."""
    series_id, category, values_list, replicates = payload
    values = np.asarray(values_list, dtype=float)
    records = []
    for sample_length in (SHORT_LENGTH, int(values.size)):
        for replicate_id in range(replicates):
            seed = _series_seed(series_id, sample_length, replicate_id)
            rng = np.random.default_rng(seed)
            sample = p2.stationary_sample(values, rng, BLOCK_MONTHS)[:sample_length]
            sample_hash = sha256_bytes(np.asarray(sample, dtype="<f8").tobytes())
            normalized = rolling_mad_volatility_normalize(sample)
            records.append(analyze_one(
                sample, sample_length, replicate_id, series_id,
                category, "raw", seed, sample_hash
            ))
            records.append(analyze_one(
                normalized, sample_length, replicate_id, series_id,
                category, "rolling_mad_scale_only", seed, sample_hash
            ))
    return series_id, records


def run_bootstrap_jobs(payloads, workers):
    """Run series tasks sequentially or in separate processes with stable order."""
    if workers < 1:
        raise ValueError("workers_must_be_positive")
    if workers == 1 or len(payloads) <= 1:
        return [_run_series_bootstrap(payload) for payload in payloads]
    from concurrent.futures import ProcessPoolExecutor, as_completed

    completed = {}
    with ProcessPoolExecutor(max_workers=min(workers, len(payloads))) as executor:
        futures = {
            executor.submit(_run_series_bootstrap, payload): index
            for index, payload in enumerate(payloads)
        }
        for future in as_completed(futures):
            index = futures[future]
            completed[index] = future.result()
    return [completed[index] for index in range(len(payloads))]


def run_audit(replicates, max_series=None, workers=None):
    if replicates < 1:
        raise ValueError("replicates_must_be_positive")
    source_metadata = {"sources": [], "errors": [], "rejected": []}
    items = p2.pink(source_metadata)
    if not items:
        raise RuntimeError("World Bank Pink Sheet returned no eligible series")
    if max_series is not None:
        items = items[:max_series]

    records = []
    series_summaries = []
    eligible_payloads = []
    skipped = 0
    started = time.monotonic()

    for series_index, item in enumerate(items, 1):
        values = np.asarray(item["values"], dtype=float)
        series_id, category = str(item["id"]), p2.series_category(item)
        g1_result = p2.g1(values)
        observed = {}
        for variant, data in (
            ("raw", values),
            ("rolling_mad_scale_only", rolling_mad_volatility_normalize(values)),
        ):
            out = BreakDetectorV1(
                mode="markov_cusum",
                markov_threshold=DEFAULT_MARKOV_THRESHOLD
            ).analyze(data)
            events, diag = out.get("structural_breaks", []), out.get("diagnostics", {})
            observed[variant] = {
                "alarm_count": len(events), "cusum_peak": diag.get("cusum_peak"),
                "cusum_updates": diag.get("cusum_updates"),
                "rho_raw": diag.get("rho_raw"), "rho_cusum_used": diag.get("rho_cusum_used"),
            }
        series_summaries.append({
            "series_id": series_id, "name": item["name"], "category": category,
            "observations": int(values.size), "source_sha256": item.get("sha256"),
            "g1": g1_result, "observed": observed,
            "bootstrap_status": "PENDING" if g1_result.get("passed")
                else "SKIPPED_G1_SCREEN_FAILED",
        })
        if g1_result.get("passed"):
            eligible_payloads.append((series_id, category, values.tolist(), replicates))
        else:
            skipped += 1
        print(
            f"[{series_index}/{len(items)}] {series_id}: n={values.size}, "
            f"G1={'PASS' if g1_result.get('passed') else 'FAIL'}",
            flush=True,
        )

    worker_count = min(
        int(workers if workers is not None else (os.cpu_count() or 1)),
        max(1, len(eligible_payloads)),
    )
    worker_results = run_bootstrap_jobs(eligible_payloads, worker_count)
    records_by_series = {series_id: series_records for series_id, series_records in worker_results}
    for summary in series_summaries:
        series_id = summary["series_id"]
        if summary["bootstrap_status"] == "PENDING":
            series_records = records_by_series.get(series_id, [])
            records.extend(series_records)
            summary["bootstrap_status"] = (
                "COMPLETED" if series_records else "FAILED_NO_REPLICATE_RECORDS"
            )
            summary["bootstrap_replicate_records"] = len(series_records)

    elapsed = time.monotonic() - started
    engine_path = Path("structural_engine/isolated_break_detector_v1/engine_markov_cusum.py")
    result = {
        "audit_id": "CHAOS-P2.2.3-MARKOV-REAL-DATA-BEHAVIOR",
        "status": "completed",
        "repository_commit": os.getenv("GITHUB_SHA", "local-unresolved"),
        "method": "per-series Stationary Bootstrap; no cross-series pooling",
        "source": {
            "provider": "World Bank Pink Sheet",
            "retrieved_at_utc": source_metadata["sources"][0].get("retrieved_at_utc")
                if source_metadata["sources"] else None,
            "url": source_metadata["sources"][0].get("url")
                if source_metadata["sources"] else None,
            "sha256": source_metadata["sources"][0].get("sha256")
                if source_metadata["sources"] else None,
            "eligible_series_count": len(items),
        },
        "detector": {
            "name": "BreakDetectorV1", "mode": "markov_cusum",
            "threshold_h": DEFAULT_MARKOV_THRESHOLD, "frozen": True,
            "engine_file_sha256": sha256_file(engine_path),
        },
        "design": {
            "replicates_per_series_per_length": replicates,
            "sample_lengths": [SHORT_LENGTH, "full_source_length"],
            "stationary_bootstrap_mean_block_months": BLOCK_MONTHS,
            "rolling_mad_window": ROLLING_WINDOW,
            "rolling_mad_transform": "vectorized divide by 1.4826 * causal trailing MAD; no rolling centering",
            "normalization_causality": "initial quiet calibration for first 40; then preceding 40 only",
            "parallel_workers": worker_count,
            "parallelism_unit": "one complete series per process",
            "seed_derivation": "SHA256(series_id|sample_length|replicate_id|audit_version)",
            "g1_gate_required_for_stationary_resampling": True,
            "metric_name": "conditional_null_alarm_probability", "not_fpr": True,
            "skipped_g1_series": skipped,
        },
        "series": series_summaries,
        "bootstrap_summary_by_category_length_variant": summarize_records(records),
        "replicate_record_count": len(records),
        "elapsed_seconds": round(elapsed, 3),
        "limitations": [
            "Bootstrap probability is conditional, not a ground-truth false-positive rate.",
            "The 100-observation horizon is resampled from the full series, not the first 100 calendar points.",
            "Rolling MAD is an external input transform, not a detector modification.",
            "Lower alarm probability is not an improvement without injected-break power and delay tests.",
            "Multiprocessing tasks are series-isolated; deterministic seeds and input order make results invariant to worker scheduling.",
        ],
    }
    return result, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--max-series", type=int, default=None)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("artifacts/markov_real_data_behavior"))
    args = parser.parse_args()
    try:
        if args.workers < 1:
            raise ValueError("workers_must_be_positive")
        result, records = run_audit(args.replicates, args.max_series, args.workers)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir/"summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        with gzip.open(args.output_dir/"replicates.jsonl.gz", "wt",
                       encoding="utf-8", newline="\n") as handle:
            for row in records:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n")
        print(f"ELAPSED_SECONDS={result['elapsed_seconds']}", flush=True)
    except (OSError, ValueError, RuntimeError, ArithmeticError) as exc:
        parser.exit(2, f"MARKOV AUDIT ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
