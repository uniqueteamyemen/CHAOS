"""Paired 500-seed A/B/C experiment for P-engine false alarms and break sensitivity."""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from experiments.identity_lab.exp_p_engine.parallel_fusion import run_candidates


TRIALS = 500
MONTHS = 140
QUIET_RANGE = (1, 40)
ONSET = 65


def scenario_spec(name: str, month: int) -> tuple[float, float, int]:
    sign = 0
    shift = 0.0
    if name == "stable_null":
        noise = 2.0
    elif name == "rising_noise_null":
        noise = 2.0 + 6.0 * month / MONTHS
    elif name == "elevated_noise_null":
        noise = 2.0 if month < ONSET else 8.0
    elif name in {"positive_step_3sigma", "negative_step_3sigma",
                  "positive_step_6sigma", "negative_step_6sigma"}:
        sign = -1 if name.startswith("negative") else 1
        magnitude = 12.0 if "6sigma" in name else 6.0
        shift = sign * magnitude if month >= ONSET else 0.0
        noise = 2.0
    elif name in {"transition_positive_3sigma", "transition_negative_3sigma"}:
        sign = -1 if "negative" in name else 1
        shift = sign * 6.0 if month >= ONSET else 0.0
        ramp = min(1.0, max(0.0, (month - 50) / 50))
        noise = 2.0 + 6.0 * ramp
    elif name in {"gradual_positive", "gradual_negative"}:
        sign = -1 if "negative" in name else 1
        shift = sign * max(0, month - ONSET) * 0.12
        noise = 2.0
    else:
        raise ValueError(f"unknown_scenario:{name}")
    return noise, shift, sign


def make_rows(seed: int, scenario: str):
    rng = random.Random(seed)
    balance = 2000.0
    rows, expected_residuals = [], []
    for month in range(1, MONTHS + 1):
        noise, shift, sign = scenario_spec(scenario, month)
        residual = shift + rng.gauss(0.0, noise)
        expected_closing = balance + 400.0 - 400.0 - 5.0
        closing = expected_closing - residual
        rows.append({
            "opening": balance, "inflow": 400.0, "outflow": 400.0,
            "other": 5.0, "closing": closing, "month": month,
        })
        expected_residuals.append(residual)
        balance = closing
    return rows, expected_residuals


def wilson(successes: int, trials: int, z: float = 1.959963984540054):
    if trials == 0:
        return [None, None]
    p = successes / trials
    denom = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5) / denom
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _variant_alerts(result, variant):
    if variant == "A":
        return result["A"]["alerts"]
    return result[variant]["events"]


def run_benchmark():
    scenarios = [
        "stable_null", "rising_noise_null", "elevated_noise_null",
        "positive_step_3sigma", "negative_step_3sigma",
        "positive_step_6sigma", "negative_step_6sigma",
        "transition_positive_3sigma", "transition_negative_3sigma",
        "gradual_positive", "gradual_negative",
    ]
    report = {
        "protocol": {
            "trials_per_condition": TRIALS,
            "months_per_sequence": MONTHS,
            "quiet_calibration_range": list(QUIET_RANGE),
            "evaluation_onset": ONSET,
            "thresholds_fixed_before_trials": True,
            "evaluation_seeds_disjoint_by_scenario": True,
            "scenarios": scenarios,
            "variants": {
                "A": "unchanged engine.run production path",
                "B": "two-sided CUSUM; preserve state during variance transitions; unbounded scale",
                "C": "two-sided CUSUM; capped scale; damp updates during variance transitions",
            },
        },
        "results": {},
    }

    for scenario_index, scenario in enumerate(scenarios):
        sign = -1 if "negative" in scenario else (1 if "positive" in scenario else 0)
        has_break = sign != 0
        null_trials = {"A": 0, "B": 0, "C": 0}
        detected = {"A": 0, "B": 0, "C": 0}
        wrong_direction = {"A": 0, "B": 0, "C": 0}
        delays = {"A": [], "B": [], "C": []}

        for trial in range(TRIALS):
            seed = 100_000 + scenario_index * 10_000 + trial
            rows, residual_values = make_rows(seed, scenario)
            result = run_candidates(
                "stock", rows, quiet_range=QUIET_RANGE,
                entity=f"synthetic-{scenario_index}",
                code_revision="p-engine-parallel-fusion-v1",
            )
            for variant in ("A", "B", "C"):
                alerts = _variant_alerts(result, variant)
                if not has_break:
                    if any(int(a.get("index", a.get("time", 0))) >= 41
                           if variant != "A" else int(a["time"]) >= 41 for a in alerts):
                        null_trials[variant] += 1
                    continue

                matching = []
                opposite = []
                for alert in alerts:
                    time_value = alert["time"]
                    try:
                        month = int(time_value)
                    except (TypeError, ValueError):
                        continue
                    if month < ONSET:
                        continue
                    if variant == "A":
                        observed_sign = 1 if residual_values[month - 1] >= 0 else -1
                    else:
                        observed_sign = int(alert["sign"])
                    if observed_sign == sign:
                        matching.append(month)
                    else:
                        opposite.append(month)
                if opposite:
                    wrong_direction[variant] += 1
                if matching:
                    first = min(matching)
                    detected[variant] += 1
                    delays[variant].append(first - ONSET)

        scenario_result = {"trials": TRIALS, "variants": {}}
        for variant in ("A", "B", "C"):
            if has_break:
                scenario_result["variants"][variant] = {
                    "sensitivity": round(detected[variant] / TRIALS, 4),
                    "sensitivity_95pct_wilson_ci": wilson(detected[variant], TRIALS),
                    "wrong_direction_trial_rate": round(wrong_direction[variant] / TRIALS, 4),
                    "mean_detection_delay": round(statistics.mean(delays[variant]), 2) if delays[variant] else None,
                    "median_detection_delay": statistics.median(delays[variant]) if delays[variant] else None,
                    "missed_trials": TRIALS - detected[variant],
                }
            else:
                scenario_result["variants"][variant] = {
                    "false_alert_rate": round(null_trials[variant] / TRIALS, 4),
                    "false_alert_rate_95pct_wilson_ci": wilson(null_trials[variant], TRIALS),
                    "false_alert_trials": null_trials[variant],
                }
        report["results"][scenario] = scenario_result
    return report


def main():
    report = run_benchmark()
    output = Path(__file__).resolve().parent / "results" / "parallel_fusion_500_seed_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        name: {
            variant: values.get("sensitivity", values.get("false_alert_rate"))
            for variant, values in scenario["variants"].items()
        }
        for name, scenario in report["results"].items()
    }
    print(json.dumps({"output": str(output), "summary": compact}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
