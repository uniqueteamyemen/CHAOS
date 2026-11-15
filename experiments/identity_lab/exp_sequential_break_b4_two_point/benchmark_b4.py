"""Paired B-v3.1 / B-v3.2 / B-v4 comparison on the frozen eight-case matrix.

B-v4 is pre-specified; no parameter tuning is performed on the 5M+ block.
The 5M+ block has already been inspected in earlier B-v3.2 work, so this is
a comparative replay rather than a pristine unseen holdout.
"""
from __future__ import annotations
import argparse, json, math, statistics, time
from pathlib import Path
from typing import Any
import numpy as np

from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import (
    AuditedSequentialBreakEngineB3, N, ONSET, generate_series,
)
from experiments.identity_lab.exp_sequential_break_b3_2_retest.engine_b3_2_retest import (
    CalibratedSequentialBreakEngineB32,
)
from experiments.identity_lab.exp_sequential_break_b4_two_point.engine_b4 import (
    TwoPointTransientWinsor18EngineB4,
)

CASES = [
    ("gauss_r0.3_null", "gauss", 0.3, False, 0.0),
    ("gauss_r0.7_null", "gauss", 0.7, False, 0.0),
    ("gauss_r0.7_vjump", "gauss", 0.7, True, 0.0),
    ("t3_r0.3_null", "t3", 0.3, False, 0.0),
    ("t3_r0.7_null", "t3", 0.7, False, 0.0),
    ("t3_r0.7_vjump", "t3", 0.7, True, 0.0),
    ("pos_shift_3.0s", "gauss", 0.7, False, 3.0),
    ("neg_shift_3.0s", "gauss", 0.7, False, -3.0),
]
MODELS = ("B-v3.1", "B-v3.2", "B-v4")
DEV_SEED_BASE, HOLDOUT_SEED_BASE = 4_000_000, 5_000_000
FPR_LIMIT, SENSITIVITY_TARGET = 5.0, 93.0
OUTPUT = Path(__file__).resolve().parent / "results" / "sequential_break_engine_b3_1_b3_2_b4_comparison.json"


def wilson(successes: int, trials: int) -> list[float]:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid_binomial_counts")
    z = 1.959963984540054
    p = successes / trials
    d = 1.0 + z*z/trials
    center = (p + z*z/(2*trials))/d
    half = z*math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials))/d
    return [max(0.0, center-half), min(1.0, center+half)]


def rate(successes: int, trials: int) -> dict[str, Any]:
    lo, hi = wilson(successes, trials)
    return {"sequences":successes,"rate_pct":round(100*successes/trials,2),
            "wilson95_pct":[round(100*lo,2),round(100*hi,2)]}


def classify(result: dict[str, Any], shift: float) -> dict[str, Any]:
    breaks=list(result["structural_breaks"]); trans=list(result["transient_anomalies"])
    unres=list(result["unresolved_alerts"])
    if shift == 0.0:
        structural=bool(breaks); wrong=[]; pre_b=[]; pre_t=[]; pre_u=[]; delay=None
    else:
        expected=1 if shift>0 else -1
        pre_b=[b for b in breaks if int(b["detection_time"])<ONSET]
        post=[b for b in breaks if int(b["detection_time"])>=ONSET]
        correct=[b for b in post if int(b["direction"])==expected]
        wrong=[b for b in post if int(b["direction"])!=expected]
        first=min(correct,key=lambda b:int(b["detection_time"])) if correct else None
        delay=int(first["detection_time"])-ONSET if first else None
        structural=bool(correct)
        pre_t=[a for a in trans if int(a["time"])<ONSET]
        pre_u=[a for a in unres if int(a["time"])<ONSET]
    life=result["pending_lifecycle"]
    terminal=int(life["resolved_structural_count"])+int(life["resolved_transient_count"])+int(life["unresolved_count"])
    return {
        "structural":bool(structural),"any_structural":bool(breaks),
        "transient":bool(trans),"unresolved":bool(unres),
        "combined":bool(breaks or trans or unres),
        "wrong_direction":bool(wrong),"pre_structural":bool(pre_b),
        "pre_transient":bool(pre_t),"pre_unresolved":bool(pre_u),
        "pre_combined":bool(pre_b or pre_t or pre_u),"delay":delay,
        "events":{"structural":len(breaks),"transient":len(trans),"unresolved":len(unres),
          "pending_opened":int(life["opened_count"]),
          "pending_resolved_structural":int(life["resolved_structural_count"]),
          "pending_resolved_transient":int(life["resolved_transient_count"]),
          "pending_unresolved":int(life["unresolved_count"])},
        "lifecycle_ok":bool(life["accounting_complete"]) and int(life["opened_count"])==terminal,
    }


def empty_counts() -> dict[str, Any]:
    return {"structural":0,"any_structural":0,"transient":0,"unresolved":0,"combined":0,
      "wrong_direction":0,"pre_structural":0,"pre_transient":0,"pre_unresolved":0,
      "pre_combined":0,"delays":[],"lifecycle_ok":True,
      "events":{"structural":0,"transient":0,"unresolved":0,"pending_opened":0,
        "pending_resolved_structural":0,"pending_resolved_transient":0,"pending_unresolved":0}}


def add(c: dict[str, Any], m: dict[str, Any]) -> None:
    for k in ("structural","any_structural","transient","unresolved","combined","wrong_direction",
              "pre_structural","pre_transient","pre_unresolved","pre_combined"):
        c[k]+=int(m[k])
    if m["delay"] is not None: c["delays"].append(m["delay"])
    c["lifecycle_ok"]=c["lifecycle_ok"] and m["lifecycle_ok"]
    for k,v in m["events"].items(): c["events"][k]+=v


def summarize_case(shift: float, var_jump: bool, c: dict[str, Any], trials: int) -> dict[str, Any]:
    kind="level_shift" if shift else ("variance_jump" if var_jump else "pure_null")
    return {
      "scenario_type":kind,"trials":trials,
      "structural_metric_label":"correct_directional_structural_detection" if shift else "structural_false_alarm",
      "structural_rate":rate(c["structural"],trials),
      "any_structural_alert_rate":rate(c["any_structural"],trials),
      "transient_alert_rate":rate(c["transient"],trials),
      "unresolved_alert_rate":rate(c["unresolved"],trials),
      "combined_any_alert_rate":rate(c["combined"],trials),
      "wrong_direction_structural_rate":rate(c["wrong_direction"],trials),
      "pre_onset_structural_rate":rate(c["pre_structural"],trials),
      "pre_onset_transient_rate":rate(c["pre_transient"],trials),
      "pre_onset_unresolved_rate":rate(c["pre_unresolved"],trials),
      "pre_onset_combined_rate":rate(c["pre_combined"],trials),
      "median_correct_detection_delay":round(float(statistics.median(c["delays"])),2) if c["delays"] else None,
      "event_totals":c["events"],"pending_lifecycle_accounting_complete":c["lifecycle_ok"],
    }


def make_models() -> dict[str, Any]:
    return {
      "B-v3.1":AuditedSequentialBreakEngineB3(anomaly_z_thresh=3.2,winsor_cap=2.5,break_percent_thresh=85.0,resolution_horizon=6),
      "B-v3.2":CalibratedSequentialBreakEngineB32(anomaly_z_thresh=6.0,winsor_cap=2.5,break_percent_thresh=85.0,resolution_horizon=14,rho_bias_correction=True,return_to_baseline_z=1.5),
      "B-v4":TwoPointTransientWinsor18EngineB4(anomaly_z_thresh=3.8,winsor_cap=1.8,break_percent_thresh=85.0,resolution_horizon=14,rho_bias_correction=False,return_to_baseline_z=1.5,persistence_z_thresh=1.45),
    }


def evaluate(seed_base: int, trials: int, stage: str) -> dict[str, Any]:
    engines=make_models()
    counts={m:{c[0]:empty_counts() for c in CASES} for m in MODELS}
    for ci,(name,dist,rho,vjump,shift) in enumerate(CASES):
        for trial in range(trials):
            seed=seed_base+ci*10_000+trial
            series=generate_series(np.random.default_rng(seed),dist=dist,rho=rho,var_jump=vjump,shift_sigma=shift,n=N,onset=ONSET)
            for model,engine in engines.items():
                add(counts[model][name],classify(engine.analyze(series),shift))
    out={"stage":stage,"seed_base":seed_base,"trials_per_case":trials,"case_count":len(CASES),"models":{}}
    for model in MODELS:
        rows={name:summarize_case(shift,vjump,counts[model][name],trials)
              for name,_,_,vjump,shift in CASES}
        nonlevel=[r for r in rows.values() if r["scenario_type"] in ("pure_null","variance_jump")]
        nulls=[r for r in rows.values() if r["scenario_type"]=="pure_null"]
        shifts=[r for r in rows.values() if r["scenario_type"]=="level_shift"]
        ws=max(r["structural_rate"]["rate_pct"] for r in nonlevel)
        wc=max(r["combined_any_alert_rate"]["rate_pct"] for r in nulls)
        wp=max(r["pre_onset_combined_rate"]["rate_pct"] for r in shifts)
        sens=round(statistics.mean(r["structural_rate"]["rate_pct"] for r in shifts),2)
        life=all(r["pending_lifecycle_accounting_complete"] for r in rows.values())
        out["models"][model]={
          "cases":rows,"worst_structural_fpr_non_level_pct":ws,
          "worst_combined_fpr_pure_null_pct":wc,
          "worst_pre_onset_combined_fpr_level_shift_pct":wp,
          "mean_directional_sensitivity_pct":sens,"lifecycle_accounting_complete":life,
          "point_gates":{"structural_fpr_all_non_level_le_5":ws<=FPR_LIMIT,
            "combined_fpr_all_pure_null_le_5":wc<=FPR_LIMIT,
            "pre_onset_combined_all_shifts_le_5":wp<=FPR_LIMIT,
            "mean_directional_sensitivity_ge_93":sens>=SENSITIVITY_TARGET,
            "lifecycle_accounting":life},
        }
    deltas={}
    for model in ("B-v3.2","B-v4"):
        deltas[model]={}
        for name,*_ in CASES:
            a=out["models"][model]["cases"][name]; b=out["models"]["B-v3.1"]["cases"][name]
            deltas[model][name]={metric:round(a[field]["rate_pct"]-b[field]["rate_pct"],2)
              for metric,field in (("structural","structural_rate"),("transient","transient_alert_rate"),
                                   ("unresolved","unresolved_alert_rate"),("combined","combined_any_alert_rate"))}
    out["paired_delta_percentage_points_vs_B-v3.1"]=deltas
    return out


def confidence_gates(m: dict[str, Any]) -> dict[str, bool]:
    rows=m["cases"]
    nonlevel=[r for r in rows.values() if r["scenario_type"] in ("pure_null","variance_jump")]
    nulls=[r for r in rows.values() if r["scenario_type"]=="pure_null"]
    shifts=[r for r in rows.values() if r["scenario_type"]=="level_shift"]
    sensitivity=statistics.mean(r["structural_rate"]["rate_pct"] for r in shifts)
    return {
      "structural_wilson_upper95_all_non_level_le_5":all(r["structural_rate"]["wilson95_pct"][1]<=FPR_LIMIT for r in nonlevel),
      "combined_wilson_upper95_all_pure_null_le_5":all(r["combined_any_alert_rate"]["wilson95_pct"][1]<=FPR_LIMIT for r in nulls),
      "pre_onset_combined_wilson_upper95_all_shifts_le_5":all(r["pre_onset_combined_rate"]["wilson95_pct"][1]<=FPR_LIMIT for r in shifts),
      "mean_directional_sensitivity_ge_93":sensitivity>=SENSITIVITY_TARGET,
      "lifecycle_accounting":m["lifecycle_accounting_complete"],
    }


def run(dev_trials: int=500,holdout_trials: int=500,output: Path=OUTPUT) -> dict[str,Any]:
    if dev_trials<100 or holdout_trials<100: raise ValueError("dev_and_holdout_trials_must_each_be_at_least_100")
    started=time.perf_counter(); dev=evaluate(DEV_SEED_BASE,dev_trials,"development"); dev_time=round(time.perf_counter()-started,2)
    started=time.perf_counter(); holdout=evaluate(HOLDOUT_SEED_BASE,holdout_trials,"comparative_holdout_replay"); holdout_time=round(time.perf_counter()-started,2)
    b4dev=dev["models"]["B-v4"]; b4hold=holdout["models"]["B-v4"]
    hg=confidence_gates(b4hold)
    report={
      "experiment":"sequential_break_engine_b3_1_b3_2_b4_paired_comparison",
      "candidate":"TwoPointTransientWinsor18EngineB4",
      "baseline_commit":"a07b29315d0af7d84e9e07e31ccdda32dac2b570",
      "parent_commit_including_B3_2_candidate":"66db7eb8f95a47c481fd91e0268d3adc34a81e16",
      "specification":{"rho":"rho_raw clipped [0.0,0.88]; no small-sample correction",
        "pending_gate":"two adjacent z_point_raw values each exceed 3.8 absolute and have same sign",
        "winsor_cap":1.8,"persistence_z_threshold":1.45,"resolution_horizon":14,
        "transient_resolution":"retains B-v3.2 observed return-to-baseline using fixed quiet-period scale and abs(return_z) < 1.5",
        "pending_lifecycle_invariant":"opened = resolved_structural + resolved_transient + unresolved",
        "break_percent_thresh":85.0,"series_length":N,"onset_index_zero_based":ONSET},
      "reference_configurations":{
        "B-v3.1":{"anomaly_z_thresh":3.2,"pending_gate":"single point","rho":"raw clipped [0,0.88]","winsor_cap":2.5,"persistence_z_threshold":1.30,"resolution_horizon":6,"transient_resolution":"horizon expiry"},
        "B-v3.2":{"anomaly_z_thresh":6.0,"pending_gate":"single point","rho":"small_sample_adjusted","winsor_cap":2.5,"persistence_z_threshold":1.30,"resolution_horizon":14,"transient_resolution":"observed return-to-baseline below 1.5"},
        "B-v4":{"anomaly_z_thresh":3.8,"pending_gate":"two consecutive same-direction points","rho":"raw clipped [0,0.88]","winsor_cap":1.8,"persistence_z_threshold":1.45,"resolution_horizon":14,"transient_resolution":"observed return-to-baseline below 1.5"}},
      "design":{"series_length":N,"case_count":len(CASES),"trials_per_case_dev":dev_trials,
        "trials_per_case_holdout_replay":holdout_trials,"cases":[c[0] for c in CASES],
        "distribution":["gauss","t3"],"rho_levels":[0.3,0.7],"pure_null_cases":4,
        "variance_jump_cases":2,"level_shift_cases":2,"dev_seed_base":DEV_SEED_BASE,
        "holdout_seed_base":HOLDOUT_SEED_BASE,"seed_scheme":"seed_base + case_index*10000 + trial",
        "same_generated_series_for_all_three_engines":True,
        "combined_definition":"any structural event including wrong-direction/pre-onset, transient alert, or unresolved alert",
        "holdout_integrity_warning":"5M+ seeds already inspected in B-v3.2 work; comparative replay, not a pristine unseen holdout",
        "false_alarm_budget_pct":FPR_LIMIT,"mean_directional_sensitivity_target_pct":SENSITIVITY_TARGET},
      "development":dev,"development_elapsed_seconds":dev_time,
      "holdout_replay":holdout,"holdout_replay_elapsed_seconds":holdout_time,
      "B4_development_point_gates":b4dev["point_gates"],
      "B4_holdout_confidence_gates":hg,
      "B4_final_gate_passed":all(b4dev["point_gates"].values()) and all(hg.values()),
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("=== B-v3.1 / B-v3.2 / B-v4 PAIRED COMPARISON ===",flush=True)
    for stage in ("development","holdout_replay"):
        print(f"\n[{stage}]",flush=True)
        for model in MODELS:
            m=report[stage]["models"][model]
            print(f"{model}: structural={m['worst_structural_fpr_non_level_pct']:.2f}% pure_null_combined={m['worst_combined_fpr_pure_null_pct']:.2f}% pre_onset_combined={m['worst_pre_onset_combined_fpr_level_shift_pct']:.2f}% sensitivity={m['mean_directional_sensitivity_pct']:.2f}% lifecycle={m['lifecycle_accounting_complete']}",flush=True)
    print(f"\nB4_holdout_confidence_gates={hg}",flush=True)
    print(f"B4_final_gate_passed={report['B4_final_gate_passed']}",flush=True)
    print(f"artifact={output}",flush=True)
    return report


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--dev-trials",type=int,default=500)
    p.add_argument("--holdout-trials",type=int,default=500)
    p.add_argument("--output",type=Path,default=OUTPUT)
    a=p.parse_args(); run(a.dev_trials,a.holdout_trials,a.output); return 0


if __name__=="__main__":
    raise SystemExit(main())
