"""Robustness holdout for P-engine A/G/H/J/I under dependent and heavy-tailed noise.

Uses fresh seeds (3,000,000+) and identical input sequences across variants.
Historical EIA replay and the prior Gaussian benchmark are not repeated here.
"""
from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import (
    _variant_alerts,
    _variant_detection_hits,
    exact_mcnemar_pvalue,
    wilson,
)
from experiments.identity_lab.exp_p_engine.engine import DOMAINS
from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates


TRIALS = 300
MONTHS = 140
QUIET_RANGE = (1, 40)
ONSET = 65
BASE_SIGMA = 2.0
SEED_OFFSET = 3_000_000
VARIANTS = ("A", "G", "H", "J", "I")
REGIMES = (
    "ar1_phi_04",
    "ar1_phi_07",
    "student_t4",
    "laplace",
    "contaminated_5pct",
    "short_noise_burst",
)
CONDITIONS = ("null", "positive_3sigma", "negative_3sigma")


def draw_noise(
    rng: random.Random,
    regime: str,
    month: int,
    previous_ar1: float = 0.0,
) -> tuple[float, float]:
    """Return (noise, next AR state); all nominal quiet scales are 2.0."""
    if regime == "ar1_phi_04" or regime == "ar1_phi_07":
        phi = 0.4 if regime == "ar1_phi_04" else 0.7
        innovation_sigma = BASE_SIGMA * math.sqrt(1.0 - phi * phi)
        value = phi * previous_ar1 + rng.gauss(0.0, innovation_sigma)
        return value, value

    if regime == "student_t4":
        # Student-t(4) has variance 2; multiplying by sqrt(2) gives SD 2.
        chi_square_4 = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(4))
        t4 = rng.gauss(0.0, 1.0) / math.sqrt(chi_square_4 / 4.0)
        return t4 * math.sqrt(2.0), 0.0

    if regime == "laplace":
        # Laplace scale b=sqrt(2) gives variance 2*b^2=4.
        sign = -1.0 if rng.random() < 0.5 else 1.0
        return sign * rng.expovariate(1.0 / math.sqrt(2.0)), 0.0

    if regime == "contaminated_5pct":
        value = rng.gauss(0.0, BASE_SIGMA)
        if rng.random() < 0.05:
            value += (-1.0 if rng.random() < 0.5 else 1.0) * 10.0
        return value, 0.0

    if regime == "short_noise_burst":
        sigma = 8.0 if 48 <= month <= 59 else BASE_SIGMA
        return rng.gauss(0.0, sigma), 0.0

    raise ValueError(f"unknown_noise_regime:{regime}")


def make_robust_rows(seed: int, regime: str, condition: str):
    """Build one exact stock-identity sequence with known residual truth."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown_condition:{condition}")
    shift_sign = (
        1 if condition == "positive_3sigma"
        else -1 if condition == "negative_3sigma"
        else 0
    )
    rng = random.Random(seed)
    previous_ar1 = 0.0
    balance = 2000.0
    columns = DOMAINS["stock"]
    rows: list[dict[str, Any]] = []
    residuals: list[float] = []

    for month in range(1, MONTHS + 1):
        noise, previous_ar1 = draw_noise(rng, regime, month, previous_ar1)
        shift = shift_sign * 3.0 * BASE_SIGMA if month >= ONSET else 0.0
        residual = noise + shift
        expected_closing = balance + 400.0 - 400.0 - 5.0
        closing = expected_closing - residual
        rows.append({
            columns["opening"]: balance,
            columns["inflow"]: 400.0,
            columns["outflow"]: 400.0,
            columns["other"]: 5.0,
            columns["closing"]: closing,
            "month": month,
        })
        residuals.append(residual)
        balance = closing

    return rows, residuals


def _score_variant(result, variant: str, residuals: list[float], condition: str):
    alerts = _variant_alerts(result, variant)
    detection_hits = _variant_detection_hits(result, variant, residuals)
    sign = 1 if condition == "positive_3sigma" else (
        -1 if condition == "negative_3sigma" else 0
    )
    post_calibration = [
        alert for alert in alerts
        if int(alert["time"]) > QUIET_RANGE[1]
    ]
    pre_onset = [
        alert for alert in alerts
        if QUIET_RANGE[1] < int(alert["time"]) < ONSET
    ]
    if sign == 0:
        return {
            "false_alert": bool(post_calibration),
            "false_event_count": len(post_calibration),
        }

    correct = [
        hit for hit in detection_hits
        if int(hit["time"]) >= ONSET and int(hit["sign"]) == sign
    ]
    wrong = [
        hit for hit in detection_hits
        if int(hit["time"]) >= ONSET and int(hit["sign"]) != sign
    ]
    first_detection = min((int(hit["time"]) for hit in correct), default=None)
    return {
        "pre_onset_false_alert": bool(pre_onset),
        "pre_onset_false_event_count": len(pre_onset),
        "detected": first_detection is not None,
        "wrong_direction": bool(wrong),
        "delay": first_detection - ONSET if first_detection is not None else None,
    }


def run_robustness_benchmark() -> dict[str, Any]:
    report: dict[str, Any] = {
        "protocol": {
            "trials_per_regime_condition": TRIALS,
            "months_per_sequence": MONTHS,
            "seed_offset": SEED_OFFSET,
            "fresh_seed_range": True,
            "quiet_range": list(QUIET_RANGE),
            "onset": ONSET,
            "nominal_quiet_sigma": BASE_SIGMA,
            "variants": {
                "A": "unchanged production engine",
                "G": "adaptive 13-run P1; unbounded two-sided CUSUM reset during transitions; h=12.5",
                "H": "adaptive 13-run P1; unbounded two-sided CUSUM held during transitions; h=12.5",
                "J": "same as H; h=14.5",
                "I": "same as H; h=16.5",
            },
            "noise_regimes": {
                "ar1_phi_04": "Gaussian AR(1), phi=0.4, stationary SD=2",
                "ar1_phi_07": "Gaussian AR(1), phi=0.7, stationary SD=2",
                "student_t4": "Student-t(4), scaled to SD=2",
                "laplace": "Laplace, SD=2",
                "contaminated_5pct": "Gaussian SD=2 plus 5% signed 10-unit additive shocks",
                "short_noise_burst": "Gaussian SD=2 with a 12-period SD=8 burst at months 48-59",
            },
            "conditions": list(CONDITIONS),
            "paired_test": "exact two-sided McNemar versus A; exploratory unadjusted p-values",
            "scoring": "fused candidate detection is based on post-onset evidence timestamps, not event start",
        },
        "results": {},
    }

    for regime_index, regime in enumerate(REGIMES):
        report["results"][regime] = {}
        for condition_index, condition in enumerate(CONDITIONS):
            counts = {
                variant: {
                    "false_trials": 0,
                    "false_events": 0,
                    "pre_onset_false_trials": 0,
                    "pre_onset_false_events": 0,
                    "detected": 0,
                    "wrong_direction": 0,
                    "delays": [],
                }
                for variant in VARIANTS
            }
            paired = {
                variant: {
                    "candidate_only_false": 0,
                    "baseline_only_false": 0,
                    "candidate_only_detected": 0,
                    "baseline_only_detected": 0,
                }
                for variant in VARIANTS if variant != "A"
            }

            for trial in range(TRIALS):
                seed = SEED_OFFSET + regime_index * 100_000 + condition_index * 10_000 + trial
                rows, residuals = make_robust_rows(seed, regime, condition)
                result = run_candidates(
                    "stock",
                    rows,
                    quiet_range=QUIET_RANGE,
                    entity=f"robust-{regime_index}-{condition_index}-{trial}",
                    code_revision="p-engine-robustness-v1",
                )
                scores = {
                    variant: _score_variant(result, variant, residuals, condition)
                    for variant in VARIANTS
                }
                if condition == "null":
                    baseline_false = scores["A"]["false_alert"]
                    for variant in VARIANTS:
                        score = scores[variant]
                        counts[variant]["false_trials"] += int(score["false_alert"])
                        counts[variant]["false_events"] += score["false_event_count"]
                        if variant != "A":
                            if score["false_alert"] and not baseline_false:
                                paired[variant]["candidate_only_false"] += 1
                            elif baseline_false and not score["false_alert"]:
                                paired[variant]["baseline_only_false"] += 1
                else:
                    baseline_false = scores["A"]["pre_onset_false_alert"]
                    baseline_detected = scores["A"]["detected"]
                    for variant in VARIANTS:
                        score = scores[variant]
                        counts[variant]["pre_onset_false_trials"] += int(
                            score["pre_onset_false_alert"]
                        )
                        counts[variant]["pre_onset_false_events"] += score[
                            "pre_onset_false_event_count"
                        ]
                        if score["detected"]:
                            counts[variant]["detected"] += 1
                            counts[variant]["delays"].append(score["delay"])
                        counts[variant]["wrong_direction"] += int(score["wrong_direction"])
                        if variant != "A":
                            if score["pre_onset_false_alert"] and not baseline_false:
                                paired[variant]["candidate_only_false"] += 1
                            elif baseline_false and not score["pre_onset_false_alert"]:
                                paired[variant]["baseline_only_false"] += 1
                            if score["detected"] and not baseline_detected:
                                paired[variant]["candidate_only_detected"] += 1
                            elif baseline_detected and not score["detected"]:
                                paired[variant]["baseline_only_detected"] += 1

            scenario_result: dict[str, Any] = {"trials": TRIALS, "variants": {}}
            for variant in VARIANTS:
                c = counts[variant]
                if condition == "null":
                    scenario_result["variants"][variant] = {
                        "false_alert_rate": round(c["false_trials"] / TRIALS, 4),
                        "false_alert_rate_95pct_wilson_ci": wilson(c["false_trials"], TRIALS),
                        "false_events_per_sequence": round(c["false_events"] / TRIALS, 4),
                        "false_alert_trials": c["false_trials"],
                    }
                else:
                    scenario_result["variants"][variant] = {
                        "pre_onset_false_alert_rate": round(
                            c["pre_onset_false_trials"] / TRIALS, 4
                        ),
                        "pre_onset_false_alert_rate_95pct_wilson_ci": wilson(
                            c["pre_onset_false_trials"], TRIALS
                        ),
                        "sensitivity": round(c["detected"] / TRIALS, 4),
                        "sensitivity_95pct_wilson_ci": wilson(c["detected"], TRIALS),
                        "wrong_direction_rate": round(c["wrong_direction"] / TRIALS, 4),
                        "median_detection_delay": (
                            statistics.median(c["delays"]) if c["delays"] else None
                        ),
                        "missed_trials": TRIALS - c["detected"],
                    }

            for variant in VARIANTS:
                if variant == "A":
                    continue
                p = paired[variant]
                p["false_alert_exact_mcnemar_p"] = exact_mcnemar_pvalue(
                    p["candidate_only_false"], p["baseline_only_false"]
                )
                if condition != "null":
                    p["detection_exact_mcnemar_p"] = exact_mcnemar_pvalue(
                        p["candidate_only_detected"], p["baseline_only_detected"]
                    )
                scenario_result["variants"][variant]["paired_vs_A"] = p

            report["results"][regime][condition] = scenario_result

    return report


def main() -> int:
    report = run_robustness_benchmark()
    output = (
        Path(__file__).resolve().parent
        / "results"
        / "parallel_fusion_robustness_300_seed.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    compact = {
        regime: {
            condition: {
                variant: values.get("sensitivity", values.get("false_alert_rate"))
                for variant, values in result["variants"].items()
            }
            for condition, result in conditions.items()
        }
        for regime, conditions in report["results"].items()
    }
    print(json.dumps({"output": str(output), "summary": compact}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
