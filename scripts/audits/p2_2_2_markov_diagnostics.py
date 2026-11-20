#!/usr/bin/env python3
"""Read-only audit of CHAOS P2.2 per-series Markov and bootstrap outputs.

This utility does not rerun, modify, or retune the frozen detector.
It deliberately reports cohort-scoped conditional alarm probabilities,
never a cross-domain false-positive rate.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


MODES = ("fast", "markov_cusum", "consensus")


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be within [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def finite_values(values: list[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if math.isfinite(number):
            result.append(number)
    return result


def distribution(values: list[float]) -> dict[str, float | int | None]:
    valid = finite_values(values)
    if not valid:
        return {
            "n": 0,
            "min": None,
            "q25": None,
            "median": None,
            "mean": None,
            "q75": None,
            "max": None,
        }
    return {
        "n": len(valid),
        "min": min(valid),
        "q25": quantile(valid, 0.25),
        "median": statistics.median(valid),
        "mean": statistics.fmean(valid),
        "q75": quantile(valid, 0.75),
        "max": max(valid),
    }


def summarize_cohort(series: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "series_total": len(series),
        "g1_passed": sum(bool(item.get("g1", {}).get("passed")) for item in series),
        "by_mode": {},
    }
    for mode in MODES:
        observed_all: list[float] = []
        observed_g1: list[float] = []
        observed_rates_g1: list[float] = []
        conditional_probabilities: list[float] = []
        expected_event_counts: list[float] = []
        rho_raw_g1: list[float] = []
        rho_used_g1: list[float] = []
        rho_clipped_g1: list[float] = []
        rho_cusum_used_g1: list[float] = []
        rho_g1_series_count = 0
        rho_cusum_missing_g1 = 0
        rho_clipped_inconsistent_g1 = 0
        correction_flag_g1: list[bool] = []
        cusum_correction_flag_g1: list[bool] = []
        cusum_correction_flag_missing_g1 = 0
        bootstrap_runs = 0
        bootstrap_errors = 0
        for item in series:
            passed_g1 = bool(item.get("g1", {}).get("passed"))
            detector = item.get("detector", {}).get(mode, {})
            alarms = detector.get("alarm_count")
            if isinstance(alarms, (int, float)) and not isinstance(alarms, bool):
                observed_all.append(float(alarms))
                if passed_g1:
                    observed_g1.append(float(alarms))
                    years = item.get("duration_years")
                    if isinstance(years, (int, float)) and years > 0:
                        observed_rates_g1.append(float(alarms) / float(years) * 10.0)

            diagnostics = detector.get("diagnostics", {})
            if passed_g1:
                flag = diagnostics.get("rho_bias_correction_enabled")
                if isinstance(flag, bool):
                    correction_flag_g1.append(flag)

                # rho values belong to Markov CUSUM only, never to Fast or Consensus.
                if mode == "markov_cusum":
                    rho_g1_series_count += 1
                    raw_value = diagnostics.get("rho_raw")
                    used_value = diagnostics.get("rho_used")
                    cusum_value = diagnostics.get("rho_cusum_used")
                    raw_valid = (
                        not isinstance(raw_value, bool)
                        and isinstance(raw_value, (int, float))
                        and math.isfinite(float(raw_value))
                    )
                    used_valid = (
                        not isinstance(used_value, bool)
                        and isinstance(used_value, (int, float))
                        and math.isfinite(float(used_value))
                    )
                    cusum_valid = (
                        not isinstance(cusum_value, bool)
                        and isinstance(cusum_value, (int, float))
                        and math.isfinite(float(cusum_value))
                    )
                    if raw_valid:
                        rho_raw_g1.append(float(raw_value))
                    if used_valid:
                        rho_used_g1.append(float(used_value))
                    if raw_valid and used_valid:
                        expected_clipped = min(0.88, max(0.0, float(raw_value)))
                        if math.isclose(
                            float(used_value), expected_clipped,
                            rel_tol=0.0, abs_tol=1e-6,
                        ):
                            rho_clipped_g1.append(float(used_value))
                        else:
                            rho_clipped_inconsistent_g1 += 1
                    if cusum_valid:
                        rho_cusum_used_g1.append(float(cusum_value))
                    else:
                        rho_cusum_missing_g1 += 1

                    # This is the structural correction switch used by the AR innovation.
                    structural_flag = diagnostics.get("rho_cusum_bias_correction_enabled")
                    if isinstance(structural_flag, bool):
                        cusum_correction_flag_g1.append(structural_flag)
                    else:
                        cusum_correction_flag_missing_g1 += 1

            bootstrap = item.get("bootstrap", {}).get("by_mode", {}).get(mode, {})
            runs = int(bootstrap.get("runs", 0) or 0)
            bootstrap_runs += runs
            bootstrap_errors += int(bootstrap.get("errors", 0) or 0)
            if runs > 0:
                conditional_probabilities.append(float(bootstrap.get("alarms", 0)) / runs)
                expected_event_counts.append(float(bootstrap.get("events", 0)) / runs)

        result["by_mode"][mode] = {
            "observed_alert_count_all_series": distribution(observed_all),
            "observed_alert_count_g1_passed_series": distribution(observed_g1),
            "observed_alerts_per_decade_g1_passed_series": distribution(observed_rates_g1),
            "all_series_with_one_or_more_observed_alerts": sum(v > 0 for v in observed_all),
            "g1_passed_series_with_one_or_more_observed_alerts": sum(v > 0 for v in observed_g1),
            "conditional_bootstrap_probability_of_one_or_more_alerts": distribution(
                conditional_probabilities
            ),
            "conditional_bootstrap_expected_event_count_per_replicate": distribution(
                expected_event_counts
            ),
            "rho_raw_g1_passed": distribution(rho_raw_g1),
            "rho_used_reported_by_manifest_g1_passed": distribution(rho_used_g1),
            "rho_clipped_g1_passed": distribution(rho_clipped_g1),
            "rho_cusum_used_g1_passed": distribution(rho_cusum_used_g1),
            "rho_diagnostic_completeness": {
                "g1_passed_markov_series": rho_g1_series_count,
                "rho_raw_available": len(rho_raw_g1),
                "rho_clipped_available_and_consistent_with_raw": len(rho_clipped_g1),
                "rho_clipped_inconsistent_with_raw": rho_clipped_inconsistent_g1,
                "rho_cusum_used_available": len(rho_cusum_used_g1),
                "rho_cusum_used_missing_or_invalid": rho_cusum_missing_g1,
                "rho_cusum_bias_correction_flag_true": cusum_correction_flag_g1.count(True),
                "rho_cusum_bias_correction_flag_false": cusum_correction_flag_g1.count(False),
                "rho_cusum_bias_correction_flag_missing_or_invalid": cusum_correction_flag_missing_g1,
            },
            "g1_passed_series_reporting_rho_bias_correction_enabled_false": correction_flag_g1.count(False),
            "g1_passed_series_reporting_rho_bias_correction_enabled_true": correction_flag_g1.count(True),
            "g1_passed_markov_series_reporting_rho_cusum_bias_correction_enabled_false": cusum_correction_flag_g1.count(False),
            "g1_passed_markov_series_reporting_rho_cusum_bias_correction_enabled_true": cusum_correction_flag_g1.count(True),
            "bootstrap_eligible_series": len(conditional_probabilities),
            "bootstrap_replicates_total": bootstrap_runs,
            "bootstrap_errors_total": bootstrap_errors,
        }
    return result


def build_report(manifest: dict[str, Any]) -> dict[str, Any]:
    series = manifest.get("series_results")
    if not isinstance(series, list):
        raise ValueError("manifest.series_results must be a list")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in series:
        if not isinstance(item, dict):
            raise ValueError("manifest contains a non-object series result")
        cohort = item.get("cohort")
        if not isinstance(cohort, str) or not cohort:
            raise ValueError("series result is missing a cohort name")
        grouped.setdefault(cohort, []).append(item)

    return {
        "audit_version": "1.1",
        "source_manifest_version": manifest.get("version"),
        "source_run_timestamp_utc": manifest.get("run_timestamp_utc"),
        "source_git_commit": manifest.get("git_commit"),
        "method_note": (
            "Conditional Stationary Bootstrap alarm probability within each cohort. "
            "Not a ground-truth false-positive rate. Cohorts are never pooled. "
            "Markov rho fields are read from historical detector diagnostics only; "
            "missing rho_cusum_used values remain missing and are never imputed. "
            "rho_clipped is accepted only when legacy rho_used agrees with clipping rho_raw "
            "to [0.0, 0.88]."
        ),
        "by_cohort": {
            cohort: summarize_cohort(items)
            for cohort, items in sorted(grouped.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("real_data_stress_pipeline/results/real_data_stress_manifest.json"),
        help="P2.2 manifest JSON path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path; stdout is used when omitted",
    )
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = build_report(manifest)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Wrote read-only audit: {args.output}")
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        parser.exit(2, f"AUDIT ERROR: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
