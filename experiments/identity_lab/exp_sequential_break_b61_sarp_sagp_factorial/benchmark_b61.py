"""B-v6.1 2x2x2 factorial experiment: development 12M, paired validation 13M."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    N,
    ONSET,
    generate_series,
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES,
    add_measurement,
    classify,
    empty_counts,
    rate,
    seed_blocks_disjoint,
    seed_ranges,
    summarize_case,
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import (
    PearsonSpearmanFixedGateEngineB6,
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import (
    SurgicalFactorEngineB61,
)

DEV_SEED_BASE = 12_000_000
HOLDOUT_SEED_BASE = 13_000_000
TRIALS_PER_CASE = 500
FPR_LIMIT = 5.0
SENSITIVITY_TARGET = 93.0
OUTPUT = (
    Path(__file__).resolve().parent
    / "results"
    / "sequential_break_engine_b61_sarp_sagp_factorial_12m_13m.json"
)

FACTORIAL_CONFIGS = tuple(
    f"D{drain}_P{persist}_G{guard}"
    for drain in (0, 1)
    for persist in (0, 1)
    for guard in (0, 1)
)
HOLDOUT_REFERENCE = "B6a_frozen_reference"


def parse_config(name: str) -> tuple[bool, bool, bool]:
    if len(name) != 8 or name[0] != "D" or name[2:4] != "_P" or name[5:7] != "_G":
        raise ValueError(f"invalid_factorial_config:{name}")
    if name[1] not in "01" or name[4] not in "01" or name[7] not in "01":
        raise ValueError(f"invalid_factorial_config:{name}")
    return name[1] == "1", name[4] == "1", name[7] == "1"


def active_factor_count(name: str) -> int:
    return sum(parse_config(name))


def make_engine(config_name: str):
    if config_name == HOLDOUT_REFERENCE:
        return PearsonSpearmanFixedGateEngineB6(
            quiet_end=40,
            window_size=12,
            anomaly_z_thresh=3.8,
            winsor_cap=1.8,
            break_percent_thresh=85.0,
            resolution_horizon=14,
            return_to_baseline_z=1.5,
            persistence_z_thresh=1.45,
            correlation_method="pearson",
        )
    drain, persist, guard = parse_config(config_name)
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
        innovation_drain=drain,
        persistence_floor=persist,
        heuristic_scale_guard=guard,
    )


def empty_instrumentation() -> dict[str, int]:
    return {
        "pending_gate_opportunities": 0,
        "innovation_gate_rejections": 0,
        "structural_threshold_candidates": 0,
        "persistence_floor_rejections": 0,
    }


def evaluate_stage(
    seed_base: int,
    config_names: tuple[str, ...],
    trials: int,
    stage_name: str,
) -> dict[str, Any]:
    engines = {name: make_engine(name) for name in config_names}
    counts: dict[str, dict[str, dict[str, Any]]] = {
        config: {
            case[0]: {
                **empty_counts(),
                "instrumentation": empty_instrumentation(),
            }
            for case in CASES
        }
        for config in config_names
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
            for config_name, engine in engines.items():
                result = engine.analyze(series)
                bucket = counts[config_name][case_name]
                add_measurement(bucket, classify(result, shift))
                diagnostics = result.get("diagnostics", {})
                for key in bucket["instrumentation"]:
                    bucket["instrumentation"][key] += int(diagnostics.get(key, 0))

    summaries = {}
    for config_name in config_names:
        case_rows = {}
        for case_name, distribution, rho, variance_jump, shift in CASES:
            bucket = counts[config_name][case_name]
            row = summarize_case(shift, variance_jump, bucket, trials)
            row["instrumentation"] = bucket["instrumentation"]
            case_rows[case_name] = row

        nonlevel = [
            row for row in case_rows.values()
            if row["scenario_type"] in ("pure_null", "variance_jump")
        ]
        pure_null = [
            row for row in case_rows.values()
            if row["scenario_type"] == "pure_null"
        ]
        shifts = [
            row for row in case_rows.values()
            if row["scenario_type"] == "level_shift"
        ]
        worst_structural = max(
            row["structural_rate"]["rate_pct"] for row in nonlevel
        )
        worst_transient = max(
            row["transient_alert_rate"]["rate_pct"] for row in nonlevel
        )
        worst_combined = max(
            row["combined_any_alert_rate"]["rate_pct"] for row in pure_null
        )
        worst_pre_onset = max(
            row["pre_onset_combined_rate"]["rate_pct"] for row in shifts
        )
        sensitivity = round(
            statistics.mean(row["structural_rate"]["rate_pct"] for row in shifts), 2
        )
        lifecycle_ok = all(
            row["pending_lifecycle_accounting_complete"] for row in case_rows.values()
        )
        point_gates = {
            "structural_fpr_all_nonlevel_le_5": worst_structural <= FPR_LIMIT,
            "transient_fpr_all_nonlevel_le_5": worst_transient <= FPR_LIMIT,
            "combined_fpr_all_pure_null_le_5": worst_combined <= FPR_LIMIT,
            "pre_onset_combined_all_shifts_le_5": worst_pre_onset <= FPR_LIMIT,
            "mean_directional_sensitivity_ge_93": sensitivity >= SENSITIVITY_TARGET,
            "lifecycle_accounting": lifecycle_ok,
        }
        summaries[config_name] = {
            "cases": case_rows,
            "worst_structural_fpr_nonlevel_pct": worst_structural,
            "worst_transient_fpr_nonlevel_pct": worst_transient,
            "worst_combined_fpr_pure_null_pct": worst_combined,
            "worst_pre_onset_combined_pct": worst_pre_onset,
            "mean_directional_sensitivity_pct": sensitivity,
            "lifecycle_accounting_complete": lifecycle_ok,
            "point_gates": point_gates,
        }

    return {
        "stage": stage_name,
        "seed_base": seed_base,
        "trials_per_case": trials,
        "case_count": len(CASES),
        "generated_series_count": len(CASES) * trials,
        "configuration_count": len(config_names),
        "configuration_evaluations": len(CASES) * trials * len(config_names),
        "same_generated_series_for_all_configurations": True,
        "models": summaries,
    }


FPR_GATE_KEYS = (
    "structural_fpr_all_nonlevel_le_5",
    "transient_fpr_all_nonlevel_le_5",
    "combined_fpr_all_pure_null_le_5",
    "pre_onset_combined_all_shifts_le_5",
)
FPR_METRIC_KEYS = (
    "worst_structural_fpr_nonlevel_pct",
    "worst_transient_fpr_nonlevel_pct",
    "worst_combined_fpr_pure_null_pct",
    "worst_pre_onset_combined_pct",
)


def select_development_configuration(development: dict[str, Any]) -> dict[str, Any]:
    scores = {}
    for name in FACTORIAL_CONFIGS:
        summary = development["models"][name]
        gate_failures = sum(
            not bool(summary["point_gates"][key]) for key in FPR_GATE_KEYS
        )
        metric_excess = sum(
            max(0.0, float(summary[key]) - FPR_LIMIT)
            for key in FPR_METRIC_KEYS
        )
        eligible = (
            gate_failures == 0
            and summary["point_gates"]["mean_directional_sensitivity_ge_93"]
            and summary["point_gates"]["lifecycle_accounting"]
        )
        scores[name] = {
            "eligible": bool(eligible),
            "fpr_gate_failures": int(gate_failures),
            "sum_fpr_excess_percentage_points": round(metric_excess, 4),
            "mean_directional_sensitivity_pct": summary["mean_directional_sensitivity_pct"],
            "active_factor_count": active_factor_count(name),
            "point_gates": summary["point_gates"],
            "metrics": {key: summary[key] for key in FPR_METRIC_KEYS},
        }

    eligible_names = [name for name, item in scores.items() if item["eligible"]]
    if eligible_names:
        selected = sorted(
            eligible_names,
            key=lambda name: (
                -scores[name]["mean_directional_sensitivity_pct"],
                scores[name]["active_factor_count"],
                name,
            ),
        )[0]
        mode = "eligible_highest_sensitivity_then_fewest_factors"
    else:
        selected = sorted(
            FACTORIAL_CONFIGS,
            key=lambda name: (
                scores[name]["fpr_gate_failures"],
                scores[name]["sum_fpr_excess_percentage_points"],
                -scores[name]["mean_directional_sensitivity_pct"],
                scores[name]["active_factor_count"],
                name,
            ),
        )[0]
        mode = "best_effort_no_factorial_configuration_met_all_development_gates"

    return {
        "selected_configuration": selected,
        "selection_mode": mode,
        "development_all_gates_met": bool(scores[selected]["eligible"]),
        "eligible_configurations": eligible_names,
        "configuration_scores": scores,
        "rule": (
            "Eligibility requires all four development FPR point-estimate ceilings "
            "(structural nonlevel, transient nonlevel, Combined pure-null, pre-onset "
            "Combined shifts) <=5%, mean directional sensitivity >=93%, and exact "
            "lifecycle accounting. If eligible, maximize sensitivity, then prefer fewer "
            "active factors. Otherwise minimize failed FPR ceilings, sum of FPR excess "
            "above 5, maximize sensitivity, then prefer fewer factors. Lexical tie-break."
        ),
        "holdout_used_for_selection": False,
    }


def marginal_factor_effects(development: dict[str, Any]) -> dict[str, Any]:
    metrics = FPR_METRIC_KEYS + ("mean_directional_sensitivity_pct",)
    effects = {}
    for factor, index in (("innovation_drain_D", 1), ("persistence_floor_P", 4), ("heuristic_scale_guard_G", 7)):
        off = [name for name in FACTORIAL_CONFIGS if name[index] == "0"]
        on = [name for name in FACTORIAL_CONFIGS if name[index] == "1"]
        effects[factor] = {}
        for metric in metrics:
            mean_off = statistics.mean(development["models"][name][metric] for name in off)
            mean_on = statistics.mean(development["models"][name][metric] for name in on)
            effects[factor][metric] = {
                "mean_factor_off": round(float(mean_off), 4),
                "mean_factor_on": round(float(mean_on), 4),
                "on_minus_off_percentage_points": round(float(mean_on - mean_off), 4),
            }
    return effects


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
            row["structural_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in nonlevel
        ),
        "transient_wilson_upper95_all_nonlevel_le_5": all(
            row["transient_alert_rate"]["wilson95_pct"][1] <= FPR_LIMIT
            for row in nonlevel
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
        "configuration | structural FPR | transient FPR | pure-null Combined | "
        "pre-onset Combined | sensitivity | lifecycle"
    )
    for name, model in summary["models"].items():
        print(
            f"{name} | {model['worst_structural_fpr_nonlevel_pct']:.2f}% | "
            f"{model['worst_transient_fpr_nonlevel_pct']:.2f}% | "
            f"{model['worst_combined_fpr_pure_null_pct']:.2f}% | "
            f"{model['worst_pre_onset_combined_pct']:.2f}% | "
            f"{model['mean_directional_sensitivity_pct']:.2f}% | "
            f"{model['lifecycle_accounting_complete']}",
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
        raise ValueError("official_B61_requires_exact_500_trials_and_12M_13M_seed_bases")
    if N != 140 or ONSET != 65:
        raise AssertionError(f"benchmark_generator_contract_mismatch:N={N},ONSET={ONSET}")

    started = time.perf_counter()
    development = evaluate_stage(
        dev_seed_base, FACTORIAL_CONFIGS, dev_trials, "development_factorial"
    )
    development_elapsed = round(time.perf_counter() - started, 2)
    selection = select_development_configuration(development)
    selected = selection["selected_configuration"]

    # Only the frozen reference and the single selected B-v6.1 candidate see 13M.
    holdout_configs = (HOLDOUT_REFERENCE, selected)
    started = time.perf_counter()
    holdout = evaluate_stage(
        holdout_seed_base, holdout_configs, holdout_trials, "paired_pristine_validation"
    )
    holdout_elapsed = round(time.perf_counter() - started, 2)

    dev_ranges = seed_ranges(dev_seed_base, dev_trials)
    holdout_ranges = seed_ranges(holdout_seed_base, holdout_trials)
    seeds_disjoint = seed_blocks_disjoint(dev_ranges, holdout_ranges)
    if not seeds_disjoint:
        raise AssertionError("development_and_holdout_seed_blocks_overlap")

    holdout_gates = {
        config: confidence_gates(summary)
        for config, summary in holdout["models"].items()
    }
    holdout_final_gates = {
        config: all(gates.values()) for config, gates in holdout_gates.items()
    }
    report = {
        "experiment": "B-v6.1 Surgical SARP-SAGP Factorial on Frozen B-v6a Pearson",
        "candidate_branch": "experiment/b6-1-sarp-sagp-factorial",
        "parent_B6_commit": "97220248dea1f359c366540a58d245461556c21e",
        "frozen_reference": "B-v6a Pearson, original 85.0 threshold, no factor changes",
        "factor_specification": {
            "D_innovation_drain": {
                "enabled_condition": "first raw point abs(z)>3.8; next two normalized innovations each abs(u)>2.8 and same sign as first",
                "normalization": "sqrt(max(1-rho^2,0.15))",
                "scope": "transient PENDING channel only; structural scan is independent",
            },
            "P_non_compensatory_persistence": {
                "enabled_condition": "dominant_persistence >= 0.75 as an independent AND gate",
                "definition": "max(full_pos,full_neg), same B-v6 threshold 1.45 and 12-point window",
            },
            "G_heuristic_scale_guard": {
                "enabled_condition": "context_scale *= (1 + 0.25*rho)",
                "classification": "heuristic scale guard; not a sample-uncertainty estimator",
            },
        },
        "fixed_specification": {
            "quiet_end": 40,
            "window_size": 12,
            "series_length": 140,
            "onset_index_zero_based": 65,
            "winsor_cap": 1.8,
            "persistence_z_threshold": 1.45,
            "anomaly_z_thresh": 3.8,
            "break_percent_thresh": 85.0,
            "rho_method": "raw Pearson lag-1, clipped [0.0,0.88], no upward correction",
            "resolution_horizon": 14,
            "return_to_baseline_z": 1.5,
            "lifecycle_invariant": "opened == resolved_structural + resolved_transient + unresolved",
            "combined_definition": "union of structural, transient and unresolved alerts",
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
            "factorial_configurations": list(FACTORIAL_CONFIGS),
            "holdout_configurations": list(holdout_configs),
            "development_selection_uses_12m_only": True,
            "13m_contains_only_frozen_reference_and_one_selected_candidate": True,
            "false_alarm_budget_pct": FPR_LIMIT,
            "mean_directional_sensitivity_target_pct": SENSITIVITY_TARGET,
            "wilson_confidence_level_pct": 95.0,
        },
        "development_factorial": development,
        "development_elapsed_seconds": development_elapsed,
        "development_selection": selection,
        "development_marginal_factor_effects": marginal_factor_effects(development),
        "pristine_13m_validation": holdout,
        "holdout_elapsed_seconds": holdout_elapsed,
        "holdout_confidence_gates": holdout_gates,
        "holdout_final_gates": holdout_final_gates,
        "holdout_approval": all(holdout_final_gates.values()),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_summary("12M DEVELOPMENT FACTORIAL", development)
    print(
        f"\nselected={selected}; mode={selection['selection_mode']}; "
        f"all_development_gates_met={selection['development_all_gates_met']}",
        flush=True,
    )
    print_summary("13M PAIRED VALIDATION", holdout)
    print("\n=== 13M WILSON 95% GATES ===", flush=True)
    for name, gates in holdout_gates.items():
        print(f"{name}: {gates}; final_pass={holdout_final_gates[name]}", flush=True)
    print(f"report={output}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trials", type=int, default=TRIALS_PER_CASE)
    parser.add_argument("--holdout-trials", type=int, default=TRIALS_PER_CASE)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run(
            dev_trials=12,
            holdout_trials=12,
            dev_seed_base=1_200_000,
            holdout_seed_base=2_200_000,
            output=Path("/tmp/b61_smoke_report.json"),
            official=False,
        )
    else:
        run(
            dev_trials=args.dev_trials,
            holdout_trials=args.holdout_trials,
            official=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
