"""B-v3.2 calibration sweep with full pending lifecycle accounting."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break_v3_2.engine_b3_2 import (
    CalibratedSequentialBreakEngineB32,
)

N = 140
ONSET = 65
RHO_LEVELS = (0.3, 0.5, 0.7)
SHIFT_LEVELS = (2.0, 2.5, 3.0)
ANOMALY_THRESHOLDS = (4.5, 5.0, 5.5, 6.0)
RHO_MODES = ("raw", "small_sample_adjusted")
DEV_SEED_BASE = 4_000_000
HOLDOUT_SEED_BASE = 5_000_000
DEV_TRIALS = 300
HOLDOUT_TRIALS = 500
FALSE_ALARM_BUDGET_PCT = 5.0
RESOLUTION_HORIZON = 14
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b3_2_calibration.json"
)


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for dist in ("gauss", "t3"):
        for rho in RHO_LEVELS:
            cases.append({
                "name": f"{dist}_r{rho:.1f}_pure_null",
                "dist": dist, "rho": rho, "var_jump": False,
                "shift_sigma": 0.0,
            })
            cases.append({
                "name": f"{dist}_r{rho:.1f}_variance_jump",
                "dist": dist, "rho": rho, "var_jump": True,
                "shift_sigma": 0.0,
            })

    for dist in ("gauss", "t3"):
        for rho in RHO_LEVELS:
            for magnitude in SHIFT_LEVELS:
                for sign in (1.0, -1.0):
                    shift = sign * magnitude
                    cases.append({
                        "name": (
                            f"{dist}_r{rho:.1f}_"
                            f"{'pos' if sign > 0 else 'neg'}_{magnitude:.1f}s"
                        ),
                        "dist": dist, "rho": rho, "var_jump": False,
                        "shift_sigma": shift,
                    })
    return cases


CASES = build_cases()


def generate_series(
    rng: np.random.Generator, *, dist: str, rho: float,
    var_jump: bool, shift_sigma: float, n: int = N, onset: int = ONSET,
) -> np.ndarray:
    if not 0.0 <= rho < 1.0:
        raise ValueError("rho_must_be_in_[0,1)")
    if dist == "t3":
        eps = rng.standard_t(df=3, size=n) / np.sqrt(3.0)
    elif dist == "gauss":
        eps = rng.normal(0.0, 1.0, size=n)
    else:
        raise ValueError(f"unsupported_distribution:{dist}")
    if var_jump:
        eps[onset:] *= 2.0

    values = np.empty(n, dtype=float)
    values[0] = eps[0]
    innovation_scale = np.sqrt(1.0 - rho**2)
    for t in range(1, n):
        values[t] = rho * values[t - 1] + innovation_scale * eps[t]
    if shift_sigma:
        values[onset:] += shift_sigma
    return values


def wilson_interval(successes: int, trials: int) -> list[float]:
    if trials <= 0:
        raise ValueError("trials_must_be_positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes_must_be_between_zero_and_trials")
    z = 1.959963984540054
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = (
        z * math.sqrt(
            p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)
        ) / denom
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def classify_trial(
    result: dict[str, Any], *, shift_sigma: float, onset: int = ONSET,
) -> dict[str, Any]:
    breaks = list(result["structural_breaks"])
    transients = list(result["transient_anomalies"])
    unresolved = list(result["unresolved_alerts"])

    if shift_sigma == 0.0:
        correct_structural = []
        pre_structural = []
        wrong_structural = breaks
        delay = None
    else:
        expected = 1 if shift_sigma > 0 else -1
        post_structural = [
            b for b in breaks if int(b["detection_time"]) >= onset
        ]
        pre_structural = [
            b for b in breaks if int(b["detection_time"]) < onset
        ]
        correct_structural = [
            b for b in post_structural if int(b["direction"]) == expected
        ]
        # Do not mix pre-onset false alerts into the wrong-direction metric.
        wrong_structural = [
            b for b in post_structural if int(b["direction"]) != expected
        ]
        earliest = (
            min(correct_structural, key=lambda b: int(b["detection_time"]))
            if correct_structural else None
        )
        delay = (
            int(earliest["detection_time"]) - onset
            if earliest is not None else None
        )

    pre_transient = (
        [a for a in transients if int(a["time"]) < onset]
        if shift_sigma != 0.0 else []
    )
    pre_unresolved = (
        [a for a in unresolved if int(a["time"]) < onset]
        if shift_sigma != 0.0 else []
    )
    pre_combined = bool(pre_structural or pre_transient or pre_unresolved)

    return {
        "structural_sequence": bool(breaks),
        "transient_sequence": bool(transients),
        "unresolved_sequence": bool(unresolved),
        "combined_sequence": bool(breaks or transients or unresolved),
        "correct_structural_sequence": bool(correct_structural),
        "wrong_structural_sequence": bool(wrong_structural),
        "pre_onset_combined_sequence": pre_combined,
        "pre_onset_structural_sequence": bool(pre_structural),
        "pre_onset_transient_sequence": bool(pre_transient),
        "pre_onset_unresolved_sequence": bool(pre_unresolved),
        "detection_delay": delay,
        "structural_events": len(breaks),
        "transient_events": len(transients),
        "unresolved_events": len(unresolved),
        "pending_opened": int(result["pending_lifecycle"]["opened_count"]),
        "pending_resolved_structural": int(
            result["pending_lifecycle"]["resolved_structural_count"]
        ),
        "pending_resolved_transient": int(
            result["pending_lifecycle"]["resolved_transient_count"]
        ),
        "pending_unresolved": int(
            result["pending_lifecycle"]["unresolved_count"]
        ),
    }


def _rate(count: int, trials: int) -> dict[str, Any]:
    low, high = wilson_interval(count, trials)
    return {
        "sequences": count,
        "rate_pct": round(count / trials * 100.0, 2),
        "wilson95_pct": [round(low * 100.0, 2), round(high * 100.0, 2)],
    }


def evaluate_config(
    *, anomaly_z_thresh: float, rho_mode: str, seed_base: int,
    trials: int, print_cases: bool = True,
) -> dict[str, Any]:
    if rho_mode not in RHO_MODES:
        raise ValueError(f"unsupported_rho_mode:{rho_mode}")
    correction_enabled = rho_mode == "small_sample_adjusted"
    engine = CalibratedSequentialBreakEngineB32(
        anomaly_z_thresh=anomaly_z_thresh,
        resolution_horizon=RESOLUTION_HORIZON,
        rho_bias_correction=correction_enabled,
    )
    case_report: dict[str, Any] = {}
    lifecycle_balanced = True

    for case_index, case in enumerate(CASES):
        count = {
            "structural": 0, "transient": 0, "unresolved": 0,
            "combined": 0, "pre_combined": 0,
            "pre_structural": 0, "pre_transient": 0, "pre_unresolved": 0,
            "correct": 0, "wrong": 0, "delays": [],
            "events": {
                "structural": 0, "transient": 0, "unresolved": 0,
                "pending_opened": 0, "pending_resolved_structural": 0,
                "pending_resolved_transient": 0, "pending_unresolved": 0,
            },
        }
        shift = float(case["shift_sigma"])

        for trial in range(trials):
            seed = seed_base + case_index * 10_000 + trial
            series = generate_series(
                np.random.default_rng(seed),
                dist=case["dist"], rho=case["rho"],
                var_jump=case["var_jump"], shift_sigma=shift,
            )
            result = engine.analyze(series)
            metrics = classify_trial(result, shift_sigma=shift)

            for key in ("structural", "transient", "unresolved", "combined"):
                count[key] += int(metrics[f"{key}_sequence"])
            count["pre_combined"] += int(
                metrics["pre_onset_combined_sequence"]
            )
            count["pre_structural"] += int(
                metrics["pre_onset_structural_sequence"]
            )
            count["pre_transient"] += int(
                metrics["pre_onset_transient_sequence"]
            )
            count["pre_unresolved"] += int(
                metrics["pre_onset_unresolved_sequence"]
            )
            count["correct"] += int(
                metrics["correct_structural_sequence"]
            )
            count["wrong"] += int(metrics["wrong_structural_sequence"])
            if metrics["detection_delay"] is not None:
                count["delays"].append(metrics["detection_delay"])

            event_map = {
                "structural": "structural_events",
                "transient": "transient_events",
                "unresolved": "unresolved_events",
                "pending_opened": "pending_opened",
                "pending_resolved_structural": "pending_resolved_structural",
                "pending_resolved_transient": "pending_resolved_transient",
                "pending_unresolved": "pending_unresolved",
            }
            for aggregate_key, metric_key in event_map.items():
                count["events"][aggregate_key] += metrics[metric_key]

            if metrics["pending_opened"] != (
                metrics["pending_resolved_structural"]
                + metrics["pending_resolved_transient"]
                + metrics["pending_unresolved"]
            ):
                lifecycle_balanced = False

        kind = (
            "pure_null" if shift == 0.0 and not case["var_jump"]
            else "variance_jump" if shift == 0.0 and case["var_jump"]
            else "level_shift"
        )
        row = {
            "kind": kind,
            "distribution": case["dist"],
            "rho_target": case["rho"],
            "variance_jump": bool(case["var_jump"]),
            "shift_sigma": shift,
            "trials": trials,
            "structural_alert_rate": _rate(count["structural"], trials),
            "transient_alert_rate": _rate(count["transient"], trials),
            "unresolved_alert_rate": _rate(count["unresolved"], trials),
            "combined_any_alert_rate": _rate(count["combined"], trials),
            "pre_onset_combined_alert_rate": _rate(
                count["pre_combined"], trials
            ),
            "pre_onset_components": {
                "structural": _rate(count["pre_structural"], trials),
                "transient": _rate(count["pre_transient"], trials),
                "unresolved": _rate(count["pre_unresolved"], trials),
            },
            "correct_directional_structural_sensitivity": _rate(
                count["correct"], trials
            ),
            "wrong_direction_structural_rate": _rate(count["wrong"], trials),
            "median_correct_detection_delay": (
                round(float(statistics.median(count["delays"])), 2)
                if count["delays"] else None
            ),
            "event_totals": count["events"],
        }
        case_report[case["name"]] = row
        if print_cases:
            print(
                f"  {case['name']:31s} "
                f"Struct={row['structural_alert_rate']['rate_pct']:5.1f}% "
                f"Trans={row['transient_alert_rate']['rate_pct']:5.1f}% "
                f"Unres={row['unresolved_alert_rate']['rate_pct']:5.1f}% "
                f"Combined={row['combined_any_alert_rate']['rate_pct']:5.1f}%",
                flush=True,
            )

    no_level = [
        row for row in case_report.values()
        if row["kind"] in ("pure_null", "variance_jump")
    ]
    pure_null = [
        row for row in case_report.values()
        if row["kind"] == "pure_null"
    ]
    shifts = [
        row for row in case_report.values()
        if row["kind"] == "level_shift"
    ]
    worst_structural = max(
        row["structural_alert_rate"]["rate_pct"] for row in no_level
    )
    worst_combined_null = max(
        row["combined_any_alert_rate"]["rate_pct"] for row in pure_null
    )
    worst_pre_onset = max(
        row["pre_onset_combined_alert_rate"]["rate_pct"] for row in shifts
    )
    mean_sensitivity = round(
        float(statistics.mean(
            row["correct_directional_structural_sensitivity"]["rate_pct"]
            for row in shifts
        )),
        4,
    )

    return {
        "anomaly_z_thresh": anomaly_z_thresh,
        "rho_mode": rho_mode,
        "rho_bias_correction_enabled": correction_enabled,
        "resolution_horizon": RESOLUTION_HORIZON,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "worst_structural_fpr_no_level_shift_pct": round(
            worst_structural, 2
        ),
        "worst_combined_fpr_pure_null_pct": round(
            worst_combined_null, 2
        ),
        "worst_pre_onset_combined_fpr_level_shift_pct": round(
            worst_pre_onset, 2
        ),
        "mean_directional_sensitivity_level_shift_pct": mean_sensitivity,
        "lifecycle_accounting_complete": lifecycle_balanced,
        "dev_gate": {
            "structural_fpr_passed": worst_structural <= FALSE_ALARM_BUDGET_PCT,
            "combined_pure_null_fpr_passed": (
                worst_combined_null <= FALSE_ALARM_BUDGET_PCT
            ),
            "pre_onset_combined_fpr_passed": (
                worst_pre_onset <= FALSE_ALARM_BUDGET_PCT
            ),
            "lifecycle_accounting_passed": lifecycle_balanced,
        },
        "cases": case_report,
    }


def choose_dev_candidate(
    sweep: list[dict[str, Any]]
) -> dict[str, Any] | None:
    eligible = [
        row for row in sweep if all(row["dev_gate"].values())
    ]
    if not eligible:
        return None
    # Preserve sensitivity first; prefer adjusted rho on exact ties, then
    # the lower transient threshold.
    eligible.sort(
        key=lambda row: (
            -row["mean_directional_sensitivity_level_shift_pct"],
            0 if row["rho_mode"] == "small_sample_adjusted" else 1,
            row["anomaly_z_thresh"],
        )
    )
    return eligible[0]


def run_calibration(
    *, dev_trials: int = DEV_TRIALS,
    holdout_trials: int = HOLDOUT_TRIALS,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    if dev_trials < 100 or holdout_trials < 100:
        raise ValueError("dev_and_holdout_trials_must_each_be_at_least_100")

    report: dict[str, Any] = {
        "experiment": "sequential_break_engine_b3_2_calibrated",
        "candidate": "CalibratedSequentialBreakEngineB32",
        "design": {
            "series_length": N,
            "onset_index_zero_based": ONSET,
            "rho_levels": list(RHO_LEVELS),
            "shift_levels": list(SHIFT_LEVELS),
            "distributions": ["gauss", "t3"],
            "pure_null_cases": 6,
            "variance_jump_cases": 6,
            "level_shift_cases": 36,
            "total_cases": len(CASES),
            "anomaly_threshold_sweep": list(ANOMALY_THRESHOLDS),
            "rho_modes": list(RHO_MODES),
            "resolution_horizon": RESOLUTION_HORIZON,
            "rho_heuristic": (
                "min(0.90, rho_raw + (1 + 3*rho_raw)/quiet_end)"
            ),
            "rho_heuristic_note": (
                "small-sample experimental heuristic; not asserted to be "
                "a validated Kendall estimator correction"
            ),
            "dev_seed_base": DEV_SEED_BASE,
            "holdout_seed_base": HOLDOUT_SEED_BASE,
            "seed_scheme": "seed_base + case_index*10000 + trial",
            "false_alarm_budget_pct": FALSE_ALARM_BUDGET_PCT,
            "dev_gate": (
                "all no-level-shift structural FPR <=5%; all pure-null "
                "combined any-alert FPR <=5%; all level-shift pre-onset "
                "combined alert rates <=5%; lifecycle accounting complete"
            ),
        },
        "dev_trials_per_case": dev_trials,
        "holdout_trials_per_case": holdout_trials,
        "dev_sweep": [],
        "selected_candidate": None,
        "holdout": None,
        "holdout_status": "NOT_RUN",
        "final_gate_passed": False,
    }

    dev_start = time.perf_counter()
    for rho_mode in RHO_MODES:
        for threshold in ANOMALY_THRESHOLDS:
            print(
                f"\n=== DEV rho_mode={rho_mode} "
                f"anomaly_z_thresh={threshold:.1f} ===",
                flush=True,
            )
            row = evaluate_config(
                anomaly_z_thresh=threshold,
                rho_mode=rho_mode,
                seed_base=DEV_SEED_BASE,
                trials=dev_trials,
                print_cases=True,
            )
            report["dev_sweep"].append(row)
            print(
                "DEV SUMMARY "
                f"rho_mode={rho_mode} threshold={threshold:.1f} "
                f"structural={row['worst_structural_fpr_no_level_shift_pct']:.2f}% "
                f"pure_null_combined={row['worst_combined_fpr_pure_null_pct']:.2f}% "
                f"pre_onset_combined={row['worst_pre_onset_combined_fpr_level_shift_pct']:.2f}% "
                f"sensitivity={row['mean_directional_sensitivity_level_shift_pct']:.2f}% "
                f"gate={all(row['dev_gate'].values())}",
                flush=True,
            )

    report["dev_elapsed_seconds"] = round(
        time.perf_counter() - dev_start, 2
    )
    selected = choose_dev_candidate(report["dev_sweep"])
    if selected is None:
        report["holdout_status"] = (
            "NOT_RUN: no development candidate passed structural, combined, "
            "pre-onset, and lifecycle gates"
        )
    else:
        report["selected_candidate"] = {
            "anomaly_z_thresh": selected["anomaly_z_thresh"],
            "rho_mode": selected["rho_mode"],
            "rho_bias_correction_enabled": selected[
                "rho_bias_correction_enabled"
            ],
            "resolution_horizon": RESOLUTION_HORIZON,
            "dev_mean_sensitivity_pct": selected[
                "mean_directional_sensitivity_level_shift_pct"
            ],
        }
        print(
            "\n=== INDEPENDENT HOLDOUT "
            f"threshold={selected['anomaly_z_thresh']:.1f} "
            f"rho_mode={selected['rho_mode']} ===",
            flush=True,
        )
        holdout = evaluate_config(
            anomaly_z_thresh=float(selected["anomaly_z_thresh"]),
            rho_mode=str(selected["rho_mode"]),
            seed_base=HOLDOUT_SEED_BASE,
            trials=holdout_trials,
            print_cases=True,
        )
        report["holdout"] = holdout
        report["holdout_status"] = "COMPLETED"

        holdout_cases = holdout["cases"]
        no_level = [
            row for row in holdout_cases.values()
            if row["kind"] in ("pure_null", "variance_jump")
        ]
        pure_null = [
            row for row in holdout_cases.values()
            if row["kind"] == "pure_null"
        ]
        shifts = [
            row for row in holdout_cases.values()
            if row["kind"] == "level_shift"
        ]

        checks = {
            "structural_point": all(
                row["structural_alert_rate"]["rate_pct"]
                <= FALSE_ALARM_BUDGET_PCT for row in no_level
            ),
            "structural_wilson_upper95": all(
                row["structural_alert_rate"]["wilson95_pct"][1]
                <= FALSE_ALARM_BUDGET_PCT for row in no_level
            ),
            "combined_pure_null_point": all(
                row["combined_any_alert_rate"]["rate_pct"]
                <= FALSE_ALARM_BUDGET_PCT for row in pure_null
            ),
            "combined_pure_null_wilson_upper95": all(
                row["combined_any_alert_rate"]["wilson95_pct"][1]
                <= FALSE_ALARM_BUDGET_PCT for row in pure_null
            ),
            "pre_onset_combined_point": all(
                row["pre_onset_combined_alert_rate"]["rate_pct"]
                <= FALSE_ALARM_BUDGET_PCT for row in shifts
            ),
            "pre_onset_combined_wilson_upper95": all(
                row["pre_onset_combined_alert_rate"]["wilson95_pct"][1]
                <= FALSE_ALARM_BUDGET_PCT for row in shifts
            ),
            "lifecycle_accounting": holdout["lifecycle_accounting_complete"],
        }
        report["holdout_gates"] = checks
        report["final_gate_passed"] = all(checks.values())

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\n=== B-v3.2 FINAL ===")
    print(f"selected_candidate={report['selected_candidate']}")
    print(f"holdout_status={report['holdout_status']}")
    print(f"final_gate_passed={report['final_gate_passed']}")
    print(f"artifact={output}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trials", type=int, default=DEV_TRIALS)
    parser.add_argument("--holdout-trials", type=int, default=HOLDOUT_TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run_calibration(
        dev_trials=args.dev_trials,
        holdout_trials=args.holdout_trials,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
