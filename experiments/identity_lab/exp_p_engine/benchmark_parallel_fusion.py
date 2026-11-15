"""Paired 500-seed A/B/C experiment for P-engine false alarms and break sensitivity."""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from experiments.identity_lab.exp_p_engine.engine import DOMAINS
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
    c = DOMAINS["stock"]
    rows, expected_residuals = [], []
    for month in range(1, MONTHS + 1):
        noise, shift, sign = scenario_spec(scenario, month)
        residual = shift + rng.gauss(0.0, noise)
        expected_closing = balance + 400.0 - 400.0 - 5.0
        closing = expected_closing - residual
        rows.append({
            c["opening"]: balance, c["inflow"]: 400.0, c["outflow"]: 400.0,
            c["other"]: 5.0, c["closing"]: closing, "month": month,
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


def _variant_detector_hits(result, variant, residual_values):
    if variant == "A":
        source = result["A"].get("alerts", []) + result["A"].get("suppressed", [])
        mapped = []
        for hit in source:
            if hit.get("detector") == "sign_run":
                detector = "P1"
            elif hit.get("detector") == "cusum":
                detector = "CUSUM"
            else:
                continue
            month = int(hit["time"])
            mapped.append({
                "time": month,
                "detector": detector,
                # Production P2 is one-sided positive CUSUM; P1 is directional.
                "sign": 1 if detector == "CUSUM" else (
                    1 if residual_values[month - 1] >= 0 else -1
                ),
            })
        return mapped

    mapped = []
    for hit in result[variant]["raw_hits"]:
        detector_name = hit.get("detector", "")
        if detector_name == "sign_run":
            detector = "P1"
        elif detector_name.startswith("cusum_"):
            detector = "CUSUM"
        else:
            continue
        mapped.append({
            "time": int(hit["time"]),
            "detector": detector,
            "sign": int(hit["sign"]),
        })
    return mapped


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
            "pre_onset_null_window": [QUIET_RANGE[1] + 1, ONSET - 1],
            "pre_onset_false_alerts_are_scored": True,
            "detector_breakdown_uses_production_emitted_and_suppressed_alerts_for_A": True,
            "variants": {
                "A": "unchanged engine.run production path",
                "B": "two-sided CUSUM; preserve state during variance transitions; unbounded scale",
                "C": "two-sided CUSUM; capped scale; damp updates during variance transitions; capped P1",
                "D": "identical CUSUM to C; production-style adaptive high-noise P1 (13 same-sign run)",
                "E": "two-sided unbounded CUSUM; reset accumulators during variance transitions; adaptive P1; h=8.5",
                "F": "same as E with h=10.5",
                "G": "same as E with h=12.5",
            },
        },
        "results": {},
    }

    variants = ("A", "B", "C", "D", "E", "F", "G")
    for scenario_index, scenario in enumerate(scenarios):
        sign = -1 if "negative" in scenario else (1 if "positive" in scenario else 0)
        has_break = sign != 0
        null_trials = {variant: 0 for variant in variants}
        null_event_counts = {variant: 0 for variant in variants}
        detected = {variant: 0 for variant in variants}
        wrong_direction = {variant: 0 for variant in variants}
        delays = {variant: [] for variant in variants}
        pre_onset_false_trials = {variant: 0 for variant in variants}
        pre_onset_false_events = {variant: 0 for variant in variants}
        detector_stats = {
            variant: {
                detector: {
                    "false_trials": 0,
                    "pre_onset_false_trials": 0,
                    "detected": 0,
                    "wrong_direction": 0,
                    "delays": [],
                }
                for detector in ("P1", "CUSUM")
            }
            for variant in variants
        }

        for trial in range(TRIALS):
            seed = 100_000 + scenario_index * 10_000 + trial
            rows, residual_values = make_rows(seed, scenario)
            result = run_candidates(
                "stock", rows, quiet_range=QUIET_RANGE,
                entity=f"synthetic-{scenario_index}",
                code_revision="p-engine-parallel-fusion-v1",
            )
            for variant in variants:
                alerts = _variant_alerts(result, variant)
                detector_hits = _variant_detector_hits(result, variant, residual_values)
                if not has_break:
                    false_events = [
                        alert for alert in alerts
                        if int(alert.get("index", alert.get("time", 0))) > QUIET_RANGE[1]
                    ]
                    if false_events:
                        null_trials[variant] += 1
                        null_event_counts[variant] += len(false_events)
                    for detector in ("P1", "CUSUM"):
                        if any(hit["time"] > QUIET_RANGE[1] and hit["detector"] == detector
                               for hit in detector_hits):
                            detector_stats[variant][detector]["false_trials"] += 1
                    continue

                # Score false alerts in the post-calibration / pre-event interval.
                # They cannot disappear behind a later true detection.
                pre_onset_alerts = [
                    alert for alert in alerts
                    if QUIET_RANGE[1] < int(alert["time"]) < ONSET
                ]
                if pre_onset_alerts:
                    pre_onset_false_trials[variant] += 1
                    pre_onset_false_events[variant] += len(pre_onset_alerts)
                for detector in ("P1", "CUSUM"):
                    pre_hits = [
                        hit for hit in detector_hits
                        if hit["detector"] == detector
                        and QUIET_RANGE[1] < hit["time"] < ONSET
                    ]
                    if pre_hits:
                        detector_stats[variant][detector]["pre_onset_false_trials"] += 1

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

                for detector in ("P1", "CUSUM"):
                    selected = [
                        hit for hit in detector_hits
                        if hit["detector"] == detector and hit["time"] >= ONSET
                    ]
                    correct = [hit["time"] for hit in selected if hit["sign"] == sign]
                    wrong = [hit for hit in selected if hit["sign"] != sign]
                    if wrong:
                        detector_stats[variant][detector]["wrong_direction"] += 1
                    if correct:
                        detector_stats[variant][detector]["detected"] += 1
                        detector_stats[variant][detector]["delays"].append(min(correct) - ONSET)

        scenario_result = {"trials": TRIALS, "variants": {}}
        for variant in variants:
            if has_break:
                scenario_result["variants"][variant] = {
                    "sensitivity": round(detected[variant] / TRIALS, 4),
                    "sensitivity_95pct_wilson_ci": wilson(detected[variant], TRIALS),
                    "pre_onset_false_alert_rate": round(
                        pre_onset_false_trials[variant] / TRIALS, 4
                    ),
                    "pre_onset_false_alert_rate_95pct_wilson_ci": wilson(
                        pre_onset_false_trials[variant], TRIALS
                    ),
                    "pre_onset_false_alert_trials": pre_onset_false_trials[variant],
                    "pre_onset_false_events_per_sequence": round(
                        pre_onset_false_events[variant] / TRIALS, 4
                    ),
                    "wrong_direction_trial_rate": round(wrong_direction[variant] / TRIALS, 4),
                    "mean_detection_delay": round(statistics.mean(delays[variant]), 2) if delays[variant] else None,
                    "median_detection_delay": statistics.median(delays[variant]) if delays[variant] else None,
                    "missed_trials": TRIALS - detected[variant],
                }
                scenario_result["variants"][variant]["detector_breakdown"] = {
                    detector: {
                        "pre_onset_false_alert_rate": round(
                            detector_stats[variant][detector]["pre_onset_false_trials"] / TRIALS, 4
                        ),
                        "pre_onset_false_alert_rate_95pct_wilson_ci": wilson(
                            detector_stats[variant][detector]["pre_onset_false_trials"], TRIALS
                        ),
                        "sensitivity": round(detector_stats[variant][detector]["detected"] / TRIALS, 4),
                        "sensitivity_95pct_wilson_ci": wilson(
                            detector_stats[variant][detector]["detected"], TRIALS
                        ),
                        "wrong_direction_trial_rate": round(
                            detector_stats[variant][detector]["wrong_direction"] / TRIALS, 4
                        ),
                        "mean_detection_delay": (
                            round(statistics.mean(detector_stats[variant][detector]["delays"]), 2)
                            if detector_stats[variant][detector]["delays"] else None
                        ),
                    }
                    for detector in ("P1", "CUSUM")
                }
            else:
                scenario_result["variants"][variant] = {
                    "false_alert_rate": round(null_trials[variant] / TRIALS, 4),
                    "false_alert_rate_95pct_wilson_ci": wilson(null_trials[variant], TRIALS),
                    "false_alert_trials": null_trials[variant],
                    "false_events_per_sequence": round(
                        null_event_counts[variant] / TRIALS, 4
                    ),
                }
                scenario_result["variants"][variant]["detector_breakdown"] = {
                    detector: {
                        "false_alert_rate": round(
                            detector_stats[variant][detector]["false_trials"] / TRIALS, 4
                        ),
                        "false_alert_rate_95pct_wilson_ci": wilson(
                            detector_stats[variant][detector]["false_trials"], TRIALS
                        ),
                        "false_alert_trials": detector_stats[variant][detector]["false_trials"],
                    }
                    for detector in ("P1", "CUSUM")
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
