"""B-v7 robust innovation sign-CUSUM benchmark: 24M development, 25M paired validation."""
from __future__ import annotations
import argparse, json, math, statistics, time
from pathlib import Path
from typing import Any
import numpy as np
from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import generate_series
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES, N, ONSET, add_measurement, classify, empty_counts, seed_blocks_disjoint,
    seed_ranges, summarize_case
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import SurgicalFactorEngineB61
from experiments.identity_lab.exp_sequential_break_b7_innovation_sign_cusum.engine_b7 import InnovationSignCusumEngineB7

DEV_SEED_BASE = 24_000_000
HOLDOUT_SEED_BASE = 25_000_000
DEV_TRIALS = 500
HOLDOUT_TRIALS = 2_000
FPR_LIMIT = 5.0
SENSITIVITY_TARGET = 93.0
MISS_DELAY_PENALTY = N - ONSET
CUSUM_THRESHOLDS = (6.0, 6.5, 7.0, 7.5, 8.0)
CONFIGS = tuple((corrected, h) for corrected in (False, True) for h in CUSUM_THRESHOLDS)
CONFIG_NAMES = tuple(f"R{int(corrected)}_H{str(h).replace('.', '_')}" for corrected, h in CONFIGS)
BASELINE = "D1_P1_G0_reference_85"
EVENT_KEYS = tuple(empty_counts()["events"].keys())
PAIRED_METRICS = ("structural", "transient", "combined", "pre_combined")
OUTPUT = Path(__file__).resolve().parent / "results" / "sequential_break_engine_b7_innovation_sign_cusum_24m_25m.json"


def config_values(name: str) -> tuple[bool, float]:
    for values, label in zip(CONFIGS, CONFIG_NAMES):
        if label == name:
            return values
    raise ValueError(f"unknown_configuration:{name}")


def make_candidate(name: str) -> InnovationSignCusumEngineB7:
    return InnovationSignCusumEngineB7(
        quiet_end=40, window_size=12, anomaly_z_thresh=3.8, winsor_cap=1.8,
        cusum_threshold=config_values(name)[1],
        structural_rho_bias_correction=config_values(name)[0],
        resolution_horizon=14,
        return_to_baseline_z=1.5, persistence_z_thresh=1.45,
        correlation_method="pearson", innovation_drain=True,
        persistence_floor=False, heuristic_scale_guard=False,
    )


def make_baseline() -> SurgicalFactorEngineB61:
    return SurgicalFactorEngineB61(
        quiet_end=40, window_size=12, anomaly_z_thresh=3.8, winsor_cap=1.8,
        break_percent_thresh=85.0, resolution_horizon=14,
        return_to_baseline_z=1.5, persistence_z_thresh=1.45,
        correlation_method="pearson", innovation_drain=True,
        persistence_floor=True, heuristic_scale_guard=False,
    )


def paired_empty() -> dict[str, dict[str, int]]:
    return {m: {"both": 0, "baseline_only": 0, "candidate_only": 0, "neither": 0}
            for m in PAIRED_METRICS}


def mcnemar_exact_p(baseline_only: int, candidate_only: int) -> float:
    n = baseline_only + candidate_only
    if n == 0:
        return 1.0
    k = min(baseline_only, candidate_only)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def evaluate_stage(seed_base: int, engines: dict[str, Any], trials: int, stage_name: str) -> dict[str, Any]:
    counts = {
        name: {case[0]: {**empty_counts(), "instrumentation": {}, "censored_delays": []}
               for case in CASES}
        for name in engines
    }
    instrumentation_keys = (
        "pending_gate_opportunities", "innovation_gate_rejections",
        "structural_threshold_candidates", "cusum_threshold_crossings",
        "cusum_updates", "cusum_directional_resets",
    )
    for name in engines:
        for bucket in counts[name].values():
            bucket["instrumentation"] = {k: 0 for k in instrumentation_keys}

    paired = {case[0]: paired_empty() for case in CASES} if len(engines) == 2 else {}

    for ci, (case_name, dist, rho, var_jump, shift) in enumerate(CASES):
        for ti in range(trials):
            seed = seed_base + ci * 10_000 + ti
            series = generate_series(
                np.random.default_rng(seed), dist=dist, rho=rho,
                var_jump=var_jump, shift_sigma=shift, n=N, onset=ONSET
            )
            trial_metrics = {}
            for name, engine in engines.items():
                result = engine.analyze(series)
                metric = classify(result, shift)
                trial_metrics[name] = metric
                bucket = counts[name][case_name]
                add_measurement(bucket, metric)
                if shift != 0:
                    bucket["censored_delays"].append(
                        int(metric["delay"]) if metric["delay"] is not None else MISS_DELAY_PENALTY
                    )
                diag = result.get("diagnostics", {})
                for key in instrumentation_keys:
                    bucket["instrumentation"][key] += int(diag.get(key, 0))

            if paired:
                bn, cn = tuple(engines.keys())
                for metric in PAIRED_METRICS:
                    a, b = bool(trial_metrics[bn][metric]), bool(trial_metrics[cn][metric])
                    cell = paired[case_name][metric]
                    if a and b: cell["both"] += 1
                    elif a: cell["baseline_only"] += 1
                    elif b: cell["candidate_only"] += 1
                    else: cell["neither"] += 1

    models = {}
    for name in engines:
        rows = {}
        for case_name, dist, rho, var_jump, shift in CASES:
            bucket = counts[name][case_name]
            row = summarize_case(shift, var_jump, bucket, trials)
            ev = bucket["events"]
            equation = (ev["pending_opened"] == ev["pending_resolved_structural"]
                        + ev["pending_resolved_transient"] + ev["pending_unresolved"])
            row["pending_lifecycle"] = {
                "pending_opened": ev["pending_opened"],
                "pending_resolved_structural": ev["pending_resolved_structural"],
                "pending_resolved_transient": ev["pending_resolved_transient"],
                "pending_unresolved": ev["pending_unresolved"],
                "accounting_complete": bool(bucket["lifecycle_ok"]),
                "equation_holds": bool(equation),
            }
            row["instrumentation"] = bucket["instrumentation"]
            if shift != 0:
                row["median_censored_detection_delay_miss_penalty_75"] = round(
                    float(statistics.median(bucket["censored_delays"])), 2
                )
                row["missed_detection_rate_pct"] = round(
                    100 * sum(d == MISS_DELAY_PENALTY for d in bucket["censored_delays"]) / trials, 2
                )
            rows[case_name] = row

        nonlevel = [r for r in rows.values() if r["scenario_type"] in ("pure_null", "variance_jump")]
        nulls = [r for r in rows.values() if r["scenario_type"] == "pure_null"]
        shifts = [r for r in rows.values() if r["scenario_type"] == "level_shift"]
        worst_s = max(r["structural_rate"]["rate_pct"] for r in nonlevel)
        worst_t = max(r["transient_alert_rate"]["rate_pct"] for r in nonlevel)
        worst_c_null = max(r["combined_any_alert_rate"]["rate_pct"] for r in nulls)
        worst_c_nonlevel = max(r["combined_any_alert_rate"]["rate_pct"] for r in nonlevel)
        worst_pre = max(r["pre_onset_combined_rate"]["rate_pct"] for r in shifts)
        sensitivity = round(statistics.mean(r["structural_rate"]["rate_pct"] for r in shifts), 2)
        hit_delays = [int(d) for c, *_, sh in CASES if sh != 0 for d in counts[name][c]["delays"]]
        censored = [int(d) for c, *_, sh in CASES if sh != 0 for d in counts[name][c]["censored_delays"]]
        all_lifecycle = all(r["pending_lifecycle_accounting_complete"]
                            and r["pending_lifecycle"]["equation_holds"] for r in rows.values())
        gates = {
            "structural_fpr_all_nonlevel_le_5": worst_s <= FPR_LIMIT,
            "transient_fpr_all_nonlevel_le_5": worst_t <= FPR_LIMIT,
            "combined_fpr_all_pure_null_le_5": worst_c_null <= FPR_LIMIT,
            "pre_onset_combined_all_shifts_le_5": worst_pre <= FPR_LIMIT,
            "mean_directional_sensitivity_ge_93": sensitivity >= SENSITIVITY_TARGET,
            "lifecycle_accounting": all_lifecycle,
        }
        models[name] = {
            "cases": rows,
            "worst_structural_fpr_nonlevel_pct": worst_s,
            "worst_transient_fpr_nonlevel_pct": worst_t,
            "worst_combined_fpr_pure_null_pct": worst_c_null,
            "worst_combined_fpr_nonlevel_pct": worst_c_nonlevel,
            "worst_pre_onset_combined_pct": worst_pre,
            "mean_directional_sensitivity_pct": sensitivity,
            "median_correct_detection_delay": round(float(statistics.median(hit_delays)), 2) if hit_delays else None,
            "median_censored_detection_delay_miss_penalty_75": round(float(statistics.median(censored)), 2) if censored else None,
            "lifecycle_accounting_complete": all_lifecycle,
            "point_gates": gates,
            "event_totals": {m: sum(b["events"][m] for b in counts[name].values()) for m in EVENT_KEYS},
        }

    if paired:
        for case_name, metrics in paired.items():
            for metric, table in metrics.items():
                table["mcnemar_exact_two_sided_p"] = mcnemar_exact_p(
                    table["baseline_only"], table["candidate_only"]
                )

    return {
        "stage": stage_name,
        "seed_base": seed_base,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "generated_series_count": len(CASES) * trials,
        "configuration_count": len(engines),
        "configuration_evaluations": len(CASES) * trials * len(engines),
        "same_generated_series_for_all_configurations": True,
        "models": models,
        "paired_sequence_comparisons": paired,
    }


def failures(m: dict[str, Any]) -> int:
    keys = ("structural_fpr_all_nonlevel_le_5", "transient_fpr_all_nonlevel_le_5",
            "combined_fpr_all_pure_null_le_5", "pre_onset_combined_all_shifts_le_5")
    return sum(not m["point_gates"][k] for k in keys)


def excess(m: dict[str, Any]) -> float:
    keys = ("worst_structural_fpr_nonlevel_pct", "worst_transient_fpr_nonlevel_pct",
            "worst_combined_fpr_pure_null_pct", "worst_pre_onset_combined_pct")
    return sum(max(0, float(m[k]) - FPR_LIMIT) for k in keys)


def select_development(development: dict[str, Any]) -> dict[str, Any]:
    scores = {}
    for name in CONFIG_NAMES:
        m = development["models"][name]
        eligible = (failures(m) == 0 and m["point_gates"]["mean_directional_sensitivity_ge_93"]
                    and m["point_gates"]["lifecycle_accounting"])
        scores[name] = {
            "eligible": eligible,
            "fpr_gate_failures": failures(m),
            "sum_fpr_excess_percentage_points": round(excess(m), 4),
            "mean_directional_sensitivity_pct": m["mean_directional_sensitivity_pct"],
            "median_censored_delay": m["median_censored_detection_delay_miss_penalty_75"],
            "cusum_threshold": config_values(name)[1],
            "structural_rho_bias_correction": config_values(name)[0],
            "point_gates": m["point_gates"],
        }

    def delay(name: str) -> float:
        v = scores[name]["median_censored_delay"]
        return float(v) if v is not None else float("inf")

    eligible = [n for n, v in scores.items() if v["eligible"]]
    if eligible:
        selected = sorted(eligible, key=lambda n: (
            -scores[n]["mean_directional_sensitivity_pct"], delay(n),
            -scores[n]["cusum_threshold"], scores[n]["structural_rho_bias_correction"], n
        ))[0]
        mode = "eligible_highest_sensitivity_then_lowest_censored_delay"
    else:
        selected = sorted(CONFIG_NAMES, key=lambda n: (
            scores[n]["fpr_gate_failures"], scores[n]["sum_fpr_excess_percentage_points"],
            -scores[n]["mean_directional_sensitivity_pct"], delay(n),
            -scores[n]["cusum_threshold"], scores[n]["structural_rho_bias_correction"], n
        ))[0]
        mode = "best_effort_no_threshold_met_all_development_gates"
    return {
        "selected_configuration": selected,
        "selected_cusum_threshold": config_values(selected)[1],
        "selected_structural_rho_bias_correction": config_values(selected)[0],
        "selection_mode": mode,
        "development_all_gates_met": bool(scores[selected]["eligible"]),
        "eligible_configurations": eligible,
        "configuration_scores": scores,
        "rule": (
            "Eligibility requires all four FPR point-estimate ceilings <=5%, mean directional "
            "sensitivity >=93%, and exact PENDING accounting. Eligible choices maximize sensitivity, "
            "then minimize median censored delay (misses count as 75), then prefer higher threshold. "
            "If none qualify: minimize failed FPR ceilings, excess above 5, maximize sensitivity, "
            "minimize censored delay, then prefer higher threshold. Holdout is excluded."
        ),
        "holdout_used_for_selection": False,
    }


def confidence_gates(summary: dict[str, Any]) -> dict[str, bool]:
    rows = summary["cases"]
    nonlevel = [r for r in rows.values() if r["scenario_type"] in ("pure_null", "variance_jump")]
    nulls = [r for r in rows.values() if r["scenario_type"] == "pure_null"]
    shifts = [r for r in rows.values() if r["scenario_type"] == "level_shift"]
    return {
        "structural_wilson_upper95_all_nonlevel_le_5": all(r["structural_rate"]["wilson95_pct"][1] <= FPR_LIMIT for r in nonlevel),
        "transient_wilson_upper95_all_nonlevel_le_5": all(r["transient_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT for r in nonlevel),
        "combined_wilson_upper95_all_pure_null_le_5": all(r["combined_any_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT for r in nulls),
        "pre_onset_combined_wilson_upper95_all_shifts_le_5": all(r["pre_onset_combined_rate"]["wilson95_pct"][1] <= FPR_LIMIT for r in shifts),
        "mean_directional_sensitivity_ge_93": summary["mean_directional_sensitivity_pct"] >= SENSITIVITY_TARGET,
        "lifecycle_accounting": summary["lifecycle_accounting_complete"],
    }


def print_summary(title: str, stage: dict[str, Any]) -> None:
    print(f"\n=== {title} ===", flush=True)
    print("config | Struct FPR | Transient FPR | Combined null | Pre-onset | Sensitivity | Delay hit | Delay censored")
    for name, m in stage["models"].items():
        print(f"{name} | {m['worst_structural_fpr_nonlevel_pct']:.2f}% | "
              f"{m['worst_transient_fpr_nonlevel_pct']:.2f}% | "
              f"{m['worst_combined_fpr_pure_null_pct']:.2f}% | "
              f"{m['worst_pre_onset_combined_pct']:.2f}% | "
              f"{m['mean_directional_sensitivity_pct']:.2f}% | "
              f"{m['median_correct_detection_delay']} | "
              f"{m['median_censored_detection_delay_miss_penalty_75']}", flush=True)
        for case, r in m["cases"].items():
            print(f"  {case}: Structural={r['structural_rate']['rate_pct']:.2f}% "
                  f"Transient={r['transient_alert_rate']['rate_pct']:.2f}% "
                  f"Combined={r['combined_any_alert_rate']['rate_pct']:.2f}% "
                  f"Pre={r['pre_onset_combined_rate']['rate_pct']:.2f}% "
                  f"Delay={r['median_correct_detection_delay']} "
                  f"Life={r['pending_lifecycle']['equation_holds']}", flush=True)


def run(dev_trials: int = DEV_TRIALS, holdout_trials: int = HOLDOUT_TRIALS,
        dev_seed_base: int = DEV_SEED_BASE, holdout_seed_base: int = HOLDOUT_SEED_BASE,
        output: Path = OUTPUT, official: bool = True) -> dict[str, Any]:
    if dev_trials < 1 or holdout_trials < 1:
        raise ValueError("trial_counts_must_be_positive")
    if official and (dev_trials != DEV_TRIALS or holdout_trials != HOLDOUT_TRIALS
                     or dev_seed_base != DEV_SEED_BASE or holdout_seed_base != HOLDOUT_SEED_BASE):
        raise ValueError("official_B7_requires_500_dev_2000_holdout_trials_and_24M_25M_seed_bases")
    if N != 140 or ONSET != 65:
        raise AssertionError(f"generator_contract_mismatch:N={N},ONSET={ONSET}")

    started = time.perf_counter()
    dev_engines = {name: make_candidate(name) for name in CONFIG_NAMES}
    dev = evaluate_stage(dev_seed_base, dev_engines, dev_trials, "development_threshold_screen")
    dev_seconds = round(time.perf_counter() - started, 2)
    selection = select_development(dev)
    selected = selection["selected_configuration"]

    hold_engines = {BASELINE: make_baseline(), selected: make_candidate(selected)}
    started = time.perf_counter()
    hold = evaluate_stage(holdout_seed_base, hold_engines, holdout_trials, "paired_pristine_holdout")
    hold_seconds = round(time.perf_counter() - started, 2)

    dev_ranges, hold_ranges = seed_ranges(dev_seed_base, dev_trials), seed_ranges(holdout_seed_base, holdout_trials)
    disjoint = seed_blocks_disjoint(dev_ranges, hold_ranges)
    if not disjoint:
        raise AssertionError("development_and_holdout_seed_blocks_overlap")
    for stage_name, stage in (("development", dev), ("holdout", hold)):
        for model_name, model in stage["models"].items():
            for case_name, row in model["cases"].items():
                life = row["pending_lifecycle"]
                if not life["equation_holds"] or not life["accounting_complete"]:
                    raise AssertionError(f"pending_accounting_failed:{stage_name}:{model_name}:{case_name}")

    gates = {name: confidence_gates(m) for name, m in hold["models"].items()}
    final_gates = {name: all(v.values()) for name, v in gates.items()}
    report = {
        "experiment": "B-v7 Robust Innovation Sign-CUSUM Structural Detector",
        "candidate_branch": "experiment/b7-innovation-sign-cusum",
        "base_commit": "1f3f369f9c0b67344954d288c99d923d5b9b5c22",
        "base_configuration": {
            "reference": "B-v6.1 D1_P1_G0 at fixed threshold 85",
            "D": "B-v6.1 transient PENDING gate; raw rho path unchanged",
            "context_rho": "raw Pearson lag-1 clipped [0,0.88]",
            "structural_rho": "development ablation: raw clipped Pearson OR corrected (rho_raw+1/40)/(1-3/40), clipped [0,0.88]; structural channel only",
            "G": False, "P_floor": False, "Sign_Flip_Guard": False,
        },
        "structural_specification": {
            "innovation": "v_t=x_t-median(quiet)-rho_structural_used*(x_(t-1)-median(quiet))",
            "score": "two reflected Bernoulli log-likelihood CUSUMs with H0 sign probability 0.5 and directional H1 probability 0.65",
            "decision": "announce direction when its CUSUM reaches selected h",
            "outlier_robustness": "one sign increment per observation, independent of magnitude",
            "latch": "reset only when abs(window_shift_z)<0.40",
            "reversal": "while latched, accumulate only opposite-direction evidence",
        },
        "fixed_specification": {
            "quiet_end": 40, "window_size": 12, "series_length": 140, "onset_index_zero_based": 65,
            "winsor_cap": 1.8, "persistence_z_threshold": 1.45, "anomaly_z_thresh": 3.8,
            "resolution_horizon": 14, "return_to_baseline_z": 1.5,
            "cusum_null_sign_probability": 0.5, "cusum_alternative_sign_probability": 0.65,
            "combined_definition": "union of structural, transient and unresolved",
            "pending_lifecycle_equation": "opened=resolved_structural+resolved_transient+unresolved",
        },
        "design": {
            "cases": [c[0] for c in CASES], "case_count": len(CASES),
            "trials_per_case_development": dev_trials, "trials_per_case_holdout": holdout_trials,
            "development_seed_base": dev_seed_base, "holdout_seed_base": holdout_seed_base,
            "seed_scheme": "seed_base+case_index*10000+trial_index",
            "development_seed_ranges": dev_ranges, "holdout_seed_ranges": hold_ranges,
            "seed_blocks_disjoint": disjoint,
            "development_generated_series": dev["generated_series_count"],
            "development_configuration_evaluations": dev["configuration_evaluations"],
            "holdout_generated_series": hold["generated_series_count"],
            "holdout_configuration_evaluations": hold["configuration_evaluations"],
            "same_generated_series_within_each_stage": True,
            "development_configurations": [
                {"name": n, "structural_rho_bias_correction": config_values(n)[0],
                 "cusum_threshold": config_values(n)[1]}
                for n in CONFIG_NAMES
            ],
            "holdout_configurations": [BASELINE, selected],
            "selection_uses_24m_only": True, "25m_uses_only_reference_and_selected_candidate": True,
            "false_alarm_budget_pct": FPR_LIMIT, "sensitivity_target_pct": SENSITIVITY_TARGET,
            "wilson_confidence_level_pct": 95, "miss_delay_penalty": MISS_DELAY_PENALTY,
        },
        "development_elapsed_seconds": dev_seconds,
        "development_threshold_screen": dev,
        "development_selection": selection,
        "holdout_elapsed_seconds": hold_seconds,
        "paired_25m_holdout": hold,
        "holdout_confidence_gates": gates,
        "holdout_final_gates": final_gates,
        "holdout_approval": bool(final_gates.get(selected, False)),
        "selected_candidate": selected,
        "selected_cusum_threshold": config_values(selected)[1],
        "selected_structural_rho_bias_correction": config_values(selected)[0],
        "baseline_reference": BASELINE,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary("24M DEVELOPMENT", dev)
    print(f"\nselected={selected} correction={config_values(selected)[0]} "
          f"h={config_values(selected)[1]} mode={selection['selection_mode']} "
          f"all_dev_gates={selection['development_all_gates_met']}", flush=True)
    print_summary("25M PAIRED HOLDOUT", hold)
    print("\n=== 25M WILSON 95% GATES ===", flush=True)
    for name, row in gates.items():
        print(f"{name}: {row}; final={final_gates[name]}", flush=True)
    print(f"\nreport={output}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run(dev_trials=12, holdout_trials=12, dev_seed_base=1_370_000,
            holdout_seed_base=2_370_000, output=Path("/tmp/b7_smoke_report.json"), official=False)
    else:
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
