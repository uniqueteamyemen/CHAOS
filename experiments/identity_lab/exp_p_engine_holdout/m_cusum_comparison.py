"""Compare Gemini's proposed Self-Normalized M-CUSUM with CHAOS C/E/F.

The Gemini M0 arm below reproduces the supplied equations and defaults exactly.
Ablations remove the self-normalizer and/or AR(1)-based k adjustment one at a
time. All arms use fresh holdout seeds not used in threshold sweep G or holdout H.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson
from experiments.identity_lab.exp_p_engine_holdout.robust_holdout import (
    MONTHS, QUIET_RANGE, ONSET, SCENARIOS, NULL_SCENARIOS,
    generate_residuals, residuals_to_stock_rows,
)

TRIALS = 500
SEED_BASE = 2_900_000
PSI_BOUND = 2.0
BASE_K = 0.50
H_SN = 7.5
MIN_RUN = 3
WINDOW = 25
V_FLOOR = 0.85

VARIANTS = (
    "Gemini-M0",
    "M-no-SN",
    "M-no-rho",
    "M-Huber-only",
    "C-default",
    "C-h24",
    "E-h24",
    "F-h16",
)
OUTPUT = (
    Path(__file__).resolve().parent / "results" / "gemini_mcusum_comparison.json"
)


def _median(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mcusum_empty_values")
    return float(statistics.median(values))


def _mad_sigma(values: Sequence[float]) -> float:
    med = _median(values)
    return 1.4826 * _median([abs(float(value) - med) for value in values])


def _pearson_rho(values: Sequence[float]) -> float:
    if len(values) < 3:
        return 0.0
    left, right = values[:-1], values[1:]
    left_mean, right_mean = statistics.mean(left), statistics.mean(right)
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 0 or right_ss <= 0:
        return 0.0
    numerator = sum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left, right)
    )
    return numerator / math.sqrt(left_ss * right_ss)


def run_mcusum(
    series: Sequence[float],
    *,
    quiet_end: int = 40,
    psi_bound: float = PSI_BOUND,
    base_k: float = BASE_K,
    h_sn: float = H_SN,
    min_run: int = MIN_RUN,
    window: int = WINDOW,
    v_floor: float = V_FLOOR,
    use_self_normalizer: bool = True,
    use_adaptive_k: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the submitted M-CUSUM equations, with flags used only for ablations.

    M0 (both flags True) retains the exact submitted update, run condition,
    window normalizer, and defaults. Time indexes are returned zero-based,
    matching the supplied code.
    """
    if quiet_end < 3 or quiet_end >= len(series):
        raise ValueError("mcusum_quiet_window_invalid")
    if psi_bound <= 0 or base_k < 0 or h_sn <= 0 or min_run < 1:
        raise ValueError("mcusum_parameter_invalid")
    if window < 2 or v_floor <= 0:
        raise ValueError("mcusum_normalizer_parameter_invalid")
    values = [float(value) for value in series]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("mcusum_series_nonfinite")

    quiet = values[:quiet_end]
    med = _median(quiet)
    mad = max(_mad_sigma(quiet), 1e-6)
    q_norm = [(value - med) / mad for value in quiet]
    rho_raw = _pearson_rho(q_norm)
    rho = max(0.0, min(0.9, rho_raw))
    lrv_inflation = math.sqrt((1.0 + rho) / max(1.0 - rho, 0.1))
    effective_k = (
        base_k * (0.65 + 0.35 * lrv_inflation)
        if use_adaptive_k else base_k
    )

    psi_scores = [
        max(-psi_bound, min(psi_bound, (value - med) / mad))
        for value in values
    ]
    history = list(psi_scores[:quiet_end])
    positive = 0.0
    negative = 0.0
    positive_run = 0
    negative_run = 0
    alerts: list[dict[str, Any]] = []
    v_values: list[float] = []

    for index in range(quiet_end, len(values)):
        x_t = psi_scores[index]
        history.append(x_t)
        win = history[-window:]
        center = _median(win)
        partial_sums = []
        running = 0.0
        for value in win:
            running += value - center
            partial_sums.append(running)

        if use_self_normalizer:
            variance_proxy = math.sqrt(
                statistics.mean(value * value for value in partial_sums) / len(win)
            )
            v_t = max(variance_proxy, v_floor)
        else:
            v_t = 1.0
        v_values.append(v_t)

        positive = max(0.0, positive + (x_t / v_t) - effective_k)
        negative = max(0.0, negative - (x_t / v_t) - effective_k)
        positive_run = positive_run + 1 if x_t > effective_k else 0
        negative_run = negative_run + 1 if -x_t > effective_k else 0

        if positive > h_sn and positive_run >= min_run:
            alerts.append({
                "time": index, "direction": 1, "stat": float(positive),
            })
        elif negative > h_sn and negative_run >= min_run:
            alerts.append({
                "time": index, "direction": -1, "stat": float(negative),
            })

    diagnostics = {
        "quiet_median": med,
        "quiet_mad_sigma": mad,
        "rho_raw": rho_raw,
        "rho_used": rho,
        "lrv_inflation_sqrt": lrv_inflation,
        "effective_k": effective_k,
        "psi_bound": psi_bound,
        "max_abs_psi": max(abs(value) for value in psi_scores),
        "v_median": statistics.median(v_values) if v_values else None,
        "v_min": min(v_values) if v_values else None,
        "v_max": max(v_values) if v_values else None,
        "self_normalizer_enabled": use_self_normalizer,
        "adaptive_k_enabled": use_adaptive_k,
        "alert_reset": False,
        "cooldown": False,
        "raw_alert_count": len(alerts),
    }
    return alerts, diagnostics


def _m_score(
    alerts: Sequence[Mapping[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    normalized = [
        {
            "time": int(alert["time"]) + 1,
            "sign": int(alert["direction"]),
        }
        for alert in alerts
    ]
    if scenario in NULL_SCENARIOS:
        false_hits = [hit for hit in normalized if hit["time"] > QUIET_RANGE[1]]
        return {
            "false_alarm": bool(false_hits),
            "false_events": len(false_hits),
            "pre_onset_false_alarm": False,
            "detected": False,
            "wrong_direction": False,
            "delay": None,
        }

    expected_sign = -1 if "negative" in scenario else 1
    pre = [
        hit for hit in normalized
        if QUIET_RANGE[1] < hit["time"] < ONSET
    ]
    post = [hit for hit in normalized if hit["time"] >= ONSET]
    correct = [hit for hit in post if hit["sign"] == expected_sign]
    wrong = [hit for hit in post if hit["sign"] != expected_sign]
    first = min((hit["time"] for hit in correct), default=None)
    return {
        "false_alarm": False,
        "false_events": 0,
        "pre_onset_false_alarm": bool(pre),
        "detected": first is not None,
        "wrong_direction": bool(wrong),
        "delay": first - ONSET if first is not None else None,
    }


def _baseline_score(
    hits: Sequence[Mapping[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    selected = [
        hit for hit in hits
        if str(hit.get("detector", "")).startswith("cusum_")
    ]
    if scenario in NULL_SCENARIOS:
        false_hits = [
            hit for hit in selected
            if int(hit["time"]) > QUIET_RANGE[1]
        ]
        return {
            "false_alarm": bool(false_hits),
            "false_events": len(false_hits),
            "pre_onset_false_alarm": False,
            "detected": False,
            "wrong_direction": False,
            "delay": None,
        }
    expected_sign = -1 if "negative" in scenario else 1
    pre = [
        hit for hit in selected
        if QUIET_RANGE[1] < int(hit["time"]) < ONSET
    ]
    post = [hit for hit in selected if int(hit["time"]) >= ONSET]
    correct = [hit for hit in post if int(hit["sign"]) == expected_sign]
    wrong = [hit for hit in post if int(hit["sign"]) != expected_sign]
    first = min((int(hit["time"]) for hit in correct), default=None)
    return {
        "false_alarm": False,
        "false_events": 0,
        "pre_onset_false_alarm": bool(pre),
        "detected": first is not None,
        "wrong_direction": bool(wrong),
        "delay": first - ONSET if first is not None else None,
    }


def _empty_counts() -> dict[str, Any]:
    return {
        "false_sequences": 0,
        "false_events": 0,
        "pre_onset_false_sequences": 0,
        "detected": 0,
        "wrong_direction_sequences": 0,
        "delays": [],
        "raw_alerts": 0,
        "rho": [],
        "effective_k": [],
        "v_median": [],
    }


def _add_trial(
    counts: dict[str, Any],
    score: Mapping[str, Any],
    *,
    raw_alerts: int = 0,
    diagnostics: Mapping[str, Any] | None = None,
) -> None:
    counts["false_sequences"] += int(bool(score["false_alarm"]))
    counts["false_events"] += int(score["false_events"])
    counts["pre_onset_false_sequences"] += int(bool(score["pre_onset_false_alarm"]))
    counts["detected"] += int(bool(score["detected"]))
    counts["wrong_direction_sequences"] += int(bool(score["wrong_direction"]))
    if score["delay"] is not None:
        counts["delays"].append(float(score["delay"]))
    counts["raw_alerts"] += int(raw_alerts)
    if diagnostics:
        counts["rho"].append(float(diagnostics["rho_used"]))
        counts["effective_k"].append(float(diagnostics["effective_k"]))
        if diagnostics["v_median"] is not None:
            counts["v_median"].append(float(diagnostics["v_median"]))


def _summarize_scenario(
    counts: Mapping[str, Any],
    *,
    scenario: str,
    trials: int,
) -> dict[str, Any]:
    if scenario in NULL_SCENARIOS:
        return {
            "false_alarm_rate": counts["false_sequences"] / trials,
            "false_alarm_wilson95": wilson(counts["false_sequences"], trials),
            "false_events_per_sequence": counts["false_events"] / trials,
            "raw_alerts_per_sequence": counts["raw_alerts"] / trials,
            "median_rho": statistics.median(counts["rho"]) if counts["rho"] else None,
            "median_effective_k": (
                statistics.median(counts["effective_k"]) if counts["effective_k"] else None
            ),
            "median_v": statistics.median(counts["v_median"]) if counts["v_median"] else None,
        }
    return {
        "pre_onset_false_alarm_rate": counts["pre_onset_false_sequences"] / trials,
        "pre_onset_false_wilson95": wilson(counts["pre_onset_false_sequences"], trials),
        "sensitivity": counts["detected"] / trials,
        "sensitivity_wilson95": wilson(counts["detected"], trials),
        "wrong_direction_trial_rate": counts["wrong_direction_sequences"] / trials,
        "mean_detection_delay": statistics.mean(counts["delays"]) if counts["delays"] else None,
        "median_detection_delay": statistics.median(counts["delays"]) if counts["delays"] else None,
        "raw_alerts_per_sequence": counts["raw_alerts"] / trials,
        "median_rho": statistics.median(counts["rho"]) if counts["rho"] else None,
        "median_effective_k": (
            statistics.median(counts["effective_k"]) if counts["effective_k"] else None
        ),
        "median_v": statistics.median(counts["v_median"]) if counts["v_median"] else None,
    }


def _aggregate_candidate(scenarios: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    null_rates = [scenarios[name]["false_alarm_rate"] for name in NULL_SCENARIOS]
    shift_rates = [scenarios[name]["sensitivity"] for name in SCENARIOS if name not in NULL_SCENARIOS]
    return {
        "worst_null_false_alarm_rate": max(null_rates),
        "minimum_shift_sensitivity": min(shift_rates),
        "mean_shift_sensitivity": statistics.mean(shift_rates),
        "pass_5pct_and_75pct_gates": (
            max(null_rates) <= 0.05 and min(shift_rates) >= 0.75
        ),
    }


def run_comparison(*, trials: int = TRIALS) -> dict[str, Any]:
    if trials < 100:
        raise ValueError("mcusum_trials_must_be_at_least_100")

    all_counts = {
        variant: {scenario: _empty_counts() for scenario in SCENARIOS}
        for variant in VARIANTS
    }
    diagnostic_samples = []

    for scenario_index, scenario in enumerate(SCENARIOS):
        for trial in range(trials):
            seed = SEED_BASE + scenario_index * 100_000 + trial
            residuals = generate_residuals(seed, scenario)

            configs = (
                ("Gemini-M0", True, True),
                ("M-no-SN", False, True),
                ("M-no-rho", True, False),
                ("M-Huber-only", False, False),
            )
            for name, use_sn, use_rho in configs:
                alerts, diag = run_mcusum(
                    residuals,
                    use_self_normalizer=use_sn,
                    use_adaptive_k=use_rho,
                )
                _add_trial(
                    all_counts[name][scenario],
                    _m_score(alerts, scenario),
                    raw_alerts=len(alerts),
                    diagnostics=diag,
                )
                if name == "Gemini-M0" and trial < 25:
                    diagnostic_samples.append({
                        "scenario": scenario,
                        "seed": seed,
                        "diagnostics": diag,
                    })

            rows = residuals_to_stock_rows(residuals)
            baseline_85 = run_candidates(
                "stock", rows, quiet_range=QUIET_RANGE,
                entity=f"mcusum-{scenario_index}",
                code_revision="p-engine-mcusum-comparison-v1",
                k_cusum=0.5, h_cusum=8.5,
            )
            baseline_24 = run_candidates(
                "stock", rows, quiet_range=QUIET_RANGE,
                entity=f"mcusum-{scenario_index}",
                code_revision="p-engine-mcusum-comparison-v1",
                k_cusum=0.5, h_cusum=24.0,
            )
            baseline_16 = run_candidates(
                "stock", rows, quiet_range=QUIET_RANGE,
                entity=f"mcusum-{scenario_index}",
                code_revision="p-engine-mcusum-comparison-v1",
                k_cusum=0.5, h_cusum=16.0,
            )
            baselines = (
                ("C-default", baseline_85["C"]["raw_hits"]),
                ("C-h24", baseline_24["C"]["raw_hits"]),
                ("E-h24", baseline_24["E"]["raw_hits"]),
                ("F-h16", baseline_16["F"]["raw_hits"]),
            )
            for name, hits in baselines:
                _add_trial(
                    all_counts[name][scenario],
                    _baseline_score(hits, scenario),
                    raw_alerts=sum(
                        1 for hit in hits
                        if str(hit.get("detector", "")).startswith("cusum_")
                    ),
                )

    scenario_reports = {}
    candidate_reports = {}
    for variant in VARIANTS:
        per_scenario = {
            scenario: _summarize_scenario(
                all_counts[variant][scenario],
                scenario=scenario,
                trials=trials,
            )
            for scenario in SCENARIOS
        }
        scenario_reports[variant] = per_scenario
        candidate_reports[variant] = _aggregate_candidate(per_scenario)

    return {
        "experiment": "gemini_self_normalized_mcusum_vs_chaos_cusum_v1",
        "candidate_specification": {
            "psi_bound": PSI_BOUND,
            "base_k": BASE_K,
            "h_sn": H_SN,
            "min_run": MIN_RUN,
            "window": WINDOW,
            "v_floor": V_FLOOR,
            "rho_clip": [0.0, 0.9],
            "effective_k": "base_k * (0.65 + 0.35 * sqrt((1+rho)/(1-rho)))",
            "m0_matches_submitted_algorithm": True,
            "alert_accumulator_reset": False,
            "alert_cooldown": False,
        },
        "ablation_definitions": {
            "M-no-SN": "Huber bounded score + adaptive rho-based k; v_t fixed at 1",
            "M-no-rho": "Huber bounded score + submitted self-normalizer; k fixed at base_k",
            "M-Huber-only": "Huber bounded score + ordinary CUSUM k/h; no SN and no rho adjustment",
        },
        "holdout": {
            "trials_per_scenario": trials,
            "seed_base": SEED_BASE,
            "scenario_names": list(SCENARIOS),
            "null_scenarios": list(NULL_SCENARIOS),
            "shift_scenarios": [name for name in SCENARIOS if name not in NULL_SCENARIOS],
            "ar1_phi": 0.60,
            "not_used_for_G_or_H": True,
        },
        "baselines": {
            "C-default": {"k": 0.5, "h": 8.5},
            "C-h24": {"k": 0.5, "h": 24.0},
            "E-h24": {"k": 0.5, "h": 24.0},
            "F-h16": {"k": 0.5, "h": 16.0},
        },
        "aggregate": candidate_reports,
        "scenarios": scenario_reports,
        "diagnostic_samples_first_25_per_scenario": diagnostic_samples,
        "decision_rule": (
            "A candidate passes only if each of the four independent null scenarios "
            "has sequence false-alarm rate <=5% and each of the six shifted scenarios "
            "has directional sensitivity >=75%. Wilson 95% intervals are reported."
        ),
        "limitations": [
            "The Gemini M0 arm preserves the submitted moving-window self-normalizer; it is not asserted to be the published Shao-Zhang self-normalized statistic.",
            "M0 preserves repeated alerts after threshold crossing because the submitted function has no reset/cooldown; raw alert multiplicity is reported separately.",
            "Synthetic regimes are controlled robustness tests, not production field labels.",
        ],
    }


def main() -> int:
    report = run_comparison()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "aggregate": report["aggregate"],
        "worst_null_by_scenario": {
            variant: {
                scenario: values["false_alarm_rate"]
                for scenario, values in report["scenarios"][variant].items()
                if scenario in NULL_SCENARIOS
            }
            for variant in VARIANTS
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
