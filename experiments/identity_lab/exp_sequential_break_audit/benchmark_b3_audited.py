"""B-v3.1 Audit-Complete: pending alert lifecycle and complete alert accounting.

This is an isolated audit candidate. It does not modify or replace B-v3.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np


N = 140
ONSET = 65
DEFAULT_THRESHOLD = 85.0
DEFAULT_SEED_BASE = 5_000_000
DEFAULT_TRIALS = 500
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b3_1_audited_500.json"
)


class AuditedSequentialBreakEngineB3:
    """Causal detector with explicit PENDING -> terminal-state accounting.

    A pending spike is resolved exactly once as one of:
      * RESOLVED_STRUCTURAL: absorbed by a same-direction structural break
        detected within the configured horizon.
      * RESOLVED_TRANSIENT: horizon elapsed without such a structural break.
      * UNRESOLVED_AT_END: the input ended before the horizon elapsed.

    The original B-v3 detector remains untouched.
    """

    def __init__(
        self,
        quiet_end: int = 40,
        window_size: int = 12,
        anomaly_z_thresh: float = 3.2,
        winsor_cap: float = 2.5,
        break_percent_thresh: float = DEFAULT_THRESHOLD,
        resolution_horizon: int = 6,
    ) -> None:
        if quiet_end < 4:
            raise ValueError("quiet_end_must_be_at_least_4")
        if window_size < 4:
            raise ValueError("window_size_must_be_at_least_4")
        if anomaly_z_thresh <= 0:
            raise ValueError("anomaly_z_thresh_must_be_positive")
        if winsor_cap <= 0:
            raise ValueError("winsor_cap_must_be_positive")
        if not 0 <= break_percent_thresh <= 100:
            raise ValueError("break_percent_thresh_out_of_range")
        if resolution_horizon < 1:
            raise ValueError("resolution_horizon_must_be_at_least_1")

        self.quiet_end = int(quiet_end)
        self.window_size = int(window_size)
        self.anomaly_z_thresh = float(anomaly_z_thresh)
        self.winsor_cap = float(winsor_cap)
        self.break_percent_thresh = float(break_percent_thresh)
        self.resolution_horizon = int(resolution_horizon)

    def _estimate_onset(
        self, series: np.ndarray, detection_t: int, lookback: int = 22
    ) -> int:
        start = max(self.quiet_end, detection_t - int(lookback))
        segment = series[start : detection_t + 1]
        if len(segment) < 6:
            return int(start)

        best_tau = start
        best_contrast = -1.0
        for split in range(2, len(segment) - 2):
            contrast = abs(
                float(np.median(segment[split:]) - np.median(segment[:split]))
            )
            if contrast > best_contrast:
                best_contrast = contrast
                best_tau = start + split
        return int(best_tau)

    def analyze(self, series: np.ndarray | list[float]) -> dict[str, Any]:
        values = np.asarray(series, dtype=float)
        if values.ndim != 1:
            raise ValueError("series_must_be_one_dimensional")
        if not np.all(np.isfinite(values)):
            raise ValueError("series_contains_nonfinite_values")
        n = int(values.size)
        if n < self.quiet_end + self.window_size:
            raise ValueError("series_too_short_for_quiet_and_window")

        quiet = values[: self.quiet_end]
        baseline_center = float(np.median(quiet))

        quiet_diffs = np.diff(quiet)
        base_diff_mad = float(
            np.median(np.abs(quiet_diffs)) * 1.4826 / np.sqrt(2.0)
        )
        base_diff_mad = max(base_diff_mad, 1e-6)

        q_spread = float(
            np.median(np.abs(quiet - baseline_center)) * 1.4826
        )
        q_spread = max(q_spread, 1e-6)
        q_norm = (quiet - baseline_center) / q_spread

        # np.corrcoef returns a 2x2 matrix; the lag-1 coefficient is [0, 1].
        if (
            q_norm.size > 2
            and np.std(q_norm[:-1]) > 1e-12
            and np.std(q_norm[1:]) > 1e-12
        ):
            rho_raw = float(np.corrcoef(q_norm[:-1], q_norm[1:])[0, 1])
        else:
            rho_raw = 0.0
        if not np.isfinite(rho_raw):
            rho_raw = 0.0
        rho = float(np.clip(rho_raw, 0.0, 0.88))

        ar_factor = 1.0 / np.sqrt(max(1.0 - rho, 0.12))
        f_lrv_corrected = np.sqrt(1.0 + rho) / max(1.0 - rho, 0.12)

        structural_breaks: list[dict[str, Any]] = []
        transient_anomalies: list[dict[str, Any]] = []
        unresolved_alerts: list[dict[str, Any]] = []
        pending_spikes: list[dict[str, Any]] = []
        pending_opened = 0
        latched_direction = 0

        start_t = self.quiet_end + self.window_size - 1
        for t in range(start_t, n):
            win_start = t - self.window_size + 1
            window = values[win_start : t + 1]

            hist_start = max(1, win_start - 10)
            local_diffs = np.abs(np.diff(values[hist_start : t + 1]))
            local_diff_mad = (
                float(np.median(local_diffs) * 1.4826 / np.sqrt(2.0))
                if local_diffs.size
                else 0.0
            )
            active_diff_scale = max(base_diff_mad, local_diff_mad, 1e-6)

            marginal_scale = active_diff_scale * ar_factor
            context_scale = active_diff_scale * f_lrv_corrected

            z_point_raw = (window - baseline_center) / marginal_scale
            z_context_raw = (window - baseline_center) / context_scale

            # Stage 1: record a spike as pending; do not prematurely call it transient.
            z_current = float(z_point_raw[-1])
            recent_pending = any(
                0 <= t - int(p["time"]) <= 2 for p in pending_spikes
            )
            if (
                abs(z_current) > self.anomaly_z_thresh
                and latched_direction == 0
                and not recent_pending
            ):
                pending_spikes.append(
                    {
                        "time": int(t),
                        "value": round(float(values[t]), 3),
                        "deviation_sigma": round(z_current, 2),
                        "direction": 1 if z_current > 0 else -1,
                    }
                )
                pending_opened += 1

            # Stage 2: use the unchanged B-v3 structural-break score.
            z_point = np.clip(z_point_raw, -self.winsor_cap, self.winsor_cap)
            z_context = np.clip(z_context_raw, -self.winsor_cap, self.winsor_cap)

            full_pos = float(np.mean(z_point > 1.30))
            full_neg = float(np.mean(z_point < -1.30))
            dominant_persistence = max(full_pos, full_neg)
            direction = 1 if full_pos >= full_neg else -1

            window_shift_z = float(np.median(z_context))
            separation_score = min(abs(window_shift_z) / 1.45, 1.0)
            break_pct = round(
                float(
                    (0.45 * dominant_persistence + 0.55 * separation_score)
                    * 100.0
                ),
                1,
            )

            if (
                break_pct >= self.break_percent_thresh
                and latched_direction != direction
            ):
                estimated_onset = self._estimate_onset(values, t)
                resolved_pending: list[dict[str, Any]] = []
                still_pending: list[dict[str, Any]] = []
                for pending in pending_spikes:
                    age = t - int(pending["time"])
                    if (
                        pending["direction"] == direction
                        and 0 <= age <= self.resolution_horizon + 4
                    ):
                        resolved_pending.append(
                            {
                                **pending,
                                "resolved_at": int(t),
                                "status": "RESOLVED_STRUCTURAL",
                            }
                        )
                    else:
                        still_pending.append(pending)
                pending_spikes = still_pending

                structural_breaks.append(
                    {
                        "detection_time": int(t),
                        "estimated_onset": int(estimated_onset),
                        "direction": int(direction),
                        "break_percentage": float(break_pct),
                        # Explicitly retain the pending alerts absorbed by this break.
                        "resolved_pending_alerts": resolved_pending,
                    }
                )
                latched_direction = direction
            elif abs(window_shift_z) < 0.40:
                latched_direction = 0

            # Stage 3: pending alerts that reach the horizon without a matching
            # structural break are finalized as transient.
            still_pending = []
            for pending in pending_spikes:
                if t - int(pending["time"]) >= self.resolution_horizon:
                    transient_anomalies.append(
                        {
                            **pending,
                            "resolved_at": int(t),
                            "status": "RESOLVED_TRANSIENT",
                        }
                    )
                else:
                    still_pending.append(pending)
            pending_spikes = still_pending

        # Stage 4: preserve pending events when the series ends before resolution.
        for pending in pending_spikes:
            unresolved_alerts.append(
                {
                    **pending,
                    "status": "UNRESOLVED_AT_END",
                }
            )

        resolved_structural_count = sum(
            len(item["resolved_pending_alerts"]) for item in structural_breaks
        )
        resolved_transient_count = len(transient_anomalies)
        unresolved_count = len(unresolved_alerts)
        accounted_for = (
            resolved_structural_count + resolved_transient_count + unresolved_count
        )
        # Audit invariant: every opened PENDING alert has exactly one terminal state.
        if pending_opened != accounted_for:
            raise AssertionError(
                "pending_lifecycle_accounting_mismatch:"
                f"opened={pending_opened}, terminal={accounted_for}"
            )

        return {
            "structural_breaks": structural_breaks,
            "transient_anomalies": transient_anomalies,
            "unresolved_alerts": unresolved_alerts,
            "pending_lifecycle": {
                "opened_count": pending_opened,
                "resolved_structural_count": resolved_structural_count,
                "resolved_transient_count": resolved_transient_count,
                "unresolved_count": unresolved_count,
                "accounting_complete": pending_opened == accounted_for,
            },
            "diagnostics": {
                "rho_estimate": round(rho, 6),
                "baseline_center": round(baseline_center, 6),
                "base_diff_scale": round(base_diff_mad, 6),
            },
        }


def generate_series(
    rng: np.random.Generator,
    *,
    dist: str = "gauss",
    rho: float = 0.7,
    var_jump: bool = False,
    shift_sigma: float = 0.0,
    n: int = N,
    onset: int = ONSET,
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

    # Explicit innovations buffer avoids aliasing the input noise array.
    values = np.empty(n, dtype=float)
    values[0] = eps[0]
    innovation_scale = np.sqrt(1.0 - rho**2)
    for t in range(1, n):
        values[t] = rho * values[t - 1] + innovation_scale * eps[t]

    if shift_sigma != 0.0:
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
        z
        * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
        / denom
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def classify_trial(
    result: dict[str, Any],
    *,
    shift_sigma: float,
    onset: int = ONSET,
) -> dict[str, Any]:
    """Return sequence-level metrics; Combined is the union of all alert types."""
    breaks = list(result["structural_breaks"])
    transients = list(result["transient_anomalies"])
    unresolved = list(result["unresolved_alerts"])

    any_structural = bool(breaks)
    any_transient = bool(transients)
    any_unresolved = bool(unresolved)
    combined_any_alert = any_structural or any_transient or any_unresolved

    if shift_sigma == 0.0:
        structural_metric = any_structural
        correct_breaks: list[dict[str, Any]] = []
        wrong_breaks: list[dict[str, Any]] = []
        pre_breaks = []
        detection_delay = None
    else:
        expected_direction = 1 if shift_sigma > 0 else -1
        pre_breaks = [
            item for item in breaks if int(item["detection_time"]) < onset
        ]
        post_breaks = [
            item for item in breaks if int(item["detection_time"]) >= onset
        ]
        correct_breaks = [
            item for item in post_breaks
            if int(item["direction"]) == expected_direction
        ]
        wrong_breaks = [
            item for item in post_breaks
            if int(item["direction"]) != expected_direction
        ]
        structural_metric = bool(correct_breaks)
        first_correct = (
            min(correct_breaks, key=lambda item: int(item["detection_time"]))
            if correct_breaks
            else None
        )
        detection_delay = (
            int(first_correct["detection_time"]) - onset
            if first_correct is not None
            else None
        )

    return {
        # In null cases this is structural FPR; in shift cases it is
        # directionally-correct structural sensitivity.
        "structural_metric": bool(structural_metric),
        "any_structural_alert": any_structural,
        "transient_alert": any_transient,
        "unresolved_alert": any_unresolved,
        "combined_any_alert": bool(combined_any_alert),
        "correct_structural_events": len(correct_breaks),
        "wrong_direction_structural_events": len(wrong_breaks),
        "pre_onset_structural_events": len(pre_breaks),
        "detection_delay": detection_delay,
    }


def _rate(successes: int, trials: int) -> dict[str, Any]:
    interval = wilson_interval(successes, trials)
    return {
        "sequences": successes,
        "rate_pct": round(successes / trials * 100.0, 2),
        "wilson95_pct": [round(value * 100.0, 2) for value in interval],
    }


def run_audited_benchmark(
    *,
    threshold: float = DEFAULT_THRESHOLD,
    seed_base: int = DEFAULT_SEED_BASE,
    trials: int = DEFAULT_TRIALS,
    output: Path = OUTPUT,
) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials_must_be_positive")

    engine = AuditedSequentialBreakEngineB3(
        break_percent_thresh=threshold,
        resolution_horizon=6,
    )
    cases = [
        ("gauss_r0.3_null", "gauss", 0.3, False, 0.0),
        ("gauss_r0.7_null", "gauss", 0.7, False, 0.0),
        ("gauss_r0.7_vjump", "gauss", 0.7, True, 0.0),
        ("t3_r0.3_null", "t3", 0.3, False, 0.0),
        ("t3_r0.7_null", "t3", 0.7, False, 0.0),
        ("t3_r0.7_vjump", "t3", 0.7, True, 0.0),
        ("pos_shift_3.0s", "gauss", 0.7, False, 3.0),
        ("neg_shift_3.0s", "gauss", 0.7, False, -3.0),
    ]

    case_reports: dict[str, Any] = {}
    for case_index, (name, dist, rho, var_jump, shift) in enumerate(cases):
        structural_sequences = 0
        transient_sequences = 0
        unresolved_sequences = 0
        combined_sequences = 0
        correct_structural_sequences = 0
        wrong_direction_sequences = 0
        pre_onset_structural_sequences = 0
        delays: list[int] = []
        event_totals = {
            "structural": 0,
            "transient": 0,
            "unresolved": 0,
            "pending_opened": 0,
            "pending_resolved_structural": 0,
            "pending_resolved_transient": 0,
            "pending_unresolved": 0,
        }

        for trial in range(trials):
            rng = np.random.default_rng(seed_base + case_index * 10_000 + trial)
            series = generate_series(
                rng,
                dist=dist,
                rho=rho,
                var_jump=var_jump,
                shift_sigma=shift,
            )
            result = engine.analyze(series)
            metrics = classify_trial(result, shift_sigma=shift)

            if shift == 0.0:
                if metrics["structural_metric"]:
                    structural_sequences += 1
            elif metrics["structural_metric"]:
                correct_structural_sequences += 1
                structural_sequences += 1

            transient_sequences += int(metrics["transient_alert"])
            unresolved_sequences += int(metrics["unresolved_alert"])
            combined_sequences += int(metrics["combined_any_alert"])
            wrong_direction_sequences += int(
                metrics["wrong_direction_structural_events"] > 0
            )
            pre_onset_structural_sequences += int(
                metrics["pre_onset_structural_events"] > 0
            )
            if metrics["detection_delay"] is not None:
                delays.append(int(metrics["detection_delay"]))

            event_totals["structural"] += len(result["structural_breaks"])
            event_totals["transient"] += len(result["transient_anomalies"])
            event_totals["unresolved"] += len(result["unresolved_alerts"])
            lifecycle = result["pending_lifecycle"]
            event_totals["pending_opened"] += lifecycle["opened_count"]
            event_totals["pending_resolved_structural"] += (
                lifecycle["resolved_structural_count"]
            )
            event_totals["pending_resolved_transient"] += (
                lifecycle["resolved_transient_count"]
            )
            event_totals["pending_unresolved"] += lifecycle["unresolved_count"]

        scenario_type = (
            "pure_null"
            if shift == 0.0 and not var_jump
            else "variance_jump"
            if shift == 0.0 and var_jump
            else "level_shift"
        )
        structural_label = (
            "structural_false_alarm"
            if scenario_type != "level_shift"
            else "correct_directional_structural_detection"
        )

        case_reports[name] = {
            "scenario_type": scenario_type,
            "trials": trials,
            "structural_metric_label": structural_label,
            "structural_rate": _rate(structural_sequences, trials),
            "transient_alert_rate": _rate(transient_sequences, trials),
            "unresolved_alert_rate": _rate(unresolved_sequences, trials),
            "combined_any_alert_rate": _rate(combined_sequences, trials),
            "wrong_direction_structural_rate": _rate(
                wrong_direction_sequences, trials
            ),
            "pre_onset_structural_rate": _rate(
                pre_onset_structural_sequences, trials
            ),
            "median_correct_detection_delay": (
                round(float(statistics.median(delays)), 2) if delays else None
            ),
            "event_totals": event_totals,
            "pending_lifecycle_accounting_complete": (
                event_totals["pending_opened"]
                == event_totals["pending_resolved_structural"]
                + event_totals["pending_resolved_transient"]
                + event_totals["pending_unresolved"]
            ),
        }

    report = {
        "experiment": "sequential_break_engine_b3_1_audit_complete",
        "candidate": "AuditedSequentialBreakEngineB3",
        "configuration": {
            "quiet_end": 40,
            "window_size": 12,
            "anomaly_z_thresh": 3.2,
            "winsor_cap": 2.5,
            "break_percent_thresh": threshold,
            "resolution_horizon": 6,
            "onset_index_zero_based": ONSET,
        },
        "design": {
            "series_length": N,
            "trials_per_case": trials,
            "case_count": len(cases),
            "distribution": ["gauss", "t3"],
            "rho_levels": [0.3, 0.7],
            "variance_jump_cases": 2,
            "level_shift_cases": 2,
            "pure_null_cases": 4,
            "seed_base": seed_base,
            "seed_scheme": "seed_base + case_index*10000 + trial",
            "sequence_rate_definition": (
                "A sequence is counted once per indicator if it contains at least "
                "one event of that indicator."
            ),
            "combined_definition": (
                "Combined is the sequence-level union of ANY structural break "
                "(including wrong-direction or pre-onset), transient anomaly, "
                "or unresolved alert."
            ),
            "pending_lifecycle_invariant": (
                "opened = resolved_structural + resolved_transient + unresolved"
            ),
        },
        "cases": case_reports,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"=== B-v3.1 AUDIT-COMPLETE "
        f"(threshold={threshold:.1f}, trials={trials}) ==="
    )
    header = (
        f"{'Scenario':18s} | {'Struct':>7s} | {'Trans':>7s} | "
        f"{'Unres':>7s} | {'Combined':>8s} | {'Delay':>5s}"
    )
    print(header)
    print("-" * len(header))
    for name, row in case_reports.items():
        struct_pct = row["structural_rate"]["rate_pct"]
        trans_pct = row["transient_alert_rate"]["rate_pct"]
        unres_pct = row["unresolved_alert_rate"]["rate_pct"]
        combined_pct = row["combined_any_alert_rate"]["rate_pct"]
        delay = row["median_correct_detection_delay"]
        delay_text = f"{delay:.1f}" if delay is not None else "-"
        print(
            f"{name:18s} | {struct_pct:6.1f}% | {trans_pct:6.1f}% | "
            f"{unres_pct:6.1f}% | {combined_pct:7.1f}% | {delay_text:>5s}"
        )
    print(f"report={output}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--seed-base", type=int, default=DEFAULT_SEED_BASE)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    run_audited_benchmark(
        threshold=args.threshold,
        seed_base=args.seed_base,
        trials=args.trials,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
