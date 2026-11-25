"""Untouched-seed confirmation of AG-CUSUM with Gemini's fixed defaults."""
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from typing import Any
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson
from experiments.identity_lab.exp_p_engine_holdout.robust_holdout import (
    NULL_SCENARIOS,SHIFT_SCENARIOS,SCENARIOS,HOLDOUT_TRIALS,generate_residuals,
)
from experiments.identity_lab.exp_p_engine_holdout.asymmetry_guarded_cusum import (
    asymmetry_guarded_bounded_cusum,_score_alerts,
)
TRIALS=1000
SEED_BASE=7_300_000
OUTPUT=Path(__file__).resolve().parent/"results"/"asymmetry_guarded_cusum_confirmation.json"

def run_confirmation(trials:int=TRIALS)->dict[str,Any]:
    if trials<500: raise ValueError("AG_confirmation_trials_must_be_at_least_500")
    counts={s:{"false":0,"false_events":0,"pre":0,"detected":0,"wrong":0,"delays":[],"raw":0,"rho":[],"ratio":[]} for s in SCENARIOS}
    for si,scenario in enumerate(SCENARIOS):
        c=counts[scenario]
        for trial in range(trials):
            seed=SEED_BASE+si*100_000+trial
            values=generate_residuals(seed,scenario)
            alerts,diag=asymmetry_guarded_bounded_cusum(values)
            m=_score_alerts(alerts,scenario)
            c["false"]+=int(m["false_alarm"]); c["false_events"]+=m["false_event_count"]
            c["pre"]+=int(m["pre_onset_false_alarm"]); c["detected"]+=int(m["detected"])
            c["wrong"]+=int(m["wrong_direction"]); c["raw"]+=len(alerts)
            if m["delay"] is not None:c["delays"].append(float(m["delay"]))
            c["rho"].append(float(diag["rho_used"]))
            if diag["first_difference_to_marginal_scale_ratio"] is not None:
                c["ratio"].append(float(diag["first_difference_to_marginal_scale_ratio"]))
    scenarios={}
    for s,c in counts.items():
        if s in NULL_SCENARIOS:
            scenarios[s]={"false_alarm_count":c["false"],"false_alarm_rate":c["false"]/trials,
              "false_alarm_wilson95":wilson(c["false"],trials),
              "false_events_per_sequence":c["false_events"]/trials,
              "raw_alerts_per_sequence":c["raw"]/trials}
        else:
            scenarios[s]={"pre_onset_false_alarm_count":c["pre"],
              "pre_onset_false_alarm_rate":c["pre"]/trials,
              "pre_onset_false_wilson95":wilson(c["pre"],trials),
              "detected_count":c["detected"],"sensitivity":c["detected"]/trials,
              "sensitivity_wilson95":wilson(c["detected"],trials),
              "wrong_direction_trial_rate":c["wrong"]/trials,
              "mean_detection_delay":statistics.mean(c["delays"]) if c["delays"] else None,
              "median_detection_delay":statistics.median(c["delays"]) if c["delays"] else None,
              "raw_alerts_per_sequence":c["raw"]/trials}
    worst_null=max(scenarios[s]["false_alarm_rate"] for s in NULL_SCENARIOS)
    worst_null_upper=max(scenarios[s]["false_alarm_wilson95"][1] for s in NULL_SCENARIOS)
    worst_pre=max(scenarios[s]["pre_onset_false_alarm_rate"] for s in SHIFT_SCENARIOS)
    worst_pre_upper=max(scenarios[s]["pre_onset_false_wilson95"][1] for s in SHIFT_SCENARIOS)
    min_sensitivity=min(scenarios[s]["sensitivity"] for s in SHIFT_SCENARIOS)
    min_sensitivity_lower=min(scenarios[s]["sensitivity_wilson95"][0] for s in SHIFT_SCENARIOS)
    return {"experiment":"p_engine_ag_cusum_untouched_seed_confirmation_v1",
      "candidate":"AG-CUSUM Gemini revision, fixed defaults; no tuning",
      "trials_per_scenario":trials,"seed_base":SEED_BASE,"scenario_names":list(SCENARIOS),
      "parameters":{"psi_bound":1.8,"gamma":0.90,"k":0.50,"h":9.5,"dwell_required":4,
        "asymmetry_ratio":3.5,"cooldown_steps":6,"quiet_end":40},
      "aggregate":{"worst_null_false_alarm_rate":worst_null,"worst_null_wilson_upper95":worst_null_upper,
        "worst_pre_onset_false_alarm_rate":worst_pre,"worst_pre_onset_wilson_upper95":worst_pre_upper,
        "minimum_shift_sensitivity":min_sensitivity,"minimum_shift_wilson_lower95":min_sensitivity_lower,
        "point_gate_pass":worst_null<=0.05 and min_sensitivity>=0.75,
        "confidence_gate_pass":worst_null_upper<=0.05 and min_sensitivity_lower>=0.75},
      "scale_diagnostics":{"median_rho":statistics.median([x for c in counts.values() for x in c["rho"]]),
        "median_first_difference_to_marginal_scale_ratio":statistics.median([x for c in counts.values() for x in c["ratio"]])},
      "scenarios":scenarios,
      "decision":"confirmation_complete_no_parameter_tuning; candidate is not promoted unless both point and confidence gates pass",
      "limitations":["Synthetic declared AR(1)/Student-t3 regimes only; no universal or field guarantee.",
        "This is an untouched seed range relative to Stage H; the fixed defaults came from the supplied Gemini proposal, not from tuning on this run."]}

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--trials",type=int,default=TRIALS);parser.add_argument("--output",type=Path,default=OUTPUT)
    args=parser.parse_args();report=run_confirmation(args.trials)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(args.output),"aggregate":report["aggregate"],
      "scenarios":{s:{"false_alarm_rate":v.get("false_alarm_rate"),"sensitivity":v.get("sensitivity"),
        "pre_onset_false_alarm_rate":v.get("pre_onset_false_alarm_rate")} for s,v in report["scenarios"].items()}},ensure_ascii=False,indent=2))
    return 0
if __name__=="__main__":raise SystemExit(main())
