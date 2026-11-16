"""B-v6.3 dual-tier confirmation: 20M development and paired 21M holdout."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    generate_series,
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES,
    N,
    ONSET,
    add_measurement,
    classify,
    empty_counts,
    seed_blocks_disjoint,
    seed_ranges,
    summarize_case,
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import (
    SurgicalFactorEngineB61,
)
from experiments.identity_lab.exp_sequential_break_b63_dual_tier_confirmation.engine_b63 import (
    DualTierStructuralConfirmationEngineB63,
)

DEV_SEED_BASE = 20_000_000
HOLDOUT_SEED_BASE = 21_000_000
TRIALS_PER_CASE = 500
FPR_LIMIT = 5.0
SENSITIVITY_TARGET = 93.0
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b63_dual_tier_20m_21m.json"
)
CONFIGS = ((88.0, 2), (88.0, 3), (90.0, 2), (90.0, 3))
CONFIG_NAMES = tuple(f"F{int(threshold)}_H{hold}" for threshold, hold in CONFIGS)
BASELINE = "D1_P1_G0_reference_85"
INSTRUMENTATION_KEYS = (
    "pending_gate_opportunities",
    "innovation_gate_rejections",
    "structural_threshold_candidates",
    "persistence_floor_rejections",
    "confirmation_candidate_windows",
    "hold_counter_resets",
    "hold_counter_peak",
    "fast_path_announcements",
    "confirmed_path_announcements",
)
EVENT_KEYS = tuple(empty_counts()["events"].keys())


def config_values(name: str) -> tuple[float, int]:
    for (threshold, hold), candidate_name in zip(CONFIGS, CONFIG_NAMES):
        if candidate_name == name:
            return threshold, hold
    raise ValueError(f"unknown_configuration:{name}")


def make_candidate(name: str) -> DualTierStructuralConfirmationEngineB63:
    fast_thresh, hold_steps = config_values(name)
    return DualTierStructuralConfirmationEngineB63(
        quiet_end=40,
        window_size=12,
        anomaly_z_thresh=3.8,
        winsor_cap=1.8,
        fast_thresh=fast_thresh,
        hold_steps=hold_steps,
        resolution_horizon=14,
        return_to_baseline_z=1.5,
        persistence_z_thresh=1.45,
        correlation_method="pearson",
        innovation_drain=True,
        persistence_floor=True,
        heuristic_scale_guard=False,
    )


def make_baseline() -> SurgicalFactorEngineB61:
    """Exact B-v6.1 D1_P1_G0 reference with its fixed 85.0 threshold."""
    return SurgicalFactorEngineB61(
        quiet_end=40,
        window_size=12,
        anomaly_z_thresh=3.8,
        winsor_cap=1.8,
        break_percent_thresh=85.0,
        resolution_horizon=14,
        return_to_baseline_z=1.5,
        persistence_z_thresh=1.45,
        correlation_method="pearson",
        innovation_drain=True,
        persistence_floor=True,
        heuristic_scale_guard=False,
    )


def make_instrumentation() -> dict[str, int]:
    return {key: 0 for key in INSTRUMENTATION_KEYS}


def evaluate_stage(
    seed_base: int,
    engines: dict[str, Any],
    trials: int,
    stage_name: str,
) -> dict[str, Any]:
    counts: dict[str, dict[str, dict[str, Any]]] = {
        name: {
            case[0]: {**empty_counts(), "instrumentation": make_instrumentation()}
            for case in CASES
        }
        for name in engines
    }

    for case_index, (case_name, distribution, rho, variance_jump, shift) in enumerate(CASES):
        for trial_index in range(trials):
            seed = seed_base + case_index * 10_000 + trial_index
            series = generate_series(
                np.random.default_rng(seed),
                dist=distribution,
                rho=rho,
                var_jump=variance_jump,
                shift_sigma=shift,
                n=N,
                onset=ONSET,
            )
            for name, engine in engines.items():
                result = engine.analyze(series)
                bucket = counts[name][case_name]
                add_measurement(bucket, classify(result, shift))
                diagnostics = result.get("diagnostics", {})
                for key in INSTRUMENTATION_KEYS:
                    bucket["instrumentation"][key] += int(diagnostics.get(key, 0))

    summaries: dict[str, Any] = {}
    for name in engines:
        case_rows: dict[str, Any] = {}
        for case_name, distribution, rho, variance_jump, shift in CASES:
            bucket = counts[name][case_name]
            row = summarize_case(shift, variance_jump, bucket, trials)
            events = bucket["events"]
            lifecycle_equation = (
                events["pending_opened"]
                == events["pending_resolved_structural"]
                + events["pending_resolved_transient"]
                + events["pending_unresolved"]
            )
            row["pending_lifecycle"] = {
                "pending_opened": events["pending_opened"],
                "pending_resolved_structural": events["pending_resolved_structural"],
                "pending_resolved_transient": events["pending_resolved_transient"],
                "pending_unresolved": events["pending_unresolved"],
                "accounting_complete": bool(bucket["lifecycle_ok"]),
                "equation_holds": bool(lifecycle_equation),
            }
            row["instrumentation"] = bucket["instrumentation"]
            case_rows[case_name] = row

        nonlevel = [
            row for row in case_rows.values()
            if row["scenario_type"] in ("pure_null", "variance_jump")
        ]
        pure_nulls = [
            row for row in case_rows.values() if row["scenario_type"] == "pure_null"
        ]
        shifts = [
            row for row in case_rows.values() if row["scenario_type"] == "level_shift"
        ]
        worst_structural = max(row["structural_rate"]["rate_pct"] for row in nonlevel)
        worst_transient = max(row["transient_alert_rate"]["rate_pct"] for row in nonlevel)
        worst_combined_nonlevel = max(
            row["combined_any_alert_rate"]["rate_pct"] for row in nonlevel
        )
        worst_combined_pure_null = max(
            row["combined_any_alert_rate"]["rate_pct"] for row in pure_nulls
        )
        worst_pre_onset = max(
            row["pre_onset_combined_rate"]["rate_pct"] for row in shifts
        )
        sensitivity = round(
            statistics.mean(row["structural_rate"]["rate_pct"] for row in shifts), 2
        )
        pooled_delays = [
            int(delay)
            for case_name, _, _, _, shift in CASES
            if shift != 0.0
            for delay in counts[name][case_name]["delays"]
        ]
        median_delay = (
            round(float(statistics.median(pooled_delays)), 2)
            if pooled_delays else None
        )
        lifecycle_ok = all(
            row["pending_lifecycle_accounting_complete"]
            and row["pending_lifecycle"]["equation_holds"]
            for row in case_rows.values()
        )
        point_gates = {
            "structural_fpr_all_nonlevel_le_5": worst_structural <= FPR_LIMIT,
            "transient_fpr_all_nonlevel_le_5": worst_transient <= FPR_LIMIT,
            "combined_fpr_all_pure_null_le_5": worst_combined_pure_null <= FPR_LIMIT,
            "pre_onset_combined_all_shifts_le_5": worst_pre_onset <= FPR_LIMIT,
            "mean_directional_sensitivity_ge_93": sensitivity >= SENSITIVITY_TARGET,
            "lifecycle_accounting": lifecycle_ok,
        }
        summaries[name] = {
            "cases": case_rows,
            "worst_structural_fpr_nonlevel_pct": worst_structural,
            "worst_transient_fpr_nonlevel_pct": worst_transient,
            "worst_combined_fpr_nonlevel_pct": worst_combined_nonlevel,
            "worst_combined_fpr_pure_null_pct": worst_combined_pure_null,
            "worst_pre_onset_combined_pct": worst_pre_onset,
            "mean_directional_sensitivity_pct": sensitivity,
            "median_correct_detection_delay": median_delay,
            "lifecycle_accounting_complete": lifecycle_ok,
            "point_gates": point_gates,
            "event_totals": {
                key: sum(bucket["events"][key] for bucket in counts[name].values())
                for key in EVENT_KEYS
            },
        }

    return {
        "stage": stage_name,
        "seed_base": seed_base,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "generated_series_count": len(CASES) * trials,
        "configuration_count": len(engines),
        "configuration_evaluations": len(CASES) * trials * len(engines),
        "same_generated_series_for_all_configurations": True,
        "models": summaries,
    }


def fpr_gate_failures(summary: dict[str, Any]) -> int:
    keys = (
        "structural_fpr_all_nonlevel_le_5",
        "transient_fpr_all_nonlevel_le_5",
        "combined_fpr_all_pure_null_le_5",
        "pre_onset_combined_all_shifts_le_5",
    )
    return sum(not bool(summary["point_gates"][key]) for key in keys)


def fpr_excess(summary: dict[str, Any]) -> float:
    keys = (
        "worst_structural_fpr_nonlevel_pct",
        "worst_transient_fpr_nonlevel_pct",
        "worst_combined_fpr_pure_null_pct",
        "worst_pre_onset_combined_pct",
    )
    return sum(max(0.0, float(summary[key]) - FPR_LIMIT) for key in keys)


def select_development_configuration(development: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    for name in CONFIG_NAMES:
        summary = development["models"][name]
        eligible = (
            fpr_gate_failures(summary) == 0
            and summary["point_gates"]["mean_directional_sensitivity_ge_93"]
            and summary["point_gates"]["lifecycle_accounting"]
        )
        scores[name] = {
            "eligible": bool(eligible),
            "fpr_gate_failures": fpr_gate_failures(summary),
            "sum_fpr_excess_percentage_points": round(fpr_excess(summary), 4),
            "mean_directional_sensitivity_pct": summary["mean_directional_sensitivity_pct"],
            "median_correct_detection_delay": summary["median_correct_detection_delay"],
            "fast_thresh": config_values(name)[0],
            "hold_steps": config_values(name)[1],
            "point_gates": summary["point_gates"],
        }

    eligible_names = [name for name, item in scores.items() if item["eligible"]]
    def delay_or_inf(name: str) -> float:
        value = scores[name]["median_correct_detection_delay"]
        return float(value) if value is not None else float("inf")

    if eligible_names:
        selected = sorted(
            eligible_names,
            key=lambda name: (
                -scores[name]["mean_directional_sensitivity_pct"],
                delay_or_inf(name),
                -scores[name]["fast_thresh"],
                -scores[name]["hold_steps"],
                name,
            ),
        )[0]
        mode = "eligible_highest_sensitivity_then_lower_median_delay_then_more_conservative"
    else:
        selected = sorted(
            CONFIG_NAMES,
            key=lambda name: (
                scores[name]["fpr_gate_failures"],
                scores[name]["sum_fpr_excess_percentage_points"],
                -scores[name]["mean_directional_sensitivity_pct"],
                delay_or_inf(name),
                -scores[name]["fast_thresh"],
                -scores[name]["hold_steps"],
                name,
            ),
        )[0]
        mode = "best_effort_no_configuration_met_all_development_gates"

    return {
        "selected_configuration": selected,
        "selection_mode": mode,
        "development_all_gates_met": bool(scores[selected]["eligible"]),
        "eligible_configurations": eligible_names,
        "configuration_scores": scores,
        "rule": (
            "Require all four development FPR point-estimate ceilings <=5% "
            "(structural and transient across six nonlevel cases, Combined across four "
            "pure-null cases, pre-onset Combined across both level shifts), mean "
            "directional sensitivity >=93%, and exact PENDING lifecycle accounting. "
            "If eligible, maximize sensitivity, then minimize pooled median correct-"
            "detection delay, then prefer the higher fast threshold and longer hold. "
            "If none is eligible, minimize failed FPR ceilings, then total percentage-"
            "point excess above 5, maximize sensitivity, minimize delay, then prefer "
            "the more conservative parameters. No holdout metric participates."
        ),
        "holdout_used_for_selection": False,
    }


def confidence_gates(summary: dict[str, Any]) -> dict[str, bool]:
    rows = summary["cases"]
    nonlevel = [
        row for row in rows.values()
        if row["scenario_type"] in ("pure_null", "variance_jump")
    ]
    pure_nulls = [
        row for row in rows.values() if row["scenario_type"] == "pure_null"
    ]
    shifts = [
        row for row in rows.values() if row["scenario_type"] == "level_shift"
    ]
    return {
        "structural_wilson_upper95_all_nonlevel_le_5": all(
            row["structural_rate"]["wilson95_pct"][1] <= FPR_LIMIT for row in nonlevel
        ),
        "transient_wilson_upper95_all_nonlevel_le_5": all(
            row["transient_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT for row in nonlevel
        ),
        "combined_wilson_upper95_all_pure_null_le_5": all(
            row["combined_any_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in pure_nulls
        ),
        "pre_onset_combined_wilson_upper95_all_shifts_le_5": all(
            row["pre_onset_combined_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in shifts
        ),
        "mean_directional_sensitivity_ge_93": (
            summary["mean_directional_sensitivity_pct"] >= SENSITIVITY_TARGET
        ),
        "lifecycle_accounting": summary["lifecycle_accounting_complete"],
    }


def print_summary(stage: str, summary: dict[str, Any]) -> None:
    print(f"\n=== {stage} AGGREGATES ===", flush=True)
    print(
        "configuration | worst Structural FPR | worst Transient FPR | "
        "worst Combined pure-null FPR | worst Pre-onset | Sensitivity | "
        "Median delay | Lifecycle"
    )
    for name, model in summary["models"].items():
        print(
            f"{name} | {model['worst_structural_fpr_nonlevel_pct']:.2f}% | "
            f"{model['worst_transient_fpr_nonlevel_pct']:.2f}% | "
            f"{model['worst_combined_fpr_pure_null_pct']:.2f}% | "
            f"{model['worst_pre_onset_combined_pct']:.2f}% | "
            f"{model['mean_directional_sensitivity_pct']:.2f}% | "
            f"{model['median_correct_detection_delay']} | "
            f"{model['lifecycle_accounting_complete']}",
            flush=True,
        )
        print(
            "case | type | Structural/sensitivity | Transient | Combined | "
            "Pre-onset | Median delay | PENDING equation",
            flush=True,
        )
        for case_name, row in model["cases"].items():
            print(
                f"{case_name} | {row['scenario_type']} | "
                f"{row['structural_rate']['rate_pct']:.2f}% | "
                f"{row['transient_alert_rate']['rate_pct']:.2f}% | "
                f"{row['combined_any_alert_rate']['rate_pct']:.2f}% | "
                f"{row['pre_onset_combined_rate']['rate_pct']:.2f}% | "
                f"{row['median_correct_detection_delay']} | "
                f"{row['pending_lifecycle']['equation_holds']}",
                flush=True,
            )


def run(
    dev_trials: int = TRIALS_PER_CASE,
    holdout_trials: int = TRIALS_PER_CASE,
    dev_seed_base: int = DEV_SEED_BASE,
    holdout_seed_base: int = HOLDOUT_SEED_BASE,
    output: Path = OUTPUT,
    official: bool = True,
) -> dict[str, Any]:
    if dev_trials < 1 or holdout_trials < 1:
        raise ValueError("trial_counts_must_be_positive")
    if official and (
        dev_trials != TRIALS_PER_CASE
        or holdout_trials != TRIALS_PER_CASE
        or dev_seed_base != DEV_SEED_BASE
        or holdout_seed_base != HOLDOUT_SEED_BASE
    ):
        raise ValueError("official_B63_requires_exact_500_trials_and_20M_21M_seed_bases")
    if N != 140 or ONSET != 65:
        raise AssertionError(f"benchmark_generator_contract_mismatch:N={N},ONSET={ONSET}")

    started = time.perf_counter()
    development_engines = {name: make_candidate(name) for name in CONFIG_NAMES}
    development = evaluate_stage(
        dev_seed_base, development_engines, dev_trials, "development_four_configurations"
    )
    development_elapsed = round(time.perf_counter() - started, 2)
    selection = select_development_configuration(development)
    selected = selection["selected_configuration"]

    # Only after selection is frozen does the 21M holdout run.
    holdout_engines = {
        BASELINE: make_baseline(),
        selected: make_candidate(selected),
    }
    started = time.perf_counter()
    holdout = evaluate_stage(
        holdout_seed_base, holdout_engines, holdout_trials, "paired_pristine_holdout"
    )
    holdout_elapsed = round(time.perf_counter() - started, 2)

    dev_ranges = seed_ranges(dev_seed_base, dev_trials)
    holdout_ranges = seed_ranges(holdout_seed_base, holdout_trials)
    seeds_disjoint = seed_blocks_disjoint(dev_ranges, holdout_ranges)
    if not seeds_disjoint:
        raise AssertionError("development_and_holdout_seed_blocks_overlap")

    for stage_name, stage in (("development", development), ("holdout", holdout)):
        for model_name, model in stage["models"].items():
            for case_name, row in model["cases"].items():
                life = row["pending_lifecycle"]
                if not life["equation_holds"] or not life["accounting_complete"]:
                    raise AssertionError(
                        f"pending_lifecycle_accounting_failed:{stage_name}:{model_name}:{case_name}"
                    )

    holdout_gates = {
        name: confidence_gates(summary)
        for name, summary in holdout["models"].items()
    }
    holdout_final_gates = {
        name: all(gates.values()) for name, gates in holdout_gates.items()
    }

    report = {
        "experiment": "B-v6.3 Dual-Tier Structural Confirmation on B-v6.1 D1_P1_G0",
        "candidate_branch": "experiment/b6-3-dual-tier-confirmation",
        "base_commit": "1f3f369f9c0b67344954d288c99d923d5b9b5c22",
        "base_configuration": {
            "name": "D1_P1_G0",
            "rho": "raw Pearson lag-1 clipped [0.0,0.88]",
            "scale_guard": False,
            "sign_flip_guard": False,
            "D": "first raw point abs(z)>3.8; next two normalized innovations abs(u)>2.8 and same sign",
            "D_scope": "transient PENDING channel only; structural scan independent",
            "P": "dominant_persistence >=0.75; persistence_z=1.45; winsor_cap=1.8",
        },
        "dual_tier_specification": {
            "fast_path": "break_pct >= fast_thresh AND dominant_persistence >= 0.75; announce at current t",
            "confirmed_path": "83.0 <= break_pct < fast_thresh AND dominant_persistence >= 0.75 in the same direction for hold_steps additional consecutive steps; announce at completion t",
            "direction_flip": "reset and reject active candidate on flip step; the flip sample does not also seed an opposite candidate",
            "invalid_candidate": "break_pct <83.0 or dominant_persistence <0.75 resets the counter without an alert",
            "latch": "latch at announcement; reset only when abs(window_shift_z) <0.40",
            "hold_steps_semantics": "initial borderline sample starts at counter zero; only subsequent qualifying samples increment",
        },
        "fixed_specification": {
            "quiet_end": 40,
            "window_size": 12,
            "series_length": 140,
            "onset_index_zero_based": 65,
            "winsor_cap": 1.8,
            "persistence_z_threshold": 1.45,
            "persistence_floor": 0.75,
            "anomaly_z_thresh": 3.8,
            "borderline_floor": 83.0,
            "resolution_horizon": 14,
            "return_to_baseline_z": 1.5,
            "rho_method": "raw Pearson lag-1 clipped [0.0,0.88], no inflation",
            "combined_definition": "union of structural, transient and unresolved alerts",
            "pending_lifecycle_equation": "pending_opened == pending_resolved_structural + pending_resolved_transient + pending_unresolved",
        },
        "design": {
            "cases": [case[0] for case in CASES],
            "case_count": len(CASES),
            "trials_per_case_development": dev_trials,
            "trials_per_case_holdout": holdout_trials,
            "development_seed_base": dev_seed_base,
            "holdout_seed_base": holdout_seed_base,
            "seed_scheme": "seed_base + case_index*10000 + trial_index",
            "development_seed_ranges": dev_ranges,
            "holdout_seed_ranges": holdout_ranges,
            "seed_blocks_disjoint": seeds_disjoint,
            "development_generated_series": development["generated_series_count"],
            "development_configuration_evaluations": development["configuration_evaluations"],
            "holdout_generated_series": holdout["generated_series_count"],
            "holdout_configuration_evaluations": holdout["configuration_evaluations"],
            "same_generated_series_within_each_stage": True,
            "development_configurations": [
                {
                    "name": name,
                    "fast_thresh": config_values(name)[0],
                    "hold_steps": config_values(name)[1],
                }
                for name in CONFIG_NAMES
            ],
            "holdout_configurations": [BASELINE, selected],
            "development_selection_uses_20m_only": True,
            "21m_contains_only_D1_P1_G0_reference_and_one_selected_candidate": True,
            "false_alarm_budget_pct": FPR_LIMIT,
            "mean_directional_sensitivity_target_pct": SENSITIVITY_TARGET,
            "wilson_confidence_level_pct": 95.0,
        },
        "development_elapsed_seconds": development_elapsed,
        "development_four_configurations": development,
        "development_selection": selection,
        "holdout_elapsed_seconds": holdout_elapsed,
        "paired_21m_holdout": holdout,
        "holdout_confidence_gates": holdout_gates,
        "holdout_final_gates": holdout_final_gates,
        "holdout_approval": bool(holdout_final_gates.get(selected, False)),
        "selected_candidate": selected,
        "baseline_reference": BASELINE,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary("20M DEVELOPMENT", development)
    print(
        f"\nselected={selected}; mode={selection['selection_mode']}; "
        f"all_development_gates_met={selection['development_all_gates_met']}",
        flush=True,
    )
    print_summary("21M PAIRED HOLDOUT", holdout)
    print("\n=== 21M WILSON 95% GATES ===", flush=True)
    for name, gates in holdout_gates.items():
        print(f"{name}: {gates}; final_pass={holdout_final_gates[name]}", flush=True)
    print(f"\nreport={output}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run(
            dev_trials=12,
            holdout_trials=12,
            dev_seed_base=1_320_000,
            holdout_seed_base=2_320_000,
            output=Path("/tmp/b63_smoke_report.json"),
            official=False,
        )
    else:
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
