"""Faithful test implementation of Gemini's Asymmetry-Guarded Bounded CUSUM."""
from __future__ import annotations
import argparse, json, math, statistics
from pathlib import Path
from typing import Any, Mapping, Sequence
from experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion import wilson
from experiments.identity_lab.exp_p_engine_holdout.robust_holdout import (
    HOLDOUT_SEED_BASE, HOLDOUT_TRIALS, NULL_SCENARIOS, SHIFT_SCENARIOS,
    SCENARIOS, QUIET_RANGE, ONSET, generate_residuals,
)
PSI_BOUND, GAMMA, K, H = 1.8, 0.90, 0.50, 9.5
DWELL_REQUIRED, ASYMMETRY_RATIO, COOLDOWN_STEPS, QUIET_END = 4, 3.5, 6, 40
OUTPUT = Path(__file__).resolve().parent / "results" / "asymmetry_guarded_cusum_h_screen.json"

def _median(values: Sequence[float]) -> float:
    if not values: raise ValueError("ag_cusum_empty_sample")
    return float(statistics.median(values))

def _pearson_rho(values: Sequence[float]) -> float:
    if len(values) < 3: return 0.0
    a,b=values[:-1],values[1:]
    ma,mb=statistics.mean(a),statistics.mean(b)
    va=sum((x-ma)**2 for x in a); vb=sum((x-mb)**2 for x in b)
    if va<=0 or vb<=0: return 0.0
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb)

def asymmetry_guarded_bounded_cusum(
    series: Sequence[float], quiet_end: int=QUIET_END,
    psi_bound: float=PSI_BOUND, gamma: float=GAMMA, k: float=K, h: float=H,
    dwell_required: int=DWELL_REQUIRED, asymmetry_ratio: float=ASYMMETRY_RATIO,
    cooldown_steps: int=COOLDOWN_STEPS,
) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    """Reproduce supplied equations/defaults; time values are zero-based."""
    values=[float(v) for v in series]
    if quiet_end<3 or len(values)<=quiet_end:
        raise ValueError("ag_cusum_quiet_window_invalid")
    if any(not math.isfinite(v) for v in values):
        raise ValueError("ag_cusum_series_nonfinite")
    if psi_bound<=0 or not 0<=gamma<1 or k<0 or h<=0 or dwell_required<1 or asymmetry_ratio<=0 or cooldown_steps<0:
        raise ValueError("ag_cusum_parameter_invalid")
    quiet=values[:quiet_end]
    med=_median(quiet)
    quiet_diffs=[quiet[i]-quiet[i-1] for i in range(1,len(quiet))]
    base_diff_scale=max(_median([abs(v) for v in quiet_diffs])*1.4826/math.sqrt(2.0),1e-6)
    quiet_marginal=1.4826*_median([abs(v-med) for v in quiet])
    rho_raw=_pearson_rho(quiet)
    rho_used=min(0.9,max(0.0,rho_raw))
    s_pos=s_neg=0.0
    dwell_pos=dwell_neg=cooldown=0
    alerts=[]
    recent_diffs=[abs(v) for v in quiet_diffs[-15:]]
    scale_path=[]
    for t in range(quiet_end,len(values)):
        recent_diffs.append(abs(values[t]-values[t-1]))
        if len(recent_diffs)>20: recent_diffs.pop(0)
        current_scale=_median(recent_diffs)*1.4826/math.sqrt(2.0)
        effective_scale=max(base_diff_scale,current_scale)
        scale_path.append(effective_scale)
        if cooldown>0:
            cooldown-=1
            continue
        z_t=(values[t]-med)/effective_scale
        x_t=max(-psi_bound,min(psi_bound,z_t))
        s_pos=max(0.0,gamma*s_pos+x_t-k)
        s_neg=max(0.0,gamma*s_neg-x_t-k)
        pos_dominant=s_pos/(s_neg+1.0)>=asymmetry_ratio
        neg_dominant=s_neg/(s_pos+1.0)>=asymmetry_ratio
        dwell_pos=dwell_pos+1 if (s_pos>h and pos_dominant) else 0
        dwell_neg=dwell_neg+1 if (s_neg>h and neg_dominant) else 0
        if dwell_pos>=dwell_required:
            alerts.append({"time":t,"direction":1,"stat":round(float(s_pos),3)})
            s_pos=s_neg=0.0; dwell_pos=dwell_neg=0; cooldown=cooldown_steps
        elif dwell_neg>=dwell_required:
            alerts.append({"time":t,"direction":-1,"stat":round(float(s_neg),3)})
            s_pos=s_neg=0.0; dwell_pos=dwell_neg=0; cooldown=cooldown_steps
    diag={
        "quiet_median":med,"quiet_marginal_mad_sigma":quiet_marginal,
        "base_first_difference_scale":base_diff_scale,
        "first_difference_to_marginal_scale_ratio":base_diff_scale/quiet_marginal if quiet_marginal>0 else None,
        "rho_raw":rho_raw,"rho_used":rho_used,
        "ar1_scale_ratio_theoretical_if_stationary":math.sqrt(max(0.0,1.0-rho_used)),
        "effective_parameters":{"psi_bound":psi_bound,"gamma":gamma,"k":k,"h":h,
          "dwell_required":dwell_required,"asymmetry_ratio":asymmetry_ratio,"cooldown_steps":cooldown_steps},
        "scale_median":_median(scale_path),"scale_median_last_20":_median(scale_path[-20:]),
        "alert_count":len(alerts),"scale_path":scale_path,
    }
    return alerts,diag

def _score_alerts(alerts: Sequence[Mapping[str,Any]],scenario: str)->dict[str,Any]:
    normalized=[{"month":int(a["time"])+1,"direction":int(a["direction"])} for a in alerts]
    if scenario in NULL_SCENARIOS:
        false=[a for a in normalized if a["month"]>QUIET_RANGE[1]]
        return {"false_alarm":bool(false),"false_event_count":len(false),"pre_onset_false_alarm":False,
          "detected":False,"wrong_direction":False,"delay":None}
    expected=-1 if "negative" in scenario else 1
    pre=[a for a in normalized if QUIET_RANGE[1]<a["month"]<ONSET]
    post=[a for a in normalized if a["month"]>=ONSET]
    correct=[a for a in post if a["direction"]==expected]
    wrong=[a for a in post if a["direction"]!=expected]
    first=min((a["month"] for a in correct),default=None)
    return {"false_alarm":False,"false_event_count":0,"pre_onset_false_alarm":bool(pre),
      "detected":first is not None,"wrong_direction":bool(wrong),
      "delay":first-ONSET if first is not None else None}

def evaluate_h_seed_screen(h_report: Mapping[str,Any],trials:int=HOLDOUT_TRIALS)->dict[str,Any]:
    if trials!=int(h_report["holdout_trials_per_scenario"]) or int(h_report["holdout_seed_base"])!=HOLDOUT_SEED_BASE:
        raise ValueError("AG_CUSUM_seed_or_trial_range_must_match_H")
    counts={s:{"false":0,"false_events":0,"pre":0,"detected":0,"wrong":0,"delays":[],"raw":0,"rho":[],"ratio":[],"scale":[]} for s in SCENARIOS}
    for si,scenario in enumerate(SCENARIOS):
        target=counts[scenario]
        for trial in range(trials):
            seed=HOLDOUT_SEED_BASE+si*100_000+trial
            values=generate_residuals(seed,scenario)
            alerts,diag=asymmetry_guarded_bounded_cusum(values)
            m=_score_alerts(alerts,scenario)
            target["false"]+=int(m["false_alarm"]); target["false_events"]+=m["false_event_count"]
            target["pre"]+=int(m["pre_onset_false_alarm"]); target["detected"]+=int(m["detected"])
            target["wrong"]+=int(m["wrong_direction"]); target["raw"]+=len(alerts)
            if m["delay"] is not None: target["delays"].append(float(m["delay"]))
            target["rho"].append(float(diag["rho_used"]))
            if diag["first_difference_to_marginal_scale_ratio"] is not None:
                target["ratio"].append(float(diag["first_difference_to_marginal_scale_ratio"]))
            target["scale"].append(float(diag["scale_median_last_20"]))
    sr={}
    for scenario,c in counts.items():
        if scenario in NULL_SCENARIOS:
            sr[scenario]={"false_alarm_count":c["false"],"false_alarm_rate":c["false"]/trials,
              "false_alarm_wilson95":wilson(c["false"],trials),
              "false_events_per_sequence":c["false_events"]/trials,
              "raw_alerts_per_sequence":c["raw"]/trials}
        else:
            sr[scenario]={"pre_onset_false_alarm_count":c["pre"],
              "pre_onset_false_alarm_rate":c["pre"]/trials,
              "pre_onset_false_wilson95":wilson(c["pre"],trials),
              "detected_count":c["detected"],"sensitivity":c["detected"]/trials,
              "sensitivity_wilson95":wilson(c["detected"],trials),
              "wrong_direction_trial_rate":c["wrong"]/trials,
              "mean_detection_delay":statistics.mean(c["delays"]) if c["delays"] else None,
              "median_detection_delay":statistics.median(c["delays"]) if c["delays"] else None,
              "raw_alerts_per_sequence":c["raw"]/trials}
    worst_null=max(sr[s]["false_alarm_rate"] for s in NULL_SCENARIOS)
    min_sens=min(sr[s]["sensitivity"] for s in SHIFT_SCENARIOS)
    worst_pre=max(sr[s]["pre_onset_false_alarm_rate"] for s in SHIFT_SCENARIOS)
    h_baselines={}
    for name,v in h_report["results"].items():
        h_baselines[name]={"worst_null_false_alarm_rate":v["worst_holdout_null_false_alarm_rate"],
          "minimum_shift_sensitivity":v["minimum_holdout_shift_sensitivity"],
          "mean_shift_sensitivity":v["mean_holdout_shift_sensitivity"],
          "holdout_gate":v["holdout_gate"],
          "per_scenario":{s:{"false_alarm_rate":x.get("false_alarm_rate"),
            "sensitivity":x.get("sensitivity"),"pre_onset_false_alarm_rate":x.get("pre_onset_false_alarm_rate"),
            "mean_detection_delay":x.get("mean_detection_delay")} for s,x in v["scenarios"].items()}}
    all_rho=[x for c in counts.values() for x in c["rho"]]
    all_ratio=[x for c in counts.values() for x in c["ratio"]]
    all_scale=[x for c in counts.values() for x in c["scale"]]
    return {
      "experiment":"p_engine_asymmetry_guarded_bounded_cusum_H_seed_screen_v1",
      "candidate":"AG-CUSUM Gemini revision","same_H_seed_range":True,"trials_per_scenario":trials,
      "seed_base":HOLDOUT_SEED_BASE,"scenario_names":list(SCENARIOS),
      "parameters":{"psi_bound":PSI_BOUND,"gamma":GAMMA,"k":K,"h":H,
        "dwell_required":DWELL_REQUIRED,"asymmetry_ratio":ASYMMETRY_RATIO,
        "cooldown_steps":COOLDOWN_STEPS,"quiet_end":QUIET_END},
      "aggregate":{"worst_null_false_alarm_rate":worst_null,"minimum_shift_sensitivity":min_sens,
        "mean_shift_sensitivity":statistics.mean(sr[s]["sensitivity"] for s in SHIFT_SCENARIOS),
        "worst_pre_onset_false_alarm_rate":worst_pre,
        "pass_point_gates":worst_null<=0.05 and min_sens>=0.75},
      "scale_diagnostics":{"median_rho":statistics.median(all_rho),
        "median_first_difference_to_marginal_scale_ratio":statistics.median(all_ratio),
        "median_last20_effective_scale":statistics.median(all_scale),
        "stationary_AR1_relation":"sd(diff)/sqrt(2) = marginal_sigma*sqrt(1-rho); positive rho lowers this scale"},
      "scenarios":sr,"H_baseline_reference":h_baselines,
      "decision_rule":"All null point rates <=5% and all directional sensitivities >=75%; confidence intervals are reported; a fresh seed confirmation is required.",
      "limitations":["Uses H's same synthetic seeds for a paired comparison; not a second untouched holdout.",
        "A Huber bound and directional ratio do not create a theoretical false-alarm guarantee.",
        "The asymmetry ratio may reject real mixed-direction events."]
    }

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--h-report",type=Path,required=True)
    parser.add_argument("--trials",type=int,default=HOLDOUT_TRIALS); parser.add_argument("--output",type=Path,default=OUTPUT)
    args=parser.parse_args(); report=evaluate_h_seed_screen(json.loads(args.h_report.read_text(encoding="utf-8")),args.trials)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(args.output),"aggregate":report["aggregate"],
      "scale_diagnostics":report["scale_diagnostics"]},ensure_ascii=False,indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
