"""B-v6.2 targeted test: D1/P1 with conditional sign-flip guard, 18M/19M."""
from __future__ import annotations
import argparse, json, statistics, time
from pathlib import Path
from typing import Any
import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import N, ONSET, generate_series
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES, add_measurement, classify, empty_counts, seed_blocks_disjoint, seed_ranges, summarize_case
)
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.engine_b6 import PearsonSpearmanFixedGateEngineB6
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import SurgicalFactorEngineB61
from experiments.identity_lab.exp_sequential_break_b62_sign_flip_guard.engine_b62 import DriftConditionalSignFlipEngineB62

DEV_SEED_BASE, HOLDOUT_SEED_BASE = 18_000_000, 19_000_000
TRIALS_PER_CASE, FPR_LIMIT, SENSITIVITY_TARGET, SIGN_FLIP_THRESHOLD = 500, 5.0, 93.0, 8
OUTPUT = Path(__file__).resolve().parent / "results" / "sequential_break_engine_b62_sign_flip_guard_18m_19m.json"
B6A, G0, SF8 = "B6a_frozen_reference", "D1_P1_G0", "D1_P1_SF8"
DEV_CONFIGS, HOLDOUT_CONFIGS = (G0, SF8), (B6A, G0, SF8)

def make_engine(name: str):
    common = dict(quiet_end=40, window_size=12, anomaly_z_thresh=3.8, winsor_cap=1.8,
                  break_percent_thresh=85.0, resolution_horizon=14,
                  return_to_baseline_z=1.5, persistence_z_thresh=1.45,
                  correlation_method="pearson")
    if name == B6A:
        return PearsonSpearmanFixedGateEngineB6(**common)
    if name == G0:
        return SurgicalFactorEngineB61(**common, innovation_drain=True,
                                       persistence_floor=True, heuristic_scale_guard=False)
    if name == SF8:
        return DriftConditionalSignFlipEngineB62(**common, innovation_drain=True,
                 persistence_floor=True, sign_flip_guard=True,
                 sign_flip_threshold=SIGN_FLIP_THRESHOLD)
    raise ValueError("unknown_configuration:" + name)

def empty_inst():
    return {k: 0 for k in ("pending_gate_opportunities","innovation_gate_rejections",
        "structural_threshold_candidates","persistence_floor_rejections",
        "sign_flip_windows_evaluated","sign_flip_guard_active_windows","sign_flip_total_count")}

def evaluate(seed_base: int, configs: tuple[str,...], trials: int, stage: str) -> dict[str,Any]:
    engines = {n: make_engine(n) for n in configs}
    counts = {c:{case[0]:{**empty_counts(),"instrumentation":empty_inst()} for case in CASES} for c in configs}
    for ci,(case,dist,rho,vjump,shift) in enumerate(CASES):
        for ti in range(trials):
            seq = generate_series(np.random.default_rng(seed_base+ci*10000+ti),
                                  dist=dist,rho=rho,var_jump=vjump,shift_sigma=shift,n=N,onset=ONSET)
            for name,engine in engines.items():
                result=engine.analyze(seq)
                bucket=counts[name][case]
                add_measurement(bucket,classify(result,shift))
                diag=result.get("diagnostics",{})
                for key in bucket["instrumentation"]:
                    bucket["instrumentation"][key]+=int(diag.get(key,0))
    models={}
    for name in configs:
        rows={}
        for case,dist,rho,vjump,shift in CASES:
            b=counts[name][case]
            row=summarize_case(shift,vjump,b,trials)
            ins=b["instrumentation"]
            row["instrumentation"]={**ins,
                "sign_flip_guard_activation_pct":round(100*ins["sign_flip_guard_active_windows"]/max(ins["sign_flip_windows_evaluated"],1),4),
                "mean_sign_flip_count":round(ins["sign_flip_total_count"]/max(ins["sign_flip_windows_evaluated"],1),4)}
            rows[case]=row
        nonlevel=[r for r in rows.values() if r["scenario_type"] in ("pure_null","variance_jump")]
        nulls=[r for r in rows.values() if r["scenario_type"]=="pure_null"]
        shifts=[r for r in rows.values() if r["scenario_type"]=="level_shift"]
        ws=max(r["structural_rate"]["rate_pct"] for r in nonlevel)
        wt=max(r["transient_alert_rate"]["rate_pct"] for r in nonlevel)
        wc=max(r["combined_any_alert_rate"]["rate_pct"] for r in nulls)
        wp=max(r["pre_onset_combined_rate"]["rate_pct"] for r in shifts)
        sens=round(statistics.mean(r["structural_rate"]["rate_pct"] for r in shifts),2)
        life=all(r["pending_lifecycle_accounting_complete"] for r in rows.values())
        gates={"structural_fpr_all_nonlevel_le_5":ws<=5,
               "transient_fpr_all_nonlevel_le_5":wt<=5,
               "combined_fpr_all_pure_null_le_5":wc<=5,
               "pre_onset_combined_all_shifts_le_5":wp<=5,
               "mean_directional_sensitivity_ge_93":sens>=93,"lifecycle_accounting":life}
        models[name]={"cases":rows,"worst_structural_fpr_nonlevel_pct":ws,
          "worst_transient_fpr_nonlevel_pct":wt,"worst_combined_fpr_pure_null_pct":wc,
          "worst_pre_onset_combined_pct":wp,"mean_directional_sensitivity_pct":sens,
          "lifecycle_accounting_complete":life,"point_gates":gates}
    return {"stage":stage,"seed_base":seed_base,"trials_per_case":trials,
       "generated_series_count":len(CASES)*trials,"configuration_evaluations":len(CASES)*trials*len(configs),
       "same_generated_series_for_all_configurations":True,"models":models}

def confidence_gates(m):
    rows=m["cases"].values()
    nonlevel=[r for r in rows if r["scenario_type"] in ("pure_null","variance_jump")]
    nulls=[r for r in m["cases"].values() if r["scenario_type"]=="pure_null"]
    shifts=[r for r in m["cases"].values() if r["scenario_type"]=="level_shift"]
    return {
      "structural_wilson_upper95_all_nonlevel_le_5":all(r["structural_rate"]["wilson95_pct"][1]<=5 for r in nonlevel),
      "transient_wilson_upper95_all_nonlevel_le_5":all(r["transient_alert_rate"]["wilson95_pct"][1]<=5 for r in nonlevel),
      "combined_wilson_upper95_all_pure_null_le_5":all(r["combined_any_alert_rate"]["wilson95_pct"][1]<=5 for r in nulls),
      "pre_onset_combined_wilson_upper95_all_shifts_le_5":all(r["pre_onset_combined_rate"]["wilson95_pct"][1]<=5 for r in shifts),
      "mean_directional_sensitivity_ge_93":m["mean_directional_sensitivity_pct"]>=93,
      "lifecycle_accounting":m["lifecycle_accounting_complete"]}

METRICS=("worst_structural_fpr_nonlevel_pct","worst_transient_fpr_nonlevel_pct",
 "worst_combined_fpr_pure_null_pct","worst_pre_onset_combined_pct","mean_directional_sensitivity_pct")
def deltas(models,left,right):
    return {k:round(models[right][k]-models[left][k],4) for k in METRICS}

def run(dev_trials=500,holdout_trials=500,dev_seed=DEV_SEED_BASE,hold_seed=HOLDOUT_SEED_BASE,
        output=OUTPUT,official=True):
    if dev_trials<1 or holdout_trials<1: raise ValueError("trial_counts_must_be_positive")
    if official and (dev_trials!=500 or holdout_trials!=500 or dev_seed!=DEV_SEED_BASE or hold_seed!=HOLDOUT_SEED_BASE):
        raise ValueError("official_B62_requires_500_trials_and_18M_19M")
    if N!=140 or ONSET!=65: raise AssertionError("generator_contract_mismatch")
    t=time.perf_counter(); dev=evaluate(dev_seed,DEV_CONFIGS,dev_trials,"development_18M"); dev_sec=round(time.perf_counter()-t,2)
    # Threshold 8 and target config are frozen before the 19M stage.
    t=time.perf_counter(); hold=evaluate(hold_seed,HOLDOUT_CONFIGS,holdout_trials,"paired_validation_19M"); hold_sec=round(time.perf_counter()-t,2)
    dr,sr=seed_ranges(dev_seed,dev_trials),seed_ranges(hold_seed,holdout_trials)
    disjoint=seed_blocks_disjoint(dr,sr)
    if not disjoint: raise AssertionError("development_holdout_seed_overlap")
    hg={n:confidence_gates(m) for n,m in hold["models"].items()}
    hf={n:all(g.values()) for n,g in hg.items()}
    report={"experiment":"B-v6.2 D1/P1 with conditional sign-flip scale guard",
      "candidate_branch":"experiment/b6-2-sign-flip-guard","parent_B61_commit":"1f3f369f9c0b67344954d288c99d923d5b9b5c22",
      "frozen_guard_spec":{"D":True,"P":True,"global_G":False,"sign_flip_guard":True,
       "threshold":8,"scale_multiplier_when_active":"1 + 0.25*rho","window_points":12,
       "first_differences":11,"max_adjacent_sign_comparisons":10,
       "flip_count_definition":"sign changes between adjacent non-zero first differences",
       "activation":"flip_count >= 8"},
      "design":{"cases":[c[0] for c in CASES],"trials_per_case":500,"development_seed_base":dev_seed,
       "holdout_seed_base":hold_seed,"seed_scheme":"seed_base + case_index*10000 + trial_index",
       "development_seed_ranges":dr,"holdout_seed_ranges":sr,"seed_blocks_disjoint":disjoint,
       "development_configurations":list(DEV_CONFIGS),"holdout_configurations":list(HOLDOUT_CONFIGS),
       "development_generated_series":dev["generated_series_count"],"development_evaluations":dev["configuration_evaluations"],
       "holdout_generated_series":hold["generated_series_count"],"holdout_evaluations":hold["configuration_evaluations"],
       "same_generated_series_within_stage":True,"holdout_used_for_threshold_selection":False,
       "fpr_budget_pct":5,"sensitivity_target_pct":93,"wilson_confidence_level_pct":95},
      "development_18M":dev,"development_elapsed_seconds":dev_sec,
      "development_candidate_minus_D1P1G0":deltas(dev["models"],G0,SF8),
      "paired_validation_19M":hold,"holdout_elapsed_seconds":hold_sec,
      "holdout_candidate_minus_D1P1G0":deltas(hold["models"],G0,SF8),
      "holdout_candidate_minus_B6a":deltas(hold["models"],B6A,SF8),
      "holdout_confidence_gates":hg,"holdout_final_gates":hf,
      "holdout_sensitivity_noninferior_to_D1P1G0":hold["models"][SF8]["mean_directional_sensitivity_pct"]>=hold["models"][G0]["mean_directional_sensitivity_pct"],
      "holdout_candidate_approved":hf[SF8]}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for label,stage in (("18M DEVELOPMENT",dev),("19M VALIDATION",hold)):
        print("\n"+label,flush=True)
        for name,m in stage["models"].items():
            active=sum(r["instrumentation"]["sign_flip_guard_active_windows"] for r in m["cases"].values())
            windows=sum(r["instrumentation"]["sign_flip_windows_evaluated"] for r in m["cases"].values())
            print(f"{name} | structural={m['worst_structural_fpr_nonlevel_pct']:.2f} | transient={m['worst_transient_fpr_nonlevel_pct']:.2f} | combined={m['worst_combined_fpr_pure_null_pct']:.2f} | pre={m['worst_pre_onset_combined_pct']:.2f} | sensitivity={m['mean_directional_sensitivity_pct']:.2f} | lifecycle={m['lifecycle_accounting_complete']} | guard_active={100*active/max(windows,1):.2f}%",flush=True)
    print("holdout_delta_vs_D1P1G0",report["holdout_candidate_minus_D1P1G0"],flush=True)
    print("holdout_delta_vs_B6a",report["holdout_candidate_minus_B6a"],flush=True)
    print("sensitivity_noninferior",report["holdout_sensitivity_noninferior_to_D1P1G0"],flush=True)
    print("wilson_gates",hg[SF8],flush=True)
    print("candidate_approved",hf[SF8],flush=True)
    print("report",output,flush=True)
    return report

def main():
    p=argparse.ArgumentParser(); p.add_argument("--dev-trials",type=int,default=500); p.add_argument("--holdout-trials",type=int,default=500); p.add_argument("--smoke",action="store_true"); a=p.parse_args()
    if a.smoke: run(12,12,1_400_000,2_400_000,Path("/tmp/b62_smoke_report.json"),False)
    else: run(a.dev_trials,a.holdout_trials)
    return 0
if __name__=="__main__": raise SystemExit(main())
